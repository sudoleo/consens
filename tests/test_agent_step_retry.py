"""A chat model step that breaks off in passing runs once more, and a turn
that still breaks off leaves its work for "Retry" (since 2026-10-27).

Twice on 2026-10-27 a step of DeepSeek V4.1 Flash in audit mode broke off
after minutes of paid work in the VM and on the web (a call after its own
searches carried a stream index the client refused), and the whole turn
ended as "The model provider could not finish this request".
"""
import json

import pytest

from app.services import agent_runs
from app.services.agent_tools import ReadOnlyTool, ToolRegistry
from app.services.llm.agent_client import measured_usage
from test_agent_audit import ANSWER, Audit, LookupArgs, audit_loop, saved
from test_agent_runs import UID, pending, store  # noqa: F401  (fixture)


class Breaking(Audit):
    """The scripted audit turn of test_agent_audit, whose steps in ``breaks``
    ({step id: times}) break off before the user sees a word: the provider
    measured some input, then the stream could not be read."""

    def __init__(self, breaks, **kwargs):
        super().__init__(**kwargs)
        self.breaks = dict(breaks)

    def factory(self):
        completion = super().factory()
        script, scripted = self, completion.stream

        def stream(**kwargs):
            if script.breaks.get(completion.step_id, 0) > 0:
                script.breaks[completion.step_id] -= 1
                script.calls.append((completion.step_id, "broken"))
                completion.usage = measured_usage({"prompt_tokens": 50, "completion_tokens": 5}, kwargs["model"])
                raise ValueError("Invalid tool call index")
                yield  # a generator, like the real stream
            yield from scripted(**kwargs)
        completion.stream = stream
        return completion


def raw_turn(store, loop):
    """The turn as stored (get_turn leaves out the work record)."""
    return (store.db.collection("users").document(UID).collection("chats").document(loop.chat_id)
            .collection("turns").document(loop.turn_id).get().to_dict())


def with_note_tool(loop):
    """A tool that answers at once (the scripted lookup waits for reviewers)."""
    note = ReadOnlyTool("note", "Note something.", LookupArgs, lambda args, *, cancellation: {"text": "Noted."})
    loop.registry = ToolRegistry([*loop.registry.tools.values(), note], argument_limit=loop.registry.argument_limit)
    return loop


def test_a_step_that_broke_off_runs_once_more_and_the_turn_completes(store):
    script = Breaking({"completion:0": 1}, search=False)
    loop = audit_loop(store, script, judges="off")
    events = list(loop.run())
    turn = saved(store, loop)
    assert turn["status"] == "completed" and turn["consensus"] == ANSWER
    # The broken step, then the same request again as the next step.
    assert [step for step, model in script.calls if step.startswith("completion:")] == ["completion:0", "completion:1"]
    assert script.calls[0] == ("completion:0", "broken")
    # The user reads why it took a moment; nothing of the broken step showed.
    notes = [e for e in events if e.get("kind") == "progress" and str(e.get("id")).endswith("/passing_retry")]
    assert [e["text"] for e in notes] == ["The model's reply broke off. Trying this step once more."]
    # The broken attempt is paid for what it used, and the work log says it failed.
    receipt = store.receipt_ref(UID, loop.chat_id, loop.turn_id, "completion:0").get().to_dict()
    assert receipt["status"] == "succeeded" and receipt["usage"]["input_tokens"] == 50
    log = [e.to_dict() for e in store.db.collection("users").document(UID).collection("chats")
           .document(loop.chat_id).collection("turns").document(loop.turn_id).collection("work_log").stream()]
    steps = [json.loads(e["content"])["status"] for e in sorted(log, key=lambda e: e["seq"]) if e["kind"] == "step"]
    assert steps == ["failed", "succeeded"]


def test_a_turn_that_still_breaks_off_leaves_its_work_for_retry(store):
    script = Breaking({"completion:1": 1, "completion:2": 1}, search=False, tool_steps=1, step_tools={0: "note"})
    loop = with_note_tool(audit_loop(store, script, judges="off"))
    with pytest.raises(ValueError):
        list(loop.run())
    turn = saved(store, loop)
    # Once more is all: the second break ends the turn as before.
    assert turn["status"] == "failed" and turn["agent_failure"]["code"] == "provider_error"
    assert [step for step, _ in script.calls if step.startswith("completion:")] == [
        "completion:0", "completion:1", "completion:2"]
    # Its calls are saved (before 2026-10-27 only after a VM run) ...
    record = raw_turn(store, loop)["agent_work_record"]
    assert "1. note" in record
    # ... and "Retry", the same question again, builds on them.
    _, retry = pending(store, chat_id=loop.chat_id, request_id="two", question="Tell me about the Eiffel Tower.")
    messages = store.messages(UID, loop.chat_id, retry)
    position = next(i for i, m in enumerate(messages) if m.get("content") == agent_runs.FAILED_TURN_RESUME)
    assert messages[position]["role"] == "assistant"
    assert messages[position + 1]["content"] == record


def test_a_failed_turn_without_calls_keeps_its_plain_note(store):
    script = Breaking({"completion:0": 1, "completion:1": 1}, search=False)
    loop = audit_loop(store, script, judges="off")
    with pytest.raises(ValueError):
        list(loop.run())
    turn = saved(store, loop)
    assert turn["status"] == "failed" and not raw_turn(store, loop).get("agent_work_record")
    _, retry = pending(store, chat_id=loop.chat_id, request_id="two", question="Again")
    contents = [m.get("content") for m in store.messages(UID, loop.chat_id, retry)]
    assert "[This previous turn did not finish successfully. No assistant answer was saved.]" in contents
    assert agent_runs.FAILED_TURN_RESUME not in contents
