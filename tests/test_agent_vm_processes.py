"""Background processes in the agent's VM (agent_vm_processes.py): a dev
server or a long test run under a supervisor that holds the VM awake while it
runs, capped in time and number. The tool layer runs against FakeVM
(test_agent_vm.py); the shell scripts themselves run in a real bash (on
Windows with a stand-in for setsid), never in a VM, with a stand-in for
agent-run (launch.sh), which ran on a test Sprite (docs/agent-mode.md).
"""
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import time

import pytest

from app.services import agent_vm, agent_vm_processes, agent_vm_tools
from app.services.agent_compaction import describe
from app.services.agent_vm_processes import (MAX_RUNNING, RUNNER, launch_script, list_command, parse_status,
                                             process_dir, start_command, status_command, stop_command, task_name)
from test_agent_runs import UID, store  # noqa: F401  (fixture)
from test_agent_vm import NAME, NO_NOTES, Agent, chat_path, _admin_allowance, fake_vm, results, tool_events, vm_loop  # noqa: F401  (fixtures)

PID = "abcd1234"


@pytest.fixture
def fixed_id(monkeypatch):
    monkeypatch.setattr(agent_vm_processes, "new_id", lambda: PID)


def status(state, text):
    return [("stdout", f"consens-process {state} {len(text)}\n{text}".encode())]


def test_a_background_process_starts_under_its_supervisor(store, fake_vm, fixed_id):
    directory = process_dir(PID)
    fake_vm.commands[start_command(directory, task_name(PID))] = (status("running", "Listening on :3000\n"), 0, 2.0)
    fake_vm.commands[status_command(directory, wait=5)] = (status("running", "GET / 200\n"), 0, 5.0)
    fake_vm.commands[stop_command(directory, task_name(PID))] = (status("stopped", "GET / 200\nbye\n"), 0, 1.0)
    script = Agent([[("vm_start_process", {"command": "npm run dev", "cwd": "app"})],
                    [("vm_process_output", {"id": PID, "wait_seconds": 5})],
                    [("vm_stop_process", {"id": PID})]])
    loop = vm_loop(store, script)
    events = list(loop.run())
    assert {"vm_start_process", "vm_process_output", "vm_stop_process"} <= set(script.offered[0])
    started, read, stopped = results(loop)
    assert started["id"] == PID and started["status"] == "running" and started["output"] == "Listening on :3000\n"
    assert started["max_seconds"] == 1800 and "vm_stop_process" in started["note"]
    assert read == {"id": PID, "status": "running", "output": "GET / 200\n"}
    # Ended by the agent: "stopped", no exit code (timeout's 124 read as its limit, 2026-10-28).
    assert stopped == {"id": PID, "status": "stopped", "output": "GET / 200\nbye\n"}
    # The supervisor in the server's own folder, the command as the agent's
    # user in its folder and login environment, the command for listing.
    files = fake_vm.vms[agent_vm.workspace_name(UID)]["files"]
    assert directory.startswith("/home/sprite/.consens/processes/")
    assert files[f"{directory}/run.sh"].decode() == RUNNER
    launch = files[f"{directory}/launch.sh"].decode()
    assert launch == launch_script("npm run dev", chat_path(loop.chat_id) + "/app", 1800)
    assert shlex.split(launch)[1:7] == ["sudo", "-n", "/bin/bash", agent_vm.AGENT_RUN, "1800",
                                        chat_path(loop.chat_id) + "/app"]
    assert files[f"{directory}/command"] == b"npm run dev"
    assert {path for _, path in fake_vm.server_files if path.startswith(directory)} == {
        f"{directory}/run.sh", f"{directory}/launch.sh", f"{directory}/command", f"{directory}/reserve"}
    # Started, read and stopped by the server, which holds the VM awake.
    assert fake_vm.server[-3:] == [start_command(directory, task_name(PID)), status_command(directory, wait=5),
                                   stop_command(directory, task_name(PID))]
    # The activity shows the command and its first output, later the process by its id.
    assert [e for e in tool_events(events, "vm_start_process") if e["status"] == "running"][0]["command"] == "npm run dev"
    # Saved as the browser merges the updates of each call.
    saved = {e["name"]: e for e in store.get_turn(UID, loop.chat_id, loop.turn_id)["agent_activity"]
             if e.get("kind") == "tool"}
    start, stop = saved["vm_start_process"], saved["vm_stop_process"]
    assert start["command"] == "npm run dev" and start["output"] == "Listening on :3000\n"
    assert start["process"] == PID and start["process_status"] == "running"
    assert stop["process"] == PID and stop["process_status"] == "stopped" and "exit_code" not in stop
    assert stop["output"] == "GET / 200\nbye\n"
    # The next message knows the process by its id.
    assert describe("vm_start_process", json.dumps({"command": "npm run dev"}), json.dumps(started)) == (
        f"vm_start_process {PID} $ npm run dev -> running: Listening on :3000")


def test_a_process_counts_with_its_whole_time_limit_against_the_days_vm_time(store, fake_vm, fixed_id, monkeypatch):
    """It holds the VM awake up to its limit, after the message too: that limit
    is charged, at most half of what is left today (DAY_SHARE, since
    2026-10-31), so the commands around it still run (agent_vm_time.py)."""
    from app.services import agent_vm_time
    monkeypatch.setattr(agent_vm_time, "daily_limit", lambda uid: 1000)
    directory = process_dir(PID)
    fake_vm.commands[start_command(directory, task_name(PID))] = (status("running", "Listening\n"), 0, 2.0)
    loop = vm_loop(store, Agent([[("vm_start_process", {"command": "npm run dev", "max_seconds": 1800})]]))
    list(loop.run())
    started = results(loop)[0]
    assert started["status"] == "running" and started["max_seconds"] == 500
    assert "at most half of what is left of today's VM time" in started["note"]
    # Its limit, and the start's own 2 s: every command the server runs for
    # the agent counts (VMTools._exec, security audit 2026-10-27).
    assert agent_vm_time.used(store.db, UID) == 502


def test_a_dev_server_leaves_an_account_without_pro_its_commands_output_and_stop(store, fake_vm, fixed_id,
                                                                               monkeypatch):
    """Bug 2026-10-31: at its default limit (30 minutes) a dev server reserved
    all 20 minutes of an account without Pro, and its own agent could then
    neither read its output, nor stop it, nor run a command."""
    from app.services import agent_vm_time
    monkeypatch.setattr(agent_vm_time, "daily_limit", lambda uid: agent_vm_time.BASE_DAILY_SECONDS)
    directory = process_dir(PID)
    fake_vm.commands[start_command(directory, task_name(PID))] = (status("running", "Listening on :3000\n"), 0, 2.0)
    fake_vm.commands[status_command(directory, wait=5)] = (status("running", "GET / 200\n"), 0, 5.0)
    fake_vm.commands["curl -s localhost:3000"] = ([("stdout", b"<html>\n")], 0, 1.0)
    fake_vm.commands[stop_command(directory, task_name(PID))] = (status("stopped", "bye\n"), 0, 1.0)
    loop = vm_loop(store, Agent([[("vm_start_process", {"command": "npm run dev"})],
                                 [("vm_process_output", {"id": PID, "wait_seconds": 5})],
                                 [("vm_exec", {"command": "curl -s localhost:3000"})],
                                 [("vm_stop_process", {"id": PID})]]))
    list(loop.run())
    started, read, fetched, stopped = results(loop)
    assert started["max_seconds"] == 600
    # Twenty minutes, less than the note's threshold: the first result says what is left.
    assert started["vm_time_left_today"]["minutes"] == 9
    assert read["output"] == "GET / 200\n" and fetched["exit_code"] == 0 and stopped["status"] == "stopped"


def test_a_process_can_be_read_and_stopped_once_the_days_vm_time_is_used_up(store, fake_vm, fixed_id, monkeypatch):
    """Reading a process's output and stopping it count nothing worth
    refusing (stopping gives time back): they go on when the day's VM time is
    used up, a new process does not (VMTools._start ``spends``)."""
    from app.services import agent_vm_time
    monkeypatch.setattr(agent_vm_time, "daily_limit", lambda uid: 100)
    agent_vm_time.charge(store, UID, 100)
    directory = process_dir(PID)
    fake_vm.commands[status_command(directory)] = (status("running", "GET / 200\n"), 0, .1)
    fake_vm.commands[stop_command(directory, task_name(PID))] = (status("stopped", "bye\n"), 0, 1.0)
    loop = vm_loop(store, Agent([[("vm_process_output", {"id": PID, "wait_seconds": 30})],
                                 [("vm_stop_process", {"id": PID})],
                                 [("vm_start_process", {"command": "npm run dev"})]]))
    list(loop.run())
    read, stopped, started = results(loop)
    assert read["output"] == "GET / 200\n" and stopped["status"] == "stopped"
    assert started == {"error": agent_vm_tools.VM_DAY_LIMIT}
    # The wait went down to nothing: it would have run in the VM.
    assert ("exec", NAME, status_command(directory, wait=30)) not in [call[:3] for call in fake_vm.calls]


def test_waiting_for_a_process_counts_and_never_runs_past_the_days_vm_time(store, fake_vm, fixed_id, monkeypatch):
    """Security audit 2026-10-27: vm_process_output with wait_seconds ran in
    the VM without counting. The wait is VM time now, capped by what is left."""
    from app.services import agent_vm_time
    monkeypatch.setattr(agent_vm_time, "daily_limit", lambda uid: 100)
    agent_vm_time.charge(store, UID, 70)
    fake_vm.commands[status_command(process_dir(PID), wait=30)] = (status("running", "Still going\n"), 0, 25.0)
    loop = vm_loop(store, Agent([[("vm_process_output", {"id": PID, "wait_seconds": 60})]]))
    list(loop.run())
    assert results(loop)[0]["status"] == "running"
    assert agent_vm_time.used(store.db, UID) == 70 + 25


def test_the_number_of_processes_and_their_time_are_capped(store, fake_vm, fixed_id):
    directory = process_dir(PID)
    fake_vm.commands[start_command(directory, task_name(PID))] = ([], 4, .1)
    loop = vm_loop(store, Agent([[("vm_start_process", {"command": "sleep 1000", "max_seconds": 60})],
                                 [("vm_process_output", {"id": "ffffffff"})],
                                 [("vm_start_process", {"command": "x", "max_seconds": 7200})]]))
    fake_vm.commands[status_command(process_dir("ffffffff"))] = ([], 5, .1)
    list(loop.run())
    capped, missing, too_long = results(loop)
    assert f"{MAX_RUNNING} background processes are already running" in capped["error"]
    # Its files go again: the list never shows it as "lost" (2026-10-28).
    assert ("delete_path", NAME, directory) in fake_vm.calls
    assert not [path for path in fake_vm.vms[NAME]["files"] if path.startswith(directory + "/")]
    assert "No background process ffffffff" in missing["error"]
    assert "max_seconds" in too_long["error"] or "3600" in too_long["error"]


def test_without_an_id_the_processes_are_listed(store, fake_vm):
    fake_vm.commands[list_command()] = ([("stdout", b"abcd1234\trunning\tnpm run dev\n"
                                                    b"0000ffff\t1\tpytest -q\nnot a line\n")], 0, .1)
    loop = vm_loop(store, Agent([[("vm_process_output", {})]]))
    list(loop.run())
    assert results(loop)[0] == {"processes": [
        {"id": "abcd1234", "status": "running", "command": "npm run dev"},
        {"id": "0000ffff", "status": "exited", "exit_code": 1, "command": "pytest -q"}],
        "chat_folder": chat_path(loop.chat_id), "workspace_notes": NO_NOTES}


def test_a_process_the_vm_stopped_is_said_to_be_lost():
    state, size, output = parse_status("consens-process lost 4\nhalf")
    assert (state, size, output) == ("lost", 4, "half")
    with pytest.raises(ValueError):
        parse_status("something else")


# --- The scripts in a real bash ----------------------------------------------------

def bash():
    found = shutil.which("bash")
    if not found:
        pytest.skip("no bash")
    return found


@pytest.fixture
def shell(tmp_path):
    """Runs a command like the VM would, in a folder of its own; on Windows
    with a stand-in for setsid (Git Bash has none)."""
    executable = bash()
    env = dict(os.environ)
    if sys.platform == "win32" or not shutil.which("setsid"):
        shims = tmp_path / "shims"
        shims.mkdir()
        (shims / "setsid").write_text('#!/bin/bash\nexec "$@"\n', newline="\n")
        env["PATH"] = f"{shims.as_posix()}{os.pathsep if sys.platform != 'win32' else ':'}{env['PATH']}"

    def run(command):
        done = subprocess.run([executable, "-c", command], capture_output=True, env=env, timeout=60)
        return done.returncode, done.stdout.decode("utf-8", "replace")
    root = (tmp_path / "processes").as_posix()
    return run, root


def prepare(root, process_id, command, cwd, seconds=60):
    """The process's files; launch.sh as agent-run would run it (folder,
    limit), without sudo and the agent's user."""
    directory = f"{root}/{process_id}"
    Path(directory).mkdir(parents=True)
    launch = f"cd {shlex.quote(cwd)} || exit 1\nexec timeout --kill-after=5 {seconds} bash -c {shlex.quote(command)}\n"
    for name, content in (("run.sh", RUNNER), ("launch.sh", launch), ("command", command)):
        Path(directory, name).write_text(content, newline="\n")
    return directory


def wait_for(path, seconds=15):
    end = time.monotonic() + seconds
    while time.monotonic() < end and not Path(path).exists():
        time.sleep(.2)
    return Path(path).exists()


def test_the_supervisor_runs_a_command_to_its_end(shell, tmp_path):
    run, root = shell
    directory = prepare(root, "11111111", "echo hello; pwd; exit 3", tmp_path.as_posix())
    code, text = run(start_command(directory, "consens-11111111", wait=0, root=root))
    assert code == 0 and text.startswith("consens-process ")
    assert wait_for(f"{directory}/exit_code")
    code, text = run(status_command(directory))
    state, _, output = parse_status(text)
    assert code == 0 and state == 3 and output.startswith("hello\n")


def test_the_supervisor_stops_a_process_and_counts_the_running_ones(shell, tmp_path):
    run, root = shell
    directories = [prepare(root, f"2222222{n}", "sleep 30", tmp_path.as_posix()) for n in range(MAX_RUNNING + 1)]
    for directory in directories[:MAX_RUNNING]:
        code, _ = run(start_command(directory, "consens-x", wait=0, root=root))
        assert code == 0
        assert wait_for(f"{directory}/pid")
    time.sleep(.5)
    # One more is refused while three run.
    code, _ = run(start_command(directories[-1], "consens-x", wait=0, root=root))
    assert code == 4
    listed = run(list_command(root=root))[1].splitlines()
    assert sorted(line.split("\t")[1] for line in listed) == ["lost", "running", "running", "running"]
    for directory in directories[:MAX_RUNNING]:
        code, text = run(stop_command(directory, "consens-x"))
        state, _, _ = parse_status(text)
        assert code == 0 and state == "stopped"
    code, text = run(status_command(directories[0]))
    assert parse_status(text)[0] == "stopped"
    listed = run(list_command(root=root))[1].splitlines()
    assert sorted(line.split("\t")[1] for line in listed) == ["lost", "stopped", "stopped", "stopped"]


def test_the_supervisor_ends_a_process_at_its_time_limit(shell, tmp_path):
    run, root = shell
    directory = prepare(root, "33333333", "echo started; sleep 30", tmp_path.as_posix(), seconds=1)
    run(start_command(directory, "consens-33333333", wait=0, root=root))
    assert wait_for(f"{directory}/exit_code", seconds=20)
    state, _, output = parse_status(run(status_command(directory))[1])
    # coreutils timeout: 124 after its limit.
    assert state == 124 and output == "started\n"


def test_a_process_that_ends_early_gives_its_unused_time_back_once(store, fake_vm, fixed_id, monkeypatch):
    """Its whole limit is charged when it starts; once a look finds it ended,
    what it did not run comes back (runtime audit 2026-10-30, K5): to the
    message that started it, or to the day it was charged on, never twice."""
    from app.services import agent_vm_time
    from app.services.agent_vm_processes import spent
    monkeypatch.setattr(agent_vm_time, "daily_limit", lambda uid: 7200)
    day = agent_vm_time.day_key()
    directory = process_dir(PID)

    def ended(ran, refunded=0):
        return [("stdout", f"consens-process 0 4 {ran} 1800 {day} {refunded}\nbye\n".encode())]
    fake_vm.commands[start_command(directory, task_name(PID))] = (status("running", "Listening\n"), 0, 2.0)
    fake_vm.commands[stop_command(directory, task_name(PID))] = (ended(100), 0, 1.0)
    loop = vm_loop(store, Agent([[("vm_start_process", {"command": "npm run dev"})],
                                 [("vm_stop_process", {"id": PID})]]))
    list(loop.run())
    assert results(loop)[1]["status"] == "exited"
    # 1800 s reserved, 100 s ran: the message charged 100 s and the commands' own 3 s.
    assert agent_vm_time.used(store.db, UID) == 103
    files = fake_vm.vms[agent_vm.workspace_name(UID)]["files"]
    assert files[f"{directory}/reserve"] == f"1800 {day}".encode() and files[f"{directory}/refunded"] == b"1"
    # A later message that stops one of an earlier message gives back to its day.
    agent_vm_time.charge(store, UID, 1800)
    fake_vm.commands[stop_command(directory, task_name(PID))] = (ended(300), 0, 1.0)
    del files[f"{directory}/refunded"]
    later = vm_loop(store, Agent([[("vm_stop_process", {"id": PID})]]), chat_id=loop.chat_id, request_id="later")
    list(later.run())
    assert agent_vm_time.used(store.db, UID) == 103 + 1800 - 1500 + 1
    # Already given back: nothing more.
    fake_vm.commands[stop_command(directory, task_name(PID))] = (ended(300, refunded=1), 0, 1.0)
    again = vm_loop(store, Agent([[("vm_stop_process", {"id": PID})]]), chat_id=loop.chat_id, request_id="again")
    list(again.run())
    assert agent_vm_time.used(store.db, UID) == 103 + 1800 - 1500 + 2
    # A process from before 2026-10-30 says nothing of its time.
    assert spent("consens-process 0 4\nbye") is None and spent("consens-process running 4 - 1800 2026-10-30 0") is None
