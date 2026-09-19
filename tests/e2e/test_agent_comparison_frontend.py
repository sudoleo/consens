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
    text = "Choose the smaller plan for a team of five."
    digest = hashlib.sha256(text.encode()).hexdigest()
    review = {"status": "succeeded", "answer_version": 1, "answer_hash": digest,
        "versions": [{"id": 1, "text": text, "hash": digest, "status": "succeeded"}],
        "comparisons": [{"id": "c1", "basis_hash": "basis", "question": "Which plan suits a team of five?", "reason": "Compare cost and flexibility",
            "context": "The team needs monthly billing.", "status": "succeeded", "answers": [
                {"provider": "openai", "model": {"label": "GPT-5.4 Mini"}, "text": "The smaller plan covers five people.", "sources": []},
                {"provider": "anthropic", "model": {"label": "Claude Haiku 4.5"}, "text": "Confirm seat limits before choosing.", "sources": []}]}],
        "checks": [{"comparison_id": "c1", "basis_hash": "basis", "answer_hash": digest, "status": "succeeded",
            "differences_data": {"claims": [{"anchor": text, "agree": ["OpenAI"], "dissent": [], "coverage": "thin", "sentence_id": "s1"}],
                "differences": [], "models_compared": ["OpenAI", "Anthropic"]}}]}
    saved = {"id": turn, "question": "Compare plans for our team", "status": "completed", "execution_mode": "agent", "mode": "Agent",
        "consensus": text, "sources": [], "model_answers": {}, "agent_review": review,
        "agent_settings": {"model_id": "claude-haiku-4-5", "label": "Claude Haiku 4.5"}}
    requests, errors = [], []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        page.set_viewport_size({"width": width, "height": 960})
        page.route("**/user_status", lambda r: _json(r, {"tier": "pro", "is_pro": True, "agent_access": True, "limit": 500}))
        page.route("**/usage", lambda r: _json(r, {"tier": "pro", "is_pro": True, "remaining": 0, "total_limit": 500}))
        page.route("**/api/my/memory", lambda r: _json(r, {"memory": {"content": "", "revision": 0}}))
        page.route("**/chats", lambda r: _json(r, {"chat": {"id": chat, "execution_mode": "agent"}}))
        page.route("**/agent/models", lambda r: _json(r, {**CATALOG, "token_budget": {"remaining": 250000, "limit": 250000}}))
        def respond(route):
            body = route.request.post_data_json
            requests.append(body)
            final = {"chat_id": chat, "turn_id": turn, "response": text, "turn": saved,
                     "bookmark_meta": {"id": body["bookmark_id"], "title": saved["question"], "query": saved["question"], "mode": "Agent", "has_consensus": True}}
            events = [("delta", {"text": text}), ("review", {"review": review}), ("final", final)]
            route.fulfill(content_type="text/event-stream", body="".join(f"event: {name}\ndata: {json.dumps(data)}\n\n" for name, data in events))
        page.route("**/agent", respond)
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        _choose_mode(page, "agent")
        page.evaluate("dark => { document.documentElement.classList.toggle('dark-mode', dark); document.body.classList.toggle('dark-mode', dark); }", dark)
        expect(page.locator("#agentTokenBudget")).to_contain_text("tokens left today")
        def assert_composer_layout():
            input_box = page.locator("#questionInput").bounding_box()
            composer = page.locator(".chat-input-container").bounding_box()
            assert input_box["width"] >= min(210, composer["width"] * .7)
            assert input_box["height"] <= 80
            if page.locator("#agentModelControls").is_visible():
                label = page.locator(".agent-model-picker .model-picker-display-text").bounding_box()
                assert label["width"] >= 90
                quota = page.locator("#agentTokenBudget").bounding_box()
                assert quota["height"] <= 24
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
        expect(page.locator(".agent-review-status")).to_have_text("Review complete · Version 1")
        expect(page.locator("#agentAnswerBody .cx-claim")).to_have_count(1)
        assert len(requests[0]["comparison_models"]) >= 2
        page.locator(".agent-comparison > summary").click()
        page.locator(".agent-comparison-response > summary").first.focus()
        page.keyboard.press("Enter")
        expect(page.locator(".agent-comparison-answer").first).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert_composer_layout()
        _snapshot(page, f"comparison-review-{width}")
        page.evaluate("data => window.App.runRegistry.showSavedView({type:'bookmark'}, data)", {
            "chatId": chat, "turnId": turn, "executionMode": "agent", "question": saved["question"], "consensus": text, "currentTurn": saved})
        expect(page.locator(".agent-review-status")).to_have_text("Review complete · Version 1")
        expect(page.locator("#agentAnswerBody .cx-claim")).to_have_count(1)
        assert not errors
    finally:
        context.close()
