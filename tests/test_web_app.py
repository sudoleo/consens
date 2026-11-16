"""consens.io as an installable app and a search keyword (app/core/web_app.py).

Both hand a question over only as /app#q=… (or #?q=…): in the fragment it
never reaches the server, so a query string here would put questions into
the access log.
"""
import re
import xml.etree.ElementTree as ElementTree
from pathlib import Path
from urllib.parse import urlsplit

from fastapi.testclient import TestClient
from PIL import Image

import main
from app.core import web_app
from app.core.rate_limit import limiter

ROOT = Path(__file__).resolve().parents[1]
OPENSEARCH = "{http://a9.com/-/spec/opensearch/1.1/}"


def _client():
    limiter.reset()
    return TestClient(main.app, follow_redirects=False)


def _manifest(**headers):
    response = _client().get("/manifest.webmanifest", headers=headers)
    assert response.status_code == 200
    return response


def test_the_manifest_opens_the_app_in_a_window_of_its_own():
    response = _manifest()
    manifest = response.json()

    assert response.headers["content-type"].startswith("application/manifest+json")
    assert manifest["start_url"] == manifest["id"] == "/app"
    assert manifest["display"] == "standalone"
    assert manifest["scope"] == "/"
    assert manifest["name"] == "consens.io" and manifest["short_name"] == "consens"
    assert [item["url"] for item in manifest["shortcuts"]] == ["/app", "/app/watches"]


def test_the_manifest_takes_no_shared_text_yet():
    # share_target needs a query string or a service worker; it comes with
    # the iOS app.
    assert "share_target" not in _manifest().json()


def test_the_window_colours_are_the_light_page_colour_of_the_tokens():
    tokens = (ROOT / "static/css/variables.css").read_text(encoding="utf-8")
    ground = re.search(r":root\s*\{.*?--ground:\s*(#[0-9a-fA-F]+);", tokens, re.S).group(1).lower()
    manifest = _manifest().json()

    assert manifest["background_color"] == manifest["theme_color"] == ground


def test_every_icon_exists_in_the_size_it_claims():
    icons = _manifest().json()["icons"]
    purposes = set()
    for icon in icons:
        path = ROOT / urlsplit(icon["src"]).path.lstrip("/")
        side = int(icon["sizes"].split("x")[0])
        with Image.open(path) as image:
            assert image.size == (side, side), icon["src"]
        assert re.search(r"\?v=[0-9a-f]{12}$", icon["src"]), icon["src"]
        purposes.add((side, icon["purpose"]))

    assert {(192, "any"), (512, "any"), (512, "maskable")} <= purposes


def test_the_shortcuts_speak_the_readers_language():
    english = _manifest().json()
    german = _manifest(**{"Accept-Language": "de-DE,de;q=0.9"}).json()
    client = _client()
    client.cookies.set("consens_lang", "de")
    chosen = client.get("/manifest.webmanifest").json()

    assert [item["name"] for item in english["shortcuts"]] == ["New chat", "Watches"]
    assert [item["name"] for item in german["shortcuts"]] == ["Neuer Chat", "Watches"]
    assert german["lang"] == chosen["lang"] == "de"
    assert _manifest().headers["vary"] == "Accept-Language, Cookie"
    assert _manifest().headers["cache-control"].startswith("private")


def test_the_search_keyword_hands_the_question_over_in_the_fragment():
    response = _client().get("/opensearch.xml")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/opensearchdescription+xml")
    document = ElementTree.fromstring(response.content)
    url = document.find(f"{OPENSEARCH}Url")
    template = url.get("template")

    assert document.findtext(f"{OPENSEARCH}ShortName") == "consens.io"
    assert url.get("type") == "text/html"
    assert template == web_app.QUESTION_TEMPLATE
    parts = urlsplit(template)
    assert (parts.path, parts.query) == ("/app", "")
    # After a "?" in the fragment Chrome encodes the terms as a query value.
    assert parts.fragment == "?q={searchTerms}"


def test_every_page_with_the_icons_offers_the_manifest_and_the_search_keyword():
    partial = (ROOT / "templates/partials/head_icons.html").read_text(encoding="utf-8")
    assert '<link rel="manifest" href="/manifest.webmanifest" crossorigin="use-credentials">' in partial
    assert 'rel="search" type="application/opensearchdescription+xml"' in partial

    page = _client().get("/", headers={"Accept": "text/html"}).text
    assert 'href="/manifest.webmanifest"' in page and 'href="/opensearch.xml"' in page


def test_the_content_security_policy_lets_the_manifest_load():
    policy = _client().get("/app").headers["content-security-policy"]
    directives = dict(item.strip().split(" ", 1) for item in policy.split(";") if item.strip())
    allowed = directives.get("manifest-src", directives["default-src"])

    assert "'self'" in allowed.split()


def test_app_keeps_safaris_own_edge_colours():
    # iPhone Safari colours its bars after the page's edges (shell.css); a
    # theme-color in the template would take that over. Only an installed
    # Chrome or Edge window gets one, from the page itself (app-bootstrap.js).
    template = (ROOT / "templates/index.html").read_text(encoding="utf-8")
    assert 'name="theme-color"' not in template
