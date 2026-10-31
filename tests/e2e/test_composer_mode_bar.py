"""The start screen's tools in the field, a comparison's status under it, responsive layout."""
from pathlib import Path

import pytest
from playwright.sync_api import expect

from test_phase4_frontend import _real_firebase_page, phase4_server  # noqa: F401
from test_run_mode_selector import _signed_in


@pytest.mark.parametrize("width,dark", [(1440, False), (1440, True), (390, False), (320, True)])
def test_composer_mode_bar(browser, phase4_server, width, dark):
    context, page = _real_firebase_page(browser, phase4_server,
        init_script="localStorage.setItem('runMode', 'compare'); localStorage.setItem('consensio.settingsReset','2026-10-12');")
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    try:
        page.set_viewport_size({"width": width, "height": 900})
        # An account with Agent beside Compare, so the next message can
        # change mode while a result stays on screen.
        _signed_in(page, agent_access=True)
        page.evaluate("dark => document.body.classList.toggle('dark-mode', dark)", dark)
        bar = page.locator('#composerModeBar')
        tools = page.locator('#composerTools')
        mode = page.locator('#runModeSelect')
        # One field, one row: the tools stand beside (+) (from 701px; a phone
        # keeps them in the (+) menu), the marks before the chip; nothing
        # hangs under the field on the start screen.
        expect(bar).to_be_hidden()
        expect(mode).to_have_value('compare')
        # Daily compares three since 2026-10-28. A phone leaves the count to
        # the chip's words; the marks are drawn all the same.
        picker = page.locator('.composer-models #composerModelPicker')
        if width > 700:
            expect(picker).to_be_visible()
        else:
            expect(picker).to_be_hidden()
        expect(page.locator('#composerModelIcons img')).to_have_count(3)
        expect(page.locator('#composerModelCount')).to_have_count(0)
        expect(page.locator('#composerAttachButton')).to_have_count(0)
        # Reasoning has no button in the row (since 2026-10-31): Compare's
        # switch is in the (+) menu at every width.
        expect(page.locator('.chat-input-container .composer-models svg path[d^="M12 5.5a3 3"]')).to_have_count(0)
        if width > 700:
            # The row is one line: (+), the tools, the marks and Send (or the
            # demo offer in its place) share it.
            boxes = [page.locator(selector).bounding_box() for selector in (
                '#attachTrigger', '#composerModelPicker', '.input-actions-container')]
            centres = [box['y'] + box['height'] / 2 for box in boxes]
            assert max(centres) - min(centres) <= 2, centres
        expect(page.locator('#composerModeDescription')).to_contain_text('side by side')
        output = Path('test-results/composer-mode-bar')
        output.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(output / f'{width}-{"dark" if dark else "light"}-hero.png'))
        # The model marks before the chip overlap into one small stack.
        if width > 700:
            marks = page.locator('#composerModelIcons .composer-model-icon')
            first, second = marks.nth(0).bounding_box(), marks.nth(1).bounding_box()
            assert second['x'] < first['x'] + first['width']
        expect(page.locator('#modeNotice')).to_have_count(0)
        # On the start screen the tools are simply there: no rise on the first
        # paint or a mode change (Apple-Audit B1) ...
        assert tools.evaluate("el => getComputedStyle(el).animationName") == 'none'
        tools.evaluate("el => { el.hidden = true; App.renderComposerMode(); }")
        if width > 700:
            # ... they rise in when they come back (a new chat, the Compare start).
            assert tools.evaluate("el => getComputedStyle(el).animationName") == 'composer-mode-reveal'
            page.emulate_media(reduced_motion='reduce')
            assert tools.evaluate("el => getComputedStyle(el).animationName") == 'none'
            page.emulate_media(reduced_motion='no-preference')
            tools.evaluate("el => Promise.all(el.getAnimations().map(animation => animation.finished))")
        else:
            # A phone draws no tools in the row: nothing to rise, no class left behind.
            assert tools.evaluate("el => el.classList.contains('is-revealing')") is False
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
        # In a chat the bar under the field carries the status of the
        # comparison on screen; the tools are in the (+) menu.
        expect(bar).to_be_visible()
        expect(tools).to_be_hidden()
        expect(page.locator('#composerModelPicker')).to_be_hidden()
        # The collapsed phone composer is (+), the field and Send in every
        # mode; the mode lives in the (+) menu at every width.
        page.evaluate("document.body.classList.add('composer-collapsed')")
        expect(page.locator('#attachTrigger')).to_be_visible()
        expect(page.locator('.composer-lead .model-picker-display')).to_have_count(0)
        # Collapsing can restart the reveal; measure its final position.
        page.wait_for_function("() => !document.body.classList.contains('composer-animating') && !document.body.classList.contains('composer-gliding')")
        bar.evaluate("el => Promise.all(el.getAnimations().map(animation => animation.finished))")
        rect = bar.bounding_box()
        assert abs(rect['height'] - 36) <= 1
        input_rect = page.locator('.chat-input-container').bounding_box()
        assert abs(rect['y'] - input_rect['y'] - input_rect['height']) <= 1
        assert abs(rect['x'] - input_rect['x'] - 12) <= 1
        assert abs(input_rect['width'] - rect['width'] - 24) <= 1
        assert rect['x'] >= 0 and rect['x'] + rect['width'] <= width + 1
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.locator('.input-section').screenshot(path=str(output / f'{width}-{"dark" if dark else "light"}-dock.png'))
        page.screenshot(path=str(output / f'{width}-{"dark" if dark else "light"}-direct.png'))
        page.evaluate("document.body.classList.remove('composer-collapsed')")
        # The choice for the next message changes; the result on screen
        # stays. Agent has its own composer, so this bar steps aside.
        page.evaluate("App.runMode.set('agent')")
        expect(bar).to_be_hidden()
        expect(page.locator('.is-direct .answer-reader-answer')).to_have_count(6)
        page.evaluate("App.runMode.set('compare')")
        expect(bar).to_be_visible()
        expect(page.locator('#composerComparisonStatus')).to_contain_text('6 of 6 ready')
        page.screenshot(path=str(output / f'{width}-{"dark" if dark else "light"}-agent.png'))
        page.evaluate('App.answerReader.reset()')
        expect(page.locator('#composerComparisonStatus')).to_be_hidden()
        expect(bar).to_be_hidden()
        page.evaluate("document.getElementById('newRunButton').click()")
        expect(bar).to_be_hidden()
        if width > 700:
            expect(picker).to_be_visible()
        expect(mode).to_have_value('compare')
        assert errors == []
    finally:
        context.close()


@pytest.mark.parametrize("width,dark", [(1440, False), (390, False), (320, True)])
def test_toolbar_reasoning_and_uploads_are_open_and_plan_gates_stay_calm(browser, phase4_server, width, dark):
    context, page = _real_firebase_page(browser, phase4_server,
        init_script="localStorage.setItem('runMode', 'compare'); localStorage.setItem('consensio.settingsReset','2026-10-12');")
    try:
        page.set_viewport_size({'width': width, 'height': 844})
        page.evaluate("dark => document.body.classList.toggle('dark-mode', dark)", dark)
        draft = page.locator('#questionInput')
        draft.fill('Keep this question while I explore the app.')
        # Reasoning is open to every tier: no notice, the switch just turns on.
        # Compare's switch is in the (+) menu, on the start screen too.
        reasoning = page.locator('#reasoningToggle')

        def switch_reasoning():
            page.locator('#attachTrigger').click()
            expect(page.locator('label[for="reasoningToggle"]')).to_contain_text('Reasoning')
            page.locator('label[for="reasoningToggle"]').click()
            if page.locator('#attachMenu').is_visible():
                page.locator('#attachTrigger').click()
            expect(page.locator('#attachMenu')).to_be_hidden()

        def choose_file():
            page.locator('#attachTrigger').click()
            page.locator('#attachUploadOption').click()

        switch_reasoning()
        # The app's one notice line (App.toast) says it, with the way to the note.
        notice = page.locator('#appToasts .toast.is-shown')
        expect(notice).to_be_hidden()
        expect(reasoning).to_be_checked()
        switch_reasoning()
        expect(reasoning).not_to_be_checked()
        draft.fill('The composer is still usable.')
        # Files are open to every signed-in account: the picker opens, no notice.
        with page.expect_file_chooser():
            choose_file()
        expect(notice).to_be_hidden()
        # A feature that is still gated shows the same calm notice.
        page.evaluate("App.showProFeatureModal('High Quality mode')")
        expect(notice).to_be_visible()
        expect(notice).to_contain_text('High Quality mode')
        expect(page.locator('#proFeatureModal')).to_be_hidden()
        expect(draft).to_have_value('The composer is still usable.')
        output = Path('test-results/early-access')
        output.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(output / f'{width}-notice.png'))
        rect = notice.bounding_box()
        assert rect['x'] >= 0 and rect['x'] + rect['width'] <= width
        notice.get_by_role('button', name='About early access').click()
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
        # Plus keeps uploads; a tier change leaves Reasoning alone.
        switch_reasoning()
        page.evaluate("window.updateUserTierUI('plus', true)")
        expect(page.locator('#reasoningToggle')).to_be_checked()
        with page.expect_file_chooser():
            choose_file()
        expect(notice).to_be_hidden()
        page.evaluate("window.updateUserTierUI('pro', true)")
        expect(notice).to_be_hidden()
        expect(reasoning).to_be_checked()
        switch_reasoning()
        expect(page.locator('#reasoningToggle')).not_to_be_checked()
        with page.expect_file_chooser() as chooser:
            choose_file()
        chooser.value.set_files({'name': 'toolbar.txt', 'mimeType': 'text/plain', 'buffer': b'A local attachment.'})
        expect(page.locator('#attachmentBar')).to_contain_text('toolbar.txt')
        # The files stand above the question in the field, on the start
        # screen as in a chat, at every width.
        expect(page.locator('.chat-input-container > #attachmentBar')).to_contain_text('toolbar.txt')
        page.evaluate('window.exitHeroMode()')
        for viewport in ({'width': 1440, 'height': 900}, {'width': 390, 'height': 844}):
            page.set_viewport_size(viewport)
            expect(page.locator('#composerModeBar')).to_be_hidden()
            expect(page.locator('.chat-input-container > #attachmentBar')).to_contain_text('toolbar.txt')
            expect(page.locator('.chat-input-container > #attachmentBar')).to_be_visible()
    finally:
        context.close()
