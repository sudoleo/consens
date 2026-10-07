"""Actual admin module/DOM integration with isolated auth and HTTP fixtures."""
from copy import deepcopy
from pathlib import Path

import pytest
from playwright.sync_api import expect

from app.services import agent_delegation_config
from app.services.prompt_catalog import prompt_catalog
from app.services.prompt_config import _snapshot, editable
from test_phase4_frontend import (
    FIREBASE_APP_STUB, FIREBASE_AUTH_STUB, _json, phase4_server,
)


@pytest.mark.parametrize("width", [1280, 390, 320])
def test_configuration_tab_shows_prompts_read_only_and_saves_settings(browser, phase4_server, width):
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
    defaults = editable(_snapshot(None))
    state = {"saved": deepcopy(defaults)}
    catalog = prompt_catalog()

    def handle_config(route):
        assert route.request.headers.get("authorization") == "Bearer token-admin"
        if route.request.method == "GET":
            return _json(route, {"config": state["saved"], "defaults": defaults,
                                 "prompts_readonly": catalog, "cache_seconds": 30,
                                 "delegation_limits": agent_delegation_config.LIMITS})
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
        zone = page.locator('#promptReferenceTimezone')
        expect(zone).to_have_value('Europe/Berlin')
        expect(page.locator('#savePromptConfigBtn')).to_be_enabled()
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')

        # System prompts are read-only: one collapsible entry per catalog item,
        # no editors, no restore buttons, and nothing a save could send.
        expect(page.locator('#promptCatalog > details')).to_have_count(len(catalog))
        expect(page.locator('#tab-configuration textarea')).to_have_count(0)
        expect(page.locator('[data-reset-prompt]')).to_have_count(0)
        agent = page.locator('#prompt-agent')
        expect(agent).to_be_hidden()
        page.locator('#promptCatalog summary', has_text='Agent: steering instructions').click()
        expect(agent).to_be_visible()
        assert agent.evaluate('(element) => element.tagName') == 'PRE'
        assert agent.text_content() == catalog[0]["text"]
        assert agent.evaluate('(element) => getComputedStyle(element).whiteSpace') == 'pre-wrap'
        expect(page.locator('#promptCatalog details[data-prompt-key="agent"]')).to_contain_text(
            'prompt_defaults.py:AGENT_SYSTEM_PROMPT')
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')

        page.locator('#delegationConfig').evaluate('(element) => { element.closest("details").open = true; }')
        expect(page.locator('#delegation-max_parallel')).to_be_visible()
        for key in ('seconds', 'max_calls', 'max_searches', 'max_cost_nano_usd'):
            expect(page.locator(f'#delegation-{key}')).to_be_hidden()
            expect(page.locator(f'label[for="delegation-{key}"]')).to_be_hidden()
        for key in ('orchestrator_prompt', 'worker_prompt'):
            expect(page.locator(f'#delegation-{key}')).to_have_count(0)
        expect(page.locator('#delegationConfig > p')).to_contain_text('daily token budget')

        # Native validation must open the collapsed delegation section rather
        # than silently rejecting submission before our submit handler runs.
        page.locator('#delegationConfig').evaluate('(element) => { element.closest("details").open = false; }')
        page.locator('#delegation-max_parallel').evaluate(
            '(element) => { element.value = "99"; element.dispatchEvent(new Event("input", {bubbles: true})); }')
        page.locator('#savePromptConfigBtn').click()
        expect(page.locator('#delegation-max_parallel')).to_be_visible()
        assert writes == []
        page.locator('#delegation-max_parallel').fill('3')

        zone.fill('UTC')
        expect(page.locator('#promptConfigDirty')).to_be_visible()
        page.locator('#savePromptConfigBtn').click()
        expect(page.locator('#promptConfigStatus')).to_contain_text('Saved.')
        assert writes[-1]["revision"] == 0
        assert set(writes[-1]["config"]) == {"reference_timezone", "delegation"}
        assert writes[-1]["config"]["delegation"] == {**defaults["delegation"], "max_parallel": 3}
        page.reload(wait_until="domcontentloaded")
        expect(zone).to_have_value('UTC')
        expect(page.locator('#delegation-max_parallel')).to_have_value('3')
        expect(page.locator('#promptConfigMeta')).to_contain_text('Revision 1')

        # A second session wins; a stale browser must keep its draft on 409.
        state["saved"]["revision"] = 2
        state["saved"]["reference_timezone"] = 'Asia/Tokyo'
        zone.fill('America/New_York')
        page.locator('#savePromptConfigBtn').click()
        expect(page.locator('#promptConfigStatus')).to_contain_text('another session')
        expect(zone).to_have_value('America/New_York')
        page.locator('#reloadPromptConfigBtn').click()
        expect(zone).to_have_value('Asia/Tokyo')
        assert len(writes) == 2
        zone.fill('Europe/Berlin')
        page.locator('#savePromptConfigBtn').click()
        expect(page.locator('#promptConfigMeta')).to_contain_text('Revision 3')
        expect(page.locator('#savePromptConfigBtn')).to_be_disabled()
        assert all("prompts" not in write["config"] for write in writes)
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
        page.evaluate('window.scrollTo(0, 0)')
        output = Path('test-results/admin-prompt-config')
        output.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(output / f'configuration-{width}.png'), full_page=True)
        assert errors == []
    finally:
        context.close()
