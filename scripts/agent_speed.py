"""Tempo of Agent turns, step by step, from their receipts and their activity.

Read-only: queries and .get() on production Firestore, never a write, and no
model call. With --openrouter it also asks OpenRouter for each step's
generation stats (GET /api/v1/generation, metadata of a finished request,
not a model call). Measures every change of docs/agent-speed-plan-2026-11-05.md
before and after its deploy (P0).

    venv/Scripts/python.exe scripts/agent_speed.py --days 2
    venv/Scripts/python.exe scripts/agent_speed.py --days 7 --model terra --summary
    venv/Scripts/python.exe scripts/agent_speed.py --turn 5ce41f --openrouter
    venv/Scripts/python.exe scripts/agent_speed.py --days 7 --exclude-own --json

Every step of the chat model leaves a receipt in ``users/{uid}/llm_calls``
(``step`` "completion:N"; a reviewer's or worker's call is "agent:<id>:N")
with the times of its request (since 2026-10-30, agent_runs.REQUEST_TIMES):
``request_started_at``, ``first_token_at`` and ``stream_ended_at``. The turn
document (``users/{uid}/chats/{chat}/turns/{turn}``) has ``created_at``,
``completed_at``, ``agent_answer_fixed_at`` and the activity, whose tool
entries ("completion:N:<call>/tool") carry ``duration_ms`` for the tools that
measure themselves (vm_exec, browser, ...) and, since 2026-11-05, ``took_ms``
for every call (DelegationLoop._execute). A temporary or deleted chat has no
turn document any more: then only its receipts count.

Per turn (``--summary``: one line per turn) the timeline of the chat model's
steps, in seconds:

- at: when the request left, counted from the turn's creation (without a turn
  document: from the first request)
- dur: request start to the stream's end; ttft: request start to first token
- srch: the step's web searches (they run inside the request); tokens: input,
  cached, output, reasoning
- gap: the stream's end to the next step's request; tools: the measured
  duration of the step's tools in it; rest: gap minus tools, our own overhead.
  A tool without a measured duration (marked ``?``) leaves its time in rest
  (marked ``*``).
- total: turn created to ``completed_at``; answer: to the answer, which is
  ``agent_answer_fixed_at`` when reviewers go on after it, else
  ``completed_at``; span: first request to last stream end (also without a
  turn document)
- pre: turn created to first request; post: last stream end to the answer;
  reviewers after the answer: ``agent_answer_fixed_at`` to ``completed_at``
- worker calls: the turn's receipts of reviewers and workers ("agent:")
- with --openrouter: the endpoint (provider), OpenRouter's latency and
  generation time, and conn: OpenRouter's ``created_at`` minus our request
  start (the way to OpenRouter, clocks of two machines)

Then the aggregates over all turns: p50/p90 of total, answer and span, steps
and searches per turn, pre and post, TTFT and seconds per search (a search
step's duration divided by its searches, its own writing included) per
model, the rest per gap (only gaps whose tools all measured themselves), gaps
by the tools before them, the share of search steps, other steps, tools,
rest, pre and post and the reviewers after the answer in the summed time, and
with --openrouter latency, TTFT and connection per model and endpoint.

Prints numbers, ids shortened to six characters and tool names only: never a
question, answer, command or URL. The technical question needs every turn, the
operator's own included. With --exclude-own, the accounts starting with
OWN_UID_PREFIXES are left out.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import sys
import time
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TZ = ZoneInfo("Europe/Berlin")
# The operator's own accounts (Max), as in scripts/cache_hit_rate.py.
OWN_UID_PREFIXES = ("mWKgPU", "XP4WVO", "f8MfuG")
ID_CHARS = 6
# What the turn document is read for: times and activity, never the answer.
TURN_FIELDS = ("created_at", "completed_at", "agent_answer_fixed_at", "status", "agent_activity")
TOOL_ID = re.compile(r"^completion:(\d+):(.+)/tool$")
OPENROUTER_PAUSE_SECONDS = 0.2


def _time(value):
    return value if isinstance(value, datetime) else None


def _iso(value):
    """OpenRouter's ``created_at`` (ISO text) as an aware datetime."""
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def seconds(start, end):
    start, end = _time(start), _time(end)
    return None if start is None or end is None else (end - start).total_seconds()


def _number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def step_index(step) -> int | None:
    """N of the chat model's step "completion:N", else None."""
    match = re.fullmatch(r"completion:(\d+)", str(step or ""))
    return int(match.group(1)) if match else None


def model_name(model) -> str:
    name = model.get("model") if isinstance(model, dict) else model
    return str(name or "?")


def tool_calls(activity) -> dict:
    """Step index -> the client tools it called: [{"name", "ms"}], ``ms`` None
    when the tool does not measure itself. Web searches run inside the model's
    request (server_tool) and are no gap of ours."""
    calls = {}
    for entry in activity if isinstance(activity, list) else []:
        if not isinstance(entry, dict) or entry.get("kind") != "tool" or entry.get("server_tool"):
            continue
        match = TOOL_ID.match(str(entry.get("id") or ""))
        if not match or match.group(2) == "web_search":
            continue
        # A tool's own duration_ms where it has one, else the time the loop
        # measured for every call (took_ms, since 2026-11-05).
        ms = _number(entry.get("duration_ms"))
        if ms is None:
            ms = _number(entry.get("took_ms"))
        known = calls.get(entry["id"])
        # An entry is merged by its id; keep a measured duration once seen.
        calls[entry["id"]] = {"step": int(match.group(1)), "name": str(entry.get("name") or "?"),
                              "ms": ms if ms is not None and ms >= 0 else (known or {}).get("ms")}
    out = defaultdict(list)
    for call in calls.values():
        out[call["step"]].append({"name": call["name"], "ms": call["ms"]})
    return dict(out)


def timeline(uid: str, chat_id: str, turn_id: str, receipts: list, turn: dict | None) -> dict:
    """One turn's chat-model steps, the gaps between them and its totals.
    Keys starting with "_" stay internal (times, generation ids)."""
    chat = sorted(((step_index(r.get("step")), r) for r in receipts if step_index(r.get("step")) is not None),
                  key=lambda item: (item[0], _time(item[1].get("request_started_at")) or datetime.min.replace(
                      tzinfo=timezone.utc)))
    turn = turn if isinstance(turn, dict) else None
    created = _time((turn or {}).get("created_at"))
    first = _time(chat[0][1].get("request_started_at")) if chat else None
    origin = created or first
    calls = tool_calls((turn or {}).get("agent_activity"))
    steps = []
    for index, receipt in chat:
        usage = receipt.get("usage") if isinstance(receipt.get("usage"), dict) else {}
        started, token, ended = (_time(receipt.get(field)) for field in
                                 ("request_started_at", "first_token_at", "stream_ended_at"))
        searches = _number(usage.get("web_search_requests"))
        steps.append({
            "step": index, "model": model_name(receipt.get("model")), "status": receipt.get("status"),
            "at": seconds(origin, started), "duration": seconds(started, ended), "ttft": seconds(started, token),
            "searches": int(searches) if searches else 0,
            **{name: _number(usage.get(field)) for name, field in (
                ("input", "input_tokens"), ("cached", "cached_input_tokens"), ("output", "output_tokens"),
                ("reasoning", "reasoning_tokens"))},
            "tools": [call["name"] for call in calls.get(index, [])],
            "unmeasured": sum(1 for call in calls.get(index, []) if call["ms"] is None),
            "gap": None, "tool_s": None, "rest": None,
            "_started": started, "_ended": ended, "_generation": receipt.get("generation_id"),
            "_calls": calls.get(index, []),
        })
    for step, following in zip(steps, steps[1:]):
        step["gap"] = seconds(step["_ended"], following["_started"])
        step["tool_s"] = sum(call["ms"] for call in calls.get(step["step"], []) if call["ms"] is not None) / 1000
        if step["gap"] is not None:
            step["rest"] = step["gap"] - step["tool_s"]
    last = steps[-1]["_ended"] if steps else None
    completed, fixed = _time((turn or {}).get("completed_at")), _time((turn or {}).get("agent_answer_fixed_at"))
    # The answer stands once it is fixed (reviewers still at work, hand_over)
    # or, without reviewers, once the turn completed.
    answered = fixed or completed
    gaps = [step for step in steps if step["gap"] is not None]
    return {
        "account": uid[:ID_CHARS], "own": uid.startswith(OWN_UID_PREFIXES), "chat": chat_id[:ID_CHARS],
        "turn": turn_id[:ID_CHARS], "document": turn is not None, "status": (turn or {}).get("status"),
        "started": (origin.astimezone(TZ).strftime("%Y-%m-%d %H:%M:%S") if origin else "?"),
        "models": list(dict.fromkeys(step["model"] for step in steps)),
        "total": seconds(created, completed), "answer": seconds(created, answered), "span": seconds(first, last),
        "pre": seconds(created, first), "post": seconds(last, answered),
        "after_answer": seconds(fixed, completed) if fixed else None,
        "steps": len(steps), "searches": sum(step["searches"] for step in steps),
        "worker_calls": sum(1 for r in receipts if str(r.get("step") or "").startswith("agent:")),
        "search_s": sum(step["duration"] or 0 for step in steps if step["searches"]),
        "other_s": sum(step["duration"] or 0 for step in steps if not step["searches"]),
        "tool_s": sum(step["tool_s"] or 0 for step in gaps),
        "rest_s": sum(step["rest"] or 0 for step in gaps),
        "step_list": steps, "_created": created,
    }


def percentile(values, q: float):
    """Linear interpolation between the closest ranks (numpy's default)."""
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    position = (len(values) - 1) * q
    low = int(position)
    high = min(low + 1, len(values) - 1)
    return values[low] + (values[high] - values[low]) * (position - low)


def stats(values) -> dict:
    values = [v for v in values if v is not None]
    return {"n": len(values), "p50": percentile(values, .5), "p90": percentile(values, .9),
            "sum": sum(values) if values else 0}


def tool_key(step: dict) -> str:
    return "+".join(sorted(set(step["tools"]))) or "(none)"


def aggregate(turns: list) -> dict:
    """p50/p90 over every turn and step; ``turns`` from ``timeline``."""
    steps = [step for turn in turns for step in turn["step_list"]]
    gaps = [step for step in steps if step["gap"] is not None]
    measured = [step for step in gaps if not step["unmeasured"]]
    by_model, per_search, by_tool, by_provider = defaultdict(list), defaultdict(list), defaultdict(list), \
        defaultdict(list)
    searches = Counter()
    for step in steps:
        by_model[step["model"]].append(step["ttft"])
        if step["searches"] and step["duration"] is not None:
            per_search[step["model"]].append(step["duration"] / step["searches"])
            searches[step["model"]] += step["searches"]
        if isinstance(step.get("openrouter"), dict) and step["openrouter"].get("provider"):
            by_provider[(step["model"], step["openrouter"]["provider"])].append(step)
    for step in gaps:
        by_tool[tool_key(step)].append(step)
    parts = {"search steps": sum(t["search_s"] for t in turns), "other steps": sum(t["other_s"] for t in turns),
             "tools": sum(t["tool_s"] for t in turns), "rest": sum(t["rest_s"] for t in turns),
             "pre and post": sum((t["pre"] or 0) + (t["post"] or 0) for t in turns),
             "reviewers after the answer": sum(t["after_answer"] or 0 for t in turns)}
    whole = sum(parts.values())
    return {
        "turns": len(turns), "with_document": sum(1 for t in turns if t["document"]), "steps": len(steps),
        "total": stats(t["total"] for t in turns), "answer": stats(t["answer"] for t in turns),
        "span": stats(t["span"] for t in turns), "steps_per_turn": stats(t["steps"] for t in turns),
        "searches_per_turn": stats(t["searches"] for t in turns),
        "pre": stats(t["pre"] for t in turns), "post": stats(t["post"] for t in turns),
        "after_answer": stats(t["after_answer"] for t in turns),
        "gap": stats(step["gap"] for step in gaps),
        "rest_per_gap": {**stats(step["rest"] for step in measured), "unmeasured_gaps": len(gaps) - len(measured)},
        "ttft_by_model": {model: stats(values) for model, values in sorted(by_model.items())},
        "seconds_per_search_by_model": {model: {**stats(values), "searches": searches[model]}
                                        for model, values in sorted(per_search.items())},
        "gaps_by_tool": {key: {**stats(step["gap"] for step in items),
                               "rest_p50": percentile([s["rest"] for s in items if not s["unmeasured"]], .5)}
                         for key, items in sorted(by_tool.items(), key=lambda item: -sum(s["gap"] for s in item[1]))},
        "shares": {name: {"s": value, "share": value / whole if whole else None} for name, value in parts.items()},
        "openrouter_by_provider": {f"{model} @ {provider}": {
            "latency": stats(s["openrouter"].get("latency") for s in items),
            "connection": stats(s["openrouter"].get("connection") for s in items),
            "ttft": stats(s["ttft"] for s in items)} for (model, provider), items in sorted(by_provider.items())},
    }


def generation_stats(data: dict, request_started) -> dict:
    """What a step's OpenRouter generation says about its endpoint and time.
    ``latency`` and ``generation_time`` come in milliseconds."""
    latency, generation = _number(data.get("latency")), _number(data.get("generation_time"))
    return {"provider": data.get("provider_name"),
            "latency": latency / 1000 if latency is not None else None,
            "generation": generation / 1000 if generation is not None else None,
            "connection": seconds(request_started, _iso(data.get("created_at")))}


def fetch_generations(turns: list, api_key: str, *, client=None, pause: float = OPENROUTER_PAUSE_SECONDS) -> int:
    """Adds ``openrouter`` to every step with a generation id; a failed
    lookup leaves ``{"error": ...}`` and the next one goes on. Returns the
    number of lookups."""
    from app.core.openrouter_contract import OPENROUTER_BASE_URL, openrouter_headers
    import httpx
    own = client is None
    client = client or httpx.Client(timeout=20)
    lookups = 0
    try:
        for turn in turns:
            for step in turn["step_list"]:
                if not step.get("_generation"):
                    continue
                if lookups:
                    time.sleep(pause)
                lookups += 1
                try:
                    response = client.get(f"{OPENROUTER_BASE_URL}/generation", params={"id": step["_generation"]},
                                          headers=openrouter_headers(api_key))
                    if response.status_code != 200:
                        step["openrouter"] = {"error": response.status_code}
                        continue
                    step["openrouter"] = generation_stats((response.json() or {}).get("data") or {}, step["_started"])
                except Exception as exc:
                    step["openrouter"] = {"error": type(exc).__name__}
    finally:
        if own:
            client.close()
    return lookups


def collect(db, since, *, exclude_own=False, turn_prefix="", model="", workers: int = 16) -> list:
    """Every Agent turn with a chat-model receipt created since ``since``:
    its receipts and its turn document (only TURN_FIELDS; None if gone)."""
    from google.cloud.firestore_v1.base_query import FieldFilter

    def of(user):
        if exclude_own and user.id.startswith(OWN_UID_PREFIXES):
            return []
        by_turn = defaultdict(list)
        for snapshot in user.collection("llm_calls").where(filter=FieldFilter("created_at", ">=", since)).stream():
            receipt = snapshot.to_dict() or {}
            chat_id, turn_id = receipt.get("chat_id"), receipt.get("turn_id")
            if receipt.get("purpose") == "agent" and chat_id and turn_id and str(turn_id).startswith(turn_prefix):
                by_turn[(chat_id, turn_id)].append(receipt)
        found = []
        for (chat_id, turn_id), receipts in by_turn.items():
            chat = [r for r in receipts if step_index(r.get("step")) is not None]
            if not chat or (model and not any(model in model_name(r.get("model")) for r in chat)):
                continue
            snapshot = (user.collection("chats").document(chat_id).collection("turns").document(turn_id)
                        .get(field_paths=list(TURN_FIELDS)))
            found.append((user.id, chat_id, turn_id, receipts, snapshot.to_dict() if snapshot.exists else None))
        return found

    out = []
    with ThreadPoolExecutor(workers) as pool:
        for found in pool.map(of, db.collection("users").list_documents()):
            out.extend(found)
    return out


def _s(value, digits=1) -> str:
    return "?" if value is None else f"{value:.{digits}f}"


def _n(value) -> str:
    return "?" if value is None else str(int(value))


def turn_table(turn: dict, *, openrouter=False) -> str:
    head = (f"turn {turn['turn']}  chat {turn['chat']}  account {turn['account']}{' own' if turn['own'] else ''}  "
            f"{turn['started']}  {', '.join(turn['models'])}  "
            f"{turn['status'] or ('no turn document' if not turn['document'] else '?')}")
    after = turn["after_answer"]
    totals = (f"  total {_s(turn['total'])} s  answer {_s(turn['answer'])} s  span {_s(turn['span'])} s  "
              f"pre {_s(turn['pre'], 2)} s  post {_s(turn['post'], 2)} s  "
              + (f"reviewers after the answer {_s(after)} s  " if after is not None else "")
              + f"steps {turn['steps']}  searches {turn['searches']}  worker calls {turn['worker_calls']}")
    lines = [head, totals,
             f"  {'step':>4} {'at':>6} {'dur':>6} {'ttft':>5} {'srch':>4} {'input':>7} {'cached':>7} {'output':>6} "
             f"{'reason':>6} | " + (f"{'provider':<18} {'lat':>5} {'gen':>5} {'conn':>5} | " if openrouter else "")
             + f"{'gap':>5} {'tools':>5} {'rest':>6}  tools after the step"]
    for step in turn["step_list"]:
        names = ", ".join(call["name"] + ("?" if call["ms"] is None else "") for call in step["_calls"]) or "-"
        rest = _s(step["rest"], 2) + ("*" if step["unmeasured"] and step["rest"] is not None else " ")
        line = (f"  {step['step']:>4} {_s(step['at']):>6} {_s(step['duration']):>6} {_s(step['ttft']):>5} "
                f"{step['searches']:>4} {_n(step['input']):>7} {_n(step['cached']):>7} {_n(step['output']):>6} "
                f"{_n(step['reasoning']):>6} | ")
        if openrouter:
            info = step.get("openrouter") or {}
            if "error" in info:
                line += f"{'lookup failed: ' + str(info['error']):<36} | "
            else:
                line += (f"{str(info.get('provider') or '?')[:18]:<18} {_s(info.get('latency'), 2):>5} "
                         f"{_s(info.get('generation'), 1):>5} {_s(info.get('connection'), 2):>5} | ")
        lines.append(line + f"{_s(step['gap'], 2):>5} {_s(step['tool_s'], 1):>5} {rest:>6}  {names}")
    return "\n".join(lines)


def summary_table(turns: list) -> str:
    lines = [f"{'turn':<7} {'account':<10} {'started':<19} {'model':<28} {'total':>6} {'answer':>6} {'pre':>5} "
             f"{'post':>5} {'steps':>5} {'srch':>4} {'search':>6} {'other':>6} {'tools':>6} {'rest':>6}"]
    for turn in turns:
        lines.append(
            f"{turn['turn']:<7} {turn['account'] + (' own' if turn['own'] else ''):<10} {turn['started']:<19} "
            f"{(turn['models'][0] if turn['models'] else '?')[:28]:<28} {_s(turn['total']):>6} {_s(turn['answer']):>6} "
            f"{_s(turn['pre'], 2):>5} {_s(turn['post'], 2):>5} {turn['steps']:>5} {turn['searches']:>4} "
            f"{_s(turn['search_s']):>6} {_s(turn['other_s']):>6} {_s(turn['tool_s']):>6} {_s(turn['rest_s']):>6}")
    return "\n".join(lines)


def aggregate_table(agg: dict) -> str:
    def row(label, value, digits=1, extra=""):
        return (f"  {label:<34} {value['n']:>5} {_s(value['p50'], digits):>8} {_s(value['p90'], digits):>8} "
                f"{_s(value['sum'], 1):>9}{extra}")

    head = f"  {'':<34} {'n':>5} {'p50':>8} {'p90':>8} {'sum':>9}"
    lines = [f"Turns {agg['turns']} ({agg['with_document']} with turn document), chat steps {agg['steps']}", "", head,
             row("total s (created to completed)", agg["total"]),
             row("answer s (created to the answer)", agg["answer"]),
             row("span s (first request to last end)", agg["span"]),
             row("steps per turn", agg["steps_per_turn"]), row("searches per turn", agg["searches_per_turn"]),
             row("pre s", agg["pre"], 2), row("post s (to the answer)", agg["post"], 2),
             row("reviewers after the answer s", agg["after_answer"], 1), row("gap s", agg["gap"], 2),
             row("rest per gap s (tools measured)", agg["rest_per_gap"], 2,
                 f"   ({agg['rest_per_gap']['unmeasured_gaps']} gaps with unmeasured tools left out)"),
             "", "TTFT s by model", head]
    lines += [row(model, value, 2) for model, value in agg["ttft_by_model"].items()]
    lines += ["", "Seconds per search by model (search step's duration / its searches)",
              head + f" {'searches':>9}"]
    lines += [row(model, value, 1, f" {value['searches']:>9}") for model, value in
              agg["seconds_per_search_by_model"].items()]
    lines += ["", "Gaps by the tools before them (rest p50: gaps whose tools all measured themselves)",
              head + f" {'rest p50':>9}"]
    lines += [row(key, value, 2, f" {_s(value['rest_p50'], 2):>9}") for key, value in agg["gaps_by_tool"].items()]
    lines += ["", "Shares of the summed time", f"  {'':<34} {'s':>9} {'share':>7}"]
    lines += [f"  {name:<34} {value['s']:>9.1f} {'-' if value['share'] is None else format(value['share'], '.0%'):>7}"
              for name, value in agg["shares"].items()]
    if agg["openrouter_by_provider"]:
        lines += ["", "OpenRouter by model and endpoint (latency: OpenRouter's; ttft: ours; conn: to OpenRouter)",
                  f"  {'':<52} {'n':>4} {'lat p50':>8} {'lat p90':>8} {'ttft p50':>8} {'ttft p90':>8} "
                  f"{'conn p50':>8} {'conn p90':>8}"]
        for key, value in agg["openrouter_by_provider"].items():
            lines.append(f"  {key[:52]:<52} {value['ttft']['n']:>4} {_s(value['latency']['p50'], 2):>8} "
                         f"{_s(value['latency']['p90'], 2):>8} {_s(value['ttft']['p50'], 2):>8} "
                         f"{_s(value['ttft']['p90'], 2):>8} {_s(value['connection']['p50'], 2):>8} "
                         f"{_s(value['connection']['p90'], 2):>8}")
    return "\n".join(lines)


def public(turn: dict) -> dict:
    """A turn without its internal keys (times, generation ids), for JSON."""
    out = {key: value for key, value in turn.items() if not key.startswith("_") and key != "step_list"}
    out["step_list"] = [{key: value for key, value in step.items() if not key.startswith("_")}
                        for step in turn["step_list"]]
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--days", type=float, default=7, help="look back this many days (default 7)")
    parser.add_argument("--turn", default="", help="only the turn whose id starts with this")
    parser.add_argument("--model", default="", help="only turns whose chat model contains this, e.g. terra")
    parser.add_argument("--summary", action="store_true", help="one line per turn instead of its timeline")
    parser.add_argument("--openrouter", action="store_true",
                        help="add each step's endpoint and times from OpenRouter (no model call)")
    parser.add_argument("--exclude-own", action="store_true", help="leave out the operator's own accounts")
    parser.add_argument("--json", action="store_true", help="print JSON instead of tables")
    args = parser.parse_args(argv)
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    from app.core.security import db_firestore as db
    since = datetime.now(timezone.utc) - timedelta(days=args.days)
    found = collect(db, since, exclude_own=args.exclude_own, turn_prefix=args.turn, model=args.model)
    turns = sorted((timeline(*item) for item in found),
                   key=lambda turn: turn["_created"] or (turn["step_list"][0]["_started"] if turn["step_list"]
                                                         else None) or since)
    if args.openrouter:
        key = os.environ.get("OPENROUTER_API_KEY", "")
        if not key:
            print("OPENROUTER_API_KEY is missing in .env", file=sys.stderr)
            return 2
        fetch_generations(turns, key)
    agg = aggregate(turns)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if args.json:
        print(json.dumps({"since": since.isoformat(), "own_accounts": "excluded" if args.exclude_own else "included",
                          "turns": [public(turn) for turn in turns], "aggregate": agg}, indent=1, default=str))
        return 0
    print(f"Agent turns since {since.astimezone(TZ):%Y-%m-%d %H:%M} "
          f"(own accounts {'excluded' if args.exclude_own else 'included'})\n")
    if not turns:
        print("No Agent turn with a chat-model receipt in this window.")
        return 0
    if args.summary:
        print(summary_table(turns))
    else:
        for turn in turns:
            print(turn_table(turn, openrouter=args.openrouter))
            print()
        if any(step["unmeasured"] for turn in turns for step in turn["step_list"]):
            print("?: the tool measures no duration of its own; *: its time stays in rest\n")
    print()
    print(aggregate_table(agg))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
