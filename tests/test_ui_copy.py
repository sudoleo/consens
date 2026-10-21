"""What /app says: one name for the thing, one style, no internal names.

Apple-Audit H3, H4, H5, H10 (2026-10-20). The copy rules, in short:

- The thing is a **chat** (New chat · Chats · Chat | Watches), for guests too.
  "Bookmark" stays an internal name (ids, classes, API fields), never a word on
  the page; "comparison" is no name for it, "Consensus" names a mode, never
  the product ("Consensus Watch", "Auto Consensus").
- **Sentence case** for titles, buttons and labels ("Send feedback", not
  "Send Feedback"); proper names and the named features keep their capitals.
- **"Log in"** is the verb ("Log in to share this answer"); "login",
  "logout" and "sign in" are not used. **"email"**, never "e-mail".
- Typographic **’** in contractions and possessives, **…** for an ellipsis.
- No internal names: the model behind Memory ("Luna"), "judges", "drawers",
  no build hash in Settings.
- Tokens and dollar costs are the operator's figures: only inside elements
  marked ``admin-only`` (style.css shows them only to admins).

``tests/ui_text.py`` finds the strings: the template's text and readable
attributes, and the prose string literals of every /app script.
"""

from __future__ import annotations

import re

import pytest

from tests import ui_text
from tests.ui_text import ROOT


TEXTS = ui_text.all_texts()


def offenders(pattern: re.Pattern, *, allow=()) -> list[str]:
    return [str(text) for text in TEXTS if pattern.search(text.text) and text.text not in allow]


def test_the_scanner_sees_the_words_of_the_app():
    # Guards the rules below against a scanner that silently finds nothing.
    assert len(TEXTS) > 1000
    words = {text.text for text in TEXTS}
    assert "Search chats" in words  # an attribute of the template
    assert "Show or hide your chats" in words  # a literal in firebase.js
    assert "Your question stays here and runs as soon as you’re logged in." in words
    sources = {text.source for text in TEXTS}
    assert {"templates/index.html", "static/firebase.js", "static/js/agent-chat.js", "static/js/app-text.js"} <= sources


@pytest.mark.parametrize("name, pattern", [
    ("bookmark", re.compile(r"\bbookmarks?\b", re.I)),
    ("comparison as the thing", re.compile(r"\b(new|start a new|this|your|the saved) comparisons?\b(?! model)", re.I)),
    ("Consensus as the product", re.compile(r"\bConsensus (Watch|Button|Model)\b|\bAuto Consensus\b")),
])
def test_the_thing_is_a_chat(name, pattern):
    assert offenders(pattern) == [], name


def test_one_style_for_logging_in_and_email():
    assert offenders(re.compile(r"\b(log(in|out))\b", re.I)) == []
    assert offenders(re.compile(r"\bsign(ed|ing)?[ -]?in\b", re.I)) == []
    assert offenders(re.compile(r"\be-mail", re.I)) == []


def test_typographic_apostrophes_and_ellipses():
    # "don't" -> "don’t", "..." -> "…" (a straight quote inside markup or
    # code is not prose and never reaches this list).
    assert offenders(re.compile(r"[A-Za-z]\\?'[A-Za-z]")) == []
    assert offenders(re.compile(r"\.\.\.")) == []


def test_no_internal_names_in_what_a_reader_sees():
    # The judges' run titles are keys the activity panel folds into one
    # "Answer check" row (agent-delegation.js checkNames), never shown.
    keys = {"Differences judge", "Coverage judge"}
    assert offenders(re.compile(r"(?<!GPT-\d )(?<!GPT-\d\.\d )\bLuna\b|\bjudges?\b|\bdrawers?\b", re.I), allow=keys) == []
    template = (ROOT / "templates/index.html").read_text(encoding="utf-8")
    settings = template[template.index('<dialog id="systemPromptModal"'):template.index('<dialog id="helpModal"')]
    assert "app_commit" not in settings  # the build stays in the source link's tooltip


# Words that keep their capitals inside a sentence-case title.
PROPER = {
    "Google", "Gmail", "Calendar", "Drive", "Telegram", "OpenRouter", "API", "Agent", "Watch", "Watches",
    "Pro", "Plus", "Free", "Compare", "Consensus", "Reasoning", "Memory", "PDF", "PDFs", "Word", "Docs",
    "Sheets", "Slides", "GitHub", "Morning", "Brief", "Beta", "UTC", "AI", "I", "Settings", "Display",
}
# Names of documents, kept as their pages title them.
TITLED = {"Privacy Policy", "Terms of Use", "Privacy Notice"}
TITLE_TAGS = {"h1", "h2", "h3", "h4", "button", "label", "legend", "summary", "option", "th", "@title", "@aria-label"}


def test_titles_buttons_and_labels_are_in_sentence_case():
    found = []
    for text in ui_text.template_texts():
        if text.context not in TITLE_TAGS or text.text in TITLED or len(text.text) > 60:
            continue
        # Each sentence starts with a capital ("Password set? Log in").
        for sentence in re.split(r"(?<=[.?!])\s+|\s+·\s+", text.text):
            words = re.findall(r"[A-Za-z][A-Za-z’'-]*", sentence)
            capitals = [word for word in words[1:] if word[0].isupper() and word not in PROPER and not word.isupper()]
            if capitals:
                found.append(f"{text}: {capitals}")
    assert found == []


def test_tokens_and_costs_are_for_admins_only():
    style = (ROOT / "static/style.css").read_text(encoding="utf-8")
    assert "body:not(.viewer-is-admin) .admin-only { display: none !important; }" in style
    firebase = (ROOT / "static/firebase.js").read_text(encoding="utf-8")
    assert 'document.body.classList.toggle("viewer-is-admin", data.is_admin === true);' in firebase
    activity = (ROOT / "static/js/agent-activity.js").read_text(encoding="utf-8")
    assert 'usageEl.className = "agent-usage admin-only";' in activity
    delegation = (ROOT / "static/js/agent-delegation.js").read_text(encoding="utf-8")
    for part in ('"agent-sidebar-usage admin-only"', "'agent-session-tokens admin-only'", "'agent-token-breakdown admin-only'"):
        assert part in delegation
    # Everywhere else the words a reader sees speak of the allowance.
    admin_parts = {"static/js/agent-activity.js", "static/js/agent-delegation.js", "static/js/sidebar-quota.js"}
    assert [str(text) for text in TEXTS
            if re.search(r"\btokens?\b|\$\d", text.text, re.I) and text.source not in admin_parts] == []


def test_dates_and_numbers_have_one_locale():
    # Apple-Audit H8: a German browser read "19. Okt. 2026" and "48.213 tokens"
    # next to "Oct 19". Every date, time, number and span goes through
    # App.format (app-text.js), which has the one locale of the interface.
    browser_locale = re.compile(r"\.toLocale(?:Date|Time)?String\(\s*(?:\)|\[\]|undefined\b)")
    own_formatter = re.compile(r"\bIntl\.(?:DateTimeFormat|NumberFormat|RelativeTimeFormat)\(\s*(?!\)\.resolvedOptions)")
    found = []
    for relative in ui_text.app_scripts():
        source = (ROOT / relative).read_text(encoding="utf-8")
        for number, line in enumerate(source.splitlines(), 1):
            code = line.split("//")[0]
            if browser_locale.search(code):
                found.append(f"{relative}:{number}: {line.strip()}")
            if relative != "static/js/app-text.js" and own_formatter.search(code):
                found.append(f"{relative}:{number}: {line.strip()}")
    assert found == []


def test_the_account_menu_says_log_out():
    # One-word labels in markup built by a script are no prose for the
    # scanner above; the account menu's entry is checked directly (review F).
    firebase = (ROOT / "static/firebase.js").read_text(encoding="utf-8")
    assert ">Log out</button>" in firebase
    assert not re.search(r">\s*Log(in|out)\s*<", firebase)
