import { describe, expect, it } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

function fakeContext() {
  const ctx = {
    fillStyle: "#000", globalAlpha: 1, font: "", textBaseline: "", textAlign: "",
    puts: 0, draws: 0, cells: new Map(),
    clearRect() {}, fillText() {}, setTransform() {},
    // The glyph a cell shows is its source offset in the glyph atlas.
    drawImage(image, sx, sy, sw, sh, dx, dy) { ctx.draws += 1; if (dx !== undefined) ctx.cells.set(dx + "," + dy, sx); },
    putImageData() { ctx.puts += 1; },
    createImageData(w, h) { return { data: new Uint8ClampedArray(w * h * 4) }; },
  };
  return ctx;
}

function boot({ hero = true, reduce = false, hidden = false, canvas = true, watchHidden = true, media = true, dpr = 1 } = {}) {
  const queue = [];
  const timers = new Map();
  let lastTimer = 0;
  const { window, document } = loadScripts(["static/js/letter-clouds.js"], {
    body: `<div class="container"><div class="input-section"><p class="hero-greeting">Hi</p>
      <textarea id="questionInput"></textarea><button id="send">Send</button></div>
      <div id="empty"></div></div>
      <section class="watch-page"${watchHidden ? " hidden" : ""}></section>`,
    before(window) {
      if (hero) window.document.body.classList.add("is-hero");
      Object.defineProperty(window, "devicePixelRatio", { configurable: true, value: dpr });
      window.requestAnimationFrame = fn => { queue.push(fn); return queue.length; };
      window.cancelAnimationFrame = () => { queue.length = 0; };
      window.setTimeout = (fn, ms) => { timers.set(++lastTimer, { fn, ms }); return lastTimer; };
      window.clearTimeout = id => { timers.delete(id); };
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
    timers,
    fog,
    state: () => window.App.letterClouds.state(),
    frame(ts = 1000) { queue.splice(0).forEach(fn => fn(ts)); },
    tick() { const due = [...timers.values()]; timers.clear(); due.forEach(t => t.fn()); },
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

  it("keeps a wave click from selecting text, and only that click", async () => {
    const app = boot();
    const empty = app.document.getElementById("empty");
    const greeting = app.document.querySelector(".hero-greeting");
    const select = target => target.dispatchEvent(new app.window.Event("selectstart", { bubbles: true, cancelable: true }));
    app.press(empty);
    expect(select(empty)).toBe(false);
    empty.dispatchEvent(new app.window.MouseEvent("pointerup", { bubbles: true }));
    expect(select(empty)).toBe(true);

    app.press(greeting);
    expect(select(greeting)).toBe(true);

    app.document.body.classList.remove("is-hero");
    await app.settle();
    app.press(empty);
    expect(select(empty)).toBe(true);
  });

  it("sleeps between calm frames and draws every display frame only during a wave", async () => {
    const app = boot();
    app.frame();
    expect(app.queue).toHaveLength(0);
    expect(app.timers.size).toBe(1);
    expect(app.state().running).toBe(true);
    app.tick();
    expect(app.queue).toHaveLength(1);

    app.press(app.document.getElementById("empty"));
    app.frame();
    expect(app.queue).toHaveLength(1);
    expect(app.timers.size).toBe(0);

    app.document.body.classList.remove("is-hero");
    await app.settle();
    expect(app.state().running).toBe(false);
    expect(app.timers.size).toBe(0);
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

  // Apple audit D11: an Android keyboard or a turned phone shuffled every
  // glyph at once, and the hidden layer kept repainting and its ~30 MB of
  // canvas behind every chat.
  function resizeTo(app, width, height) {
    app.window.innerWidth = width;
    app.window.innerHeight = height;
    app.window.dispatchEvent(new app.window.Event("resize"));
  }
  const glyphs = app => app.document.querySelector(".letter-clouds-glyphs");

  it("keeps the glyphs that are already there when the window changes size", () => {
    const app = boot();
    const before = new Map(glyphs(app).__ctx.cells);
    resizeTo(app, 700, 500);
    app.tick();
    const after = glyphs(app).__ctx.cells;
    const kept = [...before].filter(([cell]) => {
      const [x, y] = cell.split(",").map(Number);
      return x < glyphs(app).width && y < glyphs(app).height;
    });
    expect(kept.length).toBeGreaterThan(100);
    for (const [cell, glyph] of kept) expect(after.get(cell)).toBe(glyph);
  });

  it("does nothing behind a chat when the window changes size and measures again on return", async () => {
    const app = boot();
    app.document.body.classList.remove("is-hero");
    await app.settle();
    const draws = glyphs(app).__ctx.draws;
    resizeTo(app, 700, 500);
    expect(app.timers.size).toBe(0);
    expect(glyphs(app).__ctx.draws).toBe(draws);

    app.document.body.classList.add("is-hero");
    await app.settle();
    expect(glyphs(app).width).toBe(700);
    expect(app.state()).toMatchObject({ active: true, running: true });
  });

  // Apple audit G16: capped at 2x, the glyphs were scaled up 1.5 times on a
  // 3x iPhone and looked softer than the text in front of them. The fog stays
  // coarse at every density.
  it("draws the glyphs at the full density of a 3x screen and keeps the fog coarse", () => {
    const app = boot({ dpr: 3 });
    const layerWidth = app.window.innerWidth;
    expect(glyphs(app).width).toBe(Math.round(layerWidth * 3));
    const fog = app.document.querySelector(".letter-clouds-fog");
    expect(fog.width).toBe(Math.ceil(layerWidth / 10) + 1);
    // A denser screen than 3x paints no more than 3x.
    const app4 = boot({ dpr: 4 });
    expect(glyphs(app4).width).toBe(Math.round(app4.window.innerWidth * 3));
  });

  it("frees its canvases once it has faded out behind a chat", async () => {
    const app = boot();
    const layer = app.document.querySelector(".letter-clouds");
    const faded = () => {
      const event = new app.window.Event("transitionend");
      Object.defineProperty(event, "propertyName", { value: "opacity" });
      layer.dispatchEvent(event);
    };
    // Fading in on the start screen keeps everything.
    faded();
    expect(glyphs(app).width).toBeGreaterThan(0);

    app.document.body.classList.remove("is-hero");
    await app.settle();
    faded();
    expect(glyphs(app).width).toBe(0);
    expect(app.document.querySelector(".letter-clouds-fog").width).toBe(0);

    app.document.body.classList.add("is-hero");
    await app.settle();
    expect(glyphs(app).width).toBeGreaterThan(0);
    app.frame();
    expect(app.fog().puts).toBeGreaterThan(1);
  });
});
