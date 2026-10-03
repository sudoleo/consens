"""PII-free correlation context and bounded in-process operational metrics."""

from __future__ import annotations

import contextvars
import json
import logging
import os
import re
import secrets
import threading
import time
import traceback
from contextlib import contextmanager


_CORRELATION_ID = contextvars.ContextVar("correlation_id", default="-")
_SAFE_LABEL = re.compile(r"[^a-zA-Z0-9_.:-]")
_LOCK = threading.Lock()
_METRICS: dict[str, dict] = {}


def correlation_id() -> str:
    return _CORRELATION_ID.get()


def new_correlation_id(prefix: str = "req") -> str:
    return f"{prefix}-{secrets.token_hex(8)}"


@contextmanager
def correlation_scope(value: str | None = None, *, prefix: str = "job"):
    token = _CORRELATION_ID.set(value or new_correlation_id(prefix))
    try:
        yield correlation_id()
    finally:
        _CORRELATION_ID.reset(token)


class CorrelationFilter(logging.Filter):
    def filter(self, record):
        record.correlation_id = correlation_id()
        return True


class OAuthAccessFilter(logging.Filter):
    def filter(self, record):
        # Uvicorn's access tuple contains the complete request target. Keep
        # authorization codes/state out of access logs, even at debug level.
        if isinstance(record.args, tuple):
            record.args = tuple(value.split("?", 1)[0] + "?[redacted]" if isinstance(value, str)
                and value.startswith("/agent/google/callback?") else value for value in record.args)
        return True


def configure_logging() -> None:
    logging.getLogger("uvicorn.access").addFilter(OAuthAccessFilter())
    # httpx logs every request URL at INFO. Google API URLs carry calendar
    # IDs, mail queries and page tokens, so keep them out of app logs.
    for name in ("httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)
    root = logging.getLogger()
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [corr=%(correlation_id)s] %(name)s: %(message)s"
    )
    for handler in root.handlers:
        handler.addFilter(CorrelationFilter())
        handler.setFormatter(formatter)


def _label(value: str) -> str:
    return _SAFE_LABEL.sub("_", str(value or "unknown"))[:80]


def record_metric(
    family: str,
    name: str,
    *,
    duration_ms: float = 0,
    outcome: str = "success",
    processed: int = 0,
    retries: int = 0,
) -> None:
    key = f"{_label(family)}:{_label(name)}"
    with _LOCK:
        item = _METRICS.setdefault(key, {
            "count": 0,
            "failures": 0,
            "timeouts": 0,
            "cancellations": 0,
            "retries": 0,
            "processed": 0,
            "duration_ms_total": 0,
            "duration_ms_max": 0,
        })
        item["count"] += 1
        item["failures"] += int(outcome == "failure")
        item["timeouts"] += int(outcome == "timeout")
        item["cancellations"] += int(outcome == "cancelled")
        item["retries"] += max(0, int(retries))
        item["processed"] += max(0, int(processed))
        duration = max(0, int(duration_ms))
        item["duration_ms_total"] += duration
        item["duration_ms_max"] = max(item["duration_ms_max"], duration)


def metrics_snapshot() -> dict:
    with _LOCK:
        return {key: dict(value) for key, value in sorted(_METRICS.items())}


def safe_exception(exc: BaseException) -> str:
    """Stable error category without exception messages or response bodies."""
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if not isinstance(status, (int, str)):
        status = getattr(getattr(exc, "response", None), "status_code", None)
    # Numeric HTTP/gRPC status values are operational metadata. Arbitrary
    # string ``code`` attributes are not: SDKs (and application exceptions)
    # may populate them with upstream text or identifiers.
    suffix = f":{status}" if isinstance(status, int) else ""
    return f"{type(exc).__name__}{suffix}"


# Upstream failure classes recognised in an OpenRouter error. Only the class
# name on the left ever reaches a log, never the matched provider text.
_PROVIDER_REASONS = (
    ("thought_signature", ("thought signature", "thought_signature", "thoughtsignature")),
    ("reasoning_replay", ("thinking block", "reasoning_details", "reasoning item", "encrypted_content", "signature")),
    ("context_length", ("context length", "context window", "context_length", "maximum context",
                        "too many tokens", "token limit", "input is too long", "prompt is too long")),
    ("tool_protocol", ("function call", "function response", "function_call", "functioncall",
                       "tool_call", "tool call", "tool_use", "tool result", "tool_result")),
    ("tool_schema", ("function declaration", "function_declaration", "functiondeclaration", "tools[", "schema")),
    ("content_policy", ("safety", "content policy", "moderation", "prohibited")),
    ("provider_routing", ("no endpoints", "no allowed providers", "zero data retention", "data policy")),
)
_PROVIDER_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9 .()_-]{0,39}")
_UPSTREAM_STATUS = re.compile(r"[A-Z][A-Z_]{2,39}")
_DIAGNOSTIC = re.compile(r"[A-Za-z0-9 =._()-]{1,200}")


def _upstream_error(raw):
    if isinstance(raw, str):
        try:
            raw = json.loads(raw[:16_000])
        except ValueError:
            return None
    if isinstance(raw, list) and raw:
        raw = raw[0]
    error = raw.get("error") if isinstance(raw, dict) else None
    return error if isinstance(error, dict) else None


def provider_error_diagnostic(error) -> str | None:
    """Content-free summary of an OpenRouter error object.

    Emits only allowlisted tokens: the routing provider's name, the upstream
    status enum (e.g. ``INVALID_ARGUMENT``) and a fixed failure class. The
    provider's message is matched against known classes but never copied, so
    question text, model output or tool arguments cannot leak into logs.
    """
    if not isinstance(error, dict):
        return None
    metadata = error.get("metadata") if isinstance(error.get("metadata"), dict) else {}
    parts = []
    name = metadata.get("provider_name")
    if isinstance(name, str) and _PROVIDER_NAME.fullmatch(name):
        parts.append("provider=" + name.replace(" ", "_"))
    upstream = _upstream_error(metadata.get("raw"))
    status = upstream.get("status") if upstream else None
    if isinstance(status, str) and _UPSTREAM_STATUS.fullmatch(status):
        parts.append("upstream=" + status)
    raw = metadata.get("raw")
    haystack = " ".join(value for value in (error.get("message"), raw if isinstance(raw, str) else None,
                                            upstream.get("message") if upstream else None)
                        if isinstance(value, str))[:16_000].lower()
    reason = next((label for label, needles in _PROVIDER_REASONS if any(n in haystack for n in needles)), None)
    parts.append("reason=" + (reason or ("unclassified" if haystack else "none")))
    return " ".join(parts)


def provider_diagnostic(exc: BaseException) -> str:
    """Log projection of ``safe_diagnostic``; revalidated so no text slips through."""
    value = getattr(exc, "safe_diagnostic", None)
    return value if isinstance(value, str) and _DIAGNOSTIC.fullmatch(value) else "-"


SAFE_TRACEBACK_FRAMES = 12


def safe_traceback(exc: BaseException, *, limit: int = SAFE_TRACEBACK_FRAMES) -> str:
    """Where an exception came from, without ever saying what it said.

    ``safe_exception`` gives the category but not the location, which makes an
    unexpected internal error (an IndexError somewhere in the consensus
    pipeline) undiagnosable from production logs. This adds exactly the missing
    half: the innermost call frames as ``file:line:function``.

    Deliberately NOT the standard traceback: that renders the exception message
    and the offending source lines, both of which can carry question text,
    model output, or provider response bodies. Frame coordinates carry none of
    that -- they are positions in our own code.
    """
    frames = traceback.extract_tb(exc.__traceback__)
    if not frames:
        return "-"
    rendered = [
        f"{os.path.basename(frame.filename)}:{frame.lineno}:{frame.name}"
        for frame in frames[-limit:]
    ]
    return ">".join(rendered)


# Der globale Exception-Handler laeuft in Starlettes ServerErrorMiddleware,
# also AUSSERHALB dieser Middleware: deren Kontextvariable ist dann schon
# zurueckgesetzt und ihr send-Wrapper umgangen. Die ID liegt deshalb zusaetzlich
# im (geteilten) ASGI-Scope, damit Handler, Log-Zeile, 500er-Header und Alert
# dieselbe Kennung tragen.
CORRELATION_SCOPE_KEY = "consensio.correlation_id"


class CorrelationMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        started = time.monotonic()
        status_code = 500
        with correlation_scope(prefix="req") as current:
            scope[CORRELATION_SCOPE_KEY] = current
            async def send_with_correlation(message):
                nonlocal status_code
                if message.get("type") == "http.response.start":
                    status_code = int(message.get("status") or 500)
                    headers = list(message.get("headers") or [])
                    headers.append((b"x-correlation-id", current.encode("ascii")))
                    message["headers"] = headers
                await send(message)

            try:
                await self.app(scope, receive, send_with_correlation)
            finally:
                record_metric(
                    "http",
                    f"{scope.get('method', 'GET')}:{status_code // 100}xx",
                    duration_ms=(time.monotonic() - started) * 1000,
                    outcome="failure" if status_code >= 500 else "success",
                )
