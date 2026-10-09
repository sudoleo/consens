"""What a Watch page lists of its history.

The public Watch page used to stack one card per check, each with its score
and "No meaningful movement detected". A Watch is worth reading for the
checks that moved the answer, so only those stand alone; the quiet ones in
between fold into one entry.
"""

import os
from datetime import datetime, timedelta, timezone

os.environ.setdefault("UNIT_TEST_MODE", "1")

from app.services.history_view import build_history_view, day_label

START = datetime(2026, 7, 21, 8, 0, tzinfo=timezone.utc)


def _point(index, *, changed=False, severity="minor", score=84):
    return {
        "ts": START + timedelta(days=7 * index), "agreement_score": score,
        "changed": changed, "severity": severity, "change_summary": "",
        "run_id": f"run-{index}",
    }


def _kinds(points):
    return [
        (entry["kind"], len(entry["points"]))
        for entry in build_history_view(points)["timeline"]
    ]


def test_quiet_checks_fold_between_the_ones_that_moved():
    points = [_point(index) for index in range(11)]
    points[3] = _point(3, changed=True, severity="major", score=64)

    assert _kinds(points) == [
        ("latest", 1),  # what the last look found
        ("quiet", 6),
        ("moved", 1),
        ("quiet", 2),
        ("start", 1),   # since when this is watched
    ]


def test_a_newest_check_that_moved_is_listed_as_the_move():
    points = [_point(0), _point(1), _point(2, changed=True, severity="major")]

    assert _kinds(points) == [("moved", 1), ("quiet", 1), ("start", 1)]


def test_a_single_check_is_the_start():
    assert _kinds([_point(0)]) == [("start", 1)]


def test_quiet_groups_know_their_runs_for_deep_links():
    points = [_point(index) for index in range(4)]

    quiet = build_history_view(points)["timeline"][1]

    assert quiet["run_ids"] == ["run-2", "run-1"]


def test_day_label_has_no_leading_zero():
    assert day_label(datetime(2026, 8, 4)) == "Aug 4"
