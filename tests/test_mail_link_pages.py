"""The pages behind mail links are pages of the site (Apple audit K3, K6).

They name the watch, act only on the button (a GET only asks) and offer the
way on: after pausing "Resume watch" with its own token, and "Open Watches".
Firestore is the in-memory FakeDb; no mail is sent.
"""
from copy import deepcopy
from datetime import datetime, timezone
from html import unescape
from unittest.mock import patch
from urllib.parse import quote
import re

import pytest

from adapter_test_support import http_adapter  # noqa: F401 (fixture)
from test_watch_http_contract import watch_http  # noqa: F401 (fixture)

from app.services import watch_service


def _form_action(page):
    match = re.search(r'<form method="post" action="([^"]*)"', page)
    return unescape(match.group(1)) if match else None

def test_pause_link_page_names_the_watch_and_offers_resume_and_watches(watch_http):
    h = watch_http
    question = "Will the EU publish final guidance for general-purpose AI models?"
    h.watch_db.stores["shares"][h.share_id]["question"] = question
    token = watch_service.make_unsubscribe_token(h.watch["id"])
    before = deepcopy(dict(h.watch_db.stores))
    page = h.client.get("/watch/unsubscribe", params={"token": token})
    assert page.status_code == 200
    assert {k: v for k, v in h.watch_db.stores.items() if v} == {k: v for k, v in before.items() if v}
    text = page.text
    # A public page of the site: its stylesheet, its navigation, its footer.
    assert "public-shell.css" in text and 'class="site-nav' in text and "<footer" in text
    assert "system-ui" not in text
    assert question in text and "Pause this watch?" in text
    assert 'href="/app/watches"' in text and _form_action(text).startswith("/watch/unsubscribe?token=")
    assert page.headers["cache-control"] == "no-store"

    done = h.client.post("/watch/unsubscribe", params={"token": token})
    assert done.status_code == 200 and "Watch paused" in done.text and question in done.text
    assert h.watch_db.stores[watch_service.WATCHES_COLLECTION][h.watch["id"]]["status"] == "paused"
    resume_action = _form_action(done.text)
    assert resume_action.startswith("/watch/resume?token=")

    # Opening the pause link again tells the state instead of asking again.
    again = h.client.get("/watch/unsubscribe", params={"token": token})
    assert "This watch is paused" in again.text and _form_action(again.text) == resume_action

    with patch("app.api.routers.watch.get_user_tier", return_value="free"):
        resumed = h.client.post(resume_action)
    assert resumed.status_code == 200 and "Watch resumed" in resumed.text
    stored = h.watch_db.stores[watch_service.WATCHES_COLLECTION][h.watch["id"]]
    assert stored["status"] == "active" and stored["next_run_at"] > datetime.now(timezone.utc)
    assert _form_action(resumed.text) is None and 'href="/app/watches"' in resumed.text

def test_resume_link_only_asks_and_tokens_keep_their_kind(watch_http):
    h = watch_http
    watch_id = h.watch["id"]
    watch_service.pause_watch("owner", watch_id, db=h.watch_db)
    resume = watch_service.make_resume_token(watch_id)
    page = h.client.get("/watch/resume", params={"token": resume})
    assert page.status_code == 200 and "Resume this watch?" in page.text
    assert h.watch_db.stores[watch_service.WATCHES_COLLECTION][watch_id]["status"] == "paused"
    assert _form_action(page.text) == f"/watch/resume?token={quote(resume, safe='')}"
    # A pause link never resumes and a resume link never pauses.
    with pytest.raises(watch_service.WatchError):
        watch_service.parse_resume_token(watch_service.make_unsubscribe_token(watch_id))
    with pytest.raises(watch_service.WatchError):
        watch_service.parse_unsubscribe_token(resume)
    bad = h.client.get("/watch/resume", params={"token": "garbage"})
    assert bad.status_code == 400 and "This link no longer works" in bad.text

def test_resume_link_respects_the_owner_limit_and_a_reached_goal(watch_http, monkeypatch):
    h = watch_http
    watch_id = h.watch["id"]
    watch_service.pause_watch("owner", watch_id, db=h.watch_db)
    resume = watch_service.make_resume_token(watch_id)
    with patch.object(watch_service, "_check_active_limit",
                      side_effect=watch_service.WatchError("limit_reached", "Active watch limit reached.")), \
            patch("app.api.routers.watch.get_user_tier", return_value="free"):
        full = h.client.post("/watch/resume", params={"token": resume})
    assert full.status_code == 409 and "No free watch slot" in full.text
    assert h.watch_db.stores[watch_service.WATCHES_COLLECTION][watch_id]["status"] == "paused"

    h.watch_db.stores[watch_service.WATCHES_COLLECTION][watch_id]["status"] = watch_service.WATCH_STATUS_RESOLVED
    page = h.client.get("/watch/resume", params={"token": resume})
    assert "This watch reached its goal" in page.text and _form_action(page.text) is None
    # The pause link of an old mail does not turn a reached goal into "paused".
    h.client.post("/watch/unsubscribe", params={"token": watch_service.make_unsubscribe_token(watch_id)})
    assert h.watch_db.stores[watch_service.WATCHES_COLLECTION][watch_id]["status"] == "resolved"
