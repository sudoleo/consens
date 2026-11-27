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
          agent handled it (phases, wait for the answer's first token,
          models, failures, tool calls and refused ones, answer check and
          each reviewer's part in it), its Watch (proposed, started, or a
          scheduled run with its earlier looks), answer excerpt, cost;
          per account the share of its daily allowance it spent; plus counted
          server warnings of the same window.
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


# A reviewer's final round (agent_audit.FinalRequest): "final", its "hedge",
# and a "repair"; a live round's repair starts before the answer's end.
FINAL_ROUNDS = ("final", "hedge")


def searches(step: dict) -> int:
    usage = step.get("usage") if isinstance(step.get("usage"), dict) else {}
    return usage.get("web_search_requests") or 0


def reviewer_check(reviewers: list, answer_end) -> dict:
    """Per reviewer model, what of the check after the answer is its part:
    when it ended (``after_answer_seconds``), how long its final round
    waited (a live round still running) and took, how soon that round's
    first token came, where it ran and how often the reviewer searched.
    The turn's ``check_after_answer_seconds`` names no model; this tells
    which one held the check up and whether it was the provider or the
    reviewer's own research."""
    out = {}
    for name in sorted({model_name(s.get("model")) for s in reviewers}):
        calls = [s for s in reviewers if model_name(s.get("model")) == name]
        entry = {}
        ended = [s["settled_at"] for s in calls if s.get("settled_at")]
        if answer_end and ended and max(ended) > answer_end:
            entry["after_answer_seconds"] = seconds(answer_end, max(ended))
        final = [s for s in calls if s.get("round") in FINAL_ROUNDS or (
            s.get("round") == "repair" and answer_end and s.get("created_at") and s["created_at"] >= answer_end)]
        if final:
            first = min(final, key=lambda s: s["created_at"])
            if answer_end:
                entry["final_waited_seconds"] = max(0, seconds(answer_end, first["created_at"]))
            last = max((s for s in final if s.get("settled_at")), key=lambda s: s["settled_at"], default=None)
            if last:
                entry["final_seconds"] = seconds(first["created_at"], last["settled_at"])
                if last.get("endpoint"):
                    entry["final_endpoint"] = last["endpoint"]
            if first.get("first_token_at"):
                entry["final_first_token_seconds"] = seconds(first["created_at"], first["first_token_at"])
        entry["searches"] = sum(searches(s) for s in calls)
        out[name] = entry
    return out


def turn_flow(turn: dict, steps: list, agents: dict) -> dict:
    """How the agent handled the turn, from its receipts (content-free).

    The answer is the chat model's last step that ended on its own (``stop``):
    ``answer_started_seconds`` is how long the user waited for its first
    token, ``answer_seconds`` how long it wrote. ``after_comparison_seconds``
    runs from the comparison's end to the answer's end, and so also holds
    the agent's research after it (a review read it as writing time)."""
    t0 = turn.get("created_at")
    for step in steps:
        step["kind"] = "chat" if str(step.get("step", "")).startswith("completion") else (
            (agents.get(step.get("agent_id") or "") or {}).get("kind") or "other")
    steps.sort(key=lambda s: s.get("created_at") or t0)
    chat = [s for s in steps if s["kind"] == "chat"]
    comparison = [s for s in steps if s["kind"] == "comparison"]
    # A stopped judge call is mostly the loser of a hedge (consensus_engine.
    # _hedged_judge_call): it is no judge call of its own and does not make
    # the check longer (a review counted 8 of them as 17 calls).
    judges = [s for s in steps if s["kind"] == "judge" and s.get("status") != "cancelled"]
    stopped_judges = sum(1 for s in steps if s["kind"] == "judge" and s.get("status") == "cancelled")
    # The agent's reviewers (agent_audit) check its answer as the judges
    # check a Compare run's.
    reviewers = [s for s in steps if s["kind"] == "audit" and s.get("status") != "cancelled"]
    flow = {"steps": len(steps), "chat_model": model_name(chat[0].get("model")) if chat else None,
            "chat_steps": len(chat)}
    answer = next((s for s in reversed(chat) if s.get("finish_reason") == "stop"), chat[-1] if chat else None)
    answer_end = (answer or {}).get("settled_at")
    if answer and answer_end:
        flow["answer_started_seconds"] = seconds(t0, answer.get("first_token_at") or answer.get("created_at"))
        flow["answer_seconds"] = seconds(answer.get("created_at"), answer_end)
        late = [s for s in judges + reviewers if s.get("settled_at") and s["settled_at"] > answer_end]
        if late:
            flow["check_after_answer_seconds"] = seconds(answer_end, max(s["settled_at"] for s in late))
    if comparison:
        c0 = min(s["created_at"] for s in comparison)
        ended = [s for s in comparison if s.get("settled_at")]
        if ended:
            c1 = max(s["settled_at"] for s in ended)
            flow["comparison_seconds"] = seconds(c0, c1)
            slowest = max(ended, key=lambda s: s["settled_at"])
            flow["slowest_model"] = f"{model_name(slowest.get('model'))} {seconds(slowest['created_at'], slowest['settled_at'])}s"
            if answer_end and answer_end > c1:
                flow["after_comparison_seconds"] = seconds(c1, answer_end)
        flow["comparison_models"] = sorted({model_name(s.get("model")) for s in comparison})
        flow["comparison_failures"] = [f"{model_name(s.get('model'))}: {s.get('status')} {s.get('finish_reason') or ''}".strip()
                                       for s in comparison if s.get("status") != "succeeded"]
    if reviewers:
        flow["reviewer_calls"] = len(reviewers)
        flow["reviewer_models"] = dict(Counter(model_name(s.get("model")) for s in reviewers))
        flow["reviewer_check"] = reviewer_check(reviewers, answer_end)
    if judges:
        flow["judge_calls"] = len(judges)
        flow["judge_timeouts"] = sum(1 for s in judges if s.get("settled_at") and s.get("status") != "succeeded"
                                     and seconds(s["created_at"], s["settled_at"]) >= JUDGE_TIMEOUT_SECONDS)
        flow["judge_models"] = dict(Counter(model_name(s.get("model")) for s in judges))
        ended = [s for s in judges if s.get("settled_at")]
        if ended:
            flow["slowest_judge_seconds"] = max(seconds(s["created_at"], s["settled_at"]) for s in ended)
    # Named for what it mostly is: a review read "judge_calls_stopped" as
    # checks cut short by the token budget and proposed a fix for it.
    if stopped_judges:
        flow["judge_hedges_stopped"] = stopped_judges
    usage = turn.get("agent_usage") or {}
    flow["cost_usd"] = round((usage.get("estimated_cost_nano_usd") or 0) / 1e9, 3)
    flow["web_searches"] = usage.get("web_search_requests") or 0
    # The agent's own searches (its Exa receipts, "service:" steps, and any
    # of its chat steps); the rest of web_searches is the other models'
    # (reviewers, compared models, helpers).
    flow["agent_searches"] = sum(searches(s) for s in steps
                                 if s["kind"] == "chat" or str(s.get("step", "")).startswith("service:"))
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


# A call the tool registry refused before the tool ran (agent_tools.ToolRegistry.validate).
REFUSED_CALL = re.compile(r"^Invalid (\S+) arguments - (.*?)\. Expected arguments", re.DOTALL)


def turn_tools(turn_ref) -> dict:
    """The turn's tool calls from its work log, content-free: how often each
    tool ran, which calls were refused (tool and the fields it failed on,
    never a value) and which tools answered with an error. A refused call
    shows nowhere else on the turn, and the server log has no account."""
    from app.services.agent_sessions import work_log_entries
    calls, refused, errors = Counter(), Counter(), Counter()
    for snapshot in turn_ref.collection("work_log").stream():
        for entry in work_log_entries(snapshot.to_dict()):
            if entry.get("kind") != "tool":
                continue
            name = str(entry.get("name") or "?")
            calls[name] += 1
            try:
                result = json.loads(entry.get("content") or "")
            except ValueError:
                continue  # a long result the log keeps shortened: never a refusal
            error = result.get("error") if isinstance(result, dict) else None
            if not isinstance(error, str):
                continue
            match = REFUSED_CALL.match(error)
            if match:
                fields = sorted({problem.split(":", 1)[0].strip() for problem in match.group(2).split("; ")})
                refused[f"{match.group(1)}: {', '.join(fields)}"] += 1
            else:
                errors[name] += 1
    out = {"tools": dict(calls.most_common())} if calls else {}
    if refused:
        out["refused_calls"] = dict(refused)
    if errors:
        out["tool_errors"] = dict(errors)
    return out


def watch_summary(turn_id: str, turn: dict, started: dict, record: dict | None = None) -> dict:
    """The turn's part in a Watch: one it proposed (and whether the user
    started it), or this turn being a scheduled run of one. ``record``: the
    run's Watch (agent_watches): since when it exists, its status now and
    what its earlier looks found. Without them a question its first look
    already asked at the start reads as one asked a week too late."""
    from app.services.agent_watches import _outcome
    out = {}
    proposal = turn.get("agent_watch")
    if isinstance(proposal, dict):
        out["proposed"] = proposal.get("interval") or "daily"
        out["started"] = started.get(turn_id) or "no"
    # Only a run that reports something keeps ``agent_watch_run``; every run
    # carries ``watch_run`` in its settings (routers/agent.py _quiet_watch_run).
    if (turn.get("agent_settings") or {}).get("watch_run"):
        out["scheduled_run"] = _outcome(turn)[0]
        if record:
            created = turn.get("created_at")
            out["watch_since"] = local(record.get("created_at"))
            out["watch_status"] = record.get("status")
            out["earlier_looks"] = [look.get("outcome") for look in record.get("looks") or []
                                    if hasattr(look.get("at"), "astimezone") and hasattr(created, "astimezone")
                                    and look["at"] < created]
    return out


def allowance_used(db, uid: str, days, config: dict, tier: str) -> list:
    """The share of its daily allowance the account spent on each UTC day in
    ``days`` (agent_quota ledger, also its temporary chats), content-free.
    The server log names no account when one runs out (``Agent admission
    stopped``); this shows whether it was an external one."""
    from app.services import agent_budget_config, agent_quota
    limit = agent_budget_config.limit_for(config, tier)
    suffix = ("_" + config["reset_epoch"] if config.get("reset_epoch") else "") + agent_quota.LEDGER_UNIT
    out = []
    for day in days:
        spent = agent_quota.spent_amount(agent_quota.quota_ref(db, uid, day + suffix).get().to_dict() or {})
        if spent:
            out.append({"day": day, "tier": agent_budget_config.tier_key(tier),
                        "used_percent": round(spent * 100 / limit) if limit else None})
    return out


def utc_days(start: datetime, end: datetime) -> list:
    first, last = start.astimezone(timezone.utc).date(), end.astimezone(timezone.utc).date()
    return [(first + timedelta(days=n)).isoformat() for n in range((last - first).days + 1)]


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
    from google.cloud.firestore_v1.base_query import FieldFilter
    now = datetime.now(timezone.utc)
    state = load_json(STATE_FILE)
    since = (datetime.fromisoformat(state["last_seen"]) if state.get("last_seen") and not args.hours
             else now - timedelta(hours=args.hours or FIRST_LOOKBACK_HOURS))
    from app.services import agent_budget_config, agent_quota
    accounts, own = external_accounts()
    budget_config, days = agent_budget_config.get_config(db), utc_days(since, now)
    turns, newest, allowance, watches = [], since, {}, {}
    for uid, (created, providers) in accounts.items():
        user = db.collection("users").document(uid)
        chats = list(user.collection("chats").where("updated_at", ">", since).stream())
        if not chats:
            continue
        used = allowance_used(db, uid, days, budget_config, agent_quota.account_tier(uid))
        if used:
            allowance[pseudonym(uid)] = used
        calls = started = None
        for chat in chats:
            chat_data = chat.to_dict() or {}
            if chat_data.get("temporary"):
                # A temporary chat is the user's alone while it lasts.
                continue
            previous = None
            for doc in sorted(chat.reference.collection("turns").where("created_at", ">", since).stream(),
                              key=lambda d: (d.to_dict() or {}).get("created_at")):
                turn = doc.to_dict() or {}
                if calls is None:
                    calls = [c.to_dict() for c in user.collection("llm_calls").where("created_at", ">", since).stream()]
                steps = [dict(c) for c in calls if c.get("turn_id") == doc.id]
                agents = {a.id: a.to_dict() or {} for a in doc.reference.collection("agents").stream()} if steps else {}
                if started is None and isinstance(turn.get("agent_watch"), dict):
                    started = {(w.to_dict() or {}).get("turn_id"): (w.to_dict() or {}).get("status")
                               for w in db.collection("agent_watches").where(
                                   filter=FieldFilter("uid", "==", uid)).stream()}
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
                    "flow": {**turn_flow(turn, steps, agents), **turn_tools(doc.reference)},
                    "check": review_summary(turn),
                }
                run = (turn.get("agent_settings") or {}).get("watch_run")
                watch_id = run.get("watch_id") if isinstance(run, dict) else None
                if watch_id and watch_id not in watches:
                    watches[watch_id] = db.collection("agent_watches").document(watch_id).get().to_dict() or {}
                watch = watch_summary(doc.id, turn, started or {}, watches.get(watch_id) if watch_id else None)
                if watch:
                    entry["watch"] = watch
                # A Watch asks its task again on every run: that is no user repeating themselves.
                if (previous and previous.get("question") == turn.get("question")
                        and "scheduled_run" not in watch):
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
        # The log has no account, so own accounts count too (a review pinned
        # 3 of the operator's refused turns on an external user's run).
        "server_warnings_scope": "all accounts, own included; not tied to the turns below",
        # Per external account with a chat in the window, temporary ones too:
        # around 100 % or more it ran out of its daily allowance that day.
        "allowance_by_user": allowance,
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
