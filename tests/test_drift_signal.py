"""The line between "the answer moved" and "we checked again".

Contract: docs/watch-evidence-model.md. A check only moves the record on
evidence; what a search merely failed to find again does not count as a
retraction, and a reassessment has to survive one re-check.
"""

import os

os.environ.setdefault("UNIT_TEST_MODE", "1")

from app.services import drift_signal


def _check(changed=False, severity="minor", cause="none", score=84):
    return {"agreement_score": score, "changed": changed, "severity": severity, "cause": cause}


def _signals(series):
    return [point["signal"] for point in drift_signal.annotate_points(series)]


# --- Evidence model -------------------------------------------------------


def test_the_gpt6_record_holds_the_release_instead_of_flip_flopping():
    """The real Topic: no successor (Sep 2), Astra announced (Sep 9), then two
    checks whose search did not surface the announcement again. Only the
    announcement is movement; the standing answer is the one from Sep 9."""
    series = [
        _check(score=84),
        _check(True, "major", "new_evidence", score=0),
        _check(True, "major", "evidence_missing", score=9),
        _check(True, "major", "evidence_missing", score=22),
    ]

    annotated = drift_signal.annotate_points(series)

    assert [point["signal"] for point in annotated] == ["stable", "moved", "held", "held"]
    assert [point["trigger"] for point in annotated] == ["stable", "changed", "stable", "stable"]
    assert drift_signal.accepted_index(annotated) == 1


def test_a_reassessment_waits_for_the_recheck_before_it_counts():
    pending = [_check(), _check(True, "major", "reassessment")]

    assert _signals(pending) == ["stable", "confirming"]
    assert drift_signal.accepted_index(drift_signal.annotate_points(pending)) == 0


def test_a_repeated_reassessment_is_movement_on_the_recheck():
    series = [
        _check(),
        _check(True, "major", "reassessment"),
        _check(True, "major", "reassessment"),
    ]

    annotated = drift_signal.annotate_points(series)

    assert [point["signal"] for point in annotated] == ["stable", "preliminary", "moved"]
    assert annotated[2]["confirmed_by_recheck"] is True
    assert drift_signal.accepted_index(annotated) == 2


def test_a_reassessment_the_recheck_does_not_repeat_is_reverted():
    series = [_check(), _check(True, "major", "model_change"), _check(True, "minor", "reassessment")]

    assert _signals(series) == ["stable", "reverted", "restated"]


def test_a_recheck_that_only_misses_evidence_does_not_confirm():
    series = [_check(), _check(True, "major", "reassessment"), _check(True, "major", "evidence_missing")]

    assert _signals(series) == ["stable", "reverted", "held"]


def test_new_evidence_confirms_a_pending_reassessment():
    series = [_check(), _check(True, "major", "reassessment"), _check(True, "major", "new_evidence")]

    assert _signals(series) == ["stable", "preliminary", "moved"]


def test_a_major_grade_without_a_cause_is_treated_as_a_reassessment():
    """The Judge reported major but "none": that still needs the re-check."""
    assert _signals([_check(), _check(True, "major", "none")]) == ["stable", "confirming"]


def test_the_score_alone_no_longer_raises_an_event():
    series = [_check(score=84), _check(score=84), _check(score=84), _check(score=39)]

    annotated = drift_signal.annotate_points(series)

    assert annotated[-1]["signal"] == "stable"
    assert annotated[-1]["score_event"] is True


def test_classify_latest_reads_the_new_check_in_the_context_of_its_history():
    history = [_check(), _check(True, "major", "reassessment")]

    latest = drift_signal.classify_latest(history, _check(True, "major", "reassessment"))

    assert latest["signal"] == "moved"
    assert latest["accepted"] is True


# --- History written before the Judge reported a cause --------------------


def _legacy(changed=False, severity="minor", score=84, **extra):
    return {"agreement_score": score, "changed": changed, "severity": severity, **extra}


def test_legacy_minor_grade_is_a_restatement_not_a_change():
    assert _signals([_legacy(), _legacy(True, "minor", 82)]) == ["stable", "restated"]
    assert _signals([_legacy(), _legacy(True, "major", 82)]) == ["stable", "moved"]


def test_legacy_score_leaving_the_band_is_movement_only_without_a_verdict():
    series = [_legacy(), _legacy(), _legacy(), _legacy(None, "", score=64)]

    assert _signals(series)[-1] == "moved"


def test_legacy_judge_verdict_outranks_a_score_step():
    """The real GitHub Code Quality watch: the Judge said "the differences are
    purely in wording" while the score fell from 84 to 64. The page announced
    a "Meaningful change" above that sentence."""
    window = [_legacy(score=90), _legacy(score=90), _legacy(score=84)]

    assert _signals(window + [_legacy(False, "minor", 64)])[-1] == "stable"
    assert _signals(window + [_legacy(True, "minor", 64)])[-1] == "restated"


def test_legacy_score_swinging_between_two_cap_steps_reports_the_first_step_only():
    series = [_legacy(None, "", score=84), _legacy(None, "", score=64), _legacy(None, "", score=84),
              _legacy(None, "", score=64), _legacy(None, "", score=84)]

    triggers = [point["trigger"] for point in drift_signal.annotate_points(series)]

    assert triggers == ["stable", "changed", "stable", "stable", "stable"]


def test_a_stored_trigger_from_the_looser_rule_is_recomputed_not_trusted():
    series = [
        _legacy(trigger="stable"),
        _legacy(True, "minor", 82, trigger="changed"),
    ]

    annotated = drift_signal.annotate_points(series)

    assert [point["trigger"] for point in annotated] == ["stable", "stable"]
    assert annotated[1]["restated"] is True
    assert annotated[1]["changed"] is True


def test_the_first_check_has_no_band_and_no_predecessor():
    annotated = drift_signal.annotate_points([_legacy(score=90, severity="")])

    assert annotated[0]["trigger"] == "stable"
    assert annotated[0]["score_delta"] is None
    assert annotated[0]["score_event"] is False


def test_steady_checks_counts_back_to_the_last_material_check():
    series = [_legacy(), _legacy(True, "major"), _legacy(True, "minor"), _legacy()]

    assert drift_signal.steady_checks(series) == 2
    assert drift_signal.steady_checks(series[:2]) == 0
