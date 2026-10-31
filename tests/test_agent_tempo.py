"""Tempo of a whole Agent turn on a slow database (since 2026-10-21).

Prod 2026-10-21: a packing-list question took 7:18 min. OpenRouter answered
every model call in seconds, but our server wrote each status line of each
call (waiting, working, the live reasoning line every 3 s, completed) as its
own Firestore transaction, one after another, and held the run's lock while
doing it. Six comparison answers and the judges then waited in that queue
instead of reading their streams: requests left up to 77 s late, finished
judge answers were cancelled after 90 s.

This test plays a turn with six comparison models, which also review the
agent's work and answer (agent_audit.py; the judges of comparison mode until
2026-10-31), on a database where each round trip (a read, a batched read, a
commit) takes ROUND_TRIP, one transaction of the account at a time, and
measures what the server adds to the models' own time. It fails when a change puts database work back between
a model's stream and the server reading it, or lets the bookkeeping queue grow
with the number of parallel calls again.
"""
import json
import threading
import time

import pytest

from app.core import config as cfg
from app.services import agent_delegation
from app.services.agent_comparison import comparison_selection
from app.services.agent_delegation import DelegationLoop
from app.services.agent_delegation_config import defaults
from app.services.agent_policy import AgentPolicy
from app.services.agent_runs import AgentRunStore
from app.services.llm.agent_client import AgentCompletion, measured_usage, resolve_agent_model
from app.services.llm.provider_runtime import ProviderCancellation
from test_agent_comparison import REVIEWER
from test_agent_runs import Database, UID, pending
from test_chat_history import FakeTransaction

# Wall-clock limits: the CI runs them away from the parallel suite (pytest.ini).
pytestmark = pytest.mark.tempo

# One Firestore round trip. Production 2026-10-21: a transaction of six single
# reads took 0.4-0.5 s, a commit about as long as one read more (eur3).
ROUND_TRIP = 0.01
# A comparison answer streams this long, with a reasoning sentence every TICK.
MODEL_SECONDS = 1.0
TICK = 0.02
# The chat model's answer and each reviewer's round.
ANSWER_SECONDS = REVIEW_SECONDS = 0.3


class SlowTransaction(FakeTransaction):
    def get(self, ref):
        time.sleep(ROUND_TRIP)
        return super().get(ref)

    def get_all(self, refs):
        time.sleep(ROUND_TRIP)
        return [FakeTransaction.get(self, ref) for ref in refs]

    def commit(self):
        time.sleep(ROUND_TRIP)
        return super().commit()


class SlowDatabase(Database):
    """Transactions one at a time, like the account's Firestore transactions
    behind agent_quota.account_lock, each round trip ROUND_TRIP."""

    def run_transaction(self, operation):
        with self.lock:
            transaction = SlowTransaction(self)
            result = operation(transaction)
            transaction.commit()
            return result


def reasoning(step_id, i):
    return {"type": "activity", "version": 1, "step_id": step_id, "id": "r", "kind": "reasoning",
            "format": "text", "text": f"Checking source {i} against the stated budget limit. ", "append": True}


class Timeline:
    """What the scripted providers saw: when each request left and how long
    the server kept each stream waiting between two of its events."""

    def __init__(self):
        self.lock = threading.Lock()
        self.compare_started = None
        self.dispatched = {}
        self.stalls = []
        self.answer_done = None

    def factory(self):
        timeline = self

        class Completion(AgentCompletion):
            def _paced(self, events, seconds):
                """Yields ``events`` spread over ``seconds``; records how long the
                server held the stream before asking for the next event."""
                pause = seconds / max(1, len(events))
                for event in events:
                    handed = time.monotonic()
                    yield event
                    with timeline.lock:
                        timeline.stalls.append((self.step_id, time.monotonic() - handed))
                    time.sleep(pause)

            def stream(self, *, model, messages, **kwargs):
                self.usage = measured_usage({"prompt_tokens": 50, "completion_tokens": 20, "cost": .0001}, model)
                if self.step_id == "completion:0":
                    args = {"question": "What should I pack for a marathon training camp?", "context": ""}
                    self.tool_calls = [{"id": "call_0", "type": "function",
                                        "function": {"name": "compare_models", "arguments": json.dumps(args)}}]
                    self.finish_reason = "tool_calls"
                    timeline.compare_started = time.monotonic()
                    return
                if self.step_id.startswith("completion:"):
                    self.text, self.finish_reason = "Pack one outfit per training day plus a spare.", "stop"
                    yield from self._paced([{"type": "delta", "text": self.text}], ANSWER_SECONDS)
                    timeline.answer_done = time.monotonic()
                    return
                if messages[0]["content"].startswith(REVIEWER):
                    # A reviewer's round, live or final: no objection.
                    yield from self._paced([reasoning(self.step_id, i) for i in range(5)], REVIEW_SECONDS)
                    self.text, self.finish_reason = json.dumps({"marks": []}), "stop"
                    yield {"type": "delta", "text": self.text}
                    return
                with timeline.lock:
                    timeline.dispatched[self.step_id] = time.monotonic()
                ticks = int(MODEL_SECONDS / TICK)
                yield from self._paced([reasoning(self.step_id, i) for i in range(ticks)], MODEL_SECONDS)
                self.text, self.finish_reason = "Running shoes, two pairs. Recovery food for every day.", "stop"
                yield {"type": "delta", "text": self.text}

        return Completion()


@pytest.fixture
def slow_store(monkeypatch):
    # A model's live reasoning line every 3 s in production, about five
    # transactions of single reads; the same ratio here.
    monkeypatch.setattr(agent_delegation, "THINKING_UPDATE_SECONDS", 40 * ROUND_TRIP)
    return AgentRunStore(SlowDatabase())


def run_turn(store):
    timeline = Timeline()
    chat, turn = pending(store)
    config = {**defaults(), "enabled": False, "max_searches": 0, "context_chars": 120_000}
    loop = DelegationLoop(store=store, uid=UID, chat_id=chat, turn_id=turn["id"],
        model=resolve_agent_model("claude-haiku-4-5"),
        messages=[{"role": "system", "content": "Answer."},
                  {"role": "user", "content": "What should I pack for a marathon training camp?"}],
        api_key="test", cancellation=ProviderCancellation(), policy=AgentPolicy.from_config({**config, "enabled": True}),
        delegation_config=config, completion_factory=timeline.factory,
        # The most a run asks (High Quality): six families answer in parallel.
        comparison_models=comparison_selection(cfg.CONSENSUS_PRESET_MODELS["thorough"]["answers"]))
    started = time.monotonic()
    events = list(loop.run())
    return loop, timeline, events, time.monotonic() - started


def test_six_models_and_their_review_are_not_held_up_by_a_slow_database(slow_store):
    """Measured 2026-10-21 on Windows (sleeps of 15.6 ms): before the journal
    9.2 s added to 1.6 s of model time, streams held up to 0.9 s, the last
    request out after 2.2 s; after it 2.3 s, 0.02 s and 0.6 s. With the
    journal's batches (2026-10-22, same machine, 1.7 s before) 1.15 s and the
    last request out after 0.25 s."""
    loop, timeline, events, wall = run_turn(slow_store)
    turn = slow_store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert turn["status"] == "completed"
    assert turn["agent_review"]["status"] in {"succeeded", "partial"}
    assert len(turn["agent_review"]["audit"]["reviewers"]) == 6
    assert len(timeline.dispatched) == 6

    # No stream waits for the database: the server reads the next event at
    # once (prod: finished judge answers sat unread until their 90 s limit).
    worst_stall = max(stall for _, stall in timeline.stalls)
    assert worst_stall < 0.1, f"a stream waited {worst_stall:.2f} s for the server"

    # Every request leaves soon after the comparison starts: before it only
    # its own session record and receipt, nothing queued ahead of them
    # (prod: the sixth request left 77 s after the decision).
    latest = max(timeline.dispatched.values()) - timeline.compare_started
    assert latest < 1.2, f"the last comparison request left after {latest:.2f} s"

    # The whole turn: the models' own time on the critical path (answers,
    # the agent's answer, the reviewers' final round) plus the server's share.
    models = MODEL_SECONDS + ANSWER_SECONDS + REVIEW_SECONDS
    overhead = wall - models
    assert overhead < 4.5, f"the server added {overhead:.2f} s to {models:.1f} s of model time"


def test_the_live_reasoning_lines_are_saved_without_queueing_up(slow_store, monkeypatch):
    """The newest line of each model still reaches its saved session, but
    lines are written at most every half THINKING_UPDATE_SECONDS for the
    whole run, all models' lines in one write, never one write per model and
    line."""
    lines = []
    publish = slow_store.publish_agents

    def counted(*args, updates, **kwargs):
        if any("progress_text" in (patch or {}) and "status" not in (patch or {}) for _, patch, _, _ in updates):
            lines.append(time.monotonic())
        return publish(*args, updates=updates, **kwargs)

    monkeypatch.setattr(slow_store, "publish_agents", counted)
    loop, timeline, events, wall = run_turn(slow_store)
    sessions = slow_store.delegation_view(UID, loop.chat_id, loop.turn_id)["agents"]
    answers = [s for s in sessions if s.get("kind") == "comparison"]
    assert len(answers) == 6 and all(s["status"] == "completed" for s in answers)
    assert all(s.get("progress_text", "").startswith("Checking source") for s in answers)
    gap = agent_delegation.THINKING_UPDATE_SECONDS / 2
    assert lines and all(later - earlier >= gap * .9 for earlier, later in zip(lines, lines[1:]))
