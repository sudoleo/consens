"""localhost in the shared browser reaches the agent's workbench (since
2026-10-29, docs/agent-mode.md "Arbeitsplatz").

The browser has a VM of its own (security audit 2026-10-27, finding 2), so a
page the agent served on its workbench never showed there: models built a
game or an app for the user, started its dev server, opened localhost in the
browser and got a refusal (Max's tic-tac-toe runs, 2026-10-29). Now
``http://localhost:<port>`` in that browser is the same port of the
workbench, in one direction only:

  Chrome -> workspace_vm/tunnel.py listen on the browser VM (127.0.0.1 and
  ::1, only the ports asked for) -> its stdout over the provider's exec API
  -> this module -> the stdin of tunnel.py connect on the workbench (as the
  agent's user, agent-run) -> that port of the workbench's localhost.

This module only carries frames between the two (tunnel.py says which):
two threads per tunnel, none per connection, nothing buffered here, since
each side never sends more of a connection than the other took (WINDOW).
It opens connections only for the browser's side; a frame of the
workbench's side can only answer one (D, A, C, F) or say its ports (Q), so
whatever runs there, also something of the agent's in that process, can
answer the browser's localhost, as the agent's own server does anyway, and
nothing more. The provider's token stays in this module's requests to the
provider's API (agent_vm). Until the first live probe (2026-10-29) the
workbench's side was the provider's proxy API: it never passed on that a
server closed a connection (a response that ends with it never ended in
Chrome), reached no server on ::1 alone, and took 220 ms for each new
connection; through one exec stream a new one takes one round trip.

A port the browser VM uses itself (Chrome's debugging port) is never
listened on, so localhost opens only where the tunnel holds the port
(agent_browser.check_url, BrowserTools.call). Which ports: the one the
agent opens, and with it every port the agent's user listens on (Q, from
/proc/net/tcp of the workbench), so a page whose API is on another port
works. The ports are kept on the account's record
(agent_workspace.remember_values): a restart of the server forgets none.

One tunnel per account in this process (Render: one uvicorn, one instance),
started by the agent's first localhost address and ended IDLE_SECONDS after
its last bytes; the live view, a takeover and the next browser call start it
again (resume), so the user goes on in the agent's app after the run. At
most MAX_CONNECTIONS connections. The browser VM is the side the audit
trusts least: a frame longer than MAX_FRAME ends the tunnel, and a
connection to a port the tunnel does not hold is refused.
"""
from __future__ import annotations

import logging
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
# The two programs' own limit on the VMs; the backend ends them much sooner.
TUNNEL_SECONDS = 6 * 3600
IDLE_SECONDS = 10 * 60
# Both sides started (their H), a port listened on, the ports found.
LISTEN_SECONDS = 20
POLL_SECONDS = 5
# tunnel.py says the same.
MAX_CONNECTIONS = 64
WINDOW = 512 * 1024
MAX_FRAME = CHUNK + 64
# Ports at once, and the ones kept on the account's record.
MAX_PORTS = 16
KEEP_PORTS = 8
# What Chrome shows when nothing answers on the workbench's port.
NOTHING_THERE = ("HTTP/1.1 502 Bad Gateway\r\nContent-Type: text/plain; charset=utf-8\r\nConnection: close\r\n"
                 "Content-Length: {length}\r\n\r\n{body}")
NOTHING_LISTENS = "Nothing answers on port {port} of the agent's workspace. Is its server running?\n"


def frame(kind, conn, payload=b""):
    return HEADER.pack(kind, conn, len(payload)) + payload


def allowed_port(port):
    return type(port) is int and LOWEST_PORT <= port <= 65535 and port not in RESERVED_PORTS


def _nothing_there(port):
    body = NOTHING_LISTENS.format(port=port).encode()
    return NOTHING_THERE.format(length=len(body), body=body.decode()).encode()


class Tunnel:
    """One account's tunnel: the listener's stream on the browser VM
    (``stream``) and the connector's on the workbench (``bench``)."""

    def __init__(self, uid, backend, *, clock=time.monotonic):
        self.uid = uid
        self.backend = backend
        self.browser = agent_vm.browser_name(uid)
        self.workbench = agent_vm.workspace_name(uid)
        self.clock = clock
        self.stream = self.bench = None
        self.ports = set()
        self.refused = set()
        # The connections both sides know, and their port.
        self.open = {}
        self.answers = {}
        self.found = None
        self.found_event = threading.Event()
        self.hello = {"listen": threading.Event(), "connect": threading.Event()}
        self.lock = threading.Lock()
        self.used = clock()
        self.started = threading.Event()
        # closing from the first close on, ended once everything is closed.
        self.closing = False
        self.ended = threading.Event()

    def start(self):
        """Both programs, the workbench's while the browser's opens; ready
        once each said it runs (H)."""
        from app.services import agent_workspace
        failed = []

        def bench():
            try:
                self.bench = self.backend.open_stream(
                    self.workbench, agent_vm.agent_argv(["python3", agent_workspace.WORKBENCH_TUNNEL, "connect"],
                                                        TUNNEL_SECONDS, agent_vm.HOME), cwd="/")
            except Exception as exc:
                failed.append(exc)
        opening = threading.Thread(target=bench, name="agent-tunnel-bench-open", daemon=True)
        opening.start()
        try:
            self.stream = self.backend.open_stream(
                self.browser, agent_vm.wrapped_command(f"exec python3 {agent_workspace.BROWSER_TUNNEL} listen",
                                                       TUNNEL_SECONDS, False), cwd=agent_vm.SERVER_HOME)
        finally:
            # Also when the browser's side failed: the workbench's, once open,
            # is closed with the tunnel (close), never left running for hours.
            opening.join(agent_vm.WS_OPEN_SECONDS * 2 + 5)
        if failed or self.bench is None:
            raise failed[0] if failed else agent_vm.VMUnavailable("tunnel: workbench side did not open")
        threading.Thread(target=self._read, args=(self.stream, self._from_browser), name="agent-tunnel-browser",
                         daemon=True).start()
        threading.Thread(target=self._read, args=(self.bench, self._from_bench), name="agent-tunnel-bench",
                         daemon=True).start()
        deadline = time.monotonic() + LISTEN_SECONDS
        for side in ("listen", "connect"):
            if not self.hello[side].wait(max(0.0, deadline - time.monotonic())) or self.closing:
                raise agent_vm.VMUnavailable(f"tunnel: {side} side did not start")
        self.started.set()

    def live(self):
        return not self.closing

    def _send(self, stream, kind, conn, payload=b""):
        if self.closing:
            return
        try:
            stream.send(frame(kind, conn, payload))
        except Exception as exc:
            logging.info("Agent tunnel send failed category=%s", safe_exception(exc))
            self.close()

    def listen(self, ports, timeout=None):
        """The ports of ``ports`` the browser VM listens on once it answered
        for all of them (one round trip for any number); a port it refused
        joins ``refused``, one without an answer neither."""
        wanted = [port for port in dict.fromkeys(ports) if port not in self.ports]
        answers = {}
        with self.lock:
            for port in wanted:
                answers[port] = self.answers[port] = threading.Event()
        for port in wanted:
            self._send(self.stream, b"L", 0, struct.pack(">H", port))
        deadline = time.monotonic() + (LISTEN_SECONDS if timeout is None else timeout)
        for answer in answers.values():
            answer.wait(max(0.0, deadline - time.monotonic()))
        with self.lock:
            for port, answer in answers.items():
                if self.answers.get(port) is answer:
                    del self.answers[port]
            return {port for port in ports if port in self.ports}

    def listening(self, timeout=None):
        """The ports the agent's user listens on on the workbench now (Q); [] without an answer."""
        self.found_event.clear()
        self._send(self.bench, b"Q", 0)
        if not self.found_event.wait(LISTEN_SECONDS if timeout is None else timeout):
            return []
        return [port for port in (self.found or []) if allowed_port(port)][:MAX_PORTS]

    def _read(self, stream, handle):
        buffer = b""
        try:
            while not self.closing:
                chunk = stream.recv(POLL_SECONDS)
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
                    if length > MAX_FRAME:
                        logging.warning("Agent tunnel frame refused bytes=%s", length)
                        return
                    if len(buffer) < HEADER.size + length:
                        break
                    payload = buffer[HEADER.size:HEADER.size + length]
                    buffer = buffer[HEADER.size + length:]
                    handle(kind, conn, payload)
        except Exception as exc:
            logging.info("Agent tunnel ended category=%s", safe_exception(exc))
        finally:
            self.close()

    def _from_browser(self, kind, conn, payload):
        if kind == b"H":
            self.hello["listen"].set()
        elif kind == b"L" and len(payload) == 3:
            port = struct.unpack(">H", payload[:2])[0]
            with self.lock:
                if payload[2:] == b"\x01":
                    self.ports.add(port)
                    self.refused.discard(port)
                else:
                    self.refused.add(port)
                answer = self.answers.get(port)
            if answer is not None:
                answer.set()
        elif kind == b"O" and len(payload) == 2:
            self.used = self.clock()
            port = struct.unpack(">H", payload)[0]
            with self.lock:
                # Only to a port this tunnel holds, and not too many at once.
                admitted = port in self.ports and conn not in self.open and len(self.open) < MAX_CONNECTIONS
                if admitted:
                    self.open[conn] = port
            if admitted:
                self._send(self.bench, b"O", conn, payload)
            else:
                self._send(self.stream, b"C", conn)
        elif kind in (b"D", b"A", b"C"):
            self._carry(conn, kind, payload, self.bench)

    def _from_bench(self, kind, conn, payload):
        if kind == b"H":
            self.hello["connect"].set()
        elif kind == b"Q":
            self.found = [struct.unpack_from(">H", payload, start)[0] for start in range(0, len(payload) - 1, 2)]
            self.found_event.set()
        elif kind == b"F":
            with self.lock:
                port = self.open.pop(conn, None)
            if port is not None:
                self._send(self.stream, b"D", conn, _nothing_there(port))
                self._send(self.stream, b"C", conn)
        elif kind in (b"D", b"A", b"C"):
            self._carry(conn, kind, payload, self.stream)

    def _carry(self, conn, kind, payload, to):
        """A frame of a connection both sides know, to the other side; its
        close (C) ends it here."""
        with self.lock:
            known = conn in self.open
            if known and kind == b"C":
                del self.open[conn]
        if not known:
            return
        if kind == b"D":
            self.used = self.clock()
        self._send(to, kind, conn, payload)

    def close(self):
        with self.lock:
            if self.closing:
                return
            self.closing = True
            self.open.clear()
            answers = [*self.answers.values(), self.found_event, *self.hello.values()]
        for answer in answers:
            answer.set()
        for close in (getattr(self.stream, "close", None), getattr(self.bench, "close", None),
                      getattr(self.backend, "close", None)):
            if close is not None:
                try:
                    close()
                except Exception:
                    pass
        self.ended.set()


_tunnels: dict[str, Tunnel] = {}
# The ports the tunnel took per account: what browser.py may read on
# localhost and what resume listens on again. Seeded from the account's
# record (agent_workspace.Claim.tunnel_ports, record_for_view).
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
    elif not tunnel.started.wait(LISTEN_SECONDS * 2) or not tunnel.live():
        raise agent_vm.VMUnavailable("tunnel: not started")
    return tunnel


def _remember(uid, held, db):
    """``held`` joins the ports asked for; the new ones go on the account's record."""
    with _lock:
        known = _asked.setdefault(uid, set())
        new = sorted(port for port in held if port not in known)
        known.update(held)
    if new and db is not None:
        from app.services import agent_workspace
        try:
            agent_workspace.remember_values(db, uid, "tunnel_ports", new, keep=KEEP_PORTS)
        except Exception as exc:
            logging.info("Agent tunnel ports not kept category=%s", safe_exception(exc))


def open_ports(uid, ports, *, backend_factory=None, db=None):
    """localhost:<port> in the account's browser reaches that port of its
    workbench, for each of ``ports`` the browser VM does not use itself:
    returns those. Raises VMUnavailable when the tunnel cannot start or
    gave no answer for a port: only a port the browser VM refused is taken."""
    wanted = [port for port in dict.fromkeys(ports) if allowed_port(port)][:MAX_PORTS]
    if not wanted:
        return set()
    tunnel = _tunnel(uid, backend_factory or agent_vm.backend)
    held = tunnel.listen(wanted)
    _remember(uid, held, db)
    if any(port not in held and port not in tunnel.refused for port in wanted):
        raise agent_vm.VMUnavailable("tunnel: no answer")
    return held


def open_port(uid, port, *, backend_factory=None, db=None):
    return port in open_ports(uid, [port], backend_factory=backend_factory, db=db)


def seed(uid, ports):
    """The ports kept on the account's record, after a restart of the server."""
    kept = {port for port in ports if allowed_port(port)}
    if kept:
        with _lock:
            _asked.setdefault(uid, set()).update(kept)


def asked(uid):
    """The ports the tunnel took for the account."""
    with _lock:
        return set(_asked.get(uid, ()))


def live(uid):
    with _lock:
        tunnel = _tunnels.get(uid)
        return tunnel is not None and tunnel.live()


def touch(uid):
    """The user works in the agent's app (their takeover, refreshed by the
    view): the tunnel does not end as idle meanwhile."""
    with _lock:
        tunnel = _tunnels.get(uid)
    if tunnel is not None:
        tunnel.used = tunnel.clock()


def resume(uid, *, backend_factory=None, db=None, find=False):
    """In the background: the account's tunnel listens again on the ports
    it took before (a tunnel that ended when idle, a restart of the server),
    and with ``find`` also on the ports the agent's servers listen on now
    (the open of a localhost address, the live view). Nothing for an
    account that never used localhost, or when the tunnel runs and nothing
    is to be found. Returns the thread, or None."""
    with _lock:
        ports = sorted(_asked.get(uid, ()))
        tunnel = _tunnels.get(uid)
        live = tunnel is not None and tunnel.live()
    if not ports or (live and not find):
        return None

    def run():
        try:
            tunnel = _tunnel(uid, backend_factory or agent_vm.backend)
            if not live:
                _remember(uid, tunnel.listen(ports), db)
            if find:
                found = [port for port in tunnel.listening() if port not in tunnel.ports]
                if found:
                    _remember(uid, tunnel.listen(found), db)
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
