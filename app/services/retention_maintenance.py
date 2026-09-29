"""Periodic retention work that must not depend on process restarts."""

from __future__ import annotations

import asyncio
import logging
import os

from app.core.background_tasks import task_succeeded
from app.core.observability import safe_exception
from app.services.share_snapshots import cleanup_expired_pending, cleanup_revoked_shares


def _interval_seconds() -> int:
    try:
        value = int(os.environ.get("RETENTION_MAINTENANCE_INTERVAL_SECONDS", "3600"))
    except (TypeError, ValueError):
        value = 3600
    return max(60, min(value, 24 * 60 * 60))


RETENTION_MAINTENANCE_INTERVAL_SECONDS = _interval_seconds()
TASK_NAME = "retention-maintenance"


def _cleanup_steps():
    """(detail key, callable) pairs; imports stay lazy to keep startup light."""
    from app.services.answer_receipts import cleanup_expired as cleanup_answer_receipts
    from app.services.source_check_jobs import repository
    from app.services.agent_files import cleanup_expired_files
    from app.services.agent_documents import cleanup_expired_documents
    from app.services.google_connections import cleanup_google_data
    from app.services.chat_store import resume_chat_deletions
    from app.services.memory_edit import cleanup_memory_edit_records
    from app.services.notification_outbox import cleanup as cleanup_outbox
    return (
        ("expired_pending_deleted", cleanup_expired_pending),
        ("expired_answer_receipts_deleted", cleanup_answer_receipts),
        ("revoked_shares_deleted", cleanup_revoked_shares),
        ("source_checks_deleted", lambda: repository().cleanup()),
        ("files_deleted", cleanup_expired_files),
        ("documents_deleted", cleanup_expired_documents),
        ("google_records_deleted", cleanup_google_data),
        ("chat_deletions_completed", resume_chat_deletions),
        ("memory_edit_records", cleanup_memory_edit_records),
        ("notification_outbox_deleted", cleanup_outbox),
    )


async def retention_maintenance_loop() -> None:
    while True:
        details: dict = {}
        failed: list[str] = []
        for key, step in _cleanup_steps():
            # Steps are independent: one failing cleanup (for example a
            # Firestore index that is not deployed yet) must not stop the
            # others or crash-restart the whole loop.
            try:
                details[key] = await asyncio.to_thread(step)
            except Exception as exc:
                failed.append(key)
                logging.error("retention step failed step=%s category=%s", key, safe_exception(exc))
        memory = details.pop("memory_edit_records", None)
        if isinstance(memory, dict):
            details["memory_undo_snapshots_purged"] = memory.get("snapshots_purged", 0)
            details["memory_edits_recovered"] = memory.get("edits_recovered", 0)
        if failed:
            details["failed_steps"] = failed
        task_succeeded(TASK_NAME, **details)
        await asyncio.sleep(RETENTION_MAINTENANCE_INTERVAL_SECONDS)
