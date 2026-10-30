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
// Typing on a phone (since 2026-10-30, runtime audit V1): iOS and Android
// open no keyboard for noVNC's canvas. "Keyboard" (touch screens, while the
// user has the browser) focuses a field out of sight (16px, no capitals or
// corrections) whose keys go to the VM like noVNC's own keyboard input
// (app/ui.js keyboardinput): typed text from beforeinput, what a keyboard
// composes from the field's change, Backspace, Enter, Tab and the arrows on
// their own. Tapping the screen keeps it open (focusOnClick off meanwhile).
//
// A connection that drops without a reason from the server (the phone went
// to its 2FA app and iOS closed the socket, a network change) comes back by
// itself (V2): after 1, 2, 5 and 10 s, and at once when the page is in front
// again or back online. Meanwhile the skeleton and "Reconnecting…" show; the
// bar with "Hand back" stays, and so does the takeover. A close with a
// server's reason (FINAL) or four failed tries say why in up to two lines,
// with "Reconnect". Before, the view stayed empty without "Hand back", and
// closing it was the only way out, which gave the browser back mid-login.
// Closing the panel still hands back what the user holds, without
// "consensio:workspace-handback"; a dropped connection never closes it.
//
// While the agent has the browser and this tab is hidden for HIDDEN_MS, the
// view lets go (its time counts as VM time, V4: a forgotten view used half a
// day's time) and comes back when the tab does. The head says what is left
// of today's VM time (the server's "connecting" state, left_seconds), and
// while the agent has the browser, the status line names the step it is on
// (agentStep, from agent-activity.js; V6) instead of a fixed sentence.
//
// The picture stands at the top of its place, not in the middle (V5). On a
// narrow panel, while the user has the browser, "100%" shows the page at
// its real size, to pan by dragging (noVNC clipViewport, dragViewport);
// handing back fits it again.
//
// Wide screens (DOCK_QUERY) dock the panel at the right edge beside the
// chat, which narrows and re-centres in the space left of it (the body's
// workspace-view-docked, --workspace-width; workspace-view.css), next to the
// Agent activity panel when that is open and leaves it MIN_WIDTH; else it
// lies over the activity (workspace-view-covers), which waits beneath it
// (UX audit 2026-10-29 G1: at 1280px the panel was 155px wide, its buttons
// over the activity's text). The edge between them drags (or moves with the
// arrow keys) and remembers its width per browser; the chat never gets
// narrower than MIN_CHAT. Narrower screens show it full width.
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
// for, with the button to take over, and keeps saying it once they have the
// browser (G2: the request vanished just when it was needed). In the
// Terminal tab the bar stays while they have the browser, and the green
// edge stays on the browser's picture (G4). Before, only a small toggle in
// the head said so, and Max waited for the agent while it waited for him.
//
// window.App.workspaceView: open({ takeOver }), close(), isOpen(), init()
// (the start screen's Workspace button, the (+) menu's row, the row in
// Settings → Agent), holder(), handBack() (also without an open view, for the
// card in the chat), agentWaits(request or null), agentStep(line or null);
// agent-activity.js opens it from an opened page's card (Open). A change of
// holder is the window's event "consensio:workspace-holder", the hand-back
// button's own "consensio:workspace-handback".
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
  // Tries after a dropped connection, then "Reconnect" (the server allows
  // six views a minute, routers/agent_workspace.py VIEWS_PER_MINUTE).
  const BACKOFF_MS = [1_000, 2_000, 5_000, 10_000];
  // A connection that held this long starts the tries over.
  const STABLE_MS = 30_000;
  // A hidden tab lets the view go after this long while the agent has the browser.
  const HIDDEN_MS = 60_000;
  // The day's time left is counted down this often while the view is open.
  const TIME_MS = 30_000;
  // Below this width the picture is small (1280 pixels wide in the VM): "100%" is offered.
  const FULL_SIZE_BELOW = 1024;
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
    forbidden: 'The workspace is not available on your account.',
    reconnecting: 'Reconnecting…',
    lost: 'The connection to the workspace ended. Reconnect to go on.',
    paused: 'Paused while this tab was in the background, to save your workspace time.',
    watching: 'Watching. Click the screen to take over.',
  };
  // Why the server closed the view, by close code: noVNC owns the socket's
  // messages once it is ready, so these come as codes, not states.
  const CLOSED = { 4410: 'ended', 4409: 'replaced', 4402: 'no_time', 4429: 'too_many' };
  // Closes the view does not try again by itself: the server said why
  // (4403 before it opened, 1011 after "error").
  const FINAL = { ...CLOSED, 4403: 'forbidden', 1011: 'error' };
  // Nothing to try again: "Reconnect" would only hear the same.
  const NO_RETRY = new Set(['no_time', 'forbidden']);
  const TERMINAL = {
    connecting: 'Opening a terminal in the workspace…',
    ready: 'Your terminal in the workspace, with the agent’s rights.',
    ended: 'The terminal ended. Start a new one to go on.',
    lost: 'The connection to the terminal ended. Start a new one to go on.',
    error: 'The terminal is not reachable right now. Try again in a moment.',
    replaced: 'The terminal opened in another window, so this one closed.',
    unavailable: 'The terminal could not load. Reload the page and try again.',
  };
  // One line above the picture, gone while the bar says whose turn it is (G5).
  const HINTS = {
    browser: 'Log in here yourself: the agent never types a password.',
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
  const XK_BACKSPACE = 0xff08;
  const XK_DELETE = 0xffff;
  // The keys a phone's keyboard field sends as they are (X11 keysyms).
  const FIELD_KEYS = { Backspace: XK_BACKSPACE, Enter: XK_RETURN, Tab: XK_TAB, Escape: 0xff1b, Delete: XK_DELETE,
    ArrowLeft: 0xff51, ArrowUp: 0xff52, ArrowRight: 0xff53, ArrowDown: 0xff54, Home: 0xff50, End: 0xff57 };
  // What the keyboard field holds, so a Backspace has something to delete
  // (noVNC's app/ui.js keyboardinputReset does the same).
  const FIELD_FILL = '_'.repeat(40);
  // Shift, Control, Meta, Alt and Super, left and right: still down in the VM
  // from the shortcut, they would turn the text into shortcuts.
  const MODIFIERS = [0xffe1, 0xffe2, 0xffe3, 0xffe4, 0xffe7, 0xffe8, 0xffe9, 0xffea, 0xffeb, 0xffec];
  let view = null;
  // What the agent waits for the user to do in the browser (agentWaits), also before the view opens.
  let waitingFor = null;
  // The step the agent is on, in the page's language (agentStep), or null.
  let agentLine = null;
  // Sockets whose end was handled (ended runs once per socket).
  const endedSockets = new WeakSet();
  let loadRFB = () => import(NOVNC).then(module => module.default);
  let loadTerminal = () => Promise.all([import(XTERM), import(XTERM_FIT)])
    .then(([xterm, fit]) => ({ Terminal: xterm.Terminal, FitAddon: fit.FitAddon }));

  const matches = query => Boolean(window.matchMedia?.(query)?.matches);
  // The window without its scrollbar: where a fixed panel's right edge is.
  const viewportWidth = () => document.documentElement.clientWidth || window.innerWidth;
  function docked() { return matches(DOCK_QUERY); }
  // A finger, not a mouse: the phone's keyboard needs the field.
  function touch() { return matches('(pointer: coarse)'); }
  // The activity panel's width, when it docks too.
  function activityWidth() {
    return document.body.classList.contains('agent-sidebar-open') && matches(WIDE_QUERY) ? ACTIVITY_WIDTH : 0;
  }
  // Beside the activity the panel would get less than MIN_WIDTH: it lies over it.
  function covers() {
    const activity = activityWidth();
    return activity > 0 && viewportWidth() - sidebarOffset() - activity - MIN_CHAT < MIN_WIDTH;
  }
  // What the panel may not cover on the right: the activity panel beside it.
  function rightOffset() {
    return covers() ? 0 : activityWidth();
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
    document.body.classList.toggle('workspace-view-covers', isDocked && covers());
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
      showControls();
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
    showControls();
  }
  function onWindowResize() {
    layout();
    showControls();
  }

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
    // The line and the tools after the tabs; on a narrow panel they take a
    // second row, and title, tabs and the close cross keep the first (V7).
    const tools = node('div', 'workspace-view-tools');
    const status = node('span', 'workspace-view-status', STATES.connecting);
    status.setAttribute('role', 'status');
    // What is left of today's VM time (V4): already in the page's language.
    const time = node('span', 'workspace-view-time');
    time.dataset.i18nSkip = '';
    time.hidden = true;
    const toggle = button('workspace-view-toggle', 'Take over', () => (view?.holder === 'user' ? handBack() : takeOver()));
    toggle.hidden = true;
    // The app's one close cross (foundation.css .close-button, J1).
    const closer = button('close-button workspace-view-close', '', close);
    closer.setAttribute('aria-label', 'Close workspace');
    closer.title = 'Close workspace';
    closer.innerHTML = App.closeIcon?.() || '<svg class="close-icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M4 4l8 8M12 4l-8 8"/></svg>';
    const paster = button('workspace-view-paste', 'Paste', pasteClipboard);
    paster.title = 'Type your clipboard into the page';
    paster.hidden = true;
    const keyboard = button('workspace-view-tool workspace-view-keyboard', 'Keyboard', toggleKeyboard);
    keyboard.title = 'Type into the page with your keyboard';
    keyboard.setAttribute('aria-pressed', 'false');
    // Pressed down, so the field keeps its focus and the keyboard stays open.
    keyboard.addEventListener('pointerdown', event => event.preventDefault());
    keyboard.hidden = true;
    const zoom = button('workspace-view-tool workspace-view-zoom', '100%', toggleFullSize);
    zoom.title = 'Show the page at its real size, to move it by dragging';
    zoom.setAttribute('aria-pressed', 'false');
    zoom.hidden = true;
    tools.append(status, time, paster, keyboard, zoom, toggle);
    head.append(title, tabs, tools, closer);
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
    // The phone's keyboard types here (V1), out of sight like the paste target.
    const keys = node('input', 'workspace-view-paste-target workspace-view-keys');
    keys.type = 'text';
    keys.tabIndex = -1;
    keys.setAttribute('aria-label', 'Type into the page');
    for (const [name, value] of [['autocapitalize', 'off'], ['autocomplete', 'off'], ['autocorrect', 'off'],
      ['spellcheck', 'false'], ['enterkeyhint', 'enter']]) keys.setAttribute(name, value);
    keys.addEventListener('keydown', onFieldKey);
    keys.addEventListener('beforeinput', onFieldBeforeInput);
    keys.addEventListener('input', onFieldInput);
    keys.addEventListener('focus', () => showKeyboard(true));
    keys.addEventListener('blur', () => showKeyboard(false));
    // After a dropped connection: try again now (V2).
    const reconnectButton = button('workspace-view-reconnect', 'Reconnect',
      () => reconnect({ fresh: true }));
    reconnectButton.hidden = true;
    screen.append(skeleton('browser'), cover, pasteTarget, keys, reconnectButton);
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
      showControls();
    });
    panel.append(resizer, head, hint, turn, screen, terminal);
    return { panel, status, time, hint, tabButtons, toggle, paster, keyboard, zoom, cover, pasteTarget, keys, screen,
      terminal, terminalHost, reconnectButton,
      turn, turnSays, turnNote, turnRequest, turnButton, isIdle: false, idle: null, wantControl: false,
      restart, resizer, socket: null, rfb: null, rfbGone: null, RFB: null, holder: 'agent', refresh: null, width: 0,
      tab: 'browser', said: { browser: STATES.connecting, terminal: TERMINAL.connecting }, sayAs: {}, slow: null,
      // The connection (V2, V4): trying, its tries and timer, why it ended for good, paused while hidden.
      connecting: false, again: false, retries: 0, retry: null, readyAt: 0, final: null, paused: false,
      pausing: null, away: null, dayLeft: null, clock: null, full: false, fieldValue: '',
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
    if (view.hint.textContent !== App.t(HINTS[key])) view.hint.textContent = HINTS[key];
    view.panel.dataset.tab = key;
    say(view.said[key], key, view.sayAs[key]);
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
  // Characters as key presses: a line break is Return, a tab Tab, control characters nothing.
  function pressChars(rfb, text) {
    for (const char of text) {
      const code = char.codePointAt(0);
      if (char === '\n') rfb.sendKey(XK_RETURN, null);
      else if (char === '\t') rfb.sendKey(XK_TAB, null);
      else if (code >= 0x20 && !(code >= 0x7f && code < 0xa0)) rfb.sendKey(keysym(code), null);
    }
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
    pressChars(rfb, clean);
    // With the phone's keyboard open, it stays open.
    if (document.activeElement !== view.keys) rfb.focus();
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

  // ---- The phone's keyboard (V1) -------------------------------------------
  function resetField() {
    if (!view) return;
    view.keys.value = FIELD_FILL;
    view.fieldValue = FIELD_FILL;
    try { view.keys.setSelectionRange(FIELD_FILL.length, FIELD_FILL.length); } catch (_) { /* not focusable yet */ }
  }
  // Called inside the button's own click: iOS opens a keyboard only then.
  function toggleKeyboard() {
    if (!pasting()) return;
    if (document.activeElement === view.keys) { view.keys.blur(); return; }
    resetField();
    view.keys.focus({ preventScroll: true });
  }
  // While the field has the focus, a tap on the screen clicks there without taking it away.
  function showKeyboard(open) {
    if (!view) return;
    view.keyboard.setAttribute('aria-pressed', String(open));
    if (view.rfb) view.rfb.focusOnClick = !open;
  }
  function onFieldKey(event) {
    if (!pasting() || event.isComposing || event.keyCode === 229) return;
    const sym = FIELD_KEYS[event.key];
    // Characters come with beforeinput or input; a shortcut is the paste's.
    if (sym === undefined || event.ctrlKey || event.metaKey || event.altKey) return;
    event.preventDefault();
    view.rfb.sendKey(sym, null);
  }
  // Typed text and deletes as they come, where the browser lets them be
  // cancelled; a keyboard's composition changes the field and goes by input.
  function onFieldBeforeInput(event) {
    if (!pasting() || !event.cancelable) return;
    const type = event.inputType;
    if (type === 'insertText' && event.data) {
      event.preventDefault();
      pressChars(view.rfb, event.data);
    } else if (type === 'insertLineBreak' || type === 'insertParagraph') {
      event.preventDefault();
      view.rfb.sendKey(XK_RETURN, null);
    } else if (type === 'deleteContentBackward') {
      event.preventDefault();
      view.rfb.sendKey(XK_BACKSPACE, null);
    } else if (type === 'deleteContentForward') {
      event.preventDefault();
      view.rfb.sendKey(XK_DELETE, null);
    }
  }
  // What changed in the field since last time: as many Backspaces as went,
  // then what came (noVNC's keyInput: also a correction of a whole word).
  function onFieldInput() {
    if (!view) return;
    const field = view.keys;
    const now = field.value;
    const before = view.fieldValue;
    if (pasting()) {
      let same = 0;
      while (same < now.length && same < before.length && now[same] === before[same]) same += 1;
      for (let index = same; index < before.length; index += 1) view.rfb.sendKey(XK_BACKSPACE, null);
      pressChars(view.rfb, now.slice(same));
    }
    view.fieldValue = now;
    if (now.length > FIELD_FILL.length * 2) resetField();
    else if (!now) {
      // Android notices new text in an emptied field only after a new focus.
      resetField();
      field.blur();
      setTimeout(() => field.focus({ preventScroll: true }), 0);
    }
  }

  // ---- Lines in the head -----------------------------------------------------
  // Each tab has its own line; the head shows the open tab's. `raw`: already
  // in the page's language (the agent's step with its target), not translated
  // again. `wrap`: a reason that may take two lines.
  function say(text, key = 'browser', { raw = false, wrap = false } = {}) {
    if (!view) return;
    view.said[key] = text;
    view.sayAs[key] = { raw, wrap };
    if (view.tab !== key) return;
    if (raw) view.status.dataset.i18nSkip = ''; else delete view.status.dataset.i18nSkip;
    view.status.classList.toggle('is-wrapping', wrap);
    view.status.textContent = text;
    // A narrow panel cuts the line: the whole of it on hover.
    view.status.title = text;
  }
  // While the agent has the browser: the step it is on, or the way to take over.
  function sayWatching() {
    if (agentLine) say(agentLine, 'browser', { raw: true });
    else say(STATES.watching);
  }
  // What is left of today's VM time (V4), counted down while the view is open.
  function showTime() {
    if (!view) return;
    const left = view.dayLeft;
    const seconds = left ? left.seconds - (left.at ? (Date.now() - left.at) / 1000 : 0) : null;
    const text = seconds === null ? '' : App.t('{time} left today',
      { time: App.format?.duration?.(Math.max(0, seconds) * 1000, { minutes: true }) || '' });
    if (view.time.textContent !== text) view.time.textContent = text;
    view.time.hidden = !text || view.holder === 'user' || view.tab !== 'browser';
  }
  function setDayLeft(seconds) {
    if (!view) return;
    view.dayLeft = Number.isFinite(seconds) && seconds >= 0 ? { seconds, at: Date.now() } : null;
    showTime();
  }
  function stopDayClock() {
    const left = view?.dayLeft;
    if (!left?.at) return;
    left.seconds = Math.max(0, left.seconds - (Date.now() - left.at) / 1000);
    left.at = 0;
  }

  // Which tools show: the ones the open tab and the holder have use for.
  function showControls() {
    if (!view) return;
    const user = view.holder === 'user';
    const browser = view.tab === 'browser';
    const live = Boolean(view.rfb);
    view.toggle.hidden = !live || !browser || user;
    view.paster.hidden = !live || !user || !browser || !navigator.clipboard?.readText;
    view.keyboard.hidden = !live || !user || !browser || !touch();
    view.zoom.hidden = !live || !user || !browser || (!view.full && view.screen.clientWidth >= FULL_SIZE_BELOW);
    view.cover.hidden = !live || user;
    if (!view.turn.hidden) view.toggle.hidden = true;
    showTime();
  }

  function showHolder() {
    if (!view) return;
    const user = view.holder === 'user';
    view.toggle.textContent = 'Take over';
    view.panel.classList.toggle('is-user', user);
    if (view.rfb) {
      view.rfb.viewOnly = !user;
      // While the user has it, the bar says so: the head stays quiet.
      if (user) say(''); else sayWatching();
    }
    showTurn();
    showControls();
  }

  // The bar: the user's turn (and after IDLE_MS a reminder), or what the
  // agent waits for them to do, or nothing while the agent works. What the
  // agent asked for stays its quiet line while the user has the browser;
  // "The agent waits." only for a takeover nobody asked for (G2). While the
  // connection comes back the user's bar stays, with "Hand back" (V2).
  function showTurn() {
    if (!view) return;
    const user = view.holder === 'user';
    const asked = waitingFor !== null;
    const idle = user && view.isIdle;
    const browser = view.tab === 'browser';
    view.turn.hidden = !(user || (asked && browser && (view.rfb || view.again)));
    // One way to take over or hand back at a time: the bar's, when it shows.
    if (!view.turn.hidden) view.toggle.hidden = true;
    // The hint gives way to the bar: two blocks of words over the picture were one too many (G5).
    view.hint.hidden = !view.turn.hidden;
    view.turn.classList.toggle('is-user', user);
    view.turn.classList.toggle('is-idle', Boolean(idle));
    const says = idle ? 'Done?' : user ? 'You have the browser' : 'The agent is waiting for you';
    const request = asked && !idle ? String(waitingFor || '') : '';
    const note = idle ? 'Hand the browser back so the agent can go on.' : user && !request ? 'The agent waits.' : '';
    if (view.turnSays.textContent !== App.t(says)) view.turnSays.textContent = says;
    if (view.turnNote.textContent !== (note && App.t(note))) view.turnNote.textContent = note;
    view.turnNote.hidden = !note;
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
    // The agent's turn: the picture fits again, the phone's keyboard closes.
    if (holder !== 'user') {
      view.full = false;
      applySize();
      if (document.activeElement === view.keys) view.keys.blur();
    }
    showHolder();
    announceHolder(holder);
  }
  // A page in the background (the 2FA app, a call, a locked phone) may not
  // run its interval: the takeover lapsed after CONTROL_SECONDS and the agent
  // went on mid-login. Back in front, it is refreshed at once and the
  // interval starts over (A-S6; the server no longer takes a lapse for a
  // hand-back while the agent waits for the user). A dropped connection
  // comes back at once (V2); hidden for HIDDEN_MS while the agent has the
  // browser, the view lets go until the tab is back (V4).
  function onVisibility() {
    if (!view) return;
    if (document.visibilityState === 'hidden') {
      if (view.holder !== 'user' && !view.away && !view.paused) view.away = setTimeout(pause, HIDDEN_MS);
      return;
    }
    clearTimeout(view.away);
    view.away = null;
    if (view.holder === 'user') {
      clearInterval(view.refresh);
      view.refresh = setInterval(refreshNow, REFRESH_MS);
      refreshNow();
    }
    nudge();
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
    if (!view || view.holder === 'user') return;
    // No picture right now (it comes back): taken over as soon as there is one.
    if (!view.rfb) { view.wantControl = true; return; }
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
  // The button's hand-back says so to the chat ("consensio:workspace-handback",
  // agent-chat.js continueAfterHandback): the user expects the agent to go on.
  // Closing the view and a lapsed takeover hand back without that.
  async function handBack() {
    if (!view) {
      try {
        await post('/agent/workspace/control', { holder: 'agent' });
        rememberHolder('agent');
        announceHolder('agent');
      } catch (error) {
        App.showPopup?.(App.t('Could not hand back: {reason}', { reason: error.message || 'Try again.' }));
        return;
      }
      window.dispatchEvent(new CustomEvent('consensio:workspace-handback'));
      return;
    }
    if (view.holder !== 'user') return;
    try {
      await setHolder('agent');
    } catch (error) {
      say(App.t('Could not hand back: {reason}', { reason: error.message || 'Try again.' }));
      return;
    }
    window.dispatchEvent(new CustomEvent('consensio:workspace-handback'));
  }

  // The agent waits for the user in the browser (ask_user), or no longer (null).
  function agentWaits(request) {
    const next = request === null || request === undefined ? null : String(request);
    if (next === waitingFor) return;
    waitingFor = next;
    showTurn();
    showControls();
  }
  // The step the agent is on, in the page's language with its target as data
  // (agent-activity.js), or null: the status line names it while the agent
  // has the browser (V6; on a phone the panel covers the chat).
  function agentStep(line) {
    const next = line ? String(line) : null;
    if (next === agentLine) return;
    agentLine = next;
    if (view?.rfb && view.holder !== 'user') sayWatching();
  }

  // ---- The picture's size (V5) -----------------------------------------------
  // Fitted into the panel while the agent works; the page's real size, moved by
  // dragging, while the user has it and asked for it.
  function applySize() {
    if (!view) return;
    const full = view.full && view.holder === 'user';
    const rfb = view.rfb;
    if (rfb) {
      // noVNC: scaling trumps clipping, so it goes first.
      rfb.scaleViewport = !full;
      rfb.clipViewport = full;
      rfb.dragViewport = full;
    }
    view.zoom.setAttribute('aria-pressed', String(full));
    view.zoom.title = full ? 'Fit the page into the panel' : 'Show the page at its real size, to move it by dragging';
    view.panel.classList.toggle('is-full-size', full);
  }
  function toggleFullSize() {
    if (!pasting()) return;
    view.full = !view.full;
    applySize();
    showControls();
  }

  // ---- The connection --------------------------------------------------------
  function connect() {
    const scheme = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const socket = new WebSocket(`${scheme}//${location.host}/agent/workspace/view`);
    view.socket = socket;
    view.connecting = true;
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
      let message = null;
      try { message = JSON.parse(event.data); } catch (error) { return; }
      const state = message?.state;
      if (state !== 'ready') {
        if (state === 'connecting') {
          setDayLeft(Number(message.left_seconds ?? NaN));
          watchSlow();
        }
        // Coming back: "Reconnecting…" stays until the relay says more.
        if (STATES[state] && !(state === 'connecting' && view.again)) say(STATES[state]);
        if (state === 'error') loading('browser', false);
        return;
      }
      clearTimeout(view.slow);
      loading('browser', false);
      view.connecting = false;
      view.again = false;
      view.final = null;
      view.readyAt = Date.now();
      view.reconnectButton.hidden = true;
      // Synchronously, inside this event: noVNC takes over the socket's
      // handlers, so the VNC bytes that follow "ready" all reach it.
      const rfb = new view.RFB(view.screen, socket, { shared: true });
      rfb.scaleViewport = true;
      rfb.resizeSession = false;
      rfb.viewOnly = true;
      // The panel's own tone around the picture, not noVNC's dark grey.
      rfb.background = 'transparent';
      let gone = false;
      rfb.addEventListener('disconnect', () => {
        gone = true;
        // Its socket's close says why (ended); this only covers one that never comes.
        if (view?.rfb === rfb) setTimeout(() => ended(socket, 0), 0);
      });
      view.rfbGone = () => gone;
      view.rfb = rfb;
      applySize();
      if (document.activeElement === view.keys) rfb.focusOnClick = false;
      showHolder();
      // Opened to take over (the agent's card asked for it): as soon as there is a picture.
      if (view.wantControl) takeOver();
    };
    // Before "ready" and after it (noVNC takes over onclose): once per socket.
    socket.onclose = (event) => ended(socket, event.code);
    socket.addEventListener('close', (event) => ended(socket, event.code));
  }
  function ended(socket, code) {
    if (!view || view.socket !== socket || endedSockets.has(socket)) return;
    endedSockets.add(socket);
    clearTimeout(view.slow);
    view.connecting = false;
    stopDayClock();
    const rfb = view.rfb;
    const gone = view.rfbGone?.();
    view.rfb = null;
    view.rfbGone = null;
    if (rfb && !gone) {
      try { rfb.disconnect(); } catch (error) { /* already gone */ }
    }
    if (view.readyAt && Date.now() - view.readyAt >= STABLE_MS) view.retries = 0;
    view.readyAt = 0;
    if (view.pausing === socket) {
      // Let go on purpose while the tab was hidden (pause): back with the tab.
      view.pausing = null;
      view.paused = true;
      loading('browser', true);
      say(STATES.paused);
    } else if (FINAL[code]) {
      stop(FINAL[code]);
    } else {
      retryLater();
    }
    showHolder();
  }
  // The server said why it closed, or the tries are over: the reason in up
  // to two lines and, where trying again can help, "Reconnect".
  function stop(reason) {
    view.final = reason;
    view.again = false;
    clearTimeout(view.retry);
    view.retry = null;
    loading('browser', false);
    view.reconnectButton.hidden = NO_RETRY.has(reason);
    say(STATES[reason], 'browser', { wrap: true });
  }
  function retryLater() {
    if (view.retries >= BACKOFF_MS.length) { stop('lost'); return; }
    view.again = true;
    view.final = null;
    loading('browser', true);
    view.reconnectButton.hidden = true;
    say(STATES.reconnecting);
    clearTimeout(view.retry);
    view.retry = setTimeout(() => reconnect(), BACKOFF_MS[view.retries]);
    view.retries += 1;
  }
  // `fresh`: asked for (the button, the tab or the network back), the tries start over.
  function reconnect({ fresh = false } = {}) {
    if (!view || view.connecting || view.rfb || !view.RFB) return;
    if (fresh) view.retries = 0;
    clearTimeout(view.retry);
    view.retry = null;
    view.again = true;
    view.final = null;
    view.paused = false;
    view.reconnectButton.hidden = true;
    loading('browser', true);
    say(STATES.reconnecting);
    connect();
    showTurn();
  }
  // Back in front or online: a view that lost its connection tries at once.
  function nudge() {
    if (!view || view.rfb || view.connecting) return;
    if (view.paused || view.retry || view.final === 'lost') reconnect({ fresh: true });
  }
  // The tab was hidden for HIDDEN_MS while the agent had the browser: the
  // view lets go, so it stops counting as VM time, until the tab is back.
  function pause() {
    if (!view) return;
    view.away = null;
    if (view.holder === 'user' || document.visibilityState !== 'hidden' || !(view.rfb || view.connecting)) return;
    clearTimeout(view.retry);
    view.retry = null;
    const socket = view.socket;
    view.pausing = socket;
    const rfb = view.rfb;
    if (rfb && !view.rfbGone?.()) {
      try { rfb.disconnect(); } catch (error) { /* already gone */ }
    }
    try { socket?.close(); } catch (error) { /* already gone */ }
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
      endTerminal(event.code === 4403 ? STATES.forbidden
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
      // Opened again after the connection ended: it tries again, unless trying
      // cannot help; a view another window took over comes back only when
      // the user opens it here, not for the agent's request (renderHold).
      if (!view.rfb && !view.connecting && !NO_RETRY.has(view.final) && !(take && view.final === 'replaced')) {
        reconnect({ fresh: true });
      }
      return;
    }
    view = build();
    // The account it shows (onAuthState closes it for any other).
    view.uid = window.auth?.currentUser?.uid || null;
    view.wantControl = Boolean(take);
    // The chat's card for the agent's question steps aside while the view is open (agent-chat.js renderHold).
    announceHolder(view.holder);
    document.body.append(view.panel);
    document.body.classList.add('workspace-view-open');
    showTab('browser');
    watchSlow();
    layout();
    window.addEventListener('resize', onWindowResize);
    view.clock = setInterval(showTime, TIME_MS);
    // The Agent activity panel opening or closing beside it moves its right
    // edge, or lets it lie over the activity.
    view.right = activityWidth();
    view.observer = new MutationObserver(() => {
      if (!view || view.right === activityWidth()) return;
      view.right = activityWidth();
      layout();
      showControls();
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
    if (!view) return;
    view.RFB = RFB;
    connect();
  }

  function close() {
    if (!view) return;
    const closing = view;
    view = null;
    clearInterval(closing.refresh);
    clearInterval(closing.clock);
    clearTimeout(closing.slow);
    clearTimeout(closing.idle);
    clearTimeout(closing.retry);
    clearTimeout(closing.away);
    // The agent may go on at once; an unsent hand-back expires by itself
    // (also after a logout: never with another account's token).
    if (closing.holder === 'user' && closing.uid === (window.auth?.currentUser?.uid || null)) {
      post('/agent/workspace/control', { holder: 'agent' }).catch(() => {});
    }
    rememberHolder('agent');
    announceHolder('agent');
    if (document.activeElement === closing.keys) closing.keys.blur();
    try { closing.rfb?.disconnect(); } catch (error) { /* already gone */ }
    try { closing.socket?.close(); } catch (error) { /* already gone */ }
    // The shell ends shortly after its socket (TERMINAL_AFTER_DISCONNECT).
    try { closing.termSocket?.close(); } catch (error) { /* already gone */ }
    closing.termResize?.disconnect();
    try { closing.term?.dispose(); } catch (error) { /* already gone */ }
    window.removeEventListener('resize', onWindowResize);
    closing.observer?.disconnect();
    leave(closing.panel);
    document.body.classList.remove('workspace-view-open', 'workspace-view-docked', 'workspace-view-covers', 'workspace-view-resizing');
    document.body.style.removeProperty('--workspace-width');
  }
  // It leaves the way it came (Apple audit C5): folds back into the right
  // edge from where it stood while the chat takes its lane back
  // (workspace-view.css). Until 2026-10-29 it was gone at once. Its place is
  // held inline, since the body's classes that dock it go at once.
  function leave(panel) {
    if (App.motion?.reduced?.() || !panel.isConnected) { panel.remove(); return; }
    const box = panel.getBoundingClientRect();
    Object.assign(panel.style, { boxSizing: 'border-box', left: `${box.left}px`, right: 'auto', width: `${box.width}px`,
      borderLeft: getComputedStyle(panel).borderLeft });
    panel.inert = true;
    panel.classList.add('is-leaving');
    // Gone when its way out ends: the chat's new lane can hold back its
    // first frame, and a fixed timer cut it off before it showed (docked,
    // 2026-10-29). The timer only covers a way out that never runs.
    const gone = () => panel.remove();
    panel.addEventListener('animationend', event => { if (event.target === panel) gone(); });
    setTimeout(gone, (App.motion?.ms?.('layer') ?? 320) * 2);
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
    actions.append(button('text-link agent-github-link', 'Open workspace', open),
      button('text-link agent-github-link', 'Log out everywhere', () => resetBrowser(status)));
    host.append(status, actions);
    host._workspace = true;
  }

  App.workspaceView = {
    open, close, init, handBack, agentWaits, agentStep,
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
  document.addEventListener('visibilitychange', onVisibility);
  window.addEventListener('online', nudge);
  // The account is known (auth-session-state.js): a takeover from before a
  // reload is taken up again, also when that was said before this script ran.
  // A logout does not reload the page: the view of an account that is no
  // longer signed in here closes, with its sockets (until 2026-10-30 its
  // Chrome stayed in the next person's hands, and its refresh claimed the
  // browser of whoever signed in next).
  window.addEventListener('consensio:auth-state', (event) => {
    if (view && view.uid !== (event.detail?.uid || null)) close();
    returnToHolder();
  });
  if (window.__consensioAuthState?.known) returnToHolder();
})();
