"""Built app projection, keyboard/mobile layout and persisted message loading."""
import json
import os
import re
from pathlib import Path

import pytest
from playwright.sync_api import expect
from test_phase4_frontend import phase4_server, _real_firebase_page, _json
from test_agent_chat_frontend import CATALOG, _choose_mode


@pytest.mark.parametrize("width,dark", [(1440, False), (1440, True), (390, False), (390, True), (320, False)])
def test_agent_sidebar_real_app_and_saved_view(browser, phase4_server, width, dark):
    context, page = _real_firebase_page(browser, phase4_server)
    chat, turn, first, second = (c * 32 for c in "abcd")
    usage = {"input_tokens": 900, "output_tokens": 150, "estimated_cost_nano_usd": 3200000,
             "complete": True, "cost_complete": True, "cost_source": "provider", "measured_calls": 5}
    agents = [{"id": identity, "seq": i + 1, "message_seq": i + 1, "status": "review", "title": title,
               "model": {"model": "anthropic/claude-haiku-4.5", "label": "Claude Haiku 4.5"},
               "duration_ms": 3200, "usage": {**usage, "estimated_cost_nano_usd": 1000000, "measured_calls": 1}}
              for i, (identity, title) in enumerate(((first, "Check Germany"), (second, "Check France")))]
    agents.append({'id': 'e' * 32, 'seq': 3, 'message_seq': 3, 'status': 'completed', 'kind': 'judge',
                   'title': 'Coverage judge', 'model': {'model': 'openai/gpt-5.4-mini', 'label': 'GPT-5.4 Mini'},
                   'duration_ms': 2500, 'usage': usage, 'progress_text': 'Checking support for each statement.'})
    saved = {"id": turn, "turn_id": turn, "question": "Compare the two cases", "status": "completed", "position": 1,
             "execution_mode": "agent", "consensus": "Both checks are complete.", "sources": [], "model_answers": {},
             "agent_settings": {"model_id": "claude-haiku-4-5", "label": "Claude Haiku 4.5", "policy": {"delegation": True}},
             "agent_usage": usage, "agent_activity": []}
    requests, errors = [], []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        page.set_viewport_size({"width": width, "height": 900})
        page.route("**/user_status", lambda r: _json(r, {"tier": "pro", "is_pro": True, "agent_access": True, "limit": 500}))
        page.route("**/usage", lambda r: _json(r, {"tier": "pro", "is_pro": True, "remaining": 500, "total_limit": 500}))
        page.route("**/api/my/memory", lambda r: _json(r, {"memory": {"content": "", "revision": 0}}))
        page.route("**/chats", lambda r: _json(r, {"chat": {"id": chat, "execution_mode": "agent"}}))
        page.route("**/agent/models", lambda r: _json(r, CATALOG))
        page.route(f"**/agent/chats/{chat}/turns/{turn}/agents", lambda r: _json(r, {"agents": agents, "status": "succeeded", "usage": usage}))
        def details(route):
            requests.append(route.request.url)
            _json(route, {"agent": {"assignment": {"goal": "Check the premise against the supplied material.", "acceptance_criteria": "Cite the relevant passage."}},
                "messages": [{"id": "m1", "seq": 1, "sender": "orchestrator", "recipient": first, "kind": "message", "text": "Check the premise for Germany."},
                    {"id": "m2", "seq": 2, "sender": first, "recipient": "orchestrator", "kind": "question", "text": "Does the exception apply?"},
                    {"id": "m3", "seq": 3, "sender": "orchestrator", "recipient": first, "kind": "answer", "text": "Yes, apply the stated exception."}], "has_more": False})
        page.route(f"**/agent/chats/{chat}/turns/{turn}/agents/*", details)
        def answer(route):
            body = route.request.post_data_json
            final = {"chat_id": chat, "turn_id": turn, "response": saved["consensus"], "turn": saved,
                     "bookmark_meta": {"id": body["bookmark_id"], "title": "Compare the two cases", "query": saved["question"], "mode": "Agent", "has_consensus": True}}
            events = [("started", {"chat_id": chat, "turn_id": turn, "delegation": True})]
            events += [("delegation", {"version": 1, "id": str(i), "seq": i + 1, "chat_id": chat, "turn_id": turn, "agent": a}) for i, a in enumerate(agents)]
            events += [("final", final)]
            route.fulfill(content_type="text/event-stream", body="".join(f"event: {name}\ndata: {json.dumps(data)}\n\n" for name, data in events))
        page.route("**/agent", answer)
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        _choose_mode(page, "agent")
        page.evaluate("dark => { document.documentElement.classList.toggle('dark-mode', dark); document.body.classList.toggle('dark-mode', dark); }", dark)
        page.locator("#questionInput").fill(saved["question"])
        page.locator("#sendButton").click()
        sidebar = page.locator("#agentSidebar")
        expect(sidebar).to_be_visible()
        expect(page.locator(".agent-session")).to_have_count(3)
        expect(page.locator(".agent-sidebar-usage")).to_contain_text(re.compile(r'1[.,]050 tokens'))
        expect(page.locator('.agent-session-tokens').first).to_have_text(re.compile(r'1[.,]050 tokens'))
        expect(sidebar).not_to_contain_text('$')
        assert sidebar.evaluate('el => getComputedStyle(el).animationName') == 'agent-sidebar-enter'
        # Delay the first worker detail response while retaining real request
        # handling. The UI must acknowledge the click in the same frame.
        page.evaluate("""() => { const original = window.fetch; window.fetch = async (url, options) => {
          if (String(url).includes('/agents/') && !window.__detailDelayUsed) {
            window.__detailDelayUsed = true; await new Promise(resolve => setTimeout(resolve, 600));
          }
          return original(url, options);
        }; }""")
        page.locator(".agent-session summary").first.click()
        expect(page.locator('.agent-detail-skeleton')).to_be_visible()
        expect(page.locator('.agent-session-detail').first).to_have_attribute('aria-busy', 'true')
        expect(sidebar).to_contain_text("Orchestrator → Check Germany")
        expect(sidebar).to_contain_text("Does the exception apply?")
        expect(sidebar).to_contain_text("Yes, apply the stated exception.")
        expect(page.locator('.agent-session-detail').first).to_have_attribute('aria-busy', 'false')
        box = sidebar.bounding_box()
        assert box["x"] >= 0 and box["x"] + box["width"] <= width
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        if os.environ.get("AGENT_SCREENSHOTS"):
            target = Path(os.environ["AGENT_SCREENSHOTS"])
            target.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(target / f"delegation-{width}-{'dark' if dark else 'light'}.png"))
        page.locator('.agent-session summary').first.click()
        cached_requests = len(requests)
        page.locator('.agent-session summary').first.click()
        expect(sidebar).to_contain_text('Does the exception apply?')
        assert len(requests) == cached_requests
        page.locator('.agent-session summary').first.click()
        page.locator('.agent-session summary').last.click()
        expect(page.locator('.agent-judge-purpose')).to_contain_text('supported by the comparison answers')
        expect(page.locator('.agent-token-breakdown')).to_contain_text('900')
        expect(page.locator('.agent-detail-skeleton')).to_have_count(0)
        assert len(requests) == cached_requests
        if os.environ.get('AGENT_SCREENSHOTS'):
            page.screenshot(path=str(target / f"judge-{width}-{'dark' if dark else 'light'}.png"))
        page.emulate_media(reduced_motion='reduce')
        assert sidebar.evaluate('el => getComputedStyle(el).animationName') == 'none'
        assert page.locator('.container').evaluate('el => getComputedStyle(el).transitionDuration') == '0s'
        page.locator(".agent-sidebar-close").click()
        expect(sidebar).not_to_be_visible()
        # Same turn projection respects the saved manual close preference.
        page.evaluate("data => window.App.runRegistry.showSavedView({type:'bookmark'}, data)", {
            "chatId": chat, "turnId": turn, "executionMode": "agent", "question": saved["question"],
            "consensus": saved["consensus"], "currentTurn": saved})
        expect(sidebar).not_to_be_visible()
        page.locator(".agent-sidebar-toggle").click()
        expect(sidebar).to_be_visible()
        expect(page.locator(".agent-sidebar-close")).to_be_focused()
        page.keyboard.press("Escape")
        expect(sidebar).not_to_be_visible()
        expect(page.locator(".agent-sidebar-toggle")).to_be_focused()
        page.evaluate("async () => { await window.__switchE2EUser('account-b'); }")
        expect(sidebar).not_to_be_visible()
        assert not errors
        assert requests
    finally:
        context.close()
