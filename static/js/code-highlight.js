// =====================================================================
// code-highlight.js
// Syntax tones in an answer's code blocks, in the app (markdown-stream.js
// names each finished block with a language: pre[data-code]) and on public
// pages (the server's code block, adopted here). The look is
// code-highlight.css: the page's two tones and its green, no theme of its own.
// highlight.js comes from static/vendor, imported when an answer first holds
// such a block (its 36 common languages, 44 KB compressed).
// Export: window.ConsensusCode.{key, render, warm}.
// =====================================================================

(function initConsensusCode() {
  "use strict";

  const ENTRY = "/static/vendor/highlightjs/11.12.0/es/highlight.min.js";
  // Longer blocks stay plain: highlighting runs in the frame that shows them.
  const MAX_CODE_CHARS = 60000;

  // FNV-1a over language and code: the name of a block. The same block in
  // the next render is the same node (markdown-stream.js keeps it) and is
  // read once.
  function key(language, code) {
    const text = `${language}\n${code}`;
    let hash = 0x811c9dc5;
    for (let index = 0; index < text.length; index += 1) {
      hash ^= text.charCodeAt(index);
      hash = Math.imul(hash, 0x01000193);
    }
    return `${(hash >>> 0).toString(36)}-${text.length.toString(36)}`;
  }

  let highlighter = null;
  let library = null;
  function load() {
    if (!library) {
      library = import(ENTRY).then(module => { highlighter = module.default; });
      // A failed download may be tried again by the next block.
      library.catch(() => { library = null; });
    }
    return library;
  }

  function languageOf(code) {
    const name = Array.from(code.classList).find(entry => entry.startsWith("language-"));
    return name ? name.slice("language-".length) : "";
  }

  // highlight.js writes the code's own text, escaped, in <span class="…">.
  // Anything else is not its output and is not shown.
  function tones(markup, text) {
    const template = document.createElement("template");
    template.innerHTML = markup;
    for (const element of template.content.querySelectorAll("*")) {
      if (element.localName !== "span" || Array.from(element.attributes).some(attribute => attribute.name !== "class")) return null;
    }
    // Copying a block and the marks on an answer read the code's text: it
    // has to be the same letter for letter.
    return template.content.textContent === text ? template.content : null;
  }

  // data-lit says a block has been read: "true" with its tones, "plain"
  // when its language is none highlight.js knows or it is too long.
  function paint(pre) {
    const code = pre.querySelector(":scope > code");
    if (!code || pre.dataset.lit) return;
    const language = languageOf(code);
    const text = code.textContent;
    let content = null;
    if (language && text.length <= MAX_CODE_CHARS && highlighter.getLanguage(language)) {
      try {
        content = tones(highlighter.highlight(text, { language, ignoreIllegals: true }).value, text);
      } catch (_) { /* A grammar that fails leaves the block as it is. */ }
    }
    if (content) code.replaceChildren(content);
    pre.dataset.lit = content ? "true" : "plain";
  }

  // A public page's code blocks come from the server, finished and without
  // a name: they get theirs once, when the page has loaded. Never in the
  // app, where a block without a name is one still being written.
  function adopt(root) {
    root.querySelectorAll('pre:not([data-code]) > code[class*="language-"]').forEach(code => {
      const language = languageOf(code);
      if (language && language !== "mermaid") code.parentElement.dataset.code = key(language, code.textContent);
    });
  }

  function render(root) {
    if (!root || !root.querySelectorAll) return;
    const waiting = Array.from(root.querySelectorAll("pre[data-code]:not([data-lit])"));
    if (!waiting.length) return;
    if (highlighter) waiting.forEach(paint);
    else load().then(() => waiting.forEach(paint), () => {});
  }

  // A block is still being written: the library loads meanwhile, so the
  // finished block gets its tones in the frame that shows it.
  function warm() {
    load().catch(() => {});
  }

  window.ConsensusCode = { key, render, warm };

  const start = () => {
    adopt(document);
    render(document);
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
