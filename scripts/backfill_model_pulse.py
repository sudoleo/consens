"""Give older Model Pulse votes their run's participants.

Votes before the rate (2026-10-03) stored only the pick. Where the run is
still stored, its compared families can be reconstructed:

* Consensus: the chat turn (or bookmark) that carries the vote's result_id
  lists ``included_models``.
* Agent: the vote's result_id names chat and turn; the turn's saved
  ``agent_review`` names the compared answers.

A vote whose run is gone, or whose stored pick is not among the
reconstructed families, stays without them: it keeps counting in the all-time
pick tally but never enters a rate.

Default is a dry run that only reads. ``--apply`` writes
``participants``/``picked``/``pulse_version`` onto the matched votes
(never touching any other field).

    venv\\Scripts\\python.exe scripts\\backfill_model_pulse.py
    venv\\Scripts\\python.exe scripts\\backfill_model_pulse.py --apply
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import model_pulse, persistence_guard  # noqa: E402


def _hash(uid: str) -> str:
    return hashlib.sha256(str(uid).encode("utf-8")).hexdigest()


def _owner_runs(db, uid: str):
    """result_id -> participants, and (chat, turn) -> agent review, of one user."""
    by_result, agent_turns = {}, {}
    user = db.collection("users").document(uid)
    for chat in user.collection("chats").list_documents():
        for turn in chat.collection("turns").stream():
            data = turn.to_dict() or {}
            if data.get("result_id") and data.get("included_models"):
                by_result[str(data["result_id"])] = list(data["included_models"])
            if data.get("agent_review"):
                agent_turns[(chat.id, turn.id)] = data["agent_review"]
    for bookmark in user.collection("bookmarks").stream():
        data = bookmark.to_dict() or {}
        field = data.get("included_providers") or data.get("included_models") or []
        for key in ("share_result_id", "vote_subject_id"):
            if data.get(key) and field:
                by_result.setdefault(str(data[key]), list(field))
    return by_result, agent_turns


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="write the matched votes")
    args = parser.parse_args(argv)

    from app.core.security import db_firestore as db

    votes = [v for v in db.collection(model_pulse.VOTES_COLLECTION).stream()
             if (v.to_dict() or {}).get("vote_type") == "BestModel"
             and not (v.to_dict() or {}).get("pulse_version")]
    owners = {(v.to_dict() or {}).get("owner_hash") for v in votes}
    uid_by_hash = {}
    for user in db.collection("users").list_documents():
        digest = _hash(user.id)
        if digest in owners:
            uid_by_hash[digest] = user.id

    outcome = collections.Counter()
    updates = []
    runs_cache = {}
    for vote in votes:
        data = vote.to_dict() or {}
        uid = uid_by_hash.get(data.get("owner_hash"))
        source = "agent" if data.get("source") == "agent" else "consensus"
        if not uid:
            outcome[f"{source}: owner gone"] += 1
            continue
        if uid not in runs_cache:
            runs_cache[uid] = _owner_runs(db, uid)
        by_result, agent_turns = runs_cache[uid]
        result_id = str(data.get("result_id") or "")
        field = []
        if source == "agent":
            _, chat_id, turn_id = (result_id.split(":") + ["", "", ""])[:3]
            review = agent_turns.get((chat_id, turn_id))
            field = persistence_guard.agent_best_model_choice(review)[1] if review else []
        else:
            field = by_result.get(result_id) or by_result.get(str(data.get("vote_subject_id") or ""), [])
        shape = model_pulse.participation(field, data.get("model"))
        if not field:
            outcome[f"{source}: run gone"] += 1
        elif not shape:
            outcome[f"{source}: pick not in run"] += 1
        else:
            outcome[f"{source}: matched"] += 1
            updates.append((vote.reference, shape))

    print(f"votes without participants: {len(votes)}")
    for key, count in sorted(outcome.items()):
        print(f"  {key}: {count}")
    if not args.apply:
        entries = [model_pulse._entry({**vote.to_dict(), **shape})
                   for vote in votes for ref, shape in updates if ref.path == vote.reference.path]
        view = model_pulse.build_view([e for e in entries if e])
        print(f"preview, all runs ({view['runs']}, average field {view['average_field']}):")
        for row in view["rows"] + view["sparse"]:
            print(f"  {row['short']:<9} {row['picks']:>4}/{row['runs']:<4} rate {row['rate']}%"
                  f"  fair {row['fair_share']}%  lift {row['lift']}")
        print("dry run: nothing written (use --apply)")
        return 0
    batch, pending = db.batch(), 0
    for ref, shape in updates:
        batch.update(ref, shape)
        pending += 1
        if pending == 400:
            batch.commit()
            batch, pending = db.batch(), 0
    if pending:
        batch.commit()
    print(f"written: {len(updates)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
