// The settings change the Agent prepared (agent_settings.py) as a card under
// the answer. The Agent only proposes: the card shows each change as
// "now -> new" and applies it with one click through App.userSettings, the
// way the Settings dialog does, so the account saves it (PATCH
// /api/my/settings) and the owner modules show it at once (source "agent").
// "Now" is read from this page when the card renders, never from the
// proposal: a change made in another tab or in Settings is what it compares
// with. Only the settings below can be applied, whatever a proposal holds.
// agent-chat.js passes the saved turn's proposal only for a completed answer.
(function () {
  'use strict';
  const App = window.App = window.App || {};
  const views = new WeakMap();
  // Answers (chat:turn) whose card was applied in this page: it says so.
  const applied = new Set();
  // Answers whose card was applied or dismissed, also on earlier visits: the
  // card does not come back when the chat is opened again. A per-viewer
  // convenience in localStorage, bounded; a blocked storage keeps it for
  // this page only.
  const CLOSED_KEY = 'consensio.agentSettingsCards.v1';
  const CLOSED_MAX = 100;
  let serial = 0;

  function closedKeys() {
    try {
      const value = JSON.parse(window.localStorage.getItem(CLOSED_KEY) || '[]');
      return Array.isArray(value) ? value.filter(item => typeof item === 'string') : [];
    } catch (_) { return []; }
  }
  const closed = new Set(closedKeys());

  function close(key) {
    closed.add(key);
    try {
      const keys = [...closedKeys().filter(item => item !== key), key].slice(-CLOSED_MAX);
      window.localStorage.setItem(CLOSED_KEY, JSON.stringify(keys));
    } catch (_) { /* storage blocked: this page remembers it */ }
  }

  // The Settings dialog's and the picker's words (templates/index.html,
  // agent-chat.js effortCopy; agent_settings.py names the same).
  const EFFORTS = { default: 'Auto', none: 'Off', minimal: 'Minimal', low: 'Low', medium: 'Medium',
    high: 'High', xhigh: 'Extra high', max: 'Max' };
  const PREFERENCES = {
    depth: ['Answer depth', { auto: 'Automatic', quick: 'Always brief', full: 'Always thorough' }],
    quorum: ['Answer start', { all: 'After every model', balanced: 'Every model on thorough questions', fast: 'As soon as half answered' }],
    autonomy: ['Agent freedom', { guided: 'Guided', free: 'Free' }],
    judges: ['Answer check', { on: 'On', off: 'Off' }],
  };
  const SETTINGS = {
    consensus_preset: ['Comparison models', { fast: 'Daily', balanced: 'Open Models', thorough: 'High Quality', custom: 'Custom' },
      () => App.activeConsensusPresetId?.() || App.userSettings.get('consensus_preset')],
    consensus_highlights: ['Answer highlights', { all: 'All checks', contradictions: 'Contradictions only',
      concerns: 'Disagreements & issues', critical: 'Critical contradictions', none: 'No highlights' },
    () => App.userSettings.get('consensus_highlights') || 'concerns'],
    claim_counts: ['Inline claim counts', { true: 'On', false: 'Off' }, () => App.userSettings.get('claim_counts') === true],
    agreement_display: ['Agreement score', { full: 'Score and summary', summary: 'Summary only', off: 'Hidden' },
      () => App.userSettings.get('agreement_display') || 'full'],
  };
  const NAMES = ['agent_model', 'agent_preferences', ...Object.keys(SETTINGS)];

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

  function plain(value) {
    return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
  }

  // The known settings of a proposal, each in a form the account accepts.
  function normalize(proposal) {
    const settings = plain(proposal?.settings) ? proposal.settings : {};
    const value = {};
    for (const name of NAMES) {
      if (!Object.prototype.hasOwnProperty.call(settings, name)) continue;
      if (App.userSettings?.accepts?.(name, settings[name]) && settings[name] !== null) value[name] = settings[name];
    }
    if (!Object.keys(value).length) return null;
    const notes = plain(proposal.notes) ? proposal.notes : {};
    return { settings: value, note: typeof notes.agent_model === 'string' ? notes.agent_model.trim() : '' };
  }

  function modelLabel(id) {
    return App.agentChat?.modelLabel?.(id) || id;
  }

  // What each change replaces on this page now; equal ones drop out.
  function rows(proposal) {
    const result = [];
    const add = (label, from, to) => { if (from !== to) result.push({ label, from, to }); };
    for (const [name, value] of Object.entries(proposal.settings)) {
      if (name === 'agent_model') {
        // This chat's next message first; when it already runs the change,
        // what new chats start with (the account's pick).
        const now = App.agentChat?.pick?.() || {};
        const account = App.userSettings.get('agent_model') || {};
        const effort = value.reasoning_effort || 'default';
        const chatDiffers = now.model_id !== value.model_id || (now.reasoning_effort || 'default') !== effort;
        if (chatDiffers || !account.model_id || account.model_id === value.model_id) {
          add('Chat model', modelLabel(now.model_id), modelLabel(value.model_id));
          add('Reasoning', EFFORTS[now.reasoning_effort || 'default'], EFFORTS[effort]);
        } else {
          add('Chat model in new chats', modelLabel(account.model_id), modelLabel(value.model_id));
        }
      } else if (name === 'agent_preferences') {
        const now = App.agentPreferences?.get?.() || {};
        for (const [field, [label, labels]] of Object.entries(PREFERENCES)) {
          if (value[field] !== undefined) add(label, labels[now[field]], labels[value[field]]);
        }
      } else {
        const [label, labels, current] = SETTINGS[name];
        add(label, labels[String(current())] || 'Default', labels[String(value)]);
      }
    }
    return result;
  }

  function create(key) {
    const card = node('section', 'agent-settings-card');
    const title = node('p', 'agent-settings-title', 'Change settings');
    title.id = `agentSettingsTitle${serial += 1}`;
    card.setAttribute('aria-labelledby', title.id);
    const list = node('dl', 'agent-settings-list');
    const note = node('p', 'agent-settings-note');
    const status = node('p', 'agent-settings-status');
    status.setAttribute('role', 'status');
    const view = { key, card, title, list, note, status, proposal: null, message: '' };
    view.apply = button('btn agent-settings-apply', 'Apply', () => apply(view));
    view.dismiss = button('agent-settings-link', 'Dismiss', () => dismiss(view));
    const actions = node('div', 'agent-settings-actions');
    actions.append(view.apply, view.dismiss);
    card.append(title, list, note, status, actions);
    return view;
  }

  // Below the answer and its review, after memory notes and a Watch card.
  function place(body, card) {
    const review = body._agentReview?.parentNode && body._agentReview.parentNode === body.parentNode ? body._agentReview : null;
    let anchor = review || body;
    while (anchor.nextElementSibling && anchor.nextElementSibling !== card
        && anchor.nextElementSibling.matches('.agent-memory-note, .agent-watch-card')) anchor = anchor.nextElementSibling;
    if (anchor.nextElementSibling !== card) anchor.after(card);
  }

  function sync(view) {
    const changes = rows(view.proposal);
    const done = applied.has(view.key) || !changes.length;
    view.card.dataset.state = done ? 'applied' : 'proposal';
    view.title.textContent = done ? 'Settings in place' : 'Change settings';
    view.list.replaceChildren(...changes.flatMap(change => {
      const term = node('dt', '', change.label);
      const detail = node('dd');
      detail.append(node('span', 'agent-settings-from', change.from || 'Default'), ' → ',
        node('strong', 'agent-settings-to', change.to));
      return [term, detail];
    }));
    view.list.hidden = done;
    view.note.textContent = done ? '' : view.proposal.note;
    view.note.hidden = !view.note.textContent;
    // Applied here says so (view.message); a card opened later, with nothing
    // left to change, only says that these settings are in place.
    view.status.textContent = view.message || (done ? 'These settings are already in place.' : '');
    view.status.hidden = !view.status.textContent;
    view.apply.hidden = view.dismiss.hidden = done;
  }

  function apply(view) {
    const failed = [];
    for (const [name, value] of Object.entries(view.proposal.settings)) {
      if (name === 'agent_model') {
        // The picker's own path: the next message of this chat and the
        // account's pick, as if chosen there (an open chat keeps its model otherwise).
        if (App.agentChat?.applyPick?.(value) !== true) failed.push(name);
        continue;
      }
      const next = name === 'agent_preferences' ? { ...(App.userSettings.get(name) || {}), ...value } : value;
      // set() is false for a value already in place, so only a refusal counts.
      if (!App.userSettings.set(name, next, { source: 'agent' }) && !App.userSettings.accepts(name, next)) failed.push(name);
    }
    if (failed.length) {
      view.message = 'Some settings could not be applied. Change them in Settings.';
    } else {
      applied.add(view.key);
      close(view.key);
      view.message = 'Applied. These settings apply from your next message.';
    }
    App.trackAppEvent?.('app_agent_settings_applied', { settings: Object.keys(view.proposal.settings).join(','), failed: failed.length });
    sync(view);
  }

  function dismiss(view) {
    close(view.key);
    view.card.remove();
  }

  function render(body, { key = '', proposal = null } = {}) {
    if (!body) return;
    let view = views.get(body);
    const value = normalize(proposal);
    // Closed: dismissed, or applied on an earlier visit. Applied in this
    // page keeps its "in place" card until the answer changes.
    const gone = closed.has(key) && !applied.has(key);
    if (view && (!value || view.key !== key || gone)) {
      view.card.remove();
      views.delete(body);
      view = null;
    }
    if (!value || gone) return;
    if (!view) {
      view = create(key);
      views.set(body, view);
    }
    view.proposal = value;
    place(body, view.card);
    sync(view);
  }

  App.agentSettings = { render };
})();
