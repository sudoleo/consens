"""Prompt-cache hit rate of the Agent's model calls, from their llm_calls receipts.

Read-only: queries and .get() on production Firestore, never a write. Every
paid Agent step leaves a receipt with its measured usage (agent_runs.settle):
``input_tokens`` (all prompt tokens, the cached ones included),
``cached_input_tokens`` (read from the provider's prompt cache) and
``cache_write_tokens`` (written to it). The receipts hold no prompts or answers.

    venv/Scripts/python.exe scripts/cache_hit_rate.py
    venv/Scripts/python.exe scripts/cache_hit_rate.py --days 14 --family anthropic
    venv/Scripts/python.exe scripts/cache_hit_rate.py --exclude-own --json
    venv/Scripts/python.exe scripts/cache_hit_rate.py --days 5 --kind audit --by model

One line per day, model family (``--by model``: model) and kind of call:
``chat`` (the chat model's own steps), ``comparison``, ``judge``, ``audit``
(reviewers), ``source`` (page reads) or ``worker`` (the agent session's kind,
from the receipt's ``session_kind`` since 2026-10-29, else from the session
itself, when the receipt belongs to one). ``--kind`` keeps one kind. Columns:

- calls: settled calls with measured tokens
- input, read, write: prompt tokens, cache reads, cache writes
- hit: read / input
- writing, reading: calls that wrote to / read from the cache
- net (Anthropic only): what caching saved, in prompt tokens at full price.
  A read costs a tenth of the input price, a write a quarter more (five-minute
  cache): net = 0.9 * read - 0.25 * write. Negative: the writes cost more
  than the reads saved.

The technical question needs every call, the operator's own included. With
--exclude-own, the accounts starting with OWN_UID_PREFIXES are left out.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TZ = ZoneInfo("Europe/Berlin")
# The operator's own accounts (Max): kept unless --exclude-own.
OWN_UID_PREFIXES = ("mWKgPU", "XP4WVO", "f8MfuG")
# Anthropic's prices relative to an uncached prompt token (five-minute cache).
READ_SAVING, WRITE_PREMIUM = 0.9, 0.25
FIELDS = ("calls", "input", "read", "write", "writing", "reading")


def family(model) -> str:
    name = model.get("model") if isinstance(model, dict) else model
    return str(name or "?").split("/", 1)[0]


def model_name(model) -> str:
    name = model.get("model") if isinstance(model, dict) else model
    return str(name or "?")


def kind(receipt: dict, agents: dict) -> str:
    if str(receipt.get("step") or "").startswith("completion:"):
        return "chat"
    return str(receipt.get("session_kind") or (agents.get(receipt.get("agent_id") or "") or {}).get("kind")
               or "worker")


def day(value) -> str:
    return value.astimezone(TZ).date().isoformat() if hasattr(value, "astimezone") else "?"


def aggregate(receipts, agents_by_turn, *, by="family", only_kind="") -> dict:
    """(day, family or model, kind) -> counts. ``agents_by_turn``: (chat_id,
    turn_id) -> {agent_id: agent session}. Calls without measured prompt
    tokens (failed before the provider answered, usage unknown) do not count."""
    rows = defaultdict(lambda: dict.fromkeys(FIELDS, 0))
    name_of = model_name if by == "model" else family
    for receipt in receipts:
        usage = receipt.get("usage") or {}
        tokens = usage.get("input_tokens")
        if type(tokens) is not int:
            continue
        agents = agents_by_turn.get((receipt.get("chat_id"), receipt.get("turn_id"))) or {}
        what = kind(receipt, agents)
        if only_kind and what != only_kind:
            continue
        row = rows[(day(receipt.get("created_at")), name_of(receipt.get("model")), what)]
        read, write = usage.get("cached_input_tokens") or 0, usage.get("cache_write_tokens") or 0
        row["calls"] += 1
        row["input"] += tokens
        row["read"] += read
        row["write"] += write
        row["writing"] += bool(write)
        row["reading"] += bool(read)
    return dict(rows)


def totals(rows: dict) -> dict:
    """(family, kind) -> counts over the whole window."""
    out = defaultdict(lambda: dict.fromkeys(FIELDS, 0))
    for (_, name, what), row in rows.items():
        for field in FIELDS:
            out[(name, what)][field] += row[field]
    return dict(out)


def described(name: str, row: dict) -> dict:
    out = {**row, "hit": round(row["read"] / row["input"], 3) if row["input"] else None}
    if family(name) == "anthropic":
        out["net"] = round(READ_SAVING * row["read"] - WRITE_PREMIUM * row["write"])
    return out


def collect(db, since, *, exclude_own=False, family_filter=""):
    """Every Agent receipt created since ``since`` and the agent sessions of
    the turns they belong to (for the kind of each worker call)."""
    from google.cloud.firestore_v1.base_query import FieldFilter
    receipts, agents_by_turn = [], {}
    for user in db.collection("users").list_documents():
        if exclude_own and user.id.startswith(OWN_UID_PREFIXES):
            continue
        mine = [snapshot.to_dict() or {} for snapshot in
                user.collection("llm_calls").where(filter=FieldFilter("created_at", ">=", since)).stream()]
        mine = [r for r in mine if r.get("purpose") == "agent"
                and (not family_filter or family(r.get("model")) == family_filter)]
        turns = {(r.get("chat_id"), r.get("turn_id")) for r in mine
                 if not str(r.get("step") or "").startswith("completion:") and r.get("chat_id") and r.get("turn_id")}
        for chat_id, turn_id in turns:
            agents = (user.collection("chats").document(chat_id).collection("turns").document(turn_id)
                      .collection("agents").stream())
            agents_by_turn[(chat_id, turn_id)] = {agent.id: agent.to_dict() or {} for agent in agents}
        receipts.extend(mine)
    return receipts, agents_by_turn


def table(rows: dict, overall: dict) -> str:
    width = max([10, *(len(name) for _, name, _ in rows), *(len(name) for name, _ in overall)])
    head = f"{'day':<10} {'name':<{width}} {'kind':<10} {'calls':>5} {'input':>10} {'read':>10} {'write':>10} " \
           f"{'hit':>6} {'writing':>7} {'reading':>7} {'net':>9}"
    lines = [head]

    def line(label, name, what, row):
        row = described(name, row)
        hit = "-" if row["hit"] is None else f"{row['hit']:.0%}"
        net = str(row["net"]) if "net" in row else ""
        lines.append(f"{label:<10} {name:<{width}} {what:<10} {row['calls']:>5} {row['input']:>10} {row['read']:>10} "
                     f"{row['write']:>10} {hit:>6} {row['writing']:>7} {row['reading']:>7} {net:>9}")

    for key in sorted(rows):
        line(*key, rows[key])
    lines.append("")
    for key in sorted(overall):
        line("all", *key, overall[key])
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--days", type=int, default=7, help="look back this many days (default 7)")
    parser.add_argument("--family", default="", help="only this model family, e.g. anthropic")
    parser.add_argument("--by", choices=("family", "model"), default="family", help="one line per family or model")
    parser.add_argument("--kind", default="", help="only this kind of call, e.g. audit (the reviewers)")
    parser.add_argument("--exclude-own", action="store_true", help="leave out the operator's own accounts")
    parser.add_argument("--json", action="store_true", help="print JSON instead of a table")
    args = parser.parse_args(argv)
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    from app.core.security import db_firestore as db
    since = datetime.now(timezone.utc) - timedelta(days=args.days)
    receipts, agents_by_turn = collect(db, since, exclude_own=args.exclude_own, family_filter=args.family)
    rows = aggregate(receipts, agents_by_turn, by=args.by, only_kind=args.kind)
    overall = totals(rows)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if args.json:
        print(json.dumps({
            "since": since.isoformat(), "own_accounts": "excluded" if args.exclude_own else "included",
            "days": [{"day": d, args.by: f, "kind": k, **described(f, row)} for (d, f, k), row in sorted(rows.items())],
            "totals": [{args.by: f, "kind": k, **described(f, row)} for (f, k), row in sorted(overall.items())],
        }, indent=1))
    else:
        print(f"Agent receipts since {since.astimezone(TZ):%Y-%m-%d %H:%M} "
              f"(own accounts {'excluded' if args.exclude_own else 'included'})\n")
        print(table(rows, overall))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
