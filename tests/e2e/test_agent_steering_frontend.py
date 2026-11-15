"""Steering a running Agent response, as in Claude Code: a message typed
while the agent works goes into the run before its next step, "Send now"
(or Ctrl+Enter) breaks off what runs for it, and the turn shows it as the
user's message once the agent read it. Built /app and real Firebase UI with
isolated HTTP fixtures; no paid calls. The run's side is covered in
tests/test_agent_notes.py.
"""
import json

import pytest
from playwright.sync_api import expect
from test_agent_chat_frontend import CATALOG, _choose_mode, _snapshot
from test_phase4_frontend import phase4_server, _real_firebase_page, _json  # noqa: F401  (fixture)

NOTE_ID = "abc123def456"


@pytest.mark.parametrize("width,dark", [(1280, False), (390, True)])
def test_steering_a_running_response(browser, phase4_server, width, dark):
    context, page = _real_firebase_page(browser, phase4_server)
    try:
        page.set_viewport_size({"width": width, "height": 900})
        page.route("**/user_status", lambda route: _json(route, {"tier": "free", "agent_access": True}))
        page.route("**/agent/models", lambda route: _json(route, CATALOG))
        page.route("**/chats", lambda route: _json(route, {"chat": {"id": "a" * 32}}))
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        page.evaluate("dark => { document.documentElement.classList.toggle('dark-mode', dark); document.body.classList.toggle('dark-mode', dark); }", dark)
        _choose_mode(page, "agent")
        # A response that stays open; the run's endpoints answer as the server does.
        page.evaluate("""noteId => {
          const original = window.fetch;
          window.__notes = [];
          window.fetch = async (url, options) => {
            if (String(url).endsWith('/notes')) {
              window.__notes.push({ url, body: JSON.parse(options.body) });
              return new Response(JSON.stringify({ status: 'added', id: window.__notes.length === 1 ? noteId : 'fed654cba321' }),
                { headers: { 'Content-Type': 'application/json' } });
            }
            if (String(url).endsWith('/now')) {
              window.__notes.push({ url, now: true });
              return new Response(JSON.stringify({ status: 'now' }), { headers: { 'Content-Type': 'application/json' } });
            }
            if (url !== '/agent') return original(url, options);
            const encoder = new TextEncoder();
            return new Response(new ReadableStream({ start(controller) {
              window.__emitAgent = event => controller.enqueue(encoder.encode('event: activity\\ndata: ' + JSON.stringify(event) + '\\n\\n'));
              window.__emitAgent({version:1, step_id:'completion:0', kind:'tool', id:'completion:0:call/tool', name:'web_search', status:'running'});
              options.signal.addEventListener('abort', () => controller.error(new DOMException('Stopped', 'AbortError')));
            }}), {headers:{'Content-Type':'text/event-stream'}});
          };
        }""", NOTE_ID)
        field = page.locator("#questionInput")
        field.fill("Compare the mortgage rates")
        page.locator("#sendButton").click()
        expect(page.locator("#agentAnswerActivity .agent-progress")).to_be_visible()
        if width < 700:
            # Sending collapses mobile controls; focus opens the actual composer.
            field.click()
        # Enter while it works: into the run, before its next step, not after it.
        field.fill("Only the 2026 figures")
        expect(page.locator("#sendButton")).to_have_attribute("title", "Send into the running response")
        field.press("Enter")
        row = page.locator("#agentQueue .agent-queue-item")
        expect(row.locator(".agent-queue-state")).to_have_text("Read before the next step")
        now = row.locator(".agent-queue-now")
        expect(now).to_have_text("Send now")
        assert page.evaluate("() => window.__notes[0].body") == {"text": "Only the 2026 figures"}
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        _snapshot(page, f"agent-steer-waiting-{width}-{'dark' if dark else 'light'}")
        now.click()
        expect(row.locator(".agent-queue-state")).to_have_text("Sending now…")
        expect(row.locator(".agent-queue-now")).to_have_count(0)
        assert page.evaluate("() => window.__notes[1].url").endswith(f"/notes/{NOTE_ID}/now")
        # The run read it: off the queue, into the turn as the user's message.
        page.evaluate(f"""() => window.__emitAgent({{version:1, step_id:'completion:1', id:'completion:1/note-{NOTE_ID}',
          kind:'progress', text:'Only the 2026 figures', from_user:true}})""")
        page.evaluate("""() => window.__emitAgent({version:1, step_id:'completion:1', kind:'tool',
          id:'completion:1:call/tool', name:'web_search', status:'running'})""")
        expect(page.locator("#agentQueue")).to_be_hidden()
        message = page.locator("#agentAnswerActivity .agent-user-messages .agent-user-message-text")
        expect(message).to_have_text("Only the 2026 figures")
        expect(page.locator("#agentAnswerActivity .agent-progress .agent-user-note")).to_have_count(0)
        # The user's side, as their question: on the right.
        bubble = page.locator("#agentAnswerActivity .agent-user-message").bounding_box()
        activity = page.locator("#agentAnswerActivity").bounding_box()
        assert abs((bubble["x"] + bubble["width"]) - (activity["x"] + activity["width"])) < 2
        _snapshot(page, f"agent-steer-read-{width}-{'dark' if dark else 'light'}")
        # Opened, the activity shows it at its place among the steps instead.
        page.locator("#agentAnswerActivity summary").click()
        expect(page.locator("#agentAnswerActivity .agent-activity-content .agent-user-note-text")).to_have_text(
            "Only the 2026 figures")
        expect(page.locator("#agentAnswerActivity .agent-user-messages")).to_be_hidden()
        page.locator("#agentAnswerActivity summary").click()
        if width >= 700:
            # Ctrl+Enter sends now in one go.
            field.fill("In German, please")
            field.press("Control+Enter")
            expect(row.locator(".agent-queue-state")).to_have_text("Sending now…")
            assert page.evaluate("() => window.__notes[2].body") == {"text": "In German, please", "now": True}
        page.wait_for_function("() => Date.now() - App.runRegistry.visible().startedAt > 800")
        field.fill("")
        page.locator("#sendButton").click()
        page.wait_for_function("() => App.runRegistry.visible()?.status === 'canceled'")
    finally:
        context.close()
