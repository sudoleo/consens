import { describe, expect, it, vi } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

/**
 * The Watch pill under a finished Agent answer (Max, Apple-Audit J20, second
 * review 9). Since 2026-11-03 a Watch runs the Agent in its chat
 * (agent_watches.py): the pill stands under the newest answer only, carries
 * the question of its own turn and opens the sheet that starts a Watch in
 * this chat (watch-sheet.js); a chat with a Watch reads "Watching".
 */
const BODY = `<textarea id="questionInput"></textarea><div id="threadHistory" hidden></div>
  <div id="threadAsk" class="thread-ask" hidden><div class="thread-ask-bubble"><div class="thread-ask-text" id="threadAskText"></div></div></div>
  <input id="compareOpenAI" type="checkbox" checked><select id="compareOpenAIModel"><option value="gpt-5.4-mini">OpenAI</option></select>
  <input id="compareClaude" type="checkbox" checked><select id="compareClaudeModel"><option value="claude-haiku-4-5">Claude</option></select>
  <div id="agentModelControls"><div class="select-wrapper agent-model-picker"><select id="agentModelDropdown"></select></div>
  <div class="select-wrapper agent-effort-control"><select id="agentReasoningEffort"></select></div><button id="agentModelsRetry" hidden></button></div>
  <section id="agentAnswer" class="agent-answer" hidden>
  <div id="agentAnswerActivity" class="agent-answer-activity"></div><div id="agentAnswerBody" class="consensus-answer-body"></div><p id="agentAnswerError" hidden></p><button id="agentRecover" hidden></button></section>
  <dialog id="shareModal" class="modal"><div class="modal-content"><h2 id="shareModalTitle"></h2><div id="shareModalBody"></div></div></dialog>`;
const CATALOG = { default_model_id: "deepseek/deepseek-v4.1-flash", models: [
  { id: "deepseek/deepseek-v4.1-flash", label: "DeepSeek V4.1 Flash", reasoning_efforts: ["default"], reasoning_available: false }] };
const CHAT = "a".repeat(32);

function agentApp({ watches = [] } = {}) {
  let answer = 0;
  const app = loadScripts(["static/js/user-settings.js", "static/js/run-mode.js", "static/js/run-registry.js", "static/js/token-budget.js",
    "static/js/model-picker.js", "static/js/request-deadline.js", "static/js/agent-activity.js", "static/js/thread-history.js",
    "static/js/agent-chat.js", "static/js/run-view.js",
    "static/js/modal-dialog.js", "static/js/watch-state.js", "static/js/share-dialog.js", "static/js/watch-fields.js", "static/js/watch.js",
    "static/js/watch-sheet.js", "static/js/agent-watch.js"], {
    body: BODY,
    before(window) {
      window.localStorage.setItem("consensio.settingsReset", "2026-10-12");
      window.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} });
      window.auth = { currentUser: { uid: "owner", getIdToken: async () => "verified" } };
      window.App = {
        agentAccess: { uid: "owner", allowed: true }, showPopup: vi.fn(), trackAppEvent: vi.fn(),
        modelPrefs: [{ provider: "openai", checkId: "compareOpenAI", selectId: "compareOpenAIModel" },
          { provider: "anthropic", checkId: "compareClaude", selectId: "compareClaudeModel" }],
        getModelOptionLabel: option => option?.textContent || "",
        setThreadQuestion: question => {
          const ask = window.document.getElementById("threadAsk");
          window.document.getElementById("threadAskText").textContent = question;
          ask.hidden = !question;
        },
      };
      window.injectMarkdown = (el, markdown) => { el.textContent = markdown; };
      window.fetch = vi.fn(async (url, options = {}) => ({ ok: true, status: options.method === "POST" && url === "/agent/watches" ? 201 : 200,
        headers: { get: () => null },
        json: async () => String(url).startsWith("/agent/watches")
          ? (options.method === "POST" ? { watch: { id: "w9", chat_id: CHAT, status: "active", ...JSON.parse(options.body) } }
            : { watches, intervals: ["daily", "weekly"], active_count: watches.length, active_limit: 2 })
          : String(url).startsWith("/agent/") ? structuredClone(CATALOG)
          : String(url) === "/api/my/watches" ? { watches: [], limits: { plan: "pro", active_count: 0, active_limit: 10 } }
            : ({ chat: { id: CHAT } }) }));
      window.streamSSERequest = vi.fn(async (_url, payload) => {
        const id = String(++answer).repeat(32);
        return { ok: true, data: { response: `Answer ${answer}`, chat_id: CHAT, turn_id: id,
          turn: { id, question: payload.question, consensus: `Answer ${answer}`, status: "completed", mode: "Agent", execution_mode: "agent" },
          bookmark_meta: { id: "saved" } } };
      });
      window.acceptPersistedConsensusBookmark = vi.fn();
    },
  });
  app.document.dispatchEvent(new app.window.Event("DOMContentLoaded"));
  return app;
}

const agentTurn = (id, question, extra = {}) => ({ id: id.repeat(32), turn_id: id.repeat(32), question,
  consensus: `Answer to ${question}`, status: "completed", mode: "Agent", execution_mode: "agent", ...extra });

// What the pill opens since 2026-11-03: the sheet that starts a Watch in
// this chat (watch-sheet.js), its task prefilled with the answer's question.
function sheetTask(document) {
  const sheet = document.querySelector(".watch-sheet");
  return sheet?.open ? sheet.querySelector(".watch-sheet-task").value : null;
}

async function ask(window, document, question) {
  document.getElementById("questionInput").value = question;
  await window.App.agentChat.send();
}

async function settle() {
  for (let i = 0; i < 40; i += 1) await Promise.resolve();
}

describe("Watch pill under the newest Agent answer (J20, since 2026-11-03 per chat)", () => {
  it("stands under the newest answer only and starts a Watch in this chat from its question", async () => {
    const { window, document, dom } = agentApp();
    window.App.runMode.set("agent");
    await vi.waitFor(() => expect(document.getElementById("agentModelDropdown").disabled).toBe(false));
    await ask(window, document, "When will OpenAI release GPT-6?");
    expect(document.getElementById("agentAnswerWatchButton")).not.toBeNull();
    await ask(window, document, "And what about the price of it?");
    // A Watch belongs to the chat: the turn that moved up has no pill.
    expect(document.querySelectorAll("#threadHistory .agent-watch-pill")).toHaveLength(0);
    const live = document.getElementById("agentAnswerWatchButton");
    expect(document.getElementById("agentAnswer").contains(live)).toBe(true);
    live.click();
    await settle();
    expect(sheetTask(document)).toBe("And what about the price of it?");
    document.querySelector(".watch-sheet-start").click();
    await vi.waitFor(() => expect(window.fetch.mock.calls.some(([url, options]) => url === "/agent/watches"
      && options?.method === "POST")).toBe(true));
    const [, options] = window.fetch.mock.calls.find(([url, request]) => url === "/agent/watches" && request?.method === "POST");
    const body = JSON.parse(options.body);
    expect(body).toMatchObject({ chat_id: CHAT, task: "And what about the price of it?", interval: "daily", run_time: "08:00" });
    dom.window.close();
  });

  it("puts no pill under the turns of a reopened chat's history", async () => {
    const { window, document, dom } = agentApp();
    await vi.waitFor(() => expect(document.getElementById("agentModelDropdown").disabled).toBe(false));
    window.App.followup.renderStoredTurns([
      agentTurn("a", "When will OpenAI release GPT-6?"),
      agentTurn("b", "What will it cost per month?"),
    ]);
    expect(document.querySelectorAll("#threadHistory .thread-history-turn")).toHaveLength(2);
    expect(document.querySelectorAll("#threadHistory .agent-watch-pill")).toHaveLength(0);
    dom.window.close();
  });

  it("reads Watching in a chat that has a Watch and opens it on Watches", async () => {
    const { window, document, dom } = agentApp({ watches: [{ id: "w1", chat_id: CHAT, status: "active", task: "Check it." }] });
    window.App.runMode.set("agent");
    await vi.waitFor(() => expect(document.getElementById("agentModelDropdown").disabled).toBe(false));
    await ask(window, document, "When will OpenAI release GPT-6?");
    const pill = document.getElementById("agentAnswerWatchButton");
    await vi.waitFor(() => expect(pill.classList.contains("is-watching")).toBe(true));
    expect(pill.textContent).toBe("Watching");
    dom.window.close();
  });

  it("gives a reopened chat's answer the question of its own turn, not the chat shown before", async () => {
    const { window, document, dom } = agentApp();
    window.App.runMode.set("agent");
    await vi.waitFor(() => expect(document.getElementById("agentModelDropdown").disabled).toBe(false));
    await ask(window, document, "When will OpenAI release GPT-6?");
    expect(document.getElementById("agentAnswerWatchButton")).not.toBeNull();
    // Another saved chat opens in the same surface.
    window.App.runRegistry.clearAll("test-reload");
    const turn = agentTurn("d", "Is the new iPhone out in Germany?");
    window.App.followup.renderStoredTurns([]);
    window.App.runRegistry.showSavedView({ type: "bookmark", bookmarkId: "other" }, {
      bookmarkId: "other", chatId: "d".repeat(32), turnId: turn.turn_id, question: turn.question,
      consensus: turn.consensus, executionMode: "agent", currentTurn: turn, historyTurns: [] });
    expect(document.getElementById("agentAnswerBody").textContent).toContain("Answer to Is the new iPhone out");
    const pill = document.getElementById("agentAnswerWatchButton");
    expect(pill).not.toBeNull();
    pill.click();
    await settle();
    expect(sheetTask(document)).toBe("Is the new iPhone out in Germany?");
    // A new chat has no answer, and no pill.
    window.App.runRegistry.clearAll("test-new-chat");
    window.App.runRegistry.clearVisible();
    expect(document.getElementById("agentAnswerWatchButton")).toBeNull();
    dom.window.close();
  });
});
