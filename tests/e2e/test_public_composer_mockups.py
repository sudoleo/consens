"""The landing page is one chat with the app's field docked under it, and the
public input previews stay aligned with the app's start screen: one field,
one row."""
from pathlib import Path

import pytest
from playwright.sync_api import expect

from test_phase4_frontend import phase4_server  # noqa: F401


def scroll_to(page, selector, share):
    """Bring the top of `selector` to `share` of the window's height, in
    steps as a hand scrolls, so every piece on the way has been in view."""
    page.evaluate("""async ([selector, share]) => {
        const target = document.querySelector(selector).getBoundingClientRect().top + scrollY - innerHeight * share;
        const start = scrollY;
        for (let step = 1; step <= 8; step += 1) {
            window.scrollTo({top: start + (target - start) * step / 8, behavior: 'instant'});
            await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        }
    }""", [selector, share])


@pytest.mark.parametrize('width,dark,reduced', [
    (1440, False, False), (1440, True, False), (390, False, False),
    (320, True, False), (390, True, True),
])
def test_landing_field_is_docked_like_the_app_composer(browser, phase4_server, width, dark, reduced):
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
        field = page.locator('#landingField')
        # The field opens the app with the caret in the composer. It is the
        # one way into the app besides the bar's button.
        expect(field).to_have_attribute('href', '/app?focus=1')
        expect(page.locator('main a[href^="/app"]')).to_have_count(1)
        # No chat model chip, so no reasoning level either: in /app it stands
        # beside the model's name. The mode lives in the (+) menu.
        expect(field.locator('svg path[d^="M12 5.5a3 3"]')).to_have_count(0)
        expect(field.locator('.lp-mode-chip')).to_have_count(0)
        # Daily's two reviewers (Claude and DeepSeek, the app's default)
        # before their words, no chevron: the words are no picker of their own.
        models = field.locator('.lp-composer-models')
        expect(models.locator('img')).to_have_count(2)
        assert models.evaluate('el => [...el.querySelectorAll("img")].every(img => img.complete && img.naturalWidth > 0)')
        assert models.evaluate('el => el.nextElementSibling.classList.contains("lp-run-chip")')
        expect(field.locator('.lp-run-chip')).to_have_text('2 AIs cross-check')
        expect(field.locator('.lp-run-chip i')).to_have_count(0)
        # A phone leaves the count to the reviewers' words and shows no marks.
        if width > 640:
            expect(models).to_be_visible()
        else:
            expect(models).to_be_hidden()
        # One row at every width: (+), the reviewers' words and Send.
        centres = field.evaluate("""el => ['.lp-icon-btn', '.lp-run-chip', '.lp-send']
            .map(selector => { const r = el.querySelector(selector).getBoundingClientRect(); return r.top + r.height / 2; })""")
        assert max(centres) - min(centres) <= 2, centres

        def docked():
            return field.evaluate("""el => { const r = el.getBoundingClientRect();
                return r.bottom <= innerHeight && r.bottom > innerHeight - 60 && r.left >= 0 && r.right <= innerWidth; }""")

        # Docked from the first frame and all the way down the thread.
        assert docked()
        box = field.bounding_box()
        hit = page.evaluate('([x, y]) => document.elementFromPoint(x, y)?.closest("a")?.id',
            [box['x'] + box['width'] / 2, box['y'] + 24])
        assert hit == 'landingField'
        scroll_to(page, '#review', .2)
        assert docked()
        output = Path('test-results/public-composer-mockups')
        output.mkdir(parents=True, exist_ok=True)
        suffix = f'{width}-{"dark" if dark else "light"}-{"still" if reduced else "motion"}'
        field.screenshot(path=str(output / f'docked-{suffix}.png'))
        # At the end it rests under the last line of the page.
        page.evaluate("window.scrollTo({top: document.documentElement.scrollHeight, behavior: 'instant'})")
        assert page.evaluate("""() => {
            const last = document.querySelector('.lc-beat--end').getBoundingClientRect();
            const field = document.getElementById('landingField').getBoundingClientRect();
            const footer = document.querySelector('footer').getBoundingClientRect();
            return last.bottom <= field.top && field.bottom <= footer.top && field.top - last.bottom < 80;
        }""")
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
    """The Agent has one mode: one AI does the work, the AIs you choose check
    it. The page says so as one chat and shows no score or judge. Under
    reduced motion it stands in its last frame."""
    context = browser.new_context(viewport={'width': width, 'height': 900}, reduced_motion='reduce')
    context.add_init_script("localStorage.setItem('theme', '" + ('dark' if dark else 'light') + "')")
    context.route('https://cloud.umami.is/**', lambda route: route.fulfill(body=''))
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    try:
        page.goto(phase4_server + '/', wait_until='networkidle')
        expect(page.locator('h1')).to_have_text('One AI does the work. Several check it.')
        expect(page.locator('.lc-intro .lp-hero-kind')).to_have_text('Agent harness')
        expect(page.locator('meta[property="og:image:alt"]')).to_have_attribute(
            'content', 'One AI does the work. Several check it. | consens.io')
        main = page.locator('main')
        for gone in ('/100', 'agreement score', 'separate judge', 'Partial agreement', '6 AIs', '3 AIs',
                     'Live from real runs', 'Proof, not promises', 'Why consens.io', 'leading AI providers'):
            expect(main).not_to_contain_text(gone)
        # No Model Pulse strip and no benchmark section; the benchmark has its
        # own page, linked from the footer.
        expect(page.locator('#benchmark')).to_have_count(0)
        expect(page.locator('.lp-live-pulse')).to_have_count(0)
        expect(page.locator('footer a[href="/benchmark"]')).to_have_count(1)
        # One thread of chapters, nothing armed: no piece waits to appear.
        assert page.evaluate("() => [...document.querySelectorAll('section.lc-part')].map(el => el.id)") == [
            'workspace', 'review', 'files', 'browser', 'watch', 'models']
        assert not page.evaluate("() => document.documentElement.classList.contains('lc-js')")
        assert page.evaluate("""() => [...document.querySelectorAll('[data-reveal]')]
            .every(el => getComputedStyle(el).opacity === '1')""")
        # 01: the agent's own computer, the answer in figures, the plan.
        workspace = page.locator('#workspace')
        expect(workspace.locator('.lc-ws-tabs .is-active')).to_have_text('Terminal')
        expect(workspace.locator('.lc-ws-terminal')).to_contain_text('python plan_trip.py')
        expect(workspace.locator('.md-figures dd')).to_have_text(['€1,210', '€290', '17 h'])
        expect(workspace.locator('table.md-timeline tbody tr')).to_have_count(5)
        # 02: the reviewers' one mark on the plan and the note under it; the
        # days nobody objected to keep a readable ink.
        review = page.locator('#review')
        expect(review.locator('.lc-review-state [data-when="found"]')).to_be_visible()
        expect(review.locator('.lc-review-state [data-when="reviewing"]')).to_be_hidden()
        expect(review.locator('.cx-claim.is-audit.is-major')).to_have_text('The Stelvio Pass.')
        expect(review.locator('.lc-note')).to_contain_text('usually reopens at the end of May')
        expect(review.locator('.lc-note')).to_be_visible()
        expect(review.locator('.lc-fixed')).to_contain_text('Lake Resia.')
        assert review.evaluate("""el => {
            const mark = getComputedStyle(el.querySelector('.cx-claim')).backgroundSize;
            const quiet = getComputedStyle(el.querySelector('.lc-claims tbody tr td:last-child')).color;
            const loud = getComputedStyle(el.querySelector('.lc-claims tr.is-hit td:last-child')).color;
            return mark === '100% 100%' && quiet !== loud;
        }""")
        # No photo beside the finding: it is what this chapter is about.
        expect(page.locator('#review img[src*="/static/landing/"]')).to_have_count(0)
        # 03 and 04: a real file in its preview, the browser stopped at the payment.
        expect(page.locator('#files .lc-viewer')).to_contain_text('south-tyrol.pptx')
        expect(page.locator('#files .lc-viewer')).to_contain_text('PowerPoint · 6 slides')
        expect(page.locator('#browser .lc-ws-tabs .is-active')).to_have_text('Browser')
        expect(page.locator('#browser .lc-ws-turn')).to_contain_text('The agent stopped at the payment')
        expect(page.locator('#browser .lc-ws-take')).to_have_text('Take over')
        # 05: the Watch card in its running state, then what the Watch sent.
        card = page.locator('#watch .lc-watchcard')
        expect(card).to_have_attribute('data-state', 'watching')
        expect(card.get_by_text('Watch running')).to_be_visible()
        expect(card.get_by_text('Start Watch')).to_be_hidden()
        expect(page.locator('#watch')).to_contain_text('The Stelvio Pass is open.')
        # The model families, each with its mark.
        expect(page.locator('#models .lp-logo')).to_have_count(11)
        # Every photo loads once it has come into view, with its credit.
        page.evaluate("""async () => {
            for (let y = 0; y <= document.documentElement.scrollHeight; y += 500) {
                window.scrollTo({top: y, behavior: 'instant'});
                await new Promise(resolve => setTimeout(resolve, 60));
            }
        }""")
        page.wait_for_function("""() => [...document.querySelectorAll('img[src*="/static/landing/"]')]
            .every(img => img.complete && img.naturalWidth > 0)""")
        expect(page.locator('img[src*="/static/landing/"]')).to_have_count(5)
        expect(page.locator('.lc-credit a[href^="https://commons.wikimedia.org/wiki/File:"]')).to_have_count(5)
        output = Path('test-results/landing-one-mode')
        output.mkdir(parents=True, exist_ok=True)
        suffix = f'{width}-{"dark" if dark else "light"}'
        page.locator('.lc-intro').screenshot(path=str(output / f'hero-{suffix}.png'))
        page.locator('#review .lc-claims').screenshot(path=str(output / f'review-{suffix}.png'))
        page.locator('#watch .lc-watchcard').screenshot(path=str(output / f'watch-{suffix}.png'))
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        assert errors == []
    finally:
        context.close()


@pytest.mark.parametrize('width', [1440, 390])
def test_landing_plays_the_review_and_starts_the_watch_along_the_scroll(browser, phase4_server, width):
    context = browser.new_context(viewport={'width': width, 'height': 900})
    context.route('https://cloud.umami.is/**', lambda route: route.fulfill(body=''))
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    try:
        page.goto(phase4_server + '/', wait_until='networkidle')
        page.evaluate('() => document.fonts.ready')
        review = page.locator('#review .lc-review')
        expect(review).to_have_attribute('data-phase', 'plain')
        # Before the review the plan reads whole: the days after the note
        # stand right under day 3.
        scroll_to(page, '#review', .1)
        # The cells are what moves (a transform, no new layout), so they are
        # what is measured.
        rows = "() => [...document.querySelectorAll('#review .lc-claims tbody tr:not(.lc-note-row) > td:last-child')].map(cell => cell.getBoundingClientRect().top)"
        before = page.evaluate(rows)
        gaps = [b - a for a, b in zip(before, before[1:])]
        assert max(gaps) - min(gaps) < 40, gaps
        # The next chapter's own box: it carries no offset of a piece that
        # is still to appear.
        under = "() => document.getElementById('files').getBoundingClientRect().top + scrollY"
        resting = page.evaluate(under)
        # The review plays once the place of the note is in view: the
        # reviewers read, then their finding is there.
        scroll_to(page, '#review .lc-claims', .16)
        expect(review).to_have_attribute('data-phase', 'found', timeout=5000)
        expect(review.locator('.lc-note')).to_be_visible()
        page.wait_for_function("() => getComputedStyle(document.querySelector('#review .lc-note')).opacity === '1'")
        after = page.evaluate(rows)
        assert after[3] - after[2] > gaps[2] + 60, (before, after)
        # The correction waits until the finding has landed, then comes like
        # any other piece: once it stands above the field (on a phone it is
        # still under it). Nothing under the plan has moved for the note.
        fixed = review.locator('.lc-fixed')
        expect(fixed).to_have_class('lp-agent-answer lc-answer lc-fixed')
        expect(review).to_have_attribute('data-settled', 'true', timeout=5000)
        scroll_to(page, '#review .lc-fixed', .5)
        expect(fixed).to_have_class('lp-agent-answer lc-answer lc-fixed is-in', timeout=5000)
        assert abs(page.evaluate(under) - resting) < 1
        # The Watch card: its proposal while it comes up, the running Watch
        # once it has stood in view, and back again with the scroll.
        card = page.locator('#watch .lc-watchcard')
        scroll_to(page, '#watch .lc-watchcard', .7)
        expect(card).to_have_attribute('data-state', 'proposal')
        expect(card.get_by_text('Start Watch')).to_be_visible()
        height = card.bounding_box()['height']
        scroll_to(page, '#watch .lc-watchcard', .2)
        expect(card).to_have_attribute('data-state', 'watching')
        expect(card.get_by_text('Watch running')).to_be_visible()
        assert abs(card.bounding_box()['height'] - height) < 1
        scroll_to(page, '#watch .lc-watchcard', .7)
        expect(card).to_have_attribute('data-state', 'proposal')
        assert errors == []
    finally:
        context.close()


@pytest.mark.parametrize('width', [375, 390])
def test_landing_never_pans_sideways_while_scrolling(browser, phase4_server, width):
    # A piece that is wider than a phone (the terminal's columns, a figure
    # that does not break) would widen the page and let it pan sideways.
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
            const marks = [];
            for (const id of ['review', 'watch']) {
                const part = document.getElementById(id);
                window.scrollTo({top: part.getBoundingClientRect().top + scrollY, behavior: 'instant'});
                await frame(); await frame();
                marks.push(read());
            }
            return [top, ...marks];
        }""")
        top, harness, watch = boxes
        # The chapters of the agent at work are one part of the page, the
        # Watch another.
        assert top['current'] == ['Product'] and harness['current'] == ['Harness'] and watch['current'] == ['Watches']
        assert watch['boxes'] == top['boxes'] == harness['boxes']
        # The invisible second line does not reach the accessible name.
        expect(page.get_by_role('link', name='Product', exact=True)).to_have_count(1)
    finally:
        context.close()
