import { describe, expect, it } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

function boot() {
  return loadScripts([
    "static/vendor/marked/12.0.2/marked.min.js",
    "static/vendor/dompurify/3.4.17/dist/purify.min.js",
    "static/js/markdown-stream.js",
  ]);
}

const ANSWER = [
  "# Plan", "", "Intro paragraph with **bold** text.", "", "- first item", "- second item", "",
  "- loose item after a blank line", "", "```js", "const a = 1;", "", "const b = 2;", "```", "",
  "| A | B |", "|---|---|", "| 1 | 2 |", "", "> quoted", "> still quoted", "", "1. one", "2. two", "",
  "    indented code", "", "Closing sentence.", "",
].join("\n");

function stream(window, document, text, step) {
  const el = document.createElement("div");
  let parsed = 0;
  for (let end = step; end < text.length + step; end += step) {
    parsed += window.renderMarkdownStream(el, text.slice(0, Math.min(end, text.length)));
  }
  return { el, parsed };
}

describe("incremental streamed Markdown", () => {
  it.each([1, 7, 30, 400])("ends identical to a full render when chunks are %i chars", step => {
    const { window, document } = boot();
    const { el } = stream(window, document, ANSWER, step);
    const full = document.createElement("div");
    window.injectMarkdown(full, ANSWER, []);
    expect(el.innerHTML).toBe(full.innerHTML);
  });

  it("parses each finished block once, so work stays linear in the answer length", () => {
    const { window, document } = boot();
    const long = Array.from({ length: 200 }, (_, i) => `Paragraph ${i} with a few words of content.`).join("\n\n") + "\n";
    const { parsed } = stream(window, document, long, 30);
    // Quadratic re-parsing would be ~length^2 / (2 * step), about 1.3M chars here.
    expect(parsed).toBeLessThan(long.length * 5);
  });

  it("shows an opened bold span as bold before its closing asterisks arrive", () => {
    const { window, document } = boot();
    const el = document.createElement("div");
    window.renderMarkdownStream(el, "**Send it, after two");
    expect(el.textContent).not.toContain("*");
    expect(el.querySelector("strong")?.textContent).toBe("Send it, after two");
    window.renderMarkdownStream(el, "**Send it, after two fixes.** Then **");
    expect(el.textContent).not.toContain("*");
    window.renderMarkdownStream(el, "```\nconst a = 2 ** 3;");
    expect(el.textContent).toContain("2 ** 3");
  });

  it("keeps finished nodes stable and starts over when the text does not just grow", () => {
    const { window, document } = boot();
    const el = document.createElement("div");
    window.renderMarkdownStream(el, "First block.\n\nSecond");
    window.renderMarkdownStream(el, "First block.\n\nSecond block.\n\nThird");
    const first = el.firstElementChild;
    window.renderMarkdownStream(el, "First block.\n\nSecond block.\n\nThird block.\n");
    expect(el.firstElementChild).toBe(first);
    window.renderMarkdownStream(el, "Replaced text.");
    expect(el.textContent.trim()).toBe("Replaced text.");
    // Someone else writing into the element invalidates the reuse.
    el.innerHTML = "<p>foreign</p>";
    window.renderMarkdownStream(el, "Replaced text. More.");
    expect(el.textContent).not.toContain("foreign");
  });

  it("sanitizes streamed blocks like a full render", () => {
    const { window, document } = boot();
    const el = document.createElement("div");
    window.renderMarkdownStream(el, "Text ![x](https://evil.example/p) <img src=//evil.example/a>\n\nNext");
    expect(el.querySelector("img")).toBeNull();
    expect(el.innerHTML).not.toContain("evil.example");
  });

  it("gives each streamed block its final inline form before it is shown", () => {
    const { window, document } = boot();
    const el = document.createElement("div");
    const decorate = holder => holder.querySelectorAll("a").forEach(link => link.classList.add("decorated"));
    window.renderMarkdownStream(el, "See [one](https://a.example/).\n\nAnd [two](https://b.example/", { decorate });
    window.renderMarkdownStream(el, "See [one](https://a.example/).\n\nAnd [two](https://b.example/).\n\nMore\n", { decorate });
    window.renderMarkdownStream(el, "See [one](https://a.example/).\n\nAnd [two](https://b.example/).\n\nMore text", { decorate });
    expect(el.querySelectorAll("a")).toHaveLength(2);
    expect([...el.querySelectorAll("a")].every(link => link.classList.contains("decorated"))).toBe(true);
  });

  it("keeps the growing block's nodes, a link in it and a selection in it while it streams", () => {
    const { window, document } = boot();
    const el = document.createElement("div");
    document.body.append(el);
    const text = "See [the pricing page](https://a.example/p) for the plan that suits a team of five, and more words follow here.";
    window.renderMarkdownStream(el, text.slice(0, 60));
    const paragraph = el.querySelector("p");
    const link = el.querySelector("a");
    const words = link.nextSibling;
    expect(words.nodeType).toBe(window.Node.TEXT_NODE);
    const selection = window.getSelection();
    selection.setBaseAndExtent(link.firstChild, 4, words, 5);
    const chosen = selection.toString();
    for (let end = 61; end <= text.length; end += 3) window.renderMarkdownStream(el, text.slice(0, end));
    window.renderMarkdownStream(el, text);
    // Rebuilding the block for every chunk dropped the link under the finger
    // and the selection with it (Apple audit D4).
    expect(el.querySelector("p")).toBe(paragraph);
    expect(el.querySelector("a")).toBe(link);
    expect(link.nextSibling).toBe(words);
    expect(selection.toString()).toBe(chosen);
    expect(el.textContent.trim()).toBe(text.replace("[the pricing page](https://a.example/p)", "the pricing page"));
  });

  it("shows a table that is still streaming as quiet rows, and the table only once it is complete", () => {
    const { window, document } = boot();
    const el = document.createElement("div");
    const head = "Intro.\n\n| Plan | Typical cost | Funding |\n|---|---|---|\n";
    window.renderMarkdownStream(el, `${head}| Small | 20 | none |\n| Lar`);
    // A table growing row by row changed its column widths with every row,
    // so its header slid sideways under the reader's eye (Apple audit A5).
    expect(el.querySelector("table")).toBeNull();
    const pending = el.querySelector(".stream-table-pending");
    expect(pending.getAttribute("aria-hidden")).toBe("true");
    expect(pending.querySelectorAll(".skeleton")).toHaveLength(3);
    window.renderMarkdownStream(el, `${head}| Small | 20 | none |\n| Large | 3,000 | grants |\n`);
    expect(el.querySelector(".stream-table-pending")).toBe(pending);
    expect(pending.querySelectorAll(".skeleton")).toHaveLength(3);
    window.renderMarkdownStream(el, `${head}| Small | 20 | none |\n| Large | 3,000 | grants |\n\nAfter the table.\n`);
    expect(el.querySelector(".stream-table-pending")).toBeNull();
    expect(el.querySelectorAll("table tbody tr")).toHaveLength(2);
    // A pipe inside code is no table.
    const code = document.createElement("div");
    window.renderMarkdownStream(code, "```\n| not | a table |\n");
    expect(code.querySelector(".stream-table-pending")).toBeNull();
  });

  it("renders a fixed text in full into the nodes on screen", () => {
    const { window, document } = boot();
    const el = document.createElement("div");
    const text = "First paragraph with a [link](https://a.example/).\n\n| A | B |\n|---|---|\n| 1 | 2 |";
    window.renderMarkdownStream(el, text);
    const first = el.firstElementChild;
    const link = el.querySelector("a");
    window.morphMarkdown(el, text);
    const full = document.createElement("div");
    window.injectMarkdown(full, text, []);
    expect(el.innerHTML).toBe(full.innerHTML);
    expect(el.firstElementChild).toBe(first);
    expect(el.querySelector("a")).toBe(link);
    expect(window.isPlainMarkdown(el, text)).toBe(true);
  });

  it("never morphs a claim mark into another element, so its listeners go with it", () => {
    const { window, document } = boot();
    const el = document.createElement("div");
    el.innerHTML = '<p><span class="cx-claim is-major" role="button" tabindex="0">Hello</span> world.</p>';
    const paragraph = el.firstChild;
    const mark = paragraph.firstChild;
    window.morphMarkdown(el, "<span>Hello</span> world.");
    expect(el.firstChild).toBe(paragraph);
    expect(el.querySelector("span")).not.toBe(mark);
    expect(el.querySelector("span").getAttribute("role")).toBeNull();
    expect(mark.isConnected).toBe(false);
  });

  it("brings a selection back after the text under it was written anew", () => {
    const { window, document } = boot();
    const el = document.createElement("div");
    document.body.append(el);
    const text = "The tower is **330 m** tall. A ticket costs 29 euros.";
    window.injectMarkdown(el, text, []);
    const selection = window.getSelection();
    const words = el.querySelector("p").lastChild;
    selection.setBaseAndExtent(words, 3, words, 18);
    const chosen = selection.toString();
    window.keepTextSelection(el, () => {
      window.injectMarkdown(el, text, []);
      const badge = document.createElement("button");
      badge.className = "claim-badge";
      badge.textContent = "2/3";
      el.querySelector("p").prepend(badge);
    });
    expect(selection.toString()).toBe(chosen);
    expect(el.contains(selection.anchorNode)).toBe(true);
  });

  it("parses each render once, from DOMPurify's own nodes", () => {
    const { window, document } = boot();
    const descriptor = Object.getOwnPropertyDescriptor(window.Element.prototype, "innerHTML");
    let parses = 0;
    Object.defineProperty(window.Element.prototype, "innerHTML", {
      configurable: true, get: descriptor.get,
      set(value) { parses += 1; descriptor.set.call(this, value); }
    });
    const el = document.createElement("div");
    window.injectMarkdown(el, "Text with **bold** and a [link](https://a.example/).\n\n| A | B |\n|---|---|\n| 1 | 2 |", []);
    window.renderMarkdownStream(document.createElement("div"), "Streaming *text* and more");
    expect(parses).toBe(0);
    expect(el.querySelector("strong")?.textContent).toBe("bold");
    expect(el.querySelector(".markdown-table-wrap table")).not.toBeNull();
  });

  it("never promotes a paragraph to a larger lead once more text follows", () => {
    const { window, document } = boot();
    const el = document.createElement("div");
    el.className = "consensus-answer-body";
    window.renderMarkdownStream(el, "Short first paragraph.\n\nSecond paragraph follows.\n\nThird");
    expect(el.classList.contains("has-lead")).toBe(false);
  });
});
