// =====================================================================
// notices.js
// One notice system for the whole app (Apple audit E3):
//
//   App.toast({ message, tone, action, undo, onExpire, duration, key })
//     One line just above the composer (or the bottom edge where there is
//     none), above the keyboard and the safe area. One at a time; what comes
//     while another is showing waits its turn. It stays as long as it takes
//     to read (by length), pauses under the pointer and the keyboard, and an
//     error stays until it is closed. role=status, so it is read out.
//       tone      "info" (default) | "success" | "error"
//       action    { label, onAction }   onAction may return a promise; the
//                 line then shows it is working and stays until it settles
//       undo      () => {}              shorthand for action "Undo"
//       onExpire  () => {}              the line went away without its action
//       duration  ms, or Infinity       default: by length; errors Infinity
//       key       a second toast with the same key replaces the first
//     -> { update({message, tone, action, duration}), settle(), cancel(),
//          dismiss(), focusAction() }
//
//   App.toast.current()   the toast on screen, or null
//   App.toast.settleAll() lets every pending action-less ending happen now
//                         (logout, leaving a page)
//
//   App.composerNotice.show(message, { tone, for: element })
//   App.composerNotice.clear()
//     A mistake in what is being typed or attached is said where it
//     happened, at the composer, not in a window (Apple audit E1).
//
// The older names forward here: App.undoNotice.show (chat deletion),
// App.showPopup (app-core.js), App.watchDashboard.showUndoToast.
// =====================================================================
(function () {
  "use strict";
  const App = window.App = window.App || {};

  const MIN_VISIBLE_MS = 1600;   // a line is seen before the next replaces it
  const MIN_DURATION_MS = 3000;
  const MAX_DURATION_MS = 10000;
  const ACTION_MIN_MS = 5000;    // an Undo needs time to be found

  let host = null;
  let current = null;            // the toast record on screen
  const queue = [];

  function readingTime(message, hasAction) {
    const words = String(message || "").trim().split(/\s+/).filter(Boolean).length;
    // About 240 words a minute plus the moment it takes to look down.
    const time = Math.min(MAX_DURATION_MS, Math.max(MIN_DURATION_MS, 1000 + words * 250));
    return hasAction ? Math.max(ACTION_MIN_MS, time) : time;
  }

  const CLOSE_ICON = '<svg class="close-icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false">'
    + '<path d="M4 4l8 8M12 4l-8 8"/></svg>';

  function ensureHost() {
    if (host?.isConnected) return host;
    host = document.getElementById("appToasts");
    if (!host) {
      host = document.createElement("div");
      host.id = "appToasts";
      host.className = "toast-region";
      host.setAttribute("role", "status");
      host.setAttribute("aria-live", "polite");
      document.body.append(host);
    }
    return host;
  }

  // Where the line sits: just above the composer when there is one on
  // screen, else above the bottom edge; never under the keyboard.
  function placeHost() {
    const region = ensureHost();
    const viewport = window.visualViewport;
    const bottomEdge = viewport ? viewport.offsetTop + viewport.height : window.innerHeight;
    let lift = Math.max(0, window.innerHeight - bottomEdge);
    const composer = document.querySelector(".input-section");
    const rect = composer && !composer.closest("[hidden], [inert]") ? composer.getBoundingClientRect() : null;
    if (rect && rect.height && rect.top < bottomEdge && rect.bottom > bottomEdge - 400
        && !document.body.classList.contains("is-hero")
        && !document.body.classList.contains("is-watch-view")) {
      lift = Math.max(lift, window.innerHeight - rect.top + 4);
    }
    region.style.setProperty("--toast-lift", `${Math.round(lift)}px`);
  }

  function build(record) {
    const node = document.createElement("div");
    node.className = "toast";
    node.dataset.tone = record.tone;
    const text = document.createElement("span");
    text.className = "toast-text";
    const action = document.createElement("button");
    action.type = "button";
    action.className = "toast-action";
    const close = document.createElement("button");
    close.type = "button";
    close.className = "toast-close close-button";
    close.setAttribute("aria-label", "Dismiss");
    close.innerHTML = CLOSE_ICON;
    node.append(text, action, close);
    action.addEventListener("click", () => runAction(record));
    close.addEventListener("click", () => end(record, "dismissed"));
    node.addEventListener("pointerenter", () => pause(record));
    node.addEventListener("pointerleave", () => resume(record));
    node.addEventListener("focusin", () => pause(record));
    node.addEventListener("focusout", () => resume(record));
    record.node = node;
    paint(record);
  }

  function paint(record) {
    const node = record.node;
    if (!node) return;
    node.dataset.tone = record.tone;
    node.querySelector(".toast-text").textContent = record.message;
    const action = node.querySelector(".toast-action");
    action.hidden = !record.action;
    action.textContent = record.action?.label || "";
    action.disabled = record.busy;
    node.setAttribute("aria-busy", String(record.busy));
    // A line that does not go away by itself can be closed.
    node.querySelector(".toast-close").hidden = Number.isFinite(record.duration);
  }

  function normalize(options) {
    const opts = typeof options === "string" ? { message: options } : (options || {});
    const action = opts.action?.label
      ? { label: String(opts.action.label), onAction: opts.action.onAction || opts.action.run || null }
      : typeof opts.undo === "function" ? { label: "Undo", onAction: opts.undo } : null;
    const tone = ["success", "error"].includes(opts.tone) ? opts.tone : "info";
    const message = String(opts.message ?? opts.text ?? "");
    const duration = opts.duration === Infinity || (opts.duration == null && tone === "error")
      ? Infinity
      : Number.isFinite(opts.duration) && opts.duration > 0 ? opts.duration : readingTime(message, Boolean(action));
    return { message, tone, action, duration, onExpire: opts.onExpire || null, key: opts.key || null };
  }

  function handleFor(record) {
    return {
      update(changes = {}) {
        if (record.ended) return;
        if ("message" in changes) record.message = String(changes.message ?? "");
        if ("tone" in changes) record.tone = ["success", "error"].includes(changes.tone) ? changes.tone : "info";
        if ("action" in changes) {
          record.action = changes.action?.label ? { label: changes.action.label, onAction: changes.action.onAction || null } : null;
        }
        record.busy = false;
        paint(record);
        if ("duration" in changes || "message" in changes) {
          record.duration = changes.duration === Infinity ? Infinity
            : Number.isFinite(changes.duration) ? changes.duration : readingTime(record.message, Boolean(record.action));
          paint(record);
          if (record === current) restart(record);
        }
      },
      settle() { end(record, "expired"); },
      cancel() { end(record, null); },
      dismiss() { end(record, "dismissed"); },
      focusAction() {
        const button = record.node?.querySelector(".toast-action:not([hidden])");
        if (button) button.focus({ preventScroll: true });
      },
      get ended() { return record.ended; },
    };
  }

  function toast(options) {
    const record = { ...normalize(options), node: null, ended: false, busy: false,
      timer: 0, remaining: 0, startedAt: 0, shownAt: 0, paused: false };
    record.remaining = record.duration;
    const handle = handleFor(record);
    record.handle = handle;

    if (record.key) {
      if (current && current.key === record.key) end(current, "replaced");
      for (const waiting of queue.filter(item => item.key === record.key)) end(waiting, "replaced");
    }
    // The same words again restart the line instead of queueing a copy.
    if (current && !current.ended && !current.action && !record.action
        && current.message === record.message && current.tone === record.tone) {
      restart(current);
      return current.handle;
    }

    if (!current) {
      present(record);
    } else if (record.action) {
      // An Undo belongs to what the user just did: it shows now, and what
      // was on screen gives way (an older Undo happens). An error steps
      // back and comes again after it: it stays until it is closed (E3).
      if (!Number.isFinite(current.duration) && !current.action && !current.busy) setAside(current);
      else end(current, "replaced");
      present(record);
    } else {
      queue.push(record);
      hurry(current);
    }
    return handle;
  }

  // The line on screen gives way to the queue once it has been seen,
  // unless it holds an action the user might still take, is working, or
  // stays until it is closed (an error: E3; it went after 1.6 s when another
  // line came, review E3). What comes then waits behind it.
  function hurry(record) {
    if (!record || record.ended || record.action || record.busy || !queue.length) return;
    if (!Number.isFinite(record.duration)) return;
    const seen = Date.now() - record.shownAt;
    const left = Math.max(0, MIN_VISIBLE_MS - seen);
    window.clearTimeout(record.timer);
    record.timer = window.setTimeout(() => end(record, "expired"), left);
  }

  // The line leaves the screen without ending: first in the queue again.
  function setAside(record) {
    window.clearTimeout(record.timer);
    record.paused = false;
    current = null;
    const node = record.node;
    record.node = null;
    if (node) {
      node.classList.remove("is-shown");
      const remove = () => window.setTimeout(() => node.remove(), 0);
      if (App.motion?.leave) App.motion.leave(node, remove);
      else remove();
    }
    queue.unshift(record);
  }

  function present(record) {
    current = record;
    const region = ensureHost();
    App.toast.__adoptRegion?.();
    placeHost();
    build(record);
    region.append(record.node);
    record.shownAt = Date.now();
    // The next frame, so the entry transition runs from its start.
    void record.node.offsetWidth;
    record.node.classList.add("is-shown");
    restart(record);
  }

  function restart(record) {
    window.clearTimeout(record.timer);
    record.remaining = record.duration;
    if (record.paused) return;
    run(record);
  }

  function run(record) {
    if (!Number.isFinite(record.remaining) || record.busy) return;
    record.startedAt = Date.now();
    record.timer = window.setTimeout(() => end(record, "expired"), record.remaining);
    if (queue.length) hurry(record);
  }

  function pause(record) {
    if (record.ended || record.paused) return;
    record.paused = true;
    window.clearTimeout(record.timer);
    if (Number.isFinite(record.remaining) && record.startedAt) {
      record.remaining = Math.max(1200, record.remaining - (Date.now() - record.startedAt));
    }
  }

  function resume(record) {
    if (record.ended || !record.paused) return;
    if (record.node?.matches(":hover") || record.node?.contains(document.activeElement)) return;
    record.paused = false;
    run(record);
  }

  async function runAction(record) {
    if (record.ended || record.busy || !record.action) return;
    const callback = record.action.onAction;
    record.busy = true;
    window.clearTimeout(record.timer);
    paint(record);
    let result;
    try {
      result = callback?.(record.handle);
    } catch (error) {
      console.error("Toast action failed:", error);
    }
    if (result && typeof result.then === "function") {
      // The caller says how it went with update(); until then the line waits.
      try { await result; } catch (error) { console.error("Toast action failed:", error); }
      if (!record.ended && record.busy) end(record, "acted");
      return;
    }
    if (!record.ended && record.busy) end(record, "acted");
  }

  function end(record, reason) {
    if (!record || record.ended) return;
    record.ended = true;
    window.clearTimeout(record.timer);
    const queued = queue.indexOf(record);
    if (queued >= 0) queue.splice(queued, 1);
    // Leaving without its action is "expired": what the action would have
    // taken back now happens (a deletion is final).
    if (reason === "expired" || reason === "replaced" || reason === "dismissed") {
      try { record.onExpire?.(); } catch (error) { console.error("Toast callback failed:", error); }
    }
    if (record !== current) return;
    current = null;
    const node = record.node;
    if (node) {
      node.classList.remove("is-shown");
      // Never in the same task: a click on the line's own button is still
      // on its way up, and handlers further up ask where it came from (the
      // phone sidebar stays open for a click inside the notice line).
      const remove = () => window.setTimeout(() => node.remove(), 0);
      if (App.motion?.leave) App.motion.leave(node, remove);
      else remove();
    }
    // A line replaced by another (an Undo, the same key) gives its place to
    // that one, which the caller shows now; what waited keeps waiting. Moving
    // the queue on here showed a waiting line under the new one, and nothing
    // ever took it away again (review 7).
    if (reason === "replaced") return;
    const next = queue.shift();
    if (next) present(next);
  }

  toast.current = () => current?.handle || null;
  toast.settleAll = () => {
    for (const waiting of queue.splice(0)) end(waiting, "expired");
    if (current) end(current, "expired");
  };
  App.toast = toast;

  window.addEventListener("resize", () => { if (current) placeHost(); });
  window.visualViewport?.addEventListener("resize", () => { if (current) placeHost(); });

  // --- The thin forward of the first shared Undo line (chat deletion) ----
  // App.undoNotice.show({text, actionLabel, onAction, onExpire, duration})
  App.undoNotice = {
    show({ text, actionLabel = "Undo", onAction = null, onExpire = null, duration } = {}) {
      return toast({
        message: text,
        action: typeof onAction === "function" ? { label: actionLabel, onAction } : null,
        onExpire,
        duration,
      });
    },
    current: () => toast.current(),
  };

  // --- Inline notice at the composer ----------------------------------------
  function composerNoticeEl() {
    let el = document.getElementById("composerInputNotice");
    if (el) return el;
    const anchor = document.getElementById("agentComposerNotice");
    if (!anchor?.parentElement) return null;
    el = document.createElement("p");
    el.id = "composerInputNotice";
    el.className = "agent-composer-notice composer-input-notice";
    el.setAttribute("role", "alert");
    el.hidden = true;
    anchor.after(el);
    return el;
  }

  let noticeTimer = 0;
  let noticeFor = null;
  let noticeMotion = null;
  let noticeClosing = false;

  // The line opens and closes its own height, softly: the composer and what
  // sits under it are not pushed in one frame. A fold that turns around
  // (a new notice while the old one folds away) goes on from where it is.
  function foldNotice(el, opening, done) {
    const style = getComputedStyle(el);
    const from = noticeMotion ? { height: style.height, opacity: Number(style.opacity), marginTop: style.marginTop, marginBottom: style.marginBottom } : null;
    noticeMotion?.cancel();
    noticeMotion = null;
    noticeClosing = !opening;
    if (!el.animate || App.motion?.reduced?.()) { noticeClosing = false; done?.(); return; }
    el.style.overflow = "hidden";
    const height = el.getBoundingClientRect().height;
    const closed = { height: "0px", opacity: 0, marginTop: "0px", marginBottom: "0px" };
    const settled = getComputedStyle(el);
    const open = { height: `${height}px`, opacity: 1, marginTop: settled.marginTop, marginBottom: settled.marginBottom };
    noticeMotion = el.animate([from || (opening ? closed : open), opening ? open : closed], {
      duration: App.motion?.ms?.("state") ?? 200,
      easing: App.motion?.ease?.(opening ? "out" : "in") ?? "ease",
    });
    noticeMotion.onfinish = () => {
      noticeMotion = null;
      noticeClosing = false;
      el.style.overflow = "";
      done?.();
    };
    noticeMotion.oncancel = () => { el.style.overflow = ""; };
  }
  App.composerNotice = {
    show(message, { tone = "error", for: field = null, duration = 0 } = {}) {
      const el = composerNoticeEl();
      if (!el) { toast({ message, tone }); return; }
      window.clearTimeout(noticeTimer);
      // A notice still folding away is taken over by this one: its fold
      // turns around instead of hiding the new words when it ends (review 6).
      const wasHidden = el.hidden || noticeClosing;
      el.textContent = String(message || "");
      el.dataset.tone = tone;
      el.hidden = !message;
      if (wasHidden && message) foldNotice(el, true);
      else if (!message && noticeClosing) { noticeMotion?.cancel(); noticeMotion = null; noticeClosing = false; }
      noticeFor = field || document.getElementById("questionInput");
      if (noticeFor) {
        const ids = new Set((noticeFor.getAttribute("aria-describedby") || "").split(/\s+/).filter(Boolean));
        ids.add(el.id);
        noticeFor.setAttribute("aria-describedby", [...ids].join(" "));
      }
      if (duration > 0) noticeTimer = window.setTimeout(() => App.composerNotice.clear(), duration);
    },
    clear() {
      window.clearTimeout(noticeTimer);
      const el = document.getElementById("composerInputNotice");
      if (el && !el.hidden) {
        foldNotice(el, false, () => { el.hidden = true; el.textContent = ""; });
      }
      if (noticeFor) {
        const ids = (noticeFor.getAttribute("aria-describedby") || "").split(/\s+/)
          .filter(id => id && id !== "composerInputNotice");
        if (ids.length) noticeFor.setAttribute("aria-describedby", ids.join(" "));
        else noticeFor.removeAttribute("aria-describedby");
      }
      noticeFor = null;
    },
    current() {
      const el = document.getElementById("composerInputNotice");
      return el && !el.hidden ? el.textContent : "";
    },
  };
  // Changing what the notice is about takes it away.
  document.addEventListener("input", event => {
    if (noticeFor && event.target === noticeFor) App.composerNotice.clear();
  });

  // A notice shown while a modal dialog is open goes inside that dialog:
  // everything outside the top dialog is inert and painted under it, so the
  // line would be hidden and its Undo out of reach. It moves back when the
  // dialog closes.
  function topModalDialog() {
    const open = Array.from(document.querySelectorAll("dialog[open]"));
    const modal = open.filter(dialog => {
      try { return dialog.matches(":modal"); } catch (_) { return true; }
    });
    return modal[modal.length - 1] || null;
  }
  function adoptRegion() {
    const region = ensureHost();
    const target = topModalDialog() || document.body;
    if (region.parentElement !== target) target.append(region);
  }
  // A dialog that opens or closes while a line is on screen takes it along:
  // it never stays under the open dialog, and never inside a closed one
  // while another is still open (review E3). The `open` attribute is the
  // one signal every way of opening and closing a dialog sets.
  if (typeof MutationObserver === "function") {
    new MutationObserver(records => {
      if (host?.isConnected && records.some(record => record.target.localName === "dialog")) adoptRegion();
    }).observe(document.documentElement, { subtree: true, attributes: true, attributeFilter: ["open"] });
  }
  App.toast.__adoptRegion = adoptRegion;
})();
