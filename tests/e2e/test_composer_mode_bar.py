"""Composer mode visibility, frozen result status and responsive layout."""
from pathlib import Path

import pytest
from playwright.sync_api import expect

from test_phase4_frontend import _real_firebase_page, phase4_server  # noqa: F401


@pytest.mark.parametrize("width,dark", [(1440, False), (1440, True), (390, False), (320, True)])
def test_composer_mode_bar(browser, phase4_server, width, dark):
    context, page = _real_firebase_page(browser, phase4_server,
        init_script="localStorage.setItem('agentMode', 'true');")
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    try:
        page.set_viewport_size({"width": width, "height": 900})
        page.evaluate("dark => document.body.classList.toggle('dark-mode', dark)", dark)
        bar = page.locator('#composerModeBar')
        toggle = page.locator('#composerAgentToggle')
        expect(bar).to_be_visible()
        expect(toggle).to_have_attribute('aria-checked', 'true')
        expect(page.locator('#composerModelIcons img')).to_have_count(6)
        expect(page.locator('#composerModelCount')).to_have_count(0)
        expect(page.locator('#composerDeepToggle')).to_be_visible()
        expect(page.locator('#composerAttachButton')).to_be_visible()
        expect(page.locator('#composerModeDescription')).to_contain_text('Automatic consensus')
        output = Path('test-results/composer-mode-bar')
        output.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(output / f'{width}-{"dark" if dark else "light"}-hero.png'))
        page.locator('#attachTrigger').click()
        page.locator('label[for="agentModeMenuSwitch"]').click()
        page.locator('#attachTrigger').click()
        expect(bar).to_be_visible()
        expect(toggle).to_have_attribute('aria-checked', 'false')
        expect(page.locator('#composerSourcesToggle')).to_be_disabled()
        expect(page.locator('#composerSourcesToggle')).to_have_attribute('aria-checked', 'false')
        expect(page.locator('#sourceCheckSwitch')).to_be_disabled()
        expect(page.locator('#sourceCheckMenuSwitch')).to_be_disabled()
        assert page.evaluate('App.isSourceCheckEnabled()') is False
        expect(page.locator('#agentModeMenuSwitch')).not_to_be_checked()
        expect(page.locator('#composerModeDescription')).to_contain_text('no consensus')
        expect(page.locator('#modeNotice')).to_have_count(0)
        assert bar.evaluate("el => getComputedStyle(el).animationName") == 'composer-mode-reveal'
        page.emulate_media(reduced_motion='reduce')
        assert bar.evaluate("el => getComputedStyle(el).animationName") == 'none'
        page.emulate_media(reduced_motion='no-preference')
        bar.evaluate("el => Promise.all(el.getAnimations().map(animation => animation.finished))")
        page.evaluate("""() => {
            window.enterDirectComparisonView();
            App.answerReader.showDirectBookmark({id: 'mode-bar-test', query: 'Which approach works best?',
              responses: Object.fromEntries(App.modelPrefs.slice(0, 6).map(p => [p.key, 'A saved model answer.'])),
              model_labels: {OpenAI: 'Saved GPT'}});
        }""")
        expect(page.locator('#composerComparisonStatus')).to_contain_text('6 of 6 ready')
        expect(page.locator('.answer-reader-header')).to_be_hidden()
        expect(page.locator('#answerReaderMode')).to_be_hidden()
        expect(page.locator('.is-direct .answer-reader-answer')).to_have_count(6)
        # The mode remains visible even when the phone composer is collapsed.
        page.evaluate("document.body.classList.add('composer-collapsed')")
        expect(toggle).to_be_visible()
        # Collapsing can restart the reveal; measure its final position.
        page.wait_for_function("() => !document.body.classList.contains('composer-animating')")
        bar.evaluate("el => Promise.all(el.getAnimations().map(animation => animation.finished))")
        rect = bar.bounding_box()
        assert abs(rect['height'] - 36) <= 1
        input_rect = page.locator('.chat-input-container').bounding_box()
        assert abs(rect['y'] - input_rect['y'] - input_rect['height']) <= 1
        assert abs(rect['x'] - input_rect['x'] - 12) <= 1
        assert abs(input_rect['width'] - rect['width'] - 24) <= 1
        marks = page.locator('.composer-model-icon')
        first, second = marks.nth(0).bounding_box(), marks.nth(1).bounding_box()
        assert second['x'] < first['x'] + first['width']
        assert rect['x'] >= 0 and rect['x'] + rect['width'] <= width + 1
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.locator('.input-section').screenshot(path=str(output / f'{width}-{"dark" if dark else "light"}-dock.png'))
        page.screenshot(path=str(output / f'{width}-{"dark" if dark else "light"}-direct.png'))
        toggle.click()
        expect(toggle).to_have_attribute('aria-checked', 'true')
        if width >= 1100:
            expect(bar).to_be_visible()
        else:
            expect(bar).to_be_hidden()
        expect(page.locator('#composerSourcesToggle')).to_be_enabled()
        expect(page.locator('#composerSourcesToggle')).to_have_attribute('aria-checked', 'true')
        # Bookmark provenance does not change when the next question changes mode.
        expect(page.locator('#composerComparisonStatus')).to_contain_text('Agent Mode was off')
        expect(page.locator('.is-direct .answer-reader-answer')).to_have_count(6)
        page.screenshot(path=str(output / f'{width}-{"dark" if dark else "light"}-agent.png'))
        page.evaluate('App.answerReader.reset()')
        expect(page.locator('#composerComparisonStatus')).to_be_hidden()
        page.evaluate("document.getElementById('newRunButton').click()")
        expect(bar).to_be_visible()
        expect(toggle).to_have_attribute('aria-checked', 'true')
        assert errors == []
    finally:
        context.close()


@pytest.mark.parametrize("width,dark", [(1440, False), (390, False), (320, True)])
def test_toolbar_deep_think_and_upload_reuse_plan_gates(browser, phase4_server, width, dark):
    context, page = _real_firebase_page(browser, phase4_server,
        init_script="localStorage.setItem('agentMode', 'true');")
    try:
        page.set_viewport_size({'width': width, 'height': 844})
        page.evaluate("dark => document.body.classList.toggle('dark-mode', dark)", dark)
        draft = page.locator('#questionInput')
        draft.fill('Keep this question while I explore the app.')
        deep = page.locator('#composerDeepToggle')
        deep.click()
        notice = page.locator('#featureAccessNotice')
        expect(notice).to_be_visible()
        expect(notice).to_contain_text('Deep Think')
        expect(page.locator('#proFeatureModal')).to_be_hidden()
        expect(deep).to_have_attribute('aria-checked', 'false')
        draft.fill('The composer is still usable.')
        page.locator('#composerAttachButton').click()
        expect(notice).to_contain_text('File uploads')
        expect(notice).not_to_contain_text('Deep Think')
        expect(page.locator('#proFeatureModal')).to_be_hidden()
        expect(draft).to_have_value('The composer is still usable.')
        output = Path('test-results/early-access')
        output.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(output / f'{width}-notice.png'))
        rect = notice.bounding_box()
        assert rect['x'] >= 0 and rect['x'] + rect['width'] <= width
        page.locator('#featureAccessDetails').click()
        modal = page.locator('#proFeatureModal')
        expect(modal).to_be_visible()
        expect(notice).to_be_hidden()
        expect(modal.locator('a[href="mailto:contact@consens.io"]')).to_be_visible()
        expect(page.locator('#closeProModal')).to_be_focused()
        page.keyboard.press('Shift+Tab')
        expect(page.locator('#keepFreeBtn')).to_be_focused()
        page.keyboard.press('Tab')
        expect(page.locator('#closeProModal')).to_be_focused()
        page.screenshot(path=str(output / f'{width}-info.png'))
        page.keyboard.press('Escape')
        expect(modal).to_be_hidden()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        # The explicit sidebar information link remains available after dismissal.
        page.locator('#upgradeLink').evaluate('(el) => el.click()')
        expect(modal).to_be_visible()
        page.locator('#keepFreeBtn').click()
        expect(modal).to_be_hidden()
        # Plus keeps uploads and Resolve, while Deep Think stays gated.
        page.evaluate("window.updateUserTierUI('plus', true)")
        assert page.evaluate("App.showProFeatureModal('Resolve')") is False
        with page.expect_file_chooser():
            page.locator('#composerAttachButton').click()
        expect(notice).to_be_hidden()
        deep.click()
        expect(notice).to_contain_text('Deep Think')
        page.evaluate("window.updateUserTierUI('pro', true)")
        expect(notice).to_be_hidden()
        deep.click()
        expect(deep).to_have_attribute('aria-checked', 'true')
        expect(page.locator('#deepSearchToggle')).to_be_checked()
        expect(page.locator('#deepThinkInputIndicator')).to_be_hidden()
        deep.click()
        expect(page.locator('#deepSearchToggle')).not_to_be_checked()
        with page.expect_file_chooser() as chooser:
            page.locator('#composerAttachButton').click()
        chooser.value.set_files({'name': 'toolbar.txt', 'mimeType': 'text/plain', 'buffer': b'A local attachment.'})
        expect(page.locator('#attachmentBar')).to_contain_text('toolbar.txt')
        page.set_viewport_size({'width': 1440, 'height': 900})
        page.evaluate('window.exitHeroMode()')
        expect(page.locator('#composerModeBar')).to_be_visible()
        expect(page.locator('#composerModeBar #attachmentBar')).to_contain_text('toolbar.txt')
        page.set_viewport_size({'width': 390, 'height': 844})
        expect(page.locator('#composerModeBar')).to_be_hidden()
        expect(page.locator('.chat-input-container #attachmentBar')).to_contain_text('toolbar.txt')
        page.set_viewport_size({'width': 1440, 'height': 900})
        expect(page.locator('#composerModeBar')).to_be_visible()
        expect(page.locator('#composerModeBar #attachmentBar')).to_contain_text('toolbar.txt')
    finally:
        context.close()
