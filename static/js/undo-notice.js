// =====================================================================
// undo-notice.js
// One quiet line at the bottom of the screen: what just happened and the
// way back ("Chat deleted · Undo"). Nothing that can be taken back is
// final at once (Apple audit E2). A shared building block until the app's
// common notice system replaces it:
//
//   const notice = App.undoNotice.show({
//     text: "Chat deleted",
//     actionLabel: "Undo",          // optional, default "Undo"
//     onAction() {},                // the way back
//     onExpire() {},                // the line went away without its action
//     duration: 5000,               // ms; hover and keyboard focus pause it
//   });
//   notice.settle();                // ends it now as if it had run out
//   notice.cancel();                // ends it now without either callback
//
// A new line settles the one before it: its action is no longer offered,
// so whatever it held back happens now.
// =====================================================================
(function () {
  "use strict";
  const App = window.App = window.App || {};
  const quiet = window.matchMedia?.("(prefers-reduced-motion: reduce)");
  let current = null;

  function host() {
    let element = document.getElementById("undoNotice");
    if (element) return element;
    element = document.createElement("div");
    element.id = "undoNotice";
    element.className = "undo-notice";
    element.setAttribute("role", "status");
    element.setAttribute("aria-live", "polite");
    element.hidden = true;
    const text = document.createElement("span");
    text.className = "undo-notice-text";
    const action = document.createElement("button");
    action.type = "button";
    action.className = "undo-notice-action";
    element.append(text, action);
    document.body.append(element);
    return element;
  }

  function leave(element) {
    element.classList.remove("is-shown");
    const done = () => { if (!element.classList.contains("is-shown")) element.hidden = true; };
    if (quiet?.matches || !element.getAnimations) { done(); return; }
    // The way out mirrors the way in (undo-notice.css transition).
    window.setTimeout(done, 220);
  }

  function show({ text, actionLabel = "Undo", onAction = null, onExpire = null, duration = 5000 } = {}) {
    current?.settle();
    const element = host();
    const label = element.querySelector(".undo-notice-text");
    const action = element.querySelector(".undo-notice-action");
    label.textContent = String(text || "");
    action.textContent = actionLabel;
    action.hidden = typeof onAction !== "function";
    let timer = 0, remaining = duration, startedAt = 0, ended = false;
    const notice = {
      settle() { end(onExpire); },
      cancel() { end(null); },
    };
    function end(callback) {
      if (ended) return;
      ended = true;
      window.clearTimeout(timer);
      element.removeEventListener("pointerenter", pause);
      element.removeEventListener("pointerleave", resume);
      element.removeEventListener("focusin", pause);
      element.removeEventListener("focusout", resume);
      action.onclick = null;
      if (current === notice) current = null;
      // Only the line still showing this notice leaves; a newer one stays.
      if (!current) leave(element);
      try { callback?.(); } catch (error) { console.error("Undo notice callback failed:", error); }
    }
    function run() {
      startedAt = Date.now();
      timer = window.setTimeout(() => end(onExpire), remaining);
    }
    function pause() {
      if (ended || !timer) return;
      window.clearTimeout(timer);
      timer = 0;
      remaining = Math.max(1200, remaining - (Date.now() - startedAt));
    }
    function resume() {
      if (ended || timer || element.contains(document.activeElement)) return;
      run();
    }
    action.onclick = () => end(onAction);
    element.addEventListener("pointerenter", pause);
    element.addEventListener("pointerleave", resume);
    element.addEventListener("focusin", pause);
    element.addEventListener("focusout", resume);
    element.hidden = false;
    // The next frame, so the entry transition runs from its start.
    void element.offsetWidth;
    element.classList.add("is-shown");
    current = notice;
    run();
    return notice;
  }

  App.undoNotice = { show, current: () => current };
})();
