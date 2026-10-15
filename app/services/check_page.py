"""The part of a repeatedly checked page that says whether the answer moved.

Consensus Watches (``/s/...``) and curated Topics (``/topics/...``) both ask
one question again and again and keep every answer. Since 2026-10-15 both
pages are built from the same parts (templates/partials/check_page.html): a
state line, direct links, the answer, the history. This module builds the
state line from the annotated history, so the two pages cannot disagree about
what counts as movement (docs/watch-evidence-model.md).
"""

from __future__ import annotations

from datetime import datetime

from app.services import drift_signal
from app.services.history_view import day_label


def drift_view(history_points, selected_run_id="", query_first=False):
    """Whether the shown version moved the answer, and on what evidence.

    Only what the state line needs: the check's trigger, its date, its change
    summary and sources, and a newer check whose answer does not stand yet.
    """
    quiet = {"trigger": "stable", "summary": "", "evidence_sources": [],
             "pending_check": None, "checked_at": None}
    if selected_run_id == "original" or not history_points:
        return quiet
    # Idempotent: the projection already classified these points, but the view
    # must never fall back to a stored trigger from the looser rule.
    history_points = drift_signal.annotate_points(history_points)
    standing = drift_signal.accepted_index(history_points)
    index = standing if standing is not None else len(history_points) - 1
    if selected_run_id:
        for candidate, point in enumerate(history_points):
            if point.get("run_id") == selected_run_id:
                index = candidate
                break
    point = history_points[index]
    newest = history_points[-1]
    # The newest check, when its answer does not stand and the reader is
    # looking at the one that does.
    pending_check = None
    if index == standing and index != len(history_points) - 1 and not newest.get("accepted"):
        pending_check = {
            "signal": newest["signal"],
            "note": drift_signal.SIGNAL_NOTES.get(newest["signal"], ""),
            "checked_at": newest.get("ts"),
        }
    if query_first and index == 0:
        return {**quiet, "pending_check": pending_check, "checked_at": point.get("ts")}
    trigger = point.get("trigger") if point.get("trigger") in {"stable", "changed"} else "stable"
    return {
        "trigger": trigger,
        "summary": str(point.get("change_summary") or "") if trigger == "changed" else "",
        "evidence_sources": list(point.get("evidence_sources") or []),
        "pending_check": pending_check,
        "checked_at": point.get("ts"),
    }


def state_view(
    page, history, drift, *, awaiting, version_kind, selected_run_id,
    requested=False, fallback_notice="",
):
    """The one statement the page leads with: did the answer move, and since when.

    ``page`` carries ``is_active``, ``next_run`` (``{"day": ...}``),
    ``status_label`` and ``resolution``. Everything else on the page explains
    or proves this line. Scores, curves and model chips used to stand around
    it and buried what the page is for.
    """
    points = (history or {}).get("points") or []
    start = points[0]["ts"] if points else None
    facts = []
    if len(points) > 1:
        facts.append(f"Checked {len(points)} times since {day_label(start)}")
    elif start:
        facts.append(f"First checked {day_label(start)}")
    if page["is_active"] and page["next_run"]["day"]:
        facts.append(f"next check {page['next_run']['day']}")
    elif not page["is_active"]:
        facts.append(page["status_label"].lower())
    state = {"tone": "steady", "headline": "", "text": "", "sources": [], "note": "", "facts": facts}

    if awaiting:
        return {**state, "tone": "waiting", "headline": "Waiting for the first check",
                "text": "The first answer becomes the baseline. Every later check is "
                        "compared with it, and you only hear about it when the answer moves."}
    if version_kind == "fallback":
        return {**state, "tone": "past", "headline": "Latest version unavailable",
                "text": fallback_notice}
    if version_kind in {"original", "historical"} and points:
        shown = next((p for p in points if p.get("run_id") == selected_run_id), points[0])
        return {**state, "tone": "past", "headline": f"Answer from {day_label(shown['ts'])}",
                "back": requested,
                "text": "An earlier version of this page. The current answer may differ."
                        if requested else
                        "Later checks kept no copy of the answer; the history shows what they found."}
    resolution = page.get("resolution")
    if resolution:
        return {**state, "tone": "resolved",
                "headline": f"Resolved on {resolution['at']['day']}" if resolution["at"]["day"] else "Resolved",
                "text": resolution["reason"], "sources": resolution["sources"]}
    drift = drift or {}
    if drift.get("pending_check"):
        pending = drift["pending_check"]
        when = pending.get("checked_at")
        state["note"] = (f"Latest check, {day_label(when)}: " if isinstance(when, datetime) else "Latest check: ") + pending["note"]
    if drift.get("trigger") == "changed" and isinstance(drift.get("checked_at"), datetime):
        return {**state, "tone": "moved", "headline": f"Changed on {day_label(drift['checked_at'])}",
                "text": drift["summary"],
                "sources": list(drift.get("evidence_sources") or [])}
    moves = [point for point in points if point["trigger"] == "changed"]
    since = moves[-1]["ts"] if moves else start
    if since:
        state["headline"] = f"Unchanged since {day_label(since)}"
    return state
