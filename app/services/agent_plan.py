"""The agent's plan for a long task (update_plan, like Claude Code's todo list).

Offered with the agent's VM (AgentPreferences.vm, DelegationLoop), where a
message may run for hours. Each call replaces the whole list: what the agent
means to do, one step in progress while it works on it, each step completed
once done. The plan is the agent's declared intent, written by the model, so
it is data like any model output, never an instruction to anyone.

Who sees it: the user in the activity (agent-activity.js: the latest plan
pinned above the live progress, each change as a checklist in the timeline),
the reviewers in the work log (the call in the agent's ``step`` entry, the
result in its ``tool`` entry, the last plan in the ``end`` entry): they compare
the plan with what the agent did (agent_audit.REVIEW_PROMPT_BODY). It changes
nothing outside the run; an answer may come with a last update (SIDE_TOOLS).
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.services.agent_tools import ReadOnlyTool

MAX_ITEMS = 20


class PlanItem(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    content: str = Field(min_length=1, max_length=200, description="One step, as a short imperative.")
    status: Literal["pending", "in_progress", "completed"]


class UpdatePlanArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    items: list[PlanItem] = Field(min_length=1, max_length=MAX_ITEMS,
                                  description="The whole plan in order; it replaces the previous one.")


class PlanTools:
    """The plan of one message (DelegationLoop.plan_tools)."""

    def __init__(self):
        # The latest plan, as the agent last wrote it ([] before the first).
        self.items = []

    def tools(self):
        return [ReadOnlyTool("update_plan", "Write your plan for this task as a checklist the user and the "
                             "reviewers see: the whole list each time, one step in_progress while you work on it, "
                             "completed once done.", UpdatePlanArgs, self.update, activity=self._activity)]

    def update(self, args, *, cancellation):
        items = [{"content": " ".join(item.content.split()), "status": item.status} for item in args.items]
        if sum(item["status"] == "in_progress" for item in items) > 1:
            raise ValueError("Mark at most one step in_progress: the one you are working on now.")
        self.items = items
        current = next((item["content"] for item in items if item["status"] == "in_progress"), None)
        return {"status": "updated", "done": sum(item["status"] == "completed" for item in items),
                "total": len(items), "in_progress": current}

    def _activity(self, args, result):
        if isinstance(result, dict) and "error" in result:
            return {}
        return {"items": [{"content": " ".join(item.content.split()), "status": item.status} for item in args.items]}
