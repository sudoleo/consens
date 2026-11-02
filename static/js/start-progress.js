// A start the user waits for, the Apple way (since 2026-11-02, Max after a
// colleague's first try: "every normal user is gone then"): a thin bar that
// fills toward the server's estimate and a line with the time left ("About
// 40 seconds left"), instead of one word for a wait of unknown length. The
// server says until when a start of the workspace should run
// (agent_workspace.START_SECONDS, measured in Prod; ``starting_until`` on a
// step, ``until`` in the live view); the chat's step (agent-activity.js)
// and the live view (workspace-view.js) show it.
//
// The bar never runs backwards and never fills before the start is done: it
// moves evenly to 90% at the estimate, then creeps on toward 98% while the
// line says "Almost done…". A later estimate goes on from where the bar
// stands. It shows only once a start took SHOW_MS, so a quick one never
// flashes a bar. done() fills it.
//
// App.startProgress.create() → { node, set(until), done(), stop() }; set
// takes an ISO time or epoch milliseconds, the node shows itself.
(function () {
  'use strict';
  const App = window.App = window.App || {};
  // One step of the bar per tick, as long as its transition (foundation.css --dur-state).
  const TICK_MS = 200;
  const SHOW_MS = 1200;
  const DONE_MS = 400;
  const AT_ESTIMATE = 0.9, CEILING = 0.98;

  // What is left, in whole sentences (docs/i18n.md: never words in a ${…}).
  function leftText(ms) {
    if (ms > 90_000) return App.t('About {count} minutes left', { count: Math.round(ms / 60_000) });
    if (ms > 50_000) return App.t('About a minute left');
    if (ms >= 10_000) return App.t('About {count} seconds left', { count: Math.round(ms / 5_000) * 5 });
    return App.t('Almost done…');
  }

  function create() {
    const node = document.createElement('div');
    node.className = 'start-progress';
    node.hidden = true;
    node.setAttribute('role', 'progressbar');
    node.setAttribute('aria-valuemin', '0');
    node.setAttribute('aria-valuemax', '100');
    // Its words are App.t's already (the page translates nothing twice).
    node.dataset.i18nSkip = '';
    const track = document.createElement('span');
    track.className = 'start-progress-track';
    const fill = document.createElement('span');
    fill.className = 'start-progress-fill';
    track.append(fill);
    const left = document.createElement('span');
    left.className = 'start-progress-left';
    node.append(track, left);

    const began = Date.now();
    // The bar's way: from ``from`` at ``since`` to AT_ESTIMATE at ``until``.
    let from = 0, since = began, until = 0, value = 0, timer = null, finished = false;
    function at(now) {
      if (!until) return value;
      const x = (now - since) / Math.max(1000, until - since);
      if (from < AT_ESTIMATE && x <= 1) return from + (AT_ESTIMATE - from) * x;
      const base = Math.max(from, AT_ESTIMATE), over = Math.max(0, now - Math.max(until, since));
      return base + (CEILING - base) * (1 - Math.exp(-over / 20_000));
    }
    function draw() {
      const now = Date.now();
      if (!finished) value = Math.max(value, Math.min(CEILING, at(now)));
      if (node.hidden && (finished || !until || now - began < SHOW_MS)) return;
      node.hidden = false;
      fill.style.transform = `scaleX(${value.toFixed(4)})`;
      const text = finished ? '' : leftText(until - now);
      if (left.textContent !== text) left.textContent = text;
      const percent = String(Math.round(value * 100));
      if (node.getAttribute('aria-valuenow') !== percent) node.setAttribute('aria-valuenow', percent);
      if (node.getAttribute('aria-valuetext') !== text && text) node.setAttribute('aria-valuetext', text);
    }
    function tick() {
      // A node taken out of the page stops counting.
      if (began + SHOW_MS < Date.now() && !node.isConnected) { stop(); return; }
      draw();
    }
    function set(time) {
      const next = typeof time === 'number' ? time : Date.parse(time);
      if (!Number.isFinite(next) || finished) return;
      if (next === until) return;
      const now = Date.now();
      from = Math.max(value, at(now));
      since = now;
      until = next;
      if (!timer) timer = setInterval(tick, TICK_MS);
      draw();
    }
    function done() {
      if (finished) return;
      finished = true;
      value = 1;
      draw();
      stop();
      // Full for a moment, then gone (a shown bar only).
      if (!node.hidden) setTimeout(() => { node.hidden = true; }, DONE_MS);
    }
    function stop() {
      clearInterval(timer);
      timer = null;
    }
    return { node, set, done, stop, get value() { return value; } };
  }

  App.startProgress = { create, leftText };
})();
