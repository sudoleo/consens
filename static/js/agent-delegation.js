// One owner/turn projection drives both inline model icons and the agent sidebar.
(function () {
  "use strict";
  const App = window.App = window.App || {};
  const views = new Map();
  const labels = { waiting: "Waiting", working: "Working", question: "Question", review: "Review",
    rework: "Rework", completed: "Completed", failed: "Failed", stopped: "Stopped" };
  const activeStates = new Set(["waiting", "working", "question", "rework"]);
  const icons = { anthropic: "claude.png", deepseek: "deepseek.png", google: "gemini-icon.png",
    "x-ai": "grok.png", openai: "chatgpt.png", mistralai: "mistral.png" };
  let owner = "", current = null, sidebar = null, inline = null, timer = null, returnFocus = null;
  const uid = () => window.auth?.currentUser?.uid || "";
  const keyFor = (chat, turn) => `${uid()}:${chat}:${turn}`;
  function node(tag, className, text) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (text !== undefined) el.textContent = text;
    return el;
  }
  function cost(usage) {
    if (!Number.isFinite(usage?.estimated_cost_nano_usd)) return "Cost unknown";
    const value = usage.estimated_cost_nano_usd / 1e9;
    const partial = usage.cost_complete === false || (usage.cost_complete === undefined && usage.complete === false);
    return `${partial ? "At least " : ""}${usage.cost_source === "provider" ? "" : "~"}$${value.toFixed(value > 0 && value < .0001 ? 6 : 4)}${partial ? " · incomplete" : ""}`;
  }
  function mark(agent) {
    const family = (agent.model?.model || "").split("/")[0];
    const img = node("img");
    img.src = `/static/icons/chat_icons/${icons[family] || "chatgpt.png"}`;
    img.alt = "";
    if (["openai", "x-ai"].includes(family)) img.className = "mono-logo";
    return img;
  }
  function prefs(view) {
    if (current === view && sidebar) view.scroll = sidebar.scrollTop;
    try {
      sessionStorage.setItem(`agent-view:${view.key}`, JSON.stringify({ closed: view.closed, expanded: [...view.expanded], scroll: view.scroll }));
    } catch (_) { /* Storage may be unavailable. */ }
  }
  function resetOwner() {
    if (owner === uid()) return;
    owner = uid();
    for (const view of views.values()) view.controller.abort();
    views.clear(); current = null;
    if (sidebar) { sidebar.hidden = true; sidebar._rows?.clear(); sidebar.querySelector(".agent-session-list")?.replaceChildren(); }
    if (inline) inline.remove();
    inline = null;
    document.body.classList.remove("agent-sidebar-open");
  }
  function get(chatId, turnId) {
    resetOwner();
    const key = keyFor(chatId, turnId);
    if (!views.has(key)) {
      let saved = {};
      try { saved = JSON.parse(sessionStorage.getItem(`agent-view:${key}`) || "{}"); } catch (_) {}
      views.set(key, { key, uid: owner, chatId, turnId, agents: new Map(), details: new Map(),
        controller: new AbortController(), expanded: new Set(saved.expanded || []), closed: !!saved.closed,
        scroll: saved.scroll || 0, loaded: false, loading: false, running: false, usage: null });
      if (views.size > 24) {
        const old = [...views.values()].find(v => v.key !== current?.key && !v.running);
        if (old) { old.controller.abort(); views.delete(old.key); }
      }
    }
    return views.get(key);
  }
  function merge(view, agent) {
    if (!agent || !/^[a-f0-9]{32}$/.test(agent.id) || !Number.isInteger(agent.seq)) return;
    const old = view.agents.get(agent.id);
    if (!old || agent.seq > old.seq) view.agents.set(agent.id, agent);
  }
  function receive(context, event) {
    resetOwner();
    if (!App.runRegistry?.isAuthCurrent(context) || event?.version !== 1 || !event.chat_id || !event.turn_id) return;
    if (context.metadata.chatId && context.metadata.chatId !== event.chat_id) return;
    if (context.metadata.agentTurnId && context.metadata.agentTurnId !== event.turn_id) return;
    context.metadata.agentTurnId = event.turn_id;
    context.metadata.delegation = true;
    const view = get(event.chat_id, event.turn_id);
    merge(view, event.agent);
    if (current === view) render();
  }
  async function request(view, suffix = "") {
    const token = await window.auth.currentUser.getIdToken();
    if (uid() !== view.uid || view.controller.signal.aborted) throw new Error("Account changed");
    const response = await fetch(`/agent/chats/${encodeURIComponent(view.chatId)}/turns/${encodeURIComponent(view.turnId)}/agents${suffix}`,
      { headers: { Authorization: `Bearer ${token}` }, signal: view.controller.signal });
    if (!response.ok) throw new Error("Agent details could not be loaded.");
    const data = await response.json();
    if (uid() !== view.uid || view.controller.signal.aborted) throw new Error("Account changed");
    return data;
  }
  async function load(view) {
    if (view.loading || !view.uid) return;
    view.loading = true;
    try {
      const data = await request(view);
      for (const agent of data.agents || []) merge(view, agent);
      view.running = data.status === "running" || data.status === "pending";
      const calls = usage => (usage?.measured_calls || 0) + (usage?.unmetered_calls || 0);
      if (calls(data.usage) >= calls(view.usage)) view.usage = data.usage;
      view.loaded = true; view.error = "";
    } catch (error) { view.error = error.message; }
    finally { view.loading = false; if (current === view && uid() === view.uid) render(); }
  }
  async function loadDetail(view, agentId, more = false) {
    let detail = view.details.get(agentId);
    if (!detail) { detail = { messages: new Map(), cursor: 0, loadedSeq: -1 }; view.details.set(agentId, detail); }
    if (detail.loading || ((detail.hasMore || detail.error) && !more)) return;
    const seq = view.agents.get(agentId)?.message_seq || 0;
    if (!more && detail.loadedSeq >= seq) return;
    detail.loading = true;
    try {
      const data = await request(view, `/${encodeURIComponent(agentId)}?after=${detail.cursor}`);
      detail.assignment = data.agent?.assignment;
      for (const message of data.messages || []) {
        if (!Number.isInteger(message.seq) || typeof message.id !== "string") continue;
        detail.messages.set(message.id, message);
        detail.cursor = Math.max(detail.cursor, message.seq);
      }
      detail.hasMore = !!data.has_more;
      detail.loadedSeq = seq;
      detail.error = "";
    } catch (error) { detail.error = error.message; }
    finally { detail.loading = false; if (current === view && uid() === view.uid) render(); }
  }
  function ensure() {
    if (sidebar) return;
    sidebar = node("aside", "agent-sidebar");
    sidebar.id = "agentSidebar"; sidebar.hidden = true;
    sidebar.setAttribute("aria-labelledby", "agentSidebarTitle");
    sidebar.tabIndex = -1;
    const header = node("div", "agent-sidebar-header");
    const title = node("h2", "", "Agents"); title.id = "agentSidebarTitle";
    const close = node("button", "agent-sidebar-close", "Close"); close.type = "button";
    const stop = node("button", "agent-sidebar-stop", "Stop run"); stop.type = "button";
    stop.addEventListener("click", async () => {
      const view = current;
      if (!view?.running || uid() !== view.uid) return;
      stop.disabled = true;
      try {
        const token = await window.auth.currentUser.getIdToken();
        if (uid() !== view.uid || view.controller.signal.aborted) return;
        const response = await fetch(`/agent/chats/${encodeURIComponent(view.chatId)}/turns/${encodeURIComponent(view.turnId)}/stop`,
          { method: "POST", headers: { Authorization: `Bearer ${token}` }, signal: view.controller.signal });
        if (!response.ok) throw new Error("The run could not be stopped. Try again.");
        const run = App.runRegistry?.visible?.();
        if (run?.metadata.chatId === view.chatId && run.metadata.agentTurnId === view.turnId) App.runRegistry.cancel(run.runId);
        load(view);
      } catch (error) { view.error = error.message; }
      finally { stop.disabled = false; if (current === view) render(); }
    });
    close.setAttribute("aria-label", "Close agents sidebar");
    close.addEventListener("click", () => hide(true));
    header.append(title, stop, close);
    const usage = node("p", "agent-sidebar-usage");
    const status = node("p", "agent-sidebar-status"); status.setAttribute("role", "status");
    const list = node("div", "agent-session-list");
    sidebar.append(header, usage, status, list);
    sidebar.addEventListener("keydown", event => { if (event.key === "Escape") { event.preventDefault(); hide(true); } });
    sidebar.addEventListener("scroll", () => { if (current) prefs(current); }, { passive: true });
    sidebar._rows = new Map();
    document.body.append(sidebar);
  }
  function hide(manual = false) {
    if (manual && current) { current.closed = true; prefs(current); }
    if (sidebar) sidebar.hidden = true;
    document.body.classList.remove("agent-sidebar-open");
    if (manual) {
      render();
      const trigger = returnFocus?.isConnected ? returnFocus : inline?.querySelector(".agent-sidebar-toggle");
      trigger?.focus();
    }
  }
  function show(agentId, trigger) {
    if (!current) return;
    returnFocus = trigger;
    current.closed = false;
    if (agentId) current.expanded.add(agentId);
    prefs(current); render();
    (sidebar._rows.get(agentId)?.summary || sidebar.querySelector(".agent-sidebar-close")).focus();
  }
  function renderDetail(row, view, agent) {
    const detail = view.details.get(agent.id);
    if (!detail) { row.body.textContent = "Loading messages…"; return; }
    const signature = JSON.stringify([detail.assignment, [...detail.messages.keys()], detail.error, detail.hasMore, agent.sources, agent.result_truncated]);
    if (row.body.dataset.signature === signature) return;
    const scroll = row.body.scrollTop;
    const follow = row.body.scrollHeight - scroll - row.body.clientHeight < 40;
    row.body.dataset.signature = signature;
    row.body.replaceChildren();
    for (const [key, label] of Object.entries({ goal: "Goal", context: "Context", constraints: "Constraints", expected_output: "Expected result", acceptance_criteria: "Checks" })) {
      if (!detail.assignment?.[key]) continue;
      row.body.append(node("h3", "", label), node("p", "", detail.assignment[key]));
    }
    for (const message of [...detail.messages.values()].sort((a, b) => a.seq - b.seq)) {
      const from = message.sender === "orchestrator" ? "Orchestrator" : agent.title;
      const to = message.recipient === "orchestrator" ? "Orchestrator" : agent.title;
      const item = node("div", "agent-message"); item.dataset.messageId = message.id;
      item.append(node("h3", "", `${from} → ${to} · ${message.kind}`), node("p", "", message.text));
      row.body.append(item);
    }
    if (agent.result_truncated) row.body.append(node("p", "", "Result shortened to the configured limit."));
    for (const source of (agent.sources || []).slice(0, 5)) {
      try {
        const url = new URL(source.url);
        if (!["http:", "https:"].includes(url.protocol) || url.username || url.password) continue;
        const link = node("a", "agent-source", source.title || url.hostname);
        link.href = url.href; link.target = "_blank"; link.rel = "noopener noreferrer";
        row.body.append(link);
      } catch (_) { /* Invalid provider citation. */ }
    }
    if (detail.error) row.body.append(node("p", "agent-detail-error", detail.error));
    if (detail.hasMore || detail.error) {
      const more = node("button", "agent-load-more", detail.error ? "Retry" : "Load more messages");
      more.type = "button";
      more.addEventListener("click", () => loadDetail(view, agent.id, true));
      row.body.append(more);
    }
    row.body.scrollTop = follow ? row.body.scrollHeight : scroll;
  }
  function render() {
    if (!window.document?.body) return;
    ensure();
    if (!current || current.uid !== uid()) { hide(); return; }
    const view = current;
    const activity = document.getElementById("agentAnswerActivity");
    const inlineHost = activity?.querySelector("summary") || activity;
    if (inlineHost && (!inline || inline.parentElement !== inlineHost)) {
      inline?.remove(); inline = node("span", "agent-inline-models"); inlineHost.append(inline);
      inline.addEventListener("click", event => { event.preventDefault(); event.stopPropagation(); });
    }
    const inlineSignature = JSON.stringify([view.key, view.closed, [...view.agents.values()].map(a => [a.id, a.title, a.status])]);
    if (inline && inline.dataset.signature !== inlineSignature) {
      inline.dataset.signature = inlineSignature;
      inline.replaceChildren();
      for (const agent of view.agents.values()) {
        if (!activeStates.has(agent.status)) continue;
        const button = node("button", "agent-inline-model"); button.type = "button";
        button.title = `${agent.model?.label || "Model"} · ${agent.title} · ${labels[agent.status]} · ${agent.id.slice(0, 8)}`;
        button.setAttribute("aria-label", button.title); button.append(mark(agent));
        button.addEventListener("click", () => show(agent.id, button)); inline.append(button);
      }
      if (view.agents.size) {
        const button = node("button", "agent-sidebar-toggle", `Agents · ${view.agents.size}`); button.type = "button";
        button.setAttribute("aria-controls", "agentSidebar"); button.setAttribute("aria-expanded", String(!view.closed));
        button.addEventListener("click", () => view.closed ? show(null, button) : hide(true)); inline.append(button);
      }
    }
    sidebar.hidden = view.closed || !view.agents.size;
    document.body.classList.toggle("agent-sidebar-open", !sidebar.hidden);
    sidebar.querySelector(".agent-sidebar-usage").textContent = `Total run · ${cost(view.usage)}`;
    sidebar.querySelector(".agent-sidebar-stop").hidden = !view.running;
    sidebar.querySelector(".agent-sidebar-status").textContent = view.error || "";
    for (const agent of view.agents.values()) {
      let row = sidebar._rows.get(agent.id);
      if (!row) {
        const root = node("details", "agent-session");
        const summary = node("summary");
        const info = node("span", "agent-session-info");
        const title = node("strong", "", agent.title);
        const meta = node("span", "agent-session-meta");
        const body = node("div", "agent-session-detail"); body.tabIndex = 0;
        info.append(title, meta); summary.append(mark(agent), info); root.append(summary, body);
        root.addEventListener("toggle", () => {
          if (current !== view) return;
          if (root.open) { view.expanded.add(agent.id); loadDetail(view, agent.id); }
          else view.expanded.delete(agent.id);
          prefs(view);
        });
        row = { root, summary, title, meta, body };
        sidebar._rows.set(agent.id, row); sidebar.querySelector(".agent-session-list").append(root);
      }
      row.root.dataset.status = agent.status;
      row.title.textContent = `${agent.title} · ${agent.id.slice(0, 6)}`;
      const elapsed = activeStates.has(agent.status) && agent.created_at ? Math.max(0, Date.now() - Date.parse(agent.created_at)) : agent.duration_ms || 0;
      row.meta.textContent = `${labels[agent.status] || "Waiting"} · ${Math.floor(elapsed / 1000)}s · ${cost(agent.usage)}`;
      row.summary.title = `${agent.model?.label || "Model"} · ${agent.title} · ${labels[agent.status] || "Waiting"}`;
      row.root.open = view.expanded.has(agent.id);
      if (row.root.open) { loadDetail(view, agent.id); renderDetail(row, view, agent); }
    }
  }
  function project(spec) {
    resetOwner();
    if (!spec?.chatId || !spec?.turnId || !owner) { current = null; inline?.remove(); inline = null; hide(); return; }
    const view = get(spec.chatId, spec.turnId);
    const changed = current !== view;
    if (changed) {
      if (current) prefs(current);
      current = view; ensure(); sidebar._rows.clear(); sidebar.querySelector(".agent-session-list").replaceChildren();
    }
    if (spec.usage) view.usage = spec.usage;
    view.running = !!spec.running;
    render();
    if (changed) sidebar.scrollTop = view.scroll;
    if (!view.loaded) load(view);
    if (!timer) timer = setInterval(() => {
      resetOwner();
      if (current) { render(); if (current.running) load(current); }
    }, 2500);
  }
  window.addEventListener("consensio:run-registry-change", resetOwner);
  App.agentDelegation = { receive, project, cost };
})();
