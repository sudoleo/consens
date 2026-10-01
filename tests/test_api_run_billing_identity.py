"""R03/R05: every paid API run owns exactly one non-reusable usage receipt.

Uses the real API-run and usage repositories on one in-memory transactional
fake, so delete/recreate, retries and midnight crossings exercise the same
state transitions as production (without Firestore isolation semantics).
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import main
from app.api.routers import api_v1
from app.services import api_consensus_runner as runner
from app.services.api_run_repository import (
    API_IDEMPOTENCY_COLLECTION,
    API_RUNS_COLLECTION,
    ApiRunDeleted,
    ApiRunNotFound,
    FirestoreApiRunRepository,
    idempotency_hash,
)
from app.services.usage_repository import (
    MIN_EXECUTION_WINDOW,
    FirestoreUsageRepository,
    RunKind,
    RunStatus,
    TokenAdmission,
    UsageRunExpired,
    canonical_request_fingerprint,
)
from app.services import agent_budget_config
from test_api_run_repository import FakeDb


UID = "review"
LIMITS = TokenAdmission(tier="free", mode="consensus", limit=10_000_000, estimate=1_000,
                        period="2026-09-26", config=agent_budget_config.snapshot({}))
ARGS = dict(
    uid=UID,
    api_key_id="k" * 64,
    idempotency_key="same-key",
    request_payload={"question": "Same question", "deep_think": False},
    model_plan={"providers": {}, "consensus_model": "OpenAI"},
    tier="free",
)


@pytest.fixture
def env(monkeypatch):
    db = FakeDb()
    api = FirestoreApiRunRepository(db, transaction_runner=db.run_transaction)
    usage = FirestoreUsageRepository(db, transaction_runner=db.run_transaction)
    executions = []
    monkeypatch.setattr(runner, "api_run_repository", api)
    monkeypatch.setattr(runner, "usage_repository", usage)
    monkeypatch.setattr(runner, "api_account_cleanup", SimpleNamespace(ensure_active=lambda uid: None))
    monkeypatch.setattr(
        runner,
        "execute_consensus_pipeline",
        lambda run: executions.append(run["run_id"]) or {"consensus_response": "offline"},
    )
    monkeypatch.setattr(runner, "token_admission_for_run", lambda run: LIMITS)

    def runs():
        return [
            {**data, "run_id": path[1]}
            for path, data in list(db.documents.items())
            if len(path) == 2 and path[0] == API_RUNS_COLLECTION
        ]

    # The in-memory fake has no query API; scan the same documents instead.
    monkeypatch.setattr(api, "list_by_status", lambda statuses: [r for r in runs() if r.get("status") in statuses])
    monkeypatch.setattr(api, "list_expired", lambda now=None: [
        r for r in runs() if r["expires_at"] <= (now or datetime.now(timezone.utc))])
    return SimpleNamespace(db=db, api=api, usage=usage, executions=executions)


def complete_run(env, **overrides):
    run, created = env.api.create_or_get(**{**ARGS, **overrides})
    assert created
    runner.reserve_run(run)
    runner.execute_persisted_run(run["run_id"])
    assert env.api.get(run["run_id"])["status"] == "succeeded"
    return run


def usage_runs(env, status, utc_date=None):
    return sum(1 for path, data in env.db.documents.items()
               if path[:3] == ("users", UID, "usage_runs") and data.get("status") == status
               and (utc_date is None or data.get("utc_date") == utc_date))


def consumed(env):
    return usage_runs(env, RunStatus.CONSUMED.value)


def reserved(env):
    return usage_runs(env, RunStatus.RESERVED.value)


def test_deleted_run_cannot_start_paid_work_again_under_the_same_key(env):
    run = complete_run(env)
    assert env.api.delete_terminal_for_uid(run["run_id"], UID) is True

    with pytest.raises(ApiRunDeleted):
        env.api.create_or_get(**ARGS)
    with pytest.raises(ApiRunDeleted):
        env.api.get_by_idempotency(
            uid=UID, idempotency_key=ARGS["idempotency_key"],
            request_payload=ARGS["request_payload"],
        )

    assert env.executions == [run["run_id"]]
    assert consumed(env) == 1


def test_parallel_retries_after_deletion_never_start_a_pipeline(env):
    run = complete_run(env)
    env.api.delete_terminal_for_uid(run["run_id"], UID)

    def attempt(_):
        try:
            env.api.create_or_get(**ARGS)
        except ApiRunDeleted:
            return "deleted"
        return "created"

    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(attempt, range(8)))

    assert outcomes == ["deleted"] * 8
    assert env.executions == [run["run_id"]]
    assert consumed(env) == 1


def test_new_key_after_deletion_starts_exactly_one_newly_charged_run(env):
    first = complete_run(env)
    env.api.delete_terminal_for_uid(first["run_id"], UID)

    second = complete_run(env, idempotency_key="fresh-key")

    assert second["run_id"] != first["run_id"]
    assert env.executions == [first["run_id"], second["run_id"]]
    assert consumed(env) == 2


def test_retry_of_the_same_live_run_stays_idempotent(env):
    run, created = env.api.create_or_get(**ARGS)
    runner.reserve_run(run)
    again, created_again = env.api.create_or_get(**ARGS)
    runner.reserve_run(env.api.get(run["run_id"]))
    runner.execute_persisted_run(run["run_id"])
    runner.execute_persisted_run(run["run_id"])

    assert created and not created_again and again["run_id"] == run["run_id"]
    assert env.executions == [run["run_id"]]
    assert consumed(env) == 1


def test_deletion_removes_content_and_keeps_only_a_bounded_tombstone(env):
    run = complete_run(env)
    env.api.delete_terminal_for_uid(run["run_id"], UID)

    stored = env.db.documents[(API_RUNS_COLLECTION, run["run_id"])]
    assert stored["status"] == "deleted"
    for field in ("request", "model_plan", "result", "error", "request_hash"):
        assert field not in stored
    assert "Same question" not in repr(stored)
    assert stored["expires_at"] == run["expires_at"]
    with pytest.raises(ApiRunNotFound):
        env.api.get(run["run_id"])
    # A second delete is not a second success.
    assert env.api.delete_terminal_for_uid(run["run_id"], UID) is False

    # Retention removes tombstone and mapping at the original expiry.
    later = run["expires_at"] + timedelta(seconds=1)
    assert env.api.delete_expired(run["run_id"], now=later) is True
    mapping_path = ("users", UID, API_IDEMPOTENCY_COLLECTION, idempotency_hash("same-key"))
    assert mapping_path not in env.db.documents
    assert (API_RUNS_COLLECTION, run["run_id"]) not in env.db.documents


def test_legacy_runs_without_own_receipt_keep_their_historic_usage_key():
    legacy = {"uid": UID, "idempotency_hash": "b" * 64}
    assert runner.usage_key_for_run(legacy) == "consensus-api:" + "b" * 64
    assert runner.usage_key_for_run({**legacy, "usage_key": "consensus-api:run:" + "c" * 32}) == (
        "consensus-api:run:" + "c" * 32
    )


def test_route_returns_stable_410_for_a_deleted_key(env, monkeypatch):
    monkeypatch.setattr(api_v1, "api_run_repository", env.api)
    monkeypatch.setattr(api_v1, "api_key_repository", SimpleNamespace(
        authenticate=lambda key: SimpleNamespace(uid=UID, key_id="f" * 64, label="test")))
    monkeypatch.setattr(api_v1, "ensure_api_account_active", lambda uid: None)
    monkeypatch.setattr(api_v1, "enforce_uid_rate_limit", lambda *args: None)
    monkeypatch.setattr(api_v1, "get_user_tier", lambda uid: "free")
    monkeypatch.setattr(api_v1, "build_server_model_plan", lambda **kwargs: ARGS["model_plan"])
    monkeypatch.setattr(api_v1, "validate_server_credentials", lambda plan: None)
    scheduled = []
    monkeypatch.setattr(api_v1, "schedule_run", lambda run_id: scheduled.append(run_id) or True)
    client = TestClient(main.app)
    headers = {"X-API-Key": "cns_test", "Idempotency-Key": "same-key"}
    body = {"question": "Same question"}

    created = client.post("/api/v1/consensus/runs", headers=headers, json=body)
    assert created.status_code == 202
    run_id = created.json()["run_id"]
    runner.execute_persisted_run(run_id)
    assert client.delete(f"/api/v1/consensus/runs/{run_id}", headers=headers).status_code == 204

    replay = client.post("/api/v1/consensus/runs", headers=headers, json=body)
    assert replay.status_code == 410
    assert replay.json()["error"]["code"] == "run_deleted"
    assert client.get(f"/api/v1/consensus/runs/{run_id}", headers=headers).status_code == 404
    assert client.delete(f"/api/v1/consensus/runs/{run_id}", headers=headers).status_code == 404
    assert env.executions == [run_id]
    assert scheduled == [run_id]
    assert consumed(env) == 1


# --- R05: billing day and execution validity are separate -------------------


BEFORE_MIDNIGHT = datetime(2026, 9, 26, 23, 59, 59, tzinfo=timezone.utc)


def test_run_charged_before_midnight_finishes_after_midnight_without_second_charge(env):
    fingerprint = canonical_request_fingerprint({"question": "late"})
    first = env.usage.reserve(UID, "late", RunKind.REGULAR, LIMITS,
                              request_fingerprint=fingerprint, now=BEFORE_MIDNIGHT)
    # A retry two seconds later (next UTC day) is idempotent, not expired.
    retry = env.usage.reserve(UID, "late", RunKind.REGULAR, LIMITS,
                              request_fingerprint=fingerprint,
                              now=BEFORE_MIDNIGHT + timedelta(seconds=2))
    env.usage.consume(UID, "late")
    result, claim = env.usage.authorize_operation(
        UID, "late", RunKind.REGULAR, LIMITS, "consensus",
        canonical_request_fingerprint({"op": "consensus"}),
        request_fingerprint=fingerprint, now=BEFORE_MIDNIGHT + timedelta(minutes=10),
    )

    assert first.utc_date == retry.utc_date == result.utc_date == "2026-09-26"
    assert retry.idempotent and result.idempotent and not claim.idempotent
    assert usage_runs(env, "consumed", "2026-09-26") == 1
    assert usage_runs(env, "consumed", "2026-09-27") == 0
    # Its tokens book into the account period it was admitted in.
    env.usage.book_operation(UID, "late", "consensus", measured=500, estimated=0,
                             now=BEFORE_MIDNIGHT + timedelta(minutes=10))
    assert env.db.documents[("users", UID, "chat_state", "agent_tokens_2026-09-26")]["used"] == 500

    # A new run on the following day is admitted on that day.
    next_day = TokenAdmission(tier="free", mode="consensus", limit=10_000_000, estimate=1_000,
                              period="2026-09-27", config=LIMITS.config)
    env.usage.reserve(UID, "next", RunKind.REGULAR, next_day,
                      now=BEFORE_MIDNIGHT + timedelta(hours=1))
    assert usage_runs(env, "reserved", "2026-09-27") == 1


def test_execution_validity_stays_bounded(env):
    env.usage.reserve(UID, "late", RunKind.REGULAR, LIMITS, now=BEFORE_MIDNIGHT)
    env.usage.consume(UID, "late")
    with pytest.raises(UsageRunExpired):
        env.usage.claim_operation(
            UID, "late", "ask:openai", canonical_request_fingerprint({"a": 1}),
            now=BEFORE_MIDNIGHT + MIN_EXECUTION_WINDOW + timedelta(seconds=1),
        )
    # Midday reservations keep the whole remaining billing day.
    noon = datetime(2026, 9, 26, 12, tzinfo=timezone.utc)
    env.usage.reserve(UID, "noon", RunKind.REGULAR, LIMITS, now=noon)
    env.usage.consume(UID, "noon")
    env.usage.claim_operation(UID, "noon", "ask:openai",
                              canonical_request_fingerprint({"a": 1}),
                              now=datetime(2026, 9, 26, 23, 59, tzinfo=timezone.utc))
    with pytest.raises(UsageRunExpired):
        env.usage.claim_operation(UID, "noon", "ask:mistral",
                                  canonical_request_fingerprint({"a": 1}),
                                  now=datetime(2026, 9, 27, 0, 0, 1, tzinfo=timezone.utc))


def expire_usage_receipt(env, run):
    path = ("users", UID, "usage_runs", idempotency_hash(runner.usage_key_for_run(run)))
    env.db.documents[path]["expires_at"] = datetime.now(timezone.utc) - timedelta(seconds=1)
    return path


def test_crash_between_reserve_and_mark_reserved_is_terminalized_once(env, monkeypatch):
    run, _ = env.api.create_or_get(**ARGS)
    # Usage reservation committed, then the process died before mark_reserved.
    original_mark = env.api.mark_reserved
    monkeypatch.setattr(env.api, "mark_reserved", lambda run_id: (_ for _ in ()).throw(RuntimeError("crash")))
    with pytest.raises(RuntimeError):
        runner.reserve_run(run)
    monkeypatch.setattr(env.api, "mark_reserved", original_mark)
    assert reserved(env) == 1
    usage_path = expire_usage_receipt(env, run)
    monkeypatch.setattr(runner, "mock_llm_enabled", lambda: False)
    monkeypatch.setattr(runner, "_retention_backfilled", True)
    monkeypatch.setattr(runner, "schedule_run", lambda run_id: pytest.fail("must not schedule"))

    assert runner.recover_persisted_runs() == 0
    failed = env.api.get(run["run_id"])
    assert failed["status"] == "failed"
    assert failed["error"]["code"] == "reservation_expired"
    assert env.db.documents[usage_path]["status"] == RunStatus.RELEASED.value
    assert reserved(env) == 0
    assert env.executions == []
    # Nothing is left for later recovery passes to retry forever.
    assert env.api.list_by_status(("accepted",)) == []
    assert runner.recover_persisted_runs() == 0


def test_route_terminalizes_an_accepted_run_whose_reservation_expired(env, monkeypatch):
    run, _ = env.api.create_or_get(**ARGS)
    env.usage.reserve(UID, runner.usage_key_for_run(run), RunKind.REGULAR, LIMITS,
                      request_fingerprint=canonical_request_fingerprint({
                          "schema": 1, "request": run["request"], "model_plan": run["model_plan"]}))
    expire_usage_receipt(env, run)
    monkeypatch.setattr(api_v1, "api_run_repository", env.api)
    monkeypatch.setattr(api_v1, "api_key_repository", SimpleNamespace(
        authenticate=lambda key: SimpleNamespace(uid=UID, key_id="f" * 64, label="test")))
    monkeypatch.setattr(api_v1, "ensure_api_account_active", lambda uid: None)
    monkeypatch.setattr(api_v1, "enforce_uid_rate_limit", lambda *args: None)
    monkeypatch.setattr(api_v1, "validate_server_credentials", lambda plan: None)
    monkeypatch.setattr(api_v1, "schedule_run", lambda run_id: pytest.fail("must not schedule"))
    client = TestClient(main.app)

    response = client.post(
        "/api/v1/consensus/runs",
        headers={"X-API-Key": "cns_test", "Idempotency-Key": "same-key"},
        json={"question": "Same question"},
    )

    assert response.status_code == 202
    assert response.json()["status"] == "failed"
    assert response.json()["error"]["code"] == "reservation_expired"
    assert reserved(env) == 0
    assert env.executions == []
