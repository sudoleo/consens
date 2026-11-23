"""The service's second host, where the apps of users' workspaces are served
(app/services/agent_apps.py).

A request for that host never reaches consens.io's own routes, pages or
middlewares: what answers there is code an agent wrote, and it must find
nothing of consens.io under its own address, as consens.io's rules for its
pages (the security headers, the German pages, the delivery layer) are not
the app's. The service's health checks answer on every host.
"""
from __future__ import annotations

from app.services import agent_apps

# What the hosting platform and the monitors ask, whatever host they name.
OPEN_PREFIX = "/health/"


def _host(scope) -> str:
    for name, value in scope.get("headers") or ():
        if name.lower() == b"host":
            return value.decode("latin-1").strip().lower()
    return ""


class AppHostMiddleware:
    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") in {"http", "websocket"}:
            host = agent_apps.host()
            if host and _host(scope) == host and not str(scope.get("path") or "").startswith(OPEN_PREFIX):
                from app.services import agent_app_proxy
                await agent_app_proxy.app(scope, receive, send)
                return
        await self.app(scope, receive, send)
