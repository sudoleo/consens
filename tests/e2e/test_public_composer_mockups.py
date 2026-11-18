"""Public input previews stay aligned with the app's start screen: one field, one row."""
import re
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
        # No chat model chip in the mockups, so no reasoning level either: in
        # /app it stands beside the model's name.
        expect(page.locator('.lp-composer-preview .lp-composer-models')).to_have_count(3)
        expect(page.locator('.lp-composer-preview svg path[d^="M12 5.5a3 3"]')).to_have_count(0)
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
        previews = page.locator('.lp-composer-preview:has(.lp-composer-models)')
        # The hero, the demo's scene and the closing field show Daily's two
        # reviewers (Claude and DeepSeek, the app's default and the demo's
        # lineup).
        for preview, marks in zip(previews.all(), (2, 2, 2), strict=True):
            field = preview.locator(':scope > :is(.lp-prompt, .lp-composer)')
            # The mode lives in the (+) menu, as in /app.
            expect(preview.locator('.lp-mode-chip')).to_have_count(0)
            # The reviewers' marks stand inside the field, before their words
            # (no chevron: the words are no picker of their own, as in /app).
            models = field.locator('.lp-composer-models')
            expect(models.locator('img')).to_have_count(marks)
            assert models.evaluate('el => [...el.querySelectorAll("img")].every(img => img.complete && img.naturalWidth > 0)')
            assert models.evaluate('el => el.nextElementSibling.classList.contains("lp-run-chip")')
            expect(field.locator('.lp-run-chip')).to_have_text('2 AIs cross-check')
            expect(field.locator('.lp-run-chip i')).to_have_count(0)
            # One field, one row: nothing below the field's own edge.
            assert preview.evaluate("""el => {
                const field = el.firstElementChild.getBoundingClientRect();
                return Math.abs(el.getBoundingClientRect().bottom - field.bottom) < 1;
            }""")
            if width > 640:
                # (+), the marks and the reviewers' words share one line.
                centres = field.evaluate("""el => [':is(.lp-attach, .lp-icon-btn)', '.lp-composer-models', '.lp-run-chip']
                    .map(selector => { const r = el.querySelector(selector).getBoundingClientRect(); return r.top + r.height / 2; })""")
                assert max(centres) - min(centres) <= 2, centres
        output = Path('test-results/public-composer-mockups')
        output.mkdir(parents=True, exist_ok=True)
        suffix = f'{width}-{"dark" if dark else "light"}-{"still" if reduced else "motion"}'
        previews.nth(0).screenshot(path=str(output / f'hero-{suffix}.png'))
        # A phone leaves the count to the reviewers' words and shows no marks.
        ask_bar = page.locator('[data-scene="ask"] .lp-composer-models')
        ask_field = page.locator('[data-scene="ask"] .lp-composer')
        if reduced:
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
            'Should we buy the flat we rent, or keep renting and invest the difference?')
        previews.nth(1).screenshot(path=str(output / f'ask-{suffix}.png'))
        if not reduced and width > 640:
            # Sent, the marks stay before their words, as in a chat in /app.
            scroll_ask(page, .96)
            expect(page.locator('[data-scene="ask"] [data-ask-send]')).to_have_class(re.compile(r'(^|\s)is-pressed(\s|$)'))
            expect(ask_bar).to_be_visible()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), page.evaluate("""() => [...document.querySelectorAll('body *')].filter(el => {
            const r = el.getBoundingClientRect(); return r.width && r.right > innerWidth + 1;
        }).slice(0, 12).map(el => ({tag:el.tagName, cls:el.className, right:el.getBoundingClientRect().right}))""")
        page.goto(phase4_server + '/consensus-engine', wait_until='networkidle')
        expect(page.locator('.public-product-result')).to_be_visible()
        expect(page.locator('.lp-composer-models')).to_have_count(0)
        expect(page.get_by_role('heading', name='Is the consensus just the majority answer?')).to_have_count(1)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        assert errors == []
    finally:
        context.close()


@pytest.mark.parametrize('width,dark', [(1440, False), (390, True)])
def test_landing_tells_the_one_mode(browser, phase4_server, width, dark):
    """The Agent has one mode: one AI does the work, the AIs
    you choose check it. The page says so and shows no score or judge."""
    context = browser.new_context(viewport={'width': width, 'height': 900}, reduced_motion='reduce')
    context.add_init_script("localStorage.setItem('theme', '" + ('dark' if dark else 'light') + "')")
    context.route('https://cloud.umami.is/**', lambda route: route.fulfill(body=''))
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    try:
        page.goto(phase4_server + '/', wait_until='networkidle')
        expect(page.locator('h1')).to_have_text('One AI does the work. Several check it.')
        expect(page.locator('meta[property="og:image:alt"]')).to_have_attribute(
            'content', 'One AI does the work. Several check it. | consens.io')
        main = page.locator('main')
        for gone in ('/100', 'agreement score', 'separate judge', 'Partial agreement', '6 AIs', '3 AIs',
                     'Live from real runs', 'Proof, not promises', 'Why consens.io', 'leading AI providers'):
            expect(main).not_to_contain_text(gone)
        # No Model Pulse strip; the benchmark says what it measures, behind
        # the Watch scene its engine serves.
        expect(page.locator('#benchmark')).to_contain_text('not the agent’s answers')
        assert page.evaluate("""() => Boolean(document.getElementById('watch')
            .compareDocumentPosition(document.getElementById('benchmark')) & Node.DOCUMENT_POSITION_FOLLOWING)""")
        expect(page.locator('#benchmark a[href="/benchmark"]')).to_have_text('See the full benchmark')
        expect(page.locator('.lp-live-pulse')).to_have_count(0)
        # Scene 02 ends on the reviewers' marks and the row under the answer.
        run = page.locator('[data-run]')
        expect(run.locator('[data-run-clock]')).to_have_text('Thought for 17s')
        expect(run.locator('.cx-claim.is-audit.is-major')).to_have_count(1)
        expect(run.locator('[data-run-evidence]')).to_contain_text('Notes 3')
        expect(run.locator('[data-run-evidence]')).to_contain_text('Answers 2')
        # Daily's two reviewers beside the clock, and the two AIs it asked.
        expect(run.locator('[data-reviewer]')).to_have_count(2)
        expect(run.locator('[data-run-count]')).to_have_text('2 answers')
        # The run shows its search, its workspace (the script it wrote and
        # ran) and what it shared, as the demo does: the chart in the answer,
        # whole in the still frame, and the spreadsheet under it.
        expect(run.locator('[data-run-item="search"]')).to_have_text(
            'Searched the web · 3 sources: leipzig.de, finanztip.de, homeday.de')
        expect(run.locator('[data-run-item="workspace"]')).to_have_text(
            'Opened the workspace · Calculate 30 years of buying and renting')
        expect(run.locator('[data-run-item="write"]')).to_have_text('Wrote the file buy_vs_rent.py')
        expect(run.locator('[data-run-item="command"]')).to_contain_text('python buy_vs_rent.py')
        chart = run.locator('[data-run-chart]')
        expect(chart).to_be_visible()
        expect(chart).to_have_class(re.compile(r'(^|\s)is-drawn(\s|$)'))
        expect(chart.locator('.lp-agent-chart-note')).to_have_text('Buying pulls ahead in year 9')
        expect(chart.locator('.lp-agent-chart-end')).to_have_text(['€485k', '€379k'])
        assert chart.evaluate("""el => { const lines = el.querySelector('.lp-agent-chart-lines').getBoundingClientRect();
            const plot = el.querySelector('.lp-agent-chart-plot').getBoundingClientRect();
            return lines.width > 150 && Math.abs(lines.width - plot.width) < 1 && plot.height >= 96; }""")
        expect(run.locator('[data-run-files]')).to_contain_text('buy-vs-rent.xlsx')
        expect(run.locator('[data-run-files]')).to_contain_text('Excel · 2 sheets')
        expect(run.locator('[data-run-closing]')).to_be_visible()
        # Decide: the marked sentence opens the reviewer's note.
        mark = page.locator('[data-diff-open="lpNoteTax"]')
        mark.scroll_into_view_if_needed()
        mark.click()
        expect(page.locator('#lpNoteTax')).to_have_attribute('open', '')
        expect(page.locator('#lpNoteTax')).to_contain_text('Saxony has charged 5.5% since January 2023.')
        expect(page.locator('#lpNoteTax')).to_contain_text('Claude · Wrong')
        # The pause is the fifth step of the list, a picture beside its words.
        expect(page.locator('.lp-steps > .lp-step')).to_have_count(5)
        expect(page.locator('.lp-steps .lp-pause-title')).to_have_text('A reviewer paused before a step')
        output = Path('test-results/landing-one-mode')
        output.mkdir(parents=True, exist_ok=True)
        suffix = f'{width}-{"dark" if dark else "light"}'
        page.locator('.lp-scene-02 .lp-scene-visual').screenshot(path=str(output / f'run-{suffix}.png'))
        page.locator('.lp-scene-03').screenshot(path=str(output / f'decide-{suffix}.png'))
        page.locator('.lp-section--hero').screenshot(path=str(output / f'hero-{suffix}.png'))
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
    # scrolling, Product and Watches moved by up to 1.8 px. Every link keeps
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
