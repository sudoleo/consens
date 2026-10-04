import { afterEach, expect, it, vi } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

const contexts = [];
afterEach(() => contexts.splice(0).forEach(ctx => ctx.window.close()));

function boot(allowed) {
  const ctx = loadScripts(["static/js/agent-preferences.js"], {
    body: `<select id="agentDepthSelect"><option value="auto">A</option><option value="quick">Q</option><option value="full">F</option></select>
      <select id="agentQuorumSelect"><option value="balanced">B</option><option value="fast">F</option><option value="all">A</option></select>
      <select id="agentAutonomySelect"><option value="guided">G</option><option value="free">F</option></select>`,
    before(window) {
      window.App = { agentChat: { canUse: () => allowed }, settingsTabs: { setTabAvailable: vi.fn() } };
    },
  });
  ctx.window.document.dispatchEvent(new ctx.window.Event("DOMContentLoaded"));
  contexts.push(ctx);
  return ctx;
}

it("saves every choice, restores them and ignores unknown stored values", () => {
  const { window: w, document: d } = boot(true);
  expect(w.App.agentPreferences.get()).toEqual({ depth: "auto", quorum: "balanced", autonomy: "guided" });
  const depth = d.getElementById("agentDepthSelect");
  depth.value = "full"; depth.dispatchEvent(new w.Event("change"));
  const quorum = d.getElementById("agentQuorumSelect");
  quorum.value = "all"; quorum.dispatchEvent(new w.Event("change"));
  const autonomy = d.getElementById("agentAutonomySelect");
  autonomy.value = "free"; autonomy.dispatchEvent(new w.Event("change"));
  expect(w.App.agentPreferences.get()).toEqual({ depth: "full", quorum: "all", autonomy: "free" });
  // Values saved before the freedom setting existed fall back to guided.
  w.localStorage.setItem("consensio.agentPreferences.v1", JSON.stringify({ depth: "deep", quorum: "fast" }));
  w.App.agentPreferences.sync();
  expect(w.App.agentPreferences.get()).toEqual({ depth: "auto", quorum: "fast", autonomy: "guided" });
  expect(depth.value).toBe("auto");
  expect(quorum.value).toBe("fast");
  expect(autonomy.value).toBe("guided");
});

it("offers the settings tab only to accounts with Agent Beta", () => {
  const allowed = boot(true);
  expect(allowed.window.App.settingsTabs.setTabAvailable).toHaveBeenLastCalledWith("agentSettingsSection", true);
  const denied = boot(false);
  expect(denied.window.App.settingsTabs.setTabAvailable).toHaveBeenLastCalledWith("agentSettingsSection", false);
});
