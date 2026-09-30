import { describe, expect, it, vi } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

// run-mode.js is the single source of truth for Compare / Consensus / Agent.
function boot(storage = {}) {
  return loadScripts(["static/js/run-mode.js"], {
    before(window) {
      Object.entries(storage).forEach(([key, value]) => window.localStorage.setItem(key, value));
      window.App = { trackAppEvent: vi.fn() };
    }
  });
}

describe("run mode", () => {
  it.each([
    [{}, "consensus"],
    [{agentMode: "true", autoConsensus: "true"}, "consensus"],
    [{agentMode: "false", autoConsensus: "false"}, "compare"],
    [{runMode: "agent", agentMode: "false"}, "agent"],
    [{runMode: "bogus"}, "consensus"],
  ])("migrates %o once to %s and removes the legacy keys", (storage, expected) => {
    const {window, dom} = boot(storage);
    expect(window.App.runMode.preference()).toBe(expected);
    expect(window.localStorage.getItem("runMode")).toBe(expected);
    if (!storage.runMode || storage.runMode === "bogus") {
      expect(window.localStorage.getItem("agentMode")).toBeNull();
      expect(window.localStorage.getItem("autoConsensus")).toBeNull();
    }
    dom.window.close();
  });

  it("changes only to known modes, announces changes once and tracks the source", () => {
    const {window, dom} = boot({runMode: "consensus"});
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

  it("follows a change made in another tab", () => {
    const {window, dom} = boot({runMode: "consensus"});
    const heard = vi.fn();
    window.addEventListener("consensio:run-mode-change", event => heard(event.detail));
    window.dispatchEvent(new window.StorageEvent("storage", {key: "runMode", oldValue: "consensus", newValue: "compare"}));
    window.dispatchEvent(new window.StorageEvent("storage", {key: "runMode", newValue: "bogus"}));
    window.dispatchEvent(new window.StorageEvent("storage", {key: "theme", newValue: "dark"}));
    expect(heard).toHaveBeenCalledOnce();
    expect(heard).toHaveBeenCalledWith({mode: "compare", previous: "consensus"});
    dom.window.close();
  });
});
