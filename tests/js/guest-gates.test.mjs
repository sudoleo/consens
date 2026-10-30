import { describe, expect, it, vi } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

// A guest at a door that needs an account gets the login dialog with a line
// that says what for, the same everywhere; no hint dot points a guest at
// something that can only ask for an account (Apple-Audit H2).
describe("App.askToLogIn", () => {
  it("opens the login dialog with the reason", () => {
    const { window } = loadScripts(["static/js/app-core.js"], {
      before(win) { win.App = { openAuthModal: vi.fn() }; }
    });
    const trigger = window.document.createElement("button");
    expect(window.App.askToLogIn("Log in to choose your models.", { trigger, source: "models" })).toBe(true);
    expect(window.App.openAuthModal).toHaveBeenCalledWith("login", trigger, "models", { lead: "Log in to choose your models." });
  });

  it("says it in the notice line when the dialog cannot open", () => {
    const { window } = loadScripts(["static/js/app-core.js"], {
      before(win) { win.App = { toast: vi.fn() }; }
    });
    expect(window.App.askToLogIn("Log in to share this answer.")).toBe(false);
    expect(window.App.toast).toHaveBeenCalledWith({ message: "Log in to share this answer." });
  });
});

// Max, Apple-Audit H3: a guest has Agent's composer; what in it needs an
// account opens the login with a line that says what for, never a dead click.
describe("A guest at the composer's doors", () => {
  const COMPOSER = `<div class="input-section"><div class="chat-input-container">
    <textarea id="questionInput"></textarea><button id="attachTrigger"></button>
    <div id="attachMenu" hidden><button id="attachUploadOption"></button><button id="attachDriveOption" hidden></button>
      <button id="agentComparisonMenuOption"></button></div>
    <input id="attachFileInput" type="file"><div id="attachmentBar" hidden></div></div>
    <div id="composerTools"><p id="composerModeDescription"></p></div><span id="composerModelIcons"></span>
    <div id="composerModeBar" hidden><p id="composerComparisonStatus"></p></div></div>`;

  function guest({ everyone = {} } = {}) {
    const ctx = loadScripts(["static/js/motion.js", "static/js/modal-dialog.js", "static/js/user-settings.js", "static/js/run-mode.js",
      "static/js/attachments.js", "static/js/agent-mode.js", "static/js/agent-google.js", "static/js/agent-drive.js"], {
      body: COMPOSER,
      before(window) {
        window.GOOGLE_FOR_EVERYONE = everyone;
        window.App = { modelPrefs: [], getModelOptionLabel: () => "", getSelectedModelCount: () => 0,
          initCustomModelPicker: vi.fn(), trackAppEvent: vi.fn(), showPopup: vi.fn(), askToLogIn: vi.fn(),
          isGuest: () => true,
          agentChat: { isSelected: () => true, looksAgent: () => true, canUse: () => false },
          runRegistry: { visible: () => null, isExecuting: () => false, getSelectedConversationBasis: () => null } };
        window.updateQuestionInputAccess = vi.fn();
      }
    });
    ctx.document.dispatchEvent(new ctx.window.Event("DOMContentLoaded"));
    ctx.window.App.agentGoogle.refreshControls();
    ctx.window.App.agentDrive.sync();
    return ctx;
  }

  it("asks for the login to add a file from the (+) menu", () => {
    const { window, document } = guest();
    document.getElementById("attachUploadOption").click();
    expect(window.App.askToLogIn).toHaveBeenLastCalledWith("Log in to add files.",
      { trigger: document.getElementById("attachTrigger"), source: "attachments" });
    expect(window.App.askToLogIn).toHaveBeenCalledTimes(1);
  });

  it("offers Gmail, Calendar and Drive only where every account has them, and asks for the login there", () => {
    // Google is per account while the app is unverified (GOOGLE_TEST_USERS):
    // a guest sees what an account sees that is not on the list, nothing.
    const listed = guest();
    expect(listed.document.getElementById("agentGoogleMenuOption").hidden).toBe(true);
    expect(listed.document.getElementById("attachDriveOption").hidden).toBe(true);
    const open = guest({ everyone: { gmail: true, drive: true } });
    const gmail = open.document.getElementById("agentGoogleMenuOption");
    const drive = open.document.getElementById("attachDriveOption");
    expect(gmail.hidden).toBe(false);
    expect(drive.hidden).toBe(false);
    gmail.click();
    expect(open.window.App.askToLogIn).toHaveBeenLastCalledWith("Log in to use Gmail and Calendar.", expect.objectContaining({ source: "google" }));
    drive.click();
    expect(open.window.App.askToLogIn).toHaveBeenLastCalledWith("Log in to add files.", expect.objectContaining({ source: "drive" }));
    // A guest who chose Consensus has no Agent entries.
    open.window.App.agentChat.looksAgent = () => false;
    open.window.App.agentChat.isSelected = () => false;
    open.window.App.agentGoogle.refreshControls();
    open.window.App.agentDrive.sync();
    expect(gmail.hidden).toBe(true);
    expect(drive.hidden).toBe(true);
  });
});

describe("The Watches hint dot", () => {
  function boot(user) {
    const timers = [];
    const harness = loadScripts(["static/js/watch-state.js", "static/js/watch-fields.js", "static/js/watch.js"], {
      body: '<div class="view-switch"><button id="viewSwitchConsensus"></button><button id="viewSwitchWatches"></button></div>',
      before(window) {
        window.setTimeout = fn => { timers.push(fn); return timers.length; };
        window.clearTimeout = () => {};
        window.fetch = vi.fn(async () => ({ ok: true, json: async () => ({}) }));
        window.auth = { currentUser: user };
      }
    });
    const flush = () => { while (timers.length) timers.shift()(); };
    return { ...harness, flush };
  }

  it("never shows for a guest", () => {
    const { document, flush } = boot(null);
    flush();
    expect(document.getElementById("viewSwitchWatches").classList.contains("has-watch-pulse")).toBe(false);
  });

  it("shows for an account, also one that signs in after the page loaded", () => {
    const later = boot(null);
    later.window.auth.currentUser = { uid: "u1" };
    later.window.dispatchEvent(new later.window.CustomEvent("consensio:auth-state", { detail: { uid: "u1" } }));
    later.flush();
    expect(later.document.getElementById("viewSwitchWatches").classList.contains("has-watch-pulse")).toBe(true);
    const account = boot({ uid: "u2" });
    account.flush();
    expect(account.document.getElementById("viewSwitchWatches").classList.contains("has-watch-pulse")).toBe(true);
  });
});
