"""Every source behind a pill can be opened (Apple audit F6): on a phone the
first tap shows them all as a card, with a mouse a grouped pill lists them at
the pill, a single one still opens its source."""
import re

import pytest
from playwright.sync_api import expect

from test_phase4_frontend import _real_firebase_page, phase4_server  # noqa: F401
from test_touch_targets import _agent_answer_with_sources, _pro_account

SHEET = "#sourceSheet"


def _answer(browser, server, touch, width):
    context, page = _real_firebase_page(browser, server, has_touch=touch)
    # A source opened in its tab never leaves the machine.
    context.route("https://**/*", lambda route: route.fulfill(content_type="text/html", body="<p>source</p>"))
    page.set_viewport_size({"width": width, "height": 800})
    _pro_account(page)
    _agent_answer_with_sources(page)
    return context, page


def test_a_tap_on_a_phone_lists_every_source_of_the_pill(browser, phase4_server):
    context, page = _answer(browser, phase4_server, True, 390)
    try:
        opened = []
        context.on("page", lambda tab: opened.append(tab))
        pills = page.locator("#agentAnswerBody .src-ref")
        group = pills.first
        expect(group).to_contain_text("+2")
        group.tap()
        sheet = page.locator(SHEET)
        expect(sheet).to_be_visible()
        expect(sheet).to_have_class(re.compile(r"\bis-modal\b"))
        expect(sheet.locator(".source-sheet-heading")).to_have_text("3 sources")
        links = sheet.locator("a.source-sheet-link")
        expect(links).to_have_count(3)
        expect(links.nth(1)).to_have_attribute("href", "https://example.org/analysis")
        expect(links.first).to_have_attribute("target", "_blank")
        # Nothing opened by the tap itself; the page behind holds still.
        assert opened == []
        assert page.evaluate("getComputedStyle(document.documentElement).overflowY") == "hidden"
        for row in links.all():
            assert row.bounding_box()["height"] >= 44
        expect(page.locator(".source-sheet-close")).to_be_focused()
        # A tap beside the card closes it.
        page.mouse.click(10, 790)
        expect(sheet).to_be_hidden()
        assert page.evaluate("getComputedStyle(document.documentElement).overflowY") != "hidden"

        # A single source: its title and excerpt-free row, the same way.
        pills.nth(1).tap()
        expect(sheet).to_be_visible()
        expect(sheet.locator(".source-sheet-heading")).to_have_text("Source")
        expect(sheet.locator("a.source-sheet-link")).to_have_count(1)
        page.keyboard.press("Escape")
        expect(sheet).to_be_hidden()
        expect(pills.nth(1)).to_be_focused()
        assert opened == []
    finally:
        context.close()


def _reader_with_sources(page):
    """The answer reader open on a model answer with a grouped pill."""
    page.evaluate("""() => {
      const registry = window.App.runRegistry;
      const providers = window.App.modelPrefs.slice(0, 2).map(p => ({provider: p.key, modelLabel: p.key + ' test model'}));
      const sources = [{id:'S1', title:'UCI regulations', url:'https://www.uci.org/rules'},
        {id:'S2', title:'Analysis', url:'https://example.org/analysis'},
        {id:'S3', title:'Race report', url:'https://news.example.com/report'}];
      const ctx = registry.create({runId:'sheet-reader', question:'Where does the race start?',
        config:{agentMode:true, providers}});
      ctx.status = 'succeeded'; ctx.phase = 'answers_ready';
      providers.forEach(p => { ctx.modelResults[p.provider] = {status:'complete',
        text:'The race starts in Monaco [S1][S2][S3]. ' + 'A readable paragraph. '.repeat(40), sources}; });
      Object.assign(ctx.consensus, {status:'complete', text:'The race starts in Monaco.',
        completedTurn:{turn_id:'sheet-reader-turn', question:ctx.question, consensus:'The race starts in Monaco.'}});
      registry.renderVisible();
    }""")
    page.locator("#agentModeAnswersToggle").click()
    expect(page.locator("#modelAnswerReader")).to_be_visible()
    pill = page.locator("#modelAnswerReader .src-ref").first
    expect(pill).to_contain_text("+2")
    return pill


LOCKED = "getComputedStyle(document.documentElement).overflowY === 'hidden'"


def test_the_list_in_the_reader_goes_with_the_reader(browser, phase4_server):
    # Review 2 N1: the list hung in the reader's <dialog>; when the reader
    # closed under it (Android's back, a layout change), it stayed open out
    # of sight and its backdrop held the page still for good.
    context, page = _real_firebase_page(browser, phase4_server, has_touch=True)
    try:
        page.set_viewport_size({"width": 390, "height": 800})
        pill = _reader_with_sources(page)
        sheet = page.locator(SHEET)
        dialog = page.locator(".answer-reader-dialog")

        # Back, as a close request the page may hold: only the top layer,
        # the list, closes; the reader stays and the pill has the focus.
        pill.tap()
        expect(sheet).to_be_visible()
        dialog.evaluate("el => el.dispatchEvent(new Event('cancel', {cancelable: true}))")
        expect(sheet).to_be_hidden()
        expect(page.locator("#modelAnswerReader")).to_be_visible()
        expect(pill).to_be_focused()

        # Back the browser does not let the page hold: the reader closes,
        # the list with it, the page scrolls, focus is back at the toggle.
        pill.tap()
        expect(sheet).to_be_visible()
        dialog.evaluate("el => el.dispatchEvent(new Event('cancel'))")
        expect(page.locator("#modelAnswerReader")).to_be_hidden()
        expect(sheet).to_be_hidden()
        page.wait_for_function(f"() => !({LOCKED})")
        expect(page.locator("#agentModeAnswersToggle")).to_be_focused()

        # A layout change that closes and re-opens the dialog closes the
        # list too, and leaves the page free.
        page.locator("#agentModeAnswersToggle").click()
        pill.tap()
        expect(sheet).to_be_visible()
        page.set_viewport_size({"width": 1440, "height": 900})
        expect(dialog).to_have_attribute("data-modal", "false")
        expect(sheet).to_be_hidden()
        page.wait_for_function(f"() => !({LOCKED})")
        page.locator("#answerReaderClose").click()
        expect(page.locator("#modelAnswerReader")).to_be_hidden()
        assert not page.evaluate(LOCKED)
    finally:
        context.close()


@pytest.mark.parametrize("width", [1280])
def test_a_click_on_a_grouped_pill_lists_its_sources_at_the_pill(browser, phase4_server, width):
    context, page = _answer(browser, phase4_server, False, width)
    try:
        group = page.locator("#agentAnswerBody .src-ref").first
        group.click()
        sheet = page.locator(SHEET)
        expect(sheet).to_be_visible()
        expect(sheet).not_to_have_class(re.compile(r"\bis-modal\b"))
        expect(sheet.locator("a.source-sheet-link")).to_have_count(3)
        # A menu at the pill: next to it, first source focused, arrows move.
        # It rises 4px into place (overlays.css); measured where it stays,
        # not in the frame the box happens to be read.
        page.wait_for_function("""() => !document.getElementById('sourceSheet').getAnimations()
          .some(a => a.playState === 'running')""")
        pill, card = group.bounding_box(), sheet.bounding_box()
        assert abs(card["y"] - (pill["y"] + pill["height"] + 8)) <= 2 or abs(card["y"] + card["height"] - (pill["y"] - 8)) <= 2
        expect(sheet.locator("a.source-sheet-link").first).to_be_focused()
        page.keyboard.press("ArrowDown")
        expect(sheet.locator("a.source-sheet-link").nth(1)).to_be_focused()
        page.keyboard.press("Escape")
        expect(sheet).to_be_hidden()
        expect(group).to_be_focused()
        assert page.evaluate("getComputedStyle(document.documentElement).overflowY") != "hidden"

        # A single pill still opens its source in a new tab.
        with context.expect_page() as tab:
            page.locator("#agentAnswerBody .src-ref").nth(1).click()
        assert tab.value.url.startswith("https://example.org/") or tab.value.url == "about:blank"
        expect(sheet).to_be_hidden()
    finally:
        context.close()
