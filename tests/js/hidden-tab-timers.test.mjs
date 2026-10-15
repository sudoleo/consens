/**
 * Timers rest in a hidden tab (audit F18).
 *
 * The guided run block (consensus-progress.js) ticked every 200 ms and
 * re-rendered the whole block on each tick; the allowance countdown in
 * app-init.js ticked every second. Both kept going in background tabs.
 * Now both pause while document.hidden and catch up at once when the tab
 * comes back, and the run ticker only moves the clock and the per-model
 * rows; steps, counts and the note follow the boxes' state attributes.
 */

import { describe, expect, it } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";
import { bootApp } from "./helpers/appBoot.mjs";

function trackTimers(window, state) {
  state.timers = new Map();
  let next = 1;
  window.setInterval = (fn, ms) => {
    const id = next++;
    state.timers.set(id, { fn, ms });
    return id;
  };
  window.clearInterval = (id) => { state.timers.delete(id); };
  Object.defineProperty(window.document, "hidden", {
    configurable: true,
    get: () => state.hidden,
  });
}

function setHidden(window, state, hidden) {
  state.hidden = hidden;
  window.document.dispatchEvent(new window.Event("visibilitychange"));
}

function intervalsOf(state, ms) {
  return Array.from(state.timers.values()).filter((timer) => timer.ms === ms);
}

const RUN_BODY = `
  <section id="consensusRun" class="run" data-stage="idle" hidden>
    <span id="runStatus"></span>
    <span id="runCompactLabel"></span><span id="runCompactCount"></span>
    <ol id="runSteps">
      <li class="run-step" data-step="prepare"><span class="run-step-label"></span></li>
      <li class="run-step" data-step="answers"><span class="run-step-label">Answers</span><span id="runCount"></span></li>
      <li class="run-step" data-step="consensus"></li>
      <li class="run-step" data-step="differences"></li>
    </ol>
    <span id="runMeta"></span><span id="runMetaNext"></span>
    <span class="run-time" id="runTime"></span>
    <div class="run-track" id="runTrack"><i id="runBar"></i></div>
    <div class="run-detail" id="runDetail" hidden></div>
    <p id="runNote" hidden><span id="runNoteText"></span></p>
  </section>
  <section class="response-section">
    <div id="openaiResponse" class="response-box" data-short-label="OpenAI" data-response-state="streaming">
      <div class="collapsible-content is-streaming"></div>
    </div>
    <div id="claudeResponse" class="response-box" data-short-label="Claude" data-response-state="streaming">
      <div class="collapsible-content is-streaming"></div>
    </div>
  </section>
`;

function bootRun({ hidden = false } = {}) {
  const state = { hidden };
  const harness = loadScripts(["static/js/consensus-progress.js"], {
    body: RUN_BODY,
    before(window) {
      trackTimers(window, state);
      window.App = {};
    },
  });
  return { ...harness, state, pipeline: harness.window.App.consensusPipeline };
}

function microtask() {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

describe("guided run ticker", () => {
  it("does not tick in a hidden tab and catches the clock up when the tab returns", () => {
    const { window, document, state, pipeline } = bootRun({ hidden: true });
    pipeline.onPrepare(Date.now() - 65_000);
    expect(intervalsOf(state, 200)).toHaveLength(0);

    setHidden(window, state, false);
    expect(document.getElementById("runTime").textContent).toBe("1:05");
    expect(intervalsOf(state, 200)).toHaveLength(1);

    setHidden(window, state, true);
    expect(intervalsOf(state, 200)).toHaveLength(0);
    window.close();
  });

  it("stays stopped after the run ends, even when the tab comes back", () => {
    const { window, state, pipeline } = bootRun();
    pipeline.onPrepare(Date.now());
    expect(intervalsOf(state, 200)).toHaveLength(1);
    pipeline.dismiss();
    expect(intervalsOf(state, 200)).toHaveLength(0);
    setHidden(window, state, true);
    setHidden(window, state, false);
    expect(intervalsOf(state, 200)).toHaveLength(0);
    window.close();
  });

  it("moves the clock and the model rows on each tick", () => {
    const { window, document, state, pipeline } = bootRun();
    pipeline.onPrepare(Date.now() - 3_000);
    pipeline.onQueryStatus("running");
    const [ticker] = intervalsOf(state, 200);
    const row = document.querySelector('.run-model[data-box="openaiResponse"]');
    const before = row.querySelector(".run-model-track i").style.getPropertyValue("--p");

    document.querySelector("#openaiResponse .collapsible-content").textContent = "x".repeat(800);
    ticker.fn();
    expect(document.getElementById("runTime").textContent).toBe("0:03");
    expect(row.querySelector(".run-model-track i").style.getPropertyValue("--p")).not.toBe(before);
    window.close();
  });

  it("re-renders the block when a model drops out, without waiting for a tick", async () => {
    const { window, document, pipeline } = bootRun();
    pipeline.onPrepare(Date.now());
    pipeline.onQueryStatus("running");
    expect(document.getElementById("runNote").hidden).toBe(true);

    // Only the error flag changes, not data-response-state.
    document.getElementById("claudeResponse").dataset.responseError = "true";
    await microtask();
    expect(document.getElementById("runNote").hidden).toBe(false);
    expect(document.getElementById("runNoteText").textContent).toContain("Claude didn't answer.");
    window.close();
  });
});

describe("allowance countdown", () => {
  const BODY = `
    <button id="toggleSidebarButton" class="sidebar-toggle" type="button"></button>
    <aside class="sidebar"><div class="bookmarks-section"><button id="bookmarksToggle" type="button"></button><div id="bookmarksContainer"></div></div></aside>
    <a id="logoLink" href="#home"></a>
    <input id="reasoningToggle" type="checkbox">
    <textarea id="questionInput"></textarea>
    <button id="sendButton" type="button"></button>
    <input id="openrouterKey">
    <span id="countdownDisplay"></span>
  `;

  function countdownTimers(state) {
    return Array.from(state.timers.values()).filter((timer) => timer.fn.name === "updateCountdown");
  }

  it("rests while the tab is hidden and shows the current time on return", async () => {
    const state = { hidden: true };
    const { window, document, errors } = await bootApp({
      body: BODY,
      before(window) { trackTimers(window, state); },
    });
    const display = document.getElementById("countdownDisplay");
    expect(countdownTimers(state)).toHaveLength(0);
    expect(display.textContent).toBe("");

    setHidden(window, state, false);
    expect(display.textContent).toMatch(/^Resets in: \d\d:\d\d:\d\d$/);
    expect(countdownTimers(state)).toHaveLength(1);

    setHidden(window, state, true);
    expect(countdownTimers(state)).toHaveLength(0);
    // Back again: exactly one interval, not one per visit.
    setHidden(window, state, false);
    setHidden(window, state, false);
    expect(countdownTimers(state)).toHaveLength(1);
    expect(errors).toEqual([]);
    window.close();
  });
});
