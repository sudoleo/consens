import { describe, it, expect, vi } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

function boot(kind = 'stream_read_failed', { followup = false } = {}) {
  const user = { uid: 'owner', getIdToken: async () => 'token' };
  const error = Object.assign(new TypeError('connection lost'), { streamFailureKind: kind });
  const app = loadScripts(['static/js/usage-limit.js', 'static/js/run-registry.js', 'static/js/chat-session.js', 'static/js/consensus-run.js'], {
    before(window) {
      window.auth = { currentUser: user };
      window.App = {
        authState: { generation: 1, snapshot: () => ({ uid: user.uid, generation: 1 }) }, trackAppEvent: vi.fn(), trackAnswer: vi.fn(), reportCriticalError: vi.fn(),
        modelPrefs: [{ key: 'OpenAI' }, { key: 'Gemini' }]
      };
      window.streamSSERequest = vi.fn(async (_url, _payload, _signal, handlers) => {
        handlers['consensus.delta'].append('Partial answer');
        throw error;
      });
      window.fetch = vi.fn(async () => ({ ok: true, status: 200, json: async () => ({ turn: {
        status: 'completed', consensus: 'Stored answer', differences: 'Stored differences',
        differences_data: { best_model: 'OpenAI' }, sources: [], result_id: 'stored-result',
        model_answers: { OpenAI: { answer: 'Stored one', model_label: 'GPT stored', sources: [] } }
      } }) }));
      window.recordModelVote = vi.fn();
      window.saveBookmarkConsensus = vi.fn();
    }
  });
  const registry = app.window.App.runRegistry;
  const context = registry.create({ question: 'Question', followup,
    basis: followup ? { chatId: 'a'.repeat(32), turnId: 'c'.repeat(32), question: 'Earlier', consensus: 'Completed predecessor' } : null,
    config: {
    providers: [{ provider: 'OpenAI' }, { provider: 'Gemini' }]
  }, chatSession: {
    pendingTurnId: 'b'.repeat(32),
    ensurePendingTurn: async () => ({ chatId: 'a'.repeat(32), turnId: 'b'.repeat(32) }),
    handleConsensusResult: vi.fn(), markPendingUncertain: vi.fn()
  } });
  context.modelResults = { OpenAI: { status: 'complete', text: 'One' }, Gemini: { status: 'complete', text: 'Two' } };
  registry.setStatus(context.runId, 'running');
  return { ...app, registry, context };
}

describe('consensus transport recovery', () => {
  it.each([true, false])('shows the shared budget rejection only for the visible run (visible=%s)', async visible => {
    const { window, dom, context, registry } = boot();
    const show = vi.spyOn(window.App.usageLimit, 'show').mockImplementation(() => {});
    window.streamSSERequest.mockResolvedValue({ ok: false, status: 403, data: {
      detail: { error_code: 'token_budget_exhausted', error: 'No tokens remain' },
    } });
    if (!visible) registry.clearVisible();
    await window.App.executeConsensusRun(context);
    expect(context.status).toBe('failed');
    expect(show).toHaveBeenCalledTimes(visible ? 1 : 0);
    if (visible) expect(show).toHaveBeenCalledWith(expect.objectContaining({ data: expect.objectContaining({ error_code: 'token_budget_exhausted' }) }));
    dom.window.close();
  });
  it('recovers a committed turn through GET without another generation, vote or save', async () => {
    const { window, dom, context } = boot();
    await window.App.executeConsensusRun(context);
    expect(context.status, context.consensus.error?.message).toBe('succeeded');
    expect(context.consensus.text).toBe('Stored answer');
    expect(context.consensus.resultId).toBe('stored-result');
    // The stored turn is authoritative for the model answers as well.
    expect(context.modelResults.OpenAI).toMatchObject({ text: 'Stored one', status: 'complete', modelLabel: 'GPT stored' });
    expect(context.modelResults.Gemini).toMatchObject({ text: '', status: 'skipped' });
    expect(context.chatSession.handleConsensusResult).toHaveBeenCalledWith(expect.objectContaining({ chatTurnState: 'completed' }));
    expect(window.streamSSERequest).toHaveBeenCalledOnce();
    expect(window.fetch).toHaveBeenCalledWith(`/chats/${'a'.repeat(32)}/turns/${'b'.repeat(32)}`, expect.objectContaining({ cache: 'no-store', headers: { Authorization: 'Bearer token' } }));
    expect(window.recordModelVote).not.toHaveBeenCalled();
    expect(window.saveBookmarkConsensus).not.toHaveBeenCalled();
    expect(window.App.reportCriticalError).not.toHaveBeenCalled();
    expect(window.App.trackAppEvent).not.toHaveBeenCalledWith('app_consensus_completed', expect.anything());
    // The run's "ask" went out, so its recovered answer still counts once.
    expect(window.App.trackAnswer).toHaveBeenCalledWith(context, 'ok');
    dom.window.close();
  });

  it('keeps partial text but releases the conversation fence after an authoritative failed turn', async () => {
    const { window, dom, context, registry } = boot('stream_read_failed', { followup: true });
    const session = window.App.createChatSession({ activeChatId: 'a'.repeat(32), activeTurnId: 'c'.repeat(32) });
    session.pendingChatId = 'a'.repeat(32);
    session.pendingTurnId = 'b'.repeat(32);
    session.pendingClientRequestId = 'same-request';
    session.pendingUsageRunKey = 'same-usage';
    vi.spyOn(session, 'ensurePendingTurn').mockResolvedValue({ chatId: session.pendingChatId, turnId: session.pendingTurnId });
    vi.spyOn(session, 'handleConsensusResult');
    vi.spyOn(session, 'markPendingUncertain');
    context.chatSession = session;
    window.fetch.mockResolvedValue({ ok: true, status: 200, json: async () => ({ turn: { status: 'failed' } }) });
    await window.App.executeConsensusRun(context);
    expect(context.status).toBe('failed');
    expect(context.consensus.text).toBe('Partial answer');
    expect(context.keepConversationLock).toBe(false);
    expect(context.chatTurnState).toBe('failed');
    expect(context.consensus.error).toMatchObject({ incomplete: true });
    expect(session.handleConsensusResult).toHaveBeenCalledWith({ chatId: 'a'.repeat(32), turnId: 'b'.repeat(32), chatPersisted: false, chatTurnState: 'failed' });
    expect(session.pendingTurnId).toBeNull();
    expect(session.pendingClientRequestId).toBeNull();
    expect(session.pendingUsageRunKey).toBeNull();
    expect(session.activeTurnId).toBe('c'.repeat(32));
    expect(session.hasUncertainTurn()).toBe(false);
    expect(session.markPendingUncertain).not.toHaveBeenCalled();
    expect(window.streamSSERequest).toHaveBeenCalledOnce();
    expect(window.fetch).toHaveBeenCalledOnce();
    expect(window.saveBookmarkConsensus).not.toHaveBeenCalled();
    expect(window.recordModelVote).not.toHaveBeenCalled();
    expect(window.App.reportCriticalError).not.toHaveBeenCalled();
    expect(() => registry.create({ followup: true, basis: context.basis })).not.toThrow();
    dom.window.close();
  });

  it('does not hide rendering defects with transport recovery', async () => {
    const { window, dom, context } = boot('stream_handler_failed');
    await window.App.executeConsensusRun(context);
    expect(context.status).toBe('failed');
    expect(window.fetch).not.toHaveBeenCalled();
    dom.window.close();
  });

  it('bounds pending-turn polling and never treats a partial stream as complete', async () => {
    const { window, dom, context, registry } = boot('stream_incomplete', { followup: true });
    window.fetch.mockResolvedValue({ ok: true, json: async () => ({ turn: { status: 'pending', consensus: 'Unconfirmed' } }) });
    await window.App.executeConsensusRun(context);
    expect(window.fetch).toHaveBeenCalledTimes(3);
    expect(window.streamSSERequest).toHaveBeenCalledOnce();
    expect(context.status).toBe('failed');
    expect(context.consensus.text).toBe('Partial answer');
    expect(context.keepConversationLock).toBe(true);
    expect(context.chatSession.handleConsensusResult).not.toHaveBeenCalled();
    expect(() => registry.create({ followup: true, basis: context.basis })).toThrow(/final server status/);
    dom.window.close();
  });

  it.each([403, 'offline'])('retains the fence when recovery cannot establish ownership or disposition (%s)', async outcome => {
    const { window, dom, context, registry } = boot('stream_read_failed', { followup: true });
    if (outcome === 'offline') window.fetch.mockRejectedValue(new TypeError('Recovery unavailable'));
    else window.fetch.mockResolvedValue({ ok: false, status: outcome,
      json: async () => ({ turn: { status: 'failed' } }) });
    await window.App.executeConsensusRun(context);
    expect(context.status).toBe('failed');
    expect(context.consensus.text).toBe('Partial answer');
    expect(context.keepConversationLock).toBe(true);
    expect(context.chatSession.pendingTurnId).toBe('b'.repeat(32));
    expect(context.chatSession.handleConsensusResult).not.toHaveBeenCalled();
    expect(context.chatSession.markPendingUncertain).toHaveBeenCalledOnce();
    expect(window.fetch).toHaveBeenCalledTimes(outcome === 'offline' ? 3 : 1);
    expect(window.streamSSERequest).toHaveBeenCalledOnce();
    expect(window.saveBookmarkConsensus).not.toHaveBeenCalled();
    expect(() => registry.create({ followup: true, basis: context.basis })).toThrow(/final server status/);
    dom.window.close();
  });

  it('does not poll when the user cancels', async () => {
    const { window, dom, context } = boot();
    window.streamSSERequest.mockImplementation(async () => {
      window.App.runRegistry.cancel(context.runId);
      throw Object.assign(new Error('cancelled'), { name: 'AbortError', streamFailureKind: 'stream_read_failed' });
    });
    await window.App.executeConsensusRun(context);
    expect(window.fetch).not.toHaveBeenCalled();
    expect(window.App.reportCriticalError).not.toHaveBeenCalled();
    dom.window.close();
  });

  it('discards a recovery response after logout', async () => {
    const { window, dom, context, registry } = boot();
    window.fetch.mockImplementation(async () => {
      registry.clearAll('logout');
      window.auth.currentUser = null;
      return { ok: true, json: async () => ({ turn: { status: 'completed', consensus: 'Private answer' } }) };
    });
    await window.App.executeConsensusRun(context);
    expect(context.consensus.text).not.toBe('Private answer');
    expect(context.chatSession.handleConsensusResult).not.toHaveBeenCalled();
    expect(window.saveBookmarkConsensus).not.toHaveBeenCalled();
    dom.window.close();
  });
});
