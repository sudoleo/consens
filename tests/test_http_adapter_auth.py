"""Real main.app policies with SDK auth and database boundary doubles."""
from types import SimpleNamespace
from unittest.mock import Mock
import firebase_admin
import pytest
from app.api.routers import users, auth as auth_router
from app.services import topics, registration, benchmark_reports
from app.services.usage_repository import FirestoreUsageRepository
from adapter_test_support import http_adapter, login
from test_topics_feature import FakeFirestore, topic_payload, run_payload
from test_benchmark_reports import FakeCollection, _write_finished_run
from benchmark import report_reader


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/admin/topics"),
        ("POST", "/api/admin/topics"),
        ("GET", "/api/admin/topics/unknown"),
        ("PUT", "/api/admin/topics/unknown"),
        ("POST", "/api/admin/topics/unknown/runs"),
    ],
)
@pytest.mark.parametrize(
    "identity,expected",
    [(None, 401), ("invalid", 401), ("revoked", 401), ("reader", 403), ("outage", 503)],
)
def test_every_topic_admin_method_enforces_real_policy_before_service(
    http_adapter, monkeypatch, method, path, identity, expected
):
    h = http_adapter
    h.db.collection("users").document("revoked").set({"role": "admin"})
    h.flags["outage"] = identity == "outage"
    database = FakeFirestore()
    monkeypatch.setattr(topics, "db_firestore", database)
    response = h.client.request(
        method,
        path,
        headers=login(identity) if identity else {},
        json=topic_payload() if method in {"POST", "PUT"} else None,
    )
    assert response.status_code == expected, response.text
    assert "error" in response.json() and "private" not in response.text
    assert database.documents == {} and database.query_reads == []
    if identity not in {None, "invalid"}:
        assert h.checks[-1][1]["check_revoked"] is True


def test_real_topic_admin_put_list_and_version_have_persisted_results(
    http_adapter, monkeypatch
):
    h = http_adapter
    h.db.collection("users").document("admin").set({"role": "admin", "tier": "free"})
    db = FakeFirestore()
    monkeypatch.setattr(topics, "db_firestore", db)
    created = h.client.post(
        "/api/admin/topics", headers=login("admin"), json=topic_payload()
    )
    assert created.status_code == 200, created.text
    topic_id = created.json()["topic"]["id"]
    changed = h.client.put(
        "/api/admin/topics/" + topic_id,
        headers=login("admin"),
        json=topic_payload(title="Changed by admin"),
    )
    assert changed.status_code == 200, changed.text
    assert topics.get_topic(topic_id, db=db)["title"] == "Changed by admin"
    published = h.client.post(
        f"/api/admin/topics/{topic_id}/runs", headers=login("admin"), json=run_payload()
    )
    assert published.status_code == 200, published.text
    listed = h.client.get("/api/admin/topics", headers=login("admin"))
    assert listed.json()["topics"][0]["id"] == topic_id
    detail = h.client.get(f"/api/admin/topics/{topic_id}", headers=login("admin"))
    assert detail.json()["runs"][0]["version"] == 1
    assert all(kwargs["check_revoked"] for _, kwargs in h.checks)
    assert {path[0] for path in db.documents}.isdisjoint({"shares", "watches"})


@pytest.mark.parametrize(
    "tier,role,is_pro,agent,resolve",
    [
        ("free", "", False, True, False),
        ("plus", "", False, True, True),
        ("pro", "", True, True, True),
        ("free", "admin", False, True, False),
    ],
)
def test_user_status_uses_real_tier_and_role_payload(
    http_adapter, monkeypatch, tier, role, is_pro, agent, resolve
):
    h = http_adapter
    h.db.collection("users").document("owner").set({"tier": tier, "role": role})
    monkeypatch.setattr(users, "run_usage_repository", FirestoreUsageRepository(h.db))
    response = h.client.get("/user_status", headers=login("owner"))
    assert response.status_code == 200, response.text
    data = response.json()
    assert (
        data["tier"],
        data["is_pro"],
        data["agent_access"],
        data["attachments"],
        data["resolve"],
    ) == (tier, is_pro, agent, True, resolve)  # attachments: every tier since 2026-10-02
    assert data["uid"] == "owner" and data["token_budget"]["used"] == 0
    # The browser leaves analytics for operators (analytics-opt-out.js excludeOperator).
    assert data["is_admin"] is (role == "admin")


@pytest.mark.parametrize(
    "identity,expected", [(None, 401), ("invalid", 401), ("owner", 503)]
)
def test_user_status_rejects_auth_and_tier_outage(http_adapter, identity, expected):
    h = http_adapter
    h.flags["outage"] = True
    response = h.client.get("/user_status", headers=login(identity) if identity else {})
    assert response.status_code == expected
    assert "private" not in response.text


def test_a_structured_refusal_reaches_the_app_flat(http_adapter):
    # Zweitprüfung 2: {"error": {"error_code", "message"}} hid the sentence
    # and the code from every client reader; the app gets {error, code, ...}.
    h = http_adapter
    response = h.client.post("/api/my/memory/changes/not-an-id/undo", headers=login("owner"))
    assert response.status_code == 404
    body = response.json()
    assert body == {"error": "This memory change is no longer available.",
                    "code": "not_found", "error_code": "not_found"}


def test_the_flat_shape_keeps_every_field_and_spares_the_public_api():
    import main

    detail = {"error": "Today’s allowance doesn’t cover another run. It resets at 00:00 UTC.",
              "error_code": "token_budget_exhausted", "required_tokens": 900,
              "token_budget": {"used": 10}, "tier": "free"}
    assert main.error_body("/consensus", detail) == {
        "error": detail["error"], "code": "token_budget_exhausted", "error_code": "token_budget_exhausted",
        "required_tokens": 900, "token_budget": {"used": 10}, "tier": "free"}
    conflict = {"error_code": "revision_conflict", "message": "Memory changed.", "revision": 7}
    assert main.error_body("/api/my/memory", conflict)["revision"] == 7
    # A sentence alone, or extra fields (watch errors), stay as they were.
    assert main.error_body("/api/watches", "Watch not found.", {"code": "not_found"}) == {
        "error": "Watch not found.", "code": "not_found"}
    # The documented public API shape does not move.
    scoped = {"code": "insufficient_scope", "message": "API key requires scope: run:create"}
    assert main.error_body("/api/v1/runs", scoped) == {"error": scoped}
    # A throttle is "rate_limited" with its wait, unless it names itself.
    assert main.error_body("/agent", "Too many agent requests. Please wait.", status=429,
                           headers={"Retry-After": "30"}) == {
        "error": "Too many agent requests. Please wait.", "code": "rate_limited", "retry_after": 30}
    chats = {"error": "Too many chat requests. Please slow down.", "error_code": "chat_rate_limited"}
    assert main.error_body("/api/chats", chats, status=429)["code"] == "chat_rate_limited"


@pytest.mark.parametrize("method,path", [("GET", "/user_status"), ("POST", "/usage")])
def test_an_account_check_outage_is_no_rejected_login(http_adapter, monkeypatch, method, path):
    # Zweitprüfung 12: the deletion check could not be read. A 401 made the
    # browser turn Agent off for the session; a 503 makes it ask again.
    from app.core import security

    h = http_adapter
    collection = h.db.collection

    def unavailable(name):
        if name == security.ACCOUNT_DELETION_JOBS_COLLECTION:
            raise RuntimeError("private database diagnostic")
        return collection(name)

    monkeypatch.setattr(h.db, "collection", unavailable)
    response = h.client.request(
        method, path, headers=login("owner"),
        json={"id_token": "owner"} if method == "POST" else None,
    )
    assert response.status_code == 503, response.text
    assert response.headers["Retry-After"] == "5"
    assert "private" not in response.text


def test_registration_create_race_has_same_public_response_and_no_duplicate_notification(
    http_adapter, monkeypatch
):
    h = http_adapter
    monkeypatch.setenv("FIREBASE_API_KEY", "test-key")
    user = SimpleNamespace(uid="new-owner")
    lookup = Mock(
        side_effect=[
            firebase_admin.auth.UserNotFoundError("missing"),
            user,
            firebase_admin.auth.UserNotFoundError("missing"),
            user,
        ]
    )
    create = Mock(
        side_effect=[
            user,
            firebase_admin.auth.EmailAlreadyExistsError("race", None, None),
        ]
    )
    monkeypatch.setattr(registration.auth, "get_user_by_email", lookup)
    monkeypatch.setattr(registration.auth, "create_user", create)
    deliver = Mock()
    notify = Mock()
    monkeypatch.setattr(auth_router, "deliver_password_setup_email", deliver)
    monkeypatch.setattr(auth_router, "send_new_user_registration_notification", notify)
    responses = [
        h.client.post("/register", json={"email": "same@example.test"})
        for _ in range(3)
    ]
    assert [r.status_code for r in responses] == [200] * 3
    assert [r.json() for r in responses] == [{"status": "check_inbox"}] * 3
    assert create.call_count == 2 and deliver.call_count == 3
    notify.assert_called_once_with("email/password", "new-owner")


@pytest.mark.parametrize(
    "identity,expected", [(None, 401), ("reader", 403), ("revoked", 401)]
)
def test_benchmark_admin_denies_before_read(
    http_adapter, monkeypatch, identity, expected
):
    h = http_adapter
    h.db.collection("users").document("revoked").set({"role": "admin"})
    read = Mock(side_effect=AssertionError("must not read"))
    monkeypatch.setattr(benchmark_reports, "_collection", read)
    for path in ("/api/admin/benchmark/runs", "/api/admin/benchmark/runs/run"):
        response = h.client.get(path, headers=login(identity) if identity else {})
        assert response.status_code == expected
    read.assert_not_called()


def test_benchmark_admin_reads_compact_report_and_handles_missing_ids(
    http_adapter, monkeypatch, tmp_path
):
    h = http_adapter
    h.db.collection("users").document("admin").set({"role": "admin"})
    fake = FakeCollection()
    monkeypatch.setattr(benchmark_reports, "_collection", lambda: fake)
    monkeypatch.setattr(report_reader, "RUNS_DIR", tmp_path)
    benchmark_reports.publish_run_dir(_write_finished_run(tmp_path, "pilot_v1"))
    listing = h.client.get("/api/admin/benchmark/runs", headers=login("admin"))
    detail = h.client.get("/api/admin/benchmark/runs/pilot_v1", headers=login("admin"))
    assert listing.status_code == detail.status_code == 200
    assert listing.json()["runs"][0]["run_id"] == "pilot_v1"
    assert "SECRET_RAW" not in listing.text + detail.text
    assert "questions" in detail.json()["run"]
    for identifier in ("missing", "..bad"):
        response = h.client.get(
            "/api/admin/benchmark/runs/" + identifier, headers=login("admin")
        )
        assert response.status_code == 404, response.text
