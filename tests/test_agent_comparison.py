"""compare_models and the paid-step accounting of a turn of the agent.

Since 2026-10-31 the agent has one mode: it answers itself, compare_models
asks the user's chosen models its question, and those models review its work
and its answer (agent_audit.py, test_agent_audit.py). The judges of the
former comparison mode are gone. Script/make_loop build such turns for many
suites; their reviewers never start unless a test asks for them
(agent_reviewers.py), so a script's replies stay the agent's and the
comparison models'.
"""
from dataclasses import replace
import json
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.core.openrouter_contract import provider_session_id
from app.services import agent_quota, agent_budget_config
from app.services.agent_comparison import comparison_selection
from app.services.agent_delegation import DelegationLoop
from app.services.agent_delegation_config import defaults
from app.services.agent_policy import AgentPolicy
from app.services.agent_provider_limits import ModelEmptyAnswer
from app.services.llm.agent_client import AgentCompletion, measured_usage, metered_model, resolve_agent_model
from app.services.llm.provider_runtime import ProviderCancellation, AnalysisBudgetExceeded
from agent_reviewers import without_reviewers
from test_agent_runs import UID, AUTH, api, pending, receipt, store, priced

# How a reviewer's system prompt begins (agent_audit.REVIEW_PROMPT_HEAD).
REVIEWER = "You are an independent reviewer"


class Script:
    """A scripted turn of the agent: steps completion:0..compares-1 call
    compare_models, the next step writes the answer as plain text (the agent
    writes it itself, agent_answer_mode). Every other call is a comparison
    answer, or, with reviewers (make_loop(..., reviewers=True)), a
    reviewer's round, which replies with no marks (``reviews`` counts them)."""

    def __init__(self, *, compares=1, fail_model=False, length_model=None, depth=None, empty_model=0):
        self.length_model = length_model
        # OpenAI comparison answers that reason and stop without a word.
        self.empty_model, self.answer_calls = empty_model, []
        self.depth = depth
        self.compares, self.fail_model = compares, fail_model
        self.calls, self.prompts, self.sessions, self.reviews = [], [], [], []
        self.loop = None

    def factory(self):
        script = self
        class Completion(AgentCompletion):
            def stream(self, *, model, messages, **kwargs):
                script.calls.append((self.step_id, model.model))
                # The session this request goes out with (AgentCompletion.stream).
                script.sessions.append((self.step_id, kwargs.get("session_id") or self.session_id, self.one_off))
                self.usage = measured_usage({"prompt_tokens": 50, "completion_tokens": 20, "cost": .0001,
                    "prompt_tokens_details": {"cached_tokens": 20}, "completion_tokens_details": {"reasoning_tokens": 10}}, model)
                if self.step_id.startswith("completion:"):
                    index = int(self.step_id.split(":")[-1])
                    if index >= script.compares or not kwargs["tools"] or kwargs.get("allow_tool_calls") is False:
                        # The answer: plain text without tool calls.
                        self.text, self.finish_reason = "The first option costs 100.", "stop"
                        yield {"type": "delta", "text": self.text}
                        return
                    if script.compares > 1:
                        self.text = f"I will compare perspective {index + 1}."
                        yield {"type": "delta", "text": self.text}
                    args = {"question": f"Evaluate option {index + 1}", "context": "Budget is 100. Source: https://example.org/report",
                            **({"depth": script.depth} if script.depth else {})}
                    self.tool_calls = [{"id": f"call_{index}", "type": "function", "function": {"name": "compare_models", "arguments": json.dumps(args)}}]
                    self.finish_reason = "tool_calls"
                    return
                if messages[0]["content"].startswith(REVIEWER):
                    script.reviews.append((self.step_id, model.model))
                    self.text = json.dumps({"marks": []})
                else:
                    script.prompts.append(messages)
                    script.answer_calls.append((self.step_id, model.model))
                    if script.empty_model and model.model.startswith("openai"):
                        script.empty_model -= 1
                        self.finish_reason, self.output_limited = "stop", True
                        raise ModelEmptyAnswer()
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


def make_loop(store, script, *, messages=None, delegation=False, models=None, preferences=None, reviewers=False):
    """A turn of the agent with ``script``'s completions; its reviewers never
    start (agent_reviewers.InertAnswerAudit) unless ``reviewers``."""
    chat, turn = pending(store)
    config = {**defaults(), "enabled": delegation, "max_searches": 0, "context_chars": 120_000}
    loop = DelegationLoop(store=store, uid=UID, chat_id=chat, turn_id=turn["id"],
        model=resolve_agent_model("claude-haiku-4-5"), messages=messages or [{"role": "system", "content": "Answer."}, {"role": "user", "content": "Compare options"}],
        api_key="test", cancellation=ProviderCancellation(), policy=AgentPolicy.from_config({**config, "enabled": True}),
        delegation_config=config, completion_factory=script.factory,
        comparison_models=comparison_selection(models or {"anthropic": "claude-haiku-4-5", "openai": "gpt-5.4-mini"}),
        agent_preferences=preferences)
    if not reviewers:
        without_reviewers(loop)
    script.loop = loop
    return loop


def saved_turn(store, loop):
    return store.get_turn(UID, loop.chat_id, loop.turn_id)


def test_only_the_chat_models_steps_share_the_chats_provider_session(store):
    """The chat model's steps re-send one growing prefix and stay on the
    endpoint that caches it (openrouter_contract.provider_session_id). Each
    comparison answer keeps a session of its own: a retry re-sends its
    prompt, and no other call shares it. Their first request still takes the
    fastest endpoint."""
    script = Script(compares=2)
    loop = make_loop(store, script)
    list(loop.run())
    own = {session for step, session, _ in script.sessions if step.startswith("completion:")}
    helpers = [(step.split(":")[1], session) for step, session, _ in script.sessions if step.startswith("agent:")]
    assert own == {loop.provider_session} and loop.provider_session
    sessions = dict(helpers)
    assert all(session == sessions[worker] for worker, session in helpers)
    assert len(set(sessions.values())) == len(sessions) and loop.provider_session not in sessions.values()
    assert all(session == provider_session_id(UID, loop.chat_id, worker) for worker, session in sessions.items())
    # No later request continues a comparison answer (AgentCompletion.one_off);
    # the chat model's steps do.
    assert all(one_off == step.startswith("agent:") for step, _, one_off in script.sessions)
    # Both comparison models ran as helpers.
    assert {model for step, model in script.calls if step.startswith("agent:")} == {
        "anthropic/claude-haiku-4.5", "openai/gpt-5.4-mini"}


@pytest.mark.parametrize("compares", [1, 2])
def test_reviewed_exact_version_context_sources_and_all_usage(store, compares, monkeypatch):
    """One mode since 2026-10-31: the agent compares, writes the answer, and
    the user's models review that exact version. No judge runs, no
    differences stats and no Model Pulse vote come from an agent turn."""
    from app.services import differences_stats
    from app.services.agent_comparison import answer_hash
    stats = []
    monkeypatch.setattr(differences_stats, "record_differences_stats", lambda data, **meta: stats.append(data))
    script = Script(compares=compares)
    loop = make_loop(store, script, reviewers=True)
    events = list(loop.run())
    saved = saved_turn(store, loop)
    review = saved["agent_review"]
    assert saved["status"] == "completed"
    assert review["mode"] == "audit" and review["status"] == "succeeded"
    assert [row["status"] for row in review["audit"]["reviewers"]] == ["completed", "completed"]
    assert len(review["versions"]) == 1
    assert saved["consensus"] == review["versions"][-1]["text"]
    assert review["answer_hash"] == answer_hash(saved["consensus"]) == review["versions"][-1]["hash"]
    assert "checks" not in review or review["checks"] == []
    for i in range(compares):
        assert script.prompts[2 * i] == script.prompts[2 * i + 1]
        assert "https://example.org/report" in script.prompts[2 * i][1]["content"]
        assert "first option costs" not in script.prompts[2 * i][1]["content"]
    usage = saved["agent_usage"]
    assert usage["input_tokens"] + usage["output_tokens"] == len(script.calls) * 70
    quota = agent_quota.quota_ref(store.db, UID, agent_quota.day_key() + agent_quota.LEDGER_UNIT).get().to_dict()
    # Each call's provider cost, $0.0001, is 87 micro-euros (rounded up).
    assert quota["used"] == len(script.calls) * 87 and quota["reserved"] == 0
    assert any(e["type"] == "review" and e["review"]["status"] == "running" for e in events)
    tools = [e for e in events if e.get("kind") == "tool" and e.get("name") == "compare_models"]
    assert [e["status"] for e in tools] == [s for _ in range(compares) for s in ("running", "succeeded")]
    # The app's review stays a visible step.
    assert [e["status"] for e in events if e.get("kind") == "tool" and e.get("name") == "audit_answer"] == [
        "running", "succeeded"]
    assert sum(e["type"] == "delta" for e in events) == 1
    # One steering step per comparison, then the step that writes the answer
    # from their results: no separate answer step.
    assert len([step for step, _ in script.calls if step.startswith('completion:')]) == compares + 1
    # Nothing else is paid: two answers per comparison and the reviewers' rounds.
    assert script.reviews and len(script.calls) == (compares + 1) + 2 * compares + len(script.reviews)
    # The agent reads each comparison's result; no app note follows it.
    results = [i for i, m in enumerate(loop.messages) if m["role"] == "tool"]
    assert len(results) == compares
    assert all(loop.messages[i + 1]["role"] == "assistant" for i in results)
    assert all("I will compare" not in v["text"] for v in review["versions"])
    assert store.delegation_view(UID, loop.chat_id, loop.turn_id)["agents"]
    assert stats == [] and not list(store.db.collection("model_votes").stream())


@pytest.mark.parametrize('account_budget_only', [False, True])
def test_fixed_answer_cannot_be_reopened_by_a_second_review_or_late_comparison(store, account_budget_only):
    from app.services.agent_comparison import AuditAnswerArgs, AuditCompareArgs
    script = Script()
    loop = make_loop(store, script)
    loop.policy = replace(loop.policy, account_budget_only=account_budget_only)
    events = list(loop.run())
    saved = saved_turn(store, loop)
    assert saved['consensus'] == 'The first option costs 100.'
    assert len([step for step, _ in script.calls if step.startswith('completion:')]) == 2
    original = json.dumps(loop.comparison.snapshot(), sort_keys=True)
    loop.comparison.capture('A rewritten answer must never replace the reviewed one.')
    result = loop.comparison.audit(AuditAnswerArgs(), cancellation=loop.cancellation)
    assert result['finalized'] is True
    with pytest.raises(ValueError, match='already being written'):
        loop.comparison.compare(AuditCompareArgs(question='Compare again?'), cancellation=loop.cancellation)
    assert json.dumps(loop.comparison.snapshot(), sort_keys=True) == original
    assert saved['agent_review']['versions'][-1]['text'] == saved['consensus']
    first_answer = next(i for i, e in enumerate(events) if e['type'] == 'delta')
    assert not any(e.get('clear_response') for e in events[first_answer + 1:])


def test_a_rate_limited_comparison_model_is_named_and_the_others_answer(store):
    from app.services.agent_provider_limits import AgentProviderCooldown
    script = Script()
    loop = make_loop(store, script)
    loop.comparison.models = comparison_selection({'anthropic': 'claude-haiku-4-5', 'openai': 'gpt-5.4-mini',
                                                  'gemini': 'gemini-3.5-flash-lite'})
    original = loop.comparison.call
    def call(model, messages, **kwargs):
        if model.model.startswith('openai/'):
            raise AgentProviderCooldown(30)
        return original(model, messages, **kwargs)
    loop.comparison.call = call
    list(loop.run())
    saved = saved_turn(store, loop)
    comparison = saved['agent_review']['comparisons'][0]
    assert saved['status'] == 'completed' and comparison['status'] == 'partial'
    assert [m['failure']['code'] for m in comparison['failed_models']] == ['provider_rate_limited']
    assert len(comparison['answers']) == 2
    [missing] = tool_results(loop)['call_0']['missing_answers']
    assert missing['family'] == 'openai'


def test_the_reviewed_version_survives_saved_turn_projection_without_normalizing_text(store):
    from app.services.agent_comparison import answer_hash
    script = Script()
    base = type(script.factory())
    text = "\n**The ﬁrst option** costs 100 €.\n\n"

    class ExactText(base):
        def stream(self, **kwargs):
            events = list(super().stream(**kwargs))
            if self.step_id == "completion:1":  # The step after the comparison writes the answer.
                self.text = text
                yield {"type": "delta", "text": text}
            else:
                yield from events

    loop = make_loop(store, script)
    loop.factory = ExactText
    list(loop.run())
    saved = saved_turn(store, loop)
    history = store.list_turn_details(UID, loop.chat_id)["turns"][0]
    for projected in (saved, history):
        assert projected["status"] == "completed"
        assert projected["consensus"] == projected["assistant_response"] == text
        review = projected["agent_review"]
        assert review["answer_hash"] == answer_hash(projected["consensus"])
        assert review["versions"][-1]["text"] == projected["consensus"]


def test_atomic_daily_budget_and_duplicate_settlement(store, monkeypatch):
    monkeypatch.setitem(agent_budget_config.DEFAULT_TIER_LIMITS, "pro", 100)
    loops = [make_loop(store, Script()) for _ in range(2)]
    def claim(loop):
        try:
            return store.claim(UID, loop.chat_id, loop.turn_id, loop.model, run_token=loop.run_token,
                policy=loop.policy.snapshot(), reservation=(60, priced(60)))
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
    quota = agent_quota.quota_ref(store.db, UID, agent_quota.day_key() + agent_quota.LEDGER_UNIT).get().to_dict()
    # 15 tokens at the flat test price, settled once.
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
        store.claim(UID, loop.chat_id, loop.turn_id, loop.model, reservation=(2001, priced(2001)), **params)
    assert store.claim(UID, loop.chat_id, loop.turn_id, loop.model, reservation=(1500, priced(1500)), **params)
    assert agent_quota.snapshot(store.db, UID)['remaining'] == 500
    config.save(expected_revision=1, updated_by='admin', reset=True)
    assert agent_quota.snapshot(store.db, UID)['remaining'] == 2000
    store.settle(UID, loop.chat_id, loop.turn_id, completion=receipt(), status='succeeded', final=False)
    # The step admitted before the reset settles in its own generation.
    assert agent_quota.snapshot(store.db, UID)['used'] == 0
    old = agent_quota.quota_ref(store.db, UID, agent_quota.day_key() + agent_quota.LEDGER_UNIT).get().to_dict()
    # The receipt's cost, $0.000132, in micro-euros (rounded up).
    assert old['used'] == 115 and old['reserved'] == 0
    assert store.claim(UID, loop.chat_id, loop.turn_id, loop.model, step='completion:1', reservation=(800, priced(800)), **params)
    assert agent_quota.snapshot(store.db, UID)['reserved'] == 800
    store.settle(UID, loop.chat_id, loop.turn_id, completion=receipt(), status='succeeded', step='completion:1', final=False)
    assert agent_quota.snapshot(store.db, UID)['used'] == 115


def _search(kwargs):
    return next((t["parameters"] for t in kwargs.get("tools") or [] if t.get("type") == "openrouter:web_search"), None)


# "full" answers may search three rounds, "quick" answers once, whatever the
# account's remaining budget: their search is booked, not reserved. The
# agent's own search is optional: a tight budget shrinks it.
@pytest.mark.parametrize("depth,limit,rounds,own", [("quick", 10_000_000, 1, 5), ("full", 10_000_000, 3, 5),
                                                    ("full", 300_000, 3, 3), ("full", 100_000, 3, 1)])
def test_every_model_searches_with_one_configuration(store, depth, limit, rounds, own):
    from app.services.agent_audit import AGENT_SEARCH_ROUNDS
    from app.services.llm.engines import web_search_tool
    script = Script(depth=depth)
    seen = []
    base = script.factory
    def factory():
        completion = base()
        stream = completion.stream
        def recording(*, model, messages, **kwargs):
            # "answer": the step after the comparison, which writes the answer.
            kind = ("agent" if completion.step_id == "completion:0" else "answer" if completion.step_id.startswith("completion:")
                    else "comparison")
            seen.append((kind, model.model, kwargs["native_searches"], _search(kwargs), messages[0]["content"]))
            yield from stream(model=model, messages=messages, **kwargs)
        completion.stream = recording
        return completion
    script.factory = factory
    from app.services.llm.provider_runtime import AnalysisBudget
    agent_budget_config.store(store.db).save(expected_revision=0, updated_by="admin", tier_limits={"pro": limit})
    # One family with its own search, one without.
    loop = make_loop(store, script, models={"anthropic": "claude-haiku-4-5", "deepseek": "deepseek-v4.1-flash"})
    loop.policy = AgentPolicy.for_chat(loop.config)
    loop.costs.policy = loop.policy
    loop.budget = AnalysisBudget(unlimited=True)
    list(loop.run())
    expected = lambda family, rounds: web_search_tool(family, max_uses=rounds, max_results=5,
                                                       max_total_results=5 * rounds, max_characters=2000)["parameters"]
    comparisons = {model: (rounds, tool, prompt) for kind, model, rounds, tool, prompt in seen if kind == "comparison"}
    assert set(comparisons) == {"anthropic/claude-haiku-4.5", "deepseek/deepseek-v4.1-flash"}
    # The same configuration as Consensus whatever the depth: OpenRouter picks
    # the publisher's own search or Exa (engine "auto"). Every answer of one
    # comparison searches equally deep.
    assert comparisons["anthropic/claude-haiku-4.5"][:2] == (rounds, expected("anthropic", rounds))
    assert comparisons["deepseek/deepseek-v4.1-flash"][:2] == (rounds, expected("deepseek", rounds))
    assert all(tool["engine"] == "auto" for _, tool, _ in comparisons.values())
    told = "use web search once" if rounds == 1 else f"up to {rounds} search rounds"
    assert all("Current date:" in prompt and told in prompt for *_, prompt in comparisons.values())
    assert all("hints, never a requirement" in prompt for *_, prompt in comparisons.values())
    # The agent researches in every step, up to AGENT_SEARCH_ROUNDS each; its
    # reservation includes the routing reasoning headroom for every round.
    [(_, _, searched, tool, _)] = [row for row in seen if row[0] == "agent"]
    assert own <= AGENT_SEARCH_ROUNDS and searched == own and tool == expected("anthropic", own)
    [(_, _, searched, tool, _)] = [row for row in seen if row[0] == "answer"]
    assert searched >= 1 and tool == expected("anthropic", searched)
    assert saved_turn(store, loop)["status"] == "completed"


def test_a_comparison_that_overdraws_the_day_still_reaches_its_answer(store):
    """Search is booked, not reserved: a "full" comparison keeps all its rounds
    on a small allowance, and the answer is written beyond the limit. The
    next message is refused instead."""
    from app.services.llm.provider_runtime import AnalysisBudget
    script = Script(depth="full")
    rounds, base = [], script.factory
    def factory():
        completion = base()
        stream = completion.stream
        def heavy(*, model, messages, **kwargs):
            yield from stream(model=model, messages=messages, **kwargs)
            if not completion.step_id.startswith("completion:"):
                rounds.append(kwargs["native_searches"])
                # Three rounds of search results, measured after the call.
                completion.usage = measured_usage({"prompt_tokens": 40_000, "completion_tokens": 2_000}, model)
        completion.stream = heavy
        return completion
    script.factory = factory
    limit = 60_000
    agent_budget_config.store(store.db).save(expected_revision=0, updated_by="admin", tier_limits={"pro": limit})
    loop = make_loop(store, script, models={"anthropic": "claude-haiku-4-5", "deepseek": "deepseek-v4.1-flash"})
    loop.policy = AgentPolicy.for_chat(loop.config)
    loop.costs.policy = loop.policy
    loop.budget = AnalysisBudget(unlimited=True)
    list(loop.run())
    saved = saved_turn(store, loop)
    assert rounds == [3, 3]
    assert saved["status"] == "completed" and saved["consensus"] == "The first option costs 100."
    ledger = agent_quota.snapshot(store.db, UID)
    assert ledger["used"] > limit and ledger["reserved"] == 0
    assert agent_quota.remaining_allowance(store.db, UID) == 0


def test_overdraft_admits_a_reservation_beyond_the_limit_only_when_asked():
    from app.services.agent_quota import AgentTokenBudgetExceeded, reserve
    with pytest.raises(AgentTokenBudgetExceeded):
        reserve({"used": 900}, 200, limit=1000)
    assert reserve({"used": 900}, 200, limit=1000, overdraft=True)["reserved"] == 200
    # A merged step: only the answer on top of its routing allowance may lie beyond.
    assert reserve({"used": 900}, 200, limit=1000, overdraft=150)["reserved"] == 200
    with pytest.raises(AgentTokenBudgetExceeded) as refused:
        reserve({"used": 900}, 200, limit=1000, overdraft=50)
    assert (refused.value.required, refused.value.remaining) == (150, 100)


def test_a_merged_step_reserves_its_answer_once_not_per_search_round():
    from app.services.agent_costs import RunCosts
    costs = RunCosts(AgentPolicy.for_chat({**defaults(), "enabled": True}))
    messages = [{"role": "user", "content": "Q"}]
    routing = resolve_agent_model("claude-haiku-4-5")
    answer = routing.max_output_tokens + 40_000
    for searches in (0, 1, 3):
        plain = costs.estimate(routing, messages, native_searches=searches)
        merged = costs.estimate(routing, messages, native_searches=searches, answer_output=answer)
        assert merged[0] - plain[0] == 40_000 and merged[1] > plain[1]
    # The context window still has to hold the whole answer.
    with pytest.raises(AnalysisBudgetExceeded, match="context limit"):
        costs.estimate(routing, messages, answer_output=routing.context_length)


def test_search_steps_down_by_rounds_and_reserves_one_bound_per_round():
    from app.services.agent_delegation import smaller_search
    from app.services.agent_costs import RunCosts, SEARCH_INPUT_TOKENS
    assert [smaller_search(n) for n in (5, 3, 2, 1)] == [3, 1, 1, 0]
    costs = RunCosts(AgentPolicy.for_chat({**defaults(), "enabled": True}))
    messages = [{"role": "user", "content": "Q"}]
    estimate = lambda model, n: costs.estimate(model, messages, native_searches=n)[0]
    native, exa = resolve_agent_model("claude-haiku-4-5"), metered_model("deepseek-v4.1-flash")
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


# Every step may write the answer, and a bounded run reserves that whole
# allowance (about 73k tokens here; with one search round about 210k): 100k
# admit the step only without its search.
@pytest.mark.parametrize("remaining,succeeds,context_room", [(100_000, True, None), (100, False, None), (100_000, False, 0)])
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
    ref = agent_quota.quota_ref(store.db, UID, agent_quota.day_key() + agent_quota.LEDGER_UNIT)
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


@pytest.mark.parametrize("reported,remaining", [(0, 1), (1, 0), (3, -2)])
def test_search_budget_books_the_reported_count_including_an_overrun(store, reported, remaining):
    calls = []
    class Completion(AgentCompletion):
        def stream(self, *, model, messages, **kwargs):
            calls.append(kwargs["native_searches"])
            self.text, self.finish_reason = "Answer.", "stop"
            self.usage = measured_usage({"prompt_tokens": 50, "completion_tokens": 20, "cost": .001,
                "server_tool_use_details": {"web_search_requests": reported}}, model, searches_enabled=True)
            yield {"type": "delta", "text": self.text}
    # Room for the search reservation in the daily allowance.
    agent_budget_config.store(store.db).save(expected_revision=0, updated_by="admin", tier_limits={"pro": 5_000_000})
    loop = make_loop(store, Script())
    loop.factory = Completion
    loop.search_remaining = 1
    list(loop.run())
    assert calls == [1]
    assert saved_turn(store, loop)["status"] == "completed"
    # The overrun is debt: later reservations get no search until it is paid.
    assert loop.search_remaining == remaining


def test_unknown_terminal_usage_releases_admission_and_utc_day_is_separate(store, monkeypatch):
    loop = make_loop(store, Script())
    monkeypatch.setattr(agent_quota, "day_key", lambda: "2026-09-19")
    assert store.claim(UID, loop.chat_id, loop.turn_id, loop.model, run_token=loop.run_token,
        policy=loop.policy.snapshot(), reservation=(500, priced(500)))
    store.settle(UID, loop.chat_id, loop.turn_id, completion=receipt(measured=False), status="cancelled", final=False)
    quota = agent_quota.quota_ref(store.db, UID, "2026-09-19" + agent_quota.LEDGER_UNIT).get().to_dict()
    assert quota['reserved'] == 0 and quota['unknown'] == quota['unknown_released'] == 500
    assert agent_quota.public(agent_quota.quota_ref(store.db, UID, "2026-09-20" + agent_quota.LEDGER_UNIT).get().to_dict())["remaining"] == 250000


def test_a_run_past_midnight_settles_the_old_day_and_reserves_on_the_new_one(store, monkeypatch):
    loop = make_loop(store, Script())
    args = (UID, loop.chat_id, loop.turn_id)
    monkeypatch.setattr(agent_quota, "day_key", lambda: "2026-09-19")
    assert store.claim(*args, loop.model, run_token=loop.run_token, policy=loop.policy.snapshot(), reservation=(100, priced(100)))
    store.settle(*args, completion=receipt(measured=False), status="succeeded", final=False)
    monkeypatch.setattr(agent_quota, "day_key", lambda: "2026-09-20")
    assert store.claim(*args, loop.model, step="completion:1", run_token=loop.run_token, reservation=(50, priced(50)))
    previous = agent_quota.quota_ref(store.db, UID, '2026-09-19' + agent_quota.LEDGER_UNIT).get().to_dict()
    assert previous['reserved'] == 0 and previous['unknown'] == previous['unknown_released'] == 100
    # Only the new step's own reservation: no hold moves along (since 2026-10-31).
    assert agent_quota.quota_ref(store.db, UID, "2026-09-20" + agent_quota.LEDGER_UNIT).get().to_dict()["reserved"] == 50


def test_disconnect_during_review_settles_every_paid_call_and_marks_stopped(store):
    script = Script()
    loop = make_loop(store, script, reviewers=True)
    source = loop.run()
    for event in source:
        if event["type"] == "review" and event["review"]["status"] == "running":
            break
    source.close()
    saved = saved_turn(store, loop)
    assert saved["status"] == "failed" and saved["assistant_response"] == "The first option costs 100."
    # A review still running when the run closes is marked stopped; one that
    # had already finished keeps its result.
    review = saved["agent_review"]
    assert review["status"] in {"cancelled", "succeeded"}
    assert not any(row["status"] in {"waiting", "running"} for row in review["audit"]["reviewers"])
    root = store.receipt_ref(UID, loop.chat_id, loop.turn_id).get().to_dict()
    assert "running" not in root["step_states"].values()
    assert root["run_status"] == "cancelled"


def test_later_run_failure_keeps_finished_review_result(store):
    """A failure after the reviewers finished must not relabel the reviewed answer."""
    loop = make_loop(store, Script(), reviewers=True)
    # The app runs the review itself (app_registry, _finish_review).
    review = loop.app_registry.tools["audit_answer"]
    def review_then_fail(*args, **kwargs):
        review.execute(*args, **kwargs)
        raise RuntimeError("late provider failure")
    loop.app_registry.tools["audit_answer"] = replace(review, execute=review_then_fail)
    with pytest.raises(RuntimeError):
        list(loop.run())
    saved = saved_turn(store, loop)
    assert saved["status"] == "failed"
    assert saved["agent_review"]["status"] == "succeeded"
    assert [row["status"] for row in saved["agent_review"]["audit"]["reviewers"]] == ["completed", "completed"]


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
    saved = saved_turn(store, loop)
    assert saved["status"] == "completed"
    # One failed write is retried; three in a row cost that one answer.
    assert len(saved["agent_review"]["comparisons"][0]["answers"]) == (2 if failures == 1 else 1)
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


def test_one_model_is_enough_and_more_than_the_run_families_are_refused():
    from app.core import config as cfg
    assert list(comparison_selection({"anthropic": "claude-haiku-4-5"})) == ["anthropic"]
    with pytest.raises(ValueError, match=f"between one and {cfg.MAX_RUN_FAMILIES} reviewers"):
        comparison_selection({})


def test_answer_cut_off_at_the_output_limit_is_kept_as_marked_evidence(store):
    script = Script(length_model="The first option costs 100. It also")
    loop = make_loop(store, script)
    list(loop.run())
    review = saved_turn(store, loop)["agent_review"]
    comparison = review["comparisons"][0]
    assert comparison["failed_models"] == []
    assert len(comparison["answers"]) == 2
    cut = [a for a in comparison["answers"] if a["provider"] == "openai"][0]
    assert cut["truncated"] is True and cut["text"] == "The first option costs 100. It also"
    assert not any(a.get("truncated") for a in comparison["answers"] if a["provider"] != "openai")


def test_output_limit_without_text_names_the_cause_without_retry_advice(store, monkeypatch):
    notes = []
    publish = store.publish_agents
    def capture(*args, updates, **kwargs):
        notes.extend(message["text"] for _, _, message, _ in updates if message and message.get("kind") == "failure")
        return publish(*args, updates=updates, **kwargs)
    monkeypatch.setattr(store, "publish_agents", capture)
    script = Script(length_model="")
    loop = make_loop(store, script)
    list(loop.run())
    review = saved_turn(store, loop)["agent_review"]
    failed = review["comparisons"][0]["failed_models"]
    assert [f["failure"]["code"] for f in failed] == ["output_limit"]
    assert notes == ["The model used its whole output allowance before it finished an answer. "
                     "The comparison uses the other answers."]


@pytest.mark.parametrize("empties, failed", [(1, []), (2, ["empty_answer"])])
def test_an_answer_that_ends_without_a_word_gets_one_more_attempt(store, empties, failed):
    # gpt-oss-120b reasoned, searched and stopped without text once in thirteen
    # identical calls (2026-10-15): chance, not an output limit.
    script = Script(empty_model=empties)
    loop = make_loop(store, script)
    list(loop.run())
    saved = saved_turn(store, loop)
    comparison = saved["agent_review"]["comparisons"][0]
    assert [f["failure"]["code"] for f in comparison["failed_models"]] == failed
    assert len(comparison["answers"]) == 2 - len(failed)
    openai = [step for step, model in script.answer_calls if model.startswith("openai")]
    assert [step.rsplit(":", 1)[1] for step in openai] == ["0", "1"]
    assert len({step.rsplit(":", 1)[0] for step in openai}) == 1
    assert saved["status"] == "completed"


THREE = {"anthropic": "claude-haiku-4-5", "openai": "gpt-5.4-mini", "gemini": "gemini-3.5-flash-lite"}


def test_the_step_after_the_last_comparison_writes_the_answer(store):
    script = Script()
    loop = make_loop(store, script, reviewers=True)
    list(loop.run())
    saved = saved_turn(store, loop)
    assert saved["status"] == "completed"
    assert saved["agent_review"]["status"] == "succeeded"
    # Every comparison asks the whole selection.
    assert saved["agent_review"]["comparisons"][0]["asked"] == ["anthropic", "openai"]
    # compare_models, then the step that reads the answers writes the answer;
    # the app runs the review itself, no routing step calls audit_answer.
    assert [step for step, _ in script.calls if step.startswith("completion:")] == ["completion:0", "completion:1"]


def test_comparison_models_answer_at_the_same_time(store):
    import threading
    barrier = threading.Barrier(3, timeout=5)

    class Parallel(Script):
        def factory(self):
            base = type(super().factory())
            class Completion(base):
                def stream(self, *, model, messages, **kwargs):
                    if not self.step_id.startswith("completion:"):
                        barrier.wait()  # breaks unless all three answer models run at once
                    yield from super().stream(model=model, messages=messages, **kwargs)
            return Completion()

    script = Parallel()
    loop = make_loop(store, script, models=THREE)
    assert loop.policy.max_parallel == 2
    list(loop.run())
    review = saved_turn(store, loop)["agent_review"]
    assert [len(c["answers"]) for c in review["comparisons"]] == [3]
    assert review["comparisons"][0]["status"] == "succeeded"


class Straggler(Script):
    """The Gemini answer only arrives once `release` is set (or never).
    ``synthesis_evidence``: the messages the step that writes the answer reads."""

    def __init__(self, *, release_on_answer, partial="", **kwargs):
        import threading
        super().__init__(**kwargs)
        self.release = threading.Event()
        self.release_on_answer = release_on_answer
        self.partial = partial
        self.synthesis_evidence = None

    def factory(self):
        from app.services.llm.provider_runtime import current_provider_cancellation
        base = type(super().factory())
        script = self
        class Completion(base):
            def stream(self, *, model, messages, **kwargs):
                if self.step_id.startswith("completion:") and int(self.step_id.split(":")[-1]) >= script.compares:
                    script.synthesis_evidence = json.dumps(messages)
                    if script.release_on_answer:
                        script.release.set()
                        comparison = script.loop.comparison
                        cid = comparison.comparisons[-1]["id"]
                        for _ in range(200):
                            if "gemini" in comparison._raw[cid]:
                                break
                            time.sleep(.02)
                elif not self.step_id.startswith("completion:") and model.model.startswith("google"):
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


def time_runs_out_after(loop, answers=2):
    """The time before the answer must start is up (answer_time_left) once
    ``answers`` answers of the newest comparison are in: a model still
    writing then is a straggler."""
    def left():
        comparison = loop.comparison
        if not comparison.comparisons:
            return 600
        return 0 if len(comparison._raw.get(comparison.comparisons[-1]["id"], {})) >= answers else 600
    loop.answer_time_left = left
    return loop


def test_an_answer_after_the_deadline_is_late_and_stays_out_of_what_the_agent_read(store):
    script = Straggler(release_on_answer=True, depth="quick")
    loop = time_runs_out_after(make_loop(store, script, models=THREE))
    list(loop.run())
    saved = saved_turn(store, loop)
    comparison = saved["agent_review"]["comparisons"][0]
    assert "second option is cheaper" not in script.synthesis_evidence
    assert sorted(comparison["synthesis_providers"]) == ["anthropic", "openai"]
    # The agent was told which answer it writes without.
    result = tool_results(loop)["call_0"]
    # Anonymous: the agent weighs the answers, not the models' names.
    assert len(result["answers"]) == 2 and all("family" not in a and "model" not in a for a in result["answers"])
    assert [m["family"] for m in result["missing_answers"]] == ["gemini"]
    late = [a["provider"] for a in comparison["answers"] if a.get("late")]
    assert late == ["gemini"] and len(comparison["answers"]) == 3
    assert comparison["status"] == "succeeded" and not comparison["failed_models"]
    assert "pending_models" not in comparison and saved["status"] == "completed"


def test_a_model_still_writing_at_the_answer_is_stopped_and_reported(store):
    script = Straggler(release_on_answer=False, depth="quick")
    loop = time_runs_out_after(make_loop(store, script, models=THREE))
    list(loop.run())
    saved = saved_turn(store, loop)
    comparison = saved["agent_review"]["comparisons"][0]
    assert saved["status"] == "completed"
    [cut] = comparison["failed_models"]
    assert cut["failure"] == {"code": "late_cutoff", "error": "It was still writing when the answer was finished."}
    assert len(comparison["answers"]) == 2 and comparison["status"] == "partial"
    assert not any(t.is_alive() for t, _ in loop.comparison._running[comparison["id"]].values())
    view = store.delegation_view(UID, loop.chat_id, loop.turn_id)
    [stopped] = [a for a in view["agents"] if a.get("status") == "stopped"]
    notes = [m["text"] for m in store.delegation_view(UID, loop.chat_id, loop.turn_id, agent_id=stopped["id"])["messages"]
             if m["kind"] == "failure"]
    assert notes == ["It was still writing when the answer was finished. The answer uses the other answers."]


def test_text_of_a_model_stopped_mid_answer_is_kept_as_incomplete_but_never_read(store):
    script = Straggler(release_on_answer=False, partial="Gemini: the first half of an answer", depth="quick")
    loop = time_runs_out_after(make_loop(store, script, models=THREE))
    list(loop.run())
    comparison = saved_turn(store, loop)["agent_review"]["comparisons"][0]
    [stopped] = comparison["failed_models"]
    assert stopped["failure"]["code"] == "late_cutoff"
    assert stopped["partial_text"] == "Gemini: the first half of an answer"
    # Neither the step that writes the answer nor the saved answers hold unfinished text.
    assert "first half" not in script.synthesis_evidence
    assert all("first half" not in a["text"] for a in comparison["answers"])
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
        policy = AgentPolicy()
        outgoing = type("Q", (), {"put_nowait": staticmethod(lambda item: None)})
    tools = ComparisonTools(Loop(), {})
    tools.comparisons = [{"id": "c", "answers": [], "failed_models": [
        {"model": "m", "failure": {"code": "late_cutoff"}, "partial_text": "x" * 700_000}]}]
    tools.checkpoint()
    assert "partial_text" not in saved[0]["comparisons"][0]["failed_models"][0]
    assert saved[0]["comparisons"][0]["failed_models"][0]["model"] == "m"


@pytest.mark.parametrize("depth,expected", [("quick", "Answer briefly"), ("full", "as thoroughly as the task needs"),
                                             (None, "as thoroughly as the task needs")])
def test_depth_sets_the_answer_models_length_guidance(store, depth, expected):
    script = Script(depth=depth)
    loop = make_loop(store, script)
    list(loop.run())
    assert script.prompts and all(expected in prompt[0]["content"] for prompt in script.prompts)
    assert "6000 characters" not in json.dumps(script.prompts)
    review = saved_turn(store, loop)["agent_review"]
    assert review["comparisons"][0]["depth"] == (depth or "full")


def test_the_comparison_models_are_told_an_agent_weighs_their_answers():
    from app.services.agent_comparison import comparison_system_prompt
    prompt = comparison_system_prompt("full", 3)
    assert "An AI agent working for the user weighs your answer" in prompt
    assert "checked" not in prompt and "Consensus pipeline" not in prompt


def test_compare_models_offers_only_question_context_files_and_depth():
    """No progress paragraph, model choice or memory field (since
    2026-10-31): the schema refuses them."""
    from pydantic import ValidationError
    from app.services.agent_comparison import AuditCompareArgs
    assert set(AuditCompareArgs.model_json_schema()["properties"]) == {"question", "context", "file_ids", "depth"}
    assert AuditCompareArgs.model_validate({"question": "Q?"}).depth == "full"
    for retired in ({"status_update": "S"}, {"reason": "R"}, {"models": ["openai", "anthropic"]}, {"memory": []}):
        with pytest.raises(ValidationError):
            AuditCompareArgs.model_validate({"question": "Q?", **retired})


def test_the_agent_sees_only_its_own_tools_and_the_app_runs_the_review(store):
    loop = make_loop(store, Script())
    assert list(loop.registry.tools)[0] == "compare_models"
    # The answer is the agent's plain text: no tool ends the steering, and
    # no tool checks a pasted text.
    assert not {"answer", "check_text", "judge_answer", "audit_answer"} & set(loop.registry.tools)
    assert set(loop.app_registry.tools) == {"audit_answer"}


def test_a_failed_run_does_not_leave_a_model_shown_as_still_answering(store):
    class Failing(Straggler):
        def factory(self):
            base = type(super().factory())
            class Completion(base):
                def stream(self, *, model, messages, **kwargs):
                    # The step that writes the answer, and its one retry (since 2026-10-27).
                    if self.step_id in {"completion:1", "completion:2"}:
                        raise RuntimeError("answer step failed")
                    yield from super().stream(model=model, messages=messages, **kwargs)
            return Completion()

    script = Failing(release_on_answer=False, depth="quick")
    loop = time_runs_out_after(make_loop(store, script, models=THREE))
    with pytest.raises(Exception):
        list(loop.run())
    comparison = saved_turn(store, loop)["agent_review"]["comparisons"][0]
    assert "pending_models" not in comparison
    assert [m["model"] for m in comparison["failed_models"]] == ["google/gemini-3.5-flash-lite"]
    assert not any(t.is_alive() for t, _ in loop.comparison._running[comparison["id"]].values())


def test_answer_allowance_respects_the_saved_review_size(store):
    from app.services.agent_comparison import REVIEW_ANSWER_CHARS, CHARS_PER_TOKEN
    loop = make_loop(store, Script())
    shares = loop.comparison._output_shares({f"model-{index}": loop.model for index in range(6)})
    assert len(shares) == 6 and all(share <= REVIEW_ANSWER_CHARS // 6 // CHARS_PER_TOKEN for share in shares.values())


@pytest.mark.parametrize("depth", ["quick", "full"])
def test_every_comparison_waits_for_the_slowest_model(store, depth):
    """Since 2026-10-31 always (until then the default of the setting "Answer
    start"): the most careful model is often the slowest, and it is never cut
    while there is time."""
    import threading
    script = Straggler(release_on_answer=False, depth=depth)
    threading.Timer(.4, script.release.set).start()
    loop = make_loop(store, script, models=THREE)
    list(loop.run())
    comparison = saved_turn(store, loop)["agent_review"]["comparisons"][0]
    assert "second option is cheaper" in script.synthesis_evidence
    assert sorted(comparison["synthesis_providers"]) == ["anthropic", "gemini", "openai"]
    assert not any(a.get("late") for a in comparison["answers"])


class Plan(Script):
    """Scripted agent steps: ``plan[i]`` is what completion:i does, its
    ``text`` (one delta, after ``sources`` its own search found) and then its
    ``tools`` [(name, args)]. Comparison answers come from Script;
    ``requests[i]`` holds the messages step i read."""

    def __init__(self, plan, **kwargs):
        super().__init__(**kwargs)
        self.plan = plan
        self.requests = {}

    def factory(self):
        base = type(super().factory())
        script = self
        class Completion(base):
            def stream(self, *, model, messages, **kwargs):
                if not self.step_id.startswith("completion:"):
                    yield from super().stream(model=model, messages=messages, **kwargs)
                    return
                index = int(self.step_id.split(":")[-1])
                script.calls.append((self.step_id, model.model))
                script.requests[index] = json.loads(json.dumps(messages))
                self.usage = measured_usage({"prompt_tokens": 50, "completion_tokens": 20, "cost": .0001}, model)
                step = script.plan[index]
                if step.get("sources"):
                    self.sources = list(step["sources"])
                if step.get("text"):
                    self.text = step["text"]
                    yield {"type": "delta", "text": self.text}
                self.tool_calls = [{"id": f"call_{index}_{n}", "type": "function",
                                    "function": {"name": name, "arguments": json.dumps(args)}}
                                   for n, (name, args) in enumerate(step.get("tools", ()))]
                self.finish_reason = "tool_calls" if self.tool_calls else "stop"
        return Completion()


ANSWER = "The first option costs 100."
LONG_REPLY = "The first option costs 100 euros a month. " * 30
FOUND = [{"url": "https://example.org/found", "title": "Found"}]


def compare(question="Which option costs less?", **args):
    return "compare_models", {"question": question, **args}


def tool_results(loop):
    return {m["tool_call_id"]: json.loads(m["content"]) for m in loop.messages if m.get("role") == "tool"}


def deltas(events):
    return "".join(e["text"] for e in events if e.get("type") == "delta")


def orchestrator_steps(script):
    return [step for step, _ in script.calls if step.startswith("completion:")]


def test_a_long_reply_after_own_research_is_the_answer(store):
    """The agent's own research is the way to its answer (since 2026-10-31
    for every account): a reply after its search stands and is reviewed, it
    is not sent back for a comparison."""
    script = Plan([{"sources": FOUND, "text": LONG_REPLY}])
    loop = make_loop(store, script)
    events = list(loop.run())
    saved = saved_turn(store, loop)
    assert orchestrator_steps(script) == ["completion:0"]
    assert saved["status"] == "completed" and saved["consensus"] == LONG_REPLY == deltas(events)
    assert saved["agent_review"]["mode"] == "audit" and saved["agent_review"]["versions"][-1]["text"] == LONG_REPLY
    assert not any(m["content"].startswith("App rule") for m in loop.messages if m["role"] == "user")
    # Its own search put pages in view: memory locks without reviewers.
    assert loop.memory_locked is True


def test_a_long_answer_without_a_comparison_is_one_streamed_reviewed_call(store):
    """Without a comparison the agent's text is the answer: one call,
    streamed and saved as the version the reviewers review."""
    script = Plan([{"text": LONG_REPLY}])
    loop = make_loop(store, script, reviewers=True)
    events = list(loop.run())
    saved = saved_turn(store, loop)
    assert saved["status"] == "completed" and saved["assistant_response"] == LONG_REPLY
    assert orchestrator_steps(script) == ["completion:0"] and not loop.comparison.comparisons
    review = saved["agent_review"]
    assert review["status"] == "succeeded" and review["versions"][-1]["text"] == LONG_REPLY
    assert review["comparisons"] == [] and not script.prompts
    assert [e["status"] for e in events if e.get("kind") == "tool" and e.get("name") == "audit_answer"] == [
        "running", "succeeded"]
    assert deltas(events) == LONG_REPLY


def test_a_greeting_is_sent_as_plain_text(store):
    loop = make_loop(store, Plan([{"text": "Hello! How can I help?"}]))
    events = list(loop.run())
    assert loop.completion.text == deltas(events) == "Hello! How can I help?"
    assert not loop.comparison.comparisons
    assert not any("App rule" in m["content"] for m in loop.messages if m["role"] == "user")


def test_text_next_to_a_failed_comparison_is_never_the_answer(store):
    """Review 2026-10-11/12, then [compare_models, answer] in one batch: an
    answer written in the same step as a comparison that fails validation is
    no answer. The text is taken back, the agent reads the error, compares,
    and writes the answer from the comparison."""
    script = Plan([{"text": LONG_REPLY, "tools": [compare(depth="deep")]}, {"tools": [compare()]}, {"text": ANSWER}])
    loop = make_loop(store, script)
    events = list(loop.run())
    results = tool_results(loop)
    assert "error" in results["call_0_0"] and len(results["call_1_0"]["answers"]) == 2
    # The answer came right after the comparison's answers, without an app note.
    assert script.requests[2][-1]["role"] == "tool" and script.requests[2][-1]["tool_call_id"] == "call_1_0"
    saved = saved_turn(store, loop)
    assert saved["consensus"] == ANSWER and saved["agent_review"]["versions"][-1]["text"] == ANSWER
    assert len(loop.comparison.comparisons) == 1
    # What streamed of the first text was taken back before the answer.
    clear = next(i for i, e in enumerate(events) if e.get("kind") == "status" and e.get("clear_response"))
    assert deltas(events[:clear]) == LONG_REPLY and deltas(events[clear:]) == ANSWER


@pytest.mark.parametrize("outage", [1, 2])
def test_a_database_outage_while_saving_a_failed_answer_does_not_stop_the_turn(store, monkeypatch, outage):
    """Audit A12: a transient error while recording one model's failure
    cancelled the whole turn ("This response was stopped"). Since 2026-10-22
    the record can share its write with other sessions' updates (the run's
    journal batches them): an outage that outlasts the retry still costs no
    other answer, each update then tries on its own."""
    from google.api_core.exceptions import ServiceUnavailable
    from app.services import agent_delegation
    monkeypatch.setattr(agent_delegation, "TERMINAL_RETRY_SECONDS", 0)
    script = Plan([{"tools": [compare()]}, {"text": ANSWER}], fail_model=True)
    loop = make_loop(store, script)
    publish, failures = store.publish_agents, []
    def flaky(*args, updates, **kwargs):
        failing = [agent_id for agent_id, _, message, _ in updates if (message or {}).get("kind") == "failure"]
        if failing and len(failures) < outage:
            failures.append(failing[0])
            raise ServiceUnavailable("Firestore unavailable")
        return publish(*args, updates=updates, **kwargs)
    monkeypatch.setattr(store, "publish_agents", flaky)
    list(loop.run())
    saved = saved_turn(store, loop)
    assert len(failures) == outage
    assert saved["status"] == "completed" and saved["consensus"] == ANSWER
    [missing] = tool_results(loop)["call_0_0"]["missing_answers"]
    assert missing["family"] == "anthropic"


def test_a_comparison_with_one_answer_names_the_missing_one(store):
    """Review 2026-10-12: one model failed and the answer rested on the
    single other answer, unseen. The agent reads that only one answered and
    which one is missing before it writes; the comparison is partial."""
    script = Plan([{"tools": [compare()]}, {"text": ANSWER}], fail_model=True)
    loop = make_loop(store, script)
    list(loop.run())
    result = tool_results(loop)["call_0_0"]
    assert len(result["answers"]) == 1 and result["instruction"].startswith("Only one model answered.")
    [missing] = result["missing_answers"]
    assert missing["family"] == "anthropic" and missing["reason"]
    saved = saved_turn(store, loop)
    assert saved["status"] == "completed" and saved["consensus"] == ANSWER
    assert saved["agent_review"]["comparisons"][0]["status"] == "partial"


def test_a_comparison_after_the_answer_is_written_is_refused(store):
    script = Script()
    loop = make_loop(store, script)
    loop.comparison.text = "Written."
    with pytest.raises(ValueError, match="already being written"):
        loop.comparison.compare(loop.comparison.tools[0].arguments.model_validate({"question": "Q?"}),
                                cancellation=loop.cancellation)
    assert not loop.comparison.comparisons and not script.prompts


def test_newer_openai_generations_count_as_reasoning_models_for_temperature():
    from app.services.llm.consensus_engine import _effective_temperature
    assert _effective_temperature("openai", "openai/gpt-6-luna", 0.2) is None
    assert _effective_temperature("openai", "openai/gpt-4o", 0.2) == 0.2
