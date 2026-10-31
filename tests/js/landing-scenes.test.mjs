import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import { loadScripts, ROOT } from "./helpers/appWindow.mjs";

// Scene 02 as templates/landing.html builds it, cut down to what the driver
// touches.
const landing = readFileSync(path.join(ROOT, "templates/landing.html"), "utf8");
const SCENE = landing.slice(
  landing.indexOf('<div class="lp-scroll-scene" data-scene="run">'),
  landing.indexOf("<!-- ====================================================== DECIDE"),
).replace(/\{\{[^}]*\}\}|\{%[^%]*%\}/g, "");

async function stillFrame() {
  const loaded = loadScripts(["static/js/landing-scenes.js"], {
    body: `<section>${SCENE}</section>`,
    before(window) {
      // Reduced motion renders the finished turn once, as a still frame.
      window.matchMedia = (query) => ({ matches: query.includes("reduce") });
    },
  });
  const { document } = loaded;
  if (document.readyState === "loading") {
    await new Promise((resolve) => document.addEventListener("DOMContentLoaded", resolve));
  }
  return loaded;
}

describe("landing scene 02 (Apple-Audit I1)", () => {
  it("folds the log into the clock line instead of cutting it out", async () => {
    const { document } = await stillFrame();
    const log = document.querySelector("[data-run-log]");

    expect(document.querySelector("[data-run-clock]").textContent).toBe("Thought for 24s");
    // A hidden log dropped the answer by its whole height in one frame; the
    // fold is a class the stylesheet animates.
    expect(log.hidden).toBe(false);
    expect(log.classList.contains("is-folded")).toBe(true);
    // The live row stays inside the folding log, so the fold closes one
    // height instead of losing a row first.
    expect(document.querySelector('[data-run-item="status"]').hidden).toBe(false);
  });

  it("keeps the log items in the one wrapper the fold animates", async () => {
    const { document } = await stillFrame();
    const wrapper = document.querySelector("[data-run-log] > .lp-agent-log-items");
    expect(wrapper).not.toBeNull();
    expect(document.querySelectorAll("[data-run-log] > :not(.lp-agent-log-items)")).toHaveLength(0);
    expect(wrapper.querySelectorAll("[data-run-item]").length).toBe(4);
  });

  // The one mode (2026-10-31): the reviewers follow beside the clock, their
  // marks are on the answer, and the row under it has Notes and Answers. No
  // score, no judge.
  it("ends on the reviewers' marks and Notes, without a score", async () => {
    const { document } = await stillFrame();
    // The template's loops are cut out here: one mark stands for the three.
    const reviewers = [...document.querySelectorAll("[data-reviewer]")];
    expect(reviewers.length).toBeGreaterThan(0);
    expect(reviewers.every((mark) => mark.classList.contains("is-done"))).toBe(true);
    const models = document.querySelectorAll("[data-model]");
    expect(document.querySelectorAll("[data-model].is-done")).toHaveLength(models.length);
    expect(document.querySelector("[data-run-count]").textContent).toBe(`${models.length} answers`);
    // The reviewers beside the clock never count as the AIs the agent asked.
    expect(document.querySelector("[data-reviewer][data-model]")).toBeNull();
    const kinds = [...document.querySelectorAll("[data-mark]")]
      .map((mark) => ["is-major", "is-split", "is-minor"].find((kind) => mark.classList.contains(kind)));
    expect(kinds).toEqual(["is-major", "is-split", "is-minor"]);
    const row = document.querySelector("[data-run-evidence]");
    expect(row.classList.contains("is-visible")).toBe(true);
    expect(row.textContent.replace(/\s+/g, " ").trim()).toBe("Notes 3 Answers 3");
    expect(document.querySelector("[data-run-answer]").classList.contains("is-reviewing")).toBe(false);
    expect(SCENE).not.toMatch(/agreement|\/100|judge|claim-badge/i);
  });

  // a11y audit P2: the run is a function of the scroll position, so a screen
  // reader read whatever frame the page stood on.
  it("speaks the finished turn to screen readers instead of a frame", async () => {
    const { document } = await stillFrame();
    const words = document.querySelector(".lp-sr");
    expect(document.querySelector("[data-run]").getAttribute("aria-hidden")).toBe("true");
    expect(words.closest("[aria-hidden]")).toBeNull();
    const flat = (text) => text.replace(/\s+/g, " ").trim();
    const said = flat(words.textContent);
    // Every streamed sentence and both notes of the picture are in the words.
    const shown = [...document.querySelectorAll("[data-stream], .lp-agent-note, .lp-agent-ask")];
    expect(shown.length).toBe(8);
    for (const el of shown) expect(said).toContain(flat(el.textContent));
    expect(said).toContain(document.querySelector("[data-run-clock]").textContent);
  });
});
