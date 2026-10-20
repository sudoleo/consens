"""What /app's HTML carries for its first frame (Apple-Audit B1, B5, B9, B12).

The browser behaviour is measured in tests/e2e/test_first_frame.py and
tests/js/first-frame.test.mjs; this checks the markup contract they rely on.
"""
import os
import re
from pathlib import Path

os.environ.setdefault("UNIT_TEST_MODE", "1")

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_the_composer_decides_demo_and_send_in_the_template():
    html = read("templates/index.html")
    actions = html[html.index('<div class="input-actions-container">'):html.index('id="composerModeBar"')]
    # The demo offer is part of the page (hidden until app-bootstrap.js shows
    # it), before Send; an empty field's Send starts disabled.
    assert actions.index('class="demo-chip demo-action send-glow"') < actions.index('id="sendButton"')
    send = re.search(r'<button id="sendButton"[^>]*>', actions).group(0)
    assert " disabled" in send and 'aria-disabled="true"' in send
    # The words the app keeps: one name for the thing (H3).
    assert "<span>New chat</span>" in html and "New comparison" not in html.split("<body", 1)[1].split("</nav>", 1)[0]
    assert 'data-agent-default-label="{{ agent_default_label | e }}"' in html


def test_the_app_names_the_default_chat_model_without_the_catalog(monkeypatch):
    from app.api.routers import pages
    from app.services.llm import agent_client
    monkeypatch.setattr(agent_client, "agent_model_label", lambda: "Claude Sonnet 5.5")
    source = read("app/api/routers/pages.py")
    route = source[source.index('@router.get("/app"'):source.index("response.headers", source.index('@router.get("/app"'))]
    assert '"agent_default_label": agent_default_label' in route
    assert "agent_model_label()" in route
    assert pages is not None


def test_the_mail_strip_follows_the_composer():
    html = read("templates/index.html")
    # After the composer in the DOM: on the start screen it stands under the
    # field and never pushes it; in the thread order: 0 brings it up.
    assert html.index('class="input-section"') < html.index('id="verifyBanner"') < html.index('class="consensus-section"')
    css = read("static/css/shell.css")
    assert "body:not(.is-hero) #verifyBanner {\n  order: 0;" in css
    assert "body.is-hero #verifyBanner {\n  transform: translateY(var(--hero-shift, 0px));" in css


def test_firebase_is_warmed_and_katex_waits_for_a_formula():
    html = read("templates/index.html")
    head = html[:html.index("</head>")]
    firebase = read("static/firebase.js")
    imported = set(re.findall(r'from "(https://www\.gstatic\.com/firebasejs/[^"]+)"', firebase))
    assert imported
    assert '<link rel="preconnect" href="https://www.gstatic.com" crossorigin>' in head
    for url in imported:
        assert f'<link rel="modulepreload" href="{url}">' in head
    # No KaTeX on every start: math-render.js loads it for the first formula.
    assert "katex.min.js') }}\"></script>" not in head
    assert 'rel="stylesheet" href="{{ asset_url(\'/static/vendor/katex' not in head
    assert '<meta name="katex-assets"' in head
    for name in ("katex.min.css", "katex.min.js", "contrib/auto-render.min.js"):
        assert f"/static/vendor/katex/0.19.0/dist/{name}') }}}}\"" in head
