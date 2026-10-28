"""The legal pages name GitHub and the Agent workspace (audit 2026-10-28).

Until then the Privacy Notice did not mention the GitHub App (what is stored,
where repository contents go, pull requests, disconnecting), and the Terms
had no rules for the Agent's VM and browser.
"""

import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routers import pages as pages_router
from app.core import i18n
from app.core.i18n_middleware import I18nMiddleware


@pytest.fixture(scope="module")
def client():
    app = FastAPI()
    app.include_router(pages_router.router)
    app.add_middleware(I18nMiddleware)
    return TestClient(app, follow_redirects=False)


def text(response):
    assert response.status_code == 200
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", response.text))


@pytest.mark.parametrize("path,phrases", [
    ("/privacy", ["Optional GitHub connection (Agent VM):", "your GitHub login", "names of their repositories",
                  "Agent VM at Fly.io", "Only when you confirm it does Consens create a new branch and the pull request",
                  "uninstall it on GitHub", "GitHub, Inc. (USA)", "your GitHub connection, your Agent workspace"]),
    ("/de/privacy", ["Optionale GitHub-Verbindung (Agent-VM):", "deinen GitHub-Login", "Agent-VM bei Fly.io",
                     "deinstalliere sie auf GitHub", "deine GitHub-Verbindung, dein Agent-Arbeitsplatz"]),
    ("/terms", ["Agent VM and workspace.", "scan networks, ports or systems", "send spam",
                "mine cryptocurrency", "attack, overload or gain unauthorised access",
                "you are responsible for what it does there"]),
    ("/de/terms", ["Agent-VM und Arbeitsplatz.", "nach Schwachstellen zu scannen", "Spam",
                   "Kryptowährungen zu minen", "Du verantwortest, was er dort tut"]),
])
def test_the_legal_pages_cover_github_and_the_agent_workspace(client, path, phrases):
    page = text(client.get(path))
    for phrase in phrases:
        assert phrase in page, phrase


@pytest.mark.parametrize("path", ["templates/privacy.html", "templates/terms.html"])
def test_every_new_sentence_has_its_german_version(path):
    misses = []
    with open(path, encoding="utf-8") as source:
        i18n.translate_html(source.read(), "de", misses=misses)
    assert not [miss for miss in misses if "GitHub" in miss or "Agent VM" in miss or "workspace" in miss]
