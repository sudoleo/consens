/* ==========================================================================
   token-budget.js — the one daily token account in the browser

   Compare, Consensus, Deep Think and Agent book on the same server-side
   account (app/services/agent_quota.py). Every response that knows the
   account carries the same `token_budget` snapshot: /usage, /user_status,
   /prepare, the final event of /ask_* and /consensus, /resolve, Agent's
   quota events and /agent/budget. This module is the only place that keeps
   it, orders concurrent snapshots and derives what the UI shows:

     - the percentage left ((limit − measured − estimated) / limit). Short
       reservations of running work change the tokens *available for new
       work*, never the percentage;
     - whether a pipeline run of a given mode can start (the same rule as the
       server's admission: available ≥ expected tokens of a typical run);
     - the approximate share one run of a mode takes.

   Loaded in the head group so firebase.js, the run modules, Agent and the
   sidebar can all feed and read it.
   ========================================================================== */
(function () {
  "use strict";

  window.App = window.App || {};

  var NUMBER_FIELDS = ["limit", "used", "reserved", "unknown", "estimated", "remaining", "revision", "config_revision"];
  var state = { budget: null, owner: null, stale: false };

  function currentUid() {
    try { return window.auth && window.auth.currentUser ? window.auth.currentUser.uid : null; }
    catch (_) { return null; }
  }

  function valid(budget) {
    if (!budget || typeof budget !== "object") return false;
    if (!Number.isSafeInteger(budget.limit) || budget.limit <= 0) return false;
    return NUMBER_FIELDS.every(function (key) {
      return budget[key] === undefined || (Number.isSafeInteger(budget[key]) && budget[key] >= 0);
    });
  }

  // Concurrent responses arrive out of order. A newer admin configuration
  // wins, then the newer UTC day, then the ledger revision of that day
  // (every reserve, settle, admission and booking increments it), and only
  // without revisions the server's observation time.
  function isOlder(next, previous) {
    if (!previous) return false;
    var nextConfig = next.config_revision || 0;
    var prevConfig = previous.config_revision || 0;
    if (nextConfig !== prevConfig) return nextConfig < prevConfig;
    if (next.day && previous.day && next.day !== previous.day) return next.day < previous.day;
    if (Number.isSafeInteger(next.revision) && Number.isSafeInteger(previous.revision)) {
      if (next.revision !== previous.revision) return next.revision < previous.revision;
    }
    if (Number.isFinite(next.observed_at) && Number.isFinite(previous.observed_at)) {
      return next.observed_at < previous.observed_at;
    }
    return false;
  }

  function notify() {
    try {
      window.dispatchEvent(new CustomEvent("consensio:token-budget", { detail: current() }));
    } catch (_) { /* old browsers: the sidebar still syncs directly */ }
    try { window.App.sidebarQuota && window.App.sidebarQuota.sync(); } catch (_) {}
  }

  /* Accept a snapshot. `uid` (when known) must be the signed-in account; a
     late answer of a previous login never paints the next one. Returns true
     when the snapshot became current. */
  function apply(budget, options) {
    var opts = options || {};
    var uid = currentUid();
    if (!uid || !valid(budget)) return false;
    if (opts.uid && opts.uid !== uid) return false;
    if (state.owner !== uid) {
      state.budget = null;
      state.owner = uid;
    }
    if (!opts.authoritative && isOlder(budget, state.budget)) return false;
    state.budget = Object.assign({}, budget);
    state.stale = false;
    notify();
    return true;
  }

  /* Any API payload: {token_budget}, a FastAPI {detail: {token_budget}} or
     an already unwrapped error detail. Payloads without the field change
     nothing (own-key runs, older servers). */
  function fromResponse(data, options) {
    if (!data || typeof data !== "object") return false;
    var budget = data.token_budget
      || (data.detail && typeof data.detail === "object" ? data.detail.token_budget : null);
    return budget ? apply(budget, options) : false;
  }

  function current() {
    if (!state.budget || state.owner !== currentUid()) return null;
    return state.stale ? Object.assign({}, state.budget, { stale: true }) : state.budget;
  }

  function markStale() {
    if (!state.budget) return;
    state.stale = true;
    notify();
  }

  function clear() {
    state.budget = null;
    state.owner = null;
    state.stale = false;
    notify();
  }

  // Next 00:00 UTC in the viewer's clock.
  function resetInfo(now) {
    var date = now ? new Date(now) : new Date();
    var next = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate() + 1));
    var ms = next - date;
    var hours = Math.floor(ms / 3600000);
    var minutes = Math.floor((ms % 3600000) / 60000);
    var clock;
    try { clock = next.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }); }
    catch (_) { clock = "00:00 UTC"; }
    return {
      clock: clock,
      relative: hours > 0 ? hours + " h " + minutes + " min" : Math.max(1, minutes) + " min",
      ms: ms
    };
  }

  function percentLabel(left, limit) {
    var percent = Math.max(0, Math.min(100, Math.floor(left / limit * 100)));
    // 2,300 of 660,000 is not "0 %": anything left reads "<1 %".
    return percent === 0 && left > 0 ? "<1%" : percent + "%";
  }

  /* Everything a surface needs, computed once. null = unknown. */
  function view(budget) {
    var b = budget === undefined ? current() : budget;
    if (!valid(b)) return null;
    var estimated = Number.isFinite(b.estimated) ? b.estimated : 0;
    var spent = Number.isFinite(b.used) ? b.used + estimated
      : b.limit - (b.remaining || 0) - (b.reserved || 0);
    var left = Math.max(0, b.limit - spent);
    var share = left / b.limit;
    return {
      limit: b.limit,
      spent: spent,
      left: left,
      share: share,
      percent: percentLabel(left, b.limit),
      available: Math.max(0, Number.isFinite(b.remaining) ? b.remaining : left),
      reserved: b.reserved || 0,
      estimated: estimated,
      state: left <= 0 ? "out" : share <= 0.25 ? "low" : "ok",
      estimates: b.run_estimates || null,
      stale: b.stale === true,
      reset: resetInfo()
    };
  }

  function modeKey(mode) {
    return mode === "deep_think" || mode === "compare" ? mode : "consensus";
  }

  function estimate(mode) {
    var b = current();
    var value = b && b.run_estimates ? b.run_estimates[modeKey(mode)] : null;
    return Number.isSafeInteger(value) && value > 0 ? value : null;
  }

  /* Same rule as the server's admission. null when the account is unknown
     (guest, still loading): then the server decides. */
  function canStart(mode) {
    var v = view();
    var need = estimate(mode);
    if (!v || need === null) return null;
    return v.available >= need;
  }

  /* "≈ 8%" for a typical run of this mode, or null. */
  function runShare(mode) {
    var b = current();
    var need = estimate(mode);
    if (!b || need === null) return null;
    var percent = need / b.limit * 100;
    return percent < 1 ? "<1%" : Math.round(percent) + "%";
  }

  function formatTokens(value) {
    var n = Math.max(0, Math.round(Number(value) || 0));
    if (n >= 10000000) return Math.round(n / 1000000) + "M";
    if (n >= 1000000) return String(Math.round(n / 100000) / 10) + "M";
    if (n >= 10000) return Math.round(n / 1000) + "k";
    if (n >= 1000) return (n / 1000).toFixed(1).replace(/\.0$/, "") + "k";
    return String(n);
  }

  window.App.tokenBudget = {
    apply: apply,
    fromResponse: fromResponse,
    current: current,
    markStale: markStale,
    clear: clear,
    view: view,
    estimate: estimate,
    canStart: canStart,
    runShare: runShare,
    resetInfo: resetInfo,
    formatTokens: formatTokens
  };
})();
