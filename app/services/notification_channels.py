"""How a notification reaches its recipient: one class per channel.

What a message says belongs to its kind (``notification_delivery``); a
channel knows nothing about Watches, Topics or Briefs. For one outbox item it
answers three questions:

* ``reach``: where does it go on this channel (a verified mail address, the
  linked Telegram chat)? No way to reach the recipient ends the attempt.
* ``muted``: did the recipient silence this channel for the Watch for now?
* ``send``: one attempt, answered as the outbox outcome (``sent``,
  ``retry``, ``failed`` or ``skipped``, plus a reason).

A new channel (push to the app, say) is one class here, its switch in
``notification_outbox.CHANNEL_SWITCHES`` and a renderer for each kind it
carries in ``notification_delivery``. The outbox, its retries, the
subscription checks and the staging stay as they are.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime

from firebase_admin import auth

from app.core.observability import safe_exception
from app.services import mailer, notification_outbox as outbox, telegram_watch


class Stop(Exception):
    """The attempt ends before anything was sent, with this outcome."""

    def __init__(self, status: str, reason: str):
        super().__init__(reason)
        self.outcome = (status, reason)


class EmailChannel:
    name = outbox.CHANNEL_EMAIL

    def muted(self, watch: dict | None, now: datetime) -> bool:
        return False

    async def reach(self, item: dict, *, db, address: str = "") -> str:
        """The mail address. ``address`` is where a subscription without an
        account wants it (a page or Topic follower); otherwise the account's
        own address, only once it is verified."""
        if not mailer.is_configured():
            raise Stop(outbox.SKIPPED, "smtp_not_configured")
        return address or await _verified_email(item["uid"])

    async def send(self, recipient: str, message) -> tuple:
        accepted = await mailer.send_message(message)
        return (outbox.SENT, "") if accepted else (outbox.RETRY, "smtp")


async def _verified_email(uid: str) -> str:
    try:
        user = await asyncio.to_thread(auth.get_user, uid)
    except auth.UserNotFoundError:
        raise Stop(outbox.SKIPPED, "user_missing") from None
    except Exception as exc:
        logging.warning("Notification owner lookup failed category=%s", safe_exception(exc))
        raise Stop(outbox.RETRY, "owner_lookup") from None
    if not getattr(user, "email_verified", False) or not getattr(user, "email", None):
        raise Stop(outbox.SKIPPED, "unverified")
    return user.email


@dataclass(frozen=True)
class TelegramChat:
    """The chat the account linked, and its connection record (marked
    blocked when the user blocks the bot)."""

    chat_id: object
    connection_ref: object


class TelegramChannel:
    name = outbox.CHANNEL_TELEGRAM
    # "Mute 24h" under a Consensus Watch alert.
    MUTED_FIELD = "telegram_muted_until"

    def muted(self, watch: dict | None, now: datetime) -> bool:
        until = (watch or {}).get(self.MUTED_FIELD)
        return isinstance(until, datetime) and until > now

    async def reach(self, item: dict, *, db, address: str = "") -> TelegramChat:
        return await asyncio.to_thread(_linked_chat, item["uid"], db)

    async def send(self, recipient: TelegramChat, message: telegram_watch.Message) -> tuple:
        status = await asyncio.to_thread(telegram_watch.send, recipient.chat_id, message)
        outcome = _telegram_outcome(status)
        if outcome[1] == "telegram_blocked":
            # Blocked the bot: no further messages until the user links it again.
            try:
                await asyncio.to_thread(
                    recipient.connection_ref.update, {"enabled": False, "blocked_at": outbox.utcnow()},
                )
            except Exception as exc:
                logging.warning("Telegram connection block marker failed category=%s", safe_exception(exc))
        return outcome


def _linked_chat(uid: str, db) -> TelegramChat:
    ref = db.collection(telegram_watch.CONNECTIONS_COLLECTION).document(uid)
    snapshot = ref.get()
    connection = snapshot.to_dict() if snapshot.exists else None
    if not connection or not connection.get("enabled") or not connection.get("chat_id"):
        raise Stop(outbox.SKIPPED, "telegram_not_linked")
    return TelegramChat(chat_id=connection["chat_id"], connection_ref=ref)


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


CHANNELS = {channel.name: channel for channel in (EmailChannel(), TelegramChannel())}
