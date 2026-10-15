"""Topic pages built from the Watch page parts (2026-10-15): picture, hub
card, the standing answer's opening, and Google redirects kept off the page."""

from datetime import timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routers import topics as topics_router
from app.core.rate_limit import limiter
from app.services import source_redirects, topic_images, topic_pipeline, topics, watch_images
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
