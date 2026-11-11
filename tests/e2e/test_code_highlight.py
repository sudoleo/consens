"""A code block of an answer gets its syntax tones (code-highlight.js).

highlight.js only loads in a real browser: this reads blocks with the
vendored copy under the app's script policy (no inline script, no eval) and
holds what the tones may never do, change the code's text or bring markup of
the model's to life.
"""
import json
from pathlib import Path

from playwright.sync_api import expect

ROOT = Path(__file__).resolve().parents[2]
PIN = json.loads((ROOT / 'package.json').read_text(encoding='utf-8'))['devDependencies']['@highlightjs/cdn-assets']
CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
       "img-src * data:; object-src 'none'")
TOKENS = ('<style>:root{--ink:#0a0a0a;--ink-3:#5e5e5e;--agree:#217863;--dispute:#ad4b57}'
          '.dark-mode{--ink:#f5f5f5;--ink-3:#a1a1a1;--agree:#6dc0a4;--dispute:#f07f76}'
          'pre{color:var(--ink);font-family:monospace}</style>')
PYTHON = ('def area(r: float) -&gt; float:\n'
          '    # circle &lt;b&gt;area&lt;/b&gt;\n'
          '    return 3.14159 * r ** 2 if r &gt; 0 else float("nan")\n')


def _block(code, language):
    return f'<pre><code class="language-{language}">{code}</code></pre>' if language else f'<pre><code>{code}</code></pre>'


def _page(browser, body):
    context = browser.new_context()
    errors, requested, refused = [], [], []
    page = context.new_page()
    page.on('pageerror', lambda error: errors.append(str(error)))

    def serve(route):
        path = route.request.url.split('share.test', 1)[1].split('?', 1)[0]
        if path == '/s/example':
            route.fulfill(content_type='text/html', headers={'Content-Security-Policy': CSP}, body=(
                '<!doctype html><html><head><meta charset="utf-8">' + TOKENS
                + '<link rel="stylesheet" href="/static/css/code-highlight.css">'
                + '<script defer src="/static/js/code-highlight.js"></script>'
                + f'</head><body><main style="width:680px">{body}</main></body></html>'))
            return
        file = ROOT / path.lstrip('/')
        if path.startswith(('/static/vendor/highlightjs/', '/static/js/code-highlight.js',
                            '/static/css/code-highlight.css')) and file.is_file():
            if '/vendor/' in path:
                requested.append(path.split(f'/{PIN}/', 1)[1])
            route.fulfill(body=file.read_bytes(),
                          content_type='text/css' if path.endswith('.css') else 'text/javascript')
            return
        refused.append(route.request.url)
        route.abort()

    context.route('**/*', serve)
    page.goto('https://share.test/s/example')
    return context, page, errors, requested, refused


def test_a_block_gets_its_tones_and_keeps_its_text(browser):
    context, page, errors, requested, refused = _page(
        browser, f'<p>Before</p><div id="py">{_block(PYTHON, "python")}</div><div id="ts">{_block("const n: number = 1; // one", "ts")}</div>')
    try:
        expect(page.locator('#py pre')).to_have_attribute('data-lit', 'true', timeout=20000)
        expect(page.locator('#ts pre')).to_have_attribute('data-lit', 'true')
        seen = page.evaluate('''() => {
            const code = document.querySelector("#py code");
            const style = selector => getComputedStyle(code.querySelector(selector));
            return { text: code.textContent, tags: [...new Set([...code.querySelectorAll("*")].map(node => node.localName))],
                     keyword: [style(".hljs-keyword").fontWeight, style(".hljs-keyword").color],
                     comment: style(".hljs-comment").color, string: style(".hljs-string").color,
                     keywords: [...code.querySelectorAll(".hljs-keyword")].map(node => node.textContent) };
        }''')
        # Letter for letter the code that was there: what a copy takes.
        assert seen['text'] == ('def area(r: float) -> float:\n    # circle <b>area</b>\n'
                                '    return 3.14159 * r ** 2 if r > 0 else float("nan")\n')
        assert seen['tags'] == ['span']
        assert seen['keywords'][:2] == ['def', 'return']
        # The page's palette: heavier ink, the grey, the house green.
        assert seen['keyword'] == ['600', 'rgb(10, 10, 10)']
        assert seen['comment'] == 'rgb(94, 94, 94)' and seen['string'] == 'rgb(33, 120, 99)'
        # Tones are variables: dark follows without reading the block again.
        page.evaluate('() => document.documentElement.classList.add("dark-mode")')
        assert page.evaluate('() => getComputedStyle(document.querySelector("#py .hljs-comment")).color') == 'rgb(161, 161, 161)'
        assert requested == ['es/highlight.min.js'] and not refused and not errors
    finally:
        context.close()


def test_markup_in_the_code_stays_text(browser):
    hostile = '&lt;img src=https://leak.test/x.png onerror=window.pwned=1&gt;&lt;script&gt;window.pwned=2&lt;/script&gt;\n'
    context, page, errors, _requested, refused = _page(browser, _block(hostile, 'html') + _block(hostile, 'javascript'))
    try:
        expect(page.locator('pre[data-lit]')).to_have_count(2, timeout=20000)
        assert page.locator('pre img, pre script').count() == 0
        assert page.locator('pre code').first.text_content() == (
            '<img src=https://leak.test/x.png onerror=window.pwned=1><script>window.pwned=2</script>\n')
        assert page.evaluate('() => window.pwned') is None
        assert not refused and not errors
    finally:
        context.close()


def test_what_it_cannot_read_stays_as_it_was(browser):
    long = 'x = 1\n' * 12000
    context, page, errors, _requested, _refused = _page(
        browser, f'<div id="unknown">{_block("+[&gt;+&lt;-]", "brainfuck")}</div><div id="long">{_block(long, "python")}</div>'
                 f'<div id="diagram">{_block("pie", "mermaid")}</div><div id="bare">{_block("plain", "")}</div>')
    try:
        expect(page.locator('#unknown pre')).to_have_attribute('data-lit', 'plain', timeout=20000)
        expect(page.locator('#long pre')).to_have_attribute('data-lit', 'plain')
        assert page.locator('pre span').count() == 0
        assert page.locator('#unknown code').inner_html() == '+[&gt;+&lt;-]'
        # A diagram is diagram-render.js's, a block without a language nobody's.
        assert page.locator('#diagram pre').get_attribute('data-code') is None
        assert page.locator('#bare pre').get_attribute('data-code') is None
        assert not errors
    finally:
        context.close()


def test_a_page_without_code_asks_for_nothing(browser):
    context, page, errors, requested, refused = _page(browser, '<p>Plain</p>' + _block('plain', ''))
    try:
        page.wait_for_timeout(300)
        assert requested == [] and not refused and not errors
    finally:
        context.close()


def test_the_entry_is_the_pinned_copy():
    assert f'/static/vendor/highlightjs/{PIN}/es/highlight.min.js' in (
        ROOT / 'static/js/code-highlight.js').read_text(encoding='utf-8')
    assert (ROOT / f'static/vendor/highlightjs/{PIN}/LICENSE').is_file()
