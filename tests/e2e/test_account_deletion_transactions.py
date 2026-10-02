"""Full native account cascade with durable retry and independent-owner oracle."""
import uuid
import pytest
from google.cloud.firestore_v1.document import DocumentReference
from app.services import account_deletion, agent_files, persistence_guard, share_snapshots, source_check_repository
from app.services.chat_store import ChatStore
from test_source_check_repository import make_plan
from native_support import native_db, tree
from test_file_storage_transactions import cloud_files, save


AREAS = {"api_access", "user_subcollections", "chats", "waitlist_feedback", "owned_shares", "pending_results",
    "answer_receipts", "source_check_jobs", "orphan_watches", "watch_indexes", "watch_brief", "notification_outbox",
    "persistence_guards", "email_follows", "profile", "firebase_auth"}


def seed(db, uid):
    user = db.collection("users").document(uid)
    user.set({"email": uid + "@example.invalid"})
    refs = [user]
    for collection in ("bookmarks", "counters", "memory", "usage_days", "usage_runs", "llm_calls", "google_connections",
                       "google_oauth_states", "google_write_intents", "watch_state", "watch_uniques", "api_consensus_idempotency"):
        ref = user.collection(collection).document(uuid.uuid4().hex)
        ref.set({"fixture": uid})
        refs.append(ref)
    for collection, field, value in (
        ("api_consensus_keys", "uid", uid), ("api_consensus_runs", "uid", uid),
        ("pro_waitlist", "uid", uid), ("feedback", "uid", uid), ("pending_results", "owner_uid", uid),
        ("answer_receipts", "owner_uid", uid), ("notification_outbox", "uid", uid),
        ("watch_followers", "email", uid + "@example.invalid"), ("topic_followers", "email", uid + "@example.invalid"),
    ):
        ref = db.tracked(collection)
        ref.set({field: value})
        refs.append(ref)
    ref = db.tracked("shares", share_snapshots.generate_share_id())
    ref.set({"owner_uid": uid, "status": "active", "visibility": "public"})
    ref.collection("watch_history").document("old").set({"private": "answer"})
    refs.append(ref)
    orphan = db.tracked("watches")
    orphan.set({"owner_uid": uid, "status": "active", "share_id": share_snapshots.generate_share_id(), "question_hash": uid})
    refs.append(orphan)
    brief = db.tracked("watch_briefs", uid)
    brief.set({"private": "summary"})
    refs.append(brief)
    for kind in ("bookmarks", "feedback"):
        ref = db.tracked(persistence_guard.USAGE_COLLECTION, persistence_guard._owner_key(kind, uid))
        ref.set({"used": 1})
        refs.append(ref)
    ref = db.tracked("memory_edit_usage", persistence_guard._hash_uid(uid))
    ref.set({"used": 1})
    refs.append(ref)
    repo = source_check_repository.SourceCheckRepository(db)
    job = repo.create(uid=uid, run_key="cleanup", plan=make_plan(1))
    refs.append(db.tracked(repo.collection, job["job_id"]))
    db.tracked("api_consensus_account_blocks", uid)
    db.tracked("account_deletion_jobs", uid)
    return refs


def test_native_account_cascade_resumes_failed_objects_without_foreign_loss(native_db, monkeypatch):
    db, uid, other = native_db, native_db.owner(), native_db.owner()
    refs, control = seed(db, uid), seed(db, other)
    control_before = {ref.path: tree(ref) for ref in control}
    files, bucket = cloud_files(db, monkeypatch)
    chat = files.chats.create_chat(uid, execution_mode="agent")["id"]
    file = save(files, uid, chat)
    doc = files.chats._chat_ref(uid, chat).collection("documents").document(uuid.uuid4().hex)
    doc.set({"version": 1})
    doc.collection("versions").document("1").set({"files": [file], "content": "private"})
    auth_calls = []
    monkeypatch.setattr(account_deletion.auth, "revoke_refresh_tokens", lambda owner: auth_calls.append(("revoke", owner)))
    monkeypatch.setattr(account_deletion.auth, "delete_user", lambda owner: auth_calls.append(("delete", owner)))
    service = account_deletion.FirestoreAccountDeletion(db)
    service.start(uid, email=uid + "@example.invalid")
    bucket.fail_delete = True
    assert service.cleanup_uid(uid) == ["chats"]
    job = service._job_ref(uid).get().to_dict()
    assert job["status"] == "pending" and "chats" not in job["completed_areas"]
    assert set(job["completed_areas"]) == AREAS - {"chats"}
    with pytest.raises(persistence_guard.AccountDeletionInProgress):
        ChatStore(db).create_chat(uid)
    bucket.fail_delete = False
    assert account_deletion.FirestoreAccountDeletion(db).cleanup_uid(uid) == []
    final = service._job_ref(uid).get().to_dict()
    assert final["status"] == "completed" and set(final["completed_areas"]) == AREAS
    assert "email" not in final and final["tombstone_expires_at"] > final["completed_at"]
    assert all(tree(ref) == {} for ref in refs)
    assert bucket.data == {} and tree(files.chats._chat_ref(uid, chat)) == {}
    assert auth_calls == [("revoke", uid), ("delete", uid)]
    assert {ref.path: tree(ref) for ref in control} == control_before
    assert service._api_cleanup.is_blocked(uid)


def test_native_account_repeats_success_after_lost_checkpoint(native_db, monkeypatch):
    db, uid = native_db, native_db.owner()
    refs = seed(db, uid)
    monkeypatch.setattr(account_deletion.auth, "revoke_refresh_tokens", lambda owner: None)
    monkeypatch.setattr(account_deletion.auth, "delete_user", lambda owner: None)
    service = account_deletion.FirestoreAccountDeletion(db)
    service.start(uid, email=uid + "@example.invalid")
    original = DocumentReference.set
    def fail_checkpoint(ref, data, *args, **kwargs):
        if ref.path == service._job_ref(uid).path and "completed_areas" in data:
            raise OSError("Simulated lost checkpoint before commit")
        return original(ref, data, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(DocumentReference, "set", fail_checkpoint)
        assert set(service.cleanup_uid(uid)) == AREAS
    assert service._job_ref(uid).get().to_dict()["completed_areas"] == {}
    assert account_deletion.FirestoreAccountDeletion(db).cleanup_uid(uid) == []
    assert all(tree(ref) == {} for ref in refs)
    assert set(service._job_ref(uid).get().to_dict()["completed_areas"]) == AREAS
