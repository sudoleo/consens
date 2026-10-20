"""Layers under a finger (Apple audit F2, F11): what covers the page holds it
still, and the phone menu follows a swipe to close. Chromium has no real
finger here; CDP touch events stand in for one (pointerType "touch")."""
import re

import pytest
from playwright.sync_api import expect

from test_phase4_frontend import _real_firebase_page, phase4_server  # noqa: F401
from test_mobile_navigation import seed_long_answer

STATE = """() => ({
  open: document.querySelector('.sidebar').classList.contains('active'),
  x: new DOMMatrix(getComputedStyle(document.querySelector('.sidebar')).transform).m41,
  dim: Number(getComputedStyle(document.body, '::after').opacity),
  locked: getComputedStyle(document.documentElement).overflowY === 'hidden',
  focus: document.activeElement?.id || '',
  y: Math.round(scrollY),
})"""


def swipe(cdp, page, start, end, steps=8):
    (x0, y0), (x1, y1) = start, end
    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x0, "y": y0, "id": 1}]})
    for i in range(1, steps + 1):
        x = x0 + (x1 - x0) * i / steps
        y = y0 + (y1 - y0) * i / steps
        cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x, "y": y, "id": 1}]})
        page.wait_for_timeout(16)
    # The finger comes to rest before it lifts: no fling, whose stopping tap
    # Chromium would swallow (it is the travelled distance that decides here).
    page.wait_for_timeout(120)
    cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x1, "y": y1, "id": 1}]})


def lift(cdp):
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})


def _reading_page(browser, server):
    context, page = _real_firebase_page(browser, server, has_touch=True)
    page.set_viewport_size({"width": 390, "height": 780})
    seed_long_answer(page)
    page.evaluate("window.scrollTo(0, 400)")
    page.wait_for_timeout(200)
    page.evaluate("window.scrollBy(0, -80)")
    expect(page.locator("#toggleSidebarButton")).to_be_visible()
    return context, page, context.new_cdp_session(page)


def _open_menu(page):
    # A menu on its way out still lies over the menu button.
    page.wait_for_function("""() => { const menu = document.getElementById('appSidebar');
      return menu.getBoundingClientRect().right <= 0 || getComputedStyle(menu).visibility === 'hidden'; }""")
    page.locator("#toggleSidebarButton").tap()
    expect(page.locator("#appSidebar")).to_have_class(re.compile(r"\bactive\b"))
    page.wait_for_function("() => document.getElementById('appSidebar').getBoundingClientRect().left >= -.5")


def test_open_menu_holds_the_page_and_follows_the_finger(browser, phase4_server):
    context, page, cdp = _reading_page(browser, phase4_server)
    try:
        before = page.evaluate(STATE)["y"]
        _open_menu(page)
        state = page.evaluate(STATE)
        assert state["locked"] and state["focus"] == "sidebarToggleInner"
        width = page.locator("#appSidebar").bounding_box()["width"]

        # Up and down in the menu is the list's own; the thread does not move.
        swipe(cdp, page, (150, 520), (150, 260))
        lift(cdp)
        page.wait_for_timeout(300)
        state = page.evaluate(STATE)
        assert state["open"] and state["y"] == before

        # A short swipe to the left: the menu and its dim follow, then settle back.
        swipe(cdp, page, (250, 400), (250 - 0.2 * width, 404))
        held = page.evaluate(STATE)
        assert held["x"] < -0.1 * width and 0.6 < held["dim"] < 1
        lift(cdp)
        settling = page.evaluate(STATE)
        # From where the finger left it, not from a jump.
        assert settling["dim"] < 0.95 and settling["x"] < -10
        page.wait_for_function("() => new DOMMatrix(getComputedStyle(document.getElementById('appSidebar')).transform).m41 === 0")
        assert page.evaluate(STATE)["open"]

        # Past a third: it closes from where it is, focus goes back to the menu button.
        swipe(cdp, page, (250, 400), (250 - 0.45 * width, 400))
        lift(cdp)
        closing = page.evaluate(STATE)
        assert not closing["open"] and closing["x"] < -0.3 * width and closing["dim"] > 0.3
        expect(page.locator("#toggleSidebarButton")).to_be_focused()
        state = page.evaluate(STATE)
        assert not state["locked"] and state["y"] == before

        # The dimmed page takes the same swipe.
        _open_menu(page)
        swipe(cdp, page, (370, 420), (190, 420))
        lift(cdp)
        expect(page.locator("#appSidebar")).not_to_have_class(re.compile(r"\bactive\b"))

        # "Reduce motion": the menu does not travel with the finger (it fades,
        # motion.css), the swipe still closes it.
        page.emulate_media(reduced_motion="reduce")
        _open_menu(page)
        swipe(cdp, page, (250, 400), (250 - 0.45 * width, 400))
        assert page.evaluate(STATE)["x"] == 0
        lift(cdp)
        expect(page.locator("#appSidebar")).not_to_have_class(re.compile(r"\bactive\b"))
    finally:
        context.close()


def test_every_covering_layer_holds_the_page(browser, phase4_server):
    context, page, cdp = _reading_page(browser, phase4_server)
    try:
        locked = "() => getComputedStyle(document.documentElement).overflowY === 'hidden'"
        assert not page.evaluate(locked)
        layers = {
            "dialog": ("App.modalDialog.open(document.getElementById('helpModal'))",
                       "App.modalDialog.close(document.getElementById('helpModal'))"),
            "sentence card": ("document.getElementById('claimSheetBackdrop').hidden = false",
                              "document.getElementById('claimSheetBackdrop').hidden = true"),
            "activity sheet": ("document.body.classList.add('agent-sidebar-sheet')",
                               "document.body.classList.remove('agent-sidebar-sheet')"),
            "memory": ("document.getElementById('memoryEditBackdrop').hidden = false",
                       "document.getElementById('memoryEditBackdrop').hidden = true"),
        }
        for name, (show, hide) in layers.items():
            page.evaluate(f"() => {{ {show}; }}")
            assert page.evaluate(locked), name
            page.evaluate(f"() => {{ {hide}; }}")
            assert not page.evaluate(locked), name
        # A finger on an open dialog's dim does not scroll the thread behind it.
        before = page.evaluate("Math.round(scrollY)")
        page.evaluate("App.modalDialog.open(document.getElementById('helpModal'))")
        swipe(cdp, page, (20, 700), (20, 300))
        lift(cdp)
        page.wait_for_timeout(300)
        assert page.evaluate("Math.round(scrollY)") == before
    finally:
        context.close()
