import { readFileSync } from "node:fs";
import path from "node:path";

import { JSDOM } from "jsdom";
import { describe, expect, it } from "vitest";

import { ROOT } from "./helpers/appWindow.mjs";

const SCRIPT = readFileSync(path.join(ROOT, "static/js/landing-chat.js"), "utf8");

// The pieces the script works on, in the shape templates/landing.html gives
// them: a piece that appears, the review with its plan, its note and what
// comes after it, the Watch card and the docked field.
const PAGE = `
<a id="navCtaButton" href="/app">Open app</a>
<main>
  <p id="piece" data-reveal>A message</p>
  <article id="review" data-review>
    <div class="lc-claims" data-reveal>
      <table><tbody><tr class="lc-note-row"><td><div class="lc-note">A note</div></td></tr></tbody></table>
    </div>
    <p id="after" data-reveal data-after-review>The agent corrected its answer</p>
  </article>
  <section id="card" data-reveal data-watch data-state="watching"></section>
  <div class="lc-dock"><a id="landingField" href="/app?focus=1">Field</a></div>
</main>`;

// jsdom has no layout and no IntersectionObserver: the test keeps the
// observers the script makes and calls them itself, gives a piece the box it
// wants, and runs the script's frames and timers by hand.
function page({ reduced = false } = {}) {
  const dom = new JSDOM(`<!doctype html><html><head></head><body>${PAGE}</body></html>`, {
    url: "https://consens.io/", runScripts: "dangerously", pretendToBeVisual: true,
  });
  const { window } = dom;
  const observers = [];
  const timers = [];
  const frames = [];
  window.IntersectionObserver = class {
    constructor(callback, options) {
      this.callback = callback;
      this.options = options;
      this.targets = new Set();
      observers.push(this);
    }
    observe(element) { this.targets.add(element); }
    unobserve(element) { this.targets.delete(element); }
    disconnect() { this.targets.clear(); }
  };
  window.requestAnimationFrame = fn => { frames.push(fn); return frames.length; };
  window.setTimeout = (fn, ms) => { timers.push({ fn, ms }); return timers.length; };
  window.matchMedia = query => ({ matches: reduced && query.includes("reduce"), addEventListener() {} });
  const script = window.document.createElement("script");
  script.textContent = SCRIPT;
  window.document.head.appendChild(script);
  const runTimer = () => { const timer = timers.shift(); timer.fn(); return timer.ms; };
  const runFrame = () => frames.shift()();
  // Where the docked field begins: the window's height less the field (no
  // height in jsdom) and the 24 px of air above it.
  const line = window.innerHeight - 24;
  return { window, document: window.document, observers, runTimer, timers, frames, runFrame, line };
}

// A piece whose top the test moves, as the scroll would.
function place(piece, top, height = 80) {
  const box = { top, height };
  piece.getBoundingClientRect = () => ({ top: box.top, height: box.height, bottom: box.top + box.height });
  return box;
}

// What the observer of the pieces reports: in the window or not, and for one
// that is not, where its lower edge stands against the window's top.
const entry = (target, isIntersecting = true, bottom = 0) => ({
  target, isIntersecting, boundingClientRect: { bottom }, rootBounds: { top: 0 },
});

describe("landing page as one chat", () => {
  it("shows a short piece once all of it stands above the field, a tall one once its first lines do", () => {
    const { standsClear } = page().window.LandingChat;
    expect(standsClear(600, 80, 700)).toBe(true);
    expect(standsClear(640, 80, 700)).toBe(false);
    expect(standsClear(580, 900, 700)).toBe(true);
    expect(standsClear(600, 900, 700)).toBe(false);
  });

  it("takes the Watch card from its proposal over the pressed button to the running Watch", () => {
    const { watchState } = page().window.LandingChat;
    expect([0, 0.39, 0.4, 0.61, 0.62, 1].map(watchState))
      .toEqual(["proposal", "proposal", "pressing", "pressing", "watching", "watching"]);
  });

  it("leaves the page in its last frame for a reader who asked for less motion", () => {
    const { document, observers } = page({ reduced: true });
    expect(document.documentElement.classList.contains("lc-js")).toBe(false);
    expect(document.getElementById("card").dataset.state).toBe("watching");
    expect(document.getElementById("review").dataset.phase).toBeUndefined();
    expect(observers).toHaveLength(0);
  });

  it("arms the page and lets a piece in once it has cleared the field", () => {
    const { document, observers, runFrame, line } = page();
    expect(document.documentElement.classList.contains("lc-js")).toBe(true);
    expect(document.getElementById("card").dataset.state).toBe("proposal");
    expect(document.getElementById("review").dataset.phase).toBe("plain");
    const revealer = observers[1];
    const piece = document.getElementById("piece");
    const box = place(piece, line - 40);
    revealer.callback([entry(piece)]);
    expect(piece.classList.contains("is-in")).toBe(false);
    // The page glides on and the observer has nothing more to say: the
    // next frame finds the piece clear of the field.
    box.top = line - 80;
    runFrame();
    expect(piece.classList.contains("is-in")).toBe(true);
    expect(revealer.targets.has(piece)).toBe(false);
  });

  it("reads no boxes on a page at rest and takes it up again with the scroll", () => {
    const { window, document, observers, frames, runFrame, line } = page();
    const piece = document.getElementById("piece");
    const box = place(piece, line - 40);
    observers[1].callback([entry(piece)]);
    for (let n = 0; frames.length && n < 100; n += 1) runFrame();
    expect(frames).toHaveLength(0);
    expect(piece.classList.contains("is-in")).toBe(false);

    box.top = line - 80;
    window.dispatchEvent(new window.Event("scroll"));
    expect(frames).toHaveLength(1);
    runFrame();
    expect(piece.classList.contains("is-in")).toBe(true);
    expect(frames).toHaveLength(0);
  });

  it("forgets a piece that left the window again before it cleared the field", () => {
    const { document, observers, runFrame, line } = page();
    const piece = document.getElementById("piece");
    place(piece, line - 40);
    observers[1].callback([entry(piece)]);
    observers[1].callback([entry(piece, false, 2000)]);
    runFrame();
    expect(piece.classList.contains("is-in")).toBe(false);
    expect(observers[1].targets.has(piece)).toBe(true);
  });

  it("shows what already stands above the window when a visit starts further down", () => {
    const { document, observers } = page();
    const piece = document.getElementById("piece");
    observers[1].callback([entry(piece, false, -320)]);
    expect(piece.classList.contains("is-in")).toBe(true);
  });

  it("plays the review once, and the correction waits until the finding has landed", () => {
    const { document, observers, runTimer, timers } = page();
    const [driver, revealer] = observers;
    const review = document.getElementById("review");
    const after = document.getElementById("after");
    const plan = review.querySelector(".lc-claims");
    expect(revealer.targets.has(after)).toBe(false);

    // The review reaches down the window and its note stands in view (a
    // box the test did not place is at the top in jsdom).
    place(review, 40, 900);
    driver.callback([{ target: review, isIntersecting: true }]);
    expect(review.dataset.phase).toBe("reviewing");
    expect(plan.classList.contains("is-reviewing")).toBe(true);
    driver.callback([{ target: review, isIntersecting: true }]);
    expect(timers).toHaveLength(1);

    expect(runTimer()).toBe(1150);
    expect(review.dataset.phase).toBe("found");
    expect(plan.classList.contains("is-reviewing")).toBe(false);
    expect(revealer.targets.has(after)).toBe(false);

    expect(runTimer()).toBe(1500);
    expect(review.dataset.settled).toBe("true");
    expect(revealer.targets.has(after)).toBe(true);
  });

  it("shows a review the visitor jumped past in its last frame, without the clock", () => {
    const { window, document, observers, timers, runFrame } = page();
    const review = document.getElementById("review");
    const after = document.getElementById("after");
    // No observer speaks up for a piece that went from below the window
    // to above it in one jump: the scroll itself has to say so.
    place(review, -1400, 900);
    window.dispatchEvent(new window.Event("scroll"));
    runFrame();
    expect(review.dataset.phase).toBe("found");
    expect(review.dataset.settled).toBe("true");
    expect(timers).toHaveLength(0);
    expect(observers[1].targets.has(after)).toBe(true);
  });

  it("tells the app that the visitor asked for it", () => {
    for (const reduced of [false, true]) {
      const { window, document } = page({ reduced });
      const field = document.getElementById("landingField");
      field.addEventListener("click", event => event.preventDefault());
      field.click();
      expect(window.sessionStorage.getItem("skipLandingRedirect")).toBe("1");
    }
  });
});
