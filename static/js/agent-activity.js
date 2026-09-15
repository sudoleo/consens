// Displayable provider events only. Shared by live Agent runs and saved turns.
(function () {
  "use strict";
  const App = window.App = window.App || {};
  const statuses = { failed: "Response failed", cancelled: "Response stopped", canceled: "Response stopped" };

  function receive(events, event) {
    if (event?.version !== 1 || !["status", "reasoning", "usage", "tool"].includes(event.kind) || typeof event.id !== "string") return;
    const existing = events.find(item => item.id === event.id);
    if (existing && event.append && event.kind === "reasoning") {
      existing.text = (existing.text + String(event.text || "")).slice(0, 32000);
    } else if (existing) Object.assign(existing, event);
    else if (events.length < 64) events.push({ ...event, text: String(event.text || "").slice(0, event.kind === "tool" ? 8000 : 32000) });
  }

  function label(settings) {
    if (!settings?.label) return "Agent answer";
    const effort = settings.reasoning_effort;
    return `${settings.label}${effort && effort !== "default" ? ` · ${effort === "none" ? "Reasoning off" : effort + " reasoning"}` : ""}`;
  }

  function render(host, { events = [], usage = null, running = false, responding = false,
    status = "succeeded", truncated = false, finishReason = "" } = {}) {
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
      details.append(summary, content, note, usageEl);
      host.replaceChildren(details);
      host._agentActivity = { details, title, content, note, usageEl, nodes: new Map(), manual: false };
      // Native toggle events also fire for programmatic .open changes.
      // Only an explicit user gesture overrides the automatic disclosure.
      summary.addEventListener("click", () => { host._agentActivity.manual = true; });
    }
    const view = host._agentActivity;
    const reasoning = events.filter(item => item.kind === "reasoning"
      && ["text", "summary"].includes(item.format) && item.text);
    const tools = events.filter(item => item.kind === "tool");
    const activeTool = tools.findLast(item => item.status === "running");
    const latest = events.filter(item => item.kind === "status").at(-1);
    const writing = latest ? latest.status === "responding" : responding;
    const heading = running ? (activeTool ? "Using tool…" : writing ? "Writing answer…" : reasoning.length ? "Thinking…" : "Working…")
      : statuses[status] || (finishReason === "length" ? "Response limit reached" : tools.length ? "Activity and sources" : reasoning.length ? "Reasoning" : "Response details");
    if (view.title.textContent !== heading) view.title.textContent = heading;
    view.details.classList.toggle("is-running", running);
    view.details.dataset.status = status;
    if (!view.manual) view.details.open = running && (reasoning.length > 0 || tools.length > 0);
    // Follow the whole trace, with one scrollbar. Respect readers scrolling up.
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
          const toolStatus = { running: "Working…", succeeded: "Completed", failed: "Failed", blocked: "Not allowed", cancelled: "Stopped", unknown: "Usage unavailable" };
          const count = Number.isInteger(item.count) && item.count > 0 ? ` · ${item.count} ${item.count === 1 ? "search" : "searches"}` : "";
          title.textContent = `${item.name === "web_search" ? "Web search" : "Tool"} · ${toolStatus[item.status] || "Details"}${count}`;
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
        if (node.textContent !== item.text) node.textContent = item.text;
        node.setAttribute("aria-label", item.format === "summary" ? "Reasoning summary" : "Model reasoning");
      }
    }
    for (const [id, node] of view.nodes) if (!ids.has(id)) { node.remove(); view.nodes.delete(id); }
    view.content.hidden = !reasoning.length && !tools.length;
    if (follow && view.details.open) view.content.scrollTop = view.content.scrollHeight;
    view.note.textContent = truncated ? "Only the first part of the model’s reasoning is shown."
      : !reasoning.length ? (running ? "Waiting for the model’s response."
        : "No visible reasoning was returned for this response.") : "";
    if (finishReason === "length") view.note.textContent += " The response reached its output limit.";
    view.note.hidden = !view.note.textContent;
    const measured = usage && Number.isFinite(usage.input_tokens) && Number.isFinite(usage.output_tokens);
    const tokens = measured ? `${(usage.input_tokens + usage.output_tokens).toLocaleString()} ${usage.complete === false ? "measured tokens · usage incomplete" : "tokens"}` : "Usage unavailable";
    const dollars = Number.isFinite(usage?.estimated_cost_nano_usd) ? usage.estimated_cost_nano_usd / 1e9 : NaN;
    const providerCost = usage?.cost_source === "provider";
    const cost = Number.isFinite(dollars)
      ? ` · ${providerCost ? "" : "~"}$${dollars.toFixed(dollars > 0 && dollars < .0001 ? 6 : 4)} ${providerCost ? "provider cost" : "estimated"}` : "";
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
