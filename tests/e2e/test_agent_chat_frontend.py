"""Built /app and real Firebase UI with isolated HTTP fixtures; no paid calls.

Uses the same writer-free server as the Phase-4 suite. Backend authorization,
receipts and real streaming parsing are covered separately in test_agent_runs.
"""
import json
import os
import re
from pathlib import Path

import pytest
from playwright.sync_api import expect
from test_phase4_frontend import phase4_server, _real_firebase_page, _json

CATALOG = {"default_model_id": "deepseek/deepseek-v4.1-flash", "models": [
    {"id": "deepseek/deepseek-v4.1-flash", "label": "DeepSeek V4.1 Flash", "reasoning_efforts": ["default", "low", "high", "max"], "reasoning_available": True},
    {"id": "gpt-5.6-sol", "label": "GPT-5.6 Sol", "reasoning_efforts": ["default", "low", "medium", "high"], "reasoning_available": True},
    {"id": "plain", "label": "Model without reasoning", "reasoning_efforts": ["default"], "reasoning_available": False},
    {"id": "long", "label": "A model with a particularly long display name", "reasoning_efforts": ["default", "high"], "reasoning_available": True},
    {"id": "claude-haiku-4-5", "label": "Claude Haiku 4.5", "reasoning_efforts": ["default"], "reasoning_available": True,
     "tools_by_effort": {"default": ["web_search"]}},
]}


def _choose_mode(page, mode):
    page.locator("#chatExecutionControl .model-picker-display").click()
    page.locator(f'#chatExecutionControl [data-value="{mode}"]').click()
    expect(page.locator("#chatExecutionMode")).to_have_value(mode)


def _snapshot(page, name):
    if not os.environ.get("AGENT_SCREENSHOTS"):
        return
    target = Path(os.environ["AGENT_SCREENSHOTS"])
    target.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(target / f"{name}.png"))


def _choose_effort(page, effort):
    page.locator(".agent-model-picker .model-picker-display").click()
    page.locator('.agent-reasoning-option').click()
    menu = page.locator(".agent-model-picker .model-picker-menu").bounding_box()
    assert menu["x"] >= 0 and menu["x"] + menu["width"] <= page.viewport_size["width"]
    assert menu["y"] >= 0 and menu["y"] + menu["height"] <= page.viewport_size["height"]
    theme = page.evaluate("() => document.body.classList.contains('dark-mode') ? 'dark' : 'light'")
    position = page.evaluate("() => document.body.classList.contains('is-hero') ? 'hero' : 'thread'")
    _snapshot(page, f"agent-effort-{position}-{page.viewport_size['width']}-{theme}")
    page.locator(f'.agent-model-picker [data-setting-value="{effort}"]').click()


@pytest.mark.parametrize("width,dark", [(1280, False), (390, True)])
def test_saved_interruption_keeps_reason_and_partial_answer_visible(browser, phase4_server, width, dark):
    context, page = _real_firebase_page(browser, phase4_server)
    errors, paid = [], []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("request", lambda request: paid.append(request.url) if request.url.endswith("/agent") else None)
    try:
        page.set_viewport_size({"width": width, "height": 900})
        page.route("**/user_status", lambda r: _json(r, {"tier": "pro", "is_pro": True, "agent_access": True}))
        page.route("**/agent/models", lambda r: _json(r, CATALOG))
        page.route("**/agent/budget", lambda r: _json(r, {"token_budget": {"limit": 250000, "used": 30842, "remaining": 219158}}))
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        page.evaluate("dark => { document.documentElement.classList.toggle('dark-mode', dark); document.body.classList.toggle('dark-mode', dark); }", dark)
        reason = "The model provider stopped responding. Your available answer has been saved."
        turn = {"id": "b" * 32, "question": "Compare the available options.", "status": "failed", "error_code": "agent_failed",
            "execution_mode": "agent", "consensus": "## Available result\n\nThe independent answers identify two useful options. The review is incomplete.",
            "agent_settings": {"model_id": CATALOG["default_model_id"], "label": "DeepSeek V4.1 Flash"},
            "agent_failure": {"code": "provider_timeout", "error": reason},
            "agent_usage": {"input_tokens": 28000, "output_tokens": 2842, "complete": True}}
        bookmark = {"id": "interruption", "chat_id": "a" * 32, "mode": "Agent", "execution_mode": "agent",
            "query": turn["question"], "responses": {"consensus": turn["consensus"]}}
        page.route("**/bookmarks/interruption/conversation*", lambda r: _json(r, {"chat_id": "a" * 32, "turns": [turn], "has_more": False}))
        page.route("**/bookmarks/interruption", lambda r: _json(r, {"bookmark": bookmark}))
        page.evaluate("async () => { await window.openBookmark('interruption'); }")
        expect(page.locator("#agentAnswerError")).to_have_text(reason)
        expect(page.locator("#agentAnswerError")).to_be_visible()
        expect(page.locator("#agentAnswerBody h2")).to_have_text("Available result")
        expect(page.locator("#agentAnswerActivity summary")).to_contain_text("Response failed")
        expect(page.locator("#agentRecover")).not_to_be_visible()
        page.locator("#agentAnswerError").scroll_into_view_if_needed()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
        _snapshot(page, f"agent-saved-interruption-{width}")
        assert not paid and not errors
    finally:
        context.close()


@pytest.mark.parametrize("width", [1280, 390])
@pytest.mark.parametrize("content", ["partial", "comparison", "empty"])
def test_failed_stream_adopts_saved_bookmark_and_survives_reload(browser, phase4_server, width, content):
    context, page = _real_firebase_page(browser, phase4_server)
    errors, calls, bookmarks, turns = [], [], [], []
    chat_id = "a" * 32
    reason = "The model provider stopped responding. Your available answer has been saved."
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        page.set_viewport_size({"width": width, "height": 900})
        page.route("**/user_status", lambda r: _json(r, {"tier": "pro", "is_pro": True, "agent_access": True}))
        page.route("**/agent/models", lambda r: _json(r, CATALOG))
        page.route("**/agent/budget", lambda r: _json(r, {"token_budget": {"limit": 250000, "used": 1000, "remaining": 249000}}))
        page.route("**/chats", lambda r: _json(r, {"chat": {"id": chat_id, "execution_mode": "agent"}}))
        page.route("**/bookmarks?*", lambda r: _json(r, {"bookmarks": bookmarks, "next_cursor": None}))
        page.route("**/bookmarks/*/conversation*", lambda r: _json(r, {"chat_id": chat_id, "turns": turns, "has_more": False}))
        page.route("**/bookmarks/*", lambda r: _json(r, {"bookmark": bookmarks[0]}))

        def answer(route):
            body = route.request.post_data_json
            calls.append(body)
            turn = {"id": "b" * 32, "question": body["question"], "status": "failed", "execution_mode": "agent",
                "consensus": "## Available result\n\nThe independent answers are preserved." if content == 'partial' else '',
                "agent_settings": {"model_id": body["model_id"], "label": "DeepSeek V4.1 Flash"},
                "agent_failure": {"code": "provider_timeout", "error": reason},
                "agent_review": {"status": "failed", "comparisons": []}}
            if content == 'comparison':
                turn['agent_review']['comparisons'] = [{"id": "comparison-1", "question": "Compare options", "answers": [{
                    "provider": "openai", "provider_label": "OpenAI", "model": {"label": "GPT", "model": "gpt"},
                    "text": "Independent evidence remains available.", "sources": []}]}]
            turns.append(turn)
            bookmark = {"id": body["bookmark_id"], "chat_id": chat_id, "turn_id": turn["id"], "title": body["question"],
                "query": body["question"], "mode": "Agent", "execution_mode": "agent", "has_consensus": True,
                "responses": {"consensus": turn["consensus"]}}
            bookmarks.append(bookmark)
            failure = {"error": reason, "recoverable": True, "recovery_state": "saved",
                "saved_answer": {"chat_id": chat_id, "turn_id": turn["id"], "turn": turn,
                    "response": turn["consensus"], "bookmark_meta": bookmark}}
            route.fulfill(content_type="text/event-stream", body="event: error\ndata: " + json.dumps(failure) + "\n\n")

        page.route("**/agent", answer)
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        _choose_mode(page, "agent")
        page.locator("#questionInput").fill("Preserve this interrupted answer")
        page.locator("#sendButton").click()
        if content == 'partial':
            expect(page.locator("#agentAnswerBody h2")).to_have_text("Available result")
        else:
            expect(page.locator("#agentAnswerBody")).to_be_empty()
        expect(page.locator("#agentAnswerError")).to_have_text(reason)
        expect(page.locator("#agentRecover")).not_to_be_visible()
        page.wait_for_function("() => App.runRegistry.visible()?.bookmark.uiReady === true")
        bookmark_id = bookmarks[0]["id"]
        expect(page.locator(f'.bookmark[data-id="{bookmark_id}"]')).to_have_count(1)

        page.reload(wait_until="domcontentloaded")
        row = page.locator(f'.bookmark[data-id="{bookmark_id}"]')
        expect(row).to_have_count(1)
        if width < 1100 and page.locator("#toggleSidebarButton").get_attribute("aria-expanded") != "true":
            page.locator("#toggleSidebarButton").click()
        row.click()
        if content == 'partial':
            expect(page.locator("#agentAnswerBody h2")).to_have_text("Available result")
        else:
            expect(page.locator("#agentAnswerBody")).to_be_empty()
        expect(page.locator("#agentAnswerError")).to_have_text(reason)
        expect(page.locator("#agentRecover")).not_to_be_visible()
        if content == 'comparison':
            page.locator('.agent-evidence-link[data-section="answers"]').click()
            expect(page.locator('#modelAnswerReader')).to_contain_text('Independent evidence remains available.')
        if content == 'empty':
            turns.append({**turns[0], "id": "c" * 32, "position": 2, "status": "completed",
                          "question": "Next message", "consensus": "A later successful answer.", "agent_failure": None})
            page.reload(wait_until='domcontentloaded')
            page.evaluate("id => window.openBookmark(id)", bookmark_id)
            expect(page.locator('#threadHistory')).to_contain_text(reason)
            expect(page.locator('#agentAnswerBody')).to_contain_text('A later successful answer.')
        assert len(calls) == 1 and not errors
    finally:
        context.close()


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
        _choose_mode(page, "agent")
        assert not errors
        expect(page.locator("#agentModelDropdown")).to_be_enabled()
        expect(page.locator(".hero-greeting")).to_have_text("What can I help you with?")
        expect(page.locator(".hero-greeting")).to_be_visible()
        expect(page.locator("#viewSwitchConsensus")).to_have_text("Chat")
        expect(page.locator(".demo-chip")).not_to_be_visible()
        page.locator(".agent-model-picker .model-picker-display").click()
        expect(page.locator(".agent-model-picker .model-picker-menu")).to_be_visible()
        menu = page.locator(".agent-model-picker .model-picker-menu").bounding_box()
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
        _choose_effort(page, "medium")
        _snapshot(page, f"agent-composer-{width}-{'dark' if dark else 'light'}")
        expect(page.locator("#composerAgentToggle")).to_be_visible()
        expect(page.locator("#composerAgentToggle")).to_have_attribute("aria-disabled", "true")
        expect(page.locator("#composerAgentToggle")).to_have_attribute("aria-checked", "true")
        page.locator("#questionInput").fill("Explain the first step")
        page.locator("#sendButton").click()
        expect(page.locator("#agentAnswerBody")).to_contain_text("Explain the first step")
        page.wait_for_function("() => App.runRegistry.visible()?.status === 'succeeded'")
        expect(page.locator("#agentAnswer")).to_be_visible()
        expect(page.locator("#consensusOutput")).not_to_be_visible()
        expect(page.locator("#chatExecutionMode")).to_be_disabled()
        expect(page.locator("#agentAnswerLabel")).to_contain_text("GPT-5.6 Sol")
        assert page.locator("#threadAsk").evaluate("el => getComputedStyle(el).display") == "flex"
        expect(page.locator("#threadAsk .thread-ask-label")).to_have_count(0)
        expect(page.locator("#agentAnswerActivity .agent-activity-marker")).to_have_count(0)
        page.locator("#questionInput").fill("Now explain the next step")
        page.locator(".agent-model-picker .model-picker-display").click()
        page.locator('#agentModelControls [data-value="deepseek/deepseek-v4.1-flash"]').click()
        _choose_effort(page, "low")
        page.locator("#sendButton").click()
        page.wait_for_function("() => App.runRegistry.visible()?.status === 'succeeded' && App.runRegistry.visible().question.includes('next')")
        expect(page.locator("#threadHistory")).to_contain_text("Explain the first step")
        expect(page.locator("#threadHistory")).to_contain_text("GPT-5.6 Sol")
        expect(page.locator('#threadHistory .thread-ask-label')).to_have_count(0)
        expect(page.locator("#agentAnswerLabel")).to_contain_text("DeepSeek V4.1 Flash")
        expect(page.locator("#agentAnswerActivity")).to_contain_text("I am considering")
        expect(page.locator("#agentAnswerActivity details")).not_to_have_attribute("open", "")
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
        if width < 1100 and page.locator("#toggleSidebarButton").get_attribute("aria-expanded") == "true":
            page.locator("#sidebarToggleInner").click()
        page.locator("#agentAnswerActivity summary").click()
        expect(page.locator("#agentAnswerActivity .agent-activity-reasoning")).to_be_visible()
        expect(page.locator("#agentAnswerActivity .agent-usage")).to_contain_text("tokens")
        assert page.evaluate("App.agentChat.isSelected()")
        if width < 1100 and page.locator("#toggleSidebarButton").get_attribute("aria-expanded") != "true":
            page.locator("#toggleSidebarButton").click()
        page.locator("#newRunButton").click()
        if width < 1100 and page.locator("#toggleSidebarButton").get_attribute("aria-expanded") == "true":
            page.locator("#sidebarToggleInner").click()
        expect(page.locator("#chatExecutionMode")).to_be_enabled()
        _choose_mode(page, "consensus")
        expect(page.locator("#agentAnswer")).not_to_be_visible()
        expect(page.locator("#viewSwitchConsensus")).to_have_text("Consensus")
        assert not errors
    finally:
        context.close()


@pytest.mark.parametrize("width,dark", [(1280, False), (390, True), (320, False)])
def test_live_reasoning_disclosure_and_stop(browser, phase4_server, width, dark):
    context, page = _real_firebase_page(browser, phase4_server)
    try:
        page.set_viewport_size({"width": width, "height": 900})
        page.route("**/user_status", lambda route: _json(route, {"tier": "pro", "is_pro": True, "agent_access": True}))
        page.route("**/agent/models", lambda route: _json(route, CATALOG))
        page.route("**/chats", lambda route: _json(route, {"chat": {"id": "a" * 32}}))
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        page.evaluate("dark => { document.documentElement.classList.toggle('dark-mode', dark); document.body.classList.toggle('dark-mode', dark); }", dark)
        _choose_mode(page, "agent")
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
        expect(page.locator("#agentAnswerActivity .agent-progress")).to_be_visible()
        expect(page.locator("#agentAnswerActivity details")).not_to_have_attribute('open', '')
        expect(page.locator("#agentAnswerBody")).to_be_empty()
        expect(page.locator("#agentModelDropdown")).to_be_disabled()
        expect(page.locator(".agent-model-picker .model-picker-display")).to_be_disabled()
        title = page.locator("#agentAnswerActivity .agent-activity-title")
        assert title.evaluate("el => getComputedStyle(el).animationName") == "source-label-shine"
        page.evaluate("""() => window.__emitAgent({version:1, step_id:'completion:0', kind:'reasoning', id:'r1',
          format:'summary', text:'I am considering compare_models to check independent perspectives, then judge_answer.'})""")
        expect(page.locator('.agent-progress .agent-tool-mention')).to_have_count(0)
        expect(page.locator('.agent-progress')).to_contain_text('compare_models')
        expect(page.locator('.agent-progress-action')).to_have_count(0)
        _snapshot(page, f"agent-tool-mentioned-{width}-{'dark' if dark else 'light'}")
        page.locator('#agentAnswerActivity summary').click()
        expect(page.locator('#agentAnswerActivity .agent-activity-reasoning')).to_be_visible()
        if width == 1280:
            expect(page.locator(".run-entry-status")).to_have_text("Thinking")
            expect(page.locator("#newRunButton")).to_have_text("New chat")
        page.locator('#agentAnswerActivity summary').click()
        page.evaluate("() => window.__emitAgent({version:1, step_id:'completion:0', kind:'tool', id:'tool1', name:'compare_models', status:'running'})")
        expect(title).to_have_text('Comparing perspectives…')
        expect(title).to_be_visible()
        expect(page.locator('.agent-progress-action')).to_have_count(0)
        expect(page.locator('.agent-progress')).not_to_contain_text('Comparing perspectives')
        _snapshot(page, f"agent-tool-active-{width}-{'dark' if dark else 'light'}")
        page.evaluate("() => window.__emitAgent({version:1, step_id:'completion:0', kind:'tool', id:'tool1', name:'compare_models', status:'succeeded'})")
        page.locator('#agentAnswerActivity summary').click()
        # Long legacy traces become short highlights, not a scrolling wall.
        page.evaluate("""() => window.__emitAgent({version:1, step_id:'completion:0', kind:'reasoning', id:'r2',
          format:'text', text:'A measured reasoning step.\\n'.repeat(100), append:true})""")
        content = page.locator("#agentAnswerActivity .agent-activity-content")
        expect(content).to_contain_text("A measured reasoning step.")
        assert len(content.inner_text()) < 600
        # Give the disclosure more than the 40px follow tolerance; scrolling
        # to the top of a nearly fitting trace still counts as reading along.
        page.evaluate("""() => { for (let i = 3; i < 7; i++) window.__emitAgent({version:1, step_id:'completion:' + i,
          kind:'reasoning', id:'r' + i, format:'summary', text:'Comparing the supporting evidence.\\nChecking whether sources agree.\\nIdentifying remaining uncertainty.'}); }""")
        expect(content).to_contain_text('Identifying remaining uncertainty.')
        assert content.evaluate('el => el.scrollHeight - el.clientHeight') > 40
        content.evaluate("el => { el.scrollTop = 0; }")
        page.evaluate("""() => window.__emitAgent({version:1, step_id:'completion:0', kind:'reasoning', id:'r2',
          format:'text', text:'End of reasoning.', append:true})""")
        expect(content).to_contain_text("End of reasoning.")
        assert content.evaluate("el => el.scrollTop") == 0
        page.emulate_media(reduced_motion="reduce")
        assert title.evaluate("el => getComputedStyle(el).animationName") == "none"
        page.locator("#agentAnswerActivity summary").click()
        page.evaluate("() => window.__emitAgent({version:1, step_id:'completion:0', kind:'reasoning', id:'r1', format:'summary', text:' Still checking.', append:true})")
        expect(page.locator("#agentAnswerActivity details")).not_to_have_attribute("open", "")
        # The send button's existing duplicate-gesture guard elapses naturally
        # while opening and closing the disclosure.
        page.wait_for_function("() => Date.now() - App.runRegistry.visible().startedAt > 800")
        page.locator("#sendButton").click()
        page.wait_for_function("() => App.runRegistry.visible()?.status === 'canceled'")
        expect(page.locator("#agentAnswerActivity .agent-activity-title")).to_have_text("Response stopped")
        expect(page.locator("#agentAnswerError")).not_to_be_visible()
        assert title.evaluate("el => getComputedStyle(el).animationName") == "none"
    finally:
        context.close()


def test_small_viewport_long_model_and_missing_reasoning(browser, phase4_server):
    context, page = _real_firebase_page(browser, phase4_server)
    try:
        page.set_viewport_size({"width": 320, "height": 568})
        page.route("**/user_status", lambda route: _json(route, {"tier": "pro", "is_pro": True, "agent_access": True}))
        # Enough options to require an internally scrolling picker.
        catalog = {**CATALOG, "models": CATALOG["models"] + [
            {**CATALOG["models"][0], "id": f"extra-{i}", "label": f"Additional model {i}"} for i in range(30)]}
        page.route("**/agent/models", lambda route: _json(route, catalog))
        page.route("**/chats", lambda route: _json(route, {"chat": {"id": "a" * 32}}))
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        _choose_mode(page, "agent")
        expect(page.locator("#agentModelDropdown")).to_be_enabled()
        trigger = page.locator(".agent-model-picker .model-picker-display")
        trigger.click()
        menu = page.locator(".agent-model-picker .model-picker-menu")
        bounds = menu.bounding_box()
        assert bounds["y"] >= 0 and bounds["y"] + bounds["height"] <= 568
        assert menu.evaluate("el => el.scrollHeight > el.clientHeight")
        page.locator('.agent-model-picker [data-value="long"]').click()
        expect(trigger).to_have_attribute("title", "A model with a particularly long display name")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        _choose_effort(page, "high")
        _snapshot(page, "agent-long-name-320")
        trigger.click()
        page.locator('.agent-model-picker [data-value="plain"]').click()
        expect(page.locator(".agent-effort-control")).not_to_be_visible()
        page.route("**/agent", lambda route: _json(route, {
            "response": "A concise answer.", "chat_id": "a" * 32, "turn_id": "b" * 32,
            "turn": {"id": "b" * 32, "execution_mode": "agent", "status": "completed", "consensus": "A concise answer.",
                "agent_settings": {"label": "Model without reasoning", "model_id": "plain"},
                "agent_activity": [], "agent_usage": None, "agent_finish_reason": "length"}}))
        page.locator("#questionInput").fill("A simple question")
        page.locator("#sendButton").click()
        expect(page.locator("#agentAnswerBody")).to_have_text("A concise answer.")
        expect(page.locator("#agentAnswerActivity .agent-activity-title")).to_have_text("Response limit reached")
        page.locator("#agentAnswerActivity summary").click()
        expect(page.locator(".agent-activity-note")).to_contain_text("No visible reasoning")
        expect(page.locator(".agent-activity-note")).to_contain_text("output limit")
        expect(page.locator(".agent-usage")).to_have_text("Usage unavailable")
        _snapshot(page, "agent-no-reasoning-320")
    finally:
        context.close()


def test_model_catalog_retry_and_failed_stream(browser, phase4_server):
    context, page = _real_firebase_page(browser, phase4_server)
    try:
        page.set_viewport_size({"width": 390, "height": 844})
        page.route("**/user_status", lambda route: _json(route, {"tier": "pro", "is_pro": True, "agent_access": True}))
        attempts = []
        def models(route):
            attempts.append(True)
            if len(attempts) == 1:
                route.fulfill(status=503, content_type="application/json", body='{"detail":"Unavailable"}')
            else:
                _json(route, CATALOG)
        page.route("**/agent/models", models)
        page.route('**/agent/budget', lambda route: _json(route, {'token_budget': {'remaining': 250000, 'limit': 250000}}))
        page.route("**/chats", lambda route: _json(route, {"chat": {"id": "a" * 32}}))
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        _choose_mode(page, "agent")
        expect(page.locator("#agentModelsRetry")).to_be_visible()
        expect(page.locator(".agent-model-picker .model-picker-display")).to_be_disabled()
        page.locator("#agentModelsRetry").click()
        expect(page.locator(".agent-model-picker .model-picker-display")).to_be_enabled()
        calls = []
        def agent_response(route):
            request = route.request.post_data_json
            calls.append(request)
            if not request["recover_only"]:
                route.fulfill(content_type="text/event-stream",
                    body='event: error\ndata: {"error":"The model is temporarily unavailable."}\n\n')
            else:
                _json(route, {"response": "Recovered saved answer.", "chat_id": "a" * 32, "turn_id": "b" * 32,
                    "turn": {"id": "b" * 32, "status": "completed", "execution_mode": "agent", "consensus": "Recovered saved answer."}})
        page.route("**/agent", agent_response)
        page.locator("#questionInput").fill("A question")
        page.locator("#sendButton").click()
        expect(page.locator("#agentAnswerError")).to_have_text("The model is temporarily unavailable.")
        expect(page.locator("#agentRecover")).to_be_visible()
        expect(page.locator("#agentAnswerActivity .agent-activity-title")).to_have_text("Response failed")
        assert page.locator(".agent-activity-title").evaluate("el => getComputedStyle(el).animationName") == "none"
        page.wait_for_function("() => !App.runRegistry.visible()?.controllers.query")
        assert len(attempts) == 2
        _snapshot(page, "agent-error-390")
        page.locator("#agentRecover").click()
        expect(page.locator("#agentAnswerBody")).to_have_text("Recovered saved answer.")
        expect(page.locator("#agentAnswerError")).not_to_be_visible()
        expect(page.locator("#agentRecover")).not_to_be_visible()
        assert page.evaluate('App.runRegistry.list().length') == 1
        assert len(calls) == 2
        assert calls[1]["recover_only"] is True
        for key in ("client_request_id", "chat_id", "model_id", "reasoning_effort"):
            assert calls[1][key] == calls[0][key]
    finally:
        context.close()


@pytest.mark.parametrize('width', [1280, 390])
def test_quota_stream_and_failure_update_existing_percentage(browser, phase4_server, width):
    context, page = _real_firebase_page(browser, phase4_server)
    try:
        page.set_viewport_size({'width': width, 'height': 900})
        page.route('**/user_status', lambda r: _json(r, {'tier': 'pro', 'is_pro': True, 'agent_access': True}))
        page.route('**/agent/models', lambda r: _json(r, {**CATALOG, 'token_budget': {'remaining': 188878, 'limit': 250000, 'observed_at': 1}}))
        page.route('**/chats', lambda r: _json(r, {'chat': {'id': 'a' * 32}}))
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        _choose_mode(page, 'agent')
        expect(page.locator('#quotaTriggerValue')).to_have_text('75%')
        page.evaluate("""() => {
          const original = window.fetch;
          window.fetch = async (url, options) => {
            if (url !== '/agent') return original(url, options);
            const encoder = new TextEncoder();
            return new Response(new ReadableStream({start(controller) {
              window.__quotaEvent = (type, data) => controller.enqueue(encoder.encode('event: ' + type + '\\ndata: ' + JSON.stringify(data) + '\\n\\n'));
              window.__quotaEvent('quota', {token_budget:{used:61122, remaining:88878, reserved:100000, limit:250000, observed_at:2}});
            }}), {headers:{'Content-Type':'text/event-stream'}});
          };
        }""")
        page.locator('#questionInput').fill('Compare the options')
        page.locator('#sendButton').click()
        expect(page.locator('#quotaTriggerValue')).to_have_text('75%')
        page.evaluate("""() => window.__quotaEvent('error', {
          error:'The next model call needed a reservation of 50,000 tokens; 40,000 were available at that point. Completed calls release their reservations.',
          code:'agent_token_reservation', recoverable:false, token_budget:{used:61122, remaining:188878, reserved:0, unknown:100000, limit:250000, observed_at:3}})""")
        expect(page.locator('#agentAnswerError')).to_contain_text('Completed calls release their reservations')
        expect(page.locator('#quotaTriggerValue')).to_have_text('75%')
        expect(page.locator('#quotaTrigger')).to_have_attribute('title', re.compile('188.878 tokens available for new calls'))
        expect(page.locator('#quotaFoot')).to_contain_text('unavailable usage; they do not block the remaining allowance')
        expect(page.locator('#agentRecover')).to_be_hidden()
        expect(page.locator('.run-status-failed')).to_have_count(1)
        expect(page.locator('.thread-ask-label')).to_have_count(0)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        _snapshot(page, f'agent-budget-failure-{width}')
    finally:
        context.close()


def test_shared_consensus_picker_still_navigates_submenus(browser, phase4_server):
    context, page = _real_firebase_page(browser, phase4_server)
    try:
        page.route("**/user_status", lambda route: _json(route, {"tier": "pro", "is_pro": True, "agent_access": True}))
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        picker = page.locator(".consensus-model-inline")
        picker.locator(".model-picker-display").click()
        picker.locator(".model-picker-custom-option").click()
        picker.locator(".model-picker-row-open").filter(has_text="Writes the consensus").click()
        menu = picker.locator(".model-picker-menu")
        expect(menu).to_be_visible()
        option = menu.locator("[data-value]:not(:disabled)").last
        selected = option.get_attribute("data-value")
        option.click()
        expect(page.locator("#consensusModelDropdown")).to_have_value(selected)
        expect(menu).not_to_be_visible()
        assert page.evaluate("() => localStorage.getItem('pref_consensus_preset')") == "custom"
        picker.locator(".model-picker-display").click()
        expect(menu).to_be_visible()
        page.keyboard.press("Escape")
        expect(menu).not_to_be_visible()
    finally:
        context.close()


@pytest.mark.parametrize("width,dark", [(1280, False), (390, True), (320, False)])
def test_native_search_sources_in_chat_and_saved_activity(browser, phase4_server, width, dark):
    context, page = _real_firebase_page(browser, phase4_server)
    try:
        page.set_viewport_size({"width": width, "height": 900})
        page.route("**/user_status", lambda route: _json(route, {"tier": "pro", "is_pro": True, "agent_access": True}))
        page.route("**/agent/models", lambda route: _json(route, CATALOG))
        page.route("**/chats", lambda route: _json(route, {"chat": {"id": "a" * 32}}))
        activity = [{"version": 1, "step_id": "completion:0:web_search", "id": "completion:0:web_search/tool",
                     "kind": "tool", "name": "web_search", "status": "succeeded", "count": 2, "provider_native": True,
                     "sources": [{"url": "https://example.com/report", "title": "Research report with a long descriptive source title"},
                                 {"url": "https://example.org/analysis", "title": "Analysis and methodology"}]}]
        turn = {"id": "b" * 32, "status": "completed", "execution_mode": "agent", "question": "Research the topic",
                "consensus": "The current sources support this answer.", "agent_activity": activity,
                "agent_settings": {"model_id": "claude-haiku-4-5", "label": "Claude Haiku 4.5", "reasoning_effort": "default"},
                "agent_usage": {"input_tokens": 1200, "output_tokens": 200, "estimated_cost_nano_usd": 22200000, "complete": True}}
        def respond(route):
            assert route.request.post_data_json["model_id"] == "claude-haiku-4-5"
            final = {"response": turn["consensus"], "chat_id": "a" * 32, "turn_id": turn["id"], "turn": turn}
            body = "event: activity\ndata: " + json.dumps(activity[0]) + "\n\n"
            body += "event: final\ndata: " + json.dumps(final) + "\n\n"
            route.fulfill(content_type="text/event-stream", body=body)
        page.route("**/agent", respond)
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        page.evaluate("dark => { document.documentElement.classList.toggle('dark-mode', dark); document.body.classList.toggle('dark-mode', dark); }", dark)
        _choose_mode(page, "agent")
        page.locator(".agent-model-picker .model-picker-display").click()
        page.locator('#agentModelControls [data-value="claude-haiku-4-5"]').click()
        expect(page.locator("#agentModelDropdown")).to_have_value("claude-haiku-4-5")
        expect(page.locator("#agentModelNotice")).to_have_count(0)
        page.locator("#questionInput").fill(turn["question"])
        expect(page.locator("#agentModelDropdown")).to_have_value("claude-haiku-4-5")
        page.locator("#sendButton").click()
        page.wait_for_function("() => App.runRegistry.visible()?.status === 'succeeded'")
        details = page.locator("#agentAnswerActivity details")
        expect(details.locator("summary")).to_have_text("Activity and sources")
        details.locator("summary").click()
        expect(details.locator(".agent-activity-tool")).to_contain_text("Web search · Completed · 2 searches")
        expect(details.locator("a")).to_have_count(2)
        expect(details.locator("a").first).to_have_attribute("rel", "noopener noreferrer")
        details.scroll_into_view_if_needed()
        assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1")
        box = details.bounding_box()
        assert box["x"] >= 0 and box["x"] + box["width"] <= width
        _snapshot(page, f"agent-native-search-{width}-{'dark' if dark else 'light'}")
        sources = page.locator('.agent-evidence-link[data-section="sources"]')
        expect(sources).to_have_text('Sources 2')
        sources.click()
        expect(page.locator('#answerReaderInspector a')).to_have_count(2)
        expect(page.locator('#answerReaderSections [data-section="answers"]')).not_to_be_visible()
        expect(page.locator('#answerReaderSections [data-section="differences"]')).not_to_be_visible()
        page.keyboard.press('Escape')
        expect(sources).to_be_focused()
        # The shared history renderer receives the same authoritative activity.
        page.evaluate("turn => { App.agentActivity.renderTurn(document.getElementById('agentAnswerActivity'), turn); }", turn)
        expect(details.locator("a")).to_have_count(2)
        expected_tokens = page.evaluate("() => (1400).toLocaleString() + ' tokens'")
        expect(details.locator(".agent-usage")).to_contain_text(expected_tokens)
    finally:
        context.close()


@pytest.mark.parametrize("width", [1280, 320])
def test_removed_preference_and_legacy_phantom_search(browser, phase4_server, width):
    context, page = _real_firebase_page(browser, phase4_server)
    try:
        page.set_viewport_size({"width": width, "height": 900})
        page.route("**/user_status", lambda route: _json(route, {"tier": "pro", "is_pro": True, "agent_access": True}))
        page.route("**/agent/models", lambda route: _json(route, CATALOG))
        page.route("**/chats", lambda route: _json(route, {"chat": {"id": "a" * 32}}))
        turn = {"id": "b" * 32, "status": "completed", "execution_mode": "agent", "question": "was geht ab",
                "consensus": "Hey! Wie kann ich dir helfen?",
                "agent_settings": {"model_id": CATALOG["default_model_id"], "label": "DeepSeek V4.1 Flash", "reasoning_effort": "default"},
                "agent_activity": [
                    {"version": 1, "id": "r1", "kind": "reasoning", "format": "text", "text": "A casual greeting. No tool needed."},
                    {"version": 1, "id": "s1", "kind": "tool", "name": "web_search", "status": "unknown", "server_tool": True}],
                "agent_usage": {"input_tokens": 800, "output_tokens": 62, "estimated_cost_nano_usd": 400000, "cost_source": "provider", "complete": True}}
        def respond(route):
            assert route.request.post_data_json["model_id"] == CATALOG["default_model_id"]
            final = {"response": turn["consensus"], "chat_id": "a" * 32, "turn_id": turn["id"], "turn": turn}
            route.fulfill(content_type="text/event-stream", body="event: final\ndata: " + json.dumps(final) + "\n\n")
        page.route("**/agent", respond)
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        page.evaluate("() => localStorage.setItem(`agent_settings_${auth.currentUser.uid}`, JSON.stringify({model_id:'removed-model',reasoning_effort:'ultra'}))")
        _choose_mode(page, "agent")
        expect(page.locator("#agentModelDropdown")).to_have_value(CATALOG["default_model_id"])
        page.evaluate("() => { App.agentChat.render(); App.agentChat.render(); }")
        assert page.evaluate("() => JSON.parse(localStorage.getItem(`agent_settings_${auth.currentUser.uid}`)).model_id") == CATALOG["default_model_id"]
        expect(page.locator(".explanation-popup")).to_have_count(1)
        expect(page.locator("#agentModelNotice")).to_have_count(0)
        label = page.locator(".agent-model-picker .model-picker-display-text")
        expect(label).to_have_text("DeepSeek V4.1 Flash")
        assert label.evaluate("el => el.clientWidth > 0 && el.scrollWidth <= el.clientWidth + 1")
        assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1")
        expect(page.locator(".explanation-popup")).to_have_count(0)
        _snapshot(page, f"agent-repaired-selection-{width}")
        page.locator("#questionInput").fill(turn["question"])
        page.locator("#sendButton").click()
        expect(page.locator("#agentAnswerBody")).to_have_text(turn["consensus"])
        details = page.locator("#agentAnswerActivity details")
        expect(details.locator("summary")).to_have_text("Reasoning")
        details.locator("summary").click()
        expect(details.locator(".agent-activity-reasoning")).to_have_text("A casual greeting.")
        expect(details.locator(".agent-activity-tool")).to_have_count(0)
        expect(details.locator(".agent-usage")).to_have_text("862 tokens · $0.0004 provider cost")
        _snapshot(page, f"agent-greeting-without-search-{width}")
    finally:
        context.close()
