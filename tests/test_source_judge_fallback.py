"""Availability failover uses bounded original-source inputs, never second opinions."""
import json as jsonlib
from dataclasses import replace

import httpx
import pytest

from app.services import source_verification as sv, contradiction_verification as cv
from app.services import source_check_jobs as jobs
from app.services.llm.engines import _ProviderHTTPStatusError
from app.services.llm.provider_runtime import AnalysisBudget, AnalysisBudgetExceeded, bind_analysis_budget, current_analysis_budget
from test_contradiction_verification import run, judge
from test_source_check_repository import FakeDb
from app.services.source_check_repository import SourceCheckRepository


LIMITS = sv.Limits(model='openai/gpt-5-mini', fallback_model='google/gemini-3.5-flash-lite')
KEYS = {'OpenRouter': 'owner-test-key'}


def response(payload):
    data = judge(payload)[0] if payload.get('disputes') else {'findings': []}
    return {'choices': [{'message': {'content': jsonlib.dumps(data)}, 'finish_reason': 'stop'}], 'usage': {'prompt_tokens': 20}}


@pytest.mark.parametrize('error', [_ProviderHTTPStatusError(429), _ProviderHTTPStatusError(503),
    _ProviderHTTPStatusError(404), httpx.ConnectError('do not persist'), httpx.ReadTimeout('do not persist')])
def test_unavailable_primary_uses_one_fallback_same_key_and_bound_budget(monkeypatch, error):
    calls = []
    parent = AnalysisBudget(seconds=60, max_calls=2)
    def transport(url, *, json, headers):
        calls.append((json, headers, current_analysis_budget().deadline))
        if len(calls) == 1:
            raise error
        return response({})
    monkeypatch.setattr(sv, 'cancellable_post_json', transport)
    with bind_analysis_budget(parent):
        _, usage = sv.judge_sources({'check_type': cv.MODE}, KEYS, LIMITS)
    assert [c[0]['model'] for c in calls] == [LIMITS.model, LIMITS.fallback_model]
    assert calls[0][1] == calls[1][1]
    assert calls[0][0]['provider'] == calls[1][0]['provider'] == {'zdr': True}
    assert calls[0][2] < calls[1][2] == parent.deadline
    assert parent.calls == usage['calls'] == 2
    assert usage['fallback_used'] and usage['model'] == LIMITS.fallback_model
    assert 'do not persist' not in str(usage)


@pytest.mark.parametrize('error', [_ProviderHTTPStatusError(401), _ProviderHTTPStatusError(403),
    _ProviderHTTPStatusError(400), sv.SourceCheckError('invalid_output'), sv.SourceCheckError('output_limit')])
def test_credentials_and_invalid_content_do_not_trigger_fallback(monkeypatch, error):
    calls = []
    def transport(*args, **kwargs):
        calls.append(kwargs['json']['model'])
        raise error
    monkeypatch.setattr(sv, 'cancellable_post_json', transport)
    with pytest.raises(type(error)):
        sv.judge_sources({'check_type': cv.MODE}, KEYS, LIMITS)
    assert calls == [LIMITS.model]


def test_primary_attempt_timeout_can_fallback_but_global_expiry_cannot(monkeypatch):
    calls = []
    parent = AnalysisBudget(seconds=60, max_calls=2)
    def transport(*args, **kwargs):
        calls.append(kwargs['json']['model'])
        if len(calls) == 1:
            raise AnalysisBudgetExceeded('attempt timeout')
        return response({})
    monkeypatch.setattr(sv, 'cancellable_post_json', transport)
    with bind_analysis_budget(parent):
        assert sv.judge_sources({'check_type': cv.MODE}, KEYS, LIMITS)[1]['fallback_used']
    calls.clear()
    parent.deadline = 0
    with bind_analysis_budget(parent), pytest.raises(AnalysisBudgetExceeded):
        sv.judge_sources({'check_type': cv.MODE}, KEYS, LIMITS)
    assert not calls


def test_second_input_must_fit_total_budget(monkeypatch):
    payload = {'check_type': cv.MODE}
    limits = replace(LIMITS, input_tokens=cv._input_size(payload))
    calls = []
    def transport(*args, **kwargs):
        calls.append(kwargs['json']['model'])
        raise _ProviderHTTPStatusError(503)
    monkeypatch.setattr(sv, 'cancellable_post_json', transport)
    with pytest.raises(sv.SourceCheckError) as caught:
        sv.judge_sources(payload, KEYS, limits)
    assert caught.value.code == 'input_limit'
    assert calls == [LIMITS.model]
    assert caught.value.source_runtime['calls'] == 1


def test_invalid_evidence_is_diagnosed_and_never_retried(monkeypatch):
    calls = []
    def transport(url, *, json, headers):
        calls.append(json['model'])
        payload = jsonlib.loads(json['messages'][1]['content'])
        data = judge(payload)[0]
        data['findings'][0]['evidence'][0]['quote'] = 'An invented original quote.'
        return {'choices': [{'message': {'content': jsonlib.dumps(data)}}]}
    monkeypatch.setattr(sv, 'cancellable_post_json', transport)
    result = run(keys=KEYS, limits=LIMITS, judge=sv.judge_sources)
    assert calls == [LIMITS.model]
    assert result['findings'][0]['reason_code'] == 'evidence_mismatch'
    assert result['findings'][0]['validation_errors']
    assert result['findings'][0]['evidence'] == []


def test_successful_fallback_provenance_survives_cache_and_model_selection_change(monkeypatch):
    calls = []
    def transport(url, *, json, headers):
        calls.append(json['model'])
        if json['model'] == LIMITS.model:
            raise _ProviderHTTPStatusError(503)
        return response({})
    monkeypatch.setattr(sv, 'cancellable_post_json', transport)
    repo = SourceCheckRepository(FakeDb())
    cached = jobs._cached_judge('owner', repo)
    payload = {'check_type': cv.MODE}
    assert cached(payload, KEYS, LIMITS)[1]['fallback_used']
    usage = cached(payload, KEYS, LIMITS)[1]
    assert usage['cache_hit'] and usage['calls'] == 0
    assert usage['model'] == LIMITS.fallback_model
    assert len(calls) == 2
    with pytest.raises(_ProviderHTTPStatusError):
        cached(payload, KEYS, replace(LIMITS, fallback_model=''))
    assert len(calls) == 3


def test_both_attempt_failures_are_preserved_without_exception_text(monkeypatch):
    def transport(*args, **kwargs):
        raise _ProviderHTTPStatusError(503)
    monkeypatch.setattr(sv, 'cancellable_post_json', transport)
    result = run(keys=KEYS, limits=LIMITS, judge=sv.judge_sources)
    assert result['runtime']['calls'] == 2
    assert result['runtime']['fallback_used']
    assert [a['status'] for a in result['runtime']['model_attempts']] == ['failed', 'failed']
    assert result['findings'][0]['checked'] is False
