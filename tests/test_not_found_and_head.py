"""Unknown pages answer with HTML, HEAD works wherever GET does.

Audit 2026-10-05, P10/P11: unknown paths answered browsers with raw JSON,
/impressum and /datenschutz were 404s, and HEAD on /, /benchmark or the
sitemap was a 405 (uptime monitors and link checkers use HEAD).
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

import main
from app.api.routers import api_v1, topics as topics_router
from app.core.rate_limit import limiter

BROWSER = {"Accept": "text/html,application/xhtml+xml,*/*;q=0.8"}


def _client():
    limiter.reset()
    return TestClient(main.app, follow_redirects=False)


def test_unknown_page_shows_the_html_404_to_a_browser():
    response = _client().get("/no-such-page", headers=BROWSER)

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("text/html")
    assert "Page not found" in response.text
    assert response.headers["x-robots-tag"] == "noindex, noarchive"


def test_unknown_path_keeps_the_json_error_for_scripts():
    response = _client().get("/api/no-such-endpoint")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_a_post_to_an_unknown_path_never_gets_html():
    response = _client().post("/no-such-page", headers=BROWSER, json={})

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_wrong_method_on_a_known_route_stays_405():
    response = _client().delete("/privacy", headers=BROWSER)

    assert response.status_code == 405


def test_missing_topic_shows_the_html_404_to_a_browser_and_json_to_scripts():
    with patch.object(topics_router.topics, "resolve_topic_by_slug", return_value=(None, False)):
        client = _client()
        page = client.get("/topics/no-such-topic", headers=BROWSER)
        script = client.get("/topics/no-such-topic")

    assert page.status_code == 404
    assert "Page not found" in page.text
    assert script.status_code == 404
    assert script.json() == {"error": "Topic not found"}


def test_german_legal_addresses_redirect_to_the_english_pages():
    client = _client()

    impressum = client.get("/impressum")
    datenschutz = client.get("/datenschutz")

    assert (impressum.status_code, impressum.headers["location"]) == (301, "/imprint")
    assert (datenschutz.status_code, datenschutz.headers["location"]) == (301, "/privacy")


def test_head_answers_like_get_without_a_body():
    client = _client()
    for path in ("/privacy", "/imprint", "/robots.txt"):
        get = client.get(path)
        head = client.head(path)
        assert get.status_code == 200, path
        assert head.status_code == 200, path
        assert head.content == b"", path
        assert head.headers["content-type"] == get.headers["content-type"], path


def test_head_is_not_added_to_the_documented_api():
    # The router itself: newer FastAPI keeps included routers out of app.routes.
    for route in api_v1.router.routes:
        assert "HEAD" not in (getattr(route, "methods", None) or set()), route.path
    for operations in main.app.openapi()["paths"].values():
        assert "head" not in operations
