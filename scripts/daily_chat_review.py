"""Read-only daily review of external users' Agent chats (scheduled task consens-chat-review).

Reads production Firestore (queries and .get() only, never a write), Firebase
Auth (to leave out the operator's own accounts by e-mail) and the Render log
API. The only files it writes are the task state next to the task's SKILL.md.
Reviewing stored conversations to find errors and improve the service is
covered by the privacy notice since 2026-10-17 (section 2).

The scheduled task runs unattended, so every step is one fixed command that
.claude/settings.local.json allows without a prompt:

    venv/Scripts/python.exe scripts/daily_chat_review.py collect
    venv/Scripts/python.exe scripts/daily_chat_review.py save

collect   every turn of an external account since the last saved run (the
          first run looks back 26 hours) as compact JSON: question, how the
          agent handled it (phases, models, failures, answer check), answer
          excerpt, cost; plus counted server warnings of the same window.
          Users appear as pseudonyms (U + hash), never with e-mail or ID.
save      stores how far collect got, so the next run starts there.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import statistics
import sys
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

STATE_DIR = Path.home() / ".claude" / "scheduled-tasks" / "consens-chat-review"
STATE_FILE = STATE_DIR / "state.json"
PENDING_FILE = STATE_DIR / "pending.json"
# The operator's own accounts (Max): never part of the review.
OWN_EMAIL_MARKERS = ("maxl.plack", "ml.plack", "nodon")
RENDER_SERVICE = "srv-cva01khc1ekc738oe7e0"
TZ = ZoneInfo("Europe/Berlin")
FIRST_LOOKBACK_HOURS = 26
MAX_TURNS = 40
QUESTION_CHARS = 700
ANSWER_CHARS = 500
JUDGE_TIMEOUT_SECONDS = 85


def _env():
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")


def pseudonym(uid: str) -> str:
    return "U" + hashlib.sha256(f"consens-review:{uid}".encode()).hexdigest()[:5]


def local(value) -> str:
    return value.astimezone(TZ).strftime("%d.%m. %H:%M:%S") if hasattr(value, "astimezone") else "-"


def seconds(a, b):
    return round((b - a).total_seconds()) if hasattr(a, "astimezone") and hasattr(b, "astimezone") else None


def clip(text, limit):
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    return text if len(text) <= limit else text[:limit - 1] + "…"


def external_accounts():
    """uid -> (created, provider ids) for every account that is not the operator's."""
    from firebase_admin import auth
    accounts, own = {}, 0
    for user in auth.list_users().iterate_all():
        email = (user.email or "").lower()
        if any(marker in email for marker in OWN_EMAIL_MARKERS):
            own += 1
            continue
        created = datetime.fromtimestamp((user.user_metadata.creation_timestamp or 0) / 1000, timezone.utc)
        accounts[user.uid] = (created, [p.provider_id for p in user.provider_data])
    return accounts, own


def model_name(model) -> str:
    name = model.get("model") if isinstance(model, dict) else model
    return str(name or "?").split("/")[-1]


def turn_flow(turn: dict, steps: list, agents: dict) -> dict:
    """How the agent handled the turn, from its receipts (content-free)."""
    t0 = turn.get("created_at")
    for step in steps:
        step["kind"] = "chat" if str(step.get("step", "")).startswith("completion") else (
            (agents.get(step.get("agent_id") or "") or {}).get("kind") or "other")
    steps.sort(key=lambda s: s.get("created_at") or t0)
    chat = [s for s in steps if s["kind"] == "chat"]
    comparison = [s for s in steps if s["kind"] == "comparison"]
    judges = [s for s in steps if s["kind"] == "judge"]
    flow = {"steps": len(steps), "chat_model": model_name(chat[0].get("model")) if chat else None}
    if comparison:
        c0 = min(s["created_at"] for s in comparison)
        ended = [s for s in comparison if s.get("settled_at")]
        if ended:
            c1 = max(s["settled_at"] for s in ended)
            flow["comparison_seconds"] = seconds(c0, c1)
            slowest = max(ended, key=lambda s: s["settled_at"])
            flow["slowest_model"] = f"{model_name(slowest.get('model'))} {seconds(slowest['created_at'], slowest['settled_at'])}s"
        flow["comparison_models"] = sorted({model_name(s.get("model")) for s in comparison})
        flow["comparison_failures"] = [f"{model_name(s.get('model'))}: {s.get('status')} {s.get('finish_reason') or ''}".strip()
                                       for s in comparison if s.get("status") != "succeeded"]
        writer = [s for s in chat if s.get("created_at") and s["created_at"] >= (max((s2.get("settled_at") or c0) for s2 in comparison))]
        if writer and writer[-1].get("settled_at"):
            flow["writer_seconds"] = seconds(writer[0]["created_at"], writer[-1]["settled_at"])
            answer_end = writer[-1]["settled_at"]
            late = [s for s in judges if s.get("settled_at") and s["settled_at"] > answer_end]
            if late:
                flow["check_after_answer_seconds"] = seconds(answer_end, max(s["settled_at"] for s in late))
    if judges:
        flow["judge_calls"] = len(judges)
        flow["judge_timeouts"] = sum(1 for s in judges if s.get("settled_at") and s.get("status") != "succeeded"
                                     and seconds(s["created_at"], s["settled_at"]) >= JUDGE_TIMEOUT_SECONDS)
        flow["judge_models"] = dict(Counter(model_name(s.get("model")) for s in judges))
    usage = turn.get("agent_usage") or {}
    flow["cost_usd"] = round((usage.get("estimated_cost_nano_usd") or 0) / 1e9, 3)
    flow["web_searches"] = usage.get("web_search_requests") or 0
    flow["total_seconds"] = seconds(t0, turn.get("completed_at") or turn.get("failed_at") or turn.get("updated_at"))
    return flow


def review_summary(turn: dict) -> dict:
    review = turn.get("agent_review") or {}
    out = {"status": review.get("status")}
    issues = [issue.get("code") for check in review.get("checks") or [] for issue in check.get("issues") or []]
    if issues:
        out["issues"] = sorted(set(issues))
    for check in review.get("checks") or []:
        agreement = (check.get("differences_data") or {}).get("agreement") or {}
        if agreement:
            out["agreement"] = {k: agreement.get(k) for k in ("level", "score", "major_contradictions", "coverage_percent")}
    comparisons = review.get("comparisons") or []
    if comparisons:
        out["compare_task"] = clip(comparisons[0].get("question"), 400)
        out["answers_in_comparison"] = len(comparisons[0].get("answers") or [])
        failed = [f"{m.get('label')}: {(m.get('failure') or {}).get('code')}" for m in comparisons[0].get("failed_models") or []]
        if failed:
            out["failed_models"] = failed
    return out


def render_warnings(start: datetime, end: datetime) -> dict:
    """WARNING/ERROR lines of the app log in the window, counted by pattern."""
    key = os.environ.get("RENDER_API_KEY", "")
    if not key:
        return {"unavailable": "RENDER_API_KEY missing"}
    headers = {"Authorization": f"Bearer {key}", "Accept": "application/json"}
    try:
        service = json.load(urlopen(Request(f"https://api.render.com/v1/services/{RENDER_SERVICE}", headers=headers), timeout=30))
        counts, cursor = Counter(), start.isoformat()
        for _ in range(60):
            query = {"ownerId": service["ownerId"], "resource": RENDER_SERVICE, "startTime": cursor,
                     "endTime": end.isoformat(), "limit": 100, "direction": "forward", "level": "warning,error"}
            data = json.load(urlopen(Request("https://api.render.com/v1/logs?" + urlencode(query), headers=headers), timeout=60))
            for row in data.get("logs") or []:
                message = str(row.get("message") or "")
                if " WARNING " not in message and " ERROR " not in message and "Traceback" not in message:
                    continue
                pattern = re.sub(r"\[corr=[^\]]*\]|\d+", "#", message.split(": ", 1)[-1])[:110]
                counts[pattern] += 1
            if not data.get("hasMore"):
                break
            cursor = data.get("nextStartTime")
        return dict(counts.most_common(15))
    except Exception as exc:  # the review still runs without the log
        return {"unavailable": type(exc).__name__}


def cmd_collect(args) -> int:
    _env()
    from app.core.security import db_firestore as db
    now = datetime.now(timezone.utc)
    state = load_json(STATE_FILE)
    since = (datetime.fromisoformat(state["last_seen"]) if state.get("last_seen") and not args.hours
             else now - timedelta(hours=args.hours or FIRST_LOOKBACK_HOURS))
    accounts, own = external_accounts()
    turns, newest = [], since
    for uid, (created, providers) in accounts.items():
        user = db.collection("users").document(uid)
        chats = list(user.collection("chats").where("updated_at", ">", since).stream())
        if not chats:
            continue
        calls = None
        for chat in chats:
            chat_data = chat.to_dict() or {}
            previous = None
            for doc in sorted(chat.reference.collection("turns").where("created_at", ">", since).stream(),
                              key=lambda d: (d.to_dict() or {}).get("created_at")):
                turn = doc.to_dict() or {}
                if calls is None:
                    calls = [c.to_dict() for c in user.collection("llm_calls").where("created_at", ">", since).stream()]
                steps = [dict(c) for c in calls if c.get("turn_id") == doc.id]
                agents = {a.id: a.to_dict() or {} for a in doc.reference.collection("agents").stream()} if steps else {}
                created_at = turn.get("created_at")
                newest = max(newest, created_at) if hasattr(created_at, "astimezone") else newest
                failure = (turn.get("agent_failure") or {}).get("code")
                entry = {
                    "user": pseudonym(uid), "time": local(created_at),
                    "new_account": created >= since, "sign_in": providers,
                    "chat": hashlib.sha256(chat.id.encode()).hexdigest()[:6], "position": turn.get("position"),
                    "chat_title": clip(chat_data.get("title"), 80),
                    "mode": turn.get("execution_mode"), "status": turn.get("status"),
                    "error": turn.get("error_code"), "failure": failure,
                    "question": clip(turn.get("question"), QUESTION_CHARS),
                    "answer_chars": len(turn.get("assistant_response") or turn.get("consensus") or ""),
                    "answer_start": clip(turn.get("assistant_response") or turn.get("consensus"), ANSWER_CHARS),
                    "settings": {k: (turn.get("agent_settings") or {}).get(k) for k in ("label", "reasoning_effort", "answer_mode")},
                    "flow": turn_flow(turn, steps, agents),
                    "check": review_summary(turn),
                }
                if previous and previous.get("question") == turn.get("question"):
                    entry["repeated_question_after_seconds"] = seconds(previous.get("created_at"), created_at)
                previous = turn
                turns.append((created_at, entry))
    turns.sort(key=lambda item: item[0])
    shown = [entry for _, entry in turns][-MAX_TURNS:]
    totals = [e["flow"]["total_seconds"] for e in shown if e["flow"].get("total_seconds") is not None]
    digest = {
        "window": {"from": local(since), "to": local(now)},
        "own_accounts_left_out": own,
        "external_users": len({e["user"] for _, e in turns}),
        "new_accounts_in_window": sum(1 for created, _ in accounts.values() if created >= since),
        "turns": len(turns), "turns_shown": len(shown),
        "failed_turns": sum(1 for _, e in turns if e["status"] == "failed"),
        "median_total_seconds": statistics.median(totals) if totals else None,
        "cost_usd": round(sum(e["flow"]["cost_usd"] for _, e in turns), 3),
        "server_warnings": render_warnings(since, now),
        "turn_list": shown,
    }
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(digest, ensure_ascii=False, indent=1, default=str))
    save_json(PENDING_FILE, {"last_seen": max(newest, since).isoformat(), "collected_at": now.isoformat()})
    return 0


def cmd_save(_args) -> int:
    pending = load_json(PENDING_FILE)
    if not pending.get("last_seen"):
        print("Nothing to save: run collect first.")
        return 1
    save_json(STATE_FILE, {"last_seen": pending["last_seen"], "saved_at": datetime.now(timezone.utc).isoformat()})
    PENDING_FILE.unlink(missing_ok=True)
    print(f"Saved: next review starts after {pending['last_seen']}.")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    collect = sub.add_parser("collect", help="print the digest of external chats since the last run")
    collect.add_argument("--hours", type=int, default=0, help="look back this many hours instead of the saved state")
    collect.set_defaults(func=cmd_collect)
    sub.add_parser("save", help="remember how far collect got").set_defaults(func=cmd_save)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
