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
          ctx.consensus.differencesData.agreement = {score:64, model_count:3,
            scored_claims:7, total_claims:10, coverage_percent:70};
          ctx.evidenceSources = Array.from({length:10}, (_, i) => i + 1).map(i => ({id:'S'+i,
            title:'Official results and participant registration '+i,
            url:'https://results.example.invalid/report/'+i}));
          App.runRegistry.renderVisible();
        }""")
        page.evaluate("""() => {
          App.state.set('lastQuestion', App.runRegistry.visible().question, 'run');
          App.consensusPipeline.setRunFacts({models: 5, durationMs: 103000});
        }""")
        for width in [390, 320, 640, 641, 1440]:
            page.set_viewport_size({'width':width, 'height':900})
            page.evaluate('window.scrollTo(0,document.documentElement.scrollHeight)')
            if width <= 640:
                expect(page.locator('#runProvenanceFacts')).to_be_hidden()
            else:
                expect(page.locator('#runProvenanceFacts')).to_be_visible()
                expect(page.locator('#runProvenanceFacts')).to_contain_text('103 s')
            for row in page.locator('#consensusFooterTabs, .thread-history-tabs').all():
                actions = row.locator('.consensus-evidence-action:visible')
                expect(actions.locator('.consensus-evidence-icon[aria-hidden="true"]')).to_have_count(3)
                assert actions.locator('.consensus-tab-label').evaluate_all(
                    'labels => labels.map(label => label.dataset.short)') == ['Differences', 'Answers', 'Sources']
                # Measure in one frame while the chat shell animates its width.
                bounds = actions.evaluate_all('buttons => buttons.map(b => b.getBoundingClientRect().toJSON())')
                assert all(box['height'] >= 44 for box in bounds)
                assert max(box['y'] for box in bounds) - min(box['y'] for box in bounds) <= 1
                if width <= 640:
                    assert max(box['width'] for box in bounds) - min(box['width'] for box in bounds) <= 1
                for action in actions.all():
                    assert action.evaluate("""el => {
                      const r = el.getBoundingClientRect();
                      return [...el.querySelectorAll('svg, span')].filter(child => child.getClientRects().length)
                        .every(child => {const c = child.getBoundingClientRect();
                          return c.left >= r.left - 1 && c.right <= r.right + 1
                            && c.top >= r.top - 1 && c.bottom <= r.bottom + 1;});
                    }""")
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            expect(page.locator('#runReplayButton')).to_be_visible()
            expect(page.locator('.consensus-output')).to_have_css('padding-bottom', '24px')
            reader_screenshot(page, f'polished-footer-{width}-{theme}')
            page.locator('#consensusSourcesTab').click()
            inspector = page.locator('#answerReaderInspector')
            cards = inspector.locator('.answer-reader-source-card')
            assert cards.first.bounding_box()['height'] < 115
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
        page.set_viewport_size({'width':320, 'height':844})
        for mode in ['summary', 'off', 'full']:
            page.evaluate("""mode => {
              document.body.classList.toggle('agreement-score-hidden', mode === 'summary');
              document.body.classList.toggle('agreement-verdict-hidden', mode === 'off');
            }""", mode)
            expect(page.locator('#consensusFooterTabs .consensus-evidence-action:visible')).to_have_count(3)
            reader_screenshot(page, f'footer-{mode}-320-{theme}')
        # Missing sections must collapse the existing equal-column grid, even
        # though the visible controls now use their own internal grid.
        for selector in ['#consensusSourcesTab', '#consensusDifferencesTab']:
            page.locator(selector).evaluate('button => button.hidden = true')
            expect(page.locator(selector)).to_be_hidden()
        expect(page.locator('#consensusFooterTabs .consensus-evidence-action:visible')).to_have_count(1)
        assert abs(page.locator('#agentModeAnswersToggle').bounding_box()['width']
                   - page.locator('#consensusFooterTabs').bounding_box()['width']) <= 1
    finally:
        context.close()
