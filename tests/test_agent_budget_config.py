from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.api.routers import admin
from app.core.rate_limit import limiter
from app.services import agent_budget_config as budgets
from test_prompt_config import Database


def test_cached_configuration_and_atomic_reset_without_scanning_users():
    db = Database()
    clock = [1.0]
    store = budgets.BudgetConfigStore(db, clock=lambda: clock[0])
    assert store.read()['daily_token_limit'] == 250000
    for _ in range(10):
        assert store.read()['revision'] == 0
    assert db.reads == 1
    saved = store.save(expected_revision=0, updated_by='admin', daily_token_limit=400000)
    reset = store.save(expected_revision=1, updated_by='admin', reset=True)
    assert reset['daily_token_limit'] == saved['daily_token_limit'] == 400000
    assert len(reset['reset_epoch']) == 32 and reset['reset_at']
    assert all(path[0] == 'app_config' for path in db.documents)
    assert len(db.documents) == 3  # one config + two audit revisions
    clock[0] += 31
    assert store.read() == reset


def test_reset_is_revision_guarded_and_write_errors_do_not_change_cached_budget():
    db = Database()
    store = budgets.BudgetConfigStore(db)
    def reset():
        try:
            return store.save(expected_revision=0, updated_by='admin', reset=True)
        except budgets.BudgetConfigConflict:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: reset(), range(2)))
    assert sum(result is not None for result in results) == 1
    prior = store.read()
    db.fail_write = True
    with pytest.raises(RuntimeError):
        store.save(expected_revision=1, updated_by='admin', daily_token_limit=600000)
    assert store.read() == prior
    db.fail_read = True
    with pytest.raises(RuntimeError):
        store.read(force=True)


@pytest.fixture
def client(monkeypatch):
    db = Database()
    monkeypatch.setattr(admin, 'db_firestore', db)
    monkeypatch.setattr(admin, 'verify_user_token', lambda token, **kwargs: token)
    monkeypatch.setattr(admin, 'is_user_admin', lambda uid: uid == 'admin')
    monkeypatch.setattr(limiter, 'enabled', False)
    app = FastAPI()
    app.include_router(admin.router)
    return TestClient(app), db


def test_admin_limit_and_reset_routes_require_role_and_revision(client):
    api, db = client
    auth = {'Authorization': 'Bearer admin'}
    for method, path, body in [('GET', '/api/admin/agent-budget', None),
                              ('PUT', '/api/admin/agent-budget', {'revision': 0, 'daily_token_limit': 800000}),
                              ('POST', '/api/admin/agent-budget/reset', {'revision': 0})]:
        assert api.request(method, path, json=body).status_code == 401
        assert api.request(method, path, json=body, headers={'Authorization': 'Bearer member'}).status_code == 403
    assert api.get('/api/admin/agent-budget', headers=auth).json()['config']['daily_token_limit'] == 250000
    for value in [0, -1, True, 2.5, '500000', 100000001]:
        assert api.put('/api/admin/agent-budget', headers=auth, json={'revision': 0, 'daily_token_limit': value}).status_code == 422
    assert api.put('/api/admin/agent-budget', headers=auth, json={'revision': 0, 'daily_token_limit': 800000}).status_code == 200
    assert api.post('/api/admin/agent-budget/reset', headers=auth, json={'revision': 0}).status_code == 409
    response = api.post('/api/admin/agent-budget/reset', headers=auth, json={'revision': 1})
    assert response.status_code == 200 and response.json()['config']['reset_epoch']
    assert budgets.get_config(db)['daily_token_limit'] == 800000
