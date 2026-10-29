// Tab status: a run takes 20 to 60 seconds, and many people switch tabs while
// it works. While the page is hidden, its title says what the visible run is
// doing ("Working…") and, once it is done, that the answer is ready; a run of
// any chat that waits for the user comes first ("Paused"). The
// moment the page is shown again the normal title returns. Nothing changes
// while the page is in front: there the page itself shows the run.
// A screen reader hears that the answer is ready there too (#answerStatus).
(function () {
  "use strict";
  const READY = "Answer ready";
  const WORKING = "Working…";
  const FAILED = "Failed";
  // A reviewer paused the work and the user decides (agent-chat.js renderHold).
  const PAUSED = window.App?.words?.paused || "Paused";
  // The agent handed a step to the user (ask_user, agent-chat.js askCard).
  const YOUR_TURN = window.App?.words?.yourTurn || "Waiting for you";
  let baseTitle = document.title;
  let shown = null; // the label currently in the title, or null for the base
  let watched = { runId: null, status: null };

  function visibleRun() {
    try {
      return window.App?.runRegistry?.visible?.() || null;
    } catch (_) {
      return null;
    }
  }
  // A run of another chat that waits for the user says so too (A-B2): its
  // pause runs into its timeout otherwise, while the tab said nothing.
  function waitingRun() {
    try {
      const runs = window.App?.runRegistry?.list?.() || [];
      const waiting = runs.filter(run => (run?.status === "starting" || run?.status === "running") && run?.metadata?.hold);
      return waiting.find(run => run.metadata.hold.ask) || waiting[0] || null;
    } catch (_) {
      return null;
    }
  }

  // The answer's words arrive without a word about them, and the progress
  // lines leave with the first of them: the end of a run is said in a
  // polite status line (docs/a11y-audit-2026-10-23.md, B4). Failures speak
  // for themselves (role="alert"). Emptied at the start, so the same words
  // are news again for the next run.
  function announce() {
    const run = visibleRun();
    const runId = run?.runId || null;
    const status = run?.status || null;
    const was = watched.runId === runId ? watched.status : null;
    watched = { runId, status };
    const line = document.getElementById("answerStatus");
    if (!line || status === was) return;
    if (status === "starting") line.textContent = "";
    else if (status === "succeeded" && (was === "starting" || was === "running")) line.textContent = window.App.t(READY);
  }

  function label(run) {
    const status = run?.status || null;
    if ((status === "starting" || status === "running") && run?.metadata?.hold) {
      return run.metadata.hold.ask ? YOUR_TURN : PAUSED;
    }
    if (status === "starting" || status === "running") return WORKING;
    if (status === "succeeded") return READY;
    if (status === "failed") return FAILED;
    return null;
  }

  function apply(next) {
    if (next === shown) return;
    if (shown === null) baseTitle = document.title;
    shown = next;
    // The label in the page's language; the question after it stays as asked.
    document.title = next ? `${window.App.t(next)} · ${baseTitle}` : baseTitle;
  }

  // The page's own title, as App.setAppTitle sets it. Every projection of
  // the visible run sets it again, right after the registry event: while a
  // label stands in front, it stays there and the new title is its base.
  function titled(title) {
    if (shown === null) return title;
    baseTitle = title;
    return `${window.App.t(shown)} · ${title}`;
  }

  function sync() {
    if (!document.hidden) { apply(null); return; }
    const next = label(waitingRun() || visibleRun());
    // A run that finished before the page was hidden is not news; one that
    // waits for the user still is.
    if (next && next !== WORKING && next !== PAUSED && next !== YOUR_TURN && shown === null) return;
    apply(next);
  }

  window.addEventListener("consensio:run-registry-change", sync);
  window.addEventListener("consensio:run-registry-change", announce);
  document.addEventListener("visibilitychange", sync);
  window.App = window.App || {};
  window.App.tabStatus = Object.freeze({ titled });
})();
