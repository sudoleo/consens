"""The demo behind the landing's hero (/app?demo=1) plays the Agent's one mode.

Since 2026-10-31 the Agent has one mode for every account: one AI does the
work, the AIs of the Daily lineup follow it and review its answer. The demo
(static/demo.js) plays that turn on the live surfaces, locally, without a
request: the reviewers beside the clock, the agent asking them once, the
review of the written answer ("Reviewing the answer…", Notes waiting), then
their marks, Notes and Answers. No score, no judge.
"""
import pytest
from playwright.sync_api import expect

from test_phase4_frontend import _real_firebase_page, phase4_server  # noqa: F401


@pytest.mark.parametrize("width", [1440, 390])
def test_the_demo_plays_a_reviewed_agent_turn(browser, phase4_server, width):
    requests = []
    context, page = _real_firebase_page(browser, phase4_server, initial_uid=None, path="/app?demo=1",
        before_goto=lambda page: page.on("request", lambda request: requests.append(request.url)))
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        page.set_viewport_size({"width": width, "height": 900})
        expect(page.locator("#threadAskText")).to_contain_text("heat pump", timeout=30000)
        # The reviewers follow from the first step: their marks stand beside
        # the clock while the agent works.
        page.wait_for_function("""() => document.querySelectorAll(
            '#agentAnswerActivity .agent-inline-models .agent-inline-model').length === 3""", timeout=15000)
        # The agent asks them once; then it writes, and they review exactly
        # that text: the row under it waits with Notes, the head says so.
        page.wait_for_function("""() => {
            const body = document.getElementById('agentAnswerBody');
            const status = document.querySelector('.agent-review > .agent-review-status');
            const notes = document.querySelector('.agent-review .agent-evidence-link[data-section="differences"]');
            const head = document.querySelector('#agentAnswerActivity .agent-activity-title');
            return body?.classList.contains('is-answer-checking') && status?.textContent === 'Reviewing the answer…'
              && notes?.disabled && /^Reviewing/.test(head?.textContent || '');
        }""", polling=50, timeout=30000)
        # The end: the reviewers' marks in the answer, their Notes and the
        # Answers of the AIs the agent asked, and the offer to sign up.
        expect(page.locator("#postDemoLoginPrompt")).to_be_visible(timeout=30000)
        marks = page.locator("#agentAnswerBody .cx-claim.is-audit")
        expect(marks).to_have_count(3)
        kinds = marks.evaluate_all("""marks => marks.map(mark =>
            ['is-major', 'is-split', 'is-minor'].find(kind => mark.classList.contains(kind)))""")
        assert kinds == ["is-major", "is-split", "is-minor"], kinds
        links = page.locator(".agent-review .agent-evidence-link")
        assert links.evaluate_all("links => links.map(link => link.getAttribute('aria-label'))") == ["Notes 3", "Answers 3"]
        expect(page.locator("#agentAnswerActivity .agent-activity-title")).to_contain_text("Thought for")
        # No score and no judge any more.
        expect(page.locator(".agent-agreement")).to_have_count(0)
        expect(page.locator("#agentAnswer")).not_to_contain_text("/100")
        expect(page.locator("#agentAnswerActivity")).not_to_contain_text("Answer check")
        # Notes open the reviewers' notes in the reader, with the wrong one.
        links.first.click()
        expect(page.locator("#modelAnswerReader")).to_be_visible()
        expect(page.locator("#answerReaderInspector")).to_contain_text(
            "The question says only the walls were insulated in 2015.")
        expect(page.locator("#answerReaderInspector")).to_contain_text("1 wrong")
        page.keyboard.press("Escape")
        expect(page.locator("#modelAnswerReader")).not_to_be_visible()
        # Answers open what the three AIs answered when the agent asked.
        links.nth(1).click()
        expect(page.locator("#modelAnswerReader")).to_be_visible()
        expect(page.locator("#modelAnswerReader")).to_contain_text("heat-loss calculation")
        page.keyboard.press("Escape")
        # Local only: the demo asks no model and saves nothing.
        assert not [url for url in requests if "/agent" in url and "/agent/models" not in url], requests
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
        assert errors == []
    finally:
        context.close()
