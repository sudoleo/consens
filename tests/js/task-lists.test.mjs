import { describe, expect, it, vi } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

// Checklists in an answer ("- [ ] item"): markdown-stream.js draws the boxes,
// task-checks.js lets the answer of a saved turn keep its ticks.

function manualTimers(window) {
  const queue = new Map();
  let next = 0;
  window.setTimeout = (fn, ms) => { queue.set(++next, { fn, ms }); return next; };
  window.clearTimeout = handle => { queue.delete(handle); };
  return {
    delays: () => [...queue.values()].map(item => item.ms),
    run() {
      const items = [...queue.values()];
      queue.clear();
      items.forEach(item => item.fn());
    },
  };
}

function boot({ withChecks = true } = {}) {
  let timers;
  const fetch = vi.fn(async () => ({ ok: true, status: 200, json: async () => ({}) }));
  const app = loadScripts([
    "static/vendor/marked/12.0.2/marked.min.js",
    "static/vendor/dompurify/3.4.17/dist/purify.min.js",
    "static/js/markdown-stream.js",
    ...(withChecks ? ["static/js/task-checks.js"] : []),
  ], {
    before(window) {
      timers = manualTimers(window);
      window.fetch = fetch;
      window.auth = { currentUser: { getIdToken: async () => "token-1" } };
    },
  });
  return { ...app, fetch, timers };
}

const LIST = "Before you go:\n\n- [ ] Pack the **passport**\n- [x] Book the train\n- Bring snacks\n";
const flush = () => new Promise(resolve => setTimeout(resolve, 0));

describe("checklist boxes", () => {
  it("draws each item's box as a button the model's markup never made", () => {
    const { window, document } = boot();
    const el = document.createElement("div");
    window.injectMarkdown(el, LIST, []);
    const boxes = el.querySelectorAll(".md-task-box");
    expect(boxes).toHaveLength(2);
    expect([...boxes].map(box => box.getAttribute("aria-checked"))).toEqual(["false", "true"]);
    expect(boxes[0].tagName).toBe("BUTTON");
    expect(boxes[0].getAttribute("role")).toBe("checkbox");
    expect(boxes[0].getAttribute("aria-label")).toBe("Pack the passport");
    // Without a saved turn nothing can be ticked.
    expect([...boxes].every(box => box.disabled)).toBe(true);
    expect(el.querySelector("ul").classList.contains("md-task-list")).toBe(true);
    expect([...el.querySelectorAll("li")].map(li => li.classList.contains("md-task-item"))).toEqual([true, true, false]);
    expect(el.textContent).not.toContain("[");
    expect(el.querySelector("input, .md-task")).toBeNull();
  });

  it("keeps forbidding form fields and markers the model writes itself", () => {
    const { window, document } = boot();
    const el = document.createElement("div");
    window.injectMarkdown(el, 'A <input type="checkbox"> and <span class="md-task" data-checked="true"></span> here.\n\n- item <span class="md-task"></span>\n', []);
    expect(el.querySelector("input")).toBeNull();
    // A marker that does not lead its list item is dropped, never a box.
    expect(el.querySelectorAll(".md-task, .md-task-box")).toHaveLength(0);
  });

  it("shows no bracket while a box streams in and ends like a full render", () => {
    const { window, document } = boot();
    const el = document.createElement("div");
    window.renderMarkdownStream(el, "Steps:\n\n- [");
    expect(el.textContent).not.toContain("[");
    expect(el.querySelector("li")).toBeNull();
    window.renderMarkdownStream(el, "Steps:\n\n- [ ]");
    expect(el.querySelectorAll(".md-task-box")).toHaveLength(1);
    expect(el.textContent).not.toContain("[");
    window.renderMarkdownStream(el, "Steps:\n\n- [ ] Pack");
    const box = el.querySelector(".md-task-box");
    window.renderMarkdownStream(el, "Steps:\n\n- [ ] Pack the bag\n- [x");
    // The box the reader saw is the same button, not a new one.
    expect(el.querySelector(".md-task-box")).toBe(box);
    expect(el.querySelectorAll(".md-task-box")).toHaveLength(1);
    const text = "Steps:\n\n- [ ] Pack the bag\n- [x] Lock the door\n\nThen go.\n";
    window.renderMarkdownStream(el, text);
    const full = document.createElement("div");
    window.injectMarkdown(full, text, []);
    expect(el.innerHTML).toBe(full.innerHTML);
    // "- [Title](url)" still becomes a link after waiting for its bracket.
    const links = document.createElement("div");
    window.renderMarkdownStream(links, "- [");
    window.renderMarkdownStream(links, "- [Docs](https://example.com) here");
    expect(links.querySelector("a")?.textContent).toBe("Docs");
    expect(links.querySelector(".md-task-box")).toBeNull();
  });
});

describe("ticks of a saved turn", () => {
  it("can be ticked once the answer names its turn and are saved as one list", async () => {
    const { window, document, fetch, timers } = boot();
    const el = document.createElement("div");
    el.className = "consensus-answer-body";
    document.body.append(el);
    window.App.taskChecks.scope(el, { chatId: "c".repeat(32), turnId: "t".repeat(32) });
    window.injectMarkdown(el, LIST, []);
    const boxes = el.querySelectorAll(".md-task-box");
    expect([...boxes].every(box => !box.disabled)).toBe(true);
    boxes[0].click();
    expect(boxes[0].getAttribute("aria-checked")).toBe("true");
    boxes[1].click();
    expect(boxes[1].getAttribute("aria-checked")).toBe("false");
    boxes[1].click();
    expect(fetch).not.toHaveBeenCalled();
    expect(timers.delays()).toEqual([600]);
    timers.run();
    await flush();
    expect(fetch).toHaveBeenCalledTimes(1);
    const [url, init] = fetch.mock.calls[0];
    expect(url).toBe(`/chats/${"c".repeat(32)}/turns/${"t".repeat(32)}/task-checks`);
    expect(init.method).toBe("PUT");
    expect(init.headers.Authorization).toBe("Bearer token-1");
    // "[x]" counted as ticked from the start; the list holds every tick.
    expect(JSON.parse(init.body)).toEqual({ checked: [0, 1] });
  });

  it("keeps a tick through a new render of the same answer and wins over older turn data", () => {
    const { window, document } = boot();
    const el = document.createElement("div");
    el.className = "consensus-answer-body";
    document.body.append(el);
    const turn = { chatId: "a".repeat(32), turnId: "b".repeat(32) };
    window.App.taskChecks.scope(el, { ...turn, checked: [] });
    window.injectMarkdown(el, LIST, []);
    el.querySelector(".md-task-box").click();
    window.morphMarkdown(el, LIST);
    expect([...el.querySelectorAll(".md-task-box")].map(box => box.getAttribute("aria-checked"))).toEqual(["true", "false"]);
    // A re-render from the chat loaded before the tick does not undo it.
    window.App.taskChecks.scope(el, { ...turn, checked: [] });
    window.injectMarkdown(el, LIST, []);
    expect(el.querySelector(".md-task-box").getAttribute("aria-checked")).toBe("true");
  });

  it("shows a turn's saved ticks and leaves other answers' boxes alone", () => {
    const { window, document } = boot();
    const el = document.createElement("div");
    el.className = "consensus-answer-body";
    const earlier = document.createElement("div");
    earlier.className = "consensus-answer-body";
    document.body.append(el);
    window.App.taskChecks.scope(el, { turnId: "d".repeat(32), checked: [0] });
    window.injectMarkdown(el, LIST, []);
    window.injectMarkdown(earlier, "- [ ] An earlier version\n", []);
    el.prepend(earlier);
    const own = [...el.querySelectorAll(":scope > ul .md-task-box")];
    expect(own.map(box => box.getAttribute("aria-checked"))).toEqual(["true", "false"]);
    expect(earlier.querySelector(".md-task-box").disabled).toBe(true);
    // An answer without a turn again: nothing to tick.
    window.App.taskChecks.scope(el, {});
    expect(own.every(box => box.disabled)).toBe(true);
  });

  it("draws boxes without the tick module, none of them tickable", () => {
    const { window, document } = boot({ withChecks: false });
    const el = document.createElement("div");
    window.injectMarkdown(el, LIST, []);
    expect([...el.querySelectorAll(".md-task-box")].every(box => box.disabled)).toBe(true);
  });
});
