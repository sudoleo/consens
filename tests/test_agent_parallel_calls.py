"""Several calls per step at the same time (DelegationLoop._call_groups,
_execute_together): neighbouring calls of tools that only read
(ReadOnlyTool.concurrent) run together, every other call on its own, in the
step's order. Each call keeps exactly one result, in call order, its own live
events and its own work log entry. Fakes only: no model, no VM provider, no
Firestore.
"""
import json
import threading
import time

from pydantic import BaseModel, ConfigDict
import pytest

from app.services import agent_delegation
from app.services.agent_tools import ReadOnlyTool, ToolRegistry
from app.services.llm.provider_runtime import ProviderCancelled
from test_agent_runs import UID, store  # noqa: F401  (fixture)
from test_agent_vm import fake_vm, vm_loop  # noqa: F401  (fixture)
from test_agent_runtime_audit import HALT, Steps, every_call_answered, ran, tool_results


class ProbeArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    name: str
    seconds: float = 0


class Probes:
    """``read`` (concurrent) and ``write`` (not): each call records when it
    ran, runs its name's hook first and then takes ``seconds``, watching for
    Stop."""

    def __init__(self):
        self.lock = threading.Lock()
        self.spans, self.runs, self.cancelled = {}, [], []
        self.hooks = {}

    def run(self, args, *, cancellation):
        start = time.monotonic()
        with self.lock:
            self.runs.append(args.name)
        hook = self.hooks.get(args.name)
        if hook is not None:
            hook()
        while time.monotonic() < start + args.seconds:
            if cancellation.cancelled:
                with self.lock:
                    self.cancelled.append(args.name)
                cancellation.raise_if_cancelled()
            time.sleep(.01)
        if args.name.startswith("fail"):
            raise ValueError(f"{args.name} could not be read")
        with self.lock:
            self.spans[args.name] = (start, time.monotonic())
        return {"read": args.name}


def read(name, seconds=0):
    return "read", {"name": name, "seconds": seconds}


def write(name, seconds=0):
    return "write", {"name": name, "seconds": seconds}


def probe_loop(store, steps, probes, **kwargs):
    loop = vm_loop(store, Steps(steps), **{"vm": "off", **kwargs})
    loop.registry = ToolRegistry([*loop.registry.tools.values(),
                                  ReadOnlyTool("read", "Read.", ProbeArgs, probes.run, concurrent=True),
                                  ReadOnlyTool("write", "Write.", ProbeArgs, probes.run)],
                                 argument_limit=loop.registry.argument_limit)
    return loop


def tool_events(events):
    return [e for e in events if e.get("type") == "activity" and e.get("kind") == "tool"]


def test_reads_of_a_step_run_at_the_same_time_and_answer_in_the_calls_order(store):
    probes = Probes()
    # Sequential calls could never all pass the barrier: the first would wait alone.
    together = threading.Barrier(3, timeout=5)
    probes.hooks = {"a": together.wait, "b": together.wait, "c": together.wait}
    loop = probe_loop(store, [[read("a", .6), read("b", .3), read("c", .1)]], probes)
    events = list(loop.run())
    assert set(probes.spans) == {"a", "b", "c"}
    # The group takes about as long as its longest call, not the sum (1.0 s).
    first = min(start for start, _ in probes.spans.values())
    last = max(end for _, end in probes.spans.values())
    assert .6 <= last - first < .95
    # Results in call order, although c ended first.
    assert probes.spans["c"][1] < probes.spans["a"][1]
    tools = [m for m in loop.messages if m.get("role") == "tool"]
    assert [m["tool_call_id"] for m in tools] == ["call_0_0", "call_0_1", "call_0_2"]
    assert [json.loads(m["content"]) for m in tools] == [{"read": "a"}, {"read": "b"}, {"read": "c"}]
    # One work log entry per call, in call order, each with its own start and duration.
    entries = [entry for entry, _ in loop.work_log.entries_after(0) if entry["kind"] == "tool"]
    assert [entry["name"] for entry in entries] == ["read"] * 3
    durations = [entry["duration_ms"] for entry in entries]
    assert durations[0] > durations[1] > durations[2] and all("started_at" in entry for entry in entries)
    # Live events per call id, each in its own step.
    shown = tool_events(events)
    for n in range(3):
        mine = [e for e in shown if e["id"] == f"completion:0:call_0_{n}/tool"]
        assert {e["status"] for e in mine} == {"running", "succeeded"}
    assert all(e["id"] == f"{e['step_id']}/tool" for e in shown)


def test_a_call_that_changes_something_runs_alone_between_the_reads(store):
    probes = Probes()
    first, second = threading.Barrier(2, timeout=5), threading.Barrier(2, timeout=5)
    probes.hooks = {"a": first.wait, "b": first.wait, "c": second.wait, "d": second.wait}
    loop = probe_loop(store, [[read("a", .1), read("b", .1), write("w", .1), read("c", .1), read("d", .1)]],
                      probes)
    list(loop.run())
    spans = probes.spans
    assert set(spans) == {"a", "b", "w", "c", "d"}
    assert spans["w"][0] >= max(spans["a"][1], spans["b"][1])
    assert min(spans["c"][0], spans["d"][0]) >= spans["w"][1]
    assert [json.loads(m["content"]) for m in loop.messages if m.get("role") == "tool"] == [
        {"read": name} for name in "abwcd"]


def test_calls_that_change_something_run_one_after_another_in_the_steps_order(store):
    probes = Probes()
    loop = probe_loop(store, [[write("x", .05), write("y"), write("z")]], probes)
    list(loop.run())
    assert probes.runs == ["x", "y", "z"]
    assert probes.spans["x"][1] <= probes.spans["y"][0] <= probes.spans["y"][1] <= probes.spans["z"][0]


@pytest.mark.parametrize("decision, expected", [("continue", agent_delegation.CALL_AFTER_PAUSE),
                                                ("steer", agent_delegation.HOLD_STEERED)])
def test_a_halt_before_a_group_ends_the_whole_group(store, decision, expected):
    from test_agent_audit import decide_when_held
    probes = Probes()
    loop = probe_loop(store, [[write("w"), read("a"), read("b")]], probes)
    probes.hooks = {"w": lambda: loop.request_hold(dict(HALT))}
    waiter = decide_when_held(loop, store, decision, "Not those pages.")
    list(loop.run())
    waiter.join(5)
    found = tool_results(loop)
    assert found["call_0_0"] == {"read": "w"}
    assert found["call_0_1"] == found["call_0_2"] == {"error": expected}
    assert probes.runs == ["w"] and every_call_answered(loop)


def test_a_halt_while_a_group_runs_lets_it_finish_and_ends_the_steps_later_calls(store):
    from test_agent_audit import decide_when_held
    probes = Probes()
    loop = probe_loop(store, [[read("a", .2), read("b", .2), write("w")]], probes)
    probes.hooks = {"a": lambda: loop.request_hold(dict(HALT))}
    waiter = decide_when_held(loop, store, "continue")
    list(loop.run())
    waiter.join(5)
    found = tool_results(loop)
    assert found["call_0_0"] == {"read": "a"} and found["call_0_1"] == {"read": "b"}
    assert found["call_0_2"] == {"error": agent_delegation.CALL_AFTER_PAUSE} and "w" not in probes.runs


def test_stop_during_a_group_ends_every_call_of_it(store):
    probes = Probes()
    loop = probe_loop(store, [[read("a", 5), read("b", 5), write("w")]], probes)
    # The user's Stop once both calls run (agent_background.stop cancels the run).
    started = threading.Barrier(2, timeout=5, action=loop.cancellation.cancel)
    probes.hooks = {"a": started.wait, "b": started.wait}
    began = time.monotonic()
    with pytest.raises(ProviderCancelled):
        list(loop.run())
    assert time.monotonic() - began < 3
    # Both calls saw the Stop and had ended before the run did; nothing after them ran.
    assert sorted(probes.cancelled) == ["a", "b"] and "w" not in probes.runs and not probes.spans


def test_a_failing_read_costs_only_its_own_result(store):
    probes = Probes()
    loop = probe_loop(store, [[read("a"), read("fail-b"), read("c")]], probes)
    list(loop.run())
    found = tool_results(loop)
    assert found["call_0_0"] == {"read": "a"} and found["call_0_2"] == {"read": "c"}
    assert found["call_0_1"] == {"error": "fail-b could not be read"}


def test_the_same_read_twice_in_a_group_runs_once(store):
    probes = Probes()
    loop = probe_loop(store, [[read("a"), read("b"), read("a")]], probes)
    list(loop.run())
    found = tool_results(loop)
    assert found["call_0_2"] == {"error": agent_delegation.CALL_REPEATED}
    assert sorted(probes.runs) == ["a", "b"] and every_call_answered(loop)


def test_the_repeat_guard_counts_each_call_of_a_group_in_order(store):
    probes = Probes()
    assert loop_limit(store) == 2
    loop = probe_loop(store, [[read("a")], [read("a"), read("b")], [read("b"), read("a")], [read("c"), read("a")]],
                      probes)
    list(loop.run())
    found = tool_results(loop)
    # The third identical call is refused, its neighbour runs.
    assert found["call_2_0"] == {"read": "b"} and "is not run again" in found["call_2_1"]["error"]
    # The fourth ends the response: the call before it in its group still runs.
    assert found["call_3_0"] == {"read": "c"}
    assert found["call_3_1"] == {"error": agent_delegation.CALL_AT_LIMIT}
    assert probes.runs.count("a") == 2 and every_call_answered(loop)
    turn = store._turn_ref(UID, loop.chat_id, loop.turn_id).get().to_dict()
    assert turn["agent_wrap_up"]["reason"] == "repeat"


def loop_limit(store):
    return probe_loop(store, [], Probes(), request_id="limit").policy.turn_identical_calls


def test_workspace_reads_run_together_and_wait_once_for_the_users_turn(store, fake_vm):
    loop = vm_loop(store, Steps([[("vm_read_file", {"path": "a.txt"}), ("vm_read_file", {"path": "b.txt"}),
                                  ("vm_exec", {"command": "ls"}), ("vm_read_file", {"path": "c.txt"})]]))
    waits = []

    def takeover():
        waits.append(len(waits))
        return None
        yield
    loop._takeover_wait = takeover
    list(loop.run())
    # Three groups, each waiting once: both reads, the command, the last read.
    assert len(waits) == 3 and every_call_answered(loop)
    order = [(call[0], call[2]) for call in fake_vm.calls if call[0] in {"read", "exec"}]
    where = {name: next(n for n, (operation, target) in enumerate(order) if target.endswith(name))
             for name in ("/a.txt", "/b.txt", "ls", "/c.txt")}
    assert max(where["/a.txt"], where["/b.txt"]) < where["ls"] < where["/c.txt"]


def test_the_users_turn_in_the_browser_before_a_group_ends_it(store, fake_vm):
    loop = vm_loop(store, Steps([[("vm_exec", {"command": "ls"}), ("vm_read_file", {"path": "a.txt"}),
                                  ("vm_read_file", {"path": "b.txt"})]]))
    answers = iter([None, "handed_back"])

    def takeover():
        return next(answers)
        yield
    loop._takeover_wait = takeover
    list(loop.run())
    found = tool_results(loop)
    assert found["call_0_0"]["exit_code"] == 0
    assert found["call_0_1"] == found["call_0_2"] == {"error": agent_delegation.CALL_AFTER_TAKEOVER}


def test_calls_group_by_their_tools_never_past_the_limit():
    loop = type("Loop", (), {"registry": ToolRegistry([
        ReadOnlyTool("read", "Read.", ProbeArgs, lambda args, **kw: {}, concurrent=True),
        ReadOnlyTool("write", "Write.", ProbeArgs, lambda args, **kw: {})])})()
    calls = [{"id": f"c{n}", "function": {"name": name, "arguments": "{}"}}
             for n, name in enumerate(["read", "read", "write", "read", "unknown", "read", "read"])]
    groups = agent_delegation.DelegationLoop._call_groups(loop, calls, over_limit={"c6"})
    assert [[call["id"] for _, call in group] for group in groups] == [
        ["c0", "c1"], ["c2"], ["c3"], ["c4"], ["c5"], ["c6"]]


# Tools whose calls change something, wait for the user or build on each other.
ALONE = {"vm_exec", "vm_install_packages", "vm_write_file", "vm_edit_file", "vm_share_file", "vm_render_office",
         "vm_start_process", "vm_process_output", "vm_stop_process", "vm_save_picture", "browser", "ask_user",
         "request_domain", "github_import", "prepare_pull_request", "update_plan", "update_memory",
         "open_workspace", "create_document", "revise_document", "compare_models", "find_pictures", "show_image",
         "prepare_settings_change", "prepare_watch", "start_agent", "send_agent", "wait_agents", "stop_agent",
         "review_agent", "import_gmail_attachment", "prepare_gmail_draft", "prepare_calendar_event"}


def test_only_tools_that_read_run_together(store, fake_vm, tmp_path, monkeypatch):
    import base64
    from app.services import agent_vm_tools
    from app.services.agent_calendar import CalendarTools
    from app.services.agent_files import AgentFiles, FileContext
    from app.services.agent_gmail import GmailTools
    from app.services.agent_memory import MemorySnapshot
    from test_agent_vm import pending
    monkeypatch.setenv("AGENT_GITHUB_TOKEN", "test")
    monkeypatch.setattr(agent_vm_tools, "sees_pictures", lambda model: True)
    monkeypatch.setenv("AGENT_FILES_LOCAL_DIR", str(tmp_path))
    files = AgentFiles(store.db)
    chat_id = store.create_chat(UID, execution_mode="agent")["id"]
    upload = files.upload(UID, chat_id, {"name": "data.csv", "data": base64.b64encode(b"a\n1\n").decode()})
    pending(store, chat_id=chat_id)
    loop = vm_loop(store, Steps(), chat_id=chat_id, file_context=FileContext(files, UID, chat_id, [upload["id"]]))
    loop.memory.snapshot = MemorySnapshot(available=True, enabled=True, auto=True)
    google = type("Loop", (), {"file_context": loop.file_context, "uid": UID})()
    tools = {**loop.registry.tools, **{tool.name: tool for tool in [
        *GmailTools(google, None, None, None).tools(), *CalendarTools(google, None, None, None).tools()]}}
    together = {name for name, tool in tools.items() if tool.concurrent}
    assert together - {"read_source", "search_pictures"} == {
        "read_file", "read_document", "vm_read_file", "vm_view_image", "search_chats", "read_settings",
        "gmail_read", "calendar_read"}
    assert not together & ALONE and {"vm_exec", "browser", "ask_user", "compare_models"} <= set(tools)
