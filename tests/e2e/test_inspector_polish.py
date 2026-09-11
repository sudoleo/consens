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
        page.evaluate("""() => {
          App.state.set('lastQuestion', App.runRegistry.visible().question, 'run');
          App.consensusPipeline.setRunFacts({models: 5, durationMs: 103000});
        }""")
        for width in [390, 320, 1440]:
            page.set_viewport_size({'width':width, 'height':900})
            page.evaluate('window.scrollTo(0,document.documentElement.scrollHeight)')
            footer = page.locator('.consensus-footer-source-status')
            if width <= 640:
                expect(footer).to_be_hidden()
                expect(page.locator('#runProvenanceFacts')).to_be_hidden()
                expect(page.locator('#consensusSourcesTab .consensus-source-check-icon')).to_be_visible()
                expect(page.locator('#consensusSourcesTab')).to_have_attribute('data-check-state', 'unknown')
                assert page.locator('#consensusSourcesTab').evaluate("""tab => {
                  const icon = tab.querySelector('.consensus-source-check-icon').getBoundingClientRect();
                  const label = tab.querySelector('.consensus-tab-label').getBoundingClientRect();
                  return Math.abs(icon.y + icon.height / 2 - label.y - label.height / 2) < 4;
                }""")
            else:
                expect(footer).to_be_visible()
                expect(footer).to_have_css('background-color', 'rgba(0, 0, 0, 0)')
                expect(page.locator('#runProvenanceFacts')).to_be_visible()
                expect(page.locator('#runProvenanceFacts')).to_contain_text('103 s')
            expect(page.locator('#runReplayButton')).to_be_visible()
            expect(page.locator('.consensus-output')).to_have_css('padding-bottom', '24px')
            reader_screenshot(page, f'polished-footer-{width}-{theme}')
            page.locator('#consensusSourceCheckButton' if width > 640 else '#consensusSourcesTab').click()
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
            expect_single_chevron(rows.first.locator('summary'), '::before', opened=True)
            rows.first.locator('summary').click()
            expect_single_chevron(rows.first.locator('summary'), '::before', opened=False)
            statement = inspector.locator('.source-check-statement').first
            expect(statement.locator('summary')).to_have_count(0)
            expect(statement.locator('.source-check-claim')).to_be_visible()
            expect(statement.locator('.source-check-claim')).to_contain_text('across all age groups.')
            expect(inspector.locator('.source-check-statement-preview')).to_have_count(0)
            reader_screenshot(page, f'source-statements-{width}-{theme}')
            cards = inspector.locator('.answer-reader-source-card')
            assert cards.first.bounding_box()['height'] < 115
            assert rows.first.bounding_box()['height'] <= 48
            assert page.evaluate("document.querySelector('#answerReaderScroll').scrollWidth <= document.querySelector('#answerReaderScroll').clientWidth + 1")
            reader_screenshot(page, f'polished-sources-{width}-{theme}')
            if width == 1440:
                page.locator('#editSystemPromptBtn').click()
                settings = page.locator('#systemPromptModal')
                expect(settings).to_be_visible()
                # The actual hit target over the overlapping right edge must
                # belong to Settings, not the later-mounted docked reader.
                assert page.evaluate("""() => {
                  const settings = document.querySelector('.settings-modal-content').getBoundingClientRect();
                  const reader = document.querySelector('.answer-reader-dialog').getBoundingClientRect();
                  const x = Math.min(settings.right - 12, Math.max(settings.left, reader.left) + 30);
                  return !!document.elementFromPoint(x, settings.top + 30)?.closest('#systemPromptModal');
                }""")
                page.locator('#settingsTabDisplay').click()
                expect(page.locator('#settingsTabDisplay')).to_have_attribute('aria-selected', 'true')
                reader_screenshot(page, f'settings-above-sources-{theme}')
                page.locator('#closeSystemPromptModal').click()
                expect(settings).to_be_hidden()
                expect(inspector).to_be_visible()
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
        page.locator('#answerReaderClose').click()
        for support, icon in [('supported', '✓'), ('partial', '!')]:
            page.evaluate("""support => App.sourceVerification.renderCurrent({
              schema_version: 3, status: 'complete', scope: {pairs: 1, checked_pairs: 1},
              findings: [{sentence_id: 1, source_id: 'S1', claim: 'The current consensus.',
                checked: true, support, topical: 'relevant', temporal: 'suitable'}]
            })""", support)
            expect(page.locator('#consensusSourcesTab .consensus-source-check-icon')).to_have_text(icon)
            expect(page.locator('#consensusSourcesTab .consensus-source-check-icon')).to_be_visible()
            reader_screenshot(page, f'mobile-footer-{support}-{theme}')
    finally:
        context.close()


def expect_single_chevron(summary, pseudo, *, opened):
    styles = summary.evaluate("""(node, pseudo) => {
      const arrow = getComputedStyle(node, pseudo);
      const other = getComputedStyle(node, pseudo === '::before' ? '::after' : '::before');
      return {content: arrow.content, transform: arrow.transform,
        border: arrow.borderRightWidth, other: other.content,
        marker: getComputedStyle(node).listStyleType};
    }""", pseudo)
    assert styles['content'] == '\"\"'  # No extra plus/minus/text glyph.
    assert styles['other'] in ('none', 'normal')
    assert styles['marker'] == 'none'
    assert float(styles['border'].removesuffix('px')) > 0
    assert styles['transform'].startswith('matrix(-' if opened else 'matrix(0.')
