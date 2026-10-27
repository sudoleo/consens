"""consens.io workspace: the live view's way into the VM (agent_workspace.py).

A service of the VM (started again whenever it wakes) on GATEWAY_PORT, the
port its private address leads to; only the provider's token opens that
address, and only consens.io's server holds it. One WebSocket path, /vnc:
the gateway sends text frames {"state": "setup"|"starting"|"ready"|"error"}
while it installs (setup.sh, once) and starts (display.sh) the browser, then
carries the VNC server's bytes both ways as binary frames.

Standard library only, so it runs before setup.sh installed anything.
"""
import asyncio
import base64
import hashlib
import json
import os
import struct
import subprocess

GATEWAY_PORT = 6080
VNC = ("127.0.0.1", 5900)
HERE = os.path.dirname(os.path.abspath(__file__))
MAGIC = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
MAX_FRAME = 4 * 1024 * 1024


async def read_frame(reader):
    """``(opcode, payload)`` of the client's next frame (always masked)."""
    head = await reader.readexactly(2)
    opcode, length = head[0] & 0x0F, head[1] & 0x7F
    if length == 126:
        length = struct.unpack("!H", await reader.readexactly(2))[0]
    elif length == 127:
        length = struct.unpack("!Q", await reader.readexactly(8))[0]
    if length > MAX_FRAME:
        raise ValueError("frame too large")
    mask = await reader.readexactly(4) if head[1] & 0x80 else b"\0\0\0\0"
    data = bytearray(await reader.readexactly(length))
    for index in range(length):
        data[index] ^= mask[index % 4]
    return opcode, bytes(data)


def frame(opcode, payload):
    length = len(payload)
    if length < 126:
        head = struct.pack("!BB", 0x80 | opcode, length)
    elif length < 65536:
        head = struct.pack("!BBH", 0x80 | opcode, 126, length)
    else:
        head = struct.pack("!BBQ", 0x80 | opcode, 127, length)
    return head + payload


async def send_state(writer, state):
    writer.write(frame(1, json.dumps({"state": state}).encode()))
    await writer.drain()


async def run(script):
    process = await asyncio.create_subprocess_exec("bash", os.path.join(HERE, script),
                                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return await process.wait() == 0


async def handle(reader, writer):
    try:
        request = (await reader.readuntil(b"\r\n\r\n")).decode("latin-1")
        lines = request.split("\r\n")
        path = lines[0].split(" ")[1] if len(lines[0].split(" ")) > 1 else ""
        headers = {key.strip().lower(): value.strip() for key, _, value in
                   (line.partition(":") for line in lines[1:] if ":" in line)}
        key = headers.get("sec-websocket-key")
        if path != "/vnc" or not key or "websocket" not in headers.get("upgrade", "").lower():
            writer.write(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
            await writer.drain()
            return
        accept = base64.b64encode(hashlib.sha1((key + MAGIC).encode()).digest()).decode()
        writer.write(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                      f"Sec-WebSocket-Accept: {accept}\r\n\r\n").encode())
        await writer.drain()
        if not os.path.exists(os.path.expanduser("~/.consens/workspace/setup-done-2")):
            await send_state(writer, "setup")
        if not await run("setup.sh"):
            await send_state(writer, "error")
            return
        await send_state(writer, "starting")
        if not await run("display.sh"):
            await send_state(writer, "error")
            return
        vnc_reader, vnc_writer = await asyncio.open_connection(*VNC)
        await send_state(writer, "ready")
    except (OSError, asyncio.IncompleteReadError, asyncio.LimitOverrunError, ValueError):
        writer.close()
        return

    async def upward():
        while True:
            opcode, payload = await read_frame(reader)
            if opcode == 8:
                return
            if opcode == 9:
                writer.write(frame(10, payload))
                await writer.drain()
            elif opcode in (0, 2):
                vnc_writer.write(payload)
                await vnc_writer.drain()

    async def downward():
        while True:
            data = await vnc_reader.read(65536)
            if not data:
                return
            writer.write(frame(2, data))
            await writer.drain()

    tasks = [asyncio.ensure_future(upward()), asyncio.ensure_future(downward())]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in tasks:
            task.cancel()
        for stream in (vnc_writer, writer):
            try:
                stream.close()
            except Exception:
                pass


async def main():
    server = await asyncio.start_server(handle, "0.0.0.0", GATEWAY_PORT)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
