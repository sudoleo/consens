"""Real built chat: send, stream, reading interruption and view ownership."""
from pathlib import Path
import pytest
from playwright.sync_api import expect
from test_phase4_frontend import phase4_server, _real_firebase_page, _json
from test_agent_chat_frontend import CATALOG, _choose_mode


@pytest.mark.parametrize('width,history_open,at_end,reduced', [
    (1440, False, False, False), (1440, True, True, False),
    (390, False, True, False), (390, True, False, False), (320, False, False, True),
])
def test_agent_review_and_completion_keep_visible_answer_still(browser, phase4_server, width, history_open, at_end, reduced):
    context, page = _real_firebase_page(browser, phase4_server)
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    try:
        page.set_viewport_size({'width': width, 'height': 800})
        page.emulate_media(reduced_motion='reduce' if reduced else 'no-preference')
        page.route('**/user_status', lambda r: _json(r, {'tier': 'pro', 'is_pro': True, 'agent_access': True}))
        page.route('**/agent/models', lambda r: _json(r, CATALOG))
        page.evaluate("async () => { await __switchE2EUser('account-a'); }")
        _choose_mode(page, 'agent')
        page.evaluate("""() => {
          window.__fixedAnswer = Array.from({length:45}, (_, i) =>
            `Paragraph ${i}. This is the completed answer. Its checked text must remain readable while the progress area changes.`).join('\\n\\n');
          window.__stableRun = App.runRegistry.create({question:'Compare the alternatives', config:{executionMode:'agent'}});
          App.runRegistry.update(__stableRun.runId, run => {
            run.status = 'running'; run.phase = 'answers'; run.consensus.status = 'streaming';
            run.consensus.streamText = __fixedAnswer;
            run.metadata.agentActivity = [
              {id:'progress', kind:'progress', text:'I compare the alternatives and examine their different assumptions.'},
              {id:'comparison', kind:'tool', name:'compare_models', status:'succeeded'},
              {id:'writing', kind:'status', status:'responding'},
            ];
          });
          App.composer.collapse({force:true});
        }""")
        expect(page.locator('#agentAnswerBody p')).to_have_count(45)
        if history_open:
            page.locator('#agentAnswerActivity summary').click()
        page.wait_for_timeout(400)
        if at_end:
            page.evaluate('() => App.chatScroll.latest()')
            page.wait_for_function('() => document.documentElement.scrollHeight - innerHeight - scrollY < 3')
        else:
            page.evaluate("""() => {
              dispatchEvent(new WheelEvent('wheel', {deltaY:-100}));
              document.querySelectorAll('#agentAnswerBody p')[20].scrollIntoView({block:'center', behavior:'instant'});
            }""")
        page.wait_for_timeout(500)
        page.evaluate("""atEnd => {
          const paragraphs = document.querySelectorAll('#agentAnswerBody p');
          window.__readingIndex = atEnd ? paragraphs.length - 1 : 20;
          window.__readingText = paragraphs[__readingIndex].textContent;
          window.__readingTop = () => {
            const node = document.querySelectorAll('#agentAnswerBody p')[__readingIndex];
            if (!node || node.textContent !== __readingText) throw new Error('Reading paragraph disappeared or changed');
            return node.getBoundingClientRect().top;
          };
        }""", at_end)
        assert page.locator('#agentAnswerActivity').bounding_box()['y'] + page.locator('#agentAnswerActivity').bounding_box()['height'] < 0
        for stage in ['review', 'checked', 'finished', 'late_usage']:
            samples = page.evaluate("""stage => new Promise(resolve => {
              const samples = [__readingTop()];
              App.runRegistry.update(__stableRun.runId, run => {
                if (stage === 'review') run.metadata.agentActivity.push(
                  {id:'review-progress', kind:'progress', text:'The models disagree on some assumptions. I check the answer against the available comparison results.'},
                  {id:'judge', kind:'tool', name:'judge_answer', status:'running'});
                if (stage === 'checked') run.metadata.agentActivity.find(e => e.id === 'judge').status = 'succeeded';
                if (stage === 'finished') {
                  run.consensus.text = run.consensus.streamText;
                  run.consensus.status = 'complete'; run.phase = 'done';
                }
                if (stage === 'late_usage') run.metadata.agentUsage = {input_tokens:500, output_tokens:100};
              });
              if (stage === 'finished') App.runRegistry.setStatus(__stableRun.runId, 'succeeded');
              const start = performance.now();
              function sample() {
                samples.push(__readingTop());
                if (performance.now() - start < 550) requestAnimationFrame(sample);
                else resolve(samples);
              }
              requestAnimationFrame(sample);
            })""", stage)
            assert max(samples) - min(samples) < 3, (stage, samples)
        expect(page.locator('#agentAnswerActivity details')).not_to_have_attribute('open', '')
        expect(page.locator('#agentAnswerActivity .agent-progress')).not_to_be_visible()
        assert page.locator('#agentAnswerBody').inner_text() == page.evaluate('__fixedAnswer')
        assert not errors
    finally:
        context.close()


@pytest.mark.parametrize("width,reduced", [(1280, False), (390, False), (390, True)])
def test_agent_send_brings_the_question_to_the_top_and_streaming_never_moves_the_reader(browser, phase4_server, width, reduced):
    context, page = _real_firebase_page(browser, phase4_server)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        page.set_viewport_size({"width": width, "height": 800})
        page.emulate_media(reduced_motion="reduce" if reduced else "no-preference")
        page.route("**/user_status", lambda r: _json(r, {"tier": "pro", "is_pro": True, "agent_access": True, "limit": 500}))
        page.route("**/usage", lambda r: _json(r, {"tier": "pro", "is_pro": True, "remaining": 500, "total_limit": 500}))
        page.route("**/api/my/memory", lambda r: _json(r, {"memory": {"content": "", "revision": 0}}))
        page.route("**/chats", lambda r: _json(r, {"chat": {"id": "a" * 32, "execution_mode": "agent"}}))
        page.route("**/agent/models", lambda r: _json(r, CATALOG))
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        _choose_mode(page, "agent")
        page.evaluate("""() => {
          window.__replyCount = 0;
          window.streamSSERequest = async (_url, body, signal, handlers) => {
            if (window.__replyCount++) {
              window.__streamHandlers = handlers;
              return new Promise((resolve, reject) => signal.addEventListener('abort', () => reject(new DOMException('Stopped', 'AbortError')), {once:true}));
            }
            const text = Array.from({length:45}, (_, i) => `Paragraph ${i}. An earlier answer with enough material to read.`).join('\\n\\n');
            handlers.delta.append(text);
            return {ok:true, data:{chat_id:'a'.repeat(32), turn_id:'b'.repeat(32), response:text,
              turn:{id:'b'.repeat(32), question:body.question, consensus:text, status:'completed', execution_mode:'agent', sources:[], model_answers:{},
                agent_settings:{model_id:body.model_id,label:'DeepSeek V4.1 Flash'}},
              bookmark_meta:{id:body.bookmark_id,title:body.question,query:body.question,mode:'Agent',has_consensus:true}}};
          };
          window.__askTop = () => document.getElementById('threadAsk').getBoundingClientRect().top;
        }""")
        page.locator("#questionInput").fill("First message")
        page.locator("#sendButton").click()
        page.wait_for_function("() => App.runRegistry.visible()?.status === 'succeeded'")
        page.wait_for_timeout(500)
        # The first question already stands at the top: nothing scrolled, nothing followed the answer.
        assert page.evaluate("scrollY") < 3
        landing = page.evaluate("__askTop()")
        assert 0 < landing < 120

        # A new message brings its question to the top, even from old history.
        page.mouse.move(width // 2, 200)
        page.mouse.wheel(0, 900)
        page.wait_for_timeout(300)
        page.evaluate("""() => { const input = document.getElementById('questionInput'); input.value = 'Next message';
          window.__sending = App.agentChat.send(); }""")
        page.wait_for_function("() => !!window.__streamHandlers")
        page.wait_for_function(f"() => scrollY > 500 && Math.abs(__askTop() - {landing}) < 3")
        assert page.evaluate("document.getElementById('threadAskText').textContent").startswith("Next message")
        before = page.evaluate("scrollY")
        page.evaluate("__streamHandlers.delta.append(Array.from({length:35}, (_, i) => `New answer ${i}. Text for the current turn.`).join('\\n\\n'))")
        page.wait_for_function("() => document.getElementById('agentAnswerBody').textContent.includes('New answer 34')")
        page.wait_for_timeout(600)  # A full animation interval must not move the reader.
        assert abs(page.evaluate("scrollY") - before) < 3
        assert abs(page.evaluate("__askTop()") - landing) < 3

        latest = page.locator(".chat-scroll-latest")
        expect(latest).to_be_visible()
        box = latest.bounding_box()
        assert 0 <= box["x"] and box["x"] + box["width"] <= width
        capture = Path("test-results/chat-scroll")
        capture.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(capture / f"question-top-{width}-{reduced}.png"))
        # "Latest message" goes to the end as it was when pressed; text that
        # still lands during the jump may leave it within the near-end band.
        # The eased jump enters that band before it ends, so wait for the
        # jump itself to finish before measuring stillness.
        await_bottom = """() => document.documentElement.scrollHeight - innerHeight - scrollY < 81
          && !document.body.classList.contains('chat-scroll-following')"""
        latest.click()
        page.wait_for_function(await_bottom)
        expect(latest).not_to_be_visible()
        if width < 1100:
            assert page.evaluate("document.activeElement.id !== 'questionInput'")
        # Reaching the end does not resume following.
        before = page.evaluate("scrollY")
        page.evaluate("__streamHandlers.delta.append('\\n\\n' + 'Additional material.\\n\\n'.repeat(20))")
        page.wait_for_timeout(600)
        assert abs(page.evaluate("scrollY") - before) < 3
        expect(latest).to_be_visible()
        # The jump keeps the end it was pressed for; on a slow runner the text
        # was still landing then and ran past the near-end band (nightly
        # 2026-10-28). Press once all of it is there.
        page.wait_for_function("() => document.getElementById('agentAnswerBody').textContent.split('Additional material.').length > 20")
        latest.focus()
        latest.press("Enter")
        page.wait_for_function(await_bottom)
        expect(page.locator("#questionInput")).to_be_focused()

        page.evaluate("App.runRegistry.clearVisible()")
        before = page.evaluate("scrollY")
        page.evaluate("__streamHandlers.delta.append('\\n\\nA late background message.')")
        page.wait_for_timeout(500)
        assert abs(page.evaluate("scrollY") - before) < 3
        expect(latest).not_to_be_visible()
        assert not errors
    finally:
        context.close()


# A later question stands at the end of the page. The live lines are 20.8px
# tall and grow in a height motion; with a reserve in whole pixels the end of
# the page followed their fraction, and whenever it rounded a pixel lower the
# browser pulled the chat 1px down, and back with the next line (2026-10-29,
# Max: the chat jiggled as reasoning came in).
@pytest.mark.parametrize("width,height,scale", [(1280, 900, 1), (1536, 730, 1.25), (390, 800, 3)])
def test_reasoning_lines_at_the_end_of_the_page_keep_the_chat_still(browser, phase4_server, width, height, scale):
    class Scaled:
        def new_context(self, **options):
            return browser.new_context(device_scale_factor=scale, **options)

    context, page = _real_firebase_page(Scaled(), phase4_server)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        page.set_viewport_size({"width": width, "height": height})
        page.emulate_media(reduced_motion="no-preference")
        page.route("**/user_status", lambda r: _json(r, {"tier": "pro", "is_pro": True, "agent_access": True, "limit": 500}))
        page.route("**/usage", lambda r: _json(r, {"tier": "pro", "is_pro": True, "remaining": 500, "total_limit": 500}))
        page.route("**/api/my/memory", lambda r: _json(r, {"memory": {"content": "", "revision": 0}}))
        page.route("**/chats", lambda r: _json(r, {"chat": {"id": "a" * 32, "execution_mode": "agent"}}))
        page.route("**/agent/models", lambda r: _json(r, CATALOG))
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        _choose_mode(page, "agent")
        # The production SSE parser: a first answer, then a run that stays open.
        page.evaluate("""() => {
          const original = window.fetch;
          let calls = 0;
          window.fetch = async (url, options) => {
            if (url !== '/agent') return original(url, options);
            const body = JSON.parse(options.body || '{}');
            if (!calls++) {
              const text = Array.from({length:30}, (_, i) => `Paragraph ${i}. An earlier answer with enough material to read.`).join('\\n\\n');
              const final = {response:text, chat_id:'a'.repeat(32), turn_id:'b'.repeat(32),
                turn:{id:'b'.repeat(32), question:body.question, consensus:text, status:'completed', execution_mode:'agent',
                  sources:[], model_answers:{}, agent_settings:{model_id:body.model_id, label:'DeepSeek V4.1 Flash'}}};
              return new Response('event: final\\ndata: ' + JSON.stringify(final) + '\\n\\n', {headers:{'Content-Type':'text/event-stream'}});
            }
            const encoder = new TextEncoder();
            return new Response(new ReadableStream({ start(controller) {
              window.__emitAgent = event => controller.enqueue(encoder.encode('event: activity\\ndata: ' + JSON.stringify(event) + '\\n\\n'));
              options.signal.addEventListener('abort', () => controller.error(new DOMException('Stopped', 'AbortError')));
            }}), {headers:{'Content-Type':'text/event-stream'}});
          };
        }""")
        page.locator("#questionInput").fill("First message")
        page.locator("#sendButton").click()
        page.wait_for_function("() => App.runRegistry.visible()?.status === 'succeeded'")
        page.wait_for_timeout(500)
        page.locator("#questionInput").fill("Is a heat pump worth it in an old building?")
        page.locator("#sendButton").click()
        page.wait_for_function("() => !!window.__emitAgent")
        expect(page.locator("#agentAnswerActivity .agent-progress .agent-current-status")).to_have_text("Thinking…")
        # The question has reached the top: the page ends right below the turn.
        page.wait_for_function("() => !document.body.classList.contains('chat-scroll-following')")
        page.wait_for_timeout(400)
        assert page.evaluate("document.documentElement.scrollHeight - innerHeight - scrollY") < 2
        page.evaluate("""() => {
          window.__frames = [];
          window.__ends = [];
          const tick = () => {
            __frames.push([scrollY, document.getElementById('threadAsk').getBoundingClientRect().top]);
            if (!window.__stop) requestAnimationFrame(tick);
          };
          requestAnimationFrame(tick);
        }""")
        chunks = ["**Assessing the question**\n\n", "I need to weigh the running costs of a heat pump in an old building",
                  " against the upfront price.", " The insulation matters most here.", "\n\n**Checking the numbers**\n\n",
                  "Typical seasonal performance in older homes is lower,", " around 2.5 to 3.",
                  " That still beats gas at current prices."]
        for chunk in chunks:
            page.evaluate("""chunk => window.__emitAgent({version:1, step_id:'completion:0', kind:'reasoning', id:'r1',
              format:'summary', text:chunk, append:true})""", chunk)
            # Past the height motion and the cross-fade of a changed line.
            page.wait_for_timeout(450)
            page.evaluate("""() => __ends.push(document.querySelector('.chat-scroll-reserve').getBoundingClientRect().bottom + scrollY)""")
        frames = page.evaluate("() => { window.__stop = true; return __frames; }")
        expect(page.locator("#agentAnswerActivity .agent-progress p")).to_contain_text("Checking the numbers")
        # Not a pixel, in any frame: neither the scroll offset nor the question.
        assert len({scroll for scroll, _ in frames}) == 1, frames
        assert max(top for _, top in frames) - min(top for _, top in frames) < .01, frames
        # The end of the page stays where it was at rest, whatever the lines' fraction.
        ends = page.evaluate("__ends")
        assert max(ends) - min(ends) < 1 / 32, ends
        assert not errors
    finally:
        context.close()


# Full-HD windows with a bookmarks bar: the question lands at a fractional
# position (292.625px), where the reserve and the page height used to swap
# 1px every frame and the scrollbar flickered for the whole run.
@pytest.mark.parametrize("height", [929, 1009])
def test_a_live_short_turn_keeps_the_page_height_still(browser, phase4_server, height):
    context, page = _real_firebase_page(browser, phase4_server)
    try:
        page.set_viewport_size({"width": 1920, "height": height})
        page.route("**/user_status", lambda r: _json(r, {"tier": "pro", "is_pro": True, "agent_access": True, "limit": 500}))
        page.route("**/usage", lambda r: _json(r, {"tier": "pro", "is_pro": True, "remaining": 500, "total_limit": 500}))
        page.route("**/api/my/memory", lambda r: _json(r, {"memory": {"content": "", "revision": 0}}))
        page.route("**/chats", lambda r: _json(r, {"chat": {"id": "a" * 32, "execution_mode": "agent"}}))
        page.route("**/agent/models", lambda r: _json(r, CATALOG))
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        _choose_mode(page, "agent")
        page.evaluate("""() => {
          window.streamSSERequest = (_url, _body, signal, handlers) => {
            window.__streamHandlers = handlers;
            return new Promise((resolve, reject) => signal.addEventListener('abort', () => reject(new DOMException('Stopped', 'AbortError')), {once:true}));
          };
        }""")
        page.locator("#questionInput").fill("Is a heat pump worth it in an old building? " * 3)
        page.locator("#sendButton").click()
        page.wait_for_function("() => !!window.__streamHandlers")
        page.wait_for_timeout(800)
        samples = page.evaluate("""() => new Promise(resolve => {
          const out = [];
          const tick = () => { out.push([document.scrollingElement.scrollHeight, document.querySelector('.chat-scroll-reserve')?.style.height]);
            out.length < 60 ? requestAnimationFrame(tick) : resolve(out); };
          requestAnimationFrame(tick);
        })""")
        assert len({tuple(s) for s in samples}) == 1, samples[:6]
        # A short turn fits the window: nothing to scroll, so no scrollbar.
        assert samples[0][0] == height
    finally:
        context.close()
