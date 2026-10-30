"""The workspace's safety rules from the operator's side (app/services/workspace_guard.py).

Production Firestore. ``list`` and ``status`` only read; ``unlock`` writes the
one account's guard and nothing else.

    venv/Scripts/python.exe scripts/workspace_guard.py list
    venv/Scripts/python.exe scripts/workspace_guard.py status <account>
    venv/Scripts/python.exe scripts/workspace_guard.py status <account> --hosts
    venv/Scripts/python.exe scripts/workspace_guard.py unlock <account>

<account> is what the Telegram alert names (the 10 characters of
workspace_guard.uid_tag), a uid or an e-mail address.

- list: every account whose workspace is closed or locked now, and accounts
  closed in the last days, with rule and time.
- status: the account's guard (state, rule, when, until, history) and its
  trail of the last days: counts per day and the flagged hosts (adult,
  malware/phishing by Cloudflare's resolvers). ``--hosts`` lists every host
  of each day (when first and last, how often, the agent or the live view).
  This is the account's browsing by host: look only to decide on a rule.
- unlock: opens the workspace again. What the account did today until now
  is forgiven, earlier closes no longer turn the next one into a lock.

Exit code 0, or 1 when the account is not found.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def resolve(db, account):
    """The uid behind a tag, an e-mail address or a uid, or None."""
    from app.services import workspace_guard
    account = account.strip()
    if "@" in account:
        from firebase_admin import auth
        try:
            return auth.get_user_by_email(account).uid
        except Exception:
            return None
    if len(account) == 10 and all(char in "0123456789abcdef" for char in account):
        for snapshot in db.collection(workspace_guard.GUARD_COLLECTION).stream():
            if workspace_guard.uid_tag(snapshot.id) == account:
                return snapshot.id
        return None
    return account if db.collection(workspace_guard.GUARD_COLLECTION).document(account).get().exists else None


def _when(value):
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC") if isinstance(value, datetime) else "-"


def _size(value):
    from app.services.workspace_guard import _size
    return _size(value)


def show_list(db):
    from app.services import workspace_guard
    now = datetime.now(timezone.utc)
    rows = []
    for snapshot in db.collection(workspace_guard.GUARD_COLLECTION).stream():
        guard = snapshot.to_dict() or {}
        status = workspace_guard.current(guard, now)
        if status.closed or guard.get("closed_days"):
            rows.append((workspace_guard.uid_tag(snapshot.id), status.state, guard.get("rule") or "-",
                         _when(guard.get("at")), _when(status.until), ",".join(guard.get("closed_days") or [])))
    if not rows:
        print("No workspace is closed or was closed lately.")
    for row in sorted(rows, key=lambda item: item[3], reverse=True):
        print("{:<10}  {:<7}  {:<28}  at {:<20}  until {:<20}  closed on {}".format(*row))


def show_status(db, uid, hosts=False, days=7):
    from app.services import workspace_guard
    now = datetime.now(timezone.utc)
    guard = workspace_guard.guard_ref(db, uid).get().to_dict() or {}
    status = workspace_guard.current(guard, now)
    print(f"Account {workspace_guard.uid_tag(uid)} ({uid})")
    print(f"State: {status.state}  rule: {guard.get('rule') or '-'}  at: {_when(guard.get('at'))}  "
          f"until: {_when(status.until) if status.state == 'closed' else '-'}")
    for item in guard.get("history") or []:
        print(f"  {_when(item.get('at'))}  {item.get('state')}  {item.get('rule')}")
    for back in range(days):
        day = workspace_guard.day_key(now - timedelta(days=back))
        trail = workspace_guard.trail_ref(db, uid, day).get().to_dict()
        if not trail:
            continue
        counts = trail.get("counts") or {}
        print(f"\n{day}: {counts.get('hosts', 0)} hosts, {counts.get('flagged', 0)} flagged "
              f"({counts.get('adult', 0)} adult, {counts.get('malware', 0)} malware/phishing), "
              f"typed on {counts.get('typed_hosts', 0)}, view {_size(counts.get('view_bytes'))}, "
              f"VM sent {_size(counts.get('tx_bytes'))}, received {_size(counts.get('rx_bytes'))}"
              + (f", {trail.get('hosts_dropped')} hosts past the list" if trail.get("hosts_dropped") else ""))
        busiest = sorted((trail.get("hours") or {}).items(), key=lambda item: -(item[1] or {}).get("new_hosts", 0))
        if busiest:
            hour, values = busiest[0]
            print(f"  busiest hour {hour}:00 UTC: {values.get('new_hosts', 0)} new hosts, "
                  f"typed on {values.get('typed_hosts', 0)}")
        for entry in trail.get("hosts") or []:
            if hosts or entry.get("category") in workspace_guard.FLAGGED:
                print(f"  {entry.get('category') or 'unsorted':<8} {entry.get('host'):<50} {entry.get('first')}"
                      f"-{entry.get('last')} x{entry.get('n')} by {'+'.join(entry.get('by') or [])}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("list", "status", "unlock"))
    parser.add_argument("account", nargs="?", help="tag from the alert, uid or e-mail address")
    parser.add_argument("--hosts", action="store_true", help="status: every host of each day, not only flagged ones")
    parser.add_argument("--days", type=int, default=7, help="status: how many days back (default 7)")
    args = parser.parse_args(argv)
    if args.command != "list" and not args.account:
        parser.error(f"{args.command} needs an account")
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    if any(os.environ.get(key) for key in ("FIRESTORE_EMULATOR_HOST", "FIREBASE_AUTH_EMULATOR_HOST")) \
            or os.environ.get("UNIT_TEST_MODE") == "1":
        parser.error("This script works on production; unset the test and emulator settings.")
    os.chdir(ROOT)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    from app.core.security import db_firestore as db
    from app.services import workspace_guard
    workspace_guard.use_db(db)
    if args.command == "list":
        show_list(db)
        return 0
    uid = resolve(db, args.account)
    if not uid:
        print(f"No account with a workspace guard found for {args.account}.")
        return 1
    if args.command == "status":
        show_status(db, uid, hosts=args.hosts, days=max(1, args.days))
        return 0
    before = workspace_guard.unlock(uid, db=db)
    print(f"Account {workspace_guard.uid_tag(uid)}: {before.state} -> open. Today's counts so far are forgiven.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
