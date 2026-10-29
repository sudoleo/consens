import { afterEach, expect, it, vi } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

const contexts = [];
afterEach(() => contexts.splice(0).forEach(ctx => ctx.window.close()));

function boot(allowed) {
  const ctx = loadScripts(["static/js/user-settings.js", "static/js/agent-preferences.js"], {
    body: `<select id="agentDepthSelect"><option value="auto">A</option><option value="quick">Q</option><option value="full">F</option></select>
      <select id="agentQuorumSelect"><option value="balanced">B</option><option value="fast">F</option><option value="all">A</option></select>
      <select id="agentAutonomySelect"><option value="guided">G</option><option value="free">F</option></select>
      <select id="agentJudgesSelect"><option value="on">On</option><option value="off">Off</option></select>
      <select id="agentAuditSelect"><option value="off">Off</option><option value="on">On</option></select>
      <select id="agentVmSelect"><option value="off">Off</option><option value="on">On</option></select>`,
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
  // Since 2026-10-07 the answer waits for every model by default.
  expect(w.App.agentPreferences.get()).toEqual({ depth: "auto", quorum: "all", autonomy: "guided", judges: "on", audit: "off", vm: "off" });
  const depth = d.getElementById("agentDepthSelect");
  depth.value = "full"; depth.dispatchEvent(new w.Event("change"));
  // Only the explicit choice is stored, so a later default still applies.
  expect(JSON.parse(w.localStorage.getItem("consensio.agentPreferences.v2"))).toEqual({ depth: "full" });
  const quorum = d.getElementById("agentQuorumSelect");
  quorum.value = "fast"; quorum.dispatchEvent(new w.Event("change"));
  const autonomy = d.getElementById("agentAutonomySelect");
  autonomy.value = "free"; autonomy.dispatchEvent(new w.Event("change"));
  // Answer check off: the judges skip the agent's answer.
  const judges = d.getElementById("agentJudgesSelect");
  judges.value = "off"; judges.dispatchEvent(new w.Event("change"));
  // The way of working (Pro and admins): Audit brings its own VM, so vm
  // follows audit and has no choice of its own (2026-10-26).
  const audit = d.getElementById("agentAuditSelect");
  audit.value = "on"; audit.dispatchEvent(new w.Event("change"));
  expect(w.App.agentPreferences.get())
    .toEqual({ depth: "full", quorum: "fast", autonomy: "free", judges: "off", audit: "on", vm: "on" });
  expect(JSON.parse(w.localStorage.getItem("consensio.agentPreferences.v2")))
    .toEqual({ depth: "full", quorum: "fast", autonomy: "free", judges: "off", audit: "on" });
  // Unknown stored values fall back to the defaults.
  w.localStorage.setItem("consensio.agentPreferences.v2", JSON.stringify({ depth: "deep", quorum: "fast", judges: "maybe", audit: "yes", vm: "maybe" }));
  w.App.agentPreferences.sync();
  expect(w.App.agentPreferences.get()).toEqual({ depth: "auto", quorum: "fast", autonomy: "guided", judges: "on", audit: "off", vm: "off" });
  expect(depth.value).toBe("auto");
  expect(quorum.value).toBe("fast");
  expect(autonomy.value).toBe("guided");
  expect(judges.value).toBe("on");
  expect(audit.value).toBe("off");
});

it("moves v1 settings over without pinning the old defaults", () => {
  const { window: w } = boot(true);
  // v1 stored every field whenever one changed: "balanced" there was the
  // default of that time, not a choice; "free" was chosen.
  w.localStorage.removeItem("consensio.agentPreferences.v2");
  w.localStorage.setItem("consensio.agentPreferences.v1", JSON.stringify({ depth: "auto", quorum: "balanced", autonomy: "free" }));
  expect(w.App.agentPreferences.get()).toEqual({ depth: "auto", quorum: "all", autonomy: "free", judges: "on", audit: "off", vm: "off" });
  expect(w.localStorage.getItem("consensio.agentPreferences.v1")).toBe(null);
  expect(JSON.parse(w.localStorage.getItem("consensio.agentPreferences.v2"))).toEqual({ autonomy: "free" });
  // A real v1 choice of a faster start survives.
  w.localStorage.removeItem("consensio.agentPreferences.v2");
  w.localStorage.setItem("consensio.agentPreferences.v1", JSON.stringify({ depth: "auto", quorum: "fast", autonomy: "guided" }));
  expect(w.App.agentPreferences.get().quorum).toBe("fast");
});

it("offers the settings tab only to accounts with Agent Beta", () => {
  const allowed = boot(true);
  expect(allowed.window.App.settingsTabs.setTabAvailable).toHaveBeenLastCalledWith("agentSettingsSection", true);
  const denied = boot(false);
  expect(denied.window.App.settingsTabs.setTabAvailable).toHaveBeenLastCalledWith("agentSettingsSection", false);
});

// One reviewer is enough in audit mode, which runs for Pro accounts and
// admins: the chip and Send learn of a change at once (model-picker.js,
// agent-chat.js), and the settings show only what the way of working uses.
it("audits only for an account allowed it and redraws the chip when audit changes", () => {
  const { window: w, document: d } = boot(true);
  w.syncCustomModelPickers = vi.fn();
  w.updateQuestionInputAccess = vi.fn();
  const section = d.createElement("section"); section.id = "agentSettingsSection"; d.body.append(section);
  const audit = d.getElementById("agentAuditSelect");
  audit.value = "on"; audit.dispatchEvent(new w.Event("change"));
  expect(w.App.agentPreferences.auditing()).toBe(false);
  expect(section.classList.contains("is-audit")).toBe(false);
  d.body.classList.add("viewer-can-audit");
  expect(w.App.agentPreferences.auditing()).toBe(true);
  w.App.agentPreferences.sync();
  expect(section.classList.contains("is-audit")).toBe(true);
  // Today's VM time under the way of working (/user_status vm_time).
  const line = d.createElement("small"); line.id = "agentVmTime"; line.hidden = true; section.append(line);
  // The VM is promised only where the server has one (no vm_time without).
  const vm = d.createElement("small"); vm.id = "agentAuditVm"; vm.hidden = true; section.append(vm);
  w.App.agentPreferences.sync();
  expect(vm.hidden).toBe(true);
  w.App.vmTime = { used_seconds: 2520, limit_seconds: 7200 };
  w.App.agentPreferences.sync();
  expect(vm.hidden).toBe(false);
  expect(line.hidden).toBe(false);
  expect(line.textContent).toBe("Workspace time today: 42 of 120 min");
  w.App.vmTime = { used_seconds: 90, limit_seconds: null };
  w.App.agentPreferences.sync();
  expect(line.textContent).toBe("Workspace time today: 2 min, no daily limit");
  expect(w.syncCustomModelPickers).toHaveBeenCalledTimes(1);
  expect(w.updateQuestionInputAccess).toHaveBeenCalledTimes(1);
  // Another setting leaves the chip alone.
  const depth = d.getElementById("agentDepthSelect");
  depth.value = "quick"; depth.dispatchEvent(new w.Event("change"));
  expect(w.syncCustomModelPickers).toHaveBeenCalledTimes(1);
});
