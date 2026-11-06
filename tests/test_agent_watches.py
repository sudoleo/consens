"""Watches that run the Agent (agent_watches.py, since 2026-11-03): the
schedule, starting one from the card, the runs the scheduler takes, how a
run ends (the mail of a finding, the end at the goal), the routes, the
mail, and a run through the Agent route itself."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from starlette.responses import JSONResponse, StreamingResponse

from app.core import config as cfg
from app.services import agent_watch, agent_watches, mailer, notification_outbox as outbox
from test_agent_runs import AUTH, UID, api, pending, store  # noqa: F401  (fixtures)
from test_agent_watch import PROPOSAL, TASK


pytestmark = pytest.mark.usefixtures("deepseek_default_agent")

NOW = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)
BOOKMARK = "agent_watch_chat"


def proposed_chat(store, *, proposal=PROPOSAL, bookmark=True, **chat):
    """A chat with a completed answer that prepared ``proposal`` and its sidebar entry."""
    chat_id, turn = pending(store)
    turns = store.db.turns(UID, chat_id)
    turns[turn["id"]].update({"status": "completed", "agent_watch": dict(proposal)})
    # The answer is done: the chat takes the next message (a run's turn).
    store._chat_ref(UID, chat_id).update({"agent_lock_until": None})
    if chat:
        store._chat_ref(UID, chat_id).update(chat)
    if bookmark:
        store.db.collection("users").document(UID).collection("bookmarks").document(BOOKMARK).set({"chat_id": chat_id})
    return chat_id, turn["id"]


def start(store, chat_id, turn_id, *, tier="free", **kwargs):
    return agent_watches.create(UID, chat_id=chat_id, turn_id=turn_id, tier=tier, timezone_name="Europe/Berlin",
                                db=store.db, now=NOW, **kwargs)


def record(store, watch_id):
    return store.db.collection(agent_watches.COLLECTION).document(watch_id).get().to_dict()


def outbox_items(store):
    return [data for path, data in store.db.documents.items() if path[0] == outbox.OUTBOX_COLLECTION]


# --- schedule ----------------------------------------------------------------

def test_each_tier_has_its_shortest_interval_and_its_slots():
    assert agent_watches.allowed_intervals("free") == ["daily", "weekly"]
    assert agent_watches.allowed_intervals("plus") == ["every_6_hours", "daily", "weekly"]
    assert agent_watches.allowed_intervals("pro") == ["hourly", "every_6_hours", "daily", "weekly"]
    assert [agent_watches.active_limit(tier) for tier in ("free", "plus", "pro")] == [2, 5, 20]
    assert agent_watches.fit_interval("hourly", "free") == "daily"


def test_daily_runs_at_its_local_time_and_the_short_ones_by_the_hour():
    schedule = agent_watches.validate_schedule("daily", "", "", "Europe/Berlin")
    assert schedule == {"interval": "daily", "run_time": "08:00", "run_weekday": "", "timezone": "Europe/Berlin"}
    # 12:00 UTC is 13:00 in Berlin: the next 08:00 there is tomorrow, 07:00 UTC.
    assert agent_watches.next_run(schedule, now=NOW) == datetime(2026, 11, 4, 7, 0, tzinfo=timezone.utc)
    hourly = agent_watches.validate_schedule("hourly", "09:30", "monday", "")
    assert hourly == {"interval": "hourly", "run_time": "", "run_weekday": "", "timezone": "UTC"}
    assert agent_watches.next_run(hourly, now=NOW) == NOW + timedelta(hours=1)
    # From a run that was due long ago: the next slot after now, not a backlog.
    assert agent_watches.next_run(hourly, now=NOW, previous=NOW - timedelta(hours=5, minutes=30)) == NOW + timedelta(minutes=30)
    # A new Watch comes at the next such time, today while it is still ahead,
    # not one interval after now (review 2026-11-03).
    morning = datetime(2026, 11, 3, 6, 0, tzinfo=timezone.utc)
    assert agent_watches.next_run(schedule, now=morning) == datetime(2026, 11, 3, 7, 0, tzinfo=timezone.utc)
    weekly = agent_watches.validate_schedule("weekly", "08:00", "", "Europe/Berlin")
    assert agent_watches.next_run(weekly, now=morning) == datetime(2026, 11, 3, 7, 0, tzinfo=timezone.utc)
    assert agent_watches.next_run(weekly, now=NOW) == datetime(2026, 11, 4, 7, 0, tzinfo=timezone.utc)
    # After a run, the interval as before.
    assert agent_watches.next_run(weekly, now=datetime(2026, 11, 3, 7, 1, tzinfo=timezone.utc),
                                  previous=datetime(2026, 11, 3, 7, 0, tzinfo=timezone.utc)) == datetime(2026, 11, 10, 7, 0, tzinfo=timezone.utc)
    with pytest.raises(agent_watches.AgentWatchError) as error:
        agent_watches.validate_schedule("monthly")
    assert error.value.code == "invalid_interval"
    with pytest.raises(agent_watches.AgentWatchError) as error:
        agent_watches.validate_schedule("daily", "8 am", "", "Europe/Berlin")
    assert error.value.code == "invalid_run_time"


# --- starting a Watch ----------------------------------------------------------

def test_the_card_starts_the_task_the_agent_prepared_in_its_chat(store):
    chat_id, turn_id = proposed_chat(store)
    watch = start(store, chat_id, turn_id, run_time="07:15")
    assert watch["task"] == TASK and watch["goal"] == "Registration is open"
    assert (watch["interval"], watch["run_time"], watch["timezone"]) == ("daily", "07:15", "Europe/Berlin")
    assert watch["status"] == "active" and watch["turn_id"] == turn_id and watch["chat_id"] == chat_id
    saved = record(store, watch["id"])
    assert saved["bookmark_id"] == BOOKMARK and saved["next_run_at"] == datetime(2026, 11, 4, 6, 15, tzinfo=timezone.utc)
    assert agent_watches.outlook(UID, chat_id, "free", db=store.db)["already_watched"] is True
    assert [item["id"] for item in agent_watches.list_for(UID, chat_id=chat_id, db=store.db)] == [watch["id"]]


@pytest.mark.parametrize("change,code,status", [
    ({"temporary": True}, "temporary_chat", 422),
    ({"google_data": True}, "google_data", 422),
    ({"status": "deleting"}, "chat_not_found", 404),
])
def test_a_chat_that_cannot_hold_a_watch_says_why(store, change, code, status):
    chat_id, turn_id = proposed_chat(store, **change)
    with pytest.raises(agent_watches.AgentWatchError) as error:
        start(store, chat_id, turn_id)
    assert (error.value.code, error.value.status) == (code, status)


def test_one_watch_per_chat_slots_per_tier_and_intervals_per_tier(store):
    chat_id, turn_id = proposed_chat(store)
    with pytest.raises(agent_watches.AgentWatchError) as error:
        start(store, chat_id, turn_id, interval="hourly")
    assert (error.value.code, error.value.status) == ("interval_not_allowed", 403)
    start(store, chat_id, turn_id)
    with pytest.raises(agent_watches.AgentWatchError) as error:
        start(store, chat_id, turn_id)
    assert error.value.code == "already_watched"
    second = proposed_chat(store)
    start(store, *second)
    third = proposed_chat(store)
    with pytest.raises(agent_watches.AgentWatchError) as error:
        start(store, *third)
    assert (error.value.code, error.value.status) == ("limit_reached", 429)
    # Pro has room, and hourly runs.
    assert start(store, *third, tier="pro", interval="hourly")["interval"] == "hourly"


def test_no_proposal_no_watch_and_the_task_never_comes_from_the_request(store):
    chat_id, turn_id = proposed_chat(store, proposal={"question": "An old Consensus Watch proposal?"})
    with pytest.raises(agent_watches.AgentWatchError) as error:
        start(store, chat_id, turn_id)
    assert error.value.code == "no_proposal"
    chat_id, turn_id = proposed_chat(store, bookmark=False)
    with pytest.raises(agent_watches.AgentWatchError) as error:
        start(store, chat_id, turn_id)
    assert error.value.code == "chat_not_found"


def test_ending_frees_the_slot_and_a_chats_deletion_takes_its_watch(store):
    chat_id, turn_id = proposed_chat(store)
    watch = start(store, chat_id, turn_id)
    ended = agent_watches.stop(UID, watch["id"], db=store.db, now=NOW)
    assert ended["status"] == "done" and ended["ended"] == "user" and ended["next_run_at"] is None
    assert agent_watches.outlook(UID, chat_id, "free", db=store.db)["active_count"] == 0
    with pytest.raises(agent_watches.AgentWatchError):
        agent_watches.stop("someone-else", watch["id"], db=store.db)
    other = start(store, *proposed_chat(store))
    assert agent_watches.delete_for_chat(store.db, UID, other["chat_id"]) == 1
    assert record(store, other["id"]) is None
    assert agent_watches.outlook(UID, other["chat_id"], "free", db=store.db)["active_count"] == 0
    assert agent_watches.delete_for_account(store.db, UID) == 1
    assert agent_watches.list_for(UID, db=store.db) == []


def test_day_counts_keep_no_deleted_account_and_no_old_day(store, monkeypatch):
    """agent_watch_days/{date} holds each account's UID for the day's caps; a
    deleted account's UID went nowhere and old days stayed for good (bug hunt
    2026-11-04)."""
    days = store.db.collection(agent_watches.DAYS_COLLECTION)
    for back in (0, 1, 2, 9):
        day = (NOW - timedelta(days=back)).date().isoformat()
        days.document(day).set({"runs": 3, "accounts": {UID: 2, "other-user": 1}, "updated_at": NOW})
    assert agent_watches.purge_days(db=store.db, now=NOW) == 2
    kept = sorted(snapshot.id for snapshot in days.stream())
    assert kept == [(NOW - timedelta(days=1)).date().isoformat(), NOW.date().isoformat()]
    agent_watches.delete_for_account(store.db, UID)
    assert [snapshot.to_dict()["accounts"] for snapshot in days.stream()] == [{"other-user": 1}] * 2
    # The scheduler purges once a day.
    monkeypatch.setattr("app.services.llm.mock_llm.mock_llm_enabled", lambda: False)
    monkeypatch.setattr(agent_watches, "_days_purged", None)
    purged = []
    monkeypatch.setattr(agent_watches, "purge_days", lambda **kwargs: purged.append(kwargs["now"]))
    for at in (NOW, NOW + timedelta(hours=1), NOW + timedelta(days=1)):
        asyncio.run(agent_watches.run_tick(now=at, db=store.db))
    assert purged == [NOW, NOW + timedelta(days=1)]


# --- the scheduler's runs -------------------------------------------------------

def due_watch(store, **fields):
    chat_id, turn_id = proposed_chat(store)
    watch = start(store, chat_id, turn_id)
    store.db.collection(agent_watches.COLLECTION).document(watch["id"]).update(fields)
    return watch["id"]


def test_a_due_run_moves_the_watch_on_and_is_taken_once(store):
    scheduled = NOW - timedelta(minutes=3)
    watch_id = due_watch(store, next_run_at=scheduled)
    assert agent_watches.due(now=NOW, db=store.db) == [(watch_id, UID)]
    assert agent_watches.earliest_next_run_at(db=store.db) == scheduled
    run, reason = agent_watches.claim(watch_id, now=NOW, db=store.db)
    assert reason == "" and run["scheduled_at"] == scheduled and run["request_id"].startswith("watch.")
    saved = record(store, watch_id)
    assert saved["next_run_at"] > NOW and saved["running"]["request_id"] == run["request_id"] and saved["runs"] == 1
    assert agent_watches.claim(watch_id, now=NOW, db=store.db) == (None, "not_due")


def test_watches_due_at_the_same_time_take_turns(store):
    # Many Watches at the default 08:00: the one that has waited longest goes
    # first, so a full morning skips another one each day, not always the same
    # (bug hunt 2026-11-04: the tie went by document id).
    scheduled = NOW - timedelta(minutes=5)

    def due_pro(when):
        watch = start(store, *proposed_chat(store), tier="pro")
        store.db.collection(agent_watches.COLLECTION).document(watch["id"]).update({"next_run_at": when})
        return watch["id"]

    ids = [due_pro(scheduled) for _ in range(3)]
    by_name = [watch_id for watch_id, _uid in agent_watches.due(now=NOW, db=store.db)]
    assert sorted(by_name) == sorted(ids)
    for days, watch_id in enumerate(by_name):
        # The last by name ran longest ago; the first never did.
        last = None if days == 0 else {"at": NOW - timedelta(days=days), "outcome": "quiet", "summary": ""}
        store.db.collection(agent_watches.COLLECTION).document(watch_id).update({"last_run": last})
    first, *rest = by_name
    assert [watch_id for watch_id, _uid in agent_watches.due(now=NOW, db=store.db)] == [first, *reversed(rest)]
    # An earlier time still goes first.
    earlier = due_pro(scheduled - timedelta(minutes=1))
    assert agent_watches.due(now=NOW, db=store.db)[0] == (earlier, UID)


def test_a_late_run_is_skipped_and_a_running_one_waits(store):
    watch_id = due_watch(store, next_run_at=NOW - timedelta(hours=3))
    assert agent_watches.claim(watch_id, now=NOW, db=store.db) == (None, "late")
    assert record(store, watch_id)["next_run_at"] > NOW and record(store, watch_id)["runs"] == 0
    busy = due_watch(store, next_run_at=NOW, running={"request_id": "r", "started_at": NOW - timedelta(minutes=5)})
    assert agent_watches.claim(busy, now=NOW, db=store.db) == (None, "running")


def test_the_server_cap_holds_runs_back(store, monkeypatch):
    monkeypatch.setitem(cfg.LIMITS, "agent_watch_max_runs_per_day", 1)
    first = due_watch(store, next_run_at=NOW)
    second = due_watch(store, next_run_at=NOW)
    assert agent_watches.claim(first, now=NOW, db=store.db)[1] == ""
    assert agent_watches.claim(second, now=NOW, db=store.db) == (None, "budget")


def test_one_accounts_watches_never_use_up_everyone_elses_runs(store, monkeypatch):
    monkeypatch.setitem(cfg.LIMITS, "agent_watch_max_runs_per_account_day", 1)
    first = due_watch(store, next_run_at=NOW)
    second = due_watch(store, next_run_at=NOW)
    assert agent_watches.claim(first, now=NOW, db=store.db)[1] == ""
    assert agent_watches.claim(second, now=NOW, db=store.db) == (None, "account_budget")
    store.db.collection(agent_watches.COLLECTION).document(second).update({"uid": "someone-else"})
    assert agent_watches.claim(second, now=NOW, db=store.db)[1] == ""


def test_a_plan_that_no_longer_allows_the_interval_runs_it_at_one_it_does(store):
    watch_id = due_watch(store, next_run_at=NOW, interval="hourly", run_time="", run_weekday="")
    run, reason = agent_watches.claim(watch_id, now=NOW, db=store.db, tier="free")
    saved = record(store, watch_id)
    assert reason == "" and run["interval"] == "daily" and saved["interval"] == "daily"
    assert saved["run_time"] == "08:00" and saved["next_run_at"] == datetime(2026, 11, 4, 7, 0, tzinfo=timezone.utc)


class Router:
    """agent.start_agent_turn as the scheduler calls it."""

    def __init__(self, result):
        self.result, self.calls = result, []

    def __call__(self, uid, payload, *, watch_run):
        self.calls.append((uid, payload, watch_run))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.fixture
def router(monkeypatch):
    from app.api.routers import agent as agent_router
    def install(result):
        fake = Router(result)
        monkeypatch.setattr(agent_router, "start_agent_turn", fake)
        return fake
    # The plan comes from the account (security.get_user_tier, real Firestore).
    monkeypatch.setattr(agent_watches, "_tier_of", lambda uid: None)
    agent_watches._running.clear()
    yield install
    agent_watches._running.clear()


def test_a_started_run_is_the_task_in_its_chat(store, router):
    watch_id = due_watch(store, next_run_at=NOW)
    run, _ = agent_watches.claim(watch_id, now=NOW, db=store.db)
    fake = router(StreamingResponse(iter(())))
    assert agent_watches.start_run(run, db=store.db, now=NOW) is True
    uid, payload, watch_run = fake.calls[0]
    assert uid == UID and payload.question == TASK and payload.bookmark_id == BOOKMARK
    assert payload.client_request_id == run["request_id"] and payload.timezone == "Europe/Berlin"
    assert watch_run == {"watch_id": watch_id, "scheduled_at": NOW.isoformat(), "request_id": run["request_id"],
                         "goal": "Registration is open"}
    assert agent_watches._busy_accounts() == {UID}
    assert "Registration is open" in agent_watches.run_context(watch_run)


def test_a_busy_chat_tries_again_soon_and_a_deleted_one_ends_the_watch(store, router):
    watch_id = due_watch(store, next_run_at=NOW)
    run, _ = agent_watches.claim(watch_id, now=NOW, db=store.db)
    router(HTTPException(status_code=409, detail="Turn state conflict"))
    assert agent_watches.start_run(run, db=store.db, now=NOW) is False
    saved = record(store, watch_id)
    assert saved["next_run_at"] == NOW + agent_watches.BUSY_RETRY and saved["running"] is None
    assert not agent_watches._busy_accounts()
    run, _ = agent_watches.claim(watch_id, now=NOW + agent_watches.BUSY_RETRY, db=store.db)
    router(HTTPException(status_code=404, detail="Chat not found"))
    agent_watches.start_run(run, db=store.db, now=NOW)
    saved = record(store, watch_id)
    assert saved["status"] == "done" and saved["ended"] == "chat_gone" and saved["last_run"]["outcome"] == "chat_gone"
    # A saved answer for the same request: nothing ran again.
    other = due_watch(store, next_run_at=NOW)
    run, _ = agent_watches.claim(other, now=NOW, db=store.db)
    router({"turn": {}})
    assert agent_watches.start_run(run, db=store.db, now=NOW) is False
    assert record(store, other)["last_run"]["outcome"] == "already_ran"
    router(JSONResponse({"code": "cancelled"}, status_code=409))
    run, _ = agent_watches.claim(other, now=record(store, other)["next_run_at"], db=store.db)
    assert agent_watches.start_run(run, db=store.db, now=NOW) is False


def test_a_busy_run_keeps_its_time_its_count_and_its_end(store, router):
    """Review 2026-11-03: each retry counted as a run and as its own late
    start, so retries never ended, and an hourly Watch moved 10 min a time."""
    watch_id = due_watch(store, next_run_at=NOW, interval="hourly", run_time="", run_weekday="")
    router(HTTPException(status_code=409, detail="Turn state conflict"))
    at = NOW
    for _ in range(10):
        run, reason = agent_watches.claim(watch_id, now=at, db=store.db)
        assert reason == "" and run["scheduled_at"] == NOW
        agent_watches.start_run({**run, "claimed_at": at}, db=store.db, now=at)
        saved = record(store, watch_id)
        if saved["next_run_at"] == NOW + timedelta(hours=1):
            break
        assert saved["retry_of"] == NOW and saved["next_run_at"] == at + agent_watches.BUSY_RETRY
        at = saved["next_run_at"]
    # The next hourly run comes first: no further retry, the schedule unmoved.
    saved = record(store, watch_id)
    assert saved["next_run_at"] == NOW + timedelta(hours=1) and saved.get("retry_of") is None
    assert saved["runs"] == 0
    day = store.db.collection(agent_watches.DAYS_COLLECTION).document(NOW.date().isoformat()).get().to_dict()
    assert day["runs"] == 0 and day["accounts"][UID] == 0
    # A retry past the lateness of its first time is skipped like that time.
    store.db.collection(agent_watches.COLLECTION).document(watch_id).update(
        {"next_run_at": NOW + timedelta(minutes=50), "retry_of": NOW - timedelta(hours=2)})
    assert agent_watches.claim(watch_id, now=NOW + timedelta(minutes=50), db=store.db) == (None, "late")
    assert record(store, watch_id)["next_run_at"] == NOW + timedelta(hours=1)


def test_pausing_during_a_busy_retry_never_skips_the_run_after_the_resume(store, router):
    """A retry measures its lateness from its first time (retry_of): paused
    in between and resumed later, the Watch's next run is a new one, and it
    ran instead of being skipped as two hours late."""
    watch_id = due_watch(store, next_run_at=NOW)
    router(HTTPException(status_code=409, detail="Turn state conflict"))
    run, _ = agent_watches.claim(watch_id, now=NOW, db=store.db)
    agent_watches.start_run({**run, "claimed_at": NOW}, db=store.db, now=NOW)
    assert record(store, watch_id)["retry_of"] == NOW
    agent_watches.pause(UID, watch_id, db=store.db, now=NOW + timedelta(minutes=5))
    resumed = agent_watches.resume(UID, watch_id, tier="pro", db=store.db, now=NOW + timedelta(hours=1))
    following = datetime.fromisoformat(resumed["next_run_at"])
    run, reason = agent_watches.claim(watch_id, now=following, db=store.db)
    assert reason == "" and run["scheduled_at"] == following


def test_a_chat_that_took_in_google_information_ends_its_watch_and_says_so(store, router):
    watch_id = due_watch(store, next_run_at=NOW)
    run, _ = agent_watches.claim(watch_id, now=NOW, db=store.db)
    store._chat_ref(UID, run["chat_id"]).update({"google_data": True})
    router(HTTPException(status_code=422, detail="This chat contains Google information."))
    assert agent_watches.start_run(run, db=store.db, now=NOW) is False
    saved = record(store, watch_id)
    assert saved["status"] == "done" and saved["ended"] == "google_data" and saved["unread"] is True
    slots = store.db.collection("users").document(UID).collection("agent_watch_state").document("slots").get()
    assert watch_id not in (slots.to_dict() or {}).get("active", {})
    # Another refusal that would only repeat ends it too.
    other = due_watch(store, next_run_at=NOW)
    run, _ = agent_watches.claim(other, now=NOW, db=store.db)
    router(HTTPException(status_code=403, detail="Not available"))
    agent_watches.start_run(run, db=store.db, now=NOW)
    assert record(store, other)["ended"] == "cannot_run"


def test_a_failing_start_never_takes_the_tick_down(store, router, monkeypatch):
    monkeypatch.setattr("app.services.llm.mock_llm.mock_llm_enabled", lambda: False)
    due_watch(store, next_run_at=NOW - timedelta(minutes=1))
    router(HTTPException(status_code=409, detail="busy"))
    monkeypatch.setattr(agent_watches, "_retry_soon", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("down")))
    assert asyncio.run(agent_watches.run_tick(now=NOW, db=store.db)) == 0
    assert not agent_watches._busy_accounts()


def test_the_tick_starts_due_runs_one_per_account(store, router, monkeypatch):
    monkeypatch.setattr("app.services.llm.mock_llm.mock_llm_enabled", lambda: False)
    first = due_watch(store, next_run_at=NOW - timedelta(minutes=1))
    due_watch(store, next_run_at=NOW - timedelta(minutes=1))
    fake = router(StreamingResponse(iter(())))
    assert asyncio.run(agent_watches.run_tick(now=NOW, db=store.db)) == 1
    assert [call[2]["watch_id"] for call in fake.calls] == [first]


# --- a run's end ------------------------------------------------------------------

def ended_run(store, run_state, **turn):
    watch_id = due_watch(store, next_run_at=NOW)
    run, _ = agent_watches.claim(watch_id, now=NOW, db=store.db)
    chat_id = record(store, watch_id)["chat_id"]
    chat, turn_doc = pending(store, chat_id=chat_id, request_id=run["request_id"], question=TASK)
    store.db.turns(UID, chat_id)[turn_doc["id"]].update({"status": "completed", **turn,
                                                         **({"agent_watch_run": run_state} if run_state else {})})
    watch_run = {"watch_id": watch_id, "request_id": run["request_id"], "scheduled_at": NOW.isoformat(), "goal": ""}
    agent_watches._running[watch_id] = UID
    outcome = agent_watches.turn_ended(UID, chat_id, turn_doc["id"], watch_run, db=store.db, now=NOW)
    return outcome, watch_id, turn_doc["id"]


def test_a_quiet_run_is_noted_and_mails_nothing(store, monkeypatch):
    monkeypatch.setattr("app.services.watch_scheduler.wake_watch_scheduler", lambda: None)
    outcome, watch_id, turn_id = ended_run(store, None)
    assert outcome == "quiet" and outbox_items(store) == []
    saved = record(store, watch_id)
    assert saved["running"] is None and saved["last_run"]["outcome"] == "quiet" and saved["last_run"]["turn_id"] == turn_id
    assert saved["status"] == "active" and watch_id not in agent_watches._running


def test_a_watch_paused_or_ended_while_its_run_went_on_sends_nothing(store, monkeypatch):
    monkeypatch.setattr("app.services.watch_scheduler.wake_watch_scheduler", lambda: None)
    finding = {"summary": "Registration is open.", "evidence_url": "https://www.ironman.com/im-hamburg",
               "needs_user": False}
    original = agent_watches.turn_ended

    def pause_first(uid, chat_id, turn_id, watch_run, **kwargs):
        agent_watches.pause(uid, watch_run["watch_id"], db=store.db, now=NOW)
        return original(uid, chat_id, turn_id, watch_run, **kwargs)

    monkeypatch.setattr(agent_watches, "turn_ended", pause_first)
    outcome, watch_id, _turn = ended_run(store, {"finding": finding})
    assert outcome == "finding" and outbox_items(store) == []
    # The finding still waits in the chat and on the page.
    assert record(store, watch_id)["unread"] is True and record(store, watch_id)["status"] == "paused"


def test_a_finding_is_mailed_with_its_page_and_the_reviewers_counts(store, monkeypatch):
    woken = []
    monkeypatch.setattr("app.services.watch_scheduler.wake_watch_scheduler", lambda: woken.append(1))
    finding = {"summary": "Registration is open.", "evidence_url": "https://www.ironman.com/im-hamburg",
               "evidence_title": "IRONMAN Hamburg", "needs_user": False}
    review = {"audit": {"reviewers": [{"provider": "a"}, {"provider": "b"}], "issues": []}}
    outcome, watch_id, turn_id = ended_run(store, {"finding": finding}, agent_review=review)
    assert outcome == "finding" and woken
    # Mail and Telegram; Telegram goes only where the account linked it (notification_delivery).
    items = outbox_items(store)
    assert sorted(item["channel"] for item in items) == ["email", "telegram"]
    item = next(item for item in items if item["channel"] == "email")
    assert item["kind"] == outbox.KIND_AGENT_WATCH and item["resource_id"] == watch_id and item["run_id"] == turn_id
    payload = item["payload"]
    assert payload["bookmark_id"] == BOOKMARK
    saved = record(store, watch_id)
    assert saved["unread"] is True and saved["last_run"]["evidence_url"].endswith("/im-hamburg")
    assert payload["summary"] == "Registration is open." and payload["evidence_url"].endswith("/im-hamburg")
    assert payload["task"] == TASK and payload["review"] == {"reviewers": 2, "issues": 0} and payload["goal_met"] is False
    assert record(store, watch_id)["last_run"]["summary"] == "Registration is open."


def test_the_goal_ends_the_watch_and_a_halt_nobody_decided_needs_the_user(store, monkeypatch):
    monkeypatch.setattr("app.services.watch_scheduler.wake_watch_scheduler", lambda: None)
    outcome, watch_id, _ = ended_run(store, {"done": {"reason": "Registration opened."}})
    assert outcome == "done"
    saved = record(store, watch_id)
    assert saved["status"] == "done" and saved["ended"] == "goal" and saved["next_run_at"] is None
    assert outbox_items(store)[0]["payload"]["goal_met"] is True
    outcome, _, _ = ended_run(store, None, status="failed", agent_failure={"code": "hold_timeout"})
    assert outcome == "needs_you"
    assert outbox_items(store)[-1]["payload"]["halted"] is True
    assert ended_run(store, None, status="failed", agent_failure={"code": "provider_error"})[0] == "failed"


def test_each_run_is_kept_as_a_look_for_the_pulse_with_what_it_found(store, monkeypatch):
    """The page's pulse and detail (watch-dashboard.js): every run in order,
    a finding with its line, at most LOOKS_KEPT of them."""
    monkeypatch.setattr("app.services.watch_scheduler.wake_watch_scheduler", lambda: None)
    _, watch_id, _ = ended_run(store, None)
    assert [look["outcome"] for look in record(store, watch_id)["looks"]] == ["quiet"]
    assert "summary" not in record(store, watch_id)["looks"][0]
    long_finding = "Registration is open. " * 30
    _, found_id, _ = ended_run(store, {"finding": {"summary": long_finding, "evidence_url": "https://www.ironman.com/x"}})
    look = record(store, found_id)["looks"][-1]
    assert look["outcome"] == "finding" and look["at"] == NOW
    assert len(look["summary"]) == agent_watches.LOOK_SUMMARY_CHARS and look["summary"].endswith("…")
    view = agent_watches.serialize(found_id, record(store, found_id))["looks"]
    assert view == [{"at": NOW.isoformat(), "outcome": "finding", "summary": look["summary"]}]
    # A run that did not start is a look too, one that already ran is none.
    agent_watches._not_started(found_id, "not_started", db=store.db, now=NOW)
    agent_watches._not_started(found_id, "already_ran", db=store.db, now=NOW)
    assert [item["outcome"] for item in record(store, found_id)["looks"]] == ["finding", "not_started"]
    # The newest LOOKS_KEPT stay.
    store.db.collection(agent_watches.COLLECTION).document(found_id).update(
        {"looks": [agent_watches._look("quiet", NOW - timedelta(days=day)) for day in range(40, 0, -1)]})
    agent_watches._not_started(found_id, "not_started", db=store.db, now=NOW)
    kept = record(store, found_id)["looks"]
    assert len(kept) == agent_watches.LOOKS_KEPT and kept[-1]["outcome"] == "not_started"
    assert kept[0]["at"] == NOW - timedelta(days=29)


def test_a_watch_from_before_the_looks_keeps_its_last_run_as_its_first_look(store):
    watch = start(store, *proposed_chat(store))
    ref = store.db.collection(agent_watches.COLLECTION).document(watch["id"])
    earlier = NOW - timedelta(days=1)
    data = record(store, watch["id"])
    data.pop("looks", None)
    ref.set({**data, "last_run": {"at": earlier, "outcome": "finding", "summary": "Open."}})
    agent_watches._not_started(watch["id"], "not_started", db=store.db, now=NOW)
    assert [(look["outcome"], look["at"]) for look in record(store, watch["id"])["looks"]] == [
        ("finding", earlier), ("not_started", NOW)]


def test_a_legacy_run_that_had_run_already_is_no_look(store):
    """A run that had run already is no look of its own, and a Watch from
    before the looks whose last run was one has none from it (review 2026-11-04)."""
    watch = start(store, *proposed_chat(store))
    ref = store.db.collection(agent_watches.COLLECTION).document(watch["id"])
    data = record(store, watch["id"])
    data.pop("looks", None)
    data = {**data, "runs": 7, "last_run": {"at": NOW - timedelta(days=1), "outcome": "already_ran", "summary": ""}}
    assert agent_watches.serialize(watch["id"], data)["looks"] == []
    ref.set(data)
    agent_watches._not_started(watch["id"], "not_started", db=store.db, now=NOW)
    assert [(look["outcome"], look["at"]) for look in record(store, watch["id"])["looks"]] == [("not_started", NOW)]


def test_a_watch_from_before_the_looks_shows_its_last_run_and_one_running_says_so(store):
    watch = start(store, *proposed_chat(store))
    data = record(store, watch["id"])
    assert agent_watches.serialize(watch["id"], data)["looks"] == []
    data = {**data, "last_run": {"at": NOW, "outcome": "finding", "summary": "Open."}}
    assert agent_watches.serialize(watch["id"], data)["looks"] == [
        {"at": NOW.isoformat(), "outcome": "finding", "summary": "Open."}]
    started = agent_watches.utcnow() - timedelta(minutes=3)
    assert agent_watches.serialize(watch["id"], {**data, "running": {"started_at": started}})["looking"] is True
    stale = agent_watches.utcnow() - agent_watches.RUN_STALE_AFTER - timedelta(minutes=1)
    assert agent_watches.serialize(watch["id"], {**data, "running": {"started_at": stale}})["looking"] is False
    assert agent_watches.serialize(watch["id"], {**data, "running": None})["looking"] is False


def test_a_running_watch_takes_a_new_schedule_and_goal_from_now(store):
    watch = start(store, *proposed_chat(store), tier="plus")
    changed = agent_watches.update(UID, watch["id"], tier="plus", interval="weekly", run_time="09:30",
                                   weekday="monday", goal="  Registration is open ", db=store.db, now=NOW)
    assert (changed["interval"], changed["run_time"], changed["run_weekday"]) == ("weekly", "09:30", "monday")
    assert changed["goal"] == "Registration is open" and changed["timezone"] == "Europe/Berlin"
    # 3 Nov 2026 is a Tuesday: next Monday 09:30 in Berlin is 08:30 UTC.
    assert changed["next_run_at"] == datetime(2026, 11, 9, 8, 30, tzinfo=timezone.utc).isoformat()
    every = agent_watches.update(UID, watch["id"], tier="plus", interval="every_6_hours", db=store.db, now=NOW)
    assert (every["run_time"], every["run_weekday"]) == ("", "")
    assert every["next_run_at"] == (NOW + timedelta(hours=6)).isoformat()
    # Daily keeps no weekday from before; the goal can go.
    daily = agent_watches.update(UID, watch["id"], tier="plus", interval="daily", run_time="07:00", goal="",
                                 db=store.db, now=NOW)
    assert (daily["run_time"], daily["run_weekday"], daily["goal"]) == ("07:00", "", "")
    with pytest.raises(agent_watches.AgentWatchError) as error:
        agent_watches.update(UID, watch["id"], tier="plus", interval="hourly", db=store.db, now=NOW)
    assert error.value.code == "interval_not_allowed" and error.value.status == 403
    with pytest.raises(agent_watches.AgentWatchError) as error:
        agent_watches.update(UID, watch["id"], goal="x" * 201, db=store.db, now=NOW)
    assert error.value.code == "invalid_goal"
    with pytest.raises(agent_watches.AgentWatchError):
        agent_watches.update("someone-else", watch["id"], goal="", db=store.db, now=NOW)


def test_a_paused_watch_keeps_a_new_schedule_for_its_resume_and_an_ended_one_keeps_its_own(store):
    watch = start(store, *proposed_chat(store))
    agent_watches.pause(UID, watch["id"], db=store.db, now=NOW)
    changed = agent_watches.update(UID, watch["id"], tier="free", interval="weekly", run_time="10:00", db=store.db, now=NOW)
    assert changed["status"] == "paused" and changed["next_run_at"] is None and changed["interval"] == "weekly"
    resumed = agent_watches.resume(UID, watch["id"], tier="free", db=store.db, now=NOW)
    assert (resumed["interval"], resumed["run_time"]) == ("weekly", "10:00")
    agent_watches.stop(UID, watch["id"], db=store.db, now=NOW)
    with pytest.raises(agent_watches.AgentWatchError) as error:
        agent_watches.update(UID, watch["id"], tier="free", interval="daily", db=store.db, now=NOW)
    assert error.value.code == "ended" and error.value.status == 409
    # Its channels still change: the mail link's "Stop emails" works on any.
    assert agent_watches.update(UID, watch["id"], email=False, db=store.db, now=NOW)["email_enabled"] is False


def test_a_schedule_saved_as_it_stands_moves_nothing(store):
    """The panel's Save without a change (review 2026-11-04): the next run
    and a pending retry stay; a 6-hourly Watch is not pushed out by 6 hours."""
    watch = start(store, *proposed_chat(store), tier="plus", interval="every_6_hours")
    ref = store.db.collection(agent_watches.COLLECTION).document(watch["id"])
    soon, first = NOW + timedelta(minutes=5), NOW - timedelta(minutes=5)
    ref.update({"next_run_at": soon, "retry_of": first})
    same = agent_watches.update(UID, watch["id"], tier="plus", interval="every_6_hours", run_time="", weekday="",
                                timezone_name="Europe/Berlin", db=store.db, now=NOW)
    assert same["next_run_at"] == soon.isoformat()
    assert (record(store, watch["id"])["next_run_at"], record(store, watch["id"])["retry_of"]) == (soon, first)
    # A daily one at the same time in the same zone, as the panel sends it.
    daily = start(store, *proposed_chat(store))
    ref = store.db.collection(agent_watches.COLLECTION).document(daily["id"])
    ref.update({"next_run_at": soon, "retry_of": first})
    agent_watches.update(UID, daily["id"], tier="free", interval="daily", run_time="08:00", weekday="",
                         timezone_name="Europe/Berlin", db=store.db, now=NOW)
    assert (record(store, daily["id"])["next_run_at"], record(store, daily["id"])["retry_of"]) == (soon, first)
    # Another zone is another time: that one counts from now.
    moved = agent_watches.update(UID, daily["id"], tier="free", interval="daily", run_time="08:00", weekday="",
                                 timezone_name="America/New_York", db=store.db, now=NOW)
    assert moved["timezone"] == "America/New_York"
    # 12:00 UTC is 07:00 in New York: its 08:00 is still ahead today, 13:00 UTC.
    assert moved["next_run_at"] == datetime(2026, 11, 3, 13, 0, tzinfo=timezone.utc).isoformat()
    assert record(store, daily["id"])["retry_of"] is None


def test_a_new_schedule_without_a_plan_gets_the_lowest_plans_intervals(store):
    """update() fails closed (review 2026-11-04): a reschedule without a tier
    is held to Free's intervals, never the account's best."""
    watch = start(store, *proposed_chat(store), tier="pro", interval="hourly")
    with pytest.raises(agent_watches.AgentWatchError) as error:
        agent_watches.update(UID, watch["id"], interval="every_6_hours", db=store.db, now=NOW)
    assert error.value.code == "interval_not_allowed" and error.value.status == 403
    assert agent_watches.update(UID, watch["id"], interval="weekly", db=store.db, now=NOW)["interval"] == "weekly"
    # The goal and the channels need no plan.
    assert agent_watches.update(UID, watch["id"], goal="It is open", email=False, db=store.db, now=NOW)["goal"] == "It is open"


# --- the mail -------------------------------------------------------------------

def mail(**overrides):
    fields = {"recipient": "max@example.com", "outcome": "finding", "task": TASK, "goal": "Registration is open",
              "summary": "Registration for IRONMAN Hamburg 2027 is open.", "evidence_url": "https://www.ironman.com/im-hamburg",
              "evidence_title": "IRONMAN Hamburg", "halted": False, "goal_met": False, "goal_reason": "",
              "review": {"reviewers": 2, "issues": 0}, "app_url": "https://consens.io/app"}
    return mailer.build_agent_watch_message(**{**fields, **overrides})


def text_of(message):
    return message.get_body(("plain",)).get_content()


def test_the_finding_mail_leads_with_the_finding_and_its_page():
    message = mail()
    assert message["Subject"] == "Watch: Registration for IRONMAN Hamburg 2027 is open."
    plain = text_of(message)
    assert plain.startswith("WHAT IT FOUND\nRegistration for IRONMAN Hamburg 2027 is open.")
    assert "https://www.ironman.com/im-hamburg" in plain and "2 reviewers checked this run" in plain
    html = message.get_body(("html",)).get_content()
    assert 'href="https://www.ironman.com/im-hamburg"' in html and "Open the chat in consens.io" in html


def test_the_mail_speaks_the_readers_language_and_says_what_the_user_must_do():
    message = mail(language="de", outcome="needs_you", summary="", halted=True, review={"reviewers": 1, "issues": 1})
    assert message["Subject"].startswith("Deine Watch braucht dich: Ein Prüfer hat den Lauf")
    plain = text_of(message)
    assert "Die Prüfer haben eine Stelle markiert" in plain and "Chat in consens.io öffnen" in plain
    done = mail(outcome="done", summary="", goal_reason="Registration opened today.", goal_met=True, evidence_url="")
    assert done["Subject"] == "Reached: Registration is open"
    assert "The goal is met, so the Watch has ended." in text_of(done)


# --- the routes and a run through the Agent route ---------------------------------

@pytest.fixture
def watch_api(api, monkeypatch):
    from app.api.routers import agent_watches as routes
    client, store, calls = api
    monkeypatch.setattr(routes, "db_firestore", store.db)
    monkeypatch.setattr(routes, "get_user_tier", lambda uid: "free")
    client.app.include_router(routes.router)
    return client, store, calls


def test_the_routes_start_list_and_end_a_watch(watch_api):
    client, store, _ = watch_api
    chat_id, turn_id = proposed_chat(store)
    body = {"chat_id": chat_id, "turn_id": turn_id, "interval": "daily", "run_time": "07:00", "timezone": "Europe/Berlin"}
    started = client.post("/agent/watches", json=body, headers=AUTH)
    assert started.status_code == 201 and started.json()["watch"]["task"] == TASK
    again = client.post("/agent/watches", json=body, headers=AUTH)
    assert again.status_code == 409 and again.json()["code"] == "already_watched"
    hourly = client.post("/agent/watches", json={**body, "interval": "hourly"}, headers=AUTH)
    assert hourly.status_code in {403, 409}
    listed = client.get(f"/agent/watches?chat_id={chat_id}", headers=AUTH).json()
    assert [watch["id"] for watch in listed["watches"]] == [started.json()["watch"]["id"]]
    assert listed["active_count"] == 1 and listed["active_limit"] == 2 and listed["intervals"] == ["daily", "weekly"]
    watch_id = started.json()["watch"]["id"]
    assert client.post(f"/agent/watches/{watch_id}/stop", json={}, headers=AUTH).json()["watch"]["status"] == "done"
    assert client.post("/agent/watches/unknown/stop", json={}, headers=AUTH).status_code == 404
    # Another account sees none of them and cannot end them.
    other = {"Authorization": "Bearer someone-else"}
    assert client.get("/agent/watches", headers=other).json()["watches"] == []
    assert client.post(f"/agent/watches/{watch_id}/stop", json={}, headers=other).status_code == 404


def test_a_scheduled_run_goes_through_the_agent_route_quietly(watch_api, monkeypatch):
    from app.api.routers import agent
    from app.services.agent_runs import APP_CONTEXT_OPEN
    client, store, calls = watch_api
    chat_id = client.post("/chats", json={"execution_mode": "agent"}, headers=AUTH).json()["chat"]["id"]
    first = {"chat_id": chat_id, "question": "When does IRONMAN Hamburg registration open?",
             "client_request_id": "first", "bookmark_id": BOOKMARK}
    assert client.post("/agent", json=first, headers=AUTH).status_code == 200
    bookmark = store.db.collection("users").document(UID).collection("bookmarks").document(BOOKMARK)
    before = bookmark.get().to_dict()
    ended = []
    monkeypatch.setattr(agent_watches, "turn_ended", lambda *args: ended.append(args))
    run = {"watch_id": "w" * 32, "scheduled_at": NOW.isoformat(), "request_id": "watch.w.1", "goal": "Registration is open"}

    @client.app.post("/test-watch-run")
    def watch_run():
        payload = agent.AgentRequest(chat_id=chat_id, client_request_id="watch.w.1", bookmark_id=BOOKMARK, question=TASK)
        return agent.start_agent_turn(UID, payload, watch_run=run)

    assert client.post("/test-watch-run", headers=AUTH).status_code == 200
    turns = store.list_turns(UID, chat_id)["turns"]
    turn = store.get_turn(UID, chat_id, next(t["id"] for t in turns if t["question"] == TASK))
    assert turn["agent_settings"]["watch_run"] == run and turn["status"] == "completed"
    # The run's prompt and context say what it is; no prepare_watch in it.
    request = calls[-1]
    assert agent_watch.RUN_PROMPT in request["messages"][0]["content"]
    context = next(m["content"] for m in reversed(request["messages"]) if str(m["content"]).startswith(APP_CONTEXT_OPEN))
    assert "scheduled Watch run" in context and "Registration is open" in context
    names = {tool["function"]["name"] for tool in request.get("tools") or [] if tool.get("type") == "function"}
    assert "report_finding" in names and "prepare_watch" not in names
    # Nothing found: the chat keeps its place, the Watch hears of the end.
    assert bookmark.get().to_dict()["turn_id"] == before["turn_id"]
    assert ended and ended[0][:3] == (UID, chat_id, turn["id"]) and ended[0][3] == run


# --- the Watches page: own words, a chat of its own, pause, seen, channels ----

def test_the_users_own_task_starts_in_its_chat_and_a_new_chat_runs_at_once(store, monkeypatch):
    woken = []
    monkeypatch.setattr("app.services.watch_scheduler.wake_watch_scheduler", lambda: woken.append(1))
    chat_id, _ = proposed_chat(store, proposal={})
    own = start(store, chat_id, "", task="  Check the  price of the Garmin 965 on bike-discount.de ", goal="Under 400 €")
    assert own["task"] == "Check the price of the Garmin 965 on bike-discount.de" and own["goal"] == "Under 400 €"
    assert own["chat_id"] == chat_id and own["turn_id"] == "" and not woken
    with pytest.raises(agent_watches.AgentWatchError) as error:
        start(store, chat_id, "", task="Short")
    assert error.value.code == "invalid_task"
    # "New Watch" on the page: a chat of its own, titled by the task, its first run due now.
    fresh = agent_watches.create(UID, tier="free", task="Tell me when the IRONMAN Hamburg 2027 registration opens.",
                                 timezone_name="Europe/Berlin", db=store.db, now=NOW)
    chat = store.db.chats(UID)[fresh["chat_id"]]
    assert chat["execution_mode"] == "agent" and chat["title"] == "Tell me when the IRONMAN Hamburg 2027 registration opens"
    assert fresh["next_run_at"] == NOW.isoformat() and fresh["bookmark_id"].startswith("agent_watch_") and woken
    # Full: no empty chat is left behind.
    chats = len(store.db.chats(UID))
    with pytest.raises(agent_watches.AgentWatchError) as error:
        agent_watches.create(UID, tier="free", task="One more thing to watch for me.", db=store.db, now=NOW)
    assert error.value.code == "limit_reached" and len(store.db.chats(UID)) == chats


def test_a_page_watch_ended_before_its_first_run_takes_its_empty_chat_along(store, monkeypatch):
    """The chat the Watches page opened gets its sidebar entry with the first
    run's answer. Ended before that run (its first time skipped, the day's
    runs used up), it stayed hidden and held one of the account's chats for
    good (bug hunt 2026-11-04)."""
    monkeypatch.setattr("app.services.watch_scheduler.wake_watch_scheduler", lambda: None)
    fresh = agent_watches.create(UID, tier="free", task="Tell me when the IRONMAN Hamburg 2027 registration opens.",
                                 timezone_name="Europe/Berlin", db=store.db, now=NOW)
    ended = agent_watches.stop(UID, fresh["id"], db=store.db, now=NOW)
    assert ended["status"] == "done" and ended["ended"] == "user"
    assert (store._chat_ref(UID, fresh["chat_id"]).get().to_dict() or {}).get("status") != "active"
    assert record(store, fresh["id"]) is None
    assert agent_watches.outlook(UID, fresh["chat_id"], "free", db=store.db)["active_count"] == 0
    # A Watch that has run, or one in a chat of the user's own, leaves its chat as it is.
    ran = agent_watches.create(UID, tier="free", task="Tell me when the Berlin marathon 2027 date is out.",
                               timezone_name="Europe/Berlin", db=store.db, now=NOW)
    run, _reason = agent_watches.claim(ran["id"], db=store.db, now=NOW)
    assert run is not None
    agent_watches.stop(UID, ran["id"], db=store.db, now=NOW)
    assert store._chat_ref(UID, ran["chat_id"]).get().to_dict()["status"] == "active"
    own = start(store, *proposed_chat(store))
    agent_watches.stop(UID, own["id"], db=store.db, now=NOW)
    assert store._chat_ref(UID, own["chat_id"]).get().to_dict()["status"] == "active"


def test_pause_frees_the_slot_resume_takes_it_and_end_works_on_a_paused_one(store):
    first = start(store, *proposed_chat(store))
    second = start(store, *proposed_chat(store))
    paused = agent_watches.pause(UID, first["id"], db=store.db, now=NOW)
    assert paused["status"] == "paused" and paused["next_run_at"] is None
    assert agent_watches.outlook(UID, first["chat_id"], "free", db=store.db)["active_count"] == 1
    third = start(store, *proposed_chat(store))
    with pytest.raises(agent_watches.AgentWatchError) as error:
        agent_watches.resume(UID, first["id"], tier="free", db=store.db, now=NOW)
    assert error.value.code == "limit_reached"
    agent_watches.stop(UID, third["id"], db=store.db, now=NOW)
    resumed = agent_watches.resume(UID, first["id"], tier="free", db=store.db, now=NOW)
    assert resumed["status"] == "active" and resumed["next_run_at"]
    agent_watches.pause(UID, second["id"], db=store.db, now=NOW)
    assert agent_watches.stop(UID, second["id"], db=store.db, now=NOW)["status"] == "done"
    with pytest.raises(agent_watches.AgentWatchError):
        agent_watches.pause("someone-else", first["id"], db=store.db)


def test_a_resumed_watch_takes_an_interval_its_tier_still_has(store):
    watch = start(store, *proposed_chat(store), tier="pro", interval="hourly")
    agent_watches.pause(UID, watch["id"], db=store.db, now=NOW)
    resumed = agent_watches.resume(UID, watch["id"], tier="free", db=store.db, now=NOW)
    assert (resumed["interval"], resumed["run_time"]) == ("daily", "08:00")


def test_seen_and_channels_decide_what_the_next_run_sends(store, monkeypatch):
    monkeypatch.setattr("app.services.watch_scheduler.wake_watch_scheduler", lambda: None)
    finding = {"summary": "Registration is open.", "evidence_url": "https://www.ironman.com/im-hamburg"}
    _, watch_id, _ = ended_run(store, {"finding": finding})
    assert agent_watches.seen(UID, watch_id, db=store.db, now=NOW)["unread"] is False
    watch = agent_watches.set_channels(UID, watch_id, telegram=False, db=store.db, now=NOW)
    assert watch["telegram_enabled"] is False and watch["email_enabled"] is True
    store.db.documents = {path: data for path, data in store.db.documents.items() if path[0] != outbox.OUTBOX_COLLECTION}
    record(store, watch_id)  # still there
    store.db.collection(agent_watches.COLLECTION).document(watch_id).update(
        {"next_run_at": NOW, "running": None, "status": "active"})
    run, _ = agent_watches.claim(watch_id, now=NOW, db=store.db)
    chat_id = record(store, watch_id)["chat_id"]
    store._chat_ref(UID, chat_id).update({"agent_lock_until": None})
    _, turn = pending(store, chat_id=chat_id, request_id=run["request_id"], question=TASK)
    store.db.turns(UID, chat_id)[turn["id"]].update({"status": "completed", "agent_watch_run": {"finding": finding}})
    agent_watches.turn_ended(UID, chat_id, turn["id"], {"watch_id": watch_id, "request_id": run["request_id"]},
                             db=store.db, now=NOW)
    assert [item["channel"] for item in outbox_items(store)] == ["email"]


def test_the_stop_emails_link_is_its_own_kind_and_keeps_the_watch_running(store, monkeypatch):
    monkeypatch.setenv("WATCH_UNSUBSCRIBE_SECRET", "test-secret")
    watch = start(store, *proposed_chat(store))
    token = agent_watches.unsubscribe_token(watch["id"])
    assert agent_watches.parse_unsubscribe_token(token) == watch["id"]
    from app.services import watch_service
    # A Watch link of another kind is no "Stop emails" link, and the other way round.
    with pytest.raises(agent_watches.AgentWatchError):
        agent_watches.parse_unsubscribe_token(watch_service.make_unsubscribe_token(watch["id"]))
    with pytest.raises(watch_service.WatchError):
        watch_service.parse_unsubscribe_token(token)
    stopped = agent_watches.stop_emails(watch["id"], db=store.db, now=NOW)
    assert stopped["email_enabled"] is False and stopped["status"] == "active"
    assert agent_watches.stop_emails("gone" * 8, db=store.db) is None


def test_a_found_picture_is_kept_with_the_watch_and_goes_with_it(store):
    watch = start(store, *proposed_chat(store))
    found = {"content": b"\x89PNG-bytes", "content_type": "image/png", "width": 120, "height": 120,
             "kind": "item", "source_url": "https://www.ironman.com/im-hamburg", "source_host": "ironman.com"}
    assert agent_watches.PICTURES.store(watch["id"], None, db=store.db, now=NOW) == "none"
    assert agent_watches.PICTURES.store(watch["id"], found, db=store.db, now=NOW) == "ready"
    shown = agent_watches.watch_of(watch["id"], db=store.db)["image"]
    assert shown["url"].startswith(f"/api/watch/{watch['id']}/image/") and shown["kind"] == "item"
    # Found once, never replaced; and off in tests, so no run looks again.
    assert agent_watches.PICTURES.store(watch["id"], found, db=store.db, now=NOW) == "kept"
    assert agent_watches.PICTURES.look(watch["id"], record(store, watch["id"]), [{"url": "https://a.example"}]) is False
    from app.services import watch_images
    assert watch_images.load_image(watch["id"], shown["url"].rsplit("/", 1)[1], db=store.db)[1] == "image/png"
    agent_watches.delete_for_chat(store.db, UID, watch["chat_id"])
    assert store.db.collection(watch_images.WATCH_IMAGES_COLLECTION).document(watch["id"]).get().exists is False



def photo_bytes():
    import io
    import random
    from PIL import Image
    rng = random.Random(7)
    image = Image.new("RGB", (600, 400))
    image.putdata([(rng.randrange(256), rng.randrange(256), rng.randrange(256)) for _ in range(600 * 400)])
    buffer = io.BytesIO()
    image.save(buffer, "JPEG")
    return buffer.getvalue()


def test_a_new_watch_looks_for_its_picture_at_once(store, monkeypatch):
    looked = []
    monkeypatch.setattr(agent_watches.PICTURES, "first", lambda watch_id, data, db=None: looked.append(watch_id))
    watch = start(store, *proposed_chat(store))
    assert looked == [watch["id"]]


def test_the_first_picture_is_a_photo_of_what_the_watch_is_about(store):
    watch = start(store, *proposed_chat(store))
    asked, fetched = [], []

    def words(task, goal):
        asked.append((task, goal))
        return "IRONMAN Hamburg"

    def search(query, count):
        asked.append(query)
        return [{"thumbnail": "https://imgs.search.brave.com/broken", "page": "https://example.org/a"},
                {"thumbnail": "https://imgs.search.brave.com/race", "picture": "https://www.ironman.com/race.jpg",
                 "page": "https://www.ironman.com/im-hamburg"}]

    async def fetch(url, purpose):
        fetched.append((url, purpose))
        if url.endswith("broken"):
            raise ValueError("status_404")
        return url, photo_bytes(), "image/jpeg", False

    outcome = agent_watches.PICTURES.find_first(watch["id"], record(store, watch["id"]), store.db,
                                                words=words, search=search, fetch=fetch)
    assert outcome == "ready"
    assert asked == [(PROPOSAL["task"], PROPOSAL.get("goal", "")), "IRONMAN Hamburg"]
    # Brave's copy first; one that does not load is passed over.
    assert fetched == [("https://imgs.search.brave.com/broken", "image"), ("https://imgs.search.brave.com/race", "image")]
    image = record(store, watch["id"])["image"]
    assert image["status"] == "ready" and image["source_host"] == "ironman.com" and image["tries"] == 1


def test_without_a_subject_photo_the_first_picture_comes_from_the_chats_pages(store, monkeypatch):
    chat_id, turn_id = proposed_chat(store)
    store.db.turns(UID, chat_id)[turn_id]["sources"] = [{"url": "https://www.ironman.com/im-hamburg", "title": "IM"}]
    watch = start(store, chat_id, turn_id)
    from app.services import watch_images
    seen = []
    monkeypatch.setattr(watch_images, "find_image", lambda sources, task, goal, fetch=None: seen.append(sources))
    outcome = agent_watches.PICTURES.find_first(watch["id"], record(store, watch["id"]), store.db,
                                                words=lambda task, goal: "", search=lambda query, count: [])
    assert seen == [[{"url": "https://www.ironman.com/im-hamburg", "title": "IM"}]]
    # Nothing found is one look of three; the runs look again.
    assert outcome == "none" and record(store, watch["id"])["image"]["tries"] == 1
    # A chat the Watches page opened has no pages yet: its first run brings them.
    own = agent_watches.create(UID, task="Tell me when the Hamburg marathon 2027 date is announced.",
                               tier="free", timezone_name="Europe/Berlin", db=store.db, now=NOW)
    assert agent_watches.PICTURES.chat_sources(store.db, record(store, own["id"])) == []


# --- messages: the stop link in the mail, Telegram ------------------------------

def test_the_mail_carries_a_one_click_stop_link():
    message = mail(unsubscribe_url="https://consens.io/agent-watch/unsubscribe?token=abc")
    assert message["List-Unsubscribe"] == "<https://consens.io/agent-watch/unsubscribe?token=abc>"
    assert message["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    assert "Stop emails from this Watch: https://consens.io/agent-watch/unsubscribe?token=abc" in text_of(message)


def test_telegram_gets_the_finding_where_the_account_linked_it(store, monkeypatch):
    from app.services import notification_delivery as delivery, telegram_watch
    watch = start(store, *proposed_chat(store))
    sent = []
    monkeypatch.setattr(telegram_watch, "send",
                        lambda chat, message: sent.append((chat, message)) or {"status": "sent"})
    item = outbox.agent_watch_item(uid=UID, watch_id=watch["id"], run_id="t1", now=NOW, channel=outbox.CHANNEL_TELEGRAM,
                                   payload={"outcome": "finding", "summary": "Open.", "bookmark_id": BOOKMARK})["data"]

    def attempt():
        return asyncio.run(delivery.attempt(item, db=store.db, now=NOW))

    assert attempt() == (outbox.SKIPPED, "telegram_not_linked")
    store.db.collection(telegram_watch.CONNECTIONS_COLLECTION).document(UID).set({"enabled": True, "chat_id": 42})
    assert attempt() == (outbox.SENT, "")
    chat, message = sent[0]
    buttons = [button["url"] for row in message.keyboard["inline_keyboard"] for button in row]
    assert chat == 42 and buttons[-1].endswith(f"/app?chat={BOOKMARK}") and "Open." in message.text
    agent_watches.set_channels(UID, watch["id"], telegram=False, db=store.db)
    assert attempt() == (outbox.SKIPPED, "channel_disabled")


def test_the_telegram_text_is_the_finding_in_the_readers_language():
    from app.services import telegram_watch
    text = telegram_watch._agent_watch_text({"outcome": "finding", "summary": "Die Anmeldung ist offen.",
                                             "evidence_url": "https://www.ironman.com/im-hamburg", "task": TASK}, "de")
    assert text.startswith("<b>Deine Watch hat etwas gefunden</b>\n\nDie Anmeldung ist offen.")
    assert 'Gesehen auf: <a href="https://www.ironman.com/im-hamburg">ironman.com</a>' in text


# --- the Consensus Watches from before: archived ---------------------------------

def test_the_consensus_watches_are_archived(monkeypatch):
    from app.services import watch_scheduler, watch_service
    monkeypatch.setitem(cfg.LIMITS, "consensus_watches_archived", 1)
    assert asyncio.run(watch_scheduler.run_watch_tick()) == 0
    assert asyncio.run(watch_scheduler.run_brief_tick()) == 0
    # Their last times stay in the past for good: the loop sleeps until the
    # next Agent Watch, not half an hour (review 2026-11-03).
    monkeypatch.setattr(watch_service, "earliest_next_run_at", lambda: NOW - timedelta(days=3))
    monkeypatch.setattr(agent_watches, "earliest_next_run_at", lambda: NOW + timedelta(minutes=5))
    assert watch_scheduler.next_tick_seconds(now=NOW) == 305
    # A due one waiting for room is looked at again within minutes.
    monkeypatch.setattr(agent_watches, "earliest_next_run_at", lambda: NOW - timedelta(minutes=1))
    assert watch_scheduler.next_tick_seconds(now=NOW) == agent_watches.BLOCKED_RECHECK.total_seconds()
    from app.api.routers import share
    meta = share._build_watch_page_meta({"status": "active", "interval": "daily"}, [])
    assert meta["status"] == "history" and meta["is_active"] is False
    from app.api.routers import watch
    with pytest.raises(HTTPException) as error:
        watch._refuse_archived()
    assert error.value.status_code == 410 and error.value.error_fields["code"] == "watch_archived"


def test_a_wake_from_another_thread_reaches_the_scheduler(monkeypatch):
    import threading
    from app.services import watch_scheduler

    async def scenario():
        event = asyncio.Event()
        monkeypatch.setattr(watch_scheduler, "_scheduler_wake_event", event)
        monkeypatch.setattr(watch_scheduler, "_scheduler_loop", asyncio.get_running_loop())
        threading.Thread(target=watch_scheduler.wake_watch_scheduler).start()
        await asyncio.wait_for(event.wait(), 2)
        return True

    assert asyncio.run(scenario())


def test_a_page_watch_refused_late_leaves_no_empty_chat(store, monkeypatch):
    from app.services import watch_service
    monkeypatch.setattr("app.services.watch_scheduler.wake_watch_scheduler", lambda: None)
    created = []
    original = store.__class__.create_chat

    def remember(self, *args, **kwargs):
        chat = original(self, *args, **kwargs)
        created.append(chat["id"])
        return chat

    monkeypatch.setattr("app.services.agent_runs.AgentRunStore.create_chat", remember)

    def refuse(db, operation):
        raise agent_watches.AgentWatchError("limit_reached", "All your Watches are in use.", status=429)

    monkeypatch.setattr(watch_service, "_run_transaction", refuse)
    with pytest.raises(agent_watches.AgentWatchError):
        agent_watches.create(UID, task="Tell me when the Hamburg marathon 2027 date is announced.",
                             tier="free", timezone_name="Europe/Berlin", db=store.db, now=NOW)
    assert created and (store._chat_ref(UID, created[0]).get().to_dict() or {}).get("status") != "active"


def test_an_archived_watchs_resume_link_says_so(watch_api, monkeypatch):
    client, _store, _calls = watch_api
    from app.api.routers import watch as watch_routes
    client.app.include_router(watch_routes.router)
    monkeypatch.setitem(cfg.LIMITS, "consensus_watches_archived", 1)
    monkeypatch.setenv("WATCH_UNSUBSCRIBE_SECRET", "test-secret")
    from app.services import watch_service
    token = watch_service.make_resume_token("w" * 32)
    for method in ("get", "post"):
        response = getattr(client, method)(f"/watch/resume?token={token}")
        assert response.status_code == 410 and "This Watch is archived" in response.text


def test_the_routes_pause_resume_mark_seen_and_choose_channels(watch_api):
    client, store, _ = watch_api
    chat_id, _ = proposed_chat(store, proposal={})
    started = client.post("/agent/watches", json={"chat_id": chat_id, "task": "Check the IRONMAN Hamburg page.",
                                                  "timezone": "Europe/Berlin"}, headers=AUTH)
    assert started.status_code == 201
    watch_id = started.json()["watch"]["id"]
    assert client.post(f"/agent/watches/{watch_id}/pause", headers=AUTH).json()["watch"]["status"] == "paused"
    assert client.post(f"/agent/watches/{watch_id}/resume", headers=AUTH).json()["watch"]["status"] == "active"
    assert client.post(f"/agent/watches/{watch_id}/seen", headers=AUTH).json()["watch"]["unread"] is False
    changed = client.patch(f"/agent/watches/{watch_id}", json={"email_enabled": False}, headers=AUTH).json()["watch"]
    assert changed["email_enabled"] is False and changed["telegram_enabled"] is True
    moved = client.patch(f"/agent/watches/{watch_id}", json={"interval": "weekly", "run_time": "09:00",
                                                              "run_weekday": "friday", "goal": "It is open"},
                         headers=AUTH).json()["watch"]
    assert (moved["interval"], moved["run_time"], moved["run_weekday"], moved["goal"]) == ("weekly", "09:00", "friday", "It is open")
    # The plan decides how often (free: daily and weekly).
    hourly = client.patch(f"/agent/watches/{watch_id}", json={"interval": "hourly"}, headers=AUTH)
    assert hourly.status_code == 403 and hourly.json()["code"] == "interval_not_allowed"
    assert client.patch(f"/agent/watches/{watch_id}", json={"colour": "red"}, headers=AUTH).status_code == 422
    other = {"Authorization": "Bearer someone-else"}
    assert client.post(f"/agent/watches/{watch_id}/pause", headers=other).status_code == 404


def test_the_stop_emails_pages_ask_then_act(watch_api, monkeypatch):
    monkeypatch.setenv("WATCH_UNSUBSCRIBE_SECRET", "test-secret")
    client, store, _ = watch_api
    watch = start(store, *proposed_chat(store))
    token = agent_watches.unsubscribe_token(watch["id"])
    asked = client.get(f"/agent-watch/unsubscribe?token={token}")
    assert asked.status_code == 200 and "Stop emails from this Watch?" in asked.text and TASK in asked.text
    assert record(store, watch["id"])["email_enabled"] is True
    done = client.post(f"/agent-watch/unsubscribe?token={token}", data={"List-Unsubscribe": "One-Click"})
    assert done.status_code == 200 and "Emails stopped" in done.text
    assert record(store, watch["id"])["email_enabled"] is False
    assert client.get("/agent-watch/unsubscribe?token=broken").status_code == 400


def test_a_watch_pages_first_run_gives_its_new_chat_a_sidebar_entry(watch_api, monkeypatch):
    from app.api.routers import agent
    client, store, _ = watch_api
    monkeypatch.setattr(agent_watches, "turn_ended", lambda *args: None)
    chat_id = client.post("/chats", json={"execution_mode": "agent"}, headers=AUTH).json()["chat"]["id"]
    run = {"watch_id": "w" * 32, "scheduled_at": NOW.isoformat(), "request_id": "watch.w.first", "goal": ""}

    @client.app.post("/test-first-run")
    def first_run():
        payload = agent.AgentRequest(chat_id=chat_id, client_request_id="watch.w.first", bookmark_id="agent_watch_first",
                                     question=TASK)
        return agent.start_agent_turn(UID, payload, watch_run=run)

    assert client.post("/test-first-run", headers=AUTH).status_code == 200
    bookmark = store.db.collection("users").document(UID).collection("bookmarks").document("agent_watch_first").get()
    assert bookmark.exists and bookmark.to_dict()["chat_id"] == chat_id
