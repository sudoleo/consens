// Single-model execution, using the shared composer, run registry and history.
(function () {
  "use strict";
  const App = window.App = window.App || {};
  const registry = App.runRegistry;
  let preference = "consensus";
  let catalog = null;
  let catalogOwner = "";
  let catalogStatus = "idle";
  let loadGeneration = 0;
  let catalogUser = null, catalogAuthGeneration, budgetRefresh = null;
  const selections = new Map();
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
  function selection() {
    const preferred = preferredSelection() || {};
    const model = catalog?.models.find(item => item.id === preferred.model_id)
      || catalog?.models.find(item => item.id === catalog.default_model_id) || catalog?.models[0];
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
      const token = await user.getIdToken();
      if (user !== window.auth?.currentUser || generation !== loadGeneration) return;
      const response = await fetch("/agent/models", { headers: { Authorization: `Bearer ${token}` } });
      const data = await response.json();
      if (user !== window.auth?.currentUser || generation !== loadGeneration || !canUse()) return;
      if (!response.ok || !Array.isArray(data.models) || !data.models.length) throw new Error("Model list unavailable");
      catalog = data;
      catalogStatus = "ready";
    } catch (_) {
      if (uid === catalogOwner && generation === loadGeneration) catalogStatus = "failed";
    } finally {
      if (uid === catalogOwner && generation === loadGeneration) render();
    }
  }
  function receiveBudget(budget, uid) {
    if (!budget || !catalog || !canUse() || uid !== catalogOwner || uid !== window.auth?.currentUser?.uid) return;
    if (!Number.isSafeInteger(budget.limit) || budget.limit <= 0
      || ['used', 'reserved', 'unknown', 'remaining', 'revision', 'config_revision'].some(key =>
        budget[key] !== undefined && (!Number.isSafeInteger(budget[key]) || budget[key] < 0))) return;
    const previous = catalog.token_budget;
    if ((budget.config_revision ?? 0) < (previous?.config_revision ?? 0)) return;
    if ((budget.config_revision ?? 0) === (previous?.config_revision ?? 0)) {
      if (budget.day && previous?.day && budget.day < previous.day) return;
      if (!budget.day || !previous?.day || budget.day === previous.day) {
        if (Number.isSafeInteger(budget.revision) && Number.isSafeInteger(previous?.revision)) {
          if (budget.revision < previous.revision) return;
        } else if (Number.isFinite(budget.observed_at) && Number.isFinite(previous?.observed_at)
          && budget.observed_at < previous.observed_at) return;
      }
    }
    catalog.token_budget = budget;
    catalog.budgetStale = false;
    App.sidebarQuota?.sync();
  }
  async function refreshBudget(uid) {
    const generation = loadGeneration;
    if (budgetRefresh?.generation === generation) return;
    const pending = budgetRefresh = {generation};
    try {
      const user = window.auth?.currentUser;
      if (!user || uid !== user.uid || !canUse()) return;
      const token = await user.getIdToken();
      if (user !== window.auth?.currentUser || generation !== loadGeneration) return;
      const response = await fetch('/agent/budget', { headers: { Authorization: `Bearer ${token}` } });
      if (!response.ok) throw new Error('Allowance unavailable');
      const data = await response.json();
      if (user === window.auth?.currentUser && generation === loadGeneration) receiveBudget(data.token_budget, uid);
    } catch (_) {
      if (generation === loadGeneration && catalog) { catalog.budgetStale = true; App.sidebarQuota?.sync(); }
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
    const signature = JSON.stringify(options);
    if (select.dataset.options !== signature) {
      const groups = new Map();
      const grouped = options.some(model => model.provider);
      const nodes = options.map(model => {
        const option = document.createElement("option");
        option.value = model.id;
        option.textContent = model.label;
        option.dataset.modelLabel = model.label;
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
    select.disabled = !ready || running;
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
    if (select.disabled) App.collapseExpandedModelPicker?.(select);
    if (effort.disabled || effort.parentElement.hidden) App.collapseExpandedModelPicker?.(effort);
    window.syncCustomModelPickers?.();
  }
  function changeSelection() {
    const select = document.getElementById("agentModelDropdown");
    const effort = document.getElementById("agentReasoningEffort");
    const model = catalog?.models.find(item => item.id === select?.value);
    if (!model || !canUse()) return;
    const value = { model_id: model.id, reasoning_effort: model.reasoning_efforts.includes(effort.value) ? effort.value : "default" };
    rememberSelection(value);
    render();
  }
  function activityHost(key) {
    const host = document.getElementById("agentAnswerActivity");
    if (host && host.dataset.turn !== key) {
      host.replaceChildren();
      delete host._agentActivity;
      host.dataset.turn = key;
    }
    return host;
  }

  function canUse() {
    const access = App.agentAccess;
    return Boolean(window.auth?.currentUser?.uid && access?.uid === window.auth.currentUser.uid && access.allowed);
  }
  function selectedMode() {
    const context = registry.visible();
    if (context) return context.config.executionMode || "consensus";
    const basis = registry.getSelectedConversationBasis({ includeHistory: false });
    if (basis) return basis.executionMode || "consensus";
    return canUse() ? preference : "consensus";
  }
  function render() {
    const agent = selectedMode() === "agent";
    const comparisonPicker = document.getElementById("consensusModelDropdown");
    if (comparisonPicker) {
      comparisonPicker.dataset.comparisonOnly = String(agent);
      comparisonPicker.setAttribute("aria-label", agent ? "Comparison models" : "Models and consensus engine");
    }
    renderControls(agent);
    const modeChanged = document.body.classList.contains("single-agent-active") !== agent;
    document.body.classList.toggle("single-agent-active", agent);
    App.renderComposerMode?.();
    if (modeChanged) requestAnimationFrame(() => App.resizeQuestionInput?.());
    const chatTab = document.getElementById("viewSwitchConsensus");
    if (chatTab) chatTab.textContent = agent ? "Chat" : "Consensus";
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
    const label = document.getElementById("chatExecutionControl");
    const select = document.getElementById("chatExecutionMode");
    const locked = Boolean(registry.visible() || registry.getSelectedConversationBasis({ includeHistory: false }));
    if (label) label.hidden = (!canUse() && !agent) || (agent && locked);
    if (select) {
      select.value = agent ? "agent" : "consensus";
      select.disabled = locked || !canUse();
      select.title = locked ? "Start a new chat to change mode" : "Chat mode";
      App.initCustomModelPicker?.(select, { menuWidth: 290 });
      if (select.disabled) App.collapseExpandedModelPicker?.(select);
      window.syncCustomModelPickers?.();
      const button = select._customModelPicker?.displayButton;
      if (button && locked) button.title = "Start a new chat to change mode";
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
    if (panel) panel.hidden = !agent || (!context && !basis);
    if (agent && !context && basis) {
      renderAnswer(basis.consensus || "", basis.currentTurn?.agent_failure?.error
        || (basis.currentTurn?.status === 'failed' ? 'This response did not finish successfully.' : ''),
        App.agentActivity?.label(basis.currentTurn?.agent_settings) || "Agent · Beta");
      App.agentActivity?.renderTurn(activityHost(`${basis.chatId}:${basis.turnId}`), basis.currentTurn);
      App.agentReview?.render(document.getElementById("agentAnswerBody"), basis.currentTurn?.agent_review,
        { sources: basis.currentTurn?.sources, events: basis.currentTurn?.agent_activity, key: basis.turnId, question: basis.question });
      App.agentDelegation?.project(basis.currentTurn?.agent_settings?.policy?.delegation ? {
        chatId: basis.chatId, turnId: basis.turnId || basis.currentTurn?.id,
        usage: basis.currentTurn?.agent_usage, running: basis.currentTurn?.status === "pending" } : null);
    }
    if (!agent || (!context && !basis)) App.agentDelegation?.project(null);
    window.updateQuestionInputAccess?.();
  }
  function renderAnswer(text, error, label) {
    const body = document.getElementById("agentAnswerBody");
    const errorEl = document.getElementById("agentAnswerError");
    const title = document.getElementById("agentAnswerLabel");
    if (title) title.textContent = label;
    if (body && body.dataset.markdown !== text) {
      body.dataset.markdown = text;
      window.injectMarkdown?.(body, text, []);
    }
    if (errorEl) { errorEl.textContent = error; errorEl.hidden = !error; }
  }
  function project(context) {
    render();
    window.exitHeroMode?.();
    document.body.classList.remove("direct-comparison-active", "thread-message-pending");
    App.consensusPipeline?.dismiss?.();
    window.projectAgentModeRun?.(null);
    App.setAppTitle?.(context.question);
    App.setThreadQuestion?.(context.question);
    App.setThreadQuestionAttachments?.([]);
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
    const state = context.consensus;
    renderAnswer(state.text || state.streamText || "", state.error?.message || state.completedTurn?.agent_failure?.error || "",
      App.agentActivity?.label(state.completedTurn?.agent_settings || context.metadata.agentSettings) || "Agent · Beta");
    App.agentActivity?.render(activityHost(context.runId), {
      events: state.completedTurn?.agent_activity || context.metadata.agentActivity || [],
      usage: state.completedTurn?.agent_usage || context.metadata.agentUsage, running: registry.isExecuting(context.runId),
      responding: Boolean(state.text || state.streamText),
      status: context.status, truncated: state.completedTurn?.agent_reasoning_truncated,
      finishReason: state.completedTurn?.agent_finish_reason,
      review: state.completedTurn?.agent_review || context.metadata.agentReview,
    });
    App.agentReview?.render(document.getElementById("agentAnswerBody"), state.completedTurn?.agent_review || context.metadata.agentReview,
      { sources: state.completedTurn?.sources, events: state.completedTurn?.agent_activity || context.metadata.agentActivity,
        key: state.completedTurn?.id || context.runId, question: context.question });
    App.syncSendButtonRunning?.();
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
    context.consensus.text = context.consensus.streamText = data.response;
    context.consensus.status = "complete";
    context.consensus.completedTurn = turn;
    context.consensus.error = turn.status === "failed" ? { message: turn.agent_failure?.error || "This saved answer is incomplete. The response did not finish successfully." } : null;
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
  async function recoverAnswer(context) {
    if (!context || !registry.isAuthCurrent(context) || !['failed', 'canceled'].includes(context.status)
        || !context.metadata.requestSent || context.metadata.recoverable === false || context.metadata.recovering) return;
    let action;
    try {
      action = registry.beginAction({ key: 'agent-recovery', ownerRunId: context.runId, bookmarkId: context.bookmark.id });
      context.metadata.recovering = true;
      registry.show(context.runId);
      const token = await window.auth.currentUser.getIdToken();
      if (!registry.isAuthCurrent(context) || action.controller.signal.aborted) return;
      const settings = context.config.agentSettings;
      const result = await window.streamSSERequest('/agent', {
        chat_id: context.metadata.chatId, question: context.question, client_request_id: context.requestIdentity,
        bookmark_id: context.bookmark.id, recover_only: true, model_id: settings.model_id,
        reasoning_effort: settings.reasoning_effort || 'default',
        comparison_models: Object.keys(context.config.comparisonModels || {}).length ? context.config.comparisonModels : null,
        check_sources: context.config.checkSources === true,
      }, action.controller.signal, {}, { headers: { Authorization: `Bearer ${token}` } });
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
  async function send(recovery = null) {
    if (recovery) return recoverAnswer(recovery);
    if (!canUse()) { App.showPopup?.("Agent Beta is available to Pro users and admins."); return; }
    if (window.getAttachmentsPayload?.()?.length) {
      App.showPopup?.("Agent Beta currently supports text only. Remove the attachments to continue.");
      return;
    }
    const input = document.getElementById("questionInput");
    const draft = input?.value || "";
    const question = recovery?.question || String(App.quote?.compose?.(draft) ?? draft).trim();
    if (!question) return;
    const settings = recovery?.config.agentSettings || {
      ...selection(), reasoning_effort: document.getElementById("agentReasoningEffort")?.value || "default",
    };
    const comparisonModels = recovery?.config.comparisonModels || Object.fromEntries((App.modelPrefs || [])
      .filter(pref => document.getElementById(pref.checkId)?.checked)
      .map(pref => [pref.provider, document.getElementById(pref.selectId)?.value]));
    if (!recovery && (!catalog || !catalog.models.some(model => model.id === settings.model_id))) {
      App.showPopup?.("Choose an available agent model before sending."); return;
    }
    const basis = recovery ? recovery.basis : registry.getSelectedConversationBasis();
    if (basis && (!basis.chatId || basis.continuationUnavailable)) {
      App.showPopup?.("Reopen this saved chat before continuing."); return;
    }
    let context;
    try {
      context = registry.create({
        question, mode: "Agent", basis, followup: Boolean(basis),
        requestIdentity: recovery?.requestIdentity,
        bookmarkId: recovery?.bookmark.id || basis?.bookmarkId || `b_agent_${crypto.randomUUID().replaceAll("-", "")}`,
        bookmarkTitle: basis?.title || question,
        config: { executionMode: "agent", agentMode: true, autoConsensus: false,
          deepSearch: false, checkSources: App.isSourceCheckEnabled?.() === true, useOwnKeys: false, providers: [], agentSettings: settings, comparisonModels },
        metadata: { agentActivity: [], agentSettings: { ...settings, label: catalog?.models.find(model => model.id === settings.model_id)?.label } },
        usage: { status: "simulation", key: null },
      });
    } catch (error) { App.showPopup?.(error.message); return; }
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
    };
    registry.setStatus(context.runId, "running");
    if (!recovery) {
      App.clearQuestionDraft?.();
      if (input) { input.value = ""; input.dispatchEvent(new Event("input", { bubbles: true })); }
      App.quote?.clear?.();
    }
    App.composer?.collapse?.({ force: true });
    if (!recovery) App.revealSentMessage?.();
    let timer, terminalBudget = false;
    try {
      const token = await window.auth.currentUser.getIdToken();
      if (!registry.isAuthCurrent(context) || signal.aborted) return;
      const headers = { Authorization: `Bearer ${token}` };
      let chatId = recovery?.metadata.chatId || basis?.chatId;
      if (!chatId) {
        const response = await fetch("/chats", {
          method: "POST", headers: { ...headers, "Content-Type": "application/json" }, signal,
          body: JSON.stringify({ title: question.slice(0, 120), execution_mode: "agent" }),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(apiError(data));
        chatId = data.chat.id;
      }
      if (!registry.isAuthCurrent(context) || signal.aborted) return;
      context.metadata.chatId = chatId;
      context.metadata.requestSent = true;
      context.phase = "answers";
      context.consensus.status = "streaming";
      registry.update(context.runId, () => {});
      const result = await window.streamSSERequest("/agent", {
        chat_id: chatId, question, client_request_id: context.requestIdentity,
        bookmark_id: context.bookmark.id,
        recover_only: Boolean(recovery),
        model_id: settings.model_id,
        reasoning_effort: settings.reasoning_effort || "default",
        comparison_models: Object.keys(comparisonModels).length ? comparisonModels : null,
        check_sources: context.config.checkSources === true,
      }, signal, {
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
      }, { headers });
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
        return;
      }
      if (!result.ok || result.data?.error || !result.data?.turn) throw new Error(apiError(result.data));
      acceptAnswer(context, result.data);
    } catch (error) {
      if (signal.aborted || error.name === "AbortError" || !registry.isAuthCurrent(context)) return;
      context.consensus.status = "error";
      context.consensus.error = { message: error.message };
      context.bookmark.status = "failed";
      registry.setStatus(context.runId, "failed", { message: error.message });
      if (!context.metadata.agentReview && context.basis && registry.visible()?.runId === context.runId) registry.selectConversationBasis(context.basis);
    } finally {
      clearTimeout(timer);
      context.controllers.query = null;
      if (registry.isAuthCurrent(context)) registry.renderVisible();
      if (!terminalBudget && context.metadata.requestSent && registry.isAuthCurrent(context)) await refreshBudget(context.auth.uid);
    }
  }
  App.agentChat = { canUse, isSelected: () => selectedMode() === "agent", render, project, send,
    tokenBudget: () => canUse() && catalogOwner === window.auth?.currentUser?.uid
      ? (catalog?.budgetStale ? {...catalog.token_budget, stale: true} : catalog?.token_budget) : null, receiveBudget };
  function refreshVisibleBudget() {
    if (document.visibilityState !== 'hidden' && canUse() && selectedMode() === 'agent' && catalogStatus === 'ready') refreshBudget(catalogOwner);
  }
  document.addEventListener('visibilitychange', refreshVisibleBudget);
  window.addEventListener('focus', refreshVisibleBudget);
  setInterval(refreshVisibleBudget, 60000);
  window.addEventListener("consensio:run-registry-change", render);
  document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("chatExecutionMode")?.addEventListener("change", event => {
      preference = canUse() && event.target.value === "agent" ? "agent" : "consensus";
      render();
    });
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
    render();
  });
})();
