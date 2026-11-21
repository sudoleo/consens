"""Raw HTML (Settings > Display, raw-display.css): the app as the browser draws
plain HTML, with every box where the design put it."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"
RAW = STATIC / "css" / "raw-display.css"


def strip_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def rules(text: str):
    """(selector, body) of every innermost rule, at-rule blocks walked into."""
    stack, buffer = [], ""
    for char in strip_comments(text):
        if char == "{":
            stack.append(buffer.strip())
            buffer = ""
        elif char == "}":
            if stack:
                yield " ".join(stack.pop().split()), buffer
            buffer = ""
        else:
            buffer += char


def selector_list(selector: str) -> list[str]:
    """Split at the top-level commas, not at those inside :is() or :where()."""
    parts, depth, current = [], 0, ""
    for char in selector:
        depth += {"(": 1, ")": -1}.get(char, 0)
        if char == "," and depth == 0:
            parts.append(current.strip())
            current = ""
        else:
            current += char
    return [*parts, current.strip()]


def app_stylesheets() -> list[Path]:
    entry = (STATIC / "style.css").read_text(encoding="utf-8")
    names = re.findall(r"@import url\('\./(css/[\w-]+\.css)'\)", entry)
    return [STATIC / name for name in names]


def test_raw_display_is_the_last_stylesheet_of_the_app():
    sheets = app_stylesheets()
    assert sheets[-1] == RAW, "raw-display.css must come last: its tokens win on equal specificity"


def test_the_reset_rolls_back_only_what_draws():
    raw = strip_comments(RAW.read_text(encoding="utf-8"))
    layer = re.search(r"@layer raw-display\s*\{", raw)
    assert layer, "the reset must sit in a cascade layer to beat the app's own !important rules"
    reset = next(body for selector, body in rules(raw) if selector.startswith("html.raw-display, html.raw-display *"))
    for drawn in ("font-family", "box-shadow", "border-radius", "background-image", "appearance", "outline"):
        assert re.search(rf"(?<![\w-]){drawn}:\s*revert\s*!important", reset), drawn
    # The layout is the design's: nothing moves when the setting changes.
    for kept in ("display", "position", "width", "height", "margin", "padding", "opacity", "transform",
                 "visibility", "inset", "top", "left", "flex", "grid", "font-size", "line-height"):
        assert not re.search(rf"(?<![\w-]){kept}\s*:", reset), kept


def test_every_floating_layer_keeps_a_frame():
    """A layer lifted by --lift loses its shadow in Raw HTML; on a page of
    one colour only the hairline frame tells it from what lies under it."""
    framed = set()
    for selector, body in rules(RAW.read_text(encoding="utf-8")):
        if "0 0 0 1px CanvasText" in body:
            framed.update(re.findall(r"[.#][\w-]+", selector))
    missing = []
    for sheet in app_stylesheets():
        for selector, body in rules(sheet.read_text(encoding="utf-8")):
            if not re.search(r"box-shadow\s*:[^;]*var\(--(lift|shadow-overlay)\b", body):
                continue
            for part in selector_list(selector):
                # A customizable select's own picker: Raw HTML draws the native one.
                if "::picker" in part:
                    continue
                # The layer is what the last compound names; one inside
                # :is() names any of its alternatives.
                last = re.split(r"\s*[>+~]\s*|\s+(?![^(]*\))", part)[-1]
                if not set(re.findall(r"[.#][\w-]+", last)) & framed:
                    missing.append(f"{sheet.name}: {part}")
    assert not missing, "Floating layers without a frame in raw-display.css:\n" + "\n".join(missing)


def test_reading_widths_keep_the_designs_measure_in_the_browsers_font():
    """A width in ch is a width in the font's 0: in Times a fifth narrower
    than in Inter. Raw HTML gives every reading width back in Inter's ch."""
    kept = " ".join(
        selector for selector, body in rules(RAW.read_text(encoding="utf-8")) if "var(--inter-ch)" in body
    )
    missing = []
    for sheet in app_stylesheets():
        if sheet == RAW:
            continue
        for selector, body in rules(sheet.read_text(encoding="utf-8")):
            width = re.search(r"(?<![\w-])max-width:\s*(\d+(?:\.\d+)?)ch\b", body)
            # Short ones size digits and stay in the font that draws them.
            if not width or float(width.group(1)) < 10:
                continue
            missing += [f"{sheet.name}: {part}" for part in selector_list(selector) if part not in kept]
    assert not missing, "Reading widths in ch without an Inter width in raw-display.css:\n" + "\n".join(missing)


def test_the_setting_reaches_the_page_before_its_first_paint():
    bootstrap = (STATIC / "js" / "app-bootstrap.js").read_text(encoding="utf-8")
    assert 'classList.toggle("raw-display"' in bootstrap
    assert 'onChange?.("raw_display"' in bootstrap
    template = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    assert 'id="rawDisplaySwitch"' in template
    assert 'bindSettingSwitch("rawDisplaySwitch", "raw_display", false)' in (STATIC / "app-ui.js").read_text(
        encoding="utf-8"
    )
