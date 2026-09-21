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
            page.evaluate('() => App.chatScroll.sent()')
            page.wait_for_function('() => document.documentElement.scrollHeight - innerHeight - scrollY < 3')
        else:
            page.evaluate("""() => {
              dispatchEvent(new WheelEvent('wheel', {deltaY:-100}));
              document.querySelectorAll('#agentAnswerBody p')[20].scrollIntoView({block:'center', behavior:'instant'});
            }""")
        page.wait_for_timeout(500)
        page.evaluate("""atEnd => {
          const paragraphs = document.querySelectorAll('#agentAnswerBody p');
          window.__readingAnchor = atEnd ? paragraphs[paragraphs.length - 1] : paragraphs[20];
        }""", at_end)
        assert page.locator('#agentAnswerActivity').bounding_box()['y'] + page.locator('#agentAnswerActivity').bounding_box()['height'] < 0
        for stage in ['review', 'checked', 'finished', 'late_usage']:
            samples = page.evaluate("""stage => new Promise(resolve => {
              const samples = [__readingAnchor.getBoundingClientRect().top];
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
                samples.push(__readingAnchor.getBoundingClientRect().top);
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


@pytest.mark.parametrize("width,reduced,dark", [(1280, False, False), (390, False, False), (320, True, True)])
def test_consensus_stream_stays_still_and_latest_only_jumps_once(browser, phase4_server, width, reduced, dark):
    context, page = _real_firebase_page(browser, phase4_server)
    try:
        page.set_viewport_size({"width": width, "height": 800})
        page.emulate_media(reduced_motion="reduce" if reduced else "no-preference")
        page.evaluate("""dark => {
          document.body.classList.toggle('dark-mode', dark);
          window.__scrollRun = App.runRegistry.create({question:'Explain the research findings',
            config:{executionMode:'consensus',agentMode:true,providers:[]}});
          App.runRegistry.update(__scrollRun.runId, run => {
            run.status = 'running'; run.phase = 'consensus'; run.consensus.status = 'pending';
          });
          window.__sendTarget = Math.max(0, document.documentElement.scrollHeight - innerHeight);
          App.revealSentMessage();
          window.__appendConsensus = () => App.runRegistry.update(__scrollRun.runId, run => {
            run.consensus.status = 'streaming';
            run.consensus.streamText += '\\n\\n' + 'The evidence should be read carefully. Multiple independent findings help us understand the result.\\n\\n'.repeat(24);
          });
        }""", dark)
        # Fast deltas arrive while the send animation is still pending.
        before = page.evaluate("__sendTarget")
        page.evaluate("__appendConsensus()")
        page.wait_for_timeout(650)
        # The mobile composer can shrink before the first frame; the jump may
        # be shorter, but new tokens may never extend its original destination.
        assert page.evaluate("scrollY") <= before + 3
        before = page.evaluate("scrollY")
        latest = page.get_by_role("button", name="Scroll to the latest message")
        expect(latest).to_be_visible()
        page.evaluate("__appendConsensus()")
        page.wait_for_timeout(600)
        assert abs(page.evaluate("scrollY") - before) < 3
        box = latest.bounding_box()
        composer = page.locator(".chat-input-container").bounding_box()
        assert 0 <= box['x'] and box['x'] + box['width'] <= width
        assert 0 <= box['y'] and box['y'] + box['height'] < composer['y']
        capture = Path("test-results/chat-scroll")
        capture.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(capture / f"consensus-{width}-{dark}.png"))
        latest.click()
        page.wait_for_function("() => document.documentElement.scrollHeight - innerHeight - scrollY < 3")
        expect(latest).not_to_be_visible()
        before = page.evaluate("scrollY")
        page.evaluate("__appendConsensus()")
        page.wait_for_timeout(650)
        assert abs(page.evaluate("scrollY") - before) < 3
        expect(latest).to_be_visible()
        page.evaluate("""() => App.runRegistry.update(__scrollRun.runId, run => {
          run.consensus.text = run.consensus.streamText;
          run.consensus.status = 'complete'; run.phase = 'done'; run.status = 'succeeded';
        })""")
        page.wait_for_timeout(650)
        # The completed pipeline shrinks above the reading position. Native
        # scroll anchoring may compensate upward, but must never jump to the end.
        assert page.evaluate("scrollY") <= before + 3
        expect(latest).to_be_visible()
    finally:
        context.close()


@pytest.mark.parametrize("width,reduced", [(1280, False), (390, False), (390, True)])
def test_agent_chat_follows_new_messages_without_stealing_the_readers_position(browser, phase4_server, width, reduced):
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
          window.__scrollCalls = [];
          const original = window.scrollTo.bind(window);
          window.scrollTo = (...args) => { window.__scrollCalls.push(args); original(...args); };
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
        }""")
        page.locator("#questionInput").fill("First message")
        page.locator("#sendButton").click()
        page.wait_for_function("() => App.runRegistry.visible()?.status === 'succeeded'")
        page.wait_for_function("() => document.documentElement.scrollHeight - innerHeight - scrollY < 3")
        assert page.evaluate("scrollY > 500")

        # An explicit send returns to the newest turn even when reading old history.
        page.mouse.move(width // 2, 200)
        page.mouse.wheel(0, -20000)
        page.wait_for_function("() => scrollY < 10")
        page.evaluate("""() => {
          const input = document.getElementById('questionInput'); input.value = 'Next message';
          window.__scrollCalls = []; window.__sending = App.agentChat.send();
        }""")
        page.wait_for_function("() => !!window.__streamHandlers")
        page.wait_for_function("() => scrollY > 500 && document.documentElement.scrollHeight - innerHeight - scrollY < 3")
        assert page.evaluate("document.getElementById('threadPendingAsk').hidden")
        if not reduced:
            assert page.evaluate("window.__scrollCalls.length > 2")

        page.evaluate("__streamHandlers.delta.append(Array.from({length:35}, (_, i) => `New answer ${i}. Text for the current turn.`).join('\\n\\n'))")
        page.wait_for_function("() => document.getElementById('agentAnswerBody').textContent.includes('New answer 34')")
        page.wait_for_function("() => document.documentElement.scrollHeight - innerHeight - scrollY < 3")

        page.mouse.wheel(0, -900)
        page.wait_for_function("() => document.documentElement.scrollHeight - innerHeight - scrollY > 400")
        page.wait_for_timeout(150)  # Let the browser finish the wheel gesture.
        before = page.evaluate("scrollY")
        page.evaluate("__streamHandlers.delta.append('\\n\\n' + 'Additional material.\\n\\n'.repeat(20))")
        page.wait_for_timeout(600)  # A full animation interval must not move the reader.
        assert abs(page.evaluate("scrollY") - before) < 3
        latest = page.locator(".chat-scroll-latest")
        expect(latest).to_be_visible()
        box = latest.bounding_box()
        assert 0 <= box["x"] and box["x"] + box["width"] <= width
        capture = Path("test-results/chat-scroll")
        capture.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(capture / f"paused-{width}-{reduced}.png"))
        await_bottom = "() => document.documentElement.scrollHeight - innerHeight - scrollY < 3"
        latest.click()
        page.wait_for_function(await_bottom)
        expect(latest).not_to_be_visible()
        # Keyboard activation restores focus; a tap must not open the soft keyboard.
        if width < 1100:
            assert page.evaluate("document.activeElement.id !== 'questionInput'")
        page.mouse.move(width // 2, 200)
        page.mouse.wheel(0, -900)
        expect(latest).to_be_visible()
        latest.focus()
        latest.press("Enter")
        page.wait_for_function(await_bottom)
        expect(page.locator("#questionInput")).to_be_focused()

        # Resize preserves following; choosing another view fences pending callbacks.
        page.set_viewport_size({"width": width, "height": 650})
        page.wait_for_function(await_bottom)
        page.evaluate("App.runRegistry.clearVisible()")
        before = page.evaluate("scrollY")
        page.evaluate("__streamHandlers.delta.append('\\n\\nA late background message.')")
        page.wait_for_timeout(500)
        assert abs(page.evaluate("scrollY") - before) < 3
        expect(latest).not_to_be_visible()
        assert not errors
    finally:
        context.close()
