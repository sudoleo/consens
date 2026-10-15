"""Delete what the removed contradiction source check left in Firestore.

The source check (background jobs that judged contradictions against the
models' cited sources) was removed on 2026-10-15. Its collections are no
longer read, cleaned up after 30 days or deleted with an account, so they are
removed once, completely:

* ``source_check_jobs`` and both dispatch queues (``..._v1_local``,
  ``..._v1_production``), each job with its ``data`` and ``packages``
  subcollections;
* ``source_check_cache`` (fetched documents and judge results);
* ``source_check_workers`` (worker heartbeats).

Chats, bookmarks and shares saved before that date may still carry a
``source_verification`` report; the app ignores it and it goes with them.

Default is a dry run that counts the top-level documents and writes nothing.
``--apply`` deletes them with their subcollections.

    venv\\Scripts\\python.exe scripts\\purge_source_checks.py
    venv\\Scripts\\python.exe scripts\\purge_source_checks.py --apply
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

COLLECTIONS = (
    "source_check_jobs",
    "source_check_jobs_dispatch_v1_local",
    "source_check_jobs_dispatch_v1_production",
    "source_check_cache",
    "source_check_workers",
)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--apply", action="store_true", help="delete in Firestore (default: dry run)")
    args = parser.parse_args(argv)

    from app.core.security import db_firestore as db

    total = 0
    for name in COLLECTIONS:
        collection = db.collection(name)
        # An aggregation reads one document per thousand counted.
        count = collection.count().get()[0][0].value
        if args.apply and count:
            deleted = db.recursive_delete(collection)
            print(f"{name}: {count} top-level documents, {deleted} deleted with their subcollections")
            total += deleted
        else:
            print(f"{name}: {count} top-level documents")
            total += count
    print(("deleted" if args.apply else "would delete at least") + f" {total} documents")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
