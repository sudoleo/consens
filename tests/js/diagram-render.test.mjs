import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

// jsdom imports no module, so Mermaid never loads here: what is drawn is
// tested in a real browser (tests/e2e/test_diagram_render.py). These are the
// parts around the drawing.
function boot(body) {
  return loadScripts(["static/js/diagram-render.js"], { body });
}
const settle = () => new Promise(resolve => setTimeout(resolve, 0));

describe("ConsensusDiagram", () => {
  it("names a place after its source: the same source the same name", () => {
    const { window } = boot();
    const { key } = window.ConsensusDiagram;
    expect(key("flowchart LR\n  A --> B")).toBe(key("flowchart LR\n  A --> B"));
    expect(key("flowchart LR\n  A --> B")).not.toBe(key("flowchart LR\n  A --> C"));
    expect(key("pie\n  \"ä\": 1")).toMatch(/^[0-9a-z]+-[0-9a-z]+$/);
  });

  it("adopts the code block a public page was rendered with", async () => {
    const { window, document } = boot('<main><pre><code class="language-mermaid">pie\n  "a": 1\n</code></pre>'
      + '<pre><code>plain</code></pre></main>');
    window.ConsensusDiagram.render(document);
    const place = document.querySelector(".md-diagram");
    expect(place.dataset.diagram).toBe(window.ConsensusDiagram.key('pie\n  "a": 1'));
    expect(place.querySelector(":scope > pre > code.language-mermaid")).not.toBeNull();
    expect(document.querySelectorAll(".md-diagram")).toHaveLength(1);
    // Until it is drawn: its field, with nothing to open yet.
    expect(place.querySelector(":scope > .md-diagram-figure img").getAttribute("alt")).toBe("");
    // A second look adopts nothing twice.
    window.ConsensusDiagram.render(document);
    expect(document.querySelectorAll(".md-diagram, .md-diagram-figure")).toHaveLength(2);
    await window.ConsensusDiagram.request('pie\n  "a": 1').done;
    await settle();
  });

  it("leaves a block it cannot draw as the code the model wrote", async () => {
    const { window, document } = boot('<div id="a"><pre><code class="language-mermaid">flowchart LR\n  A --> B\n</code></pre></div>');
    window.ConsensusDiagram.render(document);
    await window.ConsensusDiagram.request("flowchart LR\n  A --> B").done;
    await settle();
    const place = document.querySelector("#a .md-diagram");
    expect(place.classList.contains("is-code")).toBe(true);
    expect(place.classList.contains("is-drawn")).toBe(false);
    // The text after it no longer waits.
    expect(window.ConsensusDiagram.settled("flowchart LR\n  A --> B")).toBe(true);
  });

  it("answers once for a source, whatever asks", () => {
    const { window } = boot();
    const { request } = window.ConsensusDiagram;
    expect(request("pie\n  \"a\": 1")).toBe(request("pie\n  \"a\": 1"));
    expect(request("pie\n  \"a\": 1", "dark")).not.toBe(request("pie\n  \"a\": 1", "light"));
    expect(window.ConsensusDiagram.settled("pie\n  \"b\": 2")).toBe(false);
  });

  it("imports the Mermaid folder package.json pins", () => {
    const pins = JSON.parse(readFileSync("package.json", "utf8")).devDependencies;
    const source = readFileSync("static/js/diagram-render.js", "utf8");
    expect(source).toContain(`"/static/vendor/mermaid/${pins.mermaid}/dist/mermaid.esm.min.mjs"`);
  });
});
