"""Bookmark interaction against built assets and isolated, delayed HTTP fixtures."""
import pytest
from playwright.sync_api import expect
from test_phase4_frontend import phase4_server, _real_firebase_page, _json
from test_agent_chat_frontend import CATALOG


@pytest.mark.parametrize('width,status,reduced', [(1280, 200, False), (390, 403, False), (390, 500, True)])
def test_delete_disappears_before_server_reply_and_restores_on_failure(browser, phase4_server, width, status, reduced):
    context, page = _real_firebase_page(browser, phase4_server)
    requests, errors = [], []
    page.on('pageerror', lambda error: errors.append(str(error)))
    try:
        page.set_viewport_size({'width': width, 'height': 800})
        page.emulate_media(reduced_motion='reduce' if reduced else 'no-preference')
        bookmarks = [{'id': 'first', 'title': 'Delete this bookmark', 'query': 'Question', 'mode': 'Agent'},
                     {'id': 'second', 'title': 'Keep this bookmark', 'query': 'Another question', 'mode': 'Agent'}]
        page.route('**/bookmarks?*', lambda r: _json(r, {'bookmarks': bookmarks, 'next_cursor': None}))
        page.route('**/bookmark', lambda r: requests.append(r))
        page.evaluate('() => window.loadBookmarks()')
        if width < 1100:
            page.locator('#toggleSidebarButton').click()
        row = page.locator('.bookmark[data-id="first"]')
        row.hover()
        row.locator('.delete-bookmark').click()
        expect(row).to_have_count(0)
        assert len(requests) == 1
        # A stale metadata refresh cannot resurrect the optimistically hidden row.
        page.evaluate('() => window.loadBookmarks()')
        expect(row).to_have_count(0)
        page.evaluate("() => { void window.deleteBookmark('first'); }")
        assert len(requests) == 1
        _json(requests[0], {'status': 'success'} if status == 200 else {'detail': 'Deletion failed'}, status)
        page.wait_for_timeout(250)
        expect(row).to_have_count(0 if status == 200 else 1)
        expect(page.locator('.bookmark[data-id="second"]')).to_have_count(1)
        if status != 200:
            assert page.evaluate("bookmarksData.some(item => item.id === 'first')")
            # The restored item can retry, including an ambiguous server failure.
            row.hover()
            row.locator('.delete-bookmark').click()
            expect(row).to_have_count(0)
            assert len(requests) == 2
            _json(requests[1], {'status': 'success'})
        assert not errors
    finally:
        context.close()


@pytest.mark.parametrize('mode,width,reduced', [('Agent', 1280, False), ('Standard', 390, False), ('Agent', 390, True)])
def test_open_bookmark_scrolls_smoothly_to_end_after_layout(browser, phase4_server, mode, width, reduced):
    context, page = _real_firebase_page(browser, phase4_server)
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    try:
        page.set_viewport_size({'width': width, 'height': 800})
        page.emulate_media(reduced_motion='reduce' if reduced else 'no-preference')
        page.route('**/user_status', lambda r: _json(r, {'tier': 'pro', 'is_pro': True, 'agent_access': True}))
        page.route('**/agent/models', lambda r: _json(r, CATALOG))
        text = '\n\n'.join(f'Paragraph {i}. Saved conversation content for reading.' for i in range(65))
        turn = {'id': 'b' * 32, 'question': 'Read the saved conversation', 'consensus': text, 'status': 'completed',
                'mode': mode, 'execution_mode': 'agent' if mode == 'Agent' else 'consensus'}
        bookmark = {'id': 'long', 'query': turn['question'], 'mode': mode, 'chat_id': 'a' * 32,
                    'responses': {'consensus': text}}
        page.route('**/bookmarks/long/conversation*', lambda r: _json(r, {'chat_id': 'a' * 32, 'turns': [turn], 'has_more': False}))
        page.route('**/bookmarks/long', lambda r: _json(r, {'bookmark': bookmark}))
        page.evaluate("async () => { await __switchE2EUser('account-a'); }")
        page.evaluate("""() => {
          window.__positions = [];
          const original = window.scrollTo.bind(window);
          window.scrollTo = options => { __positions.push(options.top); original(options); };
        }""")
        page.evaluate("() => window.openBookmark('long')")
        page.wait_for_function('() => scrollY > 500 && document.documentElement.scrollHeight - innerHeight - scrollY < 3')
        if not reduced:
            assert page.evaluate('__positions.length > 2')
        # Reading upwards after the jump remains under user control.
        page.mouse.move(width // 2, 180)
        page.mouse.wheel(0, -1000)
        page.wait_for_function('() => document.documentElement.scrollHeight - innerHeight - scrollY > 300')
        assert not errors
    finally:
        context.close()
