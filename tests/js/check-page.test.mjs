import { describe, expect, it } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

async function boot(body) {
  const loaded = loadScripts(["static/js/check-page.js"], {
    body,
    before(window) {
      window.matchMedia = (query) => ({ matches: query.includes("reduce") });
    },
  });
  if (loaded.document.readyState === "loading") {
    await new Promise((resolve) => loaded.document.addEventListener("DOMContentLoaded", resolve));
  }
  return loaded;
}

const SOURCES = Array.from({ length: 7 }, (_, i) =>
  `<li id="src-${i + 1}"><a class="share-source-title" href="https://s${i + 1}.example/">Source ${i + 1}</a></li>`).join("");

describe("check-page.js after the Apple audit", () => {
  it("lands the focus on the first source that was hidden (L9)", async () => {
    const { document } = await boot(
      `<ol id="shareSources" class="share-sources is-collapsed is-short">${SOURCES}</ol>
       <button id="shareSourcesToggle" class="wp-disclosure-toggle" aria-expanded="false">Show all 7 sources</button>`,
    );
    const toggle = document.getElementById("shareSourcesToggle");
    toggle.focus();
    toggle.click();
    expect(document.getElementById("shareSources").classList.contains("is-collapsed")).toBe(false);
    expect(toggle.getAttribute("aria-expanded")).toBe("true");
    expect(document.activeElement.textContent).toBe("Source 6");
  });

  it("keeps a failed site icon in place as a globe instead of removing it (I7)", async () => {
    const { window, document } = await boot(
      `<ol id="shareSources"><li id="src-1"><img class="share-source-favicon site-icon" src="/api/topics/favicon?d=x.example" width="18" height="18" alt=""><a href="https://x.example/">X</a></li></ol>
       <div class="share-md"><p>Claim.<a href="#src-1">[1]</a></p></div>`,
    );
    const icon = document.querySelector(".share-source-favicon");
    icon.dispatchEvent(new window.Event("error"));
    expect(document.querySelector(".share-source-favicon")).toBe(icon);
    expect(icon.classList.contains("is-missing")).toBe(true);
    expect(icon.getAttribute("src")).toMatch(/^data:image\/svg\+xml,/);
    // The inline citation got its icon and keeps it on failure too.
    const cite = document.querySelector(".share-md .cite-favicon");
    expect(cite).not.toBeNull();
    cite.dispatchEvent(new window.Event("error"));
    expect(document.querySelector(".share-md .cite-favicon")).toBe(cite);
  });

  it("does not unfold the server-folded question to measure it in a visible frame (I2)", async () => {
    const { document } = await boot(
      `<div class="wp-question-wrap"><h1 id="shareQuestion" class="share-question is-clamped">A question</h1>
       <button id="shareQuestionMore" hidden>Show full question</button></div>`,
    );
    const question = document.getElementById("shareQuestion");
    // jsdom has no layout: nothing is cut off, the link stays hidden and the
    // fold stays where the server put it.
    expect(question.classList.contains("is-clamped")).toBe(true);
    expect(document.getElementById("shareQuestionMore").hidden).toBe(true);
  });

  it("marks the check a jump lands on (L14)", async () => {
    const { window, document } = await boot(
      '<ol><li id="watch-run-check-3" class="wp-event">Sep 29</li></ol>',
    );
    window.location.hash = "#watch-run-check-3";
    window.dispatchEvent(new window.HashChangeEvent("hashchange"));
    expect(document.getElementById("watch-run-check-3").classList.contains("is-flash")).toBe(true);
  });
});
