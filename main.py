import asyncio
import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.status import HTTP_422_UNPROCESSABLE_CONTENT

# Init Environment
load_dotenv()
logging.basicConfig(level=logging.INFO)

from app.core.observability import (
    CORRELATION_SCOPE_KEY,
    CorrelationMiddleware,
    configure_logging,
    correlation_scope,
    metrics_snapshot,
    new_correlation_id,
    safe_exception,
    safe_traceback,
)
from app.core.error_context import server_error_report
configure_logging()
from app.core.security import CustomSecurityMiddleware, _is_production, db_firestore
from app.core.background_tasks import (
    mark_task_disabled,
    supervise_background_task,
    task_health_snapshot,
)
from app.core.concurrency import apply_worker_thread_budget
from app.core.request_limits import RequestBodyLimitMiddleware
from app.core.static_delivery import StaticDeliveryMiddleware
from app.core.e2e_profile import e2e_test_mode_enabled
from app.core.rate_limit import limiter

# Import routers
from app.api.routers import (
    agent,
    agent_files,
    agent_google,
    admin,
    api_v1,
    auth,
    bookmarks,
    chat,
    chat_history,
    client_errors,
    firebase_auth_proxy,
    pages,
    share,
    source_checks,
    topics,
    users,
    watch,
)
from app.core.config import load_models_from_db, model_config_sync_loop
from app.services.api_account_cleanup import FirestoreApiAccountCleanup
from app.services.account_deletion import FirestoreAccountDeletion
from app.services.api_consensus_runner import (
    api_run_maintenance_loop,
)
from app.services.llm.mock_llm import mock_llm_enabled
from app.services.retention_maintenance import retention_maintenance_loop
from app.services.source_check_jobs import source_check_worker_loop
from app.services.topic_runner import topic_scheduler_loop
from app.services.watch_scheduler import watch_scheduler_loop
from app.services.watch_service import backfill_publisher_watch_lineage
from app.services.seo_weekly_review import seo_review_scheduler_loop
from app.services.telegram_watch import run_startup_maintenance as telegram_startup_maintenance
from app.services.telegram_notifier import (
    dispatch_critical_error_notification,
    send_critical_error_notification,
)


def _load_startup_configuration() -> None:
    """Load the only readiness-critical document with its SDK-side 5s budget."""
    try:
        # Readiness waits for one bounded read only.  Schema backfills and the
        # initial document create are writes and run as a supervised one-shot
        # after the lifespan yields control to the server.
        load_models_from_db(persist_backfill=False)
    except Exception as exc:
        logging.error(
            "load_models_from_db failed on startup; using code defaults category=%s",
            safe_exception(exc),
        )


def _backfill_startup_configuration() -> None:
    load_models_from_db(strict=True, persist_backfill=True)

async def _disabled_loop() -> None:
    return None


def _background_writers_off_reason(*, local: bool = False) -> str:
    """Why this process must not run a shared background writer, or "".

    A local server shares the production Firestore with the live deployment.
    Under MOCK_LLM it would claim due schedule slots and queued jobs, publish
    fixture answers as real snapshots, delete real accounts' data with
    unreleased code, write its own model defaults into the live config or
    re-register the prod bot webhook. Without MOCK_LLM it still repeated the
    deployment's own work: every scheduler, cleanup and startup backfill
    polled the shared database on its own (~10k reads a day per dev server,
    plus full collection scans on every --reload) and competed for the same
    slots. Production runs them; a local server opts in with
    LOCAL_BACKGROUND_JOBS=1. `local` tasks (own local queue) run on every
    non-mock server.
    """
    if mock_llm_enabled():
        return "MOCK_LLM=1"
    if not local and not _is_production() and os.environ.get("LOCAL_BACKGROUND_JOBS") != "1":
        return "local server (LOCAL_BACKGROUND_JOBS=1 starts it)"
    return ""


def _scheduler_task(loop_factory, name: str, *, restart: bool = True, local: bool = False):
    """A shared background writer: started only where it belongs (above)."""
    reason = _background_writers_off_reason(local=local)
    if reason:
        logging.info("%s not started: %s", name, reason)
        mark_task_disabled(name, reason)
        return asyncio.create_task(_disabled_loop(), name=name)
    return _supervised_task(loop_factory, name, restart=restart)


def _supervised_task(loop_factory, name: str, *, restart: bool = True):
    return asyncio.create_task(
        supervise_background_task(
            name,
            loop_factory,
            restart=restart,
            alert=send_critical_error_notification,
        ),
        name=name,
    )


def _run_once(func):
    async def run_once():
        await asyncio.to_thread(func)

    return run_once


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Before the E2E early-return: the streaming endpoints are the same
    # thread-hungry code in every profile, so the budget must not depend on
    # which maintenance loops are enabled.
    apply_worker_thread_budget()

    if e2e_test_mode_enabled():
        # Request-level persistence still runs against the isolated emulator,
        # but no cleanup, recovery, backfill, webhook or scheduler writer is
        # meaningful (or allowed) in the browser-test process.
        logging.info("E2E profile active: all lifespan maintenance is disabled")
        yield
        return

    # Fail-closed Account-Tombstones bleiben bestehen; nur ihre idempotente
    # Datenbereinigung wird nach transienten Firestore-Fehlern wiederholt.
    api_account_cleanup = FirestoreApiAccountCleanup(db_firestore)
    account_deletion = FirestoreAccountDeletion(db_firestore)
    _load_startup_configuration()
    # Writes the local code's normalized defaults into app_config/models,
    # which every live process then adopts through the sync loop below.
    model_config_backfill_task = _scheduler_task(
        _run_once(_backfill_startup_configuration),
        "model-configuration-backfill",
        restart=False,
    )
    # Every process adopts a newly published model revision within one sync
    # interval instead of waiting for its next restart (R25). Read-only, so a
    # MOCK_LLM server keeps following the live configuration.
    model_config_sync_task = _supervised_task(
        model_config_sync_loop, "model-configuration-sync"
    )
    lineage_backfill_task = _scheduler_task(
        _run_once(backfill_publisher_watch_lineage),
        "publisher-watch-lineage-backfill",
        restart=False,
    )
    # setWebhook points the one bot at SITE_URL with this process's secret; a
    # local run would overwrite the production registration.
    telegram_webhook_task = _scheduler_task(
        _run_once(telegram_startup_maintenance),
        "telegram-watch-startup-maintenance",
        restart=False,
    )
    watch_task = _scheduler_task(watch_scheduler_loop, "consensus-watch-scheduler")
    topic_task = _scheduler_task(topic_scheduler_loop, "topic-scheduler")
    seo_review_task = _scheduler_task(
        seo_review_scheduler_loop, "seo-weekly-review-scheduler"
    )
    api_maintenance_task = _scheduler_task(
        api_run_maintenance_loop, "consensus-api-maintenance"
    )
    # Retention, both account cleanups and the source-check workers delete or
    # claim work in the shared production Firestore (and Firebase Auth), so a
    # local mock server must not run them either (and a local server only
    # its own source-check queue).
    retention_task = _scheduler_task(
        retention_maintenance_loop, "retention-maintenance"
    )
    api_account_cleanup_task = _scheduler_task(
        api_account_cleanup.retry_loop, "consensus-api-account-cleanup"
    )
    # Local source checks use their own queue (queue_environment), so a
    # non-mock local server keeps its workers; idle, one read per <=30s scan.
    source_check_task = _scheduler_task(
        source_check_worker_loop, "source-check-workers", local=True
    )
    account_deletion_task = _scheduler_task(
        account_deletion.retry_loop, "full-account-deletion-cleanup"
    )
    tasks = (
        watch_task,
        topic_task,
        seo_review_task,
        api_maintenance_task,
        retention_task,
        source_check_task,
        api_account_cleanup_task,
        account_deletion_task,
        model_config_backfill_task,
        model_config_sync_task,
        lineage_backfill_task,
        telegram_webhook_task,
    )
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

app = FastAPI(
    title="consens.io API",
    version="1.0.0",
    description="Asynchronous, user-bound Consensus runs.",
    lifespan=lifespan,
)


@app.get("/health/maintenance", include_in_schema=False)
def maintenance_health():
    tasks = task_health_snapshot()
    degraded = any(
        item.get("state") in {"failed", "restarting", "degraded"} for item in tasks.values()
    )
    return {
        "status": "degraded" if degraded else "ok",
        "tasks": tasks,
    }


@app.get("/health/metrics", include_in_schema=False)
def operational_metrics():
    return {"status": "ok", "metrics": metrics_snapshot()}

# Add Custom Security Middleware
app.add_middleware(CustomSecurityMiddleware)
app.add_middleware(RequestBodyLimitMiddleware)
app.add_middleware(CorrelationMiddleware)
# Outermost: long-lived caching for content-hashed static/dist bundles and gzip
# for static text and HTML. Server-Sent Events are never compressed or held.
app.add_middleware(StaticDeliveryMiddleware)

# Add Rate Limiter state
app.state.limiter = limiter

# Mount static directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Exception Handlers
@app.exception_handler(HTTPException)
async def handle_http_exception(request, exc: HTTPException):
    # Routen setzen bewusst Header (Retry-After bei 429/503, WWW-Authenticate
    # bei 401); das JSON-Fehlerformat darf sie nicht verschlucken.
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail},
        headers=dict(exc.headers) if exc.headers else None,
    )

@app.exception_handler(RequestValidationError)
async def handle_validation_exception(request, exc: RequestValidationError):
    """422 mit einer garantiert serialisierbaren Fehlerliste.

    exc.errors() enthaelt bei Pydantic v2 zwei Felder, die hier nicht
    hingehoeren: "ctx" traegt das ROHE Exception-Objekt (jeder Validator, der
    wie ueberall in diesem Projekt ValueError wirft, liess json.dumps damit
    platzen -- die Antwort war dann ein 500er statt eines 422ers), und "input"
    spiegelt den eingesendeten Wert zurueck, also potentiell einen Key oder ein
    Token aus einem abgelehnten Feld. Deshalb werden nur Ort, Typ und Meldung
    uebernommen, jeweils als reiner String.
    """
    details = []
    for error in exc.errors():
        location = error.get("loc") or ()
        details.append({
            "loc": [str(part) for part in location],
            "type": str(error.get("type") or ""),
            "msg": str(error.get("msg") or ""),
        })
    return JSONResponse(
        status_code=HTTP_422_UNPROCESSABLE_CONTENT,
        content={"error": "Validation failed", "details": details},
    )

@app.exception_handler(Exception)
async def handle_unexpected_exception(request, exc: Exception):
    route = getattr(request.scope.get("route"), "path", "unmatched")
    # Starlette ruft diesen Handler ausserhalb der CorrelationMiddleware auf;
    # die Request-ID kommt deshalb aus dem Scope (oder wird hier vergeben).
    corr = request.scope.get(CORRELATION_SCOPE_KEY) or new_correlation_id("err")
    with correlation_scope(corr):
        logging.error(
            "Unhandled request exception method=%s route=%s category=%s at=%s",
            request.method,
            route,
            safe_exception(exc),
            safe_traceback(exc),
        )
    # Keine Exception-Message: sie kann Nutzerinhalt tragen. Frames, Commit
    # und Correlation-ID sind der Fundort (app/core/error_context.py).
    try:
        report = server_error_report(
            exc,
            phase="request",
            path=f"{request.method} {route}",
            message="Unhandled server exception.",
            correlation=corr,
            status=500,
        )
        # Unabhaengig von der Antwort versenden: ein BackgroundTask am 500er
        # lief nie, wenn die Antwort schon begonnen hatte (SSE-Streams).
        dispatch_critical_error_notification(report)
    except Exception as alert_error:
        logging.warning("Critical alert could not be prepared category=%s", safe_exception(alert_error))
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"},
        headers={"x-correlation-id": corr},
    )

# Include Routers
#
# Nur /api/v1 ist die dokumentierte, oeffentliche Consensus-API und erscheint
# in /docs bzw. /openapi.json. Alle uebrigen Router sind interne App- und
# Admin-Endpunkte: sie sind zwar einzeln autorisiert, muessen einem Angreifer
# aber nicht als fertige Landkarte samt Parametern serviert werden.
for internal_router in (
    agent.router,
    agent_files.router,
    agent_google.router,
    auth.router,
    users.router,
    bookmarks.router,
    chat.router,
    chat_history.router,
    client_errors.router,
    firebase_auth_proxy.router,
    pages.router,
    admin.router,
    share.router,
    source_checks.router,
    watch.router,
    topics.router,
):
    app.include_router(internal_router, include_in_schema=False)

app.include_router(api_v1.router)
