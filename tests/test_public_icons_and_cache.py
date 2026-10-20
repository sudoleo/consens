"""Public pages look the same every time and come quickly (Apple audit I7, I12, I13).

Cached favicons are never throttled, only sharp icons are kept, and rendered
Topic pages are kept for a short while. No request leaves the process.
"""
from unittest.mock import Mock, patch
import io

from PIL import Image

from adapter_test_support import http_adapter  # noqa: F401 (fixture)

from app.services import favicons


def _png(size):
    buffer = io.BytesIO()
    Image.new("RGBA", (size, size), (0, 0, 0, 255)).save(buffer, format="PNG")
    return buffer.getvalue()

def test_favicon_proxy_only_keeps_sharp_icons(monkeypatch):
    def fetch_with(content, content_type="image/png"):
        response = Mock(status_code=200, content=content, headers={"Content-Type": content_type})
        monkeypatch.setattr(favicons.requests, "get", Mock(return_value=response))
        return favicons._fetch("example.com")

    assert fetch_with(_png(32)) == (None, "")
    assert fetch_with(_png(128))[0] == _png(128)
    assert fetch_with(b"<svg xmlns='http://www.w3.org/2000/svg'/>", "image/svg+xml")[0]
    assert favicons.requests.get.call_args.kwargs["params"]["sz"] == "128"

def test_cached_favicons_are_never_throttled(http_adapter, monkeypatch):
    favicons._CACHE.clear()
    lookups = Mock(return_value=(_png(64), "image/png"))
    monkeypatch.setattr(favicons, "_fetch", lookups)
    client = http_adapter.client
    from app.api.routers import topics as topics_router

    for _ in range(topics_router.FAVICON_LOOKUPS_PER_MINUTE + 20):
        response = client.get("/api/topics/favicon", params={"d": "example.com"})
        assert response.status_code == 200 and response.headers["content-type"] == "image/png"
    assert lookups.call_count == 1
    # Fresh domains past the lookup budget get the globe for now, never a 429.
    statuses = set()
    for index in range(topics_router.FAVICON_LOOKUPS_PER_MINUTE + 5):
        response = client.get("/api/topics/favicon", params={"d": f"site{index}.example"})
        statuses.add((response.status_code, response.headers["cache-control"]))
    assert (200, "no-store") in statuses and all(status == 200 for status, _ in statuses)
    favicons._CACHE.clear()

def test_topic_pages_are_served_from_a_short_cache_until_an_admin_change():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.routers import topics as topics_router
    from app.core.rate_limit import limiter
    from app.services import topics
    from test_topics_feature import FakeFirestore, run_payload, topic_payload

    db = FakeFirestore()
    topics_router.invalidate_topic_pages()
    with patch.object(topics, "db_firestore", db):
        topic = topics.create_topic(topic_payload(), actor_uid="admin", db=db)
        topics.create_run(topic["id"], run_payload(), actor_uid="admin", db=db)
        app = FastAPI()
        app.state.limiter = limiter
        app.include_router(topics_router.router)
        client = TestClient(app)
        with patch.object(topics, "list_runs", wraps=topics.list_runs) as reads:
            first = client.get("/topics/gpt-6")
            second = client.get("/topics/gpt-6")
            assert first.status_code == second.status_code == 200
            assert first.text == second.text and reads.call_count == 1
            assert second.headers["cache-control"] == first.headers["cache-control"]
            assert second.headers["content-type"].startswith("text/html")
            topics_router.invalidate_topic_pages()
            client.get("/topics/gpt-6")
            assert reads.call_count == 2
        with patch.object(topics, "list_public_topics", wraps=topics.list_public_topics) as hub_reads:
            client.get("/topics")
            client.get("/topics")
            assert hub_reads.call_count == 1
    topics_router.invalidate_topic_pages()
