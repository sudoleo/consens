// The account's workspace live (routers/agent_workspace.py, agent_workspace.py,
// docs/agent-mode.md "Arbeitsplatz"): its Chrome in a panel beside the chat,
// through noVNC (static/vendor/novnc, loaded when the panel first opens).
// The user watches; a click on the screen takes the browser over, and the
// agent waits (agent_workspace.py "Takeover") until "Hand back"; its server
// on the workbench keeps answering localhost here (agent_tunnel.py). While the user has it, the panel refreshes the takeover every
// REFRESH_MS, and at once when the page comes back to the front; a reload of
// this tab opens the view again in the user's hands (A-S6, 2026-10-29); a
// closed tab lets it expire by itself. Sign-ins happen here, by
// the user: the agent never types a password.
//
// Pasting (Ctrl+V, Cmd+V, Shift+Insert or "Paste", only while the user has the
// browser): the text goes in as key presses, as if typed, never through the
// workspace's clipboard, where it would stay for the agent to read later. So
// a password from the user's own password manager reaches the page and
// nothing else. The shortcut never reaches noVNC: a hidden field takes the
// browser's paste.
//
// Wide screens (DOCK_QUERY) dock the panel at the right edge beside the
// chat, which narrows and re-centres in the space left of it (the body's
// workspace-view-docked, --workspace-width; workspace-view.css), next to the
// Agent activity panel when that is open. The edge between them drags (or
// moves with the arrow keys) and remembers its width per browser; the chat
// never gets narrower than MIN_CHAT. Narrower screens show it full width.
//
// Two tabs (since 2026-10-28): Browser, the live view above, and Terminal, the
// user's own shell on the workbench (routers/agent_workspace.py, xterm.js from
// static/vendor/xterm, loaded on the tab's first use) with the agent's rights:
// no administrator rights, only package sources online. Its keys go to the
// shell as they are, its size follows the panel ({"type": "resize"}). While a
// tab loads it shows a skeleton of what comes (no spinner), and after
// SLOW_MS a calm word that the first start takes a minute.
//
// Whose turn it is (since 2026-10-29): a bar right above the picture says it
// while the user has the browser, with the one strong button to hand it
// back, and reminds them after IDLE_MS without a key or click there; while
// the agent waits for them (ask_user, agent-chat.js askCard) it says what
// for, with the button to take over. Before, only a small toggle in the head
// said so, and Max waited for the agent while it waited for him.
//
// window.App.workspaceView: open({ takeOver }), close(), isOpen(), init()
// (the start screen's Workspace button, the (+) menu's row, the row in
// Settings → Agent), holder(), handBack() (also without an open view, for the
// card in the chat), agentWaits(request or null); agent-activity.js opens it
// from a browser step ("Watch live"). A change of holder is the window's
// event "consensio:workspace-holder".
(function () {
  'use strict';
  const App = window.App = window.App || {};
  const NOVNC = '/static/vendor/novnc/1.7.0/core/rfb.js';
  const XTERM = '/static/vendor/xterm/6.0.0/xterm.js';
  const XTERM_FIT = '/static/vendor/xterm/6.0.0/addon-fit.js';
  const XTERM_CSS = '/static/vendor/xterm/6.0.0/xterm.css';
  const REFRESH_MS = 30_000;
  // Who had the browser in this tab, for a reload (returnToHolder); a
  // takeover older than RETURN_MS (a pause's own time) is not taken up again.
  const HOLDER_KEY = 'workspace_view_holder';
  const RETURN_MS = 30 * 60_000;
  // The user has the browser and did nothing there for this long: the bar reminds them to hand it back.
  const IDLE_MS = 60_000;
  // A start that takes longer than this (the workspace's first start, outside
  // a chat) says so calmly.
  const SLOW_MS = 6_000;
  const STATES = {
    connecting: 'Connecting to the workspace…',
    slow: 'Starting your workspace. The first start can take a minute.',
    setup: 'Setting up the browser (once, about a minute)…',
    starting: 'Starting the browser…',
    error: 'The workspace is not reachable right now. Try again in a moment.',
    ended: 'The view closed after an hour. Open it again to go on.',
    // One view per account, its time counts as VM time (routers/agent_workspace.py).
    replaced: 'The workspace opened in another window, so this view closed.',
    no_time: 'The workspace’s time for today is used up. It is back tomorrow.',
    too_many: 'The workspace was opened many times in a row. Try again in a minute.',
  };
  // Why the server closed the view, by close code: noVNC owns the socket's
  // messages once it is ready, so these come as codes, not states.
  const CLOSED = { 4410: 'ended', 4409: 'replaced', 4402: 'no_time', 4429: 'too_many' };
  const TERMINAL = {
    connecting: 'Opening a terminal on the workbench…',
    ready: 'Your terminal on the workbench, with the agent’s rights.',
    ended: 'The terminal ended. Start a new one to go on.',
    lost: 'The connection to the terminal ended. Start a new one to go on.',
    error: 'The terminal is not reachable right now. Try again in a moment.',
    replaced: 'The terminal opened in another window, so this one closed.',
    unavailable: 'The terminal could not load. Reload the page and try again.',
  };
  const HINTS = {
    browser: 'Log in to sites here yourself, typing or pasting your password: the agent pauses meanwhile, then works there as you, and never types a password.',
    terminal: 'The computer the agent works on, with the same files and rights: no administrator rights, and only package sources online.',
  };
  // Docked beside the chat from the width where the app's sidebar pushes the column (layout.css).
  const DOCK_QUERY = '(min-width: 1100px)';
  const WIDE_QUERY = '(min-width: 1200px)';
  // The Agent activity panel's width when it docks (agent-chat.css .agent-sidebar).
  const ACTIVITY_WIDTH = 346;
  const MIN_WIDTH = 380;
  // The chat's column keeps this much beside the panels: room to read and write.
  const MIN_CHAT = 520;
  const KEY_STEP = 40;
  const STORAGE_KEY = 'consens.workspaceWidth';
  // Typed in key by key: enough for a password or a few lines, not a document.
  const PASTE_MAX = 2000;
  const XK_RETURN = 0xff0d;
  const XK_TAB = 0xff09;
  // Shift, Control, Meta, Alt and Super, left and right: still down in the VM
  // from the shortcut, they would turn the text into shortcuts.
  const MODIFIERS = [0xffe1, 0xffe2, 0xffe3, 0xffe4, 0xffe7, 0xffe8, 0xffe9, 0xffea, 0xffeb, 0xffec];
  let view = null;
  // What the agent waits for the user to do in the browser (agentWaits), also before the view opens.
  let waitingFor = null;
  let loadRFB = () => import(NOVNC).then(module => module.default);
  let loadTerminal = () => Promise.all([import(XTERM), import(XTERM_FIT)])
    .then(([xterm, fit]) => ({ Terminal: xterm.Terminal, FitAddon: fit.FitAddon }));

  const matches = query => Boolean(window.matchMedia?.(query)?.matches);
  // The window without its scrollbar: where a fixed panel's right edge is.
  const viewportWidth = () => document.documentElement.clientWidth || window.innerWidth;
  function docked() { return matches(DOCK_QUERY); }
  // What the panel may not cover on the right: the activity panel, when it docks too.
  function rightOffset() {
    return document.body.classList.contains('agent-sidebar-open') && matches(WIDE_QUERY) ? ACTIVITY_WIDTH : 0;
  }
  function sidebarOffset() {
    const value = getComputedStyle(document.body).getPropertyValue('--app-sidebar-offset');
    return Number.parseFloat(value) || 0;
  }
  function bounds() {
    const room = viewportWidth() - sidebarOffset() - rightOffset() - MIN_CHAT;
    return { min: Math.min(MIN_WIDTH, Math.max(260, room)), max: Math.max(Math.min(MIN_WIDTH, room), room) };
  }
  function preferredWidth() {
    let saved = 0;
    try { saved = Number(localStorage.getItem(STORAGE_KEY)) || 0; } catch (error) { saved = 0; }
    // About half of what is left beside the app's sidebar, the chat the other half.
    return saved || Math.round((viewportWidth() - sidebarOffset() - rightOffset()) * 0.5);
  }
  function remember(width) {
    try { localStorage.setItem(STORAGE_KEY, String(Math.round(width))); } catch (error) { /* per browser only */ }
  }
  // The panel's width and the chat's room, clamped to the window as it is now.
  function layout(width = view?.width) {
    if (!view) return;
    const isDocked = docked();
    const { min, max } = bounds();
    view.width = Math.round(Math.min(max, Math.max(min, width || preferredWidth())));
    document.body.classList.toggle('workspace-view-docked', isDocked);
    document.body.style.setProperty('--workspace-width', `${isDocked ? view.width : 0}px`);
    view.panel.style.setProperty('--workspace-right', `${isDocked ? rightOffset() : 0}px`);
    view.resizer.hidden = !isDocked;
    view.resizer.setAttribute('aria-valuemin', String(Math.round(min)));
    view.resizer.setAttribute('aria-valuemax', String(Math.round(max)));
    view.resizer.setAttribute('aria-valuenow', String(view.width));
  }
  function resizeTo(width, { save = true } = {}) {
    layout(width);
    if (save && view) remember(view.width);
  }
  function startDrag(event) {
    if (!view || event.button !== 0) return;
    event.preventDefault();
    const resizer = view.resizer;
    resizer.setPointerCapture?.(event.pointerId);
    document.body.classList.add('workspace-view-resizing');
    const edge = viewportWidth() - rightOffset();
    const move = (moved) => resizeTo(edge - moved.clientX, { save: false });
    const end = () => {
      resizer.removeEventListener('pointermove', move);
      resizer.removeEventListener('pointerup', end);
      resizer.removeEventListener('pointercancel', end);
      document.body.classList.remove('workspace-view-resizing');
      if (view) remember(view.width);
    };
    resizer.addEventListener('pointermove', move);
    resizer.addEventListener('pointerup', end);
    resizer.addEventListener('pointercancel', end);
  }
  function keyResize(event) {
    if (!view) return;
    const { min, max } = bounds();
    const next = { ArrowLeft: view.width + KEY_STEP, ArrowRight: view.width - KEY_STEP, Home: max, End: min }[event.key];
    if (next === undefined) return;
    event.preventDefault();
    resizeTo(next);
  }
  function onWindowResize() { layout(); }

  function node(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }
  function button(className, text, handler) {
    const element = node('button', className, text);
    element.type = 'button';
    element.addEventListener('click', handler);
    return element;
  }
  async function idToken() {
    const user = window.auth?.currentUser;
    if (!user) throw new Error('Log in first.');
    return user.getIdToken();
  }
  async function post(path, body) {
    const response = await fetch(path, { method: 'POST', body: JSON.stringify(body || {}),
      headers: { Authorization: `Bearer ${await idToken()}`, 'Content-Type': 'application/json' } });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || data.detail || 'Try again.');
    return data;
  }

  // What comes, drawn calmly while it loads: a browser window (its address
  // bar and a page) or a terminal's lines. Decoration only (aria-hidden).
  function skeleton(kind) {
    const box = node('div', `workspace-view-skeleton is-${kind}`);
    box.setAttribute('aria-hidden', 'true');
    if (kind === 'browser') box.append(node('span', 'workspace-view-skeleton-bar'));
    const lines = node('div', 'workspace-view-skeleton-lines');
    const widths = kind === 'browser' ? [46, 92, 84, 88, 62, 0, 78, 70] : [38, 64, 52, 24];
    for (const width of widths) {
      const line = node('span', width ? 'workspace-view-skeleton-line' : 'workspace-view-skeleton-gap');
      if (width) line.style.width = `${width}%`;
      lines.append(line);
    }
    box.append(lines);
    return box;
  }

  function build() {
    const panel = node('aside', 'workspace-view');
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-label', 'Workspace');
    const head = node('header', 'workspace-view-head');
    const title = node('strong', 'workspace-view-title', 'Workspace');
    const tabs = node('div', 'workspace-view-tabs');
    tabs.setAttribute('role', 'tablist');
    tabs.setAttribute('aria-label', 'Workspace');
    const tabButtons = {};
    for (const [key, label] of [['browser', 'Browser'], ['terminal', 'Terminal']]) {
      const tab = button('workspace-view-tab', label, () => showTab(key));
      tab.setAttribute('role', 'tab');
      tab.id = `workspaceTab-${key}`;
      tab.setAttribute('aria-controls', `workspacePane-${key}`);
      tab.addEventListener('keydown', onTabKey);
      tabButtons[key] = tab;
      tabs.append(tab);
    }
    const status = node('span', 'workspace-view-status', STATES.connecting);
    status.setAttribute('role', 'status');
    const toggle = button('workspace-view-toggle', 'Take over', () => (view?.holder === 'user' ? handBack() : takeOver()));
    toggle.hidden = true;
    const closer = button('workspace-view-close', '', close);
    closer.setAttribute('aria-label', 'Close workspace');
    closer.title = 'Close workspace';
    closer.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18"/></svg>';
    const paster = button('workspace-view-paste', 'Paste', pasteClipboard);
    paster.title = 'Type your clipboard into the page';
    paster.hidden = true;
    head.append(title, tabs, status, paster, toggle, closer);
    const hint = node('p', 'workspace-view-hint', HINTS.browser);
    // Whose turn it is (showTurn): a dot in the state's colour, a title over a
    // quiet line (the app's words, or the agent's request as data), the one button.
    const turn = node('div', 'workspace-view-turn');
    turn.setAttribute('role', 'status');
    turn.hidden = true;
    const turnDot = node('span', 'workspace-view-turn-dot');
    turnDot.setAttribute('aria-hidden', 'true');
    const turnText = node('p', 'workspace-view-turn-text');
    const turnSays = node('strong', 'workspace-view-turn-says');
    const turnNote = node('span', 'workspace-view-turn-note');
    const turnRequest = node('span', 'workspace-view-turn-note workspace-view-turn-request');
    turnRequest.dataset.i18nSkip = '';
    turnText.append(turnSays, turnNote, turnRequest);
    const turnButton = button('btn workspace-view-turn-button', 'Hand back',
      () => (view?.holder === 'user' ? handBack() : takeOver()));
    turn.append(turnDot, turnText, turnButton);
    const screen = node('div', 'workspace-view-screen is-loading');
    screen.id = 'workspacePane-browser';
    screen.setAttribute('role', 'tabpanel');
    screen.setAttribute('aria-labelledby', 'workspaceTab-browser');
    const cover = button('workspace-view-cover', '', takeOver);
    cover.setAttribute('aria-label', 'Take over the browser');
    cover.title = 'Click to take over';
    cover.hidden = true;
    // Where the browser pastes a shortcut's text (onPasteKey), out of sight.
    const pasteTarget = node('textarea', 'workspace-view-paste-target');
    pasteTarget.tabIndex = -1;
    pasteTarget.setAttribute('aria-hidden', 'true');
    screen.append(skeleton('browser'), cover, pasteTarget);
    screen.addEventListener('keydown', onPasteKey, true);
    // What counts as doing something there: the idle reminder starts over.
    for (const type of ['pointerdown', 'keydown', 'wheel']) {
      screen.addEventListener(type, () => {
        if (view?.holder !== 'user') return;
        const reminded = view.isIdle;
        restartIdle();
        if (reminded) showTurn();
      }, true);
    }
    // The terminal's pane: its output is the shell's, never translated.
    const terminal = node('div', 'workspace-view-screen workspace-view-terminal is-loading');
    terminal.id = 'workspacePane-terminal';
    terminal.setAttribute('role', 'tabpanel');
    terminal.setAttribute('aria-labelledby', 'workspaceTab-terminal');
    terminal.hidden = true;
    const terminalHost = node('div', 'workspace-view-terminal-host');
    terminalHost.dataset.i18nSkip = '';
    terminalHost.setAttribute('translate', 'no');
    const restart = button('workspace-view-restart', 'Start a new terminal', () => startTerminal());
    restart.hidden = true;
    terminal.append(skeleton('terminal'), terminalHost, restart);
    panel.addEventListener('paste', onPaste);
    // The edge to the chat: drag it, or move it with the arrow keys; a double click goes back to half and half.
    const resizer = node('div', 'workspace-view-resizer');
    resizer.setAttribute('role', 'separator');
    resizer.setAttribute('aria-orientation', 'vertical');
    resizer.setAttribute('aria-label', 'Resize the workspace');
    resizer.title = 'Drag to resize';
    resizer.tabIndex = 0;
    resizer.addEventListener('pointerdown', startDrag);
    resizer.addEventListener('keydown', keyResize);
    resizer.addEventListener('dblclick', () => {
      try { localStorage.removeItem(STORAGE_KEY); } catch (error) { /* per browser only */ }
      resizeTo(preferredWidth(), { save: false });
    });
    panel.append(resizer, head, hint, turn, screen, terminal);
    return { panel, status, hint, tabButtons, toggle, paster, cover, pasteTarget, screen, terminal, terminalHost,
      turn, turnSays, turnNote, turnRequest, turnButton, isIdle: false, idle: null, wantControl: false,
      restart, resizer, socket: null, rfb: null, holder: 'agent', refresh: null, width: 0, tab: 'browser',
      said: { browser: STATES.connecting, terminal: TERMINAL.connecting }, slow: null,
      term: null, fit: null, termSocket: null, termReady: false, termResize: null };
  }

  // ---- Tabs ---------------------------------------------------------------
  function showTab(key) {
    if (!view || !view.tabButtons[key]) return;
    view.tab = key;
    for (const [name, tab] of Object.entries(view.tabButtons)) {
      const active = name === key;
      tab.setAttribute('aria-selected', String(active));
      tab.tabIndex = active ? 0 : -1;
      tab.classList.toggle('is-active', active);
    }
    view.screen.hidden = key !== 'browser';
    view.terminal.hidden = key !== 'terminal';
    view.hint.textContent = HINTS[key];
    view.panel.dataset.tab = key;
    say(view.said[key], key);
    showHolder();
    if (key === 'terminal') {
      if (!view.term && !view.termSocket) startTerminal();
      else (window.requestAnimationFrame || setTimeout)(() => { fitTerminal(); view?.term?.focus(); });
    }
  }
  function onTabKey(event) {
    if (!view || !['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const keys = Object.keys(view.tabButtons);
    const at = keys.indexOf(view.tab);
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? keys.length - 1
      : (at + (event.key === 'ArrowRight' ? 1 : keys.length - 1)) % keys.length;
    showTab(keys[next]);
    view.tabButtons[keys[next]].focus();
  }
  // A tab's skeleton shows until what it draws is there.
  function loading(key, on) {
    if (!view) return;
    (key === 'terminal' ? view.terminal : view.screen).classList.toggle('is-loading', on);
  }
  // A start that takes long says so once, while it still connects.
  function watchSlow() {
    if (!view) return;
    clearTimeout(view.slow);
    view.slow = setTimeout(() => {
      if (view && view.said.browser === STATES.connecting) say(STATES.slow);
    }, SLOW_MS);
  }

  // ---- Pasting as key presses ---------------------------------------------
  function pasting() { return Boolean(view?.rfb) && view.holder === 'user'; }
  // Latin-1 is its own keysym, the rest X11's Unicode keysyms (noVNC's keysymdef.js).
  function keysym(codePoint) {
    return codePoint >= 0x20 && codePoint <= 0xff ? codePoint : 0x01000000 | codePoint;
  }
  function typeIn(text) {
    if (!pasting()) return;
    // A copied line often ends in a line break: pasted, it would send the form.
    const clean = String(text || '').replace(/\r\n?/g, '\n').replace(/\n+$/, '');
    if (!clean) return;
    if ([...clean].length > PASTE_MAX) {
      say('That is too long to type in. Paste at most 2,000 characters at a time.');
      return;
    }
    const { rfb } = view;
    for (const modifier of MODIFIERS) rfb.sendKey(modifier, null, false);
    for (const char of clean) {
      const code = char.codePointAt(0);
      if (char === '\n') rfb.sendKey(XK_RETURN, null);
      else if (char === '\t') rfb.sendKey(XK_TAB, null);
      else if (code >= 0x20 && !(code >= 0x7f && code < 0xa0)) rfb.sendKey(keysym(code), null);
    }
    rfb.focus();
  }
  function onPasteKey(event) {
    if (!pasting()) return;
    const key = String(event.key || '').toLowerCase();
    const shortcut = ((event.ctrlKey || event.metaKey) && !event.altKey && key === 'v')
      || (event.shiftKey && key === 'insert');
    if (!shortcut) return;
    // Not to noVNC, which would press it in the VM: the browser pastes into the hidden field.
    event.stopPropagation();
    view.pasteTarget.value = '';
    view.pasteTarget.focus({ preventScroll: true });
    // Nothing to paste: back to the screen, so keys reach the VM again.
    setTimeout(() => {
      if (view && document.activeElement === view.pasteTarget) view.rfb?.focus();
    }, 400);
  }
  function onPaste(event) {
    if (!pasting()) return;
    event.preventDefault();
    typeIn(event.clipboardData?.getData('text/plain') || '');
  }
  async function pasteClipboard() {
    if (!pasting()) return;
    let text = '';
    try {
      text = await navigator.clipboard.readText();
    } catch (error) {
      say('Your browser did not share the clipboard. Press Ctrl+V (Cmd+V on a Mac) on the screen instead.');
      return;
    }
    typeIn(text);
  }

  // Each tab has its own line; the head shows the open tab's.
  function say(text, key = 'browser') {
    if (!view) return;
    view.said[key] = text;
    if (view.tab !== key) return;
    view.status.textContent = text;
    // A narrow panel cuts the line: the whole of it on hover.
    view.status.title = text;
  }

  function showHolder() {
    if (!view) return;
    const user = view.holder === 'user';
    const browser = view.tab === 'browser';
    // While the user has it, the bar above the picture holds the way back.
    view.toggle.hidden = !view.rfb || !browser || user;
    view.toggle.textContent = 'Take over';
    view.paster.hidden = !view.rfb || !user || !browser || !navigator.clipboard?.readText;
    view.cover.hidden = !view.rfb || user;
    view.panel.classList.toggle('is-user', user);
    if (view.rfb) {
      view.rfb.viewOnly = !user;
      // While the user has it, the bar says so: the head stays quiet.
      say(user ? '' : 'Watching. Click the screen to take over.');
    }
    showTurn();
  }

  // The bar: the user's turn (and after IDLE_MS a reminder), or what the
  // agent waits for them to do, or nothing while the agent works.
  function showTurn() {
    if (!view) return;
    const user = view.holder === 'user';
    const waiting = waitingFor !== null && !user;
    const idle = user && view.isIdle;
    view.turn.hidden = !view.rfb || view.tab !== 'browser' || !(user || waiting);
    // One way to take over or hand back at a time: the bar's, when it shows.
    if (!view.turn.hidden) view.toggle.hidden = true;
    view.turn.classList.toggle('is-user', user);
    view.turn.classList.toggle('is-idle', Boolean(idle));
    const says = idle ? 'Done?' : user ? 'You have the browser' : 'The agent is waiting for you';
    const note = idle ? 'Hand the browser back so the agent can go on.' : user ? 'The agent waits.' : '';
    if (view.turnSays.textContent !== App.t(says)) view.turnSays.textContent = says;
    if (view.turnNote.textContent !== (note && App.t(note))) view.turnNote.textContent = note;
    view.turnNote.hidden = !note;
    const request = waiting ? String(waitingFor || '') : '';
    if (view.turnRequest.textContent !== request) view.turnRequest.textContent = request;
    view.turnRequest.hidden = !request;
    view.turnButton.textContent = user ? 'Hand back' : 'Take over';
  }

  // IDLE_MS after taking over or the last key or click there, the bar reminds.
  function restartIdle() {
    if (!view) return;
    clearTimeout(view.idle);
    view.isIdle = false;
    view.idle = view.holder === 'user' ? setTimeout(() => {
      if (!view) return;
      view.isIdle = true;
      showTurn();
    }, IDLE_MS) : null;
  }

  function announceHolder(holder) {
    window.dispatchEvent(new CustomEvent('consensio:workspace-holder', { detail: { holder } }));
  }

  // The user has the browser (A-S6): remembered in this tab, so a reload
  // (a phone that discarded the page while the user was in the 2FA app)
  // opens the view again in their hands instead of letting it lapse.
  function rememberHolder(holder) {
    try {
      if (holder === 'user') {
        sessionStorage.setItem(HOLDER_KEY, JSON.stringify({ uid: window.auth?.currentUser?.uid || '', at: Date.now() }));
      } else sessionStorage.removeItem(HOLDER_KEY);
    } catch (_) { /* private mode: no return after a reload */ }
  }
  function refreshNow() {
    rememberHolder('user');
    post('/agent/workspace/control', { holder: 'user' }).catch(() => {});
  }
  async function setHolder(holder) {
    await post('/agent/workspace/control', { holder });
    if (!view) return;
    view.holder = holder;
    rememberHolder(holder);
    restartIdle();
    clearInterval(view.refresh);
    view.refresh = holder === 'user' ? setInterval(refreshNow, REFRESH_MS) : null;
    showHolder();
    announceHolder(holder);
  }
  // A page in the background (the 2FA app, a call, a locked phone) may not
  // run its interval: the takeover lapsed after CONTROL_SECONDS and the agent
  // went on mid-login. Back in front, it is refreshed at once and the
  // interval starts over (A-S6; the server no longer takes a lapse for a
  // hand-back while the agent waits for the user).
  function onVisible() {
    if (document.visibilityState === 'hidden' || view?.holder !== 'user') return;
    clearInterval(view.refresh);
    view.refresh = setInterval(refreshNow, REFRESH_MS);
    refreshNow();
  }
  // After a reload: the user had the browser in this tab a moment ago, so the
  // view opens again and takes it, once this tab's account is signed in.
  function returnToHolder() {
    let saved = null;
    try { saved = JSON.parse(sessionStorage.getItem(HOLDER_KEY) || 'null'); } catch (_) { saved = null; }
    const uid = window.auth?.currentUser?.uid;
    if (!saved || !uid) return;
    if (saved.uid !== uid || !(Date.now() - Number(saved.at) < RETURN_MS)) { rememberHolder('agent'); return; }
    if (!view) open({ takeOver: true });
  }

  async function takeOver() {
    if (!view?.rfb || view.holder === 'user') return;
    view.wantControl = false;
    try {
      await setHolder('user');
      view?.rfb?.focus();
    } catch (error) {
      say(App.t('Could not take over: {reason}', { reason: error.message || 'Try again.' }));
    }
  }

  // Also without an open view (the card in the chat after a takeover in
  // another window): the server's record is what the waiting run reads.
  async function handBack() {
    if (!view) {
      try {
        await post('/agent/workspace/control', { holder: 'agent' });
        rememberHolder('agent');
        announceHolder('agent');
      } catch (error) {
        App.showPopup?.(App.t('Could not hand back: {reason}', { reason: error.message || 'Try again.' }));
      }
      return;
    }
    if (view.holder !== 'user') return;
    try {
      await setHolder('agent');
    } catch (error) {
      say(App.t('Could not hand back: {reason}', { reason: error.message || 'Try again.' }));
    }
  }

  // The agent waits for the user in the browser (ask_user), or no longer (null).
  function agentWaits(request) {
    const next = request === null || request === undefined ? null : String(request);
    if (next === waitingFor) return;
    waitingFor = next;
    showTurn();
  }

  function connect(RFB) {
    const scheme = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const socket = new WebSocket(`${scheme}//${location.host}/agent/workspace/view`);
    view.socket = socket;
    socket.binaryType = 'arraybuffer';
    socket.onopen = async () => {
      try {
        socket.send(JSON.stringify({ id_token: await idToken() }));
      } catch (error) {
        say(error.message || 'Log in first.');
        socket.close();
      }
    };
    socket.onmessage = (event) => {
      if (typeof event.data !== 'string' || !view || view.socket !== socket) return;
      let state = '';
      try { state = JSON.parse(event.data).state; } catch (error) { return; }
      if (state !== 'ready') {
        if (STATES[state]) say(STATES[state]);
        if (state === 'connecting') watchSlow();
        if (state === 'error') loading('browser', false);
        return;
      }
      clearTimeout(view.slow);
      loading('browser', false);
      // Synchronously, inside this event: noVNC takes over the socket's
      // handlers, so the VNC bytes that follow "ready" all reach it.
      const rfb = new RFB(view.screen, socket, { shared: true });
      rfb.scaleViewport = true;
      rfb.resizeSession = false;
      rfb.viewOnly = true;
      // The panel's own tone around the picture, not noVNC's dark grey.
      rfb.background = 'transparent';
      rfb.addEventListener('disconnect', () => {
        if (view?.rfb !== rfb) return;
        view.rfb = null;
        say('The connection to the workspace ended. Close and open it again.');
        showHolder();
      });
      view.rfb = rfb;
      showHolder();
      // Opened to take over (the agent's card asked for it): as soon as there is a picture.
      if (view.wantControl) takeOver();
    };
    socket.onclose = (event) => {
      if (!view || view.socket !== socket || view.rfb) return;
      clearTimeout(view.slow);
      loading('browser', false);
      say(event.code === 4403 ? 'The workspace is not available on your account.'
        : 'The connection to the workspace ended. Close and open it again.');
    };
    // After noVNC's own handler (it takes over onclose): the reason wins
    // over its general "ended".
    socket.addEventListener('close', (event) => {
      if (view && view.socket === socket && CLOSED[event.code]) say(STATES[CLOSED[event.code]]);
    });
  }

  // ---- Terminal --------------------------------------------------------------
  function terminalStyles() {
    if (document.querySelector('link[data-xterm-css]')) return;
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = XTERM_CSS;
    link.dataset.xtermCss = '';
    document.head.append(link);
  }
  // The app's own tones and type, read from the page (light or dark).
  function terminalTheme() {
    const style = getComputedStyle(view.panel);
    const tone = (name, fallback) => style.getPropertyValue(name).trim() || fallback;
    return {
      fontFamily: tone('--font-mono', 'ui-monospace, Menlo, Consolas, monospace'), // i18n-ignore
      theme: { background: tone('--raise', '#151515'), foreground: tone('--ink', '#f2f2f2'),
        cursor: tone('--ink', '#f2f2f2'), selectionBackground: tone('--line', '#444444') },
    };
  }
  // The panel's size in characters; a change goes to the shell.
  function fitTerminal() {
    if (!view?.term || !view.fit || view.terminal.hidden) return;
    const { cols, rows } = view.term;
    try { view.fit.fit(); } catch (error) { return; }
    const socket = view.termSocket;
    if (view.termReady && socket?.readyState === 1 && (view.term.cols !== cols || view.term.rows !== rows)) {
      socket.send(JSON.stringify({ type: 'resize', cols: view.term.cols, rows: view.term.rows }));
    }
  }
  function endTerminal(text) {
    if (!view) return;
    view.termReady = false;
    view.termSocket = null;
    loading('terminal', false);
    view.restart.hidden = false;
    say(text, 'terminal');
  }
  async function startTerminal() {
    if (!view) return;
    try { view.termSocket?.close(); } catch (error) { /* already gone */ }
    view.restart.hidden = true;
    loading('terminal', true);
    say(TERMINAL.connecting, 'terminal');
    let lib;
    try {
      lib = await loadTerminal();
    } catch (error) {
      endTerminal(TERMINAL.unavailable);
      return;
    }
    if (!view) return;
    if (!view.term) {
      terminalStyles();
      const { fontFamily, theme } = terminalTheme();
      const term = new lib.Terminal({ cursorBlink: true, fontFamily, fontSize: 13, lineHeight: 1.2, theme,
        scrollback: 5000, allowProposedApi: false });
      const fit = new lib.FitAddon();
      term.loadAddon(fit);
      term.open(view.terminalHost);
      view.term = term;
      view.fit = fit;
      const encoder = new TextEncoder();
      term.onData(data => {
        const socket = view?.termSocket;
        if (view?.termReady && socket?.readyState === 1) socket.send(encoder.encode(data));
      });
      view.termResize = typeof ResizeObserver === 'function' ? new ResizeObserver(() => fitTerminal()) : null;
      view.termResize?.observe(view.terminalHost);
    } else {
      view.term.reset();
    }
    try { view.fit.fit(); } catch (error) { /* drawn once it is shown */ }
    connectTerminal(view.term);
  }
  function connectTerminal(term) {
    const scheme = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const socket = new WebSocket(`${scheme}//${location.host}/agent/workspace/terminal`);
    view.termSocket = socket;
    view.termReady = false;
    socket.binaryType = 'arraybuffer';
    socket.onopen = async () => {
      try {
        socket.send(JSON.stringify({ id_token: await idToken(), cols: term.cols, rows: term.rows }));
      } catch (error) {
        endTerminal(error.message || 'Log in first.');
        socket.close();
      }
    };
    socket.onmessage = (event) => {
      if (!view || view.termSocket !== socket) return;
      if (typeof event.data !== 'string') {
        term.write(new Uint8Array(event.data));
        return;
      }
      let state = '';
      try { state = JSON.parse(event.data).state; } catch (error) { return; }
      if (state === 'ready') {
        view.termReady = true;
        loading('terminal', false);
        say(TERMINAL.ready, 'terminal');
        fitTerminal();
        if (view.tab === 'terminal') term.focus();
      } else if (state === 'error') {
        endTerminal(TERMINAL.error);
      }
    };
    socket.onclose = (event) => {
      if (!view || view.termSocket !== socket) return;
      const reason = CLOSED[event.code];
      endTerminal(event.code === 4403 ? 'The workspace is not available on your account.'
        : reason === 'replaced' ? TERMINAL.replaced : reason ? STATES[reason]
          : event.code === 1000 ? TERMINAL.ended : view.termReady ? TERMINAL.lost : TERMINAL.error);
    };
  }

  async function open({ takeOver: take = false } = {}) {
    if (view) {
      view.panel.hidden = false;
      if (take && view.tab !== 'browser') showTab('browser');
      if (take && view.rfb) takeOver();
      else if (take) view.wantControl = true;
      return;
    }
    view = build();
    view.wantControl = Boolean(take);
    // The chat's card for the agent's question steps aside while the view is open (agent-chat.js renderHold).
    announceHolder(view.holder);
    document.body.append(view.panel);
    document.body.classList.add('workspace-view-open');
    showTab('browser');
    watchSlow();
    layout();
    window.addEventListener('resize', onWindowResize);
    // The Agent activity panel opening or closing beside it moves its right edge.
    view.right = rightOffset();
    view.observer = new MutationObserver(() => {
      if (!view || view.right === rightOffset()) return;
      view.right = rightOffset();
      layout();
    });
    view.observer.observe(document.body, { attributes: true, attributeFilter: ['class'] });
    let RFB;
    try {
      RFB = await loadRFB();
    } catch (error) {
      clearTimeout(view?.slow);
      loading('browser', false);
      say('The view could not load. Reload the page and try again.');
      return;
    }
    if (view) connect(RFB);
  }

  function close() {
    if (!view) return;
    const closing = view;
    view = null;
    clearInterval(closing.refresh);
    clearTimeout(closing.slow);
    clearTimeout(closing.idle);
    // The agent may go on at once; an unsent hand-back expires by itself.
    if (closing.holder === 'user') post('/agent/workspace/control', { holder: 'agent' }).catch(() => {});
    rememberHolder('agent');
    announceHolder('agent');
    try { closing.rfb?.disconnect(); } catch (error) { /* already gone */ }
    try { closing.socket?.close(); } catch (error) { /* already gone */ }
    // The shell ends shortly after its socket (TERMINAL_AFTER_DISCONNECT).
    try { closing.termSocket?.close(); } catch (error) { /* already gone */ }
    closing.termResize?.disconnect();
    try { closing.term?.dispose(); } catch (error) { /* already gone */ }
    closing.panel.remove();
    window.removeEventListener('resize', onWindowResize);
    closing.observer?.disconnect();
    document.body.classList.remove('workspace-view-open', 'workspace-view-docked', 'workspace-view-resizing');
    document.body.style.removeProperty('--workspace-width');
  }

  // ---- Settings → Agent: open the workspace, log its browser out -----------
  async function resetBrowser(status) {
    const confirmed = await App.confirm?.({ title: 'Log the workspace browser out everywhere?', danger: true,
      confirmLabel: 'Log out everywhere',
      body: 'The workspace’s browser forgets every site you are logged in to, its cookies and open tabs. The agent then reaches your accounts again only after you log in there anew.' });
    if (!confirmed) return;
    status.textContent = 'Logging out…';
    try {
      await post('/agent/workspace/reset-browser');
      status.textContent = 'The workspace browser is logged out everywhere.';
    } catch (error) {
      status.textContent = error.message || 'Try again.';
    }
  }
  function init() {
    // The start screen's tool bar, and in a chat the (+) menu.
    for (const id of ['composerWorkspaceButton', 'attachWorkspaceOption']) {
      const opener = document.getElementById(id);
      if (!opener || opener._workspace) continue;
      opener.addEventListener('click', () => {
        App.closeAttachMenu?.();
        open();
      });
      opener._workspace = true;
    }
    const host = document.getElementById('agentWorkspaceSettings');
    if (!host || host._workspace) return;
    const status = node('p', 'agent-workspace-status');
    status.setAttribute('role', 'status');
    const actions = node('div', 'agent-github-actions');
    actions.append(button('agent-github-link', 'Open workspace', open),
      button('agent-github-link', 'Log out everywhere', () => resetBrowser(status)));
    host.append(status, actions);
    host._workspace = true;
  }

  App.workspaceView = {
    open, close, init, handBack, agentWaits,
    isOpen: () => Boolean(view),
    // 'user' or 'agent' in the open view, else null.
    holder: () => view?.holder || null,
    width: () => view?.width || 0,
    showTab,
    // Tests replace the noVNC and xterm.js imports.
    _setLoader(loader) { loadRFB = loader; },
    _setTerminalLoader(loader) { loadTerminal = loader; },
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
  document.addEventListener('visibilitychange', onVisible);
  // The account is known (auth-session-state.js): a takeover from before a
  // reload is taken up again, also when that was said before this script ran.
  window.addEventListener('consensio:auth-state', returnToHolder);
  if (window.__consensioAuthState?.known) returnToHolder();
})();
