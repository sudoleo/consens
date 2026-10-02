import { describe, expect, it } from 'vitest';
import { JSDOM } from 'jsdom';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { ROOT } from './helpers/appWindow.mjs';

const source = readFileSync(path.join(ROOT, 'static/js/analytics-opt-out.js'), 'utf8');
describe('Analytics opt-out before tracker startup', () => {
  it.each([
    ['?notrack=1', null, '1'], ['?notrack=0', '1', null],
    ['', '1', '1'], ['', null, null], ['?notrack=other', '1', '1'],
    ['?notrack=', '1', '1'], ['?other=1', '1', '1'],
  ])('applies %s to %s before the next script runs', (query, stored, expected) => {
    const dom = new JSDOM('', { url: `https://consens.io/${query}`, runScripts: 'outside-only' });
    const w = dom.window;
    if (stored) w.localStorage.setItem('umami.disabled', stored);
    w.eval(source);
    w.eval('window.trackerStarted = true; window.trackerDisabled = localStorage.getItem("umami.disabled");');
    expect(w.trackerDisabled).toBe(expected);
    expect(w.trackerStarted).toBe(true);
    w.close();
  });

  it.each(['1', '0'])('allows page/tracker initialization when storage write for notrack=%s throws', flag => {
    const dom = new JSDOM('', { url: `https://consens.io/?notrack=${flag}`, runScripts: 'outside-only' });
    const calls = [];
    Object.defineProperty(dom.window, 'localStorage', { value: {
      setItem: (...args) => { calls.push(['set', ...args]); throw new Error('storage denied'); },
      removeItem: (...args) => { calls.push(['remove', ...args]); throw new Error('storage denied'); },
      getItem: () => { throw new Error('Opt-out must not read storage'); },
    } });
    expect(() => dom.window.eval(source + ';window.pageStarted = true;')).not.toThrow();
    expect(dom.window.pageStarted).toBe(true);
    expect(calls).toEqual(flag === '1' ? [['set', 'umami.disabled', '1']] : [['remove', 'umami.disabled']]);
    dom.window.close();
  });
});
