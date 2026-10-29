"""localhost in the shared browser reaches the agent's workbench
(agent_tunnel.py, workspace_vm/tunnel.py, since 2026-10-29). Both sides of
tunnel.py (listen for the browser VM, connect for the workbench) and the
server's relay run here for real: socket pairs stand for the provider's
exec API, a local HTTP server for the agent's dev server. Nothing calls
Sprites; the Sprites framing has tests of its own at the end.
"""
import hashlib
import http.server
import json
import os
import socket
import struct
import threading
import time

import httpx
import pytest

from app.services import agent_tunnel, agent_vm, agent_workspace
from test_agent_runs import store  # noqa: F401  (fixture)
from test_agent_vm import FakeSocket, sprites
from test_agent_workspace import load

UID = "tunnel-user"
BIG = 5 * 1024 * 1024


@pytest.fixture(autouse=True)
def no_tunnels():
    yield
    for uid in list(agent_tunnel._tunnels):
        agent_tunnel.close(uid)
    agent_tunnel._asked.clear()


class SocketStream:
    """The exec stream's interface over a socket."""

    def __init__(self, sock):
        self.sock = sock
        self.lock = threading.Lock()

    def send(self, data):
        with self.lock:
            self.sock.sendall(data)

    def recv(self, timeout):
        self.sock.settimeout(timeout)
        try:
            data = self.sock.recv(65536)
        except TimeoutError:
            return b""
        except OSError:
            return None
        return data or None

    def close(self):
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.sock.close()


class Provider:
    """The provider for one tunnel: tunnel.py listen (the browser VM) and
    connect (the workbench) on socket pairs. On one machine both cannot use
    the same port, so the workbench's ports are ``targets`` (its port -> a
    local one, none: nothing listens); ``listening`` is its answer to Q."""

    def __init__(self, targets=None, listening=()):
        self.targets = targets or {}
        self.listening = listening
        self.started, self.connects, self.closed, self.sides = [], [], False, {}

    def open_stream(self, name, argv, *, cwd):
        self.started.append((name, argv, cwd))
        ours, theirs = socket.socketpair()
        # As on the VMs: tunnel.py never blocks on the server.
        theirs.setblocking(False)
        mode = "connect" if "connect" in argv else "listen"

        def addresses(port):
            self.connects.append(port)
            target = self.targets.get(port)
            return [(socket.AF_INET, ("127.0.0.1", target))] if target else []
        side = load("tunnel").Tunnel(theirs, theirs.recv, theirs.send, mode=mode, addresses=addresses,
                                     ports=lambda: list(self.listening))
        self.sides[mode] = side
        threading.Thread(target=side.run, daemon=True).start()
        return SocketStream(ours)

    def close(self):
        self.closed = True


def workbench_server():
    """The agent's dev server: GET answers with the path (/big with BIG
    bytes; /nolength without a length, ended by closing), POST with the
    size and hash of what came."""
    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.0"

        def do_GET(self):
            if self.path == "/nolength":
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"the end comes with the close")
                return
            body = (b"x" * BIG) if self.path == "/big" else f"hello from the workbench: {self.path}".encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            data = self.rfile.read(int(self.headers["Content-Length"]))
            body = f"{len(data)} {hashlib.sha256(data).hexdigest()}".encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def wait_closed(port):
    """Until the ended listener gave the port back (its thread ends after the stream)."""
    for _ in range(100):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=1).close()
        except OSError:
            return
        time.sleep(0.05)
    raise AssertionError(f"port {port} still listens")


def request(port, raw, timeout=10):
    """What Chrome on the browser VM gets for ``raw`` sent to localhost:<port>."""
    with socket.create_connection(("127.0.0.1", port), timeout=timeout) as client:
        client.sendall(raw)
        answer = b""
        while chunk := client.recv(65536):
            answer += chunk
    return answer


def get(port, path="/"):
    return request(port, f"GET {path} HTTP/1.0\r\nHost: localhost:{port}\r\n\r\n".encode()).decode()


def wait_for(condition, seconds=5):
    deadline = time.time() + seconds
    while not condition():
        if time.time() > deadline:
            return False
        time.sleep(0.02)
    return True


# --- The way through --------------------------------------------------------------------

def test_localhost_in_the_browser_reaches_the_workbenchs_port(store):
    server = workbench_server()
    port = free_port()
    provider = Provider({port: server.server_port})
    try:
        assert agent_tunnel.open_port(UID, port, backend_factory=lambda: provider, db=store.db)
        answer = get(port, "/game?move=4")
        assert answer.startswith("HTTP/1.0 200") and answer.endswith("hello from the workbench: /game?move=4")
        # Connections at once, each its own on the workbench, all through one stream each side.
        answers = []
        threads = [threading.Thread(target=lambda: answers.append(get(port, "/tile.png"))) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(10)
        assert len(answers) == 4 and all(a.endswith(": /tile.png") for a in answers)
        assert provider.connects == [port] * 5
        # listen on the browser VM as the provider's user; connect on the
        # workbench as the agent's user, through agent-run, from where that user reads it.
        [(browser, listen, home), (bench, connect, root)] = sorted(provider.started, key=lambda item: "connect" in
                                                                   item[1])
        assert browser == agent_vm.browser_name(UID) and home == agent_vm.SERVER_HOME
        assert listen[-1] == f"exec python3 {agent_workspace.BROWSER_TUNNEL} listen"
        assert bench == agent_vm.workspace_name(UID) and root == "/"
        assert connect[:4] == ["sudo", "-n", "/bin/bash", agent_vm.AGENT_RUN]
        assert connect[-3:] == ["python3", agent_workspace.WORKBENCH_TUNNEL, "connect"]
        # One tunnel per account: the same port again needs nothing new.
        assert agent_tunnel.open_port(UID, port, backend_factory=lambda: Provider())
        assert len(provider.started) == 2 and agent_tunnel.asked(UID) == {port}
        # The port is kept on the account's record, for a restart of the server.
        assert agent_workspace.record(store.db, UID)["tunnel_ports"] == [port]
    finally:
        server.shutdown()


def test_an_answer_that_ends_with_the_close_ends_in_the_browser():
    """The reason the workbench's side is tunnel.py, not the provider's proxy
    API (live probe 2026-10-29): the proxy never passed on that a server
    closed a connection, so an answer without a length never ended."""
    server = workbench_server()
    port = free_port()
    try:
        assert agent_tunnel.open_port(UID, port, backend_factory=lambda: Provider({port: server.server_port}))
        started = time.time()
        answer = request(port, b"GET /nolength HTTP/1.0\r\n\r\n", timeout=5)
        assert answer.endswith(b"the end comes with the close") and time.time() - started < 3
    finally:
        server.shutdown()


def test_a_big_answer_and_a_big_upload_arrive_whole():
    """The credit (WINDOW) both ways: more than it at once goes through in pieces, byte for byte."""
    server = workbench_server()
    port = free_port()
    try:
        assert agent_tunnel.open_port(UID, port, backend_factory=lambda: Provider({port: server.server_port}))
        answer = request(port, f"GET /big HTTP/1.0\r\nHost: localhost:{port}\r\n\r\n".encode())
        assert answer.endswith(b"\r\n\r\n" + b"x" * BIG)
        data = os.urandom(3 * 1024 * 1024 + 17)
        answer = request(port, f"POST /up HTTP/1.0\r\nHost: localhost\r\nContent-Length: {len(data)}\r\n\r\n".encode()
                         + data).decode()
        assert answer.endswith(f"{len(data)} {hashlib.sha256(data).hexdigest()}")
    finally:
        server.shutdown()


def test_a_page_that_stops_reading_stops_only_its_own_connection():
    """A paused video: its answer waits within its credit, the other
    connections go on, and it arrives whole once the page reads again."""
    server = workbench_server()
    port = free_port()
    try:
        assert agent_tunnel.open_port(UID, port, backend_factory=lambda: Provider({port: server.server_port}))
        stuck = socket.create_connection(("127.0.0.1", port), timeout=20)
        stuck.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
        stuck.sendall(f"GET /big HTTP/1.0\r\nHost: localhost:{port}\r\n\r\n".encode())
        time.sleep(1)
        started = time.time()
        assert get(port, "/meanwhile").endswith(": /meanwhile") and time.time() - started < 5
        answer = b""
        while chunk := stuck.recv(65536):
            answer += chunk
        stuck.close()
        assert answer.endswith(b"x" * BIG) and len(answer) > BIG
    finally:
        server.shutdown()


def test_nothing_on_the_workbenchs_port_says_so_in_the_browser():
    port = free_port()
    assert agent_tunnel.open_port(UID, port, backend_factory=lambda: Provider())
    answer = get(port)
    assert answer.startswith("HTTP/1.1 502 Bad Gateway")
    assert f"Nothing answers on port {port} of the agent's workspace" in answer


def test_connect_opens_ipv4_and_else_ipv6_loopback():
    """A dev server on "localhost" may listen on ::1 alone (the provider's
    proxy reached none such, live probe 2026-10-29)."""
    tunnel = load("tunnel")
    assert [address for _, address in tunnel.local_addresses(5173)] == [("127.0.0.1", 5173), ("::1", 5173)]
    try:
        server = socket.socket(socket.AF_INET6)
        server.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        server.bind(("::1", 0))
    except OSError:
        pytest.skip("no IPv6 loopback here")
    server.listen(1)
    port = server.getsockname()[1]
    ours, theirs = socket.socketpair()
    try:
        side = tunnel.Tunnel(theirs, theirs.recv, theirs.send, mode="connect")
        side.open(7, port)
        assert 7 in side.conns and side.conns[7].sock.family == socket.AF_INET6
    finally:
        server.close()
        ours.close()
        theirs.close()


# --- What the tunnel never takes ------------------------------------------------------

def test_the_tunnel_never_takes_a_port_of_the_browser_vm_itself():
    """Chrome's debugging port, the ports below 1024, and any port the VM
    already uses: localhost there stays the VM's own, which the agent never
    opens (agent_browser.check_url) nor reads (browser.py own_computer)."""
    provider = Provider()
    assert not agent_tunnel.open_port(UID, 9222, backend_factory=lambda: provider)
    assert not agent_tunnel.open_port(UID, 80, backend_factory=lambda: provider)
    assert provider.started == []
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen(1)
        port = taken.getsockname()[1]
        # Refused is "taken", not a failure of the way.
        assert not agent_tunnel.open_port(UID, port, backend_factory=lambda: provider)
    assert agent_tunnel.asked(UID) == set()
    tunnel = load("tunnel")
    assert tunnel.RESERVED == set(agent_tunnel.RESERVED_PORTS) and tunnel.LOWEST_PORT == agent_tunnel.LOWEST_PORT
    assert (tunnel.WINDOW, tunnel.MAX_FRAME, tunnel.MAX_CONNECTIONS) == (
        agent_tunnel.WINDOW, agent_tunnel.MAX_FRAME, agent_tunnel.MAX_CONNECTIONS)


@pytest.mark.skipif(not socket.has_ipv6, reason="no IPv6 here")
def test_a_port_in_use_on_ipv6_loopback_is_taken_too():
    """Chrome's localhost reaches ::1 as well: a service of the VM there would answer."""
    try:
        taken = socket.socket(socket.AF_INET6)
        taken.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        taken.bind(("::1", 0))
    except OSError:
        pytest.skip("no IPv6 loopback here")
    taken.listen(1)
    port = taken.getsockname()[1]
    ours, theirs = socket.socketpair()
    try:
        listener = load("tunnel").Tunnel(theirs, theirs.recv, theirs.send)
        assert listener.listen(port) is False and not listener.listening
    finally:
        taken.close()
        ours.close()
        theirs.close()


class Recording:
    """An exec stream that hands out ``frames`` and keeps what is sent."""

    def __init__(self, frames=()):
        self.frames, self.sent = list(frames), []

    def send(self, data):
        self.sent.append(data)

    def recv(self, timeout):
        return self.frames.pop(0) if self.frames else None

    def close(self):
        pass


def test_the_browser_vm_and_the_workbench_get_only_their_part():
    """The browser VM, least trusted: a connection to a port the tunnel does
    not hold is refused, a frame longer than MAX_FRAME ends it all. The
    workbench's side only answers: its O or L go nowhere, its frames of an
    unknown connection neither; nothing it sends opens anything."""
    tunnel = agent_tunnel.Tunnel(UID, Provider())
    tunnel.stream, tunnel.bench = Recording(), Recording()
    tunnel.ports.add(4000)
    tunnel._from_browser(b"O", 7, struct.pack(">H", 4444))
    assert tunnel.stream.sent == [agent_tunnel.frame(b"C", 7)] and tunnel.bench.sent == []
    tunnel._from_browser(b"O", 8, struct.pack(">H", 4000))
    assert tunnel.bench.sent == [agent_tunnel.frame(b"O", 8, struct.pack(">H", 4000))] and tunnel.open == {8: 4000}
    tunnel.stream.sent.clear()
    for kind in (b"O", b"L"):
        tunnel._from_bench(kind, 9, struct.pack(">H", 4000))
    tunnel._from_bench(b"D", 9, b"not a connection of the browser's")
    assert tunnel.stream.sent == [] and tunnel.open == {8: 4000}
    # In order, both ways, until a close ends it.
    tunnel._from_bench(b"D", 8, b"answer")
    tunnel._from_browser(b"A", 8, struct.pack(">I", 6))
    tunnel._from_bench(b"C", 8, b"")
    tunnel._from_browser(b"D", 8, b"too late")
    assert tunnel.stream.sent == [agent_tunnel.frame(b"D", 8, b"answer"), agent_tunnel.frame(b"C", 8)]
    assert tunnel.bench.sent[-1] == agent_tunnel.frame(b"A", 8, struct.pack(">I", 6)) and not tunnel.open
    # F: the 502 page, then the close.
    tunnel._from_browser(b"O", 10, struct.pack(">H", 4000))
    tunnel._from_bench(b"F", 10, b"")
    assert tunnel.stream.sent[-2][:9] == struct.pack(">cII", b"D", 10, len(agent_tunnel._nothing_there(4000)))
    assert tunnel.stream.sent[-1] == agent_tunnel.frame(b"C", 10)
    huge = struct.pack(">cII", b"D", 1, agent_tunnel.MAX_FRAME + 1)
    other = agent_tunnel.frame(b"H", 0, b"listen")
    tunnel = agent_tunnel.Tunnel(UID, Provider())
    tunnel.stream, tunnel.bench = Recording([huge, other]), Recording()
    tunnel._read(tunnel.stream, tunnel._from_browser)
    assert tunnel.ended.is_set() and tunnel.stream.frames == [other]


def test_a_side_past_its_credit_loses_the_connection():
    """tunnel.py: more D than WINDOW before the A frames is the other side's fault."""
    tunnel = load("tunnel")
    ours, theirs = socket.socketpair()
    a, b = socket.socketpair()
    try:
        side = tunnel.Tunnel(theirs, theirs.recv, theirs.send, mode="connect")
        side._adopt(3, a, 5000)
        # The server takes nothing (its socket full).
        side._write = lambda conn: None
        for _ in range(tunnel.WINDOW // tunnel.CHUNK + 4):
            side.handle(b"D", 3, b"x" * tunnel.CHUNK)
        assert 3 not in side.conns
    finally:
        for sock in (ours, theirs, a, b):
            sock.close()


def test_at_most_max_connections_at_once(monkeypatch):
    server = workbench_server()
    port = free_port()
    monkeypatch.setattr(agent_tunnel, "MAX_CONNECTIONS", 1)
    try:
        assert agent_tunnel.open_port(UID, port, backend_factory=lambda: Provider({port: server.server_port}))
        first = socket.create_connection(("127.0.0.1", port), timeout=5)
        assert wait_for(lambda: len(agent_tunnel._tunnels[UID].open) == 1)
        # One more is closed at once, without an answer.
        assert request(port, b"GET / HTTP/1.0\r\n\r\n") == b""
        first.close()
        assert wait_for(lambda: not agent_tunnel._tunnels[UID].open)
        assert get(port).endswith(": /")
    finally:
        server.shutdown()


# --- Which ports, and for how long --------------------------------------------------

def proc_net_tcp(*listening):
    """/proc/net/tcp with ``(port, uid)`` listening, and one connection that does not."""
    lines = ["  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode"]
    for index, (port, uid) in enumerate(listening):
        lines.append(f"   {index}: 00000000:{port:04X} 00000000:0000 0A 00000000:00000000 00:00000000 00000000  "
                     f"{uid}        0 1{index} 1 0000000000000000 100 0 0 10 0")
    lines.append("   9: 0100007F:0BB8 0100007F:D431 01 00000000:00000000 00:00000000 00000000  1500        0 99 1")
    return "\n".join(lines) + "\n"


def test_the_ports_of_the_agents_servers_are_found_on_the_workbench():
    """connect answers Q from /proc/net/tcp and tcp6: listening (0A), its own
    uid, a port the tunnel takes (the parser was checked on a real sprite,
    2026-10-29)."""
    tunnel = load("tunnel")
    text = proc_net_tcp((5173, 1500), (8000, 1500), (9222, 1500), (22, 1500), (7000, 0))
    assert tunnel.listening_ports(text, 1500) == [5173, 8000]
    six = ("   0: 00000000000000000000000001000000:1F90 00000000000000000000000000000000:0000 0A "
           "00000000:00000000 00:00000000 00000000  1500        0 5 1\n")
    assert tunnel.listening_ports(six, 1500) == [8080]
    port = free_port()
    assert agent_tunnel.open_port(UID, port, backend_factory=lambda: Provider(listening=(5173, 8000)))
    assert agent_tunnel._tunnels[UID].listening() == [5173, 8000]


def test_opening_one_port_brings_the_other_servers_along(store):
    """A page on 5173 that calls its API on 8000: the open of 5173 finds
    8000 listening and holds it too, kept on the record."""
    server = workbench_server()
    page, api = free_port(), free_port()
    provider = Provider({page: server.server_port, api: server.server_port}, listening=(api,))
    try:
        assert agent_tunnel.open_port(UID, page, backend_factory=lambda: provider, db=store.db)
        agent_tunnel.resume(UID, backend_factory=lambda: provider, db=store.db, find=True).join(10)
        assert agent_tunnel.asked(UID) == {page, api}
        assert get(api, "/api/score").endswith(": /api/score")
        assert agent_workspace.record(store.db, UID)["tunnel_ports"] == [page, api]
    finally:
        server.shutdown()


def test_a_port_without_an_answer_is_a_failure_not_taken(monkeypatch):
    """Both sides started, but no answer for the port (the tunnel died, the
    time ran out): the way is down, the agent hears to try again, never to
    move its server elsewhere. A side that never starts says so too."""
    class Mute(Provider):
        def open_stream(self, name, argv, *, cwd):
            ours, theirs = socket.socketpair()
            self.started.append(theirs)
            mode = b"connect" if "connect" in argv else b"listen"
            theirs.sendall(agent_tunnel.frame(b"H", 0, mode))
            return SocketStream(ours)
    monkeypatch.setattr(agent_tunnel, "LISTEN_SECONDS", 0.3)
    with pytest.raises(agent_vm.VMUnavailable, match="no answer"):
        agent_tunnel.open_port(UID, free_port(), backend_factory=Mute)
    agent_tunnel.close(UID)

    class Missing(Provider):
        def open_stream(self, name, argv, *, cwd):
            ours, theirs = socket.socketpair()
            self.started.append(theirs)
            return SocketStream(ours)
    with pytest.raises(agent_vm.VMUnavailable, match="did not start"):
        agent_tunnel.open_port(UID, free_port(), backend_factory=Missing)


def test_an_idle_tunnel_ends_and_comes_back(monkeypatch, store):
    server = workbench_server()
    port = free_port()
    monkeypatch.setattr(agent_tunnel, "POLL_SECONDS", 0.05)
    try:
        now = [0.0]
        provider = Provider({port: server.server_port})
        tunnel = agent_tunnel.Tunnel(UID, provider, clock=lambda: now[0])
        tunnel.start()
        assert port in tunnel.listen([port]) and get(port).endswith(": /")
        # A live-reload socket that stays open without a word keeps nothing awake.
        silent = socket.create_connection(("127.0.0.1", port), timeout=5)
        assert wait_for(lambda: tunnel.open)
        now[0] = agent_tunnel.IDLE_SECONDS + 1
        assert tunnel.ended.wait(5) and provider.closed
        silent.close()
        wait_closed(port)
        # The account's tunnel: ended (idle, the VM's sleep), then resumed
        # for the ports asked before, as the live view, a takeover and the
        # next browser call do; after a restart of the server from the record.
        assert agent_tunnel.open_port(UID, port, backend_factory=lambda: Provider({port: server.server_port}),
                                      db=store.db)
        agent_tunnel._tunnels[UID].close()
        wait_closed(port)
        agent_tunnel._asked.clear()
        assert agent_tunnel.resume(UID) is None
        agent_tunnel.seed(UID, agent_workspace.listed(agent_workspace.record(store.db, UID), "tunnel_ports", int))
        again = Provider({port: server.server_port})
        agent_tunnel.resume(UID, backend_factory=lambda: again).join(10)
        assert again.started and get(port, "/again").endswith(": /again")
        assert agent_tunnel.resume(UID, backend_factory=lambda: again) is None
        # The user working in the app keeps it from ending as idle.
        tunnel = agent_tunnel._tunnels[UID]
        tunnel.used = -1.0
        agent_tunnel.touch(UID)
        assert tunnel.used > 0
    finally:
        server.shutdown()


def test_a_tunnel_that_cannot_start_is_said_and_tried_again():
    class Down(Provider):
        def open_stream(self, name, argv, *, cwd):
            raise agent_vm.VMUnavailable("exec: HTTP 502")
    with pytest.raises(agent_vm.VMUnavailable):
        agent_tunnel.open_port(UID, free_port(), backend_factory=Down)
    assert agent_tunnel.open_port(UID, free_port(), backend_factory=Provider)

    # Only the browser's side fails: the workbench's, already open, is closed with it.
    class HalfDown(Provider):
        def open_stream(self, name, argv, *, cwd):
            if "connect" not in argv:
                time.sleep(0.2)
                raise agent_vm.VMUnavailable("exec: HTTP 502")
            self.bench = super().open_stream(name, argv, cwd=cwd)
            return self.bench
    half = HalfDown()
    agent_tunnel.close(UID)
    with pytest.raises(agent_vm.VMUnavailable):
        agent_tunnel.open_port(UID, free_port(), backend_factory=lambda: half)
    with pytest.raises(OSError):
        half.bench.sock.send(b"x")


def test_a_new_tunnel_ends_the_old_one_of_its_mode(tmp_path):
    """A deploy: the old server's tunnel held the ports, the new one ends it
    (its path and mode arguments of their own, never inside a shell's
    command line), never the other mode's."""
    tunnel = load("tunnel")
    path = os.path.abspath(tunnel.__file__).encode()
    for pid, argv in {"101": [b"python3", path, b"listen"], "102": [b"timeout", b"5", b"bash", b"-c",
                                                                      b"exec python3 " + path + b" listen"],
                      "103": [b"python3", path, b"listen"], "104": [b"python3", b"other.py"],
                      "105": [b"python3", path, b"connect"],
                      # Its own starter under agent-run: the same arguments after its own.
                      "106": [b"timeout", b"--kill-after=5", b"60", b"python3", path, b"listen"],
                      "107": [b"/usr/bin/python3.12", path, b"listen"]}.items():
        (tmp_path / pid).mkdir()
        (tmp_path / pid / "cmdline").write_bytes(b"\0".join(argv) + b"\0")
    (tmp_path / "self").mkdir()
    killed = []

    def kill(pid, sig):
        killed.append(pid)
        for item in (tmp_path / str(pid)).iterdir():
            item.unlink()
        (tmp_path / str(pid)).rmdir()
    assert sorted(tunnel.end_others("listen", proc=str(tmp_path), me=103, kill=kill,
                                    wait=lambda seconds: None)) == [101, 107]
    assert sorted(killed) == [101, 107]


def test_the_browser_reads_no_page_of_its_own_computer():
    """browser.py: a page on the browser VM itself, also one a link, a
    redirect, back or the user led to, comes back as its address alone;
    localhost on a port the tunnel holds is the workbench's and reads as
    any page."""
    helper = load("browser")
    assert helper.own_computer("http://127.0.0.1:9222/json/list")
    assert helper.own_computer("http://localhost:3000/", set())
    assert not helper.own_computer("http://localhost:3000/", {3000})
    assert helper.own_computer("http://[::1]:3001/", {3000})
    assert helper.own_computer("http://10.0.0.8/") and helper.own_computer("http://x.internal/")
    for own in ("file:///home/sprite/.consens/browser/profile/Default/", "chrome://settings/passwords",
                "view-source:https://example.com/", "chrome-extension://abc/page.html"):
        assert helper.own_computer(own), own
    for fine in ("https://example.com/", "about:blank", "chrome://newtab/", "chrome-error://chromewebdata/", ""):
        assert not helper.own_computer(fine), fine

    class Page:
        url = "http://localhost:9222/json/list"

        def title(self):
            raise AssertionError("never its title")

        def evaluate(self, *args):
            raise AssertionError("never its text")
    helper.LOCAL_PORTS.clear()
    assert helper.read_text(Page()) == f"URL: {Page.url}\n{helper.OWN_COMPUTER}"
    assert helper.page_text(Page(), 0) == helper.read_text(Page())
    assert helper.with_picture(Page(), {"screenshot_after": True}, {"text": "x"}) == {"text": "x"}


# --- Sprites: the long command ------------------------------------------------------

def test_sprites_stream_keeps_stdin_open_and_hands_out_stdout():
    ws = FakeSocket([json.dumps({"type": "session_info", "session_id": "9"}), b"\x01abc", b"\x02warning\n",
                     TimeoutError(), b"\x01def", json.dumps({"type": "exit", "exit_code": 0})])
    opened = []
    backend = sprites(lambda request: httpx.Response(200), connect=lambda url, token: opened.append(url) or ws)
    stream = backend.open_stream("consens-browser-abc", ["python3", "tunnel.py"], cwd="/home/sprite")
    assert httpx.URL(opened[0]).params.get("stdin") == "true"
    stream.send(b"L")
    assert ws.sent == [b"\x00L"]
    assert [stream.recv(1) for _ in range(6)] == [b"", b"abc", b"", b"", b"def", None]
    stream.close()
    assert ws.sent[-1] == b"\x04" and ws.closed


def test_closing_a_stream_never_waits_for_a_send_that_hangs():
    """A stalled connection: its socket goes under the send instead."""
    class Hung(FakeSocket):
        def __init__(self):
            super().__init__([])
            self.socket = self
            self.shut = []

        def shutdown(self, how):
            self.shut.append(how)
    ws = Hung()
    backend = sprites(lambda request: httpx.Response(200), connect=lambda url, token: ws)
    stream = backend.open_stream("consens-browser-abc", ["python3", "tunnel.py"], cwd="/home/sprite")
    stream._send_lock.acquire()
    stream.close()
    assert ws.shut == [socket.SHUT_RDWR] and ws.closed and b"\x04" not in ws.sent
