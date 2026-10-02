"""Native Memory revision, lease and deletion fences, with persisted oracles."""
from datetime import datetime, timedelta, timezone
import pytest
from app.core import config
from app.services import memory_edit, persistence_guard, user_memory
from adapter_test_support import http_adapter, login
from native_support import native_db, race, tree


def reserved(db):
    uid, now = db.owner(), datetime.now(timezone.utc)
    repo = memory_edit.FirestoreMemoryEditRepository(db)
    repo._profile_ref(uid).set(
        {
            **user_memory.empty_profile(),
            "role": "Engineer",
            "notes": "Keep all of these notes.",
            "revision": 4,
        }
    )
    db.tracked(memory_edit.USAGE_COLLECTION, memory_edit._hash(uid))
    # Leave the shared demo daily counter intact; never delete another worker's
    # global budget while cleaning up this test's private owner documents.
    request = "native-memory-request"
    reservation = repo.reserve(
        uid,
        client_request_id=request,
        fingerprint="f" * 64,
        tier="free",
        config=config.DEFAULT_MEMORY_EDIT_CONFIG,
        now=now,
    )
    arguments = dict(
        client_request_id=request,
        fingerprint="f" * 64,
        lease_nonce=reservation["lease_nonce"],
        memory_limit=12000,
        now=now,
        patch={"operation": "replace", "target": "Engineer", "replacement": "Designer"},
    )
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
            return user_memory.FirestoreUserMemoryRepository(
                native_db
            ).save_with_revision(
                uid,
                {**user_memory.empty_profile(), "notes": "Manual current note"},
                expected_revision=4,
            )[
                1
            ]
        except user_memory.MemoryRevisionConflict:
            return None

    results = race(patch, save)
    assert sorted(value for value in results if value is not None) == [5]
    stored = repo._profile_ref(uid).get().to_dict()
    assert stored["revision"] == 5
    assert (stored["role"], stored["notes"]) in {
        ("Designer", "Keep all of these notes."),
        ("", "Manual current note"),
    }


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
    recovered = repo.reserve(
        uid,
        client_request_id=args["client_request_id"],
        fingerprint=args["fingerprint"],
        tier="free",
        config=config.DEFAULT_MEMORY_EDIT_CONFIG,
        now=now + timedelta(hours=1),
    )
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
        user_memory.FirestoreUserMemoryRepository(db).save(
            uid, {"notes": "late"}, expected_revision=4
        )
    with pytest.raises(persistence_guard.AccountDeletionInProgress):
        repo.reserve(
            uid,
            client_request_id="late-request",
            fingerprint="a" * 64,
            tier="free",
            config=config.DEFAULT_MEMORY_EDIT_CONFIG,
            now=now,
        )
    with pytest.raises(persistence_guard.AccountDeletionInProgress):
        repo.undo(uid, "b" * 32, memory_limit=12000, now=now)
    assert tree(db.collection("users").document(uid)) == before


def test_native_memory_undo_through_main_preserves_error_status_and_body(
    native_db, http_adapter, monkeypatch
):
    from copy import deepcopy
    from google.cloud.firestore_v1.document import DocumentReference
    from app.api.routers import users
    from app.core import security

    uid, now, repo, args = reserved(native_db)
    result = repo.apply_patch(uid, **args)
    monkeypatch.setattr(users, "memory_edit_repository", repo)
    monkeypatch.setattr(security, "db_firestore", native_db)
    monkeypatch.setattr(
        config, "MEMORY_EDIT_CONFIG", deepcopy(config.DEFAULT_MEMORY_EDIT_CONFIG)
    )
    monkeypatch.setitem(config.MEMORY_EDIT_CONFIG, "memory_free_chars", 5)
    client = http_adapter.client
    payload = {"revision_id": result["revision_id"]}
    headers = login(uid)
    assert client.post("/api/my/memory/undo", json=payload).status_code == 401
    before = tree(native_db.collection("users").document(uid))
    response = client.post("/api/my/memory/undo", headers=headers, json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["error_code"] == "memory_limit"
    assert tree(native_db.collection("users").document(uid)) == before
    actual_get = DocumentReference.get

    def unavailable(ref, *args, **kwargs):
        if ref.path == f"users/{uid}":
            raise OSError("Private tier storage failure")
        return actual_get(ref, *args, **kwargs)

    security._tier_cache.clear()
    with monkeypatch.context() as patch:
        patch.setattr(DocumentReference, "get", unavailable)
        response = client.post("/api/my/memory/undo", headers=headers, json=payload)
        assert response.status_code == 503 and "Private" not in response.text
    assert tree(native_db.collection("users").document(uid)) == before
    monkeypatch.setitem(config.MEMORY_EDIT_CONFIG, "memory_free_chars", 12000)
    response = client.post("/api/my/memory/undo", headers=headers, json=payload)
    assert response.status_code == 200 and response.json()["status"] == "undone"
    assert repo._profile_ref(uid).get().to_dict()["notes"] == "Keep all of these notes."


@pytest.mark.parametrize("operation,write_count", [("apply", 4), ("undo", 2)])
def test_native_memory_commit_failure_has_no_partial_profile_request_revision_or_quota(
    native_db, monkeypatch, operation, write_count
):
    from google.cloud.firestore_v1.transaction import Transaction

    uid, now, repo, args = reserved(native_db)
    revision = (
        repo.apply_patch(uid, **args)["revision_id"] if operation == "undo" else None
    )
    user = native_db.collection("users").document(uid)
    usage = native_db.collection(memory_edit.USAGE_COLLECTION).document(
        memory_edit._hash(uid)
    )
    before = (tree(user), usage.get().to_dict())
    attempted = []

    def reject_commit(tx):
        attempted.append(len(tx._write_pbs))
        raise OSError("Synthetic native commit transport failure")

    # Inject only the SDK commit transport failure after all writes are queued.
    # Every product read, revision/tombstone guard and write plan runs normally.
    with monkeypatch.context() as patch:
        patch.setattr(Transaction, "_commit", reject_commit)
        with pytest.raises(OSError, match="native commit transport"):
            if operation == "undo":
                repo.undo(uid, revision, memory_limit=12000, now=now)
            else:
                repo.apply_patch(uid, **args)
    assert attempted == [write_count]
    assert (tree(user), usage.get().to_dict()) == before


def test_native_undo_rejects_a_later_manual_revision_without_any_write(native_db):
    uid, now, repo, args = reserved(native_db)
    result = repo.apply_patch(uid, **args)
    user_memory.FirestoreUserMemoryRepository(native_db).save(
        uid, {"notes": "Newer explicit note"}, expected_revision=5
    )
    before = tree(native_db.collection("users").document(uid))
    with pytest.raises(memory_edit.MemoryEditError) as caught:
        repo.undo(uid, result["revision_id"], memory_limit=12000, now=now)
    assert caught.value.code == "revision_conflict"
    assert tree(native_db.collection("users").document(uid)) == before
