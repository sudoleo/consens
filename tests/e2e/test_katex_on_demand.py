"""Public pages load KaTeX only for a formula (partials/katex.html).

When the server check misses one, math-render.js loads the files named in the
``katex-assets`` meta tag itself. This runs that path in a real browser: the
two scripts have to execute in order (katex before auto-render) and the
formula has to end up typeset.
"""
from pathlib import Path

from playwright.sync_api import expect

ROOT = Path(__file__).resolve().parents[2]
KATEX = ROOT / 'static/vendor/katex/0.19.0/dist'


def _page(browser, body):
    context = browser.new_context()
    errors = []
    requested = []
    page = context.new_page()
    page.on('pageerror', lambda error: errors.append(str(error)))

    def vendor(route):
        name = route.request.url.split('/katex/', 1)[1].split('?', 1)[0]
        requested.append(name)
        path = KATEX / name
        kind = 'text/css' if name.endswith('.css') else (
            'font/woff2' if name.endswith('.woff2') else 'application/javascript')
        route.fulfill(body=path.read_bytes(), content_type=kind)

    context.route('https://share.test/static/vendor/katex/**', vendor)
    context.route('https://share.test/s/example', lambda route: route.fulfill(
        content_type='text/html', body=f'''<!doctype html><html><head>
          <meta name="katex-assets"
                data-css="/static/vendor/katex/katex.min.css?v=1"
                data-js="/static/vendor/katex/katex.min.js?v=1"
                data-auto-render="/static/vendor/katex/contrib/auto-render.min.js?v=1">
        </head><body><main data-math-render>{body}</main></body></html>'''))
    page.goto('https://share.test/s/example')
    page.add_script_tag(content=(ROOT / 'static/js/math-render.js').read_text(encoding='utf-8'))
    # The page is already loaded, so start the scan the DOMContentLoaded
    # listener would have run.
    page.evaluate('document.querySelectorAll("[data-math-render]").forEach(window.ConsensusMath.render)')
    return context, page, errors, requested


def test_missed_formula_loads_katex_and_is_typeset(browser):
    context, page, errors, requested = _page(
        browser, r'<p id="f">Area is $\pi r^2$ and \[ a^2+b^2=c^2 \]</p>')
    try:
        expect(page.locator('#f .katex')).to_have_count(2)
        expect(page.locator('#f .katex-display')).to_have_count(1)
        assert page.locator('#f .katex-error').count() == 0
        assert page.evaluate(
            'getComputedStyle(document.querySelector("#f .katex")).fontFamily'
        ).startswith('KaTeX_Main')
        # Requested once each, however many blocks waited (fonts come after).
        assert sorted(name for name in requested if not name.startswith('fonts/')) == [
            'contrib/auto-render.min.js', 'katex.min.css', 'katex.min.js']
        assert not errors
    finally:
        context.close()


def test_page_without_formula_requests_nothing(browser):
    context, page, errors, requested = _page(browser, '<p>Costs $5 to $10, see my_file.</p>')
    try:
        page.wait_for_timeout(300)
        assert requested == []
        assert page.locator('script[src*="katex"]').count() == 0
        assert not errors
    finally:
        context.close()
