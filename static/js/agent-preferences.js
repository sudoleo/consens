// Agent · Beta settings: how deep the comparison models answer, when the
// answer starts (quorum) and how freely Agent picks its models (autonomy). Saved in this browser and sent with every Agent
// message (agent_preferences); a running turn keeps the values it started with.
(function () {
  "use strict";
  const App = window.App = window.App || {};
  // v2 stores only what the user chose, so a later change of a default
  // reaches everyone who never touched that setting. v1 stored every field
  // whenever one changed; its values equal to the old defaults are dropped.
  const KEY = "consensio.agentPreferences.v2";
  const LEGACY_KEY = "consensio.agentPreferences.v1";
  const LEGACY_DEFAULTS = { depth: "auto", quorum: "balanced", autonomy: "guided" };
  // quorum "all" since 2026-10-07: a model that answers after the answer has
  // started no longer reaches its check.
  const DEFAULTS = Object.freeze({ depth: "auto", quorum: "all", autonomy: "guided" });
  const CHOICES = { depth: ["auto", "quick", "full"], quorum: ["balanced", "fast", "all"], autonomy: ["guided", "free"] };
  const CONTROLS = { depth: "agentDepthSelect", quorum: "agentQuorumSelect", autonomy: "agentAutonomySelect" };

  function stored() {
    try {
      const current = localStorage.getItem(KEY);
      if (current !== null) return JSON.parse(current) || {};
      const legacy = JSON.parse(localStorage.getItem(LEGACY_KEY) || "{}") || {};
      const chosen = {};
      for (const field of Object.keys(CHOICES)) {
        if (CHOICES[field].includes(legacy[field]) && legacy[field] !== LEGACY_DEFAULTS[field]) chosen[field] = legacy[field];
      }
      localStorage.setItem(KEY, JSON.stringify(chosen));
      localStorage.removeItem(LEGACY_KEY);
      return chosen;
    } catch (_) { return {}; }
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
    const value = { ...stored(), [field]: choice };
    try { localStorage.setItem(KEY, JSON.stringify(value)); } catch (_) { /* Session keeps the control value. */ }
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
    sync();
  }

  App.agentPreferences = { get, set, sync, defaults: () => ({ ...DEFAULTS }) };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bind);
  else bind();
})();
