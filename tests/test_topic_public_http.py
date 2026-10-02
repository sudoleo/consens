"""Public Topic discovery and double-opt-in with real services and HTML."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlparse
import re
import pytest
from app.services import topics, mailer, watch_service
from adapter_test_support import http_adapter
from test_topics_feature import FakeFirestore, topic_payload, run_payload


@pytest.fixture
def public_topics(http_adapter, monkeypatch):
    h = http_adapter
    h.topic_db = FakeFirestore()
    monkeypatch.setattr(topics, "db_firestore", h.topic_db)
    monkeypatch.setenv("WATCH_UNSUBSCRIBE_SECRET", "test-only-secret")
    monkeypatch.setenv("SMTP_HOST", "mail.example.test")
    monkeypatch.setenv("MAIL_FROM", "sender@example.test")
    h.send = AsyncMock(return_value=True)
    monkeypatch.setattr(mailer, "send_message", h.send)
    return h


def publish(h, slug, **changes):
    topic = topics.create_topic(
        topic_payload(slug=slug, **changes), actor_uid="admin", db=h.topic_db
    )
    topics.create_run(topic["id"], run_payload(), actor_uid="admin", db=h.topic_db)
    return topic


def test_hub_and_sitemap_distinguish_noindex_from_archive_or_unpublished(public_topics):
    h = public_topics
    publish(h, "active-topic", title='<img src=x onerror="alert(1)"> Active')
    paused = publish(h, "paused-topic")
    h.topic_db.documents[(topics.TOPICS_COLLECTION, paused["id"])]["status"] = "paused"
    noindex = publish(h, "noindex-topic")
    h.topic_db.documents[(topics.TOPICS_COLLECTION, noindex["id"])]["seo"][
        "noindex"
    ] = True
    archived = publish(h, "archived-topic")
    h.topic_db.documents[(topics.TOPICS_COLLECTION, archived["id"])][
        "status"
    ] = "archived"
    topics.create_topic(
        topic_payload(slug="unpublished-topic"), actor_uid="admin", db=h.topic_db
    )
    hub = h.client.get("/topics")
    sitemap = h.client.get("/sitemap-topics.xml")
    assert hub.status_code == sitemap.status_code == 200
    for slug in ("active-topic", "paused-topic", "noindex-topic"):
        assert "/topics/" + slug in hub.text
    for slug in ("active-topic", "paused-topic"):
        assert "/topics/" + slug in sitemap.text
    for slug in ("archived-topic", "unpublished-topic"):
        assert "/topics/" + slug not in hub.text + sitemap.text
    assert "/topics/noindex-topic" not in sitemap.text
    body = hub.text.split("</head>", 1)[1]
    assert "<img src=x onerror=" not in body and "&lt;img" in body


def test_follow_neutral_response_confirmation_escaping_and_unsubscribe(public_topics):
    h = public_topics
    topic = publish(h, "follow-topic", title='<img src=x onerror="alert(1)"> Topic')
    first = h.client.post(
        "/api/topics/follow-topic/follow", json={"email": "Reader@example.test"}
    )
    assert first.status_code == 200, first.text
    assert not topics.list_followers(topic["id"], db=h.topic_db)
    assert h.send.await_count == 1
    message = h.send.call_args.args[0]
    assert message["From"] == "sender@example.test"
    # Follow the actual mail link; POST generated and stored the challenge.
    plain = message.get_body(preferencelist=("plain",)).get_content()
    confirm_url = re.search(r"Confirm: (\S+)", plain).group(1)
    token = parse_qs(urlparse(confirm_url).query)["token"][0]
    response = h.client.get("/topic-follow/confirm", params={"token": token})
    assert response.status_code == 200, response.text
    assert "<img" not in response.text and "&lt;img" in response.text
    assert (
        topics.list_followers(topic["id"], db=h.topic_db)[0]["email"]
        == "reader@example.test"
    )
    repeat = h.client.post(
        "/api/topics/follow-topic/follow", json={"email": "Reader@example.test"}
    )
    assert repeat.json() == first.json() and h.send.await_count == 1
    assert (
        h.client.get("/topic-follow/confirm", params={"token": token}).status_code
        == 400
    )
    unsubscribe = topics.make_unsubscribe_token(topic["id"], "reader@example.test")
    for _ in range(2):
        assert (
            h.client.get(
                "/topic-follow/unsubscribe", params={"token": unsubscribe}
            ).status_code
            == 200
        )
    assert topics.list_followers(topic["id"], db=h.topic_db) == []


@pytest.mark.parametrize(
    "endpoint", ["/topic-follow/confirm", "/topic-follow/unsubscribe"]
)
@pytest.mark.parametrize("kind", ["invalid", "expired", "wrong_type", "wrong_action"])
def test_topic_tokens_reject_without_writes(public_topics, endpoint, kind):
    h = public_topics
    topic = publish(h, "token-topic")
    token = "invalid"
    if kind == "expired":
        token = topics.make_unsubscribe_token(
            topic["id"],
            "reader@example.test",
            now=datetime.now(timezone.utc) - timedelta(days=100),
        )
    if kind == "wrong_type":
        token = watch_service.sign_token_payload(
            {"sid": "S" * 16, "em": "reader@example.test", "un": 1}
        )
    if kind == "wrong_action":
        token = (
            topics.make_unsubscribe_token
            if endpoint.endswith("confirm")
            else topics.make_confirm_token
        )(topic["id"], "reader@example.test")
    before = deepcopy(h.topic_db.documents)
    response = h.client.get(endpoint, params={"token": token})
    assert response.status_code == (410 if kind == "expired" else 400), response.text
    assert h.topic_db.documents == before
    assert "noindex" in response.headers["x-robots-tag"]
