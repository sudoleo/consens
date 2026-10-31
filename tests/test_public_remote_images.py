"""Public pages load no other site's images (audit 2026-10-28).

Until then render_public_markdown (nh3) let an answer's <img> with any https
source through, and the CSP allowed every https image: a shared, Topic, Watch
or Check page made its readers' browsers fetch a model's (or an injected)
picture, which told its host who read the page. The app had blocked them all
along (markdown-stream.js neutralizeRemoteMedia).
"""

import re

import pytest
from fastapi.testclient import TestClient

from app.services import public_markdown
from app.services.public_markdown import render_public_markdown
from test_security_headers import _app


@pytest.mark.parametrize("markdown,note", [
    ("![a chart](https://tracker.example/pixel.png?reader=1)", "[Image not loaded: a chart]"),
    ("![](http://tracker.example/p.png)", "[External image not loaded]"),
    ("![x](//tracker.example/p.png)", "[Image not loaded: x]"),
    ("[see ![logo](https://tracker.example/l.png)](https://example.org)", "[Image not loaded: logo]"),
])
def test_an_answers_remote_image_is_a_note(markdown, note):
    html = render_public_markdown("Before. " + markdown + " After.")
    assert "tracker.example" not in html.replace('href="https://example.org"', "")
    assert "<img" not in html
    assert f'<span class="blocked-remote-image">{note}</span>' in html


def test_a_file_name_of_the_agent_is_a_local_note_and_own_images_stay():
    html = render_public_markdown("![chart](chart.png) ![figure](/api/topics/t1/image/abc)")
    assert '<span class="blocked-remote-image is-local-ref">[Image not loaded: chart]</span>' in html
    assert '<img src="/api/topics/t1/image/abc" alt="figure">' in html


def test_a_picture_the_agent_placed_leaves_nothing_on_a_public_page():
    """The picture is a file of the private chat (agent_web_images,
    2026-10-31): neither it nor a note or an empty paragraph shows."""
    html = render_public_markdown("Intro.\n\n![Jeef](picture:p2)\n\nText ![x](picture:f1) on.")
    assert "picture:" not in html and "Jeef" not in html and "Image not loaded" not in html
    assert html.count("<p>") == 2 and "<p></p>" not in html and "Text  on." in html


def test_alt_text_cannot_break_out_of_the_note():
    html = render_public_markdown('![<b onmouseover="x">bad</b>](https://tracker.example/p.png)')
    assert "<b" not in html and "&lt;b onmouseover=" in html


def test_nh3_drops_a_remote_image_source_that_reached_the_html():
    # The last layer, for any image markup that got past the tokens.
    assert public_markdown._same_origin_images_only("img", "src", "https://tracker.example/p.png") is None
    assert public_markdown._same_origin_images_only("img", "src", "/api/topics/favicon?d=a.b") == "/api/topics/favicon?d=a.b"
    assert public_markdown._same_origin_images_only("a", "href", "https://example.org") == "https://example.org"
    for other_host in ("//tracker.example/p.png", "/\\tracker.example/p.png", " https://t.example/p"):
        assert public_markdown._same_origin_images_only("img", "src", other_host) is None


def test_site_links_and_source_pills_keep_their_own_favicons():
    sources = [{"id": "S1", "url": "https://agency.example/report", "title": "Agency"}]
    html = render_public_markdown("See [the report](https://agency.example/report).", sources, source_pills=True)
    assert 'src="/api/topics/favicon?d=agency.example"' in html


def test_the_policy_allows_no_other_sites_images():
    response = TestClient(_app()).get("/two-cookies")
    policy = response.headers["content-security-policy"]
    img_src = re.search(r"img-src ([^;]*);", policy).group(1).split()
    assert "https:" not in img_src and "*" not in img_src
    assert img_src[:2] == ["'self'", "data:"]
