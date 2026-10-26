// Agent · Beta settings: the way of working (audit: Comparison or Audit,
// agent_audit.py; Pro and admins) and, for Comparison, how deep the
// comparison models answer, when the answer starts (quorum), how freely
// Agent picks its models (autonomy) and whether the judges check the answer
// (judges, "Answer check"). Audit always brings its own Linux VM
// (agent_vm_tools.py) and its reviewers, so ``vm`` follows ``audit`` (the
// server decides the same, routers/agent.py effective_preferences). An
// account setting ("agent_preferences", user-settings.js) sent with every
// Agent message; a running turn keeps the values it started with.
(function () {
  "use strict";
  const App = window.App = window.App || {};
  const settings = App.userSettings;
  // quorum "all" since 2026-10-07: a model that answers after the answer has
  // started no longer reaches its check.
  const DEFAULTS = Object.freeze({ depth: "auto", quorum: "all", autonomy: "guided", judges: "on", audit: "off",
    vm: "off" });
  const CHOICES = { depth: ["auto", "quick", "full"], quorum: ["balanced", "fast", "all"], autonomy: ["guided", "free"],
    judges: ["on", "off"], audit: ["off", "on"], vm: ["off", "on"] };
  // The way of working is .audit-only in the page (Pro and admins); there is no VM row.
  const CONTROLS = { depth: "agentDepthSelect", quorum: "agentQuorumSelect", autonomy: "agentAutonomySelect",
    judges: "agentJudgesSelect", audit: "agentAuditSelect" };

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
    value.vm = value.audit;
    return value;
  }

  function set(field, choice) {
    if (!CHOICES[field]?.includes(choice)) return;
    settings.set("agent_preferences", { ...stored(), [field]: choice });
    if (field === "audit") auditChanged();
  }

  // Audit runs for Pro accounts and admins (routers/agent.py audit_allowed,
  // /user_status audit_access). Its comparison models review the agent's
  // work, and one reviewer is enough (agent_comparison.comparison_selection):
  // the chip and Send follow, and the settings show only what applies.
  function auditing() {
    return get().audit === "on" && document.body.classList.contains("viewer-can-audit");
  }
  function auditChanged() {
    // Also when set from code (the Agent's settings card): the select follows.
    sync();
    window.syncCustomModelPickers?.();
    window.updateQuestionInputAccess?.();
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
    document.getElementById("agentSettingsSection")?.classList.toggle("is-audit", auditing());
    renderVmTime();
  }

  // Today's VM time under the way of working (/user_status vm_time,
  // agent_vm_time.py): whole sentences, translated here (data-i18n-skip).
  function renderVmTime() {
    const line = document.getElementById("agentVmTime");
    if (!line) return;
    const time = App.vmTime;
    const used = Math.round((Number(time?.used_seconds) || 0) / 60);
    const limit = Number(time?.limit_seconds) > 0 ? Math.round(time.limit_seconds / 60) : null;
    line.hidden = !time || !auditing();
    line.textContent = !time ? "" : limit === null
      ? App.t("VM time today: {used} min, no daily limit", { used })
      : App.t("VM time today: {used} of {limit} min", { used: Math.min(used, limit), limit });
  }

  function bind() {
    for (const [field, id] of Object.entries(CONTROLS)) {
      document.getElementById(id)?.addEventListener("change", event => set(field, event.target.value));
    }
    // The account's values arrived (server, another tab, sign-out).
    settings.onChange("agent_preferences", detail => { if (detail.source !== "local") { sync(); auditChanged(); } });
    sync();
  }

  App.agentPreferences = { get, set, sync, auditing, defaults: () => ({ ...DEFAULTS }) };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bind);
  else bind();
})();
