import { describe, expect, it, vi } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

const chatId = "c".repeat(32), turnId = "d".repeat(32), agentId = "a".repeat(32);
const agent = (seq = 1, status = "working", id = agentId) => ({ id, seq, status, title: "Check Germany", model: { model: "anthropic/claude-haiku-4.5", label: "Haiku" },
  message_seq: seq, usage: { estimated_cost_nano_usd: 123000, cost_source: "provider", complete: true }, duration_ms: 1200 });
function boot(fetcher) {
  return loadScripts(["static/js/agent-delegation.js"], { body: '<div id="agentAnswerActivity"></div>', before(w) {
    w.auth = { currentUser: { uid: "owner", getIdToken: async () => "token" } };
    w.App = { runRegistry: { isAuthCurrent: c => c.auth.uid === w.auth.currentUser.uid } };
    w.fetch = vi.fn(fetcher || (async url => ({ ok: true, json: async () => url.includes(agentId)
      ? { agent: { assignment: { goal: "Validate the premise" } }, messages: [{ id: "m1", seq: 1, sender: "orchestrator", recipient: agentId, kind: "message", text: "Check the premise for Germany." }] }
      : { agents: [agent()], status: "running", usage: { estimated_cost_nano_usd: 900000, cost_source: "provider", complete: true } } })));
  } });
}
function receive(w, data) {
  w.App.agentDelegation.receive({ metadata: { chatId }, auth: { uid: "owner" } }, { version: 1, chat_id: chatId, turn_id: turnId, agent: data });
}

describe("Agent sidebar", () => {
  it("opens on first start, shares state with inline icons and respects manual close and duplicate events", async () => {
    const { window: w, document: d, dom } = boot();
    receive(w, agent()); w.App.agentDelegation.project({ chatId, turnId, running: true });
    expect(d.getElementById("agentSidebar").hidden).toBe(false);
    expect(d.querySelectorAll(".agent-session")).toHaveLength(1);
    d.querySelector(".agent-inline-model").click();
    await vi.waitFor(() => expect(d.querySelector(".agent-session-detail").textContent).toContain("Check the premise for Germany."));
    expect(d.querySelector(".agent-session-detail").textContent).toContain("Orchestrator → Check Germany");
    const focused = d.querySelector(".agent-inline-model"); focused.focus();
    receive(w, agent());
    expect(d.activeElement).toBe(focused);
    d.querySelector(".agent-sidebar-close").click();
    receive(w, agent(2, "question")); receive(w, agent(1));
    expect(d.getElementById("agentSidebar").hidden).toBe(true);
    expect(d.querySelector(".agent-session").dataset.status).toBe("question");
    expect(d.querySelectorAll(".agent-session")).toHaveLength(1);
    w.App.agentDelegation.project(null);
    w.App.agentDelegation.project({ chatId, turnId });
    expect(d.getElementById("agentSidebar").hidden).toBe(true);
    d.querySelector(".agent-sidebar-toggle").click();
    expect(d.getElementById("agentSidebar").hidden).toBe(false);
    d.getElementById("agentSidebar").dispatchEvent(new w.KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    expect(d.getElementById("agentSidebar").hidden).toBe(true);
    dom.window.close();
  });

  it("distinguishes same-model agents and restores saved state without starting any model request", async () => {
    const { window: w, document: d, dom } = boot();
    receive(w, agent()); receive(w, { ...agent(2, "waiting", "b".repeat(32)), title: "Check France" });
    w.App.agentDelegation.project({ chatId, turnId });
    expect(d.querySelectorAll(".agent-inline-model")).toHaveLength(2);
    expect(d.querySelectorAll(".agent-session")).toHaveLength(2);
    expect([...d.querySelectorAll(".agent-inline-model")].map(el => el.title).join(" ")).toContain("Check France");
    expect(w.fetch.mock.calls.every(([url]) => url.includes("/agents"))).toBe(true);
    dom.window.close();
  });

  it("ignores delayed responses and events after account or conversation switch", async () => {
    let finish;
    const { window: w, document: d, dom } = boot(() => new Promise(resolve => { finish = resolve; }));
    receive(w, agent()); w.App.agentDelegation.project({ chatId, turnId });
    await vi.waitFor(() => expect(finish).toBeTypeOf("function"));
    w.auth.currentUser = { uid: "another", getIdToken: async () => "other-token" };
    w.dispatchEvent(new w.CustomEvent("consensio:run-registry-change"));
    finish({ ok: true, json: async () => ({ agents: [agent(10, "completed")], status: "succeeded" }) });
    await new Promise(r => setTimeout(r, 5));
    receive(w, agent(11));
    expect(d.getElementById("agentSidebar").hidden).toBe(true);
    expect(d.querySelectorAll(".agent-session")).toHaveLength(0);
    expect(d.querySelector(".agent-inline-model")).toBeNull();
    dom.window.close();
  });

  it("renders untrusted text safely, labels unknown totals and retries details only on demand", async () => {
    const { window: w, document: d, dom } = boot(async url => ({ ok: !url.includes(agentId), json: async () => ({ agents: [], status: "succeeded" }) }));
    receive(w, { ...agent(), title: '<img src=x onerror="alert(1)">' });
    w.App.agentDelegation.project({ chatId, turnId });
    d.querySelector(".agent-inline-model").click();
    await vi.waitFor(() => expect(d.querySelector(".agent-load-more")?.textContent).toBe("Retry"));
    const calls = w.fetch.mock.calls.length;
    receive(w, agent(3));
    await new Promise(r => setTimeout(r, 5));
    expect(w.fetch.mock.calls.length).toBe(calls);
    expect(d.querySelector("img[onerror]")).toBeNull();
    expect(w.App.agentDelegation.cost(null)).toBe("Cost unknown");
    expect(w.App.agentDelegation.cost({ estimated_cost_nano_usd: 1000000, cost_complete: false })).toContain("incomplete");
    dom.window.close();
  });
});
