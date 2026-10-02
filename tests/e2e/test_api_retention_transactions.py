"""Native migration transactions keep independent expiry/fences unchanged."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from app.services import api_run_repository as api
from native_support import native_db, race_with_worker_retry, tree


def test_retention_backfill_is_atomic_and_does_not_renew_another_run(
    native_db, monkeypatch
):
    db = native_db
    monkeypatch.setattr(api, "API_RUNS_COLLECTION", "audit-api-" + uuid4().hex)
    owner = db.owner()
    repo = api.FirestoreApiRunRepository(db)
    ref = db.tracked(api.API_RUNS_COLLECTION)
    stamp = datetime.now(timezone.utc) - timedelta(days=4)
    ref.set({"uid": owner, "idempotency_hash": "key", "accepted_at": stamp})
    mapping = repo._idempotency_ref(owner, "key")
    mapping.set({"run_id": "f" * 32, "expires_at": stamp + timedelta(days=90)})
    before = mapping.get().to_dict()
    outcomes = race_with_worker_retry(
        repo.backfill_retention, repo.backfill_retention,
        snapshot=lambda: {"run": tree(ref), "mapping": tree(mapping)},
    )
    assert sorted(outcomes) == [0, 1]
    assert ref.get().to_dict()["expires_at"] == stamp + timedelta(days=30)
    assert mapping.get().to_dict() == before
    # A missing mapping is not recreated, and missing dates stay explicitly unknown.
    missing = db.tracked(api.API_RUNS_COLLECTION)
    missing.set({"uid": owner, "idempotency_hash": "unknown"})
    assert repo.backfill_retention() == 0
    assert not repo._idempotency_ref(owner, "unknown").get().exists


def test_backfill_rechecks_document_after_scan_before_commit(native_db, monkeypatch):
    db = native_db
    monkeypatch.setattr(api, "API_RUNS_COLLECTION", "audit-api-" + uuid4().hex)
    owner = db.owner()
    repo = api.FirestoreApiRunRepository(db)
    ref = db.tracked(api.API_RUNS_COLLECTION)
    stamp = datetime.now(timezone.utc)
    ref.set({"uid": owner, "idempotency_hash": "key", "accepted_at": stamp})
    future = stamp + timedelta(days=45)
    actual = repo._transaction

    def competing_writer(operation):
        ref.update({"expires_at": future})
        return actual(operation)

    monkeypatch.setattr(repo, "_transaction", competing_writer)
    assert repo.backfill_retention() == 0
    assert ref.get().to_dict()["expires_at"] == future
