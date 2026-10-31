"""Audit mode near the daily allowance (spec A-R2): once the agent paid a
step, its closing answer and the reviewers' final rounds may overdraw the
allowance, like the answer and the judges after paid comparisons
(test_agent_answer_mode), and a long run's reserve counts what the
reviewers take."""
import pytest

from app.services import agent_budget_config, agent_quota
from app.services.agent_delegation import TURN_ALLOWANCE_LIMIT
from app.services.agent_tokens import input_estimate
from app.services.llm.agent_client import answer_output_limit, routing_output_limit
from test_agent_audit import ANSWER, Audit, audit_loop, saved
from test_agent_runs import UID, store  # noqa: F401  (fixture)


@pytest.fixture(autouse=True)
def _admin_allowance(monkeypatch):
    # As in test_agent_audit: the agent's search rounds fit an admin's day.
    monkeypatch.setitem(agent_budget_config.DEFAULT_TIER_LIMITS, "pro", 5_000_000)


def use_up_the_day(store):
    """Another tab used up the rest of the day; held reservations stay."""
    ref = agent_quota.quota_ref(store.db, UID, agent_quota.day_key() + agent_quota.LEDGER_UNIT)
    ref.set({**(ref.get().to_dict() or {}), "used": agent_quota.snapshot(store.db, UID)["limit"]})


def receipts(store):
    return [snapshot.to_dict() for snapshot in
            store.db.collection("users").document(UID).collection("llm_calls").stream()]


def test_after_a_paid_step_the_audit_turn_closes_with_its_answer_and_its_review(store):
    script = Audit(tool_steps=1, on_lookup=lambda _calls: use_up_the_day(store))
    loop = audit_loop(store, script)
    list(loop.run())
    turn = saved(store, loop)
    assert turn["status"] == "completed" and turn["consensus"] == ANSWER
    # Step 1 was refused before its claim and written as the closing answer.
    assert [step for step, _ in script.calls if step.startswith("completion:")] == ["completion:0", "completion:1"]
    # The reviewers' final rounds came beyond the allowance as well.
    assert turn["agent_review"]["status"] == "succeeded"
    assert script.rounds["anthropic"][-1] == script.rounds["openai"][-1] == "final"
    assert agent_quota.snapshot(store.db, UID)["remaining"] == 0
    # What the reviewers took, as the ledger booked it (_long_run_limit's estimate).
    reviewers = [r for r in receipts(store) if r.get("session_kind") == "audit"]
    assert reviewers and loop.reviewer_charge == sum(r["quota_charged"] for r in reviewers)


def test_without_a_paid_step_a_refused_first_step_ends_the_audit_turn(store):
    use_up_the_day(store)
    script = Audit()
    loop = audit_loop(store, script)
    with pytest.raises(agent_quota.AgentTokenBudgetExceeded):
        list(loop.run())
    assert not [step for step, _ in script.calls if step.startswith("completion:")]


def test_a_long_runs_reserve_counts_what_the_reviewers_took(store, monkeypatch):
    loop = audit_loop(store, Audit())
    model = loop.model
    inputs = input_estimate(loop.messages, loop.registry.schemas, model.request_config)
    room = 2 * inputs + routing_output_limit(model) + answer_output_limit(model) + 1_000
    monkeypatch.setattr(agent_quota, "remaining_allowance", lambda db, uid: room)
    assert loop._long_run_limit() is None
    # 10,000 over four steps: the next step's live rounds and the final
    # rounds need about 2,500 each, more than the 1,000 left over.
    loop.reviewer_charge, loop.routing_steps = 10_000, 4
    assert loop._long_run_limit() == TURN_ALLOWANCE_LIMIT
