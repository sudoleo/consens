// Compare: one question, the chosen models answer side by side.
// Every await/callback is bound to one RunContext from App.runRegistry; the
// shared response DOM is written only by run-view.js when that run is visible.
// Agent messages go to agent-chat.js (window.sendQuestion hands them over).
// Until 2026-10-25 this module also ran the Consensus pipeline after the
// answers; that now runs only on the server (Watches, the API, topics).
(function () {
  "use strict";

  window.App = window.App || {};
  const registry = window.App.runRegistry;
  const trackAppEvent = window.App.trackAppEvent || (() => {});

  // Familien des Laufs: window.App.modelPrefs ist die eine Quelle (Server:
  // cfg.PROVIDERS). Der eine OpenRouter-Key gilt fuer alle Familien.
  function providerDefinitions() {
    return (window.App.modelPrefs || []).map(pref => ({
      provider: pref.key,
      endpoint: pref.endpoint,
      boxId: pref.responseId,
      checkboxId: pref.checkId,
      selectId: pref.selectId,
      keyName: "openrouterKey",
      pref
    }));
  }

  function isAbortError(error) {
    return error?.name === "AbortError";
  }

  // Bookmark/turn label. "Deep Think" only survives in old bookmarks; the
  // Reasoning switch is recorded as deep_search, not as a mode.
  function getActiveMode() {
    return "Standard";
  }

  function isDemoQuery(question) {
    return String(question || "").trim().toLowerCase() === "demo";
  }

  function secureKey() {
    return globalThis.crypto?.randomUUID?.()
      || `${Date.now()}-${Math.random().toString(16).slice(2)}-${Math.random().toString(16).slice(2)}`;
  }

  function bookmarkIdForRun(runId) {
    return `b_${String(runId || "").replace(/[^A-Za-z0-9_]/g, "_").slice(0, 94)}`;
  }

  function optionLabel(select) {
    const option = select?.options?.[select.selectedIndex];
    return String(option?.dataset?.modelLabel || option?.text || select?.value || "").trim();
  }

  function selectedProviders(attachmentCount) {
    return providerDefinitions().reduce((items, definition) => {
      if (!document.getElementById(definition.checkboxId)?.checked) return items;
      const select = document.getElementById(definition.selectId);
      const modelId = String(select?.value || "").trim();
      if (!modelId) return items;
      // Die Faehigkeit gehoert zum effektiven Modell, nicht zur Familie:
      // GLM 5.3 Flash ist multimodal, GLM 5.3 text-only.
      const acceptsAttachments = typeof window.App.modelAcceptsAttachments === "function"
        ? window.App.modelAcceptsAttachments(definition.pref, modelId)
        : definition.pref.handlesAttachments !== false;
      if (attachmentCount > 0 && !acceptsAttachments) return items;
      items.push({
        ...definition,
        modelId,
        modelLabel: optionLabel(select) || definition.provider
      });
      return items;
    }, []);
  }

  function currentSystemPrompt() {
    // The account setting. Empty means the live app default supplied by
    // /prepare (also by /ask on fallback).
    const base = window.App.userSettings.get("system_prompt") || "";
    if (!base.trim()) return "";
    const now = new Date();
    const weekday = now.toLocaleDateString("en-US", { weekday: "long" });
    const date = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
    return `Today is ${weekday}, ${date}. ${base}`;
  }

  function createUsage(deepThink, useOwnKeys) {
    return {
      key: useOwnKeys ? null : secureKey(),
      deepThink: deepThink === true,
      useOwnKeys: useOwnKeys === true,
      status: useOwnKeys ? "own_keys" : "new"
    };
  }

  function authIsCurrent(context) {
    return registry.isAuthCurrent(context);
  }

  function clearSensitiveRunData(context) {
    if (!context) return;
    context.credentials = null;
    context.attachments = [];
  }

  function runIsCurrent(context) {
    return registry.isExecuting(context.runId)
      && !context.controllers.query?.signal?.aborted
      && authIsCurrent(context);
  }

  // One flat refusal, whichever form the server used (App.errorFields).
  function unwrapApiError(data) {
    if (window.App.errorFields) return window.App.errorFields(data);
    const detail = data?.detail;
    if (detail && typeof detail === "object") {
      return { ...detail, error: detail.error || detail.message || "Request failed." };
    }
    return data || {};
  }

  // A refusal's own sentence, or `fallback`; never "HTTP 502" or the
  // engine's words (App.userError, Apple-Audit H1).
  function apiErrorMessage(data, fallback = "Something went wrong. Try again.") {
    return window.App.userError(data && typeof data === "object" ? data : String(data || ""), { fallback });
  }

  function isUsageStorageBusy(data) {
    const normalized = unwrapApiError(data);
    return String(normalized.error_code || normalized.code || "").toLowerCase() === "usage_storage_busy";
  }

  function isUsageLimit(data, message = "") {
    if (window.App.usageLimit?.isLimitError) {
      return window.App.usageLimit.isLimitError(data, message);
    }
    const normalized = unwrapApiError(data);
    const code = String(normalized.error_code || normalized.code || "").toLowerCase();
    const text = String(message || normalized.error || normalized.detail || "").toLowerCase();
    return code.includes("limit") || /usage limit|quota|used up|exhausted/.test(text);
  }

  function updateUsage(context, data) {
    const normalized = unwrapApiError(data);
    if (normalized.usage_run_status) context.usage.status = normalized.usage_run_status;
    if (normalized.is_pro_user !== undefined) {
      context.usage.isProUser = normalized.is_pro_user === true;
    }
    // Die volle Stufe, damit ein Plus-Lauf die Ansicht nicht auf Free
    // zurueckstellt (is_pro_user ist fuer Plus false).
    if (normalized.tier !== undefined) {
      context.usage.tier = window.App.normalizeTier?.(normalized.tier) || "free";
    }
    // Usage is account-level rather than view-level. The auth fence prevents
    // a late response from a previous login from repainting the next account.
    if (authIsCurrent(context)) {
      window.App.renderUsageDisplay?.(normalized, context);
      const noSavedViewSelected = !registry.visible()
        && !registry.getSelectedConversationBasis?.();
      // Wie in run-view.js: ein blosses "is_pro_user: false" ohne "tier" ist
      // seit der Plus-Stufe kein Free-Beleg mehr, sondern nur "nicht Pro".
      // Nur ein ausdrueckliches tier oder ein true darf die Anzeige stellen.
      const tierSignal = normalized.tier
        ?? (normalized.is_pro_user === true ? "pro" : null);
      if (tierSignal !== null
          && (registry.isVisible(context.runId) || noSavedViewSelected)) {
        window.updateUserTierUI?.(tierSignal, true);
      }
    }
  }

  async function prepareWithRetry(payload, signal) {
    let result = null;
    for (let attempt = 1; attempt <= 3; attempt += 1) {
      const response = await fetch("/prepare", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal
      });
      const data = await window.App.readJson(response);
      result = { response, data };
      if (response.ok || !isUsageStorageBusy(data) || attempt === 3) return result;
      await new Promise(resolve => window.setTimeout(resolve, attempt * 350));
    }
    return result;
  }

  function incompleteMessage(completion) {
    return completion === "token_limit"
      ? "This answer stopped at the output limit; its end is missing."
      : "This answer was interrupted and is incomplete.";
  }

  function contextStreamRenderer(context, provider) {
    const RENDER_INTERVAL = 120;
    let timer = null;
    let lastRender = 0;

    function render() {
      timer = null;
      lastRender = Date.now();
      if (registry.isVisible(context.runId)) registry.renderVisible();
    }

    function scheduleRender() {
      if (!registry.isVisible(context.runId)) return;
      const elapsed = Date.now() - lastRender;
      if (elapsed >= RENDER_INTERVAL) render();
      else if (!timer) timer = window.setTimeout(render, RENDER_INTERVAL - elapsed);
    }

    return {
      append(chunk) {
        if (!runIsCurrent(context)) return;
        const result = context.modelResults[provider];
        result.status = "streaming";
        result.streamText += String(chunk || "");
        scheduleRender();
      },
      markReasoning() {
        if (!runIsCurrent(context)) return;
        const result = context.modelResults[provider];
        if (!result.streamText) result.status = "reasoning";
        scheduleRender();
      },
      stop() {
        if (timer) window.clearTimeout(timer);
        timer = null;
      }
    };
  }

  function persistenceOptions(context) {
    return {
      runId: context.runId,
      bookmarkId: context.bookmark.id,
      sources: context.evidenceSources.map(source => ({ ...source })),
      attachments: context.attachmentMeta.map(item => ({ ...item })),
      auth: context.auth
    };
  }

  async function runProvider(context, providerConfig, idToken, systemPrompt) {
    const result = context.modelResults[providerConfig.provider];
    const controller = new AbortController();
    context.controllers.providers.set(providerConfig.provider, controller);
    const abortProvider = () => controller.abort();
    context.controllers.query.signal.addEventListener("abort", abortProvider, { once: true });

    const payload = {
      question: context.question,
      deep_search: context.config.deepSearch,
      system_prompt: systemPrompt,
      mode: context.mode,
      run_mode: "compare",
      model: providerConfig.modelId,
      id_token: idToken,
      useOwnKeys: context.config.useOwnKeys,
      usage_run_key: context.usage.key
    };
    if (context.attachments.length) payload.attachments = context.attachments;
    if (context.config.useOwnKeys) payload.openrouter_key = context.credentials.openrouterKey || "";

    try {
      const response = await window.streamSSERequest(
        providerConfig.endpoint,
        payload,
        controller.signal,
        { delta: contextStreamRenderer(context, providerConfig.provider) }
      );
      if (!registry.isExecuting(context.runId) || !authIsCurrent(context) || result.status === "skipped") return;
      updateUsage(context, response.data || {});
      if (!response.ok) throw window.App.httpError(response, response.data || {}, "This model didn’t answer. Try again.");
      const data = response.data || {};
      if (!data.response) throw new Error(apiErrorMessage(data, "This model returned an empty answer."));

      const prepared = window.App.prepareResponseSourcesForEvidence
        ? window.App.prepareResponseSourcesForEvidence(data.response, data.sources || [], context.evidenceSources)
        : { markdown: data.response, sources: data.sources || [], evidenceSources: context.evidenceSources };
      context.evidenceSources = prepared.evidenceSources;
      // Typed completion state (R06). Partial text stays visible, labelled.
      // A token-limit answer still counts, marked as truncated; an
      // interrupted one is incomplete.
      const completion = typeof data.completion === "string" ? data.completion : "complete";
      const usable = completion === "complete" || completion === "token_limit";
      result.status = usable ? "complete" : "incomplete";
      result.completion = completion;
      result.text = prepared.markdown;
      result.streamText = prepared.markdown;
      result.sources = prepared.sources;
      result.rawSources = Array.isArray(data.sources) ? data.sources : [];
      result.error = completion === "complete" ? null : incompleteMessage(completion);
      context.progress.completedModels += 1;
      if (result.status === "complete") context.progress.successfulModels += 1;
      else context.progress.failedModels += 1;
      registry.update(context.runId, () => {});

      // Each finished answer is saved to the comparison's bookmark as it
      // arrives. An incomplete answer is never stored as if it were a
      // finished one (R06).
      if (authIsCurrent(context) && completion === "complete") {
        const promise = window.saveBookmark?.(
          context.question,
          result.text,
          providerConfig.provider,
          context.mode,
          "",
          { ...persistenceOptions(context), modelLabel: providerConfig.modelLabel || providerConfig.modelId }
        );
        if (promise?.catch) promise.catch(() => undefined);
      }
    } catch (error) {
      if (result.status === "skipped") return;
      if (isAbortError(error)) {
        if (context.status === "canceled") result.status = "canceled";
        return;
      }
      result.status = "error";
      // The panel names the model; the line says what happened in plain words.
      result.error = window.App.userError(error, { fallback: "This model didn’t answer. Try again." });
      context.progress.completedModels += 1;
      context.progress.failedModels += 1;
      registry.update(context.runId, () => {});
    } finally {
      context.controllers.query?.signal?.removeEventListener?.("abort", abortProvider);
      context.controllers.providers.delete(providerConfig.provider);
    }
  }

  async function releaseUnusedUsage(context, { allowAfterLogout = false } = {}) {
    if (!context?.usage?.key || !["new", "reserved"].includes(context.usage.status)) return;
    const key = context.usage.key;
    context.usage.status = "released_local";
    try {
      const token = await context.auth.user?.getIdToken?.(false);
      if (!token || (!allowAfterLogout && !authIsCurrent(context))) return;
      const response = await fetch("/usage/run/release", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id_token: token, usage_run_key: key }),
        keepalive: true
      });
      // The release drops the run's admission hold; spent tokens never
      // change, so there is no account snapshot to repaint.
      await response.json().catch(() => ({}));
    } catch (_) {}
  }

  function restoreComposerAfterUnsentRun(context) {
    if (!registry.isVisible(context.runId)) return;
    const input = document.getElementById("questionInput");
    const composerAttachments = window.getAttachmentsPayload?.()
      || (Array.isArray(window.pendingAttachments) ? window.pendingAttachments : []);
    const composerOccupied = Boolean(input?.value?.trim())
      || Boolean(window.App.quote?.text?.())
      || composerAttachments.length > 0;
    // The user may have prepared a new draft while this request was in the
    // background and then reopened it only to cancel. Never replace that newer
    // composer ownership with the canceled run's frozen draft/attachments.
    if (composerOccupied) return;
    if (input) {
      input.value = context.metadata.draftQuestion || context.question;
      input.dispatchEvent(new Event("input", { bubbles: true }));
      if (context.metadata.quotedContext) window.App.quote?.set?.(context.metadata.quotedContext);
    }
    if (Array.isArray(window.pendingAttachments) && context.attachments?.length) {
      window.pendingAttachments = context.attachments.map(item => ({ ...item }));
      window.renderAttachmentChips?.();
    }
  }

  function finishFailed(context, message, data = null) {
    if (!registry.isExecuting(context.runId)) return;
    const failedBeforeFanout = context.phase === "prepare";
    context.phase = "failed";
    context.error = { code: "run_failed", message: String(message || "The run failed.") };
    context.bookmark.status = "failed";
    if (isUsageLimit(data || {}, message)) {
      updateUsage(context, data || {});
      if (registry.isVisible(context.runId)) {
        window.App.usageLimit?.show?.({ data: data || {}, source: "run", phase: "prepare" });
      }
    }
    if (failedBeforeFanout) restoreComposerAfterUnsentRun(context);
    releaseUnusedUsage(context);
    clearSensitiveRunData(context);
    registry.setStatus(context.runId, "failed", context.error);
    trackAppEvent("app_query_completed", { status: "error", selected_models: context.progress.totalModels });
    window.App.trackAnswer?.(context, "failed");
  }

  async function executeRun(context) {
    const signal = context.controllers.query.signal;
    try {
      let idToken = null;
      try { idToken = await context.auth.user?.getIdToken?.(); } catch (_) {}
      if (!runIsCurrent(context)) return;
      if (!idToken) {
        finishFailed(context, "Your session has ended. Log in again to send your question.");
        return;
      }

      const preparePayload = {
        question: context.question,
        system_prompt: context.config.systemPrompt,
        deep_search: context.config.deepSearch,
        mode: context.mode,
        // Admission: the expected tokens of a typical Compare run.
        run_mode: "compare",
        // The answer that books last frees what the admission still holds;
        // otherwise the sidebar calls it held for a running message.
        operations: context.config.providers.length,
        useOwnKeys: context.config.useOwnKeys,
        id_token: idToken
      };
      if (context.usage.key) preparePayload.usage_run_key = context.usage.key;

      const prepared = await prepareWithRetry(preparePayload, signal);
      if (!runIsCurrent(context)) return;
      updateUsage(context, prepared.data || {});
      if (!prepared.response.ok && isUsageStorageBusy(prepared.data)) {
        finishFailed(context, apiErrorMessage(prepared.data, "The allowance service is busy right now. Try again in a moment."), prepared.data);
        if (registry.isVisible(context.runId)) window.App.usageLimit?.showTemporaryStorageBusy?.();
        return;
      }
      if (!prepared.response.ok && isUsageLimit(prepared.data)) {
        context.usage.status = prepared.data?.usage_run_status || context.usage.status;
        finishFailed(context, apiErrorMessage(prepared.data, "You’ve used today’s allowance."), prepared.data);
        return;
      }
      const effectivePrompt = prepared.response.ok && prepared.data?.system_prompt
        ? prepared.data.system_prompt
        : context.config.systemPrompt;
      if (!runIsCurrent(context)) return;

      context.phase = "answers";
      registry.update(context.runId, () => {});
      await Promise.all(context.config.providers.map(provider => runProvider(context, provider, idToken, effectivePrompt)));
      if (!registry.isExecuting(context.runId)) return;
      context.controllers.query = null;

      const successes = Object.values(context.modelResults)
        .filter(result => result.status === "complete" && String(result.text || "").trim()).length;
      if (successes === 0) {
        window.App.reportCriticalError?.({
          type: "run_failed",
          phase: "model_fanout",
          message: "All selected model requests failed.",
          details: `${context.progress.totalModels} providers failed`
        });
        finishFailed(context, "All selected model requests failed.");
        return;
      }

      context.phase = "done";
      context.bookmark.status = "succeeded";
      clearSensitiveRunData(context);
      registry.setStatus(context.runId, "succeeded");
      trackAppEvent("app_query_completed", { status: "success", selected_models: context.progress.totalModels });
      window.App.trackAnswer?.(context, "ok");
    } catch (error) {
      if (isAbortError(error) || !registry.isExecuting(context.runId)) return;
      // Failed before the models were asked: the message went back into the
      // box (restoreComposerAfterUnsentRun), and the sentence says so.
      const message = window.App.userError(error, { context: context.phase === "prepare" ? "send" : undefined,
        fallback: "The answers couldn’t be completed. Try again." });
      finishFailed(context, message);
      if (registry.isVisible(context.runId)) window.App.showPopup?.(message);
    }
  }

  function validateOwnKeys(providers) {
    const required = new Set(providers.map(provider => provider.keyName));
    return Array.from(required).filter(keyName => !String(localStorage.getItem(keyName) || "").trim());
  }

  function beginContext(question, draftQuestion, quotedContext) {
    // Reasoning switch; kept as config.deepSearch / deep_search on the wire.
    const deepSearch = document.getElementById("reasoningToggle")?.checked === true;
    const useOwnKeys = document.getElementById("useOwnKeysSwitch")?.checked === true;
    const attachments = window.getAttachmentsPayload?.() || [];
    const attachmentMeta = attachments.map(item => ({ name: item.name, mime: item.mime, size: item.size || 0 }));
    // Files are open to every account (2026-10-02); they only need one.
    if (attachments.length && !window.auth?.currentUser) {
      window.App.askToLogIn?.("Log in to send files with your question.", { trigger: document.getElementById("sendButton"), source: "attachments" });
      return null;
    }
    const providers = selectedProviders(attachments.length);
    if (providers.length < 2) {
      window.App.showPopup?.("Choose at least two compatible models. Remove the attachment or select another model.");
      return null;
    }

    if (useOwnKeys && validateOwnKeys(providers).length) {
      window.App.showPopup?.("Add your OpenRouter API key before sending.");
      return null;
    }

    const authUser = window.auth?.currentUser || null;
    if (!authUser) {
      window.App.askToLogIn?.("Log in to send your question.", { trigger: document.getElementById("sendButton"), source: "send" });
      return null;
    }

    const usage = createUsage(deepSearch, useOwnKeys);
    // agentMode/autoConsensus are the persisted run fields for "the
    // Consensus pipeline ran"; a Compare run never runs it.
    const config = {
      agentMode: false,
      autoConsensus: false,
      deepSearch,
      useOwnKeys,
      providers: providers.map(provider => ({ ...provider })),
      systemPrompt: currentSystemPrompt()
    };

    // A comparison is always a new chat of its own: it continues nothing,
    // also when a saved chat is open.
    let context;
    try {
      context = registry.create({
        question,
        mode: getActiveMode(),
        config,
        basis: null,
        followup: false,
        historyTurns: [],
        bookmarkId: "",
        bookmarkTitle: question,
        usage,
        attachments,
        attachmentMeta,
        metadata: { draftQuestion, quotedContext }
      });
    } catch (error) {
      if (error?.code === "parallel_limit") {
        window.App.showPopup?.(error.message);
        trackAppEvent("app_query_blocked", { reason: error.code });
        return null;
      }
      throw error;
    }

    context.bookmark.id = context.bookmark.id || bookmarkIdForRun(context.runId);
    context.credentials = Object.fromEntries(
      ["openrouterKey"].map(key => [key, String(localStorage.getItem(key) || "")])
    );
    config.providers.forEach(provider => {
      context.modelResults[provider.provider] = {
        provider: provider.provider,
        modelId: provider.modelId,
        modelLabel: provider.modelLabel,
        boxId: provider.boxId,
        status: "pending",
        streamText: "",
        text: "",
        sources: [],
        rawSources: [],
        error: null
      };
    });
    context.progress.totalModels = config.providers.length;
    context.controllers.query = new AbortController();
    context.cancelHook = (reason) => {
      Object.values(context.modelResults).forEach(result => {
        if (["pending", "reasoning", "streaming"].includes(result.status)) {
          result.status = "canceled";
          result.error = "Request canceled.";
        }
      });
      context.bookmark.status = "canceled";
      if (registry.isVisible(context.runId) && context.phase === "prepare") {
        restoreComposerAfterUnsentRun(context);
      }
      clearSensitiveRunData(context);
      releaseUnusedUsage(context, { allowAfterLogout: reason === "logout" });
    };

    registry.update(context.runId, () => {});
    registry.setStatus(context.runId, "running");
    return context;
  }

  function handComposerToRun(context) {
    window.App.clearQuestionDraft?.();
    const input = document.getElementById("questionInput");
    if (input) {
      input.value = "";
      input.dispatchEvent(new Event("input", { bubbles: true }));
      window.syncDemoChipState?.();
    }
    window.App.quote?.clear?.();
    const sentAttachments = window.App.attachments?.detachForMessage?.() || context.attachmentMeta;
    context.attachmentMeta = sentAttachments.map(item => ({ name: item.name, mime: item.mime, size: item.size || 0 }));
    window.App.composer?.collapse?.({ force: true });
    registry.renderVisible();
    // This is tied to the user's send gesture. Background projections never
    // invoke it, so a late run cannot steal the reader's scroll position.
    window.App.revealSentMessage?.();
  }

  window.sendQuestion = async function () {
    // Where the composer stands, read before the send writes anything
    // (app-core.js glideComposer).
    window.App.anchorGlide?.();
    const visible = registry.visible();
    if (visible && registry.isExecuting(visible.runId)) {
      // Words in the field: Send hands them to the running response or its
      // queue (agent-chat.js steer); an empty field means Stop.
      if (window.App.agentChat?.steering?.()) {
        await window.App.agentChat.steer();
        return;
      }
      // The first rapid repeat is a duplicate gesture, not an intentional stop.
      if (Date.now() - visible.startedAt < 450) return;
      registry.cancel(visible.runId, "user");
      trackAppEvent("app_query_canceled");
      return;
    }
    // A file still being read belongs to this draft. Sending now would either
    // drop it silently or let it surface later next to another question.
    if (window.App.attachments?.isImporting?.()) {
      window.App.showPopup?.("An attachment is still being added. Send again when it appears.");
      return;
    }
    if (!registry.claimStartAction()) return;
    // A guest's question is kept and the sign-in opens; it is sent once the
    // session can run it (composer-invite.js).
    if (window.App.composerInvite?.sendAsGuest?.()) return;

    if (window.App.agentChat?.isSelected?.()) {
      if (window.updateQuestionInputAccess && !window.updateQuestionInputAccess()) return;
      if (window.validateInputText && !window.validateInputText()) return;
      await window.App.agentChat.send();
      return;
    }

    const selectedCount = window.App.getSelectedModelCount?.() || 0;
    if (selectedCount < 2) {
      window.updateQuestionInputAccess?.();
      trackAppEvent("app_query_blocked", { reason: "minimum_models", selected_models: selectedCount });
      return;
    }
    if (window.updateQuestionInputAccess && !window.updateQuestionInputAccess()) return;
    if (window.validateInputText && !window.validateInputText()) return;

    const draftQuestion = document.getElementById("questionInput")?.value || "";
    const quotedContext = window.App.quote?.text?.() || "";
    // Files without words go out under their names, as in Agent (attachments.js messageText).
    const question = String(window.App.quote?.compose?.(draftQuestion) ?? draftQuestion).trim()
      || window.App.attachments?.messageText?.() || "";
    if (!question) return;

    if (isDemoQuery(question) && !registry.getSelectedConversationBasis()) {
      window.App.state.set("lastQuestion", question, "run");
      await window.runDemoFlow?.(question);
      return;
    }

    const useOwnKeys = document.getElementById("useOwnKeysSwitch")?.checked === true;
    const deepThink = document.getElementById("reasoningToggle")?.checked === true;
    const runMode = deepThink ? "deep_think" : "compare";
    if (window.App.usageLimit?.blockIfExhausted?.({ useOwnKeys, deepThink, mode: runMode, source: "send" })) {
      trackAppEvent("app_query_blocked", { reason: "usage_limit" });
      return;
    }
    window.App.usageLimit?.hide?.();

    const context = beginContext(String(question).trim(), draftQuestion, quotedContext);
    if (!context) return;
    handComposerToRun(context);
    trackAppEvent("app_query_started", {
      mode: context.mode,
      selected_models: context.progress.totalModels,
      custom_credentials: context.config.useOwnKeys,
      logged_in: true
    });
    window.App.trackAsk?.(context);
    await executeRun(context);
  };

  window.cancelCurrentQuery = function (runId = null) {
    const target = runId || registry.visible()?.runId;
    if (!target) return false;
    const context = registry.get(target);
    if (!context || !registry.isExecuting(target)) return false;
    if (!["prepare", "answers"].includes(context.phase)) return false;
    const canceled = registry.cancel(target, "user");
    if (canceled) trackAppEvent("app_query_canceled");
    return canceled;
  };

  window.isQueryRequestRunning = function (runId = null) {
    const context = registry.get(runId || registry.visible()?.runId);
    return Boolean(context && registry.isExecuting(context.runId) && ["prepare", "answers"].includes(context.phase));
  };

  function isRunActive() {
    const context = registry.visible();
    return Boolean(context && registry.isExecuting(context.runId));
  }

  const SEND_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 19V5.5M6 11.5l6-6 6 6" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"></path></svg>';
  const STOP_ICON = '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><rect x="8" y="8" width="8" height="8" rx="1.6"></rect></svg>';

  function setSendButtonRunning(running) {
    const button = document.getElementById("sendButton");
    if (!button) return;
    // Text typed while an Agent response runs: Send, not Stop (agent-chat.js).
    const steer = running ? window.App.agentChat?.steering?.() : null;
    const stop = running && !steer;
    const state = stop ? "stop" : "send";
    // Many projections call this per second; only a real change swaps the
    // icon, so its entry animation plays once instead of on every update.
    if (button.dataset.icon !== state) {
      if (stop && button.dataset.icon === "send") {
        // The question fans out: three arcs leave the button (shell.css).
        // A launch still on screen restarts (a reflow between); the usual
        // first send needs none, so the click forces no style pass.
        if (button.classList.contains("is-launching")) {
          button.classList.remove("is-launching");
          void button.offsetWidth;
        }
        button.classList.add("is-launching");
        clearTimeout(button._launchTimer);
        button._launchTimer = setTimeout(() => button.classList.remove("is-launching"), 800);
      }
      // The arrow comes back the way the stop square came: the same short
      // fade and scale (Apple audit C12), not in one frame.
      button.classList.toggle("is-returning", !stop && button.dataset.icon === "stop");
      clearTimeout(button._returnTimer);
      if (button.classList.contains("is-returning")) {
        button._returnTimer = setTimeout(() => button.classList.remove("is-returning"), 400);
      }
      button.dataset.icon = state;
      button.innerHTML = stop ? STOP_ICON : SEND_ICON;
    }
    button.disabled = false;
    button.setAttribute("aria-disabled", "false");
    button.classList.toggle("is-cancel-action", stop);
    button.title = steer ? steer.title : running ? "Cancel this run" : "Send question";
    button.setAttribute("aria-label", button.title);
    if (!running) window.updateQuestionInputAccess?.();
  }

  function syncSendButtonRunning() {
    setSendButtonRunning(isRunActive());
  }

  window.isRunActive = isRunActive;
  window.App.syncSendButtonRunning = syncSendButtonRunning;
})();
