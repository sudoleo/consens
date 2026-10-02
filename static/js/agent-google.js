// Google data for Agent Beta: explicit per-message selection and consent, and
// exact-content action cards. Every external write needs one explicit gesture
// bound to the displayed hash; restored or revised cards always start unapproved.
(() => {
  const App = window.App = window.App || {};
  const MAX_CALENDARS = 5, DEBOUNCE_MS = 300, EXPIRY_TICK_MS = 30000;
  const ICONS = {
    google: '<path d="M19.5 12.2a7.5 7.5 0 1 1-2.2-5.4"/><path d="M19.5 12.2H12.5"/>',
    mail: '<rect x="3.5" y="5.5" width="17" height="13" rx="2"/><path d="m4 7 8 6 8-6"/>',
    calendar: '<rect x="3.5" y="5" width="17" height="15.5" rx="2"/><path d="M3.5 10h17M8 3v4M16 3v4"/>',
    warning: '<path d="M12 4 2.8 19.5h18.4Z"/><path d="M12 10v4.5M12 17h.01"/>',
    info: '<circle cx="12" cy="12" r="8.5"/><path d="M12 11v5M12 8h.01"/>',
    close: '<path d="m7 7 10 10M17 7 7 17"/>',
    file: '<path d="M14 3.5H7A1.5 1.5 0 0 0 5.5 5v14A1.5 1.5 0 0 0 7 20.5h10a1.5 1.5 0 0 0 1.5-1.5V8Z"/><path d="M14 3.5V8h4.5"/>',
    check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
    chevron: '<path d="m8 10 4 4 4-4"/>',
  };
  const FIELD_LABELS = {to: 'To', cc: 'Cc', bcc: 'Bcc'};
  const EVENT_LABELS = {summary: 'Title', description: 'Description', location: 'Location', start: 'Start', end: 'End', attendees: 'Attendees', recurrence: 'Repeats'};
  const TARGET_COPY = {single: 'This event', instance: 'Only this occurrence', series: 'All events in the series'};

  // ---- State -----------------------------------------------------------
  let connections = {status: 'idle', configured: null, accounts: [], error: ''};
  let connectionsPromise = null, connectionsGen = 0;
  let chosen = '', gmailOn = false, calendarOn = false;
  let calendars = {account: '', items: [], next: null, status: 'idle', error: ''}, calendarGen = 0;
  const selectedCalendars = new Map();
  let pending = null, sheet = null, sheetOpener = null, disconnecting = false;
  const chats = new Map(), googleDataHints = new Map(), schedules = new Map(), silentRetries = new Set();
  let actionGeneration = 0, loadedKey = '', shownChat = '', expiryTimer = null, consentChat = null, controlsKey = '';

  // ---- Small helpers ---------------------------------------------------
  function node(tag, text, cls) {
    const el = document.createElement(tag);
    if (text) el.textContent = text;
    if (cls) el.className = cls;
    return el;
  }
  function svg(name, cls = 'agent-google-icon') {
    const holder = document.createElement('span');
    holder.innerHTML = `<svg class="${cls}" viewBox="0 0 24 24" aria-hidden="true" focusable="false">${ICONS[name]}</svg>`;
    return holder.firstChild;
  }
  function uid() { return window.auth?.currentUser?.uid || ''; }
  async function request(path, options = {}) {
    const user = window.auth?.currentUser;
    if (!user) throw new Error('Sign in to use Google data.');
    const token = await user.getIdToken();
    if (window.auth?.currentUser?.uid !== user.uid) throw new Error('Account changed.');
    const response = await fetch(path, {...options, headers: {Authorization: `Bearer ${token}`, ...options.headers}});
    if (window.auth?.currentUser?.uid !== user.uid) throw new Error('Account changed.');
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      const error = new Error(typeof data.detail === 'string' ? data.detail : data.error || 'The Google request failed. Please retry.');
      error.status = response.status;
      throw error;
    }
    return response;
  }
  const api = async (path, options) => (await request(path, options)).json();
  const post = (path, body) => api(path, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  function button(label, action, cls = '') {
    const el = node('button', label, `settings-inline-btn agent-google-btn${cls ? ' ' + cls : ''}`);
    el.type = 'button';
    if (action) el.addEventListener('click', async event => {
      if (el.getAttribute('aria-busy') === 'true') return;
      el.setAttribute('aria-busy', 'true'); el.disabled = true;
      // Synchronous until the action's first await, so popups stay user-initiated.
      try { await action(event); } catch (error) { App.showPopup?.(error.message); }
      finally { el.removeAttribute('aria-busy'); el.disabled = false; el._sync?.(); }
    });
    return el;
  }
  function checkbox(label, id, cls = '') {
    const row = node('label', '', cls), input = node('input'), text = node('span', label);
    input.type = 'checkbox'; if (id) input.id = id;
    row.append(input, text);
    return row;
  }
  function hint() {
    try { return JSON.parse(sessionStorage.getItem(`consens.googleHint.${uid()}`) || 'null'); } catch (_) { return null; }
  }
  function writeHint(value) {
    try { sessionStorage.setItem(`consens.googleHint.${uid()}`, JSON.stringify(value)); } catch (_) {}
  }
  function agentActive() {
    return Boolean(uid() && App.agentChat?.isSelected?.() && App.agentChat?.canUse?.() !== false);
  }
  function currentChatId() {
    const registry = App.runRegistry;
    const basis = registry?.getSelectedConversationBasis?.({includeHistory: false});
    if (basis?.chatId) return basis.chatId;
    const visible = registry?.visible?.();
    return visible?.config?.executionMode === 'agent' ? visible.metadata?.chatId || '' : '';
  }
  function chatUsesGoogle(chatId) {
    if (!chatId) return false;
    if (googleDataHints.has(chatId)) return googleDataHints.get(chatId);
    const basis = App.runRegistry?.getSelectedConversationBasis?.({includeHistory: false});
    return Boolean(basis?.chatId === chatId && basis.currentTurn?.agent_settings?.google_data);
  }
  function account() { return connections.accounts.find(item => item.id === chosen) || null; }
  function can(item, capability) { return Boolean(item?.capabilities?.includes(capability)); }
  function consentInput() { return document.getElementById('googleDataConsent'); }
  function consentGiven() { return consentInput()?.checked === true; }
  function sourcesOn() { return Boolean(chosen && (gmailOn || calendarOn)); }

  // ---- Selection and consent contract ----------------------------------
  function selectionProblem() {
    if (!sourcesOn()) return null;
    if (account() && account().status !== 'connected') {
      return {message: `Reconnect ${account().email} to use its Google data.`, action: 'google-open', label: 'Reconnect'};
    }
    if (calendarOn && !selectedCalendars.size) {
      return {message: 'Choose at least one calendar for this message.', action: 'google-open', label: 'Choose calendars'};
    }
    if (!consentGiven()) {
      return {message: 'Allow sharing the selected Google data with your models for this message.', action: 'google-consent', label: 'Allow for this message'};
    }
    return null;
  }
  function blocker() {
    if (!agentActive()) return null;
    const problem = selectionProblem();
    if (problem) return problem;
    if (!sourcesOn() && chatUsesGoogle(currentChatId()) && !consentGiven()) {
      return {message: 'This chat contains Google data. Allow sharing it with your models for this message.', action: 'google-consent', label: 'Allow for this message'};
    }
    return null;
  }
  // Never silently drop a visible choice: with a source on, sending needs a
  // complete, consented selection. blocker() explains the problem earlier.
  function selection() {
    const problem = blocker();
    if (problem) throw new Error(problem.message);
    if (!sourcesOn()) return null;
    return {connection_id: chosen, calendar: calendarOn, gmail: gmailOn,
      calendar_ids: calendarOn ? [...selectedCalendars.keys()] : [], consent: true};
  }
  function consent(value) {
    if (typeof value === 'boolean') {
      const box = consentInput();
      if (box && box.checked !== value) box.checked = value;
      changed();
    }
    return consentGiven();
  }
  function resetConsent() {
    const box = consentInput();
    if (box?.checked) { box.checked = false; changed(); }
  }
  function changed() {
    syncChips(); syncEntry();
    window.dispatchEvent(new CustomEvent('consensio:agent-google-change'));
    window.updateQuestionInputAccess?.();
  }
  function clearSelection() {
    chosen = ''; gmailOn = false; calendarOn = false; selectedCalendars.clear();
    calendars = {account: '', items: [], next: null, status: 'idle', error: ''}; calendarGen++;
  }
  function chooseAccount(id) {
    if (chosen === id) return;
    clearSelection(); chosen = id;
    const box = consentInput(); if (box) box.checked = false;
    changed();
  }
  function setGmail(on) {
    gmailOn = Boolean(on) && (can(account(), 'gmail_read') || can(account(), 'gmail_send'));
    changed();
  }
  function setCalendar(on) {
    calendarOn = Boolean(on && can(account(), 'calendar_read'));
    if (calendarOn && (calendars.account !== chosen || calendars.status === 'idle' || calendars.status === 'error')) loadCalendars();
    changed(); renderCalendarList();
  }

  // ---- Connections (loaded lazily on first use) ------------------------
  function loadConnections(force = false) {
    const owner = uid();
    if (!owner) return Promise.resolve();
    if (!force && connections.status === 'ready') return Promise.resolve();
    if (!force && connectionsPromise) return connectionsPromise;
    const seq = ++connectionsGen;
    connections = {...connections, status: connections.status === 'ready' ? 'refreshing' : 'loading', error: ''};
    renderSheet();
    const promise = (async () => {
      try {
        const result = await api('/agent/google/connections');
        if (seq !== connectionsGen || owner !== uid()) return;
        connections = {status: 'ready', configured: result.configured !== false, accounts: result.connections || [], error: ''};
        writeHint({configured: connections.configured, accounts: connections.accounts.length});
        if (chosen && !account()) clearSelection();
        if (!chosen) {
          const usable = connections.accounts.filter(item => item.status === 'connected');
          if (usable.length === 1) chosen = usable[0].id;
        }
        // A capability can disappear after reconnecting with fewer scopes.
        if (gmailOn && !can(account(), 'gmail_read') && !can(account(), 'gmail_send')) gmailOn = false;
        if (calendarOn && !can(account(), 'calendar_read')) calendarOn = false;
      } catch (error) {
        if (seq !== connectionsGen) return;
        connections = {...connections, status: connections.status === 'refreshing' ? 'ready' : 'error', error: error.message};
      } finally {
        if (seq === connectionsGen) { connectionsPromise = null; renderSheet(); changed(); }
      }
    })();
    connectionsPromise = promise;
    return promise;
  }
  // Must run synchronously inside the click that asked for it (popup blocker).
  function connect(capabilities, connectionId, after) {
    const popup = window.open('about:blank', 'consens-google', 'popup,width=540,height=720');
    if (!popup) throw new Error('Allow the connection window to open, then try again.');
    return (async () => {
      try {
        const result = await post('/agent/google/connect', {capabilities, connection_id: connectionId || null});
        pending = {state: result.state, uid: uid(), popup, after};
        popup.location.href = result.url;
      } catch (error) { popup.close(); throw error; }
    })();
  }
  window.addEventListener('message', async event => {
    if (!pending || event.origin !== location.origin || event.source !== pending.popup
      || event.data?.type !== 'consens-google-oauth' || event.data.state !== pending.state) return;
    const current = pending; pending = null;
    if (current.uid !== uid()) { current.popup.close(); return; }
    try {
      if (event.data.error || !event.data.code) throw new Error('Google authorization was not completed. No permissions were added.');
      await post('/agent/google/finish', {state: event.data.state, code: event.data.code});
      current.popup.close();
      await loadConnections(true);
      await current.after?.();
    } catch (error) { App.showPopup?.(error.message); }
  });
  async function loadCalendars(pageToken = '') {
    const owner = uid(), connection = chosen, seq = ++calendarGen;
    if (!pageToken) calendars = {account: connection, items: [], next: null, status: 'loading', error: ''};
    else calendars.status = 'loading-more';
    renderCalendarList();
    try {
      const result = await api(`/agent/google/connections/${connection}/calendars?page_token=${encodeURIComponent(pageToken)}`);
      if (seq !== calendarGen || owner !== uid() || connection !== chosen) return;
      calendars.items.push(...(result.calendars || []));
      calendars.next = result.next_page_token || null; calendars.status = 'ready';
    } catch (error) {
      if (seq !== calendarGen) return;
      calendars.status = 'error'; calendars.error = error.message;
    }
    renderCalendarList();
  }
  async function disconnect(item) {
    const result = await api(`/agent/google/connections/${item.id}`, {method: 'DELETE'});
    disconnecting = false;
    if (chosen === item.id) clearSelection();
    App.showPopup?.(result.notice);
    await loadConnections(true);
  }

  // ---- Composer entry points and chips ---------------------------------
  function ensureDom() {
    const input = document.getElementById('questionInput');
    if (input && !document.getElementById('agentGoogleChips')) {
      const row = node('div', '', 'agent-google-chips');
      row.id = 'agentGoogleChips'; row.hidden = true;
      row.setAttribute('role', 'group'); row.setAttribute('aria-label', 'Google data for this message');
      const list = node('div', '', 'agent-google-chip-list'); list.id = 'agentGoogleChipList';
      const consentRow = checkbox('Share with my models for this message', 'googleDataConsent', 'agent-google-consent');
      consentRow.title = 'Relevant Google excerpts and saved chat context go to your chosen models for this one message.';
      consentRow.querySelector('input').addEventListener('change', changed);
      row.append(list, consentRow);
      input.after(row);
    }
    const comparison = document.getElementById('agentComparisonMenuOption');
    if (comparison && !document.getElementById('agentGoogleMenuOption')) {
      const option = node('button', '', 'attach-menu-item agent-google-menu-option');
      option.type = 'button'; option.id = 'agentGoogleMenuOption'; option.hidden = true;
      option.setAttribute('aria-haspopup', 'dialog');
      const state = node('span', 'Off', 'agent-google-menu-state attach-menu-value'); state.id = 'agentGoogleMenuState';
      option.append(svg('google', ''), node('span', 'Google data', 'attach-menu-label'), state);
      option.addEventListener('click', event => { event.stopPropagation(); App.closeAttachMenu?.(); open(document.getElementById('attachTrigger')); });
      comparison.after(option);
    }
    const toolbar = document.querySelector('#composerModeBar .composer-mode-controls');
    if (toolbar && !document.getElementById('composerGoogleButton')) {
      const toggle = node('button', '', 'composer-agent-toggle composer-tool composer-google');
      toggle.type = 'button'; toggle.id = 'composerGoogleButton'; toggle.hidden = true;
      toggle.setAttribute('aria-haspopup', 'dialog');
      toggle.title = 'Google data · Use Gmail or Calendar for your next message';
      const state = node('span', 'Off', 'composer-agent-state composer-tool-label'); state.id = 'composerGoogleState';
      toggle.append(svg('google', ''), node('span', 'Google', 'composer-tool-label'), state);
      toggle.addEventListener('click', () => open(toggle));
      const models = document.getElementById('composerModelPicker');
      if (models?.parentNode === toolbar) models.before(toggle); else toolbar.append(toggle);
    }
  }
  function stateText() {
    if (!sourcesOn()) return 'Off';
    if (gmailOn && calendarOn) return 'Gmail, Calendar';
    return gmailOn ? 'Gmail' : 'Calendar';
  }
  function syncEntry() {
    const agent = agentActive(), known = connections.configured ?? hint()?.configured;
    const show = agent && known !== false;
    const option = document.getElementById('agentGoogleMenuOption');
    const toggle = document.getElementById('composerGoogleButton');
    for (const el of [option, toggle]) if (el && el.hidden === show) el.hidden = !show;
    const text = stateText(), label = `Google data: ${text === 'Off' ? 'off' : text}`;
    for (const id of ['agentGoogleMenuState', 'composerGoogleState']) {
      const el = document.getElementById(id);
      if (el && el.textContent !== text) el.textContent = text;
    }
    if (toggle && toggle.getAttribute('aria-label') !== label) toggle.setAttribute('aria-label', label);
    toggle?.classList.toggle('is-active', sourcesOn());
  }
  function chip(icon, text, onOpen, removeLabel, onRemove, tone = '') {
    const wrap = node('span', '', `agent-google-chip${tone ? ' ' + tone : ''}`);
    const main = node('button', '', 'settings-inline-btn agent-google-chip-main'); main.type = 'button';
    main.append(svg(icon), node('span', text, 'agent-google-chip-text'));
    main.addEventListener('click', () => onOpen(main));
    wrap.append(main);
    if (onRemove) {
      const remove = node('button', '', 'settings-inline-btn agent-google-chip-remove'); remove.type = 'button';
      remove.setAttribute('aria-label', removeLabel); remove.title = removeLabel;
      remove.append(svg('close'));
      remove.addEventListener('click', onRemove);
      wrap.append(remove);
    }
    return wrap;
  }
  function syncChips() {
    const row = document.getElementById('agentGoogleChips'), list = document.getElementById('agentGoogleChipList');
    if (!row || !list) return;
    const agent = agentActive(), chatId = currentChatId();
    const chatGoogle = chatUsesGoogle(chatId);
    const show = agent && (sourcesOn() || chatGoogle);
    const email = account()?.email || '';
    const key = JSON.stringify([show, gmailOn, calendarOn, email, [...selectedCalendars.values()], chatGoogle, sourcesOn()]);
    if (row.dataset.key !== key) {
      row.dataset.key = key;
      const chips = [];
      if (show && gmailOn) chips.push(chip('mail', `Gmail · ${email}`, open, 'Stop using Gmail for this message', () => setGmail(false)));
      if (show && calendarOn) {
        const names = [...selectedCalendars.values()];
        const text = !names.length ? 'Calendar · choose calendars' : names.length === 1 ? `Calendar · ${names[0]}` : `${names.length} calendars`;
        chips.push(chip('calendar', text, open, 'Stop using calendars for this message', () => setCalendar(false), names.length ? '' : 'is-incomplete'));
      }
      if (show && !sourcesOn() && chatGoogle) chips.push(chip('google', 'This chat contains Google data', open, '', null, 'is-info'));
      list.replaceChildren(...chips);
    }
    if (row.hidden === show) row.hidden = !show;
    // Consent never outlives the context it was given for.
    const box = consentInput();
    if (box && (!show || consentChat !== null && consentChat !== chatId) && box.checked) box.checked = false;
    consentChat = chatId;
  }
  // Cheap re-projection; never loads connections by itself. A changed chat
  // (switch, restore, new chat) also projects that chat's action cards, so
  // this module does not depend on other modules to load them.
  function refreshControls(force = false) {
    ensureDom();
    const agent = agentActive(), chatId = currentChatId();
    const key = `${agent}:${uid()}:${chatId}`;
    if (key !== controlsKey || force) {
      controlsKey = key;
      if (!agent && sheet && !sheet.hidden) closeSheet();
      syncEntry(); syncChips();
      if (chatId !== shownChat || !agent) refreshActions(agent ? chatId : '');
    }
    if (force && connections.status !== 'idle') loadConnections(true);
  }

  // ---- Google data sheet -----------------------------------------------
  function ensureSheet() {
    if (sheet) return sheet;
    sheet = node('div', '', 'agent-google-overlay'); sheet.id = 'agentGoogleSheet'; sheet.hidden = true;
    const dialog = node('section', '', 'agent-google-sheet');
    dialog.setAttribute('role', 'dialog'); dialog.setAttribute('aria-modal', 'true');
    dialog.setAttribute('aria-labelledby', 'agentGoogleSheetTitle'); dialog.setAttribute('aria-describedby', 'agentGoogleSheetIntro');
    const head = node('header', '', 'agent-google-sheet-head');
    const title = node('h2', 'Google data for this message'); title.id = 'agentGoogleSheetTitle';
    const close = node('button', '', 'settings-inline-btn agent-google-close'); close.type = 'button';
    close.setAttribute('aria-label', 'Close Google data'); close.append(svg('close'));
    close.addEventListener('click', closeSheet);
    head.append(title, close);
    const body = node('div', '', 'agent-google-sheet-body'); body.id = 'agentGoogleSheetBody';
    const foot = node('footer', '', 'agent-google-sheet-foot');
    foot.append(button('Done', closeSheet, 'is-primary'));
    dialog.append(head, body, foot);
    sheet.append(dialog);
    sheet.addEventListener('mousedown', event => { if (event.target === sheet) closeSheet(); });
    sheet.addEventListener('keydown', event => {
      if (event.key === 'Escape') { event.stopPropagation(); event.preventDefault(); closeSheet(); return; }
      if (event.key !== 'Tab') return;
      const items = [...dialog.querySelectorAll('button, input, a[href], select, summary, [tabindex="0"]')]
        .filter(el => !el.disabled && el.getClientRects().length);
      if (!items.length) return;
      const first = items[0], last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    });
    document.body.append(sheet);
    return sheet;
  }
  function open(opener) {
    if (!agentActive()) return;
    ensureSheet();
    sheetOpener = opener instanceof Element ? opener : document.activeElement;
    sheet.hidden = false;
    document.body.classList.add('agent-google-sheet-open');
    renderSheet();
    loadConnections();
    requestAnimationFrame(() => {
      const target = [...sheet.querySelectorAll('.agent-google-sheet-body input, .agent-google-sheet-body button')].find(el => !el.disabled)
        || sheet.querySelector('.agent-google-close');
      target?.focus({preventScroll: true});
    });
  }
  function closeSheet() {
    if (!sheet || sheet.hidden) return;
    sheet.hidden = true; disconnecting = false;
    document.body.classList.remove('agent-google-sheet-open');
    const visible = el => el && el.isConnected && el.getClientRects().length;
    const target = [sheetOpener, document.getElementById('attachTrigger'), document.getElementById('questionInput')].find(visible);
    target?.focus({preventScroll: true});
    sheetOpener = null;
  }
  function notice(text, tone, retry) {
    const box = node('div', '', `agent-google-notice${tone ? ' is-' + tone : ''}`);
    box.setAttribute('role', tone === 'error' ? 'alert' : 'status');
    box.append(svg(tone === 'error' ? 'warning' : 'info'), node('span', text));
    if (retry) box.append(button('Retry', retry, 'is-link'));
    return box;
  }
  function capabilityRow(item, label, capability) {
    const row = node('li', '', 'agent-google-cap');
    row.append(node('span', label, 'agent-google-cap-label'));
    if (can(item, capability)) {
      const state = node('span', '', 'agent-google-cap-state'); state.append(svg('check'), node('span', 'Allowed'));
      row.append(state);
    } else {
      const allow = button('Allow', () => connect([capability], item.id), 'is-small');
      allow.setAttribute('aria-label', `Allow: ${label}`);
      row.append(allow);
    }
    return row;
  }
  function sourceSection(item, kind) {
    const gmail = kind === 'gmail';
    const section = node('section', '', 'agent-google-source');
    const enabled = gmail ? can(item, 'gmail_read') || can(item, 'gmail_send') : can(item, 'calendar_read');
    const toggle = checkbox(gmail ? 'Use Gmail for this message' : 'Use selected calendars', gmail ? 'googleGmailEnabled' : 'googleCalendarEnabled', 'agent-google-switch');
    const input = toggle.querySelector('input');
    input.checked = gmail ? gmailOn : calendarOn; input.disabled = !enabled;
    input.setAttribute('role', 'switch');
    input.setAttribute('aria-label', gmail ? 'Use Gmail for this message' : 'Use selected calendars');
    const sub = node('small', !enabled ? `Allow ${gmail ? 'reading emails' : 'reading calendars'} first.`
      : gmail ? 'Searches and reads only emails relevant to your request.' : `Choose up to ${MAX_CALENDARS} calendars below.`);
    toggle.querySelector('span').append(sub);
    toggle.prepend(svg(gmail ? 'mail' : 'calendar', 'agent-google-icon agent-google-source-icon'));
    input.addEventListener('change', () => gmail ? setGmail(input.checked) : setCalendar(input.checked));
    section.append(toggle);
    if (!gmail) { const list = node('div', '', 'google-calendar-list'); list.id = 'agentGoogleCalendarList'; section.append(list); }
    const caps = node('ul', '', 'agent-google-caps');
    if (gmail) caps.append(capabilityRow(item, 'Read emails', 'gmail_read'), capabilityRow(item, 'Send emails you confirm', 'gmail_send'));
    else caps.append(capabilityRow(item, 'Read calendars', 'calendar_read'), capabilityRow(item, 'Create and edit events you confirm', 'calendar_write'));
    section.append(caps);
    return section;
  }
  function renderCalendarList() {
    const list = document.getElementById('agentGoogleCalendarList');
    if (!list) return;
    list.hidden = !calendarOn;
    if (!calendarOn) { list.replaceChildren(); return; }
    const focused = list.contains(document.activeElement) ? document.activeElement.id : '';
    const children = [];
    if (calendars.status === 'loading') children.push(node('p', 'Loading calendars…', 'agent-google-muted'));
    if (calendars.status === 'error') children.push(notice(`Couldn't load calendars. ${calendars.error}`, 'error', () => loadCalendars()));
    if (calendars.status === 'ready' && !calendars.items.length) children.push(node('p', 'No calendars found for this account.', 'agent-google-muted'));
    calendars.items.forEach((item, index) => {
      const name = item.summary || item.id;
      const row = checkbox(name, `calendar-${index}`, 'agent-google-check');
      if (item.timeZone) row.querySelector('span').append(node('small', item.primary ? `Primary · ${item.timeZone}` : item.timeZone));
      const input = row.querySelector('input');
      input.value = item.id; input.checked = selectedCalendars.has(item.id);
      input.setAttribute('aria-label', `${name} · ${item.timeZone || 'UTC'}`);
      input.addEventListener('change', () => {
        if (input.checked) {
          if (selectedCalendars.size >= MAX_CALENDARS) { input.checked = false; App.showPopup?.(`Select up to ${MAX_CALENDARS} calendars.`); return; }
          selectedCalendars.set(item.id, name);
        } else selectedCalendars.delete(item.id);
        changed();
      });
      children.push(row);
    });
    if (calendars.next) {
      const more = button(calendars.status === 'loading-more' ? 'Loading…' : 'More calendars', () => loadCalendars(calendars.next), 'is-link google-more');
      children.push(more);
    }
    list.replaceChildren(...children);
    if (focused) document.getElementById(focused)?.focus({preventScroll: true});
  }
  function renderSheet() {
    if (!sheet || sheet.hidden) return;
    const body = document.getElementById('agentGoogleSheetBody');
    const focused = sheet.contains(document.activeElement) ? document.activeElement.id : '';
    const children = [];
    const points = node('ul', '', 'agent-google-points'); points.id = 'agentGoogleSheetIntro';
    for (const [icon, text] of [['google', 'Reads only the calendars and emails that are relevant to your request.'],
      ['info', 'Relevant excerpts go to your chosen models, including comparison and review models. Only approved providers are used, and web search is off in these chats.'],
      ['check', 'Nothing is sent or changed in Google without your explicit confirmation.']]) {
      const item = node('li'); item.append(svg(icon), node('span', text)); points.append(item);
    }
    const details = node('a', 'Privacy details', 'agent-google-link'); details.href = '/privacy'; details.target = '_blank'; details.rel = 'noopener';
    children.push(points, details);
    const status = connections.status;
    if (status === 'idle' || status === 'loading') children.push(node('p', 'Loading Google accounts…', 'agent-google-muted'));
    else if (status === 'error') children.push(notice(`Couldn't load Google accounts. ${connections.error}`, 'error', () => loadConnections(true)));
    else if (!connections.configured) children.push(notice('Google data is not available on this installation.', 'info'));
    else if (!connections.accounts.length) {
      const empty = node('section', '', 'agent-google-empty');
      empty.append(node('h3', 'Connect a Google account'), node('p', 'Choose what Consens may read. You can add more permissions later.', 'agent-google-muted'));
      const actions = node('div', '', 'agent-google-row');
      actions.append(button('Connect Gmail', () => connect(['gmail_read']), 'is-primary'), button('Connect Google Calendar', () => connect(['calendar_read'])));
      empty.append(actions); children.push(empty);
    } else {
      const group = node('fieldset', '', 'agent-google-accounts');
      group.append(node('legend', 'Account'));
      for (const item of connections.accounts) {
        const row = node('label', '', 'agent-google-account'), radio = node('input');
        radio.type = 'radio'; radio.name = 'agentGoogleAccount'; radio.value = item.id; radio.id = `googleAccount-${item.id}`;
        radio.checked = item.id === chosen;
        radio.addEventListener('change', () => { if (radio.checked) { chooseAccount(item.id); renderSheet(); } });
        const text = node('span', '', 'agent-google-account-text');
        text.append(node('span', item.email, 'agent-google-account-email'),
          node('small', item.status === 'connected' ? 'Connected' : 'Needs reconnection', item.status === 'connected' ? '' : 'is-warning'));
        row.append(radio, text); group.append(row);
      }
      children.push(group);
      const item = account();
      if (item && item.status !== 'connected') {
        const box = notice(`Reconnect ${item.email} to use it again.`, 'error');
        box.append(button('Reconnect', () => connect(item.capabilities?.length ? item.capabilities : ['gmail_read'], item.id), 'is-small'));
        children.push(box);
      } else if (item) {
        children.push(sourceSection(item, 'gmail'), sourceSection(item, 'calendar'));
      } else children.push(node('p', 'Choose the account to use for this message.', 'agent-google-muted'));
      const more = node('details', '', 'agent-google-more');
      more.append(node('summary', 'Account options'));
      const inner = node('div', '', 'agent-google-more-body');
      const add = node('div', '', 'agent-google-row');
      add.append(node('span', 'Add another account:', 'agent-google-muted'), button('Gmail', () => connect(['gmail_read']), 'is-link'), button('Google Calendar', () => connect(['calendar_read']), 'is-link'));
      inner.append(add);
      const manage = node('a', 'Manage Google access', 'agent-google-link');
      manage.href = 'https://myaccount.google.com/permissions'; manage.target = '_blank'; manage.rel = 'noopener noreferrer';
      inner.append(manage);
      if (item) {
        if (disconnecting) {
          const confirmBox = node('div', '', 'agent-google-confirm');
          confirmBox.append(node('p', `Disconnect ${item.email}? Consens deletes its stored access. Drafts and changes for this account can no longer be confirmed.`));
          const row = node('div', '', 'agent-google-row');
          row.append(button('Disconnect', () => disconnect(item), 'is-danger'), button('Cancel', () => { disconnecting = false; renderSheet(); }));
          confirmBox.append(row); inner.append(confirmBox);
        } else inner.append(button(`Disconnect ${item.email}…`, () => { disconnecting = true; renderSheet(); document.querySelector('.agent-google-confirm .is-danger')?.focus(); }, 'is-link is-danger'));
      }
      more.append(inner);
      if (disconnecting) more.open = true;
      children.push(more);
    }
    body.replaceChildren(...children);
    renderCalendarList();
    if (focused) document.getElementById(focused)?.focus({preventScroll: true});
  }

  // ---- Action cards ----------------------------------------------------
  function valueText(value) {
    if (value === undefined || value === null) return '—';
    if (Array.isArray(value)) return value.map(item => typeof item === 'object' ? item.email || JSON.stringify(item) : item).join('\n') || 'None';
    if (typeof value === 'object') {
      if (value.date) return `${value.date} (all day; end date is exclusive)`;
      if (value.dateTime) {
        try {
          return `${new Date(value.dateTime).toLocaleString(undefined, {timeZone: value.timeZone || 'UTC', dateStyle: 'medium', timeStyle: 'short'})} · ${value.timeZone || 'UTC'} (${value.dateTime.match(/(Z|[+-]\d\d:\d\d)$/)?.[0] || ''})`;
        } catch (_) { return `${value.dateTime} ${value.timeZone || ''}`; }
      }
      return '';
    }
    return String(value);
  }
  function when(value) {
    if (!value) return '';
    try {
      if (value.date) return new Date(`${value.date}T12:00:00Z`).toLocaleDateString(undefined, {timeZone: 'UTC', weekday: 'short', day: 'numeric', month: 'short'});
      return new Date(value.dateTime).toLocaleString(undefined, {timeZone: value.timeZone || 'UTC', weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit'});
    } catch (_) { return value.dateTime || value.date || ''; }
  }
  function expired(action) { return action.status === 'pending' && Date.parse(action.approval_until) <= Date.now(); }
  function status(action) { return expired(action) ? 'expired' : action.status; }
  function badge(action) {
    const state = status(action), preview = action.preview || {};
    const done = action.kind === 'gmail_send' ? 'Sent' : preview.operation === 'Create event' ? 'Created' : 'Updated';
    const labels = {pending: 'Needs review', executing: 'In progress', succeeded: done, unknown: 'Result unknown', failed: 'Failed',
      rejected: 'Discarded', superseded: 'Replaced by newer version', expired: 'Expired'};
    return labels[state] || state;
  }
  function title(action) {
    const preview = action.preview || {};
    if (action.kind === 'gmail_send') {
      const all = [...(preview.to || []), ...(preview.cc || []), ...(preview.bcc || [])];
      const others = all.length - 1;
      return `Send email to ${preview.to?.[0] || 'recipients'}${others > 0 ? ` and ${others} other${others === 1 ? '' : 's'}` : ''}`;
    }
    const before = preview.before || {}, after = preview.after || {};
    const name = after.summary || before.summary || 'event';
    if (preview.operation === 'Create event') return `Create “${name}”${after.start ? ` on ${when(after.start)}` : ''}`;
    if (after.start && valueText(before.start) !== valueText(after.start)) return `Move “${before.summary || name}” to ${when(after.start)}`;
    return `Update “${name}”`;
  }
  function field(list, label, content) {
    const term = node('dt', label), value = node('dd');
    if (content instanceof Node) value.append(content); else value.textContent = content;
    list.append(term, value);
  }
  function recipients(addresses, flagged) {
    const wrap = node('span', '', 'agent-recipients');
    addresses.forEach((email, index) => {
      if (index) wrap.append(document.createTextNode(', '));
      if (flagged.has(email.toLowerCase())) {
        const mark = node('mark', '', 'agent-recipient-flag');
        mark.title = 'Not named by you in this chat';
        mark.append(svg('warning'), node('span', email));
        wrap.append(mark);
      } else wrap.append(node('span', email));
    });
    return wrap;
  }
  function mailBody(action, chatId, card, controls) {
    const preview = action.preview, parts = [];
    const warnings = preview.recipient_warnings || [];
    const flagged = new Set(warnings.map(item => String(item.email).toLowerCase()));
    const live = ['pending', 'expired'].includes(status(action));
    if (warnings.length && live) {
      const alert = node('div', '', 'agent-action-alert agent-recipient-warning');
      alert.setAttribute('role', 'alert');
      const text = node('div', '', 'agent-action-alert-text');
      text.append(node('strong', 'Check these recipients before sending'),
        node('p', 'You didn’t name them in this chat and they aren’t part of the replied conversation. An instruction hidden in an email or file can add recipients like these.'));
      const list = node('ul', '', 'agent-recipient-acks');
      const confirmable = controls.confirmable;
      for (const item of warnings) {
        const row = node('li');
        const label = `${item.email} (${FIELD_LABELS[item.field] || item.field})`;
        if (confirmable) {
          const ack = checkbox(`Send to ${label}`, '', 'agent-recipient-ack');
          ack.querySelector('input').dataset.email = item.email;
          ack.querySelector('input').addEventListener('change', () => card._sync?.());
          row.append(ack);
        } else row.append(node('span', label, 'agent-recipient-ack-text'));
        const onlyTo = item.field === 'to' && (preview.to || []).length <= 1;
        if (!onlyTo && ['pending', 'expired', 'failed', 'rejected'].includes(action.status)) {
          const remove = button('Remove recipient', () => renew(action, chatId, [item.email]), 'is-link');
          remove.setAttribute('aria-label', `Remove ${item.email} and prepare the email again`);
          row.append(remove);
        }
        list.append(row);
      }
      text.append(list); alert.append(svg('warning'), text);
      parts.push(alert);
    }
    const fields = node('dl', '', 'agent-action-fields');
    field(fields, 'From', preview.from || action.account || '');
    for (const key of ['to', 'cc', 'bcc']) {
      const values = preview[key] || [];
      if (key === 'to' || values.length) field(fields, FIELD_LABELS[key], values.length ? recipients(values, flagged) : 'None');
    }
    field(fields, 'Subject', preview.subject || '');
    if (preview.reply) field(fields, 'Reply to', `${preview.reply.from || ''} · “${preview.reply.subject || ''}”`);
    parts.push(fields);
    parts.push(node('pre', preview.body || '', 'agent-mail-body'));
    const files = preview.attachments || [];
    if (files.length) {
      const box = node('div', '', 'agent-action-files');
      box.append(node('h4', `Attachments (${files.length})`));
      const list = node('ul');
      for (const file of files) {
        const row = node('li', '', 'agent-action-file');
        row.append(svg('file'), node('span', file.name, 'agent-action-file-name'), node('span', `${Math.ceil((file.size || 0) / 1024)} KB`, 'agent-google-muted'));
        const review = button('Review', () => download(chatId, file), 'is-link');
        review.setAttribute('aria-label', `Review attachment ${file.name}`);
        row.append(review); list.append(row);
      }
      box.append(list); parts.push(box);
    }
    if (preview.draft_location) parts.push(node('p', preview.draft_location, 'agent-action-note'));
    return parts;
  }
  function calendarBody(action) {
    const preview = action.preview, parts = [];
    const creating = preview.operation === 'Create event' || !Object.keys(preview.before || {}).length;
    const fields = node('dl', '', 'agent-action-fields');
    field(fields, 'Calendar', preview.calendar_name || (preview.calendar === 'primary' ? 'Primary calendar' : preview.calendar || ''));
    if (!creating) field(fields, 'Applies to', TARGET_COPY[preview.target] || preview.target || '');
    parts.push(fields);
    const table = node('table', '', `agent-action-diff${creating ? ' is-new' : ''}`);
    const head = node('tr');
    for (const text of creating ? ['Field', 'Value'] : ['Field', 'Current', 'Proposed']) head.append(node('th', text));
    const thead = node('thead'); thead.append(head);
    const tbody = node('tbody'); let unchanged = 0;
    for (const key of Object.keys(EVENT_LABELS)) {
      const before = (preview.before || {})[key], after = (preview.after || {})[key];
      if (before === undefined && after === undefined) continue;
      const row = node('tr'), label = node('th', EVENT_LABELS[key]); label.scope = 'row';
      if (creating) {
        const value = node('td', valueText(after)); value.dataset.label = 'Value';
        row.append(label, value);
      } else {
        const changedRow = valueText(before) !== valueText(after);
        const old = node('td', before === undefined ? 'Not set' : valueText(before), 'agent-diff-old'), next = node('td', valueText(after), 'agent-diff-new');
        old.dataset.label = 'Was'; next.dataset.label = 'Proposed';
        row.append(label, old, next);
        if (changedRow) row.dataset.changed = 'true';
        else { row.hidden = true; row.classList.add('is-unchanged'); unchanged++; }
      }
      tbody.append(row);
    }
    table.append(thead, tbody);
    parts.push(table);
    if (unchanged) {
      const toggle = button(`Show unchanged fields (${unchanged})`, () => {
        const show = toggle.getAttribute('aria-expanded') !== 'true';
        tbody.querySelectorAll('.is-unchanged').forEach(row => { row.hidden = !show; });
        toggle.setAttribute('aria-expanded', String(show));
        toggle.textContent = show ? 'Hide unchanged fields' : `Show unchanged fields (${unchanged})`;
      }, 'is-link');
      toggle.setAttribute('aria-expanded', 'false');
      parts.push(toggle);
    }
    if (preview.invitations) parts.push(node('p', preview.invitations, 'agent-action-note'));
    parts.push(node('p', `Affected attendees: ${(preview.attendees || []).join(', ') || 'None'}`, 'agent-action-note'));
    return parts;
  }
  function technical(action) {
    const preview = action.preview || {};
    const box = node('details', '', 'agent-action-tech');
    box.append(node('summary', 'Technical details'));
    const list = node('dl', '', 'agent-action-fields');
    field(list, 'Account', action.account || '');
    field(list, 'Action', action.id);
    field(list, 'Content hash', `${String(action.hash || '').slice(0, 16)}…`);
    if (action.kind === 'calendar_event') {
      field(list, 'Calendar ID', preview.calendar || '');
      field(list, 'Target', preview.target || '');
    }
    if (preview.reply) { field(list, 'Reply message', preview.reply.message_id || ''); field(list, 'Thread', preview.reply.thread_id || ''); }
    if (action.created_at) field(list, 'Prepared', new Date(action.created_at).toLocaleString());
    if (action.approval_until) field(list, 'Approval until', new Date(action.approval_until).toLocaleString());
    box.append(list);
    return box;
  }
  function expiryText(action) {
    const until = Date.parse(action.approval_until), minutes = Math.ceil((until - Date.now()) / 60000);
    if (!Number.isFinite(minutes)) return '';
    if (minutes > 60) return `Confirm by ${new Date(until).toLocaleString(undefined, {dateStyle: 'medium', timeStyle: 'short'})}`;
    return minutes <= 1 ? 'Confirm within a minute' : `Confirm within ${minutes} min`;
  }
  async function afterChange(chatId, focusId) {
    if (currentChat() === chatId) await refreshActions(chatId, true);
    if (focusId) document.querySelector(`#agentGoogleActions [data-action-id="${focusId}"] .agent-action-title`)?.focus({preventScroll: false});
  }
  function currentChat() { return shownChat; }
  async function renew(action, chatId, remove = []) {
    const result = await post(`/agent/chats/${chatId}/actions/${action.id}/renew`, {expected_hash: action.hash, remove_recipients: remove});
    await afterChange(chatId, result.action?.id);
  }
  async function download(chatId, file) {
    if (App.agentWorkspace?.download) return App.agentWorkspace.download(chatId, file);
    const response = await request(`/agent/chats/${chatId}/files/${file.id}`);
    const url = URL.createObjectURL(await response.blob()), link = document.createElement('a');
    link.href = url; link.download = file.name; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
  }
  function controlsFor(action, chatId, card) {
    const state = status(action), preview = action.preview || {};
    const box = node('div', '', 'agent-action-controls');
    const confirmable = state === 'pending' && preview.send_authorized !== false;
    if (confirmable) {
      const review = checkbox('I have reviewed this exact change and its recipients.', `approve-${action.id}`, 'agent-action-review');
      const verb = action.kind === 'gmail_send' ? 'Send email' : preview.operation === 'Create event' ? 'Create event' : 'Update event';
      const confirm = button(verb, async () => {
        if (!card._ready()) return;
        await post(`/agent/chats/${chatId}/actions/${action.id}/confirm`, {expected_hash: action.hash});
        await afterChange(chatId, action.id);
      }, 'is-primary agent-action-confirm');
      const discard = button('Discard', async () => {
        await post(`/agent/chats/${chatId}/actions/${action.id}/reject`, {expected_hash: action.hash});
        await afterChange(chatId, action.id);
      });
      const why = node('p', '', 'agent-action-hint'); why.hidden = true; why.id = `approve-hint-${action.id}`;
      const expiry = node('p', expiryText(action), 'agent-action-expiry');
      card._ready = () => {
        const acks = [...card.querySelectorAll('.agent-recipient-ack input')];
        return review.querySelector('input').checked && acks.every(input => input.checked) && !expired(action);
      };
      card._sync = () => {
        const acks = [...card.querySelectorAll('.agent-recipient-ack input')];
        const waiting = acks.filter(input => !input.checked).length;
        confirm.disabled = !card._ready();
        why.hidden = !(review.querySelector('input').checked && waiting);
        why.textContent = waiting ? `Confirm ${waiting === 1 ? 'the flagged recipient' : `all ${waiting} flagged recipients`} above first.` : '';
        if (why.hidden) confirm.removeAttribute('aria-describedby'); else confirm.setAttribute('aria-describedby', why.id);
        expiry.textContent = expiryText(action);
      };
      confirm._sync = card._sync;
      review.querySelector('input').addEventListener('change', card._sync);
      const buttons = node('div', '', 'agent-action-buttons'); buttons.append(confirm, discard);
      box.append(review, buttons, why, expiry);
      box.confirmable = true;
      return box;
    }
    if (state === 'pending') {
      const allow = button(`Allow sending from ${action.account}`, () => connect(['gmail_send'], action.connection_id,
        () => renew(action, chatId)), 'is-primary');
      const discard = button('Discard', async () => {
        await post(`/agent/chats/${chatId}/actions/${action.id}/reject`, {expected_hash: action.hash});
        await afterChange(chatId, action.id);
      });
      const text = node('div', '', 'agent-action-callout');
      text.append(svg('info'), node('p', `Sending from ${action.account} isn’t allowed yet. Allow it once; this exact draft is then prepared again for your review.`));
      const buttons = node('div', '', 'agent-action-buttons'); buttons.append(allow, discard);
      box.append(text, buttons);
      return box;
    }
    if (state === 'expired' || state === 'failed') {
      if (state === 'expired') box.append(node('p', 'This approval expired after 30 minutes. Prepare it again to review the same content.', 'agent-action-note'));
      const again = button('Prepare again', () => renew(action, chatId), state === 'expired' ? 'is-primary' : '');
      const buttons = node('div', '', 'agent-action-buttons'); buttons.append(again);
      if (state === 'expired') buttons.append(button('Discard', async () => {
        await post(`/agent/chats/${chatId}/actions/${action.id}/reject`, {expected_hash: action.hash});
        await afterChange(chatId, action.id);
      }));
      box.append(buttons);
      return box;
    }
    if (['unknown', 'executing'].includes(state)) {
      box.append(node('p', 'The result is not yet confirmed. Checking status never repeats the write.', 'agent-action-note'),
        button('Check action status', async () => {
          await post(`/agent/chats/${chatId}/actions/${action.id}/status`, {});
          await afterChange(chatId, action.id);
        }));
      return box;
    }
    return null;
  }
  function signature(action) {
    return JSON.stringify([action.id, action.hash, action.status, action.approval_until, action.error, action.result, expired(action)]);
  }
  function card(action, chatId, {compact = false} = {}) {
    const state = status(action);
    const el = node('article', '', `agent-action-card${compact ? ' is-compact' : ''}`);
    el.dataset.status = state; el.dataset.kind = action.kind; el.dataset.actionId = action.id; el.dataset.signature = signature(action);
    const head = node('header', '', 'agent-action-head');
    const heading = node('div', '', 'agent-action-heading');
    const titleEl = node('h3', title(action), 'agent-action-title'); titleEl.tabIndex = -1;
    const meta = [action.account, action.kind === 'gmail_send' ? 'Gmail' : 'Google Calendar'].filter(Boolean).join(' · ');
    heading.append(titleEl, node('p', meta, 'agent-action-meta'));
    const badgeEl = node('span', badge(action), 'agent-action-badge'); badgeEl.dataset.tone = state;
    head.append(svg(action.kind === 'gmail_send' ? 'mail' : 'calendar', 'agent-google-icon agent-action-icon'), heading, badgeEl);
    const body = node('div', '', 'agent-action-body'); body.id = `action-body-${action.id}${compact ? '-old' : ''}`;
    const collapsible = compact || ['succeeded', 'rejected', 'superseded'].includes(state);
    if (collapsible) {
      const toggle = node('button', '', 'settings-inline-btn agent-action-toggle'); toggle.type = 'button';
      toggle.setAttribute('aria-expanded', 'false'); toggle.setAttribute('aria-controls', body.id);
      toggle.setAttribute('aria-label', `Show details: ${title(action)}`);
      toggle.append(svg('chevron'));
      toggle.addEventListener('click', () => {
        const openNow = toggle.getAttribute('aria-expanded') !== 'true';
        toggle.setAttribute('aria-expanded', String(openNow)); body.hidden = !openNow;
        toggle.setAttribute('aria-label', `${openNow ? 'Hide' : 'Show'} details: ${title(action)}`);
      });
      head.append(toggle); body.hidden = true;
    }
    el.append(head);
    const controls = compact ? null : controlsFor(action, chatId, el);
    const content = action.kind === 'gmail_send' ? mailBody(action, chatId, el, {confirmable: Boolean(controls?.confirmable)})
      : action.kind === 'calendar_event' ? calendarBody(action) : [];
    if (action.error) {
      const error = node('div', '', 'agent-action-callout is-error agent-action-error');
      error.setAttribute('role', 'status'); error.append(svg('warning'), node('p', action.error));
      body.append(error);
    }
    body.append(...content);
    if (action.status === 'succeeded') {
      const ok = node('p', '', 'agent-action-success'); ok.append(svg('check'), node('span', 'Google confirmed this action.'));
      body.append(ok);
      const link = action.result?.link;
      if (typeof link === 'string' && /^https:\/\/(calendar|www)\.google\.com\//.test(link)) {
        const a = node('a', 'Open in Google Calendar', 'agent-google-link'); a.href = link; a.target = '_blank'; a.rel = 'noopener noreferrer';
        body.append(a);
      }
    }
    if (action.result?.warning) body.append(node('p', action.result.warning, 'agent-action-note'));
    body.append(technical(action));
    el.append(body);
    if (controls) { el.append(controls); el._sync?.(); }
    return el;
  }
  function chains(actions) {
    const byId = new Map(actions.map(action => [action.id, action]));
    const replaced = new Set(actions.map(action => action.replaces).filter(id => id && byId.has(id)));
    return actions.filter(action => !replaced.has(action.id)).map(head => {
      const earlier = [];
      let cursor = byId.get(head.replaces), guard = 0;
      while (cursor && guard++ < 100) { earlier.push(cursor); cursor = byId.get(cursor.replaces); }
      return {head, earlier};
    });
  }
  function pendingCount(chatId) {
    const data = chats.get(chatId || shownChat);
    if (!data) return 0;
    return chains(data.actions).filter(({head}) => status(head) === 'pending').length;
  }
  function evidenceFor(messageId) {
    const lists = [chats.get(shownChat)?.evidence || [], ...[...chats.values()].map(data => data.evidence || [])];
    for (const list of lists) {
      const item = list.find(entry => entry.message_id === messageId);
      if (item) return {subject: item.headers?.subject || '', from: item.headers?.from || ''};
    }
    return null;
  }
  function host() {
    let panel = document.getElementById('agentGoogleActions');
    if (!panel) {
      const answer = document.getElementById('agentAnswer');
      if (!answer) return null;
      panel = node('section', '', 'agent-google-actions');
      panel.id = 'agentGoogleActions'; panel.hidden = true;
      panel.setAttribute('aria-label', 'Email and calendar actions');
      answer.after(panel);
    }
    return panel;
  }
  function evidenceList(evidence) {
    const box = node('details', '', 'agent-google-evidence');
    box.append(node('summary', `Referenced emails (${evidence.length})`));
    const list = node('ul');
    let offset = 0;
    const more = button('Show more emails', () => show(), 'is-link');
    function show() {
      more.remove();
      for (const item of evidence.slice(offset, offset + 10)) {
        const row = node('li', '', 'agent-evidence-mail');
        const headers = item.headers || {};
        row.append(svg('mail'));
        const text = node('div');
        text.append(node('strong', headers.subject || '(no subject)'));
        text.append(node('p', [headers.from, headers.date].filter(Boolean).join(' · '), 'agent-google-muted'));
        const to = [headers.to && `To: ${headers.to}`, headers.cc && `Cc: ${headers.cc}`].filter(Boolean).join(' · ');
        if (to) text.append(node('p', to, 'agent-google-muted'));
        text.append(node('p', `Account: ${item.account || ''}`, 'agent-google-muted'));
        row.append(text); list.append(row);
      }
      offset += 10;
      if (offset < evidence.length) box.append(more);
    }
    box.append(list); show();
    return box;
  }
  function renderActions(chatId) {
    const panel = host(), data = chats.get(chatId);
    if (!panel || !data) return;
    const previous = new Map([...panel.querySelectorAll(':scope > .agent-action-card')].map(el => [el.dataset.signature, el]));
    const children = [];
    for (const {head, earlier} of chains(data.actions)) {
      // Keep a live card (and its review state) only while its content is unchanged.
      const reused = previous.get(signature(head));
      children.push(reused || card(head, chatId));
      if (earlier.length) {
        const history = node('details', '', 'agent-action-history');
        history.append(node('summary', `Earlier versions (${earlier.length})`));
        history.append(...earlier.map(action => card(action, chatId, {compact: true})));
        children.push(history);
      }
    }
    if (data.evidence.length) children.push(evidenceList(data.evidence));
    panel.replaceChildren(...children);
    panel.hidden = !children.length;
    armExpiryTimer();
  }
  function armExpiryTimer() {
    const live = Boolean(document.querySelector('#agentGoogleActions .agent-action-card[data-status="pending"]'));
    if (live && !expiryTimer) {
      expiryTimer = setInterval(() => {
        const cards = [...document.querySelectorAll('#agentGoogleActions .agent-action-card[data-status="pending"]')];
        if (!cards.length) { clearInterval(expiryTimer); expiryTimer = null; return; }
        const data = chats.get(shownChat);
        const lapsed = data?.actions.some(action => action.status === 'pending' && expired(action)
          && document.querySelector(`#agentGoogleActions [data-action-id="${action.id}"][data-status="pending"]`));
        if (lapsed) { renderActions(shownChat); emitActions(shownChat); }
        else cards.forEach(el => el._sync?.());
      }, EXPIRY_TICK_MS);
    } else if (!live && expiryTimer) { clearInterval(expiryTimer); expiryTimer = null; }
  }
  function emitActions(chatId) {
    window.dispatchEvent(new CustomEvent('consensio:agent-actions-change', {detail: {chatId, pending: pendingCount(chatId), googleData: chatUsesGoogle(chatId)}}));
  }
  async function load(chatId) {
    const owner = uid(), seq = ++actionGeneration, panel = host();
    try {
      const result = await api(`/agent/chats/${chatId}/actions`);
      if (seq !== actionGeneration || owner !== uid() || shownChat !== chatId) return;
      silentRetries.delete(chatId);
      chats.set(chatId, {actions: result.actions || [], evidence: result.evidence || []});
      // The chat marker is permanent; a final-event hint may arrive first.
      if (typeof result.google_data === 'boolean') googleDataHints.set(chatId, result.google_data || googleDataHints.get(chatId) === true);
      renderActions(chatId);
      emitActions(chatId);
      syncChips(); window.updateQuestionInputAccess?.();
    } catch (error) {
      if (seq !== actionGeneration || shownChat !== chatId || !panel) return;
      const important = chatUsesGoogle(chatId) || Boolean(chats.get(chatId)?.actions?.length);
      if (!important) {
        // Most chats never use Google: retry once quietly, then stay out of the way.
        if (!silentRetries.has(chatId)) { silentRetries.add(chatId); setTimeout(() => { if (shownChat === chatId) refreshActions(chatId, true); }, 1500); }
        if (!panel.querySelector('.agent-action-card')) panel.hidden = true;
        return;
      }
      loadedKey = '';
      const box = notice('Couldn’t load email and calendar actions.', 'error', () => refreshActions(chatId, true));
      panel.querySelector(':scope > .agent-google-notice')?.remove();
      panel.prepend(box); panel.hidden = false;
    }
  }
  // Debounced per chat: one request per 300 ms, trailing calls coalesce.
  function schedule(chatId) {
    let entry = schedules.get(chatId);
    if (!entry) { entry = {last: 0, timer: null, queued: null, inflight: null}; schedules.set(chatId, entry); }
    if (entry.queued) return entry.queued;
    const current = entry;
    current.queued = new Promise(resolve => {
      const start = async () => {
        current.timer = null;
        if (current.inflight) await current.inflight;
        current.queued = null; current.last = Date.now();
        const running = load(chatId);
        current.inflight = running;
        await running;
        if (current.inflight === running) current.inflight = null;
        resolve();
      };
      const wait = Math.max(0, current.last + DEBOUNCE_MS - Date.now());
      if (!wait && !current.inflight) queueMicrotask(start);
      else current.timer = setTimeout(start, wait);
    });
    return current.queued;
  }
  function refreshActions(chatId, force = false) {
    const panel = host();
    if (!chatId || !uid() || !App.agentChat?.isSelected?.()) {
      ++actionGeneration; loadedKey = ''; shownChat = '';
      for (const entry of schedules.values()) clearTimeout(entry.timer);
      schedules.clear();
      if (panel) { panel.replaceChildren(); panel.hidden = true; }
      armExpiryTimer(); emitActions('');
      return Promise.resolve();
    }
    const key = `${uid()}:${chatId}`;
    // During a run of this chat every call refetches (resources events).
    const visible = App.runRegistry?.visible?.();
    const running = visible?.metadata?.chatId === chatId && App.runRegistry?.isExecuting?.(visible.runId);
    if (!force && !running && loadedKey === key) return schedules.get(chatId)?.queued || Promise.resolve();
    if (shownChat !== chatId) {
      ++actionGeneration;
      for (const entry of schedules.values()) clearTimeout(entry.timer);
      schedules.clear();
      if (panel) { panel.replaceChildren(); panel.hidden = true; }
      if (chats.has(chatId)) { shownChat = chatId; renderActions(chatId); }
      // A chat created by the running first message is known to be empty:
      // resources events and the finish refresh load it when that changes.
      else if (!force && running && !visible.basis) {
        chats.set(chatId, {actions: [], evidence: []});
        loadedKey = key; shownChat = chatId; emitActions(chatId);
        return Promise.resolve();
      }
    }
    loadedKey = key; shownChat = chatId;
    return schedule(chatId);
  }
  function noteGoogleData(chatId, value) {
    if (!chatId) return;
    if (value) googleDataHints.set(chatId, true);
    else if (!googleDataHints.has(chatId)) googleDataHints.set(chatId, false);
    syncChips(); window.updateQuestionInputAccess?.();
  }

  window.addEventListener('consensio:auth-state', () => {
    connectionsGen++; actionGeneration++; calendarGen++;
    connections = {status: 'idle', configured: null, accounts: [], error: ''}; connectionsPromise = null;
    clearSelection(); chats.clear(); googleDataHints.clear(); silentRetries.clear();
    for (const entry of schedules.values()) clearTimeout(entry.timer);
    schedules.clear(); loadedKey = ''; shownChat = ''; controlsKey = ''; consentChat = null;
    pending?.popup.close(); pending = null;
    closeSheet();
    const box = consentInput(); if (box) box.checked = false;
    document.getElementById('agentGoogleActions')?.replaceChildren();
    if (document.getElementById('agentGoogleActions')) document.getElementById('agentGoogleActions').hidden = true;
    armExpiryTimer();
    syncChips(); syncEntry();
  });
  // A finished Agent run may have prepared actions or read mail even when no
  // resources event reached this module: reload that chat's list once.
  window.addEventListener('consensio:run-registry-change', event => {
    const context = event.detail?.context;
    if (event.detail?.type !== 'finished' || context?.config?.executionMode !== 'agent') return;
    const chatId = context.metadata?.chatId;
    if (chatId && chatId === shownChat && uid()) refreshActions(chatId, true);
  });
  // Connections load on first use, never on page open: opening the (+) menu
  // that holds the Google entry is the earliest point they can matter.
  document.addEventListener('click', event => {
    if (connections.status === 'idle' && event.target.closest?.('#attachTrigger') && agentActive()) loadConnections();
  }, true);
  // Without a cached hint (first visit in this tab session), the first focus
  // in the Agent composer learns whether Google is configured at all, so an
  // installation without Google never shows the entry for long.
  document.addEventListener('focusin', event => {
    if (connections.status === 'idle' && !hint() && event.target.id === 'questionInput' && agentActive()) loadConnections();
  });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => ensureDom());
  else ensureDom();

  App.agentGoogle = {selection, consent, resetConsent, blocker, pendingCount, open: () => open(), close: closeSheet,
    refreshControls, refreshActions, evidenceFor, noteGoogleData};
})();
