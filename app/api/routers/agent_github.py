"""GitHub for the agent's VM: connecting a user's installation of the app and
the pull request card (agent_github.py, docs/agent-mode.md "GitHub aus der VM").

Connecting works like Google's: ``connect`` hands the popup the app's
installation page and sets a browser cookie; GitHub sends the popup to
``callback``, which passes the code to the window that opened it; ``finish``
(the signed-in user, state, cookie, code) checks with GitHub which
installations and repositories this GitHub user may use and saves only that.
"""
from __future__ import annotations

import secrets

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import Field

from app.api.routers.agent import require_agent_access
from app.api.routers.chat_history import _chat_uid, _raise_store_error
from app.core.rate_limit import limiter
from app.core.security import db_firestore
from app.services.agent_documents import Strict
from app.services.agent_github import GitHubConnections, GitHubUnavailable, PullRequests, configured

router = APIRouter()
COOKIE = "consens_github_oauth"
COOKIE_PATH = "/agent/github"


class Finish(Strict):
    state: str = Field(min_length=32, max_length=200)
    code: str = Field(min_length=1, max_length=4000)


class Decide(Strict):
    expected_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


def owner(request):
    uid = _chat_uid(request)
    require_agent_access(uid)
    return uid


def invoke(uid, operation, operation_name):
    try:
        return JSONResponse(operation(), headers={"Cache-Control": "private, no-store"})
    except GitHubUnavailable as exc:
        raise HTTPException(exc.status if 400 <= exc.status <= 599 else 422, str(exc)) from None
    except HTTPException:
        raise
    except Exception as exc:
        _raise_store_error(exc, operation=operation_name, uid=uid)


@router.get("/agent/github/connection")
@limiter.limit("30/minute")
def connection(request: Request):
    # Seeing and removing the connection keeps working after a downgrade.
    uid = _chat_uid(request)
    return invoke(uid, lambda: GitHubConnections(db_firestore).public(uid), "read GitHub connection")


@router.post("/agent/github/connect")
@limiter.limit("10/minute")
def connect(request: Request):
    uid = owner(request)
    if not configured():
        raise HTTPException(503, "GitHub is not set up on this installation.")
    started = {}

    def operation():
        data, browser = GitHubConnections(db_firestore).start(uid)
        started["browser"] = browser
        return data
    response = invoke(uid, operation, "start GitHub connection")
    # The cookie binds the state to this browser; never in a JSON response.
    secure = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
    response.set_cookie(COOKIE, started["browser"], max_age=600, httponly=True, secure=secure, samesite="lax",
                        path=COOKIE_PATH)
    return response


@router.get("/agent/github/callback")
def callback(request: Request):
    """The app's Callback URL. Hands code and state to the window that
    started the connection; without a code (GitHub showed an existing
    installation) that window asks for the user's authorization next."""
    nonce = secrets.token_urlsafe(24)
    html = """<!doctype html><html><meta charset="utf-8"><title>GitHub connection</title>
<p id="status">Completing GitHub connection…</p><script nonce="NONCE">
const params = new URLSearchParams(location.search);
history.replaceState(null, '', location.pathname);
if (window.opener) {
  window.opener.postMessage({type:'consens-github-oauth',code:params.get('code'),state:params.get('state'),error:params.get('error')}, location.origin);
  document.getElementById('status').textContent='Return to Consens to finish connecting. You may close this window.';
} else { document.getElementById('status').textContent='This window has no active Consens session. Return to Consens and connect GitHub again.'; }
</script></html>""".replace("NONCE", nonce)
    return HTMLResponse(html, headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer",
        "Content-Security-Policy": f"default-src 'none'; script-src 'nonce-{nonce}'; base-uri 'none'; frame-ancestors 'none'"})


@router.post("/agent/github/finish")
@limiter.limit("10/minute")
def finish(request: Request, payload: Finish):
    uid = owner(request)
    try:
        response = invoke(uid, lambda: GitHubConnections(db_firestore).finish(
            uid, payload.state, payload.code, request.cookies.get(COOKIE, "")), "finish GitHub connection")
    except HTTPException as exc:
        # The state is single use either way; never leave the browser secret behind.
        response = JSONResponse({"detail": exc.detail}, status_code=exc.status_code,
                                headers={"Cache-Control": "private, no-store"})
    response.delete_cookie(COOKIE, path=COOKIE_PATH)
    return response


@router.delete("/agent/github/connection")
@limiter.limit("10/minute")
def disconnect(request: Request):
    uid = _chat_uid(request)
    return invoke(uid, lambda: GitHubConnections(db_firestore).disconnect(uid), "disconnect GitHub")


@router.post("/agent/chats/{chat_id}/turns/{turn_id}/pull-request")
@limiter.limit("10/minute")
def create_pull_request(request: Request, chat_id: str, turn_id: str, payload: Decide):
    """The card's "Create pull request": only now does anything go to GitHub."""
    uid = owner(request)
    return invoke(uid, lambda: {"pull_request": PullRequests(db_firestore).confirm(
        uid, chat_id, turn_id, payload.expected_hash)}, "create pull request")


@router.post("/agent/chats/{chat_id}/turns/{turn_id}/pull-request/discard")
@limiter.limit("20/minute")
def discard_pull_request(request: Request, chat_id: str, turn_id: str, payload: Decide):
    uid = _chat_uid(request)
    return invoke(uid, lambda: {"pull_request": PullRequests(db_firestore).discard(
        uid, chat_id, turn_id, payload.expected_hash)}, "discard pull request")
