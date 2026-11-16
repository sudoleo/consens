"""What a browser needs to keep consens.io as an app and as a search keyword.

``/manifest.webmanifest`` lets a browser install /app in a window of its own,
with the mark from ``scripts/render_brand_assets.py`` and two shortcuts.
``/opensearch.xml`` offers consens.io as a search engine. Both hand a
question over as ``/app#q=<text>``, the one way in from outside
(docs/codebase-map.md §8): in the fragment it reaches no server and no access
log, and the page only fills the composer with it, never sends it.

Every visible word goes through ``_t``; ``scripts/i18n.py`` reads its first
argument as a dictionary key, as in ``mailer.py``.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from app.core import i18n
from app.core.assets import asset_url
from app.core.site import SITE_URL

ROOT = Path(__file__).resolve().parents[2]
TOKENS = ROOT / "static" / "css" / "variables.css"

APP_PATH = "/app"
# Fragment, not query: see the module docstring. The "?" inside it is for
# Chrome, which encodes the terms by where they stand in the template: after
# a "?" as a query value ("+" a space, "%2B" a plus, "&" escaped), elsewhere
# as a path, which leaves "+" and "&" as they are and makes "C++" or
# "Tom & Jerry" unreadable. Firefox encodes as a query value anyway; the page
# reads "#q=" and "#?q=" alike (app-bootstrap.js linkQuestion).
QUESTION_TEMPLATE = f"{SITE_URL}{APP_PATH}#?q={{searchTerms}}"

NAME = "consens.io"
SHORT_NAME = "consens"


def _t(text: str, language: str) -> str:
    return i18n.t(text, language)


@lru_cache(maxsize=1)
def ground_colour() -> str:
    """The light theme's page colour (``--ground`` in ``:root``): the window
    and the splash before the page paints. One value only, so the light one
    the tokens start from; the page sets the dark one itself once it runs
    (app-bootstrap.js windowColour)."""
    match = re.search(r"--ground:\s*(#[0-9a-fA-F]{3,8})\s*;", TOKENS.read_text(encoding="utf-8"))
    return match.group(1).lower() if match else "#ffffff"


def _icon(path: str, size: int, purpose: str) -> dict:
    return {"src": asset_url(path), "sizes": f"{size}x{size}", "type": "image/png", "purpose": purpose}


def manifest(language: str) -> dict:
    """The web app manifest. No ``share_target``: it needs a query string
    or a service worker, and sharing into consens comes with the iOS app."""
    colour = ground_colour()
    return {
        "id": APP_PATH,
        "name": NAME,
        "short_name": SHORT_NAME,
        "lang": language,
        "dir": "ltr",
        "start_url": APP_PATH,
        # The whole site, so a sign-in or a shared page opened from the app
        # stays in its window instead of leaving it.
        "scope": "/",
        "display": "standalone",
        "background_color": colour,
        "theme_color": colour,
        "icons": [
            _icon("/static/brand/icon-192.png", 192, "any"),
            _icon("/static/brand/logo-512.png", 512, "any"),
            _icon("/static/brand/icon-maskable-512.png", 512, "maskable"),
        ],
        "shortcuts": [
            {"name": _t("New chat", language), "url": APP_PATH},
            {"name": _t("Watches", language), "url": f"{APP_PATH}/watches"},
        ],
    }


def opensearch(language: str) -> str:
    """The OpenSearch description: consens.io as a search keyword.

    Chrome adds it on its own once someone opened the start page (only a
    page at "/" counts there), Firefox offers it in its search settings."""
    description = _t("Ask consens.io: one AI does the work, several check it.", language)
    icon = f"{SITE_URL}{asset_url('/static/brand/icon-192.png')}"
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<OpenSearchDescription xmlns="http://a9.com/-/spec/opensearch/1.1/">\n'
        f"  <ShortName>{escape(NAME)}</ShortName>\n"
        f"  <Description>{escape(description)}</Description>\n"
        "  <InputEncoding>UTF-8</InputEncoding>\n"
        f'  <Image width="192" height="192" type="image/png">{escape(icon)}</Image>\n'
        f'  <Url type="text/html" method="get" template={quoteattr(QUESTION_TEMPLATE)}/>\n'
        "</OpenSearchDescription>\n"
    )
