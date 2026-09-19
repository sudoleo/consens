import { describe, expect, it, vi } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

const chatId = "c".repeat(32), turnId = "d".repeat(32), agentId = "a".repeat(32);
const agent = (seq = 1, status = "working", id = agentId) => ({ id, seq, status, title: "Check Germany", model: { model: "anthropic/claude-haiku-4.5", label: "Haiku" },
  message_seq: seq, usage: { input_tokens: 900, output_tokens: 150, reasoning_tokens: 30, cached_input_tokens: 200, estimated_cost_nano_usd: 123000, cost_source: "provider", complete: true }, duration_ms: 1200 });
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
  it('uses SSE updates without polling, repairs quiet streams, and never revives a completed run', async () => {
    const {window:w,dom} = boot();
    let tick, now = 20000;
    w.setInterval = fn => {tick=fn;return 1;};
    w.Date.now = () => now;
    receive(w,agent()); w.App.agentDelegation.project({chatId,turnId,running:true});
    await vi.waitFor(() => expect(w.fetch).toHaveBeenCalledTimes(1));
    await new Promise(r => setTimeout(r,5));
    now += 9000; receive(w,agent(2)); tick();
    expect(w.fetch).toHaveBeenCalledTimes(1);
    now += 10000; tick();
    await vi.waitFor(() => expect(w.fetch).toHaveBeenCalledTimes(2));
    await new Promise(r => setTimeout(r,5));
    Object.defineProperty(w.document,'visibilityState',{value:'hidden',configurable:true});
    now += 10000; tick(); expect(w.fetch).toHaveBeenCalledTimes(2);
    Object.defineProperty(w.document,'visibilityState',{value:'visible',configurable:true});
    w.App.agentDelegation.project({chatId,turnId,running:false});
    await vi.waitFor(() => expect(w.fetch).toHaveBeenCalledTimes(3));
    await new Promise(r => setTimeout(r,5));
    now += 10000; tick(); expect(w.fetch).toHaveBeenCalledTimes(3);
    dom.window.close();
  });
  it('shows measured input plus output tokens, with no invented zero or double-counted details', () => {
    const {window: w, document: d, dom} = boot();
    const tokens = w.App.agentDelegation.tokens;
    expect(tokens(null, true)).toBe('Tokens pending');
    expect(tokens(null)).toBe('Tokens unavailable');
    expect(tokens({input_tokens: 0, output_tokens: 0})).toBe('0 tokens');
    expect(tokens({...agent().usage, complete: false})).toMatch(/^1[.,]050\+ tokens$/);
    receive(w, agent()); w.App.agentDelegation.project({chatId, turnId});
    expect(d.querySelector('.agent-session-tokens').textContent).toMatch(/^1[.,]050 tokens$/);
    expect(d.querySelector('.agent-session-tokens').title).toContain('900 input + 150 output');
    expect(d.querySelector('.agent-session summary').textContent).not.toContain('$');
    dom.window.close();
  });

  it('opens judge details immediately from live snapshots without detail reads', async () => {
    const {window: w, document: d, dom} = boot(async () => ({ok:true, json:async () => ({agents:[],status:'succeeded'})}));
    const judge = {...agent(1, 'completed'), kind:'judge', title:'Coverage judge', progress_text:'Checking each statement.'};
    receive(w, judge); w.App.agentDelegation.project({chatId, turnId});
    d.querySelector('.agent-inline-model').click();
    expect(d.querySelector('.agent-judge-purpose').textContent).toContain('supported');
    expect(d.querySelector('.agent-token-breakdown').textContent).toContain('900');
    expect(d.querySelector('.agent-detail-skeleton')).toBe(null);
    receive(w, {...judge, seq:2, usage:{input_tokens:950,output_tokens:180}});
    expect(d.querySelector('.agent-token-breakdown').textContent).toContain('950');
    await new Promise(r => setTimeout(r, 5));
    expect(w.fetch.mock.calls.every(([url]) => url.endsWith('/agents'))).toBe(true);
    dom.window.close();
  });

  it('shows a skeleton immediately and reuses cached messages on reopening', async () => {
    let finish;
    const {window: w, document: d, dom} = boot(url => url.includes(agentId)
      ? new Promise(resolve => { finish = resolve; }) : Promise.resolve({ok:true,json:async () => ({agents:[],status:'succeeded'})}));
    receive(w, agent()); w.App.agentDelegation.project({chatId, turnId});
    d.querySelector('.agent-inline-model').click();
    expect(d.querySelector('.agent-detail-skeleton')).not.toBe(null);
    expect(d.querySelector('.agent-session-detail').getAttribute('aria-busy')).toBe('true');
    await vi.waitFor(() => expect(finish).toBeTypeOf('function'));
    finish({ok:true, json:async () => ({agent:{assignment:{goal:'Check the premise'}},messages:[{id:'m',seq:1,text:'Verified result',kind:'result'}],has_more:false})});
    await vi.waitFor(() => expect(d.querySelector('.agent-session-detail').textContent).toContain('Verified result'));
    const count = w.fetch.mock.calls.length;
    const root = d.querySelector('.agent-session');
    root.open = false; root.dispatchEvent(new w.Event('toggle'));
    root.open = true; root.dispatchEvent(new w.Event('toggle'));
    expect(d.querySelector('.agent-detail-skeleton')).toBe(null);
    expect(w.fetch.mock.calls.length).toBe(count);
    dom.window.close();
  });
  it('updates the account allowance from the existing activity request', async () => {
    const budget = { remaining: 24000, limit: 250000, reserved: 16000, observed_at: 2 };
    const { window: w, dom } = boot(async () => ({ ok: true, json: async () => ({ agents: [], status: 'running', token_budget: budget }) }));
    w.App.agentChat = { receiveBudget: vi.fn() };
    w.App.agentDelegation.project({ chatId, turnId, running: true });
    await vi.waitFor(() => expect(w.App.agentChat.receiveBudget).toHaveBeenCalledWith(budget, 'owner'));
    dom.window.close();
  });
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
    expect(d.querySelectorAll(".agent-inline-model")).toHaveLength(1);
    expect(d.querySelectorAll(".agent-session")).toHaveLength(2);
    expect(d.querySelector(".agent-inline-model").title).toContain("2 calls");
    expect(d.querySelector('.agent-session-list').textContent).toContain("Check France");
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
    expect(w.App.agentDelegation.tokens(null)).toBe("Tokens unavailable");
    dom.window.close();
  });
});
