"""How much of the agent's context its tools take, against a budget.

Every tool the agent is offered goes to the model with each step of a
message: its name, its description and its arguments. A tool more is one more
to choose from, and where two of them fit the same wish the model picks the
wrong one. So the tools of a message and the size of each stand in
tests/fixtures/agent_tool_budget.json, and tests/test_agent_tool_budget.py
fails when a tool is new, gone, longer than its budget, or so much shorter
that the budget would let it grow back unnoticed.

Measured is a new chat's first message as the Agent route builds it
(agent_warmup.message_run), with everything the service can have configured:
its own web search, the picture search, GitHub, a chat model that takes
pictures and a host for apps. ``closed`` are the tools it starts with,
``workspace`` those the open workspace adds. Tools that come with an
account's own switches or data (memory, Google, attached files, helpers) are
not in it.

  venv/Scripts/python.exe scripts/agent_tool_budget.py           the table, and what differs from the budget
  venv/Scripts/python.exe scripts/agent_tool_budget.py --write   take the measured numbers as the budget
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUDGET = ROOT / "tests" / "fixtures" / "agent_tool_budget.json"
STATES = ("closed", "workspace")
# How far under its budget a tool's text may be before the budget is lowered
# to it: a shortened description must not be free room for the next one.
SLACK = 0.10


def size(tool) -> int:
    """The characters of the tool as the model gets it (ReadOnlyTool.schema)."""
    return len(json.dumps(tool.schema(), ensure_ascii=False))


def measure() -> dict[str, dict[str, int]]:
    """``{"closed": {name: characters}, "workspace": {...}}`` of the fullest
    first message the service builds, without a database, a VM or a model."""
    from unittest import mock

    from app.services import agent_github, agent_vm, agent_vm_tools, agent_warmup, exa, picture_search
    with mock.patch.dict(os.environ, {"AGENT_APP_HOST": "apps.example.com"}), \
            mock.patch.object(agent_vm, "configured", lambda: True), \
            mock.patch.object(exa, "available", lambda: True), \
            mock.patch.object(picture_search, "enabled", lambda: True), \
            mock.patch.object(agent_github, "configured", lambda: True), \
            mock.patch.object(agent_vm_tools, "sees_pictures", lambda model: True):
        loop = agent_warmup.message_run()
        return {"closed": {tool.name: size(tool) for tool in loop.registry.tools.values()},
                "workspace": {tool.name: size(tool) for tool in loop._workspace_tool_list()}}


def read_budget() -> dict[str, dict[str, int]]:
    return json.loads(BUDGET.read_text(encoding="utf-8"))


def differences(measured, budget) -> list[str]:
    """What the measured tools break of the budget, a line each; none when they keep it."""
    lines = []
    for state in STATES:
        have, allowed = measured.get(state, {}), budget.get(state, {})
        for name in sorted(set(have) - set(allowed)):
            lines.append(f"{state}: {name} is a new tool ({have[name]} characters).")
        for name in sorted(set(allowed) - set(have)):
            lines.append(f"{state}: {name} is no longer offered: its budget of {allowed[name]} goes.")
        for name in sorted(set(have) & set(allowed)):
            if have[name] > allowed[name]:
                lines.append(f"{state}: {name} grew to {have[name]} characters, {have[name] - allowed[name]} over "
                             f"its budget of {allowed[name]}.")
            elif have[name] < allowed[name] * (1 - SLACK):
                lines.append(f"{state}: {name} shrank to {have[name]} characters: its budget of {allowed[name]} "
                             "comes down to it.")
    return lines


def table(measured) -> str:
    rows = []
    for state in STATES:
        tools = measured[state]
        rows.append(f"{state}: {len(tools)} tools, {sum(tools.values())} characters")
        rows += [f"  {count:>6}  {name}" for name, count in sorted(tools.items(), key=lambda item: -item[1])]
    return "\n".join(rows)


def main(argv) -> int:
    measured = measure()
    print(table(measured))
    if "--write" in argv:
        BUDGET.write_text(json.dumps({state: dict(sorted(measured[state].items())) for state in STATES}, indent=2)
                          + "\n", encoding="utf-8", newline="\n")
        print(f"\nWritten to {BUDGET.relative_to(ROOT).as_posix()}.")
        return 0
    lines = differences(measured, read_budget()) if BUDGET.exists() else ["No budget yet: run with --write."]
    if lines:
        print("\n" + "\n".join(lines))
    return 1 if lines else 0


if __name__ == "__main__":
    # The app's modules without its database, as the tests load them.
    os.environ.setdefault("UNIT_TEST_MODE", "1")
    sys.path.insert(0, str(ROOT))
    sys.exit(main(sys.argv[1:]))
