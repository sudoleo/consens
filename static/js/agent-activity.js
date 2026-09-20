// User-facing progress and confirmed activity. Shared by live runs and saved turns.
(function () {
  "use strict";
  const App = window.App = window.App || {};
  const statuses = { failed: "Response failed", cancelled: "Response stopped", canceled: "Response stopped" };
  const toolNames = { web_search: 'Web search', compare_models: 'Model comparison', judge_answer: 'Answer review',
    check_contradictions: 'Contradiction source check',
    start_agent: 'Ask a model', wait_agents: 'Wait for models', send_agent: 'Follow up',
    review_agent: 'Review a model', stop_agent: 'Stop a model', report_to_orchestrator: 'Report to the main model' };
  const toolLabels = { web_search: 'Searching the web…', compare_models: 'Comparing perspectives…',
    check_contradictions: 'Checking contradictions against sources…', judge_answer: 'Checking the answer…',
    start_agent: 'Asking another model…', wait_agents: 'Waiting for model responses…',
    send_agent: 'Following up with a model…', review_agent: 'Reviewing a model response…' };
  const completedTools = { web_search: 'Searched the web', compare_models: 'Compared perspectives',
    judge_answer: 'Checked the answer', check_contradictions: 'Checked contradictions against sources',
    start_agent: 'Asked another model', wait_agents: 'Received model updates', send_agent: 'Followed up with a model',
    review_agent: 'Reviewed a model response' };
  function stepLabel(item) {
    if (item.status === 'running') return toolLabels[item.name] || 'Running a tool…';
    if (item.status === 'succeeded') return completedTools[item.name] || `${toolNames[item.name] || 'Tool'} · Completed`;
    return `${toolNames[item.name] || 'Tool'} · ${{failed:'Failed', cancelled:'Stopped', blocked:'Skipped', unknown:'Usage unavailable'}[item.status] || 'Details'}`;
  }
  function savedDuration(turn) {
    const start = Date.parse(turn?.created_at);
    const end = Date.parse(turn?.completed_at || turn?.failed_at);
    return Number.isFinite(start) && Number.isFinite(end) && end >= start ? end - start : null;
  }
  function durationLabel(ms) {
    if (!Number.isFinite(ms)) return 'Duration unavailable';
    const seconds = Math.floor(Math.max(0, ms) / 1000);
    const hours = Math.floor(seconds / 3600), minutes = Math.floor(seconds / 60) % 60;
    return `Duration: ${hours ? `${hours}h ` : ''}${minutes || hours ? `${minutes}m ` : ''}${seconds % 60}s`;
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
      view.title.textContent = durationLabel(elapsed) + (!running && statuses[status] ? ` · ${statuses[status]}` : '');
    };
    tick();
    if (running) view.clockTimer = setInterval(tick, 1000);
  }
  const quietMotion = window.matchMedia?.('(prefers-reduced-motion: reduce), (forced-colors: active)');
  const activeMotion = new Set();
  function motion(element, frames, finish = () => {}, duration = 220) {
    if (quietMotion?.matches || !element.animate || !element.isConnected) { finish(); return null; }
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
  function reveal(element) {
    return motion(element, [{ opacity: 0, transform: 'translateY(4px)' }, { opacity: 1, transform: 'none' }]);
  }
  function clearPreview(view) {
    view.preview.hidden = true;
    view.preview.replaceChildren();
    view.previewNodes.clear();
    view.previewExit = false;
    view.previewMotion = null;
  }
  function hidePreview(view) {
    if (view.previewExit) return;
    const height = view.preview.getBoundingClientRect().height;
    cancelMotion(view.previewMotion);
    view.preview.setAttribute('aria-hidden', 'true');
    view.preview.inert = true;
    if (!height) { clearPreview(view); return; }
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
    if (before && after && before !== after && !quietMotion?.matches && host.animate) {
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

  function label(settings) {
    if (!settings?.label) return "Agent answer";
    const effort = settings.reasoning_effort;
    return `${settings.label}${effort && effort !== "default" ? ` · ${effort === "none" ? "Reasoning off" : effort + " reasoning"}` : ""}`;
  }

  function renderRunDetails(view, settings, running, heading) {
    const rows = [];
    if (settings?.label) rows.push(['Chat model', settings.label]);
    if (settings?.reasoning_effort) rows.push(['Reasoning', settings.reasoning_effort === 'default' ? 'Model default'
      : settings.reasoning_effort === 'none' ? 'Off' : settings.reasoning_effort]);
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

  function render(host, { events = [], usage = null, running = false, responding = false,
    status = "succeeded", truncated = false, finishReason = "", review = null, answerText = '', settings = null, elapsedMs = null } = {}) {
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
    const latest = events.filter(item => item.kind === "status").at(-1);
    const writing = latest ? latest.status === "responding" : responding;
    const reviewStage = review?.status === "running" ? "Checking the answer…"
      : review?.comparisons?.some(c => c.status === "running") ? "Comparing perspectives…" : null;
    const waiting = running && latest?.status === 'waiting';
    const heading = waiting ? 'Waiting for available tokens…' : reviewStage
      || (activeTool ? stepLabel(activeTool) : writing ? 'Writing answer…' : 'Thinking…');
    updateClock(view, elapsedMs, running, status);
    renderRunDetails(view, settings || events.findLast(item => item.settings)?.settings, running, heading);
    view.details.classList.toggle("is-running", running);
    view.details.dataset.status = status;
    // Completion collapses even a manually opened live history. Later explicit
    // expansion is preserved across saved-turn and usage updates.
    const finished = view.running && !running;
    view.running = running;
    // Stable paragraphs keep earlier updates readable and prevent a live region
    // from announcing the entire history again whenever a new paragraph arrives.
    const paragraphs = events.flatMap(item => progress.includes(item)
      ? [{id:item.id, text:item.text, kind:'progress'}]
      : reasoning.includes(item) ? [{id:item.id, text:compactReasoning(item.text), kind:'progress'}]
        : tools.includes(item) ? [{id:`step:${item.id}`, text:stepLabel(item), kind:'step', status:item.status,
          current:running && !waiting && item === activeTool}] : []);
    if (running && (!activeTool || waiting)) paragraphs.push({id:'current-status', text:heading, kind:'step', current:true});
    if (waiting) paragraphs.push({ id: 'waiting', kind:'progress', text: latest.text || 'Active model calls are using the available allowance. This response will continue automatically.' });
    const previewHeight = view.preview.getBoundingClientRect().height;
    const showPreview = running && paragraphs.length;
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
        p = document.createElement(item.kind === 'step' ? 'div' : 'p'); view.previewNodes.set(item.id, p);
        view.preview.appendChild(p);
        previewChanged = true;
        if (!view.details.open) reveal(p);
      }
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
    } else hidePreview(view);
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
        const signature = JSON.stringify(item);
        if (node.dataset.signature !== signature) {
          node.dataset.signature = signature;
          node.dataset.status = item.status;
          const title = document.createElement("strong");
          const toolStatus = { running: "Working…", succeeded: "Completed", failed: "Failed", blocked: "Skipped · budget reserve", cancelled: "Stopped", unknown: "Usage unavailable" };
          const count = Number.isInteger(item.count) && item.count > 0 ? ` · ${item.count} ${item.count === 1 ? "search" : "searches"}` : "";
          title.textContent = `${toolNames[item.name] || "Tool"} · ${toolStatus[item.status] || "Details"}${count}`;
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
    if (finished) disclosure(view, false);
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
