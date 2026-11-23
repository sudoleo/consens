"""Background processes in the agent's VM: a dev server, a long test run
(vm_start_process, vm_process_output, vm_stop_process), and the app one of
them serves on a card for the user's own browser (vm_show_app, where the
service has a host for apps: agent_apps.py).

A process started with ``&`` in vm_exec stops when the VM pauses, which it
does after a few idle seconds, so between two of the agent's steps. A
background process here runs under a small supervisor script in the VM
(RUNNER) that holds the VM awake through the Sprites Tasks API on
``/.sprite/api.sock`` while the process lives: a hold of HOLD_EXPIRE,
refreshed every HEARTBEAT_SECONDS, released when the process ends. A crashed
supervisor's hold expires by itself.

The supervisor is the server's: it
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

Its whole limit counts as VM time when it starts (agent_vm_time.py), at
most DAY_SHARE of what is left today. Once a look at it
(vm_process_output, vm_stop_process, both also once today's VM time is used
up) finds it ended, the time it did not run is given back, once
(``refunded``): to the message that started it, or to the day it was charged
on.

Everything lives in PROCESSES_DIR/<id>: the command, its combined output
(``output.log``), the supervisor's pid file, its start and, once it ended,
its end and exit code, the VM time it was charged (``reserve``: seconds
and UTC day) and the chat that started it (``chat``):
the process and its folder go with that chat (delete_for_chat). The VM
holds no secret, so neither does any of it.
"""
from __future__ import annotations

import logging
import posixpath
import re
import secrets
import shlex
import time

from pydantic import BaseModel, ConfigDict, Field

from app.services import agent_vm
from app.services.agent_tools import ReadOnlyTool

HOME = agent_vm.HOME
PROCESSES_DIR = agent_vm.SERVER_HOME + "/.consens/processes"
DEFAULT_SECONDS = 1800
MAX_SECONDS = 3600
MAX_RUNNING = 3
# A process reserves at most this share of what is left of today's VM time:
# the commands around it still run, where a dev server at its default limit
# would reserve all 20 minutes of an account without Pro.
DAY_SHARE = 0.5
HEARTBEAT_SECONDS = 60
HOLD_EXPIRE = "5m"
OUTPUT_CHARS = 12_000
MAX_WAIT_SECONDS = 60
STOP_GRACE_SECONDS = 10
ID = r"^[a-f0-9]{8}$"
# Between the command's end and its exit code the supervisor sleeps up to a
# second and may hold the VM a last time (curl, up to 5 s): a look in between
# found neither and said "lost", and the agent ran a finished run again.
# While the folder's own supervisor lives, a look waits
# up to this long for its exit code (state_command).
SETTLE_SECONDS = 8
# The first line of every status: "consens-process <state> <bytes>", then
# the seconds it ran once it ended, the VM time it was charged (seconds,
# day) and whether the rest was given back.
STATUS_LINE = re.compile(r"^consens-process (running|lost|stopped|-?\d+) (\d+)"
                         r"(?: (-|\d+) (-|\d+) (-|\d{4}-\d{2}-\d{2}) ([01]))?$")

# The supervisor of one process (``bash run.sh <dir> <task>``): the agent's
# command (``launch.sh``, under its time limit), a Tasks API hold while it
# runs, its exit code once it ended, then the hold released.
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
# vm_show_app: how often the port is asked, a second apart (a dev server
# takes a few to listen), and the first line of the check's output:
# "consens-app <state> <started> <reserved> <answer> <chat>", each "-" where unknown.
APP_TRIES = 10
# The addresses a server "on localhost" may listen on, one a line: what the
# name means on this computer first, then both loopbacks. On a Sprite the
# name is fdf::1 before 127.0.0.1 (its /etc/hosts, test Sprite 2026-11-23),
# and a server bound to the name (Node's dev servers) listens on fdf::1
# only: curl, which knows "localhost" as the loopbacks by itself, got no
# answer from it on any of the three names. app_tunnel.py asks the same.
LOCAL_HOSTS = ("(getent ahosts localhost 2>/dev/null | cut -d' ' -f1; echo 127.0.0.1; echo ::1) "
               "| awk '!seen[$0]++'")
APP_LINE =re.compile(r"^consens-app (running|lost|stopped|-?\d+) (-|\d+) (-|\d+) (-|\d{3}) (-|[A-Za-z0-9_-]{1,100})$")
APP_NOTE = ("The app shows a card with your answer: Open there shows this app in the user's own browser, on their "
            "phone too, at an address only they can open, live while this process runs{until}. It is no link you "
            "can write and not the shared browser. What you change shows there as your server reloads it; once "
            "the process has ended, the card lets them ask you to start it again.")


class VmStartProcessArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    command: str = Field(min_length=1, max_length=20_000, description="Shell command, run by bash in the background.")
    cwd: str = Field(default="", max_length=1024, description="Working directory, absolute or relative to this "
                     "chat's folder; default that folder.")
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


class VmShowAppArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str = Field(pattern=ID, description="The background process that serves it (vm_start_process).")
    port: int = Field(ge=1024, le=65535, description="The port it listens on, on localhost.")
    path: str = Field(default="/", max_length=500, description="Where it opens: a path of the app, default /.")
    title: str = Field(default="", max_length=60, description="What the card calls it, in a few words.")


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


def state_command():
    """Sets ``code`` for the process folder ``$dir``: its exit code,
    ``running``, ``lost`` or ``stopped``. A command that has ended (its pid
    was written and is gone) without an exit code yet waits up to
    SETTLE_SECONDS for it while the folder's supervisor lives: the pid in
    ``sid`` (start_command), whose command line names this folder's run.sh,
    so a pid the VM gave to another process since (a restart lost the
    supervisor) is not waited for."""
    return ("code=$(cat \"$dir/exit_code\" 2>/dev/null); "
            "if [ -z \"$code\" ]; then pid=$(cat \"$dir/pid\" 2>/dev/null); "
            "if [ -n \"$pid\" ] && kill -0 \"$pid\" 2>/dev/null; then code=running; "
            "else sid=$(cat \"$dir/sid\" 2>/dev/null); "
            f"for _ in $(seq {SETTLE_SECONDS * 5}); do [ -f \"$dir/exit_code\" ] && break; "
            "[ -n \"$pid\" ] && [ -n \"$sid\" ] && tr '\\0' '\\n' < \"/proc/$sid/cmdline\" 2>/dev/null "
            "| grep -qxF \"$dir/run.sh\" || break; sleep 0.2; done; "
            "code=$(cat \"$dir/exit_code\" 2>/dev/null); [ -n \"$code\" ] || code=lost; fi; fi; "
            "[ -f \"$dir/stopped\" ] && [ \"$code\" != running ] && code=stopped; ")


def status_command(directory, chars=OUTPUT_CHARS, wait=0):
    """Prints STATUS_LINE, then the end of the output."""
    d = shlex.quote(directory)
    return (f"{f'sleep {int(wait)}; ' if wait else ''}dir={d}; [ -d \"$dir\" ] || exit 5; "
            + state_command() +
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
    """Refuses (exit 4) at MAX_RUNNING running processes, with a line
    ``temporary <chat>`` for each of a temporary chat (other chats' lists
    leave those out, list_command), else starts the
    supervisor detached from this command (its own session, ``sid``) and
    reports after ``wait``."""
    d = shlex.quote(directory)
    count = (f"running=0; temporary=; for p in {shlex.quote(root)}/*/; do [ -f \"$p/pid\" ] "
             "&& [ ! -f \"$p/exit_code\" ] && kill -0 \"$(cat \"$p/pid\")\" 2>/dev/null || continue; "
             "running=$((running+1)); [ -f \"$p/temporary\" ] && { "
             "c=$(head -c 100 \"$p/chat\" 2>/dev/null | tr -cd 'A-Za-z0-9_-'); temporary=\"$temporary ${c:--}\"; }; "
             "done; "
             f"if [ \"$running\" -ge {MAX_RUNNING} ]; then for c in $temporary; do printf 'temporary %s\\n' \"$c\"; "
             "done; exit 4; fi; ")
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
            "[ -f \"$dir/exit_code\" ] || { : > \"$dir/stopped\"; [ -n \"$pid\" ] && kill -TERM \"$pid\" 2>/dev/null; }; "
            f"for _ in $(seq {STOP_GRACE_SECONDS}); do [ -f \"$dir/exit_code\" ] && break; sleep 1; done; "
            "if [ ! -f \"$dir/exit_code\" ]; then [ -n \"$pid\" ] && kill -KILL \"$pid\" 2>/dev/null; "
            "if [ -n \"$sid\" ]; then sudo -n pkill -KILL -s \"$sid\" 2>/dev/null || pkill -KILL -s \"$sid\" "
            "2>/dev/null; fi; date +%s > \"$dir/ended\"; echo 137 > \"$dir/exit_code\"; "
            "curl -s --max-time 5 --unix-socket /.sprite/api.sock -X DELETE "
            f"http://sprite/v1/tasks/{shlex.quote(task)} >/dev/null 2>&1; fi; " + status_command(directory))


AT_CAP = f"{MAX_RUNNING} background processes are already running. Stop one with vm_stop_process first."
# Some of them run for another, temporary chat: its processes stay out of
# this chat's list (list_command), so the agent saw fewer than MAX_RUNNING
# and could not tell why. They end with that chat.
AT_CAP_TEMPORARY = (f"{MAX_RUNNING} background processes are already running, {{some}} for a temporary chat: "
                    "vm_process_output does not list those here, and they end when the user leaves that chat or "
                    f"at their time limit (at most {MAX_SECONDS // 60} minutes after their start). {{then}}")


def at_cap(text, chat_id):
    """The refusal at MAX_RUNNING, from start_command's ``temporary <chat>``
    lines: how many of the running processes this chat cannot see."""
    hidden = sum(1 for line in text.splitlines()
                 if line.startswith("temporary ") and line[len("temporary "):].strip() != chat_id)
    if not hidden:
        return AT_CAP
    if hidden >= MAX_RUNNING:
        return AT_CAP_TEMPORARY.format(some="all of them", then="Tell the user if this one cannot wait.")
    return AT_CAP_TEMPORARY.format(some=f"{hidden} of them",
                                   then="Stop one of the others with vm_stop_process first.")


def list_command(root=PROCESSES_DIR, chat=""):
    """The processes, one per line: id, state, the command's start. A
    temporary chat's (its file ``temporary``) only for ``chat`` itself."""
    return (f"chat={shlex.quote(chat)}; for d in {shlex.quote(root)}/*/; do [ -d \"$d\" ] || continue; "
            "if [ -f \"$d/temporary\" ] && [ \"$(head -c 100 \"$d/chat\" 2>/dev/null)\" != \"$chat\" ]; then "
            "continue; fi; id=$(basename \"$d\"); dir=${d%/}; " + state_command() +
            "printf '%s\\t%s\\t%s\\n' \"$id\" \"$code\" \"$(head -c 200 \"$d/command\" 2>/dev/null | tr '\\n\\t' '  ')\"; "
            "done; true")


def app_command(directory, port, tries=0):
    """Prints APP_LINE for the process folder: its state, its start and the
    seconds it may run, what answered on ``port`` (the HTTP status, asked up
    to ``tries`` times a second apart) and the chat that started it. The
    port is asked wherever a server "on localhost" may listen (LOCAL_HOSTS)."""
    d = shlex.quote(directory)
    ask = (f"hosts=$({LOCAL_HOSTS}); for _ in $(seq {int(tries)}); do for host in $hosts; do "
           "case \"$host\" in *:*) host=\"[$host]\";; esac; "
           f"status=$(curl -g -s -o /dev/null -m 3 -w '%{{http_code}}' \"http://$host:{int(port)}/\" 2>/dev/null); "
           "case \"$status\" in [1-5][0-9][0-9]) answer=$status; break 2;; esac; done; sleep 1; done; "
           if tries else ":; ")
    return (f"dir={d}; [ -d \"$dir\" ] || exit 5; " + state_command() +
            "started=$(head -c 20 \"$dir/started\" 2>/dev/null | tr -cd '0-9'); "
            "reserved=$(head -c 40 \"$dir/reserve\" 2>/dev/null | cut -d' ' -f1 | tr -cd '0-9'); "
            "chat=$(head -c 100 \"$dir/chat\" 2>/dev/null | tr -cd 'A-Za-z0-9_-'); answer=-; "
            "if [ \"$code\" = running ]; then " + ask + "fi; "
            "printf 'consens-app %s %s %s %s %s\\n' \"$code\" \"${started:--}\" \"${reserved:--}\" \"$answer\" "
            "\"${chat:--}\"")


def parse_app(text):
    """``(state, ends, answer, chat)`` of app_command's output: the state as
    parse_status gives it, when the process ends by itself (seconds since
    the epoch, or None), the HTTP status the port answered with (or None)
    and the chat that started the process ("" when unknown)."""
    match = APP_LINE.match(text.strip().partition("\n")[0].strip())
    if not match:
        raise ValueError("The process status could not be read.")
    state, started, reserved, answer, chat = match.groups()
    ends = int(started) + int(reserved) if started != "-" and reserved != "-" else None
    return (state if state in {"running", "lost", "stopped"} else int(state), ends,
            None if answer == "-" else int(answer), "" if chat == "-" else chat)


def app_state(vm, name, process_id, port):
    """The same look for the user's click on the card
    (routers/agent_workspace.py), as the server's own step: ``(running,
    ends, chat)``; a process that is gone is not running."""
    from app.services.llm.provider_runtime import ProviderCancellation
    out = bytearray()

    def keep(stream, chunk):
        if stream == "stdout" and len(out) < 400:
            out.extend(chunk)
    outcome = vm.exec(name, app_command(process_dir(process_id), port), cwd=agent_vm.SERVER_HOME,
                      timeout=SETTLE_SECONDS + 30, on_output=keep, cancellation=ProviderCancellation(), agent=False)
    if outcome.exit_code != 0:
        return False, None, ""
    try:
        state, ends, _, chat = parse_app(out.decode("utf-8", "replace"))
    except ValueError:
        return False, None, ""
    return state == "running", ends, chat


def task_name(process_id):
    return f"consens-{process_id}"


def claim_command(directory):
    """Makes the mark ``refunded`` only where there is none yet, in one step
    (noclobber, an exclusive create) and prints ``claimed`` when this command
    made it. Two looks that both read the process as not given back (the
    chat's deletion and its stopped message's sweep, each with a status of
    its own) give its time back once: the one that claimed it."""
    return (f"dir={shlex.quote(directory)}; [ -d \"$dir\" ] || exit 5; "
            "if (set -C; printf 1 > \"$dir/refunded\") 2>/dev/null; then echo claimed; fi; true")


def claim_refund(vm, name, directory):
    """Whether this look may give back the process's unused VM time
    (claim_command), as the server's own step: it counts no VM time."""
    from app.services.llm.provider_runtime import ProviderCancellation
    out = bytearray()

    def keep(stream, chunk):
        if stream == "stdout" and len(out) < 64:
            out.extend(chunk)
    outcome = vm.exec(name, claim_command(directory), cwd=agent_vm.SERVER_HOME, timeout=30, on_output=keep,
                      cancellation=ProviderCancellation(), agent=False)
    return outcome.exit_code == 0 and out.decode("utf-8", "replace").strip() == "claimed"


def chat_command(chat_id, root=PROCESSES_DIR):
    """The processes ``chat_id`` started (their ``chat`` file), one per
    line: the id, then ``running`` or ``ended`` (also one the VM lost)."""
    return (f"chat={shlex.quote(chat_id)}; for d in {shlex.quote(root)}/*/; do [ -f \"$d/chat\" ] || continue; "
            "[ \"$(head -c 100 \"$d/chat\")\" = \"$chat\" ] || continue; state=ended; "
            "pid=$(cat \"$d/pid\" 2>/dev/null); if [ ! -f \"$d/exit_code\" ] && [ -n \"$pid\" ] "
            "&& kill -0 \"$pid\" 2>/dev/null; then state=running; fi; "
            "printf '%s %s\\n' \"$(basename \"$d\")\" \"$state\"; done; true")


def delete_for_chat(vm, name, chat_id, *, refund=None):
    """With its chat (agent_vm.delete_chat_vm): the
    background processes it started on the workbench ``name``, a running
    one stopped as vm_stop_process stops it, and their folders with the
    command and its output. ``refund(seconds, day)`` gives back today's VM
    time a process did not use, as a look at it would (ProcessTools._refund).
    Raises
    VMUnavailable when the provider fails or the list did not come back
    whole: the chat's deletion then retries."""
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
            # Claimed first, as _refund does: the deletion and a stopped
            # message's sweep never both give it back (claim_command).
            if not refunded and reserved > ran and day == agent_vm_time.day_key() \
                    and claim_refund(vm, name, directory):
                refund(reserved - ran, day)
        vm.delete_path(name, directory, agent=False)


def parse_status(text):
    """``(state, bytes, output)`` of a status command's output: state is
    "running", "lost" (the VM stopped it, e.g. while paused without a hold),
    "stopped" (vm_stop_process ended it: coreutils timeout then reports 124,
    which read as its time limit) or the exit code."""
    first, _, rest = text.partition("\n")
    match = STATUS_LINE.match(first.strip())
    if not match:
        raise ValueError("The process status could not be read.")
    state = match.group(1)
    return (state if state in {"running", "lost", "stopped"} else int(state)), int(match.group(2)), rest


def spent(text):
    """``(ran, reserved, day, refunded)`` of a status's first line once the
    process ended (seconds it ran, the VM time it was charged and on which
    UTC day, whether the rest was given back), else None: still running,
    lost, or without a readable start or ``reserve``."""
    match = STATUS_LINE.match(text.partition("\n")[0].strip())
    if not match or match.group(3) in {None, "-"} or match.group(4) == "-" or match.group(5) == "-":
        return None
    return int(match.group(3)), int(match.group(4)), match.group(5), match.group(6) == "1"


class ProcessTools:
    """The background-process tools of one message, next to its VM tools."""

    def __init__(self, vm_tools):
        self.vm = vm_tools
        # The processes this message started: their time comes off its own
        # charge (VMSession.reserved) when they end before it does.
        self.started = set()
        # The apps this message put on a card (show): when each one's process ends by itself.
        self.shown = {}

    def tools(self):
        from app.services import agent_apps
        return [
            # Only where the service has a host for apps (agent_apps.host).
            *([ReadOnlyTool("vm_show_app", "Give the user a web app that one of your background processes serves in "
                            "the workspace, such as a dev server: a card with your answer opens it in their own "
                            "browser, on their phone too, live while the process runs. For what needs its server; "
                            "one HTML file that needs nothing from outside itself runs in the chat with vm_share_file.",
                            VmShowAppArgs, self.show, activity=self._activity, reports=True)]
              if agent_apps.host() else []),
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
        """One command of the server in the VM, counted as VM time
        (VMTools._exec); ``(exit_code, stdout)``."""
        from app.services.agent_vm_tools import _Output
        output = _Output()
        outcome = self.vm._exec(command, cwd=agent_vm.SERVER_HOME, timeout=timeout, on_output=output.add,
                                cancellation=cancellation, agent=False, idempotent=idempotent)
        return outcome.exit_code, bytes(output.streams["stdout"]).decode("utf-8", "replace")

    def _refund(self, process_id, text):
        """A process found ended gives back the VM time it did not run, once:
        only the look that claimed ``refunded`` (claim_refund) gives it, so a
        failed claim never gives twice and neither do two looks at once."""
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
            if not claim_refund(session.backend, session.name, process_dir(process_id)):
                return
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
        from app.services.agent_vm_tools import clean, model_text
        state, size, output = parse_status(text)
        raw = output.encode("utf-8")
        result = {"id": process_id, "status": state if state in {"running", "lost", "stopped"} else "exited",
                  "output": model_text(raw, max(size, len(raw)), "output")}
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
        # too: that whole limit counts against today's VM time, and it
        # reserves at most DAY_SHARE of what is left (agent_vm_time.py).
        seconds = args.max_seconds
        left = session.left()
        if left is not None:
            if left < 60:
                raise ValueError(VM_DAY_LIMIT)
            seconds = min(seconds, max(60, int(left * DAY_SHARE)))
        from app.services import agent_vm_time
        process_id = new_id()
        directory = process_dir(process_id)
        # A temporary chat's command stays out of other chats' lists (list_command).
        temporary = (("temporary", "1"),) if getattr(self.vm.loop, "temporary", False) is True else ()
        # Its chat first: a folder left by a later write that failed still
        # goes with the chat (delete_for_chat).
        for name, content in (("chat", self.vm.loop.chat_id), *temporary, ("run.sh", RUNNER),
                              ("launch.sh", launch_script(args.command, cwd, seconds)),
                              ("command", args.command), ("reserve", f"{seconds} {agent_vm_time.day_key()}")):
            self.vm._provider("write", lambda name=name, content=content: session.backend.write_file(
                session.name, posixpath.join(directory, name), content.encode("utf-8"), agent=False))
        code, text = self._run(start_command(directory, task_name(process_id)), cancellation, 30)
        if code != 0:
            # Its files go again: left behind, the list showed a process that
            # never ran as "lost".
            try:
                session.backend.delete_path(session.name, directory, agent=False)
            except agent_vm.VMUnavailable:
                logging.warning("Agent VM process folder not removed")
        if code == 4:
            raise ValueError(at_cap(text, self.vm.loop.chat_id))
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
        # Reading it costs at most its wait, which stays within today's VM
        # time below: also once that is used up (VMTools._start).
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

    def show(self, args, *, cancellation, report=None):
        """vm_show_app: the card only for a process that runs and a port
        that answers, so the user never opens one that shows nothing."""
        from app.services import agent_apps
        self.vm._start(cancellation, change=False)
        code, text = self._run(app_command(process_dir(args.id), args.port, APP_TRIES), cancellation,
                               APP_TRIES * 8 + SETTLE_SECONDS + 30, idempotent=True)
        if code == 5:
            raise ValueError(f"No background process {args.id}. List them with vm_process_output without an id.")
        state, ends, answer, _ = parse_app(text)
        if state != "running":
            raise ValueError(f"Process {args.id} does not run any more: an app is served by a running background "
                             "process. Start it with vm_start_process, then show it.")
        if answer is None:
            raise ValueError(f"Nothing answers on port {args.port} of the workspace. Read the process's output "
                             "(vm_process_output) for the port it listens on and whether it is up, then show it.")
        self.shown[args.id] = ends
        until = f", until {time.strftime('%H:%M', time.gmtime(ends))} UTC" if ends else ""
        return self.vm.session.announce({"shown_as": "app", "id": args.id, "port": args.port,
                                         "path": agent_apps.start_path(args.path),
                                         "note": APP_NOTE.format(until=until)})

    def _activity(self, args, result):
        if isinstance(args, VmShowAppArgs):
            from app.services import agent_apps
            fields = {"process": args.id, "app_port": args.port, "app_path": agent_apps.start_path(args.path)}
            if args.title.strip():
                fields["app_title"] = " ".join(args.title.split())
            if isinstance(result, dict) and result.get("shown_as") == "app":
                fields["app_shown"] = True
                if self.shown.get(args.id):
                    fields["ends_at"] = self.shown[args.id] * 1000
            return {**fields, **self.vm._outcome(result)}
        fields = {"command": args.command} if isinstance(args, VmStartProcessArgs) else {"process": args.id or ""}
        if isinstance(result, dict):
            if "id" in result:
                fields["process"] = result["id"]
            if "exit_code" in result:
                fields["exit_code"] = result["exit_code"]
            if result.get("status") in {"running", "lost", "stopped"}:
                fields["process_status"] = result["status"]
            # When it ends by itself (milliseconds since the epoch): a dev
            # server the user keeps using stops at its limit, and the
            # activity's "Running in the background" said so of it forever.
            if (isinstance(args, VmStartProcessArgs) and result.get("status") == "running"
                    and type(result.get("max_seconds")) is int):
                fields["ends_at"] = int((time.time() + result["max_seconds"]) * 1000)
        return {**fields, **self.vm._outcome(result)}
