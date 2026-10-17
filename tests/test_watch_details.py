"""Watch details and rejected matches (docs/watch-evidence-model.md, "Details").

The goal is the event a watch waits for; details are what a match must fit or
must not be ("new, from a shop, no private sellers"). Every search and the
goal verdict read them. "Not what I wanted" reopens a reached goal and rules
the match that closed it out for good. Case that prompted it: a shoe watch
closed on a used pair, then on a private listing, and the owner could only
go on by overwriting the goal with feedback, which lost the price limit.
"""

import json
import os
from datetime import datetime, timezone
from unittest.mock import patch

os.environ.setdefault("UNIT_TEST_MODE", "1")

from app.services import evidence_change, watch_probe, watch_scheduler, watch_service  # noqa: E402
from app.services.llm import consensus_engine  # noqa: E402
from test_watch_feature import FakeDb, share  # noqa: E402


GOAL = "A new Adizero Adios Pro 4 in 44.5 is offered for under 140 EUR"
DETAILS = "Only new, from a shop. No eBay, Kleinanzeigen or private sellers."
USED = {"id": "S1", "url": "https://buycycle.com/en-lt/product/6ac9", "title": "Used Adios Pro 4"}
SHOP = {"id": "S2", "url": "https://www.runnerspoint.de/adios-pro-4", "title": "Runnerspoint"}


def _watch(db, **overrides):
    db.stores["shares"]["A" * 16] = share()
    db.stores["watches"]["w1"] = {
        "owner_uid": "u1", "share_id": "A" * 16, "status": "active",
        "interval": "weekly", "email_mode": "changes_only", "email_enabled": True,
        "condition": GOAL, **overrides,
    }
    db.stores["users/u1/watch_state"]["quota"] = {"active_count": 1}


def _resolved(db, **overrides):
    _watch(db, status="resolved", resolution={
        "run_id": "r1", "condition": GOAL, "reason": "A used pair is listed for 120 EUR.",
        "sources": [{"id": "S1", "title": USED["title"], "url": USED["url"]}],
    }, **overrides)
    db.stores["users/u1/watch_state"]["quota"] = {"active_count": 0}


def _update(db, changes):
    with patch.object(watch_service.persistence_guard, "ensure_account_write_allowed"):
        return watch_service.update_watch("u1", "w1", changes, "pro", db=db)


# --- Goal identity ------------------------------------------------------------


def test_details_are_part_of_the_goal_but_old_goals_keep_their_identity():
    assert watch_service.goal_hash(GOAL) == watch_service.condition_hash(GOAL)
    assert watch_service.goal_hash(GOAL, "  ") == watch_service.condition_hash(GOAL)
    assert watch_service.goal_hash(GOAL, DETAILS) != watch_service.condition_hash(GOAL)
    # Whitespace does not make a new goal; no goal means no goal identity.
    assert watch_service.goal_hash(GOAL, DETAILS) == watch_service.goal_hash(GOAL, f" {DETAILS}  ")
    assert watch_service.goal_hash("", DETAILS) == ""


# --- Editing details ----------------------------------------------------------


def test_the_owner_sets_details_and_an_earlier_verdict_no_longer_counts():
    db = FakeDb()
    _watch(db, last_condition_status="met", last_condition_hash="old")
    updated = _update(db, {"requirements": "  Only new,\n from a shop.  "})
    stored = db.stores["watches"]["w1"]
    assert stored["requirements"] == "Only new, from a shop."
    assert stored["last_condition_status"] is None
    assert updated["requirements"] == "Only new, from a shop."
    assert updated["condition"] == GOAL


def test_details_have_a_length_limit():
    db = FakeDb()
    _watch(db)
    try:
        _update(db, {"requirements": "x" * 501})
    except watch_service.WatchError as exc:
        assert exc.code == "invalid_requirements"
    else:
        raise AssertionError("details over 500 characters must be refused")


def test_a_resolved_watch_reopens_with_new_details_and_the_same_goal():
    db = FakeDb()
    _resolved(db)
    reopened = _update(db, {"status": "active", "requirements": DETAILS})
    assert reopened["status"] == "active"
    assert reopened["condition"] == GOAL
    assert reopened["resolution"] is None
    # Not marked as a wrong match: nothing is ruled out.
    assert reopened["rejected_sources"] == []


# --- "Not what I wanted" ------------------------------------------------------


def test_not_what_i_wanted_keeps_the_goal_and_rules_the_match_out():
    db = FakeDb()
    _resolved(db)
    reopened = _update(db, {"status": "active", "reject_match": True, "requirements": DETAILS})
    stored = db.stores["watches"]["w1"]
    assert stored["status"] == "active"
    assert stored["condition"] == GOAL
    assert stored["requirements"] == DETAILS
    assert stored["resolution"] is None
    assert stored["rejected_sources"] == [{"url": USED["url"], "title": USED["title"]}]
    assert reopened["rejected_sources"][0]["url"] == USED["url"]
    assert db.stores["users/u1/watch_state"]["quota"]["active_count"] == 1


def test_not_what_i_wanted_works_without_new_details():
    db = FakeDb()
    _resolved(db)
    reopened = _update(db, {"status": "active", "reject_match": True})
    assert reopened["status"] == "active"
    assert reopened["rejected_sources"][0]["url"] == USED["url"]


def test_only_a_reached_goal_can_be_rejected():
    db = FakeDb()
    _watch(db)
    for changes in (
        {"status": "active", "reject_match": True},
        {"reject_match": True},
        {"status": "active", "reject_match": "yes"},
    ):
        try:
            _update(db, changes)
        except watch_service.WatchError as exc:
            assert exc.code == "invalid_request"
        else:
            raise AssertionError(f"{changes} must be refused on an active watch")


def test_rejected_matches_stay_unique_and_bounded():
    earlier = [{"url": f"https://shop.example/{index}", "title": str(index)} for index in range(10)]
    merged = watch_service._with_rejected(
        earlier, [{"url": "https://shop.example/3/", "title": "again"}, USED],
    )
    assert len(merged) == watch_service.WATCH_REJECTED_MAX
    # The repeated match moves to the end instead of appearing twice.
    assert [item["title"] for item in merged[-2:]] == ["again", USED["title"]]
    assert "0" not in [item["title"] for item in merged]


# --- The verdict --------------------------------------------------------------


def test_a_goal_met_only_by_a_rejected_match_is_not_met():
    verified = evidence_change.verify(
        {"changed": False, "condition_status": "met", "condition_evidence": ["S1"],
         "condition_reason": "A pair is listed for 120 EUR."},
        previous_sources=[], new_sources=[USED, SHOP], rejected_sources=[USED],
    )
    assert verified["condition_status"] == "not_met"
    assert verified["condition_verified"] is False
    assert verified["condition_reason"] == evidence_change.RULED_OUT_REASON
    assert verified["condition_sources"] == []


def test_another_match_still_meets_the_goal_next_to_a_rejected_one():
    verified = evidence_change.verify(
        {"changed": False, "condition_status": "met", "condition_evidence": ["S1", "S2"]},
        previous_sources=[], new_sources=[USED, SHOP], rejected_sources=[USED],
    )
    assert verified["condition_status"] == "met"
    assert verified["condition_verified"] is True
    assert [item["url"] for item in verified["condition_sources"]] == [SHOP["url"]]


def test_the_judge_sees_ruled_out_sources_only_when_there_are_any():
    _old, plain = evidence_change.prompt_sources([], [USED, SHOP])
    assert all("ruled_out" not in item for item in plain)
    _old, marked = evidence_change.prompt_sources(
        [], [USED, SHOP], evidence_change.source_keys([USED]),
    )
    assert [item["ruled_out"] for item in marked] == [True, False]


def _judge_prompt(**kwargs):
    prompts = []

    def call(provider, api_model, model_ref, keys, **options):
        prompts.append(options["prompt"])
        return json.dumps({
            "changed": False, "severity": "minor", "cause": "none", "evidence": [],
            "change_summary": "", "held_summary": "", "condition_status": "unknown",
            "condition_reason": "", "condition_evidence": [],
        })

    with patch.object(consensus_engine, "_differences_attempts",
                      return_value=[(("openai", "judge", "openai:judge"), False, "free")]), \
            patch.object(consensus_engine, "_judge_effort", return_value=None), \
            patch.object(consensus_engine, "_call_engine_text", side_effect=call):
        consensus_engine.query_consensus_change(
            "Old", "New", {}, "OpenAI", GOAL, old_sources=[], new_sources=[USED, SHOP], **kwargs,
        )
    return prompts[0]


def test_the_judge_checks_the_goal_against_the_details_and_rejections():
    prompt = _judge_prompt(
        requirements=DETAILS, ruled_out=evidence_change.source_keys([USED]),
    )
    assert "<USER_DETAILS_JSON>" + json.dumps(DETAILS) in prompt
    assert "also fits the USER DETAILS" in prompt
    assert "marked ruled_out" in prompt
    assert '"ruled_out": true' in prompt

    plain = _judge_prompt()
    assert "USER_DETAILS" not in plain
    assert "ruled_out" not in plain


# --- The search ---------------------------------------------------------------


def test_the_search_hears_the_details_and_the_ruled_out_matches():
    question = watch_scheduler.research_question(
        "I want the Adizero Adios Pro 4 in 44.5 for under 140 EUR.", DETAILS, [USED],
    )
    assert question.startswith("I want the Adizero Adios Pro 4")
    assert f"Details that matter to me: {DETAILS}" in question
    assert "do not offer these again: Used Adios Pro 4" in question
    assert watch_scheduler.research_question("Plain?", "", []) == "Plain?"


def test_a_check_passes_details_to_the_search_and_the_goal_verdict():
    seen = {}

    def pipeline(**kwargs):
        seen["question"] = kwargs["question"]
        return {
            "consensus_response": "A new pair costs 135 EUR at Runnerspoint [S2].",
            "differences_data": {"agreement": {"score": 90, "level": "strong"}},
            "differences": "", "agreement": {"score": 90, "level": "strong"},
            "model_answers": [{
                "provider": "OpenAI", "model": "m", "response": "r", "sources": [SHOP],
            }],
        }

    def first_check(consensus, keys, engine, **kwargs):
        seen["verdict"] = kwargs
        return {"changed": False, "cause": "none"}

    with patch.dict(os.environ, {"MOCK_LLM": "1"}), \
            patch.object(watch_scheduler, "run_consensus_pipeline", side_effect=pipeline), \
            patch.object(watch_scheduler, "_configured_consensus_engine", return_value=None), \
            patch.object(evidence_change, "first_check", side_effect=first_check):
        watch_scheduler.execute_watch(
            "Adios Pro 4 under 140?", None, condition=GOAL,
            requirements=DETAILS, rejected_sources=[USED],
        )
    assert DETAILS in seen["question"]
    assert seen["verdict"]["requirements"] == DETAILS
    assert seen["verdict"]["rejected_sources"] == [USED]


def test_the_daily_probe_names_the_details():
    since = datetime(2026, 10, 1, tzinfo=timezone.utc)
    prompt = watch_probe._prompt("Adios Pro 4 under 140?", GOAL, since, DETAILS)
    assert f"Only what fits these details from the person counts: {DETAILS}" in prompt
    assert "details from the person" not in watch_probe._prompt("Q?", GOAL, since)


# --- Runs ---------------------------------------------------------------------


def test_a_verdict_belongs_to_the_goal_with_the_details_it_was_judged_under():
    point = watch_service.run_point(
        {"condition_status": "met"}, condition=GOAL, requirements=DETAILS,
    )
    assert point["condition_hash"] == watch_service.goal_hash(GOAL, DETAILS)
    # Two "met" verdicts only confirm each other under the same details.
    earlier = {**point, "condition_verified": False}
    outcome = watch_service.run_outcome(
        {"history_points": [earlier], "condition": GOAL, "requirements": "Other details"},
        {"condition_status": "met"},
    )
    assert outcome["resolved"] is False


def test_the_public_page_never_shows_the_details():
    db = FakeDb()
    _resolved(db, requirements=DETAILS, rejected_sources=[USED])
    db.stores["watches"]["w1"]["resolution"]["requirements"] = DETAILS
    meta = watch_service.get_public_watch_meta("A" * 16, db=db)
    assert meta["condition"] == GOAL
    assert DETAILS not in json.dumps(meta, default=str)
    assert USED["url"] not in json.dumps({k: v for k, v in meta.items() if k != "resolution"}, default=str)
