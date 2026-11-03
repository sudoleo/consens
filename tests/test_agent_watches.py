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


def test_a_finding_is_mailed_with_its_page_and_the_reviewers_counts(store, monkeypatch):
    woken = []
    monkeypatch.setattr("app.services.watch_scheduler.wake_watch_scheduler", lambda: woken.append(1))
    finding = {"summary": "Registration is open.", "evidence_url": "https://www.ironman.com/im-hamburg",
               "evidence_title": "IRONMAN Hamburg", "needs_user": False}
    review = {"audit": {"reviewers": [{"provider": "a"}, {"provider": "b"}], "issues": []}}
    outcome, watch_id, turn_id = ended_run(store, {"finding": finding}, agent_review=review)
    assert outcome == "finding" and woken
    [item] = outbox_items(store)
    assert item["kind"] == outbox.KIND_AGENT_WATCH and item["resource_id"] == watch_id and item["run_id"] == turn_id
    payload = item["payload"]
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
