"""The address the chat shows a shared page under (routers/agent_files.py).

A frame cannot send the account's sign-in with its request, so the browser
asks for an address first, signed in, and the frame loads that. The address
holds a token: the account, the chat and the file, encrypted and signed with
the server's secret and good for TOKEN_SECONDS. It opens that one file and
nothing else, and the page that runs under it reads nothing from it.
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

__all__ = ["InvalidToken", "TOKEN_SECONDS", "issue", "read"]

# Long enough for the frame to load after the address arrived; the page
# stays once it is loaded.
TOKEN_SECONDS = 300
_TOKEN = re.compile(r"[A-Za-z0-9_=-]{80,1200}")
_ID = re.compile(r"[a-f0-9]{32}")
# Without a configured secret (a developer's machine, a test) the addresses
# of this process hold until it ends.
_PROCESS_SECRET = secrets.token_bytes(32)


def _cipher() -> Fernet:
    secret = (os.environ.get("CHAT_CURSOR_SECRET", "").strip()
              or os.environ.get("WATCH_UNSUBSCRIBE_SECRET", "").strip()).encode("utf-8")
    material = secret if len(secret) >= 16 else _PROCESS_SECRET
    # Its own key under the shared secret: no other signed value of the
    # server reads as a page's address, and none of these as anything else.
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(b"agent-page-address\0" + material).digest()))


def issue(uid: str, chat_id: str, file_id: str, *, now: float | None = None) -> str:
    payload = json.dumps([uid, chat_id, file_id], separators=(",", ":")).encode("utf-8")
    return _cipher().encrypt_at_time(payload, int(time.time() if now is None else now)).decode("ascii")


def read(token: str, *, now: float | None = None) -> tuple[str, str, str]:
    """``(uid, chat_id, file_id)`` of an address this server issued within
    TOKEN_SECONDS; InvalidToken for anything else."""
    if not _TOKEN.fullmatch(str(token or "")):
        raise InvalidToken
    payload = _cipher().decrypt_at_time(token.encode("ascii"), TOKEN_SECONDS,
                                        int(time.time() if now is None else now))
    try:
        uid, chat_id, file_id = json.loads(payload)
    except (ValueError, TypeError):
        raise InvalidToken from None
    if not (isinstance(uid, str) and uid and isinstance(chat_id, str) and isinstance(file_id, str)
            and _ID.fullmatch(file_id)):
        raise InvalidToken
    return uid, chat_id, file_id
