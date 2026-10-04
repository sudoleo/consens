"""The same-origin proxy for Firebase's sign-in helpers (/__/auth/*)."""

from unittest.mock import patch

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routers import firebase_auth_proxy
from app.core.security import CustomSecurityMiddleware


def _app():
    app = FastAPI()
    app.add_middleware(CustomSecurityMiddleware)
    app.include_router(firebase_auth_proxy.router)
    return app


class _RecordingClient:
    calls = []
    response = httpx.Response(
        200,
        content=b"<html>handler</html>",
        headers={
            "content-type": "text/html; charset=utf-8",
            "cache-control": "public, max-age=1800",
            "set-cookie": "upstream=1",
            "content-security-policy": "default-src 'none'",
        },
    )

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def request(self, method, url, **kwargs):
        type(self).calls.append({"method": method, "url": url, **kwargs, "client": self.kwargs})
        return type(self).response


def _client(monkeypatch, project="consensai"):
    monkeypatch.delenv("FIREBASE_AUTH_PROXY_UPSTREAM", raising=False)
    monkeypatch.setenv("FIREBASE_PROJECT_ID", project)
    _RecordingClient.calls = []
    return TestClient(_app())


def test_handler_is_forwarded_to_the_project_firebaseapp_domain(monkeypatch):
    client = _client(monkeypatch)
    with patch.object(firebase_auth_proxy.httpx, "AsyncClient", _RecordingClient):
        response = client.get(
            "/__/auth/handler?apiKey=k&authType=signInViaRedirect",
            headers={"Cookie": "session=secret-id-token", "Authorization": "Bearer secret", "Accept-Language": "de"},
        )

    assert response.status_code == 200
    assert response.text == "<html>handler</html>"
    call = _RecordingClient.calls[0]
    assert call["method"] == "GET"
    assert call["url"] == "https://consensai.firebaseapp.com/__/auth/handler"
    assert dict(call["params"]) == {"apiKey": "k", "authType": "signInViaRedirect"}
    # Nothing of the user's session travels to Firebase Hosting.
    forwarded = {name.lower() for name in call["headers"]}
    assert "cookie" not in forwarded
    assert "authorization" not in forwarded
    assert call["headers"]["accept-language"] == "de"
    assert call["client"]["follow_redirects"] is False
    # Upstream cookies are not planted on consens.io either.
    assert "set-cookie" not in response.headers
    assert response.headers["cache-control"] == "public, max-age=1800"


def test_helpers_are_framable_by_the_app_and_skip_the_app_csp(monkeypatch):
    client = _client(monkeypatch)
    with patch.object(firebase_auth_proxy.httpx, "AsyncClient", _RecordingClient):
        iframe = client.get("/__/auth/iframe?apiKey=k")
        init = client.get("/__/firebase/init.json")

    for response in (iframe, init):
        assert response.headers["x-frame-options"] == "SAMEORIGIN"
        assert "content-security-policy" not in response.headers
    assert _RecordingClient.calls[1]["url"] == "https://consensai.firebaseapp.com/__/firebase/init.json"


def test_handler_post_body_is_forwarded(monkeypatch):
    client = _client(monkeypatch)
    with patch.object(firebase_auth_proxy.httpx, "AsyncClient", _RecordingClient):
        client.post("/__/auth/handler", content=b"code=abc", headers={"Content-Type": "application/x-www-form-urlencoded"})

    call = _RecordingClient.calls[0]
    assert call["method"] == "POST"
    assert call["content"] == b"code=abc"
    assert call["headers"]["content-type"] == "application/x-www-form-urlencoded"


def test_other_paths_keep_the_strict_app_headers(monkeypatch):
    app = _app()

    @app.get("/probe")
    def probe():
        return {"ok": True}

    response = TestClient(app).get("/probe")
    assert response.headers["x-frame-options"] == "DENY"
    assert "content-security-policy" in response.headers


def test_without_a_project_the_proxy_is_absent(monkeypatch):
    client = _client(monkeypatch, project="")
    assert client.get("/__/auth/handler").status_code == 404


def test_upstream_failure_is_a_neutral_502(monkeypatch):
    class _Failing(_RecordingClient):
        async def request(self, *args, **kwargs):
            raise httpx.ConnectError("boom")

    client = _client(monkeypatch)
    with patch.object(firebase_auth_proxy.httpx, "AsyncClient", _Failing):
        response = client.get("/__/auth/handler")

    assert response.status_code == 502
    assert "boom" not in response.text
