import { describe, it, expect, vi } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

describe("judge SSE events", () => {
  it("delivers the differences before the final frame and completes without calling stop on structured receivers", async () => {
    const consensusStop = vi.fn(), differences = vi.fn();
    const original = { differences: "Original", differences_data: { agreement: { score: 88 } } };
    const frames = [
      ["differences.final", original],
      ["final", { consensus_response: "Consensus", ...original }]
    ];
    const { window, dom } = loadScripts(["static/js/markdown-stream.js"], {
      before(window) {
        window.TextDecoder = TextDecoder;
        window.fetch = async () => ({ ok: true, status: 200,
          headers: { get: () => "text/event-stream" }, body: { getReader: () => ({ read: async () => {
            const frame = frames.shift();
            if (frame?.[0] === "final") expect(differences).toHaveBeenCalledWith(original);
            return frame ? { done: false, value: new TextEncoder().encode(`event: ${frame[0]}\ndata: ${JSON.stringify(frame[1])}\n\n`) } : { done: true };
          } }) }
        });
      }
    });
    const result = await window.streamSSERequest("/consensus", {}, undefined, {
      "consensus.delta": { append: vi.fn(), stop: consensusStop },
      "differences.final": { receive: differences }
    });
    expect(result.ok).toBe(true);
    expect(result.data.differences_data).toEqual(original.differences_data);
    expect(consensusStop).toHaveBeenCalledOnce();
    dom.window.close();
  });
});
