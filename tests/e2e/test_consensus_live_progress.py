"""Real run markup/CSS in Chromium, with local simulated model events only.

No app server, authentication, LLM or Firestore requests are involved. The
browser loads the built app stylesheet and real progress module through a
route serving only repository static files.
"""

import json
import mimetypes
import os
import re
from pathlib import Path
from urllib.parse import urlparse

import pytest
from playwright.sync_api import expect

ROOT = Path(__file__).resolve().parents[2]
ORIGIN = "https://consens-progress.test"


@pytest.fixture
def progress_page(browser, request):
    context = browser.new_context(viewport={"width": 1280, "height": 800}, **getattr(request, "param", {}))
    template = (ROOT / "templates/index.html").read_text(encoding="utf-8")
    markup = re.search(r'<section id="consensusRun"[\s\S]*?</section>', template).group()
    css = json.loads((ROOT / "static/dist/manifest.json").read_text())["styles"]["app"]
    content = f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
      <link rel="stylesheet" href="{css}">
      <style>body {{ display:block; min-height:100vh; padding:24px 16px; }}
      main {{ max-width:720px; margin:0 auto; }}
      .response-section {{ display:none!important; }}</style></head>
      <body class="agent-mode-enabled"><main>{markup}</main><div class="response-section"></div></body></html>'''

    def serve(route):
        path = urlparse(route.request.url).path
        if path == "/":
            route.fulfill(content_type="text/html", body=content)
            return
        asset = (ROOT / path.lstrip("/")).resolve()
        if asset.is_relative_to(ROOT / "static") and asset.is_file():
            mime = mimetypes.guess_type(str(asset))[0] or "application/octet-stream"
            route.fulfill(body=asset.read_bytes(), content_type=mime + "; charset=utf-8")
        else:
            route.abort()

    context.route("**/*", serve)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(ORIGIN)
    page.evaluate('''() => {
      const models = ['OpenAI', 'Claude', 'Gemini', 'Mistral', 'Grok', 'DeepSeek'];
      document.querySelector('.response-section').innerHTML = models.map((name, i) =>
        `<div class="response-box" id="model-${i}" data-short-label="${name}" data-response-state="pending"><div class="collapsible-content"><span class="thinking-wrap">Waiting for a response</span></div></div>`).join('');
      window.App = { skipModel: id => { window.skippedModel = id; } };
      window.progressFixture = (id, text, state = 'pending') => {
        const box = document.getElementById('model-' + id);
        box.dataset.consensusAnswer = text;
        box.dataset.responseState = state;
        box.querySelector('.collapsible-content').classList.toggle('is-streaming', state === 'pending' && !!text);
        box.querySelector('.collapsible-content').textContent = text;
      };
    }''')
    page.add_script_tag(url=ORIGIN + "/static/js/consensus-progress.js")
    page.evaluate('''() => {
      App.consensusPipeline.onPrepare(Date.now() - 14000);
      App.consensusPipeline.onQueryStatus('running');
      progressFixture(0, 'A'.repeat(1234));
      progressFixture(1, 'B'.repeat(1782));
      progressFixture(2, 'Answer one', 'complete');
      progressFixture(3, 'Answer two', 'complete');
      progressFixture(4, '', 'reasoning');
    }''')
    expect(page.locator('[data-box="model-0"] .run-model-time')).to_have_text("Writing")
    expect(page.locator('[data-box="model-0"] .run-model-time')).to_have_attribute("title", "1,234 characters received so far")
    page.evaluate("() => document.fonts.ready")
    page.wait_for_function("getComputedStyle(document.getElementById('consensusRun')).transform === 'none'")
    yield page
    assert not errors
    context.close()


@pytest.mark.parametrize("width", [320, 390, 768, 1280])
@pytest.mark.parametrize("dark", [False, True])
def test_model_status_layout_and_phase_handoff(progress_page, width, dark):
    page = progress_page
    page.set_viewport_size({"width": width, "height": 850})
    page.evaluate("dark => document.body.classList.toggle('dark-mode', dark)", dark)
    expect(page.locator('[data-box="model-4"] .run-model-time')).to_have_text("Thinking")
    expect(page.locator('[data-box="model-5"] .run-model-time')).to_have_text("Waiting")
    expect(page.locator('[data-box="model-2"] .run-model-time')).to_have_text(re.compile(r"^\d+\.\ds$"))
    expect(page.locator('.run-step[data-step="prepare"]')).to_have_attribute("data-status", "done")
    expect(page.locator('.run-step[data-step="answers"]')).to_have_attribute("data-status", "active")
    expect(page.locator('.run-step[data-step="consensus"]')).to_have_attribute("data-status", "pending")
    expect(page.locator("#runCount")).to_have_text("2/6")
    expect(page.locator("#runMeta")).to_have_text("6 models")
    expect(page.locator("#runTrack")).not_to_be_visible()
    expect(page.locator("#runNote")).not_to_be_visible()
    # Wide: the stepper names every step. Narrow: one line plus segments.
    if width <= 640:
        expect(page.locator(".run-compact")).to_be_visible()
        expect(page.locator("#runCompactLabel")).to_have_text("Answering")
        expect(page.locator("#runMetaNext")).to_have_text("Next: consensus, then contradiction check")
        expect(page.locator(".run-step-label").first).not_to_be_visible()
    else:
        expect(page.locator(".run-compact")).not_to_be_visible()
        expect(page.locator(".run-step-label")).to_have_text(["Prepared", "Answers", "Consensus", "Contradiction check"])
        expect(page.locator("#runMetaNext")).not_to_be_visible()
    head = page.locator(".run-head").bounding_box()
    assert head["y"] + head["height"] <= page.locator("#runDetail").bounding_box()["y"]
    assert page.locator(".run-model").first.bounding_box()["height"] <= (40 if width <= 640 else 28)
    page.evaluate("() => progressFixture(0, 'A'.repeat(987654))")
    expect(page.locator('[data-box="model-0"] .run-model-time')).to_have_attribute("title", "987,654 characters received so far")
    expect(page.locator('[data-box="model-0"] .run-model-time')).to_have_text("Writing")
    assert page.evaluate('''() => {
      const rows = [...document.querySelectorAll('.run-model')];
      const timer = document.querySelector('#runTime').getBoundingClientRect();
      return document.documentElement.scrollWidth <= innerWidth && rows.every(row => {
        const name = row.querySelector('.run-model-name').getBoundingClientRect();
        const track = row.querySelector('.run-model-track').getBoundingClientRect();
        const status = row.querySelector('.run-model-time').getBoundingClientRect();
        const bounds = row.getBoundingClientRect();
        const layoutFits = innerWidth <= 640
          ? track.top >= Math.max(name.bottom, status.bottom)
            && Math.abs(track.width - bounds.width) < 1
          : name.right <= track.left && track.right <= status.left;
        return layoutFits
          && Math.abs(timer.right - status.right) < 1
          && status.right <= innerWidth && row.scrollWidth <= row.clientWidth;
      });
    }''')
    screenshot_dir = os.environ.get("PROGRESS_SCREENSHOTS")
    if screenshot_dir and width in (390, 1280):
        page.evaluate("() => progressFixture(0, 'A'.repeat(1234))")
        path = Path(screenshot_dir)
        path.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(path / f"progress-{width}-{'dark' if dark else 'light'}.png"))
    page.evaluate("() => App.consensusPipeline.onConsensusStart()")
    expect(page.locator('.run-step[data-step="answers"]')).to_have_attribute("data-status", "done")
    expect(page.locator('.run-step[data-step="consensus"]')).to_have_attribute("data-status", "active")
    expect(page.locator("#runCompactLabel")).to_have_text("Writing the consensus")
    expect(page.locator("#runDetail")).not_to_be_visible()
    expect(page.locator("#runTrack")).to_be_visible()
    page.evaluate("() => App.consensusPipeline.onDifferencesStart()")
    expect(page.locator('.run-step[data-step="differences"]')).to_have_attribute("data-status", "active")
    expect(page.locator("#runCompactLabel")).to_have_text("Checking for contradictions")
    expect(page.locator("#runNoteText")).to_have_text("An uninvolved model compares all answers. It does not get a vote.")
    page.evaluate("() => App.consensusPipeline.dismiss()")
    expect(page.locator("#consensusRun")).not_to_be_visible()


def test_reduced_motion_keeps_status_readable_and_static(progress_page):
    page = progress_page
    page.emulate_media(reduced_motion="reduce")
    mark = page.locator('.run-step[data-status="active"] .run-step-mark')
    assert mark.evaluate("el => getComputedStyle(el, '::before').animationName") == "none"
    for icon in page.locator(".run-model-icon").all():
        assert icon.evaluate("el => getComputedStyle(el).animationName") == "none"
    for bar in page.locator(".run-model-track i").all():
        assert bar.evaluate("el => getComputedStyle(el).animationName") == "none"
        assert bar.evaluate("el => getComputedStyle(el, '::after').animationName") == "none"
        assert bar.evaluate("el => getComputedStyle(el, '::after').content") == "none"
    page.evaluate("() => App.consensusPipeline.onConsensusStart()")
    assert page.locator("#runBar").evaluate("el => getComputedStyle(el).animationName") == "none"


@pytest.mark.parametrize("width", [390, 1280])
def test_a_dropped_model_sinks_and_is_explained_once(progress_page, width):
    page = progress_page
    page.set_viewport_size({"width": width, "height": 850})
    page.evaluate("() => progressFixture(1, '', 'error')")
    row = page.locator('[data-box="model-1"]')
    expect(row).to_have_attribute("data-state", "error")
    expect(row.locator(".run-model-time")).to_have_text("No answer")
    expect(page.locator("#runNoteText")).to_have_text("Claude didn't answer. The consensus uses the other 5 answers.")
    rows = page.locator(".run-model").all()
    assert max(r.bounding_box()["y"] for r in rows) == row.bounding_box()["y"]
    # A dropped model counts as finished, it just has nothing to add.
    expect(page.locator("#runCount")).to_have_text("3/6")
    screenshot_dir = os.environ.get("PROGRESS_SCREENSHOTS")
    if screenshot_dir:
        page.screenshot(path=str(Path(screenshot_dir) / f"dropped-{width}.png"))


@pytest.mark.parametrize("width", [320, 1280])
def test_only_phase_summary_is_live_and_skip_is_keyboard_accessible(progress_page, width):
    page = progress_page
    page.set_viewport_size({"width": width, "height": 850})
    expect(page.locator('#runStatus[role="status"][aria-live="polite"]')).to_have_count(1)
    assert page.locator("#consensusRun").get_attribute("aria-live") is None
    assert page.locator("#runDetail").get_attribute("aria-hidden") is None
    skip = page.locator('[data-box="model-5"] .run-model-skip-btn')
    tracks = page.locator(".run-model-track").all()
    before = [track.bounding_box() for track in tracks]
    height = page.locator("#consensusRun").bounding_box()["height"]
    expect(skip).to_be_visible(timeout=12000)
    expect(skip).to_have_text("Skip")
    assert skip.evaluate('''el => {
      const name = el.closest('.run-model').querySelector('.run-model-name').getBoundingClientRect();
      const status = el.closest('.run-model').querySelector('.run-model-time').getBoundingClientRect();
      const action = el.getBoundingClientRect();
      return action.right <= status.left && (innerWidth > 640
        || (action.left >= name.right && action.left - name.right <= 8));
    }''')
    assert [track.bounding_box() for track in tracks] == before
    assert page.locator("#consensusRun").bounding_box()["height"] == height
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    screenshot_dir = os.environ.get("PROGRESS_SCREENSHOTS")
    if screenshot_dir:
        page.wait_for_function("getComputedStyle(document.querySelector('[data-box=\"model-5\"] .run-model-skip-btn')).opacity === '1'")
        page.screenshot(path=str(Path(screenshot_dir) / f"skip-{width}.png"))
    skip.focus()
    page.keyboard.press("Enter")
    assert page.evaluate("window.skippedModel") == "model-5"


@pytest.mark.parametrize("progress_page", [{"has_touch": True}], indirect=True)
def test_skip_has_a_full_touch_target_without_overflow(progress_page):
    page = progress_page
    page.set_viewport_size({"width": 320, "height": 850})
    page.evaluate("() => [0, 1, 4].forEach(id => progressFixture(id, 'Finished answer', 'complete'))")
    skip = page.locator('[data-box="model-5"] .run-model-skip-btn')
    before = page.locator(".run-model-track").last.bounding_box()
    expect(skip).to_be_visible(timeout=12000)
    box = skip.bounding_box()
    assert box["width"] >= 44 and box["height"] >= 44
    assert page.locator(".run-model-track").last.bounding_box() == before
    assert page.locator(".run-model").last.bounding_box()["height"] <= 44
    assert box["x"] + box["width"] <= 320
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    screenshot_dir = os.environ.get("PROGRESS_SCREENSHOTS")
    if screenshot_dir:
        page.screenshot(path=str(Path(screenshot_dir) / "skip-touch-320.png"))
    skip.tap(position={"x": box["width"] / 2, "y": box["height"] - 2})
    assert page.evaluate("window.skippedModel") == "model-5"
