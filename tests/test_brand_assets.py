"""The consens.io mark has one drawing; icons, templates and cards follow it.

``static/brand/mark.svg`` is that drawing. ``scripts/render_brand_assets.py``
draws every icon file from it, ``templates/partials/brand.html`` repeats its
path for inline use. These tests keep a copy from drifting, a colour from
creeping back in (the first favicon was navy) and a page from linking icons
of its own. The rules behind them are in ``docs/brand.md``.
"""
import re
from pathlib import Path

from PIL import Image, ImageDraw

from app.core import seo_entity
from app.core.site import SITE_URL
from app.services import og_image
from scripts import render_brand_assets as brand

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"
HEAD_ICONS = '{% include "partials/head_icons.html" %}'


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_every_icon_file_is_drawn_from_the_master():
    stale = [
        path.relative_to(ROOT).as_posix()
        for path, content in brand.rendered().items()
        if not brand.is_current(path, content)
    ]

    assert stale == [], "run scripts/render_brand_assets.py"


def test_the_inline_mark_is_the_master_drawing():
    inline = re.findall(r'<path d="([^"]+)"', read("templates/partials/brand.html"))

    assert inline == [brand.mark_path()]
    assert 'fill="currentColor"' in read("templates/partials/brand.html")


def test_no_icon_carries_a_colour():
    tinted = []
    for path, content in brand.rendered().items():
        if isinstance(content, str):
            assert set(re.findall(r"#[0-9a-f]{6}", content)) == {"#0a0a0a", "#f5f5f5"}
            continue
        with Image.open(path) as image:
            red, green, blue = image.convert("RGB").split()
        if red.tobytes() != green.tobytes() or green.tobytes() != blue.tobytes():
            tinted.append(path.name)

    assert tinted == []


def test_tiles_are_solid_squares():
    # iOS paints transparency black and a search result crops to a circle:
    # the tile carries its own ground and keeps the mark inside that circle.
    for name, side in brand.TILES.items():
        with Image.open(ROOT / "static" / "brand" / name) as image:
            assert image.size == (side, side) and image.mode == "RGB", name
            corners = {image.getpixel(xy) for xy in ((0, 0), (side - 1, 0), (0, side - 1), (side - 1, side - 1))}
            assert corners == {brand.INK}, name
            light = image.convert("L").point(lambda value: 255 if value > 128 else 0)
            left, top, right, bottom = light.getbbox()
        radius = side / 2
        for x, y in ((left, top), (right, top), (left, bottom), (right, bottom)):
            assert ((x - radius) ** 2 + (y - radius) ** 2) ** 0.5 < radius, name


def test_every_page_takes_its_icons_from_one_partial():
    partial = read("templates/partials/head_icons.html")
    linked = re.findall(r"asset_url\('(/static/[^']+)'\)", partial)
    assert len(linked) == 3 and all((ROOT / path.lstrip("/")).is_file() for path in linked)

    offenders = []
    for path in sorted(TEMPLATES.rglob("*.html")):
        text = path.read_text(encoding="utf-8")
        name = path.relative_to(TEMPLATES).as_posix()
        own_links = re.search(r'<link rel="(?:icon|apple-touch-icon)"', text)
        if name == "partials/head_icons.html":
            continue
        if own_links or ("</head>" in text and "public_nav.html" in text and HEAD_ICONS not in text):
            offenders.append(name)

    assert offenders == []
    assert HEAD_ICONS in read("templates/index.html")


def test_the_mark_beside_the_wordmark_is_inline():
    # An <img> cannot take the colour of the word next to it; these places
    # used a white PNG that CSS inverted on light ground.
    for template in ("templates/partials/public_nav.html", "templates/index.html",
                     "templates/partials/product_result_mockup.html"):
        text = read(template)
        assert "brand_mark(" in text, template
        assert "favicon.png" not in text, template
    for sheet in ("static/css/layout.css", "static/css/public-pages.css", "static/css/landing.css",
                  "static/css/auth-modal.css"):
        css = re.sub(r"/\*.*?\*/", "", read(sheet), flags=re.S)
        rules = re.findall(r"([^{}]*(?:app-favicon|auth-mark|brand-mark)[^{}]*)\{([^}]*)\}", css)
        assert rules, sheet
        assert not [selector.strip() for selector, body in rules if "filter" in body], sheet


def test_the_organization_logo_shows_on_a_white_page():
    url = seo_entity.ORGANIZATION["logo"]["url"]
    assert url.startswith(SITE_URL + "/static/")
    with Image.open(ROOT / url[len(SITE_URL) + 1:]) as logo:
        assert logo.mode == "RGB" and logo.width == logo.height >= 112
        assert logo.getpixel((0, 0)) == brand.INK


def test_link_cards_use_the_lockup_of_the_site():
    css = read("static/css/public-pages.css")
    brand_rule = re.search(r"\.brand \{([^}]*)\}", css).group(1)
    mark_rule = re.search(r"\.brand \.brand-mark \{([^}]*)\}", css).group(1)
    assert "gap: 9px" in brand_rule and "--font-weight-semibold" in brand_rule and "--tracking-tight" in brand_rule
    assert "width: 24px" in mark_rule

    draw = ImageDraw.Draw(Image.new("RGB", (og_image.WIDTH, og_image.HEIGHT)))
    _font, _mark_height, mark_width, gap, _total = og_image._lockup(draw, 32)

    # 24 px mark and 9 px gap at the bar's 16 px.
    assert (mark_width, gap) == (32 * 24 // 16, 32 * 9 // 16)
    assert og_image.WORD_WEIGHT == 600
