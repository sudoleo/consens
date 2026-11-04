"""The daily VM time of an account.

A Sprite is billed only while it runs and pauses within seconds between the agent's steps, so its
cost is about the time its commands and background processes run. Per UTC day (the token account's)
Pro gets PRO_DAILY_SECONDS, others BASE_DAILY_SECONDS, admins no cap; browser actions count with
their helper's seconds.

A command never runs past what is left. A background process counts its whole limit when it starts,
since it outlives its message and nobody watches it end, and gets back what it did not run (refund).
Once the day's time is used up, commands and new processes are refused; files, a process's output
and stop and the browser go on without counting past the limit. A message charges its time once when
it ends; messages at the same time may overshoot by what they started with."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.core.observability import safe_exception

# Several long agent runs, mostly thinking rather than running commands. At Fly.io's prices two
# hours at full load on 8 CPUs cost about $0.62 plus memory; a waiting command or idle dev server
# uses a small part.
PRO_DAILY_SECONDS = 2 * 60 * 60
# Computing, a file's analysis, a chart: about $0.10 at full load.
BASE_DAILY_SECONDS = 20 * 60


def day_key():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def daily_limit(uid):
    """Seconds an account's VM may run today, or None (no cap)."""
    from app.services import agent_quota
    tier = agent_quota.account_tier(uid)
    if tier == "admin":
        return None
    return PRO_DAILY_SECONDS if tier == "pro" else BASE_DAILY_SECONDS


def ref(db, uid, day=None):
    return db.collection("users").document(uid).collection("chat_state").document(
        "agent_vm_time_" + (day or day_key()))


def used(db, uid):
    return float((ref(db, uid).get().to_dict() or {}).get("seconds") or 0)


def status(db, uid):
    """Today's VM time for the account's settings."""
    return {"used_seconds": round(used(db, uid)), "limit_seconds": daily_limit(uid)}


def charge(store, uid, seconds):
    """Adds a message's VM time to today; failures are only logged (the cap is cost control, not a
    guard)."""
    if seconds <= 0:
        return
    day = day_key()
    doc = ref(store.db, uid, day)

    def operation(tx):
        data = doc.get(transaction=tx).to_dict() or {}
        tx.set(doc, {"seconds": float(data.get("seconds") or 0) + float(seconds), "day": day,
                     "updated_at": datetime.now(timezone.utc).isoformat()})
    try:
        store._transaction(operation)
    except Exception as exc:
        logging.warning("Agent VM time charge failed category=%s", safe_exception(exc))


def refund(store, uid, seconds, day):
    """Gives back ``seconds`` charged on ``day``, never below zero; failures are logged like a
    charge's."""
    if seconds <= 0:
        return
    doc = ref(store.db, uid, day)

    def operation(tx):
        data = doc.get(transaction=tx).to_dict() or {}
        if not data:
            return
        tx.set(doc, {**data, "seconds": max(0.0, float(data.get("seconds") or 0) - float(seconds)),
                     "updated_at": datetime.now(timezone.utc).isoformat()})
    try:
        store._transaction(operation)
    except Exception as exc:
        logging.warning("Agent VM time refund failed category=%s", safe_exception(exc))
