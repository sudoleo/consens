"""Agent turns that a deploy would cut off: running or paused, from their receipts.

Read-only: queries and .get() on production Firestore, never a write. Run it
before a Render deploy (docs/codebase-map.md, "Neustart/Deploy"): a restart
gives a running turn AGENT_SHUTDOWN_GRACE_SECONDS to finish, and a turn that
waits in a pause (a reviewer's halt, a card of ask_user) does not survive it,
because runs live in their process (agent_background).

    venv/Scripts/python.exe scripts/running_agent_turns.py
    venv/Scripts/python.exe scripts/running_agent_turns.py --json

Every Agent turn has a root receipt in ``users/{uid}/llm_calls`` (its step
``completion:0``, agent_runs.receipt_ref) with ``run_status`` "running"
until it ends (agent_runs.finish_run), its
lease (``lease_until``, renewed while the process runs it) and its open
``hold``. One line per such turn:

- state: ``running``, ``paused`` (a hold is open) or ``stale`` (the lease
  ran out: no process runs it any more, the reaper ends it on its next read)
- account: the first characters of the uid, ``own`` for the operator's accounts
- chat, turn: the first characters of their ids
- started, minutes: when its first step was claimed and how long ago
- step: its newest step; hold: the kind of an open pause, never its text

Exit code 1 while a turn runs or is paused (stale ones do not count), else 0.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TZ = ZoneInfo("Europe/Berlin")
# The operator's own accounts (Max), as in scripts/cache_hit_rate.py.
OWN_UID_PREFIXES = ("mWKgPU", "XP4WVO", "f8MfuG")


def _time(value):
    return value if isinstance(value, datetime) else None


def describe(uid: str, root: dict, now: datetime) -> dict:
    """One turn's line: ids shortened, the hold by its kind only."""
    hold = root.get("hold") if isinstance(root.get("hold"), dict) else None
    decided = hold and (root.get("hold_decision") or {}).get("id") == hold.get("id")
    lease = _time(root.get("lease_until"))
    started = _time(root.get("created_at"))
    state = ("stale" if lease is not None and lease <= now else
             "paused" if hold and not decided else "running")
    kind = ""
    if hold and not decided:
        kind = (f"ask:{hold['ask']}" if hold.get("ask") else "domain" if hold.get("domain")
                else f"gate:{hold.get('kind')}" if hold.get("gate") else str(hold.get("kind") or "halt"))
    return {"state": state, "account": uid[:6], "own": uid.startswith(OWN_UID_PREFIXES),
            "chat": str(root.get("chat_id") or "")[:8], "turn": str(root.get("turn_id") or "")[:8],
            "started": started.astimezone(TZ).strftime("%Y-%m-%d %H:%M") if started else "?",
            "minutes": round((now - started).total_seconds() / 60, 1) if started else None,
            "step": str(root.get("last_step") or root.get("step") or ""), "hold": kind,
            "stop_requested": bool(root.get("cancel_requested"))}


def collect(db, now: datetime, *, workers: int = 16) -> list[dict]:
    """Every root receipt still marked running, one query per account."""
    from google.cloud.firestore_v1.base_query import FieldFilter

    def of(user):
        query = user.collection("llm_calls").where(filter=FieldFilter("run_status", "==", "running"))
        return [describe(user.id, snapshot.to_dict() or {}, now) for snapshot in query.stream()]

    turns = []
    with ThreadPoolExecutor(workers) as pool:
        for found in pool.map(of, db.collection("users").list_documents()):
            turns.extend(found)
    return sorted(turns, key=lambda turn: (turn["state"], turn["started"]))


def blocking(turns: list[dict]) -> list[dict]:
    """The turns a deploy would cut off now."""
    return [turn for turn in turns if turn["state"] in {"running", "paused"}]


def table(turns: list[dict]) -> str:
    if not turns:
        return "No Agent turn is running or paused."
    lines = [f"{'state':<8} {'account':<10} {'chat':<9} {'turn':<9} {'started':<17} {'min':>6} {'step':<44} hold"]
    for turn in turns:
        account = turn["account"] + (" own" if turn["own"] else "")
        minutes = "?" if turn["minutes"] is None else f"{turn['minutes']:.1f}"
        lines.append(f"{turn['state']:<8} {account:<10} {turn['chat']:<9} {turn['turn']:<9} {turn['started']:<17} "
                     f"{minutes:>6} {turn['step'][:44]:<44} {turn['hold']}{' (stop requested)' if turn['stop_requested'] else ''}")
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", action="store_true", help="print JSON instead of a table")
    args = parser.parse_args(argv)
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    from app.core.security import db_firestore as db
    now = datetime.now(timezone.utc)
    turns = collect(db, now)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if args.json:
        print(json.dumps({"at": now.isoformat(), "blocking": len(blocking(turns)), "turns": turns}, indent=1))
    else:
        print(f"Agent turns at {now.astimezone(TZ):%Y-%m-%d %H:%M:%S}\n")
        print(table(turns))
    return 1 if blocking(turns) else 0


if __name__ == "__main__":
    raise SystemExit(main())
