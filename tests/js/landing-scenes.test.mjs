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
    expect(log.getAttribute("aria-hidden")).toBe("true");
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
});
