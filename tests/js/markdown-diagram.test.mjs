import { describe, expect, it } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

const FENCE = "```";
const FLOW = "flowchart LR\n  A[Ask] --> B{Search?}";
const block = (source, language = "mermaid") => `${FENCE}${language}\n${source}\n${FENCE}`;

// markdown-stream.js with a stand-in for diagram-render.js: the drawing
// itself needs a browser (tests/e2e/test_diagram_render.py). `drawn` holds
// the sources whose drawing is there.
function boot({ diagrams = true } = {}) {
  const drawn = new Set();
  const calls = { render: 0, warm: [] };
  const env = loadScripts([
    "static/vendor/marked/12.0.2/marked.min.js",
    "static/vendor/dompurify/3.4.17/dist/purify.min.js",
    "static/js/markdown-stream.js",
  ], { before(window) {
    if (!diagrams) return;
    window.ConsensusDiagram = {
      key: source => `k${source.length}`,
      settled: source => drawn.has(source),
      warm: partial => calls.warm.push(partial),
      render(root) {
        calls.render += 1;
        root.querySelectorAll(".md-diagram[data-diagram]").forEach(place => {
          const source = place.querySelector("pre > code").textContent.replace(/\n$/, "");
          if (drawn.has(source)) place.classList.add("is-drawn");
        });
      },
    };
  } });
  return { ...env, drawn, calls };
}

describe("a mermaid block in an answer", () => {
  it("becomes a diagram's place named after its source, with the code inside", () => {
    const { window, document } = boot();
    const el = document.createElement("div");
    window.injectMarkdown(el, `Before\n\n${block(FLOW)}\n\nAfter`, []);
    const place = el.querySelector(".md-diagram");
    expect(place.dataset.diagram).toBe(`k${FLOW.length}`);
    expect(place.hasAttribute("data-open")).toBe(false);
    expect(place.querySelector(":scope > pre > code.language-mermaid").textContent).toBe(`${FLOW}\n`);
    expect([...el.children].map(node => node.tagName)).toEqual(["P", "DIV", "P"]);
  });

  it("is told apart by its language only: other code stays a code block", () => {
    const { window, document } = boot();
    const el = document.createElement("div");
    window.injectMarkdown(el, `${block("const a = 1;", "js")}\n\n${block(FLOW, "Mermaid title")}\n\n${block(FLOW, "mermaidjs")}`, []);
    expect(el.querySelectorAll(".md-diagram")).toHaveLength(1);
    expect(el.querySelectorAll("pre")).toHaveLength(3);
  });

  it("keeps the model's markup in the source as text", () => {
    const { window, document } = boot();
    const el = document.createElement("div");
    const source = 'flowchart LR\n  A["<img src=x onerror=alert(1)>"] --> B';
    window.injectMarkdown(el, block(source), []);
    expect(el.querySelector(".md-diagram img")).toBeNull();
    expect(el.querySelector(".md-diagram code").textContent).toBe(`${source}\n`);
  });

  it("stays a plain code block without diagram-render.js", () => {
    const { window, document } = boot({ diagrams: false });
    const el = document.createElement("div");
    window.injectMarkdown(el, block(FLOW), []);
    expect(el.querySelector(".md-diagram")).toBeNull();
    expect(el.querySelector("pre > code").textContent).toBe(`${FLOW}\n`);
  });

  it("without its closing fence is no diagram: code in a finished answer", () => {
    const { window, document } = boot();
    const el = document.createElement("div");
    window.injectMarkdown(el, `Text\n\n${FENCE}mermaid\n${FLOW}`, []);
    const place = el.querySelector(".md-diagram");
    expect(place.hasAttribute("data-open")).toBe(true);
    expect(place.hasAttribute("data-diagram")).toBe(false);
    expect(place.classList.contains("is-pending")).toBe(false);
  });
});

describe("a diagram in a streamed answer", () => {
  it("is a quiet field while its block is written, and Mermaid loads meanwhile", () => {
    const { window, document, calls } = boot();
    const el = document.createElement("div");
    window.renderMarkdownStream(el, `Intro\n\n${FENCE}mermaid\nflowchart LR\n  A[Ask] -->`);
    const place = el.querySelector(".md-diagram");
    expect(place.classList.contains("is-pending")).toBe(true);
    expect(place.hasAttribute("data-diagram")).toBe(false);
    expect(calls.warm[0]).toContain("flowchart LR");
    // The field's code follows the stream: it is what a cut-off answer shows.
    window.renderMarkdownStream(el, `Intro\n\n${FENCE}mermaid\nflowchart LR\n  A[Ask] --> B`);
    expect(el.querySelector(".md-diagram")).toBe(place);
    expect(place.textContent).toContain("A[Ask] --> B");
  });

  it("holds the text after it until it is drawn, so nothing below it moves", () => {
    const { window, document, drawn } = boot();
    const el = document.createElement("div");
    const text = `Intro\n\n${block(FLOW)}\n\nAfter the diagram.\n\nLast words`;
    window.renderMarkdownStream(el, text);
    expect(el.querySelector(".md-diagram[data-diagram]")).not.toBeNull();
    expect(el.textContent).not.toContain("After the diagram");
    window.renderMarkdownStream(el, `${text} here.`);
    expect(el.textContent).not.toContain("After the diagram");
    drawn.add(FLOW);
    window.renderMarkdownStream(el, `${text} here.`);
    expect(el.textContent).toContain("After the diagram.");
    expect(el.textContent).toContain("Last words here.");
  });

  it("keeps the drawn node through later chunks and the final render", () => {
    const { window, document, drawn } = boot();
    const el = document.createElement("div");
    drawn.add(FLOW);
    const text = `Intro\n\n${block(FLOW)}\n\nAfter`;
    window.renderMarkdownStream(el, text);
    const place = el.querySelector(".md-diagram");
    expect(place.classList.contains("is-drawn")).toBe(true);
    place.append(document.createElement("figure"));
    window.renderMarkdownStream(el, `${text} it.\n\nMore`);
    window.morphMarkdown(el, `${text} it.\n\nMore text.`);
    expect(el.querySelector(".md-diagram")).toBe(place);
    expect(place.querySelector("figure")).not.toBeNull();
    expect(place.classList.contains("is-drawn")).toBe(true);
    // Another source is another diagram: a new place.
    window.morphMarkdown(el, `Intro\n\n${block(`${FLOW}\n  B --> C`)}\n\nAfter`);
    expect(el.querySelector(".md-diagram")).not.toBe(place);
  });

  it("ends like a full render of the same text", () => {
    const { window, document, drawn } = boot();
    drawn.add(FLOW);
    const text = `# Title\n\n${block(FLOW)}\n\nAfter the diagram.\n\n- one\n- two\n`;
    const el = document.createElement("div");
    for (let end = 7; end < text.length + 7; end += 7) window.renderMarkdownStream(el, text.slice(0, end));
    const full = document.createElement("div");
    window.injectMarkdown(full, text, []);
    expect(el.innerHTML).toBe(full.innerHTML);
  });

  it("marks an open block of a model answer's stream too", () => {
    const { window, document } = boot();
    const el = document.createElement("div");
    const renderer = window.createStreamRenderer(el);
    renderer.append(`Intro\n\n${FENCE}mermaid\nflowchart LR`);
    expect(el.querySelector(".md-diagram.is-pending[data-open]")).not.toBeNull();
    renderer.stop();
  });
});
