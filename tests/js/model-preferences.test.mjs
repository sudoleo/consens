/**
 * model-picker.js with account settings: what a model change saves, the demo's
 * preset that is only shown, and values arriving from the account.
 */

import { afterEach, describe, expect, it, vi } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

const FAMILIES = [
  { key: "OpenAI", provider: "openai", dom: "openai", checked: true },
  { key: "Mistral", provider: "mistral", dom: "mistral", checked: true },
  { key: "Anthropic", provider: "anthropic", dom: "claude", checked: true },
  { key: "Grok", provider: "grok", dom: "grok", checked: false },
];

// Each family offers a Daily model (-a), a Balanced model (-b) and a Pro model
// that is locked for this account.
const BODY = FAMILIES.map(family => `
  <label for="select${family.key}"><input type="checkbox" id="select${family.key}"${family.checked ? " checked" : ""}></label>
  <div class="response-box" id="${family.dom}Response"><div class="collapsible-content"></div></div>
  <span id="${family.dom}ModelText"></span>
  <select id="${family.dom}ModelSelect">
    <option value="${family.dom}-a">A</option>
    <option value="${family.dom}-b">B</option>
    <option value="${family.dom}-pro" disabled class="premium-option">Pro</option>
  </select>
`).join("") + `
  <select id="consensusModelDropdown">
    <option value="Gemini">Gemini</option>
    <option value="OpenAI">OpenAI</option>
  </select>`;

const PRESETS = [
  { id: "fast", label: "Daily", consensus_model: "Gemini",
    models: { openai: "openai-a", mistral: "mistral-a", anthropic: "claude-a" } },
  { id: "balanced", label: "Balanced", consensus_model: "OpenAI",
    models: { openai: "openai-b", mistral: "mistral-b", grok: "grok-b" } },
];

const opened = [];
afterEach(() => opened.splice(0).forEach(dom => dom.window.close()));

function boot(storage = {}) {
  const harness = loadScripts(["static/js/user-settings.js", "static/js/model-picker.js"], {
    body: BODY,
    before(window) {
      window.localStorage.setItem("consensio.settingsReset", "2026-10-12");
      Object.entries(storage).forEach(([key, value]) => window.localStorage.setItem(key, value));
      window.CONSENSUS_PRESETS = PRESETS;
      window.DEFAULT_CONSENSUS_PRESET = "fast";
      window.App = {
        maxRunFamilies: 3,
        modelPrefs: FAMILIES.map(family => ({
          key: family.key,
          provider: family.provider,
          label: family.key,
          checkId: `select${family.key}`,
          selectId: `${family.dom}ModelSelect`,
          responseId: `${family.dom}Response`,
          textId: `${family.dom}ModelText`,
        })),
        getModelOptionLabel: option => option?.textContent || "",
        getSelectedModelCount: () => 0,
        trackAppEvent: vi.fn(),
        showPopup: vi.fn(),
        updateReasoningUI: vi.fn(),
        attachments: { refreshCompatibility: vi.fn() },
      };
      window.updateAgentModeUI = vi.fn();
      window.updateConsensusButtonAvailability = vi.fn();
    },
  });
  opened.push(harness.dom);
  const { window } = harness;
  window.restoreModelSelections();
  return { window, settings: window.App.userSettings, local: window.localStorage };
}

function lineup(window) {
  return Object.fromEntries(FAMILIES.map(family => [family.key, {
    checked: window.document.getElementById(`select${family.key}`).checked,
    model: window.document.getElementById(`${family.dom}ModelSelect`).value,
  }]));
}

function pref(window, key) {
  return window.App.modelPrefs.find(entry => entry.key === key);
}

describe("the demo's preset", () => {
  it("shows Balanced without making it the visitor's choice", () => {
    const { window, settings } = boot();
    expect(lineup(window).OpenAI.model).toBe("openai-a");
    expect(window.App.previewConsensusPreset("balanced")).toBe(true);
    expect(lineup(window)).toEqual({
      OpenAI: { checked: true, model: "openai-b" },
      Mistral: { checked: true, model: "mistral-b" },
      Anthropic: { checked: false, model: "claude-a" },
      Grok: { checked: true, model: "grok-b" },
    });
    expect(window.document.getElementById("consensusModelDropdown").value).toBe("OpenAI");
    expect(settings.get("consensus_preset")).toBeUndefined();
    expect(settings.get("compare_models")).toBeUndefined();
    expect(window.App.trackAppEvent).not.toHaveBeenCalled();
    // It stays on screen when the tier refresh restores the selection ...
    window.restoreModelSelections();
    expect(lineup(window).Grok).toEqual({ checked: true, model: "grok-b" });
  });

  it("gives way to the next choice of the user's own", () => {
    const { window, settings } = boot();
    window.App.previewConsensusPreset("balanced");
    window.App.selectConsensusPreset("fast");
    expect(settings.get("consensus_preset")).toBe("fast");
    window.restoreModelSelections();
    expect(lineup(window).Grok.checked).toBe(false);
  });
});

describe("a model change", () => {
  it("leaving a preset keeps the whole lineup on screen as the user's own", () => {
    const { window, settings } = boot();
    window.document.getElementById("mistralModelSelect").value = "mistral-b";
    window.App.markConsensusPresetCustom({ family: pref(window, "Mistral") });
    expect(settings.get("consensus_preset")).toBe("custom");
    expect(settings.get("compare_models")).toEqual({
      OpenAI: { model: "openai-a" }, Mistral: { model: "mistral-b" },
      Anthropic: { model: "claude-a" }, Grok: { model: "grok-a" },
    });
    expect(settings.get("consensus_model")).toBe("Gemini");
  });

  it("within Custom saves the changed family and keeps a stored model that is not offered right now", () => {
    // A Pro model stored on another device, shown as a fallback until the
    // account's tier is known.
    const { window, settings } = boot({
      pref_consensus_preset: "custom",
      pref_select_OpenAI: "openai-pro",
      pref_select_Mistral: "mistral-b",
      pref_select_consensus: "OpenAI",
    });
    expect(lineup(window).OpenAI.model).toBe("openai-a");
    window.document.getElementById("claudeModelSelect").value = "claude-b";
    window.App.markConsensusPresetCustom({ family: pref(window, "Anthropic") });
    expect(settings.get("compare_models")).toEqual({
      OpenAI: { model: "openai-pro" }, Mistral: { model: "mistral-b" },
      Anthropic: { model: "claude-b" }, Grok: { model: "grok-a" },
    });
    expect(settings.get("consensus_model")).toBe("OpenAI");
    window.document.getElementById("consensusModelDropdown").value = "Gemini";
    window.App.markConsensusPresetCustom({ engine: true });
    expect(settings.get("consensus_model")).toBe("Gemini");
  });
});

describe("values from the account", () => {
  it("applies them and returns unsaved families to the page defaults", () => {
    const { window, local } = boot({
      pref_consensus_preset: "custom",
      pref_check_Grok: "true", pref_check_Anthropic: "false", pref_select_OpenAI: "openai-b",
    });
    expect(lineup(window).Grok.checked).toBe(true);
    // Another tab (or the account) now holds a different choice.
    ["pref_check_Grok", "pref_check_Anthropic"].forEach(key => local.removeItem(key));
    local.setItem("pref_select_Mistral", "mistral-b");
    window.dispatchEvent(new window.StorageEvent("storage", { key: "pref_select_Mistral", storageArea: local }));
    expect(lineup(window)).toEqual({
      OpenAI: { checked: true, model: "openai-b" },
      Mistral: { checked: true, model: "mistral-b" },
      Anthropic: { checked: true, model: "claude-a" },
      Grok: { checked: false, model: "grok-a" },
    });
    expect(window.App.updateReasoningUI).toHaveBeenCalled();
    expect(window.App.attachments.refreshCompatibility).toHaveBeenCalled();
    // Applying is not a choice: nothing is saved or tracked.
    expect(window.App.trackAppEvent).not.toHaveBeenCalled();
    expect(local.getItem("pref_check_Anthropic")).toBeNull();
  });
});
