"""Late measurement of Agent calls that settled without final usage (R07).

Settlement charges such calls a bounded estimate (``agent_quota.settle``) and
marks their receipt ``quota_reconcile="pending"`` when a provider generation id
exists. This module later asks OpenRouter for that generation's real token
counts and swaps the estimate for them in one transaction, fenced by the
receipt state so a call is never reconciled (or charged) twice. Receipts that
stay unmeasured after a bounded number of attempts or a bounded age keep their
estimate and become ``final``. Receipts store no prompts or answers; neither
does this module log provider bodies.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from firebase_admin import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from app.core.observability import safe_exception
from app.core.openrouter_contract import OPENROUTER_BASE_URL, openrouter_headers
from app.services import agent_quota, persistence_guard


PENDING = "pending"
MEASURED = "measured"
FINAL = "final"
MAX_ATTEMPTS = 6
MAX_AGE = timedelta(hours=24)
BATCH_SIZE = 20
USER_COOLDOWN_SECONDS = 60
LOOKUP_TIMEOUT_SECONDS = 5

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="agent-usage-reconcile")
_lock = threading.Lock()
_last_scheduled: dict[str, float] = {}


def _enabled() -> bool:
    # Test/mock profiles share fixture generation ids that must never reach a
    # live provider lookup. Tests call ``reconcile_pending`` directly.
    return not any(os.getenv(key) == "1" for key in ("UNIT_TEST_MODE", "E2E_TEST_MODE", "MOCK_LLM"))


def schedule(db, uid: str) -> bool:
    """Run one bounded reconciliation pass for ``uid`` in the background."""
    if not _enabled():
        return False
    now = time.monotonic()
    with _lock:
        if now - _last_scheduled.get(uid, -USER_COOLDOWN_SECONDS) < USER_COOLDOWN_SECONDS:
            return False
        _last_scheduled[uid] = now
        if len(_last_scheduled) > 10_000:
            _last_scheduled.clear()
            _last_scheduled[uid] = now

    def run():
        try:
            from app.services.llm.credentials import openrouter_api_key, resolve_developer_api_keys
            key = openrouter_api_key(resolve_developer_api_keys())
            if key:
                reconcile_pending(db, uid, fetch_usage=lambda generation_id: fetch_generation_tokens(generation_id, key))
        except Exception as exc:
            logging.warning("Agent usage reconciliation failed category=%s", safe_exception(exc))

    _executor.submit(run)
    return True


def fetch_generation_tokens(generation_id: str, api_key: str):
    """Measured input + output tokens of one generation, or None if not ready."""
    import httpx

    response = httpx.get(
        f"{OPENROUTER_BASE_URL}/generation",
        params={"id": generation_id},
        headers=openrouter_headers(api_key),
        timeout=LOOKUP_TIMEOUT_SECONDS,
    )
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return generation_tokens(response.json())


def generation_tokens(payload):
    """Parse OpenRouter generation stats; native counts match stream usage."""
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        return None
    for prompt_key, completion_key in (("native_tokens_prompt", "native_tokens_completion"),
                                       ("tokens_prompt", "tokens_completion")):
        prompt, completion = data.get(prompt_key), data.get(completion_key)
        if all(type(value) is int and 0 <= value <= 10_000_000 for value in (prompt, completion)):
            return prompt + completion
    return None


def _as_datetime(value):
    return value if isinstance(value, datetime) else None


def reconcile_pending(db, uid: str, *, fetch_usage, now: datetime | None = None) -> dict:
    """Idempotently measure a bounded batch of pending estimated receipts."""
    now = now or datetime.now(timezone.utc)
    calls = db.collection("users").document(uid).collection("llm_calls")
    pending = calls.where(filter=FieldFilter("quota_reconcile", "==", PENDING)).limit(BATCH_SIZE).stream()
    outcome = {"measured": 0, "finalized": 0, "retry": 0}
    for snapshot in pending:
        receipt = snapshot.to_dict() or {}
        settled_at = _as_datetime(receipt.get("settled_at")) or _as_datetime(receipt.get("created_at"))
        attempts = int(receipt.get("quota_reconcile_attempts") or 0)
        generation_id = str(receipt.get("generation_id") or "")
        if not generation_id or attempts >= MAX_ATTEMPTS or (settled_at and now - settled_at > MAX_AGE):
            if _apply(db, uid, snapshot.reference, actual=None, now=now):
                outcome["finalized"] += 1
            continue
        try:
            actual = fetch_usage(generation_id)
        except Exception as exc:
            logging.warning("Agent usage lookup failed category=%s", safe_exception(exc))
            actual = None
        if actual is None:
            _apply(db, uid, snapshot.reference, actual=None, now=now, retry=True)
            outcome["retry"] += 1
        elif _apply(db, uid, snapshot.reference, actual=actual, now=now):
            outcome["measured"] += 1
    return outcome


def _apply(db, uid, receipt_ref, *, actual, now, retry=False) -> bool:
    user_ref = db.collection("users").document(uid)

    def operation(tx):
        persistence_guard.ensure_account_write_allowed(uid=uid, db=db, transaction=tx)
        receipt = receipt_ref.get(transaction=tx).to_dict() or {}
        # The receipt state is the exactly-once fence for the ledger swap.
        if receipt.get("quota_reconcile") != PENDING:
            return False
        estimate = int(receipt.get("quota_estimate") or 0)
        day = receipt.get("quota_day")
        daily_ref = agent_quota.quota_ref(db, uid, day) if day and actual is not None else None
        daily = (daily_ref.get(transaction=tx).to_dict() or {}) if daily_ref else None
        user = user_ref.get(transaction=tx) if actual is not None else None
        if retry:
            attempts = int(receipt.get("quota_reconcile_attempts") or 0) + 1
            tx.update(receipt_ref, {"quota_reconcile_attempts": attempts,
                                    **({"quota_reconcile": FINAL} if attempts >= MAX_ATTEMPTS else {})})
            return False
        if actual is None:
            tx.update(receipt_ref, {"quota_reconcile": FINAL, "quota_reconciled_at": now})
            return True
        if daily_ref:
            tx.set(daily_ref, agent_quota.reconcile(daily, estimate, actual))
        if user is not None and user.exists:
            totals = dict((user.to_dict() or {}).get("agent_usage") or {})
            totals["reconciled_calls"] = totals.get("reconciled_calls", 0) + 1
            totals["reconciled_tokens"] = totals.get("reconciled_tokens", 0) + actual
            totals["updated_at"] = firestore.SERVER_TIMESTAMP
            tx.update(user_ref, {"agent_usage": totals})
        tx.update(receipt_ref, {"quota_reconcile": MEASURED, "quota_measured_tokens": actual,
                                "quota_reconciled_at": now})
        return True

    from app.services.agent_runs import AgentRunStore
    return AgentRunStore(db)._agent_transaction(uid, operation)
