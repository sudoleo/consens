// User-facing progress and confirmed activity. Shared by live runs and saved turns.
(function () {
  "use strict";
  const App = window.App = window.App || {};
  const statuses = { failed: "Response failed", cancelled: "Response stopped", canceled: "Response stopped" };
  // One table per tool: noun (history/failure rows), running and completed copy.
  // Unknown future tools fall back to a neutral label instead of a raw name.
  const tools = {
    web_search: ['Web search', 'Searching the web…', 'Searched the web'],
    read_source: ['Read source', 'Reading a source…', 'Read source'],
    compare_models: ['Model comparison', 'Comparing perspectives…', 'Compared perspectives'],
    judge_answer: ['Answer review', 'Checking the answer…', 'Checked the answer'],
    check_contradictions: ['Contradiction source check', 'Checking contradictions against sources…', 'Checked contradictions against sources'],
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
  };
  // Tools whose success leaves an external write waiting for the user.
  const reviewTools = new Set(['prepare_calendar_event', 'prepare_gmail_draft']);
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
    return count ? `Searched the web · ${count} ${count === 1 ? 'search' : 'searches'}` : 'Searched the web';
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
  // before the answer of such a turn was judged too): the answer judges and
  // the source check of their contradictions did not run.
  const textOnlySteps = { judge_answer: 'Checked your text', check_contradictions: 'Skipped the source check: your text was checked instead' };
  function textOnlyReview(review) {
    const checks = Array.isArray(review?.checks) ? review.checks : [];
    return checks.length > 0 && checks.every(check => check?.skipped === 'passage_checked');
  }
  function stepLabel(item, textOnly = false) {
    if (item.status === 'succeeded' && textOnly && textOnlySteps[item.name]) return textOnlySteps[item.name];
    if (item.name === 'read_source' && readSummary(item)) return readSummary(item);
    if (item.status === 'running') return tools[item.name]?.[1] || 'Working on a step…';
    if (item.status === 'succeeded' && item.name === 'web_search') return searchSummary(item);
    if (item.status === 'succeeded') return tools[item.name]?.[2] || `${toolName(item.name)} · Completed`;
    return `${toolName(item.name)} · ${{failed:'Failed', cancelled:'Stopped', blocked:'Skipped', unknown:'Usage unavailable'}[item.status] || 'Details'}`;
  }
  function savedDuration(turn) {
    const start = Date.parse(turn?.created_at);
    const end = Date.parse(turn?.completed_at || turn?.failed_at);
    return Number.isFinite(start) && Number.isFinite(end) && end >= start ? end - start : null;
  }
  function durationText(ms) {
    const seconds = Math.floor(Math.max(0, ms) / 1000);
    const hours = Math.floor(seconds / 3600), minutes = Math.floor(seconds / 60) % 60;
    return `${hours ? `${hours}h ` : ''}${minutes || hours ? `${minutes}m ` : ''}${seconds % 60}s`;
  }
  // "Working for 12s" while it runs, "Thought for 3m 7s" once it is done.
  function durationLabel(ms, running, status) {
    if (!Number.isFinite(ms)) return running ? 'Working' : statuses[status] || 'Activity';
    const time = durationText(ms);
    if (running) return `Working for ${time}`;
    if (status === 'failed') return `Response failed after ${time}`;
    if (statuses[status] === statuses.cancelled) return `Stopped after ${time}`;
    return `Thought for ${time}`;
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
      view.title.textContent = durationLabel(elapsed, running, status);
    };
    tick();
    if (running) view.clockTimer = setInterval(tick, 1000);
  }
  const quietMotion = window.matchMedia?.('(prefers-reduced-motion: reduce), (forced-colors: active)');
  const activeMotion = new Set();
  let offscreenUpdate = false;
  function motion(element, frames, finish = () => {}, duration = 220) {
    if (offscreenUpdate || quietMotion?.matches || !element.animate || !element.isConnected) { finish(); return null; }
    const animation = element.animate(frames, { duration, easing: 'cubic-bezier(.2, .7, .2, 1)', fill: 'both' });
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
    if (host._agentActivity) host._agentActivity.clockTimer = null;
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
  function compactReasoning(text) {
    const paragraphs = String(text || "").split(/\n\s*\n|\n/).filter(Boolean);
    return paragraphs.slice(-3).map(p => {
      const sentence = p.match(/[^.!?]+[.!?](?=\s|$)/)?.[0] || p;
      const clean = sentence.replace(/^[#*>\s-]+/, "").replace(/\*\*|__|`/g, '').replace(/\s+/g, " ").trim();
      return clean.length > 180 ? clean.slice(0, 177).replace(/\s+\S*$/, "") + "…" : clean;
    }).join("\n");
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

  function renderRunDetails(view, settings, running, heading) {
    const rows = [];
    if (settings?.label) rows.push(['Chat model', settings.label]);
    if (settings?.reasoning_effort) rows.push(['Reasoning', effortName(settings.reasoning_effort)]);
    if (running) rows.push(['Current step', heading]);
    const signature = JSON.stringify(rows);
    view.runDetails.hidden = !rows.length;
    if (view.runDetails.dataset.signature === signature) return;
    view.runDetails.dataset.signature = signature;
    view.runDetails.replaceChildren();
    for (const [label, text] of rows) {
      const term = document.createElement('dt'), value = document.createElement('dd');
      term.textContent = label; value.textContent = text;
      if (label === 'Current step') value.setAttribute('role', 'status');
      view.runDetails.append(term, value);
    }
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
    highlight = null, reconnecting = false } = {}) {
    if (!host) return;
    if (!host._agentActivity) {
      const details = document.createElement("details");
      details.className = "agent-activity";
      const summary = document.createElement("summary");
      const title = document.createElement("span");
      title.className = "agent-activity-title";
      title.setAttribute("role", "timer");
      title.setAttribute('aria-live', 'off');
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
      const usageEl = document.createElement("p");
      usageEl.className = "agent-usage";
      const preview = document.createElement('div'); preview.className = 'agent-progress';
      preview.setAttribute('role', 'log'); preview.setAttribute('aria-live', 'polite');
      preview.setAttribute('aria-relevant', 'additions text');
      preview.setAttribute('aria-label', 'Progress updates');
      const history = document.createElement('div'); history.className = 'agent-activity-history';
      const runDetails = document.createElement('dl'); runDetails.className = 'agent-activity-run-details';
      const insights = document.createElement('div'); insights.className = 'agent-activity-insights'; insights.hidden = true;
      history.inert = true;
      history.append(runDetails, content, insights, note, usageEl);
      details.append(summary, history);
      // Progress shows at the model icons in the summary (agent-chat.css,
      // "Progress at the models"), not on a line of its own.
      host.replaceChildren(details, preview);
      host._agentActivity = { details, summary, history, title, runDetails, insights, content, note, usageEl, preview, nodes: new Map(), previewNodes: new Map() };
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
    const tools = events.filter(item => item.kind === "tool" && !(item.name === "web_search"
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
    const reviewStage = review?.status === "running" ? "Checking the answer…"
      : review?.comparisons?.some(c => c.status === "running") ? "Comparing perspectives…" : null;
    const waiting = running && latest?.status === 'waiting';
    // The run keeps going on the server while the browser is offline or
    // asleep; say that instead of a step that may be long over.
    const heading = running && reconnecting ? 'Reconnecting…'
      : waiting ? 'Waiting for available tokens…' : reviewStage
      || (activeTool ? stepLabel(activeTool) : writing ? 'Writing answer…' : 'Thinking…');
    // A complete, checked answer whose run failed afterwards (for example in
    // a late source check) reads as done: the same rule as failureNote.
    const settled = status === 'failed' && !running && answerText
      && App.agentReview?.failureNote?.({error: 'failed'}, review, answerText) === '';
    updateClock(view, elapsedMs, running, settled ? 'succeeded' : status);
    renderRunDetails(view, settings || events.findLast(item => item.settings)?.settings, running, heading);
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
        : tools.includes(item) ? [{id:`step:${item.id}`, text:stepLabel(item, textOnly), kind:'step', status:item.status,
          current:running && !waiting && !reconnecting && item === activeTool},
          // The one place where the run waits on the user: say so, and link to the card.
          ...(item.status === 'succeeded' && reviewTools.has(item.name)
            ? [{id:`review:${item.id}`, text:'Waiting for your confirmation below', kind:'review'}] : [])] : []);
    if (running && (!activeTool || waiting || reconnecting)) paragraphs.push({id:'current-status', text:heading, kind:'step', current:true});
    // While the comparison models answer, the main model is silent: one quiet
    // line quotes the reasoning of the model that reported last.
    const comparing = reviewStage === 'Comparing perspectives…' || activeTool?.name === 'compare_models';
    if (running && !waiting && !reconnecting && comparing && highlight?.text) {
      // quiet: true keeps the frequent changes out of the screen reader log;
      // the agent panel offers the same highlights per model.
      paragraphs.push({ id: 'comparison-highlight', kind: 'progress', quiet: true,
        text: highlight.label ? `${highlight.label}: ${highlight.text}` : highlight.text });
    }
    if (waiting) paragraphs.push({ id: 'waiting', kind:'progress', text: latest.text || 'Active model calls are using the available allowance. This response will continue automatically.' });
    const previewHeight = view.preview.getBoundingClientRect().height;
    // Like ChatGPT/Claude, the progress lines give way the moment the answer
    // starts: at that point nothing stands below them yet. Kept until the
    // run ended, their collapse pulled the finished answer up under the eye.
    // A preamble before a running tool is not the answer yet.
    const answering = running && !activeTool && Boolean(String(answerText || '').trim());
    const showPreview = running && paragraphs.length && !answering;
    let previewChanged = false;
    if (showPreview) {
      if (view.previewExit) { cancelMotion(view.previewMotion); view.previewExit = false; }
      view.preview.hidden = false;
      view.preview.removeAttribute('aria-hidden');
      view.preview.inert = false;
    }
    const previewIds = new Set();
    for (const item of showPreview ? paragraphs : []) {
      previewIds.add(item.id);
      let p = view.previewNodes.get(item.id);
      if (!p) {
        p = document.createElement(item.kind === 'progress' ? 'p' : 'div'); view.previewNodes.set(item.id, p);
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
      if (item.kind === 'review') {
        const position = view.preview.children[previewIds.size - 1];
        if (position !== p) view.preview.insertBefore(p, position || null);
        continue;
      }
      if (item.quiet) p.setAttribute('aria-hidden', 'true');
      p.classList.toggle('agent-progress-step', item.kind === 'step');
      p.classList.toggle('agent-current-status', Boolean(item.current));
      if (item.current) p.setAttribute('role', 'status'); else p.removeAttribute('role');
      if (item.status) p.dataset.status = item.status;
      if (p.textContent !== item.text) {
        const previous = p.textContent;
        p.textContent = item.text;
        if (previous && item.kind === 'step') motion(p, [{opacity:.65}, {opacity:1}], () => {}, 160);
      }
      // A fallback Thinking/Writing row moves after a newly received insight.
      const position = view.preview.children[previewIds.size - 1];
      if (position !== p) view.preview.insertBefore(p, position || null);
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
        node = document.createElement(item.kind === 'progress' ? 'p' : 'div');
        node.className = item.kind === "tool" ? "agent-activity-tool" : item.kind === 'progress' ? 'agent-activity-update' : "agent-activity-reasoning";
        view.nodes.set(item.id, node);
        view.content.appendChild(node);
        if (item.kind === 'progress' && view.details.open && running) reveal(node);
      }
      if (item.kind === "tool") {
        const signature = JSON.stringify([item, textOnly]);
        if (node.dataset.signature !== signature) {
          node.dataset.signature = signature;
          node.dataset.status = item.status;
          const title = document.createElement("strong");
          const toolStatus = { running: "Working…", succeeded: "Completed", failed: "Failed", blocked: "Skipped · budget reserve", cancelled: "Stopped", unknown: "Usage unavailable" };
          const count = Number.isInteger(item.count) && item.count > 0 ? ` · ${item.count} ${item.count === 1 ? "search" : "searches"}` : "";
          title.textContent = item.status === 'succeeded' && textOnly && textOnlySteps[item.name]
            ? textOnlySteps[item.name]
            // A read source names its host; "Completed" would hide a page that could not be read.
            : (item.name === 'read_source' && readSummary(item))
              || `${toolName(item.name)} · ${toolStatus[item.status] || "Details"}${count}`;
          node.replaceChildren(title);
          if (item.text) {
            const text = document.createElement("p");
            text.textContent = String(item.text).slice(0, 8000);
            node.appendChild(text);
          }
          for (const source of (Array.isArray(item.sources) ? item.sources : []).slice(0, 5)) {
            try {
              if (typeof source.url !== "string" || source.url.length > 2048) continue;
              const url = new URL(source.url);
              if (!["https:", "http:"].includes(url.protocol) || url.username || url.password) continue;
              const link = document.createElement("a");
              link.href = url.href;
              link.target = "_blank";
              link.rel = "noopener noreferrer";
              link.textContent = String(source.title || url.hostname).slice(0, 200);
              node.appendChild(link);
            } catch (_) { /* Ignore invalid provider URLs. */ }
          }
        }
      } else {
        const text = item.kind === 'progress' ? item.text : compactReasoning(item.text);
        if (node.textContent !== text) node.textContent = text;
        node.setAttribute("aria-label", item.kind === 'progress' ? 'Progress update' : item.summary_source === "excerpt" || item.format === "text" ? "Reasoning highlights" : "Reasoning summary");
      }
    }
    for (const [id, node] of view.nodes) if (!ids.has(id)) { node.remove(); view.nodes.delete(id); }
    view.content.hidden = !progress.length && !reasoning.length && !tools.length;
    App.agentReview?.renderActivity(view.insights, review, answerText);
    view.note.textContent = progress.length || !view.insights.hidden ? '' : reasoning.length ? (reasoning[0].summary_source === "excerpt" || reasoning[0].format === "text"
      ? "Short excerpts from the model’s reasoning." : "Model-provided reasoning summary.") : truncated ? "Reasoning highlights only."
      : !reasoning.length ? (running ? "Waiting for the model’s response."
        : "No detailed progress updates were saved for this response.") : "";
    if (finishReason === "length") view.note.textContent += " The response reached its output limit.";
    view.note.hidden = !view.note.textContent;
    const measured = usage && Number.isFinite(usage.input_tokens) && Number.isFinite(usage.output_tokens);
    const tokens = measured ? `${(usage.input_tokens + usage.output_tokens).toLocaleString()} ${usage.complete === false ? "measured tokens · usage incomplete" : "tokens"}` : "Usage unavailable";
    const dollars = Number.isFinite(usage?.estimated_cost_nano_usd) ? usage.estimated_cost_nano_usd / 1e9 : NaN;
    const providerCost = usage?.cost_source === "provider";
    const cost = Number.isFinite(dollars)
      ? ` · ${usage.cost_complete === false ? "at least " : ""}${providerCost ? "" : "~"}$${dollars.toFixed(dollars > 0 && dollars < .0001 ? 6 : 4)} ${providerCost ? "provider cost" : "estimated"}${usage.cost_complete === false ? " · cost incomplete" : ""}` : "";
    view.usageEl.textContent = tokens + cost;
    view.usageEl.title = measured ? `${usage.input_tokens.toLocaleString()} input · ${usage.output_tokens.toLocaleString()} output tokens` : "The provider did not report token usage.";
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
      review: turn?.agent_review, answerText: turn?.assistant_response ?? turn?.consensus ?? '', settings: turn?.agent_settings });
  }
  App.agentActivity = { receive, render, renderTurn, label, reveal, dispose, savedDuration };
})();
