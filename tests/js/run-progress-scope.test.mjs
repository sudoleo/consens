import { describe, expect, it, vi } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

// The guided-run block, the answer boxes and the provenance footer are the
// single main view. A run that keeps going in the background must not write
// into it once the reader has opened something else.
const BODY = `
  <div id="bookmarksContainer"></div>
  <button id="sendButton"></button>
  <textarea id="questionInput"></textarea>
  <p id="composerRunNotice" hidden></p>
  <section id="consensusRun" class="run" data-stage="idle" hidden>
    <span id="runStatus"></span>
    <div class="run-past" id="runPast"></div>
    <div class="run-now">
      <span class="run-label" id="runLabel"></span>
      <span class="run-count" id="runCount"></span>
      <span class="run-time" id="runTime"></span>
    </div>
    <div class="run-track" id="runTrack"><i id="runBar"></i></div>
    <p class="run-next" id="runNext"></p>
    <div class="run-detail" id="runDetail" hidden></div>
  </section>
  <section class="response-section">
    <span id="openaiModelText"></span>
    <div id="openaiResponse" class="response-box" data-short-label="OpenAI"><div class="collapsible-content"></div></div>
  </section>
  <section id="consensusOutput" class="is-hidden">
    <div id="consensusResponse">
      <div id="consensusAnswerBody"></div>
      <div id="runProvenance" class="run-provenance" hidden>
        <div class="consensus-footer-tabs" id="consensusFooterTabs">
          <button type="button" id="consensusDifferencesTab" hidden><span id="consensusDifferencesTabCount"></span></button>
          <div id="agentModeAnswersRow" hidden></div>
          <button type="button" id="consensusSourcesTab" hidden><span id="consensusSourcesTabCount"></span></button>
        </div>
        <span id="runProvenanceFacts"></span>
        <button type="button" id="runReplayButton" hidden><span id="runReplayCost"></span></button>
      </div>
      <div id="consensusSourcesPanel" hidden><ol id="consensusSourcesList"></ol></div>
      <details id="consensusDifferencesPanel" class="consensus-differences">
        <div class="consensus-differences-content">
          <div id="differencesCards" hidden></div>
          <p></p>
        </div>
      </details>
    </div>
  </section>
`;

function boot() {
  const user = { uid: "scope-user", getIdToken: vi.fn(async () => "token") };
  const harness = loadScripts(
    [
      "static/js/run-registry.js",
      "static/js/consensus-progress.js",
      "static/js/run-view.js"
    ],
    {
      body: BODY,
      before(window) {
        window.auth = { currentUser: user };
        window.App = {
          authState: {
            generation: 1,
            snapshot: () => ({ uid: user.uid, generation: 1 })
          },
          modelPrefs: [{
            key: "OpenAI",
            responseId: "openaiResponse",
            textId: "openaiModelText"
          }],
          state: { set: vi.fn() },
          consensusBodyEl: root => root?.querySelector("#consensusAnswerBody"),
          setAppTitle: vi.fn(),
          setThreadQuestion: vi.fn(),
          setThreadQuestionAttachments: vi.fn(),
          bookmarkSession: { restore: vi.fn() },
          chatSession: { reset: vi.fn(), restoreCompletedChat: vi.fn() },
          followup: { renderStoredTurns: vi.fn(), reset: vi.fn(), offer: vi.fn() },
          differencesPanel: { setSynthesizing: vi.fn(), expandForFallback: vi.fn() },
          syncSendButtonRunning: vi.fn()
        };
        window.injectMarkdown = (element, markdown) => { element.textContent = markdown; };
        window.renderEvidenceSources = vi.fn();
        window.resetConsensusInsights = vi.fn();
        window.resetCredibilityFrame = vi.fn();
        window.updateAgentModeUI = vi.fn();
        window.syncHeroResponseAccess = vi.fn();
        window.exitHeroMode = vi.fn();
        window.enterDirectComparisonView = vi.fn();
        window.hideConsensusOutput = vi.fn();
        window.canGenerateConsensus = () => true;
        window.spinnerHTML = "loading";
        window.consensusSpinnerHTML = "consensus loading";
      }
    }
  );
  return { ...harness, registry: harness.window.App.runRegistry };
}

function startRun(registry, question, startedAt = Date.now()) {
  const context = registry.create({
    question,
    bookmarkId: `bookmark-${question}`,
    config: {
      agentMode: true,
      providers: [{ provider: "OpenAI", modelId: "m", modelLabel: "Model" }]
    }
  });
  context.startedAt = startedAt;
  context.modelResults.OpenAI = { provider: "OpenAI", boxId: "openaiResponse", status: "streaming", streamText: "half" };
  context.phase = "answers";
  registry.setStatus(context.runId, "running");
  return context;
}

describe("guided-run block belongs to the visible run", () => {
  it("leaves the view when a saved bookmark is opened and comes back with the run", () => {
    const { registry, document, window, dom } = boot();
    const run = startRun(registry, "A");
    const block = document.getElementById("consensusRun");

    expect(block.hidden).toBe(false);
    expect(document.getElementById("runLabel").textContent).toBe("Models are answering");

    // Opening a saved bookmark: firebase.js hands the registry a saved view.
    registry.showSavedView({ type: "bookmark", bookmarkId: "other" }, { bookmarkId: "other" });
    expect(block.hidden).toBe(true);
    expect(block.dataset.stage).toBe("idle");

    // A restored bookmark reveals its consensus; that must not manufacture a
    // "Writing the consensus" step for the run still going in the background.
    window.App.consensusPipeline.onConsensusStart();
    expect(block.hidden).toBe(true);

    // The background run walks on. Its progress stays in its sidebar row.
    registry.update(run.runId, context => {
      context.phase = "consensus";
      context.consensus.status = "streaming";
    });
    expect(block.hidden).toBe(true);
    expect(document.querySelector(`[data-run-id="${run.runId}"]`).textContent)
      .toContain("Writing consensus");

    registry.show(run.runId);
    expect(block.hidden).toBe(false);
    expect(document.getElementById("runLabel").textContent).toBe("Writing the consensus");
    dom.window.close();
  });

  it("keeps counting from the real start when a running run is reopened", async () => {
    const { registry, document, dom } = boot();
    const run = startRun(registry, "A", Date.now() - 12_000);

    registry.showSavedView({ type: "bookmark", bookmarkId: "other" });
    registry.show(run.runId);

    await new Promise(resolve => setTimeout(resolve, 260));
    expect(document.getElementById("runTime").textContent).toBe("0:12");
    dom.window.close();
  });

  it("shows a live per-model bar and completes it with the answer", async () => {
    const { registry, document, dom } = boot();
    const run = startRun(registry, "A");

    await new Promise(resolve => setTimeout(resolve, 220));
    const bar = document.querySelector(".run-model-track i");
    const runningProgress = parseFloat(bar.style.getPropertyValue("--p"));
    expect(runningProgress).toBeGreaterThan(0);
    expect(runningProgress).toBeLessThan(100);

    registry.update(run.runId, context => {
      context.modelResults.OpenAI = {
        provider: "OpenAI",
        boxId: "openaiResponse",
        status: "complete",
        text: "finished answer"
      };
    });
    await new Promise(resolve => setTimeout(resolve, 220));

    expect(bar.style.getPropertyValue("--p")).toBe("100.0%");
    expect(bar.closest(".run-model").dataset.state).toBe("done");
    dom.window.close();
  });

  it("never shows one run's facts under another view", () => {
    const { registry, document, window, dom } = boot();
    const run = startRun(registry, "A", Date.now() - 4000);
    run.modelResults.OpenAI = {
      provider: "OpenAI", boxId: "openaiResponse", status: "complete", text: "answer"
    };
    run.consensus.status = "complete";
    run.consensus.text = "consensus";
    registry.setStatus(run.runId, "succeeded");

    const facts = document.getElementById("runProvenanceFacts");
    expect(facts.textContent).toContain("1 models");

    // A loaded bookmark re-renders the footer for itself (renderEvidenceSources
    // does exactly this call). It must not inherit the run's numbers.
    registry.showSavedView({ type: "bookmark", bookmarkId: "other" });
    window.App.consensusPipeline.renderProvenance();
    expect(document.getElementById("runProvenance").hidden).toBe(true);
    expect(facts.textContent).toBe("");

    registry.show(run.runId);
    expect(facts.textContent).toContain("1 models");
    dom.window.close();
  });

  it("counts raw streamed characters without Markdown UI or surrogate duplication", async () => {
    const { registry, document, dom } = boot();
    const run = startRun(registry, "characters");
    registry.update(run.runId, context => {
      context.modelResults.OpenAI.streamText = "a".repeat(1234) + "😀";
    });
    // Rendering can add math, citation labels or copy buttons. They aren't tokens.
    document.querySelector(".collapsible-content").textContent = "rendered decorations";
    await new Promise(resolve => setTimeout(resolve, 220));
    const row = document.querySelector(".run-model");
    const status = row.querySelector(".run-model-time");
    expect(status.textContent).toBe("1,235 chars");
    expect(row.dataset.state).toBe("streaming");
    const bar = row.querySelector("i");
    const previous = parseFloat(bar.style.getPropertyValue("--p"));
    registry.update(run.runId, context => {
      context.modelResults.OpenAI.streamText += "abc";
    });
    await new Promise(resolve => setTimeout(resolve, 220));
    expect(status.textContent).toBe("1,238 chars");
    expect(parseFloat(bar.style.getPropertyValue("--p"))).toBeGreaterThanOrEqual(previous);
    expect(parseFloat(bar.style.getPropertyValue("--p"))).toBeLessThan(100);
    dom.window.close();
  });

  it("does not count waiting or reasoning placeholders", async () => {
    const { registry, document, dom } = boot();
    const run = startRun(registry, "waiting");
    for (const [state, label] of [["pending", "Waiting"], ["reasoning", "Reasoning"]]) {
      registry.update(run.runId, context => {
        context.modelResults.OpenAI = { status: state };
      });
      await new Promise(resolve => setTimeout(resolve, 220));
      expect(document.querySelector(".run-model-time").textContent).toBe(label);
      expect(document.querySelector(".run-model").dataset.state).not.toBe("done");
    }
    dom.window.close();
  });

  it.each([["error", "Failed"], ["skipped", "Skipped"], ["canceled", "Canceled"]])(
    "shows %s as a terminal outcome, never a successful answer or character count",
    async (state, label) => {
      const { registry, document, dom } = boot();
      const run = startRun(registry, state);
      registry.update(run.runId, context => {
        context.modelResults.OpenAI = { status: state, error: "Not answer text" };
      });
      await new Promise(resolve => setTimeout(resolve, 220));
      expect(document.querySelector(".run-model-time").textContent).toBe(label);
      expect(document.querySelector(".run-model").dataset.state).not.toBe("done");
      expect(document.getElementById("runCount").textContent).toBe("1 of 1 finished");
      dom.window.close();
    }
  );

  it("freezes completion time and restores only the selected run's characters", async () => {
    const { registry, document, dom } = boot();
    const a = startRun(registry, "A");
    await new Promise(resolve => setTimeout(resolve, 220));
    const aStatus = document.querySelector(".run-model-time");
    expect(aStatus.textContent).toBe("4 chars");
    registry.update(a.runId, context => {
      context.modelResults.OpenAI = { status: "complete", text: "finished" };
    });
    await new Promise(resolve => setTimeout(resolve, 220));
    const completion = aStatus.textContent;
    expect(completion).toMatch(/^✓ Done — \d+\.\ds$/);
    expect(aStatus.title).toBe("8 characters received");
    await new Promise(resolve => setTimeout(resolve, 220));
    expect(aStatus.textContent).toBe(completion);
    registry.clearVisible();
    const b = startRun(registry, "B");
    registry.update(b.runId, context => { context.modelResults.OpenAI.streamText = "different"; });
    await new Promise(resolve => setTimeout(resolve, 220));
    expect(document.querySelector(".run-model-time").textContent).toBe("9 chars");
    registry.show(a.runId);
    await new Promise(resolve => setTimeout(resolve, 220));
    expect(document.querySelector(".run-model-time").textContent).toMatch(/^✓ Done/);
    expect(document.querySelector(".run-model-time").title).toBe("8 characters received");
    dom.window.close();
  });

  it("does not repeatedly announce each timer tick or streamed character", async () => {
    const { registry, document, window, dom } = boot();
    const run = startRun(registry, "announcements");
    await new Promise(resolve => setTimeout(resolve, 220));
    const announcements = vi.fn();
    const observer = new window.MutationObserver(announcements);
    observer.observe(document.getElementById("runStatus"), { childList: true, characterData: true, subtree: true });
    registry.update(run.runId, context => { context.modelResults.OpenAI.streamText += "new text"; });
    await new Promise(resolve => setTimeout(resolve, 450));
    expect(announcements).not.toHaveBeenCalled();
    registry.update(run.runId, context => { context.modelResults.OpenAI = { status: "complete", text: "done" }; });
    await new Promise(resolve => setTimeout(resolve, 220));
    expect(announcements).toHaveBeenCalledTimes(1);
    observer.disconnect();
    dom.window.close();
  });
});
