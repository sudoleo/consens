"""What the watch endpoints deliver (Apple audit J5, J7, J17, J33).

`checking`/`due` instead of a next check in the past, the whole question,
one watch per question and owner with the existing watch named in the
error, page visibility changeable in the settings, and a scheduler that
wakes at the next due check. Firestore is the in-memory FakeDb.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from adapter_test_support import http_adapter, login  # noqa: F401 (fixture)
from test_watch_feature import FakeDb, share
from test_watch_http_contract import watch_http  # noqa: F401 (fixture)

from app.services import share_snapshots, watch_scheduler, watch_service


def test_watch_errors_carry_their_code_and_the_existing_watch(watch_http):
    h = watch_http
    h.watch_db.stores["shares"]["Q" * 16] = {**share(owner="owner", slug="again")}
    response = h.client.post("/api/watch", headers=login("owner"), json={
        "share_id": "Q" * 16, "interval": "weekly", "visibility": "public",
    })
    assert response.status_code == 409
    assert response.json() == {
        "error": "This question is already watched.", "code": "already_watched",
        "watch_id": h.watch["id"],
    }

def test_watch_says_when_it_is_checking_or_due():
    now = datetime(2026, 10, 20, 9, 5, tzinfo=timezone.utc)
    base = {"status": "active", "share_id": "A" * 16, "next_run_at": now + timedelta(hours=1)}
    assert watch_service._serialize_watch("w", base, now=now)["due"] is False
    due = watch_service._serialize_watch("w", {**base, "next_run_at": now - timedelta(minutes=5)}, now=now)
    assert due["due"] is True and due["checking"] is False
    running = watch_service._serialize_watch(
        "w", {**base, "next_run_at": now - timedelta(minutes=5), "claimed_until": now + timedelta(minutes=10)},
        now=now,
    )
    assert running["checking"] is True
    stale = watch_service._serialize_watch("w", {**base, "claimed_until": now - timedelta(minutes=1)}, now=now)
    assert stale["checking"] is False
    paused = watch_service._serialize_watch(
        "w", {**base, "status": "paused", "next_run_at": now - timedelta(days=1)}, now=now,
    )
    assert paused["due"] is False and paused["checking"] is False

def test_watch_delivers_the_whole_question():
    question = "Will " + "the very long and specific policy question " * 8 + "change?"
    item = watch_service._serialize_watch("w", {"share_id": "A" * 16}, {"question": question})
    assert len(question) > 200 and item["question"] == question

QUESTION = "Will the EU AI Act guidance change this year?"

class TestOneWatchPerQuestion:
    def setup_method(self):
        self.db = FakeDb()
        self.db.stores["shares"]["A" * 16] = share(question=QUESTION)

    def test_answer_and_question_watches_share_one_rule(self):
        first = watch_service.create_watch("u1", share_id="A" * 16, interval="weekly", tier="pro", db=self.db)
        with pytest.raises(watch_service.WatchError) as error:
            watch_service.create_watch("u1", question="will the EU AI act guidance change this year",
                                       interval="weekly", tier="pro", db=self.db)
        assert error.value.code == "already_watched" and error.value.details == {"watch_id": first["id"]}
        # Another answer to the same question is the same watch.
        self.db.stores["shares"]["B" * 16] = share(slug="again", question=QUESTION)
        with pytest.raises(watch_service.WatchError) as again:
            watch_service.create_watch("u1", share_id="B" * 16, interval="weekly", tier="pro", db=self.db)
        assert again.value.details["watch_id"] == first["id"]
        # Another owner may watch it; after deleting, the owner may again.
        self.db.stores["shares"]["C" * 16] = share(owner="u2", question=QUESTION)
        watch_service.create_watch("u2", share_id="C" * 16, interval="weekly", tier="pro", db=self.db)
        watch_service.delete_watch("u1", first["id"], db=self.db)
        watch_service.create_watch("u1", share_id="B" * 16, interval="weekly", tier="pro", db=self.db)

    def test_a_watch_from_before_the_rule_is_found_and_its_old_key_cleaned(self):
        first = watch_service.create_watch("u1", share_id="A" * 16, interval="weekly", tier="pro", db=self.db)
        uniques = self.db.stores["users/u1/watch_uniques"]
        # As an answer watch from before the rule was indexed: by its page.
        uniques.clear()
        watch_service._unique_ref(self.db, "u1", "share:" + "A" * 16).set(
            {"watch_id": first["id"], "share_id": "A" * 16, "uniqueness_key": "share:" + "A" * 16}
        )
        with pytest.raises(watch_service.WatchError) as error:
            watch_service.create_watch("u1", question=QUESTION, interval="weekly", tier="pro", db=self.db)
        assert error.value.details["watch_id"] == first["id"]
        watch_service.delete_watch("u1", first["id"], db=self.db)
        assert uniques == {}

    def test_a_watched_question_costs_no_new_page(self):
        first = watch_service.create_watch("u1", share_id="A" * 16, interval="weekly", tier="pro", db=self.db)
        pending = {"question": QUESTION, "owner_uid": "u1"}
        with patch.object(share_snapshots, "get_pending_result", return_value=pending), \
                patch.object(share_snapshots, "create_share_from_pending") as create_share:
            with pytest.raises(watch_service.WatchError) as error:
                watch_service.create_watch("u1", result_id="R" * 16, interval="weekly", tier="pro", db=self.db)
        assert error.value.details["watch_id"] == first["id"]
        create_share.assert_not_called()

def test_watch_page_visibility_changes_in_settings(watch_http):
    h = watch_http
    stored_share = h.watch_db.stores["shares"][h.share_id]
    stored_share.update(visibility="public", indexed=True, index_requested=True)
    response = h.client.patch(h.url, headers=login("owner"), json={"visibility": "private"})
    assert response.status_code == 200, response.text
    assert response.json()["watch"]["visibility"] == "private"
    assert response.json()["watch"]["share_path"] == "/s/" + h.share_id
    assert stored_share["visibility"] == "private"
    assert stored_share["indexed"] is False and stored_share["index_requested"] is False
    assert h.watch_db.stores[watch_service.WATCHES_COLLECTION][h.watch["id"]]["visibility"] == "private"
    bad = h.client.patch(h.url, headers=login("owner"), json={"visibility": "secret"})
    assert bad.status_code == 400 and stored_share["visibility"] == "private"
    assert h.client.patch(h.url, headers=login("stranger"), json={"visibility": "public"}).status_code == 403
    back = h.client.patch(h.url, headers=login("owner"), json={"visibility": "public"})
    assert back.status_code == 200 and stored_share["visibility"] == "public"
    assert stored_share["indexed"] is False  # Google's index stays an admin decision

def test_scheduler_wakes_at_the_next_due_check():
    now = datetime(2026, 10, 20, 8, 50, tzinfo=timezone.utc)
    with patch.object(watch_service, "earliest_next_run_at", return_value=now + timedelta(minutes=10)):
        assert watch_scheduler.next_tick_seconds(now=now) == 605
    with patch.object(watch_service, "earliest_next_run_at", return_value=now + timedelta(seconds=2)):
        assert watch_scheduler.next_tick_seconds(now=now) == watch_scheduler.MIN_TICK_SECONDS
    for due in (None, now - timedelta(minutes=1), now + timedelta(hours=5)):
        with patch.object(watch_service, "earliest_next_run_at", return_value=due):
            assert watch_scheduler.next_tick_seconds(now=now) == watch_scheduler.TICK_SECONDS
    with patch.object(watch_service, "earliest_next_run_at", side_effect=RuntimeError("down")):
        assert watch_scheduler.next_tick_seconds(now=now) == watch_scheduler.TICK_SECONDS


def test_a_watch_that_fell_due_during_a_long_tick_runs_on_the_next_short_one():
    # Zweitprüfung 10: the tick scanned at 08:00 and ran for 20 minutes; a
    # check due at 08:10 was never seen and must not wait until 08:50.
    scanned_at = datetime(2026, 10, 20, 8, 0, tzinfo=timezone.utc)
    now = scanned_at + timedelta(minutes=20)
    with patch.object(watch_service, "earliest_next_run_at", return_value=scanned_at + timedelta(minutes=10)):
        assert watch_scheduler.next_tick_seconds(now=now, scanned_at=scanned_at) == watch_scheduler.MIN_TICK_SECONDS
    # Already due at the scan and still due (lease elsewhere, budget spent):
    # the normal rhythm, no busy loop.
    with patch.object(watch_service, "earliest_next_run_at", return_value=scanned_at - timedelta(minutes=1)):
        assert watch_scheduler.next_tick_seconds(now=now, scanned_at=scanned_at) == watch_scheduler.TICK_SECONDS
    with patch.object(watch_service, "earliest_next_run_at", return_value=scanned_at):
        assert watch_scheduler.next_tick_seconds(now=now, scanned_at=scanned_at) == watch_scheduler.TICK_SECONDS


def test_the_next_due_read_does_not_wait_out_firestore_retries():
    seen = {}

    class Query:
        def where(self, *args, **kwargs):
            return self

        def order_by(self, *args, **kwargs):
            return self

        def limit(self, *args, **kwargs):
            return self

        def stream(self, **kwargs):
            seen.update(kwargs)
            return iter(())

    db = SimpleNamespace(collection=lambda _name: Query())
    assert watch_service.earliest_next_run_at(db=db) is None
    assert seen == {"retry": None, "timeout": 3.0}
