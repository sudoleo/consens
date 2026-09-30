/**
 * The send button swaps its icon only on a real state change: projections
 * call syncSendButtonRunning many times per second, and every swap would
 * restart the icon's entry animation. Starting a run fans the question out
 * (is-launching) once.
 */
import { afterEach, expect, it, vi } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

const contexts = [];
afterEach(() => contexts.splice(0).forEach(ctx => ctx.window.close()));

it("keeps its icon across repeated syncs and launches once per run", () => {
  vi.useFakeTimers();
  let running = false;
  const ctx = loadScripts(["static/js/query-send.js"], {
    body: '<button id="sendButton" class="input-action-btn-primary" data-icon="send"><svg></svg></button>',
    before(window) {
      window.App = { runRegistry: { visible: () => ({ runId: "r" }), get: () => ({ runId: "r" }), isExecuting: () => running } };
    },
  });
  contexts.push(ctx);
  const { window: w, document: d } = ctx;
  const button = d.getElementById("sendButton");
  w.App.syncSendButtonRunning();
  const idle = button.querySelector("svg");
  w.App.syncSendButtonRunning();
  expect(button.querySelector("svg")).toBe(idle);
  expect(button.classList.contains("is-launching")).toBe(false);

  running = true;
  w.App.syncSendButtonRunning();
  const stop = button.querySelector("svg");
  expect(stop.querySelector("rect")).not.toBeNull();
  expect(button.classList.contains("is-cancel-action")).toBe(true);
  expect(button.classList.contains("is-launching")).toBe(true);
  w.App.syncSendButtonRunning();
  expect(button.querySelector("svg")).toBe(stop);
  vi.advanceTimersByTime(900);
  expect(button.classList.contains("is-launching")).toBe(false);

  running = false;
  w.App.syncSendButtonRunning();
  expect(button.querySelector("path")).not.toBeNull();
  expect(button.classList.contains("is-cancel-action")).toBe(false);
  expect(button.classList.contains("is-launching")).toBe(false);
  vi.useRealTimers();
});
