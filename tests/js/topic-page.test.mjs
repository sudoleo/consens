/**
 * topic-page.js -- the check strip readout on public Topic pages (R01).
 *
 * A strip cell's note is a change summary from a model run. Jinja escapes it
 * into data-note, the browser decodes it again for dataset.note, so the
 * readout must insert it as text. Parsing it as HTML would turn model output
 * into markup on a public page.
 */

import { describe, expect, it } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

const HOSTILE = '<img src=x onerror="window.__pwned=1"><span id="injected">not text</span>';

async function boot({ note = HOSTILE, score = "72", hover = true, storage } = {}) {
  const body = [
    '<div class="topic-strip" id="topicStrip" data-slug="gpt-6">',
    '<a class="topic-strip-cell is-first" href="/topics/gpt-6?version=a" data-date="Jul 1" data-iso="2026-07-01" data-kind="first" data-note="First check." data-score="60"></a>',
    '<a class="topic-strip-cell is-material" id="hostile" href="/topics/gpt-6" data-date="Jul 8" data-iso="2026-07-08" data-kind="material"></a>',
    "</div>",
    '<p class="topic-strip-read" id="topicStripRead" role="status">Jul 8 &mdash; resting line</p>',
    '<section class="topic-return" id="topicReturn" hidden></section>',
  ].join("");
  const loaded = loadScripts(["static/js/topic-page.js"], {
    body,
    before(window) {
      const cell = window.document.getElementById("hostile");
      // setAttribute stores exactly what dataset returns after the server's
      // attribute escaping has been decoded by the HTML parser.
      cell.setAttribute("data-note", note);
      cell.setAttribute("data-date", "Jul 8 <b id=\"date-injected\">x</b>");
      if (score !== null) cell.setAttribute("data-score", score);
      window.matchMedia = () => ({ matches: hover });
      if (storage) {
        Object.defineProperty(window, "localStorage", { value: storage, configurable: true });
      }
    },
  });
  // The module starts on DOMContentLoaded, exactly like in the browser.
  if (loaded.document.readyState === "loading") {
    await new Promise(resolve => loaded.document.addEventListener("DOMContentLoaded", resolve));
  }
  return loaded;
}

function readout(document) {
  return document.getElementById("topicStripRead");
}

describe("topic strip readout treats data as text", () => {
  for (const [label, fire] of [
    ["hover", (window, cell) => cell.dispatchEvent(new window.Event("mouseenter"))],
    ["keyboard focus", (window, cell) => cell.dispatchEvent(new window.Event("focus"))],
    ["touch preview", (window, cell) => cell.dispatchEvent(new window.MouseEvent("click", { cancelable: true }))],
  ]) {
    it(`shows HTML-like notes literally on ${label}`, async () => {
      const { window, document } = await boot({ hover: label !== "touch preview" });
      const cell = document.getElementById("hostile");
      fire(window, cell);

      const read = readout(document);
      expect(read.textContent).toContain(HOSTILE);
      expect(document.getElementById("injected")).toBeNull();
      expect(document.getElementById("date-injected")).toBeNull();
      expect(read.querySelector("img")).toBeNull();
      expect(read.querySelectorAll("[onerror]").length).toBe(0);
      expect(window.__pwned).toBeUndefined();
    });
  }

  it("keeps the bold date and the score formatting", async () => {
    const { window, document } = await boot({ note: "The answer moved." });
    document.getElementById("hostile").dispatchEvent(new window.Event("focus"));

    const read = readout(document);
    expect(read.children.length).toBe(2);
    expect(read.querySelector("b").textContent).toBe('Jul 8 <b id="date-injected">x</b>');
    expect(read.querySelector(".topic-strip-score").textContent).toBe("72/100 agreement");
    expect(read.textContent).toBe('Jul 8 <b id="date-injected">x</b> — The answer moved. 72/100 agreement');
  });

  it("omits the score for an unscored cell", async () => {
    const { window, document } = await boot({ note: "Insufficient evidence.", score: null });
    document.getElementById("hostile").dispatchEvent(new window.Event("mouseenter"));
    expect(readout(document).querySelector(".topic-strip-score")).toBeNull();
  });

  it("restores the server-rendered resting line after leaving the strip", async () => {
    const { window, document } = await boot();
    const read = readout(document);
    const resting = read.innerHTML;
    document.getElementById("hostile").dispatchEvent(new window.Event("mouseenter"));
    document.getElementById("topicStrip").dispatchEvent(new window.Event("mouseleave"));
    expect(read.innerHTML).toBe(resting);
    expect(document.getElementById("injected")).toBeNull();
  });

  it("builds the returning-reader band from text, including hostile dates", async () => {
    const store = new Map([["topic-seen:gpt-6", "2026-07-02"]]);
    const storage = {
      getItem: key => (store.has(key) ? store.get(key) : null),
      setItem: (key, value) => store.set(key, String(value)),
    };
    const { document } = await boot({ storage });
    const band = document.getElementById("topicReturn");
    expect(band.hidden).toBe(false);
    expect(band.querySelector(".topic-return-tag").textContent).toBe("Since your last visit");
    expect(band.querySelector('a[href="#facts"]').textContent).toBe("See the statements");
    expect(band.textContent).toContain('the answer moved on Jul 8 <b id="date-injected">x</b>.');
    expect(document.getElementById("date-injected")).toBeNull();
    expect(store.get("topic-seen:gpt-6")).toBe("2026-07-08");
  });
});
