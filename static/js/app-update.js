// App update: consens.io deploys several times a day, but an open app window
// (an installed desktop app, an iPhone home-screen app, a tab left open) never
// reloads on its own and kept the build it was opened with for days. The page
// knows its build (#appBootstrapConfig data-app-build) and asks /api/build
// which one is live: when it is left, when it comes back, and every 15 minutes
// while it is in front. A newer build is loaded only while nobody watches:
// while the page is hidden, never in front of the reader (a reload in the
// moment the page came back landed them somewhere else, Apple-Audit B7), and
// only while nothing would be lost: no run, no draft, no file, no open dialog,
// nothing unsaved on screen. A build learnt while the page is in front is
// loaded the moment it is left. The saved chat that was open is reopened
// afterwards at the very place the reader was (App.chatScroll.returnTo), with
// no ride. A page that stays in the background asks nothing more and never
// reloads again: every reload costs the account's start-up reads.
(function () {
  "use strict";
  const App = window.App = window.App || {};
  const own = document.getElementById("appBootstrapConfig")?.dataset.appBuild || "";
  const CHECK_EVERY_MS = 15 * 60 * 1000;
  const MIN_GAP_MS = 60 * 1000;
  // During a deploy the old instance may still answer the reload; try again later.
  const RETRY_AFTER_MS = 10 * 60 * 1000;
  const RESTORE_WITHIN_MS = 5 * 60 * 1000;
  const ATTEMPT_KEY = "consens.appUpdate.attempt";
  const RESTORE_KEY = "consens.appUpdate.restore";
  const BUILD = /^[0-9a-f]{7,40}$/;
  const TYPING = "textarea, input:not([type]), input[type=text], input[type=search], input[type=email], input[type=url], [contenteditable=true]";
  let live = "";
  let lastCheck = 0;
  let checking = null;

  function read(key) {
    try { return JSON.parse(sessionStorage.getItem(key) || "null"); } catch (_) { return null; }
  }
  function write(key, value) {
    try {
      if (value === null) sessionStorage.removeItem(key);
      else sessionStorage.setItem(key, JSON.stringify(value));
    } catch (_) { /* storage unavailable: no loop guard, no reopen */ }
  }

  function dialogOpen() {
    // The docked answer reader is a side panel, not a dialog in the way.
    if (document.querySelector("dialog[open]:not(.is-docked)")) return true;
    return Array.from(document.querySelectorAll(".modal:not(dialog)"))
      .some(modal => window.getComputedStyle(modal).display !== "none");
  }

  // What the reload has to bring back: the watch page or the empty start
  // (the address and the template do that), a saved chat -- or null when the
  // screen shows something that exists nowhere else (a guest's result, a run
  // that is not saved yet).
  function view() {
    if (document.getElementById("watchDashboard")?.hidden === false) return { bookmarkId: "" };
    const registry = App.runRegistry;
    const run = registry?.visible?.();
    if (run && run.status !== "succeeded") return null;
    const bookmarkId = registry?.getSelectedConversationIdentity?.()?.bookmarkId || "";
    if (bookmarkId) return { bookmarkId };
    if (!run && document.body.classList.contains("is-hero")) return { bookmarkId: "" };
    return null;
  }

  function idle() {
    const registry = App.runRegistry;
    if (!registry || registry.activeCount() > 0) return false;
    if ((window.pendingAttachments || []).length || App.attachments?.isImporting?.()) return false;
    if (App.quote?.has?.()) return false;
    if (String(document.getElementById("questionInput")?.value || "").trim()) return false;
    const active = document.activeElement;
    if (active?.matches?.(TYPING) && String(active.value ?? active.textContent ?? "").trim()) return false;
    if (dialogOpen()) return false;
    return view() !== null;
  }

  // Where the reader is in the open chat: the turn at the top of the screen
  // and how far it stands from it, plus the plain scroll offset.
  function readingPlace() {
    const turns = document.querySelectorAll(".container [data-turn-key]");
    const top = document.querySelector(".app-mobile-header")?.getBoundingClientRect().bottom || 0;
    for (const turn of turns) {
      if (!turn.getClientRects().length) continue;
      const rect = turn.getBoundingClientRect();
      if (rect.bottom > top) return { key: turn.dataset.turnKey, offset: Math.round(rect.top), y: Math.round(window.scrollY) };
    }
    return { y: Math.round(window.scrollY) };
  }

  function apply() {
    if (!live || !document.hidden || !idle()) return false;
    const attempt = read(ATTEMPT_KEY);
    if (attempt?.build === live && Date.now() - Number(attempt.at || 0) < RETRY_AFTER_MS) return false;
    write(ATTEMPT_KEY, { build: live, at: Date.now() });
    const uid = App.authState?.uid || null;
    const { bookmarkId } = view();
    write(RESTORE_KEY, { from: own, at: Date.now(), uid, bookmarkId: uid ? bookmarkId : "",
      place: uid && bookmarkId ? readingPlace() : null });
    window.location.reload();
    return true;
  }

  function check({ force = false } = {}) {
    if (!own) return Promise.resolve(false);
    if (checking) return checking;
    if (!force && Date.now() - lastCheck < MIN_GAP_MS) return Promise.resolve(apply());
    lastCheck = Date.now();
    checking = fetch("/api/build", { cache: "no-store", headers: { Accept: "application/json" } })
      .then(response => (response.ok ? response.json() : null))
      .then(data => {
        const build = String(data?.build || "");
        if (BUILD.test(build)) live = build === own ? "" : build;
      })
      .catch(() => { /* offline or mid-deploy: the next look asks again */ })
      .then(() => {
        checking = null;
        return apply();
      });
    return checking;
  }

  function placeTop(place) {
    const key = typeof place?.key === "string" ? place.key : "";
    const turn = key ? [...document.querySelectorAll(".container [data-turn-key]")].find(node => node.dataset.turnKey === key) : null;
    if (turn?.getClientRects().length && Number.isFinite(place.offset)) {
      return window.scrollY + turn.getBoundingClientRect().top - place.offset;
    }
    return Number.isFinite(place?.y) ? place.y : null;
  }

  // After an update: reopen the saved chat once its account is signed in
  // again, unless the user has already moved on.
  function restore() {
    const record = read(RESTORE_KEY);
    write(RESTORE_KEY, null);
    if (!record || Date.now() - Number(record.at || 0) > RESTORE_WITHIN_MS) return;
    if (record.from && record.from !== own) {
      // Umami loads async; the load event waits for it.
      const track = () => App.trackAppEvent?.("app_updated", { reopened: !!record.bookmarkId });
      if (document.readyState === "complete") track();
      else window.addEventListener("load", track, { once: true });
    }
    if (!record.bookmarkId || !record.uid) return;
    let pending = true;
    const finish = () => {
      pending = false;
      window.removeEventListener("consensio:auth-state", onAuth);
    };
    function onAuth(event) {
      const state = event.detail;
      if (!pending || !state?.known) return;
      finish();
      const untouchedStart = document.body.classList.contains("is-hero")
        && !App.runRegistry?.visible?.()
        && !App.runRegistry?.getSelectedConversationIdentity?.()
        && !String(document.getElementById("questionInput")?.value || "").trim();
      if (state.uid !== record.uid || !untouchedStart) return;
      // The chat opens where the reader left it, held there while its late
      // layout settles, instead of at its newest question.
      if (record.place) App.chatScroll?.returnTo?.(() => placeTop(record.place));
      window.openBookmark?.(record.bookmarkId);
    }
    window.addEventListener("consensio:auth-state", onAuth);
    // The Firebase module may publish a restored sign-in before this deferred
    // bundle has even run (the module was ready, the app bundle still
    // loading); that event has gone by unheard. Pick up the known state once
    // the page has loaded and the app is initialised.
    const catchUp = () => {
      const state = window.__consensioAuthState;
      if (pending && state?.known) onAuth({ detail: state });
    };
    if (document.readyState === "complete") setTimeout(catchUp, 0);
    else window.addEventListener("load", () => setTimeout(catchUp, 0), { once: true });
    setTimeout(() => { if (pending) finish(); }, 30000);
  }

  // Leaving: a build already known loads at once (a phone may freeze the
  // hidden page before a request returns); otherwise it is asked for now.
  // Coming back only asks, for the next time the page is left.
  document.addEventListener("visibilitychange", () => {
    if (document.hidden && apply()) return;
    check();
  });
  window.addEventListener("pageshow", event => {
    if (event.persisted) check({ force: true });
  });
  window.addEventListener("online", () => { if (!document.hidden) check(); });
  if (own) setInterval(() => { if (!document.hidden) check(); }, CHECK_EVERY_MS);
  restore();

  App.appUpdate = Object.freeze({ check, idle, build: own });
})();
