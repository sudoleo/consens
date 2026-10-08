import { describe, expect, it, vi } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

const CHAT = "a".repeat(32);

function boot() {
  const setup = loadScripts(["static/js/agent-live.js"]);
  setup.window.App.agentLive.SILENCE_MS = 20;
  setup.window.App.agentLive.POLL_MS = 10;
  setup.window.App.agentLive.RUNNING_ELSEWHERE_MS = 10;
  setup.window.App.agentLive.GONE_MS = 30;
  setup.window.App.agentLive.STREAM_QUIET_MS = 200;
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

  it("keeps following a turn through network errors and ends with its final frame", async () => {
    const { window: w, dom } = boot();
    const final = { response: "Answer", turn: { id: "t", consensus: "Answer" } };
    let calls = 0;
    w.fetch = vi.fn(async () => {
      calls += 1;
      if (calls <= 3) throw new TypeError("Failed to fetch");
      return reply({ known: true, done: true, last_seq: 5, reset: { seq: 3, text: "So far " },
        events: [{ seq: 4, type: "delta", data: { text: "and more" } }, { seq: 5, type: "final", data: final }] });
    });
    const states = [];
    const tokens = ["t1", "t2", "t3", "t4"];
    const { live, delivered, options } = watcher(w, { headers: async () => ({ Authorization: `Bearer ${tokens.shift()}` }),
      onState: state => states.push(state) });
    live.reconnect();
    await expect(live.finished).resolves.toEqual({ ok: true, status: 200, data: final, streamed: true });
    expect(delivered).toEqual([["reset", { text: "So far " }, 3], ["delta", { text: "and more" }, 4]]);
    // Every poll asks for a fresh token; offline polls are no verdict.
    expect(w.fetch.mock.calls.map(call => call[1].headers.Authorization)).toEqual(["Bearer t1", "Bearer t2", "Bearer t3", "Bearer t4"]);
    expect(options.recover).not.toHaveBeenCalled();
    expect(states.some(state => state.reconnecting && state.offline)).toBe(true);
    expect(states.at(-1)).toEqual({ reconnecting: false, offline: false });
    expect(options.onEngage).not.toHaveBeenCalled();
    dom.window.close();
  });

  it("polls at once when the network returns or the tab becomes visible", async () => {
    const { window: w, dom } = boot();
    w.App.agentLive.POLL_MS = 400; // backoff far longer than the test waits
    w.fetch = vi.fn(async () => { throw new TypeError("Failed to fetch"); });
    const { live } = watcher(w);
    live.reconnect();
    await vi.waitFor(() => expect(w.fetch).toHaveBeenCalledTimes(1));
    await new Promise(resolve => setTimeout(resolve, 20));
    w.dispatchEvent(new w.Event("online"));
    await vi.waitFor(() => expect(w.fetch).toHaveBeenCalledTimes(2));
    w.document.dispatchEvent(new w.Event("visibilitychange"));
    await vi.waitFor(() => expect(w.fetch).toHaveBeenCalledTimes(3));
    live.stop();
    await expect(live.finished).resolves.toBe(null);
    dom.window.close();
  });

  it("follows the saved turn when this server does not hold it", async () => {
    const { window: w, dom } = boot();
    w.fetch = vi.fn(async () => reply({ known: false, done: false, last_seq: 0, events: [] }));
    const saved = { ok: true, status: 200, streamed: false, data: { turn: { id: "t" }, response: "Saved" } };
    const answers = ["running", "offline", "running", saved];
    const { live, options } = watcher(w, { recover: vi.fn(async () => answers.shift()) });
    live.reconnect();
    await expect(live.finished).resolves.toBe(saved);
    expect(options.recover).toHaveBeenCalledTimes(4);
    dom.window.close();
  });

  it("ends a followed turn with null when it is gone for good", async () => {
    const { window: w, dom } = boot();
    w.fetch = vi.fn(async () => reply({ known: false, done: false, last_seq: 0, events: [] }));
    const { live, options } = watcher(w);
    const started = Date.now();
    live.reconnect();
    await expect(live.finished).resolves.toBe(null);
    // Not before three answers and the grace time: a turn may still be in preparation.
    expect(options.recover.mock.calls.length).toBeGreaterThanOrEqual(3);
    expect(Date.now() - started).toBeGreaterThanOrEqual(30);
    expect(live.reconnecting).toBe(false);
    dom.window.close();
  });

  it("never runs two polls at once and resolves null when its signal aborts", async () => {
    const { window: w, dom } = boot();
    let release;
    w.fetch = vi.fn(() => new Promise(resolve => { release = () => resolve(reply({ known: true, done: false, last_seq: 0, events: [] })); }));
    const controller = new w.AbortController();
    const { live } = watcher(w, { signal: controller.signal });
    live.reconnect();
    await vi.waitFor(() => expect(w.fetch).toHaveBeenCalledTimes(1));
    w.dispatchEvent(new w.Event("online"));
    live.reconnect();
    await new Promise(resolve => setTimeout(resolve, 20));
    expect(w.fetch).toHaveBeenCalledTimes(1);
    release();
    controller.abort();
    await expect(live.finished).resolves.toBe(null);
    dom.window.close();
  });

  it("can still reconnect after the buffering fallback gave up", async () => {
    const { window: w, dom } = boot();
    const final = { response: "Answer", turn: { id: "t" } };
    let known = false;
    w.fetch = vi.fn(async () => reply(known
      ? { known: true, done: true, last_seq: 1, events: [{ seq: 1, type: "final", data: final }] }
      : { known: false, done: false, last_seq: 0, events: [] }));
    const { live } = watcher(w);
    await vi.waitFor(() => expect(w.fetch).toHaveBeenCalledTimes(4));
    await new Promise(resolve => setTimeout(resolve, 40));
    expect(live.polling).toBe(false);
    known = true; // the turn's buffer exists now; then the stream breaks
    live.reconnect();
    await expect(live.finished).resolves.toEqual({ ok: true, status: 200, data: final, streamed: true });
    dom.window.close();
  });

  it("holds polls back while the stream still delivers bytes", async () => {
    const { window: w, dom } = boot();
    w.fetch = vi.fn(async () => reply({ known: true, done: false, last_seq: 0, events: [] }));
    const { live } = watcher(w);
    live.reconnect();
    live.bytes(); // the stream answered right after all
    const ticker = setInterval(() => live.bytes(), 20);
    await new Promise(resolve => setTimeout(resolve, 150));
    const during = w.fetch.mock.calls.length;
    expect(during).toBeLessThanOrEqual(2);
    clearInterval(ticker);
    // Silent longer than STREAM_QUIET_MS: polling resumes.
    await vi.waitFor(() => expect(w.fetch.mock.calls.length).toBeGreaterThan(during), { timeout: 1000 });
    live.stop();
    dom.window.close();
  });

  it("checks a turn running elsewhere less and less often", async () => {
    const { window: w, dom } = boot();
    w.fetch = vi.fn(async () => reply({ known: false, done: false, last_seq: 0, events: [] }));
    const times = [];
    const { live } = watcher(w, { recover: vi.fn(async () => { times.push(Date.now()); return "running"; }) });
    live.reconnect();
    await vi.waitFor(() => expect(times.length).toBeGreaterThanOrEqual(4), { timeout: 2000 });
    const gaps = times.slice(1).map((time, index) => time - times[index]);
    expect(gaps[2]).toBeGreaterThan(gaps[0]);
    live.stop();
    dom.window.close();
  });

  it("delivers lasting frames from the dropped window before the reset", async () => {
    const { window: w, dom } = boot();
    w.fetch = vi.fn(async () => reply({ known: true, done: false, last_seq: 7,
      reset: { seq: 6, text: "So far", frames: [{ seq: 1, type: "accepted", data: { turn_id: "t" } }, { seq: 4, type: "quota", data: { token_budget: {} } }] },
      events: [{ seq: 7, type: "delta", data: { text: "!" } }] }));
    const { live, delivered } = watcher(w);
    live.reconnect();
    await vi.waitFor(() => expect(delivered.map(item => item[2])).toEqual([1, 4, 6, 7]));
    expect(delivered.map(item => item[0])).toEqual(["accepted", "quota", "reset", "delta"]);
    live.stop();
    dom.window.close();
  });
});
