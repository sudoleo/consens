"""Sources/differences density and footer spacing in the mocked app shell."""
import pytest
from playwright.sync_api import expect

from test_phase4_frontend import _real_firebase_page, phase4_server  # noqa: F401
from test_model_answer_reader import seed_insights, reader_screenshot


@pytest.mark.parametrize('theme', ['light', 'dark'])
def test_inspector_density_disclosures_and_footer(browser, phase4_server, theme):
    context, page = _real_firebase_page(browser, phase4_server,
        init_script=f"localStorage.setItem('theme','{theme}')")
    try:
        seed_insights(page)
        page.evaluate("""() => {
          const ctx = App.runRegistry.visible();
          ctx.consensus.differencesData.differences.splice(1);
          ctx.evidenceSources = [1,2,3,4].map(i => ({id:'S'+i,
            title:'Official results and participant registration '+i,
            url:'https://results.example.invalid/report/'+i}));
          App.runRegistry.renderVisible();
          App.sourceVerification.renderCurrent({schema_version:3, status:'partial',
            scope:{checked_pairs:0, pairs:4},
            findings:[1,2,3,4].map(i => ({sentence_id:i < 3 ? 1 : 2, source_id:'S'+i,
              claim:i < 3 ? 'The published report counts registered participants across all age groups.'
                : 'The finishers list includes only participants who completed the full course.',
              checked:false, reason_code:'fetch_failed'})),
            documents:[1,2,3,4].map(i => ({source_id:'S'+i,
              source_url:'https://results.example.invalid/report/'+i, title:'Race results'}))});
        }""")
        for width in [390, 320, 1440]:
            page.set_viewport_size({'width':width, 'height':900})
            page.evaluate('window.scrollTo(0,document.documentElement.scrollHeight)')
            footer = page.locator('.consensus-footer-source-status')
            expect(footer).to_be_visible()
            if width <= 640:
                expect(footer).to_have_css('text-align', 'center')
            expect(page.locator('.consensus-output')).to_have_css('padding-bottom', '24px')
            reader_screenshot(page, f'polished-footer-{width}-{theme}')
            page.locator('#consensusSourcesTab').click()
            inspector = page.locator('#answerReaderInspector')
            rows = inspector.locator('.source-check-row')
            expect(rows).to_have_count(4)
            summary = inspector.locator('.source-check-diagnostics > summary')
            summary.focus()
            page.keyboard.press('Enter')
            expect(inspector.locator('.source-check-diagnostics')).to_have_attribute('open','')
            page.keyboard.press('Enter')
            rows.first.locator('summary').click()
            expect(rows.first).to_have_attribute('open','')
            rows.first.locator('summary').click()
            cards = inspector.locator('.answer-reader-source-card')
            assert cards.first.bounding_box()['height'] < 115
            assert rows.first.bounding_box()['height'] <= 48
            assert page.evaluate("document.querySelector('#answerReaderScroll').scrollWidth <= document.querySelector('#answerReaderScroll').clientWidth + 1")
            reader_screenshot(page, f'polished-sources-{width}-{theme}')
            page.locator('#answerReaderSections [data-section="differences"]').click()
            button = inspector.locator('.diff-resolve-btn')
            expect(button).to_be_visible()
            assert button.bounding_box()['width'] < inspector.bounding_box()['width'] * .9
            reader_screenshot(page, f'polished-differences-{width}-{theme}')
            # A finished resolve must still remove its button despite custom display.
            button.evaluate('(node) => node.hidden = true')
            expect(button).to_be_hidden()
            button.evaluate('(node) => node.hidden = false')
            page.locator('#answerReaderClose').click()
        session = context.new_cdp_session(page)
        session.send('Emulation.setTouchEmulationEnabled', {'enabled':True})
        page.set_viewport_size({'width':390, 'height':844})
        page.locator('#consensusSourcesTab').click()
        for target in page.locator('#answerReaderInspector .source-check-row-summary').all():
            assert target.bounding_box()['height'] >= 44
    finally:
        context.close()
