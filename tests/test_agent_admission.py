"""Budget-pressure regressions through real admission/receipts, without paid APIs."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
import threading

import pytest

from app.services import agent_quota
from app.services.agent_costs import input_bound
from app.services.agent_tokens import input_estimate
from app.services.agent_policy import AgentPolicy
from app.services.agent_tools import ToolRegistry
from app.services.llm.agent_client import AgentCompletion, measured_usage
from app.services.llm.provider_runtime import AnalysisBudget, AnalysisBudgetExceeded, ProviderCancelled
from test_agent_runs import UID, store, totals
from test_agent_continuation import chat_loop
from test_agent_comparison import Script, make_loop


class Completion(AgentCompletion):
    def stream(self, *, model, **kwargs):
        self.text, self.finish_reason = "Available answer.", "stop"
        self.usage = measured_usage({"prompt_tokens": 120, "completion_tokens": 30}, model)
        yield {"type": "delta", "text": self.text}


def quota(store, remaining):
    ref = agent_quota.quota_ref(store.db, UID, agent_quota.day_key())
    ref.set({"used": 250000 - remaining})
    return ref


def exhaust(generator):
    while True:
        try:
            next(generator)
        except StopIteration as done:
            return done.value


def root(loop):
    args = UID, loop.chat_id, loop.turn_id
    assert loop.store.claim(*args, loop.model, policy=loop.policy.snapshot(), run_token=loop.run_token, reservation=(1, 1))
    value = AgentCompletion()
    value.usage = measured_usage({"prompt_tokens": 0, "completion_tokens": 0}, loop.model)
    loop.store.settle(*args, completion=value, status="succeeded", final=False)
    loop.claimed = True


def test_screenshot_sized_prompt_fits_20933_tokens_without_byte_reservation(store):
    observed = []
    class Capture(Completion):
        def stream(self, **kwargs):
            observed.append(kwargs)
            yield from super().stream(**kwargs)
    loop = chat_loop(store, Capture)
    loop.messages.append({"role": "user", "content": "Vergleiche die Ergebnisse und belege die Unsicherheit. " * 400})
    old = input_bound(loop.messages, loop.registry.schemas) + loop.model.max_output_tokens
    assert old > 26283
    ref = quota(store, 20933)
    list(loop.run())
    assert len(observed) == 1 and observed[0]["native_searches"] == 0
    assert ref.get().to_dict()["reserved"] == 0
    assert ref.get().to_dict()["used"] == 250000 - 20933 + 150
    assert store.get_turn(UID, loop.chat_id, loop.turn_id)["status"] == "completed"


@pytest.mark.parametrize("text", ["Deutsche Umlaute: Größe und äußere Ähnlichkeit. ", "中文问题与回答。", "🚵🏽‍♀️⚡", "<|endoftext|>"])
def test_offline_counting_accepts_unicode_and_special_token_literals(text, monkeypatch):
    import socket
    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: pytest.fail("Tokenizer must stay offline"))
    from app.services.agent_tokens import encoding
    encoding.cache_clear()
    messages = [{"role": "user", "content": text * 100}]
    count = input_estimate(messages)
    assert 256 < count < input_bound(messages) + 512
    assert input_estimate(messages, request_config={"response_format": {"schema": text * 500}}) > count


def test_small_remaining_budget_sets_provider_and_receipt_output_cap(store):
    observed = []
    class Capture(Completion):
        def stream(self, **kwargs):
            observed.append(kwargs["model"])
            yield from super().stream(**kwargs)
    loop = chat_loop(store, Capture)
    inputs = input_estimate(loop.messages, loop.registry.schemas, loop.model.request_config)
    # Include the small notice added when optional search is unavailable.
    ref = quota(store, inputs + 900)
    list(loop.run())
    assert len(observed) == 1 and 256 <= observed[0].max_output_tokens < 1000
    saved = store.receipt_ref(UID, loop.chat_id, loop.turn_id).get().to_dict()
    assert saved["model"]["max_output_tokens"] == observed[0].max_output_tokens
    assert saved["quota_reserved"] <= inputs + 900
    assert ref.get().to_dict()["reserved"] == 0
    assert totals(store)["calls"] == loop.costs.calls == 1


def test_bounded_search_does_not_reserve_its_results_before_the_search(store):
    observed = []
    class Capture(Completion):
        def stream(self, **kwargs):
            observed.append(kwargs["native_searches"])
            yield from super().stream(**kwargs)
    loop = chat_loop(store, Capture)
    quota(store, 45000)
    list(loop.run())
    assert observed == [1]


@pytest.mark.parametrize("cancel", [False, True])
def test_parallel_comparison_waits_for_receipt_instead_of_failing_or_shrinking(store, cancel):
    entered, finish, waiting = threading.Event(), threading.Event(), threading.Event()
    calls, caps = [], []
    class Slow(Completion):
        def stream(self, **kwargs):
            calls.append(self.step_id)
            caps.append(kwargs["model"].max_output_tokens)
            if len(calls) == 1:
                entered.set()
                assert finish.wait(5)
            yield from super().stream(**kwargs)
    loop = make_loop(store, Script())
    loop.policy = AgentPolicy.for_chat(loop.config)
    loop.costs.policy, loop.budget, loop.factory = loop.policy, AnalysisBudget(unlimited=True), Slow
    root(loop)
    model = next(iter(loop.comparison.models.values()))
    messages = [{"role": "system", "content": "Answer"}, {"role": "user", "content": "Which option?"}]
    bound = loop.costs.estimate(model, messages)[0]
    ref = quota(store, bound + 300)
    original = loop._state
    def state(worker, status, **patch):
        result = original(worker, status, **patch)
        if status == "waiting":
            waiting.set()
        return result
    loop._state = state
    def call():
        return loop.comparison.call(model, messages, title="Compare", kind="comparison")
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(call)
        assert entered.wait(5)
        second = pool.submit(call)
        try:
            assert waiting.wait(5)
            assert len(calls) == 1
            if cancel:
                loop.cancellation.cancel()
        finally:
            finish.set()
        if cancel:
            for future in (first, second):
                with pytest.raises(ProviderCancelled):
                    future.result(timeout=5)
        else:
            assert first.result(timeout=5).text == second.result(timeout=5).text
            assert caps == [model.max_output_tokens] * 2
    assert len(calls) == (1 if cancel else 2)
    assert ref.get().to_dict()["reserved"] == 0
    assert loop.costs.calls == totals(store)["calls"] - 1


def test_truly_exhausted_budget_does_not_dispatch_or_leak_local_reservation(store):
    loop = chat_loop(store, Completion)
    ref = quota(store, 100)
    with pytest.raises(agent_quota.AgentTokenBudgetExceeded):
        list(loop.run())
    assert loop.costs.calls == loop.costs.tokens == 0
    assert ref.get().to_dict() == {"used": 249900}


def test_output_limit_preserves_partial_answer_without_claiming_completion(store):
    class Truncated(Completion):
        def stream(self, **kwargs):
            yield from super().stream(**kwargs)
            self.finish_reason = "length"
    loop = chat_loop(store, Truncated)
    with pytest.raises(AnalysisBudgetExceeded, match="output token limit"):
        list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "failed" and saved["consensus"] == "Available answer."
    assert agent_quota.snapshot(store.db, UID)["reserved"] == 0


def test_context_window_can_fit_reduced_output_without_losing_messages(store):
    loop = chat_loop(store, Completion)
    inputs = input_estimate(loop.messages)
    model = replace(loop.model, context_length=inputs + 600)
    value = exhaust(loop._step(model, loop.messages, "completion:0", ToolRegistry(), loop.cancellation, searches_enabled=False))
    assert value.text == "Available answer."
    saved = store.receipt_ref(UID, loop.chat_id, loop.turn_id).get().to_dict()
    assert saved["model"]["max_output_tokens"] == 600


def test_explicit_reasoning_budget_is_not_shrunk_below_provider_minimum(store):
    loop = chat_loop(store, Completion)
    model = replace(loop.model, request_config={"reasoning": {"max_tokens": 1024}})
    inputs = input_estimate(loop.messages)
    quota(store, inputs + 1100)
    with pytest.raises(agent_quota.AgentTokenBudgetExceeded):
        exhaust(loop._step(model, loop.messages, "completion:0", ToolRegistry(), loop.cancellation, searches_enabled=False))
    assert loop.costs.calls == 0


def test_consensus_default_overrides_legacy_prompt_and_disabled_workers_are_not_advertised(store):
    script = Script()
    loop = make_loop(store, script)
    system = loop.messages[0]["content"]
    assert "consens.io Agent Beta" in system and "pipeline by default" in system
    assert "Web search may first clarify" in system and "pure rewriting/translation" in system
    assert "Available worker models" not in system
    list(loop.run())
    assert all("consens.io's Consensus pipeline" in messages[0]["content"] for messages in script.prompts)


def test_server_search_final_answer_resumes_consensus_without_repeating_search(store):
    script = Script()
    base = type(script.factory())
    root_calls = []
    class Researched(base):
        def stream(self, *, model, messages, **kwargs):
            if self.step_id.startswith('completion:'):
                root_calls.append(kwargs['native_searches'])
            if self.step_id == 'completion:0':
                self.text, self.finish_reason = 'Research findings.', 'stop'
                self.sources = [{'url': 'https://example.org/current', 'title': 'Current evidence'}]
                self.usage = measured_usage({'prompt_tokens': 100, 'completion_tokens': 20}, model)
                yield {'type': 'delta', 'text': self.text}
                return
            if self.step_id == 'completion:1':
                assert kwargs['native_searches'] == 0
                assert 'https://example.org/current' in messages[-1]['content']
                self.usage = measured_usage({'prompt_tokens': 100, 'completion_tokens': 20}, model)
                self.tool_calls = [{'id': 'compare', 'type': 'function', 'function': {'name': 'compare_models',
                    'arguments': json.dumps({'question': 'Evaluate option', 'context': 'Research findings. https://example.org/current', 'reason': 'Answer the question'})}}]
                self.finish_reason = 'tool_calls'
                return
            yield from super().stream(model=model, messages=messages, **kwargs)
    loop = make_loop(store, script)
    loop.policy = AgentPolicy.for_chat(loop.config)
    loop.costs.policy, loop.budget, loop.factory = loop.policy, AnalysisBudget(unlimited=True), Researched
    list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert root_calls == [1, 0, 1]
    assert saved['status'] == 'completed' and saved['agent_review']['status'] == 'succeeded'
    assert saved['consensus'] != 'Research findings.'
    assert agent_quota.snapshot(store.db, UID)['reserved'] == 0
