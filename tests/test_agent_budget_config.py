from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.api.routers import admin
from app.core.rate_limit import limiter
from app.services import agent_budget_config as budgets
from test_prompt_config import Database

# Captured at import, before conftest's autouse fixture lowers pro/admin to
# the historic 250k Agent allowance for every test.
PRODUCT_TIER_LIMITS = dict(budgets.DEFAULT_TIER_LIMITS)


def test_product_tier_limits_are_the_real_defaults():
    # Micro-euros per day since 2026-10-31 (Max): 1 / 2.50 / 5 / 5 EUR.
    assert PRODUCT_TIER_LIMITS == {"free": 1_000_000, "plus": 2_500_000, "pro": 5_000_000, "admin": 5_000_000}
    assert budgets.MICRO_EUR == 1_000_000 and budgets.NANO_USD_PER_MICRO_EUR == 1_150
    # A dollar cost in micro-euros, rounded up; and back.
    assert budgets.micro_eur(1_150_000_000) == 1_000_000 and budgets.micro_eur(1) == 1 and budgets.micro_eur(None) is None
    assert budgets.nano_usd(1_000_000) == 1_150_000_000


def test_defaults_cover_every_tier_and_mode_and_ignore_the_legacy_agent_limit():
    config = budgets.snapshot({"daily_token_limit": 750000, "revision": 6})
    assert set(config["tier_limits"]) == {"free", "plus", "pro", "admin"}
    assert config["tier_limits"]["free"] == budgets.DEFAULT_TIER_LIMITS["free"]
    assert all(set(modes) == {"compare", "consensus", "deep_think"} for modes in config["run_estimates"].values())
    assert "daily_token_limit" not in config
    # Free holds ten typical Consensus runs a day, Plus 2.5 times as many.
    assert budgets.DEFAULT_TIER_LIMITS["free"] == 10 * budgets.DEFAULT_RUN_ESTIMATES["free"]["consensus"]
    assert budgets.DEFAULT_TIER_LIMITS["plus"] == 25 * budgets.DEFAULT_RUN_ESTIMATES["plus"]["consensus"]
    for tier, modes in budgets.DEFAULT_RUN_ESTIMATES.items():
        assert modes["compare"] < modes["consensus"] <= modes["deep_think"]
    # Missing values default per field; present invalid values fail closed.
    partial = budgets.snapshot({"unit": "micro_eur", "tier_limits": {"plus": 5},
                                "run_estimates": {"pro": {"compare": 7}}})
    assert partial["tier_limits"]["plus"] == 5 and partial["tier_limits"]["free"] == budgets.DEFAULT_TIER_LIMITS["free"]
    assert partial["run_estimates"]["pro"]["compare"] == 7
    for bad in ({"tier_limits": {"free": 0}}, {"tier_limits": {"gold": 5}}, {"tier_limits": {"free": True}},
                {"run_estimates": {"free": {"agent": 5}}}, {"run_estimates": {"free": {"compare": 2.5}}}):
        with pytest.raises(ValueError):
            budgets.snapshot({"unit": "micro_eur", **bad})


def test_limits_saved_in_tokens_give_way_to_the_euro_defaults():
    # Until 2026-10-31 every save and every reset wrote the whole table, in
    # tokens. Read as micro-euros, Free's 660,000 tokens were 0.66 EUR a day
    # and Pro's 40,000-token Compare run 0.04 EUR.
    tokens = {"revision": 3,
              "tier_limits": {"free": 660_000, "plus": 1_650_000, "pro": 5_000_000, "admin": 5_000_000},
              "run_estimates": {tier: {"compare": 32_000, "consensus": 55_000, "deep_think": 150_000}
                                for tier in budgets.TIER_KEYS}}
    config = budgets.snapshot(tokens)
    assert config["tier_limits"] == budgets.DEFAULT_TIER_LIMITS
    assert config["run_estimates"] == budgets.DEFAULT_RUN_ESTIMATES
    assert config["revision"] == 3 and config["unit"] == "micro_eur"
    # The next save writes the unit, and what it saved stands.
    db = Database()
    db.documents[("app_config", "agent_budget")] = tokens
    store = budgets.BudgetConfigStore(db)
    saved = store.save(expected_revision=3, updated_by="admin", tier_limits={"free": 800_000})
    assert saved["unit"] == "micro_eur"
    assert saved["tier_limits"] == {**budgets.DEFAULT_TIER_LIMITS, "free": 800_000}
    assert saved["run_estimates"] == budgets.DEFAULT_RUN_ESTIMATES
    assert store.read(force=True)["tier_limits"]["free"] == 800_000


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
                {'tier_limits': {'free': '500000'}}, {'tier_limits': {'free': 1_000_000_001}},
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
