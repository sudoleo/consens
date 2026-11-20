import { describe, expect, it } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

// An SVG of an answer drawn as a picture (diagram-render.js). jsdom draws
// no image, so a picture never gets paper here and its look is tested in a
// real browser (tests/e2e/test_diagram_render.py). These are the parts
// around it: what is read, what is cleaned, its size and its place.
const settle = () => new Promise(resolve => setTimeout(resolve, 0));
const ICON = '<svg viewBox="0 0 24 24"><title>Spark</title><path d="M12 2v20M2 12h20" stroke="currentColor"/></svg>';

// jsdom's window has no TextEncoder; every browser the app runs in has one.
function boot({ before, ...options } = {}) {
  return loadScripts(["static/js/diagram-render.js"], { ...options, before(page) {
    page.TextEncoder = TextEncoder;
    before?.(page);
  } });
}

function svgOf(data) {
  return Buffer.from(data, "base64").toString("utf8");
}

describe("an SVG picture", () => {
  it("is told apart by its root, whatever stands before it", () => {
    const { window } = boot();
    const { isSvg } = window.ConsensusDiagram;
    expect(isSvg(ICON)).toBe(true);
    expect(isSvg(`\uFEFF<?xml version="1.0" encoding="UTF-8"?>\n<!-- made by hand -->\n${ICON}`)).toBe(true);
    expect(isSvg(`<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">\n${ICON}`)).toBe(true);
    expect(isSvg("<svg>")).toBe(true);
    expect(isSvg("flowchart LR\n  A --> B")).toBe(false);
    expect(isSvg('<div><svg viewBox="0 0 1 1"></svg></div>')).toBe(false);
    expect(isSvg("<svgx>")).toBe(false);
    // Entities of an internal subset could grow without end: no picture.
    expect(isSvg('<!DOCTYPE svg [<!ENTITY a "aaaa">]><svg>&a;</svg>')).toBe(false);
  });

  it("is drawn at its own size, a small one larger, in the answer's ink", async () => {
    const { window } = boot();
    const { request } = window.ConsensusDiagram;
    const icon = request(ICON, "light");
    await icon.done;
    expect(icon.state).toBe("drawn");
    expect(icon.picture).toMatchObject({ kind: "svg", width: 128, height: 128, title: "Spark" });
    const drawn = svgOf(icon.picture.data);
    expect(drawn).toContain('xmlns="http://www.w3.org/2000/svg"');
    expect(drawn).toMatch(/<svg[^>]* width="128" height="128"/);
    expect(drawn).toContain('color="#0a0a0a"');
    // The file to download is the model's, without the app's size and ink.
    expect(icon.picture.file).not.toContain('width="128"');
    expect(icon.picture.file).not.toContain("color=");
    // A size of its own wins over its viewBox, in any absolute unit.
    const sized = request('<svg width="2in" height="1in" viewBox="0 0 10 5"></svg>', "light");
    await sized.done;
    expect([sized.picture.width, sized.picture.height]).toEqual([192, 96]);
    // Without a viewBox, its own size becomes one, so the picture scales.
    const plain = request('<svg width="400" height="300"><rect width="400" height="300"/></svg>', "light");
    await plain.done;
    expect(svgOf(plain.picture.data)).toContain('viewBox="0 0 400 300"');
    // Far beyond any screen it is drawn smaller, its shape kept.
    const huge = request('<svg viewBox="0 0 20000 10000"></svg>', "light");
    await huge.done;
    expect([huge.picture.width, huge.picture.height]).toEqual([4096, 2048]);
  });

  it("keeps its styles, gradients and filters and loses what could run or load", async () => {
    const { window } = boot();
    const source = '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
      + 'viewBox="0 0 200 100" onload="window.pwned=1" style="width:100%;opacity:.9">'
      + "<style>.glow{filter:url(#neon)}</style>"
      + '<defs><filter id="neon"><feGaussianBlur stdDeviation="4"/></filter>'
      + '<linearGradient id="g"><stop offset="0" stop-color="#0ff"/></linearGradient></defs>'
      + '<rect class="glow" width="200" height="100" fill="url(#g)"/>'
      + "<script>window.pwned=2</script>"
      + '<foreignObject width="10" height="10"><div>html</div></foreignObject>'
      + '<a href="javascript:window.pwned=3"><text x="10" y="50">Neon</text></a>'
      + '<image href="https://leak.test/x.png" width="5" height="5"/>'
      + '<image xlink:href="data:image/png;base64,iVBORw0KGgo=" width="5" height="5"/>'
      + '<use href="#g"/><set attributeName="href" to="javascript:alert(1)"/>'
      + '<animate attributeName="opacity" from="0" to="1" dur="1s"/></svg>';
    const entry = window.ConsensusDiagram.request(source, "dark");
    await entry.done;
    expect(entry.state).toBe("drawn");
    const drawn = svgOf(entry.picture.data);
    for (const kept of ["<style>.glow{filter:url(#neon)}</style>", "<feGaussianBlur", "<linearGradient", 'fill="url(#g)"',
      'href="#g"', "data:image/png;base64", "<animate", "opacity: 0.9"]) {
      expect(drawn, kept).toContain(kept);
    }
    for (const gone of ["<script", "foreignObject", "onload", "javascript:", "leak.test", "<set", "width:100%"]) {
      expect(drawn, gone).not.toContain(gone);
      expect(entry.picture.file, gone).not.toContain(gone);
    }
    // currentColor in the dark is the dark theme's ink.
    expect(drawn).toContain('color="#f5f5f5"');
    expect(window.pwned).toBeUndefined();
  });

  it("stays code when it is not one SVG element, or too much to read", async () => {
    const events = [];
    const { window } = boot({ before(page) { page.trackUmamiEvent = (name, data) => events.push([name, { ...data }]); } });
    const { request, settled } = window.ConsensusDiagram;
    for (const [source, outcome] of [
      ['<svg viewBox="0 0 1 1"></svg><p>and a paragraph</p>', "syntax"],
      ['<svg viewBox="0 0 1 1"><div>html breaks out</div></svg>', "syntax"],
      ['<svg viewBox="0 0 1 1"></svg> and words', "syntax"],
      ['<!DOCTYPE svg [<!ENTITY a "aaaa">]><svg>&a;</svg>', "refused"],
      [`<svg viewBox="0 0 1 1"><!--${"x".repeat(300000)}--></svg>`, "refused"],
    ]) {
      settled(source);
      await request(source).done;
      await settle();
      expect(request(source).state, source.slice(0, 60)).toBe("failed");
      expect(events.at(-1), source.slice(0, 60)).toEqual(["app_diagram", { kind: "svg", outcome }]);
    }
    // Mermaid is never asked for a picture.
    settled(ICON);
    await request(ICON).done;
    await settle();
    expect(events.at(-1)).toEqual(["app_diagram", { kind: "svg", outcome: "drawn" }]);
  });

  it("has its size in its place before it is drawn, and stands as a picture", async () => {
    const { window, document } = boot({
      body: `<div id="a"><div class="md-diagram" data-diagram="x"><pre><code class="language-svg">${ICON.replace(/</g, "&lt;")}\n</code></pre></div></div>`,
    });
    const place = document.querySelector(".md-diagram");
    window.ConsensusDiagram.render(document);
    expect(place.classList.contains("is-picture")).toBe(true);
    expect(place.classList.contains("has-size")).toBe(true);
    expect(place.style.getPropertyValue("--diagram-width")).toBe("128");
    expect(document.querySelector(".md-diagram-open").getAttribute("aria-label")).toBe("Open picture");
    await window.ConsensusDiagram.request(ICON).done;
    await settle();
    expect(place.classList.contains("is-drawn")).toBe(true);
    expect(place.querySelector("img").getAttribute("alt")).toBe("Spark");
  });

  it("gives a field still being written the picture's size once its tag is complete", () => {
    const { window, document } = boot();
    const place = document.createElement("div");
    place.className = "md-diagram";
    window.ConsensusDiagram.warm('<svg viewBox="0 0 400 200" data-note="a > b', place);
    expect(place.classList.contains("is-picture")).toBe(true);
    expect(place.classList.contains("has-size")).toBe(false);
    window.ConsensusDiagram.warm('<svg viewBox="0 0 400 200" data-note="a > b">\n  <rect', place);
    expect(place.style.getPropertyValue("--diagram-width")).toBe("400");
    expect(place.style.getPropertyValue("--diagram-height")).toBe("200");
  });

  it("adopts a public page's svg block and opens in the app's viewer with its code and file", async () => {
    const opened = [];
    const saved = [];
    const copied = [];
    const { window, document } = boot({
      body: `<main><pre><code class="language-svg">${ICON.replace(/</g, "&lt;")}\n</code></pre></main>`,
      before(page) {
        page.App = { attachments: { openStored: att => opened.push(att), save: (blob, name) => saved.push([blob, name]) } };
        Object.defineProperty(page.navigator, "clipboard", { value: { writeText: async text => copied.push(text) } });
      },
    });
    window.ConsensusDiagram.render(document);
    await window.ConsensusDiagram.request(ICON).done;
    await settle();
    document.querySelector(".md-diagram-open").click();
    expect(opened).toHaveLength(1);
    const [att] = opened;
    expect(att).toMatchObject({ name: "spark.svg", title: "Spark", mime: "image/svg+xml", drawing: true });
    expect(att.actions.map(action => action.label)).toEqual(["Copy code", "Download"]);
    await att.actions[0].run();
    expect(copied).toEqual([ICON]);
    att.actions[1].run();
    const [blob, name] = saved[0];
    expect(name).toBe("spark.svg");
    expect(blob.type).toBe("image/svg+xml");
    // jsdom's Blob has no text().
    const text = await new Promise(resolve => {
      const reader = new window.FileReader();
      reader.onload = () => resolve(reader.result);
      reader.readAsText(blob);
    });
    expect(text).toContain("<title>Spark</title>");
    expect(text).not.toContain('width="128"');
  });
});
