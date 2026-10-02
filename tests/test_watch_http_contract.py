"""Watch and Telegram routes exercise their real persistence services."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock
import pytest
from app.services import (
    watch_service as watch,
    watch_followers as followers,
    telegram_watch as telegram,
    watch_brief,
    share_snapshots,
)
from adapter_test_support import http_adapter, login
from app.core.rate_limit import limiter
from test_watch_feature import FakeDb, share


@pytest.fixture
def watch_http(http_adapter, monkeypatch):
    h = http_adapter
    h.watch_db = FakeDb()
    h.share_id = "W" * 16
    for module in (watch, followers, telegram, watch_brief, share_snapshots):
        monkeypatch.setattr(module, "db_firestore", h.watch_db)
    for key, value in {
        "TELEGRAM_BOT_TOKEN": "dummy",
        "TELEGRAM_BOT_USERNAME": "consens_test_bot",
        "TELEGRAM_WEBHOOK_SECRET": "test-webhook-secret",
        "WATCH_UNSUBSCRIBE_SECRET": "test-secret",
    }.items():
        monkeypatch.setenv(key, value)
    h.watch_db.stores["shares"][h.share_id] = share(owner="owner")
    h.watch = watch.create_watch(
        "owner", share_id=h.share_id, interval="weekly", tier="free", db=h.watch_db
    )
    h.url = "/api/watch/" + h.watch["id"]
    h.sender = Mock(return_value={"status": "sent"})
    monkeypatch.setattr(telegram.telegram_notifier, "send_bot_message", h.sender)
    return h


def test_watch_patch_delete_entitlement_owner_and_allowlist(watch_http):
    h = watch_http
    before = deepcopy(dict(h.watch_db.stores))
    for identity, payload, status in [
        ("stranger", {"status": "paused"}, 403),
        ("owner", {"owner_uid": "stranger"}, 400),
        ("owner", {"interval": "daily"}, 403),
        ("owner", {"telegram_enabled": True}, 409),
    ]:
        response = h.client.patch(h.url, headers=login(identity), json=payload)
        assert response.status_code == status, response.text
        assert (
            h.watch_db.stores[watch.WATCHES_COLLECTION]
            == before[watch.WATCHES_COLLECTION]
        )
    response = h.client.patch(
        h.url, headers=login("owner"), json={"status": "paused", "interval": "monthly"}
    )
    assert response.status_code == 200, response.text
    stored = h.watch_db.stores[watch.WATCHES_COLLECTION][h.watch["id"]]
    assert stored["status"] == response.json()["watch"]["status"] == "paused"
    assert stored["interval"] == "monthly"
    assert h.client.delete(h.url, headers=login("stranger")).status_code == 403
    assert h.watch["id"] in h.watch_db.stores[watch.WATCHES_COLLECTION]
    assert h.client.delete(h.url, headers=login("owner")).status_code == 200
    assert h.watch["id"] not in h.watch_db.stores[watch.WATCHES_COLLECTION]
    h.sender.assert_not_called()


def test_telegram_link_test_disconnect_are_bound_to_authenticated_owner(watch_http):
    h = watch_http
    assert h.client.post("/api/my/telegram/link").status_code == 401
    assert (
        h.client.post("/api/my/telegram/test", headers=login("owner")).status_code
        == 409
    )
    h.sender.assert_not_called()
    response = h.client.post(
        "/api/my/telegram/link", headers=login("owner"), json={"uid": "forged"}
    )
    assert response.status_code == 200, response.text
    token = response.json()["url"].split("start=", 1)[1]
    record = h.watch_db.stores[telegram.LINKS_COLLECTION][telegram._digest(token)]
    assert record["uid"] == "owner" and token not in str(record)
    telegram.consume_link(
        token,
        {"id": 123, "type": "private"},
        {"id": 123, "first_name": "Alice"},
        db=h.watch_db,
    )
    h.watch_db.stores[telegram.CONNECTIONS_COLLECTION]["stranger"] = {
        "chat_id": "456",
        "enabled": True,
    }
    assert h.client.post("/api/my/telegram/test", headers=login("owner")).json()[
        "delivery"
    ] == {"status": "sent"}
    assert h.sender.call_args.args[0] == "123"
    h.sender.return_value = {"status": "failed"}
    assert (
        h.client.post("/api/my/telegram/test", headers=login("owner")).status_code
        == 502
    )
    response = h.client.delete("/api/my/telegram", headers=login("owner"))
    assert (
        response.status_code == 200
        and response.json()["telegram"]["connected"] is False
    )
    assert "owner" not in h.watch_db.stores[telegram.CONNECTIONS_COLLECTION]
    assert (
        h.watch_db.stores[telegram.CONNECTIONS_COLLECTION]["stranger"]["chat_id"]
        == "456"
    )
    assert telegram._digest("123") not in h.watch_db.stores[telegram.CHATS_COLLECTION]
    count = h.sender.call_count
    limiter.reset()
    assert (
        h.client.post("/api/my/telegram/test", headers=login("owner")).status_code
        == 409
    )
    assert h.sender.call_count == count


@pytest.mark.parametrize(
    "endpoint", ["/watch/unsubscribe", "/watch/follow/unsubscribe"]
)
@pytest.mark.parametrize("kind", ["invalid", "expired", "wrong_type"])
def test_unsubscribe_invalid_expired_and_wrong_type_never_mutate(
    watch_http, endpoint, kind
):
    h = watch_http
    token = "broken"
    if kind == "expired":
        token = watch.sign_token_payload(
            {
                "wid": h.watch["id"],
                "sid": h.share_id,
                "em": "reader@example.test",
                "un": 1,
            },
            now=datetime.now(timezone.utc) - timedelta(days=100),
        )
    if kind == "wrong_type":
        token = watch.sign_token_payload(
            {"tt": "topic", "tid": "topic", "em": "reader@example.test", "un": 1}
        )
    before = deepcopy(dict(h.watch_db.stores))
    response = h.client.get(endpoint, params={"token": token})
    assert response.status_code == (410 if kind == "expired" else 400), response.text
    assert "noindex" in response.headers["x-robots-tag"]
    assert {k: v for k, v in h.watch_db.stores.items() if v} == {
        k: v for k, v in before.items() if v
    }


def test_watch_and_follower_unsubscribe_change_only_the_bound_resource(watch_http):
    h = watch_http
    email = "reader@example.test"
    h.watch_db.stores[followers.FOLLOWERS_COLLECTION][
        followers.follower_id(h.share_id, email)
    ] = {"share_id": h.share_id, "email": email}
    h.watch_db.stores[followers.FOLLOWERS_COLLECTION]["control"] = {
        "share_id": "other",
        "email": email,
    }
    token = followers.make_follow_unsubscribe_token(h.share_id, email)
    assert (
        h.client.get("/watch/follow/unsubscribe", params={"token": token}).status_code
        == 200
    )
    assert list(h.watch_db.stores[followers.FOLLOWERS_COLLECTION]) == ["control"]
    token = watch.make_unsubscribe_token(h.watch["id"])
    for _ in range(2):
        assert (
            h.client.get("/watch/unsubscribe", params={"token": token}).status_code
            == 200
        )
    stored = h.watch_db.stores[watch.WATCHES_COLLECTION][h.watch["id"]]
    assert stored["status"] == "paused" and stored.get("current_run_id") is None


def test_follower_confirmation_escapes_stored_question(watch_http):
    h = watch_http
    h.watch_db.stores["shares"][h.share_id][
        "question"
    ] = '<img src=x onerror="alert(1)"> question'
    pending = followers.request_follow(h.share_id, "reader@example.test", db=h.watch_db)
    response = h.client.get("/watch/follow/confirm", params={"token": pending["token"]})
    assert response.status_code == 200, response.text
    assert "<img" not in response.text and "&lt;img" in response.text
    assert len(h.watch_db.stores[followers.FOLLOWERS_COLLECTION]) == 1


@pytest.mark.parametrize(
    "method,path",
    [("PATCH", "watch"), ("DELETE", "watch"), ("POST", "/api/my/telegram/link")],
)
def test_watch_adapters_project_storage_failure_safely(
    watch_http, monkeypatch, method, path
):
    h = watch_http
    before = deepcopy(dict(h.watch_db.stores))
    monkeypatch.setattr(
        h.watch_db,
        "run_transaction",
        Mock(side_effect=RuntimeError("PRIVATE storage failure")),
    )
    response = h.client.request(
        method,
        h.url if path == "watch" else path,
        headers=login("owner"),
        json={"status": "paused"} if method == "PATCH" else {},
    )
    assert response.status_code == 500 and "PRIVATE" not in response.text
    assert {k: v for k, v in h.watch_db.stores.items() if v} == {
        k: v for k, v in before.items() if v
    }
