"""The admin's start page: the Agent's answers per day, one read per day."""
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routers import admin as admin_router
from app.core.rate_limit import limiter
from app.services import agent_audit_metrics as metrics


class FakeDb:
    def __init__(self, documents):
        self.documents = documents
        self.reads = []

    def collection(self, name):
        assert name == "ops_metrics"
        return SimpleNamespace(document=lambda doc_id: SimpleNamespace(id=doc_id))

    def get_all(self, refs):
        refs = list(refs)
        self.reads.extend(ref.id for ref in refs)
        for ref in refs:
            data = self.documents.get(ref.id)
            yield SimpleNamespace(id=ref.id, exists=data is not None, to_dict=lambda data=data: data)


def test_the_last_two_weeks_come_oldest_first_with_empty_days():
    db = FakeDb({
        "agent-audit-2026-11-11": {"turns": {"completed": 3, "failed": 1}, "total_s": {"le45": 4}},
        "agent-audit-2026-10-29": {"turns": {"completed": 19, "cancelled": 1}},
        # A counter that is not a number is not a turn.
        "agent-audit-2026-11-01": {"turns": {"completed": 2, "odd": "x", "flag": True}},
    })
    days = metrics.recent_days(db, today=date(2026, 11, 11))

    assert [day["day"] for day in (days[0], days[-1])] == ["2026-10-29", "2026-11-11"]
    assert len(days) == 14 and len(db.reads) == 14
    assert days[0]["turns"] == {"completed": 19, "cancelled": 1}
    assert days[-1]["turns"] == {"completed": 3, "failed": 1}
    assert days[3]["turns"] == {"completed": 2}
    assert days[1]["turns"] == {}


@pytest.fixture
def client():
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(admin_router.router)
    limiter.enabled = False
    try:
        yield TestClient(app)
    finally:
        limiter.enabled = True


def test_only_an_admin_sees_the_overview(client):
    with patch.object(admin_router, "extract_id_token", return_value="token"), \
         patch.object(admin_router, "verify_user_token", return_value="uid-1"), \
         patch.object(admin_router, "is_user_admin", return_value=False), \
         patch.object(metrics, "recent_days") as recent:
        response = client.get("/api/admin/overview", headers={"Authorization": "Bearer token"})
    assert response.status_code == 403
    recent.assert_not_called()


def test_the_overview_answers_with_the_days_or_says_it_could_not(client):
    days = [{"day": "2026-11-11", "turns": {"completed": 1}}]
    admin = (patch.object(admin_router, "extract_id_token", return_value="token"),
             patch.object(admin_router, "verify_user_token", return_value="admin-uid"),
             patch.object(admin_router, "is_user_admin", return_value=True))
    with admin[0], admin[1], admin[2], patch.object(metrics, "recent_days", return_value=days):
        assert client.get("/api/admin/overview").json() == {"agent_days": days}
    with admin[0], admin[1], admin[2], patch.object(metrics, "recent_days", side_effect=RuntimeError("db down")):
        response = client.get("/api/admin/overview")
    assert response.status_code == 503
    assert "db down" not in response.text
