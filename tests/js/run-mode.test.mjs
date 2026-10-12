import { describe, expect, it, vi } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

// run-mode.js is the single source of truth for Compare / Consensus / Agent.
// The value is the account setting "run_mode" (user-settings.js, whose own
// tests cover storage, migration and sync).
function boot(storage = {}) {
  return loadScripts(["static/js/user-settings.js", "static/js/run-mode.js"], {
    before(window) {
      Object.entries(storage).forEach(([key, value]) => window.localStorage.setItem(key, value));
      window.App = { trackAppEvent: vi.fn() };
    }
  });
}

describe("run mode", () => {
  // An unchosen mode is not stored: a later change of the default reaches
  // everyone who never chose. Every browser starts once from Agent (the reset
  // of 2026-10-12 in user-settings.js); a choice after it stays.
  const RESET = {"consensio.settingsReset": "2026-10-12"};
  it.each([
    [{}, "agent", null],
    [{agentMode: "false", autoConsensus: "false"}, "agent", null],
    [{runMode: "compare"}, "agent", null],
    [{runMode: "compare", ...RESET}, "compare", "compare"],
    [{runMode: "bogus", ...RESET}, "agent", "bogus"],
  ])("reads %o as %s (stored: %s)", (storage, expected, stored) => {
    const {window, dom} = boot(storage);
    expect(window.App.runMode.preference()).toBe(expected);
    expect(window.localStorage.getItem("runMode")).toBe(stored);
    expect(window.localStorage.getItem("agentMode")).toBeNull();
    expect(window.localStorage.getItem("consensio.settingsReset")).toBe("2026-10-12");
    window.App.runMode.set("consensus");
    expect(window.App.runMode.preference()).toBe("consensus");
    expect(window.localStorage.getItem("runMode")).toBe("consensus");
    dom.window.close();
  });

  it("changes only to known modes, announces changes once and tracks the source", () => {
    const {window, dom} = boot({runMode: "consensus", "consensio.settingsReset": "2026-10-12"});
    const heard = vi.fn();
    window.addEventListener("consensio:run-mode-change", event => heard(event.detail));
    expect(window.App.runMode.set("nonsense")).toBe(false);
    expect(window.App.runMode.set("consensus")).toBe(false);
    expect(window.App.runMode.set("compare", {source: "composer"})).toBe(true);
    expect(heard).toHaveBeenCalledOnce();
    expect(heard).toHaveBeenCalledWith({mode: "compare", previous: "consensus"});
    expect(window.App.trackAppEvent).toHaveBeenCalledWith("app_run_mode_changed", {mode: "compare", previous: "consensus", source: "composer"});
    dom.window.close();
  });

  it("resolves the effective mode from the open chat and the account", () => {
    const {window, dom} = boot({runMode: "agent"});
    const state = {family: null, canUse: false, pending: false};
    window.App.agentChat = {modeState: () => state};
    const mode = window.App.runMode;
    // No access yet: Agent is kept as the choice but runs as Consensus.
    expect(mode.effective()).toBe("consensus");
    expect(mode.pipeline()).toBe(true);
    expect(mode.availability().agent.visible).toBe(false);
    state.canUse = true;
    expect(mode.effective()).toBe("agent");
    // An open Consensus chat keeps its family.
    state.family = "consensus";
    expect(mode.effective()).toBe("consensus");
    expect(mode.availability().agent).toEqual({visible: true, enabled: false, reason: "Available in a new chat"});
    mode.set("compare");
    expect(mode.effective()).toBe("compare");
    expect(mode.pipeline()).toBe(false);
    // An open Agent chat stays Agent whatever the choice for new chats is.
    state.family = "agent";
    expect(mode.effective()).toBe("agent");
    expect(mode.availability().compare.enabled).toBe(false);
    expect(mode.availability().consensus.reason).toBe("Available in a new chat");
    dom.window.close();
  });

  it("follows a change made in another tab or arriving from the account", () => {
    const {window, dom} = boot({runMode: "consensus", "consensio.settingsReset": "2026-10-12"});
    const heard = vi.fn();
    window.addEventListener("consensio:run-mode-change", event => heard(event.detail));
    const tab = (key, newValue) => {
      if (newValue === null) window.localStorage.removeItem(key);
      else window.localStorage.setItem(key, newValue);
      window.dispatchEvent(new window.StorageEvent("storage", {key, newValue, storageArea: window.localStorage}));
    };
    tab("runMode", "compare");
    tab("theme", "dark");
    expect(heard).toHaveBeenCalledOnce();
    expect(heard).toHaveBeenLastCalledWith({mode: "compare", previous: "consensus"});
    // Signing out drops the account's choice: back to the default.
    tab("runMode", null);
    expect(heard).toHaveBeenLastCalledWith({mode: "agent", previous: "compare"});
    expect(heard).toHaveBeenCalledTimes(2);
    dom.window.close();
  });
});
