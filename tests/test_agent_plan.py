"""The agent's plan (update_plan, agent_plan.py): a checklist the user sees in
the activity and the reviewers hold against the work in the log. Offered with
the VM, where tasks run long. The VM is FakeVM (test_agent_vm.py).
"""
import json

import pytest

from app.services import agent_audit, prompt_defaults
from app.services.agent_answer_mode import SIDE_TOOLS
from app.services.agent_compaction import describe
from app.services.agent_plan import UpdatePlanArgs
from app.services.llm.agent_client import AgentCompletion, measured_usage
from test_agent_runs import UID, store  # noqa: F401  (fixture)
from test_agent_vm import (ANSWER, Agent, _admin_allowance, fake_vm, results, tool_events,  # noqa: F401  (fixtures)
                           vm_loop)

PLAN = [{"content": "Read the  data", "status": "completed"}, {"content": "Fit the model", "status": "in_progress"},
        {"content": "Plot the result", "status": "pending"}]


def test_the_plan_comes_with_the_vm(store, fake_vm):
    with_vm, without = Agent(), Agent()
    list(vm_loop(store, with_vm).run())
    list(vm_loop(store, without, vm="off", request_id="two").run())
    assert "update_plan" in with_vm.offered[0] and prompt_defaults.AGENT_PLAN_PROMPT in with_vm.systems[0]
    assert "update_plan" not in without.offered[0] and prompt_defaults.AGENT_PLAN_PROMPT not in without.systems[0]


def test_the_plan_is_in_the_activity_and_the_work_log(store, fake_vm):
    script = Agent([[("update_plan", {"items": PLAN})], [("vm_exec", {"command": "python fit.py"})],
                    [("update_plan", {"items": [{**step, "status": "completed"} for step in PLAN]})]])
    loop = vm_loop(store, script)
    events = list(loop.run())
    first, _, last = results(loop)
    assert first == {"status": "updated", "done": 1, "total": 3, "in_progress": "Fit the model"}
    assert last == {"status": "updated", "done": 3, "total": 3, "in_progress": None}
    # The activity carries the whole list each time, as the browser shows it.
    plans = [e for e in tool_events(events, "update_plan") if e["status"] == "succeeded"]
    assert plans[0]["items"][0] == {"content": "Read the data", "status": "completed"}
    assert [step["status"] for step in plans[-1]["items"]] == ["completed"] * 3
    saved = [e for e in store.get_turn(UID, loop.chat_id, loop.turn_id)["agent_activity"] if e.get("name") == "update_plan"]
    assert len(saved) == 2 and saved[0]["items"][1]["status"] == "in_progress"
    # The reviewers: the call in the agent's step, its result as the agent's
    # data, and the last plan at the end to hold against the work.
    entries = loop.work_log.entries_after(0)
    step = next(json.loads(text) for entry, text in entries if entry["kind"] == "step"
                and json.loads(text)["tool_calls"] and json.loads(text)["tool_calls"][0]["name"] == "update_plan")
    assert json.loads(step["tool_calls"][0]["arguments"])["items"] == PLAN
    tool = next(entry for entry, _ in entries if entry["kind"] == "tool" and entry["name"] == "update_plan")
    assert tool["data"] == "agent"
    end = json.loads(next(text for entry, text in entries if entry["kind"] == "end"))
    assert [step["status"] for step in end["plan"]] == ["completed"] * 3


def test_one_step_at_a_time_and_a_bounded_list(store, fake_vm):
    loop = vm_loop(store, Agent([[("update_plan", {"items": [{"content": "A", "status": "in_progress"},
                                                             {"content": "B", "status": "in_progress"}]})]]))
    list(loop.run())
    assert "at most one step in_progress" in results(loop)[0]["error"]
    end = json.loads(next(text for entry, text in loop.work_log.entries_after(0) if entry["kind"] == "end"))
    assert end["plan"] is None
    with pytest.raises(ValueError):
        UpdatePlanArgs(items=[])
    with pytest.raises(ValueError):
        UpdatePlanArgs(items=[{"content": "x", "status": "pending"}] * 21)
    with pytest.raises(ValueError):
        UpdatePlanArgs(items=[{"content": "x", "status": "skipped"}])


class Saying(Agent):
    """A scripted agent whose steps may also say something: ``steps[N]`` is
    (text, calls); the step after the last one answers ANSWER."""

    def factory(self):
        script = self

        class Completion(AgentCompletion):
            def stream(self, *, model, messages, **kwargs):
                self.usage = measured_usage({"prompt_tokens": 50, "completion_tokens": 20, "cost": .0001}, model)
                index = int(self.step_id.split(":")[1])
                text, calls = script.steps[index] if index < len(script.steps) else (ANSWER, [])
                if text:
                    self.text = text
                    yield {"type": "delta", "text": text}
                self.tool_calls = [{"id": f"call_{index}_{n}", "type": "function",
                                    "function": {"name": name, "arguments": json.dumps(arguments)}}
                                   for n, (name, arguments) in enumerate(calls)]
                self.finish_reason = "tool_calls" if calls else "stop"
        return Completion()


def test_a_note_with_a_plan_update_mid_task_is_no_answer(store, fake_vm):
    # Claude says a sentence before it updates the plan as it goes: that is
    # a preamble and the run goes on. Only a finished plan comes with the answer.
    done = [{**step, "status": "completed"} for step in PLAN]
    script = Saying([("Data is read. Next I fit the model.", [("update_plan", {"items": PLAN})]),
                     ("", [("vm_exec", {"command": "python fit.py"})]),
                     ("The model is fitted: slope 0.4.", [("update_plan", {"items": done})])])
    loop = vm_loop(store, script, audit="off")
    list(loop.run())
    assert any(call["arguments"] == '{"command": "python fit.py"}' for m in loop.messages
               for call in (c["function"] for c in m.get("tool_calls") or []))
    turn = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert turn["status"] == "completed" and turn["consensus"] == "The model is fitted: slope 0.4."


def test_the_plan_may_come_with_the_answer_and_the_reviewers_compare_it():
    # An answer whose step also closes the plan stands (agent_answer_mode).
    assert "update_plan" in SIDE_TOOLS
    assert "update_plan" in agent_audit.REVIEW_PROMPT_BODY and "hold the plan against the log" in agent_audit.REVIEW_PROMPT_BODY
    # The next message's work record says where the plan stood.
    assert describe("update_plan", "{}", json.dumps({"status": "updated", "done": 1, "total": 3,
                                                     "in_progress": "Fit the model"})
                    ) == "update_plan: 1 of 3 steps done, now: Fit the model"
