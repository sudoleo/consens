"""Which language a page goes out in, and the German page itself.

One ASGI middleware, just inside the outermost delivery layer (so it sees the
HTML before gzip):

* ``/de/<page>`` serves a localized page (``i18n.LOCALIZED_PATHS``) in German:
  the prefix is taken off before routing, so every router keeps its English
  paths. Other ``/de/…`` addresses redirect to the page without prefix.
* ``?lang=en|de`` on any page remembers the choice in a cookie
  (``consens_lang``, one year, no identifier) and redirects to the same page
  without the parameter, in the chosen language's address; ``?lang=auto``
  forgets it.
* Everywhere else the language is the cookie, else the browser's
  ``Accept-Language`` (German only when the browser prefers German over
  English), else English. A German reader who opens an English address of a
  localized page is redirected to its ``/de`` address; crawlers send no
  Accept-Language and keep the English one.
* Every HTML response in German is translated by ``i18n.translate_html``,
  gets the browser dictionary as the first script of ``<head>`` and
  ``Content-Language: de``. Localized pages list their alternates (hreflang)
  in both languages.
* ``/i18n/<lang>.<hash>.js`` is that browser dictionary plus
  ``static/js/i18n.js``.

API routes, ``/static``, Firebase's auth helpers (``/__/``) and the admin pass
through untouched.
"""

from __future__ import annotations

import gzip
from urllib.parse import parse_qsl, quote, urlencode

from starlette.datastructures import Headers, MutableHeaders

from app.core import i18n
from app.core.site import SITE_URL


# The OAuth callback renders under its own strict policy (no extra script).
PASS_THROUGH = ("/static/", "/__/", "/api/", "/admin", "/health", "/agent/google/callback")
COOKIE_MAX_AGE = 365 * 24 * 3600
BUNDLE_PREFIX = "/i18n/"


def _vary(headers: MutableHeaders, *names: str) -> None:
    present = [item.strip() for item in headers.get("vary", "").split(",") if item.strip()]
    lowered = {item.lower() for item in present}
    for name in names:
        if name.lower() not in lowered:
            present.append(name)
    headers["vary"] = ", ".join(present)


def _cookie(language: str, secure: bool) -> str:
    if language not in i18n.LANGUAGES:
        parts = [f"{i18n.LANGUAGE_COOKIE}=", "Path=/", "Max-Age=0", "SameSite=Lax"]
    else:
        parts = [f"{i18n.LANGUAGE_COOKIE}={language}", "Path=/", f"Max-Age={COOKIE_MAX_AGE}", "SameSite=Lax"]
    if secure:
        parts.append("Secure")
    return "; ".join(parts)


def request_language(request) -> str:
    """The language ``request`` is served in. The middleware passes /api/
    through untouched, so there the same rule runs here: the cookie, else
    the browser's Accept-Language (a follow from a German page mails in German)."""
    language = getattr(request.state, "language", None)
    if language in i18n.LANGUAGES:
        return language
    return (i18n.chosen_language(request.cookies.get(i18n.LANGUAGE_COOKIE))
            or i18n.preferred_language(request.headers.get("accept-language")))


def _cookies(headers: Headers) -> dict[str, str]:
    found: dict[str, str] = {}
    for chunk in headers.get("cookie", "").split(";"):
        name, _, value = chunk.strip().partition("=")
        if name and name not in found:
            found[name] = value
    return found


async def _send_simple(send, status: int, headers: list[tuple[bytes, bytes]], body: bytes = b"") -> None:
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})


def _local_location(path: str, query: list[tuple[str, str]]) -> str:
    """A redirect target on this site. ``path`` arrives decoded, so it is quoted
    again (a ``\\`` or a tab would otherwise read as ``//`` to the browser) and
    never starts with ``//``, which names another host."""
    location = "/" + quote(path, safe="/:@!$&'()*+,;=").lstrip("/")
    return location + (f"?{urlencode(query)}" if query else "")


def _redirect_headers(location: str, *extra: tuple[bytes, bytes]) -> list[tuple[bytes, bytes]]:
    return [
        (b"location", location.encode("latin-1", "replace")),
        (b"cache-control", b"private, no-store"),
        (b"vary", b"Accept-Language, Cookie"),
        (b"content-length", b"0"),
        *extra,
    ]


class I18nMiddleware:
    def __init__(self, app) -> None:
        self.app = app
        self._gzipped: dict[str, bytes] = {}

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path") or "/"
        if path.startswith(BUNDLE_PREFIX):
            await self._bundle(scope, send, path)
            return
        if path.startswith(PASS_THROUGH):
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET")
        headers = Headers(scope=scope)
        prefix_language, page_path = i18n.split_locale_prefix(path)
        query = parse_qsl(scope.get("query_string", b"").decode("latin-1"), keep_blank_values=True)
        secure = scope.get("scheme") == "https" or headers.get("x-forwarded-proto", "") == "https"

        if prefix_language and page_path not in i18n.LOCALIZED_PATHS:
            if method in {"GET", "HEAD"}:
                await _send_simple(send, 302, _redirect_headers(_local_location(page_path, query)))
                return
            prefix_language = None
            page_path = path

        switch = next((value for name, value in query if name == "lang"), None)
        if switch is not None and method in {"GET", "HEAD"} and (switch in i18n.LANGUAGES or switch == "auto"):
            rest = [(name, value) for name, value in query if name != "lang"]
            # "auto" forgets the choice: the browser's language decides again.
            target = i18n.localized_path(page_path, switch) if page_path in i18n.LOCALIZED_PATHS and switch != "auto" else page_path
            await _send_simple(send, 302, _redirect_headers(
                _local_location(target, rest), (b"set-cookie", _cookie(switch, secure).encode("latin-1"))))
            return

        chosen = i18n.chosen_language(_cookies(headers).get(i18n.LANGUAGE_COOKIE))
        language = prefix_language or chosen or i18n.preferred_language(headers.get("accept-language"))
        localized = page_path in i18n.LOCALIZED_PATHS
        if not prefix_language and localized and language != i18n.DEFAULT_LANGUAGE and method in {"GET", "HEAD"}:
            target = i18n.localized_path(page_path, language)
            await _send_simple(send, 302, _redirect_headers(_local_location(target, query)))
            return

        if prefix_language:
            scope = dict(scope)
            scope["path"] = page_path
            scope["raw_path"] = page_path.encode("utf-8")
        state = scope.setdefault("state", {})
        state["language"] = language

        translated = language in i18n.TRANSLATED_LANGUAGES
        if not translated and not localized:
            await self.app(scope, receive, self._vary_only(send))
            return
        await self.app(scope, receive, self._rewriting_send(send, language, page_path, bool(prefix_language), localized))

    def _vary_only(self, send):
        async def wrapped(message):
            if message["type"] == "http.response.start" and _is_html(message):
                headers = MutableHeaders(raw=list(message.get("headers", [])))
                _vary(headers, "Accept-Language", "Cookie")
                message = {**message, "headers": headers.raw}
            await send(message)
        return wrapped

    def _rewriting_send(self, send, language: str, page_path: str, prefixed: bool, localized: bool):
        state: dict = {"start": None, "chunks": []}

        async def wrapped(message):
            kind = message["type"]
            if kind == "http.response.start":
                if not _is_html(message) or Headers(raw=message.get("headers", [])).get("content-encoding"):
                    state["start"] = False
                    await send(message)
                    return
                state["start"] = message
                return
            if state["start"] is False or state["start"] is None or kind != "http.response.body":
                await send(message)
                return
            state["chunks"].append(message.get("body", b""))
            if message.get("more_body"):
                return
            start = state["start"]
            body = b"".join(state["chunks"])
            body = self._page(body, language, page_path, prefixed, localized)
            headers = MutableHeaders(raw=list(start.get("headers", [])))
            headers["content-length"] = str(len(body))
            if language in i18n.TRANSLATED_LANGUAGES:
                headers["content-language"] = language
            if not prefixed:
                _vary(headers, "Accept-Language", "Cookie")
            await send({**start, "headers": headers.raw})
            await send({"type": "http.response.body", "body": body})

        return wrapped

    def _page(self, body: bytes, language: str, page_path: str, prefixed: bool, localized: bool) -> bytes:
        try:
            source = body.decode("utf-8")
        except UnicodeDecodeError:
            return body
        if language in i18n.TRANSLATED_LANGUAGES:
            canonical = f"{SITE_URL}{i18n.localized_path(page_path, language)}" if prefixed else ""
            source = i18n.translate_html(source, language, link_prefix=i18n.LOCALE_PREFIX.get(language, ""),
                                         canonical=canonical)
            bundle = i18n.client_bundle(language)
            if bundle is not None:
                source = _after_charset(source, f'<script src="{bundle.url}"></script>')
        if localized:
            source = source.replace("</head>", f"  {i18n.alternate_links(page_path, SITE_URL)}\n</head>", 1)
        return source.encode("utf-8")

    async def _bundle(self, scope, send, path: str) -> None:
        name = path[len(BUNDLE_PREFIX):]
        language, _, rest = name.partition(".")
        digest = rest[:-3] if rest.endswith(".js") else ""
        bundle = i18n.client_bundle(language) if digest else None
        if bundle is None:
            await _send_simple(send, 404, [(b"content-type", b"text/plain; charset=utf-8"), (b"content-length", b"9")],
                               b"Not Found")
            return
        headers = Headers(scope=scope)
        body = bundle.body
        response_headers = [
            (b"content-type", b"text/javascript; charset=utf-8"),
            # An older page names an older hash: it gets today's words, never cached.
            (b"cache-control", b"public, max-age=31536000, immutable" if digest == bundle.digest else b"no-cache"),
            (b"vary", b"Accept-Encoding"),
        ]
        if "gzip" in headers.get("accept-encoding", "").lower():
            key = bundle.url
            compressed = self._gzipped.get(key)
            if compressed is None:
                compressed = gzip.compress(body, compresslevel=9, mtime=0)
                self._gzipped = {key: compressed}
            body = compressed
            response_headers.append((b"content-encoding", b"gzip"))
        response_headers.append((b"content-length", str(len(body)).encode()))
        await send({"type": "http.response.start", "status": 200, "headers": response_headers})
        await send({"type": "http.response.body", "body": b"" if scope.get("method") == "HEAD" else body})


def _is_html(message) -> bool:
    content_type = Headers(raw=message.get("headers", [])).get("content-type", "")
    return content_type.split(";", 1)[0].strip().lower() == "text/html"


def _after_charset(source: str, tag: str) -> str:
    """Insert ``tag`` as the first script of <head>: after <meta charset>, else after <head>."""
    lowered = source[:4096].lower()
    index = lowered.find("<meta charset")
    if index != -1:
        end = source.find(">", index)
        if end != -1:
            return source[:end + 1] + "\n  " + tag + source[end + 1:]
    index = lowered.find("<head")
    if index != -1:
        end = source.find(">", index)
        if end != -1:
            return source[:end + 1] + "\n  " + tag + source[end + 1:]
    return source
