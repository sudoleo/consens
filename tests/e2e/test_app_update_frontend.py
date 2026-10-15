"""An open app window picks up a new deploy by itself (static/js/app-update.js).

/api/build is routed to name another build than the page was rendered with.
Leaving the page (visibilitychange to hidden) then reloads it, and the saved
chat that was open is on screen again afterwards. With a draft in the
composer nothing happens.
"""
from playwright.sync_api import expect
from test_phase4_frontend import phase4_server, _real_firebase_page, _json
from test_agent_chat_frontend import CATALOG

LEAVE = """() => {
  Object.defineProperty(document, 'hidden', { configurable: true, get: () => true });
  Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'hidden' });
  document.dispatchEvent(new Event('visibilitychange'));
}"""


def _open_saved_chat(page):
    page.route('**/user_status', lambda r: _json(r, {'tier': 'pro', 'is_pro': True, 'agent_access': True}))
    page.route('**/agent/models', lambda r: _json(r, CATALOG))
    turn = {'id': 'b' * 32, 'question': 'What changed in the release?', 'status': 'completed',
            'consensus': 'Paragraph one of the saved answer.\n\nParagraph two of the saved answer.',
            'mode': 'Agent', 'execution_mode': 'agent'}
    bookmark = {'id': 'saved', 'query': turn['question'], 'mode': 'Agent', 'chat_id': 'a' * 32,
                'responses': {'consensus': turn['consensus']}}
    page.route('**/bookmarks/saved/conversation*', lambda r: _json(r, {'chat_id': 'a' * 32, 'turns': [turn], 'has_more': False}))
    page.route('**/bookmarks/saved', lambda r: _json(r, {'bookmark': bookmark}))
    page.route('**/api/build', lambda r: _json(r, {'build': 'f' * 7}))
    page.evaluate("async () => { await __switchE2EUser('account-a'); }")
    page.evaluate("() => window.openBookmark('saved')")
    expect(page.get_by_label('Agent answer', exact=True).get_by_text('Paragraph two of the saved answer.')).to_be_visible()


def test_leaving_the_page_loads_the_new_build_and_reopens_the_chat(browser, phase4_server):
    context, page = _real_firebase_page(browser, phase4_server)
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    try:
        _open_saved_chat(page)
        page.evaluate('() => { window.__beforeUpdate = true; }')
        with page.expect_navigation():
            page.evaluate(LEAVE)
        page.wait_for_function('() => window.__consensioAuthState?.known === true')
        expect(page.get_by_label('Agent answer', exact=True).get_by_text('Paragraph two of the saved answer.')).to_be_visible()
        assert page.evaluate('() => window.__beforeUpdate') is None
        assert page.evaluate("() => sessionStorage.getItem('consens.appUpdate.restore')") is None
        assert page.evaluate("() => App.runRegistry.getSelectedConversationIdentity()?.bookmarkId") == 'saved'
        assert not errors
    finally:
        context.close()


def test_a_draft_in_the_composer_keeps_the_page(browser, phase4_server):
    context, page = _real_firebase_page(browser, phase4_server)
    try:
        _open_saved_chat(page)
        page.locator('#questionInput').fill('A follow-up I am still writing')
        page.evaluate('() => { window.__beforeUpdate = true; }')
        with page.expect_response('**/api/build'):
            page.evaluate(LEAVE)
        page.wait_for_timeout(500)
        assert page.evaluate('() => window.__beforeUpdate') is True
        assert page.locator('#questionInput').input_value() == 'A follow-up I am still writing'
    finally:
        context.close()
