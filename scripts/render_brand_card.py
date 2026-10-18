"""Write the brand share card, static/og-home-v2.png, from its renderer.

The card every page without a card of its own shows in link previews (the
landing page, /app, /about, ...) is drawn by ``og_image.render_brand_card``,
in the same language as the generated question cards. After a change there:

    venv/Scripts/python.exe scripts/render_brand_card.py
    venv/Scripts/python.exe scripts/shrink_images.py

The file keeps its name; ``asset_url`` gives it a new content hash, so link
previews fetch the new picture once a service reads the page again.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services import og_image  # noqa: E402

TARGET = ROOT / "static" / "og-home-v2.png"


def main() -> int:
    if not og_image.is_available():
        print("Pillow or the Inter font is missing", file=sys.stderr)
        return 1
    TARGET.write_bytes(og_image.render_brand_card())
    print(f"{TARGET.relative_to(ROOT)}: {TARGET.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
