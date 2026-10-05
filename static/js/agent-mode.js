// =====================================================================
// agent-mode.js
// Run status of the grouped model run (body classes, answer previews) and the
// composer controls for the next message. Which mode runs (Compare,
// Consensus, Agent) is owned by run-mode.js; this module renders the one
// selector for it and the tools that apply to the chosen mode. The
// "agent-mode" names here are historical and describe the grouped run, not
// Agent (Beta). Das fruehere Modell-Panel (#agentModePanel mit Timer und
// Modell-Chips) ist seit 2026-10-05 entfernt; der gefuehrte Lauf erzaehlt
// jeden Lauf. Der Status ist modul-privat und wird extern via
// window.isAgentModeRunning() gelesen.
// Exporte: window.setAgentModeStatus, window.updateAgentModeUI,
// window.projectAgentModeRun, window.isAgentModeRunning.
// Abhaengigkeiten: window.App.{modelPrefs,
// getModelOptionLabel,trackAppEvent},
// window.updateConsensusButtonAvailability.
// =====================================================================

(function () {
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

  let agentModeStatus = "idle";
  // When a RunContext is selected, the run view is a projection of that frozen
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

  function getActiveAgentModels() {
    // The models the answer reader previews. Only a projected run describes
    // itself here. Without a run -- a saved
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
          hasAnswer: Boolean(String(result.text || result.streamText || "").trim())
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
          hasAnswer: Boolean(responseBox?.querySelector(".collapsible-content")?.textContent?.trim())
        };
      });
  }

  // The one mode selector (the first group in the (+) menu) and its mirror in
  // Settings. Both are views of App.runMode: options the open chat cannot
  // switch to stay visible but disabled with the reason, Agent only for
  // accounts with access. renderComposerMode runs on every run status tick;
  // the selector only changes when the mode, the open chat's family or the
  // account changes.
  const MODE_ORDER = ["agent", "consensus", "compare"];
  const MODE_ICONS = {
    agent: "M12 3.5 13.9 10l6.6 2-6.6 2L12 20.5 10.1 14l-6.6-2 6.6-2Z",
    consensus: "M9 6.5a5.5 5.5 0 1 0 0 11 5.5 5.5 0 1 0 0-11ZM15 6.5a5.5 5.5 0 1 0 0 11 5.5 5.5 0 1 0 0-11Z",
    compare: "M4 5h6v14H4zM14 5h6v14h-6z",
  };
  function renderModeRows(group, select, mode, available) {
    let rows = group.querySelectorAll(".attach-menu-mode");
    if (!rows.length) {
      for (const value of MODE_ORDER) {
        const row = document.createElement("button");
        row.type = "button";
        row.className = "attach-menu-item attach-menu-mode";
        row.dataset.value = value;
        const icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
        icon.setAttribute("viewBox", "0 0 24 24");
        icon.setAttribute("aria-hidden", "true");
        const path = document.createElementNS(icon.namespaceURI, "path");
        path.setAttribute("d", MODE_ICONS[value]);
        icon.append(path);
        const text = document.createElement("span");
        text.className = "attach-menu-text";
        const label = document.createElement("span");
        label.className = "attach-menu-label";
        const hint = document.createElement("span");
        hint.className = "attach-menu-hint";
        text.append(label, hint);
        const check = document.createElement("span");
        check.className = "attach-menu-check";
        check.setAttribute("aria-hidden", "true");
        row.append(icon, text, check);
        row.addEventListener("click", () => {
          window.App.closeAttachMenu?.();
          onRunModeChoice(value, "composer");
        });
        group.append(row);
      }
      rows = group.querySelectorAll(".attach-menu-mode");
    }
    for (const row of rows) {
      const value = row.dataset.value;
      const rule = available[value];
      const copy = window.App.runMode.copy(value);
      row.hidden = value === "agent" && !rule.visible;
      row.disabled = !rule.enabled;
      row.setAttribute("aria-pressed", String(value === mode));
      const label = row.querySelector(".attach-menu-label");
      label.textContent = copy.label;
      if (copy.badge) {
        const badge = document.createElement("span");
        badge.className = "attach-menu-badge";
        badge.textContent = copy.badge;
        label.append(badge);
      }
      row.querySelector(".attach-menu-hint").textContent = rule.enabled ? copy.description : rule.reason;
    }
    select.title = `Mode: ${window.App.runMode.copy(mode).label}`;
  }
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
    // the server), so the group steps aside instead of three dead rows.
    // Settings still holds the choice for new chats.
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
      if (control) renderModeRows(control, select, mode, available);
      // The models chip names who answers, and that changes with the mode.
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
      // The mode lives in this menu unless an open Agent chat has fixed it.
      const modeShown = document.getElementById("runModeControl")?.hidden === false;
      trigger.title = modeShown ? "Mode, files and options" : beta ? "Chat options" : "Add attachment";
      trigger.setAttribute("aria-label", trigger.title);
    }
    // Check contradictions is a standing setting (Settings → Runs), not a
    // per-question tool: it starts on and shows its result at the
    // contradiction under the answer (agent-review.js), not as a switch in
    // the composer that promises more than the run shows.
    const sourcesEnabled = window.App.isSourceCheckEnabled();
    const sourceSetting = document.getElementById("sourceCheckSwitch");
    if (sourceSetting) {
      sourceSetting.checked = sourcesEnabled;
      sourceSetting.disabled = !enabled;
      const title = enabled ? "" : "Compare has no consensus to check. Choose Consensus or Agent.";
      sourceSetting.title = title;
      const label = sourceSetting.closest("label");
      if (label) label.title = title;
    }
    const bar = document.getElementById("composerModeBar");
    if (!bar) return;
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

  // A second argument (an error message) is still passed by callers but no
  // longer shown: the guided run reports failures itself.
  function setAgentModeStatus(status) {
    if (status === "running") {
      if (agentModeStatus !== "running") {
        modelAnswersVisible = false;
        // Ein neuer Lauf bringt neue Antworten: die Entscheidung, welche
        // davon ganz aufgeklappt war, gilt fuer die alten.
        document.querySelectorAll(".response-box[data-answer-open]")
          .forEach(box => { delete box.dataset.answerOpen; });
      }
    } else if (status === "idle") {
      modelAnswersVisible = false;
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

    if (!context || context.config?.agentMode === false) {
      agentModeStatus = "idle";
      if (switched) modelAnswersVisible = false;
      updateAgentModeUI();
      return;
    }

    if (switched) modelAnswersVisible = false;
    if (context.status === "failed") {
      agentModeStatus = "error";
    } else if (context.status === "canceled") {
      agentModeStatus = "canceled";
    } else if (context.status === "succeeded" || context.phase === "answers_ready") {
      agentModeStatus = "complete";
    } else {
      agentModeStatus = "running";
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
  document.getElementById("sourceCheckSwitch")?.addEventListener("change", function () {
    setSourceCheckEnabled(this.checked);
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
