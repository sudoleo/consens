"""consens.io workspace: Chrome's debugging protocol (CDP) on a Unix socket
only the provider's user opens (since 2026-11-04, when the browser moved onto
the workbench, docs/agent-mode.md "Ein Rechner").

Chrome's own debugging port is TCP on 127.0.0.1, and every user of the
computer reaches it: on the workbench the agent's user too, and with it every
cookie and tab of the browser. So Chrome gets no port. display.sh starts it
through this program with --remote-debugging-pipe: Chrome reads the protocol
from its fd 3 and answers on fd 4, and only this process holds the other
ends. It offers the protocol on SOCKET (mode 0600, in the provider's home,
which the agent's user cannot open) to the server's own programs:
browser.py (Playwright, ``ws+unix://SOCKET:/devtools/browser``), display.sh
and relay.py (``GET /json/list`` over the socket).

Several may be connected at once, as on Chrome's port (a call of the agent
next to the resident helper's): each connection gets a browser session of its
own (Target.attachToBrowserTarget), its messages carry that session and ids
of this process, and what Chrome sends goes to the connection whose session
it names, its own ids back. Ending a connection detaches its session, which
ends what it set up (the auto-attach, the download folder), as a closed port
connection does. The same program for every call, no rules of its own: what
a connection may do is what the socket's file mode lets through.

Ends with Chrome (and Chrome with it: a closed pipe ends Chrome's protocol,
display.sh then starts both again). Standard library only.

    cdp.py <socket> <chrome> [chrome's arguments...]
"""
import base64
import collections
import hashlib
import json
import os
import signal
import socket
import struct
import sys
import threading

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
# One message from a connection at most; Chrome's (screenshots) have no limit here.
MESSAGE_BYTES = 64 * 1024 * 1024
HEADER_BYTES = 16 * 1024
SEND_SECONDS = 30
ANSWER_SECONDS = 10
# What may wait for a connection that does not read (Connection).
QUEUE_BYTES = 64 * 1024 * 1024


class Hub:
    def __init__(self, write_fd):
        self._write_fd = write_fd
        self._write_lock = threading.Lock()
        self._lock = threading.Lock()
        self._next = 0
        # Our id -> (connection or None, its id, waiter for our own questions).
        self._pending = {}
        # Session id -> the connection it belongs to.
        self._owners = {}

    def _id(self):
        with self._lock:
            self._next += 1
            return self._next

    def write(self, message):
        data = json.dumps(message, separators=(",", ":")).encode("utf-8") + b"\0"
        with self._write_lock:
            view = memoryview(data)
            while view:
                view = view[os.write(self._write_fd, view):]

    def ask(self, method, params=None, session=None, seconds=ANSWER_SECONDS):
        """Our own question to Chrome; its answer (a dict) or None."""
        waiter = {"done": threading.Event(), "answer": None}
        number = self._id()
        with self._lock:
            self._pending[number] = (None, None, waiter)
        message = {"id": number, "method": method, "params": params or {}}
        if session:
            message["sessionId"] = session
        self.write(message)
        waiter["done"].wait(seconds)
        with self._lock:
            self._pending.pop(number, None)
        return waiter["answer"]

    def tell(self, method, params=None):
        """A question whose answer nobody waits for."""
        number = self._id()
        with self._lock:
            self._pending[number] = (None, None, None)
        self.write({"id": number, "method": method, "params": params or {}})

    def own(self, session, connection):
        with self._lock:
            self._owners[session] = connection
            connection.sessions.add(session)

    def forward(self, connection, message):
        """A connection's message to Chrome, with our id and its session."""
        session = message.get("sessionId")
        with self._lock:
            if session is None:
                session = connection.root
            elif self._owners.get(session) is not connection:
                session = None
            if session is not None:
                number = self._next = self._next + 1
                self._pending[number] = (connection, message.get("id"), None)
        if session is None:
            connection.send({"id": message.get("id"), "error": {"code": -32001, "message": "Session not found"}})
            return
        self.write({**message, "id": number, "sessionId": session})

    def dispatch(self, raw):
        try:
            message = json.loads(raw)
        except ValueError:
            return
        if not isinstance(message, dict):
            return
        if "id" in message:
            with self._lock:
                connection, theirs, waiter = self._pending.pop(message["id"], (None, None, None))
            if waiter is not None:
                waiter["answer"] = message
                waiter["done"].set()
                return
            if connection is None:
                return
            found = (message.get("result") or {}).get("sessionId")
            if isinstance(found, str):
                self.own(found, connection)
            message["id"] = theirs
            if message.get("sessionId") == connection.root:
                del message["sessionId"]
            connection.send(message)
            return
        session = message.get("sessionId")
        with self._lock:
            connection = self._owners.get(session) if session else None
        if connection is None:
            return
        params = message.get("params") or {}
        if message.get("method") == "Target.attachedToTarget" and isinstance(params.get("sessionId"), str):
            self.own(params["sessionId"], connection)
        elif message.get("method") == "Target.detachedFromTarget" and isinstance(params.get("sessionId"), str):
            with self._lock:
                self._owners.pop(params["sessionId"], None)
                connection.sessions.discard(params["sessionId"])
        if session == connection.root:
            message = {key: value for key, value in message.items() if key != "sessionId"}
        connection.send(message)

    def leave(self, connection):
        """The connection ended: its browser session goes, and with it what it set up."""
        with self._lock:
            for session in connection.sessions:
                if self._owners.get(session) is connection:
                    del self._owners[session]
            connection.sessions.clear()
            for number, (owner, _, _) in list(self._pending.items()):
                if owner is connection:
                    del self._pending[number]
        if connection.root:
            try:
                self.tell("Target.detachFromTarget", {"sessionId": connection.root})
            except OSError:
                pass

    def targets(self):
        answer = self.ask("Target.getTargets") or {}
        infos = (answer.get("result") or {}).get("targetInfos") or []
        return [{"id": info.get("targetId"), "type": info.get("type"), "title": info.get("title", ""),
                 "url": info.get("url", "")} for info in infos if isinstance(info, dict)]

    def version(self):
        answer = self.ask("Browser.getVersion") or {}
        result = answer.get("result") or {}
        return {"Browser": result.get("product", ""), "Protocol-Version": result.get("protocolVersion", ""),
                "webSocketDebuggerUrl": "ws+unix://" + SOCKET_PATH[0] + ":/devtools/browser"}


SOCKET_PATH = [""]


class Connection:
    """One WebSocket client on the socket. What goes to it waits in its own
    queue for its own writer (since 2026-11-06): send runs on the one thread
    that reads Chrome's pipe, and a client that stopped reading held it in
    sendall, so no connection heard from Chrome any more and Chrome's pipe
    filled (bug hunt 2026-11-05). A client that lets more than QUEUE_BYTES
    wait is dropped, as one that left; one message of any size still goes."""

    def __init__(self, sock):
        self.sock = sock
        self.root = None
        self.sessions = set()
        self._ready = threading.Condition()
        self._queue = collections.deque()
        self._queued = 0
        self._writer = None
        self.closed = False

    def send(self, message, opcode=1):
        data = message if isinstance(message, bytes) else json.dumps(message, separators=(",", ":")).encode("utf-8")
        size = len(data)
        if size < 126:
            head = struct.pack("!BB", 0x80 | opcode, size)
        elif size < 65536:
            head = struct.pack("!BBH", 0x80 | opcode, 126, size)
        else:
            head = struct.pack("!BBQ", 0x80 | opcode, 127, size)
        frame = head + data
        with self._ready:
            if self.closed:
                return
            full = bool(self._queue) and self._queued + len(frame) > QUEUE_BYTES
            if not full:
                self._queue.append(frame)
                self._queued += len(frame)
                self._ready.notify()
                if self._writer is None:
                    self._writer = threading.Thread(target=self._write, daemon=True)
                    self._writer.start()
        if full:
            self.close()

    def _write(self):
        while True:
            with self._ready:
                while not self._queue and not self.closed:
                    self._ready.wait()
                if self.closed:
                    return
                frame = self._queue.popleft()
                self._queued -= len(frame)
            try:
                self.sock.sendall(frame)
            except OSError:
                self.close()
                return

    def close(self):
        with self._ready:
            self.closed = True
            self._queue.clear()
            self._queued = 0
            self._ready.notify_all()
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass


def read_exact(sock, size):
    data = bytearray()
    while len(data) < size:
        chunk = sock.recv(min(size - len(data), 1 << 20))
        if not chunk:
            raise EOFError
        data.extend(chunk)
    return bytes(data)


def unmask(data, mask):
    if not data:
        return b""
    key = (mask * (len(data) // 4 + 1))[:len(data)]
    return (int.from_bytes(data, "big") ^ int.from_bytes(key, "big")).to_bytes(len(data), "big")


def frames(sock):
    """The client's messages (text or binary payloads), pings answered."""
    parts, kind = [], None
    while True:
        first, second = read_exact(sock, 2)
        opcode, masked, size = first & 0x0F, second & 0x80, second & 0x7F
        if size == 126:
            size = struct.unpack("!H", read_exact(sock, 2))[0]
        elif size == 127:
            size = struct.unpack("!Q", read_exact(sock, 8))[0]
        if size > MESSAGE_BYTES or not masked:
            return
        mask = read_exact(sock, 4)
        payload = unmask(read_exact(sock, size), mask)
        if opcode == 8:
            return
        if opcode == 9:
            yield ("ping", bytes(payload))
            continue
        if opcode == 10:
            continue
        if opcode in (1, 2):
            parts, kind = [bytes(payload)], opcode
        elif opcode == 0 and kind is not None:
            parts.append(bytes(payload))
        else:
            return
        if sum(len(part) for part in parts) > MESSAGE_BYTES:
            return
        if first & 0x80:
            yield ("message", b"".join(parts))
            parts, kind = [], None


def respond(sock, status, body, kind="application/json"):
    data = json.dumps(body).encode("utf-8") if not isinstance(body, bytes) else body
    sock.sendall(f"HTTP/1.1 {status}\r\nContent-Type: {kind}\r\nContent-Length: {len(data)}\r\n"
                 "Connection: close\r\n\r\n".encode("ascii") + data)


def serve(hub, sock):
    try:
        sock.settimeout(SEND_SECONDS)
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = sock.recv(4096)
            if not chunk or len(head) > HEADER_BYTES:
                return
            head += chunk
        lines = head.split(b"\r\n\r\n", 1)[0].decode("latin-1").split("\r\n")
        method, path = (lines[0].split(" ") + ["", ""])[:2]
        headers = {}
        for line in lines[1:]:
            name, _, value = line.partition(":")
            headers[name.strip().lower()] = value.strip()
        if method != "GET":
            respond(sock, "405 Method Not Allowed", {"error": "GET only"})
            return
        if headers.get("upgrade", "").lower() != "websocket":
            route = path.split("?", 1)[0].rstrip("/")
            if route in {"/json", "/json/list"}:
                respond(sock, "200 OK", [target for target in hub.targets() if target.get("type") == "page"])
            elif route == "/json/version":
                respond(sock, "200 OK", hub.version())
            else:
                respond(sock, "404 Not Found", {"error": "not found"})
            return
        key = headers.get("sec-websocket-key", "")
        accept = base64.b64encode(hashlib.sha1((key + GUID).encode("ascii")).digest()).decode("ascii")
        connection = Connection(sock)
        answer = hub.ask("Target.attachToBrowserTarget")
        root = ((answer or {}).get("result") or {}).get("sessionId")
        if not isinstance(root, str):
            respond(sock, "503 Service Unavailable", {"error": "the browser did not answer"})
            return
        connection.root = root
        hub.own(root, connection)
        sock.sendall(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                      f"Sec-WebSocket-Accept: {accept}\r\n\r\n").encode("ascii"))
        sock.settimeout(None)
        try:
            for kind, payload in frames(sock):
                if kind == "ping":
                    connection.send(payload, opcode=10)
                    continue
                try:
                    message = json.loads(payload)
                except ValueError:
                    continue
                if isinstance(message, dict) and isinstance(message.get("method"), str):
                    hub.forward(connection, message)
        except (EOFError, OSError):
            pass
        finally:
            hub.leave(connection)
            connection.close()
    except (EOFError, OSError):
        pass
    finally:
        try:
            sock.close()
        except OSError:
            pass


def main():
    if len(sys.argv) < 3:
        sys.stderr.write("usage: cdp.py <socket> <chrome> [arguments...]\n")
        return 2
    path, argv = os.path.abspath(sys.argv[1]), sys.argv[2:]
    SOCKET_PATH[0] = path
    # Chrome reads from its fd 3 and writes to its fd 4.
    to_chrome_read, to_chrome_write = os.pipe()
    from_chrome_read, from_chrome_write = os.pipe()
    pid = os.posix_spawnp(argv[0], [*argv, "--remote-debugging-pipe"], os.environ,
                          file_actions=[(os.POSIX_SPAWN_DUP2, to_chrome_read, 3),
                                        (os.POSIX_SPAWN_DUP2, from_chrome_write, 4)])
    os.close(to_chrome_read)
    os.close(from_chrome_write)
    hub = Hub(to_chrome_write)

    def end(*_):
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    signal.signal(signal.SIGTERM, end)
    signal.signal(signal.SIGINT, end)

    old = os.umask(0o077)
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(path)
    os.umask(old)
    os.chmod(path, 0o600)
    listener.listen(16)

    def accept():
        while True:
            try:
                sock, _ = listener.accept()
            except OSError:
                return
            threading.Thread(target=serve, args=(hub, sock), daemon=True).start()
    threading.Thread(target=accept, daemon=True).start()

    def read():
        buffer = bytearray()
        while True:
            try:
                chunk = os.read(from_chrome_read, 1 << 20)
            except OSError:
                chunk = b""
            if not chunk:
                return
            start = len(buffer)
            buffer.extend(chunk)
            end = buffer.find(b"\0", start)
            while end != -1:
                hub.dispatch(bytes(buffer[:end]))
                del buffer[:end + 1]
                end = buffer.find(b"\0")
    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    try:
        os.waitpid(pid, 0)
    except ChildProcessError:
        pass
    try:
        os.unlink(path)
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
