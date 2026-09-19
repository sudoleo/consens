"""Built Agent comparison controls, markers and saved projection without providers."""
import hashlib
import json

import pytest
from playwright.sync_api import expect
from test_phase4_frontend import phase4_server, _real_firebase_page, _json
from test_agent_chat_frontend import CATALOG, _choose_mode, _snapshot


@pytest.mark.parametrize("width", [390, 320])
def test_mobile_agent_toolbar_taps_open_pickers_from_collapsed_composer(browser, phase4_server, width):
    context, page = _real_firebase_page(browser, phase4_server, has_touch=True)
    turn = {"id": "b" * 32, "execution_mode": "agent", "status": "completed", "question": "Compare plans",
            "consensus": "A saved answer.", "agent_settings": {"model_id": CATALOG["default_model_id"]}}
    try:
        page.set_viewport_size({"width": width, "height": 844})
        page.route('**/user_status', lambda r: _json(r, {"tier": "pro", "is_pro": True, "agent_access": True}))
        page.route('**/agent/models', lambda r: _json(r, CATALOG))
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        _choose_mode(page, 'agent')
        page.evaluate("turn => App.runRegistry.showSavedView({type:'bookmark'}, {chatId:'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', turnId:turn.id, executionMode:'agent', question:turn.question, consensus:turn.consensus, currentTurn:turn})", turn)
        page.evaluate('() => { window.exitHeroMode(); App.composer.collapse({force:true}); }')
        page.wait_for_function("() => !document.body.classList.contains('composer-animating')")
        expect(page.locator('#composerModeBar')).to_be_visible()
        sources = page.locator('#composerSourcesToggle')
        expect(sources).to_have_attribute('aria-checked', 'true')
        sources.tap()
        expect(sources).to_have_attribute('aria-checked', 'false')
        sources.tap()
        expect(sources).to_have_attribute('aria-checked', 'true')
        page.locator('#composerModelPicker').tap()
        expect(page.locator('.consensus-model-inline .model-picker-menu')).to_be_visible()
        page.wait_for_function("() => !document.body.classList.contains('composer-animating')")
        page.locator('.consensus-model-inline .model-picker-custom-option').tap()
        expect(page.locator('.consensus-model-inline .model-picker-menu')).to_contain_text('Answering models')
        _snapshot(page, f'agent-toolbar-models-touch-{width}')
        page.keyboard.press('Escape')
        page.evaluate('() => App.composer.collapse({force:true})')
        page.wait_for_function("() => !document.body.classList.contains('composer-animating')")
        page.locator('#composerDeepToggle').tap()
        menu = page.locator('.agent-model-picker .model-picker-menu')
        expect(menu).to_be_visible()
        page.wait_for_function("() => !document.body.classList.contains('composer-animating')")
        bounds = menu.bounding_box()
        assert bounds['x'] >= 0 and bounds['x'] + bounds['width'] <= width
        assert bounds['y'] >= 0 and bounds['y'] + bounds['height'] <= 844
        trigger = page.locator('.agent-model-picker .model-picker-display').bounding_box()
        assert bounds['y'] + bounds['height'] <= trigger['y'] - 7
        # Every option must receive touches across its width, including where
        # Send used to paint above the menu in the collapsed mobile composer.
        assert menu.evaluate('''menu => [...menu.querySelectorAll('[data-setting-value]')].every(option => {
            const r = option.getBoundingClientRect();
            return [.1, .5, .9].every(f => option.contains(document.elementFromPoint(r.x + r.width * f, r.y + r.height / 2)));
        })''')
        _snapshot(page, f'agent-toolbar-reasoning-touch-{width}')
        page.locator('.agent-model-picker [data-setting-value="high"]').tap()
        expect(page.locator('#agentReasoningEffort')).to_have_value('high')
        expect(page.locator('#composerDeepState')).to_have_text('High')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    finally:
        context.close()


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
    review["check_sources"] = True
    difference = review["checks"][0]["differences_data"]["differences"][0]
    difference["factual_check"] = {"checkable": True, "question": "Are five seats included?"}
    review["checks"][0]["source_verification"] = {
        "schema_version": 4, "check_type": "contradiction_evidence", "run_id": "c1", "answer_version": digest,
        "basis_hash": "basis", "status": "complete", "scope": {"contradictions": 1, "checked_contradictions": 1},
        "sources": [{"id": "D1", "url": "https://example.org/billing", "title": "Billing terms"}],
        "findings": [{"contradiction_id": "source-one", "difference_index": 0, "run_id": "c1", "answer_version": digest,
            "question": "Are five seats included?", "consensus_anchor": anchor, "checked": True, "state": "checked",
            "positions": [{"id": f"P{i+1}", "summary": p["stance"], "models": p["models"], "quote": p["quote"]} for i, p in enumerate(difference["positions"])],
            "supported_position_id": "P1", "verdict": "supports_position", "reason": "The terms explicitly include five seats.",
            "evidence": [{"source_id": "D1", "position_id": "P1", "quote": "The smaller plan includes five seats."}]}]}
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
        expect(page.locator('#composerModeBar')).to_be_visible()
        expect(page.locator('#composerAgentState')).to_have_text('On')
        legacy_mode = page.evaluate("localStorage.getItem('agentMode')")
        page.locator('#composerAgentToggle').click(force=True)
        assert page.evaluate("localStorage.getItem('agentMode')") == legacy_mode
        expect(page.locator('#composerAttachButton')).to_be_disabled()
        expect(page.locator('#composerSourcesToggle')).to_have_attribute('aria-checked', 'true')
        page.locator('#composerSourcesToggle').click()
        expect(page.locator('#composerSourcesToggle')).to_have_attribute('aria-checked', 'false')
        page.locator('#composerSourcesToggle').click()
        page.locator('#composerDeepToggle').focus()
        page.keyboard.press('Enter')
        expect(page.locator('.agent-model-picker .model-picker-menu')).to_be_visible()
        page.locator('.agent-model-picker [data-setting-value="high"]').click()
        expect(page.locator('#agentReasoningEffort')).to_have_value('high')
        expect(page.locator('#composerDeepState')).to_have_text('High')
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
        expect(page.locator('#composerModeBar')).to_be_visible()
        assert requests[0]['check_sources'] is True
        assert requests[0]['reasoning_effort'] == 'high'
        expect(page.locator('#quotaTriggerValue')).to_have_text('56%')
        expect(page.locator('.agent-evidence-link[data-section="sources"]')).to_have_text('Sources2')
        expect(page.locator('#chatExecutionControl')).not_to_be_visible()
        expect(page.locator('.agent-effort-control')).not_to_be_visible()
        expect(page.locator("#agentAnswerBody .cx-claim")).to_have_count(1)
        expect(page.locator('#agentAnswerBody .src-ref[href="https://example.org/billing"]')).to_have_count(1)
        expect(page.locator('#agentAnswerBody')).to_contain_text('billing terms')
        expect(page.locator('#agentAnswerBody')).not_to_contain_text('https://example.org/billing')
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
        expect(page.locator('#answerReaderInspector .contradiction-source-verdict')).to_contain_text('Sources support: Five seats')
        page.locator('#answerReaderInspector .contradiction-source-evidence-details > summary').click()
        expect(page.locator('#answerReaderInspector .contradiction-source-quote')).to_have_text(anchor)
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
        expect(page.locator('#answerReaderColumns .src-ref[href="https://example.org/pricing"]').first).to_be_visible()
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
        expect(page.locator('#agentAnswerBody .src-ref[href="https://example.org/billing"]')).to_have_count(1)
        page.locator('.agent-evidence-link[data-section="answers"]').click()
        expect(page.locator('#answerReaderColumns')).to_contain_text('Recommendation')
        page.keyboard.press('Escape')
        page.evaluate('turn => window.App.followup.renderStoredTurns([turn])', saved)
        history = page.locator('.thread-history-turn')
        expect(history.locator('.agent-history-models img')).to_have_count(6)
        expect(history.locator('.src-ref[href="https://example.org/billing"]')).to_have_count(1)
        history.locator('.agent-history-models button').last.click()
        expect(page.locator('#answerReaderColumns')).to_contain_text('Recommendation')
        expect(page.locator('#answerReaderModel')).to_have_value('Meta')
        page.evaluate("async () => { await window.__switchE2EUser('account-b'); }")
        expect(page.locator('#modelAnswerReader')).not_to_be_visible()
        assert not errors
    finally:
        context.close()


@pytest.mark.parametrize("width", [1280, 390])
def test_saved_agent_paper_urls_are_numbered_citations(browser, phase4_server, width):
    context, page = _real_firebase_page(browser, phase4_server)
    text = ("## Kurzfassung\n\nMehrere unabhängige Perspektiven können helfen.\n\n"
        "Verwandte Arbeiten: Self-Consistency (https://arxiv.org/abs/2203.07186), "
        "FrugalGPT (https://arxiv.org/abs/2305.05176), RouteLLM (https://arxiv.org/abs/2406.18665).")
    turn = {"id": "b" * 32, "question": "Welche Arbeiten untersuchen Modellvergleich und Routing?", "status": "failed",
        "execution_mode": "agent", "consensus": text, "sources": [],
        "agent_settings": {"model_id": CATALOG["default_model_id"], "label": "DeepSeek V4.1 Flash"}}
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    try:
        page.set_viewport_size({"width": width, "height": 900})
        page.route('**/user_status', lambda r: _json(r, {"tier": "pro", "is_pro": True, "agent_access": True}))
        page.route('**/agent/models', lambda r: _json(r, CATALOG))
        bookmark = {"id": "paper-citations", "chat_id": "a" * 32, "mode": "Agent", "execution_mode": "agent",
            "query": turn["question"], "responses": {"consensus": text}}
        page.route('**/bookmarks/paper-citations/conversation*', lambda r: _json(r, {
            "chat_id": "a" * 32, "turns": [turn], "has_more": False}))
        page.route('**/bookmarks/paper-citations', lambda r: _json(r, {"bookmark": bookmark}))
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        page.evaluate("async () => { await window.openBookmark('paper-citations'); }")
        refs = page.locator('#agentAnswerBody .src-ref')
        expect(refs).to_have_count(3)
        expect(page.locator('#agentAnswerBody')).not_to_contain_text('https://')
        assert refs.first.evaluate('el => getComputedStyle(el).verticalAlign') == 'super'
        assert page.locator('#agentAnswerBody').get_attribute('data-markdown') == text
        refs.first.focus()
        expect(page.locator('#sourceTeaser')).to_be_visible()
        expect(page.locator('#sourceTeaser .source-teaser-title')).to_have_text('Self-Consistency')
        page.locator('.agent-evidence-link[data-section="sources"]').click()
        expect(page.locator('#answerReaderInspector a')).to_have_count(3)
        expect(page.locator('#answerReaderInspector')).to_contain_text('FrugalGPT')
        page.keyboard.press('Escape')
        page.locator('#agentAnswerBody h2').scroll_into_view_if_needed()
        _snapshot(page, f'agent-paper-citations-{width}')
        page.evaluate('turn => window.App.followup.renderStoredTurns([turn])', turn)
        expect(page.locator('.thread-history-turn .src-ref')).to_have_count(3)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert not errors
    finally:
        context.close()


def test_green_agent_passages_hover_after_scrolling_and_reprojection(browser, phase4_server):
    from app.services.chat_store import turn_detail

    context, page = _real_firebase_page(browser, phase4_server)
    text = "\n**Conclusion:** The **smaller plan** includes five seats.\n\n" + "Background paragraph.\n\n" * 25 + "The **monthly price** is stable.\n\n"
    digest = hashlib.sha256(text.encode()).hexdigest()
    review = {"status": "succeeded", "answer_version": 1, "answer_hash": digest,
        "versions": [{"id": 1, "text": text, "hash": digest}],
        "comparisons": [{"id": "c1", "basis_hash": "basis", "question": "Compare plans", "status": "succeeded", "answers": []}],
        "checks": [{"comparison_id": "c1", "basis_hash": "basis", "answer_hash": digest, "status": "succeeded",
            "differences_data": {"models_compared": ["OpenAI", "Gemini"], "differences": [], "claims": [
                {"anchor": anchor, "agree": ["OpenAI", "Gemini"], "dissent": []}
                for anchor in ("Conclusion: The smaller plan includes five seats.", "The monthly price is stable.")]}}]}
    turn = turn_detail("b" * 32, {"execution_mode": "agent", "status": "completed", "question": "Compare plans", "assistant_response": text,
            "agent_review": review, "agent_settings": {"model_id": CATALOG["default_model_id"]}}, {})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    try:
        page.set_viewport_size({"width": 1440, "height": 900})
        page.route('**/user_status', lambda r: _json(r, {"tier": "pro", "is_pro": True, "agent_access": True}))
        page.route('**/agent/models', lambda r: _json(r, CATALOG))
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        for _ in range(2):
            page.evaluate("turn => App.runRegistry.showSavedView({type:'bookmark'}, {chatId:'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', turnId:turn.id, executionMode:'agent', question:turn.question, consensus:turn.consensus, currentTurn:turn})", turn)
            page.evaluate('() => window.exitHeroMode()')
            expect(page.locator('.agent-review-status')).to_have_text('Comparison checked')
            # Exercise the real Display control, including switching after render.
            page.get_by_role('button', name='Settings', exact=True).click()
            page.get_by_role('tab', name='Display', exact=True).click()
            page.locator('#consensusHighlightsSelect').select_option('all')
            page.get_by_role('button', name='Close settings', exact=True).click()
            expect(page.locator('#agentAnswerBody .cx-claim.is-marker-filtered')).to_have_count(0)
            expect(page.locator('#agentAnswerBody .cx-claim.is-unanimous').first).not_to_have_css('background-color', 'rgba(0, 0, 0, 0)')
            for index in (0, -1):
                mark = page.locator('#agentAnswerBody .cx-claim').nth(index)
                mark.evaluate("el => el.scrollIntoView({block: 'center'})")
                mark.hover()
                preview = page.locator('.insight-preview')
                # A trailing scroll used to cancel mouseenter's timer forever.
                page.evaluate("() => dispatchEvent(new Event('scroll'))")
                expect(preview).to_be_visible()
                expect(preview).to_contain_text('2/2')
                rect = preview.bounding_box()
                assert rect['y'] >= 0 and rect['y'] + rect['height'] <= 900
                page.mouse.move(0, 0)
                expect(preview).not_to_be_visible()
        assert not errors
    finally:
        context.close()
