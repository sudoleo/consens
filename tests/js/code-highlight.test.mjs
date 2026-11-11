import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

// jsdom imports no module, so highlight.js never loads here: the tones are
// tested in a real browser (tests/e2e/test_code_highlight.py). These are the
// parts around them.
function boot(body) {
  return loadScripts(["static/js/code-highlight.js"], { body });
}
const settle = () => new Promise(resolve => setTimeout(resolve, 0));

describe("ConsensusCode", () => {
  it("names a block after its language and code", () => {
    const { window } = boot();
    const { key } = window.ConsensusCode;
    expect(key("python", "print(1)\n")).toBe(key("python", "print(1)\n"));
    expect(key("python", "print(1)\n")).not.toBe(key("ruby", "print(1)\n"));
    expect(key("python", "print(1)\n")).not.toBe(key("python", "print(2)\n"));
    expect(key("c++", "int ä;")).toMatch(/^[0-9a-z]+-[0-9a-z]+$/);
  });

  it("adopts the code blocks a public page was rendered with, but no diagram and no plain block", async () => {
    const { window, document } = boot('<main><pre><code class="language-python">print(1)\n</code></pre>'
      + '<pre><code class="language-mermaid">pie\n</code></pre><pre><code>plain</code></pre></main>');
    // Once, when the page has loaded.
    if (document.readyState === "loading") await new Promise(resolve => document.addEventListener("DOMContentLoaded", resolve));
    await settle();
    const named = document.querySelectorAll("pre[data-code]");
    expect(named).toHaveLength(1);
    expect(named[0].dataset.code).toBe(window.ConsensusCode.key("python", "print(1)\n"));
  });

  it("never names a block itself in the app: one without a name is still being written", async () => {
    const { window, document } = boot();
    await settle();
    const answer = document.createElement("div");
    answer.innerHTML = '<pre><code class="language-python">def f(\n</code></pre>';
    document.body.append(answer);
    window.ConsensusCode.render(answer);
    await settle();
    expect(answer.querySelector("pre").hasAttribute("data-code")).toBe(false);
  });

  it("leaves a block as it is when the library does not arrive", async () => {
    const { window, document } = boot('<pre data-code="k"><code class="language-python">print("&lt;b&gt;")\n</code></pre>');
    window.ConsensusCode.render(document);
    await settle();
    await settle();
    const pre = document.querySelector("pre");
    expect(pre.hasAttribute("data-lit")).toBe(false);
    expect(pre.querySelector("code").innerHTML).toBe('print("&lt;b&gt;")\n');
  });

  it("imports the highlight.js folder package.json pins", () => {
    const pins = JSON.parse(readFileSync("package.json", "utf8")).devDependencies;
    const source = readFileSync("static/js/code-highlight.js", "utf8");
    expect(source).toContain(`"/static/vendor/highlightjs/${pins["@highlightjs/cdn-assets"]}/es/highlight.min.js"`);
  });
});
