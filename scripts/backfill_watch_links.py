"""Give existing watches real source URLs and their dashboard direct links.

Since 2026-10-12 a check stores Google grounding redirects as the pages they
point to (services/source_redirects.py) and the watch keeps up to three direct
links for the dashboard (services/source_links.card_links). This backfills
both for existing watches:

* every check of the watch (``shares/{id}/watch_history``): ``sources``,
  ``evidence_sources``, ``condition_sources``;
* the share the watch started from: ``sources``;
* the watch itself: ``history_points[].evidence_sources``, ``resolution``,
  ``last_probe`` and ``key_links`` (from the answer the watch page shows).

One request per redirect to Google's fixed host reads where it points; the
target page itself is never fetched. No model calls.

Default is a dry run that resolves and reports but writes nothing.
``--apply`` writes only the fields that change.

    venv\\Scripts\\python.exe scripts\\backfill_watch_links.py
    venv\\Scripts\\python.exe scripts\\backfill_watch_links.py --apply
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import source_links, source_redirects, watch_service  # noqa: E402

STATUSES = ("active", "paused", "paused_error", "resolved")
RUN_FIELDS = ("sources", "evidence_sources", "condition_sources")
SHARE_FIELDS = ("sources",)
WATCH_FIELDS = ("history_points", "resolution", "last_probe")


def _resolve(urls) -> dict[str, str]:
    urls = list(dict.fromkeys(urls))
    mapping = {}
    for start in range(0, len(urls), source_redirects.MAX_URLS):
        mapping.update(source_redirects.resolve_urls(urls[start:start + source_redirects.MAX_URLS]))
    return mapping


def _changes(data: dict, fields, mapping) -> dict:
    changes = {}
    for field in fields:
        if field in data:
            value, changed = source_redirects.replace_urls(data[field], mapping)
            if changed:
                changes[field] = value
    return changes


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--apply", action="store_true", help="write to Firestore (default: dry run)")
    args = parser.parse_args(argv)

    from app.core.security import db_firestore as db

    totals = {"redirects": 0, "resolved": 0, "docs": 0, "key_links": 0}
    snapshots = list(db.collection(watch_service.WATCHES_COLLECTION).stream())
    failed = 0
    for snapshot in snapshots:
        watch = snapshot.to_dict() or {}
        if watch.get("status") not in STATUSES or not watch.get("share_id"):
            continue
        try:
            share_ref = db.collection("shares").document(watch["share_id"])
            share_snap = share_ref.get()
            share = share_snap.to_dict() if share_snap.exists else {}
            runs = [(doc.reference, doc.to_dict() or {}) for doc in share_ref.collection("watch_history").stream()]

            redirects = source_redirects.collect_redirects([watch.get(field) for field in WATCH_FIELDS])
            redirects += source_redirects.collect_redirects([share.get(field) for field in SHARE_FIELDS])
            for _ref, run in runs:
                redirects += source_redirects.collect_redirects([run.get(field) for field in RUN_FIELDS])
            mapping = _resolve(redirects)
            totals["redirects"] += len(set(redirects))
            totals["resolved"] += len(mapping)

            writes = []
            for ref, run in runs:
                changes = _changes(run, RUN_FIELDS, mapping)
                if changes:
                    writes.append((ref, changes))
                    run.update(changes)
            share_changes = _changes(share, SHARE_FIELDS, mapping)
            if share_changes:
                writes.append((share_ref, share_changes))
                share.update(share_changes)
            watch_changes = _changes(watch, WATCH_FIELDS, mapping)

            shown_id = str(watch.get("accepted_run_id") or watch.get("last_successful_run_id") or "")
            shown = next((run for ref, run in runs if ref.id == shown_id), None) or share
            links = source_links.card_links(shown.get("sources"), shown.get("consensus_md"))
            if links != watch.get("key_links"):
                watch_changes["key_links"] = links
                totals["key_links"] += 1
            if watch_changes:
                writes.append((snapshot.reference, watch_changes))
            totals["docs"] += len(writes)

            print(f"{snapshot.id}: {len(set(redirects))} redirects, {len(mapping)} resolved, "
                  f"{len(writes)} docs; links: {[link['domain'] for link in links]}")
            if args.apply:
                for ref, changes in writes:
                    ref.update(changes)
        except Exception as exc:  # eine kaputte Watch hält die übrigen nicht auf
            failed += 1
            print(f"{snapshot.id}: failed {type(exc).__name__}")
    print(f"\n{totals}" + ("" if args.apply else "\nDry run. Re-run with --apply to write."))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
