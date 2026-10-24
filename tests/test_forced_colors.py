"""Windows contrast mode (a11y audit V2, 2026-10-23).

In forced-colors mode the system paints every background in Canvas. An icon
drawn through a CSS mask has its background as its only colour, so it vanished
there: the chevrons of every disclosure, the tick of a checklist, the file and
globe glyphs. foundation.css gives each of them a system colour back; this
test keeps a new masked icon from missing that list.
"""

import re
from pathlib import Path

CSS = Path(__file__).resolve().parents[1] / "static" / "css"
MASK = re.compile(r"(?<![-\w])mask\s*:\s*var\(--[\w-]+-mask\)")


def strip_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def split_selectors(selector: str) -> list[str]:
    """Top-level commas only: `:is(a, b) c` stays one selector."""
    parts, depth, current = [], 0, ""
    for char in selector:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        if char == "," and depth == 0:
            parts.append(current)
            current = ""
        else:
            current += char
    parts.append(current)
    return [" ".join(part.split()) for part in parts if part.strip()]


def media_blocks(text: str, query: str) -> list[str]:
    blocks = []
    for match in re.finditer(r"@media\s*\(" + re.escape(query) + r"\)\s*\{", text):
        depth, start = 1, match.end()
        for index in range(start, len(text)):
            depth += {"{": 1, "}": -1}.get(text[index], 0)
            if depth == 0:
                blocks.append(text[start:index])
                break
    return blocks


def rules(text: str):
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", text):
        yield split_selectors(match.group(1).split(";")[-1]), match.group(2)


def masked_icons() -> dict[str, str]:
    found = {}
    for path in sorted(CSS.glob("*.css")):
        for selectors, body in rules(strip_comments(path.read_text(encoding="utf-8"))):
            if MASK.search(body):
                for selector in selectors:
                    found[selector] = path.name
    return found


def test_every_masked_icon_keeps_a_colour_in_contrast_mode():
    foundation = strip_comments((CSS / "foundation.css").read_text(encoding="utf-8"))
    blocks = media_blocks(foundation, "forced-colors: active")
    assert blocks, "foundation.css has no forced-colors block"
    covered = {}
    for block in blocks:
        for selectors, body in rules(block):
            for selector in selectors:
                covered[selector] = body
    icons = masked_icons()
    assert len(icons) >= 30, icons
    missing = sorted(f"{name}: {selector}" for selector, name in icons.items() if selector not in covered)
    assert not missing, "Masked icons without a colour in forced-colors mode:\n" + "\n".join(missing)
    for selector in icons:
        body = covered[selector]
        assert "forced-color-adjust: none" in body, selector
        assert re.search(r"background-color:\s*(CanvasText|Canvas)\b", body), selector


def test_sentence_marks_speak_through_their_underline_in_contrast_mode():
    visuals = strip_comments((CSS / "components-consensus-visuals.css").read_text(encoding="utf-8"))
    block = "\n".join(media_blocks(visuals, "forced-colors: active"))
    styles = {}
    for selectors, body in rules(block):
        style = re.search(r"text-decoration-style:\s*(\w+)", body)
        if style:
            for selector in selectors:
                styles[selector] = style.group(1)

    def style_of(kind: str) -> str:
        hits = [value for selector, value in styles.items()
                if f".is-{kind}" in selector and ".cx-spot" not in selector and "provisional" not in selector]
        return hits[-1]

    # A contradiction must not read like an agreement in contrast mode.
    assert style_of("major") == "solid"
    assert style_of("split") == "dashed"
    assert style_of("unanimous") == "dotted"
