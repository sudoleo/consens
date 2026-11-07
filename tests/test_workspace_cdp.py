"""Chrome's protocol on a socket only the provider's user opens
(workspace_vm/browser/cdp.py): the browser runs on the
workbench next to the agent's user, so Chrome gets no debugging port. cdp.py
holds Chrome's pipe and gives every connection a browser session of its own;
its ids and sessions never meet another connection's, and its end detaches
what it set up (docs/agent-mode.md "Ein Rechner"). A stand-in Chrome speaks
the pipe here (fd 3 in, fd 4 out).

And browser.py reads a localhost page only where the agent's user listens
(agent_ports): the kernel's socket table, not what a page says.
"""
import base64
import json
import os
import socket
import stat
import struct
import subprocess
import sys
import textwrap
import threading
import time

import pytest

from test_agent_workspace import load

POSIX = pytest.mark.skipif(sys.platform == "win32", reason="Chrome's pipe and the socket are the VM's (Linux)")


class Pipe:
    """Chrome's side of the hub in memory: what the hub wrote, NUL by NUL."""

    def __init__(self):
        self.read_fd, self.write_fd = os.pipe()
        self.buffer = b""

    def messages(self):
        os.set_blocking(self.read_fd, False)
        try:
            while True:
                chunk = os.read(self.read_fd, 65536)
                if not chunk:
                    break
                self.buffer += chunk
        except BlockingIOError:
            pass
        found = []
        while b"\0" in self.buffer:
            raw, self.buffer = self.buffer.split(b"\0", 1)
            found.append(json.loads(raw))
        return found


class Client:
    """A connection as the hub sees it: what it was sent."""

    def __init__(self, root):
        self.root, self.sessions, self.sent = root, set(), []

    def send(self, message, opcode=1):
        self.sent.append(message)


def test_each_connection_has_its_own_session_and_ids_and_never_sees_anothers():
    cdp = load("cdp")
    pipe = Pipe()
    hub = cdp.Hub(pipe.write_fd)
    first, second = Client("S1"), Client("S2")
    hub.own("S1", first)
    hub.own("S2", second)
    # Both say id 1; each goes out with an id of the hub's and its own session.
    hub.forward(first, {"id": 1, "method": "Target.setAutoAttach", "params": {"autoAttach": True}})
    hub.forward(second, {"id": 1, "method": "Browser.getVersion"})
    out = pipe.messages()
    assert [message["sessionId"] for message in out] == ["S1", "S2"]
    assert out[0]["id"] != out[1]["id"] and out[0]["params"] == {"autoAttach": True}
    # Chrome's answers go back with their own ids, the root session left out.
    hub.dispatch(json.dumps({"id": out[1]["id"], "sessionId": "S2", "result": {"product": "Chrome"}}).encode())
    hub.dispatch(json.dumps({"id": out[0]["id"], "sessionId": "S1", "result": {}}).encode())
    assert second.sent == [{"id": 1, "result": {"product": "Chrome"}}]
    assert first.sent == [{"id": 1, "result": {}}]
    # A page the first one's auto-attach brought is its own, and only its own.
    hub.dispatch(json.dumps({"method": "Target.attachedToTarget", "sessionId": "S1",
                             "params": {"sessionId": "P1", "targetInfo": {"type": "page"}}}).encode())
    hub.dispatch(json.dumps({"method": "Page.loadEventFired", "sessionId": "P1", "params": {}}).encode())
    assert [message["method"] for message in first.sent[1:]] == ["Target.attachedToTarget", "Page.loadEventFired"]
    assert "sessionId" not in first.sent[1] and first.sent[2]["sessionId"] == "P1"
    assert len(second.sent) == 1
    # The second may not speak in the first one's page.
    hub.forward(second, {"id": 7, "method": "Runtime.evaluate", "sessionId": "P1"})
    assert second.sent[-1] == {"id": 7, "error": {"code": -32001, "message": "Session not found"}}
    assert pipe.messages() == []
    # Events of the hub's own session and of nobody's session go nowhere.
    hub.dispatch(json.dumps({"method": "Target.targetCreated", "params": {}}).encode())
    hub.dispatch(json.dumps({"method": "Inspector.detached", "sessionId": "nobody"}).encode())
    hub.dispatch(b"not json")
    assert len(first.sent) == 3 and len(second.sent) == 2
    # A page that went is no longer the first one's.
    hub.dispatch(json.dumps({"method": "Target.detachedFromTarget", "sessionId": "S1",
                             "params": {"sessionId": "P1"}}).encode())
    hub.forward(first, {"id": 2, "method": "Runtime.evaluate", "sessionId": "P1"})
    assert first.sent[-1]["error"]["message"] == "Session not found"


def test_a_connection_that_ends_detaches_its_session_and_forgets_its_pages():
    """A closed port connection ended what Playwright set up (its download
    folder, the auto-attach that holds new tabs, dialogs it closes); over
    the pipe the hub ends the connection's browser session the same way."""
    cdp = load("cdp")
    pipe = Pipe()
    hub = cdp.Hub(pipe.write_fd)
    client = Client("S1")
    hub.own("S1", client)
    hub.own("P1", client)
    hub.forward(client, {"id": 3, "method": "Page.navigate", "sessionId": "P1", "params": {"url": "https://x.example"}})
    sent = pipe.messages()
    hub.leave(client)
    [detach] = pipe.messages()
    assert detach["method"] == "Target.detachFromTarget" and detach["params"] == {"sessionId": "S1"}
    assert "sessionId" not in detach and client.sessions == set()
    # An answer for the gone connection goes nowhere.
    hub.dispatch(json.dumps({"id": sent[0]["id"], "sessionId": "P1", "result": {}}).encode())
    assert client.sent == []


def frames_from(sock, count):
    """``count`` unmasked frames the hub sent on ``sock``: (opcode, payload)."""
    def exact(size):
        data = b""
        while len(data) < size:
            chunk = sock.recv(size - len(data))
            assert chunk, "the hub closed the connection"
            data += chunk
        return data
    found = []
    for _ in range(count):
        first, second = exact(2)
        size = second & 0x7F
        if size == 126:
            size = struct.unpack("!H", exact(2))[0]
        elif size == 127:
            size = struct.unpack("!Q", exact(8))[0]
        found.append((first & 0x0F, exact(size)))
    return found


def test_a_client_that_stops_reading_never_holds_what_chrome_sends_the_others(monkeypatch):
    """send ran sendall on the one thread that reads
    Chrome's pipe, and after the upgrade without a time limit. A client that
    no longer read held that thread: no connection heard from Chrome, and
    Chrome's pipe filled. Each connection has its queue and its writer;
    one that lets more than QUEUE_BYTES wait is dropped as one that left."""
    cdp = load("cdp")
    stuck, its_peer = socket.socketpair()
    reading, peer = socket.socketpair()
    try:
        slow, fast = cdp.Connection(stuck), cdp.Connection(reading)
        chunk = b"x" * (1 << 20)

        def flood():
            for _ in range(24):
                slow.send(chunk, opcode=2)
            fast.send({"id": 1, "result": {}})
        reader = threading.Thread(target=flood, daemon=True)
        reader.start()
        reader.join(5)
        assert not reader.is_alive(), "a client that does not read held the thread that reads Chrome"
        # The other connection hears from Chrome all the same, in order.
        peer.settimeout(5)
        fast.send({"method": "Page.loadEventFired", "params": {}})
        assert frames_from(peer, 2) == [(1, b'{"id":1,"result":{}}'),
                                        (1, b'{"method":"Page.loadEventFired","params":{}}')]
        # The stuck one keeps its messages in its queue, at most QUEUE_BYTES of them.
        assert not slow.closed
        monkeypatch.setattr(cdp, "QUEUE_BYTES", 4 << 20)
        for _ in range(8):
            slow.send(chunk, opcode=2)
        assert slow.closed
        # Its writer ends with it, and what comes after goes nowhere.
        slow._writer.join(5)
        assert not slow._writer.is_alive()
        slow.send(chunk, opcode=2)
        assert slow._queued == 0
        # One message larger than QUEUE_BYTES still goes to a client that reads.
        fast.send(b"y" * (5 << 20), opcode=2)
        assert frames_from(peer, 1) == [(2, b"y" * (5 << 20))] and not fast.closed
    finally:
        for sock in (stuck, its_peer, reading, peer):
            sock.close()


FAKE_CHROME = textwrap.dedent('''
    import json, os, sys
    log = open(os.environ["FAKE_CHROME_LOG"], "a")
    buffer, sessions = b"", 0

    def send(message):
        data = json.dumps(message).encode() + b"\\0"
        while data:
            data = data[os.write(4, data):]

    while True:
        chunk = os.read(3, 65536)
        if not chunk:
            break
        buffer += chunk
        while b"\\0" in buffer:
            raw, buffer = buffer.split(b"\\0", 1)
            message = json.loads(raw)
            log.write(json.dumps(message) + "\\n")
            log.flush()
            method, answer = message["method"], {"id": message["id"]}
            if "sessionId" in message:
                answer["sessionId"] = message["sessionId"]
            if method == "Target.attachToBrowserTarget":
                sessions += 1
                answer["result"] = {"sessionId": f"S{sessions}"}
            elif method == "Target.getTargets":
                answer["result"] = {"targetInfos": [
                    {"targetId": "T1", "type": "page", "title": "Example", "url": "https://example.com/"},
                    {"targetId": "W1", "type": "service_worker", "title": "", "url": "https://example.com/sw.js"}]}
            elif method == "Browser.getVersion":
                answer["result"] = {"product": "Chrome/1.0", "protocolVersion": "1.3"}
            else:
                answer["result"] = {"echo": method}
            send(answer)
            if method == "Target.setAutoAttach":
                send({"method": "Target.attachedToTarget", "sessionId": message["sessionId"],
                      "params": {"sessionId": "P-" + message["sessionId"], "targetInfo": {"type": "page"}}})
''')


class WebSocket:
    """A small client of the hub's socket, as Playwright's driver speaks to it."""

    def __init__(self, path):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(10)
        self.sock.connect(path)
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall(f"GET /devtools/browser HTTP/1.1\r\nHost: localhost\r\nUpgrade: websocket\r\n"
                          f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
                          .encode())
        head = b""
        while b"\r\n\r\n" not in head:
            head += self.sock.recv(1)
        import hashlib
        accept = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest())
        assert b" 101 " in head and b"Sec-WebSocket-Accept: " + accept in head

    def send(self, message):
        data, mask = json.dumps(message).encode(), os.urandom(4)
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(data))
        size = struct.pack("!B", 0x80 | len(data)) if len(data) < 126 else struct.pack("!BH", 0x80 | 126, len(data))
        self.sock.sendall(bytes([0x81]) + size + mask + masked)

    def receive(self):
        def exact(size):
            data = b""
            while len(data) < size:
                chunk = self.sock.recv(size - len(data))
                assert chunk, "the hub closed the connection"
                data += chunk
            return data
        _, second = exact(2)
        size = second & 0x7F
        if size == 126:
            size = struct.unpack("!H", exact(2))[0]
        elif size == 127:
            size = struct.unpack("!Q", exact(8))[0]
        return json.loads(exact(size))

    def close(self):
        self.sock.close()


def http_get(path, sock_path):
    connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    connection.settimeout(10)
    connection.connect(sock_path)
    connection.sendall(f"GET {path} HTTP/1.1\r\nHost: localhost\r\n\r\n".encode())
    data = b""
    while chunk := connection.recv(65536):
        data += chunk
    connection.close()
    head, _, body = data.partition(b"\r\n\r\n")
    return head.split(b"\r\n", 1)[0], json.loads(body)


def wait_for(condition, seconds=10):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(.02)
    return False


@POSIX
def test_the_hub_offers_chromes_pipe_on_a_socket_of_its_user_alone(tmp_path):
    """The program as display.sh starts it, with a stand-in Chrome: Chrome
    gets --remote-debugging-pipe and fd 3 and 4, the socket mode 0600, each
    connection its own session, /json/list the pages, and the hub ends with
    Chrome."""
    chrome, log = tmp_path / "chrome.py", tmp_path / "chrome.log"
    chrome.write_text(FAKE_CHROME, encoding="utf-8")
    sock_path = str(tmp_path / "cdp.sock")
    hub_path = os.path.join(os.path.dirname(load("cdp").__file__), "cdp.py")
    hub = subprocess.Popen([sys.executable, hub_path, sock_path, sys.executable, str(chrome), "--user-data-dir=x"],
                           env={**os.environ, "FAKE_CHROME_LOG": str(log)})
    try:
        assert wait_for(lambda: os.path.exists(sock_path))
        assert stat.S_IMODE(os.stat(sock_path).st_mode) == 0o600
        status, pages = http_get("/json/list", sock_path)
        assert status.endswith(b"200 OK") and pages == [
            {"id": "T1", "type": "page", "title": "Example", "url": "https://example.com/"}]
        status, version = http_get("/json/version", sock_path)
        assert version["Browser"] == "Chrome/1.0"
        assert version["webSocketDebuggerUrl"] == f"ws+unix://{sock_path}:/devtools/browser"
        first, second = WebSocket(sock_path), WebSocket(sock_path)
        first.send({"id": 1, "method": "Target.setAutoAttach", "params": {"autoAttach": True, "flatten": True}})
        second.send({"id": 1, "method": "Browser.getVersion"})
        assert first.receive() == {"id": 1, "result": {"echo": "Target.setAutoAttach"}}
        attached = first.receive()
        assert attached["method"] == "Target.attachedToTarget" and "sessionId" not in attached
        page = attached["params"]["sessionId"]
        assert second.receive() == {"id": 1, "result": {"product": "Chrome/1.0", "protocolVersion": "1.3"}}
        first.send({"id": 2, "method": "Runtime.evaluate", "sessionId": page})
        assert first.receive() == {"id": 2, "sessionId": page, "result": {"echo": "Runtime.evaluate"}}
        second.send({"id": 2, "method": "Runtime.evaluate", "sessionId": page})
        assert second.receive()["error"]["message"] == "Session not found"
        first.close()

        def detached():
            lines = [json.loads(line) for line in log.read_text().splitlines()]
            return [line for line in lines if line["method"] == "Target.detachFromTarget"]
        assert wait_for(lambda: bool(detached()))
        [detach] = detached()
        roots = [json.loads(line) for line in log.read_text().splitlines()
                 if json.loads(line)["method"] == "Target.setAutoAttach"]
        assert detach["params"]["sessionId"] == roots[0]["sessionId"]
        # Chrome got the pipe, nothing on a port.
        assert all("9222" not in arg for arg in hub.args)
        second.close()
    finally:
        hub.terminate()
        hub.wait(10)
    assert not os.path.exists(sock_path)


@POSIX
def test_the_hub_ends_with_chrome(tmp_path):
    chrome = tmp_path / "chrome.py"
    chrome.write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
    sock_path = str(tmp_path / "cdp.sock")
    hub_path = os.path.join(os.path.dirname(load("cdp").__file__), "cdp.py")
    hub = subprocess.run([sys.executable, hub_path, sock_path, sys.executable, str(chrome)], timeout=20)
    assert hub.returncode == 0 and not os.path.exists(sock_path)


def test_browser_reads_localhost_only_where_the_agents_user_listens(tmp_path):
    """agent_ports: the TCP ports uid 1500 listens on (state 0A), from 1024
    up, from the kernel's tables; another user's port, a connection that is
    no listener and a low port do not count, nor a port another user listens
    on at another address (127.0.0.2 next to 127.0.0.1)."""
    browser = load("browser")
    tcp, tcp6 = tmp_path / "tcp", tmp_path / "tcp6"
    head = "  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode\n"
    tcp.write_text(head
                   + "   0: 0100007F:1435 00000000:0000 0A 00000000:00000000 00:00000000 00000000  1500        0 1\n"
                   + "   1: 0100007F:2406 00000000:0000 0A 00000000:00000000 00:00000000 00000000  1001        0 2\n"
                   + "   2: 0100007F:0050 00000000:0000 0A 00000000:00000000 00:00000000 00000000  1500        0 3\n"
                   + "   3: 0100007F:1F40 0100007F:9C40 01 00000000:00000000 00:00000000 00000000  1500        0 4\n"
                   + "   4: 0200007F:0BB8 00000000:0000 0A 00000000:00000000 00:00000000 00000000  1500        0 6\n"
                   + "   5: 0100007F:0BB8 00000000:0000 0A 00000000:00000000 00:00000000 00000000     0        0 7\n")
    tcp6.write_text(head + "   0: 00000000000000000000000001000000:1F40 00000000000000000000000000000000:0000 0A "
                    "00000000:00000000 00:00000000 00000000  1500        0 5\n")
    assert browser.agent_ports((str(tcp), str(tcp6), str(tmp_path / "missing"))) == {5173, 8000}
    # localhost on those is the agent's own server; any other port, a file
    # or a private network is the workspace's own.
    for url, own in (("http://localhost:5173/", False), ("http://127.0.0.1:8000/api", False),
                     ("http://localhost:9222/json", True), ("http://localhost:3000/", True),
                     ("file:///home/sprite/.consens/browser/profile/Default/Cookies", True),
                     ("http://10.0.0.8/", True), ("https://example.com/", False), ("about:blank", False)):
        assert browser.own_computer(url, {5173, 8000}) is own, url
    assert browser.CDP == "ws+unix://" + os.path.join(browser.STATE, "cdp.sock") + ":/devtools/browser"
