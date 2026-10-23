import { describe, expect, it, vi } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

// A browser with the CSS Custom Highlight API, a clock the test moves and
// animation frames it runs, so the pace is deterministic.
function boot({ highlights = true, reduced = false, letters } = {}) {
  const frames = [];
  let clock = 1000;
  const loaded = loadScripts([
    // Settings > Display > Letter animations, when the test sets it.
    ...(letters === undefined ? [] : ["static/js/user-settings.js"]),
    "static/vendor/marked/12.0.2/marked.min.js",
    "static/vendor/dompurify/3.4.17/dist/purify.min.js",
    "static/js/markdown-stream.js",
    "static/js/stream-reveal.js",
  ], {
    body: '<div id="answer"></div>',
    before(window) {
      if (highlights) {
        window.Highlight = class extends window.Set {};
        window.CSS = { highlights: new Map() };
        window.CSSStyleSheet = class { constructor() { this.rules = []; } insertRule(rule) { this.rules.push(rule); return this.rules.length - 1; } };
        Object.defineProperty(window.document, "adoptedStyleSheets", { value: [], writable: true, configurable: true });
      }
      window.matchMedia = query => ({ matches: reduced && query.includes("reduce"), addEventListener() {} });
      if (letters !== undefined) window.localStorage.setItem("consensio.letterAnimations.v1", String(letters));
      window.performance.now = () => clock;
      window.requestAnimationFrame = fn => frames.push(fn);
    },
  });
  const { window, document } = loaded;
  const run = ms => {
    for (let spent = 0; spent < ms; spent += 16) {
      clock += 16;
      frames.splice(0).forEach(frame => frame(clock));
    }
  };
  const el = document.getElementById("answer");
  const painted = [];
  const paint = text => { painted.push(text); window.renderMarkdownStream(el, text); };
  const unseen = () => [...window.CSS.highlights.entries()]
    .filter(([name]) => name.endsWith("-0")).reduce((sum, [, ranges]) => sum + ranges.size, 0);
  const lit = () => [...window.CSS.highlights.values()].reduce((sum, ranges) => sum + ranges.size, 0);
  return { ...loaded, reveal: window.App.streamReveal, el, painted, paint, run, unseen, lit };
}

const ANSWER = "Yes. For most adults, a brisk 30-minute walk on most days lowers blood pressure by a small "
  + "but real amount, about 4 to 5 mmHg systolic. The strongest evidence comes from a 2023 meta-analysis.";

describe("stream-reveal: the pace of a streamed answer", () => {
  it("is off without the Highlight API or with reduced motion", () => {
    expect(boot().reveal.active()).toBe(true);
    expect(boot({ highlights: false }).reveal.active()).toBe(false);
    expect(boot({ reduced: true }).reveal.active()).toBe(false);
  });

  it("is off while Letter animations are switched off in Settings", () => {
    expect(boot({ letters: true }).reveal.active()).toBe(true);
    const app = boot({ letters: false });
    expect(app.reveal.active()).toBe(false);
    app.window.App.userSettings.set("letter_animations", true);
    expect(app.reveal.active()).toBe(true);
  });

  it("paints a bundle that arrived at once word by word, never half a word", () => {
    const { reveal, el, painted, paint, run } = boot();
    reveal.stream(el, ANSWER, paint);
    run(16);
    expect(painted.at(-1).length).toBeGreaterThan(0);
    expect(painted.at(-1).length).toBeLessThan(ANSWER.length);
    run(3000);
    expect(painted.at(-1)).toBe(ANSWER);
    expect(painted.length).toBeGreaterThan(5);
    for (const shown of painted.slice(0, -1)) {
      expect(shown === "" || /\s/.test(ANSWER[shown.length])).toBe(true);
    }
    expect(el.textContent.trim()).toBe(ANSWER);
  });

  it("lets a word the stream cut in two wait for its rest, and stand once the stream pauses", () => {
    const { reveal, el, painted, paint, run } = boot();
    reveal.stream(el, "Walking lowers blood pres", paint);
    run(160);
    expect(painted.at(-1)).toBe("Walking lowers blood");
    reveal.stream(el, "Walking lowers blood pressure a lit", paint);
    run(160);
    expect(painted.at(-1)).toBe("Walking lowers blood pressure a");
    run(400);
    expect(painted.at(-1)).toBe("Walking lowers blood pressure a lit");
  });

  it("shows a bullet or heading only together with its first word", () => {
    const { reveal, el, painted, paint, run } = boot();
    reveal.stream(el, "Intro paragraph here.\n\n- **Tim", paint);
    run(160);
    expect(painted.at(-1).trimEnd()).toBe("Intro paragraph here.");
    expect(el.querySelector("li")).toBeNull();
    reveal.stream(el, "Intro paragraph here.\n\n- **Timing:** soon.\n\n### ", paint);
    run(1000);
    expect(painted.at(-1).trimEnd()).toBe("Intro paragraph here.\n\n- **Timing:** soon.");
    expect(el.querySelector("h3")).toBeNull();
  });

  it("keeps the words both share when the stream takes text back", () => {
    const { reveal, el, painted, paint, run } = boot();
    reveal.stream(el, "Let me check the latest numbers first.", paint);
    run(1000);
    reveal.stream(el, "Let me answer directly.", paint);
    expect(painted.at(-1)).toBe("Let me");
    run(1000);
    expect(painted.at(-1)).toBe("Let me answer directly.");
    expect(el.textContent.trim()).toBe("Let me answer directly.");
  });

  it("shows a long running answer it picks up after a reload at once", () => {
    const { reveal, el, painted, paint, run } = boot();
    const long = `${"A sentence of ordinary length that keeps going. ".repeat(40)}End.`;
    reveal.stream(el, long, paint);
    expect(painted.at(-1)).toBe(long);
    run(16);
    expect(painted).toHaveLength(2);
  });
});

describe("stream-reveal: the fixed answer", () => {
  it("renders a fixed answer whose last line looks like a list mark", () => {
    // "42." or a closing "1." line is a whole answer once it is fixed, not
    // the start of a list that waits for its first word.
    for (const answer of ["42.", "Result:\n\n1."]) {
      const { window, reveal, el, paint, run } = boot();
      reveal.stream(el, answer, paint);
      run(16);
      const render = vi.fn(() => window.morphMarkdown(el, answer));
      reveal.settle(el, answer, render);
      run(3000);
      expect(render).toHaveBeenCalledTimes(1);
      expect(el.classList.contains("is-stream-revealing")).toBe(false);
    }
  });

  it("lets the full render follow the last paced word", () => {
    const { window, reveal, el, painted, paint, run } = boot();
    reveal.stream(el, ANSWER, paint);
    run(16);
    const render = vi.fn(() => window.morphMarkdown(el, ANSWER));
    reveal.settle(el, ANSWER, render);
    expect(render).not.toHaveBeenCalled();
    run(3000);
    expect(render).toHaveBeenCalledTimes(1);
    expect(painted.at(-1)).toBe(ANSWER);
    expect(el.textContent.trim()).toBe(ANSWER);
    expect(el.classList.contains("is-stream-revealing")).toBe(false);
  });

  it("renders another chat's answer at once and leaves nothing of the look behind", () => {
    const { window, reveal, el, paint, run, lit } = boot();
    reveal.stream(el, ANSWER, paint);
    run(32);
    expect(lit()).toBeGreaterThan(0);
    const render = vi.fn(() => window.morphMarkdown(el, "Another saved answer."));
    reveal.settle(el, "Another saved answer.", render);
    expect(render).toHaveBeenCalledTimes(1);
    expect(el.textContent.trim()).toBe("Another saved answer.");
    expect(el.classList.contains("is-stream-revealing")).toBe(false);
    run(16);
    expect(lit()).toBe(0);
  });

  it("renders at once without a stream to follow", () => {
    const { reveal, el } = boot();
    const render = vi.fn();
    reveal.settle(el, "Saved answer.", render);
    expect(render).toHaveBeenCalledTimes(1);
  });

  it("hands the answer over to anyone else who writes into it", () => {
    const { window, reveal, el, painted, paint, run, lit } = boot();
    reveal.stream(el, ANSWER, paint);
    run(32);
    const paints = painted.length;
    window.injectMarkdown(el, "Marked by the review.", []);
    run(1000);
    expect(painted).toHaveLength(paints);
    expect(el.textContent.trim()).toBe("Marked by the review.");
    expect(el.classList.contains("is-stream-revealing")).toBe(false);
    expect(lit()).toBe(0);
  });
});

describe("stream-reveal: the light", () => {
  it("brings a painted word's letters into view one after another, and leaves no highlight once they stand", () => {
    const { window, reveal, el, paint, run, unseen, lit } = boot();
    reveal.stream(el, ANSWER, paint);
    run(16);
    expect(el.classList.contains("is-stream-revealing")).toBe(true);
    expect(unseen()).toBeGreaterThan(0);
    const rules = window.document.adoptedStyleSheets[0].rules;
    expect(rules[0]).toMatch(/stream-light-0-0\) \{ color: transparent; \}/);
    expect(rules.slice(1).every(rule => rule.includes("var(--stream-light"))).toBe(true);
    const render = () => window.morphMarkdown(el, ANSWER);
    reveal.settle(el, ANSWER, render);
    run(4000);
    expect(unseen()).toBe(0);
    expect(lit()).toBe(0);
    expect(el.classList.contains("is-stream-revealing")).toBe(false);
  });
});
