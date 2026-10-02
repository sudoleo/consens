"""Regressionen rund um den laufenden Consensus-Durchlauf:

1. Der Send-Button bleibt Cancel-Button, bis auch Consensus/Differences
   fertig sind (vorher sprang er zurueck, sobald die Modelle geantwortet
   hatten - der Lauf war dann nicht mehr abbrechbar).
2. Die Modellzeilen des zweiten Laufs zeigen den zweiten Lauf - nicht die
   Zeiten des ersten. (Die frueher hier gemessenen Chip-Ladebalken sind
   entfallen: die Antworten streamen sichtbar, ein geschaetzter Balken war
   die dritte Auskunft ueber denselben Vorgang.)

Die frueher hier gepruefte Fortschrittsleiste des Differences-Laufs ist
entfallen: der gefuehrte Lauf ueber dem Thread zeigt dieselbe Phase schon
mit einem Balken, zwei Balken fuer einen Vorgang waren zu viel.
"""

import re

from playwright.sync_api import expect

from test_smoke import _send_question, _wait_for_all_final_answers


def _wait_for_consensus_idle(page, timeout=60000):
    page.wait_for_function(
        "() => window.App.consensusLifecycle.isRunning() === false",
        timeout=timeout,
    )


def _wait_for_consensus_start(page, timeout=30000):
    page.wait_for_function(
        "() => window.App.consensusLifecycle.isRunning() === true",
        timeout=timeout,
    )


def _wait_for_run_start(page, timeout=20000):
    """Beim zweiten Lauf stehen die alten Antworten noch in den Boxen (der
    Send-Pfad wartet erst auf Token/Usage-Release). Ohne diesen Sync wuerde
    ein Wait auf die Antworttexte sofort mit dem Vorlauf durchlaufen."""
    page.wait_for_function(
        """() => document.getElementById("openaiResponse").dataset.responseState === "pending" """,
        timeout=timeout,
    )


def test_send_button_stays_cancelable_until_consensus_is_done(app_page):
    # Observe actual RunContext/DOM changes. The registry-owned production path
    # no longer calls the legacy consensusLifecycle.startRun bridge.
    app_page.evaluate(
        """() => {
          const button = document.getElementById("sendButton");
          window.__consensusCancelSamples = [];
          const sample = () => {
            if (!window.App.consensusLifecycle.isRunning()) return;
            window.__consensusCancelSamples.push({
              status: window.App.runRegistry.visible().consensus.status,
              cancelable: button.classList.contains("is-cancel-action")
            });
          };
          const onRunChange = () => queueMicrotask(sample);
          window.addEventListener("consensio:run-registry-change", onRunChange);
          const observer = new MutationObserver(sample);
          observer.observe(button, {attributes: true, attributeFilter: ["class"]});
          observer.observe(document.getElementById("consensusResponse"), {
            childList: true, subtree: true, characterData: true
          });
          window.__stopConsensusCancelObservation = () => {
            observer.disconnect();
            window.removeEventListener("consensio:run-registry-change", onRunChange);
          };
        }"""
    )

    _send_question(app_page)
    _wait_for_all_final_answers(app_page)

    app_page.wait_for_function(
        "() => window.__consensusCancelSamples.length > 0",
        timeout=30000,
    )
    # Erst wenn der Consensus durch ist, wird wieder gesendet statt abgebrochen.
    _wait_for_consensus_idle(app_page)
    app_page.evaluate("() => window.__stopConsensusCancelObservation()")
    samples = app_page.evaluate("() => window.__consensusCancelSamples")
    assert any(sample["status"] == "pending" for sample in samples), samples
    assert any(sample["status"] in {"streaming", "differences"} for sample in samples), samples
    assert all(sample["cancelable"] for sample in samples), samples
    expect(app_page.locator("#sendButton")).not_to_have_class(
        re.compile(r"(?:^|\s)is-cancel-action(?:\s|$)")
    )


def test_send_button_cancels_a_running_consensus(app_page):
    _send_question(app_page)
    _wait_for_all_final_answers(app_page)
    app_page.wait_for_function(
        "() => window.App.consensusLifecycle.isRunning() === true",
        timeout=30000,
    )

    app_page.evaluate("() => window.sendQuestion()")
    assert app_page.evaluate("() => window.App.consensusLifecycle.isRunning()") is False
    expect(app_page.locator("#sendButton")).not_to_have_class(
        re.compile(r"(?:^|\s)is-cancel-action(?:\s|$)")
    )


def test_model_rows_restart_empty_on_a_second_run(app_page):
    """Die Zeit neben einem Modell ist gemessen, nicht geerbt: beim zweiten
    Lauf muessen die Zeilen erst wieder leer sein (·) und dann frische
    Zeiten zeigen. Vorher hing hier ein geschaetzter Balken, der das
    "complete" des Vorlaufs las und sofort auf 100 % einrastete."""
    app_page.set_viewport_size({"width": 390, "height": 844})
    app_page.evaluate("() => window.App.runMode.set('consensus')")

    _send_question(app_page)
    _wait_for_all_final_answers(app_page)
    _wait_for_consensus_start(app_page)
    _wait_for_consensus_idle(app_page)

    # Lauf 2 engmaschig mitschneiden: die Zeilen MUESSEN zwischendurch wieder
    # ohne Zeit dastehen, sonst zeigen sie noch den Vorlauf.
    app_page.evaluate(
        """() => {
          window.__rowSamples = [];
          window.__rowSampler = setInterval(() => {
            const rows = [...document.querySelectorAll("#runDetail .run-model")];
            if (!rows.length) return;
            window.__rowSamples.push(
              rows.filter((row) => row.dataset.state === "done").length
            );
          }, 30);
        }"""
    )

    # Nach einer beantworteten Frage laeuft das Gespraech weiter. Dieser Test
    # misst einen frischen Lauf, deshalb hier bewusst der Ausstieg ueber
    # "New comparison" in der Sidebar - genau wie in der App. Die Sidebar ist
    # auf dieser Breite eingeklappt, deshalb erst aufklappen.
    app_page.locator(".sidebar-toggle:visible").first.click()
    app_page.locator("#newRunButton").click()
    expect(app_page.locator("#questionInput")).to_be_visible()
    expect(app_page.locator("#questionInput")).to_be_enabled()

    _send_question(app_page)
    _wait_for_run_start(app_page)
    _wait_for_all_final_answers(app_page)
    app_page.evaluate("() => clearInterval(window.__rowSampler)")

    samples = app_page.evaluate("() => window.__rowSamples")
    assert samples, "Keine Modellzeilen gefunden - lief der zweite Lauf ueberhaupt?"
    assert min(samples) == 0, (
        "Die Modellzeilen starteten den zweiten Lauf nicht leer "
        f"(kleinster Wert: {min(samples)})"
    )
    assert max(samples) > 0, "Keine Zeile wurde im zweiten Lauf fertig"
