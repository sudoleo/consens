"""The daily VM time of an account (since 2026-10-26, when Audit and its VM
opened to Pro accounts).

A Sprite is billed only while it runs (Fly.io: CPU and memory by the hour,
nothing while it is warm or cold), and between two of the agent's steps it
pauses within seconds. What an account's VM costs is therefore about the time
its commands run, plus its background processes, which hold it awake
(agent_vm_processes.py). Per UTC day, the token account's day
(agent_quota.day_key), a Pro account gets PRO_DAILY_SECONDS of that; admins
have no cap.

A command never runs past what is left (agent_vm_tools.VMTools._timeout); a
background process counts with its whole time limit when it starts, because
it outlives its message and nobody watches it end. Reads, writes and shares
take seconds and do not count. A message charges its time once, when it ends
(VMSession.close); messages running at the same time can overshoot the cap by
what they started with, which stays small.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.core.observability import safe_exception

# Two hours of running VM a day: several long agent runs, whose time is
# mostly spent thinking, not running commands. About $0.10 at typical load,
# about $1 at full load on 8 CPUs (Fly.io's prices of 2026-10).
PRO_DAILY_SECONDS = 2 * 60 * 60


def day_key():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def daily_limit(uid):
    """Seconds an account's VM may run today, or None (no cap). The admin
    role is read like the token account's (agent_quota._admin_role)."""
    from app.services import agent_quota
    return None if agent_quota._admin_role(uid) else PRO_DAILY_SECONDS


def ref(db, uid, day=None):
    return db.collection("users").document(uid).collection("chat_state").document(
        "agent_vm_time_" + (day or day_key()))


def used(db, uid):
    return float((ref(db, uid).get().to_dict() or {}).get("seconds") or 0)


def status(db, uid):
    """Today's VM time for the account's settings (/user_status)."""
    return {"used_seconds": round(used(db, uid)), "limit_seconds": daily_limit(uid)}


def charge(store, uid, seconds):
    """Adds a message's VM time to today's account; failures are logged, never
    the message's (the cap is cost control, not a guard)."""
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
