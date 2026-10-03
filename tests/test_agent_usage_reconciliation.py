"""R07: bounded uncertainty for Agent calls without final usage.

Started calls without final usage are charged a bounded estimate (not released
completely, not charged completely), later reconciled exactly once against the
provider's measurement. Calls that provably never started stay free.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest

from app.services import agent_quota, agent_usage_reconciliation as reconciliation
from app.services.llm.agent_client import AgentCompletion
from test_agent_runs import UID, store, receipt, totals
from test_agent_delegation import make_loop


def unknown_call(store, *, reservation=500, generation_id="gen-1", step="completion:0", loop=None):
    loop = loop or make_loop(store)
    args = (UID, loop.chat_id, loop.turn_id)
    store.claim(*args, loop.model, run_token=loop.run_token, policy=loop.policy.snapshot(),
                step=step, reservation=(reservation, 100))
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
    provisional = {"input_tokens": 80, "output_tokens": 5, "provisional": True, "complete": False}
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
    measured = {"input_tokens": 10, "output_tokens": 5}
    clean = agent_quota.settle(agent_quota.reserve({}, 200, limit=250), 200, measured)
    assert agent_quota.public(clean, limit=250)["remaining"] == 235


def test_provably_unstarted_calls_are_still_released_completely(store):
    loop = make_loop(store)
    args = (UID, loop.chat_id, loop.turn_id)
    store.claim(*args, loop.model, run_token=loop.run_token, policy=loop.policy.snapshot(), reservation=(500, 100))
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
    assert saved["quota_reconcile"] == "measured" and saved["quota_measured_tokens"] == 130
    assert totals(store)["reconciled_calls"] == 1

    # Repeated passes and a late settlement retry never charge twice.
    assert reconciliation.reconcile_pending(store.db, UID, fetch_usage=fetch)["measured"] == 0
    assert not store.settle(*args, completion=receipt(), status="succeeded", final=False)
    assert agent_quota.snapshot(store.db, UID)["used"] == 130
    assert lookups == ["gen-1"]


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


def test_generation_stats_prefer_native_counts_and_reject_garbage():
    assert reconciliation.generation_tokens(
        {"data": {"native_tokens_prompt": 100, "native_tokens_completion": 30, "tokens_prompt": 90}}) == 130
    assert reconciliation.generation_tokens({"data": {"tokens_prompt": 90, "tokens_completion": 10}}) == 100
    assert reconciliation.generation_tokens({"data": {"native_tokens_prompt": None}}) is None
    assert reconciliation.generation_tokens({"data": {"tokens_prompt": -1, "tokens_completion": 3}}) is None
    assert reconciliation.generation_tokens([]) is None


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
