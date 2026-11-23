"""The agent's tools keep to their budget (scripts/agent_tool_budget.py,
tests/fixtures/agent_tool_budget.json): which tools a message is offered and
how long each one is. Both go to the model with every step, and a tool more
is one more to choose wrongly."""
import json

from scripts.agent_tool_budget import BUDGET, SLACK, STATES, differences, measure, read_budget, table

CHANGED = (
    "The agent's tools differ from their budget (tests/fixtures/agent_tool_budget.json). Every character of a "
    "tool goes to the model with each step of a message, and each tool more is one more to choose from: where "
    "two fit the same wish, the model picks the wrong one. First shorten the text, or do without the tool. Where "
    "the change is meant, take the new numbers in the same commit:\n"
    "  venv/Scripts/python.exe scripts/agent_tool_budget.py --write\n\n")


def test_the_agents_tools_keep_to_their_budget():
    measured = measure()
    lines = differences(measured, read_budget())
    assert not lines, CHANGED + "\n".join(lines) + "\n\n" + table(measured)


def test_the_budget_names_both_states_of_a_message_in_order():
    budget = read_budget()
    assert tuple(budget) == STATES
    for state in STATES:
        assert budget[state] and list(budget[state]) == sorted(budget[state])
        assert all(type(count) is int and count > 0 for count in budget[state].values())
    # The workspace's tools come with open_workspace, never before it.
    assert "open_workspace" in budget["closed"] and not set(budget["closed"]) & set(budget["workspace"])
    # As --write writes it: a hand-edited number keeps the file's form.
    assert BUDGET.read_text(encoding="utf-8") == json.dumps(budget, indent=2) + "\n"


def test_a_new_a_gone_a_longer_and_a_much_shorter_tool_break_the_budget():
    budget = {"closed": {"read_source": 1000, "web_search": 1000}, "workspace": {"browser": 6000, "vm_exec": 1000}}
    assert differences(budget, budget) == []
    # A little shorter keeps the budget; only more than SLACK under it lowers it.
    kept = {"closed": {"read_source": 1000, "web_search": int(1000 * (1 - SLACK))},
            "workspace": {"browser": 6000, "vm_exec": 999}}
    assert differences(kept, budget) == []
    changed = {"closed": {"read_source": 1001, "web_fetch": 400},
               "workspace": {"browser": 4000, "vm_exec": 1000}}
    assert differences(changed, budget) == [
        "closed: web_fetch is a new tool (400 characters).",
        "closed: web_search is no longer offered: its budget of 1000 goes.",
        "closed: read_source grew to 1001 characters, 1 over its budget of 1000.",
        "workspace: browser shrank to 4000 characters: its budget of 6000 comes down to it.",
    ]
