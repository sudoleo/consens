"""HTTP integration seams: replace only Firebase SDK and local database."""
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from app.core import security
from app.core.rate_limit import limiter, api_uid_limiter
from test_agent_runs import Database


@pytest.fixture
def http_adapter(monkeypatch):
    import main

    db = Database()
    flags = {"outage": False}
    checks = []
    original_collection = db.collection

    def collection(name):
        if flags["outage"] and name == "users":
            raise RuntimeError("private database diagnostic")
        return original_collection(name)

    monkeypatch.setattr(db, "collection", collection)
    monkeypatch.setattr(security, "db_firestore", db)
    security._tier_cache.clear()
    security._auth_tombstone_cache.clear()

    def verify(token, **kwargs):
        checks.append((token, kwargs))
        if token == "invalid" or (token == "revoked" and kwargs.get("check_revoked")):
            raise ValueError("private auth diagnostic")
        return {"uid": token, "email_verified": True}

    monkeypatch.setattr(security.auth, "verify_id_token", verify)
    limiter.reset()
    api_uid_limiter.reset()
    yield SimpleNamespace(
        client=TestClient(main.app, raise_server_exceptions=False),
        db=db,
        flags=flags,
        checks=checks,
    )
    security._tier_cache.clear()
    security._auth_tombstone_cache.clear()
    limiter.reset()
    api_uid_limiter.reset()


def login(uid):
    return {"Authorization": "Bearer " + uid}


@pytest.fixture
def api_adapter(http_adapter, monkeypatch):
    from app.api.routers import api_v1
    from app.services.api_key_repository import FirestoreApiKeyRepository
    from app.services.api_run_repository import FirestoreApiRunRepository
    from app.services.api_account_cleanup import FirestoreApiAccountCleanup

    h = http_adapter
    h.keys = FirestoreApiKeyRepository(h.db)
    h.runs = FirestoreApiRunRepository(h.db, transaction_runner=h.db.run_transaction)
    h.cleanup = FirestoreApiAccountCleanup(h.db)
    monkeypatch.setattr(api_v1, "api_key_repository", h.keys)
    monkeypatch.setattr(api_v1, "api_run_repository", h.runs)
    monkeypatch.setattr(api_v1, "api_account_cleanup", h.cleanup)
    monkeypatch.setattr(
        security.auth,
        "get_user",
        lambda uid: SimpleNamespace(uid=uid, disabled=False, email_verified=True),
    )
    h.key = h.keys.issue("owner")["api_key"]
    h.other_key = h.keys.issue("stranger")["api_key"]
    return h
