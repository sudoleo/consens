// Displayable provider events only. Shared by live Agent runs and saved turns.
(function () {
  "use strict";
  const App = window.App = window.App || {};
  const statuses = { working: "Working…", responding: "Writing answer…", succeeded: "Completed",
    failed: "Response failed", cancelled: "Response stopped", canceled: "Response stopped" };

  function receive(events, event) {
    if (event?.version !== 1 || !["status", "reasoning", "usage"].includes(event.kind) || typeof event.id !== "string") return;
    const existing = events.find(item => item.id === event.id);
    if (existing && event.append && event.kind === "reasoning") {
      existing.text = (existing.text + String(event.text || "")).slice(0, 32000);
    } else if (existing) Object.assign(existing, event);
    else if (events.length < 40) events.push({ ...event, text: String(event.text || "").slice(0, 32000) });
  }

  function label(settings) {
    if (!settings?.label) return "Agent answer";
    const effort = settings.reasoning_effort;
    return `Agent answer · ${settings.label}${effort && effort !== "default" ? ` · ${effort === "none" ? "Reasoning off" : effort + " reasoning"}` : ""}`;
  }

  function render(host, { events = [], usage = null, running = false, status = "succeeded", truncated = false, finishReason = "" } = {}) {
    if (!host) return;
    if (!host._agentActivity) {
      const details = document.createElement("details");
      details.className = "agent-activity";
      details.open = running;
      const summary = document.createElement("summary");
      const title = document.createElement("span");
      title.className = "agent-activity-title";
      title.setAttribute("role", "status");
      summary.appendChild(title);
      const content = document.createElement("div");
      content.className = "agent-activity-content";
      const note = document.createElement("p");
      note.className = "agent-activity-note";
      const usageEl = document.createElement("p");
      usageEl.className = "agent-usage";
      details.append(summary, content, note, usageEl);
      host.replaceChildren(details);
      host._agentActivity = { details, title, content, note, usageEl, nodes: new Map() };
    }
    const view = host._agentActivity;
    const reasoning = events.filter(item => item.kind === "reasoning" && ["text", "summary"].includes(item.format));
    const writing = events.some(item => item.status === "responding");
    const heading = running ? (writing ? "Writing answer…" : reasoning.length ? "Thinking…" : "Working…") : (statuses[status] || "Activity");
    if (view.title.textContent !== heading) view.title.textContent = heading;
    view.details.classList.toggle("is-running", running);
    const ids = new Set();
    for (const item of events) {
      if (item.kind !== "status" && !reasoning.includes(item)) continue;
      ids.add(item.id);
      let node = view.nodes.get(item.id);
      if (!node) {
        node = document.createElement("div");
        node.className = `agent-activity-${item.kind}`;
        view.nodes.set(item.id, node);
        view.content.appendChild(node);
      }
      const text = item.kind === "status" ? statuses[item.status] || "" : item.text || "";
      if (node.textContent !== text) {
        const follow = node.scrollHeight - node.scrollTop - node.clientHeight < 40;
        node.textContent = text;
        if (follow) node.scrollTop = node.scrollHeight;
      }
      if (item.kind === "reasoning") node.setAttribute("aria-label", item.format === "summary" ? "Reasoning summary" : "Model reasoning");
    }
    for (const [id, node] of view.nodes) if (!ids.has(id)) { node.remove(); view.nodes.delete(id); }
    view.note.textContent = truncated ? "Only the first part of the model’s reasoning is shown."
      : !running && !reasoning.length ? "This model returned no visible reasoning." : "";
    if (finishReason === "length") view.note.textContent += " The response reached its output limit.";
    view.note.hidden = !view.note.textContent;
    const tokens = usage && Number.isFinite(usage.input_tokens) && Number.isFinite(usage.output_tokens)
      ? `${(usage.input_tokens + usage.output_tokens).toLocaleString()} tokens` : "Usage unavailable";
    const dollars = usage?.estimated_cost_nano_usd / 1e9;
    const cost = Number.isFinite(dollars)
      ? ` · ~$${dollars.toFixed(dollars > 0 && dollars < .0001 ? 6 : 4)} simulated` : "";
    view.usageEl.textContent = tokens + cost;
    view.usageEl.hidden = running;
  }

  function renderTurn(host, turn) {
    render(host, { events: turn?.agent_activity || [], usage: turn?.agent_usage,
      status: turn?.status === "failed" ? "failed" : "succeeded", truncated: turn?.agent_reasoning_truncated,
      finishReason: turn?.agent_finish_reason });
  }
  App.agentActivity = { receive, render, renderTurn, label };
})();
