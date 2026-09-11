"""V4 admission, durable execution and version fencing through existing jobs."""
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import timedelta

import pytest

from app.services import source_check_jobs as jobs, source_verification as sv
from app.services import contradiction_verification as cv, source_documents as docs
from app.services.source_check_repository import SourceCheckRepository, SourceCheckNotFound, unpack
from test_source_check_repository import FakeDb
from test_contradiction_verification import CONSENSUS, SOURCES, ANSWERS, differences, plan, doc, judge


@pytest.fixture
def store(monkeypatch):
    repo = SourceCheckRepository(FakeDb())
    monkeypatch.setattr(jobs, 'repository', lambda: repo)
    monkeypatch.setattr('app.services.llm.mock_llm.mock_llm_enabled', lambda: False)
    monkeypatch.setattr(docs, 'fetch_document', doc)
    monkeypatch.setattr(cv, 'judge_contradictions', judge)
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-server-key')
    jobs._keys.clear()
    jobs._scans.clear()
    jobs._active_owners.clear()
    jobs._heartbeats.clear()
    yield repo
    jobs._keys.clear()


def submit(data=None, *, run='run-1', own=False, context_uid='owner'):
    with jobs.source_check_context(context_uid, run, own_keys=own):
        return jobs.submit_source_check(question='Price?', consensus=CONSENSUS,
            sources=SOURCES, model_sources=SOURCES, model_answers=ANSWERS,
            differences_data=differences() if data is None else data,
            keys={'OpenRouter': 'private-key'})


def test_admission_binding_and_positions_idempotency(store):
    first = submit()
    assert first['run_id'] == 'run-1' and first['schema_version'] == 4
    assert first['job_id'] == submit()['job_id']
    changed = differences()
    changed['differences'][0]['positions'][0]['stance'] = 'Exactly 20 euros'
    assert first['job_id'] != submit(changed)['job_id']
    assert first['job_id'] != submit(run='run-2')['job_id']
    accepted = store.get_plan(first['job_id'])
    assert accepted['limits'] == asdict(sv.Limits.configured())
    assert len(accepted['packages']) == 1
    with pytest.raises(SourceCheckNotFound):
        store.get(first['job_id'], 'stranger')


def test_worker_persists_both_positions_original_quotes_and_documents(store):
    stub = submit(own=True)
    pending = store.page(stub['job_id'], uid='owner')['source_verification']
    assert pending['findings'][0]['state'] == 'pending'
    assert jobs.process_one(store)
    result = store.page(stub['job_id'], uid='owner')['source_verification']
    assert result['status'] == 'complete'
    assert result['scope']['checked_contradictions'] == 1
    assert len(result['documents']) == 2
    finding = result['findings'][0]
    assert finding['verdict'] == 'sources_conflict'
    assert {e['position_id'] for e in finding['evidence']} == {'P1', 'P2'}
    assert {e['source_id'] for e in finding['evidence']} == {s['id'] for s in result['sources']}
    assert 'private-key' not in repr(store.db.documents)
    assert stub['job_id'] not in jobs._keys
    assert not jobs.process_one(store)


@pytest.mark.parametrize('field', ['run_id', 'answer_version', 'positions_version'])
def test_repository_rejects_result_from_changed_binding(store, field):
    stub = submit()
    claim = store.claim(stub['job_id'])
    accepted = store.get_plan(stub['job_id'])
    result = sv.execute_source_package(package=accepted['packages'][0], question='Price?',
        answer_version=accepted['answer_version'], keys={}, limits=sv.Limits(), fetch=doc, judge=judge)
    result['findings'][0][field] = 'another-version'
    assert store.finish_package(claim, result)
    finding = store.page(stub['job_id'])['source_verification']['findings'][0]
    assert finding['state'] == 'unavailable'
    assert finding['reason_code'] == 'invalid_output'
    assert finding['evidence'] == []
    assert finding[field] == accepted['packages'][0]['pairs'][0][field]


def test_budget_omissions_survive_job_pages_and_completion(store):
    data = differences()
    data['differences'] *= 3
    limits = replace(sv.Limits(), max_contradictions=1)
    accepted = plan(differences_data=data, limits=limits)
    accepted['limits'] = asdict(limits)
    job = store.create(uid='owner', run_key='run-1', plan=accepted)
    page = store.page(job['job_id'])['source_verification']
    assert [f['state'] for f in page['findings']] == ['pending', 'omitted', 'omitted']
    assert jobs.process_one(store)
    result = store.page(job['job_id'])['source_verification']
    assert result['scope']['omitted_contradictions'] == 2
    assert result['scope']['checked_contradictions'] == 1
    assert result['status'] == 'partial'


def test_v4_own_key_restart_resumes_same_job_and_interruption_stays_v4(store):
    stub = submit(own=True)
    jobs._keys.clear()
    assert jobs.process_one(store)
    assert store.get(stub['job_id'])['status'] == 'awaiting_credentials'
    assert submit(own=True)['job_id'] == stub['job_id']
    store.ref(stub['job_id']).set({'attempts': 3}, merge=True)
    assert jobs.process_one(store)
    result = store.page(stub['job_id'])['source_verification']
    assert result['schema_version'] == 4 and result['status'] == 'partial'
    assert result['findings'][0]['reason_code'] == 'worker_interrupted'


def test_no_eligible_contradictions_and_persistence_errors_are_distinct(store, monkeypatch):
    assert submit({'differences': []})['reason_code'] == 'no_checkable_contradictions'
    monkeypatch.setattr(store, 'create', lambda **kw: (_ for _ in ()).throw(RuntimeError('store failed')))
    result = jobs.submit_advisory(question='Price?', consensus=CONSENSUS, sources=SOURCES,
        model_answers=ANSWERS, differences_data=differences(), keys={},
        context={'uid': 'owner', 'run_key': 'run-1'})
    assert result['schema_version'] == 4 and result['status'] == 'failed'
    assert result['reason_code'] == 'persistence_error'


def test_cached_judge_contract_separates_legacy_from_disputes(store, monkeypatch):
    seen = []
    monkeypatch.setattr(cv, 'judge_contradictions', lambda payload, keys, limits: (seen.append('v4') or {}, {}))
    monkeypatch.setattr(sv, 'judge_sources', lambda payload, keys, limits: (seen.append('v3') or {}, {}))
    cached = jobs._cached_judge('owner', store)
    for payload in ({'check_type': cv.MODE}, {'check_type': cv.MODE}, {}):
        cached(payload, {}, sv.Limits())
    assert seen == ['v4', 'v3']


def test_v4_cache_rpc_is_skipped_when_it_cannot_fit_remaining_budget(store, monkeypatch):
    from app.services.llm.provider_runtime import AnalysisBudget, bind_analysis_budget
    monkeypatch.setattr(store, 'cache_get', lambda *a: pytest.fail('Cache RPC exceeds remaining budget'))
    monkeypatch.setattr(store, 'cache_put', lambda *a, **kw: pytest.fail('Cache RPC exceeds remaining budget'))
    with bind_analysis_budget(AnalysisBudget(seconds=1, max_calls=1)):
        assert jobs._cached_fetch('owner', store, bounded=True)('https://example.com/a', sv.Limits())['text']


def test_share_snapshot_preserves_factual_classification_and_position_provenance():
    from app.services.share_snapshots import sanitize_differences_data
    data = differences()
    data['differences'][0]['claim'] = 'Plan price'
    restored = sanitize_differences_data(data)['differences'][0]
    assert restored['factual_check']['checkable'] is True
    assert restored['consensus_anchor_validated'] is True
    assert restored['positions'][1]['quote_models'] == ['Anthropic']


def test_validation_diagnostics_survive_job_storage_and_polling(store, monkeypatch):
    def invalid(payload, *args):
        raw, usage = judge(payload, *args)
        raw['findings'][0]['evidence'][0]['quote'] = 'An invented quote.'
        return raw, usage
    monkeypatch.setattr(cv, 'judge_contradictions', invalid)
    stub = submit()
    assert jobs.process_one(store)
    result = store.page(stub['job_id'], uid='owner')['source_verification']
    finding = result['findings'][0]
    assert finding['reason_code'] == 'evidence_mismatch'
    assert finding['validation_errors'][0]['code'] == 'quote_not_in_passages'
    assert finding['evidence'] == []
    assert 'An invented quote.' not in str(result)
    assert sv.stored_verification(result, CONSENSUS)['findings'][0]['validation_errors'] == finding['validation_errors']


@pytest.mark.parametrize('legacy', [False, True])
def test_queued_fallback_selection_is_frozen_and_legacy_jobs_remain_disabled(store, monkeypatch, legacy):
    from app.services.source_check_repository import pack
    original = 'openai/gpt-5-mini'
    monkeypatch.setattr(sv.cfg, 'SOURCE_VERIFICATION_FALLBACK_MODEL', original)
    stub = submit()
    admitted = store.get_plan(stub['job_id'])
    assert admitted['limits']['fallback_model'] == original
    if legacy:
        admitted['limits'].pop('fallback_model')
        store.ref(stub['job_id']).collection('data').document('plan').set({'payload': pack(admitted)})
    monkeypatch.setattr(sv.cfg, 'SOURCE_VERIFICATION_FALLBACK_MODEL', 'google/gemini-3.5-flash-lite')
    seen = []
    def record(payload, keys, limits):
        seen.append(limits.fallback_model)
        return judge(payload, keys, limits)
    monkeypatch.setattr(cv, 'judge_contradictions', record)
    assert jobs.process_one(store)
    assert seen == ['' if legacy else original]


def test_cache_transactions_run_only_after_the_result_is_committed(store, monkeypatch):
    from app.services.llm.provider_runtime import current_analysis_budget
    stub = submit()
    writes = []
    original_put = store.cache_put
    def cache_put(*args, **kwargs):
        assert current_analysis_budget() is None
        assert store.get(stub['job_id'])['status'] == 'complete'
        writes.append(args[1])
        return original_put(*args, **kwargs)
    monkeypatch.setattr(store, 'cache_put', cache_put)
    assert jobs.process_one(store)
    assert len(writes) == 3  # Both source documents plus the judge output.


def test_failed_result_commit_never_repeats_paid_v4_work(store, monkeypatch):
    stub = submit()
    calls = []
    def recorded(payload, *args):
        calls.append(payload)
        return judge(payload, *args)
    monkeypatch.setattr(cv, 'judge_contradictions', recorded)
    original_finish = store.finish_package
    finishes = []
    def finish(*args, **kwargs):
        finishes.append(True)
        if len(finishes) == 1:
            raise RuntimeError('Commit unavailable')
        return original_finish(*args, **kwargs)
    monkeypatch.setattr(store, 'finish_package', finish)
    assert jobs.process_one(store) is False
    store.ref(stub['job_id']).set({'next_attempt_at': jobs.utcnow() - timedelta(seconds=1)}, merge=True)
    jobs._scans.clear()
    assert jobs.process_one(store)
    assert len(calls) == 1
    result = store.page(stub['job_id'], uid='owner')['source_verification']
    assert result['findings'][0]['reason_code'] == 'result_persistence_failed'
    assert result['findings'][0]['checked'] is False


@pytest.mark.parametrize('phase', ['preparation', 'execution'])
def test_worker_failure_phase_survives_retry_without_repeating_uncertain_work(store, monkeypatch, phase):
    stub = submit()
    target = 'get_plan' if phase == 'preparation' else 'execute_source_package'
    owner = store if phase == 'preparation' else sv
    original = getattr(owner, target)
    seen = []
    def failed(*args, **kwargs):
        seen.append(True)
        raise RuntimeError('private upstream message must never be persisted')
    monkeypatch.setattr(owner, target, failed)
    assert jobs.process_one(store) is False
    header = store.get(stub['job_id'])
    assert header['last_failure'] == {
        'reason_code': 'worker_' + phase + '_failed', 'package_index': 0}
    assert 'private upstream' not in repr(store.db.documents)
    monkeypatch.setattr(owner, target, original)
    monkeypatch.setattr(cv, 'judge_contradictions', lambda *args: pytest.fail('Must not repeat work'))
    store.ref(stub['job_id']).set({'next_attempt_at': jobs.utcnow() - timedelta(seconds=1)}, merge=True)
    jobs._scans.clear()
    assert jobs.process_one(store)
    result = store.page(stub['job_id'], uid='owner')['source_verification']
    assert result['findings'][0]['reason_code'] == 'worker_' + phase + '_failed'
    assert not result['findings'][0]['checked']
    assert len(seen) == 1


def test_failure_from_another_package_does_not_mislabel_a_lost_lease(store):
    stub = submit()
    store.ref(stub['job_id']).set({'attempts': 1, 'last_failure': {
        'reason_code': 'result_persistence_failed', 'package_index': 7}}, merge=True)
    assert jobs.process_one(store)
    result = store.page(stub['job_id'], uid='owner')['source_verification']
    assert result['findings'][0]['reason_code'] == 'worker_interrupted'
