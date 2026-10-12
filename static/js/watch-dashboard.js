// Watch dashboard (/app/watches). Classic script; renders into #watchDashBody.
// Contract: window.App.watchDashboard.{render, cardState}. Helpers shared with
// the create dialog come from window.App.watchUi (watch.js). What a check
// means is decided once on the server (drift_signal, docs/watch-evidence-
// model.md) and arrives as `signal`; this file only presents it.
(function () {
  const ui = () => window.App.watchUi;
  const watchState = window.App.watchState;
  const EXPLAINER_STORAGE_KEY = "consensio.watchExplainer.open.v1";
  const RECENT_MS = 7 * 24 * 3600 * 1000;

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function formatDateTime(iso) {
    if (!iso) return "";
    const date = new Date(iso);
    if (isNaN(date.getTime())) return "";
    try {
      // English like the rest of the page; the browser locale put "7. Aug."
      // into English sentences.
      return new Intl.DateTimeFormat("en-US", {
        weekday: "short", month: "short", day: "numeric",
        hour: "2-digit", minute: "2-digit"
      }).format(date);
    } catch (_) {
      return date.toLocaleString();
    }
  }

  function formatDay(iso) {
    if (!iso) return "";
    const date = new Date(iso);
    if (isNaN(date.getTime())) return "";
    try {
      return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric" }).format(date);
    } catch (_) {
      return date.toDateString();
    }
  }

  function relativeTime(iso) {
    if (!iso) return "";
    const then = new Date(iso).getTime();
    if (isNaN(then)) return "";
    const diffMs = Date.now() - then;
    const future = diffMs < 0;
    const minutes = Math.round(Math.abs(diffMs) / 60000);
    const wrap = value => future ? "in " + value : value + " ago";
    if (minutes < 1) return future ? "now" : "just now";
    if (minutes < 60) return wrap(minutes + " min");
    const hours = Math.round(minutes / 60);
    if (hours < 24) return wrap(hours + " h");
    const days = Math.round(hours / 24);
    return wrap(days + (days === 1 ? " day" : " days"));
  }

  function schedule(watch) {
    const text = ui().formatWatchSchedule(watch);
    return text.charAt(0).toUpperCase() + text.slice(1);
  }

  // The footer line names the time zone only when it is not the viewer's own.
  function shortSchedule(watch) {
    const text = schedule(watch);
    let own = "";
    try { own = Intl.DateTimeFormat().resolvedOptions().timeZone || ""; } catch (_) { /* no Intl */ }
    return own && watch.timezone === own ? text.replace(" (" + own + ")", "") : text;
  }

  function hostOf(url) {
    try { return new URL(url).hostname.replace(/^www\./, ""); } catch (_) { return ""; }
  }

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
        key: "resolved", tone: "resolved", label: "Resolved",
        when: resolution.at || watch.last_run_at,
        headline: resolution.reason || "The goal this watch was waiting for is met.",
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
        ? `Last moved ${formatDay(move.ts)}: ${move.change_summary || "the answer changed on evidence."}`
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
  // already says how many checks held.
  const RECORD_MIN_CHECKS = 3;

  function buildRecord(watch) {
    const history = (Array.isArray(watch.history) ? watch.history : []).slice(-16);
    if (history.length < RECORD_MIN_CHECKS) return null;
    const strip = el("div", "wd-record");
    const moved = history.filter(point => point.signal === "moved").length;
    const held = history.filter(point => point.signal === "held").length;
    strip.setAttribute("role", "img");
    strip.setAttribute("aria-label",
      `${history.length} recent check${history.length === 1 ? "" : "s"}: ${moved} moved, ${held} held`);
    history.forEach((point, index) => {
      const tick = el("span", "wd-tick is-" + (point.signal || (point.trigger === "changed" ? "moved" : "stable")));
      if (index === history.length - 1 && watch.status === "resolved") tick.classList.add("is-resolved");
      tick.title = `${formatDay(point.ts)} · ${SIGNAL_LABELS[point.signal] || "Checked"}`;
      strip.appendChild(tick);
    });
    return strip;
  }

  function buildSources(sources) {
    const items = (sources || []).filter(item => item && /^https?:\/\//.test(item.url || "")).slice(0, 3);
    if (!items.length) return null;
    const list = el("ul", "wd-sources");
    items.forEach(item => {
      const li = el("li");
      const link = el("a");
      link.href = item.url;
      link.target = "_blank";
      link.rel = "noopener";
      link.appendChild(el("span", "wd-source-host", hostOf(item.url)));
      link.appendChild(el("span", "wd-source-title", item.title || item.url));
      li.appendChild(link);
      list.appendChild(li);
    });
    return list;
  }

  // What the watch is about, so it is recognised at a glance:
  // services/watch_images.py picks a product shot, an article photo or the
  // logos of the sites the question is about; we only show it. The × removes
  // it for good. Without one, the card shows the watch's symbol
  // (services/watch_symbols.py, picked once by the cheap Judge) instead.
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

  function buildImage(watch) {
    const image = watch.image;
    if (!image || !IMAGE_PATH.test(image.url || "")) return buildSymbol(watch);
    // A product shot is shown whole on white; an article photo fills the
    // tile; logos come as rounded tiles of their own and need no frame.
    const kind = IMAGE_KINDS.includes(image.kind) ? image.kind : "item";
    const figure = el("figure", "wd-image is-" + kind);
    const drop = () => figure.replaceWith(buildSymbol(watch));
    const host = image.source_host || hostOf(image.source_url);
    const frame = el(/^https?:\/\//.test(image.source_url || "") ? "a" : "span", "wd-image-frame");
    const noun = kind === "logo" ? "Logo" : "Image";
    if (frame.tagName === "A") {
      frame.href = image.source_url;
      frame.target = "_blank";
      frame.rel = "noopener noreferrer";
      frame.setAttribute("aria-label", host ? noun + " from " + host : noun + " source");
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
    const remove = ui().makeButton("", "wd-image-remove", async function () {
      this.disabled = true;
      try {
        await ui().api("DELETE", "/api/watch/" + encodeURIComponent(watch.id) + "/image");
        watch.image = null;
        drop();
      } catch (error) {
        this.disabled = false;
        ui().popup("Could not remove the " + noun.toLowerCase() + ": " + error.message);
      }
    });
    remove.setAttribute("aria-label", "Remove " + noun.toLowerCase());
    remove.title = "Remove " + noun.toLowerCase();
    remove.innerHTML = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><path d="M4.5 4.5l7 7M11.5 4.5l-7 7"/></svg>';
    figure.appendChild(remove);
    return figure;
  }

  function separator() {
    const dot = el("span", "wd-sep", "·");
    dot.setAttribute("aria-hidden", "true");
    return dot;
  }

  // One quiet line of parts ("Next check in 21 h · Weekly on … · Public
  // page"), joined by real separators so a wrap breaks after a dot.
  function scheduleBlock(watch) {
    const side = el("div", "wd-item-side");
    const parts = [];
    const part = (...nodes) => {
      const wrap = el("span", "wd-side-part");
      wrap.append(...nodes);
      parts.push(wrap);
      return wrap;
    };
    if (watch.status === "active" && watch.next_run_at) {
      const strong = el("strong", "wd-side-value", relativeTime(watch.next_run_at));
      strong.title = formatDateTime(watch.next_run_at);
      part(el("span", "wd-side-label", "Next check"), " ", strong);
      part(el("span", "wd-side-note", shortSchedule(watch))).title = schedule(watch);
    } else if (watch.status === "resolved") {
      part(el("span", "wd-side-label", "Closed"), " ",
        el("strong", "wd-side-value", formatDay(watch.resolution?.at) || "Done"));
      part(el("span", "wd-side-note", "slot freed"));
    } else {
      part(el("strong", "wd-side-value", "Paused"));
      part(el("span", "wd-side-note", shortSchedule(watch))).title = schedule(watch);
    }
    const probe = watch.last_probe;
    if (watch.status === "active" && probe && probe.at) {
      part(el("span", "wd-side-probe", probe.outcome === "new_evidence"
        ? `Daily scan found news ${relativeTime(probe.at)}`
        : probe.outcome === "failed"
          ? "Daily scan unavailable"
          : `Daily scan: nothing new (${relativeTime(probe.at)})`));
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
  // One watch.
  // ------------------------------------------------------------------

  function renderItem(watch, telegram) {
    const state = cardState(watch);
    const item = el("li", "wd-item is-" + state.tone);
    item.dataset.state = state.key;

    const main = el("div", "wd-item-main");
    // The picture (or symbol) floats top right and the text flows around it,
    // so a card with one is no taller and its question no narrower than needed.
    main.appendChild(buildImage(watch));
    item.classList.add("has-image");
    const status = el("div", "wd-status");
    status.appendChild(el("span", "wd-dot"));
    status.appendChild(el("span", "wd-status-label", state.label));
    // A pending first check's time is the next check, which the side column
    // already shows; saying it twice only crowds the line.
    if (state.when && state.key !== "waiting") {
      // Say what the time is: the last check, unless the label already is
      // the event ("Moved", "Resolved").
      const prefix = state.key === "watching" || state.key === "held" ? "checked "
        : state.key === "paused" ? "last check " : "";
      const time = el("time", "wd-status-time", prefix + relativeTime(state.when));
      time.dateTime = state.when;
      time.title = formatDateTime(state.when);
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

    main.appendChild(el("p", "wd-headline", state.headline));
    if (state.held) main.appendChild(el("p", "wd-held", "Held: " + state.held));
    const sources = buildSources(state.sources);
    if (sources) main.appendChild(sources);
    const record = buildRecord(watch);
    if (record) main.appendChild(record);

    item.appendChild(main);
    item.appendChild(scheduleBlock(watch));

    const actions = el("div", "wd-actions");
    const open = el("a", "wd-action", "Open page");
    open.href = watch.share_path || "#";
    open.target = "_blank";
    open.rel = "noopener";
    actions.appendChild(open);
    const settings = renderSettings(watch, telegram);
    const toggle = ui().makeButton("Settings", "wd-action wd-action-toggle", () => {
      settings.hidden = !settings.hidden;
      toggle.setAttribute("aria-expanded", String(!settings.hidden));
      item.classList.toggle("is-open", !settings.hidden);
    });
    toggle.setAttribute("aria-expanded", "false");
    if (watch.status === "resolved") {
      actions.appendChild(ui().makeButton("Watch for something new", "wd-action is-strong", () => {
        settings.hidden = false;
        toggle.setAttribute("aria-expanded", "true");
        item.classList.add("is-open");
        settings.querySelector(".wd-goal-input")?.focus();
      }));
    }
    actions.appendChild(toggle);
    item.appendChild(actions);
    item.appendChild(settings);
    return item;
  }

  function patchWatch(watch, changes) {
    return ui().api("PATCH", "/api/watch/" + encodeURIComponent(watch.id), changes);
  }

  function field(labelText, control, hint) {
    const wrap = el("label", "wd-field");
    wrap.appendChild(el("span", "wd-field-label", labelText));
    wrap.appendChild(control);
    if (hint) wrap.appendChild(el("span", "wd-field-hint", hint));
    return wrap;
  }

  function renderGoalEditor(watch) {
    const box = el("div", "wd-goal-editor");
    const resolved = watch.status === "resolved";
    box.appendChild(el("span", "wd-field-label", resolved ? "What are you waiting for next?" : "What are you waiting for?"));
    const input = el("textarea", "wd-goal-input");
    input.rows = 2;
    input.maxLength = 500;
    input.placeholder = "Example: An official release date is announced";
    input.value = resolved ? "" : (watch.condition || "");
    box.appendChild(input);
    box.appendChild(el("span", "wd-field-hint", resolved
      ? "The watch reopens with this goal. Leave it empty to watch for any change on evidence."
      : "Checked on every run. When a source confirms it, the watch closes and tells you."));
    const row = el("div", "wd-goal-actions");
    const save = ui().makeButton(resolved ? "Keep watching" : "Save goal", "wd-button is-primary", async () => {
      const goal = input.value.replace(/\s+/g, " ").trim();
      const changes = { condition: goal };
      if (resolved) changes.status = "active";
      if (!goal && watch.email_mode === "condition") changes.email_mode = "changes_only";
      save.disabled = true;
      try {
        await patchWatch(watch, changes);
        ui().popup(resolved ? "Watching again." : (goal ? "Goal saved." : "Goal cleared."));
        render();
      } catch (error) {
        save.disabled = false;
        if (error.status === 429) window.App?.showProFeatureModal?.("More Consensus Watches");
        ui().popup("Update failed: " + error.message);
      }
    });
    row.appendChild(save);
    if (!resolved && watch.condition) {
      row.appendChild(ui().makeButton("Clear goal", "wd-button", async function () {
        this.disabled = true;
        try {
          await patchWatch(watch, {
            condition: "",
            ...(watch.email_mode === "condition" ? { email_mode: "changes_only" } : {})
          });
          ui().popup("Goal cleared.");
          render();
        } catch (error) {
          this.disabled = false;
          ui().popup("Update failed: " + error.message);
        }
      }));
    }
    box.appendChild(row);
    return box;
  }

  function renderSettings(watch, telegram) {
    const panel = el("div", "wd-settings");
    panel.hidden = true;
    panel.appendChild(renderGoalEditor(watch));
    if (watch.status === "resolved") return panel;

    const grid = el("div", "wd-settings-grid");
    const interval = el("select", "wd-select");
    interval.innerHTML = ui().intervalOptions(watch.interval);
    const weekday = el("select", "wd-select");
    weekday.innerHTML = ui().weekdayOptions(watch.run_weekday);
    const weekdayField = field("Run day", weekday);
    const syncWeekday = () => { weekdayField.hidden = interval.value !== "weekly"; };
    syncWeekday();
    interval.addEventListener("change", async () => {
      const previous = watch.interval;
      interval.disabled = weekday.disabled = true;
      try {
        const data = await patchWatch(watch, {
          interval: interval.value,
          run_weekday: interval.value === "weekly" ? weekday.value : ""
        });
        Object.assign(watch, data.watch);
        syncWeekday();
        ui().popup("Schedule updated.");
      } catch (error) {
        interval.value = previous;
        syncWeekday();
        ui().popup("Update failed: " + error.message);
      } finally { interval.disabled = weekday.disabled = false; }
    });
    weekday.addEventListener("change", async () => {
      const previous = watch.run_weekday || ui().browserWeekday();
      weekday.disabled = true;
      try {
        const data = await patchWatch(watch, { run_weekday: weekday.value });
        Object.assign(watch, data.watch);
        ui().popup("Run day updated.");
      } catch (error) {
        weekday.value = previous;
        ui().popup("Update failed: " + error.message);
      } finally { weekday.disabled = false; }
    });
    const time = el("input", "wd-input");
    time.type = "time";
    time.value = watch.run_time || "";
    time.addEventListener("change", async () => {
      if (!time.value) return;
      const previous = watch.run_time || "";
      time.disabled = true;
      try {
        const data = await patchWatch(watch, { run_time: time.value, timezone: ui().browserTimezone() });
        Object.assign(watch, data.watch);
        ui().popup("Run time updated.");
      } catch (error) {
        time.value = previous;
        ui().popup("Update failed: " + error.message);
      } finally { time.disabled = false; }
    });
    const alerts = el("select", "wd-select");
    alerts.innerHTML = ui().emailModeOptions(watch.email_mode, Boolean(watch.condition));
    alerts.addEventListener("change", async () => {
      const previous = watch.email_mode || "changes_only";
      alerts.disabled = true;
      try {
        const data = await patchWatch(watch, { email_mode: alerts.value });
        Object.assign(watch, data.watch);
        ui().popup("Alert rule updated.");
      } catch (error) {
        alerts.value = previous;
        ui().popup("Update failed: " + error.message);
      } finally { alerts.disabled = false; }
    });

    const channels = el("div", "wd-channels");
    const email = el("input");
    email.type = "checkbox";
    email.checked = watch.email_enabled !== false;
    const tg = el("input");
    tg.type = "checkbox";
    tg.checked = watch.telegram_enabled === true;
    tg.disabled = !telegram?.connected;
    const emailLabel = el("label", "wd-check");
    emailLabel.append(email, document.createTextNode("E-mail"));
    const tgLabel = el("label", "wd-check");
    tgLabel.title = telegram?.connected ? "" : "Connect Telegram under Delivery below.";
    tgLabel.append(tg, document.createTextNode("Telegram"));
    channels.append(emailLabel, tgLabel);
    async function saveChannel(input, name) {
      const previous = !input.checked;
      if (!email.checked && !tg.checked) {
        input.checked = previous;
        ui().popup("Keep at least one delivery channel on.");
        return;
      }
      email.disabled = tg.disabled = true;
      try {
        const data = await patchWatch(watch, { [name]: input.checked });
        Object.assign(watch, data.watch);
        ui().popup("Delivery updated.");
      } catch (error) {
        input.checked = previous;
        ui().popup("Update failed: " + error.message);
      } finally {
        email.disabled = false;
        tg.disabled = !telegram?.connected;
      }
    }
    email.addEventListener("change", () => saveChannel(email, "email_enabled"));
    tg.addEventListener("change", () => saveChannel(tg, "telegram_enabled"));

    grid.append(
      field("Interval", interval),
      weekdayField,
      field("Run time", time, watch.timezone || ui().browserTimezone()),
      field("Alerts", alerts),
      field("Delivery", channels)
    );
    panel.appendChild(grid);
    if (watch.visibility !== "private" && watch.share_id) panel.appendChild(renderListing(watch));

    const footer = el("div", "wd-settings-footer");
    const active = watch.status === "active";
    const pause = ui().makeButton(active ? "Pause" : "Resume", "wd-button", async () => {
      pause.disabled = true;
      try {
        await patchWatch(watch, { status: active ? "paused" : "active" });
        render();
      } catch (error) {
        pause.disabled = false;
        if (error.status === 429) window.App?.showProFeatureModal?.("More Consensus Watches");
        ui().popup("Update failed: " + error.message);
      }
    });
    footer.appendChild(pause);
    footer.appendChild(ui().makeButton("Delete", "wd-button is-danger", async function () {
      const message = watch.awaiting_first_run
        ? "Delete this watch? No check has run yet, so its empty page is removed too."
        : "Delete this watch? Its history page stays available with its current visibility.";
      if (!confirm(message)) return;
      this.disabled = true;
      try {
        await ui().api("DELETE", "/api/watch/" + encodeURIComponent(watch.id));
        render();
      } catch (error) {
        this.disabled = false;
        ui().popup("Delete failed: " + error.message);
      }
    }));
    panel.appendChild(footer);
    return panel;
  }

  // "Google listing": the owner nominates a public page for the search
  // index. It only sets a request flag; a human reviews before anything is
  // listed.
  function renderListing(watch) {
    const block = el("div", "wd-listing");
    block.appendChild(el("span", "wd-field-label", "Google listing"));
    const note = el("p", "wd-field-hint");
    block.appendChild(note);
    async function request(button, want) {
      button.disabled = true;
      try {
        await ui().api("POST", "/api/share/" + encodeURIComponent(watch.share_id) + "/indexing-request", { want: want });
        window.App?.trackAppEvent?.("app_watch_listing_request", { want: want });
        ui().popup(want
          ? "Nominated. A human reviews every page before it appears on Google."
          : "Listing request withdrawn.");
        render();
      } catch (error) {
        button.disabled = false;
        ui().popup("Request failed: " + error.message);
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

  // ------------------------------------------------------------------
  // Page sections.
  // ------------------------------------------------------------------

  // The difference to a scheduled chatbot prompt, said once and plainly.
  const DIFFERENCES = [
    {
      title: "Several model families, cross-checked",
      body: "Each check asks independent AI model families and cross-checks their answers. One model's slip is not your alert."
    },
    {
      title: "Only evidence moves it",
      body: "A search that misses a source is not a retraction. You hear about a change when a source backs it, or when a second check confirms a new reading."
    },
    {
      title: "It knows when it is done",
      body: "Tell it what you are waiting for. When a source confirms it, the watch closes and shows you the proof."
    }
  ];

  const COMPARISON = [
    ["One model answers again", "Several model families answer independently"],
    ["A new answer every time; you compare", "A message only when the evidence moves, with the source"],
    ["One missed search hit changes the answer", "A missing source never counts as counter-evidence"],
    ["Runs until you switch it off", "Closes when what you wait for happens"]
  ];

  function renderDifferences(container, { open, withTable }) {
    const box = el("details", "wd-explainer");
    let stored = null;
    try { stored = window.localStorage.getItem(EXPLAINER_STORAGE_KEY); } catch (_) {}
    box.open = stored === null ? open : stored === "true";
    const summary = el("summary");
    summary.appendChild(el("span", "wd-explainer-title", "Why a Watch, not a scheduled prompt"));
    summary.appendChild(el("span", "wd-explainer-hint", "How it works"));
    box.appendChild(summary);
    box.addEventListener("toggle", () => {
      try { window.localStorage.setItem(EXPLAINER_STORAGE_KEY, String(box.open)); } catch (_) {}
    });
    const grid = el("div", "wd-explainer-grid");
    DIFFERENCES.forEach((item, index) => {
      const cell = el("div", "wd-explainer-item");
      cell.appendChild(el("span", "wd-explainer-index", String(index + 1)));
      cell.appendChild(el("strong", "", item.title));
      cell.appendChild(el("p", "", item.body));
      grid.appendChild(cell);
    });
    box.appendChild(grid);
    if (withTable) {
      const table = el("table", "wd-compare");
      table.innerHTML = "<thead><tr><th scope=\"col\">A scheduled prompt</th><th scope=\"col\">A consens.io Watch</th></tr></thead>";
      const body = el("tbody");
      COMPARISON.forEach(([left, right]) => {
        const row = el("tr");
        row.appendChild(el("td", "", left));
        row.appendChild(el("td", "", right));
        body.appendChild(row);
      });
      table.appendChild(body);
      box.appendChild(table);
    }
    container.appendChild(box);
  }

  const EXAMPLES = [
    { question: "When will OpenAI release its next flagship model?", goal: "The model is officially released" },
    { question: "Has the EU published final guidance for general-purpose AI models?", goal: "The final guidance is published" },
    { question: "Is the new iPhone available in Germany yet?", goal: "It is on sale in Germany" }
  ];

  function renderEmpty(container) {
    const hero = el("section", "wd-empty");
    hero.appendChild(el("span", "wd-eyebrow", "Consensus Watch"));
    hero.appendChild(el("h2", "wd-empty-title", "Tell us what you are waiting for."));
    hero.appendChild(el("p", "wd-empty-lead",
      "A Watch re-asks your question on a schedule, checks it across AI model families, writes only when a source moves the answer, and closes when the thing you wait for happens."));
    const actions = el("div", "wd-empty-actions");
    actions.appendChild(ui().makeButton("Create your first Watch", "wd-button is-primary is-large", () => {
      ui().openWatchDialog("create");
    }));
    hero.appendChild(actions);
    const examples = el("div", "wd-examples");
    examples.appendChild(el("span", "wd-field-label", "Or start from an example"));
    const list = el("div", "wd-example-list");
    EXAMPLES.forEach(example => {
      const button = ui().makeButton("", "wd-example", () => {
        ui().openWatchDialog("create", { question: example.question, goal: example.goal });
      });
      button.appendChild(el("strong", "", example.question));
      button.appendChild(el("span", "", "Waiting for: " + example.goal));
      list.appendChild(button);
    });
    examples.appendChild(list);
    hero.appendChild(examples);
    container.appendChild(hero);
    renderDifferences(container, { open: true, withTable: true });
  }

  function renderSummary(container, watches) {
    const active = watches.filter(watch => watch.status === "active");
    const since = Date.now() - RECENT_MS;
    const movedRecently = watches.filter(watch => (watch.history || []).some(point =>
      point.trigger === "changed" && new Date(point.ts).getTime() >= since
    )).length;
    const resolvedRecently = watches.filter(watch => watch.status === "resolved"
      && new Date(watch.resolution?.at || 0).getTime() >= since).length;
    const next = active.map(watch => watch.next_run_at).filter(Boolean).sort()[0];
    const bar = el("div", "wd-summary");
    const parts = [
      [String(active.length), active.length === 1 ? "watching" : "watching"],
      [String(movedRecently), "moved this week"],
      [String(resolvedRecently), "resolved this week"]
    ];
    parts.forEach(([value, label]) => {
      const cell = el("span", "wd-summary-item");
      cell.appendChild(el("strong", "", value));
      cell.appendChild(el("span", "", label));
      bar.appendChild(cell);
    });
    if (next) {
      const cell = el("span", "wd-summary-item is-next");
      cell.appendChild(el("span", "", "Next check"));
      const strong = el("strong", "", relativeTime(next));
      strong.title = formatDateTime(next);
      cell.appendChild(strong);
      bar.appendChild(cell);
    }
    container.appendChild(bar);
  }

  function sortActive(a, b) {
    const rank = watch => {
      const key = cardState(watch).key;
      return { moved: 0, rechecking: 1, held: 2, watching: 3, waiting: 4 }[key] ?? 5;
    };
    return rank(a) - rank(b)
      || String(a.next_run_at || "").localeCompare(String(b.next_run_at || ""));
  }

  function renderSection(container, title, watches, telegram, note) {
    if (!watches.length) return;
    const section = el("section", "wd-section");
    const head = el("div", "wd-section-head");
    head.appendChild(el("h2", "", title));
    head.appendChild(el("span", "wd-count", String(watches.length)));
    if (note) head.appendChild(el("span", "wd-section-note", note));
    section.appendChild(head);
    const list = el("ul", "wd-list");
    watches.forEach(watch => list.appendChild(renderItem(watch, telegram)));
    section.appendChild(list);
    container.appendChild(section);
  }

  // ------------------------------------------------------------------
  // Delivery: Telegram connection and Morning Brief.
  // ------------------------------------------------------------------

  function renderBrief(container, brief) {
    const row = el("div", "wd-delivery-row");
    const timezone = ui().browserTimezone();
    row.innerHTML = `
      <div class="wd-delivery-copy">
        <label class="wd-delivery-title">
          <span class="switch wd-switch"><input type="checkbox" id="watchBriefToggle"><span class="slider"></span></span>
          Morning Brief
        </label>
        <p class="wd-field-hint">One daily e-mail across all watches: what moved, what resolved, what runs next. No extra model runs. Times use ${ui().escapeHtml(timezone)}.</p>
      </div>
      <div class="wd-delivery-controls" id="watchBriefControls" hidden>
        <input type="time" id="watchBriefTime" class="wd-input" aria-label="Brief delivery time">
        <select id="watchBriefMode" class="wd-select" aria-label="Brief frequency">
          <option value="always">Every morning</option>
          <option value="changes_only">Only when something happened</option>
        </select>
      </div>`;
    container.appendChild(row);
    const toggle = row.querySelector("#watchBriefToggle");
    const controls = row.querySelector("#watchBriefControls");
    const time = row.querySelector("#watchBriefTime");
    const mode = row.querySelector("#watchBriefMode");
    toggle.checked = Boolean(brief.enabled);
    controls.hidden = !toggle.checked;
    time.value = brief.send_time || "07:00";
    mode.value = brief.mode || "always";
    let persisted = { enabled: toggle.checked, time: time.value, mode: mode.value };
    async function save(changes, revert) {
      toggle.disabled = time.disabled = mode.disabled = true;
      try {
        const data = await ui().api("PATCH", "/api/my/watch-brief", changes);
        const saved = data.brief || {};
        toggle.checked = Boolean(saved.enabled);
        controls.hidden = !saved.enabled;
        if (saved.send_time) time.value = saved.send_time;
        if (saved.mode) mode.value = saved.mode;
        persisted = { enabled: toggle.checked, time: time.value, mode: mode.value };
        ui().popup(saved.enabled ? "Morning Brief updated." : "Morning Brief off.");
      } catch (error) {
        ui().popup("Brief update failed: " + error.message);
        revert();
      } finally {
        toggle.disabled = time.disabled = mode.disabled = false;
      }
    }
    toggle.addEventListener("change", () => save(
      toggle.checked
        ? { enabled: true, send_time: time.value || "07:00", timezone: timezone, mode: mode.value }
        : { enabled: false },
      () => { toggle.checked = persisted.enabled; controls.hidden = !persisted.enabled; }
    ));
    time.addEventListener("change", () => {
      if (!time.value || !toggle.checked) return;
      save({ send_time: time.value, timezone: timezone }, () => { time.value = persisted.time; });
    });
    mode.addEventListener("change", () => {
      if (!toggle.checked) return;
      save({ mode: mode.value }, () => { mode.value = persisted.mode; });
    });
  }

  function renderTelegram(container, state) {
    const row = el("div", "wd-delivery-row");
    const copy = el("div", "wd-delivery-copy");
    copy.appendChild(el("span", "wd-delivery-title", "Telegram"));
    const note = el("p", "wd-field-hint");
    copy.appendChild(note);
    const actions = el("div", "wd-delivery-controls");
    row.append(copy, actions);
    const disconnect = () => ui().makeButton("Disconnect", "wd-button", async function () {
      if (state.connected && !confirm("Disconnect Telegram? Watches keep the setting but cannot deliver there until you reconnect.")) return;
      this.disabled = true;
      try {
        await ui().api("DELETE", "/api/my/telegram", {});
        watchState.setTelegram(null);
        render();
      } catch (error) {
        this.disabled = false;
        ui().popup("Disconnect failed: " + error.message);
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
        try {
          await ui().api("POST", "/api/my/telegram/test", {});
          ui().popup("Test message sent.");
        } catch (error) {
          ui().popup("Test failed: " + error.message);
        } finally { this.disabled = false; }
      }));
      actions.appendChild(disconnect());
    } else {
      note.textContent = "Get the same change log as a chat message. Connect once, then choose it per watch.";
      actions.appendChild(ui().makeButton("Connect Telegram", "wd-button", async function () {
        this.disabled = true;
        await ui().connectTelegram(() => {
          watchState.setTelegram(null);
          render();
        });
        if (this.isConnected) this.disabled = false;
      }));
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
  // Render.
  // ------------------------------------------------------------------

  let renderToken = 0;

  async function render() {
    const body = document.getElementById("watchDashBody");
    if (!body) return;
    const token = ++renderToken;
    const requestEpoch = watchState.sessionEpoch;
    const requestUid = window.auth?.currentUser?.uid || null;
    const isCurrent = () => token === renderToken
      && requestEpoch === watchState.sessionEpoch
      && requestUid
      && window.auth?.currentUser?.uid === requestUid
      && ui().onWatchPagePath();
    const limitTarget = document.getElementById("watchDashLimit");
    if (!body.childElementCount) {
      body.innerHTML = '<p class="wd-loading">Loading your watches…</p>';
    } else {
      body.setAttribute("aria-busy", "true");
    }
    let watches = [];
    let brief = {};
    let telegram = { configured: false, connected: false };
    try {
      const [watchData, briefData, telegramData] = await Promise.all([
        ui().api("GET", "/api/my/watches"),
        ui().api("GET", "/api/my/watch-brief").catch(() => ({ brief: {} })),
        ui().api("GET", "/api/my/telegram").catch(() => ({ telegram: {} }))
      ]);
      if (!isCurrent()) return;
      watches = watchData.watches || [];
      ui().receiveWatchList(watchData);
      ui().renderWatchLimit(limitTarget, watchState.limits);
      brief = briefData.brief || {};
      telegram = telegramData.telegram || telegram;
      watchState.setTelegram(telegram);
    } catch (error) {
      if (!isCurrent()) return;
      body.removeAttribute("aria-busy");
      if (limitTarget) limitTarget.hidden = true;
      body.innerHTML = "";
      body.appendChild(el("p", "wd-loading", "Could not load watches: " + error.message));
      return;
    }
    body.removeAttribute("aria-busy");
    body.innerHTML = "";
    if (!watches.length) {
      if (limitTarget) limitTarget.hidden = true;
      renderEmpty(body);
      return;
    }
    renderSummary(body, watches);
    renderDifferences(body, { open: false, withTable: false });
    const active = watches.filter(watch => watch.status === "active").sort(sortActive);
    const resolved = watches.filter(watch => watch.status === "resolved")
      .sort((a, b) => String(b.resolution?.at || "").localeCompare(String(a.resolution?.at || "")));
    const paused = watches.filter(watch => watch.status !== "active" && watch.status !== "resolved");
    renderSection(body, "Watching", active, telegram);
    renderSection(body, "Resolved", resolved, telegram, "Closed on evidence. Slots are free again.");
    renderSection(body, "Paused", paused, telegram);
    renderDelivery(body, telegram, brief);
  }

  window.App.watchDashboard = { render: render, cardState: cardState };
})();
