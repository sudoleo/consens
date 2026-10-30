"""The daily VM time of an account (since 2026-10-26, when Audit and its VM
opened to Pro accounts).

A Sprite is billed only while it runs (Fly.io: CPU and memory by the hour,
nothing while it is warm or cold), and between two of the agent's steps it
pauses within seconds. What an account's VM costs is therefore about the time
its commands run, plus its background processes, which hold it awake
(agent_vm_processes.py). Per UTC day, the token account's day
(agent_quota.day_key), a Pro account gets PRO_DAILY_SECONDS of that, every
other account BASE_DAILY_SECONDS (since 2026-10-30, when Audit and its VM
opened to all of them); admins have no cap. The browser's actions do not
count here: each is a step of the agent's model, which the token account
holds in check.

A command never runs past what is left (agent_vm_tools.VMTools._timeout); a
background process counts with its whole time limit when it starts, because
it outlives its message and nobody watches it end; what it did not run comes
back once a look at it finds it ended (refund, since 2026-10-30). Reads, writes and shares
take seconds and do not count. A message charges its time once, when it ends
(VMSession.close); messages running at the same time can overshoot the cap by
what they started with, which stays small.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.core.observability import safe_exception

# Two hours of running VM a day: several long agent runs, whose time is
# mostly spent thinking, not running commands. Fly.io bills what a sprite
# uses (fly.io/pricing, 2026-10-30): $0.0385 a CPU hour and $0.021875 a GB
# hour of memory. Two hours at full load on all 8 CPUs are about $0.62 plus
# memory (about $0.04 to $0.09 at 1 to 2 GB); a command that waits on the
# network or a dev server at rest uses a small part of that.
PRO_DAILY_SECONDS = 2 * 60 * 60
# Twenty minutes without Pro (Max, 2026-10-30): computing, a file's analysis,
# a chart. Used up, that is about $0.10 at full load.
BASE_DAILY_SECONDS = 20 * 60


def day_key():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def daily_limit(uid):
    """Seconds an account's VM may run today, or None (no cap). The tier is
    read like the token account's (agent_quota.account_tier)."""
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


def refund(store, uid, seconds, day):
    """Gives back ``seconds`` charged on ``day`` (a background process that
    ended before its limit, agent_vm_processes.ProcessTools._refund), never
    below zero; failures are logged like a charge's."""
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
