"""consens.io workspace: the way from the user's own browser to a server the
agent runs here (agent_app_tunnel.py, docs/agent-mode.md "App im eigenen
Browser").

The server runs this over the provider's exec API, with the provider's token
on api.sprites.dev only, and carries many connections through it at once:
frames on stdin open a TCP connection to a port on this computer's loopback
and carry its bytes, frames on stdout carry the answers. One frame is its
kind (1 byte), its connection (4 bytes), its length (4 bytes) and that many
bytes.

It serves a port only while a background process of the agent runs
(agent_vm_processes.py): that process holds the computer awake and its time
is counted, and this command, which holds it awake too, would otherwise keep
it running uncounted. With none left it says so (BYE) and ends, as it does
after QUIET_SECONDS without a connection or when stdin ends.

Standard library only, like every tool of the workspace.
"""
import os
import queue
import socket
import struct
import sys
import threading
import time

OPEN, DATA, END, CLOSE, PING = 1, 2, 3, 4, 5
HELLO, OPENED, REFUSED, BYE, PONG = 16, 17, 18, 19, 20
HEAD = struct.Struct(">BII")
CHUNK = 64 * 1024
MAX_FRAME = 1024 * 1024
CONNECT_SECONDS = 5
# Frames waiting for one connection's server before stdin waits with them.
BACKLOG = 64
CHECK_SECONDS = 5
QUIET_SECONDS = 120
LOWEST_PORT = 1024
LOOPBACK = (("127.0.0.1", socket.AF_INET), ("::1", socket.AF_INET6))
PROCESSES = os.path.expanduser("~/.consens/processes")
PROC = "/proc"

_out = threading.Lock()
_streams = {}
_streams_lock = threading.Lock()
_last_stream = [time.monotonic()]


def send(kind, stream=0, payload=b""):
    """One whole frame on stdout, whatever thread writes it. A stdout that is
    gone (the server closed the command) ends everything."""
    try:
        with _out:
            sys.stdout.buffer.write(HEAD.pack(kind, stream, len(payload)) + payload)
            sys.stdout.buffer.flush()
    except (OSError, ValueError):
        os._exit(0)


def read_exact(count):
    data = b""
    while len(data) < count:
        chunk = sys.stdin.buffer.read(count - len(data))
        if not chunk:
            return None
        data += chunk
    return data


def alive(pid):
    # /proc is this computer's; where there is none (a test on another
    # system) the pid file alone counts.
    return os.path.isdir(os.path.join(PROC, pid)) if os.path.isdir(PROC) else True


def process_runs(root):
    """Whether a background process of the agent runs: a folder with the pid
    of a living process and no exit code yet (agent_vm_processes.py)."""
    try:
        names = os.listdir(root)
    except OSError:
        return False
    for name in names:
        folder = os.path.join(root, name)
        if os.path.exists(os.path.join(folder, "exit_code")):
            continue
        try:
            with open(os.path.join(folder, "pid"), encoding="ascii") as handle:
                pid = handle.read(20).strip()
        except (OSError, ValueError):
            continue
        if pid.isdigit() and alive(pid):
            return True
    return False


def local_addresses(port):
    """Where a server "on localhost" may listen: what the name means on this
    computer first (here fdf::1 before 127.0.0.1, and a server bound to the
    name listens on that one only), then both loopbacks."""
    found = []
    try:
        for family, _, _, _, address in socket.getaddrinfo("localhost", port, type=socket.SOCK_STREAM):
            found.append((family, address))
    except OSError:
        pass
    found += [(family, (host, port)) for host, family in LOOPBACK]
    seen, addresses = set(), []
    for family, address in found:
        if address[0] not in seen:
            seen.add(address[0])
            addresses.append((family, address))
    return addresses


def connect(port):
    """The server on ``port``, on the first of its addresses that answers."""
    for family, address in local_addresses(port):
        sock = socket.socket(family, socket.SOCK_STREAM)
        sock.settimeout(CONNECT_SECONDS)
        try:
            sock.connect(address)
        except OSError:
            sock.close()
            continue
        sock.settimeout(None)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        return sock
    return None


def drop(stream):
    with _streams_lock:
        entry = _streams.pop(stream, None)
        _last_stream[0] = time.monotonic()
    if entry is not None:
        try:
            entry[0].close()
        except OSError:
            pass
        try:
            # Wakes the sending side, which waits for frames (to_server).
            entry[1].put_nowait(None)
        except queue.Full:
            pass
    return entry is not None


def to_server(stream, sock, outbox):
    """What the server's frames carry goes to the app, in order; None ends
    the sending side, the app may still answer."""
    while True:
        payload = outbox.get()
        try:
            if payload is None:
                sock.shutdown(socket.SHUT_WR)
                return
            sock.sendall(payload)
        except OSError:
            if drop(stream):
                send(CLOSE, stream)
            return


def serve(stream, port, root):
    if port < LOWEST_PORT or not process_runs(root):
        send(REFUSED, stream, b"idle" if port >= LOWEST_PORT else b"port")
        return
    sock = connect(port)
    if sock is None:
        send(REFUSED, stream, b"refused")
        return
    outbox = queue.Queue(BACKLOG)
    with _streams_lock:
        _streams[stream] = (sock, outbox)
        _last_stream[0] = time.monotonic()
    send(OPENED, stream)
    threading.Thread(target=to_server, args=(stream, sock, outbox), daemon=True).start()
    while True:
        try:
            data = sock.recv(CHUNK)
        except OSError:
            if drop(stream):
                send(CLOSE, stream)
            return
        if not data:
            break
        send(DATA, stream, data)
    send(END, stream)
    drop(stream)


def watch(root):
    """Ends the command once nothing counts its time any more, or nobody uses it."""
    missing = 0
    while True:
        time.sleep(CHECK_SECONDS)
        missing = 0 if process_runs(root) else missing + 1
        if missing >= 2:
            send(BYE, 0, b"idle")
            os._exit(0)
        with _streams_lock:
            quiet = not _streams and time.monotonic() - _last_stream[0] > QUIET_SECONDS
        if quiet:
            send(BYE, 0, b"quiet")
            os._exit(0)


def main(argv):
    root = argv[argv.index("--processes") + 1] if "--processes" in argv else PROCESSES
    send(HELLO, 0, b"1")
    threading.Thread(target=watch, args=(root,), daemon=True).start()
    while True:
        head = read_exact(HEAD.size)
        if head is None:
            return 0
        kind, stream, length = HEAD.unpack(head)
        if length > MAX_FRAME:
            return 2
        payload = read_exact(length) if length else b""
        if payload is None:
            return 0
        if kind == OPEN and len(payload) == 2:
            port = struct.unpack(">H", payload)[0]
            threading.Thread(target=serve, args=(stream, port, root), daemon=True).start()
        elif kind == PING:
            send(PONG, 0, payload)
        elif kind in (DATA, END, CLOSE):
            with _streams_lock:
                entry = _streams.get(stream)
            if entry is None:
                continue
            if kind == CLOSE:
                drop(stream)
            else:
                # A full backlog waits here: the app reads slower than the
                # server sends, and stdin waits with it.
                entry[1].put(payload if kind == DATA else None)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
