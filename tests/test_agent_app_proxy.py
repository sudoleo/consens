"""An app the agent serves in the workspace, in the user's own browser
(agent_apps.py, agent_app_tunnel.py, agent_app_proxy.py, app/core/app_host.py
and the workspace's app_tunnel.py).

The way is real end to end: the workspace's own tunnel command runs here as
a process, a small web server and a WebSocket server stand in for the
agent's app, and the app host answers through the ASGI app. Only the
provider's exec socket between them is replaced, by the command's pipes."""
import asyncio
import http.server
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.app_host import AppHostMiddleware
from app.services import agent_app_proxy, agent_app_tunnel, agent_apps, workspace_guard

TUNNEL_PY = Path(agent_app_tunnel.__file__).with_name("workspace_vm") / "workbench" / "app_tunnel.py"
HOST = "apps.test"
UID = "owner"


class Command:
    """The tunnel command as the provider's exec socket carries it: frames
    0x00 are its stdin (0x04 its end), its stdout comes back as 0x01."""

    def __init__(self, processes):
        self.loop = asyncio.get_running_loop()
        self.queue = asyncio.Queue()
        self.process = subprocess.Popen([sys.executable, "-I", str(TUNNEL_PY), "--processes", str(processes)],
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self):
        try:
            while True:
                data = self.process.stdout.read1(65536)
                if not data:
                    break
                self.loop.call_soon_threadsafe(self.queue.put_nowait, b"\x01" + data)
            self.loop.call_soon_threadsafe(self.queue.put_nowait, None)
        except RuntimeError:
            # The test's loop is gone before the command's last bytes.
            pass

    def _write(self, data):
        try:
            self.process.stdin.write(data)
            self.process.stdin.flush()
        except (OSError, ValueError):
            pass

    async def send(self, message):
        if message == b"\x04":
            await asyncio.to_thread(self._end)
        elif message[:1] == b"\x00":
            await asyncio.to_thread(self._write, message[1:])

    def _end(self):
        try:
            self.process.stdin.close()
        except OSError:
            pass

    def __aiter__(self):
        return self

    async def __anext__(self):
        item = await self.queue.get()
        if item is None:
            raise StopAsyncIteration
        return item

    async def close(self):
        self.process.kill()


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def _send(self, status, body=b"", headers=()):
        self.send_response(status)
        for name, value in headers:
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        port = self.server.server_address[1]
        if self.path.startswith("/headers"):
            self._send(200, json.dumps({key.lower(): value for key, value in self.headers.items()}).encode(),
                       [("Content-Type", "application/json")])
        elif self.path == "/redirect":
            self._send(302, headers=[("Location", f"http://localhost:{port}/headers?after=1")])
        elif self.path == "/elsewhere":
            self._send(302, headers=[("Location", "https://example.org/x")])
        elif self.path == "/cookie":
            self._send(200, b"ok", [("Set-Cookie", "sid=abc; Domain=localhost; Path=/; HttpOnly"),
                                    ("Set-Cookie", f"{agent_apps.COOKIE}=stolen; Path=/")])
        elif self.path == "/stream":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            for piece in (b"one ", b"two ", b"three"):
                self.wfile.write(f"{len(piece):x}\r\n".encode() + piece + b"\r\n")
                self.wfile.flush()
                time.sleep(0.02)
            self.wfile.write(b"0\r\n\r\n")
        elif self.path == "/big":
            self._send(200, b"x" * (3 * 1024 * 1024))
        elif self.path == "/drop":
            self.connection.close()
        else:
            self._send(404, b"missing")

    def do_POST(self):
        if self.headers.get("Transfer-Encoding", "").lower() == "chunked":
            body = b""
            while True:
                size = int(self.rfile.readline().split(b";")[0].strip() or b"0", 16)
                if not size:
                    self.rfile.readline()
                    break
                body += self.rfile.read(size)
                self.rfile.readline()
        else:
            body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        self._send(200, body)

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Length", "5")
        self.end_headers()


@pytest.fixture
def web():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server.server_address[1]
    server.shutdown()
    server.server_close()


@pytest.fixture
def sockets():
    """A WebSocket server like a dev server's: it says what the handshake
    told it, then echoes."""
    from websockets.sync.server import serve

    def handle(websocket):
        request = websocket.request
        websocket.send(json.dumps({"host": request.headers.get("Host"), "origin": request.headers.get("Origin"),
                                   "cookie": request.headers.get("Cookie"), "path": request.path,
                                   "subprotocol": websocket.subprotocol}))
        for message in websocket:
            if message == "bye":
                websocket.close(4001, "done")
                return
            websocket.send(message)

    server = serve(handle, "127.0.0.1", 0, subprotocols=["vite-hmr"])
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server.socket.getsockname()[1]
    server.shutdown()


@pytest.fixture
def processes(tmp_path):
    """The workspace's folder of background processes, with one that runs."""
    running = tmp_path / "processes" / "abcd1234"
    running.mkdir(parents=True)
    (running / "pid").write_text(str(os.getpid()), encoding="ascii")
    return tmp_path / "processes"


@pytest.fixture
def host(monkeypatch, processes):
    """The app host over the real tunnel command; ``commands`` holds each
    one the server started."""
    commands = []

    async def connect(url):
        assert url == "wss://api.sprites.dev/exec"
        commands.append(Command(processes))
        return commands[-1]

    monkeypatch.setenv("AGENT_APP_HOST", HOST)
    monkeypatch.setattr(agent_app_tunnel, "exec_url", lambda uid: "wss://api.sprites.dev/exec")
    monkeypatch.setattr(agent_app_tunnel, "connect_upstream", connect)
    monkeypatch.setattr(workspace_guard, "status", lambda uid: workspace_guard.OPEN)
    for registry in (agent_app_tunnel._tunnels, agent_app_tunnel._opening, agent_app_tunnel._idle):
        registry.clear()
    inner = FastAPI()

    @inner.get("/health/maintenance")
    def health():
        return {"status": "ok"}

    @inner.get("/{rest:path}")
    def consens(rest: str):
        return {"consens": rest}

    inner.add_middleware(AppHostMiddleware)
    with TestClient(inner, base_url=f"https://{HOST}", follow_redirects=False) as client:
        client.commands = commands
        yield client
    for command in commands:
        command.process.kill()
    for registry in (agent_app_tunnel._tunnels, agent_app_tunnel._opening, agent_app_tunnel._idle):
        registry.clear()


def sign_in(client, port, path="/", chat="chat-1"):
    """Opens the app as the card does: the opening address, its two answers."""
    token = agent_apps.issue_open(UID, port, path, agent_apps.app_key(UID, chat, port))
    first = client.get(f"{agent_apps.OPEN_PATH}?t={token}")
    assert first.status_code == 303
    second = client.get(first.headers["location"])
    assert second.status_code == 303
    return first, second


# --- Addresses and sessions ----------------------------------------------------


def test_an_opening_address_holds_for_a_minute_and_is_no_session():
    key = agent_apps.app_key(UID, "chat", 3000)
    token = agent_apps.issue_open(UID, 3000, "/app?x=1", key, now=1000)
    session, path = agent_apps.read_open(token, now=1000 + agent_apps.OPEN_SECONDS)
    assert (session.uid, session.port, session.key, path) == (UID, 3000, key, "/app?x=1")
    with pytest.raises(agent_apps.InvalidToken):
        agent_apps.read_open(token, now=1000 + agent_apps.OPEN_SECONDS + 2)
    with pytest.raises(agent_apps.InvalidToken):
        agent_apps.read_session(token, now=1000)
    cookie = agent_apps.issue_session(session, now=1000)
    assert agent_apps.read_session(cookie, now=1000 + agent_apps.SESSION_SECONDS).port == 3000
    with pytest.raises(agent_apps.InvalidToken):
        agent_apps.read_open(cookie, now=1000)
    with pytest.raises(agent_apps.InvalidToken):
        agent_apps.read_session(cookie, now=1000 + agent_apps.SESSION_SECONDS + 2)


@pytest.mark.parametrize("port", [80, 1023, 65536, "3000", 3000.0, True])
def test_only_a_port_an_app_may_listen_on_is_issued(port):
    from cryptography.fernet import Fernet
    import base64
    import hashlib
    # A token under the right key with a port outside the range is refused when read.
    cipher = Fernet(base64.urlsafe_b64encode(hashlib.sha256(b"agent-app-session\0" + agent_apps._PROCESS_SECRET)
                                             .digest()))
    value = cipher.encrypt(json.dumps([UID, port, "0" * 16]).encode()).decode()
    with pytest.raises(agent_apps.InvalidToken):
        agent_apps.read_session(value)


@pytest.mark.parametrize("path,expected", [
    ("/", "/"), ("/app/x?y=1#z", "/app/x?y=1#z"), ("", "/"), ("app", "/"), ("//evil.example", "/"),
    ("https://evil.example", "/"), ("/\\evil.example", "/"), ("/a\nb", "/"),
    (agent_apps.OPEN_PATH + "?t=x", "/"), ("/a\ud800", "/"),
])
def test_an_app_opens_at_a_path_of_its_own_host(path, expected):
    assert agent_apps.start_path(path) == expected


@pytest.mark.parametrize("path", [
    # The tool's longest path (vm_show_app), all umlauts: it opened as "This
    # link is no longer valid" while each one took six characters.
    "/" + "ü" * 499,
    # The longest path the card may send, in characters of four bytes.
    "/" + "😀" * (agent_apps.PATH_CHARS - 1),
], ids=["tool-umlauts", "card-four-bytes"])
def test_an_opening_holds_any_path_an_app_may_open_at(path):
    uid = "u" * 128
    key = agent_apps.app_key(uid, "chat", 3000)
    session, opened = agent_apps.read_open(agent_apps.issue_open(uid, 3000, path, key))
    assert (session.uid, opened) == (uid, path)


def test_the_host_is_only_what_reads_as_one(monkeypatch):
    for value, expected in (("Apps.Example.com", "apps.example.com"), ("localhost:8000", "localhost:8000"),
                            ("", ""), ("https://apps.example.com", ""), ("apps.example.com/x", "")):
        monkeypatch.setenv("AGENT_APP_HOST", value)
        assert agent_apps.host() == expected
    # Plain http only where the host is this machine (a developer's server).
    for value, scheme in (("apps.example.com", "https"), ("localhost:8765", "http"), ("apps.localhost:8765", "http"),
                          ("127.0.0.1:8765", "http"), ("notlocalhost.example:8765", "https")):
        monkeypatch.setenv("AGENT_APP_HOST", value)
        assert agent_apps.open_url("T") == f"{scheme}://{value}{agent_apps.OPEN_PATH}?t=T"


# --- The host ------------------------------------------------------------------


def test_the_apps_host_serves_nothing_of_consens(host):
    # consens.io's own routes do not answer there, whatever the path; its health checks do.
    page = host.get("/app")
    assert page.status_code == 403 and "consens.io workspace" in page.text
    assert page.headers["x-robots-tag"] == "noindex, nofollow"
    assert "default-src 'none'" in page.headers["content-security-policy"]
    assert host.get("/health/maintenance").json() == {"status": "ok"}
    # Any other host is consens.io as before.
    assert host.get("/app", headers={"host": "www.consens.io"}).json() == {"consens": "app"}


def test_without_a_configured_host_nothing_changes(host, monkeypatch):
    monkeypatch.delenv("AGENT_APP_HOST")
    assert host.get("/app").json() == {"consens": "app"}


def test_its_pages_speak_the_readers_language(host):
    page = host.get("/", headers={"accept-language": "de-DE,de;q=0.9,en;q=0.8"})
    assert 'lang="de"' in page.text and "Arbeitsplatz" in page.text


def test_opening_clears_what_another_app_left_then_sets_the_session(host, web):
    first, second = sign_in(host, web, "/headers?start=1")
    assert first.headers["clear-site-data"] == '"cache", "cookies", "storage"'
    assert "set-cookie" not in first.headers
    cookie = second.headers["set-cookie"]
    assert cookie.startswith(agent_apps.COOKIE + "=") and "HttpOnly" in cookie and "Secure" in cookie
    assert "Domain" not in cookie and "SameSite=Lax" in cookie
    assert second.headers["location"] == "/headers?start=1"
    assert second.headers["cross-origin-opener-policy"] == "same-origin"
    # The same app again keeps what it stored: one answer, nothing cleared.
    token = agent_apps.issue_open(UID, web, "/", agent_apps.app_key(UID, "chat-1", web))
    again = host.get(f"{agent_apps.OPEN_PATH}?t={token}")
    assert again.status_code == 303 and "clear-site-data" not in again.headers and "set-cookie" in again.headers
    # Another chat's app on the same port starts clean.
    other = agent_apps.issue_open(UID, web, "/", agent_apps.app_key(UID, "chat-2", web))
    assert "clear-site-data" in host.get(f"{agent_apps.OPEN_PATH}?t={other}").headers


def test_a_second_step_that_still_holds_another_apps_session_clears_it_itself(host, web):
    # The first answer's clearing did not happen: a browser that ignored it,
    # or an address that starts at the second step. What the last app
    # stored goes all the same, its cookies too, which would go on to the next.
    sign_in(host, web, chat="chat-1")
    host.cookies.set("sid", "the-last-apps", domain=HOST)
    other = agent_apps.issue_open("someone-else", web, "/", agent_apps.app_key("someone-else", "chat-9", web))
    second = host.get(f"{agent_apps.OPEN_PATH}?t={other}&s=1")
    assert second.status_code == 303 and second.headers["location"] == "/"
    assert second.headers["clear-site-data"] == '"cache", "storage"'
    cookies = second.headers.get_list("set-cookie")
    assert any(cookie.startswith("sid=;") and "Max-Age=0" in cookie for cookie in cookies)
    session = [cookie for cookie in cookies if cookie.startswith(agent_apps.COOKIE + "=")]
    assert len(session) == 1 and "Max-Age=0" not in session[0]
    assert "sid" not in host.cookies
    # A clean browser's second step (the first one cleared) clears nothing more.
    host.cookies.clear()
    _first, clean = sign_in(host, web, chat="chat-2")
    assert "clear-site-data" not in clean.headers


def test_no_app_registers_a_service_worker_here(host, web):
    # One would answer for every later app under this one host, before the
    # opening address could clear it: it is never fetched from the app.
    sign_in(host, web)
    refused = host.get("/sw.js", headers={"service-worker": "script"})
    assert refused.status_code == 403
    assert not host.commands
    assert host.get("/headers").status_code == 200


def test_an_address_that_is_not_ours_opens_nothing(host):
    page = host.get(f"{agent_apps.OPEN_PATH}?t={'A' * 120}")
    assert page.status_code == 403 and "no longer valid" in page.text and "set-cookie" not in page.headers
    assert host.post(f"{agent_apps.OPEN_PATH}?t=x").status_code == 405


# --- Requests --------------------------------------------------------------------


def test_the_app_sees_a_browser_on_its_own_computer(host, web):
    sign_in(host, web)
    host.cookies.set("theme", "dark")
    seen = host.get("/headers?a=1", headers={
        "origin": f"https://{HOST}", "referer": f"https://{HOST}/page?x=1", "x-forwarded-for": "203.0.113.9",
        "cf-connecting-ip": "203.0.113.9", "x-custom": "kept", "authorization": "Bearer app-token"}).json()
    assert seen["host"] == f"localhost:{web}"
    assert seen["origin"] == f"http://localhost:{web}"
    assert seen["referer"] == f"http://localhost:{web}/page?x=1"
    assert seen["x-custom"] == "kept" and seen["authorization"] == "Bearer app-token"
    # Nothing of the service's front, and never the session.
    assert "x-forwarded-for" not in seen and "cf-connecting-ip" not in seen
    assert seen["cookie"] == "theme=dark" and agent_apps.COOKIE not in seen["cookie"]
    assert len(host.commands) == 1


def test_bodies_go_both_ways_whole(host, web):
    sign_in(host, web)
    body = os.urandom(700_000)
    assert host.post("/echo", content=body).content == body
    # A body without a length (chunked) arrives too.
    assert host.post("/echo", content=iter([b"ab", b"cd"])).content == b"abcd"
    assert host.get("/stream").text == "one two three"
    assert len(host.get("/big").content) == 3 * 1024 * 1024
    head = host.head("/anything")
    assert head.status_code == 200 and head.content == b""
    assert host.get("/nothing").status_code == 404
    # All of them through the one command.
    assert len(host.commands) == 1


def test_what_the_app_says_of_localhost_is_turned_to_this_host(host, web):
    sign_in(host, web)
    assert host.get("/redirect").headers["location"] == "/headers?after=1"
    assert host.get("/elsewhere").headers["location"] == "https://example.org/x"
    cookies = host.get("/cookie").headers.get_list("set-cookie")
    assert cookies == ["sid=abc; Path=/; HttpOnly"]


def test_a_port_nothing_listens_on_says_so(host, web, sockets):
    import socket
    with socket.socket() as free:
        free.bind(("127.0.0.1", 0))
        port = free.getsockname()[1]
    sign_in(host, port)
    page = host.get("/")
    assert page.status_code == 502 and str(port) in page.text


def test_an_app_that_drops_the_connection_is_a_page_not_an_error(host, web):
    sign_in(host, web)
    page = host.get("/drop")
    assert page.status_code == 502 and "without an answer" in page.text


def test_without_a_running_process_nothing_is_served_and_the_vm_is_left_alone(host, web, processes):
    sign_in(host, web)
    assert host.get("/headers").status_code == 200
    # The agent's process ended: its exit code is there.
    (processes / "abcd1234" / "exit_code").write_text("0", encoding="ascii")
    page = host.get("/headers")
    assert page.status_code == 503 and "not running" in page.text
    started = len(host.commands)
    # A tab left open asks on: answered from the server, no new command in the VM.
    for _ in range(3):
        assert host.get("/headers").status_code == 503
    assert len(host.commands) == started
    # Opened anew from the chat, with a process running again, it is asked again.
    (processes / "abcd1234" / "exit_code").unlink()
    agent_app_tunnel.expect(UID)
    assert host.get("/headers").status_code == 200


def test_a_workspace_the_safety_rules_closed_serves_no_app(host, web, monkeypatch):
    sign_in(host, web)
    monkeypatch.setattr(workspace_guard, "status", lambda uid: workspace_guard.Status(state="closed"))
    page = host.get("/headers")
    assert page.status_code == 503 and "cannot be reached" in page.text
    assert host.commands == []


def test_what_it_carries_counts_for_the_safety_rules(host, web, monkeypatch):
    counted = []
    monkeypatch.setattr(workspace_guard, "note_view_bytes", lambda uid, count: counted.append((uid, count)))
    sign_in(host, web)
    assert len(host.get("/big").content) == 3 * 1024 * 1024
    host.get("/big")
    assert counted and all(uid == UID for uid, _ in counted)
    assert sum(count for _, count in counted) >= agent_app_tunnel.METER_BYTES


# --- WebSockets ------------------------------------------------------------------


def test_a_websocket_reaches_the_app_like_a_request(host, sockets):
    sign_in(host, sockets)
    host.cookies.set("theme", "dark")
    with host.websocket_connect(f"wss://{HOST}/hmr?token=abc", subprotocols=["vite-hmr"]) as socket:
        hello = json.loads(socket.receive_text())
        assert hello == {"host": f"localhost:{sockets}", "origin": f"http://localhost:{sockets}",
                         "cookie": "theme=dark", "path": "/hmr?token=abc", "subprotocol": "vite-hmr"}
        assert socket.accepted_subprotocol == "vite-hmr"
        socket.send_text("ping ä")
        assert socket.receive_text() == "ping ä"
        payload = os.urandom(300_000)
        socket.send_bytes(payload)
        assert socket.receive_bytes() == payload
        # The app closes: its code reaches the browser.
        socket.send_text("bye")
        with pytest.raises(WebSocketDisconnect) as closed:
            socket.receive_text()
        assert closed.value.code == 4001


def test_a_websocket_without_a_session_is_refused(host, sockets):
    with pytest.raises(WebSocketDisconnect):
        with host.websocket_connect(f"wss://{HOST}/hmr"):
            pass


# --- The workspace's command ---------------------------------------------------


def test_the_command_ends_by_itself_once_no_process_runs(processes, monkeypatch):
    import struct
    command = subprocess.Popen([sys.executable, "-I", "-c",
                                "import runpy, sys; sys.argv = ['app_tunnel.py', '--processes', sys.argv[1]]; "
                                f"module = runpy.run_path({str(TUNNEL_PY)!r}); "
                                "module['watch'].__globals__['CHECK_SECONDS'] = 0.05; "
                                "sys.exit(module['main'](sys.argv[1:]))", str(processes)],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    try:
        head = struct.Struct(">BII")
        kind, stream, length = head.unpack(command.stdout.read(head.size))
        assert (kind, stream, command.stdout.read(length)) == (agent_app_tunnel.HELLO, 0, b"1")
        (processes / "abcd1234" / "exit_code").write_text("0", encoding="ascii")
        kind, stream, length = head.unpack(command.stdout.read(head.size))
        assert (kind, command.stdout.read(length)) == (agent_app_tunnel.BYE, b"idle")
        assert command.wait(10) == 0
    finally:
        command.kill()


def test_both_ends_speak_the_same_frames():
    import runpy
    theirs = runpy.run_path(str(TUNNEL_PY))
    for name in ("OPEN", "DATA", "END", "CLOSE", "PING", "HELLO", "OPENED", "REFUSED", "BYE", "PONG", "MAX_FRAME"):
        assert theirs[name] == getattr(agent_app_tunnel, name), name
    assert theirs["HEAD"].format == agent_app_tunnel.HEAD.format
    assert theirs["CHUNK"] <= theirs["MAX_FRAME"] and agent_app_tunnel.CHUNK <= theirs["MAX_FRAME"]
    assert theirs["LOWEST_PORT"] == agent_apps.LOWEST_PORT


def test_the_command_is_one_of_the_workspaces_tools():
    from app.services import agent_workspace
    assert "app_tunnel.py" in agent_workspace.TOOL_FILES["workbench"]
    assert agent_app_tunnel.TUNNEL == agent_workspace.WORKSPACE_DIR + "/app_tunnel.py"
    assert agent_proxy_marks_its_sentences()


def agent_proxy_marks_its_sentences():
    """scripts/i18n.py finds the pages' sentences through ``_t`` (SERVER_MARKED)."""
    script = (Path(__file__).parents[1] / "scripts" / "i18n.py").read_text(encoding="utf-8")
    return '"app/services/agent_app_proxy.py": {"_t"}' in script and callable(agent_app_proxy._t)


def test_no_tool_of_the_workspace_has_a_name_its_setup_removes():
    """A new VM's setup removes the files of older layouts by their names. A
    tool called like one of them is gone right after it was written: the
    tunnel's command, first named tunnel.py like the tunnel between two VMs
    before, was missing on a test Sprite (2026-11-23)."""
    import re
    from app.services import agent_workspace
    setup = (TUNNEL_PY.parent / "setup.sh").read_text(encoding="utf-8")
    removed = {name for names in re.findall(r"for old in ([^;]+); do", setup) for name in names.split()}
    removed |= set(re.findall(r'\.consens/workspace/([A-Za-z0-9_.-]+)"',
                              "\n".join(line for line in setup.splitlines() if line.lstrip().startswith("rm "))))
    tools = {name for names in agent_workspace.TOOL_FILES.values() for name in names}
    assert "tunnel.py" in removed and not removed & tools


def test_the_command_asks_wherever_localhost_may_be(monkeypatch):
    """On a Sprite the name localhost is fdf::1 before 127.0.0.1, and a
    server bound to the name listens there only: the command asks the name's
    own addresses first, then both loopbacks, each once."""
    import runpy
    import socket
    theirs = runpy.run_path(str(TUNNEL_PY))
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [
        (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("fdf::1", 3000, 0, 0)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 3000))])
    assert [address[0] for _, address in theirs["local_addresses"](3000)] == ["fdf::1", "127.0.0.1", "::1"]

    def no_names(*args, **kwargs):
        raise OSError
    monkeypatch.setattr(socket, "getaddrinfo", no_names)
    assert [address[0] for _, address in theirs["local_addresses"](3000)] == ["127.0.0.1", "::1"]
