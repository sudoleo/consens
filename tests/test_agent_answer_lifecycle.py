"""The whole visible answer must finish before any judge can review it.

The agent writes the answer itself, in the step after its comparison
(agent_answer_mode). The app starts the judges only once that step has
ended with a complete text, and checks exactly what the user saw.
"""
import json

import httpx
import pytest

from app.services.agent_answer_mode import ANSWER_HOLD_CHARS
from app.services.agent_comparison import review_is_bound
from app.services.agent_provider_limits import ProviderCooldowns
from app.services.llm.agent_client import AgentCompletion, measured_usage
from app.services.llm.provider_runtime import AnalysisBudgetExceeded, ProviderCancelled
from test_agent_comparison import Script, make_loop
from test_agent_loop import packet, transport
from test_agent_runs import UID, store  # noqa: F401  (fixture)


INTRO = "Kurz vorweg: Hier die Zusammenfassung:"
CHUNKS = ["Für deine Frage sind drei Punkte entscheidend, und alle drei stützen sich auf die Antworten der Modelle.\n\n",
          "1. Die Voraussetzungen müssen erfüllt sein, sonst greift keine der beiden Optionen wie beschrieben.\n",
          "2. Die Einschränkungen bleiben wichtig, auch wenn die Kosten auf den ersten Blick ähnlich wirken.\n",
          "3. Daraus folgt diese begründete Empfehlung: die erste Option, weil sie das Budget von 100 einhält.\n"]
ANSWER = "".join(CHUNKS)


def test_the_answer_streams_while_it_is_written():
    # Long enough to stream chunk by chunk instead of appearing at the end.
    assert len(ANSWER) > ANSWER_HOLD_CHARS > len(CHUNKS[0]) + len(CHUNKS[1])


def answer_factory(script, *, early_judge=False, ending="stop", chunks=CHUNKS):
    """completion:0 compares (Script). With ``early_judge`` completion:1
    writes an intro and calls judge_answer, which only the app runs. The
    next step writes the answer in ``chunks`` and ends with ``ending``."""
    base = type(script.factory())
    answer_step = 2 if early_judge else 1

    class Completion(base):
        def stream(self, *, model, messages, tools, **kwargs):
            index = int(self.step_id.split(":")[-1]) if self.step_id.startswith("completion:") else None
            if index == answer_step:
                script.calls.append((self.step_id, model.model))
                self.usage = measured_usage({"prompt_tokens": 50, "completion_tokens": 20, "cost": .0001}, model)
                # The agent's own steering step: its model, its tools, no search.
                assert model.selection_id == script.loop.model.selection_id
                assert tools and kwargs["native_searches"] == 0
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
            if early_judge and index == 1:
                script.calls.append((self.step_id, model.model))
                self.usage = measured_usage({"prompt_tokens": 50, "completion_tokens": 20, "cost": .0001}, model)
                self.text = INTRO
                yield {"type": "delta", "text": self.text}
                self.tool_calls = [{"id": "early_judge", "type": "function", "function": {
                    "name": "judge_answer", "arguments": json.dumps({"finalize": False})}}]
                self.finish_reason = "tool_calls"
                return
            yield from super().stream(model=model, messages=messages, tools=tools, **kwargs)

    return Completion


def tool_result(loop, call_id):
    return json.loads(next(m["content"] for m in loop.messages
                           if m.get("role") == "tool" and m.get("tool_call_id") == call_id))


@pytest.mark.parametrize("early_judge", [False, True])
def test_early_judge_or_intro_cannot_replace_complete_streamed_answer(store, early_judge):
    script = Script()
    loop = make_loop(store, script)
    loop.factory = answer_factory(script, early_judge=early_judge)
    visible, events, deltas = "", [], 0
    for event in loop.run():
        events.append(event)
        if event["type"] == "delta":
            visible += event["text"]
            deltas += 1
            assert loop.comparison.judge_calls == 0
        if event.get("name") == "judge_answer" and event.get("status") == "running":
            assert visible == ANSWER
            assert store.get_turn(UID, loop.chat_id, loop.turn_id)["consensus"] == ANSWER
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert visible == saved["consensus"] == ANSWER
    # It streamed while it was written, not as one block at the end.
    assert deltas > 1
    assert INTRO not in visible
    assert saved["status"] == "completed"
    assert len(saved["agent_review"]["versions"]) == 1
    assert review_is_bound(saved["agent_review"], ANSWER)
    assert loop.comparison.judge_calls == 2
    first_delta = next(i for i, e in enumerate(events) if e["type"] == "delta")
    assert not any(e.get("clear_response") for e in events[first_delta + 1:])
    if early_judge:
        # The judges are the app's: the agent cannot start them early.
        assert "error" in tool_result(loop, "early_judge")
        assert not any(e.get("name") == "judge_answer" for e in events[:first_delta])


def test_the_check_is_announced_the_moment_the_last_word_stands(store):
    """The page shows the check from the last word on, not only once the
    settled step, the allowance and the review checkpoints are through."""
    script = Script()
    loop = make_loop(store, script)
    loop.factory = answer_factory(script)
    settled, events = [], []
    original = loop.store.settle
    def settle(*args, **kwargs):
        settled.append(kwargs.get("step"))
        return original(*args, **kwargs)
    loop.store.settle = settle
    for event in loop.run():
        if event["type"] == "answer_check":
            # Before the answer step is even settled.
            assert "completion:1" not in settled
        events.append(event)
    announced = [i for i, e in enumerate(events) if e["type"] == "answer_check"]
    last_delta = max(i for i, e in enumerate(events) if e["type"] == "delta")
    versioned = next(i for i, e in enumerate(events) if e["type"] == "review" and e["review"].get("versions"))
    assert len(announced) == 1 and last_delta < announced[0] < versioned
    assert events[announced[0]] == {"type": "answer_check"}
    # The step's own usage and the review checkpoints come after it.
    assert any(e.get("kind") == "usage" for e in events[announced[0]:versioned])
    # Live only: never part of the saved turn.
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert "answer_check" not in json.dumps(saved, default=str)
    assert review_is_bound(saved["agent_review"], ANSWER)


def test_no_check_is_announced_when_none_follows(store):
    from app.services.agent_comparison import AgentPreferences
    # Answer check off: the answer is final without judges.
    script = Script()
    loop = make_loop(store, script, preferences=AgentPreferences(judges="off"))
    loop.factory = answer_factory(script)
    assert not any(e["type"] == "answer_check" for e in loop.run())
    # A direct answer without comparisons is never checked.
    from test_agent_comparison import Script as Direct
    direct = Direct(direct=True)
    loop = make_loop(store, direct)
    assert not any(e["type"] == "answer_check" for e in loop.run())


@pytest.mark.parametrize("ending", ["length", "max_tokens", "cancelled", "timeout"])
def test_incomplete_answer_is_saved_without_starting_judges(store, ending):
    script = Script()
    loop = make_loop(store, script)
    loop.factory = answer_factory(script, ending=ending)
    events = []
    with pytest.raises((AnalysisBudgetExceeded, ProviderCancelled, httpx.ReadTimeout)):
        for event in loop.run():
            events.append(event)
    # Nothing announces a check that never comes.
    assert not any(e["type"] == "answer_check" for e in events)
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "failed"
    assert saved["consensus"] == ANSWER
    assert "".join(e["text"] for e in events if e["type"] == "delta") == ANSWER
    assert saved["agent_review"]["status"] == ("cancelled" if ending == "cancelled" else "missing")
    assert saved["agent_review"]["versions"][-1]["text"] == ANSWER
    assert not saved["agent_review"].get("checks")
    assert loop.comparison.judge_calls == 0


def _empty_over_http(script, monkeypatch):
    """The answer step through the real client, which ends without text."""
    transport(monkeypatch, [[packet({}, finish="stop", usage={"prompt_tokens": 50, "completion_tokens": 0})]])
    base = type(script.factory())

    class Completion(base):
        def stream(self, **kwargs):
            if self.step_id == "completion:1":
                yield from AgentCompletion.stream(self, **kwargs)
            else:
                yield from super().stream(**kwargs)
    return Completion


@pytest.mark.parametrize("source", [
    "http",
    # Unreachable with the real client (it raises on an empty stop); the loop
    # refuses it itself (DelegationLoop._finish_merged).
    "scripted",
])
def test_empty_answer_cannot_start_judges_or_complete_the_turn(store, monkeypatch, source):
    script = Script()
    loop = make_loop(store, script)
    loop.cooldowns = ProviderCooldowns()  # never the process-wide gate in tests
    loop.factory = (_empty_over_http(script, monkeypatch) if source == "http"
                    else answer_factory(script, chunks=[]))
    events = []
    with pytest.raises(Exception):
        for event in loop.run():
            events.append(event)
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "failed"
    assert not saved["consensus"]
    assert not saved["agent_review"].get("checks")
    assert loop.comparison.judge_calls == 0
    assert not any(e.get("name") == "judge_answer" for e in events)
    # The failure never claims an answer that does not exist.
    assert "has been saved" not in saved["agent_failure"]["error"]
