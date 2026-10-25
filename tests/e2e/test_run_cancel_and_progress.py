"""Regressionen rund um einen laufenden Compare-Lauf:

1. Der Send-Button bleibt Cancel-Button, bis alle Antworten da sind, und
   wird danach wieder zum Senden.
2. Ein Klick waehrend der Antworten bricht genau diesen Lauf ab.
3. Die Antworten des zweiten Laufs starten leer, nicht mit denen des ersten.

Bis 2026-10-25 prueften diese Tests den Consensus-Durchlauf im Browser
(Consensus/Differences nach den Antworten, Modellzeilen im gefuehrten Lauf);
den startet der Browser nicht mehr.
"""

import re

from playwright.sync_api import expect

from test_smoke import _send_question, _wait_for_all_final_answers

CANCEL_CLASS = re.compile(r"(?:^|\s)is-cancel-action(?:\s|$)")


def _wait_for_run_start(page, timeout=20000):
    """Beim zweiten Lauf stehen die alten Antworten noch in den Boxen (der
    Send-Pfad wartet erst auf Token/Usage-Release). Ohne diesen Sync wuerde
    ein Wait auf die Antworttexte sofort mit dem Vorlauf durchlaufen."""
    page.wait_for_function(
        """() => document.getElementById("openaiResponse").dataset.responseState === "pending" """,
        timeout=timeout,
    )


def test_send_button_stays_cancelable_until_the_answers_are_done(app_page):
    app_page.evaluate(
        """() => {
          const button = document.getElementById("sendButton");
          window.__cancelSamples = [];
          const sample = () => {
            const run = window.App.runRegistry.visible();
            if (!run || run.status !== "running") return;
            window.__cancelSamples.push({phase: run.phase, cancelable: button.classList.contains("is-cancel-action")});
          };
          const onRunChange = () => queueMicrotask(sample);
          window.addEventListener("consensio:run-registry-change", onRunChange);
          window.__stopCancelObservation = () => window.removeEventListener("consensio:run-registry-change", onRunChange);
        }"""
    )

    _send_question(app_page)
    _wait_for_all_final_answers(app_page)
    app_page.wait_for_function("() => window.App.runRegistry.visible()?.status === 'succeeded'", timeout=30000)
    app_page.evaluate("() => window.__stopCancelObservation()")
    samples = app_page.evaluate("() => window.__cancelSamples")
    assert any(sample["phase"] == "answers" for sample in samples), samples
    assert all(sample["cancelable"] for sample in samples), samples
    expect(app_page.locator("#sendButton")).not_to_have_class(CANCEL_CLASS)


def test_send_button_cancels_a_running_compare(app_page):
    # The answers are held, so the run is still answering when Send stops it.
    held = []
    app_page.route("**/ask_*", lambda route: held.append(route))
    _send_question(app_page)
    # Past the duplicate-click window (query-send.js), the second Send is a stop.
    app_page.wait_for_function(
        "() => { const run = window.App.runRegistry.visible();"
        " return run?.phase === 'answers' && Date.now() - run.startedAt >= 460; }",
        timeout=20000,
    )
    expect(app_page.locator("#sendButton")).to_have_class(CANCEL_CLASS)
    app_page.evaluate("() => window.sendQuestion()")
    app_page.wait_for_function("() => window.App.runRegistry.visible()?.status === 'canceled'", timeout=10000)
    assert held, "no answer was asked for"
    assert app_page.evaluate("() => window.isQueryRequestRunning()") is False
    expect(app_page.locator("#sendButton")).not_to_have_class(CANCEL_CLASS)


def test_answers_restart_empty_on_a_second_run(app_page):
    """Die Antworten des zweiten Laufs sind gemessen, nicht geerbt: sie
    muessen erst wieder warten und dann frisch erscheinen."""
    app_page.set_viewport_size({"width": 390, "height": 844})

    _send_question(app_page)
    _wait_for_all_final_answers(app_page)
    app_page.wait_for_function("() => window.App.runRegistry.visible()?.status === 'succeeded'", timeout=30000)

    # Lauf 2 engmaschig mitschneiden: die Antworten MUESSEN zwischendurch
    # wieder warten, sonst zeigen sie noch den Vorlauf.
    app_page.evaluate(
        """() => {
          window.__waitingSamples = [];
          window.__waitingSampler = setInterval(() => {
            window.__waitingSamples.push(
              document.querySelectorAll('.is-direct .answer-reader-body[aria-busy="true"]').length);
          }, 30);
        }"""
    )

    # Ein frischer Lauf beginnt ueber "New chat" in der Sidebar, genau wie in
    # der App. Die Sidebar ist auf dieser Breite eingeklappt.
    app_page.locator(".sidebar-toggle:visible").first.click()
    app_page.locator("#newRunButton").click()
    expect(app_page.locator("#questionInput")).to_be_visible()
    expect(app_page.locator("#questionInput")).to_be_enabled()

    _send_question(app_page)
    _wait_for_run_start(app_page)
    _wait_for_all_final_answers(app_page)
    app_page.wait_for_function("() => window.App.runRegistry.visible()?.status === 'succeeded'", timeout=30000)
    app_page.evaluate("() => clearInterval(window.__waitingSampler)")

    samples = app_page.evaluate("() => window.__waitingSamples")
    assert samples, "Keine Proben - lief der zweite Lauf ueberhaupt?"
    assert max(samples) > 0, "Die Antworten des zweiten Laufs starteten nicht leer"
    assert samples[-1] == 0, "Nach dem Lauf wartet keine Antwort mehr"
