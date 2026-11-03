/**
 * A Watch's runs in its chat (thread-history.js, since 2026-11-03): a run's
 * message says the Watch sent it, and runs that found nothing, one after
 * another, fold into one line; what a run found stays a turn of its own.
 */
import { describe, expect, it } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

const RUN = { watch_id: "w".repeat(32), scheduled_at: "2026-11-03T07:00:00+00:00", request_id: "watch.w.1", goal: "" };

function turn(id, extra = {}) {
  return { id: id.repeat(32), turn_id: id.repeat(32), question: "Check whether registration is open.",
    consensus: "Still closed.", status: "completed", mode: "Agent", execution_mode: "agent",
    created_at: new Date(Date.now() - 3600 * 1000).toISOString(), ...extra };
}

const quiet = id => turn(id, { agent_settings: { watch_run: RUN } });

function boot() {
  return loadScripts(["static/js/thread-history.js"], {
    body: '<div id="threadHistory" hidden></div><div id="threadAsk" class="thread-ask"><div class="thread-ask-bubble"></div></div>',
  });
}

describe("A Watch's runs in its chat", () => {
  it("folds quiet runs into one line and keeps a finding a turn of its own", () => {
    const { window, document } = boot();
    window.App.followup.renderStoredTurns([
      turn("a", { question: "Tell me when registration opens." }),
      quiet("b"), quiet("c"),
      turn("d", { agent_settings: { watch_run: RUN }, consensus: "It is open.",
        agent_watch_run: { finding: { summary: "Open.", evidence_url: "https://www.ironman.com" } } }),
      quiet("e"),
    ]);
    const history = document.getElementById("threadHistory");
    const folds = [...history.querySelectorAll(".thread-watch-fold-button")];
    expect(folds.map(button => button.textContent)).toEqual([
      "Checked 2 times · nothing new · last 1h ago", "Checked once · nothing new · 1h ago"]);
    const turns = [...history.querySelectorAll(".thread-history-turn")];
    expect(turns.map(node => node.classList.contains("is-watch-folded"))).toEqual([false, true, true, false, true]);
    // The finding and the user's own message stay; the runs say the Watch sent them.
    expect(turns[0].querySelector(".thread-watch-run")).toBeNull();
    expect(turns[3].querySelector(".thread-watch-run").textContent).toBe("Scheduled Watch run");
    folds[0].click();
    expect(folds[0].getAttribute("aria-expanded")).toBe("true");
    expect(turns[1].classList.contains("is-watch-folded")).toBe(false);
    // A later render keeps what the reader opened.
    window.App.followup.renderStoredTurns([turn("a", { question: "Tell me when registration opens." }),
      quiet("b"), quiet("c"), turn("d", { agent_settings: { watch_run: RUN }, consensus: "It is open.",
        agent_watch_run: { finding: { summary: "Open." } } }), quiet("e"), quiet("f")]);
    const again = [...history.querySelectorAll(".thread-watch-fold-button")];
    expect(again[0].getAttribute("aria-expanded")).toBe("true");
    expect(again[1].textContent).toBe("Checked 2 times · nothing new · last 1h ago");
  });

  it("labels the live question of a run and clears it for the user's own", () => {
    const { window, document } = boot();
    const ask = document.getElementById("threadAsk");
    window.App.followup.markWatchRun(ask, quiet("a"));
    expect(ask.querySelector(".thread-watch-run").textContent).toBe("Scheduled Watch run");
    expect(ask.firstElementChild.classList.contains("thread-watch-run")).toBe(true);
    window.App.followup.markWatchRun(ask, turn("b"));
    expect(ask.querySelector(".thread-watch-run")).toBeNull();
  });
});
