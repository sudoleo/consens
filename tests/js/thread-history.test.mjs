import { describe, expect, it, vi } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

// The conversation history never shrinks under the reader (Apple audit A1):
// a follow-up only appends, and the turn on screen moves up as it is (A4).

function historyApp() {
  const app = loadScripts(["static/js/thread-history.js"], {
    body: '<div id="threadHistory" hidden></div><textarea id="questionInput"></textarea>',
    before(window) {
      window.App = { runMode: { pipeline: () => true } };
      window.injectMarkdown = (el, markdown) => { el.textContent = markdown; };
    },
  });
  return { ...app, followup: app.window.App.followup, history: app.document.getElementById("threadHistory") };
}
const turn = (id, question) => ({ turn_id: id.repeat(32), question, consensus: `Answer to ${question}`, status: "completed" });

describe("thread history", () => {
  it("keeps the turns on the page and only appends a follow-up's new one", () => {
    const { followup, history, window, dom } = historyApp();
    const first = turn("a", "First"), second = turn("b", "Second");
    followup.renderStoredTurns([first]);
    const kept = history.firstElementChild;
    const removed = [];
    new window.MutationObserver(records => records.forEach(r => removed.push(...r.removedNodes)))
      .observe(history, { childList: true });
    followup.renderStoredTurns([first, second]);
    // Same node, nothing removed in between: the page never got shorter.
    expect(history.firstElementChild).toBe(kept);
    expect(history.children).toHaveLength(2);
    return new Promise(resolve => setTimeout(() => {
      expect(removed).toHaveLength(0);
      dom.window.close();
      resolve();
    }));
  });

  it("builds a kept turn again once its differences, sources or answers arrive later", () => {
    const { followup, history, dom } = historyApp();
    const first = turn("a", "First"), second = turn("b", "Second");
    followup.renderStoredTurns([first, second]);
    const [oldFirst, oldSecond] = history.children;
    // The follow-up already moved the first turn up; its check lands now.
    first.differences_data = { differences: [{ claim: "A number differs", type: "contradiction" }] };
    followup.renderStoredTurns([first, second]);
    expect(history.children).toHaveLength(2);
    expect(history.children[0]).not.toBe(oldFirst);
    expect(history.children[1]).not.toBe(oldSecond);
    const rebuilt = history.children[0];
    first.sources = [{ id: "S1", url: "https://example.invalid/a" }];
    followup.renderStoredTurns([first, second]);
    expect(history.children[0]).not.toBe(rebuilt);
    const settled = [...history.children];
    followup.renderStoredTurns([first, second]);
    expect([...history.children]).toEqual(settled);
    dom.window.close();
  });

  it("replaces another chat's history in one step and drops a turn that went back to the answer", () => {
    const { followup, history, window, dom } = historyApp();
    followup.renderStoredTurns([turn("a", "First"), turn("b", "Second")]);
    const spy = vi.spyOn(history, "replaceChildren");
    followup.renderStoredTurns([turn("c", "Other chat")]);
    expect(spy).toHaveBeenCalledTimes(1);
    expect([...history.children].map(node => node.querySelector(".thread-history-question-text").textContent)).toEqual(["Other chat"]);
    followup.renderStoredTurns([turn("c", "Other chat"), turn("d", "Next")]);
    const first = history.firstElementChild;
    followup.renderStoredTurns([turn("c", "Other chat")]);
    expect(history.firstElementChild).toBe(first);
    expect(history.children).toHaveLength(1);
    followup.renderStoredTurns([]);
    expect(history.hidden).toBe(true);
    window.close?.();
    dom.window.close();
  });

  it("takes a handed-over node only after building the rest, right before it is inserted", () => {
    const { followup, history, document, dom } = historyApp();
    const order = [];
    const build = followup.buildHistoryTurn.bind(followup);
    followup.buildHistoryTurn = data => { order.push(`build:${data.question}`); return build(data); };
    const live = document.createElement("article");
    live.className = "thread-history-turn";
    const adopt = {
      owns: data => data.question === "Live",
      take: data => { order.push(`take:${data.question}`); live.dataset.turnKey = followup.turnKey(data); return live; },
    };
    followup.renderStoredTurns([turn("a", "Old"), turn("b", "Live")], { adopt });
    expect(order).toEqual(["build:Old", "take:Live"]);
    expect(history.lastElementChild).toBe(live);
    // Kept from then on: the next projection does not take or build it again.
    followup.renderStoredTurns([turn("a", "Old"), turn("b", "Live")], { adopt });
    expect(order).toHaveLength(2);
    dom.window.close();
  });

  it("builds an Agent turn with the live turn's boxes", () => {
    const { followup, history, dom } = historyApp();
    followup.renderStoredTurns([{ ...turn("a", "Agent question"), execution_mode: "agent", mode: "Agent" }]);
    const node = history.firstElementChild;
    expect(node.classList.contains("is-agent-turn")).toBe(true);
    expect(node.querySelector(".thread-history-answer").classList.contains("agent-answer")).toBe(true);
    dom.window.close();
  });
});

const BODY = `<textarea id="questionInput"></textarea><div id="threadHistory" hidden></div>
  <div id="threadAsk" class="thread-ask" hidden><div class="thread-ask-bubble"><div class="thread-ask-text" id="threadAskText"></div></div></div>
  <input id="compareOpenAI" type="checkbox" checked><select id="compareOpenAIModel"><option value="gpt-5.4-mini">OpenAI</option></select>
  <input id="compareClaude" type="checkbox" checked><select id="compareClaudeModel"><option value="claude-haiku-4-5">Claude</option></select>
  <div id="agentModelControls"><div class="select-wrapper agent-model-picker"><select id="agentModelDropdown"></select></div>
  <div class="select-wrapper agent-effort-control"><select id="agentReasoningEffort"></select></div><button id="agentModelsRetry" hidden></button></div>
  <section id="agentAnswer" class="agent-answer" hidden>
  <div id="agentAnswerActivity" class="agent-answer-activity"></div><div id="agentAnswerBody" class="consensus-answer-body"></div><p id="agentAnswerError" hidden></p><button id="agentRecover" hidden></button></section>`;
const CATALOG = { default_model_id: "deepseek/deepseek-v4.1-flash", models: [
  { id: "deepseek/deepseek-v4.1-flash", label: "DeepSeek V4.1 Flash", reasoning_efforts: ["default"], reasoning_available: false }] };

function agentApp() {
  let answer = 0;
  const app = loadScripts(["static/js/user-settings.js", "static/js/run-mode.js", "static/js/run-registry.js", "static/js/token-budget.js",
    "static/js/model-picker.js", "static/js/request-deadline.js", "static/js/agent-activity.js", "static/js/thread-history.js",
    "static/js/agent-chat.js", "static/js/run-view.js"], {
    body: BODY,
    before(window) {
      window.localStorage.setItem("consensio.settingsReset", "2026-10-12");
      window.auth = { currentUser: { uid: "owner", getIdToken: async () => "verified" } };
      window.App = {
        agentAccess: { uid: "owner", allowed: true }, showPopup: vi.fn(),
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
      window.fetch = vi.fn(async url => ({ ok: true, json: async () => url.startsWith("/agent/") ? structuredClone(CATALOG) : ({ chat: { id: "a".repeat(32) } }) }));
      window.streamSSERequest = vi.fn(async (_url, payload) => {
        const id = String(++answer).repeat(32);
        return { ok: true, data: { response: `Answer ${answer}`, chat_id: "a".repeat(32), turn_id: id,
          turn: { id, question: payload.question, consensus: `Answer ${answer}`, status: "completed", mode: "Agent", execution_mode: "agent" },
          bookmark_meta: { id: "saved" } } };
      });
      window.acceptPersistedConsensusBookmark = vi.fn();
    },
  });
  app.document.dispatchEvent(new app.window.Event("DOMContentLoaded"));
  return app;
}

describe("Agent follow-up", () => {
  it("moves the answer on screen into the history as it is and starts a fresh one below", async () => {
    const { window, document, dom } = agentApp();
    window.App.runMode.set("agent");
    await vi.waitFor(() => expect(document.getElementById("agentModelDropdown").disabled).toBe(false));
    document.getElementById("questionInput").value = "First question";
    await window.App.agentChat.send();
    const body = document.getElementById("agentAnswerBody");
    const ask = document.getElementById("threadAsk");
    expect(body.textContent).toBe("Answer 1");
    // What the reader opened stays open.
    const opened = document.createElement("details"); opened.open = true; body.append(opened);
    document.getElementById("questionInput").value = "Follow-up";
    await window.App.agentChat.send();
    const history = document.getElementById("threadHistory");
    expect(history.contains(body)).toBe(true);
    expect(history.contains(ask)).toBe(true);
    expect(opened.open).toBe(true);
    expect(body.id).toBe("");
    expect(ask.querySelector("[id]")).toBeNull();
    // The live surface is a fresh copy with its IDs.
    expect(document.getElementById("agentAnswerBody")).not.toBe(body);
    expect(document.getElementById("agentAnswerBody").textContent).toBe("Answer 2");
    expect(document.getElementById("threadAskText").textContent).toBe("Follow-up");
    expect(history.querySelectorAll(".thread-history-turn")).toHaveLength(1);
    expect(history.querySelector(".thread-history-turn").classList.contains("is-agent-turn")).toBe(true);
    // The next follow-up keeps that turn and moves only the second one up.
    const first = history.firstElementChild;
    document.getElementById("questionInput").value = "Third";
    await window.App.agentChat.send();
    expect(history.firstElementChild).toBe(first);
    expect(history.querySelectorAll(".thread-history-turn")).toHaveLength(2);
    dom.window.close();
  });
});
