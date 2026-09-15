"""Actual admin module/DOM integration with isolated auth and HTTP fixtures."""
from copy import deepcopy
from pathlib import Path

import pytest
from playwright.sync_api import expect

from app.services.prompt_config import defaults
from test_phase4_frontend import (
    FIREBASE_APP_STUB, FIREBASE_AUTH_STUB, _json, phase4_server,
)


@pytest.mark.parametrize("width", [1280, 390, 320])
def test_configuration_tab_saves_reloads_and_preserves_conflicting_draft(browser, phase4_server, width):
    context = browser.new_context(viewport={"width": width, "height": 900})
    context.add_init_script('window.__E2E_INITIAL_UID = "admin";')
    context.route("https://www.gstatic.com/firebasejs/11.0.1/firebase-app.js",
                  lambda route: route.fulfill(content_type="application/javascript", body=FIREBASE_APP_STUB))
    context.route("https://www.gstatic.com/firebasejs/11.0.1/firebase-auth.js",
                  lambda route: route.fulfill(content_type="application/javascript", body=FIREBASE_AUTH_STUB))
    context.route("https://cloud.umami.is/**",
                  lambda route: route.fulfill(content_type="application/javascript", body="/* test */"))
    page = context.new_page()
    errors, writes = [], []
    page.on("pageerror", lambda error: errors.append(str(error)))
    state = {"saved": {**defaults(), "revision": 0, "updated_at": None, "updated_by": None}}

    def handle_config(route):
        assert route.request.headers.get("authorization") == "Bearer token-admin"
        if route.request.method == "GET":
            return _json(route, {"config": state["saved"], "defaults": defaults(),
                                 "cache_seconds": 30, "max_prompt_chars": 10000})
        payload = route.request.post_data_json
        writes.append(deepcopy(payload))
        if payload["revision"] != state["saved"]["revision"]:
            return _json(route, {"detail": "Configuration changed in another session. Reload before saving; your draft has been kept."}, status=409)
        state["saved"] = {**payload["config"], "revision": payload["revision"] + 1,
                          "updated_at": "2026-09-15T20:00:00Z", "updated_by": "admin"}
        return _json(route, {"config": state["saved"]})

    page.route("**/api/admin/**", lambda route: _json(route, {}))
    page.route("**/api/admin/prompt-config", handle_config)
    try:
        page.goto(phase4_server + "/admin#configuration", wait_until="domcontentloaded")
        expect(page.locator('#tab-configuration')).to_be_visible()
        expect(page.locator('#adminSavebar')).to_be_hidden()
        agent = page.locator('#prompt-agent')
        expect(agent).to_have_value(defaults()["prompts"]["agent"])
        expect(page.locator('#savePromptConfigBtn')).to_be_enabled()
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')

        # Native validation must open a collapsed, required editor rather than
        # silently rejecting submission before our submit handler can run.
        page.locator('#prompt-answers').evaluate('(element) => { element.value = ""; element.dispatchEvent(new Event("input", {bubbles: true})); }')
        page.locator('#savePromptConfigBtn').click()
        expect(page.locator('#prompt-answers')).to_be_visible()
        assert writes == []
        page.locator('[data-reset-prompt="answers"]').click()
        page.locator('#prompt-answers').evaluate('(element) => { element.closest("details").open = false; }')

        agent.fill('Give clear, concise answers. Literal {braces} and <script> are text.')
        page.locator('#promptReferenceTimezone').fill('UTC')
        page.locator('#savePromptConfigBtn').click()
        expect(page.locator('#promptConfigStatus')).to_contain_text('Saved.')
        assert writes[-1]["revision"] == 0
        page.reload(wait_until="domcontentloaded")
        expect(agent).to_have_value(state["saved"]["prompts"]["agent"])
        expect(page.locator('#promptReferenceTimezone')).to_have_value('UTC')
        expect(page.locator('#promptConfigMeta')).to_contain_text('Revision 1')

        # A second session wins; a stale browser must keep its draft on 409.
        state["saved"]["revision"] = 2
        state["saved"]["prompts"]["agent"] = 'Saved by another admin.'
        agent.fill('My unsaved draft')
        page.locator('#savePromptConfigBtn').click()
        expect(page.locator('#promptConfigStatus')).to_contain_text('another session')
        expect(agent).to_have_value('My unsaved draft')
        page.locator('#reloadPromptConfigBtn').click()
        expect(agent).to_have_value('Saved by another admin.')
        page.locator('[data-reset-prompt="agent"]').click()
        expect(agent).to_have_value(defaults()["prompts"]["agent"])
        assert state["saved"]["prompts"]["agent"] == 'Saved by another admin.'
        assert len(writes) == 2
        page.locator('#savePromptConfigBtn').click()
        expect(page.locator('#promptConfigMeta')).to_contain_text('Revision 3')
        expect(page.locator('#savePromptConfigBtn')).to_be_disabled()
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
        page.evaluate('window.scrollTo(0, 0)')
        output = Path('test-results/admin-prompt-config')
        output.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(output / f'configuration-{width}.png'), full_page=True)
        assert errors == []
    finally:
        context.close()
