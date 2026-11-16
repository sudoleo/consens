"""Saying so outside the tab (static/js/run-notify.js), through the real
bundles and SSE parser: a run that takes a while offers it in its live line,
only that click asks the browser, and a run that ends while the page is
hidden shows one notification. The browser's Notification is a stand-in
that records what it would show; nothing is paid for."""
from playwright.sync_api import expect

from test_agent_chat_frontend import CATALOG, _choose_mode
from test_phase4_frontend import _json, _real_firebase_page, phase4_server  # noqa: F401 (fixture)

BROWSER = """
(() => {
  let permission = 'default';
  window.__notes = [];
  window.__asked = 0;
  class Note {
    constructor(title, options) { Object.assign(this, { title, ...options, closed: false }); window.__notes.push(this); }
    close() { this.closed = true; }
  }
  Object.defineProperty(Note, 'permission', { get: () => permission });
  Note.requestPermission = () => { window.__asked += 1; permission = 'granted'; return Promise.resolve('granted'); };
  window.Notification = Note;
  let hidden = false;
  Object.defineProperty(document, 'hidden', { configurable: true, get: () => hidden });
  Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => (hidden ? 'hidden' : 'visible') });
  window.__hide = value => { hidden = value; document.dispatchEvent(new Event('visibilitychange')); };
})();
"""

STREAM = """() => {
  const original = window.fetch;
  window.fetch = async (url, options) => {
    if (url !== '/agent') return original(url, options);
    const encoder = new TextEncoder();
    return new Response(new ReadableStream({start(controller) {
      const emit = (type, event) => controller.enqueue(encoder.encode('event: ' + type + '\\ndata: ' + JSON.stringify(event) + '\\n\\n'));
      window.__note = text => emit('activity', {version: 1, step_id: 'completion:0', kind: 'progress', id: 'p1', text});
      window.__finish = () => {
        const response = 'The 2019 model pays for itself after nine winters.';
        emit('final', {response, chat_id: 'a'.repeat(32), turn_id: 'b'.repeat(32),
          turn: {id: 'b'.repeat(32), status: 'completed', execution_mode: 'agent', consensus: response,
            created_at: '2026-11-16T10:00:00Z', completed_at: '2026-11-16T10:01:13Z', agent_activity: []}});
        controller.close();
      };
      options.signal.addEventListener('abort', () => controller.error(new DOMException('Stopped', 'AbortError')));
    }}), {headers: {'Content-Type': 'text/event-stream'}});
  };
}"""


def test_a_long_run_offers_to_say_when_it_is_done_and_says_it_once(browser, phase4_server):
    def routes(page):
        page.route("**/user_status", lambda r: _json(r, {"tier": "pro", "is_pro": True, "agent_access": True}))
        page.route("**/agent/models", lambda r: _json(r, CATALOG))
        page.route("**/chats", lambda r: _json(r, {"chat": {"id": "a" * 32, "execution_mode": "agent"}}))

    context, page = _real_firebase_page(browser, phase4_server, init_script=BROWSER, before_goto=routes)
    try:
        expect(page.locator("#runNotifySetting")).to_be_attached()
        page.evaluate("() => App.userSettings.set('findings_to_agent', false)")
        _choose_mode(page, "agent")
        expect(page.locator("#agentModelDropdown")).to_be_enabled()
        page.evaluate(STREAM)
        page.locator("#questionInput").fill("Which heat pump pays for itself first?")
        page.locator("#sendButton").click()
        page.wait_for_function("() => typeof window.__note === 'function'")
        page.evaluate("() => window.__note('I compare the three offers against your budget.')")
        lines = page.locator("#agentAnswerActivity .agent-progress")
        status = lines.locator(".agent-current-status")
        expect(status).to_have_text("I compare the three offers against your budget.")
        offer = lines.locator(".agent-notify-offer")
        expect(offer).to_have_count(0)
        before = lines.bounding_box()["height"]

        # 20 s in: the offer stands at the end of the line, which keeps its height.
        page.evaluate("""() => {
          const run = App.runRegistry.visible();
          run.startedAt -= 25000;
          App.runRegistry.update(run.runId, () => {});
        }""")
        expect(offer).to_have_text("Notify me when it’s done")
        page.wait_for_timeout(400)
        assert lines.bounding_box()["height"] == before
        offer_box, status_box = offer.bounding_box(), status.bounding_box()
        assert abs(offer_box["y"] - status_box["y"]) < 1
        assert offer_box["x"] > status_box["x"] + status_box["width"]
        assert page.evaluate("window.__asked") == 0

        offer.locator("button").click()
        expect(offer).to_have_text("You’ll get a notification")
        assert page.evaluate("window.__asked") == 1

        # The answer stands while the page is in the background: one notification.
        page.evaluate("() => window.__hide(true)")
        page.evaluate("() => window.__finish()")
        page.wait_for_function("() => window.__notes.length === 1")
        note = page.evaluate("() => ({ title: window.__notes[0].title, body: window.__notes[0].body, tag: window.__notes[0].tag })")
        assert note["title"] == "Which heat pump pays for itself first?"
        assert note["body"] == "Your answer is ready."
        assert note["tag"].startswith("consens-run-")
        # The reviewers' marks after the answer are no news.
        page.evaluate("""() => {
          const run = App.runRegistry.visible();
          App.runRegistry.update(run.runId, item => { item.metadata.agentReview = { mode: 'audit', status: 'succeeded' }; });
        }""")
        page.wait_for_timeout(300)
        assert page.evaluate("window.__notes.length") == 1
        # Back in front, what it said is on screen: the notification goes.
        page.evaluate("() => window.__hide(false)")
        assert page.evaluate("window.__notes[0].closed") is True
        assert page.evaluate("localStorage.getItem('consensio.runNotify.v1')") == "on"
    finally:
        context.close()
