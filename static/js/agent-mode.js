// =====================================================================
// agent-mode.js
// Grouped model run panel (timer, status, answer previews) and the composer
// controls for the next message. Which mode runs (Compare, Consensus, Agent)
// is owned by run-mode.js; this module renders the one selector for it and
// the tools that apply to the chosen mode. The "agent-mode" names here are
// historical and describe the grouped run panel, not Agent (Beta).
// State (Status/Timer) ist modul-privat; agentModeStatus wird extern via
// window.isAgentModeRunning() gelesen.
// Exporte: window.setAgentModeStatus, window.updateAgentModeUI,
// window.projectAgentModeRun, window.isAgentModeRunning.
// Abhaengigkeiten: window.App.{modelPrefs,
// getModelOptionLabel,getSelectedModelCount,trackAppEvent,initCustomModelPicker},
// window.updateConsensusButtonAvailability.
// =====================================================================

(function () {
  const AGENT_PANEL_COLLAPSED_KEY = "agentModePanelCollapsed";
  let checkSources = true;
  try { checkSources = localStorage.getItem("checkSources") !== "false"; } catch (_) {}
  // Preserve the preference, but direct comparisons have no judges.
  const isBeta = () => window.App.agentChat?.isSelected?.() === true;
  const runMode = () => window.App.runMode.effective();
  // The consensus pipeline runs unless the next message is a Compare.
  const pipelineEnabled = () => window.App.runMode.pipeline();
  window.App.isSourceCheckEnabled = () => pipelineEnabled() && checkSources;

  function setSourceCheckEnabled(enabled) {
    if (!pipelineEnabled()) {
      renderComposerMode();
      return;
    }
    checkSources = !!enabled;
    try { localStorage.setItem("checkSources", String(checkSources)); } catch (_) {}
    renderComposerMode();
  }

  // Panel defaults to expanded so model names are visible at once. Applies
  // only until the person collapses it; that choice is kept.
  try {
    if (localStorage.getItem(AGENT_PANEL_COLLAPSED_KEY) === null) {
      localStorage.setItem(AGENT_PANEL_COLLAPSED_KEY, "false");
    }
  } catch (e) { /* localStorage gesperrt: Default bleibt aus */ }

  let agentModeStatus = "idle";
  let agentModeStatusMessage = "";
  let agentModeTimerStartedAt = null;
  let agentModeTimerElapsedMs = 0;
  let agentModeTimerInterval = null;
  // When a RunContext is selected, the panel is a projection of that frozen
  // run rather than a reflection of the controls that configure the next run.
  let projectedRunContext = null;
  // Session-only disclosure: every new grouped run starts in the clean view.
  let modelAnswersVisible = false;

  // Der geschaetzte Stream-Fortschritt pro Modell ist mit dem Balken im
  // gefuehrten Lauf entfallen (siehe consensus-progress.js): waehrend die
  // Antworten sichtbar streamen, war er eine zweite, geratene Auskunft ueber
  // dasselbe. Was bleibt, ist die gemessene Zeit pro Modell.

  function isTerminalResponseState(state) {
    return state === "complete" || state === "error" || state === "incomplete";
  }

  // ---- Einzelantworten als Vorschau statt als Scroll-Schacht --------------
  // Hinter "Compare answers" hatte jede Box ihren eigenen Innen-Scroll
  // (max-height + overflow-y in components-misc.css). Sechs private
  // Scroll-Bereiche in einer scrollenden Seite heissen: das Mausrad tut je
  // nach Zeigerposition etwas anderes, die Spalten enden auf verschiedenen
  // Hoehen, und lange Antworten sind abgeschnitten, ohne dass es jemand
  // ansagt - ausgerechnet in der Ansicht, deren einziger Zweck der Vergleich
  // ist. Stattdessen: gleich hohe Vorschauen mit Ausblendkante, und ein Knopf
  // oeffnet genau die eine Antwort ganz.
  //
  // Geklappt wird nur, was wirklich ueberlaeuft, und nie waehrend des
  // Streams: waehrend die Antwort noch waechst, will man sie wachsen sehen.
  const ANSWER_PREVIEW_HEIGHT = 300;
  const ANSWER_PREVIEW_SLACK = 48;

  function isAnswerSettled(box) {
    const content = box.querySelector(".collapsible-content");
    if (!content) return false;
    if (content.classList.contains("is-streaming")) return false;
    if (content.querySelector(".thinking-wrap")) return false;
    return isTerminalResponseState(box.dataset.responseState || "");
  }

  function answerToggleLabel(open) {
    return open ? "Show less" : "Show full answer";
  }

  function ensureAnswerToggle(box) {
    let btn = box.querySelector(".response-answer-more");
    if (btn) return btn;
    btn = document.createElement("button");
    btn.type = "button";
    btn.className = "response-answer-more";
    btn.addEventListener("click", function () {
      const open = box.dataset.answerOpen !== "1";
      box.dataset.answerOpen = open ? "1" : "0";
      box.classList.toggle("is-clamped", !open);
      btn.textContent = answerToggleLabel(open);
      btn.setAttribute("aria-expanded", String(open));
      window.App?.trackAppEvent?.("app_model_answer_expanded", {
        model: box.dataset.model || box.id,
        open: open
      });
    });
    box.appendChild(btn);
    return btn;
  }

  function syncAnswerPreviews() {
    if (window.App?.answerReader) return;
    document.querySelectorAll(".response-section > .response-box").forEach(box => {
      const content = box.querySelector(".collapsible-content");
      const existing = box.querySelector(".response-answer-more");
      const eligible = modelAnswersVisible
        && !box.classList.contains("excluded")
        && isAnswerSettled(box);
      if (!content || !eligible) {
        box.classList.remove("is-clamped");
        if (existing) existing.hidden = true;
        return;
      }
      // scrollHeight bleibt auch im geklappten Zustand die volle Hoehe
      // (overflow: hidden), der Test kippt also nicht hin und her.
      const overflows = content.scrollHeight
        > ANSWER_PREVIEW_HEIGHT + ANSWER_PREVIEW_SLACK;
      if (!overflows) {
        box.classList.remove("is-clamped");
        if (existing) existing.hidden = true;
        return;
      }
      const btn = ensureAnswerToggle(box);
      const open = box.dataset.answerOpen === "1";
      btn.hidden = false;
      btn.textContent = answerToggleLabel(open);
      btn.setAttribute("aria-expanded", String(open));
      box.classList.toggle("is-clamped", !open);
    });
  }

  let answerPreviewFrame = 0;
  function scheduleAnswerPreviewSync() {
    if (answerPreviewFrame) return;
    answerPreviewFrame = window.requestAnimationFrame(() => {
      answerPreviewFrame = 0;
      syncAnswerPreviews();
    });
  }

  let answerPreviewResizeTimer = 0;
  window.addEventListener("resize", () => {
    window.clearTimeout(answerPreviewResizeTimer);
    answerPreviewResizeTimer = window.setTimeout(syncAnswerPreviews, 150);
  });

  function isAgentPanelCollapsed() {
    return localStorage.getItem(AGENT_PANEL_COLLAPSED_KEY) === "true";
  }

  function formatAgentElapsed(ms) {
    const totalSeconds = Math.max(0, Math.floor(ms / 1000));
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }

  function updateAgentModeTimerDisplay() {
    const timerEl = document.getElementById("agentModeTimer");
    if (!timerEl) return;
    const elapsed = agentModeTimerStartedAt
      ? Date.now() - agentModeTimerStartedAt
      : agentModeTimerElapsedMs;
    const isVisible = !!agentModeTimerStartedAt || agentModeTimerElapsedMs > 0;
    timerEl.classList.toggle("is-visible", isVisible);
    timerEl.textContent = `Elapsed ${formatAgentElapsed(elapsed)}`;
  }

  function startAgentModeTimer() {
    if (agentModeTimerStartedAt) return;
    agentModeTimerStartedAt = Date.now();
    agentModeTimerElapsedMs = 0;
    window.clearInterval(agentModeTimerInterval);
    updateAgentModeTimerDisplay();
    agentModeTimerInterval = window.setInterval(updateAgentModeTimerDisplay, 1000);
  }

  function stopAgentModeTimer() {
    if (agentModeTimerStartedAt) {
      agentModeTimerElapsedMs = Date.now() - agentModeTimerStartedAt;
    }
    agentModeTimerStartedAt = null;
    window.clearInterval(agentModeTimerInterval);
    agentModeTimerInterval = null;
    updateAgentModeTimerDisplay();
  }

  function resetAgentModeTimer() {
    agentModeTimerStartedAt = null;
    agentModeTimerElapsedMs = 0;
    window.clearInterval(agentModeTimerInterval);
    agentModeTimerInterval = null;
    updateAgentModeTimerDisplay();
  }

  function getActiveAgentModels() {
    // Only a projected run describes itself here. Without a run -- a saved
    // bookmark was opened, or the view was cleared -- the chips come from the
    // controls again; reading `?.config?.agentMode !== false` off nothing was
    // true for null as well and threw on the very next line, which aborted
    // the bookmark restore mid-way and left the previous run on screen.
    if (projectedRunContext && projectedRunContext.config?.agentMode !== false) {
      return (projectedRunContext.config?.providers || []).map(function (provider) {
        const pref = window.App.modelPrefs.find(item => item.key === provider.provider);
        if (!pref) return null;
        const result = projectedRunContext.modelResults?.[provider.provider] || {};
        return {
          pref,
          label: pref.label,
          model: String(provider.modelLabel || provider.modelId || pref.label),
          responseState: String(result.status || "pending"),
          hasAnswer: Boolean(String(result.text || result.streamText || "").trim()),
          // A projected run is immutable. Render its frozen label instead of a
          // picker wired to the controls for the next comparison.
          frozenLabel: true
        };
      }).filter(Boolean);
    }
    return window.App.modelPrefs
      .filter(pref => document.getElementById(pref.checkId)?.checked)
      .map(pref => {
        const select = document.getElementById(pref.selectId);
        const responseBox = document.getElementById(pref.responseId);
        const displayedText = document.getElementById(pref.textId)?.textContent || "";
        const selectedText = window.App.getModelOptionLabel(select?.options[select.selectedIndex]) || select?.value || displayedText;
        const modelText = selectedText.trim();
        return {
          pref,
          label: pref.label,
          model: modelText,
          responseState: responseBox?.dataset?.responseState || "",
          hasAnswer: Boolean(responseBox?.querySelector(".collapsible-content")?.textContent?.trim()),
          frozenLabel: false
        };
      });
  }

  function syncAgentModePicker(agentSelect, pref) {
    const sourceSelect = document.getElementById(pref.selectId);
    const labelText = document.getElementById(pref.textId);
    if (!sourceSelect || !agentSelect) return;

    sourceSelect.value = agentSelect.value;
    localStorage.setItem("pref_select_" + pref.key, agentSelect.value);
    if (labelText) {
      const selectedLabel = window.App.getModelOptionLabel(agentSelect.options[agentSelect.selectedIndex]) || agentSelect.value;
      labelText.textContent = selectedLabel;
      labelText.title = `Choose model: ${selectedLabel}`;
    }
    sourceSelect.dispatchEvent(new Event("change", { bubbles: true }));
    updateAgentModeUI();
  }

  function getAgentModeStatusText(activeModels) {
    const count = activeModels.length;
    if (count === 0) return "No models selected.";
    if (agentModeStatus === "running") return "Querying selected models in parallel.";
    if (agentModeStatus === "complete") return "Model responses are ready for consensus.";
    if (agentModeStatus === "canceled") return "Request canceled.";
    if (agentModeStatus === "error") return agentModeStatusMessage || "The request could not be completed.";
    return "Ready for a grouped model run.";
  }

  // The one mode selector (composer) and its mirror in Settings. Both are
  // views of App.runMode: options the open chat cannot switch to stay
  // visible but disabled with the reason, Agent only for accounts with access.
  // renderComposerMode runs on every run status tick; the selector only
  // changes when the mode, the open chat's family or the account changes.
  let runModeSignature = "";
  function renderRunModeControl() {
    const mode = runMode();
    const available = window.App.runMode.availability();
    const select = document.getElementById("runModeSelect");
    const setting = document.getElementById("runModeSetting");
    // The displayed values belong to the signature: a refused choice (Compare
    // in an Agent chat) must snap the control back to the real mode.
    const signature = JSON.stringify([mode, window.App.runMode.preference(), available,
      select?.value, setting?.value]);
    if (signature === runModeSignature) return;
    // An open Agent chat offers nothing to switch to (its family is fixed on
    // the server), so the selector steps aside instead of costing the single
    // line composer its width. Settings still holds the choice for new chats.
    const control = document.getElementById("runModeControl");
    if (control) control.hidden = !available.compare.enabled && !available.consensus.enabled;
    if (select) {
      for (const option of Array.from(select.options)) {
        const rule = available[option.value];
        const copy = window.App.runMode.copy(option.value);
        if (option.value === "agent" && !rule.visible) { option.remove(); continue; }
        option.disabled = !rule.enabled;
        option.dataset.description = rule.enabled ? copy.description : rule.reason;
      }
      if (available.agent.visible && !select.querySelector('option[value="agent"]')) {
        const option = document.createElement("option");
        const copy = window.App.runMode.copy("agent");
        option.value = "agent";
        option.textContent = copy.label;
        option.dataset.modelBadge = copy.badge;
        option.dataset.description = available.agent.enabled ? copy.description : available.agent.reason;
        option.disabled = !available.agent.enabled;
        select.appendChild(option);
      }
      if (select.value !== mode) select.value = mode;
      select.title = `Mode: ${window.App.runMode.copy(mode).label}`;
      window.App.initCustomModelPicker?.(select, { menuWidth: 290 });
      window.syncCustomModelPickers?.();
    }
    // Settings holds the choice for new chats, so no per-chat locks apply.
    if (setting) {
      const agentOption = setting.querySelector('option[value="agent"]');
      if (available.agent.visible && !agentOption) {
        const option = document.createElement("option");
        option.value = "agent";
        option.textContent = "Agent · Beta";
        setting.appendChild(option);
      } else if (!available.agent.visible && agentOption) agentOption.remove();
      const preference = window.App.runMode.preference();
      const shown = setting.querySelector(`option[value="${preference}"]`) ? preference : "consensus";
      if (setting.value !== shown) setting.value = shown;
    }
    runModeSignature = JSON.stringify([mode, window.App.runMode.preference(), available,
      select?.value, setting?.value]);
  }

  function onRunModeChoice(mode, source) {
    const available = window.App.runMode.availability()[mode];
    if (!available?.enabled) { renderComposerMode(); return; }
    window.App.runMode.set(mode, { source });
  }

  // Composer controls always describe the next question. The answer reader
  // supplies a separate, frozen summary for the direct comparison on screen.
  function renderComposerMode() {
    const beta = isBeta();
    const mode = runMode();
    const enabled = mode !== "compare";
    renderRunModeControl();
    // Compare/Consensus use the Reasoning switch row; Agent uses the
    // reasoning-effort menu entry instead.
    const reasoningRow = document.getElementById("reasoningToggle")?.closest("label");
    if (reasoningRow) reasoningRow.hidden = beta;
    ["agentReasoningMenuOption", "agentComparisonMenuOption"].forEach(id => {
      const option = document.getElementById(id);
      if (option) option.hidden = !beta;
    });
    const upload = document.getElementById("attachUploadOption");
    if (upload) upload.disabled = false;
    const hint = document.getElementById("attachMenuHint");
    if (hint) {
      hint.dataset.uploadHint ||= hint.textContent;
      hint.textContent = beta ? "PDF, Word, text, images · kept 30 days" : hint.dataset.uploadHint;
    }
    const trigger = document.getElementById("attachTrigger");
    if (trigger) {
      trigger.title = beta ? "Chat options" : "Add attachment";
      trigger.setAttribute("aria-label", trigger.title);
    }
    const sourcesEnabled = window.App.isSourceCheckEnabled();
    const sourcesTitle = enabled
      ? `Check contradictions ${sourcesEnabled ? "on" : "off"} · Check contradictions against existing sources for the next ${beta ? "chat message" : "consensus"}`
      : "Compare has no consensus to check. Choose Consensus or Agent.";
    ["sourceCheckMenuSwitch", "sourceCheckSwitch"].forEach(id => {
      const control = document.getElementById(id);
      if (control) {
        control.checked = sourcesEnabled;
        control.disabled = !enabled;
        control.title = sourcesTitle;
        const label = control.closest("label");
        if (label) label.title = sourcesTitle;
      }
    });
    // Tools follow the mode: Compare has nothing to check, so the (+) menu
    // and the toolbar drop the control instead of showing a dead switch.
    const menuSourcesRow = document.getElementById("sourceCheckMenuSwitch")?.closest("label");
    if (menuSourcesRow) menuSourcesRow.hidden = !enabled;
    const bar = document.getElementById("composerModeBar");
    if (!bar) return;
    const sourcesButton = document.getElementById("composerSourcesToggle");
    if (sourcesButton) {
      sourcesButton.hidden = !enabled;
      sourcesButton.setAttribute("aria-checked", String(sourcesEnabled));
      sourcesButton.disabled = !enabled;
      sourcesButton.title = sourcesTitle;
      document.getElementById("composerSourcesState").textContent = sourcesEnabled ? "On" : "Off";
    }
    // One rule for every mode and width: the tools belong to the start
    // screen (the hero, or the Compare start); in a chat they live in the
    // (+) menu. A docked bar only carries the status of a direct comparison
    // on screen, never tools.
    const start = window.App.composer?.isStartScreen?.() ?? document.body.classList.contains("is-hero");
    const summary = beta ? null : window.App.answerReader?.directSummary?.();
    bar.hidden = !start && !summary;
    bar.dataset.docked = String(!start);
    window.App.attachments?.syncComposerPlacement?.();
    bar.dataset.runMode = mode;
    document.getElementById("composerModeDescription").textContent = window.App.runMode.copy(mode).description;
    const models = window.App.modelPrefs.filter(pref => document.getElementById(pref.checkId)?.checked);
    const comparisonCount = document.querySelector("#agentComparisonMenuOption .attach-menu-value");
    if (comparisonCount) comparisonCount.textContent = String(models.length);
    const icons = document.getElementById("composerModelIcons");
    const reasoningOn = !beta && !!document.getElementById("reasoningToggle")?.checked;
    for (const [buttonId, stateId] of [["composerReasoningToggle", "composerReasoningState"], ["agentReasoningMenuOption", "agentReasoningMenuState"]]) {
      const reasoningButton = document.getElementById(buttonId);
      if (!reasoningButton) continue;
      const effort = document.getElementById("agentReasoningEffort");
      reasoningButton.disabled = beta && (!effort || effort.disabled || effort.dataset.available !== "true");
      reasoningButton.setAttribute("role", beta ? "button" : "switch");
      reasoningButton.setAttribute("aria-checked", String(reasoningOn));
      reasoningButton.title = `Reasoning ${reasoningOn ? "on" : "off"} · Models think longer before they answer`;
      document.getElementById(stateId).textContent = reasoningOn ? "On" : "Off";
      if (beta) {
        reasoningButton.removeAttribute("aria-checked");
        reasoningButton.setAttribute("aria-haspopup", "listbox");
        reasoningButton.title = reasoningButton.disabled ? "Reasoning is unavailable or locked during this run" : "Choose reasoning for your next chat message";
        document.getElementById(stateId).textContent = effort?.selectedOptions[0]?.textContent || "Auto";
      } else reasoningButton.removeAttribute("aria-haspopup");
    }
    const attachButton = document.getElementById("composerAttachButton");
    if (attachButton) {
      attachButton.disabled = false;
      attachButton.title = "Add attachment";
    }
    const labels = models.map(pref => {
      const select = document.getElementById(pref.selectId);
      return window.App.getModelOptionLabel(select?.selectedOptions[0]) || pref.label;
    });
    const key = JSON.stringify(models.map((pref, i) => [pref.key, labels[i]]));
    if (icons.dataset.models !== key) {
      icons.replaceChildren(...models.map((pref, i) => {
        const mark = document.createElement("span");
        mark.className = "composer-model-icon";
        mark.title = `${pref.label} · ${labels[i]}`;
        mark.setAttribute("role", "img");
        mark.setAttribute("aria-label", mark.title);
        const original = document.getElementById(pref.responseId)?.querySelector("img");
        if (original) {
          const image = document.createElement("img");
          image.src = original.src;
          image.alt = "";
          ["chatgpt-logo", "grok-logo", "mono-logo"].forEach(name => {
            if (original.classList.contains(name)) image.classList.add(name);
          });
          mark.append(image);
        } else mark.textContent = pref.label.slice(0, 1);
        return mark;
      }));
      icons.dataset.models = key;
    }
    const status = document.getElementById("composerComparisonStatus");
    status.hidden = !summary;
    // The result on screen keeps its own mode; say so when the next
    // message will run differently.
    status.textContent = summary
      ? `${enabled ? "Shown: Compare result · " : ""}${summary}.`
      : "";
    status.title = status.textContent;
    status.dataset.compact = summary ? summary.replace(/^(\d+) of (\d+) ready/, "$1/$2").replace(/ unavailable$/, "!") : "";
  }

  function updateAgentModeUI() {
    // config.agentMode is the persisted run field for "the consensus
    // pipeline ran"; the name predates the Compare/Consensus/Agent choice.
    const enabled = projectedRunContext
      ? projectedRunContext.config?.agentMode !== false
      : pipelineEnabled();
    const panel = document.getElementById("agentModePanel");
    const modelsEl = document.getElementById("agentModeModels");
    const statusEl = document.getElementById("agentModeStatus");
    const countEl = document.getElementById("agentModeCount");
    const titleEl = document.getElementById("agentModeTitle");
    const answersRow = document.getElementById("agentModeAnswersRow");
    const answersToggle = document.getElementById("agentModeAnswersToggle");
    const activeModels = getActiveAgentModels();

    // Seit 2026-07-27 haengt die Einzelantworten-Disclosure NICHT mehr am
    // Agent Mode. Sie ist eine der drei Aufklapp-Flaechen in der Fusszeile
    // ("Review differences · Compare answers · Verify sources") und war dort
    // in zwei von
    // drei Faellen unsichtbar, obwohl sie das Wichtigste dahinter oeffnet:
    // worauf die Antwort beruht. Der Footer selbst wird erst zusammen mit
    // einer fertigen Consensus-Antwort sichtbar; innerhalb dieses Footers ist
    // der Schalter deshalb immer da. Das vermeidet Sonderfaelle fuer manuell
    // gestartete Consensuses, Bookmarks und nachtraeglich ausgeschlossene
    // Modelle.

    document.body.classList.toggle("agent-mode-enabled", enabled);
    document.body.classList.toggle("agent-mode-running", enabled && agentModeStatus === "running");
    window.App.answerReader?.syncPreview?.(pipelineEnabled(), activeModels);
    // "direct-comparison-active" beschreibt, was GERADE AUF DEM SCHIRM steht,
    // der Agent-Mode-Schalter dagegen, was der NAECHSTE Lauf tut. Umschalten
    // behaelt das angezeigte Ergebnis; erst eine neue Projektion wechselt es.
    // Hero-Desktop zeigt die Response-Boxen nur ohne Agent Mode; inert/
    // aria-hidden muessen der CSS-Sichtbarkeit folgen (app-core.js).
    if (typeof window.syncHeroResponseAccess === "function") {
      window.syncHeroResponseAccess();
    }
    document.body.classList.toggle(
      "agent-mode-show-answers",
      modelAnswersVisible
    );

    if (answersRow) answersRow.hidden = false;
    if (answersToggle) {
      const answersVisible = window.App?.answerReader
        ? window.App.answerReader.isLiveOpen() : modelAnswersVisible;
      const label = answersVisible ? "Hide answers" : "Compare answers";
      answersToggle.setAttribute("aria-expanded", String(answersVisible));
      answersToggle.title = label;
      answersToggle.setAttribute("aria-label", label);
      // Gezielt das Label, nicht "das erste span": der Chip traegt seit
      // 2026-07-28 auch einen Chevron und eine Zahl.
      const labelEl = answersToggle.querySelector(".consensus-tab-label");
      if (labelEl) {
        labelEl.textContent = label;
        // Kurzform fuer die Telefon-Leiste (siehe shell.css): dort steht das
        // Substantiv allein, damit die drei Knoepfe einzeilig bleiben.
        labelEl.dataset.short = answersVisible ? "Hide" : "Answers";
      }
    }

    // The mode selector describes the NEXT message, `enabled` above the run
    // on screen. Controls follow the choice; view and body classes the run.
    renderComposerMode();
    if (panel) panel.setAttribute("aria-hidden", String(!enabled));

    // Eingeklappter Zustand: Panel wird zur Kompaktzeile (Titel, beantwortete
    // Modelle, Laufzeit); Chips/Status sind per CSS ausgeblendet.
    const collapsed = isAgentPanelCollapsed();
    if (panel) panel.classList.toggle("is-collapsed", collapsed);
    const collapseBtn = document.getElementById("agentModeCollapseBtn");
    if (collapseBtn) {
      collapseBtn.setAttribute("aria-expanded", String(!collapsed));
      collapseBtn.title = collapsed ? "Expand to configure models" : "Collapse models panel";
      collapseBtn.setAttribute("aria-label", collapseBtn.title);
    }
    const answeredEl = document.getElementById("agentModeAnswered");
    if (answeredEl) {
      const answeredCount = activeModels.filter(m => m.responseState === "complete").length;
      answeredEl.textContent = `${answeredCount}/${activeModels.length} answered`;
      answeredEl.hidden = !collapsed;
    }
    const collapsedHintEl = document.getElementById("agentModeCollapsedHint");
    if (collapsedHintEl) collapsedHintEl.hidden = !collapsed;

    if (titleEl) {
      titleEl.textContent = agentModeStatus === "running" ? "Models are working" : "Selected models";
    }
    if (countEl) {
      countEl.textContent = `${activeModels.length} ${activeModels.length === 1 ? "model" : "models"}`;
    }
    if (statusEl) {
      statusEl.textContent = getAgentModeStatusText(activeModels);
    }
    if (modelsEl) {
      modelsEl.innerHTML = "";
      activeModels.forEach(modelInfo => {
        const chip = document.createElement("span");
        chip.className = "agent-mode-chip";
        chip.textContent = modelInfo.model
          ? `${modelInfo.label} · ${modelInfo.model}`
          : modelInfo.label;
        chip.setAttribute("role", "group");
        chip.setAttribute("aria-label", `Choose ${modelInfo.label} model`);
        chip.textContent = "";
        chip.dataset.modelKey = modelInfo.pref.key;
        if (modelInfo.responseState) {
          chip.dataset.responseState = modelInfo.responseState;
        }

        const chipLabel = document.createElement("span");
        chipLabel.className = "agent-mode-chip-label";
        chipLabel.textContent = modelInfo.label;
        chip.appendChild(chipLabel);

        const sourceSelect = document.getElementById(modelInfo.pref.selectId);
        if (sourceSelect && !modelInfo.frozenLabel) {
          const picker = document.createElement("select");
          picker.className = "agent-mode-picker";
          picker.setAttribute("aria-label", `Choose ${modelInfo.label} model`);
          Array.from(sourceSelect.options).forEach(option => {
            picker.appendChild(option.cloneNode(true));
          });
          picker.value = sourceSelect.value;
          picker.addEventListener("change", function () {
            syncAgentModePicker(this, modelInfo.pref);
          });
          chip.appendChild(picker);
          window.App.initCustomModelPicker(picker);
        } else if (modelInfo.model) {
          const chipModel = document.createElement("span");
          chipModel.className = "agent-mode-chip-model";
          chipModel.textContent = modelInfo.model;
          chip.appendChild(chipModel);
        }

        if (modelInfo.responseState === "complete") {
          const done = document.createElement("span");
          done.className = "agent-mode-chip-done";
          done.setAttribute("aria-hidden", "true");
          done.title = `${modelInfo.label} response complete`;
          chip.appendChild(done);
          chip.setAttribute("aria-label", `${modelInfo.label} response complete`);
        }
        modelsEl.appendChild(chip);
      });
    }

    // Nach dem Layout messen: die Boxen sind in genau diesem Aufruf sichtbar
    // geworden (agent-mode-show-answers), vorher ist ihre Hoehe 0.
    scheduleAnswerPreviewSync();
  }

  // Every change of the mode (selector, Settings, another tab) arrives here.
  // Switching between Compare and Consensus keeps the result on screen,
  // including a saved direct comparison; only the next message changes.
  function onRunModeChange(event) {
    const previous = event?.detail?.previous;
    const next = event?.detail?.mode;
    if ((previous === "compare") !== (next === "compare")) {
      modelAnswersVisible = false;
      document.body.classList.add("agent-mode-transitioning");
      window.setTimeout(() => {
        document.body.classList.remove("agent-mode-transitioning");
      }, 340);
    }
    updateAgentModeUI();
    // The composer placeholder promises a follow-up only while one exists
    // (consensus-run.js, isArmed); Compare has none.
    window.App?.followup?.render?.();
    if (window.App.runRegistry?.visible?.()) {
      window.App.runRegistry.renderVisible();
    }
    window.App.attachments?.refreshCompatibility?.();
  }

  function setAgentModeStatus(status, message = "") {
    if (status === "running") {
      if (agentModeStatus !== "running") {
        modelAnswersVisible = false;
        // Ein neuer Lauf bringt neue Antworten: die Entscheidung, welche
        // davon ganz aufgeklappt war, gilt fuer die alten.
        document.querySelectorAll(".response-box[data-answer-open]")
          .forEach(box => { delete box.dataset.answerOpen; });
      }
      agentModeStatusMessage = "";
      startAgentModeTimer();
    } else if (status === "complete" || status === "canceled" || status === "error") {
      stopAgentModeTimer();
    } else if (status === "idle") {
      modelAnswersVisible = false;
      agentModeStatusMessage = "";
      resetAgentModeTimer();
    }
    if (message) {
      agentModeStatusMessage = message;
    } else if (status !== "error") {
      agentModeStatusMessage = "";
    }
    agentModeStatus = status;
    updateAgentModeUI();
    if (typeof window.updateConsensusButtonAvailability === "function") {
      window.updateConsensusButtonAvailability();
    }
    // Der Modellstatus bleibt fuer jeden Lauf zentral. Nur Consensus reicht
    // ihn an die gefuehrte Pipeline weiter; der Direktvergleich raeumt sie ab.
    if (pipelineEnabled()) {
      window.App?.consensusPipeline?.onQueryStatus?.(status);
    } else {
      window.App?.consensusPipeline?.dismiss?.();
    }
  }

  function projectAgentModeRun(context) {
    const switched = (projectedRunContext?.runId || null) !== (context?.runId || null);
    projectedRunContext = context || null;
    window.clearInterval(agentModeTimerInterval);
    agentModeTimerInterval = null;

    if (!context || context.config?.agentMode === false) {
      agentModeStatus = "idle";
      agentModeStatusMessage = "";
      agentModeTimerStartedAt = null;
      agentModeTimerElapsedMs = 0;
      if (switched) modelAnswersVisible = false;
      updateAgentModeUI();
      return;
    }

    if (switched) modelAnswersVisible = false;
    if (context.status === "failed") {
      agentModeStatus = "error";
      agentModeStatusMessage = context.error?.message
        || context.consensus?.error?.message
        || "The run failed.";
    } else if (context.status === "canceled") {
      agentModeStatus = "canceled";
      agentModeStatusMessage = "";
    } else if (context.status === "succeeded" || context.phase === "answers_ready") {
      agentModeStatus = "complete";
      agentModeStatusMessage = "";
    } else {
      agentModeStatus = "running";
      agentModeStatusMessage = "";
    }

    const startedAt = Number(context.startedAt || context.createdAt || Date.now());
    if (agentModeStatus === "running") {
      agentModeTimerStartedAt = startedAt;
      agentModeTimerElapsedMs = 0;
      updateAgentModeTimerDisplay();
      agentModeTimerInterval = window.setInterval(updateAgentModeTimerDisplay, 1000);
    } else {
      agentModeTimerStartedAt = null;
      agentModeTimerElapsedMs = Math.max(0, Number(context.finishedAt || Date.now()) - startedAt);
      updateAgentModeTimerDisplay();
    }
    updateAgentModeUI();
  }

  function setModelAnswersVisible(visible, options = {}) {
    if (window.App?.answerReader) {
      if (visible) return window.App.answerReader.openLive();
      window.App.answerReader.close();
      return true;
    }
    const nextVisible = !!visible;
    const changed = modelAnswersVisible !== nextVisible;
    modelAnswersVisible = nextVisible;
    if (changed && options.track) {
      window.App?.trackAppEvent?.("app_agent_mode_answers_toggled", {
        visible: modelAnswersVisible
      });
    }
    updateAgentModeUI();
    if (changed && nextVisible) {
      // Derselbe dezente Reveal wie bei Differences/Sources: erst nachdem die
      // CSS-Klasse die Boxen sichtbar gemacht hat, den Anfang der ersten
      // Antwort mit "nearest" ins Bild holen.
      requestAnimationFrame(() => {
        const firstAnswer = document.querySelector(
          ".response-section > .response-box:not(.excluded)"
        );
        firstAnswer?.scrollIntoView({ block: "nearest", behavior: "smooth" });
      });
    }
    return changed;
  }

  // Einklapp-Pfeil oben rechts im Panel (Zustand wird gemerkt).
  const agentCollapseBtn = document.getElementById("agentModeCollapseBtn");
  if (agentCollapseBtn) {
    agentCollapseBtn.addEventListener("click", function () {
      const next = !isAgentPanelCollapsed();
      localStorage.setItem(AGENT_PANEL_COLLAPSED_KEY, String(next));
      if (window.App && typeof window.App.trackAppEvent === "function") {
        window.App.trackAppEvent("app_agent_mode_panel_toggled", { collapsed: next });
      }
      updateAgentModeUI();
    });
  }

  const agentAnswersToggle = document.getElementById("agentModeAnswersToggle");
  if (agentAnswersToggle) {
    agentAnswersToggle.addEventListener("click", function () {
      if (window.App?.answerReader) {
        window.App.answerReader.toggleLive(this);
        updateAgentModeUI();
        return;
      }
      setModelAnswersVisible(!modelAnswersVisible, { track: true });
    });
  }

  document.getElementById("runModeSelect")?.addEventListener("change", function () {
    onRunModeChoice(this.value, "composer");
  });
  document.getElementById("runModeSetting")?.addEventListener("change", function () {
    window.App.runMode.set(this.value, { source: "settings" });
  });
  window.addEventListener("consensio:run-mode-change", onRunModeChange);
  document.getElementById("composerSourcesToggle")?.addEventListener("click", function () {
    setSourceCheckEnabled(!checkSources);
  });
  ["sourceCheckMenuSwitch", "sourceCheckSwitch"].forEach(id => {
    document.getElementById(id)?.addEventListener("change", function () {
      setSourceCheckEnabled(this.checked);
    });
  });
  // Reuse the original controls, including their plan checks and file picker.
  document.getElementById("composerReasoningToggle")?.addEventListener("click", function (event) {
    if (isBeta()) {
      event.stopPropagation();
      window.App.openModelPicker?.(document.getElementById("agentModelDropdown"), { secondary: true });
      return;
    }
    document.getElementById("reasoningToggle")?.click();
    renderComposerMode();
  });
  // Both modes share the upload path: in Agent Beta attachments.js keeps the
  // file in the composer and agent-workspace.js uploads it to the private
  // chat store on send. The upload option carries the sign-in check.
  document.getElementById("composerAttachButton")?.addEventListener("click", function () {
    document.getElementById("attachUploadOption")?.click();
  });
  document.getElementById("agentReasoningMenuOption")?.addEventListener("click", function (event) {
    event.stopPropagation();
    if (isBeta()) window.App.openModelPicker?.(document.getElementById("agentModelDropdown"), { secondary: true });
  });
  document.getElementById("agentComparisonMenuOption")?.addEventListener("click", function (event) {
    event.stopPropagation();
    if (isBeta()) window.App.openModelPicker?.(document.getElementById("consensusModelDropdown"));
  });
  let composerIsHero = document.body.classList.contains("is-hero");
  new MutationObserver(function () {
    if (!window.document?.body) return;
    const isHero = document.body.classList.contains("is-hero");
    if (isHero === composerIsHero) return;
    composerIsHero = isHero;
    updateAgentModeUI();
  }).observe(document.body, { attributes: true, attributeFilter: ["class"] });
  window.App.renderComposerMode = renderComposerMode;

  window.setAgentModeStatus = setAgentModeStatus;
  window.projectAgentModeRun = projectAgentModeRun;
  window.updateAgentModeUI = updateAgentModeUI;

  // Getter fuer den (modul-privaten) Status, damit Query-/Consensus-Code
  // weiterhin auf den "running"-Zustand pruefen kann.
  window.isAgentModeRunning = function () {
    return agentModeStatus === "running";
  };

  window.App = window.App || {};
  window.App.agentMode = {
    // Claim- und Difference-Spruenge muessen ein verborgenes Ziel zuerst
    // idempotent aufdecken, ohne dafuer den Agent Mode umzuschalten.
    showModelAnswers() {
      return setModelAnswersVisible(true);
    }
  };
})();
