import { describe, expect, it, vi } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

const CHAT = "a".repeat(32);

function boot() {
  const setup = loadScripts(["static/js/agent-live.js"]);
  setup.window.App.agentLive.SILENCE_MS = 20;
  setup.window.App.agentLive.POLL_MS = 10;
  return setup;
}

function reply(body, status = 200) {
  return { ok: status < 400, status, json: async () => structuredClone(body) };
}

function watcher(w, overrides = {}) {
  const delivered = [];
  const seen = w.App.agentLive.sequence();
  const options = {
    chatId: CHAT, requestId: "req-1", headers: { Authorization: "Bearer t" },
    signal: new w.AbortController().signal,
    deliver: (type, data, seq) => { if (seen.accept(seq)) delivered.push([type, data, seq]); },
    cursor: () => seen.last, onEngage: vi.fn(), recover: vi.fn(async () => null), ...overrides,
  };
  return { live: w.App.agentLive.watch(options), delivered, options, seen };
}

describe("agent live fallback", () => {
  it("accepts every sequence number once and frames without one always", () => {
    const { window: w, dom } = boot();
    const seen = w.App.agentLive.sequence();
    expect([1, 2, 2, 1, 3].map(seq => seen.accept(seq))).toEqual([true, true, false, false, true]);
    expect(seen.accept(undefined)).toBe(true);
    expect(seen.accept("4")).toBe(true);
    expect(seen.accept("4")).toBe(false);
    expect(seen.last).toBe(4);
    dom.window.close();
  });

  it("polls after a silent start and feeds the frames in order", async () => {
    const { window: w, dom } = boot();
    const pages = [
      { known: true, done: false, last_seq: 2, events: [
        { seq: 1, type: "accepted", data: { chat_id: CHAT, turn_id: "t" } },
        { seq: 2, type: "activity", data: { kind: "reasoning", text: "Thinking about it" } }] },
      { known: true, done: false, last_seq: 3, events: [{ seq: 3, type: "delta", data: { text: "Partial" } }] },
      { known: true, done: false, last_seq: 3, events: [] },
    ];
    w.fetch = vi.fn(async () => reply(pages.length > 1 ? pages.shift() : pages[0]));
    const { live, delivered, options } = watcher(w);
    expect(w.fetch).not.toHaveBeenCalled();
    await vi.waitFor(() => expect(delivered.map(item => item[2])).toEqual([1, 2, 3]));
    const urls = w.fetch.mock.calls.map(call => call[0]);
    expect(urls[0]).toBe(`/agent/chats/${CHAT}/live?request_id=req-1&after=0`);
    expect(urls[1]).toContain("after=2");
    expect(w.fetch.mock.calls[0][1].headers).toEqual({ Authorization: "Bearer t" });
    expect(options.onEngage).toHaveBeenCalledTimes(1);
    expect(live.polling).toBe(true);
    // A late flush of the buffered stream through the same guard adds nothing.
    for (const [type, data, seq] of [...delivered]) options.deliver(type, data, String(seq));
    expect(delivered).toHaveLength(3);
    live.stop();
    const calls = w.fetch.mock.calls.length;
    await new Promise(resolve => setTimeout(resolve, 60));
    expect(w.fetch.mock.calls.length).toBe(calls);
    dom.window.close();
  });

  it("never polls when the stream answers in time, and pauses when bytes resume", async () => {
    const { window: w, dom } = boot();
    w.fetch = vi.fn(async () => reply({ known: true, done: false, last_seq: 0, events: [] }));
    const quick = watcher(w);
    quick.live.bytes();
    await new Promise(resolve => setTimeout(resolve, 60));
    expect(w.fetch).not.toHaveBeenCalled();
    expect(quick.options.onEngage).not.toHaveBeenCalled();
    quick.live.stop();

    const slow = watcher(w);
    await vi.waitFor(() => expect(w.fetch).toHaveBeenCalled());
    await vi.waitFor(() => expect(slow.options.onEngage).toHaveBeenCalled());
    slow.live.bytes(); // the proxy released the stream
    expect(slow.live.polling).toBe(false);
    const calls = w.fetch.mock.calls.length;
    await new Promise(resolve => setTimeout(resolve, 15));
    expect(w.fetch.mock.calls.length).toBe(calls);
    // Renewed silence on a network known to buffer resumes polling.
    await vi.waitFor(() => expect(w.fetch.mock.calls.length).toBeGreaterThan(calls));
    slow.live.stop();
    dom.window.close();
  });

  it("finishes with the terminal frame exactly like the stream would", async () => {
    const { window: w, dom } = boot();
    const final = { response: "Answer", turn: { id: "t", consensus: "Answer" }, bookmark_meta: { id: "b" } };
    w.fetch = vi.fn(async () => reply({ known: true, done: true, last_seq: 2, events: [
      { seq: 1, type: "delta", data: { text: "Answer" } }, { seq: 2, type: "final", data: final }] }));
    const { live, delivered, options } = watcher(w);
    await expect(live.finished).resolves.toEqual({ ok: true, status: 200, data: final, streamed: true });
    expect(delivered.map(item => item[0])).toEqual(["delta"]);
    expect(options.recover).not.toHaveBeenCalled();
    dom.window.close();
  });

  it("asks for the saved answer when the run is done without a terminal frame", async () => {
    const { window: w, dom } = boot();
    const saved = { ok: true, status: 200, streamed: false, data: { turn: { id: "t" }, response: "Saved" } };
    w.fetch = vi.fn(async () => reply({ known: true, done: true, last_seq: 1, events: [{ seq: 1, type: "accepted", data: {} }] }));
    const { live, options } = watcher(w, { recover: vi.fn(async () => saved) });
    await expect(live.finished).resolves.toBe(saved);
    expect(options.recover).toHaveBeenCalledTimes(1);
    expect(w.fetch).toHaveBeenCalledTimes(1);
    dom.window.close();
  });

  it("gives up on a process without the run and stops on abort", async () => {
    const { window: w, dom } = boot();
    w.fetch = vi.fn(async () => reply({ known: false, done: false, last_seq: 0, events: [] }));
    const unknown = watcher(w);
    await vi.waitFor(() => expect(w.fetch).toHaveBeenCalledTimes(4));
    await new Promise(resolve => setTimeout(resolve, 60));
    expect(w.fetch).toHaveBeenCalledTimes(4);
    expect(unknown.live.polling).toBe(false);
    expect(unknown.options.onEngage).not.toHaveBeenCalled();

    w.fetch = vi.fn(async () => reply({ known: true, done: false, last_seq: 0, events: [] }));
    const controller = new w.AbortController();
    const aborted = watcher(w, { signal: controller.signal });
    await vi.waitFor(() => expect(w.fetch).toHaveBeenCalled());
    controller.abort();
    const calls = w.fetch.mock.calls.length;
    await new Promise(resolve => setTimeout(resolve, 60));
    expect(w.fetch.mock.calls.length).toBe(calls);
    expect(aborted.live.polling).toBe(false);
    dom.window.close();
  });
});
