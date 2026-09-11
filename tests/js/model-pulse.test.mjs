import { readFileSync } from 'node:fs';
import { JSDOM } from 'jsdom';
import { describe, expect, it, vi } from 'vitest';
import { ROOT } from './helpers/appWindow.mjs';

const script = readFileSync(`${ROOT}/static/js/model-pulse.js`, 'utf8');
function setup(fetch) {
  const dom = new JSDOM(`<p id="modelLeaderboardPeriod">All-time ranking</p>
    <form><button data-model-pulse-period="all" aria-pressed="true">All</button>
    <button data-model-pulse-period="since-2026-08-31" aria-pressed="false">Recent</button></form>
    <div id="modelLeaderboardRows" data-period="all"><div>Existing server ranking</div></div>
    <span id="modelLeaderboardTotal">24 selections</span>`, { runScripts: 'outside-only' });
  dom.window.fetch = fetch;
  dom.window.requestAnimationFrame = fn => fn();
  dom.window.console.warn = () => {};
  dom.window.eval(script);
  return dom;
}
const flush = () => new Promise(resolve => setTimeout(resolve, 0));

describe('Model Pulse progressive enhancement', () => {
  it('keeps the initial server ranking without a duplicate request', () => {
    const fetch = vi.fn();
    const dom = setup(fetch);
    expect(fetch).not.toHaveBeenCalled();
    expect(dom.window.document.body.textContent).toContain('Existing server ranking');
    dom.window.close();
  });

  it('switches period and renders individual start dates and every returned family', async () => {
    const rows = Array.from({length: 10}, (_, i) => ({family: `Family ${i}`, selections: i,
      ...(i === 9 ? {available_since: '2026-09-02'} : {})}));
    const fetch = vi.fn().mockResolvedValue({ok: true, json: async () => ({rows,
      total_selections: 45, period: 'since-2026-08-31'})});
    const dom = setup(fetch);
    dom.window.document.querySelectorAll('button')[1].click();
    await flush();
    const doc = dom.window.document;
    expect(fetch.mock.calls[0][0]).toContain('period=since-2026-08-31');
    expect(doc.querySelectorAll('[role="listitem"]')).toHaveLength(10);
    expect(doc.body.textContent).toContain('tracked since 2026-09-02');
    expect(doc.getElementById('modelLeaderboardRows').dataset.period).toBe('since-2026-08-31');
    expect(doc.getElementById('modelLeaderboardTotal').textContent).toContain('45 judge selections since');
    dom.window.close();
  });

  it('preserves the last ranking and restores its period when refresh fails', async () => {
    const dom = setup(vi.fn().mockRejectedValue(new Error('offline')));
    dom.window.document.querySelectorAll('button')[1].click();
    await flush();
    const doc = dom.window.document;
    expect(doc.body.textContent).toContain('Existing server ranking');
    expect(doc.getElementById('modelLeaderboardPeriod').textContent).toBe('All-time ranking');
    expect(doc.querySelector('button').getAttribute('aria-pressed')).toBe('true');
    expect(doc.querySelector('button').disabled).toBe(false);
    expect(doc.getElementById('modelLeaderboardRows').getAttribute('aria-busy')).toBe('false');
    dom.window.close();
  });
});
