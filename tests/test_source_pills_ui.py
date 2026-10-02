"""String contracts for the source pills in chat prose (2026-10-01).

Behaviour is covered in tests/js/agent-citations.test.mjs and
tests/js/source-teaser-check.test.mjs; these checks guard the parts a DOM test
cannot see: the stylesheet and the privacy boundary of the favicon.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _rule(css: str, selector: str) -> str:
    match = re.search(r"(?m)^" + re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert match, f"missing rule {selector}"
    return match.group(1)


def test_source_pill_sits_on_the_baseline_not_raised():
    css = read("static/css/shell.css")
    pill = _rule(css, ".src-ref")
    assert "vertical-align: baseline" in pill
    assert "vertical-align: super" not in pill
    assert "border-radius: var(--radius-pill)" in pill
    assert "background: var(--src-ref-bg)" in pill
    # Long domains truncate inside the pill instead of widening the line.
    assert "text-overflow: ellipsis" in _rule(css, ".src-ref-label")
    assert "max-width:" in pill
    # Monochrome: no accent/blue in the pill itself.
    assert "--accent" not in pill


def test_source_pill_favicons_only_use_the_own_proxy():
    js = read("static/js/sources.js")
    assert '"/api/topics/favicon?d=" + encodeURIComponent(host)' in js
    assert "google.com" not in js and "s2/favicons" not in js
    # A failed favicon becomes a neutral glyph, never a broken image.
    assert "createSourceGlyph(label)" in js


def test_copy_paths_read_pills_through_the_shared_helper():
    actions = read("static/js/consensus-actions.js")
    assert "window.App.sourceRefs?.plainText" in actions
    assert "window.App.sourceRefs?.urls" in actions
