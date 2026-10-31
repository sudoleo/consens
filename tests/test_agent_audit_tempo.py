"""Tempo, long runs and load of the reviewers (spec A-L1 to A-L3, 2026-10-29).

In Prod (25.-29.10., docs/agent-audit-readiness-2026-10-29.md section 2) the
marks stood a median 10 s after the answer's last word (p90 35 s, max 74 s)
and the gate waited p90 9.6 s; three reviewers, long workbench runs and
several audit turns at once never ran there. These tests play such turns
without a model call: scripted reviewers with the latencies measured then,
scaled by SCALE, on a database whose every round trip takes ROUND_TRIP, and
measure what the server adds to the models' own time:

- A-L1: 40 workbench steps with three and with six reviewers, one gated
  step, a reviewer still in a live round when the answer is fixed and one
  whose final request hangs (the hedge answers); a turn whose final
  requests all hang ends at FINAL_ROUND_SECONDS. Per request the server's
  share, the marks after the last word, the gate's wait, and no thread of
  the turn alive after it.
- A-L2: a workbench run of 200 steps with the longest command output there
  is that takes every reviewer into a new conversation, a failure pause and
  out of following; the final round still comes with its earlier marks, and
  the review counts all of it. It also measures what the work log holds in
  memory (docs/agent-work-log.md).
- A-L3: three turns with three reviewers each at once in one process.
- Advisers (compare_models, 2026-10-31): the same three
  models answer the agent's question while they review its run.

Measured times are printed (pytest -s), with their Prod equivalent; the
assertions keep a wide margin to them, as CI runners are slower than a
laptop. The server's CPU time does not scale with SCALE, so a server share
read back in Prod seconds (divided by SCALE) overstates it.
"""
from collections import defaultdict
import json
import statistics
import sys
import threading
import time

import pytest

from app.services import agent_audit, agent_delegation, agent_quota
from app.services.agent_comparison import AgentPreferences, ComparisonTools, comparison_selection
from app.services.agent_delegation import DelegationLoop
from app.services.agent_delegation_config import defaults
from app.services.agent_policy import AgentPolicy
from app.services.agent_runs import AgentRunStore
from app.services.agent_tools import ReadOnlyTool, ToolRegistry
from app.services.agent_vm_tools import MODEL_STREAM_CHARS
from app.services.llm.agent_client import AgentCompletion, measured_usage, resolve_agent_model
from app.services.llm.provider_runtime import ProviderCancellation
from test_agent_audit import ANSWER, LookupArgs, earlier_marks, entry_of
from test_agent_gate import MemoryArgs
from test_agent_runs import Database, UID, pending
from test_chat_history import FakeTransaction

# Test seconds per production second: a 4 s live round takes 0.1 s here.
SCALE = 1 / 40


def prod(seconds):
    """A duration of production in test seconds."""
    return seconds * SCALE


# One Firestore round trip (eur3, 2026-10-21: a transaction of six single
# reads took 0.4-0.5 s, a commit about one read more; a review save 0.7 s).
ROUND_TRIP = prod(.1)
# The agent's model step and the command it runs, its answer, and a
# reviewer's reasoning line every TICK while it works.
AGENT_STEP, TOOL, ANSWER_STREAM, TICK = prod(2), prod(1), prod(3), prod(.5)
# Seconds of Prod per request (median, p90), section 2 of the spec. Live:
# MiMo Pro 4/10, Luna 4/8, Qwen 3/6; the others like Qwen. Final round: Luna
# 13/40, Qwen 20/25, MiMo Pro 9/14, GLM 8/15, DeepSeek 2/14; Haiku like GLM.
LIVE = {"openai": (4, 8), "xiaomi": (4, 10), "qwen": (3, 6), "glm": (3, 6), "deepseek": (3, 6), "anthropic": (3, 6)}
FINAL = {"openai": (13, 40), "xiaomi": (9, 14), "qwen": (20, 25), "glm": (8, 15), "deepseek": (2, 14),
         "anthropic": (8, 15)}
# Seconds of Prod a comparison answer took (median, 18.-21.10.,
# docs/agent-mode.md "Tempo"): Luna 29, Haiku 28, DeepSeek V4.1 Flash 18.
ADVICE = {"openai": 29, "anthropic": 28, "deepseek": 18}
THREE = {"openai": "gpt-5.6-luna", "xiaomi": "mimo-v2.6-pro", "qwen": "qwen3.8-27b"}
# The Daily preset, three reviewers (the default since 2026-10-28).
DAILY = {"openai": "gpt-5.6-luna", "anthropic": "claude-haiku-4-5", "deepseek": "deepseek-v4.1-flash"}
SIX = {**THREE, "glm": "glm-5.3-flash", "deepseek": "deepseek-v4.1-flash", "anthropic": "claude-haiku-4-5"}
STEPS = 40
# The step that changes memory with the agent's search hits in view: it
# waits for the reviewers' gate (agent_gate.outward "memory").
GATE_STEP = 20
# Every thread a turn starts by name: run, watcher, journal, work log,
# reviewers and their final requests (agent-review-<provider>[-<kind>]).
TURN_THREADS = "agent-"


@pytest.fixture(autouse=True)
def _admin_allowance(monkeypatch):
    """Audit mode is for admins (5M tokens a day, test_agent_audit)."""
    from app.services import agent_budget_config
    monkeypatch.setitem(agent_budget_config.DEFAULT_TIER_LIMITS, "pro", 5_000_000)


@pytest.fixture(autouse=True)
def _one_lock_per_account(monkeypatch):
    """agent_quota.account_lock as one lock per account: its 128 stripes
    hash the uid, and str hashes change with every process, so two accounts
    would now and then share one."""
    locks, guard = defaultdict(threading.RLock), threading.Lock()

    def account_lock(uid):
        with guard:
            return locks[uid]
    monkeypatch.setattr(agent_quota, "account_lock", account_lock)


@pytest.fixture
def scaled(monkeypatch):
    """The audit's own times on the same scale; no hedge history from other tests."""
    for name in ("FINAL_HEDGE_SECONDS", "FINAL_HEDGE_MIN_SECONDS", "FINAL_ROUND_SECONDS", "GATE_SECONDS",
                 "FAILURE_PAUSE_SECONDS"):
        monkeypatch.setattr(agent_audit, name, prod(getattr(agent_audit, name)))
    monkeypatch.setattr(agent_audit, "_final_seconds", {})
    monkeypatch.setattr(agent_delegation, "THINKING_UPDATE_SECONDS", prod(agent_delegation.THINKING_UPDATE_SECONDS))


# --- The database -------------------------------------------------------------

class RoundTripTransaction(FakeTransaction):
    """Each read, batched read and commit takes ``round_trip``. The commit
    applies without the fake's full copy of the database for its rollback
    (over a long run that copy took longer than the round trips): it checks
    first that every update finds its document."""

    def get(self, ref):
        time.sleep(self.database.round_trip)
        with self.database.lock:
            return super().get(ref)

    def get_all(self, refs):
        time.sleep(self.database.round_trip)
        with self.database.lock:
            return [FakeTransaction.get(self, ref) for ref in refs]

    def commit(self):
        time.sleep(self.database.round_trip)
        database = self.database
        with database.lock:
            written = set()
            for operation, ref, _ in self.operations:
                if operation == "update" and ref.path not in database.documents and ref.path not in written:
                    raise RuntimeError("missing document")
                written.add(ref.path)
            for operation, ref, data in self.operations:
                if operation == "delete":
                    ref.delete()
                elif operation in {"set", "set_merge"}:
                    database.apply_set(ref, data, merge=operation == "set_merge")
                else:
                    database.apply_update(ref, data)
            database.transaction_commits.append([ref.path for _, ref, _ in self.operations])


class RoundTripDatabase(Database):
    """Transactions as Firestore runs them: each round trip takes
    ``round_trip`` and transactions overlap; only the app's own account lock
    (around claims, settlements and session updates, AgentSessionStore.
    _agent_transaction) puts those of one account in a row."""

    def __init__(self, round_trip=ROUND_TRIP):
        super().__init__()
        self.round_trip = round_trip

    def run_transaction(self, operation):
        transaction = RoundTripTransaction(self)
        result = operation(transaction)
        transaction.commit()
        return result


@pytest.fixture
def counted_tokens(monkeypatch):
    """Token estimates from the characters (three a token) instead of the
    tokenizer over the whole conversation: its CPU time does not scale, and
    on this scale it took most of the server's (measured in A-L2: 20 s of
    CPU in 1,528 estimates, the run 17 s instead of 4 s) and kept the GIL
    busy for every other thread of the process."""
    from app.services import agent_tokens

    def estimate(messages, tools=(), request_config=None):
        payload = [messages, tools, (request_config or {}).get("response_format")]
        chars = len(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str))
        return (chars // 3 * 5 + 3) // 4 + 256 + 16 * len(messages)
    monkeypatch.setattr(agent_tokens, "input_estimate", estimate)


@pytest.fixture
def slow_store():
    return AgentRunStore(RoundTripDatabase())


# --- The scripted turn ---------------------------------------------------------

def reasoning(step_id, i):
    return {"type": "activity", "version": 1, "step_id": step_id, "id": "r", "kind": "reasoning",
            "format": "text", "text": f"Checking entry {i} against the user's request. ", "append": True}


class Turn:
    """A scripted turn: the agent's first ``steps`` steps run a
    workbench command each (``vm_exec``, ``output`` characters on stdout and
    on stderr), the step ``gate_step`` changes memory instead, then it writes
    ANSWER. A reviewer answers a live round after its median (every fifth
    after its p90), a gate round after its live median, its final round
    after its median. ``long_live``: a reviewer whose live rounds from the
    agent's third-last step on run until they are stopped (MiMo Pro took up
    to 53 s); ``hang``: reviewers whose first final request hangs until it is
    stopped (the hedge answers); ``stuck``: whose every final request hangs.
    ``live``: replies of live rounds by family, ``reply(messages, number)``
    (a dict, or an exception to raise). ``timed=False``: no model takes time.
    ``compare_step``: the step that asks the models instead (compare_models);
    each answers after its ADVICE median."""

    def __init__(self, reviewers, *, uid=UID, steps=STEPS, gate_step=None, long_live=None, hang=(), stuck=(),
                 output=200, live=None, timed=True, compare_step=None):
        self.reviewers, self.uid, self.steps, self.gate_step = dict(reviewers), uid, steps, gate_step
        self.compare_step, self.advised = compare_step, []
        self.long_live, self.hang, self.stuck = long_live, set(hang), set(stuck)
        self.output, self.live, self.timed = output, dict(live or {}), timed
        self.lock = threading.Lock()
        self.steps_done = 0
        self.calls = defaultdict(lambda: defaultdict(int))
        # When each family's final requests began (time.monotonic), and the
        # last message of each of its requests.
        self.final_started, self.messages = defaultdict(list), defaultdict(list)
        # (round kind, seconds the server added, seconds of the model) per reviewer request.
        self.requests = []
        self.model_seconds = threading.local()
        # (index, start, end) of each of the agent's model steps.
        self.agent_spans = []
        self.started = self.fixed = self.marked = self.ended = None
        self.loop = None

    def sleep(self, seconds):
        """The model at work: counted as its own time, not the server's."""
        if seconds <= 0:
            return
        started = time.monotonic()
        time.sleep(seconds)
        local = self.model_seconds
        local.seconds = getattr(local, "seconds", 0.0) + time.monotonic() - started

    def factory(self):
        script = self

        class Completion(AgentCompletion):
            def stream(self, *, model, messages, **kwargs):
                self.usage = measured_usage({"prompt_tokens": 50, "completion_tokens": 20, "cost": .0001}, model)
                if self.step_id.startswith("completion:"):
                    # A closing step without tools (a turn limit) writes the answer.
                    index = int(self.step_id.split(":")[1])
                    yield from script.agent(self, index if kwargs.get("allow_tool_calls", True) else script.steps)
                elif messages[0]["content"].startswith("You are an independent answer model"):
                    yield from script.adviser(self, script.family(model))
                else:
                    yield from script.reviewer(self, script.family(model), messages)
        return Completion()

    def adviser(self, value, family):
        """A comparison model answering the agent's question, its reasoning
        lines while it works."""
        with self.lock:
            self.advised.append(family)
        deadline, tick = time.monotonic() + prod(ADVICE[family]), 0
        while time.monotonic() < deadline or not tick:
            self.sleep(min(TICK, max(0., deadline - time.monotonic())))
            tick += 1
            yield reasoning(value.step_id, tick)
        value.text, value.finish_reason = f"{family} says the tower is 330 metres tall.", "stop"
        yield {"type": "delta", "text": value.text}

    def family(self, model):
        return next(provider for provider, selected in self.loop.comparison.models.items()
                    if selected.model == model.model)

    def agent(self, value, index):
        started = time.monotonic()
        try:
            yield from self._agent(value, index)
        finally:
            with self.lock:
                self.agent_spans.append((index, started, time.monotonic()))

    def _agent(self, value, index):
        if index < self.steps:
            if self.timed:
                self.sleep(AGENT_STEP)
            if index == 0:
                # The agent's own search found a page: outside content is in view.
                value.sources = [{"url": "https://www.toureiffel.paris/en", "title": "Official site"}]
                value._results_at = 0
            if index == self.gate_step:
                name, args = "update_memory", {"changes": [{"op": "add", "text": "Builds a site in the workspace."}]}
            elif index == self.compare_step:
                name, args = "compare_models", {"question": "How tall is the Eiffel Tower?"}
            else:
                name, args = "vm_exec", {"command": f"make step-{index}"}
            value.tool_calls = [{"id": f"call_{index}", "type": "function",
                                 "function": {"name": name, "arguments": json.dumps(args)}}]
            value.finish_reason = "tool_calls"
            with self.lock:
                self.steps_done = index + 1
            return
        chunks = [ANSWER[start:start + 60] for start in range(0, len(ANSWER), 60)]
        for chunk in chunks:
            if self.timed:
                self.sleep(ANSWER_STREAM / len(chunks))
            value.text += chunk
            yield {"type": "delta", "text": chunk}
        value.finish_reason = "stop"

    def reviewer(self, value, family, messages):
        last = messages[-1]["content"]
        kind = "final" if last.startswith("Final round.") else "gate" if "Before it runs:" in last else "live"
        with self.lock:
            self.calls[family][kind] += 1
            number = self.calls[family][kind]
            if kind == "final":
                self.final_started[family].append(time.monotonic())
            self.messages[family].append(last)
            steps_done = self.steps_done
        median, p90 = (FINAL if kind == "final" else LIVE)[family]
        seconds = prod(p90 if kind == "live" and number % 5 == 0 else median) if self.timed else 0
        if kind == "live" and family == self.long_live and steps_done >= self.steps - 3:
            seconds = None
        if kind == "final" and (family in self.stuck or (family in self.hang and number == 1)):
            seconds = None
        # Its reasoning lines while it works; a stopped request ends at the
        # next one (DelegationLoop._step checks between events).
        deadline, tick = time.monotonic() + (30 if seconds is None else seconds), 0
        while True:
            left = deadline - time.monotonic()
            if left <= 0 and tick:
                break
            self.sleep(min(TICK, left))
            tick += 1
            yield reasoning(value.step_id, tick)
        if kind == "final":
            reply = {"marks": [{"quote": "Tickets to the top cost 14 euros", "kind": "doubtful",
                                "note": f"{family} doubts the price."}]}
        elif kind == "gate":
            reply = {"marks": [], "gate": "go"}
        elif family in self.live:
            reply = self.live[family](messages, number)
            if isinstance(reply, BaseException):
                raise reply
        else:
            # Now and then a mark on the newest step it read.
            reply = {"marks": [{"entry": entry_of(messages, "step"), "kind": "doubtful", "note": "Unchecked."}]
                     if number % 7 == 0 else []}
        value.text, value.finish_reason = json.dumps(reply), "stop"
        yield {"type": "delta", "text": value.text}


class CommandArgs(LookupArgs):
    command: str = ""


def tools(script):
    """The turn's workbench command and memory change, both scripted."""
    def command(args, *, cancellation):
        if script.timed:
            time.sleep(TOOL)
        return {"exit_code": 0, "stdout": ("ok " * script.output)[:script.output],
                "stderr": ("warn " * script.output)[:script.output], "seconds": 1.0}

    def remember(args, *, cancellation):
        return {"status": "saved"}
    return [ReadOnlyTool("vm_exec", "Run a command in the workspace.", CommandArgs, command),
            ReadOnlyTool("update_memory", "Remember.", MemoryArgs, remember)]


def tempo_loop(store, script, *, model="claude-haiku-4-5"):
    """The turn as a workbench run (DelegationLoop._long_run: up to 200
    steps and two hours, old command output compacted)."""
    chat, turn = pending(store, uid=script.uid)
    config = {**defaults(), "enabled": False, "max_searches": 0}
    loop = DelegationLoop(store=store, uid=script.uid, chat_id=chat, turn_id=turn["id"],
        model=resolve_agent_model(model),
        messages=[{"role": "system", "content": "Answer."},
                  {"role": "user", "content": "Build me a small site in the workspace."}],
        api_key="test", cancellation=ProviderCancellation(), policy=AgentPolicy.for_chat(config),
        delegation_config=config, completion_factory=script.factory,
        comparison_models=comparison_selection(script.reviewers), agent_preferences=AgentPreferences())
    loop.registry = ToolRegistry([*loop.registry.tools.values(), *tools(script)],
                                 argument_limit=loop.registry.argument_limit)
    loop._long_run = lambda: True
    script.loop, loop.script = loop, script
    capture = loop.comparison.capture

    def fix(text):
        script.fixed = time.monotonic()
        capture(text)
    loop.comparison.capture = fix
    return loop


@pytest.fixture
def measured(monkeypatch):
    """Every reviewer request's time without its model's (worker_request);
    a request that was stopped (cut, overtaken) is not counted."""
    original = ComparisonTools.worker_request

    def timed(tools, worker, model, messages, **kwargs):
        script = getattr(tools.loop, "script", None)
        if script is None:
            return original(tools, worker, model, messages, **kwargs)
        script.model_seconds.seconds = 0.0
        started = time.monotonic()
        value = original(tools, worker, model, messages, **kwargs)
        wall, model_time = time.monotonic() - started, script.model_seconds.seconds
        with script.lock:
            script.requests.append((kwargs.get("review_round"), wall - model_time, model_time))
        return value
    monkeypatch.setattr(ComparisonTools, "worker_request", timed)


def watch_marks(store, scripts):
    """When each turn's review was first saved with its marks (a final status)."""
    save, by_turn = store.save_review, {script.loop.turn_id: script for script in scripts}

    def saving(uid, chat_id, turn_id, token, review, text):
        result = save(uid, chat_id, turn_id, token, review, text)
        script = by_turn.get(turn_id)
        if script is not None and script.marked is None and review.get("status") in {"succeeded", "partial", "failed"}:
            script.marked = time.monotonic()
        return result
    store.save_review = saving


def play(store, script):
    """Runs the turn; returns it as saved. A pause fails it instead of
    waiting (none of these turns has a reason for one), and so does a turn
    still running after 60 s."""
    loop, held, done = script.loop, [], threading.Event()

    def guard():
        deadline = time.monotonic() + 60
        while not done.wait(.01):
            if loop.hold is not None or time.monotonic() > deadline:
                held.append(dict(loop.hold or {"timeout": True}))
                loop.cancellation.cancel()
                return
    watcher = threading.Thread(target=guard, name="test-guard", daemon=True)
    watcher.start()
    try:
        script.started = time.monotonic()
        list(loop.run())
        script.ended = time.monotonic()
    finally:
        done.set()
        watcher.join()
        # Also in place of the stop the guard caused.
        assert not held, f"the turn paused or ran out of time: {held}"
    return store.get_turn(script.uid, loop.chat_id, loop.turn_id)


def alive_after(before):
    """Threads started since ``before`` that are still alive: the turn's own
    (TURN_THREADS) at once, any other (a cancelled timer, a tool's thread)
    after a moment to end."""
    new = [thread for thread in threading.enumerate() if thread not in before and thread.name != "test-guard"]
    named = [thread for thread in new if thread.name.startswith(TURN_THREADS) and thread.is_alive()]
    for thread in new:
        if thread not in named:
            thread.join(1)
    return [thread.name for thread in new if thread.is_alive()]


def summary(script):
    """The turn's measurements in test seconds (pytest -s prints them)."""
    rounds = [server for kind, server, _ in script.requests if kind in {"live", "gate", "repair"}]
    finals = [server for kind, server, _ in script.requests if kind in {"final", "hedge"}]
    spans = sorted(script.agent_spans)
    # From one of the agent's steps to its next request, without the command in between.
    steps = [later[1] - earlier[2] - (TOOL if script.timed and earlier[0] < script.steps else 0)
             for earlier, later in zip(spans, spans[1:])]
    checked = [json.loads(text) for entry, text in script.loop.work_log.entries_after(0)
               if entry.get("name") == "checked"]
    return {"marks after the last word": script.marked - script.fixed,
            "first final requests after fixing": max(started[0] for started in script.final_started.values())
            - script.fixed,
            "server per live round": {"median": statistics.median(rounds), "max": max(rounds),
                                      "rounds": len(rounds)},
            "server per final request": {"median": statistics.median(finals), "max": max(finals)},
            "server per agent step": {"median": statistics.median(steps), "max": max(steps), "sum": sum(steps)},
            "gate wait": checked[0]["gate_ms"] / 1000 if checked else None,
            "turn": script.ended - script.started}


def report(name, values):
    """Prints measurements (pytest -s), a time with its Prod equivalent."""
    def show(value):
        if isinstance(value, dict):
            return "{" + ", ".join(f"{key}: {show(item)}" for key, item in value.items()) + "}"
        if isinstance(value, list):
            return "[" + ", ".join(map(show, value)) + "]"
        if isinstance(value, float):
            return f"{value:.3f} s (Prod {value / SCALE:.1f} s)"
        return str(value)
    print(f"\n[{name}] " + ", ".join(f"{key}: {show(value)}" for key, value in values.items()), file=sys.stderr)


# --- A-L1: tempo with three and six reviewers ------------------------------------

@pytest.mark.parametrize("reviewers", [THREE, SIX], ids=["three", "six"])
def test_forty_workbench_steps_keep_their_tempo_with_three_and_six_reviewers(slow_store, scaled, measured,
                                                                              reviewers):
    """Measured 2026-10-29 on Windows (4 cores), three / six reviewers:
    marks after the last word 0.95-1.02 / 1.02-1.11 s (0.83 s of it the
    hedge's path), the last first final request 0.13 / 0.20-0.25 s after
    fixing, server per live round median 32-47 / 63-79 ms (max 0.24 s), per
    agent step 38-53 / 69-100 ms (37 ms without reviewers), gate 0.19-0.27 s,
    turn 6.2-7.0 / 7.3-9.0 s for 3.1 s of the models' and commands' own
    time, the account lock held about 60 / 85 % of it."""
    script = Turn(reviewers, gate_step=GATE_STEP, long_live="xiaomi", hang={"openai"})
    loop = tempo_loop(slow_store, script)
    watch_marks(slow_store, [script])
    before = set(threading.enumerate())
    turn = play(slow_store, script)
    alive = alive_after(before)
    values = summary(script)
    report(f"A-L1 {len(reviewers)} reviewers", {**values, "account lock": slow_store.lock_time()})
    review = turn["agent_review"]
    rows = {row["provider"]: row for row in review["audit"]["reviewers"]}
    assert turn["status"] == "completed" and turn["consensus"] == ANSWER
    assert review["status"] == "succeeded" and {row["status"] for row in rows.values()} == {"completed"}
    assert all(script.calls[family]["live"] >= STEPS / 4 for family in reviewers)

    # The server's share of each reviewer request: its session, claim and
    # settlement behind the account lock, never a queue that grows with the
    # run (measured median 47 / 63 ms, max 0.2 s).
    assert values["server per live round"]["median"] < .25 and values["server per live round"]["max"] < 1
    assert values["server per final request"]["max"] < .5
    assert values["server per agent step"]["median"] < .3

    # The final round starts at once (A-T1): MiMo Pro was still in a live
    # round, which would have run on until the turn's end.
    assert rows["xiaomi"]["backlog"]["seconds"] is not None and script.calls["xiaomi"]["final"] == 1
    assert values["first final requests after fixing"] < 1
    # The hung request got its hedge after the hedge time, and the hedge's
    # reply counted (A-T2); without it the marks would wait for
    # FINAL_ROUND_SECONDS and miss Luna's.
    assert rows["openai"]["hedged"] is True and script.calls["openai"]["final"] == 2
    hedge = script.final_started["openai"][1] - script.fixed
    assert agent_audit.FINAL_HEDGE_SECONDS <= hedge < agent_audit.FINAL_HEDGE_SECONDS + 1
    critical = agent_audit.FINAL_HEDGE_SECONDS + prod(FINAL["openai"][0])
    assert critical <= values["marks after the last word"] < critical + 1 < agent_audit.FINAL_ROUND_SECONDS
    assert len({claim["anchor"] for claim in review["audit"]["claims"]}) == 1
    assert len(review["audit"]["claims"][0]["dissent"]) == len(reviewers)

    # The gate: every reviewer said go within GATE_SECONDS (a late one
    # would have asked the user, and play() fails on any pause).
    [checked] = [json.loads(text) for entry, text in loop.work_log.entries_after(0) if entry.get("name") == "checked"]
    assert [verdict["verdict"] for verdict in checked["verdicts"]] == ["go"] * len(reviewers)
    assert values["gate wait"] < agent_audit.GATE_SECONDS

    # Nothing of the turn runs on: reviewers, their final requests (the
    # overtaken one too), journal, work log, watcher.
    assert alive == []


def test_final_requests_that_all_hang_end_at_the_final_rounds_time(slow_store, scaled, measured):
    """Z1 max: Luna's first request and its hedge both hang; the marks come
    at FINAL_ROUND_SECONDS with the others' marks, and the turn completes."""
    script = Turn(THREE, steps=3, stuck={"openai"})
    tempo_loop(slow_store, script)
    watch_marks(slow_store, [script])
    before = set(threading.enumerate())
    turn = play(slow_store, script)
    alive = alive_after(before)
    marks = script.marked - script.fixed
    report("A-L1 hard limit", {"marks after the last word": marks})
    review = turn["agent_review"]
    assert turn["status"] == "completed" and turn["consensus"] == ANSWER
    assert review["status"] == "partial" and {"code": "no_time"} in review["audit"]["issues"]
    rows = review["audit"]["reviewers"]
    assert [(row["provider"], row["status"], (row.get("failure") or {}).get("code")) for row in rows] == [
        ("openai", "failed", "no_time"), ("xiaomi", "completed", None), ("qwen", "completed", None)]
    # Its hedge came and hung as well.
    assert rows[0]["hedged"] is True and script.calls["openai"]["final"] == 2
    assert agent_audit.FINAL_ROUND_SECONDS <= marks < agent_audit.FINAL_ROUND_SECONDS + 1
    assert alive == []


# --- Advisers beside the reviewers (compare_models, 2026-10-31) ------------------

def test_three_advisers_beside_three_reviewers_keep_their_tempo(slow_store, scaled, measured):
    """Package 1 of one mode for comparison and audit: the Daily preset's
    three models answer the agent's question while the same three review the
    run, six sessions of one account at once behind its lock (spec A-T5: 60 %
    of the turn with three reviewers, 85 % with six). The advisers' requests
    and the reviewers' rounds keep the server's share they have without
    them. Measured 2026-10-31 (Windows, 4 cores, three runs): server per
    adviser request median 0.03 s (max 0.06 s), per live round median
    0.03-0.05 s, marks 0.41-0.45 s after the last word (Luna's final
    round), the account lock held 44-49 % of the 2.5 s turn and waited for
    0.7 s in all, the longest wait 0.03 s."""
    script = Turn(DAILY, steps=8, compare_step=2)
    tempo_loop(slow_store, script)
    watch_marks(slow_store, [script])
    before = set(threading.enumerate())
    turn = play(slow_store, script)
    alive = alive_after(before)
    values = summary(script)
    advice = [server for kind, server, _ in script.requests if kind is None]
    report("Advisers beside three reviewers", {**values, "server per adviser request": {
        "median": statistics.median(advice), "max": max(advice)}, "account lock": slow_store.lock_time()})
    review = turn["agent_review"]
    assert turn["status"] == "completed" and turn["consensus"] == ANSWER
    assert review["mode"] == "audit" and review["status"] == "succeeded"
    assert {row["status"] for row in review["audit"]["reviewers"]} == {"completed"}
    [comparison] = review["comparisons"]
    assert comparison["status"] == "succeeded" and sorted(script.advised) == sorted(DAILY)
    # The work went on after the answers: every step ran.
    assert len(script.agent_spans) == script.steps + 1
    # Each reviewer read the advisers' answers in a live round.
    for family in DAILY:
        assert any('"name": "compare_models"' in message and "says the tower is 330 metres" in message
                   for message in script.messages[family])
    assert len(advice) == len(DAILY) and max(advice) < .5
    assert values["server per live round"]["median"] < .25 and values["server per live round"]["max"] < 1
    assert values["server per agent step"]["median"] < .3
    assert values["marks after the last word"] < prod(FINAL["openai"][1]) + 1
    # No judge checks anything: the reviewers' marks are the review.
    assert review.get("checks", []) == [] and "differences_data" not in json.dumps(review)
    assert alive == []


# --- A-L2: a long workbench run ----------------------------------------------------

LONG_STEPS = 199
# A reviewer's conversation (session_budget): small, so that live rounds
# fill it often, and its final round still fits with the run's beginning,
# its marks and the rest of the log, read short.
LONG_BUDGET = 60_000
# The live requests of each reviewer that fail: two in a row, a pause.
FAILING = (20, 21)


def test_a_long_workbench_run_takes_each_reviewer_through_new_conversations_a_pause_and_out_of_following(
        monkeypatch, counted_tokens):
    """199 workbench commands with the longest output a command returns to
    the model (stdout and stderr, MODEL_STREAM_CHARS each), then the answer;
    no model takes time. Each reviewer goes on in new conversations (one
    forced in its third round, the others as its small conversation fills),
    pauses after two failed rounds in a row, and stops following when a
    round fits not even a new conversation (forced near the end). Its final
    round still comes, with its marks so far, and the review counts it all."""
    store = AgentRunStore(RoundTripDatabase(round_trip=0))
    monkeypatch.setattr(agent_audit, "session_budget", lambda model: LONG_BUDGET)
    monkeypatch.setattr(agent_audit, "FAILURE_PAUSE_SECONDS", .05)
    monkeypatch.setattr(agent_audit, "_final_seconds", {})
    fresh, unfollowed, forced = defaultdict(int), {}, set()
    original_round, original_fresh = agent_audit.ReviewerSession._round, agent_audit.ReviewerSession._fresh

    def counted_fresh(self):
        fresh[self.provider] += 1
        return original_fresh(self)

    def forced_round(self, entries):
        if self.provider not in forced and self.live_rounds == 2 and len(self.messages) > 1:
            # Its conversation is full after two rounds: a new one.
            forced.add(self.provider)
            self.chars = self.budget
        if self.following and self.provider not in unfollowed and script.steps_done >= LONG_STEPS - 9:
            # This round fits not even a new conversation: it stops following.
            budget, self.budget = self.budget, 1
            try:
                original_round(self, entries)
            finally:
                self.budget = budget
            assert not self.following
            unfollowed[self.provider] = entries[-1][0]["seq"]
            return
        return original_round(self, entries)
    monkeypatch.setattr(agent_audit.ReviewerSession, "_fresh", counted_fresh)
    monkeypatch.setattr(agent_audit.ReviewerSession, "_round", forced_round)

    def live(messages, number):
        if number in FAILING:
            return RuntimeError("provider down")
        return {"marks": [{"entry": entry_of(messages, "step"), "kind": "doubtful", "note": f"Round {number}."}]
                if number % 10 == 0 else []}
    script = Turn(THREE, steps=LONG_STEPS, output=MODEL_STREAM_CHARS, live={family: live for family in THREE},
                  timed=False)
    # The agent on a 1M window, as the workbench's models in Prod: on Haiku's
    # 200k this run ends near step 190 despite the compaction (TURN_CONTEXT_LIMIT).
    loop = tempo_loop(store, script, model="deepseek-v4.1-flash")
    agent = script._agent

    def waits_for_the_reviewers(value, index):
        if index == LONG_STEPS - 4:
            # Every reviewer took its round past LONG_STEPS - 9 first.
            deadline = time.monotonic() + 20
            while len(unfollowed) < len(THREE) and time.monotonic() < deadline:
                time.sleep(.01)
        return agent(value, index)
    script._agent = waits_for_the_reviewers
    before = set(threading.enumerate())
    started = time.monotonic()
    turn = play(store, script)
    wall = time.monotonic() - started
    alive = alive_after(before)

    entries = loop.work_log._entries
    chars = sum(len(text) for _, text in entries)
    memory = sum(sys.getsizeof(text) + sys.getsizeof(entry) + sum(map(sys.getsizeof, entry.values()))
                 for entry, text in entries)
    report("A-L2 work log", {"entries": len(entries), "characters": chars, "bytes": memory,
                             "largest entry": max(len(text) for _, text in entries), "turn": wall,
                             "fresh": dict(fresh), "unfollowed at": unfollowed})
    review = turn["agent_review"]
    assert turn["status"] == "completed" and turn["consensus"] == ANSWER and review["status"] == "succeeded"
    assert len(unfollowed) == len(THREE) and len(script.agent_spans) == LONG_STEPS + 1
    for row in review["audit"]["reviewers"]:
        family, session = row["provider"], loop.comparison.auditor.sessions[row["provider"]]
        # The counters are what happened: every new conversation, one pause,
        # where it stopped following.
        assert row["fresh"] == fresh[family] == session.fresh >= 3
        assert row["pauses"] == session.pauses == 1
        assert row["unfollowed_at_seq"] == unfollowed[family]
        assert row["status"] == "completed" and row["rounds"] == session.live_rounds
        assert script.calls[family]["live"] == session.live_rounds + len(FAILING)
        # The final round came, in a new conversation with its marks so far.
        final = script.messages[family][-1]
        assert final.startswith("Final round.") and earlier_marks({"content": final}) == session.live_marks
        assert len(session.live_marks) >= 10
    # The work log holds every entry whole: the commands' output, each step.
    assert chars > LONG_STEPS * 2 * MODEL_STREAM_CHARS
    assert alive == []


# --- A-L3: three audit turns at once -----------------------------------------------

# Each turn's workbench steps: the turns still work side by side when their answers are fixed.
PARALLEL_STEPS = 20

def test_three_audit_turns_at_once_keep_the_marks_of_one(scaled, measured, counted_tokens):
    """Three turns at once with the Daily preset's three reviewers each,
    two of them in one account (OWNER_CONCURRENT_RUNS allows two), the third
    in another, against the same turn alone (after them, in a warm process).
    Measured 2026-10-29 (Windows, 4 cores, three runs): alone 0.41-0.44 s
    after the last word; the turn in its own account 0.42-0.47 s (within the
    spec's 20 %), the two in one account 0.47-0.63 s (+14 to +54 %): their
    reviewers' claims, settlements and session updates queue behind one
    account lock (server per live round 32 -> 110-140 ms, the first final
    request 0.07 -> 0.13-0.28 s after fixing). Token counts come from the
    characters here: on this scale the tokenizer's CPU, which does not
    scale, kept the GIL busy for all three turns (A-L2 measured it)."""
    shared = AgentRunStore(RoundTripDatabase())
    turns = [Turn(DAILY, steps=PARALLEL_STEPS), Turn(DAILY, steps=PARALLEL_STEPS),
             Turn(DAILY, steps=PARALLEL_STEPS, uid="agent-user-2")]
    for turn in turns:
        tempo_loop(shared, turn)
    watch_marks(shared, turns)
    before = set(threading.enumerate())
    saved, errors = {}, []

    def run(turn):
        try:
            saved[turn.loop.turn_id] = play(shared, turn)
        except BaseException as exc:
            errors.append(exc)
    threads = [threading.Thread(target=run, args=(turn,), name=f"test-turn-{index}") for index, turn in
               enumerate(turns)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(90)
    # No deadlock, nothing left behind.
    assert not errors and not any(thread.is_alive() for thread in threads)
    assert alive_after(before | set(threads)) == []
    alone = []
    for _ in range(2):
        turn = Turn(DAILY, steps=PARALLEL_STEPS)
        store = AgentRunStore(RoundTripDatabase())
        tempo_loop(store, turn)
        watch_marks(store, [turn])
        play(store, turn)
        alone.append(turn.marked - turn.fixed)
    single = min(alone)
    marks = [turn.marked - turn.fixed for turn in turns]
    for turn in turns:
        report(f"A-L3 {turn.uid}", summary(turn))
    report("A-L3", {"alone": single, "at once": marks})
    for turn in turns:
        review = saved[turn.loop.turn_id]["agent_review"]
        assert saved[turn.loop.turn_id]["status"] == "completed" and review["status"] == "succeeded"
        assert {row["status"] for row in review["audit"]["reviewers"]} == {"completed"}
    # The turn in its own account: within 20 % of the turn alone (and the
    # clock's steps). The two in one account share its lock: bounded, not
    # within 20 % (above); a lock or queue shared by all turns would
    # multiply their marks.
    assert marks[2] < single * 1.2 + .05
    assert max(marks[:2]) < single * 2
