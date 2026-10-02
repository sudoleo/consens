"""Public Topic interactions with original JS/CSS and a controlled SSR fixture."""
from html import escape
from pathlib import Path

import pytest
from playwright.sync_api import expect

ROOT = Path(__file__).resolve().parents[2]
HOSTILE = '<img src=x onerror="window.__injected=1"><span id="injected">A & B</span>'


def topic_page(browser, *, touch=False, historical=False, blocked=False, seen=None):
    context = browser.new_context(has_touch=touch, viewport={"width": 390 if touch else 1280, "height": 800})
    errors = []
    page = context.new_page()
    page.on('pageerror', lambda error: errors.append(str(error)))
    context.route('https://topics.test/**', lambda route: route.fulfill(content_type='text/html', body=f'''<!doctype html>
      <style>.topic-strip-cell{{display:inline-block;width:48px;height:48px;background:gray}}</style>
      <div id="topicStrip" class="topic-strip" data-slug="example">
      <a class="topic-strip-cell" id="old" href="?version=old" data-iso="2026-07-01" data-date="Jul 1" data-note="First" data-kind="first"></a>
      <a class="topic-strip-cell" id="new" href="?version=new" data-iso="2026-07-08" data-date="Jul 8" data-score="72" data-kind="material" data-note="{escape(HOSTILE, quote=True)}"></a></div>
      <p id="topicStripRead" role="status">Resting line</p><section id="topicReturn" hidden></section><section id="facts">Statements</section>'''))
    page.goto('https://topics.test/topics/example' + ('?version=old' if historical else ''))
    if seen:
        page.evaluate('(seen) => localStorage.setItem("topic-seen:example", seen)', seen)
    if blocked:
        page.evaluate('Object.defineProperty(window, "localStorage", {get(){throw new Error("Storage denied")}})')
    page.add_script_tag(content=(ROOT / 'static/js/topic-page.js').read_text(encoding='utf-8'))
    return context, page, errors


@pytest.mark.parametrize('touch', [False, True])
def test_topic_markup_stays_text_and_preview_preserves_navigation(browser, touch):
    context, page, errors = topic_page(browser, touch=touch)
    try:
        cell = page.locator('#new')
        if touch:
            cell.tap()
            assert '?' not in page.url  # first touch previews rather than navigating
        else:
            cell.focus()
        expect(page.locator('#topicStripRead')).to_contain_text(HOSTILE)
        expect(page.locator('#topicStripRead .topic-strip-score')).to_have_text('72/100 agreement')
        expect(page.locator('#injected, #topicStripRead img')).to_have_count(0)
        assert page.evaluate('window.__injected') is None
        if touch:
            cell.tap()
        else:
            page.keyboard.press('Enter')
        expect(page).to_have_url('https://topics.test/topics/example?version=new')
        assert not errors
    finally:
        context.close()


@pytest.mark.parametrize('historical,blocked', [(False, False), (True, False), (False, True)])
def test_topic_returning_reader_respects_historical_and_blocked_storage(browser, historical, blocked):
    context, page, errors = topic_page(browser, historical=historical, blocked=blocked, seen='2026-07-02')
    try:
        if historical or blocked:
            expect(page.locator('#topicReturn')).to_be_hidden()
            expect(page.locator('.is-unseen')).to_have_count(0)
        else:
            expect(page.locator('#topicReturn')).to_contain_text('1 check since your last visit')
            expect(page.locator('#new')).to_have_class('topic-strip-cell is-unseen')
            page.get_by_role('link', name='See the statements').click()
            assert page.url.endswith('#facts')
        if not blocked:
            assert page.evaluate('localStorage.getItem("topic-seen:example")') == ('2026-07-02' if historical else '2026-07-08')
        page.locator('#new').focus()
        expect(page.locator('#topicStripRead')).to_contain_text(HOSTILE)
        assert not errors
    finally:
        context.close()
