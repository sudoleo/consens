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
        expect(field).to_have_attribute("placeholder", "Ask anything, or paste an AI answer to check it")
        # Agent's composer of a new chat, as an account has it (H3): its chip
        # names the default model; choosing one asks for the login.
        expect(page.locator("#agentModelControls .model-picker-display")).to_be_visible()
        expect(page.locator(".consensus-model")).to_be_hidden()
        expect(starters).to_be_visible()
        expect(page.locator("#sendButton")).to_be_disabled()
        room = starters.bounding_box()["height"]
        gap_below_field = page.evaluate(NOTE_BELOW_FIELD)

        # Three curated questions per page load (starter_questions.py), then
        # "Check an AI answer".
        expect(starters.locator(".composer-starter")).to_have_count(4)
        expect(starters.locator(".composer-starter").last).to_have_attribute("data-starter", "check")
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
        page.route("**/bookmarks?*", lambda route: _json(route, {"bookmarks": chats, "next_cursor": None}))
        page.route("**/api/my/starter-questions", lambda route: (
            asked.append(route.request.method), _json(route, {"status": "success", "questions": PREDICTED})))
        page.reload(wait_until="domcontentloaded")

        visible = page.locator("#composerStarters .composer-starter:visible")
        expect(visible).to_have_text([item["label"] for item in PREDICTED] + ["Check an AI answer"])
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
        # firebase.js asks for the chats once the status is applied.
        def chats(route):
            while held:
                held.pop().continue_()
            route.fallback()
        page.route("**/static/dist/app.*.js", lambda route: held.append(route), times=1)
        page.route("**/bookmarks?*", chats, times=1)
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
        page.route("**/consensus", lambda route: _json(route, {}))
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


AGENT_CATALOG = {"default_model_id": "deepseek/deepseek-v4.1-flash", "models": [
    {"id": "deepseek/deepseek-v4.1-flash", "label": "DeepSeek V4.1 Flash", "reasoning_efforts": ["default"],
     "reasoning_available": True}]}


@pytest.mark.parametrize("chose", [None, "consensus"])
def test_a_guest_question_runs_after_the_sign_in_in_the_mode_the_guest_saw(browser, phase4_server, chose):
    """Apple-Audit H3 (Max): a guest sees Agent, so the question sent as a
    guest goes out in Agent after the sign-in. A guest who chose Consensus
    gets Consensus, also from an account that kept Agent, and the account
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
        page.route("**/consensus", lambda route: _json(route, {}))
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
            assert page.evaluate("App.runMode.preference()") == "consensus"
            page.wait_for_function("() => window.App.userSettings.status().loaded && !window.App.userSettings.status().pending.length")
            assert account["settings"]["run_mode"] == "consensus"
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
