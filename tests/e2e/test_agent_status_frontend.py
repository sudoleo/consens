"""Localized progress through the real SSE parser and built app, without paid calls."""
import pytest
from playwright.sync_api import expect

from test_phase4_frontend import phase4_server, _real_firebase_page, _json
from test_agent_chat_frontend import CATALOG, _choose_mode, _snapshot


@pytest.mark.parametrize("width,dark,quiet", [(1280, False, "none"), (390, True, "none"),
    (320, False, "none"), (390, True, "reduce"), (320, False, "colors"), (390, True, "colors")])
def test_progress_paragraphs_collapse_at_final_and_reopen_with_keyboard(browser, phase4_server, width, dark, quiet):
    context, page = _real_firebase_page(browser, phase4_server)
    snapshot_variant = f"{width}-{'dark' if dark else 'light'}-{quiet}"
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    updates = ["Ich vergleiche die Optionen mit deinem Budget von 100 Euro.",
               "Die Antworten nennen dieselbe Preisgrenze. Ich prüfe, ob die Empfehlung ausreichend belegt ist."]
    try:
        page.set_viewport_size({"width": width, "height": 900})
        page.emulate_media(reduced_motion="reduce" if quiet == "reduce" else "no-preference",
                           forced_colors="active" if quiet == "colors" else "none")
        page.route("**/user_status", lambda r: _json(r, {"tier": "pro", "is_pro": True, "agent_access": True}))
        page.route("**/agent/models", lambda r: _json(r, CATALOG))
        page.route("**/chats", lambda r: _json(r, {"chat": {"id": "a" * 32, "execution_mode": "agent"}}))
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        page.evaluate("dark => { document.documentElement.classList.toggle('dark-mode', dark); document.body.classList.toggle('dark-mode', dark); }", dark)
        _choose_mode(page, "agent")
        expect(page.locator("#agentModelDropdown")).to_be_enabled()
        page.evaluate("""updates => {
          window.__agentMotion = [];
          const animate = Element.prototype.animate;
          Element.prototype.animate = function(frames, options) {
            const animation = animate.call(this, frames, options);
            if (this.closest('#agentAnswer')) window.__agentMotion.push({target:this, frames, options, animation});
            return animation;
          };
          const original = window.fetch;
          window.fetch = async (url, options) => {
            if (url !== '/agent') return original(url, options);
            const encoder = new TextEncoder(), events = new Map();
            return new Response(new ReadableStream({start(controller) {
              const emit = (type, event) => controller.enqueue(encoder.encode('event: ' + type + '\\ndata: ' + JSON.stringify(event) + '\\n\\n'));
              window.__progress = (id, text) => {
                const event = {version:1, step_id:'completion:0', kind:'progress', id, text};
                events.set(id, event); emit('activity', event);
              };
              window.__tool = (id, name, status) => {
                const event = {version:1, step_id:'completion:0', kind:'tool', id, name, status};
                events.set(id, event); emit('activity', event);
              };
              window.__startProgress = () => {
                window.__progress('p1', updates[0]);
                window.__tool('comparison', 'compare_models', 'running');
              };
              window.__answerChunk = text => emit('delta', {text});
              window.__finishProgress = (sparse = false) => {
                const response = 'Die erste Option passt zu deinem Budget.';
                window.__tool('judge', 'judge_answer', 'succeeded');
                emit('final', {response, chat_id:'a'.repeat(32), turn_id:'b'.repeat(32),
                  turn:{id:'b'.repeat(32), status:'completed', execution_mode:'agent', consensus:response,
                    created_at:'2026-09-20T10:00:00Z', completed_at:'2026-09-20T10:01:13Z',
                    agent_activity:[...events.values()].filter(e => !sparse || e.kind !== 'progress'),
                    agent_usage:{input_tokens:500,output_tokens:100}}});
                controller.close();
              };
              options.signal.addEventListener('abort', () => controller.error(new DOMException('Stopped', 'AbortError')));
            }}), {headers:{'Content-Type':'text/event-stream'}});
          };
        }""", updates)
        page.locator("#questionInput").fill("Welche Option passt zu meinem Budget von 100 Euro?")
        page.locator("#sendButton").click()
        preview = page.locator("#agentAnswerActivity .agent-progress")
        expect(preview.locator('.agent-current-status')).to_have_text('Thinking…')
        thinking_details = page.locator('#agentAnswerActivity details')
        thinking_details.locator('.agent-activity-title').click()
        expect(thinking_details.locator('.agent-activity-run-details')).to_be_visible()
        expect(thinking_details.locator('.agent-activity-run-details')).to_contain_text('DeepSeek V4.1 Flash')
        expect(thinking_details.locator('.agent-activity-run-details')).to_contain_text('Thinking…')
        expect(thinking_details.locator('.agent-activity-run-details')).to_contain_text('Model default')
        page.wait_for_function("""() => {
          const host = document.getElementById('agentAnswerActivity');
          return getComputedStyle(host.querySelector('.agent-activity-history')).opacity === '1'
            && host.getAnimations().every(a => a.playState !== 'running');
        }""")
        _snapshot(page, f'agent-thinking-expanded-{snapshot_variant}')
        thinking_details.locator('.agent-activity-title').click()
        expect(thinking_details).not_to_have_attribute('open', '')
        page.wait_for_function("() => typeof window.__startProgress === 'function'")
        page.evaluate('() => window.__startProgress()')
        expect(preview.locator("p")).to_have_text(updates[:1])
        expect(preview.locator('.agent-current-status')).to_have_text('Comparing perspectives…')
        title = page.locator('#agentAnswerActivity .agent-activity-title')
        expect(title).to_contain_text('Duration:')
        page.wait_for_function("() => !document.querySelector('.agent-activity-title').textContent.includes('Duration: 0s')")
        assert title.evaluate("el => getComputedStyle(el).animationName") == 'none'
        page.evaluate("() => { window.__firstProgress = document.querySelector('.agent-progress p'); }")
        page.evaluate("() => window.__tool('comparison', 'compare_models', 'succeeded')")
        page.evaluate("text => window.__progress('p2', text)", updates[1])
        page.evaluate("() => window.__tool('judge', 'judge_answer', 'running')")
        expect(preview.locator("p")).to_have_text(updates)
        expect(preview.locator(':scope > *')).to_have_text([
            updates[0], 'Compared perspectives', updates[1], 'Checking the answer…'])
        expect(preview.locator('.agent-current-status')).to_have_count(1)
        if quiet != 'colors':
            colors = preview.locator(':scope > *').evaluate_all('els => els.map(el => getComputedStyle(el).color)')
            assert colors == ['rgb(255, 255, 255)' if dark else 'rgb(0, 0, 0)'] * 4
        else:
            assert preview.evaluate("el => getComputedStyle(el).getPropertyValue('--agent-ink').trim()") == 'CanvasText'
        expect(preview).to_be_visible()
        first, second = [p.bounding_box() for p in preview.locator("p").all()]
        assert second["y"] >= first["y"] + first["height"] + 12
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
        expect(page.locator("#agentAnswerBody")).to_be_empty()
        counts = page.evaluate("""() => ({first:__agentMotion.filter(m => m.target === __firstProgress).length,
          updates:__agentMotion.filter(m => m.target.matches('.agent-progress p')).length})""")
        assert counts == ({"first": 1, "updates": 2} if quiet == "none" else {"first": 0, "updates": 0})
        page.evaluate("() => { window.__motionCount = __agentMotion.length; App.agentChat.project(App.runRegistry.visible()); }")
        assert page.evaluate("__agentMotion.length === __motionCount")
        _snapshot(page, f"agent-progress-live-{snapshot_variant}")
        summary = page.locator("#agentAnswerActivity summary")
        summary.focus()
        page.keyboard.press("Enter")
        details = page.locator("#agentAnswerActivity details")
        expect(details).to_have_attribute("open", "")
        expect(preview).not_to_be_visible()
        expect(details.locator('.agent-activity-run-details')).to_contain_text('DeepSeek V4.1 Flash')
        expect(details.locator('.agent-activity-run-details')).to_contain_text('Checking the answer…')
        expect(details.locator(".agent-activity-update")).to_have_text(updates)
        expect(details.locator('.agent-activity-tool strong')).to_have_text([
            'Model comparison · Completed', 'Answer review · Working…'])
        _snapshot(page, f'agent-live-expanded-{snapshot_variant}')
        if quiet != 'colors':
            assert details.locator('.agent-activity-update').first.evaluate('el => getComputedStyle(el).color') == (
                'rgb(255, 255, 255)' if dark else 'rgb(0, 0, 0)')
        # Exercise rapid reversal without leaving a frozen height or a stale close callback.
        page.evaluate("""() => {
          const summary = document.querySelector('#agentAnswerActivity summary');
          summary.click(); summary.click();
        }""")
        expect(details).to_have_attribute("open", "")
        if width == 320:
            summary.click()
            expect(details).not_to_have_attribute("open", "")
            expect(preview).to_be_visible()
        page.evaluate("() => window.__answerChunk('Die erste Option ')")
        expect(page.locator("#agentAnswerBody")).to_contain_text("Die erste Option")
        page.evaluate("() => window.__answerChunk('passt zu deinem Budget.')")
        expect(page.locator("#agentAnswerBody")).to_have_text("Die erste Option passt zu deinem Budget.")
        page.evaluate("sparse => window.__finishProgress(sparse)", width == 320)
        expect(page.locator("#agentAnswerBody")).to_have_text("Die erste Option passt zu deinem Budget.")
        expect(details).not_to_have_attribute("open", "")
        expect(preview).not_to_be_visible()
        expect(preview.locator("p")).to_have_count(0)
        expect(title).to_have_text('Duration: 1m 13s')
        page.evaluate("() => App.agentChat.project(App.runRegistry.visible())")
        expect(title).to_have_text('Duration: 1m 13s')
        assert page.evaluate("document.querySelector('#agentAnswerActivity')._agentActivity.clockTimer === null")
        assert page.evaluate("__agentMotion.filter(m => m.target.id === 'agentAnswerBody').length") == (1 if quiet == "none" else 0)
        if quiet == "none":
            assert page.evaluate("__agentMotion.every(m => m.options.duration <= 220)")
            if width == 320:
                assert page.evaluate("__agentMotion.some(m => m.target.matches('.agent-progress') && m.frames.at(-1).opacity === 0 && m.frames.at(-1).height === '0px')")
        else:
            assert page.evaluate("__agentMotion.length") == 0
        _snapshot(page, f"agent-progress-final-{snapshot_variant}")
        summary.focus()
        page.keyboard.press("Enter")
        expect(details.locator(".agent-activity-update")).to_have_text(updates)
        expect(details.locator(".agent-activity-update").first).to_be_visible()
        page.wait_for_function("""() => {
          const history = document.querySelector('.agent-activity-history');
          return getComputedStyle(history).opacity === '1' && history.getBoundingClientRect().height > 0;
        }""")
        assert details.locator(".agent-activity-content").evaluate("el => el.scrollHeight <= el.clientHeight + 1")
        if quiet == "none":
            # A changed OS preference also completes a transition already underway.
            page.emulate_media(reduced_motion="reduce")
            page.wait_for_function("() => __agentMotion.every(m => m.animation.playState !== 'running')")
        assert page.locator('#agentAnswerActivity').evaluate("el => el.style.height") == ""
        _snapshot(page, f"agent-progress-history-{snapshot_variant}")
        page.evaluate("""() => {
          const basis = App.runRegistry.getSelectedConversationBasis();
          App.runRegistry.showSavedView({type:'bookmark'}, basis);
        }""")
        summary.click()
        expect(details.locator('.agent-activity-update')).to_have_text(updates)
        expect(details.locator('.agent-activity-update').first).to_be_visible()
        assert not errors
    finally:
        context.close()
