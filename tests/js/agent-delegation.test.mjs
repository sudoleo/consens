import { describe, expect, it, vi } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

const chatId = "c".repeat(32), turnId = "d".repeat(32), agentId = "a".repeat(32);
const agent = (seq = 1, status = "working", id = agentId) => ({ id, seq, status, title: "Check Germany", model: { model: "anthropic/claude-haiku-4.5", label: "Haiku" },
  message_seq: seq, usage: { input_tokens: 900, output_tokens: 150, reasoning_tokens: 30, cached_input_tokens: 200, estimated_cost_nano_usd: 123000, cost_source: "provider", complete: true }, duration_ms: 1200 });
function boot(fetcher) {
  return loadScripts(["static/js/request-deadline.js", "static/js/agent-delegation.js"], { body: '<div id="agentAnswerActivity"></div>', before(w) {
    w.auth = { currentUser: { uid: "owner", getIdToken: async () => "token" } };
    w.App = { runRegistry: { isAuthCurrent: c => c.auth.uid === w.auth.currentUser.uid } };
    w.fetch = vi.fn(fetcher || (async url => ({ ok: true, json: async () => url.includes(agentId)
      ? { agent: { assignment: { goal: "Validate the premise" } }, messages: [{ id: "m1", seq: 1, sender: "orchestrator", recipient: agentId, kind: "message", text: "Check the premise for Germany." }] }
      : { agents: [agent()], status: "running", usage: { estimated_cost_nano_usd: 900000, cost_source: "provider", complete: true } } })));
  } });
}
function bootNarrow(fetcher) {
  return loadScripts(["static/js/request-deadline.js", "static/js/agent-delegation.js"], { body: '<div id="agentAnswerActivity"><details><summary></summary></details></div>', before(w) {
    w.matchMedia = query => ({ matches: false, media: query, addEventListener() {}, removeEventListener() {} });
    w.auth = { currentUser: { uid: "owner", getIdToken: async () => "token" } };
    w.App = { runRegistry: { isAuthCurrent: c => c.auth.uid === w.auth.currentUser.uid } };
    w.fetch = vi.fn(fetcher || (async () => ({ ok: true, json: async () => ({ agents: [agent()], status: "running" }) })));
  } });
}
function receive(w, data) {
  w.App.agentDelegation.receive({ metadata: { chatId }, auth: { uid: "owner" } }, { version: 1, chat_id: chatId, turn_id: turnId, agent: data });
}

describe("Agent sidebar", () => {
  it('stops its 2.5 s tick once nothing runs and never starts one for a saved turn', async () => {
    const {window:w,dom} = boot(async () => ({ok:true,json:async () => ({agents:[agent(1,'completed')],status:'succeeded'})}));
    receive(w, agent());
    w.App.agentDelegation.project({chatId,turnId,running:true});
    expect(w.App.agentDelegation.isTicking()).toBe(true);
    w.App.agentDelegation.project({chatId,turnId,running:false});
    // Settling keeps one repair load; its terminal status ends the timer.
    await vi.waitFor(() => expect(w.App.agentDelegation.isTicking()).toBe(false));
    w.App.agentDelegation.project({chatId:'e'.repeat(32),turnId,running:false});
    await vi.waitFor(() => expect(w.fetch).toHaveBeenCalledTimes(2));
    expect(w.App.agentDelegation.isTicking()).toBe(false);
    w.App.agentDelegation.project(null);
    expect(w.App.agentDelegation.isTicking()).toBe(false);
    dom.window.close();
  });
  it('opens as a sheet only on request under 1200 px, with a scrim and a focus trap', () => {
    const {window:w,document:d,dom} = bootNarrow();
    receive(w, agent());
    w.App.agentDelegation.project({chatId,turnId,running:true});
    const sidebar = d.getElementById('agentSidebar');
    const toggle = d.querySelector('.agent-sidebar-toggle');
    expect(sidebar.hidden).toBe(true);
    expect(toggle.hidden).toBe(false);
    expect(toggle.getAttribute('aria-controls')).toBe('agentSidebar');
    expect(toggle.getAttribute('aria-expanded')).toBe('false');
    toggle.click();
    expect(sidebar.hidden).toBe(false);
    expect(sidebar.getAttribute('role')).toBe('dialog');
    expect(sidebar.getAttribute('aria-modal')).toBe('true');
    const scrim = d.querySelector('.agent-sidebar-scrim');
    expect(scrim.hidden).toBe(false);
    scrim.click();
    expect(sidebar.hidden).toBe(true);
    expect(scrim.hidden).toBe(true);
    expect(d.activeElement).toBe(toggle);
    dom.window.close();
  });
  it('does not rewrite row titles or status text when nothing changed', () => {
    const {window:w,document:d,dom} = boot(async () => ({ok:true,json:async () => ({agents:[],status:'running'})}));
    receive(w, agent());
    w.App.agentDelegation.project({chatId,turnId,running:true});
    const tokens = d.querySelector('.agent-session-tokens');
    const summary = d.querySelector('.agent-session summary');
    expect(summary.getAttribute('aria-describedby')).toBe(d.querySelector('.agent-session-state').id);
    expect(summary.hasAttribute('title')).toBe(false);
    const writes = [];
    new w.MutationObserver(records => writes.push(...records)).observe(tokens, {attributes:true, childList:true, characterData:true, subtree:true});
    receive(w, agent());
    w.App.agentDelegation.project({chatId,turnId,running:true});
    return Promise.resolve().then(() => { expect(writes).toHaveLength(0); dom.window.close(); });
  });
  it('keeps model icons and keyboard focus stable as statuses and same-model calls change', () => {
    const {window:w,document:d,dom} = boot(async () => ({ok:true,json:async () => ({agents:[],status:'running'})}));
    receive(w, agent()); w.App.agentDelegation.project({chatId,turnId,running:true});
    const icon = d.querySelector('.agent-inline-model'); icon.focus();
    receive(w, agent(2, 'completed'));
    expect(d.querySelector('.agent-inline-model')).toBe(icon);
    expect(d.activeElement).toBe(icon);
    expect(icon.dataset.status).toBe('completed');
    const next = agent(1, 'working', 'b'.repeat(32));
    receive(w, next);
    expect(d.querySelector('.agent-inline-model')).toBe(icon);
    expect(d.activeElement).toBe(icon);
    expect(icon.title).toContain('2 calls');
    expect(icon.dataset.agentId).toBe(next.id);
    d.querySelector('.agent-sidebar-close').click();
    expect(d.querySelector('.agent-inline-model')).toBe(icon);
    icon.click();
    expect(d.querySelectorAll('.agent-session')[1].open).toBe(true);
    dom.window.close();
  });
  it('uses elapsed server durations with a monotonic clock and freezes terminal or recovered sessions', async () => {
    const {window:w,document:d,dom} = boot(async () => ({ok:true,json:async () => ({agents:[],status:'running'})}));
    let tick, monotonic = 100;
    w.setInterval = fn => {tick=fn;return 1;};
    w.performance.now = () => monotonic;
    w.Date.now = () => 9999999999999;
    receive(w, {...agent(), created_at:'invalid-date', duration_ms:5200});
    w.App.agentDelegation.project({chatId,turnId,running:true});
    const text = () => d.querySelector('.agent-session-state').textContent;
    expect(text()).toContain('5s');
    monotonic += 3000; tick(); expect(text()).toContain('8s');
    w.App.agentDelegation.project({chatId,turnId,running:false});
    monotonic += 60000; tick(); expect(text()).toContain('8s');
    w.App.agentDelegation.receiveProgress({metadata:{chatId,agentTurnId:turnId},auth:{uid:'owner'}},
      {version:1,chat_id:chatId,turn_id:turnId,agent_id:agentId,session_seq:1,seq:1,chars:10,streaming:true,duration_ms:100000});
    expect(text()).toContain('8s');
    w.App.agentDelegation.project({chatId,turnId,running:true});
    expect(text()).toContain('8s');
    receive(w, {...agent(2,'stopped'), duration_ms:7300, duration_incomplete:true});
    expect(text()).toContain('≥ 7s');
    monotonic += 60000; tick(); expect(text()).toContain('≥ 7s');
    dom.window.close();
  });
  it('does not replace a newer polled total with a stale run projection', async () => {
    const usage = {input_tokens:900,output_tokens:100,measured_calls:3,complete:true};
    const {window:w,document:d,dom} = boot(async () => ({ok:true,json:async () => ({agents:[agent()],status:'running',usage})}));
    w.App.agentDelegation.project({chatId,turnId,running:true});
    await vi.waitFor(() => expect(d.querySelector('.agent-sidebar-usage').textContent).toMatch(/1[.,]000 tokens/));
    w.App.agentDelegation.project({chatId,turnId,running:true,usage:{input_tokens:200,output_tokens:20,measured_calls:1,complete:true}});
    expect(d.querySelector('.agent-sidebar-usage').textContent).toMatch(/1[.,]000 tokens/);
    dom.window.close();
  });
  it('discards a pending old session response after the same user signs in again', async () => {
    let resolve;
    const {window:w,document:d,dom} = boot(() => new Promise(done => {resolve=done;}));
    w.App.agentChat = {receiveBudget:vi.fn()};
    w.App.agentDelegation.project({chatId,turnId,running:true});
    await vi.waitFor(() => expect(resolve).toBeTypeOf('function'));
    w.auth.currentUser = {...w.auth.currentUser};
    w.dispatchEvent(new w.Event('consensio:run-registry-change'));
    resolve({ok:true,json:async () => ({agents:[agent()],status:'running',token_budget:{remaining:1}})});
    await new Promise(done => setTimeout(done,5));
    expect(w.App.agentChat.receiveBudget).not.toHaveBeenCalled();
    expect(d.querySelector('.agent-session')).toBeNull();
    dom.window.close();
  });
  it('shows live received characters, switches to provider tokens and stops shimmer on completion', () => {
    const {window:w,document:d,dom} = boot(async () => ({ok:true,json:async () => ({agents:[],status:'running'})}));
    receive(w, {...agent(), usage:null}); w.App.agentDelegation.project({chatId,turnId,running:true});
    const label = d.querySelector('.agent-session-tokens');
    // A live call is shown in words and numbers only: no travelling bar.
    expect(d.querySelector('.agent-session-track')).toBeNull();
    expect(label.textContent).toBe('Tokens pending'); expect(label.classList.contains('is-loading')).toBe(true);
    const context = {metadata:{chatId,agentTurnId:turnId},auth:{uid:'owner'}};
    const progress = {version:1,chat_id:chatId,turn_id:turnId,agent_id:agentId,session_seq:1,seq:1,chars:120,streaming:true,usage:null};
    const update = event => w.App.agentDelegation.receiveProgress(context,event);
    update(progress); expect(label.textContent).toBe('120 chars');
    update({...progress,seq:2,chars:780}); expect(label.textContent).toBe('780 chars');
    update(progress); update({...progress,seq:3,session_seq:0,chars:1});
    update({...progress,seq:3,turn_id:'e'.repeat(32),chars:1});
    expect(label.textContent).toBe('780 chars');
    update({...progress,seq:3,chars:800,usage:{input_tokens:100,output_tokens:25}});
    expect(label.textContent).toBe('125 tokens'); expect(label.title).toContain('100 input + 25 output');
    expect(label.classList.contains('is-loading')).toBe(true);
    update({...progress,seq:4,chars:900,usage:{input_tokens:100,output_tokens:35},streaming:false});
    expect(label.textContent).toBe('135 tokens'); expect(label.classList.contains('is-loading')).toBe(false);
    receive(w,{...agent(2,'completed'),usage:{input_tokens:100,output_tokens:35}});
    update({...progress,seq:5,session_seq:2,chars:1000});
    expect(label.textContent).toBe('135 tokens'); expect(label.classList.contains('is-loading')).toBe(false);
    dom.window.close();
  });
  it('clears transient counters on stop and turn switches and never animates saved active snapshots', () => {
    const {window:w,document:d,dom} = boot(async () => ({ok:true,json:async () => ({agents:[],status:'running'})}));
    receive(w,{...agent(),usage:null}); w.App.agentDelegation.project({chatId,turnId,running:true});
    const context = {metadata:{chatId,agentTurnId:turnId},auth:{uid:'owner'}};
    w.App.agentDelegation.receiveProgress(context,{version:1,chat_id:chatId,turn_id:turnId,agent_id:agentId,session_seq:1,seq:1,chars:120,streaming:true});
    w.App.agentDelegation.project({chatId,turnId,running:false});
    expect(d.querySelector('.agent-session-tokens').textContent).toBe('Tokens unavailable');
    expect(d.querySelector('.agent-session-tokens.is-loading')).toBeNull();
    w.App.agentDelegation.project({chatId,turnId:'e'.repeat(32),running:true});
    expect(d.querySelector('.agent-session-tokens')).toBeNull();
    w.App.agentDelegation.project({chatId,turnId,running:false});
    expect(d.querySelector('.agent-session-tokens').textContent).toBe('Tokens unavailable');
    expect(d.querySelector('.agent-session-tokens.is-loading')).toBeNull();
    dom.window.close();
  });
  it('shows loading independently for each model and hides it for terminal or paused sessions', () => {
    const {window:w,document:d,dom} = boot(async () => ({ok:true,json:async () => ({agents:[],status:'running'})}));
    const states = ['waiting', 'working', 'rework', 'completed', 'failed', 'stopped', 'question', 'review'];
    states.forEach((status, i) => receive(w, agent(1, status, i.toString(16).repeat(32))));
    w.App.agentDelegation.project({chatId,turnId,running:true});
    const labels = [...d.querySelectorAll('.agent-session-tokens')];
    expect(labels).toHaveLength(states.length);
    const loading = () => labels.map(label => label.classList.contains('is-loading'));
    expect(loading()).toEqual([true, true, true, false, false, false, false, false]);
    receive(w, agent(2, 'completed', '1'.repeat(32)));
    expect(loading()).toEqual([true, false, true, false, false, false, false, false]);
    dom.window.close();
  });
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
    // Local stop precedes server settlement. Keep repairing until the server
    // confirms completion, without reviving the run or its timer.
    w.fetch.mockImplementationOnce(async () => ({ok:true,json:async () => ({agents:[agent(3,'stopped')],status:'cancelled'})}));
    now += 10000; tick();
    await vi.waitFor(() => expect(w.fetch).toHaveBeenCalledTimes(4));
    await new Promise(r => setTimeout(r,5));
    now += 10000; tick(); expect(w.fetch).toHaveBeenCalledTimes(4);
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
    d.querySelector('.agent-sidebar-toggle').click();
    const row = d.querySelector('.agent-session'); row.open = true; row.dispatchEvent(new w.Event('toggle'));
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

  it("keeps the panel closed when a saved turn is opened, even with room beside the column", async () => {
    const { window: w, document: d, dom } = boot(async () => ({ ok: true, json: async () => ({ agents: [agent(1, "completed")], status: "succeeded" }) }));
    w.App.agentDelegation.project({ chatId, turnId, running: false });
    await vi.waitFor(() => expect(d.querySelectorAll(".agent-session")).toHaveLength(1));
    expect(d.getElementById("agentSidebar").hidden).toBe(true);
    expect(d.body.classList.contains("agent-sidebar-open")).toBe(false);
    d.querySelector(".agent-sidebar-toggle").click();
    expect(d.getElementById("agentSidebar").hidden).toBe(false);
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

  it("points a checked pasted text to its card above the answer, and names a failed text check", async () => {
    const judge = (id, seq, status, title) => ({ ...agent(seq, status, id), kind: "judge", title,
      model: { model: `m/${seq}`, label: `Judge ${seq}` }, usage: null });
    const answer = { ...agent(1, "completed"), kind: "comparison", title: "Comparison 1 · Haiku" };
    const judges = [judge("b".repeat(32), 2, "completed", "Text check"), judge("e".repeat(32), 3, "completed", "Differences judge"),
      judge("f".repeat(32), 4, "completed", "Coverage judge")];
    const { window: w, document: d, dom } = boot(async () => ({ ok: true, json: async () => ({ agents: [answer, ...judges], status: "succeeded" }) }));
    for (const item of [answer, ...judges]) receive(w, item);
    w.App.agentDelegation.project({ chatId, turnId, running: false });
    const check = [...d.querySelectorAll(".agent-session")][1];
    check.open = true; check.dispatchEvent(new w.Event("toggle"));
    expect(check.querySelector(".agent-judge-note").textContent).toBe("The check of your text is shown above the answer, the rest under Review.");
    receive(w, judge("b".repeat(32), 5, "failed", "Text check"));
    w.App.agentDelegation.project({ chatId, turnId, running: false });
    expect(d.querySelector(".agent-judge-note").textContent).toBe("The text check could not run. The answer is shown without it.");
    dom.window.close();
  });

  it("names the row after the text when only the pasted text was checked", async () => {
    const answer = { ...agent(1, "completed"), kind: "comparison", title: "Comparison 1 · Haiku" };
    const text = { ...agent(2, "completed", "b".repeat(32)), kind: "judge", title: "Text check",
      model: { model: "m/2", label: "Judge 2" }, usage: null };
    const { window: w, document: d, dom } = boot(async () => ({ ok: true, json: async () => ({ agents: [answer, text], status: "succeeded" }) }));
    for (const item of [answer, text]) receive(w, item);
    w.App.agentDelegation.project({ chatId, turnId, running: false });
    const check = [...d.querySelectorAll(".agent-session")][1];
    expect(check.querySelector("strong").textContent).toBe("Text check");
    expect(check.textContent).toContain("Your text, sentence by sentence");
    check.open = true; check.dispatchEvent(new w.Event("toggle"));
    expect(check.querySelector(".agent-judge-purpose").textContent).toBe("Checks each sentence of your text against the independent answers.");
    expect(check.querySelector(".agent-judge-note").textContent).toBe("The check of your text is shown above the answer.");
    dom.window.close();
  });

  it("keeps calling the row Answer check while the answer's own checks follow a failed text check", async () => {
    const answer = { ...agent(1, "completed"), kind: "comparison", title: "Comparison 1 · Haiku" };
    const text = { ...agent(2, "failed", "b".repeat(32)), kind: "judge", title: "Text check",
      model: { model: "m/2", label: "Judge 2" }, usage: null };
    const { window: w, document: d, dom } = boot(async () => ({ ok: true, json: async () => ({ agents: [answer, text], status: "running" }) }));
    for (const item of [answer, text]) receive(w, item);
    w.App.agentDelegation.project({ chatId, turnId, running: true });
    const check = [...d.querySelectorAll(".agent-session")][1];
    expect(check.querySelector("strong").textContent).toBe("Answer check");
    expect(check.textContent).toContain("Differences and coverage");
    dom.window.close();
  });

  it("folds judge attempts, retries and backups into one quiet Answer check row", async () => {
    const judge = (id, seq, status, title, extra = {}) => ({ ...agent(seq, status, id), kind: "judge", title,
      model: { model: `m/${seq}`, label: `Judge ${seq}` }, usage: null, ...extra });
    const answer = { ...agent(1, "completed"), kind: "comparison", title: "Comparison 1 · Haiku" };
    const judges = [judge("b".repeat(32), 2, "failed", "Coverage judge"), judge("e".repeat(32), 3, "failed", "Differences judge"),
      judge("f".repeat(32), 4, "completed", "Coverage judge", { usage: { input_tokens: 1500, output_tokens: 400 } }),
      judge("9".repeat(32), 5, "completed", "Differences judge", { usage: { input_tokens: 600, output_tokens: 200 } })];
    const { window: w, document: d, dom } = boot(async () => ({ ok: true, json: async () => ({ agents: [answer, ...judges], status: "succeeded" }) }));
    for (const item of [answer, ...judges]) receive(w, item);
    w.App.agentDelegation.project({ chatId, turnId, running: false });
    expect(d.querySelector(".agent-sidebar-toggle").textContent).toBe("");
    expect(d.querySelector(".agent-sidebar-toggle").getAttribute("aria-label")).toBe("Activity · 2");
    expect(d.querySelectorAll(".agent-inline-model")).toHaveLength(1);
    const rows = [...d.querySelectorAll(".agent-session")];
    expect(rows).toHaveLength(2);
    const check = rows[1];
    expect(check.querySelector("strong").textContent).toBe("Answer check");
    expect(check.querySelector(".agent-session-state").textContent).toMatch(/^Completed · /);
    expect(check.querySelector(".agent-session-tokens").textContent).toMatch(/^2[.,]700 tokens$/);
    expect(d.querySelector(".agent-sidebar-status").textContent).toBe("");
    expect(d.querySelector(".agent-session-list").textContent).not.toMatch(/Failed|Not finished|Replaced|Tokens unavailable|Judge/);
    check.open = true; check.dispatchEvent(new w.Event("toggle"));
    expect(check.querySelector(".agent-judge-note").textContent).toBe("Results are marked in the answer and listed under Review.");
    expect(w.fetch.mock.calls.every(([url]) => url.endsWith("/agents"))).toBe(true);
    dom.window.close();
  });

  it("names a check that no model could run, once, in the Answer check row", () => {
    const failed = { ...agent(1, "failed"), kind: "judge", title: "Differences judge", usage: null };
    const { window: w, document: d, dom } = boot(async () => ({ ok: true, json: async () => ({ agents: [failed], status: "failed" }) }));
    receive(w, failed);
    w.App.agentDelegation.project({ chatId, turnId, running: false });
    d.querySelector(".agent-sidebar-toggle").click();
    const row = d.querySelector(".agent-session");
    expect(row.querySelector(".agent-session-state").textContent).toMatch(/^Not finished · /);
    row.open = true; row.dispatchEvent(new w.Event("toggle"));
    expect(row.querySelector(".agent-judge-note").textContent).toBe("The differences check could not run. The answer is shown without it.");
    dom.window.close();
  });

  it("shows a failed comparison model's reason as a plain note without routing labels", async () => {
    const failed = { ...agent(1, "failed"), kind: "comparison", title: "Comparison 1 · Haiku" };
    const note = "The provider did not finish this answer. The comparison uses the other answers.";
    const { window: w, document: d, dom } = boot(async url => ({ ok: true, json: async () => url.includes(agentId)
      ? { agent: { assignment: { goal: "Comparison 1 · Haiku", context: '{"question":"Q","context":"C"}' } },
          messages: [{ id: "m1", seq: 1, sender: agentId, recipient: "orchestrator", kind: "failure", text: note }] }
      : { agents: [failed], status: "succeeded" } }));
    receive(w, failed);
    w.App.agentDelegation.project({ chatId, turnId });
    d.querySelector(".agent-inline-model").click();
    await vi.waitFor(() => expect(d.querySelector(".agent-session-detail .agent-judge-note")?.textContent).toBe(note));
    const detail = d.querySelector(".agent-session-detail").textContent;
    expect(detail).not.toMatch(/→|Orchestrator|Goal|Trying again/);
    expect(d.querySelector(".agent-session-state").textContent).toMatch(/^No answer · /);
    dom.window.close();
  });

  it("keeps the text of a comparison model stopped mid-answer, marked as incomplete", async () => {
    const stopped = { ...agent(1, "stopped"), kind: "comparison", title: "Comparison 1 · Haiku", partial: true };
    const note = "It was still writing when the answer was checked. The answer and its check use the other answers.";
    const { window: w, document: d, dom } = boot(async url => ({ ok: true, json: async () => url.includes(agentId)
      ? { agent: { assignment: { goal: "Comparison 1 · Haiku" } }, messages: [
          { id: "m1", seq: 1, sender: agentId, recipient: "orchestrator", kind: "partial", text: "First half of an answer" },
          { id: "m2", seq: 2, sender: agentId, recipient: "orchestrator", kind: "failure", text: note }] }
      : { agents: [stopped], status: "succeeded" } }));
    receive(w, stopped);
    w.App.agentDelegation.project({ chatId, turnId });
    expect(d.querySelector(".agent-session-state").textContent).toMatch(/^Incomplete · /);
    d.querySelector(".agent-inline-model").click();
    await vi.waitFor(() => expect(d.querySelector(".agent-session-detail").textContent).toContain("First half of an answer"));
    expect(d.querySelector(".agent-session-detail h3").textContent).toBe("Incomplete answer · not used");
    expect(d.querySelector(".agent-session-detail .agent-judge-note").textContent).toBe(note);
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
  it("sums the run up in one overview and keeps opened details in the single scrolling list", async () => {
    const answer = (id, seq, status) => ({ ...agent(seq, status, id), kind: "comparison", title: "Independent answer" });
    const rows = [answer("a".repeat(32), 1, "completed"), answer("b".repeat(32), 2, "working"), answer("e".repeat(32), 3, "failed")];
    const { window: w, document: d, dom } = boot(async () => ({ ok: true, json: async () => ({ agents: rows, status: "running" }) }));
    for (const item of rows) receive(w, item);
    w.App.agentDelegation.project({ chatId, turnId, running: true });
    expect(d.querySelector(".agent-sidebar-progress").textContent).toBe("2 of 3 done · 1 without result");
    const segments = [...d.querySelectorAll(".agent-sidebar-segments i")];
    expect(segments.map(s => s.dataset.state)).toEqual(["done", "busy", "out"]);
    expect(d.querySelector(".agent-sidebar-segments").getAttribute("aria-hidden")).toBe("true");
    // The detail is no focusable scroll region of its own any more.
    expect(d.querySelector(".agent-session-detail").hasAttribute("tabindex")).toBe(false);
    receive(w, answer("b".repeat(32), 4, "completed"));
    expect(d.querySelector(".agent-sidebar-progress").textContent).toBe("3 of 3 done · 1 without result");
    expect([...d.querySelectorAll(".agent-sidebar-segments i")]).toEqual(segments);
    expect(segments[1].dataset.state).toBe("done");
    dom.window.close();
  });
  it("shows progress at the model icons instead of a separate light line", () => {
    const answer = (id, seq, status) => ({ ...agent(seq, status, id), kind: "comparison", title: "Independent answer",
      model: { model: `test/${id[0]}`, label: id[0] } });
    const judge = (seq, status) => ({ ...agent(seq, status, "f".repeat(32)), kind: "judge", title: "Coverage judge" });
    const { window: w, document: d, dom } = boot(async () => ({ ok: true, json: async () => ({ agents: [], status: "running" }) }));
    d.getElementById("agentAnswerActivity").innerHTML = '<details class="agent-activity is-running"><summary></summary></details>';
    receive(w, answer("a".repeat(32), 1, "completed"));
    receive(w, answer("b".repeat(32), 1, "working"));
    receive(w, judge(1, "working"));
    w.App.agentDelegation.project({ chatId, turnId, running: true });
    const states = () => [...d.querySelectorAll(".agent-activity summary .agent-inline-model")].map(b => b.dataset.status);
    // One icon per comparison model, judges stay out; agent-chat.css reads the state.
    expect(states()).toEqual(["completed", "working"]);
    receive(w, answer("b".repeat(32), 2, "completed"));
    expect(states()).toEqual(["completed", "completed"]);
    expect(d.getElementById("agentAnswerActivity").style.getPropertyValue("--light-p")).toBe("");
    expect(d.querySelector(".agent-light")).toBeNull();
    dom.window.close();
  });
  it("quotes the latest reasoning line of a comparison model that is still answering", () => {
    const answer = (id, seq, status, progress_text) => ({ ...agent(seq, status, id), kind: "comparison",
      model: { model: `test/${id[0]}`, label: id === "a".repeat(32) ? "GPT" : "Gemini" }, progress_text });
    const { window: w, dom } = boot(async () => ({ ok: true, json: async () => ({ agents: [], status: "running" }) }));
    const live = () => w.App.agentDelegation.liveHighlight(chatId, turnId);
    expect(live()).toBeNull();
    receive(w, { ...agent(1, "working", "f".repeat(32)), kind: "judge", progress_text: "Judges never speak here." });
    receive(w, answer("a".repeat(32), 1, "working", "Reading the question.\n- Checking the **2026** `figures`."));
    expect(live()).toMatchObject({ label: "GPT", text: "Checking the 2026 figures." });
    receive(w, answer("b".repeat(32), 1, "working", "Comparing both sources."));
    expect(live()).toMatchObject({ label: "Gemini", text: "Comparing both sources." });
    // A finished model no longer speaks for the running comparison.
    receive(w, answer("b".repeat(32), 2, "completed", "Comparing both sources."));
    expect(live()).toMatchObject({ label: "GPT" });
    receive(w, answer("a".repeat(32), 2, "completed", "Done."));
    expect(live()).toBeNull();
    dom.window.close();
  });
  it("projects a local demo turn without requests and releases it again", async () => {
    const { window: w, document: d, dom } = boot();
    d.getElementById("agentAnswerActivity").innerHTML = "<details><summary></summary></details>";
    const call = (id, status, text = "") => ({ id, kind: "comparison", title: id, status, text,
      model: { label: id, model: "" }, usage: status === "completed" ? { input_tokens: 10, output_tokens: 5, complete: true } : null });
    w.App.agentDelegation.demo({ turnId: "demo-1", running: true, agents: [call("demo-OpenAI", "working"), call("demo-Gemini", "working")] });
    expect(d.querySelectorAll(".agent-inline-model")).toHaveLength(2);
    expect(d.querySelector(".agent-sidebar-stop").hidden).toBe(true);
    w.App.agentDelegation.demo({ turnId: "demo-1", running: false, agents: [call("demo-OpenAI", "completed", "Send it."), call("demo-Gemini", "completed", "Keep it.")] });
    d.querySelector(".agent-session summary").click();
    await vi.waitFor(() => expect(d.querySelector(".agent-session-detail").textContent).toContain("Send it."));
    expect(w.fetch).not.toHaveBeenCalled();
    w.App.agentDelegation.demo(null);
    expect(d.querySelector(".agent-inline-models")).toBeNull();
    expect(d.getElementById("agentSidebar").hidden).toBe(true);
    dom.window.close();
  });
});
