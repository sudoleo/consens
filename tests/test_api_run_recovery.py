"""Restart orchestration uses the real run, quota and account repositories."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from app.services import api_consensus_runner as runner
from app.services.api_run_repository import (
    FirestoreApiRunRepository,
    ApiRunNotFound,
    API_RUNS_COLLECTION,
)
from app.services.api_account_cleanup import FirestoreApiAccountCleanup
from app.services.usage_repository import FirestoreUsageRepository, RunStatus
from app.services.llm import provider_transport
from adapter_test_support import http_adapter
from test_chat_history import FakeCollectionRef, FakeQuery


class RecoveryQuery(FakeQuery):
    def _matches_filters(self, snapshot):
        remaining = []
        for condition in self.filters:
            if condition.op_string == "in":
                if snapshot.to_dict().get(condition.field_path) not in condition.value:
                    return False
            else:
                remaining.append(condition)
        return FakeQuery(self.collection, [], filters=remaining)._matches_filters(
            snapshot
        )


class RecoveryCollection(FakeCollectionRef):
    def where(self, filter=None):
        return RecoveryQuery(self, [], filters=[filter])


@pytest.fixture
def recovery(http_adapter, monkeypatch):
    h = http_adapter
    original = h.db.collection
    monkeypatch.setattr(
        h.db,
        "collection",
        lambda name: RecoveryCollection(h.db, (name,))
        if name == API_RUNS_COLLECTION
        else original(name),
    )
    h.runs = FirestoreApiRunRepository(h.db, transaction_runner=h.db.run_transaction)
    h.usage = FirestoreUsageRepository(h.db, transaction_runner=h.db.run_transaction)
    monkeypatch.setattr(runner, "api_run_repository", h.runs)
    monkeypatch.setattr(runner, "usage_repository", h.usage)
    monkeypatch.setattr(runner, "api_account_cleanup", FirestoreApiAccountCleanup(h.db))
    from app.core import security

    monkeypatch.setattr(
        security.auth,
        "get_user",
        lambda uid: SimpleNamespace(uid=uid, disabled=False, email_verified=True),
    )
    monkeypatch.setattr(runner, "_retention_backfilled", False)
    monkeypatch.setattr(runner, "_scheduled_run_ids", set())
    h.tasks = []
    monkeypatch.setattr(
        runner,
        "_background_executor",
        SimpleNamespace(submit=lambda fn, *args: h.tasks.append((fn, args))),
    )
    monkeypatch.delenv("MOCK_LLM", raising=False)
    h.provider = Mock(return_value="An offline answer")
    monkeypatch.setattr(provider_transport, "query_model", h.provider)
    monkeypatch.setattr(
        runner, "query_consensus", lambda *a, **kw: "Combined offline answer"
    )
    monkeypatch.setattr(
        runner,
        "query_differences",
        lambda *a, **kw: (
            "",
            {"claims": [], "differences": [], "models_compared": ["OpenAI", "Gemini"]},
        ),
    )
    return h


def create(h, key):
    return h.runs.create_or_get(
        uid="owner",
        api_key_id="a" * 64,
        idempotency_key=key,
        request_payload={
            "question": "Independent question " + key,
            "deep_think": False,
        },
        model_plan={
            "providers": {"openai": "gpt-5.4-mini", "gemini": "gemini-3.5-flash-lite"},
            "consensus_model": "OpenAI",
        },
        tier="free",
    )[0]


def test_restart_requeues_only_pre_provider_work_and_deduplicates_schedule(recovery):
    h = recovery
    accepted = create(h, "accepted")
    reserved = create(h, "reserved")
    live = create(h, "live")
    stale = create(h, "stale")
    for run in (reserved, live, stale):
        runner.reserve_run(run)
    for run in (live, stale):
        h.runs.claim_running(run["run_id"], "lost-process")
    h.usage.consume("owner", runner.usage_key_for_run(stale))
    h.db.documents[(API_RUNS_COLLECTION, stale["run_id"])][
        "lease_expires_at"
    ] = datetime.now(timezone.utc) - timedelta(seconds=1)
    assert runner.recover_persisted_runs() == 2
    assert (
        runner.recover_persisted_runs() == 2
    )  # queue acknowledgement, still one task per run
    assert len(h.tasks) == 2
    assert {args[0] for _, args in h.tasks} == {accepted["run_id"], reserved["run_id"]}
    assert h.runs.get(live["run_id"])["status"] == "running"
    assert h.runs.get(stale["run_id"])["error"]["code"] == "worker_interrupted"
    assert (
        h.usage.get_run("owner", runner.usage_key_for_run(stale)).status
        is RunStatus.CONSUMED
    )
    assert h.provider.call_count == 0
    for fn, args in h.tasks:
        fn(*args)
    assert h.provider.call_count == 4
    for run in (accepted, reserved):
        stored = h.runs.get(run["run_id"])
        assert (
            stored["status"] == "succeeded"
            and stored["result"]["consensus_response"] == "Combined offline answer"
        )
        runner.execute_persisted_run(run["run_id"])
        assert (
            h.usage.get_run("owner", runner.usage_key_for_run(run)).status
            is RunStatus.CONSUMED
        )
    assert h.provider.call_count == 4 and not runner._scheduled_run_ids


def test_retention_rechecks_expiry_and_preserves_rebound_idempotency(recovery):
    h = recovery
    expired = create(h, "expired")
    fresh = create(h, "fresh")
    runner.reserve_run(expired)
    h.db.documents[(API_RUNS_COLLECTION, expired["run_id"])][
        "expires_at"
    ] = datetime.now(timezone.utc) - timedelta(seconds=1)
    mapping = h.runs._idempotency_ref("owner", expired["idempotency_hash"])
    mapping.update({"run_id": fresh["run_id"]})
    before = deepcopy(mapping.get().to_dict())
    assert runner.cleanup_expired_runs() == 1
    with pytest.raises(ApiRunNotFound):
        h.runs.get(expired["run_id"])
    assert (
        h.usage.get_run("owner", runner.usage_key_for_run(expired)).status
        is RunStatus.RELEASED
    )
    assert mapping.get().to_dict() == before
    assert h.runs.get(fresh["run_id"])["status"] == "accepted"
    assert not h.runs.delete_expired(fresh["run_id"])
    assert runner.cleanup_expired_runs() == 0
    h.provider.assert_not_called()


def test_backfill_preserves_existing_expiry_and_rebound_mapping(recovery):
    h = recovery
    legacy = create(h, "legacy")
    existing = create(h, "existing")
    missing = create(h, "missing-date")
    stamp = datetime.now(timezone.utc) - timedelta(days=2)
    document = h.db.documents[(API_RUNS_COLLECTION, legacy["run_id"])]
    document.pop("expires_at")
    document["accepted_at"] = stamp
    bad = h.db.documents[(API_RUNS_COLLECTION, missing["run_id"])]
    bad.pop("expires_at")
    bad.pop("accepted_at")
    bad.pop("created_at", None)
    mapping = h.runs._idempotency_ref("owner", legacy["idempotency_hash"])
    mapping.update({"run_id": existing["run_id"]})
    before = deepcopy(mapping.get().to_dict())
    existing_before = h.runs.get(existing["run_id"])
    assert h.runs.backfill_retention() == 1
    assert h.runs.get(legacy["run_id"])["expires_at"] == stamp + timedelta(days=30)
    assert mapping.get().to_dict() == before
    assert h.runs.get(existing["run_id"]) == existing_before
    assert "expires_at" not in h.runs.get(missing["run_id"])
    assert h.runs.backfill_retention() == 0


def test_recovery_backfill_failure_is_retryable_and_queue_submission_unwinds(
    recovery, monkeypatch
):
    h = recovery
    original = h.db.collection
    failures = [True]

    def unavailable(name):
        if name == API_RUNS_COLLECTION and failures and failures.pop():
            raise RuntimeError("offline")
        return original(name)

    monkeypatch.setattr(h.db, "collection", unavailable)
    with pytest.raises(RuntimeError):
        runner.recover_persisted_runs()
    assert runner._retention_backfilled is False
    assert runner.recover_persisted_runs() == 0 and runner._retention_backfilled
    monkeypatch.setattr(
        runner,
        "_background_executor",
        SimpleNamespace(submit=Mock(side_effect=RuntimeError("closed executor"))),
    )
    with pytest.raises(RuntimeError):
        runner.schedule_run("run")
    assert "run" not in runner._scheduled_run_ids
