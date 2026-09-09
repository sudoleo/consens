import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { loadScripts } from './helpers/appWindow.mjs';

const response = value => ({ok: true, json: async () => value});
const snapshot = (status, extra = {}) => ({job_id: 'job-1', schema_version: 3, answer_version: 'answer-1',
  revision: 2, status, findings: [], documents: [], sources: [], ...extra});
function boot() {
  const env = loadScripts(['static/js/source-verification.js']);
  env.window.setTimeout = (fn, ms) => setTimeout(fn, ms);
  env.window.clearTimeout = id => clearTimeout(id);
  env.window.fetch = vi.fn();
  return env;
}
function mountReport(document) {
  document.body.innerHTML = '<div id="consensusAnswerBody">The price is 20 euros.</div><div id="sourceVerificationReport"></div>'
    + '<button id="consensusSourcesTab"><span class="consensus-tab-label">Sources</span><span id="consensusSourceCheckStatus"></span></button>';
}
beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe('bound source check watcher', () => {
  it.each([403, 404])('explains a terminal %s refresh failure without changing the saved verdict', async status => {
    const {window, document} = boot(); mountReport(document);
    const queued = snapshot('queued');
    window.App.sourceVerification.renderCurrent(queued);
    window.fetch.mockResolvedValue({ok: false, status});
    const onUpdate = vi.fn();
    window.App.sourceVerification.watch({jobId: 'job-1', onUpdate, isActive: () => true});
    await vi.advanceTimersByTimeAsync(0);
    expect(document.querySelector('.source-check-refresh-notice').textContent).toContain('last received results');
    expect(document.getElementById('consensusSourceCheckStatus').textContent).toBe(' · Updates unavailable');
    expect(document.querySelector('.source-check-loading')).toBeNull();
    expect(document.querySelector('.source-check-refresh-stopped')).not.toBeNull();
    expect(document.getElementById('sourceVerificationReport').hasAttribute('aria-busy')).toBe(false);
    expect(queued.status).toBe('queued'); expect(onUpdate).not.toHaveBeenCalled();
    window.App.sourceVerification.renderCurrent(queued);
    expect(document.querySelector('.source-check-refresh-notice')).not.toBeNull();
    await vi.advanceTimersByTimeAsync(60000);
    expect(window.fetch).toHaveBeenCalledOnce();
  });
  it('keeps results during transient failures, explains the third failure and clears its notice on recovery', async () => {
    const {window, document} = boot(); mountReport(document);
    const checked = snapshot('running', {scope: {pairs: 2, checked_pairs: 1}, findings: [{sentence_id: 1,
      source_id: 'S1', claim: 'The price is 20 euros.', checked: true, support: 'supported', topical: 'relevant', temporal: 'suitable'}]});
    window.fetch.mockResolvedValueOnce(response({source_verification: checked}))
      .mockResolvedValueOnce({ok: false, status: 503}).mockResolvedValueOnce({ok: false, status: 503})
      .mockResolvedValueOnce({ok: false, status: 503}).mockResolvedValue(response({source_verification: checked, unchanged: true}));
    const onUpdate = vi.fn(value => window.App.sourceVerification.renderCurrent(value));
    const stop = window.App.sourceVerification.watch({jobId: 'job-1', onUpdate, isActive: () => true});
    await vi.advanceTimersByTimeAsync(0);
    const row = document.querySelector('.source-check-row');
    await vi.advanceTimersByTimeAsync(4500);
    expect(document.querySelector('.source-check-refresh-notice')).toBeNull();
    await vi.advanceTimersByTimeAsync(6000);
    expect(document.querySelector('.source-check-refresh-notice').textContent).toContain('Retrying automatically');
    expect(document.querySelector('.source-check-row')).toBe(row);
    expect(document.body.textContent).toContain('Statement supported');
    expect(checked.findings[0].support).toBe('supported');
    await vi.advanceTimersByTimeAsync(12000);
    expect(document.querySelector('.source-check-refresh-notice')).toBeNull();
    expect(document.querySelector('.source-check-row')).toBe(row);
    expect(onUpdate).toHaveBeenCalledOnce();
    stop();
  });
  it('hydrates completed stubs and stops a private observer as soon as auth changes', async () => {
    const {window} = boot(); const onUpdate = vi.fn();
    const user = {uid: 'owner', getIdToken: async () => 'token'};
    window.auth = {currentUser: user}; window.App.authState = {generation: 2};
    let resolve;
    window.fetch.mockReturnValue(new Promise(done => {resolve = done;}));
    window.App.sourceVerification.observe({snapshot: snapshot('complete'), auth: {user, uid: user.uid, generation: 2},
      isActive: () => true, onUpdate});
    await vi.advanceTimersByTimeAsync(0);
    expect(window.fetch).toHaveBeenCalledOnce();
    const signal = window.fetch.mock.calls[0][1].signal;
    window.auth.currentUser = null;
    window.dispatchEvent(new window.CustomEvent('consensio:auth-state'));
    expect(signal.aborted).toBe(true);
    resolve(response({source_verification: snapshot('complete')}));
    await vi.advanceTimersByTimeAsync(0);
    expect(onUpdate).not.toHaveBeenCalled();
  });
  it('resumes an original own-key job once without adding the key to its snapshots', async () => {
    const {window} = boot(); const onUpdate = vi.fn();
    const user = {uid: 'owner', getIdToken: async () => 'token'};
    window.auth = {currentUser: user};
    const awaiting = snapshot('awaiting_credentials', {credential_mode: 'own'});
    window.fetch.mockResolvedValueOnce(response({source_verification: awaiting}))
      .mockResolvedValueOnce({ok: true})
      .mockResolvedValueOnce(response({source_verification: awaiting}));
    window.App.sourceVerification.observe({snapshot: awaiting, auth: {user, uid: user.uid},
      getOwnKey: () => 'own-secret', isActive: () => true, onUpdate});
    await vi.advanceTimersByTimeAsync(0);
    await vi.advanceTimersByTimeAsync(10);
    expect(window.fetch).toHaveBeenCalledTimes(3);
    expect(window.fetch.mock.calls[1][0]).toBe('/api/source-checks/job-1/resume');
    expect(JSON.parse(window.fetch.mock.calls[1][1].body)).toEqual({openrouter_key: 'own-secret'});
    expect(JSON.stringify(onUpdate.mock.calls)).not.toContain('own-secret');
    await vi.advanceTimersByTimeAsync(60000);
    expect(window.fetch).toHaveBeenCalledTimes(3);
  });
  it('does not automatically supply an own key to a server-key job', async () => {
    const {window} = boot();
    const user = {uid: 'owner', getIdToken: async () => 'token'};
    window.auth = {currentUser: user};
    window.fetch.mockResolvedValue(response({source_verification: snapshot('awaiting_credentials', {credential_mode: 'server'})}));
    const getOwnKey = vi.fn(() => 'own-secret');
    window.App.sourceVerification.observe({snapshot: snapshot('queued'), auth: {user, uid: user.uid},
      getOwnKey, isActive: () => true, onUpdate: vi.fn()});
    await vi.advanceTimersByTimeAsync(0);
    expect(window.fetch).toHaveBeenCalledOnce();
    expect(getOwnKey).not.toHaveBeenCalled();
  });
  it('loads every page before publishing and includes auth and stable revision', async () => {
    const {window} = boot(); const onUpdate = vi.fn();
    window.fetch.mockResolvedValueOnce(response({source_verification: snapshot('complete',
      {findings: [{sentence_id: 1, source_id: 'S1'}]}), next_cursor: 'next'}))
      .mockResolvedValueOnce(response({source_verification: snapshot('complete',
        {findings: [{sentence_id: 1, source_id: 'S2'}]})}));
    window.App.sourceVerification.watch({jobId: 'job-1', getToken: async () => 'token', onUpdate, isActive: () => true});
    await vi.advanceTimersByTimeAsync(0);
    expect(onUpdate).toHaveBeenCalledOnce();
    expect(onUpdate.mock.calls[0][0].findings).toHaveLength(2);
    expect(window.fetch.mock.calls[1][0]).toContain('cursor=next&revision=2');
    expect(window.fetch.mock.calls[0][1].headers.Authorization).toBe('Bearer token');
    await vi.advanceTimersByTimeAsync(60000);
    expect(window.fetch).toHaveBeenCalledTimes(2);
  });
  it('backs off an unchanged revision and avoids fetching its finding pages again', async () => {
    const {window} = boot(); const onUpdate = vi.fn();
    const first = {source_verification: snapshot('running', {findings: [{sentence_id: 1, source_id: 'S1'}]}), next_cursor: 'next'};
    window.fetch.mockResolvedValueOnce(response(first))
      .mockResolvedValueOnce(response({source_verification: snapshot('running', {findings: [{sentence_id: 1, source_id: 'S2'}]})}))
      .mockResolvedValue(response({source_verification: snapshot('running'), unchanged: true, next_cursor: null}));
    const stop = window.App.sourceVerification.watch({jobId: 'job-1', onUpdate, isActive: () => true});
    await vi.advanceTimersByTimeAsync(0);
    expect(window.fetch).toHaveBeenCalledTimes(2);
    await vi.advanceTimersByTimeAsync(1500);
    expect(window.fetch).toHaveBeenCalledTimes(3);
    expect(window.fetch.mock.calls[0][0]).not.toContain('after_revision');
    expect(window.fetch.mock.calls[1][0]).not.toContain('after_revision');
    expect(window.fetch.mock.calls[2][0]).toContain('after_revision=2');
    expect(onUpdate).toHaveBeenCalledOnce();
    await vi.advanceTimersByTimeAsync(2999);
    expect(window.fetch).toHaveBeenCalledTimes(3);
    stop();
  });
  it('aborts on stop and never publishes a late response into another run', async () => {
    const {window} = boot(); const onUpdate = vi.fn(); let resolve;
    window.fetch.mockReturnValue(new Promise(done => {resolve = done;}));
    let active = true;
    const stop = window.App.sourceVerification.watch({jobId: 'job-1', onUpdate, isActive: () => active});
    await vi.advanceTimersByTimeAsync(0);
    const signal = window.fetch.mock.calls[0][1].signal;
    active = false; stop();
    resolve(response({source_verification: snapshot('complete')}));
    await vi.advanceTimersByTimeAsync(0);
    expect(signal.aborted).toBe(true);
    expect(onUpdate).not.toHaveBeenCalled();
  });
  it('restarts inconsistent pagination without publishing mixed versions', async () => {
    const {window} = boot(); const onUpdate = vi.fn();
    window.fetch.mockResolvedValueOnce(response({source_verification: snapshot('running'), next_cursor: '1'}))
      .mockResolvedValueOnce({ok: false, status: 409})
      .mockResolvedValueOnce(response({source_verification: snapshot('complete', {revision: 3})}));
    window.App.sourceVerification.watch({jobId: 'job-1', onUpdate, isActive: () => true});
    await vi.advanceTimersByTimeAsync(0);
    expect(onUpdate).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(1500);
    expect(onUpdate).toHaveBeenCalledOnce();
    expect(onUpdate.mock.calls[0][0].revision).toBe(3);
    expect(window.fetch.mock.calls[2][0]).not.toContain('cursor');
  });
  it('preserves evidence on pending refresh and pauses when hidden', async () => {
    const {window, document} = boot(); const onUpdate = vi.fn();
    window.fetch.mockResolvedValueOnce(response({source_verification: snapshot('running',
      {findings: [{sentence_id: 1, source_id: 'S1', checked: true}]})}))
      .mockResolvedValueOnce(response({source_verification: snapshot('running', {revision: 3})}));
    const stop = window.App.sourceVerification.watch({jobId: 'job-1', onUpdate, isActive: () => true});
    await vi.advanceTimersByTimeAsync(0);
    Object.defineProperty(document, 'hidden', {value: true, configurable: true});
    document.dispatchEvent(new window.Event('visibilitychange'));
    await vi.advanceTimersByTimeAsync(60000);
    expect(window.fetch).toHaveBeenCalledOnce();
    Object.defineProperty(document, 'hidden', {value: false, configurable: true});
    document.dispatchEvent(new window.Event('visibilitychange'));
    await vi.advanceTimersByTimeAsync(0);
    expect(onUpdate.mock.calls[1][0].findings).toHaveLength(1);
    stop();
  });
  it('supports public same-origin snapshots without credentials and rejects remote URLs', async () => {
    const {window} = boot(); const onUpdate = vi.fn();
    window.fetch.mockResolvedValue(response({source_verification: snapshot('complete')}));
    window.App.sourceVerification.watch({url: '/api/share/public/source-check', onUpdate, isActive: () => true});
    await vi.advanceTimersByTimeAsync(0);
    expect(window.fetch.mock.calls[0][1].headers.Authorization).toBeUndefined();
    expect(() => window.App.sourceVerification.watch({url: 'https://other.example/check', getToken: () => 'secret', onUpdate, isActive: () => true})).toThrow();
  });
  it('backs off transient failures and stops after denied access', async () => {
    const {window} = boot(); const onUpdate = vi.fn(); const onError = vi.fn();
    window.fetch.mockResolvedValueOnce({ok: false, status: 503}).mockResolvedValueOnce({ok: false, status: 403});
    window.App.sourceVerification.watch({jobId: 'job-1', onUpdate, onError, isActive: () => true});
    await vi.advanceTimersByTimeAsync(0);
    await vi.advanceTimersByTimeAsync(2999);
    expect(window.fetch).toHaveBeenCalledOnce();
    await vi.advanceTimersByTimeAsync(1);
    await vi.advanceTimersByTimeAsync(60000);
    expect(window.fetch).toHaveBeenCalledTimes(2);
    expect(onUpdate).not.toHaveBeenCalled();
    expect(onError).toHaveBeenCalledTimes(2);
  });
});
