"""A finger is not a mouse (Apple audit F5): on a touch phone every control
of the composer, the drawer, an answer and the login dialog takes a 44 x 44 px
tap, measured with elementFromPoint, while what is drawn keeps its size."""
import json

import pytest
from playwright.sync_api import expect

from test_phase4_frontend import _json, _real_firebase_page, phase4_server  # noqa: F401
from test_agent_chat_frontend import CATALOG

# The tappable extent of an element along its centre row and column: how far
# from the middle a tap still lands on the element (or inside it).
HIT_AREA = r"""el => {
  const r = el.getBoundingClientRect();
  const cx = Math.min(innerWidth - 1, Math.max(0, r.left + r.width / 2));
  const cy = Math.min(innerHeight - 1, Math.max(0, r.top + r.height / 2));
  const owns = (x, y) => { const t = document.elementFromPoint(x, y); return Boolean(t && (t === el || el.contains(t))); };
  if (!owns(cx, cy)) return {covered: true, box: [r.width, r.height]};
  const reach = (dx, dy) => { let n = 0; while (n < 30 && owns(cx + dx * (n + 1), cy + dy * (n + 1))) n++; return n; };
  return {hit: [reach(-1, 0) + reach(1, 0) + 1, reach(0, -1) + reach(0, 1) + 1], box: [r.width, r.height]};
}"""


def assert_tappable(page, selector, drawn=None, at_least=44):
    element = page.locator(selector).first
    expect(element).to_be_visible()
    area = element.evaluate(HIT_AREA)
    assert not area.get("covered"), (selector, area)
    # Sampling at whole pixels from a fractional centre: 44 px reads 43 or 44.
    assert min(area["hit"]) >= at_least - 1, (selector, area)
    if drawn:
        assert [round(v) for v in area["box"]] == drawn, (selector, area)
    return area


def _pro_account(page):
    page.route("**/user_status", lambda r: _json(r, {"tier": "pro", "is_pro": True, "agent_access": True, "limit": 500, "deep_limit": 50}))
    page.route("**/usage", lambda r: _json(r, {"tier": "pro", "is_pro": True, "remaining": 100, "deep_remaining": 10,
                                               "total_limit": 500, "deep_total_limit": 50}))
    page.route("**/agent/models", lambda r: _json(r, CATALOG))
    page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
    page.wait_for_function("() => document.getElementById('runModeControl').hidden === false")


def _agent_answer_with_sources(page):
    page.route("**/chats", lambda r: _json(r, {"chat": {"id": "a" * 32}}))
    page.route("**/api/my/memory", lambda r: _json(r, {"memory": {"content": "", "revision": 0}}))
    sources = [{"url": "https://www.uci.org/rules", "title": "UCI regulations for road races"},
               {"url": "https://example.org/analysis", "title": "Analysis and methodology"},
               {"url": "https://news.example.com/report", "title": "Race report"}]
    text = ("The race starts in Monaco and climbs La Turbie [S1][S2][S3]. The route follows the coast. "
            "Riders should watch the traffic near Menton [S2].\n\nA second paragraph keeps the answer long enough to read.")
    turn = {"id": "b" * 32, "turn_id": "b" * 32, "status": "completed", "execution_mode": "agent",
            "question": "Where does the race start?", "consensus": text, "sources": sources, "agent_activity": [],
            "agent_settings": {"model_id": "deepseek/deepseek-v4.1-flash", "label": "DeepSeek V4.1 Flash", "reasoning_effort": "default"}}

    def respond(route):
        final = {"response": text, "chat_id": "a" * 32, "turn_id": turn["id"], "turn": turn, "sources": sources}
        body = "event: delta\ndata: " + json.dumps({"text": text}) + "\n\n"
        body += "event: final\ndata: " + json.dumps(final) + "\n\n"
        route.fulfill(content_type="text/event-stream", body=body)
    page.route("**/agent", respond)
    page.locator("#attachTrigger").click()
    page.locator('#runModeControl [data-value="agent"]').click()
    page.keyboard.press("Escape")
    page.locator("#questionInput").fill(turn["question"])
    page.locator("#sendButton").click()
    page.wait_for_function("() => App.runRegistry.visible()?.status === 'succeeded'")
    expect(page.locator("#agentAnswerBody .src-ref")).to_have_count(2)


@pytest.mark.parametrize("width", [320, 390])
def test_composer_drawer_and_answer_take_a_finger(browser, phase4_server, width):
    context, page = _real_firebase_page(browser, phase4_server, has_touch=True)
    try:
        page.set_viewport_size({"width": width, "height": 780})
        assert page.evaluate("matchMedia('(pointer: coarse)').matches")
        page.route("**/bookmarks?*", lambda r: _json(r, {"bookmarks": [
            {"id": "first", "title": "Where does the race start?", "query": "Where does the race start?", "mode": "Agent"}],
            "next_cursor": None}))
        _pro_account(page)
        page.evaluate("() => window.loadBookmarks()")
        # The start screen: (+), the models, Send or the demo, the bar under
        # the field and an example question. The drawing stays 36 / 28 px.
        for selector in ("#attachTrigger", ".composer-models .model-picker-display:visible",
                         "#composerReasoningToggle", "#composerAttachButton", "#composerModelPicker",
                         ".composer-starter:not([hidden])"):
            assert_tappable(page, selector)
        assert_tappable(page, "#attachTrigger", drawn=[36, 36])
        assert_tappable(page, "#composerReasoningToggle", drawn=[28, 32])
        send = "#sendButton:visible, .demo-chip:visible"
        assert_tappable(page, send)
        # Send draws its 36px circle in the middle of the 44px box.
        if page.locator("#sendButton").is_visible():
            assert page.locator("#sendButton").evaluate("el => getComputedStyle(el).backgroundClip") == "content-box"

        # The drawer.
        page.locator("#toggleSidebarButton").tap()
        page.wait_for_function("() => document.getElementById('appSidebar').getBoundingClientRect().left >= -.5")
        # The address takes the room of the plan line under it (a Free plan's
        # "Early access" link there keeps its own taps; the initial beside
        # them opens the same menu).
        for selector in ("#logoLink", "#bookmarksToggle", "#emailIcon", "#accountIdentity"):
            assert_tappable(page, selector)
        page.locator("#sidebarToggleInner").tap()

        # An answer: the source pill is a 19px mark in the line. It takes a
        # finger 44 px across and its own line up and down, no further: a
        # 44 px area reached over the words, links and pills of the lines
        # above and below. The quoted passage's cross is 22px.
        _agent_answer_with_sources(page)
        pill = page.locator("#agentAnswerBody .src-ref").first
        area = pill.evaluate(HIT_AREA)
        line = pill.evaluate("el => parseFloat(getComputedStyle(el.parentElement).lineHeight)")
        assert not area.get("covered"), area
        assert area["box"][1] < 24
        assert area["hit"][0] >= 43, area
        # Whole-pixel steps from a fractional centre read a 28.9 px line as 29 or 30.
        assert line - 2 <= area["hit"][1] <= line + 2, (area, line)
        page.evaluate("() => App.quote.set('The race starts in Monaco and climbs La Turbie.')")
        page.wait_for_function("""() => !document.body.classList.contains('composer-animating')
          && !document.body.classList.contains('composer-gliding')
          && !document.querySelector('.input-section').getAnimations({subtree: true}).some(a => a.playState === 'running')""")
        assert_tappable(page, "#composerQuoteRemove", drawn=[22, 22])
        assert_tappable(page, "#sendButton")

        # The activity sheet's close: a 34px square, 44px to the finger.
        page.evaluate("""() => App.agentDelegation.demo({turnId: 'demo-1', running: false, agents: [
          {id: 'demo-OpenAI', kind: 'comparison', title: 'OpenAI', status: 'completed', text: 'Send it.',
           model: {label: 'OpenAI', model: ''}, usage: {input_tokens: 10, output_tokens: 5, complete: true}}]})""")
        page.locator(".agent-sidebar-toggle").first.tap()
        expect(page.locator("#agentSidebar")).to_be_visible()
        page.wait_for_function("""() => !document.getElementById('agentSidebar')
          .getAnimations({subtree: true}).some(a => a.playState === 'running')""")
        assert_tappable(page, ".agent-sidebar-close", drawn=[34, 34])
    finally:
        context.close()


def test_login_dialog_and_public_bar_take_a_finger(browser, phase4_server):
    context, page = _real_firebase_page(browser, phase4_server, initial_uid=None, has_touch=True)
    try:
        page.set_viewport_size({"width": 320, "height": 700})
        page.locator("#authTopLoginBtn").tap()
        expect(page.locator("#loginModal")).to_be_visible()
        for selector in ("#authTabLogin", "#authTabRegister", "#loginPasswordReveal", "#loginModal .auth-footer-links a"):
            assert_tappable(page, selector)
        # Between the field and the button there are 39px; the link takes them all.
        assert_tappable(page, "#forgotPasswordButton", at_least=39)
        # Right under the password field the link does not take the field's taps.
        field = page.locator("#loginPassword").bounding_box()
        assert page.evaluate("([x, y]) => document.elementFromPoint(x, y).id", [field["x"] + 20, field["y"] + field["height"] - 2]) == "loginPassword"

        page.goto(phase4_server + "/", wait_until="domcontentloaded")
        page.set_viewport_size({"width": 390, "height": 780})
        for selector in (".site-nav .brand", ".nav-menu > summary", ".site-nav .nav-cta"):
            assert_tappable(page, selector)
    finally:
        context.close()
