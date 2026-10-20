"""Notch and home indicator (Apple audit F12, F13). /app reaches under them
(viewport-fit=cover) and keeps its controls clear of them; behind the phone
bar the answer does not read through between the buttons. Chromium stands in
an iPhone's safe areas through CDP (Emulation.setSafeAreaInsetsOverride)."""
import io
import re

from PIL import Image
from playwright.sync_api import expect

from test_phase4_frontend import _real_firebase_page, phase4_server  # noqa: F401
from test_mobile_navigation import seed_long_answer


def _phone(browser, server, viewport, insets):
    context, page = _real_firebase_page(browser, server, has_touch=True)
    context.new_cdp_session(page).send("Emulation.setSafeAreaInsetsOverride", {"insets": insets})
    page.set_viewport_size(viewport)
    page.emulate_media(reduced_motion="reduce")
    seed_long_answer(page)
    page.wait_for_function("() => !document.body.classList.contains('composer-animating') && !document.body.classList.contains('composer-gliding')")
    return context, page


def test_portrait_keeps_the_home_indicator_free_and_the_bar_solid(browser, phase4_server):
    context, page = _phone(browser, phase4_server, {"width": 390, "height": 844},
                           {"top": 47, "bottom": 34, "left": 0, "right": 0})
    try:
        assert "viewport-fit=cover" in page.locator('meta[name="viewport"]').get_attribute("content")
        field = page.locator(".chat-input-container").bounding_box()
        assert field["y"] + field["height"] <= 844 - 34
        # The composer's ground still reaches the edge under the home indicator.
        section = page.locator(".input-section").bounding_box()
        assert abs(section["y"] + section["height"] - 844) <= 1
        menu = page.locator("#toggleSidebarButton").bounding_box()
        assert menu["y"] >= 47

        # Reading: a line of the answer passes under the bar while it shows.
        page.evaluate("window.scrollTo(0, 700)")
        page.wait_for_timeout(200)
        page.evaluate("window.scrollBy(0, -90)")
        page.wait_for_function("() => document.querySelector('.app-mobile-header').classList.contains('is-scrolled')"
                               " && getComputedStyle(document.querySelector('.app-mobile-header'), '::before').opacity === '1'"
                               " && Math.abs(document.querySelector('.app-mobile-header').getBoundingClientRect().top) < 1")
        actions = page.locator("#mobileConversationActions").bounding_box()
        # Between the menu mark and the actions, as high as the buttons: the
        # ground, nothing of the text beneath it (the fade starts below them).
        clip = {"x": menu["x"] + menu["width"] + 8, "y": menu["y"], "width": actions["x"] - menu["x"] - menu["width"] - 16,
                "height": menu["height"]}
        assert clip["width"] > 100
        image = Image.open(io.BytesIO(page.screenshot(clip=clip))).convert("L")
        low, high = image.getextrema()
        assert high - low <= 6, (low, high)

        # A notice stands above the composer, clear of the home indicator.
        page.evaluate("() => App.toast({message: 'Chat deleted', duration: 60000})")
        toast = page.locator(".toast").first
        expect(toast).to_be_visible()
        box = toast.bounding_box()
        assert box["y"] + box["height"] <= page.locator(".chat-input-container").bounding_box()["y"]
    finally:
        context.close()


def test_landscape_keeps_the_notch_free(browser, phase4_server):
    context, page = _phone(browser, phase4_server, {"width": 844, "height": 390},
                           {"top": 0, "bottom": 21, "left": 47, "right": 47})
    try:
        field = page.locator(".chat-input-container").bounding_box()
        assert field["x"] >= 47 and field["x"] + field["width"] <= 844 - 47
        assert field["y"] + field["height"] <= 390 - 21
        text = page.locator(".thread-history-turn p").first.bounding_box()
        assert text["x"] >= 47
        page.evaluate("window.scrollTo(0, 0)")
        page.locator("#toggleSidebarButton").tap()
        expect(page.locator("#appSidebar")).to_have_class(re.compile(r"\bactive\b"))
        row = page.locator("#newRunButton").bounding_box()
        assert row["x"] >= 47
    finally:
        context.close()
