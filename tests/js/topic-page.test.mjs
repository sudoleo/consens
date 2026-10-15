/**
 * topic-page.js -- the follow form on public Topic pages, and
 * check-page.js -- the parts Topic and Watch pages share.
 *
 * The follow form prints a message from the server. It is inserted as text:
 * parsing it as HTML would turn a response into markup on a public page.
 */

import { describe, expect, it } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

const HOSTILE = '<img src=x onerror="window.__pwned=1"><span id="injected">not text</span>';

async function boot(files, body, before) {
  const loaded = loadScripts(files, {
    body,
    before(window) {
      // jsdom does not lay out; the jump to a source still has to run.
      window.Element.prototype.scrollIntoView = () => {};
      before?.(window);
    },
  });
  // The modules start on DOMContentLoaded, exactly like in the browser.
  if (loaded.document.readyState === "loading") {
    await new Promise(resolve => loaded.document.addEventListener("DOMContentLoaded", resolve));
  }
  return loaded;
}

const FOLLOW = [
  '<form id="topicFollowForm" data-slug="gpt 6">',
  '<input id="topicFollowEmail" name="email" type="email" value="reader@example.com">',
  '<button type="submit">Follow</button>',
  "</form>",
  '<p id="topicFollowStatus" role="status" hidden></p>',
].join("");

function respond(ok, payload, calls) {
  return (window) => {
    window.fetch = (url, options) => {
      calls.push({ url, options });
      return Promise.resolve({ ok, json: () => Promise.resolve(payload) });
    };
  };
}

async function submit(window, document) {
  const form = document.getElementById("topicFollowForm");
  form.dispatchEvent(new window.Event("submit", { cancelable: true }));
  // Let the fetch and json promises settle.
  for (let i = 0; i < 5; i += 1) await new Promise(resolve => setTimeout(resolve, 0));
}

describe("topic follow form", () => {
  it("posts the address to the Topic and prints the reply as text", async () => {
    const calls = [];
    const { window, document } = await boot(
      ["static/js/topic-page.js"], FOLLOW, respond(true, { message: HOSTILE }, calls),
    );
    await submit(window, document);

    expect(calls).toHaveLength(1);
    expect(calls[0].url).toBe("/api/topics/gpt%206/follow");
    expect(JSON.parse(calls[0].options.body)).toEqual({ email: "reader@example.com" });
    const status = document.getElementById("topicFollowStatus");
    expect(status.hidden).toBe(false);
    expect(status.textContent).toBe(HOSTILE);
    expect(document.getElementById("injected")).toBeNull();
    expect(window.__pwned).toBeUndefined();
    expect(document.getElementById("topicFollowForm").hidden).toBe(true);
  });

  it("keeps the form and marks an error", async () => {
    const calls = [];
    const { window, document } = await boot(
      ["static/js/topic-page.js"], FOLLOW, respond(false, { detail: "Too many requests." }, calls),
    );
    await submit(window, document);

    const status = document.getElementById("topicFollowStatus");
    expect(status.textContent).toBe("Too many requests.");
    expect(status.classList.contains("is-error")).toBe(true);
    expect(document.getElementById("topicFollowForm").hidden).toBe(false);
    expect(document.querySelector("#topicFollowForm button").disabled).toBe(false);
  });
});

describe("shared check page parts", () => {
  it("folds the source list and opens it for a jump to a source", async () => {
    const items = Array.from({ length: 7 }, (_, i) => `<li id="src-${i + 1}">Source ${i + 1}</li>`).join("");
    const { window, document } = await boot(
      ["static/js/check-page.js"],
      `<ol id="shareSources">${items}</ol><button id="shareSourcesToggle" hidden>Show all</button>`,
    );
    const list = document.getElementById("shareSources");
    const toggle = document.getElementById("shareSourcesToggle");
    expect(list.classList.contains("is-collapsed")).toBe(true);
    expect(toggle.hidden).toBe(false);

    window.location.hash = "#src-6";
    window.dispatchEvent(new window.HashChangeEvent("hashchange"));
    expect(list.classList.contains("is-collapsed")).toBe(false);
    expect(toggle.hidden).toBe(true);
  });

  it("opens a folded group of quiet checks for a link to one of them", async () => {
    const { window, document } = await boot(
      ["static/js/check-page.js"],
      '<details id="group"><summary>3 checks, no change</summary><ul><li id="watch-run-check-2">Jul 2</li></ul></details>',
    );
    expect(document.getElementById("group").open).toBe(false);
    window.location.hash = "#watch-run-check-2";
    window.dispatchEvent(new window.HashChangeEvent("hashchange"));
    expect(document.getElementById("group").open).toBe(true);
  });
});
