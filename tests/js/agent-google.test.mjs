import {describe,it,expect,vi} from 'vitest';
import {loadScripts} from './helpers/appWindow.mjs';

const BODY='<div class="input-section"><div class="chat-input-container"><textarea id="questionInput"></textarea><div id="attachMenu"><button id="agentComparisonMenuOption"></button></div><button id="attachTrigger"></button></div><div id="composerModeBar"><div class="composer-mode-controls"><button id="composerModelPicker"></button></div></div></div><section id="agentAnswer"></section>';

function boot({chatId='',googleData=false,googleConsent=false,writes=false,drive=null}={}){
  const connection='a'.repeat(32),chat='b'.repeat(32);
  const action={id:'c'.repeat(32),kind:'calendar_event',hash:'d'.repeat(64),status:'pending',account:'owner@example.org',connection_id:connection,approval_until:'2099-01-01T00:00:00Z',preview:{operation:'Create event',calendar:'primary',calendar_name:'Personal',target:'single',before:{},after:{summary:'<img src=x onerror=bad()>',start:{dateTime:'2026-10-01T10:00:00+02:00',timeZone:'Europe/Copenhagen'},attendees:[{email:'a@example.org'}]},attendees:['a@example.org'],invitations:'Will notify attendees'}};
  const state={actions:[action],evidence:[],googleData,googleConsent,writes,drive,driveFiles:false,connections:[{id:connection,email:'owner@example.org',status:'connected',capabilities:['calendar_read','gmail_read']}],renewed:null};
  const setup=loadScripts(['static/js/agent-google.js'],{body:BODY,before(w){
    w.auth={currentUser:{uid:'owner',getIdToken:async()=> 'token'}};
    let agent=true;
    w.App={agentChat:{isSelected:()=>agent,canUse:()=>true},showPopup:vi.fn(),
      attachments:{hasDriveFiles:()=>state.driveFiles,removeDriveFiles:vi.fn(()=>{const had=state.driveFiles;state.driveFiles=false;return had?1:0;})},
      runRegistry:{visible:()=>null,isExecuting:()=>false,getSelectedConversationBasis:()=>chatId?{chatId,currentTurn:{}}:null}};
    state.setAgent=value=>{agent=value;};
    w.updateQuestionInputAccess=vi.fn();
    w.fetch=vi.fn(async(url,options={})=>({ok:true,json:async()=>{
      if(url.endsWith('/connections'))return {configured:true,writes:state.writes,drive:state.drive,connections:state.connections};
      if(url.includes('/calendars?'))return {calendars:[{id:'primary',summary:'Personal',timeZone:'Europe/Copenhagen'}]};
      if(url.endsWith('/confirm')){state.actions.at(-1).status='succeeded';return {action:state.actions.at(-1)};}
      if(url.endsWith('/renew')){const old=state.actions.at(-1);old.status='superseded';const next={...structuredClone(old),id:'e'.repeat(32),hash:'f'.repeat(64),status:'pending',replaces:old.id,approval_until:'2099-01-01T00:00:00Z'};
        const removed=JSON.parse(options.body).remove_recipients||[];
        if(next.preview.bcc){next.preview.bcc=next.preview.bcc.filter(e=>!removed.includes(e));next.preview.recipient_warnings=(next.preview.recipient_warnings||[]).filter(w=>!removed.includes(w.email));}
        state.renewed=JSON.parse(options.body);state.actions.push(next);return {action:next};}
      if(url.endsWith('/actions'))return {actions:state.actions,evidence:state.evidence,google_data:state.googleData,google_consent:state.googleConsent,writes:state.writes};
      return {};
    }}));
  }});
  return {...setup,connection,chat,action,state};
}
const bootGoogle=boot;
const buttons=(d,text)=>[...d.querySelectorAll('button')].filter(b=>b.textContent===text);
const flush=()=>new Promise(r=>setTimeout(r,0));

describe('Google selection and consent',()=>{
  it('loads connections only on first use and never sends a partial selection',async()=>{
    const {window:w,document:d,connection}=boot();
    w.App.agentGoogle.refreshControls();
    expect(w.fetch).not.toHaveBeenCalled();
    expect(w.App.agentGoogle.selection()).toBeNull();expect(w.App.agentGoogle.blocker()).toBeNull();
    w.App.agentGoogle.open();
    await vi.waitFor(()=>expect(d.getElementById('googleCalendarEnabled')).not.toBeNull());
    expect(d.getElementById('agentGoogleSheet').hidden).toBe(false);
    d.getElementById('googleCalendarEnabled').click();
    // Calendar on without a calendar or consent: blocked, never silently dropped.
    expect(w.App.agentGoogle.blocker().action).toBe('google-open');
    expect(()=>w.App.agentGoogle.selection()).toThrow(/calendar/);
    await vi.waitFor(()=>expect(d.querySelector('.google-calendar-list input')).not.toBeNull());
    d.querySelector('.google-calendar-list input').click();
    expect(w.App.agentGoogle.blocker()).toMatchObject({action:'google-consent'});
    expect(()=>w.App.agentGoogle.selection()).toThrow(/Allow sharing/);
    expect(d.getElementById('agentGoogleChips').hidden).toBe(false);
    expect(d.getElementById('agentGoogleChips').textContent).toContain('Personal');
    w.App.agentGoogle.consent(true);
    expect(w.App.agentGoogle.blocker()).toBeNull();
    expect(w.App.agentGoogle.selection()).toEqual({connection_id:connection,calendar:true,gmail:false,calendar_ids:['primary'],consent:true});
    w.App.agentGoogle.resetConsent();
    expect(w.App.agentGoogle.consent()).toBe(false);expect(w.App.agentGoogle.blocker().action).toBe('google-consent');
    w.auth.currentUser={uid:'other',getIdToken:async()=> 'new'};w.dispatchEvent(new w.Event('consensio:auth-state'));
    expect(w.App.agentGoogle.selection()).toBeNull();expect(d.getElementById('agentGoogleChips').hidden).toBe(true);
  });
  it('asks for consent in a chat with Google data that has none yet',async()=>{
    const chat='b'.repeat(32);
    const {window:w,document:d}=boot({chatId:chat,googleData:true});
    const changes=vi.fn();w.addEventListener('consensio:agent-google-change',changes);
    await w.App.agentGoogle.refreshActions(chat);
    expect(w.App.agentGoogle.blocker()).toMatchObject({action:'google-consent',label:'Allow for this chat'});
    expect(d.getElementById('agentGoogleChips').textContent).toContain('This chat contains Google data');
    expect(d.querySelector('.agent-google-consent').hidden).toBe(false);
    expect(d.querySelector('.agent-google-consent').textContent).toBe('Share with the models in this chat');
    w.App.agentGoogle.consent(true);
    expect(w.App.agentGoogle.blocker()).toBeNull();expect(changes).toHaveBeenCalled();
    expect(w.App.agentGoogle.selection()).toBeNull();
  });
  it('remembers the consent for the whole chat',async()=>{
    const chat='b'.repeat(32);
    const {window:w,document:d}=boot({chatId:chat,googleData:true,googleConsent:true});
    await w.App.agentGoogle.refreshActions(chat);
    // No checkbox on every follow-up: the chat already holds the consent.
    expect(w.App.agentGoogle.blocker()).toBeNull();
    expect(w.App.agentGoogle.consent()).toBe(true);
    expect(d.querySelector('.agent-google-consent').hidden).toBe(true);
    expect(d.getElementById('agentGoogleChips').textContent).toContain('Private chat · Google data');
    // A final event can carry the consent before the actions list arrives.
    const other='9'.repeat(32);
    w.App.agentGoogle.noteGoogleData(other,true,true);
    w.App.runRegistry.getSelectedConversationBasis=()=>({chatId:other,currentTurn:{}});
    expect(w.App.agentGoogle.consent()).toBe(true);
  });
  it('treats a Drive file like Google data: consent first, Agent chats only',async()=>{
    const {window:w,document:d,state}=boot();
    expect(w.App.agentGoogle.blocker()).toBeNull();
    state.driveFiles=true;w.dispatchEvent(new w.Event('consensio:attachments-change'));
    expect(w.App.agentGoogle.blocker()).toMatchObject({action:'google-consent'});
    expect(d.getElementById('agentGoogleChips').hidden).toBe(false);
    w.App.agentGoogle.consent(true);
    expect(w.App.agentGoogle.blocker()).toBeNull();
    // Switching this draft away from Agent takes the Drive file off it, with a reason.
    state.setAgent(false);w.App.agentGoogle.refreshControls();
    expect(w.App.attachments.removeDriveFiles).toHaveBeenCalled();
    expect(w.App.showPopup).toHaveBeenCalledWith(expect.stringContaining('Agent chats only'));
  });
  it('lives only in the (+) menu and appears once the installation offers it',async()=>{
    const {window:w,document:d}=boot();
    w.App.agentGoogle.refreshControls();
    const option=d.getElementById('agentGoogleMenuOption');
    // Unknown yet: no row that could vanish on first use or open onto "not available".
    expect(option.hidden).toBe(true);
    expect(d.getElementById('composerGoogleButton')).toBeNull();
    d.getElementById('attachTrigger').click();
    await vi.waitFor(()=>expect(option.hidden).toBe(false));
    expect(option.textContent).toContain('Read as sources');
  });
  it('never offers the row on an installation without Gmail and Calendar',async()=>{
    const {window:w,document:d,state}=boot();
    w.fetch=vi.fn(async()=>({ok:true,json:async()=>({configured:false,writes:false,drive:null,connections:[]})}));
    d.getElementById('attachTrigger').click();
    await vi.waitFor(()=>expect(w.fetch).toHaveBeenCalled());
    await flush();
    expect(d.getElementById('agentGoogleMenuOption').hidden).toBe(true);
  });
  it('says plainly that Google is read-only and offers no write permission',async()=>{
    const {window:w,document:d}=boot();
    w.App.agentGoogle.open();
    await vi.waitFor(()=>expect(d.getElementById('googleCalendarEnabled')).not.toBeNull());
    const sheet=d.getElementById('agentGoogleSheet');
    expect(sheet.querySelector('h2').textContent).toBe('Gmail & Calendar');
    expect(sheet.textContent).toContain('Read-only: Consens never sends, changes or deletes anything in Google.');
    expect(sheet.textContent).toContain('zero data retention');
    expect(sheet.textContent).not.toContain('Send emails you confirm');
    expect(sheet.textContent).not.toContain('Create and edit events');
    expect(d.getElementById('agentGoogleMenuOption').textContent).toContain('Gmail & Calendar');
    expect(await w.App.agentGoogle.config()).toEqual({configured:true,writes:false,drive:null});
  });
  it('removing a source chip turns it off',async()=>{
    const {window:w,document:d}=boot();
    w.App.agentGoogle.open();
    await vi.waitFor(()=>expect(d.getElementById('googleGmailEnabled')).not.toBeNull());
    d.getElementById('googleGmailEnabled').click();
    expect(d.getElementById('agentGoogleChips').textContent).toContain('Gmail · owner@example.org');
    d.querySelector('.agent-google-chip-remove').click();
    expect(w.App.agentGoogle.selection()).toBeNull();expect(w.App.agentGoogle.blocker()).toBeNull();
  });
});

describe('Action cards on a read-only installation',()=>{
  it('shows an older proposal as it was, never confirms it and lets it be discarded',async()=>{
    const {window:w,document:d,chat,action}=boot();
    await w.App.agentGoogle.refreshActions(chat);
    const card=d.querySelector('.agent-action-card');
    expect(card.textContent).toContain('can no longer be sent or applied');
    expect(buttons(d,'Create event')).toHaveLength(0);
    expect(d.getElementById('approve-'+action.id)).toBeNull();
    expect(buttons(d,'Prepare again')).toHaveLength(0);
    buttons(d,'Discard')[0].click();
    await vi.waitFor(()=>expect(w.fetch.mock.calls.some(([url])=>url.endsWith('/reject'))).toBe(true));
    expect(w.fetch.mock.calls.some(([url])=>url.endsWith('/confirm'))).toBe(false);
  });
});

// With GOOGLE_WRITES_ENABLED the dormant write path keeps working.
describe('Action cards',()=>{
  const boot=(options={})=>bootGoogle({writes:true,...options});
  it('renders untrusted text safely and submits the exact displayed hash only after review',async()=>{
    const {window:w,document:d,chat,action}=boot();
    const changes=vi.fn();w.addEventListener('consensio:agent-actions-change',e=>changes(e.detail));
    await w.App.agentGoogle.refreshActions(chat);
    expect(d.querySelector('#agentGoogleActions img')).toBeNull();
    expect(w.App.agentGoogle.pendingCount(chat)).toBe(1);
    expect(changes).toHaveBeenCalledWith(expect.objectContaining({chatId:chat,pending:1}));
    const card=d.querySelector('.agent-action-card');
    expect(card.dataset.status).toBe('pending');expect(card.textContent).toContain('Needs review');
    expect(card.textContent).toContain('Personal');
    const confirm=buttons(d,'Create event')[0];
    expect(confirm.disabled).toBe(true);
    confirm.click();await flush();
    expect(w.fetch.mock.calls.some(([url])=>url.endsWith('/confirm'))).toBe(false);
    d.getElementById('approve-'+action.id).click();confirm.click();
    await vi.waitFor(()=>expect(w.fetch.mock.calls.some(([url])=>url.endsWith('/confirm'))).toBe(true));
    const sent=w.fetch.mock.calls.find(([url])=>url.endsWith('/confirm'));
    expect(JSON.parse(sent[1].body)).toEqual({expected_hash:'d'.repeat(64)});
    await vi.waitFor(()=>expect(d.querySelector('.agent-action-card').dataset.status).toBe('succeeded'));
    expect(d.getElementById('agentGoogleActions').textContent).toContain('Google confirmed this action.');
    expect(w.App.agentGoogle.pendingCount(chat)).toBe(0);
  });
  it('does not offer repeat execution for ambiguous results',async()=>{
    const {window:w,document:d,chat,action}=boot();action.status='unknown';
    await w.App.agentGoogle.refreshActions(chat);
    expect(d.getElementById('agentGoogleActions').textContent).toContain('never repeats the write');
    expect(buttons(d,'Create event')).toHaveLength(0);
  });
  it('shows expired approvals as expired and prepares them again without a model call',async()=>{
    const {window:w,document:d,chat,action,state}=boot();action.approval_until='2020-01-01T00:00:00Z';
    await w.App.agentGoogle.refreshActions(chat);
    const card=d.querySelector('.agent-action-card');
    expect(card.dataset.status).toBe('expired');expect(card.textContent).toContain('Expired');
    expect(d.getElementById('approve-'+action.id)).toBeNull();
    buttons(d,'Prepare again')[0].click();
    await vi.waitFor(()=>expect(state.renewed).toEqual({expected_hash:action.hash,remove_recipients:[]}));
    await vi.waitFor(()=>expect(d.querySelector('.agent-action-card').dataset.actionId).toBe('e'.repeat(32)));
    // The renewed version replaces the old one, starts unapproved and keeps history.
    expect(d.querySelector('.agent-action-history summary').textContent).toBe('Earlier versions (1)');
    expect(d.getElementById('approve-'+'e'.repeat(32)).checked).toBe(false);
  });
  it('requires a per-address acknowledgement for flagged recipients and offers a send grant for unauthorized drafts',async()=>{
    const {window:w,document:d,chat,action,state}=boot();
    action.kind='gmail_send';action.preview={operation:'Send email',draft_location:'Saved in Consens',from:'owner@example.org',to:['buyer@example.org'],cc:[],bcc:['private@example.org'],subject:'Offer decision',body:'<script>send()</script>\nPlease review.',attachments:[{id:'e'.repeat(32),name:'Decision.pdf',size:4096}],send_authorized:false,reply:{from:'Supplier',subject:'Offers',message_id:'m1',thread_id:'t1'},recipient_warnings:[{email:'private@example.org',field:'bcc'}]};
    state.evidence=[{message_id:'m1',headers:{subject:'Offers',from:'Supplier <s@example.org>'}}];
    w.App.agentWorkspace={download:vi.fn()};
    await w.App.agentGoogle.refreshActions(chat);
    expect(w.App.agentGoogle.evidenceFor('m1')).toEqual({subject:'Offers',from:'Supplier <s@example.org>'});
    const panel=d.getElementById('agentGoogleActions');
    expect(panel.textContent).toContain('private@example.org');expect(panel.textContent).toContain('Decision.pdf');
    expect(panel.querySelector('script')).toBeNull();
    expect(panel.querySelector('.agent-recipient-warning').getAttribute('role')).toBe('alert');
    expect(panel.querySelector('.agent-recipient-flag').textContent).toBe('private@example.org');
    // Without a send grant: one clear primary action, no dead-end checkbox.
    expect(d.getElementById('approve-'+action.id)).toBeNull();
    expect(buttons(d,'Allow sending from owner@example.org')).toHaveLength(1);
    buttons(d,'Review')[0].click();
    expect(w.App.agentWorkspace.download).toHaveBeenCalledWith(chat,action.preview.attachments[0]);
    action.preview.send_authorized=true;action.hash='9'.repeat(64);
    await w.App.agentGoogle.refreshActions(chat,true);
    const review=d.getElementById('approve-'+action.id),send=buttons(d,'Send email')[0];
    expect(review.checked).toBe(false);
    review.click();
    expect(send.disabled).toBe(true);
    expect(d.querySelector('.agent-action-hint').hidden).toBe(false);
    d.querySelector('.agent-recipient-ack input').click();
    expect(send.disabled).toBe(false);
    // Removing the flagged recipient renews the exact draft without it.
    buttons(d,'Remove recipient')[0].click();
    await vi.waitFor(()=>expect(state.renewed).toEqual({expected_hash:'9'.repeat(64),remove_recipients:['private@example.org']}));
    await vi.waitFor(()=>expect(d.querySelector('.agent-action-card[data-status="pending"]').dataset.actionId).toBe('e'.repeat(32)));
    expect(d.querySelector('.agent-action-card[data-status="pending"] .agent-recipient-warning')).toBeNull();
  });
  it('coalesces refreshes and discards late reads after an account change',async()=>{
    const {window:w,document:d,chat,action}=boot();let resolve;
    w.fetch=vi.fn(()=>new Promise(r=>{resolve=r;}));
    const read=w.App.agentGoogle.refreshActions(chat);
    for(let i=0;i<4;i++)w.App.agentGoogle.refreshActions(chat,true);
    await vi.waitFor(()=>expect(resolve).toBeTypeOf('function'));
    expect(w.fetch).toHaveBeenCalledTimes(1);
    w.auth.currentUser={uid:'other',getIdToken:async()=> 'other-token'};w.dispatchEvent(new w.Event('consensio:auth-state'));
    resolve({ok:true,json:async()=>({actions:[action]})});await read;
    expect(d.getElementById('agentGoogleActions').textContent).toBe('');
  });
  it('projects the current chat on its own, skips a new chat while it starts and reloads when the run finishes',async()=>{
    const chat='b'.repeat(32);
    const {window:w,document:d}=boot({chatId:chat});
    w.App.agentGoogle.refreshControls();
    await vi.waitFor(()=>expect(d.querySelector('.agent-action-card')).not.toBeNull());
    expect(w.fetch.mock.calls.filter(([url])=>url.endsWith('/actions'))).toHaveLength(1);
    // A first message creates a new chat: nothing to read until it finishes.
    const fresh='9'.repeat(32),run={runId:'r1',basis:null,config:{executionMode:'agent'},metadata:{chatId:fresh}};
    w.App.runRegistry={visible:()=>run,isExecuting:()=>true,getSelectedConversationBasis:()=>null};
    w.fetch.mockClear();
    w.App.agentGoogle.refreshControls();
    expect(d.querySelector('.agent-action-card')).toBeNull();
    await flush();expect(w.fetch).not.toHaveBeenCalled();
    w.dispatchEvent(new w.CustomEvent('consensio:run-registry-change',{detail:{type:'finished',context:run}}));
    await vi.waitFor(()=>expect(w.fetch.mock.calls.some(([url])=>url.endsWith(`/chats/${fresh}/actions`))).toBe(true));
  });
  it('stays hidden when actions fail in a chat without Google data',async()=>{
    const {window:w,document:d,chat}=boot();
    w.fetch=vi.fn(async()=>({ok:false,status:500,json:async()=>({detail:'boom'})}));
    await w.App.agentGoogle.refreshActions(chat);
    expect(d.getElementById('agentGoogleActions').hidden).toBe(true);
  });
});
