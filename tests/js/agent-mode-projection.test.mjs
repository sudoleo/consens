import { describe, expect, it, vi } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

// The panel is a projection of the selected run. When nothing is selected --
// a saved bookmark was opened while a run keeps going -- it has to fall back
// to the controls instead of reading a run that is not there.
const BODY = `
  <button id="attachTrigger"></button>
  <div id="runModeControl" class="attach-menu-modes"><select id="runModeSelect" hidden>
    <option value="compare">Compare</option><option value="consensus">Consensus</option></select></div>
  <select id="runModeSetting"><option value="compare">Compare</option><option value="consensus">Consensus</option></select>
  <div id="composerModeBar">
    <p id="composerModeDescription"></p><span id="composerModelIcons"></span>
    <p id="composerComparisonStatus"></p>
    <button id="composerReasoningToggle"></button><span id="composerReasoningState"></span>
    <button id="composerAttachButton"></button>
  </div>
  <label><input id="sourceCheckSwitch" type="checkbox"></label>
  <label><input id="reasoningToggle" type="checkbox"></label><button id="attachUploadOption"></button>
  <button id="agentReasoningMenuOption" hidden></button><span id="agentReasoningMenuState"></span>
  <button id="agentComparisonMenuOption" hidden></button>
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

function boot({ mode = "consensus", checkSources = true } = {}) {
  return loadScripts(["static/js/run-mode.js", "static/js/agent-mode.js"], {
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
      window.localStorage.setItem("runMode", mode);
      window.localStorage.setItem("runModeDefault", "agent-2026-10-02");
      window.localStorage.setItem("checkSources", String(checkSources));
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
    // An open Agent chat shows Agent; Compare/Consensus need a new chat.
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
    expect(window.App.isSourceCheckEnabled()).toBe(true);
    // An open Agent chat names its fixed mode on the (+) trigger only.
    expect(document.getElementById('attachTrigger').title).toBe('Chat options');
    expect(document.getElementById('composerAttachButton').disabled).toBe(false);
    expect(document.getElementById('composerReasoningState').textContent).toBe('High');
    document.getElementById('composerReasoningToggle').click();
    expect(window.App.openModelPicker).toHaveBeenCalledWith(document.getElementById('agentModelDropdown'), {secondary: true});
    window.App.openModelPicker.mockClear();
    document.getElementById('agentReasoningMenuOption').click();
    expect(window.App.openModelPicker).toHaveBeenCalledWith(document.getElementById('agentModelDropdown'), {secondary: true});
    expect(document.getElementById('agentReasoningMenuState').textContent).toBe('High');
    document.body.classList.add('is-hero');
    await vi.waitFor(() => expect(document.getElementById('composerModeBar').hidden).toBe(false));
    expect(document.getElementById('reasoningToggle').checked).toBe(false);
    window.App.agentChat.isSelected = () => false;
    window.App.agentChat.modeState = () => ({family: null, canUse: true, pending: false});
    window.App.renderComposerMode();
    expect(document.getElementById('runModeSelect').value).toBe('compare');
    expect(document.getElementById('runModeControl').hidden).toBe(false);
    // The mode is the first group of the (+) menu: three rows, the current one pressed.
    const rows = [...document.querySelectorAll('#runModeControl .attach-menu-mode')];
    expect(rows.map(row => row.dataset.value)).toEqual(['agent', 'consensus', 'compare']);
    expect(rows.find(row => row.dataset.value === 'compare').getAttribute('aria-pressed')).toBe('true');
    expect(rows.find(row => row.dataset.value === 'agent').textContent).toContain('Beta');
    expect(document.getElementById('attachTrigger').title).toBe('Mode, files and options');
    rows.find(row => row.dataset.value === 'consensus').click();
    expect(window.localStorage.getItem('runMode')).toBe('consensus');
    expect(rows.find(row => row.dataset.value === 'consensus').getAttribute('aria-pressed')).toBe('true');
    window.App.runMode.set('compare');
    expect(document.getElementById('composerAttachButton').disabled).toBe(false);
    // Compare has nothing to check: the setting is locked off.
    expect(document.getElementById('sourceCheckSwitch').disabled).toBe(true);
    expect(document.getElementById('agentReasoningMenuOption').hidden).toBe(true);
    expect(document.getElementById('reasoningToggle').closest('label').hidden).toBe(false);
    dom.window.close();
  });

  it("keeps Check contradictions as one setting that persists and is locked in Compare", () => {
    const { window, document, dom } = boot();
    window.updateAgentModeUI();
    const setting = document.getElementById('sourceCheckSwitch');
    expect(window.App.isSourceCheckEnabled()).toBe(true);
    expect(setting.checked).toBe(true);
    // No switch in the composer bar or the (+) menu any more.
    expect(document.getElementById('composerSourcesToggle')).toBeNull();
    expect(document.getElementById('sourceCheckMenuSwitch')).toBeNull();
    setting.click();
    expect(window.App.isSourceCheckEnabled()).toBe(false);
    expect(window.localStorage.getItem('checkSources')).toBe('false');
    window.App.runMode.set('compare');
    window.projectAgentModeRun({runId: 'old', config: {agentMode: false, checkSources: true}});
    expect(setting.disabled).toBe(true);
    expect(setting.checked).toBe(false);
    window.App.runMode.set('consensus');
    expect(setting.disabled).toBe(false);
    expect(window.App.isSourceCheckEnabled()).toBe(false);
    setting.click();
    expect(window.localStorage.getItem('checkSources')).toBe('true');
    expect(window.App.isSourceCheckEnabled()).toBe(true);
    dom.window.close();
  });

  it.each([true, false])("gates the saved source preference %s on reload without changing it", checkSources => {
    const { window, document, dom } = boot({ mode: "compare", checkSources });
    window.updateAgentModeUI();
    expect(window.App.isSourceCheckEnabled()).toBe(false);
    const setting = document.getElementById('sourceCheckSwitch');
    expect(setting.checked).toBe(false);
    expect(setting.disabled).toBe(true);
    setting.checked = true;
    setting.dispatchEvent(new window.Event('change'));
    expect(setting.checked).toBe(false);
    expect(window.localStorage.getItem('checkSources')).toBe(String(checkSources));
    window.App.runMode.set('consensus');
    expect(window.App.isSourceCheckEnabled()).toBe(checkSources);
    window.App.runMode.set('compare');
    expect(window.App.isSourceCheckEnabled()).toBe(false);
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
    for (const mode of ['compare', 'consensus']) {
      window.App.runMode.set(mode);
      expect(bar.hidden).toBe(false);
    }
    document.body.classList.remove('is-hero');
    await Promise.resolve();
    for (const mode of ['compare', 'consensus']) {
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
    window.App.runMode.set('consensus');
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
    expect(select.value).toBe('consensus');
    expect(document.getElementById('composerModeBar').hidden).toBe(true);
    expect(document.getElementById('composerModeDescription').textContent).toContain('differences and checks');
    select.value = 'compare';
    select.dispatchEvent(new window.Event('change'));
    expect(window.localStorage.getItem('runMode')).toBe('compare');
    expect(window.App.trackAppEvent).toHaveBeenCalledWith('app_run_mode_changed', {mode: 'compare', previous: 'consensus', source: 'composer'});
    expect(setting.value).toBe('compare');
    expect(document.getElementById('composerModeBar').hidden).toBe(true);
    expect(document.getElementById('composerModeDescription').textContent).toContain('no consensus');
    setting.value = 'consensus';
    setting.dispatchEvent(new window.Event('change'));
    expect(select.value).toBe('consensus');
    expect(document.getElementById('composerModeBar').hidden).toBe(true);
    dom.window.close();
  });

  it("updates selected model marks and clears stale direct-result summaries", () => {
    const {window, document, dom} = boot();
    window.App.answerReader = {directSummary: () => '1 of 2 ready · 1 unavailable'};
    window.updateAgentModeUI();
    expect(document.getElementById('composerComparisonStatus').textContent).toBe('Shown: Compare result · 1 of 2 ready · 1 unavailable.');
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
