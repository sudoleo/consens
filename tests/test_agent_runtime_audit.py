"""The workspace at run time, audit 2026-10-30
(docs/agent-workspace-runtime-audit-2026-10-30.md): what the operator can
measure afterwards (I1, I4, I7, I9), what the agent reads about its own run
(L1, L3, L6, L7), several calls per step while the workspace is open (T2),
the browser's reads without a live round of their own (K6) and the settlement
in fewer round trips (T3). Fakes only: no model, no VM, no Firestore.
"""
from dataclasses import replace
from datetime import datetime, timezone
import json

import pytest

from app.services import agent_delegation
from app.services.llm import agent_client
from app.services.llm.agent_client import AgentCompletion, AgentModel, measured_usage
from test_agent_runs import UID, pending, receipt, store  # noqa: F401  (fixture)
from test_agent_vm import ANSWER, Agent, fake_vm, results, vm_loop  # noqa: F401  (fixture)


class Steps(Agent):
    """Agent, whose wrap-up step (tools listed, not callable) answers; it
    records what each step's request asked for."""

    def __init__(self, steps=()):
        super().__init__(steps)
        self.parallel, self.requests = [], []

    def factory(self):
        base, script = type(super().factory()), self

        class Completion(base):
            def stream(self, *, model, messages, **kwargs):
                script.parallel.append(getattr(self, "parallel_tool_calls", None))
                script.requests.append(json.loads(json.dumps(messages, default=str)))
                if kwargs.get("allow_tool_calls") is False:
                    self.usage = measured_usage({"prompt_tokens": 50, "completion_tokens": 20, "cost": .0001}, model)
                    self.text, self.finish_reason = ANSWER, "stop"
                    yield {"type": "delta", "text": self.text}
                    return
                yield from super().stream(model=model, messages=messages, **kwargs)
        return Completion()


def log_entries(loop, kind=None, name=None):
    return [(entry, text) for entry, text in loop.work_log.entries_after(0)
            if (kind is None or entry["kind"] == kind) and (name is None or entry["name"] == name)]


# --- I7: when a request left, its first token came and its stream ended ------------

def test_a_streamed_step_keeps_its_request_times_and_the_receipt_saves_them(store, monkeypatch):
    def lines(url, **kwargs):
        for event in [{"id": "gen-1", "choices": [{"delta": {"content": "Hello"}}]},
                      {"choices": [{"delta": {}, "finish_reason": "stop"}]},
                      {"choices": [], "usage": {"prompt_tokens": 12, "completion_tokens": 3}}]:
            yield "data: " + json.dumps(event)
            yield ""
        yield "data: [DONE]"
        yield ""
    monkeypatch.setattr(agent_client, "cancellable_sse_lines", lines)
    completion = AgentCompletion()
    list(completion.stream(model=AgentModel(), messages=[{"role": "user", "content": "Hi"}], api_key="test"))
    started, first, ended = completion.request_started_at, completion.first_token_at, completion.stream_ended_at
    assert all(isinstance(value, datetime) and value.tzinfo is timezone.utc for value in (started, first, ended))
    assert started <= first <= ended
    # The receipt keeps them beside created_at and settled_at (AgentRunStore.settle).
    chat_id, turn = pending(store)
    store.claim(UID, chat_id, turn["id"], AgentModel())
    value = receipt()
    value.request_started_at, value.first_token_at, value.stream_ended_at = started, first, ended
    store.settle(UID, chat_id, turn["id"], completion=value, status="succeeded")
    saved = store.receipt_ref(UID, chat_id, turn["id"]).get().to_dict()
    assert (saved["request_started_at"], saved["first_token_at"], saved["stream_ended_at"]) == (started, first, ended)


def test_a_step_without_a_stream_saves_no_request_times(store):
    chat_id, turn = pending(store)
    store.claim(UID, chat_id, turn["id"], AgentModel())
    store.settle(UID, chat_id, turn["id"], completion=receipt(), status="succeeded")
    saved = store.receipt_ref(UID, chat_id, turn["id"]).get().to_dict()
    assert not {"request_started_at", "first_token_at", "stream_ended_at"} & set(saved)


# --- I4: a tool entry says when its call started and how long it ran ----------------

def test_tool_entries_of_the_work_log_carry_start_and_duration(store, fake_vm):
    script = Agent([[("vm_exec", {"command": "python3 stats.py"})], [("vm_read_file", {"path": "stats.py"})]])
    loop = vm_loop(store, script)
    list(loop.run())
    tools = [entry for entry, _ in log_entries(loop, kind="tool")]
    assert [entry["name"] for entry in tools] == ["vm_exec", "vm_read_file"]
    for entry in tools:
        assert type(entry["duration_ms"]) is int and entry["duration_ms"] >= 0
        assert datetime.fromisoformat(entry["started_at"]) <= datetime.fromisoformat(entry["at"])
    # Other entries keep their shape.
    assert not any("duration_ms" in entry for entry, _ in log_entries(loop) if entry["kind"] != "tool")


def test_entry_fields_are_measurements_only(store):
    from app.services.agent_work_log import WorkLog
    log = WorkLog(store, UID, "chat", "turn", ready=lambda: False)
    log.app("checked", {"text": "x"}, step="completion:3", gate_ms=812)
    log.app("paused", "text", gate_ms=True)
    log.app("paused", "text", gate_ms=-1, duration_ms="x" * 41)
    first, second, third = (entry for entry, _ in log.entries_after(0))
    assert first["step"] == "completion:3" and first["gate_ms"] == 812
    assert "gate_ms" not in second and "gate_ms" not in third and "duration_ms" not in third


# --- I1: which limit ended the work ---------------------------------------------------

def test_a_wrap_up_says_which_limit_in_the_log_on_the_turn_and_to_the_agent(store, fake_vm):
    script = Steps([[("vm_exec", {"command": "ls"})]] * 6)
    loop = vm_loop(store, script)
    loop.policy = replace(loop.policy, turn_steps=2, vm_turn_steps=2)
    list(loop.run())
    turn = store._turn_ref(UID, loop.chat_id, loop.turn_id).get().to_dict()
    assert turn["status"] == "completed" and turn["assistant_response"] == ANSWER
    assert turn["agent_wrap_up"]["reason"] == "steps" and turn["agent_wrap_up"]["steps"] == 2
    assert isinstance(turn["agent_wrap_up"]["seconds"], float)
    [(entry, text)] = log_entries(loop, kind="app", name="limit")
    assert entry["actor"] == "app" and json.loads(text)["reason"] == "steps"
    # The agent reads which limit, and that a follow-up message can go on.
    wrap = next(m["content"] for m in reversed(loop.messages) if m.get("role") == "user")
    assert wrap.startswith("App rule: this message has reached its limit.")
    assert "step limit (2 steps per message)" in wrap and "follow-up message" in wrap


def test_a_turn_that_ends_by_itself_has_no_wrap_up(store, fake_vm):
    loop = vm_loop(store, Agent([[("vm_exec", {"command": "ls"})]]))
    list(loop.run())
    assert "agent_wrap_up" not in store._turn_ref(UID, loop.chat_id, loop.turn_id).get().to_dict()
    assert not log_entries(loop, kind="app", name="limit")


def test_the_limit_fact_names_each_limit():
    loop = type("Loop", (), {"_turn_seconds": lambda self: 7200, "_turn_steps": lambda self: 200})()
    fact = agent_delegation.DelegationLoop._limit_fact
    assert fact(loop, agent_delegation.TURN_TIME_LIMIT)[0] == "It reached its time limit (120 minutes per message)."
    assert "allowance" in fact(loop, agent_delegation.TURN_ALLOWANCE_LIMIT)[1]
    for reason in agent_delegation.WRAP_UP_REASONS:
        text, then = fact(loop, reason)
        assert text and then


# --- I9: a gate's entry names its step and its wait -----------------------------------

def test_a_gate_entry_names_its_step_and_its_wait(store):
    from test_agent_gate import gated, go, replies
    script, loop, ran = gated(store, live={})
    script.live.update(anthropic=replies(script, "anthropic", go), openai=replies(script, "openai", go))
    list(loop.run())
    assert ran
    [(checked, text)] = log_entries(loop, kind="app", name="checked")
    # As fields of the entry, where scripts/audit_report.py reads them first.
    assert checked["step"] == "completion:0" and checked["gate_ms"] == json.loads(text)["gate_ms"]


def test_a_gate_the_user_decides_keeps_its_step_and_wait_on_the_pause(store):
    from test_agent_audit import decide_when_held
    from test_agent_gate import gated, go, halt, replies
    script, loop, ran = gated(store, live={})
    script.live.update(anthropic=replies(script, "anthropic", go), openai=replies(script, "openai", halt))
    waiter = decide_when_held(loop, store, "continue")
    list(loop.run())
    waiter.join(5)
    [(paused, _)] = log_entries(loop, kind="app", name="paused")
    assert paused["step"] == "completion:0" and type(paused["gate_ms"]) is int
