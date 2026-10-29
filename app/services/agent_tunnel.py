"""localhost in the shared browser reaches the agent's workbench (since
2026-10-29, docs/agent-mode.md "Arbeitsplatz").

The browser has a VM of its own (security audit 2026-10-27, finding 2), so a
page the agent served on its workbench never showed there: models built a
game or an app for the user, started its dev server, opened localhost in the
browser and got a refusal (Max's tic-tac-toe runs, 2026-10-29). Now
``http://localhost:<port>`` in that browser is the same port of the
workbench, in one direction only:

  Chrome -> tunnel.py on the browser VM (127.0.0.1 and ::1, only the ports
  asked for) -> its stdout over the provider's exec API -> this module ->
  the provider's proxy API -> that port of the workbench.

Nothing on the workbench reaches the browser VM: the agent's processes see
connections arrive, as from any browser, and the backend opens every one of
them itself. The provider's token stays in this module's requests to the
provider's API (agent_vm). A port the browser VM uses itself (Chrome's
debugging port) is never listened on, so localhost opens only where the
tunnel holds the port (agent_browser.check_url, BrowserTools.call).

One tunnel per account in this process, started by the agent's first
localhost address and ended IDLE_SECONDS after its last bytes; the
live view starts it again for the ports asked before (resume), so the user
can go on in the agent's app after the run.
"""
from __future__ import annotations

import logging
import queue
import struct
import threading
import time

from app.core.observability import safe_exception
from app.services import agent_vm

HEADER = struct.Struct(">cII")
CHUNK = 65536
LOWEST_PORT = 1024
# Chrome's debugging port on the browser VM (display.sh; tunnel.RESERVED).
RESERVED_PORTS = frozenset({9222})
# The listener's own limit on the VM; the backend ends it much sooner.
TUNNEL_SECONDS = 6 * 3600
IDLE_SECONDS = 10 * 60
LISTEN_SECONDS = 20
POLL_SECONDS = 5
# What Chrome shows when nothing answers on the workbench's port.
NOTHING_THERE = ("HTTP/1.1 502 Bad Gateway\r\nContent-Type: text/plain; charset=utf-8\r\nConnection: close\r\n"
                 "Content-Length: {length}\r\n\r\n{body}")


def frame(kind, conn, payload=b""):
    return HEADER.pack(kind, conn, len(payload)) + payload


def allowed_port(port):
    return isinstance(port, int) and LOWEST_PORT <= port <= 65535 and port not in RESERVED_PORTS


def _nothing_there(port):
    body = f"Nothing answers on port {port} of the agent's workspace. Is its server running?\n".encode()
    return NOTHING_THERE.format(length=len(body), body=body.decode()).encode()


class _Conn:
    """One of Chrome's connections: what goes to the workbench waits in
    ``outbound`` (None ends it) until its proxy connection is open;
    ``peer_closed`` once the browser VM closed it (it is not told again)."""

    def __init__(self, conn, port):
        self.conn = conn
        self.port = port
        self.outbound = queue.Queue()
        self.peer_closed = threading.Event()


class Tunnel:
    """One account's tunnel: the listener's stream on the browser VM and a
    proxy connection to the workbench for every connection Chrome opens."""

    def __init__(self, uid, backend, *, clock=time.monotonic):
        self.uid = uid
        self.backend = backend
        self.browser = agent_vm.browser_name(uid)
        self.workbench = agent_vm.workspace_name(uid)
        self.clock = clock
        self.stream = None
        self.ports = set()
        self.conns = {}
        self.answers = {}
        self.lock = threading.Lock()
        self.used = clock()
        self.started = threading.Event()
        # closing from the first close on, ended once everything is closed.
        self.closing = False
        self.ended = threading.Event()

    def start(self):
        from app.services import agent_workspace
        argv = agent_vm.wrapped_command(f"exec python3 {agent_workspace.BROWSER_TUNNEL}", TUNNEL_SECONDS, False)
        self.stream = self.backend.open_stream(self.browser, argv, cwd=agent_vm.SERVER_HOME)
        threading.Thread(target=self._read, name="agent-tunnel", daemon=True).start()
        self.started.set()

    def live(self):
        return not self.closing

    def _send(self, kind, conn, payload=b""):
        if self.closing:
            return
        try:
            self.stream.send(frame(kind, conn, payload))
        except Exception as exc:
            logging.info("Agent tunnel send failed category=%s", safe_exception(exc))
            self.close()

    def listen(self, port, timeout=LISTEN_SECONDS):
        """True once the browser VM listens on ``port`` of localhost."""
        if port in self.ports:
            return True
        answer = threading.Event()
        with self.lock:
            self.answers[port] = answer
        self._send(b"L", 0, struct.pack(">H", port))
        answer.wait(timeout)
        with self.lock:
            self.answers.pop(port, None)
        return port in self.ports

    def _read(self):
        buffer = b""
        try:
            while not self.closing:
                chunk = self.stream.recv(POLL_SECONDS)
                if chunk is None:
                    break
                if not chunk:
                    # Idle by its bytes, not its connections: a dev server's
                    # live-reload socket stays open without a word and would
                    # keep both VMs awake for TUNNEL_SECONDS.
                    if self.clock() - self.used > IDLE_SECONDS:
                        break
                    continue
                buffer += chunk
                while len(buffer) >= HEADER.size:
                    kind, conn, length = HEADER.unpack_from(buffer)
                    if len(buffer) < HEADER.size + length:
                        break
                    payload = buffer[HEADER.size:HEADER.size + length]
                    buffer = buffer[HEADER.size + length:]
                    self._handle(kind, conn, payload)
        except Exception as exc:
            logging.info("Agent tunnel ended category=%s", safe_exception(exc))
        finally:
            self.close()

    def _handle(self, kind, conn, payload):
        if kind == b"L" and len(payload) == 3:
            port = struct.unpack(">H", payload[:2])[0]
            with self.lock:
                if payload[2:] == b"\x01":
                    self.ports.add(port)
                answer = self.answers.get(port)
            if answer is not None:
                answer.set()
        elif kind == b"O" and len(payload) == 2:
            self.used = self.clock()
            item = _Conn(conn, struct.unpack(">H", payload)[0])
            with self.lock:
                self.conns[conn] = item
            threading.Thread(target=self._carry, args=(item,), name="agent-tunnel-conn", daemon=True).start()
        elif kind == b"D":
            self.used = self.clock()
            item = self.conns.get(conn)
            if item is not None:
                item.outbound.put(payload)
        elif kind == b"C":
            item = self.conns.get(conn)
            if item is not None:
                item.peer_closed.set()
                item.outbound.put(None)

    def _carry(self, item):
        """One of Chrome's connections, to its port of the workbench."""
        try:
            upstream = self.backend.open_port(self.workbench, item.port)
        except Exception as exc:
            logging.info("Agent tunnel port not reached category=%s", safe_exception(exc))
            if not item.peer_closed.is_set():
                self._send(b"D", item.conn, _nothing_there(item.port))
            self._drop(item)
            return
        threading.Thread(target=self._back, args=(item, upstream), name="agent-tunnel-back", daemon=True).start()
        try:
            while True:
                data = item.outbound.get()
                if data is None or self.closing:
                    break
                upstream.send(data)
        except Exception as exc:
            logging.info("Agent tunnel upstream failed category=%s", safe_exception(exc))
        finally:
            # Ends _back's recv as well, which then tells the browser VM.
            try:
                upstream.close()
            except Exception:
                pass

    def _back(self, item, upstream):
        """The workbench's answer for one connection, back to Chrome."""
        try:
            while not self.closing:
                data = upstream.recv(POLL_SECONDS)
                if data is None:
                    break
                for start in range(0, len(data), CHUNK):
                    self.used = self.clock()
                    self._send(b"D", item.conn, data[start:start + CHUNK])
        except Exception as exc:
            logging.info("Agent tunnel downstream failed category=%s", safe_exception(exc))
        finally:
            self._drop(item)

    def _drop(self, item):
        with self.lock:
            self.conns.pop(item.conn, None)
        item.outbound.put(None)
        if not item.peer_closed.is_set():
            item.peer_closed.set()
            self._send(b"C", item.conn)

    def close(self):
        with self.lock:
            if self.closing:
                return
            self.closing = True
            items = list(self.conns.values())
            self.conns.clear()
            answers = list(self.answers.values())
        for item in items:
            item.peer_closed.set()
            item.outbound.put(None)
        for answer in answers:
            answer.set()
        for close in (getattr(self.stream, "close", None), getattr(self.backend, "close", None)):
            if close is not None:
                try:
                    close()
                except Exception:
                    pass
        self.ended.set()


_tunnels: dict[str, Tunnel] = {}
# The ports asked for per account, for resume: they outlive a tunnel's end
# (idle, the VM's sleep), never a restart of the backend.
_asked: dict[str, set[int]] = {}
_lock = threading.Lock()


def _tunnel(uid, backend_factory):
    with _lock:
        tunnel = _tunnels.get(uid)
        if tunnel is not None and tunnel.live():
            fresh = False
        else:
            backend = backend_factory()
            if backend is None:
                raise agent_vm.VMUnavailable("tunnel: no provider")
            tunnel = _tunnels[uid] = Tunnel(uid, backend)
            fresh = True
    if fresh:
        try:
            tunnel.start()
        except Exception:
            tunnel.close()
            tunnel.started.set()
            raise
    elif not tunnel.started.wait(LISTEN_SECONDS) or not tunnel.live():
        raise agent_vm.VMUnavailable("tunnel: not started")
    return tunnel


def open_port(uid, port, *, backend_factory=None):
    """localhost:``port`` in the account's browser reaches that port of its
    workbench; False when the browser VM uses the port itself. Raises
    VMUnavailable when the tunnel cannot start."""
    if not allowed_port(port):
        return False
    tunnel = _tunnel(uid, backend_factory or agent_vm.backend)
    if not tunnel.listen(port):
        return False
    with _lock:
        _asked.setdefault(uid, set()).add(port)
    return True


def asked(uid):
    """The ports asked for in this process, which the tunnel took."""
    with _lock:
        return set(_asked.get(uid, ()))


def resume(uid, *, backend_factory=None):
    """Starts the account's tunnel again for the ports asked before, in the
    background (the live view, routers/agent_workspace.py): the user goes on
    in the agent's app after the run, or after the tunnel was idle."""
    with _lock:
        ports = sorted(_asked.get(uid, ()))
        tunnel = _tunnels.get(uid)
        live = tunnel is not None and tunnel.live()
    if not ports or live:
        return None

    def run():
        try:
            for port in ports:
                open_port(uid, port, backend_factory=backend_factory)
        except Exception as exc:
            logging.info("Agent tunnel not resumed category=%s", safe_exception(exc))
    thread = threading.Thread(target=run, name="agent-tunnel-resume", daemon=True)
    thread.start()
    return thread


def close(uid):
    """Ends the account's tunnel (its workspace was deleted)."""
    with _lock:
        tunnel = _tunnels.pop(uid, None)
        _asked.pop(uid, None)
    if tunnel is not None:
        tunnel.close()
