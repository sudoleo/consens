import { describe, expect, it, vi } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

/**
 * Stop at an Agent message that reached the server (agent-chat.js
 * keepStoppedChat): the server saves it as a turn of its chat, with the
 * chat's sidebar entry. The page keeps that chat, as a reload shows it.
 */

const BODY = `<textarea id="questionInput"></textarea><div id="threadHistory"></div><div id="bookmarksContainer"></div>
  <div id="threadAsk" hidden><div class="thread-ask-text" id="threadAskText"></div></div>
  <input id="compareOpenAI" type="checkbox" checked><select id="compareOpenAIModel"><option value="gpt-5.4-mini">OpenAI</option></select>
  <div id="agentModelControls"><div class="select-wrapper agent-model-picker"><select id="agentModelDropdown"></select></div>
  <div class="select-wrapper agent-effort-control"><select id="agentReasoningEffort"></select></div><button id="agentModelsRetry" hidden></button></div>
  <section id="agentAnswer" hidden>
  <div id="agentAnswerActivity"></div><div id="agentAnswerBody"></div><p id="agentAnswerError" hidden></p><button id="agentRecover" hidden></button></section>`;
const CATALOG = { default_model_id: "deepseek/deepseek-v4.1-flash", models: [
  { id: "deepseek/deepseek-v4.1-flash", label: "DeepSeek V4.1 Flash", reasoning_efforts: ["default"], reasoning_available: false }] };
const CHAT = "a".repeat(32);
const TURN = "b".repeat(32);

function boot() {
  const app = loadScripts(["static/js/user-settings.js", "static/js/run-mode.js", "static/js/run-registry.js", "static/js/token-budget.js",
    "static/js/model-picker.js", "static/js/request-deadline.js", "static/js/agent-activity.js", "static/js/agent-chat.js",
    "static/js/run-view.js"], {
    body: BODY,
    before(window) {
      window.localStorage.setItem("consensio.settingsReset", "2026-10-12");
      window.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} });
      window.auth = { currentUser: { uid: "owner", getIdToken: async () => "verified" } };
      window.App = {
        agentAccess: { uid: "owner", allowed: true }, showPopup: vi.fn(), trackAppEvent: vi.fn(),
        followup: { renderStoredTurns: vi.fn(), turnKey: turn => String(turn?.id || "") },
        modelPrefs: [{ provider: "openai", checkId: "compareOpenAI", selectId: "compareOpenAIModel" }],
        getModelOptionLabel: option => option?.textContent || "",
        // As firebase.js: the run's row becomes the chat's saved row in place.
        bookmarkUi: { settleStopped: vi.fn((_meta, runId) => {
          window.document.querySelector(`.bookmark.run-entry[data-run-id="${runId}"]`)?.classList.remove("run-entry");
        }) },
      };
      window.injectMarkdown = (el, markdown) => { el.textContent = markdown; };
      window.fetch = vi.fn(async (url, init) => {
        const target = String(url);
        if (target.startsWith("/agent/models")) return { ok: true, status: 200, json: async () => structuredClone(CATALOG) };
        if (target.endsWith("/stop")) return { ok: true, status: 200, json: async () => ({ status: "stopping" }) };
        return { ok: true, status: 200, json: async () => ({ chat: { id: CHAT } }) };
      });
      // A run that works until it is stopped.
      window.streamSSERequest = vi.fn((_url, _payload, signal, handlers) => new Promise((_resolve, reject) => {
        handlers.accepted?.receive?.({ chat_id: CHAT, turn_id: TURN }, "1");
        handlers.delta?.append?.("Half an ans");
        signal?.addEventListener("abort", () => reject(new DOMException("Stopped", "AbortError")));
      }));
      window.acceptPersistedConsensusBookmark = vi.fn();
    },
  });
  app.document.dispatchEvent(new app.window.Event("DOMContentLoaded"));
  return app;
}

async function selectAgent(window) {
  window.App.runMode.set("agent");
  await vi.waitFor(() => expect(window.document.getElementById("agentModelDropdown").disabled).toBe(false));
}

describe("a stopped message", () => {
  async function stopFirst(window, document) {
    await selectAgent(window);
    document.getElementById("questionInput").value = "Gemini Neon please: a pelican";
    const first = window.App.agentChat.send();
    await vi.waitFor(() => expect(window.App.runRegistry.visible()?.metadata.agentTurnId).toBe(TURN));
    const stopped = window.App.runRegistry.visible();
    window.App.runRegistry.cancel(stopped.runId, "user");
    await first;
    return stopped;
  }

  // Stop, the pencil, a changed model name, Send: one chat, not a second
  // one beside the stopped one in the sidebar.
  it("stays in its chat: the next message continues it, with the stopped one above it", async () => {
    const { window, document, dom } = boot();
    const stopped = await stopFirst(window, document);
    document.getElementById("questionInput").value = "Qwen4 please: a pelican";
    const second = window.App.agentChat.send();
    await vi.waitFor(() => expect(window.streamSSERequest).toHaveBeenCalledTimes(2));
    const created = window.fetch.mock.calls.filter(([url, init]) => String(url) === "/chats" && init?.method === "POST");
    expect(created).toHaveLength(1);
    const body = window.streamSSERequest.mock.calls[1][1];
    expect(body.chat_id).toBe(CHAT);
    expect(body.bookmark_id).toBe(stopped.bookmark.id);
    const next = window.App.runRegistry.visible();
    expect(next.historyTurns.map(turn => [turn.id, turn.question, turn.consensus, turn.status, turn.error_code]))
      .toEqual([[TURN, "Gemini Neon please: a pelican", "Half an ans", "failed", "cancelled"]]);
    window.App.runRegistry.cancel(next.runId, "user");
    await second;
    dom.window.close();
  });

  it("becomes its chat's saved row at once, which has the menu to delete it", async () => {
    const { window, document, dom } = boot();
    await selectAgent(window);
    document.getElementById("questionInput").value = "Gemini Neon please: a pelican";
    const first = window.App.agentChat.send();
    await vi.waitFor(() => expect(window.App.runRegistry.visible()?.metadata.agentTurnId).toBe(TURN));
    const stopped = window.App.runRegistry.visible();
    expect(document.querySelector(`.bookmark.run-entry[data-run-id="${stopped.runId}"]`)).not.toBeNull();
    window.App.runRegistry.cancel(stopped.runId, "user");
    await first;
    expect(window.App.bookmarkUi.settleStopped).toHaveBeenCalledTimes(1);
    expect(window.App.bookmarkUi.settleStopped).toHaveBeenCalledWith(
      expect.objectContaining({ id: stopped.bookmark.id, title: "Gemini Neon please: a pelican", mode: "Agent" }), stopped.runId);
    // The run's end does not bring its run row back.
    window.App.runRegistry.update(stopped.runId, () => {});
    expect(document.querySelectorAll(`.bookmark[data-id="${stopped.bookmark.id}"]`)).toHaveLength(1);
    expect(document.querySelector(".bookmark.run-entry")).toBeNull();
    dom.window.close();
  });

  // Opened again from its row, it is the same chat.
  it("is continued from again when its run is shown again", async () => {
    const { window, document, dom } = boot();
    const stopped = await stopFirst(window, document);
    window.App.runRegistry.clearVisible();
    expect(window.App.runRegistry.getSelectedConversationBasis()).toBeNull();
    window.App.runRegistry.show(stopped.runId);
    expect(window.App.runRegistry.getSelectedConversationBasis()).toMatchObject({ chatId: CHAT, bookmarkId: stopped.bookmark.id });
    dom.window.close();
  });

  // A stop before the message reached the server leaves no turn: the
  // message goes back into the box, and the chat stays a new one.
  it("keeps nothing when it never reached the server", async () => {
    const { window, document, dom } = boot();
    await selectAgent(window);
    let release;
    window.auth.currentUser.getIdToken = () => new Promise(resolve => { release = resolve; });
    document.getElementById("questionInput").value = "Gemini Neon please: a pelican";
    const first = window.App.agentChat.send();
    await vi.waitFor(() => expect(release).toBeDefined());
    const stopped = window.App.runRegistry.visible();
    window.App.runRegistry.cancel(stopped.runId, "user");
    release("verified");
    await first;
    expect(window.App.bookmarkUi.settleStopped).not.toHaveBeenCalled();
    expect(window.App.runRegistry.getSelectedConversationBasis()).toBeNull();
    expect(document.getElementById("questionInput").value).toBe("Gemini Neon please: a pelican");
    dom.window.close();
  });
});
