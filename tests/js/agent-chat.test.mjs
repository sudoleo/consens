import { describe, expect, it, vi } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

const BODY = `<textarea id="questionInput"></textarea><div id="threadHistory"></div>
  <input id="compareOpenAI" type="checkbox" checked><select id="compareOpenAIModel"><option value="gpt-5.4-mini">OpenAI</option></select>
  <input id="compareClaude" type="checkbox" checked><select id="compareClaudeModel"><option value="claude-haiku-4-5">Claude</option></select>
  <div id="agentModelControls"><div class="select-wrapper agent-model-picker"><select id="agentModelDropdown" aria-label="Agent model"></select></div>
  <div class="select-wrapper agent-effort-control"><select id="agentReasoningEffort" aria-label="Agent reasoning effort"></select></div><button id="agentModelsRetry" hidden></button></div>
  <section id="agentAnswer" hidden>
  <div id="agentAnswerActivity"></div><div id="agentAnswerBody"></div><p id="agentAnswerError" hidden></p><button id="agentRecover" hidden></button></section>`;

const CATALOG = { token_budget: { remaining: 188878, limit: 250000, observed_at: 1 }, default_model_id: "deepseek/deepseek-v4.1-flash", models: [
  { id: "deepseek/deepseek-v4.1-flash", label: "DeepSeek V4.1 Flash", reasoning_efforts: ["default", "low", "high", "max"], reasoning_available: true },
  { id: "gpt-5.6-sol", label: "GPT-5.6 Sol", reasoning_efforts: ["default", "low", "medium", "high"], reasoning_available: true },
  { id: "gpt-4o", label: "GPT-4o", reasoning_efforts: ["default"], reasoning_available: false },
] };

function boot({ allowed = true, catalog = CATALOG, body = BODY, setup: prepare } = {}) {
  const setup = loadScripts(["static/js/run-mode.js", "static/js/run-registry.js", "static/js/token-budget.js", "static/js/model-picker.js", "static/js/request-deadline.js", "static/js/agent-activity.js", "static/js/agent-chat.js"], {
    body,
    before(window) {
      // These cases start from a Consensus preference; Agent is the default.
      window.localStorage.setItem("runMode", "consensus");
      window.localStorage.setItem("runModeDefault", "agent-2026-10-02");
      window.auth = { currentUser: { uid: "owner", getIdToken: async () => "verified" } };
      window.App = {
        agentAccess: { uid: "owner", allowed }, showPopup: vi.fn(),
        followup: { renderStoredTurns: vi.fn() },
        modelPrefs: [{provider:'openai',checkId:'compareOpenAI',selectId:'compareOpenAIModel'},
          {provider:'anthropic',checkId:'compareClaude',selectId:'compareClaudeModel'}],
        getModelOptionLabel: option => option?.dataset.modelLabel || option?.textContent || "",
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
      prepare?.(window);
    },
  });
  setup.document.dispatchEvent(new setup.window.Event("DOMContentLoaded"));
  return setup;
}

async function selectAgent(window) {
  // The one mode choice (run-mode.js); agent-chat.js re-renders on its event.
  window.App.runMode.set("consensus");
  window.App.runMode.set("agent");
  if (window.App.agentChat.canUse()) await vi.waitFor(() => expect(window.document.getElementById("agentModelDropdown").disabled).toBe(false));
}

describe("single-model agent chat", () => {
  it('blocks sending during catalog loading/failure and when every model is unavailable', async () => {
    const {window:w, document:d, dom} = boot();
    let release;
    w.fetch.mockImplementationOnce(() => new Promise(resolve => { release = resolve; }));
    d.body.insertAdjacentHTML('beforeend', '<div id="agentComposerNotice" hidden><span id="agentComposerMessage"></span><button id="agentComposerAction" hidden></button></div>');
    w.App.runMode.set('agent');
    w.App.agentChat.syncComposer();
    expect(w.App.agentChat.sendBlocker().message).toContain('Loading chat models');
    // A short load never flashes the notice (it moved the centred composer).
    expect(d.getElementById('agentComposerNotice').hidden).toBe(true);
    await vi.waitFor(() => expect(d.getElementById('agentComposerNotice').hidden).toBe(false), { timeout: 3000 });
    await vi.waitFor(() => expect(release).toBeTypeOf('function'));
    release({ok:false, json:async () => ({})});
    await vi.waitFor(() => expect(w.App.agentChat.sendBlocker().message).toContain('could not be loaded'));
    w.fetch.mockResolvedValueOnce({ok:true, json:async () => ({...CATALOG, models: CATALOG.models.map(m => ({...m, available:false}))})});
    d.getElementById('agentModelsRetry').click();
    await vi.waitFor(() => expect(w.App.agentChat.sendBlocker().message).toContain('No chat models'));
    d.getElementById('questionInput').value = 'Keep this draft';
    await w.App.agentChat.send();
    expect(w.streamSSERequest).not.toHaveBeenCalled();
    expect(d.getElementById('questionInput').value).toBe('Keep this draft');
    dom.window.close();
  });

  it.each(['empty', 'new draft', 'new quote', 'different chat', 'different account'])('restores an unsent draft without replacing newer composer ownership: %s', async newer => {
    const {window:w, document:d, dom} = boot();
    await selectAgent(w);
    let quoted = 'A quoted passage';
    w.App.quote = {text: () => quoted, compose: text => `${text}\n${quoted}`, clear: () => { quoted = ''; }, set: text => { quoted = text; }};
    let release;
    w.fetch.mockImplementationOnce(() => new Promise(resolve => { release = resolve; }));
    const input = d.getElementById('questionInput');
    input.value = 'My original question\nwith two lines';
    const sending = w.App.agentChat.send();
    await vi.waitFor(() => expect(release).toBeTypeOf('function'));
    if (newer === 'new draft') input.value = 'My newer question';
    if (newer === 'new quote') quoted = 'My newer quote';
    if (newer === 'different chat') w.App.runRegistry.clearVisible();
    if (newer === 'different account') w.auth.currentUser = {uid: 'other'};
    release({ok:false, json:async () => ({detail:'Could not create chat'})});
    await sending;
    expect(w.streamSSERequest).not.toHaveBeenCalled();
    expect(input.value).toBe(newer === 'empty' ? 'My original question\nwith two lines' : newer === 'new draft' ? 'My newer question' : '');
    expect(quoted).toBe(newer === 'empty' ? 'A quoted passage' : newer === 'new quote' ? 'My newer quote' : '');
    dom.window.close();
  });

  it('does not restore an already dispatched request as an unsent draft', async () => {
    const {window:w, document:d, dom} = boot();
    await selectAgent(w);
    w.streamSSERequest.mockRejectedValueOnce(new Error('Connection lost'));
    d.getElementById('questionInput').value = 'Sent question';
    await w.App.agentChat.send();
    expect(d.getElementById('questionInput').value).toBe('');
    expect(w.App.runRegistry.visible().metadata.requestSent).toBe(true);
    dom.window.close();
  });

  it.each([0, 1, 2, 6, 7])('validates %i comparison models before clearing the draft or creating a chat', async count => {
    const {window:w, document:d, dom} = boot();
    await selectAgent(w);
    w.App.modelPrefs = Array.from({length:count}, (_, i) => {
      const check = d.createElement('input'); check.type='checkbox'; check.id=`auditCheck${i}`; check.checked=true;
      const select = d.createElement('select'); select.id=`auditSelect${i}`;
      select.innerHTML=`<option value="model${i}">Model ${i}</option>`;
      d.body.append(check,select);
      return {provider:`provider${i}`,checkId:check.id,selectId:select.id};
    });
    d.getElementById('questionInput').value='Please compare these options.';
    w.fetch.mockClear();
    await w.App.agentChat.send();
    if (count < 2 || count > 6) {
      expect(w.fetch).not.toHaveBeenCalled();
      expect(w.streamSSERequest).not.toHaveBeenCalled();
      expect(d.getElementById('questionInput').value).toBe('Please compare these options.');
      expect(w.App.showPopup).toHaveBeenCalledWith(expect.stringContaining('comparison models'));
    } else {
      expect(w.streamSSERequest).toHaveBeenCalledTimes(1);
      expect(Object.keys(w.streamSSERequest.mock.calls[0][1].comparison_models)).toHaveLength(count);
    }
    dom.window.close();
  });
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
    let now = w.Date.now();
    w.Date.now = () => now;
    await selectAgent(w);
    // Focus right after the catalog brought the allowance: nothing to fetch.
    const loaded = w.fetch.mock.calls.length;
    w.dispatchEvent(new w.Event('focus'));
    await new Promise(resolve => setTimeout(resolve, 20));
    expect(w.fetch.mock.calls.length).toBe(loaded);
    now += 61000;
    const budget = {limit:250000,remaining:250000,observed_at:10};
    w.fetch.mockImplementation(async () => ({ok:true,json:async () => ({token_budget:budget})}));
    w.dispatchEvent(new w.Event('focus'));
    await vi.waitFor(() => expect(w.App.agentChat.tokenBudget()).toEqual(budget));
    now += 61000;
    w.fetch.mockImplementation(async () => ({ok:false}));
    w.dispatchEvent(new w.Event('focus'));
    await vi.waitFor(() => expect(w.App.agentChat.tokenBudget().stale).toBe(true));
    w.fetch.mockImplementation(async () => ({ok:true,json:async () => ({token_budget:budget})}));
    w.dispatchEvent(new w.Event('focus'));
    await vi.waitFor(() => expect(w.App.agentChat.tokenBudget()).toEqual(budget));
    dom.window.close();
  });
  it('recovers the model picker and budget refresh after hung control requests', async () => {
    const {window:w,document:d,dom} = boot();
    const originalTimer = w.setTimeout.bind(w);
    let timeout;
    w.setTimeout = (fn, ms, ...args) => ms === 15000 ? (timeout = fn, 999) : originalTimer(fn, ms, ...args);
    w.fetch.mockImplementationOnce(() => new Promise(() => {}));
    w.App.runMode.set('agent');
    await vi.waitFor(() => expect(timeout).toBeTypeOf('function'));
    await vi.waitFor(() => expect(w.fetch).toHaveBeenCalledTimes(1));
    timeout();
    await vi.waitFor(() => expect(d.querySelector('#agentModelsRetry').hidden).toBe(false));
    d.querySelector('#agentModelsRetry').click();
    await vi.waitFor(() => expect(d.querySelector('#agentModelDropdown').disabled).toBe(false));
    w.fetch.mockImplementationOnce(() => new Promise(() => {}));
    const before = w.fetch.mock.calls.length;
    const later = w.Date.now() + 61000;
    w.Date.now = () => later;
    w.dispatchEvent(new w.Event('focus'));
    await vi.waitFor(() => expect(w.fetch.mock.calls.length).toBe(before + 1));
    timeout();
    await vi.waitFor(() => expect(w.App.agentChat.tokenBudget().stale).toBe(true));
    w.fetch.mockResolvedValueOnce({ok:true,json:async () => ({token_budget:CATALOG.token_budget})});
    w.dispatchEvent(new w.Event('focus'));
    await vi.waitFor(() => expect(w.App.agentChat.tokenBudget().stale).not.toBe(true));
    dom.window.close();
  });
  it('ends a silent Agent connection with recoverable partial text and a known turn identity', async () => {
    const {window:w,document:d,dom} = boot();
    await selectAgent(w);
    const originalTimer = w.setTimeout.bind(w);
    let timeout, signal;
    w.setTimeout = (fn, ms, ...args) => ms === 45000 ? (timeout = fn, 999) : originalTimer(fn, ms, ...args);
    w.streamSSERequest.mockImplementationOnce((_url, _body, incoming, handlers) => {
      signal = incoming;
      handlers.accepted.receive({chat_id:'a'.repeat(32),turn_id:'c'.repeat(32)});
      handlers.delta.append('Available partial text.');
      return new Promise(() => {});
    });
    d.querySelector('#questionInput').value = 'Question';
    const sending = w.App.agentChat.send();
    await vi.waitFor(() => expect(signal).toBeDefined());
    // Before giving up, the server is asked twice; it knows no saved answer.
    w.streamSSERequest.mockResolvedValue({ ok: false, status: 404, streamed: false,
      data: { error: 'No saved answer is available for this request.', code: 'answer_unavailable', recoverable: false } });
    const first = timeout; first();
    await vi.waitFor(() => expect(timeout).not.toBe(first));
    timeout(); await sending;
    const run = w.App.runRegistry.visible();
    expect(signal.aborted).toBe(true);
    expect(run.status).toBe('failed');
    expect(run.consensus.streamText).toBe('Available partial text.');
    expect(run.metadata.agentTurnId).toBe('c'.repeat(32));
    expect(d.querySelector('#agentRecover').hidden).toBe(false);
    dom.window.close();
  });
  it('keeps a silent stream open while the server reports the run still running and adopts its saved answer', async () => {
    const {window:w,document:d,dom} = boot();
    await selectAgent(w);
    const originalTimer = w.setTimeout.bind(w);
    let timeout, signal;
    w.setTimeout = (fn, ms, ...args) => ms === 45000 ? (timeout = fn, 999) : originalTimer(fn, ms, ...args);
    w.streamSSERequest.mockImplementationOnce((_url, _body, incoming) => { signal = incoming; return new Promise(() => {}); });
    d.querySelector('#questionInput').value = 'Question behind a buffering proxy';
    const sending = w.App.agentChat.send();
    await vi.waitFor(() => expect(signal).toBeDefined());
    const sent = w.streamSSERequest.mock.calls[0][1];
    w.streamSSERequest.mockResolvedValueOnce({ ok: false, status: 409, streamed: false,
      data: { error: 'This request is still running.', code: 'request_running', recoverable: true, recovery_state: 'running' } });
    const first = timeout; first();
    await vi.waitFor(() => expect(timeout).not.toBe(first));
    expect(signal.aborted).toBe(false);
    expect(w.App.runRegistry.visible().status).toBe('running');
    w.streamSSERequest.mockResolvedValueOnce({ ok: true, status: 200, streamed: false, data: { response: 'Saved answer',
      chat_id: 'a'.repeat(32), turn_id: 'b'.repeat(32), bookmark_meta: { id: 'saved' },
      turn: { id: 'b'.repeat(32), question: sent.question, consensus: 'Saved answer', status: 'completed', execution_mode: 'agent' } } });
    timeout(); await sending;
    const checks = w.streamSSERequest.mock.calls.slice(1).map(call => call[1]);
    expect(checks).toHaveLength(2);
    // Same identity, no new paid call.
    for (const check of checks) expect(check).toEqual({ ...sent, recover_only: true });
    expect(signal.aborted).toBe(true);
    expect(w.App.runRegistry.visible().status).toBe('succeeded');
    expect(w.App.runRegistry.visible().consensus.text).toBe('Saved answer');
    dom.window.close();
  });

  it('offers Retry after a failed run and sends the same message again in the same chat', async () => {
    const {window:w,document:d,dom} = boot();
    d.body.insertAdjacentHTML('beforeend', '<div id="agentAnswerErrorActions" hidden></div><div id="bookmarksContainer"></div>');
    await selectAgent(w);
    w.streamSSERequest.mockImplementationOnce(async (_u, _p, _s, handlers) => {
      handlers.accepted.receive({ chat_id: 'a'.repeat(32), turn_id: 'c'.repeat(32) });
      return { ok: false, status: 200, streamed: true, data: { error: 'This model is busy at its provider right now.',
        code: 'provider_rate_limited', retry_after: 30, recoverable: false } };
    });
    d.getElementById('questionInput').value = 'Rate this site';
    await w.App.agentChat.send();
    const failed = w.App.runRegistry.visible();
    expect(failed.status).toBe('failed');
    failed.metadata.fileIds = ['f'.repeat(32)];
    w.App.agentChat.project(failed);
    const buttons = [...d.querySelectorAll('#agentAnswerErrorActions button')];
    expect(buttons.map(b => b.textContent)).toEqual(['Retry', 'Choose another model']);
    d.getElementById('questionInput').value = 'An unrelated draft';
    buttons[0].click();
    await vi.waitFor(() => expect(w.App.runRegistry.visible().status).toBe('succeeded'));
    const [first, second] = w.streamSSERequest.mock.calls.map(call => call[1]);
    expect(second).toMatchObject({ chat_id: first.chat_id, question: 'Rate this site', bookmark_id: first.bookmark_id,
      file_ids: ['f'.repeat(32)], recover_only: false });
    expect(second.client_request_id).not.toBe(first.client_request_id);
    // One chat creation, the composer's own draft untouched, one sidebar row.
    expect(w.fetch.mock.calls.filter(([url]) => url === '/chats')).toHaveLength(1);
    expect(d.getElementById('questionInput').value).toBe('An unrelated draft');
    expect(d.querySelector(`.bookmark.run-entry[data-run-id="${failed.runId}"]`)).toBeNull();
    dom.window.close();
  });

  it('explains allowance waiting outside the collapsed activity details', () => {
    const {window:w,document:d,dom} = boot();
    const host = d.querySelector('#agentAnswerActivity');
    const text = 'Waiting for active model calls to finish and release their unused allowance.';
    w.App.agentActivity.render(host, {running:true,events:[{kind:'status',id:'wait',status:'waiting',text}]});
    expect(host.querySelector('.agent-progress .agent-current-status').textContent).toContain('Waiting for available tokens');
    expect(host.querySelector('.agent-progress').textContent).toContain(text);
    expect(host.querySelector('details').open).toBe(false);
    dom.window.close();
  });
  it('keeps the newest status and usage after long runs exceed the activity window', () => {
    const {window:w,document:d,dom} = boot();
    const events = [];
    for (let i = 0; i < 100; i++) w.App.agentActivity.receive(events, {version:1,kind:'status',id:`step-${i}`,status:'working'});
    w.App.agentActivity.receive(events, {version:1,kind:'status',id:'waiting',status:'waiting',text:'Waiting for another call.'});
    expect(events).toHaveLength(64);
    expect(events.at(-1).status).toBe('waiting');
    w.App.agentActivity.receive(events, {version:1,kind:'status',id:'step-99',status:'responding'});
    w.App.agentActivity.render(d.querySelector('#agentAnswerActivity'), {events,running:true});
    expect(d.querySelector('.agent-progress .agent-current-status').textContent).toBe('Writing answer…');
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
    expect(host.querySelector('.agent-progress .agent-current-status').textContent).toBe('Comparing perspectives…');
    expect(host.querySelector('.agent-progress-action')).toBe(null);
    expect(host.querySelector('.agent-progress').textContent).toContain('Comparing perspectives…');
    expect(host.querySelector('details').open).toBe(false);
    events[1].status = 'succeeded';
    window.App.agentActivity.render(host, { events, running: true });
    expect(host.querySelector('.agent-progress-action')).toBe(null);
    window.App.agentActivity.render(host, { events, running: false });
    expect(host.querySelector('.agent-progress').hidden).toBe(true);
    expect(host.querySelector('.agent-activity-tool strong').textContent).toBe('Model comparison · Completed');
    dom.window.close();
  });

  it('keeps a review stage in one live row when tool events arrive', () => {
    const { window, document, dom } = boot();
    const host = document.getElementById('agentAnswerActivity');
    const state = { running: true, review: {status: 'running'}, events: [] };
    window.App.agentActivity.render(host, state);
    expect(host.querySelector('.agent-progress-action')).toBe(null);
    state.events.push({id:'judge', kind:'tool', name:'judge_answer', status:'running'});
    window.App.agentActivity.render(host, state);
    expect(host.querySelector('.agent-progress .agent-current-status').textContent).toBe('Checking the answer…');
    expect(host.querySelector('.agent-progress').hidden).toBe(false);
    expect(host.querySelector('.agent-progress').textContent.match(/Checking the answer…/g)).toHaveLength(1);
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
    expect(host.querySelector("summary").textContent).toContain("Response failed");
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
    expect(document.getElementById('questionInput').value).toBe('First');
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

  it('interleaves confirmed steps with complete localized updates and preserves the finished history', () => {
    const { window, document, dom } = boot();
    const activity = window.App.agentActivity;
    const host = document.getElementById('agentAnswerActivity');
    const events = [];
    const first = {version:1, id:'p1', kind:'progress', text:'Ich vergleiche die Optionen. Dabei berücksichtige ich dein Budget.'};
    const second = {version:1, id:'p2', kind:'progress', text:'Die Antworten sind sich beim Preis einig. Ich prüfe die Belege. <img src=x>'};
    activity.receive(events, first);
    activity.render(host, {events, running:true});
    const firstNode = host.querySelector('.agent-progress p');
    activity.receive(events, {version:1,id:'compare',kind:'tool',name:'compare_models',status:'running'});
    activity.render(host, {events, running:true});
    const stepNode = host.querySelector('.agent-progress-step');
    expect(stepNode.textContent).toBe('Comparing perspectives…');
    activity.receive(events, {version:1,id:'compare',kind:'tool',name:'compare_models',status:'succeeded'});
    activity.receive(events, second);
    activity.receive(events, second);
    activity.render(host, {events, running:true});
    expect([...host.querySelectorAll('.agent-progress p')].map(p => p.textContent)).toEqual([first.text, second.text]);
    expect(host.querySelector('.agent-progress p')).toBe(firstNode);
    expect([...host.querySelector('.agent-progress').children].map(p => p.textContent))
      .toEqual([first.text, 'Compared perspectives', second.text, 'Thinking…']);
    expect(host.querySelector('.agent-progress-step')).toBe(stepNode);
    expect(host.querySelector('img')).toBe(null);
    expect(host.querySelector('.agent-progress').getAttribute('role')).toBe('log');
    const details = host.querySelector('details');
    details.querySelector('summary').click();
    expect(details.open).toBe(true);
    activity.render(host, {events, running:false});
    expect(details.open).toBe(false);
    expect(host.querySelector('.agent-progress').hidden).toBe(true);
    expect(host.querySelector('.agent-progress').childElementCount).toBe(0);
    details.querySelector('summary').click();
    activity.renderTurn(host, {status:'completed', agent_activity:events});
    expect(details.open).toBe(true);
    expect([...details.querySelectorAll('.agent-activity-update')].map(p => p.textContent)).toEqual([first.text, second.text]);
    expect(details.querySelector('.agent-activity-note').hidden).toBe(true);
    dom.window.close();
  });

  it('reads a complete, checked answer as done even when the run failed afterwards', () => {
    const {window: w, document: d, dom} = boot();
    const host = d.getElementById('agentAnswerActivity');
    w.App.agentReview = {...w.App.agentReview, renderActivity: w.App.agentReview?.renderActivity || (() => {}),
      failureNote: (failure, review, raw) => review?.status === 'succeeded' && raw ? '' : 'incomplete'};
    w.App.agentActivity.render(host, {running:false, status:'failed', elapsedMs:103000, answerText:'Answer.', review:{status:'succeeded'}});
    expect(host.querySelector('.agent-activity-title').textContent).toBe('Thought for 1m 43s');
    w.App.agentActivity.render(host, {running:false, status:'failed', elapsedMs:103000, answerText:'Answer.', review:null});
    expect(host.querySelector('.agent-activity-title').textContent).toBe('Response failed after 1m 43s');
    dom.window.close();
  });

  it('names the sources a web search found instead of the bare verb', () => {
    const {window: w, document: d, dom} = boot();
    const host = d.getElementById('agentAnswerActivity');
    const search = {id:'s', kind:'tool', name:'web_search', status:'succeeded', count:2, sources:[
      {url:'https://www.skat.dk/a'}, {url:'https://virk.dk/b'}, {url:'https://virk.dk/c'},
      {url:'https://borger.dk/d'}, {url:'https://example.org/e'}, {url:'javascript:alert(1)'}, {url:'https://u:p@evil.test/'}]};
    w.App.agentActivity.render(host, {running:true, events:[search]});
    const step = [...host.querySelectorAll('.agent-progress-step')].map(p => p.textContent);
    expect(step[0]).toBe('Searched the web · 5 sources: skat.dk, virk.dk, borger.dk, +1');
    w.App.agentActivity.render(host, {running:true, events:[{...search, sources:[]}]});
    expect(host.querySelector('.agent-progress-step').textContent).toBe('Searched the web · 2 searches');
    dom.window.close();
  });

  it('does not claim to write the answer while a preamble led into a tool step', () => {
    const {window: w, document: d, dom} = boot();
    const host = d.getElementById('agentAnswerActivity');
    const events = [{id:'c0', kind:'status', status:'responding'},
      {id:'s', kind:'tool', name:'web_search', status:'succeeded', count:1}];
    w.App.agentActivity.render(host, {running:true, events});
    expect(host.querySelector('.agent-current-status').textContent).toBe('Thinking…');
    events.push({id:'c1', kind:'status', status:'responding'});
    w.App.agentActivity.render(host, {running:true, events});
    expect(host.querySelector('.agent-current-status').textContent).toBe('Writing answer…');
    dom.window.close();
  });

  it('shows useful run details when opened during thinking, before any progress or tool event', () => {
    const {window: w, document: d, dom} = boot();
    const host = d.getElementById('agentAnswerActivity');
    w.App.agentActivity.render(host, {running:true, settings:{label:'DeepSeek V4.1 Flash',reasoning_effort:'high'}});
    const details = host.querySelector('details');
    details.querySelector('summary').click();
    expect(details.open).toBe(true);
    expect([...details.querySelectorAll('.agent-activity-run-details dd')].map(el => el.textContent))
      .toEqual(['DeepSeek V4.1 Flash','High','Thinking…']);
    w.App.agentActivity.render(host, {running:true,settings:{label:'DeepSeek V4.1 Flash',reasoning_effort:'high'},responding:true});
    expect(details.querySelector('[role="status"]').textContent).toBe('Writing answer…');
    expect(details.open).toBe(true);
    dom.window.close();
  });

  it('ticks runtime through waiting, freezes at stop, and disposes the live timer', () => {
    const { window, document, dom } = boot();
    const activity = window.App.agentActivity;
    const host = document.getElementById('agentAnswerActivity');
    let now = 0, tick;
    vi.spyOn(window.performance, 'now').mockImplementation(() => now);
    vi.spyOn(window, 'setInterval').mockImplementation(callback => { tick = callback; return 123; });
    const clear = vi.spyOn(window, 'clearInterval');
    activity.render(host, {running:true, elapsedMs:59900});
    const title = host.querySelector('.agent-activity-title');
    expect(title.textContent).toBe('Working for 59s');
    expect(title.getAttribute('aria-live')).toBe('off');
    now = 1100; tick();
    expect(title.textContent).toBe('Working for 1m 1s');
    activity.render(host, {running:true, events:[{id:'wait',kind:'status',status:'waiting'}]});
    now = 2100; tick();
    expect(title.textContent).toBe('Working for 1m 2s');
    expect(host.querySelector('.agent-progress .agent-current-status').textContent).toContain('Waiting');
    activity.render(host, {running:false,status:'canceled'});
    expect(clear).toHaveBeenCalledWith(123);
    expect(host._agentActivity.clockTimer).toBe(null);
    now = 10000;
    activity.render(host, {running:false,status:'canceled'});
    expect(title.textContent).toBe('Stopped after 1m 2s');
    activity.render(host, {running:true,elapsedMs:2000});
    activity.dispose(host);
    expect(host._agentActivity.clockTimer).toBe(null);
    expect(() => activity.dispose(null)).not.toThrow();
    dom.window.close();
  });

  it('restores saved runtime from terminal timestamps rather than the time since creation', () => {
    const { window, document, dom } = boot();
    const activity = window.App.agentActivity;
    const host = document.getElementById('agentAnswerActivity');
    const turn = {created_at:'2026-09-20T10:00:00Z', completed_at:'2026-09-20T11:02:03Z'};
    activity.renderTurn(host, turn);
    expect(host.querySelector('.agent-activity-title').textContent).toBe('Thought for 1h 2m 3s');
    expect(host._agentActivity.clockTimer).toBe(null);
    expect(activity.savedDuration({created_at:turn.created_at, failed_at:'2026-09-20T10:00:45Z'})).toBe(45000);
    for (const invalid of [{}, {created_at:turn.created_at}, {...turn,completed_at:'invalid'},
      {...turn,completed_at:'2026-09-19T00:00:00Z'}]) expect(activity.savedDuration(invalid)).toBe(null);
    dom.window.close();
  });

  it('retains live insights across a partial final snapshot and uses saved tool outcomes', async () => {
    const { window: w, document: d, dom } = boot();
    await selectAgent(w);
    w.streamSSERequest.mockImplementationOnce(async (_url, _payload, _signal, handlers) => {
      handlers.activity.receive({version:1,id:'p1',kind:'progress',text:'Ich prüfe die Belege.'});
      handlers.activity.receive({version:1,id:'t1',kind:'tool',name:'judge_answer',status:'running'});
      return {ok:true,data:{response:'Answer',chat_id:'a'.repeat(32),turn_id:'b'.repeat(32),turn:{id:'b'.repeat(32),
        execution_mode:'agent',status:'completed',consensus:'Answer',
        agent_activity:[{version:1,id:'t1',kind:'tool',name:'judge_answer',status:'succeeded'}]}}};
    });
    d.getElementById('questionInput').value = 'Question';
    await w.App.agentChat.send();
    const saved = w.App.runRegistry.getSelectedConversationBasis().currentTurn;
    expect(saved.agent_activity.map(e => e.id)).toEqual(['p1','t1']);
    expect(saved.agent_activity[1].status).toBe('succeeded');
    w.App.runRegistry.showSavedView({type:'bookmark'}, {chatId:'a'.repeat(32),turnId:saved.id,
      executionMode:'agent',question:'Question',consensus:'Answer',currentTurn:saved});
    const details = d.querySelector('#agentAnswerActivity details');
    details.querySelector('summary').click();
    expect(details.querySelector('.agent-activity-update').textContent).toBe('Ich prüfe die Belege.');
    expect(details.querySelector('.agent-activity-tool').textContent).toContain('Completed');
    dom.window.close();
  });

  it('retains progress paragraphs and confirmed steps when the auxiliary status window rotates', () => {
    const { window, dom } = boot();
    const events = [];
    for (let i = 0; i < 90; i++) {
      window.App.agentActivity.receive(events, {version:1,id:`p${i}`,kind:'progress',text:`Check ${i}`});
      window.App.agentActivity.receive(events, {version:1,id:`t${i}`,kind:'tool',name:'compare_models',status:'succeeded'});
      window.App.agentActivity.receive(events, {version:1,id:`s${i}`,kind:'status',status:'working'});
    }
    expect(events.filter(e => e.kind === 'progress')).toHaveLength(90);
    expect(events.filter(e => e.kind === 'tool')).toHaveLength(90);
    expect(events.filter(e => e.kind === 'status')).toHaveLength(64);
    expect(events.at(-1).id).toBe('s89');
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
    expect(host.querySelector(".agent-activity-title").textContent).toMatch(/^Stopped after \d+s$/);
    expect(host.querySelector(".agent-activity").classList.contains("is-running")).toBe(false);
    activity.render(host, { usage: { input_tokens: 10, output_tokens: 3, estimated_cost_nano_usd: null } });
    expect(host.querySelector(".agent-usage").textContent).toBe("13 tokens");
    dom.window.close();
  });

  it("requires the current account's entitlement and retains no cross-account access", async () => {
    const { window, document, dom } = boot({ allowed: false });
    await selectAgent(window);
    expect(window.App.agentChat.isSelected()).toBe(false);
    expect(window.App.runMode.availability().agent.visible).toBe(false);
    expect(window.App.runMode.effective()).toBe("consensus");
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
    // An open Agent chat keeps its family: Compare and Consensus need a new chat.
    expect(window.App.runMode.availability().consensus.enabled).toBe(false);
    expect(window.App.runMode.availability().compare.reason).toBe("Available in a new chat");
    document.getElementById("questionInput").value = "Follow-up";
    await window.App.agentChat.send();
    expect(window.fetch).toHaveBeenCalledTimes(2);
    expect(window.streamSSERequest).toHaveBeenCalledTimes(2);
    expect(window.App.runRegistry.visible().historyTurns).toHaveLength(1);
    expect(window.streamSSERequest.mock.calls[1][1].chat_id).toBe("a".repeat(32));
    dom.window.close();
  });

  it("uploads attachments before starting the agent and freezes IDs for recovery", async () => {
    const { window, document, dom } = boot();
    await selectAgent(window);
    document.getElementById("questionInput").value = "Question";
    window.getAttachmentsPayload = () => [{ name: "private.txt", data: "SGVsbG8=" }];
    window.App.agentWorkspace = { refresh: vi.fn(), upload: vi.fn(async context => {
      expect(context.metadata.requestSent).not.toBe(true);
      expect(context.attachments[0].name).toBe("private.txt");
      context.metadata.fileIds = ["f".repeat(32)];
    }) };
    await window.App.agentChat.send();
    expect(window.App.agentWorkspace.upload).toHaveBeenCalledOnce();
    expect(window.streamSSERequest.mock.calls[0][1].file_ids).toEqual(["f".repeat(32)]);
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
    expect(window.App.runMode.availability().consensus.enabled).toBe(true);
    expect(window.App.runMode.availability().agent.enabled).toBe(true);
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
    expect(details.textContent).toMatch(/Stopped after \d+s/);
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
    expect(document.getElementById("agentAnswerLabel")).toBeNull();
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
    expect(host.querySelector(".agent-activity-title").textContent).toBe("Activity");
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
    expect(host.textContent).toContain("Activity");
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
    expect(host.querySelector('.agent-progress .agent-current-status').textContent).toBe("Working on a step…");
    expect(host.querySelector("details").open).toBe(false);
    expect(host.querySelector('.agent-progress').hidden).toBe(false);
    handlers.activity.receive({ ...event, status: "succeeded", text: '{"result":4}' });
    handlers.activity.receive({ version: 1, step_id: "completion:1", id: "completion:1/started", kind: "status", status: "working", clear_response: true });
    expect(run.consensus.streamText).toBe("");
    handlers.delta.append("The result is 4.");
    window.App.agentChat.project(run);
    expect(host.textContent).not.toContain("Working on a step…");
    expect(document.getElementById("agentAnswerBody").textContent).not.toContain("Let me check");
    window.App.runRegistry.cancel(run.runId);
    handlers.activity.receive({ ...event, status: "running" });
    expect(run.metadata.agentActivity.find(item => item.id === event.id).status).toBe("succeeded");
    resolve({ ok: true, data: { response: "Late", turn: {} } });
    await pending;
    dom.window.close();
  });

  it('routes resources events to the list they name and refreshes both when unsure', async () => {
    const { window: w, document: d, dom } = boot();
    await selectAgent(w);
    w.App.agentWorkspace = { refresh: vi.fn(), upload: vi.fn(async () => []) };
    w.App.agentGoogle = { refreshActions: vi.fn(), selection: () => null, consent: () => false, resetConsent: vi.fn() };
    let handlers, resolve;
    w.streamSSERequest = vi.fn((_u, _p, _s, received) => { handlers = received; return new Promise(r => { resolve = r; }); });
    d.getElementById('questionInput').value = 'Question';
    const pending = w.App.agentChat.send();
    await vi.waitFor(() => expect(handlers).toBeDefined());
    const chat = 'a'.repeat(32);
    // A brand-new chat never asks for its (empty) actions list before resources.
    expect(w.App.agentGoogle.refreshActions.mock.calls.some(([id]) => id === chat)).toBe(false);
    w.App.agentWorkspace.refresh.mockClear(); w.App.agentGoogle.refreshActions.mockClear();
    handlers.resources.receive({ documents: [{ id: 'x' }] });
    expect(w.App.agentWorkspace.refresh).toHaveBeenCalledWith(chat, true);
    expect(w.App.agentGoogle.refreshActions).not.toHaveBeenCalled();
    w.App.agentWorkspace.refresh.mockClear();
    handlers.resources.receive({ gmail_evidence: [] });
    expect(w.App.agentGoogle.refreshActions).toHaveBeenCalledWith(chat, true);
    expect(w.App.agentWorkspace.refresh).not.toHaveBeenCalled();
    w.App.agentGoogle.refreshActions.mockClear();
    handlers.resources.receive({});
    expect(w.App.agentWorkspace.refresh).toHaveBeenCalledWith(chat, true);
    expect(w.App.agentGoogle.refreshActions).toHaveBeenCalledWith(chat, true);
    resolve({ ok: true, data: { response: 'Answer', chat_id: chat, turn_id: 'b'.repeat(32),
      turn: { id: 'b'.repeat(32), consensus: 'Answer', execution_mode: 'agent' }, bookmark_meta: { id: 'saved' } } });
    await pending;
    dom.window.close();
  });

  it('never re-renders the composer shell or the full answer for a streamed chunk', async () => {
    const { window: w, document: d, dom } = boot();
    await selectAgent(w);
    w.renderMarkdownStream = vi.fn((el, md) => { el.textContent = md; });
    w.resetMarkdownStream = vi.fn();
    const full = vi.fn((el, md) => { el.textContent = md; });
    w.injectMarkdown = full;
    w.App.agentReview = { render: vi.fn(), renderActivity: vi.fn() };
    const pickers = vi.fn();
    w.App.initCustomModelPicker = pickers;
    let handlers, resolve;
    w.streamSSERequest = vi.fn((_u, _p, _s, received) => { handlers = received; return new Promise(r => { resolve = r; }); });
    d.getElementById('questionInput').value = 'Question';
    const pending = w.App.agentChat.send();
    await vi.waitFor(() => expect(handlers).toBeDefined());
    const run = w.App.runRegistry.visible();
    handlers.delta.append('First part.');
    w.App.agentChat.project(run);
    pickers.mockClear(); full.mockClear(); w.App.agentReview.render.mockClear();
    for (const chunk of [' More.', ' Even more.', ' Last.']) {
      handlers.delta.append(chunk);
      w.App.agentChat.project(run);
      w.dispatchEvent(new w.CustomEvent('consensio:run-registry-change', { detail: { context: run } }));
    }
    expect(pickers).not.toHaveBeenCalled();
    expect(full).not.toHaveBeenCalled();
    expect(w.renderMarkdownStream).toHaveBeenLastCalledWith(d.getElementById('agentAnswerBody'), 'First part. More. Even more. Last.');
    expect(w.App.agentReview.render).not.toHaveBeenCalled();
    resolve({ ok: true, data: { response: 'Final answer.', chat_id: 'a'.repeat(32), turn_id: 'b'.repeat(32),
      turn: { id: 'b'.repeat(32), consensus: 'Final answer.', execution_mode: 'agent' }, bookmark_meta: { id: 'saved' } } });
    await pending;
    w.App.agentChat.project(run);
    // The final answer is rendered once in full, and the review appears with it.
    expect(full).toHaveBeenCalledWith(d.getElementById('agentAnswerBody'), 'Final answer.', []);
    expect(w.App.agentReview.render).toHaveBeenCalled();
    dom.window.close();
  });

  it('keeps the marked answer DOM when the run ends with the text the review already rendered', async () => {
    const { window: w, document: d, dom } = boot();
    await selectAgent(w);
    w.renderMarkdownStream = vi.fn((el, md) => { el.textContent = md; });
    w.resetMarkdownStream = vi.fn();
    const full = vi.fn((el, md) => { el.textContent = md; });
    w.injectMarkdown = full;
    w.App.agentReview = { render: vi.fn(), renderActivity: vi.fn() };
    let handlers, resolve;
    w.streamSSERequest = vi.fn((_u, _p, _s, received) => { handlers = received; return new Promise(r => { resolve = r; }); });
    d.getElementById('questionInput').value = 'Question';
    const pending = w.App.agentChat.send();
    await vi.waitFor(() => expect(handlers).toBeDefined());
    const run = w.App.runRegistry.visible();
    handlers.delta.append('Final answer.');
    w.App.agentChat.project(run);
    // The live review rendered the fixed text in full and marked it.
    const body = d.getElementById('agentAnswerBody');
    const mark = d.createElement('span'); mark.className = 'cx-claim'; body.append(mark);
    body._markSignature = 'checked';
    const serial = body._agentRenderSerial;
    full.mockClear();
    resolve({ ok: true, data: { response: 'Final answer.', chat_id: 'a'.repeat(32), turn_id: 'b'.repeat(32),
      turn: { id: 'b'.repeat(32), consensus: 'Final answer.', execution_mode: 'agent' }, bookmark_meta: { id: 'saved' } } });
    await pending;
    w.App.agentChat.project(run);
    expect(full).not.toHaveBeenCalled();
    expect(body.querySelector('.cx-claim')).toBe(mark);
    expect(body._agentRenderSerial).toBe(serial);
    expect(body.dataset.renderMode).toBe('full');
    dom.window.close();
  });

  it('lets the fixed answer shimmer while it is checked and shows its marks as soon as the check ends', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const { window: w, document: d, dom } = boot();
    await selectAgent(w);
    w.renderMarkdownStream = vi.fn((el, md) => { el.textContent = md; });
    w.resetMarkdownStream = vi.fn();
    w.injectMarkdown = vi.fn((el, md) => { el.textContent = md; });
    w.App.agentReview = { render: vi.fn(), renderActivity: vi.fn() };
    let handlers, resolve;
    w.streamSSERequest = vi.fn((_u, _p, _s, received) => { handlers = received; return new Promise(r => { resolve = r; }); });
    d.getElementById('questionInput').value = 'Question';
    const pending = w.App.agentChat.send();
    await vi.waitFor(() => expect(handlers).toBeDefined());
    const run = w.App.runRegistry.visible();
    const body = d.getElementById('agentAnswerBody');
    handlers.delta.append('Answer.');
    const version = { id: 1, text: 'Answer.', hash: 'h' };
    handlers.review.receive({ review: { status: 'running', answer_version: 1, answer_hash: 'h', versions: [version], comparisons: [{ id: 'c' }] } });
    w.App.agentChat.project(run);
    expect(body.classList.contains('is-answer-checking')).toBe(true);
    expect(w.App.agentReview.render).not.toHaveBeenCalledWith(body, expect.objectContaining({ status: 'running' }), expect.anything());
    // Checks done while a source check still runs: marks now, with the reveal.
    handlers.review.receive({ review: { status: 'succeeded', answer_version: 1, answer_hash: 'h', versions: [version], comparisons: [{ id: 'c' }] } });
    w.App.agentChat.project(run);
    expect(body.classList.contains('is-answer-checking')).toBe(false);
    expect(body.classList.contains('is-answer-check-done')).toBe(true);
    expect(w.App.agentReview.render).toHaveBeenLastCalledWith(body, expect.objectContaining({ status: 'succeeded' }),
      expect.objectContaining({ reveal: true }));
    vi.advanceTimersByTime(500);
    expect(body.classList.contains('is-answer-check-done')).toBe(false);
    resolve({ ok: true, data: { response: 'Answer.', chat_id: 'a'.repeat(32), turn_id: 'b'.repeat(32),
      turn: { id: 'b'.repeat(32), consensus: 'Answer.', execution_mode: 'agent' }, bookmark_meta: { id: 'saved' } } });
    await pending;
    vi.useRealTimers();
    dom.window.close();
  });

  it('restores the draft without a recovery or failed row when the server refuses before starting', async () => {
    const { window: w, document: d, dom } = boot();
    await selectAgent(w);
    w.streamSSERequest = vi.fn(async () => ({ ok: false, status: 422, streamed: false,
      data: { detail: 'This chat contains Google information. Allow sharing it for this message.' } }));
    d.body.insertAdjacentHTML('beforeend', '<div id="bookmarksContainer"></div>');
    d.getElementById('questionInput').value = 'Follow-up with Google data';
    w.App.trackAsk = vi.fn();
    w.App.trackAnswer = vi.fn();
    await w.App.agentChat.send();
    const run = w.App.runRegistry.visible();
    w.App.agentChat.project(run); w.App.agentChat.render();
    // Analytics: the sent "ask" ends as a failed "answer", like a refused pipeline run.
    expect(w.App.trackAsk).toHaveBeenCalledTimes(1);
    expect(w.App.trackAnswer).toHaveBeenCalledWith(run, 'failed');
    expect(d.getElementById('questionInput').value).toBe('Follow-up with Google data');
    expect(run.metadata.requestSent).toBe(false);
    expect(run.metadata.recoverable).toBe(false);
    expect(d.getElementById('agentRecover').hidden).toBe(true);
    expect(d.getElementById('agentAnswerError').textContent).toContain('Message not sent.');
    expect(d.querySelector('.bookmark.run-entry')).toBeNull();
    dom.window.close();
  });

  it('explains a token reservation refusal in plain words with next steps', async () => {
    const { window: w, document: d, dom } = boot();
    d.body.insertAdjacentHTML('beforeend', '<div id="agentAnswerErrorActions" hidden></div>');
    await selectAgent(w);
    w.streamSSERequest = vi.fn(async (_u, _p, _s, handlers) => {
      handlers.accepted?.receive({ chat_id: 'a'.repeat(32), turn_id: 'b'.repeat(32) });
      return { ok: false, status: 200, streamed: true, data: { error: 'The next model call needed a reservation of 18,400 tokens; 1,200 were available at that point.',
        code: 'agent_token_reservation', required_tokens: 18400, available_tokens: 1200, recoverable: false } };
    });
    d.getElementById('questionInput').value = 'Long question';
    await w.App.agentChat.send();
    w.App.agentChat.project(w.App.runRegistry.visible());
    const error = d.getElementById('agentAnswerError').textContent;
    expect(error).toContain('Not enough Agent tokens left for this step (needs about 18k, 1.2k left)');
    expect(error).not.toContain('reservation');
    expect([...d.querySelectorAll('#agentAnswerErrorActions button')].map(b => b.textContent)).toEqual(['Try a smaller model', 'Choose models']);
    expect(d.getElementById('questionInput').value).toBe('Long question');
    w.App.openModelPicker = vi.fn();
    d.querySelector('#agentAnswerErrorActions button[data-action="compare"]').click();
    expect(w.App.openModelPicker).toHaveBeenCalledWith(d.getElementById('consensusModelDropdown'));
    dom.window.close();
  });

  it('blocks Send with the Google blocker and runs its action', async () => {
    const { window: w, document: d, dom } = boot();
    d.body.insertAdjacentHTML('beforeend', '<div id="agentComposerNotice" hidden><span id="agentComposerMessage"></span><button id="agentComposerAction" hidden></button></div>');
    const consent = vi.fn();
    w.App.agentGoogle = { blocker: () => ({ message: 'Allow sharing the selected Google data with your models for this message.', action: 'google-consent', label: 'Allow for this message' }),
      consent, open: vi.fn(), selection: () => null, resetConsent: vi.fn() };
    // DOMContentLoaded already bound the notice button before it existed; bind again.
    d.dispatchEvent(new w.Event('DOMContentLoaded'));
    await selectAgent(w);
    expect(w.App.agentChat.sendBlocker().action).toBe('google-consent');
    w.App.agentChat.syncComposer();
    expect(d.getElementById('agentComposerNotice').hidden).toBe(false);
    d.getElementById('agentComposerAction').click();
    expect(consent).toHaveBeenCalledWith(true);
    w.App.agentGoogle.blocker = () => { throw new Error('broken'); };
    expect(w.App.agentChat.sendBlocker()).toBeNull();
    dom.window.close();
  });

  it('shows a pending-review notice, bookmark dot and tab count after a run', async () => {
    const { window: w, document: d, dom } = boot();
    d.body.insertAdjacentHTML('beforeend', `<div id="agentReviewNotice" hidden><span id="agentReviewMessage"></span><button id="agentReviewAction">Review</button></div>
      <div class="bookmark" data-id="b_saved"><p>Saved</p></div>`);
    let pending = 2;
    w.App.agentGoogle = { pendingCount: vi.fn(() => pending), selection: () => null, resetConsent: vi.fn() };
    await selectAgent(w);
    w.App.runRegistry.showSavedView({ type: 'bookmark', id: 'b_saved' }, { chatId: 'a'.repeat(32), turnId: 'b'.repeat(32), bookmarkId: 'b_saved',
      executionMode: 'agent', question: 'Q', consensus: 'A', currentTurn: { id: 'b'.repeat(32), status: 'completed' } });
    w.App.agentChat.syncPendingReview();
    expect(d.getElementById('agentReviewNotice').hidden).toBe(false);
    expect(d.getElementById('agentReviewMessage').textContent).toBe('2 items need your review');
    expect(d.querySelector('.bookmark[data-id="b_saved"]').classList.contains('needs-review')).toBe(true);
    expect(d.title).toMatch(/^\(2\) /);
    pending = 0;
    w.dispatchEvent(new w.CustomEvent('consensio:agent-actions-change'));
    expect(d.getElementById('agentReviewNotice').hidden).toBe(true);
    expect(d.querySelector('.bookmark.needs-review')).toBeNull();
    expect(d.title).not.toMatch(/^\(\d+\) /);
    dom.window.close();
  });
});

// Agent shows ONE chip for the chat model and the models it is compared with
// (model-picker.js, linked pickers). The comparison select keeps its rules
// and persistence; it only draws into the Agent menu while Agent is on.
const LINKED_BODY = BODY + `<div class="consensus-model consensus-model-inline"><div class="select-wrapper">
  <select id="consensusModelDropdown" aria-label="Models and consensus engine"><option value="engine">Engine</option></select></div></div>
  <input id="compareGemini" type="checkbox"><select id="compareGeminiModel"><option value="gemini-flash">Gemini Flash</option></select>`;

function bootLinked({ initComparison = true, ...options } = {}) {
  const harness = boot({ ...options, body: LINKED_BODY, setup(window) {
    window.App.modelPrefs = [
      { key: 'OpenAI', label: 'ChatGPT', provider: 'openai', checkId: 'compareOpenAI', selectId: 'compareOpenAIModel', responseId: 'openaiResponse' },
      { key: 'Anthropic', label: 'Claude', provider: 'anthropic', checkId: 'compareClaude', selectId: 'compareClaudeModel', responseId: 'claudeResponse' },
      { key: 'Gemini', label: 'Gemini', provider: 'gemini', checkId: 'compareGemini', selectId: 'compareGeminiModel', responseId: 'geminiResponse' }];
    window.App.getSelectedModelCount = () => window.App.modelPrefs.filter(pref => window.document.getElementById(pref.checkId).checked).length;
    window.App.trackAppEvent = vi.fn();
    window.updateAgentModeUI = vi.fn();
    window.CONSENSUS_PRESETS = [{ id: 'daily', label: 'Daily', hint: 'Quick answers', consensus_model: 'engine',
      models: { openai: 'gpt-5.4-mini', anthropic: 'claude-haiku-4-5' } }];
    window.DEFAULT_CONSENSUS_PRESET = 'daily';
  } });
  if (initComparison) harness.window.App.initCustomModelPicker(harness.document.getElementById('consensusModelDropdown'), { presets: true });
  return harness;
}

describe('one Agent chip for the chat model and its comparison models', () => {
  const key = (w, el, name) => el.dispatchEvent(new w.KeyboardEvent('keydown', { key: name, bubbles: true }));

  it('carries both choices in one menu and gives the comparison chip back outside Agent', async () => {
    const { window: w, document: d, dom } = bootLinked();
    await selectAgent(w);
    const consensus = d.getElementById('consensusModelDropdown');
    const trigger = d.querySelector('.agent-model-picker .model-picker-display');
    const menu = d.querySelector('.agent-model-picker .model-picker-menu');
    expect(d.querySelector('.consensus-model').hidden).toBe(true);
    expect(trigger.querySelector('.model-picker-display-text').textContent).toBe('DeepSeek V4.1 Flash');
    expect(trigger.querySelector('.model-picker-display-count').textContent).toBe('+2');
    expect(trigger.getAttribute('aria-label')).toBe('Agent and comparison models: DeepSeek V4.1 Flash, compared with 2 models');
    expect(trigger.textContent).not.toMatch(/Agent|Compare/);

    trigger.click();
    expect([...menu.querySelectorAll('.model-picker-section-label')].map(el => el.textContent)).toEqual(['Agent', 'Compare with']);
    expect([...menu.querySelectorAll('[data-picker-level]')].map(el => el.dataset.pickerLevel)).toEqual(['models', 'secondary', 'companion']);
    expect(menu.querySelector('[data-picker-level="models"]').textContent).toContain('DeepSeek V4.1 Flash');
    expect(menu.querySelector('[data-picker-level="companion"]').textContent).toContain('2 models · Daily');
    expect(menu.getAttribute('aria-label')).toBe('Agent and comparison models');

    // Right enters a section's level, Left returns to the overview.
    const compare = menu.querySelector('[data-picker-level="companion"]');
    compare.focus();
    key(w, compare, 'ArrowRight');
    expect(menu.querySelector('[data-preset="daily"]')).not.toBeNull();
    expect(menu.querySelector('.model-picker-back-option').textContent).toBe('Compare with');
    expect(menu.contains(d.activeElement)).toBe(true);
    key(w, d.activeElement, 'ArrowLeft');
    expect(menu.querySelector('[data-picker-level="companion"]')).not.toBeNull();
    expect(menu.contains(d.activeElement)).toBe(true);

    // Custom: the comparison rows, no consensus engine. A toggle keeps focus
    // on its row and the chip counts along.
    menu.querySelector('[data-picker-level="companion"]').click();
    menu.querySelector('.model-picker-custom-option').click();
    expect(menu.textContent).toContain('Comparison models');
    expect(menu.textContent).not.toContain('Consensus engine');
    const gemini = menu.querySelector('[data-focus-key="toggle:Gemini"]');
    gemini.focus();
    gemini.click();
    expect(d.getElementById('compareGemini').checked).toBe(true);
    expect(d.activeElement.dataset.focusKey).toBe('toggle:Gemini');
    expect(trigger.querySelector('.model-picker-display-count').textContent).toBe('+3');
    expect(w.localStorage.getItem('pref_consensus_preset')).toBe('custom');

    // Escape closes the one menu and returns to the one chip.
    key(w, d.activeElement, 'Escape');
    expect(menu.classList.contains('is-open')).toBe(false);
    expect(d.activeElement).toBe(trigger);

    // Outside Agent the comparison chip is its own picker again.
    w.App.runMode.set('consensus');
    expect(d.querySelector('.consensus-model').hidden).toBe(false);
    w.App.openModelPicker(consensus);
    const own = d.querySelector('.consensus-model .model-picker-menu');
    expect(own.classList.contains('is-open')).toBe(true);
    expect(own.querySelector('[data-focus-key="toggle:Gemini"]')).not.toBeNull();
    expect(menu.classList.contains('is-open')).toBe(false);
    dom.window.close();
  });

  it('opens the named level from shortcuts and keeps the comparisons open while the chat model is locked', async () => {
    const { window: w, document: d, dom } = bootLinked();
    await selectAgent(w);
    const agentSelect = d.getElementById('agentModelDropdown');
    const consensus = d.getElementById('consensusModelDropdown');
    const trigger = d.querySelector('.agent-model-picker .model-picker-display');
    const menu = d.querySelector('.agent-model-picker .model-picker-menu');

    // (+) "Comparison models" and the composer notice open the comparison level.
    w.App.openModelPicker(consensus);
    expect(menu.classList.contains('is-open')).toBe(true);
    expect(menu.querySelector('[data-preset="daily"]')).not.toBeNull();
    expect(d.querySelector('.consensus-model .model-picker-menu').classList.contains('is-open')).toBe(false);
    expect(menu.contains(d.activeElement)).toBe(true);
    // Choosing a preset closes the one menu, not a hidden one.
    menu.querySelector('[data-preset="daily"]').click();
    expect(menu.classList.contains('is-open')).toBe(false);
    expect(trigger.getAttribute('aria-expanded')).toBe('false');

    // (+) "Reasoning" opens the effort picker; its way back is the overview.
    w.App.openModelPicker(agentSelect, { secondary: true });
    expect(menu.querySelector('[data-setting-value="high"]')).not.toBeNull();
    menu.querySelector('.model-picker-back-option').click();
    expect(menu.querySelector('[data-picker-level="secondary"]')).not.toBeNull();
    expect(menu.querySelector('.agent-reasoning-option')).toBeNull();

    // A running message locks the chat model, not the comparison models.
    agentSelect.disabled = true;
    w.syncCustomModelPickers();
    expect(trigger.disabled).toBe(false);
    w.App.collapseExpandedModelPicker(agentSelect, { ownLevelsOnly: true });
    expect(menu.classList.contains('is-open')).toBe(true);
    expect(menu.querySelector('[data-picker-level="models"]').disabled).toBe(true);
    expect(menu.querySelector('[data-picker-level="companion"]').disabled).toBe(false);
    dom.window.close();
  });

  it('links once the comparison picker exists, whichever picker comes first', async () => {
    const { window: w, document: d, dom } = bootLinked({ initComparison: false });
    await selectAgent(w);
    const trigger = d.querySelector('.agent-model-picker .model-picker-display');
    expect(trigger.querySelector('.model-picker-display-count')).toBeNull();
    w.App.initCustomModelPicker(d.getElementById('consensusModelDropdown'), { presets: true });
    expect(trigger.querySelector('.model-picker-display-count').textContent).toBe('+2');
    trigger.click();
    expect(d.querySelector('.agent-model-picker [data-picker-level="companion"]')).not.toBeNull();
    // Unlinking a link that never applied is a no-op, not an error.
    w.App.linkModelPicker(d.getElementById('agentModelDropdown'), null);
    expect(trigger.querySelector('.model-picker-display-count').hidden).toBe(true);
    dom.window.close();
  });
});
