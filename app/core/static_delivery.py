"""Transfer-level delivery for static assets and HTML pages.

Two narrow jobs, both applied as one ASGI middleware:

* Content-hashed build output (``static/dist/<group>.<12 hex>.js|css``) never
  changes under its name, so browsers may keep it for a year without
  revalidation. Everything else keeps the default ETag revalidation.
* Static text assets and HTML pages are gzip-compressed when the client asks
  for it. API payloads are left alone, and Server-Sent Events are never
  compressed or buffered: an SSE frame must reach the browser the moment the
  route yields it, and a compressor would hold it back until its window fills.

The middleware decides per response, from the request path and the response
headers, before a single body byte is sent. Anything it does not explicitly
recognise passes through unchanged, message by message.
"""
import re
import zlib
from starlette.datastructures import Headers, MutableHeaders

IMMUTABLE_CACHE_CONTROL = "public, max-age=31536000, immutable"
_HASHED_DIST = re.compile(r"^/static/dist/[A-Za-z0-9_-]+\.[0-9a-f]{12}\.(?:js|css|mjs)$")
_COMPRESSIBLE_STATIC = (
    "text/css",
    "text/javascript",
    "application/javascript",
    "application/json",
    "application/manifest+json",
    "image/svg+xml",
    "text/plain",
    "text/markdown",
)
MINIMUM_SIZE = 1024


def is_hashed_dist_path(path: str) -> bool:
    return bool(_HASHED_DIST.match(path or ""))


def _media_type(headers: Headers) -> str:
    return headers.get("content-type", "").split(";", 1)[0].strip().lower()


def _should_compress(path: str, status: int, headers: Headers) -> bool:
    media_type = _media_type(headers)
    # Event streams are excluded first and unconditionally, whatever the path.
    if media_type == "text/event-stream" or not media_type:
        return False
    if status != 200 or "content-encoding" in headers or "content-range" in headers:
        return False
    if "no-transform" in headers.get("cache-control", "").lower():
        return False
    length = headers.get("content-length")
    if length is not None and length.isdigit() and int(length) < MINIMUM_SIZE:
        return False
    if media_type == "text/html":
        return True
    return path.startswith("/static/") and media_type in _COMPRESSIBLE_STATIC


class StaticDeliveryMiddleware:
    def __init__(self, app, compresslevel: int = 6) -> None:
        self.app = app
        self.compresslevel = compresslevel

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = str(scope.get("path") or "")
        accepts_gzip = "gzip" in Headers(scope=scope).get("accept-encoding", "").lower()
        immutable = is_hashed_dist_path(path)
        state = {"mode": None, "start": None, "compressor": None}

        async def wrapped_send(message):
            kind = message["type"]
            if kind == "http.response.start":
                headers = MutableHeaders(raw=list(message.get("headers") or []))
                status = int(message.get("status") or 200)
                if immutable and status in (200, 304):
                    headers["Cache-Control"] = IMMUTABLE_CACHE_CONTROL
                if _should_compress(path, status, headers):
                    headers.add_vary_header("Accept-Encoding")
                    if accepts_gzip:
                        state["mode"] = "gzip"
                        state["start"] = {**message, "headers": headers.raw}
                        return
                state["mode"] = "pass"
                await send({**message, "headers": headers.raw})
                return
            if state["mode"] == "gzip" and kind == "http.response.pathsend" and state["start"] is not None:
                # Zero-copy file transfer cannot be re-encoded; send it as is.
                start, state["mode"], state["start"] = state["start"], "pass", None
                await send(start)
            if kind != "http.response.body" or state["mode"] != "gzip":
                await send(message)
                return
            await self._send_compressed(state, message, send)

        await self.app(scope, receive, wrapped_send)

    async def _send_compressed(self, state, message, send):
        body = message.get("body", b"")
        more_body = bool(message.get("more_body", False))
        start = state["start"]
        if start is not None:
            state["start"] = None
            headers = MutableHeaders(raw=start["headers"])
            if not more_body and len(body) < MINIMUM_SIZE:
                # Small single-chunk body: compression would cost more than it saves.
                state["mode"] = "pass"
                await send(start)
                await send(message)
                return
            state["compressor"] = zlib.compressobj(self.compresslevel, zlib.DEFLATED, 31)
            headers["Content-Encoding"] = "gzip"
            if "content-length" in headers:
                del headers["content-length"]
            etag = headers.get("etag")
            if etag and not etag.startswith("W/"):
                # The encoded bytes differ from the identity representation.
                headers["ETag"] = f"W/{etag}"
            await send({**start, "headers": headers.raw})
        compressor = state["compressor"]
        data = compressor.compress(body)
        if not more_body:
            data += compressor.flush()
        await send({"type": "http.response.body", "body": data, "more_body": more_body})

