import { readFileSync } from 'node:fs';
import { JSDOM } from 'jsdom';
import { describe, expect, it, vi } from 'vitest';
import { ROOT } from './helpers/appWindow.mjs';

const script = readFileSync(`${ROOT}/static/js/model-pulse.js`, 'utf8');

function setup(fetch) {
  const dom = new JSDOM(`<form id="modelPulseFilters">
      <input type="radio" name="period" value="all" checked><input type="radio" name="period" value="7d">
      <input type="radio" name="mode" value="all" checked>
      <select name="with"><option value="">any model</option><option value="anthropic">Claude</option></select>
      <select name="sort"><option value="rate" selected>Rate</option></select>
    </form>
    <div id="modelPulseBoard" class="is-ready"><ol><li>Existing server board</li></ol></div>
    <p id="modelPulseFoot">12 judged runs</p>`, { runScripts: 'outside-only', url: 'https://www.consens.io/model-pulse' });
  dom.window.fetch = fetch;
  dom.window.requestAnimationFrame = fn => fn();
  dom.window.console.warn = () => {};
  dom.window.eval(script);
  return dom;
}
const flush = () => new Promise(resolve => setTimeout(resolve, 0));
const change = (dom, element) => element.dispatchEvent(new dom.window.Event('change', { bubbles: true }));

const VIEW = {
  period: '7d', mode: 'all', rival: 'anthropic', sort: 'rate', min_runs: 10, scale: 60, runs: 40,
  average_field: 5.5, since: '2026-09-27',
  rows: [
    { key: 'openai', family: 'OpenAI / ChatGPT', short: 'ChatGPT', icon: '/static/icons/chat_icons/chatgpt.png',
      rank: 1, runs: 40, picks: 18, rate: 45, fair_share: 18, lift: 2.5, interval: [31, 60], is_rival: false,
      h2h: { wins: 18, losses: 9 } },
    { key: 'anthropic', family: 'Anthropic / Claude', short: 'Claude', icon: '/static/icons/chat_icons/claude.png',
      rank: 2, runs: 40, picks: 9, rate: 22.5, fair_share: 18, lift: 1.25, interval: [12, 38], is_rival: true },
  ],
  sparse: [{ key: 'mistral', short: 'Mistral', runs: 3 }],
};

describe('Model Pulse board', () => {
  it('keeps the server board without a duplicate request', () => {
    const fetch = vi.fn();
    const dom = setup(fetch);
    expect(fetch).not.toHaveBeenCalled();
    expect(dom.window.document.body.textContent).toContain('Existing server board');
    dom.window.close();
  });

  it('refetches on a filter change and renders rates, fair share, range and head-to-head', async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => VIEW });
    const dom = setup(fetch);
    const doc = dom.window.document;
    doc.querySelector('select[name="with"]').value = 'anthropic';
    doc.querySelector('input[value="7d"]').checked = true;
    change(dom, doc.querySelector('select[name="with"]'));
    await flush();
    expect(fetch.mock.calls[0][0]).toBe('/api/model-pulse?period=7d&mode=all&with=anthropic&sort=rate');
    const rows = doc.querySelectorAll('.pulse-row');
    expect(rows).toHaveLength(2);
    expect(rows[0].querySelector('.pulse-rate').textContent).toBe('45%');
    expect(rows[0].textContent).toContain('18 of 40 runs');
    expect(rows[0].textContent).toContain('2.5× fair share');
    expect(rows[0].textContent).toContain('vs Claude 18–9');
    expect(rows[1].classList.contains('is-rival')).toBe(true);
    const meter = rows[0].querySelector('.pulse-meter');
    expect(meter.style.getPropertyValue('--rate')).toBe('75');
    expect(meter.style.getPropertyValue('--fair')).toBe('30');
    expect(meter.style.getPropertyValue('--hi')).toBe('100');
    expect(doc.body.textContent).toContain('Too few runs to rank');
    expect(doc.getElementById('modelPulseFoot').textContent).toContain('40 judged runs since 2026-09-27');
    expect(dom.window.location.search).toBe('?period=7d&mode=all&with=anthropic&sort=rate');
    expect(doc.getElementById('modelPulseBoard').getAttribute('aria-busy')).toBe('false');
    dom.window.close();
  });

  it('keeps the last board when a refresh fails', async () => {
    const dom = setup(vi.fn().mockRejectedValue(new Error('offline')));
    const doc = dom.window.document;
    change(dom, doc.querySelector('select[name="sort"]'));
    await flush();
    expect(doc.body.textContent).toContain('Existing server board');
    expect(doc.getElementById('modelPulseFoot').textContent).toContain('previous view is still shown');
    expect(doc.getElementById('modelPulseBoard').classList.contains('is-loading')).toBe(false);
    dom.window.close();
  });
});
