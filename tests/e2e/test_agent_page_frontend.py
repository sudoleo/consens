"""A page the agent shared, in the built app: it runs in the answer, in a
place that has its size before it loads, opens larger on the stage and
comes back when the chat is opened again. The app's APIs are mocked; the
page's document and headers are the ones the route sends
(app/core/html_page.py), under the app's real page policy. That the page
reaches nothing is test_agent_page_sandbox.py."""
import pytest
from playwright.sync_api import expect

from app.core import html_page
from test_agent_workspace_frontend import CHAT, TURN_TWO, _routes, _shot
from test_phase4_frontend import phase4_server, _real_firebase_page, _json  # noqa: F401
from test_agent_chat_frontend import _choose_mode

PAGE, TABLE = 'e' * 32, 'f' * 32
SOURCE = """<!doctype html><meta charset="utf-8"><title>Benchmark</title>
<style>body { font: 16px system-ui; margin: 24px } .bar { height: 18px; background: #2f6f4f; margin: 6px 0 }</style>
<h1>Benchmark</h1>
<label for="n">Models</label> <input id="n" type="range" min="1" max="6" value="2">
<output id="o">2 models</output> <button id="b" type="button">Show all</button>
<div id="bars"></div>
<script>
  const n = document.getElementById('n'), o = document.getElementById('o'), bars = document.getElementById('bars');
  const draw = () => {
    o.textContent = n.value + ' models';
    bars.replaceChildren(...Array.from({ length: Number(n.value) }, (_, i) => {
      const bar = document.createElement('div'); bar.className = 'bar'; bar.style.width = (90 - i * 12) + '%'; return bar;
    }));
  };
  n.addEventListener('input', draw);
  document.getElementById('b').addEventListener('click', () => { n.value = '6'; draw(); });
  draw();
</script>"""
STAMP = {'status': 'ready', 'created_at': '2026-11-23T10:00:00Z', 'expires_at': '2099-10-29T10:00:00Z', 'warnings': []}
FILES = [
    {'id': PAGE, 'name': 'benchmark-interaktiv.html', 'kind': 'vm_file', 'turn_id': TURN_TWO, 'size': len(SOURCE),
     'mime': 'text/html', 'page': 'html', 'origin': {'source': 'vm', 'path': '/home/agent/chats/x/benchmark-interaktiv.html'}, **STAMP},
    {'id': TABLE, 'name': 'results.csv', 'kind': 'vm_file', 'turn_id': TURN_TWO, 'size': 64, 'mime': 'text/csv',
     'origin': {'source': 'vm', 'path': '/home/agent/chats/x/results.csv'}, **STAMP},
]
ANSWER = 'Hier ist das interaktive Diagramm. Mit dem Regler wählst du, wie viele Modelle es zeigt.'


def _open(browser, server, width, *, dark=False, hold=False):
    context, page = _real_firebase_page(browser, server, has_touch=width < 700)
    errors, asked, held = [], [], []
    page.on('pageerror', lambda e: errors.append(str(e)))
    # The mocked session's own 401s are no fault of the page.
    page.on('console', lambda m: errors.append(m.text) if m.type == 'error' and 'status of 401' not in m.text else None)
    page.set_viewport_size({'width': width, 'height': 860})
    _routes(page, FILES)
    page.route(f'**/agent/chats/{CHAT}/files', lambda r: _json(r, {'files': FILES}))
    page.route(f'**/agent/chats/{CHAT}/files/{PAGE}', lambda r: r.fulfill(
        body=SOURCE, content_type='application/octet-stream',
        headers={'Content-Disposition': "attachment; filename*=UTF-8''benchmark-interaktiv.html"}))

    def address(route):
        assert route.request.method == 'POST' and route.request.headers.get('authorization', '').startswith('Bearer ')
        asked.append(route.request.url)
        _json(route, {'url': f'/agent/pages/address-{len(asked)}', 'expires_in': 300})
    page.route(f'**/agent/chats/{CHAT}/files/{PAGE}/page', address)

    def document(route):
        # A frame sends no sign-in of the account with its request.
        assert 'authorization' not in route.request.headers
        answer = dict(status=200, body=html_page.document(SOURCE, 'benchmark-interaktiv.html'),
                      headers={**html_page.HEADERS, 'Content-Type': html_page.CONTENT_TYPE})
        if hold and not held:
            held.append(lambda: route.fulfill(**answer))
        else:
            route.fulfill(**answer)
    page.route('**/agent/pages/*', document)
    page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
    page.evaluate("dark => { document.documentElement.classList.toggle('dark-mode', dark); document.body.classList.toggle('dark-mode', dark); }", dark)
    _choose_mode(page, 'agent')
    expect(page.locator('#agentModelDropdown')).to_be_enabled()
    _show(page)
    return context, page, errors, asked, held


def _show(page):
    page.evaluate("""([chat, turn, answer]) => (window.exitHeroMode?.(), App.runRegistry.showSavedView)({type:'bookmark'}, {chatId: chat, turnId: turn,
      executionMode:'agent', question:'Mach mir ein interaktives Diagramm zum Benchmark', consensus: answer,
      currentTurn:{id: turn, status:'completed', execution_mode:'agent', consensus: answer,
      agent_settings:{model_id:'deepseek/deepseek-v4.1-flash', file_ids:[]}}});""", [CHAT, TURN_TWO, ANSWER])


def _inner(page, outer='.agent-page-frame'):
    return page.frame_locator(outer).frame_locator('iframe')


@pytest.mark.parametrize('width,dark', [(1440, False), (1440, True), (390, False)])
def test_a_shared_page_runs_in_the_answer_in_a_place_that_never_moves(browser, phase4_server, width, dark):
    context, page, errors, asked, held = _open(browser, phase4_server, width, dark=dark, hold=True)
    try:
        slot = page.locator('#agentAnswerBody ~ .agent-answer-pages')
        figure, stage = slot.locator('.agent-page'), slot.locator('.agent-page-stage')
        frame = stage.locator('iframe.agent-page-frame')
        expect(figure).to_have_count(1)
        # Sandboxed by the app as well as by the page's own answer.
        expect(frame).to_have_attribute('sandbox', 'allow-scripts')
        expect(frame).to_have_attribute('aria-label', 'benchmark-interaktiv.html')
        # The other file of the turn stays a row to download, under the page.
        rows = page.locator('#agentAnswerBody ~ .agent-answer-documents .agent-file-row .agent-file-name')
        expect(rows).to_have_text(['results.csv'])
        # While the page is on its way its place waits at its full size.
        expect(stage).to_have_class('agent-page-stage is-loading')
        for _ in range(100):
            if held:
                break
            page.wait_for_timeout(50)
        assert held, 'The frame never asked for its page'
        before = page.evaluate("""() => {
          const box = el => { const r = el.getBoundingClientRect(); return [Math.round(r.top), Math.round(r.height), Math.round(r.width)]; };
          return { stage: box(document.querySelector('.agent-page-stage')),
                   below: box(document.querySelector('#agentAnswerBody ~ .agent-answer-documents')), scroll: scrollY };
        }""")
        held[0]()
        inner = _inner(page)
        expect(inner.locator('#o')).to_have_text('2 models')
        expect(stage).to_have_class('agent-page-stage')
        after = page.evaluate("""() => {
          const box = el => { const r = el.getBoundingClientRect(); return [Math.round(r.top), Math.round(r.height), Math.round(r.width)]; };
          return { stage: box(document.querySelector('.agent-page-stage')),
                   below: box(document.querySelector('#agentAnswerBody ~ .agent-answer-documents')), scroll: scrollY };
        }""")
        assert after == before, (before, after)
        # Its place: the answer's width, 16:10, never under 420 px or over 600 px high.
        top, height, wide = after['stage']
        assert height == max(420, min(600, round(wide * 10 / 16))), after
        assert height == 420 if width < 700 else 420 <= height <= 600
        # The page works: its own controls, by pointer and by keys.
        inner.locator('#n').focus()
        page.keyboard.press('ArrowRight')
        expect(inner.locator('#o')).to_have_text('3 models')
        inner.locator('#b').click()
        expect(inner.locator('#o')).to_have_text('6 models')
        expect(inner.locator('.bar')).to_have_count(6)
        # Tab leaves the page for the line under it.
        page.keyboard.press('Tab')
        assert 'agent-page-open' in page.evaluate('document.activeElement.className')
        # Its own look on a white sheet in both themes; the line under it is the app's.
        assert page.evaluate("getComputedStyle(document.querySelector('.agent-page-frame')).backgroundColor") == 'rgb(255, 255, 255)'
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        assert len(asked) == 1
        _shot(page, f'agent-page-{width}-{"dark" if dark else "light"}')
        assert not errors, errors
    finally:
        context.close()


def test_a_shared_page_opens_larger_downloads_and_comes_back_with_the_chat(browser, phase4_server):
    context, page, errors, asked, _ = _open(browser, phase4_server, 1440)
    try:
        figure = page.locator('#agentAnswerBody ~ .agent-answer-pages .agent-page')
        inner = _inner(page)
        expect(inner.locator('#o')).to_have_text('2 models')
        inner.locator('#b').click()
        small = figure.locator('.agent-page-stage').bounding_box()
        # Larger: the viewer's stage, the page in a frame of its own there.
        opener = figure.get_by_role('button', name='Open benchmark-interaktiv.html larger')
        opener.click()
        dialog = page.locator('#attachmentViewerModal')
        expect(dialog).to_be_visible()
        expect(dialog).to_have_class('modal attachment-viewer-dialog is-stage')
        expect(dialog.locator('#attachmentViewerTitle')).to_have_text('benchmark-interaktiv.html')
        large = dialog.locator('iframe.attachment-viewer-frame')
        expect(large).to_have_attribute('sandbox', 'allow-scripts')
        expect(large).to_have_attribute('aria-label', 'benchmark-interaktiv.html')
        staged = _inner(page, '#attachmentViewerModal iframe.attachment-viewer-frame')
        expect(staged.locator('#o')).to_have_text('2 models')
        box = large.bounding_box()
        assert box['width'] > small['width'] + 200 and box['height'] > small['height'], (box, small)
        staged.locator('#b').click()
        expect(staged.locator('.bar')).to_have_count(6)
        # The pointer rests on the page: no tooltip of the app comes to lie
        # over it (tooltip.js shows one after 500 ms).
        page.wait_for_timeout(700)
        expect(page.locator('.global-tooltip.visible')).to_have_count(0)
        _shot(page, 'agent-page-stage')
        with page.expect_download() as pending:
            dialog.get_by_role('button', name='Download', exact=True).click()
        assert pending.value.suggested_filename == 'benchmark-interaktiv.html'
        dialog.locator('#attachmentViewerClose').click()
        expect(dialog).to_be_hidden()
        # The page under the answer stayed as the user left it, and the focus is back on its button.
        expect(inner.locator('#o')).to_have_text('6 models')
        assert 'agent-page-open' in page.evaluate('document.activeElement.className')
        with page.expect_download() as pending:
            figure.get_by_role('button', name='Download benchmark-interaktiv.html').click()
        assert pending.value.suggested_filename == 'benchmark-interaktiv.html'
        assert len(asked) == 2
        # The chat opened again: the page is there again, under a new address.
        page.reload()
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        _choose_mode(page, 'agent')
        expect(page.locator('#agentModelDropdown')).to_be_enabled()
        _show(page)
        expect(_inner(page).locator('#o')).to_have_text('2 models')
        assert len(asked) == 3
        assert not errors, errors
    finally:
        context.close()


def test_the_running_app_answers_under_the_page_path_sandboxed(phase4_server, browser):
    """The whole app, every middleware in its order: an address that opens
    nothing answers with the page's sandbox, for a German reader too."""
    context = browser.new_context()
    try:
        for headers in ({}, {'Accept-Language': 'de-DE,de;q=0.9'}):
            for path in ('x' * 120, 'nothing'):
                response = context.request.get(f'{phase4_server}/agent/pages/{path}', headers=headers)
                assert response.status == 404 and response.body() == b''
                assert response.headers['content-security-policy'] == html_page.POLICY
                assert response.headers['x-frame-options'] == 'SAMEORIGIN'
                assert response.headers['cache-control'] == 'private, no-store'
                assert response.headers['referrer-policy'] == 'no-referrer'
        # The app's own page may frame it: its policy allows frames of itself.
        app = context.request.get(f'{phase4_server}/app')
        assert "frame-src 'self'" in app.headers['content-security-policy']
        assert app.headers['x-frame-options'] == 'DENY'
    finally:
        context.close()
