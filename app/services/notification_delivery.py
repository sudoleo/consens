"""Deliver durable outbox items: one leased attempt per item and pass.

Every attempt first re-reads the current subscription state, so a recipient
who unsubscribed, paused the watch, switched a channel off or deleted the
account after the item was written never receives a late retry. The message
content comes from the item payload plus the immutable Watch version; no
retry ever starts a new LLM pipeline.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from firebase_admin import auth

from app.core.observability import safe_exception
from app.core.security import db_firestore
from app.core.site import SITE_URL
from app.services import (
    mailer,
    notification_outbox as outbox,
    share_snapshots,
    telegram_watch,
    topics,
    watch_brief,
    watch_followers,
    watch_service,
)


OUTBOX_PASS_MAX_ITEMS = 100


def _doc(db, collection: str, doc_id: str):
    if not doc_id:
        return None
    snapshot = db.collection(collection).document(doc_id).get()
    return snapshot.to_dict() if snapshot.exists else None


def _share_path(payload: dict, *, private_aware: bool) -> str:
    slug = payload.get("share_slug") or ""
    if private_aware and payload.get("visibility") == "private":
        slug = ""
    return share_snapshots.share_path(slug, payload.get("share_id") or "")


async def _verified_email(uid: str):
    """(email, outcome) — outcome is None when the address may receive mail."""
    try:
        user = await asyncio.to_thread(auth.get_user, uid)
    except auth.UserNotFoundError:
        return None, (outbox.SKIPPED, "user_missing")
    except Exception as exc:
        logging.warning("Notification owner lookup failed category=%s", safe_exception(exc))
        return None, (outbox.RETRY, "owner_lookup")
    if not getattr(user, "email_verified", False) or not getattr(user, "email", None):
        return None, (outbox.SKIPPED, "unverified")
    return user.email, None


async def _send_mail(message) -> tuple:
    accepted = await mailer.send_message(message)
    return (outbox.SENT, "") if accepted else (outbox.RETRY, "smtp")


def _watch_version_consensus(payload: dict, run_id: str, db) -> str:
    version = share_snapshots.get_watch_version(
        payload.get("share_id") or "", run_id, db=db,
    )
    return str((version or {}).get("consensus_md") or "")


def _watch_gate(item: dict, watch: dict | None, *, channel_field: str):
    """Return a terminal (status, reason) when the owner opted out meanwhile."""
    if not watch:
        return outbox.SKIPPED, "watch_deleted"
    if str(watch.get("owner_uid") or "") != str(item.get("uid") or ""):
        return outbox.SKIPPED, "owner_changed"
    if item.get("kind") == outbox.KIND_WATCH_PAUSED:
        if watch.get("status") != "paused_error":
            return outbox.SKIPPED, "resumed"
    elif watch.get("status") != "active":
        # The unsubscribe link, the Telegram pause and the dashboard all pause.
        return outbox.SKIPPED, "paused"
    if channel_field == "email_enabled" and watch.get("email_enabled") is False:
        return outbox.SKIPPED, "channel_disabled"
    if channel_field == "telegram_enabled" and watch.get("telegram_enabled") is not True:
        return outbox.SKIPPED, "channel_disabled"
    return None


def _owner_message(item: dict, payload: dict, recipient: str, consensus: str):
    share_url = SITE_URL + _share_path(payload, private_aware=True)
    unsubscribe_url = (
        SITE_URL + "/watch/unsubscribe?token="
        + watch_service.make_unsubscribe_token(item["resource_id"])
    )
    question = payload.get("question") or ""
    if item["kind"] == outbox.KIND_WATCH_PAUSED:
        return mailer.build_paused_message(
            recipient=recipient, question=question,
            share_url=share_url, unsubscribe_url=unsubscribe_url,
        )
    alert = payload.get("alert")
    old_score = payload.get("old_score")
    score = payload.get("agreement_score")
    direction = payload.get("direction") or None
    if alert == "every_run":
        return mailer.build_run_message(
            recipient=recipient, question=question, agreement_score=score,
            consensus=consensus, changed=bool(payload.get("changed")),
            severity=payload.get("severity") or "minor",
            summary=payload.get("change_summary") or "",
            share_url=share_url, unsubscribe_url=unsubscribe_url,
            old_score=old_score, direction=direction,
        )
    if alert == "condition":
        return mailer.build_condition_message(
            recipient=recipient, question=question,
            condition=payload.get("condition") or "",
            reason=payload.get("condition_reason")
            or "The condition is met by the new consensus.",
            agreement_score=score, consensus=consensus,
            share_url=share_url, unsubscribe_url=unsubscribe_url,
            old_score=old_score, direction=direction,
        )
    return mailer.build_change_message(
        recipient=recipient, question=question, old_score=old_score,
        new_score=score,
        summary=payload.get("change_summary") or "The agreement score changed materially.",
        share_url=share_url, unsubscribe_url=unsubscribe_url,
        severity=payload.get("severity") or "major", direction=direction,
    )


async def _deliver_watch_email(item: dict, db) -> tuple:
    payload = item.get("payload") or {}
    watch = await asyncio.to_thread(
        _doc, db, watch_service.WATCHES_COLLECTION, item.get("resource_id") or "",
    )
    gate = _watch_gate(item, watch, channel_field="email_enabled")
    if gate:
        return gate
    if not mailer.is_configured():
        return outbox.SKIPPED, "smtp_not_configured"
    recipient, blocked = await _verified_email(item["uid"])
    if blocked:
        return blocked
    consensus = ""
    if payload.get("alert") in {"every_run", "condition"}:
        consensus = await asyncio.to_thread(
            _watch_version_consensus, payload, item.get("run_id") or "", db,
        )
    return await _send_mail(_owner_message(item, payload, recipient, consensus))


def _telegram_outcome(status: dict) -> tuple:
    if status.get("status") == "sent":
        return outbox.SENT, ""
    if status.get("status") == "skipped_not_configured":
        return outbox.SKIPPED, "telegram_not_configured"
    code = status.get("http_status") or status.get("error_code")
    if code == 403:
        return outbox.SKIPPED, "telegram_blocked"
    if code == 429 or status.get("status") == "failed_network" or (
        isinstance(code, int) and code >= 500
    ):
        return outbox.RETRY, "telegram_transient"
    if isinstance(code, int) and 400 <= code < 500:
        return outbox.FAILED, "telegram_rejected"
    return outbox.RETRY, "telegram_unknown"


def _deliver_watch_telegram_sync(item: dict, db, now: datetime) -> tuple:
    payload = item.get("payload") or {}
    watch_id = item.get("resource_id") or ""
    watch = _doc(db, watch_service.WATCHES_COLLECTION, watch_id)
    gate = _watch_gate(item, watch, channel_field="telegram_enabled")
    if gate:
        return gate
    muted_until = watch.get("telegram_muted_until")
    if isinstance(muted_until, datetime) and muted_until > now:
        return outbox.SKIPPED, "muted"
    connection_ref = db.collection(telegram_watch.CONNECTIONS_COLLECTION).document(item["uid"])
    snapshot = connection_ref.get()
    connection = snapshot.to_dict() if snapshot.exists else None
    if not connection or not connection.get("enabled") or not connection.get("chat_id"):
        return outbox.SKIPPED, "telegram_not_linked"
    kind = "paused_error" if item["kind"] == outbox.KIND_WATCH_PAUSED else payload.get("alert")
    view = {
        "question": payload.get("question") or "",
        "last_agreement_score": payload.get("old_score"),
        "share_id": payload.get("share_id") or "",
        "share_slug": payload.get("share_slug") or "",
        "visibility": payload.get("visibility") or "public",
    }
    result = {
        "agreement_score": payload.get("agreement_score"),
        "changed": payload.get("changed"),
        "change_summary": payload.get("change_summary") or "",
        "condition_reason": payload.get("condition_reason") or "",
        "opinion_map": payload.get("direction") or {},
    }
    if kind == "every_run":
        result["consensus"] = _watch_version_consensus(payload, item.get("run_id") or "", db)
    status = telegram_watch.send_watch_message(
        connection["chat_id"], watch_id, kind, view, result,
    )
    outcome = _telegram_outcome(status)
    if outcome[1] == "telegram_blocked":
        try:
            connection_ref.update({"enabled": False, "blocked_at": outbox.utcnow()})
        except Exception as exc:
            logging.warning("Telegram connection block marker failed category=%s", safe_exception(exc))
    return outcome


async def _deliver_watch_follower(item: dict, db) -> tuple:
    payload = item.get("payload") or {}
    share_id = payload.get("share_id") or ""
    follower = await asyncio.to_thread(
        _doc, db, watch_followers.FOLLOWERS_COLLECTION, item.get("recipient_id") or "",
    )
    if not follower or str(follower.get("share_id") or "") != share_id or not follower.get("email"):
        return outbox.SKIPPED, "unsubscribed"
    watch = await asyncio.to_thread(
        _doc, db, watch_service.WATCHES_COLLECTION, item.get("resource_id") or "",
    )
    share = await asyncio.to_thread(share_snapshots.get_share, share_id, db=db)
    if (
        not watch
        or not share
        or share.get("status") != "active"
        or str(share.get("visibility") or "public") != "public"
    ):
        return outbox.SKIPPED, "page_unavailable"
    if not mailer.is_configured():
        return outbox.SKIPPED, "smtp_not_configured"
    email = follower["email"]
    token = watch_followers.make_follow_unsubscribe_token(share_id, email)
    message = mailer.build_follower_change_message(
        recipient=email, question=payload.get("question") or "",
        old_score=payload.get("old_score"), new_score=payload.get("agreement_score"),
        summary=payload.get("change_summary") or "The agreement score changed materially.",
        share_url=SITE_URL + _share_path(payload, private_aware=False),
        unsubscribe_url=SITE_URL + "/watch/follow/unsubscribe?token=" + token,
        severity=payload.get("severity") or "major",
        direction=payload.get("direction") or None,
    )
    return await _send_mail(message)


async def _deliver_topic_follower(item: dict, db) -> tuple:
    payload = item.get("payload") or {}
    topic_id = item.get("resource_id") or ""
    follower = await asyncio.to_thread(
        _doc, db, topics.FOLLOWERS_COLLECTION, item.get("recipient_id") or "",
    )
    if not follower or str(follower.get("topic_id") or "") != topic_id or not follower.get("email"):
        return outbox.SKIPPED, "unsubscribed"
    topic = await asyncio.to_thread(topics.get_topic, topic_id, db=db)
    if not topic or topic.get("status") == "archived":
        return outbox.SKIPPED, "topic_unavailable"
    if not mailer.is_configured():
        return outbox.SKIPPED, "smtp_not_configured"
    email = follower["email"]
    message = mailer.build_topic_change_message(
        recipient=email,
        title=payload.get("title") or topic.get("title") or "",
        question=payload.get("question") or "",
        old_score=payload.get("old_score"),
        new_score=payload.get("new_score"),
        change_type=payload.get("change_type") or "major",
        summary=payload.get("summary") or "The Topic consensus changed.",
        topic_url=f"{SITE_URL}/topics/{payload.get('slug') or topic.get('slug') or ''}",
        unsubscribe_url=(
            SITE_URL + "/topic-follow/unsubscribe?token="
            + topics.make_unsubscribe_token(topic_id, email)
        ),
    )
    return await _send_mail(message)


async def _deliver_brief(item: dict, db, now: datetime) -> tuple:
    payload = item.get("payload") or {}
    uid = item.get("uid") or ""
    brief = await asyncio.to_thread(_doc, db, watch_brief.BRIEFS_COLLECTION, uid)
    if not brief or not brief.get("enabled"):
        return outbox.SKIPPED, "unsubscribed"
    if not mailer.is_configured():
        return outbox.SKIPPED, "smtp_not_configured"
    recipient, blocked = await _verified_email(uid)
    if blocked:
        return blocked
    baseline = payload.get("baseline")
    if not isinstance(baseline, datetime):
        baseline = now - watch_brief.FIRST_BRIEF_WINDOW
    items, changes = await asyncio.to_thread(
        watch_brief.collect_brief_items, uid, since=baseline, db=db,
    )
    if not items:
        return outbox.SKIPPED, "no_watches"
    if payload.get("mode") == "changes_only" and changes == 0:
        return outbox.SKIPPED, "no_changes"
    scheduled_at = payload.get("scheduled_at")
    label_time = scheduled_at if isinstance(scheduled_at, datetime) else now
    timezone_name = str(payload.get("timezone") or "UTC")
    try:
        date_label = label_time.astimezone(ZoneInfo(timezone_name)).strftime("%A, %d %B %Y")
    except (ZoneInfoNotFoundError, ValueError):
        date_label = label_time.strftime("%A, %d %B %Y")
    message = mailer.build_brief_message(
        recipient=recipient, date_label=date_label, items=items,
        changes_count=changes, site_url=SITE_URL,
        unsubscribe_url=SITE_URL + "/watch/brief/unsubscribe?token="
        + watch_brief.make_brief_unsubscribe_token(uid),
    )
    outcome = await _send_mail(message)
    if outcome[0] == outbox.SENT:
        try:
            await asyncio.to_thread(watch_brief.mark_brief_sent, uid, now=now, db=db)
        except Exception as exc:
            # Display-only timestamp; it must never turn an accepted mail
            # into a retry (and therefore a duplicate digest).
            logging.warning("Morning brief sent marker failed category=%s", safe_exception(exc))
    return outcome


async def attempt(item: dict, *, db, now: datetime) -> tuple:
    kind = item.get("kind")
    channel = item.get("channel")
    if kind in {outbox.KIND_WATCH_ALERT, outbox.KIND_WATCH_PAUSED}:
        if channel == outbox.CHANNEL_TELEGRAM:
            return await asyncio.to_thread(_deliver_watch_telegram_sync, item, db, now)
        return await _deliver_watch_email(item, db)
    if kind == outbox.KIND_WATCH_FOLLOWER:
        return await _deliver_watch_follower(item, db)
    if kind == outbox.KIND_TOPIC_FOLLOWER:
        return await _deliver_topic_follower(item, db)
    if kind == outbox.KIND_WATCH_BRIEF:
        return await _deliver_brief(item, db, now)
    return outbox.FAILED, "unknown_kind"


async def deliver(item_id: str, *, db=None, now=None) -> str:
    """Claim and attempt one item. Returns the recorded outcome or ``""``."""
    db = db if db is not None else db_firestore
    now = now or outbox.utcnow()
    claimed = await asyncio.to_thread(outbox.claim, item_id, now=now, db=db)
    if not claimed:
        return ""
    try:
        status, reason = await attempt(claimed, db=db, now=now)
    except Exception as exc:
        # One broken item or channel never blocks the others; it is retried.
        logging.error(
            "Notification attempt failed kind=%s category=%s",
            str(claimed.get("kind") or ""), safe_exception(exc),
        )
        status, reason = outbox.RETRY, "exception"
    await asyncio.to_thread(
        outbox.finish, item_id, claimed["lease_owner"], status,
        now=now, db=db, error=reason,
    )
    return status


async def deliver_many(item_ids, *, db=None, now=None) -> dict:
    counts: dict = {}
    for item_id in list(dict.fromkeys(item_ids or [])):
        try:
            status = await deliver(item_id, db=db, now=now)
        except Exception as exc:
            logging.error("Notification delivery pass error category=%s", safe_exception(exc))
            status = "error"
        if status:
            counts[status] = counts.get(status, 0) + 1
    return counts


async def run_outbox_tick(*, db=None, now=None) -> dict:
    """Retry pass over due items (new, crashed mid-attempt, or backing off)."""
    db = db if db is not None else db_firestore
    now = now or outbox.utcnow()
    due = await asyncio.to_thread(
        outbox.list_due_ids, now=now, db=db, max_items=OUTBOX_PASS_MAX_ITEMS,
    )
    return await deliver_many(due, db=db, now=now)
