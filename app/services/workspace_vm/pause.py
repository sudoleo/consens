"""consens.io workspace: the agent pauses while the user has the browser
(agent_workspace.py; consens.io's server starts this at every takeover).

Every command of the agent carries AGENT_MARK in its environment
(agent_vm.wrapped_command), and so does all it starts: its background
processes, a script left running. While CONTROL says the user has the
browser, this freezes every process that carries the mark (SIGSTOP), also
ones that appear meanwhile, so nothing of the agent's reads what the user
types there, a password say. Once the user hands back, or the takeover
expires because the view stopped refreshing it, it continues them all
(SIGCONT). One at a time (LOCK): a second start ends at once.

The server holds the agent's new commands meanwhile; this is for what
already ran. A process that drops the mark on purpose (env -u, a cleared
environment) is not frozen: the reviewers see such a command in the work log.

Standard library only, like gateway.py.
"""
import json
import os
import signal
import sys
import time

HOME = os.path.expanduser("~")
CONTROL = os.path.join(HOME, ".consens/workspace/control.json")
LOCK = os.path.join(HOME, ".consens/workspace/pause.lock")
PROC = "/proc"
MARK = b"CONSENS_AGENT=1"
# What starts in the moment of the takeover is frozen this soon (a /proc
# listing costs next to nothing).
SCAN_SECONDS = 0.2
# Linux's numbers where the platform has none (the tests run elsewhere too).
STOP = getattr(signal, "SIGSTOP", 19)
CONT = getattr(signal, "SIGCONT", 18)


def user_control():
    """Whether the user has the browser now (as browser.py reads it)."""
    try:
        with open(CONTROL, encoding="utf-8") as handle:
            control = json.load(handle)
    except (OSError, ValueError):
        return False
    return control.get("holder") == "user" and float(control.get("until") or 0) > time.time()


def marked(proc=PROC):
    """The processes whose environment carries MARK, never this one."""
    own = os.getpid()
    pids = []
    for entry in os.listdir(proc):
        if not entry.isdigit() or int(entry) == own:
            continue
        try:
            with open(os.path.join(proc, entry, "environ"), "rb") as handle:
                if MARK in handle.read().split(b"\0"):
                    pids.append(int(entry))
        except OSError:
            continue
    return sorted(pids)


def send(sig, pids, kill=os.kill):
    for pid in pids:
        try:
            kill(pid, sig)
        except OSError:
            pass


def pause(*, held=user_control, find=marked, kill=os.kill, sleep=time.sleep):
    """Freezes the agent's processes while ``held()``, then continues them."""
    try:
        while held():
            send(STOP, find(), kill)
            sleep(SCAN_SECONDS)
    finally:
        send(CONT, find(), kill)


def main():
    import fcntl
    lock = open(LOCK, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return 0
    pause()
    return 0


if __name__ == "__main__":
    sys.exit(main())
