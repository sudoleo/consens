import { describe, expect, it } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

// `served` answers the HEAD probe for a failed same-origin asset: false is a
// real outage (reported), true a resource the browser refused by itself.
function boot({ served = false } = {}) {
  const reports = [];
  const probes = [];
  const loaded = loadScripts(["static/js/error-reporter.js"], {
    before(window) {
      window.fetch = (url, options) => {
        if (options?.method === "HEAD") { probes.push(String(url)); return Promise.resolve({ ok: served }); }
        reports.push(JSON.parse(options.body));
        return Promise.resolve({ ok: true });
      };
    },
  });
  return { ...loaded, reports, probes };
}

async function fail(window, element) {
  window.document.head.appendChild(element);
  element.dispatchEvent(new window.Event("error"));
  for (let i = 0; i < 3; i++) await Promise.resolve();
}

describe("critical resource reporting", () => {
  it("sends a nonempty message even for a rejection without a reason", () => {
    const { window, dom, reports } = boot();
    window.dispatchEvent(new window.Event("unhandledrejection"));
    expect(typeof reports[0].message).toBe("string");
    expect(reports[0].message.length).toBeGreaterThan(0);
    dom.window.close();
  });

  it("does not throw when the reporting transport throws synchronously", () => {
    const { window, dom } = boot();
    window.fetch = () => { throw new window.TypeError("blocked transport"); };
    expect(() => window.App.reportCriticalError({ message: "Original failure" })).not.toThrow();
    dom.window.close();
  });

  it("bounds the report before the keepalive request", () => {
    const { window, dom, reports } = boot();
    window.App.reportCriticalError({ message: "x".repeat(100000), stack: "s".repeat(100000), details: "d".repeat(100000) });
    expect(JSON.stringify(reports[0]).length).toBeLessThan(8000);
    dom.window.close();
  });
  it("identifies separate failed app assets without query strings", async () => {
    const { window, document, dom, reports } = boot();
    for (const src of [
      "/static/dist/app.012345abcdef.js?token=private",
      "/static/dist/firebase.abcdef012345.js",
      "/static/vendor/katex/0.17.0/dist/katex.min.js",
      "/static/vendor/katex/0.17.0/dist/contrib/auto-render.min.js",
    ]) {
      const script = document.createElement("script");
      script.src = src;
      await fail(window, script);
    }
    expect(reports.map(report => report.asset)).toEqual([
      "dist/app.012345abcdef.js", "dist/firebase.abcdef012345.js",
      "vendor/katex/0.17.0/dist/katex.min.js", "vendor/katex/0.17.0/dist/contrib/auto-render.min.js",
    ]);
    expect(JSON.stringify(reports)).not.toContain("private");
    dom.window.close();
  });

  it("does not send unapproved resource names", async () => {
    const { window, document, dom, reports } = boot();
    const script = document.createElement("script");
    script.src = "/static/private-user.js";
    await fail(window, script);
    expect(reports[0]).not.toHaveProperty("asset");
    dom.window.close();
  });

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

  it("sends up to five bundle frames as coordinate tuples only", () => {
    const { window, dom, reports } = boot();
    const origin = window.location.origin;
    const app = `${origin}/static/dist/app.012345abcdef.js`;
    const event = new window.Event("unhandledrejection");
    event.reason = { name: "TypeError", message: "private",
      stack: [
        "TypeError: private",
        `    at secretFunction (${app}:3:100)`,
        "    at foreign (https://foreign.example/static/dist/app.012345abcdef.js:1:1)",
        `    at ${origin}/static/js/private-user-file.js:1:2`,
        `    at other (${origin}/static/dist/head.abcdef012345.js:1:77)`,
        ...[1, 2, 3, 4, 5].map((n) => `    at f${n} (${app}:1:${n})`),
      ].join("\n") };
    window.dispatchEvent(event);
    expect(reports[0].frames).toEqual([
      ["app.012345abcdef.js", 3, 100],
      ["head.abcdef012345.js", 1, 77],
      ["app.012345abcdef.js", 1, 1],
      ["app.012345abcdef.js", 1, 2],
      ["app.012345abcdef.js", 1, 3],
    ]);
    expect(reports[0]).toMatchObject({ script: "app.012345abcdef.js", line: 3, column: 100 });
    expect(JSON.stringify(reports[0].frames)).not.toMatch(/secret|foreign|private|https?:/);
    dom.window.close();
  });

  it("names the running app bundle so the alert knows the deploy", () => {
    const { window, document, dom, reports } = boot();
    for (const src of ["/static/dist/head.abcdef012345.js", "/static/dist/app.0123456789ab.js"]) {
      const script = document.createElement("script");
      script.setAttribute("src", src);
      document.body.appendChild(script);
    }
    window.App.reportCriticalError({ type: "run_failed", message: "Failed" });
    expect(reports.find((report) => report.type === "run_failed").bundle).toBe("app.0123456789ab.js");
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

  it("drops errors that cannot point at any code location", () => {
    const { window, dom, reports } = boot();
    for (const init of [
      { message: "Script error.", filename: "" },
      { message: "Uncaught Error", filename: "https://apis.google.com/js/api.js", lineno: 1, colno: 2 },
      { message: "ResizeObserver loop completed with undelivered notifications.", filename: "" },
    ]) {
      window.dispatchEvent(new window.ErrorEvent("error", init));
    }
    expect(reports).toEqual([]);
    window.dispatchEvent(new window.ErrorEvent("error", {
      message: "private", error: new window.TypeError("private"), filename: "",
    }));
    expect(reports).toHaveLength(1);
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

  it("reports a failed app script without sending its URL", async () => {
    const { window, document, reports } = boot();
    const script = document.createElement("script");
    script.src = "/static/dist/app.abc123.js";

    await fail(window, script);

    expect(reports).toHaveLength(1);
    expect(reports[0]).toMatchObject({
      type: "resource_load_failed",
      phase: "asset_load",
      resource_class: "app_bundle",
      path: "/app",
    });
    expect(reports[0]).not.toHaveProperty("details");
  });

  it("does not alert when the server delivers an asset the browser refused itself", async () => {
    const { window, document, reports, probes } = boot({ served: true });
    for (const href of ["/static/dist/app.4f2dceaa1823.css", "/static/vendor/katex/0.17.0/dist/katex.min.css?v=2105ed91f651"]) {
      const link = document.createElement("link");
      link.rel = "stylesheet";
      link.href = href;
      await fail(window, link);
    }
    expect(probes).toHaveLength(2);
    expect(reports).toEqual([]);
  });

  it("alerts when a same-origin stylesheet is really unavailable", async () => {
    const { window, document, reports } = boot({ served: false });
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = "/static/dist/app.4f2dceaa1823.css";
    await fail(window, link);
    expect(reports).toHaveLength(1);
    expect(reports[0]).toMatchObject({ resource_class: "app_bundle", asset: "dist/app.4f2dceaa1823.css" });
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
