"""One mode selector: Agent / Compare (run-mode.js + agent-mode.js).

The Consensus mode left the browser on 2026-10-25 (the pipeline runs on the
server for Watches, the API and topics); a stored "consensus" reads as
unchosen.

The composer around it is the same in every mode (composer.css).

Covers the migration from the old Agent Mode switch, the per-chat family
locks, entitlement, the settings mirror, contextual tools and layout from
320 px to desktop in both themes.
"""
import os
import re
from pathlib import Path

import pytest
from playwright.sync_api import expect

from test_phase4_frontend import phase4_server, _real_firebase_page, _json  # noqa: F401
from test_agent_chat_frontend import CATALOG


def _shot(page, name):
    target = os.environ.get("RUN_MODE_SCREENSHOTS")
    if target:
        Path(target).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(Path(target) / f"{name}.png"))


def choose(page, mode):
    # The mode is the first group in the (+) menu since 2026-10-02.
    page.locator("#attachTrigger").click()
    page.locator(f'#runModeControl [data-value="{mode}"]').click()
    expect(page.locator("#runModeSelect")).to_have_value(mode)


def _signed_in(page, *, agent_access):
    page.route("**/user_status", lambda r: _json(r, {"tier": "pro" if agent_access else "free",
        "is_pro": agent_access, "agent_access": agent_access, "limit": 50, "deep_limit": 5}))
    page.route("**/agent/models", lambda r: _json(r, CATALOG))
    page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")


# The one-time reset of 2026-10-12 (user-settings.js) starts every browser
# from Agent, whatever an older version stored.
@pytest.mark.parametrize("legacy", ["true", "false", None])
def test_legacy_agent_mode_switch_is_reset_once(browser, phase4_server, legacy):
    script = "localStorage.removeItem('runMode'); localStorage.removeItem('consensio.settingsReset');" + (
        f"localStorage.setItem('agentMode', '{legacy}'); localStorage.setItem('autoConsensus', '{legacy}');" if legacy else "")
    context, page = _real_firebase_page(browser, phase4_server, init_script=f"if (!sessionStorage.seeded) {{ {script} sessionStorage.seeded = 1; }}")
    try:
        assert page.evaluate("App.runMode.preference()") == "agent"
        assert page.evaluate("localStorage.getItem('runMode')") is None
        assert page.evaluate("localStorage.getItem('consensio.settingsReset')") == "2026-10-12"
        assert page.evaluate("localStorage.getItem('agentMode')") is None
        assert page.evaluate("localStorage.getItem('autoConsensus')") is None
        assert page.evaluate("typeof window.setAgentMode") == "undefined"
        assert page.evaluate("typeof window.isAgentModeEnabled") == "undefined"
        # Every old control is gone; the one selector remains.
        for gone in ("#composerAgentToggle", "#agentModeMenuSwitch", "#agentModeSwitch", "#autoConsensusToggle", "#chatExecutionMode"):
            expect(page.locator(gone)).to_have_count(0)
        # Without access yet, Agent is the choice but runs (and shows) as Compare.
        expect(page.locator("#runModeSelect")).to_have_value("compare")
    finally:
        context.close()


def test_a_stored_consensus_choice_reads_as_unchosen(browser, phase4_server):
    context, page = _real_firebase_page(browser, phase4_server,
        init_script="if (!sessionStorage.seeded) { localStorage.setItem('runMode', 'consensus'); localStorage.setItem('consensio.settingsReset','2026-10-12'); sessionStorage.seeded = 1; }")
    try:
        _signed_in(page, agent_access=True)
        assert page.evaluate("App.runMode.preference()") == "agent"
        expect(page.locator("#runModeSelect")).to_have_value("agent")
        expect(page.locator('#runModeSelect option[value="consensus"]')).to_have_count(0)
        expect(page.locator('#runModeSetting option[value="consensus"]')).to_have_count(0)
    finally:
        context.close()


@pytest.mark.parametrize("width,dark", [(1440, False), (1440, True), (390, False), (320, True)])
def test_one_selector_drives_mode_tools_and_settings(browser, phase4_server, width, dark):
    context, page = _real_firebase_page(browser, phase4_server,
        init_script="if (!sessionStorage.seeded) { localStorage.setItem('runMode', 'compare'); localStorage.setItem('consensio.settingsReset','2026-10-12'); sessionStorage.seeded = 1; }")
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        page.set_viewport_size({"width": width, "height": 900})
        page.evaluate("dark => { document.body.classList.toggle('dark-mode', dark); document.documentElement.classList.toggle('dark-mode', dark); }", dark)
        _signed_in(page, agent_access=True)
        control = page.locator("#runModeControl")
        # No mode chip in the row: (+) holds the mode, files and options.
        expect(page.locator(".composer-lead .model-picker-display")).to_have_count(0)
        expect(page.locator("#composerSourcesToggle")).to_have_count(0)

        # The menu lists both with one-line descriptions, the current one checked.
        page.locator("#attachTrigger").click()
        expect(control).to_be_visible()
        options = control.locator(".attach-menu-mode")
        expect(options).to_have_count(2)
        expect(control.locator('[data-value="consensus"]')).to_have_count(0)
        expect(control.locator('[data-value="compare"]')).to_have_attribute("aria-pressed", "true")
        expect(control.locator('[data-value="agent"]')).to_contain_text("Beta")
        expect(control.locator('[data-value="compare"] .attach-menu-hint')).to_contain_text("side by side")
        menu = page.locator("#attachMenu").bounding_box()
        assert menu["x"] >= 0 and menu["x"] + menu["width"] <= width + 1
        _shot(page, f"{width}-{'dark' if dark else 'light'}-menu")
        page.keyboard.press("Escape")

        # Compare: the chosen models answer side by side.
        assert page.evaluate("localStorage.getItem('runMode')") == "compare"
        expect(page.locator("#composerModeDescription")).to_contain_text("side by side")
        _shot(page, f"{width}-{'dark' if dark else 'light'}-compare")
        # The chip for the models says who answers, never the mode's name.
        models_chip = page.locator(".consensus-model-inline .model-picker-display-text")
        expect(models_chip).to_have_text(re.compile(r"^\d+ models?$"))
        # The Compare start is a start screen like the hero: the composer
        # keeps the selector where it was and never collapses there.
        assert page.evaluate("App.composer.isStartScreen()") is True
        page.evaluate("App.composer.collapse({force: true})")
        expect(page.locator("#attachTrigger")).to_be_visible()
        page.evaluate("App.composer.expand()")
        page.wait_for_function("() => !document.body.classList.contains('composer-animating') && !document.body.classList.contains('composer-gliding')")

        # (+) keeps its place whichever mode is chosen.
        def lead():
            # One measurement once motion has settled (switching modes moves
            # the whole composer). Only motion in time that ends: the phone's
            # starter row fades with its scroll (composer.css), the light of an
            # idle Send breathes on (send-glow.css).
            return page.evaluate("""async () => {
              await Promise.all(document.getAnimations().filter(a => a.timeline === document.timeline
                && a.effect?.getComputedTiming().iterations !== Infinity)
                .map(a => a.finished.catch(() => null)));
              const box = document.querySelector('.chat-input-container').getBoundingClientRect();
              const plus = document.getElementById('attachTrigger').getBoundingClientRect();
              return [Math.round(plus.x - box.x), Math.round(plus.y - box.y)];
            }""")
        compare_lead = lead()
        # Agent: the shell switches, and the choice survives a reload.
        choose(page, "agent")
        expect(page.locator("body")).to_have_class(re.compile(r"single-agent-active"))
        expect(page.locator("#agentModelControls")).to_be_visible()
        assert page.evaluate("App.agentChat.isSelected()") is True
        expect(page.locator("#attachTrigger")).to_be_visible()
        assert lead() == compare_lead
        # Agent has ONE models chip: the chat model, its reviewers in its
        # tooltip and under the field. The comparison chip steps back into its menu.
        expect(page.locator(".consensus-model-inline")).to_be_hidden()
        expect(page.locator(".agent-model-picker .model-picker-display-text")).to_have_text("DeepSeek V4.1 Flash")
        expect(page.locator(".composer-models .model-picker-display:visible")).to_have_count(1)
        _shot(page, f"{width}-{'dark' if dark else 'light'}-agent")
        page.reload()
        _signed_in(page, agent_access=True)
        expect(page.locator("#runModeSelect")).to_have_value("agent")
        assert page.evaluate("App.agentChat.isSelected()") is True

        # Settings mirrors the same choice.
        page.evaluate("document.getElementById('runModeSetting').value = 'compare'; document.getElementById('runModeSetting').dispatchEvent(new Event('change'))")
        expect(page.locator("#runModeSelect")).to_have_value("compare")
        assert page.evaluate("App.agentChat.isSelected()") is False
        expect(models_chip).to_have_text(re.compile(r"^\d+ models?$"))

        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert errors == []
    finally:
        context.close()


def test_without_agent_access_agent_is_not_offered_and_falls_back(browser, phase4_server):
    context, page = _real_firebase_page(browser, phase4_server,
        init_script="if (!sessionStorage.seeded) { localStorage.setItem('runMode', 'agent'); localStorage.setItem('consensio.settingsReset','2026-10-12'); sessionStorage.seeded = 1; }")
    try:
        _signed_in(page, agent_access=False)
        expect(page.locator("#runModeSelect")).to_have_value("compare")
        expect(page.locator('#runModeSelect option[value="agent"]')).to_have_count(0)
        expect(page.locator('#runModeSetting option[value="agent"]')).to_have_count(0)
        assert page.evaluate("App.runMode.effective()") == "compare"
        # The stored choice is kept for when access arrives.
        assert page.evaluate("App.runMode.preference()") == "agent"
    finally:
        context.close()


def test_open_chat_keeps_its_family(browser, phase4_server):
    context, page = _real_firebase_page(browser, phase4_server,
        init_script="if (!sessionStorage.seeded) { localStorage.setItem('runMode', 'compare'); localStorage.setItem('consensio.settingsReset','2026-10-12'); sessionStorage.seeded = 1; }")
    try:
        _signed_in(page, agent_access=True)
        # A saved Consensus chat or Compare result: Compare continues, Agent
        # needs a new chat.
        page.evaluate("App.agentChat.modeState = () => ({family: 'consensus', canUse: true, pending: false}); App.renderComposerMode()")
        control = page.locator("#runModeControl")
        page.locator("#attachTrigger").click()
        expect(control.locator('[data-value="agent"]')).to_be_disabled()
        expect(control.locator('[data-value="agent"]')).to_contain_text("Available in a new chat")
        expect(control.locator('[data-value="compare"]')).to_be_enabled()
        page.keyboard.press("Escape")
        page.evaluate("App.runMode.set('agent')")
        assert page.evaluate("App.runMode.effective()") == "compare"
        # An Agent-family chat stays Agent whatever the preference says; with
        # nothing to switch to, the selector steps aside.
        page.evaluate("App.agentChat.modeState = () => ({family: 'agent', canUse: true, pending: false}); App.runMode.set('compare')")
        assert page.evaluate("App.runMode.effective()") == "agent"
        page.wait_for_function("() => document.getElementById('runModeControl').hidden === true")
        expect(page.locator('#runModeSelect option[value="compare"]')).to_be_disabled()
        # A new chat brings the selector back.
        page.evaluate("App.agentChat.modeState = () => ({family: null, canUse: true, pending: false}); App.renderComposerMode()")
        page.wait_for_function("() => document.getElementById('runModeControl').hidden === false")
    finally:
        context.close()


def test_stored_agent_choice_waits_for_access_instead_of_sending_compare(browser, phase4_server):
    context, page = _real_firebase_page(browser, phase4_server, initial_uid=None,
        init_script="if (!sessionStorage.seeded) { localStorage.setItem('runMode', 'agent'); localStorage.setItem('consensio.settingsReset','2026-10-12'); sessionStorage.seeded = 1; }")
    try:
        held = []
        page.route("**/user_status", lambda route: held.append(route))  # never answered: access stays pending
        page.evaluate("() => { window.__switchE2EUser('account-a'); }")
        page.wait_for_function("() => Boolean(window.auth?.currentUser?.uid)")
        page.locator("#questionInput").fill("Which approach works best?")
        assert page.evaluate("App.agentChat.modeState().pending") is True
        assert page.evaluate("window.updateQuestionInputAccess()") is False
    finally:
        context.close()


def test_failed_status_check_keeps_agent_and_only_a_refusal_releases_it(browser, phase4_server):
    """Apple-Audit B8: a status check that fails for a moment (5xx, network)
    does not swap Agent for Compare; it is said in the composer and asked
    again. Only a refusal (4xx) settles the account without Agent."""
    context, page = _real_firebase_page(browser, phase4_server, initial_uid=None,
        init_script="if (!sessionStorage.seeded) { localStorage.setItem('runMode', 'agent'); localStorage.setItem('consensio.settingsReset','2026-10-12'); sessionStorage.seeded = 1; }")
    try:
        answers = [503]
        page.route("**/user_status", lambda route: route.fulfill(status=answers[0], body="{}"))
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        page.wait_for_function("() => window.App.agentAccessCheck?.failed === true")
        assert page.evaluate("App.agentChat.modeState().pending") is True
        assert page.evaluate("App.agentChat.looksAgent()") is True
        expect(page.locator("#agentComposerMessage")).to_have_text("Your account could not be reached. Trying again…")
        # The send waits: nothing goes out as Compare unseen.
        page.locator("#questionInput").fill("A question")
        expect(page.locator("#sendButton")).to_be_disabled()
        # A refusal is an answer: Agent is not available for this session.
        answers[0] = 403
        page.locator("#agentComposerAction").click()
        page.wait_for_function("() => window.App.agentAccess?.uid === window.auth?.currentUser?.uid")
        assert page.evaluate("App.agentChat.modeState().pending") is False
        assert page.evaluate("App.runMode.effective()") == "compare"
        expect(page.locator("#runModeSelect")).to_have_value("compare")
        expect(page.locator("#agentComposerNotice")).to_be_hidden()
    finally:
        context.close()


@pytest.mark.parametrize("width", [1280, 390])
def test_a_guest_has_the_agent_menu_and_each_choice_asks_for_the_login(browser, phase4_server, width):
    """Apple-Audit H3 (Max): a guest's composer is an account's by default.
    The (+) menu shows Agent chosen with Compare beside it; whatever needs an
    account opens the login dialog with a line that says what for, never a
    dead click; a chosen Compare holds."""
    context, page = _real_firebase_page(browser, phase4_server, initial_uid=None, has_touch=width < 700)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        page.set_viewport_size({"width": width, "height": 900})
        label = page.evaluate("document.getElementById('appBootstrapConfig').dataset.agentDefaultLabel")
        chip = page.locator("#agentModelControls .model-picker-display")
        expect(chip).to_be_visible()
        expect(chip.locator(".model-picker-display-text")).to_have_text(label)
        expect(chip).to_have_attribute("title", re.compile("^" + re.escape(label) + " writes the answer"))
        expect(page.locator(".consensus-model")).to_be_hidden()
        expect(page.locator("#agentComposerNotice")).to_be_hidden()
        page.locator("#attachTrigger").click()
        expect(page.locator('#runModeControl [data-value="consensus"]')).to_have_count(0)
        for value in ("agent", "compare"):
            row = page.locator(f'#runModeControl [data-value="{value}"]')
            expect(row).to_be_visible()
            expect(row).to_be_enabled()
            expect(row).to_have_attribute("aria-pressed", str(value == "agent").lower())
        expect(page.locator("#attachUploadOption")).to_be_visible()
        _shot(page, f"guest-plus-menu-{width}")

        def asks(lead, focus):
            expect(page.locator("#loginModal")).to_be_visible()
            expect(page.locator("#authLead")).to_have_text(lead)
            page.locator("#closeLoginModal").click()
            expect(page.locator("#loginModal")).to_be_hidden()
            expect(page.locator(".model-picker-menu.is-open")).to_have_count(0)
            expect(page.locator("#attachMenu")).to_be_hidden()
            expect(page.locator(focus)).to_be_focused()

        page.locator("#attachUploadOption").click()
        asks("Log in to add files.", "#attachTrigger")
        # Reasoning is the (+) menu's at every width (since 2026-10-31).
        page.locator("#attachTrigger").click()
        page.locator("#agentReasoningMenuOption").click()
        asks("Log in to choose the reasoning.", "#attachTrigger")
        if width < 701:
            # Phones keep the comparison models in the (+) menu too.
            page.locator("#attachTrigger").click()
            page.locator("#agentComparisonMenuOption").click()
            asks("Log in to choose your models.", "#attachTrigger")
        chip.click()
        asks("Log in to choose your models.", "#agentModelControls .model-picker-display")

        # The guest's own choice holds, on this page and the next.
        choose(page, "compare")
        expect(chip).to_be_hidden()
        assert page.evaluate("App.runMode.effective()") == "compare"
        page.reload()
        page.wait_for_function("() => window.__consensioAuthState?.known === true && !!window.App.agentChat")
        expect(page.locator("#runModeSelect")).to_have_value("compare")
        expect(page.locator("#agentModelControls")).to_be_hidden()
        assert not page.evaluate("document.body.classList.contains('single-agent-active')")
        assert not errors, errors
    finally:
        context.close()
