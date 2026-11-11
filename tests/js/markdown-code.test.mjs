import { describe, expect, it } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

const FENCE = "```";
const block = (code, language = "python") => `${FENCE}${language}\n${code}\n${FENCE}`;

// markdown-stream.js with a stand-in for code-highlight.js: highlight.js
// itself only loads in a browser (tests/e2e/test_code_highlight.py). The
// stand-in marks a block it was given, as the real one does.
function boot({ tones = true } = {}) {
  const calls = { warm: 0 };
  const env = loadScripts([
    "static/vendor/marked/12.0.2/marked.min.js",
    "static/vendor/dompurify/3.4.17/dist/purify.min.js",
    "static/js/markdown-stream.js",
  ], { before(window) {
    if (!tones) return;
    window.ConsensusCode = {
      key: (language, code) => `${language}:${code}`,
      warm() { calls.warm += 1; },
      render(root) {
        root.querySelectorAll("pre[data-code]:not([data-lit])").forEach(pre => { pre.dataset.lit = "true"; });
      },
    };
  } });
  return { ...env, calls };
}

describe("a code block in an answer", () => {
  it("gets a name from its language and code once its fence is closed", () => {
    const { window, document } = boot();
    const el = document.createElement("div");
    window.injectMarkdown(el, `Before\n\n${block("print(1)", "Python title")}\n\nAfter`, []);
    const pre = el.querySelector("pre");
    expect(pre.dataset.code.trim()).toBe("python:print(1)");
    expect(pre.dataset.lit).toBe("true");
    expect(pre.querySelector(":scope > code.language-python").textContent).toBe("print(1)\n");
    // The copy button is the pre's, beside the code.
    expect(pre.querySelector(":scope > .code-copy")).not.toBeNull();
  });

  it("stays as marked writes it without a language, without its closing fence or without the module", () => {
    const { window, document } = boot();
    const el = document.createElement("div");
    window.injectMarkdown(el, `${block("plain", "")}\n\n    indented\n\n${block("x", "a b!c")}\n\n${FENCE}js\nlet a`, []);
    expect(el.querySelectorAll("pre")).toHaveLength(4);
    expect(el.querySelectorAll("pre[data-code]")).toHaveLength(1);
    expect(el.querySelector("pre[data-code] > code").className).toBe("language-a");
    const bare = boot({ tones: false });
    const plain = bare.document.createElement("div");
    bare.window.injectMarkdown(plain, block("print(1)"), []);
    expect(plain.querySelector("pre").hasAttribute("data-code")).toBe(false);
    expect(plain.querySelector("code").className).toBe("language-python");
  });

  it("keeps the model's markup in the code as text", () => {
    const { window, document } = boot();
    const el = document.createElement("div");
    const code = '<img src=x onerror=alert(1)> "quoted" & more';
    window.injectMarkdown(el, block(code, "html"), []);
    expect(el.querySelector("img")).toBeNull();
    expect(el.querySelector("pre[data-code] > code").textContent).toBe(`${code}\n`);
  });

  it("is a diagram, not code to highlight, when its language is mermaid", () => {
    const { window, document } = boot();
    window.ConsensusDiagram = { key: () => "k", render() {}, settled: () => true, warm() {} };
    const el = document.createElement("div");
    window.injectMarkdown(el, block("pie", "mermaid"), []);
    expect(el.querySelector(".md-diagram")).not.toBeNull();
    expect(el.querySelector("pre[data-code]")).toBeNull();
  });
});

describe("a code block in a streamed answer", () => {
  it("is plain text that grows while it is written, and the library loads meanwhile", () => {
    const { window, document, calls } = boot();
    const el = document.createElement("div");
    window.renderMarkdownStream(el, `Intro\n\n${FENCE}python\ndef f():`);
    const open = el.querySelector("pre");
    expect(open.hasAttribute("data-code")).toBe(false);
    expect(calls.warm).toBeGreaterThan(0);
    window.renderMarkdownStream(el, `Intro\n\n${FENCE}python\ndef f():\n    return 1`);
    expect(el.querySelector("pre")).toBe(open);
    expect(open.textContent).toContain("return 1");
  });

  it("keeps its tones through later chunks and the final render", () => {
    const { window, document } = boot();
    const el = document.createElement("div");
    const text = `Intro\n\n${block("def f():\n    return 1")}\n\nAfter`;
    window.renderMarkdownStream(el, text);
    const pre = el.querySelector("pre[data-code]");
    expect(pre.dataset.lit).toBe("true");
    // What code-highlight.js wrote into it stays: the node is not rendered again.
    pre.querySelector("code").innerHTML = '<span class="hljs-keyword">def</span> f():\n    <span class="hljs-keyword">return</span> 1\n';
    window.renderMarkdownStream(el, `${text} it.\n\nMore`);
    window.morphMarkdown(el, `${text} it.\n\nMore text.`);
    expect(el.querySelector("pre[data-code]")).toBe(pre);
    expect(pre.querySelectorAll(".hljs-keyword")).toHaveLength(2);
    // Other code is another block.
    window.morphMarkdown(el, `Intro\n\n${block("def g():\n    return 2")}\n\nAfter`);
    expect(el.querySelector("pre[data-code]")).not.toBe(pre);
    expect(el.querySelector("pre[data-code] code").textContent).toBe("def g():\n    return 2\n");
  });

  it("ends like a full render of the same text", () => {
    const { window, document } = boot();
    const text = `# Title\n\n${block("a = 1\n\nb = 2")}\n\nAfter.\n\n${block("x", "")}\n`;
    const el = document.createElement("div");
    for (let end = 5; end < text.length + 5; end += 5) window.renderMarkdownStream(el, text.slice(0, end));
    const full = document.createElement("div");
    window.injectMarkdown(full, text, []);
    expect(el.innerHTML).toBe(full.innerHTML);
  });
});
