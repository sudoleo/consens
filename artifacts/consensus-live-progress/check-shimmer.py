import importlib.util
from pathlib import Path
from types import SimpleNamespace
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('progress_fixture', root / 'tests/e2e/test_consensus_live_progress.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
with sync_playwright() as p:
    browser = p.chromium.launch()
    fixture = module.progress_page.__wrapped__(browser, SimpleNamespace())
    page = next(fixture)
    result = page.evaluate('''() => {
      const bar = document.querySelector('[data-box="model-0"] .run-model-track i');
      const style = getComputedStyle(bar, '::after');
      const animations = bar.getAnimations({subtree:true});
      animations.forEach(a => { a.pause(); a.currentTime = 1600; });
      return {state: bar.closest('.run-model').dataset.state, animation: style.animationName, content: style.content, height: style.height, count: animations.length};
    }''')
    print(result)
    assert result['animation'] == 'runModelShimmer' and result['count'] > 0
    page.screenshot(path=str(root / 'artifacts/consensus-live-progress/shimmer/mid-sweep.png'))
    try:
        next(fixture)
    except StopIteration:
        pass
    browser.close()
