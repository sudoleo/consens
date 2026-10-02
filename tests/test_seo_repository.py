"""Real repository with shuffled SDK-shaped reads and bounded query doubles."""
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock
from app.services.seo_repository import FirestoreSeoRepository
from test_seo_data import FakeFirestore


def test_batch_get_binds_document_identity_and_dates_not_position_or_payload():
    db = FakeFirestore()
    start = date(2026, 1, 1)
    for i in range(205):
        day = (start + timedelta(days=i)).isoformat()
        db.documents[("seo_pages", "a", "daily_metrics", day)] = {
            "clicks": i,
            "page_id": "b",
            "date": "1999-01-01",
        }
        db.documents[("seo_pages", "b", "daily_metrics", day)] = {"clicks": 1000 + i}
    del db.documents[("seo_pages", "a", "daily_metrics", "2026-01-01")]
    original = db.get_all
    db.get_all = lambda refs: list(reversed(original(refs)))
    result = FirestoreSeoRepository(db).list_metrics_for_pages(
        ["a", "b", "a", "missing"], start, start + timedelta(days=204)
    )
    assert db.get_all_calls == [400, 215]
    assert (
        len(result["a"]) == 204 and len(result["b"]) == 205 and result["missing"] == []
    )
    assert result["a"][0] == {"clicks": 1, "page_id": "a", "date": "2026-01-02"}
    assert result["b"][-1] == {"clicks": 1204, "page_id": "b", "date": "2026-07-24"}
    assert FirestoreSeoRepository(db).list_metrics_for_pages([], start, start) == {}
    assert db.get_all_calls == [400, 215]


def test_latest_and_judgment_query_shapes_bound_reads_and_return_document_ids():
    old = datetime(2026, 1, 1, tzinfo=timezone.utc)
    newest = datetime(2026, 1, 3, tzinfo=timezone.utc)
    snapshots = [
        SimpleNamespace(
            id="latest", to_dict=lambda: {"started_at": newest, "finished_at": None}
        )
    ]
    query = Mock()
    query.order_by.return_value = query
    query.limit.return_value = query
    query.stream.side_effect = lambda: iter(snapshots)
    db = Mock()
    db.collection.return_value = query
    query.document.return_value = query
    query.collection.return_value = query
    repo = FirestoreSeoRepository(db)
    assert repo.last_run() == {
        "run_id": "latest",
        "started_at": newest.isoformat(),
        "finished_at": None,
    }
    query.order_by.assert_called_with("started_at", direction="DESCENDING")
    query.limit.assert_called_with(1)
    snapshots[:] = [
        SimpleNamespace(id="s", to_dict=lambda: {"period_end": "2026-01-03"})
    ]
    assert repo.latest_query_snapshot("page")["snapshot_id"] == "s"
    query.order_by.assert_called_with("period_end", direction="DESCENDING")
    snapshots[:] = [
        SimpleNamespace(
            id=str(i),
            to_dict=lambda i=i: {
                "page_id": "a" if i != 2 else "other",
                "created_at": newest if i else old,
            },
        )
        for i in range(4)
    ]
    result = repo.list_judgments(["a", "missing"], max_per_page=2, max_scan=7)
    query.order_by.assert_called_with("created_at", direction="DESCENDING")
    query.limit.assert_called_with(7)
    assert [v["judgment_id"] for v in result["a"]] == ["1", "3"]
    assert result["missing"] == []
    snapshots.clear()
    assert repo.last_run() is None and repo.latest_query_snapshot("a") is None


def test_fallback_dates_are_ordered_with_naive_aware_and_missing_values():
    db = FakeFirestore()
    for key, dt in (
        ("missing", None),
        ("naive", datetime(2026, 1, 2)),
        ("aware", datetime(2026, 1, 1, tzinfo=timezone.utc)),
    ):
        db.documents[("seo_collection_runs", key)] = {"started_at": dt}
        db.documents[("seo_judgements", key)] = {"created_at": dt, "page_id": "a"}
    repo = FirestoreSeoRepository(db)
    assert repo.last_run()["run_id"] == "naive"
    assert [v["judgment_id"] for v in repo.list_judgments(["a"])["a"]] == [
        "naive",
        "aware",
        "missing",
    ]
