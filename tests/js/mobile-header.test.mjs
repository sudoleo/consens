import {afterEach, describe, expect, it, vi} from 'vitest';
import {loadScripts} from './helpers/appWindow.mjs';

const windows = [];
afterEach(() => windows.splice(0).forEach(window => window.close()));

function boot(mobile = true) {
  const listeners = [];
  const media = {matches:mobile, addEventListener:(_, fn) => listeners.push(fn)};
  const env = loadScripts(['static/js/mobile-header.js'], {
    body:`<header><button id="toggleSidebarButton"></button><nav id="viewSwitch"><button class="view-switch-btn">Watches</button></nav>
      <div id="mobileConversationActions"><button id="mobileNewRunButton"></button></div></header>
      <aside class="sidebar"><button id="newRunButton"></button><button id="sidebarToggleInner"></button><div id="mobileSidebarViews"></div></aside>
      <section id="consensusOutput"><div id="consensusAnswerBody">A completed answer.</div>
        <footer id="runProvenance"><span id="before"></span><span id="consensusFooterActions"><button id="action">Share</button></span><span id="after"></span></footer></section>
      <div id="watchDashboard" hidden></div>`,
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
