// GitHub for the agent's VM (agent_github.py, routers/agent_github.py).
// Two places: Settings, where a user connects their installation of the
// GitHub app (a popup like Google's: install page, callback, finish), and the
// pull request card under an answer whose agent prepared one. The card shows
// what would go to GitHub; only "Create pull request" sends it, and the
// backend checks the files against this preview first. Repository, branches,
// paths, the title and the diff are data and stay untranslated.
(function () {
  'use strict';
  const App = window.App = window.App || {};
  const MAX_FILES_SHOWN = 20;
  const views = new WeakMap();
  // A decision made in this page wins over the turn the chat still holds.
  const decided = new Map();
  let pending = null;
  let settingsLoaded = false;

  function uid() { return window.auth?.currentUser?.uid || ''; }
  function node(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }
  function data(tag, className, text) {
    const element = node(tag, className, text);
    element.translate = false;
    element.dataset.i18nSkip = '';
    return element;
  }
  function button(className, text, handler) {
    const element = node('button', className, text);
    element.type = 'button';
    element.addEventListener('click', handler);
    return element;
  }
  function failed(error) { return App.userError ? App.userError(error, { fallback: 'Try again.' }) : String(error?.message || error); }
  async function request(path, options = {}) {
    const user = window.auth?.currentUser;
    if (!user) throw new Error('Log in first.');
    const token = await user.getIdToken();
    const response = await fetch(path, { ...options, headers: { Authorization: `Bearer ${token}`, ...options.headers } });
    if (!response.ok) throw App.httpError(response, await App.readJson(response).catch(() => ({})));
    return response.status === 204 ? {} : response.json();
  }
  const post = (path, body) => request(path, { method: 'POST', body: JSON.stringify(body || {}),
    headers: { 'Content-Type': 'application/json' } });

  // ---- Settings: connect and disconnect --------------------------------------
  function settingsView() {
    const host = document.getElementById('agentGithubSettings');
    if (!host) return null;
    if (!host._github) {
      const status = node('p', 'agent-github-status');
      status.setAttribute('role', 'status');
      const repos = data('p', 'agent-github-repos');
      const actions = node('div', 'agent-github-actions');
      const connectButton = button('text-link agent-github-link', 'Connect GitHub', connect);
      const disconnectButton = button('text-link agent-github-link', 'Disconnect', disconnect);
      const manage = node('a', 'text-link agent-github-link', 'Manage on GitHub');
      manage.target = '_blank'; manage.rel = 'noopener noreferrer';
      actions.append(connectButton, disconnectButton, manage);
      host.append(status, repos, actions);
      host._github = { status, repos, connectButton, disconnectButton, manage };
    }
    return host._github;
  }
  function showConnection(info) {
    const view = settingsView();
    if (!view) return;
    const repos = Array.isArray(info?.repositories) ? info.repositories : [];
    view.status.textContent = info?.configured === false ? 'GitHub is not set up on this installation yet.'
      : info?.connected ? App.t('Connected as {account}.', { account: info.login || 'GitHub' }) : 'Not connected.';
    view.repos.textContent = info?.connected ? repos.slice(0, 12).join(', ') + (repos.length > 12 ? ` … (${repos.length})` : '') : '';
    view.repos.hidden = !view.repos.textContent;
    view.connectButton.hidden = info?.configured === false;
    view.connectButton.textContent = info?.connected ? 'Connect again' : 'Connect GitHub';
    view.disconnectButton.hidden = !info?.connected;
    view.manage.hidden = !info?.connected;
    view.manage.href = info?.manage_url || 'https://github.com/settings/installations';
  }
  async function loadConnection() {
    if (!settingsView() || !uid()) return;
    try { showConnection(await request('/agent/github/connection')); settingsLoaded = true; }
    catch (error) { const view = settingsView(); if (view) view.status.textContent = failed(error); }
  }
  // Must open the window inside the click (popup blockers).
  function connect() {
    const popup = window.open('about:blank', 'consens-github', 'popup,width=1020,height=780');
    if (!popup) { App.showPopup?.('Allow the connection window to open, then try again.'); return; }
    (async () => {
      try {
        const result = await post('/agent/github/connect');
        pending = { state: result.state, uid: uid(), popup, authorize: result.authorize_url, authorizing: false };
        popup.location.href = result.install_url;
      } catch (error) { popup.close(); App.showPopup?.(failed(error)); }
    })();
  }
  window.addEventListener('message', async event => {
    if (!pending || event.origin !== location.origin || event.source !== pending.popup
      || event.data?.type !== 'consens-github-oauth') return;
    if (event.data.state && event.data.state !== pending.state) return;
    if (!event.data.code && !event.data.error && !pending.authorizing) {
      // An installation that already existed: GitHub's authorization next,
      // which always brings a code and the state back.
      pending.authorizing = true;
      pending.popup.location.href = pending.authorize;
      return;
    }
    const current = pending; pending = null;
    if (current.uid !== uid()) { current.popup.close(); return; }
    try {
      if (!event.data.code) throw new Error('GitHub authorization was not completed. Nothing was connected.');
      const info = await post('/agent/github/finish', { state: current.state, code: event.data.code });
      current.popup.close();
      showConnection(info);
      const count = (info.repositories || []).length;
      App.showPopup?.(count === 1 ? 'GitHub connected with 1 repository.'
        : App.t('GitHub connected with {count} repositories.', { count }));
    } catch (error) { current.popup.close(); App.showPopup?.(failed(error)); }
  });
  async function disconnect() {
    try {
      const info = await request('/agent/github/connection', { method: 'DELETE' });
      showConnection(info);
      App.showPopup?.(info.notice || 'GitHub disconnected.');
    } catch (error) { App.showPopup?.(failed(error)); }
  }
  // Loaded once the section is on screen (Settings is a dialog).
  function watchSettings() {
    const host = document.getElementById('agentGithubSettings');
    if (!host || host._watched) return;
    host._watched = true;
    settingsView();
    if (typeof IntersectionObserver !== 'function') { loadConnection(); return; }
    const observer = new IntersectionObserver(entries => {
      if (entries.some(entry => entry.isIntersecting) && !settingsLoaded) loadConnection();
    });
    observer.observe(host);
  }

  // ---- The pull request card -------------------------------------------------
  const TITLES = { pending: 'Pull request ready for review', executing: 'Creating the pull request…',
    succeeded: 'Pull request created', failed: 'Pull request not created', discarded: 'Pull request discarded' };
  const MARKS = { added: '+', deleted: '−', modified: '~' };

  function create(key) {
    const card = node('section', 'agent-pr-card');
    const title = node('p', 'agent-pr-title');
    title.id = `agentPrTitle${Math.random().toString(36).slice(2, 8)}`;
    card.setAttribute('aria-labelledby', title.id);
    const target = data('p', 'agent-pr-target');
    const name = data('p', 'agent-pr-name');
    const description = data('p', 'agent-pr-body');
    const files = data('ul', 'agent-pr-files');
    const more = node('p', 'agent-pr-more');
    const details = node('details', 'agent-pr-diff');
    const summary = node('summary', '', 'Show the changes');
    const diff = data('pre', 'agent-pr-diff-text');
    details.append(summary, diff);
    const status = node('p', 'agent-pr-status');
    status.setAttribute('role', 'status');
    const link = node('a', 'text-link agent-pr-open');
    link.target = '_blank'; link.rel = 'noopener noreferrer';
    const view = { key, card, title, target, name, description, files, more, details, diff, status, link, busy: false };
    view.create = button('wd-button is-primary agent-pr-create', 'Create pull request', () => decide(view, 'create'));
    view.discard = button('text-link agent-pr-link', 'Discard', () => decide(view, 'discard'));
    const actions = node('div', 'agent-pr-actions');
    actions.append(view.create, view.discard, link);
    card.append(title, target, name, description, files, more, details, status, actions);
    return view;
  }
  function place(body, card) {
    let anchor = body._agentReview?.parentNode === body.parentNode ? body._agentReview : body;
    while (anchor.nextElementSibling && anchor.nextElementSibling !== card
        && /agent-(memory-note|watch-card|settings-card)/.test(anchor.nextElementSibling.className)) anchor = anchor.nextElementSibling;
    if (anchor.nextElementSibling !== card) anchor.after(card);
  }
  function sync(view) {
    const proposal = view.proposal;
    const expired = proposal.status === 'pending' && String(proposal.approval_until || '') < new Date().toISOString();
    view.card.dataset.state = proposal.status;
    view.title.textContent = TITLES[proposal.status] || TITLES.pending;
    view.target.textContent = `${proposal.repo} · ${proposal.branch} → ${proposal.base}`;
    view.name.textContent = proposal.title || '';
    view.description.textContent = proposal.body || '';
    view.description.hidden = !proposal.body;
    const list = Array.isArray(proposal.files) ? proposal.files : [];
    // With a cut diff every file is listed: nothing goes up unseen.
    const shown = proposal.diff_truncated ? list : list.slice(0, MAX_FILES_SHOWN);
    view.files.replaceChildren(...shown.map(file => {
      const li = node('li');
      li.dataset.change = file.change;
      const counts = Number.isInteger(file.additions) ? ` +${file.additions} −${file.deletions ?? 0}` : '';
      li.textContent = `${MARKS[file.change] || '~'} ${file.path}${counts}`;
      return li;
    }));
    view.more.textContent = list.length > shown.length ? App.t('and {count} more files', { count: list.length - shown.length }) : '';
    view.more.hidden = !view.more.textContent;
    view.diff.textContent = (proposal.diff || '') + (proposal.diff_truncated ? '\n…' : '');
    view.details.hidden = !proposal.diff;
    const result = proposal.result || {};
    view.status.textContent = proposal.status === 'failed' ? proposal.error || 'The pull request could not be created.'
      : proposal.status === 'discarded' ? 'Nothing went to GitHub.'
        : expired ? 'This preview has expired. Ask the agent to prepare the pull request again.'
          : proposal.status === 'pending' ? 'Nothing goes to GitHub until you create the pull request. It opens a new branch, never changes an existing one.' : '';
    view.status.hidden = !view.status.textContent;
    view.link.hidden = proposal.status !== 'succeeded' || !String(result.url || '').startsWith('https://github.com/');
    view.link.href = view.link.hidden ? '' : result.url;
    view.link.textContent = Number.isInteger(result.number) ? App.t('Open pull request #{number} on GitHub', { number: result.number })
      : 'Open on GitHub';
    const open = proposal.status === 'pending' && !expired;
    view.create.hidden = view.discard.hidden = !open;
    view.create.disabled = view.discard.disabled = view.busy;
    view.create.textContent = view.busy ? 'Creating…' : 'Create pull request';
  }
  async function decide(view, choice) {
    if (view.busy) return;
    const proposal = view.proposal;
    view.busy = true;
    sync(view);
    try {
      const path = `/agent/chats/${encodeURIComponent(view.chatId)}/turns/${encodeURIComponent(view.turnId)}/pull-request`;
      const result = await post(choice === 'create' ? path : `${path}/discard`, { expected_hash: proposal.hash });
      view.proposal = { ...proposal, ...result.pull_request };
      decided.set(`${view.key}:${proposal.hash}`, view.proposal);
    } catch (error) {
      view.proposal = { ...proposal };
      App.showPopup?.(failed(error));
    } finally {
      view.busy = false;
      sync(view);
    }
  }
  function render(body, { key = '', proposal = null, chatId = '', turnId = '' } = {}) {
    if (!body) return;
    let view = views.get(body);
    const valid = proposal && typeof proposal === 'object' && proposal.repo && proposal.hash;
    if (view && (!valid || view.key !== key)) { view.card.remove(); views.delete(body); view = null; }
    if (!valid) return;
    if (!view) { view = create(key); views.set(body, view); }
    view.chatId = chatId; view.turnId = turnId;
    const known = decided.get(`${key}:${proposal.hash}`);
    if (!view.busy) view.proposal = known && proposal.status === 'pending' ? known : proposal;
    place(body, view.card);
    sync(view);
  }

  App.agentGithub = { render, loadConnection };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', watchSettings, { once: true });
  else watchSettings();
})();
