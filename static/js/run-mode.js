// =====================================================================
// run-mode.js
// The one choice of what consens does with the next message:
//   agent   · Agent (Beta): works in steps with research, files and tools
//   compare · answers side by side
//
// Consensus was a third mode until 2026-10-25. The pipeline behind it now
// runs only on the server (Watches, the API, curated topics); a stored
// "consensus" choice is dropped and reads as the default, Agent
// (user-settings.js, user_settings.py). Saved Consensus chats stay
// readable and belong to the same server family as Compare.
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
  const MODES = Object.freeze(["compare", "agent"]);
  // For people who never chose. Agent is the default since 2026-10-02, for
  // guests too (Max, Apple-Audit H3: a guest sees what an account sees and
  // logs in on Send); an account without Agent access (a refused status
  // check) falls back to Compare in effective().
  const DEFAULT_MODE = "agent";

  const COPY = Object.freeze({
    compare: Object.freeze({ label: "Compare", description: "Answers side by side." }),
    agent: Object.freeze({ label: "Agent", badge: "Beta", description: "Works in steps with research, files and tools." }),
  });

  function valid(mode) {
    return MODES.includes(mode);
  }

  function read() {
    const stored = settings.get("run_mode");
    return valid(stored) ? stored : DEFAULT_MODE;
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
  // The server keeps two chat families: Agent chats, and the family of
  // Compare results and saved Consensus chats ("consensus"). An open chat
  // keeps its family, so an Agent choice there runs as Compare.
  function effective() {
    const state = window.App?.agentChat?.modeState?.();
    const pref = read();
    if (state?.family === "agent") return "agent";
    if (pref === "agent") {
      if (state?.family === "consensus" || !agentOffered(state)) return "compare";
      return "agent";
    }
    return pref;
  }

  // Which choices the open chat allows and why the others are not offered.
  function availability() {
    const state = window.App?.agentChat?.modeState?.() || {};
    const family = state.family || null;
    const newChatReason = "Available in a new chat";
    const offered = agentOffered(state) || family === "agent";
    return {
      compare: { enabled: family !== "agent", reason: family === "agent" ? newChatReason : "" },
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
    const before = detail.previous.run_mode;
    const previous = valid(before) ? before : DEFAULT_MODE;
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
  });
})();
