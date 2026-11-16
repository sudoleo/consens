import { describe, expect, it, vi } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

/**
 * The pencil at the newest message of an Agent chat (agent-chat.js
 * syncAskEdit): only while no run goes on, it puts the message back into the
 * box to be sent again as a new one, and never loses a draft that is there.
 */
const BODY = `<textarea id="questionInput"></textarea><div id="threadHistory" hidden></div>
  <div id="threadAsk" class="thread-ask" hidden><div class="thread-ask-bubble"><div class="thread-ask-text" id="threadAskText"></div>
    <button type="button" class="thread-ask-edit" aria-label="Edit and send again" hidden></button></div></div>
  <input id="compareOpenAI" type="checkbox" checked><select id="compareOpenAIModel"><option value="gpt-5.4-mini">OpenAI</option></select>
  <input id="compareClaude" type="checkbox" checked><select id="compareClaudeModel"><option value="claude-haiku-4-5">Claude</option></select>
  <div id="agentModelControls"><div class="select-wrapper agent-model-picker"><select id="agentModelDropdown"></select></div>
  <div class="select-wrapper agent-effort-control"><select id="agentReasoningEffort"></select></div><button id="agentModelsRetry" hidden></button></div>
  <section id="agentAnswer" class="agent-answer" hidden>
  <div id="agentAnswerActivity" class="agent-answer-activity"></div><div id="agentAnswerBody" class="consensus-answer-body"></div><p id="agentAnswerError" hidden></p><button id="agentRecover" hidden></button></section>`;
const CATALOG = { default_model_id: "deepseek/deepseek-v4.1-flash", models: [
  { id: "deepseek/deepseek-v4.1-flash", label: "DeepSeek V4.1 Flash", reasoning_efforts: ["default"], reasoning_available: false }] };
const CHAT = "a".repeat(32);

function agentApp() {
  let answer = 0;
  const pending = [];
  const app = loadScripts(["static/js/user-settings.js", "static/js/run-mode.js", "static/js/run-registry.js", "static/js/token-budget.js",
    "static/js/model-picker.js", "static/js/request-deadline.js", "static/js/agent-activity.js", "static/js/thread-history.js",
    "static/js/agent-chat.js", "static/js/run-view.js"], {
    body: BODY,
    before(window) {
      window.localStorage.setItem("consensio.settingsReset", "2026-10-12");
      window.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} });
      window.auth = { currentUser: { uid: "owner", getIdToken: async () => "verified" } };
      window.App = {
        agentAccess: { uid: "owner", allowed: true }, showPopup: vi.fn(), trackAppEvent: vi.fn(),
        composer: { expand: vi.fn() },
        modelPrefs: [{ provider: "openai", checkId: "compareOpenAI", selectId: "compareOpenAIModel" },
          { provider: "anthropic", checkId: "compareClaude", selectId: "compareClaudeModel" }],
        getModelOptionLabel: option => option?.textContent || "",
        // As app-core.js: the question's own words in data-question.
        setThreadQuestion: question => {
          const ask = window.document.getElementById("threadAsk");
          const text = window.document.getElementById("threadAskText");
          text.textContent = question;
          text.dataset.question = question;
          ask.hidden = !question;
        },
      };
      window.injectMarkdown = (el, markdown) => { el.textContent = markdown; };
      window.fetch = vi.fn(async url => ({ ok: true, status: 200, headers: { get: () => null },
        json: async () => (String(url).startsWith("/agent/") ? structuredClone(CATALOG) : { chat: { id: CHAT } }) }));
      // Each answer comes when the test lets it.
      window.streamSSERequest = vi.fn((_url, payload) => new Promise(resolve => pending.push(() => {
        const id = String(++answer).repeat(32);
        resolve({ ok: true, data: { response: `Answer ${answer}`, chat_id: CHAT, turn_id: id,
          turn: { id, question: payload.question, consensus: `Answer ${answer}`, status: "completed", mode: "Agent", execution_mode: "agent" },
          bookmark_meta: { id: "saved" } } });
      })));
      window.acceptPersistedConsensusBookmark = vi.fn();
    },
  });
  app.document.dispatchEvent(new app.window.Event("DOMContentLoaded"));
  return { ...app, pending };
}

async function ask(window, document, pending, question) {
  document.getElementById("questionInput").value = question;
  const sent = window.App.agentChat.send();
  await vi.waitFor(() => expect(pending.length).toBeGreaterThan(0));
  return async () => { pending.shift()(); await sent; };
}

const pencil = document => document.querySelector("#threadAsk .thread-ask-edit");

describe("Edit and send again", () => {
  it("stands at the newest message once its run is over, and puts it back into the empty box", async () => {
    const { window, document, dom, pending } = agentApp();
    window.App.runMode.set("agent");
    await vi.waitFor(() => expect(document.getElementById("agentModelDropdown").disabled).toBe(false));
    const finish = await ask(window, document, pending, "When did the Colosseum open?");
    // While the run goes on there is nothing to edit.
    await vi.waitFor(() => expect(document.getElementById("threadAskText").dataset.question).toBe("When did the Colosseum open?"));
    expect(pencil(document).hidden).toBe(true);
    await finish();
    await vi.waitFor(() => expect(pencil(document).hidden).toBe(false));

    const input = document.getElementById("questionInput");
    expect(input.value).toBe("");
    pencil(document).click();
    expect(input.value).toBe("When did the Colosseum open?");
    expect(document.activeElement).toBe(input);
    expect([input.selectionStart, input.selectionEnd]).toEqual([input.value.length, input.value.length]);
    expect(window.App.composer.expand).toHaveBeenCalled();
    // Nothing was sent, nothing replaced: the message still stands.
    expect(window.streamSSERequest).toHaveBeenCalledTimes(1);
    expect(document.getElementById("threadAskText").textContent).toBe("When did the Colosseum open?");
    dom.window.close();
  });

  it("never loses a draft that is in the box", async () => {
    const { window, document, dom, pending } = agentApp();
    window.App.runMode.set("agent");
    await vi.waitFor(() => expect(document.getElementById("agentModelDropdown").disabled).toBe(false));
    await (await ask(window, document, pending, "When did the Colosseum open?"))();
    await vi.waitFor(() => expect(pencil(document).hidden).toBe(false));
    const input = document.getElementById("questionInput");
    input.value = "And the Pantheon?  ";
    pencil(document).click();
    expect(input.value).toBe("And the Pantheon?\n\nWhen did the Colosseum open?");
    expect(input.selectionStart).toBe(input.value.length);
    // A second click adds nothing twice.
    pencil(document).click();
    expect(input.value).toBe("And the Pantheon?\n\nWhen did the Colosseum open?");
    dom.window.close();
  });

  it("has none in a reopened chat whose run still goes on", async () => {
    const { window, document, dom } = agentApp();
    window.App.runMode.set("agent");
    await vi.waitFor(() => expect(document.getElementById("agentModelDropdown").disabled).toBe(false));
    const open = status => {
      const turn = { id: "d".repeat(32), turn_id: "d".repeat(32), question: "Is it open today?", status, mode: "Agent",
        execution_mode: "agent", consensus: status === "pending" ? "" : "Yes, until 19:00." };
      window.App.setThreadQuestion(turn.question);
      window.App.runRegistry.showSavedView({ type: "bookmark", bookmarkId: `b-${status}` }, {
        bookmarkId: `b-${status}`, chatId: CHAT, turnId: turn.turn_id, question: turn.question, consensus: turn.consensus,
        executionMode: "agent", currentTurn: turn, historyTurns: [] });
    };
    open("completed");
    await vi.waitFor(() => expect(pencil(document).hidden).toBe(false));
    open("pending");
    await vi.waitFor(() => expect(pencil(document).hidden).toBe(true));
    dom.window.close();
  });

  it("goes with the newest message: the one that moves up into the history has none", async () => {
    const { window, document, dom, pending } = agentApp();
    window.App.runMode.set("agent");
    await vi.waitFor(() => expect(document.getElementById("agentModelDropdown").disabled).toBe(false));
    await (await ask(window, document, pending, "When did the Colosseum open?"))();
    await vi.waitFor(() => expect(pencil(document).hidden).toBe(false));
    const finish = await ask(window, document, pending, "And what does a ticket cost?");
    await vi.waitFor(() => expect(document.querySelectorAll("#threadHistory .thread-history-question")).toHaveLength(1));
    expect(document.querySelector("#threadHistory .thread-ask-edit")).toBeNull();
    expect(pencil(document).hidden).toBe(true);
    await finish();
    await vi.waitFor(() => expect(pencil(document).hidden).toBe(false));
    expect(document.querySelectorAll(".thread-ask-edit")).toHaveLength(1);
    pencil(document).click();
    expect(document.getElementById("questionInput").value).toBe("And what does a ticket cost?");
    dom.window.close();
  });
});
