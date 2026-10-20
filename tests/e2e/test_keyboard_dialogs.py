"""The keyboard's edge for every layer with fields (Apple audit F8): with the
iOS keyboard up, a dialog covers only what is visible, so the button under
the field is never behind the keyboard. Chromium opens no keyboard; the
visual viewport Safari reports is stood in (test_mobile_navigation)."""
import re

from playwright.sync_api import expect

from test_phase4_frontend import _real_firebase_page, phase4_server  # noqa: F401
from test_mobile_navigation import FAKE_VISUAL_VIEWPORT

KEYBOARD = 420


def _reach(page, selector):
    """The action as the user gets to it: scrolled into view inside its layer."""
    page.wait_for_function("() => !document.getAnimations().some(a => a.playState === 'running')")
    action = page.locator(selector).first
    action.evaluate("el => el.scrollIntoView({block: 'nearest'})")
    return action.bounding_box()


def test_login_settings_and_memory_end_at_the_keyboard(browser, phase4_server):
    context, page = _real_firebase_page(browser, phase4_server, initial_uid=None, has_touch=True,
                                        init_script=FAKE_VISUAL_VIEWPORT)
    try:
        page.set_viewport_size({"width": 390, "height": 820})
        page.locator("#authTopLoginBtn").tap()
        expect(page.locator("#loginModal")).to_be_visible()
        page.locator("#loginEmail").focus()
        page.evaluate(f"() => window.__keyboard({KEYBOARD})")
        expect(page.locator("body")).to_have_class(re.compile(r"\bkeyboard-open\b"))
        dialog = page.locator("#loginModal").bounding_box()
        assert abs(dialog["y"] + dialog["height"] - KEYBOARD) <= 1
        submit = _reach(page, "#loginForm button[type=submit]")
        assert submit["y"] + submit["height"] <= KEYBOARD + 1
        # Safari pans the visible area: the dialog moves with it.
        page.evaluate(f"() => window.__keyboard({KEYBOARD}, 140, 'scroll')")
        page.wait_for_function("() => Math.abs(document.getElementById('loginModal').getBoundingClientRect().top - 140) <= 1")
        # Keyboard gone: the dialog is the whole screen again.
        page.evaluate("() => { document.activeElement.blur(); window.__keyboard(820, 0); }")
        page.wait_for_function("() => Math.abs(document.getElementById('loginModal').getBoundingClientRect().bottom - 820) <= 1")
        assert page.evaluate("document.getElementById('loginModal').style.getPropertyValue('--keyboard-height')") == ""
        page.keyboard.press("Escape")

        page.evaluate("() => window.__switchE2EUser('account-a')")
        page.wait_for_function("() => window.__consensioAuthState?.uid === 'account-a'")
        page.evaluate("() => document.getElementById('editSystemPromptBtn').click()")
        expect(page.locator("#systemPromptModal")).to_be_visible()
        page.locator("#settingsTabMemory").click()
        field = page.locator("#systemPromptModal textarea:visible").first
        field.focus()
        page.evaluate(f"() => window.__keyboard({KEYBOARD})")
        page.wait_for_function(f"() => Math.abs(document.getElementById('systemPromptModal').getBoundingClientRect().bottom - {KEYBOARD}) <= 1")
        # Safari brings the focused field into view inside the panel.
        box = _reach(page, "#systemPromptModal textarea:visible")
        assert box["y"] >= 0 and box["y"] + min(box["height"], 60) <= KEYBOARD
        page.evaluate("() => { document.activeElement.blur(); window.__keyboard(820, 0); }")
        page.keyboard.press("Escape")

        page.evaluate("() => { document.getElementById('memoryEditBackdrop').hidden = false; }")
        page.locator("#memoryEditCorrection").focus()
        page.evaluate(f"() => window.__keyboard({KEYBOARD})")
        page.wait_for_function(f"() => document.getElementById('memoryEditBackdrop').getBoundingClientRect().bottom <= {KEYBOARD} + 1")
        submit = _reach(page, ".memory-edit-submit")
        assert submit["y"] + submit["height"] <= KEYBOARD + 1
    finally:
        context.close()
