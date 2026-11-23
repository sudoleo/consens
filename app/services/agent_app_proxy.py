"""Everything the app's host answers (agent_apps.py, app/core/app_host.py;
docs/agent-mode.md "App im eigenen Browser"): the trade of an opening
address for the session's cookie, and from then on every request and
WebSocket as the app in the user's workspace answers it, carried through the
account's tunnel (agent_app_tunnel.py).

To the app the browser is on its own computer: the request names
``localhost:<port>`` as host and origin, as if the user had opened the
port there. A dev server that only serves its own host (Vite's
allowedHosts) answers, and one that compares origin and host finds them
equal. What the app says about that address (a redirect, a cookie's
domain) is turned back to the app's host. The app learns nothing of the
user beyond what their browser sends an app: no address, nothing the
service's own front adds, and never the session's cookie.

The pages this module writes itself (no session, the app ended, the
workspace out of reach) carry their sentences through ``_t``.
"""
from __future__ import annotations

import asyncio
import html
import logging
from urllib.parse import parse_qs

import h11

from app.core import i18n
from app.core.observability import safe_exception
from app.services import agent_app_tunnel, agent_apps

# Headers of one connection, never carried on (RFC 9110 7.6.1).
HOP = frozenset({b"connection", b"keep-alive", b"proxy-authenticate", b"proxy-authorization", b"proxy-connection",
                 b"te", b"trailer", b"transfer-encoding", b"upgrade"})
# What the service's front (Render, Cloudflare) adds about the user and the request's way.
FRONT_PREFIXES = (b"cf-", b"x-forwarded-", b"rndr-", b"render-", b"x-render-")
FRONT = frozenset({b"forwarded", b"via", b"true-client-ip", b"x-real-ip", b"cdn-loop", b"x-request-id",
                   b"x-request-start"})
WS_MAX_MESSAGE = 16 * 1024 * 1024
# Close codes a server may send a browser (RFC 6455 7.4); the rest become one of these.
WS_SENDABLE = frozenset({1000, 1001, 1003, 1007, 1008, 1009, 1010, 1011, 1012, 1013, 1014})
OWN_HEADERS = [(b"cache-control", b"private, no-store"), (b"x-robots-tag", b"noindex, nofollow"),
               (b"referrer-policy", b"no-referrer"), (b"x-content-type-options", b"nosniff")]
PAGE = """<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex"><title>consens.io</title>
<style>html{{color-scheme:light dark}}body{{margin:0;min-height:100vh;display:grid;place-items:center;
font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;background:Canvas;color:CanvasText}}
main{{max-width:28rem;padding:2rem}}h1{{font-size:1.125rem;font-weight:600;margin:0 0 .5rem}}
p{{margin:0;opacity:.72}}</style></head>
<body><main><h1>{title}</h1><p>{text}</p></main></body></html>"""


def _t(text: str, language: str, values=None) -> str:
    return i18n.t(text, language, values or {})


def _header(scope, name):
    for key, value in scope.get("headers") or ():
        if key.lower() == name:
            return value.decode("latin-1")
    return ""


def _language(scope):
    return i18n.preferred_language(_header(scope, b"accept-language")) or "en"


def _cookies(scope):
    found = {}
    for chunk in _header(scope, b"cookie").split(";"):
        name, _, value = chunk.strip().partition("=")
        if name:
            found.setdefault(name, value)
    return found


def session_of(scope):
    """The session the request's cookie holds, or None."""
    value = _cookies(scope).get(agent_apps.COOKIE)
    if not value:
        return None
    try:
        return agent_apps.read_session(value)
    except agent_apps.InvalidToken:
        return None


async def _respond(send, status, headers, body=b""):
    await send({"type": "http.response.start", "status": status,
                "headers": [*headers, (b"content-length", str(len(body)).encode())]})
    await send({"type": "http.response.body", "body": body})


async def _page(scope, send, status, title, text):
    """One of this module's own pages; ``title`` and ``text`` in the reader's language."""
    body = PAGE.format(lang=_language(scope), title=html.escape(title), text=html.escape(text)).encode("utf-8")
    await _respond(send, status, [
        (b"content-type", b"text/html; charset=utf-8"), *OWN_HEADERS,
        (b"content-security-policy", b"default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'"),
    ], b"" if scope.get("method") == "HEAD" else body)


async def _refusal(scope, send, session, exc):
    """Why the app does not show, as a page in the reader's language."""
    language = _language(scope)
    reason = getattr(exc, "reason", "")
    if reason == "idle":
        await _page(scope, send, 503, _t("The app is not running", language),
                    _t("It ended in the workspace. Ask the agent in your chat to start it again.", language))
    elif reason == "refused":
        await _page(scope, send, 502, _t("The app does not answer", language),
                    _t("Nothing answers on port {port} right now. If the app is still starting, reload in a moment.",
                       language, {"port": session.port}))
    elif reason == "busy":
        await _page(scope, send, 503, _t("The app does not answer", language),
                    _t("Too many connections to the app at once. Reload in a moment.", language))
    else:
        await _page(scope, send, 503, _t("The workspace is out of reach", language),
                    _t("Your workspace cannot be reached right now. Try again in a moment.", language))


# --- Opening ----------------------------------------------------------------


async def open_session(scope, send):
    """The opening address: its token becomes the session's cookie, and the
    tab goes on to the app. A browser that had another app open here (or
    none) first forgets what that one stored: every app runs under this one
    host, and a service worker or a cached script of the last would answer
    for the next. That takes two answers, since the first clears the
    cookies too."""
    query = parse_qs((scope.get("query_string") or b"").decode("latin-1"))
    token = (query.get("t") or [""])[0]
    language = _language(scope)
    try:
        session, path = agent_apps.read_open(token)
    except agent_apps.InvalidToken:
        await _page(scope, send, 403, _t("This link is no longer valid", language),
                    _t("Open the app again from its card in your chat.", language))
        return
    held = session_of(scope)
    same = held is not None and held.uid == session.uid and held.key == session.key
    if not same and (query.get("s") or [""])[0] != "1":
        await _respond(send, 303, [
            (b"location", f"{agent_apps.OPEN_PATH}?t={token}&s=1".encode("ascii")), *OWN_HEADERS,
            (b"clear-site-data", b'"cache", "cookies", "storage"'),
        ])
        return
    cookie = (f"{agent_apps.COOKIE}={agent_apps.issue_session(session)}; Path=/; Max-Age={agent_apps.SESSION_SECONDS}; "
              "HttpOnly; Secure; SameSite=Lax")
    await _respond(send, 303, [
        (b"location", path.encode("utf-8")), *OWN_HEADERS, (b"set-cookie", cookie.encode("ascii")),
        # The tab that opened this one (consens.io) is out of the app's reach.
        (b"cross-origin-opener-policy", b"same-origin"),
    ])


# --- What goes to the app and comes back --------------------------------------


def _front(name):
    return name in FRONT or name.startswith(FRONT_PREFIXES)


def _without_session(value):
    kept = [chunk.strip() for chunk in value.split(b";")
            if chunk.strip() and chunk.strip().partition(b"=")[0] != agent_apps.COOKIE.encode("ascii")]
    return b"; ".join(kept)


def _local(port):
    return f"http://localhost:{port}"


def _to_local(value, host, port):
    """The app's own address in a request header (Origin, Referer), as the app knows itself."""
    for scheme in (b"https://", b"http://"):
        public = scheme + host.encode("ascii")
        if value == public or value.startswith(public + b"/"):
            return _local(port).encode("ascii") + value[len(public):]
    return value


def request_headers(scope, session, host):
    headers = [(b"host", f"localhost:{session.port}".encode("ascii"))]
    chunked = False
    for name, value in scope.get("headers") or ():
        lower = name.lower()
        # A body without a length stays one: its framing belongs to each
        # connection, so the header is written anew below.
        chunked = chunked or lower == b"transfer-encoding"
        if lower in HOP or lower == b"host" or _front(lower):
            continue
        if lower == b"cookie":
            value = _without_session(value)
            if not value:
                continue
        elif lower in (b"origin", b"referer"):
            value = _to_local(value, host, session.port)
        headers.append((lower, value))
    if chunked:
        headers.append((b"transfer-encoding", b"chunked"))
    headers.append((b"connection", b"close"))
    return headers


def _relocated(value, port):
    """A redirect to the app's own address on the workspace, as a path here."""
    for name in (b"localhost", b"127.0.0.1", b"[::1]"):
        for scheme in (b"http://", b"https://"):
            local = scheme + name + b":" + str(port).encode("ascii")
            if value == local or value.startswith((local + b"/", local + b"?", local + b"#")):
                rest = value[len(local):]
                return rest if rest.startswith(b"/") else b"/" + rest
    return value


def _cookie_here(value):
    """The app's cookie without the domain it named (its own localhost):
    the browser keeps it for this host instead of refusing it."""
    parts = [part for part in value.split(b";") if not part.strip().lower().startswith(b"domain=")]
    return b";".join(parts)


def response_headers(headers, session):
    kept = []
    for name, value in headers:
        if name in HOP:
            continue
        if name == b"location":
            value = _relocated(value, session.port)
        elif name == b"set-cookie":
            if value.split(b"=", 1)[0].strip() == agent_apps.COOKIE.encode("ascii"):
                continue
            value = _cookie_here(value)
        kept.append((name, value))
    kept.append((b"x-robots-tag", b"noindex, nofollow"))
    return kept


def _target(scope):
    path = scope.get("raw_path") or scope.get("path", "/").encode("utf-8")
    query = scope.get("query_string") or b""
    return path + (b"?" + query if query else b"")


# --- HTTP ---------------------------------------------------------------------


async def _http(scope, receive, send, session, host):
    try:
        tunnel = await agent_app_tunnel.tunnel_for(session.uid)
        stream = await tunnel.open(session.port)
    except (agent_app_tunnel.Refused, agent_app_tunnel.Unavailable) as exc:
        await _refusal(scope, send, session, exc)
        return
    connection = h11.Connection(h11.CLIENT)
    started = False
    try:
        try:
            await stream.write(connection.send(h11.Request(method=scope["method"], target=_target(scope),
                                                           headers=request_headers(scope, session, host))))
        except h11.LocalProtocolError:
            await _page(scope, send, 400, _t("The app does not answer", _language(scope)),
                        _t("The request could not be passed on to the app.", _language(scope)))
            return

        async def upload():
            """The request's body to the app, then the wait for the browser
            to leave: "gone" ends the answer with it."""
            sent = False
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return "gone"
                if sent:
                    continue
                body = message.get("body") or b""
                if body:
                    await stream.write(connection.send(h11.Data(data=body)))
                if not message.get("more_body"):
                    await stream.write(connection.send(h11.EndOfMessage()))
                    sent = True

        browser = asyncio.ensure_future(upload())
        try:
            while True:
                event = connection.next_event()
                if event is h11.NEED_DATA:
                    reading = asyncio.ensure_future(stream.read())
                    await asyncio.wait({reading, browser}, return_when=asyncio.FIRST_COMPLETED)
                    if browser.done():
                        reading.cancel()
                        if browser.exception() is not None:
                            raise browser.exception()
                        return
                    connection.receive_data(reading.result())
                elif isinstance(event, h11.Response):
                    started = True
                    await send({"type": "http.response.start", "status": event.status_code,
                                "headers": response_headers(event.headers, session)})
                elif isinstance(event, h11.Data):
                    await send({"type": "http.response.body", "body": bytes(event.data), "more_body": True})
                elif isinstance(event, (h11.EndOfMessage, h11.ConnectionClosed)):
                    if not started:
                        raise ConnectionError("The app closed the connection without an answer.")
                    await send({"type": "http.response.body", "body": b""})
                    return
        finally:
            browser.cancel()
    except (ConnectionError, h11.RemoteProtocolError, h11.LocalProtocolError) as exc:
        logging.info("Agent app request ended early category=%s", safe_exception(exc))
        if not started:
            await _page(scope, send, 502, _t("The app does not answer", _language(scope)),
                        _t("The app closed the connection without an answer. Reload in a moment.", _language(scope)))
    finally:
        await stream.close()


# --- WebSocket ----------------------------------------------------------------


async def _websocket(scope, receive, send, session, host):
    from websockets.client import ClientProtocol
    from websockets.frames import Frame, Opcode
    from websockets.protocol import State
    from websockets.uri import parse_uri

    if (await receive()).get("type") != "websocket.connect":
        return
    try:
        tunnel = await agent_app_tunnel.tunnel_for(session.uid)
        stream = await tunnel.open(session.port)
    except (agent_app_tunnel.Refused, agent_app_tunnel.Unavailable):
        await send({"type": "websocket.close", "code": 1013})
        return
    writing = asyncio.Lock()

    async def flush(protocol):
        # One writer at a time: a message longer than a tunnel frame goes in
        # several, and another's must not land between them.
        async with writing:
            for data in protocol.data_to_send():
                if data:
                    await stream.write(data)
                else:
                    await stream.end()

    try:
        target = _target(scope).decode("latin-1")
        protocol = ClientProtocol(parse_uri(f"ws://localhost:{session.port}{target}"), origin=_local(session.port),
                                  subprotocols=list(scope.get("subprotocols") or ()) or None,
                                  max_size=WS_MAX_MESSAGE)
        request = protocol.connect()
        cookie = _without_session(_header(scope, b"cookie").encode("latin-1"))
        if cookie:
            request.headers["Cookie"] = cookie.decode("latin-1")
        for name in (b"user-agent", b"accept-language"):
            if _header(scope, name):
                request.headers[name.decode("ascii").title()] = _header(scope, name)
        protocol.send_request(request)
        await flush(protocol)
        while protocol.state is State.CONNECTING:
            data = await stream.read()
            if data:
                protocol.receive_data(data)
            else:
                protocol.receive_eof()
            await flush(protocol)
            if not data or protocol.handshake_exc is not None:
                break
        if protocol.state is not State.OPEN:
            await send({"type": "websocket.close", "code": 1011})
            return
        await send({"type": "websocket.accept", "subprotocol": protocol.subprotocol})

        async def from_browser():
            while True:
                message = await receive()
                if message["type"] == "websocket.disconnect":
                    if protocol.state is State.OPEN:
                        code = message.get("code")
                        protocol.send_close(code if code in WS_SENDABLE or 3000 <= (code or 0) <= 4999 else 1000)
                        await flush(protocol)
                    return
                if message.get("text") is not None:
                    protocol.send_text(message["text"].encode("utf-8"))
                elif message.get("bytes") is not None:
                    protocol.send_binary(message["bytes"])
                await flush(protocol)

        async def from_app():
            parts, text = [], False
            while True:
                for event in protocol.events_received():
                    if not isinstance(event, Frame):
                        continue
                    if event.opcode in (Opcode.TEXT, Opcode.BINARY):
                        parts, text = [bytes(event.data)], event.opcode is Opcode.TEXT
                    elif event.opcode is Opcode.CONT:
                        parts.append(bytes(event.data))
                    else:
                        continue
                    if event.fin:
                        whole, parts = b"".join(parts), []
                        await send({"type": "websocket.send", "text": whole.decode("utf-8", "replace")} if text
                                   else {"type": "websocket.send", "bytes": whole})
                if protocol.state is State.CLOSED or protocol.close_rcvd is not None:
                    return
                data = await stream.read()
                if data:
                    protocol.receive_data(data)
                else:
                    protocol.receive_eof()
                await flush(protocol)
                if not data:
                    for event in protocol.events_received():
                        pass
                    return

        tasks = [asyncio.ensure_future(from_browser()), asyncio.ensure_future(from_app())]
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in tasks:
            task.cancel()
        broke = any(not task.cancelled() and task.exception() is not None for task in done)
        if tasks[1] in done:
            code = protocol.close_rcvd.code if protocol.close_rcvd is not None else None
            await send({"type": "websocket.close",
                        "code": 1011 if broke else code if code in WS_SENDABLE or 3000 <= (code or 0) <= 4999 else 1000})
    except Exception as exc:
        logging.info("Agent app socket ended early category=%s", safe_exception(exc))
        try:
            await send({"type": "websocket.close", "code": 1011})
        except Exception:
            pass
    finally:
        await stream.close()


# --- The host -------------------------------------------------------------------


async def app(scope, receive, send):
    """The ASGI app of the app's host (app/core/app_host.py)."""
    host = agent_apps.host()
    if scope["type"] == "websocket":
        session = session_of(scope)
        if session is None:
            if (await receive()).get("type") == "websocket.connect":
                await send({"type": "websocket.close", "code": 1008})
            return
        await _websocket(scope, receive, send, session, host)
        return
    if scope.get("path") == agent_apps.OPEN_PATH:
        if scope.get("method") not in {"GET", "HEAD"}:
            await _respond(send, 405, [(b"allow", b"GET, HEAD"), *OWN_HEADERS])
            return
        await open_session(scope, send)
        return
    session = session_of(scope)
    if session is None:
        await _page(scope, send, 403, _t("An app from a consens.io workspace", _language(scope)),
                    _t("Open it from its card in your chat on consens.io.", _language(scope)))
        return
    await _http(scope, receive, send, session, host)
