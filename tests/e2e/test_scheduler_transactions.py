"""Native due queries and leases for Watch, Topic and SEO workers."""
from datetime import datetime, timedelta, timezone
import asyncio
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import uuid
import pytest
from app.services import topics, watch_service, seo_weekly_review
from native_support import native_db, race, race_with_worker_retry


def run_scheduler_scenario(scenario):
    # The session-scoped synchronous Playwright fixture owns a running event
    # loop on pytest's thread. Exercise the real scheduler on a separate loop,
    # just as the app server does, without changing the scheduler or nesting
    # asyncio.run() in Playwright's loop. Exceptions still fail the caller.
    with ThreadPoolExecutor(max_workers=1) as worker:
        worker.submit(lambda: asyncio.run(scenario())).result(timeout=30)


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


@pytest.mark.parametrize("pipeline_fails", [False, True])
def test_native_topic_loop_commits_due_tick_and_stops_on_cancel(native_db, monkeypatch, pipeline_fails):
    from app.services import topic_runner
    db, now = native_db, datetime.now(timezone.utc)
    collection = "scheduler-topics-" + uuid.uuid4().hex
    monkeypatch.setattr(topics, "TOPICS_COLLECTION", collection)
    monkeypatch.setattr(topics, "db_firestore", db)
    monkeypatch.setattr(topics, "utcnow", lambda: now)
    monkeypatch.delenv("MOCK_LLM", raising=False)
    monkeypatch.setattr(topic_runner.mailer, "is_configured", lambda: False)
    due, future = db.tracked(collection), db.tracked(collection)
    initial = {"status": "active", "update_interval": "weekly", "lead_question": "Synthetic scheduler question", "next_run_at": now}
    due.set(initial)
    future.set({**initial, "next_run_at": now + timedelta(days=1)})
    dispatched = []
    def pipeline(question, *args, **kwargs):
        dispatched.append(kwargs["claim_key_prefix"])
        assert due.get().to_dict()["current_run_id"] == dispatched[-1]
        if pipeline_fails:
            raise RuntimeError("synthetic provider failure")
        return {"consensus": "Synthetic scheduler answer", "agreement_score": 80,
                "included_models": ["OpenAI: GPT-5.6", "Google Gemini: Gemini 3.5 Flash"]}
    monkeypatch.setattr(topic_runner.topic_pipeline, "execute_topic", pipeline)

    async def scenario():
        sleeping = asyncio.Event()
        async def wait_between_ticks(seconds):
            assert seconds == topic_runner.TOPIC_SCHEDULER_INTERVAL_SECONDS
            sleeping.set()
            await asyncio.Event().wait()
        # Replace only the clock wait; due query, claim, pipeline orchestration,
        # completion/failure, health reporting and loop cancellation stay real.
        monkeypatch.setattr(topic_runner, "asyncio", SimpleNamespace(to_thread=asyncio.to_thread, sleep=wait_between_ticks))
        task = asyncio.create_task(topic_runner.topic_scheduler_loop())
        try:
            await asyncio.wait_for(sleeping.wait(), 20)
            saved = due.get().to_dict()
            assert len(dispatched) == 1
            assert saved["current_run_id"] == "" and saved["claimed_until"] is None
            assert saved["next_run_at"] > now
            runs = list(due.collection("runs").stream())
            assert len(runs) == (0 if pipeline_fails else 1)
            assert saved["last_run_status"] == ("failed" if pipeline_fails else "success")
            if runs:
                assert runs[0].id == dispatched[0]
                assert runs[0].to_dict()["consensus_md"] == "Synthetic scheduler answer"
            assert future.get().to_dict() == {**initial, "next_run_at": now + timedelta(days=1)}
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        await asyncio.sleep(0)
        assert len(dispatched) == 1 and task.cancelled()
    run_scheduler_scenario(scenario)


def test_native_seo_loop_persists_failure_releases_lease_and_cancels(native_db, monkeypatch):
    db, now = native_db, datetime.now(timezone.utc)
    config_ref = db.tracked("app_config")
    review_collection = "scheduler-seo-" + uuid.uuid4().hex
    monkeypatch.setattr(seo_weekly_review, "REVIEWS_COLLECTION", review_collection)
    class Repository(seo_weekly_review.WeeklyReviewRepository):
        @property
        def config_ref(self):
            return config_ref
        def create_review(self, run_id, data):
            db.tracked(review_collection, run_id)
            return super().create_review(run_id, data)
    config_ref.set({"enabled": True, "interval_days": 7, "run_time": "08:00", "timezone": "UTC", "next_run_at": now})
    collections, notifications = [], []
    def collect():
        collections.append(config_ref.get().to_dict()["lease_run_id"])
        assert collections[-1]
        return {"status": "failed", "reason": "synthetic external collection failure"}
    service = seo_weekly_review.SeoWeeklyReviewService(db, repository=Repository(db),
        data_service=SimpleNamespace(collect=collect), clock=lambda: now,
        notifier=lambda value: notifications.append(value) or {"status": "sent"})
    monkeypatch.setattr(seo_weekly_review, "default_service", service)
    monkeypatch.setattr(seo_weekly_review, "SCHEDULER_TICK_SECONDS", 3600)

    async def scenario():
        completed = asyncio.Event()
        original_health = seo_weekly_review.task_succeeded
        def health(*args, **kwargs):
            original_health(*args, **kwargs)
            completed.set()
        monkeypatch.setattr(seo_weekly_review, "task_succeeded", health)
        task = asyncio.create_task(seo_weekly_review.seo_review_scheduler_loop())
        try:
            await asyncio.wait_for(completed.wait(), 20)
            assert len(collections) == len(notifications) == 1
            row = db.collection(review_collection).document(collections[0]).get().to_dict()
            assert row["status"] == "collection_failed" and row["judge_called"] is False
            assert row["telegram_notification"]["status"] == "sent"
            saved = config_ref.get().to_dict()
            assert saved["lease_run_id"] == "" and saved["lease_until"] is None
            assert saved["next_run_at"] > now
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        assert seo_weekly_review._scheduler_wake_event is None
        await asyncio.sleep(0)
        assert len(collections) == 1 and task.cancelled()
    run_scheduler_scenario(scenario)
