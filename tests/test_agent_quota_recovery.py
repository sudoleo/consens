"""Regression for a completed run locking the next run after a browser reload."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

from app.services import agent_quota
from app.services.agent_costs import aggregate_usage
from app.services.llm.agent_client import AgentCompletion, measured_usage
from test_agent_runs import UID, store, receipt, totals
from test_agent_delegation import make_loop


def test_refresh_migrates_terminal_unknown_holds_but_preserves_live_reservations(store):
    ref = agent_quota.quota_ref(store.db, UID, agent_quota.day_key())
    store.db.collection('users').document(UID).set({})
    ref.set({'used': 85329, 'unknown': 154521, 'reserved': 161923})
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda _: agent_quota.snapshot(store.db, UID), range(6)))
    assert all(r['used'] == 85329 and r['reserved'] == 7402 and r['remaining'] == 157269 for r in results)
    saved = ref.get().to_dict()
    assert saved['unknown'] == saved['unknown_released'] == 154521
    assert saved['revision'] == 1
    agent_quota.snapshot(store.db, UID)
    assert ref.get().to_dict() == saved
    # A last request from the old deployment can still settle during rollout.
    ref.set({**saved, 'unknown': 154621, 'reserved': 7502})
    assert agent_quota.snapshot(store.db, UID)['reserved'] == 7402
    assert ref.get().to_dict()['unknown_released'] == 154621


def test_terminal_unknown_usage_releases_admission_without_inventing_zero_usage(store):
    loop = make_loop(store)
    args = (UID, loop.chat_id, loop.turn_id)
    store.claim(*args, loop.model, run_token=loop.run_token, policy=loop.policy.snapshot(), reservation=(500, 100))
    store.settle(*args, completion=receipt(measured=False), status='failed', final=False)
    budget = agent_quota.snapshot(store.db, UID)
    assert budget['used'] == budget['reserved'] == 0
    assert budget['unknown'] == 500 and budget['remaining'] == budget['limit']
    assert store.receipt_ref(*args).get().to_dict()['usage'] is None
    assert totals(store)['unmetered_calls'] == 1
    before = dict(budget)
    assert not store.settle(*args, completion=receipt(), status='succeeded', final=False)
    assert agent_quota.snapshot(store.db, UID)['revision'] == before['revision']


def test_reload_reaps_lost_lease_map_and_recovers_exact_saved_single_call_usage(store):
    loop = make_loop(store)
    args = (UID, loop.chat_id, loop.turn_id)
    store.claim(*args, loop.model, run_token=loop.run_token, policy=loop.policy.snapshot(), reservation=(100, 100))
    store.settle(*args, completion=receipt(), status='succeeded', final=False)
    saved_usage = measured_usage({'prompt_tokens':155, 'completion_tokens':284, 'cost':.000460410}, loop.model)
    for aid, usage in [('a'*32, aggregate_usage([saved_usage])), ('b'*32, None)]:
        store.publish_agent(*args, run_token=loop.run_token, agent_id=aid,
            patch={'assignment':{'goal':'Verify'}, 'status':'working', 'kind':'comparison'})
        store.claim(*args, loop.model, run_token=loop.run_token, policy=loop.policy.snapshot(),
                    step=f'agent:{aid}:0', reservation=(3701, 100))
        store.publish_agent(*args, run_token=loop.run_token, agent_id=aid, patch={'status':'failed', 'usage':usage})
    ref = agent_quota.quota_ref(store.db, UID, agent_quota.day_key())
    ref.set({'used':85329, 'unknown':154521, 'reserved':161923})
    root = store.receipt_ref(*args)
    store._transaction(lambda tx: tx.update(root, {'lease_until':datetime.now(timezone.utc)-timedelta(seconds=60)}))
    store.active_ref(UID).set({'leases':{}})
    original_totals = totals(store)
    budget = agent_quota.snapshot(store.db, UID)
    assert budget['used'] == 85768 and budget['reserved'] == 0 and budget['remaining'] == 164232
    assert budget['unknown'] == 158222
    assert totals(store)['input_tokens'] == original_totals['input_tokens'] + 155
    assert totals(store)['output_tokens'] == original_totals['output_tokens'] + 284
    assert totals(store)['unsettled_calls'] == 0
    assert root.get().to_dict()['run_status'] == 'cancelled'
    recovered = store.receipt_ref(*args, step=f"agent:{'a'*32}:0").get().to_dict()
    assert recovered['usage']['source'] == 'saved_agent'
    assert agent_quota.snapshot(store.db, UID)['revision'] == budget['revision']
    assert store.get_turn(*args)['status'] == 'failed'


def test_live_lease_is_never_reaped_by_a_budget_refresh(store):
    loop = make_loop(store)
    args = (UID, loop.chat_id, loop.turn_id)
    store.claim(*args, loop.model, run_token=loop.run_token, policy=loop.policy.snapshot(), reservation=(500, 100))
    budget = agent_quota.snapshot(store.db, UID)
    assert budget['reserved'] == 500 and budget['unknown'] == 0
    assert store.receipt_ref(*args).get().to_dict()['run_status'] == 'running'


def test_renewal_committed_after_recovery_read_cannot_be_cancelled(store, monkeypatch):
    loop = make_loop(store)
    args = (UID, loop.chat_id, loop.turn_id)
    store.claim(*args, loop.model, run_token=loop.run_token, policy=loop.policy.snapshot(), reservation=(500, 100))
    root = store.receipt_ref(*args)
    store._transaction(lambda tx: tx.update(root, {'lease_until':datetime.now(timezone.utc)-timedelta(seconds=1)}))
    original = store._agent_transaction
    def renewed_before_fence(uid, operation):
        store._transaction(lambda tx: tx.update(root, {'lease_until':datetime.now(timezone.utc)+timedelta(seconds=120)}))
        return original(uid, operation)
    monkeypatch.setattr(store, '_agent_transaction', renewed_before_fence)
    assert store.reap_delegation(*args)['run_status'] == 'running'
    assert not root.get().to_dict().get('cancel_requested')
    assert agent_quota.snapshot(store.db, UID)['reserved'] == 500


@pytest.mark.parametrize('case', ['incomplete', 'provisional', 'unmetered', 'aggregate', 'multiple_steps'])
def test_recovery_never_guesses_an_individual_receipt_from_ambiguous_saved_usage(store, case):
    loop = make_loop(store)
    args = (UID, loop.chat_id, loop.turn_id)
    store.claim(*args, loop.model, run_token=loop.run_token, policy=loop.policy.snapshot(), reservation=(100, 100))
    store.settle(*args, completion=receipt(), status='succeeded', final=False)
    before = totals(store)
    aid = 'a' * 32
    usage = aggregate_usage([measured_usage({'prompt_tokens':155, 'completion_tokens':284}, loop.model)])
    if case == 'incomplete':
        usage['complete'] = False
    elif case == 'provisional':
        usage['provisional'] = True
    elif case == 'unmetered':
        usage['unmetered_calls'] = 1
    elif case == 'aggregate':
        usage['measured_calls'] = 2
    store.publish_agent(*args, run_token=loop.run_token, agent_id=aid,
        patch={'assignment':{'goal':'Verify'}, 'status':'working', 'kind':'comparison'})
    store.claim(*args, loop.model, run_token=loop.run_token, policy=loop.policy.snapshot(),
                step=f'agent:{aid}:0', reservation=(500, 100))
    if case == 'multiple_steps':
        store.settle(*args, completion=receipt(), status='succeeded', step=f'agent:{aid}:0', final=False)
        before = totals(store)
        store.claim(*args, loop.model, run_token=loop.run_token, policy=loop.policy.snapshot(),
                    step=f'agent:{aid}:1', reservation=(500, 100))
    store.publish_agent(*args, run_token=loop.run_token, agent_id=aid, patch={'status':'failed', 'usage':usage})
    root = store.receipt_ref(*args)
    store._transaction(lambda tx: tx.update(root, {'lease_until':datetime.now(timezone.utc)-timedelta(seconds=60)}))
    assert agent_quota.snapshot(store.db, UID)['reserved'] == 0
    assert totals(store)['input_tokens'] == before['input_tokens']
    assert totals(store)['output_tokens'] == before['output_tokens']
    missing_step = 1 if case == 'multiple_steps' else 0
    assert store.receipt_ref(*args, step=f'agent:{aid}:{missing_step}').get().to_dict()['usage'] is None


def test_deleted_chat_cannot_leave_an_expired_receipt_blocking_the_account(store):
    loop = make_loop(store)
    args = (UID, loop.chat_id, loop.turn_id)
    store.claim(*args, loop.model, run_token=loop.run_token, policy=loop.policy.snapshot(), reservation=(500, 100))
    root = store.receipt_ref(*args)
    store.delete_chat(UID, loop.chat_id)
    store._transaction(lambda tx: tx.update(root, {'lease_until':datetime.now(timezone.utc)-timedelta(seconds=60)}))
    assert agent_quota.snapshot(store.db, UID)['remaining'] == 250000
    assert root.get().to_dict()['run_status'] == 'cancelled'
    assert not store._chat_ref(UID, loop.chat_id).get().exists


def test_unreported_reservation_cannot_leak_across_day_or_reset(store, monkeypatch):
    monkeypatch.setattr(agent_quota, 'day_key', lambda: '2026-09-19')
    old = agent_quota.quota_ref(store.db, UID, '2026-09-18')
    old.set({'used':100, 'reserved':500, 'unknown':500})
    store.db.collection('users').document(UID).set({})
    assert agent_quota.snapshot(store.db, UID)['remaining'] == 250000
    store.repair_quota_period(UID, '2026-09-18')
    assert old.get().to_dict()['reserved'] == 0 and old.get().to_dict()['used'] == 100
    assert agent_quota.snapshot(store.db, UID)['remaining'] == 250000
