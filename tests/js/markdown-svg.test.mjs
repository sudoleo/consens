import { describe, expect, it } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

const FENCE = "```";
const ICON = '<svg viewBox="0 0 24 24">\n  <path d="M12 2v20" stroke="currentColor"/>\n</svg>';
const block = (source, language = "svg") => `${FENCE}${language}\n${source}\n${FENCE}`;

// markdown-stream.js with a stand-in for diagram-render.js (the drawing:
// tests/js/diagram-svg.test.mjs). `drawn` holds the sources whose picture
// is there.
function boot({ diagrams = true } = {}) {
  const drawn = new Set();
  const calls = { warm: [] };
  const env = loadScripts([
    "static/vendor/marked/12.0.2/marked.min.js",
    "static/vendor/dompurify/3.4.17/dist/purify.min.js",
    "static/js/markdown-stream.js",
  ], { before(window) {
    if (!diagrams) return;
    window.ConsensusDiagram = {
      key: source => `k${source.length}`,
      isSvg: source => /^\s*(?:<\?xml[^>]*\?>\s*)?<svg[\s>]/.test(source),
      settled: source => drawn.has(source),
      warm: (partial, place) => calls.warm.push([partial, place]),
      render(root) {
        root.querySelectorAll(".md-diagram[data-diagram]").forEach(place => {
          const source = place.querySelector("pre > code").textContent.replace(/\n$/, "");
          if (drawn.has(source)) place.classList.add("is-drawn");
        });
      },
    };
  } });
  return { ...env, drawn, calls };
}

function render(window, document, text) {
  const el = document.createElement("div");
  window.injectMarkdown(el, text, []);
  return el;
}

describe("an SVG in an answer", () => {
  it("becomes a picture's place named after its source, with the code inside", () => {
    const { window, document } = boot();
    const el = render(window, document, `Before\n\n${block(ICON)}\n\nAfter`);
    const place = el.querySelector(".md-diagram");
    expect(place.dataset.diagram).toBe(`k${ICON.length}`);
    expect(place.querySelector(":scope > pre > code.language-svg").textContent).toBe(`${ICON}\n`);
    expect([...el.children].map(node => node.tagName)).toEqual(["P", "DIV", "P"]);
  });

  it("is an ```xml block or one without a language only when its code is an <svg> element", () => {
    const { window, document } = boot();
    const prolog = `<?xml version="1.0" encoding="UTF-8"?>\n${ICON}`;
    const el = render(window, document, [block(prolog, "xml"), block(ICON, ""), block("<note>no</note>", "xml"),
      block(ICON, "html"), block("const a = 1;", ""), `    ${ICON.replace(/\n/g, "\n    ")}`].join("\n\n"));
    const places = [...el.querySelectorAll(".md-diagram")];
    expect(places.map(place => place.querySelector("code").textContent)).toEqual([`${prolog}\n`, `${ICON}\n`]);
    // A page's markup stays code (HTML is what was asked for), and so does an
    // indented block, whatever it holds.
    expect(el.querySelectorAll("pre")).toHaveLength(6);
  });

  it("standing in the text, is the whole element, also across blank lines and nested <svg>", () => {
    const { window, document } = boot();
    const source = '<svg viewBox="0 0 10 10">\n  <style>.a { fill: red }</style>\n\n  <svg x="2"><rect/></svg>\n\n  <circle r="2"/>\n</svg>';
    const el = render(window, document, `Here it is:\n${source}\nAnd after it.\n\nA sentence with <svg></svg> inside stays.`);
    const places = el.querySelectorAll(".md-diagram");
    expect(places).toHaveLength(1);
    expect(places[0].querySelector("code").textContent).toBe(`${source}\n`);
    expect(el.textContent).toContain("Here it is:");
    expect(el.textContent).toContain("And after it.");
    // Nothing of the element is markup in the page.
    expect(el.querySelector("circle, style")).toBeNull();
  });

  it("leaves the words after it on its line as the paragraph below the picture", () => {
    // tests/test_answer_assets.py reads the same text on the share page.
    const { window, document } = boot();
    const source = '<svg width="10" height="10"><circle r="5"/></svg>';
    const el = render(window, document, `${source} **Online**\nNext line.`);
    expect(el.querySelector(".md-diagram code").textContent).toBe(`${source}\n`);
    expect([...el.children].map(node => node.tagName)).toEqual(["DIV", "P", "P"]);
    expect(el.children[1].innerHTML).toBe("<strong>Online</strong>");
    expect(el.children[2].textContent).toBe("Next line.");
  });

  it("is no picture in a finished text that never closes it: its paragraph stays text", () => {
    const { window, document } = boot();
    const el = render(window, document, '<svg viewBox="0 0 1 1"> opens here\nand <b>is</b> text.\n\n## Then a heading\n\n- and a list');
    expect(el.querySelector(".md-diagram, pre, svg, b")).toBeNull();
    expect(el.querySelector("p").textContent).toBe('<svg viewBox="0 0 1 1"> opens here\nand <b>is</b> text.');
    expect(el.querySelector("h2").textContent).toBe("Then a heading");
    expect(el.querySelector("li").textContent).toBe("and a list");
  });

  it("stays markup the sanitizer cleans without diagram-render.js", () => {
    const { window, document } = boot({ diagrams: false });
    const el = render(window, document, block(ICON));
    expect(el.querySelector(".md-diagram")).toBeNull();
    expect(el.querySelector("pre > code").textContent).toBe(`${ICON}\n`);
  });
});

describe("an SVG in a streamed answer", () => {
  it("is a quiet field of its own while it is written, fenced or not", () => {
    const { window, document, calls } = boot();
    const el = document.createElement("div");
    window.renderMarkdownStream(el, `Intro\n\n${FENCE}svg\n<svg viewBox="0 0 400 200">\n  <rect`);
    const place = el.querySelector(".md-diagram");
    expect(place.classList.contains("is-pending")).toBe(true);
    expect(calls.warm.at(-1)).toEqual([`<svg viewBox="0 0 400 200">\n  <rect\n`, place]);
    const bare = document.createElement("div");
    window.renderMarkdownStream(bare, 'Intro\n\n<svg viewBox="0 0 400 200">\n  <rect width="4"/>\n\n  <circle');
    expect(bare.querySelectorAll(".md-diagram.is-pending[data-open]")).toHaveLength(1);
    // The blank line inside does not end it: the rest is its code, not a paragraph.
    expect([...bare.children].map(node => node.tagName)).toEqual(["P", "DIV"]);
    expect(bare.querySelector(".md-diagram code").textContent).toContain("<circle");
  });

  it("holds the text after it until it is drawn, so nothing below it moves", () => {
    const { window, document, drawn } = boot();
    const el = document.createElement("div");
    const text = `Intro\n\n${ICON}\n\nAfter the picture.`;
    window.renderMarkdownStream(el, text);
    expect(el.querySelector(".md-diagram[data-diagram]")).not.toBeNull();
    expect(el.textContent).not.toContain("After the picture");
    drawn.add(ICON);
    window.renderMarkdownStream(el, `${text} Done.`);
    expect(el.textContent).toContain("After the picture. Done.");
  });

  it("ends like a full render of the same text", () => {
    const { window, document, drawn } = boot();
    drawn.add(ICON);
    const text = `# Logo\n\n${block(ICON)}\n\nAnd raw:\n\n${ICON}\n\n- one\n- two\n`;
    const el = document.createElement("div");
    for (let end = 5; end < text.length + 5; end += 5) window.renderMarkdownStream(el, text.slice(0, end));
    const full = document.createElement("div");
    window.injectMarkdown(full, text, []);
    expect(el.innerHTML).toBe(full.innerHTML);
  });
});
