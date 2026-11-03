// The sheet that starts a Watch in the user's own words (since 2026-11-03,
// agent_watches.py): "New Watch" on the Watches page opens a chat of its own
// for it (its first run starts at once), the Watch pill under an answer
// starts one in that chat. What the Agent should do, when it is done and how
// often; Start sends it to POST /agent/watches. The Watch the Agent prepared
// itself has its card under the answer instead (agent-watch.js).
//
//   App.watchSheet.open({ chatId, task, trigger, onStarted })
(function () {
  'use strict';
  const App = window.App = window.App || {};
  const INTERVALS = ['hourly', 'every_6_hours', 'daily', 'weekly'];
  const TIMED = new Set(['daily', 'weekly']);
  const DEFAULT_TIME = '08:00';
  const TASK_MAX = 500;
  const GOAL_MAX = 200;
  let sheet = null;
  let current = null;

  function node(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }

  function timezone() {
    try { return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'; } catch (_) { return 'UTC'; }
  }

  function intervalLabel(value) {
    if (value === 'hourly') return App.t('Every hour');
    if (value === 'every_6_hours') return App.t('Every 6 hours');
    return App.watchFields?.scheduleLabel ? App.watchFields.scheduleLabel({ interval: value }) : value;
  }

  async function request(path, options = {}) {
    const user = window.auth?.currentUser;
    if (!user) throw new Error('Log in first.');
    const token = await user.getIdToken();
    const response = await fetch(path, { ...options, headers: { Authorization: `Bearer ${token}`,
      ...(options.body ? { 'Content-Type': 'application/json' } : {}), ...options.headers } });
    const data = await App.readJson(response).catch(() => ({}));
    if (!response.ok) throw App.httpError(response, data);
    return data;
  }

  function field(id, label, control, hint) {
    const wrap = node('div', 'watch-sheet-field');
    const caption = node('label', 'watch-sheet-label', label);
    caption.htmlFor = id;
    control.id = id;
    wrap.append(caption, control);
    if (hint) wrap.append(node('p', 'watch-sheet-hint', hint));
    return wrap;
  }

  function build() {
    if (sheet?.dialog.isConnected) return sheet;
    const dialog = node('dialog', 'modal watch-sheet');
    dialog.setAttribute('aria-labelledby', 'watchSheetTitle');
    const content = node('form', 'modal-content watch-sheet-content');
    content.noValidate = true;
    const title = node('h2', 'watch-sheet-title', 'New Watch');
    title.id = 'watchSheetTitle';
    const lead = node('p', 'watch-sheet-lead');
    const task = node('textarea', 'watch-sheet-task');
    task.rows = 3;
    task.maxLength = TASK_MAX;
    task.placeholder = 'Check whether registration for IRONMAN Hamburg 2027 is open.';
    task.setAttribute('data-i18n-skip', '');
    const goal = node('input', 'watch-sheet-goal');
    goal.type = 'text';
    goal.maxLength = GOAL_MAX;
    goal.placeholder = 'Registration is open';
    goal.setAttribute('data-i18n-skip', '');
    const interval = node('select', 'watch-sheet-interval');
    const time = node('input', 'watch-sheet-time');
    time.type = 'time';
    time.value = DEFAULT_TIME;
    time.setAttribute('aria-label', 'Time');
    const error = node('p', 'watch-sheet-error');
    error.setAttribute('role', 'alert');
    error.hidden = true;
    const cancel = node('button', 'text-link watch-sheet-cancel', 'Cancel');
    cancel.type = 'button';
    const start = node('button', 'wd-button is-primary watch-sheet-start', 'Start Watch');
    start.type = 'submit';
    const actions = node('div', 'watch-sheet-actions');
    actions.append(cancel, start);
    // How often, with the time beside it in one row.
    const often = field('watchSheetInterval', 'How often', interval);
    const when = node('div', 'watch-sheet-when');
    often.append(when);
    when.append(interval, time);
    content.append(title, lead,
      field('watchSheetTask', 'What should the Agent do?', task),
      field('watchSheetGoal', 'Done when', goal, 'Optional. Without it, the Watch runs until you end it.'),
      often, error, actions);
    dialog.append(content);
    document.body.append(dialog);
    App.modalDialog?.bind(dialog, { onClose: () => { current = null; } });
    cancel.addEventListener('click', () => close());
    interval.addEventListener('change', () => { time.hidden = !TIMED.has(interval.value); });
    content.addEventListener('submit', event => { event.preventDefault(); submit(); });
    task.addEventListener('input', () => { error.hidden = true; });
    sheet = { dialog, title, lead, task, goal, interval, time, error, start, cancel };
    return sheet;
  }

  function fillIntervals(allowed, preferred) {
    const list = allowed.filter(value => INTERVALS.includes(value));
    const values = list.length ? list : ['daily', 'weekly'];
    sheet.interval.replaceChildren(...values.map(value => {
      const option = node('option', '', intervalLabel(value));
      option.value = value;
      return option;
    }));
    sheet.interval.value = values.includes(preferred) ? preferred : values.includes('daily') ? 'daily' : values[0];
    sheet.time.hidden = !TIMED.has(sheet.interval.value);
  }

  function close() {
    if (!sheet) return;
    if (App.modalDialog) App.modalDialog.close(sheet.dialog);
    else sheet.dialog.removeAttribute('open');
    current = null;
  }

  function busy(value) {
    sheet.start.disabled = value;
    sheet.start.textContent = App.t(value ? 'Starting…' : 'Start Watch');
    sheet.cancel.disabled = value;
  }

  async function submit() {
    if (!current || sheet.start.disabled) return;
    const task = sheet.task.value.replace(/\s+/g, ' ').trim();
    if (task.length < 8) {
      sheet.error.textContent = App.t('Say in a sentence what the Agent should do.');
      sheet.error.hidden = false;
      sheet.task.focus();
      return;
    }
    const interval = sheet.interval.value;
    const payload = { task, goal: sheet.goal.value.replace(/\s+/g, ' ').trim(), interval,
      run_time: TIMED.has(interval) ? sheet.time.value || DEFAULT_TIME : '', timezone: timezone(),
      ...(current.chatId ? { chat_id: current.chatId } : {}) };
    const opened = current;
    busy(true);
    sheet.error.hidden = true;
    try {
      const data = await request('/agent/watches', { method: 'POST', body: JSON.stringify(payload) });
      if (current !== opened) return;
      close();
      App.trackAppEvent?.('app_watch_created', { interval: data.watch.interval, source: opened.source || 'sheet',
        has_goal: Boolean(data.watch.goal), goal_source: data.watch.goal ? 'own' : 'none' });
      App.toast?.({ message: opened.chatId ? App.t('Watch started. It runs in this chat.')
        : App.t('Watch started. Its first run is under way.') });
      window.dispatchEvent(new CustomEvent('consensio:agent-watches-changed', { detail: { watch: data.watch } }));
      opened.onStarted?.(data.watch);
    } catch (error) {
      if (current !== opened) return;
      sheet.error.textContent = App.userError(error, { fallback: 'Try again.' });
      sheet.error.hidden = false;
    } finally {
      if (sheet) busy(false);
    }
  }

  async function open({ chatId = '', task = '', trigger = null, source = '', onStarted = null } = {}) {
    if (!window.auth?.currentUser) {
      App.watchUi?.requireAccount?.({ question: task }, trigger);
      return;
    }
    build();
    current = { chatId: String(chatId || ''), source, onStarted };
    sheet.title.textContent = App.t('New Watch');
    sheet.lead.textContent = App.t(current.chatId
      ? 'The Agent runs this again in this chat and tells you only when it finds something.'
      : 'The Agent runs this in a chat of its own, starting now, and tells you only when it finds something.');
    sheet.task.value = String(task || '').replace(/\s+/g, ' ').trim().slice(0, TASK_MAX);
    sheet.goal.value = '';
    sheet.error.hidden = true;
    busy(false);
    fillIntervals(['daily', 'weekly'], 'daily');
    sheet.time.value = DEFAULT_TIME;
    if (App.modalDialog) App.modalDialog.open(sheet.dialog, { focus: sheet.task.value ? sheet.goal : sheet.task, opener: trigger });
    else sheet.dialog.setAttribute('open', '');
    // The account's intervals (Free daily, Plus every 6 hours, Pro hourly).
    const opened = current;
    try {
      const data = await request('/agent/watches' + (opened.chatId ? `?chat_id=${encodeURIComponent(opened.chatId)}` : ''));
      if (current !== opened) return;
      fillIntervals(Array.isArray(data.intervals) ? data.intervals : [], sheet.interval.value);
      if (data.active_count >= data.active_limit) {
        sheet.error.textContent = App.t('All your Watches are in use. End one first.');
        sheet.error.hidden = false;
      }
    } catch (_) {
      // The defaults stand; Start says what the server refuses.
    }
  }

  App.watchSheet = { open, close };
})();
