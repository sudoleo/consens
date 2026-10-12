"""Give shared answers real source URLs and drop the dead ones.

Shared pages (also those without a watch) keep the sources of the answer they
were shared from. Gemini cites them as Google grounding redirects, which expire
(July -> 404, October -> 302 on 2026-10-12). Since 2026-10-12 a new share is
resolved in the background right after it is created
(``share_snapshots.schedule_share_cleanup``); this backfills existing ones with
``share_snapshots.clean_share_sources(check_expired=True)``:

* a redirect that still resolves becomes the page it points to, in the
  sources and in the source check's documents alike;
* a redirect Google no longer knows (404/410) is removed from the sources and
  its number kept in ``expired_source_ids``, so old ``[S3]`` references are
  dropped instead of shown as bare text.

One request per redirect to Google's fixed host; the target page itself is
never fetched. No model calls.

Default is a dry run that resolves and checks but writes nothing.
``--apply`` writes only the fields that change.

    venv\\Scripts\\python.exe scripts\\backfill_share_links.py
    venv\\Scripts\\python.exe scripts\\backfill_share_links.py --apply
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import share_snapshots  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--apply", action="store_true", help="write to Firestore (default: dry run)")
    args = parser.parse_args(argv)

    from app.core.security import db_firestore as db

    totals = {"shares": 0, "redirects": 0, "resolved": 0, "expired": 0, "changed": 0}
    failed = 0
    ids = [snap.id for snap in db.collection(share_snapshots.SHARES_COLLECTION).stream()]
    for share_id in ids:
        try:
            stats = share_snapshots.clean_share_sources(share_id, db=db, check_expired=True, apply=args.apply)
        except Exception as exc:  # eine kaputte Share hält die übrigen nicht auf
            failed += 1
            print(f"{share_id}: failed {type(exc).__name__}")
            continue
        if not stats["redirects"]:
            continue
        totals["shares"] += 1
        for key in ("redirects", "resolved", "expired"):
            totals[key] += stats[key]
        totals["changed"] += int(stats["changed"])
        print(f"{share_id}: {stats['redirects']} redirects, {stats['resolved']} resolved, "
              f"{stats['expired']} expired")
    print(f"\n{totals}" + ("" if args.apply else "\nDry run. Re-run with --apply to write."))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
