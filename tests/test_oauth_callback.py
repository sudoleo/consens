"""The pages Google's and GitHub's OAuth redirects land on (app/core/oauth_callback.py)."""

import logging
import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routers import agent_github, agent_google
from app.core.i18n_middleware import I18nMiddleware
from app.core.observability import CorrelationMiddleware, OAuthAccessFilter
from app.core.security import CustomSecurityMiddleware

CALLBACKS = [("/agent/google/callback", "Google", "consens-google-oauth"),
             ("/agent/github/callback", "GitHub", "consens-github-oauth")]


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(agent_google.router)
    app.include_router(agent_github.router)
    # As in main.py: the security headers innermost, the i18n middleware outside.
    app.add_middleware(CustomSecurityMiddleware)
    app.add_middleware(CorrelationMiddleware)
    app.add_middleware(I18nMiddleware)
    return TestClient(app)


@pytest.mark.parametrize(("path", "service", "message"), CALLBACKS)
def test_the_callback_keeps_its_strict_policy_and_sends_no_referrer(client, path, service, message):
    page = client.get(f"{path}?code=private-code&state=private-state")
    assert page.status_code == 200
    csp = page.headers["content-security-policy"]
    nonce = re.search(r"script-src 'nonce-([^']+)'", csp).group(1)
    assert csp.startswith("default-src 'none'") and "unsafe-inline" not in csp
    assert page.headers["referrer-policy"] == "no-referrer"
    # One script, its own: no dictionary bundle the policy would refuse.
    assert re.findall(r"<script[^>]*>", page.text) == [f'<script nonce="{nonce}">']
    assert f'"type": "{message}"' in page.text and f"Completing {service} connection…" in page.text
    assert "private-code" not in page.text and "private-state" not in page.text


@pytest.mark.parametrize(("path", "service", "message"), CALLBACKS)
def test_the_callback_speaks_the_readers_language(client, path, service, message):
    page = client.get(path, headers={"Accept-Language": "de-DE,de;q=0.9"})
    assert '<html lang="de">' in page.text
    assert f"<title>{service}-Verbindung</title>" in page.text
    assert f"{service}-Verbindung wird abgeschlossen…" in page.text
    assert "Kehr zu Consens zurück, um die Verbindung abzuschließen." in page.text
    assert f"verbinde {service} erneut." in page.text
    # The cookie of the language switch wins over the browser.
    client.cookies.set("consens_lang", "en")
    english = client.get(path, headers={"Accept-Language": "de"})
    assert '<html lang="en">' in english.text and f"connect {service} again." in english.text


@pytest.mark.parametrize(("path", "service", "message"), CALLBACKS)
def test_the_access_log_keeps_no_authorization_code(path, service, message):
    record = logging.LogRecord("uvicorn.access", 20, "", 0, "%s %s %s",
                               ("GET", f"{path}?code=private-code&state=private-state&installation_id=7", "200"), None)
    OAuthAccessFilter().filter(record)
    assert record.getMessage() == f"GET {path}?[redacted] 200"
