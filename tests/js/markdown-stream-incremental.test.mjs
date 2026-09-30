import { describe, expect, it } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

function boot() {
  return loadScripts([
    "static/vendor/marked/12.0.2/marked.min.js",
    "static/vendor/dompurify/3.4.16/dist/purify.min.js",
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
});
