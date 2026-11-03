// Where the workspace's browser is logged in (since 2026-11-02), in Settings
// → Connections: the sites the Agent noted (note_sign_in,
// agent_workspace.sign_ins), each with the day it was first noted. Removing
// one only takes it off the list; logging out happens on the site itself or
// everywhere (workspace-view.js resetBrowser, which reloads this list). Site
// names are data and stay untranslated.
(function () {
  'use strict';
  const App = window.App = window.App || {};
  // A reopened Settings reads the list again, not on every scroll past it.
  const FRESH_MS = 5000;
  let loadedAt = 0;
  let loading = null;

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
  function failed(error) { return App.userError ? App.userError(error, { fallback: 'Try again.' }) : String(error?.message || error); }
  async function request(path, options = {}) {
    const user = window.auth?.currentUser;
    if (!user) throw new Error('Log in first.');
    const token = await user.getIdToken();
    const response = await fetch(path, { ...options, headers: { Authorization: `Bearer ${token}`, ...options.headers } });
    if (!response.ok) throw App.httpError(response, await App.readJson(response).catch(() => ({})));
    return response.json();
  }

  function view() {
    const host = document.getElementById('agentSignInsSettings');
    if (!host) return null;
    if (!host._signIns) {
      const list = node('ul', 'agent-sign-ins-list');
      const status = node('p', 'agent-sign-ins-status');
      status.setAttribute('role', 'status');
      host.append(list, status);
      host._signIns = { list, status };
    }
    return host._signIns;
  }
  function since(day) {
    const shown = day && App.format?.date ? App.format.date(`${day}T00:00:00`) : '';
    return shown ? App.t('Since {date}', { date: shown }) : '';
  }
  function show(entries) {
    const parts = view();
    if (!parts) return;
    parts.list.replaceChildren(...entries.map(entry => {
      const item = node('li', 'agent-sign-in');
      const text = node('span', 'agent-sign-in-text');
      text.append(data('span', 'agent-sign-in-name', entry.name || entry.site),
        data('span', 'agent-sign-in-site', entry.site));
      const day = since(entry.since);
      if (day) text.append(node('span', 'agent-sign-in-since', day));
      const remove = node('button', 'text-link agent-sign-in-remove', 'Remove');
      remove.type = 'button';
      remove.setAttribute('aria-label', App.t('Remove {site} from the list', { site: entry.name || entry.site }));
      remove.addEventListener('click', () => removeSite(entry.site, remove));
      item.append(text, remove);
      return item;
    }));
    parts.list.hidden = !entries.length;
    parts.status.textContent = entries.length ? ''
      : 'No sites yet. When you log in to a site in the workspace’s browser, the Agent notes it here.';
  }
  function load(force = false) {
    if (!view() || !window.auth?.currentUser) return Promise.resolve();
    if (loading) return loading;
    if (!force && Date.now() - loadedAt < FRESH_MS) return Promise.resolve();
    loading = request('/agent/workspace/sign-ins')
      .then(body => { loadedAt = Date.now(); show(Array.isArray(body?.sign_ins) ? body.sign_ins : []); })
      .catch(error => { const parts = view(); if (parts) parts.status.textContent = failed(error); })
      .finally(() => { loading = null; });
    return loading;
  }
  async function removeSite(site, control) {
    control.disabled = true;
    try {
      const body = await request('/agent/workspace/sign-ins/remove', { method: 'POST', body: JSON.stringify({ site }),
        headers: { 'Content-Type': 'application/json' } });
      loadedAt = Date.now();
      show(Array.isArray(body?.sign_ins) ? body.sign_ins : []);
    } catch (error) {
      control.disabled = false;
      const parts = view();
      if (parts) parts.status.textContent = failed(error);
    }
  }

  // Read when the row comes into view: hidden without a workspace, it never does.
  function watch() {
    const host = document.getElementById('agentSignInsSettings');
    if (!host || host._watched) return;
    host._watched = true;
    view();
    if (typeof IntersectionObserver !== 'function') { load(); return; }
    new IntersectionObserver(entries => {
      if (entries.some(entry => entry.isIntersecting)) load();
    }).observe(host);
  }

  App.agentSignIns = { load, show };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', watch, { once: true });
  else watch();
})();
