// Saying so outside the tab: a run that ends, or waits for the reader, while
// consens.io is in the background shows a system notification. One in ten
// answers only starts after 45 s, and the run goes on on the server when
// the reader leaves; the tab title (tab-status.js) is easy to miss.
//
// Never asked for unprompted. The live line offers it once a run takes a
// while (agent-activity.js renders the offer), Settings has the switch.
// Only where a page may show one with `new Notification()`: desktop
// browsers. Android's Chrome wants a service worker for it, an iPhone or
// iPad allows it only to an app on the home screen, through one too; there
// is nothing to offer or switch (the iOS app brings push).
// The switch is this device's (localStorage): the permission belongs to the
// browser, not to the account. The states are tab-status.js's.
(function () {
  "use strict";
  const App = window.App = window.App || {};

  const PREF_KEY = "consensio.runNotify.v1";
  const OFFERS_KEY = "consensio.runNotify.offers.v1";
  // A run takes 20 to 60 s; after 20 s it is one worth leaving.
  const OFFER_AFTER_MS = 20000;
  // Runs that showed the offer without a click: then only Settings has it.
  const MAX_OFFERS = 3;
  const ICON = "/static/brand/icon-192.png";
  const TITLE_MAX_CHARS = 80;
  const BODY = Object.freeze({
    ready: "Your answer is ready.",
    asking: "The Agent is waiting for you.",
    paused: "Waiting for your decision.",
    failed: "The answer couldn’t be completed.",
  });
  const PERMISSION_NOTE = Object.freeze({
    granted: "Allowed in this browser.",
    default: "Your browser asks once when you switch it on.",
    denied: "Blocked in this browser’s site settings.",
  });

  let constructorRefused = false;

  function read(key) {
    try { return window.localStorage.getItem(key); } catch (_) { return null; }
  }
  function write(key, value) {
    try {
      if (value === null) window.localStorage.removeItem(key);
      else window.localStorage.setItem(key, value);
    } catch (_) { /* private mode: this page still remembers */ }
  }
  function track(name, data) { App.trackAppEvent?.(name, data); }

  function supported() {
    if (constructorRefused || !window.isSecureContext || typeof window.Notification !== "function"
      || typeof window.Notification.requestPermission !== "function") return false;
    const agent = navigator.userAgent || "";
    if (/Android|iPhone|iPad|iPod|Mobile/i.test(agent)) return false;
    // iPadOS names itself a Mac.
    return !(/Macintosh/.test(agent) && navigator.maxTouchPoints > 1);
  }
  function permission() {
    return supported() ? window.Notification.permission : "unsupported";
  }
  function enabled() {
    return permission() === "granted" && read(PREF_KEY) !== "off";
  }

  // ---- The offer in the live line --------------------------------------
  const offered = new Set();
  const declined = new Set();
  const confirmed = new Set();
  // What the live line of run `runId` shows after `elapsedMs`: "ask" (the
  // offer), "set" (it was taken during this run) or null.
  function offer(runId, elapsedMs) {
    if (!runId) return null;
    if (confirmed.has(runId)) return enabled() ? "set" : null;
    if (!(elapsedMs >= OFFER_AFTER_MS) || declined.has(runId)) return null;
    if (permission() !== "default" || read(PREF_KEY) === "off") return null;
    if (offered.has(runId)) return "ask";
    // Only an offer someone can see counts towards the three: a run started
    // and left at once gets it when its tab is back in front (backInFront).
    if (document.hidden) return null;
    const count = Number(read(OFFERS_KEY)) || 0;
    if (count >= MAX_OFFERS) return null;
    offered.add(runId);
    write(OFFERS_KEY, String(count + 1));
    return "ask";
  }

  // The browser's own question, only from a click (`source`: offer, settings).
  // The browser may have decided since the offer or switch was drawn, unnoticed
  // where it tells no change (Safari without permissions.query): its answer
  // stands then, and the switch and the live line catch up with it.
  async function ask(source, runId = "") {
    let result = permission();
    if (result === "default") {
      try {
        // Older Safari answers through a callback and returns nothing.
        result = await window.Notification.requestPermission();
      } catch (_) { /* answered below */ }
      result = window.Notification.permission || result;
    }
    if (result === "granted") {
      write(PREF_KEY, "on");
      if (runId) confirmed.add(runId);
    } else if (runId) declined.add(runId);
    track("app_run_notify", { source, result });
    changed();
    return result;
  }

  // ---- The notifications -------------------------------------------------
  const NEWS = new Set(["ready", "failed", "paused", "asking"]);
  const seen = new Map();
  const said = new Map();
  const shown = new Map();
  const woken = new Set();

  function temporary(run) {
    return run?.config?.temporary === true || run?.basis?.temporary === true;
  }
  function chatTitle(run) {
    const words = String(run?.bookmark?.title || run?.question || "").replace(/\s+/g, " ").trim();
    const letters = Array.from(words);
    return letters.length > TITLE_MAX_CHARS ? `${letters.slice(0, TITLE_MAX_CHARS - 1).join("").trim()}…` : words;
  }

  // The click brings the tab to the front with this chat, as its row in the
  // chat list would.
  function openRun(run) {
    const registry = App.runRegistry;
    const watching = document.body.classList.contains("is-watch-view");
    if (registry?.isVisible?.(run.runId) && !watching) return;
    if (run.bookmark?.id && (!temporary(run) || registry?.get?.(run.runId))) {
      window.openBookmark?.(run.bookmark.id);
    } else if (registry?.get?.(run.runId)) {
      App.watch?.leave?.();
      registry.show(run.runId);
    }
  }

  // The same run in two tabs of this browser (one chat opened twice) has
  // the same request identity there, not the same runId: one notification
  // for both, which the system replaces instead of showing twice.
  function identity(run) {
    return run.requestIdentity || run.runId;
  }

  // A hidden tab asks first whether a tab in front follows the same run;
  // then the reader sees it there. Same channel pattern as
  // temporary-chat.js: a tab answers only for itself.
  const PEER_WAIT_MS = 150;
  const peers = typeof window.BroadcastChannel === "function" ? new window.BroadcastChannel("consensio.runNotify") : null;
  peers?.addEventListener("message", event => {
    const ask = event.data || {};
    if (ask.type !== "who" || document.hidden) return;
    if ((App.runRegistry?.list?.() || []).some(run => identity(run) === ask.identity)) {
      peers.postMessage({ type: "followed", identity: ask.identity });
    }
  });
  function followedInFront(id) {
    if (!peers) return Promise.resolve(false);
    return new Promise(resolve => {
      const done = answer => {
        peers.removeEventListener("message", heard);
        clearTimeout(timer);
        resolve(answer);
      };
      const heard = event => { if (event.data?.type === "followed" && event.data.identity === id) done(true); };
      const timer = setTimeout(() => done(false), PEER_WAIT_MS);
      peers.addEventListener("message", heard);
      peers.postMessage({ type: "who", identity: id });
    });
  }

  function notify(run, state) {
    if (!peers) { show(run, state); return; }
    followedInFront(identity(run)).then(followed => {
      if (!followed && document.hidden && enabled()) show(run, state);
    });
  }

  function show(run, state) {
    // A temporary chat's title is its question: the notification only says
    // what happened.
    const title = temporary(run) ? App.t("Temporary chat") : chatTitle(run) || "consens.io";
    let note;
    try {
      // One per run (`tag`): what it says next replaces it instead of piling up.
      note = new window.Notification(title, { body: App.t(BODY[state]), tag: `consens-run-${identity(run)}`,
        icon: ICON, lang: App.lang || "en" });
    } catch (_) {
      // A browser that names the constructor but refuses it (Chrome on
      // Android in a desktop disguise): nothing to offer here after all.
      constructorRefused = true;
      changed();
      return;
    }
    shown.set(run.runId, note);
    note.onclick = () => {
      window.focus();
      openRun(run);
      note.close();
    };
    note.onclose = () => { if (shown.get(run.runId) === note) shown.delete(run.runId); };
  }

  // A run's state as tab-status.js names it. Said once when it becomes
  // ready, failed or waits for the reader, never again for the same end or
  // pause: the reviewers' marks arriving after the answer change nothing.
  // A state that was there before the page was hidden is no news.
  function observe() {
    const registry = App.runRegistry;
    const runs = registry?.list?.() || [];
    const ids = new Set();
    for (const run of runs) {
      ids.add(run.runId);
      const now = App.tabStatus?.state?.(run) || null;
      const was = seen.get(run.runId);
      seen.set(run.runId, now);
      if (now === "working" || now === "reviewing") wake(run);
      if (was === undefined || was === now || !NEWS.has(now) || !document.hidden || !enabled()) continue;
      const key = now === "paused" || now === "asking" ? `hold:${run.metadata?.hold?.id || ""}` : "end";
      const told = said.get(run.runId) || new Set();
      if (told.has(key)) continue;
      told.add(key);
      said.set(run.runId, told);
      notify(run, now);
    }
    for (const id of [...seen.keys()]) {
      if (!ids.has(id)) { seen.delete(id); said.delete(id); }
    }
  }

  // The live line draws only when the run reports something; a model that
  // thinks quietly past 20 s would leave the offer unshown. One redraw then.
  function wake(run) {
    if (woken.has(run.runId) || run.config?.executionMode !== "agent" || permission() !== "default") return;
    woken.add(run.runId);
    const left = OFFER_AFTER_MS - (Date.now() - (Number(run.startedAt) || Date.now()));
    window.setTimeout(() => {
      const registry = App.runRegistry;
      if (registry?.isExecuting?.(run.runId) && registry.isVisible?.(run.runId)) registry.update(run.runId, () => {});
    }, Math.max(0, left) + 50);
  }

  // Back in front: what the notifications said is on screen now, and the
  // live line draws the offer it held back while the tab was hidden.
  function backInFront() {
    if (document.hidden) return;
    shown.forEach(note => note.close());
    shown.clear();
    changed();
  }

  // ---- The switch in Settings --------------------------------------------
  function renderSwitch() {
    const row = document.getElementById("runNotifySetting");
    const input = document.getElementById("runNotifySwitch");
    const note = document.getElementById("runNotifyPermission");
    if (!row || !input) return;
    const state = permission();
    row.hidden = state === "unsupported";
    if (row.hidden) return;
    input.checked = enabled();
    input.disabled = state === "denied";
    if (note) note.textContent = PERMISSION_NOTE[state] || "";
  }

  // The live line of the run on screen and the switch say the new state.
  function changed() {
    renderSwitch();
    const run = App.runRegistry?.visible?.();
    if (run && App.runRegistry.isExecuting?.(run.runId)) App.runRegistry.update(run.runId, () => {});
  }

  async function switched(event) {
    const input = event.target;
    if (!input.checked) {
      write(PREF_KEY, "off");
      track("app_run_notify", { source: "settings", result: "off" });
      changed();
      return;
    }
    if (permission() === "granted") {
      write(PREF_KEY, "on");
      track("app_run_notify", { source: "settings", result: "granted" });
      changed();
      return;
    }
    input.disabled = true;
    await ask("settings");
  }

  function init() {
    document.getElementById("runNotifySwitch")?.addEventListener("change", switched);
    renderSwitch();
    // Changed in the browser's own site settings while the page is open.
    navigator.permissions?.query?.({ name: "notifications" }).then(status => {
      status.addEventListener?.("change", changed);
    }, () => {});
  }

  window.addEventListener("consensio:run-registry-change", observe);
  document.addEventListener("visibilitychange", backInFront);
  window.addEventListener("focus", renderSwitch);
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
  else init();

  App.runNotify = Object.freeze({ supported, permission, enabled, offer, ask });
})();
