import { describe, expect, it, vi } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

// query-send.js runs Compare only since 2026-10-25: the chosen models answer
// side by side, each finished answer is saved to the comparison's bookmark,
// and nothing continues a chat or writes a consensus (that pipeline runs on
// the server for Watches, the API and topics).
const BODY = `
  <textarea id="questionInput"></textarea>
  <button id="sendButton"></button>
  <input type="checkbox" id="reasoningToggle">
  <input type="checkbox" id="openaiCheck" checked>
  <select id="openaiSelect"><option value="gpt-x" selected>GPT X</option></select>
  <input type="checkbox" id="geminiCheck" checked>
  <select id="geminiSelect"><option value="gemini-x" selected>Gemini X</option></select>
`;

function boot() {
  const user = { uid: "owner", getIdToken: vi.fn(async () => "token") };
  const harness = loadScripts(["static/js/run-registry.js", "static/js/query-send.js"], {
    body: BODY,
    before(window) {
      window.auth = { currentUser: user };
      window.App = {
        authState: { generation: 1, snapshot: () => ({ uid: user.uid, generation: 1 }) },
        modelPrefs: [
          { key: "OpenAI", endpoint: "/ask_openai", responseId: "openaiResponse", checkId: "openaiCheck", selectId: "openaiSelect" },
          { key: "Gemini", endpoint: "/ask_gemini", responseId: "geminiResponse", checkId: "geminiCheck", selectId: "geminiSelect" },
        ],
        userSettings: { get: () => "" },
        state: { set: vi.fn() },
        getSelectedModelCount: () => 2,
        trackAppEvent: vi.fn(), trackAsk: vi.fn(), trackAnswer: vi.fn(),
        showPopup: vi.fn(),
      };
      window.fetch = vi.fn(async url => ({
        ok: true, status: 200,
        json: async () => (url === "/prepare" ? { system_prompt: "Server prompt" } : {}),
      }));
      window.App.readJson = response => response.json();
      window.streamSSERequest = vi.fn(async (url, payload) => ({
        ok: true, status: 200, streamed: true,
        data: { response: `Answer from ${url}`, completion: "complete", sources: [] },
      }));
      window.saveBookmark = vi.fn(async () => ({}));
    },
  });
  return { ...harness, user, registry: harness.window.App.runRegistry };
}

describe("Compare: the one run the browser starts besides Agent", () => {
  it("asks every chosen model, saves each answer and never writes a consensus", async () => {
    const { window, document, registry, dom } = boot();
    // A saved chat on screen is not continued: a comparison is a chat of its own.
    registry.selectConversationBasis({ chatId: "c".repeat(32), turnId: "t".repeat(32), bookmarkId: "saved",
      question: "Earlier", consensus: "Saved consensus", executionMode: "consensus" });
    document.getElementById("questionInput").value = "Which is right?";
    await window.sendQuestion();

    const prepare = window.fetch.mock.calls.find(([url]) => url === "/prepare");
    expect(JSON.parse(prepare[1].body)).toMatchObject({ run_mode: "compare", question: "Which is right?" });
    expect(JSON.parse(prepare[1].body)).not.toHaveProperty("context");
    expect(window.fetch.mock.calls.map(([url]) => url)).toEqual(["/prepare"]);

    const urls = window.streamSSERequest.mock.calls.map(([url]) => url);
    expect(urls.sort()).toEqual(["/ask_gemini", "/ask_openai"]);
    for (const [, payload] of window.streamSSERequest.mock.calls) {
      expect(payload).toMatchObject({ run_mode: "compare", system_prompt: "Server prompt" });
      expect(payload).not.toHaveProperty("context");
      expect(payload).not.toHaveProperty("chat_id");
      expect(payload).not.toHaveProperty("context_version_id");
    }
    expect(urls).not.toContain("/consensus");

    const run = registry.visible();
    expect(run.status).toBe("succeeded");
    expect(run.config.agentMode).toBe(false);
    expect(run.basis).toBeNull();
    expect(run.historyTurns).toEqual([]);
    expect(run.conversationLockKey).toBe("");
    expect(run.consensus.status).toBe("idle");
    expect(window.saveBookmark).toHaveBeenCalledTimes(2);
    expect(window.saveBookmark.mock.calls.every(call => call[4] === "")).toBe(true);
    expect(window.App.trackAnswer).toHaveBeenCalledWith(run, "ok");
    expect(window.App).not.toHaveProperty("skipModel");
    expect(window.App).not.toHaveProperty("executeConsensusRun");
    dom.window.close();
  });

  it("keeps a partial answer readable and fails only when no model answered", async () => {
    const { window, document, registry, dom } = boot();
    window.streamSSERequest.mockImplementation(async url => ({
      ok: true, status: 200, streamed: true,
      data: url === "/ask_openai"
        ? { response: "Cut short", completion: "token_limit", sources: [] }
        : { response: "Half", completion: "interrupted", sources: [] },
    }));
    document.getElementById("questionInput").value = "Question";
    await window.sendQuestion();
    const run = registry.visible();
    expect(run.modelResults.OpenAI.status).toBe("complete");
    expect(run.modelResults.OpenAI.error).toBe("This answer stopped at the output limit; its end is missing.");
    expect(run.modelResults.Gemini.status).toBe("incomplete");
    expect(run.modelResults.Gemini.error).toBe("This answer was interrupted and is incomplete.");
    expect(run.status).toBe("succeeded");
    // Only a complete answer is saved as finished (R06).
    expect(window.saveBookmark).not.toHaveBeenCalled();

    window.streamSSERequest.mockImplementation(async () => ({ ok: false, status: 502, data: {} }));
    document.getElementById("questionInput").value = "Another";
    // A second Send right after the first is a double click (claimStartAction).
    const later = window.Date.now() + 1000;
    window.Date.now = () => later;
    await window.sendQuestion();
    expect(registry.visible().status).toBe("failed");
    expect(registry.visible().error.message).toBe("All selected model requests failed.");
    dom.window.close();
  });
});
