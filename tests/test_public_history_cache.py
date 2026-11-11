"""Public Topic and Watch pages read their history once per change, not per view.

Crawlers fetch every ?version= of a page one by one, and each view read up to
100 history documents. The history is shared by all versions of a page while
the documents the route reads anyway say nothing was added; a run written by
another process (no in-process invalidation) shows on the very next view.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routers import share as share_router
from app.api.routers import topics as topics_router
from app.core.history_cache import HistoryCache
from app.core.rate_limit import limiter
from app.services import share_snapshots, topics, watch_service
from test_topics_feature import FakeFirestore, _topic_with_runs, run_payload

NOW = datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc)


def _client(router):
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(router)
    return TestClient(app)


def _history_reads(db, path):
    """History queries and count aggregations the fake was asked for."""
    return sum(1 for entry in db.query_reads if entry[0] == path), db.count_reads


def test_topic_versions_share_one_read_of_the_record_until_a_run_is_added(monkeypatch):
    db = FakeFirestore()
    monkeypatch.setattr(topics, "db_firestore", db)
    topic, created = _topic_with_runs(db, 3)
    runs_path = (topics.TOPICS_COLLECTION, topic["id"], "runs")
    client = _client(topics_router.router)

    first = client.get("/topics/gpt-6")
    assert first.status_code == 200
    assert "Answer number 3." in first.text and "Checked 3 times" in first.text
    assert _history_reads(db, runs_path) == (1, 1)

    queries = len(db.query_reads)
    with patch.object(topics, "get_run", wraps=topics.get_run) as run_reads:
        for run in created[:2]:
            older = client.get(f"/topics/gpt-6?version={run['id']}")
            assert older.status_code == 200
            assert f"Answer number {created.index(run) + 1}." in older.text
            assert "Checked 3 times" in older.text
        assert client.get("/topics/gpt-6").text == first.text
    # Each view read the Topic (one query) and the version it shows, never
    # the record again; the repeated URL came whole from the page cache.
    assert _history_reads(db, runs_path) == (1, 1)
    assert len(db.query_reads) == queries + 3
    assert run_reads.call_count == 2

    # A scheduled run or a local server writes to the same database: nothing
    # in this process is told.
    topics.create_run(
        topic["id"],
        run_payload(observed_at=(NOW + timedelta(days=3)).isoformat(),
                    consensus_md="## Check 4\n\nAnswer number 4."),
        actor_uid="scheduler", db=db, now=NOW + timedelta(days=3),
    )
    latest = client.get("/topics/gpt-6")
    assert "Answer number 4." in latest.text and "Checked 4 times" in latest.text
    assert _history_reads(db, runs_path) == (2, 2)
    older = client.get(f"/topics/gpt-6?version={created[0]['id']}")
    assert "Answer number 1." in older.text and "Checked 4 times" in older.text
    assert _history_reads(db, runs_path) == (2, 2)


def test_a_topic_version_beyond_the_record_window_still_reads_alone(monkeypatch):
    db = FakeFirestore()
    monkeypatch.setattr(topics, "db_firestore", db)
    monkeypatch.setattr(topics_router, "TOPIC_PAGE_RUNS", 2)
    topic, created = _topic_with_runs(db, 4)
    runs_path = (topics.TOPICS_COLLECTION, topic["id"], "runs")
    client = _client(topics_router.router)

    assert "Checked 2 times" in client.get("/topics/gpt-6").text
    oldest = client.get(f"/topics/gpt-6?version={created[0]['id']}")
    assert oldest.status_code == 200 and "Answer number 1." in oldest.text
    # Sorted into the history of that view only.
    assert "Checked 3 times" in oldest.text
    assert "Checked 2 times" in client.get(f"/topics/gpt-6?version={created[3]['id']}").text
    assert client.get("/topics/gpt-6?version=doesnotexist").status_code == 404
    assert _history_reads(db, runs_path)[0] == 1


SHARE_ID = "A" * 16


def _check(day, answer, *, score=70):
    return {
        "ts": NOW + timedelta(days=day), "agreement_score": score, "changed": False,
        "severity": "minor", "change_summary": "", "trigger": "stable",
        "event_type": "watch.checked", "consensus_md": answer, "sources": [],
        "included_models": ["OpenAI", "Google Gemini"], "consensus_model": "OpenAI",
        "differences_data": {"agreement": {"score": score}},
    }


@pytest.fixture
def watch_page(monkeypatch):
    db = FakeFirestore()
    monkeypatch.setattr(share_snapshots, "db_firestore", db)
    monkeypatch.setattr(watch_service, "db_firestore", db)
    monkeypatch.setattr(share_snapshots, "list_related_shares", lambda *args, **kwargs: [])
    share_snapshots.invalidate_share_cache()
    db.documents[("shares", SHARE_ID)] = {
        "owner_uid": "u1", "slug": "will-it-change", "status": "active",
        "visibility": "public", "indexed": True,
        "question": "Will it change?", "consensus_md": "Original answer.",
        "differences_data": {"agreement": {"score": 60}},
        "latest_watch_run_id": "run0002bbbb", "last_watch_run_at": NOW + timedelta(days=1),
    }
    db.documents[("shares", SHARE_ID, "watch_history", "run0001aaaa")] = _check(0, "Answer one.")
    db.documents[("shares", SHARE_ID, "watch_history", "run0002bbbb")] = _check(1, "Answer two.")
    db.documents[("watches", "w1")] = {
        "share_id": SHARE_ID, "status": "active", "interval": "weekly",
        "created_at": NOW, "last_run_at": NOW + timedelta(days=1),
        "last_successful_run_id": "run0002bbbb", "accepted_run_id": "run0002bbbb",
        # Claimed already: the check below finishes this run.
        "current_run_id": "run0003cccc",
    }
    yield db
    share_snapshots.invalidate_share_cache()


def test_watch_versions_share_one_read_of_the_history_until_a_check_is_added(watch_page):
    db = watch_page
    history_path = ("shares", SHARE_ID, "watch_history")
    client = _client(share_router.router)
    page = f"/s/will-it-change-{SHARE_ID}"

    first = client.get(page)
    assert first.status_code == 200 and "Answer two." in first.text
    assert "Checked 2 times" in first.text
    assert _history_reads(db, history_path)[0] == 1
    for run_id, answer in (("run0001aaaa", "Answer one."), ("run0002bbbb", "Answer two.")):
        version = client.get(f"{page}?version={run_id}")
        assert version.status_code == 200 and answer in version.text
    assert client.get(page).status_code == 200
    assert _history_reads(db, history_path)[0] == 1

    # Another process finishes the check: this one's share cache keeps the
    # share as it was, only the Watch it reads on every view has moved.
    with patch.object(share_snapshots, "invalidate_share_cache"):
        watch_service.complete_watch_run(
            "w1",
            {"share_id": SHARE_ID, "current_run_id": "run0003cccc", "interval": "weekly",
             "last_successful_run_id": "run0002bbbb", "last_agreement_score": 70},
            {"consensus": "Answer three.", "agreement_score": 71, "changed": False,
             "severity": "minor", "change_summary": "", "differences_data": {"agreement": {"score": 71}},
             "included_models": ["OpenAI", "Google Gemini"], "consensus_model": "OpenAI"},
            now=NOW + timedelta(days=2), db=db,
        )
    latest = client.get(page)
    assert "Answer three." in latest.text and "Checked 3 times" in latest.text
    assert _history_reads(db, history_path)[0] == 2
    assert "Answer one." in client.get(f"{page}?version=run0001aaaa").text
    assert _history_reads(db, history_path)[0] == 2


def test_a_one_off_share_keeps_its_empty_history_too(watch_page):
    db = watch_page
    db.documents.pop(("watches", "w1"))
    for run_id in ("run0001aaaa", "run0002bbbb"):
        db.documents.pop(("shares", SHARE_ID, "watch_history", run_id))
    for field in ("latest_watch_run_id", "last_watch_run_at"):
        db.documents[("shares", SHARE_ID)].pop(field)
    client = _client(share_router.router)
    for _ in range(3):
        assert "Original answer." in client.get(f"/s/will-it-change-{SHARE_ID}").text
    assert _history_reads(db, ("shares", SHARE_ID, "watch_history"))[0] == 1


def test_a_failed_history_read_is_not_kept(watch_page):
    client = _client(share_router.router)
    page = f"/s/will-it-change-{SHARE_ID}"
    with patch.object(share_snapshots, "list_watch_history", side_effect=RuntimeError("down")):
        assert client.get(page).status_code == 200
    assert "Checked 2 times" in client.get(page).text


def test_history_cache_keeps_one_mark_per_page_and_drops_the_least_used():
    cache = HistoryCache(max_pages=2)
    loads = []

    def load(value):
        loads.append(value)
        return value

    assert cache.get_or_load("a", 1, lambda: load("a1")) == "a1"
    assert cache.get_or_load("a", 1, lambda: load("again")) == "a1"
    assert cache.get_or_load("a", 2, lambda: load("a2")) == "a2"
    cache.get_or_load("b", 1, lambda: load("b1"))
    cache.get_or_load("a", 2, lambda: load("again"))
    cache.get_or_load("c", 1, lambda: load("c1"))
    # "b" was used least recently; "a" stays.
    assert cache.get_or_load("a", 2, lambda: load("again")) == "a2"
    assert cache.get_or_load("b", 1, lambda: load("b1 again")) == "b1 again"
    assert loads == ["a1", "a2", "b1", "c1", "b1 again"]
    with pytest.raises(RuntimeError):
        cache.get_or_load("d", 1, lambda: (_ for _ in ()).throw(RuntimeError("down")))
    assert cache.get_or_load("d", 1, lambda: load("d1")) == "d1"
