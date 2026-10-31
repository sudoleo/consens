"""Anonymous daily counters of the Agent's turns (spec A-M1).

A deleted chat takes its turn, its sessions and its work log with it; these
counters stay. One document per UTC day, ``ops_metrics/agent-audit-{day}``,
counts every chat turn of the agent once at its end (until 2026-10-31 only
those in audit mode, then one of two): by status and review status, by
number of reviewers, in histogram buckets of its times (total, until the
answer was fixed, marks after the last word, each gate's wait, each
reviewer's final round by model, the reviewers' backlog when the answer was
fixed), its halts by kind and decision, its failures by code, and with the
VM whether it had the workspace from the start, opened it or stayed without
it (``workspace``: open, opened, closed). Never an
account, a chat, a turn or any text: model ids, codes and bucket labels only.

The run's thread only copies what it holds in memory (``capture``: the times
of the work log's entries, the holds of its activity). A daemon thread reads
the saved turn once and writes one merge of Firestore increments
(``record``), so the counters are never on the critical path; errors are
logged, never raised. Fields that later packages add (a reviewer's
``final_ms`` and ``backlog``, the turn's ``agent_holds``, a gate entry's
``gate_ms``) are read when present; without them their bucket stays empty.
``scripts/audit_report.py`` reads the documents back.

Since 2026-10-30 (audit I6) every turn that used the workspace counts there
too, because 47 % of them lay in chats deleted since and took all their
details along: in fields of their own (``ws_*``), its status, steps, active
time (pauses for the user left out), the first call into the workspace
(browser or VM: how long it took, how far into the message it came, whether
it failed) and the workspace's outages (VM unavailable or busy, browser off).
Every turn that ended its work at a limit counts its reason (``wrap_up``, I1).
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
from datetime import datetime, timezone

from app.core.observability import safe_exception

COLLECTION = "ops_metrics"
# Upper bounds in seconds (Z1: marks p90 <= 20 s, max <= 60 s; Z5: gate p90
# <= 10 s, never over 20 s); the last bucket is "over7200".
SECOND_BOUNDS = (2, 5, 10, 15, 20, 30, 45, 60, 90, 120, 300, 600, 1800, 3600, 7200)
# Unread log entries of a reviewer when the answer was fixed.
COUNT_BOUNDS = (0, 1, 2, 3, 5, 10, 20)
# The agent's steps in a workspace turn (up to AgentPolicy.vm_turn_steps).
STEP_BOUNDS = (1, 2, 3, 5, 10, 20, 30, 50, 100, 200)
_LABEL = re.compile(r"[^A-Za-z0-9_-]")


def document_id(day):
    return f"agent-audit-{day}"


def label(value):
    """A field name from a code, a kind or a model id: no dots, no slashes."""
    return _LABEL.sub("_", str(value if value not in (None, "") else "unknown"))[:64]


def bucket(value, bounds=SECOND_BOUNDS):
    for bound in bounds:
        if value <= bound:
            return f"le{bound}"
    return f"over{bounds[-1]}"


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
    if start is None or end is None or end < start:
        return None
    return (end - start).total_seconds()


def _gate_ms(entry, text):
    """A gate entry's wait when it carries one (as a field or in its JSON)."""
    value = entry.get("gate_ms")
    if value is None and entry.get("format") == "json":
        try:
            value = (json.loads(text) or {}).get("gate_ms")
        except (ValueError, AttributeError):
            value = None
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0 else None


def capture(loop):
    """What the counters need from the run's memory: no text, no account."""
    entries = []
    if loop.work_log is not None:
        for entry, text in loop.work_log.entries_after(0):
            if entry.get("kind") == "step" and entry.get("actor") == "agent":
                entries.append({"at": entry.get("at"), "actor": "agent", "kind": "step"})
            elif entry.get("kind") == "app" and entry.get("name") in {"answer_fixed", "checked", "paused"}:
                kept = {"at": entry.get("at"), "actor": "app", "kind": "app", "name": entry["name"]}
                if entry["name"] != "answer_fixed":
                    kept["gate_ms"] = _gate_ms(entry, text)
                entries.append(kept)
    holds = [{key: item.get(key) for key in ("halt", "gate", "ask", "domain", "state")}
             for item in loop.completion.activity or [] if item.get("kind") == "hold"]
    captured = {"entries": entries, "holds": holds, "reviewers": len(loop.comparison.auditor.reviewers),
                "ended_at": datetime.now(timezone.utc)}
    wrap_up = getattr(loop.completion, "wrap_up", None)
    if isinstance(wrap_up, dict):
        captured["wrap_up"] = wrap_up.get("reason")
    vm_tools = getattr(loop, "vm_tools", None)
    if vm_tools is not None:
        # The workspace on demand (DelegationLoop._open_workspace): how often
        # the agent opens it, stays without it, or has it from the start.
        captured["workspace"] = ("opened" if loop.workspace_opened else "closed" if loop.workspace_closed
                                 else "open")
    if vm_tools is not None and getattr(loop, "workspace_used", False):
        vm = getattr(loop.completion, "vm", None) or {}
        browser = getattr(vm_tools, "browser_tools", None)
        first = getattr(loop, "first_workspace_call", None)
        captured["workspace_run"] = {
            "steps": loop.routing_steps, "active_s": round(max(0.0, loop._turn_elapsed()), 1),
            "first": dict(first) if isinstance(first, dict) else None,
            "outages": [code for code, hit in (("vm_unavailable", vm.get("unavailable")), ("vm_busy", vm.get("busy")),
                                               ("browser_off", getattr(browser, "off", False))) if hit is True]}
    return captured


def _add(counters, *path):
    node = counters
    for key in path[:-1]:
        node = node.setdefault(key, {})
    node[path[-1]] = node.get(path[-1], 0) + 1


def _status(turn):
    if not turn:
        return "deleted"
    if turn.get("status") == "failed" and turn.get("error_code") == "cancelled":
        return "cancelled"
    return turn.get("status") or "unknown"


def _hold_kind(hold):
    if hold.get("ask"):
        return f"ask_{hold['ask']}"
    if hold.get("domain"):
        return "domain"
    kind = hold.get("kind") or hold.get("halt")
    return f"gate_{kind}" if hold.get("gate") else kind


def workspace_counters(turn, captured, counters):
    """A workspace turn's own fields (``ws_*``) and any turn's ``wrap_up``,
    added to ``counters``: codes and buckets, never a text or an id."""
    if captured.get("wrap_up"):
        _add(counters, "wrap_up", label(captured["wrap_up"]))
    run = captured.get("workspace_run")
    if not isinstance(run, dict):
        return counters
    status = _status(turn)
    _add(counters, "ws_turns", label(status))
    if isinstance(run.get("steps"), int):
        _add(counters, "ws_steps", bucket(run["steps"], STEP_BOUNDS))
    if isinstance(run.get("active_s"), (int, float)):
        _add(counters, "ws_active_s", bucket(run["active_s"]))
    first = run.get("first") if isinstance(run.get("first"), dict) else None
    if first and isinstance(first.get("ms"), (int, float)):
        _add(counters, "ws_first_call_s", label(first.get("kind")), bucket(first["ms"] / 1000))
        if isinstance(first.get("after_s"), (int, float)):
            # From the message's start to the first result of the workspace.
            _add(counters, "ws_first_result_s", bucket(first["after_s"] + first["ms"] / 1000))
        if first.get("failed"):
            _add(counters, "ws_failures", "first_call")
    for code in run.get("outages") or []:
        _add(counters, "ws_failures", label(code))
    if status in {"failed", "cancelled"}:
        failure = turn.get("agent_failure") if isinstance(turn.get("agent_failure"), dict) else {}
        _add(counters, "ws_failures", label(f"turn_{failure.get('code') or turn.get('error_code')}"))
    return counters


def turn_counters(turn, captured):
    """The increments one turn adds to its day: {field: {key: n}}, its
    workspace's among them (workspace_counters). ``turn``: the saved turn
    (None once its chat was deleted)."""
    counters = {}
    turn = turn or {}
    workspace_counters(turn, captured, counters)
    status = _status(turn)
    _add(counters, "turns", label(status))
    if captured.get("workspace"):
        _add(counters, "workspace", label(captured["workspace"]))
    review = turn.get("agent_review") or {}
    audit = review.get("audit") or {}
    reviewers = [item for item in audit.get("reviewers") or [] if isinstance(item, dict)]
    _add(counters, "reviewers", f"n{len(reviewers) if reviewers else captured.get('reviewers', 0)}")
    if review:
        _add(counters, "reviews", label(review.get("status")))
    ended = captured.get("ended_at")
    created = turn.get("created_at")
    total = _seconds(created, ended)
    if total is not None:
        _add(counters, "total_s", bucket(total))
    entries = captured.get("entries") or []
    fixed = [entry for entry in entries if entry.get("kind") == "app" and entry.get("name") == "answer_fixed"]
    if fixed:
        answer = _seconds(created, fixed[-1].get("at"))
        if answer is not None:
            _add(counters, "answer_s", bucket(answer))
        marks = _seconds(fixed[-1].get("at"), ended)
        if marks is not None and review.get("mode") == "audit" and status == "completed":
            _add(counters, "marks_s", bucket(marks))
    step_at = None
    for entry in entries:
        if entry.get("kind") == "step" and entry.get("actor") == "agent":
            step_at = entry.get("at")
        elif entry.get("kind") == "app" and entry.get("name") in {"checked", "paused"}:
            wait = entry.get("gate_ms")
            if wait is not None:
                _add(counters, "gate_s", bucket(wait / 1000))
            elif entry.get("name") == "checked":
                # Every "checked" is a gate's go: its wait since the step's entry.
                wait = _seconds(step_at, entry.get("at"))
                if wait is not None:
                    _add(counters, "gate_s", bucket(wait))
    for reviewer in reviewers:
        model = label((reviewer.get("model") or {}).get("model") if isinstance(reviewer.get("model"), dict)
                      else reviewer.get("model"))
        _add(counters, "reviewer_status", label(reviewer.get("status")))
        final_ms = reviewer.get("final_ms")
        if isinstance(final_ms, (int, float)) and not isinstance(final_ms, bool) and final_ms >= 0:
            _add(counters, "final_s", model, bucket(final_ms / 1000))
        backlog = reviewer.get("backlog")
        unread = backlog.get("entries") if isinstance(backlog, dict) else None
        if isinstance(unread, int) and not isinstance(unread, bool) and unread >= 0:
            _add(counters, "backlog_entries", bucket(unread, COUNT_BOUNDS))
        code = (reviewer.get("failure") or {}).get("code") if isinstance(reviewer.get("failure"), dict) else None
        if code:
            _add(counters, "failures", "reviewer", label(code))
    for issue in audit.get("issues") or []:
        if isinstance(issue, dict) and issue.get("code"):
            _add(counters, "failures", "review", label(issue["code"]))
    if status in {"failed", "cancelled"}:
        failure = turn.get("agent_failure") if isinstance(turn.get("agent_failure"), dict) else {}
        _add(counters, "failures", "turn", label(failure.get("code") or turn.get("error_code")))
    saved_holds = turn.get("agent_holds")
    holds = saved_holds if isinstance(saved_holds, list) else captured.get("holds") or []
    for hold in holds:
        if isinstance(hold, dict):
            decision = hold.get("decision") or hold.get("state")
            _add(counters, "halts", label(_hold_kind(hold)), label("open" if decision == "waiting" else decision))
    return counters


def _increments(counters):
    from google.cloud import firestore
    return {key: _increments(value) if isinstance(value, dict) else firestore.Increment(value)
            for key, value in counters.items()}


def write(db, turn_ref, captured):
    """Read the saved turn once and add its counters to its day (one merge)."""
    from google.cloud import firestore
    snapshot = turn_ref.get()
    turn = snapshot.to_dict() if snapshot.exists else None
    counters = turn_counters(turn, captured)
    day = captured["ended_at"].astimezone(timezone.utc).strftime("%Y-%m-%d")
    db.collection(COLLECTION).document(document_id(day)).set(
        {**_increments(counters), "day": day, "updated_at": firestore.SERVER_TIMESTAMP}, merge=True)
    return counters


def _enabled():
    # Test and mock profiles share the real Firestore locally: no counters.
    return not any(os.getenv(key) == "1" for key in ("UNIT_TEST_MODE", "E2E_TEST_MODE", "MOCK_LLM"))


def record(loop):
    """At the end of a chat turn of the agent: copy what it holds, count it
    off this thread."""
    if not _enabled():
        return False
    try:
        captured = capture(loop)
        turn_ref = loop.store._turn_ref(loop.uid, loop.chat_id, loop.turn_id)
        db = loop.store.db
    except Exception as exc:
        logging.warning("Agent audit metrics not captured category=%s", safe_exception(exc))
        return False

    def run():
        try:
            write(db, turn_ref, captured)
        except Exception as exc:
            logging.warning("Agent audit metrics not saved category=%s", safe_exception(exc))

    try:
        threading.Thread(target=run, name="agent-audit-metrics", daemon=True).start()
    except Exception as exc:
        logging.warning("Agent audit metrics not started category=%s", safe_exception(exc))
        return False
    return True
