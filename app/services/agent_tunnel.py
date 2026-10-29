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

Which ports: the one the agent opens, and with it every port the agent's
user listens on at that moment (discover, from /proc/net/tcp of the
workbench), so an app whose page calls its API on another port works. The
ports are kept on the account's record (agent_workspace.remember_values), so
a restart of the server forgets none.

One tunnel per account in this process, started by the agent's first
localhost address and ended IDLE_SECONDS after its last bytes; the live view,
a takeover and the next browser call start it again (resume), so the user
goes on in the agent's app after the run. At most MAX_CONNECTIONS
connections, and each holds at most WINDOW bytes either way before the
other side took them (A frames, tunnel.py): a page that opens connections in
a loop, sends more than its server takes or stops reading its answer never
piles up threads or memory here, and never stops the other connections. The
browser VM is the side the audit trusts least: a frame longer than
MAX_FRAME ends the tunnel, and a connection to a port the tunnel does not
hold is refused.
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
# tunnel.py says the same.
MAX_CONNECTIONS = 64
WINDOW = 512 * 1024
MAX_FRAME = CHUNK + 64
# What of one connection may wait for its proxy connection or its server: its
# credit in bytes (WINDOW, a frame's slack on top), and in frames so many
# small ones (key presses over a WebSocket) never cost more memory than that.
QUEUE_BYTES = WINDOW + MAX_FRAME
QUEUE_FRAMES = 4096
# Ports at once, and the ones kept on the account's record.
MAX_PORTS = 16
KEEP_PORTS = 8
DISCOVER_SECONDS = 15
# The listening sockets of the workbench, read as the agent's user.
LISTENING_COMMAND = "cat /proc/net/tcp /proc/net/tcp6 2>/dev/null"
# What Chrome shows when nothing answers on the workbench's port, or the
# way there failed (the provider): the agent restarts a server only then.
NOTHING_THERE = ("HTTP/1.1 502 Bad Gateway\r\nContent-Type: text/plain; charset=utf-8\r\nConnection: close\r\n"
                 "Content-Length: {length}\r\n\r\n{body}")
NOTHING_LISTENS = "Nothing answers on port {port} of the agent's workspace. Is its server running?\n"
WAY_FAILED = "The way to port {port} of the agent's workspace failed. Reload in a moment.\n"


def frame(kind, conn, payload=b""):
    return HEADER.pack(kind, conn, len(payload)) + payload


def allowed_port(port):
    return type(port) is int and LOWEST_PORT <= port <= 65535 and port not in RESERVED_PORTS


def _nothing_there(port, closed=True):
    body = (NOTHING_LISTENS if closed else WAY_FAILED).format(port=port).encode()
    return NOTHING_THERE.format(length=len(body), body=body.decode()).encode()


def listening_ports(text, uid=agent_vm.AGENT_UID):
    """The ports the agent's user listens on, from /proc/net/tcp and tcp6:
    state 0A (LISTEN), its uid, a port the tunnel takes. Never another
    user's (the provider's services)."""
    ports = set()
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 8 or parts[3] != "0A" or ":" not in parts[1]:
            continue
        try:
            port, owner = int(parts[1].rsplit(":", 1)[1], 16), int(parts[7])
        except ValueError:
            continue
        if owner == uid and allowed_port(port):
            ports.add(port)
    return sorted(ports)[:MAX_PORTS]


def discover(backend, uid, cancellation=None):
    """The ports the agent's servers on the account's workbench listen on
    now; [] when it cannot say."""
    from app.services.llm.provider_runtime import ProviderCancellation
    out = bytearray()

    def keep(stream, chunk):
        if stream == "stdout" and len(out) < 1024 * 1024:
            out.extend(chunk)
    try:
        outcome = backend.exec(agent_vm.workspace_name(uid), LISTENING_COMMAND, cwd=agent_vm.HOME,
                               timeout=DISCOVER_SECONDS, on_output=keep,
                               cancellation=cancellation or ProviderCancellation(), agent=True)
    except Exception as exc:
        logging.info("Agent tunnel ports not read category=%s", safe_exception(exc))
        return []
    if outcome.exit_code != 0:
        return []
    return listening_ports(bytes(out).decode("ascii", "replace"))


class _Conn:
    """One of Chrome's connections: what goes to the workbench waits in
    ``outbound`` (None ends it) until its proxy connection (``upstream``)
    is open; ``inflight`` bytes went to the browser VM that Chrome has not
    taken yet (``credit`` wakes the sender); ``peer_closed`` once the
    browser VM closed it (it is not told again); ``ended`` once it goes,
    with whatever still waits."""

    def __init__(self, conn, port):
        self.conn = conn
        self.port = port
        self.outbound = queue.Queue(maxsize=QUEUE_FRAMES)
        self.queued = 0
        self.inflight = 0
        self.credit = threading.Condition()
        self.peer_closed = threading.Event()
        self.ended = threading.Event()
        self.upstream = None


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
        self.refused = set()
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
            self._send(b"L", 0, struct.pack(">H", port))
        deadline = time.monotonic() + (LISTEN_SECONDS if timeout is None else timeout)
        for answer in answers.values():
            answer.wait(max(0.0, deadline - time.monotonic()))
        with self.lock:
            for port, answer in answers.items():
                if self.answers.get(port) is answer:
                    del self.answers[port]
            return {port for port in ports if port in self.ports}

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
                    if length > MAX_FRAME:
                        logging.warning("Agent tunnel frame refused bytes=%s", length)
                        return
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
                item = (_Conn(conn, port) if port in self.ports and conn not in self.conns
                        and len(self.conns) < MAX_CONNECTIONS else None)
                if item is not None:
                    self.conns[conn] = item
            if item is None:
                self._send(b"C", conn)
                return
            threading.Thread(target=self._carry, args=(item,), name="agent-tunnel-conn", daemon=True).start()
        elif kind == b"D":
            self.used = self.clock()
            item = self.conns.get(conn)
            if item is not None and not item.ended.is_set():
                # Within its credit there is always room (tunnel.py WINDOW):
                # more is the browser VM's fault, and costs the connection.
                with item.credit:
                    item.queued += len(payload)
                    over = item.queued > QUEUE_BYTES
                try:
                    if over:
                        raise queue.Full
                    item.outbound.put_nowait(payload)
                except queue.Full:
                    self._drop(item)
        elif kind == b"A" and len(payload) == 4:
            item = self.conns.get(conn)
            if item is not None:
                with item.credit:
                    item.inflight = max(0, item.inflight - struct.unpack(">I", payload)[0])
                    item.credit.notify_all()
        elif kind == b"C":
            item = self.conns.get(conn)
            if item is not None:
                item.peer_closed.set()
                try:
                    # After what it sent before: a request's last bytes still go.
                    item.outbound.put_nowait(None)
                except queue.Full:
                    self._drop(item)

    def _carry(self, item):
        """One of Chrome's connections, to its port of the workbench."""
        try:
            upstream = self.backend.open_port(self.workbench, item.port)
        except Exception as exc:
            logging.info("Agent tunnel port not reached category=%s", safe_exception(exc))
            if not item.peer_closed.is_set():
                self._send(b"D", item.conn, _nothing_there(item.port, isinstance(exc, agent_vm.PortClosed)))
            self._drop(item)
            return
        item.upstream = upstream
        if item.ended.is_set():
            self._close_upstream(item)
            return
        threading.Thread(target=self._back, args=(item, upstream), name="agent-tunnel-back", daemon=True).start()
        try:
            while True:
                data = item.outbound.get()
                if data is None or self.closing or item.ended.is_set():
                    break
                with item.credit:
                    item.queued -= len(data)
                upstream.send(data)
                # Gone on to the workbench: Chrome may send that much more.
                self._send(b"A", item.conn, struct.pack(">I", len(data)))
        except Exception as exc:
            logging.info("Agent tunnel upstream failed category=%s", safe_exception(exc))
        finally:
            # Ends _back's recv as well, which then tells the browser VM.
            self._close_upstream(item)

    def _back(self, item, upstream):
        """The workbench's answer for one connection, back to Chrome."""
        try:
            while not self.closing:
                data = upstream.recv(POLL_SECONDS)
                if data is None:
                    break
                for start in range(0, len(data), CHUNK):
                    if not self._wait_credit(item):
                        return
                    piece = data[start:start + CHUNK]
                    with item.credit:
                        item.inflight += len(piece)
                    self.used = self.clock()
                    self._send(b"D", item.conn, piece)
        except Exception as exc:
            logging.info("Agent tunnel downstream failed category=%s", safe_exception(exc))
        finally:
            self._drop(item)

    def _wait_credit(self, item):
        """Until Chrome took enough of what went before (A frames); False
        once the connection or the tunnel ends meanwhile."""
        with item.credit:
            while item.inflight >= WINDOW:
                if self.closing or item.ended.is_set():
                    return False
                item.credit.wait(POLL_SECONDS)
        return not (self.closing or item.ended.is_set())

    @staticmethod
    def _close_upstream(item):
        upstream = item.upstream
        if upstream is not None:
            try:
                upstream.close()
            except Exception:
                pass

    def _end(self, item):
        """The connection goes, whatever still waits for it: its threads stop."""
        item.ended.set()
        with item.credit:
            item.credit.notify_all()
        try:
            item.outbound.put_nowait(None)
        except queue.Full:
            pass
        self._close_upstream(item)

    def _drop(self, item):
        with self.lock:
            self.conns.pop(item.conn, None)
        self._end(item)
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
            self._end(item)
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
    elif not tunnel.started.wait(LISTEN_SECONDS) or not tunnel.live():
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
                found = [port for port in discover(tunnel.backend, uid) if port not in tunnel.ports]
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
