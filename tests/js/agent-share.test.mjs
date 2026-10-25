import { describe, expect, it, vi } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

/**
 * Sharing an Agent answer (since 2026-10-21): every finished answer has a
 * Share pill beside its Watch pill, the dialog prepares that exact turn on
 * the server, and a refusal is said in the dialog in the server's words
 * instead of a dead "Saved consensus unavailable" button.
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
const RESULT = "R".repeat(16);

const respond = (data, status = 200) => ({ ok: status < 400, status, headers: { get: () => null },
  json: async () => structuredClone(data) });

function agentApp({ refuse = null } = {}) {
  let answer = 0;
  const calls = [];
  const app = loadScripts(["static/js/user-settings.js", "static/js/run-mode.js", "static/js/run-registry.js", "static/js/token-budget.js",
    "static/js/model-picker.js", "static/js/request-deadline.js", "static/js/agent-activity.js", "static/js/thread-history.js",
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
      window.fetch = vi.fn(async (url, init = {}) => {
        const path = String(url);
        calls.push({ path, method: init.method || "GET", headers: init.headers || {} });
        if (path.endsWith("/share-result")) return refuse ? respond({ detail: refuse }, 409) : respond({ status: "success", result_id: RESULT });
        if (path === "/api/share") return respond({ status: "success", share_id: "S".repeat(16), created: true,
          url: "https://consens.io/s/webb-" + "S".repeat(16) });
        if (path.startsWith("/agent/")) return respond(CATALOG);
        if (path === "/api/my/watches") return respond({ watches: [], limits: { plan: "pro", active_count: 0, active_limit: 10 } });
        return respond({ chat: { id: CHAT } });
      });
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
  return { ...app, calls };
}

const agentTurn = (id, question, extra = {}) => ({ id: id.repeat(32), turn_id: id.repeat(32), question,
  consensus: `Answer to ${question}`, status: "completed", mode: "Agent", execution_mode: "agent", ...extra });

async function ask(window, document, question) {
  document.getElementById("questionInput").value = question;
  await window.App.agentChat.send();
}

const confirmButton = document => document.getElementById("shareConfirmBtn");

describe("Share under an Agent answer", () => {
  it("prepares the answer on screen by its turn and publishes it", async () => {
    const { window, document, dom, calls } = agentApp();
    window.App.runMode.set("agent");
    await vi.waitFor(() => expect(document.getElementById("agentModelDropdown").disabled).toBe(false));
    await ask(window, document, "Is the James Webb telescope still working?");
    const pill = document.querySelector("#agentAnswer .agent-share-pill");
    expect(pill).not.toBeNull();
    // Right after the Watch pill, in the same row.
    expect(document.getElementById("agentAnswerWatchButton").nextElementSibling).toBe(pill);
    expect(pill.textContent).toBe("Share");

    pill.click();
    await vi.waitFor(() => expect(confirmButton(document).disabled).toBe(false));
    const prepared = calls.find(call => call.path.endsWith("/share-result"));
    expect(prepared).toMatchObject({ path: `/agent/chats/${CHAT}/turns/${"1".repeat(32)}/share-result`, method: "POST" });
    expect(prepared.headers.Authorization).toBe("Bearer verified");
    expect(confirmButton(document).textContent).toBe("Create public link");
    // An Agent answer is no Consensus result.
    expect(window.lastShareResultId ?? null).toBeNull();

    confirmButton(document).click();
    await vi.waitFor(() => expect(document.getElementById("shareModalTitle").textContent).toBe("Public link created"));
    expect(document.getElementById("shareUrlInput").value).toBe("https://consens.io/s/webb-" + "S".repeat(16));
    dom.window.close();
  });

  it("says the server's reason in the dialog and offers no button that cannot work", async () => {
    const reason = "Answers in a chat with your Google data can’t be shared publicly.";
    const { window, document, dom } = agentApp({ refuse: reason });
    window.App.runMode.set("agent");
    await vi.waitFor(() => expect(document.getElementById("agentModelDropdown").disabled).toBe(false));
    await ask(window, document, "What did my last email say?");
    document.querySelector("#agentAnswer .agent-share-pill").click();

    const error = document.getElementById("shareDialogError");
    await vi.waitFor(() => expect(error.hidden).toBe(false));
    expect(error.textContent).toBe(reason);
    expect(error.getAttribute("role")).toBe("alert");
    expect(confirmButton(document).hidden).toBe(true);
    expect(document.getElementById("shareModalBody").textContent).not.toContain("unavailable");
    dom.window.close();
  });

  it("gives every finished turn of a reopened chat its own Share, for its own answer", async () => {
    const { window, document, dom, calls } = agentApp();
    await vi.waitFor(() => expect(document.getElementById("agentModelDropdown").disabled).toBe(false));
    const current = agentTurn("d", "And how long will it last?");
    window.App.runRegistry.showSavedView({ type: "bookmark", bookmarkId: "webb" }, {
      bookmarkId: "webb", chatId: CHAT, turnId: current.turn_id, question: current.question,
      consensus: current.consensus, executionMode: "agent", currentTurn: current, historyTurns: [] });
    window.App.followup.renderStoredTurns([
      agentTurn("b", "Is the James Webb telescope still working?"),
      agentTurn("c", "Why did it stop?", { status: "failed", consensus: "", agent_failure: { error: "Stopped." } }),
    ]);
    const turns = [...document.querySelectorAll("#threadHistory .thread-history-turn")];
    expect(turns.map(turn => Boolean(turn.querySelector(".agent-share-pill")))).toEqual([true, false]);
    expect(document.querySelector("#agentAnswer .agent-share-pill")).not.toBeNull();

    turns[0].querySelector(".agent-share-pill").click();
    await vi.waitFor(() => expect(confirmButton(document).disabled).toBe(false));
    expect(calls.filter(call => call.path.endsWith("/share-result")).map(call => call.path))
      .toEqual([`/agent/chats/${CHAT}/turns/${"b".repeat(32)}/share-result`]);
    dom.window.close();
  });

  it("removes the pill when the surface shows no finished answer", async () => {
    const { window, document, dom } = agentApp();
    window.App.runMode.set("agent");
    await vi.waitFor(() => expect(document.getElementById("agentModelDropdown").disabled).toBe(false));
    await ask(window, document, "Is the James Webb telescope still working?");
    expect(document.querySelector("#agentAnswer .agent-share-pill")).not.toBeNull();
    window.App.runRegistry.clearAll("test-new-chat");
    window.App.runRegistry.clearVisible();
    expect(document.querySelector("#agentAnswer .agent-share-pill")).toBeNull();
    dom.window.close();
  });
});
