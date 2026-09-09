"""Worker orchestration uses in-memory persistence and never calls paid providers."""
from copy import deepcopy
from datetime import timedelta
import json

import pytest

from app.services import source_check_jobs as jobs
from app.services import source_verification as sv
from app.services import source_documents as docs
from app.services.source_check_repository import SourceCheckRepository, utcnow, unpack
from test_source_check_repository import FakeDb

SOURCES = [{'id': 'S1', 'url': 'https://example.test/price', 'title': 'Price'}]
TEXT = 'The plan costs 20 euros.[S1]'


def doc(url, limits):
    text = 'The plan costs 20 euros.'
    return dict(text=text, url=url, title='Price', dates=[], retrieved_at='2026-09-09',
                content_hash=sv.answer_version(text), truncated=False)


def judge(payload, keys, limits):
    return {'findings': [{**pair, 'support': 'supported', 'topical': 'relevant',
        'temporal': 'not_relevant', 'reason': '', 'quotes': ['The plan costs 20 euros.']}
        for pair in payload['pairs']]}, {'cost': .01}


@pytest.fixture
def store(monkeypatch):
    db = FakeDb()
    repo = SourceCheckRepository(db)
    monkeypatch.setattr(jobs, 'repository', lambda: repo)
    monkeypatch.setattr('app.services.llm.mock_llm.mock_llm_enabled', lambda: False)
    monkeypatch.setattr(docs, 'fetch_document', doc)
    monkeypatch.setattr(sv, 'judge_sources', judge)
    monkeypatch.setenv('OPENROUTER_API_KEY', 'developer-test-key')
    jobs._keys.clear()
    jobs._active_owners.clear()
    jobs._scans.clear()
    jobs._heartbeats.clear()
    yield repo, db
    jobs._keys.clear()
    jobs._active_owners.clear()


def submit(*, own=False, uid='owner', run_key='run', key='own-test-secret', text=TEXT):
    with jobs.source_check_context(uid, run_key, own_keys=own):
        return jobs.submit_source_check(question='Price?', consensus=text, sources=SOURCES,
                                         keys={'OpenRouter': key})


def ready(repo, job_id):
    repo.ref(job_id).set({'next_attempt_at': utcnow() - timedelta(seconds=1)}, merge=True)


def test_admission_persists_complete_plan_and_only_memory_contains_own_credentials(store):
    repo, db = store
    snapshot = submit(own=True)
    assert snapshot['status'] == 'queued' and snapshot['findings'] == []
    assert jobs._keys[snapshot['job_id']][1] == 'own-test-secret'
    for row in db.documents.values():
        data = unpack(row['payload']) if 'payload' in row else row
        assert 'own-test-secret' not in repr(data)
    assert repo.get_plan(snapshot['job_id'])['limits'] == sv.Limits.configured().__dict__


def test_worker_completes_job_then_never_replays_and_forgets_key(store):
    repo, _ = store
    snapshot = submit(own=True)
    assert jobs.process_one(repo)
    finished = repo.get(snapshot['job_id'])
    assert finished['status'] == 'complete'
    assert finished['snapshot']['scope']['checked_pairs'] == 1
    assert snapshot['job_id'] not in jobs._keys
    assert not jobs.process_one(repo)


def test_restart_pauses_own_key_work_without_developer_fallback_then_owner_resumes(store, monkeypatch):
    repo, _ = store
    snapshot = submit(own=True)
    jobs._keys.clear()
    used = []
    def recording(payload, keys, limits):
        used.append(keys)
        return judge(payload, keys, limits)
    monkeypatch.setattr(sv, 'judge_sources', recording)
    assert jobs.process_one(repo)
    assert repo.get(snapshot['job_id'])['status'] == 'awaiting_credentials'
    assert used == []
    resumed = submit(own=True, key='replacement-secret')
    assert resumed['job_id'] == snapshot['job_id'] and resumed['status'] == 'queued'
    assert jobs.process_one(repo)
    assert used == [{'OpenRouter': 'replacement-secret'}]


def test_expired_or_wrong_owner_memory_key_never_used(store):
    repo, _ = store
    snapshot = submit(own=True)
    jobs._keys[snapshot['job_id']] = ('another-owner', 'other-secret', float('inf'))
    assert jobs.process_one(repo)
    assert repo.get(snapshot['job_id'])['status'] == 'awaiting_credentials'


def test_heartbeat_removes_expired_key_without_new_submission_or_paid_call(store, monkeypatch):
    from types import SimpleNamespace

    repo, _ = store
    snapshot = submit(own=True)
    expiry = jobs._keys[snapshot['job_id']][2]
    jobs._keys['still-live'] = ('owner', 'live-secret', expiry + 60)
    monkeypatch.setattr(jobs, 'time', SimpleNamespace(monotonic=lambda: expiry))
    monkeypatch.setattr(sv, 'judge_sources', lambda *_: pytest.fail('expired credential used'))

    jobs._refresh_worker(repo)

    assert snapshot['job_id'] not in jobs._keys
    assert jobs._keys['still-live'][1] == 'live-secret'
    assert jobs.process_one(repo)
    assert repo.get(snapshot['job_id'])['status'] == 'awaiting_credentials'


def test_transient_fetch_retries_only_three_times_and_leaves_explicit_result(store, monkeypatch):
    repo, _ = store
    snapshot = submit()
    calls = []
    def fail(*_):
        calls.append(1)
        raise TimeoutError('private details')
    monkeypatch.setattr(docs, 'fetch_document', fail)
    for attempt in range(3):
        assert jobs.process_one(repo)
        job = repo.get(snapshot['job_id'])
        if attempt < 2:
            assert job['status'] == 'queued' and job['completed_packages'] == 0
            assert job['next_attempt_at'] > utcnow() + timedelta(seconds=29)
            ready(repo, snapshot['job_id'])
    assert len(calls) == 3 and job['status'] == 'partial'
    plan = repo.get_plan(snapshot['job_id'])
    result = unpack(repo.ref(snapshot['job_id']).collection('packages').document('000000').get().to_dict()['payload'])
    assert result['findings'][0]['reason_code'] == 'fetch_timeout'
    assert result['findings'][0]['state'] == 'unavailable'
    assert result['runtime']['calls'] == 0


def test_permanent_fetch_failure_does_not_retry(store, monkeypatch):
    repo, _ = store
    snapshot = submit()
    monkeypatch.setattr(docs, 'fetch_document', lambda *_: (_ for _ in ()).throw(ValueError('unsupported_document')))
    assert jobs.process_one(repo)
    assert repo.get(snapshot['job_id'])['status'] == 'partial'
    assert not jobs.process_one(repo)


def test_paid_judge_failure_is_never_automatically_retried(store, monkeypatch):
    repo, _ = store
    snapshot = submit()
    calls = []
    def fail(*_):
        calls.append(1)
        raise TimeoutError('upstream secret')
    monkeypatch.setattr(sv, 'judge_sources', fail)
    assert jobs.process_one(repo)
    assert repo.get(snapshot['job_id'])['status'] == 'partial'
    assert not jobs.process_one(repo) and len(calls) == 1


def test_shared_verdict_cache_skips_paid_call_and_separates_owner_question_and_model(store, monkeypatch):
    repo, _ = store
    calls = []
    def recording(payload, keys, limits):
        calls.append(deepcopy(payload))
        return judge(payload, keys, limits)
    monkeypatch.setattr(sv, 'judge_sources', recording)
    first = submit(run_key='one')
    assert jobs.process_one(repo)
    second = submit(run_key='two')
    assert jobs.process_one(repo)
    assert len(calls) == 1
    assert repo.get(second['job_id'])['snapshot']['runtime']['calls'] == 0
    third = submit(run_key='three', uid='another')
    assert jobs.process_one(repo) and len(calls) == 2
    monkeypatch.setattr(sv.cfg, 'SOURCE_VERIFICATION_MODEL', 'openai/gpt-5-mini')
    fourth = submit(run_key='four')
    assert jobs.process_one(repo) and len(calls) == 3
    fetch_judge = jobs._cached_judge('owner', repo)
    changed = deepcopy(calls[0])
    changed['resolved_question'] = 'Different historical period'
    fetch_judge(changed, {}, sv.Limits())
    assert len(calls) == 4


def test_owner_busy_does_not_prevent_another_owner_progress(store):
    repo, _ = store
    first = submit(uid='busy', run_key='one')
    second = submit(uid='free', run_key='two')
    jobs._active_owners.add('busy')
    assert jobs.process_one(repo)
    assert repo.get(first['job_id'])['status'] == 'queued'
    assert repo.get(second['job_id'])['status'] == 'complete'
    assert 'free' not in jobs._active_owners


@pytest.mark.parametrize('legacy', [False, True])
def test_queued_job_keeps_admitted_model_after_admin_change(store, monkeypatch, legacy):
    from app.services.source_check_repository import pack
    repo, _ = store
    original = 'openai/gpt-5-mini'
    monkeypatch.setattr(sv.cfg, 'SOURCE_VERIFICATION_MODEL', original)
    snapshot = submit()
    plan = repo.get_plan(snapshot['job_id'])
    assert plan['snapshot']['model'] == original
    assert plan['limits']['model'] == original
    if legacy:
        plan['limits'].pop('model')
        repo.ref(snapshot['job_id']).collection('data').document('plan').set({'payload': pack(plan)})
    monkeypatch.setattr(sv.cfg, 'SOURCE_VERIFICATION_MODEL', sv.cfg.DEFAULT_SOURCE_VERIFICATION_MODEL)
    seen = []
    def recording(payload, keys, limits):
        seen.append(limits.model)
        return judge(payload, keys, limits)
    monkeypatch.setattr(sv, 'judge_sources', recording)
    assert jobs.process_one(repo)
    assert seen == [original]
    result = repo.page(snapshot['job_id'], uid='owner')['source_verification']
    assert result['model'] == original
    newer = submit(run_key='new-model')
    assert newer['model'] == sv.cfg.DEFAULT_SOURCE_VERIFICATION_MODEL
    assert jobs.process_one(repo)
    assert seen == [original, sv.cfg.DEFAULT_SOURCE_VERIFICATION_MODEL]


def test_repeatedly_interrupted_package_gets_complete_terminal_shape(store, monkeypatch):
    repo, _ = store
    snapshot = submit()
    repo.ref(snapshot['job_id']).set({'attempts': 3}, merge=True)
    monkeypatch.setattr(sv, 'execute_source_package', lambda **_: pytest.fail('fourth execution'))
    assert jobs.process_one(repo)
    row = repo.ref(snapshot['job_id']).collection('packages').document('000000').get().to_dict()
    result = unpack(row['payload'])
    assert result['schema_version'] == 3 and result['status'] == 'partial'
    assert result['findings'][0]['state'] == 'unavailable'
    assert result['findings'][0]['reason_code'] == 'worker_interrupted'
    assert result['findings'][0]['checked_at']


def test_cache_write_failure_preserves_successful_checked_result(store, monkeypatch):
    repo, _ = store
    snapshot = submit()
    monkeypatch.setattr(repo, 'cache_put', lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError('database issue')))
    assert jobs.process_one(repo)
    assert repo.get(snapshot['job_id'])['status'] == 'complete'


def test_context_restores_prior_owner_and_no_uncited_job_is_created(store):
    repo, db = store
    assert jobs.current_context() is None
    with jobs.source_check_context('first', 'one'):
        with jobs.source_check_context('second', 'two'):
            assert jobs.current_context()['uid'] == 'second'
        assert jobs.current_context()['uid'] == 'first'
    assert jobs.current_context() is None
    snapshot = submit(text='No sources are cited.')
    assert snapshot['status'] == 'skipped' and not db.documents



def test_different_live_process_cannot_claim_or_pause_own_key_job(store, monkeypatch):
    repo, _ = store
    monkeypatch.setattr(jobs, 'WORKER_ID', 'a' * 32)
    snapshot = submit(own=True)
    before = repo.get(snapshot['job_id'])
    a_keys = jobs._keys
    monkeypatch.setattr(jobs, '_keys', {})
    monkeypatch.setattr(jobs, 'WORKER_ID', 'b' * 32)
    assert not jobs.process_one(repo)
    after = repo.get(snapshot['job_id'])
    assert after['status'] == 'queued'
    assert after['revision'] == before['revision']
    assert after.get('attempts', 0) == 0
    assert 'credential_worker_id' not in json.dumps(after['snapshot'])
    monkeypatch.setattr(jobs, '_keys', a_keys)
    monkeypatch.setattr(jobs, 'WORKER_ID', 'a' * 32)
    assert jobs.process_one(repo)
    assert repo.get(snapshot['job_id'])['status'] == 'complete'


def test_dead_process_affinity_pauses_without_attempt_or_credential_fallback(store, monkeypatch):
    from app.services.source_check_repository import WORKER_COLLECTION
    repo, db = store
    monkeypatch.setattr(jobs, 'WORKER_ID', 'a' * 32)
    snapshot = submit(own=True)
    db.collection(WORKER_COLLECTION).document('a' * 32).set({'expires_at': utcnow() - timedelta(seconds=1)})
    monkeypatch.setattr(jobs, '_keys', {})
    monkeypatch.setattr(jobs, 'WORKER_ID', 'b' * 32)
    monkeypatch.setattr(sv, 'judge_sources', lambda *_: pytest.fail('no credentials on new process'))
    assert not jobs.process_one(repo)
    after = repo.get(snapshot['job_id'])
    assert after['status'] == 'awaiting_credentials'
    assert after.get('attempts', 0) == 0
    revision = after['revision']
    assert not jobs.process_one(repo)
    assert repo.get(snapshot['job_id'])['revision'] == revision


def test_resume_on_another_http_node_transfers_queued_work_without_sticky_routing(store, monkeypatch):
    repo, _ = store
    monkeypatch.setattr(jobs, 'WORKER_ID', 'a' * 32)
    snapshot = submit(own=True)
    a_keys = jobs._keys
    monkeypatch.setattr(jobs, '_keys', {})
    monkeypatch.setattr(jobs, 'WORKER_ID', 'b' * 32)
    resumed = jobs.resume_source_check(snapshot['job_id'], 'owner', 'node-b-secret')
    assert resumed['credential_worker_id'] == 'b' * 32 and resumed['status'] == 'queued'
    b_keys = jobs._keys
    monkeypatch.setattr(jobs, '_keys', a_keys)
    monkeypatch.setattr(jobs, 'WORKER_ID', 'a' * 32)
    assert not jobs.process_one(repo)
    used = []
    def recording(payload, keys, limits):
        used.append(keys)
        return judge(payload, keys, limits)
    monkeypatch.setattr(sv, 'judge_sources', recording)
    monkeypatch.setattr(jobs, '_keys', b_keys)
    monkeypatch.setattr(jobs, 'WORKER_ID', 'b' * 32)
    assert jobs.process_one(repo)
    assert used == [{'OpenRouter': 'node-b-secret'}]


def test_resume_on_other_node_does_not_transfer_running_package(store, monkeypatch):
    repo, _ = store
    monkeypatch.setattr(jobs, 'WORKER_ID', 'a' * 32)
    snapshot = submit(own=True)
    claimed = repo.claim(snapshot['job_id'], worker_id='a' * 32)
    assert claimed and claimed['status'] == 'running'
    monkeypatch.setattr(jobs, '_keys', {})
    monkeypatch.setattr(jobs, 'WORKER_ID', 'b' * 32)
    resumed = jobs.resume_source_check(snapshot['job_id'], 'owner', 'node-b-secret')
    assert resumed['credential_worker_id'] == 'a' * 32
    assert resumed['lease_token'] == claimed['lease_token']
    assert snapshot['job_id'] not in jobs._keys


def test_expired_affinity_cannot_steal_unexpired_running_package(store, monkeypatch):
    from app.services.source_check_repository import WORKER_COLLECTION
    repo, db = store
    monkeypatch.setattr(jobs, 'WORKER_ID', 'a' * 32)
    snapshot = submit(own=True)
    claimed = repo.claim(snapshot['job_id'], worker_id='a' * 32)
    db.collection(WORKER_COLLECTION).document('a' * 32).set({'expires_at': utcnow() - timedelta(seconds=1)})
    assert repo.claim(snapshot['job_id'], worker_id='b' * 32) is None
    assert repo.get(snapshot['job_id'])['status'] == 'running'



def test_rotating_queue_scan_reaches_job_after_more_than_24_foreign_live_jobs(store, monkeypatch):
    repo, _ = store
    monkeypatch.setattr(jobs, 'WORKER_ID', 'a' * 32)
    foreign = [submit(own=True, run_key=f'foreign-{index}') for index in range(60)]
    monkeypatch.setattr(jobs, '_keys', {})
    monkeypatch.setattr(jobs, 'WORKER_ID', 'b' * 32)
    local = submit(own=False, run_key='local')
    queries = []
    original = repo.due_page
    def counted(**kwargs):
        queries.append(kwargs)
        return original(**kwargs)
    monkeypatch.setattr(repo, 'due_page', counted)
    for _ in range(4):
        jobs.process_one(repo)
        if repo.get(local['job_id'])['status'] == 'complete':
            break
    assert repo.get(local['job_id'])['status'] == 'complete'
    assert len(queries) <= 4 and any(q['cursor'] is not None for q in queries)
    assert all(repo.get(item['job_id'])['status'] == 'queued' for item in foreign)
    assert all(repo.get(item['job_id']).get('attempts', 0) == 0 for item in foreign)


def test_queue_scan_retains_unconsumed_ready_batch_for_other_workers(store):
    repo, _ = store
    snapshots = [submit(uid=f'owner-{index}', run_key=f'run-{index}') for index in range(6)]
    for _ in range(6):
        assert jobs.process_one(repo)
    assert all(repo.get(item['job_id'])['status'] == 'complete' for item in snapshots)


def test_queue_scan_wraps_to_previously_busy_owner_without_starvation(store):
    repo, _ = store
    first = submit(uid='busy', run_key='first')
    second = submit(uid='free', run_key='second')
    jobs._active_owners.add('busy')
    assert jobs.process_one(repo)
    assert repo.get(first['job_id'])['status'] == 'queued'
    assert repo.get(second['job_id'])['status'] == 'complete'
    jobs._active_owners.remove('busy')
    assert jobs.process_one(repo)
    assert repo.get(first['job_id'])['status'] == 'complete'
