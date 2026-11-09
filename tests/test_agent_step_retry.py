"""A chat model step that breaks off in passing runs once more, and a turn
that still breaks off leaves its work for "Retry".

Twice in one day a step of DeepSeek V4.1 Flash broke off
after minutes of paid work in the VM and on the web (a call after its own
searches carried a stream index the client refused), and the whole turn
ended as "The model provider could not finish this request".
"""
import json

import pytest

from app.services import agent_runs
from app.services.agent_tools import ReadOnlyTool, ToolRegistry
from app.services.llm.agent_client import measured_usage
from agent_reviewers import without_reviewers
from test_agent_audit import ANSWER, Audit, LookupArgs, audit_loop, saved
from test_agent_runs import UID, pending, store  # noqa: F401  (fixture)


class Breaking(Audit):
    """The scripted turn of test_agent_audit, whose steps in ``breaks``
    ({step id: times}) break off before the user sees a word: the provider
    measured some input, then the stream could not be read. ``error``: what
    such a step raises instead; ``endpoint``: the endpoint that served it
    (the stream's ``provider``). ``avoided`` keeps, per request of the chat
    model, the endpoints it was told to avoid."""

    def __init__(self, breaks, *, error=None, endpoint="", **kwargs):
        super().__init__(**kwargs)
        self.breaks = dict(breaks)
        self.error, self.endpoint = error, endpoint
        self.avoided = []

    def factory(self):
        completion = super().factory()
        script, scripted = self, completion.stream

        def stream(**kwargs):
            if completion.step_id.startswith("completion:"):
                script.avoided.append(tuple(completion.avoid_endpoints))
            if script.breaks.get(completion.step_id, 0) > 0:
                script.breaks[completion.step_id] -= 1
                script.calls.append((completion.step_id, "broken"))
                completion.endpoint = script.endpoint
                completion.usage = measured_usage({"prompt_tokens": 50, "completion_tokens": 5}, kwargs["model"])
                raise script.error or ValueError("Invalid tool call index")
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
    loop = without_reviewers(audit_loop(store, script))
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
    from app.services.agent_sessions import work_log_entries
    log = [entry for e in store.db.collection("users").document(UID).collection("chats")
           .document(loop.chat_id).collection("turns").document(loop.turn_id).collection("work_log").stream()
           for entry in work_log_entries(e.to_dict())]
    steps = [json.loads(e["content"])["status"] for e in sorted(log, key=lambda e: e["seq"]) if e["kind"] == "step"]
    assert steps == ["failed", "succeeded"]


def test_a_turn_that_still_breaks_off_leaves_its_work_for_retry(store):
    script = Breaking({"completion:1": 1, "completion:2": 1}, search=False, tool_steps=1, step_tools={0: "note"})
    loop = with_note_tool(without_reviewers(audit_loop(store, script)))
    with pytest.raises(ValueError):
        list(loop.run())
    turn = saved(store, loop)
    # Once more is all: the second break ends the turn.
    assert turn["status"] == "failed" and turn["agent_failure"]["code"] == "provider_error"
    assert [step for step, _ in script.calls if step.startswith("completion:")] == [
        "completion:0", "completion:1", "completion:2"]
    # Its calls are saved, also without a VM run ...
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
    loop = without_reviewers(audit_loop(store, script))
    with pytest.raises(ValueError):
        list(loop.run())
    turn = saved(store, loop)
    assert turn["status"] == "failed" and not raw_turn(store, loop).get("agent_work_record")
    _, retry = pending(store, chat_id=loop.chat_id, request_id="two", question="Again")
    contents = [m.get("content") for m in store.messages(UID, loop.chat_id, retry)]
    assert "[This previous turn did not finish successfully. No assistant answer was saved.]" in contents
    assert agent_runs.FAILED_TURN_RESUME not in contents


# --- The second attempt goes to another endpoint -------------------------------

def test_the_second_attempt_avoids_the_endpoint_the_first_broke_off_on(store):
    """What broke an attempt mostly belongs to its endpoint (an outage, a
    stalled host), and the chat's session would send the retry straight
    back to it."""
    script = Breaking({"completion:0": 1}, endpoint="Azure", search=False)
    loop = without_reviewers(audit_loop(store, script))
    list(loop.run())
    assert saved(store, loop)["status"] == "completed"
    assert script.avoided == [(), ("Azure",)]


def test_an_attempt_without_a_known_endpoint_is_retried_as_before(store):
    script = Breaking({"completion:0": 1}, search=False)
    loop = without_reviewers(audit_loop(store, script))
    list(loop.run())
    assert saved(store, loop)["status"] == "completed" and script.avoided == [(), ()]


def test_a_step_one_endpoint_declined_is_asked_of_another(store):
    """Each endpoint of a model filters for itself: Terra on Azure declined
    a step twice that OpenAI's own endpoint takes, after four minutes of
    paid work (2026-11-07). Declined before a word, the step runs once more
    elsewhere instead of ending the turn."""
    from app.services.agent_provider_limits import ModelDeclined
    script = Breaking({"completion:1": 1}, error=ModelDeclined(), endpoint="Azure", search=False, tool_steps=1,
                      step_tools={0: "note"})
    loop = with_note_tool(without_reviewers(audit_loop(store, script)))
    list(loop.run())
    turn = saved(store, loop)
    assert turn["status"] == "completed" and turn["consensus"] == ANSWER
    assert script.avoided == [(), (), ("Azure",)]


def test_a_step_declined_on_the_other_endpoint_too_ends_the_turn_as_declined(store):
    from app.services.agent_provider_limits import ModelDeclined
    script = Breaking({"completion:0": 1, "completion:1": 1}, error=ModelDeclined(), endpoint="Azure", search=False)
    loop = without_reviewers(audit_loop(store, script))
    with pytest.raises(ModelDeclined):
        list(loop.run())
    turn = saved(store, loop)
    assert turn["status"] == "failed" and turn["agent_failure"]["code"] == "model_declined"
    assert script.avoided == [(), ("Azure",)]


def test_a_decline_without_a_known_endpoint_is_not_asked_again(store):
    """The same request to the same endpoint meets the same filter."""
    from app.services.agent_provider_limits import ModelDeclined
    script = Breaking({"completion:0": 1}, error=ModelDeclined(), search=False)
    loop = without_reviewers(audit_loop(store, script))
    with pytest.raises(ModelDeclined):
        list(loop.run())
    assert script.avoided == [()]
