import { readFileSync } from "node:fs";
import path from "node:path";

import { JSDOM } from "jsdom";
import { describe, expect, it, vi } from "vitest";

import { ROOT } from "./helpers/appWindow.mjs";

const SCRIPT = readFileSync(path.join(ROOT, "static/js/public-nav.js"), "utf8");

const NAV = `
<nav class="site-nav lp-nav">
  <a href="/" class="brand">consens.io</a>
  <div class="nav-links">
    <a href="/#product" aria-current="page">Product</a>
    <a href="/#watch">Watches</a>
    <details class="nav-menu">
      <summary aria-label="Menu"></summary>
      <div class="nav-menu-panel"><a href="/#watch">Watches</a><a href="/topics">Topics</a></div>
    </details>
    <a id="navCtaButton" href="/app" class="nav-cta">Open app</a>
  </div>
</nav>
<main><p id="outside">Text</p><section id="watch">Watch</section></main>`;

function page({ url = "https://consens.io/about", reduced = true, readyState = "interactive" } = {}) {
  const dom = new JSDOM(`<!doctype html><html><head></head><body>${NAV}</body></html>`, {
    url, runScripts: "dangerously", pretendToBeVisual: true,
  });
  const { window } = dom;
  window.requestAnimationFrame = (fn) => { fn(0); return 1; };
  window.matchMedia = (query) => ({
    matches: reduced && query.includes("reduce"),
    addEventListener() {},
  });
  if (readyState) Object.defineProperty(window.document, "readyState", { value: readyState, configurable: true });
  const script = window.document.createElement("script");
  script.textContent = SCRIPT;
  window.document.head.appendChild(script);
  return window;
}

describe("public navigation (Apple-Audit I3, L1)", () => {
  it("closes the menu on a tap beside it, on a link in it and on Escape", () => {
    const window = page();
    const { document } = window;
    const menu = document.querySelector(".nav-menu");

    menu.open = true;
    document.getElementById("outside").click();
    expect(menu.open).toBe(false);

    menu.open = true;
    document.querySelector(".nav-menu-panel a[href='/topics']").addEventListener("click", (event) => event.preventDefault());
    document.querySelector(".nav-menu-panel a[href='/topics']").click();
    expect(menu.open).toBe(false);

    menu.open = true;
    document.dispatchEvent(new window.KeyboardEvent("keydown", { key: "Escape" }));
    expect(menu.open).toBe(false);
    expect(document.activeElement).toBe(menu.querySelector("summary"));
  });

  it("closes on a real scroll, not on the nudge of a tap", () => {
    const window = page();
    const menu = window.document.querySelector(".nav-menu");
    menu.querySelector("summary").click();
    menu.open = true;
    Object.defineProperty(window, "scrollY", { value: 10, configurable: true });
    window.dispatchEvent(new window.Event("scroll"));
    expect(menu.open).toBe(true);
    Object.defineProperty(window, "scrollY", { value: 80, configurable: true });
    window.dispatchEvent(new window.Event("scroll"));
    expect(menu.open).toBe(false);
  });

  it("leaves with a movement before it closes", () => {
    vi.useFakeTimers();
    try {
      const window = page({ reduced: false });
      const menu = window.document.querySelector(".nav-menu");
      menu.open = true;
      window.document.getElementById("outside").click();
      expect(menu.classList.contains("is-closing")).toBe(true);
      expect(menu.open).toBe(true);
      vi.advanceTimersByTime(300);
      expect(menu.open).toBe(false);
      expect(menu.classList.contains("is-closing")).toBe(false);
    } finally {
      vi.useRealTimers();
    }
  });

  it("switches smooth scrolling on only after the page has loaded", () => {
    const window = page({ readyState: "interactive" });
    const root = window.document.documentElement;
    expect(root.classList.contains("is-scroll-smooth")).toBe(false);
    window.dispatchEvent(new window.Event("load"));
    expect(root.classList.contains("is-scroll-smooth")).toBe(true);
  });

  it("marks Watches while the Watch section fills the landing page", () => {
    const window = page({ url: "https://consens.io/" });
    const { document } = window;
    const watch = document.getElementById("watch");
    const current = () => Array.from(document.querySelectorAll(".site-nav a[aria-current]"), (a) => a.textContent);
    Object.defineProperty(window, "innerHeight", { value: 800, configurable: true });

    watch.getBoundingClientRect = () => ({ top: 900, bottom: 1700 });
    window.dispatchEvent(new window.Event("resize"));
    expect(current()).toEqual(["Product"]);

    watch.getBoundingClientRect = () => ({ top: 54, bottom: 900 });
    window.dispatchEvent(new window.Event("resize"));
    expect(current()).toEqual(["Watches", "Watches"]);
  });
});
