"""Pictures on a Topic's Direct-links cards (app/services/topic_pictures.py).

The picture is the preview a cited page names for itself; which pages qualify
is a rule about the source. No model is asked, a blocked page has no picture,
and a card row is plain again as soon as fewer than two pictures remain.
"""

import io
from datetime import timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from app.api.routers import topics as topics_router
from app.core.rate_limit import limiter
from app.services import topic_images, topic_pictures, topic_runner, topics, watch_images
from test_topics_feature import NOW, FakeFirestore, run_payload, topic_payload

ANNOUNCEMENT = "https://openai.com/index/gpt-6-announcement"
DOCS = "https://platform.openai.com/docs/models/gpt-6"
STORY = "https://news.example.com/2026/gpt-6-launch-story"
FORUM = "https://www.reddit.com/r/openai/comments/gpt6"
ANSWER = "OpenAI announced GPT-6 and documented it on platform.openai.com."


def photo(seed=1, size=(1200, 630), fmt="JPEG"):
    """A picture with many colours (not flat) that still compresses small."""
    ramp = Image.linear_gradient("L").resize(size)
    image = Image.merge("RGB", (ramp, ramp.rotate(180), Image.new("L", size, (seed * 37) % 256)))
    buffer = io.BytesIO()
    image.save(buffer, fmt)
    return buffer.getvalue()


def flat(size=(1200, 630)):
    buffer = io.BytesIO()
    Image.new("RGB", size, (20, 30, 200)).save(buffer, "PNG")
    return buffer.getvalue()


def page(image_url):
    return f'<html><head><meta property="og:image" content="{image_url}"></head><body></body></html>'


class Fetch:
    """Pages and images by URL; anything unknown is refused like a bot wall."""

    def __init__(self, pages=None, images=None):
        self.pages, self.images, self.calls = dict(pages or {}), dict(images or {}), []

    async def __call__(self, url, purpose):
        self.calls.append((purpose, url))
        if purpose == "page":
            if url not in self.pages:
                raise ValueError("status_403")
            return url, self.pages[url].encode("utf-8"), "text/html", False
        if url not in self.images:
            raise ValueError("status_404")
        return url, self.images[url], "image/jpeg", False


def evidence(*urls):
    kinds = {FORUM: "x", STORY: "press"}
    return [
        {"id": f"S{index}", "type": kinds.get(url, "official"), "title": f"GPT-6 source number {index}", "url": url}
        for index, url in enumerate(urls, start=1)
    ]


def topic_with_run(db, urls, **topic_fields):
    topic = topics.create_topic(topic_payload(**topic_fields), actor_uid="admin", db=db, now=NOW)
    topics.create_run(
        topic["id"], run_payload(consensus_md=ANSWER, evidence=evidence(*urls)),
        actor_uid="admin", db=db, now=NOW,
    )
    return topic["id"]


def two_pictures():
    return Fetch(
        pages={ANNOUNCEMENT: page("https://cdn.openai.com/hero-a.jpg"), DOCS: page("https://cdn.openai.com/hero-b.jpg")},
        images={"https://cdn.openai.com/hero-a.jpg": photo(1), "https://cdn.openai.com/hero-b.jpg": photo(2)},
    )


def client():
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(topics_router.router)
    return TestClient(app)


def test_only_direct_sources_and_preferred_reporting_may_give_a_picture():
    preferred = ["openai.com", "techcrunch.com"]
    wire = "https://techcrunch.com/2026/09/03/openai-launches-gpt-6"
    paper = "https://arxiv.org/abs/2609.01234"
    items = evidence(STORY, FORUM, ANNOUNCEMENT, DOCS) + [
        {"id": "S7", "type": "press", "title": "OpenAI launches GPT-6 today", "url": wire},
        {"id": "S8", "type": "research", "title": "A paper about GPT-6 systems", "url": paper},
        {"id": "S9", "type": "official", "title": "GPT-6 system card as a file", "url": "https://openai.com/gpt-6-card.pdf"},
    ]

    pages = topic_pictures.candidate_pages(items, ANSWER, preferred)

    urls = [entry["url"] for entry in pages]
    # Reporting outside the preferred domains and community pages never
    # qualify; a PDF has no preview picture.
    assert STORY not in urls and FORUM not in urls and not any(url.endswith(".pdf") for url in urls)
    # In the order of the cards: the pages the answer names, best role first.
    assert urls == [ANNOUNCEMENT, DOCS, paper, wire]


def test_pictures_are_stored_by_content_next_to_the_topic_picture(monkeypatch):
    db = FakeFirestore()
    topic_id = topic_with_run(db, [ANNOUNCEMENT, DOCS, STORY])
    db.collection("topic_images").document(topic_id).set({"token": "head", "content": b"head"})
    fetch = two_pictures()

    assert topic_pictures.refresh_for_topic(topic_id, db=db, fetch=fetch) == "ready"

    stored = topics.get_topic(topic_id, db=db)["pictures"]
    assert [item["source_url"] for item in stored["items"]] == [ANNOUNCEMENT, DOCS]
    assert ("page", STORY) not in fetch.calls  # never asked: it only reports
    for item in stored["items"]:
        assert watch_images.TOKEN_RE.match(item["token"])
        assert (item["width"], item["height"]) == (640, 336)
        saved = db.documents[("topic_images", f"{topic_id}_{item['token']}")]
        assert saved["content_type"] == "image/webp" and len(saved["content"]) <= watch_images.STORED_MAX_BYTES
        assert topic_pictures.load_picture(topic_id, item["token"], db=db) == (saved["content"], "image/webp")
    # The Topic's own picture lives under the bare id and stays.
    assert db.documents[("topic_images", topic_id)] == {"token": "head", "content": b"head"}
    assert topic_pictures.load_picture(topic_id, "0" * 20, db=db) is None
    assert topic_pictures.load_picture("../" + topic_id, stored["items"][0]["token"], db=db) is None


def test_a_stored_picture_is_not_fetched_again():
    db = FakeFirestore()
    topic_id = topic_with_run(db, [ANNOUNCEMENT, DOCS])
    assert topic_pictures.refresh_for_topic(topic_id, db=db, fetch=two_pictures()) == "ready"
    before = dict(db.documents[("topics", topic_id)]["pictures"])

    again = two_pictures()
    assert topic_pictures.refresh_for_topic(topic_id, db=db, fetch=again) == "kept"

    assert again.calls == []
    assert db.documents[("topics", topic_id)]["pictures"] == before


def test_a_blocked_page_has_no_picture_and_is_left_alone_after_three_passes():
    db = FakeFirestore()
    topic_id = topic_with_run(db, [ANNOUNCEMENT, DOCS])
    fetch = Fetch()  # every page answers 403

    for attempt in range(1, topic_pictures.MAX_MISSES + 1):
        assert topic_pictures.refresh_for_topic(topic_id, db=db, fetch=fetch) == "none"
        misses = topics.get_topic(topic_id, db=db)["pictures"]["misses"]
        assert sorted(misses.values()) == [attempt, attempt]
    asked = len(fetch.calls)
    assert asked == 2 * topic_pictures.MAX_MISSES

    assert topic_pictures.refresh_for_topic(topic_id, db=db, fetch=fetch) == "kept"
    assert len(fetch.calls) == asked
    assert topics.get_topic(topic_id, db=db)["pictures"]["items"] == []


def test_a_picture_two_pages_of_one_site_share_is_nobodys_picture():
    db = FakeFirestore()
    second = "https://openai.com/index/gpt-6-for-developers"
    topic_id = topic_with_run(db, [ANNOUNCEMENT, second, DOCS])
    share_card = "https://cdn.openai.com/share-card.jpg"
    fetch = Fetch(
        pages={ANNOUNCEMENT: page(share_card), second: page(share_card), DOCS: page("https://cdn.openai.com/docs.jpg")},
        images={share_card: photo(1), "https://cdn.openai.com/docs.jpg": photo(2)},
    )

    assert topic_pictures.refresh_for_topic(topic_id, db=db, fetch=fetch) == "ready"

    stored = topics.get_topic(topic_id, db=db)["pictures"]
    assert [item["source_url"] for item in stored["items"]] == [DOCS]
    # Both pages are settled: the next check does not ask them again.
    assert sorted(stored["misses"].values()) == [topic_pictures.MAX_MISSES] * 2
    assert len([path for path in db.documents if path[0] == "topic_images"]) == 1

    # The same bytes under two addresses are the same share card.
    db = FakeFirestore()
    topic_id = topic_with_run(db, [ANNOUNCEMENT, second])
    fetch = Fetch(
        pages={ANNOUNCEMENT: page("https://cdn.openai.com/a.jpg"), second: page("https://cdn.openai.com/b.jpg")},
        images={"https://cdn.openai.com/a.jpg": photo(1), "https://cdn.openai.com/b.jpg": photo(1)},
    )
    assert topic_pictures.refresh_for_topic(topic_id, db=db, fetch=fetch) == "none"


def test_logos_flat_cards_and_portraits_are_not_pictures():
    db = FakeFirestore()
    third = "https://help.openai.com/en/articles/gpt-6-in-chatgpt"
    topic_id = topic_with_run(db, [ANNOUNCEMENT, DOCS, third])
    fetch = Fetch(
        pages={
            ANNOUNCEMENT: page("https://cdn.openai.com/brand/logo-share.png"),
            DOCS: page("https://cdn.openai.com/flat.png"),
            third: page("https://cdn.openai.com/portrait.jpg"),
        },
        images={
            "https://cdn.openai.com/brand/logo-share.png": photo(1),
            "https://cdn.openai.com/flat.png": flat(),
            "https://cdn.openai.com/portrait.jpg": photo(3, size=(630, 1200)),
        },
    )
    notes = {}
    topic = topics.get_topic(topic_id, db=db)
    pictures, misses = topic_pictures.find_pictures(
        topic_pictures.standing_pages(topic, db=db), topic, fetch=fetch, notes=notes,
    )
    assert pictures == [] and len(misses) == 3
    # The logo is recognised by its address and never downloaded.
    assert ("image", "https://cdn.openai.com/brand/logo-share.png") not in fetch.calls
    assert notes[topic_pictures.picture_key(ANNOUNCEMENT)] == "preview is a logo or a default image"


def test_a_new_answer_rewrites_the_list_and_drops_unused_bytes():
    db = FakeFirestore()
    topic_id = topic_with_run(db, [ANNOUNCEMENT, DOCS])
    assert topic_pictures.refresh_for_topic(topic_id, db=db, fetch=two_pictures()) == "ready"
    old = {item["source_url"]: item["token"] for item in topics.get_topic(topic_id, db=db)["pictures"]["items"]}

    later = NOW + timedelta(days=7)
    card = "https://openai.com/index/gpt-6-system-card"
    topics.create_run(topic_id, run_payload(
        observed_at=later.isoformat(), consensus_md=ANSWER, evidence=evidence(ANNOUNCEMENT, card),
    ), actor_uid="admin", db=db, now=later)
    fetch = Fetch(pages={card: page("https://cdn.openai.com/card.jpg")},
                  images={"https://cdn.openai.com/card.jpg": photo(5)})

    assert topic_pictures.refresh_for_topic(topic_id, db=db, fetch=fetch) == "ready"

    items = topics.get_topic(topic_id, db=db)["pictures"]["items"]
    assert [item["source_url"] for item in items] == [ANNOUNCEMENT, card]
    assert fetch.calls == [("page", card), ("image", "https://cdn.openai.com/card.jpg")]
    kept = {path[1] for path in db.documents if path[0] == "topic_images"}
    assert kept == {f"{topic_id}_{item['token']}" for item in items}
    assert f"{topic_id}_{old[DOCS]}" not in kept


def test_the_page_shows_picture_cards_from_two_pictures_on(monkeypatch):
    db = FakeFirestore()
    monkeypatch.setattr(topics, "db_firestore", db)
    topic_id = topic_with_run(db, [ANNOUNCEMENT, DOCS, STORY])
    first = client().get("/topics/gpt-6").text
    assert "has-pictures" not in first and "wp-link-picture" not in first

    assert topic_pictures.refresh_for_topic(topic_id, db=db, fetch=two_pictures()) == "ready"
    topics_router.invalidate_topic_pages()
    text = client().get("/topics/gpt-6").text

    items = topics.get_topic(topic_id, db=db)["pictures"]["items"]
    assert 'class="wp-links-list has-pictures"' in text
    for item in items:
        assert (f'<img src="/api/topics/{topic_id}/picture/{item["token"]}" alt="" '
                f'width="640" height="336" loading="lazy" decoding="async">') in text
    # The reporting page keeps its card; in a picture row it shows its icon.
    assert text.count('class="wp-link" href=') == 3
    assert text.count('class="wp-link-picture is-empty"') == 1
    # Decoration of the page: never the share card, never structured data.
    head = text.split("</head>")[0]
    assert "/picture/" not in head

    # An older version keeps its plain cards.
    run_id = topics.get_topic(topic_id, db=db)["latest_run_id"]
    versioned = client().get(f"/topics/gpt-6?version={run_id}").text
    assert "has-pictures" not in versioned and "/picture/" not in versioned

    # One picture alone leaves the row plain.
    state = db.documents[("topics", topic_id)]["pictures"]
    db.documents[("topics", topic_id)]["pictures"] = {**state, "items": state["items"][:1]}
    topics_router.invalidate_topic_pages()
    single = client().get("/topics/gpt-6").text
    assert "has-pictures" not in single and "/picture/" not in single


def test_cards_without_pictures_render_as_they_always_did():
    """Watch pages share the macro and pass no pictures."""
    links = [
        {"url": "https://openai.com/index/gpt-6", "title": "GPT-6 announcement", "domain": "openai.com"},
        {"url": "https://example.com/a-story", "title": "A story", "domain": "example.com"},
    ]
    module = topics_router.templates.env.get_template("partials/check_page.html").module
    plain = str(module.direct_links(links))
    assert "has-pictures" not in plain and "wp-link-picture" not in plain
    assert '<ul class="wp-links-list">' in plain
    assert plain.count('class="wp-link-icon site-icon"') == 2 and plain.count("wp-link-arrow") == 2

    one = str(module.direct_links([{**links[0], "picture": {"url": "/p", "width": 640, "height": 336}}, links[1]]))
    assert "has-pictures" not in one and "wp-link-picture" not in one


def test_the_picture_route_serves_known_tokens_with_a_long_cache(monkeypatch):
    token = "ab" * 10
    seen = []

    def load(topic_id, tok):
        seen.append((topic_id, tok))
        return (b"webp-bytes", "image/webp") if tok == token else None

    monkeypatch.setattr(topic_pictures, "load_picture", load)
    served = client().get(f"/api/topics/Topic12345678/picture/{token}")
    assert served.status_code == 200 and served.content == b"webp-bytes"
    assert served.headers["content-type"] == "image/webp"
    assert "immutable" in served.headers["Cache-Control"] and "max-age=2592000" in served.headers["Cache-Control"]
    assert client().get(f"/api/topics/Topic12345678/picture/{'0' * 20}").status_code == 404
    assert seen[0] == ("Topic12345678", token)


def test_a_check_schedules_the_pictures_only_outside_tests(monkeypatch):
    # Unit, E2E and mock runs never fetch anything.
    assert topic_pictures.schedule_after_run("Topic12345678") is False

    submitted = []
    monkeypatch.setattr(watch_images, "background_enabled", lambda: True)
    monkeypatch.setattr(watch_images, "_submit", lambda name, job: submitted.append(name) or True)
    assert topic_pictures.schedule_after_run("Topic12345678") is True
    assert topic_pictures.schedule_after_run("not a topic id") is False
    assert submitted == ["topic-pictures:Topic12345678"]

    db = FakeFirestore()
    monkeypatch.setattr(topics, "db_firestore", db)
    topic = topics.create_topic(topic_payload(), actor_uid="admin", db=db, now=NOW)
    topics.create_run(topic["id"], run_payload(), actor_uid="admin", db=db, now=NOW)
    db.documents[("topics", topic["id"])].update({
        "current_run_id": "automatic-run", "claimed_until": NOW, "last_run_status": "running",
    })
    monkeypatch.setattr(topic_images, "schedule_after_run", lambda *args: False)

    def execute(question, previous_consensus, **kwargs):
        return {
            "consensus": ANSWER, "agreement_score": 70, "changed": False, "opinion_map": {},
            "differences_data": {}, "sources": [], "consensus_model": "OpenAI",
            "included_models": ["OpenAI: gpt-6-luna", "Grok: grok-4.3"],
        }

    topic_runner.execute_claimed_topic(
        topics.get_topic(topic["id"], db=db), actor_uid="admin", db=db,
        now=NOW + timedelta(days=1), executor=execute,
    )
    assert submitted[-1] == "topic-pictures:" + topic["id"]
