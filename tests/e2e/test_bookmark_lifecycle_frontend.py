"""Bookmark interaction against built assets and isolated, delayed HTTP fixtures."""
import re

import pytest
from playwright.sync_api import expect
from test_phase4_frontend import phase4_server, _real_firebase_page, _json
from test_agent_chat_frontend import CATALOG
from test_model_answer_reader import reader_screenshot


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
        control = row.locator('.delete-bookmark')
        # The first click only arms the control; nothing is deleted yet.
        # A double-click arms only: its second click never confirms.
        control.dblclick()
        expect(control).to_have_text('Delete')
        expect(row).to_have_count(1)
        page.wait_for_timeout(450)
        assert not requests
        control.click()
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
            page.wait_for_timeout(450)
            row.locator('.delete-bookmark').click()
            expect(row).to_have_count(0)
            assert len(requests) == 2
            _json(requests[1], {'status': 'success'})
        assert not errors
    finally:
        context.close()


ARMED = re.compile(r'(^|\s)is-armed(\s|$)')


@pytest.mark.parametrize('width,cancel', [(1280, 'escape'), (390, 'elsewhere')])
def test_armed_delete_cancels_without_deleting(browser, phase4_server, width, cancel):
    # The phone case runs with touch: the X is always shown there.
    context, page = _real_firebase_page(browser, phase4_server, has_touch=width < 700)
    requests, errors = [], []
    page.on('pageerror', lambda error: errors.append(str(error)))
    try:
        page.set_viewport_size({'width': width, 'height': 800})
        bookmarks = [{'id': 'first', 'title': 'Keep me even with a long title that runs to the edge', 'query': 'Question', 'mode': 'Agent'},
                     {'id': 'second', 'title': 'Other chat', 'query': 'Another question', 'mode': 'Agent'}]
        page.route('**/bookmarks?*', lambda r: _json(r, {'bookmarks': bookmarks, 'next_cursor': None}))
        page.route('**/bookmark', lambda r: requests.append(r))
        page.evaluate('() => window.loadBookmarks()')
        if width < 1100:
            page.locator('#toggleSidebarButton').click()
        row = page.locator('.bookmark[data-id="first"]')
        row.hover()
        control = row.locator('.delete-bookmark')
        reader_screenshot(page, f'bookmark-delete-idle-{width}')
        control.click()
        expect(control).to_have_text('Delete')
        # The second step reads as destructive, also with a touch-stuck :hover.
        expect(control).to_have_css('color', 'rgb(177, 79, 91)')
        # The title ends before "Delete" instead of running under it.
        title = row.locator('p')
        assert title.bounding_box()['x'] + title.bounding_box()['width'] <= control.bounding_box()['x'] + 1
        reader_screenshot(page, f'bookmark-delete-armed-{width}')
        if cancel == 'escape':
            page.keyboard.press('Escape')
        else:
            # Any click outside the armed control disarms it (inside the
            # sidebar here: a click beside it closes the phone overlay).
            page.evaluate("() => document.getElementById('bookmarksContainer').click()")
        expect(control).not_to_have_class(ARMED)
        expect(control).to_have_text('')
        # Arming another row disarms the first; its click arms, never deletes.
        row.hover()
        control.click()
        other = page.locator('.bookmark[data-id="second"] .delete-bookmark')
        page.locator('.bookmark[data-id="second"]').hover()
        other.click()
        expect(control).not_to_have_class(ARMED)
        expect(other).to_have_text('Delete')
        page.wait_for_timeout(100)
        assert not requests
        expect(page.locator('.bookmark')).to_have_count(2)
        assert not errors
    finally:
        context.close()


# Where a first question stands on an unscrolled page (chat-scroll.js landing).
LANDING = """() => { const column = document.querySelector('.container'); const ask = document.getElementById('threadAsk');
  return column.getBoundingClientRect().top + scrollY + parseFloat(getComputedStyle(column).paddingTop)
    + parseFloat(getComputedStyle(ask).marginTop); }"""


@pytest.mark.parametrize('mode,width,reduced', [('Agent', 1280, False), ('Standard', 390, False), ('Agent', 390, True)])
def test_open_bookmark_stands_at_its_newest_question_without_a_ride(browser, phase4_server, mode, width, reduced):
    """Apple audit A2/A3: an opened chat shows its newest question at once,
    before its first frame, and never cut off under the phone header."""
    context, page = _real_firebase_page(browser, phase4_server)
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    try:
        page.set_viewport_size({'width': width, 'height': 800})
        page.emulate_media(reduced_motion='reduce' if reduced else 'no-preference')
        page.route('**/user_status', lambda r: _json(r, {'tier': 'pro', 'is_pro': True, 'agent_access': True}))
        page.route('**/agent/models', lambda r: _json(r, CATALOG))
        text = '\n\n'.join(f'Paragraph {i}. Saved conversation content for reading.' for i in range(65))
        execution = 'agent' if mode == 'Agent' else 'consensus'
        turns = [{'id': 'b' * 32, 'question': 'Read the saved conversation', 'consensus': text, 'status': 'completed',
                  'mode': mode, 'execution_mode': execution, 'position': 1},
                 {'id': 'c' * 32, 'question': 'And the short follow-up?', 'consensus': text, 'status': 'completed',
                  'mode': mode, 'execution_mode': execution, 'position': 2}]
        bookmark = {'id': 'long', 'query': turns[1]['question'], 'mode': mode, 'chat_id': 'a' * 32,
                    'responses': {'consensus': text}}
        page.route('**/bookmarks/long/conversation*', lambda r: _json(r, {'chat_id': 'a' * 32, 'turns': turns, 'has_more': False}))
        page.route('**/bookmarks/long', lambda r: _json(r, {'bookmark': bookmark}))
        page.evaluate("async () => { await __switchE2EUser('account-a'); }")
        page.evaluate("""() => {
          window.__positions = [];
          const original = window.scrollTo.bind(window);
          window.scrollTo = options => { __positions.push(options.top); original(options); };
          // Every painted frame's position.
          window.__frames = [];
          const tick = () => { __frames.push(scrollY); requestAnimationFrame(tick); };
          requestAnimationFrame(tick);
        }""")
        page.evaluate("() => window.openBookmark('long')")
        page.wait_for_function("() => document.getElementById('threadAskText')?.textContent.includes('short follow-up')")
        page.wait_for_timeout(900)
        landing = page.evaluate(LANDING)
        assert abs(page.evaluate("document.getElementById('threadAsk').getBoundingClientRect().top") - landing) < 3
        assert page.evaluate('scrollY') > 500
        # One move (the opening skeleton sits at the top, then the chat), no ride.
        painted = page.evaluate("[...new Set(__frames)]")
        assert len(painted) <= 2, painted
        # Reading upwards after it remains under user control.
        page.mouse.move(width // 2, 300)
        page.mouse.wheel(0, -600)
        page.wait_for_function(f"() => document.getElementById('threadAsk').getBoundingClientRect().top - ({landing}) > 300")
        assert not errors
    finally:
        context.close()


def test_choosing_a_chat_answers_at_once_and_loads_detail_and_transcript_together(browser, phase4_server):
    """Apple audit D2: the row is marked and the thread shows the chat's
    question with a skeleton at once; detail and transcript load side by
    side; a chat seen a moment ago is back at once."""
    context, page = _real_firebase_page(browser, phase4_server)
    errors, held = [], []
    page.on('pageerror', lambda error: errors.append(str(error)))
    try:
        page.set_viewport_size({'width': 1280, 'height': 800})
        page.route('**/user_status', lambda r: _json(r, {'tier': 'pro', 'is_pro': True, 'agent_access': True}))
        page.route('**/agent/models', lambda r: _json(r, CATALOG))
        chats = {}
        for key, question in (('first', 'What is the first chat about?'), ('second', 'And the second one?')):
            turn = {'id': key[0] * 32, 'question': question, 'consensus': f'Answer of the {key} chat.', 'status': 'completed',
                    'mode': 'Agent', 'execution_mode': 'agent', 'position': 1}
            chats[key] = {'turn': turn, 'bookmark': {'id': key, 'query': question, 'title': question, 'mode': 'Agent',
                                                      'chat_id': key[0] * 31 + 'f', 'responses': {'consensus': turn['consensus']}}}
        page.route('**/bookmarks?*', lambda r: _json(r, {'bookmarks': [
            {'id': key, 'title': chat['bookmark']['title'], 'query': chat['bookmark']['query'], 'mode': 'Agent'} for key, chat in chats.items()],
            'next_cursor': None}))

        def conversation(route):
            key = route.request.url.split('/bookmarks/')[1].split('/')[0]
            held.append(('conversation', key, route))

        def detail(route):
            key = route.request.url.split('/bookmarks/')[1].split('?')[0]
            held.append(('detail', key, route))
        page.route('**/bookmarks/*/conversation*', conversation)
        page.route('**/bookmarks/first', detail)
        page.route('**/bookmarks/second', detail)
        page.evaluate("async () => { await __switchE2EUser('account-a'); await window.loadBookmarks(); }")

        def release(kind, key):
            for item in list(held):
                if item[0] == kind and item[1] == key:
                    held.remove(item)
                    chat = chats[key]
                    if kind == 'detail':
                        _json(item[2], {'bookmark': chat['bookmark']})
                    else:
                        _json(item[2], {'chat_id': chat['bookmark']['chat_id'], 'turns': [chat['turn']], 'has_more': False})

        page.locator('.bookmark[data-id="first"]').click()
        # Both requests are out before either answered.
        page.wait_for_function("() => true")
        page.wait_for_timeout(200)
        assert sorted(kind for kind, key, _ in held if key == 'first') == ['conversation', 'detail']
        expect(page.locator('.bookmark[data-id="first"]')).to_have_class(re.compile(r'(^|\s)is-active(\s|$)'))
        expect(page.locator('.thread-opening .thread-opening-question')).to_have_text('What is the first chat about?')
        expect(page.locator('.thread-opening .answer-skeleton')).to_be_visible()
        release('conversation', 'first'); release('detail', 'first')
        expect(page.locator('#agentAnswerBody')).to_contain_text('Answer of the first chat.')
        expect(page.locator('.thread-opening')).to_have_count(0)

        page.locator('.bookmark[data-id="second"]').click()
        page.wait_for_timeout(150)
        expect(page.locator('.bookmark[data-id="second"]')).to_have_class(re.compile(r'(^|\s)is-active(\s|$)'))
        expect(page.locator('.bookmark[data-id="first"]')).not_to_have_class(re.compile(r'(^|\s)is-active(\s|$)'))
        release('detail', 'second'); release('conversation', 'second')
        expect(page.locator('#agentAnswerBody')).to_contain_text('Answer of the second chat.')

        # Back to the first: on screen at once, before its check returns.
        page.locator('.bookmark[data-id="first"]').click()
        expect(page.locator('#agentAnswerBody')).to_contain_text('Answer of the first chat.')
        expect(page.locator('.thread-opening')).to_have_count(0)
        page.wait_for_timeout(150)
        assert any(key == 'first' for _, key, _ in held)
        release('detail', 'first'); release('conversation', 'first')
        page.wait_for_timeout(200)
        expect(page.locator('#agentAnswerBody')).to_contain_text('Answer of the first chat.')
        assert not errors
    finally:
        context.close()
