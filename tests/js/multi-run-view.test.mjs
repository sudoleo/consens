import { describe, expect, it, vi } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

const BODY = `
  <div id="threadHistory" hidden></div>
  <div id="bookmarksContainer"></div>
  <button id="sendButton"></button>
  <span id="openaiModelText"></span>
  <div id="openaiResponse" class="response-box"><div class="collapsible-content"></div></div>
  <span id="mistralModelText"></span>
  <div id="mistralResponse" class="response-box"><div class="collapsible-content"></div></div>
  <span id="claudeModelText"></span>
  <div id="claudeResponse" class="response-box"><div class="collapsible-content"></div></div>
  <span id="geminiModelText"></span>
  <div id="geminiResponse" class="response-box"><div class="collapsible-content"></div></div>
  <span id="deepseekModelText"></span>
  <div id="deepseekResponse" class="response-box"><div class="collapsible-content"></div></div>
  <span id="grokModelText"></span>
  <div id="grokResponse" class="response-box"><div class="collapsible-content"></div></div>
  <section id="consensusOutput" class="is-hidden">
    <div id="consensusResponse">
      <div id="consensusAnswerBody"></div>
      <div class="consensus-differences"><p></p></div>
    </div>
  </section>
`;

function boot({ realHistory = false } = {}) {
  const user = { uid: "view-user", getIdToken: vi.fn(async () => "token") };
  const state = new Map();
  const harness = loadScripts(
    ["static/js/run-registry.js", ...(realHistory ? ["static/js/consensus-run.js"] : []), "static/js/run-view.js"],
    {
      body: BODY,
      before(window) {
        window.auth = { currentUser: user };
        window.App = {
          // Familienliste der App (im Browser aus window.MODEL_FAMILIES,
          // serverseitig cfg.PROVIDERS). run-view projiziert genau diese.
          modelPrefs: [
            ["OpenAI", "openai"], ["Mistral", "mistral"], ["Anthropic", "claude"],
            ["Gemini", "gemini"], ["DeepSeek", "deepseek"], ["Grok", "grok"]
          ].map(([key, dom]) => ({
            key,
            responseId: `${dom}Response`,
            textId: `${dom}ModelText`
          })),
          authState: {
            generation: 3,
            snapshot: () => ({ uid: user.uid, generation: 3 })
          },
          state: { set: (key, value) => state.set(key, value) },
          // Im Browser kommt das aus app-state.js (head-Bundle); run-view
          // vergleicht damit die Stufe des Laufs gegen die auf dem Schirm.
          normalizeTier: (value) => {
            if (value === true) return "pro";
            if (value === false || value === null || value === undefined) return "free";
            const text = String(value).trim().toLowerCase();
            if (text === "pro" || text === "premium") return "pro";
            if (text === "plus") return "plus";
            return "free";
          },
          consensusBodyEl: root => root?.querySelector("#consensusAnswerBody"),
          setAppTitle: vi.fn(),
          setThreadQuestion: vi.fn(),
          setThreadQuestionAttachments: vi.fn(),
          bookmarkSession: { restore: vi.fn() },
          chatSession: { reset: vi.fn(), restoreCompletedChat: vi.fn() },
          followup: {
            renderStoredTurns: vi.fn(),
            reset: vi.fn(),
            offer: vi.fn()
          },
          consensusPipeline: {
            dismiss: vi.fn(),
            onPrepare: vi.fn(),
            onQueryStatus: vi.fn(),
            onConsensusStart: vi.fn(),
            onDifferencesStart: vi.fn(),
            onConsensusEnd: vi.fn(),
            renderProvenance: vi.fn()
          },
          differencesPanel: {
            setSynthesizing: vi.fn(),
            expandForFallback: vi.fn()
          },
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
        window.spinnerHTML = "loading";
        window.consensusSpinnerHTML = "consensus loading";
      }
    }
  );
  return { ...harness, registry: harness.window.App.runRegistry, state };
}

function createRunning(registry, question) {
  const context = registry.create({
    question,
    mode: "Standard",
    bookmarkId: `bookmark-${question}`,
    config: {
      agentMode: true,
      providers: [{ provider: "OpenAI", modelId: `model-${question}`, modelLabel: `Model ${question}` }]
    }
  });
  context.modelResults.OpenAI = {
    provider: "OpenAI",
    status: "complete",
    text: `answer ${question}`,
    streamText: `answer ${question}`,
    sources: []
  };
  context.progress.totalModels = 1;
  context.phase = "answers";
  registry.setStatus(context.runId, "running");
  return context;
}

describe("selected RunContext projection", () => {
  it('continues source hydration after consensus succeeds without projecting a hidden run', () => {
    const {registry, window, document, dom} = boot({realHistory: true});
    const observe = vi.fn(() => vi.fn());
    window.App.sourceVerification = {observe, renderCurrent: vi.fn()};
    const run = createRunning(registry, 'First');
    const queued = {job_id: 'job-first', status: 'queued', answer_version: 'first'};
    run.consensus.status = 'complete'; run.consensus.text = 'Consensus First';
    run.consensus.sourceVerification = queued;
    run.consensus.completedTurn = {source_verification: queued};
    run.consensus.bookmarkPayload = {};
    run.completedBasis = {bookmarkId: run.bookmark.id, currentTurn: run.consensus.completedTurn};
    registry.setStatus(run.runId, 'succeeded');
    expect(observe).toHaveBeenCalledOnce();
    const binding = observe.mock.calls[0][0];
    expect(binding.isActive()).toBe(true);
    const second = createRunning(registry, 'Second');
    second.consensus.status = 'complete'; second.consensus.text = 'Consensus Second';
    registry.renderVisible();
    const before = document.getElementById('consensusAnswerBody').textContent;
    const complete = {...queued, status: 'complete', findings: [{sentence_id: 1, source_id: 'S1'}]};
    binding.onUpdate(complete);
    expect(run.consensus.completedTurn.source_verification).toBe(complete);
    expect(run.consensus.bookmarkPayload.sourceVerification).toBe(complete);
    expect(run.completedBasis.currentTurn.source_verification).toEqual(complete);
    expect(document.getElementById('consensusAnswerBody').textContent).toBe(before);
    registry.show(run.runId);
    expect(observe).toHaveBeenCalledOnce();
    registry.clearAll();
    expect(binding.isActive()).toBe(false);
    dom.window.close();
  });
  it('hydrates a saved terminal source stub for a historical turn only while its body exists', () => {
    const {window, document, dom} = boot({realHistory: true});
    const observe = vi.fn(() => vi.fn()), render = vi.fn();
    window.App.sourceVerification = {observe, render};
    const turn = {turn_id: 'old', question: 'Old', consensus: 'Saved consensus',
      source_verification: {job_id: 'old-job', status: 'complete', findings: []}};
    window.App.followup.renderStoredTurn(turn);
    expect(observe).toHaveBeenCalledOnce();
    const binding = observe.mock.calls[0][0];
    expect(binding.snapshot.status).toBe('complete');
    expect(binding.isActive()).toBe(true);
    const hydrated = {...turn.source_verification, findings: [{sentence_id: 1, source_id: 'S1'}]};
    binding.onUpdate(hydrated);
    expect(turn.source_verification).toBe(hydrated);
    expect(render.mock.calls.at(-1)[2]).toBe(hydrated);
    document.querySelector('.thread-history-turn').remove();
    expect(binding.isActive()).toBe(false);
    dom.window.close();
  });
  it("preserves completed history, open drawers and waiting model animations during follow-up streaming", () => {
    const { registry, window, document, dom } = boot({ realHistory: true });
    window.spinnerHTML = '<span class="thinking-wrap"><span class="thinking typing-indicator"></span></span>';
    const run = registry.create({
      question: "Second question",
      config: { agentMode: true, providers: [
        { provider: "OpenAI", modelLabel: "OpenAI" },
        { provider: "Gemini", modelLabel: "Gemini" }
      ] }
    });
    run.historyTurns.push({ turn_id: "first-turn", question: "First question",
      consensus: "Completed consensus", differences: "A previous difference" });
    run.modelResults.OpenAI = { status: "streaming", streamText: "New answer" };
    run.modelResults.Gemini = { status: "pending", streamText: "" };
    run.phase = "answers";
    registry.setStatus(run.runId, "running");

    const historyTurn = document.querySelector(".thread-history-turn");
    const tab = historyTurn.querySelector(".consensus-tab");
    tab.click();
    tab.focus();
    const panel = document.getElementById(tab.getAttribute("aria-controls"));
    const spinner = document.querySelector("#geminiResponse .thinking-wrap");
    const render = vi.spyOn(window, "injectMarkdown");
    for (let i = 0; i < 12; i += 1) {
      run.modelResults.OpenAI.streamText += " token";
      registry.renderVisible();
    }
    expect(document.querySelector(".thread-history-turn")).toBe(historyTurn);
    expect(document.activeElement).toBe(tab);
    expect(panel.hidden).toBe(false);
    expect(document.querySelector("#geminiResponse .thinking-wrap")).toBe(spinner);
    expect(render.mock.calls.every(([element]) => element.closest("#openaiResponse"))).toBe(true);
    expect(document.querySelector("#openaiResponse .collapsible-content").textContent).toBe(run.modelResults.OpenAI.streamText);

    // An actual history change must still project, including an in-place update.
    run.historyTurns[0].consensus = "Updated saved consensus";
    registry.renderVisible();
    expect(document.querySelector(".thread-history-answer-body").textContent).toBe("Updated saved consensus");
    run.modelResults.Gemini.status = "reasoning";
    registry.renderVisible();
    expect(document.querySelector("#geminiResponse .typing-indicator").dataset.text).toBe("Reasoning");
    run.modelResults.Gemini = { status: "complete", text: "Finished answer", sources: [] };
    registry.renderVisible();
    expect(document.querySelector("#geminiResponse .thinking-wrap")).toBeNull();
    expect(document.getElementById("geminiResponse").dataset.responseState).toBe("complete");
    const completedNode = document.querySelector("#geminiResponse .collapsible-content").firstChild;
    run.modelResults.OpenAI.streamText += " more";
    registry.renderVisible();
    expect(document.querySelector("#geminiResponse .collapsible-content").firstChild).toBe(completedNode);

    // Saved views can replace the same DOM; returning must invalidate caches.
    registry.showSavedView({ type: "bookmark", bookmarkId: "saved" }, { bookmarkId: "saved" });
    window.App.followup.clearHistory();
    document.querySelector("#geminiResponse .collapsible-content").textContent = "Saved answer";
    registry.show(run.runId);
    expect(document.querySelector(".thread-history-answer-body").textContent).toBe("Updated saved consensus");
    expect(document.querySelector("#geminiResponse .collapsible-content").textContent).toBe("Finished answer");
    dom.window.close();
  });

  it("refreshes model source mappings and terminal errors without text changes", () => {
    const { registry, window, document, dom } = boot();
    const run = createRunning(registry, "Sources");
    const render = vi.spyOn(window, "injectMarkdown");
    registry.renderVisible();
    expect(render).not.toHaveBeenCalled();
    run.evidenceSources.push({ id: "S1", url: "https://example.com" });
    run.modelResults.OpenAI.sources.push({ id: "S1", url: "https://example.com" });
    registry.renderVisible();
    expect(render).toHaveBeenCalled();
    expect(JSON.parse(document.getElementById("openaiResponse").dataset.consensusSources)).toHaveLength(1);
    run.modelResults.OpenAI.status = "skipped";
    run.modelResults.OpenAI.error = "Skipped model";
    registry.renderVisible();
    expect(document.getElementById("openaiResponse").dataset.responseSkipped).toBe("true");
    expect(document.querySelector("#openaiResponse .collapsible-content").textContent).toBe("Skipped model");
    dom.window.close();
  });

  it("publishes insights while sources are pending and preserves their DOM through source and final events", () => {
    const { registry, window, document, dom } = boot();
    const run = createRunning(registry, "Independent judges");
    const sourceRender = vi.fn();
    window.App.sourceVerification = { renderCurrent: sourceRender };
    window.renderConsensusInsights = vi.fn(() => {
      document.getElementById("consensusAnswerBody").innerHTML = '<span class="cx-claim">Consensus claim</span>';
      document.querySelector(".consensus-differences p").innerHTML = '<span class="diff-card">Original difference</span>';
      return true;
    });
    registry.update(run.runId, context => {
      Object.assign(context.consensus, { text: "Consensus claim", status: "complete",
        differences: "Original difference", differencesData: { agreement: { score: 88 } },
        differencesComplete: true, sourceVerification: { status: "pending" } });
      context.phase = "sources";
    });
    const claim = document.querySelector(".cx-claim"), diff = document.querySelector(".diff-card");
    expect(claim).not.toBeNull(); expect(diff).not.toBeNull();
    expect(window.App.consensusPipeline.onConsensusEnd).toHaveBeenCalled();
    expect(sourceRender).toHaveBeenLastCalledWith({ status: "pending" }, {differencesData: run.consensus.differencesData});
    const renders = window.renderConsensusInsights.mock.calls.length;
    const resets = window.resetConsensusInsights.mock.calls.length;
    run.consensus.sourceVerification = { status: "complete", findings: [] };
    window.App.runView.projectSources(run);
    expect(window.resetConsensusInsights).toHaveBeenCalledTimes(resets);
    registry.setStatus(run.runId, "succeeded");
    expect(window.renderConsensusInsights).toHaveBeenCalledTimes(renders);
    expect(document.querySelector(".cx-claim")).toBe(claim);
    expect(document.querySelector(".diff-card")).toBe(diff);
    const other = createRunning(registry, "Other");
    sourceRender.mockClear();
    window.App.runView.projectSources(run);
    expect(sourceRender).not.toHaveBeenCalled();
    expect(registry.visible()).toBe(other);
    dom.window.close();
  });
  it("keeps late background updates out of the visible DOM and restores either run from its row", () => {
    const { registry, document, dom } = boot();
    const runA = createRunning(registry, "A");
    const runB = createRunning(registry, "B");
    const output = document.querySelector("#openaiResponse .collapsible-content");

    expect(registry.visible().runId).toBe(runB.runId);
    expect(output.textContent).toBe("answer B");

    registry.update(runA.runId, context => {
      context.modelResults.OpenAI.text = "late answer A";
      context.modelResults.OpenAI.streamText = "late answer A";
    });

    expect(output.textContent).toBe("answer B");
    expect(document.querySelectorAll(".bookmark.run-entry")).toHaveLength(2);
    expect(document.querySelector(`[data-run-id="${runA.runId}"]`)?.textContent).toContain("Models answering");

    document.querySelector(`[data-run-id="${runA.runId}"]`).click();
    expect(registry.visible().runId).toBe(runA.runId);
    expect(output.textContent).toBe("late answer A");

    registry.cancel(runB.runId, "user");
    expect(registry.visible().runId).toBe(runA.runId);
    expect(output.textContent).toBe("late answer A");
    expect(document.querySelector(`[data-run-id="${runB.runId}"]`)?.textContent).toContain("Canceled");

    document.querySelector(`[data-run-id="${runB.runId}"]`).click();
    expect(registry.visible().runId).toBe(runB.runId);
    expect(output.textContent).toBe("answer B");
    dom.window.close();
  });
});

describe("projection re-entrancy", () => {
  it("survives a surface that renders the visible run back at it", () => {
    const { registry, window, document, dom } = boot();
    let tierCalls = 0;
    // The real chain is updateUserTierUI -> restoreModelSelections ->
    // setModelSelectionState -> renderVisible. Any such feedback used to
    // recurse until "Maximum call stack size exceeded", which the run then
    // reported as a failure right after /prepare.
    window.updateUserTierUI = () => {
      tierCalls += 1;
      registry.renderVisible();
    };

    const run = createRunning(registry, "A");
    run.usage = { isProUser: true };
    expect(() => registry.update(run.runId, () => {})).not.toThrow();
    expect(tierCalls).toBe(1);
    expect(document.querySelector("#openaiResponse .collapsible-content").textContent)
      .toBe("answer A");

    // A tier the view already shows is not pushed again on every stream tick.
    // app-state.js exposes window.userTier as a read-only view, so mimic that
    // shape rather than assigning (a plain write throws in the real app).
    Object.defineProperty(window, "userTier", { get: () => "pro", configurable: true });
    registry.update(run.runId, () => {});
    expect(tierCalls).toBe(1);
    dom.window.close();
  });
});

describe("run-local evidence mapping", () => {
  it("rewrites source numbers against the supplied run without touching the visible global", () => {
    const stateSet = vi.fn();
    const renderEvidence = vi.fn();
    const { window, dom } = loadScripts(["static/js/sources.js"], {
      before(target) {
        target.App = { state: { set: stateSet } };
        target.currentEvidenceSources = [{ id: "S1", url: "https://visible.example/source" }];
        target.renderEvidenceSources = renderEvidence;
      }
    });

    const runAFirst = window.App.prepareResponseSourcesForEvidence(
      "A [S1]",
      [{ id: "S1", url: "https://a.example/one", title: "A one" }],
      []
    );
    const runBFirst = window.App.prepareResponseSourcesForEvidence(
      "B [S1]",
      [{ id: "S1", url: "https://b.example/one", title: "B one" }],
      []
    );
    const runASecond = window.App.prepareResponseSourcesForEvidence(
      "A again [S1]",
      [{ id: "S1", url: "https://a.example/two", title: "A two" }],
      runAFirst.evidenceSources
    );

    expect(runAFirst.markdown).toBe("A [1]");
    expect(runBFirst.markdown).toBe("B [1]");
    expect(runASecond.markdown).toBe("A again [2]");
    expect(runASecond.evidenceSources.map(source => source.url)).toEqual([
      "https://a.example/one",
      "https://a.example/two"
    ]);
    expect(runBFirst.evidenceSources.map(source => source.url)).toEqual([
      "https://b.example/one"
    ]);
    expect(window.currentEvidenceSources).toEqual([
      { id: "S1", url: "https://visible.example/source" }
    ]);
    expect(stateSet).not.toHaveBeenCalled();
    expect(renderEvidence).not.toHaveBeenCalled();
    dom.window.close();
  });

  it("moves a legacy leading source block behind the first model claim", () => {
    const { window, dom } = loadScripts(["static/js/sources.js"], {
      before(target) {
        target.App = { state: { set: vi.fn() } };
        target.currentEvidenceSources = [];
      }
    });

    expect(window.rewriteSourceTags(
      "[S1] [S2] Die erste Aussage ist belegt. Danach folgt mehr Text.",
      { S1: 3, 1: 3, S2: 4, 2: 4 }
    )).toBe("Die erste Aussage ist belegt. [3] [4] Danach folgt mehr Text.");

    expect(window.rewriteSourceTags(
      "Die Quellen stehen bereits richtig.[S1]",
      { S1: 1, 1: 1 }
    )).toBe("Die Quellen stehen bereits richtig.[1]");
    dom.window.close();
  });
});
