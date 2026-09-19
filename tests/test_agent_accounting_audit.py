"""Provider-independent metering/lease invariants across the full registry."""
from datetime import datetime, timedelta, timezone

import pytest

from app.core import config as cfg
from app.services import agent_quota
from app.services.agent_costs import RunCosts
from app.services.agent_policy import AgentPolicy
from app.services.agent_provider_limits import ProviderCooldowns
from app.services.llm.agent_client import AgentCompletion, measured_usage, metered_model
from app.services.llm.engines import _ProviderHTTPStatusError, _ProviderResponseError
from test_agent_runs import UID, store
from test_agent_delegation import make_loop
from test_agent_loop import packet, transport


@pytest.mark.parametrize('model_id', sorted(cfg.MODEL_CONFIGS))
def test_every_registered_chat_comparison_and_judge_model_uses_provider_totals(model_id, monkeypatch):
    model = metered_model(model_id)
    transport(monkeypatch, [[packet({'content': 'Answer'}, finish='stop'),
        packet(usage={'prompt_tokens': 101, 'completion_tokens': 29,
                     'prompt_tokens_details': {'cached_tokens': 40, 'cache_write_tokens': 30},
                     'completion_tokens_details': {'reasoning_tokens': 21}, 'cost': '0.000000007'})]])
    value = AgentCompletion()
    list(value.stream(model=model, messages=[{'role': 'user', 'content': 'Hi'}], api_key='test'))
    assert agent_quota.measured_tokens(value.usage) == 130
    assert value.usage['estimated_cost_nano_usd'] == 7
    assert value.usage['complete'] and value.usage['cost_complete']
    assert value.usage['reasoning_tokens'] == 21 and value.usage['cached_input_tokens'] == 40


@pytest.mark.parametrize('code', [400, 401, 402, 403, 404, 413, 422, 429])
def test_explicit_http_rejection_releases_paid_claim_once(store, code):
    class Rejected(AgentCompletion):
        def stream(self, **kwargs):
            raise _ProviderHTTPStatusError(code)
            yield
    loop = make_loop(store, Rejected, cooldowns=ProviderCooldowns())
    with pytest.raises(_ProviderHTTPStatusError):
        list(loop.run())
    budget = agent_quota.snapshot(store.db, UID)
    assert budget['used'] == budget['reserved'] == budget['unknown'] == 0
    assert budget['remaining'] == budget['limit']
    saved = store.receipt_ref(UID, loop.chat_id, loop.turn_id).get().to_dict()
    assert saved['usage']['source'] == 'provider_rejection'
    assert not store.settle(UID, loop.chat_id, loop.turn_id, completion=AgentCompletion(), status='failed', final=False)
    assert agent_quota.snapshot(store.db, UID)['revision'] == budget['revision']


@pytest.mark.parametrize('error', [_ProviderHTTPStatusError(408), _ProviderHTTPStatusError(500),
                                  _ProviderHTTPStatusError(503), _ProviderResponseError({'code': 429}), TimeoutError()])
def test_ambiguous_errors_never_invent_free_usage(error):
    value = AgentCompletion()
    value.record_rejection(error, metered_model('claude-haiku-4-5'))
    assert value.usage is None


def test_stop_after_admission_but_before_provider_releases_all_tokens(store, monkeypatch):
    requests, _, _ = transport(monkeypatch, [])
    loop = make_loop(store)
    stream = loop.run()
    assert next(stream)['type'] == 'started'
    assert agent_quota.snapshot(store.db, UID)['reserved'] > 0
    stream.close()
    assert requests == []
    budget = agent_quota.snapshot(store.db, UID)
    assert budget['used'] == budget['reserved'] == budget['unknown'] == 0
    saved = store.receipt_ref(UID, loop.chat_id, loop.turn_id).get().to_dict()
    assert saved['usage']['source'] == 'not_started' and saved['run_status'] == 'cancelled'


def test_intermediate_usage_is_lower_bound_after_interrupted_generation(store, monkeypatch):
    transport(monkeypatch, [[packet({'content': 'Partial'}, usage={'prompt_tokens': 100, 'completion_tokens': 0}),
                            TimeoutError()]])
    loop = make_loop(store)
    with pytest.raises(TimeoutError):
        list(loop.run())
    budget = agent_quota.snapshot(store.db, UID)
    assert budget['used'] == 0 and budget['reserved'] == budget['unknown'] > 0
    assert loop.completion.usage['input_tokens'] == 100
    assert not loop.completion.usage['complete']


def test_final_usage_replaces_cumulative_values_and_releases_reservation(store, monkeypatch):
    transport(monkeypatch, [[packet({'content': 'Answer'}, usage={'prompt_tokens': 100, 'completion_tokens': 0}),
                            packet(finish='stop'), packet(usage={'prompt_tokens': 100, 'completion_tokens': 30, 'cost': .001})]])
    loop = make_loop(store)
    list(loop.run())
    budget = agent_quota.snapshot(store.db, UID)
    assert budget['used'] == 130 and budget['reserved'] == budget['unknown'] == 0
    assert loop.completion.usage['complete']


def test_token_receipt_is_complete_without_search_price():
    model = metered_model('claude-haiku-4-5')
    usage = measured_usage({'prompt_tokens': 100, 'completion_tokens': 20}, model, searches_enabled=True)
    costs = RunCosts(AgentPolicy())
    reservation = costs.reserve(model, [])
    costs.reconcile(reservation, usage)
    assert costs.tokens == agent_quota.measured_tokens(usage) == 120
    assert usage['complete'] and not usage['cost_complete']
    assert costs.cost == reservation[1]


def test_final_cost_does_not_promote_intermediate_token_counts(store, monkeypatch):
    transport(monkeypatch, [[packet({'content': 'Answer'}, usage={'prompt_tokens': 100, 'completion_tokens': 0}),
                            packet(finish='stop', usage={'cost': .001})]])
    loop = make_loop(store)
    list(loop.run())
    budget = agent_quota.snapshot(store.db, UID)
    assert budget['used'] == 0 and budget['reserved'] == budget['unknown'] > 0
    assert not loop.completion.usage['complete']
    assert loop.completion.usage['cost_complete']


def test_separately_reported_final_token_fields_complete_the_receipt(monkeypatch):
    transport(monkeypatch, [[packet({'content': 'Answer'}, usage={'prompt_tokens': 100, 'completion_tokens': 0}),
                            packet(finish='stop', usage={'prompt_tokens': 100}),
                            packet(usage={'completion_tokens': 30})]])
    value = AgentCompletion()
    list(value.stream(model=metered_model('claude-haiku-4-5'), messages=[], api_key='test'))
    assert value.usage['complete'] and agent_quota.measured_tokens(value.usage) == 130


def test_reaped_session_preserves_confirmed_duration_without_growing_after_reload(store):
    loop = make_loop(store)
    args = (UID, loop.chat_id, loop.turn_id)
    store.claim(*args, loop.model, run_token=loop.run_token, policy=loop.policy.snapshot(), reservation=(500, 100))
    aid = 'a' * 32
    store.publish_agent(*args, run_token=loop.run_token, agent_id=aid, patch={
        'assignment': {'goal': 'Check'}, 'status': 'working', 'duration_ms': 5100,
        'created_at': (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()})
    root = store.receipt_ref(*args)
    store._transaction(lambda tx: tx.update(root, {'lease_until': datetime.now(timezone.utc) - timedelta(seconds=1)}))
    first = store.delegation_view(*args)['agents'][0]
    again = store.delegation_view(*args)['agents'][0]
    assert first['status'] == 'stopped' and first['duration_incomplete']
    assert first['duration_ms'] == again['duration_ms'] == 5100
    assert first['ended_at'] == again['ended_at']


def test_ledger_versions_cover_reservation_settlement_and_released_review_hold():
    data = agent_quota.reserve({}, 500)
    assert data['revision'] == 1
    data = agent_quota.settle(data, 200, {'input_tokens': 60, 'output_tokens': 40})
    assert data['revision'] == 2 and data['used'] == 100 and data['reserved'] == 300
    data = agent_quota.release(data, 300)
    assert data['revision'] == 3 and data['reserved'] == 0
