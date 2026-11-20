"""Localized progress through the real SSE parser and built app, without paid calls."""
import re

import pytest
from playwright.sync_api import expect

from test_phase4_frontend import phase4_server, _real_firebase_page, _json
from test_agent_chat_frontend import CATALOG, _choose_mode, _detailed_progress, _snapshot


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
        # The trace line by line: each note, step and its motion. Without the
        # correction pass: then the lines give way to the answer's first words
        # (the line that stays for it has its tests in test_agent_audit_frontend.py).
        _detailed_progress(page)
        page.evaluate("() => App.userSettings.set('findings_to_agent', false)")
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
              window.__answerCheck = () => emit('answer_check', {type:'answer_check'});
              window.__finishProgress = (sparse = false) => {
                const response = 'Die erste Option passt zu deinem Budget.';
                window.__tool('review', 'audit_answer', 'succeeded');
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
        expect(preview.locator('.agent-current-status')).to_have_text('Analyzing your message…')
        thinking_details = page.locator('#agentAnswerActivity details')
        thinking_details.locator('.agent-activity-title').click()
        # Before any step: what it does now, then the model it runs on (its
        # default reasoning goes unsaid).
        expect(thinking_details.locator('.agent-activity-current')).to_have_text('Analyzing your message…')
        expect(thinking_details.locator('.agent-activity-run-details')).to_have_text('DeepSeek V4.1 Flash')
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
        expect(title).to_contain_text('Working for')
        page.wait_for_function("() => !document.querySelector('.agent-activity-title').textContent.includes('Working for 0s')")
        assert title.evaluate("el => getComputedStyle(el).animationName") == 'none'
        page.evaluate("() => { window.__firstProgress = document.querySelector('.agent-progress p'); }")
        page.evaluate("() => window.__tool('comparison', 'compare_models', 'succeeded')")
        page.evaluate("text => window.__progress('p2', text)", updates[1])
        page.evaluate("() => window.__tool('review', 'audit_answer', 'running')")
        expect(preview.locator("p")).to_have_text(updates)
        expect(preview.locator(':scope > *')).to_have_text([
            updates[0], 'Compared perspectives', updates[1], 'Reviewing the answer…'])
        expect(preview.locator('.agent-current-status')).to_have_count(1)
        if quiet != 'colors':
            # Current typography uses the same secondary ink for trace and steps.
            trace_color = 'rgb(161, 161, 161)' if dark else 'rgb(94, 94, 94)'
            step_color = trace_color
            colors = preview.locator(':scope > *').evaluate_all('els => els.map(el => getComputedStyle(el).color)')
            assert colors == [trace_color, step_color, trace_color, step_color]
        else:
            assert preview.evaluate("el => getComputedStyle(el).getPropertyValue('--agent-ink').trim()") == 'CanvasText'
            assert preview.evaluate("el => getComputedStyle(el).getPropertyValue('--agent-trace-ink').trim()") == 'CanvasText'
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
        expect(details.locator('.agent-activity-run-details')).to_have_text('DeepSeek V4.1 Flash')
        expect(details.locator(".agent-activity-update")).to_have_text(updates)
        # The steps in the live run's words; the running one is what it does now.
        expect(details.locator('.agent-activity-tool strong')).to_have_text([
            'Compared perspectives', 'Reviewing the answer…'])
        _snapshot(page, f'agent-live-expanded-{snapshot_variant}')
        if quiet != 'colors':
            assert details.locator('.agent-activity-update').first.evaluate('el => getComputedStyle(el).color') == trace_color
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
        # The streamed letters come into view by stream-reveal.js (highlights),
        # not with reduced motion.
        assert page.evaluate("() => App.streamReveal.active()") == (quiet != "reduce")
        page.evaluate("() => window.__answerChunk('passt zu deinem Budget.')")
        expect(page.locator("#agentAnswerBody")).to_have_text("Die erste Option passt zu deinem Budget.")
        # The last word stands and the server announces the check: it shows at
        # once, also in words where the evidence row will stand (the only sign
        # with reduced motion or forced colors).
        check = page.locator("#agentAnswer .agent-check-status")
        expect(check).to_have_count(0)
        page.evaluate("() => window.__answerCheck()")
        expect(check).to_have_text("Reviewing the answer…")
        expect(check).to_be_visible()
        expect(page.locator("#agentAnswerBody")).to_have_class(re.compile(r"\bis-answer-checking\b"))
        body_box, check_box = page.locator("#agentAnswerBody").bounding_box(), check.bounding_box()
        assert check_box["y"] >= body_box["y"] + body_box["height"]
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
        page.evaluate("sparse => window.__finishProgress(sparse)", width == 320)
        expect(page.locator("#agentAnswerBody")).to_have_text("Die erste Option passt zu deinem Budget.")
        expect(check).to_have_count(0)
        expect(page.locator("#agentAnswerBody")).not_to_have_class(re.compile(r"\bis-answer-checking\b"))
        # A history the reader opened stays open on screen: closing it would pull
        # the answer up under the eye. The live paragraphs still give way.
        reader_opened = width != 320
        if reader_opened:
            expect(details).to_have_attribute("open", "")
        else:
            expect(details).not_to_have_attribute("open", "")
        expect(preview).not_to_be_visible()
        expect(preview.locator("p")).to_have_count(0)
        expect(title).to_have_text('Thought for 1m 13s')
        page.evaluate("() => App.agentChat.project(App.runRegistry.visible())")
        expect(title).to_have_text('Thought for 1m 13s')
        if reader_opened:
            expect(details).to_have_attribute("open", "")
        assert page.evaluate("document.querySelector('#agentAnswerActivity')._agentActivity.clockTimer === null")
        # The answer's letters came into view one by one (stream-reveal.js):
        # the body itself does not fade in as a whole.
        assert page.evaluate("__agentMotion.filter(m => m.target.id === 'agentAnswerBody').length") == 0
        if quiet == "none":
            assert page.evaluate("__agentMotion.every(m => m.options.duration <= 220)")
            if width == 320:
                # The lines gave way at once when the answer began, also while
                # the check still ran: no second, animated collapse at the end
                # (they once came back for the check and left again).
                assert not page.evaluate("__agentMotion.some(m => m.target.matches('.agent-progress') && m.frames.at(-1).height === '0px')")
        else:
            assert page.evaluate("__agentMotion.length") == 0
        _snapshot(page, f"agent-progress-final-{snapshot_variant}")
        summary.focus()
        if reader_opened:
            page.keyboard.press("Enter")
            expect(details).not_to_have_attribute("open", "")
        page.keyboard.press("Enter")
        expect(details).to_have_attribute("open", "")
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


@pytest.mark.parametrize("width,dark", [(1280, False), (390, True), (320, False)])
def test_the_calm_line_says_what_the_agent_does_without_its_console(browser, phase4_server, width, dark):
    """Every account starts calm (no console commands by default): one line
    in everyday words, while it thinks its newest thought, the command and its
    output only in the history under the head."""
    context, page = _real_firebase_page(browser, phase4_server)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    command = "cd /home/sprite/game && npm install && npx vite build --mode production"
    try:
        page.set_viewport_size({"width": width, "height": 900})
        page.route("**/user_status", lambda r: _json(r, {"tier": "pro", "is_pro": True, "agent_access": True}))
        page.route("**/agent/models", lambda r: _json(r, CATALOG))
        page.route("**/chats", lambda r: _json(r, {"chat": {"id": "a" * 32, "execution_mode": "agent"}}))
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        page.evaluate("dark => { document.documentElement.classList.toggle('dark-mode', dark); document.body.classList.toggle('dark-mode', dark); }", dark)
        _choose_mode(page, "agent")
        expect(page.locator("#agentModelDropdown")).to_be_enabled()
        page.evaluate("""() => {
          const original = window.fetch;
          window.fetch = async (url, options) => {
            if (url !== '/agent') return original(url, options);
            const encoder = new TextEncoder();
            return new Response(new ReadableStream({ start(controller) {
              window.__emitAgent = event => controller.enqueue(encoder.encode('event: activity\\ndata: ' + JSON.stringify(event) + '\\n\\n'));
              options.signal.addEventListener('abort', () => controller.error(new DOMException('Stopped', 'AbortError')));
            }}), {headers:{'Content-Type':'text/event-stream'}});
          };
        }""")
        page.locator("#questionInput").fill("Build the snake game and test it")
        page.locator("#sendButton").click()
        preview = page.locator("#agentAnswerActivity .agent-progress")
        expect(preview.locator(".agent-current-status")).to_have_text("Analyzing your message…")
        page.wait_for_function("() => !!window.__emitAgent")
        page.evaluate("""() => {
          __emitAgent({version:1, step_id:'completion:1', kind:'reasoning', id:'r1', format:'summary',
            text:'**Planning the build**' + String.fromCharCode(10, 10) + 'The game needs its packages before the first build.', append:true});
          __emitAgent({version:1, step_id:'completion:1', kind:'progress', id:'completion:1/note',
            text:'I build the game first. Then I open it in the browser.'});
        }""")
        status = preview.locator(".agent-current-status")
        # One line (a thin thought under the status did not fit): while it
        # thinks, the line is its newest thought; the
        # note may follow the summary's heading by a moment, which then stands
        # its four seconds first.
        expect(status).to_have_text("I build the game first.", timeout=8000)
        page.evaluate("""command => {
          __emitAgent({version:1, step_id:'completion:1', kind:'tool', id:'c1', name:'vm_exec', status:'running',
            command, started_at:new Date().toISOString(),
            output:'added 212 packages in 9s' + String.fromCharCode(10) + 'vite v7.1.2 building for production...'});
        }""", command)
        # The note stands its seconds, then the running step takes the line.
        expect(status).to_have_text("Working in the workspace…", timeout=8000)
        # Nothing under it, nothing of the console in the live lines.
        expect(preview.locator(".agent-progress-thought")).to_have_count(0)
        expect(preview.locator(":scope > *")).to_have_count(1)
        expect(preview.locator(".agent-vm, code, pre, .agent-vm-fold")).to_have_count(0)
        expect(preview).not_to_contain_text("npm")
        expect(preview).not_to_contain_text("vite")
        # Past the lines' own motion (the sheen and the dots run on as CSS).
        page.wait_for_function("""() => document.getElementById('agentAnswerActivity').getAnimations({subtree:true})
          .filter(a => !(a instanceof CSSAnimation)).every(a => a.playState !== 'running')""")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
        _snapshot(page, f"agent-calm-live-{width}-{'dark' if dark else 'light'}")
        # The history under the head has the command, a click away.
        page.locator("#agentAnswerActivity .agent-activity-title").click()
        history = page.locator("#agentAnswerActivity .agent-activity-history")
        expect(history.locator(".agent-vm-target")).to_have_text(command)
        expect(history).to_contain_text("I build the game first. Then I open it in the browser.")
        expect(preview).not_to_be_visible()
        page.locator("#agentAnswerActivity .agent-activity-title").click()
        # A file by its name, held a moment so the line never flashes.
        page.evaluate("""() => {
          __emitAgent({version:1, step_id:'completion:1', kind:'tool', id:'c1', name:'vm_exec', status:'succeeded',
            exit_code:0, duration_ms:9000});
          __emitAgent({version:1, step_id:'completion:2', kind:'tool', id:'c2', name:'vm_write_file', status:'running',
            path:'/home/sprite/game/src/snake.js'});
        }""")
        expect(status).to_have_text("Writing “snake.js”…")
        expect(preview).not_to_contain_text("/home/sprite")
        assert not errors
    finally:
        context.close()


@pytest.mark.parametrize("quiet", ["none", "reduce"])
def test_the_first_seconds_after_send_show_life_before_the_model_speaks(browser, phase4_server, quiet):
    """From the click on Send the line says what happens to the message and
    moves: its mark breathes, and rests with reduced motion. It stays while
    the server takes seconds to answer (no word about the transport after
    it); "Thinking…" comes only once the model has shown a sign of its own."""
    context, page = _real_firebase_page(browser, phase4_server)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        page.set_viewport_size({"width": 1280, "height": 900})
        page.emulate_media(reduced_motion="reduce" if quiet == "reduce" else "no-preference")
        page.route("**/user_status", lambda r: _json(r, {"tier": "pro", "is_pro": True, "agent_access": True}))
        page.route("**/agent/models", lambda r: _json(r, CATALOG))
        page.route("**/chats", lambda r: _json(r, {"chat": {"id": "a" * 32, "execution_mode": "agent"}}))
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        _choose_mode(page, "agent")
        expect(page.locator("#agentModelDropdown")).to_be_enabled()
        # The server's answer waits for the test, as on a slow connection.
        page.evaluate("""() => {
          const original = window.fetch;
          window.fetch = async (url, options) => {
            if (url !== '/agent') return original(url, options);
            await new Promise(resolve => { window.__serverAnswers = resolve; });
            const encoder = new TextEncoder();
            return new Response(new ReadableStream({ start(controller) {
              window.__emitAgent = event => controller.enqueue(encoder.encode('event: activity\\ndata: ' + JSON.stringify(event) + '\\n\\n'));
              options.signal.addEventListener('abort', () => controller.error(new DOMException('Stopped', 'AbortError')));
            }}), {headers:{'Content-Type':'text/event-stream'}});
          };
        }""")
        page.locator("#questionInput").fill("Is a heat pump worth it in an old building?")
        page.locator("#sendButton").click()
        status = page.locator("#agentAnswerActivity .agent-progress .agent-current-status")
        expect(status).to_have_text("Analyzing your message…")
        expect(page.locator("#agentAnswerActivity .agent-activity-title")).to_contain_text("Working for")
        breathing = status.evaluate("el => getComputedStyle(el, '::before').animationName")
        assert breathing == ("none" if quiet == "reduce" else "activity-dot-breathe")
        page.wait_for_function("() => !!window.__serverAnswers")
        # Seconds without the server's answer change nothing.
        page.wait_for_timeout(3500)
        expect(status).to_have_text("Analyzing your message…")
        page.evaluate("() => window.__serverAnswers()")
        expect(status).to_have_text("Analyzing your message…")
        # The model's first sign: a pause from here on is its thinking.
        page.wait_for_function("() => !!window.__emitAgent")
        page.evaluate("""() => __emitAgent({version:1, step_id:'completion:0', kind:'reasoning', id:'r1',
          format:'summary', text:'Checking the assumptions.', append:true})""")
        expect(status).to_have_text("Thinking…")
        expect(page.locator("#agentAnswerActivity .agent-progress > *")).to_have_count(1)
        assert not errors
    finally:
        context.close()


# The end of an answer nobody reviewed (reviewers off), over window.fetch in
# the provider's rhythm: uneven bundles of words, then the final frame while
# the last of them still come into view.
ENDING_TEXT = (
    "Bayern play their last first-half match away at Eintracht Frankfurt "
    "([kicker.de](https://www.kicker.de/bundesliga/spieltag)). Kick-off is on Saturday evening "
    "([bundesliga.com](https://www.bundesliga.com/de/bundesliga/spieltag)).\n\n"
    "Two home matches come before it, against Wolfsburg and Union Berlin. The exact times are in the league's "
    "schedule ([dfl.de](https://www.dfl.de/de/spielplan)).\n\n"
    "The short winter break lies between the two matchdays, and the second half starts the weekend after.\n\n"
    "Calendar of fixed dates ([dfb.de](https://www.dfb.de/rahmenterminkalender))"
)
ENDING_SOURCES = [{"url": "https://www.kicker.de/bundesliga/spieltag", "title": "kicker"},
                  {"url": "https://www.bundesliga.com/de/bundesliga/spieltag", "title": "Bundesliga"},
                  {"url": "https://www.dfl.de/de/spielplan", "title": "DFL"},
                  {"url": "https://www.dfb.de/rahmenterminkalender", "title": "DFB"}]
ENDING_STREAM = """plan => {
  const real = window.fetch.bind(window);
  window.fetch = (input, init = {}) => {
    const url = typeof input === 'string' ? input : input.url;
    if (new URL(url, location.href).pathname !== '/agent' || init.method !== 'POST') return real(input, init);
    const request = JSON.parse(init.body);
    const encoder = new TextEncoder();
    let seq = 0;
    const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
    const body = new ReadableStream({ async start(controller) {
      const send = (kind, data) => controller.enqueue(encoder.encode(`id: ${++seq}\\nevent: ${kind}\\ndata: ${JSON.stringify(data)}\\n\\n`));
      controller.enqueue(encoder.encode(':' + ' '.repeat(2045) + '\\n\\n'));
      send('accepted', { chat_id: plan.chat, turn_id: plan.turn });
      await wait(200);
      const sizes = [38, 61, 24, 83, 47, 19, 72, 55, 33, 90], gaps = [70, 140, 40, 210, 90, 60, 180, 110, 50, 240];
      for (let at = 0, index = 0; at < plan.text.length; at += sizes[index % 10], index += 1) {
        await wait(gaps[index % 10]);
        send('delta', { type: 'delta', text: plan.text.slice(at, at + sizes[index % 10]) });
      }
      await wait(120);
      const review = { mode: 'audit', status: 'off', answer_version: 1, answer_hash: 'h1', comparisons: [],
        versions: [{ id: 1, text: plan.text, hash: 'h1', status: 'off', comparison_ids: [] }],
        audit: { reviewers: [], setting: 'off' } };
      const turn = { id: plan.turn, turn_id: plan.turn, question: request.question, status: 'completed', position: 1,
        mode: 'Agent', execution_mode: 'agent', consensus: plan.text, differences: '', differences_data: null,
        model_answers: {}, sources: plan.sources, agent_activity: [], agent_review: review };
      send('final', { chat_id: plan.chat, turn_id: plan.turn, response: plan.text, turn,
        bookmark_meta: { id: request.bookmark_id, title: request.question, query: request.question, mode: 'Agent', has_consensus: true } });
      controller.close();
    } });
    return Promise.resolve(new Response(body, { status: 200, headers: { 'Content-Type': 'text/event-stream' } }));
  };
}"""
# Every frame that differs from the one before: how much of the answer
# stands, each source pill's opacity, and where the row under it is.
ENDING_FRAMES = """() => {
  window.__ending = [];
  let last = '';
  const frame = () => {
    const body = document.getElementById('agentAnswerBody');
    const row = document.querySelector('#agentAnswer .agent-review:not([hidden])');
    const state = { chars: body.textContent.length,
      pills: [...body.querySelectorAll('.src-ref')].map(pill => Number(getComputedStyle(pill).opacity)),
      row: row ? Math.round(row.getBoundingClientRect().top * 10) / 10 : null,
      bottom: Math.round(body.getBoundingClientRect().bottom * 10) / 10 };
    const key = JSON.stringify(state);
    if (key !== last) { last = key; window.__ending.push(state); }
    requestAnimationFrame(frame);
  };
  requestAnimationFrame(frame);
}"""


def test_the_row_under_an_answer_comes_after_its_last_word_and_no_pill_goes_out(browser, phase4_server):
    """The run ends while the answer's last words still come into view at
    their pace (stream-reveal.js). The row under it (sources, Copy, Watch,
    Share, the review's state) waits for them: it never stands over words
    still to come, no source pill that stood goes out when it is placed, and
    from then on neither the row nor the answer moves."""
    context, page = _real_firebase_page(browser, phase4_server)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        page.set_viewport_size({"width": 1280, "height": 900})
        page.route("**/user_status", lambda r: _json(r, {"tier": "pro", "is_pro": True, "agent_access": True}))
        page.route("**/agent/models", lambda r: _json(r, CATALOG))
        page.route("**/chats", lambda r: _json(r, {"chat": {"id": "a" * 32, "execution_mode": "agent"}}))
        page.route("**/bookmarks/**", lambda r: _json(r, {"bookmark": {}}))
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        _choose_mode(page, "agent")
        expect(page.locator("#agentModelDropdown")).to_be_enabled()
        page.evaluate("() => App.userSettings.set('reviewers', 'off')")
        assert page.evaluate("() => App.streamReveal.active()")
        page.evaluate(ENDING_STREAM, {"chat": "a" * 32, "turn": "1".rjust(32, "0"), "text": ENDING_TEXT,
                                      "sources": ENDING_SOURCES})
        page.locator("#questionInput").fill("When is Bayern's last match of the first half?")
        page.locator("#sendButton").click()
        expect(page.locator("#agentAnswerBody")).not_to_be_empty()
        page.evaluate(ENDING_FRAMES)
        page.wait_for_function("() => App.runRegistry.visible()?.status === 'succeeded'", timeout=60000)
        row = page.locator("#agentAnswer .agent-review")
        expect(row.locator(".agent-review-status")).to_have_text("Not reviewed · reviewers off")
        expect(row.locator('.agent-evidence-link[data-section="sources"]')).to_have_accessible_name("Sources 4")
        expect(row.locator(":is(.agent-copy-pill, .agent-watch-pill, .agent-share-pill)")).to_have_count(3)
        # Past the row's fade and the last letters' light.
        page.wait_for_timeout(1200)
        frames = page.evaluate("() => window.__ending")
        whole = frames[-1]["chars"]
        with_row = [frame for frame in frames if frame["row"] is not None]
        assert with_row and with_row[0] is not frames[0], frames[:3]
        # Never over words still to come.
        assert {frame["chars"] for frame in with_row} == {whole}, [(f["chars"], f["row"]) for f in frames[-8:]]
        # Placed once, where it stays; the answer above it stays too.
        assert len({frame["row"] for frame in with_row}) == 1, [f["row"] for f in with_row]
        assert len({frame["bottom"] for frame in with_row}) == 1, [f["bottom"] for f in with_row]
        # A pill that stood never goes out again (the review sets them anew
        # when the row is placed).
        stood = 0
        for frame in frames:
            assert all(opacity == 1 for opacity in frame["pills"][:stood]), frame
            while stood < len(frame["pills"]) and frame["pills"][stood] == 1:
                stood += 1
        assert stood == len(ENDING_SOURCES), frames[-1]
        assert not errors
    finally:
        context.close()
