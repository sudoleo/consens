"""Built Agent comparison controls, markers and saved projection without providers."""
import hashlib
import json

import pytest
from playwright.sync_api import expect
from test_phase4_frontend import phase4_server, _real_firebase_page, _json
from test_agent_chat_frontend import CATALOG, _choose_mode, _snapshot


@pytest.mark.parametrize("width,dark", [(1440, False), (390, True), (320, False)])
def test_comparison_review_and_saved_projection(browser, phase4_server, width, dark):
    context, page = _real_firebase_page(browser, phase4_server)
    chat, turn = "a" * 32, "b" * 32
    anchor = "The smaller plan includes five seats."
    text = "For a team of five, start with the **smaller plan**.\n\n" + anchor + "\n\nConfirm the seat limit before purchasing: the model answers disagree on this detail.\n\nSee the [billing terms](https://example.org/billing)."
    digest = hashlib.sha256(text.encode()).hexdigest()
    models = [("openai", "OpenAI", "openai/gpt-5.4-mini", "GPT-5.4 Mini"),
              ("deepseek", "DeepSeek", "deepseek/deepseek-v4-flash", "DeepSeek V4 Flash"),
              ("gemini", "Gemini", "google/gemini-3.5-flash-lite", "Gemini 3.5 Flash-Lite"),
              ("kimi", "Kimi", "moonshotai/kimi-k2.6", "Kimi K2.6"),
              ("glm", "GLM", "z-ai/glm-5.3-flash", "GLM 5.3 Flash"),
              ("meta", "Meta", "meta/muse-glimmer-30b", "Muse Glimmer 30B")]
    answers = [{"provider": p, "provider_label": label, "model": {"model": model, "label": name},
        "text": "### Recommendation\n\nChoose the **smaller plan**.\n\n- Monthly billing\n- Confirm the seat limit\n\n[Plan details](https://example.org/pricing)", "sources": []} for p, label, model, name in models]
    activity = [{"version": 1, "id": "search", "kind": "tool", "name": "web_search", "status": "succeeded",
                 "sources": [{"url": "https://example.org/pricing", "title": "Plan details"}]}]
    agents = [{"id": f"{i + 10:032x}", "seq": i + 1, "status": "completed", "kind": "comparison", "title": a["model"]["label"], "model": a["model"], "duration_ms": 3100,
               "progress_text": "Checking seat limits and monthly billing.", "progress_kind": "excerpt"} for i, a in enumerate(answers)]
    review = {"status": "succeeded", "answer_version": 1, "answer_hash": digest,
        "versions": [{"id": 1, "text": text, "hash": digest, "status": "succeeded"}],
        "comparisons": [{"id": "c1", "basis_hash": "basis", "question": "Which plan suits a team of five?", "reason": "Compare cost and flexibility",
            "context": "The team needs monthly billing.", "status": "succeeded", "answers": answers}],
        "checks": [{"comparison_id": "c1", "basis_hash": "basis", "answer_hash": digest, "status": "succeeded",
            "differences_data": {"claims": [], "differences": [{"claim": "Whether the smaller plan includes five seats", "consensus_anchor": anchor, "type": "contradiction", "severity": "major", "positions": [
                {"models": ["OpenAI"], "stance": "Five seats are included.", "quote": "Choose the smaller plan."},
                {"models": ["DeepSeek"], "stance": "The seat limit needs confirmation.", "quote": "Confirm the seat limit"}]}], "models_compared": [m[1] for m in models]}}]}
    saved = {"id": turn, "question": "Compare plans for our team", "status": "completed", "execution_mode": "agent", "mode": "Agent",
        "consensus": text, "sources": [], "model_answers": {}, "agent_review": review, "agent_activity": activity,
        "agent_settings": {"model_id": "claude-haiku-4-5", "label": "Claude Haiku 4.5", "policy": {"delegation": True}}}
    requests, errors = [], []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        page.set_viewport_size({"width": width, "height": 960})
        page.route("**/user_status", lambda r: _json(r, {"tier": "pro", "is_pro": True, "agent_access": True, "limit": 500}))
        page.route("**/usage", lambda r: _json(r, {"tier": "pro", "is_pro": True, "remaining": 0, "total_limit": 500}))
        page.route("**/api/my/memory", lambda r: _json(r, {"memory": {"content": "", "revision": 0}}))
        page.route("**/chats", lambda r: _json(r, {"chat": {"id": chat, "execution_mode": "agent"}}))
        page.route("**/agent/models", lambda r: _json(r, {**CATALOG, "token_budget": {"remaining": 188878, "limit": 250000}}))
        page.route(f"**/agent/chats/{chat}/turns/{turn}/agents", lambda r: _json(r, {"agents": agents, "status": "succeeded"}))
        page.route(f"**/agent/chats/{chat}/turns/{turn}/agents/*", lambda r: _json(r, {"agent": {"assignment": {"goal": "Compare plans"}}, "messages": [], "has_more": False}))
        def respond(route):
            body = route.request.post_data_json
            requests.append(body)
            final = {"chat_id": chat, "turn_id": turn, "response": text, "turn": saved, "token_budget": {"remaining": 140057, "limit": 250000},
                     "bookmark_meta": {"id": body["bookmark_id"], "title": saved["question"], "query": saved["question"], "mode": "Agent", "has_consensus": True}}
            events = [("started", {"chat_id": chat, "turn_id": turn, "delegation": True})]
            events += [('activity', e) for e in activity]
            events += [("delegation", {"version": 1, "chat_id": chat, "turn_id": turn, "agent": a}) for a in agents]
            events += [("delta", {"text": text}), ("review", {"review": review}), ("final", final)]
            route.fulfill(content_type="text/event-stream", body="".join(f"event: {name}\ndata: {json.dumps(data)}\n\n" for name, data in events))
        page.route("**/agent", respond)
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        _choose_mode(page, "agent")
        page.evaluate("dark => { document.documentElement.classList.toggle('dark-mode', dark); document.body.classList.toggle('dark-mode', dark); }", dark)
        expect(page.locator("#quotaTriggerValue")).to_have_text("75%")
        expect(page.locator("#agentTokenBudget")).to_have_count(0)
        def assert_composer_layout():
            input_box = page.locator("#questionInput").bounding_box()
            composer = page.locator(".chat-input-container").bounding_box()
            assert input_box["width"] >= min(210, composer["width"] * .7)
            assert input_box["height"] <= 80
            if page.locator("#agentModelControls").is_visible():
                label = page.locator(".agent-model-picker .model-picker-display-text").bounding_box()
                assert label["width"] >= 90
        picker = page.locator(".consensus-model-inline .model-picker-display")
        expect(picker).to_contain_text("Compare")
        picker.click()
        page.locator(".consensus-model-inline .model-picker-custom-option").click()
        expect(page.locator(".consensus-model-inline .model-picker-menu")).not_to_contain_text("Consensus engine")
        page.keyboard.press("Escape")
        assert_composer_layout()
        _snapshot(page, f"comparison-composer-{width}")
        page.locator("#questionInput").fill(saved["question"])
        page.locator("#sendButton").click()
        expect(page.locator(".agent-review-status")).to_have_text("Comparison checked")
        expect(page.locator('#quotaTriggerValue')).to_have_text('56%')
        expect(page.locator('.agent-evidence-link[data-section="sources"]')).to_have_text('Sources2')
        expect(page.locator('#chatExecutionControl')).not_to_be_visible()
        expect(page.locator('.agent-effort-control')).not_to_be_visible()
        expect(page.locator("#agentAnswerBody .cx-claim")).to_have_count(1)
        assert len(requests[0]["comparison_models"]) >= 2
        expect(page.locator('.agent-inline-model')).to_have_count(6)
        icons = page.locator('.agent-model-stack img').evaluate_all('(els) => els.map(e => e.getAttribute("src"))')
        page.wait_for_function("() => [...document.querySelectorAll('.agent-model-stack img')].every(img => img.complete && img.naturalWidth > 0)")
        assert page.locator('.agent-model-stack img').first.bounding_box()['width'] <= 15
        assert any('kimi.svg' in src for src in icons)
        assert any('zai.svg' in src for src in icons)
        assert any('meta.svg' in src for src in icons)
        page.locator('.agent-sidebar-close').click()
        page.mouse.move(0, 0)
        expect(page.locator('.agent-basis-select, .agent-comparison-response')).to_have_count(0)
        _snapshot(page, f"comparison-review-{width}")
        marker = page.locator('#agentAnswerBody .cx-claim[role="button"]').first
        marker.focus()
        page.keyboard.press("Enter")
        expect(page.locator('#modelAnswerReader')).to_be_visible()
        expect(page.locator('#answerReaderInspector .diff-card')).to_have_count(1)
        expect(page.locator('#answerReaderInspector .diff-card')).to_have_attribute('open', '')
        expect(page.locator('#agentSidebar')).not_to_be_visible()
        page.locator('.answer-reader-dialog').evaluate("async el => { await Promise.all(el.getAnimations().map(a => a.finished.catch(() => {}))); }")
        if width >= 1400:
            panel_box = page.locator('.answer-reader-dialog').bounding_box()
            answer_box = page.locator('#agentAnswerBody').bounding_box()
            input_box = page.locator('.input-section').bounding_box()
            assert answer_box['x'] + answer_box['width'] <= panel_box['x'], (answer_box, panel_box)
            assert input_box['x'] + input_box['width'] <= panel_box['x'], (input_box, panel_box)
        _snapshot(page, f"comparison-contradictions-{width}")
        page.locator('#answerReaderInspector .diff-jump-link').first.click()
        expect(page.locator('#answerReaderColumns h3').last).to_have_text('Recommendation')
        expect(page.locator('#answerReaderColumns strong').first).to_have_text('smaller plan')
        _snapshot(page, f"comparison-answer-{width}")
        page.locator('#answerReaderSections [data-section="sources"]').click()
        expect(page.locator('#answerReaderInspector a[href="https://example.org/pricing"]')).to_be_visible()
        page.keyboard.press('Escape')
        expect(page.locator('#modelAnswerReader')).not_to_be_visible()
        expect(marker).to_be_focused()
        page.locator('.agent-evidence-link[data-section="differences"]').click()
        expect(page.locator('#answerReaderInspector')).to_contain_text('Whether the smaller plan includes five seats')
        page.keyboard.press('Escape')
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert_composer_layout()
        page.evaluate("data => window.App.runRegistry.showSavedView({type:'bookmark'}, data)", {
            "chatId": chat, "turnId": turn, "executionMode": "agent", "question": saved["question"], "consensus": text, "currentTurn": saved})
        expect(page.locator(".agent-review-status")).to_have_text("Comparison checked")
        expect(page.locator("#agentAnswerBody .cx-claim")).to_have_count(1)
        page.locator('.agent-evidence-link[data-section="answers"]').click()
        expect(page.locator('#answerReaderColumns')).to_contain_text('Recommendation')
        page.keyboard.press('Escape')
        page.evaluate('turn => window.App.followup.renderStoredTurns([turn])', saved)
        history = page.locator('.thread-history-turn')
        expect(history.locator('.agent-history-models img')).to_have_count(6)
        history.locator('.agent-history-models button').last.click()
        expect(page.locator('#answerReaderColumns')).to_contain_text('Recommendation')
        expect(page.locator('#answerReaderModel')).to_have_value('Meta')
        page.evaluate("async () => { await window.__switchE2EUser('account-b'); }")
        expect(page.locator('#modelAnswerReader')).not_to_be_visible()
        assert not errors
    finally:
        context.close()
