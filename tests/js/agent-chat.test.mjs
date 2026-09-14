import { describe, expect, it, vi } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

const BODY = `<label id="chatExecutionControl"><select id="chatExecutionMode">
  <option value="consensus">Consensus</option><option value="agent">Agent</option></select></label>
  <textarea id="questionInput"></textarea><div id="threadHistory"></div>
  <section id="agentAnswer" hidden><div id="agentAnswerLabel"></div>
  <div id="agentAnswerBody"></div><p id="agentAnswerError" hidden></p></section>`;

function boot({ allowed = true } = {}) {
  const setup = loadScripts(["static/js/run-registry.js", "static/js/agent-chat.js"], {
    body: BODY,
    before(window) {
      window.auth = { currentUser: { uid: "owner", getIdToken: async () => "verified" } };
      window.App = {
        agentAccess: { uid: "owner", allowed }, showPopup: vi.fn(),
        followup: { renderStoredTurns: vi.fn() },
      };
      window.injectMarkdown = (el, markdown) => { el.textContent = markdown; };
      window.fetch = vi.fn(async () => ({ ok: true, json: async () => ({ chat: { id: "a".repeat(32) } }) }));
      window.streamSSERequest = vi.fn(async (_url, _payload, _signal, handlers) => {
        handlers.delta.append("Answer");
        return { ok: true, data: { response: "Answer", chat_id: "a".repeat(32), turn_id: "b".repeat(32),
          turn: { id: "b".repeat(32), question: "Question", consensus: "Answer", mode: "Agent", execution_mode: "agent" },
          bookmark_meta: { id: "saved" } } };
      });
      window.acceptPersistedConsensusBookmark = vi.fn();
    },
  });
  setup.document.dispatchEvent(new setup.window.Event("DOMContentLoaded"));
  return setup;
}

function selectAgent(window) {
  const select = window.document.getElementById("chatExecutionMode");
  select.value = "agent";
  select.dispatchEvent(new window.Event("change"));
}

describe("single-model agent chat", () => {
  it("requires the current account's entitlement and retains no cross-account access", () => {
    const { window, document, dom } = boot({ allowed: false });
    selectAgent(window);
    expect(window.App.agentChat.isSelected()).toBe(false);
    expect(document.getElementById("chatExecutionControl").hidden).toBe(true);
    window.App.agentAccess.allowed = true;
    selectAgent(window);
    expect(window.App.agentChat.isSelected()).toBe(true);
    window.auth.currentUser.uid = "different-owner";
    window.App.agentChat.render();
    expect(window.App.agentChat.canUse()).toBe(false);
    dom.window.close();
  });

  it("calls only the agent endpoint and continues the same persisted chat", async () => {
    const { window, document, dom } = boot();
    selectAgent(window);
    document.getElementById("questionInput").value = "Question";
    await window.App.agentChat.send();
    expect(window.fetch.mock.calls.map(call => call[0])).toEqual(["/chats"]);
    expect(window.streamSSERequest).toHaveBeenCalledTimes(1);
    const [url, payload, , , options] = window.streamSSERequest.mock.calls[0];
    expect(url).toBe("/agent");
    expect(payload.question).toBe("Question");
    expect(options.headers.Authorization).toBe("Bearer verified");
    expect(payload).not.toHaveProperty("model");
    expect(payload).not.toHaveProperty("usage_run_key");
    expect(window.App.runRegistry.visible().status).toBe("succeeded");
    expect(window.App.runRegistry.getSelectedConversationBasis().executionMode).toBe("agent");
    expect(document.getElementById("chatExecutionMode").disabled).toBe(true);
    document.getElementById("questionInput").value = "Follow-up";
    await window.App.agentChat.send();
    expect(window.fetch).toHaveBeenCalledTimes(1);
    expect(window.streamSSERequest).toHaveBeenCalledTimes(2);
    expect(window.App.runRegistry.visible().historyTurns).toHaveLength(1);
    expect(window.streamSSERequest.mock.calls[1][1].chat_id).toBe("a".repeat(32));
    dom.window.close();
  });

  it("rejects attachments before any network call", async () => {
    const { window, document, dom } = boot();
    selectAgent(window);
    document.getElementById("questionInput").value = "Question";
    window.getAttachmentsPayload = () => [{ name: "private.pdf" }];
    await window.App.agentChat.send();
    expect(window.fetch).not.toHaveBeenCalled();
    expect(window.streamSSERequest).not.toHaveBeenCalled();
    expect(window.App.showPopup).toHaveBeenCalledWith(expect.stringContaining("text only"));
    dom.window.close();
  });

  it("restores an agent bookmark independently of the global consensus preference", () => {
    const { window, document, dom } = boot();
    window.App.runRegistry.showSavedView({ type: "bookmark" }, {
      chatId: "a".repeat(32), turnId: "b".repeat(32), question: "Q", consensus: "Saved answer",
      currentTurn: { mode: "Agent", execution_mode: "agent" },
    });
    expect(window.App.agentChat.isSelected()).toBe(true);
    expect(document.getElementById("agentAnswerBody").textContent).toBe("Saved answer");
    window.App.runRegistry.clearVisible();
    expect(window.App.agentChat.isSelected()).toBe(false);
    expect(document.getElementById("chatExecutionMode").disabled).toBe(false);
    dom.window.close();
  });

  it("ignores late completion after logout", async () => {
    const { window, document, dom } = boot();
    selectAgent(window);
    let resolve;
    window.streamSSERequest = vi.fn(() => new Promise(r => { resolve = r; }));
    document.getElementById("questionInput").value = "Question";
    const pending = window.App.agentChat.send();
    await vi.waitFor(() => expect(resolve).toBeTypeOf("function"));
    window.App.runRegistry.clearAll("logout");
    window.auth.currentUser = null;
    resolve({ ok: true, data: { response: "Late", turn: {} } });
    await pending;
    expect(window.acceptPersistedConsensusBookmark).not.toHaveBeenCalled();
    expect(window.App.runRegistry.visible()).toBe(null);
    dom.window.close();
  });

  it("recovers with the same identity and an explicit no-new-call flag", async () => {
    const { window, document, dom } = boot();
    selectAgent(window);
    window.streamSSERequest.mockRejectedValueOnce(new Error("Connection lost"));
    document.getElementById("questionInput").value = "Question";
    await window.App.agentChat.send();
    const failed = window.App.runRegistry.visible();
    expect(failed.status).toBe("failed");
    await window.App.agentChat.send(failed);
    expect(window.fetch).toHaveBeenCalledTimes(1);
    const payload = window.streamSSERequest.mock.calls[1][1];
    expect(payload.recover_only).toBe(true);
    expect(payload.client_request_id).toBe(window.streamSSERequest.mock.calls[0][1].client_request_id);
    expect(window.App.runRegistry.visible().status).toBe("succeeded");
    dom.window.close();
  });

  it("rebuilds its history after displaying another conversation", async () => {
    const { window, document, dom } = boot();
    selectAgent(window);
    document.getElementById("questionInput").value = "Question";
    await window.App.agentChat.send();
    const run = window.App.runRegistry.visible();
    window.App.agentChat.project(run);
    const count = window.App.followup.renderStoredTurns.mock.calls.length;
    window.App.runRegistry.showSavedView({type: "bookmark"}, {question: "Another", consensus: "Other answer"});
    window.App.runRegistry.show(run.runId);
    window.App.agentChat.project(run);
    expect(window.App.followup.renderStoredTurns.mock.calls.length).toBe(count + 1);
    dom.window.close();
  });
});
