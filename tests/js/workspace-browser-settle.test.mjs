/**
 * The workspace browser's watch on the page for every action (browser.py
 * HIT_JS and QUIET_JS, since 2026-10-30, runtime audit T4 and L2): it says
 * how long the page has not changed since the action, so the answer comes
 * once the action's effect is there (a menu a timer opens), and the changes
 * near the element a ref names come first.
 */
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { JSDOM } from "jsdom";
import { describe, expect, it } from "vitest";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const SOURCE = readFileSync(path.join(ROOT, "app/services/workspace_vm/browser/browser.py"), "utf8");
const HIT_JS = SOURCE.match(/HIT_JS = r"""\n([\s\S]*?)\n"""/)[1];
const QUIET_JS = SOURCE.match(/QUIET_JS = r"""\n([\s\S]*?)\n"""/)[1];

function page(body, boxes) {
  const dom = new JSDOM(`<!doctype html><html><body>${body}</body></html>`, { runScripts: "outside-only" });
  const { window } = dom;
  window.Element.prototype.getBoundingClientRect = function () {
    const [left, top, right, bottom] = boxes.get(this) || [0, 0, 0, 0];
    return { left, top, right, bottom, width: right - left, height: bottom - top };
  };
  // A clock the test moves: performance.now() as the page tells it.
  let now = 1000;
  Object.defineProperty(window.performance, "now", { configurable: true, value: () => now });
  return {
    window,
    document: window.document,
    hit: window.eval(`(${HIT_JS})`),
    quiet: window.eval(`(${QUIET_JS})`),
    later: (ms) => {
      now += ms;
    },
  };
}

// MutationObserver hands its records over in a microtask.
const settled = () => new Promise((resolve) => setTimeout(resolve, 0));

describe("workspace browser watch", () => {
  it("counts from the action's end and starts again with every change of the page", async () => {
    const { document, hit, quiet, later } = page('<button data-consens-ref="e1">Account</button>', new Map());
    // No watch on the page (a new document): null, and browser.py loads it as before.
    expect(quiet(true)).toBeNull();
    hit({ mode: "before", points: [], limit: 5, refs: ["e1"] });
    later(400);
    // The action took 400 ms: its effect may still come, so the count starts now.
    expect(quiet(true)).toBe(0);
    later(150);
    expect(quiet(false)).toBe(150);
    // A timer opens the menu: the page changed, the count starts again.
    const menu = document.createElement("div");
    menu.textContent = "Settings";
    document.body.append(menu);
    await settled();
    later(100);
    expect(quiet(false)).toBe(100);
    // read's own marks are no change of the page.
    document.querySelector("button").setAttribute("data-consens-ref", "e1");
    menu.setAttribute("data-consens-frame", "f1");
    later(250);
    expect(quiet(false)).toBe(350);
  });

  it("lists the changes nearest to the element a ref names first", () => {
    const boxes = new Map();
    const { document, hit } = page(
      '<div class="far">far</div><button data-consens-ref="e7">Account</button><div class="near">near</div>', boxes);
    const [far, button, near] = document.querySelectorAll(".far, button, .near");
    boxes.set(far, [900, 700, 1000, 760]).set(button, [10, 10, 110, 40]).set(near, [10, 50, 200, 90]);
    hit({ mode: "before", points: [], limit: 5, refs: ["e7", "e99", "x; drop"] });
    far.textContent = "far, changed";
    near.textContent = "near, changed";
    button.setAttribute("aria-expanded", "true");
    const report = hit({ mode: "after", points: [], limit: 5 });
    expect(report.count).toBe(3);
    expect(report.changed.map((item) => [item.tag, item.how])).toEqual([
      ["button", "aria-expanded"], ["div.near", "text"], ["div.far", "text"]]);
  });

  it("watches a page also without points or refs (a key, a scroll)", () => {
    const { document, hit } = page("<p>text</p>", new Map());
    const { at } = hit({ mode: "before", points: [], limit: 5 });
    expect(at).toEqual([]);
    document.querySelector("p").textContent = "other";
    expect(hit({ mode: "after", points: [], limit: 5 }).count).toBe(1);
  });
});
