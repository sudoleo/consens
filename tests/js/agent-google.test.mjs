import {describe,it,expect,vi} from 'vitest';
import {loadScripts} from './helpers/appWindow.mjs';

function boot(){
  const connection='a'.repeat(32),chat='b'.repeat(32);
  const action={id:'c'.repeat(32),kind:'calendar_event',hash:'d'.repeat(64),status:'pending',account:'owner@example.org',approval_until:'2099-01-01T00:00:00Z',preview:{operation:'Create event',calendar:'primary',target:'single',before:{},after:{summary:'<img src=x onerror=bad()>',start:{dateTime:'2026-10-01T10:00:00+02:00',timeZone:'Europe/Copenhagen'},attendees:[{email:'a@example.org'}]},attendees:['a@example.org'],invitations:'Will notify attendees'}};
  const setup=loadScripts(['static/js/agent-workspace.js','static/js/agent-google.js'],{body:'<div id="agentModelControls"></div><section id="agentAnswer"></section>',before(w){
    w.auth={currentUser:{uid:'owner',getIdToken:async()=> 'token'}};
    w.App={agentChat:{isSelected:()=>true,canUse:()=>true},showPopup:vi.fn()};
    w.fetch=vi.fn(async(url,options)=>({ok:true,json:async()=>{
      if(url.endsWith('/connections'))return {configured:true,connections:[{id:connection,email:'owner@example.org',status:'connected',capabilities:['calendar_read']}]};
      if(url.includes('/calendars?'))return {calendars:[{id:'primary',summary:'Personal',timeZone:'Europe/Copenhagen'}]};
      if(url.endsWith('/confirm')){action.status='succeeded';return {action};}
      if(url.endsWith('/actions'))return {actions:[action]};
      return {};
    }}));
  }});
  return {...setup,connection,chat,action};
}
describe('Google selection and approvals',()=>{
  it('requires explicit account, calendar and model-transfer consent',async()=>{
    const {window:w,document:d,dom,connection}=boot();
    await w.App.agentGoogle.refreshControls();
    expect(w.App.agentGoogle.selection()).toBeNull();
    const select=d.querySelector('[aria-label="Google account"]');select.value=connection;select.dispatchEvent(new w.Event('change'));
    await vi.waitFor(()=>expect(d.querySelector('.google-calendar-list input')).not.toBeNull());
    d.querySelector('.google-calendar-list input').click();d.getElementById('googleCalendarEnabled').click();
    expect(w.App.agentGoogle.selection()).toBeNull();
    d.getElementById('googleDataConsent').click();
    expect(w.App.agentGoogle.selection()).toEqual({connection_id:connection,calendar:true,calendar_ids:['primary'],consent:true});
    w.auth.currentUser={uid:'other',getIdToken:async()=> 'new'};w.dispatchEvent(new w.Event('consensio:auth-state'));
    expect(w.App.agentGoogle.selection()).toBeNull();expect(d.getElementById('agentGoogleControls').textContent).toBe('');
    dom.window.close();
  });
  it('renders untrusted text safely and submits the exact displayed hash only after review',async()=>{
    const {window:w,document:d,dom,chat,action}=boot();
    await w.App.agentGoogle.refreshActions(chat);
    expect(d.querySelector('#agentGoogleActions img')).toBeNull();
    const confirm=[...d.querySelectorAll('button')].find(b=>b.textContent==='Confirm and execute');
    expect(confirm.disabled).toBe(true);expect(w.fetch.mock.calls.some(([url])=>url.endsWith('/confirm'))).toBe(false);
    d.getElementById('approve-'+action.id).click();confirm.click();
    await vi.waitFor(()=>expect(w.fetch.mock.calls.some(([url])=>url.endsWith('/confirm'))).toBe(true));
    const sent=w.fetch.mock.calls.find(([url])=>url.endsWith('/confirm'));
    expect(JSON.parse(sent[1].body)).toEqual({expected_hash:'d'.repeat(64)});
    await vi.waitFor(()=>expect(d.getElementById('agentGoogleActions').textContent).toContain('succeeded'));
    dom.window.close();
  });
  it('does not offer repeat execution for ambiguous results',async()=>{
    const {window:w,document:d,dom,chat,action}=boot();action.status='unknown';
    await w.App.agentGoogle.refreshActions(chat);
    expect(d.getElementById('agentGoogleActions').textContent).toContain('never repeats the write');
    expect([...d.querySelectorAll('button')].some(b=>b.textContent==='Confirm and execute')).toBe(false);
    dom.window.close();
  });
});
