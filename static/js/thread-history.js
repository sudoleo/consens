// =====================================================================
// thread-history.js
// The turns of a chat above its newest answer (window.App.followup):
// Agent turns and the turns of a saved Consensus chat, built from what the
// server stored. Also the one exchange on screen (lastExchange) and the
// composer's input lock and placeholder.
//
// Until 2026-10-25 this file was consensus-run.js and also ran the
// Consensus synthesis in the browser (/consensus); that pipeline now runs
// only on the server (Watches, the API, curated topics). Saved Consensus
// chats stay readable here; they are no longer continued.
//
// Shared deps via existing window contracts:
//   - window.injectMarkdown (markdown-stream.js)
//   - window.renderStoredConsensusClaims / renderStoredDifferenceCards
//     (consensus-insights.js)
//   - window.App.{agentActivity, agentReview, passageCheck, agentMemory,
//     watch, answerShare, agentWorkspace, answerReader, taskChecks}
// =====================================================================

(function () {
  window.App = window.App || {};

  // "BestModel: Anthropic" ist Buchhaltung fuer die Modell-Wertung, kein Satz
  // fuer Leser. Im Freitext-Fallback stand sie bisher sichtbar unter der
  // Analyse.
  function stripBestModelLine(differencesText) {
    return String(differencesText || "")
      .replace(/^[ \t]*\**BestModel:\**[^\n]*$/gim, "")
      .trim();
  }

  // Die Karten eines archivierten Turns sollen die Modelle nennen, die DAMALS
  // geantwortet haben. modelDisplayName in consensus-insights.js liest die
  // Live-Antwortboxen — die tragen laengst die Auswahl des neuesten Laufs.
  function storedModelLabeller(modelAnswers) {
    const labels = {};
    Object.entries(modelAnswers && typeof modelAnswers === "object" ? modelAnswers : {})
      .forEach(([provider, item]) => {
        const key = String(item?.provider || provider || "").toLowerCase();
        const label = String(item?.model_label || "").trim();
        if (key && label) labels[key] = label;
      });
    return function (model) {
      return labels[String(model || "").toLowerCase()] || model;
    };
  }

  // --------- Der Austausch auf dem Schirm und der Verlauf darueber ---------
  // lastExchange ist das Frage/Antwort-Paar einer geoeffneten gespeicherten
  // Consensus-Antwort (firebase.js showExchange); der Antwortleser liest es
  // (model-answer-reader.js). Fortgesetzt wird ein solcher Chat nicht mehr:
  // seit 2026-10-25 laeuft der Consensus nur noch auf dem Server.
  const DEFAULT_INPUT_PLACEHOLDER = "Enter your question";

  // Jede archivierte Schublade braucht eine eigene ID fuer aria-controls.
  // Der Verlauf lebt im selben Dokument wie der Live-Renderbaum, dessen IDs
  // ein JS-Vertrag sind — hier darf nie eine davon ein zweites Mal auftauchen.
  let panelSequence = 0;

  const followup = {
    lastExchange: null, // {question, consensus, turn} der Antwort auf dem Schirm

    buildStoredAgreement(differencesData) {
      const agreement = differencesData?.agreement;
      if (!agreement || typeof agreement.score !== "number") return null;
      const score = Math.max(0, Math.min(100, Math.round(agreement.score)));
      const verdict = document.createElement("div");
      verdict.className = "consensus-verdict thread-history-verdict "
        + (score >= 65 ? "is-calm" : score >= 40 ? "is-warn" : "is-alert");

      const gauge = document.createElement("span");
      gauge.className = "verdict-gauge";
      gauge.style.setProperty("--val", String(score));
      const scoreLine = document.createElement("span");
      scoreLine.className = "verdict-score";
      const num = document.createElement("span");
      num.className = "verdict-score-num";
      num.textContent = String(score);
      const unit = document.createElement("span");
      unit.className = "verdict-score-unit";
      unit.textContent = "/100";
      scoreLine.append(num, unit);
      const meter = document.createElement("span");
      meter.className = "verdict-meter";
      const fill = document.createElement("span");
      fill.className = "verdict-meter-fill";
      meter.appendChild(fill);
      gauge.append(scoreLine, meter);

      const main = document.createElement("span");
      main.className = "verdict-main";
      const headline = document.createElement("span");
      headline.className = "verdict-headline";
      headline.textContent = score >= 85 ? "High agreement"
        : score >= 65 ? "Strong agreement"
          : score >= 40 ? "Partial agreement"
            : score >= 20 ? "Low agreement" : "Very low agreement";
      const detail = document.createElement("span");
      detail.className = "verdict-detail";
      const modelCount = Number(agreement.model_count) || 0;
      detail.textContent = modelCount
        ? (modelCount === 1 ? "1 model compared" : `${modelCount} models compared`)
        : "Saved agreement score";
      main.append(headline, detail);
      verdict.append(gauge, main);
      return verdict;
    },

    // Which turn a history node shows: its ID and its question. A node kept
    // under the same key is never rebuilt (renderStoredTurns).
    turnKey(turnData) {
      const turnId = String(turnData?.turn_id || turnData?.id || "").trim();
      const question = window.App.normalizeQuestionText?.(turnData?.question)
        ?? String(turnData?.question || "").replace(/\s+/g, " ").trim();
      // A turn whose saved state moved on is built again: its check finished
      // later, or its differences, sources or model answers arrived after the
      // follow-up had already moved it up (the footer then gains its tabs).
      const differences = turnData?.differences_data;
      return JSON.stringify([turnId, question, turnData?.status || "", turnData?.agent_review?.status || "",
        String(turnData?.consensus || "").length,
        Array.isArray(differences?.differences) ? differences.differences.length : -1,
        differences?.agreement?.score ?? "",
        Array.isArray(turnData?.sources) ? turnData.sources.length : 0,
        Object.keys(turnData?.model_answers || {}).length]);
    },

    isStorableTurn(turnData) {
      return Boolean(turnData?.question && (turnData.consensus
        || (turnData.execution_mode === 'agent' && turnData.status === 'failed')));
    },

    // One archived turn, built off the page. `attached()` runs what needs the
    // node in the document (its file row, the fold measurement).
    // `options.followUp`: a turn after the chat's first (its Watch opens at
    // the question, so the watched question stands on its own).
    buildHistoryTurn(turnData, options = {}) {
      const turnId = String(turnData.turn_id || "").trim();
      const normalizedQuestion = window.App.normalizeQuestionText?.(turnData.question)
        ?? String(turnData.question).replace(/\s+/g, " ").trim();
      const agentTurn = turnData.execution_mode === "agent" || turnData.mode === "Agent";
      const turn = document.createElement("article");
      // An Agent turn keeps the live turn's boxes (shell.css .is-agent-turn):
      // the live turn moves up into the history unchanged when a follow-up
      // starts (agent-chat.js), and a reopened chat must look the same.
      turn.className = agentTurn ? "thread-history-turn is-agent-turn" : "thread-history-turn";
      if (turnId) turn.dataset.turnId = turnId;
      turn.dataset.turnKey = this.turnKey(turnData);

      const question = document.createElement("div");
      question.className = "thread-history-question";
      const questionText = document.createElement("div");
      questionText.className = "thread-history-question-text";
      if (window.App.fillQuestionText) window.App.fillQuestionText(questionText, normalizedQuestion);
      else questionText.textContent = normalizedQuestion;
      questionText.dataset.question = normalizedQuestion;
      // Text und "Show more" teilen sich die Blase (wie der aktive Kopf).
      const questionBubble = document.createElement("div");
      questionBubble.className = "thread-ask-bubble";
      questionBubble.append(questionText);
      // Screen readers find each message and answer by heading, as in the
      // live turn (#threadAsk, #agentAnswer in index.html).
      const turnHeading = text => {
        const heading = document.createElement("h2");
        heading.className = "visually-hidden";
        heading.textContent = text;
        return heading;
      };
      question.append(turnHeading("Your message"), questionBubble);

      // Anhaenge bleiben an ihrer Nachricht, auch wenn der Turn in den
      // Verlauf rutscht.
      const attachmentsMeta = Array.isArray(turnData.attachments) ? turnData.attachments : [];
      if (attachmentsMeta.length) {
        const attachmentRow = document.createElement("div");
        attachmentRow.className = "attachment-bar message-attachments";
        const rendered = window.App.attachments?.renderMessageAttachments?.(
          attachmentRow,
          attachmentsMeta
        );
        if (rendered) question.appendChild(attachmentRow);
      }

      // Eine archivierte Frage klappt wie die aktive ein
      // (#threadAskMore in app-core.js schaltet beide). Ohne das hat ab dem
      // zweiten Turn jede lange Frage den Thread wieder aufgerissen.
      const questionMore = document.createElement("button");
      questionMore.type = "button";
      questionMore.className = "thread-ask-more";
      questionMore.textContent = "Show more";
      questionMore.setAttribute("aria-expanded", "false");
      questionBubble.appendChild(questionMore);

      const answer = document.createElement("div");
      answer.className = agentTurn ? "thread-history-answer agent-answer" : "thread-history-answer";
      let agentResources = null;
      if (agentTurn) answer.append(turnHeading("Answer"));
      else {
        const answerLabel = document.createElement("div");
        answerLabel.className = "thread-history-answer-label";
        answerLabel.setAttribute("role", "heading");
        answerLabel.setAttribute("aria-level", "2");
        answerLabel.textContent = "Consensus answer";
        answer.append(answerLabel);
      }
      const turnSources = Array.isArray(turnData.sources) ? turnData.sources : [];
      const answerBody = document.createElement("div");
      answerBody.className = "consensus-answer-body";
      answerBody.dataset.markdown = turnData.consensus;
      // Consensus prose has carried no source references since 2026-09-11, so
      // a numeric [1] in it never picks up a citation (as in the live run).
      // Older answers with [S1] tags and Agent prose keep their citations.
      answerBody.dataset.sourceReferences = agentTurn || /\[S\d/i.test(turnData.consensus || '') ? 'legacy' : 'none';
      // Its checklists keep their ticks on the turn (task-checks.js).
      window.App.taskChecks?.scope(answerBody, { turnId, checked: turnData.task_checks });
      if (typeof window.injectMarkdown === "function") {
        window.injectMarkdown(answerBody, turnData.consensus,
          turnData.execution_mode === "agent" || turnData.mode === "Agent" ? [] : turnSources);
      } else {
        answerBody.textContent = turnData.consensus;
      }
      answerBody.classList.add("thread-history-answer-body");
      const claimsFallback = document.createElement("div");
      claimsFallback.className = "consensus-claims-fallback thread-history-claims-fallback";
      claimsFallback.hidden = true;
      window.renderStoredConsensusClaims?.(
        answerBody,
        turnData.differences_data,
        claimsFallback,
        agentTurn ? turnSources : []
      );
      const verdict = this.buildStoredAgreement(turnData.differences_data);
      if (verdict) verdict.classList.add("thread-history-verdict");
      answer.append(answerBody, claimsFallback);
      if (agentTurn) {
        const activity = document.createElement("div");
        activity.className = "agent-answer-activity";
        window.App.agentActivity?.renderTurn(activity, turnData);
        answer.insertBefore(activity, answerBody);
        const failureText = turnData.agent_failure?.error && (window.App.agentReview?.failureNote?.(
          turnData.agent_failure, turnData.agent_review, turnData.consensus || '') ?? turnData.agent_failure.error);
        if (failureText) {
          const failure = document.createElement("p");
          failure.className = "agent-review-note";
          failure.textContent = failureText;
          answer.append(failure);
        }
        window.App.agentReview?.render(answerBody, turnData.agent_review,
          {sources: turnSources, events: turnData.agent_activity, key: turnData.id || turnData.turn_id, question: turnData.question});
        // A pasted text the Agent checked: its result card above the answer.
        window.App.passageCheck?.apply(answerBody, turnData.agent_review);
        window.App.agentMemory?.render(answerBody, { key: turnId, changes: turnData.agent_memory });
        // Every finished Agent answer has its Watch pill, with the question
        // of its own turn (Max, Apple-Audit J20). The history shows no
        // prepared-Watch card, so a turn with one gets the pill as well.
        window.App.watch?.answerButton?.(answerBody, { question: turnData.question, history: true,
          eligible: turnData.status !== "failed" && Boolean(String(turnData.consensus || "").trim()),
          followUp: options.followUp === true });
        // Its Share pill shares this turn's answer; the chat is the one on
        // screen when it is pressed (share-dialog.js).
        window.App.answerShare?.button?.(answerBody, { turnId: turnId || "",
          eligible: turnData.status !== "failed" && Boolean(String(turnData.consensus || "").trim()) });
        // Documents and mail attachments of this turn stay with its answer;
        // agent-workspace.js fills the row from the chat's file list.
        if (turnId) {
          agentResources = document.createElement("div");
          // Its pictures go right under the answer text (agent-workspace.js).
          agentResources._answerBody = answerBody;
          answer.appendChild(agentResources);
        }
      }

      // Der Fuss eines archivierten Turns spricht dieselbe Sprache wie der
      // Fuss der aktiven Antwort: EINE Zeile leiser Schubladen nebeneinander
      // (#runProvenance / .consensus-footer-tabs), nicht drei untereinander
      // gestapelte <details>. Gestapelt hat jeder alte Turn den Thread um
      // drei weitere Zeilen verlaengert, obwohl alles zugeklappt war.
      const footer = document.createElement("div");
      footer.className = "thread-history-footer";
      if (verdict) footer.appendChild(verdict);
      const tabs = document.createElement("div");
      tabs.className = "consensus-footer-tabs thread-history-tabs";
      const panels = document.createElement("div");
      panels.className = "thread-history-panels";
      footer.append(tabs, panels);
      // An Agent turn carries its own evidence row (Differences, Answers,
      // Sources) from agent-review.js; a second footer showed Sources twice.
      footer.hidden = turnData.execution_mode === "agent" || turnData.mode === "Agent";
      answer.appendChild(footer);

      // Chip + Schublade als Paar: gleiche Klassen wie im Live-Fuss, damit
      // shell.css beide gleich behandelt. Die IDs sind je Turn eindeutig —
      // der Verlauf teilt sich den DOM mit dem Live-Renderbaum.
      function addDrawer(label, shortLabel, count, fill) {
        const panelId = `threadHistoryPanel-${++panelSequence}`;
        const tab = document.createElement("button");
        tab.type = "button";
        tab.className = "consensus-tab consensus-evidence-action";
        tab.setAttribute("aria-expanded", "false");
        tab.setAttribute("aria-controls", panelId);
        const icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
        icon.setAttribute("class", "consensus-evidence-icon");
        icon.setAttribute("viewBox", "0 0 24 24");
        icon.setAttribute("aria-hidden", "true");
        const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
        path.setAttribute("d", {
          Differences: "M12 20v-7M12 13 5 6M12 13l7-7M5 11V6h5M14 6h5v5",
          Answers: "M4 4h12v10H8l-4 4V4ZM16 8h4v12l-4-4h-4",
          Sources: "M14 3H5v18h14V8ZM14 3v5h5M8 12h8M8 16h6"
        }[shortLabel]);
        icon.appendChild(path);
        const tabLabel = document.createElement("span");
        tabLabel.className = "consensus-tab-label";
        tabLabel.dataset.short = shortLabel;
        // data-short is the label a reader sees (German on a German page);
        // data-tab names the tab for code.
        tabLabel.dataset.tab = shortLabel.toLowerCase();
        tabLabel.textContent = label;
        const tabCount = document.createElement("span");
        tabCount.className = "consensus-tab-count";
        tabCount.textContent = count > 0 ? String(count) : "";
        const meta = document.createElement("span");
        meta.className = "consensus-tab-meta";
        meta.appendChild(tabCount);
        tab.append(icon, tabLabel, meta);

        const panel = document.createElement("div");
        panel.className = "thread-history-panel";
        panel.id = panelId;
        panel.hidden = true;
        fill(panel);

        tab.addEventListener("click", () => {
          const kind = shortLabel === 'Differences' ? 'differences' : shortLabel === 'Sources' ? 'sources' : null;
          if (kind && window.App?.answerReader?.openPanel(kind, tab, turn)) return;
          const open = tab.getAttribute("aria-expanded") === "true";
          tab.setAttribute("aria-expanded", String(!open));
          panel.hidden = open;
        });

        tabs.insertBefore(tab, shortLabel === "Answers"
          ? tabs.querySelector('[data-tab="sources"]')?.closest('.consensus-tab') || null
          : null);
        panels.appendChild(panel);
      }

      const differencesText = stripBestModelLine(turnData.differences);
      const storedDifferences = turnData.differences_data?.differences;
      const hasStructuredDifferences = Array.isArray(storedDifferences);
      if (hasStructuredDifferences || differencesText) {
        addDrawer(
          "Review differences",
          "Differences",
          hasStructuredDifferences ? storedDifferences.length : 0,
          panel => {
            // Der Turn traegt dieselben strukturierten Daten wie der Live-Lauf.
            // Sie hier NICHT zu benutzen hiess: derselbe Befund las sich im
            // Verlauf als roher Judge-Text, sobald die Antwort nach oben rutschte.
            const cards = document.createElement("div");
            cards.className = "differences-cards thread-history-differences";
            const rendered = window.renderStoredDifferenceCards?.(
              cards,
              turnData.differences_data,
              { modelLabel: storedModelLabeller(turnData.model_answers) }
            );
            if (rendered) {
              panel.appendChild(cards);
              return;
            }
            const body = document.createElement("div");
            body.className = "thread-history-detail-body";
            const markup = window.colorizeCredibility
              ? window.colorizeCredibility(differencesText)
              : differencesText;
            if (typeof window.injectMarkdown === "function") {
              window.injectMarkdown(body, markup, turnSources);
            } else {
              body.textContent = differencesText;
            }
            panel.appendChild(body);
          }
        );
      }

      if (turnSources.length) {
        const list = document.createElement("ol");
        list.className = "thread-history-sources";
        turnSources.forEach((source, index) => {
          const item = document.createElement("li");
          const rawUrl = String(source?.url || "");
          let safeUrl = "";
          try {
            const parsed = new URL(rawUrl);
            if (["http:", "https:"].includes(parsed.protocol)) safeUrl = parsed.href;
          } catch (_) {}
          const title = String(source?.title || rawUrl || `Source ${index + 1}`);
          const label = safeUrl ? document.createElement("a") : document.createElement("span");
          label.textContent = title;
          if (safeUrl) {
            label.href = safeUrl;
            label.target = "_blank";
            label.rel = "noopener noreferrer";
          }
          item.appendChild(label);
          list.appendChild(item);
        });
        addDrawer("Sources", "Sources", turnSources.length, panel => {
          panel.appendChild(list);
        });
      }

      const storedAnswers = turnData.model_answers && typeof turnData.model_answers === "object"
        ? Object.entries(turnData.model_answers).map(([provider, item]) => ({ provider, item }))
        : [];
      const usableAnswers = storedAnswers.filter(({ item }) => String(item?.answer || "").trim());
      if (window.App?.answerReader) {
        window.App.answerReader.registerTurn(turn, turnData, tabs);
      } else if (usableAnswers.length) {
        addDrawer("Compare answers", "Answers", usableAnswers.length, panel => {
          const models = document.createElement("div");
          models.className = "thread-history-models";
          usableAnswers.forEach(({ provider, item }) => {
            const section = document.createElement("section");
            section.dataset.provider = String(item.provider || provider);
            const heading = document.createElement("h4");
            heading.textContent = String(item.model_label || item.provider || "Model");
            const body = document.createElement("div");
            body.className = "thread-history-detail-body";
            const sources = Array.isArray(item.sources) ? item.sources : turnSources;
            if (typeof window.injectMarkdown === "function") {
              window.injectMarkdown(body, item.answer, sources);
            } else {
              body.textContent = item.answer;
            }
            section.append(heading, body);
            models.appendChild(section);
          });
          panel.appendChild(models);
        });
      }
      turn.append(question, answer);
      return {
        node: turn,
        attached() {
          if (agentResources) window.App.agentWorkspace?.renderTurnResources?.(agentResources, turnId);
          // Erst im DOM laesst sich messen, ob der Clamp ueberhaupt greift; nur
          // dann bekommt der Turn seinen Aufklapp-Link.
          window.App.observeQuestionFold?.(question, questionText);
        }
      };
    },

    renderStoredTurn(turnData) {
      return this.renderStoredTurns(turnData ? [turnData] : []);
    },

    // The history never shrinks under the reader (Apple audit A1): turns
    // already on the page under the same key stay as they are, only what is
    // missing is appended. Emptying the history first left the page shorter
    // for a moment; the browser cut the scroll position to fit, and a
    // follow-up jumped to the top of the chat and rode back down. Another
    // chat replaces the history in one step, built off the page.
    // `options.adopt` ({owns(turn), take(turn)}) may hand over a ready node,
    // e.g. the live Agent turn that moves up when its follow-up starts. It is
    // taken only after everything else is built, right before the insert, so
    // no layout read can see the page without it.
    renderStoredTurns(turns, options = {}) {
      const history = document.getElementById("threadHistory");
      if (!history) return 0;
      const wanted = (Array.isArray(turns) ? turns : []).filter(turn => this.isStorableTurn(turn));
      const shown = Array.from(history.children).filter(node => node.classList?.contains("thread-history-turn"));
      let kept = 0;
      while (kept < shown.length && kept < wanted.length
          && shown[kept].dataset.turnKey === this.turnKey(wanted[kept])) kept += 1;
      const plan = wanted.slice(kept).map((turnData, index) => options.adopt?.owns?.(turnData)
        ? { turnData, adopt: true } : { turnData, built: this.buildHistoryTurn(turnData, { followUp: kept + index > 0 }) });
      const nodes = plan.map(item => item.adopt ? options.adopt.take(item.turnData) : item.built.node);
      const hooks = plan.filter(item => item.built).map(item => item.built.attached);
      if (kept || !shown.length) {
        // Same conversation: drop only what no longer belongs (a turn that
        // went back to the live answer), append the rest.
        shown.slice(kept).forEach(node => node.remove());
        history.append(...nodes);
      } else {
        history.replaceChildren(...nodes);
      }
      history.hidden = !history.children.length;
      hooks.forEach(attached => attached());
      return nodes.length;
    },

    clearHistory() {
      const history = document.getElementById("threadHistory");
      if (!history) return;
      history.replaceChildren();
      history.hidden = true;
    },

    // The saved Consensus answer on screen (firebase.js). Nothing continues
    // it; the answer reader reads its question and model answers.
    showExchange(question, consensusText, turn = null) {
      if (!question || !consensusText) return;
      this.lastExchange = {
        question: question,
        consensus: consensusText,
        turn: turn && typeof turn === "object" ? turn : null
      };
      this.render();
    },

    // Another view: nothing of the previous exchange stays.
    reset() {
      this.lastExchange = null;
      this.render();
    },

    // Der Kontext-Zustand hat KEINE eigene Flaeche mehr am Composer. Sichtbar
    // ist er dort, wo er hingehoert: im Thread, der ueber dem Eingabefeld
    // steht. Uebrig bleibt das Nachziehen der Login-Schranke und des
    // Platzhalters.
    render() {
      this.syncInputLock();
    },

    // Der Composer bleibt nach einer Antwort offen; hier wird nur noch die
    // Login-Schranke (updateQuestionInputAccess) nachgezogen und der
    // Platzhalter gesetzt; Agent setzt danach seinen eigenen
    // (agent-chat.js syncComposer).
    syncInputLock() {
      // Tippen und Absenden sind zwei Rechte: wer auf die E-Mail-Bestaetigung
      // wartet, darf seine Frage schon schreiben.
      const canAsk = typeof window.userCanAskQuestions === "function"
        ? window.userCanAskQuestions()
        : true;
      const canType = typeof window.userCanTypeQuestions === "function"
        ? window.userCanTypeQuestions()
        : canAsk;
      const input = document.getElementById("questionInput");
      if (!input) return;
      input.disabled = !canType;
      input.setAttribute("aria-disabled", !canType ? "true" : "false");
      if (!canAsk) return;
      input.placeholder = DEFAULT_INPUT_PLACEHOLDER;
      window.App.agentChat?.syncComposer?.();
    }
  };
  window.App.followup = followup;
})();
