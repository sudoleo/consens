"""Watches that run the Agent on a schedule (since 2026-11-03, "Watch mit Agent").

A Watch is a task with a schedule in one Agent chat. At its time the server
starts an ordinary Agent turn in that chat (routers/agent.py
start_agent_turn, on agent_background's thread), with no browser open: the
agent does the task with every tool it has in the chat and decides itself
how to look. It reaches the user in two ways only (agent_watch.py
WatchRunTools): ``report_finding`` with a page it opened in this run as
evidence, which mails the user once the turn has ended and its reviewers
have looked, and ``finish_watch``, which ends the Watch once its goal is
met. A run without either is quiet: no mail, and the chat keeps its place in
the sidebar (routers/agent.py _final).

What the task says, the agent may do in the user's name: starting the Watch
from its card is that permission (Max, 2026-11-03). The user is away during
a run, so a card that would wait for them (ask_user, a reviewer's halt)
ends at once (DelegationLoop.hold_timeout); a halt is mailed.

The agent prepares a Watch (agent_watch.py prepare_watch, the card under its
answer); only the user starts it (POST /agent/watches), in the chat where
it was prepared. The records live in the top-level collection
``agent_watches``: the due query spans all accounts, a single-field range on
``next_run_at``, which only an active Watch carries. The account's slots
(``users/{uid}/agent_watch_state/slots``) keep the limit and one Watch per
chat in one transaction. Schedules reuse watch_service's local-time rules
for daily and weekly runs.

Nothing is made up later (feedback 2026-10: liegengebliebene Jobs verfallen):
a run more than LATE_AFTER behind its time is skipped to the next one; a run
whose allowance is spent fails like any message, and the next one tries
again.
"""
from __future__ import annotations

import asyncio
import logging
import secrets
import threading
from datetime import datetime, timedelta, timezone

from google.cloud.firestore_v1.base_query import FieldFilter

from app.core import config as cfg
from app.core.observability import record_metric, safe_exception
from app.core.security import db_firestore
from app.services import notification_outbox as outbox
from app.services import persistence_guard, watch_service

COLLECTION = "agent_watches"
STATE_COLLECTION = "agent_watch_state"
DAYS_COLLECTION = "agent_watch_days"

STATUS_ACTIVE = "active"
STATUS_DONE = "done"

TASK_MIN_CHARS = 8
TASK_MAX_CHARS = 500
GOAL_MAX_CHARS = 200
FINDING_MAX_CHARS = 600
REASON_MAX_CHARS = 300
URL_MAX_CHARS = 2000

INTERVALS = {
    "hourly": timedelta(hours=1),
    "every_6_hours": timedelta(hours=6),
    "daily": timedelta(days=1),
    "weekly": timedelta(days=7),
}
# Shortest first: what a tier allows is a tail of this order (allowed_intervals).
ORDER = ("hourly", "every_6_hours", "daily", "weekly")
# These run at a local time of day; the shorter ones every N hours from the start.
TIMED = frozenset({"daily", "weekly"})
DEFAULT_RUN_TIME = "08:00"

# A run this far behind its time waits for the next one instead.
LATE_AFTER = timedelta(hours=2)
# The chat had a turn running: the run tries again this much later.
BUSY_RETRY = timedelta(minutes=10)
# A run whose end was never recorded (the process died) blocks no later run after this.
RUN_STALE_AFTER = timedelta(hours=2)
# Runs one process starts side by side, and never two of one account (its
# workspace serves one chat at a time).
MAX_PARALLEL_RUNS = 3
# What a scheduled run reads of its chat: the newest messages up to this
# many characters (AgentRunStore.messages ``history_chars``), so the
# hundredth run costs what the first did.
HISTORY_CHARS = 40_000

_running: dict[str, str] = {}
_running_lock = threading.Lock()


class AgentWatchError(ValueError):
    """A refusal the route returns as ``{error, code}`` with ``status``."""

    def __init__(self, code: str, message: str, *, status: int = 422):
        super().__init__(message)
        self.code = code
        self.status = status


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _db(db):
    return db if db is not None else db_firestore


def _ref(db, watch_id: str):
    return db.collection(COLLECTION).document(watch_id)


def _slots_ref(db, uid: str):
    return db.collection("users").document(uid).collection(STATE_COLLECTION).document("slots")


def _line(value, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


# --- limits and schedule ---------------------------------------------------

def active_limit(tier) -> int:
    return cfg.get_agent_watch_active_limit(tier)


def allowed_intervals(tier) -> list[str]:
    shortest = timedelta(hours=cfg.get_agent_watch_min_hours(tier))
    return [name for name in ORDER if INTERVALS[name] >= shortest]


def fit_interval(interval: str, tier) -> str:
    """``interval``, or the shortest one the tier allows when it is shorter."""
    allowed = allowed_intervals(tier)
    if interval in allowed:
        return interval
    return allowed[0] if allowed else "weekly"


def validate_schedule(interval, run_time="", weekday="", timezone_name="") -> dict:
    """The schedule as stored: daily and weekly at a local time (DEFAULT_RUN_TIME
    when none is given), the shorter ones without one."""
    interval = str(interval or "")
    if interval not in INTERVALS:
        raise AgentWatchError("invalid_interval", "Choose how often the Watch runs.")
    zone = str(timezone_name or "").strip() or "UTC"
    try:
        if interval in TIMED:
            run_time, zone = watch_service.validate_run_schedule(run_time or DEFAULT_RUN_TIME, zone)
            weekday = watch_service.validate_run_weekday(weekday, interval, has_run_time=True)
        else:
            _time, zone = watch_service.validate_run_schedule(DEFAULT_RUN_TIME, zone)
            run_time = weekday = ""
    except watch_service.WatchError as exc:
        raise AgentWatchError(exc.code, exc.message) from None
    return {"interval": interval, "run_time": run_time, "run_weekday": weekday, "timezone": zone}


def next_run(schedule: dict, *, now: datetime, previous: datetime | None = None) -> datetime:
    """The next run after ``now``, from the one scheduled before (``previous``)."""
    interval = schedule["interval"]
    if interval in TIMED:
        return watch_service.next_scheduled_run(
            interval, schedule["run_time"], schedule["timezone"], schedule.get("run_weekday") or "",
            now=now, previous_scheduled=previous)
    step = INTERVALS[interval]
    candidate = (previous or now) + step
    while candidate <= now:
        candidate += step
    return candidate


# --- the user's Watches ----------------------------------------------------

def serialize(watch_id: str, data: dict) -> dict:
    """What the browser shows of one Watch (agent-watch.js)."""
    last = data.get("last_run") if isinstance(data.get("last_run"), dict) else {}
    nxt = data.get("next_run_at")
    return {
        "id": watch_id, "chat_id": data.get("chat_id") or "", "turn_id": data.get("turn_id") or "",
        "task": data.get("task") or "",
        "goal": data.get("goal") or "", "status": data.get("status") or STATUS_DONE,
        "interval": data.get("interval") or "", "run_time": data.get("run_time") or "",
        "run_weekday": data.get("run_weekday") or "", "timezone": data.get("timezone") or "",
        "next_run_at": nxt.isoformat() if isinstance(nxt, datetime) else None,
        "runs": int(data.get("runs") or 0),
        "last_run": {"at": last["at"].isoformat() if isinstance(last.get("at"), datetime) else None,
                     "outcome": last.get("outcome") or "", "summary": last.get("summary") or ""} if last else None,
        "ended": data.get("ended") or "",
    }


def outlook(uid: str, chat_id: str, tier, *, db=None) -> dict:
    """What prepare_watch tells the agent: whether this chat already has a
    Watch, whether a slot is free and which intervals the account has."""
    db = _db(db)
    snapshot = _slots_ref(db, uid).get()
    active = dict((snapshot.to_dict() or {}).get("active") or {}) if snapshot.exists else {}
    limit = active_limit(tier)
    return {"already_watched": chat_id in active.values(), "active_count": len(active),
            "active_limit": limit, "limit_reached": len(active) >= limit,
            "intervals": allowed_intervals(tier)}


def _bookmark_id(db, uid: str, chat_id: str) -> str:
    """The chat's sidebar entry, which a run's answer updates like any message's."""
    query = (db.collection("users").document(uid).collection("bookmarks")
             .where(filter=FieldFilter("chat_id", "==", chat_id)).limit(1))
    for snapshot in query.stream():
        return snapshot.id
    return ""


def create(uid: str, *, chat_id: str, turn_id: str, tier, timezone_name: str = "",
           interval: str | None = None, run_time: str | None = None, weekday: str | None = None,
           db=None, now: datetime | None = None) -> dict:
    """Start the Watch the agent prepared on ``turn_id`` (its ``agent_watch``)
    in that chat. The task and the goal come from the saved proposal, never
    from the request; the schedule may be the user's own."""
    from app.services.agent_runs import AgentRunStore
    db = _db(db)
    now = now or utcnow()
    store = AgentRunStore(db)
    bookmark_id = _bookmark_id(db, uid, chat_id)
    if not bookmark_id:
        raise AgentWatchError("chat_not_found", "This chat no longer exists.", status=404)
    chat_ref, turn_ref, slots_ref = store._chat_ref(uid, chat_id), store._turn_ref(uid, chat_id, turn_id), _slots_ref(db, uid)
    watch_id = secrets.token_hex(16)
    limit = active_limit(tier)
    allowed = allowed_intervals(tier)

    def operation(tx):
        persistence_guard.ensure_account_write_allowed(uid=uid, db=db, transaction=tx)
        chat, turn, slots = chat_ref.get(transaction=tx), turn_ref.get(transaction=tx), slots_ref.get(transaction=tx)
        chat_data = (chat.to_dict() or {}) if chat.exists else {}
        if chat_data.get("status") != "active":
            raise AgentWatchError("chat_not_found", "This chat no longer exists.", status=404)
        if chat_data.get("temporary") is True:
            raise AgentWatchError("temporary_chat", "A temporary chat keeps nothing, so it cannot have a Watch.")
        if chat_data.get("google_data"):
            raise AgentWatchError("google_data", "A chat with Google information cannot have a Watch.")
        proposal = (turn.to_dict() or {}).get("agent_watch") if turn.exists else None
        proposal = proposal if isinstance(proposal, dict) else {}
        task = _line(proposal.get("task"), TASK_MAX_CHARS)
        if len(task) < TASK_MIN_CHARS:
            raise AgentWatchError("no_proposal", "This answer has no Watch to start.", status=404)
        schedule = validate_schedule(interval or proposal.get("interval"), proposal.get("run_time") if run_time is None else run_time,
                                     proposal.get("run_weekday") if weekday is None else weekday, timezone_name)
        if schedule["interval"] not in allowed:
            raise AgentWatchError("interval_not_allowed", "Runs this often need a higher plan.", status=403)
        active = dict((slots.to_dict() or {}).get("active") or {}) if slots.exists else {}
        if chat_id in active.values():
            raise AgentWatchError("already_watched", "This chat already has a Watch.", status=409)
        if len(active) >= limit:
            raise AgentWatchError("limit_reached", "All your Watches are in use. End one first.", status=429)
        data = {"uid": uid, "chat_id": chat_id, "turn_id": turn_id, "bookmark_id": bookmark_id,
                "task": task, "goal": _line(proposal.get("goal"), GOAL_MAX_CHARS), **schedule,
                "status": STATUS_ACTIVE, "next_run_at": next_run(schedule, now=now),
                "runs": 0, "last_run": None, "running": None, "created_at": now, "updated_at": now}
        tx.set(_ref(db, watch_id), data)
        tx.set(slots_ref, {"active": {**active, watch_id: chat_id}, "updated_at": now})
        return data

    data = watch_service._run_transaction(db, operation)
    return serialize(watch_id, data)


def list_for(uid: str, *, chat_id: str = "", db=None) -> list[dict]:
    db = _db(db)
    query = db.collection(COLLECTION).where(filter=FieldFilter("uid", "==", uid))
    items = [serialize(snapshot.id, snapshot.to_dict() or {}) for snapshot in query.stream()]
    if chat_id:
        items = [item for item in items if item["chat_id"] == chat_id]
    return sorted(items, key=lambda item: (item["status"] != STATUS_ACTIVE, item["next_run_at"] or ""))


def _end(tx, db, watch_id: str, data: dict, *, reason: str, now: datetime) -> None:
    """Ends a Watch inside ``tx``: no next run, its slot free. Reads first."""
    slots_ref = _slots_ref(db, data["uid"])
    slots = slots_ref.get(transaction=tx)
    active = dict((slots.to_dict() or {}).get("active") or {}) if slots.exists else {}
    tx.update(_ref(db, watch_id), {"status": STATUS_DONE, "next_run_at": None, "ended": reason,
                                   "ended_at": now, "updated_at": now})
    if watch_id in active:
        active.pop(watch_id)
        tx.set(slots_ref, {"active": active, "updated_at": now})


def stop(uid: str, watch_id: str, *, db=None, now: datetime | None = None) -> dict:
    """The user ends their Watch; a run already going finishes."""
    db = _db(db)
    now = now or utcnow()
    ref = _ref(db, watch_id)

    def operation(tx):
        snapshot = ref.get(transaction=tx)
        data = (snapshot.to_dict() or {}) if snapshot.exists else {}
        if data.get("uid") != uid:
            raise AgentWatchError("not_found", "This Watch no longer exists.", status=404)
        if data.get("status") == STATUS_ACTIVE:
            _end(tx, db, watch_id, data, reason="user", now=now)
            data = {**data, "status": STATUS_DONE, "next_run_at": None, "ended": "user"}
        return data

    return serialize(watch_id, watch_service._run_transaction(db, operation))


def delete_for_chat(db, uid: str, chat_id: str) -> int:
    """With its chat: the chat's Watches and their slots."""
    db = _db(db)
    query = db.collection(COLLECTION).where(filter=FieldFilter("uid", "==", uid))
    ids = [snapshot.id for snapshot in query.stream() if (snapshot.to_dict() or {}).get("chat_id") == chat_id]
    if not ids:
        return 0

    def operation(tx):
        slots_ref = _slots_ref(db, uid)
        slots = slots_ref.get(transaction=tx)
        active = dict((slots.to_dict() or {}).get("active") or {}) if slots.exists else {}
        for watch_id in ids:
            tx.delete(_ref(db, watch_id))
            active.pop(watch_id, None)
        if slots.exists:
            tx.set(slots_ref, {"active": active, "updated_at": utcnow()})

    watch_service._run_transaction(db, operation)
    return len(ids)


def delete_for_account(db, uid: str) -> int:
    db = _db(db)
    count = 0
    for snapshot in db.collection(COLLECTION).where(filter=FieldFilter("uid", "==", uid)).stream():
        snapshot.reference.delete()
        count += 1
    _slots_ref(db, uid).delete()
    return count


# --- the schedule's runs ---------------------------------------------------

def _stream(query):
    """The scheduler's reads: no retries and a short deadline, so a slow
    Firestore costs one tick, not a retry series (watch_service.earliest_next_run_at)."""
    try:
        return query.stream(retry=None, timeout=3.0)
    except TypeError:  # lightweight test doubles
        return query.stream()


def due(*, now: datetime | None = None, db=None, max_items: int = 20) -> list[tuple[str, str]]:
    """(watch id, uid) of the Watches whose time has come, the oldest first."""
    db = _db(db)
    now = now or utcnow()
    query = (db.collection(COLLECTION).where(filter=FieldFilter("next_run_at", "<=", now))
             .order_by("next_run_at").limit(max_items))
    return [(snapshot.id, str((snapshot.to_dict() or {}).get("uid") or "")) for snapshot in _stream(query)]


def earliest_next_run_at(*, db=None) -> datetime | None:
    """When the next run is due, for the scheduler's sleep (an ended Watch has none)."""
    db = _db(db)
    query = (db.collection(COLLECTION).where(filter=FieldFilter("next_run_at", "<=", datetime.max.replace(tzinfo=timezone.utc)))
             .order_by("next_run_at").limit(1))
    for snapshot in _stream(query):
        value = (snapshot.to_dict() or {}).get("next_run_at")
        return value if isinstance(value, datetime) else None
    return None


def claim(watch_id: str, *, now: datetime | None = None, db=None) -> tuple[dict | None, str]:
    """Takes one due run: the Watch moves on to its next time and notes the
    run as running, under the server's daily cap. Returns (run, "") or
    (None, reason): "not_due", "running", "late" (skipped), "budget"."""
    db = _db(db)
    now = now or utcnow()
    ref = _ref(db, watch_id)
    day_ref = db.collection(DAYS_COLLECTION).document(now.date().isoformat())
    cap = cfg.get_agent_watch_max_runs_per_day()

    def operation(tx):
        snapshot, day = ref.get(transaction=tx), day_ref.get(transaction=tx)
        data = (snapshot.to_dict() or {}) if snapshot.exists else {}
        scheduled = data.get("next_run_at")
        if data.get("status") != STATUS_ACTIVE or not isinstance(scheduled, datetime) or scheduled > now:
            return None, "not_due"
        running = data.get("running") if isinstance(data.get("running"), dict) else None
        if running and isinstance(running.get("started_at"), datetime) and now - running["started_at"] < RUN_STALE_AFTER:
            return None, "running"
        following = next_run(data, now=now, previous=scheduled)
        if now - scheduled > LATE_AFTER:
            tx.update(ref, {"next_run_at": following, "last_skipped_at": now, "updated_at": now})
            return None, "late"
        runs_today = int((day.to_dict() or {}).get("runs") or 0) if day.exists else 0
        if runs_today >= cap:
            return None, "budget"
        request_id = f"watch.{watch_id[:16]}.{int(scheduled.timestamp())}"
        tx.update(ref, {"next_run_at": following, "running": {"request_id": request_id, "started_at": now,
                                                              "scheduled_at": scheduled},
                        "runs": int(data.get("runs") or 0) + 1, "updated_at": now})
        tx.set(day_ref, {"runs": runs_today + 1, "updated_at": now})
        return {**data, "id": watch_id, "request_id": request_id, "scheduled_at": scheduled}, ""

    return watch_service._run_transaction(db, operation)


def run_question(watch: dict) -> str:
    """The run's message in the chat: the task as the user's words."""
    return watch["task"]


def run_context(watch: dict) -> str:
    """The run's app context (after the date): what this message is."""
    from app.services.agent_watch import RUN_NOTE
    goal = watch.get("goal") or ""
    return RUN_NOTE.format(goal=f" It ends once this goal is met: {goal}." if goal else "")


def _reviewers(uid: str, db) -> str:
    """Who checks a run's work: the account's setting, as the composer sends it."""
    try:
        from app.services.user_settings import UserSettings
        value = getattr(UserSettings(db).get(uid), "reviewers", None)
    except Exception as exc:
        logging.info("Agent watch reviewers setting unreadable category=%s", safe_exception(exc))
        value = None
    return value if value in {"always", "workspace", "off"} else "always"


def _retry_soon(watch_id: str, run: dict, *, db, now: datetime) -> None:
    """The chat was busy: the run comes again shortly, within its lateness."""
    scheduled = run.get("scheduled_at")
    retry = now + BUSY_RETRY
    ref = _ref(db, watch_id)

    def operation(tx):
        snapshot = ref.get(transaction=tx)
        data = (snapshot.to_dict() or {}) if snapshot.exists else {}
        if data.get("status") != STATUS_ACTIVE:
            return
        patch = {"running": None, "updated_at": now}
        if isinstance(scheduled, datetime) and retry - scheduled <= LATE_AFTER:
            # The schedule's next time stays where it was when it comes first.
            following = data.get("next_run_at")
            patch["next_run_at"] = min(following, retry) if isinstance(following, datetime) else retry
        tx.update(ref, patch)

    watch_service._run_transaction(db, operation)


def _not_started(watch_id: str, outcome: str, *, db, now: datetime) -> None:
    """The run did not start; a Watch whose chat is gone ends with it."""
    ref = _ref(db, watch_id)

    def operation(tx):
        snapshot = ref.get(transaction=tx)
        if not snapshot.exists:
            return
        data = snapshot.to_dict() or {}
        if outcome == "chat_gone" and data.get("status") == STATUS_ACTIVE:
            _end(tx, db, watch_id, data, reason="chat_gone", now=now)
        tx.update(ref, {"running": None, "updated_at": now,
                        "last_run": {"at": now, "turn_id": "", "outcome": outcome, "summary": ""}})

    watch_service._run_transaction(db, operation)


# Refusals a little later may not repeat: the chat busy with another
# message (409), the server's capacity or a provider's cooldown (503, 429).
_TRANSIENT = frozenset({409, 429, 503})


def _refused(watch_id: str, run: dict, status: int, *, db, now: datetime) -> None:
    logging.info("Agent watch run not started status=%s", status)
    if status in _TRANSIENT:
        _retry_soon(watch_id, run, db=db, now=now)
    else:
        _not_started(watch_id, "chat_gone" if status == 404 else "not_started", db=db, now=now)


def start_run(run: dict, *, db=None, now: datetime | None = None) -> bool:
    """Starts the claimed ``run`` as an Agent turn in its chat. True when it
    runs; otherwise the Watch notes why, or comes again soon (a busy chat)."""
    from fastapi import HTTPException
    from starlette.responses import StreamingResponse
    from app.api.routers import agent as agent_router
    db = _db(db)
    now = now or utcnow()
    watch_id, uid = run["id"], run["uid"]
    watch_run = {"watch_id": watch_id, "scheduled_at": run["scheduled_at"].isoformat(),
                 "request_id": run["request_id"], "goal": run.get("goal") or ""}
    # Before the start: a run can end (turn_ended forgets it) before the call returns.
    with _running_lock:
        _running[watch_id] = uid
    try:
        payload = agent_router.AgentRequest(
            chat_id=run["chat_id"], client_request_id=run["request_id"], bookmark_id=run["bookmark_id"],
            question=run_question(run), timezone=run.get("timezone") or None, reviewers=_reviewers(uid, db))
        response = agent_router.start_agent_turn(uid, payload, watch_run=watch_run)
    except HTTPException as exc:
        _forget(watch_id)
        _refused(watch_id, run, int(exc.status_code or 0), db=db, now=now)
        return False
    except Exception as exc:
        _forget(watch_id)
        logging.warning("Agent watch run not started category=%s", safe_exception(exc))
        _not_started(watch_id, "not_started", db=db, now=now)
        return False
    if not isinstance(response, StreamingResponse):
        # A JSON refusal (a duplicate still running, a stopped request), or
        # the saved answer of a turn this request already ran: no run follows.
        _forget(watch_id)
        if isinstance(response, dict):
            _not_started(watch_id, "already_ran", db=db, now=now)
        else:
            _refused(watch_id, run, int(getattr(response, "status_code", 0) or 0), db=db, now=now)
        return False
    record_metric("scheduler", "agent-watch-run", processed=1)
    return True


def _forget(watch_id: str) -> None:
    with _running_lock:
        _running.pop(watch_id, None)


def _busy_accounts() -> set[str]:
    with _running_lock:
        return set(_running.values())


def _room() -> bool:
    with _running_lock:
        return len(_running) < MAX_PARALLEL_RUNS


async def run_tick(*, now: datetime | None = None, db=None) -> int:
    """Starts the Watches whose time has come (the watch scheduler's loop
    calls it each tick). Returns how many started."""
    from app.services.llm.mock_llm import mock_llm_enabled
    # MOCK_LLM instances share the production Firestore (watch_scheduler.run_watch_tick).
    if mock_llm_enabled():
        return 0
    # Each claim reads the clock again (a start takes a moment); a given ``now`` holds for all.
    clock = (lambda: now) if now is not None else utcnow
    now = clock()
    try:
        candidates = await asyncio.to_thread(due, now=now, db=db)
    except Exception as exc:
        logging.warning("Agent watch due-look failed category=%s", safe_exception(exc))
        return 0
    started = 0
    for watch_id, uid in candidates:
        if not _room():
            break
        if uid in _busy_accounts():
            continue
        try:
            run, reason = await asyncio.to_thread(claim, watch_id, now=clock(), db=db)
        except Exception as exc:
            logging.warning("Agent watch claim failed category=%s", safe_exception(exc))
            continue
        if reason == "budget":
            logging.warning("Agent watch runs per day reached")
            break
        if run is None:
            continue
        started += int(await asyncio.to_thread(start_run, run, db=db, now=clock()))
    return started


# --- a run's end -----------------------------------------------------------

def _review_line(turn: dict) -> dict:
    """How the reviewers saw the run's answer, as counts (the mail says it)."""
    audit = ((turn.get("agent_review") or {}).get("audit") or {})
    reviewers = audit.get("reviewers") if isinstance(audit.get("reviewers"), list) else []
    issues = audit.get("issues") if isinstance(audit.get("issues"), list) else []
    return {"reviewers": len(reviewers), "issues": len(issues)}


def _outcome(turn: dict) -> tuple[str, dict]:
    """("finding" | "needs_you" | "done" | "quiet" | "failed", details) of a run's turn."""
    run = turn.get("agent_watch_run") if isinstance(turn.get("agent_watch_run"), dict) else {}
    finding = run.get("finding") if isinstance(run.get("finding"), dict) else None
    done = run.get("done") if isinstance(run.get("done"), dict) else None
    failure = (turn.get("agent_failure") or {}).get("code") if isinstance(turn.get("agent_failure"), dict) else ""
    if finding:
        return ("needs_you" if finding.get("needs_user") else "finding"), {**finding, "done": done}
    if done:
        return "done", {"done": done}
    if failure == "hold_timeout":
        # A reviewer halted the run and nobody was there to decide.
        return "needs_you", {"summary": "", "halted": True, "done": None}
    if turn.get("status") == "failed":
        return "failed", {}
    return "quiet", {}


def turn_ended(uid: str, chat_id: str, turn_id: str, watch_run: dict, *, db=None,
               now: datetime | None = None) -> str:
    """After a run's turn ended (its producer's last step): the Watch notes
    the run, ends when the goal is met, and stages the mail of a finding,
    a question for the user or the goal. Returns the outcome."""
    from app.services.agent_runs import AgentRunStore
    db = _db(db)
    now = now or utcnow()
    watch_id = watch_run["watch_id"]
    try:
        turn = AgentRunStore(db).get_turn(uid, chat_id, turn_id)
    except Exception as exc:
        logging.warning("Agent watch run turn unreadable category=%s", safe_exception(exc))
        turn = {"status": "failed"}
    outcome, details = _outcome(turn)
    ref = _ref(db, watch_id)

    def operation(tx):
        snapshot = ref.get(transaction=tx)
        data = (snapshot.to_dict() or {}) if snapshot.exists else {}
        if data.get("uid") != uid:
            return None
        running = data.get("running") if isinstance(data.get("running"), dict) else {}
        ends = details.get("done") is not None and data.get("status") == STATUS_ACTIVE
        if ends:
            _end(tx, db, watch_id, data, reason="goal", now=now)
        patch = {"last_run": {"at": now, "turn_id": turn_id, "outcome": outcome,
                              "summary": _line(details.get("summary"), FINDING_MAX_CHARS)},
                 "updated_at": now}
        if running.get("request_id") == watch_run.get("request_id"):
            patch["running"] = None
        tx.update(ref, patch)
        if outcome in {"finding", "needs_you", "done"}:
            item = outbox.agent_watch_item(
                uid=uid, watch_id=watch_id, run_id=turn_id, now=now, payload={
                    "outcome": outcome, "task": data.get("task") or "", "goal": data.get("goal") or "",
                    "summary": _line(details.get("summary"), FINDING_MAX_CHARS),
                    "evidence_url": str(details.get("evidence_url") or "")[:URL_MAX_CHARS],
                    "evidence_title": _line(details.get("evidence_title"), 240),
                    "halted": bool(details.get("halted")),
                    "goal_met": bool(details.get("done")), "goal_reason": _line((details.get("done") or {}).get("reason"), REASON_MAX_CHARS),
                    "review": _review_line(turn)})
            outbox.stage(tx, db, item)
            return item["id"]
        return None

    try:
        staged = watch_service._run_transaction(db, operation)
    except Exception as exc:
        logging.warning("Agent watch run end not recorded category=%s", safe_exception(exc))
        staged = None
    finally:
        _forget(watch_id)
    logging.info("Agent watch run ended outcome=%s", outcome)
    if staged:
        from app.services import watch_scheduler
        # The mail goes out on the scheduler's next pass, which this wakes.
        watch_scheduler.wake_watch_scheduler()
    return outcome
