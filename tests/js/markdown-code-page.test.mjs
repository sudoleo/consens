import { describe, expect, it, vi } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

// A finished ```html block of an answer can be viewed as a page
// (markdown-stream.js pageLine). The line for it stands under the block as
// soon as the block is closed; its button comes with the render of the
// fixed answer. The code goes to the viewer's stage (attachments.js
// showWrittenPage, composer-attachments.test.mjs) and from there to the
// sandboxed document of app/core/html_page.py, never into this page
// (tests/e2e/test_agent_page_sandbox.py runs it in a browser).
const FENCE = "```";
const block = (code, language = "html") => `${FENCE}${language}\n${code}\n${FENCE}`;
const PAGE = `<!doctype html>
<html><head><title>Loan calculator</title>
<link rel="stylesheet" href="https://cdn.example.com/a.css">
<link rel="icon" href="https://cdn.example.com/icon.png">
<style>body { font: 16px system-ui }</style></head>
<body><h1>Loan</h1><img src="data:image/png;base64,AAAA"><img src="chart.png">
<script src="https://cdn.example.com/chart.js"></script>
<script src="https://cdn.example.com/chart.js"></script>
<script>document.title = "ran";</script><a href="https://example.com">a link</a></body></html>`;

function boot() {
  return loadScripts([
    "static/vendor/marked/12.0.2/marked.min.js",
    "static/vendor/dompurify/3.4.17/dist/purify.min.js",
    "static/js/markdown-stream.js",
  ], { before(window) {
    // code-highlight.js names a finished block (data-code) by a hash of it;
    // highlight.js itself only loads in a browser.
    window.ConsensusCode = { key: (language, code) => `${language}-${code.length}`, warm() {}, render() {} };
  } });
}

describe("An HTML block as a page", () => {
  it("offers a finished html block of a fixed answer as a page, and no other block", () => {
    const { window, document } = boot();
    const output = document.createElement("div");
    window.injectMarkdown(output, [`Here it is:`, block(PAGE), `And the script:`, block("print(1)", "python"),
      block("<p>plain</p>", ""), `${FENCE}html\n<p>never closed`].join("\n\n"), []);
    expect(output.querySelectorAll("pre")).toHaveLength(4);
    const lines = output.querySelectorAll(".md-block-tools.md-code-tools");
    expect(lines).toHaveLength(1);
    expect(lines[0].previousElementSibling).toBe(output.querySelector("pre"));
    const button = lines[0].querySelector("button.code-page");
    expect([button.getAttribute("aria-label"), button.dataset.word]).toEqual(["View as page", "View as page"]);
    // The word is drawn from the attribute: the answer's text is the answer.
    expect(lines[0].textContent).toBe("");
  });

  it("keeps the line's place while the answer is written and puts the button there once it is fixed", () => {
    const { window, document } = boot();
    const output = document.createElement("div");
    document.body.append(output);
    const text = `Here it is:\n\n${block(PAGE)}\n\nOpen it.\n`;
    // The block is still being written: nothing says yet what it will be.
    window.renderMarkdownStream(output, text.slice(0, text.indexOf("</body>")));
    expect(output.querySelector(".md-code-tools")).toBeNull();
    // Its fence closed, the answer goes on: the line stands, without a button.
    window.renderMarkdownStream(output, text.slice(0, text.indexOf("Open") + 2));
    const line = output.querySelector(".md-code-tools");
    const pre = output.querySelector("pre[data-code]");
    expect(line.previousElementSibling).toBe(pre);
    expect(line.childElementCount).toBe(0);
    window.renderMarkdownStream(output, text);
    expect(output.querySelector(".md-code-tools")).toBe(line);
    expect(output.querySelector(".code-page")).toBeNull();
    const after = output.querySelector("pre[data-code] ~ p");
    // The fixed answer: the same nodes, and the button in the line.
    window.morphMarkdown(output, text);
    expect([output.querySelector("pre[data-code]"), output.querySelector(".md-code-tools"), output.querySelector("pre[data-code] ~ p")])
      .toEqual([pre, line, after]);
    expect(line.querySelectorAll("button.code-page")).toHaveLength(1);
    window.morphMarkdown(output, text);
    expect(output.querySelectorAll(".md-code-tools")).toHaveLength(1);
    expect(output.querySelectorAll(".code-page")).toHaveLength(1);
  });

  it("opens the code on the viewer's stage, with the page's title and what it asks for elsewhere", () => {
    const { window, document } = boot();
    const openStored = vi.fn();
    window.App.attachments = { openStored };
    const output = document.createElement("div");
    document.body.append(output);
    window.injectMarkdown(output, `${block(PAGE)}\n\n${block("<p>Hello <b>you</b></p>")}`, []);
    const [first, second] = output.querySelectorAll(".code-page");
    first.click();
    expect(openStored).toHaveBeenCalledTimes(1);
    // The stylesheet, the picture beside the page and the script (once): the
    // icon, the picture inside the file and the link load nothing here.
    expect(openStored.mock.calls[0][0]).toEqual({ name: "page.html", title: "Loan calculator", mime: "text/html",
      htmlSource: `${PAGE}\n`, outside: 3 });
    // Reading it ran nothing of it.
    expect(document.title).toBe("");
    second.click();
    expect(openStored.mock.calls[1][0]).toMatchObject({ title: "Page", htmlSource: "<p>Hello <b>you</b></p>\n", outside: 0 });
  });
});
