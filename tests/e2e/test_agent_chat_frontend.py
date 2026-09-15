"""Built /app and real Firebase UI with isolated HTTP fixtures; no paid calls.

Uses the same writer-free server as the Phase-4 suite. Backend authorization,
receipts and real streaming parsing are covered separately in test_agent_runs.
"""
import json
import os
from pathlib import Path

import pytest
from playwright.sync_api import expect
from test_phase4_frontend import phase4_server, _real_firebase_page, _json

CATALOG = {"default_model_id": "deepseek/deepseek-v4.1-flash", "models": [
    {"id": "deepseek/deepseek-v4.1-flash", "label": "DeepSeek V4.1 Flash", "reasoning_efforts": ["default", "low", "high", "max"], "reasoning_available": True},
    {"id": "gpt-5.6-sol", "label": "GPT-5.6 Sol", "reasoning_efforts": ["default", "low", "medium", "high"], "reasoning_available": True},
]}


@pytest.mark.parametrize("width,dark", [(1280, False), (390, False), (390, True), (320, False)])
def test_single_agent_send_followup_restore_and_layout(browser, phase4_server, width, dark):
    context, page = _real_firebase_page(browser, phase4_server)
    errors, requested, calls = [], [], []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("request", lambda request: requested.append(request.url.split("?")[0]))
    chat_id = "a" * 32
    turns = []
    bookmark = {}
    try:
        page.set_viewport_size({"width": width, "height": 900})
        page.route("**/user_status", lambda route: _json(route, {"tier": "pro", "is_pro": True,
            "agent_access": True, "limit": 500, "deep_limit": 50}))
        # Even an exhausted consensus allowance must not block shadow billing.
        page.route("**/usage", lambda route: _json(route, {"tier": "pro", "is_pro": True,
            "remaining": 0, "deep_remaining": 0, "total_limit": 500, "deep_total_limit": 50}))
        page.route("**/api/my/memory", lambda route: _json(route, {"memory": {"content": "", "revision": 0}}))
        page.route("**/chats", lambda route: _json(route, {"chat": {"id": chat_id, "execution_mode": "agent"}}))
        page.route("**/agent/models", lambda route: _json(route, CATALOG))
        def answer(route):
            body = route.request.post_data_json
            calls.append(body)
            turn_id = f"{len(turns) + 1:032x}"
            text = f"A **single model** answers: {body['question']}\n\nNo comparison was requested."
            model = next(item for item in CATALOG["models"] if item["id"] == body["model_id"])
            activity = [{"version": 1, "step_id": "completion:0", "id": "r1", "kind": "reasoning", "format": "summary", "text": "I am considering the question carefully."}]
            turn = {"id": turn_id, "turn_id": turn_id, "question": body["question"],
                "status": "completed", "position": len(turns) + 1, "mode": "Agent", "execution_mode": "agent",
                "consensus": text, "differences": "", "differences_data": None, "model_answers": {}, "sources": []}
            turn.update(agent_settings={"model_id": model["id"], "label": model["label"], "reasoning_effort": body["reasoning_effort"]},
                agent_activity=activity, agent_usage={"input_tokens": 1000, "output_tokens": 100, "estimated_cost_nano_usd": 180600})
            turns.append(turn)
            bookmark.update(id=body["bookmark_id"], query=body["question"], title="Explain the first step",
                mode="Agent", execution_mode="agent", chat_id=chat_id, turn_id=turn_id,
                responses={"consensus": text, "differences": ""}, sources=[])
            meta = {"id": body["bookmark_id"], "title": bookmark["title"], "query": body["question"],
                    "mode": "Agent", "has_consensus": True}
            final = {"chat_id": chat_id, "turn_id": turn_id, "response": text, "turn": turn, "bookmark_meta": meta}
            stream = "event: activity\ndata: " + json.dumps(activity[0]) + "\n\n"
            stream += "event: delta\ndata: " + json.dumps({"text": text}) + "\n\n"
            stream += "event: final\ndata: " + json.dumps(final) + "\n\n"
            route.fulfill(content_type="text/event-stream", body=stream)
        page.route("**/agent", answer)
        page.route("**/bookmarks/*/conversation*", lambda route: _json(route, {"chat_id": chat_id, "turns": turns, "next_cursor": None, "has_more": False}))
        page.route("**/bookmarks/*", lambda route: _json(route, {"bookmark": bookmark}))
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        expect(page.locator("#chatExecutionMode")).to_be_visible()
        page.evaluate("dark => { document.documentElement.classList.toggle('dark-mode', dark); document.body.classList.toggle('dark-mode', dark); }", dark)
        page.locator("#chatExecutionMode").select_option("agent")
        expect(page.locator("#agentModelDropdown")).to_be_enabled()
        expect(page.locator(".hero-greeting")).to_have_text("What can I help you with?")
        expect(page.locator(".demo-chip")).not_to_be_visible()
        page.locator("#agentModelControls .model-picker-display").click()
        expect(page.locator("#agentModelControls .model-picker-menu")).to_be_visible()
        menu = page.locator("#agentModelControls .model-picker-menu").bounding_box()
        assert menu["x"] >= 0 and menu["x"] + menu["width"] <= width
        if os.environ.get("AGENT_SCREENSHOTS"):
            target = Path(os.environ["AGENT_SCREENSHOTS"])
            target.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(target / f"agent-picker-{width}-{'dark' if dark else 'light'}.png"))
        if width == 1280:
            page.locator('#agentModelControls [data-value="deepseek/deepseek-v4.1-flash"]').focus()
            page.keyboard.press("ArrowDown")
            page.keyboard.press("Enter")
        else:
            page.locator('#agentModelControls [data-value="gpt-5.6-sol"]').click()
        page.locator("#agentReasoningEffort").select_option("medium")
        expect(page.locator("#composerAgentToggle")).not_to_be_visible()
        page.locator("#questionInput").fill("Explain the first step")
        page.locator("#sendButton").click()
        expect(page.locator("#agentAnswerBody")).to_contain_text("Explain the first step")
        page.wait_for_function("App.runRegistry.visible()?.status === 'succeeded'")
        expect(page.locator("#agentAnswer")).to_be_visible()
        expect(page.locator("#consensusOutput")).not_to_be_visible()
        expect(page.locator("#chatExecutionMode")).to_be_disabled()
        expect(page.locator("#agentAnswerLabel")).to_contain_text("GPT-5.6 Sol")
        page.locator("#questionInput").fill("Now explain the next step")
        page.locator("#agentModelControls .model-picker-display").click()
        page.locator('#agentModelControls [data-value="deepseek/deepseek-v4.1-flash"]').click()
        page.locator("#agentReasoningEffort").select_option("low")
        page.locator("#sendButton").click()
        page.wait_for_function("App.runRegistry.visible()?.status === 'succeeded' && App.runRegistry.visible().question.includes('next')")
        expect(page.locator("#threadHistory")).to_contain_text("Explain the first step")
        expect(page.locator("#threadHistory")).to_contain_text("Agent answer")
        expect(page.locator("#threadHistory")).to_contain_text("GPT-5.6 Sol")
        expect(page.locator("#agentAnswerLabel")).to_contain_text("DeepSeek V4.1 Flash")
        expect(page.locator("#agentAnswerActivity")).to_contain_text("I am considering")
        expect(page.locator("#agentAnswerBody")).to_contain_text("Now explain the next step")
        assert len(calls) == 2
        assert calls[0]["chat_id"] == calls[1]["chat_id"]
        assert calls[0]["model_id"] == "gpt-5.6-sol" and calls[0]["reasoning_effort"] == "medium"
        assert calls[1]["model_id"] == "deepseek/deepseek-v4.1-flash"
        assert not any(url.endswith(("/prepare", "/consensus", "/context")) or "/ask_" in url for url in requested)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        screenshot_dir = os.environ.get("AGENT_SCREENSHOTS")
        if screenshot_dir:
            target = Path(screenshot_dir)
            target.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(target / f"agent-{width}-{'dark' if dark else 'light'}.png"), full_page=True)
        # Exercise real bookmark materialization after throwing away run state.
        page.evaluate("() => App.runRegistry.clearAll('test-reload')")
        # The real bookmark row already routes through the public load path.
        if width < 1100 and page.locator("#toggleSidebarButton").get_attribute("aria-expanded") != "true":
            page.locator("#toggleSidebarButton").click()
        page.locator(f'.bookmark[data-id="{bookmark["id"]}"]').click()
        expect(page.locator("#agentAnswer")).to_be_visible()
        expect(page.locator("#agentAnswerBody")).to_contain_text("Now explain the next step")
        expect(page.locator("#agentAnswerActivity")).to_contain_text("I am considering")
        expect(page.locator("#agentReasoningEffort")).to_have_value("low")
        assert page.evaluate("App.agentChat.isSelected()")
        if width < 1100 and page.locator("#toggleSidebarButton").get_attribute("aria-expanded") != "true":
            page.locator("#toggleSidebarButton").click()
        page.locator("#newRunButton").click()
        if width < 1100 and page.locator("#toggleSidebarButton").get_attribute("aria-expanded") == "true":
            page.locator("#sidebarToggleInner").click()
        expect(page.locator("#chatExecutionMode")).to_be_enabled()
        page.locator("#chatExecutionMode").select_option("consensus")
        expect(page.locator("#agentAnswer")).not_to_be_visible()
        assert not errors
    finally:
        context.close()


def test_live_reasoning_disclosure_and_stop(browser, phase4_server):
    context, page = _real_firebase_page(browser, phase4_server)
    try:
        page.set_viewport_size({"width": 390, "height": 900})
        page.route("**/user_status", lambda route: _json(route, {"tier": "pro", "is_pro": True, "agent_access": True}))
        page.route("**/agent/models", lambda route: _json(route, CATALOG))
        page.route("**/chats", lambda route: _json(route, {"chat": {"id": "a" * 32}}))
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        page.locator("#chatExecutionMode").select_option("agent")
        expect(page.locator("#agentModelDropdown")).to_be_enabled()
        # Exercise the production SSE parser with a stream that remains open.
        # Mock fetch honors AbortSignal just as the real network request does.
        page.evaluate("""() => {
          const original = window.fetch;
          window.fetch = async (url, options) => {
            if (url !== '/agent') return original(url, options);
            const encoder = new TextEncoder();
            return new Response(new ReadableStream({ start(controller) {
              window.__emitAgent = event => controller.enqueue(encoder.encode('event: activity\\ndata: ' + JSON.stringify(event) + '\\n\\n'));
              window.__emitAgent({version:1, step_id:'completion:0', kind:'reasoning', id:'r1', format:'summary', text:'Checking the assumptions.', append:true});
              options.signal.addEventListener('abort', () => controller.error(new DOMException('Stopped', 'AbortError')));
            }}), {headers:{'Content-Type':'text/event-stream'}});
          };
        }""")
        page.locator("#questionInput").fill("Think about this question")
        page.locator("#sendButton").click()
        expect(page.locator("#agentAnswerActivity .agent-activity-title")).to_have_text("Thinking…")
        expect(page.locator("#agentAnswerActivity .agent-activity-reasoning")).to_be_visible()
        expect(page.locator("#agentAnswerBody")).to_be_empty()
        expect(page.locator("#agentModelDropdown")).to_be_disabled()
        page.locator("#agentAnswerActivity summary").click()
        page.evaluate("() => window.__emitAgent({version:1, step_id:'completion:0', kind:'reasoning', id:'r1', format:'summary', text:' Still checking.', append:true})")
        expect(page.locator("#agentAnswerActivity details")).not_to_have_attribute("open", "")
        # The send button's existing duplicate-gesture guard elapses naturally
        # while opening and closing the disclosure.
        page.wait_for_function("() => Date.now() - App.runRegistry.visible().startedAt > 800")
        page.locator("#sendButton").click()
        page.wait_for_function("() => App.runRegistry.visible()?.status === 'canceled'")
        expect(page.locator("#agentAnswerActivity .agent-activity-title")).to_have_text("Response stopped")
        expect(page.locator("#agentAnswerError")).to_have_text("Response stopped.")
    finally:
        context.close()
