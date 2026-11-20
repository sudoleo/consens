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
// observers the script makes and calls them with the boxes it wants, and it
// runs the script's timers by hand.
function page({ reduced = false } = {}) {
  const dom = new JSDOM(`<!doctype html><html><head></head><body>${PAGE}</body></html>`, {
    url: "https://consens.io/", runScripts: "dangerously", pretendToBeVisual: true,
  });
  const { window } = dom;
  const observers = [];
  const timers = [];
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
  window.requestAnimationFrame = () => 1;
  window.setTimeout = (fn, ms) => { timers.push({ fn, ms }); return timers.length; };
  window.matchMedia = query => ({ matches: reduced && query.includes("reduce"), addEventListener() {} });
  const script = window.document.createElement("script");
  script.textContent = SCRIPT;
  window.document.head.appendChild(script);
  const runTimer = () => { const timer = timers.shift(); timer.fn(); return timer.ms; };
  return { window, document: window.document, observers, runTimer, timers };
}

// The line a piece has to clear: the window's height less the docked field
// (no height in jsdom) and the 24 px of air above it.
const entry = (target, top, height, isIntersecting = true) => ({
  target, isIntersecting, boundingClientRect: { top, height, bottom: top + height }, rootBounds: { top: 0 },
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
    const { window, document, observers } = page();
    expect(document.documentElement.classList.contains("lc-js")).toBe(true);
    expect(document.getElementById("card").dataset.state).toBe("proposal");
    expect(document.getElementById("review").dataset.phase).toBe("plain");
    const revealer = observers[1];
    const piece = document.getElementById("piece");
    const line = window.innerHeight - 24;
    revealer.callback([entry(piece, line - 40, 80)]);
    expect(piece.classList.contains("is-in")).toBe(false);
    revealer.callback([entry(piece, line - 80, 80)]);
    expect(piece.classList.contains("is-in")).toBe(true);
    expect(revealer.targets.has(piece)).toBe(false);
  });

  it("shows what already stands above the window when a visit starts further down", () => {
    const { document, observers } = page();
    const piece = document.getElementById("piece");
    observers[1].callback([entry(piece, -400, 80, false)]);
    expect(piece.classList.contains("is-in")).toBe(true);
  });

  it("plays the review once, and the correction waits until the finding has landed", () => {
    const { document, observers, runTimer, timers } = page();
    const [driver, revealer] = observers;
    const review = document.getElementById("review");
    const after = document.getElementById("after");
    const plan = review.querySelector(".lc-claims");
    expect(revealer.targets.has(after)).toBe(false);

    // The note stands in view (every box is at the top in jsdom).
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
