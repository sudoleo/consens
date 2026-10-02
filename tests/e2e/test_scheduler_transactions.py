"""Native due queries and leases for Watch, Topic and SEO workers."""
from datetime import datetime, timedelta, timezone
from app.services import topics, watch_service, seo_weekly_review
from native_support import native_db, race, race_with_worker_retry


def test_native_due_queries_and_topic_claim_fence(native_db):
    db, now = native_db, datetime(2087, 1, 4, tzinfo=timezone.utc)
    refs = []
    for collection in (topics.TOPICS_COLLECTION, watch_service.WATCHES_COLLECTION):
        group = []
        for status, due in (("active", now), ("active", now + timedelta(days=1)), ("paused", now)):
            ref = db.tracked(collection)
            ref.set({"status": status, "next_run_at": due, "update_interval": "weekly"})
            group.append(ref)
        refs.append(group)
    for group, query in zip(refs, (topics.list_due_topic_ids, watch_service.list_due_watch_ids)):
        result = query(now=now, db=db)
        assert group[0].id in result and all(ref.id not in result for ref in group[1:])
    ref = refs[0][0]
    def claim():
        try:
            return topics.claim_topic_run(ref.id, now=now, db=db)
        except topics.TopicError as exc:
            assert exc.code == "conflict"
    values = race_with_worker_retry(claim, claim, snapshot=lambda: ref.get().to_dict())
    old = next(value for value in values if value)
    assert sum(value is not None for value in values) == 1
    later = now + timedelta(minutes=topics.TOPIC_RUN_LEASE_MINUTES + 1)
    fresh = topics.claim_topic_run(ref.id, now=later, db=db)
    before = ref.get().to_dict()
    assert not topics.fail_topic_run(ref.id, "late failure", now=later, db=db, expected_claim_id=old["current_run_id"])
    assert ref.get().to_dict() == before
    assert fresh["current_run_id"] != old["current_run_id"]


def test_native_seo_claim_and_finish_require_current_owner(native_db):
    db, now = native_db, datetime.now(timezone.utc)
    ref = db.tracked("app_config")
    class Repository(seo_weekly_review.WeeklyReviewRepository):
        @property
        def config_ref(self):
            return ref
    outcomes = race_with_worker_retry(lambda: Repository(db).acquire("first", now),
        lambda: Repository(db).acquire("second", now), snapshot=lambda: ref.get().to_dict())
    assert sorted(outcomes) == [False, True]
    old = ref.get().to_dict()["lease_run_id"]
    later = now + timedelta(minutes=seo_weekly_review.LEASE_MINUTES + 1)
    assert Repository(db).acquire("replacement", later)
    before = ref.get().to_dict()
    assert Repository(db).finish_lease(old, later, 7) is False
    assert ref.get().to_dict() == before
    assert Repository(db).finish_lease("replacement", later, 7) is True
    saved = ref.get().to_dict()
    assert saved["lease_run_id"] == "" and saved["next_run_at"] > later
    assert Repository(db).finish_lease("replacement", later + timedelta(hours=1), 7) is False
    assert ref.get().to_dict() == saved


def test_native_watch_claim_budget_and_stale_renewal(native_db):
    db, now = native_db, datetime(2086, 2, 4, tzinfo=timezone.utc)
    watch = db.tracked(watch_service.WATCHES_COLLECTION)
    budget = db.tracked(watch_service.RUNTIME_COLLECTION, "daily_" + now.strftime("%Y%m%d"))
    watch.set({"owner_uid": db.owner(), "status": "active", "next_run_at": now})
    outcomes = race_with_worker_retry(*(lambda: watch_service.claim_watch(watch.id, now=now, db=db) for _ in range(2)),
        snapshot=lambda: (watch.get().to_dict(), budget.get().to_dict()))
    assert sorted(reason for claimed, reason in outcomes) == ["claimed", "claimed"]
    # The non-winner's reason is also 'claimed': the lease is already occupied.
    claims = [claimed for claimed, reason in outcomes if claimed]
    assert len(claims) == 1 and budget.get().to_dict()["count"] == 1
    later = now + timedelta(minutes=watch_service.WATCH_LEASE_MINUTES + 1)
    current, reason = watch_service.claim_watch(watch.id, now=later, db=db)
    before = watch.get().to_dict()
    assert current["current_run_id"] != claims[0]["current_run_id"]
    assert not watch_service.renew_watch_lease(watch.id, claims[0]["current_run_id"], now=later, db=db)
    assert watch.get().to_dict() == before
