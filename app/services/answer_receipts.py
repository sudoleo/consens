"""Server-stored /ask answers as the only authoritative Consensus input (R09).

Every successful ``/ask_*`` call stores the exact answer it delivered, bound to
the owner, the logical run, the question, the provider family, the concrete
model and a content digest. ``/consensus`` accepts answers only through these
receipts: the browser sends receipt ids, never authoritative text. A modified
text, a foreign owner, another run or another question is rejected.

Provenance:
- ``developer``  the answer came from the service credential.
- ``byok``       the answer came from the user's own OpenRouter key. It is a
                 real model call, but its model/text provenance rests on a key
                 the service does not control; results built from it are
                 flagged and excluded from model rankings and votes.

Receipts expire after ``RECEIPT_TTL_HOURS`` and are deleted with the account.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

from app.core.observability import safe_exception
from app.services import persistence_guard
from app.services.llm import completion

COLLECTION = "answer_receipts"
SCHEMA_VERSION = 1
RECEIPT_TTL_HOURS = 24
PROVENANCE_DEVELOPER = "developer"
PROVENANCE_BYOK = "byok"
PROVENANCES = frozenset({PROVENANCE_DEVELOPER, PROVENANCE_BYOK})
_RECEIPT_ID_RE = re.compile(r"[0-9a-f]{40}")
MAX_SOURCES = 50


class ReceiptError(Exception):
    """A submitted answer receipt is not a valid authoritative answer."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def content_digest(text: str) -> str:
    return hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()


def question_digest(question: str) -> str:
    return hashlib.sha256(" ".join(str(question or "").split()).encode("utf-8")).hexdigest()


def run_binding(uid: str, usage_run_key: Optional[str], run_id: Optional[str]) -> str:
    """One logical browser run: the usage run key, or the BYOK run id."""
    value = str(usage_run_key or "").strip() or str(run_id or "").strip()
    return hashlib.sha256(f"{uid}\0{value}".encode("utf-8")).hexdigest() if value else ""


def is_receipt_id(value) -> bool:
    return isinstance(value, str) and bool(_RECEIPT_ID_RE.fullmatch(value))


def _clean_sources(sources) -> list:
    clean = []
    for item in sources if isinstance(sources, list) else []:
        if not isinstance(item, dict):
            continue
        clean.append({
            key: str(item.get(key) or "")[:2000]
            for key in ("id", "title", "url", "provider")
            if item.get(key)
        })
        if len(clean) >= MAX_SOURCES:
            break
    return clean


def store_receipt(
    *,
    db,
    uid: str,
    run: str,
    question: str,
    provider: str,
    model: str,
    text: str,
    sources,
    state: str,
    provenance: str,
    now: Optional[datetime] = None,
) -> Optional[str]:
    """Persist one delivered answer; returns its receipt id or None.

    Best effort towards the stream: a storage failure must not break the
    answer the user already sees, it only makes that answer ineligible for a
    server-verified Consensus (the browser then shows a clear error).
    """
    if not uid or not run or provenance not in PROVENANCES or not str(text or "").strip():
        return None
    now = now or _utcnow()
    receipt_id = secrets.token_hex(20)
    document = {
        "schema_version": SCHEMA_VERSION,
        "owner_uid": uid,
        "run": run,
        "question_hash": question_digest(question),
        "provider": str(provider),
        "model": str(model or "")[:120],
        "text": str(text),
        "content_sha256": content_digest(text),
        "sources": _clean_sources(sources),
        "completion": state if state in completion.STATES else completion.COMPLETE,
        "provenance": provenance,
        "created_at": now,
        "expires_at": now + timedelta(hours=RECEIPT_TTL_HOURS),
    }
    ref = db.collection(COLLECTION).document(receipt_id)
    try:
        def persist(transaction):
            persistence_guard.ensure_account_write_allowed(
                uid=uid, db=db, transaction=transaction
            )
            persistence_guard._set(transaction, ref, document)

        persistence_guard._run_transaction(db, persist)
        return receipt_id
    except persistence_guard.AccountDeletionInProgress:
        return None
    except Exception as exc:
        logging.error("answer receipt write failed category=%s", safe_exception(exc))
        return None


def load_receipts(
    *,
    db,
    uid: str,
    run: str,
    question: str,
    receipt_ids: dict,
    now: Optional[datetime] = None,
) -> dict:
    """Resolve ``{provider: receipt_id}`` to verified receipts.

    Raises ReceiptError for any id that is unknown, expired, foreign, bound to
    another run/question/provider, or whose text no longer matches its digest.
    """
    now = now or _utcnow()
    expected_question = question_digest(question)
    receipts = {}
    for receipt_id in receipt_ids.values():
        if not is_receipt_id(receipt_id):
            raise ReceiptError("invalid_answer_receipt", "Invalid answer receipt.")
    refs = {provider: db.collection(COLLECTION).document(receipt_id) for provider, receipt_id in receipt_ids.items()}
    snapshots = {}
    get_all = getattr(db, "get_all", None)
    if callable(get_all) and refs:
        # One batched read instead of one round trip per model before streaming.
        by_path = {snapshot.reference.path: snapshot for snapshot in get_all(list(refs.values()))}
        snapshots = {provider: by_path.get(ref.path) for provider, ref in refs.items()}
    for provider, receipt_id in receipt_ids.items():
        snapshot = snapshots.get(provider) or refs[provider].get()
        data = snapshot.to_dict() if getattr(snapshot, "exists", False) else None
        data = data or {}
        expires_at = data.get("expires_at")
        valid = bool(
            data
            and data.get("owner_uid") == uid
            and isinstance(expires_at, datetime)
            and expires_at.tzinfo is not None
            and expires_at >= now
        )
        if not valid:
            raise ReceiptError("unknown_answer_receipt", "Model answer not found or expired.")
        if (
            not run
            or not hmac.compare_digest(str(data.get("run") or ""), run)
            or not hmac.compare_digest(str(data.get("question_hash") or ""), expected_question)
            or data.get("provider") != provider
        ):
            raise ReceiptError(
                "answer_receipt_mismatch",
                "Model answer does not belong to this run, question or model.",
            )
        text = str(data.get("text") or "")
        if not hmac.compare_digest(content_digest(text), str(data.get("content_sha256") or "")):
            raise ReceiptError("answer_receipt_mismatch", "Model answer failed its integrity check.")
        receipts[provider] = {
            "provider": provider,
            "model": str(data.get("model") or ""),
            "text": text,
            "sources": data.get("sources") if isinstance(data.get("sources"), list) else [],
            "completion": data.get("completion") if data.get("completion") in completion.STATES else completion.COMPLETE,
            "provenance": data.get("provenance") if data.get("provenance") in PROVENANCES else PROVENANCE_BYOK,
        }
    return receipts


def result_provenance(receipts: Iterable[dict]) -> str:
    """``developer`` only if every answer came from the service credential."""
    values = {item.get("provenance") for item in receipts}
    return PROVENANCE_DEVELOPER if values == {PROVENANCE_DEVELOPER} else PROVENANCE_BYOK


class ReceiptStore:
    """Bound store for one database (the router keeps one; tests replace it)."""

    def __init__(self, db):
        self.db = db

    def store(self, **kwargs) -> Optional[str]:
        return store_receipt(db=self.db, **kwargs)

    def load(self, **kwargs) -> dict:
        return load_receipts(db=self.db, **kwargs)


def cleanup_expired(db=None, max_docs: int = 500) -> int:
    if db is None:
        from app.core.security import db_firestore as db
    from app.services.share_snapshots import _where
    deleted = 0
    for doc in _where(db.collection(COLLECTION), "expires_at", "<", _utcnow()).limit(max_docs).stream():
        doc.reference.delete()
        deleted += 1
    return deleted
