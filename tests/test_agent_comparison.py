"""Paid-step accounting and exact-version review through the real shared judges."""
from dataclasses import replace
import json
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.services import agent_quota, agent_budget_config
from app.services.agent_comparison import AgentPreferences, comparison_selection, review_is_bound, review_issues
from app.services.agent_delegation import DelegationLoop
from app.services.agent_delegation_config import defaults
from app.services.agent_policy import AgentPolicy
from app.services.llm.agent_client import AgentCompletion, measured_usage, metered_model, resolve_agent_model
from app.services.llm.provider_runtime import ProviderCancellation, ProviderCancelled, AnalysisBudgetExceeded
from test_agent_runs import UID, AUTH, api, pending, receipt, store


class Script:
    def __init__(self, *, compares=1, revise=False, missing=False, fail_coverage=False, fail_model=False, length_model=None,
                 direct=False, depth=None, pick=None):
        self.length_model = length_model
        self.pick = pick
        self.direct, self.depth = direct, depth
        self.compares, self.revise, self.missing = compares, revise, missing
        self.fail_coverage, self.fail_model = fail_coverage, fail_model
        self.calls, self.prompts = [], []
        self.loop = None

    def factory(self):
        script = self
        class Completion(AgentCompletion):
            def stream(self, *, model, messages, **kwargs):
                script.calls.append((self.step_id, model.model))
                self.usage = measured_usage({"prompt_tokens": 50, "completion_tokens": 20, "cost": .0001,
                    "prompt_tokens_details": {"cached_tokens": 20}, "completion_tokens_details": {"reasoning_tokens": 10}}, model)
                if self.step_id.startswith("completion:"):
                    if not kwargs["tools"]:
                        self.text, self.finish_reason = "The first option costs 100.", "stop"
                        yield {"type": "delta", "text": self.text}
                        return
                    index = int(self.step_id.split(":")[-1])
                    if index < script.compares:
                        if script.compares > 1:
                            self.text = f"I will compare perspective {index + 1}."
                            yield {"type": "delta", "text": self.text}
                        args = {"question": f"Evaluate option {index + 1}", "context": "Budget is 100. Source: https://example.org/report", "reason": "Compare trade-offs",
                                "next_step": "answer" if script.direct and index == script.compares - 1 else "more_work",
                                **({"depth": script.depth} if script.depth else {}),
                                **({"models": script.pick} if script.pick is not None else {})}
                        action = "compare_models"
                    else:
                        self.text = "The first option costs 100."
                        if script.revise and index > script.compares:
                            self.text = "The first option costs 100. The constraint matters."
                        yield {"type": "delta", "text": self.text}
                        if script.missing:
                            self.finish_reason = "stop"
                            return
                        action, args = "judge_answer", {"finalize": not script.revise or index > script.compares}
                    self.tool_calls = [{"id": f"call_{index}", "type": "function", "function": {"name": action, "arguments": json.dumps(args)}}]
                    self.finish_reason = "tool_calls"
                    return
                schema = (model.request_config.get("response_format") or {}).get("json_schema", {}).get("schema")
                if schema:
                    if "sentences" in schema["properties"]:
                        if script.fail_coverage:
                            raise RuntimeError("Coverage unavailable")
                        properties = schema["properties"]["sentences"]["items"]["properties"]
                        self.text = json.dumps({"sentences": [{"id": key, "classification": "claim", "models": {name: "supports" for name in properties["models"]["properties"]}, "counter_quotes": []} for key in properties["id"]["enum"]]})
                    else:
                        self.text = json.dumps({"differences": [], "best_model": "Model A"})
                else:
                    script.prompts.append(messages)
                    if script.fail_model and model.model.startswith("anthropic"):
                        raise RuntimeError("Comparison unavailable")
                    self.text = "The first option costs 100. The constraint matters."
                    if script.length_model is not None and model.model.startswith("openai"):
                        self.text, self.finish_reason = script.length_model, "length"
                        if self.text:
                            yield {"type": "delta", "text": self.text}
                        return
                self.finish_reason = "stop"
                yield {"type": "delta", "text": self.text}
        return Completion()


def make_loop(store, script, *, check_sources=False, source_limits=None, messages=None, delegation=False, models=None,
              preferences=None):
    chat, turn = pending(store)
    config = {**defaults(), "enabled": delegation, "max_searches": 0, "context_chars": 120_000}
    loop = DelegationLoop(store=store, uid=UID, chat_id=chat, turn_id=turn["id"],
        model=resolve_agent_model("claude-haiku-4-5"), messages=messages or [{"role": "system", "content": "Answer."}, {"role": "user", "content": "Compare options"}],
        api_key="test", cancellation=ProviderCancellation(), policy=AgentPolicy.from_config({**config, "enabled": True}),
        delegation_config=config, completion_factory=script.factory,
        check_sources=check_sources, source_limits=source_limits,
        comparison_models=comparison_selection(models or {"anthropic": "claude-haiku-4-5", "openai": "gpt-5.4-mini"}),
        agent_preferences=preferences)
    script.loop = loop
    return loop


@pytest.mark.parametrize("compares,revise", [(1, False), (2, False), (1, True)])
def test_real_judges_exact_versions_context_sources_and_all_usage(store, compares, revise):
    script = Script(compares=compares, revise=revise)
    loop = make_loop(store, script)
    events = list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    review = saved["agent_review"]
    assert saved["status"] == "completed"
    assert review["status"] == "succeeded"
    assert len(review["versions"]) == 1
    assert saved["consensus"] == review["versions"][-1]["text"]
    assert len(review["checks"]) == compares
    assert review_is_bound(review, saved["consensus"])
    assert not review_is_bound(review, saved["consensus"] + "changed")
    assert all(c["differences_data"]["judges"]["differences"]["provider"] != "Claude" for c in review["checks"])
    assert all(c["answer_hash"] == review["answer_hash"] for c in review["checks"])
    for i in range(compares):
        assert script.prompts[2 * i] == script.prompts[2 * i + 1]
        assert "https://example.org/report" in script.prompts[2 * i][1]["content"]
        assert "first option costs" not in script.prompts[2 * i][1]["content"]
    usage = saved["agent_usage"]
    assert usage["input_tokens"] + usage["output_tokens"] == len(script.calls) * 70
    quota = agent_quota.quota_ref(store.db, UID, agent_quota.day_key()).get().to_dict()
    assert quota["used"] == len(script.calls) * 70 and quota["reserved"] == 0
    assert any(e["type"] == "review" and e["review"]["status"] == "running" for e in events)
    tools = [e for e in events if e.get("kind") == "tool" and e.get("name") == "compare_models"]
    assert [e["status"] for e in tools] == [s for _ in range(compares) for s in ("running", "succeeded")]
    assert sum(e["type"] == "delta" for e in events) == 1
    assert len([step for step, _ in script.calls if step.startswith('completion:')]) == compares + 2
    assert all("I will compare" not in v["text"] for v in review["versions"])
    assert store.delegation_view(UID, loop.chat_id, loop.turn_id)["agents"]


@pytest.mark.parametrize('account_budget_only', [False, True])
def test_fixed_answer_cannot_be_reopened_by_false_finalize_or_late_comparison(store, account_budget_only):
    from app.services.agent_comparison import CompareArgs, JudgeArgs
    script = Script(revise=True)
    loop = make_loop(store, script)
    loop.policy = replace(loop.policy, account_budget_only=account_budget_only)
    events = list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved['consensus'] == 'The first option costs 100.'
    assert len([step for step, _ in script.calls if step.startswith('completion:')]) == 3
    original = json.dumps(loop.comparison.snapshot(), sort_keys=True)
    loop.comparison.capture('A rewritten answer must never replace the checked one.')
    result = loop.comparison.judge(JudgeArgs(finalize=False), cancellation=loop.cancellation)
    assert result['finalized'] is True
    with pytest.raises(ValueError, match='synthesis is already fixed'):
        loop.comparison.compare(CompareArgs(question='Compare again?', context='', reason='Retry', next_step='answer'),
                                cancellation=loop.cancellation)
    assert json.dumps(loop.comparison.snapshot(), sort_keys=True) == original
    assert review_is_bound(saved['agent_review'], saved['consensus'])
    first_answer = next(i for i, e in enumerate(events) if e['type'] == 'delta')
    assert not any(e.get('clear_response') for e in events[first_answer + 1:])


@pytest.mark.parametrize("failure,expected", [("fail_coverage", "partial"), ("fail_model", "failed")])
def test_partial_or_failed_checks_never_certify_success(store, failure, expected):
    script = Script(**{failure: True})
    loop = make_loop(store, script)
    list(loop.run())
    review = store.get_turn(UID, loop.chat_id, loop.turn_id)["agent_review"]
    assert review["status"] == expected
    issues = review['checks'][0]['issues']
    expected_issue = 'coverage_unavailable' if failure == 'fail_coverage' else 'insufficient_answers'
    assert {'code': expected_issue} in issues


def test_rate_limited_answer_is_distinct_from_successful_judges(store):
    from app.services.agent_provider_limits import AgentProviderCooldown
    script = Script()
    loop = make_loop(store, script)
    loop.comparison.models = comparison_selection({'anthropic': 'claude-haiku-4-5', 'openai': 'gpt-5.4-mini',
                                                  'gemini': 'gemini-3.5-flash-lite'})
    original = loop.comparison.call
    def call(model, messages, **kwargs):
        if kwargs['kind'] == 'comparison' and model.model.startswith('openai/'):
            raise AgentProviderCooldown(30)
        return original(model, messages, **kwargs)
    loop.comparison.call = call
    list(loop.run())
    review = store.get_turn(UID, loop.chat_id, loop.turn_id)['agent_review']
    assert review['status'] == 'partial'
    assert review['checks'][0]['issues'] == [{'code': 'models_unavailable', 'count': 1}]
    assert review['comparisons'][0]['failed_models'][0]['failure']['code'] == 'provider_rate_limited'
    assert len(review['comparisons'][0]['answers']) == 2
    assert review_is_bound(review, loop.comparison.text)


def test_review_binding_survives_saved_turn_projection_without_normalizing_text(store):
    script = Script()
    base = type(script.factory())
    text = "\n**The ﬁrst option** costs 100\u00a0€.\n\n"

    class ExactText(base):
        def stream(self, **kwargs):
            events = list(super().stream(**kwargs))
            if self.step_id == "completion:2":
                self.text = text
                yield {"type": "delta", "text": text}
            else:
                yield from events

    loop = make_loop(store, script)
    loop.factory = ExactText
    list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    history = store.list_turn_details(UID, loop.chat_id)["turns"][0]
    for projected in (saved, history):
        assert projected["status"] == "completed"
        assert projected["consensus"] == projected["assistant_response"] == text
        assert review_is_bound(projected["agent_review"], projected["consensus"])


@pytest.mark.parametrize('data,codes', [
    ({'judges': {'differences': {}, 'coverage': {}}}, ['differences_unavailable', 'coverage_unavailable']),
    ({'judges': {'differences': {'provider': 'Gemini'}, 'coverage': {'missing': 2}},
      'evidence_coverage': {'unindexed_sentences': 3, 'truncated_answers': 1}},
     ['sentences_unchecked', 'unindexed_sentences', 'truncated_answers']),
])
def test_review_issues_explain_each_missing_check(data, codes):
    issues = review_issues({'answers': [{}, {}]}, data)
    assert [issue['code'] for issue in issues] == codes


def test_missing_tool_uses_existing_review_and_persists_checked_answer(store):
    script = Script(missing=True)
    loop = make_loop(store, script)
    list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "completed"
    assert saved["agent_review"]["status"] == "succeeded"
    assert saved["consensus"] == "The first option costs 100."
    assert len(script.calls) == 7  # Three root steps, two comparisons, two judges.


def test_atomic_daily_budget_and_duplicate_settlement(store, monkeypatch):
    monkeypatch.setitem(agent_budget_config.DEFAULT_TIER_LIMITS, "pro", 100)
    loops = [make_loop(store, Script()) for _ in range(2)]
    def claim(loop):
        try:
            return store.claim(UID, loop.chat_id, loop.turn_id, loop.model, run_token=loop.run_token,
                policy=loop.policy.snapshot(), reservation=(60, 100))
        except AnalysisBudgetExceeded:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(claim, loops))
    assert sum(claims) == 1
    loop = loops[claims.index(True)]
    value = receipt()
    value.usage = measured_usage({"prompt_tokens": 10, "completion_tokens": 5,
        "prompt_tokens_details": {"cached_tokens": 5}, "completion_tokens_details": {"reasoning_tokens": 5}}, loop.model)
    for _ in range(2):
        store.settle(UID, loop.chat_id, loop.turn_id, completion=value, status="cancelled", final=False)
    quota = agent_quota.quota_ref(store.db, UID, agent_quota.day_key()).get().to_dict()
    assert quota["used"] == 15 and quota["reserved"] == 0


@pytest.mark.parametrize("remaining", [0, 40000])
def test_quota_rejection_distinguishes_empty_from_insufficient_reservation(remaining):
    data = {"used": 250000 - remaining}
    with pytest.raises(agent_quota.AgentTokenBudgetExceeded) as error:
        agent_quota.reserve(data, 50000)
    assert error.value.remaining == remaining and error.value.required == 50000
    assert error.value.code == ("agent_token_reservation" if remaining else "agent_tokens_exhausted")
    if remaining:
        assert 'Completed calls release their reservations' in str(error.value)
    assert "reserved" not in data


def test_admin_budget_is_enforced_and_reset_isolated_from_inflight_settlement(store):
    config = agent_budget_config.store(store.db)
    config.save(expected_revision=0, updated_by='admin', tier_limits={'pro': 2000})
    loop = make_loop(store, Script())
    params = dict(run_token=loop.run_token, policy=loop.policy.snapshot())
    with pytest.raises(agent_quota.AgentTokenBudgetExceeded):
        store.claim(UID, loop.chat_id, loop.turn_id, loop.model, reservation=(2001, 100), **params)
    assert store.claim(UID, loop.chat_id, loop.turn_id, loop.model, reservation=(1500, 100), **params)
    store.protect_review(UID, loop.chat_id, loop.turn_id, loop.run_token, 400)
    assert agent_quota.snapshot(store.db, UID)['remaining'] == 100
    config.save(expected_revision=1, updated_by='admin', reset=True)
    assert agent_quota.snapshot(store.db, UID)['remaining'] == 2000
    store.settle(UID, loop.chat_id, loop.turn_id, completion=receipt(), status='succeeded', final=False)
    assert agent_quota.snapshot(store.db, UID)['used'] == 0
    # Review holds move once to the fresh generation before further work.
    store.protect_review(UID, loop.chat_id, loop.turn_id, loop.run_token, 600)
    assert agent_quota.snapshot(store.db, UID)['reserved'] == 600
    old = agent_quota.quota_ref(store.db, UID, agent_quota.day_key()).get().to_dict()
    assert old['used'] == 1100 and old['reserved'] == 0
    assert store.claim(UID, loop.chat_id, loop.turn_id, loop.model, step='completion:1', reservation=(800, 100), **params)
    assert agent_quota.snapshot(store.db, UID)['reserved'] == 800
    store.settle(UID, loop.chat_id, loop.turn_id, completion=receipt(), status='succeeded', step='completion:1', final=False)
    assert agent_quota.snapshot(store.db, UID)['used'] == 1100



def _search(kwargs):
    return next((t["parameters"] for t in kwargs.get("tools") or [] if t.get("type") == "openrouter:web_search"), None)


# "full" answers may search three rounds, "quick" answers once, whatever the
# account's remaining budget: their search is booked, not reserved.
@pytest.mark.parametrize("depth,limit,rounds", [("quick", 10_000_000, 1), ("full", 10_000_000, 3),
                                                ("full", 300_000, 3), ("full", 100_000, 3)])
def test_every_model_searches_with_one_configuration_and_judges_never_search(store, depth, limit, rounds):
    from app.services.llm.engines import web_search_tool
    script = Script(direct=True, depth=depth)
    seen = []
    base = script.factory
    def factory():
        completion = base()
        stream = completion.stream
        def recording(*, model, messages, **kwargs):
            schema = (model.request_config.get("response_format") or {}).get("json_schema")
            kind = ("orchestrator" if completion.step_id == "completion:0" else "answer" if completion.step_id.startswith("completion:")
                    else "judge" if schema else "comparison")
            seen.append((kind, model.model, kwargs["native_searches"], _search(kwargs), messages[0]["content"]))
            yield from stream(model=model, messages=messages, **kwargs)
        completion.stream = recording
        return completion
    script.factory = factory
    from app.services.llm.provider_runtime import AnalysisBudget
    agent_budget_config.store(store.db).save(expected_revision=0, updated_by="admin", tier_limits={"pro": limit})
    # One family with its own search, one without.
    loop = make_loop(store, script, models={"anthropic": "claude-haiku-4-5", "deepseek": "deepseek-v4-flash"})
    loop.policy = AgentPolicy.for_chat(loop.config)
    loop.costs.policy = loop.policy
    loop.budget = AnalysisBudget(unlimited=True)
    list(loop.run())
    expected = lambda family, rounds: web_search_tool(family, max_uses=rounds, max_results=5,
                                                       max_total_results=5 * rounds, max_characters=2000)["parameters"]
    comparisons = {model: (rounds, tool, prompt) for kind, model, rounds, tool, prompt in seen if kind == "comparison"}
    assert set(comparisons) == {"anthropic/claude-haiku-4.5", "deepseek/deepseek-v4-flash"}
    # The same configuration as Consensus whatever the depth: OpenRouter picks
    # the publisher's own search or Exa (engine "auto"). Every answer of one
    # comparison searches equally deep.
    assert comparisons["anthropic/claude-haiku-4.5"][:2] == (rounds, expected("anthropic", rounds))
    assert comparisons["deepseek/deepseek-v4-flash"][:2] == (rounds, expected("deepseek", rounds))
    assert all(tool["engine"] == "auto" for _, tool, _ in comparisons.values())
    told = "use web search once" if rounds == 1 else f"up to {rounds} search rounds"
    assert all("Current date:" in prompt and told in prompt for *_, prompt in comparisons.values())
    # The orchestrator may research to phrase the question (its findings stay
    # with it); sources named in a context are only hints to the answer models.
    [(_, _, searched, tool, _)] = [row for row in seen if row[0] == "orchestrator"]
    # Its own research is optional: a tight budget shrinks it (unlike the
    # answer models' rounds above). Its reservation includes the routing
    # reasoning headroom for every search round (ROUTING_REASONING_HEADROOM).
    own = 3 if limit >= 300_000 else 1
    assert searched == own and tool == expected("anthropic", own)
    assert all("hints, never a requirement" in prompt for *_, prompt in comparisons.values())
    assert all(rounds == 0 for kind, _, rounds, _, _ in seen if kind in {"judge", "answer"})
    assert any(kind == "judge" for kind, *_ in seen)
    assert store.get_turn(UID, loop.chat_id, loop.turn_id)["status"] == "completed"


def test_a_comparison_that_overdraws_the_day_still_reaches_its_checked_answer(store):
    """Search is booked, not reserved: a "full" comparison keeps all its rounds
    on a small allowance, and synthesis and judges finish beyond the limit.
    The next message is refused instead."""
    from app.services.llm.provider_runtime import AnalysisBudget
    script = Script(direct=True, depth="full")
    rounds, base = [], script.factory
    def factory():
        completion = base()
        stream = completion.stream
        def heavy(*, model, messages, **kwargs):
            yield from stream(model=model, messages=messages, **kwargs)
            if not completion.step_id.startswith("completion:") and not model.request_config.get("response_format"):
                rounds.append(kwargs["native_searches"])
                # Three rounds of search results, measured after the call.
                completion.usage = measured_usage({"prompt_tokens": 40_000, "completion_tokens": 2_000}, model)
        completion.stream = heavy
        return completion
    script.factory = factory
    limit = 60_000
    agent_budget_config.store(store.db).save(expected_revision=0, updated_by="admin", tier_limits={"pro": limit})
    loop = make_loop(store, script, models={"anthropic": "claude-haiku-4-5", "deepseek": "deepseek-v4-flash"})
    loop.policy = AgentPolicy.for_chat(loop.config)
    loop.costs.policy = loop.policy
    loop.budget = AnalysisBudget(unlimited=True)
    list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert rounds == [3, 3]
    assert saved["status"] == "completed" and saved["agent_review"]["status"] == "succeeded"
    ledger = agent_quota.snapshot(store.db, UID)
    assert ledger["used"] > limit and ledger["reserved"] == 0
    assert agent_quota.remaining_tokens(store.db, UID) == 0


def test_overdraft_admits_a_reservation_beyond_the_limit_only_when_asked():
    from app.services.agent_quota import AgentTokenBudgetExceeded, reserve
    with pytest.raises(AgentTokenBudgetExceeded):
        reserve({"used": 900}, 200, limit=1000)
    assert reserve({"used": 900}, 200, limit=1000, overdraft=True)["reserved"] == 200


def test_search_steps_down_by_rounds_and_reserves_one_bound_per_round():
    from app.services.agent_delegation import smaller_search
    from app.services.agent_costs import RunCosts, SEARCH_INPUT_TOKENS
    assert [smaller_search(n) for n in (3, 2, 1)] == [1, 1, 0]
    costs = RunCosts(AgentPolicy.for_chat({**defaults(), "enabled": True}))
    messages = [{"role": "user", "content": "Q"}]
    estimate = lambda model, n: costs.estimate(model, messages, native_searches=n)[0]
    native, exa = resolve_agent_model("claude-haiku-4-5"), metered_model("deepseek-v4-flash")
    for model in (native, exa):
        none, one, three = estimate(model, 0), estimate(model, 1), estimate(model, 3)
        assert none < one < three
        # Same bound for every family: one round adds at most its search input
        # (in its continuation) plus one more output segment.
        assert one - 2 * none <= SEARCH_INPUT_TOKENS
        # Comparison answers reserve no search tokens: settlement books them.
        assert costs.estimate(model, messages, native_searches=3, soft_search=True)[0] == none
    # Never the whole context window; a small window caps the search input instead.
    assert estimate(native, 1) < native.context_length // 2
    small = replace(native, context_length=20_000, max_output_tokens=4_000)
    assert estimate(small, 1) <= 2 * small.context_length


@pytest.mark.parametrize("remaining,succeeds,context_room", [(40000, True, None), (100, False, None), (40000, False, 0)])
def test_search_reservation_can_fall_back_without_extra_paid_claim(store, remaining, succeeds, context_room):
    calls = []
    class Completion(AgentCompletion):
        def stream(self, *, model, messages, **kwargs):
            calls.append(kwargs)
            assert "Web search is unavailable" in messages[0]["content"]
            assert kwargs["native_searches"] == 0
            self.text, self.finish_reason = "Answer from existing evidence.", "stop"
            self.usage = measured_usage({"prompt_tokens": 50, "completion_tokens": 20}, model)
            yield {"type": "delta", "text": self.text}
    loop = make_loop(store, Script())
    loop.factory = Completion
    loop.search_remaining = 1
    if context_room is not None:
        loop.policy = replace(loop.policy, context_chars=len(json.dumps(loop.messages, ensure_ascii=False)) + context_room)
    ref = agent_quota.quota_ref(store.db, UID, agent_quota.day_key())
    ref.set({"used": 250000 - remaining})
    if succeeds:
        events = list(loop.run())
        assert len(calls) == 1 and loop.costs.calls == 1
        assert any(e.get("name") == "web_search" and e.get("status") == "blocked" for e in events)
        assert ref.get().to_dict()["used"] == 250000 - remaining + 70
        assert ref.get().to_dict()["reserved"] == 0
    else:
        with pytest.raises(AnalysisBudgetExceeded, match="context limit" if context_room is not None else "reservation"):
            list(loop.run())
        assert calls == [] and loop.costs.calls == 0 and loop.costs.tokens == 0
        assert ref.get().to_dict() == {"used": 250000 - remaining}
    assert loop.search_remaining == 1


def test_unknown_terminal_usage_releases_admission_and_utc_day_is_separate(store, monkeypatch):
    loop = make_loop(store, Script())
    monkeypatch.setattr(agent_quota, "day_key", lambda: "2026-09-19")
    assert store.claim(UID, loop.chat_id, loop.turn_id, loop.model, run_token=loop.run_token,
        policy=loop.policy.snapshot(), reservation=(500, 100))
    store.settle(UID, loop.chat_id, loop.turn_id, completion=receipt(measured=False), status="cancelled", final=False)
    quota = agent_quota.quota_ref(store.db, UID, "2026-09-19").get().to_dict()
    assert quota['reserved'] == 0 and quota['unknown'] == quota['unknown_released'] == 500
    assert agent_quota.public(agent_quota.quota_ref(store.db, UID, "2026-09-20").get().to_dict())["remaining"] == 250000


def test_configured_default_uses_cross_family_judges(store):
    loop = make_loop(store, Script())
    loop.model = resolve_agent_model()
    list(loop.run())
    review = store.get_turn(UID, loop.chat_id, loop.turn_id)["agent_review"]
    assert review["status"] == "succeeded"
    assert review["checks"][0]["differences_data"]["judges"]["differences"]["provider"] != "DeepSeek"


@pytest.mark.parametrize("chat_model", ["gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3.1-pro-preview"])
@pytest.mark.parametrize("failure", [None, "404", "timeout", "empty", "cooldown"])
def test_gemini_chat_uses_standard_luna_then_flash_lite_for_both_judges(store, monkeypatch, chat_model, failure):
    from app.core import config as cfg
    from app.services.agent_provider_limits import AgentProviderCooldown

    # Match the admin configuration, including the expensive Pro choice. The
    # chat model's tier must never select that table for either review role.
    monkeypatch.setitem(cfg.DIFFERENCES_JUDGE_MODEL_BY_PROVIDER, "openai", "gpt-5.6-luna")
    monkeypatch.setitem(cfg.DIFFERENCES_JUDGE_MODEL_BY_PROVIDER, "gemini", "gemini-3.5-flash-lite")
    monkeypatch.setitem(cfg.PRO_JUDGE_MODEL_BY_PROVIDER, "openai", "gpt-5.6-terra")
    script = Script()
    loop = make_loop(store, script)
    loop.model = resolve_agent_model(chat_model)
    base = type(script.factory())
    attempts = {"differences": [], "coverage": []}

    class FailingLuna(base):
        def stream(self, **kwargs):
            model = kwargs["model"]
            schema = (model.request_config.get("response_format") or {}).get("json_schema", {}).get("schema")
            if schema:
                role = "coverage" if "sentences" in schema["properties"] else "differences"
                attempts[role].append(model.model)
                if failure and model.model == "openai/gpt-5.6-luna":
                    if failure == "404":
                        raise RuntimeError("404 Model unavailable")
                    if failure == "timeout":
                        raise TimeoutError("No response")
                    if failure == "cooldown":
                        raise AgentProviderCooldown(30)
                    self.finish_reason = "stop"
                    return
                assert model.request_config.get("reasoning", {}).get("effort") == "low"
            yield from super().stream(**kwargs)

    loop.factory = FailingLuna
    list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    review = saved["agent_review"]
    assert saved["status"] == "completed"
    assert review["status"] == "succeeded"
    assert review_is_bound(review, saved["consensus"])
    for role in attempts:
        expected = ["openai/gpt-5.6-luna"]
        if failure:
            if failure != "404":
                expected.append("openai/gpt-5.6-luna")
            expected.append("google/gemini-3.5-flash-lite")
        assert attempts[role] == expected
        meta = review["checks"][0]["differences_data"]["judges"][role]
        assert meta["model"] == expected[-1]
        assert meta["tier"] == "standard"
        assert meta["attempts"] == len(expected)


@pytest.mark.parametrize("chat_model,primary,fallback", [
    ("gemini-3.1-pro-preview", "openai/gpt-5.6-luna", "google/gemini-3.5-flash-lite"),
    # Since 2026-10-04 an OpenAI chat is judged by Luna first as well.
    ("gpt-5.4-mini", "openai/gpt-5.6-luna", "google/gemini-3.5-flash-lite"),
])
def test_unavailable_chat_judges_stop_after_standard_fallback(store, monkeypatch, chat_model, primary, fallback):
    from app.core import config as cfg
    monkeypatch.setitem(cfg.DIFFERENCES_JUDGE_MODEL_BY_PROVIDER, "openai", "gpt-5.6-luna")
    monkeypatch.setitem(cfg.DIFFERENCES_JUDGE_MODEL_BY_PROVIDER, "gemini", "gemini-3.5-flash-lite")
    loop = make_loop(store, Script())
    loop.model = resolve_agent_model(chat_model)
    call = loop.comparison.call
    attempts = {"Coverage judge": [], "Differences judge": []}

    def unavailable(model, messages, **kwargs):
        if kwargs["kind"] == "judge":
            attempts[kwargs["title"]].append(model.model)
            raise TimeoutError("No judge available")
        return call(model, messages, **kwargs)

    loop.comparison.call = unavailable
    list(loop.run())
    review = store.get_turn(UID, loop.chat_id, loop.turn_id)["agent_review"]
    assert review["status"] == "failed"
    assert all(models == [primary, primary, fallback] for models in attempts.values())
    assert {"code": "differences_unavailable"} in review["checks"][0]["issues"]
    assert {"code": "coverage_unavailable"} in review["checks"][0]["issues"]


def test_midnight_moves_only_unspent_review_hold(store, monkeypatch):
    loop = make_loop(store, Script())
    args = (UID, loop.chat_id, loop.turn_id)
    monkeypatch.setattr(agent_quota, "day_key", lambda: "2026-09-19")
    assert store.claim(*args, loop.model, run_token=loop.run_token, policy=loop.policy.snapshot(), reservation=(100, 100))
    store.settle(*args, completion=receipt(measured=False), status="succeeded", final=False)
    store.protect_review(*args, loop.run_token, 200)
    monkeypatch.setattr(agent_quota, "day_key", lambda: "2026-09-20")
    assert store.claim(*args, loop.model, step="completion:1", run_token=loop.run_token, reservation=(50, 100))
    previous = agent_quota.quota_ref(store.db, UID, '2026-09-19').get().to_dict()
    assert previous['reserved'] == 0 and previous['unknown'] == previous['unknown_released'] == 100
    assert agent_quota.quota_ref(store.db, UID, "2026-09-20").get().to_dict()["reserved"] == 200


def test_disconnect_during_review_settles_every_paid_call_and_marks_stopped(store):
    loop = make_loop(store, Script())
    source = loop.run()
    for event in source:
        if event["type"] == "review" and event["review"]["status"] == "running":
            loop.cancellation.cancel()
            break
    source.close()
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "failed"
    # A stop that lands after the judges already finished keeps their result;
    # a review still running when the stop arrives is marked stopped.
    review = saved["agent_review"]
    finished = all(check.get("differences_data") for check in review.get("checks", [])) and review.get("checks")
    assert review["status"] == ("succeeded" if finished else "cancelled")
    root = store.receipt_ref(UID, loop.chat_id, loop.turn_id).get().to_dict()
    assert "running" not in root["step_states"].values()
    assert root["run_status"] == "cancelled"


def test_later_run_failure_keeps_finished_review_result(store):
    """A failure after the judges finished must not relabel the checked answer."""
    loop = make_loop(store, Script())
    judge = loop.registry.tools["judge_answer"]
    def judge_then_fail(*args, **kwargs):
        judge.execute(*args, **kwargs)
        raise RuntimeError("late provider failure")
    loop.registry.tools["judge_answer"] = replace(judge, execute=judge_then_fail)
    with pytest.raises(RuntimeError):
        list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "failed"
    assert saved["agent_review"]["status"] == "succeeded"
    assert saved["agent_review"]["checks"][0]["differences_data"] is not None


def test_failed_review_recovery_preserves_status_and_never_calls_provider(api):
    client, store, calls = api
    loop = make_loop(store, Script(missing=True))
    def failed_review(*args, **kwargs):
        raise AnalysisBudgetExceeded("Review admission unavailable")
    loop.registry.tools["judge_answer"] = replace(loop.registry.tools["judge_answer"], execute=failed_review)
    with pytest.raises(AnalysisBudgetExceeded):
        list(loop.run())
    payload = {"chat_id": loop.chat_id, "question": "Question one", "client_request_id": "one",
               "bookmark_id": "agent_review_recovery", "recover_only": True}
    before = agent_quota.quota_ref(store.db, UID, agent_quota.day_key()).get().to_dict()
    response = client.post("/agent", json=payload, headers=AUTH)
    assert response.status_code == 200, response.text
    assert response.json()["turn"]["agent_review"]["status"] == "missing"
    assert response.json()["turn"]["status"] == "failed"
    assert calls == []
    assert agent_quota.quota_ref(store.db, UID, agent_quota.day_key()).get().to_dict() == before
    assert client.post("/agent", json={**payload, "comparison_models": {"openai": "gpt-5.4-mini", "anthropic": "claude-haiku-4-5"}}, headers=AUTH).status_code == 409
    # Settings are part of the request identity; the defaults equal "not sent".
    assert client.post("/agent", json={**payload, "agent_preferences": {"depth": "auto", "quorum": "all"}}, headers=AUTH).status_code == 200
    assert client.post("/agent", json={**payload, "agent_preferences": {"depth": "full", "quorum": "all"}}, headers=AUTH).status_code == 409
    assert client.post("/agent", json={**payload, "agent_preferences": {"depth": "deep"}}, headers=AUTH).status_code == 422


@pytest.mark.parametrize("committed,failures", [(False, 1), (True, 1), (False, 3)])
def test_transient_settlement_failure_never_repeats_model_or_leaves_run_pending(store, monkeypatch, committed, failures):
    from google.api_core.exceptions import ServiceUnavailable
    original = store.settle
    failed = []
    def settle(*args, **kwargs):
        step = kwargs.get("step", "")
        if step.startswith("agent:") and len(failed) < failures and (not failed or step == failed[0]):
            failed.append(step)
            if committed:
                original(*args, **kwargs)
            raise ServiceUnavailable("temporary settlement failure")
        return original(*args, **kwargs)
    monkeypatch.setattr(store, "settle", settle)
    script = Script()
    loop = make_loop(store, script)
    list(loop.run())
    assert failed and len(script.calls) == len({step for step, model in script.calls})
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "completed"
    assert saved["agent_review"]["status"] == ("succeeded" if failures == 1 else "failed")
    root = store.receipt_ref(UID, loop.chat_id, loop.turn_id).get().to_dict()
    assert root["run_status"] == "succeeded" and "running" not in root["step_states"].values()
    assert store.db.collection("users").document(UID).get().to_dict()["agent_usage"]["unsettled_calls"] == 0
    assert saved["agent_usage"]["input_tokens"] + saved["agent_usage"]["output_tokens"] == len(script.calls) * 70


def test_comparison_models_get_their_own_completion_limit():
    from app.core import config as cfg
    from app.services.agent_comparison import COMPARISON_OUTPUT_CEILING
    from app.services.llm.agent_client import _CATALOG
    chosen = {"anthropic": "claude-haiku-4-5", "openai": "gpt-5.4-mini"}
    models = comparison_selection(chosen)
    for provider, model in models.items():
        catalog = _CATALOG["models"][model.model]["top_provider"].get("max_completion_tokens") or COMPARISON_OUTPUT_CEILING
        assert model.max_output_tokens == min(COMPARISON_OUTPUT_CEILING, catalog)
        assert model.max_output_tokens > cfg.MAX_TOKENS


def test_answer_cut_off_at_the_output_limit_is_kept_as_marked_evidence(store):
    script = Script(length_model="The first option costs 100. It also")
    loop = make_loop(store, script)
    list(loop.run())
    review = store.get_turn(UID, loop.chat_id, loop.turn_id)["agent_review"]
    comparison = review["comparisons"][0]
    assert comparison["failed_models"] == []
    assert len(comparison["answers"]) == 2
    cut = [a for a in comparison["answers"] if a["provider"] == "openai"][0]
    assert cut["truncated"] is True and cut["text"] == "The first option costs 100. It also"
    assert not any(a.get("truncated") for a in comparison["answers"] if a["provider"] != "openai")


def test_output_limit_without_text_names_the_cause_without_retry_advice(store, monkeypatch):
    notes = []
    publish = store.publish_agent
    def capture(*args, message=None, **kwargs):
        if message and message.get("kind") == "failure":
            notes.append(message["text"])
        return publish(*args, message=message, **kwargs)
    monkeypatch.setattr(store, "publish_agent", capture)
    script = Script(length_model="")
    loop = make_loop(store, script)
    list(loop.run())
    review = store.get_turn(UID, loop.chat_id, loop.turn_id)["agent_review"]
    failed = review["comparisons"][0]["failed_models"]
    assert [f["failure"]["code"] for f in failed] == ["output_limit"]
    assert notes == ["The model used its whole output allowance before it finished an answer. "
                     "The comparison uses the other answers."]


THREE = {"anthropic": "claude-haiku-4-5", "openai": "gpt-5.4-mini", "gemini": "gemini-3.5-flash-lite"}


def comparison_texts(messages):
    return json.dumps(messages)


def test_last_comparison_goes_straight_to_the_checked_answer(store):
    script = Script(direct=True)
    loop = make_loop(store, script)
    list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "completed"
    assert saved["agent_review"]["status"] == "succeeded"
    assert review_is_bound(saved["agent_review"], saved["consensus"])
    # Guided: every comparison records that it asked the whole selection.
    assert saved["agent_review"]["comparisons"][0]["asked"] == ["anthropic", "openai"]
    # compare_models, then the tool-free answer step: no routing round that
    # would only have emitted judge_answer.
    assert [step for step, _ in script.calls if step.startswith("completion:")] == ["completion:0", "completion:1"]


def test_comparison_models_answer_at_the_same_time(store):
    import threading
    barrier = threading.Barrier(3, timeout=5)

    class Parallel(Script):
        def factory(self):
            base = type(super().factory())
            script = self
            class Completion(base):
                def stream(self, *, model, messages, **kwargs):
                    if not self.step_id.startswith("completion:") and not model.request_config.get("response_format"):
                        barrier.wait()  # breaks unless all three answer models run at once
                    yield from super().stream(model=model, messages=messages, **kwargs)
            return Completion()

    script = Parallel(direct=True)
    loop = make_loop(store, script, models=THREE)
    assert loop.policy.max_parallel == 2
    list(loop.run())
    review = store.get_turn(UID, loop.chat_id, loop.turn_id)["agent_review"]
    assert [len(c["answers"]) for c in review["comparisons"]] == [3]
    assert review["status"] == "succeeded"


class Straggler(Script):
    """The Gemini answer only arrives once `release` is set (or never)."""

    def __init__(self, *, release_on_answer, partial="", **kwargs):
        import threading
        super().__init__(direct=True, **kwargs)
        self.release = threading.Event()
        self.release_on_answer = release_on_answer
        self.partial = partial
        self.synthesis_evidence = None
        self.judge_prompts = []

    def factory(self):
        from app.services.llm.provider_runtime import current_provider_cancellation
        base = type(super().factory())
        script = self
        class Completion(base):
            def stream(self, *, model, messages, **kwargs):
                if model.request_config.get("response_format"):
                    script.judge_prompts.append(json.dumps(messages))
                if self.step_id.startswith("completion:") and not kwargs["tools"]:
                    script.synthesis_evidence = json.dumps(messages)
                    if script.release_on_answer:
                        script.release.set()
                        comparison = script.loop.comparison
                        cid = comparison.comparisons[-1]["id"]
                        for _ in range(200):
                            if "gemini" in comparison._raw[cid]:
                                break
                            time.sleep(.02)
                elif not self.step_id.startswith("completion:") and model.model.startswith("google") \
                        and not model.request_config.get("response_format"):
                    cancellation = current_provider_cancellation()
                    if script.partial:
                        self.text = script.partial
                        yield {"type": "delta", "text": script.partial}
                    while not script.release.wait(.02):
                        cancellation.raise_if_cancelled()
                    self.text, self.finish_reason = "Gemini: the second option is cheaper.", "stop"
                    self.usage = measured_usage({"prompt_tokens": 50, "completion_tokens": 20}, model)
                    yield {"type": "delta", "text": self.text}
                    return
                yield from super().stream(model=model, messages=messages, **kwargs)
        return Completion()


@pytest.fixture
def quick_quorum(monkeypatch):
    from app.services import agent_comparison
    monkeypatch.setattr(agent_comparison, "MIN_GRACE_SECONDS", .05)
    monkeypatch.setattr(agent_comparison, "QUORUM_GRACE", {"quick": 1.0, "full": 1.0})


def test_answer_starts_at_quorum_and_a_late_answer_stays_out_of_the_check(store, quick_quorum):
    script = Straggler(release_on_answer=True, depth="quick")
    loop = make_loop(store, script, models=THREE, preferences=AgentPreferences(quorum="balanced"))
    list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    review = saved["agent_review"]
    comparison = review["comparisons"][0]
    assert "second option is cheaper" not in script.synthesis_evidence
    assert sorted(comparison["synthesis_providers"]) == ["anthropic", "openai"]
    late = [a["provider"] for a in comparison["answers"] if a.get("late")]
    assert late == ["gemini"] and len(comparison["answers"]) == 3
    # The text never saw the late answer, so the judges do not check it against it.
    assert script.judge_prompts and not any("second option is cheaper" in p for p in script.judge_prompts)
    assert comparison["status"] == "succeeded" and not comparison["failed_models"]
    assert review["status"] == "succeeded" and review_is_bound(review, saved["consensus"])
    assert "pending_models" not in comparison


def test_a_model_still_writing_at_the_check_is_stopped_and_reported(store, quick_quorum):
    script = Straggler(release_on_answer=False, depth="quick")
    loop = make_loop(store, script, models=THREE, preferences=AgentPreferences(quorum="balanced"))
    list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    review = saved["agent_review"]
    comparison = review["comparisons"][0]
    assert saved["status"] == "completed"
    assert [m["failure"]["code"] for m in comparison["failed_models"]] == ["late_cutoff"]
    assert len(comparison["answers"]) == 2 and comparison["status"] == "partial"
    assert review["status"] == "partial" and review_is_bound(review, saved["consensus"])
    assert {"code": "models_unavailable", "count": 1} in review["checks"][0]["issues"]
    assert not any(t.is_alive() for t, _ in loop.comparison._running[comparison["id"]].values())


def test_text_of_a_model_stopped_mid_answer_is_kept_as_incomplete_but_never_checked(store, quick_quorum):
    script = Straggler(release_on_answer=False, partial="Gemini: the first half of an answer", depth="quick")
    loop = make_loop(store, script, models=THREE, preferences=AgentPreferences(quorum="balanced"))
    list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    review = saved["agent_review"]
    comparison = review["comparisons"][0]
    [stopped] = comparison["failed_models"]
    assert stopped["failure"]["code"] == "late_cutoff"
    assert stopped["partial_text"] == "Gemini: the first half of an answer"
    # Neither the synthesis nor the checked basis sees unfinished text.
    assert "first half" not in script.synthesis_evidence
    assert all("first half" not in a["text"] for a in comparison["answers"])
    assert review["status"] == "partial" and review_is_bound(review, saved["consensus"])
    view = store.delegation_view(UID, loop.chat_id, loop.turn_id)
    [session] = [a for a in view["agents"] if a.get("partial")]
    assert session["status"] == "stopped"
    messages = store.delegation_view(UID, loop.chat_id, loop.turn_id, agent_id=session["id"])["messages"]
    assert [m["kind"] for m in messages if m["kind"] == "partial"] == ["partial"]


def test_partial_text_gives_way_before_the_review_exceeds_its_storage(store):
    from app.services.agent_comparison import ComparisonTools
    saved = []
    class Loop:
        class store:
            @staticmethod
            def save_review(*args):
                saved.append(args[4])
        uid = chat_id = turn_id = run_token = "x"
        outgoing = type("Q", (), {"put_nowait": staticmethod(lambda item: None)})
    tools = ComparisonTools(Loop(), {})
    tools.comparisons = [{"id": "c", "answers": [], "failed_models": [
        {"model": "m", "failure": {"code": "late_cutoff"}, "partial_text": "x" * 700_000}]}]
    tools.checkpoint()
    assert "partial_text" not in saved[0]["comparisons"][0]["failed_models"][0]
    assert saved[0]["comparisons"][0]["failed_models"][0]["model"] == "m"


def test_quorum_sizes():
    from app.services.agent_comparison import quorum_size
    assert [quorum_size(n, "full") for n in (2, 3, 4, 6)] == [2, 3, 4, 6]
    assert [quorum_size(n, "quick") for n in (2, 3, 4, 6)] == [2, 2, 2, 3]


@pytest.mark.parametrize("depth,expected", [("quick", "Answer briefly"), ("full", "as thoroughly as the task needs"),
                                             (None, "as thoroughly as the task needs")])
def test_depth_sets_the_answer_models_length_guidance(store, depth, expected):
    script = Script(direct=True, depth=depth)
    loop = make_loop(store, script)
    list(loop.run())
    assert script.prompts and all(expected in prompt[0]["content"] for prompt in script.prompts)
    assert "6000 characters" not in json.dumps(script.prompts)
    review = store.get_turn(UID, loop.chat_id, loop.turn_id)["agent_review"]
    assert review["comparisons"][0]["depth"] == (depth or "full")


def test_next_step_is_a_required_decision():
    from pydantic import ValidationError
    from app.services.agent_comparison import CompareArgs
    with pytest.raises(ValidationError):
        CompareArgs(question="Q?", context="", reason="R")


def test_a_failed_run_does_not_leave_a_model_shown_as_still_answering(store, quick_quorum):
    class Failing(Straggler):
        def factory(self):
            base = type(super().factory())
            class Completion(base):
                def stream(self, *, model, messages, **kwargs):
                    if self.step_id.startswith("completion:") and not kwargs["tools"]:
                        raise RuntimeError("answer step failed")
                    yield from super().stream(model=model, messages=messages, **kwargs)
            return Completion()

    script = Failing(release_on_answer=False, depth="quick")
    loop = make_loop(store, script, models=THREE, preferences=AgentPreferences(quorum="balanced"))
    with pytest.raises(Exception):
        list(loop.run())
    comparison = store.get_turn(UID, loop.chat_id, loop.turn_id)["agent_review"]["comparisons"][0]
    assert "pending_models" not in comparison
    assert [m["model"] for m in comparison["failed_models"]] == ["google/gemini-3.5-flash-lite"]
    assert not any(t.is_alive() for t, _ in loop.comparison._running[comparison["id"]].values())


def test_answer_allowance_respects_the_saved_review_size(store):
    from app.services.agent_comparison import REVIEW_ANSWER_CHARS, CHARS_PER_TOKEN
    loop = make_loop(store, Script())
    share = loop.comparison._output_share(6)
    assert share <= REVIEW_ANSWER_CHARS // 6 // CHARS_PER_TOKEN


def test_only_an_accepted_last_comparison_skips_the_routing_round(store):
    from app.services.llm.agent_client import AgentCompletion
    loop = make_loop(store, Script())
    loop.comparison.ready_to_answer = True
    value = AgentCompletion()
    value.tool_calls = [{"id": "1", "type": "function", "function": {"name": "compare_models", "arguments": "{}"}}]
    assert loop._answer_ready(value, True)
    assert not loop._answer_ready(value, False)
    loop.google_actions = True
    assert not loop._answer_ready(value, True)


def test_a_depth_fixed_in_settings_overrides_the_orchestrator(store):
    from app.services.agent_comparison import AgentPreferences
    script = Script(direct=True, depth="quick")
    loop = make_loop(store, script, preferences=AgentPreferences(depth="full"))
    assert 'fixed the comparison depth to "full"' in loop.messages[0]["content"]
    list(loop.run())
    assert all("as thoroughly as the task needs" in prompt[0]["content"] for prompt in script.prompts)
    assert store.get_turn(UID, loop.chat_id, loop.turn_id)["agent_review"]["comparisons"][0]["depth"] == "full"


def test_waiting_for_every_model_puts_a_slow_answer_into_the_text(store, quick_quorum):
    import threading
    from app.services.agent_comparison import AgentPreferences
    script = Straggler(release_on_answer=False)
    threading.Timer(.4, script.release.set).start()
    loop = make_loop(store, script, models=THREE, preferences=AgentPreferences(quorum="all"))
    list(loop.run())
    comparison = store.get_turn(UID, loop.chat_id, loop.turn_id)["agent_review"]["comparisons"][0]
    assert "second option is cheaper" in script.synthesis_evidence
    assert sorted(comparison["synthesis_providers"]) == ["anthropic", "gemini", "openai"]
    assert not any(a.get("late") for a in comparison["answers"])


def test_quick_questions_also_wait_for_the_slowest_model_by_default(store, quick_quorum):
    """Default "all" since 2026-10-07: a late answer would miss the check."""
    import threading
    script = Straggler(release_on_answer=False, depth="quick")
    threading.Timer(.4, script.release.set).start()
    loop = make_loop(store, script, models=THREE)
    list(loop.run())
    comparison = store.get_turn(UID, loop.chat_id, loop.turn_id)["agent_review"]["comparisons"][0]
    assert sorted(comparison["synthesis_providers"]) == ["anthropic", "gemini", "openai"]
    assert not any(a.get("late") for a in comparison["answers"])


def test_thorough_questions_wait_for_the_slowest_model_by_default(store, quick_quorum):
    """The most careful (slowest) model of a "full" comparison is never cut."""
    import threading
    script = Straggler(release_on_answer=False, depth="full")
    threading.Timer(.4, script.release.set).start()
    loop = make_loop(store, script, models=THREE)
    list(loop.run())
    comparison = store.get_turn(UID, loop.chat_id, loop.turn_id)["agent_review"]["comparisons"][0]
    assert "second option is cheaper" in script.synthesis_evidence
    assert sorted(comparison["synthesis_providers"]) == ["anthropic", "gemini", "openai"]
    assert not any(a.get("late") for a in comparison["answers"])


def test_quorum_modes():
    from app.services.agent_comparison import quorum_size
    assert [quorum_size(6, d, "all") for d in ("quick", "full")] == [6, 6]
    assert [quorum_size(6, d, "fast") for d in ("quick", "full")] == [3, 3]
    assert [quorum_size(6, d, "balanced") for d in ("quick", "full")] == [3, 6]


def _votes(store):
    return [doc.to_dict() for doc in store.db.collection("model_votes").stream()]


def test_checked_agent_answer_adds_one_best_answer_pick_to_the_model_pulse(store):
    from app.core import config as cfg
    loop = make_loop(store, Script())
    list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["agent_review"]["status"] == "succeeded"
    votes = _votes(store)
    assert len(votes) == 1
    vote = votes[0]
    assert vote["source"] == "agent" and vote["vote_type"] == "BestModel"
    assert vote["model"] in cfg.VALID_LEADERBOARD_MODELS
    assert vote["vote_subject_id"] == f"agent:{loop.turn_id}"
    board = store.db.collection("leaderboard").document(vote["model"]).get().to_dict()
    # The fake store keeps the transform; Firestore applies it.
    assert getattr(board["BestModel"], "value", board["BestModel"]) == 1
    # The turn is finished once: a second settlement adds nothing.
    assert not store.finish_run(UID, loop.chat_id, loop.turn_id, completion=loop.completion,
                                status="succeeded", run_token=loop.run_token)
    assert len(_votes(store)) == 1


def test_mock_runs_and_unchecked_answers_never_vote(store, monkeypatch):
    from app.services import agent_runs, persistence_guard
    monkeypatch.setattr(agent_runs, "mock_llm_enabled", lambda: True)
    list(make_loop(store, Script()).run())
    assert _votes(store) == []
    assert persistence_guard.agent_best_model_pick({"status": "failed", "checks": []}) is None
    review = {"status": "partial", "comparisons": [{"id": "a", "answers": [{}, {}]}, {"id": "b", "answers": [{}, {}, {}]}],
              "checks": [{"comparison_id": "a", "status": "succeeded", "differences_data": {"best_model": "OpenAI"}},
                         {"comparison_id": "b", "status": "partial", "differences_data": {"best_model": "Claude"}},
                         {"comparison_id": "c", "status": "failed", "differences_data": {"best_model": "Grok"}}]}
    # The widest comparison decides, and an alias lands on its family.
    assert persistence_guard.agent_best_model_pick(review) == "Anthropic"
    review["checks"][1]["differences_data"]["best_model"] = "Not a model"
    assert persistence_guard.agent_best_model_pick(review) is None


def test_free_mode_asks_only_the_families_the_agent_chose(store):
    from app.services.agent_comparison import AgentPreferences
    script = Script(direct=True, pick=["gemini", "anthropic"])
    loop = make_loop(store, script, models=THREE, preferences=AgentPreferences(autonomy="free"))
    system = loop.messages[0]["content"]
    assert "Agent freedom is FREE" in system
    list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    comparison = saved["agent_review"]["comparisons"][0]
    assert comparison["asked"] == ["gemini", "anthropic"]
    assert sorted(a["provider"] for a in comparison["answers"]) == ["anthropic", "gemini"]
    assert comparison["status"] == "succeeded" and not comparison["failed_models"]
    # The judges still check the answer, and only the chosen models answered.
    assert saved["agent_review"]["status"] == "succeeded"
    assert len(script.prompts) == 2


def test_free_mode_keeps_the_two_family_floor(store):
    from pydantic import ValidationError
    from app.services.agent_comparison import AgentPreferences, CompareArgs
    loop = make_loop(store, Script(), models=THREE, preferences=AgentPreferences(autonomy="free"))
    args = loop.registry.tools["compare_models"].arguments
    schema = args.model_json_schema()
    # The schema itself offers exactly this turn's families and requires a choice.
    assert schema["properties"]["models"]["items"]["enum"] == ["anthropic", "openai", "gemini"]
    assert "models" in schema["required"] and schema["properties"]["models"]["minItems"] == 2
    assert "Claude Haiku 4.5" in schema["properties"]["models"]["description"]
    base = {"question": "Q", "context": "", "reason": "R", "next_step": "answer"}
    for invalid in ({}, {"models": ["openai"]}, {"models": ["openai", "mistral"]}):
        with pytest.raises(ValidationError):
            args.model_validate({**base, **invalid})
    choose = loop.comparison._choose
    assert choose(args.model_validate({**base, "models": ["gemini", "openai"]})) == ["gemini", "openai"]
    # A repeated family is still one opinion.
    with pytest.raises(ValueError, match="at least two different families"):
        choose(args.model_validate({**base, "models": ["openai", "openai"]}))
    # Guided mode has no model choice at all: every comparison asks everyone.
    guided = make_loop(store, Script(), models=THREE)
    assert guided.registry.tools["compare_models"].arguments is CompareArgs
    assert "models" not in CompareArgs.model_fields
    assert guided.comparison._choose(CompareArgs.model_validate(base)) == ["anthropic", "openai", "gemini"]
    assert "Agent freedom" not in guided.messages[0]["content"]


class DirectFirst(Script):
    """The orchestrator first replies without a tool; `repeat` replies again."""

    def __init__(self, *, repeat=False, **kwargs):
        super().__init__(direct=True, **kwargs)
        self.repeat = repeat

    def factory(self):
        base = type(super().factory())
        script = self
        class Completion(base):
            def stream(self, *, model, messages, **kwargs):
                if self.step_id.startswith("completion:") and kwargs["tools"]:
                    index = int(self.step_id.split(":")[-1])
                    if index == 0 or (script.repeat and index == 1):
                        script.calls.append((self.step_id, model.model))
                        self.text, self.finish_reason = "Hello! How can I help?", "stop"
                        yield {"type": "delta", "text": self.text}
                        return
                    self.step_id = f"completion:{index - 1}"
                yield from super().stream(model=model, messages=messages, **kwargs)
        return Completion()


def test_free_mode_sends_a_direct_answer_back_through_a_comparison(store):
    from app.services.agent_comparison import AgentPreferences
    script = DirectFirst(pick=["openai", "anthropic"])
    loop = make_loop(store, script, preferences=AgentPreferences(autonomy="free"))
    events = list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert sum("App rule: every substantive answer" in m["content"] for m in loop.messages if m["role"] == "user") == 1
    assert saved["status"] == "completed"
    assert saved["agent_review"]["status"] == "succeeded"
    # The unchecked direct reply never reached the reader.
    assert not any(e.get("type") == "delta" and "How can I help" in e.get("text", "") for e in events)


def test_free_mode_accepts_a_confirmed_greeting_and_guided_mode_never_asks(store):
    from app.services.agent_comparison import AgentPreferences
    loop = make_loop(store, DirectFirst(repeat=True, pick=["openai", "anthropic"]), preferences=AgentPreferences(autonomy="free"))
    list(loop.run())
    assert loop.completion.text == "Hello! How can I help?"
    assert not loop.comparison.comparisons
    guided = make_loop(store, DirectFirst(repeat=True))
    list(guided.run())
    assert guided.completion.text == "Hello! How can I help?"
    assert not any("App rule" in m["content"] for m in guided.messages if m["role"] == "user")


def test_settings_saved_before_the_freedom_field_still_match_on_recovery():
    from app.services.agent_comparison import AgentPreferences, stored_preferences
    assert stored_preferences({"depth": "auto", "quorum": "all"}) == AgentPreferences().model_dump()
    assert stored_preferences({"depth": "auto"})["quorum"] == "all"
    assert stored_preferences(None) == AgentPreferences().model_dump()
    assert stored_preferences({"depth": "full", "quorum": "all", "autonomy": "free"})["autonomy"] == "free"


@pytest.mark.parametrize("provider,api_model,model_ref,sent", [
    ("openai", "openai/gpt-5.6-luna", "gpt-5.6-luna", False),
    ("gemini", "google/gemini-3.5-flash-lite", "gemini-3.5-flash-lite", False),
    ("anthropic", "anthropic/claude-haiku-4.5", "claude-haiku-4-5", True)])
def test_judge_temperature_follows_the_consensus_rule_for_reasoning_models(store, provider, api_model, model_ref, sent):
    from types import SimpleNamespace
    loop = make_loop(store, Script())
    seen = []
    loop.comparison.call = lambda model, messages, **kwargs: (seen.append(model.request_config), SimpleNamespace(text="{}"))[1]
    loop.comparison.judge_transport(provider, api_model, model_ref, system="", prompt="p", max_tokens=1000,
                                    temperature=0.2, json_mode=True, effort="low", json_schema={"type": "object"})
    assert ("temperature" in seen[0]) is sent


def test_newer_openai_generations_count_as_reasoning_models_for_temperature():
    from app.services.llm.consensus_engine import _effective_temperature
    assert _effective_temperature("openai", "openai/gpt-6-luna", 0.2) is None
    assert _effective_temperature("openai", "openai/gpt-4o", 0.2) == 0.2


def test_judge_calls_follow_the_turns_stop(store, monkeypatch):
    # judge_answer runs in a tool thread; a Stop must reach its provider calls.
    from app.services.llm import consensus_engine
    from app.services.llm.provider_runtime import current_provider_cancellation
    seen = []
    original = consensus_engine.query_differences

    def spy(*args, **kwargs):
        seen.append(current_provider_cancellation())
        return original(*args, **kwargs)

    monkeypatch.setattr(consensus_engine, "query_differences", spy)
    loop = make_loop(store, Script())
    list(loop.run())
    assert seen and all(c is loop.cancellation for c in seen)
