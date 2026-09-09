"""Public input previews stay aligned with the app's starting toolbar."""
from pathlib import Path

import pytest
from playwright.sync_api import expect

from test_phase4_frontend import phase4_server  # noqa: F401


def scroll_ask(page, progress):
    page.evaluate("""progress => {
        const scene = document.querySelector('[data-scene="ask"]');
        const stage = scene.querySelector('.lp-scene-stage');
        const top = scene.getBoundingClientRect().top + scrollY;
        const travel = scene.offsetHeight - stage.offsetHeight;
        const target = travel > 40 ? top + progress * travel
          : top - innerHeight * .82 + progress * (scene.offsetHeight + innerHeight * .5);
        window.scrollTo({top: target, behavior: 'instant'});
    }""", progress)
    page.wait_for_function("""progress => {
        const value = parseFloat(document.querySelector('[data-scene="ask"]').style.getPropertyValue('--sp'));
        return Math.abs(value - progress) < .03;
    }""", arg=progress)


@pytest.mark.parametrize('width,dark,reduced', [
    (1440, False, False), (1440, True, False), (390, False, False),
    (320, True, False), (390, True, True),
])
def test_public_composer_mockups(browser, phase4_server, width, dark, reduced):
    context = browser.new_context(viewport={'width': width, 'height': 900},
        reduced_motion='reduce' if reduced else 'no-preference')
    context.add_init_script("localStorage.setItem('theme', '" + ('dark' if dark else 'light') + "')")
    context.route('https://cloud.umami.is/**', lambda route: route.fulfill(body=''))
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    try:
        page.goto(phase4_server + '/', wait_until='networkidle')
        page.evaluate('() => document.fonts.ready')
        expect(page.locator('.lp-composer-tools')).to_have_count(2)
        expect(page.locator('#heroDemoField')).to_have_attribute('href', '/app?demo=1')
        previews = page.locator('.lp-composer-preview')
        for preview in previews.all():
            bar = preview.locator('.lp-composer-tools')
            expect(bar.locator('.lp-composer-tool').nth(1)).to_have_attribute('aria-label', 'Check Sources on')
            expect(bar.locator('img')).to_have_count(6)
            assert bar.evaluate('el => el.scrollWidth <= el.clientWidth + 1')
            assert bar.evaluate('el => Math.abs(el.getBoundingClientRect().height - 36) < 1')
            assert bar.evaluate('el => [...el.querySelectorAll("img")].every(img => img.complete && img.naturalWidth > 0)')
            geometry = bar.evaluate("""el => {
                const bar = el.getBoundingClientRect(), field = el.previousElementSibling.getBoundingClientRect();
                return {gap: bar.top - field.bottom, inset: bar.left - field.left, width: field.width - bar.width};
            }""")
            assert abs(geometry['gap']) < 1
            assert abs(geometry['inset'] - 12) < 1
            assert abs(geometry['width'] - 24) < 1
        output = Path('test-results/public-composer-mockups')
        output.mkdir(parents=True, exist_ok=True)
        suffix = f'{width}-{"dark" if dark else "light"}-{"still" if reduced else "motion"}'
        previews.nth(0).screenshot(path=str(output / f'hero-{suffix}.png'))
        ask_bar = page.locator('[data-scene="ask"] .lp-composer-tools')
        if reduced:
            expect(ask_bar).to_be_visible()
            assert ask_bar.evaluate('el => getComputedStyle(el).animationName') == 'none'
            ask_bar.scroll_into_view_if_needed()
        else:
            scroll_ask(page, .65)
            expect(ask_bar).to_have_attribute('aria-hidden', 'false')
        expect(ask_bar).to_be_visible()
        previews.nth(1).screenshot(path=str(output / f'ask-{suffix}.png'))
        if not reduced:
            scroll_ask(page, .96)
            expect(ask_bar).to_have_attribute('aria-hidden', 'true')
            expect(ask_bar).to_be_hidden()
            scroll_ask(page, .65)
            expect(ask_bar).to_be_visible()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), page.evaluate("""() => [...document.querySelectorAll('body *')].filter(el => {
            const r = el.getBoundingClientRect(); return r.width && r.right > innerWidth + 1;
        }).slice(0, 12).map(el => ({tag:el.tagName, cls:el.className, right:el.getBoundingClientRect().right}))""")
        page.goto(phase4_server + '/consensus-engine', wait_until='networkidle')
        expect(page.locator('.public-product-result')).to_be_visible()
        expect(page.locator('.lp-composer-tools')).to_have_count(0)
        expect(page.get_by_role('heading', name='Can I turn the source check off?')).to_have_count(1)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        assert errors == []
    finally:
        context.close()
