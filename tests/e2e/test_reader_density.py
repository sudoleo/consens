"""Reader proportions with six full answers in the real, locally mocked shell."""
import pytest
from playwright.sync_api import expect

from test_phase4_frontend import _real_firebase_page, phase4_server  # noqa: F401
from test_model_answer_reader import reader_screenshot


@pytest.mark.parametrize('theme', ['light', 'dark'])
def test_six_answers_leave_room_to_read_and_keep_touch_targets(browser, phase4_server, theme):
    context, page = _real_firebase_page(browser, phase4_server,
        init_script=f"localStorage.setItem('theme','{theme}')")
    try:
        page.evaluate(r"""() => {
          const labels = ['GPT-5.6 Luna', 'Mistral Medium', 'Claude Sonnet',
            'Gemini 3.5 Flash-Lite', 'DeepSeek V4 Flash', 'Grok Fast'];
          const question = 'Wie lassen sich die beiden Versicherer sinnvoll vergleichen?';
          const text = '**Mein Eindruck:** Ein Vergleich wird aussagekräftiger, wenn Zeitraum, '
            + 'Geschäftsfelder und Kennzahlen zusammenpassen. Eine einzelne Zahl reicht dafür nicht aus.\n\n'
            + '### Worauf es beim Vergleich ankommt\n\n'
            + '- **Profitabilität:** Entwicklung des Ergebnisses und der Schadenquote.\n'
            + '- **Wachstum:** Beitragseinnahmen im gleichen Zeitraum betrachten.\n'
            + '- **Kapitalbasis:** Solvenz und finanzielle Stabilität einordnen.\n\n'
            + '### Einordnung\n\n'
            + 'Die veröffentlichten Berichte zeigen unterschiedliche Schwerpunkte. '
            + 'Konzernzahlen lassen sich nur eingeschränkt auf einzelne Tochtergesellschaften übertragen.\n\n';
          const ctx = App.runRegistry.create({runId:'density-six', question,
            config:{agentMode:true, providers:App.modelPrefs.slice(0,6).map((p,i) =>
              ({provider:p.key, modelLabel:labels[i]}))}});
          ctx.status = 'succeeded'; ctx.phase = 'answers_ready';
          ctx.config.providers.forEach(p => { ctx.modelResults[p.provider] = {
            status:'complete', text:text.repeat(4), sources:[]}; });
          Object.assign(ctx.consensus, {status:'complete', text:text.repeat(3),
            completedTurn:{turn_id:'density-current',question,consensus:text}});
          App.runRegistry.renderVisible();
        }""")
        page.set_viewport_size({'width':1920, 'height':912})
        page.locator('#agentModeAnswersToggle').click()
        for width in [1920, 1400, 1440, 2560]:
            page.set_viewport_size({'width':width, 'height':912})
            expect(page.locator('#answerReaderModels button')).to_have_count(6)
            metrics = page.evaluate("""() => {
              const rect = s => document.querySelector(s).getBoundingClientRect();
              const reader = rect('.answer-reader-dialog'), chat = rect('.container');
              return {width:reader.width, chatWidth:chat.width, chatRight:chat.right,
                readerLeft:reader.left, bodyTop:rect('.answer-reader-body').top,
                headerHeight:rect('.answer-reader-header').height,
                overflow:document.querySelector('#answerReaderScroll').scrollWidth -
                  document.querySelector('#answerReaderScroll').clientWidth};
            }""")
            reader_screenshot(page, f'lean-six-{width}-{theme}')
            assert 520 <= metrics['width'] <= 720
            assert metrics['chatWidth'] >= 550
            assert metrics['chatRight'] < metrics['readerLeft']
            assert metrics['headerHeight'] <= 36
            assert metrics['bodyTop'] < 340
            assert metrics['overflow'] <= 1
            expect(page.locator('.answer-reader-body')).to_have_css('font-size', '14px')
        # Touch emulation exercises the coarse-pointer overrides, including on
        # desktop-size touch screens. The smaller visual icons keep 44px targets.
        session = context.new_cdp_session(page)
        session.send('Emulation.setTouchEmulationEnabled', {'enabled':True})
        page.wait_for_function("matchMedia('(pointer: coarse)').matches")
        for selector in ['#answerReaderClose', '#answerReaderExpand', '#answerReaderModels button',
                         '#answerReaderSections button', '#answerReaderCompare']:
            for target in page.locator(selector).all():
                assert target.bounding_box()['height'] >= 44
        assert page.locator('#answerReaderClose').bounding_box()['width'] >= 44
        page.set_viewport_size({'width':390, 'height':844})
        expect(page.locator('#answerReaderSingle')).to_be_visible()
        assert page.locator('#answerReaderScroll').bounding_box()['height'] >= 400
        reader_screenshot(page, f'lean-touch-390-{theme}')
        page.locator('#answerReaderCompare').click()
        expect(page.locator('#answerReaderMobile')).to_be_visible()
        page.locator('#answerReaderSideB').click()
        expect(page.locator('#answerReaderSideB')).to_have_attribute('aria-pressed', 'true')
        page.locator('#answerReaderClose').click()
        expect(page.locator('#agentModeAnswersToggle')).to_be_focused()
    finally:
        context.close()
