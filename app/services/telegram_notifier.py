"""Best-effort Telegram notifications for server-side maintenance workflows."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
import time
from collections import deque
from datetime import datetime, timezone
from typing import Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.observability import safe_exception


DEFAULT_ADMIN_URL = "https://www.consens.io/admin#seo"
_CRITICAL_DEDUPE_SECONDS = 10 * 60
_CRITICAL_RATE_WINDOW_SECONDS = 10 * 60
# Eigene Budgets je Quelle: ein Sturm aus Browser-Meldungen (5/min pro IP am
# Endpoint, aber beliebig viele Clients) darf keinen Serverfehler verdraengen.
_CRITICAL_RATE_LIMITS = {"server": 10, "browser": 5}
_CRITICAL_SUPPRESSED_MAX = 256
_ALERT_FRAMES_MAX = 8
_critical_lock = threading.Lock()
_critical_seen: dict[str, float] = {}
_critical_sent_at: dict[str, deque[float]] = {
    bucket: deque() for bucket in _CRITICAL_RATE_LIMITS
}
_critical_suppressed: dict[str, int] = {}
_REGISTRATION_DEDUPE_SECONDS = 24 * 60 * 60
_registration_lock = threading.Lock()
_registration_seen: dict[str, float] = {}

_SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;]+"),
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+"),
    re.compile(
        r"(?i)([?&](?:access_token|api_key|id_token|key|password|secret|token)=)[^&#\s]+"
    ),
    re.compile(
        r"(?i)((?:api[_-]?key|id[_-]?token|password|secret|token)\s*[:=]\s*)[^\s,;]+"
    ),
    re.compile(r"\b(?:sk[-_][A-Za-z0-9_-]{12,}|cns_live_[A-Za-z0-9_-]{12,})\b"),
    re.compile(r"\bAIza[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\b\d{6,}:[A-Za-z0-9_-]{20,}\b"),
)


def bot_token() -> str:
    return str(os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()


def _telegram_description(error: HTTPError) -> str:
    try:
        decoded = json.loads(error.read(4_096) or b"{}")
    except (OSError, ValueError, AttributeError, TypeError):
        return ""
    if not isinstance(decoded, dict):
        return ""
    return _scrub_alert_text(decoded.get("description"), limit=200)


def alert_environment() -> str:
    """Wo der Prozess laeuft. Ohne Render-Variablen ist es ein lokaler Lauf,
    auch wenn die .env einen Bot-Token mitbringt -- frueher stand dann
    faelschlich "production" im Alert. ``ENVIRONMENT`` uebersteuert lokal."""
    on_render = bool(os.environ.get("RENDER") or os.environ.get("RENDER_SERVICE_NAME"))
    if on_render:
        name = (
            os.environ.get("RENDER_SERVICE_NAME")
            or os.environ.get("ENVIRONMENT")
            or "production"
        )
    else:
        name = os.environ.get("ENVIRONMENT") or "local"
    return _scrub_alert_text(name, limit=80)


def call_bot_api(method: str, payload: dict, *, timeout: int = 30) -> dict:
    """Call one Telegram Bot API method without leaking credentials.

    The structured result lets user-facing notification flows distinguish a
    blocked bot (HTTP 403) from temporary network failures. Maintenance
    notifications keep their existing best-effort semantics.
    """
    token = bot_token()
    attempted_at = datetime.now(timezone.utc).isoformat()
    if not token:
        return {"status": "skipped_not_configured", "attempted_at": attempted_at}
    request = Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
        decoded = json.loads(raw or b"{}")
    except HTTPError as exc:
        # Telegram erklaert Ablehnungen im Body ("Bad Request: chat not
        # found"). Die Beschreibung ist Betriebsdiagnose, nie unser Text; der
        # Token steht nur in der URL und wird nie geloggt.
        description = _telegram_description(exc)
        logging.warning(
            "Telegram Bot API %s failed category=%s description=%s",
            method,
            safe_exception(exc),
            description or "-",
        )
        return {
            "status": "failed_http", "http_status": int(exc.code),
            "description": description,
            "attempted_at": attempted_at,
        }
    except (URLError, TimeoutError, OSError, ValueError):
        logging.warning("Telegram Bot API %s failed with a network/response error", method)
        return {"status": "failed_network", "attempted_at": attempted_at}
    if decoded.get("ok") is False:
        description = _scrub_alert_text(decoded.get("description"), limit=200)
        logging.warning(
            "Telegram Bot API %s returned ok:false error_code=%s description=%s",
            method,
            decoded.get("error_code"),
            description or "-",
        )
        return {
            "status": "failed_api",
            "error_code": decoded.get("error_code"),
            "description": description,
            "retry_after": ((decoded.get("parameters") or {}).get("retry_after")),
            "attempted_at": attempted_at,
        }
    return {
        "status": "sent", "attempted_at": attempted_at,
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "result": decoded.get("result"),
    }


def send_bot_message(chat_id, text: str, *, reply_markup: dict | None = None,
                     parse_mode: str = "") -> dict:
    payload = {
        "chat_id": str(chat_id),
        "text": str(text or "")[:4096],
        "disable_web_page_preview": True,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return call_bot_api("sendMessage", payload)


def _scrub_alert_text(value, *, limit: int) -> str:
    text = str(value or "").replace("\x00", "").strip()
    for pattern in _SECRET_PATTERNS:
        if pattern.groups:
            text = pattern.sub(r"\1[redacted]", text)
        else:
            text = pattern.sub("[redacted]", text)
    return text[:limit]


def _critical_chat_id() -> str:
    return str(
        os.environ.get("CRITICAL_ERROR_TELEGRAM_CHAT_ID")
        or os.environ.get("TELEGRAM_CHAT_ID")
        or ""
    ).strip()


def reset_critical_state() -> None:
    """Test-Helfer: Dedup-, Budget- und Unterdrueckungszaehler leeren."""
    with _critical_lock:
        _critical_seen.clear()
        _critical_suppressed.clear()
        for stamps in _critical_sent_at.values():
            stamps.clear()


def _alert_bucket(report: Mapping) -> str:
    return "browser" if str(report.get("source") or "") == "browser" else "server"


def _alert_frames(report: Mapping) -> list[str]:
    frames = report.get("frames")
    if not isinstance(frames, (list, tuple)):
        return []
    cleaned = (_scrub_alert_text(frame, limit=160) for frame in frames[:_ALERT_FRAMES_MAX])
    return [frame for frame in cleaned if frame]


def _browser_location(report: Mapping) -> str:
    script = _scrub_alert_text(report.get("script"), limit=100)
    if not script:
        return ""
    return f"{script}:{report.get('line', 0)}:{report.get('column', 0)}"


def critical_fingerprint(report: Mapping) -> str:
    """Kurzer, stabiler Schluessel fuer "derselbe Fehler an derselben Stelle".

    Bewusst ohne Message und Zeitpunkt: die Quelle, der Typ, der Ort im
    Ablauf und die innerste Codestelle. Er dient zugleich zum Dedup und als
    ``fp=`` im Alert, damit ein wiederkehrender Fehler wiedererkennbar ist.
    """
    frames = _alert_frames(report)
    parts = (
        _scrub_alert_text(report.get("source") or "server", limit=40),
        _scrub_alert_text(report.get("type") or "unexpected_error", limit=80),
        _scrub_alert_text(report.get("phase"), limit=80),
        _scrub_alert_text(report.get("path"), limit=200),
        _scrub_alert_text(report.get("resource_class"), limit=80),
        _scrub_alert_text(report.get("asset"), limit=150),
        _scrub_alert_text(report.get("failure_kind"), limit=80),
        _scrub_alert_text(report.get("error_name"), limit=80),
        _scrub_alert_text(report.get("location"), limit=200) or _browser_location(report),
        frames[0] if frames else "",
    )
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:8]


def _reserve_critical_delivery(fingerprint: str, bucket: str = "server") -> tuple[str, int, float]:
    """Bound alert storms per process and collapse identical failures.

    Returns the reservation status, how many alerts of this fingerprint were
    suppressed since its last delivered alert, and the budget stamp (needed to
    release the slot again when the send fails)."""
    now = time.monotonic()
    cutoff = now - _CRITICAL_RATE_WINDOW_SECONDS
    limit = _CRITICAL_RATE_LIMITS.get(bucket, _CRITICAL_RATE_LIMITS["server"])
    with _critical_lock:
        stamps = _critical_sent_at.setdefault(bucket, deque())
        for queue in _critical_sent_at.values():
            while queue and queue[0] <= cutoff:
                queue.popleft()
        for key, seen_at in list(_critical_seen.items()):
            if seen_at <= now - _CRITICAL_DEDUPE_SECONDS:
                _critical_seen.pop(key, None)
        if fingerprint in _critical_seen or len(stamps) >= limit:
            status = "deduplicated" if fingerprint in _critical_seen else "rate_limited"
            _critical_suppressed[fingerprint] = _critical_suppressed.get(fingerprint, 0) + 1
            while len(_critical_suppressed) > _CRITICAL_SUPPRESSED_MAX:
                _critical_suppressed.pop(next(iter(_critical_suppressed)))
            return status, 0, now
        _critical_seen[fingerprint] = now
        stamps.append(now)
        suppressed = _critical_suppressed.pop(fingerprint, 0)
    return "reserved", suppressed, now


def _release_critical_delivery(fingerprint: str, bucket: str, stamp: float, suppressed: int) -> None:
    """A failed send must not block the next alert of this fingerprint."""
    with _critical_lock:
        if _critical_seen.get(fingerprint) == stamp:
            _critical_seen.pop(fingerprint, None)
        try:
            _critical_sent_at.get(bucket, deque()).remove(stamp)
        except ValueError:
            pass
        if suppressed:
            _critical_suppressed[fingerprint] = _critical_suppressed.get(fingerprint, 0) + suppressed


def _fix_context(report: Mapping, fingerprint: str, frames: list[str]) -> str:
    """Die eine Zeile, die sich unveraendert in Claude Code einfuegen laesst."""
    fields = [("fp", fingerprint)]
    for key, field, limit in (
        ("commit", "commit", 12),
        ("route", "path", 200),
        ("corr", "correlation_id", 64),
        ("bundle", "bundle", 100),
        ("loc", "location", 200),
    ):
        value = _scrub_alert_text(report.get(field), limit=limit)
        if value:
            fields.append((key, value.replace(" ", "_") if key == "bundle" else value))
    if not report.get("location"):
        location = _browser_location(report)
        if location:
            fields.append(("loc", location))
    if frames:
        fields.append(("frames", " < ".join(frames)))
    return "fix-context: " + " ".join(f"{key}={value}" for key, value in fields)


def _critical_error_message(report: Mapping, *, fingerprint: str = "", suppressed: int = 0) -> str:
    fingerprint = fingerprint or critical_fingerprint(report)
    source = _scrub_alert_text(report.get("source") or "server", limit=40)
    error_type = _scrub_alert_text(report.get("type") or "unexpected_error", limit=80)
    phase = _scrub_alert_text(report.get("phase"), limit=80)
    message = _scrub_alert_text(report.get("message") or "No message", limit=700)
    path = _scrub_alert_text(report.get("path"), limit=300)
    resource_class = _scrub_alert_text(report.get("resource_class"), limit=80)
    details = _scrub_alert_text(report.get("details"), limit=1_200)
    stack = _scrub_alert_text(report.get("stack"), limit=1_800)
    instance = _scrub_alert_text(report.get("instance"), limit=60)
    commit = _scrub_alert_text(report.get("commit"), limit=12)
    correlation = _scrub_alert_text(report.get("correlation_id"), limit=64)
    status = report.get("status")
    frames = _alert_frames(report)
    lines = [
        "🚨 consens.io critical error",
        f"Source: {source}",
        f"Type: {error_type}",
        f"Environment: {alert_environment()}",
    ]
    if instance:
        lines.append(f"Instance: {instance}")
    if commit:
        lines.append(f"Commit: {commit}")
    lines.append(f"Time: {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    if phase:
        lines.append(f"Phase: {phase}")
    if path:
        if type(status) is int:
            lines.append(f"Route: {path} -> {status}")
        else:
            lines.append(f"Path: {path}")
    if correlation:
        lines.append(f"Correlation: {correlation}")
    if resource_class:
        lines.append(f"Resource: {resource_class}")
    asset = _scrub_alert_text(report.get("asset"), limit=150)
    if asset:
        lines.append(f"Asset: {asset}")
    bundle = _scrub_alert_text(report.get("bundle"), limit=100)
    if bundle:
        lines.append(f"Bundle: {bundle}")
    failure_kind = _scrub_alert_text(report.get("failure_kind"), limit=80)
    if failure_kind:
        lines.append(f"Failure: {failure_kind}")
    error_name = _scrub_alert_text(report.get("error_name"), limit=80)
    error_message = _scrub_alert_text(report.get("error_message"), limit=200)
    if error_name:
        lines.append(f"Error: {error_name}" + (f": {error_message}" if error_message else ""))
    bundle_location = _browser_location(report)
    location = _scrub_alert_text(report.get("location"), limit=200)
    if location and bundle_location:
        lines.append(f"Location: {location} (bundle {bundle_location})")
    elif location or bundle_location:
        lines.append(f"Location: {location or bundle_location}")
    if suppressed:
        lines.append(f"(+{int(suppressed)} similar since last alert)")
    lines.extend(("", message))
    if frames:
        lines.extend(("", "Frames (innermost first):", *frames))
    if details:
        lines.extend(("", f"Details: {details}"))
    if stack:
        lines.extend(("", f"Stack: {stack}"))
    # Der fix-context-Block ueberlebt jede Kuerzung: gekuerzt wird davor.
    tail = "\n\n" + _fix_context(report, fingerprint, frames)[:1_500]
    body = "\n".join(lines)
    return body[: 4096 - len(tail)] + tail


def _critical_target(report: Mapping):
    attempted_at = datetime.now(timezone.utc).isoformat()
    chat_id = _critical_chat_id()
    if not bot_token() or not chat_id:
        return None, {"status": "skipped_not_configured", "attempted_at": attempted_at}
    fingerprint = critical_fingerprint(report)
    bucket = _alert_bucket(report)
    reservation, suppressed, stamp = _reserve_critical_delivery(fingerprint, bucket)
    if reservation != "reserved":
        return None, {"status": reservation, "fingerprint": fingerprint, "attempted_at": attempted_at}
    return (chat_id, fingerprint, bucket, suppressed, stamp, attempted_at), None


def _deliver_critical(report: Mapping, target) -> dict:
    chat_id, fingerprint, bucket, suppressed, stamp, attempted_at = target
    try:
        result = send_bot_message(
            chat_id,
            _critical_error_message(report, fingerprint=fingerprint, suppressed=suppressed),
        )
    except Exception:
        # This function is called from exception paths and must never create a
        # second failure or log secrets from a Telegram request URL.
        _release_critical_delivery(fingerprint, bucket, stamp, suppressed)
        logging.warning("Critical Telegram notification failed safely fp=%s", fingerprint)
        return {"status": "failed_safely", "fingerprint": fingerprint, "attempted_at": attempted_at}
    if result.get("status") != "sent":
        _release_critical_delivery(fingerprint, bucket, stamp, suppressed)
        logging.warning(
            "Critical Telegram notification not delivered fp=%s status=%s http_status=%s "
            "error_code=%s description=%s",
            fingerprint,
            result.get("status"),
            result.get("http_status", "-"),
            result.get("error_code", "-"),
            result.get("description") or "-",
        )
    result.pop("result", None)
    result["fingerprint"] = fingerprint
    return result


def send_critical_error_notification(report: Mapping) -> dict:
    """Send a redacted, deduplicated operational alert without raising."""
    target, skipped = _critical_target(report)
    if skipped is not None:
        return skipped
    return _deliver_critical(report, target)


def dispatch_critical_error_notification(report: Mapping) -> dict:
    """Fire-and-forget: reserve now, send on a daemon thread.

    Unabhaengig von jedem Response-Lebenszyklus. Als BackgroundTask am
    500er lief der Alert nie, wenn die Antwort schon begonnen hatte (SSE).
    Dedup und Budget greifen synchron, deshalb startet ein Fehlersturm
    hoechstens so viele Threads, wie das Budget Alerts erlaubt.
    """
    try:
        target, skipped = _critical_target(report)
        if skipped is not None:
            return skipped
        threading.Thread(
            target=_deliver_critical,
            args=(dict(report), target),
            name="critical-alert",
            daemon=True,
        ).start()
        return {"status": "dispatched", "fingerprint": target[1], "attempted_at": target[5]}
    except Exception:
        logging.warning("Critical Telegram notification could not be dispatched")
        return {"status": "failed_safely"}


def _new_user_registration_message(registration_method: str) -> str:
    method = _scrub_alert_text(registration_method or "unknown", limit=60)
    return "\n".join((
        "👤 consens.io new user registered",
        f"Method: {method}",
        f"Environment: {alert_environment()}",
        f"Time: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
    ))


def _reserve_registration_delivery(dedupe_key: str) -> tuple[str, str]:
    if not dedupe_key:
        return "reserved", ""
    fingerprint = hashlib.sha256(str(dedupe_key).encode("utf-8")).hexdigest()
    now = time.monotonic()
    with _registration_lock:
        for key, seen_at in list(_registration_seen.items()):
            if seen_at <= now - _REGISTRATION_DEDUPE_SECONDS:
                _registration_seen.pop(key, None)
        if fingerprint in _registration_seen:
            return "deduplicated", fingerprint
        _registration_seen[fingerprint] = now
    return "reserved", fingerprint


def _release_registration_delivery(fingerprint: str) -> None:
    if not fingerprint:
        return
    with _registration_lock:
        _registration_seen.pop(fingerprint, None)


def send_new_user_registration_notification(
    registration_method: str,
    dedupe_key: str = "",
) -> dict:
    """Send a PII-free registration alert without affecting sign-up."""
    attempted_at = datetime.now(timezone.utc).isoformat()
    chat_id = _critical_chat_id()
    if not bot_token() or not chat_id:
        return {"status": "skipped_not_configured", "attempted_at": attempted_at}

    reservation, fingerprint = _reserve_registration_delivery(dedupe_key)
    if reservation != "reserved":
        return {"status": reservation, "attempted_at": attempted_at}

    try:
        result = send_bot_message(
            chat_id,
            _new_user_registration_message(registration_method),
        )
    except Exception:
        _release_registration_delivery(fingerprint)
        logging.warning("New-user Telegram notification failed safely")
        return {"status": "failed_safely", "attempted_at": attempted_at}
    if result.get("status") != "sent":
        _release_registration_delivery(fingerprint)
    result.pop("result", None)
    return result


def _group_count(review: dict, name: str) -> int:
    return len(((review.get("groups") or {}).get(name) or []))


def _review_findings(review: dict) -> list[str]:
    findings = review.get("findings") or {}
    lines = []
    for marker, key in (("+", "positive"), ("-", "negative")):
        for item in (findings.get(key) or [])[:3]:
            text = str(item or "").strip()
            if text:
                lines.append(f"{marker} {text[:300]}")
    return lines


def _review_delta_line(review: dict) -> str:
    delta = review.get("delta") or {}
    if not delta.get("comparable"):
        return "Change since last review: no comparable previous run"
    changed = delta.get("changed") or []
    new_pages = delta.get("new_pages") or []
    if not changed and not new_pages:
        return "Change since last review: none"
    parts = [
        f"{str(item.get('title') or item.get('page_id') or '')[:60]}: "
        f"{item.get('from')} -> {item.get('to')}"
        for item in changed[:3]
    ]
    if len(changed) > 3:
        parts.append(f"+{len(changed) - 3} more")
    if new_pages:
        parts.append(f"{len(new_pages)} new")
    return "Change since last review: " + "; ".join(parts)


def _review_judge_line(review: dict) -> str:
    judge_error = str(review.get("judge_error") or "").strip()
    if review.get("judge_called"):
        return "Portfolio judge: answered"
    if judge_error:
        return f"Portfolio judge: FAILED - {judge_error[:200]}"
    return "Portfolio judge: not called"


def _review_message(review: dict) -> str:
    status = str(review.get("status") or "unknown")
    pages = list(review.get("pages") or [])
    decisions = review.get("editorial_decisions") or {}
    editorial_total = _group_count(review, "manual_improvement")
    editorial_open = max(0, editorial_total - len(decisions))
    prompt_pending = bool(
        review.get("proposed_topic_brief")
        and review.get("topic_brief_decision", "pending") == "pending"
    )
    summary = str(review.get("summary") or "No summary available.").strip()
    admin_url = str(os.environ.get("SEO_ADMIN_URL") or DEFAULT_ADMIN_URL).strip()
    counts = review.get("status_counts") or {}
    status_line = ", ".join(f"{name} {count}" for name, count in counts.items())
    lines = [
        f"SEO review {status}",
        "",
        summary[:1_200],
    ]
    findings = _review_findings(review)
    if findings:
        lines.extend(["", *findings])
    lines.extend([
        "",
        _review_delta_line(review),
        f"Pages reviewed: {len(pages)}" + (f" ({status_line})" if status_line else ""),
        _review_judge_line(review),
        f"Editorial decisions open: {editorial_open}",
        f"Publisher prompt decision: {'required' if prompt_pending else 'none'}",
        "",
        admin_url,
    ])
    return "\n".join(lines)


def send_seo_review_notification(review: dict) -> dict:
    """Notify after every terminal SEO review without failing the review itself."""
    configured_token = bot_token()
    # Accept the same chat id the critical alerts use. A deployment that only
    # set CRITICAL_ERROR_TELEGRAM_CHAT_ID used to drop every review silently.
    chat_id = _critical_chat_id()
    attempted_at = datetime.now(timezone.utc).isoformat()
    if not configured_token or not chat_id:
        return {
            "status": "skipped_not_configured",
            "attempted_at": attempted_at,
        }

    payload = {
        "chat_id": chat_id,
        "text": _review_message(review),
        "disable_web_page_preview": True,
    }
    result = call_bot_api("sendMessage", payload)
    result.pop("result", None)
    return result
