"""Same-origin proxy for Firebase Auth's hosted sign-in helpers.

Google sign-in runs through ``<authDomain>/__/auth/handler`` (the popup or
redirect target) and ``<authDomain>/__/auth/iframe`` (the channel that hands
the result back to the page). With the default ``<project>.firebaseapp.com``
both live on a foreign site: Google's account chooser says "continue to
consensai.firebaseapp.com", and browsers that partition third-party storage
(Safari, Firefox, Chrome) break the redirect flow entirely.

Firebase's documented fix ("redirect best practices", reverse-proxy option)
is to forward ``/__/auth/*`` and ``/__/firebase/init.json`` transparently from
the app's own origin. Once ``FIREBASE_AUTH_DOMAIN`` names this host, the
whole sign-in stays first-party and mobile can use the redirect flow.

The proxy forwards nothing of the user's: no cookies, no Authorization, only
the request line, a handful of content-negotiation headers and the body of the
handler's POST. The upstream host is derived from the project id, never from
the request.
"""

from __future__ import annotations

import logging
import os

import httpx
from fastapi import APIRouter, Request, Response

from app.core.observability import safe_exception


router = APIRouter()

PROXY_TIMEOUT_SECONDS = 10.0
_FORWARDED_REQUEST_HEADERS = (
    "accept",
    "accept-language",
    "content-type",
    "if-modified-since",
    "if-none-match",
    "user-agent",
)
_FORWARDED_RESPONSE_HEADERS = (
    "cache-control",
    "content-language",
    "content-type",
    "etag",
    "expires",
    "last-modified",
    "location",
)


def firebase_auth_upstream() -> str:
    """``https://<project>.firebaseapp.com`` or "" when no project is set."""
    explicit = os.environ.get("FIREBASE_AUTH_PROXY_UPSTREAM", "").strip().rstrip("/")
    if explicit:
        return explicit
    project = os.environ.get("FIREBASE_PROJECT_ID", "").strip()
    return f"https://{project}.firebaseapp.com" if project else ""


async def _forward(request: Request, path: str) -> Response:
    upstream = firebase_auth_upstream()
    if not upstream:
        return Response(status_code=404)

    url = f"{upstream}{path}"
    headers = {
        name: value
        for name in _FORWARDED_REQUEST_HEADERS
        if (value := request.headers.get(name))
    }
    body = await request.body() if request.method == "POST" else None
    try:
        async with httpx.AsyncClient(timeout=PROXY_TIMEOUT_SECONDS, follow_redirects=False) as client:
            upstream_response = await client.request(
                request.method,
                url,
                params=request.query_params,
                headers=headers,
                content=body,
            )
    except Exception as exc:
        logging.warning("Firebase auth proxy failed path=%s error=%s", path, safe_exception(exc))
        return Response("Sign-in is temporarily unavailable.", status_code=502, media_type="text/plain")

    response = Response(content=upstream_response.content, status_code=upstream_response.status_code)
    for name in _FORWARDED_RESPONSE_HEADERS:
        value = upstream_response.headers.get(name)
        if value:
            response.headers[name] = value
    return response


@router.api_route("/__/auth/{helper:path}", methods=["GET", "HEAD", "POST"])
async def firebase_auth_helper(helper: str, request: Request) -> Response:
    return await _forward(request, f"/__/auth/{helper}")


@router.get("/__/firebase/init.json")
async def firebase_init_json(request: Request) -> Response:
    return await _forward(request, "/__/firebase/init.json")
