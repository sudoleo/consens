import { describe, expect, it } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

function boot() {
  let status = null;
  let hidden = false;
  const result = loadScripts(["static/js/tab-status.js"], {
    before(window) {
      window.document.title = "consens.io";
      Object.defineProperty(window.document, "hidden", { configurable: true, get: () => hidden });
      window.App = { runRegistry: { visible: () => (status ? { status } : null) } };
    },
  });
  const { window } = result;
  return {
    title: () => window.document.title,
    run(next) { status = next; window.dispatchEvent(new window.CustomEvent("consensio:run-registry-change")); },
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

  it("does not announce a run that was already done before the tab was left", () => {
    const app = boot();
    app.run("succeeded");
    app.hide();
    expect(app.title()).toBe("consens.io");
  });
});
