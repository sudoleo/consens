import { describe, expect, it } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

function fakeContext() {
  const ctx = {
    fillStyle: "#000", globalAlpha: 1, font: "", textBaseline: "", textAlign: "",
    puts: 0, draws: 0,
    clearRect() {}, fillText() {}, setTransform() {},
    drawImage() { ctx.draws += 1; },
    putImageData() { ctx.puts += 1; },
    createImageData(w, h) { return { data: new Uint8ClampedArray(w * h * 4) }; },
  };
  return ctx;
}

function boot({ hero = true, reduce = false, hidden = false, canvas = true, watchHidden = true, media = true } = {}) {
  const queue = [];
  const { window, document } = loadScripts(["static/js/letter-clouds.js"], {
    body: `<div class="container"><div class="input-section"><p class="hero-greeting">Hi</p>
      <textarea id="questionInput"></textarea><button id="send">Send</button></div>
      <div id="empty"></div></div>
      <section class="watch-page"${watchHidden ? " hidden" : ""}></section>`,
    before(window) {
      if (hero) window.document.body.classList.add("is-hero");
      window.requestAnimationFrame = fn => { queue.push(fn); return queue.length; };
      window.cancelAnimationFrame = () => { queue.length = 0; };
      if (media) {
        window.matchMedia = query => ({
          matches: reduce && query.includes("reduced-motion"),
          addEventListener() {},
        });
      }
      Object.defineProperty(window.document, "hidden", { configurable: true, get: () => hidden });
      window.HTMLCanvasElement.prototype.getContext = function () {
        if (!canvas) return null;
        return this.__ctx || (this.__ctx = fakeContext());
      };
    },
  });
  const fog = () => document.querySelector(".letter-clouds-fog")?.__ctx;
  return {
    window,
    document,
    queue,
    fog,
    state: () => window.App.letterClouds.state(),
    frame(ts = 1000) { queue.splice(0).forEach(fn => fn(ts)); },
    settle: () => new Promise(resolve => setTimeout(resolve, 0)),
    press(target) {
      target.dispatchEvent(new window.MouseEvent("pointerdown", { bubbles: true, button: 0, clientX: 120, clientY: 90 }));
    },
  };
}

describe("letter clouds", () => {
  it("draws on the empty start screen and stops completely once a chat is open", async () => {
    const app = boot();
    expect(app.state()).toMatchObject({ supported: true, active: true, running: true });
    app.frame();
    expect(app.fog().puts).toBeGreaterThan(1);

    app.document.body.classList.remove("is-hero");
    await app.settle();
    expect(app.state()).toMatchObject({ active: false, running: false });
    expect(app.document.querySelector(".letter-clouds").classList.contains("is-off")).toBe(true);
    const puts = app.fog().puts;
    app.frame(2000);
    expect(app.fog().puts).toBe(puts);

    app.document.body.classList.add("is-hero");
    await app.settle();
    expect(app.state()).toMatchObject({ active: true, running: true });
  });

  it("never starts when a chat is already open on load", () => {
    const app = boot({ hero: false });
    expect(app.state()).toMatchObject({ active: false, running: false });
  });

  it("sends a wave only from free space, not from controls or the composer", () => {
    const app = boot();
    app.press(app.document.getElementById("questionInput"));
    app.press(app.document.getElementById("send"));
    app.press(app.document.querySelector(".hero-greeting"));
    expect(app.state().ripples).toBe(0);
    app.press(app.document.getElementById("empty"));
    expect(app.state().ripples).toBeGreaterThan(0);
  });

  it("pauses behind the watch page", async () => {
    const app = boot();
    app.document.querySelector(".watch-page").hidden = false;
    await app.settle();
    expect(app.state().active).toBe(false);
  });

  it("shows still clouds without waves under reduced motion", () => {
    const app = boot({ reduce: true });
    app.frame();
    expect(app.fog().puts).toBeGreaterThan(1);
    expect(app.window.App.letterClouds.splash(100, 100)).toBe(false);
    expect(app.state().running).toBe(false);
  });

  it("does not render while the tab is hidden", () => {
    const app = boot({ hidden: true });
    expect(app.state()).toMatchObject({ active: true, running: false });
  });

  it("skips the animation when reduced motion cannot be checked", () => {
    const app = boot({ media: false });
    expect(app.state()).toMatchObject({ supported: false, active: false });
    expect(app.document.querySelector(".letter-clouds")).toBeNull();
  });

  it("stays out of the page when the browser has no canvas", () => {
    const app = boot({ canvas: false });
    expect(app.state().supported).toBe(false);
    expect(app.document.querySelector(".letter-clouds")).toBeNull();
  });
});
