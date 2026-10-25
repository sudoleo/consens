import { describe, expect, it, vi } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

// run-mode.js is the single source of truth for Agent / Compare (Consensus
// left the browser on 2026-10-25). The value is the account setting
// "run_mode" (user-settings.js, whose own tests cover storage, migration and
// sync).
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
    // A choice of the retired Consensus mode reads as unchosen.
    [{runMode: "consensus", ...RESET}, "agent", "consensus"],
  ])("reads %o as %s (stored: %s)", (storage, expected, stored) => {
    const {window, dom} = boot(storage);
    expect(window.App.runMode.preference()).toBe(expected);
    expect(window.localStorage.getItem("runMode")).toBe(stored);
    expect(window.localStorage.getItem("agentMode")).toBeNull();
    expect(window.localStorage.getItem("consensio.settingsReset")).toBe("2026-10-12");
    window.App.runMode.set("compare");
    expect(window.App.runMode.preference()).toBe("compare");
    expect(window.localStorage.getItem("runMode")).toBe("compare");
    dom.window.close();
  });

  it("changes only to known modes, announces changes once and tracks the source", () => {
    const {window, dom} = boot({runMode: "compare", "consensio.settingsReset": "2026-10-12"});
    const heard = vi.fn();
    window.addEventListener("consensio:run-mode-change", event => heard(event.detail));
    expect(window.App.runMode.MODES).toEqual(["compare", "agent"]);
    expect(window.App.runMode.set("nonsense")).toBe(false);
    expect(window.App.runMode.set("consensus")).toBe(false);
    expect(window.App.runMode.set("compare")).toBe(false);
    expect(window.App.runMode.set("agent", {source: "composer"})).toBe(true);
    expect(heard).toHaveBeenCalledOnce();
    expect(heard).toHaveBeenCalledWith({mode: "agent", previous: "compare"});
    expect(window.App.trackAppEvent).toHaveBeenCalledWith("app_run_mode_changed", {mode: "agent", previous: "compare", source: "composer"});
    expect(window.App.runMode.copy("consensus")).toBeUndefined();
    dom.window.close();
  });

  it("resolves the effective mode from the open chat and the account", () => {
    const {window, dom} = boot({runMode: "agent"});
    const state = {family: null, canUse: false, pending: false};
    window.App.agentChat = {modeState: () => state};
    const mode = window.App.runMode;
    // No access: Agent is kept as the choice but runs as Compare.
    expect(mode.effective()).toBe("compare");
    expect(mode.availability().agent.visible).toBe(false);
    state.canUse = true;
    expect(mode.effective()).toBe("agent");
    // A saved Consensus chat or Compare result keeps its family, which only
    // Compare continues; Agent waits for a new chat.
    state.family = "consensus";
    expect(mode.effective()).toBe("compare");
    expect(mode.availability().agent).toEqual({visible: true, enabled: false, reason: "Available in a new chat"});
    expect(mode.availability().compare).toEqual({enabled: true, reason: ""});
    mode.set("compare");
    expect(mode.effective()).toBe("compare");
    // An open Agent chat stays Agent whatever the choice for new chats is.
    state.family = "agent";
    expect(mode.effective()).toBe("agent");
    expect(mode.availability().compare).toEqual({enabled: false, reason: "Available in a new chat"});
    expect(mode.availability()).not.toHaveProperty("consensus");
    expect(mode).not.toHaveProperty("pipeline");
    dom.window.close();
  });

  // Max, Apple-Audit H3: a guest sees Agent as an account does by default;
  // the login comes on Send (composer-invite.js), nothing runs without it.
  it("gives a guest Agent and Compare beside it, and an account without access only Compare", () => {
    const {window, dom} = boot();
    const state = {family: null, canUse: false, pending: false, guest: true};
    window.App.agentChat = {modeState: () => state};
    const mode = window.App.runMode;
    expect(mode.effective()).toBe("agent");
    expect(mode.availability().agent).toEqual({visible: true, enabled: true, reason: ""});
    expect(mode.availability().compare.enabled).toBe(true);
    // The guest's own choice holds, back and forth.
    mode.set("compare");
    expect(mode.effective()).toBe("compare");
    mode.set("agent");
    expect(mode.effective()).toBe("agent");
    // A signed-in account without Agent access is no guest.
    state.guest = false;
    expect(mode.effective()).toBe("compare");
    expect(mode.availability().agent.visible).toBe(false);
    dom.window.close();
  });

  it("follows a change made in another tab or arriving from the account", () => {
    const {window, dom} = boot({runMode: "compare", "consensio.settingsReset": "2026-10-12"});
    const heard = vi.fn();
    window.addEventListener("consensio:run-mode-change", event => heard(event.detail));
    const tab = (key, newValue) => {
      if (newValue === null) window.localStorage.removeItem(key);
      else window.localStorage.setItem(key, newValue);
      window.dispatchEvent(new window.StorageEvent("storage", {key, newValue, storageArea: window.localStorage}));
    };
    tab("runMode", "agent");
    tab("theme", "dark");
    expect(heard).toHaveBeenCalledOnce();
    expect(heard).toHaveBeenLastCalledWith({mode: "agent", previous: "compare"});
    tab("runMode", "compare");
    expect(heard).toHaveBeenLastCalledWith({mode: "compare", previous: "agent"});
    // Signing out drops the account's choice: back to the default.
    tab("runMode", null);
    expect(heard).toHaveBeenLastCalledWith({mode: "agent", previous: "compare"});
    // An old tab writing the retired mode reads as the default, so nothing
    // changes for this page.
    tab("runMode", "consensus");
    expect(heard).toHaveBeenCalledTimes(3);
    dom.window.close();
  });
});
