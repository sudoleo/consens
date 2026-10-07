import { describe, expect, it } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

// Two differences passes (and Coverage windows) run side by side since
// 2026-10-07: the Answer check lasts from its first start to its last end.
const chatId = "c".repeat(32), turnId = "d".repeat(32);
const start = "2026-10-07T12:00:00.000Z";
const judge = (id, title, startedAt, ms) => ({ id: id.repeat(32), seq: id.charCodeAt(0), status: "completed", kind: "judge", title,
  created_at: startedAt, duration_ms: ms, model: { model: "openai/gpt-6-luna", label: "GPT-6 Luna" },
  usage: { input_tokens: 100, output_tokens: 10, complete: true }, message_seq: 1 });

function render(judges) {
  const { window: w, document: d, dom } = loadScripts(["static/js/request-deadline.js", "static/js/agent-delegation.js"], {
    body: '<div id="agentAnswerActivity"></div>', before(win) {
      win.auth = { currentUser: { uid: "owner", getIdToken: async () => "token" } };
      win.App = { runRegistry: { isAuthCurrent: c => c.auth.uid === win.auth.currentUser.uid } };
      win.fetch = async () => ({ ok: true, json: async () => ({ agents: judges, status: "succeeded" }) });
    } });
  for (const item of judges) w.App.agentDelegation.receive({ metadata: { chatId }, auth: { uid: "owner" } },
    { version: 1, chat_id: chatId, turn_id: turnId, agent: item });
  w.App.agentDelegation.project({ chatId, turnId, running: false });
  d.querySelector(".agent-sidebar-toggle")?.click();
  const text = d.querySelector(".agent-session .agent-session-state")?.textContent || "";
  dom.window.close();
  return text;
}

describe("Answer check duration", () => {
  it("does not add up passes that ran at the same time", () => {
    const parallel = render([judge("a", "Differences judge", start, 15000), judge("b", "Differences judge", start, 16000),
      judge("e", "Coverage judge", start, 10000)]);
    expect(parallel).toMatch(/16/);
    expect(parallel).not.toMatch(/31/);
  });

  it("still adds a retry that started after the first attempt ended", () => {
    const retry = render([judge("a", "Differences judge", start, 5000),
      judge("b", "Differences judge", "2026-10-07T12:00:05.000Z", 7000)]);
    expect(retry).toMatch(/12/);
  });
});
