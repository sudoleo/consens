"""The split between what a notification says (its kind) and how it travels
(its channel): every kind and channel is wired, and one attempt takes its
steps in order (notification_delivery, notification_channels)."""

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services import notification_channels as channels
from app.services import notification_delivery as delivery
from app.services import notification_outbox as outbox
from app.services import agent_watches, telegram_watch, watch_brief, watch_service
from test_watch_feature import FakeDb

NOW = datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc)
USER = SimpleNamespace(email="owner@example.test", email_verified=True)


def attempt(item, db):
    return asyncio.run(delivery.attempt(item, db=db, now=NOW))


def agent_item(channel=outbox.CHANNEL_EMAIL):
    return outbox.agent_watch_item(uid="u1", watch_id="aw1", run_id="t1", now=NOW, channel=channel,
                                   payload={"outcome": "finding", "summary": "Open."})["data"]


# --- wiring --------------------------------------------------------------------

def test_every_kind_and_every_channel_is_wired():
    assert set(delivery.KINDS) == outbox.KINDS
    assert set(channels.CHANNELS) == set(outbox.CHANNELS) == set(outbox.CHANNEL_SWITCHES)
    for name, channel in channels.CHANNELS.items():
        assert channel.name == name
    for kind in delivery.KINDS.values():
        assert set(kind.render) <= set(channels.CHANNELS)
        if kind.switches is not None:
            assert set(kind.switches) == set(outbox.CHANNELS)


def test_a_kind_never_travels_on_a_channel_it_has_no_message_for():
    item = {"kind": outbox.KIND_TOPIC_FOLLOWER, "channel": outbox.CHANNEL_TELEGRAM}
    assert attempt(item, FakeDb()) == (outbox.FAILED, "unknown_channel")
    assert attempt({"kind": "nope", "channel": outbox.CHANNEL_EMAIL}, FakeDb()) == (outbox.FAILED, "unknown_kind")
    with pytest.raises(ValueError):
        outbox.new_item(kind=outbox.KIND_AGENT_WATCH, channel="pigeon", resource_id="w", run_id="r",
                        recipient_id="u", payload={}, now=NOW)


# --- the switches ----------------------------------------------------------------

def test_an_unset_switch_is_the_kinds_default():
    legacy, agent = outbox.WATCH_CHANNEL_DEFAULTS, outbox.AGENT_WATCH_CHANNEL_DEFAULTS
    assert outbox.watch_channels({}, defaults=legacy) == [outbox.CHANNEL_EMAIL]
    assert outbox.watch_channels({"telegram_enabled": True}, defaults=legacy) == list(outbox.CHANNELS)
    # Only a real bool counts; anything else is the default.
    assert outbox.watch_channels({"telegram_enabled": "yes", "email_enabled": None}, defaults=legacy) == ["email"]
    assert outbox.watch_channels({}, defaults=agent) == list(outbox.CHANNELS)
    assert outbox.watch_channels({"email_enabled": False}, defaults=agent) == [outbox.CHANNEL_TELEGRAM]


def test_staging_and_delivery_read_the_same_switches():
    claimed = {"owner_uid": "u1", "current_run_id": "r1", "share_id": "A" * 16, "telegram_enabled": True}
    items = outbox.watch_paused_items("w1", claimed, now=NOW, email=True)
    assert [item["data"]["channel"] for item in items] == list(outbox.CHANNELS)
    # No mail server configured: only Telegram.
    items = outbox.watch_paused_items("w1", claimed, now=NOW, email=False)
    assert [item["data"]["channel"] for item in items] == [outbox.CHANNEL_TELEGRAM]
    shown = agent_watches.serialize("aw1", {"email_enabled": False, "status": "active"})
    assert shown["email_enabled"] is False and shown["telegram_enabled"] is True


# --- the steps of one attempt ------------------------------------------------------

def test_a_switched_off_channel_never_looks_up_the_recipient():
    db = FakeDb()
    db.stores[agent_watches.COLLECTION]["aw1"] = {"uid": "u1", "email_enabled": False}
    with (
        patch.object(channels.mailer, "is_configured", return_value=True),
        patch.object(channels.auth, "get_user") as get_user,
    ):
        assert attempt(agent_item(), db) == (outbox.SKIPPED, "channel_disabled")
    get_user.assert_not_called()


def test_a_gone_watch_ends_the_attempt_before_its_channel():
    with patch.object(channels.mailer, "is_configured", return_value=False):
        assert attempt(agent_item(), FakeDb()) == (outbox.SKIPPED, "watch_deleted")


def test_the_recipient_is_checked_before_anything_is_rendered():
    db = FakeDb()
    db.stores[agent_watches.COLLECTION]["aw1"] = {"uid": "u1"}
    unverified = SimpleNamespace(email="owner@example.test", email_verified=False)
    with (
        patch.object(channels.mailer, "is_configured", return_value=True),
        patch.object(channels.auth, "get_user", return_value=unverified),
        patch.object(delivery.mailer, "build_agent_watch_message") as build,
    ):
        assert attempt(agent_item(), db) == (outbox.SKIPPED, "unverified")
    build.assert_not_called()


def test_a_brief_with_nothing_in_it_is_not_sent():
    db = FakeDb()
    db.stores[watch_brief.BRIEFS_COLLECTION]["u1"] = {"enabled": True}
    item = outbox.brief_item("u1", scheduled_at=NOW, baseline=NOW - timedelta(days=1), mode="always",
                             timezone_name="UTC", now=NOW)["data"]
    send = AsyncMock(return_value=True)
    with (
        patch.object(channels.mailer, "is_configured", return_value=True),
        patch.object(channels.auth, "get_user", return_value=USER),
        patch.object(delivery.watch_brief, "collect_brief_items", return_value=([], 0)),
        patch.object(channels.mailer, "send_message", send),
        patch.object(delivery.watch_brief, "mark_brief_sent") as mark,
    ):
        assert attempt(item, db) == (outbox.SKIPPED, "no_watches")
    send.assert_not_awaited()
    mark.assert_not_called()


def test_mute_holds_telegram_only_while_it_lasts():
    db = FakeDb()
    db.stores[watch_service.WATCHES_COLLECTION]["w1"] = {
        "owner_uid": "u1", "status": "paused_error", "telegram_enabled": True,
        "telegram_muted_until": NOW + timedelta(hours=1),
    }
    claimed = {"owner_uid": "u1", "current_run_id": "r1", "share_id": "A" * 16, "telegram_enabled": True}
    telegram, = outbox.watch_paused_items("w1", claimed, now=NOW, email=False)
    assert attempt(telegram["data"], db) == (outbox.SKIPPED, "muted")
    assert channels.CHANNELS[outbox.CHANNEL_EMAIL].muted(db.stores["watches"]["w1"], NOW) is False
    db.stores[watch_service.WATCHES_COLLECTION]["w1"]["telegram_muted_until"] = NOW - timedelta(minutes=1)
    assert attempt(telegram["data"], db) == (outbox.SKIPPED, "telegram_not_linked")


def test_a_blocked_bot_switches_the_connection_off():
    db = FakeDb()
    db.stores[agent_watches.COLLECTION]["aw1"] = {"uid": "u1"}
    db.stores[telegram_watch.CONNECTIONS_COLLECTION]["u1"] = {"enabled": True, "chat_id": 42}
    with patch.object(telegram_watch.telegram_notifier, "send_bot_message",
                      return_value={"status": "failed_http", "http_status": 403}):
        assert attempt(agent_item(outbox.CHANNEL_TELEGRAM), db) == (outbox.SKIPPED, "telegram_blocked")
    assert db.stores[telegram_watch.CONNECTIONS_COLLECTION]["u1"]["enabled"] is False
