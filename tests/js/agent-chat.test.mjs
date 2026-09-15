import { describe, expect, it, vi } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

const BODY = `<label id="chatExecutionControl"><select id="chatExecutionMode">
  <option value="consensus">Consensus</option><option value="agent">Agent</option></select></label>
  <textarea id="questionInput"></textarea><div id="threadHistory"></div>
  <div id="agentModelControls"><div class="select-wrapper"><select id="agentModelDropdown"></select></div>
  <label><select id="agentReasoningEffort"></select></label><button id="agentModelsRetry" hidden></button></div>
  <section id="agentAnswer" hidden><div id="agentAnswerLabel"></div>
  <div id="agentAnswerActivity"></div><div id="agentAnswerBody"></div><p id="agentAnswerError" hidden></p></section>`;

const CATALOG = { default_model_id: "deepseek/deepseek-v4.1-flash", models: [
  { id: "deepseek/deepseek-v4.1-flash", label: "DeepSeek V4.1 Flash", reasoning_efforts: ["default", "low", "high", "max"], reasoning_available: true },
  { id: "gpt-5.6-sol", label: "GPT-5.6 Sol", reasoning_efforts: ["default", "low", "medium", "high"], reasoning_available: true },
  { id: "gpt-4o", label: "GPT-4o", reasoning_efforts: ["default"], reasoning_available: false },
] };

function boot({ allowed = true } = {}) {
  const setup = loadScripts(["static/js/run-registry.js", "static/js/model-picker.js", "static/js/agent-activity.js", "static/js/agent-chat.js"], {
    body: BODY,
    before(window) {
      window.auth = { currentUser: { uid: "owner", getIdToken: async () => "verified" } };
      window.App = {
        agentAccess: { uid: "owner", allowed }, showPopup: vi.fn(),
        followup: { renderStoredTurns: vi.fn() },
        modelPrefs: [], getModelOptionLabel: option => option?.dataset.modelLabel || option?.textContent || "",
      };
      window.injectMarkdown = (el, markdown) => { el.textContent = markdown; };
      window.fetch = vi.fn(async url => ({ ok: true, json: async () => url === "/agent/models" ? CATALOG : ({ chat: { id: "a".repeat(32) } }) }));
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

async function selectAgent(window) {
  const select = window.document.getElementById("chatExecutionMode");
  select.value = "agent";
  select.dispatchEvent(new window.Event("change"));
  if (window.App.agentChat.canUse()) await vi.waitFor(() => expect(window.document.getElementById("agentModelDropdown").disabled).toBe(false));
}

describe("single-model agent chat", () => {
  it("requires the current account's entitlement and retains no cross-account access", async () => {
    const { window, document, dom } = boot({ allowed: false });
    await selectAgent(window);
    expect(window.App.agentChat.isSelected()).toBe(false);
    expect(document.getElementById("chatExecutionControl").hidden).toBe(true);
    window.App.agentAccess.allowed = true;
    await selectAgent(window);
    expect(window.App.agentChat.isSelected()).toBe(true);
    window.auth.currentUser.uid = "different-owner";
    window.App.agentChat.render();
    expect(window.App.agentChat.canUse()).toBe(false);
    dom.window.close();
  });

  it("calls only the agent endpoint and continues the same persisted chat", async () => {
    const { window, document, dom } = boot();
    await selectAgent(window);
    document.getElementById("questionInput").value = "Question";
    await window.App.agentChat.send();
    expect(window.fetch.mock.calls.map(call => call[0])).toEqual(["/agent/models", "/chats"]);
    expect(window.streamSSERequest).toHaveBeenCalledTimes(1);
    const [url, payload, , , options] = window.streamSSERequest.mock.calls[0];
    expect(url).toBe("/agent");
    expect(payload.question).toBe("Question");
    expect(options.headers.Authorization).toBe("Bearer verified");
    expect(payload).not.toHaveProperty("model");
    expect(payload.model_id).toBe(CATALOG.default_model_id);
    expect(payload).not.toHaveProperty("usage_run_key");
    expect(window.App.runRegistry.visible().status).toBe("succeeded");
    expect(window.App.runRegistry.getSelectedConversationBasis().executionMode).toBe("agent");
    expect(document.getElementById("chatExecutionMode").disabled).toBe(true);
    document.getElementById("questionInput").value = "Follow-up";
    await window.App.agentChat.send();
    expect(window.fetch).toHaveBeenCalledTimes(2);
    expect(window.streamSSERequest).toHaveBeenCalledTimes(2);
    expect(window.App.runRegistry.visible().historyTurns).toHaveLength(1);
    expect(window.streamSSERequest.mock.calls[1][1].chat_id).toBe("a".repeat(32));
    dom.window.close();
  });

  it("rejects attachments before any network call", async () => {
    const { window, document, dom } = boot();
    await selectAgent(window);
    document.getElementById("questionInput").value = "Question";
    window.getAttachmentsPayload = () => [{ name: "private.pdf" }];
    await window.App.agentChat.send();
    expect(window.fetch.mock.calls.map(call => call[0])).toEqual(["/agent/models"]);
    expect(window.streamSSERequest).not.toHaveBeenCalled();
    expect(window.App.showPopup).toHaveBeenCalledWith(expect.stringContaining("text only"));
    dom.window.close();
  });

  it("restores an agent bookmark independently of the global consensus preference", async () => {
    const { window, document, dom } = boot();
    window.App.runRegistry.showSavedView({ type: "bookmark" }, {
      chatId: "a".repeat(32), turnId: "b".repeat(32), question: "Q", consensus: "Saved answer",
      currentTurn: { mode: "Agent", execution_mode: "agent" },
    });
    expect(window.App.agentChat.isSelected()).toBe(true);
    expect(document.getElementById("agentAnswerBody").textContent).toBe("Saved answer");
    await vi.waitFor(() => expect(document.getElementById("agentModelDropdown").disabled).toBe(false));
    window.App.runRegistry.clearVisible();
    expect(window.App.agentChat.isSelected()).toBe(false);
    expect(document.getElementById("chatExecutionMode").disabled).toBe(false);
    dom.window.close();
  });

  it("ignores late completion after logout", async () => {
    const { window, document, dom } = boot();
    await selectAgent(window);
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
    await selectAgent(window);
    window.streamSSERequest.mockRejectedValueOnce(new Error("Connection lost"));
    document.getElementById("questionInput").value = "Question";
    await window.App.agentChat.send();
    const failed = window.App.runRegistry.visible();
    expect(failed.status).toBe("failed");
    await window.App.agentChat.send(failed);
    expect(window.fetch).toHaveBeenCalledTimes(2);
    const payload = window.streamSSERequest.mock.calls[1][1];
    expect(payload.recover_only).toBe(true);
    expect(payload.client_request_id).toBe(window.streamSSERequest.mock.calls[0][1].client_request_id);
    expect(window.App.runRegistry.visible().status).toBe("succeeded");
    dom.window.close();
  });

  it("rebuilds its history after displaying another conversation", async () => {
    const { window, document, dom } = boot();
    await selectAgent(window);
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

  it("reuses the picker, sends supported effort, and leaves consensus preferences alone", async () => {
    const { window, document, dom } = boot();
    window.localStorage.setItem("pref_consensus_preset", "daily");
    await selectAgent(window);
    const select = document.getElementById("agentModelDropdown");
    document.querySelector("#agentModelControls .model-picker-display").click();
    document.querySelector('#agentModelControls [data-value="gpt-5.6-sol"]').click();
    const effort = document.getElementById("agentReasoningEffort");
    expect([...effort.options].map(option => option.value)).toEqual(["default", "low", "medium", "high"]);
    effort.value = "medium";
    effort.dispatchEvent(new window.Event("change"));
    document.getElementById("questionInput").value = "Question";
    await window.App.agentChat.send();
    expect(window.streamSSERequest.mock.calls[0][1]).toMatchObject({ model_id: "gpt-5.6-sol", reasoning_effort: "medium" });
    expect(window.localStorage.getItem("pref_consensus_preset")).toBe("daily");
    select.value = "gpt-4o";
    select.dispatchEvent(new window.Event("change"));
    expect(effort.parentElement.hidden).toBe(true);
    expect(effort.value).toBe("default");
    dom.window.close();
  });

  it("streams reasoning separately, preserves disclosure, and ignores deltas after stop", async () => {
    const { window, document, dom } = boot();
    await selectAgent(window);
    let handlers, resolve;
    window.streamSSERequest = vi.fn((_url, _payload, _signal, received) => {
      handlers = received;
      return new Promise(r => { resolve = r; });
    });
    document.getElementById("questionInput").value = "Question";
    const pending = window.App.agentChat.send();
    await vi.waitFor(() => expect(handlers).toBeDefined());
    const run = window.App.runRegistry.visible();
    const event = { version: 1, step_id: "completion:0", kind: "reasoning", id: "r1", format: "summary", text: "First thought", append: true };
    handlers.activity.receive(event);
    window.App.agentChat.project(run);
    const details = document.querySelector("#agentAnswerActivity details");
    expect(details.open).toBe(true);
    expect(details.textContent).toContain("First thought");
    expect(document.getElementById("agentAnswerBody").textContent).not.toContain("First thought");
    expect(document.getElementById("agentModelDropdown").disabled).toBe(true);
    details.open = false;
    handlers.activity.receive({ ...event, text: " continued" });
    window.App.agentChat.project(run);
    expect(details.open).toBe(false);
    window.App.runRegistry.cancel(run.runId);
    handlers.activity.receive({ ...event, text: " forbidden late text" });
    window.App.agentChat.project(run);
    expect(details.textContent).not.toContain("forbidden");
    expect(details.textContent).toContain("Response stopped");
    resolve({ ok: true, data: { response: "Late", turn: {} } });
    await pending;
    expect(window.acceptPersistedConsensusBookmark).not.toHaveBeenCalled();
    dom.window.close();
  });

  it("restores reasoning and settings from a saved turn without treating reasoning as HTML", async () => {
    const { window, document, dom } = boot();
    const turn = { mode: "Agent", execution_mode: "agent", agent_settings: { model_id: "gpt-5.6-sol", label: "GPT-5.6 Sol", reasoning_effort: "medium" },
      agent_activity: [{ version: 1, id: "r1", kind: "reasoning", format: "text", text: '<img src=x onerror="alert(1)">Saved thought' }],
      agent_usage: { input_tokens: 100, output_tokens: 20, estimated_cost_nano_usd: 10000 } };
    window.App.runRegistry.showSavedView({ type: "bookmark" }, { chatId: "a".repeat(32), turnId: "b".repeat(32),
      question: "Q", consensus: "Saved answer", currentTurn: turn });
    await vi.waitFor(() => expect(document.getElementById("agentModelDropdown").disabled).toBe(false));
    expect(document.getElementById("agentModelDropdown").value).toBe("gpt-5.6-sol");
    expect(document.getElementById("agentReasoningEffort").value).toBe("medium");
    expect(document.querySelector("#agentAnswerActivity img")).toBe(null);
    expect(document.getElementById("agentAnswerActivity").textContent).toContain("Saved thought");
    expect(document.getElementById("agentAnswerActivity").textContent).toContain("120 tokens");
    dom.window.close();
  });
});
