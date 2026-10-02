"""Actual feedback HTTP handler and privacy-preserving stats persistence."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock
import json
import pytest
from app.api.routers import pages
from app.services import persistence_guard as guard, differences_stats
from app.core.rate_limit import limiter
from adapter_test_support import http_adapter, login
from test_phase5_operations import Database as FakeDb
from test_differences_stats import make_differences_data


@pytest.fixture
def feedback(http_adapter, monkeypatch):
    h = http_adapter
    h.feedback_db = FakeDb()
    monkeypatch.setattr(pages, "db_firestore", h.feedback_db)
    return h


def test_feedback_auth_payload_and_persisted_cooldown(feedback):
    h = feedback
    payload = {
        "message": "  Deliberately supplied private feedback  ",
        "email": "Me@Example.test",
    }
    for identity in (None, "invalid"):
        response = h.client.post(
            "/feedback", json=payload, headers=login(identity) if identity else {}
        )
        assert response.status_code == 401
    assert h.feedback_db.data == {}
    response = h.client.post("/feedback", json=payload, headers=login("owner"))
    assert response.status_code == 200, response.text
    saved = [v for p, v in h.feedback_db.data.items() if p[0] == "feedback"]
    assert len(saved) == 1
    assert set(saved[0]) == {"uid", "email", "message", "timestamp"}
    assert saved[0]["uid"] == "owner" and saved[0]["email"] == "me@example.test"
    assert saved[0]["message"] == payload["message"].strip()
    limiter.reset()  # Persistent UID cooldown must also work after process-local limiter reset.
    before = deepcopy(h.feedback_db.data)
    response = h.client.post("/feedback", json=payload, headers=login("owner"))
    assert response.status_code == 429 and "wait" in response.json()["error"].lower()
    assert h.feedback_db.data == before
    assert (
        h.client.post("/feedback", json=payload, headers=login("other")).status_code
        == 200
    )


def test_feedback_daily_limit_and_storage_failure_are_safe(feedback, monkeypatch):
    h = feedback
    now = datetime.now(timezone.utc)
    ref = h.feedback_db.collection(guard.USAGE_COLLECTION).document(
        guard._owner_key("feedback", "owner")
    )
    ref.set(
        {
            "day": now.date().isoformat(),
            "day_count": guard.MAX_FEEDBACK_PER_UTC_DAY,
            "last_submitted_at": now - timedelta(minutes=1),
        }
    )
    before = deepcopy(h.feedback_db.data)
    response = h.client.post(
        "/feedback", json={"message": "private"}, headers=login("owner")
    )
    assert response.status_code == 429 and "Daily" in response.json()["error"]
    assert h.feedback_db.data == before
    monkeypatch.setattr(
        h.feedback_db,
        "run_transaction",
        Mock(side_effect=RuntimeError("SECRET database write")),
    )
    response = h.client.post(
        "/feedback", json={"message": "private"}, headers=login("other")
    )
    assert response.status_code == 500 and "SECRET" not in response.text
    assert h.feedback_db.data == before


@pytest.mark.parametrize(
    "payload",
    [
        {"message": "   "},
        {"message": "x" * 4001},
        {"message": "ok", "uid": "forged"},
        {"message": "ok", "email": "bad"},
    ],
)
def test_feedback_rejects_invalid_fields_before_storage(feedback, payload):
    h = feedback
    assert (
        h.client.post("/feedback", json=payload, headers=login("owner")).status_code
        == 422
    )
    assert h.feedback_db.data == {}


def test_stats_wrapper_persists_only_counts_and_safe_model_metadata():
    db = FakeDb()
    data = make_differences_data()
    data.update(
        question="PRIVATE_QUESTION",
        answer="PRIVATE_ANSWER",
        uid="PRIVATE_UID",
        run_id="PRIVATE_RUN",
    )
    record_id = differences_stats.record_differences_stats(
        data, db=db, question_word_count=17, consensus_model="OpenAI"
    )
    saved = db.data[(differences_stats.DIFFERENCES_STATS_COLLECTION, record_id)]
    serialized = json.dumps(saved, default=str)
    assert all(
        marker not in serialized
        for marker in (
            "PRIVATE_",
            "The sky is blue",
            "Water boils",
            "Disagreement about",
            "depends on",
            "Check a physics",
        )
    )
    assert saved["model_count"] == 4 and saved["question_word_count"] == 17
    assert saved["agreement"]["major_contradictions"] == 1
    assert saved["claims"] == [{"agree": 3, "dissent": 1}, {"agree": 2, "dissent": 0}]
    assert "created_at" in saved


def test_stats_failure_never_aborts_answer_or_logs_content(caplog):
    db = Mock()
    db.collection.side_effect = RuntimeError("SECRET prompt")
    assert (
        differences_stats.record_differences_stats(make_differences_data(), db=db)
        is None
    )
    assert "SECRET" not in caplog.text
