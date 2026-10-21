// Watch dashboard (/app/watches). Classic script; renders into #watchDashBody.
// Contract: window.App.watchDashboard.{render, refresh, cardState, renderGuest,
// renderSkeleton, focusWatch, addCreated, showUndoToast, commitPending, reset}.
// Helpers shared with the create dialog come from window.App.watchUi
// (watch.js) and window.App.watchFields (watch-fields.js). What a check
// means is decided once on the server (drift_signal, docs/watch-evidence-
// model.md) and arrives as `signal`; this file only presents it.
//
// The page is built once per visit and then changed card by card (D6): an
// action updates its own card from the server's answer, an open settings
// panel stays open, the focus stays where it was, and a card keeps its place
// until the next visit sorts it (J14).
(function () {
  const ui = () => window.App.watchUi;
  const F = () => window.App.watchFields;
  const watchState = window.App.watchState;
  const EXPLAINER_STORAGE_KEY = "consensio.watchExplainer.open.v1";
  const RECENT_MS = 7 * 24 * 3600 * 1000;
  const UNDO_MS = 6000;
  const REFRESH_STEPS_MS = [60 * 1000, 2 * 60 * 1000, 5 * 60 * 1000, 10 * 60 * 1000];

  // This visit of the page.
  const page = {
    cards: new Map(),      // watch id -> card entry
    sections: new Map(),   // section key -> { section, list, count }
    fresh: new Set(),      // watches created during this session: on top
    pendingDeletes: new Map(),
    telegram: null,
    brief: {},
    built: false,
    signature: "",
    lastLoad: 0,
    refreshTimer: null,
    refreshStep: 0
  };

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function reducedMotion() {
    return ui()?.reducedMotion?.() === true;
  }

  function hostOf(url) {
    try { return new URL(url).hostname.replace(/^www\./, ""); } catch (_) { return ""; }
  }

  function separator() {
    const dot = el("span", "wd-sep", "·");
    dot.setAttribute("aria-hidden", "true");
    return dot;
  }

  // A failed change in plain words (App.userError): the server's sentence,
  // or what happened; a full plan is a 429 without "rate_limited".
  function errorText(error, fallback = "That didn’t work. Try again.") {
    if (!error) return fallback;
    if (error.status === 429 && error.code !== "rate_limited") return "All slots are in use. Pause another watch first.";
    return window.App.userError(error, { fallback });
  }

  // ------------------------------------------------------------------
  // Times that stay true while the page is open (J5): every time on the
  // page is written by a function and re-read every half minute.
  // ------------------------------------------------------------------
  const liveNodes = new Map();
  let ticker = null;

  function liveText(node, compute) {
    liveNodes.set(node, compute);
    node.textContent = compute(Date.now());
    ensureTicker();
    return node;
  }

  function tick() {
    const view = document.getElementById("watchDashboard");
    if (!view || view.hidden) return;
    const now = Date.now();
    let due = false;
    liveNodes.forEach((compute, node) => {
      if (!node.isConnected) {
        liveNodes.delete(node);
        return;
      }
      const text = compute(now);
      if (node.textContent !== text) node.textContent = text;
    });
    page.cards.forEach(entry => {
      const state = F().nextCheck(entry.watch, now).state;
      if (entry.watch.status === "active" && (state === "due" || state === "checking")) due = true;
    });
    if (due && !page.refreshTimer) planRefresh(true);
  }

  function ensureTicker() {
    if (ticker) return;
    ticker = setInterval(tick, 30 * 1000);
  }

  // A check that is due or running reports back within minutes: the page
  // asks again a few times with growing pauses instead of polling forever
  // (every request reads the account's watches).
  function planRefresh(force) {
    clearTimeout(page.refreshTimer);
    page.refreshTimer = null;
    const now = Date.now();
    const waiting = [...page.cards.values()].some(entry => {
      const state = F().nextCheck(entry.watch, now).state;
      return entry.watch.status === "active" && (state === "due" || state === "checking");
    });
    if (!waiting && !force) {
      page.refreshStep = 0;
      return;
    }
    if (page.refreshStep >= REFRESH_STEPS_MS.length) return;
    const delay = REFRESH_STEPS_MS[page.refreshStep];
    page.refreshStep += 1;
    page.refreshTimer = setTimeout(() => {
      page.refreshTimer = null;
      refresh().catch(() => {});
    }, delay);
  }

  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") {
      commitPending();
      return;
    }
    const view = document.getElementById("watchDashboard");
    if (!view || view.hidden || !page.built || !window.auth?.currentUser) return;
    tick();
    if (Date.now() - page.lastLoad > 60 * 1000) refresh().catch(() => {});
  });
  window.addEventListener("pagehide", () => commitPending());

  // ------------------------------------------------------------------
  // What a watch's state means to its owner.
  // ------------------------------------------------------------------

  function latestPoint(watch) {
    const history = Array.isArray(watch.history) ? watch.history : [];
    return history.length ? history[history.length - 1] : null;
  }

  function lastMove(watch) {
    const history = Array.isArray(watch.history) ? watch.history : [];
    return [...history].reverse().find(point => point.trigger === "changed") || null;
  }

  function steadyChecks(watch) {
    const history = Array.isArray(watch.history) ? watch.history : [];
    let count = 0;
    for (let index = history.length - 1; index >= 0; index -= 1) {
      if (history[index].trigger === "changed") break;
      count += 1;
    }
    return count;
  }

  // One reading per card: tone (colour), label, the sentence under the
  // question and the sources that carry it.
  function cardState(watch) {
    const point = latestPoint(watch);
    if (watch.status === "resolved") {
      const resolution = watch.resolution || {};
      return {
        key: "resolved", tone: "resolved", label: "Reached",
        when: resolution.at || watch.last_run_at,
        headline: resolution.reason || "What this watch was waiting for has happened.",
        sources: resolution.sources || []
      };
    }
    if (watch.status === "paused_error") {
      return {
        key: "paused", tone: "error", label: "Paused after errors",
        when: watch.last_run_at,
        headline: "Three checks in a row could not complete. Resume to try again; the history is kept.",
        sources: []
      };
    }
    if (watch.status !== "active") {
      return {
        key: "paused", tone: "paused", label: "Paused", when: watch.last_run_at,
        headline: "No checks run while paused. Resume to continue the same record.",
        sources: []
      };
    }
    if (!point || watch.awaiting_first_run) {
      return {
        key: "waiting", tone: "waiting", label: "First check pending",
        when: watch.next_run_at,
        headline: "The first check sets the baseline: what the models agree on today, with sources.",
        sources: []
      };
    }
    if (point.signal === "confirming") {
      return {
        key: "rechecking", tone: "rechecking", label: "Re-checking",
        when: point.ts,
        headline: "A different reading came up. A second check runs within the hour before it counts.",
        sources: []
      };
    }
    if (point.signal === "held") {
      return {
        key: "held", tone: "held", label: "Answer stands",
        when: point.ts,
        headline: "The sources behind the answer did not come up in this check, and nothing contradicted them.",
        sources: []
      };
    }
    if (point.trigger === "changed") {
      return {
        key: "moved", tone: "moved", label: "Moved",
        when: point.ts,
        headline: point.change_summary || "The answer moved on new evidence.",
        sources: point.evidence_sources || [],
        held: point.held_summary || ""
      };
    }
    const move = lastMove(watch);
    const steady = steadyChecks(watch);
    return {
      key: "watching", tone: "watching", label: "Watching",
      when: point.ts,
      headline: move
        ? `Last moved ${F().shortDay(move.ts)}: ${move.change_summary || "the answer changed on evidence."}`
        : (steady > 1 ? `The answer has held through ${steady} checks.` : "The answer has held since the first check."),
      sources: []
    };
  }

  // The server says where the goal stands (watch_service.goal_state): a check
  // that looked but found no answer is "unclear", not "not checked".
  const GOAL_STATES = {
    reached: { status: "Reached", tone: "reached" },
    confirming: { status: "Reported, confirming", tone: "reported" },
    not_met: { status: "Not yet", tone: "open" },
    unclear: { status: "No clear answer yet", tone: "open" },
    pending: { status: "Not checked yet", tone: "open" }
  };

  function goalLine(watch) {
    const goal = String(watch.condition || "").trim();
    if (!goal) return null;
    let state = GOAL_STATES[watch.goal_state];
    if (!state) {
      state = watch.status === "resolved" ? GOAL_STATES.reached
        : watch.last_condition_status === "met" ? GOAL_STATES.confirming
          : watch.last_condition_status ? GOAL_STATES.not_met : GOAL_STATES.pending;
    }
    return { goal: goal, status: state.status, tone: state.tone };
  }

  const SIGNAL_LABELS = {
    moved: "Moved on evidence",
    confirming: "Re-checking a different reading",
    preliminary: "First seen; confirmed by the next check",
    reverted: "Set aside: a re-check did not repeat it",
    held: "Answer stood; sources did not come up",
    restated: "Same answer, new wording",
    stable: "No change"
  };

  // From three checks on the strip has a shape worth reading; one or two
  // lone ticks only looked like a rendering glitch, and the sentence above
  // already says how many checks held. What the strokes mean is written next
  // to them, not only in a mouse tooltip (J26).
  const RECORD_MIN_CHECKS = 3;

  function buildRecord(watch) {
    const history = (Array.isArray(watch.history) ? watch.history : []).slice(-16);
    if (history.length < RECORD_MIN_CHECKS) return null;
    const wrap = el("div", "wd-record-row");
    const strip = el("div", "wd-record");
    const moved = history.filter(point => point.signal === "moved").length;
    const held = history.filter(point => point.signal === "held").length;
    strip.setAttribute("aria-hidden", "true");
    history.forEach((point, index) => {
      const tick = el("span", "wd-tick is-" + (point.signal || (point.trigger === "changed" ? "moved" : "stable")));
      if (index === history.length - 1 && watch.status === "resolved") tick.classList.add("is-resolved");
      tick.title = `${F().shortDay(point.ts)} · ${SIGNAL_LABELS[point.signal] || "Checked"}`;
      strip.appendChild(tick);
    });
    const parts = [`Last ${history.length} checks`];
    if (moved) parts.push(`${moved} moved`);
    if (held) parts.push(`${held} held without sources`);
    wrap.append(strip, el("span", "wd-record-caption", parts.join(" · ")));
    return wrap;
  }

  // Up to three links straight to the pages: the evidence of a move, else
  // the watch's direct links (services/source_links.py: the pages its answer
  // names, deep pages with a real title). Favicons come through our own proxy.
  function buildSources(sources) {
    const items = (sources || []).filter(item => item && /^https?:\/\//.test(item.url || "")).slice(0, 3);
    if (!items.length) return null;
    const list = el("ul", "wd-sources");
    items.forEach(item => {
      const li = el("li");
      const link = el("a");
      link.href = item.url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      const host = item.domain || hostOf(item.url);
      if (host) {
        const icon = el("img", "wd-source-icon");
        icon.src = "/api/topics/favicon?d=" + encodeURIComponent(host);
        icon.alt = "";
        icon.width = 14;
        icon.height = 14;
        icon.loading = "lazy";
        icon.addEventListener("error", () => icon.classList.add("is-missing"));
        link.appendChild(icon);
      }
      link.appendChild(el("span", "wd-source-host", host));
      const title = item.title && item.title !== host ? item.title : "";
      if (title) link.appendChild(el("span", "wd-source-title", title));
      link.title = (title ? title + " · " : "") + host;
      li.appendChild(link);
      list.appendChild(li);
    });
    return list;
  }

  // What the watch is about, so it is recognised at a glance:
  // services/watch_images.py picks a product shot, an article photo or the
  // logos of the sites the question is about; we only show it. Without one,
  // the card shows the watch's symbol (services/watch_symbols.py, picked once
  // by the cheap Judge) instead. The picture leads to the watch's own page,
  // like the question beside it; removing it lives in Settings (J23).
  const IMAGE_PATH = /^\/api\/watch\/[A-Za-z0-9]+\/image\/[0-9a-f]{20}$/;
  const IMAGE_KINDS = ["item", "article", "logo"];

  // 24px line drawings, one per name in watch_symbols.SYMBOLS (a test keeps
  // both lists equal). Strokes take the text colour, so they follow the theme.
  const SYMBOL_ICONS = {
    briefcase: '<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M9 7V5.5A1.5 1.5 0 0 1 10.5 4h3A1.5 1.5 0 0 1 15 5.5V7M3 12.5h18"/>',
    graduation: '<path d="M2 9l10-5 10 5-10 5z"/><path d="M6 11v4.5c0 1.5 2.7 3 6 3s6-1.5 6-3V11M22 9v5"/>',
    trophy: '<path d="M7 4h10v5a5 5 0 0 1-10 0z"/><path d="M7 5.5H4v1A3.5 3.5 0 0 0 7.5 10M17 5.5h3v1a3.5 3.5 0 0 1-3.5 3.5M12 14v3.5M8 20.5h8M9.5 17.5h5"/>',
    heart: '<path d="M12 20.5l-7.4-7.3a4.6 4.6 0 0 1 6.5-6.5l.9.9.9-.9a4.6 4.6 0 0 1 6.5 6.5z"/>',
    pulse: '<path d="M3 12h4l2.5-6 4 12 2.5-6H21"/>',
    flask: '<path d="M9 3h6M10 3v6.2l-5.2 9.1A1.8 1.8 0 0 0 6.4 21h11.2a1.8 1.8 0 0 0 1.6-2.7L14 9.2V3M7.3 15h9.4"/>',
    sigma: '<path d="M17.5 5H6.5l6.5 7-6.5 7h11"/>',
    chip: '<rect x="7" y="7" width="10" height="10" rx="1.5"/><rect x="10" y="10" width="4" height="4"/><path d="M10 4v3M14 4v3M10 17v3M14 17v3M4 10h3M4 14h3M17 10h3M17 14h3"/>',
    phone: '<rect x="7" y="2.5" width="10" height="19" rx="2.2"/><path d="M11 18.5h2"/>',
    code: '<path d="M8.5 7l-5 5 5 5M15.5 7l5 5-5 5M13.5 5l-3 14"/>',
    sparkle: '<path d="M11 5Q12 12 19 13Q12 14 11 21Q10 14 3 13Q10 12 11 5z"/><path d="M18.5 3v4M16.5 5h4"/>',
    scale: '<path d="M12 4v16M8 20.5h8M5 7h14M2.5 13L5 7l2.5 6M16.5 13L19 7l2.5 6M2.5 13a2.5 2.5 0 0 0 5 0M16.5 13a2.5 2.5 0 0 0 5 0"/>',
    coins: '<circle cx="9" cy="9" r="6"/><path d="M15 9a6 6 0 1 1-6 6M9 6.5v5"/>',
    chart: '<path d="M4 4v16h16M7.5 14.5l3.5-4 3 2.5 5-6M16 7h3v3"/>',
    tag: '<path d="M3.5 12.2V4.5a1 1 0 0 1 1-1h7.7a1 1 0 0 1 .7.3l7.6 7.6a1 1 0 0 1 0 1.4l-7.7 7.7a1 1 0 0 1-1.4 0l-7.6-7.6a1 1 0 0 1-.3-.7z"/><circle cx="8" cy="8" r="1.5"/>',
    car: '<path d="M5 16.5H4a1 1 0 0 1-1-1V13l2-5a2 2 0 0 1 1.9-1.3h10.2A2 2 0 0 1 19 8l2 5v2.5a1 1 0 0 1-1 1h-1M9 16.5h6M3.5 12.5h17"/><circle cx="7" cy="16.5" r="2"/><circle cx="17" cy="16.5" r="2"/>',
    plane: '<path d="M12 2.5c.83 0 1.5.67 1.5 1.5v5l7 4v2l-7-2v4.5l2.5 1.8V21L12 20l-4 1v-1.7l2.5-1.8V13l-7 2v-2l7-4V4c0-.83.67-1.5 1.5-1.5z"/>',
    home: '<path d="M3.5 11L12 4l8.5 7M5.5 9.5V20h13V9.5M10 20v-5.5h4V20"/>',
    bolt: '<path d="M13 2.5L4.5 13.5H11l-1 8 8.5-11H12z"/>',
    cloud: '<path d="M7 18.5a4.5 4.5 0 0 1-.6-8.96 6 6 0 0 1 11.4-.94A5 5 0 0 1 17.5 18.5z"/>',
    film: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 4v16M17 4v16M3 9h4M3 15h4M17 9h4M17 15h4"/>',
    music: '<path d="M9 18V5.5l11-2V16"/><circle cx="6.5" cy="18" r="2.5"/><circle cx="17.5" cy="16" r="2.5"/>',
    game: '<path d="M7 8h10a4 4 0 0 1 4 4v1.5a3.5 3.5 0 0 1-6.3 2.1L14 14.5h-4l-.7 1.1A3.5 3.5 0 0 1 3 13.5V12a4 4 0 0 1 4-4z"/><path d="M7 11v3M5.5 12.5h3M15.5 11.5h.01M17.5 13.5h.01"/>',
    book: '<path d="M12 6.5C10.5 5 8 4.5 3.5 4.5v14c4.5 0 7 .5 8.5 2 1.5-1.5 4-2 8.5-2v-14c-4.5 0-7 .5-8.5 2zM12 6.5v14"/>',
    globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18 14 14 0 0 1 0-18"/>',
    eye: '<path d="M2.5 12C4.5 8 8 5.5 12 5.5s7.5 2.5 9.5 6.5c-2 4-5.5 6.5-9.5 6.5S4.5 16 2.5 12z"/><circle cx="12" cy="12" r="3"/>'
  };

  function buildSymbol(watch) {
    const name = Object.prototype.hasOwnProperty.call(SYMBOL_ICONS, watch.symbol) ? watch.symbol : "eye";
    const figure = el("figure", "wd-image is-symbol");
    figure.setAttribute("aria-hidden", "true");
    const tile = el("span", "wd-symbol");
    tile.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'
      + SYMBOL_ICONS[name] + "</svg>";
    figure.appendChild(tile);
    return figure;
  }

  function imageOf(watch) {
    const image = watch.image;
    return image && IMAGE_PATH.test(image.url || "") ? image : null;
  }

  function buildImage(watch) {
    const image = imageOf(watch);
    if (!image) return buildSymbol(watch);
    // A product shot is shown whole on white; an article photo fills the
    // tile; logos come as rounded tiles of their own and need no frame.
    const kind = IMAGE_KINDS.includes(image.kind) ? image.kind : "item";
    const figure = el("figure", "wd-image is-" + kind);
    const drop = () => figure.replaceWith(buildSymbol(watch));
    const host = image.source_host || hostOf(image.source_url);
    const noun = kind === "logo" ? "Logo" : "Image";
    const frame = el(watch.share_path ? "a" : "span", "wd-image-frame");
    if (frame.tagName === "A") {
      frame.href = watch.share_path;
      frame.target = "_blank";
      frame.rel = "noopener";
      // The question link next to it says the same; one stop for a reader.
      frame.tabIndex = -1;
      frame.setAttribute("aria-hidden", "true");
    }
    if (host) frame.title = noun + ": " + host;
    const img = el("img");
    img.src = image.url;
    img.alt = "";
    img.decoding = "async";
    if (image.width && image.height) {
      img.width = image.width;
      img.height = image.height;
    }
    img.addEventListener("error", drop);
    frame.appendChild(img);
    figure.appendChild(frame);
    return figure;
  }

  // One quiet line of parts ("Next check tomorrow, 09:00 · Weekly on … ·
  // Public page"), joined by real separators so a wrap breaks after a dot.
  function scheduleBlock(watch) {
    const side = el("div", "wd-item-side");
    const parts = [];
    const part = (...nodes) => {
      const wrap = el("span", "wd-side-part");
      wrap.append(...nodes);
      parts.push(wrap);
      return wrap;
    };
    const fields = F();
    if (watch.status === "active" && watch.next_run_at) {
      const next = el("strong", "wd-side-value");
      next.title = fields.dateTimeTitle(watch.next_run_at);
      liveText(next, now => fields.nextCheck(watch, now).text);
      part(next).classList.add("wd-side-next");
      part(el("span", "wd-side-note", fields.scheduleLabel(watch)));
    } else if (watch.status === "resolved") {
      part(el("span", "wd-side-label", "Reached"), " ",
        el("strong", "wd-side-value", fields.shortDay(watch.resolution?.at) || "on evidence"));
    } else {
      part(el("strong", "wd-side-value", "Paused"));
      part(el("span", "wd-side-note", fields.scheduleLabel(watch)));
    }
    const probe = watch.last_probe;
    if (watch.status === "active" && probe && probe.at) {
      const scan = el("span", "wd-side-probe");
      liveText(scan, now => probe.outcome === "new_evidence"
        ? `Daily scan found news ${fields.relativePast(probe.at, now)}`
        : probe.outcome === "failed"
          ? "Daily scan unavailable"
          : `Daily scan: nothing new (${fields.relativePast(probe.at, now)})`);
      part(scan);
    }
    // How the watch is set up belongs with its schedule, not in the status line.
    if (watch.visibility === "public") part(el("span", "wd-side-meta", "Public page"));
    if (watch.telegram_enabled) part(el("span", "wd-side-meta", "Telegram"));
    // A no-break space ties each dot to the part before it.
    parts.forEach((node, index) => {
      if (index) side.append(" ", separator(), " ");
      side.appendChild(node);
    });
    return side;
  }

  // ------------------------------------------------------------------
  // One watch: a card entry owns its parts and is changed in place.
  // ------------------------------------------------------------------

  function buildMain(watch) {
    const state = cardState(watch);
    const main = el("div", "wd-item-main");
    // The picture (or symbol) floats top right and the text flows around it,
    // so a card with one is no taller and its question no narrower than needed.
    main.appendChild(buildImage(watch));
    const status = el("div", "wd-status");
    status.appendChild(el("span", "wd-dot"));
    status.appendChild(el("span", "wd-status-label", state.label));
    // A pending first check's time is the next check, which the side column
    // already shows; saying it twice only crowds the line.
    if (state.when && state.key !== "waiting") {
      // Say what the time is: the last check, unless the label already is
      // the event ("Moved", "Reached").
      const prefix = state.key === "watching" || state.key === "held" ? "checked "
        : state.key === "paused" ? "last check " : "";
      const time = el("time", "wd-status-time");
      time.dateTime = state.when;
      time.title = F().dateTimeTitle(state.when);
      liveText(time, now => prefix + F().relativePast(state.when, now));
      status.appendChild(time);
    }
    main.appendChild(status);

    const question = el("h3", "wd-question");
    const link = el("a", "", watch.question || "(untitled)");
    link.title = watch.question || "";
    link.href = watch.share_path || "#";
    link.target = "_blank";
    link.rel = "noopener";
    question.appendChild(link);
    main.appendChild(question);

    const goal = goalLine(watch);
    if (goal) {
      const line = el("p", "wd-goal");
      // Spaces between the parts let the line break like a sentence; a
      // no-break space keeps the dot at the end of a line, never opening one.
      line.append(
        el("span", "wd-goal-label", "Waiting for"), " ",
        el("span", "wd-goal-text", goal.goal), " ", separator(), " ",
        el("span", "wd-goal-status is-" + goal.tone, goal.status)
      );
      main.appendChild(line);
    }
    const details = String(watch.requirements || "").trim();
    if (details) {
      const line = el("p", "wd-goal wd-details");
      line.append(el("span", "wd-goal-label", "Details"), " ", el("span", "wd-details-text", details));
      main.appendChild(line);
    }

    main.appendChild(el("p", "wd-headline", state.headline));
    if (state.held) main.appendChild(el("p", "wd-held", "Held: " + state.held));
    const sources = buildSources(state.sources && state.sources.length ? state.sources : watch.key_links);
    if (sources) main.appendChild(sources);
    const record = buildRecord(watch);
    if (record) main.appendChild(record);
    return main;
  }

  function actionButton(label, key, handler, extra = "") {
    const button = ui().makeButton(label, "wd-action" + (extra ? " " + extra : ""), handler);
    button.dataset.action = key;
    return button;
  }

  // The footer row: open the page, act on what the state names (Resume next
  // to "Resume to continue", J22), the two ways on from a reached goal, and
  // Settings.
  function buildActions(entry) {
    const watch = entry.watch;
    const actions = el("div", "wd-actions");
    const open = el("a", "wd-action", "Open page");
    open.href = watch.share_path || "#";
    open.target = "_blank";
    open.rel = "noopener";
    open.dataset.action = "open";
    actions.appendChild(open);
    if (watch.status !== "active" && watch.status !== "resolved") {
      actions.appendChild(actionButton("Resume", "resume", () => setStatus(entry, "active"), "is-strong"));
    }
    if (watch.status === "resolved") {
      if (watch.condition) {
        actions.appendChild(actionButton("Not what I wanted", "reject", () => openPanel(entry, "reject")));
      }
      actions.appendChild(actionButton("Watch for something new", "next", () => openPanel(entry, "next"), "is-strong"));
    }
    const toggle = actionButton("Settings", "settings", () => {
      if (entry.item.classList.contains("is-open")) closePanel(entry);
      else openPanel(entry, watch.status === "resolved" ? "next" : "settings");
    }, "wd-action-toggle");
    toggle.setAttribute("aria-expanded", String(entry.item.classList.contains("is-open")));
    if (entry.panel) toggle.setAttribute("aria-controls", entry.panel.root.id);
    actions.appendChild(toggle);
    entry.toggle = toggle;
    return actions;
  }

  let entrySerial = 0;

  function buildCard(watch) {
    const entry = { id: watch.id, watch: Object.assign({}, watch), item: null, main: null, side: null, actions: null, panel: null, note: null };
    const item = el("li", "wd-item");
    entry.item = item;
    item.dataset.watchId = watch.id || "";
    entry.serial = (entrySerial += 1);
    entry.main = buildMain(entry.watch);
    entry.side = scheduleBlock(entry.watch);
    entry.panel = createPanel(entry);
    entry.actions = buildActions(entry);
    entry.note = el("p", "wd-card-note");
    entry.note.setAttribute("role", "status");
    entry.note.hidden = true;
    item.append(entry.main, entry.side, entry.actions, entry.note, entry.panel.root);
    applyTone(entry);
    page.cards.set(watch.id, entry);
    return entry;
  }

  function applyTone(entry) {
    const state = cardState(entry.watch);
    const item = entry.item;
    Array.from(item.classList).filter(name => /^is-(watching|moved|held|waiting|rechecking|resolved|paused|error)$/.test(name))
      .forEach(name => item.classList.remove(name));
    item.classList.add("is-" + state.tone, "has-image");
    item.dataset.state = state.key;
  }

  // The server's answer for one watch replaces that card's parts and
  // nothing else; open stays open, the focus stays on its control (D6, J8).
  function updateCard(id, changes, { fromList = false } = {}) {
    const entry = page.cards.get(id);
    if (!entry || !changes) return entry || null;
    // A change made here is newer than any list asked for before it landed.
    if (!fromList) entry.localAt = Date.now();
    const previousStatus = entry.watch.status;
    Object.assign(entry.watch, changes);
    const focused = document.activeElement;
    const focusKey = focused && (entry.main.contains(focused) || entry.actions.contains(focused))
      ? focused.dataset?.action || (focused.closest(".wd-question") ? "question" : "") : "";
    const main = buildMain(entry.watch);
    const side = scheduleBlock(entry.watch);
    const before = entry.main.getBoundingClientRect().height;
    entry.main.replaceWith(main);
    entry.side.replaceWith(side);
    entry.main = main;
    entry.side = side;
    // A state with more or fewer lines (sources come, sources go) grows or
    // shrinks to its height instead of moving the cards below in one frame.
    morphHeight(main, before);
    const resolvedChanged = (previousStatus === "resolved") !== (entry.watch.status === "resolved");
    if (resolvedChanged) {
      // A reached goal and a running watch have different settings. The
      // way on was chosen in the open panel: it closes softly, and the
      // panel of the new state takes its place once it is shut.
      const old = entry.panel;
      const wasOpen = entry.item.classList.contains("is-open");
      if (wasOpen) setPanelOpen(entry, false);
      const panel = createPanel(entry);
      entry.panel = panel;
      const swap = () => { if (old.root.isConnected) old.root.replaceWith(panel.root); };
      if (wasOpen && !reducedMotion()) setTimeout(swap, 360);
      else swap();
    } else {
      entry.panel.sync(entry.watch);
    }
    const actions = buildActions(entry);
    entry.actions.replaceWith(actions);
    entry.actions = actions;
    applyTone(entry);
    if (focusKey) {
      const target = focusKey === "question" ? entry.main.querySelector(".wd-question a")
        : entry.actions.querySelector(`[data-action="${focusKey}"]`) || entry.toggle;
      try { target?.focus({ preventScroll: true }); } catch (_) { target?.focus(); }
    }
    syncWatchInList(entry.watch);
    return entry;
  }

  function morphHeight(node, from) {
    if (reducedMotion() || !node.isConnected || !from) return;
    const rect = node.getBoundingClientRect();
    if (rect.bottom < 0 || rect.top > window.innerHeight) return;
    const to = rect.height;
    if (Math.abs(to - from) < 2) return;
    node.style.height = from + "px";
    node.style.overflow = "hidden";
    void node.offsetHeight;
    node.style.transition = "height var(--dur-state) var(--ease-standard)";
    node.style.height = to + "px";
    setTimeout(() => {
      node.style.height = "";
      node.style.overflow = "";
      node.style.transition = "";
    }, 260);
  }

  // The account's list (watchState) follows a change made here, so Watch
  // buttons and Agent cards elsewhere say the same.
  function syncWatchInList(watch) {
    const list = watchState.watches;
    if (!Array.isArray(list)) return;
    const index = list.findIndex(item => item.id === watch.id);
    if (index >= 0) list[index] = Object.assign({}, list[index], watch);
    window.dispatchEvent(new CustomEvent("consensio:watches-changed"));
  }

  function cardNote(entry, message, tone = "") {
    if (!entry?.note) return;
    entry.note.textContent = message || "";
    entry.note.hidden = !message;
    entry.note.classList.toggle("is-error", tone === "error");
  }

  function patchWatch(watch, changes) {
    return ui().api("PATCH", "/api/watch/" + encodeURIComponent(watch.id), changes);
  }

  // ------------------------------------------------------------------
  // Settings (J7, J9, J10, J11): the parts of the "New watch" dialog, under
  // the same names. One way to save: a change lands as soon as it is made --
  // a choice right away, a text or a time when it is finished (leaving the
  // field or Enter) -- and says "Saved" at the field. Quick changes in a row
  // travel as one request. Why: a card is the live watch, there is no draft
  // of it to commit, and nothing typed can be left behind by a second
  // button (J9).
  // ------------------------------------------------------------------

  function createSaver(entry) {
    let pending = {};
    let touched = new Set();
    let timer = null;
    let running = null;
    function queue(changes, fieldNode, delay = 350) {
      Object.assign(pending, changes);
      if (fieldNode) touched.add(fieldNode);
      clearTimeout(timer);
      timer = setTimeout(flush, delay);
    }
    async function flush() {
      clearTimeout(timer);
      timer = null;
      if (running) await running.catch(() => {});
      if (!Object.keys(pending).length) return;
      const changes = pending;
      const fieldsNow = [...touched];
      pending = {};
      touched = new Set();
      fieldsNow.forEach(node => node.classList.add("is-saving"));
      running = patchWatch(entry.watch, changes).then(data => {
        const saved = data?.watch || {};
        // A field the server did not take (an older server without it)
        // is said at the field, never assumed saved.
        const ignored = Object.keys(changes).filter(key =>
          ["visibility"].includes(key) && saved[key] !== undefined && saved[key] !== changes[key]);
        updateCard(entry.id, saved);
        fieldsNow.forEach(node => {
          if (ignored.length && node.dataset.field && ignored.includes(node.dataset.field)) {
            F().setError(node, "This can’t be changed here yet.");
          } else {
            F().markSaved(node);
          }
        });
        entry.panel.clean(Object.keys(changes));
      }, error => {
        // A server that does not know a field yet refuses the change with
        // its list of fields; at the field that reads as "not here yet".
        const message = error?.status === 400 && "visibility" in changes
          ? "This can’t be changed here yet." : errorText(error, "Couldn’t save. Try again.");
        fieldsNow.forEach(node => F().setError(node, message));
        entry.panel.sync(entry.watch, { force: true });
      }).finally(() => {
        fieldsNow.forEach(node => node.classList.remove("is-saving"));
        running = null;
      });
      return running;
    }
    return { queue, flush };
  }

  function goalOptionsFor(watch) {
    const goal = String(watch.condition || "").trim();
    return goal ? [goal] : [];
  }

  function createPanel(entry) {
    const root = el("div", "wd-settings");
    root.id = "wdSettings" + String(entry.serial || 0);
    root.setAttribute("inert", "");
    root.setAttribute("aria-hidden", "true");
    const inner = el("div", "wd-settings-inner");
    const content = el("div", "wd-settings-content");
    inner.appendChild(content);
    root.appendChild(inner);
    const panel = entry.watch.status === "resolved"
      ? buildResolvedPanel(entry, content)
      : buildActivePanel(entry, content);
    panel.root = root;
    panel.content = content;
    return panel;
  }

  // Footer of every panel: delete with Undo (J14, J21), and for a running
  // watch Pause/Resume.
  function panelFooter(entry, { pauseButton = true } = {}) {
    const footer = el("div", "wd-settings-footer");
    let pause = null;
    if (pauseButton) {
      pause = ui().makeButton("Pause", "wd-button", () => {
        setStatus(entry, entry.watch.status === "active" ? "paused" : "active");
      });
      pause.dataset.action = "pause";
      footer.appendChild(pause);
    }
    const remove = ui().makeButton("Delete", "wd-button is-danger", () => deleteWatch(entry));
    remove.dataset.action = "delete";
    footer.appendChild(remove);
    return { footer, pause };
  }

  function buildActivePanel(entry, content) {
    const fields = F();
    const watch = entry.watch;
    const saver = createSaver(entry);
    const prefix = "wd" + String(entry.serial || 0) + "_";
    const dirty = new Set();

    // --- the goal, as a choice ---------------------------------------
    const goals = fields.goalList({ prefix: prefix + "goal", name: prefix + "goalChoice" });
    goals.input.classList.add("wd-goal-input", "is-goal");
    goals.root.dataset.field = "condition";
    goals.root.classList.add("watch-field");
    content.appendChild(goals.root);
    function syncGoals(current) {
      if (dirty.has("condition") && document.activeElement === goals.input) return;
      // A goal typed and not saved yet (its save failed, or it is on its
      // way) stays in its field and chosen; a failed save never wipes it.
      const typed = dirty.has("condition") && goals.input.value.trim() !== "";
      goals.setOffered(goalOptionsFor(current));
      goals.offered.classList.toggle("is-empty", !current.condition);
      goals.select(typed ? "custom" : current.condition ? String(current.condition).trim() : "none");
      if (!typed && document.activeElement !== goals.input) goals.input.value = "";
      goals.hint.textContent = current.condition
        ? "Checked on every run. When a source confirms it, the watch ends and tells you."
        : "You hear from us whenever a source changes the answer.";
    }
    function saveGoal(goal) {
      const changes = { condition: goal };
      if (!goal && entry.watch.email_mode === "condition") {
        changes.email_mode = "changes_only";
        alerts.value = "changes_only";
      }
      fields.relabelAlerts(alerts, Boolean(goal));
      saver.queue(changes, goals.root, 0);
    }
    goals.root.addEventListener("change", event => {
      if (event.target === goals.input) return;
      // Another choice drops what was typed for "Something else".
      if (event.target !== goals.customChoice) dirty.delete("condition");
      if (event.target === goals.anyChoice && goals.anyChoice.checked) {
        if (entry.watch.condition) saveGoal("");
      } else if (event.target === goals.customChoice) {
        goals.input.focus();
      }
    });
    goals.input.addEventListener("focus", () => { goals.customChoice.checked = true; });
    goals.input.addEventListener("input", () => {
      dirty.add("condition");
      goals.customChoice.checked = true;
      fields.setError(goals.root, "");
    });
    function commitGoalText() {
      const text = goals.input.value.replace(/\s+/g, " ").trim();
      if (!text || text === String(entry.watch.condition || "").trim()) return;
      saveGoal(text);
    }
    goals.input.addEventListener("change", commitGoalText);
    // Leaving the field again tries a failed save once more ("Try again").
    goals.input.addEventListener("blur", () => { if (dirty.has("condition")) commitGoalText(); });
    goals.input.addEventListener("keydown", event => {
      if (event.key !== "Enter" || window.App.isComposingKey?.(event) || event.isComposing) return;
      event.preventDefault();
      commitGoalText();
    });

    // --- details ------------------------------------------------------
    const details = fields.detailsInput(prefix + "details", watch.requirements || "");
    details.classList.add("wd-goal-input", "is-details");
    details.setAttribute("aria-label", "Details that matter");
    const detailsField = fields.field({ label: "Details that matter", control: details, id: prefix + "details",
      hint: "Every check searches with these. The goal only counts when they fit." });
    detailsField.dataset.field = "requirements";
    const ruledOut = el("p", "watch-field-hint wd-ruled-out");
    detailsField.insertBefore(ruledOut, detailsField.querySelector(".watch-field-error"));
    content.appendChild(detailsField);
    details.addEventListener("input", () => dirty.add("requirements"));
    function commitDetails() {
      const text = details.value.replace(/\s+/g, " ").trim();
      if (text === String(entry.watch.requirements || "").trim()) {
        dirty.delete("requirements");
        return;
      }
      saver.queue({ requirements: text }, detailsField, 0);
    }
    details.addEventListener("change", commitDetails);
    details.addEventListener("keydown", event => {
      if (event.key !== "Enter" || event.shiftKey || window.App.isComposingKey?.(event) || event.isComposing) return;
      event.preventDefault();
      commitDetails();
    });

    // --- schedule -----------------------------------------------------
    const grid = el("div", "watch-config-grid wd-settings-grid");
    const interval = fields.intervalSelect(prefix + "interval", watch.interval, ui().dailyIntervalAllowed());
    const weekday = fields.weekdaySelect(prefix + "weekday", watch.run_weekday || ui().browserWeekday());
    const time = fields.timeInput(prefix + "time", watch.run_time || "");
    const intervalField = fields.field({ label: "How often", control: interval });
    intervalField.dataset.field = "interval";
    const weekdayField = fields.field({ label: "Day", control: weekday });
    weekdayField.dataset.field = "run_weekday";
    const timeField = fields.field({ label: "Time", control: time, id: prefix + "time" });
    timeField.dataset.field = "run_time";
    const timeNote = el("p", "watch-field-hint wd-time-note");
    timeField.insertBefore(timeNote, timeField.querySelector(".watch-field-error"));
    grid.append(intervalField, weekdayField, timeField);
    content.appendChild(grid);
    // The day comes and goes with "Weekly", softly (the time may wrap).
    const syncWeekday = () => {
      const hide = interval.value !== "weekly";
      if (weekdayField.hidden !== hide) ui().smoothHeight(grid, () => { weekdayField.hidden = hide; });
    };
    interval.addEventListener("change", () => {
      syncWeekday();
      saver.queue({ interval: interval.value, run_weekday: interval.value === "weekly" ? weekday.value : "" }, intervalField);
    });
    weekday.addEventListener("change", () => saver.queue({ run_weekday: weekday.value }, weekdayField));
    // A time is saved when it is finished: on leaving the field or Enter,
    // never after the first digits (J11). The field is never locked.
    time.addEventListener("input", () => dirty.add("run_time"));
    function commitTime() {
      if (!time.value || time.value === entry.watch.run_time) {
        dirty.delete("run_time");
        return;
      }
      saver.queue({ run_time: time.value, timezone: ui().browserTimezone() }, timeField, 0);
    }
    time.addEventListener("blur", commitTime);
    time.addEventListener("keydown", event => {
      if (event.key === "Enter") {
        event.preventDefault();
        commitTime();
      }
    });

    // --- alerts and channels --------------------------------------------
    const alerts = fields.alertSelect(prefix + "alerts", watch.email_mode, Boolean(watch.condition));
    const alertsField = fields.field({ label: "Notify me", control: alerts, wide: true });
    alertsField.dataset.field = "email_mode";
    content.appendChild(alertsField);
    alerts.addEventListener("change", () => {
      if (alerts.value === "condition" && !String(entry.watch.condition || "").trim()) {
        fields.setError(alertsField, "Choose what you are waiting for first.");
        alerts.value = entry.watch.email_mode || "changes_only";
        return;
      }
      saver.queue({ email_mode: alerts.value }, alertsField);
    });
    const channels = ui().buildChannels({
      onChange(name, box) {
        if (!channels.email.checked && !channels.telegram.checked) {
          box.checked = !box.checked;
          fields.setError(channels.field, "Keep at least one way to reach you.");
          return;
        }
        saver.queue({ [name]: box.checked }, channels.field);
      }
    });
    channels.field.dataset.field = "channels";
    content.appendChild(channels.field);

    // --- page -----------------------------------------------------------
    const visibility = fields.visibilitySelect(prefix + "visibility", watch.visibility);
    const visibilityField = fields.field({ label: "Watch page", control: visibility, className: "is-medium" });
    visibilityField.dataset.field = "visibility";
    content.appendChild(visibilityField);
    visibility.addEventListener("change", () => saver.queue({ visibility: visibility.value }, visibilityField, 0));
    const listingSlot = el("div", "wd-listing-slot");
    content.appendChild(listingSlot);

    // --- picture --------------------------------------------------------
    const pictureSlot = el("div", "wd-picture-slot");
    content.appendChild(pictureSlot);

    const { footer, pause } = panelFooter(entry);
    content.appendChild(footer);

    function sync(current, { force = false } = {}) {
      const active = document.activeElement;
      const keep = control => !force && (control === active);
      syncGoals(current);
      if (!keep(details) && !dirty.has("requirements")) details.value = current.requirements || "";
      const ruled = ruledOutHint(current);
      ruledOut.textContent = ruled;
      ruledOut.hidden = !ruled;
      if (!keep(interval)) interval.value = ["daily", "monthly"].includes(current.interval) ? current.interval : "weekly";
      if (!keep(weekday) && current.run_weekday) weekday.value = current.run_weekday;
      // A typed time and typed details stay through a failed save, like the goal.
      if (!keep(time) && !dirty.has("run_time")) time.value = current.run_time || "";
      const zone = fields.timezoneNote(current.timezone);
      timeNote.textContent = zone ? "In " + zone : "";
      timeNote.hidden = !zone;
      syncWeekday();
      if (!keep(alerts)) alerts.value = ["condition", "every_run"].includes(current.email_mode) ? current.email_mode : "changes_only";
      fields.relabelAlerts(alerts, Boolean(String(current.condition || "").trim()));
      if (force || active !== channels.email) channels.email.checked = current.email_enabled !== false;
      const telegram = watchState.telegram || page.telegram || {};
      channels.sync(telegram);
      if (force || active !== channels.telegram) channels.telegram.checked = current.telegram_enabled === true && telegram.connected === true;
      if (!keep(visibility)) visibility.value = current.visibility === "public" ? "public" : "private";
      listingSlot.replaceChildren();
      if (current.visibility !== "private" && current.share_id) listingSlot.appendChild(renderListing(entry));
      pictureSlot.replaceChildren();
      const picture = pictureRow(entry);
      if (picture) pictureSlot.appendChild(picture);
      if (pause) pause.textContent = current.status === "active" ? "Pause" : "Resume";
    }
    sync(watch, { force: true });
    return {
      kind: "active",
      sync,
      clean(keys) {
        keys.forEach(key => dirty.delete(key));
        if (keys.includes("condition")) syncGoals(entry.watch);
      },
      flush: () => {
        if (document.activeElement === time) commitTime();
        if (dirty.has("requirements")) commitDetails();
        if (dirty.has("condition")) commitGoalText();
        return saver.flush();
      },
      focusFirst: () => goals.checked() || goals.anyChoice,
      saver
    };
  }

  // A reached goal offers two ways on: a wrong match keeps the goal and
  // rules the match out, a reached goal asks for the next one -- with the
  // same choice list as the dialog. Only the box for the way chosen shows.
  function buildResolvedPanel(entry, content) {
    const fields = F();
    const watch = entry.watch;
    const prefix = "wd" + String(entry.serial || 0) + "_";
    let reject = null;
    let rejectInput = null;
    if (watch.condition) {
      reject = el("div", "wd-goal-editor wd-reject");
      const label = el("label", "watch-goal-label", "Not what you wanted?");
      rejectInput = fields.detailsInput(prefix + "reject", "");
      rejectInput.classList.add("wd-goal-input", "is-reject");
      rejectInput.setAttribute("aria-label", "What was wrong with this match");
      label.htmlFor = rejectInput.id;
      reject.append(label, rejectInput, el("p", "watch-field-hint",
        "Say what was wrong, e.g. used or a private seller. The goal stays, and this match never counts again."));
      const row = el("div", "wd-goal-actions");
      const keep = ui().makeButton("Keep watching", "wd-button is-primary", async () => {
        const text = rejectInput.value.replace(/\s+/g, " ").trim();
        keep.disabled = true;
        try {
          const data = await patchWatch(entry.watch, { status: "active", reject_match: true, requirements: text });
          window.App?.trackAppEvent?.("app_watch_match_rejected", { with_details: Boolean(text) });
          updateCard(entry.id, data.watch);
          cardNote(entry, "Watching again. That match won’t count again.");
        } catch (error) {
          keep.disabled = false;
          fields.setError(reject, errorText(error));
        }
      });
      row.appendChild(keep);
      reject.appendChild(row);
      const error = el("p", "watch-field-error");
      error.setAttribute("role", "alert");
      error.hidden = true;
      reject.appendChild(error);
      reject.hidden = true;
      content.appendChild(reject);
    }
    const next = el("div", "wd-goal-editor wd-next-goal");
    const goals = fields.goalList({ prefix: prefix + "next", name: prefix + "nextChoice", label: "What are you waiting for next?" });
    goals.input.classList.add("wd-goal-input", "is-goal");
    goals.root.classList.add("watch-field");
    goals.offered.classList.add("is-empty");
    goals.select("custom");
    goals.hint.textContent = "The watch runs again with this goal. Pick “Any change” to watch for any change on evidence.";
    next.appendChild(goals.root);
    const row = el("div", "wd-goal-actions");
    const keepWatching = ui().makeButton("Keep watching", "wd-button is-primary", async () => {
      const choice = goals.value();
      if (choice.kind === "custom" && !choice.goal) {
        fields.setError(goals.root, "Describe the event, or pick “Any change”.");
        goals.input.focus();
        return;
      }
      const goal = choice.kind === "custom" ? choice.goal : "";
      const changes = { condition: goal, status: "active" };
      if (!goal && entry.watch.email_mode === "condition") changes.email_mode = "changes_only";
      keepWatching.disabled = true;
      try {
        const data = await patchWatch(entry.watch, changes);
        updateCard(entry.id, data.watch);
        cardNote(entry, "Watching again.");
      } catch (error) {
        keepWatching.disabled = false;
        fields.setError(goals.root, errorText(error));
      }
    });
    row.appendChild(keepWatching);
    next.appendChild(row);
    content.appendChild(next);
    goals.input.addEventListener("input", () => fields.setError(goals.root, ""));
    goals.input.addEventListener("focus", () => { goals.customChoice.checked = true; });
    content.appendChild(panelFooter(entry, { pauseButton: false }).footer);
    return {
      kind: "resolved",
      sync() { /* nothing here mirrors the server's fields */ },
      clean() {},
      flush: () => Promise.resolve(),
      show(way) {
        const rejecting = way === "reject" && Boolean(reject);
        if (reject) reject.hidden = !rejecting;
        next.hidden = rejecting;
      },
      focusFirst: way => way === "reject" && rejectInput ? rejectInput : goals.input
    };
  }

  function ruledOutHint(watch) {
    const names = (Array.isArray(watch.rejected_sources) ? watch.rejected_sources : [])
      .map(source => source.title || hostOf(source.url))
      .filter(Boolean);
    if (!names.length) return "";
    const shown = names.slice(-3).join(", ");
    return "Ruled out: " + shown + (names.length > 3 ? ` and ${names.length - 3} more` : "") + ".";
  }

  // The panel opens with its content: the rows grow from 0 to their height
  // while the chevron turns, and close the same way (J13).
  function setPanelOpen(entry, open, { animate = true, way = "settings" } = {}) {
    const root = entry.panel.root;
    const item = entry.item;
    if (open) {
      entry.panel.show?.(way);
      root.removeAttribute("inert");
      root.removeAttribute("aria-hidden");
    } else {
      // Whatever was typed is saved on the way out.
      entry.panel.flush?.();
      root.setAttribute("inert", "");
      root.setAttribute("aria-hidden", "true");
    }
    if (!animate) item.classList.add("is-instant");
    item.classList.toggle("is-open", open);
    if (!animate) {
      void item.offsetHeight;
      item.classList.remove("is-instant");
    }
    entry.toggle?.setAttribute("aria-expanded", String(open));
  }

  function openPanel(entry, way = "settings") {
    if (entry.item.classList.contains("is-open")) {
      entry.panel.show?.(way);
    } else {
      setPanelOpen(entry, true, { way });
    }
    if (way === "reject" || way === "next") {
      const target = entry.panel.focusFirst?.(way);
      try { target?.focus({ preventScroll: true }); } catch (_) { target?.focus(); }
    }
  }

  function closePanel(entry) {
    setPanelOpen(entry, false);
  }

  // "Google listing": the owner nominates a public page for the search
  // index. It only sets a request flag; a human reviews before anything is
  // listed.
  function renderListing(entry) {
    const watch = entry.watch;
    const block = el("div", "wd-listing");
    block.appendChild(el("span", "watch-field-label", "Google listing"));
    const note = el("p", "watch-field-hint");
    block.appendChild(note);
    async function request(button, want) {
      button.disabled = true;
      try {
        await ui().api("POST", "/api/share/" + encodeURIComponent(watch.share_id) + "/indexing-request", { want: want });
        window.App?.trackAppEvent?.("app_watch_listing_request", { want: want });
        updateCard(entry.id, { index_requested: want });
        cardNote(entry, want
          ? "Nominated. A human reviews every page before it appears on Google."
          : "Listing request withdrawn.");
      } catch (error) {
        button.disabled = false;
        cardNote(entry, errorText(error), "error");
      }
    }
    if (watch.indexed) {
      note.textContent = "Listed: the page appears on Google, in the sitemap and under related questions.";
    } else if (watch.index_requested) {
      note.textContent = "Requested. A human reviews every page before it is listed.";
      block.appendChild(ui().makeButton("Withdraw request", "wd-button", function () { request(this, false); }));
    } else {
      note.textContent = watch.index_eligible
        ? "Public pages stay unlisted until you nominate them. This page meets the quality bar."
        : "Public pages stay unlisted until you nominate them. This page is below the quality bar, but you can still ask for a review.";
      block.appendChild(ui().makeButton("Request listing", "wd-button", function () { request(this, true); }));
    }
    return block;
  }

  // Removing the picture is a setting with Undo, not a permanent × on the
  // tile a thumb lands on (J23). Without it, the symbol stands there.
  function pictureRow(entry) {
    const image = imageOf(entry.watch);
    if (!image) return null;
    const kind = IMAGE_KINDS.includes(image.kind) ? image.kind : "item";
    const noun = kind === "logo" ? "logo" : "picture";
    const host = image.source_host || hostOf(image.source_url);
    const row = el("div", "wd-picture-row");
    row.appendChild(el("span", "watch-field-hint", host ? `The ${noun} comes from ${host}.` : `The card shows a ${noun}.`));
    const remove = ui().makeButton(`Remove ${noun}`, "wd-link", () => removePicture(entry));
    remove.dataset.action = "remove-picture";
    row.appendChild(remove);
    return row;
  }

  function removePicture(entry) {
    const watch = entry.watch;
    const image = watch.image;
    if (!image) return;
    watch.image = null;
    updateCard(entry.id, {});
    showUndoToast("Picture removed", {
      undo: () => updateCard(entry.id, { image }),
      commit: async () => {
        try {
          await ui().api("DELETE", "/api/watch/" + encodeURIComponent(watch.id) + "/image");
        } catch (error) {
          updateCard(entry.id, { image });
          cardNote(entry, "Could not remove the picture: " + errorText(error), "error");
        }
      }
    });
  }

  // Pause and Resume change the card where it is; the list sorts it on the
  // next visit (J14). The result is said with a way back.
  async function setStatus(entry, status, { undoable = true } = {}) {
    const previous = entry.watch.status;
    cardNote(entry, "");
    try {
      const data = await patchWatch(entry.watch, { status });
      updateCard(entry.id, data.watch);
      refreshLimits();
      // Deleted while the pause was on its way: the deletion's Undo stays
      // on screen; a "Watch paused · Undo" now would end it, and the watch
      // would be gone before the reader could take it back.
      if (page.pendingDeletes.has(entry.id) || !page.cards.has(entry.id)) return;
      if (undoable) {
        showUndoToast(status === "active" ? "Watching again" : "Watch paused", {
          undo: () => setStatus(entry, previous === "active" ? "active" : "paused", { undoable: false })
        });
      }
    } catch (error) {
      cardNote(entry, errorText(error), "error");
    }
  }

  // Delete is delayed until its Undo has passed (J14): the card folds away
  // at once, the request goes out when the reader lets it.
  function deleteWatch(entry) {
    if (page.pendingDeletes.has(entry.id)) return;
    const watch = entry.watch;
    const hadFocus = entry.item.contains(document.activeElement);
    page.pendingDeletes.set(entry.id, entry);
    collapse(entry.item, () => updateSectionCounts());
    const notice = showUndoToast(watch.awaiting_first_run ? "Watch deleted, with its empty page" : "Watch deleted", {
      undo: () => {
        page.pendingDeletes.delete(entry.id);
        expand(entry.item);
        updateSectionCounts();
      },
      commit: async () => {
        try {
          await ui().api("DELETE", "/api/watch/" + encodeURIComponent(watch.id));
          page.pendingDeletes.delete(entry.id);
          page.cards.delete(entry.id);
          entry.item.remove();
          updateSectionCounts();
          refreshLimits();
        } catch (error) {
          page.pendingDeletes.delete(entry.id);
          expand(entry.item);
          updateSectionCounts();
          cardNote(entry, "Could not delete: " + errorText(error), "error");
        }
      }
    });
    // A keyboard reader keeps a place: the way back.
    if (hadFocus) notice.focusUndo();
  }

  // A card folds to nothing with the gap it held, so the cards below glide
  // up instead of jumping; expand is the same way back.
  function gapOf(node) {
    const list = node.parentElement;
    if (!list) return 0;
    return parseFloat(getComputedStyle(list).rowGap || getComputedStyle(list).gap) || 0;
  }

  // One fold at a time per node. A newer one (Undo right after Delete, or
  // Delete again right after Undo) takes over from where the running one
  // stands, and the older one's end never lands on it: a quick Undo used to
  // leave the card hidden for good once the fold-away finished.
  const folds = new WeakMap();

  function startFold(node, direction) {
    const fold = { direction };
    folds.set(node, fold);
    return fold;
  }

  function foldIsCurrent(node, fold) {
    return folds.get(node) === fold;
  }

  function endFold(node, fold) {
    if (!foldIsCurrent(node, fold)) return false;
    folds.delete(node);
    return true;
  }

  // Folding away right now (and not yet hidden).
  function leaving(node) {
    return folds.get(node)?.direction === "out";
  }

  function collapse(node, done) {
    const fold = startFold(node, "out");
    const finish = () => {
      if (!endFold(node, fold)) return;
      node.hidden = true;
      node.style.cssText = "";
      done?.();
    };
    if (reducedMotion() || !node.isConnected) {
      finish();
      return;
    }
    const height = node.getBoundingClientRect().height;
    const gap = gapOf(node);
    const sideways = node.nextElementSibling && !node.nextElementSibling.hidden ? "marginBottom" : "marginTop";
    node.style.overflow = "hidden";
    // The measured height includes the padding; so does the height the fold
    // starts from (a card is content-box: it grew by its padding in the
    // first frame).
    node.style.boxSizing = "border-box";
    node.style.height = height + "px";
    void node.offsetHeight;
    // Leaving starts slowly (--ease-in), so a tall card never jumps in its
    // first frame.
    node.style.transition = "height var(--dur-layer) var(--ease-in), opacity var(--dur-state) var(--ease-standard), margin var(--dur-layer) var(--ease-in), padding var(--dur-layer) var(--ease-in)";
    node.style.height = "0px";
    node.style.paddingTop = node.style.paddingBottom = "0px";
    node.style.marginTop = node.style.marginBottom = "0px";
    node.style.opacity = "0";
    if (gap && (node.previousElementSibling || node.nextElementSibling)) node.style[sideways] = -gap + "px";
    const onEnd = event => { if (event.target === node && event.propertyName === "height") end(); };
    const end = () => {
      node.removeEventListener("transitionend", onEnd);
      finish();
    };
    node.addEventListener("transitionend", onEnd);
    setTimeout(end, 500);
  }

  // Where a fold stands in this frame, to go on from there.
  function foldState(node) {
    const style = getComputedStyle(node);
    return {
      height: node.getBoundingClientRect().height + "px",
      opacity: style.opacity,
      paddingTop: style.paddingTop,
      paddingBottom: style.paddingBottom,
      marginTop: style.marginTop,
      marginBottom: style.marginBottom
    };
  }

  function expand(node) {
    // An Undo while the card still folds away turns it around where it is.
    const from = leaving(node) && !node.hidden && node.isConnected ? foldState(node) : null;
    const fold = startFold(node, "in");
    node.hidden = false;
    node.style.cssText = "";
    if (reducedMotion() || !node.isConnected) {
      endFold(node, fold);
      return;
    }
    const height = node.getBoundingClientRect().height;
    const gap = gapOf(node);
    const sideways = node.nextElementSibling && !node.nextElementSibling.hidden ? "marginBottom" : "marginTop";
    node.style.overflow = "hidden";
    node.style.boxSizing = "border-box";
    if (from) {
      Object.assign(node.style, from);
    } else {
      node.style.height = "0px";
      node.style.opacity = "0";
      node.style.paddingTop = node.style.paddingBottom = "0px";
      node.style.marginTop = node.style.marginBottom = "0px";
      if (gap && (node.previousElementSibling || node.nextElementSibling)) node.style[sideways] = -gap + "px";
    }
    void node.offsetHeight;
    node.style.transition = "height var(--dur-layer) var(--ease-standard), opacity var(--dur-state) var(--ease-standard), margin var(--dur-layer) var(--ease-standard), padding var(--dur-layer) var(--ease-standard)";
    node.style.height = height + "px";
    node.style.opacity = "1";
    node.style.paddingTop = node.style.paddingBottom = "";
    node.style.marginTop = node.style.marginBottom = "";
    setTimeout(() => { if (endFold(node, fold)) node.style.cssText = ""; }, 500);
  }

  // ------------------------------------------------------------------
  // Undo notice: the app's one notice line (App.toast, notices.js) with the
  // action that takes it back. A newer notice lets the older one happen.
  // App.watchDashboard.showUndoToast(message, {undo, commit, timeout}) stays
  // as a thin forward for the cards.
  // ------------------------------------------------------------------
  let dashToast = null;
  // Commits on their way (a DELETE whose Undo has passed): the logout waits
  // for them while the account's token is still there.
  const committing = new Set();

  function runCommit(commit) {
    let running;
    try {
      running = Promise.resolve(commit());
    } catch (error) {
      running = Promise.reject(error);
    }
    const tracked = running.catch(error => console.error("Watch change failed:", error))
      .finally(() => committing.delete(tracked));
    committing.add(tracked);
    return tracked;
  }

  function showUndoToast(message, { undo = null, commit = null, timeout = UNDO_MS } = {}) {
    dashToast?.settle();
    const handle = window.App.toast({
      message,
      action: typeof undo === "function" ? { label: "Undo", onAction: () => { undo(); } } : null,
      onExpire: typeof commit === "function" ? () => { runCommit(commit); } : null,
      duration: timeout,
    });
    dashToast = handle;
    return {
      dismiss: () => handle.settle(),
      focusUndo: () => handle.focusAction()
    };
  }

  // Leaving the page (or the tab) or logging out lets every pending Undo
  // happen now and saves what is typed in an open card. Resolves once all of
  // it was sent (the logout waits for that before it drops the token).
  function commitPending() {
    dashToast?.settle();
    dashToast = null;
    const saving = [];
    page.cards.forEach(entry => {
      const flushed = entry.panel?.flush?.();
      if (flushed && typeof flushed.then === "function") saving.push(flushed);
    });
    return Promise.allSettled([...committing, ...saving]).then(() => undefined);
  }

  // ------------------------------------------------------------------
  // Page sections.
  // ------------------------------------------------------------------

  // The difference to a scheduled chatbot prompt, said once and plainly.
  const DIFFERENCES = [
    {
      title: "Several model families, cross-checked",
      body: "Each check asks independent AI model families and cross-checks their answers. One model’s slip is not your alert."
    },
    {
      title: "Only evidence moves it",
      body: "A search that misses a source is not a retraction. You hear about a change when a source backs it, or when a second check confirms a new reading."
    },
    {
      title: "It knows when it is done",
      body: "Tell it what you are waiting for. When a source confirms it, the watch ends and shows you the proof."
    }
  ];

  const COMPARISON = [
    ["One model answers again", "Several model families answer independently"],
    ["A new answer every time; you compare", "A message only when the evidence moves, with the source"],
    ["One missed search hit changes the answer", "A missing source never counts as counter-evidence"],
    ["Runs until you switch it off", "Ends when what you wait for happens"]
  ];

  function differencesGrid() {
    const grid = el("div", "wd-explainer-grid");
    DIFFERENCES.forEach((item, index) => {
      const cell = el("div", "wd-explainer-item");
      cell.appendChild(el("span", "wd-explainer-index", String(index + 1)));
      cell.appendChild(el("strong", "", item.title));
      cell.appendChild(el("p", "", item.body));
      grid.appendChild(cell);
    });
    return grid;
  }

  // At the end of the page, closed unless the reader opened it before: the
  // own watches come first (J29).
  function renderDifferences(container, { open = false } = {}) {
    const box = el("details", "wd-explainer");
    let stored = null;
    try { stored = window.localStorage.getItem(EXPLAINER_STORAGE_KEY); } catch (_) {}
    box.open = stored === null ? open : stored === "true";
    const summary = el("summary");
    summary.appendChild(el("span", "wd-explainer-title", "Why a watch, not a scheduled prompt"));
    summary.appendChild(el("span", "wd-explainer-hint", "How it works"));
    box.appendChild(summary);
    box.addEventListener("toggle", () => {
      try { window.localStorage.setItem(EXPLAINER_STORAGE_KEY, String(box.open)); } catch (_) {}
    });
    box.appendChild(differencesGrid());
    const table = el("table", "wd-compare");
    table.innerHTML = "<thead><tr><th scope=\"col\">A scheduled prompt</th><th scope=\"col\">A consens.io watch</th></tr></thead>";
    const body = el("tbody");
    COMPARISON.forEach(([left, right]) => {
      const row = el("tr");
      row.appendChild(el("td", "", left));
      row.appendChild(el("td", "", right));
      body.appendChild(row);
    });
    table.appendChild(body);
    box.appendChild(table);
    container.appendChild(box);
  }

  const EXAMPLES = [
    { question: "When will OpenAI release its next flagship model?", goal: "The model is officially released" },
    { question: "Has the EU published final guidance for general-purpose AI models?", goal: "The final guidance is published" },
    { question: "Is the new iPhone available in Germany yet?", goal: "It is on sale in Germany" }
  ];

  // No watches yet: the page head keeps its one heading and its one action
  // ("New watch"); below, on the same left edge, only the ways to start
  // (J24).
  function renderEmpty(container) {
    const section = el("section", "wd-empty");
    const head = el("div", "wd-section-head");
    head.appendChild(el("h2", "", "Start from an example"));
    section.appendChild(head);
    const list = el("div", "wd-example-list");
    EXAMPLES.forEach(example => {
      const button = ui().makeButton("", "wd-example", event => {
        ui().openWatchDialog("create", { question: example.question, goal: example.goal, trigger: event.currentTarget, source: "example" });
      });
      button.appendChild(el("strong", "", example.question));
      button.appendChild(el("span", "", "Waiting for: " + example.goal));
      list.appendChild(button);
    });
    section.appendChild(list);
    container.appendChild(section);
    renderDifferences(container, { open: false });
  }

  // A guest sees what a watch is, by one example card, and how it differs;
  // the head's button leads into the sign-in and back (J3).
  const GUEST_EXAMPLE = {
    id: "example", status: "active", question: "Is the new iPhone available in Germany yet?",
    condition: "It is on sale in Germany", goal_state: "not_met", interval: "weekly", run_weekday: "tuesday",
    run_time: "09:00", symbol: "phone", share_path: "",
    history: [
      { ts: "", signal: "stable", trigger: "stable" }, { ts: "", signal: "stable", trigger: "stable" },
      { ts: "", signal: "held", trigger: "stable" }, { ts: "", signal: "stable", trigger: "stable" }
    ]
  };

  function renderGuest(message) {
    renderToken += 1;
    page.built = false;
    page.cards.clear();
    const body = document.getElementById("watchDashBody");
    if (!body) return;
    syncHead({ guest: true });
    const now = Date.now();
    const example = Object.assign({}, GUEST_EXAMPLE, {
      next_run_at: new Date(now + 20 * 3600 * 1000).toISOString(),
      history: GUEST_EXAMPLE.history.map((point, index) => ({ ...point, ts: new Date(now - (3 - index) * 7 * 86400000 - 2 * 3600000).toISOString() })),
      timezone: F().browserTimezone()
    });
    const fragment = document.createDocumentFragment();
    if (message) fragment.appendChild(alertBar(message));
    const section = el("section", "wd-guest");
    const head = el("div", "wd-section-head");
    head.appendChild(el("h2", "", "What a watch looks like"));
    section.appendChild(head);
    const list = el("ul", "wd-list");
    const item = el("li", "wd-item is-example");
    item.setAttribute("aria-label", "Example watch");
    const main = buildMain(example);
    main.querySelector(".wd-question a")?.removeAttribute("href");
    item.append(main, scheduleBlock(example));
    item.classList.add("is-" + cardState(example).tone, "has-image");
    main.querySelector(".wd-status")?.appendChild(el("span", "wd-example-badge", "Example"));
    list.appendChild(item);
    section.appendChild(list);
    section.appendChild(differencesGrid());
    fragment.appendChild(section);
    body.replaceChildren(fragment);
    body.removeAttribute("aria-busy");
  }

  function renderSkeleton() {
    const body = document.getElementById("watchDashBody");
    if (!body) return;
    body.innerHTML = window.App.watchSkeleton?.() || '<div class="wd-skeleton skeleton-group" role="status" aria-label="Loading your watches"></div>';
    body.setAttribute("aria-busy", "true");
  }

  function alertBar(message, retry) {
    const bar = el("div", "wd-alert");
    bar.setAttribute("role", "alert");
    bar.appendChild(el("span", "", message));
    if (retry) {
      const button = ui().makeButton("Try again", "wd-link", retry);
      bar.appendChild(button);
    }
    return bar;
  }

  // The head: one heading, one action. At the limit the action steps back
  // to a plain button and says why before any typing (J25, the dialog
  // explains); a guest is invited to sign in.
  function syncHead({ guest = false } = {}) {
    const create = document.getElementById("watchDashCreate");
    const limitTarget = document.getElementById("watchDashLimit");
    const limits = watchState.limits;
    if (create) {
      const label = guest ? "Log in to start watching" : "New watch";
      const text = create.querySelector(".wd-button-label");
      if (text) text.textContent = label;
      create.classList.toggle("is-primary", guest || !limits?.atLimit);
      create.classList.toggle("is-guest", guest);
    }
    if (limitTarget) {
      if (guest || !limits) {
        limitTarget.hidden = true;
        limitTarget.textContent = "";
      } else {
        ui().renderWatchLimit(limitTarget, limits);
      }
    }
  }

  // Counts that are zero are left out: absence is not news (J29).
  function renderSummary(container, watches) {
    const active = watches.filter(watch => watch.status === "active");
    const since = Date.now() - RECENT_MS;
    const movedRecently = watches.filter(watch => (watch.history || []).some(point =>
      point.trigger === "changed" && new Date(point.ts).getTime() >= since
    )).length;
    const reachedRecently = watches.filter(watch => watch.status === "resolved"
      && new Date(watch.resolution?.at || 0).getTime() >= since).length;
    const next = active.map(watch => watch.next_run_at).filter(Boolean).sort()[0];
    const bar = el("div", "wd-summary");
    const parts = [
      [active.length, "watching"],
      [movedRecently, "moved this week"],
      [reachedRecently, "reached this week"]
    ];
    parts.forEach(([value, label]) => {
      if (!value) return;
      const cell = el("span", "wd-summary-item");
      cell.appendChild(el("strong", "", String(value)));
      cell.appendChild(el("span", "", label));
      bar.appendChild(cell);
    });
    if (next) {
      const cell = el("span", "wd-summary-item is-next");
      const strong = el("strong");
      strong.title = F().dateTimeTitle(next);
      liveText(strong, now => F().nextCheck({ next_run_at: next }, now).text);
      cell.appendChild(strong);
      bar.appendChild(cell);
    }
    if (!bar.childElementCount) return null;
    container.appendChild(bar);
    return bar;
  }

  function sortActive(a, b) {
    const rank = watch => {
      if (page.fresh.has(watch.id)) return -1;
      const key = cardState(watch).key;
      return { moved: 0, rechecking: 1, held: 2, watching: 3, waiting: 4 }[key] ?? 5;
    };
    return rank(a) - rank(b)
      || String(a.next_run_at || "").localeCompare(String(b.next_run_at || ""));
  }

  const SECTION_META = {
    active: { title: "Watching" },
    paused: { title: "Paused" },
    resolved: { title: "Reached", note: "Reached on evidence. These don’t use a slot." }
  };

  function sectionOf(watch) {
    return watch.status === "active" ? "active" : watch.status === "resolved" ? "resolved" : "paused";
  }

  function renderSection(container, key, watches) {
    const meta = SECTION_META[key];
    const section = el("section", "wd-section");
    section.dataset.section = key;
    const head = el("div", "wd-section-head");
    head.appendChild(el("h2", "", meta.title));
    const count = el("span", "wd-count", String(watches.length));
    head.appendChild(count);
    if (meta.note) head.appendChild(el("span", "wd-section-note", meta.note));
    section.appendChild(head);
    const list = el("ul", "wd-list");
    watches.forEach(watch => list.appendChild(buildCard(watch).item));
    section.appendChild(list);
    page.sections.set(key, { section, list, count });
    if (!watches.length) section.hidden = true;
    container.appendChild(section);
    return section;
  }

  function updateSectionCounts() {
    page.sections.forEach(({ section, list, count }) => {
      const visible = Array.from(list.children).filter(item => !item.hidden).length;
      count.textContent = String(visible);
      // A section still folding away comes back with an Undo, from where
      // it stands; it never ends hidden around a card that came back.
      if (!visible && !section.hidden && !leaving(section)) collapse(section);
      else if (visible && (section.hidden || leaving(section))) expand(section);
    });
  }

  // ------------------------------------------------------------------
  // Delivery: Telegram connection and Morning Brief.
  // ------------------------------------------------------------------

  function renderBrief(container, brief) {
    const fields = F();
    const row = el("div", "wd-delivery-row");
    const timezone = ui().browserTimezone();
    row.innerHTML = `
      <div class="wd-delivery-copy">
        <label class="wd-delivery-title">
          <span class="switch wd-switch"><input type="checkbox" id="watchBriefToggle"><span class="slider"></span></span>
          Morning Brief
        </label>
        <p class="wd-field-hint">One daily email across all watches: what moved, what was reached, what runs next. No extra model runs.</p>
        <p class="watch-field-error" id="watchBriefError" role="alert" hidden></p>
      </div>
      <div class="wd-delivery-controls watch-field" id="watchBriefControls" hidden>
        <div class="watch-field-head"><span class="watch-field-status" aria-live="polite"></span></div>
        <div class="wd-brief-inputs">
          <input type="time" id="watchBriefTime" class="watch-input watch-time" aria-label="Brief delivery time">
          <select id="watchBriefMode" class="watch-select wd-select" aria-label="Brief frequency">
            <option value="always">Every morning</option>
            <option value="changes_only">Only when something happened</option>
          </select>
        </div>
      </div>`;
    container.appendChild(row);
    const toggle = row.querySelector("#watchBriefToggle");
    const controls = row.querySelector("#watchBriefControls");
    const time = row.querySelector("#watchBriefTime");
    const mode = row.querySelector("#watchBriefMode");
    const error = row.querySelector("#watchBriefError");
    toggle.checked = Boolean(brief.enabled);
    controls.hidden = !toggle.checked;
    time.value = brief.send_time || "07:00";
    mode.value = brief.mode || "always";
    let persisted = { enabled: toggle.checked, time: time.value, mode: mode.value };
    let saving = Promise.resolve();
    function save(changes, revert) {
      error.hidden = true;
      saving = saving.then(async () => {
        try {
          const data = await ui().api("PATCH", "/api/my/watch-brief", changes);
          const saved = data.brief || {};
          toggle.checked = Boolean(saved.enabled);
          controls.hidden = !saved.enabled;
          if (saved.send_time && document.activeElement !== time) time.value = saved.send_time;
          if (saved.mode) mode.value = saved.mode;
          persisted = { enabled: toggle.checked, time: saved.send_time || time.value, mode: mode.value };
          if (saved.enabled) fields.markSaved(controls);
        } catch (failure) {
          error.textContent = "Could not save the brief: " + errorText(failure);
          error.hidden = false;
          revert();
        }
      });
      return saving;
    }
    toggle.addEventListener("change", () => save(
      toggle.checked
        ? { enabled: true, send_time: time.value || "07:00", timezone: timezone, mode: mode.value }
        : { enabled: false },
      () => { toggle.checked = persisted.enabled; controls.hidden = !persisted.enabled; }
    ));
    // The time is saved once it is finished: leaving the field or Enter (J11).
    const commitTime = () => {
      if (!time.value || !toggle.checked || time.value === persisted.time) return;
      save({ send_time: time.value, timezone: timezone }, () => { time.value = persisted.time; });
    };
    time.addEventListener("blur", commitTime);
    time.addEventListener("keydown", event => {
      if (event.key === "Enter") {
        event.preventDefault();
        commitTime();
      }
    });
    mode.addEventListener("change", () => {
      if (!toggle.checked) return;
      save({ mode: mode.value }, () => { mode.value = persisted.mode; });
    });
  }

  function renderTelegram(container, state) {
    const row = el("div", "wd-delivery-row");
    row.id = "watchTelegramRow";
    const copy = el("div", "wd-delivery-copy");
    copy.appendChild(el("span", "wd-delivery-title", "Telegram"));
    const note = el("p", "wd-field-hint");
    copy.appendChild(note);
    const error = el("p", "watch-field-error");
    error.setAttribute("role", "alert");
    error.hidden = true;
    copy.appendChild(error);
    const actions = el("div", "wd-delivery-controls");
    row.append(copy, actions);
    const rerender = next => {
      const fresh = el("div");
      renderTelegram(fresh, next);
      row.replaceWith(fresh.firstElementChild);
      page.cards.forEach(entry => entry.panel?.sync?.(entry.watch));
    };
    const disconnect = () => ui().makeButton("Disconnect", "wd-button", async function () {
      if (state.connected) {
        const confirmed = await window.App.confirm({
          title: "Disconnect Telegram?",
          body: "Watches keep the setting but cannot deliver there until you reconnect.",
          confirmLabel: "Disconnect",
          danger: true,
        });
        if (!confirmed || !this.isConnected) return;
      }
      this.disabled = true;
      try {
        const data = await ui().api("DELETE", "/api/my/telegram", {});
        const next = data.telegram || { configured: state.configured, connected: false };
        watchState.setTelegram(next);
        page.telegram = next;
        rerender(next);
      } catch (failure) {
        this.disabled = false;
        error.textContent = "Disconnect failed: " + errorText(failure);
        error.hidden = false;
      }
    });
    if (!state.configured) {
      note.textContent = state.linked
        ? "Linked, but Telegram delivery is temporarily unavailable."
        : "Telegram delivery is not available on this deployment.";
      if (state.linked) actions.appendChild(disconnect());
    } else if (state.connected) {
      const identity = state.telegram_username ? "@" + state.telegram_username : (state.telegram_first_name || "your account");
      note.textContent = `Connected to ${identity}. Turn it on per watch under Settings.`;
      actions.appendChild(ui().makeButton("Send test", "wd-button", async function () {
        this.disabled = true;
        error.hidden = true;
        try {
          await ui().api("POST", "/api/my/telegram/test", {});
          note.textContent = `Connected to ${identity}. A test message is on its way.`;
        } catch (failure) {
          error.textContent = "Test failed: " + errorText(failure);
          error.hidden = false;
        } finally { this.disabled = false; }
      }));
      actions.appendChild(disconnect());
    } else {
      const idle = "Get the same change log as a chat message. Connect once, then choose it per watch.";
      note.textContent = idle;
      const connect = ui().makeButton("Connect Telegram", "wd-button", () => {
        error.hidden = true;
        ui().connectTelegram(next => {
          watchState.setTelegram(next);
          page.telegram = next;
        });
      });
      const cancel = ui().makeButton("Cancel", "wd-link", () => ui().cancelTelegramPairing());
      actions.append(connect, cancel);
      const sync = (status, detail) => {
        if (!row.isConnected) { unsubscribe(); return; }
        const waiting = status === "waiting";
        connect.disabled = waiting;
        connect.textContent = waiting ? "Waiting for Telegram…" : "Connect Telegram";
        cancel.hidden = !waiting;
        note.textContent = waiting ? "Press Start in Telegram. This updates by itself." : idle;
        if (status === "connected") rerender(detail);
        if (status === "expired") {
          error.textContent = "The link expired. Connect again when you are ready.";
          error.hidden = false;
        }
        if (status === "failed") {
          error.textContent = "Telegram couldn’t be connected. " + errorText(detail, "Try again.");
          error.hidden = false;
        }
      };
      const unsubscribe = ui().onTelegramStatus(sync);
      sync(ui().telegramStatus());
    }
    container.appendChild(row);
  }

  function renderDelivery(container, telegram, brief) {
    const section = el("section", "wd-section wd-delivery");
    const head = el("div", "wd-section-head");
    head.appendChild(el("h2", "", "Delivery"));
    head.appendChild(el("span", "wd-section-note", "Every message says what changed, why, with the source, and what held."));
    section.appendChild(head);
    const box = el("div", "wd-delivery-box");
    renderTelegram(box, telegram);
    renderBrief(box, brief);
    section.appendChild(box);
    container.appendChild(section);
  }

  // ------------------------------------------------------------------
  // Render: built once per visit, then changed in place.
  // ------------------------------------------------------------------

  let renderToken = 0;

  function layoutSignature(watches) {
    return watches.map(watch => sectionOf(watch) + ":" + watch.id).sort().join("|");
  }

  function build(watches) {
    const body = document.getElementById("watchDashBody");
    const fromSkeleton = Boolean(body.querySelector(".wd-skeleton")) || !page.built;
    page.cards.clear();
    page.sections.clear();
    const fragment = document.createDocumentFragment();
    if (!watches.length) {
      renderEmpty(fragment);
    } else {
      renderSummary(fragment, watches);
      const active = watches.filter(watch => sectionOf(watch) === "active").sort(sortActive);
      const paused = watches.filter(watch => sectionOf(watch) === "paused")
        .sort((a, b) => (a.status === "paused_error" ? 0 : 1) - (b.status === "paused_error" ? 0 : 1));
      const reached = watches.filter(watch => sectionOf(watch) === "resolved")
        .sort((a, b) => String(b.resolution?.at || "").localeCompare(String(a.resolution?.at || "")));
      renderSection(fragment, "active", active);
      renderSection(fragment, "paused", paused);
      renderSection(fragment, "resolved", reached);
      renderDelivery(fragment, page.telegram || {}, page.brief || {});
      renderDifferences(fragment, { open: false });
    }
    body.replaceChildren(fragment);
    if (fromSkeleton && !reducedMotion()) {
      body.classList.remove("is-arriving");
      void body.offsetWidth;
      body.classList.add("is-arriving");
    }
    page.built = true;
    page.signature = layoutSignature(watches);
  }

  // A later answer for a built page: cards change in place, a new watch
  // joins at the top of its section, a vanished one folds away. A card
  // changed here after the list was asked for keeps its newer state.
  function reconcile(watches, requestedAt = 0) {
    const body = document.getElementById("watchDashBody");
    if (!page.built || !body || body.querySelector(".wd-empty") || !watches.length) {
      build(watches);
      return;
    }
    const ids = new Set(watches.map(watch => watch.id));
    watches.forEach(watch => {
      const entry = page.cards.get(watch.id);
      if (entry && entry.localAt >= requestedAt) return;
      if (entry) updateCard(watch.id, watch, { fromList: true });
      else insertCard(watch);
    });
    page.cards.forEach((entry, id) => {
      if (ids.has(id) || page.pendingDeletes.has(id)) return;
      page.cards.delete(id);
      collapse(entry.item, () => { entry.item.remove(); updateSectionCounts(); });
    });
    const summary = body.querySelector(".wd-summary");
    const fresh = document.createDocumentFragment();
    const next = renderSummary(fresh, watches);
    if (summary && next) summary.replaceWith(next);
    else if (summary) summary.remove();
    else if (next) body.prepend(next);
    updateSectionCounts();
  }

  function insertCard(watch, { highlight = false } = {}) {
    const key = sectionOf(watch);
    const target = page.sections.get(key);
    if (!target) return null;
    const entry = buildCard(watch);
    target.list.prepend(entry.item);
    if (target.section.hidden) expand(target.section);
    else {
      entry.item.hidden = true;
      expand(entry.item);
    }
    if (highlight) markCard(entry);
    updateSectionCounts();
    return entry;
  }

  function markCard(entry) {
    entry.item.classList.remove("is-highlight");
    void entry.item.offsetWidth;
    entry.item.classList.add("is-highlight");
    setTimeout(() => entry.item.classList.remove("is-highlight"), 2200);
  }

  // Bring a watch into view and mark it (from "Open watch", a Watch button
  // or the nudge). Scrolling only to what the reader asked for.
  function focusWatch(id) {
    const entry = page.cards.get(id);
    if (!entry) return;
    entry.item.scrollIntoView({ block: "center", behavior: reducedMotion() ? "auto" : "smooth" });
    markCard(entry);
  }

  // The watch just created, at the top of the list behind the dialog (J15).
  function addCreated(watch) {
    if (!watch?.id) return;
    page.fresh.add(watch.id);
    const list = Array.isArray(watchState.watches) ? watchState.watches.slice() : [];
    if (!list.some(item => item.id === watch.id)) list.unshift(watch);
    const body = document.getElementById("watchDashBody");
    if (!page.built || !body || body.querySelector(".wd-empty")) {
      build(list);
    } else if (!page.cards.has(watch.id)) {
      insertCard(watch, { highlight: true });
    }
    const entry = page.cards.get(watch.id);
    if (entry) {
      const rect = entry.item.getBoundingClientRect();
      if (rect.top < 0 || rect.top > window.innerHeight - 80) focusWatch(watch.id);
      else markCard(entry);
    }
    refresh().catch(() => {});
  }

  function refreshLimits() {
    ui().api("GET", "/api/my/watches").then(data => {
      ui().receiveWatchList(data);
      syncHead();
    }).catch(() => {});
  }

  // What the page shows, loaded once however many ways ask for it at the
  // same time: a direct /app/watches opening renders from the route and
  // again from the auth state, and the account's list request on sign-in
  // runs alongside (review 2: three list loads, two of brief and Telegram).
  // A render that comes while a load for the same account is on its way
  // takes that one; the list itself is the shared request of watch.js,
  // which also takes it in (receiveWatchList).
  let loading = null;
  function load() {
    const uid = window.auth?.currentUser?.uid || null;
    const epoch = watchState.sessionEpoch;
    if (loading && loading.uid === uid && loading.epoch === epoch) return loading.promise;
    const promise = Promise.all([
      ui().requestWatchList(),
      ui().api("GET", "/api/my/watch-brief").catch(() => ({ brief: page.brief || {} })),
      ui().api("GET", "/api/my/telegram").catch(() => ({ telegram: page.telegram || {} }))
    ]).then(([watchData, briefData, telegramData]) => ({ watchData, briefData, telegramData }));
    const entry = { promise, uid, epoch };
    loading = entry;
    const done = () => { if (loading === entry) loading = null; };
    promise.then(done, done);
    return promise;
  }

  function isCurrentRender(token, epoch, uid) {
    return token === renderToken
      && epoch === watchState.sessionEpoch
      && uid
      && window.auth?.currentUser?.uid === uid
      && ui().onWatchPagePath();
  }

  // The page as it is now. A first visit shows the skeleton until the list
  // is in; a later visit (`visit: true`, watch.js on opening the page) keeps
  // what it shows and sorts anew only when the list changed; within a visit
  // cards only change in place. A failed load never wipes what is there (J6).
  async function render({ visit = false } = {}) {
    const body = document.getElementById("watchDashBody");
    if (!body) return;
    const token = ++renderToken;
    const epoch = watchState.sessionEpoch;
    const uid = window.auth?.currentUser?.uid || null;
    syncHead();
    if (!page.built && !body.querySelector(".wd-skeleton")) renderSkeleton();
    body.setAttribute("aria-busy", "true");
    const requestedAt = Date.now();
    let data;
    try {
      data = await load();
    } catch (error) {
      if (!isCurrentRender(token, epoch, uid)) return;
      body.removeAttribute("aria-busy");
      body.querySelector(".wd-alert")?.remove();
      const bar = alertBar("Couldn’t load your watches. Check your connection.", () => render());
      if (page.built) body.prepend(bar);
      else body.replaceChildren(bar);
      return;
    }
    if (!isCurrentRender(token, epoch, uid)) return;
    body.removeAttribute("aria-busy");
    body.querySelector(".wd-alert")?.remove();
    const watches = data.watchData.watches || [];
    page.brief = data.briefData.brief || {};
    page.telegram = data.telegramData.telegram || { configured: false, connected: false };
    watchState.setTelegram(page.telegram);
    page.lastLoad = Date.now();
    syncHead();
    // Same watches in the same sections, or the same visit: change in
    // place; otherwise this visit sorts the page anew.
    if (page.built && !body.querySelector(".wd-skeleton")
        && (!visit || layoutSignature(watches) === page.signature)) {
      reconcile(watches, requestedAt);
    } else {
      build(watches);
    }
    page.refreshStep = 0;
    planRefresh();
  }

  // A silent refresh of the list only, keeping the page as it stands.
  async function refresh() {
    if (!page.built || !window.auth?.currentUser) return;
    const token = renderToken;
    const epoch = watchState.sessionEpoch;
    const uid = window.auth.currentUser.uid;
    const requestedAt = Date.now();
    let data;
    try {
      data = await ui().api("GET", "/api/my/watches");
    } catch (_) {
      return;
    }
    if (!isCurrentRender(token, epoch, uid)) return;
    ui().receiveWatchList(data);
    page.lastLoad = Date.now();
    syncHead();
    reconcile(data.watches || [], requestedAt);
    planRefresh();
  }

  function reset() {
    renderToken += 1;
    // An account change drops a pending Undo without doing it: nothing of
    // the old account's page is sent with the next one.
    dashToast?.cancel();
    dashToast = null;
    page.cards.clear();
    page.sections.clear();
    page.fresh.clear();
    page.pendingDeletes.clear();
    page.built = false;
    page.signature = "";
    clearTimeout(page.refreshTimer);
    page.refreshTimer = null;
    const body = document.getElementById("watchDashBody");
    if (body) body.replaceChildren();
  }

  window.App.watchDashboard = {
    render: render,
    refresh: refresh,
    cardState: cardState,
    renderGuest: renderGuest,
    renderSkeleton: renderSkeleton,
    focusWatch: focusWatch,
    addCreated: addCreated,
    showUndoToast: showUndoToast,
    commitPending: commitPending,
    reset: reset
  };
})();
