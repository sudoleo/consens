"""German for German readers (docs/i18n.md): engine, addresses, dictionary."""
import asyncio
import gzip
import json
import re
import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.testclient import TestClient

from app.core import i18n
from app.core.i18n_middleware import I18nMiddleware
from scripts import i18n as i18n_tool

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def small_catalog(monkeypatch):
    """A fixed dictionary instead of app/i18n/de, for the engine's own rules."""
    entries = {
        "New chat": "Neuer Chat",
        "Settings": "Einstellungen",
        "Read the <0>privacy policy</0> first.": "Lies zuerst die <0>Datenschutzerklärung</0>.",
        "{n} chats": "{n} Chats",
        "Switch to {mode}": "Zu {mode} wechseln",
        "Compare": "Vergleich",
        "A page": "Eine Seite",
        "Ask once.": "Einmal fragen.",
        "Did not respond:": "Keine Antwort:",
        "Broken <0>marker</0>": "Kaputt",
    }
    current = i18n.Catalog(entries)
    monkeypatch.setitem(i18n._catalogs, "de", ((), current))
    monkeypatch.setitem(i18n._checked, "de", float("inf"))
    i18n._translated_cache.clear()
    yield current
    i18n._translated_cache.clear()


PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><title>A page</title>
<meta name="description" content="Ask once."><meta property="og:locale" content="en_US">
<link rel="canonical" href="https://www.consens.io/about">
<script type="application/ld+json">{"@type": "WebPage", "name": "A page", "url": "https://x"}</script>
<script>if (a < b && c > "New chat") {}</script></head>
<body><p class="x">Read the <a href="/privacy" class="l">privacy   policy</a> first.</p>
<button title="Settings"><svg viewBox="0 0 1 1"><path d="M0"/></svg> New chat</button>
<ul><li>3 chats<li>Switch to Compare</ul>
<div translate="no">New chat</div><div data-i18n-skip>New chat</div>
<span>Did not respond: <b>Luna</b></span>
<textarea>New chat</textarea><code>New chat</code>
<a href="/about#team">Team</a> <a href="/app">App</a>
</body></html>"""


def test_a_page_is_translated_segment_by_segment(small_catalog):
    out = i18n.translate_html(PAGE, "de", link_prefix="/de", canonical="https://www.consens.io/de/about")
    assert '<html lang="de">' in out
    assert "<title>Eine Seite</title>" in out
    assert 'content="Einmal fragen."' in out and 'content="de_DE"' in out
    assert 'href="https://www.consens.io/de/about"' in out
    assert '"name": "Eine Seite"' in out and '"url": "https://x"' in out
    assert 'c > "New chat"' in out, "scripts are never touched"
    assert '<p class="x">Lies zuerst die <a href="/de/privacy" class="l">Datenschutzerklärung</a>.</p>' in out
    assert 'title="Einstellungen"' in out and "</svg> Neuer Chat</button>" in out
    assert "<li>3 Chats<li>Zu Vergleich wechseln</ul>" in out
    assert '<div translate="no">New chat</div><div data-i18n-skip>New chat</div>' in out
    assert "<span>Keine Antwort: <b>Luna</b></span>" in out
    assert "<textarea>New chat</textarea><code>New chat</code>" in out
    assert '<a href="/de/about#team">' in out and '<a href="/app">' in out


def test_fields_options_and_context(small_catalog):
    small_catalog.exact["agent freedom|Settings"] = "Frei"
    out = i18n.translate_html(
        '<textarea placeholder="Settings">New chat</textarea>'
        '<select><option>New chat</option></select>'
        '<select data-i18n-context="agent freedom"><option>Settings</option></select>', "de")
    assert '<textarea placeholder="Einstellungen">New chat</textarea>' in out, "the reader's text stays, the placeholder is ours"
    assert "<option>Neuer Chat</option>" in out
    assert "<option>Frei</option>" in out


def test_misses_name_the_whole_run(small_catalog):
    misses = []
    i18n.translate_html("<p>Unknown sentence <b>here</b> now.</p><p>New chat</p>", "de", misses=misses)
    assert misses == ["Unknown sentence <0>here</0> now."]


def test_entries_that_change_markers_or_placeholders_are_refused(small_catalog):
    assert small_catalog.rejected == [("Broken <0>marker</0>", "Kaputt")]
    assert i18n.Catalog({"{n} left": "{count} übrig"}).rejected


def test_a_placeholder_takes_whole_elements_only(monkeypatch):
    current = i18n.Catalog({
        "{answered} of {length}": "{answered} von {length}",
        "{activeCount} of {activeLimit} active": "{activeCount} von {activeLimit} aktiv",
        "{remaining} slots free": "{remaining} Plätze frei",
        "Standard access": "Standard-Zugang",
        "Switch to {mode}": "Zu {mode} wechseln",
    })
    monkeypatch.setitem(i18n._catalogs, "de", ((), current))
    monkeypatch.setitem(i18n._checked, "de", float("inf"))
    i18n._translated_cache.clear()
    # The plan line of /app/watches (watch.js renderWatchLimit): the whole
    # line once matched "{answered} of {length}" and stayed English.
    line = ('<div><span>Standard access</span> <strong>2 of 20 active</strong> '
            '<span aria-hidden="true">·</span> <span>18 slots free</span></div>')
    try:
        # A whole element is still a value.
        out = i18n.translate_html(line + "<p>Switch to <b>Luna</b></p>", "de")
    finally:
        i18n._translated_cache.clear()
    assert current.lookup("<0>Standard access</0> <1>2 of 20 active</1> <2>·</2> <3>18 slots free</3>") is None
    assert out == ('<div><span>Standard-Zugang</span> <strong>2 von 20 aktiv</strong> '
                   '<span aria-hidden="true">·</span> <span>18 Plätze frei</span></div>'
                   "<p>Zu <b>Luna</b> wechseln</p>")
    assert i18n.whole_elements("<0>a</0> <1/>") and not i18n.whole_elements("<0>a") and not i18n.whole_elements("a</0>")


@pytest.mark.parametrize("html_text", [
    # A shared question or answer that types our own markers: the page used
    # to answer 500 (IndexError, the marker names an element that is not there).
    "<p>&lt;0/&gt; chats</p>",
    "<p>Read the &lt;0&gt;privacy policy&lt;/0&gt; first.</p>",
])
def test_markers_typed_in_the_text_are_left_alone(small_catalog, html_text):
    assert i18n.translate_html(html_text, "de") == html_text


def test_a_typed_marker_leaves_the_rest_of_its_run_translated(small_catalog):
    out = i18n.translate_html("<p>&lt;0/&gt; chats <b>New chat</b></p>", "de")
    assert out == "<p>&lt;0/&gt; chats <b>Neuer Chat</b></p>"


def test_long_content_does_not_stall_the_patterns():
    # A shared answer whose paragraph repeats the literals of a pattern with
    # four placeholders, without its ending: the lazy groups backtracked with
    # the fourth power of the length (4.5 KB took seconds, the event loop
    # stood still for every user). Text that long is content, not interface.
    current = i18n.catalog("de")
    unit = "a paused for this question because a API cannot read attachments. Remove the files to use "
    paragraph = i18n.normalize(unit * 50)
    assert len(paragraph) > 4000
    started = time.perf_counter()
    assert current.lookup(paragraph) is None
    assert time.perf_counter() - started < 1
    # Interface text with placeholders is far shorter and still translates.
    assert current.lookup("Sources: 12") == current.translate("Sources: {0}", {"0": 12})
    assert current.lookup("Sources: 12") != "Sources: 12"


def test_english_is_left_alone():
    assert i18n.translate_html(PAGE, "en") == PAGE
    assert i18n.t("New chat", "en") == "New chat"
    assert i18n.t("{n} chats", "en", {"n": 2}) == "2 chats"


@pytest.mark.parametrize("header, expected", [
    (None, "en"), ("", "en"), ("de-DE,de;q=0.9,en;q=0.8", "de"), ("de-AT", "de"),
    ("en-US,en;q=0.9,de;q=0.8", "en"), ("fr-FR,de;q=0.7,en;q=0.5", "de"), ("fr, it", "en"),
    ("en;q=0.5, de;q=0.9", "de"), ("de;q=0", "en"),
])
def test_the_browser_decides_only_between_our_languages(header, expected):
    assert i18n.preferred_language(header) == expected


# ---------------------------------------------------------------------------
# Addresses
# ---------------------------------------------------------------------------

@pytest.fixture
def client(small_catalog):
    app = FastAPI()

    @app.get("/about", response_class=HTMLResponse)
    def about():
        return PAGE

    @app.get("/app", response_class=HTMLResponse)
    def app_page():
        return "<html lang=\"en\"><head><meta charset=\"UTF-8\"></head><body><p>New chat</p><a href=\"/privacy\">x</a></body></html>"

    @app.get("/api/thing")
    def api():
        return JSONResponse({"error": "New chat"})

    app.add_middleware(I18nMiddleware)
    return TestClient(app, follow_redirects=False)


def test_a_german_browser_is_sent_to_the_german_address(client):
    response = client.get("/about", headers={"Accept-Language": "de-DE,de;q=0.9"})
    assert response.status_code == 302
    assert response.headers["location"] == "/de/about"
    assert "Accept-Language" in response.headers["vary"]
    # Crawlers send no language and stay on the English page, which names both.
    english = client.get("/about")
    assert english.status_code == 200 and "content-language" not in english.headers
    assert '<link rel="alternate" hreflang="de" href="https://www.consens.io/de/about">' in english.text
    assert '<link rel="alternate" hreflang="x-default" href="https://www.consens.io/about">' in english.text


def test_the_german_address_serves_german_with_the_dictionary_script(client):
    response = client.get("/de/about")
    assert response.status_code == 200
    assert response.headers["content-language"] == "de"
    assert "Neuer Chat" in response.text
    bundle = re.search(r'<script src="(/i18n/de\.[0-9a-f]{12}\.js)"></script>', response.text)
    assert bundle, "the dictionary is the first script of <head>"
    assert response.text.index(bundle.group(0)) < response.text.index("<title>")
    script = client.get(bundle.group(1), headers={"Accept-Encoding": "gzip"})
    assert script.status_code == 200
    assert script.headers["cache-control"] == "public, max-age=31536000, immutable"
    body = script.content if script.headers.get("content-encoding") != "gzip" else script.content
    assert b"window.__consensI18n=" in body and b"Neuer Chat" in body
    assert client.get("/i18n/de.000000000000.js").headers["cache-control"] == "no-cache"
    assert client.get("/i18n/fr.000000000000.js").status_code == 404


def test_other_pages_follow_the_choice_on_one_address(client):
    german = client.get("/app", headers={"Accept-Language": "de"})
    assert german.headers["content-language"] == "de" and "<p>Neuer Chat</p>" in german.text
    assert 'href="/de/privacy"' in german.text
    assert "Accept-Language" in german.headers["vary"] and "Cookie" in german.headers["vary"]
    assert client.get("/de/app").headers["location"] == "/app"
    # API answers stay English: the browser translates what it shows.
    assert client.get("/api/thing", headers={"Accept-Language": "de"}).json() == {"error": "New chat"}


def test_lang_parameter_stores_the_choice(client):
    response = client.get("/about?lang=de&x=1")
    assert response.status_code == 302 and response.headers["location"] == "/de/about?x=1"
    assert "consens_lang=de" in response.headers["set-cookie"] and "Max-Age=31536000" in response.headers["set-cookie"]
    back = client.get("/de/about?lang=en")
    assert back.headers["location"] == "/about" and "consens_lang=en" in back.headers["set-cookie"]
    # The cookie beats the browser: English stays English.
    client.cookies.set("consens_lang", "en")
    assert client.get("/about", headers={"Accept-Language": "de"}).status_code == 200
    forget = client.get("/app?lang=auto")
    assert forget.headers["location"] == "/app" and "Max-Age=0" in forget.headers["set-cookie"]


def _redirect_location(path: str, query: bytes = b"") -> str:
    """Location of a redirect for a raw ASGI path, as uvicorn decodes it."""
    async def inner(scope, receive, send):
        raise AssertionError("expected a redirect")

    sent = []

    async def send(message):
        sent.append(message)

    scope = {"type": "http", "method": "GET", "path": path, "query_string": query, "headers": []}
    asyncio.run(I18nMiddleware(inner)(scope, None, send))
    assert sent[0]["status"] == 302
    return dict(sent[0]["headers"])[b"location"].decode("latin-1")


@pytest.mark.parametrize("path, query", [
    ("/de//evil.example", b""),
    ("/de//evil.example/about", b"x=1"),
    ("//evil.example", b"lang=de"),
    ("/\\evil.example", b"lang=de"),
    ("/de/\\evil.example", b""),
    ("/\t/evil.example", b"lang=en"),
])
def test_language_redirects_stay_on_this_site(small_catalog, path, query):
    location = _redirect_location(path, query)
    assert location.startswith("/") and not location.startswith("//"), location
    assert "\\" not in location and "\t" not in location, location


def test_footer_offers_the_other_language():
    footer = (ROOT / "templates/partials/public_footer.html").read_text(encoding="utf-8")
    assert '<a href="?lang=de" hreflang="de" lang="de" translate="no">Deutsch</a>' in footer
    assert '<a href="?lang=en" hreflang="en" lang="en" translate="no">English</a>' in footer


# ---------------------------------------------------------------------------
# The dictionary
# ---------------------------------------------------------------------------

def _dictionary_files():
    return sorted((ROOT / "app/i18n/de").glob("*.json"))


def test_dictionary_files_are_valid_and_agree_with_each_other():
    seen: dict[str, tuple[str, str]] = {}
    conflicts = []
    for path in _dictionary_files():
        data = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict), path
        for key, value in data.items():
            if key.startswith("_"):
                continue
            assert isinstance(value, str) and value.strip(), f"{path.name}: empty value for {key!r}"
            normalized = i18n.normalize(key)
            if normalized in seen and i18n.normalize(seen[normalized][1]) != i18n.normalize(value):
                conflicts.append(f"{normalized!r}: {seen[normalized][0]}={seen[normalized][1]!r} vs {path.name}={value!r}")
            seen[normalized] = (path.name, value)
    assert not conflicts, "one English text, two German ones:\n" + "\n".join(conflicts)
    current = i18n.Catalog(i18n._read_entries(_dictionary_files()))
    assert not current.rejected, current.rejected


def test_every_visible_english_text_has_german():
    grouped = i18n_tool.missing("de")
    lines = [f"{item.source}:{item.line}: {item.key}" for items in grouped.values() for item in items]
    assert not lines, (
        f"{len(lines)} texts without German (python scripts/i18n.py missing; docs/i18n.md):\n" + "\n".join(lines[:60]))


def test_a_service_sentence_that_reaches_a_card_is_found():
    """The hold, secret and notes endpoints answer with the sentence of the
    exception agent_sessions.py raised ("This pause is already over.", B7 in
    docs/agent-audit-readiness-2026-10-29.md): it needs German like any other."""
    keys = {item.key for item in i18n_tool.server_keys("app/services/agent_sessions.py")}
    assert {"This pause is already over.", "This response is no longer running.",
            "This response already has the most messages it takes while it runs."} <= keys
    assert "app/services/agent_sessions.py" in i18n_tool.server_files()


def test_a_sentence_composed_from_chosen_words_is_found():
    """"Difference: ${text}" with the word picked inside ${…} has no entry of
    its own; whole sentences or App.t for each part do (docs/i18n.md)."""
    current = i18n.Catalog({"Difference": "Unterschied", "Disagreement": "Uneinigkeit",
                            "Allow {0} first.": "Erlaube zuerst: {0}.", "Waiting for: {goal}": "Wartet auf: {goal}"})
    composed = "li.textContent = `${hard ? 'Disagreement' : 'Difference'}: ${text}`;"
    swallowed = "sub.textContent = `Allow ${gmail ? 'reading emails' : 'reading calendars'} first.`;"
    whole = "view.goal.textContent = `Waiting for: ${goal}`; item.textContent = `${App.t(label)}: ${text}`;"
    assert [gap.key for gap in i18n_tool.composed_in("x.js", composed, current)] == ["Disagreement: Q17"]
    assert [gap.key for gap in i18n_tool.composed_in("x.js", swallowed, current)] == ["Allow reading emails first."]
    assert i18n_tool.composed_in("x.js", whole, current) == []


def test_a_tag_inside_a_label_marks_its_key():
    """{% if %} inside a label's value renders whole sentences that the key
    glued from both branches stands for neither of: the German page kept
    "Consensus verdict at a glance" (share.html, a11y audit L2)."""
    glued = '<div aria-label="{% if a %}Answer check{% else %}Consensus verdict{% endif %} at a glance"></div>'
    whole = ("<div aria-label=\"{{ 'Answer check at a glance' if a else 'Consensus verdict at a glance' }}\""
             ' class="box{% if a %} is-agent{% endif %}"></div>')

    def keys(source):
        return i18n.html_segments(i18n_tool.jinja_to_html(source))

    assert keys(glued) == ["{%}Answer check{%}Consensus verdict{%} at a glance"]
    assert not any(i18n_tool.TAG_IN_VALUE in key for key in keys(whole))


def test_no_script_composes_a_sentence_without_an_entry():
    """Scripts, and labels in templates with a tag inside their value."""
    gaps = [f"{gap.source}:{gap.line}: {gap.key}" for gap in i18n_tool.composed_gaps("de")]
    assert not gaps, "composed from parts, write whole sentences or App.t each part (docs/i18n.md):\n" + "\n".join(gaps)


def test_words_a_script_writes_reach_the_browser():
    """page-*.json and mail.json stay on the server; a script's words must be in another file."""
    client = {}
    for path in _dictionary_files():
        if not i18n.server_only(path):
            client.update({i18n.normalize(key): value for key, value in json.loads(path.read_text(encoding="utf-8")).items()})
    current = i18n.Catalog(client)
    missing = sorted({
        item.key for relative in i18n_tool.script_files() for item in i18n_tool.script_keys(relative)
        if not i18n_tool.covered(current, item.key)
    })
    assert not missing, "in server-only files, the browser never sees them:\n" + "\n".join(missing[:40])


def test_a_script_sentence_with_a_context_names_its_entry():
    """App.t("…", params, "watch schedule") is looked up under its context, so an
    open pattern can live there ("watch schedule|In {city} time", docs/i18n.md)."""
    source = 'note.textContent = window.App.t("In {city} time", { city }, "watch schedule") || App.t("Copy", null);'
    assert [item.key for item in i18n_tool.script_keys("x.js", source)] == ["watch schedule|In {city} time", "Copy"]


def test_the_engine_files_name_the_same_rules():
    """i18n.js mirrors app/core/i18n.py: same tags, attributes and markers."""
    script = (ROOT / "static/js/i18n.js").read_text(encoding="utf-8")

    def js_set(name):
        block = re.search(rf"const {name} = (?:new Set\()?\[([^\]]*)\]", script).group(1)
        return set(re.findall(r'"([^"]+)"', block))

    assert js_set("PHRASING") == set(i18n.PHRASING_TAGS)
    assert js_set("OPAQUE") == set(i18n.OPAQUE_INLINE_TAGS)
    assert js_set("SKIP") == set(i18n.SKIP_TAGS)
    assert js_set("TEXT_ATTRIBUTES") == set(i18n.TEXT_ATTRIBUTES)


def test_scripts_do_not_find_elements_by_their_visible_label():
    offenders = []
    for path in sorted((ROOT / "static/js").glob("*.js")) + sorted((ROOT / "static").glob("*.js")):
        source = path.read_text(encoding="utf-8")
        for match in re.finditer(r"\[(?:data-(?:short|label|tooltip|ghost|compact|description)|aria-label|title|placeholder|alt)=[\"'][A-Z]", source):
            offenders.append(f"{path.name}:{source.count(chr(10), 0, match.start()) + 1}")
    assert not offenders, "a translated attribute is no selector (docs/i18n.md): " + ", ".join(offenders)


# ---------------------------------------------------------------------------
# Language of content (a11y audit L1)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("Photosynthesis turns light into chemical energy. It happens in the chloroplasts of the leaf,"
     " and it is the reason that plants are green.", "en"),
    ("Die Photosynthese wandelt Licht in chemische Energie um. Sie findet in den Chloroplasten statt,"
     " und sie ist der Grund, dass die Pflanzen grün sind.", "de"),
    # Too short to tell, another language, or mixed: the page's lang holds.
    ("Is ibuprofen safe?", None),
    ("La photosynthèse transforme la lumière en énergie chimique dans les chloroplastes de la feuille.", None),
    ("¿Es seguro tomar ibuprofeno con medicamentos para la presión? Es una pregunta que muchos hacen y es"
     " importante saber la respuesta.", None),
    ("The answer is ja, und das ist nicht falsch, but it is not the whole story and it depends on the"
     " dose, sagt der Arzt, die man nimmt.", None),
])
def test_content_language_is_named_only_when_clear(text, expected):
    assert i18n.content_language(text) == expected


def test_content_in_a_skipped_region_keeps_its_words(small_catalog):
    # A model's heading "Settings" stays as it is on a German page; the frame
    # around the answer is translated (share.html, partials/check_page.html).
    page = ('<html lang="en"><body><h2>Settings</h2>'
            '<div class="share-md" data-i18n-skip lang="en"><h2>Settings</h2></div></body></html>')
    assert i18n.translate_html(page, "de") == (
        '<html lang="de"><body><h2>Einstellungen</h2>'
        '<div class="share-md" data-i18n-skip lang="en"><h2>Settings</h2></div></body></html>')
