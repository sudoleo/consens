"""agent-run (workspace_vm/workbench/agent-run) in a real bash: a command of
the agent ends with what it left running in the background, its call with
it, and its output is bounded (agent_vm.agent_argv ``output``). It runs as
root on the workbench; here as root too, with the agent's user, its home and
the provider's socket swapped for this machine's (nobody, a temporary
folder), where the machine allows a mount namespace and a cgroup v2. CI
runs as no root and skips; the cases without a cgroup v2 run wherever the
rest does.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

import pytest

from app.services import agent_vm, agent_workspace

SCRIPT = (agent_workspace._FILES / "workbench" / "agent-run").read_text()


def _cgroup2_root():
    try:
        mounts = Path("/proc/self/mounts").read_text().splitlines()
    except OSError:
        return None
    for line in mounts:
        parts = line.split()
        if len(parts) > 2 and parts[2] == "cgroup2":
            return parts[1]
    return None


def _usable():
    if os.name != "posix" or not hasattr(os, "geteuid") or os.geteuid() != 0:
        return "agent-run runs as root"
    for tool in ("unshare", "setpriv", "timeout", "setsid", "pgrep", "stdbuf"):
        if not shutil.which(tool):
            return f"no {tool}"
    try:
        subprocess.run(["id", "nobody"], check=True, capture_output=True)
        subprocess.run(["unshare", "--mount", "--propagation", "private", "--", "true"], check=True,
                       capture_output=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return "no mount namespace or no user nobody"
    return None


SKIP = _usable()
pytestmark = pytest.mark.skipif(SKIP is not None, reason=SKIP or "")


class Runner:
    """agent-run as this machine allows: nobody for the agent's user, the
    socket and the hidden folders in a folder of their own that nobody may
    pass through. ``cgroups=False``: as on a VM without cgroup v2."""

    def __init__(self, base):
        self.base = base
        self.home, self.work, sprite = base / "home", base / "work", base / "sprite"
        for folder in (self.home, self.work, sprite / "checkpoints", sprite / "logs"):
            folder.mkdir(parents=True)
        (sprite / "api.sock").touch()
        for folder in (base, self.home, self.work):
            folder.chmod(0o777 if folder != base else 0o755)
        self.sprite = sprite

    def script(self, cgroups=True):
        """``cgroups``: True, False (none on the VM) or "unjoined" (one that
        refuses the command's process)."""
        text = (SCRIPT.replace("user=agent", "user=nobody").replace(f"home={agent_vm.HOME}", f"home={self.home}")
                .replace('--regid="$user"', "--regid=nogroup")
                .replace("/.sprite/api.sock", str(self.sprite / "api.sock"))
                .replace("/.sprite/checkpoints /.sprite/logs",
                         f"{self.sprite / 'checkpoints'} {self.sprite / 'logs'}"))
        if not cgroups:
            text = text.replace("done < /proc/self/mounts", "done < /dev/null")
        if cgroups == "unjoined":
            text = text.replace('echo "$BASHPID" > "$group/cgroup.procs"', "false")
        path = self.base / f"agent-run-{cgroups}"
        path.write_text(text, newline="\n")
        return str(path)

    def argv(self, command, *, output=1000, seconds=30, cgroups=True):
        options = [] if output is None else ["--output", str(output)]
        return ["/bin/bash", self.script(cgroups), *options, str(seconds), str(self.work), "bash", "-c", command]

    def start(self, command, *, stdin=None, **kwargs):
        return subprocess.Popen(self.argv(command, **kwargs),
                                stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def __call__(self, command, *, stdin=None, **kwargs):
        """``(exit code, stdout, stderr, seconds)`` of a command to its end."""
        began = time.monotonic()
        process = self.start(command, stdin=stdin, **kwargs)
        out, err = process.communicate(stdin, timeout=60)
        return process.returncode, out, err.decode("utf-8", "replace"), time.monotonic() - began


@pytest.fixture
def run():
    base = Path(tempfile.mkdtemp(prefix="agent-run-", dir="/tmp"))
    yield Runner(base)
    # Nothing of nobody's stays behind, whatever a case left.
    subprocess.run(["pkill", "-KILL", "-u", "nobody"], capture_output=True)
    shutil.rmtree(base, ignore_errors=True)


def alive(name):
    found = subprocess.run(["pgrep", "-u", "nobody", "-f", name], capture_output=True, text=True).stdout.split()
    # Zombies are ended: only their parent has not looked yet.
    return [pid for pid in found if Path(f"/proc/{pid}/stat").exists()
            and Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] != "Z"]


def wait_gone(name, seconds=5):
    end = time.monotonic() + seconds
    while time.monotonic() < end and alive(name):
        time.sleep(.1)
    return not alive(name)


needs_cgroup = pytest.mark.skipif(_cgroup2_root() is None, reason="no cgroup v2 here")


@needs_cgroup
def test_what_a_command_leaves_in_the_background_ends_with_it_and_so_does_the_call(run):
    """`cmd &` held the exec's pipe open until the full time limit, which
    then read as timed out; setsid and nohup children outlived the limit,
    Stop and the chat, uncounted. Now the call ends with the command, and so
    does everything it started, whatever session it made for itself."""
    code, out, err, seconds = run("sleep 3001 & setsid nohup sleep 3002 > /dev/null 2>&1 & (sleep 3003 &); "
                                  "echo started; exit 3")
    assert code == 3 and out == b"started\n" and seconds < 10
    assert agent_vm.BACKGROUND_ENDED.search(err) and "3 processes it left" in err
    for name in ("sleep 3001", "sleep 3002", "sleep 3003"):
        assert wait_gone(name), name
    # Its own cgroup is gone again.
    assert not list(Path(_cgroup2_root(), "consens-run").glob("*-*"))


@needs_cgroup
def test_a_command_with_nothing_left_says_nothing_and_keeps_its_streams(run):
    code, out, err, _ = run("echo out; echo err >&2; grep -q consens-run /proc/self/cgroup && echo inside")
    assert (code, out, err) == (0, b"out\ninside\n", "err\n")
    # stdin as given, the agent's user.
    code, out, _, _ = run("cat; id -un", stdin=b"typed\n")
    assert out == b"typed\nnobody\n"


@needs_cgroup
def test_output_passes_its_first_bytes_and_then_only_its_end(run):
    code, out, err, _ = run("seq 1 100000; seq 1 50000 >&2; echo END; echo ENDERR >&2", output=1000)
    assert code == 0
    assert out.startswith(b"1\n2\n3\n") and out.endswith(b"99999\n100000\nEND\n") and len(out) == 1000 + 65536
    assert err.endswith("50000\nENDERR\n") and len(err) == 1000 + 65536
    # Endless output ends at the time limit, never streaming it all.
    code, out, _, seconds = run("yes", output=100_000, seconds=2)
    assert code == 124 and len(out) == 100_000 + 65536 and seconds < 10
    # 0: everything (a background process's log).
    code, out, _, _ = run("seq 1 100000", output=0)
    assert out.endswith(b"100000\n") and len(out) == sum(len(str(n)) + 1 for n in range(1, 100001))


@needs_cgroup
def test_a_stop_reaches_the_command_and_ends_what_it_left(run):
    """TERM (sudo hands it on: vm_stop_process, Stop) goes to the command
    through timeout; what survives it ends with the command."""
    process = run.start("trap 'echo got-term; exit 7' TERM; setsid sleep 3011 & sleep 30 & wait")
    time.sleep(1.5)
    process.terminate()
    out, err = process.communicate(timeout=30)
    assert process.returncode == 7 and out == b"got-term\n"
    assert "1 process it left" in err.decode()
    assert wait_gone("sleep 3011")


@needs_cgroup
def test_a_killed_agent_run_or_sudo_leaves_nothing_running(run):
    """Stop kills the provider's exec session; whether it hits sudo, its
    process group or more, the watcher in the command's cgroup ends it."""
    process = run.start("setsid sleep 3021 & sleep 3022")
    time.sleep(1.5)
    assert alive("sleep 3021") and alive("sleep 3022")
    process.kill()
    process.communicate(timeout=30)
    assert wait_gone("sleep 3021") and wait_gone("sleep 3022")
    # Its parent (sudo on the VM) killed instead.
    parent = subprocess.Popen(["/bin/bash", "-c", '"$@"; echo done', "sudo",
                               *run.argv("setsid sleep 3023 & sleep 3024")],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.5)
    assert alive("sleep 3023") and alive("sleep 3024")
    parent.kill()
    parent.wait()
    assert wait_gone("sleep 3023") and wait_gone("sleep 3024")
    assert not list(Path(_cgroup2_root(), "consens-run").glob("*-*"))


@pytest.mark.parametrize("cgroups", [False, pytest.param("unjoined", marks=needs_cgroup)])
def test_without_a_cgroup_its_process_group_ends_and_the_call_too(run, cgroups):
    """A VM without cgroup v2, or one whose cgroup would not take the
    command: what stayed in the command's process group (``&``) ends with
    it; one that made a session of its own cannot be found, but no longer
    holds the call open past a moment."""
    code, out, err, seconds = run("sleep 3031 & setsid sleep 3032 & echo started", cgroups=cgroups)
    assert code == 0 and out == b"started\n" and seconds < 10
    assert "1 process it left" in err
    assert wait_gone("sleep 3031")


def test_the_servers_own_steps_run_as_before(run):
    """Without --output (files, keys, the tunnel): no supervisor, nothing
    ended, stdin as given."""
    code, out, err, _ = run("cat; id -un", output=None, stdin=b"data")
    assert (code, out, err) == (0, b"datanobody\n", "")
    code, _, err, _ = run("true", output="12x")
    assert code == 125 and "usage" in err
