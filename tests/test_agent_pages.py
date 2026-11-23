"""A page the agent shared runs in the chat (app/core/html_page.py,
routers/agent_files.py): only one route answers a chat's file as a document,
every answer of it is sandboxed, and its address opens one file of one
account for a few minutes."""
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core import html_page
from app.core.i18n_middleware import I18nMiddleware
from app.core.security import CustomSecurityMiddleware
from app.services import agent_pages
from test_agent_files import setup  # noqa: F401  (fixture)

PAGE = (b'<!doctype html><title>Benchmark</title><style>body{font:16px system-ui}</style>'
        b'<input id="n" type="range" max="9"><output id="o"></output>'
        b'<script>n.oninput = () => { o.textContent = "<" + n.value + ">"; };</script>')
READY = {'status': 'ready', 'parts': [], 'warnings': []}


@pytest.fixture
def client(setup, monkeypatch):  # noqa: F811
    """The file routes behind the middlewares that touch a page's answer:
    the security headers and the German pages."""
    from app.api.routers import agent_files as router
    from app.core.rate_limit import limiter
    files, chat = setup
    monkeypatch.setattr(router, 'db_firestore', files.db)
    monkeypatch.setattr(router, '_chat_uid', lambda request: request.headers.get('x-test-uid', 'owner'))
    monkeypatch.setattr(router, 'require_agent_access', lambda uid: None)
    monkeypatch.setattr(limiter, 'enabled', False)
    app = FastAPI()
    # As main.py includes it: HEAD wherever GET answers (allow_head_on_get_routes).
    for route in router.router.routes:
        if 'GET' in route.methods:
            route.methods.add('HEAD')
    app.include_router(router.router)
    app.add_middleware(CustomSecurityMiddleware)
    app.add_middleware(I18nMiddleware)
    return TestClient(app), files, chat


def share(files, chat, raw=PAGE, name='benchmark.html', page=True, uid='owner'):
    """A file as vm_share_file stores it (agent_vm_tools.share)."""
    extra = {'kind': 'vm_file', 'origin': {'source': 'vm', 'path': '/x/' + name}, **({'page': 'html'} if page else {})}
    return files.save(uid, chat, raw=raw, name=name, mime='text/html', extraction=READY, extra=extra)['id']


def sandboxed(response):
    """Every header of html_page.HEADERS, once each, and nothing that lifts them."""
    for name, value in html_page.HEADERS.items():
        assert [v.decode() for k, v in response.headers.raw if k.decode().lower() == name.lower()] == [value], name
    policy = response.headers['content-security-policy']
    assert policy.startswith('sandbox allow-scripts;')
    assert 'allow-same-origin' not in policy and 'allow-top-navigation' not in policy
    assert 'allow-popups' not in policy and 'allow-forms' not in policy and 'allow-downloads' not in policy
    return True


def address(client, chat, file_id, uid='owner'):
    response = client.post(f'/agent/chats/{chat}/files/{file_id}/page', headers={'x-test-uid': uid})
    assert response.status_code == 200, response.text
    assert response.headers['cache-control'] == 'private, no-store'
    return response.json()['url']


# ---- what the policy says ---------------------------------------------------

def test_the_policy_confines_a_page_to_itself():
    directives = dict(part.split(' ', 1) for part in html_page.POLICY.split('; '))
    assert directives['sandbox'] == 'allow-scripts'
    assert directives['default-src'] == "'none'" and directives['connect-src'] == "'none'"
    assert directives['frame-src'] == "'none'" and directives['form-action'] == "'none'"
    assert directives['base-uri'] == "'none'" and directives['frame-ancestors'] == "'self'"
    # Script and style only from the file itself, pictures only as data.
    for name in ('script-src', 'style-src', 'img-src', 'media-src', 'font-src'):
        assert not any(source.startswith(('http', '*', "'self'")) for source in directives[name].split()), name
    assert html_page.HEADERS['X-Content-Type-Options'] == 'nosniff'
    assert html_page.HEADERS['Referrer-Policy'] == 'no-referrer'
    assert html_page.HEADERS['Cache-Control'] == 'private, no-store'
    assert html_page.HEADERS['X-Frame-Options'] != 'DENY'


# ---- which file is a page ---------------------------------------------------

def test_a_file_that_needs_nothing_from_outside_is_a_page():
    assert html_page.refusal(PAGE) is None
    # Data in the file, a link to click, and markup inside a script, a
    # comment or a string are no loads.
    own = (b'<style>.a{background:url(data:image/png;base64,AAAA)} .b{fill:url(#g)}</style>'
           b'<img src="data:image/png;base64,AAAA"><a href="https://example.com/x">read</a>'
           b'<link rel="icon" href="https://example.com/favicon.ico">'
           b'<!-- <script src="https://old.example/x.js"></script> -->'
           b"<script>if (1 < 2) document.title = '<script src=lib.js>';</script><svg><use href=\"#g\"/></svg>")
    assert html_page.refusal(own) is None
    assert html_page.named('Chart.HTML') and html_page.named('a.htm') and not html_page.named('a.html.txt')


@pytest.mark.parametrize('markup,loaded', [
    (b'<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>', 'https://cdn.jsdelivr.net/npm/chart.js'),
    (b"<SCRIPT SRC='app.js'></SCRIPT>", 'app.js'),
    (b'<link href="//fonts.googleapis.com/css?family=Inter" rel="preload stylesheet">', '//fonts.googleapis.com/css'),
    (b'<img alt="a > b" src=chart.png>', 'chart.png'),
    (b'<img srcset="small.png 1x, big.png 2x">', 'small.png'),
    (b'<iframe src="https://example.com/embed"></iframe>', 'https://example.com/embed'),
    (b'<video poster="data:image/png;base64,AA" src="clip.mp4"></video>', 'clip.mp4'),
    (b"<style>@import 'https://fonts.googleapis.com/css2?family=Inter';</style>", 'https://fonts.googleapis.com/css2'),
    (b'<style>.a{background:url( "img/bg.png" )}</style>', 'img/bg.png'),
    (b'<p style="background:url(https://example.com/a.png)">', 'https://example.com/a.png'),
    (b'<script type="module">import * as d3 from "https://cdn.jsdelivr.net/npm/d3@7/+esm";</script>', 'd3@7'),
    (b'<script>const lib = await import("//esm.sh/three");</script>', '//esm.sh/three'),
    (b'<img src="&#104;ttps://example.com/a.png">', 'https://example.com/a.png'),
])
def test_a_file_that_loads_from_outside_is_refused_with_what_it_loads(markup, loaded):
    reason = html_page.refusal(b'<!doctype html><p>Chart</p>' + markup)
    assert reason.startswith('it loads ') and loaded in reason and 'inside the file itself' in reason


def test_a_refusal_names_the_first_addresses_and_counts_the_rest():
    markup = ''.join(f'<img src="https://example.com/{n}.png">' for n in range(5)).encode()
    reason = html_page.refusal(markup)
    assert 'https://example.com/0.png, https://example.com/1.png, https://example.com/2.png and 2 more' in reason
    assert '3.png' not in reason
    long = html_page.refusal(b'<img src="https://example.com/' + b'a' * 500 + b'">')
    assert 'a' * 80 in long and 'a' * 101 not in long


def test_a_file_too_large_or_not_utf8_is_refused():
    assert '2 MB' in html_page.refusal(PAGE + b' ' * html_page.MAX_BYTES)
    assert html_page.refusal('<p>Grüße</p>'.encode('latin-1')) == 'it is not UTF-8 text.'
    # A byte order mark is none of the page's text.
    assert html_page.text(b'\xef\xbb\xbf<p>ok</p>') == '<p>ok</p>'


OPENINGS = {
    'css urls': lambda: b"<p style='" + b'url(' * 500_000 + b"'>",
    'spaces after url': lambda: b'<style>url(' + b' ' * 1_900_000 + b'</style>',
    'spaces after import': lambda: b'<script>' + b'import ' + b' ' * 1_900_000 + b'</script>',
    'tags without end': lambda: b'<a x' * 500_000 + b'"',
    'comments without end': lambda: b'<!--' * 500_000,
    'quotes without end': lambda: b'<a ' + b"=' " * 600_000,
}


@pytest.mark.parametrize('kind', sorted(OPENINGS))
def test_reading_a_file_costs_one_pass_whatever_its_markup(kind):
    """A file is the agent's own, up to 2 MB: one made of nothing but
    openings must not hold the share for the square of its length (an
    unbounded pattern took over 8 s or never ended on the first three,
    a bounded one under 0.1 s)."""
    markup = OPENINGS[kind]()[:html_page.MAX_BYTES]
    started = time.perf_counter()
    html_page.refusal(markup)
    assert time.perf_counter() - started < 4


def test_the_document_holds_the_file_as_text_of_one_attribute():
    """The file runs as the srcdoc of a frame: nothing of it may end the
    attribute and become markup of the document around it."""
    hostile = '"></iframe><script>parent.x = 1</script><iframe srcdoc="\'&quot;<b>'
    body = html_page.document(hostile, 'a"><script>alert(1)</script>.html').decode('utf-8')
    assert body.count('<script') == 0 and body.count('<iframe') == 1 and body.count('</iframe>') == 1
    assert 'sandbox="allow-scripts"' in body and 'allow-same-origin' not in body
    # A page's parser gives the frame the file's own text back.
    from html.parser import HTMLParser

    class Frame(HTMLParser):
        srcdoc = title = None

        def handle_starttag(self, tag, attrs):
            if tag == 'iframe':
                self.srcdoc, self.title = dict(attrs)['srcdoc'], dict(attrs)['title']

    frame = Frame()
    frame.feed(body)
    assert frame.title == 'a"><script>alert(1)</script>.html'
    # After it, the few lines that keep a click on a link from emptying the
    # frame, and the ones that tell the chat how tall the page is.
    assert frame.srcdoc == hostile + '\n' + html_page._STAY + html_page._FIT
    assert "preventDefault" in html_page._STAY and "consensPage:{height:h}" in html_page._FIT


def test_the_document_of_a_written_page_is_one_script_of_ours_that_frames_what_its_parent_sends():
    """An HTML block of an answer runs in a fixed document: it holds nothing
    but our script, which takes the code from the page that frames it and
    from no one else, and makes it the srcdoc of a sandboxed frame."""
    import json
    import re
    body = html_page.written_document().decode('utf-8')
    assert body == html_page.written_document().decode('utf-8')
    assert body.count('<script>') == 1 and body.count('</script>') == 1 and '<iframe' not in body
    script = re.search(r'<script>(.*)</script>', body, re.S).group(1)
    # Only the framing page is heard, never an opener and never the page
    # itself once it runs, and only once.
    assert "if(shown||parent===window||e.source!==parent)return;" in script
    assert "frame.setAttribute('sandbox','allow-scripts')" in script and 'allow-same-origin' not in script
    assert "frame.srcdoc=source+'\\n'+" in script
    # The lines that keep a link from emptying the frame go after the code,
    # as a string of the script that does not end it.
    literal = re.search(r"frame\.srcdoc=source\+'\\n'\+(\".*\");document\.body\.appendChild", script, re.S).group(1)
    assert '<' not in literal and json.loads(literal) == html_page._STAY
    # Its address is no address of a shared page.
    with pytest.raises(agent_pages.InvalidToken):
        agent_pages.read(html_page.WRITTEN_PATH.removeprefix(html_page.PATH_PREFIX))


def test_the_browser_frames_a_written_page_at_the_address_the_route_answers():
    from pathlib import Path
    script = (Path(__file__).resolve().parents[1] / 'static' / 'js' / 'attachments.js').read_text(encoding='utf-8')
    assert f'const WRITTEN_PAGE = "{html_page.WRITTEN_PATH}";' in script
    assert script.count('consensPage: { source: att.htmlSource }') == 1


def test_the_prompt_names_the_place_the_app_gives_a_page():
    """The agent builds for a frame it cannot see: the size its prompt
    names is the stylesheet's, the answer's column and the page's field."""
    import re
    from pathlib import Path

    from app.services.prompt_defaults import AGENT_VM_PROMPT
    css = Path(__file__).resolve().parents[1] / 'static' / 'css'
    sheet = (css / 'agent-workspace.css').read_text(encoding='utf-8')
    field = re.search(r'\.agent-page-stage \{([^}]*)\}', sheet).group(1)
    fitted = re.search(r'\.agent-page-stage\.is-fitted \{([^}]*)\}', sheet).group(1)
    assert 'aspect-ratio: 16 / 10' in field and 'min-height: 420px' in field and 'max-height: 600px' in field
    assert 'height: var(--agent-page-height)' in fitted and 'min-height: 120px' in fitted and 'max-height: 3000px' in fitted
    assert '--app-container-width: 704px' in (css / 'layout.css').read_text(encoding='utf-8')
    assert ("up to about 700 px and a phone's width on a phone, and as tall as its content, from 120 to 3000 px; "
            "a longer page scrolls inside that place, a layout bound to the window's height gets 420 to 600 px"
            ) in AGENT_VM_PROMPT


def test_a_shared_answer_and_a_mail_carry_no_page():
    """A page runs for the account in its chat and nowhere else: what is
    published or mailed is built without the chat's files and names neither
    the page's route nor its document."""
    import inspect

    from app.services import mailer, public_markdown, share_snapshots
    for module in (share_snapshots, public_markdown, mailer):
        source = inspect.getsource(module)
        for name in ('agent_pages', 'html_page', 'AgentFiles', 'agent/pages', '<iframe'):
            assert name not in source, (module.__name__, name)


# ---- the address ------------------------------------------------------------

def test_an_address_opens_its_file_for_a_few_minutes_and_nothing_else(monkeypatch):
    now = 1_800_000_000
    token = agent_pages.issue('owner', 'c' * 32, 'f' * 32, now=now)
    assert agent_pages.read(token, now=now + agent_pages.TOKEN_SECONDS - 1) == ('owner', 'c' * 32, 'f' * 32)
    # The page that runs under it reads nothing from it.
    assert 'owner' not in token and 'c' * 32 not in token and 'f' * 32 not in token
    with pytest.raises(agent_pages.InvalidToken):
        agent_pages.read(token, now=now + agent_pages.TOKEN_SECONDS + 1)
    for broken in (token[:-2] + ('AA' if not token.endswith('AA') else 'BB'), token[5:], 'x' * 120, '', token + '/x'):
        with pytest.raises(agent_pages.InvalidToken):
            agent_pages.read(broken, now=now)
    # Another server secret, or another signed value of the same secret, opens nothing.
    monkeypatch.setenv('CHAT_CURSOR_SECRET', 'a-secret-of-this-server-0001')
    signed = agent_pages.issue('owner', 'c' * 32, 'f' * 32, now=now)
    assert agent_pages.read(signed, now=now)[0] == 'owner'
    with pytest.raises(agent_pages.InvalidToken):
        agent_pages.read(token, now=now)
    monkeypatch.setenv('CHAT_CURSOR_SECRET', 'a-secret-of-this-server-0002')
    with pytest.raises(agent_pages.InvalidToken):
        agent_pages.read(signed, now=now)


# ---- the route --------------------------------------------------------------

def test_a_shared_page_is_served_sandboxed_as_the_frame_of_a_document(client):
    client, files, chat = client
    file_id = share(files, chat)
    url = address(client, chat, file_id)
    assert url.startswith('/agent/pages/') and file_id not in url and chat not in url
    response = client.get(url)
    assert response.status_code == 200 and sandboxed(response)
    assert response.headers['content-type'] == 'text/html; charset=utf-8'
    assert 'content-disposition' not in response.headers and 'etag' not in response.headers
    body = response.text
    assert body.count('<iframe sandbox="allow-scripts"') == 1 and 'srcdoc="&lt;!doctype html&gt;' in body
    assert 'n.oninput = () =&gt;' in body and '<script' not in body
    # No sign-in goes with the frame's request: the address is the permission.
    assert client.get(url, headers={'x-test-uid': 'someone-else'}).status_code == 200


def test_a_german_reader_gets_the_page_untouched(client):
    """The German pages rewrite every HTML answer and add the dictionary's
    script; a page of the agent's is the user's file."""
    client, files, chat = client
    url = address(client, chat, share(files, chat))
    english = client.get(url)
    german = client.get(url, headers={'Accept-Language': 'de-DE,de;q=0.9'})
    assert german.status_code == 200 and german.content == english.content and sandboxed(german)
    assert '/i18n/' not in german.text and 'content-language' not in german.headers


@pytest.mark.parametrize('method', ['get', 'head', 'post', 'put', 'delete', 'options'])
def test_every_answer_under_the_page_path_is_sandboxed(client, method):
    """A refusal, a method the route does not answer, a conditional or a
    partial request: whatever leaves under /agent/pages/ carries the sandbox."""
    client, files, chat = client
    good = address(client, chat, share(files, chat))
    for url in (good, '/agent/pages/' + 'x' * 120, '/agent/pages/nothing', '/agent/pages/a/b/c', html_page.WRITTEN_PATH):
        response = getattr(client, method)(url)
        assert sandboxed(response), (method, url, response.status_code)
    for headers in ({'Range': 'bytes=0-10'}, {'If-None-Match': '*'}, {'If-Modified-Since': 'Mon, 23 Nov 2026 10:00:00 GMT'}):
        response = client.get(good, headers=headers)
        # Always the whole answer anew: nothing of it is kept or cut.
        assert response.status_code == 200 and sandboxed(response) and 'content-range' not in response.headers
    assert client.head(good).status_code == 200 and client.head(good).content == b''


def test_a_written_page_gets_the_fixed_document_sandboxed_whoever_asks(client):
    """The document an HTML block of an answer runs in: the same bytes for
    every request, under the headers of a shared page, with nothing of an
    account in it and no German rewrite."""
    client, files, chat = client
    response = client.get(html_page.WRITTEN_PATH)
    assert response.status_code == 200 and sandboxed(response)
    assert response.headers['content-type'] == 'text/html; charset=utf-8'
    assert response.content == html_page.written_document()
    for headers in ({'x-test-uid': 'someone-else'}, {'Accept-Language': 'de-DE,de;q=0.9'}, {'Cookie': 'consens_lang=de'}):
        other = client.get(html_page.WRITTEN_PATH, headers=headers)
        assert other.status_code == 200 and other.content == response.content and sandboxed(other)
        assert '/i18n/' not in other.text and 'content-language' not in other.headers
    # Nothing a request carries reaches the document.
    echoed = client.get(html_page.WRITTEN_PATH + '?source=%3Cscript%3Ealert(1)%3C/script%3E')
    assert echoed.content == response.content
    assert client.head(html_page.WRITTEN_PATH).status_code == 200
    assert client.post(html_page.WRITTEN_PATH, content=b'<p>x</p>').status_code == 405


def test_a_storage_failure_answers_sandboxed_too(client, monkeypatch):
    from app.api.routers import agent_files as router
    client, files, chat = client
    url = address(client, chat, share(files, chat))

    def broken(*args, **kwargs):
        raise RuntimeError('bucket unreachable')
    monkeypatch.setattr(router.AgentFiles, 'download', broken)
    response = client.get(url)
    assert response.status_code == 503 and sandboxed(response) and response.content == b''
    assert response.headers['content-type'].startswith('text/plain')


def test_an_address_of_another_account_file_or_time_finds_nothing(client, monkeypatch):
    client, files, chat = client
    file_id = share(files, chat)
    other_file = share(files, chat, raw=PAGE + b'<p>second</p>', name='other.html')
    plain = share(files, chat, raw=b'<p>with a script from a CDN</p>', name='site.html', page=False)
    stranger_chat = files.chats.create_chat('stranger', execution_mode='agent')['id']

    def refused(url):
        response = client.get(url)
        assert response.status_code == 404 and sandboxed(response) and response.content == b''
        return True

    # A stranger gets no address for the file, with their own sign-in.
    assert client.post(f'/agent/chats/{chat}/files/{file_id}/page', headers={'x-test-uid': 'stranger'}).status_code == 404
    assert client.post(f'/agent/chats/{stranger_chat}/files/{file_id}/page', headers={'x-test-uid': 'stranger'}).status_code == 422
    # An address made for the stranger's account, or for another chat, opens nothing of the owner's.
    assert refused('/agent/pages/' + agent_pages.issue('stranger', chat, file_id))
    assert refused('/agent/pages/' + agent_pages.issue('stranger', stranger_chat, file_id))
    assert refused('/agent/pages/' + agent_pages.issue('owner', stranger_chat, file_id))
    # An address opens the file it was made for, never another.
    assert 'second' not in client.get(address(client, chat, file_id)).text
    assert 'second' in client.get(address(client, chat, other_file)).text
    assert refused('/agent/pages/' + agent_pages.issue('owner', chat, 'e' * 32))
    # A file that is no page has no address and no document.
    assert client.post(f'/agent/chats/{chat}/files/{plain}/page').status_code == 404
    assert refused('/agent/pages/' + agent_pages.issue('owner', chat, plain))
    # Past its time, and once the file is gone.
    good = address(client, chat, file_id)
    assert client.get(good).status_code == 200
    late = time.time() + agent_pages.TOKEN_SECONDS + 5
    with monkeypatch.context() as later:
        later.setattr(agent_pages.time, 'time', lambda: late)
        assert refused(good)
    fresh = address(client, chat, file_id)
    files.delete('owner', chat, file_id)
    assert refused(fresh)


def test_no_other_route_answers_a_chats_file_as_a_document(client):
    """An HTML, XHTML or SVG file leaves the download route as bytes to
    save, in both of its forms, and the page route answers only a page."""
    client, files, chat = client
    for name, mime, raw in (('benchmark.html', 'text/html', PAGE), ('old.xhtml', 'application/xhtml+xml', PAGE),
                            ('logo.svg', 'image/svg+xml', b'<svg xmlns="http://www.w3.org/2000/svg"><script>1</script></svg>'),
                            ('feed.xml', 'text/xml', b'<?xml version="1.0"?><a/>'),
                            ('feed.atom', 'application/atom+xml', b'<?xml version="1.0"?><feed/>')):
        file_id = files.save('owner', chat, raw=raw, name=name, mime=mime, extraction=READY,
                             extra={'kind': 'vm_file', **({'page': 'html'} if name == 'benchmark.html' else {})})['id']
        for query in ('', '?preview=1'):
            response = client.get(f'/agent/chats/{chat}/files/{file_id}{query}')
            assert response.status_code == 200 and response.content == raw
            assert response.headers['content-type'] == 'application/octet-stream', (name, query)
            assert response.headers['content-disposition'].startswith('attachment;')
            assert response.headers['x-content-type-options'] == 'nosniff'
    # What is no document keeps its type.
    text = files.save('owner', chat, raw=b'a,b\n1,2\n', name='data.csv', mime='text/csv', extraction=READY,
                      extra={'kind': 'vm_file'})['id']
    assert client.get(f'/agent/chats/{chat}/files/{text}').headers['content-type'].startswith('text/csv')
    # The browser learns that the file is a page, never where it lies.
    listed = {file['name']: file for file in client.get(f'/agent/chats/{chat}/files').json()['files']}
    assert listed['benchmark.html']['page'] == 'html' and 'page' not in listed['logo.svg']
    assert 'object_key' not in listed['benchmark.html']
