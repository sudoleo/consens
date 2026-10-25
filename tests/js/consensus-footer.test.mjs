import { describe, expect, it, vi } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

// consensus-footer.js: what a saved Consensus answer (a chat from before
// 2026-10-25) needs on screen once the browser no longer runs the pipeline:
// show and hide the answer area, and the footer's drawers with their counts.
const BODY = `
  <div id="consensusOutput" class="consensus-output is-hidden">
    <div id="runProvenance" hidden>
      <div id="consensusFooterTabs">
        <button id="consensusDifferencesTab" class="consensus-tab" aria-expanded="false" hidden>
          <span id="consensusDifferencesTabCount"></span></button>
        <div id="agentModeAnswersRow" hidden><span id="consensusAnswersTabCount"></span></div>
        <button id="consensusSourcesTab" class="consensus-tab" aria-expanded="false" hidden>
          <span id="consensusSourcesTabCount"></span></button>
      </div>
    </div>
    <div id="consensusSourcesPanel" hidden><ol id="consensusSourcesList"></ol></div>
    <details id="consensusDifferencesPanel"><summary></summary>
      <div class="consensus-differences-content"><div id="differencesCards" hidden></div><p></p></div>
    </details>
  </div>
  <section class="response-section">
    <div class="response-box"></div><div class="response-box excluded"></div><div class="response-box"></div>
  </section>
`;

function boot() {
  return loadScripts(["static/js/consensus-footer.js"], {
    body: BODY,
    before(window) {
      window.App = {};
      window.requestAnimationFrame = callback => { callback(); return 1; };
    },
  });
}

describe("the footer of a saved Consensus answer", () => {
  it("offers only drawers with content and counts what is in them", () => {
    const { window, document, dom } = boot();
    const footer = document.getElementById("runProvenance");
    window.App.consensusFooter.render();
    expect(footer.hidden).toBe(true);

    document.getElementById("differencesCards").hidden = false;
    document.getElementById("differencesCards").innerHTML = '<div class="diff-card"></div><div class="diff-card"></div>';
    document.getElementById("consensusSourcesList").innerHTML = "<li>A</li>";
    window.App.consensusFooter.render();
    expect(footer.hidden).toBe(false);
    expect(document.getElementById("consensusDifferencesTab").hidden).toBe(false);
    expect(document.getElementById("consensusDifferencesTabCount").textContent).toBe("2");
    expect(document.getElementById("consensusSourcesTabCount").textContent).toBe("1");
    expect(document.getElementById("consensusAnswersTabCount").textContent).toBe("2");
    dom.window.close();
  });

  it("opens a drawer from its chip, or through the answer reader when it takes it", () => {
    const { window, document, dom } = boot();
    document.getElementById("consensusSourcesList").innerHTML = "<li>A</li>";
    window.App.consensusFooter.render();
    const tab = document.getElementById("consensusSourcesTab");
    const panel = document.getElementById("consensusSourcesPanel");
    panel.scrollIntoView = vi.fn();
    panel.querySelector("li").scrollIntoView = vi.fn();
    tab.click();
    expect(panel.hidden).toBe(false);
    expect(tab.getAttribute("aria-expanded")).toBe("true");
    tab.click();
    expect(panel.hidden).toBe(true);

    window.App.answerReader = { openPanel: vi.fn(() => true) };
    tab.click();
    expect(window.App.answerReader.openPanel).toHaveBeenCalledWith("sources", tab);
    expect(panel.hidden).toBe(true);
    dom.window.close();
  });

  it("clears with the view and shows or hides the answer area", () => {
    vi.useFakeTimers();
    try {
      const { window, document, dom } = boot();
      const output = document.getElementById("consensusOutput");
      document.getElementById("consensusSourcesList").innerHTML = "<li>A</li>";
      window.App.consensusFooter.render();
      window.App.consensusFooter.clear();
      expect(document.getElementById("runProvenance").hidden).toBe(true);
      expect(document.getElementById("consensusSourcesTab").hidden).toBe(true);

      window.revealConsensusOutput();
      expect(output.classList.contains("is-hidden")).toBe(false);
      expect(output.classList.contains("is-visible")).toBe(true);
      window.hideConsensusOutput();
      expect(output.classList.contains("is-visible")).toBe(false);
      vi.advanceTimersByTime(300);
      expect(output.classList.contains("is-hidden")).toBe(true);
      // Nothing of the retired live run is left to call.
      expect(window.App).not.toHaveProperty("consensusPipeline");
      expect(window).not.toHaveProperty("cancelCurrentConsensus");
      expect(window).not.toHaveProperty("canGenerateConsensus");
      dom.window.close();
    } finally {
      vi.useRealTimers();
    }
  });
});
