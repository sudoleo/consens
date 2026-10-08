"""Reasoning that outgrows its allowance, its live progress, and the turn clock.

Routing steps get reasoning headroom and one lighter retry like the answer
step; a cut tool call or a silent stop after thinking is an output limit, not
a provider error; thinking past the stored bound keeps the progress line
alive; waiting for every comparison model never eats the answer's time; a
free 429 in the answer step is retried once. No real paid model calls.
"""
from dataclasses import replace
import json
import threading

import pytest

from app.services import agent_delegation
from app.services.agent_comparison import AgentPreferences, review_is_bound
from app.services.agent_delegation import TURN_TIME_LIMIT, TURN_WRAP_UP_SECONDS
from app.services.agent_provider_limits import (
    TURN_OUTPUT_LIMIT, ModelOutputLimit, ProviderCooldowns, agent_failure,
)
from app.services.llm.agent_client import (
    ANSWER_OUTPUT_CEILING, ANSWER_REASONING_HEADROOM, REASONING_STORAGE_CHARS, ROUTING_REASONING_HEADROOM,
    AgentCompletion, AgentModel, answer_output_limit, lighter_reasoning, measured_usage, reasoning_active,
    routing_output_limit,
)
from app.services.llm.engines import _ProviderHTTPStatusError
from test_agent_chat_integrity import chat_loop
from test_agent_comparison import THREE, Script, Straggler, make_loop
from test_agent_loop import packet, transport
from test_agent_runs import UID, store  # noqa: F401  (fixture)
from test_agent_synthesis_context import _AnswerOverHttp


SONNET = AgentModel(model="anthropic/claude-sonnet-5.5", reasoning_effort="max",
                    request_config={"reasoning": {"effort": "max", "exclude": False}})


def low(model):
    return replace(model, reasoning_effort="low",
                   request_config={**model.request_config, "reasoning": {"effort": "low", "exclude": False}})


def saved(store, loop):
    return store.get_turn(UID, loop.chat_id, loop.turn_id)


# --- Headroom only where the model really reasons -------------------------

def test_routing_steps_get_reasoning_headroom_and_models_without_reasoning_get_none():
    assert routing_output_limit(SONNET) == SONNET.max_output_tokens + ROUTING_REASONING_HEADROOM
    assert answer_output_limit(SONNET) == ANSWER_OUTPUT_CEILING + ANSWER_REASONING_HEADROOM
    # Kimi K2.6 switches reasoning off in the registry; Grok 4.20 "No
    # reasoning" only reasons on request: no doubled reservation or Stop charge.
    kimi = AgentModel(model="moonshotai/kimi-k2.6", request_config={"reasoning": {"enabled": False, "exclude": False}})
    grok = AgentModel(model="x-ai/grok-4.20", selection_id="grok-4.20-non-reasoning",
                      request_config={"reasoning": {"exclude": False}})
    off = replace(SONNET, model="openai/gpt-6-luna", request_config={"reasoning": {"effort": "none"}})
    for model in (kimi, grok, off):
        assert not reasoning_active(model)
        assert answer_output_limit(model) == ANSWER_OUTPUT_CEILING
        assert routing_output_limit(model) == model.max_output_tokens
    assert reasoning_active(replace(grok, request_config={"reasoning": {"effort": "high"}}))


def test_lighter_reasoning_is_never_heavier_than_the_current_level():
    luna = replace(SONNET, model="openai/gpt-6-luna", selection_id="gpt-6-luna")
    assert lighter_reasoning(replace(luna, request_config={"reasoning": {"effort": "max"}})).reasoning_effort == "low"
    # "low" comes first on purpose, but never as a step up from "minimal".
    assert lighter_reasoning(replace(luna, request_config={"reasoning": {"effort": "low"}})).reasoning_effort == "none"
    assert lighter_reasoning(replace(luna, request_config={"reasoning": {"effort": "none"}})) is None
    assert lighter_reasoning(low(SONNET)) is None


# --- The client names an output limit as such ----------------------------

def _stream(monkeypatch, packets, *, tools=None):
    transport(monkeypatch, [packets])
    value = AgentCompletion()
    value.tool_call_limit = 4
    events = []
    source = value.stream(model=SONNET, messages=[{"role": "user", "content": "Plan"}], api_key="test",
                          tools=tools, allow_tool_calls=bool(tools))
    try:
        for event in source:
            events.append(event)
    except Exception as exc:
        return value, events, exc
    return value, events, None


TOOL = [{"type": "function", "function": {"name": "compare_models", "parameters": {"type": "object"}}}]


def test_a_tool_call_cut_at_the_token_limit_is_an_output_limit_not_a_provider_error(monkeypatch):
    value, _, error = _stream(monkeypatch, [
        packet({"reasoning": "Phrasing the comparison carefully. "}),
        packet({"tool_calls": [{"index": 0, "id": "call_1", "type": "function",
                                "function": {"name": "compare_models", "arguments": '{"question": "Which'}}]}),
        packet({}, finish="length", usage={"prompt_tokens": 50, "completion_tokens": 16384})], tools=TOOL)
    assert isinstance(error, ModelOutputLimit) and value.output_limited
    assert agent_failure(error)["code"] == "output_limit"


@pytest.mark.parametrize("finish", ["stop", None])
def test_a_model_that_thought_and_stopped_without_writing_is_an_output_limit(monkeypatch, finish):
    value, _, error = _stream(monkeypatch, [
        packet({"reasoning": "Still weighing every option. "}),
        packet({}, finish=finish, usage={"prompt_tokens": 50, "completion_tokens": 900,
                                         "completion_tokens_details": {"reasoning_tokens": 900}})])
    assert isinstance(error, ModelOutputLimit) and value.output_limited


def test_an_empty_stop_without_any_reasoning_stays_a_provider_error(monkeypatch):
    value, _, error = _stream(monkeypatch, [packet({}, finish="stop", usage={"prompt_tokens": 50, "completion_tokens": 0})])
    assert type(error) is RuntimeError and not value.output_limited
    assert agent_failure(error)["code"] == "provider_error"


def test_reasoning_past_the_stored_bound_still_streams_but_is_not_stored(monkeypatch):
    chunk = "Checking the next source against the claim. " * 50
    count = REASONING_STORAGE_CHARS // len(chunk) + 10
    value, events, error = _stream(monkeypatch, [
        *[packet({"reasoning": chunk}) for _ in range(count)],
        packet({"content": "Answer."}, finish="stop", usage={"prompt_tokens": 50, "completion_tokens": 20})])
    assert error is None and value.text == "Answer."
    reasoning = [e for e in events if e.get("kind") == "reasoning"]
    # Every delta reaches live progress ...
    assert sum(len(e["text"]) for e in reasoning) == count * len(chunk)
    assert any(e.get("transient") for e in reasoning)
    # ... but storage keeps its bound.
    stored = sum(len(item.get("text", "")) for item in value.activity if item["kind"] == "reasoning")
    assert stored == value.reasoning_chars == REASONING_STORAGE_CHARS and value.reasoning_truncated


def test_answer_step_thinking_excerpts_keep_updating_past_the_stored_bound(store, monkeypatch):
    monkeypatch.setattr(agent_delegation, "THINKING_UPDATE_SECONDS", 0)
    chunk = "Some filler about weighing evidence and costs carefully. " * 20
    late = REASONING_STORAGE_CHARS // len(chunk) + 5
    packets = [packet({"reasoning": f"\n\nThought number {i} checks one more source. " + chunk}) for i in range(late + 3)]
    transport(monkeypatch, [[*packets, packet({"content": "The first option costs 100."}, finish="stop",
                                              usage={"prompt_tokens": 50, "completion_tokens": 20, "cost": .0001})]])
    script = Script()
    loop = make_loop(store, script)
    loop.factory = _AnswerOverHttp.factory(script)
    events = list(loop.run())
    thinking = [e for e in events if e.get("kind") == "progress" and e["id"].endswith("/thinking")]
    # Previously the line froze at 32,000 characters while the model kept thinking.
    assert any(f"Thought number {late + 2}" in e["text"] for e in thinking)
    assert saved(store, loop)["consensus"] == "The first option costs 100."


# --- Routing steps: one lighter retry instead of a failed turn ------------

class ThoughtOutRouting(Script):
    """The first routing request(s) reason through their allowance."""

    def __init__(self, *, failures=1, partial_tool=False, **kwargs):
        super().__init__(direct=True, **kwargs)
        self.failures, self.partial_tool = failures, partial_tool
        self.routing = []

    def factory(self):
        base = type(super().factory())
        script = self

        class Completion(base):
            def stream(self, *, model, messages, **kwargs):
                if self.step_id.startswith("completion:") and kwargs["tools"]:
                    script.routing.append((self.step_id, model.reasoning_effort, model.max_output_tokens))
                    if len(script.routing) <= script.failures:
                        script.calls.append((self.step_id, model.model))
                        self.usage = measured_usage({"prompt_tokens": 50, "completion_tokens": model.max_output_tokens,
                                                     "cost": .001}, model)
                        self.finish_reason = "length"
                        # The client marks this as an output limit and raises.
                        self.output_limited = True
                        raise ModelOutputLimit()
                    # Later routing steps answer like before, from their own index.
                    self.step_id = f"completion:{len(script.routing) - 1 - script.failures}"
                    try:
                        yield from super().stream(model=model, messages=messages, **kwargs)
                    finally:
                        self.step_id = script.routing[-1][0]
                    return
                yield from super().stream(model=model, messages=messages, **kwargs)
        return Completion


def _routing_loop(store, script, monkeypatch, lighter=low):
    monkeypatch.setattr(agent_delegation, "lighter_reasoning", lambda model: lighter(model) if lighter else None)
    loop = make_loop(store, script)
    loop.factory = script.factory()
    return loop


def test_thought_out_routing_step_is_retried_once_with_lighter_reasoning(store, monkeypatch):
    script = ThoughtOutRouting()
    loop = _routing_loop(store, script, monkeypatch)
    events = list(loop.run())
    turn = saved(store, loop)
    assert turn["status"] == "completed" and review_is_bound(turn["agent_review"], turn["consensus"])
    first, retry = script.routing[:2]
    # Headroom on top of the text allowance; the retry claims its own step.
    assert first[0] == "completion:0" and retry == ("completion:1", "low", first[2])
    assert first[2] == routing_output_limit(loop.model) >= loop.model.max_output_tokens
    assert any(e.get("kind") == "progress" and e["id"] == "completion:1/retry" for e in events)
    # The thought-out step is paid and settled; the answer keeps the chosen level.
    assert turn["agent_usage"]["output_tokens"] >= first[2]
    assert loop.routing_lighter.reasoning_effort == "low"
    assert loop.model.reasoning_effort != "low"


def test_routing_without_a_lighter_level_ends_as_output_limit_with_advice(store, monkeypatch):
    script = ThoughtOutRouting()
    loop = _routing_loop(store, script, monkeypatch, lighter=None)
    with pytest.raises(ModelOutputLimit):
        list(loop.run())
    failure = saved(store, loop)["agent_failure"]
    assert failure == {"code": "output_limit", "error": TURN_OUTPUT_LIMIT}
    assert "lower reasoning level" in failure["error"]
    assert len(script.routing) == 1


def test_routing_that_thinks_out_twice_ends_as_output_limit_not_provider_error(store, monkeypatch):
    script = ThoughtOutRouting(failures=2)
    loop = _routing_loop(store, script, monkeypatch)
    with pytest.raises(ModelOutputLimit):
        list(loop.run())
    assert saved(store, loop)["agent_failure"]["code"] == "output_limit"
    assert [step for step, *_ in script.routing] == ["completion:0", "completion:1"]


# --- A free 429 in the answer step: one short retry ------------------------

def _answer_with(monkeypatch, store, first, *, retry_seconds=0):
    monkeypatch.setattr(agent_delegation, "RATE_LIMIT_RETRY_SECONDS", retry_seconds)
    answer = "The first option costs 100."
    requests, _, _ = transport(monkeypatch, [[first], [
        packet({"content": answer}, finish="stop", usage={"prompt_tokens": 50, "completion_tokens": 20, "cost": .0001})]])
    script = Script()
    loop = make_loop(store, script)
    loop.factory = _AnswerOverHttp.factory(script)
    loop.cooldowns = ProviderCooldowns()  # never the process-wide gate in tests
    return loop, requests, answer


def test_rate_limited_answer_step_is_retried_once_and_the_429_costs_nothing(store, monkeypatch):
    loop, requests, answer = _answer_with(monkeypatch, store, _ProviderHTTPStatusError(429, retry_after=1))
    monkeypatch.setattr(agent_delegation.DelegationLoop, "_pause", lambda self, seconds: iter(()))
    events = list(loop.run())
    turn = saved(store, loop)
    assert len(requests) == 2 and turn["status"] == "completed" and turn["consensus"] == answer
    assert review_is_bound(turn["agent_review"], answer)
    assert any(e.get("kind") == "progress" and e["id"].endswith("/rate_limit") for e in events)
    rejected = [usage for usage in loop.costs.usages if usage and usage.get("source") == "provider_rejection"]
    assert len(rejected) == 1 and rejected[0]["estimated_cost_nano_usd"] == 0


def test_answer_step_honours_a_long_retry_after_instead_of_retrying(store, monkeypatch):
    loop, requests, _ = _answer_with(monkeypatch, store, _ProviderHTTPStatusError(429, retry_after=30))
    with pytest.raises(_ProviderHTTPStatusError):
        list(loop.run())
    assert len(requests) == 1
    assert saved(store, loop)["agent_failure"]["code"] == "provider_rate_limited"


def test_rate_limit_retry_respects_the_turn_deadline_and_stops(store):
    loop = chat_loop(store, Script())
    now = [loop.turn_started]
    loop.clock = lambda: now[0]
    assert loop._rate_limit_delay(None) == agent_delegation.RATE_LIMIT_RETRY_SECONDS
    assert loop._rate_limit_delay(4) == 4 and loop._rate_limit_delay(11) is None
    now[0] += loop.policy.turn_seconds + TURN_WRAP_UP_SECONDS - 30
    assert loop._rate_limit_delay(1) is None
    loop.cancellation.cancel()
    with pytest.raises(Exception):
        list(loop._pause(5))


# --- "Answer start: all" leaves the answer its time -----------------------

def test_answer_reserve_follows_the_reasoning_level_and_moves_the_soft_limit(store):
    loop = chat_loop(store, Script())
    loop.model = SONNET
    assert loop._answer_reserve() == agent_delegation.ANSWER_RESERVE_SECONDS["max"]
    hard = loop.policy.turn_seconds + TURN_WRAP_UP_SECONDS
    now = [loop.turn_started + hard - loop._answer_reserve() - 1]
    loop.clock = lambda: now[0]
    assert loop._turn_limit() is None and loop.answer_time_left() == 1
    now[0] += 1
    # A "max" answer and its checks would no longer fit before the hard stop.
    assert loop._turn_limit() == TURN_TIME_LIMIT
    loop.model = low(SONNET)
    assert loop._answer_reserve() < agent_delegation.ANSWER_RESERVE_SECONDS["max"]
    assert make_loop(store, Script()).answer_time_left() is None  # bounded runs


def test_waiting_for_every_model_stops_when_only_the_answer_time_is_left(store):
    script = Straggler(release_on_answer=False)
    loop = chat_loop(store, script, models=THREE, preferences=AgentPreferences(quorum="all"))
    hard = loop.policy.turn_seconds + TURN_WRAP_UP_SECONDS
    # Once a comparison runs, the turn is just past the answer's reserve
    # (before the soft limit and well before the hard stop).
    late = hard - loop._answer_reserve() + 1
    assert late < loop.policy.turn_seconds
    loop.clock = lambda: loop.turn_started + (late if loop.comparison.comparisons else 0)
    # Without the deadline the straggler would only end the wait here, and
    # then show up in the synthesis below.
    timer = threading.Timer(5, script.release.set)
    timer.start()
    try:
        list(loop.run())
    finally:
        timer.cancel()
        script.release.set()
    turn = saved(store, loop)
    comparison = turn["agent_review"]["comparisons"][0]
    assert turn["status"] == "completed" and review_is_bound(turn["agent_review"], turn["consensus"])
    assert sorted(comparison["synthesis_providers"]) == ["anthropic", "openai"]
    assert "second option is cheaper" not in script.synthesis_evidence
    assert [m["failure"]["code"] for m in comparison["failed_models"]] == ["late_cutoff"]
