/**
 * The workspace browser's refs (app/services/workspace_vm/browser/browser.py,
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
const SOURCE = readFileSync(path.join(ROOT, "app/services/workspace_vm/browser/browser.py"), "utf8");
const SNAPSHOT_JS = SOURCE.match(/SNAPSHOT_JS = r"""\n([\s\S]*?)\n"""/)[1];
const FIND_JS = SOURCE.match(/FIND_JS = r"""\n([\s\S]*?)\n"""/)[1];

// What a browser's own stylesheet says and jsdom leaves out: these are inline.
const BROWSER_DEFAULTS = "<style>a, b, i, em, strong, span, label, code { display: inline }</style>";

function page(body) {
  const dom = new JSDOM(`<!doctype html><html><head>${BROWSER_DEFAULTS}</head><body>${body}</body></html>`, {
    runScripts: "outside-only",
  });
  const { window } = dom;
  // jsdom lays nothing out: every element has a box here, and its text
  // shows as it stands (jsdom has no innerText).
  window.Element.prototype.getBoundingClientRect = () => ({ width: 10, height: 10 });
  Object.defineProperty(window.HTMLElement.prototype, "innerText", {
    configurable: true,
    get() {
      return this.textContent;
    },
  });
  const snapshot = window.eval(`(${SNAPSHOT_JS})`);
  const search = window.eval(`(${FIND_JS})`);
  // The browser's count (browser.py's REF_COUNTER), kept as page_lines keeps it.
  let counter = 0;
  const read = (start) => {
    const result = snapshot(start);
    counter = Math.max(counter, result.count);
    return result;
  };
  // As browser.py's find_text: read first, then the search with read's refs.
  const find = (query, limit = 20) => {
    const refs = read(counter).lines.map((line) => (line.match(/^\[(e\d+)\] /) || [])[1]).filter(Boolean);
    return search({ query, refs, limit, around: 60 });
  };
  return { window, document: window.document, read, find };
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

  it("gives a link's and a heading's text whole up to 200 characters", () => {
    const words = (size) => "word ".repeat(size / 5).trim();
    const { read } = page(`<h2>${words(190)}</h2><a href="/a">${words(150)}</a><a href="/b">${"x".repeat(250)}</a>`);
    const [heading, whole, long] = read(0).lines;
    expect(heading).toBe(`heading "${words(190)}"`);
    expect(whole).toBe(`[e1] link "${words(150)}"`);
    expect(long).toBe(`[e2] link "${"x".repeat(199)}…"`);
  });
});

describe("workspace browser find", () => {
  it("finds a text in any case, with the ref of the listed element it lies in", () => {
    const { find } = page(
      '<h1>Prices</h1><p>The price is <b>12 €</b>.</p><a href="/sale">Sale <span>price</span> list</a>' +
        '<button aria-label="Buy">Buy</button>'
    );
    const found = find("PRICE");
    expect(found.total).toBe(3);
    expect(found.matches.map((match) => match.ref)).toEqual(["", "", "e1"]);
    expect(found.matches[2].snippet).toContain("Sale price list");
  });

  it("gives the same refs as read, also for elements read numbered before", () => {
    const { document, read, find } = page('<button aria-label="One">One</button>');
    read(0);
    const added = document.createElement("a");
    added.href = "/new";
    added.textContent = "New offer";
    document.body.prepend(added);
    const found = find("offer");
    // read numbered the new link on from 0 here; find names the ref read put on it.
    expect(found.matches[0].ref).toBe(added.getAttribute("data-consens-ref"));
    expect(document.querySelector("button").getAttribute("data-consens-ref")).toBe("e1");
  });

  it("reads text across inline elements, never across blocks, and skips what is hidden", () => {
    const { find } = page(
      '<p>Hel<b>lo</b> World</p><div>Total</div><div>42</div><p style="display:none">secret code</p>' +
        "<script>var hidden = 'code';</script><p>Line<br>break</p>"
    );
    expect(find("hello world").total).toBe(1);
    expect(find("total42").total).toBe(0);
    expect(find("total 42").total).toBe(1);
    expect(find("code").total).toBe(0);
    expect(find("linebreak").total).toBe(0);
    expect(find("line break").total).toBe(1);
  });

  it("lists up to the limit, counts every place, and takes the text as it is", () => {
    const items = Array.from({ length: 30 }, (_, n) => `<button>Item ${n + 1}</button>`).join("");
    const { find } = page(`${items}<p>a+b (x) [y]</p>`);
    const found = find("item");
    expect(found.total).toBe(30);
    expect(found.matches).toHaveLength(20);
    expect(found.matches[0].ref).toBe("e1");
    expect(find("a+b (x) [y]").total).toBe(1);
    expect(find("nothing like it")).toEqual({ total: 0, matches: [] });
  });

  it("shows the page around a place, cut at words", () => {
    const before = "alpha ".repeat(20);
    const after = " omega".repeat(20);
    const { find } = page(`<p>${before}needle${after}</p>`);
    const [match] = find("needle").matches;
    expect(match.snippet.startsWith("…alpha")).toBe(true);
    expect(match.snippet.endsWith("omega…")).toBe(true);
    expect(match.snippet).toContain("alpha needle omega");
    expect(match.snippet.length).toBeLessThan(140);
  });
});
