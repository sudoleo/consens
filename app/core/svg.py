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
# The root's start tag as a page's parser reads it: a quote opens a value
# only after "=", and a ">" inside one does not end the tag. Possessive, so
# a tag that never ends costs one pass.
_ROOT_TAG = re.compile(r"""<svg(?:=[\t\n\f\r ]*(?:"[^"]*"|'[^']*')|[^>])*+>""")
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
    length = float(match.group(1) + (match.group(2) or "")) * _UNITS[(match.group(3) or "px").lower()]
    return length if math.isfinite(length) else math.nan


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
    # A page's parser drops a start tag the text never ends: no picture.
    tag = _ROOT_TAG.match(text, start)
    if not tag:
        return None
    # Only the root's tag: the parser reads markup after it in quadratic
    # time (CVE-2025-6069), and some of it, such as "<![", makes it raise.
    reader = _Root()
    try:
        reader.feed(tag.group())
        reader.close()
    except Exception:  # noqa: BLE001 - what html.parser raises differs between versions
        return None
    attributes = reader.attributes or {}
    try:
        box = [float(part) for part in re.split(r"[\s,]+", attributes.get("viewbox", "").strip())]
    except ValueError:
        box = []
    valid = len(box) == 4 and all(map(math.isfinite, box)) and box[2] > 0 and box[3] > 0
    box = box if valid and 0 < box[2] / box[3] < math.inf else None
    width, height = _length(attributes.get("width")), _length(attributes.get("height"))
    ratio = box[2] / box[3] if box else 2
    if not width > 0 and not height > 0:
        width, height = (box[2], box[3]) if box else (300, 150)
    elif not width > 0:
        width = height * ratio
    elif not height > 0:
        height = width / ratio
    if not (math.isfinite(width) and math.isfinite(height)):
        width, height = 300, 150
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
