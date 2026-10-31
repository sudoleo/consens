"""A shared Agent answer shows its reviewers' notes (since 2026-10-31).

The snapshot is written to the emulator as the server would publish it
(share_snapshots.build_agent_pending_result → _build_share_document); the
page is the real /s/ page of the app server.
"""
import hashlib
import os
import uuid

import pytest
from google.auth.credentials import AnonymousCredentials
from google.cloud import firestore as google_firestore
from playwright.sync_api import expect

from app.core.e2e_profile import E2E_PROJECT_ID, assert_safe_e2e_environment
from app.services import share_snapshots
from test_phase4_frontend import phase4_server

ANSWER = ("Yes. It sends science data every day. [S1]\n\n"
          "Its mirror has degraded by less than one percent since launch.")
FIRST = "It sends science data every day. [S1]"
SECOND = "Its mirror has degraded by less than one percent since launch."


def _digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _turn():
    claims = [
        {"anchor": FIRST, "audit": True, "kind": "wrong", "agree": [], "dissent": [
            {"model": "OpenAI", "kind": "doubtful", "note": "NASA reports **weekly** downlinks, not daily ones.",
             "source": "https://www.nasa.gov/webb-status", "mark": 1},
            {"model": "Gemini", "kind": "wrong", "note": "The mission plan names two contacts a day, not one.",
             "mark": 2}]},
        {"anchor": SECOND, "audit": True, "kind": "incomplete", "agree": [], "dissent": [
            {"model": "Gemini", "kind": "incomplete", "note": "It leaves out the 2022 micrometeoroid hit.",
             "mark": 3}]},
    ]
    review = {
        "version": 1, "mode": "audit", "status": "succeeded", "answer_hash": _digest(ANSWER), "answer_version": 1,
        "comparisons": [], "versions": [],
        "audit": {"reviewers": [
            {"provider": "openai", "provider_label": "OpenAI", "model": {"label": "GPT-6 Luna"}, "status": "completed"},
            {"provider": "gemini", "provider_label": "Gemini", "model": {"label": "Gemini 3.5 Flash"},
             "status": "completed"},
        ], "claims": claims, "unplaced": [], "process": []},
    }
    return {"id": "2" * 32, "status": "completed", "execution_mode": "agent",
            "question": "Is the James Webb telescope still working?", "consensus": ANSWER,
            "sources": [{"id": "S1", "title": "NASA Webb", "url": "https://science.nasa.gov/webb"}],
            "consensus_model": "anthropic/claude-sonnet-5.5", "agent_settings": {"label": "Claude Sonnet 5.5"},
            "agent_review": review}


@pytest.fixture
def shared_page():
    assert os.environ.get("E2E_TEST_MODE") == "1", "Native tests require the explicit demo profile"
    assert_safe_e2e_environment(os.environ)
    db = google_firestore.Client(project=E2E_PROJECT_ID, credentials=AnonymousCredentials())
    uid = f"share-notes-{uuid.uuid4().hex}"
    payload = share_snapshots.build_agent_pending_result(uid, _turn())
    document = share_snapshots._build_share_document(uid, payload, visibility="public")
    share_id = share_snapshots.generate_share_id()
    db.collection(share_snapshots.SHARES_COLLECTION).document(share_id).set(document)
    try:
        yield share_snapshots.share_path(document["slug"], share_id)
    finally:
        db.collection(share_snapshots.SHARES_COLLECTION).document(share_id).delete()


@pytest.mark.parametrize("width,scheme", [(390, "light"), (1280, "dark")])
def test_the_notes_open_from_the_answer_and_name_who_noted_what(browser, phase4_server, shared_page, width, scheme):
    context = browser.new_context(viewport={"width": width, "height": 900}, color_scheme=scheme)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        page.goto(phase4_server + shared_page, wait_until="domcontentloaded")
        reviewers = page.locator(".share-reviewers")
        expect(reviewers.locator(".share-models-label")).to_have_text("Reviewed by")
        expect(reviewers.locator(".share-models-stack-mark")).to_have_count(2)
        teaser = page.locator("#diffTeaser")
        expect(teaser).to_contain_text("The reviewers noted 2 passages of this answer.")
        teaser.click()
        notes = page.locator("#differencesView")
        expect(notes).to_be_visible()
        expect(page.locator("#consensusView")).to_be_hidden()
        expect(page.locator("#toggleDifferencesView")).to_have_attribute("aria-pressed", "true")
        expect(notes.locator("h2")).to_be_focused()
        expect(notes.locator(".diff-verdict")).to_have_text("2 passages noted by 2 AI reviewers.")
        cards = notes.locator(".diff-card")
        expect(cards).to_have_count(2)
        # In the answer's order, each in the colour of its most serious note.
        first, second = cards.nth(0), cards.nth(1)
        expect(first).to_have_class("diff-card is-note is-major")
        expect(second).to_have_class("diff-card is-note")
        expect(first.locator(".diff-answer-mark")).to_have_text("It sends science data every day.")
        expect(first.locator(".share-note")).to_have_count(2)
        expect(first.locator(".share-note-kind")).to_have_text(["Doubtful", "Wrong"])
        expect(first.locator(".diff-position-name")).to_have_text(["GPT-6 Luna", "Gemini 3.5 Flash"])
        expect(first.locator(".share-note-source")).to_have_text("nasa.gov")
        paints = [card.locator(".diff-answer-mark").evaluate("el => getComputedStyle(el).backgroundColor")
                  for card in (first, second)]
        assert paints[0] != paints[1], paints
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
        page.screenshot(path=f"test-results/share-notes-{width}-{scheme}.png", full_page=True)
        page.locator("#toggleConsensusView").click()
        expect(page.locator("#consensusView")).to_be_visible()
        assert not errors
    finally:
        context.close()
