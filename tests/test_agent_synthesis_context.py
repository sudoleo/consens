"""Answer generation receives evidence, never the orchestrator's private continuation."""
from dataclasses import replace
import json

import pytest

from app.services import prompt_config
from app.services.agent_comparison import review_is_bound
from app.services.llm.agent_client import AgentCompletion
from test_agent_comparison import Script, make_loop
from test_agent_loop import packet, transport
from test_agent_runs import UID, store


@pytest.mark.parametrize("compares,fail_model", [(1, False), (2, False), (1, True)])
def test_synthesis_receives_original_conversation_and_evidence_without_tool_protocol(store, monkeypatch, compares, fail_model):
    config = prompt_config.defaults()
    # The Consensus-mode prompt no longer shapes the Agent answer.
    config["prompts"]["consensus"] = "CONSENSUS_MODE_ONLY_STYLE"
    monkeypatch.setattr(prompt_config, "get_config", lambda: config)
    history = [{"role": "system", "content": "INTERNAL_ROUTING_PROMPT"},
               {"role": "user", "content": "Please preserve literal code and my budget of 100."},
               {"role": "assistant", "content": "Your example is `status_update = 'ready'`."},
               {"role": "user", "content": "Compare both options, please."}]
    script = Script(compares=compares, fail_model=fail_model)
    base = type(script.factory())
    captured = []

    class Completion(base):
        def stream(self, **kwargs):
            if self.step_id.startswith("completion:") and not kwargs["tools"]:
                captured.append(kwargs["messages"])
            yield from super().stream(**kwargs)
            if self.step_id == "completion:0":
                self.text = "INTERNAL_TOOL_PREAMBLE"
                self._reasoning_parts = [{"type": "reasoning.text", "text": "PRIVATE_CONTINUATION"}]
                self._reasoning_text = "PRIVATE_REASONING"

    loop = make_loop(store, script, messages=history)
    loop.factory = Completion
    loop.completion.event("tool", "research-step", name="INTERNAL_SEARCH_STEP", status="succeeded",
                          sources=[{"url": "https://example.org/research", "title": "Research evidence"}])
    # Runtime reminders must not be mistaken for an actual user request.
    loop.messages.append({"role": "user", "content": "INTERNAL_NEXT_STEP"})
    events = list(loop.run())
    assert len(captured) == 1
    messages = captured[0]
    assert messages[1:-1] == history[1:]
    from app.services.prompt_defaults import AGENT_ANSWER_PROMPT
    assert messages[0]["content"].startswith(AGENT_ANSWER_PROMPT)
    assert "CONSENSUS_MODE_ONLY_STYLE" not in messages[0]["content"]
    for message in messages:
        assert set(message) == {"role", "content"}
        assert message["role"] in {"system", "user", "assistant"}
    serialized = json.dumps(messages)
    for private in ("INTERNAL_ROUTING_PROMPT", "INTERNAL_TOOL_PREAMBLE", "PRIVATE_CONTINUATION",
                    "PRIVATE_REASONING", "INTERNAL_NEXT_STEP", "INTERNAL_SEARCH_STEP", "judge_answer", "next_tool"):
        assert private not in serialized
    for index in range(compares):
        assert f"Evaluate option {index + 1}" in serialized
    assert "Budget is 100. Source: https://example.org/report" in serialized
    assert "The constraint matters." in serialized
    assert "https://example.org/research" in serialized
    if fail_model:
        assert '"unavailable_answers": 1' in messages[-1]["content"]
    # Filtering execution metadata must not strip legitimate user code/history.
    assert "status_update = 'ready'" in serialized
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["consensus"] == "The first option costs 100."
    assert review_is_bound(saved["agent_review"], saved["consensus"])
    assert not any(e.get("kind") == "reasoning" for e in events)


def test_standalone_synthesis_keeps_effort_and_never_stores_reasoning_continuation(store, monkeypatch):
    script = Script()
    base = type(script.factory())
    answer = "The first option costs 100.\n\nUse `status_update` in your example."
    requests, _, _ = transport(monkeypatch, [[
        packet({"reasoning_content": "PRIVATE_REASONING", "content": answer[:26]}),
        packet({"reasoning_details": [{"type": "reasoning.text", "text": "PRIVATE_CONTINUATION", "index": 0}],
                "content": answer[26:]}, finish="stop",
               usage={"prompt_tokens": 50, "completion_tokens": 20, "cost": .0001}),
    ]])

    class Completion(base):
        def stream(self, **kwargs):
            if self.step_id.startswith("completion:") and not kwargs["tools"]:
                yield from AgentCompletion.stream(self, **kwargs)
            else:
                yield from super().stream(**kwargs)

    loop = make_loop(store, script)
    reasoning = {"effort": "low", "exclude": False, "summary": "auto"}
    loop.model = replace(loop.model, request_config={**loop.model.request_config, "reasoning": reasoning})
    loop.factory = Completion
    events = list(loop.run())
    assert len(requests) == 1
    # Reasoning streams (excerpts keep a long answer step visibly alive), but
    # fragments without a complete sentence never surface, and no continuation
    # data reaches events, the saved turn or the conversation.
    assert requests[0]["reasoning"] == reasoning
    assert "tools" not in requests[0]
    assert loop.model.request_config["reasoning"] == reasoning
    assert "".join(e["text"] for e in events if e["type"] == "delta") == answer
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["consensus"] == answer
    assert review_is_bound(saved["agent_review"], answer)
    assert "PRIVATE_" not in json.dumps(events) + json.dumps(saved, default=str)


def _answer_transport(monkeypatch, responses):
    requests, _, _ = transport(monkeypatch, responses)
    return requests


class _AnswerOverHttp:
    """Only the tool-free answer step goes through the real client."""
    @staticmethod
    def factory(script):
        base = type(script.factory())
        class Completion(base):
            def stream(self, **kwargs):
                if self.step_id.startswith("completion:") and not kwargs["tools"]:
                    yield from AgentCompletion.stream(self, **kwargs)
                else:
                    yield from super().stream(**kwargs)
        return Completion


def test_answer_step_shows_reasoning_excerpts_while_thinking_but_keeps_them_out_of_context(store, monkeypatch):
    script = Script()
    answer = "The first option costs 100."
    requests = _answer_transport(monkeypatch, [[
        packet({"reasoning": "Weighing the cost of both options against the budget. "}),
        packet({"reasoning": "The first option fits the stated budget exactly."}),
        packet({"content": answer}, finish="stop", usage={"prompt_tokens": 50, "completion_tokens": 20, "cost": .0001}),
    ]])
    loop = make_loop(store, script)
    loop.factory = _AnswerOverHttp.factory(script)
    events = list(loop.run())
    assert len(requests) == 1 and requests[0].get("reasoning", {}).get("exclude") is not True
    thinking = [e for e in events if e.get("kind") == "progress" and e["id"].endswith("/thinking")]
    assert thinking and "Weighing the cost of both options" in thinking[-1]["text"]
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["consensus"] == answer
    assert any(item["id"].endswith("/thinking") for item in saved["agent_activity"])
    # Visible excerpts only: no continuation data in the conversation.
    assert "Weighing" not in json.dumps(loop.messages)


def _thought_only():
    return [packet({"reasoning": "Still weighing every option. "}),
            packet({}, finish="length", usage={"prompt_tokens": 50, "completion_tokens": 32768, "cost": .5})]


def test_thought_only_answer_step_is_written_again_with_lighter_reasoning(store, monkeypatch):
    from app.services import agent_delegation
    script = Script()
    answer = "The first option costs 100."
    requests = _answer_transport(monkeypatch, [_thought_only(), [
        packet({"content": answer}, finish="stop", usage={"prompt_tokens": 50, "completion_tokens": 20, "cost": .0001})]])
    monkeypatch.setattr(agent_delegation, "lighter_reasoning", lambda model: replace(
        model, reasoning_effort="low", request_config={**model.request_config, "reasoning": {"effort": "low", "exclude": False}}))
    loop = make_loop(store, script)
    loop.factory = _AnswerOverHttp.factory(script)
    events = list(loop.run())
    assert len(requests) == 2 and requests[1]["reasoning"]["effort"] == "low"
    assert any(e.get("kind") == "progress" and e["id"].endswith("/retry") for e in events)
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "completed" and saved["consensus"] == answer
    assert review_is_bound(saved["agent_review"], answer)
    # Both attempts are paid and counted.
    assert saved["agent_usage"]["output_tokens"] >= 32768 + 20


def test_thought_only_answer_without_lighter_reasoning_fails_as_output_limit_not_provider_error(store, monkeypatch):
    from app.services import agent_delegation
    from app.services.agent_provider_limits import ModelOutputLimit, agent_failure
    script = Script()
    requests = _answer_transport(monkeypatch, [_thought_only()])
    monkeypatch.setattr(agent_delegation, "lighter_reasoning", lambda model: None)
    loop = make_loop(store, script)
    loop.factory = _AnswerOverHttp.factory(script)
    with pytest.raises(ModelOutputLimit):
        list(loop.run())
    assert len(requests) == 1
    assert loop.completion.failure["code"] == "output_limit"
    assert agent_failure(ModelOutputLimit())["code"] == "output_limit"


def test_reasoning_answer_step_gets_headroom_and_a_lighter_retry_effort():
    from app.services.llm.agent_client import (
        ANSWER_OUTPUT_CEILING, ANSWER_REASONING_HEADROOM, AgentModel, answer_output_limit, lighter_reasoning)
    sonnet = AgentModel(model="anthropic/claude-sonnet-5.5", reasoning_effort="max",
                        request_config={"reasoning": {"effort": "max", "exclude": False}})
    assert answer_output_limit(sonnet) == ANSWER_OUTPUT_CEILING + ANSWER_REASONING_HEADROOM
    lighter = lighter_reasoning(sonnet)
    # Sonnet cannot switch reasoning off: its lightest supported effort.
    assert lighter.reasoning_effort == "low" and lighter.request_config["reasoning"]["effort"] == "low"
    assert lighter_reasoning(lighter) is None
    off = replace(sonnet, model="openai/gpt-6-luna", request_config={"reasoning": {"effort": "none"}})
    assert answer_output_limit(off) == ANSWER_OUTPUT_CEILING
    plain = replace(sonnet, model="anthropic/claude-haiku-4.5", request_config={})
    assert lighter_reasoning(plain) is None
