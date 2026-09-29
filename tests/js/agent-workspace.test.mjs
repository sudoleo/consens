import { describe, it, expect, vi } from 'vitest';
import { loadScripts } from './helpers/appWindow.mjs';

function boot() {
  return loadScripts(['static/js/agent-workspace.js'], { body: '<section id="agentAnswer"></section>', before(window) {
    window.auth = {currentUser:{uid:'owner',getIdToken:async()=> 'token'}};
    window.App = { agentChat:{isSelected:()=>true}, showPopup:vi.fn(),runRegistry:{isAuthCurrent:()=>true} };
    window.fetch = vi.fn(async()=>({ok:true,json:async()=>({files:[{id:'a'.repeat(32),name:'<img src=x onerror=alert(1)>.txt',status:'partial',warnings:['Missing scanned page']}]})}));
  }});
}
describe('private Agent workspace', () => {
  it('shows saved document versions outside the collapsed upload list', async()=>{
    const {window,document,dom} = boot();
    window.fetch = vi.fn(async()=>({ok:true,json:async()=>({files:[{id:'a'.repeat(32),name:'Decision-v2.pdf',kind:'document',document_id:'d'.repeat(32),version:2,parent_version:1,status:'ready'}]})}));
    await window.App.agentWorkspace.refresh('b'.repeat(32));
    const card = document.querySelector('.agent-document-results .agent-file-card');
    expect(card.textContent).toContain('based on version 1');
    expect(card.closest('details')).toBeNull();
    expect(card.querySelector('button').textContent).toBe('Download');
    dom.window.close();
  });
  it('restores safe file cards and warnings and removes only the selected file', async()=>{
    const {window,document,dom} = boot();
    await window.App.agentWorkspace.refresh('b'.repeat(32));
    expect(document.querySelector('#agentWorkspace img')).toBeNull();
    expect(document.getElementById('agentWorkspace').textContent).toContain('Missing scanned page');
    document.querySelectorAll('#agentWorkspace button')[1].click();
    await new Promise(resolve=>setTimeout(resolve,10));
    expect(window.fetch.mock.calls[1][0]).toBe(`/agent/chats/${'b'.repeat(32)}/files/${'a'.repeat(32)}`);
    expect(window.fetch.mock.calls[1][1].method).toBe('DELETE');
    dom.window.close();
  });
  it('discards an old account response', async()=>{
    const {window,document,dom} = boot();
    let release; window.fetch=vi.fn(()=>new Promise(resolve=>{release=resolve;}));
    const loading=window.App.agentWorkspace.refresh('b'.repeat(32));
    await vi.waitFor(() => expect(typeof release).toBe("function"));
    window.auth.currentUser={uid:'other',getIdToken:async()=> 'new'};
    window.dispatchEvent(new window.Event('consensio:auth-state'));
    release({ok:true,json:async()=>({files:[{name:'private owner file'}]})});
    await loading;
    expect(document.getElementById('agentWorkspace').textContent).not.toContain('private owner file');
    dom.window.close();
  });
});
