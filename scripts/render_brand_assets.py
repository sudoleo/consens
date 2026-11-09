"""Write every icon form of the consens.io mark from its one drawing.

``static/brand/mark.svg`` is the mark: a circle and a wedge, traced from the
279 x 200 PNG the project started with. Everything a browser, a phone or a
search engine asks for is drawn from it here, so no file carries its own copy
of the shape or an older colour:

    static/favicon.svg                 tab icon, ink or chalk by system theme
    static/favicon.png                 chalk mark on nothing (icon rows; CSS inverts it on light)
    static/favicon-dark.png            ink mark on nothing (alpha mask of og_image)
    static/brand/icon-192.png          solid tile: tabs without SVG support, search results
    static/brand/apple-touch-icon.png  solid tile, 180 px (iOS paints transparency black)
    static/brand/logo-512.png          solid tile, Organization logo in JSON-LD

    venv/Scripts/python.exe scripts/render_brand_assets.py          # write
    venv/Scripts/python.exe scripts/render_brand_assets.py --check  # exit 1 if a file is stale

``templates/partials/brand.html`` holds the same path for inline use;
``tests/test_brand_assets.py`` keeps the three in step. Rules for using the
mark are in ``docs/brand.md``.
"""
from __future__ import annotations

import argparse
import io
import math
import re
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"
MASTER = STATIC / "brand" / "mark.svg"

WIDTH, HEIGHT = 279, 200
INK = (10, 10, 10)
CHALK = (245, 245, 245)
# In a tile the mark is two thirds as wide as the tile. Its weight sits in
# the upper half, so the point that goes to the tile's middle lies above the
# middle of its box (y = 100).
TILE_MARK_WIDTH = 0.66
OPTICAL_CENTRE = (139.4, 85.0)
TILES = {"icon-192.png": 192, "apple-touch-icon.png": 180, "logo-512.png": 512}
SUPERSAMPLE = 8
# A rendering may differ by rounding between Pillow versions.
PIXEL_TOLERANCE = 3


def mark_path() -> str:
    """The ``d`` attribute of the master drawing."""
    match = re.search(r'<path[^>]*\sd="([^"]+)"', MASTER.read_text(encoding="utf-8"))
    if not match:
        raise SystemExit(f"{MASTER}: no path")
    return match.group(1)


def _arc(start, radius: float, large: bool, sweep: bool, end, steps: int = 240):
    """Points of an SVG circular arc (endpoint form), without its start."""
    (x0, y0), (x1, y1) = start, end
    hx, hy = (x0 - x1) / 2, (y0 - y1) / 2
    span = hx * hx + hy * hy
    scale = math.sqrt(max(radius * radius - span, 0.0) / span)
    if large == sweep:
        scale = -scale
    cx, cy = scale * hy + (x0 + x1) / 2, -scale * hx + (y0 + y1) / 2
    a0, a1 = math.atan2(y0 - cy, x0 - cx), math.atan2(y1 - cy, x1 - cx)
    delta = a1 - a0
    if sweep and delta < 0:
        delta += 2 * math.pi
    elif not sweep and delta > 0:
        delta -= 2 * math.pi
    return [(cx + radius * math.cos(a0 + delta * i / steps), cy + radius * math.sin(a0 + delta * i / steps))
            for i in range(1, steps + 1)]


def _cubic(p0, p1, p2, p3, steps: int = 96):
    points = []
    for i in range(1, steps + 1):
        t = i / steps
        u = 1 - t
        points.append(tuple(u ** 3 * a + 3 * u * u * t * b + 3 * u * t * t * c + t ** 3 * d
                            for a, b, c, d in zip(p0, p1, p2, p3)))
    return points


def polygons(d: str) -> list[list[tuple[float, float]]]:
    """Flatten the path. It uses absolute M, C, A (circular) and Z only."""
    tokens = re.findall(r"[MCAZ]|-?\d*\.?\d+", d)
    result, current, i = [], [], 0

    def numbers(count: int) -> list[float]:
        nonlocal i
        values = [float(token) for token in tokens[i:i + count]]
        i += count
        return values

    while i < len(tokens):
        command = tokens[i]
        i += 1
        if command == "M":
            current = [tuple(numbers(2))]
        elif command == "C":
            x1, y1, x2, y2, x, y = numbers(6)
            current += _cubic(current[-1], (x1, y1), (x2, y2), (x, y))
        elif command == "A":
            rx, ry, rotation, large, sweep, x, y = numbers(7)
            if rx != ry or rotation:
                raise SystemExit("only circular arcs are supported")
            current += _arc(current[-1], rx, bool(large), bool(sweep), (x, y))
        elif command == "Z":
            result.append(current)
            current = []
        else:
            raise SystemExit(f"unexpected path token {command!r}")
    return result


def mask(shapes, size: tuple[int, int], scale: float, offset: tuple[float, float]) -> Image.Image:
    """The mark as an alpha mask: drawn large, then reduced, for clean edges."""
    big = Image.new("L", (size[0] * SUPERSAMPLE, size[1] * SUPERSAMPLE), 0)
    draw = ImageDraw.Draw(big)
    for shape in shapes:
        draw.polygon([((x * scale + offset[0]) * SUPERSAMPLE, (y * scale + offset[1]) * SUPERSAMPLE)
                      for x, y in shape], fill=255)
    return big.resize(size, Image.LANCZOS)


def glyph(shapes, colour) -> Image.Image:
    image = Image.new("RGBA", (WIDTH, HEIGHT), colour + (0,))
    image.putalpha(mask(shapes, (WIDTH, HEIGHT), 1.0, (0.0, 0.0)))
    return image


def tile(shapes, side: int) -> Image.Image:
    scale = TILE_MARK_WIDTH * side / WIDTH
    offset = (side / 2 - OPTICAL_CENTRE[0] * scale, side / 2 - OPTICAL_CENTRE[1] * scale)
    image = Image.new("RGB", (side, side), INK)
    image.paste(Image.new("RGB", (side, side), CHALK), (0, 0), mask(shapes, (side, side), scale, offset))
    return image


def favicon_svg(d: str) -> str:
    # A square box with the mark in its middle; the colours are --ink of
    # static/css/variables.css in its light and its dark value.
    top = (HEIGHT - WIDTH) / 2
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 {top:g} {WIDTH} {WIDTH}">'
        "<style>path{fill:#0a0a0a}@media (prefers-color-scheme:dark){path{fill:#f5f5f5}}</style>"
        f'<path d="{d}"/></svg>\n'
    )


def _png(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, "PNG", optimize=True)
    return buffer.getvalue()


def rendered() -> dict[Path, bytes | str]:
    d = mark_path()
    shapes = polygons(d)
    files: dict[Path, bytes | str] = {
        STATIC / "favicon.svg": favicon_svg(d),
        STATIC / "favicon.png": _png(glyph(shapes, CHALK)),
        STATIC / "favicon-dark.png": _png(glyph(shapes, INK)),
    }
    for name, side in TILES.items():
        files[STATIC / "brand" / name] = _png(tile(shapes, side))
    return files


def is_current(path: Path, content: bytes | str) -> bool:
    if not path.is_file():
        return False
    if isinstance(content, str):
        return path.read_text(encoding="utf-8") == content
    with Image.open(path) as stored, Image.open(io.BytesIO(content)) as fresh:
        if stored.size != fresh.size or stored.mode != fresh.mode:
            return False
        difference = ImageChops.difference(stored, fresh)
        return max(high for _low, high in difference.getextrema()) <= PIXEL_TOLERANCE


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="report stale files, write nothing")
    args = parser.parse_args()

    stale = 0
    for path, content in rendered().items():
        if is_current(path, content):
            continue
        stale += 1
        name = path.relative_to(ROOT).as_posix()
        if args.check:
            print(f"stale: {name}")
            continue
        if isinstance(content, str):
            path.write_text(content, encoding="utf-8", newline="\n")
        else:
            path.write_bytes(content)
        print(f"wrote {name}")
    if args.check and stale:
        print("run scripts/render_brand_assets.py", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
