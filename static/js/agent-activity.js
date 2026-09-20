// Displayable provider events only. Shared by live Agent runs and saved turns.
(function () {
  "use strict";
  const App = window.App = window.App || {};
  const statuses = { failed: "Response failed", cancelled: "Response stopped", canceled: "Response stopped" };
  const toolNames = { web_search: 'Web search', compare_models: 'Model comparison', judge_answer: 'Answer review',
    check_contradictions: 'Contradiction source check',
    start_agent: 'Ask a model', wait_agents: 'Wait for models', send_agent: 'Follow up',
    review_agent: 'Review a model', stop_agent: 'Stop a model', report_to_orchestrator: 'Report to the main model' };
  function compactReasoning(text) {
    const paragraphs = String(text || "").split(/\n\s*\n|\n/).filter(Boolean);
    return paragraphs.slice(-3).map(p => {
      const sentence = p.match(/[^.!?]+[.!?](?=\s|$)/)?.[0] || p;
      const clean = sentence.replace(/^[#*>\s-]+/, "").replace(/\*\*|__|`/g, '').replace(/\s+/g, " ").trim();
      return clean.length > 180 ? clean.slice(0, 177).replace(/\s+\S*$/, "") + "…" : clean;
    }).join("\n");
  }

  function receive(events, event) {
    if (event?.version !== 1 || !["status", "reasoning", "usage", "tool"].includes(event.kind) || typeof event.id !== "string") return;
    const existing = events.find(item => item.id === event.id);
    if (existing && event.append && event.kind === "reasoning") {
      existing.text = (existing.text + String(event.text || "")).slice(0, 32000);
    } else if (existing) {
      Object.assign(existing, event);
      if (event.kind === 'status') { events.splice(events.indexOf(existing), 1); events.push(existing); }
    } else {
      if (events.length >= 64) events.splice(0, events.length - 63);
      events.push({ ...event, text: String(event.text || "").slice(0, event.kind === "tool" ? 8000 : 32000) });
    }
  }

  function label(settings) {
    if (!settings?.label) return "Agent answer";
    const effort = settings.reasoning_effort;
    return `${settings.label}${effort && effort !== "default" ? ` · ${effort === "none" ? "Reasoning off" : effort + " reasoning"}` : ""}`;
  }

  function render(host, { events = [], usage = null, running = false, responding = false,
    status = "succeeded", truncated = false, finishReason = "", review = null } = {}) {
    if (!host) return;
    if (!host._agentActivity) {
      const details = document.createElement("details");
      details.className = "agent-activity";
      const summary = document.createElement("summary");
      const title = document.createElement("span");
      title.className = "agent-activity-title";
      title.setAttribute("role", "status");
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
      preview.setAttribute('role', 'status'); preview.setAttribute('aria-live', 'polite');
      details.append(summary, content, note, usageEl);
      host.replaceChildren(details, preview);
      host._agentActivity = { details, title, content, note, usageEl, preview, nodes: new Map() };
    }
    const view = host._agentActivity;
    const reasoning = events.filter(item => item.kind === "reasoning"
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
    const toolLabels = { web_search: 'Searching the web…', compare_models: 'Comparing perspectives…',
      check_contradictions: 'Checking contradictions against sources…',
      judge_answer: 'Checking the answer…', start_agent: 'Asking another model…', wait_agents: 'Waiting for model responses…',
      send_agent: 'Following up with a model…', review_agent: 'Reviewing a model response…' };
    const waiting = running && latest?.status === 'waiting';
    const heading = running ? (waiting ? 'Waiting for available tokens…' : reviewStage || (activeTool ? toolLabels[activeTool.name] || 'Running a tool…' : writing ? 'Writing answer…' : reasoning.length ? 'Thinking…' : 'Working…'))
      : statuses[status] || (finishReason === "length" ? "Response limit reached" : tools.length ? "Activity and sources" : reasoning.length ? "Reasoning" : "Response details");
    if (view.title.textContent !== heading) view.title.textContent = heading;
    view.details.classList.toggle("is-running", running);
    view.details.dataset.status = status;
    // The disclosure heading owns the current stage; the preview adds only
    // reasoning highlights, never a second copy of the same tool status.
    const highlights = compactReasoning(reasoning.at(-1)?.text).split('\n').filter(Boolean);
    const paragraphs = waiting ? [latest.text || 'Active model calls are using the available allowance. This response will continue automatically.']
      : [...new Set(highlights)].filter(text => text !== heading).slice(0, 3);
    const previewSignature = running ? JSON.stringify(paragraphs) : '';
    if (view.preview.dataset.signature !== previewSignature) {
      view.preview.dataset.signature = previewSignature;
      view.preview.replaceChildren(...(running ? paragraphs : []).map(text => {
        const p = document.createElement('p');
        p.textContent = text;
        return p;
      }));
    }
    view.preview.hidden = !running || !paragraphs.length;
    // Expansion is always an explicit user choice.
    const follow = view.content.scrollHeight - view.content.scrollTop - view.content.clientHeight < 40;
    const ids = new Set();
    for (const item of events.filter(item => reasoning.includes(item) || tools.includes(item))) {
      ids.add(item.id);
      let node = view.nodes.get(item.id);
      if (!node) {
        node = document.createElement("div");
        node.className = item.kind === "tool" ? "agent-activity-tool" : "agent-activity-reasoning";
        view.nodes.set(item.id, node);
        view.content.appendChild(node);
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
        const text = compactReasoning(item.text);
        if (node.textContent !== text) node.textContent = text;
        node.setAttribute("aria-label", item.summary_source === "excerpt" || item.format === "text" ? "Reasoning highlights" : "Reasoning summary");
      }
    }
    for (const [id, node] of view.nodes) if (!ids.has(id)) { node.remove(); view.nodes.delete(id); }
    view.content.hidden = !reasoning.length && !tools.length;
    if (follow && view.details.open) view.content.scrollTop = view.content.scrollHeight;
    view.note.textContent = reasoning.length ? (reasoning[0].summary_source === "excerpt" || reasoning[0].format === "text"
      ? "Short excerpts from the model’s reasoning." : "Model-provided reasoning summary.") : truncated ? "Reasoning highlights only."
      : !reasoning.length ? (running ? "Waiting for the model’s response."
        : "No visible reasoning was returned for this response.") : "";
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
  }

  function renderTurn(host, turn) {
    const events = turn?.agent_activity || [];
    const terminal = events.filter(item => item.kind === "status" && ["succeeded", "failed", "cancelled", "canceled"].includes(item.status)).at(-1);
    const status = turn?.error_code === "cancelled" ? "cancelled" : terminal?.status
      || (turn?.status === "failed" ? "failed" : "succeeded");
    render(host, { events, usage: turn?.agent_usage, status, truncated: turn?.agent_reasoning_truncated,
      finishReason: turn?.agent_finish_reason });
  }
  App.agentActivity = { receive, render, renderTurn, label };
})();
