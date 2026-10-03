"""User-only connection controls and exact-content action confirmations."""
from __future__ import annotations
import secrets
from urllib.parse import urlparse

from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import Field

from app.api.routers.agent import require_agent_access
from app.api.routers.chat_history import _chat_uid, _raise_store_error
from app.core.rate_limit import limiter
from app.core.security import db_firestore
from app.services.agent_documents import Strict
from app.services.agent_actions import AgentActions
from app.services.google_connections import GoogleConnections, GoogleError, available, configuration, drive_picker, writes_enabled

router = APIRouter()


class Connect(Strict):
    capabilities: list[str] = Field(min_length=1, max_length=4)
    connection_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")


class Finish(Strict):
    state: str = Field(min_length=32, max_length=200)
    code: str = Field(min_length=1, max_length=4000)


class Confirm(Strict):
    expected_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class Renew(Confirm):
    remove_recipients: list[str] = Field(default_factory=list, max_length=30)


def owner(request):
    uid = _chat_uid(request)
    require_agent_access(uid)
    return uid


def account_owner(request):
    # Seeing and removing stored Google access must keep working after a
    # downgrade; only new connections and actions require Agent access.
    return _chat_uid(request)


def invoke(uid, operation):
    try:
        return JSONResponse(operation(), headers={"Cache-Control": "private, no-store"})
    except GoogleError as exc:
        raise HTTPException(exc.status if 400 <= exc.status <= 599 else 422, str(exc)) from None
    except HTTPException:
        raise
    except Exception as exc:
        _raise_store_error(exc, operation="access Google integration", uid=uid)


@router.get("/agent/google/connections")
@limiter.limit("30/minute")
def connections(request: Request):
    uid = account_owner(request)
    # One answer for every Google entry point: account connections (Gmail and
    # Calendar), whether Consens may write back, and the public Drive picker
    # configuration (Drive works without a stored connection).
    return invoke(uid, lambda: {"configured": available(), "writes": writes_enabled(), "drive": drive_picker(),
        "connections": GoogleConnections(db_firestore).list(uid)})


@router.post("/agent/google/connect")
@limiter.limit("10/minute")
def connect(request: Request, payload: Connect):
    uid = owner(request)
    def operation():
        data, browser = GoogleConnections(db_firestore).start(uid, payload.capabilities, connection_id=payload.connection_id)
        return {**data, "browser": browser}
    response = invoke(uid, operation)
    # Cookie secret never belongs in a JSON response or model-visible state.
    import json
    data = json.loads(response.body)
    browser = data.pop("browser")
    response = JSONResponse(data, headers={"Cache-Control": "private, no-store"})
    response.set_cookie("consens_google_oauth", browser, max_age=600, httponly=True, secure=urlparse(configuration()["REDIRECT_URI"]).scheme == "https",
        samesite="lax", path="/agent/google")
    return response


@router.get("/agent/google/callback")
def callback(request: Request):
    # No third-party assets, no template interpolation of the authorization code.
    # Finish requires the authenticated original user, one-time state and cookie.
    nonce = secrets.token_urlsafe(24)
    html = """<!doctype html><html><meta charset="utf-8"><title>Google connection</title>
<p id="status">Completing Google connection…</p><script nonce="NONCE">
const params = new URLSearchParams(location.search);
history.replaceState(null, '', location.pathname);
if (window.opener) {
  window.opener.postMessage({type:'consens-google-oauth',code:params.get('code'),state:params.get('state'),error:params.get('error')}, location.origin);
  document.getElementById('status').textContent='Return to Consens to finish connecting. You may close this window.';
} else { document.getElementById('status').textContent='This connection window has no active Consens session. Return to Consens and connect again.'; }
</script></html>""".replace("NONCE", nonce)
    return HTMLResponse(html, headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer",
        "Content-Security-Policy": f"default-src 'none'; script-src 'nonce-{nonce}'; base-uri 'none'; frame-ancestors 'none'"})


@router.post("/agent/google/finish")
@limiter.limit("10/minute")
def finish(request: Request, payload: Finish):
    uid = owner(request)
    try:
        response = invoke(uid, lambda: {"connection": GoogleConnections(db_firestore).finish(uid, payload.state, payload.code, request.cookies.get("consens_google_oauth", ""))})
    except HTTPException as exc:
        # The state is single use either way; never leave the browser secret behind.
        response = JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers={"Cache-Control": "private, no-store"})
    response.delete_cookie("consens_google_oauth", path="/agent/google")
    return response


@router.delete("/agent/google/connections/{connection_id}")
@limiter.limit("10/minute")
def disconnect(request: Request, connection_id: str):
    uid = account_owner(request)
    return invoke(uid, lambda: GoogleConnections(db_firestore).disconnect(uid, connection_id))


@router.get("/agent/google/connections/{connection_id}/calendars")
@limiter.limit("30/minute")
def calendars(request: Request, connection_id: str, page_token: str = Query(default="", max_length=2000)):
    uid = owner(request)
    def operation():
        params = {"maxResults": 50, "minAccessRole": "reader"}
        if page_token:
            params["pageToken"] = page_token
        result = GoogleConnections(db_firestore).api(uid, connection_id, "calendar_read", "GET", "/calendar/v3/users/me/calendarList", params=params)
        return {"calendars": [{key: item[key] for key in ("id", "summary", "timeZone", "primary", "accessRole") if key in item} for item in result.get("items", [])[:50]],
            "next_page_token": result.get("nextPageToken")}
    return invoke(uid, operation)


@router.get("/agent/chats/{chat_id}/actions")
@limiter.limit("60/minute")
def actions(request: Request, chat_id: str):
    uid = owner(request)
    def operation():
        service = AgentActions(db_firestore)
        actions = service.list(uid, chat_id)
        from app.services.google_connections import now
        chat_ref = service.files.chats._chat_ref(uid, chat_id)
        current = now().isoformat()
        evidence = [data for data in (s.to_dict() or {} for s in chat_ref.collection("google_evidence").order_by("created_at").limit(100).stream())
            if data.get("expires_at", "") > current]
        # The browser needs this before sending: every message in a chat that
        # already holds Google data requires fresh model-sharing consent.
        chat = chat_ref.get().to_dict() or {}
        # google_consent: the user already allowed sharing this chat's Google
        # data with its models; later messages need no new checkbox.
        return {"actions": actions, "evidence": evidence, "google_data": bool(chat.get("google_data")),
            "google_consent": bool(chat.get("google_data") and chat.get("google_consent")), "writes": writes_enabled()}
    return invoke(uid, operation)


@router.post("/agent/chats/{chat_id}/actions/{action_id}/confirm")
@limiter.limit("10/minute")
def confirm_action(request: Request, chat_id: str, action_id: str, payload: Confirm):
    uid = owner(request)
    return invoke(uid, lambda: {"action": AgentActions(db_firestore).confirm(uid, chat_id, action_id, payload.expected_hash)})


@router.post("/agent/chats/{chat_id}/actions/{action_id}/renew")
@limiter.limit("10/minute")
def renew_action(request: Request, chat_id: str, action_id: str, payload: Renew):
    """Prepare the stored proposal again under the current Google grant.

    No model call and no new content: optionally fewer email recipients.
    The new version supersedes the old one and needs its own review.
    """
    uid = owner(request)
    return invoke(uid, lambda: {"action": AgentActions(db_firestore).renew(uid, chat_id, action_id, payload.expected_hash,
        remove_recipients=payload.remove_recipients)})


@router.post("/agent/chats/{chat_id}/actions/{action_id}/reject")
@limiter.limit("20/minute")
def reject_action(request: Request, chat_id: str, action_id: str, payload: Confirm):
    uid = owner(request)
    return invoke(uid, lambda: {"action": AgentActions(db_firestore).reject(uid, chat_id, action_id, payload.expected_hash)})


@router.post("/agent/chats/{chat_id}/actions/{action_id}/status")
@limiter.limit("20/minute")
def action_status(request: Request, chat_id: str, action_id: str):
    uid = owner(request)
    return invoke(uid, lambda: {"action": AgentActions(db_firestore).reconcile(uid, chat_id, action_id)})
