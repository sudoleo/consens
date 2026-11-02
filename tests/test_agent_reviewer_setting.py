"""Who checks the Agent's work: the account setting ``reviewers`` (since
2026-11-01). "always" has the reviewers from the run's start (the one mode,
test_agent_audit), "workspace" from the agent's first step that reaches for
its workspace on, "off" never. Without reviewers no halt and no gate: memory
locks once outside content is in view, a domain is the user's alone, and the
answer's review ends "off", not "failed"."""
import json

import pytest
from pydantic import BaseModel, ConfigDict

from app.api.routers import agent
from app.services import agent_audit_metrics, agent_memory, prompt_defaults, user_settings
from app.services.agent_audit import AnswerAudit
from app.services.agent_memory import MemorySnapshot
from app.services.agent_plan import PlanTools
from app.services.agent_tools import ReadOnlyTool, ToolRegistry
from test_agent_audit import ANSWER, Audit, audit_loop, round_entries, saved
from test_agent_runs import AUTH, UID, api, store  # noqa: F401  (fixtures)


@pytest.fixture(autouse=True)
def _admin_allowance(monkeypatch):
    from app.services import agent_budget_config
    monkeypatch.setitem(agent_budget_config.DEFAULT_TIER_LIMITS, "pro", 5_000_000)


class PlainArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    step: int = 0


def with_tools(loop, *, workspace=()):
    """``loop`` (with the script's lookup, audit_loop) and a plain tool; the
    names in ``workspace`` count as the workspace's tools (no VM in tests)."""
    plain = ReadOnlyTool("plain", "Look at nothing.", PlainArgs, lambda args, *, cancellation: {"text": "ok"})
    loop.registry = ToolRegistry([*loop.registry.tools.values(), plain], argument_limit=loop.registry.argument_limit)
    loop.workspace_names = frozenset(workspace)
    return loop


def test_the_setting_takes_its_three_values_and_nothing_else():
    assert user_settings.validate_changes({"reviewers": "off"}) == ({"reviewers": "off"}, [])
    assert user_settings.validate_changes({"reviewers": "workspace"}) == ({"reviewers": "workspace"}, [])
    assert user_settings.validate_changes({"reviewers": None}) == ({"reviewers": None}, [])
    assert user_settings.validate_changes({"reviewers": "never"}) == ({}, ["reviewers"])
    assert user_settings.sanitize_settings({"reviewers": "sometimes", "claim_counts": True}) == {"claim_counts": True}


@pytest.mark.parametrize("setting", ["off", "workspace"])
def test_without_reviewers_the_answer_stands_unreviewed_and_nobody_follows(store, setting):
    script = Audit()
    loop = audit_loop(store, script, reviewers=setting)
    events = list(loop.run())
    turn = saved(store, loop)
    review = turn["agent_review"]
    assert turn["status"] == "completed" and turn["consensus"] == ANSWER
    # Nobody was asked, nobody failed: "off", with the setting that said so.
    assert review["status"] == "off" and review["audit"]["reviewers"] == []
    assert review["audit"]["setting"] == setting and "issues" not in review["audit"]
    assert script.rounds == {} and not loop.comparison.auditor.sessions
    # No "Reviewing the answer…" for an answer nobody reviews.
    assert not any(event.get("type") == "answer_check" for event in events)
    # The agent knows, in its own words.
    system = loop.messages[0]["content"]
    assert prompt_defaults.AGENT_REVIEW_FACTS[setting] in system
    assert prompt_defaults.AGENT_REVIEW_FACTS["always"] not in system


def test_in_the_workspace_only_the_reviewers_start_with_its_first_step_and_read_from_the_start(store):
    # Step 0 looks at something else, step 1 reaches for the workspace, step 2 answers.
    script = Audit(tool_steps=2, step_tools={0: "plain"})
    loop = with_tools(audit_loop(store, script, reviewers="workspace"), workspace={"lookup"})
    list(loop.run())
    review = saved(store, loop)["agent_review"]
    assert review["status"] == "succeeded" and review["audit"]["setting"] == "workspace"
    assert [r["provider"] for r in review["audit"]["reviewers"]] == ["anthropic", "openai"]
    # Their first round began at the workspace's step, with the work before it.
    assert script.rounds["anthropic"][0] == "live" and script.rounds["anthropic"][-1] == "final"
    first = next(m for m in script.prompts["openai"] if m["role"] == "user")
    entries, _ = round_entries(first)
    # The work before the workspace is theirs too; the workspace's own result comes in a later round.
    assert any(entry["kind"] == "tool" and entry.get("name") == "plain" for entry in entries)
    assert not any(entry["kind"] == "tool" and entry.get("name") == "lookup" for entry in entries)


def test_the_answer_check_is_off_also_when_the_run_ends_before_the_review(store):
    script = Audit()
    loop = audit_loop(store, script, reviewers="off")
    tools = loop.comparison
    # The answer was fixed, then the run broke off before its review.
    tools.text = ANSWER
    tools.versions.append({"id": 1, "text": ANSWER, "hash": "h", "status": "required", "comparison_ids": []})
    assert tools.auditor.close() is True
    assert tools.review["status"] == "off"


def test_an_always_review_without_reviewers_still_fails(store):
    """The setting is the only reason for "off": reviewers that never started
    under "always" are a failure, as before."""
    script = Audit()
    loop = audit_loop(store, script)
    audit = AnswerAudit(loop.comparison)
    assert not audit.unreviewed
    off = AnswerAudit(loop.comparison, setting="off")
    assert off.unreviewed and off.snapshot()["setting"] == "off"
    assert "setting" not in audit.snapshot()


@pytest.mark.parametrize("setting", ["always", "workspace", "off"])
def test_the_plan_says_who_checks_and_memory_is_the_same_for_every_setting(setting):
    """Memory said who checks a change until 2026-11-02; no change waits now."""
    writable = MemorySnapshot(available=True, enabled=True, auto=True)
    assert agent_memory.orchestrator_prompt(writable).endswith(agent_memory.AUDIT_MEMORY_WRITE_PROMPT)
    description = PlanTools(reviewed=setting != "off").tools()[0].description
    assert ("the reviewers see" in description) is (setting != "off")


def test_the_route_runs_a_message_with_the_setting_its_page_sent(api):
    client, store, calls = api
    chat_id = client.post("/chats", json={"execution_mode": "agent"}, headers=AUTH).json()["chat"]["id"]
    payload = {"chat_id": chat_id, "question": "Hi", "client_request_id": "off-1", "bookmark_id": "bm_off",
               "reviewers": "off"}
    response = client.post("/agent", json=payload, headers=AUTH)
    assert response.status_code == 200 and "event: final" in response.text, response.text
    turn = next(t for t in store.list_turns(UID, chat_id)["turns"] if t["question"] == "Hi")
    saved_turn = store.get_turn(UID, chat_id, turn["id"])
    assert saved_turn["agent_settings"]["reviewers"] == "off"
    assert saved_turn["agent_review"]["status"] == "off" and not calls.reviews
    assert prompt_defaults.AGENT_REVIEW_FACTS["off"] in calls[0]["messages"][0]["content"]
    # A page from before sends none: the reviewers follow, as they did.
    old = {**payload, "client_request_id": "old-1", "question": "Again"}
    old.pop("reviewers")
    assert client.post("/agent", json=old, headers=AUTH).status_code == 200
    again = next(t for t in store.list_turns(UID, chat_id)["turns"] if t["question"] == "Again")
    assert store.get_turn(UID, chat_id, again["id"])["agent_settings"]["reviewers"] == "always"
    assert calls.reviews
    # Not part of the request's identity: the replay recovers whatever it sends now.
    replay = client.post("/agent", json={**payload, "reviewers": "always"}, headers=AUTH)
    assert replay.status_code == 200 and replay.json()["response"] == "A helpful answer"
    assert client.post("/agent", json={**payload, "reviewers": "never"}, headers=AUTH).status_code == 422


def test_the_daily_counters_count_the_setting():
    counters = agent_audit_metrics.turn_counters({"status": "completed"},
                                                 {"review_setting": "off", "reviewers": 0})
    assert counters["review_setting"] == {"off": 1}


def test_the_agent_cannot_switch_off_its_own_reviewers():
    from app.services import agent_settings
    assert "reviewers" not in {entry[0] for entry in agent_settings.DISPLAY.values()}
    assert "whether reviewers check your work" in agent_settings.ELSEWHERE
