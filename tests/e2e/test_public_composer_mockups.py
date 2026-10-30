"""Public input previews stay aligned with the app's start screen: one field, one row."""
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
        expect(page.locator('.lp-composer-preview > .lp-composer-tools')).to_have_count(0)
        # The field opens the app with the caret in the composer; only the demo
        # button starts the demo, and it sits above the field's link.
        expect(page.locator('#heroAskField')).to_have_attribute('href', '/app?focus=1')
        expect(page.locator('#heroDemoButton')).to_have_attribute('href', '/app?demo=1')
        demo_box = page.locator('#heroDemoButton').bounding_box()
        hit = page.evaluate('([x, y]) => document.elementFromPoint(x, y)?.closest("a")?.id',
            [demo_box['x'] + demo_box['width'] / 2, demo_box['y'] + demo_box['height'] / 2])
        assert hit == 'heroDemoButton'
        field_box = page.locator('#heroField').bounding_box()
        hit = page.evaluate('([x, y]) => document.elementFromPoint(x, y)?.closest("a")?.id',
            [field_box['x'] + field_box['width'] / 2, field_box['y'] + 24])
        assert hit == 'heroAskField'
        previews = page.locator('.lp-composer-preview:has(.lp-composer-tools)')
        # The hero shows Daily's three marks (the app's default since
        # 2026-10-28); the heat-pump scene is a run with six.
        for preview, marks in zip(previews.all(), (3, 6), strict=True):
            field = preview.locator(':scope > :is(.lp-prompt, .lp-composer)')
            tools = field.locator('.lp-composer-tools')
            # The mode lives in the (+) menu (as in /app), so the row's tools
            # start with Reasoning. Its words are its name (a plain span may
            # not carry an aria-label, test_a11y_axe.py).
            tool = tools.locator('.lp-composer-tool')
            expect(tool).to_have_count(1)
            expect(tool).to_have_attribute('title', 'Reasoning auto · the model decides how long to think')
            assert tool.get_attribute('aria-label') is None
            expect(preview.locator('.lp-mode-chip')).to_have_count(0)
            # The marks stand inside the field, before the chip.
            models = field.locator('.lp-composer-models')
            expect(models.locator('img')).to_have_count(marks)
            assert models.evaluate('el => [...el.querySelectorAll("img")].every(img => img.complete && img.naturalWidth > 0)')
            assert models.evaluate('el => el.nextElementSibling.classList.contains("lp-run-chip")')
            # One field, one row: nothing below the field's own edge.
            assert preview.evaluate("""el => {
                const field = el.firstElementChild.getBoundingClientRect();
                return Math.abs(el.getBoundingClientRect().bottom - field.bottom) < 1;
            }""")
            if width > 700:
                expect(tools).to_be_visible()
                # (+), Reasoning, the marks and the chip share one line.
                centres = field.evaluate("""el => [':is(.lp-attach, .lp-icon-btn)', '.lp-composer-tool', '.lp-composer-models', '.lp-run-chip']
                    .map(selector => { const r = el.querySelector(selector).getBoundingClientRect(); return r.top + r.height / 2; })""")
                assert max(centres) - min(centres) <= 2, centres
                assert tools.evaluate('el => el.scrollWidth <= el.clientWidth + 1')
            else:
                # A phone keeps Reasoning in the (+) menu, as /app does.
                expect(tools).to_be_hidden()
        output = Path('test-results/public-composer-mockups')
        output.mkdir(parents=True, exist_ok=True)
        suffix = f'{width}-{"dark" if dark else "light"}-{"still" if reduced else "motion"}'
        previews.nth(0).screenshot(path=str(output / f'hero-{suffix}.png'))
        # The marks leave with the tools after send. A phone, as /app, leaves
        # the count to the chip's words and shows no marks.
        ask_bar = page.locator('[data-scene="ask"] .lp-composer-models')
        ask_field = page.locator('[data-scene="ask"] .lp-composer')
        if reduced:
            assert page.locator('[data-scene="ask"] .lp-composer-tools').evaluate('el => getComputedStyle(el).animationName') == 'none'
            ask_field.scroll_into_view_if_needed()
        else:
            scroll_ask(page, .65)
        expect(ask_field.locator('.lp-run-chip')).to_be_visible()
        if width > 640:
            expect(ask_bar).to_be_visible()
        else:
            expect(ask_bar).to_be_hidden()
        # A screen reader reads the finished scene in words, never a frame
        # of the typing (a11y audit P2).
        expect(page.locator('[data-scene="ask"] .lp-ask-stage')).to_have_attribute('aria-hidden', 'true')
        expect(page.locator('[data-scene="ask"] .lp-sr')).to_contain_text(
            'Can a heat pump heat our 1978 house with the original radiators?')
        previews.nth(1).screenshot(path=str(output / f'ask-{suffix}.png'))
        if not reduced and width > 640:
            scroll_ask(page, .96)
            expect(ask_bar).to_be_hidden()
            scroll_ask(page, .65)
            expect(ask_bar).to_be_visible()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), page.evaluate("""() => [...document.querySelectorAll('body *')].filter(el => {
            const r = el.getBoundingClientRect(); return r.width && r.right > innerWidth + 1;
        }).slice(0, 12).map(el => ({tag:el.tagName, cls:el.className, right:el.getBoundingClientRect().right}))""")
        page.goto(phase4_server + '/consensus-engine', wait_until='networkidle')
        expect(page.locator('.public-product-result')).to_be_visible()
        expect(page.locator('.lp-composer-tools')).to_have_count(0)
        expect(page.get_by_role('heading', name='Is the consensus just the majority answer?')).to_have_count(1)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        assert errors == []
    finally:
        context.close()


@pytest.mark.parametrize('width', [375, 390])
def test_landing_never_pans_sideways_while_scrolling(browser, phase4_server, width):
    # The pinned scenes' progress rail carried its light 6px past its tip;
    # at a full rail that widened the page and a phone panned sideways.
    context = browser.new_context(viewport={'width': width, 'height': 812})
    context.route('https://cloud.umami.is/**', lambda route: route.fulfill(body=''))
    page = context.new_page()
    try:
        page.goto(phase4_server + '/', wait_until='networkidle')
        widest = page.evaluate("""async () => {
            let widest = 0;
            for (let y = 0; y < document.documentElement.scrollHeight; y += 200) {
                window.scrollTo({top: y, behavior: 'instant'});
                await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
                widest = Math.max(widest, document.documentElement.scrollWidth);
            }
            return widest;
        }""")
        assert widest <= width
    finally:
        context.close()


@pytest.mark.parametrize('width', [1440, 900])
def test_landing_bar_holds_still_when_it_marks_another_section(browser, phase4_server, width):
    # Semibold is wider: when the bar marked Watches instead of Product while
    # scrolling, Product and Watches moved by up to 1.8 px. Every link now keeps
    # the width of its semibold self.
    context = browser.new_context(viewport={'width': width, 'height': 900})
    context.route('https://cloud.umami.is/**', lambda route: route.fulfill(body=''))
    page = context.new_page()
    try:
        page.goto(phase4_server + '/', wait_until='networkidle')
        boxes = page.evaluate("""async () => {
            const frame = () => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
            const read = () => ({
                current: [...document.querySelectorAll('.site-nav .nav-links > a[aria-current]')].map(a => a.textContent),
                boxes: [...document.querySelectorAll('.site-nav .nav-links > a')].map(a => {
                    const r = a.getBoundingClientRect(); return [a.textContent.trim(), r.left, r.width]; }),
            });
            const top = read();
            const watch = document.getElementById('watch');
            window.scrollTo({top: watch.getBoundingClientRect().top + scrollY, behavior: 'instant'});
            await frame(); await frame();
            return [top, read()];
        }""")
        top, watch = boxes
        assert top['current'] == ['Product'] and watch['current'] == ['Watches']
        assert watch['boxes'] == top['boxes']
        # The invisible second line does not reach the accessible name.
        expect(page.get_by_role('link', name='Product', exact=True)).to_have_count(1)
    finally:
        context.close()
