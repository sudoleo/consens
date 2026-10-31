"""R07: bounded uncertainty for Agent calls without final usage.

Started calls without final usage are charged a bounded estimate (not released
completely, not charged completely), later reconciled exactly once against the
provider's measurement. Calls that provably never started stay free.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest

from app.services import agent_quota, agent_usage_reconciliation as reconciliation
from app.services.agent_budget_config import NANO_USD_PER_MICRO_EUR as EUR
from app.services.llm.agent_client import AgentCompletion
from test_agent_runs import UID, store, receipt, totals, priced
from test_agent_delegation import make_loop


def unknown_call(store, *, reservation=500, generation_id="gen-1", step="completion:0", loop=None):
    """``reservation`` micro-euros of the account (its cost: that many x EUR nano-USD)."""
    loop = loop or make_loop(store)
    args = (UID, loop.chat_id, loop.turn_id)
    store.claim(*args, loop.model, run_token=loop.run_token, policy=loop.policy.snapshot(),
                step=step, reservation=(reservation, reservation * EUR))
    value = receipt(measured=False)
    value.generation_id = generation_id
    store.settle(*args, completion=value, status="failed", step=step, final=False)
    return loop, args


def test_unknown_usage_is_charged_a_bounded_estimate_not_released_or_fully_charged():
    data = agent_quota.settle(agent_quota.reserve({}, 100, limit=100), 100, None)
    budget = agent_quota.public(data, limit=100)
    assert budget["used"] == 0 and budget["reserved"] == 0
    assert budget["estimated"] == 50 and budget["remaining"] == 50
    # A provisional lower bound above the floor is charged as the estimate.
    provisional = {"input_tokens": 80, "output_tokens": 5, "provisional": True, "complete": False,
                   "estimated_cost_nano_usd": 85 * EUR}
    data = agent_quota.settle(agent_quota.reserve({}, 100, limit=100), 100, provisional)
    assert agent_quota.public(data, limit=100)["estimated"] == 85


def test_repeated_unknown_calls_are_bounded_but_measured_calls_do_not_lock():
    data = {}
    for _ in range(3):
        data = agent_quota.settle(agent_quota.reserve(data, 100, limit=250), 100, None)
    # The fourth unknown call no longer fits; it is refused before starting.
    with pytest.raises(agent_quota.AgentTokenBudgetExceeded):
        agent_quota.reserve(data, 150, limit=250)
    # Normal measured calls release their holds completely.
    measured = {"input_tokens": 10, "output_tokens": 5, "estimated_cost_nano_usd": 15 * EUR}
    clean = agent_quota.settle(agent_quota.reserve({}, 200, limit=250), 200, measured)
    assert agent_quota.public(clean, limit=250)["remaining"] == 235


def test_provably_unstarted_calls_are_still_released_completely(store):
    loop = make_loop(store)
    args = (UID, loop.chat_id, loop.turn_id)
    store.claim(*args, loop.model, run_token=loop.run_token, policy=loop.policy.snapshot(), reservation=(500, priced(500)))
    value = AgentCompletion()
    value.record_unstarted(loop.model)
    store.settle(*args, completion=value, status="cancelled", final=False)
    budget = agent_quota.snapshot(store.db, UID)
    assert budget["estimated"] == budget["used"] == budget["reserved"] == 0
    assert budget["remaining"] == budget["limit"]
    assert "quota_reconcile" not in store.receipt_ref(*args).get().to_dict()


def test_reconciliation_replaces_the_estimate_exactly_once(store):
    _loop, args = unknown_call(store)
    saved = store.receipt_ref(*args).get().to_dict()
    assert saved["quota_reconcile"] == "pending" and saved["quota_estimate"] == 250
    before = agent_quota.snapshot(store.db, UID)
    assert before["estimated"] == 250

    lookups = []
    fetch = lambda generation_id: lookups.append(generation_id) or 130
    assert reconciliation.reconcile_pending(store.db, UID, fetch_usage=fetch)["measured"] == 1
    after = agent_quota.snapshot(store.db, UID)
    assert after["estimated"] == 0 and after["used"] == 130
    assert after["remaining"] == after["limit"] - 130
    assert lookups == ["gen-1"]
    saved = store.receipt_ref(*args).get().to_dict()
    assert saved["quota_reconcile"] == "measured" and saved["quota_measured"] == 130
    assert totals(store)["reconciled_calls"] == 1

    # Repeated passes and a late settlement retry never charge twice.
    assert reconciliation.reconcile_pending(store.db, UID, fetch_usage=fetch)["measured"] == 0
    assert not store.settle(*args, completion=receipt(), status="succeeded", final=False)
    assert agent_quota.snapshot(store.db, UID)["used"] == 130
    assert lookups == ["gen-1"]


def test_a_reviewers_estimate_is_reconciled_at_its_cost(store):
    """Since 2026-10-31 a reviewer's call counts what it cost, like any other
    (until then at half weight, A-K2)."""
    loop = make_loop(store)
    args = (UID, loop.chat_id, loop.turn_id)
    store.claim(*args, loop.model, run_token=loop.run_token, policy=loop.policy.snapshot(),
                reservation=(500, 500 * EUR))
    reviewer = "a" * 32
    store.publish_agent(*args, run_token=loop.run_token, agent_id=reviewer, patch={
        "assignment": {"goal": "Check"}, "status": "working", "kind": "audit"})
    unknown_call(store, reservation=1000, step=f"agent:{reviewer}:0", loop=loop)
    saved = store.receipt_ref(*args, f"agent:{reviewer}:0").get().to_dict()
    # The whole reservation is held, half of it charged as the estimate.
    assert saved["quota_reserved"] == 1000 and saved["quota_estimate"] == 500
    assert reconciliation.reconcile_pending(store.db, UID, fetch_usage=lambda _gid: 130)["measured"] == 1
    assert store.receipt_ref(*args, f"agent:{reviewer}:0").get().to_dict()["quota_measured"] == 130
    assert agent_quota.snapshot(store.db, UID)["used"] == 130


def test_parallel_reconciliation_passes_apply_the_measurement_once(store):
    unknown_call(store)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: reconciliation.reconcile_pending(
            store.db, UID, fetch_usage=lambda _gid: 130), range(4)))
    assert sum(r["measured"] for r in results) == 1
    budget = agent_quota.snapshot(store.db, UID)
    assert budget["used"] == 130 and budget["estimated"] == 0


def test_unavailable_measurement_keeps_the_estimate_and_stops_after_bounded_attempts(store):
    _loop, args = unknown_call(store)
    for _ in range(reconciliation.MAX_ATTEMPTS):
        reconciliation.reconcile_pending(store.db, UID, fetch_usage=lambda _gid: None)
    saved = store.receipt_ref(*args).get().to_dict()
    assert saved["quota_reconcile"] == "final"
    budget = agent_quota.snapshot(store.db, UID)
    assert budget["estimated"] == 250 and budget["used"] == 0
    # Finalized receipts are never looked up again.
    reconciliation.reconcile_pending(store.db, UID, fetch_usage=lambda _gid: pytest.fail("no lookup"))


def test_lookup_errors_count_as_attempts_and_old_receipts_are_finalized(store):
    _loop, args = unknown_call(store)
    def broken(_gid):
        raise RuntimeError("provider down")
    assert reconciliation.reconcile_pending(store.db, UID, fetch_usage=broken)["retry"] == 1
    assert store.receipt_ref(*args).get().to_dict()["quota_reconcile_attempts"] == 1
    later = store.receipt_ref(*args).get().to_dict()["settled_at"] + reconciliation.MAX_AGE + timedelta(seconds=1)
    outcome = reconciliation.reconcile_pending(store.db, UID, fetch_usage=broken, now=later)
    assert outcome["finalized"] == 1
    assert agent_quota.snapshot(store.db, UID)["estimated"] == 250


def test_receipts_without_generation_id_keep_their_estimate_as_final(store):
    _loop, args = unknown_call(store, generation_id="")
    assert store.receipt_ref(*args).get().to_dict()["quota_reconcile"] == "final"
    reconciliation.reconcile_pending(store.db, UID, fetch_usage=lambda _gid: pytest.fail("no lookup"))
    assert agent_quota.snapshot(store.db, UID)["estimated"] == 250


def test_generation_stats_charge_their_total_cost_and_reject_garbage():
    """OpenRouter's ``total_cost`` (dollars) in micro-euros, rounded up."""
    assert reconciliation.generation_charge({"data": {"total_cost": 0.00115, "native_tokens_prompt": 100}}) == 1000
    assert reconciliation.generation_charge({"data": {"total_cost": "0.0023"}}) == 2000
    assert reconciliation.generation_charge({"data": {"total_cost": 0.000001}}) == 1
    # Counts without a cost are not a measurement of it.
    assert reconciliation.generation_charge({"data": {"native_tokens_prompt": 100, "native_tokens_completion": 30}}) is None
    assert reconciliation.generation_charge({"data": {"total_cost": None}}) is None
    assert reconciliation.generation_charge({"data": {"total_cost": -1}}) is None
    assert reconciliation.generation_charge({"data": {"total_cost": True}}) is None
    assert reconciliation.generation_charge([]) is None


def test_every_call_counts_what_it_cost_in_the_account():
    """Max, 2026-10-31: the account counts money. A call takes its cost
    (cache discount, reasoning and search included) in micro-euros, whatever
    kind it is; no weights. A cost that is not final is no measurement."""
    usage = {"input_tokens": 10_000, "output_tokens": 500, "cached_input_tokens": 8_000, "cache_write_tokens": 1_000,
             "estimated_cost_nano_usd": 2_300_000, "cost_source": "provider", "cost_complete": True}
    assert agent_quota.measured_charge(usage) == 2_000
    # Rounded up to a whole micro-euro.
    assert agent_quota.measured_charge({**usage, "estimated_cost_nano_usd": 1}) == 1
    assert agent_quota.measured_charge({**usage, "estimated_cost_nano_usd": 0}) == 0
    assert agent_quota.measured_charge({**usage, "cost_complete": False}) is None
    assert agent_quota.measured_charge({**usage, "estimated_cost_nano_usd": None}) is None
    assert agent_quota.measured_charge({**usage, "provisional": True}) is None
    assert agent_quota.measured_charge({"session_kind": "audit", **usage}) == 2_000
    data = agent_quota.settle(agent_quota.reserve({}, 20_000, limit=100_000), 20_000, usage)
    assert data["used"] == 2_000 and data["reserved"] == 0
    # A lost final chunk: the cost of what was seen is the lower bound.
    assert agent_quota.provisional_lower_bound({**usage, "provisional": True}) == 2_000


def test_background_scheduling_is_disabled_in_unit_test_mode(store):
    assert reconciliation.schedule(store.db, UID) is False


def test_snapshot_schedules_reconciliation_for_yesterdays_estimates(store, monkeypatch):
    from datetime import datetime, timezone
    # Shortly after midnight yesterday is read on every snapshot.
    monkeypatch.setattr(agent_quota, "PREVIOUS_DAY_GRACE", timedelta(days=2))
    scheduled = []
    monkeypatch.setattr(reconciliation, "schedule", lambda db, uid: scheduled.append(uid) or True)
    config = agent_quota.agent_budget_config.get_config(store.db)
    today = agent_quota.period_key(config)
    day = datetime.strptime(today.split("_")[0], "%Y-%m-%d")
    yesterday = (day - timedelta(days=1)).strftime("%Y-%m-%d") + today[len(today.split("_")[0]):]
    agent_quota.snapshot(store.db, UID)
    assert scheduled == []
    agent_quota.quota_ref(store.db, UID, yesterday).set({"estimated": 250})
    agent_quota.snapshot(store.db, UID)
    assert scheduled == [UID]


def test_a_settled_empty_yesterday_is_not_read_on_every_snapshot(store, monkeypatch):
    reads = []
    real = agent_quota.quota_ref

    def counting(db, uid, day):
        reads.append(day)
        return real(db, uid, day)

    monkeypatch.setattr(agent_quota, "PREVIOUS_DAY_GRACE", timedelta(0))
    monkeypatch.setattr(agent_quota, "quota_ref", counting)
    agent_quota._quiet_until.clear()
    agent_quota.snapshot(store.db, UID)
    first = len(reads)
    agent_quota.snapshot(store.db, UID)
    # Today's ledger is read again; the closed, empty yesterday is not.
    assert len(reads) - first == first - 1
    agent_quota._quiet_until.clear()
