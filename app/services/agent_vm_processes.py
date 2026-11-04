"""Background processes in the agent's VM: a dev server, a long test run.

A process started with ``&`` in vm_exec ends with its command. One started here runs under a
supervisor script (RUNNER) that holds the VM awake through the Sprites Tasks API while the process
lives, else the VM pauses between two of the agent's steps; a crashed supervisor's hold expires by
itself. The supervisor is the server's (the provider's user and home, out of the agent's reach);
only the command runs as the agent's user through agent-run.

A process ends after ``max_seconds`` and at most MAX_RUNNING run at once, which bounds what the VM
can cost after the message. Its whole limit counts as VM time when it starts, at most DAY_SHARE of
what is left today; once a look finds it ended, the unused time is given back once (``refunded``). A
process outlives its message and goes with the chat that started it. Everything lives in
PROCESSES_DIR/<id>; the VM holds no secret, so neither does any of it."""
from __future__ import annotations

import logging
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
# So the commands around it still run: a dev server at its default limit reserved all of a Free
# account's time.
DAY_SHARE = 0.5
HEARTBEAT_SECONDS = 60
HOLD_EXPIRE = "5m"
OUTPUT_CHARS = 12_000
MAX_WAIT_SECONDS = 60
STOP_GRACE_SECONDS = 10
ID = r"^[a-f0-9]{8}$"
# "consens-process <state> <bytes>", then once it ended the seconds it ran, the VM time it was
# charged (seconds, day) and whether the rest was given back.
STATUS_LINE = re.compile(r"^consens-process (running|lost|stopped|-?\d+) (\d+)"
                         r"(?: (-|\d+) (-|\d+) (-|\d{4}-\d{2}-\d{2}) ([01]))?$")

# The supervisor of one process (``bash run.sh <dir> <task>``): the command under its limit, a Tasks
# API hold while it runs, its exit code, then the hold released.
RUNNER = r"""#!/bin/bash
# consens.io: one background process of the agent (agent_vm_processes.py).
dir="$1"; task="$2"
api() { curl -s --max-time 5 --unix-socket /.sprite/api.sock -H 'Content-Type: application/json' "$@" >/dev/null 2>&1; }
hold() { api -X PUT "http://sprite/v1/tasks/$task" -d '{"expire": "%(expire)s"}'; }
date +%%s > "$dir/started"
bash "$dir/launch.sh" > "$dir/output.log" 2>&1 < /dev/null &
child=$!
echo "$child" > "$dir/pid"
hold
while kill -0 "$child" 2>/dev/null; do
  for _ in $(seq %(heartbeat)d); do kill -0 "$child" 2>/dev/null || break; sleep 1; done
  kill -0 "$child" 2>/dev/null && hold
done
wait "$child"
code=$?
date +%%s > "$dir/ended"
echo "$code" > "$dir/exit_code"
api -X DELETE "http://sprite/v1/tasks/$task"
""" % {"expire": HOLD_EXPIRE, "heartbeat": HEARTBEAT_SECONDS}

PROCESSES_NOTE = ("It runs in the background: read its output with vm_process_output and end it with "
                  "vm_stop_process; it ends by itself after max_seconds.")
FOREGROUND_NOTE = ("Its command left processes running in the background (with & or nohup), and they were ended "
                   "when it ended: run the server in the foreground of the command, then it runs as long as the "
                   "process.")


class VmStartProcessArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    command: str = Field(min_length=1, max_length=20_000, description="Shell command, run by bash in the background.")
    cwd: str = Field(default="", max_length=1024, description="Working directory; default this chat's folder.")
    max_seconds: int = Field(default=DEFAULT_SECONDS, ge=10, le=MAX_SECONDS,
                             description=f"The process is ended after this long (default {DEFAULT_SECONDS // 60} minutes).")


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
    """``launch.sh``: the command as the agent's user in ``cwd`` with the login environment and its
    time limit, as one line of quoted words. What it leaves running ends with it."""
    argv = agent_vm.wrapped_command(command, seconds, True, cwd=cwd)
    return "exec " + " ".join(shlex.quote(arg) for arg in argv) + "\n"


def status_command(directory, chars=OUTPUT_CHARS, wait=0):
    d = shlex.quote(directory)
    return (f"{f'sleep {int(wait)}; ' if wait else ''}dir={d}; [ -d \"$dir\" ] || exit 5; "
            "code=$(cat \"$dir/exit_code\" 2>/dev/null); "
            "if [ -z \"$code\" ]; then pid=$(cat \"$dir/pid\" 2>/dev/null); "
            "if [ -n \"$pid\" ] && kill -0 \"$pid\" 2>/dev/null; then code=running; else code=lost; fi; fi; "
            "[ -f \"$dir/stopped\" ] && [ \"$code\" != running ] && code=stopped; "
            "size=$(stat -c %s \"$dir/output.log\" 2>/dev/null || echo 0); "
            "ran=-; if [ -f \"$dir/exit_code\" ]; then s=$(cat \"$dir/started\" 2>/dev/null); "
            "e=$(cat \"$dir/ended\" 2>/dev/null || date +%s); "
            "case \"$s:$e\" in *[!0-9:]*|:*|*:) ;; *) ran=$((e - s)); [ \"$ran\" -ge 0 ] || ran=-;; esac; fi; "
            "res=$(head -c 40 \"$dir/reserve\" 2>/dev/null | tr -cd '0-9 -'); "
            "case \"$res\" in [0-9]*\\ [0-9]*-[0-9]*-[0-9]*) ;; *) res='- -';; esac; "
            "ref=0; [ -f \"$dir/refunded\" ] && ref=1; "
            "printf 'consens-process %s %s %s %s %s\\n' \"$code\" \"$size\" \"$ran\" \"$res\" \"$ref\"; "
            f"tail -c {int(chars)} \"$dir/output.log\" 2>/dev/null; true")


def start_command(directory, task, *, wait=2, root=PROCESSES_DIR):
    """Refuses (exit 4) at MAX_RUNNING running processes, else starts the supervisor in its own
    session and reports after ``wait``."""
    d = shlex.quote(directory)
    count = (f"running=0; for p in {shlex.quote(root)}/*/; do [ -f \"$p/pid\" ] && [ ! -f \"$p/exit_code\" ] "
             "&& kill -0 \"$(cat \"$p/pid\")\" 2>/dev/null && running=$((running+1)); done; "
             f"if [ \"$running\" -ge {MAX_RUNNING} ]; then exit 4; fi; ")
    return (count + f"setsid nohup bash {d}/run.sh {d} {shlex.quote(task)} >/dev/null 2>&1 "
            f"< /dev/null & echo $! > {d}/sid; " + status_command(directory, wait=wait))


def stop_command(directory, task):
    """TERM to the command (timeout ends its process group, agent-run what it left); after
    STOP_GRACE_SECONDS KILL to the supervisor's session, as root where there is sudo. Signals go
    only while the session is still this process's run.sh: after a cold start or a restore its pids
    may be others'."""
    d = shlex.quote(directory)
    return (f"dir={d}; [ -d \"$dir\" ] || exit 5; pid=$(cat \"$dir/pid\" 2>/dev/null); "
            "sid=$(cat \"$dir/sid\" 2>/dev/null); ours=; "
            "case \"$sid\" in ''|*[!0-9]*) ;; *) tr '\\0' '\\n' 2>/dev/null < \"/proc/$sid/cmdline\" "
            "| grep -qxF -- \"$dir/run.sh\" && ours=1;; esac; "
            "case \"$pid\" in ''|*[!0-9]*) pid=;; esac; [ -n \"$ours\" ] || pid=; "
            "[ -f \"$dir/exit_code\" ] || { : > \"$dir/stopped\"; [ -n \"$pid\" ] && kill -TERM \"$pid\" 2>/dev/null; }; "
            "if [ -n \"$ours\" ]; then "
            f"for _ in $(seq {STOP_GRACE_SECONDS}); do [ -f \"$dir/exit_code\" ] && break; sleep 1; done; fi; "
            "if [ ! -f \"$dir/exit_code\" ]; then if [ -n \"$ours\" ]; then [ -n \"$pid\" ] && kill -KILL \"$pid\" 2>/dev/null; "
            "sudo -n pkill -KILL -s \"$sid\" 2>/dev/null || pkill -KILL -s \"$sid\" 2>/dev/null; fi; "
            "date +%s > \"$dir/ended\"; echo 137 > \"$dir/exit_code\"; "
            "curl -s --max-time 5 --unix-socket /.sprite/api.sock -X DELETE "
            f"http://sprite/v1/tasks/{shlex.quote(task)} >/dev/null 2>&1; fi; " + status_command(directory))


def list_command(root=PROCESSES_DIR, chat=""):
    """The processes, one per line: id, state, the command's start. A temporary chat's only for
    ``chat`` itself."""
    return (f"chat={shlex.quote(chat)}; for d in {shlex.quote(root)}/*/; do [ -d \"$d\" ] || continue; "
            "if [ -f \"$d/temporary\" ] && [ \"$(head -c 100 \"$d/chat\" 2>/dev/null)\" != \"$chat\" ]; then "
            "continue; fi; id=$(basename \"$d\"); "
            "code=$(cat \"$d/exit_code\" 2>/dev/null); if [ -z \"$code\" ]; then pid=$(cat \"$d/pid\" 2>/dev/null); "
            "if [ -n \"$pid\" ] && kill -0 \"$pid\" 2>/dev/null; then code=running; else code=lost; fi; fi; "
            "[ -f \"$d/stopped\" ] && [ \"$code\" != running ] && code=stopped; "
            "printf '%s\\t%s\\t%s\\n' \"$id\" \"$code\" \"$(head -c 200 \"$d/command\" 2>/dev/null | tr '\\n\\t' '  ')\"; "
            "done; true")


def task_name(process_id):
    return f"consens-{process_id}"


def chat_command(chat_id, root=PROCESSES_DIR):
    """The processes ``chat_id`` started, one per line: the id, then ``running`` or ``ended``."""
    return (f"chat={shlex.quote(chat_id)}; for d in {shlex.quote(root)}/*/; do [ -f \"$d/chat\" ] || continue; "
            "[ \"$(head -c 100 \"$d/chat\")\" = \"$chat\" ] || continue; state=ended; "
            "pid=$(cat \"$d/pid\" 2>/dev/null); if [ ! -f \"$d/exit_code\" ] && [ -n \"$pid\" ] "
            "&& kill -0 \"$pid\" 2>/dev/null; then state=running; fi; "
            "printf '%s %s\\n' \"$(basename \"$d\")\" \"$state\"; done; true")


def delete_for_chat(vm, name, chat_id, *, refund=None):
    """With its chat: the background processes it started, a running one stopped, and their folders.
    ``refund(seconds, day)`` gives back unused VM time as a look would. Raises VMUnavailable when
    the provider fails or the list was not whole, so the deletion retries."""
    from app.services import agent_vm_time
    from app.services.llm.provider_runtime import ProviderCancellation

    def run(command, timeout):
        out = bytearray()

        def keep(stream, chunk):
            if stream == "stdout" and len(out) < OUTPUT_CHARS * 2:
                out.extend(chunk)
        outcome = vm.exec(name, command, cwd=agent_vm.SERVER_HOME, timeout=timeout, on_output=keep,
                          cancellation=ProviderCancellation(), agent=False)
        return outcome.exit_code, out.decode("utf-8", "replace")
    code, listed = run(chat_command(chat_id), 30)
    if code != 0:
        raise agent_vm.VMUnavailable(f"processes: exit {code}")
    for line in dict.fromkeys(listed.splitlines()):
        process_id, _, state = line.partition(" ")
        if not re.match(ID, process_id):
            continue
        directory = process_dir(process_id)
        if state == "running":
            _, text = run(stop_command(directory, task_name(process_id)), STOP_GRACE_SECONDS + 30)
        else:
            _, text = run(status_command(directory, chars=0), 30)
        found = spent(text)
        if refund is not None and found is not None:
            ran, reserved, day, refunded = found
            if not refunded and reserved > ran and day == agent_vm_time.day_key():
                # Marked first: the deletion and a stopped message's sweep never both give it back.
                vm.write_file(name, posixpath.join(directory, "refunded"), b"1", agent=False)
                refund(reserved - ran, day)
        vm.delete_path(name, directory, agent=False)


def parse_status(text):
    """``(state, bytes, output)``: "running", "lost" (the VM stopped it), "stopped" (vm_stop_process
    ended it; timeout's 124 would read as its limit) or the exit code."""
    first, _, rest = text.partition("\n")
    match = STATUS_LINE.match(first.strip())
    if not match:
        raise ValueError("The process status could not be read.")
    state = match.group(1)
    return (state if state in {"running", "lost", "stopped"} else int(state)), int(match.group(2)), rest


def spent(text):
    """``(ran, reserved, day, refunded)`` of an ended process's status, else None (running, lost, or
    an older status)."""
    match = STATUS_LINE.match(text.partition("\n")[0].strip())
    if not match or match.group(3) in {None, "-"} or match.group(4) == "-" or match.group(5) == "-":
        return None
    return int(match.group(3)), int(match.group(4)), match.group(5), match.group(6) == "1"


class ProcessTools:
    """The background-process tools of one message, next to its VM tools."""

    def __init__(self, vm_tools):
        self.vm = vm_tools
        # Their time comes off this message's own charge when they end before it does.
        self.started = set()

    def tools(self):
        return [
            ReadOnlyTool("vm_start_process", "Start a command in the background in your workspace, such as a dev server or "
                         "a long test run (at most three at once). Returns its id and first output.",
                         VmStartProcessArgs, self.start, activity=self._activity, reports=True),
            ReadOnlyTool("vm_process_output", "Read the end of a background process's output and whether it still "
                         "runs, optionally after waiting; without id, list the processes.",
                         VmProcessOutputArgs, self.output, activity=self._activity, reports=True),
            ReadOnlyTool("vm_stop_process", "Stop a background process.", VmStopProcessArgs, self.stop,
                         activity=self._activity, reports=True),
        ]

    def _run(self, command, cancellation, timeout, idempotent=False):
        """One server command in the VM, counted as VM time: ``(exit_code, stdout)``."""
        from app.services.agent_vm_tools import _Output
        output = _Output()
        outcome = self.vm._exec(command, cwd=agent_vm.SERVER_HOME, timeout=timeout, on_output=output.add,
                                cancellation=cancellation, agent=False, idempotent=idempotent)
        return outcome.exit_code, bytes(output.streams["stdout"]).decode("utf-8", "replace")

    def _refund(self, process_id, text):
        """A process found ended gives back the VM time it did not run, once: ``refunded`` is
        written first, so a failed write never gives twice."""
        from app.services import agent_vm_time
        found = spent(text)
        if found is None:
            return
        ran, reserved, day, refunded = found
        unused = max(0, reserved - ran)
        if refunded or not unused:
            return
        session = self.vm.session
        mine = process_id in self.started
        if not mine and day != agent_vm_time.day_key():
            return
        try:
            session.backend.write_file(session.name, posixpath.join(process_dir(process_id), "refunded"), b"1",
                                       agent=False)
        except Exception as exc:
            logging.info("Agent VM process refund not marked category=%s", type(exc).__name__)
            return
        if mine:
            self.started.discard(process_id)
            with session._lock:
                session.reserved = max(0.0, session.reserved - unused)
        else:
            agent_vm_time.refund(self.vm.loop.store, self.vm.loop.uid, unused, day)

    def _result(self, process_id, text, extra=None):
        from app.services import agent_secrets
        from app.services.agent_vm_tools import clean, model_text
        state, size, output = parse_status(text)
        raw = output.encode("utf-8")
        uid = self.vm.loop.uid
        result = {"id": process_id, "status": state if state in {"running", "lost", "stopped"} else "exited",
                  "output": model_text(raw, max(size, len(raw)), "output", uid)}
        if isinstance(state, int):
            result["exit_code"] = state
        extra = dict(extra or {})
        notes = [extra.pop("note")] if extra.get("note") else []
        if state == "lost":
            notes.append("The process is gone without an exit code: the VM stopped it. Start it again.")
        elif state != "running" and agent_vm.BACKGROUND_ENDED.search(output[-400:]):
            notes.append(FOREGROUND_NOTE)
        if notes:
            result["note"] = " ".join(notes)
        view = agent_secrets.mask(uid, clean(output), cut_start=size > len(raw), cut_end=state == "running")
        return {**result, **extra, "_view": view[-2000:]}

    def start(self, args, *, cancellation, report=None):
        from app.services.agent_vm_tools import vm_path
        report = report or (lambda fields: None)
        from app.services.agent_vm_tools import VM_DAY_LIMIT
        self.vm._start(cancellation)
        cwd = vm_path(args.cwd, self.vm.session.dir) if args.cwd.strip() else self.vm.session.dir
        session = self.vm.session
        # It holds the VM awake up to its limit, after the message too: that whole limit counts
        # against today's VM time.
        seconds = args.max_seconds
        left = session.left()
        if left is not None:
            if left < 60:
                raise ValueError(VM_DAY_LIMIT)
            seconds = min(seconds, max(60, int(left * DAY_SHARE)))
        from app.services import agent_vm_time
        process_id = new_id()
        directory = process_dir(process_id)
        # A temporary chat's command stays out of other chats' lists.
        temporary = (("temporary", "1"),) if getattr(self.vm.loop, "temporary", False) is True else ()
        # Its chat first: a folder left by a failed later write still goes with the chat.
        for name, content in (("chat", self.vm.loop.chat_id), *temporary, ("run.sh", RUNNER),
                              ("launch.sh", launch_script(args.command, cwd, seconds)),
                              ("command", args.command), ("reserve", f"{seconds} {agent_vm_time.day_key()}")):
            self.vm._provider("write", lambda name=name, content=content: session.backend.write_file(
                session.name, posixpath.join(directory, name), content.encode("utf-8"), agent=False))
        code, text = self._run(start_command(directory, task_name(process_id)), cancellation, 30)
        if code != 0:
            # Left behind, the list showed a process that never ran as "lost".
            try:
                session.backend.delete_path(session.name, directory, agent=False)
            except agent_vm.VMUnavailable:
                logging.warning("Agent VM process folder not removed")
        if code == 4:
            raise ValueError(f"{MAX_RUNNING} background processes are already running. Stop one with "
                             "vm_stop_process first.")
        if code != 0:
            raise ValueError("The background process could not be started.")
        with session._lock:
            session.reserved += seconds
        self.started.add(process_id)
        self._refund(process_id, text)
        note = PROCESSES_NOTE + (" Its limit is shorter than asked: a process takes at most half of what is left "
                                 "of today's VM time." if seconds < args.max_seconds else "")
        result = self._result(process_id, text, {"max_seconds": seconds, "note": note})
        report({"output": result.pop("_view"), "process": process_id})
        return self.vm.session.announce(result)

    def output(self, args, *, cancellation, report=None):
        report = report or (lambda fields: None)
        # Reading it costs at most its wait, within today's VM time: also once that is used up.
        self.vm._start(cancellation, change=False, spends=False)
        if not args.id:
            code, text = self._run(list_command(chat=self.vm.loop.chat_id), cancellation, 30, idempotent=True)
            processes = []
            for line in text.splitlines():
                parts = line.split("\t", 2)
                if len(parts) == 3 and re.fullmatch(ID, parts[0]):
                    state = parts[1]
                    processes.append({"id": parts[0], "status": state if state in {"running", "lost", "stopped"}
                                      else "exited",
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
        code, text = self._run(status_command(process_dir(args.id), wait=wait), cancellation, wait + 30,
                               idempotent=True)
        if code == 5:
            raise ValueError(f"No background process {args.id}. List them with vm_process_output without an id.")
        self._refund(args.id, text)
        result = self._result(args.id, text)
        report({"output": result.pop("_view"), "process": args.id})
        return self.vm.session.announce(result)

    def stop(self, args, *, cancellation, report=None):
        report = report or (lambda fields: None)
        # Stopping gives VM time back: also once today's is used up.
        self.vm._start(cancellation, spends=False)
        code, text = self._run(stop_command(process_dir(args.id), task_name(args.id)), cancellation,
                               STOP_GRACE_SECONDS + 30)
        if code == 5:
            raise ValueError(f"No background process {args.id}. List them with vm_process_output without an id.")
        self._refund(args.id, text)
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
            if result.get("status") in {"running", "lost", "stopped"}:
                fields["process_status"] = result["status"]
        return {**fields, **self.vm._outcome(result)}
