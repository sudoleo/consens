"""Rate-limited intake for critical failures detected by the app shell."""

import re
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, BackgroundTasks, Body, HTTPException, Request, status

from app.core.rate_limit import limiter
from app.core.sourcemaps import BUNDLE_SCRIPT, resolve_bundle_location
from app.core.version import get_commit_short
from app.services.telegram_notifier import _scrub_alert_text, send_critical_error_notification


router = APIRouter()
_ALLOWED_TYPES = {
    "resource_load_failed",
    "run_failed",
    "consensus_failed",
    "unhandled_error",
    "unhandled_rejection",
}
_ALLOWED_PHASES = {
    "answers",
    "asset_load",
    "browser",
    "browser_promise",
    "browser_runtime",
    "consensus",
    "consensus_connection",
    "markdown_render",
    "model_fanout",
    "preflight",
    "prepare",
}
_GENERIC_MESSAGES = {
    "resource_load_failed": "A required browser script or stylesheet failed to load.",
    "run_failed": "A browser run failed.",
    "consensus_failed": "A browser consensus run failed.",
    "unhandled_error": "An unhandled browser error occurred.",
    "unhandled_rejection": "An unhandled browser promise rejection occurred.",
}
_ALLOWED_RESOURCE_CLASSES = {
    "app_bundle",
    "static_asset",
    "jsdelivr_dependency",
    "firebase_dependency",
    "same_origin_resource",
    "unknown_resource",
}
_ALLOWED_FAILURE_KINDS = {
    "request_failed", "stream_read_failed", "stream_handler_failed",
    "stream_incomplete", "consensus_processing_failed",
}
_ALLOWED_ERROR_NAMES = {
    "Error", "TypeError", "ReferenceError", "RangeError", "SyntaxError",
    "URIError", "EvalError", "AggregateError", "SecurityError", "InvalidStateError",
    "IndexSizeError", "QuotaExceededError", "NetworkError", "NotSupportedError",
}
_BUNDLE_SCRIPT = BUNDLE_SCRIPT
# Nur bei diesen Fehlerarten ist die Browser-Message in aller Regel Code-Text
# ("Cannot read properties of undefined (reading 'x')") und hilft beim Fixen.
# Alles andere (Error, Promise-Rejections mit Provider-Text, ...) bleibt beim
# festen Standardtext.
_MESSAGE_ERROR_NAMES = {"TypeError", "ReferenceError", "RangeError", "SyntaxError"}
_MAX_CLIENT_FRAMES = 5
_LONG_QUOTED = re.compile(r'"[^"]{25,}"|\'[^\']{25,}\'|`[^`]{25,}`')
_URL_TEXT = re.compile(r"\b[a-z][a-z0-9+.-]*://\S+", re.IGNORECASE)
_EMAIL_TEXT = re.compile(r"[^\s@'\"`()]+@[^\s@'\"`()]+\.[A-Za-z]{2,}")
_BUNDLE_ASSET = re.compile(r"dist/(?:(?:head|auth|firebase|demo|app)\.[a-f0-9]{12}\.js|app\.[a-f0-9]{12}\.css)")
_STATIC_ASSETS = {
    "js/analytics-opt-out.js",
    "vendor/marked/12.0.2/marked.min.js",
    "vendor/dompurify/3.4.16/dist/purify.min.js",
    "vendor/katex/0.17.0/dist/katex.min.js",
    "vendor/katex/0.17.0/dist/katex.min.css",
    "vendor/katex/0.17.0/dist/contrib/auto-render.min.js",
}


def _bounded_string(data: dict, field: str, limit: int, *, required: bool = False) -> str:
    value = data.get(field, "")
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise HTTPException(status_code=400, detail=f"{field} must be a string")
    value = value.strip()
    if required and not value:
        raise HTTPException(status_code=400, detail=f"{field} is required")
    if len(value) > limit:
        value = value[:limit]
    return value


def _require_same_origin(request: Request) -> None:
    fetch_site = request.headers.get("sec-fetch-site", "").lower()
    if fetch_site and fetch_site != "same-origin":
        raise HTTPException(status_code=403, detail="Cross-origin reports are not accepted")

    origin = request.headers.get("origin", "").strip()
    if not origin:
        return
    origin_host = urlparse(origin).netloc.lower()
    request_host = request.headers.get("host", "").lower()
    if not origin_host or origin_host != request_host:
        raise HTTPException(status_code=403, detail="Cross-origin reports are not accepted")


def _route_family(path: str) -> str:
    """Keep operational routing context without forwarding IDs or slugs."""
    if path in {"/", "/app", "/app/watches", "/admin", "/admin/benchmark"}:
        return path
    if path.startswith("/s/"):
        return "/s/{share_id}"
    if path.startswith("/topics/"):
        return "/topics/{slug}"
    if path.startswith("/app/"):
        return "/app/{view}"
    if path.startswith("/admin/"):
        return "/admin/{view}"
    return "/other"

def _coordinate(value) -> Optional[int]:
    return value if type(value) is int and 0 < value <= 10_000_000 else None


def _bundle_frame(script, line, column) -> Optional[str]:
    """Ein Frame nur aus Allowlist-Bundle + Zahlen, ueber die Source-Map
    aufgeloest. Freitext (URLs, Funktionsnamen) kommt hier nie durch."""
    if not isinstance(script, str) or not _BUNDLE_SCRIPT.fullmatch(script):
        return None
    line, column = _coordinate(line), _coordinate(column)
    if line is None or column is None:
        return None
    return resolve_bundle_location(script, line, column) or f"{script}:{line}:{column}"


def _client_frames(raw) -> list[str]:
    if not isinstance(raw, list):
        return []
    frames = []
    for item in raw[:_MAX_CLIENT_FRAMES]:
        if isinstance(item, (list, tuple)) and len(item) == 3:
            frame = _bundle_frame(*item)
            if frame:
                frames.append(frame)
    return frames


def _js_error_message(raw: str, error_name: str) -> str:
    """Die Browser-Message eines Code-Fehlers, entschaerft.

    Lange String-Literale (z. B. JSON.parse-Ausschnitte aus Modellantworten)
    werden zu "…", URLs und Mailadressen zu Platzhaltern, Secrets ueber
    ``_scrub_alert_text`` entfernt; hoechstens 200 Zeichen."""
    text = " ".join(str(raw or "").split())
    for prefix in ("Uncaught ", f"{error_name}: "):
        if text.startswith(prefix):
            text = text[len(prefix):]
    text = _LONG_QUOTED.sub("…", text)
    text = _URL_TEXT.sub("[url]", text)
    text = _EMAIL_TEXT.sub("[email]", text)
    return _scrub_alert_text(text, limit=200)


@router.post("/api/client-errors", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("5/minute")
def report_client_error(
    request: Request,
    background_tasks: BackgroundTasks,
    data: dict = Body(...),
):
    _require_same_origin(request)
    error_type = _bounded_string(data, "type", 80, required=True)
    if error_type not in _ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported error type")

    # Validate the client fields, but never forward their free-form content to
    # logs or Telegram. Browser errors routinely contain prompts, URLs, e-mail
    # addresses, access tokens, and provider response bodies. Einzige Ausnahme:
    # die entschaerfte Message von Code-Fehlern (_MESSAGE_ERROR_NAMES).
    raw_message = _bounded_string(data, "message", 700, required=True)
    _bounded_string(data, "details", 1_500)
    _bounded_string(data, "stack", 4_000)
    raw_phase = _bounded_string(data, "phase", 80)
    phase = raw_phase if raw_phase in _ALLOWED_PHASES else "browser"
    raw_path = _bounded_string(data, "path", 300)
    path = _route_family(raw_path) if raw_path.startswith("/") else "/other"
    raw_resource_class = _bounded_string(data, "resource_class", 80)
    resource_class = (
        raw_resource_class
        if error_type == "resource_load_failed"
        and raw_resource_class in _ALLOWED_RESOURCE_CLASSES
        else ""
    )
    report = {
        "source": "browser",
        "type": error_type,
        "phase": phase,
        "message": _GENERIC_MESSAGES[error_type],
        "path": path,
    }
    commit = get_commit_short()
    if commit:
        report["commit"] = commit
    # Welcher App-Build im Browser lief (der Hash gehoert zum Deploy).
    bundle = _bounded_string(data, "bundle", 100)
    if _BUNDLE_SCRIPT.fullmatch(bundle):
        report["bundle"] = bundle
    if resource_class:
        report["resource_class"] = resource_class
    if error_type == "resource_load_failed":
        asset = _bounded_string(data, "asset", 150)
        if asset in _STATIC_ASSETS or _BUNDLE_ASSET.fullmatch(asset):
            report["asset"] = asset
    raw_failure_kind = _bounded_string(data, "failure_kind", 80)
    if error_type == "consensus_failed" and raw_failure_kind in _ALLOWED_FAILURE_KINDS:
        report["failure_kind"] = raw_failure_kind
    if error_type in {"unhandled_error", "unhandled_rejection"}:
        error_name = _bounded_string(data, "error_name", 80)
        if error_name in _ALLOWED_ERROR_NAMES:
            report["error_name"] = error_name
            if error_name in _MESSAGE_ERROR_NAMES:
                error_message = _js_error_message(raw_message, error_name)
                if error_message:
                    report["error_message"] = error_message
        script = _bounded_string(data, "script", 100)
        if _BUNDLE_SCRIPT.fullmatch(script):
            report["script"] = script
            for field in ("line", "column"):
                number = _coordinate(data.get(field))
                if number is not None:
                    report[field] = number
            if "line" in report and "column" in report:
                location = resolve_bundle_location(script, report["line"], report["column"])
                if location:
                    report["location"] = location
        frames = _client_frames(data.get("frames"))
        if frames:
            report["frames"] = frames
    background_tasks.add_task(send_critical_error_notification, report)
    return {"status": "accepted"}
