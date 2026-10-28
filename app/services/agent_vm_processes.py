"""Background processes in the agent's VM: a dev server, a long test run
(vm_start_process, vm_process_output, vm_stop_process; since 2026-10-26).

A process started with ``&`` in vm_exec stops when the VM pauses, which it
does after a few idle seconds, so between two of the agent's steps. A
background process here runs under a small supervisor script in the VM
(RUNNER) that holds the VM awake through the Sprites Tasks API on
``/.sprite/api.sock`` while the process lives: a hold of HOLD_EXPIRE,
refreshed every HEARTBEAT_SECONDS, released when the process ends. A crashed
supervisor's hold expires by itself.

Since the security audit of 2026-10-27 the supervisor is the server's: it
runs as the provider's user, its files lie in the provider's home, which the
agent cannot open, and the socket stays out of the agent's reach. Only the
command itself runs as the agent's user, through agent-run like every other
command of the agent (``launch.sh``, agent_vm.agent_argv).

Costs are capped: a process ends after ``max_seconds`` (default
DEFAULT_SECONDS, at most MAX_SECONDS; coreutils ``timeout`` in the VM, so
also without the backend), and at most MAX_RUNNING run at once. That bounds
what the VM can cost after the message is done to MAX_RUNNING x MAX_SECONDS
of awake time. A process outlives its message: the next one finds it by its
id (the work record names it, agent_compaction.work_record).

Everything lives in PROCESSES_DIR/<id>: the command, its combined output
(``output.log``), the supervisor's pid file and, once it ended, its exit
code. The VM holds no secret, so neither does any of it.
"""
from __future__ import annotations

import posixpath
import re
import secrets
import shlex

from pydantic import BaseModel, ConfigDict, Field

from app.services import agent_vm
from app.services.agent_tools import ReadOnlyTool

HOME = agent_vm.HOME
PROCESSES_DIR = agent_vm.SERVER_HOME + "/.consens/processes"
DEFAULT_SECONDS = 1800
MAX_SECONDS = 3600
MAX_RUNNING = 3
HEARTBEAT_SECONDS = 60
HOLD_EXPIRE = "5m"
OUTPUT_CHARS = 12_000
MAX_WAIT_SECONDS = 60
STOP_GRACE_SECONDS = 10
ID = r"^[a-f0-9]{8}$"
# The first line of every status: "consens-process <state> <bytes>".
STATUS_LINE = re.compile(r"^consens-process (running|lost|-?\d+) (\d+)$")

# The supervisor of one process (``bash run.sh <dir> <task>``): the agent's
# command (``launch.sh``, under its time limit), a Tasks API hold while it
# runs, its exit code once it ended, then the hold released.
RUNNER = r"""#!/bin/bash
# consens.io: one background process of the agent (agent_vm_processes.py).
dir="$1"; task="$2"
api() { curl -s --max-time 5 --unix-socket /.sprite/api.sock -H 'Content-Type: application/json' "$@" >/dev/null 2>&1; }
hold() { api -X PUT "http://sprite/v1/tasks/$task" -d '{"expire": "%(expire)s"}'; }
bash "$dir/launch.sh" > "$dir/output.log" 2>&1 < /dev/null &
child=$!
echo "$child" > "$dir/pid"
hold
while kill -0 "$child" 2>/dev/null; do
  for _ in $(seq %(heartbeat)d); do kill -0 "$child" 2>/dev/null || break; sleep 1; done
  kill -0 "$child" 2>/dev/null && hold
done
wait "$child"
echo "$?" > "$dir/exit_code"
api -X DELETE "http://sprite/v1/tasks/$task"
""" % {"expire": HOLD_EXPIRE, "heartbeat": HEARTBEAT_SECONDS}

PROCESSES_NOTE = ("It runs in the background: read its output with vm_process_output and end it with "
                  "vm_stop_process; it ends by itself after max_seconds.")


class VmStartProcessArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    command: str = Field(min_length=1, max_length=20_000, description="Shell command, run by bash in the background.")
    cwd: str = Field(default="", max_length=1024, description="Working directory; default this chat's folder.")
    max_seconds: int = Field(default=DEFAULT_SECONDS, ge=10, le=MAX_SECONDS,
                             description="The process is ended after this long.")


class VmProcessOutputArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str = Field(default="", pattern=r"^([a-f0-9]{8})?$", description="The process; empty lists all of them.")
    wait_seconds: int = Field(default=0, ge=0, le=MAX_WAIT_SECONDS,
                              description="Wait this long first, e.g. for a server to start.")


class VmStopProcessArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str = Field(pattern=ID)


def new_id():
    return secrets.token_hex(4)


def process_dir(process_id):
    return f"{PROCESSES_DIR}/{process_id}"


def launch_script(command, cwd, seconds):
    """``launch.sh``: the command as the agent's user in ``cwd``, with the
    login environment and under its time limit (agent_vm.wrapped_command),
    as one line of quoted words."""
    argv = agent_vm.wrapped_command(command, seconds, True, cwd=cwd)
    return "exec " + " ".join(shlex.quote(arg) for arg in argv) + "\n"


def status_command(directory, chars=OUTPUT_CHARS, wait=0):
    """Prints STATUS_LINE, then the end of the output."""
    d = shlex.quote(directory)
    return (f"{f'sleep {int(wait)}; ' if wait else ''}dir={d}; [ -d \"$dir\" ] || exit 5; "
            "code=$(cat \"$dir/exit_code\" 2>/dev/null); "
            "if [ -z \"$code\" ]; then pid=$(cat \"$dir/pid\" 2>/dev/null); "
            "if [ -n \"$pid\" ] && kill -0 \"$pid\" 2>/dev/null; then code=running; else code=lost; fi; fi; "
            "size=$(stat -c %s \"$dir/output.log\" 2>/dev/null || echo 0); "
            "printf 'consens-process %s %s\\n' \"$code\" \"$size\"; "
            f"tail -c {int(chars)} \"$dir/output.log\" 2>/dev/null; true")


def start_command(directory, task, *, wait=2, root=PROCESSES_DIR):
    """Refuses (exit 4) at MAX_RUNNING running processes, else starts the
    supervisor detached from this command (its own session, ``sid``) and
    reports after ``wait``."""
    d = shlex.quote(directory)
    count = (f"running=0; for p in {shlex.quote(root)}/*/; do [ -f \"$p/pid\" ] && [ ! -f \"$p/exit_code\" ] "
             "&& kill -0 \"$(cat \"$p/pid\")\" 2>/dev/null && running=$((running+1)); done; "
             f"if [ \"$running\" -ge {MAX_RUNNING} ]; then exit 4; fi; ")
    return (count + f"setsid nohup bash {d}/run.sh {d} {shlex.quote(task)} >/dev/null 2>&1 "
            f"< /dev/null & echo $! > {d}/sid; " + status_command(directory, wait=wait))


def stop_command(directory, task):
    """TERM to the command (sudo hands it on to coreutils ``timeout``, which
    ends the command's process group); after STOP_GRACE_SECONDS KILL to
    everything in the supervisor's session, as root where there is sudo:
    the command runs as the agent's user."""
    d = shlex.quote(directory)
    return (f"dir={d}; [ -d \"$dir\" ] || exit 5; pid=$(cat \"$dir/pid\" 2>/dev/null); "
            "sid=$(cat \"$dir/sid\" 2>/dev/null); "
            "[ -f \"$dir/exit_code\" ] || { [ -n \"$pid\" ] && kill -TERM \"$pid\" 2>/dev/null; }; "
            f"for _ in $(seq {STOP_GRACE_SECONDS}); do [ -f \"$dir/exit_code\" ] && break; sleep 1; done; "
            "if [ ! -f \"$dir/exit_code\" ]; then [ -n \"$pid\" ] && kill -KILL \"$pid\" 2>/dev/null; "
            "if [ -n \"$sid\" ]; then sudo -n pkill -KILL -s \"$sid\" 2>/dev/null || pkill -KILL -s \"$sid\" "
            "2>/dev/null; fi; echo 137 > \"$dir/exit_code\"; "
            "curl -s --max-time 5 --unix-socket /.sprite/api.sock -X DELETE "
            f"http://sprite/v1/tasks/{shlex.quote(task)} >/dev/null 2>&1; fi; " + status_command(directory))


def list_command(root=PROCESSES_DIR):
    return (f"for d in {shlex.quote(root)}/*/; do [ -d \"$d\" ] || continue; id=$(basename \"$d\"); "
            "code=$(cat \"$d/exit_code\" 2>/dev/null); if [ -z \"$code\" ]; then pid=$(cat \"$d/pid\" 2>/dev/null); "
            "if [ -n \"$pid\" ] && kill -0 \"$pid\" 2>/dev/null; then code=running; else code=lost; fi; fi; "
            "printf '%s\\t%s\\t%s\\n' \"$id\" \"$code\" \"$(head -c 200 \"$d/command\" 2>/dev/null | tr '\\n\\t' '  ')\"; "
            "done; true")


def task_name(process_id):
    return f"consens-{process_id}"


def parse_status(text):
    """``(state, bytes, output)`` of a status command's output: state is
    "running", "lost" (the VM stopped it, e.g. while paused without a hold)
    or the exit code."""
    first, _, rest = text.partition("\n")
    match = STATUS_LINE.match(first.strip())
    if not match:
        raise ValueError("The process status could not be read.")
    state = match.group(1)
    return (state if state in {"running", "lost"} else int(state)), int(match.group(2)), rest


class ProcessTools:
    """The background-process tools of one message, next to its VM tools."""

    def __init__(self, vm_tools):
        self.vm = vm_tools

    def tools(self):
        return [
            ReadOnlyTool("vm_start_process", "Start a command in the background in your VM, such as a dev server or "
                         "a long test run (at most three at once). Returns its id and first output.",
                         VmStartProcessArgs, self.start, activity=self._activity, reports=True),
            ReadOnlyTool("vm_process_output", "Read the end of a background process's output and whether it still "
                         "runs, optionally after waiting; without id, list the processes.",
                         VmProcessOutputArgs, self.output, activity=self._activity, reports=True),
            ReadOnlyTool("vm_stop_process", "Stop a background process.", VmStopProcessArgs, self.stop,
                         activity=self._activity, reports=True),
        ]

    def _run(self, command, cancellation, timeout):
        """One command of the server in the VM, counted as VM time
        (VMTools._exec); ``(exit_code, stdout)``."""
        from app.services.agent_vm_tools import _Output
        output = _Output()
        outcome = self.vm._exec(command, cwd=agent_vm.SERVER_HOME, timeout=timeout, on_output=output.add,
                                cancellation=cancellation, agent=False)
        return outcome.exit_code, bytes(output.streams["stdout"]).decode("utf-8", "replace")

    def _result(self, process_id, text, extra=None):
        from app.services.agent_vm_tools import clean, model_text
        state, size, output = parse_status(text)
        raw = output.encode("utf-8")
        result = {"id": process_id, "status": "running" if state == "running" else "lost" if state == "lost"
                  else "exited", "output": model_text(raw, max(size, len(raw)), "output")}
        if isinstance(state, int):
            result["exit_code"] = state
        if state == "lost":
            result["note"] = "The process is gone without an exit code: the VM stopped it. Start it again."
        return {**result, **(extra or {}), "_view": clean(output)[-2000:]}

    def start(self, args, *, cancellation, report=None):
        from app.services.agent_vm_tools import vm_path
        report = report or (lambda fields: None)
        from app.services.agent_vm_tools import VM_DAY_LIMIT
        self.vm._start(cancellation)
        cwd = vm_path(args.cwd, self.vm.session.dir) if args.cwd.strip() else self.vm.session.dir
        session = self.vm.session
        # It holds the VM awake for up to its time limit, after the message
        # too: that whole limit counts against today's VM time, and it never
        # runs past what is left (agent_vm_time.py).
        seconds = args.max_seconds
        left = session.left()
        if left is not None:
            if left < 60:
                raise ValueError(VM_DAY_LIMIT)
            seconds = min(seconds, int(left))
        process_id = new_id()
        directory = process_dir(process_id)
        for name, content in (("run.sh", RUNNER), ("launch.sh", launch_script(args.command, cwd, seconds)),
                              ("command", args.command)):
            self.vm._provider("write", lambda name=name, content=content: session.backend.write_file(
                session.name, posixpath.join(directory, name), content.encode("utf-8"), agent=False))
        code, text = self._run(start_command(directory, task_name(process_id)), cancellation, 30)
        if code == 4:
            raise ValueError(f"{MAX_RUNNING} background processes are already running. Stop one with "
                             "vm_stop_process first.")
        if code != 0:
            raise ValueError("The background process could not be started.")
        with session._lock:
            session.reserved += seconds
        result = self._result(process_id, text, {"max_seconds": seconds, "note": PROCESSES_NOTE})
        report({"output": result.pop("_view"), "process": process_id})
        return self.vm.session.announce(result)

    def output(self, args, *, cancellation, report=None):
        report = report or (lambda fields: None)
        self.vm._start(cancellation)
        if not args.id:
            code, text = self._run(list_command(), cancellation, 30)
            processes = []
            for line in text.splitlines():
                parts = line.split("\t", 2)
                if len(parts) == 3 and re.fullmatch(ID, parts[0]):
                    state = parts[1]
                    processes.append({"id": parts[0], "status": state if state in {"running", "lost"} else "exited",
                                      **({"exit_code": int(state)} if re.fullmatch(r"-?\d+", state) else {}),
                                      "command": parts[2].strip()})
            return self.vm.session.announce({"processes": processes})
        wait = args.wait_seconds
        left = self.vm.loop.answer_time_left() if hasattr(self.vm.loop, "answer_time_left") else None
        if left is not None:
            wait = max(0, min(wait, int(left) - 15))
        # The wait runs in the VM and counts as VM time: never past today's.
        day = self.vm.session.left()
        if day is not None:
            wait = max(0, min(wait, int(day)))
        code, text = self._run(status_command(process_dir(args.id), wait=wait), cancellation, wait + 30)
        if code == 5:
            raise ValueError(f"No background process {args.id}. List them with vm_process_output without an id.")
        result = self._result(args.id, text)
        report({"output": result.pop("_view"), "process": args.id})
        return self.vm.session.announce(result)

    def stop(self, args, *, cancellation, report=None):
        report = report or (lambda fields: None)
        self.vm._start(cancellation)
        code, text = self._run(stop_command(process_dir(args.id), task_name(args.id)), cancellation,
                               STOP_GRACE_SECONDS + 30)
        if code == 5:
            raise ValueError(f"No background process {args.id}. List them with vm_process_output without an id.")
        result = self._result(args.id, text)
        report({"output": result.pop("_view"), "process": args.id})
        return self.vm.session.announce(result)

    def _activity(self, args, result):
        fields = {"command": args.command} if isinstance(args, VmStartProcessArgs) else {"process": args.id or ""}
        if isinstance(result, dict):
            if "id" in result:
                fields["process"] = result["id"]
            if "exit_code" in result:
                fields["exit_code"] = result["exit_code"]
            if result.get("status") in {"running", "lost"}:
                fields["process_status"] = result["status"]
        return {**fields, **self.vm._outcome(result)}
