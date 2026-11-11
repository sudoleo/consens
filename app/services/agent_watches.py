"""Watches that run the Agent on a schedule.

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
from its card is that permission (Max). The user is away during
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

Nothing is made up later (Max: liegengebliebene Jobs verfallen):
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
# A day's counts (DAYS_COLLECTION/{date}, with each account's UID) serve that
# day's caps and a run claimed before midnight that gives its run back after
# it. Older days go (purge_days, once a day from run_tick), and an account's
# deletion takes its UID out of those left, or they would keep the UIDs of
# deleted accounts for good.
DAYS_KEPT = 2

STATUS_ACTIVE = "active"
STATUS_PAUSED = "paused"
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
# Due runs that wait for room (their account's run, MAX_PARALLEL_RUNS) are
# looked at again after this at the latest; a run's end wakes the loop sooner.
BLOCKED_RECHECK = timedelta(minutes=5)
# Due Watches one tick reads: enough that one account's many Watches at the
# same time do not hide everyone else's (one run per account at a time).
DUE_BATCH = 100
# A run whose end was never recorded (the process died) blocks no later run after this.
RUN_STALE_AFTER = timedelta(hours=2)
# Runs one process starts side by side, and never two of one account (its
# workspace serves one chat at a time).
MAX_PARALLEL_RUNS = 3
# What a scheduled run reads of its chat: the newest messages up to this
# many characters (AgentRunStore.messages ``history_chars``), so the
# hundredth run costs what the first did.
HISTORY_CHARS = 40_000
# The runs a Watch keeps for its page (``looks``): the pulse of its row
# shows the newest 14, its detail 30 with what they found, each finding
# cut to a line (the whole one is in the chat).
LOOKS_KEPT = 30
LOOK_SUMMARY_CHARS = 280

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
    """The next run after ``now``, from the one scheduled before (``previous``).
    Without one (a new or resumed Watch), a daily or weekly Watch comes at
    the next such local time, today when it is still ahead:
    watch_service.next_scheduled_run counts from a run that just happened."""
    interval = schedule["interval"]
    if interval in TIMED:
        weekday = schedule.get("run_weekday") or ""
        if previous is None and not weekday:
            return watch_service.next_scheduled_run(
                "daily", schedule["run_time"], schedule["timezone"], "", now=now,
                previous_scheduled=now - timedelta(days=1))
        return watch_service.next_scheduled_run(
            interval, schedule["run_time"], schedule["timezone"], weekday,
            now=now, previous_scheduled=previous)
    step = INTERVALS[interval]
    candidate = (previous or now) + step
    while candidate <= now:
        candidate += step
    return candidate


# --- the user's Watches ----------------------------------------------------

def serialize(watch_id: str, data: dict) -> dict:
    """What the browser shows of one Watch (agent-watch.js, the Watches page)."""
    from app.services import watch_images
    last = data.get("last_run") if isinstance(data.get("last_run"), dict) else {}
    nxt = data.get("next_run_at")
    created = data.get("created_at")
    return {
        "id": watch_id, "chat_id": data.get("chat_id") or "", "turn_id": data.get("turn_id") or "",
        "bookmark_id": data.get("bookmark_id") or "", "task": data.get("task") or "",
        "goal": data.get("goal") or "", "status": data.get("status") or STATUS_DONE,
        "interval": data.get("interval") or "", "run_time": data.get("run_time") or "",
        "run_weekday": data.get("run_weekday") or "", "timezone": data.get("timezone") or "",
        "next_run_at": nxt.isoformat() if isinstance(nxt, datetime) else None,
        "created_at": created.isoformat() if isinstance(created, datetime) else None,
        "runs": int(data.get("runs") or 0),
        "last_run": {"at": last["at"].isoformat() if isinstance(last.get("at"), datetime) else None,
                     "outcome": last.get("outcome") or "", "summary": last.get("summary") or "",
                     "evidence_url": last.get("evidence_url") or ""} if last else None,
        "looks": _looks_view(data),
        # A run is going right now (claim noted it, its end has not come yet).
        "looking": _looking(data),
        "ended": data.get("ended") or "",
        # A finding, a question or the goal the user has not looked at yet (``seen``).
        "unread": data.get("unread") is True,
        # email_enabled, telegram_enabled: the switch of every channel.
        **{switch: outbox.channel_on(data, channel, defaults=outbox.AGENT_WATCH_CHANNEL_DEFAULTS)
           for channel, switch in outbox.CHANNEL_SWITCHES.items()},
        "image": watch_images.image_view(watch_id, data),
    }


def _look(outcome: str, at: datetime, summary="") -> dict:
    """One run as its Watch keeps it (``looks``): when, how it went and,
    when it told the user something, what in a line."""
    look = {"at": at, "outcome": str(outcome or "")}
    line = _line(summary, LOOK_SUMMARY_CHARS + 1)
    if line:
        look["summary"] = line if len(line) <= LOOK_SUMMARY_CHARS else line[:LOOK_SUMMARY_CHARS - 1].rstrip() + "…"
    return look


def _legacy_look(data: dict) -> list[dict]:
    """A Watch from before ``looks``: its last run as its one
    look. A run that had run already is no look of its own (_not_started),
    so it is none here either."""
    last = data.get("last_run") if isinstance(data.get("last_run"), dict) else {}
    if not isinstance(last.get("at"), datetime) or not last.get("outcome") or last.get("outcome") == "already_ran":
        return []
    return [_look(last["outcome"], last["at"], last.get("summary") or "")]


def _with_look(data: dict, look: dict) -> list[dict]:
    kept = [item for item in (data.get("looks") or []) if isinstance(item, dict) and isinstance(item.get("at"), datetime)]
    if "looks" not in data:
        # A Watch from before ``looks``: its last run stays its first look.
        kept = _legacy_look(data)
    return [*kept, look][-LOOKS_KEPT:]


def _looks_view(data: dict) -> list[dict]:
    """Its runs, oldest first. A Watch from before ``looks``
    shows its last run alone (``runs`` says it had more: the page then
    calls it its last look, not its first)."""
    looks = [item for item in (data.get("looks") or []) if isinstance(item, dict) and isinstance(item.get("at"), datetime)]
    if not looks:
        looks = _legacy_look(data)
    return [{"at": item["at"].isoformat(), "outcome": str(item.get("outcome") or ""),
             "summary": str(item.get("summary") or "")} for item in looks[-LOOKS_KEPT:]]


def _looking(data: dict) -> bool:
    running = data.get("running") if isinstance(data.get("running"), dict) else {}
    started = running.get("started_at")
    return (data.get("status") == STATUS_ACTIVE and isinstance(started, datetime)
            and utcnow() - started < RUN_STALE_AFTER)


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


def chat_title(task: str) -> str:
    """The title of a chat the Watches page opens for a task: its first words."""
    title = ""
    for word in _line(task, TASK_MAX_CHARS).split():
        if len(title) + len(word) + 1 > 60:
            break
        title = f"{title} {word}".strip()
    return title.rstrip(" .,:;") or _line(task, 60)


def create(uid: str, *, tier, chat_id: str = "", turn_id: str = "", task: str | None = None,
           goal: str | None = None, timezone_name: str = "", interval: str | None = None,
           run_time: str | None = None, weekday: str | None = None, db=None,
           now: datetime | None = None) -> dict:
    """Start a Watch in its chat. Three ways in:

    * ``turn_id``: the Watch the agent prepared on that turn (``agent_watch``);
      its task and goal come from the saved proposal, never from the request.
    * ``chat_id`` with ``task``: the user's own words (the Watch pill under an
      answer, the sheet) in that chat.
    * ``task`` alone: "New Watch" on the Watches page opens a chat of its own;
      its first run comes at once, and its task is that chat's first message.
    """
    from app.services.agent_runs import AgentRunStore
    db = _db(db)
    now = now or utcnow()
    store = AgentRunStore(db)
    own = task is not None
    if own:
        task = _line(task, TASK_MAX_CHARS + 1)
        if not TASK_MIN_CHARS <= len(task) <= TASK_MAX_CHARS:
            raise AgentWatchError("invalid_task", "Say in a sentence what the Agent should do.")
        goal = _line(goal, GOAL_MAX_CHARS + 1)
        if len(goal) > GOAL_MAX_CHARS:
            raise AgentWatchError("invalid_goal", "Keep the goal to one short sentence.")
    elif not (chat_id and turn_id):
        raise AgentWatchError("no_proposal", "This answer has no Watch to start.", status=404)
    limit = active_limit(tier)
    allowed = allowed_intervals(tier)
    if own and not chat_id:
        # Checked before the chat exists: a refused Watch leaves no empty chat behind.
        schedule = validate_schedule(interval or "daily", run_time or "", weekday or "", timezone_name)
        if schedule["interval"] not in allowed:
            raise AgentWatchError("interval_not_allowed", "Runs this often need a higher plan.", status=403)
        slots = _slots_ref(db, uid).get()
        taken = dict((slots.to_dict() or {}).get("active") or {}) if slots.exists else {}
        if len(taken) >= limit:
            raise AgentWatchError("limit_reached", "All your Watches are in use. End one first.", status=429)
        chat_id = store.create_chat(uid, title=chat_title(task), execution_mode="agent")["id"]
        bookmark_id = "agent_watch_" + secrets.token_hex(8)
        first_run = now
    else:
        bookmark_id = _bookmark_id(db, uid, chat_id)
        if not bookmark_id:
            raise AgentWatchError("chat_not_found", "This chat no longer exists.", status=404)
        first_run = None
    chat_ref, slots_ref = store._chat_ref(uid, chat_id), _slots_ref(db, uid)
    turn_ref = store._turn_ref(uid, chat_id, turn_id) if turn_id else None
    watch_id = secrets.token_hex(16)

    def operation(tx):
        persistence_guard.ensure_account_write_allowed(uid=uid, db=db, transaction=tx)
        chat, slots = chat_ref.get(transaction=tx), slots_ref.get(transaction=tx)
        turn = turn_ref.get(transaction=tx) if turn_ref is not None else None
        chat_data = (chat.to_dict() or {}) if chat.exists else {}
        if chat_data.get("status") != "active":
            raise AgentWatchError("chat_not_found", "This chat no longer exists.", status=404)
        if chat_data.get("temporary") is True:
            raise AgentWatchError("temporary_chat", "A temporary chat keeps nothing, so it cannot have a Watch.")
        if chat_data.get("google_data"):
            raise AgentWatchError("google_data", "A chat with Google information cannot have a Watch.")
        if own:
            proposal = {"task": task, "goal": goal}
        else:
            proposal = (turn.to_dict() or {}).get("agent_watch") if turn is not None and turn.exists else None
            proposal = proposal if isinstance(proposal, dict) else {}
        watch_task = _line(proposal.get("task"), TASK_MAX_CHARS)
        if len(watch_task) < TASK_MIN_CHARS:
            raise AgentWatchError("no_proposal", "This answer has no Watch to start.", status=404)
        schedule = validate_schedule(interval or proposal.get("interval") or "daily",
                                     proposal.get("run_time") if run_time is None else run_time,
                                     proposal.get("run_weekday") if weekday is None else weekday, timezone_name)
        if schedule["interval"] not in allowed:
            raise AgentWatchError("interval_not_allowed", "Runs this often need a higher plan.", status=403)
        active = dict((slots.to_dict() or {}).get("active") or {}) if slots.exists else {}
        if chat_id in active.values():
            raise AgentWatchError("already_watched", "This chat already has a Watch.", status=409)
        if len(active) >= limit:
            raise AgentWatchError("limit_reached", "All your Watches are in use. End one first.", status=429)
        data = {"uid": uid, "chat_id": chat_id, "turn_id": turn_id, "bookmark_id": bookmark_id,
                "task": watch_task, "goal": _line(proposal.get("goal"), GOAL_MAX_CHARS), **schedule,
                "status": STATUS_ACTIVE, "next_run_at": first_run or next_run(schedule, now=now),
                "runs": 0, "last_run": None, "running": None, "unread": False,
                "email_enabled": True, "telegram_enabled": True, "created_at": now, "updated_at": now}
        tx.set(_ref(db, watch_id), data)
        tx.set(slots_ref, {"active": {**active, watch_id: chat_id}, "updated_at": now})
        return data

    try:
        data = watch_service._run_transaction(db, operation)
    except Exception:
        if first_run is not None:
            # The chat was opened for this Watch alone: a refusal leaves none behind.
            try:
                store.delete_chat(uid, chat_id)
            except Exception as exc:
                logging.warning("Agent watch chat not removed category=%s", safe_exception(exc))
        raise
    if first_run is not None:
        from app.services import watch_scheduler
        # Its first run is due now: the scheduler looks at once.
        watch_scheduler.wake_watch_scheduler()
    # Its picture comes with it, not only after a run (Max).
    PICTURES.first(watch_id, data, db=db)
    return serialize(watch_id, data)


def _owned(tx, db, uid: str, watch_id: str) -> dict:
    snapshot = _ref(db, watch_id).get(transaction=tx)
    data = (snapshot.to_dict() or {}) if snapshot.exists else {}
    if data.get("uid") != uid:
        raise AgentWatchError("not_found", "This Watch no longer exists.", status=404)
    return data


def pause(uid: str, watch_id: str, *, db=None, now: datetime | None = None) -> dict:
    """No runs until it is resumed; its slot is free meanwhile."""
    db = _db(db)
    now = now or utcnow()

    def operation(tx):
        data = _owned(tx, db, uid, watch_id)
        if data.get("status") != STATUS_ACTIVE:
            return data
        slots_ref = _slots_ref(db, uid)
        slots = slots_ref.get(transaction=tx)
        active = dict((slots.to_dict() or {}).get("active") or {}) if slots.exists else {}
        active.pop(watch_id, None)
        # A busy run's retry (retry_of) ends here: after the resume, late counts from the new time.
        patch = {"status": STATUS_PAUSED, "next_run_at": None, "retry_of": None, "updated_at": now}
        tx.update(_ref(db, watch_id), patch)
        tx.set(slots_ref, {"active": active, "updated_at": now})
        return {**data, **patch}

    return serialize(watch_id, watch_service._run_transaction(db, operation))


def resume(uid: str, watch_id: str, *, tier, db=None, now: datetime | None = None) -> dict:
    """Runs again from its next time, with a free slot, at an interval the tier still has."""
    db = _db(db)
    now = now or utcnow()
    limit = active_limit(tier)

    def operation(tx):
        data = _owned(tx, db, uid, watch_id)
        if data.get("status") != STATUS_PAUSED:
            return data
        slots_ref = _slots_ref(db, uid)
        slots = slots_ref.get(transaction=tx)
        active = dict((slots.to_dict() or {}).get("active") or {}) if slots.exists else {}
        if data.get("chat_id") in active.values():
            raise AgentWatchError("already_watched", "This chat already has a Watch.", status=409)
        if len(active) >= limit:
            raise AgentWatchError("limit_reached", "All your Watches are in use. End one first.", status=429)
        interval = fit_interval(data.get("interval") or "daily", tier)
        schedule = {"interval": interval,
                    "run_time": (data.get("run_time") or DEFAULT_RUN_TIME) if interval in TIMED else "",
                    "run_weekday": (data.get("run_weekday") or "") if interval == "weekly" else "",
                    "timezone": data.get("timezone") or "UTC"}
        patch = {"status": STATUS_ACTIVE, **schedule, "next_run_at": next_run(schedule, now=now), "retry_of": None,
                 "updated_at": now}
        tx.update(_ref(db, watch_id), patch)
        tx.set(slots_ref, {"active": {**active, watch_id: data.get("chat_id")}, "updated_at": now})
        return {**data, **patch}

    return serialize(watch_id, watch_service._run_transaction(db, operation))


def seen(uid: str, watch_id: str, *, db=None, now: datetime | None = None) -> dict:
    """The user looked at what its last run found (its chat or its row)."""
    db = _db(db)
    now = now or utcnow()

    def operation(tx):
        data = _owned(tx, db, uid, watch_id)
        if data.get("unread") is True:
            tx.update(_ref(db, watch_id), {"unread": False, "seen_at": now})
            data = {**data, "unread": False}
        return data

    return serialize(watch_id, watch_service._run_transaction(db, operation))


def set_channels(uid: str, watch_id: str, *, email: bool | None = None, telegram: bool | None = None,
                 db=None, now: datetime | None = None) -> dict:
    """Where a run that found something tells the user: mail, Telegram, both or neither."""
    return update(uid, watch_id, email=email, telegram=telegram, db=db, now=now)


def update(uid: str, watch_id: str, *, tier=None, email: bool | None = None, telegram: bool | None = None,
           goal: str | None = None, interval: str | None = None, run_time: str | None = None,
           weekday: str | None = None, timezone_name: str | None = None, db=None,
           now: datetime | None = None) -> dict:
    """What the user changes on a Watch's page (PATCH): its channels, its
    goal ("" runs it until they end it) and how often it runs. A new
    schedule counts from now; one saved as it stands keeps its next run and
    a pending retry. A paused Watch keeps a new one for
    its resume; an ended Watch keeps what it had. ``tier`` decides the
    interval; without one the lowest plan's (allowed_intervals(None), Free)
    does, never more."""
    db = _db(db)
    now = now or utcnow()
    channels = {key: value for key, value in (("email_enabled", email), ("telegram_enabled", telegram))
                if isinstance(value, bool)}
    if goal is not None:
        goal = _line(goal, GOAL_MAX_CHARS + 1)
        if len(goal) > GOAL_MAX_CHARS:
            raise AgentWatchError("invalid_goal", "Keep the goal to one short sentence.")
    reschedules = any(value is not None for value in (interval, run_time, weekday, timezone_name))

    def operation(tx):
        data = _owned(tx, db, uid, watch_id)
        patch = dict(channels)
        if (goal is not None or reschedules) and data.get("status") not in {STATUS_ACTIVE, STATUS_PAUSED}:
            raise AgentWatchError("ended", "This Watch has ended.", status=409)
        if goal is not None:
            patch["goal"] = goal
        if reschedules:
            wanted = str(interval or data.get("interval") or "daily")
            schedule = validate_schedule(
                wanted, data.get("run_time") if run_time is None else run_time,
                ((data.get("run_weekday") if weekday is None else weekday) or "") if wanted == "weekly" else "",
                data.get("timezone") if timezone_name is None else timezone_name)
            stored = {key: str(data.get(key) or "") for key in schedule}
            # Saved as it stands (the panel's Save without a change): nothing
            # moves, an hourly Watch's next run is not pushed out by an hour.
            if schedule != stored:
                if schedule["interval"] not in allowed_intervals(tier):
                    raise AgentWatchError("interval_not_allowed", "Runs this often need a higher plan.", status=403)
                patch.update(schedule)
                if data.get("status") == STATUS_ACTIVE:
                    patch.update({"next_run_at": next_run(schedule, now=now), "retry_of": None})
        if patch:
            tx.update(_ref(db, watch_id), {**patch, "updated_at": now})
        return {**data, **patch}

    return serialize(watch_id, watch_service._run_transaction(db, operation))


def unsubscribe_token(watch_id: str) -> str:
    """The mail's "Stop emails" link (List-Unsubscribe): a token of its own kind."""
    return watch_service.sign_token_payload({"aw": watch_id})


def parse_unsubscribe_token(token: str) -> str:
    try:
        payload = watch_service.parse_token_payload(token)
    except watch_service.WatchError as exc:
        raise AgentWatchError(exc.code, exc.message, status=400) from None
    watch_id = payload.get("aw")
    if not isinstance(watch_id, str) or not watch_id.isalnum() or len(watch_id) > 64 or set(payload) - {"aw", "exp"}:
        raise AgentWatchError("invalid_token", "This link is invalid.", status=400)
    return watch_id


def watch_of(watch_id: str, *, db=None) -> dict | None:
    snapshot = _ref(_db(db), watch_id).get()
    return serialize(watch_id, snapshot.to_dict() or {}) if snapshot.exists else None


def stop_emails(watch_id: str, *, db=None, now: datetime | None = None) -> dict | None:
    """The mail link's one action: no more mails from this Watch, which keeps running."""
    db = _db(db)
    now = now or utcnow()
    ref = _ref(db, watch_id)

    def operation(tx):
        snapshot = ref.get(transaction=tx)
        if not snapshot.exists:
            return None
        data = snapshot.to_dict() or {}
        tx.update(ref, {"email_enabled": False, "updated_at": now})
        return {**data, "email_enabled": False}

    data = watch_service._run_transaction(db, operation)
    return serialize(watch_id, data) if data is not None else None


def list_for(uid: str, *, chat_id: str = "", db=None) -> list[dict]:
    db = _db(db)
    query = db.collection(COLLECTION).where(filter=FieldFilter("uid", "==", uid))
    items = [serialize(snapshot.id, snapshot.to_dict() or {}) for snapshot in query.stream()]
    if chat_id:
        items = [item for item in items if item["chat_id"] == chat_id]
    return sorted(items, key=lambda item: (item["status"] != STATUS_ACTIVE, item["next_run_at"] or ""))


def _drop_images(db, watch_ids) -> None:
    """A Watch's picture goes with it (``watch_images/{id}``)."""
    from app.services import watch_images
    for watch_id in watch_ids:
        db.collection(watch_images.WATCH_IMAGES_COLLECTION).document(watch_id).delete()
        watch_images.forget(watch_id)


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
    unrun = {}

    def operation(tx):
        snapshot = ref.get(transaction=tx)
        data = (snapshot.to_dict() or {}) if snapshot.exists else {}
        if data.get("uid") != uid:
            raise AgentWatchError("not_found", "This Watch no longer exists.", status=404)
        # Never claimed (claim counts runs): no run can start in its chat any more.
        unrun["ended"] = data.get("status") in {STATUS_ACTIVE, STATUS_PAUSED} and not int(data.get("runs") or 0)
        if data.get("status") in {STATUS_ACTIVE, STATUS_PAUSED}:
            _end(tx, db, watch_id, data, reason="user", now=now)
            data = {**data, "status": STATUS_DONE, "next_run_at": None, "ended": "user"}
        return data

    data = watch_service._run_transaction(db, operation)
    if unrun.get("ended") and not data.get("turn_id"):
        _drop_unused_chat(db, uid, str(data.get("chat_id") or ""))
    return serialize(watch_id, data)


def _drop_unused_chat(db, uid: str, chat_id: str) -> None:
    """The chat the Watches page opened for a Watch that ended before its
    first run: no message and no sidebar entry (the first run's answer writes
    it), so nobody could see or delete it, and it held one of the account's
    chats. It goes, and the Watch with it (chat_store._purge_chat), like a
    refused create leaves no chat behind."""
    from app.services.agent_runs import AgentRunStore
    store = AgentRunStore(db)
    try:
        if not chat_id or _bookmark_id(db, uid, chat_id):
            return
        if int(store.get_chat(uid, chat_id).get("turn_count") or 0):
            return
        store.delete_chat(uid, chat_id)
    except Exception as exc:
        logging.warning("Unused agent watch chat not removed category=%s", safe_exception(exc))


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
    _drop_images(db, ids)
    return len(ids)


def delete_for_account(db, uid: str) -> int:
    db = _db(db)
    ids = []
    for snapshot in db.collection(COLLECTION).where(filter=FieldFilter("uid", "==", uid)).stream():
        snapshot.reference.delete()
        ids.append(snapshot.id)
    _slots_ref(db, uid).delete()
    _drop_images(db, ids)
    _forget_in_days(db, uid)
    return len(ids)


def _forget_in_days(db, uid: str) -> None:
    """Takes ``uid`` out of the day counts still kept (DAYS_KEPT)."""
    for snapshot in db.collection(DAYS_COLLECTION).stream():
        if uid not in dict((snapshot.to_dict() or {}).get("accounts") or {}):
            continue

        def operation(tx, ref=snapshot.reference):
            day = ref.get(transaction=tx)
            accounts = dict(((day.to_dict() or {}) if day.exists else {}).get("accounts") or {})
            if accounts.pop(uid, None) is not None:
                tx.update(ref, {"accounts": accounts})
        watch_service._run_transaction(db, operation)


def purge_days(*, db=None, now: datetime | None = None) -> int:
    """Deletes the day counts older than DAYS_KEPT days; returns how many."""
    db = _db(db)
    now = now or utcnow()
    oldest = (now.date() - timedelta(days=DAYS_KEPT - 1)).isoformat()
    gone = 0
    for snapshot in _stream(db.collection(DAYS_COLLECTION)):
        if snapshot.id < oldest:
            snapshot.reference.delete()
            gone += 1
    return gone


_days_purged = None  # the date of this process's last purge_days


# --- the schedule's runs ---------------------------------------------------

ADMIN_LIST_LIMIT = 300


def list_all(*, db=None, limit: int = ADMIN_LIST_LIMIT) -> list[dict]:
    """Every account's Watches for the admin, running ones first by their
    next run, then paused, then ended: one read per Watch."""
    db = _db(db)
    watches = []
    for snapshot in db.collection(COLLECTION).limit(limit).stream():
        data = snapshot.to_dict() or {}
        watches.append({**serialize(snapshot.id, data), "uid": str(data.get("uid") or "")})
    order = {STATUS_ACTIVE: 0, STATUS_PAUSED: 1}
    watches.sort(key=lambda watch: (order.get(watch["status"], 2), watch["next_run_at"] or "~"))
    return watches


def _stream(query):
    """The scheduler's reads: no retries and a short deadline, so a slow
    Firestore costs one tick, not a retry series (watch_service.earliest_next_run_at)."""
    try:
        return query.stream(retry=None, timeout=3.0)
    except TypeError:  # lightweight test doubles
        return query.stream()


def _waited_since(data: dict) -> datetime:
    """When a Watch last ran (one that never did: the earliest)."""
    last = data.get("last_run") if isinstance(data.get("last_run"), dict) else {}
    at = last.get("at")
    return at if isinstance(at, datetime) else datetime.min.replace(tzinfo=timezone.utc)


def due(*, now: datetime | None = None, db=None, max_items: int = DUE_BATCH) -> list[tuple[str, str]]:
    """(watch id, uid) of the Watches whose time has come, the oldest first.
    Watches due at the same time (the default 08:00) go by how long they have
    waited: when the morning's capacity ends before LATE_AFTER, another one is
    skipped each day, not always the same."""
    db = _db(db)
    now = now or utcnow()
    query = (db.collection(COLLECTION).where(filter=FieldFilter("next_run_at", "<=", now))
             .order_by("next_run_at").limit(max_items))
    found = [(snapshot.id, snapshot.to_dict() or {}) for snapshot in _stream(query)]
    found.sort(key=lambda item: (item[1].get("next_run_at") if isinstance(item[1].get("next_run_at"), datetime)
                                 else now, _waited_since(item[1])))
    return [(watch_id, str(data.get("uid") or "")) for watch_id, data in found]


def earliest_next_run_at(*, db=None) -> datetime | None:
    """When the next run is due, for the scheduler's sleep (an ended Watch has none)."""
    db = _db(db)
    query = (db.collection(COLLECTION).where(filter=FieldFilter("next_run_at", "<=", datetime.max.replace(tzinfo=timezone.utc)))
             .order_by("next_run_at").limit(1))
    for snapshot in _stream(query):
        value = (snapshot.to_dict() or {}).get("next_run_at")
        return value if isinstance(value, datetime) else None
    return None


def _day_ref(db, now: datetime):
    return db.collection(DAYS_COLLECTION).document(now.date().isoformat())


def claim(watch_id: str, *, now: datetime | None = None, db=None, tier=None) -> tuple[dict | None, str]:
    """Takes one due run: the Watch moves on to its next time and notes the
    run as running, under the daily caps (the server's, the account's).
    Returns (run, "") or (None, reason): "not_due", "running", "late"
    (skipped), "budget" (the server's cap), "account_budget".

    A retry (``retry_of``, _retry_soon) is the run of its first time: late
    and the following time count from that, so retries end and never shift
    the schedule. ``tier``: a Watch whose interval the account's plan no
    longer allows runs at the shortest one it does from here on."""
    db = _db(db)
    now = now or utcnow()
    ref = _ref(db, watch_id)
    day_ref = _day_ref(db, now)
    cap, account_cap = cfg.get_agent_watch_max_runs_per_day(), cfg.get_agent_watch_max_runs_per_account_day()

    def operation(tx):
        snapshot, day = ref.get(transaction=tx), day_ref.get(transaction=tx)
        data = (snapshot.to_dict() or {}) if snapshot.exists else {}
        attempt = data.get("next_run_at")
        if data.get("status") != STATUS_ACTIVE or not isinstance(attempt, datetime) or attempt > now:
            return None, "not_due"
        running = data.get("running") if isinstance(data.get("running"), dict) else None
        if running and isinstance(running.get("started_at"), datetime) and now - running["started_at"] < RUN_STALE_AFTER:
            return None, "running"
        scheduled = data.get("retry_of") if isinstance(data.get("retry_of"), datetime) else attempt
        schedule = {key: data.get(key) for key in ("interval", "run_time", "run_weekday", "timezone")}
        if tier is not None and schedule["interval"] not in allowed_intervals(tier):
            schedule = validate_schedule(fit_interval(schedule["interval"], tier), schedule["run_time"],
                                         schedule["run_weekday"], schedule["timezone"])
        following = next_run(schedule, now=now, previous=scheduled)
        if now - scheduled > LATE_AFTER:
            tx.update(ref, {**schedule, "next_run_at": following, "retry_of": None, "last_skipped_at": now,
                            "updated_at": now})
            return None, "late"
        uid = str(data.get("uid") or "")
        day_data = (day.to_dict() or {}) if day.exists else {}
        accounts = dict(day_data.get("accounts") or {})
        runs_today, account_runs = int(day_data.get("runs") or 0), int(accounts.get(uid) or 0)
        if runs_today >= cap:
            return None, "budget"
        if account_runs >= account_cap:
            return None, "account_budget"
        # Each attempt its own request: a refused one may have left its turn.
        request_id = f"watch.{watch_id[:16]}.{int(attempt.timestamp())}"
        tx.update(ref, {**schedule, "next_run_at": following, "retry_of": None,
                        "running": {"request_id": request_id, "started_at": now, "scheduled_at": scheduled},
                        "runs": int(data.get("runs") or 0) + 1, "updated_at": now})
        tx.set(day_ref, {"runs": runs_today + 1, "accounts": {**accounts, uid: account_runs + 1}, "updated_at": now})
        return {**data, **schedule, "id": watch_id, "request_id": request_id, "scheduled_at": scheduled}, ""

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
        from app.services.user_settings import FirestoreUserSettingsRepository
        values, _, _ = FirestoreUserSettingsRepository(db).get(uid)
        value = values.get("reviewers")
    except Exception as exc:
        logging.info("Agent watch reviewers setting unreadable category=%s", safe_exception(exc))
        value = None
    return value if value in {"always", "workspace", "off"} else "always"


def _retry_soon(watch_id: str, run: dict, *, db, now: datetime) -> None:
    """The chat was busy: the run comes again shortly, within the lateness
    of its first time (``retry_of``). A run that did not start counts for
    no cap and no run."""
    scheduled = run.get("scheduled_at")
    retry = now + BUSY_RETRY
    ref = _ref(db, watch_id)
    day_ref = _day_ref(db, run.get("claimed_at") if isinstance(run.get("claimed_at"), datetime) else now)

    def operation(tx):
        snapshot, day = ref.get(transaction=tx), day_ref.get(transaction=tx)
        data = (snapshot.to_dict() or {}) if snapshot.exists else {}
        if data.get("uid") and day.exists:
            day_data = day.to_dict() or {}
            accounts = dict(day_data.get("accounts") or {})
            uid = data["uid"]
            accounts[uid] = max(0, int(accounts.get(uid) or 0) - 1)
            tx.set(day_ref, {"runs": max(0, int(day_data.get("runs") or 0) - 1), "accounts": accounts,
                             "updated_at": now})
        if not data:
            return
        patch = {"running": None, "runs": max(0, int(data.get("runs") or 0) - 1), "updated_at": now}
        following = data.get("next_run_at")
        if (data.get("status") == STATUS_ACTIVE and isinstance(scheduled, datetime)
                and retry - scheduled <= LATE_AFTER
                and not (isinstance(following, datetime) and following <= retry)):
            # Before the schedule's next time: the same run once more.
            patch["next_run_at"], patch["retry_of"] = retry, scheduled
        tx.update(ref, patch)

    watch_service._run_transaction(db, operation)


# Refusals that end the Watch: its chat is gone, or it can no longer run
# there (a chat that took in Google information, a refusal that would only
# repeat). The page says which (watch-dashboard.js lineOf).
_ENDING = frozenset({"chat_gone", "google_data", "cannot_run"})


def _not_started(watch_id: str, outcome: str, *, db, now: datetime) -> None:
    """The run did not start; a Watch that cannot run any more ends, unread,
    so its page shows why."""
    ref = _ref(db, watch_id)

    def operation(tx):
        snapshot = ref.get(transaction=tx)
        if not snapshot.exists:
            return
        data = snapshot.to_dict() or {}
        patch = {"running": None, "updated_at": now,
                 "last_run": {"at": now, "turn_id": "", "outcome": outcome, "summary": ""}}
        if outcome != "already_ran":
            # A run that ran already is no look of its own.
            patch["looks"] = _with_look(data, _look(outcome, now))
        if outcome in _ENDING and data.get("status") in {STATUS_ACTIVE, STATUS_PAUSED}:
            _end(tx, db, watch_id, data, reason=outcome, now=now)
            patch["unread"] = outcome != "chat_gone"
        tx.update(ref, patch)

    watch_service._run_transaction(db, operation)


# Refusals a little later may not repeat: the chat busy with another
# message (409), the server's capacity or a provider's cooldown (503, 429).
_TRANSIENT = frozenset({409, 429, 503})


def _refused(watch_id: str, run: dict, status: int, *, db, now: datetime) -> None:
    logging.info("Agent watch run not started status=%s", status)
    if status in _TRANSIENT:
        _retry_soon(watch_id, run, db=db, now=now)
    elif status == 404:
        _not_started(watch_id, "chat_gone", db=db, now=now)
    elif status in {403, 422}:
        _not_started(watch_id, "google_data" if _chat_has_google_data(run, db) else "cannot_run", db=db, now=now)
    else:
        _not_started(watch_id, "not_started", db=db, now=now)


def _chat_has_google_data(run: dict, db) -> bool:
    from app.services.agent_runs import AgentRunStore
    try:
        chat = AgentRunStore(db)._chat_ref(run["uid"], run["chat_id"]).get()
        return bool(chat.exists and (chat.to_dict() or {}).get("google_data"))
    except Exception:
        return False


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
    global _days_purged
    if _days_purged != now.date():
        _days_purged = now.date()
        try:
            await asyncio.to_thread(purge_days, db=db, now=now)
        except Exception as exc:
            logging.warning("Agent watch day purge failed category=%s", safe_exception(exc))
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
            tier = await asyncio.to_thread(_tier_of, uid)
            run, reason = await asyncio.to_thread(claim, watch_id, now=clock(), db=db, tier=tier)
        except Exception as exc:
            logging.warning("Agent watch claim failed category=%s", safe_exception(exc))
            continue
        if reason == "budget":
            logging.warning("Agent watch runs per day reached")
            break
        if reason == "account_budget":
            logging.warning("Agent watch runs per account and day reached")
            continue
        if run is None:
            continue
        try:
            started += int(await asyncio.to_thread(start_run, {**run, "claimed_at": clock()}, db=db, now=clock()))
        except Exception as exc:
            # A failure noting a refusal never takes the scheduler loop down.
            _forget(watch_id)
            logging.warning("Agent watch start failed category=%s", safe_exception(exc))
    return started


def _tier_of(uid: str):
    from app.core.security import get_user_tier
    try:
        return get_user_tier(uid)
    except Exception as exc:
        logging.info("Agent watch tier unreadable category=%s", safe_exception(exc))
        return None


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
    the run, ends when the goal is met, marks a finding, a question for the
    user or the goal unread and stages its messages (mail and Telegram, as
    the Watch has them on). A Watch without a picture looks for one in the
    pages of the run (PICTURES). Returns the outcome."""
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
    tells = outcome in {"finding", "needs_you", "done"}
    evidence_url = str(details.get("evidence_url") or "")[:URL_MAX_CHARS]

    def operation(tx):
        snapshot = ref.get(transaction=tx)
        data = (snapshot.to_dict() or {}) if snapshot.exists else {}
        if data.get("uid") != uid:
            return None
        running = data.get("running") if isinstance(data.get("running"), dict) else {}
        ends = details.get("done") is not None and data.get("status") in {STATUS_ACTIVE, STATUS_PAUSED}
        # Paused or ended by the user while this run went on: its finding
        # waits in the chat, no message follows; reaching the goal still tells.
        withdrawn = not ends and (data.get("status") == STATUS_PAUSED
                                  or (data.get("status") == STATUS_DONE and data.get("ended") == "user"))
        if ends:
            _end(tx, db, watch_id, data, reason="goal", now=now)
        patch = {"last_run": {"at": now, "turn_id": turn_id, "outcome": outcome,
                              "summary": _line(details.get("summary"), FINDING_MAX_CHARS),
                              "evidence_url": evidence_url},
                 "looks": _with_look(data, _look(outcome, now, details.get("summary") if tells else "")),
                 "updated_at": now}
        if tells:
            patch["unread"] = True
        if running.get("request_id") == watch_run.get("request_id"):
            patch["running"] = None
        tx.update(ref, patch)
        if not tells or withdrawn:
            return data, []
        payload = {
            "outcome": outcome, "task": data.get("task") or "", "goal": data.get("goal") or "",
            "summary": _line(details.get("summary"), FINDING_MAX_CHARS), "evidence_url": evidence_url,
            "evidence_title": _line(details.get("evidence_title"), 240), "halted": bool(details.get("halted")),
            "goal_met": bool(details.get("done")),
            "goal_reason": _line((details.get("done") or {}).get("reason"), REASON_MAX_CHARS),
            "review": _review_line(turn), "bookmark_id": data.get("bookmark_id") or ""}
        channels = outbox.watch_channels(data, defaults=outbox.AGENT_WATCH_CHANNEL_DEFAULTS)
        items = [outbox.agent_watch_item(uid=uid, watch_id=watch_id, run_id=turn_id, now=now,
                                         payload=payload, channel=channel) for channel in channels]
        for item in items:
            outbox.stage(tx, db, item)
        return data, [item["id"] for item in items]

    try:
        result = watch_service._run_transaction(db, operation)
    except Exception as exc:
        logging.warning("Agent watch run end not recorded category=%s", safe_exception(exc))
        result = None
    finally:
        _forget(watch_id)
    logging.info("Agent watch run ended outcome=%s", outcome)
    if result is None:
        return outcome
    data, _staged = result
    from app.services import watch_scheduler
    # The messages go out on the scheduler's next pass, which this wakes; a
    # run that waited for this one's room starts there too.
    watch_scheduler.wake_watch_scheduler()
    if outcome != "failed":
        sources = [*([{"url": evidence_url, "title": details.get("evidence_title") or ""}] if evidence_url else []),
                   *(turn.get("sources") or [])]
        PICTURES.look(watch_id, data, sources, db=db)
    return outcome


class Pictures:
    """A Watch's picture (watch_images.py): a real
    photo of what it is about, never generated; without one, the page draws
    the eye. Looked for on a thread of its own:

    * at its start (Max: "beim ersten Anlegen direkt ein
      passendes Bild"): a cheap model names what it is about in a few words
      (watch_scheduler.picture_words), Brave's image search finds the photo
      (picture_search); without one, the pages of the chat it starts in;
    * after a run, while it has none: the pages that run opened, the
      evidence first.

    MAX_LOOKS looks in all, then the eye stays. Off in tests and under
    MOCK_LLM (watch_images.background_enabled)."""

    MAX_LOOKS = 3
    # Brave's first pictures for the words; the rest are rarely better.
    SUBJECT_RESULTS = 4
    WORDS_CHARS = 80

    def __init__(self):
        from concurrent.futures import ThreadPoolExecutor
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="agent-watch-picture")

    def wanted(self, data: dict) -> bool:
        image = data.get("image") if isinstance(data.get("image"), dict) else {}
        return image.get("status") != "ready" and int(image.get("tries") or 0) < self.MAX_LOOKS

    def look(self, watch_id: str, data: dict, sources, *, db=None) -> bool:
        from app.services import watch_images
        if not self.wanted(data) or not watch_images.background_enabled():
            return False
        if not [source for source in sources if isinstance(source, dict) and source.get("url")]:
            return False
        self.pool.submit(self.find, watch_id, data.get("task") or "", data.get("goal") or "", list(sources), db)
        return True

    def first(self, watch_id: str, data: dict, *, db=None) -> bool:
        from app.services import watch_images
        if not self.wanted(data) or not watch_images.background_enabled():
            return False
        self.pool.submit(self.find_first, watch_id, dict(data), db)
        return True

    def find_first(self, watch_id: str, data: dict, db=None, *, words=None, search=None,
                   fetch=None) -> str:
        """The picture at the start: of the subject first, else of the chat's
        pages. ``words``, ``search`` and ``fetch`` stand in for the model, Brave
        and the network in tests."""
        from app.services import watch_images
        db = _db(db)
        task, goal = data.get("task") or "", data.get("goal") or ""
        try:
            found = self.subject(task, goal, words=words, search=search, fetch=fetch)
        except Exception as exc:
            logging.info("Agent watch subject picture failed category=%s", safe_exception(exc))
            found = None
        if not found:
            sources = self.chat_sources(db, data)
            if sources:
                try:
                    found = watch_images.find_image(sources, task, goal, fetch=fetch)
                except Exception as exc:
                    logging.info("Agent watch picture search failed category=%s", safe_exception(exc))
        return self.store(watch_id, found, db=db)

    def subject(self, task: str, goal: str, *, words=None, search=None, fetch=None) -> dict | None:
        """A photo of what the Watch is about: the words a model names for it,
        Brave's pictures for those, the first that makes a thumbnail (Brave's
        copy first: it loads where the original page refuses strangers)."""
        from urllib.parse import urlsplit
        from app.services import picture_search, watch_images
        if search is None:
            if not picture_search.enabled():
                return None
            search = picture_search.search
        if words is None:
            from app.services import watch_scheduler
            words = watch_scheduler.picture_words
        query = _line(words(task, goal), self.WORDS_CHARS)
        if not query:
            return None
        results = search(query, self.SUBJECT_RESULTS) or []
        fetch = fetch or watch_images._http_fetch

        async def first():
            for result in results[:self.SUBJECT_RESULTS]:
                url = result.get("thumbnail") or result.get("picture")
                if not url:
                    continue
                try:
                    _url, content, _kind, truncated = await asyncio.wait_for(
                        fetch(url, "image"), watch_images.FETCH_SECONDS + 1)
                except Exception as exc:
                    logging.info("Agent watch picture fetch skipped category=%s", safe_exception(exc))
                    continue
                if truncated:
                    continue
                thumbnail = await asyncio.to_thread(watch_images.make_thumbnail, content)
                if thumbnail:
                    stored, (width, height) = thumbnail
                    page = str(result.get("page") or "")
                    return {"content": stored, "content_type": "image/webp", "kind": "item",
                            "width": int(width), "height": int(height), "source_url": page,
                            "source_host": (urlsplit(page).hostname or "").lower().removeprefix("www.")}
            return None

        return asyncio.run(first())

    @staticmethod
    def chat_sources(db, data: dict) -> list:
        """The pages of the turn the Watch was prepared on, else of the chat's
        newest turn (the Watch pill sits under it); a page-made chat has none."""
        from app.services.agent_runs import AgentRunStore
        from firebase_admin import firestore
        store = AgentRunStore(db)
        uid, chat_id, turn_id = data.get("uid") or "", data.get("chat_id") or "", data.get("turn_id") or ""
        if not (uid and chat_id):
            return []
        try:
            if turn_id:
                snapshot = store._turn_ref(uid, chat_id, turn_id).get()
                turn = (snapshot.to_dict() or {}) if snapshot.exists else {}
            else:
                newest = list(store._chat_ref(uid, chat_id).collection("turns")
                              .order_by("position", direction=firestore.Query.DESCENDING).limit(1).stream())
                turn = (newest[0].to_dict() or {}) if newest else {}
        except Exception as exc:
            logging.info("Agent watch picture sources unread category=%s", safe_exception(exc))
            return []
        return [source for source in turn.get("sources") or [] if isinstance(source, dict) and source.get("url")]

    def find(self, watch_id: str, task: str, goal: str, sources, db=None) -> str:
        from app.services import watch_images
        db = _db(db)
        try:
            found = watch_images.find_image(sources, task, goal)
        except Exception as exc:
            logging.info("Agent watch picture search failed category=%s", safe_exception(exc))
            found = None
        return self.store(watch_id, found, db=db)

    def store(self, watch_id: str, found: dict | None, *, db, now: datetime | None = None) -> str:
        """The picture and the Watch's ``image`` in one transaction: a Watch
        deleted meanwhile gets none, a found picture is never replaced."""
        import hashlib
        from app.services import watch_images
        now = now or utcnow()
        ref = _ref(db, watch_id)
        image_ref = db.collection(watch_images.WATCH_IMAGES_COLLECTION).document(watch_id)

        def operation(tx):
            snapshot = ref.get(transaction=tx)
            data = (snapshot.to_dict() or {}) if snapshot.exists else {}
            if not data.get("uid") or not self.wanted(data):
                return "kept"
            previous = data.get("image") if isinstance(data.get("image"), dict) else {}
            tries = int(previous.get("tries") or 0) + 1
            if not found:
                tx.update(ref, {"image": {"status": "none", "tries": tries, "last_attempt_at": now}})
                return "none"
            token = hashlib.sha256(found["content"]).hexdigest()[:20]
            tx.set(image_ref, {"owner_uid": data["uid"], "token": token, "content": found["content"],
                               "content_type": found["content_type"], "width": found["width"],
                               "height": found["height"], "created_at": now})
            tx.update(ref, {"image": {
                "status": "ready", "kind": found.get("kind") if found.get("kind") in {"item", "article", "logo"} else "item",
                "token": token, "width": found["width"], "height": found["height"],
                "source_url": str(found.get("source_url") or "")[:2000],
                "source_host": str(found.get("source_host") or "")[:120], "tries": tries, "picked_at": now}})
            return "ready"

        try:
            outcome = watch_service._run_transaction(db, operation)
        except Exception as exc:
            logging.info("Agent watch picture not saved category=%s", safe_exception(exc))
            return "failed"
        if outcome == "ready":
            watch_images.forget(watch_id)
        return outcome


PICTURES = Pictures()
