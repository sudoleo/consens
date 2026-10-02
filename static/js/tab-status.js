// Tab status: a run takes 20 to 60 seconds, and many people switch tabs while
// it works. While the page is hidden, its title says what the visible run is
// doing ("Working…") and, once it is done, that the answer is ready. The
// moment the page is shown again the normal title returns. Nothing changes
// while the page is in front: there the page itself shows the run.
(function () {
  "use strict";
  const READY = "Answer ready";
  const WORKING = "Working…";
  const FAILED = "Run stopped";
  let baseTitle = document.title;
  let shown = null; // the label currently in the title, or null for the base

  function visibleStatus() {
    try {
      return window.App?.runRegistry?.visible?.()?.status || null;
    } catch (_) {
      return null;
    }
  }

  function label(status) {
    if (status === "starting" || status === "running") return WORKING;
    if (status === "succeeded") return READY;
    if (status === "failed") return FAILED;
    return null;
  }

  function apply(next) {
    if (next === shown) return;
    if (shown === null) baseTitle = document.title;
    shown = next;
    document.title = next ? `${next} · ${baseTitle}` : baseTitle;
  }

  function sync() {
    if (!document.hidden) { apply(null); return; }
    const next = label(visibleStatus());
    // A run that finished before the page was hidden is not news.
    if (next && next !== WORKING && shown === null) return;
    apply(next);
  }

  window.addEventListener("consensio:run-registry-change", sync);
  document.addEventListener("visibilitychange", sync);
})();
