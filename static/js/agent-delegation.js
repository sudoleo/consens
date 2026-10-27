// One owner/turn projection drives both inline model icons and the agent sidebar.
(function () {
  "use strict";
  const App = window.App = window.App || {};
  const views = new Map();
  const labels = { waiting: "Waiting", working: "Working", question: "Question", review: "Review",
    rework: "Rework", completed: "Completed", failed: "Failed", stopped: "Stopped" };
  // Judge calls are plumbing: retries and backup models are routine and say
  // nothing about the answer. The panel shows them as ONE row, "Answer check",
  // whose state is the outcome of the checks, not of individual attempts.
  const ended = new Set(["failed", "stopped"]);
  const CHECK_ID = "answer-check";
  const checkNames = { "Differences judge": "differences", "Coverage judge": "coverage", "Text check": "text" };
  function joinNames(names) {
    return names.length > 1 ? `${names.slice(0, -1).join(", ")} and ${names.at(-1)}` : names[0];
  }
  function checkRow(view) {
    const judges = [...view.agents.values()].filter(agent => agent.kind === "judge");
    if (!judges.length) return null;
    const titles = [...new Set(judges.map(agent => agent.title))];
    const done = new Set(titles.filter(title => judges.some(agent => agent.title === title && agent.status === "completed")));
    const busy = judges.filter(agent => activeStates.has(agent.status));
    // Coverage windows start while the answer is still being written
    // (agent_coverage_prefetch); the answer's check is done only after its
    // Differences judge, so finished early windows never read as done, not
    // even when the run ended before the check (then it did not finish).
    const answerCheckOpen = titles.includes("Coverage judge") && !titles.includes("Differences judge");
    const status = view.running && (busy.length || done.size < titles.length || answerCheckOpen) ? "working"
      : done.size === titles.length && !answerCheckOpen ? "completed" : "failed";
    const metered = judges.filter(agent => measured(agent.usage));
    const usage = metered.length ? { input_tokens: metered.reduce((n, a) => n + a.usage.input_tokens, 0),
      output_tokens: metered.reduce((n, a) => n + a.usage.output_tokens, 0),
      complete: metered.every(a => a.usage.complete !== false) } : null;
    // Attempts of one check run one after another, its passes and Coverage
    // windows side by side, and the checks run side by side: a check lasts
    // from its first start to its last end (summing only without start times).
    const duration = Math.max(...titles.map(title => span(view, judges.filter(a => a.title === title))));
    // A pasted text was checked: its result is the card above the answer.
    // Alone and running or done, the answer's own checks have not started yet
    // (or never ran: turns saved before they followed it, 2026-10-09). After
    // a failed one the answer's checks follow as usual.
    const textOnly = titles.length === 1 && titles[0] === "Text check" && (done.size === 1 || busy.length > 0);
    return { id: CHECK_ID, kind: "check", title: textOnly ? "Text check" : "Answer check", status, usage, duration_ms: duration,
      checkedText: titles.includes("Text check"), textOnly,
      progress_text: busy.find(agent => agent.progress_text)?.progress_text || "",
      missing: status === "failed" ? [...titles.filter(title => !done.has(title)).map(title => checkNames[title] || "answer"),
        ...(answerCheckOpen ? ["differences"] : [])] : [] };
  }
  function span(view, agents) {
    const starts = agents.map(agent => Date.parse(agent.created_at));
    if (starts.some(start => !Number.isFinite(start))) return agents.reduce((ms, a) => ms + elapsed(view, a), 0);
    const ends = agents.map((agent, index) => starts[index] + elapsed(view, agent));
    return Math.max(...ends) - Math.min(...starts);
  }
  // A reviewer of the agent's work (audit) goes on in a new session after a
  // failed round or a full conversation (agent_audit.ReviewerSession): ONE
  // row per reviewer, under its first session's id. Its state is that of the
  // session at work, else of the last one; tokens and time cover them all.
  // Until 2026-10-26 a reviewer back after a failed round read as a third
  // reviewer beside the two chosen.
  function reviewerRows(view) {
    const groups = new Map();
    for (const agent of view.agents.values()) {
      if (agent.kind !== "audit") continue;
      const key = agent.model?.model || agent.title;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(agent);
    }
    const rows = new Map();
    for (const sessions of groups.values()) {
      if (sessions.length === 1) { rows.set(sessions[0].id, sessions[0]); continue; }
      sessions.sort((a, b) => (Date.parse(a.created_at) || 0) - (Date.parse(b.created_at) || 0));
      const latest = sessions.find(agent => activeStates.has(agent.status)) || sessions.at(-1);
      const metered = sessions.filter(agent => measured(agent.usage));
      const row = { ...latest, id: sessions[0].id, sessions: sessions.map(agent => agent.id), progressId: latest.id,
        sources: sessions.flatMap(agent => agent.sources || []),
        usage: metered.length ? { input_tokens: metered.reduce((n, a) => n + a.usage.input_tokens, 0),
          output_tokens: metered.reduce((n, a) => n + a.usage.output_tokens, 0),
          complete: metered.length === sessions.length && metered.every(a => a.usage.complete !== false) } : null,
        // The span is live already: no anchor of its own to count on.
        duration_ms: span(view, sessions), runtimeAnchor: undefined,
        duration_incomplete: sessions.some(agent => agent.duration_incomplete) };
      for (const agent of sessions) rows.set(agent.id, agent === sessions[0] ? row : null);
    }
    return rows;
  }
  function rowsFor(view) {
    const check = checkRow(view);
    const reviewers = reviewerRows(view);
    const rows = [...view.agents.values()].filter(agent => agent.kind !== "judge")
      .map(agent => reviewers.has(agent.id) ? reviewers.get(agent.id) : agent).filter(Boolean);
    return [...rows, ...(check ? [check] : [])];
  }
  function findRow(view, id) {
    if (id === CHECK_ID) return checkRow(view);
    const agent = view.agents.get(id);
    return agent?.kind === "audit" ? reviewerRows(view).get(id) || agent : agent;
  }
  // A row's sessions: one, or a reviewer's in order.
  function loadRow(view, agent) {
    for (const id of agent.sessions || [agent.id]) loadDetail(view, id);
  }
  function rowDetail(view, agent) {
    if (!agent.sessions) return view.details.get(agent.id);
    const parts = agent.sessions.map(id => view.details.get(id));
    if (parts.some(part => !part)) return undefined;
    const messages = new Map(parts.flatMap(part => [...part.messages]));
    return { assignment: parts[0].assignment, messages, loading: parts.some(part => part.loading),
      loadedSeq: Math.min(...parts.map(part => part.loadedSeq)), hasMore: parts.some(part => part.hasMore),
      error: parts.find(part => part.error)?.error || "", retry: agent.sessions.find((id, i) => parts[i].hasMore || parts[i].error) };
  }
  function stateLabel(agent) {
    // Ended mid-answer: its text is kept and shown, marked incomplete.
    if (agent.kind === "comparison" && agent.partial && ended.has(agent.status)) return "Incomplete";
    if (agent.kind === "comparison" && agent.status === "failed") return "No answer";
    // A reviewer of the agent's work and answer (Agent audit).
    if (agent.kind === "audit" && agent.status === "failed") return "No review";
    return labels[agent.status] || "Waiting";
  }
  const activeStates = new Set(["waiting", "working", "question", "rework"]);
  let owner = "", current = null, sidebar = null, inline = null, timer = null, returnFocus = null, scrim = null;
  let ownerUser = null, ownerGeneration;
  const uid = () => window.auth?.currentUser?.uid || "";
  // Beside the column on wide screens (the column moves aside, agent-chat.css),
  // a sheet on narrower ones. On every width it opens only on request: the
  // panel glyph or a model icon (2026-10-17, before that it opened by itself
  // for a running turn on a wide screen).
  const wideQuery = window.matchMedia?.('(min-width: 1200px)');
  const wide = () => !wideQuery || wideQuery.matches;
  function setText(el, value) { if (el.textContent !== window.App.t(value)) el.textContent = value; }
  function setTitle(el, value) { if (el.title !== window.App.t(value)) el.title = value; }
  const keyFor = (chat, turn) => `${uid()}:${chat}:${turn}`;
  function node(tag, className, text) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (text !== undefined) el.textContent = text;
    return el;
  }
  function measured(usage) {
    return ['input_tokens', 'output_tokens'].every(key => Number.isInteger(usage?.[key]) && usage[key] >= 0);
  }
  function tokens(usage, pending = false) {
    if (!measured(usage)) return pending ? 'Tokens pending' : 'Tokens unavailable';
    return `${App.format.number(usage.input_tokens + usage.output_tokens)}${usage.complete === false ? '+' : ''} tokens`;
  }
  function tokenDescription(usage) {
    return measured(usage) ? `${App.format.number(usage.input_tokens)} input + ${App.format.number(usage.output_tokens)} output tokens. Reasoning is included in output; cache tokens are included in input.${usage.complete === false ? ' Measured usage so far; some calls did not report usage.' : ''}`
      : 'The provider has not reported token usage.';
  }
  function mark(agent) {
    if (agent.kind === "check") {
      const icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      icon.setAttribute("viewBox", "0 0 16 16"); icon.setAttribute("aria-hidden", "true");
      icon.classList.add("agent-check-mark");
      const path = document.createElementNS(icon.namespaceURI, "path");
      path.setAttribute("d", "M8 1.5 13.5 4v4c0 3-2.3 5.6-5.5 6.5C4.8 13.6 2.5 11 2.5 8V4L8 1.5ZM5.5 8l1.8 1.8L10.8 6.3");
      icon.append(path);
      return icon;
    }
    return App.createModelMark?.(agent.model) || node("span", "model-mark-fallback", (agent.model?.label || "M").slice(0, 1));
  }
  function prefs(view) {
    if (current === view && sidebar) view.scroll = sidebar._list.scrollTop;
    try {
      // Only an explicit open/close is remembered; the default follows the viewport.
      sessionStorage.setItem(`agent-view:${view.key}`, JSON.stringify({ closed: view.manual ? view.closed : undefined,
        expanded: [...view.expanded], scroll: view.scroll }));
    } catch (_) { /* Storage may be unavailable. */ }
  }
  // The panel the reader opened stays open for the chat, also over its next
  // messages (Apple audit A9): a new turn starts with the chat's choice.
  const chatKey = chatId => `agent-panel:${uid()}:${chatId}`;
  function chatPanelOpen(chatId) {
    try { return chatId ? sessionStorage.getItem(chatKey(chatId)) : null; } catch (_) { return null; }
  }
  function rememberChatPanel(view) {
    try { sessionStorage.setItem(chatKey(view.chatId), view.closed ? "closed" : "open"); } catch (_) { /* Storage may be unavailable. */ }
  }
  function resetOwner() {
    if (owner === uid() && ownerUser === window.auth?.currentUser && ownerGeneration === App.authState?.generation) return;
    owner = uid();
    ownerUser = window.auth?.currentUser;
    ownerGeneration = App.authState?.generation;
    for (const view of views.values()) view.controller.abort();
    views.clear(); current = null;
    if (sidebar) { sidebar.hidden = true; clearRows(); App.agentWorkLog?.reset(sidebar._workLog); }
    if (scrim) scrim.hidden = true;
    if (inline) inline.remove();
    inline = null;
    document.body.classList.remove("agent-sidebar-open", "agent-sidebar-sheet");
  }
  function get(chatId, turnId) {
    resetOwner();
    const key = keyFor(chatId, turnId);
    if (!views.has(key)) {
      let saved = {};
      try { saved = JSON.parse(sessionStorage.getItem(`agent-view:${key}`) || "{}"); } catch (_) {}
      const chatChoice = chatPanelOpen(chatId);
      if (typeof saved.closed !== 'boolean' && chatChoice) saved.closed = chatChoice === "closed";
      views.set(key, { key, uid: owner, user: ownerUser, authGeneration: ownerGeneration, chatId, turnId, agents: new Map(), details: new Map(), progress: new Map(),
        controller: new AbortController(), expanded: new Set(saved.expanded || []),
        closed: typeof saved.closed === 'boolean' ? saved.closed : true, manual: typeof saved.closed === 'boolean',
        scroll: saved.scroll || 0, loaded: false, loading: false, running: false, ended: false, settling: false, usage: null, lastSync: 0 });
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
    if (!old || agent.seq > old.seq) {
      view.agents.set(agent.id, {...agent, runtimeAnchor: performance.now()});
      if (!activeStates.has(agent.status)) view.progress.delete(agent.id);
    } else if (agent.seq === old.seq && Number.isFinite(agent.duration_ms) && agent.duration_ms > (old.duration_ms || 0)) {
      old.duration_ms = agent.duration_ms;
      old.runtimeAnchor = performance.now();
    }
  }
  function elapsed(view, agent) {
    const base = Number.isFinite(agent.duration_ms) ? Math.max(0, agent.duration_ms) : 0;
    return base + (view.running && activeStates.has(agent.status) && Number.isFinite(agent.runtimeAnchor)
      ? Math.max(0, performance.now() - agent.runtimeAnchor) : 0);
  }
  function stopClock(view) {
    for (const agent of view.agents.values()) agent.duration_ms = elapsed(view, agent);
    view.running = false;
    view.ended = true;
    view.progress.clear();
  }
  function mergeUsage(view, usage) {
    if (!usage) return;
    const calls = value => (value?.measured_calls || 0) + (value?.unmetered_calls || 0);
    if (calls(usage) < calls(view.usage)) return;
    if (calls(usage) === calls(view.usage) && view.usage?.complete === true && usage.complete === false) return;
    view.usage = usage;
  }
  function receive(context, event) {
    resetOwner();
    if (!App.runRegistry?.isAuthCurrent(context) || event?.version !== 1 || !event.chat_id || !event.turn_id) return;
    if (context.metadata.chatId && context.metadata.chatId !== event.chat_id) return;
    if (context.metadata.agentTurnId && context.metadata.agentTurnId !== event.turn_id) return;
    context.metadata.agentTurnId = event.turn_id;
    context.metadata.delegation = true;
    const view = get(event.chat_id, event.turn_id);
    view.lastSync = Date.now();
    merge(view, event.agent);
    if (current === view) render();
  }
  function receiveProgress(context, event) {
    resetOwner();
    if (!App.runRegistry?.isAuthCurrent(context) || event?.version !== 1
        || event.chat_id !== context.metadata.chatId || event.turn_id !== context.metadata.agentTurnId) return;
    const view = views.get(keyFor(event.chat_id, event.turn_id));
    if (view?.ended) return;
    const agent = view?.agents.get(event.agent_id);
    const previous = view?.progress.get(event.agent_id);
    if (!agent || !activeStates.has(agent.status) || event.session_seq !== agent.seq
        || !Number.isSafeInteger(event.seq) || event.seq <= (previous?.seq || 0)
        || !Number.isSafeInteger(event.chars) || event.chars < 0 || typeof event.streaming !== 'boolean') return;
    view.progress.set(agent.id, {...event, chars: Math.max(previous?.chars || 0, event.chars)});
    if (Number.isFinite(event.duration_ms) && event.duration_ms >= 0) {
      agent.duration_ms = event.duration_ms;
      agent.runtimeAnchor = performance.now();
    }
    view.lastSync = Date.now();
    if (current === view) render();
  }
  async function request(view, suffix = "") {
    const authorized = () => view.user === window.auth?.currentUser && view.authGeneration === App.authState?.generation && !view.controller.signal.aborted;
    if (!authorized()) throw new Error("Account changed");
    const data = await App.withRequestDeadline(async signal => {
      const token = await window.auth.currentUser.getIdToken();
      if (!authorized() || signal.aborted) throw new Error("Account changed");
      const response = await fetch(`/agent/chats/${encodeURIComponent(view.chatId)}/turns/${encodeURIComponent(view.turnId)}/agents${suffix}`,
        { headers: { Authorization: `Bearer ${token}` }, signal });
      if (!response.ok) throw App.httpError(response, await App.readJson(response).catch(() => ({})));
      return App.readJson(response);
    }, { signal: view.controller.signal });
    if (!authorized()) throw new Error("Account changed");
    App.agentChat?.receiveBudget(data.token_budget, view.uid);
    return data;
  }
  async function load(view) {
    if (view.loading || !view.uid || view.local) return;
    view.loading = true;
    view.lastSync = Date.now();
    try {
      const data = await request(view);
      for (const agent of data.agents || []) merge(view, agent);
      // A delayed poll must never revive a run ended by the authoritative SSE.
      if (data.status && !["running", "pending"].includes(data.status)) {
        stopClock(view);
        view.settling = false;
      } else if (data.status) view.settling = !view.running;
      mergeUsage(view, data.usage);
      view.loaded = true; view.error = "";
    } catch (error) { view.error = App.userError(error, { fallback: "The activity couldn’t be loaded. Try again." }); }
    finally {
      view.loading = false;
      if (current === view && uid() === view.uid) {
        render();
        syncTimer();
        if (view.refreshAfterLoad) { view.refreshAfterLoad = false; load(view); }
      }
    }
  }
  async function loadDetail(view, agentId, more = false) {
    // Judge summaries, progress and measured usage are already in the live
    // session snapshot. Their hidden prompt/JSON needs no extra DB request.
    if (view.agents.get(agentId)?.kind === 'judge' || view.local) return;
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
    } catch (error) { detail.error = App.userError(error, { fallback: "These details couldn’t be loaded. Try again." }); }
    finally { detail.loading = false; if (current === view && uid() === view.uid) render(); }
  }
  function ensure() {
    if (sidebar) return;
    sidebar = node("aside", "agent-sidebar");
    sidebar.id = "agentSidebar"; sidebar.hidden = true;
    sidebar.setAttribute("aria-labelledby", "agentSidebarTitle");
    sidebar.tabIndex = -1;
    const header = node("div", "agent-sidebar-header");
    const title = node("h2", "", "Agent activity"); title.id = "agentSidebarTitle";
    const close = node("button", "agent-sidebar-close"); close.type = "button";
    const cross = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    cross.setAttribute("viewBox", "0 0 16 16"); cross.setAttribute("aria-hidden", "true");
    const strokes = document.createElementNS(cross.namespaceURI, "path");
    strokes.setAttribute("d", "M4 4l8 8M12 4l-8 8");
    cross.append(strokes); close.append(cross);
    const stop = node("button", "agent-sidebar-stop"); stop.type = "button";
    stop.append(node("span", "agent-sidebar-stop-glyph"), "Stop run");
    stop.firstChild.setAttribute("aria-hidden", "true");
    stop.addEventListener("click", async () => {
      const view = current;
      if (!view?.running || uid() !== view.uid) return;
      stop.disabled = true;
      try {
        const response = await App.withRequestDeadline(async signal => {
          const token = await view.user.getIdToken();
          if (view.user !== window.auth?.currentUser || view.authGeneration !== App.authState?.generation || signal.aborted) throw new DOMException('Account changed', 'AbortError');
          return fetch(`/agent/chats/${encodeURIComponent(view.chatId)}/turns/${encodeURIComponent(view.turnId)}/stop`,
            { method: "POST", headers: { Authorization: `Bearer ${token}` }, signal });
        }, { signal: view.controller.signal });
        if (view.user !== window.auth?.currentUser || view.authGeneration !== App.authState?.generation) return;
        if (!response.ok) throw App.httpError(response, await App.readJson(response).catch(() => ({})), "The run couldn’t be stopped. Try again.");
        const run = App.runRegistry?.visible?.();
        if (run?.metadata.chatId === view.chatId && run.metadata.agentTurnId === view.turnId) App.runRegistry.cancel(run.runId);
        load(view);
      } catch (error) { view.error = App.userError(error, { fallback: "The run couldn’t be stopped. Try again." }); }
      finally { stop.disabled = false; if (current === view) render(); }
    });
    close.setAttribute("aria-label", "Close agents sidebar");
    close.addEventListener("click", () => hide(true));
    const actions = node("div", "agent-sidebar-actions");
    actions.append(stop, close);
    header.append(title, actions);
    // Run overview: how many calls are through, total usage, and one segment
    // per row in the Consensus pipeline's language (done, running, out).
    const overview = node("div", "agent-sidebar-overview");
    const counts = node("div", "agent-sidebar-counts");
    const progress = node("span", "agent-sidebar-progress");
    // Token figures are the operator's (Apple-Audit H4): admins only.
    const usage = node("span", "agent-sidebar-usage admin-only");
    counts.append(progress, usage);
    const segments = node("div", "agent-sidebar-segments"); segments.setAttribute("aria-hidden", "true");
    overview.append(counts, segments);
    const status = node("p", "agent-sidebar-status"); status.setAttribute("role", "status");
    const list = node("div", "agent-session-list");
    sidebar._list = list;
    // The work log (agent-work-log.js, admins): the list's last child, so it
    // scrolls with the rows; rows are inserted before it.
    sidebar._workLog = node("div", "agent-work-log-host audit-only");
    sidebar._workLog.hidden = true;
    list.append(sidebar._workLog);
    sidebar.append(header, overview, status, list);
    sidebar.setAttribute('role', 'complementary');
    sidebar.addEventListener("keydown", event => {
      if (event.key === "Escape") { event.preventDefault(); hide(true); return; }
      // As a sheet over the chat, keyboard focus stays inside until it closes.
      if (event.key !== 'Tab' || wide()) return;
      const focusable = [...sidebar.querySelectorAll('button, summary, a[href], [tabindex]:not([tabindex="-1"])')]
        .filter(el => !el.hidden && !el.closest('[hidden]') && el.getClientRects().length);
      if (!focusable.length) return;
      const first = focusable[0], last = focusable.at(-1);
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    });
    scrim = node('div', 'agent-sidebar-scrim'); scrim.hidden = true;
    scrim.setAttribute('aria-hidden', 'true');
    scrim.addEventListener('click', () => hide(true));
    document.body.append(scrim);
    wideQuery?.addEventListener?.('change', () => render());
    list.addEventListener("scroll", () => { if (current) prefs(current); }, { passive: true });
    sidebar._rows = new Map();
    document.body.append(sidebar);
  }
  // The rows go; the work log section stays the list's last child.
  function clearRows() {
    if (!sidebar) return;
    sidebar._rows?.clear();
    sidebar._list.replaceChildren(...(sidebar._workLog ? [sidebar._workLog] : []));
  }
  // The panel leaves the way it came (Apple audit C5): it slides and fades
  // out, the sheet's scrim with it, and is hidden only then. Asked to show
  // again while leaving, it simply stays.
  const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)');
  let leaveTimer = 0;
  function setPanelVisible(visible) {
    if (!sidebar) return;
    if (visible) {
      clearTimeout(leaveTimer); leaveTimer = 0;
      sidebar.classList.remove("is-leaving"); scrim?.classList.remove("is-leaving");
      sidebar.hidden = false;
      return;
    }
    if (sidebar.hidden || sidebar.classList.contains("is-leaving")) {
      if (sidebar.hidden && scrim) scrim.hidden = true;
      return;
    }
    if (reducedMotion?.matches) { sidebar.hidden = true; if (scrim) scrim.hidden = true; return; }
    sidebar.classList.add("is-leaving");
    if (scrim && !scrim.hidden) scrim.classList.add("is-leaving");
    leaveTimer = setTimeout(() => {
      leaveTimer = 0;
      if (!sidebar.classList.contains("is-leaving")) return;
      sidebar.classList.remove("is-leaving"); scrim?.classList.remove("is-leaving");
      sidebar.hidden = true;
      if (scrim) scrim.hidden = true;
    }, 200);
  }
  function hide(manual = false) {
    if (manual && current) { current.closed = true; current.manual = true; prefs(current); rememberChatPanel(current); }
    setPanelVisible(false);
    document.body.classList.remove("agent-sidebar-open", "agent-sidebar-sheet");
    if (manual) {
      render();
      const trigger = returnFocus?.isConnected ? returnFocus : inline?.querySelector(".agent-sidebar-toggle");
      // Focus returns without scrolling: the trigger sits at the top of the
      // answer, and the reader may be far below it.
      trigger?.focus({ preventScroll: true });
    }
  }
  // A model icon opens the panel on that model's row, closed: its reasoning
  // and answer open only when the reader asks for them on the row itself.
  function show(agentId, trigger) {
    if (!current) return;
    App.answerReader?.close({ focus: false });
    returnFocus = trigger;
    current.closed = false;
    current.manual = true;
    prefs(current); rememberChatPanel(current); render();
    // A reviewer's later session is shown in its first one's row.
    const grouped = [...reviewerRows(current).values()].find(entry => entry?.sessions?.includes(agentId));
    const row = sidebar._rows.get(grouped?.id || agentId);
    (row?.summary || sidebar.querySelector(".agent-sidebar-close")).focus({ preventScroll: true });
    if (row) { reveal(row.root); point(row.summary); }
  }
  // A short glow names the row the icon stands for among the others.
  function point(summary) {
    summary.classList.remove("is-pointed");
    void summary.offsetWidth;
    summary.classList.add("is-pointed");
    summary.addEventListener("animationend", () => summary.classList.remove("is-pointed"), { once: true });
  }
  // A comparison model's answer is read where answers are read: in the
  // reader, on that model; the answer check opens its differences there.
  // Without a readable answer yet (still running, a delegated worker) the
  // row opens its detail here as before.
  function openInReader(view, agent) {
    const comparisonId = agent?.kind === "check"
      ? [...view.agents.values()].findLast(item => item.kind === "comparison" && item.comparison_id)?.comparison_id
      : agent?.kind === "comparison" ? agent.comparison_id : null;
    const context = comparisonId && App.agentReview?.contextFor?.(null, comparisonId);
    if (!context) return false;
    const trigger = inline?.querySelector(".agent-sidebar-toggle");
    if (agent.kind === "check") {
      return Boolean(context.check) && App.answerReader?.openContext(context, { section: "differences", trigger }) !== false;
    }
    const answer = context.answers?.find(item => (agent.model?.model && item.model === agent.model.model)
      || (agent.model?.label && item.label === agent.model.label));
    return Boolean(answer) && App.answerReader?.openContext(context, { model: answer.provider, trigger }) !== false;
  }
  // A reviewer's work as one overview and one timeline (2026-10-26): rounds
  // without objection fold into one line ("Rounds 1–5 · No objections"), a
  // round with notes lists them, the final review closes it. Before, every
  // round stood under its own heading: a screen of "No objections." per run.
  // The notes come as agent_audit.review_text writes them
  // ("- **kind** · #entry · “quote”: note (source)").
  const NO_OBJECTION = "No objections.";
  const NOTE_LINE = /^- \*\*([a-z_]+)\*\* · (?:#(\d+))?(?: · )?(“[^”]*”)?: (.*?)(?: \((https?:\/\/[^\s)]+)\))?$/;
  const noteKinds = { wrong: "Wrong", doubtful: "Doubtful", incomplete: "Incomplete" };
  const reviewNotes = text => String(text || "").trim() === NO_OBJECTION ? []
    : String(text || "").split("\n").filter(line => line.trim()).map(line => {
      const match = NOTE_LINE.exec(line.trim());
      return match ? { kind: match[1], entry: match[2], quote: match[3], note: match[4], source: match[5] } : { note: line.replace(/^- /, "") };
    });
  const notesLabel = count => !count ? "No objections" : count === 1 ? "1 note" : App.t("{count} notes", { count });
  function reviewTimeline(body, messages, agent) {
    const rounds = messages.filter(message => message.kind === "round");
    const final = messages.findLast(message => message.kind === "result");
    const stats = node("dl", "agent-review-stats");
    const stat = (label, value) => { const item = node("div"); item.append(node("dt", "", label), node("dd", "", value)); stats.append(item); };
    stat("Rounds", App.format.number(rounds.length));
    stat("Notes", App.format.number(rounds.reduce((n, message) => n + reviewNotes(message.text).length, 0)));
    stat("Final review", final ? App.format.number(reviewNotes(final.text).length) : activeStates.has(agent.status) ? "Pending" : "None");
    body.append(stats);
    const list = node("ol", "agent-review-rounds");
    const entry = (label, state, message, notes) => {
      const item = node("li", "agent-review-round");
      item.classList.toggle("is-quiet", !notes?.length);
      const head = node("div", "agent-review-round-head");
      const time = node("time", "agent-review-round-time", App.format.time(message.created_at));
      if (message.created_at) time.dateTime = message.created_at;
      head.append(node("span", "agent-review-round-label", label), node("span", "agent-review-round-state", state), time);
      item.append(head);
      if (notes?.length) item.append(noteList(notes, agent));
      list.append(item);
      return item;
    };
    let round = 0, quiet = null;
    for (const message of messages) {
      if (message.kind === "round") {
        round += 1;
        const notes = reviewNotes(message.text);
        if (!notes.length && quiet) {
          quiet.label.textContent = App.t("Rounds {first}–{last}", { first: quiet.first, last: round });
          continue;
        }
        const item = entry(App.t("Round {n}", { n: round }), notesLabel(notes.length), message, notes);
        quiet = notes.length ? null : { first: round, label: item.querySelector(".agent-review-round-label") };
      } else if (message.kind === "result") {
        quiet = null;
        const notes = reviewNotes(message.text);
        entry("Final review", notesLabel(notes.length), message, notes).classList.add("is-final");
      } else if (message.kind === "failure") {
        // Why a round or the review brought nothing: in its place in time.
        quiet = null;
        const item = entry("No result", "", message);
        item.classList.add("is-failed");
        item.append(node("p", "agent-review-round-reason", message.text));
      }
    }
    if (list.childElementCount) body.append(list);
    else body.append(node("p", "agent-judge-note", activeStates.has(agent.status) ? "Follows the work from its first step." : "No rounds."));
  }
  function noteList(notes, agent) {
    const list = node("ul", "agent-review-notes");
    for (const note of notes) {
      const item = node("li", "agent-review-note");
      if (note.kind) item.dataset.kind = note.kind;
      const head = node("span", "agent-review-note-where");
      if (note.kind) head.append(node("strong", "", noteKinds[note.kind] || note.kind));
      // The work log's number: for those who can open the log (admins).
      if (note.entry) head.append(node("span", "admin-only", App.t("Step {entry}", { entry: note.entry })));
      if (head.childElementCount) item.append(head);
      if (note.quote) {
        // The words of the answer it is about.
        const quote = node("q", "agent-review-note-quote", note.quote.replace(/^“|”$/g, ""));
        quote.dataset.i18nSkip = "";
        item.append(quote);
      }
      // The reviewer's own words.
      const text = node("p", "agent-review-note-text", note.note);
      text.dataset.i18nSkip = "";
      item.append(text);
      if (note.source) {
        try {
          const url = new URL(note.source);
          const link = node("a", "agent-review-note-source", url.hostname.replace(/^www\./, ""));
          link.href = url.href; link.target = "_blank"; link.rel = "noopener noreferrer";
          item.append(link);
        } catch (_) { /* Not a link. */ }
      }
      list.append(item);
    }
    return list;
  }
  function renderDetail(row, view, agent) {
    if (agent.kind === 'check') {
      const signature = JSON.stringify([agent.status, agent.usage, agent.progress_text, agent.missing]);
      if (row.body.dataset.signature === signature) return;
      row.body.dataset.signature = signature;
      row.body.setAttribute('aria-busy', 'false');
      row.body.replaceChildren(node('p', 'agent-judge-purpose', agent.textOnly
        ? 'Checks each sentence of your text against the independent answers.'
        : 'Checks which statements are supported by the comparison answers and where those answers disagree.'));
      if (agent.progress_text) row.body.append(node('p', 'agent-session-progress', agent.progress_text));
      if (measured(agent.usage)) {
        const usage = node('dl', 'agent-token-breakdown admin-only'); usage.title = tokenDescription(agent.usage);
        for (const [label, count] of [['Input', agent.usage.input_tokens], ['Output', agent.usage.output_tokens]]) {
          const item = node('div'); item.append(node('dt', '', label), node('dd', '', App.format.number(count))); usage.append(item);
        }
        row.body.append(usage);
      }
      const names = agent.missing;
      row.body.append(node('p', 'agent-judge-note', agent.status === 'working' ? 'Check in progress.'
        : names.length === 1 ? `The ${joinNames(names)} check could not run. The answer is shown without it.`
        : names.length ? `The ${joinNames(names)} checks could not run. The answer is shown without them.`
          : agent.textOnly ? 'The check of your text is shown above the answer.'
            : agent.checkedText ? 'The check of your text is shown above the answer, the rest under Review.'
            : 'Results are marked in the answer and listed under Review.'));
      return;
    }
    const detail = rowDetail(view, agent);
    const loading = !detail || (detail.loading && detail.loadedSeq < 0);
    row.body.setAttribute('aria-busy', String(Boolean(detail?.loading || loading)));
    if (loading) {
      if (!row.body.querySelector('.agent-detail-skeleton')) {
        const skeleton = node('div', 'agent-detail-skeleton'); skeleton.setAttribute('role', 'status'); skeleton.setAttribute('aria-label', 'Loading details');
        for (let i = 0; i < 3; i++) { const bar = node('span'); bar.setAttribute('aria-hidden', 'true'); skeleton.append(bar); }
        row.body.replaceChildren(skeleton); delete row.body.dataset.signature;
      }
      return;
    }
    const signature = JSON.stringify([detail.assignment, [...detail.messages.keys()], detail.error, detail.hasMore, detail.loading, agent.sources, agent.result_truncated, agent.progress_text, agent.status]);
    if (row.body.dataset.signature === signature) return;
    row.body.dataset.signature = signature;
    row.body.replaceChildren();
    if (agent.progress_text) {
      row.body.append(node("h3", "", "Reasoning highlights"), node("p", "agent-session-progress", agent.progress_text));
    }
    for (const [key, label] of Object.entries({ goal: "Goal", context: "Context", constraints: "Constraints", expected_output: "Expected result", acceptance_criteria: "Checks" })) {
      if (!detail.assignment?.[key]) continue;
      // A comparison answer's goal only repeats its row title.
      if (agent.kind === "comparison" && key === "goal") continue;
      if (agent.kind === "judge" && key === "context") continue;
      // A reviewer's saved assignment only names its task, as its row title does.
      if (agent.kind === "audit") continue;
      if (agent.kind === "comparison" && key === "context") {
        let context = detail.assignment[key];
        try { const task = JSON.parse(context); context = [task.question, task.context].filter(Boolean).join("\n\n"); } catch (_) {}
        const task = node("details", "agent-session-task"); task.append(node("summary", "", "Comparison task"), node("p", "", context)); row.body.append(task); continue;
      }
      row.body.append(node("h3", "", label), node("p", "", detail.assignment[key]));
    }
    // A reviewer's sessions follow one another: their messages in time order.
    if (agent.kind === "audit") reviewTimeline(row.body, [...detail.messages.values()].sort((a, b) =>
      ((Date.parse(a.created_at) || 0) - (Date.parse(b.created_at) || 0)) || a.seq - b.seq), agent);
    else for (const message of [...detail.messages.values()].sort((a, b) => a.seq - b.seq)) {
      if (agent.kind === "judge" && message.kind === "result") continue;
      const from = message.sender === "orchestrator" ? "Orchestrator" : agent.title;
      const to = message.recipient === "orchestrator" ? "Orchestrator" : agent.title;
      const item = node("div", "agent-message"); item.dataset.messageId = message.id;
      // A comparison model has one reply: its answer, or why none arrived.
      // Routing labels ("→ Orchestrator · failure") are plumbing there.
      if (agent.kind === "comparison") {
        if (message.kind === "failure") { row.body.append(node("p", "agent-judge-note", message.text)); continue; }
        if (message.kind === "result") item.append(node("h3", "", "Answer"));
        if (message.kind === "partial") item.append(node("h3", "", "Incomplete answer · not used"));
      } else item.append(node("h3", "", `${from} → ${to} · ${message.kind}`));
      const text = node("div", "consensus-answer-body agent-message-body");
      if (window.injectMarkdown) window.injectMarkdown(text, message.text, agent.sources || []);
      else text.textContent = message.text;
      item.append(text);
      row.body.append(item);
    }
    if (agent.result_truncated) row.body.append(node("p", "agent-judge-note", "Result shortened to the configured limit."));
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
      more.addEventListener("click", () => loadDetail(view, detail.retry || agent.id, true));
      row.body.append(more);
    }
  }
  const settled = new Set(["completed", ...ended]);
  function renderOverview(view, rows) {
    const done = rows.filter(agent => settled.has(agent.status)).length;
    const out = rows.filter(agent => ended.has(agent.status)).length;
    setText(sidebar.querySelector(".agent-sidebar-progress"), !rows.length && view.running ? "Starting…"
      // Each part through App.t: an optional tail glued to a sentence
      // matches no dictionary entry (docs/i18n.md).
      : [window.App.t("{done} of {total} done", { done, total: rows.length }),
        out ? window.App.t("{out} without result", { out }) : ""].filter(Boolean).join(" · "));
    const segments = sidebar.querySelector(".agent-sidebar-segments");
    while (segments.children.length > rows.length) segments.lastElementChild.remove();
    while (segments.children.length < rows.length) segments.append(node("i"));
    rows.forEach((agent, i) => {
      const segment = segments.children[i];
      const state = agent.status === "completed" ? "done" : ended.has(agent.status) ? "out"
        : view.running && activeStates.has(agent.status) ? "busy" : "idle";
      if (segment.dataset.state !== state) segment.dataset.state = state;
    });
  }
  function reveal(root) {
    const list = sidebar._list;
    // Before layout settles the detail may still be a skeleton; the frame
    // after it has its first height.
    (window.requestAnimationFrame || setTimeout)(() => {
      if (!root.isConnected || !list.scrollBy) return;
      const top = root.getBoundingClientRect().top - list.getBoundingClientRect().top;
      const bottom = top + root.offsetHeight;
      const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
      // Taller than the list: start of the row at the top. Otherwise the least
      // movement that shows the whole row.
      const delta = top < 0 || root.offsetHeight > list.clientHeight ? top
        : bottom > list.clientHeight ? bottom - list.clientHeight : 0;
      if (Math.abs(delta) > 1) list.scrollBy({ top: delta, behavior: reduce ? "auto" : "smooth" });
    });
  }
  function render() {
    if (!window.document?.body) return;
    ensure();
    if (!current || (!current.local && current.uid !== uid())) { hide(); return; }
    const view = current;
    const activity = document.getElementById("agentAnswerActivity");
    const inlineHost = activity?.querySelector("summary") || activity;
    if (inlineHost && (!inline || inline.parentElement !== inlineHost)) {
      inline?.remove(); inline = node("span", "agent-inline-models"); inlineHost.append(inline);
      inline.addEventListener("click", event => { event.preventDefault(); event.stopPropagation(); });
    }
    const inlineSignature = JSON.stringify([view.key, view.closed, (view.seed || []).length, Boolean(view.workLog),
      [...view.agents.values()].map(a => [a.id, a.title, a.status, a.model?.model, a.model?.label])]);
    if (inline && inline.dataset.signature !== inlineSignature) {
      inline.dataset.signature = inlineSignature;
      if (inline._viewKey !== view.key) {
        inline._viewKey = view.key;
        inline._buttons = new Map();
        inline._stack = node("span", "agent-model-stack");
        // A quiet panel glyph beside the model icons instead of a text chip.
        const toggle = node("button", "agent-sidebar-toggle"); toggle.type = "button";
        toggle.setAttribute("aria-controls", "agentSidebar");
        const glyph = document.createElementNS("http://www.w3.org/2000/svg", "svg");
        glyph.setAttribute("viewBox", "0 0 16 16"); glyph.setAttribute("aria-hidden", "true");
        const frame = document.createElementNS(glyph.namespaceURI, "path");
        frame.setAttribute("d", "M2.5 3.5h11v9h-11zM10 3.5v9");
        glyph.append(frame); toggle.append(glyph);
        toggle.addEventListener("click", () => view.closed ? show(null, toggle) : hide(true));
        inline._toggle = toggle;
        // The workspace beside it once the run worked there (workspace-view.js):
        // agent-chat.css shows it when the activity holds a VM step.
        const workspace = node("button", "agent-workspace-toggle workspace-only");
        workspace.type = "button";
        workspace.setAttribute("aria-label", "Open the workspace");
        workspace.title = "Workspace";
        const screen = document.createElementNS("http://www.w3.org/2000/svg", "svg");
        screen.setAttribute("viewBox", "0 0 16 16"); screen.setAttribute("aria-hidden", "true");
        const outline = document.createElementNS(screen.namespaceURI, "path");
        outline.setAttribute("d", "M2.5 3h11v7.5h-11zM6 13.5h4M8 10.5v3");
        screen.append(outline); workspace.append(screen);
        workspace.addEventListener("click", () => App.workspaceView?.open());
        inline._workspace = workspace;
        inline.replaceChildren(inline._stack, toggle, workspace);
      }
      const models = new Map();
      for (const agent of view.agents.values()) {
        // Judges and the helper that opens a source (read_source) are not
        // voices of the answer: no icon in the stack, a row in the panel.
        if (agent.kind === "judge" || agent.kind === "source") continue;
        const key = agent.model?.model || agent.id;
        if (!models.has(key)) models.set(key, []);
        models.get(key).push(agent);
      }
      // A saved turn's icons stand at once, from its review (Apple audit
      // A10); the agent list arrives later and only completes them.
      if (!view.agents.size) {
        for (const seed of view.seed || []) {
          const key = seed.model?.model || seed.model?.label;
          if (key && !models.has(key)) models.set(key, [{ id: "", status: "completed", model: seed.model }]);
        }
      }
      let added = 0;
      for (const [key, calls] of models) {
        const agent = calls.find(a => activeStates.has(a.status)) || calls[0];
        let button = inline._buttons.get(key);
        if (!button) {
          button = node("button", "agent-inline-model"); button.type = "button";
          // Only a model joining a live run settles in; a saved turn's
          // icons are simply there (Apple audit A10). The class goes once the
          // entry ran, so moving the turn into the history replays nothing.
          if (view.running) {
            button.classList.add("is-arriving");
            button.style.setProperty('--agent-icon-delay', `${Math.min(added++, 4) * 24}ms`);
            button.addEventListener("animationend", () => button.classList.remove("is-arriving"), { once: true });
          }
          button.append(mark(agent));
          button.addEventListener("click", () => show(button.dataset.agentId, button));
          inline._buttons.set(key, button); inline._stack.append(button);
        }
        // Translated part by part: the model name, the count and the state.
        button.title = [agent.model?.label || App.t("Model"), calls.length === 1 ? App.t("1 call") : App.t("{n} calls", { n: calls.length }),
          App.t(labels[agent.status] || "Waiting")].join(" · ");
        button.dataset.status = agent.status;
        button.dataset.agentId = agent.id;
        button.setAttribute("aria-label", button.title);
      }
      for (const [key, button] of inline._buttons) {
        if (!models.has(key)) { button.remove(); inline._buttons.delete(key); }
      }
      inline._toggle.hidden = !view.agents.size && !(view.seed || []).length && !view.workLog;
      const activityLabel = `Activity · ${rowsFor(view).length}`;
      inline._toggle.setAttribute("aria-label", activityLabel);
      inline._toggle.title = activityLabel;
      inline._toggle.setAttribute("aria-expanded", String(!view.closed));
    }
    // A running turn of a chat whose panel is open shows it before its first
    // call arrives ("Starting…"), so a follow-up never closes it in between.
    // A turn with a work log keeps its panel also without any model call
    // (audit mode with the answer check off).
    const panelVisible = !view.closed && (view.agents.size > 0 || view.running || Boolean(view.workLog));
    setPanelVisible(panelVisible);
    const sheet = panelVisible && !wide();
    if (sheet) scrim.hidden = false;
    else if (!sidebar.classList.contains("is-leaving")) scrim.hidden = true;
    if (sheet) sidebar.setAttribute('aria-modal', 'true'); else sidebar.removeAttribute('aria-modal');
    sidebar.setAttribute('role', sheet ? 'dialog' : 'complementary');
    document.body.classList.toggle("agent-sidebar-open", panelVisible);
    document.body.classList.toggle("agent-sidebar-sheet", sheet);
    const usageEl = sidebar.querySelector(".agent-sidebar-usage");
    setText(usageEl, tokens(view.usage, view.running));
    setTitle(usageEl, `Total run. ${tokenDescription(view.usage)}`);
    sidebar.querySelector(".agent-sidebar-stop").hidden = !view.running || view.local;
    setText(sidebar.querySelector(".agent-sidebar-status"), view.error || (view.settling ? "Finishing pending model calls…" : ""));
    const visible = rowsFor(view);
    renderOverview(view, visible);
    for (const [id, row] of sidebar._rows) {
      if (!visible.some(agent => agent.id === id)) { row.root.remove(); sidebar._rows.delete(id); }
    }
    for (const agent of visible) {
      let row = sidebar._rows.get(agent.id);
      if (!row) {
        const root = node("details", "agent-session");
        const summary = node("summary");
        const info = node("span", "agent-session-info");
        const heading = node('span', 'agent-session-heading');
        const title = node("strong", "", agent.title);
        const role = node('span', 'agent-session-role');
        const meta = node("span", "agent-session-meta");
        const state = node('span', 'agent-session-state');
        state.id = `agent-session-state-${agent.id}`;
        const usage = node('span', 'agent-session-tokens admin-only');
        heading.append(title, usage);
        meta.append(role, state);
        // The detail flows inside the one scrolling list; a second scroll
        // area beside it made two scrollbars and trapped the wheel.
        const body = node("div", "agent-session-detail");
        info.append(heading, meta); summary.append(mark(agent), info); root.append(summary, body);
        summary.setAttribute('aria-describedby', state.id);
        // An open row folds away like any other (its chevron says so); only
        // a closed one opens the answer reader.
        summary.addEventListener("click", event => {
          if (current === view && !root.open && openInReader(view, findRow(view, agent.id))) event.preventDefault();
        });
        root.addEventListener("toggle", () => {
          if (current !== view || view.uid !== uid() || !window.document?.body || !root.isConnected) return;
          if (root.open) {
            view.expanded.add(agent.id);
            const shown = findRow(view, agent.id);
            if (shown && shown.kind !== "check") loadRow(view, shown);
            renderDetail(row, view, shown);
            // Opened by the reader (click, key or a model icon), not restored:
            // bring its start into view. The heading then sticks while reading.
            if (document.activeElement === summary) reveal(root);
          }
          else view.expanded.delete(agent.id);
          prefs(view);
        });
        row = { root, summary, title, role, state, usage, body };
        sidebar._rows.set(agent.id, row); sidebar._list.insertBefore(root, sidebar._workLog);
      }
      row.root.dataset.status = agent.status;
      // The check row belongs at the end (before the work log); answer rows
      // that arrive later go above it.
      if (agent.kind === "check" && row.root.nextElementSibling !== sidebar._workLog) {
        sidebar._list.insertBefore(row.root, sidebar._workLog);
      }
      setText(row.title, agent.model?.label || agent.title);
      setText(row.role, agent.kind === 'comparison' ? 'Independent answer' : agent.kind === 'audit' ? 'Reviewer'
        : agent.kind === 'check' ? (agent.textOnly ? 'Your text, sentence by sentence' : 'Differences and coverage') : agent.title);
      row.role.hidden = row.role.textContent === row.title.textContent;
      // The state through App.t first: the line glued to the time matches no
      // entry ("No review · 8 Sek." stayed half English, 2026-10-26).
      setText(row.state, `${App.t(stateLabel(agent))} · ${agent.duration_incomplete ? '≥ ' : ''}${App.format.duration(elapsed(view, agent))}`);
      setTitle(row.state, agent.duration_incomplete ? 'Last confirmed elapsed time before the server connection ended.' : 'Elapsed session time, including waiting and review.');
      const pending = view.running && ['waiting', 'working', 'rework'].includes(agent.status);
      const progress = pending ? view.progress.get(agent.progressId || agent.id) : null;
      const loading = pending && progress?.streaming !== false;
      const usage = measured(progress?.usage) ? progress.usage : agent.usage;
      const chars = loading && progress?.chars > 0 && !measured(progress.usage);
      // A call that ended without a result and without reported usage has no
      // number worth showing; "Tokens unavailable" there only reads as a fault.
      const silent = ended.has(agent.status) && !measured(usage);
      setText(row.usage, silent ? '' : chars ? `${App.format.number(progress.chars)} chars` : tokens(usage, loading));
      row.usage.hidden = silent;
      setTitle(row.usage, chars ? 'Received answer and visible reasoning characters. Token usage has not yet been reported for this call.' : tokenDescription(usage));
      // A live call shows itself in words ("Working · 14s") and a counting
      // number, not in a travelling bar: the panel stays still while it works.
      row.usage.classList.toggle('is-loading', loading);
      row.root.open = view.expanded.has(agent.id);
      if (row.root.open) { if (agent.kind !== "check") loadRow(view, agent); renderDetail(row, view, agent); }
    }
    App.agentWorkLog?.render(sidebar._workLog, view);
  }
  // A follow-up moves the live turn into the history (agent-chat.js
  // liveTurn.take): its icons go with it as they are and from then on open
  // that turn's answers in the reader, like the icons of any earlier turn.
  // The panel glyph stays with the live turn, which gets new icons.
  function release() {
    if (!inline) return;
    const view = current, old = inline;
    inline = null;
    old._toggle?.remove();
    old._workspace?.remove();
    old.addEventListener("click", event => {
      const button = event.target.closest?.(".agent-inline-model");
      event.preventDefault(); event.stopPropagation();
      const agent = button && view?.agents.get(button.dataset.agentId);
      if (agent) openInReader(view, agent);
    }, true);
  }
  function project(spec) {
    resetOwner();
    // A new message of a chat whose panel is open: the panel waits for the
    // new turn's calls instead of closing and opening again (Apple audit A9).
    if (spec?.chatId && !spec.turnId && spec.running && owner && chatPanelOpen(spec.chatId) === "open"
        && sidebar && !sidebar.hidden && !sidebar.classList.contains("is-leaving")) {
      if (current) prefs(current);
      current = null; inline?.remove(); inline = null;
      clearRows();
      App.agentWorkLog?.render(sidebar._workLog, null);
      setText(sidebar.querySelector(".agent-sidebar-progress"), "Starting…");
      setText(sidebar.querySelector(".agent-sidebar-usage"), "");
      sidebar.querySelector(".agent-sidebar-segments")?.replaceChildren();
      setText(sidebar.querySelector(".agent-sidebar-status"), "");
      sidebar.querySelector(".agent-sidebar-stop").hidden = true;
      syncTimer();
      return;
    }
    if (!spec?.chatId || !spec?.turnId || !owner) { current = null; inline?.remove(); inline = null; hide(); syncTimer(); return; }
    const view = get(spec.chatId, spec.turnId);
    const changed = current !== view;
    const wasRunning = view.running;
    if (changed) {
      if (current) prefs(current);
      current = view; ensure(); clearRows();
    }
    mergeUsage(view, spec.usage);
    if (Array.isArray(spec.models)) view.seed = spec.models;
    // The turn has a work log (admins, audit mode): once known, it stays.
    if (spec.workLog) view.workLog = true;
    if (wasRunning && !spec.running) { stopClock(view); view.settling = true; }
    view.running = !!spec.running && !view.ended;
    if (!view.running) view.progress.clear();
    render();
    if (changed) sidebar._list.scrollTop = view.scroll;
    if (wasRunning && !spec.running && view.loading) view.refreshAfterLoad = true;
    else if (!view.loaded || (wasRunning && !spec.running)) load(view);
    syncTimer();
  }
  // Ticks elapsed labels and repairs a quiet stream while something runs; a
  // saved or finished turn keeps no timer at all.
  function syncTimer() {
    const live = Boolean(current && (current.running || current.settling));
    if (!live) { clearInterval(timer); timer = null; return; }
    if (timer) return;
    timer = setInterval(() => {
      resetOwner();
      if (!current || !(current.running || current.settling)) { clearInterval(timer); timer = null; return; }
      if (document.visibilityState === 'hidden') return;
      if (current.running && [...current.agents.values()].some(agent => activeStates.has(agent.status))) render();
      // SSE already carries session updates. Poll only to repair a quiet or
      // interrupted stream, instead of rereading every agent every 2.5s.
      if (Date.now() - current.lastSync >= 10000) load(current);
    }, 2500);
  }
  // demo.js plays a turn the server never sees. Its rows arrive here as a
  // whole snapshot each time (null releases them), so the demo shows the same
  // model icons, panel and light as a real run: no requests, no stop.
  const demoAgent = /^[\w-]{1,64}$/;
  function demo(spec) {
    resetOwner();
    if (!spec) {
      if (!current?.local) return;
      views.delete(current.key); current = null; inline?.remove(); inline = null; hide(); syncTimer(); return;
    }
    let view = views.get("demo");
    if (!view || view.turnId !== spec.turnId) {
      view = { key: "demo", local: true, uid: owner, chatId: "demo", turnId: spec.turnId, agents: new Map(), details: new Map(),
        progress: new Map(), controller: new AbortController(), expanded: new Set(), closed: true, manual: false,
        scroll: 0, loaded: true, loading: false, running: true, ended: false, settling: false, usage: null, lastSync: Date.now() };
      views.set("demo", view);
    }
    if (current !== view) {
      current = view; ensure(); clearRows();
    }
    for (const agent of spec.agents || []) {
      if (!demoAgent.test(agent?.id || "")) continue;
      const old = view.agents.get(agent.id);
      // The clock runs here, as for a real call: it keeps going while the
      // status stays and freezes when the call is through.
      const same = old && old.status === agent.status;
      view.agents.set(agent.id, { ...agent, duration_ms: same ? old.duration_ms : old ? elapsed(view, old) : 0,
        runtimeAnchor: same ? old.runtimeAnchor : performance.now() });
      if (agent.text && !view.details.get(agent.id)?.messages.size) {
        view.details.set(agent.id, { messages: new Map([[`${agent.id}:answer`, { id: `${agent.id}:answer`, seq: 1, kind: "result",
          sender: agent.id, recipient: "orchestrator", text: agent.text }]]), cursor: 1, loadedSeq: 1 });
      } else if (!view.details.has(agent.id)) view.details.set(agent.id, { messages: new Map(), cursor: 0, loadedSeq: 0 });
    }
    view.usage = spec.usage || view.usage;
    if (view.running && !spec.running) stopClock(view);
    view.running = Boolean(spec.running) && !view.ended;
    render();
    syncTimer();
  }
  window.addEventListener("consensio:run-registry-change", resetOwner);
  document.addEventListener("consensio:reader-opening", () => {
    if (current) { current.closed = true; prefs(current); hide(); render(); }
  });
  // The newest reasoning line of each comparison model still answering, in
  // the order the models joined, for the otherwise quiet "Comparing
  // perspectives…" phase: the activity preview quotes them in turn
  // (agent-activity.js). Live only: data the run streams anyway, never a
  // request of its own.
  function liveHighlights(chatId, turnId) {
    const view = chatId && turnId ? views.get(keyFor(chatId, turnId)) : null;
    if (!view || view.ended) return [];
    const lines = [];
    let order = 0;
    for (const agent of view.agents.values()) {
      if (agent.kind !== "comparison") continue;
      order += 1;
      if (!activeStates.has(agent.status) || !agent.progress_text) continue;
      // Same cleanup as agentActivity's compactReasoning: no markdown marks.
      const text = String(agent.progress_text).split("\n")
        .map(line => line.replace(/^[#*>\s-]+/, "").replace(/\*\*|__|`/g, "").replace(/\s+/g, " ").trim())
        .filter(Boolean).at(-1);
      if (text) lines.push({ id: agent.id, order, label: agent.model?.label || "", text });
    }
    return lines;
  }
  App.agentDelegation = { receive, receiveProgress, project, release, demo, tokens, liveHighlights, isTicking: () => Boolean(timer) };
})();
