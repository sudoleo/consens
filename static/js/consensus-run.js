// =====================================================================
// consensus-run.js
// Consensus execution for an admitted RunContext
// (window.App.executeConsensusRun): /consensus payload, SSE stream,
// read-only transport recovery and the result (main answer, structured
// differences, citation/share metadata). window.getConsensus is only a
// compatibility bridge into that path. Follow-up/history rendering stays
// here; lifecycle UI helpers live in consensus-lifecycle.js.
//
// Shared deps via existing window contracts:
//   - window.App.runRegistry, window.App.trackAppEvent
//   - window.streamSSERequest / injectMarkdown
//   - window.saveBookmarkConsensus / window.recordModelVote (firebase.js)
//   - window.auth (firebase.js)
// =====================================================================

(function () {
  window.App = window.App || {};

  const trackAppEvent = window.App.trackAppEvent;
  const streamSSERequest = window.streamSSERequest;
  const injectMarkdown = window.injectMarkdown;

  // Namen aller konfigurierten Familien (Serververtrag), aus der einen
  // Frontend-Quelle window.App.modelPrefs.
  function familyKeys() {
    return (window.App.modelPrefs || []).map(pref => pref.key);
  }

  const sourceRunObservers = new WeakMap();
  window.App.watchRunSources = function (context) {
    const registry = window.App.runRegistry;
    const snapshot = context?.consensus?.sourceVerification;
    if (!snapshot?.job_id || context.consensus.status !== 'complete' || !registry?.isAuthCurrent(context)) return;
    const existing = sourceRunObservers.get(context);
    if (existing?.jobId === snapshot.job_id) return;
    existing?.stop();
    const jobId = snapshot.job_id;
    const stop = window.App.sourceVerification?.observe({ snapshot, auth: context.auth,
      useOwnKeys: context.config?.useOwnKeys === true,
      getOwnKey: () => window.localStorage.getItem('openrouterKey'),
      isActive: () => registry.get(context.runId) === context && context.consensus.sourceVerification?.job_id === jobId,
      onUpdate(value) {
        context.consensus.sourceVerification = value;
        if (context.consensus.completedTurn) context.consensus.completedTurn.source_verification = value;
        if (context.consensus.bookmarkPayload) context.consensus.bookmarkPayload.sourceVerification = value;
        if (context.completedBasis?.currentTurn) context.completedBasis.currentTurn.source_verification = value;
        // Keep the continuation basis current too. Its projection remains bound
        // to the visible run; a hidden completion cannot repaint another answer.
        if (context.completedBasis) registry.setCompletedBasis(context.runId, context.completedBasis);
        window.App.runView?.projectSources?.(context);
      }
    });
    sourceRunObservers.set(context, {jobId, stop: stop || (() => {})});
  };

  function isAbortError(error) {
    return error && error.name === "AbortError";
  }

  // A broken response body does not prove that the server failed to commit.
  // Reconcile through read-only history; never repeat the paid POST.
  async function recoverConsensusResult(context, payload, signal, error) {
    const registry = window.App.runRegistry;
    if (!['request_failed', 'stream_read_failed', 'stream_incomplete'].includes(error?.streamFailureKind)
        || isAbortError(error) || !payload.chat_id || !payload.turn_id) throw error;
    const current = () => !signal.aborted && registry.isAuthCurrent(context)
      && registry.isExecuting(context.runId);
    if (!current()) throw error;
    const recovery = new AbortController();
    const cancel = () => recovery.abort();
    signal.addEventListener('abort', cancel, { once: true });
    const timeout = window.setTimeout(cancel, 5000);
    try {
      for (let attempt = 0; attempt < 3 && current() && !recovery.signal.aborted; attempt++) {
        if (attempt) await new Promise(resolve => window.setTimeout(resolve, 500));
        if (!current() || recovery.signal.aborted) break;
        try {
          const response = await fetch(`/chats/${encodeURIComponent(payload.chat_id)}/turns/${encodeURIComponent(payload.turn_id)}`, {
            headers: { Authorization: `Bearer ${payload.id_token}` },
            cache: 'no-store', signal: recovery.signal
          });
          if ([401, 403, 404].includes(response.status)) break;
          if (!response.ok) continue;
          const { turn } = await response.json();
          if (!current() || recovery.signal.aborted) break;
          if (turn?.status === 'failed') {
            // The owner-bound read is an authoritative terminal disposition.
            // Keep the partial text, but let ChatSession clear the pending
            // turn and release the conversation lock instead of treating the
            // outcome as unknown (which demanded a page reload).
            return { ok: false, status: 409, streamed: false, data: {
              error: 'This conversation turn failed. Its partial answer was not saved as a completed result.',
              chat_id: payload.chat_id, turn_id: payload.turn_id,
              chat_persisted: false, chat_turn_state: 'failed',
              consensus_completion: 'interrupted'
            } };
          }
          if (turn?.status !== 'completed' || typeof turn.consensus !== 'string' || !turn.consensus.trim()) continue;
          return { ok: true, status: 200, streamed: false, data: {
            consensus_response: turn.consensus,
            differences: turn.differences || '', differences_data: turn.differences_data || null,
            sources: turn.sources || [], model_answers: turn.model_answers || {},
            source_verification: turn.source_verification || null, result_id: turn.result_id || null,
            chat_id: payload.chat_id, turn_id: payload.turn_id,
            chat_persisted: true, chat_turn_state: 'completed', chat_replayed: true
          } };
        } catch (_) {
          // Keep the original transport category if reconciliation also fails.
        }
      }
    } finally {
      window.clearTimeout(timeout);
      signal.removeEventListener('abort', cancel);
      recovery.abort();
    }
    throw error;
  }

  function parseBestModel(differencesText) {
    if (typeof differencesText !== "string") return null;
    const regex = /BestModel:\s*(.*)/i;
    const match = differencesText.match(regex);
    return match ? match[1].trim() : null;
  }

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

  // --------- Follow-up-Fragen: Kontext-State ---------
  // Genau eine Kontext-Ebene: das Frage/Konsens-Paar des letzten erfolgreichen
  // Laufs. offer() merkt sich das Paar, consume() liefert den context-Payload
  // für query-send.js und räumt auf.
  //
  // Es gibt KEINE Follow-up-Entscheidung mehr: ein sichtbares Gespraech laeuft
  // ueber das Eingabefeld einfach weiter (wie in jedem Chat). Der frueher hier
  // gerenderte Kontext-Chip samt "New comparison" ist ersatzlos entfallen —
  // der Ausstieg steht in der Sidebar, wo ein neues Gespraech beginnt.
  // Kein Tier-Gate: ein Follow-up ist ein vollwertiger Lauf und zaehlt wie
  // jede andere Frage gegen das Tagesbudget — mehr kostet es niemanden.
  const DEFAULT_INPUT_PLACEHOLDER = "Enter your question";
  const FOLLOWUP_INPUT_PLACEHOLDER = "Ask a follow-up question";
  const UNAVAILABLE_INPUT_PLACEHOLDER = "Start a new comparison — saved context unavailable";

  // Jede archivierte Schublade braucht eine eigene ID fuer aria-controls.
  // Der Verlauf lebt im selben Dokument wie der Live-Renderbaum, dessen IDs
  // ein JS-Vertrag sind — hier darf nie eine davon ein zweites Mal auftauchen.
  let panelSequence = 0;

  const followup = {
    lastExchange: null, // {question, consensus, turn} des letzten Konsens-Laufs
    // True while the current query continues the preceding exchange. The flag
    // is reset by offer(); completed turns may continue indefinitely.
    followupInFlight: false,
    continuationUnavailable: false,
    // Was consume() zuletzt ausgegeben hat. Nur dafuer da, den Kontext
    // zurueckzuholen, wenn der Lauf gar nicht stattgefunden hat.
    spentExchange: null,

    // Ein sichtbares Gespraech laeuft immer weiter: sobald ein fortsetzbarer
    // Turn da ist, geht die naechste Frage mit seinem Kontext raus — aber nur
    // im Agent Mode. beginContext (query-send.js) bindet den Kontext an genau
    // diese Bedingung; ohne sie versprach der Platzhalter "Ask a follow-up
    // question" eine Fortsetzung, die der naechste Lauf nicht mehr gab.
    isArmed() {
      return !!this.lastExchange && window.App.runMode?.pipeline?.() === true;
    },

    hasContinuableExchange() {
      return !!this.lastExchange;
    },

    previousQuestionForBookmark() {
      return String(this.spentExchange?.question || "").trim();
    },

    previousTurnForBookmark() {
      const turn = this.spentExchange?.turn;
      return turn && typeof turn === "object" ? turn : null;
    },

    staticizeHistoryNode(node) {
      if (!node) return null;
      const clone = node.cloneNode(true);
      clone.removeAttribute("id");
      clone.hidden = false;
      clone.querySelectorAll("[id]").forEach(child => child.removeAttribute("id"));
      clone.querySelectorAll(
        ".consensus-copy-icon-btn, .copy-btn"
      ).forEach(child => child.remove());
      clone.querySelectorAll("button").forEach(button => {
        const replacement = document.createElement("span");
        replacement.className = button.className;
        replacement.innerHTML = button.innerHTML;
        replacement.setAttribute("aria-hidden", "true");
        button.replaceWith(replacement);
      });
      clone.querySelectorAll("[aria-controls]").forEach(child => {
        child.removeAttribute("aria-controls");
        child.removeAttribute("aria-expanded");
      });
      return clone;
    },

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
        ? `${modelCount} model${modelCount === 1 ? "" : "s"} compared`
        : "Saved agreement score";
      main.append(headline, detail);
      verdict.append(gauge, main);
      return verdict;
    },

    appendHistoryTurn(turnData, liveBody = null, liveVerdict = null) {
      const history = document.getElementById("threadHistory");
      if (!history || !turnData?.question || (!turnData?.consensus
          && !(turnData.execution_mode === 'agent' && turnData.status === 'failed'))) return false;
      const turnId = String(turnData.turn_id || "").trim();
      const normalizedQuestion = String(turnData.question).replace(/\s+/g, " ").trim();
      // A replay of the same completed turn is idempotent. A colliding ID with
      // different content must never make the visible exchange disappear:
      // append it and let the owner-bound transcript remain the authority.
      if (turnId && Array.from(history.children).some(node => (
        node.dataset?.turnId === turnId
        && node.querySelector?.(".thread-history-question-text")?.textContent === normalizedQuestion
      ))) {
        return false;
      }

      const turn = document.createElement("article");
      turn.className = "thread-history-turn";
      if (turnId) turn.dataset.turnId = turnId;

      const question = document.createElement("div");
      question.className = "thread-history-question";
      const questionText = document.createElement("div");
      questionText.className = "thread-history-question-text";
      questionText.textContent = normalizedQuestion;
      question.append(questionText);

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

      // Eine archivierte Frage klappt wie die aktive auf drei Zeilen ein
      // (#threadAskMore in app-core.js schaltet beide). Ohne das hat ab dem
      // zweiten Turn jede lange Frage den Thread wieder aufgerissen.
      const questionMore = document.createElement("button");
      questionMore.type = "button";
      questionMore.className = "thread-ask-more";
      questionMore.textContent = "Show full question";
      question.appendChild(questionMore);

      const answer = document.createElement("div");
      answer.className = "thread-history-answer";
      let agentResources = null;
      if (turnData.execution_mode !== "agent" && turnData.mode !== "Agent") {
        const answerLabel = document.createElement("div");
        answerLabel.className = "thread-history-answer-label";
        answerLabel.textContent = "Consensus Answer";
        answer.append(answerLabel);
      }
      const turnSources = Array.isArray(turnData.sources) ? turnData.sources : [];
      const answerBody = document.createElement("div");
      answerBody.className = "consensus-answer-body";
      answerBody.dataset.markdown = turnData.consensus;
      const sourceReferences = turnData.source_verification?.check_type !== 'contradiction_evidence';
      answerBody.dataset.sourceReferences = sourceReferences ? 'legacy' : 'none';
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
        sourceReferences ? turnSources : []
      );
      const verdict = this.staticizeHistoryNode(liveVerdict)
        || this.buildStoredAgreement(turnData.differences_data);
      if (verdict) verdict.classList.add("thread-history-verdict");
      answer.append(answerBody, claimsFallback);
      if (turnData.execution_mode === "agent" || turnData.mode === "Agent") {
        const activity = document.createElement("div");
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
        window.App.agentMemory?.render(answerBody, { key: turnId, changes: turnData.agent_memory });
        // Documents and mail attachments of this turn stay with its answer;
        // agent-workspace.js fills the row from the chat's file list.
        if (turnId) {
          agentResources = document.createElement("div");
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
          ? tabs.querySelector('[data-short="Sources"]')?.closest('.consensus-tab') || null
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

      let sourceReport = null;
      if (turnSources.length || turnData.source_verification) {
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
        addDrawer("Verify sources", "Sources", turnSources.length, panel => {
          const report = document.createElement("div");
          sourceReport = report;
          report.className = "source-verification-report";
          panel.appendChild(report);
          panel.appendChild(list);
          window.App.sourceVerification?.render(answerBody, report, turnData.source_verification, {differencesData: turnData.differences_data});
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
      history.appendChild(turn);
      history.hidden = false;
      if (agentResources) window.App.agentWorkspace?.renderTurnResources?.(agentResources, turnId);
      if (sourceReport && turnData.source_verification?.job_id) {
        const user = window.auth?.currentUser;
        const jobId = turnData.source_verification.job_id;
        window.App.sourceVerification?.observe({snapshot: turnData.source_verification,
          auth: {user, uid: user?.uid, generation: window.App.authState?.generation},
          getOwnKey: () => window.localStorage.getItem('openrouterKey'),
          isActive: () => turn.isConnected && answerBody.isConnected && turnData.source_verification?.job_id === jobId,
          onUpdate(value) {
            turnData.source_verification = value;
            window.App.sourceVerification?.render(answerBody, sourceReport, value, {differencesData: turnData.differences_data});
          }
        });
      }
      // Erst im DOM laesst sich messen, ob der Clamp ueberhaupt greift; nur
      // dann bekommt der Turn seinen Aufklapp-Link.
      requestAnimationFrame(() => {
        question.classList.toggle(
          "is-long",
          questionText.scrollHeight > questionText.clientHeight + 2
        );
      });
      return true;
    },

    // Der Live-Consensus wird fuer den naechsten Lauf wiederverwendet. Bevor
    // das passiert, frieren wir die sichtbare Frage und Antwort als statischen
    // Turn ein. Interaktive Marker werden dabei zu reinen Anzeigeelementen;
    // doppelte IDs oder tote Buttons duerfen nicht in den Live-DOM gelangen.
    archiveCurrentExchange() {
      const liveBody = window.App.consensusBodyEl?.();
      const exchange = this.spentExchange || this.lastExchange;
      if (!liveBody || !exchange?.question || !liveBody.textContent?.trim()) {
        return false;
      }
      const turnData = Object.assign(
        {},
        exchange.turn || { question: exchange.question, consensus: exchange.consensus }
      );
      // Die sichtbaren Anhaenge gehoeren zu genau diesem Turn und wandern mit
      // ihm in den Verlauf. Der gespeicherte Turn kennt sie inzwischen selbst;
      // der sichtbare Stand bleibt die Rueckfalllinie, wenn die Turn-Anlage
      // fuer diesen Lauf nicht zustande gekommen ist.
      if (!Array.isArray(turnData.attachments) || !turnData.attachments.length) {
        turnData.attachments = window.App.getThreadAttachments?.() || [];
      }
      return this.appendHistoryTurn(
        turnData,
        liveBody,
        document.getElementById("consensusVerdict")
      );
    },

    renderStoredTurn(turnData) {
      this.clearHistory();
      return this.appendHistoryTurn(turnData);
    },

    renderStoredTurns(turns) {
      this.clearHistory();
      let rendered = 0;
      (Array.isArray(turns) ? turns : []).forEach(turn => {
        if (this.appendHistoryTurn(turn)) rendered += 1;
      });
      return rendered;
    },

    clearHistory() {
      const history = document.getElementById("threadHistory");
      if (!history) return;
      history.replaceChildren();
      history.hidden = true;
    },

    offer(question, consensusText, turn = null) {
      if (!question || !consensusText) return;
      this.continuationUnavailable = false;
      this.followupInFlight = false;
      this.lastExchange = {
        question: question,
        consensus: consensusText,
        turn: turn && typeof turn === "object" ? turn : null
      };
      // Ein Lauf ist durchgelaufen: nichts mehr zurueckzuholen.
      this.spentExchange = null;
      this.render();
    },

    // Ein Lauf, der gar nicht stattgefunden hat (Kontingent leer), darf den
    // Gespraechsfaden nicht gefressen haben: consume() ist beim Absenden
    // passiert, gesendet wurde aber nichts. Sonst waere der Kontext weg,
    // waehrend die Absage-Karte sagt "nichts wurde gesendet" — und die
    // naechste Frage ginge stillschweigend ohne Kontext raus.
    restoreAfterBlockedRun() {
      if (!this.spentExchange) return;
      this.lastExchange = this.spentExchange;
      this.spentExchange = null;
      this.followupInFlight = false;
      this.render();
    },

    // Neuer Lauf ohne Kontext bzw. Clear: der Faden ist abgeschnitten.
    // Loescht auch das In-Flight-Flag (frische Frage darf wieder anbieten).
    reset() {
      this.lastExchange = null;
      this.followupInFlight = false;
      this.spentExchange = null;
      this.continuationUnavailable = false;
      this.render();
    },

    markContinuationUnavailable() {
      this.lastExchange = null;
      this.followupInFlight = false;
      this.spentExchange = null;
      this.continuationUnavailable = true;
      this.render();
    },

    // The returned one-hop payload remains for legacy bookmark restores. An
    // owned active chat uses only its server-issued context-version binding.
    consume() {
      if (!this.lastExchange) return null;
      const ctx = {
        previous_question: this.lastExchange.question,
        previous_consensus: this.lastExchange.consensus
      };
      const spent = this.lastExchange;
      this.reset();
      this.followupInFlight = true;
      // Nach reset(), sonst raeumt es sich selbst wieder weg.
      this.spentExchange = spent;
      return ctx;
    },

    // Der Kontext-Zustand hat KEINE eigene Flaeche mehr am Composer. Sichtbar
    // ist er dort, wo er hingehoert: im Thread, der ueber dem Eingabefeld
    // steht. Uebrig bleibt das Nachziehen der Login-Schranke und des
    // Platzhalters.
    render() {
      this.syncInputLock();
    },

    // Der Composer bleibt nach einer Antwort offen; hier wird nur noch die
    // Login-Schranke (updateQuestionInputAccess) nachgezogen und das
    // Platzhalter-Wording an den Kontext-Zustand angepasst — updateQuestion-
    // InputAccess laeuft nach jedem Auth-Update und wuerde den Follow-up-
    // Platzhalter sonst wieder ueberschreiben.
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
      input.placeholder = this.isArmed()
        ? FOLLOWUP_INPUT_PLACEHOLDER
        : (this.continuationUnavailable
            ? UNAVAILABLE_INPUT_PLACEHOLDER
            : DEFAULT_INPUT_PLACEHOLDER);
      window.App.agentChat?.syncComposer?.();
    }
  };
  window.App.followup = followup;

  // ------------------------------------------------------------------
  // RunContext consensus path. Unlike the legacy compatibility function
  // below, this path never reads response boxes, current bookmark globals or
  // the visible chat session. Query-send passes the exact owning context.
  function contextConsensusRenderer(context, target) {
    const RENDER_INTERVAL = 120;
    let timer = null;
    let lastRender = 0;
    function render() {
      timer = null;
      lastRender = Date.now();
      if (window.App.runRegistry.isVisible(context.runId)) {
        window.App.runRegistry.renderVisible();
      }
    }
    function schedule() {
      if (!window.App.runRegistry.isVisible(context.runId)) return;
      const elapsed = Date.now() - lastRender;
      if (elapsed >= RENDER_INTERVAL) render();
      else if (!timer) timer = window.setTimeout(render, RENDER_INTERVAL - elapsed);
    }
    return {
      append(chunk) {
        if (!window.App.runRegistry.isExecuting(context.runId)) return;
        const text = String(chunk || "");
        if (!text) return;
        if (target === "consensus") {
          context.consensus.status = "streaming";
          context.consensus.streamText += text;
        } else if (target === "consensus-final") {
          context.consensus.text = text;
          context.consensus.streamText = text;
          context.consensus.status = "differences";
          context.phase = "differences";
        } else {
          context.consensus.status = "differences";
          context.phase = "differences";
        }
        schedule();
      },
      markReasoning() {
        if (!window.App.runRegistry.isExecuting(context.runId)) return;
        if (target === "differences") {
          context.consensus.status = "differences";
          context.phase = "differences";
        }
        schedule();
      },
      stop() {
        if (timer) window.clearTimeout(timer);
        timer = null;
      }
    };
  }

  function runAnswer(context, provider) {
    const result = context.modelResults?.[provider];
    return result?.status === "complete" ? String(result.text || "").trim() : "";
  }

  // Server receipts of the completed answers (R09). The server resolves the
  // exact stored text, sources and model; the browser copy is never sent.
  function runReceipts(context) {
    return Object.fromEntries(familyKeys()
      .map(provider => [provider, context.modelResults?.[provider]])
      .filter(([, result]) => result?.status === "complete" && result.receipt
        && String(result.text || "").trim())
      .map(([provider, result]) => [provider, result.receipt]));
  }

  function runSources(context, provider) {
    const sources = context.modelResults?.[provider]?.sources;
    return Array.isArray(sources) ? sources.map(source => ({ ...source })) : [];
  }

  function runModelAnswers(context) {
    return Object.fromEntries(Object.entries(context.modelResults || {})
      .filter(([, result]) => result?.status === "complete" && String(result.text || "").trim())
      .map(([provider, result]) => [provider, {
        provider,
        model_label: result.modelLabel || provider,
        answer: result.text,
        sources: runSources(context, provider)
      }]));
  }

  function updateContextUsage(context, data) {
    const detail = data?.detail && typeof data.detail === "object" ? data.detail : {};
    const status = data?.usage_run_status || detail.usage_run_status;
    if (status && context.usage) context.usage.status = status;
    if (!window.App.runRegistry.isAuthCurrent(context)) return;
    // The booked account rides on the final event (or a 403 detail).
    window.App.renderUsageDisplay?.(data?.token_budget ? data : detail, context);
  }

  function contextCitationMeta(context) {
    let url = window.location.href;
    try {
      const parsed = new URL(window.location.href);
      url = parsed.origin + parsed.pathname;
    } catch (_) {}
    return {
      question: context.question,
      includedModels: (context.config.providers || [])
        .filter(provider => runAnswer(context, provider.provider))
        .map(provider => `${provider.provider}: ${provider.modelLabel || provider.modelId}`),
      consensusModel: context.config.consensusModelLabel || context.config.consensusModel,
      dateISO: new Date().toISOString(),
      url
    };
  }

  function consensusErrorMessage(result, data) {
    const detail = data?.detail;
    if (detail && typeof detail === "object") {
      return String(detail.error || detail.message || `Consensus HTTP ${result.status}`);
    }
    return String(data?.error || detail || `Consensus HTTP ${result.status}`);
  }

  window.App.executeConsensusRun = async function (context, options = {}) {
    const registry = window.App.runRegistry;
    if (!context || !registry.isExecuting(context.runId)) return null;
    if (["pending", "streaming", "differences"].includes(context.consensus.status)) return null;

    const trigger = String(options.trigger || "auto");
    let dispositionOnly = options.dispositionOnly === true;
    const controller = new AbortController();
    context.controllers.consensus = controller;
    context.phase = "consensus";
    context.consensus.status = "pending";
    context.consensus.sourceReferenceMode = 'none';
    context.consensus.error = null;
    registry.update(context.runId, () => {});

    const successfulAnswers = Object.values(context.modelResults || {})
      .filter(result => result?.status === "complete" && String(result.text || "").trim()).length;
    if (!dispositionOnly && successfulAnswers < 2 && context.chatSession?.pendingTurnId) {
      dispositionOnly = true;
    }
    if (!dispositionOnly && successfulAnswers < 2) {
      context.consensus.status = "error";
      context.consensus.error = { message: "At least two completed model answers are required." };
      context.credentials = null;
      context.attachments = [];
      registry.setStatus(context.runId, "failed", context.consensus.error);
      return null;
    }

    trackAppEvent("app_consensus_started", {
      trigger,
      included_models: successfulAnswers,
      excluded_models: Math.max(0, 6 - (context.config.providers || []).length),
      custom_credentials: context.config.useOwnKeys,
      logged_in: true
    });

    try {
      let idToken = null;
      try { idToken = await context.auth.user?.getIdToken?.(); } catch (_) {}
      if (!idToken || !registry.isAuthCurrent(context) || !registry.isExecuting(context.runId)) {
        throw new Error("Authentication changed while generating the consensus.");
      }

      const chatTurnIds = await context.chatSession?.ensurePendingTurn?.({
        idToken,
        question: context.question,
        consensusModel: context.config.consensusModel,
        signal: controller.signal
      }) || null;
      if (!registry.isExecuting(context.runId)) return null;

      const modelLabels = Object.fromEntries((context.config.providers || []).map(provider => [
        provider.provider,
        provider.modelLabel || provider.modelId || provider.provider
      ]));
      const payload = {
        id_token: idToken,
        useOwnKeys: context.config.useOwnKeys,
        usage_run_key: context.usage?.key || null,
        deep_search: context.config.deepSearch,
        check_sources: context.config.checkSources !== false,
        question: context.question,
        run_id: context.runId,
        answer_receipts: runReceipts(context),
        model_labels: modelLabels,
        consensus_model: context.config.consensusModel,
        bookmarkId: context.bookmark.id,
        previousQuestion: context.previousExchange?.question || "",
        previousTurn: context.previousExchange?.turn || null,
        excluded_models: familyKeys()
          .filter(provider => !context.config.providers.some(item => item.provider === provider)),
        openrouter_key: context.credentials?.openrouterKey || "",
        keepalive: true
      };
      if (chatTurnIds) {
        payload.chat_id = chatTurnIds.chatId;
        payload.turn_id = chatTurnIds.turnId;
        if (chatTurnIds.contextVersionId) payload.context_version_id = chatTurnIds.contextVersionId;
        payload.turn_sources = context.evidenceSources.map(source => ({ ...source }));
      }

      const requestResult = await streamSSERequest("/consensus", payload, controller.signal, {
        "sources.status": { receive(data) {
          if (!registry.isExecuting(context.runId)) return;
          context.consensus.sourceVerification = { status: data.status };
          window.App.runView?.projectSources?.(context);
        } },
        "sources.final": { receive(data) {
          if (!registry.isExecuting(context.runId)) return;
          context.consensus.sourceVerification = data.source_verification;
          window.App.runView?.projectSources?.(context);
        } },
        "differences.final": { receive(data) {
          if (!registry.isExecuting(context.runId)) return;
          context.consensus.differences = String(data.differences || "");
          context.consensus.differencesData = data.differences_data || null;
          context.consensus.differencesComplete = true;
          context.phase = context.consensus.sourceVerification?.status === "pending" ? "sources" : "finalizing";
          if (registry.isVisible(context.runId)) registry.renderVisible();
        } },
        "consensus.delta": contextConsensusRenderer(context, "consensus"),
        "consensus.reset": { receive() {
          // A failed synthesis attempt is discarded before the retry streams.
          if (!registry.isExecuting(context.runId)) return;
          context.consensus.streamText = "";
          if (registry.isVisible(context.runId)) registry.renderVisible();
        } },
        "consensus.final": contextConsensusRenderer(context, "consensus-final"),
        "differences.delta": contextConsensusRenderer(context, "differences")
      }).catch(error => recoverConsensusResult(context, payload, controller.signal, error));
      const data = requestResult.data || {};
      if (data.chat_replayed) context.consensus.sourceReferenceMode = data.source_verification?.check_type === 'contradiction_evidence' ? 'none' : 'legacy';
      if (!data.consensus_response && context.consensus.text) data.consensus_response = context.consensus.text;
      updateContextUsage(context, data);
      if (!registry.isExecuting(context.runId)) return data;

      const disposition = data?.chat_turn_state
        ? data
        : (data?.detail && typeof data.detail === "object" && data.detail.chat_turn_state ? data.detail : null);
      if (disposition) {
        context.chatSession?.handleConsensusResult?.({
          chatId: disposition.chat_id,
          turnId: disposition.turn_id,
          chatPersisted: disposition.chat_persisted === true,
          chatTurnState: disposition.chat_turn_state
        });
        context.chatTurnState = disposition.chat_turn_state;
        context.keepConversationLock = disposition.chat_turn_state === "pending";
      } else if (chatTurnIds) {
        context.chatSession?.markPendingUncertain?.();
        context.keepConversationLock = true;
      }

      const failedChatTurn = disposition?.chat_turn_state === "failed";
      const pendingChatTurn = disposition?.chat_turn_state === "pending";
      if (!requestResult.ok || !data.consensus_response || failedChatTurn || pendingChatTurn) {
        const message = failedChatTurn || pendingChatTurn
          ? String(
              disposition?.error
              || disposition?.message
              || (pendingChatTurn
                ? "The consensus was generated, but its conversation turn did not receive a final server status. Reload before continuing."
                : data.consensus_response)
              || "The consensus could not be completed."
            )
          : consensusErrorMessage(requestResult, data);
        context.consensus.status = "error";
        context.consensus.error = { message };
        // Typed state of the synthesis (R06): partial text stays visible but
        // is labelled as incomplete, never shown as a finished consensus.
        if (["token_limit", "interrupted"].includes(data.consensus_completion)) {
          context.consensus.completion = data.consensus_completion;
          context.consensus.error = { message: String(data.error || message), incomplete: true };
        }
        context.consensus.text = context.consensus.text || context.consensus.streamText;
        context.phase = "failed";
        context.bookmark.status = "failed";
        context.credentials = null;
        context.attachments = [];
        registry.setStatus(context.runId, "failed", context.consensus.error);
        const limitDetail = data?.detail && typeof data.detail === "object" ? data.detail : data;
        if (registry.isVisible(context.runId) && window.App.usageLimit?.isLimitError(limitDetail, message)) {
          window.App.usageLimit.show({ data: limitDetail, source: "consensus", phase: "consensus" });
        }
        trackAppEvent("app_consensus_completed", { status: "error", trigger, included_models: successfulAnswers });
        return data;
      }

      if (Array.isArray(data.sources)) context.evidenceSources = data.sources.map(source => ({ ...source }));
      if (data.chat_replayed === true) {
        // Recovery is authoritative. Answers absent from the stored turn must
        // not borrow text or sources from the interrupted local projection.
        const stored = data.model_answers || {};
        context.modelResults = Object.fromEntries((context.config.providers || []).map(provider => {
          const answer = stored[provider.provider];
          const text = typeof answer === "string" ? answer : String(answer?.answer || "");
          const modelLabel = answer?.model_label || answer?.model_id || provider.modelLabel || provider.modelId;
          if (text && modelLabel) modelLabels[provider.provider] = modelLabel;
          return [provider.provider, { ...(context.modelResults[provider.provider] || {}),
            text, streamText: text, status: text ? "complete" : "skipped",
            error: text ? null : "No stored answer is available for this model.", modelLabel,
            sources: Array.isArray(answer?.sources) ? answer.sources : [] }];
        }));
      }
      context.consensus.status = "complete";
      context.consensus.text = String(data.consensus_response || context.consensus.text || "");
      context.consensus.streamText = context.consensus.text;
      context.consensus.differences = String(data.differences || context.consensus.differences || "");
      context.consensus.differencesData = data.differences_data || context.consensus.differencesData || null;
      context.consensus.differencesComplete = true;
      context.consensus.sourceVerification = data.source_verification || context.consensus.sourceVerification || null;
      context.consensus.sources = context.evidenceSources.map(source => ({ ...source }));
      context.consensus.resultId = data.result_id || null;
      context.consensus.modelLabels = modelLabels;
      context.consensus.citationMeta = contextCitationMeta(context);

      const modelAnswers = data.model_answers && typeof data.model_answers === "object"
        && Object.keys(data.model_answers).length
        ? data.model_answers
        : runModelAnswers(context);
      const completedTurn = {
        turn_id: data.turn_id || chatTurnIds?.turnId || "",
        question: context.question,
        consensus: context.consensus.text,
        differences: context.consensus.differences,
        differences_data: context.consensus.differencesData,
        source_verification: context.consensus.sourceVerification,
        sources: context.evidenceSources.map(source => ({ ...source })),
        model_answers: modelAnswers,
        attachments: context.attachmentMeta.map(item => ({ ...item }))
      };
      context.consensus.completedTurn = completedTurn;

      const conversation = {
        runId: context.runId,
        auth: context.auth,
        bookmarkId: context.bookmark.id,
        chatId: data.chat_persisted === true && data.chat_turn_state === "completed"
          ? data.chat_id : null,
        turnId: data.chat_persisted === true && data.chat_turn_state === "completed"
          ? data.turn_id : null,
        sources: context.evidenceSources.map(source => ({ ...source })),
        modelResponses: Object.fromEntries(Object.entries(modelAnswers).map(([provider, item]) => [
          provider,
          typeof item === "string" ? item : String(item?.answer || "")
        ]))
      };
      context.consensus.bookmarkPayload = {
        question: context.question,
        resultId: context.consensus.resultId,
        previousQuestion: context.previousExchange?.question || "",
        previousTurn: context.previousExchange?.turn || null,
        consensusText: context.consensus.text,
        differencesText: context.consensus.differences,
        differencesData: context.consensus.differencesData,
        conversation
      };

      const completedBasis = {
        bookmarkId: context.bookmark.id,
        chatId: conversation.chatId || context.chatSession?.activeChatId || "",
        turnId: conversation.turnId || context.chatSession?.activeTurnId || completedTurn.turn_id,
        question: context.question,
        consensus: context.consensus.text,
        currentTurn: completedTurn,
        historyTurns: context.historyTurns,
        title: context.bookmark.title || context.question
      };
      context.completedBasis = completedBasis;
      context.phase = "done";
      context.bookmark.status = "succeeded";

      let savePromise = null;
      if (registry.isAuthCurrent(context) && data.chat_replayed !== true) {
        if (data.bookmark_persisted === true && data.bookmark_meta) {
          // The successful /consensus final event is now emitted only after
          // the primary server-side bookmark write. Apply its compact metadata
          // locally; no second network roundtrip is needed for the normal path.
          window.acceptPersistedConsensusBookmark?.(data.bookmark_meta, conversation);
          context.persistence.consensusWrite = true;
          savePromise = Promise.resolve(data.bookmark_meta);
        } else {
          // Cached servers and a failed primary write retain the idempotent
          // compatibility endpoint as a bounded, keepalive-enabled retry path.
          savePromise = window.saveBookmarkConsensus?.(
            context.question,
            context.consensus.text,
            context.consensus.differences,
            context.consensus.differencesData,
            context.consensus.resultId,
            context.config.consensusModel,
            modelLabels,
            context.previousExchange?.question || "",
            context.previousExchange?.turn || null,
            conversation
          );
        }
        context.persistence.consensusPromise = savePromise || null;
        savePromise?.catch?.(() => undefined);
      } else if (data.chat_replayed === true) {
        context.persistence.consensusWrite = true;
      }

      context.credentials = null;
      context.attachments = [];
      registry.setStatus(context.runId, "succeeded");
      registry.setCompletedBasis(context.runId, completedBasis);
      window.App.watchRunSources(context);

      if (registry.isAuthCurrent(context) && data.chat_replayed !== true) {
        const best = context.consensus.differencesData?.best_model || parseBestModel(context.consensus.differences);
        if (best) window.recordModelVote?.(best, "BestModel", context.consensus.resultId);
      }
      if (registry.isVisible(context.runId) && data.chat_replayed !== true) {
        window.App.watch?.showFeatureNudge?.();
      }
      if (data.chat_replayed !== true) {
        trackAppEvent("app_consensus_completed", {
          status: data.error ? "partial" : "success",
          trigger,
          included_models: successfulAnswers
        });
      }
      return data;
    } catch (error) {
      if (isAbortError(error) || !registry.isExecuting(context.runId)) return null;
      context.chatSession?.markPendingUncertain?.();
      if (context.chatSession?.pendingTurnId) context.keepConversationLock = true;
      context.consensus.status = "error";
      context.consensus.error = { message: error?.message || "The consensus request failed." };
      context.consensus.text = context.consensus.text || context.consensus.streamText;
      context.phase = "failed";
      context.bookmark.status = "failed";
      context.credentials = null;
      context.attachments = [];
      registry.setStatus(context.runId, "failed", context.consensus.error);
      window.App.reportCriticalError?.({
        type: "consensus_failed",
        phase: "consensus_connection",
        failure_kind: error?.streamFailureKind || "consensus_processing_failed",
        message: "The consensus request ended without a confirmed result.",
        details: `run ${context.requestIdentity}`
      });
      trackAppEvent("app_consensus_completed", {
        status: context.consensus.text ? "partial" : "error",
        trigger,
        included_models: successfulAnswers
      });
      return null;
    } finally {
      context.controllers.consensus = null;
      if (registry.isVisible(context.runId)) registry.renderVisible();
      window.App.syncSendButtonRunning?.();
    }
  };

  // Compatibility entry point: every paid consensus belongs to an admitted
  // RunContext (window.App.executeConsensusRun). Without an executing visible
  // run this bridge starts nothing.
  window.getConsensus = async function (trigger = "manual") {
    const registry = window.App.runRegistry;
    const boundContext = registry?.visible?.();
    if (boundContext && registry.isExecuting(boundContext.runId)) {
      return await window.App.executeConsensusRun(boundContext, {
        trigger,
        dispositionOnly: trigger === "disposition"
      });
    }
    if (trigger === "manual") {
      window.App.showPopup?.("Open a comparison that has answers ready before generating a consensus.");
    }
    return null;
  };
})();
