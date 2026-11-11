"""ASGI request-body limits applied before framework JSON/form parsing."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import os
import re
import threading


# Ceiling for every route (MAX_REQUEST_BODY_BYTES), reached only by uploads.
DEFAULT_MAX_REQUEST_BODY_BYTES = 16 * 1024 * 1024
# Every other route. The body is buffered and parsed before authentication
# and rate limits: a hostile 16 MB JSON body cost about a second of CPU and
# 380 MB of memory on any route.
SMALL_REQUEST_BODY_BYTES = 1024 * 1024
# The routes that need more: the real uploads, files as base64 inside JSON
# (/ask_* two files of at most 5 MB, 14 MB as base64, before the server
# shrinks an image the browser could not; an Agent upload one file of at most
# 7,000,000 base64 characters), and a saved chat (its sources are bounded
# only by the Firestore document, at most 1 MiB).
LARGE_ROUTE_MAX_REQUEST_BODY_BYTES = (
    (re.compile(r"/ask_[a-z0-9_]+"), 15 * 1024 * 1024),
    (re.compile(r"/agent/chats/[^/]+/files"), 8 * 1024 * 1024),
    (re.compile(r"/bookmark"), 2 * 1024 * 1024),
)
# Routes whose largest valid body is far smaller still. A hostile body there
# could make validation expensive (one error per key), so it is refused early.
# The settings PATCH is at most ~64 KB (a 32 KB system prompt, fully escaped);
# a Telegram update is a few KB and arrives before its secret is checked.
PATH_MAX_REQUEST_BODY_BYTES = {
    "/api/my/settings": 256 * 1024,
    "/api/telegram/webhook": 64 * 1024,
    "/api/client-errors": 64 * 1024,
}


# A body above the small limit is a big one: only the routes above take it.
# It stays in memory for as long as its request runs (an /ask_* answer streams
# for a minute), and it is buffered before anyone has shown a login. So only
# so many are in flight at once. One Compare message with files is six of
# them (config.MAX_RUN_FAMILIES); the rest is room for a second person.
BIG_BODIES_IN_FLIGHT = 12
BIG_BODIES_PER_CLIENT = 8
# How long a big body may take to arrive: 14 MB over a weak mobile link, and
# no longer, or a client that sends nothing would keep its place forever.
BIG_BODY_SECONDS = 180
# The values a JSON body may hold (every "," "[" and "{" outside its strings).
# The size limit does not bound the work of parsing: a megabyte of "[],[],"
# is 700,000 lists, a quarter of a second and 24 MB, on any route and before
# any login; 15 MB of it took 2.8 s and 353 MB. A real body is a few fields
# and long strings: a saved chat with thousands of sources stays far below.
MAX_JSON_ELEMENTS = 50_000
# From this size on the count runs beside the event loop.
_COUNT_IN_THREAD_BYTES = 256 * 1024

# One body at a time is read without its escapes: that takes two copies of it
# for a moment.
_unescaping = threading.Lock()


def json_elements_within(body, budget: int = MAX_JSON_ELEMENTS) -> bool:
    """Whether a JSON body holds at most ``budget`` values, without parsing it.

    Linear in the body and at the speed of bytes.find, count and replace: the
    text between two strings is counted, a string is skipped whole. A pattern
    that walks a string escape by escape took 1.8 s for 15 MB of them. A body
    that is no JSON at all is the parser's to refuse; it does so at the first
    wrong byte, having built only what was counted here.
    """
    if len(body) <= budget:
        return True
    if body.find(b"\\") < 0:
        return _elements_within(body, budget)
    # Inside a string a backslash escapes the byte after it. Without the
    # escaped backslashes, and then without the escaped quotes, every quote
    # that is left opens or closes a string.
    with _unescaping:
        return _elements_within(body.replace(b"\\\\", b"").replace(b'\\"', b""), budget)


def _elements_within(body, budget: int) -> bool:
    size = len(body)
    elements = strings = position = 0
    while True:
        quote = body.find(b'"', position)
        end = size if quote < 0 else quote
        elements += (body.count(b",", position, end) + body.count(b"[", position, end)
                     + body.count(b"{", position, end))
        if elements > budget:
            return False
        if quote < 0:
            return True
        # Every string is a key or a value: within the budget there are at
        # most two per element. More of them is no body of ours either.
        strings += 1
        if strings > 2 * budget + 2:
            return False
        close = body.find(b'"', quote + 1)
        if close < 0:
            return True
        position = close + 1


def client_of(headers: dict, client) -> str:
    """Whose request this is, for the places of big bodies: the address
    Cloudflare saw (rate_limit.client_ip_key says why only that header), an
    IPv6 address by its /64, which is what one customer gets."""
    raw = (headers.get(b"cf-connecting-ip") or b"").decode("latin-1").strip()
    if not raw:
        raw = (headers.get(b"x-forwarded-for") or b"").decode("latin-1").split(",", 1)[0].strip()
    if not raw and client:
        raw = str(client[0])
    try:
        address = ipaddress.ip_address(raw)
    except ValueError:
        return raw or "unknown"
    if address.version == 4:
        return str(address)
    if address.ipv4_mapped is not None:
        return str(address.ipv4_mapped)
    return str(ipaddress.ip_network(f"{address}/64", strict=False).network_address)


class BigBodies:
    """The places of big bodies in flight, counted on the event loop."""

    def __init__(self, total: int = BIG_BODIES_IN_FLIGHT, per_client: int = BIG_BODIES_PER_CLIENT):
        self.total = total
        self.per_client = per_client
        self.held: dict[str, int] = {}

    def take(self, client: str) -> bool:
        if sum(self.held.values()) >= self.total or self.held.get(client, 0) >= self.per_client:
            return False
        self.held[client] = self.held.get(client, 0) + 1
        return True

    def give(self, client: str) -> None:
        left = self.held.get(client, 0) - 1
        if left > 0:
            self.held[client] = left
        else:
            self.held.pop(client, None)


big_bodies = BigBodies()


def route_max_request_body_bytes(path: str) -> int:
    """The body limit of one route, before the configured ceiling."""
    if path in PATH_MAX_REQUEST_BODY_BYTES:
        return PATH_MAX_REQUEST_BODY_BYTES[path]
    for pattern, limit in LARGE_ROUTE_MAX_REQUEST_BODY_BYTES:
        if pattern.fullmatch(path):
            return limit
    return SMALL_REQUEST_BODY_BYTES


def configured_max_request_body_bytes() -> int:
    raw = os.environ.get("MAX_REQUEST_BODY_BYTES", "").strip()
    if not raw:
        return DEFAULT_MAX_REQUEST_BODY_BYTES
    try:
        parsed = int(raw)
    except ValueError as exc:
        raise RuntimeError("MAX_REQUEST_BODY_BYTES must be an integer") from exc
    if parsed < 1024 or parsed > 32 * 1024 * 1024:
        raise RuntimeError(
            "MAX_REQUEST_BODY_BYTES must be between 1024 and 33554432"
        )
    return parsed


class RequestBodyLimitMiddleware:
    """Reject oversized Content-Length and chunked bodies with HTTP 413.

    The body is buffered only up to the configured cap and replayed once to
    Starlette. Therefore JSON parsing, authentication dependencies and route
    handlers never see an oversized payload, nor one with more values than
    any real body holds; and only so many big bodies are in flight at once.
    """

    def __init__(self, app, max_body_bytes: int | None = None, places: BigBodies | None = None):
        self.app = app
        self.max_body_bytes = (
            configured_max_request_body_bytes()
            if max_body_bytes is None
            else int(max_body_bytes)
        )
        if self.max_body_bytes < 1:
            raise ValueError("max_body_bytes must be positive")
        self.places = big_bodies if places is None else places

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        limit = min(self.max_body_bytes, route_max_request_body_bytes(str(scope.get("path") or "")))
        headers = {
            key.lower(): value
            for key, value in scope.get("headers", [])
        }
        declared = None
        content_length = headers.get(b"content-length")
        if content_length is not None:
            try:
                declared = int(content_length)
            except ValueError:
                await self._reject(send, "Invalid Content-Length header.")
                return
            if declared < 0:
                await self._reject(send, "Invalid Content-Length header.")
                return
            if declared > limit:
                await self._reject(send)
                return

        client = client_of(headers, scope.get("client"))
        holding = False

        def take_place() -> bool:
            nonlocal holding
            if not holding:
                holding = self.places.take(client)
            return holding

        try:
            # Refused before a byte of it is read.
            if declared is not None and declared > SMALL_REQUEST_BODY_BYTES and not take_place():
                await self._busy(send)
                return

            buffered = bytearray()
            disconnected = False
            deadline = None
            loop = asyncio.get_running_loop()
            while True:
                if holding and deadline is None:
                    deadline = loop.time() + BIG_BODY_SECONDS
                try:
                    message = await (receive() if deadline is None
                                     else asyncio.wait_for(receive(), max(0.0, deadline - loop.time())))
                except asyncio.TimeoutError:
                    await self._reject(send, "The request took too long to arrive.", status=408)
                    return
                if message.get("type") == "http.disconnect":
                    disconnected = True
                    break
                if message.get("type") != "http.request":
                    continue
                chunk = message.get("body", b"")
                if chunk:
                    buffered.extend(chunk)
                    if len(buffered) > limit:
                        await self._reject(send)
                        return
                    # A chunked body says its size only by arriving.
                    if len(buffered) > SMALL_REQUEST_BODY_BYTES and not take_place():
                        await self._busy(send)
                        return
                if not message.get("more_body", False):
                    break

            if disconnected:
                # An aborted, partially buffered request is not a complete body.
                # Preserve the disconnect instead of letting a valid JSON prefix
                # trigger a write after its sender has abandoned the request.
                async def disconnected_receive():
                    return {"type": "http.disconnect"}

                await self.app(scope, disconnected_receive, send)
                return

            body = bytes(buffered)
            buffered.clear()
            if not (headers.get(b"content-type") or b"").lower().startswith(b"multipart/"):
                within = (await asyncio.to_thread(json_elements_within, body)
                          if len(body) > _COUNT_IN_THREAD_BYTES else json_elements_within(body))
                if not within:
                    await self._reject(send)
                    return

            delivered = False

            async def replay_receive():
                nonlocal delivered, body
                if not delivered:
                    delivered = True
                    # Starlette keeps the body for the request; this copy goes.
                    message, body = {"type": "http.request", "body": body, "more_body": False}, b""
                    return message
                # After replaying the buffered body, keep forwarding the real
                # connection state. StreamingResponse listens for an actual
                # http.disconnect while it produces the response; synthesizing one
                # here cancels every non-instant SSE stream before its first chunk.
                return await receive()

            await self.app(scope, replay_receive, send)
        finally:
            if holding:
                self.places.give(client)

    async def _busy(self, send):
        # The app's own shape of a throttle (main.error_body): the page says
        # "Too many requests …" and tries again, as after any other limit.
        from app.core.rate_limit import RATE_LIMITED_CODE, rate_limit_message

        retry_after = 5
        await self._reject(
            send, rate_limit_message(retry_after), status=429,
            fields={"code": RATE_LIMITED_CODE, "retry_after": retry_after},
            headers=[(b"retry-after", str(retry_after).encode("ascii"))],
        )

    async def _reject(self, send, detail: str = "Request body too large.", *, status: int = 413,
                      fields: dict | None = None, headers=()):
        payload = json.dumps(
            {"error": detail, **(fields or {})}, separators=(",", ":")
        ).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-type", b"application/json; charset=utf-8"),
                    (b"content-length", str(len(payload)).encode("ascii")),
                    (b"cache-control", b"no-store"),
                    *headers,
                ],
            }
        )
        await send({"type": "http.response.body", "body": payload})
