"""Durable notification outbox: at-least-once delivery with bounded retries.

Every user-facing notification (Watch owner mail/Telegram, the paused-after-
three-failures notice, Watch page followers, Topic followers and the Morning
Brief) is first written as one document in ``notification_outbox``. Watch
results and the Brief claim stage their items inside the same Firestore
transaction that commits the result/advances the schedule, so a process that
dies after the commit can no longer lose the notification.

State machine of one item (document id = stable delivery id)::

    pending --claim--> pending (lease: next_attempt_at = now + lease,
                                attempts += 1, lease_owner = token)
            --finish(sent)----> sent      (terminal)
            --finish(skipped)-> skipped   (terminal: unsubscribed, paused,
                                           unverified, channel disabled, ...)
            --finish(failed)--> failed    (terminal: permanent rejection)
            --finish(retry)---> pending   (next_attempt_at = backoff)

A crash between claim and finish leaves the item ``pending`` with its lease
as ``next_attempt_at``; the next retry pass picks it up after the lease.
After ``MAX_ATTEMPTS`` or after ``deliver_until`` the item turns ``failed``.

Guarantee: at-least-once per delivery id, not exactly-once. SMTP acceptance
is not inbox delivery, and a crash after the provider accepted a message but
before ``finish`` produces one duplicate. Every attempt re-checks the current
subscription state (see ``notification_delivery``), so unsubscribed, paused
or deleted recipients never receive a late retry.

This module is deliberately free of mailer/Telegram/auth imports so the
Watch, Brief and Topic persistence layers can stage items without cycles.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from google.api_core.exceptions import FailedPrecondition
from google.cloud.firestore_v1.base_query import FieldFilter

from app.core.observability import record_metric
from app.core.security import db_firestore
from app.services import persistence_guard


OUTBOX_COLLECTION = "notification_outbox"
SCHEMA_VERSION = 1

KIND_WATCH_ALERT = "watch_alert"
KIND_WATCH_PAUSED = "watch_paused"
KIND_WATCH_FOLLOWER = "watch_follower"
KIND_TOPIC_FOLLOWER = "topic_follower"
KIND_WATCH_BRIEF = "watch_brief"
KINDS = {
    KIND_WATCH_ALERT, KIND_WATCH_PAUSED, KIND_WATCH_FOLLOWER,
    KIND_TOPIC_FOLLOWER, KIND_WATCH_BRIEF,
}
CHANNEL_EMAIL = "email"
CHANNEL_TELEGRAM = "telegram"

STATUS_PENDING = "pending"
SENT = "sent"
SKIPPED = "skipped"
FAILED = "failed"
RETRY = "retry"
TERMINAL_STATUSES = {SENT, SKIPPED, FAILED}

MAX_ATTEMPTS = 8
LEASE_MINUTES = 10
RETRY_BASE_MINUTES = 15
RETRY_MAX_MINUTES = 6 * 60
DEFAULT_DELIVER_WITHIN = timedelta(days=3)
# A Morning Brief that is half a day late is noise, and the next scheduled
# Brief already covers the same period.
BRIEF_DELIVER_WITHIN = timedelta(hours=12)
RETENTION_DAYS = 30
TEXT_LIMIT = 400
QUESTION_LIMIT = 2_000


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def delivery_id(kind: str, resource_id: str, run_id: str, channel: str,
                recipient_id: str) -> str:
    """Stable id: the same notification can only ever exist once."""
    raw = "\0".join(
        str(part or "") for part in (kind, resource_id, run_id, channel, recipient_id)
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _clip(value, limit: int = TEXT_LIMIT) -> str:
    return str(value or "")[:limit]


def _score(value):
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _direction(value) -> dict:
    """Only the two fields mail/Telegram render; never the full position map."""
    if not isinstance(value, dict):
        return {}
    label = _clip(value.get("shift_label") or value.get("label"), 80)
    if not label:
        return {}
    shift = value.get("shift_score")
    return {
        "shift_label": label,
        "shift_score": shift if isinstance(shift, (int, float)) else None,
    }


def new_item(*, kind: str, channel: str, resource_id: str, run_id: str,
             recipient_id: str, payload: dict, now: datetime, uid: str = "",
             deliver_within: Optional[timedelta] = None) -> dict:
    if kind not in KINDS or channel not in {CHANNEL_EMAIL, CHANNEL_TELEGRAM}:
        raise ValueError("invalid notification kind or channel")
    return {
        "id": delivery_id(kind, resource_id, run_id, channel, recipient_id),
        "data": {
            "schema_version": SCHEMA_VERSION,
            "kind": kind,
            "channel": channel,
            # Owner uid for account-deletion cleanup; empty for Topic items.
            "uid": str(uid or ""),
            "resource_id": str(resource_id or ""),
            "run_id": str(run_id or ""),
            "recipient_id": str(recipient_id or ""),
            "payload": dict(payload or {}),
            "status": STATUS_PENDING,
            "attempts": 0,
            "next_attempt_at": now,
            "deliver_until": now + (deliver_within or DEFAULT_DELIVER_WITHIN),
            "lease_owner": "",
            "last_error": "",
            "created_at": now,
            "updated_at": now,
        },
    }


# ---------------------------------------------------------------------------
# Item builders. The payload carries only what the message builders render;
# long consensus text is read from the immutable Watch version at send time.
# ---------------------------------------------------------------------------

def _watch_view(claimed: dict) -> dict:
    return {
        "share_id": str(claimed.get("share_id") or ""),
        "share_slug": _clip(claimed.get("share_slug"), 200),
        "visibility": "private" if claimed.get("visibility") == "private" else "public",
        "question": _clip(claimed.get("question"), QUESTION_LIMIT),
    }


def _result_view(claimed: dict, result: dict) -> dict:
    return {
        "old_score": _score(claimed.get("last_agreement_score")),
        "agreement_score": _score(result.get("agreement_score")),
        "changed": bool(result.get("changed")),
        "severity": _clip(result.get("severity") or "minor", 10),
        "change_summary": _clip(result.get("change_summary")),
        "direction": _direction(result.get("opinion_map")),
    }


def watch_alert_items(watch_id: str, claimed: dict, result: dict, alert: str, *,
                      now: datetime, email: bool) -> list[dict]:
    """Owner alert items for one successful run (``alert`` = change|every_run|condition)."""
    uid = str(claimed.get("owner_uid") or "")
    run_id = str(claimed.get("current_run_id") or "")
    if not alert or not uid or not run_id:
        return []
    payload = {
        **_watch_view(claimed),
        **_result_view(claimed, result),
        "alert": alert,
    }
    if alert == "condition":
        payload["condition"] = _clip(claimed.get("condition"), 500)
        payload["condition_reason"] = _clip(result.get("condition_reason"), 800)
    items = []
    if email and claimed.get("email_enabled") is not False:
        items.append(new_item(
            kind=KIND_WATCH_ALERT, channel=CHANNEL_EMAIL, resource_id=watch_id,
            run_id=run_id, recipient_id=uid, uid=uid, payload=payload, now=now,
        ))
    if claimed.get("telegram_enabled") is True:
        items.append(new_item(
            kind=KIND_WATCH_ALERT, channel=CHANNEL_TELEGRAM, resource_id=watch_id,
            run_id=run_id, recipient_id=uid, uid=uid, payload=payload, now=now,
        ))
    return items


def watch_paused_items(watch_id: str, claimed: dict, *, now: datetime,
                       email: bool) -> list[dict]:
    uid = str(claimed.get("owner_uid") or "")
    run_id = str(claimed.get("current_run_id") or "")
    if not uid or not run_id:
        return []
    payload = {**_watch_view(claimed), "alert": "paused_error"}
    items = []
    if email and claimed.get("email_enabled") is not False:
        items.append(new_item(
            kind=KIND_WATCH_PAUSED, channel=CHANNEL_EMAIL, resource_id=watch_id,
            run_id=run_id, recipient_id=uid, uid=uid, payload=payload, now=now,
        ))
    if claimed.get("telegram_enabled") is True:
        items.append(new_item(
            kind=KIND_WATCH_PAUSED, channel=CHANNEL_TELEGRAM, resource_id=watch_id,
            run_id=run_id, recipient_id=uid, uid=uid, payload=payload, now=now,
        ))
    return items


def watch_follower_items(watch_id: str, claimed: dict, result: dict,
                         follower_ids, *, now: datetime) -> list[dict]:
    run_id = str(claimed.get("current_run_id") or "")
    if not run_id or claimed.get("visibility") == "private":
        return []
    payload = {**_watch_view(claimed), **_result_view(claimed, result)}
    return [
        new_item(
            kind=KIND_WATCH_FOLLOWER, channel=CHANNEL_EMAIL, resource_id=watch_id,
            run_id=run_id, recipient_id=str(follower_id),
            uid=str(claimed.get("owner_uid") or ""), payload=payload, now=now,
        )
        for follower_id in dict.fromkeys(str(value) for value in follower_ids or [] if value)
    ]


def topic_follower_items(topic: dict, run_id: str, run: dict, old_score,
                         follower_ids, *, now: datetime) -> list[dict]:
    topic_id = str(topic.get("id") or "")
    if not topic_id or not run_id:
        return []
    payload = {
        "title": _clip(topic.get("title"), 240),
        "question": _clip(topic.get("lead_question"), QUESTION_LIMIT),
        "slug": _clip(topic.get("slug"), 200),
        "old_score": _score(old_score),
        "new_score": _score(run.get("agreement_score")),
        "change_type": _clip(run.get("change_type"), 10),
        "summary": _clip(run.get("change_summary"), 1200),
    }
    return [
        new_item(
            kind=KIND_TOPIC_FOLLOWER, channel=CHANNEL_EMAIL, resource_id=topic_id,
            run_id=run_id, recipient_id=str(follower_id), payload=payload, now=now,
        )
        for follower_id in dict.fromkeys(str(value) for value in follower_ids or [] if value)
    ]


def brief_item(uid: str, *, scheduled_at: datetime, baseline: datetime,
               mode: str, timezone_name: str, now: datetime) -> dict:
    return new_item(
        kind=KIND_WATCH_BRIEF, channel=CHANNEL_EMAIL, resource_id=uid,
        run_id=scheduled_at.isoformat(), recipient_id=uid, uid=uid,
        payload={
            "scheduled_at": scheduled_at,
            "baseline": baseline,
            "mode": _clip(mode, 20),
            "timezone": _clip(timezone_name, 64),
        },
        now=now, deliver_within=BRIEF_DELIVER_WITHIN,
    )


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def _ref(db, item_id: str):
    return db.collection(OUTBOX_COLLECTION).document(item_id)


def stage(transaction, db, item: dict) -> None:
    """Write one item inside the caller's result transaction.

    Callers stage only on the transition that is committed exactly once per
    run/slot (the fenced Watch completion, the Brief claim, a new Topic run),
    so a set cannot resurrect an already delivered id.
    """
    transaction.set(_ref(db, item["id"]), item["data"])


class StagedIds:
    """Wrap an item builder and remember the ids of its latest invocation.

    Firestore may retry a transaction body; only the last invocation's items
    are the committed ones, so ``ids`` is replaced on every call.
    """

    def __init__(self, builder):
        self._builder = builder
        self.ids: list[str] = []

    def __call__(self, *args) -> list[dict]:
        items = list(self._builder(*args) or [])
        self.ids = [item["id"] for item in items]
        return items


def _run_transaction(db, operation):
    from app.services import watch_service

    return watch_service._run_transaction(db, operation)


def list_due_ids(*, now=None, db=None, max_items: int = 50) -> list[str]:
    db = db if db is not None else db_firestore
    now = now or utcnow()
    collection = db.collection(OUTBOX_COLLECTION)
    try:
        query = (
            collection
            .where(filter=FieldFilter("status", "==", STATUS_PENDING))
            .where(filter=FieldFilter("next_attempt_at", "<=", now))
        )
    except TypeError:
        query = None
    if query is None or not hasattr(query, "order_by"):
        # Minimal fakes: filter in memory with the same semantics.
        docs = [
            doc for doc in collection.stream()
            if (doc.to_dict() or {}).get("status") == STATUS_PENDING
            and isinstance((doc.to_dict() or {}).get("next_attempt_at"), datetime)
            and (doc.to_dict() or {})["next_attempt_at"] <= now
        ]
        docs.sort(key=lambda doc: (doc.to_dict() or {})["next_attempt_at"])
        return [doc.id for doc in docs[:max_items]]
    limit = max(1, min(200, int(max_items)))
    try:
        return [doc.id for doc in query.order_by("next_attempt_at").limit(limit).stream()]
    except FailedPrecondition:
        # Composite (status, next_attempt_at) index not deployed yet: use the
        # automatic single-field index on status and order a bounded window
        # here, so retries keep working during the index build.
        logging.warning("Notification outbox index missing; ordering in memory")
        window = collection.where(filter=FieldFilter("status", "==", STATUS_PENDING)).limit(1000).stream()
        due = []
        for doc in window:
            at = (doc.to_dict() or {}).get("next_attempt_at")
            if isinstance(at, datetime) and at <= now:
                due.append((at, doc.id))
        due.sort()
        return [doc_id for _, doc_id in due[:limit]]


def _terminal_update(status: str, now: datetime, error: str = "") -> dict:
    update = {
        "status": status,
        "lease_owner": "",
        "next_attempt_at": None,
        "updated_at": now,
        "last_error": _clip(error, 80),
    }
    if status == SENT:
        update["sent_at"] = now
    return update


def _record_terminal(data: dict, status: str, error: str = "") -> None:
    kind = str((data or {}).get("kind") or "unknown")
    if status == FAILED:
        record_metric("notification", kind, outcome="failure")
        logging.warning(
            "Notification delivery failed permanently kind=%s channel=%s reason=%s",
            kind, str((data or {}).get("channel") or ""), _clip(error, 80),
        )
    else:
        record_metric("notification", kind, processed=int(status == SENT))


def claim(item_id: str, *, now=None, db=None) -> Optional[dict]:
    """Lease one due item for a single delivery attempt, or return None."""
    db = db if db is not None else db_firestore
    now = now or utcnow()
    ref = _ref(db, item_id)
    terminal = {}

    def operation(transaction):
        snapshot = ref.get(transaction=transaction)
        data = snapshot.to_dict() if snapshot.exists else None
        if not data or data.get("status") != STATUS_PENDING:
            return None
        due = data.get("next_attempt_at")
        if isinstance(due, datetime) and due > now:
            return None
        attempts = data.get("attempts")
        attempts = attempts if isinstance(attempts, int) and attempts >= 0 else 0
        deliver_until = data.get("deliver_until")
        if attempts >= MAX_ATTEMPTS or (
            isinstance(deliver_until, datetime) and deliver_until <= now
        ):
            reason = "attempts_exhausted" if attempts >= MAX_ATTEMPTS else "expired"
            transaction.update(ref, _terminal_update(FAILED, now, reason))
            terminal.update(data=data, status=FAILED, error=reason)
            return None
        uid = str(data.get("uid") or "")
        if uid:
            try:
                persistence_guard.ensure_account_write_allowed(
                    uid=uid, db=db, transaction=transaction, now=now,
                )
            except persistence_guard.AccountDeletionInProgress:
                transaction.update(ref, _terminal_update(SKIPPED, now, "account_deleted"))
                terminal.update(data=data, status=SKIPPED, error="account_deleted")
                return None
        lease_owner = secrets.token_hex(12)
        transaction.update(ref, {
            "attempts": attempts + 1,
            "next_attempt_at": now + timedelta(minutes=LEASE_MINUTES),
            "lease_owner": lease_owner,
            "last_attempt_at": now,
            "updated_at": now,
        })
        return {
            **data,
            "id": item_id,
            "attempts": attempts + 1,
            "lease_owner": lease_owner,
        }

    claimed = _run_transaction(db, operation)
    if terminal:
        _record_terminal(terminal["data"], terminal["status"], terminal["error"])
    return claimed


def retry_delay(attempts: int) -> timedelta:
    minutes = RETRY_BASE_MINUTES * (2 ** max(0, int(attempts) - 1))
    return timedelta(minutes=min(RETRY_MAX_MINUTES, minutes))


def finish(item_id: str, lease_owner: str, outcome: str, *, now=None, db=None,
           error: str = "") -> bool:
    """Record one attempt's outcome while the caller still owns the lease."""
    db = db if db is not None else db_firestore
    now = now or utcnow()
    ref = _ref(db, item_id)
    terminal = {}

    def operation(transaction):
        snapshot = ref.get(transaction=transaction)
        data = snapshot.to_dict() if snapshot.exists else None
        if (
            not data
            or data.get("status") != STATUS_PENDING
            or not lease_owner
            or str(data.get("lease_owner") or "") != str(lease_owner)
        ):
            return False
        status = outcome
        attempts = data.get("attempts") if isinstance(data.get("attempts"), int) else 0
        if outcome == RETRY:
            if attempts >= MAX_ATTEMPTS:
                status = FAILED
                error_text = error or "attempts_exhausted"
            else:
                transaction.update(ref, {
                    "next_attempt_at": now + retry_delay(attempts),
                    "lease_owner": "",
                    "last_error": _clip(error, 80),
                    "updated_at": now,
                })
                return True
        else:
            error_text = error
        if status not in TERMINAL_STATUSES:
            status, error_text = FAILED, "invalid_outcome"
        transaction.update(ref, _terminal_update(status, now, error_text))
        terminal.update(data=data, status=status, error=error_text)
        return True

    finished = bool(_run_transaction(db, operation))
    if terminal:
        _record_terminal(terminal["data"], terminal["status"], terminal["error"])
    return finished


def cleanup(*, now=None, db=None, max_items: int = 500) -> int:
    """Delete terminal items after the retention window (bounded per pass)."""
    db = db if db is not None else db_firestore
    now = now or utcnow()
    cutoff = now - timedelta(days=RETENTION_DAYS)
    collection = db.collection(OUTBOX_COLLECTION)
    try:
        query = collection.where(filter=FieldFilter("created_at", "<=", cutoff))
    except TypeError:
        query = None
    if query is not None and hasattr(query, "limit"):
        docs = query.limit(max(1, int(max_items))).stream()
    else:
        docs = [
            doc for doc in collection.stream()
            if isinstance((doc.to_dict() or {}).get("created_at"), datetime)
            and (doc.to_dict() or {})["created_at"] <= cutoff
        ][:max_items]
    deleted = 0
    for doc in docs:
        if (doc.to_dict() or {}).get("status") in TERMINAL_STATUSES:
            doc.reference.delete()
            deleted += 1
    return deleted


def delete_for_uid(uid: str, *, db=None) -> int:
    """Account deletion: remove every item owned by ``uid`` (any status)."""
    db = db if db is not None else db_firestore
    uid = str(uid or "").strip()
    if not uid:
        return 0
    collection = db.collection(OUTBOX_COLLECTION)
    try:
        query = collection.where(filter=FieldFilter("uid", "==", uid))
    except TypeError:
        query = collection.where("uid", "==", uid)
    deleted = 0
    for doc in query.stream():
        doc.reference.delete()
        deleted += 1
    return deleted
