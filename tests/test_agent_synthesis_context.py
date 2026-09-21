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
    config["prompts"]["consensus"] = "Use the configured editorial style."
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
                self._reasoning_parts = {0: {"type": "reasoning.text", "text": "PRIVATE_CONTINUATION"}}
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
    assert "Use the configured editorial style." in messages[0]["content"]
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


def test_standalone_synthesis_excludes_provider_reasoning_without_changing_effort_or_visible_text(store, monkeypatch):
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
    assert requests[0]["reasoning"] == {"effort": "low", "exclude": True}
    assert "tools" not in requests[0]
    assert loop.model.request_config["reasoning"] == reasoning
    assert "".join(e["text"] for e in events if e["type"] == "delta") == answer
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["consensus"] == answer
    assert review_is_bound(saved["agent_review"], answer)
    assert "PRIVATE_" not in json.dumps(events) + json.dumps(saved, default=str)
