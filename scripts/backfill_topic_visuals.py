"""Give existing Topics their picture, the opening of their standing answer
and figures for it.

Since 2026-10-15 a Topic page is built like a Watch page: a picture from its
sources (services/topic_images.py), on the hub the first sentences of the
answer that stands (``accepted_lead``), and figures drawn from that answer
(services/topic_figures.py, stored on the run). All three appear by themselves
with the next check; this fills them in for the Topics that exist today. The
figures are the one field added to an already published run: derived from its
own answer, nothing in it changes.

``--figures FILE`` takes figures already made for the standing runs (JSON:
``{slug: {"cleaned": [...]}}`` as written by a probe), so they are not asked
for twice; without it the Judge is called once per Topic.

Default is a dry run: it calls the visual Judge once per Topic without a
picture and fetches the pages, but writes nothing; ``--out DIR`` saves the
picture it would store, for a look. ``--apply`` stores picture, opening and figures
exactly as a check would, never touching other fields.

``--redo-figures`` does only the figures and replaces the ones a standing run
already has: for after the templates changed (2026-11-12: lineup and the
shared time axis). With ``--figures FILE`` no Judge is asked.

``--pictures`` does only the pictures on the Direct-links cards
(services/topic_pictures.py) and nothing else: no Judge is asked. Its dry run
fetches the pages the standing answers cite, says per page whether it gave a
picture and why not, and with ``--out DIR`` saves the thumbnails for a look.

    venv\\Scripts\\python.exe scripts\\backfill_topic_visuals.py --out _preview
    venv\\Scripts\\python.exe scripts\\backfill_topic_visuals.py --apply --figures probe.json
    venv\\Scripts\\python.exe scripts\\backfill_topic_visuals.py --pictures --out _preview
    venv\\Scripts\\python.exe scripts\\backfill_topic_visuals.py --redo-figures --figures probe.json --apply
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import topic_figures, topic_images, topic_pictures, topics, watch_images  # noqa: E402
from app.services.public_markdown import lead_sentences, strip_chat_framing  # noqa: E402

_EXTENSIONS = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp", "image/gif": "gif"}


def card_pictures(db, *, apply: bool, out: str) -> int:
    """The pictures on the Direct-links cards, for every Topic. No model call."""
    failed = 0
    for topic in topics.list_admin_topics(db=db):
        if topic.get("status") not in {"active", "paused"}:
            continue
        try:
            raw = topics.get_topic(topic["id"], db=db) or {}
            pages = topic_pictures.standing_pages(raw, db=db)
            print(f"{topic['slug']}: {len(pages)} eligible pages")
            if apply:
                print(f"    {topic_pictures.refresh_for_topic(topic['id'], db=db)}")
                continue
            notes = {}
            found, _misses = topic_pictures.find_pictures(pages, raw, notes=notes)
            for page in pages:
                print(f"    {notes.get(page['key'], 'not looked at'):<44} {page['url']}")
            for number, picture in enumerate(found, start=1):
                line = f"    picture {number}: {picture['width']}x{picture['height']} from {picture['source_host']}"
                content = picture.get("content")
                if content and out:
                    os.makedirs(out, exist_ok=True)
                    host = "".join(ch if ch.isalnum() else "-" for ch in picture["source_host"])
                    path = os.path.join(out, f"{topic['slug']}-{number}-{host}.webp")
                    with open(path, "wb") as handle:
                        handle.write(content)
                    line += f", {len(content)} bytes, saved {path}"
                print(line)
        except Exception as exc:  # one Topic must not stop the others
            failed += 1
            print(f"    failed: {type(exc).__name__}")
    return 1 if failed else 0


def redo_figures(db, made: dict, *, apply: bool) -> int:
    """New figures for every standing run, in place of the stored ones."""
    failed = 0
    for topic in topics.list_admin_topics(db=db):
        if topic.get("status") not in {"active", "paused"}:
            continue
        standing_id = str(topic.get("accepted_run_id") or topic.get("latest_run_id") or "")
        run = topics.get_run(topic["id"], standing_id, db=db) if standing_id else None
        if not run:
            continue
        try:
            answer = strip_chat_framing(run.get("consensus_md") or "")
            given = (made.get(topic["slug"]) or {}).get("cleaned")
            figures = (
                topic_figures.clean_figures({"figures": given}, answer) if given is not None
                else topic_figures.build(str(topic.get("lead_question") or ""), answer)
            )
            print(f"{topic['slug']}:\n    figures: {[(f['kind'], len(f['items'])) for f in figures]}")
            if apply:
                topic_ref = db.collection(topics.TOPICS_COLLECTION).document(topic["id"])
                topic_ref.collection("runs").document(standing_id).update({"figures": figures})
                print("    figures stored")
        except Exception as exc:  # one Topic must not stop the others
            failed += 1
            print(f"    failed: {type(exc).__name__}")
    return 1 if failed else 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--apply", action="store_true", help="write to Firestore (default: dry run)")
    parser.add_argument("--out", default="", help="dry run: save the found pictures here")
    parser.add_argument("--figures", default="", help="JSON with figures already made for the standing runs")
    parser.add_argument("--redo-figures", action="store_true",
                        help="only the figures, replacing the ones the standing runs have")
    parser.add_argument("--pictures", action="store_true",
                        help="only the pictures on the Direct-links cards (no Judge)")
    args = parser.parse_args(argv)
    made = json.load(open(args.figures, encoding="utf-8")) if args.figures else {}

    from app.core.security import db_firestore as db

    if args.pictures:
        return card_pictures(db, apply=args.apply, out=args.out)
    if args.redo_figures:
        return redo_figures(db, made, apply=args.apply)

    pick = topic_images._default_pick()
    if pick is None:
        print("Judge unavailable (test or mock mode); nothing to do.")
        return 1
    failed = 0
    for topic in topics.list_admin_topics(db=db):
        if topic.get("status") not in {"active", "paused"}:
            continue
        topic_id = topic["id"]
        standing_id = str(topic.get("accepted_run_id") or topic.get("latest_run_id") or "")
        run = topics.get_run(topic_id, standing_id, db=db) if standing_id else None
        if not run:
            continue
        try:
            lead = lead_sentences(run.get("consensus_md") or "", limit=220)
            print(f"{topic['slug']}:\n    lead: {lead!r}")
            if args.apply and lead and topic.get("accepted_lead") != lead:
                db.collection(topics.TOPICS_COLLECTION).document(topic_id).update({"accepted_lead": lead})
                print("    lead stored")
            answer = strip_chat_framing(run.get("consensus_md") or "")
            if run.get("figures"):
                print("    figures: already there")
            else:
                given = (made.get(topic["slug"]) or {}).get("cleaned")
                figures = (
                    topic_figures.clean_figures({"figures": given}, answer) if given is not None
                    else topic_figures.build(str(topic.get("lead_question") or ""), answer)
                )
                print(f"    figures: {[(f['kind'], len(f['items'])) for f in figures]}")
                if args.apply and figures:
                    topic_ref = db.collection(topics.TOPICS_COLLECTION).document(topic_id)
                    topic_ref.collection("runs").document(standing_id).update({"figures": figures})
                    print("    figures stored")
            raw = topics.get_topic(topic_id, db=db) or {}
            sources = list(run.get("evidence") or [])
            if not topic_images.needs_image(raw):
                print("    picture: already there or no tries left")
                continue
            if args.apply:
                outcome = topic_images.refresh_for_topic(topic_id, raw, sources, db=db, pick=pick)
                print(f"    picture: {outcome}")
                continue
            # The dry run calls the Judge for real (same cost as --apply).
            sites, _symbol = topic_images._pick_visual(pick, str(raw.get("lead_question") or ""), sources)
            found, _looked = watch_images.search(sources, str(raw.get("lead_question") or ""), "", sites=sites)
            print(f"    sites={sites} -> "
                  + (f"{found['kind']} from {found['source_host']} ({found['width']}x{found['height']})"
                     if found else "no picture"))
            if found and args.out:
                os.makedirs(args.out, exist_ok=True)
                path = os.path.join(args.out, f"{topic['slug']}.{_EXTENSIONS.get(found['content_type'], 'img')}")
                with open(path, "wb") as handle:
                    handle.write(found["content"])
                print(f"    saved {path}")
        except Exception as exc:  # one Topic must not stop the others
            failed += 1
            print(f"    failed: {type(exc).__name__}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
