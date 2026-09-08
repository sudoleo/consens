import { describe, expect, it, vi } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

// The panel is a projection of the selected run. When nothing is selected --
// a saved bookmark was opened while a run keeps going -- it has to fall back
// to the controls instead of reading a run that is not there.
const BODY = `
  <div id="composerModeBar">
    <button id="composerAgentToggle"></button><span id="composerAgentState"></span>
    <p id="composerModeDescription"></p><span id="composerModelIcons"></span>
    <p id="composerComparisonStatus"></p>
    <button id="composerDeepToggle"></button><span id="composerDeepState"></span>
    <button id="composerAttachButton"></button>
  </div>
  <input id="agentModeMenuSwitch" type="checkbox"><input id="agentModeSwitch" type="checkbox">
  <input id="autoConsensusToggle" type="checkbox">
  <input id="deepSearchToggle" type="checkbox"><button id="attachUploadOption"></button>
  <div id="agentModePanel">
    <span id="agentModeTitle"></span>
    <span id="agentModeCount"></span>
    <span id="agentModeStatus"></span>
    <span id="agentModeTimer"></span>
    <div id="agentModeModels"></div>
  </div>
  <input type="checkbox" id="openaiCheck" checked>
  <select id="openaiModelSelect"><option value="gpt" data-model-label="GPT">GPT</option></select>
  <span id="openaiModelText">GPT</span>
  <div id="openaiResponse" class="response-box"><div class="collapsible-content"></div></div>
`;

function boot() {
  return loadScripts(["static/js/agent-mode.js"], {
    body: BODY,
    before(window) {
      window.App = {
        modelPrefs: [{
          key: "OpenAI",
          label: "OpenAI",
          checkId: "openaiCheck",
          selectId: "openaiModelSelect",
          textId: "openaiModelText",
          responseId: "openaiResponse"
        }],
        deepThinkModelLabels: {},
        getModelOptionLabel: option => option?.textContent || "",
        getSelectedModelCount: () => 1,
        initCustomModelPicker: vi.fn(),
        trackAppEvent: vi.fn()
      };
      window.localStorage.setItem("agentMode", "true");
    }
  });
}

describe("agent mode panel projection", () => {
  it("shows the starting toolbar, hides it in an agent chat and restores it for a new comparison", async () => {
    const { window, document, dom } = boot();
    const bar = document.getElementById('composerModeBar');
    document.body.classList.add('is-hero');
    await Promise.resolve();
    expect(bar.hidden).toBe(false);
    document.body.classList.remove('is-hero');
    await Promise.resolve();
    expect(bar.hidden).toBe(true);
    window.setAgentMode(false, {persist: true});
    expect(bar.hidden).toBe(false);
    window.setAgentMode(true, {persist: true});
    document.body.classList.add('is-hero');
    await Promise.resolve();
    expect(bar.hidden).toBe(false);
    dom.window.close();
  });

  it("routes toolbar actions through the original controls and respects a rejected deep toggle", () => {
    const { window, document, dom } = boot();
    const deep = document.getElementById('deepSearchToggle');
    const button = document.getElementById('composerDeepToggle');
    const upload = vi.fn();
    document.getElementById('attachUploadOption').addEventListener('click', upload);
    button.click();
    expect(deep.checked).toBe(true);
    expect(button.getAttribute('aria-checked')).toBe('true');
    deep.addEventListener('click', event => event.preventDefault());
    button.click();
    expect(deep.checked).toBe(true);
    expect(button.getAttribute('aria-checked')).toBe('true');
    document.getElementById('composerAttachButton').click();
    expect(upload).toHaveBeenCalledOnce();
    dom.window.close();
  });
  it("keeps the composer setting independent of a frozen run and synchronizes all switches", () => {
    const { window, document, dom } = boot();
    window.projectAgentModeRun({runId: 'direct', config: {agentMode: false}});
    const toggle = document.getElementById('composerAgentToggle');
    expect(toggle.getAttribute('aria-checked')).toBe('true');
    expect(document.getElementById('composerModeBar').hidden).toBe(true);
    expect(document.getElementById('composerModeDescription').textContent).toContain('Automatic consensus');
    toggle.click();
    expect(window.localStorage.getItem('agentMode')).toBe('false');
    expect(toggle.getAttribute('aria-checked')).toBe('false');
    expect(document.getElementById('composerModeBar').hidden).toBe(false);
    expect(document.getElementById('agentModeMenuSwitch').checked).toBe(false);
    expect(document.getElementById('autoConsensusToggle').checked).toBe(false);
    expect(document.getElementById('composerModeDescription').textContent).toContain('no consensus');
    document.getElementById('agentModeMenuSwitch').click();
    expect(toggle.getAttribute('aria-checked')).toBe('true');
    expect(document.getElementById('agentModeSwitch').checked).toBe(true);
    expect(document.getElementById('composerModeBar').hidden).toBe(true);
    dom.window.close();
  });

  it("updates selected model marks and clears stale direct-result summaries", () => {
    const {window, document, dom} = boot();
    window.App.answerReader = {directSummary: () => '1 of 2 ready · 1 unavailable'};
    window.updateAgentModeUI();
    expect(document.getElementById('composerComparisonStatus').textContent).toContain('Agent Mode was off');
    expect(document.querySelector('.composer-model-icon').getAttribute('aria-label')).toContain('GPT');
    document.getElementById('openaiCheck').checked = false;
    window.App.answerReader.directSummary = () => null;
    window.updateAgentModeUI();
    expect(document.getElementById('composerModelIcons').children.length).toBe(0);
    expect(document.getElementById('composerComparisonStatus').hidden).toBe(true);
    dom.window.close();
  });
  it("falls back to the controls when no run is selected", () => {
    const { window, document, dom } = boot();

    window.projectAgentModeRun({
      runId: "run-1",
      status: "running",
      phase: "answers",
      startedAt: Date.now(),
      config: { agentMode: true, providers: [{ provider: "OpenAI", modelLabel: "Frozen model" }] },
      modelResults: { OpenAI: { status: "streaming", streamText: "half" } }
    });
    expect(document.getElementById("agentModeModels").textContent).toContain("Frozen model");
    expect(document.body.classList.contains("agent-mode-running")).toBe(true);

    // Deselecting the run must not throw: everything after this call in
    // run-view's projection (the guided-run block, the send button) would
    // otherwise be skipped, and the bookmark restore that triggered it would
    // abort halfway through.
    expect(() => window.projectAgentModeRun(null)).not.toThrow();
    expect(document.getElementById("agentModeModels").textContent).not.toContain("Frozen model");
    expect(document.getElementById("agentModeModels").textContent).toContain("OpenAI");
    expect(document.body.classList.contains("agent-mode-running")).toBe(false);
    dom.window.close();
  });
});
