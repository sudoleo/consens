"""app/core/svg.py reads an SVG as the app draws it (static/js/diagram-render.js)."""

import json
from pathlib import Path

from app.core import svg
from app.services.agent_files import public_file

CASES = json.loads((Path(__file__).parent / "fixtures" / "svg_sizes.json").read_text(encoding="utf-8"))["cases"]


def test_a_picture_is_drawn_at_the_size_the_app_draws_it_at():
    # tests/js/diagram-svg.test.mjs reads the same cases with diagram-render.js.
    for source, size in CASES:
        assert list(svg.size(source)) == size, source


def test_only_bytes_the_app_draws_are_a_picture():
    assert svg.picture('<svg viewBox="0 0 24 24"><path d="M1 1"/></svg>'.encode()) == (128, 128)
    assert svg.picture('\uFEFF<!-- Logo -->\n<svg width="320" height="120"></svg>'.encode()) == (320, 120)
    for raw in (b"\x89PNG\r\n\x1a\n", b"\xff\xfe<\x00s\x00", b"<html><svg></svg></html>", b"<p>text</p>",
                b'<!DOCTYPE svg [<!ENTITY a "aaaa">]><svg>&a;</svg>', b"<svg>" + b" " * svg.MAX_CHARS + b"</svg>"):
        assert svg.picture(raw) is None, raw[:40]


def test_the_browser_hears_that_a_file_is_drawn_as_a_picture_and_the_model_does_not():
    data = {"id": "a" * 32, "name": "logo.svg", "mime": "application/octet-stream", "size": 90, "picture": "svg",
            "width": 128, "height": 64, "object_key": "agent-files/x"}
    assert public_file(data) == {"id": "a" * 32, "name": "logo.svg", "mime": "application/octet-stream",
                                 "size": 90, "width": 128, "height": 64, "picture": "svg"}
    assert "picture" not in public_file(data, for_model=True)
