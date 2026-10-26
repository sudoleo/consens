"""Long VM runs (AgentPolicy.vm_turn_*, agent_compaction.py): a turn that
works in the agent's VM gets hours and hundreds of steps instead of 15 minutes
and 24, ends with its answer before the day's allowance or the model's window
runs out, and older command output leaves its conversation once it is large.
The VM is FakeVM (test_agent_vm.py); no test calls a provider.
"""
from dataclasses import replace
import json

import pytest

from app.services import agent_compaction, agent_quota
from app.services.agent_compaction import CONTENT_CLEARED, OUTPUT_CLEARED, compact, stub
from app.services.agent_delegation import TURN_ALLOWANCE_LIMIT, TURN_CONTEXT_LIMIT, TURN_WRAP_UP_SECONDS
from app.services.agent_delegation_config import defaults
from app.services.agent_policy import AgentPolicy
from app.services.agent_runs import ACTIVITY_MAX_CHARS, bounded_activity
from app.services.llm.agent_client import AgentCompletion, measured_usage
from test_agent_runs import UID, store  # noqa: F401  (fixture)
from test_agent_vm import ANSWER, Agent, _admin_allowance, fake_vm, results, vm_loop  # noqa: F401  (fixtures)


class LongAgent(Agent):
    """Agent, plus: a step whose tools may not be called (the wrap-up)
    answers, and every step's conversation is kept."""

    def __init__(self, steps=()):
        super().__init__(steps)
        self.seen = []

    def factory(self):
        script = self

        class Completion(AgentCompletion):
            def stream(self, *, model, messages, **kwargs):
                self.usage = measured_usage({"prompt_tokens": 50, "completion_tokens": 20, "cost": .0001}, model)
                index = int(self.step_id.split(":")[1])
                script.seen.append([dict(message) for message in messages])
                script.offered.append([tool["function"]["name"] for tool in kwargs.get("tools") or []
                                       if tool.get("type") == "function"])
                if index < len(script.steps) and kwargs.get("allow_tool_calls") is not False:
                    self.tool_calls = [{"id": f"call_{index}_{n}", "type": "function",
                                        "function": {"name": name, "arguments": json.dumps(arguments)}}
                                       for n, (name, arguments) in enumerate(script.steps[index])]
                    self.finish_reason = "tool_calls"
                    return
                self.text, self.finish_reason = ANSWER, "stop"
                yield {"type": "delta", "text": self.text}
        return Completion()


def saved(store, loop):
    return store.get_turn(UID, loop.chat_id, loop.turn_id)


# --- Limits -----------------------------------------------------------------------

def test_a_vm_turn_has_its_own_limits_and_a_bounded_run_none():
    chat = AgentPolicy.for_chat(defaults())
    assert (chat.vm_turn_steps, chat.vm_turn_seconds) == (200, 7200)
    assert chat.snapshot()["vm_turn_seconds"] == 7200
    bounded = AgentPolicy.from_config({**defaults(), "enabled": True})
    assert "vm_turn_steps" not in bounded.snapshot() and "vm_turn_seconds" not in bounded.snapshot()


def test_a_turn_is_a_long_run_from_its_first_vm_call_on(store, fake_vm):
    loop = vm_loop(store, LongAgent([[("vm_exec", {"command": "ls"})]]), audit="off")
    assert loop._turn_seconds() == 900 and loop._turn_steps() == 24
    list(loop.run())
    assert loop._long_run() is True
    assert loop._turn_seconds() == 7200 and loop._turn_steps() == 200
    loop.turn_started, loop.clock = 0.0, lambda: 7200 + TURN_WRAP_UP_SECONDS - 60
    assert loop._hard_stop_left() == 60


def test_a_vm_that_never_started_keeps_the_short_limits(store, fake_vm):
    fake_vm.fail.add("ensure")
    loop = vm_loop(store, LongAgent([[("vm_exec", {"command": "ls"})]]), audit="off")
    list(loop.run())
    assert loop._long_run() is False and loop._turn_steps() == 24


def test_a_long_run_takes_more_than_the_usual_24_steps(store, fake_vm):
    script = LongAgent([[("vm_exec", {"command": f"make step{n}"})] for n in range(30)])
    loop = vm_loop(store, script, audit="off")
    list(loop.run())
    turn = saved(store, loop)
    assert turn["status"] == "completed" and turn["consensus"] == ANSWER
    assert turn["agent_vm"]["commands"] == 30 and len(script.seen) == 31


def test_a_long_run_at_its_step_limit_writes_the_answer_from_its_own_work(store, fake_vm):
    """Without a comparison a short turn stops at its limit; a VM run's own
    work carries the answer (one last step, tools listed but not callable)."""
    script = LongAgent([[("vm_exec", {"command": f"make step{n}"})] for n in range(10)])
    loop = vm_loop(store, script, audit="off")
    loop.policy = replace(loop.policy, vm_turn_steps=3)
    list(loop.run())
    turn = saved(store, loop)
    assert turn["status"] == "completed" and turn["consensus"] == ANSWER
    assert turn["agent_vm"]["commands"] == 3
    last = script.seen[-1][-1]
    assert last["role"] == "user" and "Write the answer now from what you have" in last["content"]


def test_a_long_run_ends_with_its_answer_before_the_allowance_runs_out(store, fake_vm, monkeypatch):
    left = [10_000_000]
    monkeypatch.setattr(agent_quota, "remaining_tokens", lambda db, uid: left[0])
    script = LongAgent([[("vm_exec", {"command": f"make step{n}"})] for n in range(10)])
    loop = vm_loop(store, script, audit="off")
    original = loop._turn_limit

    def limit():
        if loop.vm_tools.session.commands >= 2:
            left[0] = 1_000
        return original()
    loop._turn_limit = limit
    list(loop.run())
    turn = saved(store, loop)
    assert turn["status"] == "completed" and turn["consensus"] == ANSWER
    assert turn["agent_vm"]["commands"] == 2
    assert loop._long_run_limit() == TURN_ALLOWANCE_LIMIT


def test_a_long_run_ends_with_its_answer_before_the_context_window_is_full(store, fake_vm):
    script = LongAgent([[("vm_exec", {"command": "ls"})], [("vm_exec", {"command": "pwd"})]])
    loop = vm_loop(store, script, audit="off")
    list(loop.run())
    assert loop._long_run_limit() is None
    loop.model = replace(loop.model, context_length=1_000)
    assert loop._long_run_limit() == TURN_CONTEXT_LIMIT


def test_a_short_turn_never_reads_the_allowance_between_steps(store, fake_vm, monkeypatch):
    def unexpected(db, uid):
        raise AssertionError("read the allowance")
    monkeypatch.setattr(agent_quota, "remaining_tokens", unexpected)
    loop = vm_loop(store, LongAgent([]), audit="off")
    list(loop.run())
    assert saved(store, loop)["status"] == "completed"


# --- Compaction -------------------------------------------------------------------

def exec_result(n, size):
    return json.dumps({"exit_code": n % 2, "timed_out": False, "duration_ms": 1200, "cwd": "/home/sprite",
                       "stdout": f"start {n}\n" + "x" * size + f"\nlast line {n}\n", "stderr": ""})


def conversation(results_):
    """System, question, then one assistant call and its result per entry
    of ``results_`` (``(name, content)``)."""
    messages = [{"role": "system", "content": "Answer."}, {"role": "user", "content": "Build it."}]
    for n, (name, content) in enumerate(results_):
        messages.append({"role": "assistant", "content": "", "tool_calls": [
            {"id": f"c{n}", "type": "function", "function": {"name": name, "arguments": "{}"}}]})
        messages.append({"role": "tool", "tool_call_id": f"c{n}", "content": content})
    return messages


def test_compaction_waits_for_its_mark_and_keeps_the_newest_results_whole(monkeypatch):
    monkeypatch.setattr(agent_compaction, "COMPACT_ABOVE_CHARS", 50_000)
    monkeypatch.setattr(agent_compaction, "KEEP_RECENT_CHARS", 20_000)
    monkeypatch.setattr(agent_compaction, "MIN_GAIN_CHARS", 5_000)
    small = conversation([("vm_exec", exec_result(n, 9_000)) for n in range(4)])
    assert compact(small, 2) is None
    messages = conversation([("vm_exec", exec_result(n, 9_000)) for n in range(8)]
                            + [("compare_models", json.dumps({"answers": ["y" * 9_000]}))])
    cut = compact(messages, 2)
    changed = [index for index, _ in cut.replacements]
    # The six oldest commands; the two newest stay whole, and so does the
    # comparison (not a VM tool, and the newest batch).
    assert changed == [3 + 2 * n for n in range(6)]
    assert cut.after < cut.before - 5_000 and cut.summary()["tool_call_ids"] == [f"c{n}" for n in range(6)]
    first = json.loads(cut.replacements[0][1]["content"])
    assert first["compacted"] == OUTPUT_CLEARED and first["exit_code"] == 0 and first["duration_ms"] == 1200
    assert first["stdout_end"].endswith("last line 0\n") and len(first["stdout_end"]) <= agent_compaction.TAIL_CHARS
    assert "stderr_end" not in first
    # Only the content changes: the call id, and the assistant messages untouched.
    assert cut.replacements[0][1]["tool_call_id"] == "c0" and cut.replacements[0][1]["role"] == "tool"
    assert messages[3]["content"] == exec_result(0, 9_000)


def test_compaction_never_cuts_for_a_small_gain_or_twice(monkeypatch):
    monkeypatch.setattr(agent_compaction, "COMPACT_ABOVE_CHARS", 30_000)
    monkeypatch.setattr(agent_compaction, "KEEP_RECENT_CHARS", 10_000)
    messages = conversation([("vm_exec", exec_result(n, 9_000)) for n in range(4)])
    # Two old results to cut (the newest batch and one more stay): together
    # below MIN_GAIN_CHARS (30k), so no cut.
    assert compact(messages, 2) is None
    monkeypatch.setattr(agent_compaction, "MIN_GAIN_CHARS", 1_000)
    cut = compact(messages, 2)
    for index, message in cut.replacements:
        messages[index] = message
    # What is cut stays a stub: nothing more to win, nothing changes.
    assert compact(messages, 2) is None


def test_a_compacted_file_read_keeps_where_it_was_and_the_inputs():
    content = json.dumps({"path": "/home/sprite/app.py", "first_line": 1, "last_line": 400, "total_lines": 900,
                          "content": "print()\n" * 400, "input_dir": "/home/sprite/input",
                          "inputs": ["/home/sprite/input/data.csv"]})
    short = json.loads(stub("vm_read_file", content))
    assert short == {"path": "/home/sprite/app.py", "first_line": 1, "last_line": 400, "total_lines": 900,
                     "input_dir": "/home/sprite/input", "inputs": ["/home/sprite/input/data.csv"],
                     "compacted": CONTENT_CLEARED}
    assert json.loads(stub("vm_exec", "not json"))["compacted"] == OUTPUT_CLEARED


def test_a_long_run_compacts_old_output_and_the_work_log_says_so(store, fake_vm, monkeypatch):
    monkeypatch.setattr(agent_compaction, "COMPACT_ABOVE_CHARS", 40_000)
    monkeypatch.setattr(agent_compaction, "KEEP_RECENT_CHARS", 15_000)
    monkeypatch.setattr(agent_compaction, "MIN_GAIN_CHARS", 5_000)
    for n in range(8):
        fake_vm.commands[f"make step{n}"] = ([("stdout", (f"step {n}\n" + "y" * 10_000 + "\ndone\n").encode())], 0, 1.0)
    script = LongAgent([[("vm_exec", {"command": f"make step{n}"})] for n in range(8)])
    loop = vm_loop(store, script)
    list(loop.run())
    assert saved(store, loop)["status"] == "completed"
    tools = [json.loads(m["content"]) for m in loop.messages if m.get("role") == "tool"]
    assert tools[0]["compacted"] == OUTPUT_CLEARED and tools[0]["stdout_end"].endswith("done\n")
    assert "compacted" not in tools[-1] and tools[-1]["stdout"].startswith("step 7\n")
    # The model's later steps read the stub in place of the old output.
    assert json.loads(script.seen[-1][3]["content"])["compacted"] == OUTPUT_CLEARED
    # The reviewers keep the whole result, and the cut is in the log.
    entries = loop.work_log.entries_after(0)
    first = next(text for entry, text in entries if entry["kind"] == "tool")
    assert json.loads(first)["stdout"].startswith("step 0\n")
    compactions = [json.loads(text) for entry, text in entries if entry["kind"] == "app" and entry["name"] == "compacted"]
    assert compactions and compactions[0]["tool_call_ids"][0] == "call_0_0"


def test_a_short_turn_is_never_compacted(store, fake_vm, monkeypatch):
    monkeypatch.setattr(agent_compaction, "COMPACT_ABOVE_CHARS", 0)
    loop = vm_loop(store, LongAgent([]), audit="off")
    called = []
    monkeypatch.setattr(agent_compaction, "compact", lambda *args: called.append(args))
    list(loop.run())
    assert called == []


# --- What a long run saves --------------------------------------------------------

def test_the_saved_activity_stays_within_its_size_dropping_old_output_first():
    events = [{"id": f"completion:{n}:call/tool", "kind": "tool", "name": "vm_exec", "status": "succeeded",
               "command": f"make {n}", "output": "z" * 2_000, "output_truncated": False} for n in range(400)]
    small = events[:10]
    assert bounded_activity(small) is small
    bounded = bounded_activity(events)
    assert len(json.dumps(bounded)) <= ACTIVITY_MAX_CHARS and len(bounded) == 400
    assert bounded[0]["output"] == "" and bounded[0]["output_truncated"] is True
    assert bounded[-1]["output"] == "z" * 2_000 and bounded[-1]["command"] == "make 399"
    # The caller's events are not changed.
    assert events[0]["output"] == "z" * 2_000


def test_a_long_activity_is_saved_with_the_turn(store, fake_vm, monkeypatch):
    monkeypatch.setattr("app.services.agent_runs.ACTIVITY_MAX_CHARS", 14_000)
    for n in range(10):
        fake_vm.commands[f"make step{n}"] = ([("stdout", ("w" * 1_500).encode())], 0, 1.0)
    loop = vm_loop(store, LongAgent([[("vm_exec", {"command": f"make step{n}"})] for n in range(10)]),
                   audit="off")
    list(loop.run())
    activity = saved(store, loop)["agent_activity"]
    assert len(json.dumps(loop.completion.activity)) > 20_000 >= 14_000 >= len(json.dumps(activity))
    commands = [event for event in activity if event.get("name") == "vm_exec"]
    assert len(commands) == 10 and commands[0]["output"] == "" and commands[0]["output_truncated"] is True
    assert commands[-1]["output"] == "w" * 1_500
