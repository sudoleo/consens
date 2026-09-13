"""Empty direct mode uses the real answer layout without issuing a query."""
from pathlib import Path

import pytest
from playwright.sync_api import expect

from test_phase4_frontend import _real_firebase_page, phase4_server  # noqa: F401
from test_model_answer_reader import seed_reader


def settle(page):
    page.wait_for_function("() => !document.body.classList.contains('comparison-layout-changing')")
    page.locator('.input-section').evaluate(
        "el => Promise.all(el.getAnimations({subtree:true}).filter(a => "
        "a.effect.getComputedTiming().iterations !== Infinity).map(a => a.finished.catch(() => {})))")


@pytest.mark.parametrize('width,height,theme', [(1440, 900, 'light'), (1440, 900, 'dark'),
    (1024, 768, 'light'), (390, 844, 'light'), (390, 844, 'dark'),
    (320, 568, 'dark'), (844, 390, 'light')])
def test_preview_toggle_layout_and_real_result(browser, phase4_server, width, height, theme):
    context, page = _real_firebase_page(browser, phase4_server,
        init_script=f"localStorage.setItem('agentMode','true'); localStorage.setItem('theme','{theme}');")
    errors, requests = [], []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('request', lambda request: requests.append(request.url)
        if any(part in request.url for part in ['/prepare', '/ask_', '/consensus']) else None)
    try:
        page.set_viewport_size({'width': width, 'height': height})
        draft = page.locator('#questionInput')
        draft.fill('Compare the alternatives for my next project.')
        toggle = page.locator('#composerAgentToggle')
        toggle.click()
        intro = page.locator('#answerReaderPreviewIntro')
        cards = page.locator('.is-preview .answer-reader-answer')
        expect(intro).to_be_visible()
        expect(cards).to_have_count(6)
        expect(page.locator('#composerComparisonStatus')).to_be_hidden()
        expect(page.locator('.is-preview [aria-busy="true"], .is-preview .skeleton')).to_have_count(0)
        assert page.evaluate('App.runRegistry.visible()') is None
        assert not page.locator('.response-section').evaluate('el => el.inert')
        settle(page)
        first, second = cards.nth(0).bounding_box(), cards.nth(1).bounding_box()
        if width >= 1100:
            assert abs(first['y'] - second['y']) < 1
            assert second['x'] > first['x'] + first['width']
            sidebar = page.locator('.sidebar').bounding_box()
            assert first['x'] >= sidebar['x'] + sidebar['width'] + 23
        elif width < 760:
            assert second['y'] >= first['y'] + first['height']
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        composer = page.locator('.input-section').bounding_box()
        assert 0 <= composer['x'] and composer['x'] + composer['width'] <= width + 1
        assert composer['y'] + composer['height'] <= height + 1
        output = Path('test-results/direct-comparison-preview')
        output.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(output / f'{width}-{theme}.png'), full_page=True)
        # Every model remains reachable above the sticky/fixed composer.
        cards.last.scroll_into_view_if_needed()
        page.evaluate('window.scrollTo(0, document.documentElement.scrollHeight)')
        assert cards.last.bounding_box()['y'] + cards.last.bounding_box()['height'] <= page.locator('.input-section').bounding_box()['y'] + 1
        toggle.click()
        expect(intro).to_be_hidden()
        expect(draft).to_have_value('Compare the alternatives for my next project.')
        settle(page)
        assert page.evaluate("document.body.classList.contains('is-hero')")
        # Keyboard activation works and reduced motion makes the switch instant.
        page.emulate_media(reduced_motion='reduce')
        toggle.focus()
        page.keyboard.press('Space')
        expect(intro).to_be_visible()
        assert page.locator('#modelAnswerReader').evaluate('el => getComputedStyle(el).animationName') == 'none'
        assert not page.evaluate("document.body.classList.contains('comparison-layout-changing')")
        assert requests == []
        seed_reader(page, direct=True)
        expect(intro).to_be_hidden()
        expect(page.locator('.is-direct .answer-reader-answer')).to_have_count(3)
        expect(page.locator('#answerReaderColumns')).to_contain_text('Original answer')
        toggle.click()
        expect(page.locator('#answerReaderColumns')).to_contain_text('Original answer')
        assert errors == []
    finally:
        context.close()


def test_persisted_off_new_comparison_and_model_selection(browser, phase4_server):
    context, page = _real_firebase_page(browser, phase4_server,
        init_script="localStorage.setItem('agentMode','false');")
    try:
        intro = page.locator('#answerReaderPreviewIntro')
        cards = page.locator('.is-preview .answer-reader-answer')
        expect(intro).to_be_visible()
        expect(cards).to_have_count(6)
        page.evaluate("""() => {
          const pref = App.modelPrefs.find(p => document.getElementById(p.checkId).checked);
          document.getElementById(pref.checkId).click();
        }""")
        expect(cards).to_have_count(5)
        page.evaluate("document.getElementById('newRunButton').click()")
        expect(intro).to_be_visible()
        expect(cards).to_have_count(5)
        page.evaluate("""() => {
          for (let i = 0; i < 8; i++) setAgentMode(i % 2 === 0, {persist:true});
        }""")
        expect(intro).to_be_visible()
        settle(page)
        assert page.evaluate('App.runRegistry.visible()') is None
    finally:
        context.close()
