"""Rate-limited intake for critical failures detected by the app shell."""

import re
from urllib.parse import urlparse

from fastapi import APIRouter, BackgroundTasks, Body, HTTPException, Request, status

from app.core.rate_limit import limiter
from app.services.telegram_notifier import send_critical_error_notification


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
_BUNDLE_SCRIPT = re.compile(r"(?:head|auth|firebase|demo|app)\.[a-f0-9]{12}\.js")


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
    # addresses, access tokens, and provider response bodies.
    _bounded_string(data, "message", 700, required=True)
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
    if resource_class:
        report["resource_class"] = resource_class
    raw_failure_kind = _bounded_string(data, "failure_kind", 80)
    if error_type == "consensus_failed" and raw_failure_kind in _ALLOWED_FAILURE_KINDS:
        report["failure_kind"] = raw_failure_kind
    if error_type in {"unhandled_error", "unhandled_rejection"}:
        error_name = _bounded_string(data, "error_name", 80)
        if error_name in _ALLOWED_ERROR_NAMES:
            report["error_name"] = error_name
        script = _bounded_string(data, "script", 100)
        if _BUNDLE_SCRIPT.fullmatch(script):
            report["script"] = script
            for field in ("line", "column"):
                number = data.get(field)
                if type(number) is int and 0 < number <= 10_000_000:
                    report[field] = number
    background_tasks.add_task(send_critical_error_notification, report)
    return {"status": "accepted"}
