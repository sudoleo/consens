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

  it("says its own words in the page's language, inside an answer nothing translates", async () => {
    const german = { "Open diagram": "Diagramm öffnen", Diagram: "Diagramm" };
    const { window, document } = loadScripts(["static/js/diagram-render.js"], {
      body: '<div data-i18n-skip><pre><code class="language-mermaid">pie\n  "a": 1\n</code></pre></div>',
      before(page) { page.App = { t: text => german[text] || text, attachments: { openStored() {} } }; },
    });
    window.ConsensusDiagram.render(document);
    expect(document.querySelector(".md-diagram-open").getAttribute("aria-label")).toBe("Diagramm öffnen");
    await window.ConsensusDiagram.request('pie\n  "a": 1').done;
    await settle();
  });

  it("counts a diagram of an answer being written once, by Mermaid's name for it", async () => {
    const events = [];
    const { window } = loadScripts(["static/js/diagram-render.js"], {
      before(page) { page.trackUmamiEvent = (name, data) => events.push([name, { ...data }]); },
    });
    const { request, settled } = window.ConsensusDiagram;
    // A chat opened later draws without asking the stream's question: no count.
    await request('pie title Costs\n  "a": 1').done;
    await settle();
    expect(events).toEqual([]);
    // The stream asks until the drawing is there; jsdom never loads Mermaid.
    settled("sequenceDiagram\n  A->>B: hi");
    settled("sequenceDiagram\n  A->>B: hi");
    await request("sequenceDiagram\n  A->>B: hi").done;
    await settle();
    settled("sequenceDiagram\n  A->>B: hi");
    expect(events).toEqual([["app_diagram", { kind: "sequence", outcome: "load" }]]);
    // Refused before Mermaid is asked, and counted as that.
    settled('---\ntitle: x\n---\n%%{init: {}}%%\ngraph TD\n  A@{ img: "https://example.invalid/x.png" } --> B');
    await settle();
    expect(events[1]).toEqual(["app_diagram", { kind: "flowchart", outcome: "refused" }]);
    // A first line that names no kind sends none of its words.
    settled(`My secret plan\n${"A --> B\n".repeat(4000)}`);
    await settle();
    expect(events[2]).toEqual(["app_diagram", { kind: "other", outcome: "refused" }]);
    for (const [first, kind] of [["stateDiagram-v2", "state"], ["erDiagram", "er"], ["xychart-beta", "xychart"],
      ["C4Context", "c4"], ["classDiagram", "class"], ["gitGraph", "git"], ["quadrantChart", "quadrant"]]) {
      settled(`${first}\n  A@{ img: "x" }`);
      await settle();
      expect(events.at(-1)[1]).toEqual({ kind, outcome: "refused" });
    }
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
