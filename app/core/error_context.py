"""Inhaltsfreier Fundort-Kontext fuer Server-Fehlermeldungen (Telegram-Alerts).

Ein Alert soll sich in Claude Code einfuegen lassen und dort direkt zur
Codestelle fuehren. Dafuer braucht er WO und WELCHER Build -- nie WAS: die
Exception-Message eines Serverfehlers kann Fragetext, Modellantworten oder
Provider-Bodies tragen und bleibt deshalb draussen (wie in
``observability.safe_traceback``). Die Frames sind der Fundort.
"""

from __future__ import annotations

import os
import socket
import traceback
from pathlib import Path

from app.core.observability import correlation_id, safe_exception
from app.core.version import get_commit_short


_REPO_ROOT = Path(__file__).resolve().parents[2]
ALERT_FRAMES = 8
# Programmierfehler im eigenen Code. Provider-, Netz-, Timeout-, Firestore-
# und Domaenenfehler (ValueError-Unterklassen, HTTP-Status, Abbrueche) sind
# erwartbare Betriebszustaende mit eigener Behandlung und kein Alert-Anlass.
_PROGRAMMING_ERRORS = (
    AttributeError,
    LookupError,  # KeyError, IndexError
    NameError,  # inkl. UnboundLocalError
    TypeError,
    AssertionError,
    ArithmeticError,  # ZeroDivisionError & Co.
    RecursionError,
    NotImplementedError,
)


def _relative_app_path(filename: str) -> str | None:
    try:
        path = Path(filename).resolve()
        relative = path.relative_to(_REPO_ROOT)
    except (OSError, ValueError):
        return None
    parts = relative.parts
    if not parts or parts[0] in {"venv", ".venv", "node_modules"} or "site-packages" in parts:
        return None
    return relative.as_posix()


def alert_frames(exc: BaseException, *, limit: int = ALERT_FRAMES) -> list[str]:
    """``app/x.py:12:func``, innerster Projekt-Frame zuerst.

    Bibliotheks-Frames (Starlette, httpx, ...) zeigen nicht auf den Fehler im
    eigenen Code und fallen weg. Ohne einen einzigen Projekt-Frame bleibt der
    innerste Frame als Dateiname stehen, damit der Alert nie ortlos ist.
    """
    frames = traceback.extract_tb(exc.__traceback__)
    rendered = []
    for frame in reversed(frames):
        relative = _relative_app_path(frame.filename)
        if relative is None:
            continue
        rendered.append(f"{relative}:{frame.lineno}:{frame.name}")
        if len(rendered) >= limit:
            break
    if not rendered and frames:
        frame = frames[-1]
        rendered.append(f"{os.path.basename(frame.filename)}:{frame.lineno}:{frame.name}")
    return rendered


def instance_id() -> str:
    value = os.environ.get("RENDER_INSTANCE_ID") or ""
    if not value:
        try:
            value = socket.gethostname()
        except OSError:
            value = ""
    return str(value or "unknown").strip()[:60]


def is_unexpected_exception(exc: BaseException) -> bool:
    """True nur fuer Programmierfehler, die ein Alert wert sind."""
    return isinstance(exc, _PROGRAMMING_ERRORS)


def server_error_report(
    exc: BaseException,
    *,
    phase: str,
    path: str,
    message: str,
    correlation: str | None = None,
    status: int | None = None,
    **extra,
) -> dict:
    """Einheitliche Alert-Form fuer Request-, Stream- und Hintergrundfehler."""
    corr = correlation if correlation is not None else correlation_id()
    report = {
        "source": "server",
        "type": safe_exception(exc),
        "phase": phase,
        "message": message,
        "path": path,
        "frames": alert_frames(exc),
        "commit": get_commit_short(),
        "instance": instance_id(),
    }
    if corr and corr != "-":
        report["correlation_id"] = corr
    if status is not None:
        report["status"] = int(status)
    report.update(extra)
    return report
