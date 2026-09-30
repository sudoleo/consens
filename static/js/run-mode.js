// =====================================================================
// run-mode.js
// The one choice of what consens does with the next message:
//   compare   · answers side by side, no consensus
//   consensus · the consensus pipeline with differences and checks
//   agent     · Agent (Beta): works in steps with research, files and tools
//
// This module only owns the preference. It is the single source of truth
// for the composer selector, the settings panel and every run. Whether a
// mode can be used right now (plan, sign-in, the family of an open chat)
// is decided where that knowledge lives (agent-chat.js); the composer asks
// App.runMode.effective() for the combined answer.
//
// Loaded in the render-blocking head bundle so the first paint already
// matches the stored mode. No DOM access here.
// Exports: window.App.runMode
// Event:   "consensio:run-mode-change" on window, detail {mode, previous}
// =====================================================================

(function () {
  "use strict";

  const STORAGE_KEY = "runMode";
  const MODES = Object.freeze(["compare", "consensus", "agent"]);
  // For people who never chose. When Agent leaves Beta this becomes
  // "agent"; accounts without Agent access still fall back to consensus in
  // effective(), so the switch is this one line.
  const DEFAULT_MODE = "consensus";
  // Before 2026-10 two switches decided this: "agentMode" (consensus on/off)
  // and an in-memory Agent Beta choice. "autoConsensus" only mirrored the
  // first. Migrated once and removed, so nothing can read a stale copy.
  const LEGACY_KEYS = ["agentMode", "autoConsensus"];

  const COPY = Object.freeze({
    compare: Object.freeze({ label: "Compare", description: "Answers side by side, no consensus." }),
    consensus: Object.freeze({ label: "Consensus", description: "One answer with its differences and checks." }),
    agent: Object.freeze({ label: "Agent", badge: "Beta", description: "Works in steps with research, files and tools." }),
  });

  let memory = null; // used only when storage is unavailable

  function valid(mode) {
    return MODES.includes(mode);
  }

  function read() {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (valid(stored)) return stored;
      const legacy = localStorage.getItem("agentMode");
      const migrated = legacy === "false" ? "compare" : legacy === "true" ? "consensus" : DEFAULT_MODE;
      localStorage.setItem(STORAGE_KEY, migrated);
      LEGACY_KEYS.forEach(key => localStorage.removeItem(key));
      return migrated;
    } catch (_) {
      return memory || DEFAULT_MODE;
    }
  }

  function preference() {
    return read();
  }

  function set(mode, options = {}) {
    if (!valid(mode)) return false;
    const previous = read();
    if (previous === mode) return false;
    try { localStorage.setItem(STORAGE_KEY, mode); } catch (_) { memory = mode; }
    if (options.source) {
      window.App?.trackAppEvent?.("app_run_mode_changed", { mode, previous, source: options.source });
    }
    window.dispatchEvent(new CustomEvent("consensio:run-mode-change", { detail: { mode, previous } }));
    return true;
  }

  // What the next message will actually do, given the open chat and the
  // account. agent-chat.js reports the open chat's family and access.
  function effective() {
    const state = window.App?.agentChat?.modeState?.();
    const pref = read();
    if (state?.family === "agent") return "agent";
    if (pref === "agent") {
      if (state?.family === "consensus" || !state?.canUse) return "consensus";
      return "agent";
    }
    return pref;
  }

  // Compare and Consensus share one chat family and may alternate per
  // message; Agent chats are a separate family on the server. This says
  // which choices the open chat allows and why the others are not offered.
  function availability() {
    const state = window.App?.agentChat?.modeState?.() || {};
    const family = state.family || null;
    const newChatReason = "Available in a new chat";
    return {
      compare: { enabled: family !== "agent", reason: family === "agent" ? newChatReason : "" },
      consensus: { enabled: family !== "agent", reason: family === "agent" ? newChatReason : "" },
      agent: {
        visible: Boolean(state.canUse) || family === "agent",
        enabled: family !== "consensus" && (Boolean(state.canUse) || family === "agent"),
        reason: family === "consensus" ? newChatReason : "",
      },
    };
  }

  // Another tab changed the mode: storage is shared, the event is not.
  window.addEventListener("storage", event => {
    if (event.key !== STORAGE_KEY || !valid(event.newValue)) return;
    window.dispatchEvent(new CustomEvent("consensio:run-mode-change",
      { detail: { mode: event.newValue, previous: valid(event.oldValue) ? event.oldValue : null } }));
  });

  window.App = window.App || {};
  window.App.runMode = Object.freeze({
    MODES,
    DEFAULT_MODE,
    copy: mode => COPY[mode],
    preference,
    set,
    effective,
    availability,
    // The consensus pipeline runs for Consensus, and for an Agent choice the
    // account or open chat cannot honour. Only Compare skips it.
    pipeline: () => effective() !== "compare",
  });
})();
