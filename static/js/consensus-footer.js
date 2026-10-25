// =====================================================================
// consensus-footer.js
// The surroundings of a saved Consensus answer on screen (a Consensus chat
// from before 2026-10-25, opened from the sidebar): showing and hiding the
// answer area, and the footer under it with its three drawers
// (Review differences · Compare answers · Sources).
//
// Until 2026-10-25 consensus-progress.js (the guided run block, run facts,
// "Run again") and consensus-lifecycle.js (gate, cancel, run state) lived
// here; the browser no longer runs the Consensus pipeline, so only what a
// saved answer needs is left.
// Exports: window.App.consensusFooter {render, clear},
//          window.revealConsensusOutput, window.hideConsensusOutput
// =====================================================================

(function () {
  window.App = window.App || {};

  const $ = id => document.getElementById(id);
  let revealTimer = null;

  function revealConsensusOutput() {
    const output = $("consensusOutput");
    if (!output) return;
    if (revealTimer) {
      clearTimeout(revealTimer);
      revealTimer = null;
    }
    output.classList.remove("is-hidden");
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        // No scroll here: chat-scroll.js owns all jumps.
        output.classList.add("is-visible");
      });
    });
  }

  function hideConsensusOutput() {
    const output = $("consensusOutput");
    if (!output) return;
    output.classList.remove("is-visible");
    if (revealTimer) clearTimeout(revealTimer);
    revealTimer = setTimeout(() => {
      output.classList.add("is-hidden");
    }, 280);
  }

  // ---- The three drawers ---------------------------------------------
  // Contradictions, model answers and sources are the everything-behind-the
  // answer. Each chip owns one disclosure and reports how much is in it, so
  // the reader can tell what is worth opening before opening it. The counts
  // are read off the rendered DOM: a second tally could disagree with what
  // is on screen.

  // count > 0 shows the number next to the label; count === 0 with
  // hasContent still offers the drawer but without a figure — the free-text
  // differences fallback has something to show and nothing to count.
  function syncTab(tabId, countId, panel, count, hasContent = count > 0) {
    const tab = $(tabId);
    if (!tab) return;
    const available = Boolean(panel) && hasContent;
    tab.hidden = !available;
    if (!available) return;
    const countEl = $(countId);
    if (countEl) countEl.textContent = count > 0 ? String(count) : "";
    tab.setAttribute("aria-expanded", String(isPanelOpen(panel)));
  }

  function isPanelOpen(panel) {
    if (!panel) return false;
    return panel.tagName === "DETAILS" ? panel.open : !panel.hidden;
  }

  function setPanelOpen(panel, open) {
    if (!panel) return;
    if (panel.tagName === "DETAILS") panel.open = open;
    else panel.hidden = !open;
  }

  function togglePanel(tab, panel) {
    if (!tab || !panel) return;
    const open = !isPanelOpen(panel);
    setPanelOpen(panel, open);
    tab.setAttribute("aria-expanded", String(open));
    if (open) {
      // Erst nach dem Layout scrollen: bei hidden -> sichtbar hatte der
      // Sources-Drawer sonst noch keine belastbare Geometrie. Bei langen
      // Quellenlisten fahren wir gezielt den ersten Eintrag an, damit nur ein
      // kleiner Inhaltsanfang ins Bild kommt statt der ganze Drawer zu springen.
      requestAnimationFrame(() => {
        const target = panel.id === "consensusSourcesPanel"
          ? panel.querySelector(".consensus-sources-list > li") || panel
          : panel;
        target.scrollIntoView({ block: "nearest", behavior: window.App.scrollBehavior?.() || "auto" });
      });
    }
  }

  function countDifferences() {
    const cards = $("differencesCards");
    if (!cards || cards.hidden) return 0;
    return cards.querySelectorAll(".diff-card").length;
  }

  // Anything in the drawer at all: cards, the "no contradictions" empty
  // state, or the free-text fallback paragraph.
  function differencesHasContent() {
    const panel = $("consensusDifferencesPanel");
    if (!panel) return false;
    const cards = $("differencesCards");
    if (cards && !cards.hidden && cards.childElementCount) return true;
    const fallback = panel.querySelector(".consensus-differences-content > p");
    return Boolean(fallback && !fallback.hidden && fallback.textContent.trim());
  }

  function countSources() {
    return document.querySelectorAll("#consensusSourcesList > li").length;
  }

  function render() {
    const wrap = $("runProvenance");
    if (!wrap) return;

    syncTab(
      "consensusDifferencesTab",
      "consensusDifferencesTabCount",
      $("consensusDifferencesPanel"),
      countDifferences(),
      differencesHasContent()
    );
    syncTab(
      "consensusSourcesTab",
      "consensusSourcesTabCount",
      $("consensusSourcesPanel"),
      countSources()
    );

    // "Compare answers" bekommt dieselbe Zahl wie die anderen beiden
    // Schubladen: wie viele Antworten dahinter liegen.
    const answersCount = $("consensusAnswersTabCount");
    if (answersCount) {
      const boxes = document.querySelectorAll(
        ".response-section > .response-box:not(.excluded)"
      ).length;
      answersCount.textContent = boxes > 0 ? String(boxes) : "";
    }

    const hasTabs = Boolean(
      document.querySelector("#consensusFooterTabs .consensus-tab:not([hidden])")
      || !$("agentModeAnswersRow")?.hidden
    );
    wrap.hidden = !hasTabs;
  }

  // The footer describes the one saved answer on screen; another view takes
  // it with it.
  function clear() {
    const wrap = $("runProvenance");
    if (wrap) wrap.hidden = true;
    ["consensusDifferencesTab", "consensusSourcesTab"].forEach(id => {
      const tab = $(id);
      if (tab) {
        tab.hidden = true;
        tab.setAttribute("aria-expanded", "false");
      }
    });
    setPanelOpen($("consensusSourcesPanel"), false);
  }

  document.addEventListener("click", event => {
    const diffTab = event.target.closest("#consensusDifferencesTab");
    if (diffTab) {
      if (window.App?.answerReader?.openPanel("differences", diffTab)) return;
      togglePanel(diffTab, $("consensusDifferencesPanel"));
      return;
    }
    const sourcesTab = event.target.closest("#consensusSourcesTab");
    if (sourcesTab) {
      if (window.App?.answerReader?.openPanel("sources", sourcesTab)) return;
      togglePanel(sourcesTab, $("consensusSourcesPanel"));
    }
  });

  // The differences drawer is a <details>; anything that opens or closes it
  // from elsewhere (the free-text fallback, a loaded bookmark) still has to
  // leave the chip telling the truth.
  $("consensusDifferencesPanel")?.addEventListener("toggle", () => {
    const tab = $("consensusDifferencesTab");
    if (tab) tab.setAttribute("aria-expanded", String($("consensusDifferencesPanel").open));
  });

  window.revealConsensusOutput = revealConsensusOutput;
  window.hideConsensusOutput = hideConsensusOutput;
  window.App.consensusFooter = Object.freeze({ render, clear });
})();
