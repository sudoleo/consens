"""Agent VM (AgentPreferences.vm, admin accounts only): the agent's own Linux
VM per chat, created at its first VM call and reused across messages, with
shell commands and files (agent_vm_tools.py) over a small provider interface
(agent_vm.py). These tests never call Sprites: the loop runs against FakeVM,
SpritesBackend against httpx.MockTransport and a fake WebSocket.
"""
import base64
import json

import httpx
import pytest

from app.services import agent_vm, agent_vm_tools, prompt_defaults
from app.services.agent_comparison import AgentPreferences, comparison_selection
from app.services.agent_delegation import DelegationLoop
from app.services.agent_delegation_config import defaults
from app.services.agent_policy import AgentPolicy
from app.services.agent_vm import ExecOutcome, SpritesBackend, VMBackend, VMFileMissing, VMUnavailable
from app.services.agent_vm_tools import (MODEL_STREAM_CHARS, VIEW_CHARS, VM_NO_TIME, VM_UNAVAILABLE, VMTools,
                                         VmExecArgs, model_text, tail)
from app.services.llm.agent_client import AgentCompletion, measured_usage, resolve_agent_model
from app.services.llm.provider_runtime import ProviderCancellation, ProviderCancelled
from test_agent_runs import AUTH, UID, api, pending, store  # noqa: F401  (fixtures)


@pytest.fixture(autouse=True)
def _admin_allowance(monkeypatch):
    """The VM is for admins, whose daily account (5M tokens) holds audit
    mode's search rounds; the suites' 250k (conftest) would not."""
    from app.services import agent_budget_config
    monkeypatch.setitem(agent_budget_config.DEFAULT_TIER_LIMITS, "pro", 5_000_000)


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class FakeVM:
    """The provider's state across messages; ``backend()`` is one message's
    backend. ``commands`` maps a command to ``(chunks, exit_code, seconds)``,
    chunks as ``(stream, bytes)``; ``fail`` names operations that fail."""

    def __init__(self, clock=None):
        self.vms, self.calls, self.commands, self.fail = {}, [], {}, set()
        self.clock = clock or Clock()
        self.backends = 0

    def backend(self):
        self.backends += 1
        return _FakeBackend(self)


class _FakeBackend(VMBackend):
    provider = "fake"

    def __init__(self, vm):
        self.vm = vm

    def _call(self, operation, *args):
        self.vm.calls.append((operation, *args))
        if operation in self.vm.fail:
            raise VMUnavailable(operation)

    def ensure(self, name):
        self._call("ensure", name)
        self.vm.vms.setdefault(name, {"files": {}, "checkpoints": [], "created": len(self.vm.calls)})
        self.vm.vms[name]["policy"] = agent_vm.EGRESS_RULES

    def exec(self, name, command, *, cwd, timeout, on_output, cancellation):
        self._call("exec", name, command, cwd, timeout)
        chunks, exit_code, seconds = self.vm.commands.get(command, ([("stdout", b"ok\n")], 0, .5))
        for stream, chunk in chunks:
            self.vm.clock.now += seconds / max(1, len(chunks))
            on_output(stream, chunk)
        return ExecOutcome(exit_code=exit_code, timed_out=exit_code is None, seconds=seconds)

    def read_file(self, name, path, *, limit):
        self._call("read", name, path)
        files = self.vm.vms[name]["files"]
        if path not in files:
            raise VMFileMissing(path)
        return files[path][:limit], len(files[path]) <= limit

    def write_file(self, name, path, data):
        self._call("write", name, path)
        self.vm.vms[name]["files"][path] = data
        return len(data)

    def checkpoint(self, name, comment):
        self._call("checkpoint", name, comment)
        checkpoints = self.vm.vms[name]["checkpoints"]
        checkpoints.append(comment)
        return f"v{len(checkpoints)}"

    def restore(self, name, checkpoint):
        self._call("restore", name, checkpoint)

    def delete(self, name):
        self._call("delete", name)
        self.vm.vms.pop(name, None)

    def close(self):
        self.vm.calls.append(("close",))


class Agent:
    """A scripted agent: step N makes the tool calls ``steps[N]`` (name,
    arguments), the step after the last one answers ANSWER."""

    def __init__(self, steps=()):
        self.steps = list(steps)
        self.offered, self.systems = [], []

    def factory(self):
        script = self

        class Completion(AgentCompletion):
            def stream(self, *, model, messages, **kwargs):
                self.usage = measured_usage({"prompt_tokens": 50, "completion_tokens": 20, "cost": .0001}, model)
                index = int(self.step_id.split(":")[1])
                script.offered.append([tool["function"]["name"] for tool in kwargs.get("tools") or []
                                       if tool.get("type") == "function"])
                script.systems.append(messages[0]["content"])
                if index < len(script.steps):
                    self.tool_calls = [{"id": f"call_{index}_{n}", "type": "function",
                                        "function": {"name": name, "arguments": json.dumps(arguments)}}
                                       for n, (name, arguments) in enumerate(script.steps[index])]
                    self.finish_reason = "tool_calls"
                    return
                self.text, self.finish_reason = ANSWER, "stop"
                yield {"type": "delta", "text": self.text}
        return Completion()


ANSWER = "The script printed 42: the mean of the column is 42."


def vm_loop(store, script, *, chat_id=None, request_id="one", vm="on", audit="on", file_context=None,
            google_data=False):
    chat, turn = pending(store, chat_id=chat_id, request_id=request_id)
    config = {**defaults(), "enabled": False, "max_searches": 0}
    return DelegationLoop(store=store, uid=UID, chat_id=chat, turn_id=turn["id"],
        model=resolve_agent_model("claude-haiku-4-5"),
        messages=[{"role": "system", "content": "Answer."}, {"role": "user", "content": "Analyse my data."}],
        api_key="test", cancellation=ProviderCancellation(), policy=AgentPolicy.for_chat(config),
        delegation_config=config, completion_factory=script.factory,
        comparison_models=comparison_selection({"anthropic": "claude-haiku-4-5", "openai": "gpt-5.4-mini"}),
        agent_preferences=AgentPreferences(audit=audit, judges="off", vm=vm), file_context=file_context,
        google_data=google_data)


@pytest.fixture
def fake_vm(monkeypatch):
    vm = FakeVM()
    monkeypatch.setattr(agent_vm, "backend", vm.backend)
    return vm


def tool_events(events, name=None):
    return [e for e in events if e.get("type") == "activity" and e.get("kind") == "tool"
            and (name is None or e.get("name") == name)]


def results(loop):
    return [json.loads(m["content"]) for m in loop.messages if m.get("role") == "tool"]


# --- The turn -------------------------------------------------------------------

def test_the_agent_runs_commands_in_its_vm_live_and_the_turn_keeps_the_summary(store, fake_vm):
    fake_vm.commands["python3 stats.py"] = ([("stdout", b"reading\n"), ("stderr", b"warning: old numpy\n"),
                                            ("stdout", b"mean 42\n")], 0, 3.0)
    script = Agent([[("vm_write_file", {"path": "stats.py", "content": "print(42)"})],
                    [("vm_exec", {"command": "python3 stats.py", "timeout_seconds": 120})],
                    [("vm_read_file", {"path": "~/stats.py"})]])
    loop = vm_loop(store, script)
    loop.vm_tools.session.clock = fake_vm.clock
    events = list(loop.run())
    turn = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert turn["status"] == "completed" and turn["consensus"] == ANSWER
    # The agent is told about its VM and offered its three tools.
    assert prompt_defaults.AGENT_VM_PROMPT in script.systems[0]
    assert {"vm_exec", "vm_read_file", "vm_write_file"} <= set(script.offered[0])
    name = agent_vm.vm_name(UID, loop.chat_id)
    # The chat names its VM before the provider creates it; the VM gets the egress rules.
    chat = store._chat_ref(UID, loop.chat_id).get().to_dict()
    assert chat["agent_vm"]["name"] == name and chat["agent_vm"]["provider"] == "fake"
    assert fake_vm.vms[name]["policy"] == [{"include": "defaults"}]
    # One checkpoint for the message, before its first call ran.
    operations = [call[0] for call in fake_vm.calls]
    assert operations[:3] == ["ensure", "checkpoint", "write"] and operations.count("checkpoint") == 1
    assert fake_vm.calls[1][2] == f"consens.io message {loop.turn_id}"
    # The command ran under its limit in the home folder; no environment from the backend.
    assert ("exec", name, "python3 stats.py", "/home/sprite", 120) in fake_vm.calls
    # What the model read: each stream, exit code and duration.
    write, run, read = results(loop)
    assert write == {"path": "/home/sprite/stats.py", "bytes": 9}
    assert run["exit_code"] == 0 and run["duration_ms"] == 3000 and run["timed_out"] is False
    assert run["stdout"] == "reading\nmean 42\n" and run["stderr"] == "warning: old numpy\n"
    assert read["content"] == "print(42)\n" and read["total_lines"] == 1 and "more" not in read
    # The activity: what ran, its output while it ran, then how it ended.
    exec_events = tool_events(events, "vm_exec")
    assert exec_events[0]["status"] == "running" and exec_events[0]["command"] == "python3 stats.py"
    live = [e for e in exec_events if e["status"] == "running" and "output" in e]
    assert live and live[0]["output"].startswith("reading\n")
    saved = next(e for e in turn["agent_activity"] if e.get("name") == "vm_exec")
    assert saved["status"] == "succeeded" and saved["exit_code"] == 0 and saved["duration_ms"] == 3000
    assert saved["output"] == "reading\nwarning: old numpy\nmean 42\n" and saved["output_truncated"] is False
    assert saved["command"] == "python3 stats.py" and saved["cwd"] == "/home/sprite"
    paths = {e["name"]: e["path"] for e in turn["agent_activity"] if e.get("name") in {"vm_read_file", "vm_write_file"}}
    assert paths == {"vm_write_file": "/home/sprite/stats.py", "vm_read_file": "/home/sprite/stats.py"}
    # The message's summary: its checkpoint and the commands' run time.
    assert turn["agent_vm"] == {"provider": "fake", "checkpoint": "v1", "calls": 3, "commands": 1, "seconds": 3.0}
    # Command output is outside content: memory is locked from then on.
    assert loop.memory_locked is True
    assert fake_vm.calls[-1] == ("close",)


def test_the_work_log_holds_every_vm_call_as_data_for_the_reviewers(store, fake_vm):
    script = Agent([[("vm_exec", {"command": "ls"})]])
    loop = vm_loop(store, script)
    list(loop.run())
    entries = [entry for entry, _ in loop.work_log.entries_after(0)]
    tool = next(entry for entry in entries if entry["kind"] == "tool" and entry["name"] == "vm_exec")
    content = json.loads(loop.work_log.entries_after(tool["seq"] - 1)[0][1])
    assert tool["data"] == "vm" and content["exit_code"] == 0 and content["stdout"] == "ok\n"
    step = next(entry for entry, text in loop.work_log.entries_after(0) if entry["kind"] == "step")
    assert step["actor"] == "agent"
    end = json.loads([text for entry, text in loop.work_log.entries_after(0) if entry["kind"] == "end"][0])
    assert end["vm"]["commands"] == 1


def test_the_vm_is_created_once_and_each_message_takes_its_own_checkpoint(store, fake_vm):
    first = vm_loop(store, Agent([[("vm_write_file", {"path": "notes.txt", "content": "a"})]]))
    list(first.run())
    second = vm_loop(store, Agent([[("vm_read_file", {"path": "notes.txt"})]]), chat_id=first.chat_id,
                     request_id="two")
    list(second.run())
    name = agent_vm.vm_name(UID, first.chat_id)
    assert list(fake_vm.vms) == [name]
    assert fake_vm.vms[name]["checkpoints"] == [f"consens.io message {first.turn_id}",
                                                f"consens.io message {second.turn_id}"]
    # The second message reads what the first one wrote.
    assert results(second)[0]["content"] == "a\n"
    assert store.get_turn(UID, first.chat_id, first.turn_id)["agent_vm"]["checkpoint"] == "v1"
    assert store.get_turn(UID, first.chat_id, second.turn_id)["agent_vm"]["checkpoint"] == "v2"
    # Another chat has a VM of its own.
    assert agent_vm.vm_name(UID, "other") != name and agent_vm.vm_name("other-user", first.chat_id) != name


def test_a_message_without_vm_calls_never_wakes_the_vm(store, fake_vm):
    loop = vm_loop(store, Agent())
    list(loop.run())
    assert fake_vm.calls == [] and fake_vm.backends == 0
    assert "agent_vm" not in store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert "agent_vm" not in store._chat_ref(UID, loop.chat_id).get().to_dict()


def test_the_messages_attachments_are_in_the_input_folder_at_first_use(store, fake_vm, tmp_path, monkeypatch):
    from app.services.agent_files import AgentFiles, FileContext
    monkeypatch.setenv("AGENT_FILES_LOCAL_DIR", str(tmp_path))
    files = AgentFiles(store.db)
    chat_id = store.create_chat(UID, execution_mode="agent")["id"]
    uploaded = [files.upload(UID, chat_id, {"name": name, "data": base64.b64encode(b"a,b\n1,2\n").decode()})
                for name in ("data.csv", "data.csv")]
    context = FileContext(files, UID, chat_id, [item["id"] for item in uploaded])
    script = Agent([[("vm_exec", {"command": "ls input"})], [("vm_exec", {"command": "wc -l input/data.csv"})]])
    loop = vm_loop(store, script, chat_id=chat_id, file_context=context)
    list(loop.run())
    name = agent_vm.vm_name(UID, chat_id)
    assert fake_vm.vms[name]["files"] == {"/home/sprite/input/data.csv": b"a,b\n1,2\n",
                                          "/home/sprite/input/data (2).csv": b"a,b\n1,2\n"}
    first, second = results(loop)
    assert first["inputs"] == ["/home/sprite/input/data.csv", "/home/sprite/input/data (2).csv"]
    assert first["input_dir"] == "/home/sprite/input" and "inputs" not in second


def test_an_unreachable_vm_costs_its_tools_never_the_answer(store, fake_vm):
    fake_vm.fail.add("ensure")
    script = Agent([[("vm_exec", {"command": "ls"})], [("vm_exec", {"command": "pwd"})]])
    loop = vm_loop(store, script)
    events = list(loop.run())
    turn = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert turn["status"] == "completed" and turn["consensus"] == ANSWER
    # One short message for the agent; the second call never reaches the provider.
    assert results(loop) == [{"error": VM_UNAVAILABLE}, {"error": VM_UNAVAILABLE}]
    assert [call[0] for call in fake_vm.calls].count("ensure") == 1
    # The user sees a calm state, not the provider's error.
    ended = [e for e in tool_events(events, "vm_exec") if e["status"] != "running"]
    assert {e["outcome"] for e in ended} == {"unavailable"} and all("text" not in e for e in ended)
    assert turn["agent_vm"]["unavailable"] is True and turn["agent_vm"]["commands"] == 0


def test_a_vm_failing_mid_command_is_off_for_the_rest_of_the_message(store, fake_vm):
    script = Agent([[("vm_exec", {"command": "ls"})], [("vm_exec", {"command": "make"})],
                    [("vm_exec", {"command": "ls"})]])
    loop = vm_loop(store, script)
    original = _FakeBackend.exec

    def flaky(self, name, command, **kwargs):
        if command == "make":
            self.vm.calls.append(("exec", name, command))
            raise VMUnavailable("connection lost")
        return original(self, name, command, **kwargs)
    _FakeBackend.exec = flaky
    try:
        list(loop.run())
    finally:
        _FakeBackend.exec = original
    assert [r.get("error") for r in results(loop)] == [None, VM_UNAVAILABLE, VM_UNAVAILABLE]
    assert [call[2] for call in fake_vm.calls if call[0] == "exec"] == ["ls", "make"]


@pytest.mark.parametrize("operation", ["ensure", "exec"])
def test_an_unexpected_vm_failure_also_costs_only_the_tools(store, fake_vm, monkeypatch, operation):
    """A broken install (live 2026-10-25: websockets missing in the server's
    Python) or a bug is no provider refusal, yet it must not fail the answer."""
    reported = []
    monkeypatch.setattr(agent_vm_tools, "report_server_exception",
                        lambda exc, **kwargs: reported.append((type(exc).__name__, kwargs["where"])))

    def broken(self, *args, **kwargs):
        raise ModuleNotFoundError("No module named 'websockets'")
    monkeypatch.setattr(_FakeBackend, operation, broken)
    loop = vm_loop(store, Agent([[("vm_exec", {"command": "ls"})], [("vm_exec", {"command": "pwd"})]]))
    list(loop.run())
    turn = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert turn["status"] == "completed" and turn["consensus"] == ANSWER
    assert results(loop) == [{"error": VM_UNAVAILABLE}, {"error": VM_UNAVAILABLE}]
    assert reported == [("ModuleNotFoundError", f"agent_vm.{'start' if operation == 'ensure' else 'exec'}")]
    assert turn["agent_vm"]["unavailable"] is True


def test_no_vm_without_the_setting_or_in_chats_with_google_data(store, fake_vm):
    for request_id, kwargs in (("off", {"vm": "off"}), ("google", {"google_data": True})):
        script = Agent()
        loop = vm_loop(store, script, request_id=request_id, **kwargs)
        assert loop.vm_tools is None
        list(loop.run())
        assert not {"vm_exec", "vm_read_file", "vm_write_file"} & set(script.offered[0])
        assert prompt_defaults.AGENT_VM_PROMPT not in script.systems[0]


def test_the_vm_also_works_with_comparison_tools(store, fake_vm):
    script = Agent([[("vm_exec", {"command": "ls"})]])
    loop = vm_loop(store, script, audit="off")
    list(loop.run())
    assert {"compare_models", "vm_exec"} <= set(script.offered[0])
    assert results(loop)[0]["stdout"] == "ok\n"
    assert store.get_turn(UID, loop.chat_id, loop.turn_id)["status"] == "completed"


def test_the_same_command_may_run_again(store, fake_vm):
    """The identical-call guard stops a loop without progress; a VM command's
    result depends on the VM's state (tests again after an edit)."""
    script = Agent([[("vm_exec", {"command": "pytest -q"})]] * 4)
    loop = vm_loop(store, script)
    list(loop.run())
    assert [r.get("exit_code") for r in results(loop)] == [0, 0, 0, 0]


# --- Limits and output ------------------------------------------------------------

class TimeLoop:
    """What VMTools needs of a loop, with a settable time before the answer."""

    def __init__(self, left):
        self.left, self.uid, self.chat_id, self.turn_id = left, UID, "c" * 32, "t" * 32
        self.file_context = None

    def answer_time_left(self):
        return self.left


def test_a_command_never_runs_past_its_cap_or_the_time_the_answer_needs():
    tools = VMTools(TimeLoop(None))
    assert tools._timeout(300) == 300 and tools._timeout(20) == 20
    tools.loop.left = 100.7
    assert tools._timeout(300) == 100
    tools.loop.left = agent_vm_tools.MIN_COMMAND_SECONDS - 1
    with pytest.raises(ValueError, match=VM_NO_TIME):
        tools._timeout(30)
    with pytest.raises(ValueError):
        VmExecArgs(command="ls", timeout_seconds=agent_vm_tools.EXEC_TIMEOUT_MAX + 1)


def test_long_output_keeps_its_end_and_says_what_was_cut():
    raw = ("x" * 30_000 + "\nthe end\n").encode()
    text = model_text(raw, len(raw) + 5_000, "stdout")
    assert text.endswith("the end\n") and len(text) < MODEL_STREAM_CHARS + 100
    omitted = int(text.split("earlier bytes")[0].split("[… ")[1].replace(",", ""))
    assert omitted == len(raw) + 5_000 - (MODEL_STREAM_CHARS)
    assert model_text(b"short\n", 6, "stderr") == "short\n"
    # Progress bars and colors: only the line's last state, no escape codes.
    raw = b"\x1b[32m10%\r50%\r100%\x1b[0m\ndone\r\n"
    shown, cut = tail(raw, len(raw), VIEW_CHARS)
    assert shown == "100%\ndone\n" and cut == 0


def test_a_timed_out_command_says_so(store, fake_vm):
    fake_vm.commands["sleep 999"] = ([("stdout", b"started\n")], None, 61.0)
    loop = vm_loop(store, Agent([[("vm_exec", {"command": "sleep 999"})]]))
    list(loop.run())
    [result] = results(loop)
    assert result["timed_out"] is True and result["exit_code"] is None and "time limit of 60 seconds" in result["note"]
    # The activity's event, as its updates add up (saved like the browser merges them).
    saved = next(e for e in store.get_turn(UID, loop.chat_id, loop.turn_id)["agent_activity"]
                 if e.get("name") == "vm_exec")
    assert saved["status"] == "succeeded" and saved["timed_out"] is True and saved["output"] == "started\n"


def test_reading_a_missing_or_long_file(store, fake_vm):
    lines = "".join(f"line {n}\n" for n in range(1, 1001)).encode()
    script = Agent([[("vm_read_file", {"path": "/nope"})], [("vm_read_file", {"path": "big.txt", "offset": 3,
                                                                                "limit": 2})]])
    loop = vm_loop(store, script)
    loop.vm_tools.session.ready(ProviderCancellation())
    fake_vm.vms[agent_vm.vm_name(UID, loop.chat_id)]["files"]["/home/sprite/big.txt"] = lines
    list(loop.run())
    missing, page = results(loop)
    assert missing == {"error": "No file at /nope."}
    assert page["content"] == "line 3\nline 4\n" and page["first_line"] == 3 and page["last_line"] == 4
    assert page["total_lines"] == 1000 and page["more"] == "More lines follow: read on with offset=5."


def test_an_edit_replaces_exact_text_and_shows_the_changed_lines(store, fake_vm):
    """vm_edit_file (2026-10-26), like Claude Code's Edit: the agent changes a
    file without writing it whole again, and sees the changed lines."""
    source = "".join(f"line {n}\n" for n in range(1, 11)).replace("line 5\n", "total = a - b\n")
    script = Agent([[("vm_edit_file", {"path": "calc.py", "old_string": "total = a - b",
                                       "new_string": "total = a + b\nprint(total)"})]])
    loop = vm_loop(store, script)
    loop.vm_tools.session.ready(ProviderCancellation())
    files = fake_vm.vms[agent_vm.vm_name(UID, loop.chat_id)]["files"]
    files["/home/sprite/calc.py"] = source.encode()
    events = list(loop.run())
    assert "vm_edit_file" in script.offered[0]
    assert "vm_edit_file changes part of a file" in prompt_defaults.AGENT_VM_PROMPT
    assert files["/home/sprite/calc.py"].decode() == source.replace("total = a - b\n", "total = a + b\nprint(total)\n")
    [result] = results(loop)
    assert result["path"] == "/home/sprite/calc.py" and result["replacements"] == 1
    assert result["first_line"] == 2 and result["last_line"] == 9
    assert result["snippet"].splitlines() == ["     2\tline 2", "     3\tline 3", "     4\tline 4",
                                              "     5\ttotal = a + b", "     6\tprint(total)", "     7\tline 6",
                                              "     8\tline 7", "     9\tline 8"]
    # The activity names the file; the lines it shows again are file content: memory locks.
    edit = next(e for e in tool_events(events, "vm_edit_file") if e["status"] == "succeeded")
    assert edit["path"] == "/home/sprite/calc.py" and loop.memory_locked is True
    entry = next(e for e, _ in loop.work_log.entries_after(0) if e["kind"] == "tool" and e["name"] == "vm_edit_file")
    assert entry["data"] == "vm"


def test_an_edit_must_find_its_text_exactly_once_or_replace_all(store, fake_vm):
    loop = vm_loop(store, Agent())
    tools, cancellation = loop.vm_tools, ProviderCancellation()

    def edit(**kwargs):
        args = agent_vm_tools.VmEditFileArgs(path=kwargs.pop("path", "a.txt"), **kwargs)
        try:
            return tools.edit(args, cancellation=cancellation)
        except ValueError as exc:
            return {"error": str(exc)}
    # The same text on both sides changes nothing and never wakes the VM.
    assert "nothing to change" in edit(old_string="x", new_string="x")["error"] and fake_vm.calls == []
    tools.session.ready(cancellation)
    files = fake_vm.vms[agent_vm.vm_name(UID, loop.chat_id)]["files"]
    assert edit(path="none.txt", old_string="a", new_string="b")["error"] == (
        "No file at /home/sprite/none.txt. Create it with vm_write_file.")
    # Windows line endings and bytes that are no UTF-8 stay exactly as they were.
    files["/home/sprite/a.txt"] = b"x = 1\r\ny = 1\r\n\xff\xfe raw\r\n"
    assert "was not found" in edit(old_string="x = 2", new_string="x = 3")["error"]
    assert "occurs 2 times" in edit(old_string="= 1", new_string="= 2")["error"]
    assert files["/home/sprite/a.txt"] == b"x = 1\r\ny = 1\r\n\xff\xfe raw\r\n"
    done = edit(old_string="= 1", new_string="= 2", replace_all=True)
    assert done["replacements"] == 2 and files["/home/sprite/a.txt"] == b"x = 2\r\ny = 2\r\n\xff\xfe raw\r\n"
    files["/home/sprite/b.bin"] = b"\x00\x01binary"
    assert "binary file" in edit(path="b.bin", old_string="binary", new_string="text")["error"]
    with pytest.raises(ValueError):
        agent_vm_tools.VmEditFileArgs(path="a.txt", old_string="", new_string="b")


def test_a_line_longer_than_a_page_is_read_cut_and_reading_goes_on(store, fake_vm):
    """One line over READ_CHARS (minified JSON) used to come back empty with
    "read on with offset=<the same offset>": the agent read it again and again."""
    long_line = "x" * (agent_vm_tools.READ_CHARS + 500)
    script = Agent([[("vm_read_file", {"path": "data.json"})],
                    [("vm_read_file", {"path": "data.json", "offset": 2})]])
    loop = vm_loop(store, script)
    loop.vm_tools.session.ready(ProviderCancellation())
    fake_vm.vms[agent_vm.vm_name(UID, loop.chat_id)]["files"]["/home/sprite/data.json"] = (
        f"short\n{long_line}\nend\n".encode())
    list(loop.run())
    first, cut = results(loop)
    assert first["content"] == "short\n" and first["more"] == "More lines follow: read on with offset=2."
    assert cut["first_line"] == 2 and cut["last_line"] == 2
    assert cut["content"] == long_line[:agent_vm_tools.READ_CHARS] + "\n"
    assert "longer than" in cut["note"] and "vm_exec" in cut["note"]
    assert cut["more"] == "More lines follow: read on with offset=3."


def test_a_shared_file_reaches_the_user_under_the_answer_never_as_a_link(store, fake_vm, tmp_path, monkeypatch):
    """vm_share_file (2026-10-26): the file goes into the chat's private store
    as the turn's ``vm_file``; a picture only by its bytes, never by its name."""
    from app.services.agent_files import AgentFiles, FileContext
    monkeypatch.setenv("AGENT_FILES_LOCAL_DIR", str(tmp_path))
    files = AgentFiles(store.db)
    chat_id = store.create_chat(UID, execution_mode="agent")["id"]
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40
    script = Agent([[("vm_share_file", {"path": "/tmp/chart.png"}),
                     ("vm_share_file", {"path": "notes.txt", "name": "Results.txt"})],
                    [("vm_share_file", {"path": "/tmp/chart.png"}), ("vm_share_file", {"path": "/tmp/fake.png"}),
                     ("vm_share_file", {"path": "big.bin"}), ("vm_share_file", {"path": "/nope"})]])
    loop = vm_loop(store, script, chat_id=chat_id, file_context=FileContext(files, UID, chat_id, []))
    loop.vm_tools.session.ready(ProviderCancellation())
    fake_vm.vms[agent_vm.vm_name(UID, chat_id)]["files"].update({
        "/tmp/chart.png": png, "/home/sprite/notes.txt": b"mean 42\n", "/tmp/fake.png": b"<svg onload=alert(1)>",
        "/home/sprite/big.bin": b"x" * (agent_vm_tools.SHARE_BYTES + 1)})
    events = list(loop.run())
    chart, notes, again, fake, big, missing = results(loop)
    assert "vm_share_file" in script.offered[0]
    assert chart["shown_as"] == "picture" and chart["file"]["mime"] == "image/png" and chart["file"]["name"] == "chart.png"
    assert notes["shown_as"] == "download" and notes["file"]["name"] == "Results.txt"
    assert notes["file"]["mime"] == "text/plain" and "Do not embed it as an image" in notes["note"]
    # The same file again is the same download.
    assert again["file"] == chart["file"]
    # A name never makes a file a picture.
    assert fake["shown_as"] == "download" and fake["file"]["mime"] == "application/octet-stream"
    assert big == {"error": "/home/sprite/big.bin is larger than 5 MB. Share a smaller file (compress, split or "
                            "shrink it)."}
    assert missing == {"error": "No file at /nope."}
    saved = {file["name"]: file for file in files.list(UID, chat_id)}
    assert set(saved) == {"chart.png", "Results.txt", "fake.png"}
    assert {(file["kind"], file["turn_id"]) for file in saved.values()} == {("vm_file", loop.turn_id)}
    assert saved["chart.png"]["origin"] == {"source": "vm", "path": "/tmp/chart.png"}
    assert files.download(UID, chat_id, chart["file"]["id"])[1] == png
    # The browser hears of each new file once (agent-workspace.js refreshes).
    shared = [file["name"] for event in events if event.get("type") == "resources" for file in event["files"]]
    assert shared == ["chart.png", "Results.txt", "fake.png"]
    assert [event["path"] for event in tool_events(events, "vm_share_file") if event["status"] == "succeeded"] == [
        "/tmp/chart.png", "/home/sprite/notes.txt", "/tmp/chart.png", "/tmp/fake.png"]


# --- Admins only ------------------------------------------------------------------

@pytest.mark.parametrize("admin", [True, False])
def test_only_an_admins_message_gets_the_vm(api, monkeypatch, admin):
    from app.api.routers import agent
    client, store, calls = api
    monkeypatch.setattr(agent, "is_user_admin", lambda uid: admin)
    chat_id = store.create_chat(UID, execution_mode="agent")["id"]
    payload = {"chat_id": chat_id, "question": "Hi", "client_request_id": "r1", "bookmark_id": "bm1",
               "agent_preferences": {"vm": "on"}}
    assert client.post("/agent", json=payload, headers=AUTH).status_code == 200
    turn = next(t for t in store.list_turns(UID, chat_id)["turns"] if t["question"] == "Hi")
    settings = store.get_turn(UID, chat_id, turn["id"])["agent_settings"]
    assert settings["agent_preferences"]["vm"] == ("on" if admin else "off")
    names = {tool["function"]["name"] for tool in calls[0].get("tools") or [] if tool.get("type") == "function"}
    assert ("vm_exec" in names) is admin
    assert (prompt_defaults.AGENT_VM_PROMPT in calls[0]["messages"][0]["content"]) is admin
    # The same request again is the same message, with the same effective settings.
    assert client.post("/agent", json=payload, headers=AUTH).status_code == 200


def test_an_admin_with_everything_on_gets_every_tool(store, fake_vm, tmp_path, monkeypatch):
    # VM with GitHub and pictures, a file in the chat, Memory and workers at
    # once: a bound of 20 tools failed every message of such a chat
    # ("Invalid tool registry", 422).
    from app.services.agent_files import AgentFiles, FileContext
    from app.services.agent_memory import MemorySnapshot
    monkeypatch.setenv("AGENT_GITHUB_TOKEN", "test")
    monkeypatch.setattr(agent_vm_tools, "sees_pictures", lambda model: True)
    monkeypatch.setenv("AGENT_FILES_LOCAL_DIR", str(tmp_path))
    files = AgentFiles(store.db)
    chat_id = store.create_chat(UID, execution_mode="agent")["id"]
    upload = files.upload(UID, chat_id, {"name": "data.csv", "data": base64.b64encode(b"a\n1\n").decode()})
    chat, turn = pending(store, chat_id=chat_id)
    config = {**defaults(), "enabled": True, "max_searches": 0}
    loop = DelegationLoop(store=store, uid=UID, chat_id=chat, turn_id=turn["id"],
        model=resolve_agent_model("claude-haiku-4-5"),
        messages=[{"role": "system", "content": "Answer."}, {"role": "user", "content": "Analyse my data."}],
        api_key="test", cancellation=ProviderCancellation(), policy=AgentPolicy.for_chat(config),
        delegation_config=config, completion_factory=Agent().factory,
        comparison_models=comparison_selection({"anthropic": "claude-haiku-4-5", "openai": "gpt-5.4-mini"}),
        agent_preferences=AgentPreferences(audit="off", judges="off", vm="on"),
        file_context=FileContext(files, UID, chat_id, [upload["id"]]),
        memory=MemorySnapshot(available=True, enabled=True, auto=True))
    assert {"start_agent", "compare_models", "read_file", "update_memory", "vm_exec", "vm_view_image",
            "github_import", "update_plan"} <= set(loop.registry.tools)


# --- Deletion -----------------------------------------------------------------------

def test_deleting_the_chat_deletes_its_vm(store, fake_vm):
    loop = vm_loop(store, Agent([[("vm_exec", {"command": "ls"})]]))
    list(loop.run())
    name = agent_vm.vm_name(UID, loop.chat_id)
    store._purge_chat(UID, loop.chat_id)
    assert name not in fake_vm.vms and ("delete", name) in fake_vm.calls
    assert not store._chat_ref(UID, loop.chat_id).get().exists


def test_a_failed_vm_deletion_keeps_the_chats_deletion_job_retrying(store, fake_vm):
    loop = vm_loop(store, Agent([[("vm_exec", {"command": "ls"})]]))
    list(loop.run())
    fake_vm.fail.add("delete")
    with pytest.raises(VMUnavailable):
        store._purge_chat(UID, loop.chat_id)
    # Nothing of the chat is gone yet: the job retries all of it.
    assert store._chat_ref(UID, loop.chat_id).get().exists


def test_a_chat_without_a_vm_is_deleted_without_asking_the_provider(store, monkeypatch):
    def unexpected():
        raise AssertionError("no provider call expected")
    monkeypatch.setattr(agent_vm, "backend", unexpected)
    chat_id, _ = pending(store)
    store._purge_chat(UID, chat_id)
    assert not store._chat_ref(UID, chat_id).get().exists


def test_a_chat_deleted_while_its_vm_was_created_deletes_the_vm(store, fake_vm):
    loop = vm_loop(store, Agent())
    original = _FakeBackend.ensure

    def deleted_meanwhile(self, name):
        original(self, name)
        store._chat_ref(UID, loop.chat_id).update({"status": "deleting"})
    _FakeBackend.ensure = deleted_meanwhile
    try:
        with pytest.raises(ValueError, match="not available"):
            loop.vm_tools.session.ready(ProviderCancellation())
    finally:
        _FakeBackend.ensure = original
    assert fake_vm.vms == {} and ("delete", agent_vm.vm_name(UID, loop.chat_id)) in fake_vm.calls


# --- SpritesBackend (no network) -----------------------------------------------------

def sprites(handler, **kwargs):
    return SpritesBackend("secret-token", transport=httpx.MockTransport(handler), **kwargs)


def test_sprites_creates_a_missing_vm_and_applies_the_egress_rules():
    seen = []

    def handler(request):
        seen.append((request.method, request.url.path, request.content.decode() or None))
        assert request.headers["Authorization"] == "Bearer secret-token"
        if request.method == "GET":
            return httpx.Response(404)
        # Live 2026-10-25: the policy answers 204 without a body; any 2xx is success.
        return httpx.Response(201, json={}) if request.url.path == "/v1/sprites" else httpx.Response(204)
    sprites(handler).ensure("consens-abc")
    assert seen == [("GET", "/v1/sprites/consens-abc", None),
                    ("POST", "/v1/sprites", json.dumps({"name": "consens-abc"}, separators=(",", ":"))),
                    ("POST", "/v1/sprites/consens-abc/policy/network",
                     json.dumps({"rules": [{"include": "defaults"}]}, separators=(",", ":")))]


def test_sprites_failures_are_one_kind_of_error():
    with pytest.raises(VMUnavailable):
        sprites(lambda request: httpx.Response(500)).ensure("consens-abc")

    def offline(request):
        raise httpx.ConnectError("down")
    with pytest.raises(VMUnavailable):
        sprites(offline).write_file("consens-abc", "/home/sprite/a", b"x")
    sprites(lambda request: httpx.Response(404)).delete("consens-abc")  # Already gone.


def test_sprites_checkpoint_waits_for_completion_and_finds_its_id_by_comment():
    def handler(request):
        if request.method == "POST":
            assert json.loads(request.content) == {"comment": "consens.io message t1"}
            lines = [{"type": "info", "data": "Creating checkpoint...", "time": "t"},
                     {"type": "complete", "data": "Checkpoint v8 created", "time": "t"}]
            return httpx.Response(200, content="\n".join(json.dumps(line) for line in lines).encode())
        return httpx.Response(200, json=[{"id": "v7", "comment": "other", "create_time": "2026-10-25T10:00:00Z"},
                                         {"id": "v8", "comment": "consens.io message t1",
                                          "create_time": "2026-10-25T11:00:00Z"}])
    assert sprites(handler).checkpoint("consens-abc", "consens.io message t1") == "v8"

    def failing(request):
        return httpx.Response(200, content=json.dumps({"type": "error", "error": "disk full", "time": "t"}).encode())
    with pytest.raises(VMUnavailable):
        sprites(failing).checkpoint("consens-abc", "c")


def test_sprites_files_read_up_to_their_limit_and_write_with_folders():
    def handler(request):
        if request.url.path.endswith("/fs/read"):
            if request.url.params["path"] == "/missing":
                return httpx.Response(404)
            assert request.url.params["workingDir"] == "/home/sprite"
            return httpx.Response(200, content=b"0123456789")
        assert request.url.params["mkdir"] == "true" and request.content == b"data"
        return httpx.Response(200, json={"path": "/home/sprite/a", "size": 4, "mode": "0644"})
    backend = sprites(handler)
    assert backend.read_file("vm", "/home/sprite/a", limit=100) == (b"0123456789", True)
    assert backend.read_file("vm", "/home/sprite/a", limit=4) == (b"0123", False)
    with pytest.raises(VMFileMissing):
        backend.read_file("vm", "/missing", limit=10)
    assert backend.write_file("vm", "/home/sprite/a", b"data") == 4


class FakeSocket:
    """The exec WebSocket: ``messages`` in order, then a closed connection."""

    def __init__(self, messages):
        self.messages, self.closed = list(messages), False

    def recv(self, timeout=None):
        from websockets.exceptions import ConnectionClosedOK
        if self.closed or not self.messages:
            raise ConnectionClosedOK(None, None)
        message = self.messages.pop(0)
        if isinstance(message, BaseException):
            raise message
        return message

    def close(self):
        self.closed = True


def test_sprites_exec_streams_the_frames_and_never_sends_the_token_to_the_vm():
    opened, output = [], []
    socket = FakeSocket([json.dumps({"type": "session_info", "session_id": "17"}), b"\x01hello ", b"\x02careful\n",
                         b"\x01world\n", b"\x03\x02"])
    backend = sprites(lambda request: httpx.Response(200),
                      connect=lambda url, token: opened.append((url, token)) or socket)
    outcome = backend.exec("consens-abc", "make && echo 'done'", cwd="/home/sprite/app", timeout=60,
                           on_output=lambda stream, chunk: output.append((stream, chunk)),
                           cancellation=ProviderCancellation())
    assert outcome.exit_code == 2 and outcome.timed_out is False and socket.closed
    assert output == [("stdout", b"hello "), ("stderr", b"careful\n"), ("stdout", b"world\n")]
    [(url, token)] = opened
    query = httpx.URL(url).params
    assert url.startswith("wss://api.sprites.dev/v1/sprites/consens-abc/exec?")
    # Under the VM-side limit, with the login environment loaded silently (the
    # Sprites .bashrc warned about bind in every command, live 2026-10-25);
    # no environment from the backend, the token only in the header.
    assert query.get_list("cmd") == ["timeout", "--kill-after=5", "60", "bash", "-c", agent_vm.SHELL_PRELUDE,
                                     "bash", "make && echo 'done'"]
    assert query["dir"] == "/home/sprite/app" and query["stdin"] == "false" and "env" not in query
    assert token == "secret-token" and "secret-token" not in url


def test_sprites_exec_reports_a_timeout_and_a_lost_connection():
    clock = Clock()

    class Slow(FakeSocket):
        def recv(self, timeout=None):
            clock.now += 61
            return super().recv(timeout)
    backend = sprites(lambda request: httpx.Response(200), connect=lambda url, token: Slow([b"\x03\x7c"]),
                      clock=clock)
    outcome = backend.exec("vm", "sleep 99", cwd="/home/sprite", timeout=60, on_output=lambda *a: None,
                           cancellation=ProviderCancellation())
    assert outcome.timed_out is True and outcome.exit_code == 124
    lost = sprites(lambda request: httpx.Response(200), connect=lambda url, token: FakeSocket([b"\x01half"]))
    with pytest.raises(VMUnavailable):
        lost.exec("vm", "ls", cwd="/home/sprite", timeout=60, on_output=lambda *a: None,
                  cancellation=ProviderCancellation())


def test_sprites_exec_on_stop_ends_the_command_in_the_vm():
    killed = []
    cancellation = ProviderCancellation()

    class Stopped(FakeSocket):
        def recv(self, timeout=None):
            if not self.messages:
                cancellation.cancel()
            return super().recv(timeout)

    def handler(request):
        killed.append(request.url.path)
        return httpx.Response(200, content=b'{"type":"complete"}\n')
    backend = sprites(handler, connect=lambda url, token: Stopped([json.dumps({"type": "session_info",
                                                                              "session_id": "9"})]))
    with pytest.raises(ProviderCancelled):
        backend.exec("vm", "sleep 99", cwd="/home/sprite", timeout=60, on_output=lambda *a: None,
                     cancellation=cancellation)
    assert killed == ["/v1/sprites/vm/exec/9/kill"]


def test_the_provider_is_configured_by_its_token_only(monkeypatch):
    monkeypatch.delenv("SPRITES_TOKEN", raising=False)
    assert agent_vm.backend() is None and not agent_vm.configured()
    monkeypatch.setenv("SPRITES_TOKEN", "t")
    vm = agent_vm.backend()
    try:
        assert isinstance(vm, SpritesBackend) and agent_vm.configured()
    finally:
        vm.close()
