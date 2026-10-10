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
    # The turn says what to do instead of only what happened.
    assert "lower reasoning level" in loop.completion.failure["error"]
    assert agent_failure(ModelOutputLimit())["code"] == "output_limit"


def test_reasoning_answer_step_gets_headroom_and_a_lighter_retry_effort():
    from app.services.llm.agent_client import (
        ANSWER_OUTPUT_CEILING, ANSWER_REASONING_HEADROOM, AgentModel, answer_output_limit, lighter_reasoning)
    sonnet = AgentModel(model="anthropic/claude-sonnet-5.5", reasoning_effort="max",
                        request_config={"reasoning": {"effort": "max", "exclude": False}})
    assert answer_output_limit(sonnet) == ANSWER_OUTPUT_CEILING + ANSWER_REASONING_HEADROOM
    lighter = lighter_reasoning(sonnet)
    # Sonnet cannot switch reasoning off; the retry tries "low" first anyway.
    assert lighter.reasoning_effort == "low" and lighter.request_config["reasoning"]["effort"] == "low"
    assert lighter_reasoning(lighter) is None
    off = replace(sonnet, model="openai/gpt-6-luna", request_config={"reasoning": {"effort": "none"}})
    assert answer_output_limit(off) == ANSWER_OUTPUT_CEILING
    plain = replace(sonnet, model="anthropic/claude-haiku-4.5", request_config={})
    assert lighter_reasoning(plain) is None


SHARED, EXA, NATIVE = "https://example.org/shared", "https://example.org/exa", "https://example.org/native"
HIGHLIGHT = "\n".join(f"EXA_HIGHLIGHT line {i}: the first option is listed at 100 EUR per month." for i in range(30))
PAGE = "\n".join(["Navigation and unrelated history."] * 40
                 + ["PAGE_PASSAGE: The first option costs 100 EUR and includes support."]
                 + ["Footer text about the weather."] * 40)


def _cited_run(store, monkeypatch, *, context_chars=None):
    """Both comparison answers cite a shared source without text and one of
    their own: the Exa family with search text, the native one without."""
    from app.services import agent_source_evidence
    claim_end = len("The first option costs 100.")
    fetched = []

    def fetch(url, limits):
        fetched.append(url)
        if url != NATIVE:
            raise ValueError("not_found")
        return {"text": PAGE, "dates": [{"value": "2026-10-01", "origin": "json-ld:datePublished"}]}
    monkeypatch.setattr(agent_source_evidence, "fetch_document", fetch)
    script = Script()
    base = type(script.factory())
    captured = []

    class Completion(base):
        def stream(self, *, model, messages, **kwargs):
            if self.step_id.startswith("completion:") and not kwargs["tools"]:
                captured.append(messages)
            yield from super().stream(model=model, messages=messages, **kwargs)
            if not self.step_id.startswith("completion:") and not model.request_config.get("response_format"):
                own = NATIVE if model.model.startswith("anthropic") else EXA
                self.sources = [{"url": SHARED, "title": "Shared"}, {"url": own, "title": "Own"}]
                self.citations = [
                    {"url": SHARED, "content": "", "start_index": 0, "end_index": claim_end, "fallback_end_index": 0},
                    {"url": own, "content": "" if own == NATIVE else HIGHLIGHT, "start_index": 0,
                     "end_index": claim_end, "fallback_end_index": 0}]

    loop = make_loop(store, script)
    if context_chars:
        loop.policy = replace(loop.policy, context_chars=context_chars)
    loop.factory = Completion
    list(loop.run())
    assert len(captured) == 1
    return loop, captured[0], fetched


def _evidence(messages):
    return json.loads(messages[-1]["content"].split("\n", 1)[1])


def test_answer_step_reads_what_the_cited_sources_say_without_storing_it(store, monkeypatch):
    """Comparison citations reach the answer step as one pooled source list:
    search text where the provider sent it, the page where it did not,
    bound to the sentences the answers support with them."""
    from app.services import agent_source_evidence
    loop, messages, fetched = _cited_run(store, monkeypatch)
    evidence = _evidence(messages)
    answers = evidence["comparisons"][0]["answers"]
    assert sorted(answer["sources"][1] for answer in answers) == [EXA, NATIVE]
    assert all(answer["sources"][0] == SHARED for answer in answers)
    sources = {source["url"]: source for source in evidence["sources"]}
    assert list(sources)[0] == SHARED and sources[SHARED]["cited_by"] == 2
    # No text for the shared source anywhere: listed, citable, without excerpt.
    assert "excerpt" not in sources[SHARED]
    assert "EXA_HIGHLIGHT" in sources[EXA]["excerpt"] and sources[EXA]["supports"] == ["The first option costs 100."]
    # The page is cut to the passage behind the claim and its neighbourhood.
    assert "PAGE_PASSAGE" in sources[NATIVE]["excerpt"]
    assert len(sources[NATIVE]["excerpt"]) <= agent_source_evidence.LEAD_EXCERPT_CHARS < len(PAGE)
    assert sources[NATIVE]["published"] == "2026-10-01"
    assert sorted(fetched) == sorted([SHARED, NATIVE])
    # Excerpts are context for one answer step: never saved with the turn.
    saved = json.dumps(store.get_turn(UID, loop.chat_id, loop.turn_id), default=str)
    assert "EXA_HIGHLIGHT" not in saved and "PAGE_PASSAGE" not in saved
    assert '"title": "Own"' in saved


def test_bounded_runs_give_excerpts_only_the_context_room_left(store, monkeypatch):
    loop, messages, _ = _cited_run(store, monkeypatch, context_chars=7000)
    assert len(json.dumps(messages, ensure_ascii=False)) <= 7000
    sources = {source["url"]: source for source in _evidence(messages)["sources"]}
    assert set(sources) == {SHARED, EXA, NATIVE}
    excerpts = sum(len(source.get("excerpt", "")) for source in sources.values())
    assert 0 < excerpts < 2 * 1200
    assert store.get_turn(UID, loop.chat_id, loop.turn_id)["status"] == "completed"


def test_a_failing_excerpt_step_never_costs_the_paid_answer(store, monkeypatch):
    """Excerpts only enrich the answer step: an error while pooling them
    leaves the answers with their URLs, and the turn completes."""
    from app.services import agent_source_evidence

    def broken(*args, **kwargs):
        raise RuntimeError("excerpt bug")
    monkeypatch.setattr(agent_source_evidence, "select_passages", broken)
    loop, messages, _ = _cited_run(store, monkeypatch)
    evidence = _evidence(messages)
    assert evidence["sources"] == []
    assert all(answer["sources"][0] == SHARED for answer in evidence["comparisons"][0]["answers"])
    assert store.get_turn(UID, loop.chat_id, loop.turn_id)["status"] == "completed"


@pytest.mark.parametrize("context_chars", [6000, 9000, 16000])
def test_bounded_runs_fit_quote_heavy_excerpts(store, monkeypatch, context_chars):
    """Quotes and line breaks cost twice in the evidence string: the excerpts
    shrink until the step fits, instead of failing the paid turn."""
    import sys
    monkeypatch.setattr(sys.modules[__name__], "HIGHLIGHT", "\n".join(
        f'EXA_HIGHLIGHT {i}: "the first option" is listed at "100 EUR" per "month" {chr(92)} "net".' for i in range(60)))
    loop, messages, _ = _cited_run(store, monkeypatch, context_chars=context_chars)
    assert len(json.dumps(messages, ensure_ascii=False)) <= context_chars
    assert store.get_turn(UID, loop.chat_id, loop.turn_id)["status"] == "completed"
