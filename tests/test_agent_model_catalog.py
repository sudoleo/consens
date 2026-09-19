"""Admin DB membership/order and public metadata are independent contracts."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.core import config as cfg, security
from app.api.routers import agent
from app.services.llm import agent_client, agent_model_metadata as metadata
from test_agent_runs import api, store, AUTH, UID

REAL_REFRESH = agent._refresh_model_configuration
TERRA = {'id': 'openai/gpt-5.6-terra', 'pricing': {'prompt': '0.000002', 'completion': '0.000012'},
         'context_length': 1050000, 'top_provider': {'max_completion_tokens': 128000},
         'reasoning': {'supported_efforts': ['high', 'low', 'none'], 'mandatory': False}}


def test_public_metadata_cache_coalesces_reads_and_preserves_last_good_values(monkeypatch):
    clock = [10]
    monkeypatch.setattr(metadata.time, 'monotonic', lambda: clock[0])
    fetch = Mock(return_value={TERRA['id']: metadata._normalize(TERRA)})
    monkeypatch.setattr(metadata, 'fetch_models', fetch)
    cache = metadata.ModelMetadataCache()
    with ThreadPoolExecutor(max_workers=4) as pool:
        values = list(pool.map(lambda _: cache.snapshot(), range(4)))
    assert fetch.call_count == 1
    assert values[0][TERRA['id']]['context_length'] == 1050000
    values[0][TERRA['id']]['pricing']['prompt'] = '999'
    assert cache.snapshot()[TERRA['id']]['pricing']['prompt'] == '0.000002'
    clock[0] += 301
    fetch.side_effect = TimeoutError('offline')
    assert cache.snapshot()[TERRA['id']]['context_length'] == 1050000
    assert metadata.BASELINE['models'].keys() <= cache.snapshot().keys()
    assert fetch.call_count == 2
    clock[0] += 31
    cache.snapshot()
    assert fetch.call_count == 3


def test_public_fetch_uses_one_fixed_unauthenticated_bounded_endpoint(monkeypatch):
    response = Mock()
    response.read.return_value = json.dumps({'data': [TERRA, {'id': 'broken'}]}).encode()
    open_url = Mock()
    open_url.return_value.__enter__ = Mock(return_value=response)
    open_url.return_value.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(metadata, 'urlopen', open_url)
    assert set(metadata.fetch_models()) == {TERRA['id']}
    open_url.assert_called_once_with(metadata.MODELS_URL, timeout=5)
    response.read.assert_called_once_with(8 * 1024 * 1024 + 1)


@pytest.mark.parametrize('change', [
    {'pricing': {'prompt': '-1', 'completion': '1'}},
    {'pricing': {'prompt': 'NaN', 'completion': '1'}},
    {'pricing': {'prompt': '1'}},
    {'context_length': True}, {'context_length': 0},
    {'top_provider': {'max_completion_tokens': -1}},
    {'reasoning': {'supported_efforts': 'high'}},
])
def test_invalid_metadata_never_becomes_an_admission_estimate(change):
    assert metadata._normalize({**TERRA, **change}) is None


def test_admin_db_additions_order_removals_and_replay_without_a_code_allowlist(api, monkeypatch):
    client, store, calls = api
    previous = cfg._capture_runtime_config()
    payload = {key: cfg.get_ordered_models(key) for key in cfg.PROVIDERS}
    payload['openai'] = ['gpt-5.6-terra', 'future-missing', 'gpt-4o']
    document = Mock()
    document.get.side_effect = lambda **_: SimpleNamespace(exists=True, to_dict=lambda: deepcopy(payload))
    database = Mock()
    database.collection.return_value.document.return_value = document
    monkeypatch.setattr(security, 'db_firestore', database)
    monkeypatch.setattr(agent, '_refresh_model_configuration', REAL_REFRESH)
    catalog = {key: {**deepcopy(value), '_version': metadata.BASELINE['version']}
               for key, value in metadata.BASELINE['models'].items()}
    catalog[TERRA['id']] = {**metadata._normalize(TERRA), '_version': 'provider-test'}
    monkeypatch.setattr(metadata, 'snapshot', lambda: deepcopy(catalog))
    try:
        response = client.get('/agent/models', headers=AUTH)
        assert response.status_code == 200
        options = [m for m in response.json()['models'] if m['provider'] == 'openai']
        assert [m['id'] for m in options] == payload['openai']
        assert options[0]['available'] and options[0]['reasoning_efforts'] == ['default', 'none', 'low', 'high']
        assert not options[1]['available'] and options[1]['unavailable_reason']
        assert options[2]['available']  # Free models are not filtered by a Pro/preset list.
        with pytest.raises(ValueError, match='information is temporarily unavailable'):
            agent_client.resolve_agent_model('future-missing')
        resolved = agent_client.resolve_agent_model('gpt-5.6-terra', 'high')
        assert resolved.context_length == 1050000 and resolved.pricing_version == 'provider-test'
        assert resolved.output_usd_per_million == '12.000000'
        assert agent_client.metered_model('gpt-5.6-terra').model == TERRA['id']
        chat_id = store.create_chat(UID, execution_mode='agent')['id']
        request = {'chat_id': chat_id, 'question': 'Hi', 'client_request_id': 'db-model',
                   'bookmark_id': 'db_model', 'model_id': 'gpt-5.6-terra', 'reasoning_effort': 'high'}
        result = client.post('/agent', json=request, headers=AUTH)
        assert 'event: final' in result.text, result.text
        assert calls[0]['model'].model == TERRA['id']
        payload['openai'] = ['gpt-4o', 'future-missing']
        fresh = client.get('/agent/models', headers=AUTH).json()
        assert [m['id'] for m in fresh['models'] if m['provider'] == 'openai'] == payload['openai']
        before = document.get.call_count
        replay = client.post('/agent', json={**request, 'recover_only': True}, headers=AUTH)
        assert replay.status_code == 200 and document.get.call_count == before
        rejected = client.post('/agent', json={**request, 'client_request_id': 'removed'}, headers=AUTH)
        assert rejected.status_code == 422 and len(calls) == 1
        assert 'not available in Agent Beta' in rejected.text
        document.set.assert_not_called()
    finally:
        cfg._restore_runtime_config(previous)


def test_unavailable_admin_db_is_reported_without_falling_back_to_code_defaults(monkeypatch):
    monkeypatch.setattr(cfg, 'load_models_from_db', Mock(side_effect=TimeoutError()))
    with pytest.raises(agent.HTTPException) as exc:
        REAL_REFRESH()
    assert exc.value.status_code == 503
