import { describe, expect, it, vi } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

// Each code block of a rendered answer carries a copy button (2026-10-26):
// an icon without text, copied through one listener on the document, so it
// survives the morph of a streamed answer.
const CODE_HTML = "<p>Run this:</p><pre><code>npm ci\nnpm run build\n</code></pre><p>Then <code>ls</code>.</p>";

function boot(clipboard) {
  return loadScripts(["static/js/markdown-stream.js"], {
    before(window) {
      window.marked = { parse: vi.fn(() => CODE_HTML) };
      window.DOMPurify = { sanitize: vi.fn(value => value) };
      Object.defineProperty(window.navigator, "clipboard", { configurable: true, value: clipboard });
    },
  });
}

describe("Copying a code block", () => {
  it("puts one textless copy button on each code block and copies the code without its last newline", async () => {
    const writeText = vi.fn(async () => {});
    const { window, document } = boot({ writeText });
    const output = document.createElement("div");
    document.body.append(output);
    window.injectMarkdown(output, "Run this:");
    const buttons = output.querySelectorAll(".code-copy");
    // Only the block: inline code has none.
    expect(buttons).toHaveLength(1);
    const [button] = buttons;
    expect(button.parentElement.tagName).toBe("PRE");
    expect(button.parentElement.classList.contains("has-copy")).toBe(true);
    expect(button.getAttribute("aria-label")).toBe("Copy code");
    // No words of its own: the answer's text is unchanged.
    expect(button.textContent).toBe("");
    expect(output.textContent).toBe("Run this:npm ci\nnpm run build\nThen ls.");
    button.click();
    await vi.waitFor(() => expect(writeText).toHaveBeenCalledWith("npm ci\nnpm run build"));
    await vi.waitFor(() => expect(button.classList.contains("is-copied")).toBe(true));
    expect(button.getAttribute("aria-label")).toBe("Copied");
    // A second render (a morph keeps its nodes) adds no second button.
    window.morphMarkdown(output, "Run this:");
    expect(output.querySelectorAll(".code-copy")).toHaveLength(1);
  });

  it("says so when the clipboard refuses", async () => {
    const { window, document } = boot({ writeText: vi.fn(async () => { throw new Error("denied"); }) });
    window.App.showPopup = vi.fn();
    const output = document.createElement("div");
    document.body.append(output);
    window.injectMarkdown(output, "Run this:");
    output.querySelector(".code-copy").click();
    await vi.waitFor(() => expect(window.App.showPopup).toHaveBeenCalledWith("Copy to clipboard failed."));
    expect(output.querySelector(".code-copy").classList.contains("is-copied")).toBe(false);
  });

  it("gives the blocks of a streamed answer their button too", () => {
    const { window, document } = boot({ writeText: vi.fn() });
    const output = document.createElement("div");
    window.renderMarkdownStream(output, "Run this:\n\n```\nnpm ci\n```\n\nThen ls.\n");
    expect(output.querySelectorAll("pre > .code-copy").length).toBeGreaterThan(0);
  });
});
