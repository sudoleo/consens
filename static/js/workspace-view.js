// The account's workspace live (routers/agent_workspace.py, agent_workspace.py,
// docs/agent-mode.md "Arbeitsplatz"): its Chrome in a panel beside the chat,
// through noVNC (static/vendor/novnc, loaded when the panel first opens).
// The user watches; a click on the screen takes the browser over, and the
// agent waits (workspace_vm/browser.py) until "Hand back". While the user has
// it, the panel refreshes the takeover every REFRESH_MS; a closed tab lets it
// expire by itself. Sign-ins happen here, by the user: the agent never types
// a password.
//
// Wide screens (DOCK_QUERY) dock the panel at the right edge beside the
// chat, which narrows and re-centres in the space left of it (the body's
// workspace-view-docked, --workspace-width; workspace-view.css), next to the
// Agent activity panel when that is open. The edge between them drags (or
// moves with the arrow keys) and remembers its width per browser; the chat
// never gets narrower than MIN_CHAT. Narrower screens show it full width.
//
// window.App.workspaceView: open(), close(), isOpen(), init() (the start
// screen's Workspace button, the (+) menu's row, the row in Settings → Agent);
// agent-activity.js opens it from a browser step ("Watch live").
(function () {
  'use strict';
  const App = window.App = window.App || {};
  const NOVNC = '/static/vendor/novnc/1.7.0/core/rfb.js';
  const REFRESH_MS = 30_000;
  const STATES = {
    connecting: 'Connecting to the workspace…',
    setup: 'Setting up the browser (once, about a minute)…',
    starting: 'Starting the browser…',
    error: 'The workspace is not reachable right now. Try again in a moment.',
    ended: 'The view closed after an hour. Open it again to go on.',
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
  let view = null;
  let loadRFB = () => import(NOVNC).then(module => module.default);

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

  function build() {
    const panel = node('aside', 'workspace-view');
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-label', 'Workspace');
    const head = node('header', 'workspace-view-head');
    const title = node('strong', 'workspace-view-title', 'Workspace');
    const status = node('span', 'workspace-view-status', STATES.connecting);
    status.setAttribute('role', 'status');
    const toggle = button('workspace-view-toggle', 'Take over', () => (view?.holder === 'user' ? handBack() : takeOver()));
    toggle.hidden = true;
    const closer = button('workspace-view-close', '', close);
    closer.setAttribute('aria-label', 'Close workspace');
    closer.title = 'Close workspace';
    closer.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18"/></svg>';
    head.append(title, status, toggle, closer);
    const hint = node('p', 'workspace-view-hint',
      'Log in to sites here yourself: the agent then works there as you, and never types a password.');
    const screen = node('div', 'workspace-view-screen');
    const cover = button('workspace-view-cover', '', takeOver);
    cover.setAttribute('aria-label', 'Take over the browser');
    cover.title = 'Click to take over';
    cover.hidden = true;
    screen.append(cover);
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
    panel.append(resizer, head, hint, screen);
    return { panel, status, toggle, cover, screen, resizer, socket: null, rfb: null, holder: 'agent', refresh: null,
      width: 0 };
  }

  function say(text) {
    if (!view) return;
    view.status.textContent = text;
    // A narrow panel cuts the line: the whole of it on hover.
    view.status.title = text;
  }

  function showHolder() {
    if (!view) return;
    const user = view.holder === 'user';
    view.toggle.hidden = !view.rfb;
    view.toggle.textContent = user ? 'Hand back' : 'Take over';
    view.toggle.classList.toggle('is-user', user);
    view.cover.hidden = !view.rfb || user;
    view.panel.classList.toggle('is-user', user);
    if (view.rfb) {
      view.rfb.viewOnly = !user;
      say(user ? 'You have the browser. The agent waits until you hand it back.'
        : 'Watching. Click the screen to take over.');
    }
  }

  async function setHolder(holder) {
    await post('/agent/workspace/control', { holder });
    if (!view) return;
    view.holder = holder;
    clearInterval(view.refresh);
    view.refresh = holder === 'user'
      ? setInterval(() => post('/agent/workspace/control', { holder: 'user' }).catch(() => {}), REFRESH_MS) : null;
    showHolder();
  }

  async function takeOver() {
    if (!view?.rfb || view.holder === 'user') return;
    try {
      await setHolder('user');
      view?.rfb?.focus();
    } catch (error) {
      say(App.t('Could not take over: {reason}', { reason: error.message || 'Try again.' }));
    }
  }

  async function handBack() {
    if (!view || view.holder !== 'user') return;
    try {
      await setHolder('agent');
    } catch (error) {
      say(App.t('Could not hand back: {reason}', { reason: error.message || 'Try again.' }));
    }
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
        return;
      }
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
    };
    socket.onclose = (event) => {
      if (!view || view.socket !== socket || view.rfb) return;
      say(event.code === 4403 ? 'The workspace is not available on your account.'
        : view.status.textContent === STATES.ended ? STATES.ended
          : 'The connection to the workspace ended. Close and open it again.');
    };
  }

  async function open() {
    if (view) {
      view.panel.hidden = false;
      return;
    }
    view = build();
    document.body.append(view.panel);
    document.body.classList.add('workspace-view-open');
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
    // The agent may go on at once; an unsent hand-back expires by itself.
    if (closing.holder === 'user') post('/agent/workspace/control', { holder: 'agent' }).catch(() => {});
    try { closing.rfb?.disconnect(); } catch (error) { /* already gone */ }
    try { closing.socket?.close(); } catch (error) { /* already gone */ }
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
    open, close, init,
    isOpen: () => Boolean(view),
    width: () => view?.width || 0,
    // Tests replace the noVNC import.
    _setLoader(loader) { loadRFB = loader; },
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
