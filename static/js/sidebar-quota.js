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

  // sync() runs on every account update and on each tick of the reset
  // countdown. Writing a value that is already there still invalidates
  // style and layout, so every write below only happens on a change
  // (Apple audit D10).
  function setText(node, text) {
    if (node && node.textContent !== window.App.t(text)) node.textContent = text;
  }
  function setHidden(node, hidden) {
    if (node && node.hidden !== hidden) node.hidden = hidden;
  }
  function setAttr(node, name, value) {
    if (node && node.getAttribute(name) !== value) node.setAttribute(name, value);
  }

  function tokens() {
    return window.App && window.App.tokenBudget ? window.App.tokenBudget : null;
  }

  function fmt(value, unit) {
    var api = tokens();
    return api ? api.formatAmount(value, unit) : String(value);
  }

  // A part of the allowance as the reader sees it: "8%", never "<1" as 0.
  function shareOf(value, limit) {
    if (!(limit > 0)) return "Some";
    var percent = Math.round(value / limit * 100);
    return percent < 1 ? "Less than 1%" : percent + "%";
  }

  /* "Watches: 2 / 5" → {value: 2, limit: 5}; null while loading. */
  function parseWatches() {
    var strong = el("watchUsageDisplay") && el("watchUsageDisplay").querySelector("strong");
    var text = strong ? (strong.textContent || "").trim() : "";
    if (!text || text === "…" || text === "...") return null;
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
    var mode = "compare";
    try {
      var runMode = window.App.runMode;
      mode = runMode && runMode.effective ? runMode.effective() : mode;
    } catch (_) { /* default */ }
    if (mode === "agent") return "agent";
    // "deep_think" is the kept estimate key of a run with Reasoning on.
    var reasoning = el("reasoningToggle");
    if (reasoning && reasoning.checked) return "deep_think";
    return "compare";
  }

  var MODE_NAMES = { compare: "Compare run", deep_think: "Reasoning run" };

  function renderRing(view) {
    var trigger = el("quotaTrigger");
    var arc = el("quotaRingArc");
    if (!trigger) return;
    // Guests and a still-loading account have no number: no ring at all.
    if (!view) {
      setHidden(trigger, true);
      if (trigger.hasAttribute("data-state")) trigger.removeAttribute("data-state");
      return;
    }
    setHidden(trigger, false);
    setAttr(trigger, "data-state", view.state);
    if (arc) {
      setAttr(arc, "stroke-dashoffset", String((100 * (1 - view.share)).toFixed(2)));
      setAttr(arc, "stroke", STROKE[view.state] || STROKE.ok);
    }
    var label = view.percent + " of today’s allowance left · resets " + view.reset.clock;
    if (view.stale) label += " (last confirmed value)";
    setAttr(trigger, "title", label);
    setAttr(trigger, "aria-label", label);
  }

  function renderPanel(view) {
    var primary = el("quotaPrimary");
    setHidden(primary, !view);
    var detail = el("quotaDetail");
    var foot = el("quotaFoot");
    if (!view) {
      setHidden(detail, true);
      setText(detail, "");
      if (foot) {
        var signedIn = !!(window.auth && window.auth.currentUser);
        setText(foot, signedIn ? "Loading your allowance…" : "");
        setHidden(foot, !signedIn);
      }
      return;
    }

    setText(el("quotaPercent"), view.percent);
    var track = el("quotaTrack");
    if (track) {
      setAttr(track, "data-state", view.state);
      var fill = track.querySelector("i");
      var share = (view.share * 100).toFixed(1) + "%";
      if (fill && fill.style.getPropertyValue("--p") !== share) fill.style.setProperty("--p", share);
      setAttr(track, "aria-valuenow", String(Math.round(view.share * 100)));
    }
    setText(el("quotaReset"), "Resets at " + view.reset.clock + " · in " + view.reset.relative);

    if (detail) {
      // The reader's unit is the allowance in percent; the euro figures
      // are the operator's and stand in a line only an admin sees
      // (.admin-only, Apple-Audit H4).
      var mode = nextRunMode();
      var share = mode !== "agent" && tokens() ? tokens().runShare(mode) : null;
      var line = share ? "A " + MODE_NAMES[mode] + " uses about " + share + "."
        : mode === "agent" ? "Agent uses a little of it for each model it asks." : "";
      var unit = tokens() && tokens().current() ? tokens().current().unit : undefined;
      var figures = fmt(view.left, unit) + " of " + fmt(view.limit, unit);
      var admin = detail.querySelector(".admin-only");
      var words = detail.querySelector(".quota-detail-words");
      if (!admin || !words) {
        admin = document.createElement("span");
        admin.className = "admin-only";
        words = document.createElement("span");
        words.className = "quota-detail-words";
        detail.replaceChildren(admin, words);
      }
      setText(admin, line ? figures + " · " : figures);
      setText(words, line);
      // Without words of its own the line is the admin's figures alone.
      detail.classList.toggle("admin-only", !line);
      setHidden(detail, false);
    }

    if (foot) {
      var notes = [];
      if (view.reserved > 0) notes.push(shareOf(view.reserved, view.limit) + " is held for a message still running.");
      if (view.estimated > 0) notes.push(shareOf(view.estimated, view.limit) + " is an estimate until the exact use is known.");
      if (view.state === "out") notes.push("Compare and Agent share this allowance; it returns at the reset.");
      if (view.stale) notes.push("Last confirmed value; it refreshes when the connection is back.");
      setText(foot, notes.join(" "));
      setHidden(foot, notes.length === 0);
    }
  }

  function renderWatches() {
    var row = el("quotaRowWatch");
    var value = el("quotaWatchValue");
    var watches = parseWatches();
    if (!row) return;
    setHidden(row, !watches);
    if (watches) setText(value, watches.unlimited ? "Unlimited" : watches.value + " / " + watches.limit);
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
      setText(planLabel, "Free");
      setHidden(planLabel, tier !== "free");
    }
  }

  // The card is one of the app's popovers (App.popover): opening it closes
  // the account menu or any other, and it rises out of its ring.
  function setOpen(open) {
    var panel = el("sidebarQuota");
    var trigger = el("quotaTrigger");
    if (!panel) return;
    if (open) sync();
    var popover = window.App && window.App.popover;
    if (popover && open !== panel.classList.contains("is-open")) {
      if (open) popover.opened(panel, { trigger: trigger });
      else popover.closed(panel);
    }
    panel.classList.toggle("is-open", open);
    if (trigger) trigger.setAttribute("aria-expanded", String(open));
  }

  function init() {
    var trigger = el("quotaTrigger");
    var panel = el("sidebarQuota");
    if (!trigger || !panel) return;

    sync();
    if (window.App && window.App.popover) {
      window.App.popover.register(panel, { close: function () { setOpen(false); } });
    }

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
