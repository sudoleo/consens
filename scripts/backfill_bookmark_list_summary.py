"""Give older bookmarks the ``list_summary`` the sidebar list reads.

Since 2026-10-16 every bookmark write stores its sidebar counts in
``list_summary`` (persistence_guard.py), so ``GET /bookmarks`` projects a few
small fields instead of reading whole documents with all answers. Bookmarks
written before that still work: the list reads them in full on every load.
This script stores their summary once, through the same quota transaction as
any bookmark save (a deleted bookmark is never recreated).

Default is a dry run that only reads (one projected read per bookmark).
``--apply`` writes ``list_summary`` and the refreshed ``_quota_bytes``.

    venv\\Scripts\\python.exe scripts\\backfill_bookmark_list_summary.py
    venv\\Scripts\\python.exe scripts\\backfill_bookmark_list_summary.py --apply
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import persistence_guard  # noqa: E402


def missing_summaries(db):
    """(uid, bookmark ref) of every bookmark without a valid stored summary."""
    field = persistence_guard.BOOKMARK_LIST_SUMMARY_FIELD
    for user in db.collection("users").list_documents():
        for snapshot in user.collection("bookmarks").select([field]).stream():
            if persistence_guard.stored_bookmark_list_summary(snapshot.to_dict() or {}) is None:
                yield user.id, snapshot.reference


def main(argv=None, db=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="write the missing summaries")
    args = parser.parse_args(argv)

    if db is None:
        from app.core.security import db_firestore as db

    targets = list(missing_summaries(db))
    print(f"bookmarks without list_summary: {len(targets)} "
          f"(owners: {len({uid for uid, _ref in targets})})")
    if not args.apply:
        print("dry run: nothing written (use --apply)")
        return 0
    written = failed = 0
    for uid, ref in targets:
        try:
            persistence_guard.write_bookmark(
                uid=uid, doc_ref=ref, patch={}, db=db,
                current_guard=lambda current: bool(current),
            )
            written += 1
        except (persistence_guard.PersistenceConflictError, persistence_guard.AccountDeletionInProgress):
            continue  # deleted meanwhile; nothing to summarize
        except persistence_guard.PersistenceLimitError as exc:
            # An over-limit bookmark keeps working through the full-read fallback.
            failed += 1
            print(f"  skipped {ref.path}: {exc.code}")
    print(f"written: {written}, skipped: {failed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
