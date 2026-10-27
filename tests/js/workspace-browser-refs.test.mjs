/**
 * The workspace browser's refs (app/services/workspace_vm/browser.py,
 * SNAPSHOT_JS): a ref stays with its element and is never given twice, so a
 * ref from an older read names its element or none, never another one. Until
 * 2026-10-27 every read numbered the page from e1 again.
 */
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { JSDOM } from "jsdom";
import { describe, expect, it } from "vitest";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const SOURCE = readFileSync(path.join(ROOT, "app/services/workspace_vm/browser.py"), "utf8");
const SNAPSHOT_JS = SOURCE.match(/SNAPSHOT_JS = r"""\n([\s\S]*?)\n"""/)[1];

function page(body) {
  const dom = new JSDOM(`<!doctype html><html><body>${body}</body></html>`, { runScripts: "outside-only" });
  const { window } = dom;
  // jsdom lays nothing out: every element has a box here.
  window.Element.prototype.getBoundingClientRect = () => ({ width: 10, height: 10 });
  const snapshot = window.eval(`(${SNAPSHOT_JS})`);
  return { window, document: window.document, read: (start) => snapshot(start) };
}

const refOf = (line) => line.match(/^\[(e\d+)\]/)[1];

describe("workspace browser refs", () => {
  it("keeps an element's ref across reads and numbers new elements on", () => {
    const { document, read } = page(
      '<button aria-label="One">1</button><button aria-label="Two">2</button><a href="/x">Three</a>'
    );
    const first = read(0);
    expect(first.lines.map(refOf)).toEqual(["e1", "e2", "e3"]);
    expect(first.count).toBe(3);

    const added = document.createElement("button");
    added.setAttribute("aria-label", "New");
    document.body.prepend(added);
    const second = read(first.count);
    // The new element comes first on the page and takes the next number.
    expect(second.lines.map(refOf)).toEqual(["e4", "e1", "e2", "e3"]);
    expect(second.count).toBe(4);
  });

  it("never gives a removed element's ref to another one", () => {
    const { document, read } = page('<button aria-label="One">1</button><button aria-label="Two">2</button>');
    const first = read(0);
    document.querySelector('[data-consens-ref="e1"]').remove();
    document.body.append(document.createElement("button"));
    const second = read(first.count);
    expect(second.lines.map(refOf)).toEqual(["e2", "e3"]);
    expect(document.querySelector('[data-consens-ref="e1"]')).toBeNull();
  });

  it("goes on with the workspace's count on a new page", () => {
    const { read } = page('<button aria-label="One">1</button>');
    expect(read(7).lines.map(refOf)).toEqual(["e8"]);
  });

  it("gives a copied element a ref of its own", () => {
    const { document, read } = page('<button aria-label="One">1</button>');
    const first = read(0);
    const original = document.querySelector("button");
    document.body.append(original.cloneNode(true));
    const second = read(first.count);
    expect(second.lines.map(refOf)).toEqual(["e1", "e2"]);
    expect(document.querySelectorAll('[data-consens-ref="e1"]').length).toBe(1);
  });

  it("lists what lies inside a listed element as part of it", () => {
    const { read } = page('<a href="/x"><span role="button">Inner</span></a><button aria-label="After">b</button>');
    expect(read(0).lines.map(refOf)).toEqual(["e1", "e2"]);
  });
});
