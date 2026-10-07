import { describe, expect, it } from 'vitest';
import { JSDOM } from 'jsdom';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { loadScripts, ROOT } from './helpers/appWindow.mjs';

// docs/analytics.md: the core events and the tracker guards around them.
const optOut = readFileSync(path.join(ROOT, 'static/js/analytics-opt-out.js'), 'utf8');

function page(url, { stored = {}, webdriver = false } = {}) {
  const dom = new JSDOM('<!doctype html><body></body>', { url, runScripts: 'outside-only' });
  const w = dom.window;
  Object.entries(stored).forEach(([key, value]) => w.localStorage.setItem(key, value));
  if (webdriver) Object.defineProperty(w.navigator, 'webdriver', { value: true });
  const tracked = [];
  w.umami = { track: (name, data) => tracked.push([name, data]) };
  w.eval(optOut);
  return { w, tracked };
}

describe('Operator exclusion', () => {
  it('switches the operator off unless they opted in with ?notrack=0', () => {
    const plain = page('https://consens.io/app');
    plain.w.consensioAnalytics.excludeOperator();
    expect(plain.w.localStorage.getItem('umami.disabled')).toBe('1');

    const optedIn = page('https://consens.io/app?notrack=0', { stored: { 'umami.disabled': '1' } });
    expect(optedIn.w.localStorage.getItem('umami.keep')).toBe('1');
    optedIn.w.consensioAnalytics.excludeOperator();
    expect(optedIn.w.localStorage.getItem('umami.disabled')).toBe(null);
  });

  it('?notrack=1 drops an earlier opt-in', () => {
    const { w } = page('https://consens.io/?notrack=1', { stored: { 'umami.keep': '1' } });
    expect(w.localStorage.getItem('umami.keep')).toBe(null);
    expect(w.localStorage.getItem('umami.disabled')).toBe('1');
  });
});

describe('consensioBeforeSend', () => {
  it('drops automated browsers', () => {
    const { w } = page('https://consens.io/', { webdriver: true });
    expect(w.consensioBeforeSend('event', { url: 'https://consens.io/' })).toBe(false);
  });

  it('puts back campaign tags and nothing else', () => {
    const { w } = page('https://consens.io/s/x?utm_source=linkedin&token=secret&ref=hn&focus=1');
    const payload = w.consensioBeforeSend('event', { url: 'https://consens.io/s/x' });
    expect(payload.url).toBe('https://consens.io/s/x?utm_source=linkedin&ref=hn');
  });

  it('leaves a URL without campaign tags alone', () => {
    const { w } = page('https://consens.io/topic-follow/confirm?token=secret');
    expect(w.consensioBeforeSend('event', { url: 'https://consens.io/topic-follow/confirm' }).url)
      .toBe('https://consens.io/topic-follow/confirm');
  });
});

describe('open_app', () => {
  function click(w, href, attrs = '') {
    w.document.body.innerHTML = `<a href="${href}" ${attrs}>go</a>`;
    const link = w.document.querySelector('a');
    link.addEventListener('click', event => event.preventDefault());
    link.click();
  }

  it('names the page and the button a visitor entered the app from', () => {
    const { w, tracked } = page('https://consens.io/');
    click(w, '/app?demo=1', 'id="heroDemoButton" data-umami-event="landing_hero_demo_start"');
    expect(tracked).toEqual([['open_app', { from: 'landing', demo: true, place: 'heroDemoButton' }]]);
  });

  it('reports share pages as one source', () => {
    const { w, tracked } = page('https://consens.io/s/some-question-abc');
    click(w, '/app?focus=1');
    expect(tracked).toEqual([['open_app', { from: 'share', demo: false }]]);
  });

  it('ignores links inside the app and links elsewhere', () => {
    const inApp = page('https://consens.io/app');
    click(inApp.w, '/app/watches');
    const external = page('https://consens.io/');
    click(external.w, 'https://example.com/app');
    expect(inApp.tracked).toEqual([]);
    expect(external.tracked).toEqual([]);
  });
});

describe('ask and answer', () => {
  function harness() {
    const events = [];
    const { window } = loadScripts(['static/js/app-core.js'], {
      before: w => { w.trackUmamiEvent = (name, data) => events.push([name, data]); },
    });
    return { App: window.App, events };
  }

  it('describe an agent follow-up and a compare run in the same shape', () => {
    const { App, events } = harness();
    App.trackAsk({ config: { executionMode: 'agent', agentSettings: { reasoning_effort: 'high' } },
      conversationLockKey: 'chat-1', attachments: [], attachmentMeta: [{ name: 'a.pdf' }] });
    App.trackAsk({ config: { autoConsensus: false, deepSearch: false }, conversationLockKey: '', attachments: [] });
    expect(events).toEqual([
      ['ask', { mode: 'agent', follow_up: true, files: true, reasoning: true }],
      ['ask', { mode: 'compare', follow_up: false, files: false, reasoning: false }],
    ]);
  });

  it('count only the first terminal state of a run', () => {
    const { App, events } = harness();
    const context = { config: { autoConsensus: true }, metadata: {} };
    App.trackAnswer(context, 'ok');
    App.trackAnswer(context, 'failed');
    expect(events).toEqual([['answer', { mode: 'consensus', status: 'ok' }]]);
  });
});
