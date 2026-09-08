"""Cross-module reader regressions, using only local mocked app data."""
import pytest
from playwright.sync_api import expect
from test_phase4_frontend import _real_firebase_page, phase4_server  # noqa: F401
from test_model_answer_reader import seed_insights, seed_reader, reader_screenshot


@pytest.mark.parametrize('kind', ['sources', 'differences'])
def test_live_inspector_releases_shared_targets_on_followup(browser, phase4_server, kind):
    context, page = _real_firebase_page(browser, phase4_server)
    try:
        seed_insights(page)
        page.evaluate('(kind) => App.answerReader.openPanel(kind)', kind)
        expect(page.locator('.answer-reader-dialog')).to_have_attribute('open', '')
        page.evaluate("""() => {
          const registry = App.runRegistry, first = registry.visible();
          const turn = {turn_id:'reader-current',question:first.question,consensus:first.consensus.text,
            sources:first.evidenceSources,differences_data:first.consensus.differencesData,
            model_answers:Object.fromEntries(first.config.providers.map(p => [p.provider,
              {answer:first.modelResults[p.provider].text,model_label:p.modelLabel}]))};
          const next = registry.create({runId:'review-next',question:'A different next question',
            config:first.config,basis:{historyTurns:[...first.historyTurns,turn]}});
          next.modelResults = first.modelResults;
          next.evidenceSources = [{title:'Next question source',url:'https://example.invalid/new'}];
          registry.renderVisible();
        }""")
        expect(page.locator('.answer-reader-dialog')).not_to_have_attribute('open', '')
        expect(page.locator('#consensusSourcesPanel #consensusSourcesList')).to_have_count(1)
        expect(page.locator('#consensusDifferencesPanel #differencesCards')).to_have_count(1)
        # The original turn can still be reopened with its own evidence.
        page.evaluate("""(kind) => App.answerReader.openPanel(kind, null,
            document.querySelectorAll('.thread-history-turn')[1])""", kind)
        expect(page.locator('#answerReaderQuestion')).to_contain_text('What changes in the next question?')
        expect(page.locator('#answerReaderInspector')).not_to_contain_text('Next question source')
        expect(page.locator('#answerReaderInspector')).to_contain_text(
            'Official race results' if kind == 'sources' else 'The reported participant total differs')
    finally:
        context.close()


def select_answer_text(page):
    body = page.locator('.answer-reader-body p').first
    body.evaluate("""async element => {
      element.scrollIntoView({block:'start',behavior:'instant'});
      // Ask about this animates the composer scroll. Two animation frames are
      // insufficient when immediately reopening the modal: wait until those
      // scroll events settle before starting the next selection gesture.
      await new Promise(resolve => {
        let timer;
        const finish = () => { document.removeEventListener('scroll', settle, true); resolve(); };
        const settle = () => { clearTimeout(timer); timer = setTimeout(finish, 100); };
        document.addEventListener('scroll', settle, true);
        settle();
      });
      const range = document.createRange();
      range.setStart(element.firstChild,0); range.setEnd(element.firstChild,80);
      const selection = getSelection(); selection.removeAllRanges(); selection.addRange(range);
      element.dispatchEvent(new MouseEvent('mouseup',{bubbles:true}));
    }""")
    expect(page.locator('#memorySelectionMenu')).to_be_visible()


@pytest.mark.parametrize('mode,width', [('direct',1440),('docked',1440),('modal',390)])
def test_reader_selection_actions_reach_composer_and_memory(browser, phase4_server, mode, width):
    context, page = _real_firebase_page(browser, phase4_server,
        init_script="localStorage.setItem('theme','dark')")
    try:
        page.set_viewport_size({'width':width,'height':1000})
        seed_reader(page, direct=mode == 'direct')
        if mode != 'direct':
            page.locator('#agentModeAnswersToggle').click()
        # Transparent, frameless icons in both reading surfaces; dark mono logos
        # inherit their normal inversion instead of gaining a white backing tile.
        mark = page.locator('.answer-reader-identity .answer-reader-model-mark').first
        expect(mark).to_have_css('background-color','rgba(0, 0, 0, 0)')
        expect(mark).to_have_css('border-top-width','0px')
        expect(mark.locator('img')).to_have_css('background-color','rgba(0, 0, 0, 0)')
        select_answer_text(page)
        reader_screenshot(page, f'review-selection-{mode}')
        page.locator('[data-selection-action="ask"]').click()
        expect(page.locator('#questionInput')).to_be_focused()
        assert page.evaluate('App.quote.text().length') > 0
        if mode != 'direct':
            expect(page.locator('.answer-reader-dialog')).not_to_have_attribute('open','')
        for intent in ['add','correct']:
            if mode != 'direct':
                page.locator('#agentModeAnswersToggle').click()
            select_answer_text(page)
            page.locator(f'[data-memory-intent="{intent}"]').click()
            expect(page.locator('#memoryEditBackdrop')).to_be_visible()
            expect(page.locator('#memoryEditCorrection')).to_be_focused()
            expect(page.locator('#memoryEditSource')).to_have_text('Model answer')
            page.keyboard.press('Escape')
            expect(page.locator('#memoryEditBackdrop')).to_be_hidden()
            if mode != 'direct':
                expect(page.locator('#agentModeAnswersToggle')).to_be_focused()
    finally:
        context.close()
