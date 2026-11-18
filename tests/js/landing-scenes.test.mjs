import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import { loadScripts, ROOT } from "./helpers/appWindow.mjs";

// Scene 02 as templates/landing.html builds it, cut down to what the driver
// touches, with the chart its include draws in the answer.
const landing = readFileSync(path.join(ROOT, "templates/landing.html"), "utf8");
const CHART = readFileSync(path.join(ROOT, "templates/partials/demo_chart_mockup.html"), "utf8");
const SCENE = landing.slice(
  landing.indexOf('<div class="lp-scroll-scene" data-scene="run">'),
  landing.indexOf("<!-- ====================================================== DECIDE"),
).replace('{% include "partials/demo_chart_mockup.html" %}', CHART)
  .replace(/\{#[\s\S]*?#\}|\{\{[^}]*\}\}|\{%[^%]*%\}/g, "");

// The composer of scene 01 with the marks its include puts before the words.
const MARKS = readFileSync(path.join(ROOT, "templates/partials/composer_marks_mockup.html"), "utf8");
const ASK = landing.slice(
  landing.indexOf('<div class="lp-scroll-scene" data-scene="ask">'),
  landing.indexOf("<!-- Scene 02 -->"),
).replace('{% include "partials/composer_marks_mockup.html" %}', MARKS)
  .replace(/\{#[\s\S]*?#\}|\{\{[^}]*\}\}|\{%[^%]*%\}/g, "");

// A scene the scroll drives: 1000 px of travel, so scrollY / 1000 is the
// playhead, and one frame per flush(). The comparison label is as wide as its
// wording (a pixel a letter).
async function scrubbed(scene, scrollY) {
  const frames = [];
  const loaded = loadScripts(["static/js/landing-scenes.js"], {
    body: `<section>${scene}</section>`,
    before(window) {
      window.matchMedia = () => ({ matches: false });
      window.requestAnimationFrame = (fn) => frames.push(fn);
      Object.defineProperty(window, "scrollY", { value: scrollY, writable: true, configurable: true });
      const proto = window.HTMLElement.prototype;
      proto.getBoundingClientRect = function () {
        const height = this.classList.contains("lp-scroll-scene") ? 2000 : 0;
        const width = this.matches("[data-run-compare]") ? this.textContent.length : 0;
        return { top: -window.scrollY, left: 0, right: width, bottom: height - window.scrollY, width, height };
      };
      Object.defineProperty(proto, "offsetHeight", {
        configurable: true,
        get() { return this.classList.contains("lp-scene-stage") ? 1000 : 0; },
      });
    },
  });
  const { window, document } = loaded;
  if (document.readyState === "loading") {
    await new Promise((resolve) => document.addEventListener("DOMContentLoaded", resolve));
  }
  const flush = () => frames.splice(0).forEach((fn) => fn(0));
  const scrollTo = (y) => { window.scrollY = y; flush(); };
  flush();
  return { ...loaded, flush, scrollTo };
}

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

describe("landing scene 01", () => {
  // In a chat /app keeps the reviewers' marks before their words; the scene
  // took them away at send and left "2 AIs cross-check" alone in the row.
  it("keeps the reviewers' marks in the field once the question is sent", async () => {
    const { document, scrollTo } = await scrubbed(ASK, 650);
    const marks = document.querySelector(".lp-composer-models");
    expect(marks).not.toBeNull();
    expect(document.querySelector("[data-ask-text]").textContent)
      .toBe("Should we buy the flat we rent, or keep renting and invest the difference?");
    scrollTo(960);
    expect(document.querySelector("[data-ask-send]").classList.contains("is-pressed")).toBe(true);
    expect(marks.className).toBe("lp-composer-models");
  });
});

describe("landing scene 02, scrubbed", () => {
  const LIVE = "Comparing perspectives…";
  const DONE = "Compared perspectives";

  // Held at the width of the longer wording, the finished label stood 40 px
  // short of the model icons after it.
  it("gives the comparison label the width of the wording it shows", async () => {
    const { document, scrollTo } = await scrubbed(SCENE, 400);
    const label = document.querySelector("[data-run-compare]");
    expect(label.textContent).toBe(LIVE);
    expect(label.style.minWidth).toBe(`${LIVE.length}px`);
    scrollTo(560);
    expect(label.textContent).toBe(DONE);
    expect(label.style.minWidth).toBe(`${DONE.length}px`);
    scrollTo(400);
    expect(label.style.minWidth).toBe(`${LIVE.length}px`);
  });

  // Measuring renders the finished turn last. Left there, the card showed
  // "Thought for 17s" with its log folded until the next frame unfolded it.
  it("stands on the reader's frame again after a relayout is measured", async () => {
    const { window, document } = await scrubbed(SCENE, 400);
    const clock = document.querySelector("[data-run-clock]");
    expect(clock.textContent).toBe("Working for 7s");
    window.dispatchEvent(new window.Event("resize"));
    await new Promise((resolve) => window.setTimeout(resolve, 200));
    // No frame has run since the measuring: this is what it left behind.
    expect(clock.textContent).toBe("Working for 7s");
    expect(document.querySelector("[data-run-log]").classList.contains("is-folded")).toBe(false);
    expect(document.querySelector("[data-run-evidence]").classList.contains("is-visible")).toBe(false);
    expect(document.querySelector("[data-run-compare]").textContent).toBe(LIVE);
  });

  // The workspace as /app shows a call in it: the command prints line by
  // line while it runs, and its output folds once it is done.
  it("prints the command's output line by line and folds it when it is done", async () => {
    const { document, scrollTo } = await scrubbed(SCENE, 180);
    const command = document.querySelector('[data-run-item="command"]');
    const output = document.querySelector("[data-run-output]");
    const shown = () => [...document.querySelectorAll("[data-run-line]")].filter((line) => !line.hidden).length;
    expect(document.querySelector('[data-run-item="write"]').textContent.replace(/\s+/g, " ").trim())
      .toBe("Writing the file buy_vs_rent.py");
    expect(command.hidden).toBe(true);
    scrollTo(250);
    expect(command.hidden).toBe(false);
    expect(command.classList.contains("is-current")).toBe(true);
    expect(document.querySelector('[data-run-item="write"]').textContent).toContain("Wrote the file");
    expect(shown()).toBe(3);
    expect(output.classList.contains("is-folded")).toBe(false);
    expect(document.querySelector("[data-run-ran]").hidden).toBe(true);
    scrollTo(310);
    expect(shown()).toBe(5);
    scrollTo(340);
    expect(command.classList.contains("is-current")).toBe(false);
    expect(output.classList.contains("is-folded")).toBe(true);
    expect(document.querySelector("[data-run-ran]").hidden).toBe(false);
  });

  // With the steps open under it, the answer and its chart were taller than
  // a laptop screen: the steps give way to one live row once the agent writes.
  it("folds the steps into the clock line when the answer starts", async () => {
    const { document, scrollTo } = await scrubbed(SCENE, 540);
    const log = document.querySelector("[data-run-log]");
    const row = document.querySelector("[data-run-writing]");
    const status = document.querySelector("[data-run-status]");
    expect(log.classList.contains("is-folded")).toBe(false);
    expect(row.classList.contains("is-open")).toBe(false);
    scrollTo(600);
    expect(log.classList.contains("is-folded")).toBe(true);
    expect(row.classList.contains("is-open")).toBe(true);
    expect(status.textContent).toBe("Writing answer…");
    expect(document.querySelector("[data-run-clock]").textContent).toBe("Working for 11s");
    scrollTo(850);
    expect(status.textContent).toBe("Reviewing the answer…");
    expect(row.classList.contains("is-open")).toBe(true);
    scrollTo(950);
    expect(row.classList.contains("is-open")).toBe(false);
    expect(row.closest("[data-run-log]")).toBeNull();
  });

  // The chart's lines grow with the scroll, and its marks stand once the
  // lines have reached them: the crossing in year 9, the 12 years, the ends.
  it("draws the chart as far as the page has scrolled", async () => {
    const { document, scrollTo } = await scrubbed(SCENE, 590);
    const chart = document.querySelector("[data-run-chart]");
    const marks = () => ["is-crossed", "is-staying", "is-drawn"].filter((name) => chart.classList.contains(name));
    expect(chart.hidden).toBe(true);
    expect(document.querySelector("[data-run-files]").hidden).toBe(true);
    scrollTo(630);
    expect(chart.hidden).toBe(false);
    expect(chart.style.getPropertyValue("--draw")).toBe("0.200");
    expect(marks()).toEqual([]);
    scrollTo(645);
    expect(marks()).toEqual(["is-crossed"]);
    scrollTo(660);
    expect(chart.style.getPropertyValue("--draw")).toBe("0.500");
    expect(marks()).toEqual(["is-crossed", "is-staying"]);
    scrollTo(720);
    expect(chart.style.getPropertyValue("--draw")).toBe("1.000");
    expect(marks()).toEqual(["is-crossed", "is-staying", "is-drawn"]);
    expect(document.querySelector("[data-run-files]").hidden).toBe(false);
    // Scrubbed back, the lines go back.
    scrollTo(630);
    expect(marks()).toEqual([]);
  });

  // "Without the reviewers…" is the page's sentence about the review. It
  // stood in the text the agent streamed, written before any reviewer read it.
  it("keeps the page's own sentence out of the text the agent writes", async () => {
    const { document, scrollTo } = await scrubbed(SCENE, 780);
    const closing = document.querySelector("[data-run-closing]");
    const answer = document.querySelector("[data-run-answer]");
    expect(closing.hasAttribute("data-stream")).toBe(false);
    expect(closing.textContent).toBe("Without the reviewers, an outdated tax rate would have decided it.");
    // The whole answer is written, and the reviewers are not back yet.
    expect([...document.querySelectorAll("[data-stream]")].every((el) => el.textContent.length > 0)).toBe(true);
    expect(answer.classList.contains("is-marked")).toBe(false);
    scrollTo(920);
    expect(answer.classList.contains("is-marked")).toBe(true);
  });
});

describe("landing scene 02 (Apple-Audit I1)", () => {
  it("folds the log into the clock line instead of cutting it out", async () => {
    const { document } = await stillFrame();
    const log = document.querySelector("[data-run-log]");

    expect(document.querySelector("[data-run-clock]").textContent).toBe("Thought for 17s");
    // A hidden log dropped the answer by its whole height in one frame; the
    // fold is a class the stylesheet animates.
    expect(log.hidden).toBe(false);
    expect(log.classList.contains("is-folded")).toBe(true);
    // The live row under the clock has folded with the end of the run.
    expect(document.querySelector("[data-run-writing]").classList.contains("is-open")).toBe(false);
  });

  it("keeps the log items in the one wrapper the fold animates", async () => {
    const { document } = await stillFrame();
    const wrapper = document.querySelector("[data-run-log] > .lp-agent-log-items");
    expect(wrapper).not.toBeNull();
    expect(document.querySelectorAll("[data-run-log] > :not(.lp-agent-log-items)")).toHaveLength(0);
    // Plan, search, workspace, script, command, comparison and its note.
    expect(wrapper.querySelectorAll("[data-run-item]").length).toBe(7);
  });

  // The run shows its search and its workspace in /app's
  // words, and what it shared under the verdict: its chart in the text, the
  // spreadsheet as a file.
  it("shows the search, the workspace and the shared files once done", async () => {
    const { document } = await stillFrame();
    const said = (item) => document.querySelector(`[data-run-item="${item}"]`).textContent.replace(/\s+/g, " ").trim();
    expect(said("search")).toBe("Searched the web · 3 sources: leipzig.de, finanztip.de, homeday.de");
    expect(said("workspace")).toBe("Opened the workspace · Calculate 30 years of buying and renting");
    expect(said("write")).toBe("Wrote the file buy_vs_rent.py");
    expect(said("command")).toContain("python buy_vs_rent.py 2s");
    expect(document.querySelector("[data-run-output]").classList.contains("is-folded")).toBe(true);
    const chart = document.querySelector("[data-run-chart]");
    expect(chart.hidden).toBe(false);
    expect(chart.classList.contains("is-drawn")).toBe(true);
    expect(chart.textContent).toContain("Buying pulls ahead in year 9");
    const files = document.querySelector("[data-run-files]");
    expect(files.hidden).toBe(false);
    expect(files.textContent).toContain("buy-vs-rent.xlsx");
    expect(files.textContent).toContain("Excel · 2 sheets");
    expect(files.textContent).not.toContain("chart.png");
  });

  // The one mode: the reviewers follow beside the clock, their
  // marks are on the answer, and the row under it has Notes and Answers. No
  // score, no judge.
  it("ends on the reviewers' marks and Notes, without a score", async () => {
    const { document } = await stillFrame();
    // The template's loops are cut out here: one mark stands for Daily's two.
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
    expect(row.textContent.replace(/\s+/g, " ").trim()).toBe("Notes 3 Answers 2");
    expect(document.querySelector("[data-run-answer]").classList.contains("is-reviewing")).toBe(false);
    expect(SCENE).not.toMatch(/agreement|\/100|judge|claim-badge/i);
  });

  // The run is a function of the scroll position, so a screen
  // reader read whatever frame the page stood on.
  it("speaks the finished turn to screen readers instead of a frame", async () => {
    const { document } = await stillFrame();
    const words = document.querySelector(".lp-sr");
    expect(document.querySelector("[data-run]").getAttribute("aria-hidden")).toBe("true");
    expect(words.closest("[aria-hidden]")).toBeNull();
    const flat = (text) => text.replace(/\s+/g, " ").trim();
    const said = flat(words.textContent);
    // Every streamed sentence, both notes of the picture and the page's
    // sentence under the answer are in the words.
    const shown = [...document.querySelectorAll("[data-stream], [data-run-closing], .lp-agent-note, .lp-agent-ask")];
    expect(shown.length).toBe(8);
    for (const el of shown) expect(said).toContain(flat(el.textContent));
    expect(said).toContain(document.querySelector("[data-run-clock]").textContent);
    // What the workspace did and what the chart shows, in words.
    expect(said).toContain("Wrote the file buy_vs_rent.py");
    expect(said).toContain("Ran the command python buy_vs_rent.py");
    expect(said).toContain("buying stands at €485k, renting at €379k");
  });
});
