/**
 * The workspace browser's element keys (browser.py KEY_JS):
 * read keeps on each element what it says of itself, an action on its ref
 * compares that first. A list that draws its rows anew (WhatsApp's chats)
 * gives a row's element, ref and all, another row's content; a click on the
 * ref then reached another chat without an error.
 */
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { JSDOM } from "jsdom";
import { describe, expect, it } from "vitest";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const SOURCE = readFileSync(path.join(ROOT, "app/services/workspace_vm/browser/browser.py"), "utf8");
const KEY_JS = SOURCE.match(/\nKEY_JS = r"""\n([\s\S]*?)\n"""/)[1];
const SNAPSHOT_JS = SOURCE.match(/SNAPSHOT_JS = r"""\n([\s\S]*?)\n"""/)[1].replace("%KEY_JS%", KEY_JS);
// browser.py's KEY_CHECK_JS: the key read kept and the key now.
const CHECK_JS = SOURCE.match(/KEY_CHECK_JS = r"""\n([\s\S]*?)\n"""/)[1].replace("%KEY_JS%", KEY_JS);
// browser.py's SHOWN_JS: the elements an answer shows
// take what the snapshot saw of them as their key.
const SHOWN_JS = (SOURCE.match(/\nSHOWN_JS = r"""\n([\s\S]*?)\n"""/) || [])[1];
const REF = /^ *\[(e\d+)\] /;

function page(body) {
  const dom = new JSDOM(`<!doctype html><html><body>${body}</body></html>`, { runScripts: "outside-only" });
  const { window } = dom;
  window.Element.prototype.getBoundingClientRect = () => ({ width: 10, height: 10 });
  Object.defineProperty(window.HTMLElement.prototype, "innerText", {
    configurable: true,
    get() {
      return this.textContent;
    },
  });
  const read = window.eval(`(${SNAPSHOT_JS})`);
  const show = SHOWN_JS ? window.eval(`(${SHOWN_JS})`) : () => {};
  return {
    document: window.document,
    read,
    check: window.eval(`(${CHECK_JS})`),
    show,
    // A read whose answer shows every line it lists (browser.py shown_to_agent).
    look(arg) {
      const result = read(arg);
      const refs = result.lines.map((line) => (line.match(REF) || [])[1]).filter(Boolean);
      show([refs, typeof arg === "number" ? null : arg.step]);
      return result;
    },
  };
}

describe("workspace browser element keys", () => {
  it("keeps what each element says when an answer shows its line", () => {
    const { document, look } = page('<button>Send</button><a href="/inbox" aria-label="Inbox">3</a>');
    expect(look(0).lines).toEqual(['[e1] button "Send"', '[e2] link "Inbox"']);
    expect(document.querySelector("button").getAttribute("data-consens-key")).toBe("BUTTON Send");
    expect(document.querySelector("a").getAttribute("data-consens-key")).toBe("A Inbox");
  });

  it("tells a row the list filled with another chat from the row read listed", () => {
    const { document, look, check } = page(
      '<div role="listbox"><div role="option">Anna Weber</div><div role="option">Ben Kraus</div></div>');
    look(0);
    const [first] = document.querySelectorAll("[role=option]");
    expect(first.getAttribute("data-consens-ref")).toBe("e1");
    expect(check(first)).toEqual(["DIV Anna Weber", "DIV Anna Weber"]);
    // The list scrolls and draws Clara into Anna's element: same ref, other chat.
    first.textContent = "Clara Diaz";
    const [kept, now] = check(first);
    expect(first.getAttribute("data-consens-ref")).toBe("e1");
    expect(kept).not.toBe(now);
    // A new read keeps the ref with the element and its key with what it says now.
    expect(look(2).lines[0]).toBe('[e1] option "Clara Diaz"');
    expect(check(first)).toEqual(["DIV Clara Diaz", "DIV Clara Diaz"]);
  });

  it("leaves out what is typed into a field, so typing never makes its ref stale", () => {
    const { document, look, check } = page(
      '<div contenteditable="true" aria-label="Type a message"></div><div contenteditable="true"></div>' +
        '<input placeholder="Search"><textarea name="note"></textarea>');
    look(0);
    const [labelled, bare] = document.querySelectorAll("[contenteditable]");
    const input = document.querySelector("input");
    const area = document.querySelector("textarea");
    labelled.textContent = "Hello there";
    bare.textContent = "A draft";
    input.value = "anna";
    area.value = "remember the milk";
    for (const field of [labelled, bare, input, area]) {
      const [kept, now] = check(field);
      expect(now).toBe(kept);
    }
    expect(labelled.getAttribute("data-consens-key")).toBe("DIV Type a message");
    expect(input.getAttribute("data-consens-key")).toBe("INPUT Search");
  });

  it("has no key for an element read never listed, which the server then takes as it is", () => {
    const { document, check } = page('<button data-consens-ref="e7">Pay</button>');
    expect(check(document.querySelector("button"))).toEqual([null, "BUTTON Pay"]);
  });

  it("checks a ref within a step against the element as the agent saw it before that step", () => {
    // One step: [type e40 Hallo enter, click e17]. The send moves the chat to
    // the top and the list draws Clara into Anna's row; the snapshot after the
    // type must not make that row's key Clara's.
    const { document, look, check } = page(
      '<div role="listbox"><div role="option">Anna Weber</div><div role="option">Ben Kraus</div></div>');
    look({ start: 0, step: "t.1" });
    const [first] = document.querySelectorAll("[role=option]");
    // The next step, before anything moved: as read saw it.
    expect(check(first, "t.2")).toEqual(["DIV Anna Weber", "DIV Anna Weber"]);
    first.textContent = "Clara Diaz";
    // The snapshot after the step's first call, then the click on the row: stale.
    expect(look({ start: 2, step: "t.2" }).lines[0]).toBe('[e1] option "Clara Diaz"');
    expect(check(first, "t.2")).toEqual(["DIV Anna Weber", "DIV Clara Diaz"]);
    // Another snapshot in the same step keeps it so.
    look({ start: 2, step: "t.2" });
    expect(check(first, "t.2")[0]).toBe("DIV Anna Weber");
    // The step's results showed Clara there: the next step takes her row as it is.
    expect(check(first, "t.3")).toEqual(["DIV Clara Diaz", "DIV Clara Diaz"]);
    look({ start: 2, step: "t.3" });
    expect(check(first, "t.3")).toEqual(["DIV Clara Diaz", "DIV Clara Diaz"]);
    // A call without a step reads the key of the last snapshot, as before.
    first.textContent = "Dora Ruiz";
    look(2);
    expect(check(first)).toEqual(["DIV Dora Ruiz", "DIV Dora Ruiz"]);
  });

  it("keeps a row's key as the agent last saw it while the answers show other lines", () => {
    // The answer after an action shows 4,000 characters
    // of the list (or only what changed), a read 6,000 from its offset. The
    // list drew Clara into Ben's row out of the part shown; the snapshot made
    // Clara that row's key, and the next step's click on e2, meant for Ben,
    // reached Clara without a StaleRef.
    const { document, read, show, look, check } = page(
      '<div role="listbox"><div role="option">Anna Weber</div><div role="option">Ben Kraus</div></div>');
    look({ start: 0, step: "t.1" });
    const [, second] = document.querySelectorAll("[role=option]");
    second.textContent = "Clara Diaz";
    // The step's action: its snapshot lists both rows, its answer shows only e1.
    expect(read({ start: 2, step: "t.2" }).lines[1]).toBe('[e2] option "Clara Diaz"');
    show([["e1"], "t.2"]);
    expect(check(second, "t.3")).toEqual(["DIV Ben Kraus", "DIV Clara Diaz"]);
    expect(check(second, "t.4")).toEqual(["DIV Ben Kraus", "DIV Clara Diaz"]);
    // An answer that shows the row: from the next step on, Clara is its key.
    read({ start: 2, step: "t.4" });
    show([["e2"], "t.4"]);
    expect(check(second, "t.4")).toEqual(["DIV Ben Kraus", "DIV Clara Diaz"]);
    expect(check(second, "t.5")).toEqual(["DIV Clara Diaz", "DIV Clara Diaz"]);
  });

  it("keeps a row's key as the agent last saw it without a step too", () => {
    const { document, read, show, look, check } = page(
      '<div role="listbox"><div role="option">Anna Weber</div><div role="option">Ben Kraus</div></div>');
    look(0);
    const [, second] = document.querySelectorAll("[role=option]");
    second.textContent = "Clara Diaz";
    read(2);
    show([["e1"], null]);
    expect(check(second)).toEqual(["DIV Ben Kraus", "DIV Clara Diaz"]);
    // An element no answer showed has no key yet: the server takes it as it is.
    const fresh = page('<button>Pay</button><button>Cancel</button>');
    fresh.read(0);
    fresh.show([["e1"], null]);
    const [pay, cancel] = fresh.document.querySelectorAll("button");
    expect(fresh.check(pay)).toEqual(["BUTTON Pay", "BUTTON Pay"]);
    expect(fresh.check(cancel)).toEqual([null, "BUTTON Cancel"]);
  });
});
