import { describe, expect, it } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

function boot(scripts = []) {
  let status = null;
  let metadata = {};
  let hidden = false;
  const result = loadScripts([...scripts, "static/js/tab-status.js"], {
    before(window) {
      window.document.title = "consens.io";
      Object.defineProperty(window.document, "hidden", { configurable: true, get: () => hidden });
      window.App = { runRegistry: { visible: () => (status ? { status, metadata } : null) } };
    },
  });
  const { window } = result;
  return {
    window,
    title: () => window.document.title,
    run(next, data = {}) { status = next; metadata = data; window.dispatchEvent(new window.CustomEvent("consensio:run-registry-change")); },
    hide() { hidden = true; window.document.dispatchEvent(new window.Event("visibilitychange")); },
    show() { hidden = false; window.document.dispatchEvent(new window.Event("visibilitychange")); },
  };
}

describe("tab status", () => {
  it("names a running and a finished run only while the page is hidden", () => {
    const app = boot();
    app.run("running");
    expect(app.title()).toBe("consens.io");
    app.hide();
    expect(app.title()).toBe("Working… · consens.io");
    app.run("succeeded");
    expect(app.title()).toBe("Answer ready · consens.io");
    app.show();
    expect(app.title()).toBe("consens.io");
  });

  it("says that a run paused by a reviewer waits for the user, also when it paused before", () => {
    const app = boot();
    app.run("running", { hold: { id: "a1b2c3d4e5f6" } });
    app.hide();
    expect(app.title()).toBe("Paused · consens.io");
    app.run("running", { hold: null });
    expect(app.title()).toBe("Working… · consens.io");
  });

  it("says that the agent waits for the user when it asked them something (ask_user)", () => {
    const app = boot();
    app.run("running", { hold: { id: "a1b2c3d4e5f6", ask: "browser" } });
    app.hide();
    expect(app.title()).toBe("Waiting for you · consens.io");
  });

  // Each projection of the visible run sets the page title again
  // (App.setAppTitle from run-view.js and agent-chat.js), right after the
  // registry event: a Compare run did it with every streamed chunk and wiped
  // "Working…", and its last projection wiped "Answer ready" at once.
  it("keeps its label in front of the title a projection sets while the page is hidden", () => {
    const app = boot(["static/js/app-core.js"]);
    const project = () => app.window.App.setAppTitle("Price of gold");
    app.run("running");
    project();
    app.hide();
    expect(app.title()).toBe("Working… · Price of gold | consens.io");
    project();
    expect(app.title()).toBe("Working… · Price of gold | consens.io");
    app.run("succeeded");
    project();
    expect(app.title()).toBe("Answer ready · Price of gold | consens.io");
    app.show();
    expect(app.title()).toBe("Price of gold | consens.io");
  });

  it("does not announce a run that was already done before the tab was left", () => {
    const app = boot();
    app.run("succeeded");
    app.hide();
    expect(app.title()).toBe("consens.io");
  });
});
