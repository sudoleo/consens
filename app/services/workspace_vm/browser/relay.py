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

While the view is open it keeps Chrome running (since 2026-10-29): a Chrome
that ended, by a crash or because the user closed its window, starts again
within KEEP_SECONDS with its tabs (display.sh --keep). On 2026-10-28 Chrome
died in Max's open view and the screen stayed black until the agent's next
call.

Standard library only, so it runs before setup.sh installed anything.
"""
import json
import os
import socket
import subprocess
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
MARKER = os.path.expanduser("~/.consens/browser/setup-done-1")
# The VNC server's Unix socket (display.sh): on no network at all.
VNC = os.path.expanduser("~/.consens/browser/vnc.sock")
CHUNK = 65536
KEEP_SECONDS = 10


def state(name):
    sys.stderr.write(json.dumps({"state": name}) + "\n")
    sys.stderr.flush()


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
    done.wait()
    try:
        vnc.close()
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
