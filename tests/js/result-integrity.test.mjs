import { describe, it, expect, vi } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

// Review R06 (typed completion state) and R09 (answers only via server receipts).

function boot({ final, onPayload } = {}) {
  const user = { uid: 'owner', getIdToken: async () => 'token' };
  const app = loadScripts(['static/js/run-registry.js', 'static/js/consensus-run.js'], {
    before(window) {
      window.auth = { currentUser: user };
      window.App = {
        authState: { generation: 1, snapshot: () => ({ uid: user.uid, generation: 1 }) },
        trackAppEvent: vi.fn(), reportCriticalError: vi.fn(),
        modelPrefs: [{ key: 'OpenAI' }, { key: 'Gemini' }, { key: 'Grok' }]
      };
      window.streamSSERequest = vi.fn(async (url, payload, _signal, handlers) => {
        onPayload?.(url, payload);
        handlers['consensus.delta'].append('Partial synthesis');
        return { ok: true, status: 200, streamed: true, data: final || {
          consensus_response: 'Consensus', consensus_completion: 'complete', differences: '', result_id: 'r1'
        } };
      });
      window.recordModelVote = vi.fn();
      window.saveBookmarkConsensus = vi.fn(async () => ({}));
    }
  });
  const registry = app.window.App.runRegistry;
  const context = registry.create({ question: 'Question', config: {
    providers: [{ provider: 'OpenAI' }, { provider: 'Gemini' }, { provider: 'Grok' }]
  } });
  context.modelResults = {
    OpenAI: { status: 'complete', text: 'One', receipt: 'a'.repeat(40) },
    Gemini: { status: 'complete', text: 'Two', receipt: 'b'.repeat(40) },
    Grok: { status: 'incomplete', completion: 'token_limit', text: 'Cut', receipt: 'c'.repeat(40) }
  };
  registry.setStatus(context.runId, 'running');
  return { ...app, registry, context };
}

describe('consensus result integrity', () => {
  it('sends only receipts of complete answers, never answer text or sources', async () => {
    let sent = null;
    const { window, dom, context } = boot({ onPayload: (_url, payload) => { sent = payload; } });
    await window.App.executeConsensusRun(context);
    expect(sent.answer_receipts).toEqual({ OpenAI: 'a'.repeat(40), Gemini: 'b'.repeat(40) });
    expect(sent.run_id).toBe(context.runId);
    expect(sent).not.toHaveProperty('answers');
    expect(sent).not.toHaveProperty('model_sources');
    expect(context.status).toBe('succeeded');
    dom.window.close();
  });

  it('keeps a truncated synthesis visible but marks it incomplete and failed', async () => {
    const { window, dom, context } = boot({ final: {
      consensus_response: '', consensus_completion: 'token_limit', error_code: 'consensus_incomplete',
      error: 'The consensus stopped at the output limit and is incomplete.'
    } });
    await window.App.executeConsensusRun(context);
    expect(context.status).toBe('failed');
    expect(context.consensus.status).toBe('error');
    expect(context.consensus.completion).toBe('token_limit');
    expect(context.consensus.error).toEqual(expect.objectContaining({ incomplete: true }));
    expect(context.consensus.text).toBe('Partial synthesis');
    expect(window.recordModelVote).not.toHaveBeenCalled();
    expect(window.saveBookmarkConsensus).not.toHaveBeenCalled();
    dom.window.close();
  });
});
