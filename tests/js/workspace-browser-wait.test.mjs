/**
 * The workspace browser's wait with text (browser.py SHOWS_JS, since
 * 2026-11-03): whether the page in front shows the text. "type e40 Hello
 * enter, wait text Hello" was met at once by the draft itself when Enter
 * had sent nothing (bug hunt P65): what is in the focused editor does not
 * count, only the text elsewhere on the page.
 */
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { JSDOM } from "jsdom";
import { describe, expect, it } from "vitest";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const SOURCE = readFileSync(path.join(ROOT, "app/services/workspace_vm/browser/browser.py"), "utf8");
const SHOWS_JS = SOURCE.match(/SHOWS_JS = r"""\n([\s\S]*?)\n"""/)[1];

function page(body) {
  const dom = new JSDOM(`<!doctype html><html><body>${body}</body></html>`, { runScripts: "outside-only" });
  const { window } = dom;
  // jsdom has no innerText; Chrome's includes an editor's text as the page shows it.
  Object.defineProperty(window.HTMLElement.prototype, "innerText", {
    configurable: true,
    get() {
      return this.textContent;
    },
  });
  return { document: window.document, shows: window.eval(`(${SHOWS_JS})`) };
}

describe("workspace browser wait with text", () => {
  it("finds the text in any case and spacing", () => {
    const { shows } = page("<p>Your order\n  has been   DELIVERED</p>");
    expect(shows("has been delivered")).toBe(true);
    expect(shows("shipped")).toBe(false);
  });

  it("does not count a draft in the focused editor that Enter did not send", () => {
    const { document, shows } = page(
      '<div class="chat"><p>See you then</p></div>' +
        '<div contenteditable="true" tabindex="0" aria-label="Type a message">Hello Anna</div>');
    const editor = document.querySelector("[contenteditable]");
    editor.focus();
    expect(document.activeElement).toBe(editor);
    expect(shows("Hello Anna")).toBe(false);
    expect(shows("see you then")).toBe(true);
    // Sent: the message in the chat, the editor empty and still focused.
    document.querySelector(".chat").insertAdjacentHTML("beforeend", "<p>Hello Anna</p>");
    editor.textContent = "";
    expect(shows("Hello Anna")).toBe(true);
    // Sent once before and the same draft again: it is on the page outside the editor.
    editor.textContent = "Hello Anna";
    expect(shows("hello anna")).toBe(true);
  });

  it("reads an editor without focus as before, a page that is one editor too", () => {
    const { document, shows } = page(
      '<div contenteditable="true"><h1>Meeting notes</h1></div><input value="Hello"><button>Go</button>');
    expect(shows("Meeting notes")).toBe(true);
    // A focused field outside the editor changes nothing (its value is not in the page's text).
    document.querySelector("input").focus();
    expect(shows("Meeting notes")).toBe(true);
    // A page whose body is the editor still shows what it holds.
    document.body.setAttribute("contenteditable", "true");
    document.body.setAttribute("tabindex", "0");
    document.body.focus();
    expect(shows("Meeting notes")).toBe(true);
  });
});
