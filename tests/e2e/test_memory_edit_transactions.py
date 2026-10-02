"""Native Memory revision, lease and deletion fences, with persisted oracles."""
from datetime import datetime, timedelta, timezone
import pytest
from app.core import config
from app.services import memory_edit, persistence_guard, user_memory
from native_support import native_db, race, tree


def reserved(db):
    uid, now = db.owner(), datetime.now(timezone.utc)
    repo = memory_edit.FirestoreMemoryEditRepository(db)
    repo._profile_ref(uid).set({**user_memory.empty_profile(), "role": "Engineer", "notes": "Keep all of these notes.", "revision": 4})
    db.tracked(memory_edit.USAGE_COLLECTION, memory_edit._hash(uid))
    # Leave the shared demo daily counter intact; never delete another worker's
    # global budget while cleaning up this test's private owner documents.
    request = "native-memory-request"
    reservation = repo.reserve(uid, client_request_id=request, fingerprint="f" * 64,
        tier="free", config=config.DEFAULT_MEMORY_EDIT_CONFIG, now=now)
    arguments = dict(client_request_id=request, fingerprint="f" * 64,
        lease_nonce=reservation["lease_nonce"], memory_limit=12000, now=now,
        patch={"operation": "replace", "target": "Engineer", "replacement": "Designer"})
    return uid, now, repo, arguments


def test_native_patch_and_manual_save_have_one_revision_winner(native_db):
    uid, now, repo, args = reserved(native_db)
    def patch():
        try:
            return repo.apply_patch(uid, **args)["revision"]
        except memory_edit.MemoryEditError as exc:
            assert exc.code == "revision_conflict"
    def save():
        try:
            return user_memory.FirestoreUserMemoryRepository(native_db).save_with_revision(uid,
                {**user_memory.empty_profile(), "notes": "Manual current note"}, expected_revision=4)[1]
        except user_memory.MemoryRevisionConflict:
            return None
    results = race(patch, save)
    assert sorted(value for value in results if value is not None) == [5]
    stored = repo._profile_ref(uid).get().to_dict()
    assert stored["revision"] == 5
    assert (stored["role"], stored["notes"]) in {
        ("Designer", "Keep all of these notes."), ("", "Manual current note")}


def test_native_undo_is_lossless_owner_bound_idempotent_and_revision_checked(native_db):
    db = native_db
    uid, now, repo, args = reserved(db)
    result = repo.apply_patch(uid, **args)
    revision = result["revision_id"]
    before = tree(db.collection("users").document(uid))
    for owner, limit, at, code in [
        (uid, 4, now, "memory_limit"),
        (db.owner(), 12000, now, "revision_not_found"),
        (uid, 12000, now + timedelta(days=31), "undo_expired"),
    ]:
        with pytest.raises(memory_edit.MemoryEditError) as caught:
            repo.undo(owner, revision, memory_limit=limit, now=at)
        assert caught.value.code == code
        assert tree(db.collection("users").document(uid)) == before
    restored = repo.undo(uid, revision, memory_limit=12000, now=now)
    assert repo.undo(uid, revision, memory_limit=12000, now=now) == restored
    assert repo._profile_ref(uid).get().to_dict()["notes"] == "Keep all of these notes."
    assert repo._profile_ref(uid).get().to_dict()["revision"] == 6


def test_native_lost_lease_and_account_tombstone_never_write_memory(native_db):
    db = native_db
    uid, now, repo, args = reserved(db)
    recovered = repo.reserve(uid, client_request_id=args["client_request_id"], fingerprint=args["fingerprint"],
        tier="free", config=config.DEFAULT_MEMORY_EDIT_CONFIG, now=now + timedelta(hours=1))
    assert recovered["lease_nonce"] != args["lease_nonce"]
    before = tree(db.collection("users").document(uid))
    with pytest.raises(memory_edit.MemoryEditError) as caught:
        repo.apply_patch(uid, **args)
    assert caught.value.code == "lease_lost"
    assert tree(db.collection("users").document(uid)) == before
    db.tracked("account_deletion_jobs", uid).set({"status": "pending"})
    args["lease_nonce"] = recovered["lease_nonce"]
    with pytest.raises(persistence_guard.AccountDeletionInProgress):
        repo.apply_patch(uid, **args)
    with pytest.raises(persistence_guard.AccountDeletionInProgress):
        user_memory.FirestoreUserMemoryRepository(db).save(uid, {"notes": "late"}, expected_revision=4)
    assert tree(db.collection("users").document(uid)) == before


def test_native_memory_undo_through_main_preserves_error_status_and_body(native_db, monkeypatch):
    from fastapi.testclient import TestClient
    from app.api.routers import users
    from app.core.rate_limit import limiter
    import main
    uid, now, repo, args = reserved(native_db)
    result = repo.apply_patch(uid, **args)
    monkeypatch.setattr(users, "memory_edit_repository", repo)
    monkeypatch.setattr(users, "verify_user_token", lambda token: uid)
    monkeypatch.setattr(users, "get_user_tier", lambda owner: "free")
    monkeypatch.setattr(users.cfg, "get_memory_char_limit", lambda tier: 5)
    monkeypatch.setattr(limiter, "enabled", False)
    client = TestClient(main.app)
    payload = {"revision_id": result["revision_id"]}
    headers = {"Authorization": "Bearer fixture-outer-identity"}
    assert client.post("/api/my/memory/undo", json=payload).status_code == 401
    before = tree(native_db.collection("users").document(uid))
    response = client.post("/api/my/memory/undo", headers=headers, json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["error_code"] == "memory_limit"
    assert tree(native_db.collection("users").document(uid)) == before
    def unavailable(owner):
        raise users.TierStatusUnavailable("Synthetic unavailable tier store")
    monkeypatch.setattr(users, "get_user_tier", unavailable)
    assert client.post("/api/my/memory/undo", headers=headers, json=payload).status_code == 503
    monkeypatch.setattr(users, "get_user_tier", lambda owner: "free")
    monkeypatch.setattr(users.cfg, "get_memory_char_limit", lambda tier: 12000)
    response = client.post("/api/my/memory/undo", headers=headers, json=payload)
    assert response.status_code == 200 and response.json()["status"] == "undone"
    assert repo._profile_ref(uid).get().to_dict()["notes"] == "Keep all of these notes."


def test_native_undo_rejects_a_later_manual_revision_without_any_write(native_db):
    uid, now, repo, args = reserved(native_db)
    result = repo.apply_patch(uid, **args)
    user_memory.FirestoreUserMemoryRepository(native_db).save(uid, {"notes": "Newer explicit note"}, expected_revision=5)
    before = tree(native_db.collection("users").document(uid))
    with pytest.raises(memory_edit.MemoryEditError) as caught:
        repo.undo(uid, result["revision_id"], memory_limit=12000, now=now)
    assert caught.value.code == "revision_conflict"
    assert tree(native_db.collection("users").document(uid)) == before
