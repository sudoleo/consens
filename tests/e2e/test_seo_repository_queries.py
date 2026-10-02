"""Native Firestore query and BatchGet contracts, no browser/provider calls."""
from datetime import date, datetime, timezone
from uuid import uuid4
from app.services import seo_repository as seo
from native_support import native_db


def test_seo_native_latest_judgments_and_unordered_batch_identity(
    native_db, monkeypatch
):
    db = native_db
    # Separate collections avoid reading or clearing another task's documents.
    namespace = "audit-seo-" + uuid4().hex
    for key in (
        "SEO_PAGES_COLLECTION",
        "SEO_RUNS_COLLECTION",
        "SEO_JUDGMENTS_COLLECTION",
    ):
        monkeypatch.setattr(seo, key, namespace + "-" + key.lower())
    repo = seo.FirestoreSeoRepository(db)
    a = db.tracked(seo.SEO_PAGES_COLLECTION, "a")
    b = db.tracked(seo.SEO_PAGES_COLLECTION, "b")
    for ref, value in ((a, 3), (b, 9)):
        ref.collection(seo.DAILY_METRICS_SUBCOLLECTION).document("2026-10-01").set(
            {"clicks": value, "date": "wrong", "page_id": "wrong"}
        )
    data = repo.list_metrics_for_pages(
        ["b", "a", "absent", "a"], date(2026, 10, 1), date(2026, 10, 2)
    )
    assert data == {
        "a": [{"clicks": 3, "date": "2026-10-01", "page_id": "a"}],
        "b": [{"clicks": 9, "date": "2026-10-01", "page_id": "b"}],
        "absent": [],
    }
    assert repo.last_run() is None
    for day in (1, 3, 2):
        stamp = datetime(2026, 10, day, tzinfo=timezone.utc)
        db.tracked(seo.SEO_RUNS_COLLECTION, str(day)).set({"started_at": stamp})
        db.tracked(seo.SEO_JUDGMENTS_COLLECTION, str(day)).set(
            {"page_id": "a", "created_at": stamp}
        )
        a.collection(seo.QUERY_SNAPSHOTS_SUBCOLLECTION).document(str(day)).set(
            {"period_end": f"2026-10-0{day}"}
        )
    assert repo.last_run()["run_id"] == "3"
    assert repo.latest_query_snapshot("a")["snapshot_id"] == "3"
    assert [
        v["judgment_id"]
        for v in repo.list_judgments(["a"], max_per_page=2, max_scan=3)["a"]
    ] == ["3", "2"]
