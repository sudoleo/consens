"""A finger's selection gets the same menu (Apple audit F7): on a phone a
selection in the answer shows "Ask about this" without any mouseup, under the
selection handle and clear of the system's own menu above it."""
from playwright.sync_api import expect

from test_phase4_frontend import _real_firebase_page, phase4_server  # noqa: F401
from test_touch_targets import _agent_answer_with_sources, _pro_account

# What a finger leaves behind: a selection, no mouseup, no Shift.
SELECT_WORDS = """([selector, first, last]) => {
  const node = [...document.querySelector(selector).querySelectorAll('p')].map(p => p.firstChild).find(n => n && n.nodeType === 3);
  const range = document.createRange();
  range.setStart(node, node.data.indexOf(first));
  range.setEnd(node, node.data.indexOf(last) + last.length);
  const selection = getSelection();
  selection.removeAllRanges();
  selection.addRange(range);
  const r = range.getBoundingClientRect();
  return {top: r.top, bottom: r.bottom};
}"""


def test_a_touch_selection_brings_the_menu_and_asks_about_it(browser, phase4_server):
    context, page = _real_firebase_page(browser, phase4_server, has_touch=True)
    try:
        page.set_viewport_size({"width": 390, "height": 800})
        _pro_account(page)
        _agent_answer_with_sources(page)
        menu = page.locator("#memorySelectionMenu")
        # The finger lands in the answer and holds: a long press, which sends
        # no mouse events at all (a tap's compatibility mouseup would hide
        # what is being tested here).
        page.locator("#agentAnswerBody p").first.dispatch_event("pointerdown", {"pointerType": "touch", "isPrimary": True})
        page.evaluate(SELECT_WORDS, ["#agentAnswerBody", "race", "Monaco"])
        expect(menu).to_be_visible()
        expect(menu.get_by_role("button", name="Ask about this")).to_be_visible()
        page.wait_for_function("() => getComputedStyle(document.getElementById('memorySelectionMenu')).visibility === 'visible'")
        page.wait_for_timeout(100)
        box = menu.bounding_box()
        rect = page.evaluate("() => { const r = getSelection().getRangeAt(0).getBoundingClientRect(); return {top: r.top, bottom: r.bottom}; }")
        # Under the selection handle, not over the selection (the system menu's place).
        assert box["y"] >= rect["bottom"] + 20, (box, rect)
        menu.get_by_role("button", name="Ask about this").tap()
        expect(page.locator("#composerQuote")).to_be_visible()
        expect(page.locator("#composerQuote")).to_contain_text("race starts in Monaco")
        expect(menu).to_be_hidden()

        # A selection that goes takes the menu with it.
        page.locator("#agentAnswerBody p").first.dispatch_event("pointerdown", {"pointerType": "touch", "isPrimary": True})
        page.evaluate(SELECT_WORDS, ["#agentAnswerBody", "climbs", "Turbie"])
        expect(menu).to_be_visible()
        page.evaluate("() => getSelection().removeAllRanges()")
        expect(menu).to_be_hidden()
    finally:
        context.close()
