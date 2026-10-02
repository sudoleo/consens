"""Memory undo through main, real auth/tier/revision/deletion policies."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

from app.api.routers import users
from app.core import config, security
from app.services import memory_edit, persistence_guard, user_memory
from adapter_test_support import http_adapter, login


@pytest.fixture
def memory_http(http_adapter, monkeypatch):
    h = http_adapter
    monkeypatch.setattr(
        config, "MEMORY_EDIT_CONFIG", deepcopy(config.DEFAULT_MEMORY_EDIT_CONFIG)
    )
    h.db.collection("users").document("owner").set({"tier": "free"})
    h.db.collection("users").document("stranger").set({"tier": "free"})
    h.repo = memory_edit.FirestoreMemoryEditRepository(h.db)
    h.profile = {
        **user_memory.empty_profile(),
        "role": "Engineer",
        "notes": "Keep this complete note.",
    }
    h.repo._profile_ref("owner").set({**h.profile, "revision": 4})
    h.now = datetime.now(timezone.utc)
    h.request = "memory-http-request"
    reserved = h.repo.reserve(
        "owner",
        client_request_id=h.request,
        fingerprint="f" * 64,
        tier="free",
        config=config.get_memory_edit_config(),
        now=h.now,
    )
    h.result = h.repo.apply_patch(
        "owner",
        client_request_id=h.request,
        fingerprint="f" * 64,
        lease_nonce=reserved["lease_nonce"],
        memory_limit=config.get_memory_char_limit("free"),
        patch={"operation": "replace", "target": "Engineer", "replacement": "Designer"},
        now=h.now,
    )
    h.provider = Mock(
        side_effect=AssertionError("Undo/rejected edits must not call a model")
    )
    monkeypatch.setattr(users, "memory_edit_repository", h.repo)
    monkeypatch.setattr(
        users,
        "memory_edit_service",
        memory_edit.MemoryEditService(h.repo, provider=h.provider),
    )
    h.payload = {"revision_id": h.result["revision_id"]}
    return h


@pytest.mark.parametrize(
    "scenario,status,code",
    [
        ("no_auth", 401, None),
        ("invalid_auth", 401, None),
        ("tier_outage", 503, None),
        ("foreign", 404, "revision_not_found"),
        ("missing", 404, "revision_not_found"),
        ("invalid_id", 422, None),
        ("expired", 409, "undo_expired"),
        ("conflict", 409, "revision_conflict"),
        ("limit", 422, "memory_limit"),
    ],
)
def test_main_undo_errors_preserve_all_state_and_never_call_provider(
    memory_http, monkeypatch, scenario, status, code
):
    h = memory_http
    identity = "owner"
    if scenario == "no_auth":
        identity = None
    elif scenario == "invalid_auth":
        identity = "invalid"
    elif scenario == "tier_outage":
        h.flags["outage"] = True
    elif scenario == "foreign":
        identity = "stranger"
    elif scenario == "missing":
        h.payload["revision_id"] = "e" * 32
    elif scenario == "invalid_id":
        h.payload["revision_id"] = "not-a-revision"
    elif scenario == "expired":
        h.repo._revision_ref("owner", h.result["revision_id"]).update(
            {"undo_expires_at": h.now - timedelta(seconds=1)}
        )
    elif scenario == "conflict":
        user_memory.FirestoreUserMemoryRepository(h.db).save(
            "owner", {"notes": "Later explicit note"}, expected_revision=5
        )
    elif scenario == "limit":
        monkeypatch.setitem(config.MEMORY_EDIT_CONFIG, "memory_free_chars", 5)
    before = deepcopy(h.db.documents)
    writes = len(h.db.write_log)
    response = h.client.post(
        "/api/my/memory/undo",
        headers=login(identity) if identity else {},
        json=h.payload,
    )
    assert response.status_code == status, response.text
    assert "error" in response.json()
    if code:
        assert response.json()["error"]["error_code"] == code
        assert response.json()["error"]["message"]
    assert "private database diagnostic" not in response.text
    assert h.db.documents == before and len(h.db.write_log) == writes
    h.provider.assert_not_called()


@pytest.mark.parametrize("endpoint", ["undo", "edit"])
def test_main_previously_authenticated_memory_write_is_fenced_by_tombstone(
    memory_http, endpoint
):
    h = memory_http
    # The auth result predates account deletion; the repository must independently
    # fence the already authenticated request in its own transaction.
    assert security.verify_user_token("owner") == "owner"
    h.db.collection(persistence_guard.ACCOUNT_DELETION_JOBS_COLLECTION).document(
        "owner"
    ).set({"status": "pending"})
    payload = (
        h.payload
        if endpoint == "undo"
        else {
            "client_request_id": "late-edit-request",
            "source_kind": "consensus",
            "selected_text": "Engineer",
            "correction": "Designer",
            "intent": "correct",
        }
    )
    before = deepcopy(h.db.documents)
    response = h.client.post(
        "/api/my/memory/" + endpoint, headers=login("owner"), json=payload
    )
    assert response.status_code == 403, response.text
    assert response.json() == {"error": "This account is being deleted."}
    assert h.db.documents == before
    h.provider.assert_not_called()


def test_main_undo_retry_restores_every_profile_field_without_second_revision_or_charge(
    memory_http,
):
    h = memory_http
    quota_before = deepcopy(
        {p: data for p, data in h.db.documents.items() if p[0] != "users"}
    )
    response = h.client.post(
        "/api/my/memory/undo", headers=login("owner"), json=h.payload
    )
    assert response.status_code == 200, response.text
    assert response.json() == {
        "status": "undone",
        "revision_id": h.result["revision_id"],
        "revision": 6,
    }
    profile = h.repo._profile_ref("owner").get().to_dict()
    assert {field: profile[field] for field in h.profile} == h.profile
    after = deepcopy(h.db.documents)
    replay = h.client.post(
        "/api/my/memory/undo", headers=login("owner"), json=h.payload
    )
    assert replay.json() == response.json() and h.db.documents == after
    assert {
        p: data for p, data in h.db.documents.items() if p[0] != "users"
    } == quota_before
    h.provider.assert_not_called()
