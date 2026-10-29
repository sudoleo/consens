"""consens.io: localhost in the shared browser reaches the agent's
workbench (agent_tunnel.py, since 2026-10-29). Runs on both VMs.

The browser has a VM of its own so that nothing of the agent runs next to
its sign-ins (security audit 2026-10-27, finding 2). A page the agent serves
on its workbench (a dev server, an app it builds for the user) still belongs
in the browser the user sees: http://localhost:3000 there is port 3000 of
the workbench. The way goes one direction only:

  listen (browser VM, as the provider's user): listens on 127.0.0.1 and ::1
     for the ports the server names and hands every connection Chrome opens
     to the server;
  connect (workbench, as the agent's user through agent-run, installed
     where that user reads it by setup.sh): opens each such connection to
     that port of its own localhost, 127.0.0.1 or else ::1, and tells the
     server which ports the agent's servers listen on.

The server carries frames between the two (agent_tunnel.Tunnel): nothing on
the workbench reaches the browser VM, and the server opens connections only
for the browser's side. Until the first live probe (2026-10-29) the
workbench's side was the provider's proxy API: it never passed on that a
server closed a connection, reached no server on ::1 alone, and took
220 ms for each new connection.

The server runs this over the provider's exec API, and both talk in frames
on stdin and stdout: kind (1 byte), connection (4 bytes), length (4 bytes),
payload.
  L (listen; conn 0, payload the port, 2 bytes): listen on it; the answer is
     L with the port and 1 (listening) or 0 (taken, or refused).
  O (payload the port): a connection; from listen when Chrome opened one,
     to connect to open it.
  F (connect): the connection could not be opened (nothing listens there).
  Q (connect; conn 0): which ports the agent's user listens on; the answer
     is Q with them, 2 bytes each (/proc/net/tcp and tcp6, LISTEN, its uid).
  D: bytes of the connection; C: it closed (the other side finishes what
     waits for it, sends its FIN, and closes once its peer closes too).
  H (conn 0, payload the mode): sent once at the start, when it runs.
  A (payload 4 bytes): that many bytes of the connection were taken (sent
     on to Chrome or to the server). Neither side sends more than WINDOW
     bytes of a connection ahead of its A frames, so a connection whose
     reader stops (a paused video) holds only its own bytes, never the
     others'.
A port the browser VM already uses itself (Chrome's debugging port, a
service of the provider) is taken, never listened on: the browser opens
localhost only where this program holds the port (agent_browser.check_url).
It ends with stdin (the server closed the tunnel).

One tunnel per VM and mode: at its start it ends any other one (end_others;
during a deploy the old server's tunnel held the ports). At most
MAX_CONNECTIONS connections at once. Nothing here ever blocks: sockets and
stdout are written as far as they take, the rest waits in buffers that the
credit keeps small.

Standard library only, so it runs before setup.sh installed anything.
"""
import errno
import os
import selectors
import signal
import socket
import struct
import sys
import time

HEADER = struct.Struct(">cII")
CHUNK = 65536
# Chrome's debugging port (display.sh) and the ports below 1024, which the
# provider's user may not bind anyway.
RESERVED = {9222}
LOWEST_PORT = 1024
# agent_tunnel says the same: connections at once, the bytes of one in
# flight each way before the other side took them, and the largest frame.
MAX_CONNECTIONS = 64
WINDOW = 512 * 1024
MAX_FRAME = CHUNK + 64
END_SECONDS = 3
CONNECT_SECONDS = 3
MODES = ("listen", "connect")


def end_others(mode, proc="/proc", me=None, kill=os.kill, wait=time.sleep):
    """Ends the other tunnels of this VM in ``mode``: Python processes that
    run this file with it (python3 <this file> <mode>), SIGTERM first,
    SIGKILL after END_SECONDS. Never the programs that started this one:
    ``timeout python3 tunnel.py connect`` (agent-run) has the same
    arguments after its own, and the first live probe's connector ended
    its own timeout, and with it itself (2026-10-29)."""
    me = os.getpid() if me is None else me
    path = os.fsencode(os.path.abspath(__file__))
    try:
        names = os.listdir(proc)
    except OSError:
        return []
    others = []
    for name in names:
        if not name.isdigit() or int(name) == me:
            continue
        try:
            with open(os.path.join(proc, name, "cmdline"), "rb") as handle:
                argv = handle.read().split(b"\0")
        except OSError:
            continue
        if (len(argv) >= 3 and os.path.basename(argv[0]).startswith(b"python") and argv[1] == path
                and argv[2] == mode.encode()):
            others.append(int(name))
    for pid in others:
        try:
            kill(pid, signal.SIGTERM)
        except OSError:
            pass
    deadline = time.time() + END_SECONDS
    alive = others
    while alive and time.time() < deadline:
        wait(0.05)
        alive = [pid for pid in alive if os.path.exists(os.path.join(proc, str(pid)))]
    for pid in alive:
        try:
            kill(pid, getattr(signal, "SIGKILL", signal.SIGTERM))
        except OSError:
            pass
    return others


def listening_ports(text, uid):
    """The ports ``uid`` listens on, from /proc/net/tcp and tcp6 (state 0A),
    that the tunnel takes; never another user's (the provider's services)."""
    ports = set()
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 8 or parts[3] != "0A" or ":" not in parts[1]:
            continue
        try:
            port, owner = int(parts[1].rsplit(":", 1)[1], 16), int(parts[7])
        except ValueError:
            continue
        if owner == uid and port >= LOWEST_PORT and port not in RESERVED:
            ports.add(port)
    return sorted(ports)


def own_ports():
    text = ""
    for name in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            with open(name, encoding="ascii", errors="replace") as handle:
                text += handle.read()
        except OSError:
            pass
    return listening_ports(text, os.getuid())


def local_addresses(port):
    """Where connect opens ``port``: 127.0.0.1, else ::1 (a dev server on
    "localhost" may listen on either)."""
    return [(socket.AF_INET, ("127.0.0.1", port)), (socket.AF_INET6, ("::1", port))]


def frame(kind, conn, payload=b""):
    return HEADER.pack(kind, conn, len(payload)) + payload


class _Client:
    """One connection, to Chrome or to the agent's server: ``out`` waits to
    be written to it, ``unacked`` bytes of it the other side has not taken
    yet; ``finishing`` once the other side closed it (FIN after ``out``),
    ``shut`` once the FIN went."""

    def __init__(self, sock, port):
        self.sock = sock
        self.port = port
        self.out = bytearray()
        self.unacked = 0
        self.finishing = False
        self.shut = False
        self.events = 0


class Tunnel:
    """``source`` is what the server's frames arrive on (stdin) and ``sink``
    where this program's go (stdout), read with ``read`` and written with
    ``write`` (a socket for both in the tests, where Windows selects sockets
    only). ``addresses`` and ``ports`` are connect's way to a port and its
    answer to Q (the tests give their own)."""

    def __init__(self, source, read, write, sink=None, hosts=("127.0.0.1", "::1"), mode="listen",
                 addresses=local_addresses, ports=own_ports):
        if mode not in MODES:
            raise ValueError(mode)
        self.mode = mode
        self.read = read
        self.write = write
        self.hosts = hosts
        self.addresses = addresses
        self.ports = ports
        self.source = source
        self.sink = source if sink is None else sink
        self.selector = selectors.DefaultSelector()
        self.pending = bytearray()
        self.stdio = {}
        self._watch_stdio()
        self.buffer = bytearray()
        self.listening = {}
        self.conns = {}
        self.next_conn = 1

    # --- The server's side ------------------------------------------------------

    def _watch_stdio(self):
        """stdin always for reading, stdout for writing while frames wait."""
        wanted = {self.source: selectors.EVENT_READ}
        wanted[self.sink] = wanted.get(self.sink, 0) | (selectors.EVENT_WRITE if self.pending else 0)
        for fileobj, events in wanted.items():
            if self.stdio.get(fileobj) == events:
                continue
            if fileobj in self.stdio and events:
                self.selector.modify(fileobj, events, "stdio")
            elif fileobj in self.stdio:
                self.selector.unregister(fileobj)
            elif events:
                self.selector.register(fileobj, events, "stdio")
            if events:
                self.stdio[fileobj] = events
            else:
                self.stdio.pop(fileobj, None)

    def send(self, kind, conn, payload=b""):
        self.pending += frame(kind, conn, payload)
        self.flush()

    def flush(self):
        while self.pending:
            try:
                written = self.write(bytes(self.pending[:CHUNK * 4]))
            except (BlockingIOError, InterruptedError):
                break
            if not written:
                break
            del self.pending[:written]
        self._watch_stdio()

    def read_stdin(self):
        try:
            data = self.read(CHUNK)
        except (BlockingIOError, InterruptedError):
            return True
        except OSError:
            data = b""
        if not data:
            return False
        self.buffer += data
        while len(self.buffer) >= HEADER.size:
            kind, conn, length = HEADER.unpack_from(self.buffer)
            if length > MAX_FRAME:
                return False
            if len(self.buffer) < HEADER.size + length:
                break
            payload = bytes(self.buffer[HEADER.size:HEADER.size + length])
            del self.buffer[:HEADER.size + length]
            self.handle(kind, conn, payload)
        return True

    def handle(self, kind, conn, payload):
        if self.mode == "listen" and kind == b"L" and len(payload) == 2:
            port = struct.unpack(">H", payload)[0]
            self.send(b"L", 0, payload + (b"\x01" if self.listen(port) else b"\x00"))
            return
        if self.mode == "connect" and kind == b"Q":
            self.send(b"Q", 0, b"".join(struct.pack(">H", port) for port in self.ports()[:64]))
            return
        if self.mode == "connect" and kind == b"O" and len(payload) == 2:
            self.open(conn, struct.unpack(">H", payload)[0])
            return
        client = self.conns.get(conn)
        if client is None:
            return
        if kind == b"D":
            if len(client.out) + len(payload) > WINDOW + CHUNK:
                # More than its credit: the other side is wrong, the connection goes.
                self.close(conn, tell=True)
                return
            client.out += payload
            self._write(conn)
        elif kind == b"A" and len(payload) == 4:
            client.unacked = max(0, client.unacked - struct.unpack(">I", payload)[0])
            self._interest(conn)
        elif kind == b"C":
            client.finishing = True
            self._write(conn)

    # --- Chrome's side (listen) ---------------------------------------------------

    def listen(self, port):
        """Listens on ``port`` of loopback, IPv4 and IPv6 where the VM has
        it; False when the port is in use on either (Chrome's localhost
        reaches both, so a service of this VM on ::1 would answer)."""
        if port in self.listening:
            return True
        if port in RESERVED or port < LOWEST_PORT:
            return False
        sockets = []
        for host in self.hosts:
            family = socket.AF_INET6 if ":" in host else socket.AF_INET
            try:
                server = socket.socket(family, socket.SOCK_STREAM)
            except OSError:
                continue
            try:
                if family == socket.AF_INET6:
                    server.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
                if os.name != "nt":
                    # Linux: the port again while the last tunnel's
                    # connections still wait out TIME_WAIT (a restart of
                    # the tunnel found it "taken", CI 2026-10-29). Windows'
                    # SO_REUSEADDR would also take a port in use.
                    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server.bind((host, port))
                server.listen(64)
            except OSError as exc:
                server.close()
                if family == socket.AF_INET or exc.errno == errno.EADDRINUSE:
                    for held in sockets:
                        held.close()
                    return False
                # No IPv6 loopback on this VM: IPv4 alone.
                continue
            sockets.append(server)
        if not sockets or sockets[0].family != socket.AF_INET:
            for server in sockets:
                server.close()
            return False
        for server in sockets:
            server.setblocking(False)
            self.selector.register(server, selectors.EVENT_READ, ("listen", port))
        self.listening[port] = sockets
        return True

    def accept(self, server, port):
        try:
            sock, _ = server.accept()
        except OSError:
            return
        if len(self.conns) >= MAX_CONNECTIONS:
            sock.close()
            return
        conn = self.next_conn
        self.next_conn += 1
        self._adopt(conn, sock, port)
        self.send(b"O", conn, struct.pack(">H", port))

    # --- The agent's server's side (connect) --------------------------------------

    def open(self, conn, port):
        """Opens ``port`` of this VM's localhost for connection ``conn``, or
        says F: a connect to loopback answers at once, refused or taken."""
        if conn in self.conns or len(self.conns) >= MAX_CONNECTIONS or port < LOWEST_PORT or port in RESERVED:
            self.send(b"F", conn)
            return
        for family, address in self.addresses(port):
            try:
                sock = socket.socket(family, socket.SOCK_STREAM)
            except OSError:
                continue
            sock.settimeout(CONNECT_SECONDS)
            try:
                sock.connect(address)
            except OSError:
                sock.close()
                continue
            self._adopt(conn, sock, port)
            return
        self.send(b"F", conn)

    # --- Both -------------------------------------------------------------------

    def _adopt(self, conn, sock, port):
        sock.setblocking(False)
        try:
            # Small writes (a request line, a key press over a WebSocket) go at once.
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError:
            pass
        self.conns[conn] = _Client(sock, port)
        self._interest(conn)

    def _interest(self, conn):
        """Read while the connection has credit (and after the FIN, to see
        its peer close it), write while something waits for it."""
        client = self.conns.get(conn)
        if client is None:
            return
        events = 0
        if client.unacked < WINDOW or client.finishing:
            events |= selectors.EVENT_READ
        if client.out:
            events |= selectors.EVENT_WRITE
        if events == client.events:
            return
        if client.events and events:
            self.selector.modify(client.sock, events, ("conn", conn))
        elif client.events:
            self.selector.unregister(client.sock)
        else:
            self.selector.register(client.sock, events, ("conn", conn))
        client.events = events

    def _read(self, conn):
        client = self.conns.get(conn)
        if client is None:
            return
        try:
            data = client.sock.recv(CHUNK)
        except (BlockingIOError, InterruptedError):
            return
        except OSError:
            data = b""
        if not data:
            self.close(conn, tell=not client.finishing)
        elif not client.finishing:
            client.unacked += len(data)
            self.send(b"D", conn, data)
            self._interest(conn)

    def _write(self, conn):
        client = self.conns.get(conn)
        if client is None:
            return
        written = 0
        while client.out:
            try:
                sent = client.sock.send(bytes(client.out[:CHUNK * 4]))
            except (BlockingIOError, InterruptedError):
                break
            except OSError:
                self.close(conn, tell=True)
                return
            if not sent:
                break
            del client.out[:sent]
            written += sent
        if written:
            # Taken: the other side may send that much more.
            self.send(b"A", conn, struct.pack(">I", written))
        if client.finishing and not client.out and not client.shut:
            try:
                client.sock.shutdown(socket.SHUT_WR)
            except OSError:
                self.close(conn)
                return
            client.shut = True
        self._interest(conn)

    def close(self, conn, tell=False):
        client = self.conns.pop(conn, None)
        if client is None:
            return
        if client.events:
            try:
                self.selector.unregister(client.sock)
            except (KeyError, ValueError):
                pass
        client.sock.close()
        if tell:
            self.send(b"C", conn)

    def run(self):
        self.send(b"H", 0, self.mode.encode())
        try:
            self.serve()
        finally:
            for conn in list(self.conns):
                self.close(conn)
            for sockets in self.listening.values():
                for server in sockets:
                    server.close()
            self.listening.clear()
            # What still waits for the server, as far as it takes it now.
            try:
                self.flush()
            except OSError:
                pass

    def serve(self):
        while True:
            for key, events in self.selector.select():
                what = key.data
                if what == "stdio":
                    if events & selectors.EVENT_WRITE:
                        self.flush()
                    if events & selectors.EVENT_READ and key.fileobj is self.source and not self.read_stdin():
                        return
                elif what[0] == "listen":
                    self.accept(key.fileobj, what[1])
                else:
                    if events & selectors.EVENT_WRITE:
                        self._write(what[1])
                    if events & selectors.EVENT_READ:
                        self._read(what[1])


if __name__ == "__main__":
    MODE = sys.argv[1] if len(sys.argv) > 1 else ""
    if MODE not in MODES:
        sys.exit("usage: tunnel.py listen|connect")
    end_others(MODE)
    os.set_blocking(1, False)
    try:
        Tunnel(sys.stdin, lambda size: os.read(0, size), lambda data: os.write(1, data), sink=sys.stdout,
               mode=MODE).run()
    except (BrokenPipeError, KeyboardInterrupt):
        pass
