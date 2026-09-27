// Google account selection is explicit and session-only; actions require their own exact preview.
(() => {
  const App = window.App = window.App || {};
  let controlKey = '', controlGeneration = 0, actionKey = '', actionGeneration = 0, currentChat = '';
  let accounts = [], pending = null, chosen = '', calendars = [], selectedCalendars = new Set();
  const api = async (path, options = {}) => (await App.agentWorkspace.request(path, options)).json();
  const post = (path, body) => api(path, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  const node = (tag, text, cls) => {const el=document.createElement(tag); if(text)el.textContent=text; if(cls)el.className=cls; return el;};
  const button = (label, action) => App.agentWorkspace.button(label, action);
  function host(id, anchor) {
    let panel=document.getElementById(id);
    if(!panel){const target=document.getElementById(anchor);if(!target)return null;panel=node('section','','agent-workspace agent-google');panel.id=id;target.after(panel);}
    return panel;
  }
  function checked(label, id) {
    const row=node('label'), input=node('input'); input.type='checkbox';input.id=id;row.append(input,document.createTextNode(label));return row;
  }
  function selection() {
    if(!document.getElementById('googleDataConsent')?.checked)return null;
    const calendar=document.getElementById('googleCalendarEnabled')?.checked === true;
    const gmail=document.getElementById('googleGmailEnabled')?.checked === true;
    if(!calendar && !gmail)return null;
    if(!chosen || (calendar && !selectedCalendars.size))throw new Error('Choose a Google account and, when enabled, at least one calendar.');
    return {connection_id:chosen,calendar,gmail,calendar_ids:calendar?[...selectedCalendars]:[],consent:true};
  }
  async function connect(capabilities, connectionId) {
    const popup=window.open('about:blank','consens-google','popup,width=540,height=720');
    if(!popup)throw new Error('Allow the connection window to open, then try again.');
    try {
      const result=await post('/agent/google/connect',{capabilities,connection_id:connectionId || null});
      pending={state:result.state,uid:window.auth.currentUser.uid,popup}; popup.location.href=result.url;
    } catch(error){popup.close();throw error;}
  }
  window.addEventListener('message', async event => {
    if(!pending || event.origin!==location.origin || event.source!==pending.popup || event.data?.type!=='consens-google-oauth' || event.data.state!==pending.state)return;
    const current=pending;pending=null;
    if(current.uid!==window.auth?.currentUser?.uid){current.popup.close();return;}
    try {
      if(event.data.error || !event.data.code)throw new Error('Google authorization was not completed. No permissions were added.');
      await post('/agent/google/finish',{state:event.data.state,code:event.data.code});
      current.popup.close();await refreshControls(true);
    }catch(error){App.showPopup?.(error.message);}
  });
  async function loadCalendars(panel, pageToken='') {
    const owner=window.auth?.currentUser?.uid, account=chosen, seq=controlGeneration;
    const list=panel.querySelector('.google-calendar-list');
    if(!pageToken){calendars=[];selectedCalendars.clear();list.replaceChildren();}
    const result=await api(`/agent/google/connections/${account}/calendars?page_token=${encodeURIComponent(pageToken)}`);
    if(seq!==controlGeneration || owner!==window.auth?.currentUser?.uid || account!==chosen)return;
    calendars.push(...result.calendars); list.querySelector('.google-more')?.remove();
    for(const calendar of result.calendars){
      const label=checked(`${calendar.summary || calendar.id} · ${calendar.timeZone || 'UTC'}`, `calendar-${calendars.indexOf(calendar)}`);
      const input=label.querySelector('input'); input.value=calendar.id;
      input.addEventListener('change',()=>{if(input.checked){if(selectedCalendars.size>=5){input.checked=false;App.showPopup?.('Select up to five calendars.');return;}selectedCalendars.add(calendar.id);}else selectedCalendars.delete(calendar.id);});
      list.append(label);
    }
    if(result.next_page_token){const more=button('More calendars',()=>loadCalendars(panel,result.next_page_token));more.classList.add('google-more');list.append(more);}
  }
  async function refreshControls(force=false) {
    const panel=host('agentGoogleControls','agentModelControls'); if(!panel)return;
    const uid=window.auth?.currentUser?.uid;
    panel.hidden=!App.agentChat?.isSelected() || !App.agentChat?.canUse();
    if(panel.hidden || !uid)return;
    if(controlKey===uid && !force)return;
    controlKey=uid; const seq=++controlGeneration;chosen='';selectedCalendars.clear();
    panel.textContent='Loading Google connections…';
    try {
      const result=await api('/agent/google/connections');
      if(seq!==controlGeneration || uid!==window.auth?.currentUser?.uid)return;
      accounts=result.connections;panel.replaceChildren();
      const detail=node('details'),summary=node('summary','Google accounts and data for this message');detail.append(summary);
      detail.append(node('p','Consens can read selected calendars and relevant Gmail messages for your request and send excerpts and saved chat context to your chosen AI models, including comparison and review models. Only operator-approved models and hosting providers can process Google data. Web search and external source checks are disabled in these chats. Sending mail or invitations always requires a separate exact confirmation.'));
      if(!result.configured){detail.append(node('p','Google connections are not configured on this installation.'));panel.append(detail);return;}
      detail.append(button('Connect Google Calendar',()=>connect(['calendar_read'])));
      detail.append(button('Connect Gmail',()=>connect(['gmail_read'])));
      const picker=node('select');picker.setAttribute('aria-label','Google account');picker.append(new Option('Choose an account',''));
      for(const account of accounts)picker.append(new Option(`${account.email} · ${account.status}`,account.id));
      detail.append(picker);
      const accountActions=node('div');detail.append(accountActions);
      const calendarToggle=checked('Use selected calendars','googleCalendarEnabled');detail.append(calendarToggle);
      const list=node('div','','google-calendar-list');detail.append(list);
      detail.append(checked('Use Gmail for this request','googleGmailEnabled'));
      const consent=checked('I agree to share relevant selected Google information with my chosen models for this request.','googleDataConsent');detail.append(consent);
      const help=node('a','Manage Google access');help.href='https://myaccount.google.com/permissions';help.target='_blank';help.rel='noopener noreferrer';detail.append(help);
      picker.addEventListener('change', async()=>{
        chosen=picker.value;selectedCalendars.clear();list.replaceChildren();accountActions.replaceChildren();
        document.getElementById('googleDataConsent').checked=false; document.getElementById('googleCalendarEnabled').checked=false;
        document.getElementById('googleGmailEnabled').checked=false;
        if(!chosen)return;
        const account=accounts.find(a=>a.id===chosen);
        accountActions.append(button('Calendar read permission',()=>connect(['calendar_read'],account.id)),button('Calendar write permission',()=>connect(['calendar_write'],account.id)),
          button('Gmail read permission',()=>connect(['gmail_read'],account.id)),button('Gmail send permission',()=>connect(['gmail_send'],account.id)),
          button('Disconnect',async()=>{const result=await api(`/agent/google/connections/${account.id}`,{method:'DELETE'});App.showPopup?.(result.notice);await refreshControls(true);}));
        if(account.status==='connected' && account.capabilities.includes('calendar_read')){
          try {await loadCalendars(panel);}catch(error){list.textContent=error.message;}
        }else list.textContent='Authorize calendar reading to choose calendars.';
      });
      panel.append(detail);
    }catch(error){if(seq!==controlGeneration)return;controlKey='';panel.textContent=error.message;panel.append(button('Retry connections',()=>refreshControls(true)));}
  }
  function valueText(value) {
    if(value===undefined || value===null)return '—';
    if(Array.isArray(value))return value.map(item=>typeof item==='object'?item.email || JSON.stringify(item):item).join('\n') || 'None';
    if(typeof value==='object'){
      if(value.date)return `${value.date} (all day; end date is exclusive)`;
      if(value.dateTime){try{return `${new Date(value.dateTime).toLocaleString(undefined,{timeZone:value.timeZone || 'UTC',dateStyle:'medium',timeStyle:'short'})} · ${value.timeZone || 'UTC'} (${value.dateTime.match(/(Z|[+-]\d\d:\d\d)$/)?.[0] || ''})`;}catch(_){return `${value.dateTime} ${value.timeZone || ''}`;}}
      return '';
    }
    return String(value);
  }
  function preview(action, chatId) {
    const card=node('article','','agent-action-card');
    card.append(node('h3',action.preview.operation),node('p',`Account: ${action.account} · Status: ${action.status}`));
    if(action.kind==='calendar_event'){
      card.append(node('p',`Calendar: ${action.preview.calendar} · Applies to: ${action.preview.target}`));
      const table=node('table'),head=node('tr');for(const title of ['Field','Current','Proposed'])head.append(node('th',title));table.append(head);
      for(const key of ['summary','description','location','start','end','attendees','recurrence']){
        if(action.preview.before[key]===undefined && action.preview.after[key]===undefined)continue;
        const row=node('tr'),before=node('td',valueText(action.preview.before[key])),after=node('td',valueText(action.preview.after[key]));
        before.dataset.label='Current';after.dataset.label='Proposed';
        row.append(node('th',({summary:'Title',description:'Description',location:'Location',start:'Start',end:'End',attendees:'Attendees',recurrence:'Repeats'})[key]),before,after);table.append(row);
      }
      card.append(table,node('p',action.preview.invitations),node('p',`Affected attendees: ${action.preview.attendees.join(', ') || 'None'}`));
    }
    if(action.kind==='gmail_send'){
      card.append(node('p',action.preview.draft_location));
      for(const field of ['from','to','cc','bcc','subject'])card.append(node('p',`${({from:'From',to:'To',cc:'Cc',bcc:'Bcc',subject:'Subject'})[field]}: ${valueText(action.preview[field])}`));
      if(action.preview.reply)card.append(node('p',`Reply to: ${action.preview.reply.from} · ${action.preview.reply.subject} · message ${action.preview.reply.message_id} · thread ${action.preview.reply.thread_id}`));
      const body=node('pre',action.preview.body,'agent-mail-body');card.append(body);
      card.append(node('p',`Attachments (${action.preview.attachments.length})`));
      for(const file of action.preview.attachments){const row=node('p',`${file.name} · ${Math.ceil(file.size/1024)} KB `);row.append(button('Review attachment',()=>App.agentWorkspace.download(chatId,file)));card.append(row);}
      if(action.preview.send_authorized===false)card.append(node('p','Gmail sending is not yet authorized. Enable Gmail send permission for this account, then ask to prepare a fresh draft revision.'));
    }
    if(action.error)card.append(node('p',action.error,'agent-action-error'));
    if(action.status==='pending'){
      const label=checked('I have reviewed this exact change and its recipients.','approve-'+action.id);card.append(label);
      const confirm=button('Confirm and execute',async()=>{
        if(!label.querySelector('input').checked)return;
        await post(`/agent/chats/${chatId}/actions/${action.id}/confirm`,{expected_hash:action.hash});if(currentChat===chatId)await refreshActions(chatId,true);
      });confirm.disabled=true;
      label.querySelector('input').addEventListener('change',()=>{confirm.disabled=!label.querySelector('input').checked || Date.parse(action.approval_until)<=Date.now() || action.preview.send_authorized===false;});
      card.append(confirm,button('Reject',async()=>{await post(`/agent/chats/${chatId}/actions/${action.id}/reject`,{expected_hash:action.hash});if(currentChat===chatId)await refreshActions(chatId,true);}));
      card.append(node('p',`Approval expires ${new Date(action.approval_until).toLocaleString()}. Ask a follow-up to revise this proposal before confirming.`));
    }else if(['unknown','executing'].includes(action.status)){
      card.append(node('p','The result is not yet confirmed. Checking status never repeats the write.'),button('Check action status',async()=>{await post(`/agent/chats/${chatId}/actions/${action.id}/status`,{});if(currentChat===chatId)await refreshActions(chatId,true);}));
    }
    if(action.result){card.append(node('p',action.status==='succeeded'?'Google confirmed this action.':''));if(action.result.warning)card.append(node('p',action.result.warning));}
    return card;
  }
  async function refreshActions(chatId,force=false) {
    const panel=host('agentGoogleActions','agentAnswer'),uid=window.auth?.currentUser?.uid;if(!panel)return;
    if(!chatId || !uid || !App.agentChat?.isSelected()){++actionGeneration;actionKey='';currentChat='';panel.replaceChildren();panel.hidden=true;return;}
    const key=`${uid}:${chatId}`;if(actionKey===key && !force)return;actionKey=key;currentChat=chatId;const seq=++actionGeneration;
    try {
      const result=await api(`/agent/chats/${chatId}/actions`);
      if(seq!==actionGeneration || uid!==window.auth?.currentUser?.uid)return;
      panel.replaceChildren(...result.actions.map(action=>preview(action,chatId)));
      if(result.evidence?.length){
        const detail=node('details'),summary=node('summary',`Referenced Google messages (${result.evidence.length})`);detail.append(summary);
        let offset=0;
        const more=button('More referenced messages',async()=>show());
        function show(){
          more.remove();
          for(const item of result.evidence.slice(offset,offset+10)){
            const row=node('article','','agent-file-card');row.append(node('strong',item.headers.subject || '(no subject)'));
            row.append(node('p',`Account: ${item.account}`));
            for(const field of ['from','to','cc','date'])if(item.headers[field])row.append(node('p',`${field}: ${item.headers[field]}`));
            row.append(node('p',`Message: ${item.message_id} · Thread: ${item.thread_id}`));detail.append(row);
          }
          offset+=10;if(offset<result.evidence.length)detail.append(more);
        }
        show();panel.append(detail);
      }
      panel.hidden=!result.actions.length && !result.evidence?.length;
    }catch(error){if(seq!==actionGeneration)return;actionKey='';panel.hidden=false;panel.replaceChildren(node('p',error.message),button('Retry actions',()=>refreshActions(chatId,true)));}
  }
  window.addEventListener('consensio:auth-state',()=>{
    controlGeneration++;actionGeneration++;controlKey='';actionKey='';chosen='';selectedCalendars.clear();accounts=[];
    pending?.popup.close();pending=null;document.getElementById('agentGoogleControls')?.replaceChildren();document.getElementById('agentGoogleActions')?.replaceChildren();
  });
  App.agentGoogle={selection,consent:()=>document.getElementById('googleDataConsent')?.checked === true,
    resetConsent:()=>{const box=document.getElementById('googleDataConsent');if(box)box.checked=false;},refreshControls,refreshActions};
})();
