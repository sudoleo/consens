"""Browser regressions with mocked APIs and no paid calls or Firestore writes."""
import re

from playwright.sync_api import expect

from tests.e2e.test_phase4_frontend import (
    FIREBASE_AUTH_STUB, _real_firebase_page, phase4_server,
)


def test_app_renders_markdown_and_math_without_jsdelivr(browser, phase4_server):
    context, page = _real_firebase_page(browser, phase4_server)
    try:
        errors = []
        cdn_requests = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        context.route("https://cdn.jsdelivr.net/**", lambda route: (cdn_requests.append(route.request.url), route.abort()))
        page.reload(wait_until="networkidle")
        page.wait_for_function("() => typeof window.renderMathInElement === 'function'")
        page.evaluate(r"""() => {
            const target = document.createElement('div');
            target.id = 'vendor-regression';
            document.body.append(target);
            target.innerHTML = DOMPurify.sanitize(marked.parse('**Works** <img src=x onerror="alert(1)">'));
            const math = document.createElement('div');
            math.textContent = '\\(x^2\\)';
            target.append(math);
            renderMathInElement(math);
        }""")
        expect(page.locator('#vendor-regression strong')).to_have_text('Works')
        expect(page.locator('#vendor-regression [onerror]')).to_have_count(0)
        expect(page.locator('#vendor-regression .katex')).to_have_count(1)
        page.evaluate('document.fonts.ready')
        assert page.evaluate("document.fonts.check('12px KaTeX_Main')")
        assert not cdn_requests
        assert not errors
    finally:
        context.close()


def test_rejected_vote_and_login_tokens_are_handled(browser, phase4_server):
    context, page = _real_firebase_page(browser, phase4_server)
    try:
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.evaluate("""async () => {
            window.auth.currentUser.getIdToken = async () => { throw new Error('offline'); };
            await window.recordModelVote('OpenAI', 'BestModel', 'result');
            document.getElementById('loginEmail').value = 'test@example.invalid';
            document.getElementById('loginPassword').value = 'test-password';
            document.getElementById('loginButton').click();
        }""")
        expect(page.locator('#loginError')).to_contain_text('An error occurred')
        assert not errors
    finally:
        context.close()


def test_auth_refresh_failure_shows_recovery_message(browser, phase4_server):
    context, page = _real_firebase_page(browser, phase4_server)
    try:
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        stub = FIREBASE_AUTH_STUB.replace(
            'getIdToken: async () => "token-" + uid,',
            "getIdToken: async () => { throw new Error('offline'); },",
        )
        context.route('https://www.gstatic.com/firebasejs/9.22.0/firebase-auth.js',
                      lambda route: route.fulfill(content_type='application/javascript', body=stub))
        page.reload(wait_until='networkidle')
        expect(page.get_by_text(re.compile('Your session could not be refreshed'))).to_be_visible()
        expect(page.get_by_role('button', name='Reload', exact=True)).to_be_visible()
        expect(page.locator('#loginContainer .skeleton, #bookmarksContainer .skeleton')).to_have_count(0)
        assert not errors
    finally:
        context.close()
