"""Topic pages built from the Watch page parts: picture, hub
card, the standing answer's opening, and Google redirects kept off the page."""

from datetime import timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routers import topics as topics_router
from app.services import check_page
from app.services.public_markdown import render_public_markdown
from app.core.rate_limit import limiter
from app.services import (
    source_redirects, topic_images, topic_pipeline, topics, watch_images, watch_symbols,
)
from test_topics_feature import NOW, FakeFirestore, run_payload, topic_payload

REDIRECT = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AbC123"


def client():
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(topics_router.router)
    return TestClient(app)


def found_image():
    return {
        "content": b"\x89PNG fake bytes", "content_type": "image/png", "width": 240, "height": 120,
        "kind": "logo", "source_url": "https://openai.com/", "source_host": "openai.com",
    }


def test_a_topic_gets_one_picture_from_its_sources_and_keeps_it(monkeypatch):
    db = FakeFirestore()
    topic = topics.create_topic(topic_payload(), actor_uid="admin", db=db, now=NOW)
    sources = [{"url": "https://openai.com/index/gpt-6"}, {"url": "https://news.example.com/a"}]
    searched = []

    def search(found_sources, question, condition="", *, fetch=None, sites=None):
        searched.append((question, sites))
        return found_image(), True

    monkeypatch.setattr(watch_images, "search", search)
    picks = []

    def pick(question, condition, domains):
        picks.append(domains)
        return {"symbol": "rocket", "sites": ["openai.com", "unrelated.example"]}

    current = topics.get_topic(topic["id"], db=db)
    assert topic_images.refresh_for_topic(topic["id"], current, sources, db=db, pick=pick) == "ready"
    assert searched == [("What is the current evidence about GPT-6?", ["openai.com"])]
    stored = topics.get_topic(topic["id"], db=db)
    assert stored["image"]["status"] == "ready" and stored["image"]["sites"] == ["openai.com"]

    view = topic_images.image_view(topic["id"], stored)
    assert view["url"] == f"/api/topics/{topic['id']}/image/{stored['image']['token']}"
    assert view["kind"] == "logo" and view["source_host"] == "openai.com"
    assert topic_images.load_image(topic["id"], stored["image"]["token"], db=db) == (
        b"\x89PNG fake bytes", "image/png"
    )
    assert topic_images.load_image(topic["id"], "0" * 20, db=db) is None
    # A finished picture stays; the Judge is not asked again.
    assert topic_images.refresh_for_topic(topic["id"], stored, sources, db=db, pick=pick) == "skipped"
    assert len(picks) == 1


def test_a_failed_search_counts_as_a_try_and_stops_after_the_limit(monkeypatch):
    db = FakeFirestore()
    topic = topics.create_topic(topic_payload(), actor_uid="admin", db=db, now=NOW)
    monkeypatch.setattr(watch_images, "search", lambda *a, **k: (None, True))
    sources = [{"url": "https://openai.com/index/gpt-6"}]
    for _ in range(topic_images.MAX_ATTEMPTS):
        current = topics.get_topic(topic["id"], db=db)
        assert topic_images.refresh_for_topic(topic["id"], current, sources, db=db, pick=None) == "none"
    current = topics.get_topic(topic["id"], db=db)
    assert topic_images.image_view(topic["id"], current) is None
    assert topic_images.refresh_for_topic(topic["id"], current, sources, db=db, pick=None) == "skipped"


def test_the_topic_page_and_hub_show_the_picture_and_the_standing_answer(monkeypatch):
    db = FakeFirestore()
    monkeypatch.setattr(topics, "db_firestore", db)
    topic = topics.create_topic(topic_payload(), actor_uid="admin", db=db, now=NOW)
    topics.create_run(topic["id"], run_payload(
        consensus_md="Here is the current picture:\n\n**GPT-6 Astra is out.** It shipped on Sep 4.",
    ), actor_uid="admin", db=db, now=NOW)
    later = NOW + timedelta(days=1)
    topics.create_run(topic["id"], run_payload(
        observed_at=later.isoformat(), change_type="major", change_summary="Astra shipped.",
        consensus_md="**GPT-6 Astra is out.** It shipped on Sep 4, 2026.",
    ), actor_uid="admin", db=db, now=later)
    # The hub card reads the opening from the Topic, not from its runs.
    assert topics.get_topic(topic["id"], db=db)["accepted_lead"] == (
        "GPT-6 Astra is out. It shipped on Sep 4, 2026."
    )
    monkeypatch.setattr(watch_images, "search", lambda *a, **k: (found_image(), True))
    topic_images.refresh_for_topic(
        topic["id"], topics.get_topic(topic["id"], db=db),
        [{"url": "https://openai.com/index/gpt-6"}], db=db, pick=None,
    )

    page = client().get("/topics/gpt-6")
    assert page.status_code == 200
    assert '<figure class="wp-image is-logo">' in page.text
    assert f'src="/api/topics/{topic["id"]}/image/' in page.text
    # The picture is decoration of the page, never the share card.
    assert "/image/" not in page.text.split("<script type=\"application/ld+json\">")[0]

    hub = client().get("/topics")
    assert hub.status_code == 200
    assert "GPT-6 Astra is out. It shipped on Sep 4, 2026." in hub.text
    assert "Model releases · Changed Jul 24" in hub.text
    assert 'class="topics-row-image is-logo"' in hub.text
    assert "/100" not in hub.text

    token = topics.get_topic(topic["id"], db=db)["image"]["token"]
    monkeypatch.setattr(topic_images, "load_image", lambda topic_id, tok: (b"img", "image/png") if tok == token else None)
    served = client().get(f"/api/topics/{topic['id']}/image/{token}")
    assert served.status_code == 200 and served.content == b"img"
    assert "immutable" in served.headers["Cache-Control"]
    assert client().get(f"/api/topics/{topic['id']}/image/{'0' * 20}").status_code == 404


def test_google_redirects_stay_off_the_topic_page(monkeypatch):
    db = FakeFirestore()
    monkeypatch.setattr(topics, "db_firestore", db)
    topic = topics.create_topic(topic_payload(), actor_uid="admin", db=db, now=NOW)
    topics.create_run(topic["id"], run_payload(
        consensus_md="OpenAI confirmed it [S1]. A blog repeated it [S2].",
        evidence=[
            {"id": "S1", "type": "official", "title": "GPT-6 announcement",
             "url": "https://openai.com/index/gpt-6"},
            {"id": "S2", "type": "press", "title": "reuters.com", "url": REDIRECT},
        ],
    ), actor_uid="admin", db=db, now=NOW)

    page = client().get("/topics/gpt-6")

    assert page.status_code == 200
    assert "vertexaisearch" not in page.text
    assert 'id="src-1"' in page.text and 'id="src-2"' not in page.text
    assert "[S2]" not in page.text
    assert 'class="wp-link" href="https://openai.com/index/gpt-6"' in page.text


def test_a_topic_check_resolves_redirects_before_the_judge_and_the_page(monkeypatch):
    seen = {}

    def pipeline(**kwargs):
        return {
            "consensus_response": "Answer.", "differences_data": {}, "differences": "",
            "agreement": {"score": 80, "level": "high"},
            "model_answers": [
                {"provider": "OpenAI", "model": "m1", "sources": [{"title": "Story", "url": REDIRECT}]},
                {"provider": "Grok", "model": "m2", "sources": []},
            ],
        }

    def resolve(sources):
        seen["before"] = [item["url"] for item in sources]
        return [{**item, "url": "https://www.reuters.com/story"} for item in sources]

    def first_check(consensus, keys, engine, *, condition="", new_sources=None):
        seen["judge"] = [item["url"] for item in new_sources]
        return {"changed": False}

    monkeypatch.setattr(topic_pipeline, "run_consensus_pipeline", pipeline)
    monkeypatch.setattr(topic_pipeline.provider_transport, "provider_available", lambda *a: True)
    monkeypatch.setattr(source_redirects, "resolve_sources", resolve)
    monkeypatch.setattr(topic_pipeline.evidence_change, "first_check", first_check)

    result = topic_pipeline.execute_topic(
        "Question?", "", model_overrides={"openai": "m1", "grok": "m2"},
    )

    assert seen["before"] == [REDIRECT]
    assert seen["judge"] == ["https://www.reuters.com/story"]
    assert [item["url"] for item in result["sources"]] == ["https://www.reuters.com/story"]


def test_without_a_good_picture_a_topic_shows_its_symbol(monkeypatch):
    db = FakeFirestore()
    monkeypatch.setattr(topics, "db_firestore", db)
    topic = topics.create_topic(topic_payload(), actor_uid="admin", db=db, now=NOW)
    topics.create_run(topic["id"], run_payload(), actor_uid="admin", db=db, now=NOW)
    monkeypatch.setattr(watch_images, "search", lambda *a, **k: (None, True))

    # The one Judge call that picks the sites also names the symbol.
    outcome = topic_images.refresh_for_topic(
        topic["id"], topics.get_topic(topic["id"], db=db),
        [{"url": "https://www.nature.com/articles/x"}], db=db,
        pick=lambda question, condition, domains: {"symbol": "sigma", "sites": []},
    )
    assert outcome == "none"
    stored = topics.get_topic(topic["id"], db=db)
    assert stored["symbol"] == "sigma"
    assert topic_images.visual_view(topic["id"], stored)["kind"] == "symbol"

    page = client().get("/topics/gpt-6")
    assert '<figure class="wp-image is-symbol" aria-hidden="true">' in page.text
    assert watch_symbols.SYMBOL_PATHS["sigma"] in page.text
    hub = client().get("/topics")
    assert '<span class="topics-row-image is-symbol"' in hub.text

    # A topic whose found picture is not fit for the page is closed for good.
    db.documents[("topics", topic["id"])]["image"]["status"] = "dismissed"
    assert not topic_images.needs_image(topics.get_topic(topic["id"], db=db))


def test_an_editor_can_set_a_real_picture_over_a_dismissed_search(monkeypatch):
    import io

    from PIL import Image

    db = FakeFirestore()
    monkeypatch.setattr(topics, "db_firestore", db)
    topic = topics.create_topic(topic_payload(), actor_uid="admin", db=db, now=NOW)
    topics.create_run(topic["id"], run_payload(), actor_uid="admin", db=db, now=NOW)
    db.documents[("topics", topic["id"])].update({
        "symbol": "sigma", "image": {"status": "dismissed", "attempts": 2, "tries": 2},
    })
    picture = io.BytesIO()
    Image.new("RGB", (1066, 600), (60, 80, 160)).save(picture, "JPEG")

    state = topic_images.set_editorial_image(
        topic["id"], picture.getvalue(),
        source_url="https://www.nature.com/articles/d41586-025-02343-x",
        crop=(83, 0, 983, 600), db=db,
    )

    assert state["picked_by"] == "editor" and state["source_host"] == "nature.com"
    assert (state["width"], state["height"]) == (320, 213)
    stored = topics.get_topic(topic["id"], db=db)
    # The picture wins over the symbol, and the search stays closed.
    assert topic_images.visual_view(topic["id"], stored)["kind"] == "article"
    assert not topic_images.needs_image(stored)
    assert topic_images.load_image(topic["id"], state["token"], db=db)[1] == "image/webp"
    page = client().get("/topics/gpt-6")
    assert f'/api/topics/{topic["id"]}/image/{state["token"]}' in page.text
    assert 'href="https://www.nature.com/articles/d41586-025-02343-x"' in page.text


SPLIT_ANSWER = """Grok 5 is not out yet.

## What xAI has announced

- **Announced by Elon Musk on 2026-09-14** on X.
- xAI said that **“Grok 5 is currently in training.”**
- Status: unreleased.
"""


def contradiction(claim, anchor, other, severity="major", **fields):
    return {
        "type": "contradiction", "severity": severity, "claim": claim,
        "consensus_anchor": anchor, "anchor_occurrence": 0,
        "positions": [
            {"in_answer": True, "stance": claim, "models": ["Grok", "Gemini"], "quote": "as they wrote it"},
            {"stance": other, "models": ["OpenAI"], "quote": ""},
        ],
        **fields,
    }


SPLITS = [
    contradiction("Grok 4.8 was announced.", "**Announced by Elon Musk on 2026-09-14** on X.",
                  "There is no primary-source confirmation.", verify="Check the posts."),
    contradiction("The rollout reached everyone.", "Status: unreleased.", "It reached paid users only.",
                  severity="minor"),
    contradiction("xAI said Grok 5 is in training.", "xAI said that **“Grok 5 is currently in training.”**",
                  "There is no confirmed announcement of Grok 5."),
    {"type": "emphasis", "claim": "Weight", "positions": []},
]


def test_a_marked_passage_survives_the_emphasis_around_it():
    """grok-5-release-date: a passage ending in bold kept its asterisks,
    because the token after "**" read as a letter and the bold never closed."""
    marked = check_page.mark_passages(SPLIT_ANSWER, SPLITS, [0, 2])
    html = check_page.fill_marks(render_public_markdown(marked, []))

    assert ('<mark class="wp-mark" data-diff="0"><strong>Announced by Elon Musk on 2026-09-14</strong> on X.</mark>'
            in html)
    assert ('<mark class="wp-mark" data-diff="2">xAI said that <strong>“Grok 5 is currently in training.”</strong></mark>'
            in html)
    assert "WPMARK" not in html and "**" not in html and "\u27e6" not in html
    # Nothing but the marks changed.
    plain = render_public_markdown(SPLIT_ANSWER, [])
    assert html.replace('<mark class="wp-mark" data-diff="0">', "").replace(
        '<mark class="wp-mark" data-diff="2">', "").replace("</mark>", "") == plain


def test_a_passage_the_renderer_splits_is_left_unmarked():
    # The anchor starts inside the bold run: a mark there would cross it.
    crossing = [{"consensus_anchor": "Elon Musk on 2026-09-14** on X."}]
    html = check_page.fill_marks(render_public_markdown(check_page.mark_passages(SPLIT_ANSWER, crossing, [0]), []))
    assert html == render_public_markdown(SPLIT_ANSWER, [])
    # No anchor, an anchor over two lines, an anchor the answer does not contain: no token at all.
    for anchor in ("", "- **Announced by Elon Musk on 2026-09-14** on X.\n- xAI said", "Not in the answer."):
        assert check_page.mark_passages(SPLIT_ANSWER, [{"consensus_anchor": anchor}], [0]) == SPLIT_ANSWER
    # A passage that opens a list item is marked after the bullet.
    bullet = [{"consensus_anchor": "- Status: unreleased."}]
    assert "- \u27e6WPMARK0OPEN\u27e7Status: unreleased.\u27e6WPMARK0CLOSE\u27e7" in check_page.mark_passages(
        SPLIT_ANSWER, bullet, [0])
    assert check_page.fill_marks("left \u27e6WPMARK7OPEN\u27e7 alone") == "left  alone"


def test_a_topic_page_states_its_critical_contradictions_openly(monkeypatch):
    db = FakeFirestore()
    monkeypatch.setattr(topics, "db_firestore", db)
    topic = topics.create_topic(topic_payload(), actor_uid="admin", db=db, now=NOW)
    topics.create_run(topic["id"], run_payload(
        consensus_md=SPLIT_ANSWER, differences_data={"differences": SPLITS},
    ), actor_uid="admin", db=db, now=NOW)

    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(topics_router.router)
    text = TestClient(app).get("/topics/gpt-6").text

    # The two critical contradictions as the app's cards, open, each with an
    # id its marked passage points at; the minor one stays in the fold.
    section = text.split('<section class="wp-split diff-view"', 1)[1].split("</section>", 1)[0]
    assert ">Where the models disagree</h2>" in section
    assert section.count('<details class="diff-card is-contradiction is-major"') == 2
    assert 'id="topicDiff0" open>' in section and 'id="topicDiff2" open>' in section
    assert "topicDiff1" not in text and "It reached paid users only." not in section
    assert "In contrast" in section and "There is no primary-source confirmation." in section
    assert "Worth verifying: Check the posts." in section
    answer = text.split('id="wpAnswerHeading"', 1)[1].split('<section class="wp-split', 1)[0]
    assert answer.count('<mark class="wp-mark" data-diff=') == 2
    assert text.index('id="wpAnswerHeading"') < text.index("wp-split diff-view") < text.index('id="wpHistoryHeading"')
    # The fold keeps every difference, as before.
    fold = text.split('<details class="wp-more wp-disclosure">', 1)[1]
    assert "It reached paid users only." in fold and "There is no primary-source confirmation." in fold


def test_a_topic_without_a_critical_contradiction_has_no_such_section(monkeypatch):
    db = FakeFirestore()
    monkeypatch.setattr(topics, "db_firestore", db)
    topic = topics.create_topic(topic_payload(), actor_uid="admin", db=db, now=NOW)
    topics.create_run(topic["id"], run_payload(
        consensus_md=SPLIT_ANSWER, differences_data={"differences": SPLITS[1:2] + SPLITS[3:]},
    ), actor_uid="admin", db=db, now=NOW)
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(topics_router.router)
    text = TestClient(app).get("/topics/gpt-6").text
    assert "wp-split" not in text and "wp-mark" not in text
