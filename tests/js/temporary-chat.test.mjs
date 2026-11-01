import { describe, expect, it, vi } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

// A temporary chat (temporary-chat.js): the switch of a new Agent chat, its
// words, the field's dashed rim, and its end. Leaving it (whatever takes it
// off the screen in the run registry) or reloading deletes it on the server.
const MARKUP = `
  <button type="button" id="temporaryChatButton" aria-pressed="false" hidden></button>
  <p id="temporaryChatNote" hidden></p>
  <div class="chat-input-container" style="border-top-left-radius: 25px; border-top-width: 1px">
    <svg class="composer-dashed-edge"><rect></rect></svg>
    <textarea id="questionInput"></textarea>
  </div>`;

const pressed = document => document.getElementById("temporaryChatButton").getAttribute("aria-pressed");

// One bus for the windows of a test: BroadcastChannel between tabs.
function channelBus() {
  const members = new Set();
  return class FakeChannel {
    constructor(name) { this.name = name; this.listeners = new Set(); members.add(this); }
    addEventListener(type, listener) { if (type === "message") this.listeners.add(listener); }
    removeEventListener(type, listener) { this.listeners.delete(listener); }
    postMessage(data) {
      for (const other of members) {
        if (other !== this && other.name === this.name) setTimeout(() => other.listeners.forEach(l => l({ data })), 0);
      }
    }
  };
}

// The field's box and the rim's length, which jsdom does not lay out: a
// rounded rect's perimeter, and a ResizeObserver that reports at once.
function geometry(window, { width, height }) {
  const field = window.document.querySelector(".chat-input-container");
  Object.defineProperty(field, "clientWidth", { configurable: true, get: () => width });
  Object.defineProperty(field, "clientHeight", { configurable: true, get: () => height });
  const rect = field.querySelector("rect");
  rect.getTotalLength = () => {
    const [w, h, r] = ["width", "height", "rx"].map(name => Number(rect.getAttribute(name)));
    return 2 * (w + h) - (8 - 2 * Math.PI) * r;
  };
  window.ResizeObserver = class {
    constructor(callback) { this.callback = callback; window.__observers = (window.__observers || 0) + 1; }
    observe() { this.callback([]); }
    disconnect() { window.__observers -= 1; }
  };
  return { field, rect };
}

function boot({ stored = null, channel = null, armed = false, box = null } = {}) {
  const user = { uid: "user-a", getIdToken: vi.fn(async () => "token-a") };
  const fetch = vi.fn(async () => ({ ok: true, status: 200 }));
  const harness = loadScripts(["static/js/run-registry.js", "static/js/temporary-chat.js"], {
    body: MARKUP,
    before(window) {
      window.App = {
        authState: { uid: user.uid, generation: 1, snapshot: () => ({ uid: user.uid, generation: 1 }) },
        agentChat: { isSelected: () => true, syncComposer: vi.fn() },
      };
      window.auth = { currentUser: user };
      window.fetch = fetch;
      if (channel) window.BroadcastChannel = channel;
      if (armed) window.sessionStorage.setItem("consens.temporaryChat.armed.v1", "1");
      if (stored) window.sessionStorage.setItem("consens.temporaryChat.v1", JSON.stringify(stored));
      if (box) geometry(window, box);
    },
  });
  const { window } = harness;
  return { ...harness, fetch, temporary: window.App.temporaryChat, registry: window.App.runRegistry };
}

function run(registry, token) {
  return registry.create({ question: "Q", mode: "Agent", bookmarkId: "b_agent_1",
    config: { executionMode: "agent", temporary: Boolean(token) }, metadata: token ? { temporaryToken: token } : {} });
}

const deletes = fetch => fetch.mock.calls.filter(([, init]) => init?.method === "DELETE").map(([url, init]) => [url, init.keepalive]);
const settle = () => new Promise(resolve => setTimeout(resolve, 0));

describe("App.temporaryChat", () => {
  it("is chosen on a new Agent chat only, at the top right, and says so", () => {
    const { temporary, document, window } = boot();
    temporary.sync();
    const button = document.getElementById("temporaryChatButton");
    expect(button.hidden).toBe(false);
    expect(pressed(document)).toBe("false");
    button.click();
    expect(temporary.armed()).toBe(true);
    expect(pressed(document)).toBe("true");
    expect(document.body.classList.contains("temporary-chat")).toBe(true);
    expect(window.App.agentChat.syncComposer).toHaveBeenCalled();
    // A second click takes it back.
    button.click();
    expect(temporary.armed()).toBe(false);
    expect(pressed(document)).toBe("false");
    expect(document.body.classList.contains("temporary-chat")).toBe(false);
    // Compare has none: the switch goes off with the mode.
    button.click();
    window.App.agentChat.isSelected = () => false;
    temporary.sync();
    expect(temporary.armed()).toBe(false);
    expect(button.hidden).toBe(true);
  });

  it("lives while its runs are on screen and is deleted once the user leaves it", async () => {
    const { temporary, registry, fetch, document, window } = boot();
    temporary.sync();
    temporary.arm(true);
    const token = temporary.start();
    const first = run(registry, token);
    expect(temporary.adopt(token, "chat-1")).toBe(true);
    expect(JSON.parse(window.sessionStorage.getItem("consens.temporaryChat.v1"))).toEqual({ chatId: "chat-1", uid: "user-a" });
    expect(temporary.token("chat-1")).toBe(token);
    // In the chat the switch says so and stays on (a click turns nothing
    // off); the note stands under the field.
    const button = document.getElementById("temporaryChatButton");
    expect(button.hidden).toBe(false);
    expect(pressed(document)).toBe("true");
    expect(button.getAttribute("aria-disabled")).toBe("true");
    button.click();
    expect(temporary.current()).toEqual({ token, chatId: "chat-1" });
    expect(pressed(document)).toBe("true");
    expect(document.getElementById("temporaryChatNote").hidden).toBe(false);
    // A follow-up of the same chat keeps it.
    run(registry, token);
    expect(temporary.current()).toEqual({ token, chatId: "chat-1" });
    expect(deletes(fetch)).toEqual([]);
    // New chat: off the screen, so it ends, its run stops and the server deletes it.
    registry.clearVisible();
    await settle();
    expect(temporary.current()).toBeNull();
    expect(registry.get(first.runId).status).not.toBe("running");
    expect(deletes(fetch)).toEqual([["/chats/chat-1", true]]);
    expect(window.sessionStorage.getItem("consens.temporaryChat.v1")).toBeNull();
    expect(document.body.classList.contains("temporary-chat")).toBe(false);
  });

  it("deletes a chat the server created after the user had left it", async () => {
    const { temporary, registry, fetch } = boot();
    temporary.arm(true);
    const token = temporary.start();
    run(registry, token);
    run(registry, "");
    expect(temporary.current()).toBeNull();
    expect(temporary.adopt(token, "late-chat")).toBe(false);
    await settle();
    expect(deletes(fetch)).toEqual([["/chats/late-chat", true]]);
  });

  it("ends with a reload: the chat this tab had is deleted once its account is known", async () => {
    const { fetch, window } = boot({ stored: { chatId: "chat-9", uid: "user-a" } });
    expect(window.sessionStorage.getItem("consens.temporaryChat.v1")).toBeNull();
    window.dispatchEvent(new window.CustomEvent("consensio:auth-state", { detail: { known: true, uid: "user-a" } }));
    await settle();
    expect(deletes(fetch)).toEqual([["/chats/chat-9", true]]);
  });

  it("leaves another account's chat to the server's deadline", async () => {
    const { fetch, window } = boot({ stored: { chatId: "chat-9", uid: "someone-else" } });
    window.dispatchEvent(new window.CustomEvent("consensio:auth-state", { detail: { known: true, uid: "user-a" } }));
    await settle();
    expect(deletes(fetch)).toEqual([]);
  });
});

describe("App.temporaryChat's dashed field", () => {
  it.each([
    ["the start screen's box", { width: 768, height: 140 }],
    ["a phone's pill", { width: 343, height: 50 }],
  ])("fits whole dashes around %s, the seam in a gap", (_, box) => {
    const { temporary, document, window } = boot({ box });
    temporary.sync();
    expect(window.__observers || 0).toBe(0);
    temporary.arm(true);
    expect(window.__observers).toBe(1);
    const rect = document.querySelector(".composer-dashed-edge rect");
    // On the rim, just inside the field's edge, in its inner radius.
    expect(rect.getAttribute("x")).toBe("0.5");
    expect(Number(rect.getAttribute("width"))).toBe(box.width - 1);
    expect(Number(rect.getAttribute("height"))).toBe(box.height - 1);
    expect(Number(rect.getAttribute("rx"))).toBe(Math.min(23.5, (box.height - 1) / 2));
    const [dash, gap] = rect.style.strokeDasharray.split(" ").map(Number);
    const length = rect.getTotalLength();
    // A whole number of dashes: the pattern closes without a stub.
    const count = length / (dash + gap);
    expect(Math.abs(count - Math.round(count))).toBeLessThan(1e-9);
    // Close to the drawn 4.5 / 3.5, and the seam in the middle of a gap.
    expect(dash / (dash + gap)).toBeCloseTo(4.5 / 8, 9);
    expect(Math.abs(dash + gap - 8)).toBeLessThan(0.5);
    expect(Number(rect.style.strokeDashoffset)).toBeCloseTo(dash + gap / 2, 9);
    // Switched off, it stops following the field.
    temporary.arm(false);
    expect(window.__observers).toBe(0);
  });
});

describe("App.temporaryChat retries", () => {
  it("deletes the chat a retried first message replaced", async () => {
    const { temporary, registry, fetch } = boot();
    temporary.arm(true);
    const token = temporary.start();
    run(registry, token);
    expect(temporary.adopt(token, "first-chat")).toBe(true);
    expect(temporary.adopt(token, "second-chat")).toBe(true);
    await settle();
    expect(deletes(fetch)).toEqual([["/chats/first-chat", true]]);
    expect(temporary.current()).toEqual({ token, chatId: "second-chat" });
  });
});

describe("App.temporaryChat in a duplicated tab", () => {
  it("leaves a chat its original tab still has open, and deletes one nobody has", async () => {
    const channel = channelBus();
    const original = boot({ channel });
    original.temporary.arm(true);
    const token = original.temporary.start();
    run(original.registry, token);
    original.temporary.adopt(token, "chat-open");
    // The copy starts with the same sessionStorage.
    const copy = boot({ channel, stored: { chatId: "chat-open", uid: "user-a" } });
    copy.window.dispatchEvent(new copy.window.CustomEvent("consensio:auth-state", { detail: { known: true, uid: "user-a" } }));
    await new Promise(resolve => setTimeout(resolve, 600));
    expect(deletes(copy.fetch)).toEqual([]);
    expect(original.temporary.current()).toEqual({ token, chatId: "chat-open" });
    // A reload: nobody else has it.
    const reloaded = boot({ channel, stored: { chatId: "chat-gone", uid: "user-a" } });
    reloaded.window.dispatchEvent(new reloaded.window.CustomEvent("consensio:auth-state", { detail: { known: true, uid: "user-a" } }));
    await new Promise(resolve => setTimeout(resolve, 600));
    expect(deletes(reloaded.fetch)).toEqual([["/chats/chat-gone", true]]);
  });
});

describe("App.temporaryChat after the review of 2026-11-01", () => {
  it("keeps a chat temporary whose first message did not get through", () => {
    const { temporary, registry } = boot();
    temporary.arm(true);
    const token = temporary.start();
    const first = run(registry, token);
    registry.setStatus(first.runId, "failed");
    // The switch is spent, but the chat on screen is still the temporary one:
    // agent-chat.js starts it anew instead of sending a saved chat.
    expect(temporary.armed()).toBe(false);
    expect(temporary.unanswered()).toBe(true);
    registry.clearVisible();
    expect(temporary.unanswered()).toBe(false);
  });

  it("keeps the switch through a reload of this tab, as at a guest's sign-in", () => {
    const first = boot();
    first.temporary.sync();
    first.temporary.arm(true);
    expect(first.window.sessionStorage.getItem("consens.temporaryChat.armed.v1")).toBe("1");
    const again = boot({ armed: true });
    again.temporary.sync();
    expect(again.temporary.armed()).toBe(true);
    expect(pressed(again.document)).toBe("true");
    again.temporary.start();
    expect(again.window.sessionStorage.getItem("consens.temporaryChat.armed.v1")).toBeNull();
  });

  it("tries a failed delete again and gives up on a refusal for good", async () => {
    vi.useFakeTimers();
    try {
      const { temporary, registry, fetch } = boot();
      fetch.mockResolvedValueOnce({ ok: false, status: 503 }).mockResolvedValueOnce({ ok: true, status: 200 });
      temporary.arm(true);
      const token = temporary.start();
      run(registry, token);
      temporary.adopt(token, "chat-retry");
      const left = temporary.leave("test");
      await vi.advanceTimersByTimeAsync(3000);
      expect(await left).toBe(true);
      expect(deletes(fetch)).toEqual([["/chats/chat-retry", true], ["/chats/chat-retry", true]]);
    } finally {
      vi.useRealTimers();
    }
  });
});
