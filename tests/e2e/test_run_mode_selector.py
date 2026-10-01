"""One mode selector: Compare / Consensus / Agent (run-mode.js + agent-mode.js).

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
    page.locator("#runModeControl .model-picker-display").click()
    page.locator(f'#runModeControl [data-value="{mode}"]').click()
    expect(page.locator("#runModeSelect")).to_have_value(mode)


def _signed_in(page, *, agent_access):
    page.route("**/user_status", lambda r: _json(r, {"tier": "pro" if agent_access else "free",
        "is_pro": agent_access, "agent_access": agent_access, "limit": 50, "deep_limit": 5}))
    page.route("**/agent/models", lambda r: _json(r, CATALOG))
    page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")


@pytest.mark.parametrize("legacy,expected", [("true", "consensus"), ("false", "compare"), (None, "consensus")])
def test_legacy_agent_mode_switch_migrates_once(browser, phase4_server, legacy, expected):
    script = "localStorage.removeItem('runMode');" + (
        f"localStorage.setItem('agentMode', '{legacy}'); localStorage.setItem('autoConsensus', '{legacy}');" if legacy else "")
    context, page = _real_firebase_page(browser, phase4_server, init_script=f"if (!sessionStorage.seeded) {{ {script} sessionStorage.seeded = 1; }}")
    try:
        assert page.evaluate("App.runMode.preference()") == expected
        assert page.evaluate("localStorage.getItem('agentMode')") is None
        assert page.evaluate("localStorage.getItem('autoConsensus')") is None
        assert page.evaluate("typeof window.setAgentMode") == "undefined"
        assert page.evaluate("typeof window.isAgentModeEnabled") == "undefined"
        # Every old control is gone; the one selector remains.
        for gone in ("#composerAgentToggle", "#agentModeMenuSwitch", "#agentModeSwitch", "#autoConsensusToggle", "#chatExecutionMode"):
            expect(page.locator(gone)).to_have_count(0)
        expect(page.locator("#runModeSelect")).to_have_value(expected)
    finally:
        context.close()


@pytest.mark.parametrize("width,dark", [(1440, False), (1440, True), (390, False), (320, True)])
def test_one_selector_drives_mode_tools_and_settings(browser, phase4_server, width, dark):
    context, page = _real_firebase_page(browser, phase4_server,
        init_script="if (!sessionStorage.seeded) { localStorage.setItem('runMode', 'consensus'); sessionStorage.seeded = 1; }")
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        page.set_viewport_size({"width": width, "height": 900})
        page.evaluate("dark => { document.body.classList.toggle('dark-mode', dark); document.documentElement.classList.toggle('dark-mode', dark); }", dark)
        _signed_in(page, agent_access=True)
        control = page.locator("#runModeControl")
        expect(control).to_be_visible()
        expect(control.locator(".model-picker-display")).to_contain_text("Consensus")
        expect(page.locator("#composerSourcesToggle")).to_be_visible()
        _shot(page, f"{width}-{'dark' if dark else 'light'}-consensus")

        # The menu lists all three with one-line descriptions.
        control.locator(".model-picker-display").click()
        options = control.locator(".model-picker-option")
        expect(options).to_have_count(3)
        expect(control.locator('[data-value="agent"]')).to_contain_text("Beta")
        expect(control.locator('[data-value="compare"] .model-picker-option-description')).to_contain_text("side by side")
        menu = control.locator(".model-picker-menu").bounding_box()
        assert menu["x"] >= 0 and menu["x"] + menu["width"] <= width + 1
        _shot(page, f"{width}-{'dark' if dark else 'light'}-menu")
        page.keyboard.press("Escape")

        # Compare: nothing to check, so the tool leaves the toolbar and menu.
        choose(page, "compare")
        assert page.evaluate("localStorage.getItem('runMode')") == "compare"
        assert page.evaluate("App.runMode.pipeline()") is False
        assert page.evaluate("App.isSourceCheckEnabled()") is False
        expect(page.locator("#composerSourcesToggle")).to_be_hidden()
        expect(page.locator("#composerModeDescription")).to_contain_text("no consensus")
        _shot(page, f"{width}-{'dark' if dark else 'light'}-compare")
        # The chip for the models says who answers, never the mode's name.
        models_chip = page.locator(".consensus-model-inline .model-picker-display-text")
        expect(models_chip).to_have_text(re.compile(r"^\d+ models?$"))
        # The Compare start is a start screen like the hero: the composer
        # keeps the selector where it was and never collapses there.
        assert page.evaluate("App.composer.isStartScreen()") is True
        page.evaluate("App.composer.collapse({force: true})")
        expect(control).to_be_visible()
        page.evaluate("App.composer.expand()")
        page.wait_for_function("() => !document.body.classList.contains('composer-animating')")
        page.locator("#attachTrigger").click()
        expect(page.locator('label[for="sourceCheckMenuSwitch"]')).to_be_hidden()
        page.locator("#attachTrigger").click()

        # (+) and the mode keep their place whichever mode is chosen.
        def lead():
            # One measurement once motion has settled (switching modes moves
            # the whole composer).
            return page.evaluate("""async () => {
              await Promise.all(document.getAnimations().map(a => a.finished.catch(() => null)));
              const box = document.querySelector('.chat-input-container').getBoundingClientRect();
              const plus = document.getElementById('attachTrigger').getBoundingClientRect();
              const mode = document.getElementById('runModeControl').getBoundingClientRect();
              return [Math.round(plus.x - box.x), Math.round(mode.x - box.x), Math.round(mode.y - plus.y)];
            }""")
        compare_lead = lead()
        # Agent: the shell switches, and the choice survives a reload.
        choose(page, "agent")
        expect(page.locator("body")).to_have_class(re.compile(r"single-agent-active"))
        expect(page.locator("#agentModelControls")).to_be_visible()
        assert page.evaluate("App.agentChat.isSelected()") is True
        expect(page.locator("#attachTrigger")).to_be_visible()
        assert lead() == compare_lead
        # Agent has ONE models chip: the chat model and how many models it is
        # compared with. The comparison chip steps back into its menu.
        expect(page.locator(".consensus-model-inline")).to_be_hidden()
        expect(page.locator(".agent-model-picker .model-picker-display-count")).to_have_text(re.compile(r"^\+\d+$"))
        expect(page.locator(".composer-models .model-picker-display:visible")).to_have_count(1)
        _shot(page, f"{width}-{'dark' if dark else 'light'}-agent")
        page.reload()
        _signed_in(page, agent_access=True)
        expect(page.locator("#runModeSelect")).to_have_value("agent")
        assert page.evaluate("App.agentChat.isSelected()") is True

        # Settings mirrors the same choice.
        page.evaluate("document.getElementById('runModeSetting').value = 'consensus'; document.getElementById('runModeSetting').dispatchEvent(new Event('change'))")
        expect(page.locator("#runModeSelect")).to_have_value("consensus")
        assert page.evaluate("App.agentChat.isSelected()") is False
        expect(models_chip).to_have_text(re.compile(r"^\d+ models? · "))

        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert errors == []
    finally:
        context.close()


def test_without_agent_access_agent_is_not_offered_and_falls_back(browser, phase4_server):
    context, page = _real_firebase_page(browser, phase4_server,
        init_script="if (!sessionStorage.seeded) { localStorage.setItem('runMode', 'agent'); sessionStorage.seeded = 1; }")
    try:
        _signed_in(page, agent_access=False)
        expect(page.locator("#runModeSelect")).to_have_value("consensus")
        expect(page.locator('#runModeSelect option[value="agent"]')).to_have_count(0)
        expect(page.locator('#runModeSetting option[value="agent"]')).to_have_count(0)
        assert page.evaluate("App.runMode.effective()") == "consensus"
        assert page.evaluate("App.runMode.pipeline()") is True
        # The stored choice is kept for when access arrives.
        assert page.evaluate("App.runMode.preference()") == "agent"
    finally:
        context.close()


def test_open_chat_keeps_its_family(browser, phase4_server):
    context, page = _real_firebase_page(browser, phase4_server,
        init_script="if (!sessionStorage.seeded) { localStorage.setItem('runMode', 'consensus'); sessionStorage.seeded = 1; }")
    try:
        _signed_in(page, agent_access=True)
        # A Consensus-family chat: Compare/Consensus alternate, Agent needs a new chat.
        page.evaluate("App.agentChat.modeState = () => ({family: 'consensus', canUse: true, pending: false}); App.renderComposerMode()")
        control = page.locator("#runModeControl")
        control.locator(".model-picker-display").click()
        expect(control.locator('[data-value="agent"]')).to_be_disabled()
        expect(control.locator('[data-value="agent"]')).to_contain_text("Available in a new chat")
        expect(control.locator('[data-value="compare"]')).to_be_enabled()
        page.keyboard.press("Escape")
        page.evaluate("App.runMode.set('agent')")
        assert page.evaluate("App.runMode.effective()") == "consensus"
        # An Agent-family chat stays Agent whatever the preference says; with
        # nothing to switch to, the selector steps aside.
        page.evaluate("App.agentChat.modeState = () => ({family: 'agent', canUse: true, pending: false}); App.runMode.set('compare')")
        assert page.evaluate("App.runMode.effective()") == "agent"
        expect(control).to_be_hidden()
        expect(page.locator('#runModeSelect option[value="compare"]')).to_be_disabled()
        # A new chat brings the selector back.
        page.evaluate("App.agentChat.modeState = () => ({family: null, canUse: true, pending: false}); App.renderComposerMode()")
        expect(control).to_be_visible()
    finally:
        context.close()


def test_stored_agent_choice_waits_for_access_instead_of_sending_consensus(browser, phase4_server):
    context, page = _real_firebase_page(browser, phase4_server, initial_uid=None,
        init_script="if (!sessionStorage.seeded) { localStorage.setItem('runMode', 'agent'); sessionStorage.seeded = 1; }")
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


def test_failed_status_check_releases_the_agent_wait(browser, phase4_server):
    context, page = _real_firebase_page(browser, phase4_server, initial_uid=None,
        init_script="if (!sessionStorage.seeded) { localStorage.setItem('runMode', 'agent'); sessionStorage.seeded = 1; }")
    try:
        page.route("**/user_status", lambda route: route.fulfill(status=503, body="{}"))
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        page.wait_for_function("() => window.App.agentAccess?.uid === window.auth?.currentUser?.uid")
        assert page.evaluate("App.agentChat.modeState().pending") is False
        assert page.evaluate("App.runMode.effective()") == "consensus"
        expect(page.locator("#runModeSelect")).to_have_value("consensus")
    finally:
        context.close()
