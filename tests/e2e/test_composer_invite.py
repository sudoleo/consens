"""The empty composer invites the first question (static/js/composer-invite.js).

Guests type and sign in when they send; the question then goes out by itself.
Example questions fill the field and never send. Real bundles against a
stubbed Firebase SDK; model requests are routed, nothing is paid for.
"""
import json

import pytest
from playwright.sync_api import expect

from tests.e2e.test_auth_dialog import _guest_page
from tests.e2e.test_phase4_frontend import _json, _real_firebase_page, _route_account_settings, phase4_server  # noqa: F401 (fixture)

CAPTURE_EVENTS = (
    "window.__events = [];"
    "window.umami = { track: (name, data) => window.__events.push([name, data]) };"
)


NOTE_BELOW_FIELD = (
    "() => document.querySelector('.feedback-note').getBoundingClientRect().top"
    " - document.getElementById('questionInput').getBoundingClientRect().bottom"
)


def test_a_guest_picks_an_example_and_send_asks_for_the_sign_in(browser, phase4_server):
    context, page = _guest_page(browser, phase4_server)
    agent_calls = []
    page.on("request", lambda request: agent_calls.append(request.url) if "/agent" in request.url.split("/static/")[0] else None)
    try:
        field = page.locator("#questionInput")
        starters = page.locator("#composerStarters")
        expect(field).to_be_enabled()
        expect(field).to_have_attribute("placeholder", "Ask anything")
        # Agent's composer of a new chat, as an account has it: its chip
        # names the default model; choosing one asks for the login.
        expect(page.locator("#agentModelControls .model-picker-display")).to_be_visible()
        expect(page.locator(".consensus-model")).to_be_hidden()
        expect(starters).to_be_visible()
        expect(page.locator("#sendButton")).to_be_disabled()
        room = starters.bounding_box()["height"]
        gap_below_field = page.evaluate(NOTE_BELOW_FIELD)

        # Three curated questions per page load (starter_questions.py), in one
        # row, without "Check an AI answer".
        expect(starters.locator(".composer-starter")).to_have_count(3)
        expect(starters.locator('[data-starter="check"]')).to_have_count(0)
        tops = {round(box["y"]) for box in (starters.locator(".composer-starter").nth(i).bounding_box() for i in range(3))}
        assert len(tops) == 1, tops
        first = starters.locator(".composer-starter").first
        question = first.get_attribute("data-question")
        first.click()
        expect(field).to_have_value(question)
        expect(field).to_be_focused()
        # The examples step back but keep their room, so the centred composer
        # does not jump (a two-line question only grows the field itself).
        expect(starters).to_be_hidden()
        assert starters.bounding_box()["height"] == room
        # The note below glides up into their room instead of standing alone
        # under an empty gap. Measured from the field's bottom: a two-line
        # example grows the field.
        shift = page.evaluate(
            "() => parseFloat(getComputedStyle(document.querySelector('.input-section')).getPropertyValue('--starters-room'))")
        assert shift > room
        page.wait_for_function(f"() => Math.abs(({NOTE_BELOW_FIELD})() - {gap_below_field - shift}) < 1")

        page.click("#sendButton")
        expect(page.locator("#loginModal")).to_be_visible()
        expect(page.locator("#authLead")).to_have_text(
            "Your question stays here and runs as soon as you’re logged in.")
        # The reason stays on the other tab, and leaves with the dialog.
        page.click("#authTabLogin")
        expect(page.locator("#authLead")).to_contain_text("runs as soon as you’re logged in")
        page.click("#closeLoginModal")
        page.click("#authTopLoginBtn")
        expect(page.locator("#authLead")).to_have_text("Pick up where you left off.")

        stored = page.evaluate("""() => ({
          draft: JSON.parse(localStorage.getItem('consensio.questionDraft.v1')),
          pending: JSON.parse(localStorage.getItem('consensio.sendAfterLogin.v1')),
        })""")
        assert stored["draft"]["text"] == question
        assert stored["pending"]["source"] == "example"
        # Only exactly this text goes out by itself after the sign-in, in the
        # mode the account has: the guest chose none.
        assert stored["pending"]["text"] == question
        assert "mode" not in stored["pending"]
        # Nothing went to Agent, which needs an account.
        assert agent_calls == [], agent_calls
    finally:
        context.close()


def test_a_guest_on_a_phone_gets_the_sentence_and_one_row_of_examples(browser, phase4_server):
    context, page = _guest_page(browser, phase4_server)
    try:
        page.set_viewport_size({"width": 375, "height": 812})
        expect(page.locator(".hero-greeting:not(.hero-greeting-temporary)")).to_be_visible()
        expect(page.locator("#questionInput")).to_have_attribute("placeholder", "Ask anything")
        layout = page.evaluate("""() => {
          const row = document.getElementById('composerStarters');
          const tops = new Set([...row.children].map(button => Math.round(button.offsetTop)));
          return { rows: tops.size, pageScroll: document.documentElement.scrollWidth > window.innerWidth };
        }""")
        assert layout == {"rows": 1, "pageScroll": False}
    finally:
        context.close()


PREDICTED = [
    {"label": "Heat pump running costs?", "question": "What will a heat pump cost to run in our 1978 house per year?"},
    {"label": "AI Act deadlines?", "question": "Which EU AI Act deadlines apply to our support chatbot?"},
    {"label": "Creatine timing?", "question": "Does the time of day I take creatine change how I sleep?"},
]


def test_an_account_with_chats_gets_predicted_questions_from_the_first_frame(browser, phase4_server):
    context, page = _real_firebase_page(browser, phase4_server)
    asked = []
    try:
        chats = [{"id": f"chat_{index}", "query": f"Question {index}?", "title": f"Topic {index}"} for index in range(4)]
        # The examples belong to Agent's start screen; an account without
        # Agent starts in Compare.
        page.route("**/user_status", lambda route: _json(route, {"tier": "free", "is_pro": False, "agent_access": True}))
        page.route("**/agent/models", lambda route: _json(route, AGENT_CATALOG))
        page.route("**/bookmarks?*", lambda route: _json(route, {"bookmarks": chats, "next_cursor": None}))
        page.route("**/api/my/starter-questions", lambda route: (
            asked.append(route.request.method), _json(route, {"status": "success", "questions": PREDICTED})))
        page.reload(wait_until="domcontentloaded")

        visible = page.locator("#composerStarters .composer-starter:visible")
        # Three predicted, in one row, without "Check an AI answer".
        expect(visible).to_have_text([item["label"] for item in PREDICTED])
        assert asked == ["POST"]
        page.locator('[data-starter="predicted"]').first.click()
        expect(page.locator("#questionInput")).to_have_value(PREDICTED[0]["question"])
        page.fill("#questionInput", "")

        # The next visit paints them before the session is restored and asks
        # nothing while the newest chats are the same. The e2e auth stub's
        # token is no JWT; a real one names its account.
        page.evaluate("""() => localStorage.setItem('id_token',
          'header.' + btoa(JSON.stringify({ user_id: 'account-a' })) + '.signature')""")
        page.reload(wait_until="domcontentloaded")
        assert page.evaluate("document.querySelectorAll('[data-starter=\"predicted\"]').length") == 3
        page.wait_for_function("() => window.bookmarksData?.length === 4")
        page.wait_for_timeout(2500)
        assert asked == ["POST"]
    finally:
        context.close()


def _hold_back(page, first):
    """After the sign-in's reload the app starts (the deferred bundle runs
    initApp) while firebase.js asks for the account's status. Either may come
    first; this holds the other back. Call the result once the page loads."""
    held = []
    if first == "status":
        # The status has answered while the bundle is still on its way;
        # firebase.js applies it once the app has started.
        def status_answered(request):
            if request.url.endswith("/user_status"):
                while held:
                    held.pop().continue_()
        page.route("**/static/dist/app.*.js", lambda route: held.append(route), times=1)
        page.on("requestfinished", status_answered)
        return lambda: None
    started = []

    def status(route):
        if started:
            route.fallback()
        else:
            held.append(route)

    def release():
        page.wait_for_function("() => typeof window.updateQuestionInputAccess === 'function'")
        started.append(True)
        while held:
            held.pop().fallback()
    page.route("**/user_status", status, times=1)
    return release


# The status first once lost the question: the field was still empty when the
# session could run it, and that used up its one try.
@pytest.mark.parametrize("first", ["app", "status"])
def test_the_question_sent_as_a_guest_goes_out_after_the_sign_in(browser, phase4_server, first):
    context, page = _real_firebase_page(browser, phase4_server, init_script=CAPTURE_EVENTS)
    prepared = []
    try:
        page.route("**/prepare", lambda route: (
            prepared.append(route.request.post_data_json), _json(route, {"system_prompt": "Prepared prompt"})))
        page.route("**/ask_*", lambda route: _json(route, {"response": "An answer", "sources": []}))
        release = _hold_back(page, first)
        # What a guest's Send left behind, then the page the sign-in reloads.
        page.evaluate("""pending => {
          localStorage.setItem('consensio.questionDraft.v1', 'Is creatine safe for teenagers?');
          localStorage.setItem('consensio.sendAfterLogin.v1', JSON.stringify({ ...pending, at: Date.now() }));
        }""", {"source": "example"})
        page.reload(wait_until="domcontentloaded")
        release()

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


LINK_QUESTION = "Is creatine safe for teenagers?"


def _guest_waits_and_opens_the_link(browser, server, prepared, *, requested_here):
    """A guest's Send left the question waiting; then the mail's link opens."""
    from tests.e2e.test_auth_dialog import _link_page

    # What a guest's Send left behind, on the page before the sign-in only.
    remembered = "localStorage.setItem('consensio.authEmail', 'account-a@example.invalid');" if requested_here else ""
    waiting = CAPTURE_EVENTS + f"""
      if (!sessionStorage.getItem('e2e.uid')) {{
        {remembered}
        localStorage.setItem('consensio.questionDraft.v1', {json.dumps(LINK_QUESTION)});
        localStorage.setItem('consensio.sendAfterLogin.v1',
          JSON.stringify({{ source: 'typed', text: {json.dumps(LINK_QUESTION)}, at: Date.now() }}));
      }}"""

    def routes(page):
        page.route("**/prepare", lambda route: (
            prepared.append(route.request.post_data_json), _json(route, {"system_prompt": "Prepared prompt"})))
        page.route("**/ask_*", lambda route: _json(route, {"response": "An answer", "sources": []}))

    return _link_page(
        browser, server, init_script=waiting, before_goto=routes,
        redeem=lambda route: _json(route, {"token": "custom-token-account-a", "first": True}))


def test_the_question_sent_as_a_guest_goes_out_after_the_sign_in_link(browser, phase4_server):
    """The mail's link opens in the browser that sent the question: one click
    logs in, and the question runs once, as after any other sign-in."""
    question = LINK_QUESTION
    prepared = []
    context, page, asked, spent = _guest_waits_and_opens_the_link(
        browser, phase4_server, prepared, requested_here=True)
    try:
        page.wait_for_function(f"() => window.App.runRegistry.visible()?.question === {json.dumps(question)}")
        page.wait_for_function("() => window.__events.some(([name]) => name === 'ask')")
        assert len(asked) == 1 and len(spent) == 1 and len(prepared) == 1
        ask = page.evaluate("() => window.__events.find(([name]) => name === 'ask')[1]")
        assert ask["after_login"] is True
        assert page.evaluate("localStorage.getItem('consensio.sendAfterLogin.v1')") is None
    finally:
        context.close()


def test_a_link_asked_for_elsewhere_does_not_send_the_waiting_question(browser, phase4_server):
    """Confirmed in a browser that did not ask for this link: the account
    logs in, the question stays in the field and goes nowhere by itself."""
    prepared = []
    context, page, asked, spent = _guest_waits_and_opens_the_link(
        browser, phase4_server, prepared, requested_here=False)
    try:
        expect(page.locator("#authLead")).to_have_text("Log in as account-a@example.invalid?")
        assert page.evaluate("localStorage.getItem('consensio.sendAfterLogin.v1')") is not None
        page.click("#linkConfirmButton")
        page.wait_for_function("() => window.__consensioAuthState?.uid === 'account-a' && !window.App.reloadingAfterSignIn"
                               " && typeof window.updateQuestionInputAccess === 'function'")
        expect(page.locator("#questionInput")).to_have_value(LINK_QUESTION)
        page.wait_for_timeout(800)
        assert len(spent) == 1 and prepared == []
        assert page.evaluate("localStorage.getItem('consensio.sendAfterLogin.v1')") is None
        assert not page.evaluate("() => window.__events.some(([name]) => name === 'ask')")
    finally:
        context.close()


AGENT_CATALOG = {"default_model_id": "deepseek/deepseek-v4.1-flash", "models": [
    {"id": "deepseek/deepseek-v4.1-flash", "label": "DeepSeek V4.1 Flash", "reasoning_efforts": ["default"],
     "reasoning_available": True}]}


@pytest.mark.parametrize("chose", [None, "compare"])
def test_a_guest_question_runs_after_the_sign_in_in_the_mode_the_guest_saw(browser, phase4_server, chose):
    """A guest sees Agent, so the question sent as a
    guest goes out in Agent after the sign-in. A guest who chose Compare
    gets Compare, also from an account that kept Agent, and the account
    keeps that choice."""
    context, page = _real_firebase_page(browser, phase4_server, init_script=CAPTURE_EVENTS)
    agent, prepared = [], []
    try:
        page.route("**/user_status", lambda route: _json(route, {"tier": "free", "is_pro": False, "agent_access": True}))
        page.route("**/agent/models", lambda route: _json(route, AGENT_CATALOG))
        page.route("**/agent/budget", lambda route: _json(route, {"token_budget": {"limit": 660000, "used": 0, "remaining": 660000}}))
        page.route("**/api/my/memory", lambda route: _json(route, {"memory": {"content": "", "revision": 0}}))
        page.route("**/chats", lambda route: _json(route, {"chat": {"id": "a" * 32, "execution_mode": "agent"}}))
        page.route("**/agent/chats/*/files*", lambda route: _json(route, {"files": [], "documents": []}))
        page.route("**/agent/chats/*/actions*", lambda route: _json(route, {"actions": []}))
        # The Agent run itself is held open: only its request matters here.
        page.route("**/agent", lambda route: agent.append(route.request.post_data_json))
        page.route("**/prepare", lambda route: (
            prepared.append(route.request.post_data_json), _json(route, {"system_prompt": "Prepared prompt"})))
        page.route("**/ask_*", lambda route: _json(route, {"response": "An answer", "sources": []}))
        account = _route_account_settings(page, {"run_mode": "agent"}, revision=3)
        question = "Is creatine safe for teenagers?"
        # What a guest's Send left behind, then the page the sign-in reloads.
        page.evaluate("""pending => {
          localStorage.setItem('consensio.questionDraft.v1', pending.text);
          localStorage.setItem('consensio.sendAfterLogin.v1', JSON.stringify({ ...pending, at: Date.now() }));
        }""", {"source": "typed", "text": question, **({"mode": chose} if chose else {})})
        page.reload(wait_until="domcontentloaded")

        page.wait_for_function(f"() => window.App.runRegistry.visible()?.question === {json.dumps(question)}")
        page.wait_for_function("() => window.__events.some(([name]) => name === 'ask')")
        assert page.evaluate("localStorage.getItem('consensio.sendAfterLogin.v1')") is None
        if chose:
            page.wait_for_function("() => window.App.runRegistry.visible()?.config?.executionMode !== 'agent'")
            assert len(prepared) == 1 and not agent
            assert page.evaluate("App.runMode.preference()") == "compare"
            page.wait_for_function("() => window.App.userSettings.status().loaded && !window.App.userSettings.status().pending.length")
            assert account["settings"]["run_mode"] == "compare"
        else:
            for _ in range(50):
                if agent:
                    break
                page.wait_for_timeout(100)
            assert len(agent) == 1 and agent[0]["question"] == question, agent
            assert not prepared
            assert page.evaluate("window.App.runRegistry.visible().config.executionMode") == "agent"
            assert account["settings"]["run_mode"] == "agent"
    finally:
        context.close()


# /app#q=… (app-bootstrap.js): a question from outside fills the field and
# never sends. In the fragment it reaches no server; the address loses it at
# once, so a reload fills nothing again.
QUESTION_LINK = "/app#q=Is+creatine+safe+for+teenagers%3F+%28C%2B%2B+%26+more%29"
LINKED = "Is creatine safe for teenagers? (C++ & more)"


def _sent(page):
    sent = []
    page.on("request", lambda request: sent.append(request.url)
            if request.method == "POST" and any(part in request.url for part in ("/agent", "/prepare", "/ask_")) else None)
    return sent


def test_a_question_link_waits_in_a_guests_field_through_the_sign_in_check(browser, phase4_server):
    # The guest's field is emptied once Firebase answers and refilled from the
    # draft (firebase.js): the link's question has to survive that.
    context, page = _real_firebase_page(browser, phase4_server, initial_uid=None, path=QUESTION_LINK,
                                        init_script=CAPTURE_EVENTS)
    sent = _sent(page)
    try:
        field = page.locator("#questionInput")
        expect(field).to_have_value(LINKED)
        expect(field).to_be_focused()
        assert page.evaluate("[location.hash, location.pathname]") == ["", "/app"]
        assert page.evaluate("document.getElementById('questionInput').selectionStart") == len(LINKED)
        page.wait_for_timeout(600)
        expect(field).to_have_value(LINKED)
        assert sent == []
        # Sending is the guest's own click, and asks for the sign-in.
        page.click("#sendButton")
        expect(page.locator("#loginModal")).to_be_visible()
        pending = page.evaluate("JSON.parse(localStorage.getItem('consensio.sendAfterLogin.v1'))")
        assert pending["text"] == LINKED and pending["source"] == "link"
        assert ["app_question_link", {"filled": True, "guest": True}] in page.evaluate("window.__events")
        assert sent == []
    finally:
        context.close()


def test_a_question_link_fills_an_accounts_field_once_and_never_over_a_draft(browser, phase4_server):
    context, page = _real_firebase_page(browser, phase4_server, path=QUESTION_LINK)
    sent = _sent(page)
    try:
        field = page.locator("#questionInput")
        expect(field).to_have_value(LINKED)
        expect(field).to_be_focused()
        assert page.evaluate("location.hash") == ""
        page.wait_for_timeout(600)
        assert sent == []
        # A reload of the address it left fills nothing.
        page.reload(wait_until="domcontentloaded")
        page.wait_for_function("() => window.__consensioAuthState?.known === true")
        expect(field).to_have_value("")

        # While the app is open the browser changes only the fragment (the
        # address bar's keyword in this tab).
        field.fill("My own words")
        page.evaluate("location.hash = '#?q=Someone+else'")
        page.wait_for_function("() => location.hash === ''")
        expect(field).to_have_value("My own words")
        field.fill("")
        page.evaluate("location.hash = '#?q=A+second+question'")
        expect(field).to_have_value("A second question")
        expect(field).to_be_focused()
        assert sent == []
    finally:
        context.close()


def test_a_long_question_from_a_link_shows_its_start_with_the_caret_at_its_end(browser, phase4_server):
    # Its last lines alone could read otherwise than the whole.
    lines = "%0A".join(f"Line+{index}" for index in range(30))
    context, page = _real_firebase_page(browser, phase4_server, path=f"/app#q={lines}")
    try:
        field = page.locator("#questionInput")
        expect(field).to_be_focused()
        page.wait_for_timeout(300)
        state = page.evaluate("""() => {
          const input = document.getElementById('questionInput');
          return { top: input.scrollTop, overflows: input.scrollHeight > input.clientHeight + 1,
            caret: input.selectionStart, length: input.value.length };
        }""")
        assert state["overflows"], state
        assert state["top"] == 0, state
        assert state["caret"] == state["length"], state
    finally:
        context.close()
