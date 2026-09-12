import { describe, it, expect, vi } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

const frame = (event, data) => new TextEncoder().encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`);
function boot(reader, fetchError) {
  return loadScripts(["static/js/markdown-stream.js"], { before(window) {
    window.TextDecoder = TextDecoder;
    window.fetch = async () => {
      if (fetchError) throw fetchError;
      return { ok: true, status: 200, headers: { get: () => "text/event-stream" },
        body: { getReader: () => reader } };
    };
  } });
}

describe("SSE completion and failure diagnostics", () => {
  it.each(["final", "error"])("accepts %s without waiting for a later failing read", async (event) => {
    const data = event === "final" ? { consensus_response: "Complete" } : { error: "Provider failed" };
    const reader = { read: vi.fn().mockResolvedValueOnce({ value: frame(event, data) })
      .mockRejectedValue(new TypeError("network lost")),
      cancel: vi.fn().mockRejectedValue(new Error("cleanup failed")), releaseLock: vi.fn() };
    const { window, dom } = boot(reader);
    const result = await window.streamSSERequest("/consensus", {});
    expect(result.data).toEqual(data);
    expect(reader.read).toHaveBeenCalledTimes(1);
    expect(reader.cancel).toHaveBeenCalledOnce();
    expect(reader.releaseLock).toHaveBeenCalledOnce();
    dom.window.close();
  });

  it("keeps reading after consensus.final and keepalives until the persisted final", async () => {
    const chunks = [frame("consensus.final", { text: "Answer" }), new TextEncoder().encode(": keepalive\n\n"),
      frame("final", { consensus_response: "Answer", bookmark_persisted: true })];
    const reader = { read: vi.fn(async () => ({ value: chunks.shift() })) };
    const { window, dom } = boot(reader);
    const receive = vi.fn();
    const result = await window.streamSSERequest("/consensus", {}, undefined, { "consensus.final": { receive } });
    expect(receive).toHaveBeenCalledWith({ text: "Answer" });
    expect(result.data.bookmark_persisted).toBe(true);
    expect(reader.read).toHaveBeenCalledTimes(3);
    dom.window.close();
  });

  it.each([
    ["request_failed", null, new TypeError("fetch failed")],
    ["stream_read_failed", { read: async () => { throw new TypeError("read failed"); } }],
    ["stream_incomplete", { read: async () => ({ done: true }) }],
    ["stream_handler_failed", { read: async () => ({ value: frame("consensus.delta", { text: "Answer" }) }) }]
  ])("distinguishes %s and stops renderers", async (kind, reader, fetchError) => {
    const { window, dom } = boot(reader, fetchError);
    const stop = vi.fn();
    await expect(window.streamSSERequest("/consensus", {}, undefined, {
      "consensus.delta": { append() { throw new ReferenceError("render failed"); }, stop }
    })).rejects.toMatchObject({ streamFailureKind: kind });
    expect(stop).toHaveBeenCalledOnce();
    dom.window.close();
  });

  it("preserves deliberate cancellation as AbortError", async () => {
    const { window, dom } = boot(null, new DOMException("cancelled", "AbortError"));
    await expect(window.streamSSERequest("/consensus", {})).rejects.toMatchObject({ name: "AbortError" });
    dom.window.close();
  });
});
