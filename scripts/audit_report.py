"""Audit mode in production: the tables of section 2 and the targets Z1-Z8 of
docs/agent-audit-readiness-2026-10-29.md, from turns, receipts and counters.

Read-only: queries and .get() on production Firestore, never a write.
Method as in that spec (section 8):

- receipts ``users/{uid}/llm_calls`` (``purpose == "agent"``, ``created_at``
  in the window): calls, tokens, cost, the allowance charged
  (``quota_charged``), the session's kind (``session_kind``, since
  2026-10-29) and a reviewer call's ``round`` where they exist;
- turns ``users/{uid}/chats/{chat}/turns/{turn}`` in audit mode
  (``agent_review.mode == "audit"`` or the frozen preference), with their
  sessions (``agents``, reviewers: ``kind == "audit"``) and their work log
  (``answer_fixed``, ``checked``, ``paused``, ``decision`` and the agent's
  ``step`` entries, by time; never their text);
- the anonymous daily counters ``ops_metrics/agent-audit-{day}``
  (agent_audit_metrics), which also count turns whose chats were deleted.

Times: total = turn created until the run finished; to the answer = until
the last ``answer_fixed``; marks after the last word = from there until the
run finished; final round = a reviewer's first receipt after the answer was
fixed until its last one settled; gate wait = the agent's step entry until
``checked``/``paused`` of its gate (or the entry's own ``gate_ms``).
p50 is the median, p90 the nearest rank. Turns whose chat is gone keep only their
receipts: counted apart (``deleted``), audit when a receipt says so
(``session_kind``/``round``), else by the shape of their receipts.

    venv/Scripts/python.exe scripts/audit_report.py --days 5
    venv/Scripts/python.exe scripts/audit_report.py --days 14 --exclude-own --json

The operator's own accounts count unless --exclude-own; the report always
says how many turns are theirs. Nothing printed names an account, a chat or
any text.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import statistics
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TZ = ZoneInfo("Europe/Berlin")
# The operator's own accounts (Max), as in scripts/cache_hit_rate.py.
OWN_UID_PREFIXES = ("mWKgPU", "XP4WVO", "f8MfuG")
REVIEWER_ROUNDS = {"live", "gate", "final", "repair", "hedge"}
FINAL_ROUNDS = {"final", "repair", "hedge"}
TERMINAL_SESSIONS = {"completed", "failed", "stopped"}
# Holds that ended without the user deciding them (Z4, a proxy).
UNDECIDED = {"timeout", "ended", "waiting", "open"}
# The release (spec section 1): turns in all, with three reviewers, and
# workspace runs over ten minutes.
RELEASE = {"turns": 100, "three_reviewers": 30, "long_workspace_runs": 10}


# --- Reading (network) --------------------------------------------------------

def _usage(receipt):
    usage = receipt.get("usage") if isinstance(receipt.get("usage"), dict) else {}
    model = receipt.get("model")
    return {"chat": receipt.get("chat_id"), "turn": receipt.get("turn_id"), "step": str(receipt.get("step") or ""),
            "agent_id": receipt.get("agent_id"), "session_kind": receipt.get("session_kind"),
            "round": receipt.get("round"), "model": model.get("model") if isinstance(model, dict) else model,
            "created_at": receipt.get("created_at"), "settled_at": receipt.get("settled_at"),
            "finished_at": receipt.get("finished_at"), "status": receipt.get("status"),
            "input": usage.get("input_tokens"), "cached": usage.get("cached_input_tokens"),
            "output": usage.get("output_tokens"), "cost": usage.get("estimated_cost_nano_usd"),
            "searches": usage.get("web_search_requests"), "search_hits": receipt.get("search_hits"),
            "quota_charged": receipt.get("quota_charged")}


def _log_entry(entry):
    """A work log entry's time and kind; for a gate its wait, for an agent
    step only how often it searched and how many pages it kept."""
    kept = {key: entry.get(key) for key in ("seq", "at", "actor", "kind", "name", "step")}
    content = entry.get("content")
    if entry.get("kind") == "app" and entry.get("name") in {"checked", "paused"}:
        value = entry.get("gate_ms")
        if value is None and entry.get("format") == "json" and isinstance(content, str):
            try:
                value = (json.loads(content) or {}).get("gate_ms")
            except (ValueError, AttributeError):
                value = None
        kept["gate_ms"] = value if isinstance(value, (int, float)) and not isinstance(value, bool) else None
    elif (entry.get("kind") == "step" and entry.get("actor") == "agent" and isinstance(content, str)
          and not entry.get("ref") and not entry.get("truncated")):
        try:
            step = json.loads(content)
        except ValueError:
            step = None
        if isinstance(step, dict):
            searches = (step.get("usage") or {}).get("web_search_requests")
            kept.update(model=step.get("model"), searches=searches if isinstance(searches, int) else None,
                        hits=len(step.get("sources") or []))
    return kept


def _turn(turn):
    review = turn.get("agent_review") if isinstance(turn.get("agent_review"), dict) else {}
    audit = review.get("audit") if isinstance(review.get("audit"), dict) else {}
    settings = turn.get("agent_settings") if isinstance(turn.get("agent_settings"), dict) else {}
    failure = turn.get("agent_failure") if isinstance(turn.get("agent_failure"), dict) else {}
    reviewers = []
    for item in audit.get("reviewers") or []:
        if isinstance(item, dict):
            model = item.get("model")
            reviewers.append({"model": model.get("model") if isinstance(model, dict) else model,
                              "status": item.get("status"), "rounds": item.get("rounds"),
                              "failure": (item.get("failure") or {}).get("code") if isinstance(item.get("failure"), dict)
                              else None, "final_ms": item.get("final_ms"), "backlog": item.get("backlog")})
    saved_holds = turn.get("agent_holds")
    holds = ([{key: hold.get(key) for key in ("kind", "gate", "ask", "domain", "decision", "seconds")}
              for hold in saved_holds if isinstance(hold, dict)] if isinstance(saved_holds, list) else
             [{"kind": item.get("halt"), "gate": item.get("gate"), "ask": item.get("ask"),
               "domain": bool(item.get("domain")), "decision": item.get("state")}
              for item in turn.get("agent_activity") or [] if isinstance(item, dict) and item.get("kind") == "hold"])
    return {"status": turn.get("status"), "error_code": turn.get("error_code"), "failure": failure.get("code"),
            "created_at": turn.get("created_at"), "completed_at": turn.get("completed_at"),
            "failed_at": turn.get("failed_at"), "updated_at": turn.get("updated_at"),
            "model": settings.get("model"), "preferences": settings.get("agent_preferences") or {},
            "comparison_models": len(settings.get("comparison_models") or {}),
            "review": {"mode": review.get("mode"), "status": review.get("status"), "reviewers": reviewers,
                       "issues": [i.get("code") for i in audit.get("issues") or [] if isinstance(i, dict)]}
            if review else None,
            "vm": bool(turn.get("agent_vm")), "holds": holds}


def collect(db, since, *, exclude_own=False, workers=12):
    """Every Agent receipt since ``since``, every audit turn it belongs to
    (with sessions and log) and the daily counters of the window."""
    from google.cloud.firestore_v1.base_query import FieldFilter
    users = [user for user in db.collection("users").list_documents()
             if not (exclude_own and user.id.startswith(OWN_UID_PREFIXES))]

    def receipts_of(user):
        found = [snapshot.to_dict() or {} for snapshot in
                 user.collection("llm_calls").where(filter=FieldFilter("created_at", ">=", since)).stream()]
        return user, [_usage(r) for r in found if r.get("purpose") == "agent" and r.get("chat_id") and r.get("turn_id")]

    def turn_of(args):
        user, chat, turn_id = args
        ref = user.collection("chats").document(chat).collection("turns").document(turn_id)
        snapshot = ref.get()
        if not snapshot.exists:
            return args, None
        data = snapshot.to_dict() or {}
        info = _turn(data)
        if not ((info["review"] or {}).get("mode") == "audit" or info["preferences"].get("audit") == "on"):
            return args, {**info, "audit": False}
        info["agents"] = [{"id": a.id, **{key: (a.to_dict() or {}).get(key) for key in
                                         ("kind", "status", "created_at", "ended_at")}}
                          for a in ref.collection("agents").stream()]
        info["log"] = [_log_entry(e.to_dict() or {}) for e in ref.collection("work_log").order_by("seq").stream()]
        return args, {**info, "audit": True}

    receipts, keys = [], set()
    with ThreadPoolExecutor(workers) as pool:
        for user, found in pool.map(receipts_of, users):
            own = user.id.startswith(OWN_UID_PREFIXES)
            for receipt in found:
                receipts.append({**receipt, "own": own, "account": user.id})
                keys.add((user, receipt["chat"], receipt["turn"]))
        turns = {}
        for (user, chat, turn_id), info in pool.map(turn_of, sorted(keys, key=lambda k: (k[0].id, k[1], k[2]))):
            turns[(user.id, chat, turn_id)] = info
    days, day = [], since.astimezone(timezone.utc).date()
    while day <= datetime.now(timezone.utc).date():
        snapshot = db.collection("ops_metrics").document(f"agent-audit-{day.isoformat()}").get()
        if snapshot.exists:
            days.append(snapshot.to_dict() or {})
        day += timedelta(days=1)
    return {"receipts": receipts, "turns": turns, "counters": days, "since": since}


# --- Evaluation (offline) -------------------------------------------------------

def _time(value):
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            return _time(datetime.fromisoformat(value.replace("Z", "+00:00")))
        except ValueError:
            return None
    return None


def _seconds(start, end):
    start, end = _time(start), _time(end)
    return (end - start).total_seconds() if start is not None and end is not None and end >= start else None


def quantiles(values):
    """{n, p50 (the median), p90 (nearest rank), max}, None without values."""
    values = sorted(v for v in values if v is not None)
    if not values:
        return {"n": 0, "p50": None, "p90": None, "max": None}
    p90 = values[min(len(values) - 1, int(round(.9 * (len(values) - 1))))]
    return {"n": len(values), "p50": round(statistics.median(values), 1), "p90": round(p90, 1),
            "max": round(values[-1], 1)}


def _round(receipt, fixed_at):
    """A reviewer receipt's round: its own ``round``, else final once the answer was fixed."""
    if receipt.get("round") in REVIEWER_ROUNDS:
        return "final" if receipt["round"] in FINAL_ROUNDS else "live"
    created = _time(receipt.get("created_at"))
    return "final" if fixed_at is not None and created is not None and created >= fixed_at else "live"


def audit_turns(data):
    """One row per audit turn with its receipts sorted into the agent's and
    the reviewers' live and final rounds."""
    by_turn = defaultdict(list)
    for receipt in data["receipts"]:
        by_turn[(receipt["account"], receipt["chat"], receipt["turn"])].append(receipt)
    rows = []
    for key, info in data["turns"].items():
        if not info or not info.get("audit"):
            continue
        receipts = by_turn.get(key, [])
        root = next((r for r in receipts if r["step"] == "completion:0"), {})
        log = info.get("log") or []
        fixed = [_time(e.get("at")) for e in log if e.get("kind") == "app" and e.get("name") == "answer_fixed"]
        fixed_at = fixed[-1] if fixed else None
        sessions = {a["id"]: a for a in info.get("agents") or []}
        calls = []
        for receipt in receipts:
            if receipt["step"].startswith("completion:"):
                calls.append(("agent", receipt))
                continue
            kind = receipt.get("session_kind") or (sessions.get(receipt.get("agent_id")) or {}).get("kind")
            calls.append((f"reviewer_{_round(receipt, fixed_at)}" if kind == "audit" else f"worker_{kind}", receipt))
        pauses = []
        for index, entry in enumerate(log):
            if entry.get("kind") == "app" and entry.get("name") == "paused":
                decision = next((e for e in log[index + 1:] if e.get("kind") == "app" and e.get("name") == "decision"),
                                None)
                pauses.append((entry, decision))
        end = (_time(root.get("finished_at")) or _time(info.get("completed_at")) or _time(info.get("failed_at"))
               or _time(info.get("updated_at")))
        rows.append({"key": key, "own": key[0].startswith(OWN_UID_PREFIXES), "info": info, "calls": calls,
                     "created": _time(info.get("created_at")), "end": end, "fixed": fixed_at, "log": log,
                     "pauses": pauses, "sessions": sessions,
                     "paused_s": sum(_seconds(p.get("at"), d.get("at")) or 0 for p, d in pauses if d)})
    return rows


def _status(info):
    if info.get("status") == "failed" and info.get("error_code") == "cancelled":
        return "cancelled"
    return info.get("status") or "?"


def deleted_turns(data):
    """Turns whose chat is gone, from their receipts: (audit, audit_like, other)."""
    by_turn = defaultdict(list)
    for receipt in data["receipts"]:
        key = (receipt["account"], receipt["chat"], receipt["turn"])
        if key in data["turns"] and data["turns"][key] is None:
            by_turn[key].append(receipt)
    out = Counter()
    for receipts in by_turn.values():
        agents = [r for r in receipts if r["step"].startswith("agent:")]
        if any(r.get("session_kind") == "audit" or r.get("round") in REVIEWER_ROUNDS for r in agents):
            out["audit"] += 1
            continue
        chat = [_time(r.get("settled_at") or r.get("created_at")) for r in receipts if r["step"].startswith("completion:")]
        chat = [t for t in chat if t]
        # A review after the agent's last step is the shape of an audit turn.
        late = chat and any((_time(r.get("created_at")) or chat[0]) >= max(chat) - timedelta(seconds=1) for r in agents)
        out["audit_like" if late else "other"] += 1
    return dict(out)


def _gates(row):
    """Each gate of a turn: (result, wait in seconds)."""
    holds = list(row["info"].get("holds") or [])
    gates, step_at, paused = [], None, 0
    for entry in row["log"]:
        if entry.get("kind") == "step" and entry.get("actor") == "agent":
            step_at = entry.get("at")
            continue
        if entry.get("kind") != "app" or entry.get("name") not in {"checked", "paused"}:
            continue
        hold = None
        if entry["name"] == "paused":
            hold = holds[paused] if paused < len(holds) else None
            paused += 1
            if not (hold and hold.get("gate")):
                continue
        wait = entry["gate_ms"] / 1000 if entry.get("gate_ms") is not None else _seconds(step_at, entry.get("at"))
        result = "go" if entry["name"] == "checked" else "domain" if hold.get("domain") else hold.get("kind") or "halt"
        gates.append((result, wait))
    return gates


def _hold_label(hold):
    if hold.get("ask"):
        return f"ask:{hold['ask']}"
    if hold.get("domain"):
        return "domain"
    return f"gate:{hold.get('kind')}" if hold.get("gate") else str(hold.get("kind") or "?")


def _tokens(rows):
    out = defaultdict(Counter)
    for row in rows:
        for role, receipt in row["calls"]:
            for name in {role, "reviewer" if role.startswith("reviewer_") else role}:
                item = out[name]
                item["calls"] += 1
                for field in ("input", "cached", "output", "cost", "quota_charged"):
                    if isinstance(receipt.get(field), int):
                        item[field] += receipt[field]
    return {role: {"calls": c["calls"], "input": c["input"], "cached_share": round(c["cached"] / c["input"], 3)
                   if c["input"] else None, "output": c["output"], "cost_usd": round(c["cost"] / 1e9, 2),
                   "quota": c["quota_charged"]} for role, c in sorted(out.items())}


def _search(data, rows):
    """Share of searching steps without a kept page, per model: from the
    receipts' ``search_hits`` (every mode, since 2026-10-29), else from the
    agent's complete step entries in audit logs."""
    out = defaultdict(Counter)
    for receipt in data["receipts"]:
        if isinstance(receipt.get("searches"), int) and receipt["searches"] > 0 and isinstance(receipt.get("search_hits"), int):
            item = out[(receipt["model"], "receipts")]
            item["steps"] += 1
            item["without_hits"] += receipt["search_hits"] == 0
    for row in rows:
        for entry in row["log"]:
            if isinstance(entry.get("searches"), int) and entry["searches"] > 0:
                item = out[(entry.get("model"), "work_log")]
                item["steps"] += 1
                item["without_hits"] += entry.get("hits") == 0
    return [{"model": model, "source": source, "steps": c["steps"], "without_hits": c["without_hits"],
             "share": round(c["without_hits"] / c["steps"], 3)} for (model, source), c in sorted(out.items())]


def _counters(days):
    """The daily counters of the window, added up ({field: {key: n}})."""
    total = {}

    def add(target, source):
        for key, value in source.items():
            if isinstance(value, dict):
                add(target.setdefault(key, {}), value)
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                target[key] = target.get(key, 0) + value
    for day in days:
        add(total, {k: v for k, v in day.items() if k not in {"day", "updated_at"}})
    return {"days": sorted(d.get("day") for d in days if d.get("day")), **total}


def _target(target_id, metric, value, target, ok):
    return {"id": target_id, "metric": metric, "value": value, "target": target, "ok": ok}


def report(data):
    rows = audit_turns(data)
    completed = [r for r in rows if r["info"].get("status") == "completed"]
    finished = {id(r) for r in completed}
    reviewers = Counter(len((r["info"]["review"] or {}).get("reviewers") or []) or r["info"]["comparison_models"]
                        for r in rows)
    times = {
        "total": quantiles(_seconds(r["created"], r["end"]) for r in completed),
        "total_without_pauses": quantiles((_seconds(r["created"], r["end"]) or 0) - r["paused_s"]
                                          if _seconds(r["created"], r["end"]) is not None else None for r in completed),
        "to_answer": quantiles(_seconds(r["created"], r["fixed"]) for r in completed),
        "marks_after_last_word": quantiles(_seconds(r["fixed"], r["end"]) for r in completed),
    }
    final_by_model, live_by_model, live_per_turn = defaultdict(list), defaultdict(list), []
    live_total = 0
    # A live round that failed ends its session (agent_audit: a new one goes
    # on), also when its paid reply was only unreadable: the sessions say it.
    live_failed = sum(1 for row in rows for session in row["sessions"].values()
                      if session.get("kind") == "audit" and session.get("status") == "failed"
                      and (row["fixed"] is None or (_time(session.get("created_at")) or row["fixed"]) < row["fixed"]))
    for row in rows:
        finals = defaultdict(list)
        live = 0
        for role, receipt in row["calls"]:
            if role == "reviewer_final":
                finals[receipt["model"]].append(receipt)
            elif role == "reviewer_live":
                live += 1
                live_total += 1
                live_by_model[receipt["model"]].append(_seconds(receipt.get("created_at"), receipt.get("settled_at")))
        live_per_turn.append(live)
        if id(row) in finished:
            for model, receipts in finals.items():
                start = min(_time(r.get("created_at")) for r in receipts)
                stop = max(_time(r.get("settled_at")) or start for r in receipts)
                final_by_model[model].append(_seconds(start, stop))
    times["final_round_by_model"] = {model: quantiles(values) for model, values in sorted(final_by_model.items())}
    times["live_request_by_model"] = {model: quantiles(values) for model, values in sorted(live_by_model.items())}
    gates = [gate for row in rows for gate in _gates(row)]
    holds = [hold for row in rows for hold in row["info"].get("holds") or []]
    reviewer_failures = Counter(item["failure"] for r in rows for item in (r["info"]["review"] or {}).get("reviewers") or []
                                if item.get("failure"))
    review_status = Counter((r["info"]["review"] or {}).get("status") for r in completed)
    tokens = _tokens(rows)
    quota_rows = [(role, receipt) for row in rows for role, receipt in row["calls"]
                  if isinstance(receipt.get("quota_charged"), int)]
    quota_all = sum(receipt["quota_charged"] for _, receipt in quota_rows)
    quota_reviewers = sum(receipt["quota_charged"] for role, receipt in quota_rows if role.startswith("reviewer_"))
    cost_all = sum(receipt.get("cost") or 0 for _, receipt in quota_rows)
    cost_reviewers = sum(receipt.get("cost") or 0 for role, receipt in quota_rows if role.startswith("reviewer_"))
    quota = {"turns": sum(1 for row in rows if any(isinstance(r.get("quota_charged"), int) for _, r in row["calls"])),
             "reviewer_share": round(quota_reviewers / quota_all, 3) if quota_all else None,
             "reviewer_cost_share": round(cost_reviewers / cost_all, 3) if cost_all else None,
             "reviewer_tokens": quota_reviewers, "agent_tokens": quota_all - quota_reviewers}
    succeeded = review_status.get("succeeded", 0)
    reviewed = sum(n for status, n in review_status.items() if status)
    failed_after_answer = sum(1 for r in rows if r["info"].get("status") == "failed" and r["fixed"] is not None)
    undecided = sum(1 for hold in holds if hold.get("decision") in UNDECIDED)
    open_sessions = sum(1 for r in rows if r["end"] is not None for s in r["sessions"].values()
                        if s.get("kind") == "audit" and s.get("status") not in TERMINAL_SESSIONS)
    marks, gate_wait = times["marks_after_last_word"], quantiles(wait for _, wait in gates)
    targets = [
        _target("Z1", "marks after the last word (s)", marks,
                "p50 <= 10, p90 <= 20, max <= 60",
                None if not marks["n"] else marks["p50"] <= 10 and marks["p90"] <= 20 and marks["max"] <= 60),
        _target("Z2", "reviews succeeded of completed audit turns",
                {"succeeded": succeeded, "reviewed": reviewed, "failed": review_status.get("failed", 0),
                 "share": round(succeeded / reviewed, 3) if reviewed else None},
                ">= 98 %, failed <= 0.5 %",
                None if not reviewed else succeeded / reviewed >= .98
                and review_status.get("failed", 0) / reviewed <= .005),
        _target("Z3", "turns failed after the answer was fixed", failed_after_answer, "0", failed_after_answer == 0),
        _target("Z4", "holds that ended without a decision (proxy)", undecided, "0", undecided == 0),
        _target("Z5", "gate wait (s)", gate_wait, "p90 <= 10, never over 20",
                None if not gate_wait["n"] else gate_wait["p90"] <= 10 and gate_wait["max"] <= 20),
        _target("Z6", "reviewer sessions not ended after their turn", open_sessions, "0", open_sessions == 0),
        _target("Z7", "browser loses a running or paused run", None, "0 (smoke, A-L4; not in the data)", None),
        _target("Z8", "reviewers' share of the allowance", quota["reviewer_share"],
                f"Max' decision (cost share {quota['reviewer_cost_share']})", None),
    ]
    long_runs = sum(1 for r in completed if r["info"].get("vm") and (_seconds(r["created"], r["end"]) or 0) > 600)
    return {
        "since": data["since"].isoformat() if isinstance(data.get("since"), datetime) else data.get("since"),
        "data": {"audit_turns": len(rows), "own": sum(r["own"] for r in rows), "other": sum(not r["own"] for r in rows),
                 "deleted": deleted_turns(data), "reviewers_per_turn": dict(sorted(reviewers.items()))},
        "status": {"turns": dict(Counter(_status(r["info"]) for r in rows)),
                   "turn_failures": dict(Counter(r["info"].get("failure") for r in rows
                                                 if _status(r["info"]) in {"failed", "cancelled"})),
                   "reviews": dict(review_status), "reviewer_failures": dict(reviewer_failures),
                   "live_rounds": {"total": live_total, "failed": live_failed}},
        "times": times,
        "live_rounds_per_turn": quantiles(live_per_turn),
        "gate": {"rounds": len(gates), "results": dict(Counter(result for result, _ in gates)), "wait": gate_wait},
        "halts": {"count": len(holds), "by_kind_and_decision": dict(Counter(
                      f"{_hold_label(h)} -> {h.get('decision')}" for h in holds)),
                  "until_decision": quantiles(_seconds(p.get("at"), d.get("at")) for r in rows for p, d in r["pauses"] if d)},
        "tokens": tokens, "quota": quota, "search": _search(data, rows),
        "counters": _counters(data.get("counters") or []),
        "targets": targets,
        "release": {"turns": len(rows), "three_reviewers": reviewers.get(3, 0), "long_workspace_runs": long_runs,
                    "needed": RELEASE},
    }


# --- Output -----------------------------------------------------------------------

def _q(value):
    if not value or not value.get("n"):
        return "n=0"
    return f"n={value['n']} p50={value['p50']} p90={value['p90']} max={value['max']}"


def render(result):
    out = []
    add = out.append
    data = result["data"]
    add(f"Audit turns since {result['since']}: {data['audit_turns']} ({data['own']} own, {data['other']} other); "
        f"deleted chats: {data['deleted'] or 'none'}; reviewers per turn: {data['reviewers_per_turn']}")
    status = result["status"]
    add(f"Status: {status['turns']}; failures {status['turn_failures']}; reviews {status['reviews']}; "
        f"reviewer failures {status['reviewer_failures']}; live or gate rounds failed "
        f"{status['live_rounds']['failed']}/{status['live_rounds']['total']}")
    add("\nTimes, completed turns (s)")
    for name in ("total", "total_without_pauses", "to_answer", "marks_after_last_word"):
        add(f"  {name:<24} {_q(result['times'][name])}")
    for title, key in (("final round", "final_round_by_model"), ("live request", "live_request_by_model")):
        for model, value in result["times"][key].items():
            add(f"  {title:<13} {model:<30} {_q(value)}")
    add(f"  live rounds per turn      {_q(result['live_rounds_per_turn'])}")
    gate = result["gate"]
    add(f"\nGate: {gate['rounds']} rounds {gate['results']}; wait {_q(gate['wait'])}")
    halts = result["halts"]
    add(f"Halts: {halts['count']} {halts['by_kind_and_decision']}; until decided {_q(halts['until_decision'])}")
    add("\nTokens and cost")
    for role, item in result["tokens"].items():
        share = "-" if item["cached_share"] is None else f"{item['cached_share']:.0%}"
        add(f"  {role:<16} calls={item['calls']:<5} input={item['input']:<10} cached={share:<5} "
            f"output={item['output']:<8} cost=${item['cost_usd']:<6} allowance={item['quota']}")
    quota = result["quota"]
    add(f"  allowance ({quota['turns']} turns with quota_charged): reviewers {quota['reviewer_share']} of it, "
        f"{quota['reviewer_cost_share']} of the cost")
    add("\nSearch steps without a kept page")
    for item in result["search"] or [{"model": "no data", "source": "", "steps": 0, "without_hits": 0, "share": None}]:
        add(f"  {item['model']:<30} {item['source']:<9} {item['without_hits']}/{item['steps']} ({item['share']})")
    counters = result["counters"]
    add(f"\nDaily counters (ops_metrics): {counters if counters.get('days') else 'none in the window'}")
    add("\nTargets")
    for target in result["targets"]:
        ok = {True: "ok", False: "MISSED", None: "-"}[target["ok"]]
        value = _q(target["value"]) if isinstance(target["value"], dict) and "n" in target["value"] else target["value"]
        add(f"  {target['id']} {ok:<6} {target['metric']}: {value} (target {target['target']})")
    release = result["release"]
    add(f"\nRelease: {release['turns']}/{release['needed']['turns']} turns, "
        f"{release['three_reviewers']}/{release['needed']['three_reviewers']} with three reviewers, "
        f"{release['long_workspace_runs']}/{release['needed']['long_workspace_runs']} workspace runs over 10 min")
    return "\n".join(out)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--days", type=int, default=7, help="look back this many days (default 7)")
    parser.add_argument("--exclude-own", action="store_true", help="leave out the operator's own accounts")
    parser.add_argument("--json", action="store_true", help="print JSON instead of tables")
    args = parser.parse_args(argv)
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    from app.core.security import db_firestore as db
    since = datetime.now(timezone.utc) - timedelta(days=args.days)
    result = report(collect(db, since, exclude_own=args.exclude_own))
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, indent=1, default=str) if args.json else render(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
