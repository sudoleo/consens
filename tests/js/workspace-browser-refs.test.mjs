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

  // DeepSeek, 2026-10-28: a Wikipedia read was mostly navigation. The main
  // content comes first now, the rest after a line, all of it still there.
  it("lists the main content first and the header and navigation after it", () => {
    const { read, find } = page(
      '<header><a href="/">Home</a></header><nav><a href="/a">Menu A</a></nav>' +
        '<main><h1>Paris 2024</h1><a href="/t">Triathlon</a></main><footer><a href="/i">Imprint</a></footer>'
    );
    const { lines } = read(0);
    expect(lines).toEqual(['heading "Paris 2024"', '[e3] link "Triathlon"',
      "(outside the main content: header, navigation, footer)",
      '[e1] link "Home"', '[e2] link "Menu A"', '[e4] link "Imprint"']);
    // Refs stay in page order and find names them as before.
    expect(find("Menu").matches[0].ref).toBe("e2");
  });

  it("leaves a page without a main region in page order", () => {
    const { read } = page('<nav><a href="/a">Menu</a></nav><a href="/b">Body</a>');
    expect(read(0).lines).toEqual(['[e1] link "Menu"', '[e2] link "Body"']);
  });

  // 2026-10-30, bild.de: the consent dialog's "Alle akzeptieren" stood 600
  // lines down, after the page it covered, and it was a frame read said only
  // "open its address" of.
  it("lists what lies over the page first, and marks each frame with its size for page_lines", () => {
    const { window, document, read } = page(
      '<main><h1>News</h1><a href="/a">Story</a></main>' +
      '<div id="layer" style="position: fixed"><button>Alle akzeptieren</button>' +
      '<iframe src="https://cmp.example/consent"></iframe></div>');
    document.elementFromPoint = () => document.querySelector("#layer button");
    window.getComputedStyle = new Proxy(window.getComputedStyle, {
      apply: (target, self, [el]) => el.id === "layer" ? { position: "fixed", visibility: "visible", display: "block" }
        : Reflect.apply(target, window, [el]),
    });
    const { lines } = read(0);
    expect(lines).toEqual(["(over the page:)", '[e2] button "Alle akzeptieren"',
      "frame f1 10x10 https://cmp.example/consent", "(the page under it:)", 'heading "News"', '[e1] link "Story"']);
    expect(document.querySelector("iframe").getAttribute("data-consens-frame")).toBe("f1");
  });
});

// HIT_JS (since 2026-10-30): what a click or drag at x,y met and what changed
// after it. jsdom lays nothing out: each element's box and what lies at a
// point are given here, as Chrome would measure them.
const HIT_JS = SOURCE.match(/HIT_JS = r"""\n([\s\S]*?)\n"""/)[1];

function board(body, boxes, at) {
  const { window, document, read } = page(body);
  window.Element.prototype.getBoundingClientRect = function () {
    const [left, top, right, bottom] = boxes.get(this) || [0, 0, 0, 0];
    return { left, top, right, bottom, width: right - left, height: bottom - top };
  };
  document.elementFromPoint = (x, y) => at(x, y);
  return { window, document, read, hit: window.eval(`(${HIT_JS})`) };
}

describe("workspace browser hits", () => {
  const body =
    '<div id="board" class="board"><div class="piece wn square-21"></div><div class="piece bp square-33"></div>' +
    '<div class="square-11"></div></div><div class="clock"><span class="clock-time">9:41</span></div>' +
    '<button aria-label="Resign">x</button>';

  function setUp() {
    const boxes = new Map();
    const { window, document, read, hit } = board(body, boxes, (x, y) =>
      x < 600 && y < 600 ? document.querySelector(".square-21") : document.querySelector("button"));
    const [boardEl, knight, pawn, square] = document.querySelectorAll("#board, .piece, .square-11");
    boxes.set(boardEl, [0, 0, 600, 600]).set(knight, [75, 525, 150, 600]).set(pawn, [150, 375, 225, 450])
      .set(square, [0, 525, 75, 600]).set(document.querySelector(".clock-time"), [700, 0, 760, 20])
      .set(document.querySelector("button"), [700, 650, 740, 690]);
    return { window, document, read, hit, boxes, knight, pawn };
  }

  it("says what lies at each point, its box and the element around it with a box of its own", () => {
    const { read, hit } = setUp();
    read(0);
    const { view, at } = hit({ mode: "before", points: [[100, 550], [720, 670], [5000, 10]], limit: 5 });
    expect(view).toEqual([1024, 768]);
    expect(at[0]).toEqual({ tag: "div.piece.wn.square-21", name: "", ref: "", box: [75, 525, 150, 600],
      drawn: false, in: { tag: "div#board.board", name: "", ref: "", box: [0, 0, 600, 600], drawn: false } });
    // An element read listed comes with its ref; a point outside the view meets nothing.
    expect(at[1]).toMatchObject({ tag: "button", name: "Resign", ref: "e1", box: [700, 650, 740, 690] });
    expect(at[2]).toBeNull();
  });

  it("lists what changed after it, nearest to its points first, and only that", () => {
    const { window, document, read, hit, boxes, knight, pawn } = setUp();
    hit({ mode: "before", points: [[100, 550], [180, 400]], limit: 5 });
    pawn.remove();
    knight.className = "piece wn square-33";
    boxes.set(knight, [150, 375, 225, 450]);
    const mark = document.createElement("div");
    mark.className = "highlight square-21";
    boxes.set(mark, [75, 525, 150, 600]);
    document.getElementById("board").append(mark);
    document.querySelector(".clock-time").textContent = "9:40";
    // Not a change of the page: read's own mark, and what came and went again.
    read(0);
    const flash = document.createElement("div");
    document.body.append(flash);
    flash.remove();
    const report = hit({ mode: "after", points: [[100, 550], [180, 400]], limit: 5 });
    expect(report.count).toBe(4);
    expect(report.changed.map((item) => [item.tag, item.how])).toEqual([
      ["div.piece.wn.square-33", "class"], ["div.highlight.square-21", "new"], ["span.clock-time", "text"]]);
    expect(report.removed.map((item) => item.tag)).toEqual(["div.piece.bp.square-33"]);
    // Asked once: the watch is gone with it, as after the page loaded anew.
    expect(hit({ mode: "after", points: [[100, 550]], limit: 5 })).toBeNull();
    expect(window.__consensHit).toBeUndefined();
  });

  it("names an element whose properties a form's fields shadow, never failing the look", () => {
    const boxes = new Map();
    const { document, hit } = board('<form id="f"><input name="tagName"><input name="getAttribute"></form>', boxes,
      () => document.getElementById("f"));
    boxes.set(document.getElementById("f"), [0, 0, 300, 100]);
    const { at } = hit({ mode: "before", points: [[10, 10]], limit: 5 });
    // Chrome lets the fields shadow the form's own; jsdom does not.
    expect(["form#f", "element"]).toContain(at[0].tag);
    expect(hit({ mode: "after", points: [[10, 10]], limit: 5 }).count).toBe(0);
  });

  it("counts every changed element once on a busy page and lists only the limit", () => {
    const { document, hit } = setUp();
    const many = Array.from({ length: 600 }, () => document.body.appendChild(document.createElement("i")));
    hit({ mode: "before", points: [[100, 550]], limit: 2 });
    for (let round = 0; round < 3; round += 1) for (const item of many) item.dataset.tick = String(round);
    const report = hit({ mode: "after", points: [[100, 550]], limit: 2 });
    expect(report.count).toBe(600);
    expect(report.changed).toHaveLength(2);
  });
});
