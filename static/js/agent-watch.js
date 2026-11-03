// The Watch the Agent prepared (agent_watch.py) as a card under the answer.
// Since 2026-11-03 a Watch runs the Agent again on a schedule in this chat
// (agent_watches.py): the card shows its task, its goal and when it runs,
// and Start sends only the chat, the turn and the schedule to POST
// /agent/watches, which reads the task from the saved turn. "Change" opens
// how often and when; a running Watch says when it runs next and what its
// last run found, and "End" stops it. The card belongs to a completed answer,
// which points to it; agent-chat.js passes the saved turn's proposal only
// then. What runs comes from the chat's Watches (GET /agent/watches), never
// from the saved turn.
(function () {
  'use strict';
  const App = window.App = window.App || {};
  const MIN_TASK = 8;
  // Shortest first, as the server orders them (agent_watches.ORDER).
  const INTERVALS = ['hourly', 'every_6_hours', 'daily', 'weekly'];
  const TIMED = new Set(['daily', 'weekly']);
  const WEEKDAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];
  const DEFAULT_TIME = '08:00';
  const views = new WeakMap();
  const shown = new Set();
  // chat id -> { watches, intervals, active_count, active_limit } of its last read.
  const chats = new Map();
  const loading = new Map();
  let serial = 0;

  function line(value) {
    return typeof value === 'string' ? value.replace(/\s+/g, ' ').trim() : '';
  }

  function normalize(proposal) {
    const task = line(proposal?.task);
    if (task.length < MIN_TASK) return null;
    const interval = INTERVALS.includes(proposal.interval) ? proposal.interval : 'daily';
    const time = /^([01]\d|2[0-3]):[0-5]\d$/.test(proposal.run_time || '') ? proposal.run_time : '';
    const weekday = interval === 'weekly' && WEEKDAYS.includes(proposal.run_weekday) ? proposal.run_weekday : '';
    return { task, goal: line(proposal.goal), interval, run_time: TIMED.has(interval) ? time || DEFAULT_TIME : '', run_weekday: weekday };
  }

  function timezone() {
    try { return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'; } catch (_) { return 'UTC'; }
  }

  // "Every hour", "Every 6 hours", "Daily at 08:00", "Weekly on Monday at 09:00".
  function scheduleLabel(watch) {
    if (watch.interval === 'hourly') return App.t('Every hour');
    if (watch.interval === 'every_6_hours') return App.t('Every 6 hours');
    // A Watch set in another zone names its city (watch-fields.js timezoneCity).
    if (App.watchFields?.scheduleLabel) return App.watchFields.scheduleLabel(watch);
    return watch.run_time ? `${watch.interval} ${watch.run_time}` : watch.interval;
  }

  function when(value) {
    return value && App.format?.upcoming ? App.format.upcoming(value) : '';
  }

  function ago(value) {
    return value && App.format?.relative ? App.format.relative(value) : '';
  }

  function icon() {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('aria-hidden', 'true');
    // The eye of the Watch pill under an answer.
    for (const [tag, attrs] of [['path', { d: 'M3 12s3.5-6 9-6 9 6 9 6-3.5 6-9 6-9-6-9-6Z' }],
      ['circle', { cx: '12', cy: '12', r: '2.5' }]]) {
      const shape = document.createElementNS(svg.namespaceURI, tag);
      for (const [name, value] of Object.entries(attrs)) shape.setAttribute(name, value);
      svg.append(shape);
    }
    return svg;
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

  function load(chatId, { force = false } = {}) {
    if (!chatId || !window.auth?.currentUser) return Promise.resolve(null);
    if (!force && chats.has(chatId)) return Promise.resolve(chats.get(chatId));
    if (loading.has(chatId)) return loading.get(chatId);
    const pending = request(`/agent/watches?chat_id=${encodeURIComponent(chatId)}`)
      .then(data => { chats.set(chatId, data); shown.forEach(sync); return data; })
      .catch(() => null)
      .finally(() => loading.delete(chatId));
    loading.set(chatId, pending);
    return pending;
  }

  function scheduleControls(view) {
    const row = node('div', 'agent-watch-schedule');
    row.hidden = true;
    const interval = node('select', 'agent-watch-interval');
    interval.setAttribute('aria-label', App.t('How often'));
    const time = node('input', 'agent-watch-time');
    time.type = 'time';
    time.setAttribute('aria-label', App.t('Time'));
    interval.addEventListener('change', () => { view.choice.interval = interval.value; sync(view); });
    time.addEventListener('change', () => { if (time.value) view.choice.run_time = time.value; sync(view); });
    row.append(interval, time);
    Object.assign(view, { scheduleRow: row, intervalInput: interval, timeInput: time });
    return row;
  }

  function create(key) {
    const card = node('section', 'agent-watch-card');
    const title = node('span', 'agent-watch-title');
    const head = node('div', 'agent-watch-head');
    head.append(icon(), title);
    title.id = `agentWatchTitle${serial += 1}`;
    card.setAttribute('aria-labelledby', title.id);
    // The task, its goal and a run's finding are the model's words: the
    // line around the goal comes translated from sync() (docs/i18n.md).
    const task = node('p', 'agent-watch-question');
    task.setAttribute('data-i18n-skip', '');
    const goal = node('p', 'agent-watch-goal');
    goal.setAttribute('data-i18n-skip', '');
    const settings = node('p', 'agent-watch-settings');
    settings.setAttribute('data-i18n-skip', '');
    const status = node('p', 'agent-watch-status');
    status.setAttribute('role', 'status');
    status.setAttribute('data-i18n-skip', '');
    const view = { key, card, title, task, goal, settings, status, proposal: null, choice: null,
      chatId: '', turnId: '', busy: false, message: '', changing: false };
    // The one primary button of every watch surface (Apple-Audit J18).
    view.start = button('wd-button is-primary agent-watch-start', 'Start Watch', () => start(view));
    view.change = button('text-link agent-watch-link', 'Change', () => { view.changing = !view.changing; sync(view); });
    view.end = button('text-link agent-watch-link agent-watch-end', 'End Watch', () => end(view));
    const actions = node('div', 'agent-watch-actions');
    actions.append(view.start, view.change, view.end);
    card.append(head, task, goal, settings, scheduleControls(view), status, actions);
    return view;
  }

  // Below the answer and its review, after a memory note when one is there.
  function place(body, card) {
    const review = body._agentReview?.parentNode && body._agentReview.parentNode === body.parentNode ? body._agentReview : null;
    let anchor = review || body;
    while (anchor.nextElementSibling && anchor.nextElementSibling !== card
        && anchor.nextElementSibling.classList.contains('agent-memory-note')) anchor = anchor.nextElementSibling;
    if (anchor.nextElementSibling !== card) anchor.after(card);
  }

  function fillIntervals(view, allowed) {
    const select = view.intervalInput;
    const wanted = allowed.join(',');
    if (select.dataset.options !== wanted) {
      select.replaceChildren(...allowed.map(value => {
        const option = node('option', '', scheduleLabel({ interval: value, run_time: '' }));
        option.value = value;
        return option;
      }));
      select.dataset.options = wanted;
    }
    select.value = view.choice.interval;
  }

  function lastRunLine(watch) {
    const last = watch.last_run;
    if (!last?.at) return '';
    const at = ago(last.at);
    if (['finding', 'needs_you', 'done'].includes(last.outcome) && last.summary) {
      return App.t('Last run {when}: {summary}', { when: at, summary: last.summary });
    }
    if (last.outcome === 'quiet') return App.t('Last run {when}: nothing new.', { when: at });
    return App.t('Last run {when} did not finish.', { when: at });
  }

  function sync(view) {
    const { proposal } = view;
    const data = chats.get(view.chatId) || null;
    const watches = Array.isArray(data?.watches) ? data.watches : [];
    const own = watches.find(watch => watch.turn_id === view.turnId)
      || watches.find(watch => watch.task === proposal.task && watch.chat_id === view.chatId) || null;
    const other = !own && watches.find(watch => watch.status === 'active') || null;
    const allowed = Array.isArray(data?.intervals) && data.intervals.length ? data.intervals.filter(value => INTERVALS.includes(value)) : INTERVALS;
    if (!allowed.includes(view.choice.interval)) view.choice.interval = allowed.includes(proposal.interval) ? proposal.interval : allowed[0];
    if (TIMED.has(view.choice.interval) && !view.choice.run_time) view.choice.run_time = DEFAULT_TIME;
    const full = !own && !other && Boolean(data) && data.active_count >= data.active_limit;
    const state = own ? (own.status === 'active' ? 'watching' : 'ended') : other ? 'taken' : full ? 'full' : 'proposal';
    view.card.dataset.state = state;
    view.title.textContent = state === 'watching' ? App.t('Watch running') : state === 'ended'
      ? App.t(own.ended === 'goal' ? 'Watch reached its goal' : 'Watch ended') : App.t('Watch');
    const shownWatch = own || { ...proposal, ...view.choice, timezone: timezone() };
    view.task.textContent = shownWatch.task || proposal.task;
    const goal = line(shownWatch.goal);
    view.goal.textContent = goal ? App.t('Done when: {goal}', { goal }) : App.t('Runs until you end it');
    const schedule = scheduleLabel(shownWatch);
    view.settings.textContent = state === 'watching' && own.next_run_at
      ? App.t('{schedule} · next run {when}', { schedule, when: when(own.next_run_at) }) : schedule;
    view.settings.hidden = state === 'ended';
    view.status.textContent = state === 'proposal' ? view.message
      : state === 'watching' || state === 'ended' ? lastRunLine(own) || view.message
        : state === 'taken' ? App.t('This chat already has a Watch. End it first to start this one.')
          : App.t('All your Watches are in use. End one in its chat first.');
    view.status.hidden = !view.status.textContent;
    const offer = state === 'proposal' || state === 'full' || state === 'taken';
    view.start.hidden = !offer;
    view.start.disabled = view.busy || state !== 'proposal';
    view.start.textContent = App.t(view.busy && offer ? 'Starting…' : 'Start Watch');
    view.change.hidden = !offer;
    view.change.disabled = view.busy;
    view.change.setAttribute('aria-expanded', String(view.changing && offer));
    view.end.hidden = state !== 'watching';
    view.end.disabled = view.busy;
    view.scheduleRow.hidden = !(view.changing && offer);
    if (!view.scheduleRow.hidden) {
      fillIntervals(view, allowed);
      view.timeInput.hidden = !TIMED.has(view.choice.interval);
      view.timeInput.value = view.choice.run_time || DEFAULT_TIME;
    }
  }

  async function start(view) {
    if (view.busy || !view.chatId || !view.turnId) return;
    const timed = TIMED.has(view.choice.interval);
    const payload = { chat_id: view.chatId, turn_id: view.turnId, interval: view.choice.interval,
      run_time: timed ? view.choice.run_time || DEFAULT_TIME : '',
      run_weekday: view.choice.interval === 'weekly' ? view.proposal.run_weekday : '', timezone: timezone() };
    view.busy = true;
    view.message = '';
    sync(view);
    try {
      const data = await request('/agent/watches', { method: 'POST', body: JSON.stringify(payload) });
      const current = chats.get(view.chatId) || { watches: [], intervals: INTERVALS, active_count: 0, active_limit: 1 };
      chats.set(view.chatId, { ...current, watches: [data.watch, ...current.watches],
        active_count: current.active_count + 1 });
      view.changing = false;
      App.trackAppEvent?.('app_watch_created', { interval: data.watch.interval, source: 'agent',
        has_goal: Boolean(data.watch.goal), goal_source: data.watch.goal ? 'suggested' : 'none' });
    } catch (error) {
      view.message = App.t('Watch not started. {reason}', { reason: App.userError(error, { fallback: 'Try again.' }) });
    } finally {
      view.busy = false;
      // From then on the chat's Watches decide (another tab, a run that ended it).
      load(view.chatId, { force: true }).then(() => sync(view));
      sync(view);
    }
  }

  async function end(view) {
    const own = (chats.get(view.chatId)?.watches || []).find(watch => watch.turn_id === view.turnId && watch.status === 'active');
    if (view.busy || !own) return;
    view.busy = true;
    sync(view);
    try {
      await request(`/agent/watches/${encodeURIComponent(own.id)}/stop`, { method: 'POST' });
    } catch (error) {
      view.message = App.userError(error, { fallback: 'Try again.' });
    } finally {
      view.busy = false;
      await load(view.chatId, { force: true });
      sync(view);
    }
  }

  function render(body, { key = '', proposal = null, chatId = '', turnId = '' } = {}) {
    if (!body) return;
    let view = views.get(body);
    const value = normalize(proposal);
    if (view && (!value || view.key !== key)) {
      view.card.remove();
      shown.delete(view);
      views.delete(body);
      view = null;
    }
    if (!value) return;
    if (!view) {
      view = create(key);
      views.set(body, view);
      shown.add(view);
      view.choice = { interval: value.interval, run_time: value.run_time };
    }
    view.proposal = value;
    view.chatId = String(chatId || '');
    view.turnId = String(turnId || '');
    place(body, view.card);
    sync(view);
    load(view.chatId).then(() => { if (shown.has(view)) sync(view); });
  }

  App.agentWatch = { render, load };
})();
