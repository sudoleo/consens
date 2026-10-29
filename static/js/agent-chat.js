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
  // Where the next message's settings come from: this session's pick for
  // the chat (also one made while a response runs: it is for the next
  // message, the running one keeps its own), the running turn, the settings
  // an opened chat was saved with, the account's own pick (account setting
  // "agent_model") or the catalog default.
  function preferredSource() {
    const context = registry.visible();
    const basis = registry.getSelectedConversationBasis({ includeHistory: false });
    const saved = context?.consensus.completedTurn?.agent_settings || context?.metadata.agentSettings || basis?.currentTurn?.agent_settings;
    const session = selections.get(selectionKey());
    if (session) return { value: session, source: "session" };
    if (context && registry.isExecuting(context.runId)) return { value: context.config.agentSettings || saved, source: "run" };
    if (saved) return { value: saved, source: "chat" };
    const preferred = App.userSettings.get("agent_model");
    if (preferred) return { value: preferred, source: "account" };
    return { value: { model_id: catalog?.default_model_id, reasoning_effort: "default" }, source: "default" };
  }
  function preferredSelection() {
    return preferredSource().value;
  }
  // A migrated ID (grok-4.3-no-reasoning) names its successor, as on the server.
  function canonicalId(id) {
    return (id && catalog?.aliases?.[id]) || id;
  }
  // Premium models stay Pro in Agent as in every other mode. They stay in the
  // list with their badge; the server refuses them for other tiers as well.
  function locked(model) {
    return Boolean(model?.premium) && window.App?.state?.get?.("isUserPro") !== true;
  }
  function selectable(model) {
    return Boolean(model) && model.available !== false && !locked(model);
  }
  // High, Extra high and Max are Pro (the server refuses them as well).
  const PRO_EFFORTS = new Set(["high", "xhigh", "max"]);
  function effortLocked(value) {
    return PRO_EFFORTS.has(value) && window.App?.state?.get?.("isUserPro") !== true;
  }
  // Auto lets the model reason at its own default, "high" for Sonnet 5.5,
  // a Pro level. Without Pro the server runs Auto as Medium where the model
  // offers it (free_default_effort), so the picker shows Medium instead.
  function autoEffort(model) {
    return window.App?.state?.get?.("isUserPro") !== true && model?.free_default_effort ? model.free_default_effort : null;
  }
  function visibleEfforts(model) {
    const efforts = model?.reasoning_efforts || ["default"];
    return autoEffort(model) ? efforts.filter(value => value !== "default") : efforts;
  }
  function effortFor(model, value) {
    return visibleEfforts(model).includes(value) && !effortLocked(value) ? value : autoEffort(model) || "default";
  }
  function selection() {
    const preferred = preferredSelection() || {};
    const available = catalog?.models.filter(selectable);
    const wanted = canonicalId(preferred.model_id);
    const model = available?.find(item => item.id === wanted)
      || available?.find(item => item.id === catalog.default_model_id) || available?.[0];
    return model ? { model_id: model.id, reasoning_effort: effortFor(model, preferred.reasoning_effort) } : preferred;
  }
  // options.derived: a repair the app makes itself, not a choice (see
  // App.userSettings.set); it never wins over the account's own pick.
  function rememberSelection(value, options) {
    selections.set(selectionKey(), value);
    App.userSettings.set("agent_model", value, options);
  }
  // The preferred model or level cannot run: selection() falls back for every
  // render and send. Only a lasting cause is written back: a migrated ID or a
  // model that left the list, and to the account's pick only when it came
  // from there. A model that is listed but unavailable for now, Pro models or
  // levels while the tier is still loading are never saved over, so the
  // user's own pick returns by itself. Opening an old chat never changes the
  // pick for new chats.
  const repairNotices = new Set();
  function repairSelection(previous, source, current) {
    if (!previous.model_id) return;
    const wanted = canonicalId(previous.model_id);
    const listed = catalog.models.find(item => item.id === wanted);
    if ((wanted !== previous.model_id && wanted === current.model_id) || !listed) {
      // A level the new model offers stays, even one the tier may not have
      // confirmed yet; selection() still applies the tier per message.
      const offered = catalog.models.find(item => item.id === current.model_id)?.reasoning_efforts || ["default"];
      const repaired = { model_id: current.model_id,
        reasoning_effort: offered.includes(previous.reasoning_effort) ? previous.reasoning_effort : current.reasoning_effort };
      if (source === "account") rememberSelection(repaired, { derived: true });
      else if (source !== "run") selections.set(selectionKey(), repaired);
    }
    if (wanted === current.model_id || (listed && locked(listed))) return;
    const notice = `${selectionKey()}:${previous.model_id}`;
    if (repairNotices.has(notice)) return;
    repairNotices.add(notice);
    const label = catalog.models.find(item => item.id === current.model_id)?.label;
    App.showPopup?.(listed
      ? `${listed.label} is unavailable right now. Using ${label} for your next message.`
      : `Previous model unavailable. Selected ${label} for your next message.`);
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
  // look: Agent's chip is on screen, also while access is still loading for
  // a session expected to land in Agent (expectingAgent below).
  function renderControls(look) {
    const uid = canUse() ? window.auth.currentUser.uid : "";
    if (uid !== catalogOwner || catalogUser !== window.auth?.currentUser || catalogAuthGeneration !== App.authState?.generation) {
      catalogOwner = uid;
      catalogUser = window.auth?.currentUser;
      catalogAuthGeneration = App.authState?.generation;
      catalog = null;
      catalogStatus = "idle";
      loadGeneration++;
      selections.clear();
      repairNotices.clear();
    }
    const host = document.getElementById("agentModelControls");
    const select = document.getElementById("agentModelDropdown");
    const effort = document.getElementById("agentReasoningEffort");
    if (host) host.hidden = !look;
    App.sidebarQuota?.sync();
    if (!look || !select || !effort) {
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
    const { value: previous = {}, source } = preferredSource();
    if (ready && !running && previous && (previous.model_id !== current.model_id || previous.reasoning_effort !== current.reasoning_effort)) {
      // Historical settings stay frozen; only the next message changes.
      repairSelection(previous, source, current);
    }
    // While the list loads, the chip keeps the name it had when the page was
    // left, else the default model's (app-bootstrap.js App.firstFrame): a
    // "Loading models…" in between was one of five faces of the composer in
    // its first second (Apple-Audit B1).
    const waiting = App.firstFrame?.agentModel?.() || "Loading models…";
    const options = ready ? catalog.models : [{ id: "", label: catalogStatus === "failed" ? "Models unavailable" : waiting }];
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
    // Open also while a response runs: the pick is for the next message (the
    // running one keeps its settings), as the comparison models always were.
    // Until 2026-10-26 a run locked them, and the Reasoning button below the
    // composer followed only now and then.
    select.disabled = !ready || !catalog.models.some(selectable);
    select.dataset.running = String(running);
    // Whether the chip's words come from the model list (app-bootstrap.js
    // remembers only those for the next first frame; agent-mode.js does not
    // dim Reasoning while they load).
    select.dataset.catalog = ready ? "ready" : catalogStatus;
    const model = catalog?.models.find(item => item.id === select.value);
    const efforts = visibleEfforts(model);
    const waitingEffort = ready ? "" : App.firstFrame?.agentEffort?.() || "";
    const effortSignature = JSON.stringify([model?.id, efforts, efforts.map(effortLocked), waitingEffort]);
    if (effort.dataset.options !== effortSignature) {
      effort.replaceChildren(...efforts.map(value => {
        const option = document.createElement("option");
        option.value = value;
        const [copyLabel, description] = effortCopy[value] || [value, "Reasoning effort"];
        const label = waitingEffort || copyLabel;
        option.textContent = label;
        option.dataset.modelLabel = label;
        option.dataset.description = description;
        option.disabled = effortLocked(value);
        if (option.disabled) option.dataset.modelBadge = "Pro";
        return option;
      }));
      effort.dataset.options = effortSignature;
    }
    effort.value = model ? effortFor(model, current.reasoning_effort) : "default";
    effort.disabled = !ready || efforts.length < 2;
    effort.dataset.available = String(ready && model?.reasoning_available);
    effort.parentElement.hidden = true;
    document.getElementById("agentModelsRetry")?.toggleAttribute("hidden", catalogStatus !== "failed");
    App.initCustomModelPicker?.(select, { grouped: true, secondarySelect: effort, secondaryLabel: 'Reasoning' });
    // One chip, one menu: the chat model above, the models it is compared
    // with below (model-picker.js, linked pickers). The comparison chip of
    // Consensus/Compare steps back while linked.
    const comparison = document.getElementById("consensusModelDropdown");
    App.linkModelPicker?.(select, comparison, { ownLabel: "Agent", companionLabel: "Compare with", ariaLabel: "Agent and comparison models" });
    // A locked chat model (its list still loading) closes only its own
    // levels; the comparison models stay open to change for the next message.
    if (select.disabled) App.collapseExpandedModelPicker?.(select, { ownLevelsOnly: true });
    if (effort.disabled || effort.parentElement.hidden) App.collapseExpandedModelPicker?.(effort);
    window.syncCustomModelPickers?.();
  }
  // The Agent's settings card (agent-settings.js): the pick for the next
  // message, in this chat and as the account's choice, as if made in the picker.
  // False when the picker would not take it as given (a Pro model or level
  // this page does not unlock): the card then says it could not apply it.
  function applyPick(value) {
    const model = catalog?.models.find(item => item.id === canonicalId(value?.model_id));
    if (!selectable(model) || !canUse()) return false;
    const effort = effortFor(model, value.reasoning_effort || "default");
    if (effort !== (value.reasoning_effort || "default")) return false;
    rememberSelection({ model_id: model.id, reasoning_effort: effort });
    // A pick made earlier on the new-chat screen would otherwise beat the
    // account's pick in the next new chat.
    selections.delete(`${catalogOwner}:draft`);
    render();
    return true;
  }
  function modelLabel(id) {
    return catalog?.models.find(item => item.id === canonicalId(id))?.label || null;
  }
  function changeSelection() {
    const select = document.getElementById("agentModelDropdown");
    const effort = document.getElementById("agentReasoningEffort");
    const model = catalog?.models.find(item => item.id === select?.value);
    if (!selectable(model) || !canUse()) return;
    const value = { model_id: model.id, reasoning_effort: effortFor(model, effort.value) };
    rememberSelection(value);
    render();
  }
  function activityHost(key) {
    const host = document.getElementById("agentAnswerActivity");
    if (host && host.dataset.turn !== key) {
      App.agentActivity?.dispose(host);
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
  // A guest (app-bootstrap.js App.isGuest) gets Agent's composer of a new
  // chat as an account does by default (Max, Apple-Audit H3): the default
  // model's name on the chip, no model list (it needs an account), no notice.
  // Every choice in it asks for the login (model-picker.js, attachments.js,
  // agent-google.js), and Send does too (composer-invite.js).
  function guest() {
    return !window.auth?.currentUser && App.isGuest?.() === true;
  }
  function modeState() {
    return { family: chatFamily(), canUse: canUse(), pending: accessPending(), guest: guest() };
  }
  // Agent's look before its access is known (Apple-Audit B1, B4): a session
  // app-bootstrap.js expects in Agent (html.agent-shell-expected) keeps
  // Agent's composer in a new chat instead of Consensus's for a moment. A
  // look only: nothing is sent until access is known (app-init.js waits).
  function expectingAgent() {
    return !chatFamily() && document.documentElement.classList.contains("agent-shell-expected");
  }
  function looksAgent() {
    return selectedMode() === "agent" || expectingAgent();
  }
  // While access is unknown only a failed status check speaks (firebase.js
  // asks again by itself, Apple-Audit B8); a short wait stays quiet.
  function accessBlocker() {
    const check = App.agentAccessCheck;
    if (!check?.failed || check.uid !== window.auth?.currentUser?.uid) return null;
    return { message: "Your account could not be reached. Trying again…", action: "status-retry", label: "Try now" };
  }
  function selectedMode() {
    return (App.runMode?.effective?.() === "agent") ? "agent" : (chatFamily() || "consensus");
  }
  function shellInputs() {
    const context = registry.visible();
    const basis = registry.getSelectedConversationBasis({ includeHistory: false });
    const picked = catalogStatus === 'ready' ? selection() : null;
    return JSON.stringify([selectedMode(), App.runMode?.preference?.(), canUse(), guest(), window.auth?.currentUser?.uid || '', App.authState?.generation,
      Boolean(window.__consensioAuthState?.known),
      expectingAgent(), App.agentAccessCheck?.attempt,
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
    // First-paint hint for app-bootstrap.js, written once access is known:
    // whether this browser's account may use Agent at all (the mode of a new
    // chat follows from it and the account's choice).
    const authState = window.__consensioAuthState;
    const accessKnown = Boolean(App.agentAccess?.uid && App.agentAccess.uid === window.auth?.currentUser?.uid);
    if (accessKnown) { try { localStorage.setItem("agentShellExpected", App.agentAccess.allowed ? "1" : "0"); } catch (_) {} }
    if (agent || accessKnown || (authState?.known && !authState.uid)) document.documentElement.classList.remove("agent-shell-expected");
    // A sign-in on this page (no reload in between) expects Agent the same
    // way until its access is known (app-bootstrap.js App.expectsAgent).
    else if (accessPending() && App.expectsAgent?.()) document.documentElement.classList.add("agent-shell-expected");
    // Agent's look (chip, Reasoning, no demo, its words) stands from the first
    // frame for a session expected in Agent and stays until access is known.
    const look = agent || expectingAgent();
    const comparisonPicker = document.getElementById("consensusModelDropdown");
    if (comparisonPicker) {
      comparisonPicker.dataset.comparisonOnly = String(look);
      comparisonPicker.setAttribute("aria-label", look ? "Comparison models" : "Answering models");
      // Agent shows one chip: the comparison models live in the Agent menu.
      const chip = comparisonPicker.closest(".consensus-model");
      if (chip) chip.hidden = look;
    }
    renderControls(look);
    resumePending();
    if (deferredFollow && canUse()) {
      const deferred = deferredFollow;
      deferredFollow = null;
      setTimeout(() => followRunning(deferred), 0);
    }
    const modeChanged = document.body.classList.contains("single-agent-active") !== (look || demoView);
    document.body.classList.toggle("single-agent-active", look || demoView);
    document.body.classList.toggle("agent-demo-active", demoView);
    App.renderComposerMode?.();
    if (modeChanged) requestAnimationFrame(() => App.resizeQuestionInput?.());
    // The switch says "Chat" and the sidebar "New chat" in every mode and for
    // guests (Max, Apple-Audit H3): the words no longer change once the mode
    // is known, so the pill keeps its width (B10).
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
      App.taskChecks?.scope(document.getElementById("agentAnswerBody"), { chatId: basis.chatId,
        turnId: basis.currentTurn?.status === 'completed' ? basis.currentTurn.id || basis.turnId : '',
        checked: basis.currentTurn?.task_checks });
      renderAnswer(basis.consensus || "", failure?.error ? failureNotice(failure, basis.currentTurn?.agent_review, basis.consensus || "")
        : (basis.currentTurn?.status === 'failed' ? 'This response did not finish successfully.' : ''));
      markLiveTurn(basis.currentTurn);
      App.agentActivity?.renderTurn(activityHost(`${basis.chatId}:${basis.turnId}`), basis.currentTurn, {
        vmRestore: basis.currentTurn?.agent_vm?.checkpoint && basis.currentTurn?.status !== 'pending'
          ? () => restoreVm(basis.chatId, basis.currentTurn.id || basis.turnId) : null });
      App.agentReview?.render(document.getElementById("agentAnswerBody"), basis.currentTurn?.agent_review,
        { sources: basis.currentTurn?.sources, events: basis.currentTurn?.agent_activity, key: basis.turnId, question: basis.question });
      App.passageCheck?.apply(document.getElementById("agentAnswerBody"), basis.currentTurn?.agent_review,
        { live: basis.currentTurn?.status === "pending" });
      App.agentMemory?.render(document.getElementById('agentAnswerBody'), {
        key: `${basis.chatId}:${basis.turnId}`, changes: basis.currentTurn?.agent_memory,
      });
      App.agentMemory?.nudge(document.getElementById('agentAnswerBody'), { key: `${basis.chatId}:${basis.turnId}` });
      App.agentWatch?.render(document.getElementById('agentAnswerBody'), { key: `${basis.chatId}:${basis.turnId}`,
        proposal: basis.currentTurn?.status === 'completed' ? basis.currentTurn.agent_watch : null });
      // A reopened chat's answer has its Watch pill too, with the question of
      // this turn, never one left from the chat shown before (J20).
      App.watch?.answerButton?.(document.getElementById('agentAnswerBody'), {
        question: basis.currentTurn?.question || basis.question,
        eligible: basis.currentTurn?.status === 'completed' && !basis.currentTurn?.agent_watch,
        followUp: Boolean(document.querySelector('#threadHistory > .thread-history-turn')) });
      App.answerShare?.button?.(document.getElementById('agentAnswerBody'), {
        chatId: basis.chatId, turnId: basis.currentTurn?.id || basis.turnId,
        eligible: basis.currentTurn?.status === 'completed' && Boolean(String(basis.consensus || '').trim()) });
      App.agentGithub?.render(document.getElementById('agentAnswerBody'), { key: `${basis.chatId}:${basis.turnId}`,
        proposal: basis.currentTurn?.status === 'completed' ? basis.currentTurn.agent_pull_request : null,
        chatId: basis.chatId, turnId: basis.currentTurn?.id || basis.turnId });
      App.agentSettings?.render(document.getElementById('agentAnswerBody'), { key: `${basis.chatId}:${basis.turnId}`,
        proposal: basis.currentTurn?.status === 'completed' ? basis.currentTurn.agent_settings_proposal : null });
      App.agentDelegation?.project(basis.currentTurn?.agent_settings?.policy?.delegation ? {
        chatId: basis.chatId, turnId: basis.turnId || basis.currentTurn?.id,
        usage: basis.currentTurn?.agent_usage, running: basis.currentTurn?.status === "pending",
        models: reviewModels(basis.currentTurn?.agent_review), workLog: Boolean(basis.currentTurn?.agent_work_log) } : null);
    }
    if (!agent || (!context && !basis)) {
      markLiveTurn(null);
      App.agentDelegation?.project(null);
      // A saved Consensus turn or a new chat: no check of a pasted text.
      App.passageCheck?.apply(document.getElementById("agentAnswerBody"), null);
      App.agentWatch?.render(document.getElementById("agentAnswerBody"), {});
      App.watch?.answerButton?.(document.getElementById("agentAnswerBody"), {});
      App.answerShare?.button?.(document.getElementById("agentAnswerBody"), {});
      App.agentSettings?.render(document.getElementById("agentAnswerBody"), {});
    }
    window.updateQuestionInputAccess?.();
    syncPendingReview();
  }
  // The models a saved turn compared, from its review: its icons stand at
  // once, before the activity list loads (agent-delegation.js, Apple audit A10).
  function reviewModels(review) {
    const models = new Map();
    for (const comparison of review?.comparisons || []) {
      for (const answer of comparison.answers || []) {
        const label = answer.model?.label || answer.provider_label || answer.provider;
        const key = answer.model?.model || label;
        if (key && !models.has(key)) models.set(key, { model: { model: answer.model?.model, label, provider: answer.provider } });
      }
    }
    return [...models.values()];
  }
  // Links become the same source pills the finished answer shows while their
  // block streams in. Turning them into pills only when the check arrived
  // re-wrapped every cited paragraph the reader was already in. Pills show a
  // host, so their width does not depend on the final source numbering.
  function streamSourcePills(holder) {
    const sources = [...holder.querySelectorAll('a[href]')]
      .filter(link => !link.closest('code, pre, .katex') && !link.querySelector('img, svg'))
      .map(link => ({ url: link.getAttribute('href'), title: link.textContent }));
    if (sources.length) window.linkifyAgentSources?.(holder, sources);
  }
  // While a run streams, only the growing last Markdown block is parsed again
  // (markdown-stream.js). Once the text is fixed it is rendered in full, like
  // a saved answer, so review markers and cross-block Markdown are exact.
  // Both morph into the nodes on screen: a link in the answer stays the same
  // link and a selection stays (Apple audit D4, A6). Where it can draw,
  // stream-reveal.js paces the streamed text and brings its letters into
  // view; the full render then follows its last word.
  function renderAnswerBody(body, text, mode) {
    if (!body) return;
    // The run ends with the same text the review already rendered in full
    // with its claim marks: switching to 'full' must keep that DOM. Rendering
    // it again dropped every mark and rebuilt it, a visible flicker.
    if (mode === 'full' && body.dataset.markdown === text && body.dataset.renderMode === 'stream'
        && body._markSignature && body.querySelector('.cx-claim')) {
      body.dataset.renderMode = mode;
      window.resetMarkdownStream?.(body);
    }
    if (body.dataset.markdown === text && body.dataset.renderMode === mode) return;
    const entering = !body.dataset.markdown?.trim() && Boolean(text.trim());
    // Provisional marks the reader saw belong to one text (agent-review.js).
    if (body.dataset.markdown !== text) body._shownMarks = null;
    body.dataset.markdown = text;
    body.dataset.renderMode = mode;
    const reveal = App.streamReveal?.active() ? App.streamReveal : null;
    if (mode === 'stream') {
      const paint = shown => window.renderMarkdownStream(body, shown, { decorate: streamSourcePills });
      if (reveal) reveal.stream(body, text, paint);
      else paint(text);
    } else if (window.morphMarkdown) {
      const morph = () => window.morphMarkdown(body, text, { decorate: streamSourcePills });
      const full = () => (window.keepTextSelection ? window.keepTextSelection(body, morph) : morph());
      if (reveal) {
        // A full render that follows the paced words comes after the review
        // set its marks and source pills on the paced text, and replaces
        // them: the view is projected again once it stands, after the reveal
        // measured it, so no letter comes in twice.
        let later = false;
        reveal.settle(body, text, () => {
          full();
          if (!later) return;
          body._agentRenderSerial = (body._agentRenderSerial || 0) + 1;
          queueMicrotask(() => registry.renderVisible());
        });
        later = true;
      } else full();
    } else {
      window.resetMarkdownStream?.(body);
      window.injectMarkdown?.(body, text, []);
    }
    // A new render has no claim marks; the review renderer re-applies them.
    body._agentRenderSerial = (body._agentRenderSerial || 0) + 1;
    // Animate the start of an answer once, never each streamed text chunk;
    // paced text comes into view letter by letter instead.
    if (!text.trim()) body._agentReveal?.cancel();
    else if (entering && !(reveal && mode === 'stream')) body._agentReveal = App.agentActivity?.reveal(body, { lift: false });
  }
  function renderAnswer(text, error, { streaming = false } = {}) {
    renderAnswerBody(document.getElementById("agentAnswerBody"), text,
      streaming && window.renderMarkdownStream ? 'stream' : 'full');
    renderError(typeof error === 'string' ? { text: error } : error);
  }
  // While the judges check the fixed answer a quiet sheen passes over it, so
  // the reader sees below the fold that something is still happening. It
  // fades out instead of switching off when the marks arrive. Where the
  // evidence row will stand, one quiet line says it in words: the only sign
  // with reduced motion or forced colors, and as tall as that row, so the row
  // takes its place in the same frame without a jump (agent-chat.css).
  // In audit mode the reviewers do it, in the activity's words (agent-activity.js
  // reviewStage): one word for one state on screen at a time.
  function setAnswerChecking(body, checking, { fade = true, audit = false } = {}) {
    const words = audit ? 'Reviewing the answer…' : App.words?.checking || 'Checking the answer…';
    // Announced before the review said its mode: the line takes the review's words.
    if (checking && body?._checkStatus && body._checkStatus.textContent !== App.t(words)) body._checkStatus.textContent = words;
    if (!body || body.classList.contains('is-answer-checking') === checking) return;
    body.classList.toggle('is-answer-checking', checking);
    clearTimeout(body._answerCheckFade);
    body.classList.toggle('is-answer-check-done', !checking && fade);
    if (!checking && fade) body._answerCheckFade = setTimeout(() => body.classList.remove('is-answer-check-done'), 450);
    body._checkStatus?.remove();
    body._checkStatus = null;
    if (!checking) return;
    const line = document.createElement('p');
    // Audit: as tall as the review's row (no score line above it on a phone).
    line.className = audit ? 'agent-check-status is-audit' : 'agent-check-status';
    line.setAttribute('role', 'status');
    line.textContent = words;
    // Under the answer's pictures, where the evidence row will stand.
    (App.answerTail?.(body) || body).after(line);
    body._checkStatus = line;
    App.agentActivity?.reveal(line, { lift: false });
  }
  function renderError(error) {
    const errorEl = document.getElementById("agentAnswerError");
    const actionsEl = document.getElementById('agentAnswerErrorActions');
    const text = error?.text || '';
    if (errorEl) {
      if (errorEl.textContent !== window.App.t(text)) errorEl.textContent = text;
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
  // Local reset time for the UTC-day allowance, e.g. "02:00".
  function resetTime() {
    const next = new Date(); next.setUTCHours(24, 0, 0, 0);
    return App.format.time(next);
  }
  const BOOKMARK_FAILURES = new Set(['bookmark_count_limit', 'bookmark_storage_limit', 'bookmark_too_large', 'bookmark_unavailable']);
  // Budget refusals carry a stable code; show a plain next step in the
  // reader's unit, the allowance, never ledger terms (Apple-Audit H4).
  function failureNotice(failure, review, text, { retry = true } = {}) {
    const code = failure?.code || failure?.error_code;
    if (code === 'agent_token_reservation') {
      return { text: 'Not enough of today’s allowance is left for this step. '
        + `Try a smaller model or fewer comparison models, or wait for the reset at ${resetTime()}.`,
      actions: [['choose-model', 'Try a smaller model'], ['compare', 'Choose models']] };
    }
    if (code === 'agent_tokens_exhausted') return { text: `You’ve used today’s allowance. It resets at ${resetTime()}.` };
    // A pause nobody decided (A-R4): why it stopped, also under a partial answer.
    if (code === 'hold_timeout') {
      return { text: 'Stopped after 30 minutes without your decision.', actions: retry ? [['retry', 'Retry']] : [] };
    }
    // The answer is complete; only its sidebar entry was not saved. Said even
    // under a checked answer, which failureNote treats as settled: the
    // reader must know to free space and recover it (2026-10-19).
    if (BOOKMARK_FAILURES.has(code)) return { text: failure.error || failure.message || '' };
    const note = App.agentReview?.failureNote?.(failure, review, text);
    // Any other stop (provider busy, timeout, lost connection) can be sent
    // again as it was; a busy model can also be swapped first. A refusal of
    // the request itself (agent_provider_limits) would fail again unchanged.
    const repeats = ['conversation_too_long', 'file_unavailable', 'provider_rejected', 'model_declined'].includes(code);
    const actions = retry && !repeats ? [['retry', 'Retry']] : [];
    // A refused request names the way out itself: another chat model.
    if (['provider_rate_limited', 'provider_unavailable', 'provider_rejected', 'model_declined'].includes(code)) actions.push(['choose-model', 'Choose another model']);
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
    window.projectAgentModeRun?.(null);
    // First the history, while the live surface still shows the turn this
    // run continues: that turn moves up into the history as it is.
    const history = document.getElementById("threadHistory");
    // Agent history is fixed for a run after its initial previous-turn append.
    // Avoid serializing and duplicating all saved reasoning in a DOM attribute
    // on every streamed activity update.
    const signature = `${context.runId}:${context.historyTurns.length}`;
    if (history && history.dataset.agentHistory !== signature) {
      App.followup?.renderStoredTurns?.(context.historyTurns, { adopt: liveTurn });
      history.dataset.agentHistory = signature;
    }
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
    return true;
  }
  // The live surface as the page first had it (#threadAsk, #agentAnswer and
  // their IDs, a JS contract). When a follow-up starts, the turn on screen
  // moves into the history as it is: the same nodes, with what the reader
  // opened, the cards under it and its marks (Apple audit A4); a fresh copy
  // of the live surface takes its place for the new message. Rebuilding the
  // turn instead shifted it sideways, closed "Thought for …" and let its
  // logos fly in again.
  const pristine = { ask: null, answer: null };
  function capturePristine() {
    pristine.ask ||= document.getElementById("threadAsk")?.cloneNode(true) || null;
    pristine.answer ||= document.getElementById("agentAnswer")?.cloneNode(true) || null;
  }
  capturePristine();
  // Which turn the live surface shows, in the history's own key
  // (thread-history.js turnKey); only that turn can move up.
  function markLiveTurn(turn) {
    const panel = document.getElementById("agentAnswer");
    if (!panel) return;
    const key = turn && App.followup?.turnKey?.(turn);
    if (key) panel.dataset.turnKey = key;
    else delete panel.dataset.turnKey;
  }
  const liveTurn = {
    owns(turn) {
      const panel = document.getElementById("agentAnswer"), ask = document.getElementById("threadAsk");
      return Boolean(pristine.ask && pristine.answer && panel && ask && !panel.hidden && !ask.hidden
        && panel.dataset.turnKey && panel.dataset.turnKey === App.followup?.turnKey?.(turn));
    },
    take(turn) {
      const panel = document.getElementById("agentAnswer"), ask = document.getElementById("threadAsk");
      const contract = new Set([pristine.ask, pristine.answer].flatMap(root => [root, ...root.querySelectorAll("[id]")]).map(el => el.id));
      // Its model icons stay with it (agent-delegation.js) and open its answers.
      App.agentDelegation?.release?.();
      const freshAsk = pristine.ask.cloneNode(true), freshPanel = pristine.answer.cloneNode(true);
      freshPanel.hidden = false;
      ask.replaceWith(freshAsk);
      panel.replaceWith(freshPanel);
      // Retry, "Choose another model" and "Recover saved answer" act on the
      // run on screen: the turn in the history keeps its words, not these
      // buttons (review B2; a saved failure there reads as one, thread-history.js).
      panel.querySelector("#agentAnswerErrorActions")?.remove();
      panel.querySelector("#agentRecover")?.remove();
      for (const el of [ask, ...ask.querySelectorAll("[id]"), panel, ...panel.querySelectorAll("[id]")]) {
        if (contract.has(el.id)) el.removeAttribute("id");
      }
      ask.classList.add("thread-history-question");
      ask.querySelector(".thread-ask-text")?.classList.add("thread-history-question-text");
      panel.classList.add("thread-history-answer");
      panel.removeAttribute("aria-label");
      delete panel.dataset.turnKey;
      const node = document.createElement("article");
      node.className = "thread-history-turn is-agent-turn";
      const turnId = String(turn.turn_id || turn.id || "").trim();
      if (turnId) node.dataset.turnId = turnId;
      node.dataset.turnKey = App.followup.turnKey(turn);
      node.append(ask, panel);
      return node;
    },
  };
  function project(context) {
    renderShell();
    const framed = projectFrame(context);
    const state = context.consensus;
    const running = registry.isExecuting(context.runId);
    const failure = state.error || state.completedTurn?.agent_failure;
    // A message refused before it started is back in the composer instead.
    const retry = !running && context.metadata.requestSent && !context.metadata.restoreDraft;
    // The streamed text is fixed once the review holds it as a version: from
    // then on it is shown in full, so an answer that ends in a table shows
    // the table while the judges still check it.
    const settled = running && !state.text && Boolean(state.streamText)
      && Boolean(context.metadata.agentReview?.versions?.some(version => version?.text === state.streamText));
    // Its checklists can be ticked once the answer is saved as a turn.
    const savedTurn = !running && state.completedTurn?.status === 'completed' ? state.completedTurn : null;
    App.taskChecks?.scope(document.getElementById("agentAnswerBody"), { chatId: context.metadata.chatId,
      turnId: savedTurn ? savedTurn.id || savedTurn.turn_id : '', checked: savedTurn?.task_checks });
    renderAnswer(state.text || state.streamText || "", failure ? failureNotice(failure,
      state.completedTurn?.agent_review || context.metadata.agentReview, running ? "" : state.text || state.streamText || "", { retry }) : "",
      { streaming: running && !state.text && !settled });
    // A finished turn is what the next message continues (setCompletedBasis).
    markLiveTurn(running ? null : state.completedTurn);
    // A message that never left (offline, refused before it started) is
    // back in the box and says so: no "Failed after 0s" above that line.
    const unsent = !running && context.status === "failed" && !context.metadata.requestSent;
    if (unsent) activityHost(`${context.runId}:unsent`);
    else App.agentActivity?.render(activityHost(context.runId), {
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
      highlights: running ? App.agentDelegation?.liveHighlights?.(context.metadata.chatId, context.metadata.agentTurnId) : [],
      reconnecting: context.metadata.reconnecting === true && context.metadata.offline === true,
    });
    // Evidence links and Copy belong to a finished answer. While the run
    // streams they are only cleared once, when this run takes over the view.
    // A checked answer shows its marks at once, even while the run still
    // finishes: waiting for the end of the run made them appear late.
    const answerBody = document.getElementById("agentAnswerBody");
    const liveReview = context.metadata.agentReview;
    const shownText = state.text || state.streamText || '';
    const fixed = running && Boolean(shownText.trim()) && Boolean(liveReview?.versions?.length);
    // The server announces the check of exactly the text on screen the moment
    // its last word stands (answer_check), before the review holds it as a
    // version: the check shows from then on. A text taken back or changed
    // since drops the announcement.
    if (context.metadata.answerCheckText && context.metadata.answerCheckText !== shownText) context.metadata.answerCheckText = null;
    const announced = running && !fixed && Boolean(shownText.trim()) && context.metadata.answerCheckText === shownText;
    // With the answer check off the run's fixed answer passes "required" on
    // its way to "off" for a moment; nothing is checked, so no sheen.
    const checking = announced || (fixed && context.config.agentPreferences?.judges !== 'off'
      && ['required', 'running'].includes(liveReview.status));
    // "off": the answer check is switched off, the fixed answer is final.
    const checked = fixed && ['succeeded', 'partial', 'off'].includes(liveReview.status);
    setAnswerChecking(answerBody, checking, { audit: liveReview?.mode === 'audit'
      || (!liveReview && context.config.agentPreferences?.audit === 'on') });
    if (checking) context.metadata.revealMarks = true;
    // In audit mode the row under the fixed answer stands while the reviewers
    // work, Notes waiting and Sources already counted (agent-review.js; UX
    // audit B3): the end of the review changes a word, not the row.
    const reviewing = fixed && liveReview?.mode === 'audit';
    if (!running || framed || checked || reviewing) {
      const live = running && !checked && !reviewing;
      App.agentReview?.render(answerBody, live ? null : state.completedTurn?.agent_review || liveReview,
        { sources: state.completedTurn?.sources, events: live ? [] : state.completedTurn?.agent_activity || context.metadata.agentActivity,
          key: state.completedTurn?.id || context.runId, question: context.question, reveal: Boolean(context.metadata.revealMarks) });
    }
    // Sentences whose Coverage window is done are marked quietly while the
    // check still waits for Differences (coverage_preview); the final review
    // replaces them, and without a check they come off again.
    if (running && !checked) App.agentReview?.preview?.(answerBody, checking ? liveReview : null,
      context.metadata.coveragePreview, { sources: state.completedTurn?.sources, events: context.metadata.agentActivity,
        key: context.runId, question: context.question });
    // A pasted text the Agent checks: "Checking ..." above the answer while
    // the models answer, the result card as soon as the check is in.
    App.passageCheck?.apply(answerBody, state.completedTurn?.agent_review || liveReview, { live: running });
    // Memory changes appear as soon as Agent made them, not only at the end.
    App.agentMemory?.render(answerBody, { key: context.runId, running,
      changes: state.completedTurn?.agent_memory || context.metadata.agentMemory || [] });
    App.agentMemory?.nudge(answerBody, { key: context.runId,
      finished: !running && state.completedTurn?.status === 'completed', memory: state.completedTurn?.agent_settings?.memory });
    // A Watch the Agent prepared: its card under the completed answer that points to it.
    App.agentWatch?.render(answerBody, { key: context.runId,
      proposal: !running && state.completedTurn?.status === 'completed' ? state.completedTurn.agent_watch : null });
    // The same Watch pill as under a Consensus answer, on every finished
    // answer (watch.js; Apple-Audit J20). It is not the Agent offering one:
    // a prepared Watch has its card instead, and a follow-up opens at its
    // question so the watched question stands on its own.
    App.watch?.answerButton?.(answerBody, { question: context.question,
      eligible: !running && state.completedTurn?.status === 'completed' && !state.completedTurn?.agent_watch,
      followUp: context.historyTurns.length > 0 });
    // Share beside it, for every finished answer (share-dialog.js).
    App.answerShare?.button?.(answerBody, { chatId: context.metadata.chatId, turnId: state.completedTurn?.id,
      eligible: !running && state.completedTurn?.status === 'completed' && Boolean(String(state.text || '').trim()) });
    // A settings change the Agent prepared: its card, applied with one click.
    // Keyed like the saved chat's view (chat:turn), so applying or dismissing
    // holds when the chat is opened again.
    App.agentSettings?.render(answerBody, {
      key: context.metadata.chatId && state.completedTurn?.id ? `${context.metadata.chatId}:${state.completedTurn.id}` : context.runId,
      proposal: !running && state.completedTurn?.status === 'completed' ? state.completedTurn.agent_settings_proposal : null });
    App.syncSendButtonRunning?.();
    if (!running) syncPendingReview();
    const delegated = context.metadata.delegation || state.completedTurn?.agent_settings?.policy?.delegation;
    // Before the server named the new turn, a chat whose activity panel is
    // open keeps it open, waiting (agent-delegation.js, Apple audit A9).
    // Audit mode writes a work log (admins only, agent-work-log.js).
    const workLog = Boolean(state.completedTurn?.agent_work_log)
      || (context.config.agentPreferences?.audit === "on" && document.body.classList.contains("viewer-can-audit"));
    App.agentDelegation?.project(delegated ? { chatId: context.metadata.chatId,
      turnId: state.completedTurn?.id || context.metadata.agentTurnId,
      usage: state.completedTurn?.agent_usage || context.metadata.agentUsage, running, workLog }
      : running ? { chatId: context.metadata.chatId || context.basis?.chatId, running: true } : null);
  }
  // A refusal's sentence (the server's {error, code}), or one of ours; never
  // the engine's words (App.userError, app-text.js).
  function apiError(data) {
    return App.userError(data && typeof data === "object" ? data : String(data || ""),
      { fallback: "The answer couldn’t be completed. Try again." });
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
  // Besides its Watch pill, a finished answer may offer to keep itself
  // current (watch.js owns the card, the counter and "dismissed"). Only a
  // first message qualifies, because a watch re-asks the bare question, and
  // only one built on sources, because those are what can change. A turn
  // whose Agent already prepared a Watch has its own card (agent-watch.js).
  function offerWatch(context) {
    if (!registry.isVisible(context.runId) || !registry.isAuthCurrent(context)) return;
    const turn = context.consensus.completedTurn;
    App.watch?.showFeatureNudge?.({
      eligible: turn?.status !== "failed" && context.historyTurns.length === 0 && !turn?.agent_watch
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
          agent_preferences: context.config.agentPreferences || { depth: "auto", quorum: "all", autonomy: "guided", judges: "on" },
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
      App.showPopup?.(App.userError(error, { fallback: "The saved answer couldn’t be loaded. Try again." }));
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
  // A comparison needs two models; in audit mode they review the work, and
  // one is enough (agent-preferences.js auditing).
  function comparisonMinimum() { return App.agentPreferences?.auditing?.() ? 1 : 2; }
  function comparisonLimit() { return Number(App.maxRunFamilies) > 0 ? Number(App.maxRunFamilies) : 6; }
  function comparisonRequirement(suffix) {
    const limit = comparisonLimit();
    return comparisonMinimum() === 1
      ? (suffix === 'send' ? `Select between one and ${limit} reviewers to send your message.` : `Select between one and ${limit} reviewers before sending.`)
      : (suffix === 'send' ? `Select between two and ${limit} comparison models to send your message.` : `Select between two and ${limit} comparison models before sending.`);
  }
  function hasValidComparisonSelection(value = comparisonSelection()) {
    const models = Object.values(value);
    return models.length >= comparisonMinimum() && models.length <= comparisonLimit()
      && models.every(id => typeof id === 'string' && id.trim());
  }
  function sendBlocker() {
    if (!canUse()) return { message: 'Log in to use Agent.' };
    if (catalogStatus === 'failed') return { message: 'Chat models could not be loaded. Retry to continue.' };
    if (catalogStatus !== 'ready') return { message: 'Loading chat models… You can already write your message.', loading: true };
    if (!catalog.models.some(model => model.available !== false)) {
      return { message: 'No chat models are available right now. Try reloading the model list.', action: 'reload', label: 'Reload models' };
    }
    if (!hasValidComparisonSelection()) {
      return { message: comparisonRequirement('send'), action: 'compare', label: 'Choose models' };
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
      const text = !count ? '' : count === 1 ? '1 item needs your review' : `${count} items need your review`;
      const message = document.getElementById('agentReviewMessage');
      if (message && message.textContent !== window.App.t(text)) message.textContent = text;
    }
    // Bookmark dot and tab title follow the conversation on screen.
    const context = registry.visible();
    const basis = registry.getSelectedConversationBasis({ includeHistory: false });
    const bookmarkId = context?.bookmark.id || basis?.bookmarkId;
    document.querySelectorAll('.bookmark.needs-review').forEach(row => {
      if (count && row.dataset.id === bookmarkId) return;
      row.classList.remove('needs-review');
      if (row.title === window.App.t('Needs review')) row.removeAttribute('title');
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
    else if (action === 'status-retry') App.retryAccountStatus?.();
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
    if (++stall.misses >= 2) throw Object.assign(new Error('The connection is taking too long. Try again.'), { name: 'TimeoutError' });
    return undefined;
  }
  function syncComposer() {
    renderQueue();
    renderHold();
    const agent = selectedMode() === 'agent';
    const running = registry.isExecuting(registry.visible()?.runId);
    // Nothing stands in a guest's way: Send asks for the login (composer-invite.js).
    const blocker = running || guest() ? null : agent ? sendBlocker() : expectingAgent() ? accessBlocker() : null;
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
    if (message && message.textContent !== window.App.t(blocker?.message || '')) message.textContent = blocker?.message || '';
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
    // Until access is known, a session expected in Agent keeps Agent's words
    // (seeded before the first paint in app-bootstrap.js), as the greeting does.
    if (!looksAgent() || window.userCanAskQuestions?.() === false) return;
    const basis = registry.getSelectedConversationBasis({ includeHistory: false });
    // While a card waits above it, the field says what it does now (UX audit
    // 2026-10-29 C3, C11): words go to the agent with the card's answer
    // (steer), or, for a key, into the card's key field. Short enough for
    // a phone beside the reviewers (H2: "Write your next message…" ended
    // mid-word). A new chat names the one thing nobody would guess: a pasted
    // AI answer gets checked (the Agent decides; there is no extra mode or
    // button).
    input.placeholder = running ? runningPlaceholder(openHold(registry.visible())) : basis?.chatId && !basis.continuationUnavailable
      ? 'Ask a follow-up' : App.askPlaceholder?.() ?? input.placeholder;
  }
  function runningPlaceholder(hold) {
    return hold?.ask === 'secret' ? 'Paste the key above' : hold ? 'Or write to the agent…' : 'Message the agent…';
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
  // A turn keeps running on the server when this page goes away (reload, a
  // phone that discarded the tab). Its identity stays in this tab's session
  // storage until the page saw the turn end, so a reload can follow it again.
  // Long enough for a long VM run (2 h) with a pause for the user (30 min).
  const PENDING_MAX_AGE_MS = 3 * 60 * 60 * 1000;
  let resumedFor = '';
  function pendingKey(uid) { return `agent_pending_runs_${uid}`; }
  function readPending(uid) {
    try {
      const list = JSON.parse(sessionStorage.getItem(pendingKey(uid)) || '[]');
      return Array.isArray(list) ? list.filter(item => item && typeof item === 'object' && item.body
        && Date.now() - Number(item.at) < PENDING_MAX_AGE_MS) : [];
    } catch (_) { return []; }
  }
  function writePending(uid, list) {
    try {
      if (list.length) sessionStorage.setItem(pendingKey(uid), JSON.stringify(list));
      else sessionStorage.removeItem(pendingKey(uid));
    } catch (_) { /* private mode: no resume after reload */ }
  }
  // The date in the agent's context follows the user's device, not the app's zone.
  function deviceTimezone() {
    try { return Intl.DateTimeFormat().resolvedOptions().timeZone || null; } catch (_) { return null; }
  }
  function rememberPending(context, body) {
    const uid = context.auth.uid;
    if (!uid) return;
    const list = readPending(uid).filter(item => item.body.client_request_id !== body.client_request_id);
    const queue = queueOf(context).map(item => ({ text: item.text, state: item.state }));
    list.push({ at: Date.now(), body, title: context.bookmark.title, followup: Boolean(context.basis),
      settings: context.metadata.agentSettings || null, attachmentMeta: context.attachmentMeta || [],
      ...(queue.length ? { queue } : {}) });
    writePending(uid, list.slice(-4));
  }
  function forgetPending(context) {
    const uid = context.auth.uid;
    if (!uid) return;
    const list = readPending(uid);
    const rest = list.filter(item => item.body.client_request_id !== context.requestIdentity);
    if (rest.length !== list.length) writePending(uid, rest);
  }
  function markPendingStop(context) {
    const uid = context.auth.uid;
    if (!uid) return;
    const list = readPending(uid);
    const item = list.find(entry => entry.body.client_request_id === context.requestIdentity);
    if (!item) return;
    item.stop = true;
    writePending(uid, list);
  }
  // The VM back to how it was before this message (routers/agent.py
  // restore_agent_vm, admins): asked first, since later changes are lost.
  async function restoreVm(chatId, turnId) {
    const confirmed = await App.confirm?.({ title: "Restore the workspace?", danger: true, confirmLabel: "Restore",
      body: "Your workspace goes back to how it was before this message: every chat’s folder and the browser with the sites it is logged in to. Everything changed there since is lost, and running background processes stop." });
    if (!confirmed) return;
    let message = "The workspace is back to how it was before this message.";
    try {
      const token = await window.auth.currentUser.getIdToken();
      const response = await fetch(`/agent/chats/${encodeURIComponent(chatId)}/turns/${encodeURIComponent(turnId)}/vm-restore`,
        { method: "POST", headers: { Authorization: `Bearer ${token}` } });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        message = data.error || "The workspace could not be restored.";
      }
    } catch (_) {
      message = "The workspace could not be restored. Check your connection.";
    }
    App.showPopup?.(message);
  }
  // A message typed while a response runs (Enter or Send, app-init.js,
  // query-send.js): never lost, always on screen (2026-10-26; before, it
  // went nowhere without the VM and showed nothing until the agent read it).
  // A run that reads messages (Agent VM, routers/agent.py add_agent_note)
  // takes it before its next step, like typing to Claude Code while it works;
  // the activity then shows it under "You". Any other waits in the queue
  // above the field and goes out as the next message once the response is
  // done. Stop or a failure puts it back in the field.
  let queueSerial = 0;
  function queueOf(context) {
    return context?.metadata ? (context.metadata.queue ||= []) : [];
  }
  // The waiting messages live in the run's pending record too, so a reload
  // keeps them (A-B4; before, they lived only in memory, also everything
  // typed during the final review): what the run did not read goes out after
  // it, as without a reload. Called after every change of the queue.
  function persistQueue(context) {
    const uid = context?.auth?.uid;
    if (!uid) return;
    const list = readPending(uid);
    const record = list.find(entry => entry.body.client_request_id === context.requestIdentity);
    if (!record) return;
    const queue = queueOf(context).map(item => ({ text: item.text, state: item.state,
      ...(item.noteId ? { noteId: item.noteId } : {}) }));
    if (JSON.stringify(record.queue || []) === JSON.stringify(queue)) return;
    if (queue.length) record.queue = queue;
    else delete record.queue;
    writePending(uid, list);
  }
  // After a reload. A message whose POST was on its way (no id came back)
  // may have reached the run: it waits like a delivered one and is known by
  // its words once the run reads it (delivered), else it goes out after.
  function restoreQueue(saved) {
    return (Array.isArray(saved) ? saved : [])
      .filter(item => item && typeof item.text === "string" && item.text.trim()).slice(0, 20)
      .map(item => {
        const noteId = typeof item.noteId === "string" && item.noteId ? item.noteId : null;
        const unsure = item.state === "sending";
        return { key: ++queueSerial, text: item.text, state: noteId || unsure ? "waiting" : "queued",
          ...(noteId ? { noteId } : {}), ...(unsure && !noteId ? { unsure: true } : {}) };
      });
  }
  // Once the answer is fixed (a version under review) the run takes no more
  // steps: a message then waits for its end like any other (2026-10-27;
  // before, it went to the run as "Read before the next step" and came back
  // only when the review was done).
  function readsMessages(context) {
    return (context?.config?.agentPreferences?.audit === "on" || context?.config?.agentPreferences?.vm === "on")
      && !context?.metadata?.agentReview?.versions?.length;
  }
  // What Send does now: null when it stops the response (an empty field).
  function steering() {
    const context = registry.visible();
    const text = String(document.getElementById("questionInput")?.value || "").trim();
    if (selectedMode() !== "agent" || !context || !registry.isExecuting(context.runId) || !text) return null;
    const hold = openHold(context);
    return { title: hold?.ask === "secret" ? "Into the key field"
      : hold ? "Send to the agent and let it go on"
      : readsMessages(context) ? "Send into the running response" : "Send after this response" };
  }
  async function steer() {
    const context = registry.visible();
    const input = document.getElementById("questionInput");
    if (!steering() || !input) return false;
    const text = String(input.value).trim();
    // The agent asked for a key and its card is open (A-S7): the field never
    // sends a message then (its placeholder says so, C11). Its words go, as
    // dots, into the card's key field, the card says so for a moment, and
    // the user saves them there or answers "Not now". Only the open card
    // decides, nothing guesses at the words: a key someone writes into a
    // message unasked stays a message.
    const open = openHold(context);
    if (open?.ask === "secret") {
      const field = document.querySelector("#agentHold .agent-ask-secret-input");
      if (!field || field.disabled) return true;
      field.value = text;
      input.value = "";
      input.dispatchEvent(new Event("input", { bubbles: true }));
      open.failed = "";
      open.movedUntil = Date.now() + MOVED_NOTE_MS;
      renderHold();
      field.focus({ preventScroll: true });
      return true;
    }
    input.value = "";
    input.dispatchEvent(new Event("input", { bubbles: true }));
    if (openHold(context)) {
      // Paused by a reviewer: the message is the decision (renderHold).
      if (!(await decideHold(context, "steer", text)) && !input.value.trim()) {
        input.value = text;
        input.dispatchEvent(new Event("input", { bubbles: true }));
      }
      return true;
    }
    const item = { key: ++queueSerial, text, state: "queued" };
    queueOf(context).push(item);
    persistQueue(context);
    renderQueue();
    if (readsMessages(context)) await deliver(context, item);
    return true;
  }
  async function deliver(context, item) {
    const chatId = context.metadata.chatId;
    // Before the response has started, the message waits for its end.
    if (!chatId || !context.metadata.requestSent) return;
    item.state = "sending";
    persistQueue(context);
    renderQueue();
    const url = `/agent/chats/${encodeURIComponent(chatId)}/requests/${encodeURIComponent(context.requestIdentity)}/notes`;
    try {
      const token = await window.auth.currentUser.getIdToken();
      const response = await fetch(url, { method: "POST", body: JSON.stringify({ text: item.text }),
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" } });
      const data = await response.json().catch(() => ({}));
      if (response.ok && data.id && context.metadata.readNotes?.includes(data.id)) {
        // Read before this answer arrived (delivered): done, never sent again.
        const queue = queueOf(context);
        if (queue.includes(item)) queue.splice(queue.indexOf(item), 1);
      } else if (response.ok && data.id) Object.assign(item, { state: "waiting", noteId: data.id });
      else item.state = "queued";
    } catch (_) {
      // Unreachable now: it goes out with the next message instead.
      item.state = "queued";
    }
    persistQueue(context);
    renderQueue();
  }
  // The activity showed the message under "You": the run has read it. Its
  // id comes with the step that read it ("completion:3/note-<id>",
  // agent_loop.activity); matched as "note-<id>" alone, a read message
  // stayed queued and went out again after the response. The run can read
  // it before this page has the POST's answer with the id: kept as read, so
  // deliver drops it then (before, it went out again as a new, paid message).
  function delivered(context, event) {
    const match = typeof event?.id === "string" ? /(?:^|\/)note-([^/]+)$/.exec(event.id) : null;
    if (!event?.from_user || !match) return;
    const queue = queueOf(context);
    let index = queue.findIndex(item => item.noteId === match[1]);
    // A message restored after a reload whose POST had no answer yet: its words.
    if (index < 0) index = queue.findIndex(item => item.unsure && item.text === String(event.text || "").trim());
    if (index >= 0) { queue.splice(index, 1); persistQueue(context); renderQueue(); }
    else (context.metadata.readNotes ||= []).push(match[1]);
  }
  // The response is over: what it did not read goes out now, or back into
  // the field when it stopped or failed.
  function flushQueue(context) {
    const queue = queueOf(context).splice(0);
    persistQueue(context);
    renderQueue();
    // An open pause ends with the response too.
    renderHold();
    if (!queue.length || !registry.isAuthCurrent(context)) return;
    const text = queue.map(item => item.text).join("\n\n");
    const input = window.document?.getElementById("questionInput");
    if (!input) return;
    // Another chat is open now: its field and its mode are not this
    // message's. Said, never sent there.
    const elsewhere = () => {
      const start = text.replace(/\s+/g, " ").trim();
      App.showPopup?.(App.t("Not sent: “{text}”. You had opened another chat before the response ended.",
        { text: start.length > 60 ? `${start.slice(0, 59)}…` : start }));
    };
    if (!registry.isVisible(context.runId)) { elsewhere(); return; }
    if (context.status === "succeeded" && !input.value.trim()) {
      setTimeout(() => {
        if (!registry.isVisible(context.runId)) { elsewhere(); return; }
        if (input.value.trim() || registry.isExecuting(registry.visible()?.runId)) return;
        input.value = text;
        input.dispatchEvent(new Event("input", { bubbles: true }));
        window.sendQuestion?.();
      }, 0);
      return;
    }
    // Older text first: a new draft follows the waiting message, the run's
    // own question (restoreUnsentDraft, refused before it started) leads it.
    const ownQuestion = context.metadata.draftRestored
      && input.value.trim() === String(context.metadata.draftQuestion || "").trim();
    input.value = !input.value.trim() ? text : ownQuestion ? `${input.value}\n\n${text}` : `${text}\n\n${input.value}`;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    App.showPopup?.(context.status === "succeeded" ? "Your waiting message is back in the field, before your new text."
      : "Your waiting message is back in the field: the response ended before it could take it.");
  }
  const queueLabels = { queued: "Sends after this response", sending: "Sending…", waiting: "Read before the next step" };
  function renderQueue() {
    if (!window.document?.body) return;
    const host = document.getElementById("agentQueue");
    if (!host) return;
    const context = registry.visible();
    const queue = selectedMode() === "agent" && context && registry.isExecuting(context.runId) ? queueOf(context) : [];
    const signature = JSON.stringify(queue.map(item => [item.key, item.state]));
    if (host.dataset.signature === signature) return;
    host.dataset.signature = signature;
    host.replaceChildren(...queue.map(item => {
      const row = document.createElement("div");
      row.className = "agent-queue-item";
      row.dataset.state = item.state;
      const text = document.createElement("span");
      text.className = "agent-queue-text";
      // The user's own words: never translated.
      text.dataset.i18nSkip = "";
      text.textContent = item.text;
      const state = document.createElement("span");
      state.className = "agent-queue-state";
      state.textContent = queueLabels[item.state];
      row.append(text, state);
      if (item.state === "queued") {
        const remove = document.createElement("button");
        remove.type = "button";
        remove.className = "close-button agent-queue-remove";
        remove.setAttribute("aria-label", "Remove waiting message");
        remove.title = "Remove waiting message";
        remove.innerHTML = window.App?.closeIcon?.() || "";
        remove.addEventListener("click", () => {
          const index = queue.indexOf(item);
          if (index >= 0) queue.splice(index, 1);
          persistQueue(context);
          renderQueue();
          document.getElementById("questionInput")?.focus({ preventScroll: true });
        });
        row.append(remove);
      }
      return row;
    }));
    host.hidden = !queue.length;
  }
  // A reviewer paused the work for the user (agent_audit.py halt,
  // DelegationLoop.request_hold; since 2026-10-26): one card above the field
  // until the user decides. The agent never learns of it: going on changes
  // nothing for it, a message written now reaches it like any message
  // written while it works, and Stop is the Stop button. Without a decision
  // the response stops after timeout_seconds (30 min).
  // A pause with `gate` (since 2026-10-27, agent_gate.py) comes before a step
  // that acts outside the workspace runs: it runs only if the user lets it.
  // "unchecked": not every reviewer could answer for it (one that failed or
  // paused never counts as a go), so no reviewer and no reason.
  const holdKinds = { safety: "Security-critical step", harm: "Possible damage", off_goal: "Far off your request",
    injection: "Prompt injection", unchecked: "Not checked" };
  let holdTimer = null;
  // Every card names its deadline only in its last minutes, as the agent's
  // own questions did (UX audit 2026-10-29 C7): a reviewer's pause said
  // "Stops in 30 minutes" from its first second, a threat that did not count
  // for 25 minutes.
  const CLOCK_MINUTES = 5;
  // A move of the main field's words into the key field says so this long (C11).
  const MOVED_NOTE_MS = 6000;
  function openHold(context) {
    const hold = context?.metadata?.hold;
    return hold && registry.isExecuting(context.runId) && registry.isAuthCurrent(context) ? hold : null;
  }
  function holdClock(hold) {
    // The server's time, unless this clock runs behind it.
    const at = Date.parse(hold.at);
    const since = Number.isFinite(at) ? Math.min(at, hold.receivedAt) : hold.receivedAt;
    const left = since + (Number(hold.timeout_seconds) || 1800) * 1000 - Date.now();
    const minutes = Math.ceil(left / 60000);
    if (minutes > CLOCK_MINUTES) return "";
    // What happens then: the agent's own question goes on without an
    // answer, a domain stays closed and the work goes on (C8; the card said
    // "Stops"), a reviewer's pause stops the response.
    if (hold.ask) {
      return minutes > 1 ? App.t("The agent waits {count} more minutes", { count: minutes })
        : "The agent waits less than a minute more";
    }
    if (hold.domain) {
      return minutes > 1 ? App.t("Not allowed in {count} minutes without your decision", { count: minutes })
        : "Not allowed within a minute without your decision";
    }
    return minutes > 1 ? App.t("Stops in {count} minutes without your decision", { count: minutes })
      : "Stops within a minute without your decision";
  }
  // A decision's POST (…/hold, …/secret) within DECISION_TIMEOUT_MS: on a
  // half-open connection it hung for minutes, every button of the card
  // locked and nothing said so (A-B3). The pressed button says it is on its
  // way meanwhile (C13), and the Stop button beside the field stays a Stop.
  const DECISION_TIMEOUT_MS = 15000;
  async function postDecision(context, path, body) {
    const url = `/agent/chats/${encodeURIComponent(context.metadata.chatId)}/requests/${encodeURIComponent(context.requestIdentity)}/${path}`;
    let response = null, data = {};
    try {
      await App.withRequestDeadline(async signal => {
        const token = await window.auth.currentUser.getIdToken();
        response = await fetch(url, { method: "POST", body: JSON.stringify(body), signal,
          headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" } });
        if (!response.ok) data = await response.json().catch(() => ({}));
      }, { timeoutMs: DECISION_TIMEOUT_MS });
    } catch (_) { response = null; }
    return { response, data: data && typeof data === "object" ? data : {} };
  }
  // A refusal the user can act on says the server's own sentence (in their
  // language); anything else, a lost connection or an internal error, the
  // card's. In the card, where the user acted, not in a toast (C12: a
  // toast said "Internal error" and the card looked as before).
  const DECISION_REFUSALS = new Set(["notes_full", "invalid_action", "vm_unavailable"]);
  function refusal(data, fallback) {
    return DECISION_REFUSALS.has(data.code) && typeof data.error === "string" && data.error ? data.error : fallback;
  }
  async function decideHold(context, action, text = "") {
    const hold = openHold(context);
    if (!hold || hold.deciding) return false;
    hold.deciding = action;
    hold.failed = "";
    renderHold();
    const { response, data } = await postDecision(context, "hold", { id: hold.id, action, text });
    // Decided, or the response or the pause is over (decided in another tab,
    // A-B5): the card goes, the activity keeps the record.
    if (response && (response.ok || data.code === "not_running" || data.code === "hold_over")) {
      holdDone(context, hold);
      return true;
    }
    // Refused (no room for another message) or lost: the card stays until
    // the run says the pause is over, so a decision stays possible; the
    // Stop button beside the field always is.
    undecided(context, hold, refusal(data, "Your decision did not reach the server. Try again."));
    renderHold();
    return false;
  }
  // By the pause's id: the stream may have sent the same pause again
  // meanwhile, as a new object (hold.receive keeps its decision on the way).
  function holdDone(context, hold) {
    context.metadata.holdDecided = hold.id;
    if (context.metadata.hold?.id === hold.id) context.metadata.hold = null;
    renderHold();
    registry.update(context.runId, () => {});
  }
  function undecided(context, hold, failed = "") {
    hold.deciding = null;
    hold.failed = failed;
    if (context.metadata.hold?.id === hold.id) Object.assign(context.metadata.hold, { deciding: null, failed });
  }
  // The key the agent asked for (ask_user with secret, agent_secrets.py;
  // since 2026-10-29): it goes from this field to the workspace alone (POST
  // .../secret), never into the chat, and the field is no form, so nothing
  // ever sends it by GET. Saved, the server answers the card. A text area
  // whose letters show as dots, not a password field: Chrome offered to save
  // a password field's value as the account's password once it disappeared,
  // and a single line dropped the line breaks of a PEM key. Enter saves,
  // Shift+Enter starts a new line.
  async function saveSecret(context, input) {
    const hold = openHold(context);
    if (!hold || hold.deciding) return;
    if (!input.value.trim()) {
      input.focus();
      return;
    }
    hold.deciding = "secret";
    hold.failed = "";
    renderHold();
    const { response, data } = await postDecision(context, "secret", { id: hold.id, value: input.value });
    if (response && (response.ok || data.code === "not_running" || data.code === "hold_over")) {
      input.value = "";
      holdDone(context, hold);
      // Over before it was saved: the key did not go anywhere, and the user
      // hears so (the card is gone, so a toast says it).
      if (data.code === "hold_over" && typeof data.error === "string" && data.error) App.showPopup?.(data.error);
      return;
    }
    undecided(context, hold, refusal(data, "The key did not reach your workspace. Try again."));
    renderHold();
  }
  function secretField(context, hold) {
    const name = String(hold.secret || "");
    const field = document.createElement("div");
    field.className = "agent-ask-secret";
    const input = document.createElement("textarea");
    input.className = "agent-ask-secret-input";
    input.rows = 1;
    input.autocomplete = "off";
    input.spellcheck = false;
    input.setAttribute("autocapitalize", "off");
    input.setAttribute("autocorrect", "off");
    input.dataset.i18nSkip = "";
    input.placeholder = name;
    input.setAttribute("aria-label", App.t("Paste {name}", { name }));
    input.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" || event.shiftKey || event.isComposing) return;
      event.preventDefault();
      saveSecret(context, input);
    });
    const note = document.createElement("p");
    note.className = "agent-ask-secret-note";
    note.dataset.i18nSkip = "";
    note.textContent = App.t("Saved in your workspace as {path} for the agent’s commands, never in the chat. Only for keys like this one: a password you type in the browser yourself.",
      { path: `~/.secrets/${name}` });
    field.append(input, note);
    return field;
  }
  // Why the work waits, one line each (data-reason). A reviewer's pause: the
  // kind first, then the reviewer's own sentence (already in the user's
  // language) and, quietly after it, who said it (UX audit C10: the kind
  // stood once in a line of its own for all reasons, every name twice). A
  // domain request: what the reviewers made of it (no concern, their
  // concern, or that not every one could look). A second halt on the open
  // pause comes as the same pause with more `reasons` (A-S2): renderHold
  // swaps these lines and the title in place, so a decision on its way and
  // the words in the field stay.
  function holdReasons(hold) {
    return Array.isArray(hold.reasons) ? hold.reasons.filter(item => item && typeof item === "object") : [];
  }
  function holdCalls(hold) {
    return Array.isArray(hold.step_calls) ? hold.step_calls.filter(item => item && typeof item === "object") : [];
  }
  function reasonLines(hold) {
    const listed = holdReasons(hold);
    const said = item => {
      const line = document.createElement("p");
      line.className = "agent-hold-reason";
      line.dataset.reason = "";
      const kind = holdKinds[item.kind];
      if (kind && item.kind !== "unchecked") {
        const label = document.createElement("strong");
        label.className = "agent-hold-kind";
        label.textContent = kind;
        line.append(label, " ");
      }
      const text = document.createElement("span");
      text.className = "agent-hold-reason-text";
      text.dataset.i18nSkip = "";
      text.textContent = String(item.reason || "");
      line.append(text);
      if (item.reviewer) {
        const by = document.createElement("span");
        by.className = "agent-hold-by";
        by.dataset.i18nSkip = "";
        by.textContent = String(item.reviewer);
        line.append(" ", by);
      }
      return line;
    };
    const plain = text => {
      const line = document.createElement("p");
      line.className = "agent-hold-reason";
      line.dataset.reason = "";
      line.textContent = text;
      return line;
    };
    const own = { kind: hold.kind, reason: hold.reason, reviewer: hold.reviewer };
    if (hold.domain) {
      if (hold.review === "halt" || listed.length) return (listed.length ? listed : [own]).map(said);
      return [plain(hold.review === "go" ? "The reviewers see no problem with it." : "Not every reviewer could check this request.")];
    }
    // "unchecked": no reviewer paused it, none could answer for it; what the
    // step would do, in a sentence (C1: before, "It acts outside the
    // workspace", which a memory change does not). A reviewer that pauses on
    // it later stands under its name.
    if (hold.kind === "unchecked" && !listed.length) {
      return [plain(holdCalls(hold).some(call => call.tool === "update_memory")
        ? "The agent wants to remember something about you. That happens only with your OK."
        : "This step runs only with your OK.")];
    }
    return (listed.length ? listed : [own]).map(said);
  }
  function reasonsKey(hold) {
    return JSON.stringify([hold.reason || "", hold.review || "", holdReasons(hold).map(item => [item.reviewer || "", item.reason || ""])]);
  }
  // The title counts who paused (C10: two reviewers read "A reviewer paused
  // the work"). Whole sentences, so every language says them its way.
  function holdTitle(hold) {
    if (hold.kind === "unchecked") return "Not every reviewer could check this step";
    const count = Math.max(1, holdReasons(hold).length);
    if (hold.gate) {
      return count === 1 ? "A reviewer paused before a step" : count === 2 ? "Two reviewers paused before a step"
        : App.t("{count} reviewers paused before a step", { count });
    }
    return count === 1 ? "A reviewer paused the work" : count === 2 ? "Two reviewers paused the work"
      : App.t("{count} reviewers paused the work", { count });
  }
  // The button last pressed on a card: it says the decision is on its way.
  let pressedButton = null;
  function holdButton(label, className, onClick) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = className;
    button.textContent = label;
    if (onClick) button.addEventListener("click", event => { pressedButton = button; onClick(event); });
    return button;
  }
  // What a model step was about to do, in a sentence (agent_audit.halt_step
  // step_calls, C1): before, 'browser: {"action": "click", "ref": "e14"}'
  // and a memory change's whole JSON. The element as the browser's read
  // named it; the words are data. Any other call stays code ("").
  function callWords(call) {
    const text = String(call.text || ""), target = String(call.target || "");
    if (call.tool === "update_memory") {
      if (call.action === "delete") return App.t("Forget a memory");
      if (!text) return App.t("Change your memory");
      return call.action === "update" ? App.t("Change a memory: “{text}”", { text }) : App.t("Remember: “{text}”", { text });
    }
    if (call.tool !== "browser") return "";
    switch (call.action) {
      case "open": return text ? App.t("Opens {text}", { text }) : App.t("Uses the browser");
      case "click": return target ? App.t("Clicks “{target}”", { target }) : App.t("Clicks on the page");
      case "type":
        if (target) {
          return call.enter ? App.t("Types “{text}” into “{target}” and sends it", { text, target })
            : App.t("Types “{text}” into “{target}”", { text, target });
        }
        return call.enter ? App.t("Types “{text}” and sends it", { text }) : App.t("Types “{text}”", { text });
      case "select": return App.t("Chooses “{text}”", { text });
      case "key": return App.t("Presses {text}", { text });
      case "upload": return App.t("Uploads {text}", { text });
      case "download": return text ? App.t("Downloads {text}", { text }) : App.t("Downloads the file on the page");
      default: return App.t("Uses the browser");
    }
  }
  // Where the reviewer saw it, in the activity's words ("Browser",
  // "Memory", "In the file tabelle.csv"), and the words themselves
  // (agent_audit.halt_step: the reviewer's quote where the entry holds it).
  // A command or a file's rows stand in the code field and scroll inside it;
  // a cut line fades out (C17). A pause saved before 2026-10-27 has no
  // step_kind: "name: text".
  function holdEvidence(hold) {
    const box = document.createElement("figure");
    box.className = "agent-hold-evidence";
    const label = document.createElement("figcaption");
    label.className = "agent-hold-evidence-label";
    const kind = hold.step_kind;
    const calls = kind === "call" ? holdCalls(hold) : [];
    const tools = [...new Set(calls.map(call => String(call.tool || "")))];
    if (kind === "file" && hold.step_source) {
      label.dataset.i18nSkip = "";
      label.textContent = App.t("In the file {name}", { name: String(hold.step_source) });
    } else {
      label.textContent = kind === "result" ? App.agentActivity?.toolName?.(hold.step_name) || "Tool result"
        : tools.length === 1 && tools[0] ? App.agentActivity?.toolName?.(tools[0]) || "The agent’s step"
        : kind === "context" || kind === "file" ? "What the agent received"
        : hold.gate ? "The step that has not run yet" : "The agent’s step";
    }
    // The work log's number only for those who can open the log (admins).
    if (hold.entry) {
      const step = document.createElement("span");
      step.className = "admin-only";
      step.dataset.i18nSkip = "";
      step.textContent = ` · ${App.t("Step {entry}", { entry: hold.entry })}`;
      label.append(step);
    }
    box.append(label);
    const code = value => {
      const text = document.createElement("pre");
      text.className = "agent-hold-evidence-text";
      text.dataset.i18nSkip = "";
      text.textContent = value;
      return text;
    };
    if (!calls.length) {
      box.append(code(kind ? String(hold.step) : `${hold.step_name ? `${hold.step_name}: ` : ""}${hold.step}`));
      return box;
    }
    for (const call of calls) {
      const words = callWords(call);
      if (!words) { box.append(code(String(call.text || ""))); continue; }
      const line = document.createElement("p");
      line.className = "agent-hold-evidence-words";
      line.dataset.i18nSkip = "";
      line.textContent = words;
      box.append(line);
    }
    return box;
  }
  // A code field longer than it shows fades out at its cut instead of
  // ending in half a line, until it is scrolled to its end (C17).
  function fadeCut(field) {
    const cut = () => field.classList.toggle("is-cut", field.scrollTop + field.clientHeight < field.scrollHeight - 1);
    field.addEventListener("scroll", cut, { passive: true });
    cut();
  }
  // One family (UX audit 2026-10-29 C2): every card above the field is
  // built like the agent's own questions from the design pass of 2026-10-29
  // (438aacdc). Its glyph hangs in a tinted circle left of the words;
  // title, words, evidence and the decision share one edge. One filled
  // button and at most one link (C3): the field below takes a message to the
  // agent (steer: its placeholder says so while a card is open), and Stop is
  // the Stop button there. Before, the reviewers' and the domain's cards
  // were an older family with a meta line, up to three links beside the
  // button ("Write to the agent" opened a second field over the first, and
  // "Stop" stood above Stop) and a deadline from the first second.
  const holdGlyphs = {
    // Two bars: the work pauses.
    pause: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6.5v11M15 6.5v11" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round"></path></svg>',
    // A globe: an address on the web.
    domain: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8.5" fill="none" stroke="currentColor" stroke-width="2"></circle><path d="M3.5 12h17M12 3.5c2.6 2.4 3.6 5.4 3.6 8.5s-1 6.1-3.6 8.5c-2.6-2.4-3.6-5.4-3.6-8.5s1-6.1 3.6-8.5z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"></path></svg>',
    // A pointer: the user's hand in the browser.
    browser: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6.5 4.5l11 6.6-4.8 1.3 2.8 5.3-2.2 1.2-2.8-5.4-4 3.6z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"></path></svg>',
    // A question.
    confirm: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9.2 9.2a2.9 2.9 0 1 1 4.2 2.6c-.9.5-1.4 1.1-1.4 2v.6M12 17.6v.1" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"></path></svg>',
    // A key.
    secret: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="8" cy="15.5" r="3.6" fill="none" stroke="currentColor" stroke-width="2"></circle><path d="M10.6 12.9l7.4-7.4M15.2 8.3l2.3 2.3M17.4 6.1l1.9 1.9" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"></path></svg>',
  };
  function cardShell(className, glyph) {
    const card = document.createElement("section");
    card.className = `agent-hold-card ${className}`;
    card.setAttribute("aria-labelledby", "agentHoldTitle");
    const mark = document.createElement("span");
    mark.className = "agent-hold-glyph";
    mark.innerHTML = glyph;
    const body = document.createElement("div");
    body.className = "agent-hold-body";
    // Said once when it appears: the title and why (role=alert).
    const alert = document.createElement("div");
    alert.className = "agent-hold-alert";
    alert.setAttribute("role", "alert");
    const title = document.createElement("h2");
    title.id = "agentHoldTitle";
    title.className = "agent-hold-title";
    alert.append(title);
    body.append(alert);
    card.append(mark, body);
    return { card, body, alert, title };
  }
  // The card's one quiet line under its words: the deadline in its last
  // minutes, a decision that did not go through (C12), or what just
  // happened to the main field's words (C11). Said when it changes.
  function cardStatus() {
    const status = document.createElement("p");
    status.className = "agent-hold-clock";
    status.setAttribute("role", "status");
    status.hidden = true;
    return status;
  }
  function cardActions(...buttons) {
    const actions = document.createElement("div");
    actions.className = "agent-hold-actions";
    actions.append(...buttons.filter(Boolean));
    return actions;
  }
  // The agent asks for a domain its workspace may reach (since 2026-10-27,
  // agent_domains.py, DelegationLoop._domain_wait): the user decides every
  // one, after the reviewers judged it. The domain and the agent's reason
  // are data (untranslated): the reason as the quiet line under the title,
  // like an ask card's request (C16; it stood in the code field). "Allow
  // for this chat" is the decision "continue", "Don't allow" is "deny".
  function domainCard(context, hold) {
    const { card, body, alert, title } = cardShell("agent-domain-card", holdGlyphs.domain);
    title.dataset.i18nSkip = "";
    title.textContent = App.t("The agent asks to reach {domain}", { domain: String(hold.domain || "") });
    if (hold.domain_reason) {
      const why = document.createElement("p");
      why.className = "agent-ask-request";
      why.dataset.i18nSkip = "";
      why.textContent = String(hold.domain_reason);
      alert.append(why);
    }
    alert.append(...reasonLines(hold));
    const what = document.createElement("p");
    what.className = "agent-hold-note";
    what.textContent = "The workspace reaches only package sources. If you allow it, the agent can reach this address for the rest of this chat.";
    body.append(what, cardStatus(), cardActions(
      holdButton("Allow for this chat", "btn agent-hold-continue", () => decideHold(context, "continue")),
      holdButton("Don’t allow", "text-link agent-hold-deny", () => decideHold(context, "deny"))));
    return card;
  }
  // The agent hands a step to the user (ask_user, agent_ask.py; since
  // 2026-10-29): "browser", their turn in the workspace's browser, which
  // handing it back answers (the run sees it on the server); "confirm", their
  // yes or no to a step in their name; "secret", a key for its commands;
  // "takeover", the user took the browser over on their own and the agent's
  // next call waits for it. The agent's request is data (untranslated). The
  // one button follows who has the browser in this window
  // (App.workspaceView.holder, the event consensio:workspace-holder
  // re-draws the card). The colour only on the glyph: the house green for
  // the user's turn, the pause tone before a step in their name.
  const askTitles = { browser: "The agent needs you in the browser", confirm: "The agent asks before it goes on",
    secret: "The agent needs a key from you", takeover: "You have the browser" };
  // Per question: "offered" (the open view took the browser for the user),
  // "user" (the user had it in this window, so a hand-back here answers it).
  const askSeen = new Map();
  function askCard(context, hold) {
    const kind = askTitles[hold.ask] ? hold.ask : "confirm";
    const { card, body, alert, title } = cardShell(`agent-ask-card is-${kind}`, holdGlyphs[kind] || holdGlyphs.browser);
    title.textContent = askTitles[kind];
    const what = document.createElement("p");
    what.className = "agent-ask-request";
    if (kind === "takeover") {
      what.textContent = "The agent waits until you hand it back.";
    } else {
      what.dataset.i18nSkip = "";
      what.textContent = String(hold.request || "");
    }
    alert.append(what);
    let actions;
    if (kind === "confirm") {
      actions = cardActions(
        holdButton("Allow", "btn agent-hold-continue", () => decideHold(context, "continue")),
        holdButton("Don’t allow", "text-link agent-hold-deny", () => decideHold(context, "deny")));
    } else if (kind === "secret") {
      // The field below takes no words for the agent while this card is
      // open (steer, A-S7): what it holds moves into the key field. "Not
      // now" is the answer without a key.
      const field = secretField(context, hold);
      const input = field.querySelector(".agent-ask-secret-input");
      body.append(field);
      actions = cardActions(
        holdButton("Save", "btn agent-hold-continue", () => saveSecret(context, input)),
        holdButton("Not now", "text-link agent-hold-deny", () => decideHold(context, "deny")));
    } else {
      // The server knows a takeover from any window; this one's view only its own.
      const holding = kind === "takeover" || App.workspaceView?.holder?.() === "user";
      actions = cardActions(
        holding ? holdButton("Hand back", "btn agent-hold-hand-back", () => App.workspaceView?.handBack?.())
          : holdButton("Open the browser", "btn agent-hold-open", () => App.workspaceView?.open?.({ takeOver: true })),
        kind === "browser" && !holding ? holdButton("Not now", "text-link agent-hold-skip",
          () => decideHold(context, "continue")) : null);
    }
    body.append(cardStatus(), actions);
    return card;
  }
  function holdCard(context, hold) {
    if (hold.ask) return askCard(context, hold);
    if (hold.domain) return domainCard(context, hold);
    const kind = hold.kind === "unchecked" ? "is-unchecked" : hold.gate ? "is-gate" : "is-halt";
    const { card, body, alert, title } = cardShell(kind, holdGlyphs.pause);
    title.textContent = holdTitle(hold);
    alert.append(...reasonLines(hold));
    if (hold.step) body.append(holdEvidence(hold));
    body.append(cardStatus(), cardActions(holdButton(hold.gate ? "Let it run" : "Let it continue",
      "btn agent-hold-continue", () => decideHold(context, "continue"))));
    return card;
  }
  // The card goes the way it came (C18): it fades and sinks 3px, then makes
  // room. Focus that was on it moves to the field below, for a keyboard and
  // a mouse; never under a finger, where the field would raise the keyboard.
  function leaveHold(host) {
    const card = host.querySelector(".agent-hold-card");
    delete host.dataset.id;
    if (!card) { host.hidden = true; return; }
    const focus = document.activeElement;
    if (focus && host.contains(focus)) {
      let keys = false;
      try { keys = focus.matches(":focus-visible"); } catch (_) { keys = false; }
      if (keys || window.matchMedia?.("(hover: hover) and (pointer: fine)")?.matches) {
        document.getElementById("questionInput")?.focus({ preventScroll: true });
      }
    }
    if (App.motion?.isLeaving?.(card)) return;
    const gone = () => {
      if (host.dataset.id) return;
      host.replaceChildren();
      host.hidden = true;
    };
    if (App.motion?.leave) App.motion.leave(card, gone);
    else gone();
  }
  // The room the card may take on a phone (C4): the screen between the
  // header and the rest of the fixed composer, measured, since the field
  // grows when it opens and the keyboard takes its share of the screen
  // (agent-chat.css --hold-room). The card scrolls in itself beyond it.
  const PHONE_QUERY = "(max-width: 1099px)";
  function fitHold() {
    const host = document.getElementById("agentHold");
    const section = host?.closest(".input-section");
    if (!host || !section || host.hidden || !window.matchMedia?.(PHONE_QUERY)?.matches) {
      host?.style.removeProperty("--hold-room");
      return;
    }
    const screen = window.visualViewport?.height || window.innerHeight;
    // The header's height even while it slides away: its marks stay on top.
    const header = Math.max(56, document.querySelector(".app-mobile-header")?.getBoundingClientRect().bottom || 0);
    const rest = section.getBoundingClientRect().height - host.getBoundingClientRect().height;
    const room = `${Math.max(160, Math.floor(screen - header - rest - 16))}px`;
    if (host.style.getPropertyValue("--hold-room") !== room) host.style.setProperty("--hold-room", room);
  }
  function renderHold() {
    if (!window.document?.body) return;
    const host = document.getElementById("agentHold");
    if (!host) return;
    const context = registry.visible();
    // The run on screen decides, never the mode switch (A-B2): a pause is
    // the user's to decide whatever the next message would run with.
    const hold = openHold(context);
    clearTimeout(holdTimer);
    const workspace = App.workspaceView;
    const holder = workspace?.holder?.() || "";
    const browserTurn = hold && (hold.ask === "browser" || hold.ask === "takeover");
    // Handed back in this window: the server sees it within a few seconds
    // (agent_ask.HANDBACK_POLL_SECONDS); until then nothing asks again.
    if (browserTurn && holder === "user") askSeen.set(hold.id, "user");
    const handedBack = browserTurn && holder === "agent" && askSeen.get(hold.id) === "user";
    // The agent asked for the browser and the view is open here: it is the
    // user's at once, without a click (once per question).
    if (hold?.ask === "browser" && workspace?.isOpen?.() && holder === "agent" && !askSeen.has(hold.id)) {
      askSeen.set(hold.id, "offered");
      workspace.open({ takeOver: true });
    }
    // The workspace's bar says what the agent waits for there (workspace-view.js).
    workspace?.agentWaits?.(hold?.ask === "browser" && !handedBack ? String(hold.request || "") : null);
    // The field under the card says what it does while the card waits (syncComposer).
    const input = document.getElementById("questionInput");
    if (input && looksAgent() && registry.isExecuting(context?.runId)) {
      const placeholder = runningPlaceholder(hold);
      if (input.placeholder !== App.t(placeholder)) input.placeholder = placeholder;
    }
    // With the view open the bar above the picture carries the turn; the card
    // would say the same a second time beside it.
    if (!hold || handedBack || (browserTurn && workspace?.isOpen?.())) {
      if (host.dataset.id || !host.hidden) leaveHold(host);
      return;
    }
    // A browser card's button follows who has the browser in this window.
    const key = hold.ask === "browser" ? `${hold.id}:${App.workspaceView?.holder?.() || ""}` : hold.id;
    const reasons = reasonsKey(hold);
    const fresh = host.dataset.id !== key;
    if (fresh) {
      host.dataset.id = key;
      host.dataset.reasons = reasons;
      host.replaceChildren(holdCard(context, hold));
    } else if (host.dataset.reasons !== reasons) {
      // The same pause with another reason (a second halt, A-S2): only its
      // lines and its count change, the card with its decision stays.
      host.dataset.reasons = reasons;
      const old = [...host.querySelectorAll("[data-reason]")];
      if (old.length) {
        old[0].before(...reasonLines(hold));
        for (const line of old) line.remove();
      }
      const title = host.querySelector(".agent-hold-title");
      if (title && !hold.ask && !hold.domain) title.textContent = holdTitle(hold);
    }
    host.hidden = false;
    fitHold();
    if (fresh) for (const field of host.querySelectorAll(".agent-hold-evidence-text")) fadeCut(field);
    // The one quiet line: a failed decision first, then the words just moved
    // into the key field, then the deadline in its last minutes. While a
    // decision is on its way it keeps what it said: the pressed button says
    // it (C13; "Sending…" here grew the card by a line).
    const status = host.querySelector(".agent-hold-clock");
    const moved = hold.movedUntil > Date.now() ? "Moved into the key field. Save stores it." : "";
    const said = hold.failed || moved || (hold.deciding ? null : holdClock(hold));
    if (status && said !== null) {
      status.hidden = !said;
      status.dataset.state = hold.failed ? "error" : moved ? "note" : "clock";
      if (said && status.textContent !== App.t(said)) status.textContent = said;
    }
    for (const button of host.querySelectorAll("button")) {
      button.disabled = Boolean(hold.deciding);
      const pressed = Boolean(hold.deciding) && hold.deciding !== "steer" && button === pressedButton;
      button.classList.toggle("is-busy", pressed);
      if (pressed) button.setAttribute("aria-busy", "true"); else button.removeAttribute("aria-busy");
    }
    for (const input of host.querySelectorAll(".agent-ask-secret-input")) input.disabled = Boolean(hold.deciding);
    holdTimer = setTimeout(renderHold, moved ? Math.max(100, hold.movedUntil - Date.now()) : 15000);
  }
  // Stop is explicit: closing the connection no longer ends a turn. The
  // request identity reaches the turn before its id is known, and a Stop
  // that overtakes its own message keeps it from starting at all. It is
  // retried (backoff, and at once when the network returns) until the server
  // answered, and stays in the pending record so a reload delivers it too.
  const STOP_RETRY_MAX_MS = 10 * 60 * 1000;
  function stopOnServer(context) {
    const chatId = context.metadata.chatId;
    if (!context.metadata.requestSent || !chatId) return;
    markPendingStop(context);
    const url = `/agent/chats/${encodeURIComponent(chatId)}/requests/${encodeURIComponent(context.requestIdentity)}/stop`;
    const started = Date.now();
    let delay = 1000;
    const retry = () => {
      if (Date.now() - started > STOP_RETRY_MAX_MS) return;
      const wait = delay;
      delay = Math.min(30000, delay * 2);
      let timer = null;
      const now = () => { clearTimeout(timer); window.removeEventListener("online", now); attempt(); };
      timer = setTimeout(now, wait);
      window.addEventListener("online", now, { once: true });
    };
    const attempt = async () => {
      const user = window.auth?.currentUser;
      // Another account now: the record stays for its owner's next visit.
      if (!user || user.uid !== context.auth.uid) return;
      let response;
      try {
        const token = await user.getIdToken();
        response = await fetch(url, { method: "POST", headers: { Authorization: `Bearer ${token}` }, keepalive: true });
      } catch (_) { retry(); return; }
      if (response.status === 429 || response.status >= 500) { retry(); return; }
      forgetPending(context);
      if (!response.ok) return;
      let data = null;
      try { data = await response.json(); } catch (_) { /* no verdict needed */ }
      // The turn had already ended (e.g. while this browser was offline):
      // show what it ended with instead of a Stop that did nothing.
      if (data?.status === "not_running" && context.metadata.agentTurnId && registry.get(context.runId)?.status === "canceled") {
        recoverAnswer(context);
      }
    };
    attempt();
  }
  function cancelRun(context, reason) {
    context.consensus.status = "canceled";
    context.consensus.error = null;
    context.bookmark.status = "canceled";
    if (context.metadata.agentReview) {
      const review = { ...context.metadata.agentReview, status: "cancelled" };
      // A pasted text still being checked reads "stopped" at once, as it
      // will after a reload (agent_runs.finish_run).
      if (["waiting", "running"].includes(review.passage_check?.status)) {
        review.passage_check = { ...review.passage_check, status: "cancelled" };
      }
      context.metadata.agentReview = review;
    }
    else if (context.basis && registry.visible()?.runId === context.runId) registry.selectConversationBasis(context.basis);
    // Only the person's Stop ends the turn; a logout or account switch
    // leaves it running to its saved answer.
    if (reason === "user" && context.metadata.requestSent) stopOnServer(context);
    else forgetPending(context);
    restoreUnsentDraft(context);
    flushQueue(context);
  }
  // After a reload: follow this tab's turns that were still running. Also
  // when the mode switch stands on Compare (A-B2): a turn that may wait for
  // the user is followed whatever the next message would run with.
  function resumePending() {
    const uid = window.auth?.currentUser?.uid;
    if (!uid || resumedFor === uid || !canUse()) return;
    resumedFor = uid;
    const records = readPending(uid);
    if (!records.length) return;
    // Outside the current render: creating a run renders the shell again.
    setTimeout(async () => {
      for (const record of records) {
        if (registry.list().some(run => run.requestIdentity === record.body.client_request_id)) continue;
        if (record.stop) {
          // Stopped before the reload, Stop not yet confirmed: deliver it.
          stopOnServer({ runId: null, requestIdentity: record.body.client_request_id, auth: { uid },
            metadata: { requestSent: true, chatId: record.body.chat_id } });
          continue;
        }
        if (await resumeState(record) === "over") { dropPending(uid, record); continue; }
        resume(record, uid);
      }
    }, 0);
  }
  // A record says only that this page did not see its turn end. Asked
  // first, quietly (recover_only starts nothing): only a turn still running,
  // or one that ended moments ago, takes the screen. A turn long over or one
  // the server no longer knows took it on every reload, the field slid down
  // and back up, and its record stayed (2026-10-26). Without an answer (no
  // network) it is followed as before. "Moments ago" counts from the turn's
  // end, not from sending: a VM run of more than 10 minutes that ended just
  // before the reload counted as long over, and its answer stayed away.
  const RESUME_FRESH_MS = 10 * 60 * 1000;
  async function resumeState(record) {
    let result = null;
    try {
      const headers = { Authorization: `Bearer ${await window.auth.currentUser.getIdToken()}` };
      result = await App.withRequestDeadline(signal => window.streamSSERequest("/agent", { ...record.body, recover_only: true },
        signal, {}, { headers }), { timeoutMs: 15000 });
    } catch (_) { return "unknown"; }
    if (result?.data?.recovery_state === "running") return "running";
    const turn = result?.data?.turn;
    if (turn) {
      const ended = Date.parse(turn.completed_at || turn.failed_at || "");
      return Date.now() - (Number.isFinite(ended) ? ended : Number(record.at)) < RESUME_FRESH_MS ? "ended" : "over";
    }
    if (!result || result.status >= 500 || result.status === 429) return "unknown";
    return "over";
  }
  function dropPending(uid, record) {
    const list = readPending(uid);
    const rest = list.filter(item => item.body.client_request_id !== record.body.client_request_id);
    if (rest.length !== list.length) writePending(uid, rest);
  }
  // A chat opened while its newest turn runs, started in another tab or on
  // another device (A-B2): this tab follows it like its own after a reload,
  // by the turn's request identity (GET /bookmarks/{id}/conversation names
  // it as `running`, with the settings its recover_only request repeats), so
  // its pause card shows here too. Before, the chat showed its last saved
  // turn, nothing followed it, and a pause ran into its timeout unseen.
  // Asked quietly first: only a turn still running takes the screen, and
  // only while its chat is still the one on screen.
  const followingElsewhere = new Set();
  // Opened before the account's Agent access was known (a chat restored at
  // load): tried again once it is (renderShellNow).
  let deferredFollow = null;
  async function followRunning({ chatId, bookmarkId, turn } = {}) {
    const uid = window.auth?.currentUser?.uid;
    const requestId = typeof turn?.client_request_id === "string" ? turn.client_request_id : "";
    if (!uid || !chatId || !bookmarkId || !requestId || !turn.question) return false;
    if (!canUse()) {
      deferredFollow = accessPending() ? { chatId, bookmarkId, turn } : null;
      return false;
    }
    if (followingElsewhere.has(requestId) || registry.list().some(run => run.requestIdentity === requestId)) return false;
    const settings = turn.agent_settings && typeof turn.agent_settings === "object" ? turn.agent_settings : {};
    const selection = settings.selection || {};
    const record = { at: Date.now(), title: "", followup: false, attachmentMeta: Array.isArray(turn.attachments) ? turn.attachments : [],
      settings: { model_id: selection.model_id ?? null, reasoning_effort: selection.reasoning_effort || "default" },
      body: { chat_id: chatId, question: turn.question, client_request_id: requestId, bookmark_id: bookmarkId,
        recover_only: false, model_id: selection.model_id ?? null, reasoning_effort: selection.reasoning_effort || "default",
        comparison_models: settings.comparison_selection ?? null,
        agent_preferences: settings.agent_preferences || { depth: "auto", quorum: "all", autonomy: "guided", judges: "on" },
        file_ids: settings.file_ids || [], google_selection: settings.google_selection || null,
        google_data_consent: settings.google_data_consent === true } };
    followingElsewhere.add(requestId);
    try {
      if (await resumeState(record) !== "running") return false;
      const basis = registry.getSelectedConversationBasis();
      if (registry.visible() || basis?.bookmarkId !== bookmarkId || window.auth?.currentUser?.uid !== uid) return false;
      if (registry.list().some(run => run.requestIdentity === requestId)) return false;
      record.title = basis.title || turn.question;
      // Kept for a reload of this tab, like a run sent here.
      writePending(uid, [...readPending(uid).filter(item => item.body.client_request_id !== requestId), record].slice(-4));
      resume(record, uid, { basis: basis.chatId === chatId ? basis : null });
      return true;
    } finally {
      followingElsewhere.delete(requestId);
    }
  }
  // `basis`: the saved chat on screen whose newest turn runs elsewhere
  // (followRunning): the run continues it, with its history above.
  async function resume(record, uid, { basis = null } = {}) {
    if (!canUse() || window.auth.currentUser.uid !== uid) return;
    const body = { ...record.body, recover_only: false };
    const settings = record.settings || { model_id: body.model_id, reasoning_effort: body.reasoning_effort };
    let context;
    try {
      context = registry.create({
        question: body.question, mode: "Agent", basis, followup: Boolean(basis),
        ...(basis ? { historyTurns: [...(basis.historyTurns || []), ...(basis.currentTurn ? [basis.currentTurn] : [])] } : {}),
        attachments: [], attachmentMeta: record.attachmentMeta || [],
        requestIdentity: body.client_request_id, bookmarkId: body.bookmark_id, bookmarkTitle: record.title || body.question,
        config: { executionMode: "agent", agentMode: true, autoConsensus: false, deepSearch: false,
          useOwnKeys: false, providers: [],
          agentSettings: { model_id: body.model_id, reasoning_effort: body.reasoning_effort },
          comparisonModels: body.comparison_models || {},
          agentPreferences: body.agent_preferences || { depth: "auto", quorum: "all", autonomy: "guided", judges: "on" },
          googleSelection: body.google_selection || null, googleDataConsent: body.google_data_consent === true },
        metadata: { draftQuestion: "", quotedContext: "", fileIds: body.file_ids || [], agentActivity: [],
          agentSettings: settings, chatId: body.chat_id, requestSent: true, resumed: true },
        usage: { status: "simulation", key: null },
      });
    } catch (_) { return; }
    // What waited for this run before the reload waits again (A-B4).
    context.metadata.queue = restoreQueue(record.queue);
    context.controllers.query = new AbortController();
    const signal = context.controllers.query.signal;
    context.cancelHook = reason => cancelRun(context, reason);
    context.phase = "answers";
    context.consensus.status = "streaming";
    registry.setStatus(context.runId, "running");
    App.composer?.collapse?.({ force: true });
    // Counted for this tab's own runs after a reload (docs/analytics.md).
    if (!basis) App.trackAppEvent?.("app_run_resumed");
    try {
      const result = await follow(context, body, signal, { post: false });
      if (!registry.isAuthCurrent(context) || signal.aborted) return;
      adopt(context, result, { offer: !record.followup });
      // The resumed view shows only this message; a follow-up's chat opens
      // whole once its answer is saved (with a basis it stands whole already).
      if (record.followup && !basis && registry.isVisible(context.runId)) window.openBookmark?.(body.bookmark_id);
    } catch (error) {
      if (signal.aborted || error.name === "AbortError" || !registry.isAuthCurrent(context)) return;
      failRun(context, error);
    } finally {
      context.controllers.query = null;
      if (["succeeded", "failed"].includes(context.status)) forgetPending(context);
      flushQueue(context);
      if (registry.isAuthCurrent(context)) registry.renderVisible();
      if (!context.metadata.terminalBudget && registry.isAuthCurrent(context)) await refreshBudget(context.auth.uid);
    }
  }
  // A stream that broke or ended without its last frame: the turn itself
  // keeps running on the server and is followed by polling instead.
  const RESUMABLE = new Set(["request_failed", "stream_read_failed", "stream_incomplete"]);
  // Back in the foreground or online after this long without a byte, the
  // stream is dead without an error (phones keep half-open connections): the
  // server sends a keepalive at least every 15 s.
  const REVIVE_QUIET_MS = 20000;
  // Follows one Agent turn to its end and returns that end the way
  // streamSSERequest does ({ ok, status, data, streamed }). The server runs
  // the turn independently of this connection (agent_background.py): a
  // broken stream, a sleeping phone or a reload only switch to following it
  // by polling (agent-live.js), they never end it. `post: false` follows a
  // turn that is already running (after a reload) without sending anything.
  async function follow(context, body, signal, { headers = null, post = true } = {}) {
    let timer = null, resumeTracked = false, lastByte = Date.now();
    // Streamed text is painted once per frame, apart from the rest of the
    // projection (every 100 ms): the answer flows instead of jumping on by a
    // bundle of words ten times a second (Apple audit D4). A frame that took
    // long (a long table or list still growing) spaces out the next ones.
    let paintFrame = 0, paintTimer = 0, paintAfter = 0;
    const paint = () => {
      paintFrame = 0;
      if (!registry.isExecuting(context.runId) || !registry.isVisible(context.runId)
          || !registry.isAuthCurrent(context) || context.consensus.text) return;
      const answer = document.getElementById("agentAnswerBody");
      // Only into an answer this run already streams: its first text, errors
      // and the activity line are projected (project()).
      if (answer?.dataset.renderMode !== 'stream' || !answer.dataset.markdown) return;
      const started = performance.now();
      renderAnswerBody(answer, context.consensus.streamText || "", 'stream');
      const cost = performance.now() - started;
      paintAfter = cost > 8 ? performance.now() + cost * 2 : 0;
    };
    const schedulePaint = () => {
      if (paintFrame || paintTimer || typeof requestAnimationFrame !== "function") return;
      const wait = paintAfter - performance.now();
      if (wait > 0) paintTimer = setTimeout(() => { paintTimer = 0; schedulePaint(); }, wait);
      else paintFrame = requestAnimationFrame(paint) || 0;
    };
    const authHeaders = async () => {
      const user = window.auth?.currentUser;
      if (!user || !registry.isAuthCurrent(context)) throw new DOMException("Account changed", "AbortError");
      return { Authorization: `Bearer ${await user.getIdToken()}` };
    };
    const stall = { misses: 0 };
    const handlers = {
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
      // The last word stands and the server checks exactly this text next
      // (agent_delegation._answer_check_follows): bound to the text on screen.
      answer_check: { receive() {
        if (!registry.isExecuting(context.runId) || !registry.isAuthCurrent(context)) return;
        context.metadata.answerCheckText = context.consensus.streamText || '';
        registry.update(context.runId, () => {});
      } },
      review: { receive(event) {
        if (!registry.isExecuting(context.runId) || !registry.isAuthCurrent(context)) return;
        context.metadata.agentReview = event.review;
        registry.update(context.runId, () => {});
      } },
      // A reviewer paused the work for the user (renderHold), or the pause
      // is over (null). A frame for a pause decided here is late news.
      hold: { receive(event) {
        if (!registry.isExecuting(context.runId) || !registry.isAuthCurrent(context)) return;
        const hold = event.hold && typeof event.hold.id === "string" ? event.hold : null;
        if (hold && context.metadata.holdDecided === hold.id) return;
        // The same pause again (a resumed stream): a decision on its way stays.
        const same = hold && context.metadata.hold?.id === hold.id ? context.metadata.hold : null;
        context.metadata.hold = hold ? { ...hold, receivedAt: same?.receivedAt || Date.now(),
          ...(same?.deciding ? { deciding: same.deciding } : {}) } : null;
        renderHold();
        registry.update(context.runId, () => {});
      } },
      // Provisional marks of the fixed answer: the newest per comparison,
      // every claim so far (agent-review.js preview). Never saved.
      coverage_preview: { receive(event) {
        if (!registry.isExecuting(context.runId) || !registry.isAuthCurrent(context)) return;
        if (typeof event.comparison_id !== "string" || !Array.isArray(event.claims)) return;
        context.metadata.coveragePreview = { ...context.metadata.coveragePreview, [event.comparison_id]: event };
        registry.update(context.runId, () => {});
      } },
      activity: { receive(event) {
        if (!registry.isExecuting(context.runId) || !registry.isAuthCurrent(context)) return;
        App.agentActivity?.receive(context.metadata.agentActivity, event);
        delivered(context, event);
        if (event.kind === "status" && event.clear_response) {
          context.consensus.streamText = "";
          context.metadata.coveragePreview = null;
        }
        if (event.settings) context.metadata.agentSettings = event.settings;
        if (event.kind === "usage") context.metadata.agentUsage = event.usage;
        if (!timer) timer = setTimeout(() => { timer = null; registry.update(context.runId, () => {}); }, 100);
      } },
      // A reader behind the server's frame window: the answer text so far.
      reset: { receive(event) {
        if (!registry.isExecuting(context.runId) || !registry.isAuthCurrent(context)) return;
        context.consensus.streamText = typeof event.text === "string" ? event.text : "";
        if (!timer) timer = setTimeout(() => { timer = null; registry.update(context.runId, () => {}); }, 100);
      } },
      delta: { receive(event) {
        if (!registry.isExecuting(context.runId) || !registry.isAuthCurrent(context)) return;
        const text = typeof event.text === "string" ? event.text : "";
        if (!text) return;
        context.consensus.streamText += text;
        schedulePaint();
        if (!timer) timer = setTimeout(() => { timer = null; registry.update(context.runId, () => {}); }, 100);
      } },
    };
    // The one path every Agent frame takes, from the stream or from a
    // live poll (agent-live.js): a sequence number already applied is
    // dropped, so a buffered stream that flushes late renders nothing twice.
    const seen = App.agentLive?.sequence();
    const deliver = (type, data, seq) => {
      if (seen && !seen.accept(seq)) return;
      if (data && typeof data === "object") handlers[type]?.receive(data);
    };
    const streamHandlers = Object.fromEntries(Object.keys(handlers)
      .map(type => [type, { receive: (data, seq) => deliver(type, data, seq),
        append: (text, seq) => deliver(type, { text }, seq) }]));
    // Abort only the stream (when a poll ended the run first), not the run.
    const streamControl = new AbortController();
    const abortStream = () => streamControl.abort();
    signal.addEventListener("abort", abortStream, { once: true });
    // The saved turn, without starting anything: a result with `turn`,
    // 'running' (it runs on, e.g. on the previous server during a deploy),
    // 'offline' (no verdict) or null (no such turn).
    const recover = async () => {
      let saved;
      try {
        const current = await authHeaders();
        saved = await App.withRequestDeadline(requestSignal => window.streamSSERequest("/agent", { ...body, recover_only: true },
          requestSignal, {}, { headers: current }), { signal, timeoutMs: 15000 });
      } catch (_) { return signal.aborted ? null : "offline"; }
      if (saved?.data?.turn) return saved;
      if (saved?.data?.recovery_state === "running") return "running";
      if (!saved || saved.status >= 500 || saved.status === 429) return "offline";
      return null;
    };
    const live = App.agentLive?.watch({
      chatId: body.chat_id, requestId: body.client_request_id, headers: authHeaders, signal, deliver,
      cursor: () => seen?.last || 0, recover,
      // A pause sends nothing while it waits for the user (up to 30 min):
      // following never gives up on it (agent-live.js MAX_FOLLOW_MS).
      paused: () => Boolean(context.metadata.hold),
      onEngage: () => App.trackAppEvent?.("app_stream_buffered"),
      onState: ({ reconnecting, offline }) => {
        if (!registry.isAuthCurrent(context)) return;
        if (context.metadata.reconnecting === reconnecting && context.metadata.offline === offline) return;
        context.metadata.reconnecting = reconnecting;
        context.metadata.offline = offline;
        registry.update(context.runId, () => {});
      },
    });
    // The stream died (error, silence) but the turn runs on: follow it by
    // polling. Counted once per run, only for a stream that really died.
    const resumeFollowing = () => {
      if (!resumeTracked) { resumeTracked = true; App.trackAppEvent?.("app_stream_resumed"); }
      live.reconnect();
    };
    const revive = () => {
      if (document.visibilityState === "hidden" || !live || live.reconnecting) return;
      if (Date.now() - lastByte >= REVIVE_QUIET_MS) resumeFollowing();
    };
    if (post) {
      document.addEventListener("visibilitychange", revive);
      window.addEventListener("online", revive);
    }
    try {
      if (!post) {
        if (!live) throw Object.assign(new Error("Connection lost before the response was completed."), { streamFailureKind: "stream_incomplete" });
        live.reconnect();
        const followed = await live.finished;
        if (signal.aborted) throw new DOMException("Request cancelled", "AbortError");
        if (!followed) throw Object.assign(new Error("This response could not be followed. Check its saved answer."), { streamFailureKind: "stream_incomplete" });
        return followed;
      }
      const streaming = App.withRequestDeadline((requestSignal, onProgress) => window.streamSSERequest("/agent", body, requestSignal,
        streamHandlers, { headers, onProgress: () => { lastByte = Date.now(); onProgress?.(); live?.bytes(); } }),
        // 45 s without a byte (keepalives come every 15 s): with the live
        // follower the stream is given up for polling, never the turn.
        { signal: streamControl.signal, timeoutMs: 45000, onIdle: live
          ? () => { resumeFollowing(); return undefined; }
          : () => checkStalledRun(context, body, headers, stall) });
      if (!live) return await streaming;
      streaming.catch(() => {}); // Rejects with AbortError when the poll wins.
      const outcome = await Promise.race([streaming.then(value => ({ value }), error => ({ error })),
        live.finished.then(value => ({ value, polled: true }))]);
      if (outcome.polled) {
        abortStream();
        if (outcome.value) return outcome.value;
        // The follower gave up (no such turn, follow limit): no silent stream
        // may keep the run open.
        throw Object.assign(new Error("Connection lost before the response was completed."), { streamFailureKind: "stream_incomplete" });
      }
      if (!outcome.error) return outcome.value;
      const error = outcome.error;
      if (signal.aborted || error?.name === "AbortError" || !registry.isAuthCurrent(context) || !context.metadata.requestSent
          || !(live.reconnecting || RESUMABLE.has(error?.streamFailureKind))) throw error;
      // The stream broke, the turn did not: follow it to its end.
      resumeFollowing();
      const followed = await live.finished;
      if (signal.aborted) throw new DOMException("Request cancelled", "AbortError");
      if (!followed) throw error;
      return followed;
    } finally {
      live?.stop();
      signal.removeEventListener("abort", abortStream);
      document.removeEventListener("visibilitychange", revive);
      window.removeEventListener("online", revive);
      clearTimeout(timer);
      if (paintFrame) cancelAnimationFrame(paintFrame);
      clearTimeout(paintTimer);
      context.metadata.reconnecting = false;
      context.metadata.offline = false;
    }
  }
  // The end the server reported (terminal frame, polled frame or saved
  // turn): adopt the answer, or throw its failure for failRun.
  function adopt(context, result, { offer = true } = {}) {
    receiveBudget(result.data?.token_budget, context.auth.uid);
    context.metadata.terminalBudget = Boolean(result.data?.token_budget);
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
      throw Object.assign(App.httpError(result, data, apiError(data)), { failure: data, notDispatched: refused });
    }
    acceptAnswer(context, result.data);
    App.trackAnswer?.(context, "ok");
    if (offer) offerWatch(context);
  }
  // The words of a failed run: a refusal's own sentence, otherwise what
  // happened in plain words (offline, unreachable, too slow), never the
  // engine's ("Failed to fetch", "Load failed", Apple-Audit H1).
  const NOT_SENT_ALREADY_SAYS = new Set(["offline", "unreachable", "timeout", "unknown"]);
  function failRun(context, error) {
    // Flat ({error, code}) or wrapped ({error: {error, error_code}}, {detail}).
    const failure = App.errorFields?.(error.failure) || error.failure || {};
    const code = failure.code || failure.error_code;
    const notSent = Boolean(error.notDispatched || !context.metadata.requestSent);
    const reason = App.userError(error, { context: notSent ? "send" : undefined,
      fallback: notSent ? undefined : "The answer couldn’t be completed. Try again." });
    context.consensus.status = "error";
    context.consensus.error = { message: reason, code,
      required_tokens: failure.required_tokens, available_tokens: failure.available_tokens };
    // "ask" went out with the POST; a refusal still ends that run as
    // failed, like a refused pipeline run (query-send.js finishFailed).
    const asked = context.metadata.requestSent === true;
    if (error.notDispatched || !context.metadata.requestSent) {
      // Never offer "Check saved answer" or keep a Failed sidebar row for a
      // message that the server refused before starting it.
      context.metadata.requestSent = false;
      context.metadata.recoverable = false;
      // "You’re offline. Your message is back in the box." says it already.
      context.consensus.error.message = NOT_SENT_ALREADY_SAYS.has(App.userError.kind(error)) ? reason : `Message not sent. ${reason}`;
      releaseRunRow(context);
    } else if (['agent_token_reservation', 'agent_tokens_exhausted'].includes(code) && !context.consensus.streamText) {
      // An admission refusal produced no answer: offer the question again.
      context.metadata.recoverable = false;
      context.metadata.restoreDraft = true;
    } else if (code === 'hold_timeout' && !context.consensus.streamText) {
      // A pause nobody decided ends the run with nothing saved to check
      // (UX audit C15): Retry stays, "Check saved answer" would find nothing.
      context.metadata.recoverable = false;
    }
    context.bookmark.status = "failed";
    // Nothing reviews any more: the review ends here as it will read after a
    // reload (agent_runs.finish_run), not "Reviewing the answer…" until the
    // chat is opened again (A-B5). A finished review keeps its result.
    const review = context.metadata.agentReview;
    if (review && !["succeeded", "partial", "off", "failed", "cancelled", "missing"].includes(review.status)) {
      context.metadata.agentReview = { ...review, status: review.status === "required" ? "missing" : "failed",
        ...(Array.isArray(review.comparisons) ? { comparisons: review.comparisons.map(comparison => comparison?.status === "running"
          ? { ...comparison, status: "failed" } : comparison) } : {}),
        ...(["waiting", "running"].includes(review.passage_check?.status)
          ? { passage_check: { ...review.passage_check, status: "failed" } } : {}) };
    }
    if (asked) App.trackAnswer?.(context, "failed");
    registry.setStatus(context.runId, "failed", { message: context.consensus.error.message });
    if (!context.metadata.agentReview && context.basis && registry.visible()?.runId === context.runId) registry.selectConversationBasis(context.basis);
  }
  async function send(recovery = null, { retry = null } = {}) {
    if (recovery) return recoverAnswer(recovery);
    if (!canUse()) {
      // A guest is asked in the login dialog (Apple-Audit H2); an account
      // without Agent hears why.
      if (!window.auth?.currentUser) App.askToLogIn?.("Log in to use Agent.", { trigger: document.getElementById("sendButton"), source: "agent" });
      else App.showPopup?.("Agent isn’t available on your account yet.");
      return;
    }
    const input = document.getElementById("questionInput");
    const draft = retry ? retry.question : input?.value || "";
    // Files without words go out under their names (attachments.js messageText).
    const question = retry ? String(retry.question || "").trim()
      : String(App.quote?.compose?.(draft) ?? draft).trim() || App.attachments?.messageText?.() || "";
    if (!question) return;
    const settings = recovery?.config.agentSettings || {
      ...selection(), reasoning_effort: document.getElementById("agentReasoningEffort")?.value || "default",
    };
    const comparisonModels = comparisonSelection();
    if (!hasValidComparisonSelection(comparisonModels)) {
      App.showPopup?.(comparisonRequirement('before'));
      return;
    }
    if (!catalog || catalogStatus !== 'ready' || !catalog.models.some(model => model.id === settings.model_id && model.available !== false)) {
      App.showPopup?.("Choose an available agent model before sending."); return;
    }
    const basis = retry ? retry.basis || null : registry.getSelectedConversationBasis();
    if (basis && (!basis.chatId || basis.continuationUnavailable)) {
      App.showPopup?.("Reopen this saved chat before continuing."); return;
    }
    let context, signal;
    let refused = null;
    // The run is created and started as one change: the registry projects it
    // once (run-registry.js batch). Two projections in this click read each
    // other's half-written layout and held the first frame back
    // (Apple-Audit D3).
    const begin = () => {
      try {
        context = registry.create({
          question, mode: "Agent", basis, followup: Boolean(basis),
          historyTurns: [...(basis?.historyTurns || []), ...(basis?.currentTurn ? [basis.currentTurn] : [])],
          attachments: retry ? [] : window.getAttachmentsPayload?.() || [],
          attachmentMeta: retry ? retry.attachmentMeta : App.attachments?.messageMeta?.() || [],
          requestIdentity: recovery?.requestIdentity,
          bookmarkId: retry?.bookmarkId || basis?.bookmarkId || `b_agent_${crypto.randomUUID().replaceAll("-", "")}`,
          bookmarkTitle: basis?.title || question,
          config: { executionMode: "agent", agentMode: true, autoConsensus: false,
            deepSearch: false, useOwnKeys: false, providers: [], agentSettings: settings, comparisonModels,
            agentPreferences: recovery?.config.agentPreferences || App.agentPreferences?.get?.() || { depth: "auto", quorum: "all", autonomy: "guided", judges: "on" },
            googleSelection: retry ? retry.googleSelection : App.agentGoogle?.selection() || null,
            googleDataConsent: retry ? retry.googleDataConsent : App.agentGoogle?.consent() === true },
          metadata: { draftQuestion: draft, quotedContext: retry ? '' : App.quote?.text?.() || '',
            ...(retry ? { fileIds: retry.fileIds } : {}),
            agentActivity: [], agentSettings: { ...settings, label: catalog?.models.find(model => model.id === settings.model_id)?.label } },
          usage: { status: "simulation", key: null },
        });
      } catch (error) { refused = error; return; }
      // Its files wait over the message from the first frame until stored
      // (agent-workspace.js upload), not shown and then covered again.
      if (context.attachments.length) App.attachments?.markUploading?.(context.runId, context.attachments);
      if (retry?.runId) {
        // The new run takes over the failed run's sidebar row.
        const failed = registry.get(retry.runId);
        if (failed) failed.bookmark.uiReady = true;
        document.querySelector(`.bookmark.run-entry[data-run-id="${cssId(retry.runId)}"]`)?.remove();
      }
      if (context.config.googleDataConsent) App.agentGoogle?.resetConsent();
      context.controllers.query = new AbortController();
      signal = context.controllers.query.signal;
      context.consensus.status = "pending";
      context.cancelHook = reason => cancelRun(context, reason);
      registry.setStatus(context.runId, "running");
    };
    if (registry.batch) registry.batch(begin); else begin();
    if (refused) { App.showPopup?.(App.userError(refused, { context: "send" })); return; }
    // Emptied once the run is on screen: Send is already the stop button
    // then, and the field's listeners leave it alone.
    if (!recovery && !retry) {
      App.clearQuestionDraft?.();
      if (input) { input.value = ""; input.dispatchEvent(new Event("input", { bubbles: true })); }
      App.quote?.clear?.();
    }
    App.composer?.collapse?.({ force: true });
    if (!recovery && !retry) App.revealSentMessage?.();
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
          return { response, data: await App.readJson(response) };
        }, { signal });
        // The chat limit says what to do ("Delete one…"), not the raw server text.
        if (!response.ok) {
          const refusal = App.httpError(response, data);
          const limit = App.chatPersistenceErrorMessage?.(data);
          if (limit) refusal.message = refusal.serverMessage = limit;
          throw refusal;
        }
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
        agent_preferences: context.config.agentPreferences || { depth: "auto", quorum: "all", autonomy: "guided", judges: "on" },
        file_ids: context.metadata.fileIds || [],
        google_selection: context.config.googleSelection || null,
        google_data_consent: context.config.googleDataConsent === true,
        timezone: deviceTimezone(),
      };
      rememberPending(context, body);
      const result = await follow(context, body, signal, { headers });
      if (!registry.isAuthCurrent(context) || signal.aborted) return;
      adopt(context, result);
    } catch (error) {
      if (signal.aborted || error.name === "AbortError" || !registry.isAuthCurrent(context)) return;
      failRun(context, error);
    } finally {
      context.controllers.query = null;
      App.attachments?.markUploading?.(context.runId, []);
      // Only a known end clears the record for a reload; Stop and logout
      // handle theirs in cancelRun, a transport problem keeps it.
      if (["succeeded", "failed"].includes(context.status)) forgetPending(context);
      restoreUnsentDraft(context);
      flushQueue(context);
      if (registry.isAuthCurrent(context)) registry.renderVisible();
      if (!context.metadata.terminalBudget && context.metadata.requestSent && registry.isAuthCurrent(context)) await refreshBudget(context.auth.uid);
    }
  }
  App.agentChat = { canUse, modeState, hasValidComparisonSelection, sendBlocker, syncComposer, isSelected: () => selectedMode() === "agent",
    // Agent's composer is on screen (also while its access is still loading).
    looksAgent,
    // The settings card (agent-settings.js): the next message's pick, its labels, and applying one.
    pick: () => selection(), modelLabel, applyPick,
    render: () => renderShell(), renderShell, project, send, steer, steering, revealPendingReview, syncPendingReview,
    // firebase.js: a chat opened while its newest turn runs elsewhere.
    followRunning,
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
  // The session is known (signed in, or ended): the look the page expected
  // gives way to the real one, e.g. no Agent chip for a session that ended
  // while the page still expected it (review 1).
  window.addEventListener("consensio:auth-state", () => renderShell());
  // The user took the workspace's browser over or handed it back (workspace-view.js):
  // the agent's browser card offers the other way.
  window.addEventListener("consensio:workspace-holder", () => renderHold());
  window.addEventListener("resize", fitHold);
  window.visualViewport?.addEventListener?.("resize", fitHold);
  // The field opens and closes under the card (composer-collapse.js), the
  // line under it comes and goes: the whole composer is watched. The card's
  // own height changes it too, but leaves the room the same.
  const holdComposer = document.querySelector(".input-section");
  if (holdComposer && typeof ResizeObserver === "function") new ResizeObserver(() => fitHold()).observe(holdComposer);
  // No login can load (auth-bootstrap.js): nobody is a guest who could send,
  // so the signed-out page it shows has no Agent.
  window.addEventListener("consensio:auth-unavailable", () => renderShell());
  // The account's model pick arrived (server, another tab, sign-out). A pick
  // this tab's model list does not know comes from a newer list (a tab or
  // device opened after a deploy): the list is fetched again before anything
  // repairs the pick, so a stale tab never resets it for every device.
  App.userSettings.onChange("agent_model", detail => {
    if (detail.source === "local") return;
    const pick = App.userSettings.get("agent_model");
    if (pick && catalogStatus === "ready" && !catalog.models.some(item => item.id === canonicalId(pick.model_id))) {
      catalogStatus = "idle";
    }
    render();
  });
  // The placeholder has a length per width; a rotated phone gets the right one.
  for (const query of ['(max-width: 360px)', '(max-width: 640px)']) {
    window.matchMedia?.(query)?.addEventListener?.('change', () => syncComposer());
  }
  window.addEventListener('consensio:agent-actions-change', () => { syncPendingReview(); window.updateQuestionInputAccess?.(); });
  // Google selection/consent changes (chips, sheet, consent box) change the
  // send blocker, so the notice and Send state must follow immediately.
  window.addEventListener('consensio:agent-google-change', () => { syncComposer(); window.updateQuestionInputAccess?.(); });
  // The buttons under a failed answer live on the live surface, which a
  // follow-up replaces by a fresh copy (liveTurn.take). A listener bound to
  // the first copy went with it: after the first follow-up Retry & Co. did
  // nothing (review B2). One listener on the document reaches every copy.
  document.addEventListener("click", event => {
    if (event.target.closest?.("#agentRecover")) {
      const context = registry.visible();
      if (["failed", "canceled"].includes(context?.status) && context.metadata.requestSent) send(context);
      return;
    }
    const button = event.target.closest?.("#agentAnswerErrorActions button[data-action]");
    if (button) runNoticeAction(button.dataset.action);
  });
  document.addEventListener("DOMContentLoaded", () => {
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
    document.getElementById('agentReviewAction')?.addEventListener('click', () => revealPendingReview());
    document.getElementById('questionInput')?.addEventListener('input', () => {
      if (selectedMode() === 'agent') window.updateQuestionInputAccess?.();
      // Text while a response runs turns Stop into Send (query-send.js).
      App.syncSendButtonRunning?.();
    });
    render();
  });
})();
