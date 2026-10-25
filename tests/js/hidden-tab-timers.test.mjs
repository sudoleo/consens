/**
 * Timers rest in a hidden tab (audit F18).
 *
 * The allowance countdown in app-init.js ticked every second, also in
 * background tabs. Now it pauses while document.hidden and catches up at
 * once when the tab comes back. (The guided Consensus run block had the
 * same rule; it left the browser on 2026-10-25.)
 */

import { describe, expect, it } from "vitest";

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
    expect(display.textContent).toMatch(/^Resets in: \d\d:\d\d$/);
    expect(countdownTimers(state)).toHaveLength(1);

    // The hidden countdown wakes the allowance panel through a
    // MutationObserver (sidebar-quota.js). It changes once a minute, so the
    // ticks in between write nothing (Apple audit D10); a minute boundary
    // may fall between these ticks once.
    const observer = new window.MutationObserver(() => {});
    observer.observe(display, { childList: true, characterData: true, subtree: true });
    for (let tick = 0; tick < 5; tick += 1) countdownTimers(state)[0].fn();
    expect(observer.takeRecords().length).toBeLessThanOrEqual(1);
    observer.disconnect();

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
