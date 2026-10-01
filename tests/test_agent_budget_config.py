from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.api.routers import admin
from app.core.rate_limit import limiter
from app.services import agent_budget_config as budgets
from test_prompt_config import Database


def test_defaults_cover_every_tier_and_mode_and_ignore_the_legacy_agent_limit():
    config = budgets.snapshot({"daily_token_limit": 750000, "revision": 6})
    assert set(config["tier_limits"]) == {"free", "plus", "pro", "admin"}
    assert config["tier_limits"]["free"] == budgets.DEFAULT_TIER_LIMITS["free"]
    assert all(set(modes) == {"compare", "consensus", "deep_think"} for modes in config["run_estimates"].values())
    assert "daily_token_limit" not in config
    # Free/Plus keep today's capacity: old run quota x typical consensus run.
    assert budgets.DEFAULT_TIER_LIMITS["free"] == 12 * budgets.DEFAULT_RUN_ESTIMATES["free"]["consensus"]
    assert budgets.DEFAULT_TIER_LIMITS["plus"] == 30 * budgets.DEFAULT_RUN_ESTIMATES["plus"]["consensus"]
    for tier, modes in budgets.DEFAULT_RUN_ESTIMATES.items():
        assert modes["compare"] < modes["consensus"] <= modes["deep_think"]
    # Missing values default per field; present invalid values fail closed.
    partial = budgets.snapshot({"tier_limits": {"plus": 5}, "run_estimates": {"pro": {"compare": 7}}})
    assert partial["tier_limits"]["plus"] == 5 and partial["tier_limits"]["free"] == budgets.DEFAULT_TIER_LIMITS["free"]
    assert partial["run_estimates"]["pro"]["compare"] == 7
    for bad in ({"tier_limits": {"free": 0}}, {"tier_limits": {"gold": 5}}, {"tier_limits": {"free": True}},
                {"run_estimates": {"free": {"agent": 5}}}, {"run_estimates": {"free": {"compare": 2.5}}}):
        with pytest.raises(ValueError):
            budgets.snapshot(bad)


def test_tier_keys_and_modes():
    assert budgets.tier_key("plus") == "plus"
    assert budgets.tier_key("plus", admin=True) == "admin"
    assert budgets.tier_key("premium") == budgets.tier_key(None) == "free"
    assert budgets.run_mode("compare") == "compare"
    assert budgets.run_mode("anything") == "consensus"
    assert budgets.run_mode("compare", deep_think=True) == "deep_think"


def test_cached_configuration_and_atomic_reset_without_scanning_users():
    db = Database()
    clock = [1.0]
    store = budgets.BudgetConfigStore(db, clock=lambda: clock[0])
    assert store.read()['tier_limits']['free'] == budgets.DEFAULT_TIER_LIMITS['free']
    for _ in range(10):
        assert store.read()['revision'] == 0
    assert db.reads == 1
    saved = store.save(expected_revision=0, updated_by='admin', tier_limits={'free': 400000},
                       run_estimates={'free': {'compare': 20000}})
    reset = store.save(expected_revision=1, updated_by='admin', reset=True)
    assert reset['tier_limits'] == saved['tier_limits']
    assert reset['tier_limits']['free'] == 400000
    assert reset['tier_limits']['plus'] == budgets.DEFAULT_TIER_LIMITS['plus']
    assert reset['run_estimates']['free'] == {**budgets.DEFAULT_RUN_ESTIMATES['free'], 'compare': 20000}
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
        store.save(expected_revision=1, updated_by='admin', tier_limits={'pro': 600000})
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
    body = {'revision': 0, 'tier_limits': {'free': 800000}}
    for method, path, payload in [('GET', '/api/admin/agent-budget', None),
                                  ('PUT', '/api/admin/agent-budget', body),
                                  ('POST', '/api/admin/agent-budget/reset', {'revision': 0})]:
        assert api.request(method, path, json=payload).status_code == 401
        assert api.request(method, path, json=payload, headers={'Authorization': 'Bearer member'}).status_code == 403
    loaded = api.get('/api/admin/agent-budget', headers=auth).json()
    assert loaded['config']['tier_limits']['free'] == budgets.DEFAULT_TIER_LIMITS['free']
    assert loaded['defaults']['run_estimates'] == budgets.DEFAULT_RUN_ESTIMATES
    for bad in [{'tier_limits': {'free': 0}}, {'tier_limits': {'free': True}}, {'tier_limits': {'free': 2.5}},
                {'tier_limits': {'free': '500000'}}, {'tier_limits': {'free': 100000001}},
                {'tier_limits': {'gold': 5}}, {'run_estimates': {'free': {'agent': 5}}},
                {'daily_token_limit': 500000}, {}]:
        assert api.put('/api/admin/agent-budget', headers=auth, json={'revision': 0, **bad}).status_code == 422, bad
    assert api.put('/api/admin/agent-budget', headers=auth, json=body).status_code == 200
    estimates = {'revision': 1, 'run_estimates': {'pro': {'deep_think': 200000}}}
    assert api.put('/api/admin/agent-budget', headers=auth, json=estimates).status_code == 200
    assert api.post('/api/admin/agent-budget/reset', headers=auth, json={'revision': 0}).status_code == 409
    response = api.post('/api/admin/agent-budget/reset', headers=auth, json={'revision': 2})
    assert response.status_code == 200 and response.json()['config']['reset_epoch']
    config = budgets.get_config(db)
    assert config['tier_limits']['free'] == 800000
    assert config['run_estimates']['pro']['deep_think'] == 200000
