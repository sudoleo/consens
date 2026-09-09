import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routers import source_checks as api
from app.services.source_check_repository import SourceCheckRepository
from app.services.source_verification import answer_version
from test_source_check_repository import FakeDb, make_plan


@pytest.fixture
def source_api(monkeypatch):
    repo = SourceCheckRepository(FakeDb())
    monkeypatch.setattr(api.jobs, 'repository', lambda: repo)
    monkeypatch.setattr(api, 'verify_user_token', lambda token: token)
    app = FastAPI()
    app.include_router(api.router)
    app.state.limiter = api.limiter
    plan = make_plan(9)
    plan['snapshot']['answer_version'] = answer_version('Public consensus.')
    job = repo.create(uid='owner', run_key='one', plan=plan)
    with TestClient(app) as client:
        yield client, repo, job, monkeypatch


def test_owner_reads_all_pages_and_other_owner_cannot_read(source_api):
    client, repo, job, _ = source_api
    url = '/api/source-checks/' + job['job_id']
    assert client.get(url).status_code == 401
    assert client.get(url, headers={'Authorization': 'Bearer stranger'}).status_code == 404
    cursor, found = 0, []
    while cursor is not None:
        response = client.get(url, params={'cursor': cursor}, headers={'Authorization': 'Bearer owner'})
        assert response.status_code == 200
        assert response.headers['cache-control'] == 'private, no-store'
        body = response.json()
        found.extend(body['source_verification']['findings'])
        cursor = body['next_cursor']
    assert len(found) == 9
    assert all(item['pending'] for item in found)
    repo.claim(job['job_id'])
    assert client.get(url, params={'revision': 0}, headers={'Authorization': 'Bearer owner'}).status_code == 409


def test_public_access_requires_active_matching_share_and_correct_answer(source_api):
    from app.services import share_snapshots
    client, repo, job, monkeypatch = source_api
    share = {'owner_uid': 'owner', 'status': 'active', 'visibility': 'public',
             'consensus_md': 'Public consensus.', 'source_verification': job['snapshot']}
    monkeypatch.setattr(share_snapshots, 'get_share', lambda _: share)
    url = '/api/share/abcd1234/source-check'
    assert client.get(url).status_code == 200
    share['status'] = 'revoked'
    assert client.get(url).status_code == 404
    share['status'] = 'active'
    share['consensus_md'] = 'Different private content.'
    assert client.get(url).status_code == 404


def test_private_share_and_history_cannot_leak_other_jobs(source_api):
    from app.services import share_snapshots
    client, repo, job, monkeypatch = source_api
    share = {'owner_uid': 'owner', 'status': 'active', 'visibility': 'private',
             'consensus_md': 'Public consensus.', 'source_verification': job['snapshot']}
    monkeypatch.setattr(share_snapshots, 'get_share', lambda _: share)
    monkeypatch.setattr(share_snapshots, 'get_watch_version', lambda *args: None)
    url = '/api/share/abcd1234/source-check'
    assert client.get(url).status_code == 401
    assert client.get(url, headers={'Authorization': 'Bearer stranger'}).status_code == 404
    assert client.get(url, headers={'Authorization': 'Bearer owner'}).status_code == 200
    assert client.get(url, params={'version': 'notfound1'}, headers={'Authorization': 'Bearer owner'}).status_code == 404
    share['owner_uid'] = 'stranger'
    share['visibility'] = 'public'
    assert client.get(url).status_code == 404


def test_resume_does_not_accept_key_for_another_owner_or_server_job(source_api):
    client, repo, job, _ = source_api
    url = '/api/source-checks/' + job['job_id'] + '/resume'
    payload = {'openrouter_key': 'secret-that-must-not-be-stored'}
    assert client.post(url, json=payload, headers={'Authorization': 'Bearer stranger'}).status_code == 404
    assert client.post(url, json=payload, headers={'Authorization': 'Bearer owner'}).status_code == 409
    assert 'secret-that-must-not-be-stored' not in repr(repo.db.documents)


def test_invalid_cursor_has_no_unbounded_or_cross_job_access(source_api):
    client, _, job, _ = source_api
    url = '/api/source-checks/' + job['job_id']
    assert client.get(url, params={'cursor': -1}, headers={'Authorization': 'Bearer owner'}).status_code == 422
    assert client.get(url, params={'cursor': 100000}, headers={'Authorization': 'Bearer owner'}).status_code == 400


def test_unchanged_poll_does_not_read_large_plan_or_package_documents(source_api, monkeypatch):
    client, repo, job, _ = source_api
    def unexpected(*args, **kwargs):
        pytest.fail('Unchanged polling must only read the compact job header')
    monkeypatch.setattr(repo, 'get_plan', unexpected)
    response = client.get('/api/source-checks/' + job['job_id'],
        params={'after_revision': job['revision']}, headers={'Authorization': 'Bearer owner'})
    assert response.status_code == 200
    assert response.json()['unchanged'] is True
