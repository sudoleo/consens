/* ==========================================================================
   Sidebar quota: the ring in the account footer and the panel above it.

   Both are a view of one number: today's token account, shared by Compare,
   Consensus, Reasoning runs and Agent (App.tokenBudget, token-budget.js). The
   ring is a quiet 20 px glyph without text — a number inside a ring that
   small either overflows or is unreadable. The exact value lives in the
   ring's tooltip/aria-label and in the panel: one primary figure, a thin
   bar, the reset time and one secondary line. Semantic colour sits only on
   the ring's arc and the bar's fill when the account runs low, never on a
   surface behind them.

   Watches keep their own allowance (watch.js writes #watchUsageDisplay);
   the panel shows it as a separate, smaller line.
   ========================================================================== */
(function () {
  "use strict";

  var STROKE = { ok: "var(--ink-2)", low: "var(--partial)", out: "var(--dispute)" };

  function el(id) {
    return document.getElementById(id);
  }

  function tokens() {
    return window.App && window.App.tokenBudget ? window.App.tokenBudget : null;
  }

  function fmt(value) {
    var api = tokens();
    return api ? api.formatTokens(value) : String(value);
  }

  /* "Watches: 2 / 5" → {value: 2, limit: 5}; null while loading. */
  function parseWatches() {
    var strong = el("watchUsageDisplay") && el("watchUsageDisplay").querySelector("strong");
    var text = strong ? (strong.textContent || "").trim() : "";
    if (!text || text === "...") return null;
    if (/unlimited/i.test(text)) return { unlimited: true };
    var parts = text.split("/");
    if (parts.length !== 2) return null;
    var value = Number(parts[0].trim());
    var limit = Number(parts[1].trim());
    if (!Number.isFinite(value) || !Number.isFinite(limit) || limit <= 0) return null;
    return { value: value, limit: limit };
  }

  // The mode the next message will run in, for the "one run ≈ x %" hint.
  function nextRunMode() {
    var mode = "consensus";
    try {
      var runMode = window.App.runMode;
      mode = runMode && runMode.effective ? runMode.effective() : mode;
    } catch (_) { /* default */ }
    if (mode === "agent") return "agent";
    // "deep_think" is the kept estimate key of a run with Reasoning on.
    var reasoning = el("reasoningToggle");
    if (reasoning && reasoning.checked) return "deep_think";
    return mode === "compare" ? "compare" : "consensus";
  }

  var MODE_NAMES = { compare: "Compare run", consensus: "Consensus run", deep_think: "Reasoning run" };

  function renderRing(view) {
    var trigger = el("quotaTrigger");
    var arc = el("quotaRingArc");
    if (!trigger) return;
    // Guests and a still-loading account have no number: no ring at all.
    if (!view) {
      trigger.hidden = true;
      trigger.removeAttribute("data-state");
      return;
    }
    trigger.hidden = false;
    trigger.dataset.state = view.state;
    if (arc) {
      arc.setAttribute("stroke-dashoffset", String((100 * (1 - view.share)).toFixed(2)));
      arc.setAttribute("stroke", STROKE[view.state] || STROKE.ok);
    }
    var label = view.percent + " of today’s allowance left · resets " + view.reset.clock;
    if (view.stale) label += " (last confirmed value)";
    trigger.title = label;
    trigger.setAttribute("aria-label", label);
  }

  function renderPanel(view) {
    var primary = el("quotaPrimary");
    if (primary) primary.hidden = !view;
    var detail = el("quotaDetail");
    var foot = el("quotaFoot");
    if (!view) {
      if (detail) { detail.hidden = true; detail.textContent = ""; }
      if (foot) {
        var signedIn = !!(window.auth && window.auth.currentUser);
        foot.textContent = signedIn ? "Loading your allowance…" : "";
        foot.hidden = !signedIn;
      }
      return;
    }

    if (el("quotaPercent")) el("quotaPercent").textContent = view.percent;
    var track = el("quotaTrack");
    if (track) {
      track.dataset.state = view.state;
      var fill = track.querySelector("i");
      if (fill) fill.style.setProperty("--p", (view.share * 100).toFixed(1) + "%");
      track.setAttribute("aria-valuenow", String(Math.round(view.share * 100)));
    }
    if (el("quotaReset")) {
      el("quotaReset").textContent = "Resets at " + view.reset.clock + " · in " + view.reset.relative;
    }

    if (detail) {
      var line = fmt(view.left) + " of " + fmt(view.limit) + " tokens";
      var mode = nextRunMode();
      var share = mode !== "agent" && tokens() ? tokens().runShare(mode) : null;
      if (share) line += " · a " + MODE_NAMES[mode] + " uses about " + share;
      else if (mode === "agent") line += " · Agent books each model call";
      detail.textContent = line;
      detail.hidden = false;
    }

    if (foot) {
      var notes = [];
      if (view.reserved > 0) notes.push(fmt(view.reserved) + " held for work in progress.");
      if (view.estimated > 0) notes.push(fmt(view.estimated) + " estimated until the provider reports the exact usage.");
      if (view.state === "out") notes.push("Compare, Consensus and Agent share this allowance; it returns at the reset.");
      if (view.stale) notes.push("Last confirmed value; it refreshes when the connection is back.");
      foot.textContent = notes.join(" ");
      foot.hidden = notes.length === 0;
    }
  }

  function renderWatches() {
    var row = el("quotaRowWatch");
    var value = el("quotaWatchValue");
    var watches = parseWatches();
    if (!row) return;
    row.hidden = !watches;
    if (watches && value) value.textContent = watches.unlimited ? "Unlimited" : watches.value + " / " + watches.limit;
  }

  function sync() {
    var api = tokens();
    var view = api ? api.view() : null;
    renderRing(view);
    renderPanel(view);
    renderWatches();

    // Der Plan steht im Kopf des Panels. Pro und Plus sprechen ueber das
    // Badge daneben (user-tier.js), nur Free braucht das Textlabel.
    var planLabel = el("quotaPlanLabel");
    if (planLabel) {
      var tier = window.userTier || "free";
      planLabel.textContent = "Free";
      planLabel.hidden = tier !== "free";
    }
  }

  function setOpen(open) {
    var panel = el("sidebarQuota");
    var trigger = el("quotaTrigger");
    if (!panel) return;
    if (open) sync();
    panel.classList.toggle("is-open", open);
    if (trigger) trigger.setAttribute("aria-expanded", String(open));
  }

  function init() {
    var trigger = el("quotaTrigger");
    var panel = el("sidebarQuota");
    if (!trigger || !panel) return;

    sync();

    // Watches still arrive through the hidden #usageDisplay column.
    var source = el("usageDisplay");
    if (source) {
      new MutationObserver(sync).observe(source, { childList: true, subtree: true, characterData: true });
    }
    window.addEventListener("consensio:token-budget", sync);
    // The run hint follows the mode and Reasoning switches.
    window.addEventListener("consensio:run-mode-change", sync);
    document.addEventListener("change", function (event) {
      if (event.target && event.target.id === "reasoningToggle") sync();
    });

    trigger.addEventListener("click", function (event) {
      event.stopPropagation();
      setOpen(!panel.classList.contains("is-open"));
    });

    document.addEventListener("click", function (event) {
      if (!panel.classList.contains("is-open")) return;
      if (panel.contains(event.target) || trigger.contains(event.target)) return;
      setOpen(false);
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && panel.classList.contains("is-open")) {
        setOpen(false);
        trigger.focus();
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }

  window.App = window.App || {};
  window.App.sidebarQuota = { sync: sync, setOpen: setOpen };
})();
