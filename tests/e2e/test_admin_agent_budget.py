"""Admin budget save/reset through the real module with isolated HTTP fixtures."""
import os
from pathlib import Path

import pytest
from playwright.sync_api import expect
from test_phase4_frontend import FIREBASE_APP_STUB, FIREBASE_AUTH_STUB, _json, phase4_server


@pytest.mark.parametrize('width', [1280, 390, 320])
def test_admin_agent_budget_save_and_reset(browser, phase4_server, width):
    context = browser.new_context(viewport={'width': width, 'height': 900})
    context.add_init_script('window.__E2E_INITIAL_UID = "admin";')
    context.route('https://www.gstatic.com/firebasejs/11.0.1/firebase-app.js',
                  lambda route: route.fulfill(content_type='application/javascript', body=FIREBASE_APP_STUB))
    context.route('https://www.gstatic.com/firebasejs/11.0.1/firebase-auth.js',
                  lambda route: route.fulfill(content_type='application/javascript', body=FIREBASE_AUTH_STUB))
    context.route('https://cloud.umami.is/**', lambda r: r.fulfill(content_type='application/javascript', body=''))
    page = context.new_page()
    errors, writes = [], []
    page.on('pageerror', lambda error: errors.append(str(error)))
    state = {'daily_token_limit': 250000, 'revision': 0, 'reset_epoch': ''}
    def handle(route):
        assert route.request.headers['authorization'] == 'Bearer token-admin'
        if route.request.method != 'GET':
            body = route.request.post_data_json
            writes.append((route.request.method, body))
            assert body['revision'] == state['revision']
            state['revision'] += 1
            if route.request.method == 'PUT':
                state['daily_token_limit'] = body['daily_token_limit']
            else:
                state.update(reset_epoch='a' * 32, reset_at='2026-09-19T12:00:00Z')
        _json(route, {'config': state, 'cache_seconds': 30})
    page.route('**/api/admin/**', lambda r: _json(r, {}))
    page.route('**/api/admin/agent-budget', handle)
    page.route('**/api/admin/agent-budget/reset', handle)
    try:
        page.goto(phase4_server + '/admin#limits', wait_until='domcontentloaded')
        field = page.locator('#agentDailyTokenLimit')
        expect(field).to_have_value('250000')
        field.fill('500000')
        expect(page.locator('#adminSavebar')).not_to_have_class('is-dirty')
        page.locator('#saveAgentBudget').click()
        expect(page.locator('#agentBudgetStatus')).to_contain_text('saved')
        page.once('dialog', lambda dialog: dialog.dismiss())
        page.locator('#resetAgentBudgets').click()
        assert len(writes) == 1
        page.once('dialog', lambda dialog: dialog.accept())
        page.locator('#resetAgentBudgets').click()
        expect(page.locator('#agentBudgetStatus')).to_contain_text('All Agent budgets reset')
        expect(field).to_have_value('500000')
        assert writes == [('PUT', {'revision': 0, 'daily_token_limit': 500000}), ('POST', {'revision': 1})]
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        if os.environ.get('AGENT_SCREENSHOTS'):
            target = Path(os.environ['AGENT_SCREENSHOTS']); target.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(target / f'admin-budget-{width}.png'))
        assert not errors
    finally:
        context.close()
