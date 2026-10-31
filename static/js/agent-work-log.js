// The agent's work log in the activity sidebar (admins; every chat run
// since 2026-10-31; agent_work_log.py, docs/agent-work-log.md). Folded until
// opened; then it loads the entries in order and, while the turn runs,
// follows them. Each entry shows who, what and where its content came from;
// its content opens on demand, the whole of a long one with "Show all".
(function () {
  "use strict";
  const App = window.App = window.App || {};
  const KINDS = { start: 'Start', context: 'Context', step: 'Step', tool: 'Tool', app: 'App', end: 'End' };
  const DATA = { user: 'User', web: 'Web', file: 'File', google: 'Google', memory: 'Memory', agent: 'Model', vm: 'VM',
    app: 'App' };
  // Content from outside the user and the app: data, never instructions.
  const UNTRUSTED = new Set(['web', 'file', 'google', 'agent', 'vm']);
  const POLL_MS = 3000;
  const PAGE = 200;
  const logs = new Map();

  function node(tag, className, text) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (text !== undefined) el.textContent = text;
    return el;
  }
  function stateFor(view) {
    let log = logs.get(view.key);
    if (!log) {
      log = { entries: new Map(), after: 0, loading: false, error: '', incomplete: false, loaded: false, timer: 0, open: false };
      logs.set(view.key, log);
      while (logs.size > 24) logs.delete(logs.keys().next().value);
    }
    return log;
  }
  async function fetchLog(view, suffix) {
    const authorized = () => view.user === window.auth?.currentUser && view.authGeneration === App.authState?.generation
      && !view.controller.signal.aborted;
    if (!authorized()) throw new Error('Account changed');
    const data = await App.withRequestDeadline(async signal => {
      const token = await window.auth.currentUser.getIdToken();
      if (!authorized() || signal.aborted) throw new Error('Account changed');
      const response = await fetch(`/agent/chats/${encodeURIComponent(view.chatId)}/turns/${encodeURIComponent(view.turnId)}/work-log${suffix}`,
        { headers: { Authorization: `Bearer ${token}` }, signal });
      if (!response.ok) throw App.httpError(response, await App.readJson(response).catch(() => ({})));
      return App.readJson(response);
    }, { signal: view.controller.signal });
    if (!authorized()) throw new Error('Account changed');
    return data;
  }
  async function load(host, view) {
    const log = stateFor(view);
    if (log.loading) return;
    log.loading = true;
    try {
      let more = true;
      while (more) {
        const data = await fetchLog(view, `?after=${log.after}&limit=${PAGE}`);
        for (const entry of data.entries || []) {
          if (!Number.isInteger(entry.seq)) continue;
          log.entries.set(entry.seq, entry);
          log.after = Math.max(log.after, entry.seq);
        }
        log.incomplete = Boolean(data.incomplete);
        more = Boolean(data.has_more);
      }
      log.loaded = true; log.error = '';
    } catch (error) {
      log.error = App.userError(error, { fallback: 'The work log couldn’t be loaded. Try again.' });
    } finally {
      log.loading = false;
      paint(host, view);
      // The run ended while this load was on its way: once more, for its last entries.
      if (log.reloadAfter && host._view === view) { log.reloadAfter = false; load(host, view); }
      else schedule(host, view);
    }
  }
  const live = view => Boolean(view.running || view.settling);
  // While the turn runs and its log is open and on screen, new entries
  // arrive by polling. A hidden panel or tab, another turn or a closed log
  // stops it; the sidebar's next render starts it again.
  function onScreen(host, view) {
    return stateFor(view).open && host.isConnected && host._view === view && !host.closest('[hidden]')
      && document.visibilityState !== 'hidden';
  }
  function schedule(host, view) {
    const log = stateFor(view);
    clearTimeout(log.timer); log.timer = 0;
    if (!onScreen(host, view) || !live(view)) return;
    log.timer = setTimeout(() => {
      log.timer = 0;
      // Checked again when due: the panel may have closed meanwhile.
      if (onScreen(host, view)) load(host, view);
    }, POLL_MS);
  }
  function detach(host) {
    if (host?._view) clearTimeout(stateFor(host._view).timer);
    if (host?._view) stateFor(host._view).timer = 0;
    if (host) { host._view = null; host._box = null; host.replaceChildren(); }
  }
  function pretty(entry, text) {
    if (entry.format !== 'json' || entry.ref || entry.truncated) return text;
    try { return JSON.stringify(JSON.parse(text), null, 2); } catch (_) { return text; }
  }
  function actorLabel(actor) {
    if (actor === 'agent') return 'Agent';
    if (actor === 'app') return 'App';
    return String(actor || '').startsWith('worker:') ? 'Worker' : String(actor || '');
  }
  function entryRow(view, entry) {
    const item = node('li', 'agent-work-log-entry');
    item.dataset.kind = entry.kind; item.dataset.data = entry.data;
    const details = node('details');
    const summary = node('summary');
    const seq = node('span', 'agent-work-log-seq', `#${entry.seq}`);
    // One word per element, each translated on its own (docs/i18n.md).
    const actor = node('span', 'agent-work-log-actor', actorLabel(entry.actor));
    const kind = node('span', 'agent-work-log-kind', KINDS[entry.kind] || entry.kind);
    summary.append(seq, actor, kind);
    if (entry.name) {
      const name = node('code', 'agent-work-log-name', entry.name);
      name.setAttribute('data-i18n-skip', '');
      summary.append(name);
    }
    const badge = node('span', 'agent-work-log-data', DATA[entry.data] || entry.data);
    if (UNTRUSTED.has(entry.data)) badge.classList.add('is-untrusted');
    summary.append(badge);
    const time = node('time', 'agent-work-log-time');
    if (Number.isFinite(Date.parse(entry.at))) {
      time.dateTime = entry.at;
      time.textContent = App.format?.time(entry.at) || '';
    }
    summary.append(time);
    details.append(summary);
    // The content is built when opened: a long log stays light.
    details.addEventListener('toggle', () => {
      if (!details.open || details._filled) return;
      details._filled = true;
      const content = node('pre', 'agent-work-log-content', pretty(entry, String(entry.content || '')));
      content.setAttribute('data-i18n-skip', '');
      details.append(content);
      if (entry.ref || entry.truncated) {
        const note = node('p', 'agent-work-log-note', entry.ref
          ? App.t('Shortened: {shown} of {total} characters.', { shown: String(entry.content || '').length, total: entry.chars })
          : 'Shortened: the full content could not be stored.');
        details.append(note);
      }
      if (entry.ref) {
        const all = node('button', 'agent-work-log-more', 'Show all'); all.type = 'button';
        all.addEventListener('click', async () => {
          all.disabled = true;
          try {
            const full = await fetchLog(view, `/${entry.seq}`);
            if (full.content_unavailable) { all.hidden = true; return; }
            content.textContent = pretty({ ...entry, ref: null }, String(full.content || ''));
            all.remove(); details.querySelector('.agent-work-log-note')?.remove();
          } catch (error) {
            all.disabled = false;
            all.title = App.userError(error, { fallback: 'This entry couldn’t be loaded. Try again.' });
          }
        });
        details.append(all);
      }
    });
    item.append(details);
    return item;
  }
  function paint(host, view) {
    const box = host._box;
    if (!box || host._view !== view) return;
    const log = stateFor(view);
    const last = log.entries.get(log.after);
    // A finished run whose log has no end lost its last entries.
    const gap = log.incomplete || (log.loaded && !live(view) && log.entries.size > 0 && last?.kind !== 'end');
    box.status.textContent = log.error || (!log.loaded ? 'Loading…'
      : !log.entries.size ? (live(view) ? 'Waiting for the first entries…' : 'No work log for this response.')
      : gap ? 'Some entries could not be saved; the log is incomplete.' : '');
    box.status.hidden = !box.status.textContent;
    const shown = new Set([...box.list.children].map(child => Number(child.dataset.seq)));
    for (const [seq, entry] of [...log.entries].sort((a, b) => a[0] - b[0])) {
      if (shown.has(seq)) continue;
      const row = entryRow(view, entry); row.dataset.seq = String(seq);
      box.list.append(row);
    }
    box.count.textContent = log.entries.size ? String(log.entries.size) : '';
  }
  // Called by the sidebar on every render with its host element and the
  // turn it shows (agent-delegation.js); ``view.workLog`` says the turn has
  // a log (or, running, writes one).
  function render(host, view) {
    if (!host) return;
    host.hidden = !view?.workLog || view.local;
    if (host.hidden) { detach(host); return; }
    if (host._view !== view) {
      detach(host);
      host._view = view;
      const details = node('details', 'agent-work-log');
      const summary = node('summary', 'agent-work-log-summary');
      const title = node('span', '', 'Work log');
      const count = node('span', 'agent-work-log-count');
      summary.append(title, count);
      const status = node('p', 'agent-work-log-status'); status.setAttribute('role', 'status');
      const list = node('ol', 'agent-work-log-list');
      details.append(summary, status, list);
      host._box = { details, status, list, count };
      host.replaceChildren(details);
      const log = stateFor(view);
      details.open = log.open;
      details.addEventListener('toggle', () => {
        log.open = details.open;
        if (details.open) load(host, view);
        else schedule(host, view);
      });
      paint(host, view);
      if (log.open) load(host, view);
      log.wasLive = live(view);
      return;
    }
    // Live: keep polling. A run that just ended: load its last entries once
    // (after the load on its way, if there is one).
    const log = stateFor(view);
    const now = live(view);
    if (log.open && now && !log.loading && !log.timer) schedule(host, view);
    else if (log.open && !now && log.wasLive) {
      if (log.loading) log.reloadAfter = true;
      else load(host, view);
    }
    log.wasLive = now;
    paint(host, view);
  }
  // Another account: nothing of the previous one's logs stays.
  function reset(host) {
    for (const log of logs.values()) clearTimeout(log.timer);
    logs.clear();
    detach(host);
    if (host) host.hidden = true;
  }
  App.agentWorkLog = { render, reset, KINDS };
})();
