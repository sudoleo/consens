"""consens.io workbench: the agent pauses while the user has the browser
(agent_workspace.set_control starts this as root at every takeover).

Every command of the agent runs as its own user (agent-run), in its cgroup
where the VM has a cgroup v2 freezer. While CONTROL says the user has the
browser, this freezes that cgroup, or, without one, stops every process of
the agent's user (SIGSTOP), also ones that appear meanwhile. Nothing of the
agent's runs then, whatever it started and however. Once the user hands
back, or the takeover expires because the view stopped refreshing it, it
continues them all. One at a time (LOCK): a second start ends at once.

The server holds the agent's new calls meanwhile; this is for what already
ran. CONTROL lies in the provider's home, which the agent cannot open.
Standard library only.
"""
import json
import os
import signal
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CONTROL = os.path.join(HERE, "control.json")
LOCK = os.path.join(HERE, "pause.lock")
GROUP = "/sys/fs/cgroup/consens-agent"
AGENT_UID = 1500
PROC = "/proc"
# What starts in the moment of the takeover is stopped this soon (a /proc
# listing costs next to nothing).
SCAN_SECONDS = 0.2
# Linux's numbers where the platform has none (the tests run elsewhere too).
STOP = getattr(signal, "SIGSTOP", 19)
CONT = getattr(signal, "SIGCONT", 18)


def user_control():
    """Whether the user has the browser now."""
    try:
        with open(CONTROL, encoding="utf-8") as handle:
            control = json.load(handle)
    except (OSError, ValueError):
        return False
    return control.get("holder") == "user" and float(control.get("until") or 0) > time.time()


def agent_pids(proc=PROC, uid=AGENT_UID):
    """The processes of the agent's user (real uid), never this one."""
    own = os.getpid()
    pids = []
    for entry in os.listdir(proc):
        if not entry.isdigit() or int(entry) == own:
            continue
        try:
            with open(os.path.join(proc, entry, "status"), encoding="utf-8") as handle:
                for line in handle:
                    if line.startswith("Uid:"):
                        if int(line.split()[1]) == uid:
                            pids.append(int(entry))
                        break
        except (OSError, ValueError, IndexError):
            continue
    return sorted(pids)


def send(sig, pids, kill=os.kill):
    for pid in pids:
        try:
            kill(pid, sig)
        except OSError:
            pass


def freezer(group=GROUP):
    """The cgroup's freeze file, or None where the VM has none."""
    path = os.path.join(group, "cgroup.freeze")
    return path if os.path.exists(path) else None


def set_frozen(path, frozen):
    try:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("1" if frozen else "0")
        return True
    except OSError:
        return False


def pause(*, held=user_control, find=agent_pids, kill=os.kill, sleep=time.sleep, group=GROUP):
    """Freezes the agent while ``held()``, then lets it go on: its cgroup
    where it has one (a process can leave it only through root's files;
    measured on a Sprite 2026-10-27), else each of its user's processes."""
    path = freezer(group)
    frozen = bool(path) and set_frozen(path, True)
    try:
        while held():
            if not frozen:
                send(STOP, find(), kill)
            sleep(SCAN_SECONDS)
    finally:
        if frozen:
            set_frozen(path, False)
        else:
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
