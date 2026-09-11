import { describe, expect, it } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

function boot() {
  let now = 0, sequence = 0, tick;
  const frames = new Map();
  const motion = { matches: false };
  const app = loadScripts(["static/js/consensus-progress.js"], {
    body: `<section id="consensusRun" hidden><div id="runPast"></div><span id="runStatus"></span><span id="runTime"></span><div id="runDetail" hidden></div></section>
      <div class="response-section"><div id="model" class="response-box" data-response-state="pending" data-consensus-answer="abcd"><div class="collapsible-content is-streaming">abcd</div></div></div>`,
    before(window) {
      window.performance.now = () => now;
      window.matchMedia = () => motion;
      window.requestAnimationFrame = callback => { frames.set(++sequence, callback); return sequence; };
      window.cancelAnimationFrame = id => frames.delete(id);
      window.setInterval = callback => { tick = callback; return 1; };
      window.clearInterval = () => {};
    }
  });
  const pipeline = app.window.App.consensusPipeline;
  pipeline.onPrepare();
  pipeline.onQueryStatus("running");
  const advance = ms => {
    now += ms;
    const callbacks = [...frames.values()];
    frames.clear();
    callbacks.forEach(callback => callback(now));
  };
  advance(0); advance(0);
  const box = app.document.getElementById("model");
  const status = app.document.querySelector(".run-model-time");
  return {
    ...app, pipeline, frames, motion, advance, status,
    count: () => Number(status.textContent.replace(/[^0-9]/g, "")),
    receive(count, state = "pending") {
      box.dataset.consensusAnswer = "x".repeat(count);
      box.dataset.responseState = state;
      tick();
    }
  };
}

describe("stream character animation", () => {
  it("eases monotonically toward received counts, retargets bursts and stops at the exact value", () => {
    const app = boot();
    expect(app.count()).toBe(4);
    app.receive(1000);
    expect(app.count()).toBe(4);
    app.advance(65);
    const first = app.count();
    expect(first).toBeGreaterThan(4);
    expect(first).toBeLessThan(1000);
    app.receive(1400);
    expect(app.count()).toBe(first);
    for (let i = 0, previous = first; i < 4; i++) {
      app.advance(65);
      expect(app.count()).toBeGreaterThanOrEqual(previous);
      expect(app.count()).toBeLessThanOrEqual(1400);
      previous = app.count();
    }
    expect(app.count()).toBe(1400);
    expect(app.frames.size).toBe(0);
    app.advance(1000);
    expect(app.count()).toBe(1400);
    app.pipeline.dismiss();
    app.dom.window.close();
  });

  it("never lets a queued animation overwrite terminal status or a new run", () => {
    const app = boot();
    app.receive(1000);
    app.advance(65);
    app.receive(1000, "error");
    app.advance(300);
    expect(app.status.textContent).toBe("Failed");
    app.receive(2000);
    app.receive(3000);
    app.pipeline.dismiss();
    expect(app.frames.size).toBe(0);
    app.advance(500);
    expect(app.document.querySelector(".run-model-time")).toBeNull();
    app.pipeline.onPrepare();
    app.receive(7);
    app.pipeline.onQueryStatus("running");
    expect(app.document.querySelector(".run-model-time").textContent).toBe("7 chars");
    app.pipeline.dismiss();
    app.dom.window.close();
  });

  it("settles immediately with Reduced Motion, including changes mid-animation", () => {
    const app = boot();
    app.receive(1000);
    app.advance(30);
    app.motion.matches = true;
    app.advance(16);
    expect(app.count()).toBe(1000);
    app.receive(2345);
    expect(app.status.textContent).toBe("2,345 chars");
    expect(app.frames.size).toBe(0);
    app.pipeline.dismiss();
    app.dom.window.close();
  });
});
