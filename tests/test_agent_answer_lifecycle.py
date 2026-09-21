"""The whole visible answer must finish before any judge can review it."""
import json

import httpx
import pytest

from app.services.agent_comparison import review_is_bound
from app.services.llm.agent_client import measured_usage
from app.services.llm.provider_runtime import AnalysisBudgetExceeded, ProviderCancelled
from test_agent_comparison import Script, make_loop
from test_agent_runs import UID, store


INTRO = "Kurz vorweg: Hier die Zusammenfassung:"
CHUNKS = ["Für deine Frage sind drei Punkte entscheidend.\n\n",
          "1. Die Voraussetzungen müssen erfüllt sein.\n",
          "2. Die Einschränkungen bleiben wichtig.\n",
          "3. Daraus folgt diese begründete Empfehlung.\n"]
ANSWER = "".join(CHUNKS)


def answer_factory(script, *, no_call=False, ending="stop", chunks=CHUNKS):
    base = type(script.factory())

    class Completion(base):
        def stream(self, *, model, messages, tools, **kwargs):
            if self.step_id.startswith("completion:") and not tools:
                script.calls.append((self.step_id, model.model))
                self.usage = measured_usage({"prompt_tokens": 50, "completion_tokens": 20, "cost": .0001}, model)
                assert model.selection_id == script.loop.model.selection_id
                assert kwargs["native_searches"] == 0 and kwargs["allow_tool_calls"] is False
                assert script.loop.comparison.judge_calls == 0
                # No unfinished assistant tool-call message may enter this step.
                pending = set()
                for message in messages:
                    pending.update(c["id"] for c in message.get("tool_calls", []))
                    if message["role"] == "tool":
                        pending.remove(message["tool_call_id"])
                assert not pending
                for chunk in chunks:
                    self.text += chunk
                    yield {"type": "delta", "text": chunk}
                    assert script.loop.comparison.judge_calls == 0
                if ending == "cancelled":
                    script.loop.cancellation.cancel()
                    raise ProviderCancelled()
                if ending == "timeout":
                    raise httpx.ReadTimeout("Provider interrupted the answer")
                self.finish_reason = ending
                return
            if self.step_id == "completion:1":
                script.calls.append((self.step_id, model.model))
                self.usage = measured_usage({"prompt_tokens": 50, "completion_tokens": 20, "cost": .0001}, model)
                self.text = INTRO
                yield {"type": "delta", "text": self.text}
                if no_call:
                    self.finish_reason = "stop"
                else:
                    self.tool_calls = [{"id": "early_judge", "type": "function", "function": {
                        "name": "judge_answer", "arguments": json.dumps({"finalize": False})}}]
                    self.finish_reason = "tool_calls"
                return
            yield from super().stream(model=model, messages=messages, tools=tools, **kwargs)

    return Completion


@pytest.mark.parametrize("no_call", [False, True])
def test_early_judge_or_intro_cannot_replace_complete_streamed_answer(store, no_call):
    script = Script()
    loop = make_loop(store, script)
    loop.factory = answer_factory(script, no_call=no_call)
    visible, events = "", []
    for event in loop.run():
        events.append(event)
        if event["type"] == "delta":
            visible += event["text"]
            assert loop.comparison.judge_calls == 0
        if event.get("name") == "judge_answer" and event.get("status") == "running":
            assert visible == ANSWER
            assert store.get_turn(UID, loop.chat_id, loop.turn_id)["consensus"] == ANSWER
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert visible == saved["consensus"] == ANSWER
    assert INTRO not in visible
    assert saved["status"] == "completed"
    assert len(saved["agent_review"]["versions"]) == 1
    assert review_is_bound(saved["agent_review"], ANSWER)
    assert loop.comparison.judge_calls == 2
    first_delta = next(i for i, e in enumerate(events) if e["type"] == "delta")
    assert not any(e.get("clear_response") for e in events[first_delta + 1:])


@pytest.mark.parametrize("ending", ["length", "max_tokens", "cancelled", "timeout"])
def test_incomplete_answer_is_saved_without_starting_judges(store, ending):
    script = Script()
    loop = make_loop(store, script)
    loop.factory = answer_factory(script, ending=ending)
    events = []
    with pytest.raises((AnalysisBudgetExceeded, ProviderCancelled, httpx.ReadTimeout)):
        for event in loop.run():
            events.append(event)
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "failed"
    assert saved["consensus"] == ANSWER
    assert "".join(e["text"] for e in events if e["type"] == "delta") == ANSWER
    assert saved["agent_review"]["status"] == ("cancelled" if ending == "cancelled" else "missing")
    assert not saved["agent_review"].get("checks")
    assert loop.comparison.judge_calls == 0


def test_empty_answer_cannot_start_judges_or_complete_the_turn(store):
    script = Script()
    loop = make_loop(store, script)
    loop.factory = answer_factory(script, chunks=[])
    with pytest.raises(ValueError, match="did not complete the answer"):
        list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "failed"
    assert not saved["consensus"]
    assert not saved["agent_review"].get("checks")
    assert loop.comparison.judge_calls == 0
