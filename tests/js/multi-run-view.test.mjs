import { describe, expect, it, vi } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);

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
    ["static/js/run-registry.js", ...(realHistory ? ["static/js/thread-history.js"] : []), "static/js/agent-activity.js",
      "static/js/run-view.js"],
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
          followup: {
            renderStoredTurns: vi.fn(),
            clearHistory: vi.fn(),
            reset: vi.fn()
          },
          consensusFooter: { render: vi.fn(), clear: vi.fn() },
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
      agentMode: false,
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
  it('gives an archived Agent turn one evidence row and no second Sources footer', () => {
    const {window, document, dom} = boot({realHistory: true});
    for (const src of ['static/js/agent-review.js']) {
      const script = document.createElement('script');
      script.textContent = require('node:fs').readFileSync(src, 'utf8');
      document.body.append(script);
    }
    window.App.answerReader = {openContext: vi.fn(), refreshContext: vi.fn(), registerTurn: vi.fn()};
    const text = 'Checked answer.';
    window.App.followup.renderStoredTurn({turn_id: 'agent-old', question: 'Q', consensus: text, execution_mode: 'agent',
      sources: [{url: 'https://example.org/a', title: 'A'}],
      agent_review: {status: 'succeeded', answer_version: 1, answer_hash: 'h', versions: [{id: 1, text, hash: 'h'}],
        comparisons: [{id: 'c1', basis_hash: 'b', question: 'Q', status: 'succeeded', answers: [{provider: 'openai', model: {label: 'GPT'}, text: 'x', sources: []}]}],
        checks: [{comparison_id: 'c1', basis_hash: 'b', answer_hash: 'h', status: 'succeeded', differences_data: {differences: []}}]}});
    const turn = document.querySelector('.thread-history-turn');
    const review = turn.querySelector('.agent-review');
    expect(review).not.toBeNull();
    expect(turn.querySelectorAll('.agent-review')).toHaveLength(1);
    expect(turn.querySelector('.thread-history-footer').hidden).toBe(true);
    dom.window.close();
  });
  it("preserves waiting model animations and finished answers while the others stream", () => {
    const { registry, window, document, dom } = boot();
    window.spinnerHTML = '<span class="thinking-wrap"><span class="thinking typing-indicator"></span></span>';
    const run = registry.create({
      question: "Second question",
      config: { agentMode: false, providers: [
        { provider: "OpenAI", modelLabel: "OpenAI" },
        { provider: "Gemini", modelLabel: "Gemini" }
      ] }
    });
    run.modelResults.OpenAI = { status: "streaming", streamText: "New answer" };
    run.modelResults.Gemini = { status: "pending", streamText: "" };
    run.phase = "answers";
    registry.setStatus(run.runId, "running");

    // A comparison continues nothing: no history above it.
    expect(window.App.followup.clearHistory).toHaveBeenCalled();
    expect(window.App.followup.renderStoredTurns).not.toHaveBeenCalled();
    const spinner = document.querySelector("#geminiResponse .thinking-wrap");
    const render = vi.spyOn(window, "injectMarkdown");
    for (let i = 0; i < 12; i += 1) {
      run.modelResults.OpenAI.streamText += " token";
      registry.renderVisible();
    }
    expect(document.querySelector("#geminiResponse .thinking-wrap")).toBe(spinner);
    expect(render.mock.calls.every(([element]) => element.closest("#openaiResponse"))).toBe(true);
    expect(document.querySelector("#openaiResponse .collapsible-content").textContent).toBe(run.modelResults.OpenAI.streamText);

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
    document.querySelector("#geminiResponse .collapsible-content").textContent = "Saved answer";
    registry.show(run.runId);
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

  it("takes a saved Consensus answer off the screen when a comparison opens, once", () => {
    const { registry, window, document, dom } = boot();
    const output = document.getElementById("consensusOutput");
    output.classList.remove("is-hidden");
    output.classList.add("is-visible");
    document.getElementById("consensusAnswerBody").textContent = "Saved consensus";
    document.querySelector(".consensus-differences p").textContent = "Saved difference";
    const run = createRunning(registry, "Compare");
    expect(output.classList.contains("is-hidden")).toBe(true);
    expect(output.classList.contains("is-visible")).toBe(false);
    expect(document.getElementById("consensusAnswerBody").textContent).toBe("");
    expect(document.querySelector(".consensus-differences p").textContent).toBe("");
    expect(window.resetConsensusInsights).toHaveBeenCalled();
    expect(window.App.consensusFooter.clear).toHaveBeenCalled();
    expect(window.enterDirectComparisonView).toHaveBeenCalled();
    // Further updates of the same run leave the consensus area alone.
    const resets = window.resetConsensusInsights.mock.calls.length;
    for (let i = 0; i < 3; i += 1) registry.update(run.runId, () => {});
    expect(window.resetConsensusInsights).toHaveBeenCalledTimes(resets);
    dom.window.close();
  });
  it("builds a run's row once and changes only its words, so its pulse runs on (Apple audit C7)", () => {
    const { registry, document, dom } = boot();
    const run = createRunning(registry, "Pulse");
    const row = document.querySelector(`[data-run-id="${run.runId}"]`);
    const label = row.querySelector("p"), status = row.querySelector(".run-entry-status");
    const writes = [];
    new dom.window.MutationObserver(records => writes.push(...records)).observe(label, { childList: true, characterData: true, subtree: true });
    expect(status.textContent).toBe("Models answering");
    registry.update(run.runId, context => { context.phase = "prepare"; });
    for (let i = 0; i < 5; i += 1) registry.update(run.runId, () => {});
    expect(row.querySelector("p")).toBe(label);
    expect(row.querySelector(".run-entry-status")).toBe(status);
    expect(status.textContent).toBe("Preparing");
    expect(row.classList.contains("is-pending")).toBe(true);
    return new Promise(resolve => setTimeout(() => {
      // The unchanged title was never written again.
      expect(writes).toHaveLength(0);
      dom.window.close();
      resolve();
    }));
  });

  // A-B2 (docs/agent-audit-readiness-2026-10-29.md): a paused Agent run of a
  // chat not on screen read "Working" with its pulse while the pause ran
  // into its timeout.
  it("says in the row of a chat not on screen that its run waits for the user", () => {
    const { registry, document, dom, window } = boot();
    window.App.agentChat = { render: vi.fn(), project: vi.fn() };
    const agent = registry.create({ question: "Paused", mode: "Agent", bookmarkId: "bookmark-agent",
      config: { executionMode: "agent", agentMode: true } });
    registry.setStatus(agent.runId, "running");
    createRunning(registry, "Visible");
    expect(registry.visible().runId).not.toBe(agent.runId);
    const row = document.querySelector(`[data-run-id="${agent.runId}"]`);
    const status = row.querySelector(".run-entry-status");
    expect(status.textContent).toBe("Working");
    registry.update(agent.runId, context => { context.metadata.hold = { id: "a1b2c3d4e5f6", kind: "injection" }; });
    expect(status.textContent).toBe("Paused");
    expect(row.classList.contains("is-paused")).toBe(true);
    expect(row.getAttribute("aria-label")).toBe("Paused. Paused. Open run.");
    registry.update(agent.runId, context => { context.metadata.hold = { id: "0123456789ab", ask: "browser" }; });
    expect(status.textContent).toBe("Waiting for you");
    registry.update(agent.runId, context => { context.metadata.hold = null; });
    expect(status.textContent).toBe("Working");
    expect(row.classList.contains("is-paused")).toBe(false);
    // The word of the activity's head (UX audit E2): thinking, a command or
    // the answer being written is "Working", the reviewers' check "Reviewing".
    registry.update(agent.runId, context => {
      context.metadata.agentActivity = [{ version: 1, kind: "reasoning", id: "r", format: "summary", text: "Weighing it." }];
      context.consensus.streamText = "The answer begins";
    });
    expect(status.textContent).toBe("Working");
    registry.update(agent.runId, context => { context.metadata.agentReview = { mode: "audit", status: "running" }; });
    expect(status.textContent).toBe("Reviewing");
    registry.update(agent.runId, context => { context.metadata.agentReview = { status: "running" }; });
    expect(status.textContent).toBe("Checking");
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
    expect(document.querySelector(`[data-run-id="${runB.runId}"]`)?.textContent).toContain("Stopped");

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
