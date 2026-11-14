"""The page a provider's OAuth redirect lands on (Google, GitHub).

It hands code and state to the window that started the connection. Its
policy allows no script but its own, so the i18n middleware passes it by
(``OAUTH_CALLBACK_PATHS``) and the page writes the reader's language itself.
"""

from __future__ import annotations

import html
import json
import secrets

from fastapi import Request
from fastapi.responses import HTMLResponse

from app.core import i18n
from app.core.i18n_middleware import request_language


def _t(text: str, language: str, service: str, *, context: str = "") -> str:
    return i18n.t(text, language, {"service": service}, context=context)


def page(request: Request, *, service: str, message: str) -> HTMLResponse:
    """``message`` is the ``type`` the opener listens for."""
    language = request_language(request)
    nonce = secrets.token_urlsafe(24)
    title = _t("{service} connection", language, service, context="oauth callback")
    waiting = _t("Completing {service} connection…", language, service, context="oauth callback")
    words = {
        "done": _t("Return to Consens to finish connecting. You may close this window.", language, service),
        "orphan": _t("This window has no active Consens session. Return to Consens and connect {service} again.",
                     language, service, context="oauth callback"),
        "type": message,
    }
    # Inside <script>, "</" would end it early.
    data = json.dumps(words, ensure_ascii=False).replace("</", "<\\/")
    body = f"""<!doctype html><html lang="{language}"><meta charset="utf-8"><title>{html.escape(title)}</title>
<p id="status">{html.escape(waiting)}</p><script nonce="{nonce}">
const words = {data};
const params = new URLSearchParams(location.search);
history.replaceState(null, '', location.pathname);
if (window.opener) {{
  window.opener.postMessage({{type:words.type,code:params.get('code'),state:params.get('state'),error:params.get('error')}}, location.origin);
  document.getElementById('status').textContent=words.done;
}} else {{ document.getElementById('status').textContent=words.orphan; }}
</script></html>"""
    return HTMLResponse(body, headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer",
        "Content-Security-Policy": f"default-src 'none'; script-src 'nonce-{nonce}'; base-uri 'none'; frame-ancestors 'none'"})
