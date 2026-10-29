// Projects the selected RunContext into the one main application DOM.
// Background callbacks only mutate their context; this adapter is the only
// place that mirrors run-owned data into compatibility globals and elements.
// An Agent run is handed to agent-chat.js; everything else is a Compare run
// (the models' answers side by side). Until 2026-10-25 a run here could also
// carry a Consensus synthesis; the browser no longer runs one.
(function () {
  "use strict";

  window.App = window.App || {};
  const registry = window.App.runRegistry;
  if (!registry) return;

  // Familien aus der einen Frontend-Quelle (window.App.modelPrefs).
  function providers() {
    return (window.App.modelPrefs || []).map(pref => ({
      provider: pref.key,
      boxId: pref.responseId,
      textId: pref.textId
    }));
  }

  let projectedRunId = null;
  const modelProjections = new Map();

  function selectedConfig(context, provider) {
    return (context.config?.providers || []).find(item => item.provider === provider) || null;
  }

  function renderModel(context, definition, force) {
    const box = document.getElementById(definition.boxId);
    const output = box?.querySelector(".collapsible-content");
    if (!box || !output) return;

    const config = selectedConfig(context, definition.provider);
    const result = context.modelResults[definition.provider] || null;
    const selected = Boolean(config);
    box.classList.toggle("excluded", !selected);
    const status = result?.status || "pending";
    const markdown = String(result?.text || result?.streamText || "");
    const signature = JSON.stringify([context.runId, config, status, markdown,
      result?.error, result?.sources, context.evidenceSources]);
    const previous = modelProjections.get(definition.provider);
    // Other models' tokens must not restart this model's loading animation
    // or reparse its unchanged Markdown, math and source links.
    if (!force && previous?.output === output && previous.signature === signature) return;
    modelProjections.set(definition.provider, { output, signature });
    delete box.dataset.responseError;
    delete box.dataset.responseSkipped;
    delete box.dataset.consensusAnswer;
    delete box.dataset.consensusSources;
    output.classList.remove("is-streaming");

    const modelText = document.getElementById(definition.textId);
    if (modelText && config?.modelLabel) modelText.textContent = config.modelLabel;

    if (!selected) {
      box.dataset.responseState = "idle";
      output.replaceChildren();
      return;
    }

    box.dataset.responseState = status === "streaming" ? "pending" : status;
    if (status === "incomplete" && markdown) {
      // R06: keep the partial text visible, clearly labelled as incomplete.
      box.dataset.consensusAnswer = markdown;
      window.injectMarkdown?.(output, markdown, context.evidenceSources);
      const note = document.createElement("p");
      note.className = "response-incomplete-notice";
      note.setAttribute("role", "note");
      note.textContent = result?.error || "This answer is incomplete.";
      output.prepend(note);
      return;
    }
    if (status === "error" || status === "skipped" || status === "canceled") {
      box.dataset.responseError = "true";
      if (status === "skipped") box.dataset.responseSkipped = "true";
      output.textContent = result?.error || (status === "canceled" ? "Request canceled." : "The model request failed.");
      return;
    }

    if (markdown) {
      box.dataset.consensusAnswer = markdown;
      box.dataset.consensusSources = JSON.stringify(result?.sources || []);
      window.injectMarkdown?.(output, markdown, context.evidenceSources);
      if (status === "streaming") output.classList.add("is-streaming");
      return;
    }

    if (["pending", "reasoning", "streaming"].includes(status)) {
      output.innerHTML = window.spinnerHTML || "";
      if (status === "reasoning") {
        const label = output.querySelector(".thinking.typing-indicator");
        if (label) {
          label.dataset.text = "Reasoning";
          label.setAttribute("aria-label", "Reasoning");
        }
      }
      return;
    }
    output.replaceChildren();
  }

  // A comparison has no consensus answer. A saved Consensus answer that was
  // on screen before leaves with its markers, verdict and footer.
  function clearConsensus() {
    const output = document.getElementById("consensusOutput");
    if (output) {
      output.classList.add("is-hidden");
      output.classList.remove("is-visible");
    }
    const response = document.getElementById("consensusResponse");
    window.resetConsensusInsights?.();
    window.resetCredibilityFrame?.(response?.querySelector(".consensus-differences"));
    window.App.consensusBodyEl?.(response)?.replaceChildren();
    response?.querySelector(".consensus-differences p")?.replaceChildren();
    window.App.consensusFooter?.clear?.();
  }

  function syncCompatibilityState(context) {
    window.App.state.set("lastQuestion", context.question, "run");
    window.App.state.set("currentEvidenceSources", context.evidenceSources || [], "evidence");
    window.App.state.set("consensusCitationMeta", null, "consensus");
    window.App.state.set("lastShareResultId", null, "share");
    window.lastQuestionAttachmentsMeta = context.attachmentMeta || [];
    window.App.bookmarkSession?.restore?.(context.bookmark.id);
  }

  // A projection is a one-way DOM write, and several of the surfaces it
  // writes into report back: the tier sync rebuilds the model picker, and the
  // picker asks the registry to render the visible run again. That is a
  // cycle -- project -> updateUserTierUI -> restoreModelSelections ->
  // setModelSelectionState -> renderVisible -> project -- and it ended in
  // "Maximum call stack size exceeded", which the run then reported as a
  // failure right after /prepare. A render requested while one is already
  // running is by definition redundant: it would read the same context and
  // write the same DOM, and everything the nested caller changed is
  // re-asserted from the run further down this same pass.
  let projecting = false;

  function project(context) {
    if (projecting) return;
    projecting = true;
    try {
      window.App.chatScroll?.project(context);
      renderProjection(context);
    } finally {
      projecting = false;
      window.App.chatScroll?.changed();
    }
  }

  function renderProjection(context) {
    window.App.agentChat?.render?.();
    if (context?.config?.executionMode === "agent") {
      projectedRunId = null;
      modelProjections.clear();
      window.App.agentChat.project(context);
      return;
    }
    if (!context) {
      projectedRunId = null;
      modelProjections.clear();
      window.projectAgentModeRun?.(null);
      // Nothing on screen belongs to a run any more: a saved bookmark, or a
      // cleared view. A run still going in the background reports itself in
      // its sidebar row. A saved answer draws its own footer (firebase.js).
      window.App.consensusFooter?.clear?.();
      window.App.syncSendButtonRunning?.();
      return;
    }
    const switched = projectedRunId !== context.runId;
    projectedRunId = context.runId;

    // Only when the run actually disagrees with the tier on screen. Pushing
    // it on every pass rebuilt the whole model picker for each streamed
    // chunk, and the picker's own restore is what closed the cycle above.
    // "is_pro_user: false" heisst seit der Plus-Stufe nur noch "nicht Pro" --
    // es unterscheidet Free nicht mehr von Plus. Ein Lauf ohne ausdrueckliches
    // "tier" (aeltere Antwort, Tab von vor einem Deploy) darf die Stufe auf dem
    // Schirm deshalb nur noch ANHEBEN, nie senken: sonst schaltet ein
    // Plus-Konto beim ersten projizierten Lauf zurueck auf Free und verliert
    // Anhaenge.
    const runTier = context.usage?.tier
      ?? (context.usage?.isProUser === true ? "pro" : null);
    if (runTier !== null
      && (window.App.normalizeTier?.(runTier) || "free") !== (window.userTier || "free")) {
      window.updateUserTierUI?.(runTier, true);
    }

    window.enterDirectComparisonView?.();
    window.App.setAppTitle?.(context.question);
    // Auch der Direktvergleich zeigt die Frage: er fuehrt keinen Thread, aber
    // ohne sie steht auf dem Schirm nur noch die Antwort auf etwas, das
    // nirgends mehr geschrieben steht.
    window.App.setThreadQuestion?.(context.question);
    // A comparison never checks a pasted text: the card of an Agent turn
    // must not stay on this one.
    window.App.passageCheck?.apply(document.getElementById("agentAnswerBody"), null);
    window.App.setThreadQuestionAttachments?.(context.attachmentMeta || []);
    if (switched) {
      // A comparison continues nothing: no history above it, and nothing of
      // a saved answer that was on screen before.
      window.App.followup?.clearHistory?.();
      clearConsensus();
    }
    window.App.followup?.reset?.();
    providers().forEach(provider => renderModel(context, provider, switched));
    window.renderEvidenceSources?.(context.evidenceSources || []);
    syncCompatibilityState(context);
    window.projectAgentModeRun?.(context);
    window.syncHeroResponseAccess?.();
    window.App.syncSendButtonRunning?.();

    window.App.answerReader?.project?.(context);
  }

  function statusLabel(context) {
    if (context.status === "succeeded") return "Completed";
    if (context.status === "failed") return "Failed";
    if (context.config?.executionMode === "agent") {
      if (context.status === "canceled") return "Stopped";
      // A pause waits for the user (agent-chat.js renderHold): said in the
      // row of every chat, also one not on screen (A-B2; before it read
      // "Working" while its pause ran into the timeout unseen).
      const hold = context.metadata?.hold;
      if (hold) return hold.ask ? window.App.words?.yourTurn || "Waiting for you" : window.App.words?.paused || "Paused";
      const latest = context.metadata?.agentActivity?.filter(event => event.kind === 'status').at(-1);
      if (latest?.status === 'waiting') return 'Waiting for allowance';
      if (context.consensus?.streamText) return "Writing answer";
      if (context.metadata?.agentActivity?.some(event => event.kind === "reasoning")) return "Thinking";
      return "Working";
    }
    if (context.status === "canceled") return "Stopped";
    if (context.phase === "prepare") return "Preparing";
    if (context.phase === "answers") return "Models answering";
    return "Running";
  }

  const RUN_STATUSES = ["starting", "running", "succeeded", "failed", "canceled"];
  function setIfChanged(element, property, value) {
    if (element[property] !== value) element[property] = value;
  }
  function setAttributeIfChanged(element, name, value) {
    if (element.getAttribute(name) !== value) element.setAttribute(name, value);
  }
  // A run's row is built once; afterwards only what changed is written, so
  // its pulse runs on instead of restarting with every registry event
  // (Apple audit C7). It has a saved row's height and becomes the saved row
  // in place when the chat is saved (firebase.js replacePendingBookmarkWithReady),
  // so the list below it never moves (A11).
  function ensureRunRow(context) {
    if (!context?.bookmark?.id || !context.auth?.uid) return;
    if (context.bookmark.deleted || context.bookmark.deleting) return;
    if (context.bookmark.uiReady) return;
    const container = document.getElementById("bookmarksContainer");
    if (!container) return;
    let row = document.querySelector(`.bookmark[data-run-id="${context.runId}"]`);
    if (!row) {
      row = document.createElement("div");
      row.className = "bookmark run-entry";
      row.dataset.runId = context.runId;
      row.dataset.id = context.bookmark.id;
      row.setAttribute("role", "button");
      row.setAttribute("tabindex", "0");
      const label = document.createElement("p");
      const status = document.createElement("span");
      status.className = "run-entry-status";
      status.setAttribute("aria-hidden", "true");
      row.append(label, status);
      const savedRow = document.querySelector(
        `.bookmark:not(.run-entry)[data-id="${context.bookmark.id}"]`
      );
      if (savedRow) {
        // A follow-up keeps its chat's place and marking.
        if (savedRow.classList.contains("is-active")) row.classList.add("is-active");
        savedRow.replaceWith(row);
      } else {
        container.prepend(row);
        window.App.bookmarkUi?.insertSoftly?.(row);
      }
    }
    for (const status of RUN_STATUSES) row.classList.toggle(`run-status-${status}`, status === context.status);
    row.classList.toggle("is-pending", context.status === "starting" || context.status === "running");
    // Waiting for the user: nothing works, so nothing pulses (layout.css).
    row.classList.toggle("is-paused", (context.status === "starting" || context.status === "running")
      && Boolean(context.metadata?.hold));
    setAttributeIfChanged(row, "aria-label", `${context.bookmark.title || context.question}. ${statusLabel(context)}. Open run.`);
    setIfChanged(row, "title", `${statusLabel(context)} — open this run`);
    const label = row.querySelector(":scope > p");
    // The whole name; the row's own ellipsis cuts it where the space ends.
    if (label) setIfChanged(label, "textContent", String(context.bookmark.title || context.question || "New chat").replace(/\s+/g, " ").trim());
    const status = row.querySelector(":scope > .run-entry-status");
    if (status) setIfChanged(status, "textContent", context.persistence?.errors?.length && context.status === "succeeded"
      ? `${statusLabel(context)} · not saved`
      : statusLabel(context));
  }

  // One listener for every run row, also one that became a saved row in
  // place (firebase.js serves those).
  function openRunRow(row) {
    if (!registry.get(row.dataset.runId)) return;
    registry.show(row.dataset.runId);
    window.App.chatScroll?.opened?.();
  }
  document.addEventListener("click", event => {
    const row = event.target.closest?.("#bookmarksContainer .bookmark.run-entry[data-run-id]");
    if (row) openRunRow(row);
  });
  document.addEventListener("keydown", event => {
    if (event.key !== "Enter" && event.key !== " ") return;
    const row = event.target.closest?.("#bookmarksContainer .bookmark.run-entry[data-run-id]");
    if (!row || event.target !== row) return;
    event.preventDefault();
    openRunRow(row);
  });

  window.addEventListener("consensio:run-registry-change", event => {
    const context = event.detail?.context;
    if (context) {
      ensureRunRow(context);
      if (context.status === "succeeded") window.App.bookmarkUi?.finalizeRun?.(context);
    }
  });

  window.App.runView = Object.freeze({ project, ensureRunRow });
  registry.setProjector(project);
})();
