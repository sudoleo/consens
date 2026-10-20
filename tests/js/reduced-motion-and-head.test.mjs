/**
 * Three small /app guards from the audit's frontend section.
 *
 * F15: smooth scrolling honours prefers-reduced-motion. Every scroll with a
 *      `behavior` takes it from App.scrollBehavior() (app-core.js) or checks
 *      the preference itself; a hard-coded "smooth" may not come back.
 * F8:  marked and DOMPurify no longer block the first paint. They load
 *      deferred and still before the Firebase module and the app bundle that
 *      call them (deferred scripts and modules run in document order).
 * F10: the footer note and the dialogs' close mark use --ink-3, which keeps
 *      text contrast (4.5:1) on the canvas in both themes and at least the
 *      3:1 of a graphical control on the raised dialog surface.
 */

import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import { loadScripts, ROOT } from "./helpers/appWindow.mjs";
import { templateText } from "./helpers/appBoot.mjs";

const read = (relative) => readFileSync(path.join(ROOT, relative), "utf8").replace(/\r\n/g, "\n");

function bootCore(reduce) {
  return loadScripts(["static/js/app-core.js"], {
    before(window) {
      // Like a MediaQueryList, `matches` is live.
      window.matchMedia = (query) => ({
        media: query,
        get matches() { return query.includes("prefers-reduced-motion") ? reduce.value : false; },
        addEventListener() {}, removeEventListener() {},
      });
    },
  });
}

describe("reduced motion (F15)", () => {
  it("App.scrollBehavior follows the system setting at call time", () => {
    const reduce = { value: false };
    const { window } = bootCore(reduce);
    expect(window.App.scrollBehavior()).toBe("smooth");
    reduce.value = true;
    expect(window.App.scrollBehavior()).toBe("auto");
    window.close();
  });

  it("no /app script hard-codes a smooth scroll", () => {
    const files = [
      ...readdirSync(path.join(ROOT, "static/js")).map((name) => `static/js/${name}`),
      ...readdirSync(path.join(ROOT, "static")).map((name) => `static/${name}`),
    ].filter((file) => file.endsWith(".js"));
    const offenders = files.filter((file) => /behavior:\s*["']smooth["']/.test(read(file)));
    expect(offenders).toEqual([]);
  });
});

describe("render-blocking vendor scripts (F8)", () => {
  it("loads marked and DOMPurify deferred, ahead of the Firebase module and the app group", () => {
    const head = templateText().split("</head>")[0];
    const tag = (name) => head.match(new RegExp(`<script[^>]*${name}[^>]*></script>`))?.[0];
    for (const name of ["marked\\.min\\.js", "purify\\.min\\.js"]) {
      const script = tag(name);
      expect(script, name).toBeTruthy();
      expect(script).toMatch(/\sdefer[\s>]/);
      expect(head.indexOf(script)).toBeLessThan(head.indexOf('script.group != "head"'));
    }
  });
});

function luminance(hex) {
  const [r, g, b] = [1, 3, 5].map((index) => parseInt(hex.slice(index, index + 2), 16) / 255)
    .map((channel) => (channel <= 0.03928 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(a, b) {
  const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (light + 0.05) / (dark + 0.05);
}

function rule(css, selector) {
  const start = css.indexOf(`\n${selector} {`);
  expect(start, selector).toBeGreaterThan(-1);
  return css.slice(start, css.indexOf("}", start));
}

describe("contrast of the footer note and the close mark (F10)", () => {
  const variables = read("static/css/variables.css");
  const shell = read("static/css/shell.css");
  const [lightInk3, darkInk3] = [...variables.matchAll(/--ink-3:\s*(#[0-9a-f]{6})/gi)].map((m) => m[1]);
  const [lightGround, darkGround] = [...variables.matchAll(/--ground:\s*(#[0-9a-f]{6})/gi)].map((m) => m[1]);
  const lightSurface = shell.match(/body:not\(\.dark-mode\) \{[^}]*--app-surface:\s*(#[0-9a-f]{6})/i)[1];
  const darkSurface = shell.match(/body\.dark-mode \{\s*--app-surface:\s*(#[0-9a-f]{6})/i)[1];

  it("colours both with --ink-3", () => {
    const consensus = read("static/css/components-consensus.css");
    // The one close cross of every dialog (Apple audit G3) lives in foundation.css.
    const foundation = read("static/css/foundation.css");
    expect(rule(consensus, ".feedback-note")).toContain("color: var(--ink-3)");
    expect(rule(foundation, ".close-button")).toContain("color: var(--ink-3)");
    expect(variables).not.toContain("--feedback-text-color");
  });

  it("keeps --ink-3 readable as text on the canvas and as a control on dialogs", () => {
    expect(contrast(lightInk3, lightGround)).toBeGreaterThanOrEqual(4.5);
    expect(contrast(darkInk3, darkGround)).toBeGreaterThanOrEqual(4.5);
    expect(contrast(lightInk3, lightSurface)).toBeGreaterThanOrEqual(4.5);
    expect(contrast(darkInk3, darkSurface)).toBeGreaterThanOrEqual(3);
  });
});
