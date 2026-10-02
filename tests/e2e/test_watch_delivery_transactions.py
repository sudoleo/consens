"""Native durable delivery and probe claims; no SMTP/provider traffic."""
from datetime import datetime, timedelta, timezone
import pytest
from app.services import notification_outbox as outbox, watch_probe, watch_service, persistence_guard
from native_support import native_db, race, tree


def test_native_outbox_claim_takeover_rejects_stale_ack_and_terminal_replay(native_db):
    db, now, uid = native_db, datetime.now(timezone.utc), native_db.owner()
    item = outbox.new_item(kind="watch_alert", channel="email", resource_id=uid, run_id="run", recipient_id=uid,
        payload={"summary": "Fixture"}, now=now, uid=uid)
    ref = db.tracked(outbox.OUTBOX_COLLECTION, item["id"])
    ref.set(item["data"])
    claims = race(*(lambda: outbox.claim(ref.id, now=now, db=db) for _ in range(2)))
    assert sum(claim is not None for claim in claims) == 1
    old = next(claim for claim in claims if claim)
    later = now + timedelta(minutes=outbox.LEASE_MINUTES + 1)
    current = outbox.claim(ref.id, now=later, db=db)
    before = ref.get().to_dict()
    assert current["lease_owner"] != old["lease_owner"]
    assert not outbox.finish(ref.id, old["lease_owner"], outbox.SENT, now=later, db=db)
    assert ref.get().to_dict() == before
    assert outbox.finish(ref.id, current["lease_owner"], outbox.SENT, now=later, db=db)
    assert outbox.claim(ref.id, now=later + timedelta(days=1), db=db) is None
    assert ref.get().to_dict()["attempts"] == 2


def test_native_probe_budget_is_atomic_and_old_configuration_cannot_schedule(native_db, monkeypatch):
    db, now = native_db, datetime(2088, 2, 3, tzinfo=timezone.utc)
    monkeypatch.setattr(watch_probe.cfg, "get_watch_probe_max_per_day", lambda: 1)
    budget = watch_probe._budget_ref(db, now)
    db.tracked(budget.parent.id, budget.id)
    refs = [db.tracked("watches") for _ in range(2)]
    for ref in refs:
        ref.set({"owner_uid": db.owner(), "status": "active", "interval": "weekly", "model_tier": "pro",
            "next_probe_at": now, "next_run_at": now + timedelta(days=5), "condition": "original"})
    outcomes = race(*(lambda ref=ref: watch_probe.claim_probe(ref.id, now=now, db=db) for ref in refs))
    assert sorted(reason for claim, reason in outcomes) == ["budget", "claimed"]
    assert budget.get().to_dict()["count"] == 1
    index = next(index for index, outcome in enumerate(outcomes) if outcome[0])
    claimed, ref = outcomes[index][0], refs[index]
    ref.update({"condition": "new decision"})
    before = ref.get().to_dict()
    assert not watch_probe.record_probe(ref.id, {"outcome": watch_probe.OUTCOME_NEW}, now=now,
        db=db, expected_claim=claimed)
    assert ref.get().to_dict() == before
    ref.update({"condition": "original"})
    assert watch_probe.record_probe(ref.id, {"outcome": watch_probe.OUTCOME_NEW}, now=now,
        db=db, expected_claim=claimed)
    assert ref.get().to_dict()["next_run_at"] == now
    completed = ref.get().to_dict()
    assert not watch_probe.record_probe(ref.id, {"outcome": watch_probe.OUTCOME_NEW}, now=now + timedelta(minutes=1),
        db=db, expected_claim=claimed)
    assert ref.get().to_dict() == completed


def test_native_watch_result_and_outbox_commit_atomically_and_survive_worker_loss(native_db):
    db, now, uid = native_db, datetime.now(timezone.utc), native_db.owner()
    share = db.tracked("shares")
    share.set({"owner_uid": uid, "status": "active"})
    watch = db.tracked("watches")
    data = {"owner_uid": uid, "share_id": share.id, "status": "active", "current_run_id": "native-run",
        "interval": "weekly", "model_tier": "pro", "next_run_at": now, "condition": ""}
    watch.set(data)
    item = outbox.new_item(kind="watch_alert", channel="email", resource_id=watch.id, run_id="native-run",
        recipient_id=uid, payload={"summary": "durable"}, now=now, uid=uid)
    delivery = db.tracked(outbox.OUTBOX_COLLECTION, item["id"])
    before = {"watch": tree(watch), "share": tree(share)}
    def failed_builder(*args):
        raise RuntimeError("Abort before native commit")
    result = {"consensus": "Evidence answer", "sources": [], "changed": False}
    with pytest.raises(RuntimeError, match="Abort before"):
        watch_service.complete_watch_run(watch.id, data, result, now=now, db=db, notifications=failed_builder)
    assert {"watch": tree(watch), "share": tree(share)} == before
    assert not delivery.get().exists
    completed = watch_service.complete_watch_run(watch.id, data, result, now=now, db=db, notifications=lambda *args: [item])
    assert completed["run_id"] == "native-run"
    assert share.collection("watch_history").document("native-run").get().exists
    assert delivery.get().to_dict()["status"] == outbox.STATUS_PENDING
    # No delivery callback occurred: a fresh worker sees the committed intent.
    assert delivery.id in outbox.list_due_ids(now=now, db=db)
    assert watch_service.complete_watch_run(watch.id, data, result, now=now, db=db, notifications=lambda *args: [item]) is None
    assert len(list(share.collection("watch_history").stream())) == 1


def test_native_owner_tombstone_fences_watch_and_probe_late_results(native_db):
    db, now, uid = native_db, datetime.now(timezone.utc), native_db.owner()
    share, watch = db.tracked("shares"), db.tracked("watches")
    share.set({"owner_uid": uid, "status": "active"})
    data = {"owner_uid": uid, "share_id": share.id, "status": "active", "current_run_id": "late-run",
        "interval": "weekly", "model_tier": "pro", "next_run_at": now, "condition": ""}
    watch.set(data)
    db.tracked("account_deletion_jobs", uid).set({"status": "pending"})
    before = (tree(watch), tree(share))
    with pytest.raises(persistence_guard.AccountDeletionInProgress):
        watch_service.complete_watch_run(watch.id, data, {"consensus": "late"}, now=now, db=db)
    with pytest.raises(persistence_guard.AccountDeletionInProgress):
        watch_service.claim_watch(watch.id, now=now, db=db)
    with pytest.raises(persistence_guard.AccountDeletionInProgress):
        watch_probe.record_probe(watch.id, {"outcome": watch_probe.OUTCOME_NEW}, now=now, db=db)
    assert (tree(watch), tree(share)) == before
