/**
 * The DOMPurify copy the app actually ships (R02).
 *
 * The version is read from package.json, so the vendored path under
 * static/vendor cannot drift from the pin, and the vendor regression payloads
 * run against the sanitizer configurations the app really uses: the default
 * one and markdown-stream.js' MODEL_HTML_CONFIG. The last block checks that
 * Markdown, formulas and source anchors still render after the upgrade.
 */

import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import { loadScripts, ROOT } from "./helpers/appWindow.mjs";

const PIN = JSON.parse(readFileSync(path.join(ROOT, "package.json"), "utf8")).devDependencies.dompurify;
const VENDORED = `static/vendor/dompurify/${PIN}/dist/purify.min.js`;

function atLeast(version, minimum) {
  const a = version.split(".").map(Number);
  const b = minimum.split(".").map(Number);
  for (let index = 0; index < 3; index += 1) {
    if (a[index] !== b[index]) return a[index] > b[index];
  }
  return true;
}

function boot(extra = []) {
  return loadScripts([
    "static/vendor/marked/12.0.2/marked.min.js",
    VENDORED,
    ...extra,
  ], { body: '<div id="answer"></div>' });
}

// Mutation-XSS and namespace-confusion payloads from DOMPurify's advisories
// and test suite. None may leave an executable element or handler behind.
const PAYLOADS = [
  '<img src=x onerror=alert(1)>',
  '<svg><p><style><a id="</style><img src=1 onerror=alert(1)>">',
  '<math><mtext><table><mglyph><style><!--</style><img title="--&gt;&lt;/mglyph&gt;&lt;img&Tab;src=1&Tab;onerror=alert(1)&gt;">',
  '<form><math><mtext></form><form><mglyph><style></math><img src onerror=alert(1)>',
  '<svg></p><style><a id="</style><img src=1 onerror=alert(1)>">',
  '<math><mi><table><mi><mglyph><svg><mtext><textarea><path id="</textarea><img onerror=alert(1) src=1>"></path></textarea></mtext></svg></mglyph></mi></table></mi></math>',
  '<noscript><p title="</noscript><img src=x onerror=alert(1)>">',
  '<a href="javascript:alert(1)">x</a>',
  '<iframe srcdoc="<script>alert(1)</script>"></iframe>',
  '<template><script>alert(1)</script></template>',
  '<div id="x"><!--</div><img src=x onerror=alert(1)>-->',
  '<svg><foreignObject><script>alert(1)</script></foreignObject></svg>',
];

function assertInert(document, html) {
  const holder = document.createElement("div");
  holder.innerHTML = html;
  expect(holder.querySelector("script, iframe, object, embed")).toBeNull();
  for (const element of holder.querySelectorAll("*")) {
    for (const attribute of element.attributes) {
      expect(attribute.name.startsWith("on")).toBe(false);
      expect(/^\s*javascript:/i.test(attribute.value)).toBe(false);
    }
  }
}

describe("shipped DOMPurify", () => {
  it("is the pinned, maintained release and not an advisory-affected one", () => {
    const { window } = boot();
    expect(window.DOMPurify.version).toBe(PIN);
    // GHSA-gx9m-whjm-85jf (CVE-2024-47875) affects everything below 3.1.3.
    expect(atLeast(PIN, "3.1.3")).toBe(true);
  });

  it.each(PAYLOADS)("neutralizes %s with the default config", (payload) => {
    const { window, document } = boot();
    assertInert(document, window.DOMPurify.sanitize(payload));
  });

  it.each(PAYLOADS)("neutralizes %s through the model-answer renderer", (payload) => {
    const { window, document } = boot(["static/js/markdown-stream.js"]);
    const output = document.getElementById("answer");
    window.injectMarkdown(output, payload, []);
    assertInert(document, output.innerHTML);
  });

  it("still renders Markdown, formulas and numbered source anchors", () => {
    const { window, document } = boot([
      "node_modules/katex/dist/katex.min.js",
      "node_modules/katex/dist/contrib/auto-render.min.js",
      "static/js/math-render.js",
      "static/js/sources.js",
      "static/js/markdown-stream.js",
    ]);
    const output = document.getElementById("answer");
    window.injectMarkdown(
      output,
      "**Bold** and a list:\n\n- one\n- two\n\nEnergy is $E = mc^2$ here.[S1]",
      [{ id: "S1", url: "https://example.org/Report?key=AbC", title: "Report" }],
    );
    expect(output.querySelector("strong")?.textContent).toBe("Bold");
    expect(output.querySelectorAll("li").length).toBe(2);
    expect(output.querySelector(".katex")).not.toBeNull();
    const anchor = output.querySelector("a.source-link");
    expect(anchor).not.toBeNull();
    expect(anchor.getAttribute("href")).toBe("https://example.org/Report?key=AbC");
  });
});
