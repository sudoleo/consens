"""The empty composer invites the first question (static/js/composer-invite.js).

Guests type and sign in when they send; the question then goes out by itself.
Example questions fill the field and never send. Real bundles against a
stubbed Firebase SDK; model requests are routed, nothing is paid for.
"""
import json

from playwright.sync_api import expect

from tests.e2e.test_auth_dialog import _guest_page
from tests.e2e.test_phase4_frontend import _json, _real_firebase_page, phase4_server  # noqa: F401 (fixture)

VAT = "Do I charge VAT to US clients as a German freelancer?"
CAPTURE_EVENTS = (
    "window.__events = [];"
    "window.umami = { track: (name, data) => window.__events.push([name, data]) };"
)


def test_a_guest_picks_an_example_and_send_asks_for_the_sign_in(browser, phase4_server):
    context, page = _guest_page(browser, phase4_server)
    try:
        field = page.locator("#questionInput")
        starters = page.locator("#composerStarters")
        expect(field).to_be_enabled()
        expect(field).to_have_attribute("placeholder", "Ask anything, or paste an AI answer to check it")
        # A guest cannot choose models yet; the chip would only promise it.
        expect(page.locator(".consensus-model")).to_be_hidden()
        expect(starters).to_be_visible()
        expect(page.locator("#sendButton")).to_be_disabled()
        top = field.bounding_box()["y"]

        page.click('[data-starter="vat"]')
        expect(field).to_have_value(VAT)
        expect(field).to_be_focused()
        # The examples step back but keep their room: the field does not move.
        expect(starters).to_be_hidden()
        assert field.bounding_box()["y"] == top

        page.click("#sendButton")
        expect(page.locator("#loginModal")).to_be_visible()
        expect(page.locator("#authLead")).to_have_text(
            "Your question stays here and runs as soon as you're signed in.")
        # The reason stays on the other tab, and leaves with the dialog.
        page.click("#authTabLogin")
        expect(page.locator("#authLead")).to_contain_text("runs as soon as you're signed in")
        page.click("#closeLoginModal")
        page.click("#authTopLoginBtn")
        expect(page.locator("#authLead")).to_have_text("Pick up where you left off.")

        stored = page.evaluate("""() => ({
          draft: localStorage.getItem('consensio.questionDraft.v1'),
          pending: JSON.parse(localStorage.getItem('consensio.sendAfterLogin.v1')),
        })""")
        assert stored["draft"] == VAT
        assert stored["pending"]["source"] == "example"
    finally:
        context.close()


def test_a_guest_on_a_phone_gets_the_sentence_and_one_row_of_examples(browser, phase4_server):
    context, page = _guest_page(browser, phase4_server)
    try:
        page.set_viewport_size({"width": 375, "height": 812})
        expect(page.locator(".hero-greeting")).to_be_visible()
        expect(page.locator("#questionInput")).to_have_attribute("placeholder", "Ask, or paste an AI answer to check")
        layout = page.evaluate("""() => {
          const row = document.getElementById('composerStarters');
          const tops = new Set([...row.children].map(button => Math.round(button.offsetTop)));
          return { rows: tops.size, pageScroll: document.documentElement.scrollWidth > window.innerWidth };
        }""")
        assert layout == {"rows": 1, "pageScroll": False}
    finally:
        context.close()


def test_the_question_sent_as_a_guest_goes_out_after_the_sign_in(browser, phase4_server):
    context, page = _real_firebase_page(browser, phase4_server, init_script=CAPTURE_EVENTS)
    prepared = []
    try:
        page.route("**/prepare", lambda route: (
            prepared.append(route.request.post_data_json), _json(route, {"system_prompt": "Prepared prompt"})))
        page.route("**/ask_*", lambda route: _json(route, {"response": "An answer", "sources": []}))
        page.route("**/consensus", lambda route: _json(route, {}))
        # What a guest's Send left behind, then the page the sign-in reloads.
        page.evaluate("""pending => {
          localStorage.setItem('consensio.questionDraft.v1', 'Is creatine safe for teenagers?');
          localStorage.setItem('consensio.sendAfterLogin.v1', JSON.stringify({ ...pending, at: Date.now() }));
        }""", {"source": "example"})
        page.reload(wait_until="domcontentloaded")

        page.wait_for_function("() => window.App.runRegistry.visible()?.question === 'Is creatine safe for teenagers?'")
        page.wait_for_function("() => window.__events.some(([name]) => name === 'ask')")
        assert len(prepared) == 1
        state = page.evaluate("""() => ({
          pending: localStorage.getItem('consensio.sendAfterLogin.v1'),
          draft: localStorage.getItem('consensio.questionDraft.v1'),
          ask: window.__events.find(([name]) => name === 'ask')[1],
        })""")
        assert state["pending"] is None
        assert not state["draft"]
        assert state["ask"]["source"] == "example"
        assert state["ask"]["after_login"] is True

        # Only once: a further reload leaves the next question to the reader.
        page.reload(wait_until="domcontentloaded")
        page.wait_for_function("() => window.__consensioAuthState?.known === true")
        page.wait_for_timeout(500)
        assert len(prepared) == 1
    finally:
        context.close()
