"""Long VM runs (AgentPolicy.vm_turn_*, agent_compaction.py): a turn that
works in the agent's VM gets hours and hundreds of steps instead of 15 minutes
and 24, ends with its answer before the day's allowance or the model's window
runs out, and older command output leaves its conversation once it is large.
The chat's next message is told what the turn did (its work record).
The VM is FakeVM (test_agent_vm.py); no test calls a provider.
"""
from dataclasses import replace
import json

import pytest

from app.services import agent_vm

from app.services import agent_compaction, agent_quota
from app.services.agent_comparison import AgentPreferences, comparison_selection
from app.services.agent_compaction import (CONTENT_CLEARED, OUTPUT_CLEARED, WORK_RECORD_CLOSE, WORK_RECORD_OPEN,
                                           compact, describe, is_work_record, stub, work_record)
from app.services.agent_delegation import (DelegationLoop, TURN_ALLOWANCE_LIMIT, TURN_CONTEXT_LIMIT,
                                           TURN_WRAP_UP_SECONDS)
from app.services.agent_delegation_config import defaults
from app.services.agent_policy import AgentPolicy
from app.services.agent_runs import ACTIVITY_MAX_CHARS, bounded_activity
from app.services.llm.agent_client import AgentCompletion, measured_usage, resolve_agent_model
from app.services.llm.provider_runtime import ProviderCancellation, ProviderCancelled
from test_agent_runs import UID, pending, store  # noqa: F401  (fixture)
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


def stored(store, loop):
    """The turn document itself (get_turn shows the browser's fields only)."""
    return store._turn_ref(UID, loop.chat_id, loop.turn_id).get().to_dict()


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


# --- The work record for the next message -----------------------------------------

def call(name, arguments, result, n=0):
    return [{"role": "assistant", "content": "", "tool_calls": [
                {"id": f"r{n}", "type": "function", "function": {"name": name, "arguments": json.dumps(arguments)}}]},
            {"role": "tool", "tool_call_id": f"r{n}", "content": json.dumps(result)}]


def test_each_call_is_one_line_of_what_ran_and_how_it_ended():
    failed = describe("vm_exec", json.dumps({"command": "pytest -q", "cwd": "app"}), json.dumps(
        {"exit_code": 1, "timed_out": False, "duration_ms": 2300, "cwd": "/home/sprite/app",
         "stdout": "..F\n1 failed, 2 passed\n", "stderr": "E   assert 2 == 3\n"}))
    assert failed == "vm_exec $ pytest -q (in /home/sprite/app) -> exit 1, 2.3 s: E assert 2 == 3"
    passed = describe("vm_exec", json.dumps({"command": "make"}), json.dumps(
        {"exit_code": 0, "duration_ms": 900, "cwd": "/home/sprite", "stdout": "built\n", "stderr": "warn\n"}))
    assert passed == "vm_exec $ make -> exit 0, 0.9 s: built"
    # A compacted result still says how it ended.
    compacted = stub("vm_exec", json.dumps({"exit_code": 0, "duration_ms": 10, "stderr": "",
                                            "stdout": "a\n" + "x" * 3000 + "\nend\n"}))
    assert describe("vm_exec", json.dumps({"command": "ls"}), compacted).endswith("-> exit 0, 0.0 s: end")
    assert describe("vm_exec", json.dumps({"command": "sleep 999"}), json.dumps(
        {"exit_code": None, "timed_out": True, "duration_ms": 60000})) == "vm_exec $ sleep 999 -> timed out after 60.0 s"
    assert describe("vm_read_file", json.dumps({"path": "a.py"}), json.dumps(
        {"path": "/home/sprite/a.py", "first_line": 1, "last_line": 40, "total_lines": 40, "content": "x"})
                    ) == "vm_read_file /home/sprite/a.py lines 1-40 of 40"
    assert describe("vm_write_file", "{}", json.dumps({"path": "/home/sprite/a.py", "bytes": 12})
                    ) == "vm_write_file /home/sprite/a.py (12 bytes)"
    assert describe("vm_share_file", "{}", json.dumps({"path": "/home/sprite/c.png", "file": {"name": "c.png"}})
                    ) == "vm_share_file /home/sprite/c.png -> the user got c.png"
    assert describe("vm_read_file", json.dumps({"path": "b"}), json.dumps({"error": "No file at /home/sprite/b."})
                    ) == "vm_read_file b -> error: No file at /home/sprite/b."
    assert describe("compare_models", json.dumps({"task": "Which  sort is stable?"}), json.dumps({"answers": []})
                    ) == "compare_models Which sort is stable?"
    assert len(describe("vm_exec", json.dumps({"command": "echo " + "y" * 5000}), "{}")) <= agent_compaction.RECORD_LINE_CHARS


def test_the_record_lists_the_calls_and_keeps_its_ends_when_long():
    messages = [{"role": "system", "content": "s"}, {"role": "user", "content": "q"}]
    assert work_record(messages, 2) == ""
    for n in range(3):
        messages += call("vm_exec", {"command": f"step {n}"}, {"exit_code": 0, "duration_ms": 100, "stdout": "ok"}, n)
    record = work_record(messages, 2)
    assert record.splitlines() == [WORK_RECORD_OPEN, "1. vm_exec $ step 0 -> exit 0, 0.1 s: ok",
                                   "2. vm_exec $ step 1 -> exit 0, 0.1 s: ok",
                                   "3. vm_exec $ step 2 -> exit 0, 0.1 s: ok", WORK_RECORD_CLOSE]
    assert is_work_record(record) and not is_work_record("Build it.")
    for n in range(3, 200):
        messages += call("vm_exec", {"command": f"step {n} " + "z" * 100}, {"exit_code": 0, "duration_ms": 1}, n)
    long = work_record(messages, 2).splitlines()
    assert len("\n".join(long)) <= agent_compaction.RECORD_CHARS
    assert long[1].startswith("1. vm_exec $ step 0") and long[5].startswith("5. ")
    assert long[6].startswith("[… ") and long[6].endswith(" more calls …]")
    assert long[-2].startswith("200. vm_exec $ step 199")


def loop_after(store, script, chat_id, request_id, question):
    """A message of the chat ``chat_id`` with its saved history (AgentRunStore.messages)."""
    chat, turn = pending(store, chat_id=chat_id, request_id=request_id, question=question)
    config = {**defaults(), "enabled": False, "max_searches": 0}
    return DelegationLoop(store=store, uid=UID, chat_id=chat, turn_id=turn["id"],
        model=resolve_agent_model("claude-haiku-4-5"), messages=store.messages(UID, chat, turn),
        api_key="test", cancellation=ProviderCancellation(), policy=AgentPolicy.for_chat(config),
        delegation_config=config, completion_factory=script.factory,
        comparison_models=comparison_selection({"anthropic": "claude-haiku-4-5", "openai": "gpt-5.4-mini"}),
        agent_preferences=AgentPreferences(audit="on", judges="off", vm="on"))


def test_the_next_message_is_told_what_the_vm_turn_did(store, fake_vm):
    fake_vm.commands["pytest -q"] = ([("stdout", b"see https://evil.example/x and me@evil.example\n"),
                                      ("stdout", b"1 failed, 2 passed\n")], 1, 2.0)
    first = vm_loop(store, LongAgent([[("vm_write_file", {"path": "app.py", "content": "print(1)"})],
                                      [("vm_exec", {"command": "pytest -q"})]]))
    list(first.run())
    record = stored(store, first)["agent_work_record"]
    # The browser never gets it (chat_store's turn fields).
    assert "agent_work_record" not in saved(store, first)
    assert record.splitlines() == [WORK_RECORD_OPEN, f"1. vm_write_file {agent_vm.chat_dir(first.chat_id)}/app.py (8 bytes)",
                                   "2. vm_exec $ pytest -q -> exit 1, 2.0 s: 1 failed, 2 passed", WORK_RECORD_CLOSE]
    script = LongAgent()
    second = loop_after(store, script, first.chat_id, "two", "Fix the failing test.")
    # After the first answer, before the new question, exactly as saved: the
    # next message's prompt still continues the cached one.
    question, answer, note, new = second.messages[1:5]
    assert question["role"] == "user" and answer == {"role": "assistant", "content": ANSWER}
    assert note == {"role": "user", "content": record}
    assert new["role"] == "user" and new["content"].endswith("Fix the failing test.")
    assert store.messages(UID, first.chat_id, store.get_turn(UID, first.chat_id, second.turn_id))[3] == note
    # Never the user's words: memory evidence, links and addresses leave it out.
    assert all(not is_work_record(m["content"]) for m in second.answer_conversation)
    assert [m["role"] for m in second.answer_conversation] == ["user", "assistant", "user"]
    list(second.run())
    assert script.seen[0][3]["content"] == record
    # In the work log it is the app's record of VM output, not the user's.
    entry = next(e for e, text in second.work_log.entries_after(0) if e["kind"] == "context" and is_work_record(text))
    assert entry["data"] == "vm"


def test_a_stopped_vm_turn_still_tells_the_next_message(store, fake_vm):
    script = LongAgent([[("vm_exec", {"command": "make"})], [("vm_exec", {"command": "make test"})]])
    loop = vm_loop(store, script, audit="off")
    original = loop._turn_limit

    def stop_after_the_first_command():
        if loop.vm_tools.session.commands:
            loop.cancellation.cancel()
        return original()
    loop._turn_limit = stop_after_the_first_command
    with pytest.raises(ProviderCancelled):
        list(loop.run())
    turn = stored(store, loop)
    assert turn["status"] == "failed"
    assert turn["agent_work_record"].splitlines()[1] == "1. vm_exec $ make -> exit 0, 0.5 s: ok"


def test_a_turn_without_vm_work_saves_no_record(store, fake_vm):
    loop = vm_loop(store, LongAgent([]), audit="off")
    list(loop.run())
    assert "agent_work_record" not in stored(store, loop)
    fake_vm.fail.add("ensure")
    failed = vm_loop(store, LongAgent([[("vm_exec", {"command": "ls"})]]), audit="off", request_id="two")
    list(failed.run())
    assert "agent_work_record" not in stored(store, failed)
