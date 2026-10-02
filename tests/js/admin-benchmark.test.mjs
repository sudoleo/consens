import { readFileSync } from 'node:fs';
import { describe, expect, it, vi } from 'vitest';
import { JSDOM } from 'jsdom';
import { ROOT } from './helpers/appWindow.mjs';
import path from 'node:path';

const source = readFileSync(path.join(ROOT, 'static/js/admin-benchmark.js'), 'utf8');
const compact = id => ({ run: { run_id: id, manifest: { sample_role: 'pilot' }, results: { n_questions: 2, systems: { consensus: { accuracy_overall: .5 } } } } });
const response = (data, status = 200) => ({ ok: status < 400, status, json: async () => data });
function boot(fetch) {
  const dom = new JSDOM('<select id="runSelect"></select><button id="refreshBtn"></button><p id="bmStatus"></p><div id="runDetail"></div>', { url: 'https://consens.io/admin/benchmark', runScripts: 'outside-only' });
  const w = dom.window;
  w.initializeApp = () => ({});
  w.getAuth = () => ({ currentUser: { getIdToken: async () => 'token' } });
  w.onAuthStateChanged = (_auth, callback) => { w.authChanged = callback; };
  // Execute the original ES-module body with only the Firebase/network boundary
  // injected; all selection, rendering and race guards are production code.
  w.fetch = fetch;
  w.eval(readFileSync(path.join(ROOT, 'static/js/admin-api.js'), 'utf8').replace(/export /g, ''));
  w.eval(source.replace(/^import .*;\r?\n/gm, ''));
  return { w, doc: w.document };
}

describe('Benchmark compact report viewer', () => {
  it('renders compact data, safely quotes labels and excludes raw prompts/answers', async () => {
    const payload = compact('run-a');
    payload.run.manifest.system_prompt = 'PRIVATE RAW PROMPT';
    payload.run.manifest.consensus_prompt_template = 'PRIVATE SYNTHESIS';
    payload.run.questions = [{ question_id: '<img src=x onerror=alert(1)>', category: 'math', answer: 'PRIVATE ANSWER', models: {} }];
    const fetch = vi.fn(async url => response(url.endsWith('/runs') ? { runs: [{ run_id: 'run-a' }] } : payload));
    const { w, doc } = boot(fetch);
    w.authChanged({ uid: 'admin' });
    await vi.waitFor(() => expect(doc.getElementById('runDetail').textContent).toContain('Run · run-a'));
    expect(doc.getElementById('runDetail').textContent).toContain('50.0%');
    expect(doc.getElementById('runDetail').textContent).toContain('<img src=x onerror=alert(1)>');
    expect(doc.querySelector('img')).toBeNull();
    expect(doc.body.textContent).not.toContain('PRIVATE');
    w.close();
  });

  it.each([true, false])('ignores an older selection response (success=%s)', async successful => {
    let release;
    const fetch = vi.fn(url => url.endsWith('/runs') ? Promise.resolve(response({ runs: [{ run_id: 'old' }, { run_id: 'new' }] })) : url.endsWith('/old') ? new Promise(done => { release = done; }) : Promise.resolve(response(compact('new'))));
    const { w, doc } = boot(fetch);
    w.authChanged({});
    await vi.waitFor(() => expect(release).toBeTypeOf('function'));
    const select = doc.getElementById('runSelect'); select.value = 'new'; select.dispatchEvent(new w.Event('change'));
    await vi.waitFor(() => expect(doc.getElementById('runDetail').textContent).toContain('Run · new'));
    release(response(successful ? compact('old') : { error: 'Old failure' }, successful ? 200 : 404));
    await new Promise(done => setTimeout(done, 0));
    expect(doc.getElementById('runDetail').textContent).toContain('Run · new');
    expect(doc.getElementById('bmStatus').textContent).toBe('');
    w.close();
  });

  it.each([404, 403, 'wrong-id'])('clears old data for a failed or mismatched selection: %s', async failure => {
    const fetch = vi.fn(async url => response(url.endsWith('/runs') ? { runs: [{ run_id: 'first' }, { run_id: 'missing /?' }] } : url.endsWith('/first') ? compact('first') : failure === 'wrong-id' ? compact('unrelated') : { error: 'Unavailable' }, !url.endsWith('/runs') && !url.endsWith('/first') && typeof failure === 'number' ? failure : 200));
    const { w, doc } = boot(fetch); w.authChanged({});
    await vi.waitFor(() => expect(doc.getElementById('runDetail').textContent).toContain('Run · first'));
    const select = doc.getElementById('runSelect'); select.value = 'missing /?'; select.dispatchEvent(new w.Event('change'));
    await vi.waitFor(() => expect(doc.getElementById('bmStatus').classList.contains('error')).toBe(true));
    expect(doc.getElementById('runDetail').textContent).toBe('');
    expect(fetch.mock.calls.at(-1)[0]).toContain('missing%20%2F%3F');
    w.close();
  });

  it('invalidates pending detail when refresh finds no runs', async () => {
    let release, count = 0;
    const fetch = vi.fn(url => url.endsWith('/runs') ? Promise.resolve(response({ runs: ++count === 1 ? [{ run_id: 'old' }] : [] })) : new Promise(done => { release = done; }));
    const { w, doc } = boot(fetch); w.authChanged({});
    await vi.waitFor(() => expect(release).toBeTypeOf('function'));
    doc.getElementById('refreshBtn').click();
    await vi.waitFor(() => expect(doc.getElementById('bmStatus').textContent).toBe('No benchmark runs found.'));
    release(response(compact('old'))); await new Promise(done => setTimeout(done, 0));
    expect(doc.getElementById('runDetail').textContent).toBe('');
    expect(doc.getElementById('runSelect').options.length).toBe(0);
    w.close();
  });
});
