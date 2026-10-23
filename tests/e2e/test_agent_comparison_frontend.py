"""Built Agent comparison controls, markers and saved projection without providers."""
import hashlib
import json
import re

import pytest
from playwright.sync_api import expect
from test_phase4_frontend import phase4_server, _real_firebase_page, _json
from test_agent_chat_frontend import CATALOG, _choose_mode, _open_agent_level, _snapshot


@pytest.mark.parametrize("width", [1280, 390])
def test_comparison_selection_blocks_send_before_losing_draft(browser, phase4_server, width):
    context, page = _real_firebase_page(browser, phase4_server)
    requests = []
    try:
        page.set_viewport_size({"width": width, "height": 960})
        page.route('**/user_status', lambda r: _json(r, {"tier": "pro", "is_pro": True, "agent_access": True}))
        page.route('**/agent/models', lambda r: _json(r, CATALOG))
        page.route('**/agent', lambda r: (requests.append(r.request.url), _json(r, {"error": "Unexpected request"}, 500)))
        page.route('**/chats', lambda r: (requests.append(r.request.url), _json(r, {"error": "Unexpected request"}, 500)))
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        _choose_mode(page, 'agent')
        page.locator('#questionInput').fill('Keep this draft while I choose the models.')
        expect(page.locator('#sendButton')).to_be_enabled()
        # One chip in Agent: the comparison models are a section of its menu.
        expect(page.locator('.consensus-model-inline')).to_be_hidden()
        _open_agent_level(page, 'companion')
        page.locator('.agent-model-picker .model-picker-custom-option').click()
        selected = page.locator('.agent-model-picker .model-picker-row-toggle[aria-checked="true"]')
        while selected.count() > 1:
            selected.first.click()
        expect(page.locator('#sendButton')).to_be_disabled()
        selected.first.click()
        expect(page.locator('#sendButton')).to_be_disabled()
        page.keyboard.press('Escape')
        expect(page.locator('#agentComposerNotice')).to_be_visible()
        expect(page.locator('#agentComposerMessage')).to_contain_text('comparison models')
        expect(page.locator('#sendButton')).to_have_attribute('title', page.locator('#agentComposerMessage').inner_text())
        page.locator('#questionInput').click()
        page.locator('#questionInput').press('Control+End')
        page.locator('#questionInput').press('Enter')
        # With a keyboard Enter sends at every width (Apple-Audit E7); the send
        # is blocked here, so the draft stays as it was.
        draft = 'Keep this draft while I choose the models.'
        expect(page.locator('#questionInput')).to_have_value(draft)
        # Also guard direct callers, independent of the disabled button.
        page.evaluate('() => App.agentChat.send()')
        expect(page.locator('#questionInput')).to_have_value(draft)
        assert requests == []
        page.locator('#agentComposerAction').click()
        expect(page.locator('.agent-model-picker .model-picker-menu')).to_be_visible()
        custom = page.locator('.agent-model-picker .model-picker-custom-option')
        if custom.is_visible():
            custom.click()
        excluded = page.locator('.agent-model-picker .model-picker-row-toggle[aria-checked="false"]')
        excluded.first.click()
        expect(page.locator('#sendButton')).to_be_disabled()
        excluded.first.click()
        expect(page.locator('#sendButton')).to_be_enabled()
        expect(page.locator('#agentComposerNotice')).not_to_be_visible()
        assert requests == []
    finally:
        context.close()


@pytest.mark.parametrize("width", [390, 369, 320])
def test_mobile_agent_plus_menu_opens_tools_from_single_line_composer(browser, phase4_server, width):
    context, page = _real_firebase_page(browser, phase4_server, has_touch=True,
        init_script="localStorage.setItem('theme','dark')" if width == 369 else None)
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
        page.wait_for_function("() => !document.body.classList.contains('composer-animating') && !document.body.classList.contains('composer-gliding')")
        expect(page.locator('#composerModeBar')).not_to_be_visible()
        assert page.locator('.chat-input-container').bounding_box()['height'] <= 60
        _snapshot(page, f'agent-single-line-{width}')
        # Focusing a follow-up expands the composer into the same anatomy as
        # every mode on a phone: the field, under it ONE row of (+), the
        # models and Send (an open Agent chat has no mode to choose), even
        # with a keyboard-sized viewport.
        page.set_viewport_size({"width": width, "height": 450})
        page.locator('#questionInput').tap()
        page.wait_for_function("() => !document.body.classList.contains('composer-collapsed') && !document.body.classList.contains('composer-animating') && !document.body.classList.contains('composer-gliding')")
        def box(selector):
            return page.locator(selector).evaluate('el => el.getBoundingClientRect().toJSON()')
        # One models chip (what the comparison models do, the chat model in
        # its tooltip), never a second comparison chip next to it.
        agent_model = box('.agent-model-picker .model-picker-display')
        expect(page.locator('.consensus-model-inline')).to_be_hidden()
        expect(page.locator('.composer-models .model-picker-display:visible')).to_have_count(1)
        expect(page.locator('.agent-model-picker .model-picker-display-text')).to_have_text(re.compile(r'^\d AIs cross-check$'))
        expect(page.locator('#runModeControl')).to_be_hidden()
        bounds = [box('#attachTrigger'), agent_model, box('#sendButton')]
        centers = [b['y'] + b['height'] / 2 for b in bounds]
        assert max(centers) - min(centers) <= 1
        assert all(a['right'] <= b['left'] + 1 for a, b in zip(bounds, bounds[1:]))
        assert box('#questionInput')['bottom'] <= min(b['top'] for b in bounds) + 1
        assert page.locator('.agent-model-picker .model-picker-display-text').evaluate(
            'label => label.scrollWidth <= label.clientWidth + 1')
        assert bounds[0]['x'] >= 0 and bounds[-1]['right'] <= width and agent_model['right'] <= width
        assert page.locator('.agent-model-picker').evaluate(
            "el => getComputedStyle(el, '::after').display === 'none'")
        _snapshot(page, f'agent-expanded-keyboard-{width}')
        page.set_viewport_size({"width": width, "height": 844})
        page.evaluate('() => App.composer.collapse({force:true})')
        page.wait_for_function("() => !document.body.classList.contains('composer-animating') && !document.body.classList.contains('composer-gliding')")
        page.locator('#attachTrigger').tap()
        expect(page.locator('#attachMenu')).to_be_visible()
        assert page.evaluate("document.body.classList.contains('composer-collapsed')")
        # The (+) menu no longer carries a mode switch; the mode stays Agent.
        expect(page.locator('#attachMenu .attach-menu-toggle[for="agentModeMenuSwitch"]')).to_have_count(0)
        expect(page.locator('#runModeSelect')).to_have_value('agent')
        # Agent Beta uploads into the private chat store, so upload stays available.
        expect(page.locator('#attachUploadOption')).to_be_enabled()
        # The mode leads the menu.
        expect(page.locator('#runModeControl [data-value="agent"]')).to_have_attribute('aria-pressed', 'true')
        _snapshot(page, f'agent-plus-options-{width}')
        page.locator('#agentComparisonMenuOption').tap()
        expect(page.locator('#attachMenu')).not_to_be_visible()
        expect(page.locator('.agent-model-picker .model-picker-menu')).to_be_visible()
        page.wait_for_function("() => !document.body.classList.contains('composer-animating') && !document.body.classList.contains('composer-gliding')")
        page.locator('.agent-model-picker .model-picker-custom-option').tap()
        expect(page.locator('.agent-model-picker .model-picker-menu')).to_contain_text('Comparison models')
        _snapshot(page, f'agent-toolbar-models-touch-{width}')
        selected = page.locator('.agent-model-picker .model-picker-row-toggle[aria-checked="true"]')
        while selected.count() > 1:
            selected.first.tap()
        page.keyboard.press('Escape')
        page.evaluate('() => App.composer.collapse({force:true})')
        page.wait_for_function("() => !document.body.classList.contains('composer-animating') && !document.body.classList.contains('composer-gliding')")
        expect(page.locator('#agentComposerNotice')).to_be_visible()
        expect(page.locator('#composerModeBar')).not_to_be_visible()
        _snapshot(page, f'agent-followup-selection-hint-{width}')
        page.locator('#agentComposerAction').tap()
        expect(page.locator('.agent-model-picker .model-picker-menu')).to_be_visible()
        page.locator('.agent-model-picker .model-picker-row-toggle[aria-checked="false"]').first.tap()
        expect(page.locator('#agentComposerNotice')).not_to_be_visible()
        page.keyboard.press('Escape')
        page.evaluate('() => App.composer.collapse({force:true})')
        page.wait_for_function("() => !document.body.classList.contains('composer-animating') && !document.body.classList.contains('composer-gliding')")
        page.locator('#attachTrigger').tap()
        page.locator('#agentReasoningMenuOption').tap()
        menu = page.locator('.agent-model-picker .model-picker-menu')
        expect(menu).to_be_visible()
        page.wait_for_function("() => !document.body.classList.contains('composer-animating') && !document.body.classList.contains('composer-gliding')")
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
        expect(page.locator('#composerReasoningState')).to_have_text('High')
        expect(page.locator('#agentReasoningMenuState')).to_have_text('High')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    finally:
        context.close()


@pytest.mark.parametrize("width,dark", [(1440, False), (390, True), (320, False)])
def test_comparison_review_and_saved_projection(browser, phase4_server, width, dark):
    context, page = _real_firebase_page(browser, phase4_server, has_touch=width < 700)
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
                 "sources": [{"url": "https://example.org/pricing", "title": "Plan details"}]},
                # The orchestrator read a cited page after the comparison (read_source).
                {"version": 1, "id": "read", "kind": "tool", "name": "read_source", "status": "succeeded",
                 "host": "example.org", "read": "completed", "sources": [{"url": "https://example.org/terms", "title": "Seat terms"}]}]
    agents = [{"id": f"{i + 10:032x}", "seq": i + 1, "status": "completed", "kind": "comparison", "title": a["model"]["label"], "model": a["model"], "duration_ms": 3100,
               "comparison_id": "c1", "progress_text": "Checking seat limits and monthly billing.", "progress_kind": "excerpt"} for i, a in enumerate(answers)]
    agents.append({"id": f"{30:032x}", "seq": 7, "status": "completed", "kind": "judge", "title": "Differences judge",
                   "model": answers[0]["model"], "duration_ms": 2100})
    # The helper that opened the page: a row in the panel, never a voice in the model stack.
    agents.append({"id": f"{31:032x}", "seq": 8, "status": "completed", "kind": "source", "title": "Read source · example.org",
                   "model": {"model": "openai/gpt-6-luna", "label": "GPT-6 Luna"}, "duration_ms": 1800})
    review = {"status": "succeeded", "answer_version": 1, "answer_hash": digest,
        "versions": [{"id": 1, "text": text, "hash": digest, "status": "succeeded"}],
        "comparisons": [{"id": "c1", "basis_hash": "basis", "question": "Which plan suits a team of five?", "reason": "Compare cost and flexibility",
            "context": "The team needs monthly billing.", "status": "succeeded", "answers": answers}],
        "checks": [{"comparison_id": "c1", "basis_hash": "basis", "answer_hash": digest, "status": "succeeded",
            "differences_data": {"claims": [], "differences": [{"claim": "Whether the smaller plan includes five seats", "consensus_anchor": anchor, "type": "contradiction", "severity": "major", "positions": [
                {"models": ["OpenAI"], "stance": "Five seats are included.", "quote": "Choose the smaller plan."},
                {"models": ["DeepSeek"], "stance": "The seat limit needs confirmation.", "quote": "Confirm the seat limit"}]}], "models_compared": [m[1] for m in models]}}]}
    review["read_sources"] = [{"id": 1, "url": "https://example.org/terms", "host": "example.org", "title": "Seat terms",
                               "status": "completed", "text": "The smaller plan includes five seats."}]
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
        assert page.evaluate("App.runMode.preference()") == 'agent'
        assert page.evaluate("localStorage.getItem('agentMode')") is None
        # The toolbar Attach opens the same file picker as the (+) menu upload.
        expect(page.locator('#composerAttachButton')).to_be_enabled()
        with page.expect_file_chooser():
            page.locator('#composerAttachButton').click()
        expect(page.locator('#composerSourcesToggle')).to_have_count(0)
        page.locator('#composerReasoningToggle').focus()
        page.keyboard.press('Enter')
        expect(page.locator('.agent-model-picker .model-picker-menu')).to_be_visible()
        page.locator('.agent-model-picker [data-setting-value="high"]').click()
        expect(page.locator('#agentReasoningEffort')).to_have_value('high')
        expect(page.locator('#composerReasoningState')).to_have_text('High')
        page.evaluate("dark => { document.documentElement.classList.toggle('dark-mode', dark); document.body.classList.toggle('dark-mode', dark); }", dark)
        expect(page.locator('#quotaTrigger')).to_have_attribute('aria-label', re.compile(r'^75% of today'))
        expect(page.locator("#agentTokenBudget")).to_have_count(0)
        def assert_composer_layout():
            input_box = page.locator("#questionInput").bounding_box()
            composer = page.locator(".chat-input-container").bounding_box()
            hero = page.evaluate("document.body.classList.contains('is-hero')")
            assert input_box["width"] >= min(210, composer["width"] * (.7 if hero else .25))
            assert input_box["height"] <= 80
            if page.locator("#agentModelControls").is_visible():
                label = page.locator(".agent-model-picker .model-picker-display-text").bounding_box()
                assert label["width"] >= 90
        expect(page.locator(".consensus-model-inline")).to_be_hidden()
        expect(page.locator(".agent-model-picker .model-picker-display-text")).to_have_text(re.compile(r"^\d+ AIs cross-check$"))
        _open_agent_level(page, "companion")
        page.locator(".agent-model-picker .model-picker-custom-option").click()
        expect(page.locator(".agent-model-picker .model-picker-menu")).not_to_contain_text("Consensus engine")
        page.keyboard.press("Escape")
        assert_composer_layout()
        _snapshot(page, f"comparison-composer-{width}")
        page.locator("#questionInput").fill(saved["question"])
        page.locator("#sendButton").click()
        expect(page.locator(".agent-review-status")).to_be_hidden()
        expect(page.locator('#composerModeBar')).not_to_be_visible()
        page.wait_for_function("() => !document.body.classList.contains('composer-animating') && !document.body.classList.contains('composer-gliding')")
        assert page.locator('.chat-input-container').bounding_box()['height'] <= 60
        expect(page.locator('#attachTrigger')).to_be_visible()
        assert 'check_sources' not in requests[0]
        assert requests[0]['reasoning_effort'] == 'high'
        expect(page.locator('#quotaTrigger')).to_have_attribute('aria-label', re.compile(r'^56% of today'))
        expect(page.locator('.agent-evidence-link[data-section="sources"]')).to_have_text('Sources3')
        page.wait_for_function("() => App.runRegistry.visible()?.status === 'succeeded'")
        evidence_links = page.locator('#agentAnswer .agent-evidence-link')
        expect(evidence_links.locator('svg[aria-hidden="true"]')).to_have_count(3)
        expect(page.locator('#agentAnswer').get_by_role('button', name='Follow up')).to_have_count(0)
        assert evidence_links.first.evaluate('el => getComputedStyle(el).backgroundImage') == 'none'
        if width <= 540:
            # One toolbar row (2026-10-22): the evidence links and the
            # answer's Watch and Share, from the answer's left edge to its
            # right, side by side, each a finger wide.
            expect(page.locator('#agentAnswer .agent-share-pill')).to_be_visible()
            # Measure one layout frame: activity-height transitions can move the
            # entire row between separate Playwright round trips.
            row = page.evaluate('''() => ({
                body: document.getElementById('agentAnswerBody').getBoundingClientRect().toJSON(),
                cells: [...document.querySelectorAll('#agentAnswer :is(.agent-evidence-link, .agent-watch-pill, .agent-share-pill)')]
                    .map(cell => cell.getBoundingClientRect().toJSON())})''')
            boxes = row['cells']
            assert len(boxes) == 5, boxes
            assert max(round(box['y']) for box in boxes) - min(round(box['y']) for box in boxes) <= 1
            assert all(box['height'] >= 44 and box['width'] >= 43.5 for box in boxes), boxes
            assert abs(boxes[0]['left'] - row['body']['left']) <= 1, (boxes[0], row['body'])
            assert abs(boxes[-1]['right'] - row['body']['right']) <= 1, (boxes[-1], row['body'])
            assert all(a['right'] <= b['left'] for a, b in zip(boxes, boxes[1:])), boxes
            assert evidence_links.evaluate_all('''links => links.every(link => {
                const box = link.getBoundingClientRect();
                return [...link.children].every(child => {
                    const rect = child.getBoundingClientRect();
                    return rect.left >= box.left && rect.right <= box.right;
                });
            })''')
        expect(page.locator('#runModeSelect')).to_have_value('agent')
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
        # A model's row in the agent panel opens its answer in the reader;
        # the answer check opens the differences.
        expect(page.locator('#agentSidebar')).not_to_be_visible()
        page.locator('#agentAnswer .agent-sidebar-toggle').click()
        page.locator('.agent-session', has_text='Kimi K2.6').locator('summary').click()
        expect(page.locator('#modelAnswerReader')).to_be_visible()
        expect(page.locator('#agentSidebar')).not_to_be_visible()
        expect(page.locator('#answerReaderModel')).to_have_value('Kimi')
        expect(page.locator('#answerReaderColumns')).to_contain_text('Recommendation')
        page.keyboard.press('Escape')
        expect(page.locator('#modelAnswerReader')).not_to_be_visible()
        page.locator('#agentAnswer .agent-sidebar-toggle').click()
        page.locator('.agent-session', has_text='Answer check').locator('summary').click()
        expect(page.locator('#answerReaderInspector')).to_contain_text('Whether the smaller plan includes five seats')
        page.keyboard.press('Escape')
        # The panel leaves with a short animation; ask once it has settled.
        page.wait_for_function("() => !document.getElementById('agentSidebar').classList.contains('is-leaving')")
        if page.locator('#agentSidebar').is_visible():
            page.locator('.agent-sidebar-close').click()
        page.mouse.move(0, 0)
        details = page.locator('#agentAnswerActivity details')
        details.locator('.agent-activity-title').click()
        insights = details.locator('.agent-activity-insights')
        expect(insights).to_be_visible()
        expect(insights).to_contain_text('Which plan suits a team of five?')
        expect(insights).to_contain_text('Compare cost and flexibility')
        expect(insights).to_contain_text('6 model answers')
        expect(insights).to_contain_text('Disagreement: Whether the smaller plan includes five seats')
        # The read page is the step's pill: its domain, the live run's verb.
        read = details.locator('.agent-activity-tool', has_text='Read source')
        expect(read.locator('strong')).to_have_text('Read source')
        expect(read.locator('.agent-activity-sources .src-ref')).to_have_text('example.org')
        expect(insights).to_have_css('opacity', '1')
        page.wait_for_function("""() => {
          const host = document.getElementById('agentAnswerActivity');
          return getComputedStyle(host.querySelector('.agent-activity-history')).opacity === '1'
            && host.getAnimations().every(a => a.playState !== 'running');
        }""")
        _snapshot(page, f'agent-duration-insights-{width}')
        insights.get_by_role('button', name='Read model answers').click()
        expect(page.locator('#answerReaderColumns')).to_contain_text('Recommendation')
        page.keyboard.press('Escape')
        insights.get_by_role('button', name='Explore review and sources').click()
        expect(page.locator('#answerReaderInspector')).to_contain_text('Whether the smaller plan includes five seats')
        page.keyboard.press('Escape')
        details.locator('.agent-activity-title').click()
        expect(details).not_to_have_attribute('open', '')
        expect(page.locator('.agent-basis-select, .agent-comparison-response')).to_have_count(0)
        _snapshot(page, f"comparison-review-{width}")
        marker = page.locator('#agentAnswerBody .cx-claim[role="button"]').first
        marker.focus()
        page.keyboard.press("Enter")
        # Enter pins the mark's card (a sheet on a phone): the two sides with
        # "vs"; its footer leads, with the toolbar's glyphs and words, to the
        # difference in the reader and to the answers.
        card = page.locator('#claimPopover')
        expect(card).to_be_visible()
        expect(card.locator('.cx-card-vs')).to_have_count(1)
        expect(card.locator('.cx-card-action')).to_have_text(['Contradictions', 'Answers'])
        card.locator('.cx-card-action[data-section="differences"]').click()
        expect(card).to_be_hidden()
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
        expect(page.locator('#answerReaderColumns .src-ref[href="https://example.org/pricing"]').first).to_be_visible()
        _snapshot(page, f"comparison-answer-{width}")
        page.locator('#answerReaderSections [data-section="sources"]').click()
        expect(page.locator('#answerReaderInspector a[href="https://example.org/pricing"]')).to_be_visible()
        read_marks = page.locator('#answerReaderInspector .agent-source-read')
        expect(read_marks).to_have_count(1)
        expect(page.locator('#answerReaderInspector li', has=page.locator('.agent-source-read'))).to_contain_text('Seat terms')
        expect(read_marks).to_have_text('Read by the agent')
        page.keyboard.press('Escape')
        expect(page.locator('#modelAnswerReader')).not_to_be_visible()
        expect(marker).to_be_focused()
        page.locator('.agent-evidence-link[data-section="differences"]').click()
        expect(page.locator('#answerReaderInspector')).to_contain_text('Whether the smaller plan includes five seats')
        page.keyboard.press('Escape')
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert_composer_layout()
        # Older/incomplete traces still have useful, persisted review evidence.
        saved['agent_activity'] = []
        page.evaluate("data => window.App.runRegistry.showSavedView({type:'bookmark'}, data)", {
            "chatId": chat, "turnId": turn, "executionMode": "agent", "question": saved["question"], "consensus": text, "currentTurn": saved})
        expect(page.locator(".agent-review-status")).to_be_hidden()
        expect(page.locator("#agentAnswerBody .cx-claim")).to_have_count(1)
        expect(page.locator('#agentAnswerBody .src-ref[href="https://example.org/billing"]')).to_have_count(1)
        details.locator('.agent-activity-title').click()
        expect(insights).to_be_visible()
        expect(insights).to_contain_text('Compare cost and flexibility')
        expect(insights).to_contain_text('Disagreement: Whether the smaller plan includes five seats')
        details.locator('.agent-activity-title').click()
        expect(details).not_to_have_attribute('open', '')
        page.locator('.agent-evidence-link[data-section="answers"]').click()
        expect(page.locator('#answerReaderColumns')).to_contain_text('Recommendation')
        page.keyboard.press('Escape')
        page.evaluate('turn => window.App.followup.renderStoredTurns([turn])', saved)
        history = page.locator('.thread-history-turn')
        # The summary carries the model marks too (a click there opens an
        # answer, as in the live turn): open the activity at its title.
        expect(history.locator('.agent-activity > summary > .agent-history-models')).to_have_count(1)
        history.locator('.agent-activity-title').click()
        expect(history.locator('.agent-activity-insights')).to_be_visible()
        expect(history.locator('.agent-activity-insights')).to_contain_text('6 model answers')
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
def test_saved_agent_paper_urls_become_source_pills(browser, phase4_server, width):
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
        # Source pills sit on the text baseline (favicon + domain), no raised numbers.
        assert refs.first.evaluate('el => getComputedStyle(el).verticalAlign') == 'baseline'
        expect(refs.first.locator('.src-ref-label')).to_have_text('arxiv.org')
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


@pytest.mark.parametrize("width,dark", [(1440, False), (1440, True), (390, False), (390, True)])
def test_differences_reader_stays_calm_with_missing_models(browser, phase4_server, width, dark):
    """One status line, severity-first findings, one open finding at a time."""
    from app.services.chat_store import turn_detail

    context, page = _real_firebase_page(browser, phase4_server, has_touch=width < 700,
        init_script=f"localStorage.setItem('theme', '{'dark' if dark else 'light'}');")
    critical, minor = "The smaller plan includes five seats.", "Billing is monthly."
    text = "For a team of five, start with the **smaller plan**.\n\n" + critical + "\n\n" + minor + "\n\nConfirm the seat limit before purchasing."
    digest = hashlib.sha256(text.encode()).hexdigest()
    models = [("openai", "OpenAI", "openai/gpt-5.4-mini", "GPT-5.4 Mini"),
              ("gemini", "Gemini", "google/gemini-3.5-flash-lite", "Gemini 3.5 Flash-Lite"),
              ("kimi", "Kimi", "moonshotai/kimi-k2.6", "Kimi K2.6"),
              ("glm", "GLM", "z-ai/glm-5.3-flash", "GLM 5.3 Flash")]
    answers = [{"provider": p, "provider_label": label, "model": {"model": model, "label": name},
        "text": f"### {name}\n\nChoose the **smaller plan**. Confirm the seat limit.", "sources": []} for p, label, model, name in models]
    failed = [{"label": "GPT-5.6 Luna", "model": "openai/gpt-5.6-luna", "failure": {"code": "late_cutoff"}},
              {"label": "DeepSeek V4 Flash", "model": "deepseek/deepseek-v4-flash", "failure": {}}]
    differences = [
        {"claim": "Whether billing is monthly or annual", "consensus_anchor": minor, "type": "contradiction", "severity": "minor",
         "positions": [{"models": ["OpenAI", "Gemini"], "stance": "Billing is monthly.", "quote": "Confirm the seat limit."},
                       {"models": ["Kimi"], "stance": "Annual billing is cheaper.", "quote": "Choose the smaller plan."}]},
        {"claim": "Whether the smaller plan includes five seats", "consensus_anchor": critical, "type": "contradiction", "severity": "major",
         "positions": [{"models": ["OpenAI", "Gemini", "Kimi"], "stance": "Five seats are included.", "quote": "Choose the smaller plan."},
                       {"models": ["GLM"], "stance": "The seat limit needs confirmation.", "quote": "Confirm the seat limit."}]},
        {"claim": "What matters most when the team grows", "type": "emphasis",
         "positions": [{"models": ["Gemini"], "stance": "Upgrade flexibility."}, {"models": ["GLM"], "stance": "Monthly cost."}]}]
    question = ("Which plan suits a team of five that needs monthly billing, expects to grow to eight people next year "
                "and wants to avoid paying for seats it does not use?")
    review = {"status": "succeeded", "answer_version": 1, "answer_hash": digest,
        "versions": [{"id": 1, "text": text, "hash": digest, "status": "succeeded"}],
        "comparisons": [{"id": "c1", "basis_hash": "basis", "question": question, "reason": "Compare cost and flexibility",
            "status": "partial", "answers": answers, "failed_models": failed}],
        "checks": [{"comparison_id": "c1", "basis_hash": "basis", "answer_hash": digest, "status": "succeeded",
            "issues": [{"code": "models_unavailable", "count": 2}],
            "differences_data": {"claims": [], "differences": differences, "models_compared": [m[1] for m in models]}}]}
    turn = turn_detail("b" * 32, {"execution_mode": "agent", "status": "completed", "question": "Compare plans for our team",
        "assistant_response": text, "agent_review": review, "agent_settings": {"model_id": CATALOG["default_model_id"]}}, {})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    theme = 'dark' if dark else 'light'
    try:
        page.set_viewport_size({"width": width, "height": 900})
        page.route('**/user_status', lambda r: _json(r, {"tier": "pro", "is_pro": True, "agent_access": True}))
        page.route('**/agent/models', lambda r: _json(r, CATALOG))
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        page.evaluate("turn => App.runRegistry.showSavedView({type:'bookmark'}, {chatId:'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', turnId:turn.id, executionMode:'agent', question:turn.question, consensus:turn.consensus, currentTurn:turn})", turn)
        page.evaluate('() => window.exitHeroMode()')
        page.locator('.agent-evidence-link[data-section="differences"]').click()
        reader = page.locator('#modelAnswerReader')
        expect(reader).to_be_visible()
        page.locator('.answer-reader-dialog').evaluate("async el => { await Promise.all(el.getAnimations().map(a => a.finished.catch(() => {}))); }")
        # No subtitle, no "Comparison focus" label; the question is one line.
        expect(page.locator('#answerReaderStatus')).to_be_hidden()
        expect(page.locator('.answer-reader-context-top')).to_be_hidden()
        line_box = page.locator('#answerReaderQuestion summary span').bounding_box()
        assert line_box['height'] <= 24, line_box
        # One quiet status line; the missing models wait behind it.
        status = page.locator('#answerReaderInspector details.agent-evidence-status')
        expect(status.locator('summary')).to_have_text('4 of 6 models answered · Checked')
        expect(status.locator('.agent-evidence-status-detail')).to_be_hidden()
        expect(page.locator('#answerReaderInspector')).not_to_contain_text('Checked ·')
        cards = page.locator('#answerReaderInspector .diff-card')
        expect(cards).to_have_count(3)
        expect(cards.locator('.diff-type-tag')).to_have_text(['Critical', 'Minor', 'Emphasis'])
        expect(page.locator('#answerReaderInspector')).not_to_contain_text('positions')
        # The weightiest finding is open on entry; the others wait as one line.
        expect(cards.first).to_have_attribute('open', '')
        for index in (1, 2):
            expect(cards.nth(index)).not_to_have_attribute('open', '')
        # The chat's type, three steps: a semibold title, the claims at the
        # answer's 17px, one meta size and grey for everything else.
        type_steps = cards.first.evaluate("""card => {
          const style = el => { const s = getComputedStyle(el); return [s.fontSize, s.fontWeight, s.color]; };
          return {title: style(card.querySelector('.diff-card-claim')), claim: style(card.querySelector('.diff-position-stance')),
            tag: style(card.querySelector('.diff-type-tag')), meta: style(card.querySelector('.diff-position-meta')),
            versus: style(card.querySelector('.diff-versus-mark')),
            status: style(document.querySelector('#answerReaderInspector .agent-evidence-status')),
            more: style(document.querySelector('#answerReaderInspector .diff-more-summary'))};
        }""")
        assert type_steps['title'][:2] == ['17px', '600']
        assert type_steps['claim'][:2] == ['17px', '400']
        # The dot carries the colour, not the word, and "vs" is no warning sign.
        assert type_steps['tag'] == type_steps['meta'] == type_steps['versus'] == type_steps['status'] == type_steps['more']
        assert type_steps['meta'][0] == '13px'
        _snapshot(page, f'differences-calm-overview-{width}-{theme}')
        status.locator('summary').click()
        detail = status.locator('.agent-evidence-status-detail')
        expect(detail).to_be_visible()
        expect(detail).to_contain_text('GPT-5.6 Luna: no answer, it was still writing when the answer was finished.')
        expect(detail).to_contain_text('DeepSeek V4 Flash: no answer, no complete answer arrived.')
        status.locator('summary').click()
        expect(cards.first).to_have_attribute('open', '')
        # Two claims facing each other, always one above the other, "vs" between them.
        expect(cards.first.locator('.diff-sides.is-versus')).to_have_count(1)
        expect(cards.first.locator('.diff-versus-mark')).to_have_text('vs')
        expect(cards.first.locator('.diff-position-stance')).to_have_text(
            ['Five seats are included.', 'The seat limit needs confirmation.'])
        side_boxes = [cards.first.locator('.diff-position').nth(i).bounding_box() for i in range(2)]
        assert side_boxes[1]['y'] > side_boxes[0]['y'] + side_boxes[0]['height'] - 1  # one above the other
        heads = cards.first.locator('.diff-position-label')
        expect(heads).to_have_count(2)
        expect(heads.first.locator('.diff-position-name')).to_have_text(['GPT-5.4 Mini', 'Gemini 3.5 Flash-Lite', 'Kimi K2.6'])
        expect(heads.first.locator('.diff-jump-link')).to_have_count(3)
        expect(cards.first.locator('.diff-position-links')).to_have_count(0)
        if width >= 760:
            # Icons and names share a single line per position.
            assert heads.first.bounding_box()['height'] <= 30
        quote = cards.first.locator('.diff-position-quote').first
        expect(quote).to_be_hidden()
        cards.first.locator('.diff-quote-toggle').first.click()
        expect(quote).to_be_visible()
        _snapshot(page, f'differences-calm-detail-{width}-{theme}')
        # The smaller differences wait in one closed group behind the critical one.
        more = page.locator('#answerReaderInspector details.diff-more')
        expect(more.locator('.diff-more-summary')).to_have_text('2 smaller differences')
        expect(cards.nth(1)).to_be_hidden()
        more.locator('.diff-more-summary').click()
        cards.nth(1).locator('summary').click()
        expect(cards.nth(1)).to_have_attribute('open', '')
        expect(cards.first).not_to_have_attribute('open', '')
        assert page.evaluate("() => { const s = document.getElementById('answerReaderScroll'); return s.scrollWidth <= s.clientWidth + 1; }")
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        cards.nth(1).locator('.diff-jump-link').last.click()
        expect(page.locator('#answerReaderColumns h3').last).to_have_text('Kimi K2.6')
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
            expect(page.locator('.agent-review-status')).to_be_hidden()
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


def test_phone_closing_the_sentence_sheet_brings_no_hover_card(browser, phase4_server):
    """On a phone a tap on a disputed sentence opens its card as a sheet from
    the bottom edge; closing it gives the focus back to the sentence. That
    focus is no request for the hover card (Apple audit follow-up
    2026-10-21): it used to pop up on its own 130 ms later. The hover card
    exists only for a real mouse."""
    from app.services.chat_store import turn_detail

    context, page = _real_firebase_page(browser, phase4_server, has_touch=True)
    sentence = "The smaller plan includes five seats."
    text = "For a team of five, start with the smaller plan.\n\n" + sentence + "\n\nConfirm the seat limit."
    digest = hashlib.sha256(text.encode()).hexdigest()
    answers = [{"provider": p, "provider_label": label, "model": {"model": model, "label": name},
                "text": "Choose the smaller plan.", "sources": []}
               for p, label, model, name in [("openai", "OpenAI", "openai/gpt-5.4-mini", "GPT-5.4 Mini"),
                                             ("gemini", "Gemini", "google/gemini-3.5-flash-lite", "Gemini 3.5 Flash-Lite")]]
    review = {"status": "succeeded", "answer_version": 1, "answer_hash": digest,
        "versions": [{"id": 1, "text": text, "hash": digest, "status": "succeeded"}],
        "comparisons": [{"id": "c1", "basis_hash": "basis", "question": "Compare plans", "status": "succeeded", "answers": answers}],
        "checks": [{"comparison_id": "c1", "basis_hash": "basis", "answer_hash": digest, "status": "succeeded",
            "differences_data": {"models_compared": ["OpenAI", "Gemini"], "claims": [], "differences": [
                {"claim": "Whether the smaller plan includes five seats", "consensus_anchor": sentence, "type": "contradiction",
                 "severity": "major", "positions": [
                     {"models": ["OpenAI"], "stance": "Five seats are included.", "quote": "Choose the smaller plan."},
                     {"models": ["Gemini"], "stance": "Only three seats are included.", "quote": "Choose the smaller plan."}]}]}}]}
    turn = turn_detail("b" * 32, {"execution_mode": "agent", "status": "completed", "question": "Compare plans", "assistant_response": text,
            "agent_review": review, "agent_settings": {"model_id": CATALOG["default_model_id"]}}, {})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    try:
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("matchMedia('(hover: none) and (pointer: coarse)').matches")
        page.route('**/user_status', lambda r: _json(r, {"tier": "pro", "is_pro": True, "agent_access": True}))
        page.route('**/agent/models', lambda r: _json(r, CATALOG))
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        page.evaluate("turn => App.runRegistry.showSavedView({type:'bookmark'}, {chatId:'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', turnId:turn.id, executionMode:'agent', question:turn.question, consensus:turn.consensus, currentTurn:turn})", turn)
        page.evaluate('() => window.exitHeroMode()')
        mark = page.locator('#agentAnswerBody .cx-claim.is-major')
        expect(mark).to_have_text(sentence)
        expect(mark).to_have_attribute('tabindex', '0')
        mark.tap()
        sheet = page.locator('#claimPopover')
        expect(sheet).to_be_visible()
        expect(sheet).to_have_attribute('aria-modal', 'true')
        expect(sheet.locator('.cx-card-claim')).to_have_text(['Five seats are included.', 'Only three seats are included.'])
        sheet.locator('.claim-popover-close').tap()
        expect(sheet).to_be_hidden()
        # The focus is back on the sentence, and no card follows it.
        page.wait_for_function("() => document.activeElement?.classList.contains('cx-claim')")
        page.wait_for_timeout(400)
        expect(page.locator('.insight-preview:not([hidden])')).to_have_count(0)
        expect(mark).not_to_have_class(re.compile(r"\bis-hovered\b"))
        # A scroll with the tap still on the sentence brings none either.
        page.evaluate("() => dispatchEvent(new Event('scroll'))")
        page.wait_for_timeout(300)
        expect(page.locator('.insight-preview:not([hidden])')).to_have_count(0)
        assert not errors
    finally:
        context.close()


@pytest.mark.parametrize("width", [1280, 390])
def test_live_comparison_quotes_model_reasoning_in_turn_only_while_comparing(browser, phase4_server, width):
    """The quiet compare_models phase quotes the comparison models' latest
    reasoning sentences on ONE line from streamed delegation events: each
    excerpt stands about 2.5 s, then the next model with something new takes
    the line in turn; it leaves with the comparison and is never saved."""
    context, page = _real_firebase_page(browser, phase4_server)
    chat, turn, gemini, gpt = (c * 32 for c in "abcd")
    text = "Both plans fit; the smaller one is cheaper."
    def answer(identity, seq, status, label, model, progress):
        return {"id": identity, "seq": seq, "status": status, "kind": "comparison", "title": "Independent answer",
                "model": {"model": model, "label": label}, "duration_ms": 1200, "progress_text": progress}
    tool = {"version": 1, "id": "compare", "kind": "tool", "name": "compare_models", "status": "running"}
    saved = {"id": turn, "question": "Compare plans for our team", "status": "completed", "execution_mode": "agent",
             "mode": "Agent", "consensus": text, "sources": [], "model_answers": {},
             "agent_activity": [{**tool, "status": "succeeded"}],
             "agent_settings": {"model_id": "claude-haiku-4-5", "label": "Claude Haiku 4.5", "policy": {"delegation": True}}}
    listed = {"agents": [], "status": "running"}
    bookmarks, errors = [], []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        page.set_viewport_size({"width": width, "height": 900})
        page.route("**/user_status", lambda r: _json(r, {"tier": "pro", "is_pro": True, "agent_access": True}))
        page.route("**/agent/models", lambda r: _json(r, CATALOG))
        page.route("**/chats", lambda r: _json(r, {"chat": {"id": chat, "execution_mode": "agent"}}))
        page.route(f"**/agent/chats/{chat}/turns/{turn}/agents", lambda r: _json(r, listed))
        page.route("**/bookmarks?*", lambda r: _json(r, {"bookmarks": bookmarks, "next_cursor": None}))
        page.route("**/bookmarks/*/conversation*", lambda r: _json(r, {"chat_id": chat, "turns": [saved], "has_more": False}))
        page.route("**/bookmarks/*", lambda r: _json(r, {"bookmark": bookmarks[0]}))
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        _choose_mode(page, "agent")
        # A real open stream: the app's SSE parser and run lifecycle receive
        # each delegation event in turn, as during a live comparison.
        page.evaluate("""data => {
          const fetch = window.fetch;
          window.fetch = (url, options) => {
            if (String(url) !== '/agent') return fetch(url, options);
            window.__agentRequest = JSON.parse(options.body);
            return Promise.resolve(new Response(new ReadableStream({start(controller) {
              window.__agentPush = (type, event) => controller.enqueue(new TextEncoder().encode(`event: ${type}\\ndata: ${JSON.stringify(event)}\\n\\n`));
              // The app may abort the stream itself once the final event arrived.
              window.__agentClose = () => { try { controller.close(); } catch (_) {} };
              window.__agentPush('started', {chat_id: data.chat, turn_id: data.turn, delegation: true});
              window.__agentPush('activity', data.tool);
            }}), {headers: {'Content-Type': 'text/event-stream'}}));
          };
        }""", {"chat": chat, "turn": turn, "tool": tool})
        push = lambda name, event: page.evaluate("([name, event]) => window.__agentPush(name, event)", [name, event])
        delegate = lambda agent: push("delegation", {"version": 1, "chat_id": chat, "turn_id": turn, "agent": agent})
        page.locator("#questionInput").fill(saved["question"])
        page.locator("#sendButton").click()
        preview = page.locator("#agentAnswerActivity .agent-progress")
        expect(preview).to_contain_text("Comparing perspectives…")
        quotes = preview.locator("p").filter(has_text=re.compile(r"^(Gemini 3\.5 Flash-Lite|GPT-5\.4 Mini): "))
        expect(quotes).to_have_count(0)

        delegate(answer(gemini, 1, "working", "Gemini 3.5 Flash-Lite", "google/gemini-3.5-flash-lite",
                        "Reading the question.\nChecking the 2026 figures."))
        expect(quotes).to_have_count(1)
        expect(quotes).to_have_text("Gemini 3.5 Flash-Lite: Checking the 2026 figures.")
        delegate(answer(gpt, 1, "working", "GPT-5.4 Mini", "openai/gpt-5.4-mini", "Weighing both sources."))
        # Gemini's excerpt stands its time before GPT takes the line.
        expect(quotes).to_have_text("Gemini 3.5 Flash-Lite: Checking the 2026 figures.")
        expect(quotes).to_have_text("GPT-5.4 Mini: Weighing both sources.")
        # Gemini's newer reasoning takes the line back in turn; still exactly one line.
        delegate(answer(gemini, 2, "working", "Gemini 3.5 Flash-Lite", "google/gemini-3.5-flash-lite",
                        "Checking the 2026 figures.\nComparing the seat limits."))
        expect(quotes).to_have_text("Gemini 3.5 Flash-Lite: Comparing the seat limits.")
        expect(preview.locator("p:not(.agent-progress-step)")).to_have_count(1)
        expect(preview).to_contain_text("Comparing perspectives…")
        # The quote is live only: it never enters the activity history.
        expect(page.locator("#agentAnswerActivity .agent-activity-history")).not_to_contain_text("seat limits")

        # Once both comparison models finished, the line leaves while the run continues.
        finished = [answer(gemini, 3, "completed", "Gemini 3.5 Flash-Lite", "google/gemini-3.5-flash-lite", "Comparing the seat limits."),
                    answer(gpt, 2, "completed", "GPT-5.4 Mini", "openai/gpt-5.4-mini", "Weighing both sources.")]
        for agent in finished:
            delegate(agent)
        expect(quotes).to_have_count(0)
        assert page.evaluate("App.runRegistry.visible()?.status") == "running"
        # A newer report from a model still answering brings it back; the end of the run removes it.
        delegate(answer(gpt, 3, "working", "GPT-5.4 Mini", "openai/gpt-5.4-mini", "Rechecking the price."))
        expect(quotes).to_have_text("GPT-5.4 Mini: Rechecking the price.")
        listed.update(agents=finished, status="succeeded")
        request = page.evaluate("window.__agentRequest")
        bookmark = {"id": request["bookmark_id"], "chat_id": chat, "turn_id": turn, "title": saved["question"],
                    "query": saved["question"], "mode": "Agent", "execution_mode": "agent", "has_consensus": True,
                    "responses": {"consensus": text}}
        bookmarks.append(bookmark)
        push("activity", {**tool, "status": "succeeded"})
        push("delta", {"text": text})
        push("final", {"chat_id": chat, "turn_id": turn, "response": text, "turn": saved, "bookmark_meta": bookmark})
        page.evaluate("() => window.__agentClose()")
        page.wait_for_function("() => App.runRegistry.visible()?.status === 'succeeded'")
        expect(page.locator("#agentAnswerBody")).to_contain_text(text)
        expect(preview).to_be_hidden()
        expect(page.locator("#agentAnswerActivity")).not_to_contain_text("Rechecking the price")

        # Nothing of it is stored: not in browser storage, not in the reopened turn.
        page.reload(wait_until="domcontentloaded")
        assert "Rechecking" not in page.evaluate("() => JSON.stringify({...localStorage, ...sessionStorage})")
        row = page.locator(f'.bookmark[data-id="{bookmark["id"]}"]')
        expect(row).to_have_count(1)
        if width < 1100 and page.locator("#toggleSidebarButton").get_attribute("aria-expanded") != "true":
            page.locator("#toggleSidebarButton").click()
        row.click()
        expect(page.locator("#agentAnswerBody")).to_contain_text(text)
        activity = page.locator("#agentAnswerActivity")
        activity.locator(".agent-activity-title").click()
        expect(activity.locator(".agent-activity-history")).to_be_visible()
        expect(activity).to_contain_text("Compared perspectives")
        expect(activity).not_to_contain_text("Comparing the seat limits")
        expect(activity).not_to_contain_text("Gemini 3.5 Flash-Lite:")
        expect(activity.locator(".agent-progress")).to_be_hidden()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert not errors
    finally:
        context.close()


def test_provisional_marks_while_the_answer_is_checked_then_the_final_review(browser, phase4_server):
    """Coverage windows that are done mark the fixed answer quietly while the
    Differences judge still runs (coverage_preview, since 2026-10-18). Since
    2026-10-21 a provisional mark is neutral: it says that the sentence was
    compared, not how. The final review replaces them in the same frame,
    without a moment without marks, and brings the colours; the saved turn
    shows the saved review alone. Green marks show only under "All checks"
    (the default shows disagreements only)."""
    context, page = _real_firebase_page(browser, phase4_server,
        init_script="localStorage.setItem('consensio.consensusHighlightMode.v1','all')")
    chat, turn = "a" * 32, "b" * 32
    seats, billing = "The smaller plan includes five seats.", "Monthly billing is available on both plans."
    text = f"{seats}\n\n{billing}\n"
    digest = hashlib.sha256(text.encode()).hexdigest()
    answers = [{"provider": p, "provider_label": label, "model": {"model": model, "label": name},
                "text": "Choose the smaller plan; it has five seats and monthly billing.", "sources": []}
               for p, label, model, name in [("openai", "OpenAI", "openai/gpt-5.4-mini", "GPT-5.4 Mini"),
                                             ("gemini", "Gemini", "google/gemini-3.5-flash-lite", "Gemini 3.5 Flash-Lite")]]
    base = {"answer_version": 1, "answer_hash": digest, "versions": [{"id": 1, "text": text, "hash": digest, "status": "required"}],
            "comparisons": [{"id": "c1", "basis_hash": "basis", "question": "Which plan fits a team of five?",
                             "status": "succeeded", "answers": answers}]}

    def supported(anchor, number):
        return {"anchor": anchor, "agree": ["OpenAI", "Gemini"], "dissent": [], "coverage": "supported",
                "sentence_id": number, "anchor_occurrence": 0}

    review = {**base, "status": "succeeded", "checks": [{"comparison_id": "c1", "basis_hash": "basis", "answer_hash": digest,
        "status": "succeeded", "differences_data": {"models_compared": ["Gemini", "OpenAI"],
            "claims": [supported(seats, 1), supported(billing, 2)],
            "agreement": {"score": 72, "coverage_status": "sufficient"},
            "differences": [{"claim": "Whether both plans bill monthly", "consensus_anchor": billing, "type": "contradiction",
                             "severity": "major", "positions": [
                                 {"models": ["OpenAI"], "stance": "Both plans bill monthly.", "quote": "monthly billing"},
                                 {"models": ["Gemini"], "stance": "Only the smaller plan bills monthly.", "quote": "the smaller plan"}]}]}}]}
    saved = {"id": turn, "question": "Which plan fits our team?", "status": "completed", "execution_mode": "agent", "mode": "Agent",
             "consensus": text, "sources": [], "model_answers": {}, "agent_review": review, "agent_activity": [],
             "agent_settings": {"model_id": "claude-haiku-4-5", "label": "Claude Haiku 4.5"}}
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        page.set_viewport_size({"width": 1280, "height": 900})
        page.route("**/user_status", lambda r: _json(r, {"tier": "pro", "is_pro": True, "agent_access": True}))
        page.route("**/agent/models", lambda r: _json(r, CATALOG))
        page.route("**/chats", lambda r: _json(r, {"chat": {"id": chat, "execution_mode": "agent"}}))
        page.route(f"**/agent/chats/{chat}/turns/{turn}/agents", lambda r: _json(r, {"agents": [], "status": "succeeded"}))
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        _choose_mode(page, "agent")
        # A real open stream: each frame reaches the app's SSE parser on its own.
        page.evaluate("""data => {
          const fetch = window.fetch;
          window.fetch = (url, options) => {
            if (String(url) !== '/agent') return fetch(url, options);
            window.__agentRequest = JSON.parse(options.body);
            return Promise.resolve(new Response(new ReadableStream({start(controller) {
              window.__agentPush = (type, event) => controller.enqueue(new TextEncoder().encode(`event: ${type}\\ndata: ${JSON.stringify(event)}\\n\\n`));
              window.__agentClose = () => { try { controller.close(); } catch (_) {} };
              window.__agentPush('started', {chat_id: data.chat, turn_id: data.turn, delegation: false});
            }}), {headers: {'Content-Type': 'text/event-stream'}}));
          };
        }""", {"chat": chat, "turn": turn})
        push = lambda name, event: page.evaluate("([name, event]) => window.__agentPush(name, event)", [name, event])
        page.locator("#questionInput").fill(saved["question"])
        page.locator("#sendButton").click()
        page.wait_for_function("() => typeof window.__agentPush === 'function'")
        body = page.locator("#agentAnswerBody")
        marks = body.locator(".cx-claim")
        push("delta", {"text": text})
        push("review", {"review": {**base, "status": "running", "checks": []}})
        expect(body).to_have_class(re.compile(r"\bis-answer-checking\b"))
        expect(marks).to_have_count(0)

        # The first window is done: its sentence is marked quietly and
        # neutrally, no colour, no count, no score yet.
        preview = {"answer_hash": digest, "comparison_id": "c1", "models_compared": ["Gemini", "OpenAI"], "sentences": 2}
        push("coverage_preview", {**preview, "claims": [supported(seats, 1)], "checked": 1})
        expect(marks).to_have_count(1)
        expect(marks.first).to_have_text(seats)
        expect(marks.first).to_have_class(re.compile(r"\bis-provisional\b.*\bis-mark-arriving\b|\bis-mark-arriving\b.*\bis-provisional\b"))
        expect(marks.first).not_to_have_class(re.compile(r"\bis-(thin|unanimous|minor|split|major)\b"))
        expect(body.locator(".claim-badge")).to_have_count(0)
        expect(marks.first).to_have_css("background-color", "rgba(0, 0, 0, 0)")
        expect(marks.first).to_have_css("text-decoration-style", "dotted")
        expect(body).to_have_class(re.compile(r"\bhas-provisional-marks\b"))
        expect(body).to_have_class(re.compile(r"\bis-answer-checking\b"))
        expect(body).not_to_have_class(re.compile(r"\bis-marks-revealing\b"))
        expect(page.locator("#agentAnswer .agent-agreement")).to_have_count(0)
        # The provisional mark says that it was compared, not how it came out.
        marks.first.hover()
        hover_card = page.locator(".insight-preview")
        expect(hover_card).to_have_text("Compared with 2 model answersThe result appears once the whole answer is checked")
        page.mouse.move(0, 0)

        # The next window: the seen mark stays as it is, the new one fades in.
        push("coverage_preview", {**preview, "claims": [supported(seats, 1), supported(billing, 2)], "checked": 2})
        expect(marks).to_have_count(2)
        expect(marks.first).not_to_have_class(re.compile(r"\bis-mark-arriving\b"))
        expect(marks.nth(1)).to_have_class(re.compile(r"\bis-mark-arriving\b"))

        # Differences is done: the final review takes over in the same frame
        # (never a moment without marks) and brings the colours: the
        # contradiction in red, the score.
        page.evaluate("""() => {
          const body = document.getElementById('agentAnswerBody');
          window.__markGap = false;
          new MutationObserver(() => { if (!body.querySelector('.cx-claim')) window.__markGap = true; })
            .observe(body, {subtree: true, childList: true});
        }""")
        push("review", {"review": review})
        expect(body).not_to_have_class(re.compile(r"\bhas-provisional-marks\b"))
        expect(body).not_to_have_class(re.compile(r"\bis-answer-checking\b"))
        expect(body.locator(".cx-claim.is-major")).to_have_count(1)
        expect(body.locator(".cx-claim.is-major")).to_have_text(billing)
        expect(body.locator(".cx-claim.is-unanimous")).to_have_count(1)
        expect(body.locator(".cx-claim.is-provisional")).to_have_count(0)
        assert page.evaluate("window.__markGap") is False
        expect(page.locator("#agentAnswer .agent-agreement-num")).to_have_text("72")
        # The hand-over leaves no trace once the colours have stroked on.
        expect(body.locator(".was-provisional")).to_have_count(0)

        request = page.evaluate("window.__agentRequest")
        bookmark = {"id": request["bookmark_id"], "chat_id": chat, "turn_id": turn, "title": saved["question"],
                    "query": saved["question"], "mode": "Agent", "execution_mode": "agent", "has_consensus": True}
        push("final", {"chat_id": chat, "turn_id": turn, "response": text, "turn": saved, "bookmark_meta": bookmark})
        page.evaluate("() => window.__agentClose()")
        page.wait_for_function("() => App.runRegistry.visible()?.status === 'succeeded'")
        expect(body.locator(".cx-claim.is-major")).to_have_count(1)

        # The saved turn knows nothing of the preview: the saved review alone.
        page.evaluate("turn => App.runRegistry.showSavedView({type:'bookmark'}, {chatId:'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', turnId:turn.id, executionMode:'agent', question:turn.question, consensus:turn.consensus, currentTurn:turn})", saved)
        expect(body.locator(".cx-claim.is-major")).to_have_count(1)
        expect(body.locator(".cx-claim.is-unanimous")).to_have_count(1)
        expect(body.locator(".is-mark-arriving")).to_have_count(0)
        expect(body).not_to_have_class(re.compile(r"\bhas-provisional-marks\b"))
        assert not errors
    finally:
        context.close()
