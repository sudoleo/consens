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
    // A picture from the web under the answer (agent_web_images.py; pictureSummary).
    show_image: ['Picture', 'Getting a picture…', 'Showed a picture'],
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
    // The user's earlier chats (agent_chat_search.py); one opened says so (stepLabel).
    search_chats: ['Your chats', 'Searching your chats…', 'Searched your chats'],
    // The agent's own VM (agent_vm_tools.py); each call also shows as a
    // compact block of its own (vmView).
    vm_exec: ['Command', 'Running a command…', 'Ran a command'],
    vm_read_file: ['Read file', 'Reading a file…', 'Read a file'],
    vm_write_file: ['Write file', 'Writing a file…', 'Wrote a file'],
    vm_edit_file: ['Edit file', 'Editing a file…', 'Edited a file'],
    vm_share_file: ['Share file', 'Sharing a file…', 'Shared a file'],
    github_import: ['GitHub', 'Importing a repository…', 'Imported a repository'],
    update_plan: ['Plan', 'Updating the plan…', 'Updated the plan'],
    vm_start_process: ['Background process', 'Starting a background process…', 'Started a background process'],
    vm_process_output: ['Background process', 'Reading a background process…', 'Read a background process'],
    vm_stop_process: ['Background process', 'Stopping a background process…', 'Stopped a background process'],
    vm_view_image: ['Picture', 'Looking at a picture…', 'Looked at a picture'],
    vm_install_packages: ['Install', 'Installing packages…', 'Installed packages'],
    // The workspace's browser, a computer of its own (agent_browser.py).
    browser: ['Browser', 'Using the browser…', 'Used the browser'],
    request_domain: ['Network', 'Asking for access…', 'Got access'],
    // The user's turn (agent_ask.py): the card above the field says what for.
    ask_user: ['Your turn', 'Waiting for you…', 'Asked you'],
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
  // "Showed a picture · liquipedia.net"; a site that gave none says so.
  function pictureSummary(item) {
    if (item.status !== 'succeeded') return null;
    const host = typeof item.host === 'string' && /^[\w.-]{1,253}$/.test(item.host) ? item.host : '';
    if (item.outcome === 'failed') return 'Couldn’t get the picture';
    return host ? `Showed a picture · ${host}` : tools.show_image[2];
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
    if (item.name === 'show_image' && pictureSummary(item)) return pictureSummary(item);
    if (item.name === 'search_chats' && item.opened && ['running', 'succeeded'].includes(item.status)) {
      return item.status === 'running' ? 'Opening an earlier chat…' : 'Read an earlier chat';
    }
    if (item.status === 'running') return tools[item.name]?.[1] || 'Working on a step…';
    if (item.status === 'succeeded' && item.name === 'web_search') return searchSummary(item);
    if (item.status === 'succeeded') return tools[item.name]?.[2] || `${toolName(item.name)} · Completed`;
    // Translated part by part: "{tool} · {state}" has no entry of its own.
    const state = {failed:'Failed', cancelled:'Stopped', blocked:'Skipped', unknown:'Usage unavailable'}[item.status] || 'Details';
    return `${App.t(toolName(item.name))} · ${App.t(state)}`;
  }
  // A turn's working time: from its start to its end without the time it
  // waited for the user (agent_wait_seconds, chat_store.turn_detail: its
  // pauses and the agent's questions). The server's turn clock leaves that
  // out as well (_turn_elapsed), and the head stands still while it waits
  // (UX audit E1): a pause that ran into its 30 minutes read "Thought for 32m 4s".
  function savedDuration(turn) {
    const start = Date.parse(turn?.created_at);
    const end = Date.parse(turn?.completed_at || turn?.failed_at);
    if (!(Number.isFinite(start) && Number.isFinite(end) && end >= start)) return null;
    const waited = Number.isFinite(turn?.agent_wait_seconds) && turn.agent_wait_seconds > 0 ? turn.agent_wait_seconds * 1000 : 0;
    return Math.max(0, end - start - waited);
  }
  // "23s", "3m 7s": the one way the app writes a span (App.format).
  function durationText(ms) {
    return App.format.duration(ms);
  }
  // One word for what a run does now, the same in the activity's head, the
  // chat list (run-view.js) and the tab title (tab-status.js), UX audit E1/E2:
  // before, the head said "Working for" while the reviewers checked the
  // answer and while the run waited for the user, and the chat list
  // "Thinking" or a cut "Writing ans…" at the same moment.
  const PHASE_WORDS = Object.freeze({ working: 'Working', reviewing: 'Reviewing', checking: 'Checking',
    paused: 'Paused', asking: 'Waiting for you' });
  function phase({ asking = false, held = false, review = null } = {}) {
    if (asking) return 'asking';
    if (held) return 'paused';
    if (review?.status === 'running') return review.mode === 'audit' ? 'reviewing' : 'checking';
    return 'working';
  }
  // Every word the head writes before its clock, each alone in its element
  // (the page translates it on its own; tests/test_i18n.py reads this list):
  // until 2026-10-29 "Failed after" and "Stopped after" had no German alone
  // and stood in English before "0 Sek." (I3).
  const HEAD_VERBS = Object.freeze({ working: 'Working for', reviewing: 'Reviewing', checking: 'Checking',
    paused: 'Paused', asking: 'Waiting for you', succeeded: 'Thought for', failed: 'Failed after',
    cancelled: 'Stopped after' });
  // "Working for 12s" while it works, "Reviewing · 2m 19s" while the
  // reviewers check the written answer, "Paused · 1m 4s" (the clock stands
  // still) while it waits for the user, "Thought for 3m 7s" once it is done.
  function titleParts(ms, now, status) {
    if (!Number.isFinite(ms)) return { verb: now ? PHASE_WORDS[now] : statuses[status] || 'Activity', gap: '', time: '' };
    const time = durationText(ms);
    if (now) return { verb: HEAD_VERBS[now], gap: now === 'working' ? ' ' : ' · ', time };
    const settled = status === 'failed' ? 'failed' : statuses[status] === statuses.cancelled ? 'cancelled' : 'succeeded';
    return { verb: HEAD_VERBS[settled], gap: ' ', time };
  }
  // The clock ticks in a field of fixed width, so the chevron and the model
  // icons after it do not move with every second (Apple audit A7): the time
  // sits in a slot as wide as its largest value in the same unit ("59s",
  // "9m 59s"), and the verb ("Working for" / "Thought for") takes the width
  // of the wider of the two, so the end of the run changes the words, not
  // the line. A change of state (Reviewing, Paused) or of the slot glides
  // the head once to its new width.
  const SETTLED_VERBS = { running: HEAD_VERBS.working, done: HEAD_VERBS.succeeded };
  const SLOTS = ["seconds", "minutes", "long"];
  function setTitle(view, ms, now, status) {
    const { verb, gap, time } = titleParts(ms, now, status);
    const label = `${verb}${gap}${time}`;
    if (view.title.dataset.label === window.App.t(label)) return;
    view.title.dataset.label = label;
    const verbEl = view.title.querySelector(".agent-activity-verb-text");
    const gapEl = view.title.querySelector(".agent-activity-gap");
    const timeEl = view.title.querySelector(".agent-activity-time");
    const seconds = Math.floor(Math.max(0, ms || 0) / 1000);
    const unit = !time ? "" : seconds < 60 ? "seconds" : seconds < 600 ? "minutes" : "long";
    // A live clock holds the slot of its own unit: the minutes slot from
    // the first second left a wide gap before the chevron for a whole
    // minute. The label a run ends with keeps at least the slot it ticked
    // in, so the end of the run does not move the line.
    if (now && unit) view.liveSlot = unit;
    const slot = now || !unit || !view.liveSlot ? unit
      : SLOTS[Math.max(SLOTS.indexOf(view.liveSlot), SLOTS.indexOf(unit))];
    const resize = view.title.isConnected && Boolean(verbEl.textContent) && (verbEl.textContent !== window.App.t(verb)
      || gapEl.textContent !== gap || (Boolean(timeEl.dataset.unit) && timeEl.dataset.unit !== slot));
    const from = resize ? view.title.getBoundingClientRect().width : 0;
    if (resize) cancelMotion(view.slotMotion);
    if (verbEl.textContent !== window.App.t(verb)) verbEl.textContent = verb;
    // While it works, the verb it will end with stands invisibly in the same
    // cell (agent-chat.css), so the field is as wide as the wider one; it is
    // no text of the title. Once it is over the clock is still and the field
    // takes its own words: "Fertig nach" kept the width of "Arbeitet seit",
    // a double gap before the time (UX audit B14/R19).
    const paired = now && verb === SETTLED_VERBS.running ? SETTLED_VERBS.done : "";
    const holder = verbEl.parentElement;
    if (paired) holder.dataset.ghost = paired; else delete holder.dataset.ghost;
    if (gapEl.textContent !== gap) gapEl.textContent = gap;
    if (timeEl.textContent !== window.App.t(time)) timeEl.textContent = time;
    timeEl.dataset.unit = slot;
    if (!resize) return;
    // The chevron glides to its new place while the new words open up (none
    // with reduced motion, motion()); the words keep to one line meanwhile.
    const to = view.title.getBoundingClientRect().width;
    view.slotMotion = from && to && from !== to ? motion(view.title, [
      { width: `${from}px`, minWidth: `${from}px`, overflow: 'clip', whiteSpace: 'nowrap' },
      { width: `${to}px`, minWidth: `${to}px`, overflow: 'clip', whiteSpace: 'nowrap' },
    ]) : null;
  }
  // `now`: the phase of a running run, or null once it is over. While it
  // waits for the user the clock stands still.
  function updateClock(view, elapsedMs, now, status) {
    clearInterval(view.clockTimer);
    view.clockTimer = null;
    const ticking = Boolean(now) && now !== 'paused' && now !== 'asking';
    const at = performance.now();
    const previous = Number.isFinite(view.elapsedMs) ? view.elapsedMs + (view.clockRunning ? at - view.clockAt : 0) : null;
    view.elapsedMs = Number.isFinite(elapsedMs) ? Math.max(0, elapsedMs) : previous ?? (now ? 0 : null);
    view.clockAt = at;
    view.clockRunning = ticking;
    const tick = () => {
      const elapsed = view.elapsedMs === null ? null : view.elapsedMs + (view.clockRunning ? performance.now() - view.clockAt : 0);
      setTitle(view, elapsed, now, status);
    };
    tick();
    if (ticking) view.clockTimer = setInterval(tick, 1000);
  }
  // The time a live run waited for the user on this page, so far, on the
  // caller's clock: the wall clock since the start (agent-chat.js).
  function waitedMs(view, waiting) {
    const at = Date.now();
    if (waiting && view.waitStart == null) view.waitStart = at;
    if (!waiting && view.waitStart != null) {
      view.waited = (view.waited || 0) + at - view.waitStart;
      view.waitStart = null;
    }
    return (view.waited || 0) + (view.waitStart != null ? at - view.waitStart : 0);
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

  // Room in a live run's activity besides its steps: status and reasoning
  // entries, and apart from them the pauses (as many as a turn saves in
  // agent_holds, A-M5).
  const AUXILIARY_ENTRIES = 63, HOLD_ENTRIES = 20;
  function receive(events, event) {
    if (event?.version !== 1 || !["status", "progress", "reasoning", "usage", "tool", "hold"].includes(event.kind) || typeof event.id !== "string") return;
    const existing = events.find(item => item.id === event.id);
    if (existing && event.append && event.kind === "reasoning") {
      existing.text = (existing.text + String(event.text || "")).slice(0, 32000);
    } else if (existing) {
      Object.assign(existing, event);
      if (event.kind === 'status') { events.splice(events.indexOf(existing), 1); events.push(existing); }
    } else {
      // Keep commentary and confirmed steps together for the full timeline.
      // Pauses have room of their own (A-B7): in a long run the many status
      // and reasoning entries pushed earlier pauses out of the live activity.
      const own = event.kind === 'hold' ? item => item.kind === 'hold'
        : item => !['progress', 'tool', 'hold'].includes(item.kind);
      if (!['progress', 'tool'].includes(event.kind)) {
        const limit = event.kind === 'hold' ? HOLD_ENTRIES : AUXILIARY_ENTRIES;
        const auxiliary = events.filter(own);
        for (const item of auxiliary.slice(0, Math.max(0, auxiliary.length - limit))) events.splice(events.indexOf(item), 1);
      }
      // A progress note keeps the agent's whole text beside a tool call
      // (agent_answer_mode.NOTE_CHARS); status lines are short anyway.
      events.push({ ...event, text: String(event.text || "").slice(0, event.kind === "progress" || event.kind === "tool" ? 8000 : 32000) });
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
  // model's default (the same words as the answer's label). The name stays
  // as it is, the reasoning is translated on its own: on the German page
  // "{0} reasoning" took the whole line ("Nachdenken: Claude Sonnet 5.5 ·
  // High"), and the line was written anew on every render because the page
  // translates data-label, which it was compared with (2026-10-23).
  function renderRunDetails(view, settings) {
    const text = settings?.label ? label(settings) : '';
    view.runDetails.hidden = !text;
    if (view.runDetailsText === text) return;
    view.runDetailsText = text;
    view.runDetails.replaceChildren();
    if (!text) return;
    const name = document.createElement('span');
    name.setAttribute('data-i18n-skip', '');
    name.textContent = settings.label;
    view.runDetails.append(name);
    const effort = settings.reasoning_effort;
    if (!effort || effort === 'default') return;
    const reasoning = document.createElement('span');
    reasoning.textContent = effort === 'none' ? 'Reasoning off' : `${effortName(effort)} reasoning`;
    view.runDetails.append(' · ', reasoning);
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
    'github_import', 'vm_start_process', 'vm_process_output', 'vm_stop_process', 'vm_view_image',
    'vm_install_packages', 'browser', 'request_domain']);
  const vmVerbs = { vm_read_file: ['Reading the file', 'Read the file'],
    vm_write_file: ['Writing the file', 'Wrote the file'], vm_edit_file: ['Editing the file', 'Edited the file'],
    vm_share_file: ['Sharing the file', 'Shared the file'],
    github_import: ['Importing the repository into', 'Imported the repository into'],
    vm_start_process: ['Starting in the background', 'Started in the background'],
    vm_process_output: ['Reading the output of process', 'Read the output of process'],
    vm_stop_process: ['Stopping process', 'Stopped process'],
    vm_view_image: ['Looking at the picture', 'Looked at the picture'],
    vm_install_packages: ['Installing', 'Installed'],
    request_domain: ['Asking for access to', 'Access to'] };
  // A browser step by its action (agent_browser.py): what it did and to what.
  const browserVerbs = { open: ['Opening', 'Opened'], read: ['Reading the page', 'Read the page'],
    text: ['Reading the page', 'Read the page'], find: ['Searching the page for', 'Searched the page for'],
    click: ['Clicking', 'Clicked'], drag: ['Dragging', 'Dragged'], type: ['Typing into', 'Typed into'],
    select: ['Choosing in', 'Chose in'], key: ['Pressing', 'Pressed'], scroll: ['Scrolling', 'Scrolled'],
    back: ['Going back', 'Went back'], forward: ['Going forward', 'Went forward'],
    tabs: ['Listing the tabs', 'Listed the tabs'], tab: ['Switching the tab', 'Switched the tab'],
    screenshot: ['Taking a screenshot', 'Took a screenshot'], upload: ['Uploading', 'Uploaded'],
    download: ['Downloading', 'Downloaded'], wait: ['Waiting for the page', 'Waited for the page'] };
  // A page by its name: the host of its address, without "www.".
  function hostOf(address) {
    try {
      const url = new URL(String(address || ''));
      return ['http:', 'https:'].includes(url.protocol) ? url.hostname.replace(/^www\./, '') : '';
    } catch (_) { return ''; }
  }
  // What a step names, in its own type (UX audit A8/A9): a command, a path
  // or code in mono; a search term on a page as a quote in the text's type
  // („Förderfähige Kosten“); an opened page by its title (its host after it,
  // the address on hover). Before, all three stood in mono, the page as its
  // raw address.
  function vmTargetKind(item) {
    if (item.name !== 'browser') return 'code';
    if (item.action === 'find' && item.query) return 'quote';
    if (item.action === 'open' && (item.title || hostOf(item.url))) return 'text';
    return 'code';
  }
  function vmTarget(item) {
    if (['vm_exec', 'vm_start_process'].includes(item.name)) return item.command;
    if (item.name === 'vm_install_packages') return Array.isArray(item.packages) ? item.packages.join(' ') : '';
    if (item.name === 'request_domain') return item.domain;
    if (item.name === 'browser') {
      if (item.action === 'open') return item.title || hostOf(item.url) || item.url;
      return item.action === 'download' ? item.url || item.downloads?.[0] || item.title
        : item.action === 'upload' ? item.file
        : item.action === 'key' ? item.key : item.action === 'find' ? item.query
        // A place of the screenshot, or how many strokes (agent_browser._activity).
        : item.action === 'drag' && Number.isInteger(item.strokes)
          ? App.t(item.strokes === 1 ? '1 stroke' : '{count} strokes', { count: item.strokes })
        : item.ref || item.at || item.title;
    }
    return item.path || item.process;
  }
  // The glossary's word: the workspace, never "VM" on the page (docs/i18n.md).
  const vmOutcomes = { unavailable: 'Workspace not available', no_time: 'Skipped · no time left',
    day_limit: 'Skipped · VM time for today used up', busy: 'Skipped · workspace in use by another chat' };
  function vmMeta(item) {
    if (vmOutcomes[item.outcome]) return App.t(vmOutcomes[item.outcome]);
    if (item.status === 'running') return ['vm_exec', 'vm_install_packages'].includes(item.name) ? App.t('Running…') : '';
    // A background process that still runs once its call is done.
    if (item.process_status === 'running') return App.t('Running in the background');
    // Ended by vm_stop_process: no exit code (timeout's 124 read as its limit).
    if (item.status === 'cancelled' || item.process_status === 'stopped') return App.t('Stopped');
    if (item.status === 'failed') return App.t('Failed');
    const parts = [];
    if (item.timed_out) parts.push(App.t('Timed out'));
    else if (Number.isInteger(item.exit_code) && item.exit_code !== 0) {
      // A command's exit code is its verdict, in words (UX audit F1); a
      // stopped process's code (143) is only how it ended.
      parts.push(commandFailed(item) ? App.t('Failed · code {code}', { code: item.exit_code })
        : App.t('Exit {code}', { code: item.exit_code }));
    }
    // The opened page's host after its title (vmTarget).
    if (vmTargetKind(item) === 'text' && item.title && hostOf(item.url)) parts.push(hostOf(item.url));
    // A quick command needs no clock ("0s" says nothing).
    if (Number.isFinite(item.duration_ms) && item.duration_ms >= 1000) parts.push(App.format.duration(item.duration_ms));
    return parts.join(' · ');
  }
  // A command that ended with an error (or ran out of time), or a step that
  // failed: its line says so in the disagreement's tone (agent-chat.css).
  // Before, "Exit 1" stood as grey as "3s" beside a command that worked,
  // and data-status said "succeeded".
  const commandTools = new Set(['vm_exec', 'vm_install_packages']);
  function commandFailed(item) {
    return item.status === 'succeeded' && commandTools.has(item.name)
      && (item.timed_out === true || (Number.isInteger(item.exit_code) && item.exit_code !== 0));
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
    // A step in the workspace's browser: watch it live (workspace-view.js).
    const watch = document.createElement('button'); watch.type = 'button'; watch.className = 'agent-vm-watch';
    watch.hidden = true;
    watch.addEventListener('click', event => {
      event.preventDefault();
      event.stopPropagation();
      App.workspaceView?.open();
    });
    summary.append(verb, target, meta, watch);
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
      item.exit_code, item.duration_ms, item.timed_out, item.outcome, item.action, item.url, item.ref, item.page,
      item.title, item.packages, item.domain, item.query]);
    if (details.dataset.signature === signature) return;
    details.dataset.signature = signature;
    details.dataset.status = item.status;
    details.dataset.tool = item.name;
    if (item.status === 'failed' || commandFailed(item)) details.dataset.outcome = 'failed';
    else delete details.dataset.outcome;
    const [verb, target, meta] = details.firstElementChild.children;
    const verbs = item.name === 'browser' ? browserVerbs[item.action] : vmVerbs[item.name];
    verb.hidden = !verbs;
    verb.textContent = verbs ? App.t(verbs[item.status === 'running' ? 0 : 1]) : '';
    details.dataset.target = vmTargetKind(item);
    target.textContent = String(vmTarget(item) || '');
    // An opened page's address, on hover.
    if (details.dataset.target === 'text' && item.url) target.title = String(item.url).slice(0, 500);
    else target.removeAttribute('title');
    meta.textContent = vmMeta(item);
    const watch = details.firstElementChild.children[3];
    watch.hidden = !(item.name === 'browser' && document.body.classList.contains('viewer-has-workspace')
      && Boolean(App.workspaceView));
    watch.textContent = App.t('Watch live');
    const output = details.lastElementChild;
    // A browser step shows the page as it read it; a command its output.
    const text = String((item.name === 'browser' ? item.page : item.output) || '');
    output.textContent = text && item.output_truncated ? `…\n${text}` : text;
    output.hidden = !text;
    details.classList.toggle('has-output', Boolean(text));
    if (!('chosen' in details.dataset)) details.open = item.status === 'running' && Boolean(text);
    if (details.open) output.scrollTop = output.scrollHeight;
  }

  // The agent's plan (agent_plan.py, update_plan), like Claude Code's todo
  // list: its steps as a checklist, the latest pinned above the live
  // progress, each change folded in the timeline. The steps are the model's
  // words, data that stays untranslated; the line above them goes through App.t.
  const planStates = { completed: 'Done', in_progress: 'In progress', pending: 'To do' };
  const hasPlan = item => item.kind === 'tool' && item.name === 'update_plan' && Array.isArray(item.items)
    && item.items.length > 0;
  function planView(className) {
    const details = document.createElement('details');
    details.className = className;
    const summary = document.createElement('summary');
    summary.className = 'agent-plan-head';
    summary.dataset.i18nSkip = '';
    const list = document.createElement('ol');
    list.className = 'agent-plan-list';
    list.translate = false;
    list.dataset.i18nSkip = '';
    details.append(summary, list);
    summary.addEventListener('click', () => { details.dataset.chosen = ''; });
    return details;
  }
  function updatePlan(details, item, open) {
    const steps = item.items.slice(0, 20);
    const signature = JSON.stringify([item.status, steps]);
    if (details.dataset.signature === signature) return;
    details.dataset.signature = signature;
    details.dataset.status = item.status;
    const done = steps.filter(step => step.status === 'completed').length;
    details.firstElementChild.textContent = item.status === 'failed' ? App.t('Plan not updated')
      : App.t('Plan · {done} of {total} done', { done, total: steps.length });
    details.lastElementChild.replaceChildren(...steps.map(step => {
      const li = document.createElement('li');
      const status = planStates[step.status] ? step.status : 'pending';
      const text = String(step.content || '').slice(0, 200);
      li.dataset.status = status;
      li.textContent = text;
      // The mark is drawn by CSS; a screen reader hears the state in words.
      li.setAttribute('aria-label', `${App.t(planStates[status])}: ${text}`);
      return li;
    }));
    if (!('chosen' in details.dataset)) details.open = open;
  }

  // A message the user sent into the running response (agent-chat.js
  // steer): the user's own words, never translated, under a quiet "You".
  // A reviewer's halt (agent_audit.py): who paused the work, why (the
  // reviewer's own sentence) and what the user decided (agent-chat.js
  // renderHold has the card).
  // "unchecked" (agent_gate.py, since 2026-10-27): a step that acts outside
  // the workspace that not every reviewer could check before it ran.
  const holdKinds = { safety: 'Security-critical step', harm: 'Possible damage', off_goal: 'Far off your request',
    injection: 'Prompt injection', unchecked: 'Not checked', domain: 'Network access' };
  const holdStates = { waiting: 'Waiting for your decision', continue: 'You let the work go on',
    steer: 'You wrote to the agent', stop: 'You stopped the response', deny: 'You did not allow it',
    timeout: 'Stopped after 30 minutes without a decision', ended: 'Over when the response ended' };
  // A request for a domain (agent_domains.py) is the user's to decide, not a
  // reviewer's pause. Undecided it stays closed and the work goes on (UX
  // audit 2026-10-29 C8: this said "Stopped after 30 minutes").
  const domainStates = { ...holdStates, continue: 'You allowed it for this chat',
    timeout: 'Not allowed after 30 minutes without a decision' };
  // The agent's own question to the user (ask_user, agent_ask.py; since
  // 2026-10-29): their turn in the browser, their yes to a step, or a call
  // that waited while they had the browser. Its request is data.
  const askHeads = { browser: 'The agent asked you to take over the browser', confirm: 'The agent asked before a step',
    secret: 'The agent asked you for a key', takeover: 'The agent waited while you had the browser' };
  // While it still waits, in the present (C14: "The agent asked …" stood over "Waiting for you").
  const askHeadsNow = { browser: 'The agent asks you to take over the browser', confirm: 'The agent asks before a step',
    secret: 'The agent asks you for a key', takeover: 'You have the browser' };
  const askStates = { ...holdStates, waiting: 'Waiting for you', handed_back: 'You handed the browser back',
    timeout: 'No answer within 30 minutes' };
  const confirmStates = { ...askStates, continue: 'You allowed it' };
  const secretStates = { ...askStates, continue: 'You saved it in the workspace', deny: 'You did not give it' };
  function holdView(className) {
    const node = document.createElement('div');
    node.className = className;
    const head = document.createElement('strong');
    const reason = document.createElement('p');
    reason.className = 'agent-hold-step-reason';
    reason.dataset.i18nSkip = '';
    const state = document.createElement('span');
    state.className = 'agent-hold-step-state';
    node.append(head, reason, state);
    Object.assign(node, { _head: head, _reason: reason, _state: state });
    return node;
  }
  function updateHold(node, item) {
    if (item.ask) {
      const states = item.ask === 'confirm' ? confirmStates : item.ask === 'secret' ? secretStates : askStates;
      const state = states[item.state] ? item.state : 'waiting';
      const signature = JSON.stringify([item.ask, item.request, state]);
      if (node.dataset.signature === signature) return;
      node.dataset.signature = signature;
      node.dataset.state = state;
      const heads = state === 'waiting' ? askHeadsNow : askHeads;
      node._head.textContent = heads[item.ask] || heads.confirm;
      node._reason.textContent = String(item.request || '').slice(0, 400);
      node._reason.hidden = state === 'waiting' || !item.request;
      node._state.textContent = states[state];
      return;
    }
    const state = holdStates[item.state] ? item.state : 'waiting';
    const signature = JSON.stringify([item.reviewer, item.halt, item.reason, state, item.domain]);
    if (node.dataset.signature === signature) return;
    node.dataset.signature = signature;
    node.dataset.state = state;
    const domain = item.halt === 'domain' && item.domain;
    node._head.textContent = domain ? App.t(state === 'waiting' ? 'The agent asks to reach {domain}' : 'The agent asked to reach {domain}',
      { domain: String(item.domain) })
      : item.reviewer ? App.t('Paused by {reviewer}', { reviewer: String(item.reviewer) })
      : item.halt === 'unchecked' ? 'Paused before a step ran' : 'Paused by a reviewer';
    node._reason.textContent = String(item.reason || '').slice(0, 400);
    // While it waits, the card above the field says why; the history keeps
    // the reason once the user decided (on a phone both stood one above the other).
    node._reason.hidden = state === 'waiting';
    node._state.textContent = `${App.t(holdKinds[item.halt] || 'Needs your decision')} · ${App.t((domain ? domainStates : holdStates)[state])}`;
  }

  // A step's thinking line (agent_delegation `completion:N/thinking`).
  const isThought = item => item.kind === 'progress' && /\/thinking$/.test(String(item.id || ''));
  // What a step thought, in its opened history (ReasoningProgress.sections,
  // UX audit A2): each heading over its paragraphs, as ChatGPT and Claude
  // open "Thought for …". Before, a step kept only its newest line, and a
  // provider summary only its headings. The words are the model's: never
  // translated; a step still thinking (no sections yet) shows its line.
  function updateThought(node, item) {
    const sections = (Array.isArray(item.sections) ? item.sections : [])
      .filter(section => section && (section.title || section.text)).slice(0, 40);
    const signature = JSON.stringify([item.text, sections]);
    if (node.dataset.signature === signature) return;
    node.dataset.signature = signature;
    const paragraph = (text, className) => {
      const p = document.createElement('p');
      if (className) p.className = className;
      p.dataset.i18nSkip = '';
      p.translate = false;
      p.textContent = String(text).slice(0, 4000);
      return p;
    };
    node.replaceChildren(...(sections.length ? sections.flatMap(section => [
      ...(section.title ? [paragraph(section.title, 'agent-thought-title')] : []),
      ...String(section.text || '').split(/\n{2,}/).filter(text => text.trim()).map(text => paragraph(text)),
    ]) : [paragraph(item.text)]));
  }

  function userNote(className, text) {
    const p = document.createElement('p');
    p.className = className;
    const who = document.createElement('span');
    who.className = 'agent-user-note-who';
    who.textContent = 'You';
    const words = document.createElement('span');
    words.className = 'agent-user-note-text';
    words.dataset.i18nSkip = '';
    words.translate = false;
    words.textContent = String(text || '').slice(0, 4000);
    p.append(who, words);
    return p;
  }

  // Like Claude Code, a run that works in its VM folds its earlier steps into
  // one line ("Ran 4 commands"); the note that leads into the latest command,
  // that command and what follows stay in view. Until 2026-10-26 every
  // command and every note between them stood one under the other, a screen
  // long. A step that waits on the reader never folds away.
  // The live lines stay a few: the step at work (with the note leading into
  // it), and whatever waits on the user; every earlier step folds into one
  // line, in every run (2026-10-28, Max: a long run grew the live lines down
  // the screen, and their growing and folding made the page jump). Until
  // then only a VM run folded, up to its latest command.
  function foldPast(paragraphs) {
    // The step at work, not the "Thinking…" row that stands after it.
    const lastStep = paragraphs.findLastIndex(item => (item.kind === 'vm' || item.kind === 'step')
      && item.id !== 'current-status');
    let start = lastStep;
    while (start > 0 && paragraphs[start - 1].kind === 'progress' && !paragraphs[start - 1].quiet) start--;
    const waits = paragraphs.findIndex(item => item.kind === 'review'
      || (item.kind === 'hold' && (item.item.state || 'waiting') === 'waiting'));
    const past = paragraphs.slice(0, waits >= 0 ? Math.min(start, waits) : start);
    const steps = past.filter(item => !['progress', 'user', 'hold'].includes(item.kind));
    if (steps.length < 2) return null;
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
    highlights = [], reconnecting = false, vm = null, vmRestore = null } = {}) {
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
      // The VM back to its checkpoint before this message (agent-chat.js
      // restoreVm, admins): a quiet action under the usage line.
      const vmRestoreEl = document.createElement("button");
      vmRestoreEl.type = "button";
      vmRestoreEl.className = "agent-vm-restore audit-only";
      vmRestoreEl.textContent = "Restore the VM to before this message";
      vmRestoreEl.hidden = true;
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
      history.append(timeline, note, runDetails, usageEl, vmRestoreEl);
      details.append(summary, history);
      // Progress shows at the model icons in the summary (agent-chat.css,
      // "Progress at the models"), not on a line of its own.
      host.replaceChildren(details, preview);
      host._agentActivity = { details, summary, history, title, timeline, runDetails, insights, content, current, note, usageEl, vmRestoreEl, preview, nodes: new Map(), previewNodes: new Map() };
      vmRestoreEl.addEventListener('click', () => host._agentActivity.vmRestore?.());
      summary.addEventListener('click', event => {
        event.preventDefault();
        const view = host._agentActivity;
        disclosure(view, !(view.disclosureTarget ?? details.open));
      });
    }
    const view = host._agentActivity;
    const progress = events.filter(item => item.kind === 'progress' && item.text);
    // Reasoning stays beside the agent's notes (UX audit A1): until
    // 2026-10-29 any progress line, a note as much as a gate or retry line,
    // hid every thought of the run, live and saved (a rule from the time
    // progress lines were summaries standing in for it). Only a step's
    // reasoning that its own note repeats word for word stands back.
    const said = step => progress.filter(item => item.step_id === step).map(item => item.text).join('\n');
    const reasoning = events.filter(item => item.kind === "reasoning" && ["text", "summary"].includes(item.format)
      && item.text && !(item.step_id && compactReasoning(item.text).split('\n').every(line => said(item.step_id).includes(line))));
    // Older saved turns mistook a missing search counter for tool activity.
    // Preserve real client calls and searches backed by counts or citations.
    // `answer` only ends the steering; the answer itself is what follows.
    // Older saved turns also carry a step of the removed contradiction source
    // check (`check_contradictions`); it has no result left to show.
    const tools = events.filter(item => item.kind === "tool" && !["answer", "check_contradictions"].includes(item.name) && !(item.name === "web_search"
      && item.status === "unknown" && (item.server_tool || item.provider_native)
      && !(Number.isInteger(item.count) && item.count > 0) && !item.sources?.length));
    const activeTool = tools.findLast(item => item.status === "running");
    // A request for a domain and a step not every reviewer could check have no
    // reviewer's reason of their own, yet stay in the history: every opened
    // pause names its kind (halt).
    const holds = events.filter(item => item.kind === 'hold' && (item.reason || item.domain || item.halt));
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
    // A reviewer's halt: the work waits for the user's decision (the card above the field).
    const held = running && holds.some(item => (item.state || 'waiting') === 'waiting');
    // The agent's own question waits for the user, not for a decision on a pause.
    const asking = held && holds.some(item => item.ask && (item.state || 'waiting') === 'waiting');
    // The answer stands and its check is over: the run only saves now. Its
    // status line ("Writing answer…") came back for that moment and left with
    // the end, a row in and out of the open history just as the marks arrived.
    const saving = running && !activeTool && !waiting && !reconnecting && !held && Boolean(review)
      && !['running', 'required', 'pending'].includes(review.status) && Boolean(String(answerText || '').trim());
    const heading = running && reconnecting ? 'Reconnecting…'
      : asking ? 'Waiting for you' : held ? 'Paused' : waiting ? 'Waiting for available tokens…' : reviewStage
      || (activeTool ? stepLabel(activeTool) : writing ? 'Writing answer…' : 'Thinking…');
    // A complete, checked answer whose run failed afterwards reads as done:
    // the same rule as failureNote.
    const settled = status === 'failed' && !running && answerText
      && App.agentReview?.failureNote?.({error: 'failed'}, review, answerText) === '';
    const now = running ? phase({ asking, held, review }) : null;
    // The clock leaves out the time the run waited for the user here, as the
    // saved duration does (savedDuration).
    const waited = waitedMs(view, now === 'paused' || now === 'asking');
    updateClock(view, running && Number.isFinite(elapsedMs) ? Math.max(0, elapsedMs - waited) : elapsedMs, now,
      settled ? 'succeeded' : status);
    renderRunDetails(view, settings || events.findLast(item => item.settings)?.settings);
    view.details.classList.toggle("is-running", running);
    view.details.dataset.status = status;
    // Completion collapses a manually opened live history only offscreen
    // (below). Later explicit expansion is preserved across saved-turn and usage updates.
    const finished = view.running && !running;
    view.running = running;
    // Stable paragraphs keep earlier updates readable and prevent a live region
    // from announcing the entire history again whenever a new paragraph arrives.
    // The latest plan stands above the live progress, never in its order.
    const plan = tools.findLast(item => hasPlan(item) && item.status !== 'failed');
    const paragraphs = events.flatMap(item => holds.includes(item) ? [{id:`hold:${item.id}`, kind:'hold', item}]
      : progress.includes(item)
      ? [{id:item.id, text:item.text, kind:item.from_user ? 'user' : 'progress'}]
      : reasoning.includes(item) ? [{id:item.id, text:compactReasoning(item.text), kind:'progress'}]
        : tools.includes(item) && item.name === 'update_plan' ? []
        : tools.includes(item) && vmTools.has(item.name) ? [{id:`vm:${item.id}`, kind:'vm', item}]
        : tools.includes(item) ? [{id:`step:${item.id}`, text:stepLabel(item, textOnly), kind:'step', status:item.status,
          current:running && !waiting && !reconnecting && !held && item === activeTool},
          // The one place where the run waits on the user: say so, and link to the card.
          ...(item.status === 'succeeded' && reviewTools.has(item.name)
            ? [{id:`review:${item.id}`, text:'Waiting for your confirmation below', kind:'review'}] : [])] : []);
    // A waiting pause stands once in the timeline (its entry, with who paused
    // and why) and once on the card where the user decides; a status line
    // under it said the same a third time (UX audit C9).
    if (running && !saving && !held && (!activeTool || waiting || reconnecting)) paragraphs.push({id:'current-status', text:heading, kind:'step', current:true});
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
    const pinned = showPreview && plan ? 1 : 0;
    if (pinned) {
      previewIds.add('plan');
      let node = view.previewNodes.get('plan');
      if (!node) { node = planView('agent-plan'); view.previewNodes.set('plan', node); previewChanged = true; }
      updatePlan(node, plan, true);
      if (view.preview.firstElementChild !== node) view.preview.insertBefore(node, view.preview.firstElementChild);
    }
    const folded = showPreview ? foldPast(paragraphs) : null;
    const pastIds = new Set(folded?.past.map(item => item.id) || []);
    let fold = view.previewNodes.get('vm-fold');
    if (folded) {
      previewIds.add('vm-fold');
      if (!fold) { fold = foldView(); view.previewNodes.set('vm-fold', fold); }
      if (fold._label.textContent !== window.App.t(folded.label)) fold._label.textContent = folded.label;
      if (fold.dataset.count !== String(pastIds.size)) { fold.dataset.count = String(pastIds.size); previewChanged = true; }
      if (view.preview.children[pinned] !== fold) view.preview.insertBefore(fold, view.preview.children[pinned] || null);
    }
    let pastIndex = 0, presentIndex = pinned + (folded ? 1 : 0);
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
        p = item.kind === 'vm' ? vmView('agent-vm') : item.kind === 'hold' ? holdView('agent-hold-step')
          : item.kind === 'user' ? userNote('agent-user-note', item.text)
          : document.createElement(item.kind === 'progress' ? 'p' : 'div');
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
      if (item.kind === 'review' || item.kind === 'vm' || item.kind === 'user' || item.kind === 'hold') {
        if (item.kind === 'vm') updateVm(p, item.item);
        if (item.kind === 'hold') updateHold(p, item.item);
        place(item, p);
        continue;
      }
      if (item.quiet) p.setAttribute('aria-hidden', 'true');
      // The agent's note beside a call: a few lines here, whole in the timeline.
      p.classList.toggle('agent-progress-note', item.kind === 'progress' && String(item.id).endsWith('/note'));
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
    // The plan stands once in the history, where it was first made, with its
    // latest state (UX audit A5): every change of the checklist was an entry
    // of its own ("Plan · 1 of 4 done", "2 of 4", "3 of 4"). An update that
    // failed keeps its own line ("Plan not updated").
    const firstPlan = tools.find(item => hasPlan(item) && item.status !== 'failed');
    for (const item of events.filter(item => progress.includes(item) || reasoning.includes(item) || (tools.includes(item)
      && !(hasPlan(item) && item.status !== 'failed' && item !== firstPlan)) || holds.includes(item))) {
      ids.add(item.id);
      let node = view.nodes.get(item.id);
      if (!node) {
        node = item.kind === 'hold' ? holdView('agent-activity-tool agent-hold-step')
          : item.kind === 'tool' && vmTools.has(item.name) ? vmView('agent-activity-tool agent-vm')
          : hasPlan(item) ? planView('agent-activity-tool agent-plan')
          : item.from_user ? userNote('agent-activity-update agent-user-note', item.text)
          : document.createElement(item.kind === 'progress' && !isThought(item) ? 'p' : 'div');
        if (!node.className) node.className = item.kind === "tool" ? "agent-activity-tool"
          : isThought(item) ? 'agent-activity-update agent-activity-thought'
          : item.kind === 'progress' ? 'agent-activity-update' : "agent-activity-reasoning";
        view.nodes.set(item.id, node);
        view.content.appendChild(node);
        if (item.kind === 'progress' && view.details.open && running) reveal(node);
      }
      if (item.kind === 'hold') {
        updateHold(node, item);
      } else if (item.kind === "tool" && vmTools.has(item.name)) {
        updateVm(node, item);
      } else if (node.classList.contains('agent-user-note')) {
        // The user's words, written once at creation.
      } else if (node.classList.contains('agent-plan')) {
        if (hasPlan(item)) updatePlan(node, item === firstPlan ? plan || item : item, false);
      } else if (node.classList.contains('agent-activity-thought')) {
        updateThought(node, item);
        node.setAttribute('aria-label', item.summary_source === 'provider_summary' ? 'Reasoning summary' : 'Reasoning highlights');
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
    const currentStep = running && !saving && (!activeTool || waiting || reconnecting || held) ? heading : '';
    if (currentStep) {
      const label = view.current.firstElementChild;
      if (label.textContent !== window.App.t(currentStep)) label.textContent = currentStep;
      // After the comparisons too; appended once, a move would restart its shine.
      if (view.timeline.lastElementChild !== view.current) view.timeline.append(view.current);
    } else view.current.remove();
    view.timeline.classList.toggle('has-current', Boolean(currentStep));
    view.current.classList.toggle('is-paused', held);
    view.content.hidden = !progress.length && !reasoning.length && !tools.length && !holds.length;
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
    view.vmRestore = vmRestore;
    view.vmRestoreEl.hidden = running || !vmRestore || !vm?.checkpoint;
    // A history the reader opened stays open while it is on screen: closing
    // it there moved the answer below. Above the viewport the correction in
    // render() keeps the reading position, so it can tidy itself up.
    if (finished && (offscreenUpdate || !view.details.open)) disclosure(view, false);
  }

  // options.vmRestore: what the VM's restore action does (agent-chat.js).
  function renderTurn(host, turn, options = {}) {
    const events = turn?.agent_activity || [];
    const terminal = events.filter(item => item.kind === "status" && ["succeeded", "failed", "cancelled", "canceled"].includes(item.status)).at(-1);
    const status = turn?.error_code === "cancelled" ? "cancelled" : terminal?.status
      || (turn?.status === "failed" ? "failed" : "succeeded");
    render(host, { events, usage: turn?.agent_usage, status, truncated: turn?.agent_reasoning_truncated,
      finishReason: turn?.agent_finish_reason, elapsedMs:savedDuration(turn),
      review: turn?.agent_review, answerText: turn?.assistant_response ?? turn?.consensus ?? '', settings: turn?.agent_settings,
      vm: turn?.agent_vm, vmRestore: options.vmRestore || null });
  }
  App.agentActivity = { receive, render, renderTurn, label, reveal, dispose, savedDuration, toolName, phase, PHASE_WORDS };
})();
