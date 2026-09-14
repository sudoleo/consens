// Single-model execution, using the shared composer, run registry and history.
(function () {
  "use strict";
  const App = window.App = window.App || {};
  const registry = App.runRegistry;
  let preference = "consensus";

  function canUse() {
    const access = App.agentAccess;
    return Boolean(window.auth?.currentUser?.uid && access?.uid === window.auth.currentUser.uid && access.allowed);
  }
  function selectedMode() {
    const context = registry.visible();
    if (context) return context.config.executionMode || "consensus";
    const basis = registry.getSelectedConversationBasis();
    if (basis) return basis.executionMode || "consensus";
    return canUse() ? preference : "consensus";
  }
  function render() {
    const agent = selectedMode() === "agent";
    document.body.classList.toggle("single-agent-active", agent);
    const label = document.getElementById("chatExecutionControl");
    const select = document.getElementById("chatExecutionMode");
    const locked = Boolean(registry.visible() || registry.getSelectedConversationBasis());
    if (label) label.hidden = !canUse() && !agent;
    if (select) {
      select.value = agent ? "agent" : "consensus";
      select.disabled = locked || !canUse();
      select.title = locked ? "Start a new chat to change mode" : "Chat mode";
    }
    const panel = document.getElementById("agentAnswer");
    const context = registry.visible();
    const basis = registry.getSelectedConversationBasis();
    if (!agent || !context) {
      const history = document.getElementById("threadHistory");
      if (history) delete history.dataset.agentHistory;
    }
    const recover = document.getElementById("agentRecover");
    if (recover) recover.hidden = !agent || context?.status !== "failed" || !context?.metadata.requestSent;
    if (panel) panel.hidden = !agent || (!context && !basis);
    if (agent && !context && basis) renderAnswer(basis.consensus || "", "", "Agent · Beta");
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
    const signature = JSON.stringify(context.historyTurns);
    if (history && history.dataset.agentHistory !== signature) {
      App.followup?.renderStoredTurns?.(context.historyTurns);
      history.dataset.agentHistory = signature;
    }
    const state = context.consensus;
    renderAnswer(state.text || state.streamText || "", state.error?.message || "",
      registry.isExecuting(context.runId) ? "Agent · responding…" : "Agent · Beta");
    App.syncSendButtonRunning?.();
  }
  function apiError(data) {
    const error = data?.error || data?.detail;
    return typeof error === "string" ? error : error?.error || "The agent request failed.";
  }
  async function send(recovery = null) {
    if (!canUse()) { App.showPopup?.("Agent Beta is available to Pro users and admins."); return; }
    if (window.getAttachmentsPayload?.()?.length) {
      App.showPopup?.("Agent Beta currently supports text only. Remove the attachments to continue.");
      return;
    }
    const input = document.getElementById("questionInput");
    const draft = input?.value || "";
    const question = recovery?.question || String(App.quote?.compose?.(draft) ?? draft).trim();
    if (!question) return;
    const basis = recovery?.basis || registry.getSelectedConversationBasis();
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
          deepSearch: false, checkSources: false, useOwnKeys: false, providers: [] },
        usage: { status: "simulation", key: null },
      });
    } catch (error) { App.showPopup?.(error.message); return; }
    if (basis?.currentTurn) context.historyTurns.push(basis.currentTurn);
    context.controllers.query = new AbortController();
    const signal = context.controllers.query.signal;
    context.consensus.status = "pending";
    context.cancelHook = () => {
      context.consensus.status = "canceled";
      context.consensus.error = { message: "Response stopped." };
      context.bookmark.status = "canceled";
      if (context.basis) registry.selectConversationBasis(context.basis);
    };
    registry.setStatus(context.runId, "running");
    if (!recovery) {
      App.clearQuestionDraft?.();
      if (input) { input.value = ""; input.dispatchEvent(new Event("input", { bubbles: true })); }
      App.quote?.clear?.();
    }
    App.composer?.collapse?.({ force: true });
    App.revealSentMessage?.();
    let timer;
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
      context.metadata.chatId = chatId;
      context.metadata.requestSent = true;
      context.phase = "answers";
      context.consensus.status = "streaming";
      registry.update(context.runId, () => {});
      const result = await window.streamSSERequest("/agent", {
        chat_id: chatId, question, client_request_id: context.requestIdentity,
        bookmark_id: context.bookmark.id,
        recover_only: Boolean(recovery),
      }, signal, {
        delta: { append(text) {
          if (!registry.isExecuting(context.runId) || !registry.isAuthCurrent(context)) return;
          context.consensus.streamText += text;
          if (!timer) timer = setTimeout(() => { timer = null; registry.update(context.runId, () => {}); }, 100);
        } },
      }, { headers });
      if (!registry.isAuthCurrent(context) || signal.aborted) return;
      if (!result.ok || result.data?.error || !result.data?.turn) throw new Error(apiError(result.data));
      const data = result.data;
      const turn = { ...data.turn, turn_id: data.turn_id };
      context.consensus.text = data.response;
      context.consensus.streamText = data.response;
      context.consensus.status = "complete";
      context.consensus.completedTurn = turn;
      context.bookmark.status = "succeeded";
      context.persistence.consensusWrite = true;
      context.phase = "done";
      const conversation = { runId: context.runId, auth: context.auth, bookmarkId: context.bookmark.id,
        chatId: data.chat_id, turnId: data.turn_id };
      window.acceptPersistedConsensusBookmark?.(data.bookmark_meta, conversation);
      registry.setStatus(context.runId, "succeeded");
      registry.setCompletedBasis(context.runId, {
        ...conversation, executionMode: "agent", question, consensus: data.response,
        currentTurn: turn, historyTurns: context.historyTurns, title: context.bookmark.title,
      });
    } catch (error) {
      if (error.name === "AbortError" || !registry.isAuthCurrent(context)) return;
      context.consensus.status = "error";
      context.consensus.error = { message: error.message };
      context.bookmark.status = "failed";
      registry.setStatus(context.runId, "failed", { message: error.message });
      if (context.basis) registry.selectConversationBasis(context.basis);
    } finally {
      clearTimeout(timer);
      context.controllers.query = null;
      if (registry.isAuthCurrent(context)) registry.renderVisible();
    }
  }
  App.agentChat = { canUse, isSelected: () => selectedMode() === "agent", render, project, send };
  window.addEventListener("consensio:run-registry-change", render);
  document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("chatExecutionMode")?.addEventListener("change", event => {
      preference = canUse() && event.target.value === "agent" ? "agent" : "consensus";
      render();
    });
    document.getElementById("agentRecover")?.addEventListener("click", () => {
      const context = registry.visible();
      if (context?.status === "failed" && context.metadata.requestSent) send(context);
    });
    render();
  });
})();
