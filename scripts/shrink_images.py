"""Keep the provider logos and the landing share image small.

Provider logos (``static/icons/chat_icons/*.png``) are drawn at 13-48 CSS px:
14 px in the model picker, 34 px on /about and in the landing logo strip,
where the wide Mistral mark gets 48 px. The sources were up to 1200 px wide
and weighed 236 KB together, Gemini's alone 112 KB, for marks a 3x phone
shows at most 144 device pixels wide. This script scales each one to
``MAX_ICON_SIDE`` on its long side (Lanczos; Pillow resamples alpha
premultiplied, so edges keep no dark fringe) and keeps the result only when
the file gets smaller. No palette reduction: logos keep their gradients.

The landing share image (``static/og-home-v2.png``, 1200x630) is flat colour.
As RGB it weighed 451 KB, above the roughly 300 KB at which WhatsApp is
widely reported to drop the picture from a link preview. It uses about 120
colours, so a 256-colour palette without dithering keeps every channel of
every pixel within 13/255 of the source at 21 KB. If a palette would move any
channel by more than ``MAX_PALETTE_ERROR``, the file stays as it is.

Pillow is an app dependency:

    venv/Scripts/python.exe scripts/shrink_images.py          # shrink in place
    venv/Scripts/python.exe scripts/shrink_images.py --check  # report, exit 1 if anything would shrink

``tests/test_static_images.py`` holds new files to the same budget.
"""
from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
ICON_DIR = ROOT / "static" / "icons" / "chat_icons"
SHARE_IMAGES = (ROOT / "static" / "og-home-v2.png",)
MAX_ICON_SIDE = 144
MAX_PALETTE_ERROR = 16


def _png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, "PNG", optimize=True)
    return buffer.getvalue()


def shrunk_icon(path: Path) -> bytes | None:
    """Smaller PNG bytes for a logo, or None when the file is already best."""
    with Image.open(path) as source:
        image = source.convert("RGBA") if source.mode in ("P", "RGB", "L") else source.copy()
    width, height = image.size
    scale = MAX_ICON_SIDE / max(width, height)
    if scale < 1:
        image = image.resize((max(1, round(width * scale)), max(1, round(height * scale))), Image.LANCZOS)
    data = _png_bytes(image)
    return data if len(data) < path.stat().st_size else None


def palette_share_image(path: Path) -> bytes | None:
    """The share image as a 256-colour PNG, or None when that would not help
    or would visibly change it."""
    with Image.open(path) as source:
        if source.mode == "P":
            return None
        rgb = source.convert("RGB")
    palette = rgb.quantize(colors=256, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
    error = max(high for _low, high in ImageChops.difference(rgb, palette.convert("RGB")).getextrema())
    if error > MAX_PALETTE_ERROR:
        print(f"{path.relative_to(ROOT)}: a palette would move a pixel by {error}/255, left as is")
        return None
    data = _png_bytes(palette)
    return data if len(data) < path.stat().st_size else None


def plan() -> list[tuple[Path, bytes]]:
    changes = []
    for path in sorted(ICON_DIR.glob("*.png")):
        data = shrunk_icon(path)
        if data is not None:
            changes.append((path, data))
    for path in SHARE_IMAGES:
        data = palette_share_image(path)
        if data is not None:
            changes.append((path, data))
    return changes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--check", action="store_true", help="only report what would shrink")
    args = parser.parse_args(argv)
    changes = plan()
    for path, data in changes:
        before = path.stat().st_size
        print(f"{path.relative_to(ROOT)}: {before / 1024:.1f} KB -> {len(data) / 1024:.1f} KB")
        if not args.check:
            path.write_bytes(data)
    if not changes:
        print("All images are already as small as this script makes them.")
    return 1 if args.check and changes else 0


if __name__ == "__main__":
    sys.exit(main())
