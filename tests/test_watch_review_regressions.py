"""Regressions for review findings R16 (stale watch runs), R17 (durable
notification outbox) and R30 (owner-bound global watch lease).

All tests run offline against the in-memory FakeDb from the watch suite.
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_watch_feature import FakeDb, share  # noqa: E402

from app.services import (  # noqa: E402
    notification_delivery,
    notification_outbox as outbox,
    persistence_guard,
    topics,
    watch_brief,
    watch_followers,
    watch_scheduler,
    watch_service,
)


NOW = datetime(2026, 9, 28, 9, 0, tzinfo=timezone.utc)
SHARE_ID = "A" * 16


@pytest.fixture(autouse=True)
def _secret():
    with patch.dict(os.environ, {"WATCH_UNSUBSCRIBE_SECRET": "test-secret"}):
        yield


def _db_with_claimed_watch(**overrides):
    db = FakeDb()
    db.stores["shares"][SHARE_ID] = share()
    created = watch_service.create_watch(
        "u1", share_id=SHARE_ID, interval="weekly", tier="pro", db=db,
    )
    watch_id = created["id"]
    db.stores["watches"][watch_id].update(overrides)
    db.stores["watches"][watch_id].update(
        next_run_at=NOW - timedelta(minutes=1), claimed_until=None,
    )
    budget = {}
    from test_watch_feature import FakeDocRef, FakeTransaction

    claimed, reason = watch_service._claim_in_transaction(
        FakeTransaction(),
        FakeDocRef(db.stores["watches"], watch_id),
        FakeDocRef(budget, "day"),
        NOW,
        50,
    )
    assert reason == "claimed"
    return db, watch_id, claimed


def _owner_count(db):
    return db.stores["users/u1/watch_state"]["quota"]["active_count"]


RESULT = {
    "consensus": "A new consensus.",
    "agreement_score": 30,
    "changed": True,
    "severity": "major",
    "change_summary": "The conclusion flipped.",
    "differences_data": {},
}


# ---------------------------------------------------------------------------
# R16: a stale run can neither undo a pause nor overwrite a new schedule
# ---------------------------------------------------------------------------

def test_pause_then_stale_failure_keeps_watch_paused_and_counter_consistent():
    db, watch_id, claimed = _db_with_claimed_watch()
    assert _owner_count(db) == 1
    watch_service.update_watch("u1", watch_id, {"status": "paused"}, "pro", db=db)
    assert _owner_count(db) == 0
    assert db.stores["watches"][watch_id]["current_run_id"] is None

    assert watch_service.fail_watch_run(watch_id, claimed, now=NOW, db=db) is None

    stored = db.stores["watches"][watch_id]
    assert stored["status"] == "paused"
    assert _owner_count(db) == 0


def test_pause_then_stale_success_does_not_reactivate_or_reschedule():
    db, watch_id, claimed = _db_with_claimed_watch()
    watch_service.update_watch("u1", watch_id, {"status": "paused"}, "pro", db=db)
    before = dict(db.stores["watches"][watch_id])
    with patch.object(watch_service.share_snapshots, "invalidate_share_cache"):
        assert watch_service.complete_watch_run(
            watch_id, claimed, RESULT, now=NOW, db=db,
        ) is None
    assert db.stores["watches"][watch_id] == before
    assert _owner_count(db) == 0


def test_resume_revokes_the_old_claim_so_no_second_worker_shares_a_generation():
    db, watch_id, claimed = _db_with_claimed_watch()
    watch_service.update_watch("u1", watch_id, {"status": "paused"}, "pro", db=db)
    watch_service.update_watch("u1", watch_id, {"status": "active"}, "pro", db=db)
    stored = db.stores["watches"][watch_id]
    assert stored["status"] == "active"
    assert stored["current_run_id"] is None
    assert _owner_count(db) == 1
    # The worker from before the pause is fenced out; it cannot fail/complete.
    assert watch_service.fail_watch_run(watch_id, claimed, now=NOW, db=db) is None
    assert db.stores["watches"][watch_id]["consecutive_failures"] == 0


def test_resending_the_current_status_keeps_a_running_claim():
    db, watch_id, claimed = _db_with_claimed_watch()
    watch_service.update_watch("u1", watch_id, {"status": "active"}, "pro", db=db)
    stored = db.stores["watches"][watch_id]
    assert stored["current_run_id"] == claimed["current_run_id"]
    assert stored["claimed_until"] == claimed["claimed_until"]


def test_schedule_change_during_run_survives_completion_and_failure():
    for finish in ("complete", "fail"):
        db, watch_id, claimed = _db_with_claimed_watch()
        updated = watch_service.update_watch(
            "u1", watch_id,
            {"run_time": "18:30", "timezone": "Europe/Berlin", "interval": "monthly"},
            "pro", db=db,
        )
        new_next = db.stores["watches"][watch_id]["next_run_at"]
        assert updated["run_time"] == "18:30"
        assert db.stores["watches"][watch_id]["config_generation"] >= 1
        # The schedule edit is not a status change: the run stays current.
        assert db.stores["watches"][watch_id]["current_run_id"] == claimed["current_run_id"]
        with patch.object(watch_service.share_snapshots, "invalidate_share_cache"):
            if finish == "complete":
                assert watch_service.complete_watch_run(
                    watch_id, claimed, RESULT, now=NOW, db=db,
                ) is not None
            else:
                assert watch_service.fail_watch_run(
                    watch_id, claimed, now=NOW, db=db,
                ) is False
        stored = db.stores["watches"][watch_id]
        assert stored["run_time"] == "18:30"
        assert stored["interval"] == "monthly"
        assert stored["next_run_at"] == new_next
        assert stored["status"] == "active"


def test_third_failure_only_pauses_an_active_watch():
    db, watch_id, claimed = _db_with_claimed_watch(consecutive_failures=2)
    assert watch_service.fail_watch_run(watch_id, claimed, now=NOW, db=db) is True
    assert db.stores["watches"][watch_id]["status"] == "paused_error"
    assert _owner_count(db) == 0


def test_alert_rule_changed_during_run_is_applied_at_commit():
    db, watch_id, claimed = _db_with_claimed_watch(telegram_enabled=False)
    # The owner switches from changes_only to Telegram-only while the run works.
    db.stores["telegram_connections"]["u1"] = {"enabled": True, "chat_id": "1"}
    watch_service.update_watch(
        "u1", watch_id, {"telegram_enabled": True, "email_enabled": False}, "pro", db=db,
    )
    builder = watch_scheduler.run_notification_builder(
        watch_id, RESULT, [], now=NOW, mail_ready=True,
    )
    with patch.object(watch_service.share_snapshots, "invalidate_share_cache"):
        watch_service.complete_watch_run(
            watch_id, claimed, RESULT, now=NOW, db=db, notifications=builder,
        )
    channels = sorted(
        item["channel"] for item in db.stores["notification_outbox"].values()
    )
    assert channels == ["telegram"]


def test_condition_edited_during_run_neither_alerts_nor_records_the_old_state():
    db, watch_id, claimed = _db_with_claimed_watch(
        email_mode="condition", condition="Price above 100",
    )
    watch_service.update_watch(
        "u1", watch_id, {"condition": "Price above 200"}, "pro", db=db,
    )
    result = {**RESULT, "condition_status": "met", "condition_reason": "It is."}
    builder = watch_scheduler.run_notification_builder(
        watch_id, result, [], now=NOW, mail_ready=True,
    )
    with patch.object(watch_service.share_snapshots, "invalidate_share_cache"):
        watch_service.complete_watch_run(
            watch_id, claimed, result, now=NOW, db=db, notifications=builder,
        )
    stored = db.stores["watches"][watch_id]
    assert stored["last_condition_status"] is None
    # The old goal was met, but the owner no longer waits for it: no resolution.
    assert stored["status"] == "active"
    assert db.stores["notification_outbox"] == {}


# ---------------------------------------------------------------------------
# R30: the global worker lease has an owner
# ---------------------------------------------------------------------------

def test_expired_worker_cannot_release_the_new_owners_lease():
    db = FakeDb()
    with patch.object(watch_service, "utcnow", return_value=NOW):
        first = watch_service.acquire_worker_lease(now=NOW, db=db)
    assert first
    after_expiry = NOW + timedelta(minutes=watch_service.WORKER_LEASE_MINUTES, seconds=1)
    second = watch_service.acquire_worker_lease(now=after_expiry, db=db)
    assert second and second != first
    assert not watch_service.acquire_worker_lease(now=after_expiry, db=db)

    # A's delayed release and renewal are both refused; B stays the owner.
    assert watch_service.release_worker_lease(first, db=db) is False
    assert watch_service.renew_worker_lease(first, now=after_expiry, db=db) is False
    assert not watch_service.acquire_worker_lease(now=after_expiry, db=db)
    lease = db.stores[watch_service.RUNTIME_COLLECTION]["global_worker"]
    assert lease["owner"] == second

    # B renews, then really dies: C takes over only after B's lease expired.
    assert watch_service.renew_worker_lease(second, now=after_expiry, db=db)
    later = after_expiry + timedelta(minutes=watch_service.WORKER_LEASE_MINUTES - 1)
    assert not watch_service.acquire_worker_lease(now=later, db=db)
    much_later = after_expiry + timedelta(minutes=watch_service.WORKER_LEASE_MINUTES, seconds=1)
    third = watch_service.acquire_worker_lease(now=much_later, db=db)
    assert third and third not in {first, second}


def test_owner_release_frees_the_lease_immediately():
    db = FakeDb()
    owner = watch_service.acquire_worker_lease(now=NOW, db=db)
    assert watch_service.release_worker_lease(owner, db=db) is True
    assert watch_service.acquire_worker_lease(now=NOW, db=db)


def test_legacy_ownerless_lease_simply_expires():
    db = FakeDb()
    db.stores[watch_service.RUNTIME_COLLECTION]["global_worker"] = {
        "claimed_until": NOW + timedelta(minutes=5),
    }
    assert not watch_service.acquire_worker_lease(now=NOW, db=db)
    assert watch_service.release_worker_lease("", db=db) is False
    assert watch_service.acquire_worker_lease(now=NOW + timedelta(minutes=6), db=db)


def test_scheduler_stops_when_its_worker_lease_was_taken_over():
    started = []

    async def lose_lease(owner, stop, lost):
        lost.set()

    with (
        patch.object(watch_service, "acquire_worker_lease", return_value="owner-a"),
        patch.object(watch_service, "release_worker_lease", return_value=False) as release,
        patch.object(watch_service, "list_due_watch_ids", return_value=["w1", "w2"]),
        patch.object(watch_scheduler.watch_probe, "list_due_probe_ids", return_value=[]),
        patch.object(
            watch_service, "claim_watch",
            side_effect=lambda wid, **kw: started.append(wid) or (None, "not_due"),
        ),
        patch.object(watch_scheduler, "_renew_worker_lease_until_stopped", side_effect=lose_lease),
    ):
        asyncio.run(watch_scheduler.run_watch_tick())
    assert started == []
    release.assert_called_once_with("owner-a")


# ---------------------------------------------------------------------------
# R17: durable outbox
# ---------------------------------------------------------------------------

def _stage(db, item):
    db.run_transaction(lambda tx: outbox.stage(tx, db, item))


def _alert_item(watch_id, claimed, alert="change", email=True):
    return outbox.watch_alert_items(
        watch_id, claimed, RESULT, alert, now=NOW, email=email,
    )


def test_delivery_ids_are_stable_per_resource_run_channel_and_recipient():
    a = outbox.delivery_id("watch_alert", "w1", "run1", "email", "u1")
    assert a == outbox.delivery_id("watch_alert", "w1", "run1", "email", "u1")
    assert a != outbox.delivery_id("watch_alert", "w1", "run1", "telegram", "u1")
    assert a != outbox.delivery_id("watch_alert", "w1", "run2", "email", "u1")
    assert a != outbox.delivery_id("watch_follower", "w1", "run1", "email", "u1")


def test_crash_after_result_commit_leaves_a_retryable_item():
    db, watch_id, claimed = _db_with_claimed_watch()
    builder = watch_scheduler.run_notification_builder(
        watch_id, RESULT, [], now=NOW, mail_ready=True,
    )
    with patch.object(watch_service.share_snapshots, "invalidate_share_cache"):
        watch_service.complete_watch_run(
            watch_id, claimed, RESULT, now=NOW, db=db, notifications=builder,
        )
    # Process dies here: nothing was sent. The item is durable and due.
    assert builder.ids
    assert outbox.list_due_ids(now=NOW, db=db) == builder.ids
    sent = []
    user = SimpleNamespace(email="owner@example.test", email_verified=True)
    with (
        patch.object(notification_delivery.mailer, "is_configured", return_value=True),
        patch.object(notification_delivery.auth, "get_user", return_value=user),
        patch.object(
            notification_delivery.mailer, "send_message", new_callable=AsyncMock,
            side_effect=lambda message: sent.append(message["To"]) or True,
        ),
    ):
        counts = asyncio.run(notification_delivery.run_outbox_tick(db=db, now=NOW))
    assert counts == {"sent": 1}
    assert sent == ["owner@example.test"]
    item = db.stores["notification_outbox"][builder.ids[0]]
    assert item["status"] == "sent"
    # Retry pass after success does not send again.
    assert outbox.list_due_ids(now=NOW + timedelta(days=1), db=db) == []


def test_crash_mid_attempt_is_retried_after_the_lease():
    db = FakeDb()
    claimed = {"owner_uid": "u1", "share_id": SHARE_ID, "current_run_id": "run1"}
    item = _alert_item("w1", claimed)[0]
    _stage(db, item)
    leased = outbox.claim(item["id"], now=NOW, db=db)
    assert leased["attempts"] == 1
    # Worker died before finish: not due during the lease, due afterwards.
    assert outbox.list_due_ids(now=NOW + timedelta(minutes=1), db=db) == []
    later = NOW + timedelta(minutes=outbox.LEASE_MINUTES, seconds=1)
    assert outbox.list_due_ids(now=later, db=db) == [item["id"]]
    again = outbox.claim(item["id"], now=later, db=db)
    assert again["attempts"] == 2
    # The dead worker's late finish is fenced by the lease owner.
    assert outbox.finish(item["id"], leased["lease_owner"], outbox.SENT, now=later, db=db) is False
    assert outbox.finish(item["id"], again["lease_owner"], outbox.SENT, now=later, db=db) is True


def test_failures_back_off_and_turn_terminal_with_a_metric():
    db = FakeDb()
    claimed = {"owner_uid": "u1", "share_id": SHARE_ID, "current_run_id": "run1"}
    item = _alert_item("w1", claimed)[0]
    _stage(db, item)
    now = NOW
    for attempt in range(1, outbox.MAX_ATTEMPTS + 1):
        leased = outbox.claim(item["id"], now=now, db=db)
        assert leased is not None, attempt
        outbox.finish(item["id"], leased["lease_owner"], outbox.RETRY, now=now, db=db, error="smtp")
        stored = db.stores["notification_outbox"][item["id"]]
        if attempt < outbox.MAX_ATTEMPTS:
            assert stored["status"] == "pending"
            assert stored["next_attempt_at"] == now + outbox.retry_delay(attempt)
            now = stored["next_attempt_at"]
    stored = db.stores["notification_outbox"][item["id"]]
    assert stored["status"] == "failed"
    assert stored["last_error"] == "smtp"
    from app.core.observability import metrics_snapshot

    metric = metrics_snapshot().get("notification:watch_alert") or {}
    assert metric.get("failures", 0) >= 1


def test_expired_items_fail_instead_of_sending_stale_news():
    db = FakeDb()
    item = outbox.brief_item(
        "u1", scheduled_at=NOW, baseline=NOW - timedelta(days=1),
        mode="always", timezone_name="UTC", now=NOW,
    )
    _stage(db, item)
    assert outbox.claim(item["id"], now=NOW + outbox.BRIEF_DELIVER_WITHIN, db=db) is None
    assert db.stores["notification_outbox"][item["id"]]["status"] == "failed"


def test_paused_watch_skips_a_queued_alert_before_the_attempt():
    db, watch_id, claimed = _db_with_claimed_watch()
    for item in _alert_item(watch_id, claimed):
        _stage(db, item)
    watch_service.unsubscribe(watch_service.make_unsubscribe_token(watch_id), db=db)
    send = AsyncMock(return_value=True)
    with (
        patch.object(notification_delivery.mailer, "is_configured", return_value=True),
        patch.object(notification_delivery.mailer, "send_message", send),
    ):
        counts = asyncio.run(notification_delivery.run_outbox_tick(db=db, now=NOW))
    assert counts == {"skipped": 1}
    send.assert_not_awaited()
    item = next(iter(db.stores["notification_outbox"].values()))
    assert item["last_error"] == "paused"


def test_unsubscribed_follower_receives_no_late_retry_and_others_still_do():
    db = FakeDb()
    db.stores["shares"][SHARE_ID] = share(slug="follow-me")
    db.stores["watches"]["w1"] = {
        "share_id": SHARE_ID, "status": "active", "created_at": NOW,
        "interval": "weekly", "owner_uid": "u1",
    }
    ids = []
    for email in ("a@example.com", "b@example.com"):
        pending = watch_followers.request_follow(SHARE_ID, email, db=db)
        watch_followers.confirm_follow(pending["token"], db=db)
        ids.append(watch_followers.follower_id(SHARE_ID, email))
    claimed = {
        "owner_uid": "u1", "share_id": SHARE_ID, "share_slug": "follow-me",
        "visibility": "public", "question": "Q", "current_run_id": "run1",
        "last_agreement_score": 60,
    }
    for item in outbox.watch_follower_items("w1", claimed, RESULT, ids, now=NOW):
        _stage(db, item)
    watch_followers.unsubscribe_follow(
        watch_followers.make_follow_unsubscribe_token(SHARE_ID, "a@example.com"), db=db,
    )
    recipients = []

    async def send(message):
        if message["To"] == "b@example.com" and not recipients:
            recipients.append("fail-once")
            return False
        recipients.append(message["To"])
        return True

    with (
        patch.object(notification_delivery.mailer, "is_configured", return_value=True),
        patch.object(notification_delivery.mailer, "send_message", side_effect=send),
        patch.object(notification_delivery.share_snapshots, "get_share",
                     side_effect=lambda sid, db=None: db.stores["shares"].get(sid)),
    ):
        first = asyncio.run(notification_delivery.run_outbox_tick(db=db, now=NOW))
        retry_at = NOW + outbox.retry_delay(1) + timedelta(seconds=1)
        second = asyncio.run(notification_delivery.run_outbox_tick(db=db, now=retry_at))
    assert first == {"skipped": 1, "retry": 1}
    assert second == {"sent": 1}
    assert recipients == ["fail-once", "b@example.com"]


def test_account_deletion_tombstone_skips_items_before_any_attempt():
    db = FakeDb()
    claimed = {"owner_uid": "u1", "share_id": SHARE_ID, "current_run_id": "run1"}
    item = _alert_item("w1", claimed)[0]
    _stage(db, item)
    db.stores[persistence_guard.ACCOUNT_DELETION_JOBS_COLLECTION]["u1"] = {"status": "pending"}
    assert outbox.claim(item["id"], now=NOW, db=db) is None
    assert db.stores["notification_outbox"][item["id"]]["status"] == "skipped"
    assert outbox.delete_for_uid("u1", db=db) == 1


def test_telegram_attempt_rechecks_mute_and_connection_and_disables_on_403():
    db, watch_id, claimed = _db_with_claimed_watch(telegram_enabled=True)
    db.stores["telegram_connections"]["u1"] = {"enabled": True, "chat_id": "123"}
    items = [
        item for item in _alert_item(watch_id, claimed, email=False)
    ]
    assert [item["data"]["channel"] for item in items] == ["telegram"]
    _stage(db, items[0])
    db.stores["watches"][watch_id]["telegram_muted_until"] = NOW + timedelta(hours=1)
    counts = asyncio.run(notification_delivery.run_outbox_tick(db=db, now=NOW))
    assert counts == {"skipped": 1}

    second_claim = dict(claimed, current_run_id="run-two")
    item = _alert_item(watch_id, second_claim, email=False)[0]
    _stage(db, item)
    db.stores["watches"][watch_id]["telegram_muted_until"] = None
    with patch.object(
        notification_delivery.telegram_watch.telegram_notifier, "send_bot_message",
        return_value={"status": "failed_http", "http_status": 403},
    ):
        counts = asyncio.run(notification_delivery.run_outbox_tick(db=db, now=NOW))
    assert counts == {"skipped": 1}
    assert db.stores["telegram_connections"]["u1"]["enabled"] is False


def test_brief_is_retried_after_a_crash_following_the_claim_and_honours_unsubscribe():
    db = FakeDb()
    db.stores["watch_briefs"]["u1"] = {
        "enabled": True, "send_time": "07:00", "timezone": "Europe/Berlin",
        "mode": "always", "next_send_at": NOW - timedelta(minutes=1),
        "enabled_at": NOW - timedelta(days=2),
    }
    claimed = watch_brief.claim_brief("u1", now=NOW, db=db)
    item_id = claimed["outbox_id"]
    # Crash: the schedule already moved on, but the digest is still queued.
    assert db.stores["watch_briefs"]["u1"]["next_send_at"] > NOW
    assert outbox.list_due_ids(now=NOW, db=db) == [item_id]
    user = SimpleNamespace(email="owner@example.test", email_verified=True)
    rows = [{"question": "Q", "share_path": "/s/q-a", "status": "active",
             "interval": "weekly", "run_time": "", "timezone": "", "score": 70,
             "previous_score": None, "new_points": [], "next_run_at": "", "last_run_at": ""}]
    with (
        patch.object(notification_delivery.mailer, "is_configured", return_value=True),
        patch.object(notification_delivery.auth, "get_user", return_value=user),
        patch.object(notification_delivery.watch_brief, "collect_brief_items",
                     return_value=(rows, 0)),
        patch.object(notification_delivery.mailer, "send_message",
                     new_callable=AsyncMock, return_value=True) as send,
    ):
        assert asyncio.run(notification_delivery.run_outbox_tick(db=db, now=NOW)) == {"sent": 1}
    send.assert_awaited_once()
    assert db.stores["watch_briefs"]["u1"]["last_sent_at"] == NOW

    # Next slot: queued, then unsubscribed before the attempt.
    db.stores["watch_briefs"]["u1"]["next_send_at"] = NOW
    later = NOW + timedelta(minutes=1)
    claimed = watch_brief.claim_brief("u1", now=later, db=db)
    watch_brief.unsubscribe_brief(watch_brief.make_brief_unsubscribe_token("u1"), db=db)
    with patch.object(notification_delivery.mailer, "is_configured", return_value=True):
        assert asyncio.run(
            notification_delivery.run_outbox_tick(db=db, now=later)
        ) == {"skipped": 1}


def test_topic_run_stages_follower_items_in_the_run_transaction():
    from test_topics_feature import FakeFirestore, run_payload, topic_payload

    db = FakeFirestore()
    topic = topics.create_topic(topic_payload(), actor_uid="admin", db=db, now=NOW)
    topics.create_run(topic["id"], run_payload(), actor_uid="admin", db=db, now=NOW)
    db.documents[(topics.FOLLOWERS_COLLECTION, "f1")] = {
        "topic_id": topic["id"], "email": "reader@example.com", "created_at": NOW,
    }
    from app.services import topic_runner

    with patch.object(topic_runner.mailer, "is_configured", return_value=True):
        staged = topic_runner.topic_notification_builder(topic["id"], db=db, now=NOW)
    payload = {**run_payload(), "change_type": "major", "change_summary": "Big shift.",
               "agreement_score": 20}
    run = topics.create_run(
        topic["id"], payload, actor_uid="admin", db=db, now=NOW, notifications=staged,
    )
    assert len(staged.ids) == 1
    stored = db.documents[(outbox.OUTBOX_COLLECTION, staged.ids[0])]
    assert stored["kind"] == "topic_follower"
    assert stored["run_id"] == run["id"]
    assert stored["recipient_id"] == "f1"


def test_outbox_retry_scan_survives_a_missing_composite_index():
    from datetime import datetime, timedelta, timezone
    from google.api_core.exceptions import FailedPrecondition
    from app.services import notification_outbox as outbox

    now = datetime(2026, 9, 29, 12, tzinfo=timezone.utc)
    rows = {
        "late": {"status": "pending", "next_attempt_at": now - timedelta(minutes=5)},
        "early": {"status": "pending", "next_attempt_at": now - timedelta(hours=1)},
        "future": {"status": "pending", "next_attempt_at": now + timedelta(hours=1)},
    }

    class Doc:
        def __init__(self, doc_id):
            self.id = doc_id
        def to_dict(self):
            return rows[self.id]

    class Ordered:
        def limit(self, _):
            return self
        def stream(self):
            raise FailedPrecondition("The query requires an index.")

    class Query:
        def where(self, filter=None):
            return self
        def order_by(self, _):
            return Ordered()
        def limit(self, _):
            return self
        def stream(self):
            return [Doc(doc_id) for doc_id in rows]

    class Db:
        def collection(self, _):
            return Query()

    assert outbox.list_due_ids(now=now, db=Db()) == ["early", "late"]
