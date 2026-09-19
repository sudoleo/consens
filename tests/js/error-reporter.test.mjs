import { describe, expect, it } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

function boot() {
  const reports = [];
  const loaded = loadScripts(["static/js/error-reporter.js"], {
    before(window) {
      window.fetch = (_url, options) => {
        reports.push(JSON.parse(options.body));
        return Promise.resolve({ ok: true });
      };
    },
  });
  return { ...loaded, reports };
}

function fail(window, element) {
  window.document.head.appendChild(element);
  element.dispatchEvent(new window.Event("error"));
}

describe("critical resource reporting", () => {
  it("keeps distinct runtime locations and strips query data from the script field", () => {
    const { window, dom, reports } = boot();
    for (const colno of [42, 84, 42]) {
      window.dispatchEvent(new window.ErrorEvent("error", {
        message: "private runtime message",
        error: new window.TypeError("private runtime message"),
        filename: window.location.origin + "/static/dist/app.012345abcdef.js?token=private",
        lineno: 1, colno,
      }));
    }
    expect(reports).toHaveLength(2);
    expect(reports[0]).toMatchObject({ error_name: "TypeError", script: "app.012345abcdef.js", line: 1, column: 42 });
    expect(reports[1].column).toBe(84);
    dom.window.close();
  });

  it("extracts an app location from a rejected promise stack", () => {
    const { window, dom, reports } = boot();
    const event = new window.Event("unhandledrejection");
    event.reason = { name: "RangeError", message: "private",
      stack: `RangeError: private\n    at secret (${window.location.origin}/static/dist/firebase.abcdef012345.js:2:321)` };
    window.dispatchEvent(event);
    expect(reports[0]).toMatchObject({ error_name: "RangeError", script: "firebase.abcdef012345.js", line: 2, column: 321 });
    dom.window.close();
  });

  it.each([
    "https://foreign.example/static/dist/app.012345abcdef.js",
    "/static/js/private-user-file.js",
    "/static/dist/app.private.js",
  ])("does not include unapproved runtime metadata: %s", (filename) => {
    const { window, dom, reports } = boot();
    window.dispatchEvent(new window.ErrorEvent("error", {
      message: "private", error: { name: "private@example.test" }, filename, lineno: 4, colno: 8,
    }));
    expect(reports[0]).not.toHaveProperty("script");
    expect(reports[0]).not.toHaveProperty("line");
    expect(reports[0]).not.toHaveProperty("error_name");
    dom.window.close();
  });

  it("preserves distinct stream failure categories during deduplication", () => {
    const { window, dom, reports } = boot();
    for (const kind of ["stream_read_failed", "stream_handler_failed", "stream_read_failed"]) {
      window.App.reportCriticalError({ type: "consensus_failed", phase: "consensus_connection",
        message: "Failed", failure_kind: kind });
    }
    expect(reports.map(report => report.failure_kind)).toEqual(["stream_read_failed", "stream_handler_failed"]);
    dom.window.close();
  });
  it("ignores optional source favicons", () => {
    const { window, document, reports } = boot();
    const image = document.createElement("img");
    image.src = "/api/topics/favicon?d=example.com";

    fail(window, image);

    expect(reports).toEqual([]);
  });

  it("ignores document favicons", () => {
    const { window, document, reports } = boot();
    const link = document.createElement("link");
    link.rel = "icon";
    link.href = "/static/favicon.svg";

    fail(window, link);

    expect(reports).toEqual([]);
  });

  it("reports a failed app script without sending its URL", () => {
    const { window, document, reports } = boot();
    const script = document.createElement("script");
    script.src = "/static/dist/app.abc123.js";

    fail(window, script);

    expect(reports).toHaveLength(1);
    expect(reports[0]).toMatchObject({
      type: "resource_load_failed",
      phase: "asset_load",
      resource_class: "app_bundle",
      path: "/app",
    });
    expect(reports[0]).not.toHaveProperty("details");
  });

  it("classifies a failed CDN stylesheet", () => {
    const { window, document, reports } = boot();
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = "https://cdn.jsdelivr.net/npm/katex/dist/katex.min.css";

    fail(window, link);

    expect(reports).toHaveLength(1);
    expect(reports[0].resource_class).toBe("jsdelivr_dependency");
  });
});
