// Single-model execution, using the shared composer, run registry and history.
(function () {
  "use strict";
  const App = window.App = window.App || {};
  const registry = App.runRegistry;
  let catalog = null;
  let catalogOwner = "";
  let catalogStatus = "idle";
  // The model list usually arrives within a moment. Its "Loading…" notice
  // only shows when the wait is noticeable: flashing it on every reload
  // pushed the centred composer up and back down.
  const LOADING_NOTICE_DELAY_MS = 1200;
  let loadingNoticeSince = 0, loadingNoticeTimer = null;
  let loadGeneration = 0;
  let catalogUser = null, catalogAuthGeneration, budgetRefresh = null, budgetTimer = null;
  // Shell/run split: the composer shell renders only when one of its inputs
  // changes, never for a streamed text chunk.
  let shellSignature = '';
  // projectFrame() runs once per run on screen; viewEpoch changes whenever
  // the view leaves that run, so returning to it frames it again.
  let frameKey = '', viewEpoch = 0, framedRunId = null;
  // The local demo (demo.js) plays a scripted Agent turn on the real answer
  // surface, also for guests without Agent access. While it is on screen the
  // panel stays visible; the first real run or a new chat ends it.
  let demoView = false;
  const selections = new Map();
  const cssId = value => (window.CSS?.escape ? CSS.escape(value) : String(value).replace(/["\\]/g, '\\$&'));
  const effortCopy = {
    default: ["Auto", "Use the model’s default reasoning"],
    none: ["Off", "Answer without extended reasoning"],
    minimal: ["Minimal", "Keep reasoning to a minimum"],
    low: ["Low", "Spend less time reasoning"],
    medium: ["Medium", "Balance depth and response time"],
    high: ["High", "Spend more time on complex questions"],
    xhigh: ["Extra high", "Explore the question in greater depth"],
    max: ["Max", "Use the highest supported reasoning effort"],
  };

  function selectionKey() {
    const context = registry.visible();
    const basis = registry.getSelectedConversationBasis({ includeHistory: false });
    return `${catalogOwner}:${context?.metadata.chatId || context?.basis?.chatId || basis?.chatId || (context ? `run:${context.runId}` : "draft")}`;
  }
  function preferredSelection() {
    const context = registry.visible();
    const basis = registry.getSelectedConversationBasis({ includeHistory: false });
    const saved = context?.consensus.completedTurn?.agent_settings || context?.metadata.agentSettings || basis?.currentTurn?.agent_settings;
    if (context && registry.isExecuting(context.runId)) return context.config.agentSettings || saved;
    let preferred;
    try { preferred = JSON.parse(localStorage.getItem(`agent_settings_${catalogOwner}`) || "null"); } catch (_) {}
    return selections.get(selectionKey()) || saved || preferred || { model_id: catalog?.default_model_id, reasoning_effort: "default" };
  }
  // Premium models stay Pro in Agent as in every other mode. They stay in the
  // list with their badge; the server refuses them for other tiers as well.
  function locked(model) {
    return Boolean(model?.premium) && window.App?.state?.get?.("isUserPro") !== true;
  }
  function selectable(model) {
    return Boolean(model) && model.available !== false && !locked(model);
  }
  function selection() {
    const preferred = preferredSelection() || {};
    const available = catalog?.models.filter(selectable);
    const model = available?.find(item => item.id === preferred.model_id)
      || available?.find(item => item.id === catalog.default_model_id) || available?.[0];
    return model ? { model_id: model.id,
      reasoning_effort: model.reasoning_efforts.includes(preferred.reasoning_effort) ? preferred.reasoning_effort : "default" } : preferred;
  }
  function rememberSelection(value) {
    selections.set(selectionKey(), value);
    try { localStorage.setItem(`agent_settings_${catalogOwner}`, JSON.stringify(value)); } catch (_) {}
  }
  async function loadModels() {
    if (!canUse() || catalogStatus !== "idle") return;
    const uid = catalogOwner;
    const user = window.auth.currentUser;
    const generation = ++loadGeneration;
    catalogStatus = "loading";
    try {
      const { response, data } = await App.withRequestDeadline(async signal => {
        const token = await user.getIdToken();
        if (user !== window.auth?.currentUser || generation !== loadGeneration || signal.aborted) throw new Error('Account changed');
        const response = await fetch("/agent/models", { headers: { Authorization: `Bearer ${token}` }, signal });
        return { response, data: await response.json() };
      });
      if (user !== window.auth?.currentUser || generation !== loadGeneration || !canUse()) return;
      if (!response.ok || !Array.isArray(data.models) || !data.models.length) throw new Error("Model list unavailable");
      catalog = data;
      catalogStatus = "ready";
      receiveBudget(data.token_budget, uid);
    } catch (_) {
      if (uid === catalogOwner && generation === loadGeneration) catalogStatus = "failed";
    } finally {
      if (uid === catalogOwner && generation === loadGeneration) render();
    }
  }
  // Agent and the pipeline share one daily token account. Validation,
  // ordering of concurrent snapshots and the account owner fence live in
  // App.tokenBudget (token-budget.js); Agent only feeds it.
  // When the allowance was last confirmed (a fetch or a run's own report).
  let budgetSeenAt = 0;
  function receiveBudget(budget, uid) {
    if (!budget || !canUse() || uid !== window.auth?.currentUser?.uid) return;
    budgetSeenAt = Date.now();
    App.tokenBudget?.apply?.(budget, { uid });
  }
  async function refreshBudget(uid) {
    const generation = loadGeneration;
    if (budgetRefresh?.generation === generation) return;
    const pending = budgetRefresh = {generation};
    try {
      const user = window.auth?.currentUser;
      if (!user || uid !== user.uid || !canUse()) return;
      const data = await App.withRequestDeadline(async signal => {
        const token = await user.getIdToken();
        if (user !== window.auth?.currentUser || generation !== loadGeneration || signal.aborted) throw new Error('Account changed');
        const response = await fetch('/agent/budget', { headers: { Authorization: `Bearer ${token}` }, signal });
        if (!response.ok) throw new Error('Allowance unavailable');
        return response.json();
      });
      if (user === window.auth?.currentUser && generation === loadGeneration) receiveBudget(data.token_budget, uid);
    } catch (_) {
      // A stale figure may be asked for again on the next focus.
      budgetSeenAt = 0;
      if (generation === loadGeneration && catalog) App.tokenBudget?.markStale?.();
    } finally { if (budgetRefresh === pending) budgetRefresh = null; }
  }
  function renderControls(agent) {
    const uid = canUse() ? window.auth.currentUser.uid : "";
    if (uid !== catalogOwner || catalogUser !== window.auth?.currentUser || catalogAuthGeneration !== App.authState?.generation) {
      catalogOwner = uid;
      catalogUser = window.auth?.currentUser;
      catalogAuthGeneration = App.authState?.generation;
      catalog = null;
      catalogStatus = "idle";
      loadGeneration++;
      selections.clear();
    }
    const host = document.getElementById("agentModelControls");
    const select = document.getElementById("agentModelDropdown");
    const effort = document.getElementById("agentReasoningEffort");
    if (host) host.hidden = !agent;
    App.sidebarQuota?.sync();
    if (!agent || !select || !effort) {
      // Outside Agent the comparison chip is the Consensus/Compare chip again.
      App.linkModelPicker?.(select, null);
      if (select) App.collapseExpandedModelPicker?.(select);
      if (effort) App.collapseExpandedModelPicker?.(effort);
      return;
    }
    if (canUse() && catalogStatus === "idle") loadModels();
    const ready = catalogStatus === "ready" && canUse();
    const running = registry.isExecuting(registry.visible()?.runId);
    const current = selection();
    const previous = preferredSelection() || {};
    if (ready && !running && (previous.model_id !== current.model_id || previous.reasoning_effort !== current.reasoning_effort)) {
      // Repair the next-message preference once; historical settings stay frozen.
      rememberSelection(current);
      if (previous.model_id && previous.model_id !== current.model_id) {
        const label = catalog.models.find(item => item.id === current.model_id)?.label;
        App.showPopup?.(`Previous model unavailable. Selected ${label} for your next message.`);
      }
    }
    const options = ready ? catalog.models : [{ id: "", label: catalogStatus === "failed" ? "Models unavailable" : "Loading models…" }];
    const signature = JSON.stringify([options, options.map(locked)]);
    if (select.dataset.options !== signature) {
      const groups = new Map();
      const grouped = options.some(model => model.provider);
      const nodes = options.map(model => {
        const option = document.createElement("option");
        option.value = model.id;
        option.textContent = model.label;
        option.dataset.modelLabel = model.label;
        option.disabled = model.available === false || locked(model);
        if (model.premium) option.dataset.modelBadge = "Pro";
        // The default chat model is free for every tier (agent_model_options).
        else if (model.early_access) option.dataset.modelBadge = "Early access";
        if (model.unavailable_reason) option.dataset.description = model.unavailable_reason;
        if (grouped) {
          const key = model.provider || 'other';
          if (!groups.has(key)) {
            const group = document.createElement('optgroup');
            group.label = model.provider_label || 'Other models';
            group.dataset.modelGroup = key;
            groups.set(key, group);
          }
          groups.get(key).append(option);
        }
        return option;
      });
      const order = (App.modelPrefs || []).map(pref => pref.provider);
      const rank = key => order.includes(key) ? order.indexOf(key) : order.length;
      select.replaceChildren(...(grouped ? [...groups.values()].sort((a, b) =>
        rank(a.dataset.modelGroup) - rank(b.dataset.modelGroup) || a.label.localeCompare(b.label)) : nodes));
      select.dataset.options = signature;
    }
    select.value = ready ? current.model_id || catalog.default_model_id : "";
    select.disabled = !ready || running || !catalog.models.some(selectable);
    const model = catalog?.models.find(item => item.id === select.value);
    const efforts = model?.reasoning_efforts || ["default"];
    const effortSignature = JSON.stringify([model?.id, efforts]);
    if (effort.dataset.options !== effortSignature) {
      effort.replaceChildren(...efforts.map(value => {
        const option = document.createElement("option");
        option.value = value;
        const [label, description] = effortCopy[value] || [value, "Reasoning effort"];
        option.textContent = label;
        option.dataset.modelLabel = label;
        option.dataset.description = description;
        return option;
      }));
      effort.dataset.options = effortSignature;
    }
    effort.value = efforts.includes(current.reasoning_effort) ? current.reasoning_effort : "default";
    effort.disabled = !ready || running || efforts.length < 2;
    effort.dataset.available = String(ready && model?.reasoning_available);
    effort.parentElement.hidden = true;
    document.getElementById("agentModelsRetry")?.toggleAttribute("hidden", catalogStatus !== "failed");
    App.initCustomModelPicker?.(select, { grouped: true, secondarySelect: effort, secondaryLabel: 'Reasoning' });
    // One chip, one menu: the chat model above, the models it is compared
    // with below (model-picker.js, linked pickers). The comparison chip of
    // Consensus/Compare steps back while linked.
    const comparison = document.getElementById("consensusModelDropdown");
    App.linkModelPicker?.(select, comparison, { ownLabel: "Agent", companionLabel: "Compare with", ariaLabel: "Agent and comparison models" });
    // A locked chat model (loading, a message running) closes only its own
    // levels; the comparison models stay open to change for the next message.
    if (select.disabled) App.collapseExpandedModelPicker?.(select, { ownLevelsOnly: true });
    if (effort.disabled || effort.parentElement.hidden) App.collapseExpandedModelPicker?.(effort);
    window.syncCustomModelPickers?.();
  }
  function changeSelection() {
    const select = document.getElementById("agentModelDropdown");
    const effort = document.getElementById("agentReasoningEffort");
    const model = catalog?.models.find(item => item.id === select?.value);
    if (!selectable(model) || !canUse()) return;
    const value = { model_id: model.id, reasoning_effort: model.reasoning_efforts.includes(effort.value) ? effort.value : "default" };
    rememberSelection(value);
    render();
  }
  function activityHost(key) {
    const host = document.getElementById("agentAnswerActivity");
    if (host && host.dataset.turn !== key) {
      App.agentActivity?.dispose(host);
      host.replaceChildren();
      delete host._agentActivity;
      // A new turn starts its light path from the beginning.
      host.classList.remove("has-light-progress");
      host.style.removeProperty("--light-p");
      host.dataset.turn = key;
    }
    return host;
  }

  function canUse() {
    const access = App.agentAccess;
    return Boolean(window.auth?.currentUser?.uid && access?.uid === window.auth.currentUser.uid && access.allowed);
  }
  // The open chat's family. Agent chats and Consensus chats are separate on
  // the server, so an open chat keeps its family; null means a new chat.
  function chatFamily() {
    const context = registry.visible();
    if (context) return context.config.executionMode === "agent" ? "agent" : "consensus";
    const basis = registry.getSelectedConversationBasis({ includeHistory: false });
    if (basis) return basis.executionMode === "agent" ? "agent" : "consensus";
    return null;
  }
  // A signed-in account whose Agent access is still loading. A stored Agent
  // choice must not silently send as Consensus in that moment.
  function accessPending() {
    const uid = window.auth?.currentUser?.uid;
    return Boolean(uid && App.agentAccess?.uid !== uid);
  }
  function modeState() {
    return { family: chatFamily(), canUse: canUse(), pending: accessPending() };
  }
  function selectedMode() {
    return (App.runMode?.effective?.() === "agent") ? "agent" : (chatFamily() || "consensus");
  }
  function shellInputs() {
    const context = registry.visible();
    const basis = registry.getSelectedConversationBasis({ includeHistory: false });
    const picked = catalogStatus === 'ready' ? selection() : null;
    return JSON.stringify([selectedMode(), App.runMode?.preference?.(), canUse(), window.auth?.currentUser?.uid || '', App.authState?.generation,
      catalogStatus, catalogOwner, loadGeneration, catalog?.models?.length, picked?.model_id, picked?.reasoning_effort,
      context?.runId, context?.status, registry.isExecuting(context?.runId),
      context?.metadata.recovering, context?.metadata.recoveryState, context?.metadata.recoverable, context?.metadata.requestSent,
      basis && [basis.key, basis.chatId, basis.turnId, basis.bookmarkId, basis.continuationUnavailable,
        basis.consensus?.length, basis.currentTurn?.id, basis.currentTurn?.status, basis.currentTurn?.agent_review?.status,
        basis.currentTurn?.completed_at]]);
  }
  // Composer controls, mode chrome and a saved (non-run) projection. Without
  // `force` it returns at once when nothing it shows has changed, so the
  // registry listener and the run projector can call it on every update.
  function renderShell(force = false) {
    App.agentPreferences?.sync?.();
    const visibleRun = registry.visible()?.runId || null;
    if (visibleRun !== framedRunId) { framedRunId = visibleRun; viewEpoch++; frameKey = ''; }
    const signature = shellInputs();
    if (!force && signature === shellSignature) return false;
    shellSignature = signature;
    renderShellNow();
    return true;
  }
  function render() { renderShell(true); }
  // The allowance refresh only runs while Agent mode is on screen. Runs in
  // this tab report their own spending, so the poll only catches other tabs,
  // devices and the daily reset: every 5 minutes (each poll reads the token
  // account in Firestore; 60 s cost ~300 reads an hour per open tab).
  function syncBudgetPolling(agent) {
    if (agent && canUse() && !budgetTimer) budgetTimer = setInterval(refreshVisibleBudget, 300000);
    else if ((!agent || !canUse()) && budgetTimer) { clearInterval(budgetTimer); budgetTimer = null; }
  }
  function renderShellNow() {
    if (demoView && (registry.visible() || document.body.classList.contains("is-hero"))) demoView = false;
    // However the demo ends, its model icons and panel go with it.
    if (!demoView) App.agentDelegation?.demo?.(null);
    const agent = selectedMode() === "agent";
    const comparisonPicker = document.getElementById("consensusModelDropdown");
    if (comparisonPicker) {
      comparisonPicker.dataset.comparisonOnly = String(agent);
      comparisonPicker.setAttribute("aria-label", agent ? "Comparison models" : "Models and consensus engine");
      // Agent shows one chip: the comparison models live in the Agent menu.
      const chip = comparisonPicker.closest(".consensus-model");
      if (chip) chip.hidden = agent;
    }
    renderControls(agent);
    const modeChanged = document.body.classList.contains("single-agent-active") !== (agent || demoView);
    document.body.classList.toggle("single-agent-active", agent || demoView);
    document.body.classList.toggle("agent-demo-active", demoView);
    // First-paint hint for app-bootstrap.js, written once access is known.
    const authState = window.__consensioAuthState;
    const accessKnown = Boolean(App.agentAccess?.uid && App.agentAccess.uid === window.auth?.currentUser?.uid);
    if (accessKnown) { try { localStorage.setItem("agentShellExpected", agent ? "1" : "0"); } catch (_) {} }
    if (agent || accessKnown || (authState?.known && !authState.uid)) document.documentElement.classList.remove("agent-shell-expected");
    App.renderComposerMode?.();
    if (modeChanged) requestAnimationFrame(() => App.resizeQuestionInput?.());
    // Only the label follows the mode; the icon and the switch's thumb stay.
    const chatTabLabel = document.querySelector("#viewSwitchConsensus > span");
    if (chatTabLabel) chatTabLabel.textContent = agent ? "Chat" : "Consensus";
    const greeting = document.querySelector(".hero-greeting");
    const newChat = document.getElementById("newRunButton");
    if (newChat) {
      const text = newChat.querySelector("span");
      if (text) text.textContent = agent ? "New chat" : "New comparison";
      newChat.title = agent ? "Start a new chat" : "Start a new comparison";
    }
    if (greeting) {
      if (!greeting.dataset.consensusGreeting) greeting.dataset.consensusGreeting = greeting.textContent;
      greeting.textContent = agent ? "What can I help you with?" : greeting.dataset.consensusGreeting;
    }
    const panel = document.getElementById("agentAnswer");
    const context = registry.visible();
    const basis = registry.getSelectedConversationBasis({ includeHistory: false });
    if (!agent || !context) {
      const history = document.getElementById("threadHistory");
      if (history) delete history.dataset.agentHistory;
    }
    const recover = document.getElementById("agentRecover");
    if (recover) {
      recover.hidden = !agent || !["failed", "canceled"].includes(context?.status) || !context?.metadata.requestSent || context.metadata.recoverable === false;
      recover.disabled = Boolean(context?.metadata.recovering);
      recover.textContent = context?.metadata.recovering ? 'Checking saved answer…'
        : context?.metadata.recoveryState === 'running' ? 'Check run status'
          : context?.metadata.recoveryState === 'saved' ? 'Recover saved answer' : 'Check saved answer';
    }
    if (panel) panel.hidden = demoView ? false : !agent || (!context && !basis);
    if (panel?.hidden) activityHost('');
    if (demoView) return;
    // With the Google sheet (Package A) this only re-projects cached state; the
    // connections list loads when the Google entry is first opened.
    App.agentGoogle?.refreshControls?.();
    if (!agent || (!context && !basis)) { App.agentWorkspace?.refresh(null); App.agentGoogle?.refreshActions?.(null); }
    syncBudgetPolling(agent);
    if (agent && !context && basis) {
      App.agentWorkspace?.refresh(basis.chatId);
      App.agentGoogle?.refreshActions?.(basis.chatId);
      const failure = basis.currentTurn?.agent_failure;
      setAnswerChecking(document.getElementById("agentAnswerBody"), false, { fade: false });
      renderAnswer(basis.consensus || "", failure?.error ? failureNotice(failure, basis.currentTurn?.agent_review, basis.consensus || "")
        : (basis.currentTurn?.status === 'failed' ? 'This response did not finish successfully.' : ''));
      App.agentActivity?.renderTurn(activityHost(`${basis.chatId}:${basis.turnId}`), basis.currentTurn);
      App.agentReview?.render(document.getElementById("agentAnswerBody"), basis.currentTurn?.agent_review,
        { sources: basis.currentTurn?.sources, events: basis.currentTurn?.agent_activity, key: basis.turnId, question: basis.question });
      App.agentMemory?.render(document.getElementById('agentAnswerBody'), {
        key: `${basis.chatId}:${basis.turnId}`, changes: basis.currentTurn?.agent_memory,
      });
      App.agentDelegation?.project(basis.currentTurn?.agent_settings?.policy?.delegation ? {
        chatId: basis.chatId, turnId: basis.turnId || basis.currentTurn?.id,
        usage: basis.currentTurn?.agent_usage, running: basis.currentTurn?.status === "pending" } : null);
    }
    if (!agent || (!context && !basis)) App.agentDelegation?.project(null);
    window.updateQuestionInputAccess?.();
    syncPendingReview();
  }
  // While a run streams, only the growing last Markdown block is parsed again
  // (markdown-stream.js). The final text is rendered once in full, like a
  // saved answer, so review markers and cross-block Markdown are exact.
  function renderAnswer(text, error, { streaming = false } = {}) {
    const body = document.getElementById("agentAnswerBody");
    const mode = streaming && window.renderMarkdownStream ? 'stream' : 'full';
    // The run ends with the same text the review already rendered in full
    // with its claim marks: switching to 'full' must keep that DOM. Rendering
    // it again dropped every mark and rebuilt it, a visible flicker.
    if (body && mode === 'full' && body.dataset.markdown === text && body.dataset.renderMode === 'stream'
        && body._markSignature && body.querySelector('.cx-claim')) {
      body.dataset.renderMode = mode;
      window.resetMarkdownStream?.(body);
    }
    if (body && (body.dataset.markdown !== text || body.dataset.renderMode !== mode)) {
      const entering = !body.dataset.markdown?.trim() && Boolean(text.trim());
      body.dataset.markdown = text;
      body.dataset.renderMode = mode;
      if (mode === 'stream') window.renderMarkdownStream(body, text);
      else {
        window.resetMarkdownStream?.(body);
        window.injectMarkdown?.(body, text, []);
      }
      // A fresh DOM has no claim marks; the review renderer re-applies them.
      body._agentRenderSerial = (body._agentRenderSerial || 0) + 1;
      // Animate the start of an answer once, never each streamed text chunk.
      if (!text.trim()) body._agentReveal?.cancel();
      else if (entering) body._agentReveal = App.agentActivity?.reveal(body);
    }
    renderError(typeof error === 'string' ? { text: error } : error);
  }
  // While the judges check the fixed answer a quiet sheen passes over it, so
  // the reader sees below the fold that something is still happening. It
  // fades out instead of switching off when the marks arrive.
  function setAnswerChecking(body, checking, { fade = true } = {}) {
    if (!body || body.classList.contains('is-answer-checking') === checking) return;
    body.classList.toggle('is-answer-checking', checking);
    clearTimeout(body._answerCheckFade);
    body.classList.toggle('is-answer-check-done', !checking && fade);
    if (!checking && fade) body._answerCheckFade = setTimeout(() => body.classList.remove('is-answer-check-done'), 450);
  }
  function renderError(error) {
    const errorEl = document.getElementById("agentAnswerError");
    const actionsEl = document.getElementById('agentAnswerErrorActions');
    const text = error?.text || '';
    if (errorEl) {
      if (errorEl.textContent !== text) errorEl.textContent = text;
      errorEl.hidden = !text;
    }
    if (!actionsEl) return;
    const actions = text ? error.actions || [] : [];
    const signature = JSON.stringify(actions);
    if (actionsEl.dataset.signature !== signature) {
      actionsEl.dataset.signature = signature;
      actionsEl.replaceChildren(...actions.map(([action, label]) => {
        const button = document.createElement('button');
        button.type = 'button'; button.dataset.action = action; button.textContent = label;
        return button;
      }));
    }
    actionsEl.hidden = !actions.length;
  }
  // Local reset time for the UTC-day Agent allowance, e.g. "02:00".
  function resetTime() {
    const next = new Date(); next.setUTCHours(24, 0, 0, 0);
    return next.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }
  function compactTokens(value) {
    if (!Number.isFinite(value)) return '';
    return value >= 10000 ? `${Math.round(value / 1000)}k` : value >= 1000 ? `${(value / 1000).toFixed(1).replace(/\.0$/, '')}k`
      : value.toLocaleString();
  }
  // Budget refusals carry a stable code; show a plain next step, not ledger terms.
  function failureNotice(failure, review, text, { retry = true } = {}) {
    const code = failure?.code || failure?.error_code;
    if (code === 'agent_token_reservation') {
      const needs = compactTokens(failure.required_tokens), left = compactTokens(failure.available_tokens);
      return { text: `Not enough Agent tokens left for this step${needs ? ` (needs about ${needs}, ${left || 0} left)` : ''}. `
        + `Try a smaller model or fewer comparison models, or wait for the reset at ${resetTime()}.`,
      actions: [['choose-model', 'Try a smaller model'], ['compare', 'Choose models']] };
    }
    if (code === 'agent_tokens_exhausted') return { text: `You've used today's Agent tokens. They reset at ${resetTime()}.` };
    const note = App.agentReview?.failureNote?.(failure, review, text);
    // Any other stop (provider busy, timeout, lost connection) can be sent
    // again as it was; a busy model can also be swapped first.
    const actions = retry ? [['retry', 'Retry']] : [];
    if (code === 'provider_rate_limited' || code === 'provider_unavailable') actions.push(['choose-model', 'Choose another model']);
    return { text: note ?? (failure?.error || failure?.message || ''), actions };
  }
  // A brand-new chat has no files or actions until the run reports resources
  // or finishes; its first lists need no request.
  function knownEmptyChat(context) {
    return !context.basis && registry.isExecuting(context.runId) && !context.metadata.resourcesSeen
      && !(context.metadata.fileIds || []).length;
  }
  // Everything that describes which run is on screen, not how far it got.
  // It changes once per run/view, so a streamed chunk never repeats it.
  function projectFrame(context) {
    const knownEmpty = knownEmptyChat(context);
    const key = JSON.stringify([context.runId, viewEpoch, context.metadata.chatId, context.metadata.agentTurnId,
      (context.attachmentMeta || []).length, (context.metadata.fileIds || []).length, knownEmpty, context.historyTurns.length]);
    if (frameKey === key) return false;
    frameKey = key;
    window.exitHeroMode?.();
    document.body.classList.remove("direct-comparison-active", "thread-message-pending");
    App.consensusPipeline?.dismiss?.();
    window.projectAgentModeRun?.(null);
    App.setAppTitle?.(context.question);
    App.setThreadQuestion?.(context.question);
    App.setThreadQuestionAttachments?.(context.attachmentMeta || []);
    // A new chat's lists are known to be empty until the run reports
    // resources, its own uploads refresh the workspace, or it finishes; no
    // GET is needed for them. Otherwise both re-project their cached lists.
    const listChat = knownEmpty ? null : context.metadata.chatId;
    App.agentWorkspace?.refresh(listChat);
    App.agentGoogle?.refreshActions?.(listChat);
    App.state?.set?.("lastQuestion", context.question, "run");
    App.state?.set?.("lastShareResultId", null, "share");
    App.state?.set?.("consensusCitationMeta", null, "consensus");
    App.state?.set?.("currentEvidenceSources", [], "evidence");
    window.lastConsensusBookmarkPayload = null;
    const history = document.getElementById("threadHistory");
    // Agent history is fixed for a run after its initial previous-turn append.
    // Avoid serializing and duplicating all saved reasoning in a DOM attribute
    // on every streamed activity update.
    const signature = `${context.runId}:${context.historyTurns.length}`;
    if (history && history.dataset.agentHistory !== signature) {
      App.followup?.renderStoredTurns?.(context.historyTurns);
      history.dataset.agentHistory = signature;
    }
    return true;
  }
  function project(context) {
    renderShell();
    const framed = projectFrame(context);
    const state = context.consensus;
    const running = registry.isExecuting(context.runId);
    const failure = state.error || state.completedTurn?.agent_failure;
    // A message refused before it started is back in the composer instead.
    const retry = !running && context.metadata.requestSent && !context.metadata.restoreDraft;
    renderAnswer(state.text || state.streamText || "", failure ? failureNotice(failure,
      state.completedTurn?.agent_review || context.metadata.agentReview, running ? "" : state.text || state.streamText || "", { retry }) : "",
      { streaming: running && !state.text });
    App.agentActivity?.render(activityHost(context.runId), {
      elapsedMs: App.agentActivity.savedDuration(state.completedTurn)
        ?? Math.max(0, (context.finishedAt || Date.now()) - context.startedAt),
      events: state.completedTurn?.agent_activity || context.metadata.agentActivity || [],
      usage: state.completedTurn?.agent_usage || context.metadata.agentUsage, running: registry.isExecuting(context.runId),
      responding: Boolean(state.text || state.streamText),
      status: context.status, truncated: state.completedTurn?.agent_reasoning_truncated,
      finishReason: state.completedTurn?.agent_finish_reason,
      review: state.completedTurn?.agent_review || context.metadata.agentReview,
      answerText: state.text || state.streamText || '',
      settings: state.completedTurn?.agent_settings || context.metadata.agentSettings,
    });
    // Evidence links and Copy belong to a finished answer. While the run
    // streams they are only cleared once, when this run takes over the view.
    // A checked answer shows its marks at once, even while a source check
    // still runs: waiting for the end of the run made them appear late.
    const answerBody = document.getElementById("agentAnswerBody");
    const liveReview = context.metadata.agentReview;
    const fixed = running && Boolean((state.text || state.streamText || '').trim()) && Boolean(liveReview?.versions?.length);
    const checking = fixed && ['required', 'running'].includes(liveReview.status);
    const checked = fixed && ['succeeded', 'partial'].includes(liveReview.status);
    setAnswerChecking(answerBody, checking);
    if (checking) context.metadata.revealMarks = true;
    if (!running || framed || checked) {
      const live = running && !checked;
      App.agentReview?.render(answerBody, live ? null : state.completedTurn?.agent_review || liveReview,
        { sources: state.completedTurn?.sources, events: live ? [] : state.completedTurn?.agent_activity || context.metadata.agentActivity,
          key: state.completedTurn?.id || context.runId, question: context.question, reveal: Boolean(context.metadata.revealMarks) });
    }
    // Memory changes appear as soon as Agent made them, not only at the end.
    App.agentMemory?.render(answerBody, { key: context.runId, running,
      changes: state.completedTurn?.agent_memory || context.metadata.agentMemory || [] });
    App.syncSendButtonRunning?.();
    if (!running) syncPendingReview();
    App.agentDelegation?.project(context.metadata.delegation || state.completedTurn?.agent_settings?.policy?.delegation ? { chatId: context.metadata.chatId,
      turnId: state.completedTurn?.id || context.metadata.agentTurnId,
      usage: state.completedTurn?.agent_usage || context.metadata.agentUsage, running: registry.isExecuting(context.runId) } : null);
  }
  function apiError(data) {
    const error = data?.error || data?.detail;
    return typeof error === "string" ? error : error?.error || error?.message || "The agent request failed.";
  }
  function acceptAnswer(context, data) {
    const turn = { ...data.turn, turn_id: data.turn_id };
    context.metadata.resourcesSeen = true;
    App.agentWorkspace?.refresh(data.chat_id, true);
    App.agentGoogle?.noteGoogleData?.(data.chat_id, data.google_data === true, data.google_consent === true);
    App.agentGoogle?.refreshActions?.(data.chat_id, true);
    // A final/recovery snapshot may omit earlier progress. Keep confirmed live
    // entries, while the saved snapshot remains authoritative for matching IDs.
    const activity = new Map((context.metadata.agentActivity || []).map(item => [item.id, { ...item }]));
    for (const item of turn.agent_activity || []) activity.set(item.id, { ...activity.get(item.id), ...item });
    if (activity.size) turn.agent_activity = [...activity.values()];
    context.consensus.text = context.consensus.streamText = data.response;
    context.consensus.status = "complete";
    context.consensus.completedTurn = turn;
    context.consensus.error = turn.status === "failed" ? { ...turn.agent_failure, message: turn.agent_failure?.error || "This saved answer is incomplete. The response did not finish successfully." } : null;
    context.bookmark.status = "succeeded";
    context.persistence.consensusWrite = true;
    context.metadata.recoverable = false;
    context.phase = "done";
    const conversation = { runId: context.runId, auth: context.auth, bookmarkId: context.bookmark.id,
      chatId: data.chat_id, turnId: data.turn_id };
    window.acceptPersistedConsensusBookmark?.(data.bookmark_meta, conversation);
    if (registry.isExecuting(context.runId)) registry.setStatus(context.runId, 'succeeded');
    else {
      // Only an explicit server-confirmed recovery may replace terminal state.
      registry.update(context.runId, run => { run.status = 'succeeded'; run.error = null; run.finishedAt = Date.now(); });
    }
    registry.setCompletedBasis(context.runId, {
      ...conversation, executionMode: "agent", question: context.question, consensus: data.response,
      currentTurn: turn, historyTurns: context.historyTurns, title: context.bookmark.title,
    });
  }
  // Agent has no Watch button: a finished answer may offer to keep itself
  // current (watch.js owns the card, the counter and "dismissed"). Only a
  // first message qualifies, because a watch re-asks the bare question, and
  // only one built on sources, because those are what can change.
  function offerWatch(context) {
    if (!registry.isVisible(context.runId) || !registry.isAuthCurrent(context)) return;
    const turn = context.consensus.completedTurn;
    App.watch?.showFeatureNudge?.({
      eligible: turn?.status !== "failed" && context.historyTurns.length === 0
        && Array.isArray(turn?.sources) && turn.sources.length > 0,
      question: context.question,
      anchor: document.getElementById("agentWatchAnchor"),
    });
  }
  async function recoverAnswer(context) {
    if (!context || !registry.isAuthCurrent(context) || !['failed', 'canceled'].includes(context.status)
        || !context.metadata.requestSent || context.metadata.recoverable === false || context.metadata.recovering) return;
    let action;
    try {
      action = registry.beginAction({ key: 'agent-recovery', ownerRunId: context.runId, bookmarkId: context.bookmark.id });
      context.metadata.recovering = true;
      registry.show(context.runId);
      const settings = context.config.agentSettings;
      const result = await App.withRequestDeadline(async signal => {
        const token = await window.auth.currentUser.getIdToken();
        if (!registry.isAuthCurrent(context) || signal.aborted) throw new DOMException('Account changed', 'AbortError');
        return window.streamSSERequest('/agent', {
          chat_id: context.metadata.chatId, question: context.question, client_request_id: context.requestIdentity,
          bookmark_id: context.bookmark.id, recover_only: true, model_id: settings.model_id,
          reasoning_effort: settings.reasoning_effort || 'default',
          comparison_models: Object.keys(context.config.comparisonModels || {}).length ? context.config.comparisonModels : null,
          check_sources: context.config.checkSources === true,
          agent_preferences: context.config.agentPreferences || { depth: "auto", quorum: "balanced", autonomy: "guided" },
        file_ids: context.metadata.fileIds || [],
        google_selection: context.config.googleSelection || null,
        google_data_consent: context.config.googleDataConsent === true,
        }, signal, {}, { headers: { Authorization: `Bearer ${token}` } });
      }, { signal: action.controller.signal });
      if (!registry.isAuthCurrent(context) || action.controller.signal.aborted) return;
      receiveBudget(result.data?.token_budget, context.auth.uid);
      const recoverable = result.data?.recoverable ?? result.data?.detail?.recoverable;
      if (typeof recoverable === 'boolean') context.metadata.recoverable = recoverable;
      context.metadata.recoveryState = result.data?.recovery_state;
      if (!result.ok || !result.data?.turn) throw new Error(apiError(result.data));
      acceptAnswer(context, result.data);
    } catch (error) {
      if (action?.controller.signal.aborted || !registry.isAuthCurrent(context)) return;
      App.showPopup?.(error.message);
    } finally {
      context.metadata.recovering = false;
      if (action) registry.finishAction(action.actionId);
      if (registry.isAuthCurrent(context)) registry.renderVisible();
    }
  }
  function comparisonSelection() {
    return Object.fromEntries((App.modelPrefs || [])
      .filter(pref => document.getElementById(pref.checkId)?.checked)
      .map(pref => [pref.provider, document.getElementById(pref.selectId)?.value]));
  }
  function hasValidComparisonSelection(value = comparisonSelection()) {
    const models = Object.values(value);
    const limit = Number(App.maxRunFamilies) > 0 ? Number(App.maxRunFamilies) : 6;
    return models.length >= 2 && models.length <= limit && models.every(id => typeof id === 'string' && id.trim());
  }
  function sendBlocker() {
    if (!canUse()) return { message: 'Sign in to use Agent.' };
    if (catalogStatus === 'failed') return { message: 'Chat models could not be loaded. Retry to continue.' };
    if (catalogStatus !== 'ready') return { message: 'Loading chat models… You can already write your message.', loading: true };
    if (!catalog.models.some(model => model.available !== false)) {
      return { message: 'No chat models are available right now. Try reloading the model list.', action: 'reload', label: 'Reload models' };
    }
    if (!hasValidComparisonSelection()) {
      const limit = Number(App.maxRunFamilies) > 0 ? Number(App.maxRunFamilies) : 6;
      return { message: `Select between two and ${limit} comparison models to send your message.`, action: 'compare', label: 'Choose models' };
    }
    const basis = registry.getSelectedConversationBasis({ includeHistory: false });
    if (basis && (!basis.chatId || basis.continuationUnavailable)) return { message: 'Reopen this saved chat before continuing.' };
    // Google data needs the chat's consent (agent-google.js owns the rules).
    try {
      const google = App.agentGoogle?.blocker?.();
      if (google?.message) return google;
    } catch (_) { /* A Google state error never blocks a non-Google message. */ }
    return null;
  }
  // "2 items need your review" after a run left external writes waiting.
  function pendingReviewCount() {
    const context = registry.visible();
    const basis = registry.getSelectedConversationBasis({ includeHistory: false });
    const chatId = context?.metadata.chatId || basis?.chatId;
    if (!chatId || selectedMode() !== 'agent' || (context && registry.isExecuting(context.runId))) return 0;
    const count = Number(App.agentGoogle?.pendingCount?.(chatId));
    return Number.isInteger(count) && count > 0 ? count : 0;
  }
  let pendingTitle = 0;
  function syncPendingReview() {
    const count = pendingReviewCount();
    const notice = document.getElementById('agentReviewNotice');
    if (notice) {
      notice.hidden = !count;
      const text = count ? `${count} ${count === 1 ? 'item needs' : 'items need'} your review` : '';
      const message = document.getElementById('agentReviewMessage');
      if (message && message.textContent !== text) message.textContent = text;
    }
    // Bookmark dot and tab title follow the conversation on screen.
    const context = registry.visible();
    const basis = registry.getSelectedConversationBasis({ includeHistory: false });
    const bookmarkId = context?.bookmark.id || basis?.bookmarkId;
    document.querySelectorAll('.bookmark.needs-review').forEach(row => {
      if (count && row.dataset.id === bookmarkId) return;
      row.classList.remove('needs-review');
      if (row.title === 'Needs review') row.removeAttribute('title');
    });
    if (count && bookmarkId) {
      document.querySelectorAll(`.bookmark[data-id="${cssId(bookmarkId)}"]`).forEach(row => {
        row.classList.add('needs-review');
        if (!row.title) row.title = 'Needs review';
      });
    }
    const title = document.title.replace(/^\(\d+\) /, '');
    if (count !== pendingTitle || /^\(\d+\) /.test(document.title) !== Boolean(count)) {
      document.title = count ? `(${count}) ${title}` : title;
      pendingTitle = count;
    }
  }
  function revealPendingReview() {
    const card = document.querySelector('.agent-action-card[data-status="pending"]') || document.querySelector('.agent-action-card');
    if (!card) return false;
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    card.scrollIntoView({ block: 'start', behavior: reduce ? 'auto' : 'smooth' });
    const target = card.querySelector('input[type=checkbox]:not(:disabled), button:not(:disabled)') || card;
    if (target === card && !card.hasAttribute('tabindex')) card.tabIndex = -1;
    target.focus({ preventScroll: true });
    return true;
  }
  // Shortcuts named by a composer notice or an answer error. Google actions
  // belong to agent-google.js (Package A) and stay optional.
  function runNoticeAction(action) {
    if (action === 'compare') App.openModelPicker?.(document.getElementById('consensusModelDropdown'));
    else if (action === 'choose-model') {
      App.composer?.expand?.();
      App.openModelPicker?.(document.getElementById('agentModelDropdown'), { level: 'models' });
    } else if (action === 'google-consent') App.agentGoogle?.consent?.(true);
    else if (action === 'google-open') App.agentGoogle?.open?.();
    else if (action === 'reload') { catalogStatus = 'idle'; render(); }
    else if (action === 'retry') retryFailed();
    window.updateQuestionInputAccess?.();
  }
  // Retry sends the failed message again, as a new turn in the same chat,
  // with its files and the model now selected (so a busy model can be swapped).
  function retryFailed() {
    const context = registry.visible();
    if (context?.config.executionMode === 'agent' && ['failed', 'canceled'].includes(context.status)) {
      return send(null, { retry: {
        runId: context.runId, question: context.question, basis: context.basis,
        chatId: context.metadata.requestSent ? context.metadata.chatId : null,
        bookmarkId: context.metadata.requestSent ? context.bookmark.id : null,
        fileIds: context.metadata.fileIds || [], attachmentMeta: context.attachmentMeta || [],
        googleSelection: context.config.googleSelection || null, googleDataConsent: context.config.googleDataConsent === true,
      } });
    }
    // A saved failed turn (reopened chat, or a run that ended with a saved
    // failure) is retried as the next message of that chat.
    if (context && registry.isExecuting(context.runId)) return;
    const basis = registry.getSelectedConversationBasis();
    const turn = basis?.currentTurn;
    if (!basis?.chatId || turn?.status !== 'failed') return;
    return send(null, { retry: {
      question: basis.question, basis, chatId: basis.chatId, bookmarkId: basis.bookmarkId,
      fileIds: turn.agent_settings?.file_ids || [], attachmentMeta: turn.attachments || [],
      googleSelection: null, googleDataConsent: App.agentGoogle?.consent?.() === true,
    } });
  }
  // No byte for 45 s does not prove that a run died: some networks (company
  // proxies, virus scanners) hold an event stream back until it ends. Ask the
  // server instead. A saved answer or failure ends the wait; a run that is
  // still going keeps it open; twice no answer at all gives up.
  async function checkStalledRun(context, body, headers, stall) {
    if (!registry.isAuthCurrent(context)) return undefined;
    let result = null;
    try {
      result = await App.withRequestDeadline(signal => window.streamSSERequest('/agent', { ...body, recover_only: true },
        signal, {}, { headers }), { timeoutMs: 15000 });
    } catch (_) { /* counted below */ }
    if (result?.data?.turn) return result;
    if (result?.data?.recovery_state === 'running') { stall.misses = 0; return undefined; }
    if (++stall.misses >= 2) throw new Error('The connection is taking too long. Please try again.');
    return undefined;
  }
  function syncComposer() {
    const agent = selectedMode() === 'agent';
    const running = registry.isExecuting(registry.visible()?.runId);
    const blocker = agent && !running ? sendBlocker() : null;
    const notice = document.getElementById('agentComposerNotice');
    const message = document.getElementById('agentComposerMessage');
    const action = document.getElementById('agentComposerAction');
    let quiet = false;
    clearTimeout(loadingNoticeTimer);
    if (blocker?.loading) {
      if (!loadingNoticeSince) loadingNoticeSince = performance.now();
      const wait = LOADING_NOTICE_DELAY_MS - (performance.now() - loadingNoticeSince);
      if (wait > 0) { quiet = true; loadingNoticeTimer = setTimeout(syncComposer, wait); }
    } else loadingNoticeSince = 0;
    if (notice) notice.hidden = !blocker || quiet;
    if (message && message.textContent !== (blocker?.message || '')) message.textContent = blocker?.message || '';
    if (action) {
      action.hidden = !blocker?.action;
      action.textContent = blocker?.label || '';
      action.dataset.action = blocker?.action || '';
    }
    const input = document.getElementById('questionInput');
    if (!input) return;
    const descriptions = new Set((input.getAttribute('aria-describedby') || '').split(/\s+/).filter(Boolean));
    descriptions.delete('agentComposerMessage');
    if (blocker) descriptions.add('agentComposerMessage');
    if (descriptions.size) input.setAttribute('aria-describedby', [...descriptions].join(' '));
    else input.removeAttribute('aria-describedby');
    if (!agent || window.userCanAskQuestions?.() === false) return;
    const basis = registry.getSelectedConversationBasis({ includeHistory: false });
    input.placeholder = running ? 'Write your next message…' : basis?.chatId && !basis.continuationUnavailable
      ? 'Ask a follow-up' : 'Message Agent';
  }
  // Attachments still in the composer are this run's own when an upload
  // failed (agent-workspace keeps the chips and marks the run).
  function ownAttachmentsRemain(context) {
    const pending = window.getAttachmentsPayload?.() || [];
    if (!pending.length) return true;
    if (context.metadata.uploadFailed === true) return true;
    const own = (context.attachmentMeta || []).map(item => `${item.name}:${item.size || 0}`).sort().join('|');
    return own === pending.map(item => `${item.name}:${item.size || 0}`).sort().join('|');
  }
  // A message the server refused before starting leaves no sidebar entry:
  // a new chat's run row disappears, a follow-up's row returns to its saved chat.
  function releaseRunRow(context) {
    context.bookmark.uiReady = true; // run-view.ensureRunRow must not recreate the row
    const row = document.querySelector(`.bookmark.run-entry[data-run-id="${cssId(context.runId)}"]`);
    if (!row) return;
    if (context.basis?.bookmarkId && App.bookmarkUi?.replacePendingBookmarkWithReady) {
      App.bookmarkUi.replacePendingBookmarkWithReady(context.basis.bookmarkMeta?.id ? context.basis.bookmarkMeta
        : { id: context.basis.bookmarkId, title: context.basis.title || context.basis.question }, context.runId);
    } else row.remove();
  }
  function restoreUnsentDraft(context) {
    if ((context.metadata.requestSent && !context.metadata.restoreDraft) || context.metadata.draftRestored || !registry.isAuthCurrent(context)
        || !registry.isVisible(context.runId)) return;
    const input = document.getElementById('questionInput');
    // Never replace a newer draft, quotation, attachment, or another chat's composer.
    if (!input || input.value || App.quote?.text?.() || !ownAttachmentsRemain(context)) return;
    context.metadata.draftRestored = true;
    if (context.basis) registry.selectConversationBasis(context.basis);
    input.value = context.metadata.draftQuestion;
    if (context.metadata.quotedContext) App.quote?.set?.(context.metadata.quotedContext);
    input.dispatchEvent(new Event('input', { bubbles: true }));
    App.composer?.expand?.();
  }
  async function send(recovery = null, { retry = null } = {}) {
    if (recovery) return recoverAnswer(recovery);
    if (!canUse()) { App.showPopup?.("Sign in to use Agent."); return; }
    const input = document.getElementById("questionInput");
    const draft = retry ? retry.question : input?.value || "";
    const question = retry ? String(retry.question || "").trim() : String(App.quote?.compose?.(draft) ?? draft).trim();
    if (!question) return;
    const settings = recovery?.config.agentSettings || {
      ...selection(), reasoning_effort: document.getElementById("agentReasoningEffort")?.value || "default",
    };
    const comparisonModels = comparisonSelection();
    if (!hasValidComparisonSelection(comparisonModels)) {
      App.showPopup?.(`Select between two and ${Number(App.maxRunFamilies) > 0 ? Number(App.maxRunFamilies) : 6} comparison models before sending.`);
      return;
    }
    if (!catalog || catalogStatus !== 'ready' || !catalog.models.some(model => model.id === settings.model_id && model.available !== false)) {
      App.showPopup?.("Choose an available agent model before sending."); return;
    }
    const basis = retry ? retry.basis || null : registry.getSelectedConversationBasis();
    if (basis && (!basis.chatId || basis.continuationUnavailable)) {
      App.showPopup?.("Reopen this saved chat before continuing."); return;
    }
    let context;
    try {
      context = registry.create({
        question, mode: "Agent", basis, followup: Boolean(basis),
        attachments: retry ? [] : window.getAttachmentsPayload?.() || [],
        attachmentMeta: retry ? retry.attachmentMeta : App.attachments?.messageMeta?.() || [],
        requestIdentity: recovery?.requestIdentity,
        bookmarkId: retry?.bookmarkId || basis?.bookmarkId || `b_agent_${crypto.randomUUID().replaceAll("-", "")}`,
        bookmarkTitle: basis?.title || question,
        config: { executionMode: "agent", agentMode: true, autoConsensus: false,
          deepSearch: false, checkSources: App.isSourceCheckEnabled?.() === true, useOwnKeys: false, providers: [], agentSettings: settings, comparisonModels,
          agentPreferences: recovery?.config.agentPreferences || App.agentPreferences?.get?.() || { depth: "auto", quorum: "balanced", autonomy: "guided" },
          googleSelection: retry ? retry.googleSelection : App.agentGoogle?.selection() || null,
          googleDataConsent: retry ? retry.googleDataConsent : App.agentGoogle?.consent() === true },
        metadata: { draftQuestion: draft, quotedContext: retry ? '' : App.quote?.text?.() || '',
          ...(retry ? { fileIds: retry.fileIds } : {}),
          agentActivity: [], agentSettings: { ...settings, label: catalog?.models.find(model => model.id === settings.model_id)?.label } },
        usage: { status: "simulation", key: null },
      });
    } catch (error) { App.showPopup?.(error.message); return; }
    if (retry?.runId) {
      // The new run takes over the failed run's sidebar row.
      const failed = registry.get(retry.runId);
      if (failed) failed.bookmark.uiReady = true;
      document.querySelector(`.bookmark.run-entry[data-run-id="${cssId(retry.runId)}"]`)?.remove();
    }
    if (context.config.googleDataConsent) App.agentGoogle?.resetConsent();
    if (basis?.currentTurn) context.historyTurns.push(basis.currentTurn);
    context.controllers.query = new AbortController();
    const signal = context.controllers.query.signal;
    context.consensus.status = "pending";
    context.cancelHook = () => {
      context.consensus.status = "canceled";
      context.consensus.error = null;
      context.bookmark.status = "canceled";
      if (context.metadata.agentReview) context.metadata.agentReview = { ...context.metadata.agentReview, status: "cancelled" };
      else if (context.basis && registry.visible()?.runId === context.runId) registry.selectConversationBasis(context.basis);
      restoreUnsentDraft(context);
    };
    registry.setStatus(context.runId, "running");
    if (!recovery && !retry) {
      App.clearQuestionDraft?.();
      if (input) { input.value = ""; input.dispatchEvent(new Event("input", { bubbles: true })); }
      App.quote?.clear?.();
    }
    App.composer?.collapse?.({ force: true });
    if (!recovery && !retry) App.revealSentMessage?.();
    let timer, terminalBudget = false;
    try {
      const token = await App.withRequestDeadline(() => window.auth.currentUser.getIdToken(), { signal });
      if (!registry.isAuthCurrent(context) || signal.aborted) return;
      const headers = { Authorization: `Bearer ${token}` };
      let chatId = recovery?.metadata.chatId || retry?.chatId || basis?.chatId;
      if (!chatId) {
        const { response, data } = await App.withRequestDeadline(async requestSignal => {
          const response = await fetch("/chats", {
            method: "POST", headers: { ...headers, "Content-Type": "application/json" }, signal: requestSignal,
            body: JSON.stringify({ title: question.slice(0, 120), execution_mode: "agent" }),
          });
          return { response, data: await response.json() };
        }, { signal });
        if (!response.ok) throw new Error(apiError(data));
        chatId = data.chat.id;
      }
      if (!registry.isAuthCurrent(context) || signal.aborted) return;
      context.metadata.chatId = chatId;
      if (context.attachments.length && !App.agentWorkspace) throw new Error("File uploads are unavailable. Reload and retry.");
      if (!retry) await App.agentWorkspace?.upload(context, headers, signal);
      if (!registry.isAuthCurrent(context) || signal.aborted) return;
      context.metadata.requestSent = true;
      if (!recovery) App.trackAsk?.(context);
      context.phase = "answers";
      context.consensus.status = "streaming";
      registry.update(context.runId, () => {});
      const body = {
        chat_id: chatId, question, client_request_id: context.requestIdentity,
        bookmark_id: context.bookmark.id,
        recover_only: Boolean(recovery),
        model_id: settings.model_id,
        reasoning_effort: settings.reasoning_effort || "default",
        comparison_models: comparisonModels,
        check_sources: context.config.checkSources === true,
        agent_preferences: context.config.agentPreferences || { depth: "auto", quorum: "balanced", autonomy: "guided" },
        file_ids: context.metadata.fileIds || [],
        google_selection: context.config.googleSelection || null,
        google_data_consent: context.config.googleDataConsent === true,
      };
      const stall = { misses: 0 };
      const result = await App.withRequestDeadline((requestSignal, onProgress) => window.streamSSERequest("/agent", body, requestSignal, {
        accepted: { receive(event) {
          if (registry.isAuthCurrent(context) && event.chat_id === context.metadata.chatId) {
            context.metadata.agentTurnId = event.turn_id;
            context.metadata.delegation = true;
          }
        } },
        quota: { receive(event) {
          if (registry.isAuthCurrent(context)) receiveBudget(event.token_budget, context.auth.uid);
        } },
        started: { receive(event) {
          if (registry.isAuthCurrent(context) && event.chat_id === context.metadata.chatId) {
            context.metadata.agentTurnId = event.turn_id;
            context.metadata.delegation = event.delegation === true;
          }
        } },
        delegation: { receive(event) {
          if (!registry.isExecuting(context.runId) || !registry.isAuthCurrent(context)) return;
          App.agentDelegation?.receive(context, event);
          if (!timer) timer = setTimeout(() => { timer = null; registry.update(context.runId, () => {}); }, 100);
        } },
        delegation_progress: { receive(event) {
          if (!registry.isExecuting(context.runId) || !registry.isAuthCurrent(context)) return;
          App.agentDelegation?.receiveProgress(context, event);
        } },
        resources: { receive(event) {
          if (!registry.isExecuting(context.runId) || !registry.isAuthCurrent(context)) return;
          context.metadata.resourcesSeen = true;
          // Refresh only the list the event names; both when it names neither.
          // Each side debounces its own GET per chat (300 ms).
          const keys = event && typeof event === 'object' ? event : {};
          const files = 'documents' in keys || 'files' in keys;
          const actions = 'actions' in keys || 'gmail_evidence' in keys;
          if (files || !actions) App.agentWorkspace?.refresh(context.metadata.chatId, true);
          if (actions || !files) App.agentGoogle?.refreshActions?.(context.metadata.chatId, true);
        } },
        memory: { receive(event) {
          if (!registry.isExecuting(context.runId) || !registry.isAuthCurrent(context)) return;
          context.metadata.agentMemory = App.agentMemory?.receive(context.metadata.agentMemory || [], event) || [];
          registry.update(context.runId, () => {});
        } },
        review: { receive(event) {
          if (!registry.isExecuting(context.runId) || !registry.isAuthCurrent(context)) return;
          context.metadata.agentReview = event.review;
          registry.update(context.runId, () => {});
        } },
        activity: { receive(event) {
          if (!registry.isExecuting(context.runId) || !registry.isAuthCurrent(context)) return;
          App.agentActivity?.receive(context.metadata.agentActivity, event);
          if (event.kind === "status" && event.clear_response) context.consensus.streamText = "";
          if (event.settings) context.metadata.agentSettings = event.settings;
          if (event.kind === "usage") context.metadata.agentUsage = event.usage;
          if (!timer) timer = setTimeout(() => { timer = null; registry.update(context.runId, () => {}); }, 100);
        } },
        delta: { append(text) {
          if (!registry.isExecuting(context.runId) || !registry.isAuthCurrent(context)) return;
          context.consensus.streamText += text;
          if (!timer) timer = setTimeout(() => { timer = null; registry.update(context.runId, () => {}); }, 100);
        } },
      }, { headers, onProgress }), { signal, timeoutMs: 45000, onIdle: () => checkStalledRun(context, body, headers, stall) });
      if (!registry.isAuthCurrent(context) || signal.aborted) return;
      receiveBudget(result.data?.token_budget, context.auth.uid);
      terminalBudget = Boolean(result.data?.token_budget);
      const recoverable = result.data?.recoverable ?? result.data?.detail?.recoverable;
      if (typeof recoverable === 'boolean') context.metadata.recoverable = recoverable;
      context.metadata.recoveryState = result.data?.recovery_state;
      if (result.data?.saved_answer?.turn && result.data.saved_answer.bookmark_meta) {
        // A failed run can still have an authoritative saved partial answer.
        // Keep its error/review state while adopting the durable bookmark now.
        acceptAnswer(context, result.data.saved_answer);
        App.trackAnswer?.(context, "partial");
        return;
      }
      if (!result.ok || result.data?.error || !result.data?.turn) {
        // A plain (non-SSE) 4xx refusal happens before the server accepted a
        // turn: nothing was dispatched, so the message goes back to the composer.
        const data = result.data || {};
        const refused = result.streamed === false && result.status >= 400 && result.status < 500
          && !context.metadata.agentTurnId && data.recoverable !== true && !data.recovery_state;
        throw Object.assign(new Error(apiError(data)), { failure: data, notDispatched: refused });
      }
      acceptAnswer(context, result.data);
      App.trackAnswer?.(context, "ok");
      offerWatch(context);
    } catch (error) {
      if (signal.aborted || error.name === "AbortError" || !registry.isAuthCurrent(context)) return;
      const failure = error.failure || {};
      const code = failure.code || failure.error_code || failure.detail?.code;
      context.consensus.status = "error";
      context.consensus.error = { message: error.message, code,
        required_tokens: failure.required_tokens, available_tokens: failure.available_tokens };
      if (error.notDispatched || !context.metadata.requestSent) {
        // Never offer "Check saved answer" or keep a Failed sidebar row for a
        // message that the server refused before starting it.
        context.metadata.requestSent = false;
        context.metadata.recoverable = false;
        context.consensus.error.message = `Message not sent. ${error.message}`;
        releaseRunRow(context);
      } else if (['agent_token_reservation', 'agent_tokens_exhausted'].includes(code) && !context.consensus.streamText) {
        // An admission refusal produced no answer: offer the question again.
        context.metadata.recoverable = false;
        context.metadata.restoreDraft = true;
      }
      context.bookmark.status = "failed";
      if (context.metadata.requestSent) App.trackAnswer?.(context, "failed");
      registry.setStatus(context.runId, "failed", { message: error.message });
      if (!context.metadata.agentReview && context.basis && registry.visible()?.runId === context.runId) registry.selectConversationBasis(context.basis);
    } finally {
      clearTimeout(timer);
      context.controllers.query = null;
      restoreUnsentDraft(context);
      if (registry.isAuthCurrent(context)) registry.renderVisible();
      if (!terminalBudget && context.metadata.requestSent && registry.isAuthCurrent(context)) await refreshBudget(context.auth.uid);
    }
  }
  App.agentChat = { canUse, modeState, hasValidComparisonSelection, sendBlocker, syncComposer, isSelected: () => selectedMode() === "agent",
    render: () => renderShell(), renderShell, project, send, revealPendingReview, syncPendingReview,
    tokenBudget: () => App.tokenBudget?.current?.() || null, receiveBudget,
    // demo.js: show (true) or release (false) the answer surface for the demo.
    // Returns the activity host for that turn, or null when released.
    demoView: on => {
      demoView = Boolean(on);
      if (demoView) { document.getElementById("agentAnswer")?.removeAttribute("hidden"); renderShell(true); return activityHost("demo"); }
      renderShell(true); return null;
    } };
  // Coming back to the tab refreshes a figure older than a minute; switching
  // between editor and browser no longer fetches it every time.
  function refreshVisibleBudget() {
    if (Date.now() - budgetSeenAt < 60000) return;
    if (document.visibilityState !== 'hidden' && canUse() && selectedMode() === 'agent' && catalogStatus === 'ready') refreshBudget(catalogOwner);
  }
  document.addEventListener('visibilitychange', refreshVisibleBudget);
  window.addEventListener('focus', refreshVisibleBudget);
  // The run projector (run-view.js) renders the shell for every registry
  // change; this listener only catches changes without a projection, and is
  // a no-op when nothing the shell shows has changed.
  window.addEventListener("consensio:run-registry-change", () => renderShell());
  window.addEventListener("consensio:run-mode-change", () => renderShell());
  window.addEventListener('consensio:agent-actions-change', () => { syncPendingReview(); window.updateQuestionInputAccess?.(); });
  // Google selection/consent changes (chips, sheet, consent box) change the
  // send blocker, so the notice and Send state must follow immediately.
  window.addEventListener('consensio:agent-google-change', () => { syncComposer(); window.updateQuestionInputAccess?.(); });
  document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("agentRecover")?.addEventListener("click", () => {
      const context = registry.visible();
      if (["failed", "canceled"].includes(context?.status) && context.metadata.requestSent) send(context);
    });
    // The shared picker emits input before change. Commit before other UI
    // listeners can project the previous draft selection back into the select.
    for (const id of ["agentModelDropdown", "agentReasoningEffort"]) {
      const control = document.getElementById(id);
      control?.addEventListener("input", changeSelection, true);
      control?.addEventListener("change", changeSelection, true);
    }
    document.getElementById("agentModelsRetry")?.addEventListener("click", () => { catalogStatus = "idle"; render(); });
    document.getElementById('agentComposerAction')?.addEventListener('click', event => {
      // The shared picker's outside-click handler must not close this shortcut's menu.
      event.stopPropagation();
      runNoticeAction(event.currentTarget.dataset.action);
    });
    document.getElementById('agentAnswerErrorActions')?.addEventListener('click', event => {
      const button = event.target.closest('button[data-action]');
      if (!button) return;
      event.stopPropagation();
      runNoticeAction(button.dataset.action);
    });
    document.getElementById('agentReviewAction')?.addEventListener('click', () => revealPendingReview());
    document.getElementById('questionInput')?.addEventListener('input', () => {
      if (selectedMode() === 'agent') window.updateQuestionInputAccess?.();
    });
    render();
  });
})();
