import asyncio

import pytest

import main
from app.core import background_tasks
from app.services import retention_maintenance


def setup_function():
    background_tasks.reset_task_health()


def test_supervisor_restarts_crashes_and_keeps_last_success_health():
    async def exercise():
        attempts = 0
        keep_running = asyncio.Event()

        async def worker():
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise RuntimeError("transient failure")
            background_tasks.task_succeeded("test-worker", work=1)
            await keep_running.wait()

        task = asyncio.create_task(
            background_tasks.supervise_background_task(
                "test-worker",
                worker,
                initial_backoff_seconds=0.01,
                max_backoff_seconds=0.01,
            )
        )
        for _ in range(100):
            state = background_tasks.task_health_snapshot().get("test-worker", {})
            if state.get("last_success_at"):
                break
            await asyncio.sleep(0.01)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        return attempts, background_tasks.task_health_snapshot()["test-worker"]

    attempts, health = asyncio.run(exercise())
    assert attempts == 3
    assert health["restart_count"] == 2
    assert health["consecutive_failures"] == 0
    assert health["last_success_at"]
    assert health["state"] == "stopped"


def test_supervisor_alerts_after_repeated_failure():
    async def exercise():
        alerts = []

        async def worker():
            raise OSError("firestore unavailable")

        task = asyncio.create_task(
            background_tasks.supervise_background_task(
                "failing-worker",
                worker,
                alert=alerts.append,
                alert_after_failures=3,
                initial_backoff_seconds=0.01,
                max_backoff_seconds=0.01,
            )
        )
        for _ in range(100):
            if alerts:
                break
            await asyncio.sleep(0.01)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        return alerts

    alerts = asyncio.run(exercise())
    assert len(alerts) == 1
    assert alerts[0]["type"] == "background_task_repeated_failure"
    assert "failing-worker" in alerts[0]["message"]


def test_failed_one_shot_task_alerts_immediately():
    alerts = []

    async def exercise():
        async def worker():
            raise RuntimeError("startup maintenance failed")

        await background_tasks.supervise_background_task(
            "one-shot",
            worker,
            restart=False,
            alert=alerts.append,
        )

    asyncio.run(exercise())
    assert len(alerts) == 1
    assert background_tasks.task_health_snapshot()["one-shot"]["state"] == "failed"


def test_retention_loop_runs_cleanup_before_first_sleep(monkeypatch):
    calls = []
    monkeypatch.setattr(
        retention_maintenance,
        "cleanup_expired_pending",
        lambda: calls.append("pending") or 2,
    )
    monkeypatch.setattr(
        retention_maintenance,
        "cleanup_revoked_shares",
        lambda: calls.append("shares") or 3,
    )
    from app.services import answer_receipts
    monkeypatch.setattr(answer_receipts, "cleanup_expired", lambda: calls.append("receipts") or 5)

    from app.services import source_check_jobs
    from types import SimpleNamespace
    monkeypatch.setattr(source_check_jobs, "repository",
        lambda: SimpleNamespace(cleanup=lambda: calls.append("sources") or 4))

    from app.services import chat_store, memory_edit
    monkeypatch.setattr(chat_store, "resume_chat_deletions",
        lambda: calls.append("chat_deletions") or 5)
    monkeypatch.setattr(memory_edit, "cleanup_memory_edit_records",
        lambda: calls.append("memory") or {"snapshots_purged": 6, "edits_recovered": 7})
    from app.services import agent_memory
    monkeypatch.setattr(agent_memory, "cleanup_memory_change_logs",
        lambda: calls.append("memory_changes") or 9)
    from app.services import notification_outbox
    monkeypatch.setattr(notification_outbox, "cleanup",
        lambda: calls.append("outbox") or 8)

    async def stop_after_first_tick(seconds):
        raise asyncio.CancelledError

    monkeypatch.setattr(retention_maintenance.asyncio, "sleep", stop_after_first_tick)

    async def exercise():
        try:
            await retention_maintenance.retention_maintenance_loop()
        except asyncio.CancelledError:
            pass

    asyncio.run(exercise())
    assert calls == ["pending", "receipts", "shares", "sources", "chat_deletions", "memory", "memory_changes", "outbox"]
    health = background_tasks.task_health_snapshot()["retention-maintenance"]
    assert health["details"] == {
        "expired_pending_deleted": 2,
        "expired_answer_receipts_deleted": 5,
        "revoked_shares_deleted": 3,
        "source_checks_deleted": 4,
        "files_deleted": 0,
        "documents_deleted": 0,
        "google_records_deleted": 0,
        "chat_deletions_completed": 5,
        "memory_undo_snapshots_purged": 6,
        "memory_edits_recovered": 7,
        "memory_change_logs": 9,
        "notification_outbox_deleted": 8,
    }


def test_scheduler_task_does_not_start_loop_under_mock_llm(monkeypatch):
    calls = []

    async def loop():
        calls.append("ran")

    monkeypatch.setattr(main, "mock_llm_enabled", lambda: True)

    async def exercise():
        await main._scheduler_task(loop, "retention-maintenance")

    asyncio.run(exercise())
    assert calls == []
    health = background_tasks.task_health_snapshot()["retention-maintenance"]
    assert health["state"] == "disabled"


def test_scheduler_task_runs_loop_without_mock_llm(monkeypatch):
    calls = []

    async def loop():
        calls.append("ran")

    monkeypatch.setattr(main, "mock_llm_enabled", lambda: False)
    monkeypatch.setattr(main, "_is_production", lambda: True)

    async def exercise():
        task = main._scheduler_task(loop, "retention-maintenance")
        for _ in range(100):
            if calls:
                break
            await asyncio.sleep(0.01)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    asyncio.run(exercise())
    assert calls == ["ran"]


@pytest.mark.parametrize(("production", "opt_in", "runs"), [
    (True, None, True),
    (False, None, False),
    (False, "1", True),
])
def test_scheduler_task_runs_locally_only_on_explicit_opt_in(monkeypatch, production, opt_in, runs):
    """A local server shares the production Firestore; its background writers
    polled it in parallel to the deployment (reads) and raced it for slots."""
    calls = []

    async def loop():
        calls.append("ran")

    monkeypatch.setattr(main, "mock_llm_enabled", lambda: False)
    monkeypatch.setattr(main, "_is_production", lambda: production)
    if opt_in is None:
        monkeypatch.delenv("LOCAL_BACKGROUND_JOBS", raising=False)
    else:
        monkeypatch.setenv("LOCAL_BACKGROUND_JOBS", opt_in)

    async def exercise():
        task = main._scheduler_task(loop, "topic-scheduler")
        for _ in range(50):
            if calls:
                break
            await asyncio.sleep(0.01)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    asyncio.run(exercise())
    assert calls == (["ran"] if runs else [])
    if not runs:
        assert background_tasks.task_health_snapshot()["topic-scheduler"]["state"] == "disabled"


def test_local_tasks_run_on_a_local_server_but_never_under_mock_llm(monkeypatch):
    """The source-check workers serve the local queue of a non-mock dev server."""
    monkeypatch.setattr(main, "_is_production", lambda: False)
    monkeypatch.delenv("LOCAL_BACKGROUND_JOBS", raising=False)
    monkeypatch.setattr(main, "mock_llm_enabled", lambda: False)
    assert main._background_writers_off_reason(local=True) == ""
    assert main._background_writers_off_reason() != ""
    monkeypatch.setattr(main, "mock_llm_enabled", lambda: True)
    assert main._background_writers_off_reason(local=True) == "MOCK_LLM=1"


def test_lifespan_gates_prod_writers_behind_mock_llm(monkeypatch):
    """A local MOCK_LLM server shares the production Firestore: every task that
    claims schedule slots or queued jobs, deletes data, writes the live model
    config or re-registers the prod Telegram webhook must go through the gated
    wrapper. Only the read-only model sync may start unconditionally, so a new
    lifespan task has to choose a side here explicitly."""
    gated, supervised = [], []

    async def idle():
        await asyncio.Event().wait()

    def record(names):
        def factory(_func, name, **_kwargs):
            names.append(name)
            return asyncio.create_task(idle(), name=name)
        return factory

    monkeypatch.setattr(main, "e2e_test_mode_enabled", lambda: False)
    monkeypatch.setattr(main, "apply_worker_thread_budget", lambda: 1)
    monkeypatch.setattr(main, "_load_startup_configuration", lambda: None)
    monkeypatch.setattr(main, "_scheduler_task", record(gated))
    monkeypatch.setattr(main, "_supervised_task", record(supervised))
    from types import SimpleNamespace
    stub = SimpleNamespace(retry_loop=idle)
    monkeypatch.setattr(main, "FirestoreApiAccountCleanup", lambda _db: stub)
    monkeypatch.setattr(main, "FirestoreAccountDeletion", lambda _db: stub)

    async def exercise():
        async with main.lifespan(main.app):
            pass

    asyncio.run(exercise())
    assert set(gated) == {
        "consensus-watch-scheduler",
        "topic-scheduler",
        "seo-weekly-review-scheduler",
        "consensus-api-maintenance",
        "retention-maintenance",
        "source-check-workers",
        "consensus-api-account-cleanup",
        "full-account-deletion-cleanup",
        "model-configuration-backfill",
        "publisher-watch-lineage-backfill",
        "telegram-watch-startup-maintenance",
    }
    assert supervised == ["model-configuration-sync"]


def test_gated_one_shot_never_runs_under_mock_llm(monkeypatch):
    calls = []
    monkeypatch.setattr(main, "mock_llm_enabled", lambda: True)

    async def exercise():
        await main._scheduler_task(
            main._run_once(lambda: calls.append("ran")),
            "telegram-watch-startup-maintenance",
            restart=False,
        )

    asyncio.run(exercise())
    assert calls == []
    health = background_tasks.task_health_snapshot()
    assert health["telegram-watch-startup-maintenance"]["state"] == "disabled"


def test_gated_one_shot_runs_once_without_mock_llm(monkeypatch):
    calls = []
    monkeypatch.setattr(main, "mock_llm_enabled", lambda: False)
    monkeypatch.setattr(main, "_is_production", lambda: True)
    monkeypatch.setattr(main, "send_critical_error_notification", lambda *_a, **_k: None)

    async def exercise():
        await main._scheduler_task(
            main._run_once(lambda: calls.append("ran")),
            "publisher-watch-lineage-backfill",
            restart=False,
        )

    asyncio.run(exercise())
    assert calls == ["ran"]
    health = background_tasks.task_health_snapshot()
    assert health["publisher-watch-lineage-backfill"]["state"] == "completed"


def test_e2e_profile_starts_no_lifespan_task(monkeypatch):
    started = []

    def record(_func, name, **_kwargs):
        started.append(name)
        raise AssertionError(f"{name} started in the E2E profile")

    monkeypatch.setattr(main, "e2e_test_mode_enabled", lambda: True)
    monkeypatch.setattr(main, "apply_worker_thread_budget", lambda: 1)
    monkeypatch.setattr(main, "_scheduler_task", record)
    monkeypatch.setattr(main, "_supervised_task", record)

    async def exercise():
        async with main.lifespan(main.app):
            pass

    asyncio.run(exercise())
    assert started == []


def test_maintenance_health_reports_degraded_task_state():
    background_tasks.mark_task_disabled("optional", "test")
    background_tasks._update("required", state="restarting")

    response = main.maintenance_health()

    assert response["status"] == "degraded"
    assert response["tasks"]["optional"]["state"] == "disabled"


def test_startup_readiness_only_loads_bounded_configuration(monkeypatch):
    calls = []
    monkeypatch.setattr(
        main,
        "load_models_from_db",
        lambda **kwargs: calls.append(kwargs),
    )

    main._load_startup_configuration()

    assert calls == [{"persist_backfill": False}]


def test_startup_configuration_write_runs_through_one_shot_wrapper(monkeypatch):
    calls = []
    monkeypatch.setattr(
        main,
        "load_models_from_db",
        lambda **kwargs: calls.append(kwargs),
    )

    main._backfill_startup_configuration()

    assert calls == [{"strict": True, "persist_backfill": True}]


def test_retention_step_failure_does_not_stop_later_steps(monkeypatch):
    calls = []

    def missing_index():
        raise RuntimeError("FailedPrecondition: index missing")

    steps = (
        ("first_deleted", lambda: calls.append("first") or 1),
        ("broken_deleted", missing_index),
        ("last_deleted", lambda: calls.append("last") or 3),
    )
    monkeypatch.setattr(retention_maintenance, "_cleanup_steps", lambda: steps)

    async def stop_after_first_tick(seconds):
        raise asyncio.CancelledError

    monkeypatch.setattr(retention_maintenance.asyncio, "sleep", stop_after_first_tick)

    async def exercise():
        try:
            await retention_maintenance.retention_maintenance_loop()
        except asyncio.CancelledError:
            pass

    asyncio.run(exercise())
    assert calls == ["first", "last"]
    details = background_tasks.task_health_snapshot()["retention-maintenance"]["details"]
    assert details == {"first_deleted": 1, "last_deleted": 3, "failed_steps": ["broken_deleted"]}


def test_repeated_partial_retention_failure_degrades_health_and_alerts_once(monkeypatch):
    import app.services.telegram_notifier as telegram_notifier
    alerts, statuses = [], []
    tick = 0

    def flaky():
        if tick in (1, 2, 3, 4, 6):
            raise RuntimeError("private cleanup failure")
        return 2

    monkeypatch.setattr(retention_maintenance, "_cleanup_steps", lambda: (
        ("first_deleted", lambda: 1),
        ("chat_deletions_completed", flaky),
    ))
    monkeypatch.setattr(telegram_notifier, "send_critical_error_notification", alerts.append)

    async def advance(seconds):
        nonlocal tick
        statuses.append(main.maintenance_health()["status"])
        tick += 1
        if tick == 7:
            raise asyncio.CancelledError

    monkeypatch.setattr(retention_maintenance.asyncio, "sleep", advance)

    async def exercise():
        try:
            await retention_maintenance.retention_maintenance_loop()
        except asyncio.CancelledError:
            pass

    asyncio.run(exercise())
    assert statuses == ["ok", "degraded", "degraded", "degraded", "degraded", "ok", "degraded"]
    assert len(alerts) == 1  # third failed tick in a row; the clean tick 5 resets
    assert alerts[0]["type"] == "background_task_repeated_failure"
    assert "failed_steps=chat_deletions_completed; failures=3" in alerts[0]["details"]
    assert "private cleanup failure" not in str(alerts[0])
    health = background_tasks.task_health_snapshot()[retention_maintenance.TASK_NAME]
    assert health["consecutive_failures"] == 1 and health["details"]["first_deleted"] == 1
