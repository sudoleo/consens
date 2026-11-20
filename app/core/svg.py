"""What the app reads as an SVG picture, the way static/js/diagram-render.js
reads it: one <svg> element after at most a byte order mark, the XML
declaration, comments and a doctype without an internal subset, drawn at
its own size.

The browser draws the picture (an image: nothing in it runs or loads); the
server only needs to know that it is one and how large it will be, so a
shared answer names its block "svg" (public_markdown.py) and a picture the
agent shares from its workspace keeps its place from the first frame
(agent_vm_tools.share). Both sides read the same cases:
tests/fixtures/svg_sizes.json.
"""

from __future__ import annotations

import math
import re
from html.parser import HTMLParser

_PROLOG = re.compile(r"(?:\uFEFF|\s|<\?xml\b[^>]*\?>|<!--.*?-->|<!DOCTYPE\s+svg\b[^>\[]*>)*",
                     re.IGNORECASE | re.DOTALL)
_ROOT = re.compile(r"<svg[\s>]")
_LENGTH = re.compile(r"\s*\+?(\d+\.?\d*|\.\d+)(e[+-]?\d+)?\s*(px|pt|pc|mm|cm|in)?\s*", re.IGNORECASE)
_UNITS = {"px": 1, "pt": 4 / 3, "pc": 16, "mm": 96 / 25.4, "cm": 96 / 2.54, "in": 96}
# diagram-render.js MAX_SVG_CHARS, PICTURE_LEAST, PICTURE_MOST.
MAX_CHARS = 300_000
PICTURE_LEAST = 128
PICTURE_MOST = 4096


def is_svg(source) -> bool:
    text = str(source or "")
    return bool(_ROOT.match(text, _PROLOG.match(text).end()))


class _Root(HTMLParser):
    """The attributes of the first <svg> tag, as a page's parser reads them:
    names in lower case, entities resolved, the first of a repeated one."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.attributes = None

    def handle_starttag(self, tag, attrs):
        if self.attributes is None and tag == "svg":
            self.attributes = {}
            for name, value in attrs:
                self.attributes.setdefault(name, value or "")

    handle_startendtag = handle_starttag


def _length(value) -> float:
    match = _LENGTH.fullmatch(str(value or ""))
    if not match:
        return math.nan
    return float(match.group(1) + (match.group(2) or "")) * _UNITS[(match.group(3) or "px").lower()]


def _round(value: float) -> int:
    """JavaScript's Math.round for the positive sizes here (Python's round
    rounds a half to the even number)."""
    return math.floor(value + 0.5)


def size(source):
    """``(width, height)`` the picture is drawn at (diagram-render.js
    measure): its own width and height in absolute units, else its viewBox's,
    else 300 × 150; its longer side at least PICTURE_LEAST and at most
    PICTURE_MOST. None when the source is no picture."""
    text = str(source or "")
    start = _PROLOG.match(text).end()
    if not _ROOT.match(text, start):
        return None
    # The whole source: a ">" inside a quoted value does not end the tag.
    reader = _Root()
    reader.feed(text[start:])
    reader.close()
    attributes = reader.attributes or {}
    try:
        box = [float(part) for part in re.split(r"[\s,]+", attributes.get("viewbox", "").strip())]
    except ValueError:
        box = []
    box = box if len(box) == 4 and all(map(math.isfinite, box)) and box[2] > 0 and box[3] > 0 else None
    width, height = _length(attributes.get("width")), _length(attributes.get("height"))
    ratio = box[2] / box[3] if box else 2
    if not width > 0 and not height > 0:
        width, height = (box[2], box[3]) if box else (300, 150)
    elif not width > 0:
        width = height * ratio
    elif not height > 0:
        height = width / ratio
    longer = max(width, height)
    scale = PICTURE_LEAST / longer if longer < PICTURE_LEAST else PICTURE_MOST / longer if longer > PICTURE_MOST else 1
    return max(1, _round(width * scale)), max(1, _round(height * scale))


def picture(raw):
    """``(width, height)`` of a file's bytes that the app draws as an SVG
    picture, or None: UTF-8 text no longer than the app draws, without
    entity declarations, whose root is an <svg> element."""
    try:
        text = raw.decode("utf-8")
    except (AttributeError, UnicodeDecodeError):
        return None
    if len(text) > MAX_CHARS or re.search(r"<!ENTITY", text, re.IGNORECASE):
        return None
    return size(text)
