import { describe, it, expect, vi } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

function boot(kind = 'stream_read_failed') {
  const user = { uid: 'owner', getIdToken: async () => 'token' };
  const error = Object.assign(new TypeError('connection lost'), { streamFailureKind: kind });
  const app = loadScripts(['static/js/run-registry.js', 'static/js/consensus-run.js'], {
    before(window) {
      window.auth = { currentUser: user };
      window.App = {
        authState: { generation: 1, snapshot: () => ({ uid: user.uid, generation: 1 }) }, trackAppEvent: vi.fn(), reportCriticalError: vi.fn(),
        modelPrefs: [{ key: 'OpenAI' }, { key: 'Gemini' }]
      };
      window.streamSSERequest = vi.fn(async (_url, _payload, _signal, handlers) => {
        handlers['consensus.delta'].append('Partial answer');
        throw error;
      });
      window.fetch = vi.fn(async () => ({ ok: true, status: 200, json: async () => ({ turn: {
        status: 'completed', consensus: 'Stored answer', differences: 'Stored differences',
        differences_data: { best_model: 'OpenAI' }, sources: [], result_id: 'stored-result'
      } }) }));
      window.recordModelVote = vi.fn();
      window.saveBookmarkConsensus = vi.fn();
    }
  });
  const registry = app.window.App.runRegistry;
  const context = registry.create({ question: 'Question', config: {
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
  it('recovers a committed turn through GET without another generation, vote or save', async () => {
    const { window, dom, context } = boot();
    await window.App.executeConsensusRun(context);
    expect(context.status, context.consensus.error?.message).toBe('succeeded');
    expect(context.consensus.text).toBe('Stored answer');
    expect(context.consensus.resultId).toBe('stored-result');
    expect(context.chatSession.handleConsensusResult).toHaveBeenCalledWith(expect.objectContaining({ chatTurnState: 'completed' }));
    expect(window.streamSSERequest).toHaveBeenCalledOnce();
    expect(window.fetch).toHaveBeenCalledWith(`/chats/${'a'.repeat(32)}/turns/${'b'.repeat(32)}`, expect.objectContaining({ cache: 'no-store', headers: { Authorization: 'Bearer token' } }));
    expect(window.recordModelVote).not.toHaveBeenCalled();
    expect(window.saveBookmarkConsensus).not.toHaveBeenCalled();
    expect(window.App.reportCriticalError).not.toHaveBeenCalled();
    dom.window.close();
  });

  it('keeps partial text and the conversation fence when the stored turn failed', async () => {
    const { window, dom, context } = boot();
    window.fetch.mockResolvedValue({ ok: true, json: async () => ({ turn: { status: 'failed' } }) });
    await window.App.executeConsensusRun(context);
    expect(context.status).toBe('failed');
    expect(context.consensus.text).toBe('Partial answer');
    expect(context.keepConversationLock).toBe(true);
    expect(window.App.reportCriticalError).toHaveBeenCalledWith(expect.objectContaining({ failure_kind: 'stream_read_failed' }));
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
    const { window, dom, context } = boot('stream_incomplete');
    window.fetch.mockResolvedValue({ ok: true, json: async () => ({ turn: { status: 'pending', consensus: 'Unconfirmed' } }) });
    await window.App.executeConsensusRun(context);
    expect(window.fetch).toHaveBeenCalledTimes(3);
    expect(window.streamSSERequest).toHaveBeenCalledOnce();
    expect(context.status).toBe('failed');
    expect(context.consensus.text).toBe('Partial answer');
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
