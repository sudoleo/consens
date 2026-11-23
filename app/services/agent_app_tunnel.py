"""The server's end of the way to an app in the workspace
(workspace_vm/workbench/app_tunnel.py is the other, docs/agent-mode.md "App im
eigenen Browser").

One command per account on the provider's exec API carries every connection
of that account's app at once: its stdin and stdout hold frames (kind, 1
byte; connection, 4 bytes; length, 4 bytes; that many bytes), and each
connection is a ``Stream`` to one port on the workspace's loopback. The
provider's token goes to its API only, never to an address of the VM.

The command in the VM serves only while a background process of the agent
runs, whose time is counted (agent_vm_processes.py), and ends by itself once
none is left or nobody used it for a while; then the tunnel here is closed
and the next request opens a new one. What it carries counts for the
workspace's safety rules like the live view's bytes (workspace_guard.py):
neither shows in the VM's own network counters.
"""
from __future__ import annotations

import asyncio
import logging
import os
import struct
import time

from app.core.observability import safe_exception
from app.services import agent_vm

OPEN, DATA, END, CLOSE, PING = 1, 2, 3, 4, 5
HELLO, OPENED, REFUSED, BYE, PONG = 16, 17, 18, 19, 20
HEAD = struct.Struct(">BII")
CHUNK = 64 * 1024
MAX_FRAME = 1024 * 1024
TUNNEL = agent_vm.TOOLS_DIR + "/app_tunnel.py"
# The command's own limit in the VM: as long as a background process may run
# (agent_vm_processes.MAX_SECONDS), then the next request opens a new one.
TUNNEL_SECONDS = 60 * 60
UPSTREAM_OPEN_SECONDS = 30
HELLO_SECONDS = 20
OPEN_SECONDS = 15
# Frames of one connection waiting for the browser before the whole tunnel
# waits with them, and how long it does before that connection is given up:
# one tab that stopped reading must not hold the others.
BACKLOG = 128
STALLED_SECONDS = 20
GUARD_SECONDS = 30
# Bytes carried before they are handed to the safety rules.
METER_BYTES = 4 * 1024 * 1024
# Connections of one account's app at once (a page with many modules opens dozens).
MAX_STREAMS = 200


class Refused(Exception):
    """The workspace did not open the connection. ``reason``: "idle" (no
    background process runs, so nothing is served), "refused" (nothing
    listens on the port), "busy" (too many connections at once) or "closed"
    (the tunnel ended)."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


class Unavailable(Exception):
    """No tunnel: the workspace is closed by the safety rules ("guarded"),
    or its VM could not be reached ("vm")."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


class Stream:
    """One connection to the app: ``write``, ``end`` (nothing more to send),
    ``read`` (b"" once the app sent everything) and ``close``."""

    def __init__(self, tunnel, number):
        self.tunnel = tunnel
        self.number = number
        self.incoming: asyncio.Queue = asyncio.Queue(BACKLOG)
        self.opened: asyncio.Future = asyncio.get_running_loop().create_future()
        self.ended = False
        self.closed = False

    async def write(self, data):
        for start in range(0, len(data), CHUNK):
            await self.tunnel._send(DATA, self.number, data[start:start + CHUNK])

    async def end(self):
        await self.tunnel._send(END, self.number)

    async def read(self):
        """The next bytes, b"" at the app's end; ConnectionError when the
        connection broke off."""
        if self.ended:
            return b""
        item = await self.incoming.get()
        if item is None:
            self.ended = True
            return b""
        if isinstance(item, Exception):
            self.ended = True
            raise item
        return item

    async def close(self):
        if self.closed:
            return
        self.closed = True
        if self.tunnel._streams.pop(self.number, None) is not None and not self.tunnel.closed:
            try:
                await self.tunnel._send(CLOSE, self.number)
            except Exception:
                pass
        self.tunnel._touch()


class Tunnel:
    def __init__(self, uid, upstream):
        self.uid = uid
        self.upstream = upstream
        self.closed = False
        self.reason = ""
        self._streams: dict[int, Stream] = {}
        self._next = 1
        self._hello: asyncio.Future = asyncio.get_running_loop().create_future()
        self._send_lock = asyncio.Lock()
        self._carried = 0
        self._tasks = [asyncio.ensure_future(self._read()), asyncio.ensure_future(self._guarded())]
        self.used = time.monotonic()

    def _touch(self):
        self.used = time.monotonic()

    def _count(self, size):
        from app.services import workspace_guard
        self._carried += size
        if self._carried >= METER_BYTES:
            workspace_guard.note_view_bytes(self.uid, self._carried)
            self._carried = 0

    async def _send(self, kind, number, payload=b""):
        if self.closed:
            raise ConnectionError("The tunnel is closed.")
        self._count(len(payload))
        async with self._send_lock:
            # stdin of the command in the VM: exec frames 0x00.
            await self.upstream.send(b"\x00" + HEAD.pack(kind, number, len(payload)) + payload)

    async def open(self, port):
        if self.closed:
            raise Refused("closed")
        if len(self._streams) >= MAX_STREAMS:
            raise Refused("busy")
        number = self._next
        self._next = self._next % 0xFFFFFFFF + 1
        stream = self._streams[number] = Stream(self, number)
        self._touch()
        try:
            await self._send(OPEN, number, struct.pack(">H", port))
            await asyncio.wait_for(asyncio.shield(stream.opened), OPEN_SECONDS)
        except Refused:
            self._streams.pop(number, None)
            raise
        except (asyncio.TimeoutError, ConnectionError):
            await stream.close()
            raise Refused("closed") from None
        return stream

    async def _deliver(self, stream, item):
        """``item`` for the connection's reader. A reader that takes nothing
        for STALLED_SECONDS loses its connection instead of holding all."""
        try:
            await asyncio.wait_for(stream.incoming.put(item), STALLED_SECONDS)
        except asyncio.TimeoutError:
            self._streams.pop(stream.number, None)
            stream.closed = True
            # Its reader finds the break once it reads on.
            while not stream.incoming.empty():
                stream.incoming.get_nowait()
            stream.incoming.put_nowait(ConnectionError("The connection stalled."))
            try:
                await self._send(CLOSE, stream.number)
            except Exception:
                pass

    async def _frame(self, kind, number, payload):
        if kind == HELLO:
            if not self._hello.done():
                self._hello.set_result(True)
            return
        if kind == BYE:
            self.reason = payload.decode("ascii", "replace")[:20]
            if self.reason == "idle":
                _idle.add(self.uid)
            raise ConnectionAbortedError
        if kind == REFUSED and payload == b"idle":
            _idle.add(self.uid)
        stream = self._streams.get(number)
        if stream is None:
            return
        if kind == OPENED:
            if not stream.opened.done():
                stream.opened.set_result(True)
        elif kind == REFUSED:
            self._streams.pop(number, None)
            if not stream.opened.done():
                stream.opened.set_exception(Refused(payload.decode("ascii", "replace")[:20] or "refused"))
        elif kind == DATA:
            self._count(len(payload))
            await self._deliver(stream, payload)
        elif kind == END:
            self._streams.pop(number, None)
            self._touch()
            await self._deliver(stream, None)
        elif kind == CLOSE:
            self._streams.pop(number, None)
            self._touch()
            await self._deliver(stream, ConnectionError("The app closed the connection."))

    async def _read(self):
        """stdout of the command (exec frames 0x01) is the tunnel's frames;
        its exit (0x03) or the socket's end closes the tunnel."""
        pending = bytearray()
        try:
            async for message in self.upstream:
                if not isinstance(message, bytes) or not message:
                    continue
                if message[0] == 3:
                    break
                if message[0] != 1:
                    continue
                pending += message[1:]
                while len(pending) >= HEAD.size:
                    kind, number, length = HEAD.unpack_from(pending)
                    if length > MAX_FRAME:
                        raise ValueError("frame too long")
                    if len(pending) < HEAD.size + length:
                        break
                    payload = bytes(pending[HEAD.size:HEAD.size + length])
                    del pending[:HEAD.size + length]
                    await self._frame(kind, number, payload)
        except ConnectionAbortedError:
            pass
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logging.info("Agent app tunnel ended category=%s", safe_exception(exc))
        await self.close()

    async def _guarded(self):
        """A workspace the safety rules closed carries no app either."""
        from app.services import workspace_guard
        while True:
            await asyncio.sleep(GUARD_SECONDS)
            try:
                found = await asyncio.to_thread(workspace_guard.status, self.uid)
            except Exception as exc:
                logging.info("Agent app tunnel guard check failed category=%s", safe_exception(exc))
                continue
            if found.closed:
                self.reason = "guarded"
                await self.close()
                return

    async def ready(self):
        try:
            await asyncio.wait_for(asyncio.shield(self._hello), HELLO_SECONDS)
        except (asyncio.TimeoutError, ConnectionError):
            await self.close()
            raise Unavailable("vm") from None

    async def close(self):
        if self.closed:
            return
        self.closed = True
        from app.services import workspace_guard
        workspace_guard.note_view_bytes(self.uid, self._carried)
        self._carried = 0
        if _tunnels.get(self.uid) is self:
            _tunnels.pop(self.uid, None)
        gone = ConnectionError("The tunnel is closed.")
        if not self._hello.done():
            self._hello.set_exception(gone)
            self._hello.exception()
        for stream in list(self._streams.values()):
            if not stream.opened.done():
                stream.opened.set_exception(Refused("closed"))
                stream.opened.exception()
            try:
                stream.incoming.put_nowait(gone)
            except asyncio.QueueFull:
                stream.incoming.get_nowait()
                stream.incoming.put_nowait(gone)
        self._streams.clear()
        current = asyncio.current_task()
        for task in self._tasks:
            if task is not current:
                task.cancel()
        try:
            # Its stdin's end (0x04) ends the command in the VM.
            await self.upstream.send(b"\x04")
        except Exception:
            pass
        try:
            await self.upstream.close()
        except Exception:
            pass
        logging.info("Agent app tunnel closed reason=%s", self.reason or "ended")


_tunnels: dict[str, Tunnel] = {}
_opening: dict[str, asyncio.Lock] = {}
# Accounts whose workspace said that no background process runs: their app
# is answered from here, without waking the VM again, until the app is
# opened anew from the chat (expect, after routers/agent_workspace.py found
# a running process). A tab left open on an app that ended asks again and
# again, and each tunnel it opened would hold the VM awake uncounted.
_idle: set[str] = set()


def expect(uid):
    """The account's app runs again: its next request opens the tunnel."""
    _idle.discard(uid)


async def connect_upstream(url):
    """The command's exec WebSocket with the provider's token, which goes to
    the provider's API only (tests replace it)."""
    from websockets.asyncio.client import connect
    if not url.startswith("wss://" + agent_vm.SPRITES_API.split("://", 1)[1] + "/"):
        raise ValueError("The tunnel connects to the provider's API only.")
    return await connect(url, additional_headers={"Authorization": f"Bearer {os.getenv('SPRITES_TOKEN', '').strip()}"},
                         open_timeout=UPSTREAM_OPEN_SECONDS, max_size=8 * 1024 * 1024, ping_interval=20,
                         ping_timeout=40, close_timeout=2)


def exec_url(uid):
    """The workspace awake with its tools up to date, and the exec address
    of its tunnel command there (blocking: the provider's API)."""
    from app.core.security import db_firestore
    from app.services import agent_workspace
    vm = agent_vm.backend()
    if vm is None:
        raise agent_vm.VMUnavailable("no provider configured")
    try:
        name = agent_workspace.open_workspace(vm, uid, db=db_firestore)
        argv = agent_vm.wrapped_command(f"exec python3 {TUNNEL}", TUNNEL_SECONDS, False)
        return vm.exec_url(name, argv, cwd=agent_vm.SERVER_HOME, stdin=True)
    finally:
        vm.close()


async def tunnel_for(uid):
    """The account's tunnel, opened where none is: Unavailable when the
    safety rules closed the workspace or its VM does not answer."""
    from app.services import workspace_guard
    found = _tunnels.get(uid)
    if found is not None and not found.closed:
        return found
    if uid in _idle:
        raise Refused("idle")
    lock = _opening.setdefault(uid, asyncio.Lock())
    async with lock:
        found = _tunnels.get(uid)
        if found is not None and not found.closed:
            return found
        guard = await asyncio.to_thread(workspace_guard.status, uid)
        if guard.closed:
            raise Unavailable("guarded")
        try:
            url = await asyncio.to_thread(exec_url, uid)
            upstream = await connect_upstream(url)
        except Exception as exc:
            logging.warning("Agent app tunnel unavailable category=%s", safe_exception(exc))
            agent_vm.lose_contact(agent_vm.workspace_name(uid))
            raise Unavailable("vm") from None
        tunnel = Tunnel(uid, upstream)
        await tunnel.ready()
        _tunnels[uid] = tunnel
        return tunnel


async def close_all():
    for tunnel in list(_tunnels.values()):
        await tunnel.close()
