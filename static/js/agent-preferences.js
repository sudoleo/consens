// Agent · Beta settings: how deep the comparison models answer, when the
// answer starts (quorum) and how freely Agent picks its models (autonomy). Saved in this browser and sent with every Agent
// message (agent_preferences); a running turn keeps the values it started with.
(function () {
  "use strict";
  const App = window.App = window.App || {};
  const KEY = "consensio.agentPreferences.v1";
  const DEFAULTS = Object.freeze({ depth: "auto", quorum: "balanced", autonomy: "guided" });
  const CHOICES = { depth: ["auto", "quick", "full"], quorum: ["balanced", "fast", "all"], autonomy: ["guided", "free"] };
  const CONTROLS = { depth: "agentDepthSelect", quorum: "agentQuorumSelect", autonomy: "agentAutonomySelect" };

  function get() {
    let stored = {};
    try { stored = JSON.parse(localStorage.getItem(KEY) || "{}") || {}; } catch (_) { stored = {}; }
    const value = { ...DEFAULTS };
    for (const field of Object.keys(CHOICES)) {
      if (CHOICES[field].includes(stored[field])) value[field] = stored[field];
    }
    return value;
  }

  function set(field, choice) {
    if (!CHOICES[field]?.includes(choice)) return;
    const value = { ...get(), [field]: choice };
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
