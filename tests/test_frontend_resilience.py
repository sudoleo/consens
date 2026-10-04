"""Regression checks for browser failures that must degrade gracefully."""

from pathlib import Path
import re

import pytest


ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.source_contract


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_missing_markdown_dependencies_render_plaintext_instead_of_throwing():
    markdown = read("static/js/markdown-stream.js")

    assert 'typeof window.marked?.parse !== "function"' in markdown
    assert 'typeof window.DOMPurify?.sanitize !== "function"' in markdown
    assert 'message: "Markdown renderer unavailable; displaying unformatted text."' in markdown
    assert markdown.count("return escapeHtml(prepared);") >= 2


def test_usage_storage_busy_is_retried_and_stops_before_model_fanout():
    query = read("static/js/query-send.js")
    limits = read("static/js/usage-limit.js")

    assert '=== "usage_storage_busy"' in query
    assert "async function prepareWithRetry(payload, signal)" in query
    assert "for (let attempt = 1; attempt <= 3; attempt += 1)" in query
    assert "window.App.usageLimit?.showTemporaryStorageBusy?.();" in query
    assert "function showTemporaryStorageBusy()" in limits
    assert "No model was asked; please try this question again in a moment." in limits

    busy_branch = query.index("if (!prepared.response.ok && isUsageStorageBusy(prepared.data))")
    fanout = query.index("context.config.providers.map(provider => runProvider", busy_branch)
    assert busy_branch < fanout


# Local CSS/JS references: template URLs plus nested @import/ESM imports.
TEMPLATE_ASSET = re.compile(r"""(?:src|href)=["'](?P<url>/static/[^"'?]+\.(?:js|css|mjs))""")
NESTED_IMPORT = re.compile(
    r"""@import\s+url\(['"]?(?P<css>[^'"\)\s]+\.css)[^)]*\)"""
    r"""|from\s+["'](?P<js>/static/[^"']+\.m?js)[^"']*["']"""
)
HAND_MARK = re.compile(r"""/static/[^"'\s)]+\?v=|\.(?:css|m?js)\?v=""")


def _asset_sources():
    sources = sorted((ROOT / "templates").rglob("*.html"))
    sources += [
        path for path in sorted((ROOT / "static").rglob("*"))
        if path.suffix in {".css", ".js", ".mjs"}
        and path.relative_to(ROOT / "static").parts[0] not in {"dist", "vendor"}
    ]
    return sources


def test_no_hand_maintained_cache_marks_remain():
    """Cache identity comes from content: asset_url() in templates (with the
    transitive @import/ESM closure folded in) and static/dist for /app. A
    hand-written ?v= is exactly the stale-cache trap this replaced."""

    offenders = [
        f"{source.relative_to(ROOT)}: {match.group(0)}"
        for source in _asset_sources()
        for match in HAND_MARK.finditer(source.read_text(encoding="utf-8"))
    ]
    assert offenders == []


def test_template_assets_go_through_asset_url_and_nested_imports_exist():
    for source in _asset_sources():
        text = source.read_text(encoding="utf-8")
        relative = source.relative_to(ROOT)
        if source.suffix == ".html":
            unversioned = [match.group("url") for match in TEMPLATE_ASSET.finditer(text)]
            assert unversioned == [], f"{relative} links CSS/JS without asset_url()"
            for url in re.findall(r"asset_url\('(/static/[^']+)'\)", text):
                assert (ROOT / url.lstrip("/")).is_file(), f"{relative} references missing {url}"
            continue
        for match in NESTED_IMPORT.finditer(text):
            target = (
                source.parent / match.group("css")
                if match.group("css")
                else ROOT / match.group("js").lstrip("/")
            )
            assert target.resolve().is_file(), f"{relative} imports missing {target}"


def test_mobile_enter_keeps_the_textarea_newline_behavior():
    app_init = read("static/js/app-init.js")
    keydown = app_init.split(
        'document.getElementById("questionInput").addEventListener("keydown"', 1
    )[1].split("// Es gibt genau EINEN sichtbaren Sidebar-Toggle", 1)[0]

    assert 'window.matchMedia("(max-width: 768px)").matches' in keydown
    assert "event.isComposing" in keydown
    assert keydown.index("matchMedia") < keydown.index("event.preventDefault()")
