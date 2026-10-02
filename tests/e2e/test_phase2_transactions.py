"""Phase-2 race regressions against the isolated Firestore emulator."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import os
import threading
import uuid

from google.cloud import firestore as google_firestore
from google.auth.credentials import AnonymousCredentials
from google.cloud.firestore_v1.base_query import FieldFilter
from google.api_core.exceptions import Aborted

from app.core.e2e_profile import E2E_PROJECT_ID, assert_safe_e2e_environment
from app.services import chat_store, share_snapshots, watch_service
from native_support import race_with_worker_retry, tree


def _emulator_db():
    assert os.environ.get("E2E_TEST_MODE") == "1", "Native tests require the explicit demo profile"
    assert_safe_e2e_environment(os.environ)
    return google_firestore.Client(project=E2E_PROJECT_ID, credentials=AnonymousCredentials())


def _delete_collection(collection):
    for snapshot in collection.stream():
        snapshot.reference.delete()


def test_two_workers_cannot_exceed_owner_watch_limit(monkeypatch):
    db = _emulator_db()
    suffix = uuid.uuid4().hex
    uid = f"phase2-watch-{suffix}"
    share_ids = [
        share_snapshots.generate_share_id(),
        share_snapshots.generate_share_id(),
    ]
    for index, share_id in enumerate(share_ids):
        question = f"Will phase two race {index} remain bounded {suffix}?"
        db.collection("shares").document(share_id).set({
            "owner_uid": uid,
            "status": "active",
            "visibility": "public",
            "slug": f"phase-two-{index}",
            "question": question,
            "question_hash": share_snapshots.question_hash(question),
            "differences_data": {"agreement": {"score": 70}},
        })

    monkeypatch.setattr(
        watch_service.cfg,
        "get_watch_active_limit",
        lambda _tier: 1,
    )

    def create(share_id):
        try:
            watch = watch_service.create_watch(
                uid,
                share_id=share_id,
                interval="weekly",
                tier="free",
                db=db,
            )
            return "created", watch["id"]
        except watch_service.WatchError as exc:
            return exc.code, ""

    try:
        # Bootstrap the real index separately from the quota race: its own
        # committed migration is not a partial write by an aborted creation.
        for share_id in share_ids:
            watch_service._ensure_watch_indexes(uid, f"share:{share_id}", db=db)
        def snapshot():
            return {
                "owner": tree(db.collection("users").document(uid)),
                "shares": {share_id: tree(db.collection("shares").document(share_id))
                           for share_id in share_ids},
                "watches": {item.id: item.to_dict() for item in db.collection("watches").where(
                    filter=FieldFilter("owner_uid", "==", uid)).stream()},
            }
        outcomes = race_with_worker_retry(
            *(lambda share_id=share_id: create(share_id) for share_id in share_ids),
            snapshot=snapshot,
        )
        assert sorted(code for code, _watch_id in outcomes) == [
            "created",
            "limit_reached",
        ]
        watches = list(db.collection("watches").where(
            filter=FieldFilter("owner_uid", "==", uid)
        ).stream())
        assert len(watches) == 1
        state = (
            db.collection("users").document(uid).collection("watch_state")
            .document("quota").get().to_dict()
        )
        assert state["active_count"] == 1
    finally:
        for snapshot in db.collection("watches").where(
            filter=FieldFilter("owner_uid", "==", uid)
        ).stream():
            watch_service.delete_watch(uid, snapshot.id, db=db)
        for share_id in share_ids:
            db.collection("shares").document(share_id).delete()
        user_ref = db.collection("users").document(uid)
        _delete_collection(user_ref.collection("watch_state"))
        _delete_collection(user_ref.collection("watch_uniques"))
        user_ref.delete()


def test_two_workers_publish_one_pending_share_and_consume_one_quota():
    db = _emulator_db()
    suffix = uuid.uuid4().hex
    uid = f"phase2-share-{suffix}"
    result_id = share_snapshots.generate_share_id()
    pending_ref = db.collection("pending_results").document(result_id)
    pending_ref.set({
        "owner_uid": uid,
        "question": f"Can publication stay idempotent under a race {suffix}?",
        "consensus_md": "Yes. The transaction is the publication boundary.",
        "differences_data": {},
        "differences_text": "",
        "sources": [],
        "included_models": ["OpenAI", "Anthropic"],
        "consensus_model": "OpenAI",
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
    })

    def publish(_worker):
        return share_snapshots.create_share_from_pending(uid, result_id, db=db)

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(publish, range(2)))
        assert len({outcome["share_id"] for outcome in outcomes}) == 1
        assert sorted(outcome["created"] for outcome in outcomes) == [False, True]
        quota = (
            db.collection("users").document(uid).collection("counters")
            .document("shares_daily").get().to_dict()
        )
        assert quota["count"] == 1
    finally:
        pending = pending_ref.get().to_dict() or {}
        for field in ("share_id", "public_share_id", "private_share_id"):
            share_id = str(pending.get(field) or "")
            if share_id:
                db.collection("shares").document(share_id).delete()
        pending_ref.delete()
        user_ref = db.collection("users").document(uid)
        _delete_collection(user_ref.collection("counters"))
        user_ref.delete()


def test_two_workers_cannot_exceed_owner_chat_limit(monkeypatch):
    db = _emulator_db()
    uid = f"phase2-chat-{uuid.uuid4().hex}"
    store = chat_store.ChatStore(db)
    monkeypatch.setattr(chat_store, "MAX_CHATS_PER_OWNER", 1)

    def create(_worker):
        try:
            return "created", store.create_chat(uid)["id"]
        except chat_store.ChatQuotaExceeded as exc:
            return exc.error_code, ""

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(create, range(2)))
        assert sorted(code for code, _chat_id in outcomes) == [
            "chat_limit_reached",
            "created",
        ]
        assert len(list(
            db.collection("users").document(uid).collection("chats").stream()
        )) == 1
    finally:
        store.delete_all_chats(uid)
        db.collection("users").document(uid).delete()


def test_parallel_reports_never_lose_increments_or_change_indexing():
    db = _emulator_db()
    share_id = share_snapshots.generate_share_id()
    ref = db.collection("shares").document(share_id)
    ref.set({
        "status": "active",
        "visibility": "public",
        "indexed": True,
        "reports_count": 0,
    })

    try:
        gate = threading.Barrier(8)
        def report(_worker):
            gate.wait(timeout=10)
            try:
                return share_snapshots.report_share(share_id, "spam", db=db)
            except ValueError as exc:
                if not isinstance(exc.__cause__, Aborted):
                    raise
                # Explicitly failed transactions are not successful reports.
                # Check their lack of side effects before one separate retry.
                return None
        with ThreadPoolExecutor(max_workers=8) as pool:
            counts = list(
                pool.map(
                    report,
                    range(8),
                )
            )
        successful = [count for count in counts if count is not None]
        partial = ref.get().to_dict()
        assert partial["reports_count"] == len(successful)
        assert sorted(successful) == list(range(1, len(successful) + 1))
        counts = successful + [share_snapshots.report_share(share_id, "spam", db=db)
                               for count in counts if count is None]
        stored = ref.get().to_dict()
        assert sorted(counts) == list(range(1, 9))
        assert stored["reports_count"] == 8
        assert stored["report_reasons"] == {"spam": 8}
        assert stored["needs_review"] is True
        assert stored["indexed"] is True  # Reports queue review; only admin changes indexing.
    finally:
        ref.delete()
