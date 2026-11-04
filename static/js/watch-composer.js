// The one field that starts a Watch (since 2026-11-04, the Watches redesign):
// a Watch is a sentence. The user writes what the Agent should keep an eye
// on; two chips under it say how often (a popover with the account's
// intervals, the weekday and the time) and, if they want, when it is done
// (a token they type into). A line under the field says what happens next,
// Return starts it (POST /agent/watches). The Watches page holds one
// (watch-dashboard.js: large on its empty page, a slim field above the
// list that opens as it is focused), the sheet of the Watch pill under an
// answer another (watch-sheet.js, in that chat). The schedule picker is
// also the detail panel's (watch-dashboard.js, "How often").
//
//   const composer = App.watchComposer.create({ mode: 'hero'|'inline'|'sheet',
//     chatId, task, source, onStarted, onSettle });
//   composer.element, .focus(), .setTask(text, { interval }), .setOptions({
//     intervals, limitReached }), .setMode(mode), .reset(), .isEmpty()
//   App.watchComposer.schedulePicker({ schedule, allowed, onChange })
//     -> { element, value() }
//   App.watchComposer.weekdayToday()
(function () {
  'use strict';
  const App = window.App = window.App || {};
  // Shortest first, as the server orders them (agent_watches.ORDER).
  const ORDER = ['hourly', 'every_6_hours', 'daily', 'weekly'];
  const TIMED = new Set(['daily', 'weekly']);
  const WEEKDAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];
  const DEFAULT_TIME = '08:00';
  const TASK_MIN = 8;
  const TASK_MAX = 500;
  const GOAL_MAX = 200;
  // The segment's word for each interval (one "watch schedule" context:
  // German "Täglich", not the preset's "Alltag").
  const SEGMENTS = { hourly: 'Hourly', every_6_hours: '6 hours', daily: 'Daily', weekly: 'Weekly' };
  const ICONS = {
    clock: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/></svg>',
    flag: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5.5 20.5V4"/><path d="M5.5 4.5h11l-2.2 4 2.2 4h-11"/></svg>',
    send: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 19V5"/><path d="m6 11 6-6 6 6"/></svg>',
    plus: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg>',
    lock: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="11" width="14" height="9.5" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg>',
    clear: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 7l10 10M17 7 7 17"/></svg>',
  };
  let serial = 0;

  function node(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }

  function icon(name, className = 'wc-icon') {
    const span = node('span', className);
    span.setAttribute('aria-hidden', 'true');
    span.innerHTML = ICONS[name];
    return span;
  }

  function line(value) {
    return String(value || '').replace(/\s+/g, ' ').trim();
  }

  function timezone() {
    try { return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'; } catch (_) { return 'UTC'; }
  }

  function weekdayToday(now = new Date()) {
    return WEEKDAYS[(now.getDay() + 6) % 7];
  }

  // Monday 2026-11-02 + index: the weekday's name in the reader's language.
  function weekdayName(index, style) {
    return App.format?.weekday ? App.format.weekday(new Date(2026, 10, 2 + index), { style }) : WEEKDAYS[index];
  }

  function normalizeSchedule(value = {}) {
    const interval = ORDER.includes(value.interval) ? value.interval : 'daily';
    const time = /^([01]\d|2[0-3]):[0-5]\d$/.test(value.run_time || '') ? value.run_time : DEFAULT_TIME;
    const weekday = WEEKDAYS.includes(value.run_weekday) ? value.run_weekday : weekdayToday();
    return { interval, run_time: TIMED.has(interval) ? time : '', run_weekday: interval === 'weekly' ? weekday : '',
      time, weekday };
  }

  // The schedule as the app writes it everywhere (watch-fields.js).
  function scheduleText(schedule) {
    if (schedule.interval === 'hourly') return App.t('Every hour');
    if (schedule.interval === 'every_6_hours') return App.t('Every 6 hours');
    return App.watchFields?.scheduleLabel ? App.watchFields.scheduleLabel(schedule) : schedule.interval;
  }

  // What the intervals the plan leaves out need.
  function lockedNote(allowed) {
    const locked = ORDER.filter(value => !allowed.includes(value));
    if (locked.includes('every_6_hours')) return App.t('Shorter intervals come with Plus and Pro.');
    if (locked.includes('hourly')) return App.t('Every hour comes with Pro.');
    return '';
  }

  // --- how often: the segments, the weekday, the time --------------------------

  function schedulePicker({ schedule = {}, allowed = ['daily', 'weekly'], onChange = () => {} } = {}) {
    const id = 'wcPick' + (++serial);
    const state = normalizeSchedule(schedule);
    let permitted = allowed.length ? allowed : ['daily', 'weekly'];
    const root = node('div', 'wc-picker');
    const caption = node('div', 'wc-picker-caption', 'How often');
    caption.id = id + '-caption';
    const segments = node('div', 'wc-segments');
    segments.setAttribute('role', 'radiogroup');
    segments.setAttribute('aria-labelledby', caption.id);
    const days = node('div', 'wc-days');
    days.setAttribute('role', 'radiogroup');
    days.setAttribute('aria-label', App.t('Day'));
    const timeRow = node('div', 'wc-time-row');
    const timeLabel = node('label', 'wc-time-label', 'At');
    // The app's 24-hour clock everywhere (app-text.js time), never the
    // browser's "08:00 AM": a list every half hour, the Watch's own time in it.
    const time = node('select', 'wc-time');
    time.id = id + '-time';
    time.setAttribute('data-i18n-skip', '');
    timeLabel.htmlFor = time.id;
    timeRow.append(timeLabel, time);
    const note = node('div', 'wc-picker-note');

    const segmentButtons = ORDER.map(value => {
      const button = node('button', 'wc-segment');
      button.type = 'button';
      button.dataset.interval = value;
      button.setAttribute('role', 'radio');
      button.append(node('span', 'wc-segment-label', App.t(SEGMENTS[value], null, 'watch schedule')));
      button.addEventListener('click', () => {
        if (button.getAttribute('aria-disabled') === 'true') return;
        state.interval = value;
        sync(true);
      });
      return button;
    });
    segments.append(...segmentButtons);
    const dayButtons = WEEKDAYS.map((value, index) => {
      const button = node('button', 'wc-day', weekdayName(index, 'narrow'));
      button.type = 'button';
      button.dataset.weekday = value;
      button.setAttribute('role', 'radio');
      button.setAttribute('aria-label', weekdayName(index, 'long'));
      button.setAttribute('data-i18n-skip', '');
      button.addEventListener('click', () => {
        state.weekday = value;
        sync(true);
      });
      return button;
    });
    days.append(...dayButtons);
    function fillTimes() {
      const times = [];
      for (let minutes = 0; minutes < 24 * 60; minutes += 30) {
        times.push(String(Math.floor(minutes / 60)).padStart(2, '0') + ':' + String(minutes % 60).padStart(2, '0'));
      }
      if (!times.includes(state.time)) times.push(state.time);
      times.sort();
      if (time.options.length === times.length && [...time.options].every((option, index) => option.value === times[index])) return;
      time.replaceChildren(...times.map(value => {
        const option = node('option', '', value);
        option.value = value;
        return option;
      }));
    }
    time.addEventListener('change', () => {
      if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(time.value)) return;
      state.time = time.value;
      sync(true);
    });
    // Arrows move within a group of radios, as in every radio group.
    const arrows = (buttons) => event => {
      if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) return;
      const usable = buttons.filter(button => button.getAttribute('aria-disabled') !== 'true');
      const index = usable.indexOf(document.activeElement);
      if (index < 0) return;
      event.preventDefault();
      const step = ['ArrowLeft', 'ArrowUp'].includes(event.key) ? -1 : 1;
      const next = usable[(index + step + usable.length) % usable.length];
      next.focus();
      next.click();
    };
    segments.addEventListener('keydown', arrows(segmentButtons));
    days.addEventListener('keydown', arrows(dayButtons));
    root.append(caption, segments, days, timeRow, note);

    function value() {
      return normalizeSchedule({ interval: state.interval, run_time: state.time, run_weekday: state.weekday });
    }

    function sync(changed) {
      if (!permitted.includes(state.interval)) state.interval = permitted.includes('daily') ? 'daily' : permitted[0];
      segmentButtons.forEach(button => {
        const on = button.dataset.interval === state.interval;
        const locked = !permitted.includes(button.dataset.interval);
        button.setAttribute('aria-checked', String(on));
        button.tabIndex = on ? 0 : -1;
        button.classList.toggle('is-locked', locked);
        if (locked) {
          button.setAttribute('aria-disabled', 'true');
          if (!button.querySelector('.wc-lock')) button.prepend(icon('lock', 'wc-lock'));
        } else {
          button.removeAttribute('aria-disabled');
          button.querySelector('.wc-lock')?.remove();
        }
      });
      dayButtons.forEach(button => {
        const on = button.dataset.weekday === state.weekday;
        button.setAttribute('aria-checked', String(on));
        button.tabIndex = on ? 0 : -1;
      });
      days.hidden = state.interval !== 'weekly';
      timeRow.hidden = !TIMED.has(state.interval);
      fillTimes();
      if (time.value !== state.time) time.value = state.time;
      note.textContent = lockedNote(permitted);
      note.hidden = !note.textContent;
      if (changed) onChange(value());
    }

    sync(false);
    return {
      element: root,
      value,
      setAllowed(next) {
        permitted = next?.length ? next : permitted;
        sync(false);
      },
      set(next) {
        Object.assign(state, normalizeSchedule(next));
        sync(false);
      },
      focus() {
        (segmentButtons.find(button => button.getAttribute('aria-checked') === 'true') || segmentButtons[0]).focus();
      },
    };
  }

  // --- the field ----------------------------------------------------------------

  async function request(path, options = {}) {
    if (App.watchUi?.api) return App.watchUi.api(options.method || 'GET', path, options.body);
    const user = window.auth?.currentUser;
    if (!user) throw new Error('Log in first.');
    const token = await user.getIdToken();
    const response = await fetch(path, { method: options.method || 'GET', headers: { Authorization: `Bearer ${token}`,
      ...(options.body ? { 'Content-Type': 'application/json' } : {}) },
    ...(options.body ? { body: JSON.stringify(options.body) } : {}) });
    const data = await App.readJson(response).catch(() => ({}));
    if (!response.ok) throw App.httpError(response, data);
    return data;
  }

  function create(config = {}) {
    const id = 'wc' + (++serial);
    const options = { mode: 'inline', chatId: '', source: '', onStarted: null, onSettle: null, ...config };
    const state = { schedule: normalizeSchedule(config.schedule), goal: '', editingGoal: false, busy: false,
      intervals: null, limitReached: false, loaded: false, popover: false, errorKind: '' };

    const form = node('form', 'wc');
    form.noValidate = true;
    form.setAttribute('aria-label', App.t('New Watch'));
    const label = node('label', 'visually-hidden', 'What should the Agent keep an eye on?');
    label.htmlFor = id + '-task';
    const lead = icon('plus', 'wc-lead');
    const task = node('textarea', 'wc-task');
    task.id = id + '-task';
    task.rows = 1;
    task.maxLength = TASK_MAX;
    task.setAttribute('data-i18n-skip', '');
    task.setAttribute('autocomplete', 'off');
    task.setAttribute('enterkeyhint', 'go');
    // The placeholder is ours (translated); what is typed stays as written.
    task.placeholder = App.t('Tell me when registration for IRONMAN Hamburg 2027 opens');
    const field = node('div', 'wc-field');
    field.append(lead, label, task);

    const bar = node('div', 'wc-bar');
    const chips = node('div', 'wc-chips');
    const when = node('button', 'wc-chip wc-when');
    when.type = 'button';
    when.setAttribute('aria-haspopup', 'dialog');
    when.setAttribute('aria-expanded', 'false');
    const whenText = node('span', 'wc-chip-text');
    when.append(icon('clock'), whenText);
    // Done when: a quiet chip, a token to type into, then the goal with its cross.
    const goalAdd = node('button', 'wc-chip is-quiet wc-goal-add');
    goalAdd.type = 'button';
    goalAdd.append(icon('flag'), node('span', 'wc-chip-text', 'Done when'));
    const goalChip = node('span', 'wc-chip wc-goal');
    goalChip.hidden = true;
    const goalLabel = node('label', 'wc-goal-label', 'Done when');
    const goal = node('input', 'wc-goal-input');
    goal.type = 'text';
    goal.id = id + '-goal';
    goal.maxLength = GOAL_MAX;
    goal.setAttribute('data-i18n-skip', '');
    goal.setAttribute('autocomplete', 'off');
    goal.placeholder = App.t('registration is open');
    goalLabel.htmlFor = goal.id;
    const goalClear = node('button', 'wc-goal-clear');
    goalClear.type = 'button';
    goalClear.setAttribute('aria-label', App.t('Remove goal'));
    goalClear.innerHTML = ICONS.clear;
    goalChip.append(icon('flag'), goalLabel, goal, goalClear);
    chips.append(when, goalAdd, goalChip);
    const hint = node('span', 'wc-hint', 'Return to start');
    hint.setAttribute('aria-hidden', 'true');
    const send = node('button', 'wc-send');
    send.type = 'submit';
    send.setAttribute('aria-label', App.t('Start Watch'));
    send.innerHTML = ICONS.send;
    bar.append(chips, hint, send);

    const preview = node('p', 'wc-preview');
    preview.id = id + '-preview';
    task.setAttribute('aria-describedby', preview.id);
    const error = node('p', 'wc-error');
    error.setAttribute('role', 'alert');
    error.hidden = true;

    const popover = node('div', 'wc-popover');
    popover.setAttribute('role', 'dialog');
    popover.setAttribute('aria-label', App.t('How often'));
    popover.hidden = true;
    const picker = schedulePicker({ schedule: state.schedule, allowed: ['daily', 'weekly'], onChange(next) {
      state.schedule = next;
      sync();
    } });
    popover.append(picker.element);
    const box = node('div', 'wc-box');
    box.append(field, bar);
    // The popover right after the field: in a sheet it opens in place there.
    form.append(box, popover, preview, error);

    // --- size and state ---------------------------------------------------

    function grow() {
      task.style.height = 'auto';
      const max = options.mode === 'inline' ? 168 : 200;
      task.style.height = Math.min(task.scrollHeight, max) + 'px';
      task.style.overflowY = task.scrollHeight > max ? 'auto' : 'hidden';
    }

    function goalSize() {
      goal.size = Math.max(4, Math.min(42, (goal.value || goal.placeholder).length + 1));
    }

    function isEmpty() {
      return !line(task.value) && !line(goal.value);
    }

    function collapsed() {
      return options.mode === 'inline' && isEmpty() && !form.contains(document.activeElement) && !state.popover
        && !state.busy && error.hidden;
    }

    function previewText() {
      const first = options.chatId ? App.t('It looks again in this chat on this schedule.')
        : App.t('Its first look starts right away, in a chat of its own.');
      const end = line(goal.value) ? App.t('It ends by itself once its goal is reached.') : App.t('It runs until you end it.');
      return first + ' ' + end;
    }

    function sync() {
      whenText.textContent = scheduleText(state.schedule);
      whenText.setAttribute('data-i18n-skip', '');
      const showGoal = state.editingGoal || Boolean(line(goal.value));
      goalAdd.hidden = showGoal;
      goalChip.hidden = !showGoal;
      goalSize();
      preview.textContent = previewText();
      preview.setAttribute('data-i18n-skip', '');
      const ready = line(task.value).length > 0 && !state.busy;
      send.disabled = !ready;
      form.classList.toggle('is-busy', state.busy);
      form.classList.toggle('is-ready', ready);
      task.readOnly = state.busy;
      goal.readOnly = state.busy;
      [when, goalAdd, goalClear].forEach(button => { button.disabled = state.busy; });
      form.classList.toggle('is-collapsed', collapsed());
    }

    function setMode(mode) {
      options.mode = mode;
      form.classList.remove('is-hero', 'is-inline', 'is-sheet');
      form.classList.add('is-' + mode);
      task.rows = mode === 'inline' ? 1 : 2;
      task.placeholder = mode === 'inline' ? App.t('Keep an eye on something…')
        : App.t('Tell me when registration for IRONMAN Hamburg 2027 opens');
      sync();
      grow();
    }

    // `kind` 'limit': the refusal of a full plan, which goes by itself once
    // a slot is free again (never told apart by its words).
    function showError(message, kind = '') {
      error.textContent = message;
      error.hidden = !message;
      state.errorKind = message ? kind : '';
      sync();
    }

    function showLimit() {
      showError(App.t('All your Watches are in use. End one first.'), 'limit');
    }

    // --- the account's intervals ------------------------------------------

    function setOptions({ intervals, limitReached } = {}) {
      if (Array.isArray(intervals)) {
        state.intervals = intervals.filter(value => ORDER.includes(value));
        state.loaded = true;
        picker.setAllowed(state.intervals);
        state.schedule = picker.value();
      }
      if (typeof limitReached === 'boolean') state.limitReached = limitReached;
      // A Watch ended meanwhile: "All your Watches are in use" no longer holds
      // (review 2026-11-04), and the slim field may close again.
      if (!state.limitReached && state.errorKind === 'limit') showError('');
      else sync();
    }

    let loading = null;
    function loadOptions() {
      if (state.loaded || loading || !window.auth?.currentUser) return loading;
      const path = '/agent/watches' + (options.chatId ? `?chat_id=${encodeURIComponent(options.chatId)}` : '');
      loading = request(path).then(data => {
        setOptions({ intervals: Array.isArray(data.intervals) ? data.intervals : [],
          limitReached: Number(data.active_count) >= Number(data.active_limit) });
        if (state.limitReached && form.contains(document.activeElement)) showLimit();
      }).catch(() => {}).finally(() => { loading = null; });
      return loading;
    }

    // --- how often --------------------------------------------------------

    function closePopover({ focus = false } = {}) {
      if (!state.popover) return;
      state.popover = false;
      popover.hidden = true;
      when.setAttribute('aria-expanded', 'false');
      App.popover?.closed?.(popover);
      document.removeEventListener('pointerdown', outside, true);
      if (focus) when.focus({ preventScroll: true });
      sync();
    }

    function outside(event) {
      if (!popover.contains(event.target) && !when.contains(event.target)) closePopover();
    }

    function openPopover() {
      if (state.busy) return;
      loadOptions();
      App.popover?.opened?.(popover, { trigger: when });
      state.popover = true;
      popover.hidden = false;
      // Under the chip, inside the field's edge.
      const formBox = form.getBoundingClientRect();
      const chipBox = when.getBoundingClientRect();
      popover.style.left = Math.max(0, chipBox.left - formBox.left - 4) + 'px';
      popover.style.top = (chipBox.bottom - formBox.top + 8) + 'px';
      when.setAttribute('aria-expanded', 'true');
      document.addEventListener('pointerdown', outside, true);
      picker.focus();
      sync();
    }

    App.popover?.register?.(popover, { close: () => closePopover() });
    // Tab out of it (or of its chip) and it closes, as a menu does.
    const leave = () => setTimeout(() => {
      const active = document.activeElement;
      if (state.popover && !popover.contains(active) && active !== when) closePopover();
    }, 0);
    popover.addEventListener('focusout', leave);
    when.addEventListener('focusout', leave);
    when.addEventListener('click', () => (state.popover ? closePopover({ focus: true }) : openPopover()));
    popover.addEventListener('keydown', event => {
      if (event.key === 'Escape') {
        event.preventDefault();
        event.stopPropagation();
        closePopover({ focus: true });
      }
      if (event.key === 'Enter' && event.target.matches('select')) {
        event.preventDefault();
        closePopover({ focus: true });
      }
    });

    // --- done when --------------------------------------------------------

    goalAdd.addEventListener('click', () => {
      state.editingGoal = true;
      sync();
      goal.focus();
    });
    goal.addEventListener('input', () => { sync(); });
    goal.addEventListener('blur', () => {
      if (!line(goal.value)) {
        state.editingGoal = false;
        goal.value = '';
      }
      sync();
    });
    goal.addEventListener('keydown', event => {
      if (event.key === 'Escape' && !line(goal.value)) {
        event.preventDefault();
        event.stopPropagation();
        state.editingGoal = false;
        sync();
        goalAdd.focus();
      }
    });
    goalClear.addEventListener('click', () => {
      goal.value = '';
      state.editingGoal = false;
      sync();
      goalAdd.focus();
    });

    // --- typing and starting ----------------------------------------------

    task.addEventListener('input', () => {
      if (!error.hidden && line(task.value).length >= TASK_MIN) showError('');
      grow();
      sync();
    });
    task.addEventListener('keydown', event => {
      if (event.key === 'Enter' && !event.shiftKey && !event.isComposing && event.keyCode !== 229) {
        event.preventDefault();
        submit();
      }
      if (event.key === 'Escape' && options.mode === 'inline' && isEmpty()) {
        task.blur();
      }
    });
    form.addEventListener('focusin', () => {
      loadOptions();
      sync();
      if (state.limitReached) showLimit();
    });
    form.addEventListener('focusout', () => {
      // After the focus has moved: still inside (a chip, the popover) keeps it open.
      setTimeout(() => {
        if (!form.contains(document.activeElement) && !state.popover) {
          if (state.errorKind === 'limit' && isEmpty()) showError('');
          sync();
          options.onSettle?.();
        }
      }, 0);
    });
    form.addEventListener('pointerdown', event => {
      // A click anywhere on the slim field goes into it.
      if (form.classList.contains('is-collapsed') && !event.target.closest('button, input, textarea')) {
        event.preventDefault();
        task.focus();
      }
    });
    form.addEventListener('submit', event => {
      event.preventDefault();
      submit();
    });

    async function submit() {
      if (state.busy) return;
      const text = line(task.value);
      if (text.length < TASK_MIN) {
        showError(App.t('Say in a sentence what the Agent should do.'));
        task.focus();
        return;
      }
      if (!window.auth?.currentUser) {
        App.watchUi?.requireAccount?.({ question: text }, send);
        return;
      }
      closePopover();
      const schedule = state.schedule;
      const payload = { task: text, goal: line(goal.value), interval: schedule.interval,
        run_time: schedule.run_time, run_weekday: schedule.run_weekday, timezone: timezone(),
        ...(options.chatId ? { chat_id: options.chatId } : {}) };
      state.busy = true;
      showError('');
      try {
        const data = await request('/agent/watches', { method: 'POST', body: payload });
        App.trackAppEvent?.('app_watch_created', { interval: data.watch.interval, source: options.source || 'composer',
          has_goal: Boolean(data.watch.goal), goal_source: data.watch.goal ? 'own' : 'none' });
        state.busy = false;
        reset();
        App.toast?.({ message: options.chatId ? App.t('Watch started. It runs in this chat.')
          : App.t('Watch started. Its first look is under way.') });
        window.dispatchEvent(new CustomEvent('consensio:agent-watches-changed', { detail: { watch: data.watch } }));
        options.onStarted?.(data.watch);
      } catch (failure) {
        state.busy = false;
        showError(App.userError ? App.userError(failure, { fallback: 'Try again.' }) : App.t('Try again.'));
        task.focus({ preventScroll: true });
      }
    }

    function setTask(text, { interval } = {}) {
      task.value = String(text || '').replace(/\s+/g, ' ').trimStart().slice(0, TASK_MAX);
      if (interval && ORDER.includes(interval)) {
        picker.set({ ...state.schedule, interval });
        state.schedule = picker.value();
      }
      showError('');
      grow();
      sync();
    }

    function focus({ end = true } = {}) {
      task.focus({ preventScroll: options.mode !== 'inline' });
      if (end) task.setSelectionRange(task.value.length, task.value.length);
      sync();
    }

    // `reload`: the account's intervals and slots are read again at the next
    // focus (a sheet opened again, a Watch started or ended in between);
    // until then no full plan is assumed, so the old answer cannot refuse
    // before the new one is there (review 2026-11-04).
    function reset({ reload = true } = {}) {
      closePopover();
      if (reload) {
        state.loaded = false;
        state.limitReached = false;
      }
      task.value = '';
      goal.value = '';
      state.editingGoal = false;
      error.hidden = true;
      state.errorKind = '';
      grow();
      sync();
    }

    setMode(options.mode);
    if (config.task) setTask(config.task);
    return {
      element: form,
      focus,
      setTask,
      setOptions,
      setMode,
      reset,
      isEmpty,
      isBusy: () => state.busy,
      refresh: sync,
      load: loadOptions,
      destroy() {
        closePopover();
        App.popover?.unregister?.(popover);
        form.remove();
      },
      task: () => line(task.value),
    };
  }

  App.watchComposer = { create, schedulePicker, scheduleText, weekdayToday, normalizeSchedule, ORDER, TIMED };
})();
