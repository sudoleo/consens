"""consens.io browser VM: localhost in the shared browser reaches the
agent's workbench (agent_tunnel.py, since 2026-10-29).

The browser has a VM of its own so that nothing of the agent runs next to
its sign-ins (security audit 2026-10-27, finding 2). A page the agent serves
on its workbench (a dev server, an app it builds for the user) still belongs
in the browser the user sees: http://localhost:3000 here is port 3000 there.
The way goes one direction only. This program listens on 127.0.0.1 and ::1
of the browser VM for the ports the server names and hands every connection
Chrome opens to the server, which carries it to that port of the workbench
over the provider's proxy API. Nothing on the workbench ever reaches this VM.

The server runs this over the provider's exec API like relay.py, and both
talk in frames on stdin and stdout: kind (1 byte), connection (4 bytes),
length (4 bytes), payload.
  server -> here: L (conn 0, payload the port, 2 bytes): listen on it, the
     answer is L with the port and 1 (listening) or 0 (taken, or refused);
     D: bytes for that connection; C: close it (after what waits for it).
  here -> server: O (payload the port): Chrome opened a connection; D, C.
  both ways: A (payload 4 bytes): that many bytes of the connection were
     taken (written to Chrome, or sent on to the workbench). Neither side
     sends more than WINDOW bytes of a connection ahead of its A frames, so
     a connection whose reader stops holds only its own bytes, never the
     others'.
A port this VM already uses itself (Chrome's debugging port, a service of
the provider) is taken, never listened on: the browser opens localhost only
where this program holds the port (agent_browser.check_url). It ends with
stdin (the server closed the tunnel).

One tunnel per browser VM: at its start it ends any other one still
running (end_others). During a deploy the old server's tunnel held the
ports, and the new server's found them taken. At most MAX_CONNECTIONS of
Chrome's connections at once; one more is closed at once, so a page that
opens connections in a loop never piles up threads on the server.

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


def end_others(proc="/proc", me=None, kill=os.kill, wait=time.sleep):
    """Ends the other tunnels of this VM: processes that run this file (its
    path is one of their arguments, never inside a shell's command line),
    SIGTERM first, SIGKILL after END_SECONDS."""
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
        if path in argv:
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


def frame(kind, conn, payload=b""):
    return HEADER.pack(kind, conn, len(payload)) + payload


class _Client:
    """One of Chrome's connections: ``out`` waits to be written to it,
    ``unacked`` bytes of it the server has not taken yet; ``finishing`` once
    the server closed it (FIN after ``out``), ``shut`` once the FIN went."""

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
    only). Nothing here ever blocks: Chrome's sockets and the sink are
    written as far as they take, the rest waits in buffers, and each
    connection's credit (WINDOW) keeps those buffers small. A page that
    stops reading (a paused video) stops only its own connection."""

    def __init__(self, source, read, write, sink=None, hosts=("127.0.0.1", "::1")):
        self.read = read
        self.write = write
        self.hosts = hosts
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
        if kind == b"L" and len(payload) == 2:
            port = struct.unpack(">H", payload)[0]
            self.send(b"L", 0, payload + (b"\x01" if self.listen(port) else b"\x00"))
            return
        client = self.conns.get(conn)
        if client is None:
            return
        if kind == b"D":
            if len(client.out) + len(payload) > WINDOW + CHUNK:
                # More than its credit: the server is wrong, the connection goes.
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

    # --- Chrome's side ----------------------------------------------------------

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
        sock.setblocking(False)
        try:
            # Small writes (a request line, a key press over a WebSocket) go at once.
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError:
            pass
        conn = self.next_conn
        self.next_conn += 1
        self.conns[conn] = _Client(sock, port)
        self._interest(conn)
        self.send(b"O", conn, struct.pack(">H", port))

    def _interest(self, conn):
        """Read while the connection has credit (and after the FIN, to see
        Chrome close it), write while something waits for it."""
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
            # Taken by Chrome: the server may send that much more.
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
    end_others()
    os.set_blocking(1, False)
    try:
        Tunnel(sys.stdin, lambda size: os.read(0, size), lambda data: os.write(1, data), sink=sys.stdout).run()
    except (BrokenPipeError, KeyboardInterrupt):
        pass
