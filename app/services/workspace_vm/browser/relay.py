"""consens.io browser VM: the live view's way to the VNC server
(routers/agent_workspace.py; since 2026-10-27 instead of a gateway service
behind the VM's own address).

The server runs this over the provider's exec API, with the provider's token
on api.sprites.dev only, and carries the user's WebSocket through it: the
view's bytes arrive on stdin, the VNC server's leave on stdout. Before that,
stderr says how far it is, one JSON line each: {"state": "setup"} while
setup.sh installs the browser (once), {"state": "starting"} while display.sh
starts it, {"state": "ready"} once the VNC server answers, or
{"state": "error"}. It ends with stdin (the view closed) or the VNC server.

While the view is open it keeps Chrome running (since 2026-10-28): a Chrome
that ended, by a crash or because the user closed its window, starts again
within KEEP_SECONDS with its tabs (display.sh --keep). On 2026-10-28 Chrome
died in Max's open view and the screen stayed black until the agent's next
call.

And it tells the server's safety rules (workspace_guard.py, since
2026-10-30) what happens in the browser while the user can steer it, on
stderr like the states: {"visit": host} whenever a tab shows a page of
another host (Chrome's target list every LOOK_SECONDS; a page Chrome would
not load counts too, its tab names the address it was asked for), {"net":
{"rx", "tx", "boot"}} with the VM's network counters every NET_SECONDS (each
line is a count in Firestore, the counters' rules are per day), and
{"policy": fingerprint} of Chrome's policy once Chrome runs. Only the host,
never the address's path or the page.

Standard library only, so it runs before setup.sh installed anything.
"""
import hashlib
import json
import os
import socket
import subprocess
import sys
import threading
import urllib.request
from urllib.parse import urlsplit

HERE = os.path.dirname(os.path.abspath(__file__))
MARKER = os.path.expanduser("~/.consens/browser/setup-done-1")
# The VNC server's Unix socket (display.sh): on no network at all.
VNC = os.path.expanduser("~/.consens/browser/vnc.sock")
CHUNK = 65536
KEEP_SECONDS = 10
# The safety rules' look at the browser (watch).
TARGETS = "http://127.0.0.1:9222/json/list"
LOOK_SECONDS = 1
NET_SECONDS = 60
POLICY = "/etc/opt/chrome/policies/managed/consens.json"
_said = threading.Lock()


def say(line):
    """One JSON line on stderr, whole even with several threads."""
    with _said:
        sys.stderr.write(json.dumps(line) + "\n")
        sys.stderr.flush()


def state(name):
    say({"state": name})


def page_host(url):
    """The host of an http(s) page, else None (Chrome's own pages, a new tab)."""
    try:
        parts = urlsplit(url or "")
        host = (parts.hostname or "").lower().rstrip(".")
    except ValueError:
        return None
    return host[:253] if parts.scheme in {"http", "https"} and host else None


def net_counters():
    """The bytes the VM received and sent on its network, summed over its
    interfaces but loopback, and the boot they count from (they start
    again with a new boot), or None."""
    try:
        with open("/proc/net/dev", encoding="utf-8") as handle:
            lines = handle.read().splitlines()[2:]
        with open("/proc/sys/kernel/random/boot_id", encoding="utf-8") as handle:
            boot = handle.read().strip()[:36]
    except OSError:
        return None
    rx = tx = 0
    for line in lines:
        name, _, numbers = line.partition(":")
        fields = numbers.split()
        if name.strip() == "lo" or len(fields) < 9:
            continue
        rx += int(fields[0])
        tx += int(fields[8])
    return {"rx": rx, "tx": tx, "boot": boot}


def policy_print():
    """The fingerprint of Chrome's policy on this VM ("" without one)."""
    try:
        with open(POLICY, "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()[:16]
    except OSError:
        return ""


def watch(done, look=LOOK_SECONDS, net=NET_SECONDS):
    """Until the view closes: a visit for each tab that shows another host
    than at the last look, the network counters now and then."""
    say({"policy": policy_print()})
    shown = {}
    since_net = net
    while not done.wait(look):
        # Any failure costs this look, never the watch: a Chrome that
        # restarts mid-answer (an IncompleteRead) must not end it for the
        # rest of the view.
        try:
            since_net += look
            if since_net >= net:
                since_net = 0
                counters = net_counters()
                if counters:
                    say({"net": counters})
            with urllib.request.urlopen(TARGETS, timeout=3) as response:
                targets = json.loads(response.read().decode("utf-8"))
            now = {}
            for target in targets if isinstance(targets, list) else ():
                if isinstance(target, dict) and target.get("type") == "page":
                    host = page_host(target.get("url"))
                    if host:
                        now[str(target.get("id"))] = host
            for tab, host in now.items():
                if shown.get(tab) != host:
                    say({"visit": host})
            shown = now
        except Exception:
            continue


def run(script, *args):
    return subprocess.run(["bash", os.path.join(HERE, script), *args], stdin=subprocess.DEVNULL,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def keep_chrome(done):
    """Starts Chrome again whenever it is gone, until the view closes."""
    while not done.wait(KEEP_SECONDS):
        try:
            run("display.sh", "--keep")
        except OSError:
            pass


def connect_vnc():
    vnc = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    vnc.settimeout(10)
    vnc.connect(VNC)
    return vnc


def pipe(read, write, done):
    try:
        while True:
            data = read()
            if not data:
                break
            write(data)
    except OSError:
        pass
    done.set()


def main():
    if not os.path.exists(MARKER):
        state("setup")
    if not run("setup.sh"):
        state("error")
        return 1
    state("starting")
    if not run("display.sh"):
        state("error")
        return 1
    try:
        vnc = connect_vnc()
    except OSError:
        state("error")
        return 1
    vnc.settimeout(None)
    state("ready")
    stdin, stdout = sys.stdin.buffer.raw, sys.stdout.buffer.raw
    done = threading.Event()

    def to_vm(data):
        vnc.sendall(data)

    def to_view(data):
        view = memoryview(data)
        while view:
            view = view[stdout.write(view):]
    threading.Thread(target=pipe, args=(lambda: stdin.read(CHUNK), to_vm, done), daemon=True).start()
    threading.Thread(target=pipe, args=(lambda: vnc.recv(CHUNK), to_view, done), daemon=True).start()
    threading.Thread(target=keep_chrome, args=(done,), daemon=True).start()
    threading.Thread(target=watch, args=(done,), daemon=True).start()
    done.wait()
    counters = net_counters()
    if counters:
        say({"net": counters})
    try:
        vnc.close()
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
