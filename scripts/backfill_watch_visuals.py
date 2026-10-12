"""Give existing watches their symbol and, where one can be found, a picture.

Since 2026-10-12 every watch gets a symbol (picked once by the cheap Judge)
and, failing a product shot or article photo, the logos of the sites it is
about (services/watch_images.py). New and active watches get both after their
next check; paused ones are never checked again, so this backfills them.

Sources are those of the latest successful check plus the original answer.
The Judge sees the question, the goal and the source domains -- one cheap call
per watch that still lacks a symbol or its site choice.

Default is a dry run: it calls the Judge and fetches the pages, but writes
nothing. ``--apply`` stores symbol, site choice and picture exactly as a check
would (``refresh_for_watch``), never touching other fields.

    venv\\Scripts\\python.exe scripts\\backfill_watch_visuals.py
    venv\\Scripts\\python.exe scripts\\backfill_watch_visuals.py --apply
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import share_snapshots, watch_images, watch_service  # noqa: E402

STATUSES = ("active", "paused", "paused_error", "resolved")


def _sources(db, watch: dict, share: dict) -> list:
    sources = []
    run_id = str(watch.get("last_successful_run_id") or "")
    if run_id and watch.get("share_id"):
        run = db.collection("shares").document(watch["share_id"]).collection("watch_history").document(run_id).get()
        sources += list((run.to_dict() or {}).get("sources") or []) if run.exists else []
    return sources + list(share.get("sources") or [])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--apply", action="store_true", help="write to Firestore (default: dry run)")
    args = parser.parse_args(argv)

    from app.core.security import db_firestore as db

    pick = watch_images._default_pick()
    if pick is None:
        print("Judge unavailable (test or mock mode); nothing to do.")
        return 1
    # Erst die Liste, dann die langsame Arbeit: ein offener Stream liefe ab.
    snapshots = list(db.collection(watch_service.WATCHES_COLLECTION).stream())
    failed = 0
    for snapshot in snapshots:
        watch = snapshot.to_dict() or {}
        if watch.get("status") not in STATUSES:
            continue
        try:
            share = share_snapshots.get_share(str(watch.get("share_id") or "")) or {}
            question = str(share.get("question") or "")
            condition = str(watch.get("condition") or "")
            sources = _sources(db, watch, share)
            if not question or not watch_images.wants_work(watch, sources):
                continue
            if args.apply:
                outcome = watch_images.refresh_for_watch(
                    snapshot.id, watch, sources, question, condition, db=db, pick=pick,
                )
                print(f"{snapshot.id}: {outcome}")
                continue
            # Der Trockenlauf ruft den Judge wirklich (Kosten wie --apply).
            verdict = watch_images._pick_visual(pick, question, condition, sources)
            sites = verdict["sites"] if verdict else None
            found = None
            if watch_images.needs_image(watch):
                found, _looked = watch_images.search(sources, question, condition, sites=sites)
            print(f"{snapshot.id}: {question[:70]!r}\n"
                  f"    symbol={verdict and verdict['symbol']} sites={sites}"
                  f" -> {found and (found['kind'], found['source_host'])}")
        except Exception as exc:  # eine kaputte Watch hält die übrigen nicht auf
            failed += 1
            print(f"{snapshot.id}: failed {type(exc).__name__}")
    if not args.apply:
        print("\nDry run. Re-run with --apply to write.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
