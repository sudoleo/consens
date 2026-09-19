import { describe, expect, it, vi } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

const BODY = `<div id="chatExecutionControl" class="select-wrapper"><select id="chatExecutionMode" aria-label="Chat mode">
  <option value="consensus">Consensus</option><option value="agent">Agent</option></select></div>
  <textarea id="questionInput"></textarea><div id="threadHistory"></div>
  <div id="agentModelControls"><div class="select-wrapper agent-model-picker"><select id="agentModelDropdown" aria-label="Agent model"></select></div>
  <div class="select-wrapper agent-effort-control"><select id="agentReasoningEffort" aria-label="Agent reasoning effort"></select></div><button id="agentModelsRetry" hidden></button></div>
  <section id="agentAnswer" hidden><div id="agentAnswerLabel"></div>
  <div id="agentAnswerActivity"></div><div id="agentAnswerBody"></div><p id="agentAnswerError" hidden></p><button id="agentRecover" hidden></button></section>`;

const CATALOG = { token_budget: { remaining: 188878, limit: 250000, observed_at: 1 }, default_model_id: "deepseek/deepseek-v4.1-flash", models: [
  { id: "deepseek/deepseek-v4.1-flash", label: "DeepSeek V4.1 Flash", reasoning_efforts: ["default", "low", "high", "max"], reasoning_available: true },
  { id: "gpt-5.6-sol", label: "GPT-5.6 Sol", reasoning_efforts: ["default", "low", "medium", "high"], reasoning_available: true },
  { id: "gpt-4o", label: "GPT-4o", reasoning_efforts: ["default"], reasoning_available: false },
] };

function boot({ allowed = true, catalog = CATALOG } = {}) {
  const setup = loadScripts(["static/js/run-registry.js", "static/js/model-picker.js", "static/js/agent-activity.js", "static/js/agent-chat.js"], {
    body: BODY,
    before(window) {
      window.auth = { currentUser: { uid: "owner", getIdToken: async () => "verified" } };
      window.App = {
        agentAccess: { uid: "owner", allowed }, showPopup: vi.fn(),
        followup: { renderStoredTurns: vi.fn() },
        modelPrefs: [], getModelOptionLabel: option => option?.dataset.modelLabel || option?.textContent || "",
      };
      window.injectMarkdown = (el, markdown) => { el.textContent = markdown; };
      window.fetch = vi.fn(async url => ({ ok: true, json: async () => url.startsWith('/agent/') ? structuredClone(catalog) : ({ chat: { id: "a".repeat(32) } }) }));
      window.streamSSERequest = vi.fn(async (_url, _payload, _signal, handlers) => {
        handlers.delta?.append("Answer");
        return { ok: true, data: { response: "Answer", chat_id: "a".repeat(32), turn_id: "b".repeat(32),
          turn: { id: "b".repeat(32), question: "Question", consensus: "Answer", mode: "Agent", execution_mode: "agent" },
          token_budget: structuredClone(CATALOG.token_budget), bookmark_meta: { id: "saved" } } };
      });
      window.acceptPersistedConsensusBookmark = vi.fn();
    },
  });
  setup.document.dispatchEvent(new setup.window.Event("DOMContentLoaded"));
  return setup;
}

async function selectAgent(window) {
  const select = window.document.getElementById("chatExecutionMode");
  select.value = "agent";
  select.dispatchEvent(new window.Event("change"));
  if (window.App.agentChat.canUse()) await vi.waitFor(() => expect(window.document.getElementById("agentModelDropdown").disabled).toBe(false));
}

describe("single-model agent chat", () => {
  it('keeps unresolved admin models visible and disabled, and repairs a saved unavailable selection', async () => {
    const catalog = {...CATALOG, models: [...CATALOG.models,
      {id:'future-missing', label:'Future model', available:false,
        unavailable_reason:'Model information unavailable', reasoning_efforts:['default']}]
      .map(model => ({...model, provider:'openai', provider_label:'OpenAI'}))};
    const {window:w, document:d, dom} = boot({catalog});
    w.localStorage.setItem('agent_settings_owner', JSON.stringify({model_id:'future-missing', reasoning_effort:'high'}));
    await selectAgent(w);
    const select = d.querySelector('#agentModelDropdown');
    expect(select.value).toBe(CATALOG.default_model_id);
    expect(select.querySelector('option[value="future-missing"]').disabled).toBe(true);
    d.querySelector('.agent-model-picker .model-picker-display').click();
    d.querySelector('button[data-model-group="openai"]').click();
    const missing = d.querySelector('.agent-model-picker [data-value="future-missing"]');
    expect(missing.disabled).toBe(true);
    expect(missing.textContent).toContain('Model information unavailable');
    missing.click();
    expect(select.value).toBe(CATALOG.default_model_id);
    dom.window.close();
  });
  it('groups chat models by provider, supports keyboard navigation and keeps reasoning tied to the chosen model', async () => {
    const catalog = {...CATALOG, models: CATALOG.models.map((model, i) => ({...model,
      provider: i ? 'openai' : 'deepseek', provider_label: i ? 'OpenAI' : 'DeepSeek'}))};
    const {window:w, document:d, dom} = boot({catalog});
    await selectAgent(w);
    const select = d.querySelector('#agentModelDropdown');
    const trigger = d.querySelector('.agent-model-picker .model-picker-display');
    const menu = d.querySelector('.agent-model-picker .model-picker-menu');
    trigger.click();
    expect(menu.querySelectorAll('button[data-model-group]')).toHaveLength(2);
    expect(menu.querySelectorAll('[data-value]')).toHaveLength(0);
    expect(menu.getAttribute('role')).toBe('menu');
    expect(trigger.getAttribute('aria-haspopup')).toBe('menu');
    expect(menu.querySelector('.is-current-group').dataset.modelGroup).toBe('deepseek');
    const openai = menu.querySelector('button[data-model-group="openai"]');
    openai.focus();
    openai.dispatchEvent(new w.KeyboardEvent('keydown', {key:'ArrowRight',bubbles:true}));
    expect(menu.querySelectorAll('[data-value]')).toHaveLength(2);
    expect(trigger.getAttribute('aria-haspopup')).toBe('listbox');
    expect(menu.querySelector('[data-value="deepseek/deepseek-v4.1-flash"]')).toBeNull();
    expect(d.activeElement.dataset.value).toBe('gpt-5.6-sol');
    d.activeElement.dispatchEvent(new w.KeyboardEvent('keydown', {key:'ArrowLeft',bubbles:true}));
    expect(menu.querySelectorAll('button[data-model-group]')).toHaveLength(2);
    menu.querySelector('button[data-model-group="openai"]').click();
    menu.querySelector('[data-value="gpt-5.6-sol"]').click();
    expect(select.value).toBe('gpt-5.6-sol');
    expect(menu.classList.contains('is-open')).toBe(false);
    expect(d.activeElement).toBe(trigger);
    expect(JSON.parse(w.localStorage.getItem('agent_settings_owner')).model_id).toBe('gpt-5.6-sol');
    w.App.openModelPicker(select, {secondary:true});
    expect(menu.querySelector('[data-setting-value="medium"]')).not.toBeNull();
    menu.querySelector('.model-picker-back-option').click();
    expect(menu.querySelector('.is-current-group').dataset.modelGroup).toBe('openai');
    menu.querySelector('.agent-reasoning-option').click();
    menu.querySelector('[data-setting-value="medium"]').click();
    expect(d.querySelector('#agentReasoningEffort').value).toBe('medium');
    trigger.click();
    menu.querySelector('button[data-model-group="openai"]').focus();
    d.activeElement.dispatchEvent(new w.KeyboardEvent('keydown', {key:'Escape',bubbles:true}));
    expect(menu.classList.contains('is-open')).toBe(false);
    expect(d.activeElement).toBe(trigger);
    dom.window.close();
  });
  it('orders allowance snapshots by reset, UTC day and ledger revision despite server clock skew', async () => {
    const {window:w,dom} = boot();
    await selectAgent(w);
    const chat = w.App.agentChat;
    const budget = {limit:250000,used:100,reserved:0,remaining:249900,day:'2026-09-19',revision:10,config_revision:1,observed_at:500};
    chat.receiveBudget(budget,'owner');
    chat.receiveBudget({...budget,revision:9,remaining:0,observed_at:1000},'owner');
    expect(chat.tokenBudget()).toEqual(budget);
    const settled = {...budget,used:120,revision:11,remaining:249880,observed_at:100};
    chat.receiveBudget(settled,'owner'); expect(chat.tokenBudget()).toEqual(settled);
    const nextDay = {...budget,day:'2026-09-20',used:0,remaining:250000,revision:0,observed_at:50};
    chat.receiveBudget(nextDay,'owner'); chat.receiveBudget(settled,'owner');
    expect(chat.tokenBudget()).toEqual(nextDay);
    const reset = {...nextDay,revision:0,config_revision:2};
    chat.receiveBudget(reset,'owner'); chat.receiveBudget({...nextDay,revision:100},'owner');
    expect(chat.tokenBudget()).toEqual(reset);
    chat.receiveBudget({...reset,remaining:NaN,revision:1},'owner'); expect(chat.tokenBudget()).toEqual(reset);
    dom.window.close();
  });
  it('refreshes idle allowance on focus and marks failed refreshes as stale', async () => {
    const {window:w,dom} = boot();
    await selectAgent(w);
    const budget = {limit:250000,remaining:250000,observed_at:10};
    w.fetch.mockImplementation(async () => ({ok:true,json:async () => ({token_budget:budget})}));
    w.dispatchEvent(new w.Event('focus'));
    await vi.waitFor(() => expect(w.App.agentChat.tokenBudget()).toEqual(budget));
    w.fetch.mockImplementation(async () => ({ok:false}));
    w.dispatchEvent(new w.Event('focus'));
    await vi.waitFor(() => expect(w.App.agentChat.tokenBudget().stale).toBe(true));
    w.fetch.mockImplementation(async () => ({ok:true,json:async () => ({token_budget:budget})}));
    w.dispatchEvent(new w.Event('focus'));
    await vi.waitFor(() => expect(w.App.agentChat.tokenBudget()).toEqual(budget));
    dom.window.close();
  });
  it('freezes source-check permission for sending and recovery while the next-message preference changes', async () => {
    const {window, document, dom} = boot();
    await selectAgent(window);
    window.App.isSourceCheckEnabled = vi.fn(() => true);
    window.streamSSERequest.mockImplementationOnce(async () => {
      window.App.isSourceCheckEnabled.mockReturnValue(false);
      throw new Error('Connection lost');
    });
    document.getElementById('questionInput').value = 'Compare options';
    await window.App.agentChat.send();
    const context = window.App.runRegistry.visible();
    expect(context.config.checkSources).toBe(true);
    expect(window.streamSSERequest.mock.calls[0][1].check_sources).toBe(true);
    await window.App.agentChat.send(context);
    expect(window.streamSSERequest.mock.calls[1][1]).toMatchObject({check_sources: true, recover_only: true});
    document.getElementById('questionInput').value = 'Next message';
    await window.App.agentChat.send();
    expect(window.streamSSERequest.mock.calls[2][1].check_sources).toBe(false);
    dom.window.close();
  });

  it('updates the allowance on terminal errors and ignores older or foreign snapshots', async () => {
    const { window, document, dom } = boot();
    await selectAgent(window);
    const chat = window.App.agentChat;
    const budget = { remaining: 40000, limit: 250000, observed_at: 20 };
    window.streamSSERequest.mockImplementationOnce(async (_url, _body, _signal, handlers) => {
      handlers.quota.receive({ token_budget: { ...budget, remaining: 80000, observed_at: 10 } });
      expect(chat.tokenBudget().remaining).toBe(80000);
      return { ok: true, data: { error: 'Not enough tokens for the next reservation.', token_budget: budget } };
    });
    document.getElementById('questionInput').value = 'Compare options';
    await chat.send();
    expect(window.App.runRegistry.visible().status).toBe('failed');
    expect(chat.tokenBudget()).toEqual(budget);
    chat.receiveBudget({ ...budget, remaining: 100000, observed_at: 10 }, 'owner');
    chat.receiveBudget({ ...budget, remaining: 0, observed_at: 30 }, 'someone-else');
    expect(chat.tokenBudget()).toEqual(budget);
    expect(window.fetch.mock.calls.map(call => call[0])).toEqual(['/agent/models', '/chats']);
    dom.window.close();
  });

  it('refreshes the allowance after a disconnected stream', async () => {
    const { window, document, dom } = boot();
    await selectAgent(window);
    window.fetch.mockImplementation(async url => ({ ok: true, json: async () => url === '/agent/budget'
      ? { ...CATALOG, token_budget: { remaining: 25000, limit: 250000, observed_at: 2 } } : { chat: { id: 'a'.repeat(32) } } }));
    window.streamSSERequest.mockRejectedValueOnce(new Error('Connection lost'));
    document.getElementById('questionInput').value = 'Question';
    await window.App.agentChat.send();
    expect(window.App.agentChat.tokenBudget().remaining).toBe(25000);
    expect(window.fetch.mock.calls.map(call => call[0])).toEqual(['/agent/models', '/chats', '/agent/budget']);
    dom.window.close();
  });

  it('leaves tool mentions plain and highlights only confirmed running calls', () => {
    const { window, document, dom } = boot();
    const host = document.getElementById('agentAnswerActivity');
    const events = [{ id: 'r', kind: 'reasoning', format: 'summary', text: 'Maybe call compare_models, then judge_answer. <img src=x onerror=alert(1)>' }];
    window.App.agentActivity.render(host, { events, running: true });
    expect(host.querySelector('.agent-tool-mention')).toBe(null);
    expect(host.querySelector('.agent-progress').textContent).toContain('compare_models');
    expect(host.querySelector('.agent-progress-action')).toBe(null);
    expect(host.querySelector('img')).toBe(null);
    events.push({id: 'tool1', kind: 'tool', name: 'compare_models', status: 'running'});
    window.App.agentActivity.render(host, { events, running: true });
    expect(host.querySelector('.agent-activity-title').textContent).toBe('Comparing perspectives…');
    expect(host.querySelector('.agent-progress-action')).toBe(null);
    expect(host.querySelector('.agent-progress').textContent).not.toContain('Comparing perspectives…');
    expect(host.querySelector('details').open).toBe(false);
    events[1].status = 'succeeded';
    window.App.agentActivity.render(host, { events, running: true });
    expect(host.querySelector('.agent-progress-action')).toBe(null);
    window.App.agentActivity.render(host, { events, running: false });
    expect(host.querySelector('.agent-progress').hidden).toBe(true);
    expect(host.querySelector('.agent-activity-tool strong').textContent).toBe('Model comparison · Completed');
    dom.window.close();
  });

  it('keeps a review stage in one heading when tool events arrive', () => {
    const { window, document, dom } = boot();
    const host = document.getElementById('agentAnswerActivity');
    const state = { running: true, review: {status: 'running'}, events: [] };
    window.App.agentActivity.render(host, state);
    expect(host.querySelector('.agent-progress-action')).toBe(null);
    state.events.push({id:'judge', kind:'tool', name:'judge_answer', status:'running'});
    window.App.agentActivity.render(host, state);
    expect(host.querySelector('.agent-activity-title').textContent).toBe('Checking the answer…');
    expect(host.querySelector('.agent-progress').hidden).toBe(true);
    expect(host.textContent.match(/Checking the answer…/g)).toHaveLength(1);
    state.events[0].status = 'failed';
    window.App.agentActivity.render(host, state);
    expect(host.querySelector('.agent-progress-action')).toBe(null);
    dom.window.close();
  });
  it("commits a draft model before an input-triggered projection can restore the old model", async () => {
    const { window, document, dom } = boot();
    await selectAgent(window);
    const select = document.getElementById("agentModelDropdown");
    select.addEventListener("input", () => window.App.agentChat.render());
    document.querySelector("#agentModelControls .model-picker-display").click();
    document.querySelector('#agentModelControls [data-value="gpt-4o"]').click();
    expect(select.value).toBe("gpt-4o");
    window.App.agentChat.render();
    expect(select.value).toBe("gpt-4o");
    document.getElementById("questionInput").value = "First question";
    await window.App.agentChat.send();
    expect(window.streamSSERequest.mock.calls[0][1].model_id).toBe("gpt-4o");
    expect(select.value).toBe("gpt-4o");
    dom.window.close();
  });

  it("keeps a running chat's model independent of an earlier draft selection", async () => {
    const { window, document, dom } = boot();
    await selectAgent(window);
    const select = document.getElementById("agentModelDropdown");
    select.value = CATALOG.default_model_id;
    select.dispatchEvent(new window.Event("change"));
    window.App.runRegistry.create({ question: "Restored run", config: {
      executionMode: "agent", agentSettings: { model_id: "gpt-4o", reasoning_effort: "default" } },
      metadata: { agentSettings: { model_id: "gpt-4o", reasoning_effort: "default" } } });
    expect(select.value).toBe("gpt-4o");
    dom.window.close();
  });

  it("shows provider costs separately from estimates and removes status dashes", () => {
    const { window, document, dom } = boot();
    const host = document.getElementById("agentAnswerActivity");
    const usage = { input_tokens: 100, output_tokens: 20, estimated_cost_nano_usd: 12000000, cost_source: "provider" };
    window.App.agentActivity.render(host, { usage, status: "failed" });
    expect(host.querySelector(".agent-usage").textContent).toContain("$0.0120 provider cost");
    expect(host.querySelector("summary").textContent).toBe("Response failed");
    expect(host.querySelector(".agent-activity-marker")).toBe(null);
    window.App.agentActivity.render(host, { usage: { ...usage, cost_source: "catalog" } });
    expect(host.querySelector(".agent-usage").textContent).toContain("~$0.0120 estimated");
    dom.window.close();
  });

  it.each(["cancel", "error"])("keeps the selected conversation when a background follow-up ends: %s", async end => {
    const { window, document, dom } = boot();
    await selectAgent(window);
    document.getElementById("questionInput").value = "First";
    await window.App.agentChat.send();
    const registry = window.App.runRegistry;
    const original = registry.getSelectedConversationBasis();
    let reject;
    window.streamSSERequest.mockImplementationOnce(() => new Promise((_resolve, r) => { reject = r; }));
    document.getElementById("questionInput").value = "Follow up";
    const sending = window.App.agentChat.send();
    await vi.waitFor(() => expect(reject).toBeTypeOf("function"));
    const run = registry.visible();
    const other = { chatId: "c".repeat(32), bookmarkId: "other", question: "Other", consensus: "Other answer", executionMode: "agent" };
    registry.showSavedView({ type: "bookmark" }, other);
    if (end === "cancel") registry.cancel(run.runId);
    reject(new Error("Connection ended"));
    await sending;
    expect(registry.getSelectedConversationBasis().chatId).toBe(other.chatId);
    expect(run.status).toBe(end === "cancel" ? "canceled" : "failed");
    registry.show(run.runId);
    expect(registry.getSelectedConversationBasis().chatId).toBe(original.chatId);
    dom.window.close();
  });

  it("recovers a first message without borrowing another conversation's history", async () => {
    const { window, document, dom } = boot();
    await selectAgent(window);
    window.streamSSERequest.mockRejectedValueOnce(new Error("Connection lost"));
    document.getElementById("questionInput").value = "First";
    await window.App.agentChat.send();
    const failed = window.App.runRegistry.visible();
    window.App.runRegistry.showSavedView({ type: "bookmark" }, {
      chatId: "c".repeat(32), bookmarkId: "other", question: "Other", consensus: "Other answer", executionMode: "agent",
      currentTurn: { id: "other-turn", question: "Other", consensus: "Other answer" },
    });
    await window.App.agentChat.send(failed);
    expect(window.App.runRegistry.visible().historyTurns).toHaveLength(0);
    expect(window.App.runRegistry.visible().basis).toBe(null);
    expect(window.streamSSERequest.mock.calls[1][1].chat_id).toBe("a".repeat(32));
    dom.window.close();
  });

  it("does not start a model request after cancellation during chat creation", async () => {
    const { window, document, dom } = boot();
    await selectAgent(window);
    let resolve;
    window.fetch.mockImplementationOnce(() => new Promise(r => { resolve = r; }));
    document.getElementById("questionInput").value = "First";
    const sending = window.App.agentChat.send();
    await vi.waitFor(() => expect(resolve).toBeTypeOf("function"));
    window.App.runRegistry.cancel(window.App.runRegistry.visible().runId);
    resolve({ ok: true, json: async () => ({ chat: { id: "a".repeat(32) } }) });
    await sending;
    expect(window.streamSSERequest).not.toHaveBeenCalled();
    dom.window.close();
  });

  it("reconciles a removed saved model with the displayed choice before sending", async () => {
    const { window, document, dom } = boot();
    window.localStorage.setItem("agent_settings_owner", JSON.stringify({ model_id: "removed-model", reasoning_effort: "ultra" }));
    await selectAgent(window);
    expect(document.getElementById("agentModelDropdown").value).toBe(CATALOG.default_model_id);
    expect(document.getElementById("agentModelNotice")).toBe(null);
    expect(document.querySelector(".agent-model-picker .model-picker-display").textContent).toContain("DeepSeek V4.1 Flash");
    expect(JSON.parse(window.localStorage.getItem("agent_settings_owner"))).toEqual({
      model_id: CATALOG.default_model_id, reasoning_effort: "default",
    });
    expect(window.App.showPopup).toHaveBeenCalledTimes(1);
    window.App.agentChat.render();
    window.App.agentChat.render();
    expect(window.App.showPopup).toHaveBeenCalledTimes(1);
    expect(document.getElementById("agentReasoningEffort").value).toBe("default");
    document.getElementById("questionInput").value = "Question";
    await window.App.agentChat.send();
    expect(window.streamSSERequest.mock.calls[0][1]).toMatchObject({ model_id: CATALOG.default_model_id, reasoning_effort: "default" });
    dom.window.close();
  });

  it("uses the same keyboard picker for effort and returns focus after choosing", async () => {
    const { window, document, dom } = boot();
    await selectAgent(window);
    const trigger = document.querySelector(".agent-model-picker .model-picker-display");
    trigger.focus();
    trigger.dispatchEvent(new window.KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true, cancelable: true }));
    document.querySelector('.agent-reasoning-option').click();
    expect(document.activeElement.dataset.settingValue).toBe("default");
    document.activeElement.dispatchEvent(new window.KeyboardEvent("keydown", { key: "End", bubbles: true, cancelable: true }));
    expect(document.activeElement.dataset.settingValue).toBe("max");
    document.activeElement.click();
    expect(document.getElementById("agentReasoningEffort").value).toBe("max");
    expect(document.activeElement).toBe(trigger);
    expect(trigger.getAttribute("aria-expanded")).toBe("false");
    trigger.click();
    expect(trigger.getAttribute("aria-expanded")).toBe("true");
    trigger.click();
    expect(trigger.getAttribute("aria-expanded")).toBe("false");
    trigger.click();
    document.getElementById("questionInput").focus();
    await Promise.resolve();
    expect(trigger.getAttribute("aria-expanded")).toBe("false");
    dom.window.close();
  });

  it("collapses finished reasoning, preserves explicit disclosure, and restores stopped status", () => {
    const { window, document, dom } = boot();
    const activity = window.App.agentActivity;
    const host = document.getElementById("agentAnswerActivity");
    const events = [{ id: "r1", kind: "reasoning", format: "text", text: "Consider the question" }];
    activity.render(host, { events, running: true });
    const details = host.querySelector("details");
    expect(details.open).toBe(false);
    expect(host.querySelector('.agent-progress').hidden).toBe(false);
    expect(host.querySelector('.agent-progress p').textContent).toBe('Consider the question');
    activity.render(host, { events, running: false });
    expect(details.open).toBe(false);
    expect(host.querySelector('.agent-progress').hidden).toBe(true);
    details.querySelector("summary").click();
    activity.render(host, { events, running: false });
    expect(details.open).toBe(true);
    activity.renderTurn(host, { status: "failed", error_code: "cancelled", agent_activity: events });
    expect(host.querySelector(".agent-activity-title").textContent).toBe("Response stopped");
    expect(host.querySelector(".agent-activity").classList.contains("is-running")).toBe(false);
    activity.render(host, { usage: { input_tokens: 10, output_tokens: 3, estimated_cost_nano_usd: null } });
    expect(host.querySelector(".agent-usage").textContent).toBe("13 tokens");
    dom.window.close();
  });

  it("requires the current account's entitlement and retains no cross-account access", async () => {
    const { window, document, dom } = boot({ allowed: false });
    await selectAgent(window);
    expect(window.App.agentChat.isSelected()).toBe(false);
    expect(document.getElementById("chatExecutionControl").hidden).toBe(true);
    window.App.agentAccess.allowed = true;
    await selectAgent(window);
    expect(window.App.agentChat.isSelected()).toBe(true);
    window.auth.currentUser.uid = "different-owner";
    window.App.agentChat.render();
    expect(window.App.agentChat.canUse()).toBe(false);
    dom.window.close();
  });

  it("calls only the agent endpoint and continues the same persisted chat", async () => {
    const { window, document, dom } = boot();
    await selectAgent(window);
    document.getElementById("questionInput").value = "Question";
    await window.App.agentChat.send();
    expect(window.fetch.mock.calls.map(call => call[0])).toEqual(["/agent/models", "/chats"]);
    expect(window.streamSSERequest).toHaveBeenCalledTimes(1);
    const [url, payload, , , options] = window.streamSSERequest.mock.calls[0];
    expect(url).toBe("/agent");
    expect(payload.question).toBe("Question");
    expect(options.headers.Authorization).toBe("Bearer verified");
    expect(payload).not.toHaveProperty("model");
    expect(payload.model_id).toBe(CATALOG.default_model_id);
    expect(payload).not.toHaveProperty("usage_run_key");
    expect(window.App.runRegistry.visible().status).toBe("succeeded");
    expect(window.App.runRegistry.getSelectedConversationBasis().executionMode).toBe("agent");
    expect(document.getElementById("chatExecutionMode").disabled).toBe(true);
    document.getElementById("questionInput").value = "Follow-up";
    await window.App.agentChat.send();
    expect(window.fetch).toHaveBeenCalledTimes(2);
    expect(window.streamSSERequest).toHaveBeenCalledTimes(2);
    expect(window.App.runRegistry.visible().historyTurns).toHaveLength(1);
    expect(window.streamSSERequest.mock.calls[1][1].chat_id).toBe("a".repeat(32));
    dom.window.close();
  });

  it("rejects attachments before any network call", async () => {
    const { window, document, dom } = boot();
    await selectAgent(window);
    document.getElementById("questionInput").value = "Question";
    window.getAttachmentsPayload = () => [{ name: "private.pdf" }];
    await window.App.agentChat.send();
    expect(window.fetch.mock.calls.map(call => call[0])).toEqual(["/agent/models"]);
    expect(window.streamSSERequest).not.toHaveBeenCalled();
    expect(window.App.showPopup).toHaveBeenCalledWith(expect.stringContaining("text only"));
    dom.window.close();
  });

  it("restores an agent bookmark independently of the global consensus preference", async () => {
    const { window, document, dom } = boot();
    window.App.runRegistry.showSavedView({ type: "bookmark" }, {
      chatId: "a".repeat(32), turnId: "b".repeat(32), question: "Q", consensus: "Saved answer",
      currentTurn: { mode: "Agent", execution_mode: "agent" },
    });
    expect(window.App.agentChat.isSelected()).toBe(true);
    expect(document.getElementById("agentAnswerBody").textContent).toBe("Saved answer");
    await vi.waitFor(() => expect(document.getElementById("agentModelDropdown").disabled).toBe(false));
    window.App.runRegistry.clearVisible();
    expect(window.App.agentChat.isSelected()).toBe(false);
    expect(document.getElementById("chatExecutionMode").disabled).toBe(false);
    dom.window.close();
  });

  it("ignores late completion after logout", async () => {
    const { window, document, dom } = boot();
    await selectAgent(window);
    let resolve;
    window.streamSSERequest = vi.fn(() => new Promise(r => { resolve = r; }));
    document.getElementById("questionInput").value = "Question";
    const pending = window.App.agentChat.send();
    await vi.waitFor(() => expect(resolve).toBeTypeOf("function"));
    window.App.runRegistry.clearAll("logout");
    window.auth.currentUser = null;
    resolve({ ok: true, data: { response: "Late", turn: {} } });
    await pending;
    expect(window.acceptPersistedConsensusBookmark).not.toHaveBeenCalled();
    expect(window.App.runRegistry.visible()).toBe(null);
    dom.window.close();
  });

  it("recovers with the same identity and an explicit no-new-call flag", async () => {
    const { window, document, dom } = boot();
    await selectAgent(window);
    window.streamSSERequest.mockRejectedValueOnce(new Error("Connection lost"));
    document.getElementById("questionInput").value = "Question";
    await window.App.agentChat.send();
    const failed = window.App.runRegistry.visible();
    expect(failed.status).toBe("failed");
    expect(document.getElementById('agentRecover').textContent).toBe('Check saved answer');
    await window.App.agentChat.send(failed);
    expect(window.fetch.mock.calls.map(call => call[0])).toEqual(['/agent/models', '/chats', '/agent/budget']);
    const payload = window.streamSSERequest.mock.calls[1][1];
    expect(payload.recover_only).toBe(true);
    expect(payload.client_request_id).toBe(window.streamSSERequest.mock.calls[0][1].client_request_id);
    expect(window.App.runRegistry.visible().status).toBe("succeeded");
    expect(window.App.runRegistry.list()).toHaveLength(1);
    dom.window.close();
  });

  it('adopts a server-saved partial answer and bookmark while preserving its failed review', async () => {
    const {window:w,document:d,dom} = boot();
    await selectAgent(w);
    const turn = {id:'b'.repeat(32),execution_mode:'agent',status:'failed',consensus:'Available answer.',
      agent_failure:{code:'provider_timeout',error:'The provider stopped responding.'},agent_review:{status:'failed',comparisons:[]}};
    w.streamSSERequest.mockResolvedValueOnce({ok:false,data:{error:'The provider stopped responding.',recoverable:true,recovery_state:'saved',
      saved_answer:{chat_id:'a'.repeat(32),turn_id:turn.id,response:turn.consensus,turn,bookmark_meta:{id:'saved'}},token_budget:CATALOG.token_budget}});
    d.getElementById('questionInput').value = 'Question';
    await w.App.agentChat.send();
    const run = w.App.runRegistry.visible();
    expect(run.bookmark.status).toBe('succeeded');
    expect(run.consensus.completedTurn.agent_review.status).toBe('failed');
    w.App.agentChat.project(run);
    expect(d.getElementById('agentAnswerBody').textContent).toBe('Available answer.');
    expect(d.getElementById('agentAnswerError').textContent).toContain('provider stopped');
    expect(d.getElementById('agentRecover').hidden).toBe(true);
    expect(w.acceptPersistedConsensusBookmark).toHaveBeenCalledTimes(1);
    dom.window.close();
  });

  it('offers a status check rather than claiming an unfinished server run is already saved', async () => {
    const {window:w,document:d,dom} = boot();
    await selectAgent(w);
    w.streamSSERequest.mockRejectedValueOnce(new Error('Connection lost'));
    d.getElementById('questionInput').value = 'Question';
    await w.App.agentChat.send();
    w.streamSSERequest.mockResolvedValueOnce({ok:false,data:{error:'The request is still running.',code:'request_running',recoverable:true,recovery_state:'running'}});
    await w.App.agentChat.send(w.App.runRegistry.visible());
    expect(d.getElementById('agentRecover').textContent).toBe('Check run status');
    expect(w.App.runRegistry.list()).toHaveLength(1);
    expect(w.streamSSERequest.mock.calls[1][1].recover_only).toBe(true);
    dom.window.close();
  });

  it('does not offer recovery without a saved answer and deduplicates concurrent recovery clicks', async () => {
    const {window: w, document: d, dom} = boot();
    await selectAgent(w);
    w.streamSSERequest.mockResolvedValueOnce({ok: true, data: {error: 'Not enough reservation', recoverable:false, token_budget:CATALOG.token_budget}});
    d.getElementById('questionInput').value = 'Question';
    await w.App.agentChat.send();
    const run = w.App.runRegistry.visible();
    expect(d.getElementById('agentRecover').hidden).toBe(true);
    await w.App.agentChat.send(run);
    expect(w.streamSSERequest).toHaveBeenCalledTimes(1);
    run.metadata.recoverable = undefined; // a transport failure has unknown server state
    let finish;
    w.streamSSERequest.mockImplementationOnce(() => new Promise(resolve => {finish = resolve;}));
    const pending = w.App.agentChat.send(run);
    await vi.waitFor(() => expect(finish).toBeTypeOf('function'));
    expect(d.getElementById('agentRecover').disabled).toBe(true);
    await w.App.agentChat.send(run);
    expect(w.streamSSERequest).toHaveBeenCalledTimes(2);
    finish({ok:false,data:{error:'This run ended without a saved answer.',recoverable:false}});
    await pending;
    expect(w.App.runRegistry.list()).toHaveLength(1);
    expect(w.App.runRegistry.visible()).toBe(run);
    expect(d.getElementById('agentRecover').hidden).toBe(true);
    expect(run.consensus.error.message).toBe('Not enough reservation');
    dom.window.close();
  });

  it('keeps a new budget generation when an older worker sends a later snapshot', async () => {
    const {window:w,dom} = boot(); await selectAgent(w);
    const budget = {...CATALOG.token_budget,remaining:250000,config_revision:2,observed_at:10};
    w.App.agentChat.receiveBudget(budget,'owner');
    w.App.agentChat.receiveBudget({...budget,remaining:100,config_revision:1,observed_at:20},'owner');
    expect(w.App.agentChat.tokenBudget()).toEqual(budget);
    dom.window.close();
  });

  it("rebuilds its history after displaying another conversation", async () => {
    const { window, document, dom } = boot();
    await selectAgent(window);
    document.getElementById("questionInput").value = "Question";
    await window.App.agentChat.send();
    const run = window.App.runRegistry.visible();
    run.historyTurns.push({ question: "Old", consensus: "Long history ".repeat(10000) });
    window.App.agentChat.project(run);
    expect(document.getElementById("threadHistory").dataset.agentHistory.length).toBeLessThan(100);
    const count = window.App.followup.renderStoredTurns.mock.calls.length;
    window.App.agentChat.project(run);
    expect(window.App.followup.renderStoredTurns.mock.calls.length).toBe(count);
    window.App.runRegistry.showSavedView({type: "bookmark"}, {question: "Another", consensus: "Other answer"});
    window.App.runRegistry.show(run.runId);
    window.App.agentChat.project(run);
    expect(window.App.followup.renderStoredTurns.mock.calls.length).toBe(count + 1);
    dom.window.close();
  });

  it("reuses the picker, sends supported effort, and leaves consensus preferences alone", async () => {
    const { window, document, dom } = boot();
    window.localStorage.setItem("pref_consensus_preset", "daily");
    await selectAgent(window);
    const select = document.getElementById("agentModelDropdown");
    document.querySelector("#agentModelControls .model-picker-display").click();
    document.querySelector('#agentModelControls [data-value="gpt-5.6-sol"]').click();
    const effort = document.getElementById("agentReasoningEffort");
    expect([...effort.options].map(option => option.value)).toEqual(["default", "low", "medium", "high"]);
    effort.value = "medium";
    effort.dispatchEvent(new window.Event("change"));
    document.getElementById("questionInput").value = "Question";
    await window.App.agentChat.send();
    expect(window.streamSSERequest.mock.calls[0][1]).toMatchObject({ model_id: "gpt-5.6-sol", reasoning_effort: "medium" });
    expect(window.localStorage.getItem("pref_consensus_preset")).toBe("daily");
    select.value = "gpt-4o";
    select.dispatchEvent(new window.Event("change"));
    expect(effort.parentElement.hidden).toBe(true);
    expect(effort.value).toBe("default");
    dom.window.close();
  });

  it("streams reasoning separately, preserves disclosure, and ignores deltas after stop", async () => {
    const { window, document, dom } = boot();
    await selectAgent(window);
    let handlers, resolve;
    window.streamSSERequest = vi.fn((_url, _payload, _signal, received) => {
      handlers = received;
      return new Promise(r => { resolve = r; });
    });
    document.getElementById("questionInput").value = "Question";
    const pending = window.App.agentChat.send();
    await vi.waitFor(() => expect(handlers).toBeDefined());
    const run = window.App.runRegistry.visible();
    window.App.agentDelegation = {receiveProgress:vi.fn(),project:vi.fn()};
    const progress = {version:1,chars:120};
    handlers.delegation_progress.receive(progress);
    expect(window.App.agentDelegation.receiveProgress).toHaveBeenCalledWith(run,progress);
    const event = { version: 1, step_id: "completion:0", kind: "reasoning", id: "r1", format: "summary", text: "First thought", append: true };
    handlers.activity.receive(event);
    window.App.agentChat.project(run);
    const details = document.querySelector("#agentAnswerActivity details");
    expect(details.open).toBe(false);
    expect(document.querySelector('.agent-progress').textContent).toContain('First thought');
    expect(details.textContent).toContain("First thought");
    expect(document.getElementById("agentAnswerBody").textContent).not.toContain("First thought");
    expect(document.getElementById("agentModelDropdown").disabled).toBe(true);
    details.querySelector("summary").click();
    handlers.activity.receive({ ...event, text: " continued" });
    window.App.agentChat.project(run);
    expect(details.open).toBe(true);
    window.App.runRegistry.cancel(run.runId);
    handlers.delegation_progress.receive({...progress,chars:900});
    expect(window.App.agentDelegation.receiveProgress).toHaveBeenCalledTimes(1);
    handlers.activity.receive({ ...event, text: " forbidden late text" });
    window.App.agentChat.project(run);
    expect(details.textContent).not.toContain("forbidden");
    expect(details.textContent).toContain("Response stopped");
    resolve({ ok: true, data: { response: "Late", turn: {} } });
    await pending;
    expect(window.acceptPersistedConsensusBookmark).not.toHaveBeenCalled();
    dom.window.close();
  });

  it("restores reasoning and settings from a saved turn without treating reasoning as HTML", async () => {
    const { window, document, dom } = boot();
    const turn = { mode: "Agent", execution_mode: "agent", agent_settings: { model_id: "gpt-5.6-sol", label: "GPT-5.6 Sol", reasoning_effort: "medium" },
      agent_activity: [{ version: 1, id: "r1", kind: "reasoning", format: "text", text: '<img src=x onerror="alert(1)">Saved thought' }],
      agent_usage: { input_tokens: 100, output_tokens: 20, estimated_cost_nano_usd: 10000 } };
    window.App.runRegistry.showSavedView({ type: "bookmark" }, { chatId: "a".repeat(32), turnId: "b".repeat(32),
      question: "Q", consensus: "Saved answer", currentTurn: turn });
    await vi.waitFor(() => expect(document.getElementById("agentModelDropdown").disabled).toBe(false));
    expect(document.getElementById("agentModelDropdown").value).toBe("gpt-5.6-sol");
    expect(document.getElementById("agentReasoningEffort").value).toBe("medium");
    expect(document.querySelector("#agentAnswerActivity img")).toBe(null);
    expect(document.getElementById("agentAnswerActivity").textContent).toContain("Saved thought");
    expect(document.getElementById("agentAnswerActivity").textContent).toContain("120 tokens");
    dom.window.close();
  });

  it("repairs a removed history model for the next message without changing its saved label", async () => {
    const { window, document, dom } = boot();
    await selectAgent(window);
    const settings = { model_id: "removed-model", label: "Historical model", reasoning_effort: "ultra" };
    const basis = { chatId: "c".repeat(32), bookmarkId: "old", question: "Old question", consensus: "Old answer", executionMode: "agent",
      currentTurn: { id: "old-turn", question: "Old question", consensus: "Old answer", agent_settings: settings } };
    window.App.runRegistry.showSavedView({ type: "bookmark" }, basis);
    expect(document.getElementById("agentModelDropdown").value).toBe(CATALOG.default_model_id);
    expect(document.getElementById("agentAnswerLabel").textContent).toContain("Historical model");
    window.App.agentChat.render();
    expect(window.App.showPopup).toHaveBeenCalledTimes(1);
    expect(window.App.runRegistry.getSelectedConversationBasis().currentTurn.agent_settings).toEqual(settings);
    document.getElementById("questionInput").value = "Follow up";
    await window.App.agentChat.send();
    expect(window.streamSSERequest.mock.calls[0][1]).toMatchObject({ model_id: CATALOG.default_model_id, reasoning_effort: "default" });
    dom.window.close();
  });

  it("keeps the actual failure reason visible when reopening an incomplete answer", async () => {
    const { window, document, dom } = boot();
    const failure = "The model provider stopped responding. Your available answer has been saved.";
    const turn = { status: "failed", error_code: "agent_failed", execution_mode: "agent",
      agent_failure: { code: "provider_timeout", error: failure } };
    window.App.runRegistry.showSavedView({ type: "bookmark" }, { chatId: "a".repeat(32), turnId: "b".repeat(32),
      question: "Q", consensus: "Preserved partial answer", executionMode: "agent", currentTurn: turn });
    await vi.waitFor(() => expect(document.getElementById("agentModelDropdown").disabled).toBe(false));
    expect(document.getElementById("agentAnswerBody").textContent).toBe("Preserved partial answer");
    expect(document.getElementById("agentAnswerError").hidden).toBe(false);
    expect(document.getElementById("agentAnswerError").textContent).toBe(failure);
    dom.window.close();
  });

  it.each(["server_tool", "provider_native"])("hides legacy unconfirmed searches (%s) while preserving reasoning and measured costs", flag => {
    const { window, document, dom } = boot();
    const host = document.getElementById("agentAnswerActivity");
    const events = [
      { id: "r1", kind: "reasoning", format: "text", text: "A casual greeting. No tool needed." },
      { id: "s1", kind: "tool", name: "web_search", status: "unknown", [flag]: true },
    ];
    window.App.agentActivity.renderTurn(host, { agent_activity: events,
      agent_usage: { input_tokens: 800, output_tokens: 62, estimated_cost_nano_usd: 400000, cost_source: "provider", complete: true } });
    expect(host.querySelector(".agent-activity-title").textContent).toBe("Reasoning");
    expect(host.querySelector(".agent-activity-tool")).toBe(null);
    expect(host.querySelector(".agent-usage").textContent).toBe("862 tokens · $0.0004 provider cost");
    // A count or citations confirm use even if the response was interrupted.
    for (const evidence of [{ count: 1 }, { sources: [{ url: "https://example.org", title: "Source" }] }]) {
      window.App.agentActivity.renderTurn(host, { agent_activity: [{ ...events[1], ...evidence }] });
      expect(host.querySelector(".agent-activity-tool")).not.toBe(null);
    }
    // Unknown client-call outcomes are not the legacy synthetic native event.
    window.App.agentActivity.renderTurn(host, { agent_activity: [{ ...events[1], [flag]: false }] });
    expect(host.querySelector(".agent-activity-tool")).not.toBe(null);
    dom.window.close();
  });

  it("renders confirmed native sources, partial usage and safe links from history", () => {
    const { window, document, dom } = boot();
    const host = document.getElementById("agentAnswerActivity");
    const events = [];
    const native = { version: 1, step_id: "completion:0:web_search", id: "completion:0:web_search/tool", kind: "tool",
      name: "web_search", status: "succeeded", count: 2, sources: [
        { url: "https://example.com/report", title: '<img src=x onerror="alert(1)">Report' },
        { url: "javascript:alert(1)", title: "Unsafe" }, { url: "https://user:pass@example.com", title: "Credentials" }], };
    window.App.agentActivity.receive(events, native);
    window.App.agentActivity.receive(events, { ...native, count: 1 });
    expect(events).toHaveLength(1);
    window.App.agentActivity.renderTurn(host, { agent_activity: events, agent_usage: {
      input_tokens: 100, output_tokens: 20, complete: false, estimated_cost_nano_usd: 10000000 } });
    expect(host.textContent).toContain("Activity and sources");
    expect(host.textContent).toContain("Web search · Completed · 1 search");
    expect(host.textContent).toContain("usage incomplete");
    expect(host.querySelector("img")).toBe(null);
    expect(host.querySelectorAll("a")).toHaveLength(1);
    expect(host.querySelector("a").rel).toBe("noopener noreferrer");
    expect(host.querySelector("details").open).toBe(false);
    dom.window.close();
  });

  it("keeps tool states honest and clears intermediate answer text for a new step", async () => {
    const { window, document, dom } = boot();
    await selectAgent(window);
    let handlers, resolve;
    window.streamSSERequest = vi.fn((_url, _payload, _signal, received) => {
      handlers = received;
      return new Promise(r => { resolve = r; });
    });
    document.getElementById("questionInput").value = "Question";
    const pending = window.App.agentChat.send();
    await vi.waitFor(() => expect(handlers).toBeDefined());
    const run = window.App.runRegistry.visible();
    handlers.delta.append("Let me check.");
    const event = { version: 1, step_id: "tool:0", id: "tool:0/tool", kind: "tool", name: "double", status: "running" };
    handlers.activity.receive(event);
    window.App.agentChat.project(run);
    const host = document.getElementById("agentAnswerActivity");
    expect(host.querySelector('.agent-activity-title').textContent).toBe("Running a tool…");
    expect(host.querySelector("details").open).toBe(false);
    expect(host.querySelector('.agent-progress').hidden).toBe(true);
    handlers.activity.receive({ ...event, status: "succeeded", text: '{"result":4}' });
    handlers.activity.receive({ version: 1, step_id: "completion:1", id: "completion:1/started", kind: "status", status: "working", clear_response: true });
    expect(run.consensus.streamText).toBe("");
    handlers.delta.append("The result is 4.");
    window.App.agentChat.project(run);
    expect(host.textContent).not.toContain("Running a tool…");
    expect(document.getElementById("agentAnswerBody").textContent).not.toContain("Let me check");
    window.App.runRegistry.cancel(run.runId);
    handlers.activity.receive({ ...event, status: "running" });
    expect(run.metadata.agentActivity.find(item => item.id === event.id).status).toBe("succeeded");
    resolve({ ok: true, data: { response: "Late", turn: {} } });
    await pending;
    dom.window.close();
  });
});
