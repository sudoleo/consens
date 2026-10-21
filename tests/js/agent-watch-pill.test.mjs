import { describe, expect, it, vi } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

/**
 * The Watch pill under every finished Agent answer (Max, Apple-Audit J20,
 * second review 9): the live answer, the turns of the history and a reopened
 * chat each have one, and each carries the question of its own turn, never
 * one left from another turn or chat.
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

function agentApp() {
  let answer = 0;
  const app = loadScripts(["static/js/user-settings.js", "static/js/run-mode.js", "static/js/run-registry.js", "static/js/token-budget.js",
    "static/js/model-picker.js", "static/js/request-deadline.js", "static/js/agent-activity.js", "static/js/consensus-run.js",
    "static/js/agent-chat.js", "static/js/run-view.js",
    "static/js/modal-dialog.js", "static/js/watch-state.js", "static/js/share-dialog.js", "static/js/watch-fields.js", "static/js/watch.js"], {
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
      window.fetch = vi.fn(async url => ({ ok: true, status: 200, headers: { get: () => null },
        json: async () => String(url).startsWith("/agent/") ? structuredClone(CATALOG)
          : String(url) === "/api/my/watches" ? { watches: [], limits: { plan: "pro", active_count: 0, active_limit: 10 } }
            : String(url) === "/api/watch/goal-suggestions" ? { goals: [] }
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

// What the pill opens: the question step (a follow-up) or the goal step
// with the question on top.
function openedQuestion(document) {
  return document.getElementById("watchQuestion")?.value
    ?? document.querySelector(".watch-question-preview strong")?.textContent;
}

async function ask(window, document, question) {
  document.getElementById("questionInput").value = question;
  await window.App.agentChat.send();
}

describe("Watch pill under every Agent answer (J20)", () => {
  it("keeps each turn's pill with its own question when a follow-up moves it up", async () => {
    const { window, document, dom } = agentApp();
    window.App.runMode.set("agent");
    await vi.waitFor(() => expect(document.getElementById("agentModelDropdown").disabled).toBe(false));
    await ask(window, document, "When will OpenAI release GPT-6?");
    const first = document.getElementById("agentAnswerWatchButton");
    expect(first).not.toBeNull();
    await ask(window, document, "And what about the price of it?");
    const history = document.getElementById("threadHistory");
    const pills = [...history.querySelectorAll(".agent-watch-pill")];
    expect(pills).toEqual([first]);
    // Only the live answer's pill carries the live ID.
    expect(first.id).toBe("");
    expect(document.querySelectorAll("#agentAnswerWatchButton")).toHaveLength(1);
    const live = document.getElementById("agentAnswerWatchButton");
    expect(document.getElementById("agentAnswer").contains(live)).toBe(true);
    first.click();
    expect(openedQuestion(document)).toBe("When will OpenAI release GPT-6?");
    live.click();
    // A follow-up opens at the question, so it can stand alone.
    expect(document.getElementById("watchQuestion").value).toBe("And what about the price of it?");
    dom.window.close();
  });

  it("puts a pill under every Agent turn of a reopened chat's history", async () => {
    const { window, document, dom } = agentApp();
    await vi.waitFor(() => expect(document.getElementById("agentModelDropdown").disabled).toBe(false));
    window.App.followup.renderStoredTurns([
      agentTurn("a", "When will OpenAI release GPT-6?"),
      agentTurn("b", "What will it cost per month?", { agent_watch: { question: "What will it cost per month?" } }),
      agentTurn("c", "Why did it fail?", { status: "failed", consensus: "", agent_failure: { error: "Stopped." } }),
    ]);
    const turns = [...document.querySelectorAll("#threadHistory .thread-history-turn")];
    expect(turns).toHaveLength(3);
    const pills = turns.map(turn => turn.querySelector(".agent-watch-pill"));
    expect(pills[0]).not.toBeNull();
    // The history shows no prepared-Watch card, so that turn has the pill too.
    expect(pills[1]).not.toBeNull();
    expect(pills[2]).toBeNull();
    expect(pills[0].id).toBe("");
    pills[0].click();
    expect(openedQuestion(document)).toBe("When will OpenAI release GPT-6?");
    pills[1].click();
    expect(document.getElementById("watchQuestion").value).toBe("What will it cost per month?");
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
    expect(openedQuestion(document)).toBe("Is the new iPhone out in Germany?");
    // A new chat has no answer, and no pill.
    window.App.runRegistry.clearAll("test-new-chat");
    window.App.runRegistry.clearVisible();
    expect(document.getElementById("agentAnswerWatchButton")).toBeNull();
    dom.window.close();
  });
});
