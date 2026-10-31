"""The agent writes the answer in its own conversation (agent_answer_mode).

The step after a comparison sees every answer in full, with the sources'
excerpts, and may write the answer with the chosen reasoning and the answer
allowance. Reasoning excerpts show while it thinks; the text it writes is
exactly what the app shows, saves and has reviewed. Provider continuation
data never reaches the user or the saved turn.
"""
from dataclasses import replace
import json

import pytest

from app.services.agent_comparison import answer_hash
from app.services.llm.agent_client import AgentCompletion, answer_output_limit, routing_output_limit
from test_agent_comparison import Script, make_loop
from test_agent_loop import packet, transport
from test_agent_runs import UID, store  # noqa: F401  (fixture)


def _writes_answer(step_id, script):
    """The orchestrator step after the scripted comparisons: it writes the answer."""
    return step_id.startswith("completion:") and int(step_id.split(":")[-1]) >= script.compares


def reviewed(review, text):
    """The saved review is the reviewers' review of exactly ``text``."""
    return review.get("mode") == "audit" and review.get("answer_hash") == answer_hash(text)


def _comparison_results(messages):
    """The compare_models results in the agent's conversation, in order."""
    calls = {call["id"] for message in messages if message["role"] == "assistant"
             for call in message.get("tool_calls") or [] if call["function"]["name"] == "compare_models"}
    return [json.loads(message["content"]) for message in messages
            if message["role"] == "tool" and message["tool_call_id"] in calls]


def _deltas(events):
    return "".join(event["text"] for event in events if event["type"] == "delta")


@pytest.mark.parametrize("compares,fail_model", [(1, False), (2, False), (1, True)])
def test_the_answer_step_writes_from_full_answers_in_its_own_conversation(store, compares, fail_model):
    from app.services.prompt_defaults import AGENT_AUDIT_ANSWER_SECTION
    history = [{"role": "system", "content": "STEERING_PROMPT"},
               {"role": "user", "content": "Please preserve literal code and my budget of 100."},
               {"role": "assistant", "content": "Your example is `status_update = 'ready'`."},
               {"role": "user", "content": "Compare both options, please."}]
    script = Script(compares=compares, fail_model=fail_model)
    base = type(script.factory())
    captured = []

    class Completion(base):
        def stream(self, **kwargs):
            if _writes_answer(self.step_id, script):
                # A copy: the loop appends to its live conversation afterwards.
                captured.append({**kwargs, "messages": json.loads(json.dumps(kwargs["messages"]))})
            yield from super().stream(**kwargs)
            if self.step_id == "completion:0":
                self._reasoning_parts = [{"type": "reasoning.text", "text": "PRIVATE_CONTINUATION"}]

    loop = make_loop(store, script, messages=history)
    loop.factory = Completion
    events = list(loop.run())
    assert len(captured) == 1
    request = captured[0]
    messages = request["messages"]
    # The agent's own conversation, with the app's facts and its tools still
    # listed: no fresh context, no second read of the answers.
    assert messages[1:4] == history[1:]
    assert messages[0]["content"].startswith("STEERING_PROMPT") and AGENT_AUDIT_ANSWER_SECTION in messages[0]["content"]
    assert request["tools"] and request.get("allow_tool_calls") is not False
    results = _comparison_results(messages)
    assert [result["question"] for result in results] == [f"Evaluate option {i + 1}" for i in range(compares)]
    for result in results:
        assert result["context"] == "Budget is 100. Source: https://example.org/report"
        # Depth only set how the comparison models answered.
        assert "depth" not in result and "text_shortened_for_routing" not in json.dumps(result)
        assert "untrusted data" in result["instruction"]
        assert all("family" not in answer and "model" not in answer for answer in result["answers"])
        # Every delivered answer in full, a failed one named as missing.
        assert all(answer["text"] == "The first option costs 100. The constraint matters." for answer in result["answers"])
        if fail_model:
            assert len(result["answers"]) == 1
            assert [missing["family"] for missing in result["missing_answers"]] == ["anthropic"]
        else:
            assert len(result["answers"]) == 2 and result["missing_answers"] == []
    # No app note after the evidence (until 2026-10-31 AGENT_WRITE_NOTE): the
    # answers advise, the agent goes on from them.
    assert messages[-1]["role"] == "tool"
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    # What the step wrote is what the user saw, what was saved and reviewed.
    assert _deltas(events) == saved["consensus"] == "The first option costs 100."
    assert reviewed(saved["agent_review"], saved["consensus"])
    # A preamble before a tool call never reaches the user; continuation
    # data stays with the provider conversation.
    assert "I will compare" not in _deltas(events)
    assert "PRIVATE_" not in json.dumps(events) + json.dumps(saved, default=str)
    assert not any(e.get("kind") == "reasoning" for e in events)


class _AnswerOverHttp:
    """Only the step that writes the answer goes through the real client."""
    @staticmethod
    def factory(script):
        base = type(script.factory())

        class Completion(base):
            def stream(self, **kwargs):
                if _writes_answer(self.step_id, script):
                    yield from AgentCompletion.stream(self, **kwargs)
                else:
                    yield from super().stream(**kwargs)
        return Completion


def test_answer_step_keeps_effort_and_allowance_and_never_stores_reasoning_continuation(store, monkeypatch):
    script = Script()
    answer = "The first option costs 100.\n\nUse `status_update` in your example."
    requests, _, _ = transport(monkeypatch, [[
        packet({"reasoning_content": "PRIVATE_REASONING", "content": answer[:26]}),
        packet({"reasoning_details": [{"type": "reasoning.text", "text": "PRIVATE_CONTINUATION", "index": 0}],
                "content": answer[26:]}, finish="stop",
               usage={"prompt_tokens": 50, "completion_tokens": 20, "cost": .0001}),
    ]])
    loop = make_loop(store, script)
    reasoning = {"effort": "low", "exclude": False, "summary": "auto"}
    loop.model = replace(loop.model, request_config={**loop.model.request_config, "reasoning": reasoning})
    loop.factory = _AnswerOverHttp.factory(script)
    events = list(loop.run())
    assert len(requests) == 1
    # The chosen reasoning level and the whole answer allowance, with the
    # turn's tools still listed (prompt cache).
    assert requests[0]["reasoning"] == reasoning
    assert requests[0]["tools"] and requests[0]["tool_choice"] == "auto"
    assert requests[0]["max_tokens"] == max(routing_output_limit(loop.model), answer_output_limit(loop.model))
    assert loop.model.request_config["reasoning"] == reasoning
    # Reasoning fragments without a complete sentence never surface, and no
    # continuation data reaches events or the saved turn.
    assert _deltas(events) == answer
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["consensus"] == answer
    assert reviewed(saved["agent_review"], answer)
    assert "PRIVATE_" not in json.dumps(events) + json.dumps(saved, default=str)


def test_answer_step_shows_reasoning_excerpts_while_thinking_but_never_in_the_answer(store, monkeypatch):
    script = Script()
    answer = "The first option costs 100."
    requests, _, _ = transport(monkeypatch, [[
        packet({"reasoning": "Weighing the cost of both options against the budget. "}),
        packet({"reasoning": "The first option fits the stated budget exactly."}),
        packet({"content": answer}, finish="stop", usage={"prompt_tokens": 50, "completion_tokens": 20, "cost": .0001}),
    ]])
    loop = make_loop(store, script)
    loop.factory = _AnswerOverHttp.factory(script)
    events = list(loop.run())
    assert len(requests) == 1 and requests[0].get("reasoning", {}).get("exclude") is not True
    thinking = [e for e in events if e.get("kind") == "progress" and e["id"].endswith("/thinking")]
    assert thinking and "Weighing the cost of both options" in thinking[0]["text"]
    assert thinking[-1]["id"] == "completion:1/thinking"
    # The end of the step says its last word and keeps what it thought
    # (ReasoningProgress.closing, UX audit A2).
    assert thinking[-1]["text"] == "The first option fits the stated budget exactly."
    assert thinking[-1]["sections"] == [{"title": "", "text": "Weighing the cost of both options against the budget. "
                                         "The first option fits the stated budget exactly."}]
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["consensus"] == answer == _deltas(events)
    assert reviewed(saved["agent_review"], answer)
    assert any(item["id"].endswith("/thinking") for item in saved["agent_activity"])


def _thought_only():
    return [packet({"reasoning": "Still weighing every option. "}),
            # $0.03774 is 32,818 micro-euros, as many as the tokens.
            packet({}, finish="length", usage={"prompt_tokens": 50, "completion_tokens": 32768, "cost": .03774})]


def test_thought_only_answer_step_is_written_again_with_lighter_reasoning(store, monkeypatch):
    from app.services import agent_delegation
    script = Script()
    answer = "The first option costs 100."
    requests, _, _ = transport(monkeypatch, [_thought_only(), [
        packet({"content": answer}, finish="stop", usage={"prompt_tokens": 50, "completion_tokens": 20, "cost": .0001})]])
    monkeypatch.setattr(agent_delegation, "lighter_reasoning", lambda model: replace(
        model, reasoning_effort="low", request_config={**model.request_config, "reasoning": {"effort": "low", "exclude": False}}))
    loop = make_loop(store, script)
    loop.factory = _AnswerOverHttp.factory(script)
    events = list(loop.run())
    # The step after the comparison thought through its allowance; the retry
    # claims the next step with lighter reasoning and writes the answer.
    assert len(requests) == 2 and requests[1]["reasoning"]["effort"] == "low"
    assert any(e.get("kind") == "progress" and e["id"] == "completion:2/retry" for e in events)
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "completed" and saved["consensus"] == answer == _deltas(events)
    assert reviewed(saved["agent_review"], answer)
    # Both attempts are paid and counted.
    assert saved["agent_usage"]["output_tokens"] >= 32768 + 20


def test_thought_only_answer_without_lighter_reasoning_fails_as_output_limit_not_provider_error(store, monkeypatch):
    from app.services import agent_delegation
    from app.services.agent_provider_limits import ModelOutputLimit, agent_failure
    script = Script()
    requests, _, _ = transport(monkeypatch, [_thought_only()])
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
    # No answer, so nothing to review.
    assert loop.comparison.versions == []


def test_reasoning_answer_step_gets_headroom_and_a_lighter_retry_effort():
    from app.services.llm.agent_client import (
        ANSWER_OUTPUT_CEILING, ANSWER_REASONING_HEADROOM, AgentModel, lighter_reasoning)
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


def _cited_run(store, monkeypatch):
    """Both comparison answers cite a shared source without text and one of
    their own: the Exa family with search text, the native one without.
    Returns the comparison result the answer step writes from."""
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
            if _writes_answer(self.step_id, script):
                captured.append(json.loads(json.dumps(messages)))
            yield from super().stream(model=model, messages=messages, **kwargs)
            if not self.step_id.startswith("completion:"):
                own = NATIVE if model.model.startswith("anthropic") else EXA
                self.sources = [{"url": SHARED, "title": "Shared"}, {"url": own, "title": "Own"}]
                self.citations = [
                    {"url": SHARED, "content": "", "start_index": 0, "end_index": claim_end, "fallback_end_index": 0},
                    {"url": own, "content": "" if own == NATIVE else HIGHLIGHT, "start_index": 0,
                     "end_index": claim_end, "fallback_end_index": 0}]

    loop = make_loop(store, script)
    loop.factory = Completion
    list(loop.run())
    assert len(captured) == 1
    results = _comparison_results(captured[0])
    assert len(results) == 1
    return loop, results[0], fetched


def test_comparison_result_carries_what_the_cited_sources_say_without_storing_it(store, monkeypatch):
    """Comparison citations reach the agent as one pooled source list in the
    tool result: search text where the provider sent it, the page where it
    did not, bound to the sentences the answers support with them."""
    from app.services import agent_source_evidence
    loop, result, fetched = _cited_run(store, monkeypatch)
    answers = result["answers"]
    assert sorted(answer["sources"][1] for answer in answers) == [EXA, NATIVE]
    assert all(answer["sources"][0] == SHARED for answer in answers)
    sources = {source["url"]: source for source in result["sources"]}
    assert list(sources)[0] == SHARED and sources[SHARED]["cited_by"] == 2
    # No text for the shared source anywhere: listed, citable, without excerpt.
    assert "excerpt" not in sources[SHARED]
    assert "EXA_HIGHLIGHT" in sources[EXA]["excerpt"] and sources[EXA]["supports"] == ["The first option costs 100."]
    # The page is cut to the passage behind the claim and its neighbourhood.
    assert "PAGE_PASSAGE" in sources[NATIVE]["excerpt"]
    assert len(sources[NATIVE]["excerpt"]) <= agent_source_evidence.LEAD_EXCERPT_CHARS < len(PAGE)
    assert sources[NATIVE]["published"] == "2026-10-01"
    assert sorted(fetched) == sorted([SHARED, NATIVE])
    # Excerpts are context for the agent's next step: never saved with the turn.
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "completed" and reviewed(saved["agent_review"], saved["consensus"])
    serialized = json.dumps(saved, default=str)
    assert "EXA_HIGHLIGHT" not in serialized and "PAGE_PASSAGE" not in serialized
    assert '"title": "Own"' in serialized


def test_a_failing_excerpt_step_never_costs_the_paid_answer(store, monkeypatch):
    """Excerpts only enrich the comparison result: an error while pooling
    them leaves the answers with their URLs, and the turn completes."""
    from app.services import agent_source_evidence

    def broken(*args, **kwargs):
        raise RuntimeError("excerpt bug")
    monkeypatch.setattr(agent_source_evidence, "select_passages", broken)
    loop, result, _ = _cited_run(store, monkeypatch)
    assert result["sources"] == []
    assert all(answer["sources"][0] == SHARED for answer in result["answers"])
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "completed" and reviewed(saved["agent_review"], saved["consensus"])
