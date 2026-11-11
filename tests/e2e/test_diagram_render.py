"""A ```mermaid block of an answer shows as its diagram (diagram-render.js).

Mermaid only runs in a real browser: this draws with the vendored copy under
the app's script policy (no inline script, no eval) and holds what the
drawing may never do, load or run anything of the model's.
"""
import base64
import json
from pathlib import Path

from playwright.sync_api import expect

ROOT = Path(__file__).resolve().parents[2]
PIN = json.loads((ROOT / 'package.json').read_text(encoding='utf-8'))['devDependencies']['mermaid']
# The app's script policy. Pictures are open to every host here, unlike in the
# app: a picture Mermaid asked for reaches `refused` instead of being stopped
# by the policy, so the tests see that nothing asks in the first place.
CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
       "img-src * data:; object-src 'none'")
TOKENS = ('<style>:root{--ground:#ffffff;--raise:#f3f3f3;--ink:#0a0a0a;--ink-3:#5e5e5e;--agree:#217863}'
          '.dark-mode{--ground:#050505;--raise:#151515;--ink:#f5f5f5;--ink-3:#a1a1a1;--agree:#6dc0a4}</style>')
FLOW = 'flowchart LR\n  A[Frage &amp; Antwort für Ägypten] --&gt; B{Suche nötig?}\n  B -- ja --&gt; C[Zeile eins&lt;br&gt;Zeile zwei]'


def _block(source):
    return f'<pre><code class="language-mermaid">{source}\n</code></pre>'


def _page(browser, body, width='680px', viewport=None, init=None):
    context = browser.new_context(**({'viewport': viewport} if viewport else {}))
    errors, requested, refused = [], [], []
    page = context.new_page()
    page.on('pageerror', lambda error: errors.append(str(error)))
    if init:
        # The page's policy runs no inline script; this one is the browser's.
        page.add_init_script(init)

    def serve(route):
        path = route.request.url.split('share.test', 1)[1].split('?', 1)[0]
        if path == '/s/example':
            route.fulfill(content_type='text/html', headers={'Content-Security-Policy': CSP}, body=(
                '<!doctype html><html><head><meta charset="utf-8">' + TOKENS
                + '<link rel="stylesheet" href="/static/css/diagram.css">'
                + '<script defer src="/static/js/diagram-render.js"></script>'
                + f'</head><body style="margin:0"><main style="width:{width}">{body}</main></body></html>'))
            return
        file = ROOT / path.lstrip('/')
        if path.startswith(('/static/vendor/mermaid/', '/static/js/diagram-render.js', '/static/css/diagram.css')) and file.is_file():
            if '/vendor/' in path:
                requested.append(path.split('/dist/', 1)[1])
            route.fulfill(body=file.read_bytes(),
                          content_type='text/css' if path.endswith('.css') else 'text/javascript')
            return
        refused.append(route.request.url)
        route.abort()

    context.route('**/*', serve)
    page.goto('https://share.test/s/example')
    return context, page, errors, requested, refused


def _drawing(page, selector='.md-diagram'):
    """The SVG of a drawn diagram's image, as text."""
    source = page.locator(f'{selector} img').get_attribute('src')
    assert source.startswith('data:image/svg+xml;base64,')
    return base64.b64decode(source.split(',', 1)[1]).decode('utf-8')


def test_a_block_is_drawn_as_an_image_of_its_own_size(browser):
    context, page, errors, requested, refused = _page(
        browser, f'<p>Before</p>{_block(FLOW)}<p id="after">After</p>')
    try:
        place = page.locator('.md-diagram')
        expect(place).to_have_class('md-diagram is-arriving has-size is-drawn', timeout=20000)
        # The image decodes: what Mermaid wrote as HTML ("&nbsp;", <br>) went in as XML.
        size = page.evaluate('''async () => {
            const img = document.querySelector(".md-diagram img");
            await img.decode();
            const box = document.querySelector(".md-diagram-figure").getBoundingClientRect();
            return { natural: [img.naturalWidth, img.naturalHeight], box: [box.width, box.height],
                     pre: getComputedStyle(document.querySelector(".md-diagram > pre")).display };
        }''')
        assert size['natural'][0] > 100 and size['natural'][1] > 40
        # As wide as the answer at most, at the drawing's own shape.
        assert size['box'][0] <= 680
        assert abs(size['box'][0] / size['box'][1] - size['natural'][0] / size['natural'][1]) < 0.05
        assert size['pre'] == 'none'
        svg = _drawing(page)
        # Mermaid sets a label word by word.
        assert all(word in svg for word in ('Frage', '&amp;', 'Ägypten', 'nötig?', 'Zeile', 'zwei'))
        # Labels are SVG text (Safari misplaces HTML labels in an image), flat, in the page's tones.
        assert '<foreignObject' not in svg and '<filter' not in svg and 'drop-shadow(' not in svg
        assert '#f3f3f3' in svg and '#0a0a0a' in svg
        assert page.locator('.md-diagram img').get_attribute('alt') == 'Diagram'
        assert requested[0] == 'mermaid.esm.min.mjs' and all(name.endswith('.mjs') for name in requested)
        assert not refused and not errors
    finally:
        context.close()


def test_the_drawing_follows_the_page_into_the_dark(browser):
    context, page, errors, _requested, _refused = _page(browser, _block('flowchart LR\n  A[One] --&gt; B[Two]'))
    try:
        place = page.locator('.md-diagram')
        expect(place).to_have_attribute('data-drawn', 'light', timeout=20000)
        size = page.locator('.md-diagram-figure').bounding_box()
        page.evaluate('document.documentElement.classList.add("dark-mode")')
        expect(place).to_have_attribute('data-drawn', 'dark')
        svg = _drawing(page)
        assert '#f5f5f5' in svg and '#151515' in svg and '#0a0a0a' not in svg
        assert page.locator('.md-diagram-figure').bounding_box() == size
        assert not errors
    finally:
        context.close()


def test_a_wide_diagram_stays_readable_on_a_phone_and_pans_in_its_place(browser):
    steps = ' --&gt; '.join(f'S{index}[Schritt Nummer {index}]' for index in range(1, 8))
    context, page, errors, _requested, _refused = _page(
        browser, f'<p>Before</p>{_block("flowchart LR" + chr(10) + "  " + steps)}', width='auto',
        viewport={'width': 390, 'height': 800})
    try:
        expect(page.locator('.md-diagram')).to_have_attribute('data-drawn', 'light', timeout=20000)
        size = page.evaluate('''() => {
            const place = document.querySelector(".md-diagram");
            const figure = place.querySelector(".md-diagram-figure");
            return { natural: Number(place.style.getPropertyValue("--diagram-width")), shown: figure.getBoundingClientRect().width,
                     place: [place.clientWidth, place.scrollWidth],
                     page: [document.documentElement.clientWidth, document.documentElement.scrollWidth] };
        }''')
        assert size['natural'] > 900
        # Three quarters of its own size (15 px labels stay above 11 px), not the 390 px of the screen.
        assert abs(size['shown'] - 0.75 * size['natural']) < 1
        assert size['place'][0] <= 390 < size['place'][1]
        # The page itself never pans.
        assert size['page'][1] <= size['page'][0]
        # The side it goes on to fades out, and so does the one left behind.
        place = page.locator('.md-diagram')
        expect(place).to_have_class('md-diagram is-arriving has-size is-drawn is-cut-end')
        place.evaluate('place => { place.scrollLeft = 120; }')
        expect(place).to_have_class('md-diagram is-arriving has-size is-drawn is-cut-end is-cut-start')
        place.evaluate('place => { place.scrollLeft = place.scrollWidth; }')
        expect(place).to_have_class('md-diagram is-arriving has-size is-drawn is-cut-start')
        assert not errors
    finally:
        context.close()


def test_a_written_diagram_is_counted_by_kind_and_outcome_without_its_words(browser):
    context, page, errors, _requested, _refused = _page(
        browser, '<p>Plain</p>', init='window.events = []; window.trackUmamiEvent = (name, data) => window.events.push([name, data]);')
    try:
        page.wait_for_function('() => typeof window.ConsensusDiagram === "object"')
        # What the stream asks for each finished block of a running answer.
        page.evaluate('''() => {
            for (const source of ["flowchart TD\\n  A[Secret plan] --> B", "stateDiagram-v2\\n  [*] --> Idle",
                                  "xychart-beta\\n  x-axis [Prüfer, Rest]\\n  bar [1, 2]", "Totally private words\\n  A --> B"]) {
              window.ConsensusDiagram.settled(source);
            }
        }''')
        page.wait_for_function('() => window.events.length === 4', timeout=20000)
        events = page.evaluate('() => window.events')
        assert all(name == 'app_diagram' and set(data) == {'kind', 'outcome'} for name, data in events)
        assert sorted((data['kind'], data['outcome']) for _name, data in events) == [
            ('flowchart', 'drawn'), ('other', 'syntax'), ('state', 'drawn'), ('xychart', 'syntax')]
        assert not errors
    finally:
        context.close()


def test_what_mermaid_cannot_read_stays_the_code_the_model_wrote(browser):
    context, page, errors, _requested, refused = _page(
        browser, _block('flowchart TD\n  A --&gt; --&gt; B (((') + _block('pie title Parts\n  "a" : 2\n  "b" : 1'))
    try:
        expect(page.locator('.md-diagram.is-drawn')).to_have_count(1, timeout=20000)
        broken = page.locator('.md-diagram').first
        expect(broken).to_have_class('md-diagram is-arriving is-code')
        expect(broken.locator('pre')).to_be_visible()
        expect(broken.locator('.md-diagram-figure')).to_be_hidden()
        # Mermaid leaves no error drawing and no workbench behind.
        assert page.locator('body > :not(main)').count() == 0
        assert not refused and not errors
    finally:
        context.close()


def test_nothing_of_the_models_loads_or_runs(browser):
    # Its own settings line asks for HTML labels, loose security, the layout
    # engine that is not shipped and its own style rules; the labels carry
    # markup; a click names a script.
    hostile = ('%%{init: {"securityLevel": "loose", "htmlLabels": true, "flowchart": {"htmlLabels": true}, '
               '"theme": "forest", "layout": "elk", '
               '"themeCSS": ".node rect { background: url(https://leak.test/css.png) }"}}%%\n'
               'flowchart LR\n'
               '  A["&lt;img src=https://leak.test/label.png onerror=window.pwned=1&gt;Text"] --&gt; B["&lt;b&gt;bold&lt;/b&gt;"]\n'
               '  click A href "javascript:window.pwned=2"\n'
               '  click B call alert(1)')
    context, page, errors, _requested, refused = _page(browser, _block(hostile))
    try:
        expect(page.locator('.md-diagram')).to_have_attribute('data-drawn', 'light', timeout=20000)
        page.locator('.md-diagram img').click()
        svg = _drawing(page)
        assert '<foreignObject' not in svg and '<image' not in svg and '<script' not in svg
        assert 'javascript:' not in svg and 'leak.test/css.png' not in svg and '#cde498' not in svg
        assert page.evaluate('window.pwned') is None
        assert not refused and not errors
    finally:
        context.close()


def test_a_block_that_would_fetch_a_picture_is_never_drawn(browser):
    # An image shape makes Mermaid load its address while it draws: such a
    # block is refused before Mermaid is even asked for.
    shape = 'flowchart LR\n  A@{ img: "https://leak.test/shape.png", label: "x", w: 60, h: 60 } --&gt; B'
    context, page, errors, requested, refused = _page(browser, _block(shape))
    try:
        expect(page.locator('.md-diagram')).to_have_class('md-diagram is-arriving is-code')
        page.wait_for_timeout(300)
        assert requested == [] and not refused and not errors
    finally:
        context.close()


def test_a_page_without_a_diagram_asks_for_nothing(browser):
    context, page, errors, requested, refused = _page(browser, '<p>Plain</p><pre><code>flowchart LR</code></pre>')
    try:
        page.wait_for_timeout(300)
        assert page.locator('.md-diagram').count() == 0
        assert requested == [] and not refused and not errors
    finally:
        context.close()


def test_the_entry_is_the_pinned_copy():
    assert f'/static/vendor/mermaid/{PIN}/dist/mermaid.esm.min.mjs' in (
        ROOT / 'static/js/diagram-render.js').read_text(encoding='utf-8')
    assert (ROOT / f'static/vendor/mermaid/{PIN}/LICENSE').is_file()
