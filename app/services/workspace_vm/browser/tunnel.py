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
     D: bytes for that connection; C: close it.
  here -> server: O (payload the port): Chrome opened a connection; D, C.
A port this VM already uses itself (Chrome's debugging port, a service of
the provider) is taken, never listened on: the browser opens localhost only
where this program holds the port (agent_browser.check_url). It ends with
stdin (the server closed the tunnel).

Standard library only, so it runs before setup.sh installed anything.
"""
import os
import selectors
import socket
import struct
import sys

HEADER = struct.Struct(">cII")
CHUNK = 65536
# Chrome's debugging port (display.sh) and the ports below 1024, which the
# provider's user may not bind anyway.
RESERVED = {9222}
LOWEST_PORT = 1024


def frame(kind, conn, payload=b""):
    return HEADER.pack(kind, conn, len(payload)) + payload


class Tunnel:
    """``source`` is what the server's frames arrive on (stdin; a socket in
    the tests, where Windows selects sockets only), read with ``read``;
    ``write`` takes the frames for the server."""

    def __init__(self, source, read, write, hosts=("127.0.0.1", "::1")):
        self.read = read
        self.write = write
        self.hosts = hosts
        self.selector = selectors.DefaultSelector()
        self.selector.register(source, selectors.EVENT_READ, "stdin")
        self.buffer = b""
        self.listening = {}
        self.conns = {}
        # Closed by the server: the browser has its answer and our FIN, and
        # the socket goes once the browser closes too. Closing it at once
        # with the browser's bytes unread sent a reset, which could drop the
        # answer's end (seen in the tests on Windows).
        self.finishing = set()
        self.next_conn = 1

    def send(self, kind, conn, payload=b""):
        data = frame(kind, conn, payload)
        while data:
            data = data[self.write(data):]

    def listen(self, port):
        """Listens on ``port`` of loopback (IPv4 and, where the VM has it,
        IPv6); True when at least IPv4 holds it."""
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
                server.bind((host, port))
                server.listen(64)
            except OSError:
                server.close()
                if family == socket.AF_INET:
                    break
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
            client, _ = server.accept()
        except OSError:
            return
        client.setblocking(True)
        conn = self.next_conn
        self.next_conn += 1
        self.conns[conn] = client
        self.selector.register(client, selectors.EVENT_READ, ("conn", conn))
        self.send(b"O", conn, struct.pack(">H", port))

    def close(self, conn, tell=False):
        self.finishing.discard(conn)
        client = self.conns.pop(conn, None)
        if client is None:
            return
        try:
            self.selector.unregister(client)
        except (KeyError, ValueError):
            pass
        client.close()
        if tell:
            self.send(b"C", conn)

    def handle(self, kind, conn, payload):
        if kind == b"L" and len(payload) == 2:
            port = struct.unpack(">H", payload)[0]
            self.send(b"L", 0, payload + (b"\x01" if self.listen(port) else b"\x00"))
        elif kind == b"D":
            client = self.conns.get(conn)
            if client is None:
                return
            try:
                client.sendall(payload)
            except OSError:
                self.close(conn, tell=True)
        elif kind == b"C":
            client = self.conns.get(conn)
            if client is None or conn in self.finishing:
                return
            try:
                client.shutdown(socket.SHUT_WR)
            except OSError:
                self.close(conn)
                return
            self.finishing.add(conn)

    def read_stdin(self):
        try:
            data = self.read(CHUNK)
        except OSError:
            data = b""
        if not data:
            return False
        self.buffer += data
        while len(self.buffer) >= HEADER.size:
            kind, conn, length = HEADER.unpack_from(self.buffer)
            if len(self.buffer) < HEADER.size + length:
                break
            payload = self.buffer[HEADER.size:HEADER.size + length]
            self.buffer = self.buffer[HEADER.size + length:]
            self.handle(kind, conn, payload)
        return True

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

    def serve(self):
        while True:
            for key, _ in self.selector.select():
                what = key.data
                if what == "stdin":
                    if not self.read_stdin():
                        return
                elif what[0] == "listen":
                    self.accept(key.fileobj, what[1])
                else:
                    conn = what[1]
                    try:
                        data = key.fileobj.recv(CHUNK)
                    except OSError:
                        data = b""
                    if not data:
                        self.close(conn, tell=conn not in self.finishing)
                    elif conn not in self.finishing:
                        self.send(b"D", conn, data)


if __name__ == "__main__":
    try:
        Tunnel(sys.stdin, lambda size: os.read(0, size), lambda data: os.write(1, data)).run()
    except (BrokenPipeError, KeyboardInterrupt):
        pass
