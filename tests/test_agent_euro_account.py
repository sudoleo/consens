"""The daily account in euros (Max, 2026-10-31).

Every call takes what it cost from the account, in whole micro-euros at the
fixed NANO_USD_PER_MICRO_EUR: a cheap model goes further than a dear one, a
web search counts its fee, a cache read its discounted price, an audit
reviewer the same as any call. Ledgers of the token account stay apart.
"""
from dataclasses import replace

from app.services import agent_budget_config, agent_quota
from app.services.agent_costs import RunCosts, worst_case_nanos
from app.services.agent_policy import AgentPolicy
from app.services.llm.agent_client import AgentCompletion, AgentModel, measured_usage
from test_agent_runs import UID, PRICED, store, priced  # noqa: F401  (fixtures)
from test_agent_delegation import make_loop


DEAR = replace(PRICED, model="anthropic/claude-opus-4.7", label="Dear", selection_id="dear",
               input_usd_per_million="15", output_usd_per_million="75",
               cache_read_usd_per_million="1.5", cache_write_usd_per_million="18.75")
USAGE = {"prompt_tokens": 10_000, "completion_tokens": 1_000}


def settled(store, model, raw):
    loop = make_loop(store)
    args = (UID, loop.chat_id, loop.turn_id)
    store.claim(*args, model, run_token=loop.run_token, policy=loop.policy.snapshot(),
                reservation=(20_000, priced(20_000)))
    value = AgentCompletion()
    value.text, value.finish_reason = "ok", "stop"
    value.usage = measured_usage(raw, model)
    store.settle(*args, completion=value, status="succeeded", final=False)
    return store.receipt_ref(*args).get().to_dict()


def test_the_same_tokens_cost_a_cheap_model_a_fraction_of_a_dear_one(store):
    cheap = settled(store, PRICED, USAGE)["quota_charged"]
    dear = settled(store, DEAR, USAGE)["quota_charged"]
    # 10,000 x $0.10 + 1,000 x $0.50 per million = $0.0015 = 1,305 micro-euros;
    # at $15/$75 a hundred and fifty times that.
    assert cheap == -(-1_500_000 // 1_150) == 1_305
    assert dear == -(-225_000_000 // 1_150) == 195_653
    assert agent_quota.snapshot(store.db, UID)["used"] == cheap + dear


def test_the_provider_cost_counts_with_search_and_cache_as_billed(store):
    """OpenRouter's usage.cost includes the search fee and the cache discount:
    the account takes exactly that, with no weights on top."""
    raw = {**USAGE, "prompt_tokens_details": {"cached_tokens": 9_000}, "cost": 0.0215,
           "server_tool_use_details": {"web_search_requests": 2}}
    receipt = settled(store, PRICED, raw)
    assert receipt["quota_charged"] == agent_budget_config.micro_eur(21_500_000) == 18_696
    assert receipt["usage"]["cached_input_tokens"] == 9_000


def test_a_reviewer_counts_what_it_cost_like_any_call(store):
    loop = make_loop(store)
    args = (UID, loop.chat_id, loop.turn_id)
    store.claim(*args, loop.model, run_token=loop.run_token, policy=loop.policy.snapshot(),
                reservation=(100, priced(100)))
    reviewer = "c" * 32
    store.publish_agent(*args, run_token=loop.run_token, agent_id=reviewer,
                        patch={"assignment": {"goal": "Check"}, "status": "working", "kind": "audit"})
    step = f"agent:{reviewer}:0"
    store.claim(*args, PRICED, step=step, run_token=loop.run_token, policy=loop.policy.snapshot(),
                reservation=(5_000, priced(5_000)))
    assert store.receipt_ref(*args, step).get().to_dict()["quota_reserved"] == 5_000
    value = AgentCompletion()
    value.text, value.finish_reason = "ok", "stop"
    value.usage = measured_usage(USAGE, PRICED)
    store.settle(*args, completion=value, status="succeeded", step=step, final=False)
    assert store.receipt_ref(*args, step).get().to_dict()["quota_charged"] == 1_305


def test_the_euro_ledger_is_apart_from_the_token_ledger(store, monkeypatch):
    """A call reserved in tokens before the switch settles into its own token
    ledger (no "_eur"), never into the euro one."""
    monkeypatch.setattr(agent_quota, "day_key", lambda: "2026-10-31")
    config = agent_budget_config.get_config(store.db)
    assert agent_quota.period_key(config) == "2026-10-31_eur"
    loop = make_loop(store)
    args = (UID, loop.chat_id, loop.turn_id)
    store.claim(*args, PRICED, run_token=loop.run_token, policy=loop.policy.snapshot(),
                reservation=(30_000, priced(400)))
    # As written by the token account: 30,000 tokens held in the old ledger.
    receipt = store.receipt_ref(*args)
    store._transaction(lambda tx: tx.update(receipt, {"quota_day": "2026-10-31", "quota_reserved": 30_000}))
    tokens = agent_quota.quota_ref(store.db, UID, "2026-10-31")
    tokens.set({"used": 120_000, "reserved": 30_000})
    euros = agent_quota.quota_ref(store.db, UID, "2026-10-31_eur")
    euros.set({"used": 0, "reserved": 400})
    value = AgentCompletion()
    value.text, value.finish_reason = "ok", "stop"
    value.usage = measured_usage(USAGE, PRICED)
    store.settle(*args, completion=value, status="succeeded", final=False)
    assert tokens.get().to_dict()["reserved"] == 0
    # The euro ledger keeps its own hold and charge untouched.
    assert euros.get().to_dict() == {"used": 0, "reserved": 400}
    snapshot = agent_quota.snapshot(store.db, UID)
    assert snapshot["unit"] == "micro_eur" and snapshot["reserved"] == 400


def test_a_reservation_is_what_the_call_is_expected_to_cost():
    """Not the worst case: the input once, the prefix the session's last call
    held in the cache at the cache-read price, the output and the search
    rounds its kind of call measured on that model so far."""
    from decimal import Decimal
    from app.services.agent_costs import OUTPUT_START_TOKENS, SEARCH_ROUND_TOKENS, search_cost_nanos
    costs = RunCosts(AgentPolicy(account_budget_only=True))
    model = replace(DEAR, max_output_tokens=65_536, context_length=1_000_000)
    messages = [{"role": "user", "content": "Which option? " * 2_000}]
    inputs = costs.inputs(messages)
    tokens, cost = costs.estimate(model, messages, session="agent")
    # Fresh input at the cache-write price (dearer here), the output's start value.
    assert tokens == inputs + OUTPUT_START_TOKENS
    assert cost == int((inputs * Decimal("18.75") + OUTPUT_START_TOKENS * 75) * 1000)
    # With search: the expected rounds' results and fees, one round to begin with.
    searching = costs.estimate(model, messages, native_searches=5, session="agent")
    assert searching[0] == tokens + SEARCH_ROUND_TOKENS
    assert searching[1] == cost + int(SEARCH_ROUND_TOKENS * Decimal("18.75") * 1000) + search_cost_nanos(model)
    # The session's call measured its cache and a short output, and searched twice.
    usage = measured_usage({"prompt_tokens": inputs, "completion_tokens": 1_000,
                            "prompt_tokens_details": {"cached_tokens": 0, "cache_write_tokens": inputs - 100},
                            "server_tool_use_details": {"web_search_requests": 2}}, model)
    costs.reconcile((tokens, cost), usage, model=model, session="agent", searches=5)
    after = costs.estimate(model, messages, native_searches=5, session="agent")
    cached, fresh = inputs - 100, 100 + 2 * SEARCH_ROUND_TOKENS
    assert after[1] == int((cached * Decimal("1.5") + fresh * Decimal("18.75") + 1_000 * 75) * 1000) \
        + 2 * search_cost_nanos(model)
    # Far below the worst case, and the output limit sent stays the model's own.
    assert after[1] * 20 < worst_case_nanos(model, inputs * 6 + 5 * 32_000 * 6, 65_536 * 6)
    # Another session reads nothing from that cache.
    assert costs.estimate(model, messages, session="reviewer")[1] > costs.estimate(model, messages, session="agent")[1]


def test_every_comparison_model_gets_the_same_output_whatever_is_left(store, monkeypatch):
    from app.core import config as cfg
    from app.services.agent_comparison import CHARS_PER_TOKEN, REVIEW_ANSWER_CHARS
    from test_agent_comparison import Script, make_loop as comparison_loop
    loop = comparison_loop(store, Script())
    monkeypatch.setattr(cfg, "MAX_TOKENS", 500)
    shares = loop.comparison._output_shares({"cheap": PRICED, "dear": DEAR})
    for left in (0, 10, 5_000_000):
        monkeypatch.setattr(agent_quota, "remaining_allowance", lambda db, uid, **kwargs: left)
        assert loop.comparison._output_shares({"cheap": PRICED, "dear": DEAR}) == shares
    assert shares == {"cheap": REVIEW_ANSWER_CHARS // 2 // CHARS_PER_TOKEN, "dear": REVIEW_ANSWER_CHARS // 2 // CHARS_PER_TOKEN}


def test_worst_case_prices_every_input_at_the_dearest_input_price():
    assert worst_case_nanos(DEAR, 1_000, 0) == 1_000 * 18_750
    assert worst_case_nanos(DEAR, 0, 100) == 100 * 75_000
    assert worst_case_nanos(AgentModel(model="x/free", input_usd_per_million="0", output_usd_per_million="0",
                                       cache_read_usd_per_million="0", cache_write_usd_per_million=""), 5, 5) == 0
