"""Transfer-level delivery for static assets and HTML pages.

Two narrow jobs, both applied as one ASGI middleware:

* Content-hashed build output (``static/dist/<group>.<12 hex>.js|css``),
  the content-hashed font files (``static/fonts/.../<name>.<12 hex>.woff2``,
  named by ``scripts/subset_inter_font.py``) and URLs carrying
  ``asset_url``'s content hash (``?v=<12 hex>``) never change under their
  name, so browsers may keep them for a year without revalidation. A font
  that had to be asked for again on every visit (a 304 round trip) arrived
  after the first paint and swapped the text under the reader's eyes.
  Every other ``/static`` response is ``no-cache``: browsers and
  the CDN must revalidate (ETag, usually a 304). That covers the unversioned
  nested ``@import``/ESM URLs whose bytes are already folded into the entry
  file's hash, and it replaces the hand-bumped ``?v=`` marks.
* Static text assets and HTML pages are gzip-compressed when the client asks
  for it. API payloads are left alone, and Server-Sent Events are never
  compressed or buffered: an SSE frame must reach the browser the moment the
  route yields it, and a compressor would hold it back until its window fills.

* A font part asked for under its name from before the content hash
  (``InterVariable-latin.woff2``) gets its current hashed file. A tab opened
  before a deploy still runs the old stylesheet and loads italic or
  latin-ext only at its first such character -- otherwise that text fell
  back to a system font until the next reload (Zweitprüfung, Schriften).

The middleware decides per response, from the request path and the response
headers, before a single body byte is sent. Anything it does not explicitly
recognise passes through unchanged, message by message.
"""
import mimetypes
import re
import zlib
from functools import lru_cache
from pathlib import Path
from starlette.datastructures import Headers, MutableHeaders

# StaticFiles takes the type from the platform's table, and Windows (and some
# slim Linux images) know no .woff2: the fonts went out as
# application/octet-stream next to a preload that announces font/woff2.
mimetypes.add_type("font/woff2", ".woff2")

IMMUTABLE_CACHE_CONTROL = "public, max-age=31536000, immutable"
REVALIDATE_CACHE_CONTROL = "no-cache"
_CONTENT_VERSION = re.compile(r"(?:^|&)v=[0-9a-f]{12}(?:&|$)")
_HASHED_DIST = re.compile(r"^/static/dist/[A-Za-z0-9_-]+\.[0-9a-f]{12}\.(?:js|css|mjs)$")
_HASHED_FONT = re.compile(r"^/static/fonts/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+\.[0-9a-f]{12}\.woff2$")
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


STATIC_ROOT = Path(__file__).resolve().parents[2] / "static"
_HASHED_FONT_FILE = re.compile(r"^(?P<part>[A-Za-z0-9_-]+)\.[0-9a-f]{12}\.woff2$")


@lru_cache(maxsize=4)
def _legacy_font_aliases(static_root: Path) -> dict[str, str]:
    """``/static/fonts/.../<part>.woff2`` -> ``/static/fonts/.../<part>.<hash>.woff2``
    for every hashed font file whose old, unhashed name no longer exists.
    Read once per process: fonts change only with a deploy."""
    aliases: dict[str, str] = {}
    for file in sorted((static_root / "fonts").rglob("*.woff2")):
        match = _HASHED_FONT_FILE.match(file.name)
        if not match:
            continue
        legacy = file.with_name(match["part"] + ".woff2")
        if legacy.exists():
            continue
        aliases["/static/" + legacy.relative_to(static_root).as_posix()] = (
            "/static/" + file.relative_to(static_root).as_posix()
        )
    return aliases


def legacy_font_target(path: str, static_root: Path = STATIC_ROOT) -> "str | None":
    """The hashed file an old font URL stands for, or None."""
    if not (path or "").startswith("/static/fonts/") or not path.endswith(".woff2"):
        return None
    return _legacy_font_aliases(static_root).get(path)


def static_cache_control(path: str, query_string: str = "") -> "str | None":
    """Cache-Control for a /static response, or None to leave it alone."""
    if is_hashed_dist_path(path) or _HASHED_FONT.match(path or ""):
        return IMMUTABLE_CACHE_CONTROL
    if not (path or "").startswith("/static/"):
        return None
    if _CONTENT_VERSION.search(query_string or ""):
        return IMMUTABLE_CACHE_CONTROL
    return REVALIDATE_CACHE_CONTROL


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
        query = (scope.get("query_string") or b"").decode("latin-1")
        # Cache policy of the URL asked for: an old name is no content hash
        # and keeps revalidating.
        cache_control = static_cache_control(path, query)
        font = legacy_font_target(path)
        if font:
            scope = {**scope, "path": font, "raw_path": font.encode("latin-1")}
        state = {"mode": None, "start": None, "compressor": None}

        async def wrapped_send(message):
            kind = message["type"]
            if kind == "http.response.start":
                headers = MutableHeaders(raw=list(message.get("headers") or []))
                status = int(message.get("status") or 200)
                if cache_control and status in (200, 304):
                    headers["Cache-Control"] = cache_control
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

