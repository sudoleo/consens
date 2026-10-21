"""The first frame of /app is the settled app, and the start field stays put.

Apple-Audit B1, B2, B4, B5, B8, B10, B13, C2, F10: per animation frame the
composer's visible state is sampled after the frame (a message posted from
requestAnimationFrame), from the reload until the app has settled. What the
reader sees in the first frame must be what the app ends on.
"""
import json
import re
import urllib.request

import pytest
from playwright.sync_api import expect

from test_phase4_frontend import FIREBASE_APP_STUB, FIREBASE_AUTH_STUB, _json, _route_account_settings, phase4_server  # noqa: F401
from test_agent_chat_frontend import CATALOG

# The composer's face, one string per part (agent-chat.js, agent-mode.js,
# demo.js, model-picker.js draw these; app-bootstrap.js seeds them).
SAMPLER = r"""
(() => {
  if (window.__frames) return;
  const rows = window.__frames = [];
  let last = '';
  const shown = el => {
    if (!el || !el.isConnected || !el.getClientRects().length) return false;
    for (let node = el; node && node !== document.documentElement; node = node.parentElement) {
      const style = getComputedStyle(node);
      if (style.visibility === 'hidden' || +style.opacity === 0) return false;
    }
    return true;
  };
  const text = el => (el?.textContent || '').replace(/\s+/g, ' ').trim();
  const chip = selector => {
    const host = document.querySelector(selector);
    if (!shown(host)) return 'hidden';
    const display = host.querySelector('.model-picker-display');
    if (shown(display)) return 'chip:' + text(display);
    const select = host.querySelector('select');
    return shown(select) ? 'native:' + text(select.selectedOptions[0]) : 'empty';
  };
  function sample() {
    if (!document.body) return;
    const send = document.getElementById('sendButton');
    const header = document.querySelector('.app-mobile-header');
    const row = {
      send: shown(send) ? (send.disabled ? 'disabled' : 'enabled') : 'hidden',
      demo: shown(document.querySelector('.demo-chip')) ? 'demo' : '-',
      agent: chip('#agentModelControls'),
      consensus: chip('.consensus-model'),
      reasoning: shown(document.getElementById('composerModeBar')) ? text(document.getElementById('composerReasoningState')) : 'no bar',
      marks: document.querySelectorAll('#composerModelIcons .composer-model-icon').length,
      greeting: shown(document.querySelector('.hero-greeting')) ? text(document.querySelector('.hero-greeting')) : '-',
      tab: text(document.getElementById('viewSwitchConsensus')),
      switchInHeader: Boolean(header && shown(header.querySelector('.view-switch'))),
      newChat: text(document.getElementById('newRunButton')),
      guestButtons: shown(document.getElementById('authTopActions')),
    };
    const key = JSON.stringify(row);
    if (key !== last) { rows.push(row); last = key; }
  }
  const channel = new MessageChannel();
  channel.port1.onmessage = sample;
  const tick = () => { channel.port2.postMessage(0); requestAnimationFrame(tick); };
  requestAnimationFrame(tick);
})();
"""


def _context(browser, width, height, *, uid="account-a", mobile=False, init_script=None):
    context = browser.new_context(viewport={"width": width, "height": height}, is_mobile=mobile, has_touch=mobile,
                                  device_scale_factor=2 if mobile else 1)
    context.add_init_script(f"window.__E2E_INITIAL_UID = {json.dumps(uid)};")
    if init_script:
        context.add_init_script(init_script)
    context.add_init_script(SAMPLER)
    context.route("https://www.gstatic.com/firebasejs/9.22.0/firebase-app.js",
                  lambda route: route.fulfill(content_type="application/javascript", body=FIREBASE_APP_STUB))
    context.route("https://www.gstatic.com/firebasejs/9.22.0/firebase-auth.js",
                  lambda route: route.fulfill(content_type="application/javascript", body=FIREBASE_AUTH_STUB))
    context.route("https://cloud.umami.is/**", lambda route: route.fulfill(content_type="application/javascript", body="/* e2e */"))
    return context


def _routes(page, status=None):
    page.route("**/confirm-registration", lambda route: _json(route, {"status": "ok"}))
    page.route("**/auth/session", lambda route: _json(route, {"status": "ok"}))
    _route_account_settings(page)
    page.route("**/user_status", status or (lambda route: _json(route, {"tier": "pro", "is_pro": True, "agent_access": True})))
    page.route("**/usage", lambda route: _json(route, {"tier": "pro", "is_pro": True, "remaining": 500, "total_limit": 500}))
    page.route("**/api/my/memory", lambda route: _json(route, {"memory": {"content": "", "revision": 0}}))
    page.route("**/agent/models", lambda route: _json(route, CATALOG))
    page.route("**/agent/budget", lambda route: _json(route, {"token_budget": {"limit": 5000000, "used": 0, "remaining": 5000000}}))
    page.route("**/bookmarks?*", lambda route: _json(route, {"bookmarks": [], "next_cursor": None}))
    page.route("**/api/my/starter-questions", lambda route: _json(route, {"questions": []}))


def _settled(page):
    page.wait_for_function("() => window.__consensioAuthState?.known === true && typeof window.openShareDialog === 'function'")
    page.wait_for_function("() => !document.documentElement.classList.contains('agent-shell-expected')")
    page.wait_for_timeout(600)


def _frames(page):
    return page.evaluate("() => window.__frames")


@pytest.mark.parametrize("width,height,mobile", [(1400, 900, False), (390, 844, True)], ids=["desktop", "mobile"])
def test_a_reload_paints_the_composer_it_settles_on(browser, phase4_server, width, height, mobile):
    context = _context(browser, width, height, mobile=mobile)
    page = context.new_page()
    try:
        _routes(page)
        page.goto(phase4_server + "/app")
        _settled(page)
        expect(page.locator("#agentModelControls .model-picker-display-text")).to_have_text("DeepSeek V4.1 Flash")
        page.reload()
        _settled(page)
        frames = _frames(page)
        # One face from the first frame to the end: Agent's chip with the
        # model it had when the page was left, Reasoning "Auto", no demo, no
        # Consensus chip, a quiet Send (B1); "Chat" and "New chat" (B10).
        assert len(frames) == 1, frames
        first = frames[0]
        assert first["agent"].startswith("chip:DeepSeek V4.1 Flash"), first
        assert first["consensus"] == "hidden" and first["demo"] == "-" and first["send"] == "disabled", first
        assert first["reasoning"] == "Auto" and first["marks"] == 6, first
        assert first["tab"] == "Chat" and first["newChat"] == "New chat", first
        # On a phone the switch lives in the menu, never cut off in the bar (B2);
        # on a desktop the bar is only a wrapper (display: contents) around it.
        assert first["switchInHeader"] is not mobile
    finally:
        context.close()


def test_a_session_firebase_keeps_paints_the_account_before_firebase_answers(browser, phase4_server):
    """B4: no guest page first after a sign-in that stored only Firebase's own user."""
    html = urllib.request.urlopen(phase4_server + "/app").read().decode("utf-8")
    api_key = re.search(r'data-firebase-api-key="([^"]*)"', html).group(1)
    stored = json.dumps({"uid": "account-a", "emailVerified": True})
    context = _context(browser, 1400, 900, init_script=(
        f"if (!sessionStorage.getItem('seeded')) {{ sessionStorage.setItem('seeded', '1');"
        f" localStorage.setItem({json.dumps(f'firebase:authUser:{api_key}:[DEFAULT]')}, {json.dumps(stored)}); }}"))
    page = context.new_page()
    try:
        _routes(page)
        page.goto(phase4_server + "/app")
        _settled(page)
        frames = _frames(page)
        assert all(not frame["guestButtons"] and frame["demo"] == "-" for frame in frames), frames
        assert all(frame["agent"].startswith("chip:") and frame["greeting"] == "What can I help you with?" for frame in frames), frames
    finally:
        context.close()


def test_a_failed_status_check_keeps_agent_says_so_and_asks_again(browser, phase4_server):
    """B8: no silent switch to the old comparison view on one failed request."""
    calls = []

    def status(route):
        calls.append(1)
        if len(calls) == 1:
            route.fulfill(status=503, content_type="application/json", body='{"error": "busy"}')
        else:
            _json(route, {"tier": "pro", "is_pro": True, "agent_access": True})

    context = _context(browser, 1400, 900, init_script="localStorage.setItem('id_token', 'cached');")
    page = context.new_page()
    try:
        _routes(page, status=status)
        page.goto(phase4_server + "/app")
        expect(page.locator("#agentComposerMessage")).to_have_text("Your account could not be reached. Trying again…")
        page.locator("#agentComposerAction").click()
        _settled(page)
        assert len(calls) == 2
        expect(page.locator("#agentComposerNotice")).to_be_hidden()
        frames = _frames(page)
        assert all(frame["consensus"] == "hidden" and frame["demo"] == "-" and frame["greeting"] == "What can I help you with?"
                   for frame in frames), frames
        assert page.evaluate("App.agentChat.isSelected()")
    finally:
        context.close()


@pytest.mark.parametrize("width,height,mobile", [(1400, 900, False), (390, 844, True)], ids=["desktop", "mobile"])
def test_an_ended_session_becomes_the_guest_page_with_a_field_that_types(browser, phase4_server, width, height, mobile):
    """Review 1 (regression of B4): this browser remembers an account, but
    Firebase answers that the session has ended (password changed elsewhere,
    account disabled, a Google sign-in that came back without a user). The
    page turns into the guest page: the field takes typing, the guest buttons
    stand, and neither the account's model nor a Watches dot waits for an
    account that is not coming. A guest has Agent's chip with the default
    model (Apple-Audit H3)."""
    look = json.dumps({"uid": "account-a", "agentModel": "GPT-5.6 Sol", "agentEffort": "High"})
    context = _context(browser, width, height, uid=None, mobile=mobile,
                       init_script=f"localStorage.setItem('id_token', 'cached'); localStorage.setItem('consensio.firstFrame.v1', {json.dumps(look)});")
    # Firebase answers once every module is ready, as on a real network:
    # nothing else draws the field after that answer (the later route wins).
    slow = FIREBASE_AUTH_STUB.replace("queueMicrotask(() => window.__switchE2EUser(window.__E2E_INITIAL_UID));",
                                      "setTimeout(() => window.__switchE2EUser(window.__E2E_INITIAL_UID), 1500);")
    assert slow != FIREBASE_AUTH_STUB
    context.route("https://www.gstatic.com/firebasejs/9.22.0/firebase-auth.js",
                  lambda route: route.fulfill(content_type="application/javascript", body=slow))
    page = context.new_page()
    try:
        _routes(page)
        page.goto(phase4_server + "/app")
        page.wait_for_function("() => window.__consensioAuthState?.known === true && typeof window.openShareDialog === 'function'")
        page.wait_for_timeout(600)
        field = page.locator("#questionInput")
        expect(field).to_be_enabled()
        expect(field).to_have_attribute("aria-disabled", "false")
        expect(field).to_have_attribute("placeholder", re.compile("AI answer"))
        assert not page.evaluate("document.documentElement.classList.contains('agent-shell-expected')")
        assert page.evaluate("document.body.classList.contains('is-guest')")
        frames = _frames(page)
        # The remembered account's words first, the guest's in the end.
        assert frames[0]["agent"].startswith("chip:GPT-5.6 Sol"), frames
        last = frames[-1]
        label = page.evaluate("document.getElementById('appBootstrapConfig').dataset.agentDefaultLabel")
        assert last["guestButtons"] and last["agent"].startswith(f"chip:{label}"), last
        assert last["reasoning"] == "Auto" and last["consensus"] == "hidden", last
        assert not page.evaluate("document.getElementById('viewSwitchWatches').classList.contains('has-watch-pulse')")
        field.type("Still here")
        expect(field).to_have_value("Still here")
    finally:
        context.close()


@pytest.mark.parametrize("width,height,mobile", [(1400, 900, False), (390, 844, True)], ids=["desktop", "mobile"])
def test_a_guest_sees_agent_and_the_demo_offer_from_the_first_frame_and_it_fades_once(browser, phase4_server, width, height, mobile):
    """H3 (Max): a guest sees Agent's composer of a new chat as an account
    does by default, from the first frame to the end: the chip with the
    default model and the comparison count, Agent's greeting, Reasoning
    "Auto"; the demo offer stays a guest's (B13). One face, also on reload."""
    context = _context(browser, width, height, uid=None, mobile=mobile)
    page = context.new_page()
    agent_calls = []
    page.on("request", lambda request: agent_calls.append(request.url) if "/agent/" in request.url else None)
    try:
        _routes(page)
        page.goto(phase4_server + "/app")
        page.wait_for_function("() => window.__consensioAuthState?.known === true && typeof window.openShareDialog === 'function'")
        page.wait_for_timeout(600)
        page.reload()
        page.wait_for_function("() => window.__consensioAuthState?.known === true && typeof window.openShareDialog === 'function'")
        page.wait_for_timeout(600)
        frames = _frames(page)
        label = page.evaluate("document.getElementById('appBootstrapConfig').dataset.agentDefaultLabel")
        assert label
        assert len(frames) == 1, frames
        first = frames[0]
        assert first["demo"] == "demo" and first["send"] == "hidden" and first["guestButtons"], first
        assert first["agent"].startswith(f"chip:{label}") and first["agent"].endswith("+6"), first
        assert first["consensus"] == "hidden", first
        assert first["reasoning"] == "Auto" and first["marks"] == 6, first
        assert first["greeting"] == "What can I help you with?", first
        assert first["tab"] == "Chat" and first["switchInHeader"] is not mobile
        # Nothing a guest cannot have is asked for (the model list needs an account).
        assert agent_calls == [], agent_calls
        expect(page.locator("#agentComposerNotice")).to_be_hidden()
        # No Watches dot for a guest, on the phone's menu button neither (H2, review 3).
        assert not page.evaluate("document.getElementById('viewSwitchWatches').classList.contains('has-watch-pulse')")
        # The first keystroke retires the offer for good: it fades where it
        # stood while Send comes in (B13), then it is gone.
        page.evaluate("""() => { window.__leaving = false; const chip = document.querySelector('.demo-chip');
          new MutationObserver(() => { if (chip.classList.contains('is-leaving')) window.__leaving = true; })
            .observe(chip, { attributes: true, attributeFilter: ['class'] }); }""")
        page.locator("#questionInput").type("I")
        expect(page.locator("#sendButton")).to_be_visible()
        assert page.evaluate("() => window.__leaving") is True
        expect(page.locator(".demo-chip")).to_have_count(0)
        assert page.evaluate("localStorage.getItem('demoChipDismissed')") == "1"
    finally:
        context.close()


TRACK_FIELD = r"""() => {
  const rows = window.__field = [];
  const box = document.querySelector('.chat-input-container');
  const channel = new MessageChannel();
  channel.port1.onmessage = () => { const r = box.getBoundingClientRect(); rows.push([Math.round(r.top), Math.round(r.height)]); };
  const tick = () => { channel.port2.postMessage(0); if (!window.__stopField) requestAnimationFrame(tick); };
  requestAnimationFrame(tick);
}"""


def test_the_start_field_stays_put_and_grows_downward(browser, phase4_server):
    """B5: notices, the mail strip and new lines never move the field's top."""
    context = _context(browser, 1400, 900)
    page = context.new_page()
    try:
        _routes(page)
        page.goto(phase4_server + "/app")
        _settled(page)
        page.evaluate(TRACK_FIELD)
        page.locator("#questionInput").click()
        page.keyboard.type("A first line")
        for line in range(4):
            page.keyboard.press("Shift+Enter")
            page.keyboard.type(f"line {line + 2}")
        page.wait_for_timeout(300)
        page.evaluate("() => { document.getElementById('verifyBanner').hidden = false; }")
        page.evaluate("() => { const notice = document.getElementById('agentComposerNotice'); notice.hidden = false;"
                      " document.getElementById('agentComposerMessage').textContent = 'Loading chat models…'; }")
        page.wait_for_timeout(200)
        page.evaluate("() => { window.__stopField = true; }")
        rows = page.evaluate("() => window.__field")
        assert len({top for top, _ in rows}) == 1, rows
        heights = [height for _, height in rows]
        assert heights[-1] > heights[0]
        # Softly: the field's height glides (frames in between, not only whole
        # lines); a loaded machine may skip frames, so the transition itself
        # is checked as well.
        assert len(set(heights)) >= 4, heights
        assert page.evaluate("getComputedStyle(document.getElementById('questionInput')).transitionProperty") == "height"
        # The strip stands under the composer, the notice in the examples' place.
        banner = page.locator("#verifyBanner").bounding_box()
        section = page.locator(".input-section").bounding_box()
        assert banner["y"] >= section["y"] + section["height"] - 1
        expect(page.locator("#composerStarters")).to_have_css("visibility", "hidden")
    finally:
        context.close()


def test_the_empty_start_screen_fits_a_phone_on_its_side(browser, phase4_server):
    """F10: nothing to scroll on the empty start screen."""
    context = _context(browser, 667, 375, mobile=True)
    page = context.new_page()
    try:
        _routes(page)
        page.goto(phase4_server + "/app")
        _settled(page)
        assert page.evaluate("document.scrollingElement.scrollHeight <= innerHeight"), page.evaluate(
            "[document.scrollingElement.scrollHeight, innerHeight]")
        assert page.evaluate("getComputedStyle(document.documentElement).overscrollBehaviorY") == "none"
    finally:
        context.close()


NEVER_ENDING_AGENT = r"""() => {
  const realFetch = window.fetch;
  window.fetch = (url, options) => String(url) !== '/agent' ? realFetch(url, options)
    : Promise.resolve(new Response(new ReadableStream({ start() {} }), { headers: { 'Content-Type': 'text/event-stream' } }));
}"""


@pytest.mark.parametrize("width,height,mobile", [(1400, 900, False), (390, 844, True)], ids=["desktop", "mobile"])
def test_the_first_send_moves_the_field_in_one_movement(browser, phase4_server, width, height, mobile):
    """C2: the box glides and changes its shape together; it never stands at
    its end first, and nothing in it jumps before it moves."""
    context = _context(browser, width, height, mobile=mobile)
    page = context.new_page()
    try:
        _routes(page)
        page.route("**/chats", lambda route: _json(route, {"chat": {"id": "a" * 32, "execution_mode": "agent"}}))
        page.route("**/agent/chats/*/files*", lambda route: _json(route, {"files": [], "documents": []}))
        page.route("**/agent/chats/*/actions*", lambda route: _json(route, {"actions": []}))
        page.goto(phase4_server + "/app")
        _settled(page)
        page.evaluate(NEVER_ENDING_AGENT)
        page.locator("#questionInput").fill("Is a heat pump worth it in a 1970s house?")
        start = page.locator(".chat-input-container").bounding_box()
        page.evaluate(TRACK_FIELD)
        page.locator("#sendButton").tap() if mobile else page.locator("#sendButton").click()
        page.wait_for_timeout(800)
        page.evaluate("() => { window.__stopField = true; }")
        rows = [row for row in page.evaluate("() => window.__field")]
        end = page.locator(".chat-input-container").bounding_box()
        assert end["height"] < start["height"] - 40
        moving = [row for row in rows if (row[0], row[1]) != (round(start["y"]), round(start["height"]))]
        # Top goes down and height shrinks, frame by frame, never back.
        tops = [top for top, _ in moving]
        heights = [height for _, height in moving]
        assert tops == sorted(tops) and heights == sorted(heights, reverse=True), rows
        # More than a handful of frames between start and end: a glide.
        assert len(moving) >= 6, rows
        # No first frame that already stands at the end.
        assert abs(moving[0][0] - round(end["y"])) > 20, rows
    finally:
        context.close()
