"""Provider logos and the landing share image stay small and cacheable.

``scripts/shrink_images.py`` took the PNG logos from 236 KB to 63 KB and the
share image from 451 KB to 21 KB; these budgets keep a newly added file from
undoing that. Logo URLs carry ``asset_url``'s content hash, so browsers keep
them for a year instead of revalidating every logo on every page.
"""
import re
from pathlib import Path

from PIL import Image

import app.core.config as cfg

ROOT = Path(__file__).resolve().parents[1]
ICON_DIR = ROOT / "static" / "icons" / "chat_icons"
CONTENT_HASH = r"\?v=[0-9a-f]{12}"


def test_provider_logos_stay_small():
    # Drawn at 48 CSS px at most (the wide Mistral mark in the landing logo
    # strip); the detailed Claude mark needs 17 KB at 144 px.
    oversized = [
        f"{path.name}: {path.stat().st_size // 1024} KB"
        for path in sorted(ICON_DIR.glob("*.png"))
        if path.stat().st_size > 20 * 1024
    ]

    assert oversized == [], "run scripts/shrink_images.py"


def test_landing_share_image_stays_small_enough_for_link_previews():
    path = ROOT / "static" / "og-home-v2.png"

    # WhatsApp is widely reported to drop the picture from link previews
    # above roughly 300 KB.
    assert path.stat().st_size <= 300 * 1024, "run scripts/shrink_images.py"
    with Image.open(path) as image:
        assert image.size == (1200, 630)


def test_provider_logo_urls_carry_a_content_hash():
    for provider in cfg.PROVIDERS.values():
        expected = rf"/static/icons/chat_icons/{re.escape(provider.icon)}{CONTENT_HASH}"
        assert re.fullmatch(expected, provider.icon_url), provider.key
    for family in cfg.get_model_families():
        assert re.search(rf"{CONTENT_HASH}$", family["icon"]), family["provider"]


def test_templates_link_logos_through_asset_url():
    offenders = [
        f"{path.relative_to(ROOT)}: {match}"
        for path in sorted((ROOT / "templates").rglob("*.html"))
        for match in re.findall(r'src="(/static/icons/[^"]+)"', path.read_text(encoding="utf-8"))
    ]

    assert offenders == []
