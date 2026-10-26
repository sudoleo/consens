// User-facing progress and confirmed activity. Shared by live runs and saved turns.
(function () {
  "use strict";
  const App = window.App = window.App || {};
  // The glossary's words for a run (App.words, Apple-Audit H9).
  const statuses = { failed: "Failed", cancelled: "Stopped", canceled: "Stopped" };
  // One table per tool: noun (history/failure rows), running and completed copy.
  // Unknown future tools fall back to a neutral label instead of a raw name.
  const tools = {
    web_search: ['Web search', 'Searching the web…', 'Searched the web'],
    read_source: ['Read source', 'Reading a source…', 'Read source'],
    compare_models: ['Model comparison', 'Comparing perspectives…', 'Compared perspectives'],
    check_text: ['Text check', 'Checking your text against independent answers…', 'Checked your text against independent answers'],
    prepare_watch: ['Watch', 'Preparing a Watch…', 'Prepared a Watch for you to start'],
    read_settings: ['Settings', 'Checking your settings…', 'Checked your settings'],
    prepare_settings_change: ['Settings', 'Preparing a settings change…', 'Prepared a settings change for you to apply'],
    judge_answer: ['Answer check', 'Checking the answer…', 'Checked the answer'],
    // Audit instead of comparison: the comparison models review the answer.
    audit_answer: ['Answer review', 'Reviewing the answer…', 'Reviewed the answer'],
    start_agent: ['Ask a model', 'Asking another model…', 'Asked another model'],
    wait_agents: ['Wait for models', 'Waiting for model responses…', 'Received model updates'],
    send_agent: ['Follow up', 'Following up with a model…', 'Followed up with a model'],
    review_agent: ['Review a model', 'Reviewing a model response…', 'Reviewed a model response'],
    stop_agent: ['Stop a model', 'Stopping a model…', 'Stopped a model'],
    report_to_orchestrator: ['Report to the main model', 'Reporting to the main model…', 'Reported to the main model'],
    read_file: ['Read files', 'Reading your files…', 'Read your files'],
    read_document: ['Open document', 'Opening the document…', 'Opened the document'],
    create_document: ['Create document', 'Writing the document…', 'Created a document'],
    revise_document: ['Revise document', 'Revising the document…', 'Revised the document'],
    calendar_read: ['Calendar', 'Checking your calendar…', 'Checked your calendar'],
    prepare_calendar_event: ['Calendar change', 'Preparing a calendar change for your review…', 'Calendar change ready for review'],
    gmail_read: ['Gmail', 'Reading relevant emails…', 'Read relevant emails'],
    import_gmail_attachment: ['Email attachment', 'Importing an email attachment…', 'Imported an email attachment'],
    prepare_gmail_draft: ['Email draft', 'Drafting an email for your review…', 'Email draft ready for review'],
    update_memory: ['Memory', 'Updating memory…', 'Updated memory'],
    // The agent's own VM (agent_vm_tools.py); each call also shows as a
    // compact block of its own (vmView).
    vm_exec: ['Command', 'Running a command…', 'Ran a command'],
    vm_read_file: ['Read file', 'Reading a file…', 'Read a file'],
    vm_write_file: ['Write file', 'Writing a file…', 'Wrote a file'],
    vm_edit_file: ['Edit file', 'Editing a file…', 'Edited a file'],
    vm_share_file: ['Share file', 'Sharing a file…', 'Shared a file'],
    github_import: ['GitHub', 'Importing a repository…', 'Imported a repository'],
  };
  // Tools whose success leaves an external write waiting for the user.
  const reviewTools = new Set(['prepare_calendar_event', 'prepare_gmail_draft']);
  // Checks the app runs once the answer is written (DelegationLoop._finish_review).
  const answerChecks = new Set(['judge_answer', 'audit_answer']);
  const toolName = name => tools[name]?.[0] || 'Tool';
  // "Searched the web · 3 sources: skat.dk, virk.dk, borger.dk" says what the
  // answer now rests on; the bare verb said nothing a reader could check.
  function searchSummary(item) {
    const urls = new Set(), hosts = [];
    for (const source of Array.isArray(item.sources) ? item.sources : []) {
      try {
        const url = new URL(source?.url);
        if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || urls.has(url.href)) continue;
        urls.add(url.href);
        const host = url.hostname.replace(/^www\./, '');
        if (!hosts.includes(host)) hosts.push(host);
      } catch (_) { /* Invalid provider URL. */ }
    }
    if (hosts.length) {
      const more = hosts.length > 3 ? `, +${hosts.length - 3}` : '';
      return `Searched the web · ${urls.size} ${urls.size === 1 ? 'source' : 'sources'}: ${hosts.slice(0, 3).join(', ')}${more}`;
    }
    const count = Number.isInteger(item.count) && item.count > 0 ? item.count : 0;
    return count === 1 ? 'Searched the web · 1 search' : count ? `Searched the web · ${count} searches` : 'Searched the web';
  }
  // "Read source · arxiv.org" only when the page was really read (the server
  // sends `read` from the fetch result); a failed or refused read says so.
  function readSummary(item) {
    const host = typeof item.host === 'string' && /^[\w.-]{1,253}$/.test(item.host) ? item.host : '';
    if (item.status === 'running') return host ? `Reading ${host}…` : tools.read_source[1];
    if (item.status === 'succeeded' && item.read === 'completed') return host ? `Read source · ${host}` : 'Read source';
    if (item.status === 'succeeded' && item.read === 'already_read') return host ? `Already read · ${host}` : 'Already read';
    if (item.status === 'succeeded' && item.read === 'failed') return host ? `Could not read · ${host}` : 'Could not read the source';
    // Refused before any fetch (not cited, limit, no time left): nothing was read.
    if (item.status === 'succeeded' && item.read === 'refused') return 'Read source · Skipped';
    return null;
  }
  // A turn whose only check was that of a pasted text (saved on 2026-10-09
  // before the answer of such a turn was judged too): the answer judges did
  // not run.
  const textOnlySteps = { judge_answer: 'Checked your text' };
  function textOnlyReview(review) {
    const checks = Array.isArray(review?.checks) ? review.checks : [];
    return checks.length > 0 && checks.every(check => check?.skipped === 'passage_checked');
  }
  // A settings change says what came of it (agent_settings.py `outcome`).
  const settingsOutcomes = { refused: 'Settings change not prepared', unchanged: 'Settings already in place' };
  function stepLabel(item, textOnly = false) {
    if (item.status === 'succeeded' && textOnly && textOnlySteps[item.name]) return textOnlySteps[item.name];
    if (item.status === 'succeeded' && item.name === 'prepare_settings_change' && settingsOutcomes[item.outcome]) {
      return settingsOutcomes[item.outcome];
    }
    if (item.name === 'read_source' && readSummary(item)) return readSummary(item);
    if (item.status === 'running') return tools[item.name]?.[1] || 'Working on a step…';
    if (item.status === 'succeeded' && item.name === 'web_search') return searchSummary(item);
    if (item.status === 'succeeded') return tools[item.name]?.[2] || `${toolName(item.name)} · Completed`;
    // Translated part by part: "{tool} · {state}" has no entry of its own.
    const state = {failed:'Failed', cancelled:'Stopped', blocked:'Skipped', unknown:'Usage unavailable'}[item.status] || 'Details';
    return `${App.t(toolName(item.name))} · ${App.t(state)}`;
  }
  function savedDuration(turn) {
    const start = Date.parse(turn?.created_at);
    const end = Date.parse(turn?.completed_at || turn?.failed_at);
    return Number.isFinite(start) && Number.isFinite(end) && end >= start ? end - start : null;
  }
  // "23s", "3m 7s": the one way the app writes a span (App.format).
  function durationText(ms) {
    return App.format.duration(ms);
  }
  // "Working for 12s" while it runs, "Thought for 3m 7s" once it is done.
  function durationLabel(ms, running, status) {
    if (!Number.isFinite(ms)) return running ? 'Working' : statuses[status] || 'Activity';
    const time = durationText(ms);
    if (running) return `Working for ${time}`;
    if (status === 'failed') return `Failed after ${time}`;
    if (statuses[status] === statuses.cancelled) return `Stopped after ${time}`;
    return `Thought for ${time}`;
  }
  // The clock ticks in a field of fixed width, so the chevron and the model
  // icons after it do not move with every second (Apple audit A7): the time
  // sits in a slot as wide as its largest value in the same unit ("59s",
  // "9m 59s"), and the verb ("Working for" / "Thought for") takes the width
  // of the wider of the two, so the end of the run changes the words, not
  // the line.
  const SETTLED_VERBS = { running: "Working for", done: "Thought for" };
  const SLOTS = ["seconds", "minutes", "long"];
  function setTitle(view, ms, running, status) {
    const label = durationLabel(ms, running, status);
    if (view.title.dataset.label === window.App.t(label)) return;
    view.title.dataset.label = label;
    const time = Number.isFinite(ms) ? durationText(ms) : "";
    const verb = time ? label.slice(0, label.length - time.length).trimEnd() : label;
    const verbEl = view.title.querySelector(".agent-activity-verb-text");
    const timeEl = view.title.querySelector(".agent-activity-time");
    const seconds = Math.floor(Math.max(0, ms || 0) / 1000);
    const unit = !time ? "" : seconds < 60 ? "seconds" : seconds < 600 ? "minutes" : "long";
    // A live clock holds the slot of its own unit: the minutes slot from
    // the first second left a wide gap before the chevron for a whole
    // minute. The label a run ends with keeps at least the slot it ticked
    // in, so the end of the run does not move the line.
    if (running && unit) view.liveSlot = unit;
    const slot = running || !unit || !view.liveSlot ? unit
      : SLOTS[Math.max(SLOTS.indexOf(view.liveSlot), SLOTS.indexOf(unit))];
    const resize = Boolean(timeEl.dataset.unit) && timeEl.dataset.unit !== slot && timeEl.isConnected;
    const from = resize ? timeEl.getBoundingClientRect().width : 0;
    if (resize) cancelMotion(view.slotMotion);
    if (verbEl.textContent !== window.App.t(verb)) verbEl.textContent = verb;
    // The other verb stands invisibly in the same cell (agent-chat.css), so
    // the field is as wide as the wider one; it is no text of the title.
    const paired = verb === SETTLED_VERBS.running ? SETTLED_VERBS.done : verb === SETTLED_VERBS.done ? SETTLED_VERBS.running : "";
    const holder = verbEl.parentElement;
    if (paired) holder.dataset.ghost = paired; else delete holder.dataset.ghost;
    view.title.querySelector(".agent-activity-gap").textContent = time ? " " : "";
    if (timeEl.textContent !== window.App.t(time)) timeEl.textContent = time;
    timeEl.dataset.unit = slot;
    if (!resize) return;
    // The first minute widens the slot once: the chevron glides to its new
    // place while the new time opens up (none with reduced motion, motion()).
    // min-width moves along: the slot's own min-width would win over width.
    const to = timeEl.getBoundingClientRect().width;
    view.slotMotion = from && to && from !== to ? motion(timeEl, [
      { width: `${from}px`, minWidth: `${from}px`, overflow: 'clip' },
      { width: `${to}px`, minWidth: `${to}px`, overflow: 'clip' },
    ]) : null;
  }
  function updateClock(view, elapsedMs, running, status) {
    clearInterval(view.clockTimer);
    view.clockTimer = null;
    const now = performance.now();
    const previous = Number.isFinite(view.elapsedMs) ? view.elapsedMs + (view.clockRunning ? now - view.clockAt : 0) : null;
    view.elapsedMs = Number.isFinite(elapsedMs) ? Math.max(0, elapsedMs) : previous ?? (running ? 0 : null);
    view.clockAt = now;
    view.clockRunning = running;
    const tick = () => {
      const elapsed = view.elapsedMs === null ? null : view.elapsedMs + (view.clockRunning ? performance.now() - view.clockAt : 0);
      setTitle(view, elapsed, running, status);
    };
    tick();
    if (running) view.clockTimer = setInterval(tick, 1000);
  }
  const quietMotion = window.matchMedia?.('(prefers-reduced-motion: reduce), (forced-colors: active)');
  const activeMotion = new Set();
  let offscreenUpdate = false;
  function motion(element, frames, finish = () => {}, duration = 220) {
    if (offscreenUpdate || quietMotion?.matches || !element.animate || !element.isConnected) { finish(); return null; }
    const animation = element.animate(frames, { duration, easing: window.App?.motion?.ease?.("out") ?? 'cubic-bezier(.2, .7, .2, 1)', fill: 'both' });
    activeMotion.add(animation);
    animation.onfinish = () => { activeMotion.delete(animation); if (finish() !== false) animation.cancel(); };
    animation.oncancel = () => activeMotion.delete(animation);
    return animation;
  }
  quietMotion?.addEventListener?.('change', () => {
    if (quietMotion.matches) for (const animation of [...activeMotion]) {
      if (animation.playState !== 'idle') animation.finish();
    }
  });
  function cancelMotion(animation) {
    if (!animation) return;
    activeMotion.delete(animation);
    animation.onfinish = null;
    animation.cancel();
  }
  function dispose(host) {
    if (!host) return;
    clearInterval(host._agentActivity?.clockTimer);
    if (host._agentActivity) { host._agentActivity.clockTimer = null; dropLine(host._agentActivity); }
    for (const animation of [...activeMotion]) {
      if (host.contains(animation.effect?.target)) cancelMotion(animation);
    }
    cancelMotion(host._agentActivity?.historyMotion);
  }
  // `lift: false` fades only: the answer's first words must not glide.
  function reveal(element, { lift = true } = {}) {
    return motion(element, lift ? [{ opacity: 0, transform: 'translateY(4px)' }, { opacity: 1, transform: 'none' }]
      : [{ opacity: 0 }, { opacity: 1 }]);
  }
  function clearPreview(view) {
    view.preview.hidden = true;
    view.preview.replaceChildren();
    view.previewNodes.clear();
    view.previewExit = false;
    view.previewMotion = null;
  }
  function hidePreview(view, instant = false) {
    if (view.previewExit && !instant) return;
    const height = view.preview.getBoundingClientRect().height;
    cancelMotion(view.previewMotion);
    view.preview.setAttribute('aria-hidden', 'true');
    view.preview.inert = true;
    if (!height || instant) { clearPreview(view); return; }
    view.previewExit = true;
    const style = getComputedStyle(view.preview);
    view.previewMotion = motion(view.preview, [
      { height: `${height}px`, opacity: 1, marginTop: style.marginTop, marginBottom: style.marginBottom, overflow: 'clip' },
      { height: '0px', opacity: 0, marginTop: '0px', marginBottom: '0px', overflow: 'clip' },
    ], () => clearPreview(view));
  }
  function disclosure(view, open) {
    const host = view.details.parentElement;
    const before = host.getBoundingClientRect().height;
    cancelMotion(view.disclosureMotion);
    cancelMotion(view.historyMotion);
    view.disclosureTarget = open;
    view.history.inert = !open;
    if (!open && view.history.contains(document.activeElement)) view.summary.focus({ preventScroll: true });
    // Measure the destination in normal flow, including the live preview when
    // closing. Keep the outgoing history painted until its short fade finishes.
    view.details.open = open;
    const after = host.getBoundingClientRect().height;
    if (before && after && before !== after && !offscreenUpdate && !quietMotion?.matches && host.animate) {
      view.details.open = true;
      view.details.classList.toggle('is-closing', !open);
      view.historyMotion = motion(view.history, [{ opacity: open ? 0 : 1 }, { opacity: open ? 1 : 0 }], () => false, 160);
      view.disclosureMotion = motion(host, [
        { height: `${before}px`, overflow: 'clip' }, { height: `${after}px`, overflow: 'clip' },
      ], () => {
        view.details.open = open;
        cancelMotion(view.historyMotion);
        view.details.classList.remove('is-closing');
        view.disclosureMotion = null;
        if (!open && view.running) reveal(view.preview);
      });
    } else {
      view.details.classList.remove('is-closing');
      view.disclosureMotion = null;
    }
  }
  // Where a sentence ends: its punctuation, then whitespace or the end of the
  // line, never inside "e.g.", "U.S.", "Dr.", "J. Smith" or "am 3. Oktober"
  // (the server's rule, agent_progress.py _ends_sentence).
  const ABBREVIATIONS = new Set(['approx', 'ca', 'cf', 'co', 'corp', 'dept', 'dr', 'esp', 'est', 'etc', 'fig', 'inc',
    'jr', 'ltd', 'mr', 'mrs', 'ms', 'no', 'nos', 'nr', 'prof', 'sr', 'st', 'vol', 'vs', 'jan', 'feb', 'mar', 'apr',
    'jun', 'jul', 'aug', 'sep', 'sept', 'oct', 'nov', 'dec', 'bzw', 'evtl', 'ggf', 'inkl', 'usw', 'vgl', 'zzgl', 'abs',
    'bd', 'bzgl', 'hr', 'fr', 'mio', 'mrd', 'tsd']);
  const ORDINAL_AFTER = new Set(['am', 'vom', 'zum', 'zur', 'im', 'beim', 'bis', 'ab', 'seit', 'der', 'die', 'das',
    'den', 'dem', 'des', 'ein', 'eine', 'einem', 'einen', 'einer', 'jeden', 'jedem', 'jeder', 'ihrem', 'seinem']);
  function sentences(line) {
    const found = [];
    let start = 0;
    for (const match of line.matchAll(/[.!?]+["'”’)\]]*(?=\s|$)/g)) {
      const marks = match[0].replace(/["'”’)\]]+$/, '');
      if (!/[!?]/.test(marks)) {
        // An ellipsis trails off; it ends nothing.
        if (marks !== '.') continue;
        const before = line.slice(Math.max(0, match.index - 40), match.index).split(/\s+/).filter(Boolean);
        const word = (before.at(-1) || '').replace(/^[(["'“‘]+/, '');
        if (word.includes('.') || ABBREVIATIONS.has(word.toLowerCase()) || /^\p{L}$/u.test(word)) continue;
        if (/^\d{1,2}$/.test(word) && before.length > 1 && ORDINAL_AFTER.has(before.at(-2).toLowerCase())) continue;
      }
      const end = match.index + match[0].length;
      const sentence = line.slice(start, end).trim();
      if (sentence) found.push(sentence);
      start = end;
    }
    return found;
  }
  // Reasoning highlights as complete statements only (2026-10-21): each of
  // the last three lines gives its first complete sentence that fits, or
  // stands as it is when it is a title without punctuation. Nothing is cut:
  // a line whose sentences are all too long, or one that an older turn
  // stored cut off ("…"), is left out.
  function compactReasoning(text) {
    const lines = String(text || "").split("\n");
    const excerpts = [];
    for (let index = lines.length - 1; index >= 0 && excerpts.length < 3; index -= 1) {
      const line = lines[index].replace(/^[#*>\s-]+/, "").replace(/^\d{1,3}[.)]\s+/, "")
        .replace(/\*\*|__|`/g, '').replace(/\s+/g, " ").trim();
      if (!line) continue;
      const found = sentences(line);
      const excerpt = found.length ? found.find(sentence => sentence.length <= 180)
        : line.length <= 180 && !/(?:…|\.\.)$/.test(line) ? line : '';
      if (excerpt) excerpts.unshift(excerpt);
    }
    return excerpts.join("\n");
  }
  // A line that changes in place fades out and back in with its new words
  // (at once with reduced motion, motion()): one quiet change, not a jump.
  function crossfade(p, text) {
    if ((p._fadeText ?? p.textContent) === text) return;
    const previous = p.textContent;
    p._fadeText = text;
    cancelMotion(p._fadeMotion);
    if (!previous) { p.textContent = text; return; }
    p._fadeMotion = motion(p, [{ opacity: 1 }, { opacity: 0 }], () => {
      p.textContent = p._fadeText;
      p._fadeMotion = motion(p, [{ opacity: 0 }, { opacity: 1 }], () => {}, 220);
    }, 140);
  }
  // While the comparison models answer, one quiet line quotes them in turn
  // (2026-10-21): an excerpt stands at least LINE_DWELL_MS, then the next
  // model in order with something new to say takes the line. Before, the
  // model that reported last always won, and the line changed model every
  // half second.
  const LINE_DWELL_MS = 2500;
  function comparisonLine(view, highlights) {
    const lines = (Array.isArray(highlights) ? highlights : []).filter(item => item?.id && item.text)
      .map((item, index) => ({ ...item, order: Number.isFinite(item.order) ? item.order : index + 1 }));
    view.highlights = lines;
    if (!lines.length) return dropLine(view);
    const now = performance.now();
    const shown = view.line;
    if (shown && now - shown.at < LINE_DWELL_MS) return shown;
    const seen = view.lineSeen ||= new Map();
    const after = shown?.order ?? 0;
    const turn = [...lines.filter(item => item.order > after), ...lines.filter(item => item.order <= after)];
    // Nothing new anywhere: the model on the line keeps it while it answers.
    const next = turn.find(item => seen.get(item.id) !== item.text)
      || (shown && lines.some(item => item.id === shown.id) ? null : turn[0]);
    if (!next) return shown;
    seen.set(next.id, next.text);
    view.line = { id: next.id, order: next.order, at: now, text: next.label ? `${next.label}: ${next.text}` : next.text };
    return view.line;
  }
  function dropLine(view) {
    clearTimeout(view.lineTimer);
    view.line = view.lineTimer = null;
    return null;
  }
  // The line moves on by itself when its time is up, also when no new
  // report arrives to render the activity again.
  function scheduleLine(view) {
    clearTimeout(view.lineTimer);
    view.lineTimer = null;
    const wait = view.line ? view.line.at + LINE_DWELL_MS - performance.now() : 0;
    if (wait > 0) view.lineTimer = setTimeout(() => {
      view.lineTimer = null;
      const node = view.previewNodes.get('comparison-highlight');
      if (!view.running || !node?.isConnected) return;
      const line = comparisonLine(view, view.highlights);
      if (line) crossfade(node, line.text);
      scheduleLine(view);
    }, wait + 20);
  }

  function receive(events, event) {
    if (event?.version !== 1 || !["status", "progress", "reasoning", "usage", "tool"].includes(event.kind) || typeof event.id !== "string") return;
    const existing = events.find(item => item.id === event.id);
    if (existing && event.append && event.kind === "reasoning") {
      existing.text = (existing.text + String(event.text || "")).slice(0, 32000);
    } else if (existing) {
      Object.assign(existing, event);
      if (event.kind === 'status') { events.splice(events.indexOf(existing), 1); events.push(existing); }
    } else {
      // Keep commentary and confirmed steps together for the full timeline.
      if (!['progress', 'tool'].includes(event.kind)) {
        const auxiliary = events.filter(item => !['progress', 'tool'].includes(item.kind));
        for (const item of auxiliary.slice(0, Math.max(0, auxiliary.length - 63))) events.splice(events.indexOf(item), 1);
      }
      events.push({ ...event, text: String(event.text || "").slice(0, event.kind === "progress" ? 400 : event.kind === "tool" ? 8000 : 32000) });
    }
  }

  // Same wording as the reasoning picker (agent-chat.js effortCopy).
  const effortNames = { default: 'Model default', none: 'Off', minimal: 'Minimal', low: 'Low', medium: 'Medium',
    high: 'High', xhigh: 'Extra high', max: 'Max' };
  const effortName = effort => effortNames[effort] || String(effort || '');
  function label(settings) {
    if (!settings?.label) return "Agent answer";
    const effort = settings.reasoning_effort;
    return `${settings.label}${effort && effort !== "default" ? ` · ${effort === "none" ? "Reasoning off" : `${effortName(effort)} reasoning`}` : ""}`;
  }

  // The model the turn ran on, with its reasoning only when it was not the
  // model's default (the same words as the answer's label).
  function renderRunDetails(view, settings) {
    const text = settings?.label ? label(settings) : '';
    view.runDetails.hidden = !text;
    if (view.runDetails.dataset.label !== text) {
      view.runDetails.dataset.label = text;
      view.runDetails.textContent = text;
    }
  }
  // A step in the timeline says what happened in the words of the live run
  // ("Searched the web"); its sources follow as the answer's pills.
  const failedSteps = { failed: "Failed", blocked: "Skipped · allowance kept for the answer", cancelled: "Stopped", unknown: "Usage unavailable" };
  function historyTitle(item, textOnly, linked) {
    if (item.status === 'succeeded' && linked && !textOnly) {
      if (item.name === 'web_search') return tools.web_search[2];
      if (item.name === 'read_source' && item.read === 'completed') return tools.read_source[2];
    }
    if (failedSteps[item.status] && !(item.name === 'read_source' && readSummary(item))) {
      const count = Number.isInteger(item.count) && item.count > 0 ? ` · ${item.count} ${item.count === 1 ? "search" : "searches"}` : "";
      return `${toolName(item.name)} · ${failedSteps[item.status]}${count}`;
    }
    return stepLabel(item, textOnly);
  }
  function sourcePill(url, title) {
    // sources.js builds the answer's pill (favicon, domain, preview on hover).
    if (typeof window.createSourceRef === 'function') return window.createSourceRef([{ src: { url: url.href, title }, token: url.href }]);
    const link = document.createElement('a');
    link.className = 'src-ref';
    link.href = url.href;
    link.textContent = url.hostname.replace(/^www\./, '');
    if (title) link.title = title;
    return link;
  }

  // A call in the agent's own VM (agent_vm_tools.py), compact like a
  // terminal: the command (or the file) and how it ended on one line, its
  // output below, open while it runs and folded once it is done, unless the
  // reader opened or closed it. Command, path and output are data: they sit
  // in <code> and <pre>, which stay untranslated, and the line's own words go
  // through App.t (the line is data-i18n-skip).
  const vmTools = new Set(['vm_exec', 'vm_read_file', 'vm_write_file', 'vm_edit_file', 'vm_share_file',
    'github_import']);
  const vmVerbs = { vm_read_file: ['Reading the file', 'Read the file'],
    vm_write_file: ['Writing the file', 'Wrote the file'], vm_edit_file: ['Editing the file', 'Edited the file'],
    vm_share_file: ['Sharing the file', 'Shared the file'],
    github_import: ['Importing the repository into', 'Imported the repository into'] };
  const vmOutcomes = { unavailable: 'VM not available', no_time: 'Skipped · no time left' };
  function vmMeta(item) {
    if (vmOutcomes[item.outcome]) return App.t(vmOutcomes[item.outcome]);
    if (item.status === 'running') return item.name === 'vm_exec' ? App.t('Running…') : '';
    if (item.status === 'cancelled') return App.t('Stopped');
    if (item.status === 'failed') return App.t('Failed');
    const parts = [];
    if (item.timed_out) parts.push(App.t('Timed out'));
    else if (Number.isInteger(item.exit_code) && item.exit_code !== 0) parts.push(App.t('Exit {code}', { code: item.exit_code }));
    // A quick command needs no clock ("0s" says nothing).
    if (Number.isFinite(item.duration_ms) && item.duration_ms >= 1000) parts.push(App.format.duration(item.duration_ms));
    return parts.join(' · ');
  }
  function vmView(className) {
    const details = document.createElement('details');
    details.className = className;
    const summary = document.createElement('summary');
    summary.className = 'agent-vm-head';
    summary.dataset.i18nSkip = '';
    const verb = document.createElement('span'); verb.className = 'agent-vm-verb';
    const target = document.createElement('code'); target.className = 'agent-vm-target'; target.translate = false;
    const meta = document.createElement('span'); meta.className = 'agent-vm-meta';
    summary.append(verb, target, meta);
    const output = document.createElement('pre'); output.className = 'agent-vm-output'; output.translate = false;
    output.hidden = true;
    details.append(summary, output);
    summary.addEventListener('click', event => {
      if (!details.classList.contains('has-output')) { event.preventDefault(); return; }
      details.dataset.chosen = '';
    });
    // Opened later, the output shows its end, where a command says how it went.
    details.addEventListener('toggle', () => { if (details.open) output.scrollTop = output.scrollHeight; });
    return details;
  }
  function updateVm(details, item) {
    const signature = JSON.stringify([item.status, item.command, item.path, item.output, item.output_truncated,
      item.exit_code, item.duration_ms, item.timed_out, item.outcome]);
    if (details.dataset.signature === signature) return;
    details.dataset.signature = signature;
    details.dataset.status = item.status;
    details.dataset.tool = item.name;
    const [verb, target, meta] = details.firstElementChild.children;
    const verbs = vmVerbs[item.name];
    verb.hidden = !verbs;
    verb.textContent = verbs ? App.t(verbs[item.status === 'running' ? 0 : 1]) : '';
    target.textContent = String((item.name === 'vm_exec' ? item.command : item.path) || '');
    meta.textContent = vmMeta(item);
    const output = details.lastElementChild;
    const text = String(item.output || '');
    output.textContent = text && item.output_truncated ? `…\n${text}` : text;
    output.hidden = !text;
    details.classList.toggle('has-output', Boolean(text));
    if (!('chosen' in details.dataset)) details.open = item.status === 'running' && Boolean(text);
    if (details.open) output.scrollTop = output.scrollHeight;
  }

  // Like Claude Code, a run that works in its VM folds its earlier steps into
  // one line ("Ran 4 commands"); the note that leads into the latest command,
  // that command and what follows stay in view. Until 2026-10-26 every
  // command and every note between them stood one under the other, a screen
  // long. A step that waits on the reader never folds away.
  function foldPast(paragraphs) {
    const lastVm = paragraphs.findLastIndex(item => item.kind === 'vm');
    let start = lastVm;
    while (start > 0 && paragraphs[start - 1].kind === 'progress' && !paragraphs[start - 1].quiet) start--;
    const review = paragraphs.findIndex(item => item.kind === 'review');
    const past = paragraphs.slice(0, review >= 0 ? Math.min(start, review) : start);
    const steps = past.filter(item => item.kind !== 'progress');
    if (steps.length < 2 || !steps.some(item => item.kind === 'vm')) return null;
    const commands = steps.filter(item => item.kind === 'vm' && item.item.name === 'vm_exec').length;
    const label = commands === steps.length ? (commands === 1 ? 'Ran 1 command' : `Ran ${commands} commands`)
      : steps.length === 1 ? '1 earlier step' : `${steps.length} earlier steps`;
    return { past, label };
  }
  function foldView() {
    const fold = document.createElement('details');
    fold.className = 'agent-vm-fold';
    const summary = document.createElement('summary');
    const label = document.createElement('span');
    summary.append(label);
    const list = document.createElement('div');
    list.className = 'agent-vm-fold-list';
    fold.append(summary, list);
    fold._label = label; fold._list = list;
    return fold;
  }
  function render(host, spec) {
    const restore = host?._agentActivity && App.chatScroll?.preserveAbove(host, host.nextElementSibling);
    offscreenUpdate = !!restore;
    try {
      if (restore) {
        // Finish a height transition that started before the reader scrolled
        // past the status. Offscreen changes settle once, with one correction.
        for (const animation of [...activeMotion]) {
          if (host.contains(animation.effect?.target) && animation.effect.getKeyframes().some(frame => 'height' in frame)) {
            const finish = animation.onfinish;
            animation.onfinish = null;
            finish?.();
          }
        }
      }
      renderActivity(host, spec);
    } finally {
      offscreenUpdate = false;
      restore?.();
    }
  }
  function renderActivity(host, { events = [], usage = null, running = false, responding = false,
    status = "succeeded", truncated = false, finishReason = "", review = null, answerText = '', settings = null, elapsedMs = null,
    highlights = [], reconnecting = false, vm = null } = {}) {
    if (!host) return;
    if (!host._agentActivity) {
      const details = document.createElement("details");
      details.className = "agent-activity";
      const summary = document.createElement("summary");
      const title = document.createElement("span");
      title.className = "agent-activity-title";
      title.setAttribute("role", "timer");
      title.setAttribute('aria-live', 'off');
      const verb = document.createElement("span"); verb.className = "agent-activity-verb";
      const verbText = document.createElement("span"); verbText.className = "agent-activity-verb-text";
      verb.append(verbText);
      const gap = document.createElement("span"); gap.className = "agent-activity-gap";
      const time = document.createElement("span"); time.className = "agent-activity-time";
      title.append(verb, gap, time);
      const chevron = document.createElement("span");
      chevron.className = "agent-activity-chevron";
      chevron.setAttribute("aria-hidden", "true");
      summary.append(title, chevron);
      const content = document.createElement("div");
      content.className = "agent-activity-content";
      content.tabIndex = 0;
      content.setAttribute("role", "region");
      content.setAttribute("aria-label", "Agent activity");
      const note = document.createElement("p");
      note.className = "agent-activity-note";
      // Tokens and provider cost are the operator's figures, not the
      // reader's (Apple-Audit H4): only an admin sees this line.
      const usageEl = document.createElement("p");
      usageEl.className = "agent-usage admin-only";
      const preview = document.createElement('div'); preview.className = 'agent-progress';
      preview.setAttribute('role', 'log'); preview.setAttribute('aria-live', 'polite');
      // A line that changes swaps its text node, an addition: "text" as well
      // read every change twice (a11y audit B5).
      preview.setAttribute('aria-relevant', 'additions');
      preview.setAttribute('aria-label', 'Progress updates');
      const history = document.createElement('div'); history.className = 'agent-activity-history';
      // One timeline: the agent's notes and its steps in order, then what the
      // comparisons found; the model it ran on is a quiet line at the end.
      const timeline = document.createElement('div'); timeline.className = 'agent-activity-timeline';
      const runDetails = document.createElement('p'); runDetails.className = 'agent-activity-run-details';
      const insights = document.createElement('div'); insights.className = 'agent-activity-insights'; insights.hidden = true;
      // While it runs and no step is under way: what it does now, the last
      // entry of the timeline after the comparisons (the preview's line,
      // hidden while this is open).
      const current = document.createElement('p'); current.className = 'agent-activity-current';
      current.setAttribute('role', 'status');
      current.append(document.createElement('strong'));
      history.inert = true;
      timeline.append(content, insights);
      history.append(timeline, note, runDetails, usageEl);
      details.append(summary, history);
      // Progress shows at the model icons in the summary (agent-chat.css,
      // "Progress at the models"), not on a line of its own.
      host.replaceChildren(details, preview);
      host._agentActivity = { details, summary, history, title, timeline, runDetails, insights, content, current, note, usageEl, preview, nodes: new Map(), previewNodes: new Map() };
      summary.addEventListener('click', event => {
        event.preventDefault();
        const view = host._agentActivity;
        disclosure(view, !(view.disclosureTarget ?? details.open));
      });
    }
    const view = host._agentActivity;
    const progress = events.filter(item => item.kind === 'progress' && item.text);
    const reasoning = progress.length ? [] : events.filter(item => item.kind === "reasoning"
      && ["text", "summary"].includes(item.format) && item.text);
    // Older saved turns mistook a missing search counter for tool activity.
    // Preserve real client calls and searches backed by counts or citations.
    // `answer` only ends the steering; the answer itself is what follows.
    // Older saved turns also carry a step of the removed contradiction source
    // check (`check_contradictions`); it has no result left to show.
    const tools = events.filter(item => item.kind === "tool" && !["answer", "check_contradictions"].includes(item.name) && !(item.name === "web_search"
      && item.status === "unknown" && (item.server_tool || item.provider_native)
      && !(Number.isInteger(item.count) && item.count > 0) && !item.sources?.length));
    const activeTool = tools.findLast(item => item.status === "running");
    const textOnly = textOnlyReview(review);
    const latest = events.filter(item => item.kind === "status").at(-1);
    // Text the model writes before a tool call is a preamble, not the answer.
    // Once a later step (search, comparison) has run, "Writing answer…" only
    // returns with a new responding status after it.
    const afterLatest = latest ? events.slice(events.indexOf(latest) + 1) : [];
    const writing = latest ? latest.status === "responding" && !afterLatest.some(item => item.kind === "tool") : responding;
    const reviewStage = review?.status === "running" ? (review.mode === "audit" ? "Reviewing the answer…" : "Checking the answer…")
      : review?.comparisons?.some(c => c.status === "running") ? "Comparing perspectives…" : null;
    const waiting = running && latest?.status === 'waiting';
    // The run keeps going on the server while the browser is offline or
    // asleep; say that instead of a step that may be long over.
    const heading = running && reconnecting ? 'Reconnecting…'
      : waiting ? 'Waiting for available tokens…' : reviewStage
      || (activeTool ? stepLabel(activeTool) : writing ? 'Writing answer…' : 'Thinking…');
    // A complete, checked answer whose run failed afterwards reads as done:
    // the same rule as failureNote.
    const settled = status === 'failed' && !running && answerText
      && App.agentReview?.failureNote?.({error: 'failed'}, review, answerText) === '';
    updateClock(view, elapsedMs, running, settled ? 'succeeded' : status);
    renderRunDetails(view, settings || events.findLast(item => item.settings)?.settings);
    view.details.classList.toggle("is-running", running);
    view.details.dataset.status = status;
    // Completion collapses a manually opened live history only offscreen
    // (below). Later explicit expansion is preserved across saved-turn and usage updates.
    const finished = view.running && !running;
    view.running = running;
    // Stable paragraphs keep earlier updates readable and prevent a live region
    // from announcing the entire history again whenever a new paragraph arrives.
    const paragraphs = events.flatMap(item => progress.includes(item)
      ? [{id:item.id, text:item.text, kind:'progress'}]
      : reasoning.includes(item) ? [{id:item.id, text:compactReasoning(item.text), kind:'progress'}]
        : tools.includes(item) && vmTools.has(item.name) ? [{id:`vm:${item.id}`, kind:'vm', item}]
        : tools.includes(item) ? [{id:`step:${item.id}`, text:stepLabel(item, textOnly), kind:'step', status:item.status,
          current:running && !waiting && !reconnecting && item === activeTool},
          // The one place where the run waits on the user: say so, and link to the card.
          ...(item.status === 'succeeded' && reviewTools.has(item.name)
            ? [{id:`review:${item.id}`, text:'Waiting for your confirmation below', kind:'review'}] : [])] : []);
    if (running && (!activeTool || waiting || reconnecting)) paragraphs.push({id:'current-status', text:heading, kind:'step', current:true});
    // While the comparison models answer, the main model is silent: one quiet
    // line quotes their reasoning in turn (comparisonLine).
    const comparing = reviewStage === 'Comparing perspectives…' || ['compare_models', 'check_text'].includes(activeTool?.name);
    const line = running && !waiting && !reconnecting && comparing ? comparisonLine(view, highlights) : dropLine(view);
    if (line) {
      // quiet: true keeps the changes out of the screen reader log; the
      // agent panel offers the same highlights per model.
      paragraphs.push({ id: 'comparison-highlight', kind: 'progress', quiet: true, text: line.text });
      scheduleLine(view);
    }
    if (waiting) paragraphs.push({ id: 'waiting', kind:'progress', text: latest.text || 'Active model calls are using the available allowance. This response will continue automatically.' });
    // A hidden or still empty preview is 0 tall without asking the layout (a
    // new run's first render happens inside the click on Send, Apple-Audit D3).
    const previewHeight = view.preview.hidden || !view.preview.childElementCount
      ? 0 : view.preview.getBoundingClientRect().height;
    // Like ChatGPT/Claude, the progress lines give way the moment the answer
    // starts: at that point nothing stands below them yet. Kept until the
    // run ended, their collapse pulled the finished answer up under the eye.
    // A preamble before a running tool is not the answer yet; the app's own
    // checks of the written answer are no such tool: the lines came back for
    // "Checking the answer" and left again (2026-10-12), two collapses for one.
    const answering = running && (!activeTool || answerChecks.has(activeTool.name))
      && Boolean(String(answerText || '').trim());
    const showPreview = running && paragraphs.length && !answering;
    let previewChanged = false;
    if (showPreview) {
      if (view.previewExit) { cancelMotion(view.previewMotion); view.previewExit = false; }
      view.preview.hidden = false;
      view.preview.removeAttribute('aria-hidden');
      view.preview.inert = false;
    }
    const previewIds = new Set();
    const folded = showPreview ? foldPast(paragraphs) : null;
    const pastIds = new Set(folded?.past.map(item => item.id) || []);
    let fold = view.previewNodes.get('vm-fold');
    if (folded) {
      previewIds.add('vm-fold');
      if (!fold) { fold = foldView(); view.previewNodes.set('vm-fold', fold); }
      if (fold._label.textContent !== window.App.t(folded.label)) fold._label.textContent = folded.label;
      if (fold.dataset.count !== String(pastIds.size)) { fold.dataset.count = String(pastIds.size); previewChanged = true; }
      if (view.preview.firstElementChild !== fold) view.preview.insertBefore(fold, view.preview.firstElementChild);
    }
    let pastIndex = 0, presentIndex = folded ? 1 : 0;
    const place = (item, p) => {
      const inFold = pastIds.has(item.id);
      const parent = inFold ? fold._list : view.preview;
      const position = parent.children[inFold ? pastIndex++ : presentIndex++];
      if (position !== p) parent.insertBefore(p, position || null);
    };
    for (const item of showPreview ? paragraphs : []) {
      previewIds.add(item.id);
      let p = view.previewNodes.get(item.id);
      if (!p) {
        p = item.kind === 'vm' ? vmView('agent-vm') : document.createElement(item.kind === 'progress' ? 'p' : 'div');
        view.previewNodes.set(item.id, p);
        if (item.kind === 'review') {
          const jump = document.createElement('button');
          jump.type = 'button'; jump.className = 'agent-progress-review-jump';
          jump.textContent = item.text;
          jump.addEventListener('click', () => App.agentChat?.revealPendingReview?.());
          p.className = 'agent-progress-review';
          p.append(jump);
        }
        view.preview.appendChild(p);
        previewChanged = true;
        if (!view.details.open) reveal(p);
      }
      if (item.kind === 'review' || item.kind === 'vm') {
        if (item.kind === 'vm') updateVm(p, item.item);
        place(item, p);
        continue;
      }
      if (item.quiet) p.setAttribute('aria-hidden', 'true');
      p.classList.toggle('agent-progress-step', item.kind === 'step');
      p.classList.toggle('agent-current-status', Boolean(item.current));
      if (item.current) p.setAttribute('role', 'status'); else p.removeAttribute('role');
      if (item.status) p.dataset.status = item.status;
      // A reasoning line that changes in place (a comparison model's quote,
      // the chat model's thinking) cross-fades; a step only brightens.
      if (item.kind === 'progress') crossfade(p, item.text);
      else if (p.textContent !== window.App.t(item.text)) {
        const previous = p.textContent;
        p.textContent = item.text;
        if (previous) motion(p, [{opacity:.65}, {opacity:1}], () => {}, 160);
      }
      // A fallback Thinking/Writing row moves after a newly received insight.
      place(item, p);
    }
    if (showPreview) {
      for (const [id, node] of view.previewNodes) if (!previewIds.has(id)) {
        node.remove(); view.previewNodes.delete(id); previewChanged = true;
      }
      if (previewChanged && !view.details.open) {
        cancelMotion(view.previewMotion);
        const height = view.preview.getBoundingClientRect().height;
        if (height !== previewHeight) view.previewMotion = motion(view.preview, [
          { height: `${previewHeight}px`, overflow: 'clip' }, { height: `${height}px`, overflow: 'clip' },
        ]);
      }
    } else hidePreview(view, answering);
    const ids = new Set();
    for (const item of events.filter(item => progress.includes(item) || reasoning.includes(item) || tools.includes(item))) {
      ids.add(item.id);
      let node = view.nodes.get(item.id);
      if (!node) {
        node = item.kind === 'tool' && vmTools.has(item.name) ? vmView('agent-activity-tool agent-vm')
          : document.createElement(item.kind === 'progress' ? 'p' : 'div');
        if (!node.className) node.className = item.kind === "tool" ? "agent-activity-tool" : item.kind === 'progress' ? 'agent-activity-update' : "agent-activity-reasoning";
        view.nodes.set(item.id, node);
        view.content.appendChild(node);
        if (item.kind === 'progress' && view.details.open && running) reveal(node);
      }
      if (item.kind === "tool" && vmTools.has(item.name)) {
        updateVm(node, item);
      } else if (item.kind === "tool") {
        const signature = JSON.stringify([item, textOnly]);
        if (node.dataset.signature !== signature) {
          node.dataset.signature = signature;
          node.dataset.status = item.status;
          const pills = [];
          for (const source of (Array.isArray(item.sources) ? item.sources : []).slice(0, 5)) {
            try {
              if (typeof source.url !== "string" || source.url.length > 2048) continue;
              const url = new URL(source.url);
              if (!["https:", "http:"].includes(url.protocol) || url.username || url.password) continue;
              const pill = sourcePill(url, String(source.title || '').slice(0, 200));
              pill.target = "_blank";
              pill.rel = "noopener noreferrer";
              pills.push(pill);
            } catch (_) { /* Ignore invalid provider URLs. */ }
          }
          const title = document.createElement("strong");
          title.textContent = historyTitle(item, textOnly, pills.length > 0);
          node.replaceChildren(title);
          if (item.text) {
            const text = document.createElement("p");
            text.textContent = String(item.text).slice(0, 8000);
            node.appendChild(text);
          }
          if (pills.length) {
            const row = document.createElement("span");
            row.className = "agent-activity-sources";
            row.append(...pills);
            node.appendChild(row);
          }
        }
      } else {
        const text = item.kind === 'progress' ? item.text : compactReasoning(item.text);
        if (node.textContent !== window.App.t(text)) node.textContent = text;
        node.setAttribute("aria-label", item.kind === 'progress' ? 'Progress update' : item.summary_source === "excerpt" || item.format === "text" ? "Reasoning highlights" : "Reasoning summary");
      }
    }
    for (const [id, node] of view.nodes) if (!ids.has(id)) { node.remove(); view.nodes.delete(id); }
    const currentStep = running && (!activeTool || waiting || reconnecting) ? heading : '';
    if (currentStep) {
      const label = view.current.firstElementChild;
      if (label.textContent !== window.App.t(currentStep)) label.textContent = currentStep;
      // After the comparisons too; appended once, a move would restart its shine.
      if (view.timeline.lastElementChild !== view.current) view.timeline.append(view.current);
    } else view.current.remove();
    view.timeline.classList.toggle('has-current', Boolean(currentStep));
    view.content.hidden = !progress.length && !reasoning.length && !tools.length;
    App.agentReview?.renderActivity(view.insights, review, answerText);
    view.timeline.classList.toggle('has-insights', !view.insights.hidden);
    view.note.textContent = progress.length || !view.insights.hidden ? '' : reasoning.length ? (reasoning[0].summary_source === "excerpt" || reasoning[0].format === "text"
      ? "Short excerpts from the model’s reasoning." : "Model-provided reasoning summary.") : truncated ? "Reasoning highlights only."
      : !reasoning.length ? (running ? "Waiting for the model’s response."
        : "No detailed progress updates were saved for this response.") : "";
    if (finishReason === "length") {
      // A sentence of its own, so it is translated on its own (docs/i18n.md).
      const limit = document.createElement("span");
      limit.textContent = "The response reached its output limit.";
      view.note.append(view.note.textContent ? " " : "", limit);
    }
    view.note.hidden = !view.note.textContent;
    const measured = usage && Number.isFinite(usage.input_tokens) && Number.isFinite(usage.output_tokens);
    const number = App.format.number;
    const total = measured ? number(usage.input_tokens + usage.output_tokens) : "";
    // Translated part by part: the line is put together from several.
    const tokens = !measured ? App.t("Usage unavailable")
      : usage.complete === false ? App.t("{total} measured tokens · usage incomplete", { total }) : App.t("{total} tokens", { total });
    const dollars = Number.isFinite(usage?.estimated_cost_nano_usd) ? usage.estimated_cost_nano_usd / 1e9 : NaN;
    const providerCost = usage?.cost_source === "provider";
    const amount = `${providerCost ? "" : "~"}$${Number.isFinite(dollars) ? dollars.toFixed(dollars > 0 && dollars < .0001 ? 6 : 4) : ""}`;
    const kind = App.t(providerCost ? "provider cost" : "estimated");
    const cost = !Number.isFinite(dollars) ? ""
      : usage.cost_complete === false ? ` · ${App.t("at least {amount} {kind} · cost incomplete", { amount, kind })}`
      : ` · ${amount} ${kind}`;
    // The commands' summed run time in the agent's VM (agent_vm_tools.py).
    const vmTime = Number.isFinite(vm?.seconds) && vm.commands > 0
      ? ` · ${App.t("VM {time}", { time: App.format.duration(vm.seconds * 1000) })}` : "";
    view.usageEl.textContent = tokens + cost + vmTime;
    view.usageEl.title = measured ? `${number(usage.input_tokens)} input · ${number(usage.output_tokens)} output tokens` : "The provider did not report token usage.";
    view.usageEl.hidden = running;
    // A history the reader opened stays open while it is on screen: closing
    // it there moved the answer below. Above the viewport the correction in
    // render() keeps the reading position, so it can tidy itself up.
    if (finished && (offscreenUpdate || !view.details.open)) disclosure(view, false);
  }

  function renderTurn(host, turn) {
    const events = turn?.agent_activity || [];
    const terminal = events.filter(item => item.kind === "status" && ["succeeded", "failed", "cancelled", "canceled"].includes(item.status)).at(-1);
    const status = turn?.error_code === "cancelled" ? "cancelled" : terminal?.status
      || (turn?.status === "failed" ? "failed" : "succeeded");
    render(host, { events, usage: turn?.agent_usage, status, truncated: turn?.agent_reasoning_truncated,
      finishReason: turn?.agent_finish_reason, elapsedMs:savedDuration(turn),
      review: turn?.agent_review, answerText: turn?.assistant_response ?? turn?.consensus ?? '', settings: turn?.agent_settings,
      vm: turn?.agent_vm });
  }
  App.agentActivity = { receive, render, renderTurn, label, reveal, dispose, savedDuration };
})();
