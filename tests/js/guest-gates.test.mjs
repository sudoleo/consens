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
