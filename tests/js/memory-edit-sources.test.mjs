/**
 * The selection toolbar (Ask about this / Remember / Correct) belongs to every
 * answer, including the Agent answer that is currently on screen, not only to
 * answers that already moved into the chat history.
 */
import { afterEach, expect, it } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

const contexts = [];
afterEach(() => contexts.splice(0).forEach(ctx => ctx.window.close()));

function boot(body) {
  const ctx = loadScripts(["static/js/memory-edit.js"], { body: body + '<textarea id="questionInput"></textarea>', before(window) {
    window.auth = { currentUser: null };
    window.App = { quote: { set() {} } };
    window.Range.prototype.getBoundingClientRect = () => ({ left: 10, top: 10, bottom: 20, right: 60, width: 50, height: 10 });
  } });
  ctx.window.document.dispatchEvent(new ctx.window.Event("DOMContentLoaded"));
  contexts.push(ctx);
  return ctx;
}

function select(ctx, element) {
  const range = ctx.document.createRange();
  range.selectNodeContents(element);
  const selection = ctx.window.getSelection();
  selection.removeAllRanges();
  selection.addRange(range);
  element.dispatchEvent(new ctx.window.KeyboardEvent("keyup", { key: "Shift", bubbles: true }));
}

it.each([
  ["the current Agent answer", '<div id="agentAnswerBody"><p id="text">A current agent statement.</p></div>'],
  ["an earlier answer in the chat", '<div class="thread-history-answer"><p id="text">An earlier statement.</p></div>'],
])("offers Ask about this for %s", (_label, body) => {
  const ctx = boot(body);
  select(ctx, ctx.document.getElementById("text"));
  const menu = ctx.document.getElementById("memorySelectionMenu");
  expect(menu.hidden).toBe(false);
  expect(menu.querySelector('[data-selection-action="ask"]').hidden).toBe(false);
});
