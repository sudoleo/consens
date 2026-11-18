"""The login / sign-up dialog: the first thing a newcomer has to get through.

Real static/firebase.js against a stubbed Firebase SDK that records every
call. No request reaches Firebase, Google or Firestore.
"""
import json
import re

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
    # Firebase keeps a sign-in across the reload that follows it; here the
    # tab does (pages read it back through LINK_PERSISTENCE).
    .replace(
        "export async function signInWithCustomToken(_auth, token) {\n",
        """export async function signInWithCustomToken(_auth, token) {
  window.__authCalls.push(["custom-token", token]);
  sessionStorage.setItem("e2e.uid", String(token).replace(/^custom-token-/, ""));
""",
    )
)
assert RECORDING_AUTH_STUB.count("__authCalls.push") == 6
LINK_PERSISTENCE = "window.__E2E_INITIAL_UID = sessionStorage.getItem('e2e.uid') || window.__E2E_INITIAL_UID;"
LINK_CODE = "Ab3_" + "x" * 39


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
        expect(page.locator("#loginError")).to_have_text("Enter your email address.")
        assert _calls(page) == []

        page.fill("#loginEmail", "someone@example.test")
        page.fill("#loginPassword", "not-the-password")
        page.click("#loginPasswordReveal")
        expect(page.locator("#loginPassword")).to_have_attribute("type", "text")
        page.press("#loginPassword", "Enter")

        # SDK 9.22 reports enumeration-protected wrong passwords as
        # auth/internal-error; the user must still read "wrong password".
        expect(page.locator("#loginError")).to_contain_text("Email or password is not correct")
        expect(page.locator("#loginPassword")).to_have_attribute("aria-invalid", "true")
        expect(page.locator("#loginButton")).to_be_enabled()
        expect(page.locator("#loginButton")).to_have_text("Log in")
        assert _calls(page) == [["password", "someone@example.test"]]
    finally:
        context.close()


# The field was marked only when the text on screen equalled the German
# message, which the page translates a moment after it is set.
def test_a_wrong_password_marks_the_field_on_the_german_page_too(browser, phase4_server):
    context, page = _guest_page(browser, phase4_server)
    try:
        context.add_cookies([{"name": "consens_lang", "value": "de", "url": phase4_server}])
        page.goto(phase4_server + "/app", wait_until="domcontentloaded")
        page.wait_for_function("() => window.__consensioAuthState?.known === true && !!window.App.openAuthModal")
        page.click("#authTopLoginBtn")
        page.fill("#loginEmail", "someone@example.test")
        page.fill("#loginPassword", "not-the-password")
        page.press("#loginPassword", "Enter")
        expect(page.locator("#loginError")).to_contain_text("E-Mail oder Passwort ist falsch")
        expect(page.locator("#loginPassword")).to_have_attribute("aria-invalid", "true")
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
        # The mail holds the one button that logs in: no password step.
        expect(page.locator("#authLead")).to_have_text("Open the link and you’re in.")
        expect(page.locator("#registrationSuccess")).not_to_contain_text("password", use_inner_text=True, ignore_case=True)
        expect(page.locator("#registrationSetupText")).to_be_hidden()
        expect(page.locator("#registrationLoginButton")).to_be_hidden()
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
        expect(page.locator("#authTabRegister")).to_have_attribute("aria-selected", "true")
        assert _calls(page) == []
    finally:
        context.close()


def test_log_in_offers_a_link_instead_of_the_password(browser, phase4_server):
    context, page = _guest_page(browser, phase4_server)
    try:
        requests = []
        page.route("**/register", lambda route: (
            requests.append(json.loads(route.request.post_data)), _json(route, {"status": "check_inbox"})))
        page.click("#authTopLoginBtn")
        page.click("#emailLinkButton")

        expect(page.locator("#authTabLogin")).to_have_attribute("aria-selected", "true")
        expect(page.locator("#loginPassword")).to_be_hidden()
        expect(page.locator("#forgotPasswordButton")).to_be_hidden()
        expect(page.locator("#loginButton")).to_be_hidden()
        expect(page.locator("#sendLinkButton")).to_have_text("Email me a link")
        expect(page.locator("#loginEmail")).to_be_focused()

        page.press("#loginEmail", "Enter")
        expect(page.locator("#loginError")).to_have_text("Enter your email address.")
        assert requests == []

        page.fill("#loginEmail", "someone@gmail.com")
        page.press("#loginEmail", "Enter")
        expect(page.locator("#registrationSuccess")).to_be_visible()
        expect(page.locator("#authLead")).to_have_text("Open the link and you’re in.")
        assert requests == [{"email": "someone@gmail.com"}]

        # A typo: back to the link, not to the password.
        page.click("#registrationChangeButton")
        expect(page.locator("#sendLinkButton")).to_be_visible()
        expect(page.locator("#loginPassword")).to_be_hidden()
        expect(page.locator("#loginEmail")).to_have_value("someone@gmail.com")

        page.click("#passwordModeButton")
        expect(page.locator("#loginPassword")).to_be_focused()
        expect(page.locator("#emailLinkButton")).to_be_visible()
        assert _calls(page) == []
    finally:
        context.close()


def test_an_app_on_the_iphone_home_screen_signs_up_with_a_password(browser, phase4_server):
    """Its window keeps its own storage, which a link from the mail (opened in
    Safari) never reaches: the mail sets a password, as before the link."""
    context, page = _guest_page(
        browser, phase4_server,
        init_script="Object.defineProperty(navigator, 'standalone', { get: () => true });")
    try:
        registrations = []
        page.route("**/register", lambda route: (
            registrations.append(json.loads(route.request.post_data)), _json(route, {"status": "check_inbox"})))
        page.click("#authTopLoginBtn")
        expect(page.locator("#loginPassword")).to_be_visible()
        expect(page.locator("#emailLinkButton")).to_be_hidden()

        page.click("#authTabRegister")
        expect(page.locator("#singleMailNote")).to_have_text("No password needed yet. We’ll email you a link to set one.")
        page.fill("#loginEmail", "new.person@example.test")
        page.click("#confirmRegisterButton")
        expect(page.locator("#authLead")).to_have_text("One step left to your account.")
        expect(page.locator("#registrationSetupText")).to_be_visible()
        assert registrations == [{"email": "new.person@example.test", "password_setup": True}]

        page.click("#registrationLoginButton")
        expect(page.locator("#authTabLogin")).to_have_attribute("aria-selected", "true")
        expect(page.locator("#loginEmail")).to_have_value("new.person@example.test")
        expect(page.locator("#loginPassword")).to_be_focused()
        expect(page.locator("#emailLinkButton")).to_be_hidden()
    finally:
        context.close()


REDEEMED = {"token": "custom-token-account-a", "first": False}
REFUSED = {"error": "This link has expired or was already used.", "code": "link_invalid"}


def _link_page(browser, server, *, redeem=None, account=None, init_script="", initial_uid=None, before_goto=None):
    """A page opened from a sign-in mail (/app#signin=<code>).

    Returns the bodies sent to ask whose link it is (``asked``) and to spend
    it (``spent``). By default the link is account-a's and signs in."""
    asked, spent = [], []

    def routes(page):
        page.route("https://www.gstatic.com/firebasejs/9.22.0/firebase-auth.js",
                   lambda route: route.fulfill(content_type="application/javascript", body=RECORDING_AUTH_STUB))

        def ask(route):
            asked.append(route.request.post_data_json)
            (account or (lambda r: _json(r, {"email": "account-a@example.invalid"})))(route)

        def spend(route):
            spent.append(route.request.post_data_json)
            (redeem or (lambda r: _json(r, REDEEMED)))(route)

        page.route("**/auth/email-link/account", ask)
        page.route("**/auth/email-link", spend)
        if before_goto:
            before_goto(page)

    context, page = _real_firebase_page(
        browser, server, initial_uid=initial_uid, path="/app#signin=" + LINK_CODE,
        init_script=init_script + LINK_PERSISTENCE, before_goto=routes,
    )
    return context, page, asked, spent


def test_the_link_logs_in_at_once_in_the_browser_that_asked_for_it(browser, phase4_server):
    context, page, asked, spent = _link_page(
        browser, phase4_server,
        init_script="localStorage.setItem('consensio.authEmail', 'Account-A@example.invalid');")
    try:
        page.wait_for_function("() => window.__consensioAuthState?.uid === 'account-a' && !window.App.reloadingAfterSignIn")
        assert asked == [{"code": LINK_CODE}] and spent == [{"code": LINK_CODE}]
        assert "signin" not in page.url and "#" not in page.url
        expect(page.locator("#loginModal")).to_be_hidden()

        # The link is spent: another reload does not ask again.
        page.reload(wait_until="domcontentloaded")
        page.wait_for_function("() => window.__consensioAuthState?.known === true")
        page.wait_for_timeout(300)
        assert len(asked) == 1 and len(spent) == 1
    finally:
        context.close()


def test_another_browser_names_the_account_and_logs_in_only_after_the_click(browser, phase4_server):
    context, page, asked, spent = _link_page(browser, phase4_server)
    try:
        dialog = page.get_by_role("dialog", name="Your email link")
        expect(dialog).to_be_visible()
        expect(page.locator("#authLead")).to_have_text("Log in as account-a@example.invalid?")
        expect(page.locator("#linkConfirmButton")).to_have_text("Log in")
        expect(page.locator("#linkConfirmButton")).to_be_enabled()
        expect(page.locator("#loginForm")).to_be_hidden()
        expect(page.locator("#authTabs")).to_be_hidden()
        assert "signin" not in page.url

        # A page that loads the link and clicks nothing (a mail scanner)
        # leaves it usable.
        page.wait_for_timeout(500)
        assert asked == [{"code": LINK_CODE}] and spent == []
        assert page.evaluate("() => window.__consensioAuthState.uid") is None

        page.click("#linkConfirmButton")
        page.wait_for_function("() => window.__consensioAuthState?.uid === 'account-a' && !window.App.reloadingAfterSignIn")
        assert spent == [{"code": LINK_CODE}]
        expect(page.locator("#loginModal")).to_be_hidden()
        # The address was on screen a moment ago: nothing to announce now.
        expect(page.get_by_text("Logged in as")).to_have_count(0)
    finally:
        context.close()


def test_the_dialog_says_nothing_wrong_while_it_checks_the_link(browser, phase4_server):
    held = []
    context, page, asked, spent = _link_page(browser, phase4_server, account=held.append)
    try:
        expect(page.get_by_role("dialog", name="Your email link")).to_be_visible()
        expect(page.locator("#linkConfirmButton")).to_have_text("One moment…")
        expect(page.locator("#linkConfirmButton")).to_be_disabled()
        expect(page.locator("#authLead")).to_be_hidden()
        assert spent == []
    finally:
        for route in held:
            route.abort()
        context.close()


def test_an_expired_link_says_so_and_offers_a_new_one(browser, phase4_server):
    context, page, asked, spent = _link_page(
        browser, phase4_server, account=lambda route: _json(route, REFUSED, status=400),
        init_script="localStorage.setItem('consensio.authEmail', 'new.person@example.test');")
    try:
        registrations = []
        page.route("**/register", lambda route: (
            registrations.append(json.loads(route.request.post_data)), _json(route, {"status": "check_inbox"})))
        expect(page.get_by_role("dialog", name="Log in to consens.io")).to_be_visible()
        expect(page.locator("#authLead")).to_have_text("This link has expired or was already used.")
        expect(page.locator("#sendLinkButton")).to_have_text("Email me a new link")
        expect(page.locator("#sendLinkButton")).to_be_enabled()
        expect(page.locator("#loginEmail")).to_have_value("new.person@example.test")
        expect(page.locator("#linkConfirm")).to_be_hidden()
        assert asked == [{"code": LINK_CODE}] and spent == []
        assert "signin" not in page.url
        assert page.evaluate("() => window.__consensioAuthState.uid") is None

        page.click("#sendLinkButton")
        expect(page.locator("#registrationSuccess")).to_be_visible()
        assert registrations == [{"email": "new.person@example.test"}]
        # The new link is on its way: the old one's failure is no news anymore.
        page.click("#registrationChangeButton")
        expect(page.locator("#sendLinkButton")).to_be_visible()
        expect(page.locator("#authLead")).to_have_text("Pick up where you left off.")
    finally:
        context.close()


def test_an_expired_link_says_so_only_under_log_in(browser, phase4_server):
    context, page, _asked, _spent = _link_page(
        browser, phase4_server, account=lambda route: _json(route, REFUSED, status=400))
    try:
        expect(page.locator("#authLead")).to_have_text("This link has expired or was already used.")
        # Password instead of a new link: the failure still explains the way here.
        page.click("#passwordModeButton")
        expect(page.locator("#authLead")).to_have_text("This link has expired or was already used.")
        page.click("#authTabRegister")
        expect(page.locator("#authLead")).to_have_text(
            "Ask once and see where leading AI models agree and where they don’t.")
        page.click("#authTabLogin")
        expect(page.locator("#authLead")).to_have_text("Pick up where you left off.")
    finally:
        context.close()


def test_a_link_spent_between_the_question_and_the_click_says_so(browser, phase4_server):
    context, page, asked, spent = _link_page(
        browser, phase4_server, redeem=lambda route: _json(route, REFUSED, status=400))
    try:
        page.click("#linkConfirmButton")
        expect(page.locator("#authLead")).to_have_text("This link has expired or was already used.")
        expect(page.locator("#sendLinkButton")).to_have_text("Email me a new link")
        assert len(spent) == 1
        assert page.evaluate("() => window.__consensioAuthState.uid") is None
    finally:
        context.close()


def test_a_link_opened_in_an_open_app_tab_is_taken_too(browser, phase4_server):
    """Only the fragment changes when a mail app reuses the /app tab."""
    context, page = _guest_page(browser, phase4_server)
    try:
        asked = []
        page.route("**/auth/email-link/account", lambda route: (
            asked.append(route.request.post_data_json), _json(route, REFUSED, status=400)))
        page.evaluate(f"() => {{ location.hash = 'signin={LINK_CODE}'; }}")
        expect(page.locator("#authLead")).to_have_text("This link has expired or was already used.")
        assert asked == [{"code": LINK_CODE}]
        assert "signin" not in page.url
    finally:
        context.close()


def test_a_link_never_switches_the_account_in_use(browser, phase4_server):
    context, page, asked, spent = _link_page(
        browser, phase4_server, initial_uid="account-a",
        redeem=lambda route: _json(route, {"token": "custom-token-account-b", "first": False}))
    try:
        expect(page.get_by_text("You’re already logged in.")).to_be_visible()
        assert asked == [] and spent == []
        assert page.evaluate("() => window.__consensioAuthState.uid") == "account-a"
        assert "signin" not in page.url
    finally:
        context.close()


def test_closed_google_window_is_explained_next_to_the_google_button(browser, phase4_server):
    context, page = _guest_page(browser, phase4_server)
    try:
        page.click("#authTopLoginBtn")
        expect(page.locator("#inAppBrowserNotice")).to_be_hidden()
        page.click("#googleLoginButton")
        expect(page.locator("#googleError")).to_contain_text("The Google window closed before you were logged in")
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


def test_backdrop_closes_only_on_a_deliberate_click_without_typed_input(browser, phase4_server):
    context, page = _guest_page(browser, phase4_server)
    try:
        modal = page.locator("#loginModal")
        page.click("#authTopLoginBtn")
        expect(modal).to_be_visible()

        # A text selection dragged out of the field ends on the backdrop: the
        # click lands there, but the press began inside, so the dialog stays.
        page.fill("#loginEmail", "someone@example.test")
        field = page.locator("#loginEmail").bounding_box()
        page.mouse.move(field["x"] + field["width"] - 8, field["y"] + field["height"] / 2)
        page.mouse.down()
        page.mouse.move(6, 6, steps=6)
        page.mouse.up()
        expect(modal).to_be_visible()

        # Something is typed: a plain click beside the dialog does not lose it.
        page.mouse.click(6, 6)
        expect(modal).to_be_visible()
        expect(page.locator("#loginEmail")).to_have_value("someone@example.test")

        # Empty dialog: the backdrop is an exit again, and so is the close button.
        page.fill("#loginEmail", "")
        page.mouse.click(6, 6)
        expect(modal).to_be_hidden()
        page.click("#authTopLoginBtn")
        page.fill("#loginEmail", "someone@example.test")
        page.click("#closeLoginModal")
        expect(modal).to_be_hidden()
    finally:
        context.close()


def test_landing_field_arrives_with_the_caret_in_the_composer(browser, phase4_server):
    # Signed in: the caret is in the composer as soon as the account may type.
    context, page = _real_firebase_page(browser, phase4_server, path="/app?focus=1")
    try:
        page.goto(phase4_server + "/app?focus=1", wait_until="domcontentloaded")
        expect(page.locator("#questionInput")).to_be_enabled()
        expect(page.locator("#questionInput")).to_be_focused()
        assert "focus=" not in page.url
    finally:
        context.close()
    # A guest types too (signs in on Send, test_composer_invite.py): the
    # caret is in the field, no dialog and no demo in the way.
    context, page = _guest_page(browser, phase4_server, path="/app?focus=1")
    try:
        expect(page.locator("#questionInput")).to_be_enabled()
        expect(page.locator("#questionInput")).to_be_focused()
        expect(page.locator("#questionInput")).to_have_attribute(
            "placeholder", "Ask anything")
        assert "focus=" not in page.url
        expect(page.locator("#loginModal")).to_be_hidden()
    finally:
        context.close()


def test_a_guest_starts_with_the_sidebar_shut_and_signing_in_opens_it(browser, phase4_server):
    """The first visit begins at the question, not at an empty chat list.

    Without a choice of the reader's own: shut for a guest, open once the
    account is there; the app's own opening is not remembered as a choice.
    """
    context, page = _guest_page(browser, phase4_server)
    try:
        sidebar = page.locator("#appSidebar")
        toggle = page.locator("#toggleSidebarButton")
        expect(sidebar).to_have_class(re.compile(r"\bcollapsed\b"))
        expect(toggle).to_have_attribute("aria-expanded", "false")

        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        expect(sidebar).not_to_have_class(re.compile(r"\bcollapsed\b"))
        expect(toggle).to_have_attribute("aria-expanded", "true")
        assert page.evaluate("() => localStorage.getItem('sidebar_collapsed')") is None

        # The reader's own choice outlasts the next sign-in (the open
        # sidebar's own toggle; the floating one is hidden then).
        page.locator("#sidebarToggleInner").click()
        expect(sidebar).to_have_class(re.compile(r"\bcollapsed\b"))
        page.evaluate("async () => { await window.__switchE2EUser(null); }")
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        expect(sidebar).to_have_class(re.compile(r"\bcollapsed\b"))
    finally:
        context.close()

