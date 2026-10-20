import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import { ROOT } from "./helpers/appWindow.mjs";
import { ancestors, lineOf, parseCss, walkRules } from "./helpers/css-rules.mjs";

/**
 * A finger is not a mouse (Apple audit F3, F4, F15):
 *   - a tap leaves :hover stuck on touch screens until the next tap
 *     elsewhere; a knob looked switched on, a row stayed grey. Every :hover
 *     rule of /app and the public pages therefore lives inside the one guard
 *     `@media (hover: hover) and (pointer: fine)`; :focus-visible and state
 *     selectors stay outside it, so keyboard and open states look the same
 *     everywhere;
 *   - no grey/blue tap flash of the browser, the press (--press-scale) is the
 *     one feedback;
 *   - the type does not grow on its own when the phone turns.
 */
const read = (relative) => readFileSync(path.join(ROOT, relative), "utf8").replace(/\r\n/g, "\n");

const GUARD = "@media (hover: hover) and (pointer: fine)";
// The admin pages are a desktop tool; everything a visitor or user can open is checked.
const SHEETS = readdirSync(path.join(ROOT, "static/css"))
  .filter(name => name.endsWith(".css") && !name.startsWith("admin"))
  .map(name => `static/css/${name}`);

describe("hover only where a pointer hovers (F4)", () => {
  it("covers the app and the public stylesheets", () => {
    for (const sheet of ["shell.css", "layout.css", "landing.css", "public-pages.css", "foundation.css"]) {
      expect(SHEETS).toContain(`static/css/${sheet}`);
    }
  });

  it("keeps every :hover rule inside the one guard", () => {
    const offenders = [];
    for (const file of SHEETS) {
      const css = read(file);
      for (const rule of walkRules(parseCss(css))) {
        if (!rule.selector.includes(":hover")) continue;
        if (ancestors(rule).some(at => at.prelude === GUARD)) continue;
        offenders.push(`${file}:${lineOf(css, rule.start)}: ${rule.selector}`);
      }
    }
    expect(offenders).toEqual([]);
  });

  it("spells the guard one way and needs no touch counter-rules", () => {
    const offenders = [];
    for (const file of SHEETS) {
      const css = read(file);
      const tree = parseCss(css);
      const visit = node => {
        for (const child of node.children || []) {
          if (child.type !== "at") continue;
          if (/\(hover:\s*hover\)/.test(child.prelude) && child.prelude !== GUARD) {
            offenders.push(`${file}:${lineOf(css, child.start)}: ${child.prelude}`);
          }
          visit(child);
        }
      };
      visit(tree);
      // "A tap leaves :hover stuck" resets under (hover: none) are obsolete:
      // no hover fill reaches a touch screen any more.
      for (const rule of walkRules(tree)) {
        if (rule.selector.includes(":hover") && ancestors(rule).some(at => /hover:\s*none/.test(at.prelude))) {
          offenders.push(`${file}:${lineOf(css, rule.start)}: ${rule.selector} (touch reset)`);
        }
      }
    }
    expect(offenders).toEqual([]);
  });
});

describe("no browser tap flash, no text inflation (F3, F15)", () => {
  const foundation = read("static/css/foundation.css");

  it("lives once in foundation.css, which /app and every public page import", () => {
    expect(foundation).toMatch(/:root \{[^}]*-webkit-tap-highlight-color: transparent;/);
    expect(foundation).toMatch(/:root \{[^}]*-webkit-text-size-adjust: 100%;\s*text-size-adjust: 100%;/);
    expect(read("static/css/variables.css")).toMatch(/@import url\('\.\/foundation\.css'\)/);
    expect(read("static/css/public-tokens.css")).toMatch(/@import url\('\.\/foundation\.css'\)/);
  });

  it("is not set again (or undone) anywhere else", () => {
    const offenders = SHEETS
      .filter(file => !file.endsWith("foundation.css"))
      .filter(file => /tap-highlight-color|text-size-adjust/.test(read(file)));
    expect(offenders).toEqual([]);
  });
});
