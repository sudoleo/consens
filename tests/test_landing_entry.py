"""Signed-in visitors who open consens.io land in the app, not on the landing.

The app sets the `consens_app` hint cookie while someone is signed in
(static/js/auth-session-state.js). Only entries redirect -- a click inside
the site (logo, "Product", "/#watch") still shows the landing page.
"""

import os

os.environ.setdefault("UNIT_TEST_MODE", "1")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routers import pages


def _client():
    app = FastAPI()
    app.include_router(pages.router)
    return TestClient(app)


def _redirects(headers=None, cookie=True, path="/"):
    client = _client()
    if cookie:
        client.cookies.set(pages.APP_HINT_COOKIE, "1")
    response = client.get(path, headers=headers or {}, follow_redirects=False)
    return response


def test_a_signed_in_entry_goes_straight_to_the_app():
    for site in ("none", "cross-site"):
        response = _redirects({"Sec-Fetch-Site": site})
        assert response.status_code == 302
        assert response.headers["location"] == "/app"
        assert response.headers["cache-control"] == "private, no-store"
        assert "Cookie" in response.headers["vary"]


def test_the_query_survives_the_redirect():
    response = _redirects({"Sec-Fetch-Site": "none"}, path="/?utm_source=mail")
    assert response.headers["location"] == "/app?utm_source=mail"


def test_a_click_inside_the_site_still_shows_the_landing(monkeypatch):
    monkeypatch.setattr(pages, "landing_pulse_preview", lambda: None)
    response = _redirects({"Sec-Fetch-Site": "same-origin"})
    assert response.status_code == 200
    assert "Cookie" in response.headers["vary"]


def test_without_fetch_metadata_a_same_site_referer_counts_as_a_click(monkeypatch):
    monkeypatch.setattr(pages, "landing_pulse_preview", lambda: None)
    assert _redirects({"Referer": "http://testserver/app"}).status_code == 200
    assert _redirects({"Referer": "https://www.google.com/"}).status_code == 302


def test_no_hint_or_an_explicit_home_shows_the_landing(monkeypatch):
    monkeypatch.setattr(pages, "landing_pulse_preview", lambda: None)
    assert _redirects({"Sec-Fetch-Site": "none"}, cookie=False).status_code == 200
    assert _redirects({"Sec-Fetch-Site": "none"}, path="/?home").status_code == 200
