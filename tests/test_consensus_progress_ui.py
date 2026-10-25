"""Thread and footer contracts of the app page.

Since 2026-10-25 the browser runs Agent and Compare only; the guided
Consensus run (#consensusRun, consensus-progress.js, consensus-lifecycle.js)
left with the pipeline, which runs on the server for Watches, the API and
topics. A saved Consensus answer still shows its footer drawers
(consensus-footer.js) and its earlier turns (thread-history.js).
"""

from pathlib import Path
from tests.frontend_order import loads_before


ROOT = Path(__file__).resolve().parents[1]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_saved_consensus_precedes_model_answers_without_a_run_block():
    template = read("templates/index.html")
    bundles = read("static/js/bundles.json")

    assert template.index('class="consensus-section"') < template.index(
        'class="response-section"'
    )
    for retired in ('id="consensusRun"', 'id="runStatus"', 'id="runSteps"',
                    'id="runProvenanceFacts"', 'id="runReplayButton"',
                    'id="composerRunNotice"'):
        assert retired not in template, retired
    for retired in ("consensus-progress.js", "consensus-lifecycle.js",
                    "consensus-run.js", "chat-session.js"):
        assert retired not in bundles, retired
        assert not (ROOT / "static" / "js" / retired).exists(), retired
    assert loads_before("agent-mode.js", "consensus-footer.js")
    assert loads_before("consensus-footer.js", "thread-history.js")


def test_a_saved_answer_hands_over_to_a_footer_of_drawers():
    template = read("templates/index.html")
    footer = read("static/js/consensus-footer.js")
    css = read("static/css/shell.css")

    assert 'id="runProvenance"' in template
    assert 'id="consensusFooterTabs"' in template
    assert ".run-provenance" in css
    assert "App.consensusFooter = Object.freeze({ render, clear })" in footer
    # The live run's styles went with it.
    assert ".run-step" not in css
    assert ".run-replay" not in css


def test_result_footer_has_one_boundary_before_the_composer():
    """Closed drawers and the legacy divider must not stack hairlines."""
    css = read("static/css/shell.css")

    assert ".consensus-differences-panel[open]" in css
    assert ".consensus-divider {\n  display: none;" in css
    assert "body:not(.is-hero) .input-section::before" in css


def test_the_composer_carries_no_followup_affordance_at_all():
    """Ein Gespraech laeuft im Agent ueber das Eingabefeld weiter, ohne
    Kontext-Chip, ohne Angebots-Leiste und ohne ein zweites "New comparison"
    am Composer. Der Ausstieg steht in der Sidebar."""
    template = read("templates/index.html")
    history = read("static/js/thread-history.js")

    assert 'id="followupChipBar"' not in template
    assert 'id="followupBar"' not in template
    assert "followupChipBar" not in history
    assert "followup-newrun" not in history
    assert 'id="newRunButton"' in template
    # Compare setzt keinen Chat fort: kein Angebot, kein scharfer Kontext.
    assert "isArmed" not in history
    assert "offer(" not in history


def test_saved_turns_render_as_a_static_history_above_the_active_one():
    template = read("templates/index.html")
    history = read("static/js/thread-history.js")
    app_init = read("static/js/app-init.js")
    view = read("static/js/run-view.js")
    css = read("static/css/shell.css")

    # Der statische Verlauf steht im DOM vor dem aktiven Turn. Der Live-
    # Renderbaum mit seinen einmaligen IDs bleibt dadurch unveraendert.
    assert template.index('id="threadHistory"') < template.index('id="threadAsk"')
    assert "renderStoredTurn(turnData)" in history
    assert "renderStoredTurns(turns, options = {})" in history
    assert 'questionText.className = "thread-history-question-text"' in history
    assert "buildStoredAgreement(differencesData)" in history
    assert "const insightRoot = window.App.consensusBodyEl?.() || document" in read(
        "static/js/consensus-insights.js"
    )
    # Ein Compare-Lauf fuehrt keinen Verlauf; ein Wechsel des Laufs leert ihn.
    assert "followup?.clearHistory?.()" in view
    # Auch der Direktvergleich zeigt seine Frage: ohne sie stand auf dem
    # Schirm nur die Antwort auf etwas Ungesagtes.
    assert "window.App.setThreadQuestion?.(context.question)" in view
    assert "clearHistory?.()" in app_init

    # User-Turns stehen rechts; Consensus-Turns bleiben als Lesetext links.
    assert "align-items: flex-end" in css
    assert ".thread-history-question" in css
    assert ".thread-history-answer-body" in css
    assert ".thread-history-verdict" in css
    assert "flex: 1 1 0" in css
    assert ".thread-history-verdict .verdict-judge" in css
    insights = read("static/js/consensus-insights.js")
    assert "TOPIC_MAX_SHOWN = 1" in insights
    assert "TOPIC_MAX_WORDS" not in insights


def test_the_sent_message_leaves_the_field_before_prepare_runs():
    """Zwischen Klick und dem Moment, in dem der Lauf den neuen Turn aufmacht,
    liegt /prepare. Das dauerte so lange, dass es aussah, als sei der Klick
    ins Leere gegangen: die Frage stand unveraendert im Feld (User-Befund
    2026-08-15). Sie geht deshalb SOFORT raus und steht als eigene Blase im
    Thread."""
    template = read("templates/index.html")
    query = read("static/js/query-send.js")
    core = read("static/js/app-core.js")
    css = read("static/css/shell.css")

    assert 'id="threadPendingAsk"' in template
    assert 'id="threadPendingAskText"' in template
    assert 'id="threadPendingAskAttachments"' in template
    assert template.index('id="threadAsk"') < template.index('id="threadPendingAsk"')

    # Der synchrone Hand-off leert das Feld und projiziert den Context, bevor
    # executeRun mit Token-/prepare-Awaits beginnt.
    handoff_at = query.index("handComposerToRun(context);")
    assert handoff_at < query.index("await executeRun(context);", handoff_at)
    handoff = query.split("function handComposerToRun(context)", 1)[1].split(
        "window.sendQuestion =", 1
    )[0]
    assert 'input.value = "";' in handoff
    assert "registry.renderVisible();" in handoff

    assert ".thread-ask-pending { order: 4; }" in css
    assert "body.thread-message-pending:not(.is-hero) .response-section { order: 3; }" in css
    assert css.index("body:not(.is-hero) .consensus-section { order: 3; }") < css.index(
        ".thread-ask-pending { order: 4; }"
    )

    # Jeder Kopf im Thread wird vom selben Renderer gefuellt (Clamp, Aufklapp-
    # Link, ResizeObserver), sonst verhielte sich die Blase anders als der
    # Kopf, zu dem sie wird.
    assert "function renderThreadQuestion(wrap, text, question)" in core
    assert "const threadAskResizeObservers = new WeakMap()" in core
    set_head = core.split("function setThreadQuestion(", 1)[1].split("}", 1)[0]
    assert "clearPendingThreadQuestion()" in set_head


def test_a_run_that_never_happens_gives_the_message_back():
    """Kontingent leer, fehlender Key, abgebrochen: dann ist nichts
    rausgegangen. Die Nachricht gehoert unveraendert und abschickbar zurueck
    ins Feld."""
    query = read("static/js/query-send.js")

    restore_block = query.split("function restoreComposerAfterUnsentRun(context)", 1)[1].split(
        "function finishFailed", 1
    )[0]
    assert "registry.isVisible(context.runId)" in restore_block
    assert "input.value = context.metadata.draftQuestion || context.question;" in restore_block
    assert "window.App.quote?.set?.(context.metadata.quotedContext)" in restore_block
    # Ein inzwischen vorbereiteter Entwurf (Text, Zitat oder Datei) wird nie
    # von einem spaeter abgebrochenen Hintergrund-Run ueberschrieben.
    assert "if (composerOccupied) return;" in restore_block
    assert "composerAttachments.length > 0" in restore_block

    assert "if (failedBeforeFanout) restoreComposerAfterUnsentRun(context);" in query
    assert 'if (registry.isVisible(context.runId) && context.phase === "prepare")' in query


def test_archived_questions_clamp_like_the_active_one():
    """Eine lange Frage bleibt auch im Verlauf eingeklappt (acht Zeilen)
    (User-Befund 2026-08-14)."""
    css = read("static/css/shell.css")
    history = read("static/js/thread-history.js")
    core = read("static/js/app-core.js")

    clamp_block = css.split(
        ".thread-history-question.is-long:not(.is-open) .thread-history-question-text {", 1
    )[1].split("}", 1)[0]
    assert "-webkit-line-clamp: 8" in clamp_block
    assert ".thread-history-question.is-long .thread-ask-more" in css

    turn = history.split("buildHistoryTurn(turnData, options = {})", 1)[1].split(
        "renderStoredTurn(turnData)", 1
    )[0]
    assert 'questionMore.className = "thread-ask-more"' in turn
    assert "window.App.observeQuestionFold?.(question, questionText);" in turn

    assert 'event.target.closest(".thread-ask-more")' in core
    assert 'more.closest(".thread-ask, .thread-history-question")' in core


def test_archived_turns_use_the_same_drawer_row_as_a_saved_answer():
    """Differences, Sources und Model answers liegen im Verlauf NEBEN-, nicht
    untereinander: dieselben .consensus-tab-Chips wie im Fuss der Antwort."""
    import re

    history = read("static/js/thread-history.js")
    css = read("static/css/shell.css")

    turn = history.split("buildHistoryTurn(turnData, options = {})", 1)[1].split(
        "renderStoredTurn(turnData)", 1
    )[0]
    assert "thread-history-details" not in turn
    assert '"consensus-footer-tabs thread-history-tabs"' in turn
    drawer_classes = re.search(r'tab\.className = "([^"]+)"', turn)
    assert drawer_classes is not None
    assert {"consensus-tab", "consensus-evidence-action"} <= set(drawer_classes[1].split())
    assert '"Review differences",\n          "Differences",' in turn
    assert 'addDrawer("Sources", "Sources", turnSources.length' in turn
    assert 'addDrawer("Compare answers", "Answers", usableAnswers.length' in turn
    # Der Verlauf teilt sich den DOM mit dem Live-Renderbaum: keine ID darf
    # dort ein zweites Mal auftauchen.
    assert "`threadHistoryPanel-${++panelSequence}`" in turn
    assert 'tab.setAttribute("aria-controls", panelId)' in turn

    assert ".thread-history-footer" in css
    assert ".thread-history-panel[hidden]" in css


def test_composer_row_is_reduced_to_attach_run_switch_and_send():
    """The mode explainer and the clear button left the composer; the one
    mode selector (Agent / Compare) is its only mode control."""
    template = read("templates/index.html")

    assert 'id="attachTrigger"' in template
    assert 'id="runModeSelect"' in template
    assert 'id="consensusModelDropdown"' in template
    assert 'id="sendButton"' in template

    assert 'id="toggleAllButton"' not in template
    assert 'id="modeExplainerTrigger"' not in template
    assert 'id="clearButton"' not in template

    # ...but the functions are still reachable.
    assert 'id="runModeSetting"' in template
    assert 'id="reasoningToggle"' in template
    assert 'id="newRunButton"' in template


def test_sidebar_header_groups_brand_and_toggle_before_new_comparison():
    template = read("templates/index.html")

    brand = template.index('class="sidebar-brand-row"')
    toggle = template.index('id="sidebarToggleInner"')
    new_run = template.index('id="newRunButton"')
    search = template.index('id="chatSearch"')

    assert brand < toggle < new_run < search
    assert 'class="sidebar-top"' not in template
    # Exactly one sidebar toggle in the markup besides the floating one.
    assert template.count('id="sidebarToggleInner"') == 1
    assert template.count('id="toggleSidebarButton"') == 1


def test_consensus_loader_matches_the_run_visual_language():
    """Die synthetisierende Box bleibt still, der Loader sind die Punkte.

    Frueher lief hier eine wandernde Linie (.is-synthesizing::after mit
    @keyframes consensusLoadingLine) und davor ein Sweep-Verlauf. Beides wurde
    bewusst entfernt: die Antwortflaeche selbst zappelt nicht. Der Test haelt
    genau diese Entscheidung fest, statt die geloeschte Animation zu fordern.
    """
    consensus_css = read("static/css/components-consensus.css")
    feedback_css = read("static/css/components-feedback.css")

    # Die Box waehrend der Synthese: rahmenlos und ohne eigene Bewegung.
    assert ".consensus-box.is-synthesizing" in consensus_css
    assert "background: transparent" in consensus_css
    # Keine wandernde Linie und kein Sweep mehr - weder als Regel noch als
    # Keyframe, sonst kaeme die alte Unruhe durch die Hintertuer zurueck.
    assert ".consensus-box.is-synthesizing::after" not in consensus_css
    assert "consensusLoadingLine" not in consensus_css
    assert "consensusLoadingLine" not in feedback_css
    assert "consensusSynthesisSweep" not in feedback_css
    # Der verbleibende Loader ist die ruhige Punktreihe (4px, kein Schatten).
    assert "animation: consensusLoaderDots" in feedback_css
    assert "width: 4px" in feedback_css
    assert "box-shadow: none" in feedback_css
