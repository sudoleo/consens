"""Link previews: every public page shows a 1200 x 630 card, never the favicon."""
import json
import re
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from app.api.routers import pages as pages_router
from app.core.assets import asset_url
from app.core.site import SITE_URL
from app.services import og_image, topics
from adapter_test_support import http_adapter  # noqa: F401 - fixture
from test_topic_public_http import public_topics, publish  # noqa: F401 - fixture
from test_topics_feature import topic_payload

ROOT = Path(__file__).resolve().parents[1]
BRAND_CARD = SITE_URL + asset_url("/static/og-home-v2.png")
# Every public template except the landing page, which spells out the same
# brand card itself.
CARD_TEMPLATES = [
    "about", "ai-model-comparison", "benchmark", "consensus-engine", "model-pulse",
    "questions", "topics", "topic", "share", "watch_share", "index",
]


def meta(html, key):
    found = re.search(r'<meta (?:property|name)="%s" content="([^"]*)"' % re.escape(key), html)
    return found.group(1) if found else None


@pytest.fixture(scope="module")
def pages_client():
    app = FastAPI()
    app.include_router(pages_router.router)
    return TestClient(app)


@pytest.mark.parametrize("name", CARD_TEMPLATES)
def test_public_templates_take_their_card_from_the_partial(name):
    template = (ROOT / "templates" / f"{name}.html").read_text(encoding="utf-8")
    assert '{% include "partials/og_card.html" %}' in template
    for tag in ('property="og:image', 'name="twitter:card"', 'name="twitter:image'):
        assert tag not in template, f"{name} sets {tag} next to the partial"


def test_the_partial_shows_the_brand_card_unless_a_page_brings_its_own():
    partial = pages_router.templates.env.get_template("partials/og_card.html")
    brand = partial.render(og_card_image="")
    assert meta(brand, "og:image") == meta(brand, "twitter:image") == BRAND_CARD
    assert meta(brand, "twitter:card") == "summary_large_image"
    assert (meta(brand, "og:image:width"), meta(brand, "og:image:height")) == ("1200", "630")
    own = partial.render(og_card_image="https://www.consens.io/topics/x/og.png",
                         og_card_alt='When "will" it ship?')
    assert meta(own, "og:image") == meta(own, "twitter:image") == "https://www.consens.io/topics/x/og.png"
    assert meta(own, "og:image:alt") == "When &#34;will&#34; it ship?"


@pytest.mark.parametrize("path", ["/about", "/benchmark", "/app"])
def test_info_pages_and_the_app_share_the_brand_card(pages_client, path):
    response = pages_client.get(path)
    assert response.status_code == 200
    assert meta(response.text, "og:image") == BRAND_CARD
    assert meta(response.text, "twitter:card") == "summary_large_image"
    # The favicon stays the Organization logo in JSON-LD, never a preview.
    assert not re.search(r"<meta [^>]*favicon", response.text.split("</head>", 1)[0])


def test_the_app_names_the_product_it_is(pages_client):
    head = pages_client.get("/app").text.split("</head>", 1)[0]
    assert "<title>consens.io</title>" in head
    assert "Compare AI Answers" not in head
    assert meta(head, "og:url") == "https://www.consens.io/app"
    # The script resets the tab to the same title when a chat is closed.
    script = (ROOT / "static" / "js" / "app-core.js").read_text(encoding="utf-8")
    assert 'const DEFAULT_APP_TITLE = "consens.io";' in script


@pytest.mark.skipif(not og_image.is_available(), reason="Pillow/Font fehlt")
def test_a_topic_page_previews_its_own_question(public_topics):  # noqa: F811
    h = public_topics
    publish(h, "gpt-six", title="When will GPT-6 be released?")
    page = h.client.get("/topics/gpt-six")
    assert page.status_code == 200
    card_url = f"{SITE_URL}/topics/gpt-six/og.png"
    assert meta(page.text, "og:image") == meta(page.text, "twitter:image") == card_url
    assert meta(page.text, "og:image:alt") == meta(page.text, "og:title")
    graph = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>',
                                 page.text, re.S).group(1))
    article = next(node for node in graph["@graph"] if node.get("@type") == "Article")
    assert article["image"] == card_url

    card = h.client.get("/topics/gpt-six/og.png")
    assert card.status_code == 200 and card.headers["content-type"] == "image/png"
    assert card.headers["X-Robots-Tag"] == "noindex"
    assert Image.open(BytesIO(card.content)).size == (1200, 630)


@pytest.mark.skipif(not og_image.is_available(), reason="Pillow/Font fehlt")
def test_topic_cards_end_with_their_page(public_topics):  # noqa: F811
    h = public_topics
    archived = publish(h, "gone-topic")
    h.topic_db.documents[(topics.TOPICS_COLLECTION, archived["id"])]["status"] = "archived"
    topics.create_topic(topic_payload(slug="draft-topic"), actor_uid="admin", db=h.topic_db)
    for slug in ("gone-topic", "draft-topic", "no-such-topic"):
        assert h.client.get(f"/topics/{slug}/og.png").status_code == 404
