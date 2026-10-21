import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";

import { afterEach, describe, expect, it, vi } from "vitest";

import { loadScripts, ROOT } from "./helpers/appWindow.mjs";

/**
 * Motion is one system (Apple audit C8, C10, C11, C13, C14, E4, E11):
 *   - every transition and animation of /app names a duration and a curve
 *     from foundation.css; script reads the same values through App.motion;
 *   - one spinner, one beat for what repeats;
 *   - one focus ring that no hover tint hides, readable in the dark too;
 *   - one press;
 *   - the theme changes in one step, "reduce motion" turns journeys into
 *     fades, and every <details> opens softly.
 */
const read = (relative) => readFileSync(path.join(ROOT, relative), "utf8").replace(/\r\n/g, "\n");

const STYLE = read("static/style.css");
const APP_CSS = [...STYLE.matchAll(/url\('\.\/css\/([^']+)'\)/g)].map(m => `static/css/${m[1]}`);

// Every stylesheet a visitor or user gets: /app (static/style.css) and each
// sheet a template links, with everything they import, however deep
// (components-consensus-visuals.css, for one, only arrives through another
// sheet). The admin pages are a desktop tool and keep their own.
function templateFiles(dir) {
  return readdirSync(path.join(ROOT, dir), { withFileTypes: true }).flatMap(entry =>
    entry.isDirectory() ? templateFiles(`${dir}/${entry.name}`) : entry.name.endsWith(".html") ? [`${dir}/${entry.name}`] : []);
}
const LINKED = templateFiles("templates").flatMap(file =>
  [...read(file).matchAll(/\/(static\/(?:css\/)?[\w.-]+\.css)/g)].map(m => m[1]));
function withImports(entries) {
  const seen = new Set();
  const stack = [...entries];
  while (stack.length) {
    const file = stack.pop();
    if (seen.has(file)) continue;
    seen.add(file);
    for (const m of read(file).matchAll(/@import\s+url\(\s*['"]?([^'")]+)['"]?\s*\)/g)) {
      stack.push(path.posix.normalize(path.posix.join(path.posix.dirname(file), m[1])));
    }
  }
  return [...seen].sort();
}
const ALL_CSS = withImports(["static/style.css", ...LINKED])
  .filter(file => file !== "static/style.css" && !path.posix.basename(file).startsWith("admin"));

function declarations(css) {
  const out = [];
  const pattern = /(?<![-\w])(transition(?:-duration|-delay|-timing-function|-property)?|animation(?:-duration|-delay|-timing-function)?)\s*:\s*([^;{}]+);/g;
  for (const match of css.matchAll(pattern)) {
    out.push({ prop: match[1], value: match[2].trim(), line: css.slice(0, match.index).split("\n").length });
  }
  return out;
}

function items(value) {
  const out = [];
  let depth = 0, current = "";
  for (const ch of value) {
    if (ch === "(") depth += 1;
    if (ch === ")") depth -= 1;
    if (ch === "," && depth === 0) { out.push(current.trim()); current = ""; } else current += ch;
  }
  out.push(current.trim());
  return out;
}

describe("motion tokens (C14)", () => {
  const files = ALL_CSS;

  it("reads the nested and the public stylesheets too", () => {
    for (const sheet of ["components-consensus-visuals.css", "landing.css", "public-pages.css", "public-shell.css",
      "public-nav.css", "public-tokens.css", "benchmark.css", "topics.css", "consensus-engine.css", "model-pulse.css"]) {
      expect(files).toContain(`static/css/${sheet}`);
    }
    expect(files.some(file => file.includes("admin"))).toBe(false);
  });

  it("names only --dur-* and --ease-* in every transition and animation, in the app and on every public page", () => {
    const offenders = [];
    for (const file of files) {
      for (const { prop, value, line } of declarations(read(file))) {
        const clean = value.replace(/var\([^()]*(?:\([^()]*\)[^()]*)*\)/g, "VAR");
        if (/(?<![\w.-])\d*\.?\d*[1-9]\d*(?:ms|s)(?![\w-])/.test(clean)) offenders.push(`${file}:${line}: ${prop}: ${value} (raw time)`);
        if (/cubic-bezier\(|(?<![\w-])(?:ease|ease-in|ease-out|ease-in-out|linear)(?![\w-])/.test(clean)) offenders.push(`${file}:${line}: ${prop}: ${value} (raw curve)`);
        if (/^(?:transition|transition-property)$/.test(prop) && /(?<![\w-])all(?![\w-])/.test(clean)) offenders.push(`${file}:${line}: ${prop}: ${value} (all)`);
        if (prop === "transition" || prop === "animation") {
          for (const item of items(value)) {
            if (/^none\b/.test(item) || /allow-discrete/.test(item) || !/var\(--dur-|calc\(/.test(item)) continue;
            if (!/var\(--ease-|steps\(/.test(item)) offenders.push(`${file}:${line}: ${prop}: ${item} (no curve)`);
          }
        }
      }
    }
    expect(offenders).toEqual([]);
  });

  it("keeps durations in the tokens, not in custom properties of their own", () => {
    const offenders = [];
    for (const file of files) {
      const css = read(file).replace(/\/\*[\s\S]*?\*\//g, "");
      for (const match of css.matchAll(/(--[\w-]+)\s*:\s*([^;{}]+);/g)) {
        if (!/(?<![\w.-])\d*\.?\d*[1-9]\d*(?:ms|s)(?![\w-])/.test(match[2])) continue;
        if (file === "static/css/foundation.css" && /^--dur-/.test(match[1])) continue;
        offenders.push(`${file}: ${match[1]}: ${match[2].trim()}`);
      }
    }
    expect(offenders).toEqual([]);
  });

  it("uses --ease-in for things that leave", () => {
    const uses = APP_CSS.map(file => read(file)).join("\n").match(/var\(--ease-in\)/g) || [];
    expect(uses.length).toBeGreaterThan(5);
  });

  it("lets script read the same values", () => {
    const offenders = [];
    for (const file of ["static/firebase.js", "static/js/app-core.js", "static/js/model-answer-reader.js",
      "static/js/model-picker.js", "static/js/composer-starters.js", "static/js/agent-activity.js",
      "static/js/disclosure.js", "static/js/notices.js", "static/js/popover.js"]) {
      read(file).split("\n").forEach((line, index) => {
        if (/duration:\s*\d+[^}\n]*easing|easing:\s*["'][^"']+["']\s*[,}]/.test(line) && !/App\??\.motion/.test(line)) {
          offenders.push(`${file}:${index + 1}: ${line.trim()}`);
        }
      });
    }
    expect(offenders).toEqual([]);
  });

  it("keeps the fallbacks of App.motion equal to foundation.css", () => {
    const foundation = read("static/css/foundation.css");
    const motion = read("static/js/motion.js");
    for (const [name, value] of [["press", 120], ["state", 200], ["layer", 320], ["light", 560]]) {
      expect(foundation).toContain(`--dur-${name}: ${value}ms;`);
      expect(motion).toMatch(new RegExp(`${name}: ${value}\\b`));
    }
    for (const name of ["standard", "out", "in"]) {
      const value = foundation.match(new RegExp(`--ease-${name}: (cubic-bezier\\([^)]*\\))`))[1];
      expect(motion).toContain(`${name}: "${value}"`);
    }
  });
});

describe("one spinner and one beat (C13)", () => {
  it("draws every spinner with the one look and turn", () => {
    const css = APP_CSS.map(file => read(file)).join("\n");
    const spins = css.match(/@keyframes [\w-]*spin[\w-]*/gi) || [];
    expect(spins).toEqual(["@keyframes spinner-turn"]);
    expect(read("static/css/motion.css")).toMatch(/animation: spinner-turn var\(--dur-spin\) var\(--ease-linear\) infinite;/);
  });

  it("repeats everything else at the one beat, on the public pages too", () => {
    const offenders = [];
    for (const file of ALL_CSS) {
      for (const { value, line } of declarations(read(file))) {
        if (!/infinite/.test(value)) continue;
        if (!/var\(--dur-(?:beat|spin)\)|calc\(var\(--dur-(?:beat|spin)\)/.test(value)) offenders.push(`${file}:${line}: ${value}`);
      }
    }
    expect(offenders).toEqual([]);
  });
});

describe("focus ring and press (E4, E11)", () => {
  it("hides the ring behind no hover tint", () => {
    const offenders = [];
    const keep = /auth-modal:focus|auth-success:focus|agent-action-title:focus|model-picker-wrapper select:focus|bookmark > p:focus-visible|bookmark-rename-input/;
    for (const file of APP_CSS.filter(file => !file.endsWith("variables.css"))) {
      const css = read(file);
      for (const match of css.matchAll(/([^{}]*:focus(?:-visible)?[^{}]*)\{([^}]*)\}/g)) {
        const [selector, body] = [match[1].trim(), match[2]];
        if (keep.test(selector) || !/outline\s*:\s*(?:none|0)\s*[;}]?/.test(body)) continue;
        if (/box-shadow\s*:[^;]*(?:0 0 0|focus|ring)|outline\s*:\s*(?:var\(--focus|[1-9]px)/.test(body)) continue;
        offenders.push(`${file}: ${selector.split("\n").pop()}`);
      }
    }
    expect(offenders).toEqual([]);
  });

  it("draws the ring in the theme's own ink, so it reads on dark too", () => {
    const foundation = read("static/css/foundation.css");
    expect(foundation).toMatch(/:root,\s*\.dark-mode \{\s*--focus-ring-color: var\(--ink-2\);\s*--focus-ring: 2px solid var\(--focus-ring-color\);/);
    const variables = read("static/css/variables.css");
    const dark = variables.slice(variables.indexOf(".dark-mode {"));
    const hex = (name, css) => css.match(new RegExp(`--${name}:\\s*(#[0-9a-f]{6})`, "i"))[1];
    const luminance = (h) => {
      const [r, g, b] = [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16) / 255)
        .map(c => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
      return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    };
    const contrast = (a, b) => {
      const [x, y] = [luminance(a), luminance(b)].sort((m, n) => n - m);
      return (x + 0.05) / (y + 0.05);
    };
    expect(contrast(hex("ink-2", dark), hex("ground", dark))).toBeGreaterThanOrEqual(3);
    expect(contrast(hex("ink-2", variables), hex("ground", variables))).toBeGreaterThanOrEqual(3);
  });

  it("gives way by one amount everywhere", () => {
    const offenders = [];
    for (const file of APP_CSS) {
      const css = read(file);
      for (const match of css.matchAll(/([^{}]*:active[^{}]*)\{([^}]*)\}/g)) {
        const body = match[2];
        if (/transform\s*:\s*(?:translateY|scale\(0\.\d+\))/.test(body)) offenders.push(`${file}: ${match[1].trim().split("\n").pop()}`);
      }
    }
    expect(offenders).toEqual([]);
    expect(read("static/css/foundation.css")).toContain("--press-scale: 0.97;");
    expect(read("static/css/base.css")).toContain("transform: scale(var(--press-scale));");
  });
});

describe("reduce motion and the theme switch (C8, C10)", () => {
  it("fades the sidebar and keeps the column still with reduce motion", () => {
    const motion = read("static/css/motion.css");
    const block = motion.slice(motion.indexOf("@media (prefers-reduced-motion: reduce)"));
    expect(block).toMatch(/\.sidebar\.collapsed \{\s*transform: none !important;\s*opacity: 0;/);
    expect(block).toMatch(/\.container,[\s\S]*transition: none !important;/);
  });

  it("switches the theme with every transition off for that frame", () => {
    const ctx = loadScripts(["static/js/motion.js"], {
      before(window) { window.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} }); },
    });
    const { window, document } = ctx;
    let during = null;
    window.App.motion.switchTheme(() => { during = document.documentElement.classList.contains("is-theme-switching"); });
    expect(during).toBe(true);
    expect(read("static/css/motion.css")).toMatch(/html\.is-theme-switching \*,[\s\S]*transition: none !important;/);
    window.close();
  });
});

describe("disclosures (C11)", () => {
  const contexts = [];
  afterEach(() => contexts.splice(0).forEach(ctx => ctx.window.close()));

  it("animates a <details> open and closed and leaves the ones that move themselves", () => {
    const ctx = loadScripts(["static/js/motion.js", "static/js/disclosure.js"], {
      body: `<details id="d"><summary>Sources</summary><p>One</p></details>
        <details id="own"><summary>Thought for 3 s</summary><p>Two</p></details>`,
      before(window) { window.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} }); },
    });
    contexts.push(ctx);
    const { window, document } = ctx;
    const animations = [];
    window.HTMLElement.prototype.animate = function (frames, options) {
      const animation = { frames, options, onfinish: null, cancel() {}, target: this };
      animations.push(animation);
      return animation;
    };
    // jsdom lays nothing out: a closed <details> is its 20px summary, an open one 80px.
    window.HTMLElement.prototype.getBoundingClientRect = function () {
      const h = this.tagName === "SUMMARY" ? 20 : this.tagName === "DETAILS" && this.open ? 80 : 20;
      return { top: 0, bottom: h, height: h, width: 100, left: 0, right: 100 };
    };
    const details = document.getElementById("d");
    details.querySelector("summary").click();
    expect(details.open).toBe(true);
    expect(animations).toHaveLength(1);
    expect(animations[0].frames).toEqual([{ height: "20px" }, { height: "80px" }]);
    expect(details.classList.contains("is-disclosing")).toBe(true);
    animations[0].onfinish();
    expect(details.classList.contains("is-disclosing")).toBe(false);

    // Closing keeps it open until its height is down, then closes.
    details.querySelector("summary").click();
    expect(animations).toHaveLength(2);
    expect(animations[1].frames).toEqual([{ height: "80px" }, { height: "20px" }]);
    expect(details.open).toBe(true);
    animations[1].onfinish();
    expect(details.open).toBe(false);

    const own = document.getElementById("own");
    own.querySelector("summary").addEventListener("click", event => event.preventDefault());
    own.querySelector("summary").click();
    expect(animations).toHaveLength(2);
    expect(own.open).toBe(false);
    vi.restoreAllMocks();
  });
});
