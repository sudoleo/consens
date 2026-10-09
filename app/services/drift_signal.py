"""One definition of what counts as movement between two consensus checks.

A tracked page is only worth reading if "the answer moved" is rarer than "we
looked again". Two kinds of noise kept breaking that:

* the Judge compared two texts without their sources, so a fact that one
  check's web search simply did not find again read as a retraction -- the
  GPT-6 Topic announced "officially released", "unconfirmed" and "hypothetical"
  in four consecutive weeks while the model was out;
* the agreement score is quantised by the caps in ``consensus_scoring`` (90/84
  /64/39), so one contradiction labelled differently moves it a whole step.

The rule below (contract: ``docs/watch-evidence-model.md``) therefore asks
*why* a check differs before it calls the difference movement:

* ``new_evidence`` -- a newly cited source carries the change: it moved;
* ``evidence_missing`` -- the sources behind the standing answer did not come
  up and nothing contradicts it: the standing answer ``held``;
* ``reassessment`` / ``model_change`` -- same evidence, read differently: that
  only counts once the directly following check repeats it. Until then the
  check is ``confirming``; a re-check that does not repeat it makes it
  ``reverted``.

The score no longer raises an event of its own; it stays a curve marker
(``score_event``). History written before the Judge reported a cause keeps the
older rule (major grade, or a score leaving the band of the recent checks) and
is re-read on every render, so nothing needs a backfill.
"""

from __future__ import annotations

from datetime import timedelta

SCORE_BAND_DELTA = 15
SCORE_BAND_WINDOW = 3

MATERIAL_SEVERITY = "major"

CAUSE_NEW_EVIDENCE = "new_evidence"
CAUSE_EVIDENCE_MISSING = "evidence_missing"
CAUSE_REASSESSMENT = "reassessment"
CAUSE_MODEL_CHANGE = "model_change"
CAUSE_NONE = "none"
CAUSES = (
    CAUSE_NEW_EVIDENCE, CAUSE_EVIDENCE_MISSING, CAUSE_REASSESSMENT,
    CAUSE_MODEL_CHANGE, CAUSE_NONE,
)
_REASSESSMENT_CAUSES = {CAUSE_REASSESSMENT, CAUSE_MODEL_CHANGE}
# A re-check confirms a pending reassessment when it differs from the standing
# answer in substance again -- for whichever evidence-backed reason.
_CONFIRMING_CAUSES = _REASSESSMENT_CAUSES | {CAUSE_NEW_EVIDENCE}

SIGNAL_MOVED = "moved"
SIGNAL_CONFIRMING = "confirming"
SIGNAL_PRELIMINARY = "preliminary"
SIGNAL_REVERTED = "reverted"
SIGNAL_HELD = "held"
SIGNAL_RESTATED = "restated"
SIGNAL_STABLE = "stable"
# Checks whose answer stands: the next check is compared with the newest of
# them, and a public page shows it by default.
ACCEPTED_SIGNALS = frozenset({SIGNAL_MOVED, SIGNAL_RESTATED, SIGNAL_STABLE})
# Checks that need a prompt re-check before the regular schedule resumes, and
# how soon it runs. One re-check per event: the check after a "confirming" one
# is either movement or not major, so it never asks for another.
RECHECK_SIGNALS = frozenset({SIGNAL_CONFIRMING})
CONFIRMATION_DELAY = timedelta(minutes=20)


def _numeric(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def normalize_cause(value) -> str:
    cause = str(value or "").strip().lower()
    return cause if cause in CAUSES else ""


def recent_scores(points, limit: int = SCORE_BAND_WINDOW) -> list:
    """The last numeric agreement scores of an ascending history, oldest first."""
    scores = []
    for point in points or []:
        score = _numeric((point or {}).get("agreement_score"))
        if score is not None:
            scores.append(score)
    return scores[-limit:] if limit else scores


def score_left_band(score, previous_scores) -> bool:
    """True when the new score leaves the band the recent checks held.

    Compared against every score in the window, not just the predecessor: a
    score that keeps jumping between two cap steps never leaves its band and
    therefore stops reporting each jump as an event.
    """
    score = _numeric(score)
    if score is None:
        return False
    window = [
        value for value in (_numeric(item) for item in previous_scores or [])
        if value is not None
    ]
    if not window:
        return False
    return all(abs(score - value) >= SCORE_BAND_DELTA for value in window)


def is_major(changed, severity) -> bool:
    return bool(changed) and str(severity or "").lower() == MATERIAL_SEVERITY


def is_restated(changed, severity) -> bool:
    """The Judge saw a difference, but not one that carries the conclusion."""
    return bool(changed) and str(severity or "").lower() != MATERIAL_SEVERITY


def _legacy_signal(point: dict, window: list) -> str:
    """History written before the Judge reported a cause."""
    changed = point.get("changed")
    if is_major(changed, point.get("severity")):
        return SIGNAL_MOVED
    if is_restated(changed, point.get("severity")):
        return SIGNAL_RESTATED
    # The Judge read both answers and found no material difference. That
    # verdict outranks a score that jumped one grading step; otherwise the
    # page announced "Meaningful change" above "the differences are purely in
    # wording". Only a check without any verdict still falls back to the band.
    if not isinstance(changed, bool) and score_left_band(point.get("agreement_score"), window):
        return SIGNAL_MOVED
    return SIGNAL_STABLE


def _own_signal(point: dict, window: list) -> str:
    """The signal a check earns on its own, before its successor is known."""
    cause = normalize_cause(point.get("cause"))
    if not cause:
        return _legacy_signal(point, window)
    if not is_major(point.get("changed"), point.get("severity")):
        return SIGNAL_RESTATED if point.get("changed") else SIGNAL_STABLE
    if cause == CAUSE_NEW_EVIDENCE:
        return SIGNAL_MOVED
    if cause == CAUSE_EVIDENCE_MISSING:
        return SIGNAL_HELD
    # A major difference the Judge could not pin on new evidence -- including
    # an inconsistent "major, no cause" -- has to survive one re-check.
    return SIGNAL_CONFIRMING


def _repeats_change(point: dict) -> bool:
    return (
        is_major(point.get("changed"), point.get("severity"))
        and normalize_cause(point.get("cause")) in _CONFIRMING_CAUSES
    )


def annotate_points(points) -> list[dict]:
    """Classify an ascending history series in one pass.

    Every read surface (share page, agreement curve, dashboard JSON, morning
    brief, Topic record) runs its points through here instead of re-deriving
    the rule. Adds ``signal``, ``trigger`` (``changed`` iff moved), ``accepted``,
    ``score_event``, ``restated`` and ``score_delta``; the stored ``trigger`` of
    older checks is recomputed rather than trusted.
    """
    annotated = []
    window: list = []
    for point in points or []:
        point = dict(point or {})
        score = _numeric(point.get("agreement_score"))
        point["signal"] = _own_signal(point, window)
        point["score_event"] = score_left_band(score, window)
        point["restated"] = is_restated(point.get("changed"), point.get("severity"))
        previous = window[-1] if window else None
        point["score_delta"] = (
            int(score) - int(previous)
            if score is not None and previous is not None and annotated
            else None
        )
        point["confirmed_by_recheck"] = False
        if annotated and annotated[-1]["signal"] == SIGNAL_CONFIRMING:
            pending = annotated[-1]
            if _repeats_change(point):
                pending["signal"] = SIGNAL_PRELIMINARY
                point["signal"] = SIGNAL_MOVED
                point["confirmed_by_recheck"] = True
            else:
                pending["signal"] = SIGNAL_REVERTED
        annotated.append(point)
        if score is not None:
            window = (window + [score])[-SCORE_BAND_WINDOW:]
    for point in annotated:
        point["trigger"] = "changed" if point["signal"] == SIGNAL_MOVED else "stable"
        point["accepted"] = point["signal"] in ACCEPTED_SIGNALS
    return annotated


# Signals whose claim inventory a Topic record does not read: their answer
# does not stand, so the claims they drop or add are not part of the record.
NON_RECORD_SIGNALS = frozenset({SIGNAL_HELD, SIGNAL_CONFIRMING, SIGNAL_REVERTED})


def topic_point(run: dict) -> dict:
    """A Topic run in the shape of a history point.

    Topics never treated the agreement score as movement, so their legacy
    rule is the Judge grade alone; the score is left out on purpose.
    """
    change_type = str((run or {}).get("change_type") or "stable")
    return {
        "changed": change_type in {"minor", MATERIAL_SEVERITY},
        "severity": MATERIAL_SEVERITY if change_type == MATERIAL_SEVERITY else "minor",
        "cause": (run or {}).get("cause"),
        "agreement_score": None,
    }


def annotate_runs(runs) -> list[dict]:
    """Annotate ascending Topic runs with ``signal``, ``trigger``, ``accepted``."""
    runs = list(runs or [])
    annotated = annotate_points([topic_point(run) for run in runs])
    return [
        {
            **run,
            "signal": point["signal"],
            "trigger": point["trigger"],
            "accepted": point["accepted"],
            "confirmed_by_recheck": point["confirmed_by_recheck"],
        }
        for run, point in zip(runs, annotated)
    ]


def classify_latest(previous_points, point: dict) -> dict:
    """The annotated newest check of ``previous_points + [point]``."""
    return annotate_points(list(previous_points or []) + [point])[-1]


def accepted_index(annotated) -> int | None:
    """Index of the newest check whose answer stands, or None."""
    for index in range(len(annotated or []) - 1, -1, -1):
        if annotated[index].get("accepted"):
            return index
    return None


def steady_checks(points) -> int:
    """Completed checks since the last material one (0 = the newest is it)."""
    annotated = annotate_points(points)
    steady = 0
    for point in reversed(annotated):
        if point["trigger"] == "changed":
            break
        steady += 1
    return max(0, min(steady, max(0, len(annotated) - 1)))
