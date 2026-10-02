"""The evidence model behind Watches and Topics (docs/watch-evidence-model.md).

A record only moves on evidence: the server verifies what the Change Judge
cites, a held answer is a gap in a Topic's claim record rather than a
retraction, a goal can close a Watch, and the daily probe only pulls a check
forward for a source the standing answer did not have.
"""

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

os.environ.setdefault("UNIT_TEST_MODE", "1")

from app.services import claim_ledger, evidence_change, topic_runner, watch_probe, watch_service  # noqa: E402
from test_claim_ledger import dimension, run  # noqa: E402
from test_watch_feature import FakeDb, share  # noqa: E402


NOW = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)
OLD = [{"id": "S1", "url": "https://openai.com/index/astra", "title": "Astra announced"}]
NEW = [
    {"id": "S1", "url": "https://openai.com/index/astra", "title": "Astra announced"},
    {"id": "S2", "url": "https://openai.com/index/gpt-6", "title": "GPT-6 is here"},
]


# --- Server-side verification of the Judge -----------------------------------


def test_new_evidence_must_cite_a_source_the_standing_answer_did_not_have():
    verified = evidence_change.verify(
        {"changed": True, "severity": "major", "cause": "new_evidence", "evidence": ["S2"]},
        previous_sources=OLD, new_sources=NEW,
    )
    assert verified["cause"] == "new_evidence"
    assert verified["evidence_sources"] == [
        {"id": "S2", "title": "GPT-6 is here", "url": "https://openai.com/index/gpt-6"}
    ]

    reused = evidence_change.verify(
        {"changed": True, "severity": "major", "cause": "new_evidence", "evidence": ["S1"]},
        previous_sources=OLD, new_sources=NEW,
    )
    assert reused["cause"] == "reassessment"
    assert reused["evidence_sources"] == []


def test_invented_source_ids_are_dropped():
    verified = evidence_change.verify(
        {"changed": True, "severity": "major", "cause": "new_evidence", "evidence": ["S9"]},
        previous_sources=OLD, new_sources=NEW,
    )
    assert verified["cause"] == "reassessment"


def test_a_reassessment_after_a_line_up_change_is_a_model_change():
    verified = evidence_change.verify(
        {"changed": True, "severity": "major", "cause": "reassessment"},
        previous_sources=OLD, new_sources=NEW,
        previous_models=["OpenAI: gpt-5.5"], new_models=["OpenAI: gpt-6-luna"],
    )
    assert verified["cause"] == "model_change"


def test_an_unchanged_answer_has_no_cause_and_a_goal_needs_a_cited_source():
    verified = evidence_change.verify(
        {
            "changed": False, "severity": "minor", "cause": "new_evidence",
            "condition_status": "met", "condition_evidence": ["S7"],
        },
        previous_sources=OLD, new_sources=NEW,
    )
    assert verified["cause"] == "none"
    assert verified["condition_verified"] is False
    sourced = evidence_change.verify(
        {"changed": False, "severity": "minor", "condition_status": "met", "condition_evidence": ["S2"]},
        previous_sources=OLD, new_sources=NEW,
    )
    assert sourced["condition_verified"] is True
    assert sourced["condition_sources"][0]["url"] == "https://openai.com/index/gpt-6"


def test_the_judge_sees_which_new_sources_it_has_seen_before():
    old_view, new_view = evidence_change.prompt_sources(OLD, NEW)
    assert old_view == [{"id": "S1", "site": "openai.com", "title": "Astra announced"}]
    assert [item["seen_before"] for item in new_view] == [True, False]


# --- Topics: the GPT-6 record -------------------------------------------------


def test_a_held_topic_run_is_a_gap_in_the_claim_record_not_a_retraction():
    released = dimension("OpenAI has officially released GPT-6 Astra", key="astra")
    priced = dimension("Official pricing is published for the GPT-6 line", key="price")
    runs = [
        run(0, [dimension("No successor model has been announced", key="none"),
                dimension("GPT-5.5 is the current flagship", key="flag")]),
        {**run(1, [released, priced], change_type="major", summary="Astra released."),
         "cause": "new_evidence"},
        {**run(2, [dimension("GPT-6 cannot be confirmed from official sources", key="x"),
                   dimension("Variant names are speculative", key="y")],
               change_type="major", summary="No longer confirmed."),
         "cause": "evidence_missing"},
    ]

    ledger = claim_ledger.build_claim_ledger(runs)
    record = claim_ledger.build_record_summary(runs)
    strip = claim_ledger.build_check_strip(runs, ledger)

    holding = {claim["label"] for claim in ledger["holding"] + ledger["new"]}
    assert "OpenAI has officially released GPT-6 Astra" in holding
    assert "GPT-6 cannot be confirmed from official sources" not in holding
    assert ledger["thin"] == 1
    assert record["material_count"] == 1
    assert record["anchor_run_id"] == "run-1"
    assert [cell["kind"] for cell in strip] == ["first", "material", "held"]


def test_a_topic_run_outcome_asks_for_a_recheck_on_a_reassessment():
    recent = [run(0, [], change_type="stable")]
    pending = topic_runner.run_outcome(recent, "major", "reassessment")
    assert pending == {"signal": "confirming", "accepted": False, "recheck": True}
    moved = topic_runner.run_outcome(recent, "major", "new_evidence")
    assert moved == {"signal": "moved", "accepted": True, "recheck": False}


# --- Watches: reopening after the goal was reached ----------------------------


def _resolved_watch(db):
    db.stores["shares"]["A" * 16] = share()
    db.stores["watches"]["w1"] = {
        "owner_uid": "u1", "share_id": "A" * 16, "status": "resolved",
        "interval": "weekly", "email_mode": "changes_only", "email_enabled": True,
        "condition": "GPT-6 is officially released",
        "resolution": {"run_id": "r1", "condition": "GPT-6 is officially released"},
    }
    db.stores["users/u1/watch_state"]["quota"] = {"active_count": 0}
    db.stores["watch_uniques"] = db.stores["watch_uniques"]


def test_a_resolved_watch_only_reopens_with_a_new_or_empty_goal():
    db = FakeDb()
    _resolved_watch(db)
    with patch.object(watch_service.persistence_guard, "ensure_account_write_allowed"):
        try:
            watch_service.update_watch("u1", "w1", {"status": "active"}, "pro", db=db)
        except watch_service.WatchError as exc:
            assert exc.code == "goal_reached"
        else:
            raise AssertionError("reopening with the reached goal must fail")
        reopened = watch_service.update_watch(
            "u1", "w1", {"status": "active", "condition": "Pricing is published"}, "pro", db=db,
        )
    assert reopened["status"] == "active"
    assert reopened["resolution"] is None
    assert db.stores["watches"]["w1"]["next_probe_at"] is not None


# --- The daily probe ----------------------------------------------------------


def test_a_probe_only_counts_a_yes_with_a_source_the_answer_did_not_cite():
    fresh = watch_probe.evaluate(
        "NEW: yes\nOpenAI released GPT-6 today [S1].",
        [{"id": "S1", "url": "https://openai.com/index/gpt-6", "title": "GPT-6"}],
        OLD,
    )
    assert fresh["outcome"] == "new_evidence"
    assert fresh["sources"][0]["url"] == "https://openai.com/index/gpt-6"
    assert fresh["summary"].startswith("OpenAI released GPT-6")

    known = watch_probe.evaluate("NEW: yes\nAstra exists.", OLD, OLD)
    assert known["outcome"] == "nothing_new"
    assert watch_probe.evaluate("NEW: no", NEW, OLD)["outcome"] == "nothing_new"
    assert watch_probe.evaluate("Something else entirely", NEW, OLD)["outcome"] == "nothing_new"


def _probe_watch(db, **overrides):
    db.stores["watches"]["w1"] = {
        "owner_uid": "u1", "share_id": "A" * 16, "status": "active",
        "interval": "weekly", "next_probe_at": NOW - timedelta(minutes=1),
        "next_run_at": NOW + timedelta(days=5), **overrides,
    }


def test_probe_claim_advances_first_and_respects_the_daily_cap():
    db = FakeDb()
    _probe_watch(db)
    with patch.object(watch_probe.cfg, "get_watch_probe_max_per_day", return_value=1):
        claimed, reason = watch_probe.claim_probe("w1", now=NOW, db=db)
        assert reason == "claimed" and claimed["share_id"] == "A" * 16
        assert db.stores["watches"]["w1"]["next_probe_at"] == NOW + watch_probe.PROBE_INTERVAL
        db.stores["watches"]["w1"]["next_probe_at"] = NOW
        assert watch_probe.claim_probe("w1", now=NOW, db=db) == (None, "budget")


def test_probe_is_skipped_when_the_full_check_is_close_or_the_watch_is_daily():
    db = FakeDb()
    _probe_watch(db, next_run_at=NOW + timedelta(hours=5))
    assert watch_probe.claim_probe("w1", now=NOW, db=db) == (None, "covered")
    _probe_watch(db, interval="daily")
    assert watch_probe.claim_probe("w1", now=NOW, db=db) == (None, "not_eligible")
    assert db.stores["watches"]["w1"]["next_probe_at"] is None


def test_new_evidence_pulls_the_full_check_forward():
    db = FakeDb()
    _probe_watch(db)
    pulled = watch_probe.record_probe(
        "w1", {"outcome": "new_evidence", "summary": "Released.", "sources": []}, now=NOW, db=db,
    )
    assert pulled is True
    assert db.stores["watches"]["w1"]["next_run_at"] == NOW
    assert db.stores["watches"]["w1"]["last_probe"]["outcome"] == "new_evidence"

    _probe_watch(db)
    assert watch_probe.record_probe("w1", {"outcome": "nothing_new"}, now=NOW, db=db) is False
    assert db.stores["watches"]["w1"]["next_run_at"] == NOW + timedelta(days=5)


def test_claimed_probe_cannot_record_for_changed_goal_or_superseded_claim():
    from copy import deepcopy
    db = FakeDb()
    _probe_watch(db, condition="original goal")
    claimed, reason = watch_probe.claim_probe("w1", now=NOW, db=db)
    assert reason == "claimed"
    db.stores["watches"]["w1"]["condition"] = "changed goal"
    before = deepcopy(db.stores["watches"]["w1"])
    assert watch_probe.record_probe("w1", {"outcome": "new_evidence"}, now=NOW, db=db, expected_claim=claimed) is False
    assert db.stores["watches"]["w1"] == before
    db.stores["watches"]["w1"].update(condition="original goal", probe_claim_token="newer worker")
    before = deepcopy(db.stores["watches"]["w1"])
    assert watch_probe.record_probe("w1", {"outcome": "new_evidence"}, now=NOW, db=db, expected_claim=claimed) is False
    assert db.stores["watches"]["w1"] == before
