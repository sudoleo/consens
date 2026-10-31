// =====================================================================
// agent-mode.js
// Body classes and answer previews of the view on screen (a Compare run, a
// saved chat, the empty start screen) and the composer controls for the
// next message. Which mode runs (Agent, Compare) is owned by run-mode.js;
// this module renders the one selector for it and the tools that apply to
// the chosen mode. The "agent-mode" names here are historical: they once
// meant the grouped Consensus run (removed from the browser 2026-10-25),
// not Agent (Beta).
// Exporte: window.setAgentModeStatus, window.updateAgentModeUI,
// window.projectAgentModeRun.
// Abhaengigkeiten: window.App.{modelPrefs, getModelOptionLabel,
// trackAppEvent, runMode, answerReader}.
// =====================================================================

(function () {
  // Agent's composer is on screen: chosen, or expected while its access
  // loads (agent-chat.js looksAgent). The bar and the (+) menu follow it.
  const isBeta = () => {
    const chat = window.App.agentChat;
    // Before agent-chat.js has run (a render from an earlier module), the
    // first frame's expectation stands (app-bootstrap.js).
    if (!chat) return document.documentElement.classList.contains("agent-shell-expected");
    return (chat.looksAgent?.() ?? chat.isSelected?.()) === true;
  };
  const runMode = () => window.App.runMode.effective();
  // An Agent choice whose access is still loading runs as nothing yet (Send
  // waits, agent-chat.js); its start screen is Agent's hero, not Compare's
  // answer grid, which would flash on every load until access arrives. That
  // includes the second before the sign-in itself is known (Firebase restores
  // it from storage): neither account nor guest yet, the grid came for it
  // and the field slid down and back up on every reload (2026-10-26).
  const agentAwaited = () => {
    const state = window.App.agentChat?.modeState?.();
    if (window.App.runMode.preference() !== "agent" || state?.family) return false;
    return state?.pending === true || (!state?.canUse && !state?.guest && window.__consensioAuthState?.known !== true);
  };
  // Anything but a side-by-side comparison: the next message goes to Agent.
  const threadMode = () => runMode() !== "compare" || agentAwaited();

  // When a RunContext is selected, the run view is a projection of that frozen
  // run rather than a reflection of the controls that configure the next run.
  let projectedRunContext = null;
  // Session-only disclosure: every new run starts in the clean view.
  let modelAnswersVisible = false;

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
    // The models the answer reader previews on the Compare start screen: the
    // ones the controls have chosen for the next message.
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
  const MODE_ORDER = ["agent", "compare"];
  const MODE_ICONS = {
    agent: "M12 3.5 13.9 10l6.6 2-6.6 2L12 20.5 10.1 14l-6.6-2 6.6-2Z",
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
    // the server), so the group steps aside instead of dead rows.
    // Settings still holds the choice for new chats.
    const control = document.getElementById("runModeControl");
    if (control) control.hidden = !available.compare.enabled;
    if (select) {
      for (const option of Array.from(select.options)) {
        const rule = available[option.value];
        const copy = window.App.runMode.copy(option.value);
        // A mode this version does not know (Consensus, retired 2026-10-25)
        // is no choice.
        if (!rule || (option.value === "agent" && !rule.visible)) { option.remove(); continue; }
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
      for (const option of Array.from(setting.options)) {
        if (!available[option.value]) option.remove();
      }
      const agentOption = setting.querySelector('option[value="agent"]');
      if (available.agent.visible && !agentOption) {
        const option = document.createElement("option");
        option.value = "agent";
        option.textContent = "Agent · Beta";
        setting.appendChild(option);
      } else if (!available.agent.visible && agentOption) agentOption.remove();
      const preference = window.App.runMode.preference();
      const shown = setting.querySelector(`option[value="${preference}"]`) ? preference : "compare";
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
    renderRunModeControl();
    // Compare uses the Reasoning switch row; Agent uses the reasoning-effort
    // menu entry instead.
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
    const tools = document.getElementById("composerTools");
    const bar = document.getElementById("composerModeBar");
    if (!tools || !bar) return;
    // One rule for every mode and width: the tools belong to the start
    // screen (the hero, or the Compare start), in the field's own row; in a
    // chat they live in the (+) menu. The bar under the field only carries
    // the status of a direct comparison on screen, never tools.
    const start = window.App.composer?.isStartScreen?.() ?? document.body.classList.contains("is-hero");
    const summary = beta ? null : window.App.answerReader?.directSummary?.();
    const counts = summary ? window.App.answerReader?.directCounts?.() : null;
    const wasHidden = tools.hidden;
    tools.hidden = !start;
    // The tools come in when they come back (a new chat, the Compare start),
    // never on the first paint, where they are simply there (Apple-Audit B1).
    if (wasHidden && !tools.hidden) revealBar(tools);
    // Reasoning stands after the models, right before Send, on the start
    // screen as the tools; in a chat it is in the (+) menu.
    const reasoningTool = document.getElementById("composerReasoningToggle");
    if (reasoningTool) reasoningTool.hidden = !start;
    bar.hidden = !summary;
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
      // While the model list loads, Reasoning keeps its look and opens the
      // chip's menu; it is dimmed only for a model without it or a run.
      const loading = !["ready", "failed"].includes(document.getElementById("agentModelDropdown")?.dataset.catalog);
      reasoningButton.disabled = beta && !loading && (!effort || effort.disabled || effort.dataset.available !== "true");
      reasoningButton.setAttribute("role", beta ? "button" : "switch");
      reasoningButton.setAttribute("aria-checked", String(reasoningOn));
      // A switch says On or Off as its state. As the Agent's menu button the
      // word is the chosen level, and the name is what it shows ("Reasoning
      // Auto"), so speech input finds it by its words (WCAG 2.5.3).
      if (buttonId === "composerReasoningToggle") {
        if (beta) reasoningButton.removeAttribute("aria-label");
        else reasoningButton.setAttribute("aria-label", "Reasoning");
      }
      reasoningButton.title = reasoningOn ? "Reasoning on · Models think longer before they answer"
        : "Reasoning off · Models think longer before they answer";
      // One write, and only of a change: the label is in the first frame
      // already (app-bootstrap.js).
      const state = document.getElementById(stateId);
      // Until agent-chat.js has drawn the levels, the first frame's word
      // (app-bootstrap.js, data-seeded) stays.
      if (effort?.dataset.options) delete state.dataset.seeded;
      const level = state.dataset.seeded ? state.textContent : effort?.selectedOptions[0]?.textContent;
      const word = beta ? level || "Auto" : reasoningOn ? "On" : "Off";
      if (state.textContent !== window.App.t(word)) state.textContent = word;
      if (beta) {
        reasoningButton.removeAttribute("aria-checked");
        reasoningButton.setAttribute("aria-haspopup", "listbox");
        reasoningButton.title = !reasoningButton.disabled ? "Choose reasoning for your next chat message"
          : effort?.dataset.available === "true" ? "This model thinks at one fixed level"
            : "This model has no reasoning setting";
      } else reasoningButton.removeAttribute("aria-haspopup");
    }
    const labels = models.map(pref => {
      const select = document.getElementById(pref.selectId);
      return window.App.getModelOptionLabel(select?.selectedOptions[0]) || pref.label;
    });
    const key = JSON.stringify(models.map((pref, i) => [pref.key, labels[i]]));
    const providers = models.map(pref => pref.provider || pref.key).join(",");
    // The same families keep their marks (the first frame drew them,
    // app-bootstrap.js); only a model's name in the tooltip changes.
    if (icons.dataset.models !== key && icons.dataset.providers === providers
      && icons.children.length === models.length) {
      icons.querySelectorAll(".composer-model-icon").forEach((mark, i) => {
        mark.title = `${models[i].label} · ${labels[i]}`;
        mark.setAttribute("aria-label", mark.title);
      });
      icons.dataset.models = key;
    }
    if (icons.dataset.models !== key) {
      icons.replaceChildren(...models.map((pref, i) => {
        const mark = document.createElement("span");
        mark.className = "composer-model-icon";
        mark.dataset.provider = pref.provider;
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
      icons.dataset.providers = providers;
    }
    renderReviewers(beta, start, models.length);
    const status = document.getElementById("composerComparisonStatus");
    status.hidden = !summary;
    // The comparison on screen says how far it got. (Its "Shown: Compare
    // result" prefix for a differing next mode left with Consensus on
    // 2026-10-25: Agent, the only other mode, has its own composer, where
    // this bar steps aside.) The summary comes translated (directSummary),
    // so the narrow form comes from the numbers: parsed out of the words, it
    // stayed the whole German sentence, cut off (2026-10-23).
    status.textContent = summary ? `${summary}.` : "";
    status.title = status.textContent;
    status.dataset.compact = counts
      ? `${counts.ready}/${counts.total}${counts.unavailable ? ` · ${counts.unavailable}!` : ""}` : "";
  }

  // In audit mode the comparison models review the agent’s work and get a
  // control of their own (Max, 2026-10-27): their marks stand before the
  // chip, which then names the chat model (model-picker.js), and say "2 AIs
  // cross-check" (#composerModelPicker on the start screen,
  // #composerReviewers in a chat). Both open the reviewers' level of the
  // Agent menu.
  function renderReviewers(beta, start, count) {
    const auditing = beta && window.App.agentPreferences?.auditing?.() === true;
    const words = auditing ? window.App.words.crossCheck(count, 1) : "";
    // Where the words do not fit, their short form ("3 AIs"), the same in the
    // chat and on the start screen: the marks never stand without a word on a
    // phone (UX audit E4, E5). An attribute is not translated by i18n.js.
    const short = !auditing ? "" : count === 1 ? "1 AI" : `${count} AIs`;
    const shortText = window.App.t?.(short) ?? short;
    // One write, and only of a change: i18n.js translates what is written.
    const write = (node, name, value) => {
      const current = name === "text" ? node.textContent : node.getAttribute(name);
      if (current === (window.App.t?.(value) ?? value)) return;
      if (name === "text") node.textContent = value;
      else node.setAttribute(name, value);
    };
    const picker = document.getElementById("composerModelPicker");
    const label = document.getElementById("composerModelLabel");
    if (label) {
      label.hidden = !auditing;
      if (auditing) write(label, "text", words);
      if (auditing) label.dataset.short = shortText; else delete label.dataset.short;
    }
    if (picker) {
      // On the start screen the marks stand before the chip in every mode
      // and say who answers; in a chat only the reviewers keep theirs.
      const wasHidden = picker.hidden;
      picker.hidden = !start;
      if (wasHidden && !picker.hidden) revealBar(picker);
      // The name holds the words on screen (WCAG 2.5.3).
      write(picker, "aria-label", auditing ? words : "Configure models for your next question");
      write(picker, "title", auditing ? "Choose the reviewers of the agent’s work" : "Configure models");
    }
    const reviewers = document.getElementById("composerReviewers");
    if (!reviewers) return;
    reviewers.hidden = !auditing || start;
    if (reviewers.hidden) return;
    write(reviewers, "aria-label", words);
    // What the icons are, said beside them and in the tooltip (2026-10-28,
    // Max: new users did not know why a logo stood there).
    write(reviewers, "title", "Independent reviewers follow the agent’s work and pause it when in doubt. Choose them here.");
    const caption = document.getElementById("composerReviewersLabel");
    if (caption) {
      write(caption, "text", words);
      caption.dataset.short = shortText;
    }
    // The bar's marks, the same nodes: they are drawn there in every mode.
    const marks = document.getElementById("composerModelIcons");
    const own = document.getElementById("composerReviewerIcons");
    if (marks && own && own.dataset.models !== marks.dataset.models) {
      own.replaceChildren(...Array.from(marks.children, mark => {
        const copy = mark.cloneNode(true);
        // Named once, by the button.
        copy.removeAttribute("role");
        copy.removeAttribute("aria-label");
        copy.setAttribute("aria-hidden", "true");
        return copy;
      }));
      own.dataset.models = marks.dataset.models || "";
    }
  }

  function revealBar(bar) {
    // display:none until now, so the animation starts with the class. Where
    // CSS keeps it out (a phone), no animation ends to take the class off.
    if (!bar.getClientRects().length) return;
    bar.classList.add("is-revealing");
    bar.addEventListener("animationend", () => bar.classList.remove("is-revealing"), { once: true });
  }

  function updateAgentModeUI() {
    // config.agentMode is the persisted run field for "the consensus
    // pipeline ran"; a projected run in this module is always a Compare run
    // (false). A saved Consensus answer on screen (firebase.js reveals it
    // before calling here) keeps its answers behind "Compare answers": an
    // open saved chat runs its next message as Compare, and the view must
    // not follow that. Otherwise the view follows the choice for the next
    // message: Agent's start screen, or Compare's.
    const savedConsensusShown = !document.body.classList.contains("direct-comparison-active")
      && document.getElementById("consensusOutput")?.classList.contains("is-visible") === true;
    const enabled = projectedRunContext
      ? projectedRunContext.config?.agentMode !== false
      : savedConsensusShown || threadMode();
    const answersRow = document.getElementById("agentModeAnswersRow");
    const answersToggle = document.getElementById("agentModeAnswersToggle");
    const activeModels = getActiveAgentModels();

    // Die Einzelantworten-Disclosure ist eine der drei Aufklapp-Flaechen in
    // der Fusszeile einer gespeicherten Consensus-Antwort ("Review
    // differences · Compare answers · Sources"). Der Footer selbst wird erst
    // zusammen mit der Antwort sichtbar; innerhalb dieses Footers ist der
    // Schalter deshalb immer da.

    document.body.classList.toggle("agent-mode-enabled", enabled);
    window.App.answerReader?.syncPreview?.(threadMode(), activeModels);
    // "direct-comparison-active" beschreibt, was GERADE AUF DEM SCHIRM steht,
    // der Modus dagegen, was die NAECHSTE Nachricht tut. Umschalten behaelt
    // das angezeigte Ergebnis; erst eine neue Projektion wechselt es.
    // Hero-Desktop zeigt die Response-Boxen nur in Compare; inert/
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

    // The mode selector describes the NEXT message, `enabled` the view on
    // screen. Controls follow the choice; view and body classes the run.
    renderComposerMode();

    // Nach dem Layout messen: die Boxen sind in genau diesem Aufruf sichtbar
    // geworden (agent-mode-show-answers), vorher ist ihre Hoehe 0.
    scheduleAnswerPreviewSync();
  }

  // Every change of the mode (selector, Settings, another tab) arrives here.
  // Switching keeps the result on screen, including a saved direct
  // comparison; only the next message changes.
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
    window.App?.followup?.render?.();
    if (window.App.runRegistry?.visible?.()) {
      window.App.runRegistry.renderVisible();
    }
    window.App.attachments?.refreshCompatibility?.();
  }

  // "running": a new set of answers is on its way (the Compare demo), so the
  // answers start closed and no box keeps an earlier "show full answer".
  // "idle": the view was cleared. A second argument (an error message) may
  // still be passed by callers; nothing here shows it.
  function setAgentModeStatus(status) {
    if (status === "running" || status === "idle") modelAnswersVisible = false;
    if (status === "running") {
      document.querySelectorAll(".response-box[data-answer-open]")
        .forEach(box => { delete box.dataset.answerOpen; });
    }
    updateAgentModeUI();
  }

  // The Compare run on screen (or none). Another run's answers start closed.
  function projectAgentModeRun(context) {
    const switched = (projectedRunContext?.runId || null) !== (context?.runId || null);
    projectedRunContext = context || null;
    if (switched) modelAnswersVisible = false;
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
        firstAnswer?.scrollIntoView({ block: "nearest", behavior: window.App.scrollBehavior?.() || "auto" });
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
  // Reuse the original controls, including their plan checks and file picker.
  document.getElementById("composerReasoningToggle")?.addEventListener("click", function (event) {
    if (isBeta()) {
      event.stopPropagation();
      window.App.openModelPicker?.(document.getElementById("agentModelDropdown"), { secondary: true, trigger: this });
      return;
    }
    document.getElementById("reasoningToggle")?.click();
    renderComposerMode();
  });
  // From the (+) menu, which closes: a login dialog gives the focus back to (+).
  document.getElementById("agentReasoningMenuOption")?.addEventListener("click", function (event) {
    event.stopPropagation();
    if (isBeta()) window.App.openModelPicker?.(document.getElementById("agentModelDropdown"),
      { secondary: true, trigger: document.getElementById("attachTrigger") });
  });
  document.getElementById("agentComparisonMenuOption")?.addEventListener("click", function (event) {
    event.stopPropagation();
    if (isBeta()) window.App.openModelPicker?.(document.getElementById("consensusModelDropdown"),
      { trigger: document.getElementById("attachTrigger") });
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

  window.App = window.App || {};
  window.App.agentMode = {
    // Claim- und Difference-Spruenge muessen ein verborgenes Ziel zuerst
    // idempotent aufdecken, ohne dafuer den Agent Mode umzuschalten.
    showModelAnswers() {
      return setModelAnswersVisible(true);
    }
  };
})();
