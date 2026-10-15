"""An open app window learns about a new deploy (static/js/app-update.js).

The page carries the build it was rendered with; /api/build names the build
the server runs now. Both come from the same get_commit_short(), so a window
reloads exactly when a deploy changed the running commit.
"""

import os
from pathlib import Path

os.environ.setdefault("UNIT_TEST_MODE", "1")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routers import pages

ROOT = Path(__file__).resolve().parents[1]


def _client():
    app = FastAPI()
    app.include_router(pages.router)
    return TestClient(app)


def test_the_live_build_is_never_cached(monkeypatch):
    monkeypatch.setattr(pages, "get_commit_short", lambda: "4c542cc")
    response = _client().get("/api/build")
    assert response.status_code == 200
    assert response.json() == {"build": "4c542cc"}
    assert response.headers["cache-control"] == "no-store"


def test_an_unknown_build_stays_empty(monkeypatch):
    # The page then has no build either and app-update.js asks nothing.
    monkeypatch.setattr(pages, "get_commit_short", lambda: "")
    assert _client().get("/api/build").json() == {"build": ""}


def test_the_app_page_carries_the_build_it_was_rendered_with():
    html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    assert 'data-app-build="{{ app_commit | e }}"' in html
    bundles = (ROOT / "static" / "js" / "bundles.json").read_text(encoding="utf-8")
    assert "static/js/app-update.js" in bundles
