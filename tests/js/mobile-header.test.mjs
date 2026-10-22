import {afterEach, describe, expect, it, vi} from 'vitest';
import {loadScripts} from './helpers/appWindow.mjs';

const windows = [];
afterEach(() => windows.splice(0).forEach(window => window.close()));

function boot(mobile = true, {actions = '', main = ''} = {}) {
  const listeners = [];
  const media = {matches:mobile, addEventListener:(_, fn) => listeners.push(fn)};
  const env = loadScripts(['static/js/mobile-header.js'], {
    body:`<header><button id="toggleSidebarButton"></button><nav id="viewSwitch"><button class="view-switch-btn">Watches</button></nav>
      <div id="mobileConversationActions"><button id="mobileNewRunButton"></button>${actions}</div></header>
      <aside class="sidebar"><button id="newRunButton"></button><button id="sidebarToggleInner"></button><div id="mobileSidebarViews"></div></aside>
      <section id="consensusOutput"><div id="consensusAnswerBody">A completed answer.</div>
        <footer id="runProvenance"><span id="before"></span><span id="consensusFooterActions"><button id="action">Share</button><button class="consensus-actions-toggle" aria-label="Citation and copy options"></button></span><span id="after"></span></footer></section>
      <div id="watchDashboard" hidden></div>${main}`,
    before(window) { window.matchMedia = () => media; }
  });
  windows.push(env.window);
  return {...env, resize(value) { media.matches=value; listeners.forEach(fn => fn()); }};
}

describe('mobile action placement', () => {
  it('moves the actual controls and restores their exact desktop slots without duplicates', () => {
    const {document, resize}=boot(false);
    const actions=document.getElementById('consensusFooterActions');
    const views=document.getElementById('viewSwitch');
    const listener=vi.fn();document.getElementById('action').addEventListener('click',listener);
    resize(true);
    expect(actions.parentElement.id).toBe('mobileConversationActions');
    expect(views.parentElement.id).toBe('mobileSidebarViews');
    document.getElementById('action').click();expect(listener).toHaveBeenCalledOnce();
    resize(false);
    expect(actions.previousElementSibling.id).toBe('before');
    expect(actions.nextElementSibling.id).toBe('after');
    expect(views.parentElement.tagName).toBe('HEADER');
    expect(document.querySelectorAll('#action')).toHaveLength(1);
    expect(actions.hidden).toBe(false);
  });
  it('hides actions for incomplete, cleared and Watch views and restores them for the answer', async () => {
    const {document}=boot();
    const actions=document.getElementById('consensusFooterActions');
    expect(actions.hidden).toBe(false);
    for (const [node, attribute, value] of [
      [document.getElementById('runProvenance'),'hidden',''],
      [document.getElementById('consensusOutput'),'class','is-hidden'],
      [document.body,'class','is-hero']
    ]) {
      node.setAttribute(attribute,value);await Promise.resolve();expect(actions.hidden).toBe(true);
      node.removeAttribute(attribute);await Promise.resolve();expect(actions.hidden).toBe(false);
    }
    document.getElementById('watchDashboard').hidden=false;await Promise.resolve();
    expect(actions.hidden).toBe(true);
    document.getElementById('watchDashboard').hidden=true;await Promise.resolve();
    expect(actions.hidden).toBe(false);
  });
  it('names the menu toggle for what it opens in the island and in the footer', () => {
    const {document, resize}=boot(false);
    const toggle=document.querySelector('.consensus-actions-toggle');
    expect(toggle.getAttribute('aria-label')).toBe('Citation and copy options');
    resize(true);
    expect(toggle.getAttribute('aria-label')).toBe('Share, copy and cite');
    expect(toggle.title).toBe('Share, copy and cite');
    resize(false);
    expect(toggle.getAttribute('aria-label')).toBe('Citation and copy options');
  });
  it('uses the existing new-comparison action and closes the sidebar after switching views', () => {
    const {document}=boot();
    const newRun=vi.fn(), closeSidebar=vi.fn();
    document.getElementById('newRunButton').addEventListener('click',newRun);
    document.getElementById('sidebarToggleInner').addEventListener('click',closeSidebar);
    document.getElementById('mobileNewRunButton').click();expect(newRun).toHaveBeenCalledOnce();
    document.querySelector('.sidebar').classList.add('active');
    document.querySelector('.view-switch-btn').click();expect(closeSidebar).toHaveBeenCalledOnce();
  });
});

describe('Agent answer actions in the bar', () => {
  const frame = () => new Promise(resolve => setTimeout(resolve, 40));
  function bootAgent(mobile = true) {
    const env = boot(mobile, {
      actions: '<button id="mobileAgentWatch" hidden></button><button id="mobileAgentShare" hidden></button>',
      main: `<section id="agentAnswer"><div id="agentAnswerBody">An answer.</div><div class="agent-review">
        <button id="agentAnswerWatchButton" class="agent-watch-pill" aria-label="Watch this question for changes"></button>
        <button class="agent-share-pill"></button></div></section>`,
    });
    env.document.body.classList.add('single-agent-active');
    return env;
  }
  it('shows the answer pills as glyphs and presses them with the glyph to return focus to', async () => {
    const {document} = bootAgent();
    await Promise.resolve();
    const [watchGlyph, shareGlyph] = ['mobileAgentWatch', 'mobileAgentShare'].map(id => document.getElementById(id));
    expect(watchGlyph.hidden).toBe(false);
    expect(shareGlyph.hidden).toBe(false);
    const pills = [document.getElementById('agentAnswerWatchButton'), document.querySelector('.agent-share-pill')];
    const triggers = [];
    pills.forEach(pill => pill.addEventListener('click', () => triggers.push(pill._actionTrigger)));
    watchGlyph.click(); shareGlyph.click();
    expect(triggers).toEqual([watchGlyph, shareGlyph]);
    expect(pills.map(pill => pill._actionTrigger)).toEqual([null, null]);
  });
  it('follows the pill: its "Watching" state, its removal, the start screen and the desktop', async () => {
    const {document, resize} = bootAgent();
    await Promise.resolve();
    const glyph = document.getElementById('mobileAgentWatch');
    const pill = document.getElementById('agentAnswerWatchButton');
    pill.classList.add('is-watching');
    pill.setAttribute('aria-label', 'You watch this question. Open it on Watches.');
    await frame();
    expect(glyph.classList.contains('is-watching')).toBe(true);
    expect(glyph.getAttribute('aria-label')).toBe('You watch this question. Open it on Watches.');
    document.body.classList.add('is-hero'); await Promise.resolve();
    expect(glyph.hidden).toBe(true);
    document.body.classList.remove('is-hero'); await Promise.resolve();
    expect(glyph.hidden).toBe(false);
    pill.remove(); await frame();
    expect(glyph.hidden).toBe(true);
    expect(document.getElementById('mobileAgentShare').hidden).toBe(false);
    resize(false);
    expect(document.getElementById('mobileAgentShare').hidden).toBe(true);
  });
});
