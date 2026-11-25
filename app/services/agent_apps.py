"""An app the agent serves in the workspace, in the user's own browser
(docs/agent-mode.md "App im eigenen Browser").

The workspace has no address a browser can open, and what the agent builds
must never run as consens.io: a page under consens.io's own address could
read the user's sign-in. So an app has an address of its own, the service's
second host (AGENT_APP_HOST, a different site to every browser), where
nothing of consens.io is served (app/core/app_host.py) and every request
goes to the port of the user's workspace (agent_app_proxy.py).

Who may open it is decided on consens.io, signed in (routers/agent_workspace.py
open_app): the answer is an address on the app's host with a token, good for
OPEN_SECONDS. That address trades the token for a cookie of the app's host
(the session: account, port and which app), good for SESSION_SECONDS. Both
are encrypted and signed with the server's secret under keys of their own.
The app's own code never sees either: the cookie is HttpOnly and is taken
out of what goes on to the app.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
import time

from cryptography.fernet import Fernet, InvalidToken

__all__ = ["InvalidToken", "COOKIE", "OPEN_PATH", "OPEN_SECONDS", "SESSION_SECONDS", "Session", "app_key", "host",
           "issue_open", "issue_session", "open_url", "read_open", "read_session", "start_path"]

# Long enough for a new tab to load the address; the cookie it leaves holds
# as long as a background process may run (agent_vm_processes.MAX_SECONDS).
OPEN_SECONDS = 60
SESSION_SECONDS = 60 * 60
# The browser sends it to this host only, over HTTPS, with every path, and
# no script of the app reads it.
COOKIE = "__Host-consens_app"
# The one path of the app's host that is consens.io's: an app that serves
# its own under it does not get those requests.
OPEN_PATH = "/__consens/open"
LOWEST_PORT, HIGHEST_PORT = 1024, 65535
PATH_CHARS = 2000
# Room for the longest opening issue_open makes: a Firebase uid (128
# characters at most) and a path of PATH_CHARS characters of four UTF-8
# bytes each.
_TOKEN = re.compile(r"[A-Za-z0-9_=-]{80,11000}")
_HOST = re.compile(r"[a-z0-9]([a-z0-9.-]{0,251}[a-z0-9])?(:\d{1,5})?")
_KEY = re.compile(r"[a-f0-9]{16}")
# Without a configured secret (a developer's machine, a test) the addresses
# of this process hold until it ends.
_PROCESS_SECRET = secrets.token_bytes(32)


def host() -> str:
    """The host apps are served on, or "" where there is none: the tool and
    the card come with it (ProcessTools.tools, routers/agent_workspace.py)."""
    value = os.environ.get("AGENT_APP_HOST", "").strip().lower()
    return value if _HOST.fullmatch(value) else ""


def _cipher(purpose: bytes) -> Fernet:
    secret = (os.environ.get("CHAT_CURSOR_SECRET", "").strip()
              or os.environ.get("WATCH_UNSUBSCRIBE_SECRET", "").strip()).encode("utf-8")
    material = secret if len(secret) >= 16 else _PROCESS_SECRET
    # A key per purpose: a token to open is no session, and neither reads as
    # any other signed value of the server.
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(purpose + b"\0" + material).digest()))


def app_key(uid: str, chat_id: str, port: int) -> str:
    """Which app a browser has open: the same chat's on the same port again
    keeps what the app stored in the browser, another one starts clean
    (agent_app_proxy.open_session)."""
    return hashlib.sha256(f"{uid}\0{chat_id}\0{port}".encode("utf-8")).hexdigest()[:16]


def start_path(path: str) -> str:
    """Where the app opens: a path on its own host, never another address
    and never consens.io's own path there."""
    path = str(path or "/")
    if (not path.startswith("/") or path.startswith("//") or "\\" in path or len(path) > PATH_CHARS
            or any(ord(char) < 0x20 or ord(char) == 0x7f for char in path) or path.startswith(OPEN_PATH)
            or not _utf8(path)):
        return "/"
    return path


def _utf8(text) -> bool:
    """A lone surrogate (JSON allows one) has no UTF-8: such a path would
    break the opening's payload (issue_open)."""
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _port(value) -> bool:
    return type(value) is int and LOWEST_PORT <= value <= HIGHEST_PORT


class Session:
    """What the app host's cookie says: whose workspace, which port, which app."""

    __slots__ = ("uid", "port", "key")

    def __init__(self, uid: str, port: int, key: str):
        self.uid, self.port, self.key = uid, port, key


def issue_open(uid: str, port: int, path: str, key: str, *, now: float | None = None) -> str:
    # As UTF-8, not as \u escapes: an "ü" then costs two bytes, not six.
    payload = json.dumps([uid, port, start_path(path), key], separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return _cipher(b"agent-app-open").encrypt_at_time(payload, int(time.time() if now is None else now)).decode("ascii")


def read_open(token: str, *, now: float | None = None) -> tuple[Session, str]:
    """``(session, path)`` of an address this server issued within
    OPEN_SECONDS; InvalidToken for anything else."""
    if not _TOKEN.fullmatch(str(token or "")):
        raise InvalidToken
    payload = _cipher(b"agent-app-open").decrypt_at_time(token.encode("ascii"), OPEN_SECONDS,
                                                         int(time.time() if now is None else now))
    try:
        uid, port, path, key = json.loads(payload)
    except (ValueError, TypeError):
        raise InvalidToken from None
    if not (isinstance(uid, str) and uid and _port(port) and isinstance(path, str)
            and isinstance(key, str) and _KEY.fullmatch(key)):
        raise InvalidToken
    return Session(uid, port, key), start_path(path)


def issue_session(session: Session, *, now: float | None = None) -> str:
    payload = json.dumps([session.uid, session.port, session.key], separators=(",", ":")).encode("utf-8")
    return _cipher(b"agent-app-session").encrypt_at_time(
        payload, int(time.time() if now is None else now)).decode("ascii")


def read_session(value: str, *, now: float | None = None) -> Session:
    if not _TOKEN.fullmatch(str(value or "")):
        raise InvalidToken
    payload = _cipher(b"agent-app-session").decrypt_at_time(value.encode("ascii"), SESSION_SECONDS,
                                                            int(time.time() if now is None else now))
    try:
        uid, port, key = json.loads(payload)
    except (ValueError, TypeError):
        raise InvalidToken from None
    if not (isinstance(uid, str) and uid and _port(port) and isinstance(key, str) and _KEY.fullmatch(key)):
        raise InvalidToken
    return Session(uid, port, key)


def open_url(token: str) -> str:
    """The address the new tab loads. Plain http only for a host on this
    machine (a developer's server); everywhere else the cookie needs HTTPS."""
    name = host()
    bare = name.split(":", 1)[0]
    local = bare in {"localhost", "127.0.0.1"} or bare.endswith(".localhost")
    return f"{'http' if local else 'https'}://{name}{OPEN_PATH}?t={token}"
