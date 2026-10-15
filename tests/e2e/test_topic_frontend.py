"""Public Topic interactions with the original JS and a controlled fixture.

Since 2026-10-15 a Topic page is built from the Watch page parts; its scripts
are check-page.js (shared) and topic-page.js (the follow form).
"""
import json
from pathlib import Path

import pytest
from playwright.sync_api import expect

ROOT = Path(__file__).resolve().parents[2]
HOSTILE = '<img src=x onerror="window.__injected=1"><span id="injected">A & B</span>'


def topic_page(browser, *, touch=False):
    context = browser.new_context(has_touch=touch, viewport={"width": 390 if touch else 1280, "height": 800})
    errors = []
    page = context.new_page()
    page.on('pageerror', lambda error: errors.append(str(error)))
    sources = "".join(f'<li id="src-{n}">Source {n}</li>' for n in range(1, 8))
    context.route('https://topics.test/**', lambda route: route.fulfill(content_type='text/html', body=f'''<!doctype html>
      <ol id="shareSources" class="share-sources">{sources}</ol>
      <button type="button" id="shareSourcesToggle" hidden>Show all 7 sources</button>
      <form id="topicFollowForm" data-slug="example">
        <input id="topicFollowEmail" name="email" type="email" value="reader@example.com">
        <button type="submit">Follow</button>
      </form>
      <p id="topicFollowStatus" role="status" hidden></p>'''))
    context.route('https://topics.test/api/topics/example/follow', lambda route: route.fulfill(
        content_type='application/json', body=json.dumps({"status": "success", "message": HOSTILE})))
    page.goto('https://topics.test/topics/example')
    for name in ('check-page.js', 'topic-page.js'):
        page.add_script_tag(content=(ROOT / 'static/js' / name).read_text(encoding='utf-8'))
    return context, page, errors


@pytest.mark.parametrize('touch', [False, True])
def test_topic_follow_prints_the_reply_as_text_and_sources_unfold(browser, touch):
    context, page, errors = topic_page(browser, touch=touch)
    try:
        toggle = page.locator('#shareSourcesToggle')
        expect(toggle).to_be_visible()
        if touch:
            toggle.tap()
        else:
            toggle.click()
        expect(toggle).to_be_hidden()

        page.locator('#topicFollowForm button').click()
        status = page.locator('#topicFollowStatus')
        expect(status).to_have_text(HOSTILE)
        expect(page.locator('#injected, #topicFollowStatus img')).to_have_count(0)
        expect(page.locator('#topicFollowForm')).to_be_hidden()
        assert page.evaluate('window.__injected') is None
        assert not errors
    finally:
        context.close()
