// Agent · Beta settings: how deep the comparison models answer, when the
// answer starts (quorum), how freely Agent picks its models (autonomy) and
// whether the judges check the answer (judges, "Answer check"). An
// account setting ("agent_preferences", user-settings.js) sent with every
// Agent message; a running turn keeps the values it started with.
(function () {
  "use strict";
  const App = window.App = window.App || {};
  const settings = App.userSettings;
  // quorum "all" since 2026-10-07: a model that answers after the answer has
  // started no longer reaches its check.
  const DEFAULTS = Object.freeze({ depth: "auto", quorum: "all", autonomy: "guided", judges: "on" });
  const CHOICES = { depth: ["auto", "quick", "full"], quorum: ["balanced", "fast", "all"], autonomy: ["guided", "free"],
    judges: ["on", "off"] };
  const CONTROLS = { depth: "agentDepthSelect", quorum: "agentQuorumSelect", autonomy: "agentAutonomySelect",
    judges: "agentJudgesSelect" };

  // Only what the user chose is stored, so a later change of a default
  // reaches everyone who never touched that setting.
  function stored() {
    return settings.get("agent_preferences") || {};
  }

  function get() {
    const saved = stored();
    const value = { ...DEFAULTS };
    for (const field of Object.keys(CHOICES)) {
      if (CHOICES[field].includes(saved[field])) value[field] = saved[field];
    }
    return value;
  }

  function set(field, choice) {
    if (!CHOICES[field]?.includes(choice)) return;
    settings.set("agent_preferences", { ...stored(), [field]: choice });
  }

  // The tab only exists for accounts that can use Agent · Beta.
  function sync() {
    const allowed = App.agentChat?.canUse?.() === true;
    App.settingsTabs?.setTabAvailable?.("agentSettingsSection", allowed);
    const value = get();
    for (const [field, id] of Object.entries(CONTROLS)) {
      const control = document.getElementById(id);
      if (control && control.value !== value[field]) control.value = value[field];
    }
  }

  function bind() {
    for (const [field, id] of Object.entries(CONTROLS)) {
      document.getElementById(id)?.addEventListener("change", event => set(field, event.target.value));
    }
    // The account's values arrived (server, another tab, sign-out).
    settings.onChange("agent_preferences", detail => { if (detail.source !== "local") sync(); });
    sync();
  }

  App.agentPreferences = { get, set, sync, defaults: () => ({ ...DEFAULTS }) };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bind);
  else bind();
})();
