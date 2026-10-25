"""Cleanup of the retired /ask answer receipts (R09).

Until 2026-10-25 every ``/ask_*`` call stored the answer it delivered as a
receipt, and the browser's ``/consensus`` accepted answers only through those
receipts. The browser runs no Consensus any more and ``/consensus`` is gone,
so no receipt is written. What stays: the expired ones are swept by the
retention job (``retention_maintenance``) and account deletion removes the
collection (``account_deletion``).
"""

from __future__ import annotations

from datetime import datetime, timezone

COLLECTION = "answer_receipts"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def cleanup_expired(db=None, max_docs: int = 500) -> int:
    if db is None:
        from app.core.security import db_firestore as db
    from app.services.share_snapshots import _where
    deleted = 0
    for doc in _where(db.collection(COLLECTION), "expires_at", "<", _utcnow()).limit(max_docs).stream():
        doc.reference.delete()
        deleted += 1
    return deleted
