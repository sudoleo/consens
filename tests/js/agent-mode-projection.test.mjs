import { describe, expect, it, vi } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

// The run view is a projection of the selected run. When nothing is selected
// -- a saved bookmark was opened while a run keeps going -- it has to fall
// back to the controls instead of reading a run that is not there.
const BODY = `
  <button id="attachTrigger"></button>
  <div id="runModeControl" class="attach-menu-modes"><select id="runModeSelect" hidden>
    <option value="compare">Compare</option></select></div>
  <select id="runModeSetting"><option value="agent">Agent · Beta</option><option value="compare">Compare</option></select>
  <div id="composerModeBar">
    <p id="composerModeDescription"></p><span id="composerModelIcons"></span>
    <p id="composerComparisonStatus"></p>
    <button id="composerReasoningToggle"></button><span id="composerReasoningState"></span>
    <button id="composerAttachButton"></button>
  </div>
  <label><input id="reasoningToggle" type="checkbox"></label><button id="attachUploadOption"></button>
  <button id="agentReasoningMenuOption" hidden></button><span id="agentReasoningMenuState"></span>
  <button id="agentComparisonMenuOption" hidden></button>
  <input type="checkbox" id="openaiCheck" checked>
  <select id="openaiModelSelect"><option value="gpt" data-model-label="GPT">GPT</option></select>
  <span id="openaiModelText">GPT</span>
  <div id="openaiResponse" class="response-box"><div class="collapsible-content"></div></div>
`;

// An account with Agent access in a new chat whose composer is not Agent's
// (isSelected false): the tests read the shared controls.
function boot({ mode = "agent" } = {}) {
  return loadScripts(["static/js/user-settings.js", "static/js/run-mode.js", "static/js/agent-mode.js"], {
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
        getModelOptionLabel: option => option?.textContent || "",
        getSelectedModelCount: () => 1,
        initCustomModelPicker: vi.fn(),
        trackAppEvent: vi.fn()
      };
      window.App.agentChat = { isSelected: () => false, modeState: () => ({ family: null, canUse: true, pending: false }) };
      window.localStorage.setItem("runMode", mode);
      window.localStorage.setItem("consensio.settingsReset", "2026-10-12");
    }
  });
}

describe("agent mode panel projection", () => {
  it('moves Beta tools into the plus menu after chat start', async () => {
    const {window, document, dom} = boot({mode: "compare"});
    window.App.agentChat = {isSelected: () => true, modeState: () => ({family: 'agent', canUse: true, pending: false})};
    window.App.openModelPicker = vi.fn();
    document.body.insertAdjacentHTML('beforeend', '<select id="agentModelDropdown"></select><select id="agentReasoningEffort" data-available="true"><option value="high">High</option></select>');
    document.body.classList.remove('is-hero');
    window.App.renderComposerMode();
    expect(document.getElementById('composerModeBar').hidden).toBe(true);
    // An open Agent chat shows Agent; Compare needs a new chat.
    const select = document.getElementById('runModeSelect');
    expect(select.value).toBe('agent');
    expect(select.querySelector('[value="compare"]').disabled).toBe(true);
    expect(select.querySelector('[value="compare"]').dataset.description).toBe('Available in a new chat');
    expect(document.getElementById('runModeControl').hidden).toBe(true);
    expect(document.getElementById('agentReasoningMenuOption').hidden).toBe(false);
    expect(document.getElementById('reasoningToggle').closest('label').hidden).toBe(true);
    select.value = 'compare';
    select.dispatchEvent(new window.Event('change'));
    expect(window.localStorage.getItem('runMode')).toBe('compare');
    expect(select.value).toBe('agent');
    // An open Agent chat names its fixed mode on the (+) trigger only.
    expect(document.getElementById('attachTrigger').title).toBe('Chat options');
    expect(document.getElementById('composerAttachButton').disabled).toBe(false);
    expect(document.getElementById('composerReasoningState').textContent).toBe('High');
    document.getElementById('composerReasoningToggle').click();
    // The control that asked travels along (a guest's login dialog gives the focus back to it).
    expect(window.App.openModelPicker).toHaveBeenCalledWith(document.getElementById('agentModelDropdown'),
      {secondary: true, trigger: document.getElementById('composerReasoningToggle')});
    window.App.openModelPicker.mockClear();
    document.getElementById('agentReasoningMenuOption').click();
    expect(window.App.openModelPicker).toHaveBeenCalledWith(document.getElementById('agentModelDropdown'),
      {secondary: true, trigger: document.getElementById('attachTrigger')});
    expect(document.getElementById('agentReasoningMenuState').textContent).toBe('High');
    document.body.classList.add('is-hero');
    await vi.waitFor(() => expect(document.getElementById('composerModeBar').hidden).toBe(false));
    expect(document.getElementById('reasoningToggle').checked).toBe(false);
    window.App.agentChat.isSelected = () => false;
    window.App.agentChat.modeState = () => ({family: null, canUse: true, pending: false});
    window.App.renderComposerMode();
    expect(document.getElementById('runModeSelect').value).toBe('compare');
    expect(document.getElementById('runModeControl').hidden).toBe(false);
    // The mode is the first group of the (+) menu: two rows, the current one pressed.
    const rows = [...document.querySelectorAll('#runModeControl .attach-menu-mode')];
    expect(rows.map(row => row.dataset.value)).toEqual(['agent', 'compare']);
    expect(rows.find(row => row.dataset.value === 'compare').getAttribute('aria-pressed')).toBe('true');
    expect(rows.find(row => row.dataset.value === 'agent').textContent).toContain('Beta');
    expect(document.getElementById('attachTrigger').title).toBe('Mode, files and options');
    rows.find(row => row.dataset.value === 'agent').click();
    expect(window.localStorage.getItem('runMode')).toBe('agent');
    expect(rows.find(row => row.dataset.value === 'agent').getAttribute('aria-pressed')).toBe('true');
    window.App.runMode.set('compare');
    expect(document.getElementById('composerAttachButton').disabled).toBe(false);
    expect(document.getElementById('agentReasoningMenuOption').hidden).toBe(true);
    expect(document.getElementById('reasoningToggle').closest('label').hidden).toBe(false);
    dom.window.close();
  });

  it("uses one toolbar rule for every mode: tools on the start screen, a docked status line in a chat", async () => {
    const { window, document, dom } = boot();
    const sync = vi.fn();
    window.App.attachments = { syncComposerPlacement: sync };
    const bar = document.getElementById('composerModeBar');
    document.body.classList.add('is-hero');
    await Promise.resolve();
    expect(bar.hidden).toBe(false);
    expect(bar.dataset.docked).toBe('false');
    for (const mode of ['compare', 'agent']) {
      window.App.runMode.set(mode);
      expect(bar.hidden).toBe(false);
    }
    document.body.classList.remove('is-hero');
    await Promise.resolve();
    for (const mode of ['compare', 'agent']) {
      window.App.runMode.set(mode);
      expect(bar.hidden).toBe(true);
    }
    // A comparison on screen keeps its status line, docked without tools;
    // attachments follow the bar on every render.
    window.App.answerReader = {directSummary: () => '2 of 2 ready'};
    sync.mockClear();
    window.updateAgentModeUI();
    expect(bar.hidden).toBe(false);
    expect(bar.dataset.docked).toBe('true');
    expect(sync).toHaveBeenCalled();
    dom.window.close();
  });

  it("shows the starting toolbar, hides it in a chat in every mode and restores it on the start screen", async () => {
    const { window, document, dom } = boot();
    const bar = document.getElementById('composerModeBar');
    document.body.classList.add('is-hero');
    await Promise.resolve();
    expect(bar.hidden).toBe(false);
    document.body.classList.remove('is-hero');
    await Promise.resolve();
    expect(bar.hidden).toBe(true);
    window.App.runMode.set('compare');
    expect(bar.hidden).toBe(true);
    window.App.runMode.set('agent');
    document.body.classList.add('is-hero');
    await Promise.resolve();
    expect(bar.hidden).toBe(false);
    dom.window.close();
  });

  it("routes toolbar actions through the original controls and respects a rejected reasoning toggle", () => {
    const { window, document, dom } = boot();
    const deep = document.getElementById('reasoningToggle');
    const button = document.getElementById('composerReasoningToggle');
    const upload = vi.fn();
    document.getElementById('attachUploadOption').addEventListener('click', upload);
    button.click();
    expect(deep.checked).toBe(true);
    expect(button.getAttribute('aria-checked')).toBe('true');
    expect(button.title).toBe('Reasoning on · Models think longer before they answer');
    expect(button.title).not.toContain('Pro');
    expect(document.getElementById('composerReasoningState').textContent).toBe('On');
    deep.addEventListener('click', event => event.preventDefault());
    button.click();
    expect(deep.checked).toBe(true);
    expect(button.getAttribute('aria-checked')).toBe('true');
    document.getElementById('composerAttachButton').click();
    expect(upload).toHaveBeenCalledOnce();
    dom.window.close();
  });
  it("keeps the mode choice independent of a frozen run and synchronizes selector and settings", () => {
    const { window, document, dom } = boot();
    window.projectAgentModeRun({runId: 'direct', config: {agentMode: false}});
    const select = document.getElementById('runModeSelect');
    const setting = document.getElementById('runModeSetting');
    expect(select.value).toBe('agent');
    expect([...select.options].map(option => option.value)).toEqual(['compare', 'agent']);
    expect([...setting.options].map(option => option.value)).toEqual(['agent', 'compare']);
    expect(document.getElementById('composerModeBar').hidden).toBe(true);
    expect(document.getElementById('composerModeDescription').textContent).toContain('research, files and tools');
    select.value = 'compare';
    select.dispatchEvent(new window.Event('change'));
    expect(window.localStorage.getItem('runMode')).toBe('compare');
    expect(window.App.trackAppEvent).toHaveBeenCalledWith('app_run_mode_changed', {mode: 'compare', previous: 'agent', source: 'composer'});
    expect(setting.value).toBe('compare');
    expect(document.getElementById('composerModeBar').hidden).toBe(true);
    expect(document.getElementById('composerModeDescription').textContent).toBe('Answers side by side.');
    setting.value = 'agent';
    setting.dispatchEvent(new window.Event('change'));
    expect(select.value).toBe('agent');
    expect(document.getElementById('composerModeBar').hidden).toBe(true);
    dom.window.close();
  });

  it("updates selected model marks and clears stale direct-result summaries", () => {
    const {window, document, dom} = boot();
    window.App.answerReader = {directSummary: () => '1 of 2 ready · 1 unavailable'};
    window.updateAgentModeUI();
    expect(document.getElementById('composerComparisonStatus').textContent).toBe('1 of 2 ready · 1 unavailable.');
    expect(document.querySelector('.composer-model-icon').getAttribute('aria-label')).toContain('GPT');
    document.getElementById('openaiCheck').checked = false;
    window.App.answerReader.directSummary = () => null;
    window.updateAgentModeUI();
    expect(document.getElementById('composerModelIcons').children.length).toBe(0);
    expect(document.getElementById('composerComparisonStatus').hidden).toBe(true);
    dom.window.close();
  });
  // Audit (Max, 2026-10-27): the reviewers say what they do next to their
  // marks under the field; in a chat, where the bar steps aside, their marks
  // stand before the chip, which names the chat model (model-picker.js).
  it("gives the reviewers their own control in audit mode", () => {
    const { window, document, dom } = loadScripts(["static/js/app-text.js", "static/js/user-settings.js",
      "static/js/run-mode.js", "static/js/agent-mode.js"], {
      body: BODY + `<button id="composerModelPicker" aria-label="Configure models for your next question" title="Configure models">
        <span id="composerModelLabel" hidden></span></button>
        <button id="composerReviewers" hidden><span id="composerReviewerIcons"></span></button>`,
      before(window) {
        window.App = { modelPrefs: [{ key: "OpenAI", label: "OpenAI", provider: "openai", checkId: "openaiCheck",
          selectId: "openaiModelSelect", textId: "openaiModelText", responseId: "openaiResponse" }],
          getModelOptionLabel: option => option?.textContent || "", getSelectedModelCount: () => 1,
          initCustomModelPicker: vi.fn(), trackAppEvent: vi.fn() };
        window.localStorage.setItem("runMode", "agent");
        window.localStorage.setItem("consensio.settingsReset", "2026-10-12");
      }
    });
    let audit = false;
    window.App.agentPreferences = { auditing: () => audit };
    window.App.agentChat = { isSelected: () => true, looksAgent: () => true,
      modeState: () => ({ family: "agent", canUse: true, pending: false }) };
    const picker = document.getElementById("composerModelPicker");
    const label = document.getElementById("composerModelLabel");
    const reviewers = document.getElementById("composerReviewers");
    document.body.classList.add("is-hero");
    window.App.renderComposerMode();
    expect(label.hidden).toBe(true);
    expect(reviewers.hidden).toBe(true);
    expect(picker.getAttribute("aria-label")).toBe("Configure models for your next question");

    audit = true;
    window.App.renderComposerMode();
    expect(label.hidden).toBe(false);
    expect(label.textContent).toBe("1 AI cross-checks");
    expect(picker.getAttribute("aria-label")).toBe("1 AI cross-checks");
    expect(picker.title).toBe("Choose the models that review the agent's work");
    // The start screen has the bar: no second control in the field.
    expect(reviewers.hidden).toBe(true);

    document.body.classList.remove("is-hero");
    window.App.renderComposerMode();
    expect(document.getElementById("composerModeBar").hidden).toBe(true);
    expect(reviewers.hidden).toBe(false);
    expect(reviewers.getAttribute("aria-label")).toBe("1 AI cross-checks");
    const [mark] = reviewers.querySelectorAll(".composer-model-icon");
    expect(mark.dataset.provider).toBe("openai");
    // Named once, by the button.
    expect(mark.getAttribute("aria-hidden")).toBe("true");
    expect(mark.hasAttribute("role")).toBe(false);

    audit = false;
    window.App.renderComposerMode();
    expect(reviewers.hidden).toBe(true);
    expect(label.hidden).toBe(true);
    expect(picker.title).toBe("Configure models");
    dom.window.close();
  });

  it("previews the chosen models and marks the view by the run on screen", () => {
    const { window, document, dom } = boot();
    const syncPreview = vi.fn();
    window.App.answerReader = { syncPreview };
    const previewedModels = () => syncPreview.mock.lastCall[1].map(model => model.model).join(" ");

    // A Compare run on screen: its answers side by side, not a thread.
    window.projectAgentModeRun({
      runId: "run-1",
      status: "running",
      phase: "answers",
      startedAt: Date.now(),
      config: { agentMode: false, providers: [{ provider: "OpenAI", modelLabel: "Frozen model" }] },
      modelResults: { OpenAI: { status: "streaming", streamText: "half" } }
    });
    expect(previewedModels()).toContain("GPT");
    expect(document.body.classList.contains("agent-mode-enabled")).toBe(false);
    expect(document.body.classList.contains("agent-mode-running")).toBe(false);

    // Deselecting the run must not throw: everything after this call in
    // run-view's projection (the send button) would otherwise be skipped,
    // and the bookmark restore that triggered it would abort halfway.
    expect(() => window.projectAgentModeRun(null)).not.toThrow();
    expect(previewedModels()).toContain("GPT");
    // Nothing on screen: the view follows the choice, here Agent.
    expect(document.body.classList.contains("agent-mode-enabled")).toBe(true);
    expect(window).not.toHaveProperty("isAgentModeRunning");
    dom.window.close();
  });

  it("shows Agent's start screen, not Compare's grid, while Agent access loads", () => {
    const { window, document, dom } = boot();
    const syncPreview = vi.fn();
    window.App.answerReader = { syncPreview };
    const state = { family: null, canUse: false, pending: true };
    window.App.agentChat = { isSelected: () => false, modeState: () => state };
    window.updateAgentModeUI();
    // The next message would run as Compare until access arrives, but the
    // view waits for Agent.
    expect(window.App.runMode.effective()).toBe("compare");
    expect(syncPreview.mock.lastCall[0]).toBe(true);
    expect(document.body.classList.contains("agent-mode-enabled")).toBe(true);
    // Before that, while the sign-in itself is unknown (neither account nor
    // guest): Agent's start screen too, no grid for that second (2026-10-26).
    state.pending = false;
    window.__consensioAuthState = { known: false, uid: null, generation: 0 };
    window.updateAgentModeUI();
    expect(syncPreview.mock.lastCall[0]).toBe(true);
    // A refusal settles the account in Compare.
    window.__consensioAuthState = { known: true, uid: "u1", generation: 1 };
    window.updateAgentModeUI();
    expect(syncPreview.mock.lastCall[0]).toBe(false);
    expect(document.body.classList.contains("agent-mode-enabled")).toBe(false);
    dom.window.close();
  });

  it("keeps a saved Consensus answer's answers behind its footer whatever the next mode is", () => {
    // An open saved chat runs its next message as Compare (run-mode.js);
    // the answer on screen still reads as a thread, not a side-by-side grid.
    const { window, document, dom } = boot({ mode: "compare" });
    document.body.insertAdjacentHTML("beforeend", '<div id="consensusOutput" class="consensus-output is-visible"></div>');
    window.updateAgentModeUI();
    expect(document.body.classList.contains("agent-mode-enabled")).toBe(true);
    // A saved direct comparison is a grid, and a cleared view follows the mode.
    document.body.classList.add("direct-comparison-active");
    window.updateAgentModeUI();
    expect(document.body.classList.contains("agent-mode-enabled")).toBe(false);
    document.body.classList.remove("direct-comparison-active");
    document.getElementById("consensusOutput").classList.remove("is-visible");
    window.updateAgentModeUI();
    expect(document.body.classList.contains("agent-mode-enabled")).toBe(false);
    dom.window.close();
  });

  it("keeps no 1 Hz timer running for the retired model panel", () => {
    vi.useFakeTimers();
    try {
      const { window, dom } = boot();
      const setInterval = vi.spyOn(window, "setInterval");
      window.setAgentModeStatus("running");
      window.projectAgentModeRun({
        runId: "run-2",
        status: "running",
        startedAt: Date.now(),
        config: { agentMode: false, providers: [{ provider: "OpenAI", modelLabel: "GPT" }] },
        modelResults: {}
      });
      expect(setInterval).not.toHaveBeenCalled();
      window.setAgentModeStatus("complete");
      expect(setInterval).not.toHaveBeenCalled();
      dom.window.close();
    } finally {
      vi.useRealTimers();
    }
  });
});
