from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_verdict_color_and_label_follow_the_agreement_score():
    script = (ROOT / "static" / "js" / "consensus-insights.js").read_text(
        encoding="utf-8"
    )
    verdict = script.split("function renderVerdictHeader", 1)[1].split(
        "// --- Agreement-Badges", 1
    )[0]

    assert 'boundedScore >= 65 ? "is-calm"' in verdict
    assert 'boundedScore >= 40 ? "is-warn" : "is-alert"' in verdict
    assert "boundedScore >= 85" in verdict
    assert 'headline.textContent = "High agreement"' in verdict
    assert 'headline.textContent = "Strong agreement"' in verdict
    assert 'headline.textContent = "Partial agreement"' in verdict
    assert 'headline.textContent = "Low agreement"' in verdict
    assert 'headline.textContent = "Very low agreement"' in verdict


def test_settings_offer_three_agreement_display_levels_persistently():
    template = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    init = (ROOT / "static" / "js" / "app-init.js").read_text(encoding="utf-8")
    shell = (ROOT / "static" / "css" / "shell.css").read_text(encoding="utf-8")

    assert 'id="agreementDisplaySelect"' in template
    for value in ("full", "summary", "off"):
        assert f'<option value="{value}">' in template
    # The choice is the account setting agreement_display (user-settings.js).
    assert 'window.App.userSettings.get("agreement_display") || "full"' in init
    assert 'window.App.userSettings.set("agreement_display", mode)' in init
    assert 'classList.toggle("agreement-score-hidden", mode === "summary")' in init
    assert 'classList.toggle("agreement-verdict-hidden", mode === "off")' in init
    # Nur die Zahl weg: die Worte des Urteils bleiben.
    assert "body.agreement-score-hidden .verdict-gauge" in shell
    # Alles weg: unter der Antwort bleiben nur die Schubladen.
    assert "body.agreement-verdict-hidden .consensus-verdict" in shell


def test_footer_status_is_separate_from_navigation_and_tools_follow_it():
    template = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    # The source-check status beside the Sources tab went with the check (2026-10-15).
    assert 'consensusSourceCheckStatus' not in template
    assert template.index('id="consensusFooterTabs"') < template.index('id="consensusFooterActions"')
    assert 'id="consensusMarkerLegend"' not in template
    assert "About these highlights" not in template


def test_the_old_agreement_score_switch_choice_still_applies():
    # Migrated where every setting is read (user-settings.js); its behaviour is
    # tested in tests/js/user-settings.test.mjs ("reads the old agreement switch").
    init = (ROOT / "static" / "js" / "app-init.js").read_text(encoding="utf-8")
    settings = (ROOT / "static" / "js" / "user-settings.js").read_text(encoding="utf-8")

    assert 'const AGREEMENT_SCORE_LEGACY_KEY = "consensio.showAgreementScore.v1";' in settings
    assert 'legacy === "false"' in settings
    assert "consensio.showAgreementScore.v1" not in init


def test_sentence_checks_have_a_discreet_persistent_visibility_control():
    template = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    insights = (ROOT / "static" / "js" / "consensus-insights.js").read_text(
        encoding="utf-8"
    )
    shell = (ROOT / "static" / "css" / "shell.css").read_text(encoding="utf-8")
    inputs = (ROOT / "static" / "css" / "components-input.css").read_text(
        encoding="utf-8"
    )

    assert 'id="consensusMarkerToggle"' not in template
    assert 'id="consensusHighlightsSelect"' in template
    assert "button:not(" not in inputs
    # Persistent as the account setting consensus_highlights (user-settings.js).
    assert 'settings.set("consensus_highlights", show ? highlightMode : "none")' in insights
    assert 'classList.toggle(MARKERS_HIDDEN_CLASS, !show)' in insights
    assert "body.consensus-markers-hidden .consensus-answer-body .claim-badge" in shell


def test_public_mockups_use_the_same_score_semantics():
    landing = (ROOT / "templates" / "landing.html").read_text(encoding="utf-8")
    engine = (ROOT / "templates" / "consensus-engine.html").read_text(
        encoding="utf-8"
    )
    product = (
        ROOT / "templates" / "partials" / "product_result_mockup.html"
    ).read_text(encoding="utf-8")

    assert "Agreement on the core" not in landing
    assert "Agreement on the core" not in engine
    assert "Agreement on the core" not in product
    assert '<div class="consensus-verdict is-calm">' in product
    assert '<span class="verdict-headline">Strong agreement</span>' in product
    # 43 ist der Score, den der Demo-Lauf wirklich rechnet (consensus_scoring
    # auf die Daten in static/demo.js). Scene 02 uebergibt ihn im Lauf-Fuss,
    # Scene 03 zeigt ihn im Verdict — ein Lauf, eine Zahl.
    assert (
        'style="--val:43" title="Agreement score 43/100"' in landing
        and '<span class="verdict-headline">Partial agreement</span>' in landing
    )
    assert "<b>43</b>/100 agreement" in landing
    # Der Landing-Walkthrough zeigt denselben Lauf wie die Demo in /app: unter
    # 65 faerbt der Verdict-Balken amber, sonst behauptet das Mockup eine Ruhe,
    # die der Score nicht deckt.
    assert '<div class="consensus-verdict is-warn">' in landing
    assert (
        'style="--val:64" title="Agreement score 64/100"' in engine
        and '<span class="verdict-headline">Partial agreement</span>' in engine
    )
    assert (
        'style="--val:82" title="Agreement score 82/100"' in engine
        and '<span class="verdict-headline">Strong agreement</span>' in engine
    )
