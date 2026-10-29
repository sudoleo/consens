"""localhost in the shared browser reaches the agent's workbench
(agent_tunnel.py, workspace_vm/browser/tunnel.py, since 2026-10-29). The
listener of the browser VM and the server's relay run here for real: a
socket pair stands for the provider's exec API, a plain TCP connection for
its proxy, a local HTTP server for the agent's dev server. Nothing calls
Sprites; the Sprites framing has tests of its own at the end.
"""
import http.server
import json
import socket
import threading

import httpx
import pytest

from app.services import agent_tunnel, agent_vm, agent_workspace
from test_agent_vm import FakeSocket, sprites
from test_agent_workspace import load

UID = "tunnel-user"


@pytest.fixture(autouse=True)
def no_tunnels():
    yield
    for uid in list(agent_tunnel._tunnels):
        agent_tunnel.close(uid)
    agent_tunnel._asked.clear()


class SocketStream:
    """The exec stream's and the proxy's interface over a socket."""

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
    """The provider for one tunnel: the browser VM's tunnel.py on a socket
    pair, the workbench's ports as ``targets`` (its port -> a local one)."""

    def __init__(self, targets=None):
        self.targets = targets or {}
        self.started, self.ports, self.closed, self.listeners = [], [], False, []

    def open_stream(self, name, argv, *, cwd):
        self.started.append((name, argv, cwd))
        ours, theirs = socket.socketpair()
        listener = load("tunnel").Tunnel(theirs, theirs.recv, theirs.send)
        self.listeners.append(listener)
        threading.Thread(target=listener.run, daemon=True).start()
        return SocketStream(ours)

    def open_port(self, name, port):
        self.ports.append((name, port))
        if port not in self.targets:
            raise agent_vm.VMUnavailable("proxy: port not reached")
        return SocketStream(socket.create_connection(("127.0.0.1", self.targets[port])))

    def close(self):
        self.closed = True


def workbench_server():
    """The agent's dev server: answers every path with what it was asked."""
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = f"hello from the workbench: {self.path}".encode()
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
    import time
    for _ in range(100):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=1).close()
        except OSError:
            return
        time.sleep(0.05)
    raise AssertionError(f"port {port} still listens")


def get(port, path="/"):
    """What Chrome on the browser VM gets for http://localhost:<port><path>."""
    with socket.create_connection(("127.0.0.1", port), timeout=10) as client:
        client.sendall(f"GET {path} HTTP/1.0\r\nHost: localhost:{port}\r\n\r\n".encode())
        answer = b""
        while chunk := client.recv(65536):
            answer += chunk
    return answer.decode()


def test_localhost_in_the_browser_reaches_the_workbenchs_port():
    server = workbench_server()
    port = free_port()
    provider = Provider({port: server.server_port})
    try:
        assert agent_tunnel.open_port(UID, port, backend_factory=lambda: provider)
        answer = get(port, "/game?move=4")
        assert answer.startswith("HTTP/1.0 200") and answer.endswith("hello from the workbench: /game?move=4")
        # Connections at once, each its own way to the workbench.
        answers = []
        threads = [threading.Thread(target=lambda: answers.append(get(port, "/tile.png"))) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(10)
        assert len(answers) == 4 and all(a.endswith(": /tile.png") for a in answers)
        # The listener runs on the browser VM as the provider's user, with
        # the provider's exec API; the workbench is reached through the proxy.
        [(name, argv, cwd)] = provider.started
        assert name == agent_vm.browser_name(UID) and cwd == agent_vm.SERVER_HOME
        assert argv[-1] == f"exec python3 {agent_workspace.BROWSER_TUNNEL}"
        assert set(provider.ports) == {(agent_vm.workspace_name(UID), port)} and len(provider.ports) == 5
        # One tunnel per account: a second port uses it, the same port is free.
        assert agent_tunnel.open_port(UID, port, backend_factory=lambda: Provider())
        assert len(provider.started) == 1 and agent_tunnel.asked(UID) == {port}
    finally:
        server.shutdown()


def test_nothing_on_the_workbenchs_port_says_so_in_the_browser():
    port = free_port()
    assert agent_tunnel.open_port(UID, port, backend_factory=lambda: Provider())
    answer = get(port)
    assert answer.startswith("HTTP/1.1 502 Bad Gateway")
    assert f"Nothing answers on port {port} of the agent's workspace" in answer


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
        assert not agent_tunnel.open_port(UID, port, backend_factory=lambda: provider)
    assert agent_tunnel.asked(UID) == set()
    # tunnel.py refuses them by itself as well.
    listener = load("tunnel")
    assert listener.RESERVED == set(agent_tunnel.RESERVED_PORTS) and listener.LOWEST_PORT == agent_tunnel.LOWEST_PORT


def test_an_idle_tunnel_ends_and_the_view_starts_it_again(monkeypatch):
    server = workbench_server()
    port = free_port()
    monkeypatch.setattr(agent_tunnel, "POLL_SECONDS", 0.05)
    try:
        now = [0.0]
        provider = Provider({port: server.server_port})
        tunnel = agent_tunnel.Tunnel(UID, provider, clock=lambda: now[0])
        tunnel.start()
        assert tunnel.listen(port) and get(port).endswith(": /")
        # A live-reload socket that stays open without a word keeps nothing awake.
        silent = socket.create_connection(("127.0.0.1", port), timeout=5)
        for _ in range(100):
            if tunnel.conns:
                break
            threading.Event().wait(0.05)
        assert tunnel.conns
        now[0] = agent_tunnel.IDLE_SECONDS + 1
        assert tunnel.ended.wait(5) and provider.closed
        silent.close()
        wait_closed(port)
        # The account's tunnel: ended (idle, the VM's sleep), then resumed
        # for the ports asked before, as the live view and the next browser
        # call do.
        assert agent_tunnel.open_port(UID, port, backend_factory=lambda: Provider({port: server.server_port}))
        agent_tunnel._tunnels[UID].close()
        wait_closed(port)
        assert agent_tunnel.resume("nobody") is None
        again = Provider({port: server.server_port})
        agent_tunnel.resume(UID, backend_factory=lambda: again).join(10)
        assert again.started and get(port, "/again").endswith(": /again")
        assert agent_tunnel.resume(UID, backend_factory=lambda: again) is None
    finally:
        server.shutdown()


def test_a_tunnel_that_cannot_start_is_said_and_tried_again():
    class Down(Provider):
        def open_stream(self, name, argv, *, cwd):
            raise agent_vm.VMUnavailable("exec: HTTP 502")
    with pytest.raises(agent_vm.VMUnavailable):
        agent_tunnel.open_port(UID, free_port(), backend_factory=Down)
    port = free_port()
    assert agent_tunnel.open_port(UID, port, backend_factory=Provider)


def test_the_browser_reads_no_page_of_its_own_computer():
    """browser.py: a page on the browser VM itself, also one a link or a
    redirect led to, comes back as its address alone; localhost on a port
    the tunnel holds is the workbench's and reads as any page."""
    helper = load("browser")
    assert helper.own_computer("http://127.0.0.1:9222/json/list")
    assert helper.own_computer("http://localhost:3000/", set())
    assert not helper.own_computer("http://localhost:3000/", {3000})
    assert helper.own_computer("http://[::1]:3001/", {3000})
    assert helper.own_computer("http://10.0.0.8/") and helper.own_computer("http://x.internal/")
    assert not helper.own_computer("https://example.com/") and not helper.own_computer("about:blank")

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


# --- Sprites: the proxy and the long command ------------------------------------------

def test_sprites_proxy_names_the_port_then_carries_bytes():
    """Sprites' own SDKs (proxy.go): a JSON message names the port on the
    VM's localhost, the answer says connected, then binary frames."""
    opened = []
    ws = FakeSocket([json.dumps({"status": "connected", "target": "localhost:3000"}), b"HTTP/1.1 200 OK\r\n"])
    backend = sprites(lambda request: httpx.Response(200), connect=lambda url, token: opened.append((url, token)) or ws)
    stream = backend.open_port("consens-abc", 3000)
    assert opened == [("wss://api.sprites.dev/v1/sprites/consens-abc/proxy", "secret-token")]
    assert json.loads(ws.sent[0]) == {"host": "localhost", "port": 3000}
    stream.send(b"GET / HTTP/1.1\r\n\r\n")
    assert ws.sent[1] == b"GET / HTTP/1.1\r\n\r\n"
    assert stream.recv(1) == b"HTTP/1.1 200 OK\r\n" and stream.recv(1) is None
    # Nothing listening: the provider does not say connected.
    refused = FakeSocket([json.dumps({"status": "error", "message": "connection refused"})])
    backend = sprites(lambda request: httpx.Response(200), connect=lambda url, token: refused)
    with pytest.raises(agent_vm.VMUnavailable, match="port not reached"):
        backend.open_port("consens-abc", 3001)
    assert refused.closed


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
