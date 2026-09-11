"""Chat-only source checks must never add work to scheduled products."""
from copy import deepcopy

import pytest

from app.services import (
    api_consensus_runner, consensus_pipeline, source_check_jobs as jobs,
    source_documents, source_verification, topic_pipeline, watch_scheduler,
    share_snapshots,
)
from app.services.source_check_repository import SourceCheckRepository
from test_source_check_repository import FakeDb, make_plan


def forbidden(*args, **kwargs):
    pytest.fail('A non-chat run must not fetch sources, invoke the source judge or submit a job')


@pytest.mark.parametrize('product', ['watch', 'topic', 'api'])
def test_product_runs_keep_consensus_and_differences_without_source_work(monkeypatch, product):
    monkeypatch.setenv('MOCK_LLM', '1')
    monkeypatch.setattr(consensus_pipeline, 'start_source_verification', forbidden)
    monkeypatch.setattr(jobs, 'submit_advisory', forbidden)
    monkeypatch.setattr(source_documents, 'fetch_document', forbidden)
    monkeypatch.setattr(source_verification, 'judge_sources', forbidden)
    monkeypatch.setattr(topic_pipeline.provider_transport, 'provider_available', lambda *a: True)
    models = {'openai': 'mock-openai', 'mistral': 'mock-mistral'}
    # Even an accidentally inherited owner context must not opt a product in.
    with jobs.source_check_context('owner', product + ':run', origin=product):
        if product == 'watch':
            result = watch_scheduler.execute_watch('Question?', 'Previous answer', model_overrides=models)
        elif product == 'topic':
            result = topic_pipeline.execute_topic('Question?', 'Previous answer', model_overrides=models)
        else:
            result = api_consensus_runner.execute_consensus_pipeline({
                'request': {'question': 'Question?'},
                'model_plan': {'providers': models, 'consensus_model': 'OpenAI'},
            })
    assert result.get('consensus') or result.get('consensus_response')
    assert isinstance(result['differences_data']['agreement']['score'], int)
    assert result.get('source_verification') is None
    if product != 'api':
        assert len(result['included_models']) == 2
        assert 'sources' in result
        assert 'opinion_map' in result
        assert 'changed' in result


@pytest.mark.parametrize('differences', [None, {'agreement': {'score': 88}}])
def test_neutral_analysis_does_not_emit_disabled_or_failed_chat_status(monkeypatch, differences):
    monkeypatch.setattr(consensus_pipeline, 'start_source_verification', forbidden)
    monkeypatch.setattr(jobs, 'submit_advisory', forbidden)
    result = consensus_pipeline.analyze_provider_answers(
        question='Question?', answers={'openai': 'A', 'mistral': 'B'},
        consensus_model='OpenAI', keys={}, synthesize=lambda *a, **kw: 'Consensus',
        judge=lambda *a, **kw: ('Differences', deepcopy(differences)),
        require_differences_data=False,
    )
    assert result.consensus == 'Consensus'
    assert result.source_verification is None
    assert result.differences_data == differences


@pytest.mark.parametrize('origin', ['watch', 'topic', 'api'])
def test_non_chat_admission_stops_before_planning_or_persistence(monkeypatch, origin):
    monkeypatch.setattr(source_verification, 'plan_source_verification', forbidden)
    monkeypatch.setattr(jobs, 'repository', forbidden)
    with jobs.source_check_context('owner', origin + ':run', origin=origin):
        assert jobs.submit_source_check(question='Question?', consensus='Consensus', sources=[], keys={}) is None


@pytest.mark.parametrize('origin', ['watch', 'topic', 'api'])
def test_preexisting_background_jobs_are_cancelled_without_plan_or_paid_work(monkeypatch, origin):
    repo = SourceCheckRepository(FakeDb())
    job = repo.create(uid='owner', run_key=origin + ':run', plan=make_plan(1), origin=origin)
    monkeypatch.setattr(repo, 'get_plan', forbidden)
    monkeypatch.setattr(source_verification, 'execute_source_package', forbidden)
    monkeypatch.setattr('app.services.llm.credentials.resolve_developer_api_keys', forbidden)
    jobs._scans.clear()
    jobs._heartbeats.clear()
    jobs.process_one(repo)
    stored = repo.get(job['job_id'])
    assert stored['status'] == 'cancelled'
    assert stored['next_attempt_at'] is None
    assert stored['snapshot']['reason_code'] == 'chat_only'
    assert stored['completed_packages'] == 0


def test_historical_watch_read_preserves_answer_sources_and_stored_data():
    data = {'consensus_md': 'Saved answer. [S1]', 'differences_data': {'agreement': {'score': 76}},
            'sources': [{'id': 'S1', 'title': 'Original source', 'url': 'https://example.test'}],
            'source_verification': {'status': 'complete', 'job_id': 'old-watch-job'}}
    before = deepcopy(data)
    result = share_snapshots._watch_version_payload('historic123', data)
    assert result['source_verification'] is None
    assert result['consensus_md'] == data['consensus_md']
    assert result['sources'][0]['url'] == data['sources'][0]['url']
    assert result['differences_data']['agreement']['score'] == 76
    assert data == before
