"""The login / sign-up dialog: the first thing a newcomer has to get through.

Real static/firebase.js against a stubbed Firebase SDK that records every
call. No request reaches Firebase, Google or Firestore.
"""
import json

from playwright.sync_api import expect

from tests.e2e.test_phase4_frontend import (
    FIREBASE_AUTH_STUB, _json, _real_firebase_page, phase4_server,
)


RECORDING_AUTH_STUB = (
    "window.__authCalls = window.__authCalls || [];\n"
    + FIREBASE_AUTH_STUB
    .replace(
        "export async function signInWithEmailAndPassword() { return { user: auth.currentUser }; }",
        """export async function signInWithEmailAndPassword(_auth, email) {
  window.__authCalls.push(["password", email]);
  const error = new Error("Firebase: INVALID_LOGIN_CREDENTIALS (auth/internal-error).");
  error.code = "auth/internal-error";
  throw error;
}""",
    )
    .replace(
        "export async function signInWithPopup() { return { user: auth.currentUser }; }",
        """export async function signInWithPopup() {
  window.__authCalls.push(["popup"]);
  const error = new Error("closed");
  error.code = "auth/popup-closed-by-user";
  throw error;
}""",
    )
    .replace(
        "export async function signInWithRedirect() {}",
        'export async function signInWithRedirect() { window.__authCalls.push(["redirect"]); }',
    )
    .replace(
        "export async function getRedirectResult() { return null; }",
        """export async function getRedirectResult() {
  window.__authCalls.push(["redirect-result"]);
  return window.__redirectResult || null;
}""",
    )
    .replace(
        "export async function sendPasswordResetEmail() {}",
        """export async function sendPasswordResetEmail(_auth, email, settings) {
  window.__authCalls.push(["reset", email, settings ? settings.url : ""]);
}""",
    )
)
assert RECORDING_AUTH_STUB.count("__authCalls.push") == 5


def _guest_page(browser, server, init_script=None, path="/app"):
    context, page = _real_firebase_page(
        browser, server, initial_uid=None, path=path, init_script=init_script
    )
    context.route(
        "https://www.gstatic.com/firebasejs/9.22.0/firebase-auth.js",
        lambda route: route.fulfill(content_type="application/javascript", body=RECORDING_AUTH_STUB),
    )
    # The first load already consumed one-shot URL parameters (?setup=1).
    page.goto(server + path, wait_until="domcontentloaded")
    page.wait_for_function("() => window.__consensioAuthState?.known === true && !!window.App.openAuthModal")
    return context, page


def _calls(page):
    return page.evaluate("() => window.__authCalls")


def test_enter_submits_the_login_and_wrong_credentials_read_as_such(browser, phase4_server):
    context, page = _guest_page(browser, phase4_server)
    try:
        page.click("#authTopLoginBtn")
        expect(page.locator("#loginEmail")).to_be_focused()

        # Empty fields are caught here, not by a Firebase round trip.
        page.press("#loginEmail", "Enter")
        expect(page.locator("#loginError")).to_have_text("Please enter your e-mail address.")
        assert _calls(page) == []

        page.fill("#loginEmail", "someone@example.test")
        page.fill("#loginPassword", "not-the-password")
        page.click("#loginPasswordReveal")
        expect(page.locator("#loginPassword")).to_have_attribute("type", "text")
        page.press("#loginPassword", "Enter")

        # SDK 9.22 reports enumeration-protected wrong passwords as
        # auth/internal-error; the user must still read "wrong password".
        expect(page.locator("#loginError")).to_contain_text("E-mail or password is not correct")
        expect(page.locator("#loginButton")).to_be_enabled()
        expect(page.locator("#loginButton")).to_have_text("Log in")
        assert _calls(page) == [["password", "someone@example.test"]]
    finally:
        context.close()


def test_sign_up_is_one_field_and_the_inbox_is_one_tap_away(browser, phase4_server):
    context, page = _guest_page(browser, phase4_server)
    try:
        registrations = []

        def register(route):
            registrations.append(json.loads(route.request.post_data))
            if len(registrations) == 1:
                route.fulfill(status=422, content_type="application/json",
                              body=json.dumps({"detail": [{"msg": "invalid"}]}))
            else:
                _json(route, {"status": "check_inbox"})

        page.route("**/register", register)
        page.click("#authTopSignupBtn")
        expect(page.get_by_role("dialog", name="Create your free account")).to_be_visible()
        expect(page.locator("#authTabRegister")).to_have_attribute("aria-selected", "true")
        expect(page.locator("#loginPassword")).to_be_hidden()

        page.fill("#loginEmail", "new.person")
        page.press("#loginEmail", "Enter")
        expect(page.locator("#registerError")).to_contain_text("looks incomplete")
        assert registrations == []

        # A validation error from the server reads as a sentence, not "[object Object]".
        page.fill("#loginEmail", "new.person@gmail.com")
        page.click("#confirmRegisterButton")
        expect(page.locator("#registerError")).to_contain_text("looks incomplete")

        page.click("#confirmRegisterButton")
        expect(page.locator("#registrationSuccess")).to_be_visible()
        expect(page.locator("#registrationSuccessEmail")).to_have_text("new.person@gmail.com")
        expect(page.locator("#registrationMailboxLink")).to_have_text("Open Gmail")
        expect(page.locator("#registrationMailboxLink")).to_have_attribute("href", "https://mail.google.com/mail/u/0/#inbox")
        expect(page.locator("#registrationResendButton")).to_be_disabled()
        expect(page.locator("#authTabs")).to_be_hidden()
        assert registrations[-1] == {"email": "new.person@gmail.com"}
        assert page.evaluate("() => localStorage.getItem('consensio.authEmail')") == "new.person@gmail.com"

        page.click("#registrationChangeButton")
        expect(page.locator("#loginEmail")).to_have_value("new.person@gmail.com")
        expect(page.locator("#confirmRegisterButton")).to_be_visible()

        page.click("#confirmRegisterButton")
        page.click("#registrationLoginButton")
        expect(page.locator("#authTabLogin")).to_have_attribute("aria-selected", "true")
        expect(page.locator("#loginEmail")).to_have_value("new.person@gmail.com")
        expect(page.locator("#loginPassword")).to_be_focused()
    finally:
        context.close()


def test_forgot_password_answers_neutrally_and_leads_back_into_the_app(browser, phase4_server):
    context, page = _guest_page(browser, phase4_server)
    try:
        page.click("#authTopLoginBtn")
        page.click("#forgotPasswordButton")
        expect(page.locator("#loginError")).to_contain_text("Enter your e-mail address above")
        assert _calls(page) == []

        page.fill("#loginEmail", "maybe@example.test")
        page.click("#forgotPasswordButton")
        expect(page.locator("#loginNotice")).to_contain_text("If an account exists for maybe@example.test")
        assert _calls(page) == [["reset", "maybe@example.test", phase4_server + "/app?setup=1"]]
        assert "#" not in page.url
    finally:
        context.close()


def test_coming_back_from_the_setup_mail_opens_a_prefilled_login(browser, phase4_server):
    context, page = _guest_page(
        browser, phase4_server,
        init_script="localStorage.setItem('consensio.authEmail', 'new.person@example.test');",
        path="/app?setup=1",
    )
    try:
        expect(page.get_by_role("dialog", name="Log in to consens.io")).to_be_visible()
        expect(page.locator("#loginEmail")).to_have_value("new.person@example.test")
        expect(page.locator("#loginNotice")).to_have_text("Your password is set. Log in to start.")
        expect(page.locator("#loginPassword")).to_be_focused()
        assert "setup" not in page.url
    finally:
        context.close()


def test_closed_google_window_is_explained_next_to_the_google_button(browser, phase4_server):
    context, page = _guest_page(browser, phase4_server)
    try:
        page.click("#authTopLoginBtn")
        expect(page.locator("#inAppBrowserNotice")).to_be_hidden()
        page.click("#googleLoginButton")
        expect(page.locator("#googleError")).to_contain_text("The Google window closed before sign-in finished")
        expect(page.locator("#googleLoginButton")).to_be_enabled()
        expect(page.locator("#googleLoginLabel")).to_have_text("Continue with Google")
        assert _calls(page) == [["popup"]]
    finally:
        context.close()


def test_in_app_browser_gets_a_way_out_instead_of_a_dead_google_button(browser, phase4_server):
    ua = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 "
          "(KHTML, like Gecko) Mobile/15E148 [LinkedInApp]/9.30.1234")
    context, page = _guest_page(
        browser, phase4_server,
        init_script=f"Object.defineProperty(navigator, 'userAgent', {{ get: () => {json.dumps(ua)} }});",
    )
    try:
        page.click("#authTopSignupBtn")
        notice = page.locator("#inAppBrowserNotice")
        expect(notice).to_be_visible()
        expect(page.locator("#inAppBrowserName")).to_have_text("the LinkedIn app")
        expect(page.locator("#inAppOpenBrowser")).to_be_hidden()

        page.click("#googleLoginButton")
        assert "is-emphasized" in (notice.get_attribute("class") or "")
        assert _calls(page) == []
    finally:
        context.close()


def test_phone_with_first_party_auth_domain_uses_the_redirect_and_resumes(browser, phase4_server):
    ua = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 "
          "(KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1")
    first_party = f"""
      Object.defineProperty(navigator, 'userAgent', {{ get: () => {json.dumps(ua)} }});
      let config;
      Object.defineProperty(window, 'FIREBASE_CONFIG', {{
        configurable: true,
        get: () => config,
        set: value => {{ config = {{ ...value, authDomain: location.host }}; }},
      }});
    """
    context, page = _guest_page(browser, phase4_server, init_script=first_party)
    try:
        page.click("#authTopLoginBtn")
        page.click("#googleLoginButton")
        expect(page.locator("#googleLoginLabel")).to_have_text("Opening Google…")
        assert _calls(page) == [["redirect"]]
        assert page.evaluate("() => sessionStorage.getItem('consensio.googleRedirectPending')") == "1"

        # Back from Google with an account: the dialog closes by itself.
        context.add_init_script("window.__redirectResult = { user: { uid: 'google-user' } };")
        page.reload(wait_until="domcontentloaded")
        page.wait_for_function("() => (window.__authCalls || []).some(call => call[0] === 'redirect-result')")
        expect(page.locator("#loginModal")).to_be_hidden()
        assert page.evaluate("() => sessionStorage.getItem('consensio.googleRedirectPending')") is None
    finally:
        context.close()
