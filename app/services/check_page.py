"""The part of a repeatedly checked page that says whether the answer moved.

Consensus Watches (``/s/...``) and curated Topics (``/topics/...``) both ask
one question again and again and keep every answer. Since 2026-10-15 both
pages are built from the same parts (templates/partials/check_page.html): a
state line, direct links, the answer, the history. This module builds the
state line from the annotated history, so the two pages cannot disagree about
what counts as movement (docs/watch-evidence-model.md).
"""

from __future__ import annotations

import re
from datetime import datetime

from app.services import drift_signal
from app.services.history_view import build_history_view, day_label

# A paused Watch is not checked any more. Its page says so first, in grey,
# instead of promising "Unchanged since ..." in green for weeks after its last
# check (Apple-Audit L2; Max: shown honestly, not restarted).
PAUSED_STATUSES = frozenset({"paused", "paused_error"})


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
    paused = page.get("status") in PAUSED_STATUSES
    if len(points) > 1:
        facts.append(f"Checked {len(points)} times since {day_label(start)}")
    elif start:
        facts.append(f"First checked {day_label(start)}")
    if page["is_active"] and page["next_run"]["day"]:
        facts.append(f"next check {page['next_run']['day']}")
    elif not page["is_active"] and not paused:
        # A paused page says it in its headline; the facts would repeat it.
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
    if paused:
        last = (page.get("last_run") or {}).get("day") or ""
        return {**state, "tone": "paused",
                "headline": f"Paused · last checked {last}" if last else "Paused"}
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


def watch_summary(status, points, *, last_run=None, resolved_at=None):
    """The headline of a Watch page for the places that point at it: its row
    on /questions and its preview card (Apple-Audit L3, L13).

    Built by :func:`state_view` from the same history, so the list and the
    card can no longer announce a score or a state the page does not show.
    ``points`` are the Watch's history points, oldest first.
    """
    points = list(points or [])
    history = build_history_view(points) if points else None
    page = {
        "is_active": status == "active",
        "status": status,
        "status_label": str(status or "").replace("_", " ").capitalize(),
        "next_run": {"day": ""},
        "last_run": {"day": day_label(last_run) if isinstance(last_run, datetime) else ""},
        "resolution": (
            {"at": {"day": day_label(resolved_at) if isinstance(resolved_at, datetime) else ""},
             "reason": "", "sources": []}
            if status == "resolved" else None
        ),
    }
    state = state_view(
        page, history, drift_view(points), awaiting=False,
        version_kind="current", selected_run_id="",
    )
    return {"tone": state["tone"], "headline": state["headline"], "active": status == "active"}


# "Model C claims ... whereas Models A and B ...": the judge's own labels.
# Since 2026-10-16 the judge step names the real models itself
# (consensus_engine._named_models); pages written before keep the letters.
_JUDGE_LABEL = re.compile(r"\bModels?\s+([A-Z](?:\s*(?:,|/|&|\band\b|\bor\b)\s*[A-Z])*)\b")


def _leading_letters(stance) -> list[str]:
    """The letters a stance opens with ("Models A and B state ..."): the
    position's own models. A label later in the sentence ("..., unlike
    Model B") names the other side and is no evidence."""
    match = _JUDGE_LABEL.match(str(stance or "").strip())
    if not match:
        return []
    letters: list[str] = []
    for letter in re.findall(r"[A-Z]", match.group(1)):
        if letter not in letters:
            letters.append(letter)
    return letters


def _judge_letter_blocks(differences) -> dict[str, tuple[frozenset, list[str]]]:
    """Letter -> (its block of letters, the block's families).

    Evidence: a position whose stance opens with exactly as many letters as
    it lists families says that SET of letters is that set of families --
    never which letter is which, the judge's list order is no pairing. A
    letter's candidates are what all its pieces of evidence share; letters
    with the same candidates form a block once they are as many as their
    families (one letter, one family: placed alone). Contradicting evidence
    leaves a letter without candidates, and it keeps its text.
    """
    candidates: dict[str, set[str]] = {}
    first_order: dict[str, list[str]] = {}
    for diff in differences:
        for position in diff.get("positions") or []:
            if not isinstance(position, dict):
                continue
            letters = _leading_letters(position.get("stance"))
            models = list(dict.fromkeys(str(model) for model in position.get("models") or [] if model))
            if not letters or len(letters) != len(models):
                continue
            for letter in letters:
                candidates[letter] = candidates.get(letter, set(models)) & set(models)
                first_order.setdefault(letter, models)
    blocks: dict[str, tuple[frozenset, list[str]]] = {}
    progress = True
    while progress:
        progress = False
        for letter in sorted(candidates):
            if letter in blocks or not candidates[letter]:
                continue
            group = frozenset(other for other in candidates
                              if other not in blocks and candidates[other] == candidates[letter])
            if len(group) != len(candidates[letter]):
                continue
            families = [model for model in first_order[letter] if model in candidates[letter]]
            for member in group:
                blocks[member] = (group, families)
            for other in candidates:
                if other not in blocks:
                    candidates[other] = candidates[other] - set(families)
            progress = True
            break
    return blocks


def named_differences(differences):
    """Differences with "Model A/B/C" replaced by the families the page names
    next to each position, and without a family line that only repeats the
    stance (Apple-Audit L15). Readers had to map "Model C" to "Gemini"
    themselves.

    The letters are one judge call's anonymization, so one mapping holds for
    every difference on the page (_judge_letter_blocks). A label is named
    only when it covers whole blocks: "Models A and B" becomes "OpenAI and
    Gemini" when the page says that pair is those two, "Model A" alone only
    when A is known on its own. Anything less certain keeps its letters --
    a wrong family is worse than a letter (Zweitprüfung 14).
    """
    differences = [diff for diff in differences or [] if isinstance(diff, dict)]
    blocks = _judge_letter_blocks(differences)

    def name(text):
        def replace(match):
            letters = re.findall(r"[A-Z]", match.group(1))
            if not letters or not all(letter in blocks for letter in letters):
                return match.group(0)
            named = set(letters)
            if any(not blocks[letter][0] <= named for letter in letters):
                return match.group(0)
            # Each block's families in turn, onto its letters in span order.
            queues = {group: list(families) for group, families in (blocks[letter] for letter in letters)}
            used: dict[str, str] = {}
            for letter in letters:
                if letter not in used:
                    used[letter] = queues[blocks[letter][0]].pop(0)
            return re.sub(r"[A-Z]", lambda found: used[found.group(0)], match.group(1))
        return _JUDGE_LABEL.sub(replace, str(text or ""))

    named = []
    for diff in differences:
        positions = []
        for position in diff.get("positions") or []:
            if not isinstance(position, dict):
                continue
            stance = name(position.get("stance"))
            models = list(position.get("models") or [])
            if models and all(str(model) in stance for model in models):
                models = []
            positions.append({**position, "stance": stance, "models": models})
        named.append({**diff, "claim": name(diff.get("claim")),
                      "verify": name(diff.get("verify")), "positions": positions})
    return named


# Differences on the share page as the app draws them (consensus-insights.js
# buildDifferenceCards, Max 2026-10-16): critical contradictions first, then
# minor ones, then other emphases; two or more smaller ones fold behind the
# critical ones. Each side is one claim, the side the answer takes first, the
# sides under one another with "vs" between them; the same claim said by
# several models is one side.
_DIFFERENCE_TAGS = {
    "major": ("Critical", "Critical contradiction", "is-crit"),
    "minor": ("Minor", "Minor contradiction about a detail", "is-warn"),
    "": ("Contradiction", "Contradiction", "is-warn"),
}
_MODEL_ALIASES = {"Claude": "Anthropic", "ChatGPT": "OpenAI", "Google": "Gemini", "xAI": "Grok"}
_MONO_PROVIDERS = {"OpenAI", "Grok", "Kimi", "GLM", "Meta", "Qwen"}


def _difference_rank(diff) -> int:
    if diff.get("type") != "contradiction":
        return 2
    return 1 if diff.get("severity") == "minor" else 0


def _claim_key(text) -> str:
    return re.sub(r"[\W_]+", " ", str(text or "").lower()).strip()


def _merged_sides(positions):
    merged, taken = [], set()
    for position in positions:
        models = [model for model in position.get("models") or [] if model not in taken]
        key = _claim_key(position.get("stance") or position.get("quote"))
        same = next((side for side in merged if key and _claim_key(side.get("stance") or side.get("quote")) == key), None)
        taken.update(models)
        if same:
            same["models"] = same["models"] + models
            same["quote"] = same.get("quote") or position.get("quote")
            same["in_answer"] = same.get("in_answer") is True or position.get("in_answer") is True
            continue
        # A side without a model of its own (the page names them in the claim) stays.
        if models or not position.get("models"):
            merged.append({**position, "models": models})
    return merged


def difference_cards(differences, providers, render_inline):
    """``differences`` as named_differences returns them; ``providers`` maps a
    family label to its provider (icon); ``render_inline`` turns a model's
    Markdown into safe inline HTML (bold stays bold, no raw asterisks)."""
    def model_view(name):
        label = _MODEL_ALIASES.get(str(name), str(name))
        provider = providers.get(label)
        return {"name": str(name), "icon": provider.icon_url if provider else "",
                "mono": label in _MONO_PROVIDERS}

    ordered = sorted(enumerate(differences or []), key=lambda entry: (_difference_rank(entry[1]), entry[0]))
    cards = []
    for index, diff in ordered:
        contradiction = diff.get("type") == "contradiction"
        if contradiction:
            tag, meaning, dot = _DIFFERENCE_TAGS.get(diff.get("severity") or "", _DIFFERENCE_TAGS[""])
        else:
            tag, meaning, dot = "Emphasis", "Different emphasis, not a contradiction", "is-info"
        sides = _merged_sides([position for position in diff.get("positions") or [] if isinstance(position, dict)])
        sides.sort(key=lambda side: side.get("in_answer") is not True)
        cards.append({
            "index": index,
            "rank": _difference_rank(diff),
            "classes": ("is-contradiction" if contradiction else "is-emphasis")
                       + (" is-major" if contradiction and diff.get("severity") == "major" else ""),
            "dot": dot, "tag": tag, "meaning": meaning,
            "claim": str(diff.get("claim") or ""),
            "versus": contradiction and len(sides) > 1,
            "verify": str(diff.get("verify") or "").strip(),
            "sides": [{
                "stance_html": render_inline(side.get("stance") or side.get("quote") or ""),
                "quote_html": render_inline(side.get("quote") or "") if side.get("stance") else "",
                "in_answer": side.get("in_answer") is True,
                "models": [model_view(model) for model in side.get("models") or []],
            } for side in sides],
        })
    smaller = [card for card in cards if card["rank"] > 0]
    if len(smaller) >= 2 and len(smaller) < len(cards):
        return {"cards": [card for card in cards if card["rank"] == 0], "smaller": smaller}
    return {"cards": cards, "smaller": []}
