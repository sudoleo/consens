"""Daily evidence probe between two full Consensus Watch checks.

A weekly watch that waits for an announcement should not learn about it six
days late. Once a day, one inexpensive model with web search is asked whether
anything new bears on the question or the goal since the last check. Only a
source the standing answer did not cite counts; then the full check (all
models, cross-checked, evidence-aware) is pulled forward to now. Everything
else changes nothing -- a probe never writes an answer, it only schedules
(contract: docs/watch-evidence-model.md).

Probes run inside the scheduler tick under the global worker lease, are
claimed at-most-once (the next probe time advances before the call) and share
one daily cap, ``watch_probe_max_per_day``.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone

from google.cloud.firestore_v1.base_query import FieldFilter

import app.core.config as cfg
from app.core.entitlements import TIER_FREE
from app.core.observability import safe_exception
from app.core.security import db_firestore
from app.services import share_snapshots, watch_service
from app.services.llm import provider_transport
from app.services.source_catalog import canonical_source_url

PROBE_INTERVAL = timedelta(hours=24)
# A probe is pointless when the full check runs soon anyway.
PROBE_MIN_LEAD = timedelta(hours=30)
# Gemini first: its search grounding is the cheapest current-news lookup of
# the Free watch line-up; the others follow the configured order.
PROBE_PROVIDER_PREFERENCE = ("gemini", "openai", "mistral")
PROBE_SUMMARY_CHARS = 300
_VERDICT_RE = re.compile(r"^\s*NEW\s*:\s*(yes|no)\b", re.IGNORECASE)

OUTCOME_NEW = "new_evidence"
OUTCOME_NOTHING = "nothing_new"
OUTCOME_FAILED = "failed"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def eligible(watch: dict) -> bool:
    """Probes are for owner watches that wait longer than a day between checks."""
    return (
        watch.get("status") == "active"
        and watch.get("interval") in {"weekly", "monthly"}
        and watch.get("model_tier") != "free"
    )


def next_probe_after(watch: dict, now: datetime) -> datetime | None:
    """When to probe next, or None when the watch never needs one."""
    return now + PROBE_INTERVAL if eligible(watch) else None


def _probe_model(keys: dict) -> tuple[str, str] | None:
    configured = cfg.get_watch_models(TIER_FREE)
    order = list(PROBE_PROVIDER_PREFERENCE) + [
        provider for provider in configured if provider not in PROBE_PROVIDER_PREFERENCE
    ]
    for provider in order:
        model = configured.get(provider)
        if model and provider_transport.provider_available(provider, keys):
            return provider, model
    return None


def _prompt(question: str, goal: str, since: datetime) -> str:
    focus = (
        f"In particular: has this happened yet? {goal}\n" if goal else ""
    )
    return (
        f"Search the web for news published since {since.strftime('%Y-%m-%d')} on "
        f"this question:\n{question}\n{focus}\n"
        "Begin your reply with exactly one line, NEW: yes or NEW: no. Answer yes "
        "only if a source published in that window reports a concrete development "
        "(an announcement, a release, a figure, a decision). Then, if yes, name it "
        "in at most three sentences and cite the sources. Do not summarise older "
        "background."
    )


def evaluate(text: str, sources, standing_sources) -> dict:
    """Decide a probe from its reply and sources; only a new source counts."""
    match = _VERDICT_RE.match(str(text or ""))
    says_new = bool(match and match.group(1).lower() == "yes")
    known = {
        canonical_source_url((item or {}).get("url"))
        for item in standing_sources or [] if isinstance(item, dict)
    }
    fresh = [
        {"title": str(item.get("title") or "")[:240], "url": str(item.get("url") or "")}
        for item in share_snapshots.sanitize_sources(sources or [])
        if canonical_source_url(item.get("url")) not in known
    ][:3]
    outcome = OUTCOME_NEW if says_new and fresh else OUTCOME_NOTHING
    summary = _VERDICT_RE.sub("", str(text or ""), count=1).strip()
    return {
        "outcome": outcome,
        "summary": summary[:PROBE_SUMMARY_CHARS] if outcome == OUTCOME_NEW else "",
        "sources": fresh if outcome == OUTCOME_NEW else [],
    }


def execute_probe(question: str, goal: str, standing_sources, since: datetime) -> dict:
    keys = provider_transport.developer_keys()
    chosen = _probe_model(keys)
    if chosen is None:
        raise RuntimeError("No probe model is available.")
    provider, model = chosen
    reply = provider_transport.query_provider(
        provider, model, _prompt(question, goal, since), keys, TIER_FREE,
    )
    if reply.get("error"):
        raise RuntimeError(str(reply.get("error_code") or "probe_failed"))
    return evaluate(reply.get("text") or "", reply.get("sources") or [], standing_sources)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def _budget_ref(db, now: datetime):
    return db.collection(watch_service.RUNTIME_COLLECTION).document(
        "probe_daily_" + now.strftime("%Y%m%d")
    )


def list_due_probe_ids(*, now=None, db=None, max_items=50) -> list[str]:
    db = db if db is not None else db_firestore
    now = now or utcnow()
    query = (
        db.collection(watch_service.WATCHES_COLLECTION)
        .where(filter=FieldFilter("status", "==", "active"))
        .where(filter=FieldFilter("next_probe_at", "<=", now))
        .order_by("next_probe_at")
        .limit(max(1, min(200, int(max_items))))
    )
    return [doc.id for doc in query.stream()]


def claim_probe(watch_id: str, *, now=None, db=None):
    """Advance the probe time first (at-most-once) and take one budget slot.

    Returns the watch snapshot to probe, or ``(None, reason)`` with reason
    ``budget`` when today's cap is used up.
    """
    db = db if db is not None else db_firestore
    now = now or utcnow()
    ref = db.collection(watch_service.WATCHES_COLLECTION).document(watch_id)
    budget_ref = _budget_ref(db, now)
    limit = cfg.get_watch_probe_max_per_day()

    def claim(transaction):
        snapshot = ref.get(transaction=transaction)
        budget_snapshot = budget_ref.get(transaction=transaction)
        data = snapshot.to_dict() if snapshot.exists else None
        due = (data or {}).get("next_probe_at")
        if not data or not isinstance(due, datetime) or due > now:
            return None, "not_due"
        if not eligible(data):
            transaction.update(ref, {"next_probe_at": None})
            return None, "not_eligible"
        claimed_until = data.get("claimed_until")
        next_run = data.get("next_run_at")
        if (
            (isinstance(claimed_until, datetime) and claimed_until > now)
            or not isinstance(next_run, datetime)
            or next_run - now < PROBE_MIN_LEAD
        ):
            # A full check is running or close: it covers today.
            transaction.update(ref, {"next_probe_at": now + PROBE_INTERVAL})
            return None, "covered"
        count = (budget_snapshot.to_dict() or {}).get("count", 0) if budget_snapshot.exists else 0
        count = count if isinstance(count, int) and count >= 0 else 0
        if count >= limit:
            return None, "budget"
        transaction.update(ref, {"next_probe_at": now + PROBE_INTERVAL})
        transaction.set(budget_ref, {"date": now.strftime("%Y-%m-%d"), "count": count + 1})
        return dict(data), "claimed"

    return watch_service._run_transaction(db, claim)


def record_probe(watch_id: str, verdict: dict, *, now=None, db=None) -> bool:
    """Store the probe result; on new evidence pull the full check to now."""
    db = db if db is not None else db_firestore
    now = now or utcnow()
    ref = db.collection(watch_service.WATCHES_COLLECTION).document(watch_id)

    def persist(transaction):
        snapshot = ref.get(transaction=transaction)
        data = snapshot.to_dict() if snapshot.exists else None
        if not data:
            return False
        updates = {"last_probe": {
            "at": now,
            "outcome": verdict.get("outcome") or OUTCOME_FAILED,
            "summary": str(verdict.get("summary") or "")[:PROBE_SUMMARY_CHARS],
            "sources": list(verdict.get("sources") or [])[:3],
        }}
        pulled = False
        next_run = data.get("next_run_at")
        claimed_until = data.get("claimed_until")
        if (
            verdict.get("outcome") == OUTCOME_NEW
            and data.get("status") == "active"
            and isinstance(next_run, datetime) and next_run > now
            and not (isinstance(claimed_until, datetime) and claimed_until > now)
        ):
            updates["next_run_at"] = now
            pulled = True
        transaction.update(ref, updates)
        return pulled

    return bool(watch_service._run_transaction(db, persist))


def run_probe(watch_id: str, *, now=None, db=None) -> str:
    """Claim, execute and record one probe. Returns its outcome or a skip reason."""
    now = now or utcnow()
    claimed, reason = claim_probe(watch_id, now=now, db=db)
    if not claimed:
        return reason
    try:
        share = share_snapshots.get_share(str(claimed.get("share_id") or ""), db=db)
        if not share or share.get("status") != "active":
            return "unavailable"
        standing = None
        standing_id = watch_service.standing_run_id(claimed)
        if standing_id:
            standing = share_snapshots.get_watch_version(claimed["share_id"], standing_id, db=db)
        since = claimed.get("last_run_at") if isinstance(claimed.get("last_run_at"), datetime) else (
            claimed.get("created_at") if isinstance(claimed.get("created_at"), datetime) else now
        )
        verdict = execute_probe(
            str(share.get("question") or ""),
            str(claimed.get("condition") or ""),
            (standing or share).get("sources") or [],
            since,
        )
    except Exception as exc:
        logging.warning("Watch probe failed category=%s", safe_exception(exc))
        verdict = {"outcome": OUTCOME_FAILED}
    pulled = record_probe(watch_id, verdict, now=utcnow(), db=db)
    return "pulled" if pulled else verdict["outcome"]
