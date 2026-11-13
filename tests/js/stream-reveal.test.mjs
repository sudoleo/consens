import { describe, expect, it, vi } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

// A browser with the CSS Custom Highlight API, a clock the test moves and
// animation frames it runs, so the pace is deterministic.
function boot({ highlights = true, reduced = false, streaming } = {}) {
  const frames = [];
  let clock = 1000;
  const loaded = loadScripts([
    // Settings > Display > Streaming animation, when the test sets it.
    ...(streaming === undefined ? [] : ["static/js/user-settings.js"]),
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
      if (streaming !== undefined) window.localStorage.setItem("consensio.streamAnimation.v1", String(streaming));
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

  it("is off while Streaming animation is switched off in Settings", () => {
    expect(boot({ streaming: true }).reveal.active()).toBe(true);
    const app = boot({ streaming: false });
    expect(app.reveal.active()).toBe(false);
    app.window.App.userSettings.set("stream_animation", true);
    expect(app.reveal.active()).toBe(true);
  });

  // Letter animations is the start screen's clouds: an account that has them
  // off still sees its answers come in with the light.
  it("stays on while only Letter animations are off", () => {
    const app = boot({ streaming: true });
    app.window.App.userSettings.set("letter_animations", false);
    expect(app.reveal.active()).toBe(true);
  });

  // The first word has no pace history: taking 25 ms a letter in the longest
  // light, and held for the live lines above it, it was slow to come into
  // view.
  it("brings the first word into view within a tenth of a second, then comes in word by word", () => {
    const { window, reveal, el, painted, paint, run } = boot();
    // A first bundle of a few words: a slow pace to begin with.
    reveal.stream(el, "Yes. For most", paint);
    run(16);
    expect(painted.at(-1)).toBe("Yes.");
    // Each letter's highlight step (0: not in view yet, none: in ink).
    const node = el.querySelector("p").firstChild;
    const stepAt = offset => {
      for (const [name, ranges] of window.CSS.highlights) {
        for (const range of ranges) {
          if (range.startContainer === node && range.startOffset <= offset && offset < range.endOffset) {
            return Number(name.split("-").at(-1));
          }
        }
      }
      return null;
    };
    run(64);
    // About 80 ms after it arrived, every letter is more than half in view
    // (step 4 and on; the last two were at step 0 and 2 before).
    expect([0, 1, 2, 3].map(stepAt).every(step => step >= 4)).toBe(true);
    // The words after it keep the pace.
    reveal.stream(el, ANSWER, paint);
    run(16);
    expect(painted.at(-1).length).toBeLessThan(ANSWER.length);
    run(3000);
    expect(painted.at(-1)).toBe(ANSWER);
  });

  it("lets a lone first word stand soon, but not a mark its rest could change", () => {
    const word = boot();
    word.reveal.stream(word.el, "Walking", word.paint);
    word.run(32);
    expect(word.painted.at(-1)).toBe("");
    word.run(48);
    expect(word.painted.at(-1)).toBe("Walking");
    const mark = boot();
    mark.reveal.stream(mark.el, "**Walk", mark.paint);
    mark.run(160);
    expect(mark.painted.at(-1)).toBe("");
    mark.run(160);
    expect(mark.painted.at(-1)).toBe("**Walk");
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

  // Back in a chat whose answer still streams,
  // while the last answer's review marks stood, the review took them off by
  // rendering the arrived text in full (agentReview.render → morphMarkdown).
  // The look counted that as someone else's answer and started from nothing:
  // the answer went blank and ran in from its first word again.
  it("goes on from what someone else rendered into the answer instead of running it in again", () => {
    const head = ANSWER.slice(0, ANSWER.indexOf(" about"));
    // The next words arrive before or after the look noticed the other write.
    for (const noticed of [false, true]) {
      const { window, reveal, el, painted, paint, run } = boot();
      reveal.stream(el, head, paint);
      run(16);
      expect(painted.at(-1).length).toBeLessThan(head.length);
      window.morphMarkdown(el, head);
      if (noticed) run(16);
      const paints = painted.length;
      reveal.stream(el, ANSWER, paint);
      expect(painted.slice(paints).every(shown => shown.startsWith(head)), String(noticed)).toBe(true);
      expect(el.textContent.trim().startsWith(head)).toBe(true);
      run(3000);
      expect(painted.slice(paints).every(shown => shown.startsWith(head))).toBe(true);
      expect(painted.at(-1)).toBe(ANSWER);
    }
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

// The agent corrected sentences of its fixed answer after the review
// (findings_to_agent, agent-review.js): only they come into view again, in
// the same light; what moved below them glides instead of jumping.
describe("stream-reveal: a fixed answer rewritten in place", () => {
  const BEFORE = "Tickets cost 18 euros. The arena opened in 80 AD.\n\nIt held about 50,000 spectators.";
  const AFTER = "Tickets cost 24 euros since 2025. The arena opened in 80 AD.\n\nIt held about 50,000 spectators.";
  // The letters each highlight step covers, by step (0: not in view yet).
  const steps = window => {
    const covered = new Map();
    for (const [name, ranges] of window.CSS.highlights) {
      const step = Number(name.split("-").at(-1));
      for (const range of ranges) covered.set(step, (covered.get(step) || "") + range.toString());
    }
    return covered;
  };

  it("lights up only the sentences that changed, from the first frame, and leaves no highlight after", () => {
    const { window, reveal, el, run, unseen, lit } = boot();
    window.injectMarkdown(el, BEFORE, []);
    reveal.rewrite(el, () => window.morphMarkdown(el, AFTER));
    expect(el.textContent).toContain("Tickets cost 24 euros since 2025.");
    // Before any frame ran: the new sentence is not in view yet, nothing else is touched.
    const sentence = "Tickets cost 24 euros since 2025.";
    const pieces = [...steps(window).values()];
    expect(steps(window).get(0)?.length).toBeGreaterThan(sentence.length - 3);
    expect(pieces.join("").length).toBe(sentence.length);
    expect(pieces.every(piece => sentence.includes(piece))).toBe(true);
    run(200);
    expect(lit()).toBeGreaterThan(0);
    run(3000);
    expect(unseen()).toBe(0);
    expect(lit()).toBe(0);
  });

  it("lets what stands below a longer sentence glide down to its place", () => {
    const { window, document, reveal, el } = boot();
    window.injectMarkdown(el, BEFORE, []);
    const below = document.createElement("section");
    el.after(below);
    let top = 100;
    below.getBoundingClientRect = () => ({ top });
    below.animate = vi.fn();
    reveal.rewrite(el, () => { window.morphMarkdown(el, AFTER); top = 124; });
    expect(below.animate).toHaveBeenCalledTimes(1);
    const [frames, timing] = below.animate.mock.calls[0];
    expect(frames).toEqual([{ transform: "translateY(-24px)" }, { transform: "none" }]);
    expect(timing.duration).toBeLessThan(300);
  });

  it("only rewrites, without light or motion, under reduced motion", () => {
    const { window, document, reveal, el, lit } = boot({ reduced: true });
    window.injectMarkdown(el, BEFORE, []);
    const below = document.createElement("section");
    el.after(below);
    below.animate = vi.fn();
    reveal.rewrite(el, () => window.morphMarkdown(el, AFTER));
    expect(el.textContent).toContain("Tickets cost 24 euros since 2025.");
    expect(lit()).toBe(0);
    expect(below.animate).not.toHaveBeenCalled();
  });
});
