// The Watches page (/app/watches). Since 2026-11-03 a Watch runs the Agent
// on a schedule in its chat (agent_watches.py), and the page is where its
// findings arrive: grouped by what they want from the reader (Needs you,
// New, Running, Paused, then Ended folded away), each a row that opens its
// chat. "…" pauses, resumes, chooses where it writes (mail, Telegram) and
// ends it. Below: where the messages go (the account's mail, Telegram), and
// the Consensus Watches from before as a quiet archive with their pages.
//
// Contract (watch.js calls these at view time): window.App.watchDashboard.
// {render, refresh, renderGuest, renderSkeleton, focusWatch, addCreated,
// commitPending, reset}. Data: GET /agent/watches, GET /api/my/watches (the
// archive), GET /api/my/telegram. Opening a row opens its chat
// (window.openBookmark) and marks its finding seen.
(function () {
  'use strict';
  const App = window.App = window.App || {};
  const ui = () => App.watchUi;
  const TIMED = new Set(['daily', 'weekly']);
  const MENU_ICON = '<svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true">'
    + '<circle cx="5.5" cy="12" r="1.6"/><circle cx="12" cy="12" r="1.6"/><circle cx="18.5" cy="12" r="1.6"/></svg>';
  const EYE = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 12s3.5-6 9-6 9 6 9 6-3.5 6-9 6-9-6-9-6Z"/>'
    + '<circle cx="12" cy="12" r="2.5"/></svg>';
  const CHEVRON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 6 6 6-6 6"/></svg>';
  // The sections, in the order the reader meets them.
  const SECTIONS = [
    ['needs', 'Needs you'],
    ['new', 'New'],
    ['running', 'Running'],
    ['paused', 'Paused'],
  ];

  const page = { token: 0, data: null, archive: [], telegram: null, focus: '', menu: null, showEnded: false };

  function el(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }

  function data(tag, className, text) {
    // The task and a finding are the reader's or the model's words.
    const element = el(tag, className, text);
    element.setAttribute('data-i18n-skip', '');
    return element;
  }

  function body() {
    return document.getElementById('watchDashBody');
  }

  // --- what a Watch is right now ------------------------------------------

  function stateOf(watch) {
    if (watch.unread && watch.last_run?.outcome === 'needs_you' && watch.status !== 'done') return 'needs';
    if (watch.unread) return 'new';
    if (watch.status === 'active') return 'running';
    if (watch.status === 'paused') return 'paused';
    return 'ended';
  }

  function scheduleOf(watch) {
    if (watch.interval === 'hourly') return App.t('Every hour');
    if (watch.interval === 'every_6_hours') return App.t('Every 6 hours');
    return App.watchFields?.scheduleLabel ? App.watchFields.scheduleLabel(watch) : watch.interval;
  }

  function firstRunPending(watch) {
    return watch.status === 'active' && !watch.last_run && Date.parse(watch.next_run_at || '') <= Date.now() + 60000;
  }

  // The one line under the task: what its last run found, or where it stands.
  function lineOf(watch) {
    const last = watch.last_run;
    const summary = last?.summary || '';
    if (watch.status === 'done') {
      if (watch.ended === 'goal') return summary || App.t('It reached its goal.');
      if (watch.ended === 'chat_gone') return App.t('Its chat was deleted.');
      return summary || App.t('Ended.');
    }
    if (last?.outcome === 'needs_you') return summary || App.t('A reviewer stopped a run. Open the chat to decide.');
    if (['finding', 'done'].includes(last?.outcome) && summary) return summary;
    if (watch.status === 'paused') return App.t('Paused. It runs again once you resume it.');
    if (firstRunPending(watch)) return App.t('Its first run is under way.');
    if (!last) return App.t('Nothing yet. It looks for the first time {when}.', { when: App.format.upcoming(watch.next_run_at) });
    if (last.outcome === 'quiet') return App.t('Nothing new.');
    return App.t('The last run did not finish. It tries again on schedule.');
  }

  function metaOf(watch) {
    if (watch.status === 'done') return App.t(watch.ended === 'goal' ? 'Reached its goal' : 'Ended');
    const parts = [scheduleOf(watch)];
    if (watch.status === 'active' && watch.next_run_at && !firstRunPending(watch)) {
      parts.push(App.t('next run {when}', { when: App.format.upcoming(watch.next_run_at) }));
    }
    if (watch.status === 'paused') parts.push(App.t('paused'));
    return parts.join(' · ');
  }

  function whenOf(watch) {
    const at = watch.last_run?.at;
    return at ? App.format.relative(at) : '';
  }

  // --- rows -----------------------------------------------------------------

  function picture(watch) {
    const frame = el('span', 'aw-picture');
    const image = watch.image;
    if (image?.url) {
      frame.classList.add('is-' + (['item', 'article', 'logo'].includes(image.kind) ? image.kind : 'item'));
      const img = el('img');
      img.src = image.url;
      img.alt = '';
      img.loading = 'lazy';
      img.decoding = 'async';
      frame.append(img);
    } else {
      frame.classList.add('is-symbol');
      frame.innerHTML = EYE;
    }
    return frame;
  }

  function row(watch) {
    const state = stateOf(watch);
    const item = el('li', 'aw-row is-' + state);
    item.dataset.watchId = watch.id;
    const open = el('button', 'aw-open');
    open.type = 'button';
    const text = el('span', 'aw-text');
    const title = data('span', 'aw-title', watch.task);
    const line = data('span', 'aw-line', lineOf(watch));
    const meta = el('span', 'aw-meta', metaOf(watch));
    meta.setAttribute('data-i18n-skip', '');
    text.append(title, line, meta);
    const side = el('span', 'aw-side');
    const when = el('span', 'aw-when', whenOf(watch));
    when.setAttribute('data-i18n-skip', '');
    side.append(when);
    if (state === 'needs' || state === 'new') {
      const dot = el('span', 'aw-dot');
      dot.setAttribute('aria-hidden', 'true');
      side.append(dot);
    }
    const chevron = el('span', 'aw-chevron');
    chevron.innerHTML = CHEVRON;
    side.append(chevron);
    open.append(picture(watch), text, side);
    // What a screen reader hears: the state, the task, the line.
    const status = state === 'needs' ? App.t('Needs you') : state === 'new' ? App.t('New finding') : '';
    open.setAttribute('aria-label', [status, watch.task, lineOf(watch)].filter(Boolean).join('. '));
    open.addEventListener('click', () => openChat(watch));
    const more = el('button', 'aw-more');
    more.type = 'button';
    more.innerHTML = MENU_ICON;
    more.setAttribute('aria-label', App.t('Options for this Watch'));
    more.setAttribute('aria-haspopup', 'menu');
    more.setAttribute('aria-expanded', 'false');
    more.addEventListener('click', event => {
      event.stopPropagation();
      if (page.menu?.button === more) closeMenu({ focus: true });
      else showMenu(more, watch, { keyboard: event.detail === 0 });
    });
    item.append(open, more);
    return item;
  }

  function section(key, label, watches) {
    const box = el('section', 'aw-section is-' + key);
    const head = el('h2', 'aw-section-title', label);
    head.id = 'awSection-' + key;
    box.setAttribute('aria-labelledby', head.id);
    const list = el('ul', 'aw-list');
    watches.forEach(watch => list.append(row(watch)));
    box.append(head, list);
    return box;
  }

  function endedSection(watches) {
    const box = el('section', 'aw-section is-ended');
    const toggle = el('button', 'aw-disclosure');
    toggle.type = 'button';
    toggle.setAttribute('aria-expanded', String(page.showEnded));
    toggle.textContent = App.t(page.showEnded ? 'Hide ended Watches' : 'Show ended Watches ({count})', { count: watches.length });
    const list = el('ul', 'aw-list');
    list.hidden = !page.showEnded;
    if (page.showEnded) watches.forEach(watch => list.append(row(watch)));
    toggle.addEventListener('click', () => { page.showEnded = !page.showEnded; draw(); });
    box.append(toggle, list);
    return box;
  }

  // --- the archive and the messages ------------------------------------------

  function archiveSection() {
    const watches = page.archive;
    const box = el('details', 'aw-archive');
    const summary = el('summary', 'aw-archive-summary');
    summary.append(el('span', '', App.t('Earlier Watches')), el('span', 'aw-archive-count', String(watches.length)));
    const note = el('p', 'aw-archive-note',
      App.t('Before Watches ran the Agent, they asked a question again on a schedule. They are archived: nothing checks them any more, and their pages stay as they last were.'));
    const list = el('ul', 'aw-archive-list');
    for (const watch of watches) {
      const item = el('li', 'aw-archive-row');
      const link = data('a', 'aw-archive-link', watch.question || '');
      link.href = watch.share_path || '/app/watches';
      const when = watch.last_run_at || watch.updated_at || watch.created_at;
      item.append(link);
      if (when) item.append(el('span', 'aw-archive-when', App.t('Last checked {date}', { date: App.format.date(when) })));
      list.append(item);
    }
    box.append(summary, note, list);
    return box;
  }

  function telegramRow() {
    const state = page.telegram || {};
    const item = el('div', 'aw-channel');
    const copy = el('div', 'aw-channel-copy');
    copy.append(el('span', 'aw-channel-title', 'Telegram'));
    const note = el('p', 'aw-channel-note');
    copy.append(note);
    const actions = el('div', 'aw-channel-actions');
    item.append(copy, actions);
    const button = (label, handler, className = 'wd-button') => {
      const control = el('button', className, label);
      control.type = 'button';
      control.addEventListener('click', handler);
      actions.append(control);
      return control;
    };
    if (!state.configured) {
      note.textContent = App.t('Telegram is not available right now.');
      return item;
    }
    if (state.connected) {
      const name = state.telegram_username ? '@' + state.telegram_username : (state.telegram_first_name || '');
      note.textContent = name ? App.t('Connected to {name}. Each Watch writes there too, unless you turn it off in its menu.', { name })
        : App.t('Connected. Each Watch writes there too, unless you turn it off in its menu.');
      button(App.t('Send test'), async function () {
        this.disabled = true;
        try {
          await ui().api('POST', '/api/my/telegram/test', {});
          App.toast?.({ message: App.t('A test message is on its way.') });
        } catch (error) {
          App.toast?.({ message: App.userError(error, { fallback: 'Try again.' }) });
        } finally { this.disabled = false; }
      });
      button(App.t('Disconnect'), async function () {
        const confirmed = await App.confirm({ title: App.t('Disconnect Telegram?'),
          body: App.t('Your Watches then write only by email.'), confirmLabel: App.t('Disconnect'), danger: true });
        if (!confirmed) return;
        this.disabled = true;
        try {
          const result = await ui().api('DELETE', '/api/my/telegram', {});
          page.telegram = result.telegram || { configured: true, connected: false };
          App.watchState?.setTelegram?.(page.telegram);
          draw();
        } catch (error) {
          this.disabled = false;
          App.toast?.({ message: App.userError(error, { fallback: 'Try again.' }) });
        }
      }, 'text-link');
      return item;
    }
    const idle = App.t('Get what your Watches find as a chat message too.');
    note.textContent = idle;
    const connect = button(App.t('Connect Telegram'), () => {
      ui().connectTelegram(next => {
        page.telegram = next;
        App.watchState?.setTelegram?.(next);
        draw();
      });
    });
    const cancel = button(App.t('Cancel'), () => ui().cancelTelegramPairing(), 'text-link');
    const sync = status => {
      const waiting = status === 'waiting';
      connect.disabled = waiting;
      connect.textContent = App.t(waiting ? 'Waiting for Telegram…' : 'Connect Telegram');
      cancel.hidden = !waiting;
      note.textContent = waiting ? App.t('Press Start in Telegram. This updates by itself.') : idle;
    };
    const unsubscribe = ui().onTelegramStatus?.(status => {
      if (!item.isConnected) { unsubscribe?.(); return; }
      sync(status);
    });
    sync(ui().telegramStatus?.());
    return item;
  }

  function channelsSection() {
    const box = el('section', 'aw-channels');
    box.setAttribute('aria-labelledby', 'awChannelsTitle');
    const head = el('h2', 'aw-section-title', App.t('Messages'));
    head.id = 'awChannelsTitle';
    const mail = el('div', 'aw-channel');
    const copy = el('div', 'aw-channel-copy');
    copy.append(el('span', 'aw-channel-title', App.t('Email')));
    const address = window.auth?.currentUser?.email || '';
    copy.append(el('p', 'aw-channel-note', address
      ? App.t('A Watch writes to {address} when a run finds something, needs you, or reaches its goal.', { address })
      : App.t('A Watch writes when a run finds something, needs you, or reaches its goal.')));
    mail.append(copy);
    box.append(head, mail, telegramRow());
    return box;
  }

  // --- the page ---------------------------------------------------------------

  function syncHead() {
    const limit = document.getElementById('watchDashLimit');
    const info = page.data;
    if (!limit) return;
    if (!info) {
      limit.hidden = true;
      return;
    }
    limit.hidden = false;
    limit.replaceChildren(el('span', 'aw-limit', App.t('{count} of {limit} Watches running',
      { count: info.active_count, limit: info.active_limit })));
  }

  function emptyState() {
    const box = el('section', 'aw-empty');
    const glyph = el('span', 'aw-empty-glyph');
    glyph.innerHTML = EYE;
    const start = el('button', 'wd-button is-primary', App.t('New Watch'));
    start.type = 'button';
    start.addEventListener('click', () => App.watchSheet?.open({ trigger: start, source: 'empty' }));
    box.append(glyph, el('h2', 'aw-empty-title', App.t('Nothing watched yet')),
      el('p', 'aw-empty-text', App.t('Ask the Agent in any chat to keep an eye on something, or start a Watch here. It looks on a schedule and tells you only when it finds something.')),
      start);
    return box;
  }

  function draw() {
    const host = body();
    if (!host || !page.data) return;
    closeMenu();
    const watches = Array.isArray(page.data.watches) ? page.data.watches : [];
    const groups = { needs: [], new: [], running: [], paused: [], ended: [] };
    watches.forEach(watch => groups[stateOf(watch)].push(watch));
    // Newest finding first; a running Watch by its next run.
    const latest = (a, b) => String(b.last_run?.at || b.created_at || '').localeCompare(String(a.last_run?.at || a.created_at || ''));
    groups.needs.sort(latest);
    groups.new.sort(latest);
    groups.ended.sort(latest);
    groups.running.sort((a, b) => String(a.next_run_at || '').localeCompare(String(b.next_run_at || '')));
    const fragment = document.createDocumentFragment();
    if (!watches.length) fragment.append(emptyState());
    for (const [key, label] of SECTIONS) {
      if (groups[key].length) fragment.append(section(key, App.t(label), groups[key]));
    }
    if (groups.ended.length) fragment.append(endedSection(groups.ended));
    fragment.append(channelsSection());
    if (page.archive.length) fragment.append(archiveSection());
    host.replaceChildren(fragment);
    host.removeAttribute('aria-busy');
    syncHead();
    if (page.focus) focusWatch(page.focus);
  }

  async function load() {
    const token = ++page.token;
    const [agent, archive, telegram] = await Promise.all([
      ui().api('GET', '/agent/watches'),
      // Shared with watch.js's own load of the list (one GET, review 2).
      ui().requestWatchList().catch(() => ({ watches: [] })),
      ui().api('GET', '/api/my/telegram').catch(() => ({ telegram: page.telegram || {} })),
    ]);
    if (token !== page.token) return false;
    page.data = agent;
    page.archive = (Array.isArray(archive.watches) ? archive.watches : []).filter(watch => watch.question);
    page.telegram = telegram.telegram || { configured: false, connected: false };
    App.watchState?.setTelegram?.(page.telegram);
    return true;
  }

  async function render() {
    const host = body();
    if (!host) return;
    if (!page.data) renderSkeleton();
    try {
      if (await load()) draw();
    } catch (error) {
      if (page.data) return;
      host.replaceChildren(failureNote(App.userError(error, { fallback: 'Watches could not be loaded. Try again.' })));
      host.removeAttribute('aria-busy');
    }
  }

  function failureNote(message) {
    const box = el('div', 'aw-alert');
    box.setAttribute('role', 'alert');
    box.append(el('p', '', message));
    const retry = el('button', 'wd-button', App.t('Try again'));
    retry.type = 'button';
    retry.addEventListener('click', () => render());
    box.append(retry);
    return box;
  }

  function renderGuest(message) {
    page.token += 1;
    page.data = null;
    const host = body();
    if (!host) return;
    syncHead();
    const box = el('section', 'aw-empty');
    const glyph = el('span', 'aw-empty-glyph');
    glyph.innerHTML = EYE;
    const signIn = el('button', 'wd-button is-primary', App.t('Log in'));
    signIn.type = 'button';
    signIn.addEventListener('click', () => ui()?.requireAccount?.({}, signIn));
    box.append(glyph, el('h2', 'aw-empty-title', App.t('Let the Agent keep an eye on things')),
      el('p', 'aw-empty-text', message || App.t('A Watch runs the Agent on a schedule: it checks a page, a price or the news for you and tells you only when it finds something.')),
      signIn);
    host.replaceChildren(box);
    host.removeAttribute('aria-busy');
  }

  function renderSkeleton() {
    const host = body();
    if (!host) return;
    host.innerHTML = App.watchSkeleton?.() || '<div class="wd-skeleton skeleton-group" role="status" aria-label="Loading your watches"></div>';
    host.setAttribute('aria-busy', 'true');
  }

  function focusWatch(id) {
    page.focus = String(id || '');
    const target = page.focus && body()?.querySelector(`.aw-row[data-watch-id="${CSS.escape(page.focus)}"] .aw-open`);
    if (!target) return;
    page.focus = '';
    target.scrollIntoView({ block: 'center', behavior: App.motion?.reduced?.() ? 'auto' : 'smooth' });
    target.focus({ preventScroll: true });
    target.closest('.aw-row')?.classList.add('is-focused');
    setTimeout(() => target.closest('.aw-row')?.classList.remove('is-focused'), 1600);
  }

  // --- acting on one --------------------------------------------------------

  function replace(watch) {
    if (!page.data || !watch) return;
    const list = page.data.watches || [];
    const index = list.findIndex(item => item.id === watch.id);
    if (index >= 0) list[index] = watch;
    else list.unshift(watch);
    page.data.active_count = list.filter(item => item.status === 'active').length;
    draw();
  }

  async function act(watch, path, options = {}) {
    try {
      const result = await ui().api(options.method || 'POST', `/agent/watches/${encodeURIComponent(watch.id)}${path}`, options.body || {});
      replace(result.watch);
      window.dispatchEvent(new CustomEvent('consensio:agent-watches-changed', { detail: { watch: result.watch } }));
      return result.watch;
    } catch (error) {
      App.toast?.({ message: App.userError(error, { fallback: 'Try again.' }) });
      return null;
    }
  }

  function openChat(watch) {
    if (watch.unread) act(watch, '/seen');
    if (firstRunPending(watch) || !watch.bookmark_id) {
      App.toast?.({ message: App.t('Its first run is under way. Its chat appears in a moment.') });
      return;
    }
    window.openBookmark?.(watch.bookmark_id);
  }

  async function end(watch) {
    const confirmed = await App.confirm({ title: App.t('End this Watch?'),
      body: App.t('It stops running. Its chat and what it found stay.'), confirmLabel: App.t('End Watch'), danger: true });
    if (confirmed) act(watch, '/stop');
  }

  function menuItems(watch) {
    const telegram = page.telegram?.connected === true;
    const items = [['open', App.t('Open chat')]];
    if (watch.status === 'active') items.push(['pause', App.t('Pause')]);
    if (watch.status === 'paused') items.push(['resume', App.t('Resume')]);
    if (watch.status !== 'done') {
      items.push(['email', App.t('Email'), watch.email_enabled]);
      if (telegram) items.push(['telegram', 'Telegram', watch.telegram_enabled]);
      items.push(['end', App.t('End Watch')]);
    }
    return items;
  }

  function showMenu(button, watch, { keyboard = false } = {}) {
    closeMenu();
    const menu = el('div', 'bookmark-menu aw-menu');
    menu.setAttribute('role', 'menu');
    menu.setAttribute('aria-label', App.t('Options for this Watch'));
    for (const [action, label, checked] of menuItems(watch)) {
      const item = el('button', 'bookmark-menu-item' + (action === 'end' ? ' is-destructive' : ''));
      item.type = 'button';
      item.tabIndex = -1;
      item.dataset.action = action;
      if (checked === undefined) item.setAttribute('role', 'menuitem');
      else {
        item.setAttribute('role', 'menuitemcheckbox');
        item.setAttribute('aria-checked', String(Boolean(checked)));
      }
      const mark = el('span', 'aw-menu-check');
      mark.setAttribute('aria-hidden', 'true');
      mark.textContent = checked ? '✓' : '';
      item.append(mark, el('span', '', label));
      menu.append(item);
    }
    App.popover?.register(menu, { close: () => closeMenu() });
    App.popover?.opened(menu, { trigger: button });
    document.body.append(menu);
    const bounds = button.getBoundingClientRect();
    const width = menu.offsetWidth, height = menu.offsetHeight;
    const below = bounds.bottom + 4 + height <= window.innerHeight - 8;
    menu.style.left = `${Math.max(8, Math.min(bounds.right - width, window.innerWidth - width - 8))}px`;
    menu.style.top = `${below ? bounds.bottom + 4 : Math.max(8, bounds.top - 4 - height)}px`;
    menu.classList.toggle('opens-up', !below);
    button.setAttribute('aria-expanded', 'true');
    button.closest('.aw-row')?.classList.add('has-menu');
    page.menu = { menu, button };
    const items = [...menu.querySelectorAll('.bookmark-menu-item')];
    const focusItem = index => items[(index + items.length) % items.length]?.focus({ preventScroll: true });
    menu.addEventListener('keydown', event => {
      const index = items.indexOf(document.activeElement);
      if (event.key === 'ArrowDown') { event.preventDefault(); focusItem(index + 1); }
      else if (event.key === 'ArrowUp') { event.preventDefault(); focusItem(index - 1); }
      else if (event.key === 'Home') { event.preventDefault(); focusItem(0); }
      else if (event.key === 'End') { event.preventDefault(); focusItem(items.length - 1); }
      else if (event.key === 'Escape') { event.preventDefault(); closeMenu({ focus: true }); }
      else if (event.key === 'Tab') closeMenu();
    });
    menu.addEventListener('click', event => {
      const item = event.target.closest('.bookmark-menu-item');
      if (!item) return;
      event.stopPropagation();
      const action = item.dataset.action;
      closeMenu({ focus: action !== 'end' });
      if (action === 'open') openChat(watch);
      else if (action === 'pause') act(watch, '/pause');
      else if (action === 'resume') act(watch, '/resume');
      else if (action === 'email') act(watch, '', { method: 'PATCH', body: { email_enabled: !watch.email_enabled } });
      else if (action === 'telegram') act(watch, '', { method: 'PATCH', body: { telegram_enabled: !watch.telegram_enabled } });
      else if (action === 'end') end(watch);
    });
    menu.tabIndex = -1;
    if (keyboard) focusItem(0);
    else menu.focus({ preventScroll: true });
  }

  function closeMenu({ focus = false } = {}) {
    if (!page.menu) return;
    const { menu, button } = page.menu;
    page.menu = null;
    if (App.popover) {
      App.popover.leave(menu, () => {
        App.popover.unregister(menu);
        menu.remove();
      });
    } else menu.remove();
    button.setAttribute('aria-expanded', 'false');
    button.closest('.aw-row')?.classList.remove('has-menu');
    if (focus && button.isConnected) button.focus({ preventScroll: true });
  }

  function addCreated(watch) {
    if (watch?.task) replace(watch);
  }

  function reset() {
    page.token += 1;
    page.data = null;
    page.archive = [];
    page.telegram = null;
    page.showEnded = false;
    closeMenu();
  }

  // A Watch started on the sheet, changed on a card or in another tab: the
  // open page shows it at once; back on the tab, it reads again.
  window.addEventListener('consensio:agent-watches-changed', event => {
    if (!page.data || event.detail?.loaded) return;
    if (event.detail?.watch) replace(event.detail.watch);
  });
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible' && page.data && document.getElementById('watchDashboard')?.hidden === false) {
      load().then(fresh => { if (fresh) draw(); }).catch(() => {});
    }
  });
  App.watchDashboard = {
    render, refresh: render, renderGuest, renderSkeleton, focusWatch, addCreated,
    // The page keeps nothing pending (deleting is "End", taken back by no Undo).
    commitPending() {}, reset,
  };
})();
