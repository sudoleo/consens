// =====================================================================
// run-mode.js
// The one choice of what consens does with the next message:
//   compare   · answers side by side, no consensus
//   consensus · the consensus pipeline with differences and checks
//   agent     · Agent (Beta): works in steps with research, files and tools
//
// This module only owns the preference. It is the single source of truth
// for the composer selector, the settings panel and every run; the value is
// the account setting "run_mode" (user-settings.js stores and syncs it,
// including the migration of older stored values). Whether a
// mode can be used right now (plan, sign-in, the family of an open chat)
// is decided where that knowledge lives (agent-chat.js); the composer asks
// App.runMode.effective() for the combined answer.
//
// Loaded in the render-blocking head bundle, after user-settings.js, so the
// first paint already matches the stored mode. No DOM access here.
// Exports: window.App.runMode
// Event:   "consensio:run-mode-change" on window, detail {mode, previous}
// =====================================================================

(function () {
  "use strict";

  const settings = window.App.userSettings;
  const MODES = Object.freeze(["compare", "consensus", "agent"]);
  // For people who never chose. Agent is the default since 2026-10-02, for
  // guests too (Max, Apple-Audit H3: a guest sees what an account sees and
  // logs in on Send); an account without Agent access (a refused status
  // check) still falls back to consensus in effective().
  const DEFAULT_MODE = "agent";

  const COPY = Object.freeze({
    compare: Object.freeze({ label: "Compare", description: "Answers side by side, no consensus." }),
    consensus: Object.freeze({ label: "Consensus", description: "One answer with its differences and checks." }),
    agent: Object.freeze({ label: "Agent", badge: "Beta", description: "Works in steps with research, files and tools." }),
  });

  function valid(mode) {
    return MODES.includes(mode);
  }

  function read() {
    return settings.get("run_mode") || DEFAULT_MODE;
  }

  function preference() {
    return read();
  }

  function set(mode, options = {}) {
    if (!valid(mode)) return false;
    const previous = read();
    if (previous === mode) return false;
    settings.set("run_mode", mode);
    if (options.source) {
      window.App?.trackAppEvent?.("app_run_mode_changed", { mode, previous, source: options.source });
    }
    window.dispatchEvent(new CustomEvent("consensio:run-mode-change", { detail: { mode, previous } }));
    return true;
  }

  // Agent is offered to an account with access and to a guest, who sees it
  // as that account will and logs in on Send (composer-invite.js; the server
  // still refuses Agent without an account, agent.py require_agent_access).
  function agentOffered(state) {
    return Boolean(state?.canUse || state?.guest);
  }

  // What the next message will actually do, given the open chat and the
  // account. agent-chat.js reports the open chat's family, access and guest.
  function effective() {
    const state = window.App?.agentChat?.modeState?.();
    const pref = read();
    if (state?.family === "agent") return "agent";
    if (pref === "agent") {
      if (state?.family === "consensus" || !agentOffered(state)) return "consensus";
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
    const offered = agentOffered(state) || family === "agent";
    return {
      compare: { enabled: family !== "agent", reason: family === "agent" ? newChatReason : "" },
      consensus: { enabled: family !== "agent", reason: family === "agent" ? newChatReason : "" },
      agent: {
        visible: offered,
        enabled: family !== "consensus" && offered,
        reason: family === "consensus" ? newChatReason : "",
      },
    };
  }

  // The account's value arrived from the server, another tab or a sign-out.
  // A change on this page went through set() and has announced itself.
  settings.onChange("run_mode", detail => {
    if (detail.source === "local") return;
    const mode = read();
    const previous = detail.previous.run_mode || DEFAULT_MODE;
    if (mode === previous) return;
    window.dispatchEvent(new CustomEvent("consensio:run-mode-change", { detail: { mode, previous } }));
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
