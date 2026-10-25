"""Chat contracts that outlive the browser's Consensus chat session.

Since 2026-10-25 the browser neither creates nor continues a Consensus chat
(chat-session.js is gone; the pipeline runs on the server for Watches, the
API and topics). What stays: the Agent creates its own chats with the same
limit wording (App.chatPersistenceErrorMessage, app-text.js, covered in
tests/js/app-text.test.mjs), and saved Consensus chats render their turns
read-only (thread-history.js).
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_the_browser_session_for_consensus_chats_is_gone():
    assert not (ROOT / "static" / "js" / "chat-session.js").exists()
    bundles = (ROOT / "static" / "js" / "bundles.json").read_text(encoding="utf-8")
    assert "chat-session.js" not in bundles
    assert "consensus-run.js" not in bundles
    app_text = (ROOT / "static" / "js" / "app-text.js").read_text(encoding="utf-8")
    assert "App.chatPersistenceErrorMessage = chatPersistenceErrorMessage;" in app_text


def test_agent_chat_creation_reports_the_chat_limit_like_consensus():
    """Lokaler Test 2026-10-11: POST /chats endete im Agent mit 403
    chat_limit_reached, der Lauf zeigte nur "At most 200 chats per account"."""
    agent = (ROOT / "static" / "js" / "agent-chat.js").read_text(encoding="utf-8")
    creation = agent.split('fetch("/chats", {', 1)[1].split("chatId = data.chat.id;", 1)[0]

    # The limit's own words win over the server's ("Delete one…"), carried
    # as the refusal's sentence (App.httpError, Apple-Audit H1).
    assert "const limit = App.chatPersistenceErrorMessage?.(data);" in creation
    assert "if (limit) refusal.message = refusal.serverMessage = limit;" in creation


def test_archived_turns_render_the_same_difference_cards_as_a_saved_answer():
    history = (ROOT / "static" / "js" / "thread-history.js").read_text(
        encoding="utf-8"
    )
    insights = (ROOT / "static" / "js" / "consensus-insights.js").read_text(
        encoding="utf-8"
    )

    # Ein archivierter Turn traegt dieselben strukturierten Daten wie die
    # gespeicherte Antwort und muss sie auch benutzen, sonst liest sich
    # derselbe Befund im Verlauf als roher Judge-Freitext.
    assert "window.renderStoredDifferenceCards = renderStoredDifferenceCards" in insights
    assert "window.renderStoredDifferenceCards?.(" in history
    assert "hasStructuredDifferences || differencesText" in history

    stored = insights.split("function renderStoredDifferenceCards", 1)[1].split(
        "\n          }", 1
    )[0]
    assert "Array.isArray(differencesData.differences)" in stored
    assert "static: true" in stored

    # Der Freitext bleibt der Fallback fuer alte Turns ohne strukturierte
    # Daten, ohne die Buchhaltungszeile des Judges.
    assert "function stripBestModelLine(differencesText)" in history
    assert "BestModel:" in history.split("function stripBestModelLine", 1)[1][:300]
    assert "const differencesText = stripBestModelLine(turnData.differences)" in history


def test_archived_difference_cards_carry_no_live_run_controls():
    insights = (ROOT / "static" / "js" / "consensus-insights.js").read_text(
        encoding="utf-8"
    )

    cards = insights.split("function buildDifferenceCards", 1)[1].split(
        "function renderDifferenceCards", 1
    )[0]
    # Sprunglinks zeigten sonst auf die Antwortboxen des NEUESTEN Laufs.
    # Archivierte Karten bieten Sprunglinks nur mit expliziter, turngebundener
    # Navigation an, niemals still auf die aktuellen Antwortboxen.
    assert "if (isStatic && !opts.answerNavigation) return false;" in cards
    assert "if (opts.answerNavigation) opts.answerNavigation.open(model, pos.quote, entry);" in cards
    # Die Modellnamen kommen aus dem Turn, nicht aus den Live-Boxen; Icon und
    # Name stehen in einer Kopfzeile pro Position.
    assert "const name = labelFor(model);" in cards
    assert "nameEl.textContent = name;" in cards
    assert '"Open the full answer from " + name' in cards
    assert "function storedModelLabeller(modelAnswers)" in (
        (ROOT / "static" / "js" / "thread-history.js").read_text(encoding="utf-8")
    )

    # Eine Resolve-Runde startet der Browser nicht mehr (2026-10-25): eine
    # Karte zeigt nur ein gespeichertes Ergebnis, ohne Knopf.
    resolve = insights.split("function buildResolveSection(diff)", 1)[1].split(
        "\n          }", 1
    )[0]
    assert "if (!diff.resolution" in resolve
    assert "button" not in resolve
    assert "function runResolveRound" not in insights
