/**
 * scroll in a box of the page (browser.py BOX_SCROLL_JS) and what is in view
 * after it (IN_VIEW_JS): a chat list or a side pane scrolls in a box of its
 * own, and the rows it scrolled out are not in view, though the window
 * holds their place.
 */
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { JSDOM } from "jsdom";
import { describe, expect, it } from "vitest";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const SOURCE = readFileSync(path.join(ROOT, "app/services/workspace_vm/browser/browser.py"), "utf8");
const IN_VIEW_JS = SOURCE.match(/IN_VIEW_JS = r"""\n([\s\S]*?)\n"""/)[1];
const BOX_SCROLL_JS = SOURCE.match(/BOX_SCROLL_JS = r"""\n([\s\S]*?)\n"""/)[1];

// jsdom lays nothing out: each element's box ([left, top, right, bottom]
// in the window, 1024x768) and scroll sizes ({height, view, top}) as the test
// gives them, and scrollBy as Chrome's, within the box's content.
function page(body, boxes = {}, sizes = {}) {
  const dom = new JSDOM(`<!doctype html><html><body>${body}</body></html>`, { runScripts: "outside-only" });
  const { window } = dom;
  const { document } = window;
  const byId = (table) => new Map(Object.entries(table).map(([id, value]) => [document.getElementById(id), value]));
  const placed = byId(boxes);
  const scrolled = byId(sizes);
  const proto = window.Element.prototype;
  proto.getBoundingClientRect = function () {
    const [left, top, right, bottom] = placed.get(this) || [0, 0, 0, 0];
    return { left, top, right, bottom, width: right - left, height: bottom - top };
  };
  const size = (name, fallback) => function () {
    const own = scrolled.get(this);
    return own ? own[name] : fallback;
  };
  Object.defineProperty(proto, "scrollHeight", { configurable: true, get: size("height", 0) });
  Object.defineProperty(proto, "clientHeight", { configurable: true, get: size("view", 0) });
  Object.defineProperty(proto, "scrollTop", { configurable: true, get: size("top", 0) });
  proto.scrollBy = function ({ top }) {
    const own = scrolled.get(this);
    if (own) own.top = Math.max(0, Math.min(own.height - own.view, own.top + top));
  };
  Object.defineProperty(window.HTMLElement.prototype, "innerText", {
    configurable: true,
    get() {
      return this.textContent;
    },
  });
  return {
    document,
    inView: window.eval(`(${IN_VIEW_JS})`),
    boxScroll: window.eval(`(${BOX_SCROLL_JS})`),
  };
}

const CHATS = `
  <h1 id="title">Chats</h1>
  <div id="chats" class="list pane" style="overflow-y: auto">
    <button id="r1" data-consens-ref="e1">Anna</button>
    <button id="r2" data-consens-ref="e2">Ben</button>
    <button id="r3" data-consens-ref="e3">Carla</button>
    <button id="new" data-consens-ref="e4" style="position: fixed">New chat</button>
  </div>
  <form id="send"><input name="parentElement"><button id="go" data-consens-ref="e5">Send</button></form>`;
// The list's box is y 100-400 of the window; it scrolled Anna out above and
// holds Carla below, both within the window.
const PLACED = {
  title: [0, 0, 400, 40], chats: [0, 100, 300, 400], r1: [0, 40, 300, 90], r2: [0, 150, 300, 200],
  r3: [0, 450, 300, 500], new: [900, 700, 1000, 740], send: [400, 100, 900, 160], go: [400, 110, 500, 150],
};

describe("workspace browser scroll in a box", () => {
  it("counts only what the boxes around an element leave in view, and a fixed element as in the window", () => {
    const { inView } = page(CHATS, PLACED);
    expect(inView()).toEqual({ refs: ["e2", "e4", "e5"], headings: ['heading "Chats"'] });
  });

  it("scrolls the nearest box that scrolls, by 80 % of its height, and names it", () => {
    const { document, boxScroll } = page(CHATS, PLACED, { chats: { height: 3000, view: 300, top: 0 } });
    expect(boxScroll(document.getElementById("r2"), 1)).toEqual({
      tag: "div#chats.list.pane", moved: [0, 240, 300, 3000],
    });
    expect(boxScroll(document.getElementById("chats"), -1)).toEqual({
      tag: "div#chats.list.pane", moved: [240, 0, 300, 3000],
    });
  });

  it("goes past a box with nothing to scroll, and answers null where none scrolls", () => {
    const { document, boxScroll } = page(CHATS, PLACED, { chats: { height: 300, view: 300, top: 0 } });
    expect(boxScroll(document.getElementById("r2"), 1)).toBeNull();
    // A form whose field is named parentElement: the walk goes up the DOM, not round the field.
    expect(boxScroll(document.getElementById("go"), 1)).toBeNull();
    expect(boxScroll(null, 1)).toBeNull();
  });
});
