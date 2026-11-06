"""Deliver durable outbox items: one leased attempt per item and pass.

Every attempt first re-reads the current subscription state, so a recipient
who unsubscribed, paused the watch, switched a channel off or deleted the
account after the item was written never receives a late retry. The message
content comes from the item payload plus the immutable Watch version; no
retry ever starts a new LLM pipeline.

Each kind says what must still stand (``load``) and what its message says on
each channel it carries (``render``). How a message reaches the recipient
belongs to the channel (``notification_channels``). Every attempt takes the
same steps, in this order, and any of them can end it with an outcome:

1. ``load``: the subscription is still there (Watch, follower, Brief)
2. the Watch's switch for this channel is on and the channel is not muted
3. ``channel.reach``: the recipient can be reached on it
4. ``render``: the message (a Brief with nothing in it ends here)
5. ``channel.send``, then the kind's ``after_sent``
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Awaitable, Callable, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.observability import safe_exception
from app.core.security import db_firestore
from app.core.site import SITE_URL
from app.services import (
    account_language,
    mailer,
    notification_channels as channels,
    notification_outbox as outbox,
    share_snapshots,
    telegram_watch,
    topics,
    watch_brief,
    watch_followers,
    watch_service,
)
from app.services.notification_channels import Stop


OUTBOX_PASS_MAX_ITEMS = 100
EMAIL = outbox.CHANNEL_EMAIL
TELEGRAM = outbox.CHANNEL_TELEGRAM


@dataclass(frozen=True)
class Subject:
    """What an attempt found still standing.

    ``watch`` is the Watch whose channel switches and mute apply (None for a
    kind without switches), ``address`` a fixed mail recipient (a follower;
    empty means the account's own address), ``data`` what the renderer needs.
    """

    watch: Optional[dict] = None
    address: str = ""
    data: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Kind:
    """One kind of notification.

    ``load(item, db, now)`` returns the Subject or raises Stop;
    ``render[channel](item, subject, recipient, db=, now=)`` returns the
    channel's message or raises Stop; ``switches`` are the defaults of the
    Watch's channel switches (None: the kind has none); ``after_sent`` runs
    once a message was accepted.
    """

    load: Callable[..., Awaitable[Subject]]
    render: dict
    switches: Optional[dict] = None
    after_sent: Optional[Callable[..., Awaitable[None]]] = None


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


def _delta(payload: dict) -> dict:
    """The change log of an item; items queued before it existed (bounded by
    their ``deliver_until``) only carry the summary."""
    return payload.get("delta") or {
        "summary": payload.get("change_summary") or payload.get("summary") or "",
    }


# ---------------------------------------------------------------------------
# Consensus Watch: the owner's alert and the paused-after-three-failures notice
# ---------------------------------------------------------------------------

def _watch_version_answer(payload: dict, run_id: str, db) -> tuple[str, list]:
    """The answer of the run's immutable version and the sources its [S1]
    citations point to. Expired redirects are left out, like on the page:
    their citations drop instead of linking nowhere."""
    version = share_snapshots.get_watch_version(
        payload.get("share_id") or "", run_id, db=db,
    ) or {}
    expired = {str(source_id) for source_id in version.get("expired_source_ids") or []}
    sources = [
        source for source in version.get("sources") or []
        if isinstance(source, dict) and str(source.get("id") or "") not in expired
    ]
    return str(version.get("consensus_md") or ""), sources


async def _load_watch(item: dict, db, now: datetime) -> Subject:
    watch = await asyncio.to_thread(
        _doc, db, watch_service.WATCHES_COLLECTION, item.get("resource_id") or "",
    )
    if not watch:
        raise Stop(outbox.SKIPPED, "watch_deleted")
    if str(watch.get("owner_uid") or "") != str(item.get("uid") or ""):
        raise Stop(outbox.SKIPPED, "owner_changed")
    if item.get("kind") == outbox.KIND_WATCH_PAUSED:
        if watch.get("status") != "paused_error":
            raise Stop(outbox.SKIPPED, "resumed")
    elif watch.get("status") != "active" and not (
        watch.get("status") == watch_service.WATCH_STATUS_RESOLVED
        and (item.get("payload") or {}).get("alert") == "condition"
    ):
        # The unsubscribe link, the Telegram pause and the dashboard all pause.
        # The resolving check is the one alert a resolved watch still sends.
        raise Stop(outbox.SKIPPED, "paused")
    return Subject(watch=watch)


def _owner_message(item: dict, payload: dict, recipient: str, answer: tuple, language: str = ""):
    consensus, answer_sources = answer
    share_url = SITE_URL + mailer.owner_page_path(
        _share_path(payload, private_aware=True),
        private=payload.get("visibility") == "private",
    )
    unsubscribe_url = (
        SITE_URL + "/watch/unsubscribe?token="
        + watch_service.make_unsubscribe_token(item["resource_id"])
    )
    question = payload.get("question") or ""
    if item["kind"] == outbox.KIND_WATCH_PAUSED:
        return mailer.build_paused_message(
            recipient=recipient, question=question, language=language,
            share_url=share_url, unsubscribe_url=unsubscribe_url,
            resume_url=(
                SITE_URL + "/watch/resume?token="
                + watch_service.make_resume_token(item["resource_id"])
            ),
        )
    alert = payload.get("alert")
    delta = _delta(payload)
    if alert == "every_run":
        return mailer.build_run_message(
            recipient=recipient, question=question, delta=delta, language=language,
            moved=bool(payload.get("moved")), consensus=consensus,
            share_url=share_url, unsubscribe_url=unsubscribe_url,
            answer_sources=answer_sources,
        )
    if alert == "condition":
        return mailer.build_condition_message(
            recipient=recipient, question=question, language=language,
            goal=payload.get("condition") or "",
            reason=payload.get("condition_reason") or "",
            sources=payload.get("condition_sources") or [],
            consensus=consensus, share_url=share_url, unsubscribe_url=unsubscribe_url,
            answer_sources=answer_sources,
        )
    return mailer.build_change_message(
        recipient=recipient, question=question, delta=delta, language=language,
        share_url=share_url, unsubscribe_url=unsubscribe_url,
    )


async def _watch_mail(item: dict, subject: Subject, recipient: str, *, db, now):
    payload = item.get("payload") or {}
    answer = ("", [])
    if payload.get("alert") in {"every_run", "condition"}:
        answer = await asyncio.to_thread(
            _watch_version_answer, payload, item.get("run_id") or "", db,
        )
    language = await asyncio.to_thread(account_language.of, item["uid"], db=db)
    return _owner_message(item, payload, recipient, answer, language)


async def _watch_telegram(item: dict, subject: Subject, recipient, *, db, now):
    payload = item.get("payload") or {}
    kind = "paused_error" if item["kind"] == outbox.KIND_WATCH_PAUSED else payload.get("alert")
    view = {
        "question": payload.get("question") or "",
        "share_id": payload.get("share_id") or "",
        "share_slug": payload.get("share_slug") or "",
        "visibility": payload.get("visibility") or "public",
        "condition": payload.get("condition") or "",
    }
    result = {
        "delta": _delta(payload),
        "moved": bool(payload.get("moved")),
        "condition_reason": payload.get("condition_reason") or "",
        # The same sources as the "Why" of the goal-reached mail.
        "condition_sources": payload.get("condition_sources") or [],
    }
    if kind in {"every_run", "condition"}:
        result["consensus"], result["consensus_sources"] = await asyncio.to_thread(
            _watch_version_answer, payload, item.get("run_id") or "", db,
        )
    return telegram_watch.watch_message(item.get("resource_id") or "", kind, view, result)


# ---------------------------------------------------------------------------
# Followers of a public Watch page or a Topic (mail only, no account)
# ---------------------------------------------------------------------------

async def _load_watch_follower(item: dict, db, now: datetime) -> Subject:
    share_id = (item.get("payload") or {}).get("share_id") or ""
    follower = await asyncio.to_thread(
        _doc, db, watch_followers.FOLLOWERS_COLLECTION, item.get("recipient_id") or "",
    )
    if not follower or str(follower.get("share_id") or "") != share_id or not follower.get("email"):
        raise Stop(outbox.SKIPPED, "unsubscribed")
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
        raise Stop(outbox.SKIPPED, "page_unavailable")
    return Subject(address=follower["email"], data={"language": follower.get("language") or ""})


async def _watch_follower_mail(item: dict, subject: Subject, recipient: str, *, db, now):
    payload = item.get("payload") or {}
    token = watch_followers.make_follow_unsubscribe_token(payload.get("share_id") or "", recipient)
    return mailer.build_follower_change_message(
        recipient=recipient, question=payload.get("question") or "",
        language=subject.data["language"],
        delta=_delta(payload),
        share_url=SITE_URL + _share_path(payload, private_aware=False),
        unsubscribe_url=SITE_URL + "/watch/follow/unsubscribe?token=" + token,
    )


async def _load_topic_follower(item: dict, db, now: datetime) -> Subject:
    topic_id = item.get("resource_id") or ""
    follower = await asyncio.to_thread(
        _doc, db, topics.FOLLOWERS_COLLECTION, item.get("recipient_id") or "",
    )
    if not follower or str(follower.get("topic_id") or "") != topic_id or not follower.get("email"):
        raise Stop(outbox.SKIPPED, "unsubscribed")
    topic = await asyncio.to_thread(topics.get_topic, topic_id, db=db)
    if not topic or topic.get("status") == "archived":
        raise Stop(outbox.SKIPPED, "topic_unavailable")
    return Subject(address=follower["email"],
                   data={"language": follower.get("language") or "", "topic": topic})


async def _topic_follower_mail(item: dict, subject: Subject, recipient: str, *, db, now):
    payload = item.get("payload") or {}
    topic = subject.data["topic"]
    return mailer.build_topic_change_message(
        recipient=recipient, language=subject.data["language"],
        title=payload.get("title") or topic.get("title") or "",
        question=payload.get("question") or "",
        delta=_delta(payload),
        topic_url=f"{SITE_URL}/topics/{payload.get('slug') or topic.get('slug') or ''}",
        unsubscribe_url=(
            SITE_URL + "/topic-follow/unsubscribe?token="
            + topics.make_unsubscribe_token(item.get("resource_id") or "", recipient)
        ),
    )


# ---------------------------------------------------------------------------
# Morning Brief
# ---------------------------------------------------------------------------

async def _load_brief(item: dict, db, now: datetime) -> Subject:
    brief = await asyncio.to_thread(_doc, db, watch_brief.BRIEFS_COLLECTION, item.get("uid") or "")
    if not brief or not brief.get("enabled"):
        raise Stop(outbox.SKIPPED, "unsubscribed")
    return Subject()


async def _brief_mail(item: dict, subject: Subject, recipient: str, *, db, now):
    payload = item.get("payload") or {}
    uid = item.get("uid") or ""
    baseline = payload.get("baseline")
    if not isinstance(baseline, datetime):
        baseline = now - watch_brief.FIRST_BRIEF_WINDOW
    items, changes = await asyncio.to_thread(
        watch_brief.collect_brief_items, uid, since=baseline, db=db,
    )
    if not items:
        raise Stop(outbox.SKIPPED, "no_watches")
    if payload.get("mode") == "changes_only" and changes == 0:
        raise Stop(outbox.SKIPPED, "no_changes")
    scheduled_at = payload.get("scheduled_at")
    label_time = scheduled_at if isinstance(scheduled_at, datetime) else now
    timezone_name = str(payload.get("timezone") or "UTC")
    try:
        label_time = label_time.astimezone(ZoneInfo(timezone_name))
    except (ZoneInfoNotFoundError, ValueError):
        pass
    language = await asyncio.to_thread(account_language.of, uid, db=db)
    return mailer.build_brief_message(
        recipient=recipient, language=language,
        date_label=mailer.brief_date_label(label_time, language=language), items=items,
        changes_count=changes, site_url=SITE_URL,
        unsubscribe_url=SITE_URL + "/watch/brief/unsubscribe?token="
        + watch_brief.make_brief_unsubscribe_token(uid),
        brief_timezone=timezone_name,
    )


async def _brief_sent(item: dict, db, now: datetime) -> None:
    try:
        await asyncio.to_thread(watch_brief.mark_brief_sent, item.get("uid") or "", now=now, db=db)
    except Exception as exc:
        # Display-only timestamp; it must never turn an accepted mail
        # into a retry (and therefore a duplicate digest).
        logging.warning("Morning brief sent marker failed category=%s", safe_exception(exc))


# ---------------------------------------------------------------------------
# Agent Watch: a finding, a question or the goal of one run (agent_watches.turn_ended)
# ---------------------------------------------------------------------------

async def _load_agent_watch(item: dict, db, now: datetime) -> Subject:
    """Its Watch or its owner gone: nothing."""
    from app.services import agent_watches
    watch = await asyncio.to_thread(_doc, db, agent_watches.COLLECTION, item.get("resource_id") or "")
    if not watch:
        raise Stop(outbox.SKIPPED, "watch_deleted")
    if str(watch.get("uid") or "") != str(item.get("uid") or ""):
        raise Stop(outbox.SKIPPED, "owner_changed")
    return Subject(watch=watch)


def _agent_chat_url(payload: dict) -> str:
    """The run's chat: /app opens it (firebase.js openChatFromLink), after a sign-in if needed."""
    bookmark = str(payload.get("bookmark_id") or "")
    return SITE_URL + "/app" + (f"?chat={bookmark}" if bookmark.replace("_", "").isalnum() else "")


async def _agent_watch_mail(item: dict, subject: Subject, recipient: str, *, db, now):
    from app.services import agent_watches
    payload = item.get("payload") or {}
    language = await asyncio.to_thread(account_language.of, item["uid"], db=db)
    return mailer.build_agent_watch_message(
        recipient=recipient, language=language, outcome=payload.get("outcome") or "finding",
        task=payload.get("task") or "", goal=payload.get("goal") or "",
        summary=payload.get("summary") or "", evidence_url=payload.get("evidence_url") or "",
        evidence_title=payload.get("evidence_title") or "", halted=bool(payload.get("halted")),
        goal_met=bool(payload.get("goal_met")), goal_reason=payload.get("goal_reason") or "",
        review=payload.get("review") or {}, app_url=_agent_chat_url(payload),
        unsubscribe_url=SITE_URL + "/agent-watch/unsubscribe?token="
        + agent_watches.unsubscribe_token(item["resource_id"]),
    )


async def _agent_watch_telegram(item: dict, subject: Subject, recipient, *, db, now):
    payload = item.get("payload") or {}
    language = await asyncio.to_thread(account_language.of, item["uid"], db=db)
    return telegram_watch.agent_watch_message(
        payload, chat_url=_agent_chat_url(payload), language=language,
    )


# ---------------------------------------------------------------------------
# One attempt
# ---------------------------------------------------------------------------

_WATCH = Kind(load=_load_watch, switches=outbox.WATCH_CHANNEL_DEFAULTS,
              render={EMAIL: _watch_mail, TELEGRAM: _watch_telegram})

KINDS = {
    outbox.KIND_WATCH_ALERT: _WATCH,
    outbox.KIND_WATCH_PAUSED: _WATCH,
    outbox.KIND_WATCH_FOLLOWER: Kind(load=_load_watch_follower, render={EMAIL: _watch_follower_mail}),
    outbox.KIND_TOPIC_FOLLOWER: Kind(load=_load_topic_follower, render={EMAIL: _topic_follower_mail}),
    outbox.KIND_WATCH_BRIEF: Kind(load=_load_brief, render={EMAIL: _brief_mail}, after_sent=_brief_sent),
    outbox.KIND_AGENT_WATCH: Kind(load=_load_agent_watch, switches=outbox.AGENT_WATCH_CHANNEL_DEFAULTS,
                                  render={EMAIL: _agent_watch_mail, TELEGRAM: _agent_watch_telegram}),
}


async def attempt(item: dict, *, db, now: datetime) -> tuple:
    kind = KINDS.get(item.get("kind"))
    if kind is None:
        return outbox.FAILED, "unknown_kind"
    render = kind.render.get(item.get("channel"))
    if render is None:
        return outbox.FAILED, "unknown_channel"
    channel = channels.CHANNELS[item["channel"]]
    try:
        subject = await kind.load(item, db, now)
        if kind.switches is not None:
            if not outbox.channel_on(subject.watch, channel.name, defaults=kind.switches):
                return outbox.SKIPPED, "channel_disabled"
            if channel.muted(subject.watch, now):
                return outbox.SKIPPED, "muted"
        recipient = await channel.reach(item, db=db, address=subject.address)
        message = await render(item, subject, recipient, db=db, now=now)
    except Stop as stop:
        return stop.outcome
    outcome = await channel.send(recipient, message)
    if outcome[0] == outbox.SENT and kind.after_sent is not None:
        await kind.after_sent(item, db, now)
    return outcome


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
