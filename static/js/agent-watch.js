// The Watch the Agent prepared (agent_watch.py) as a card under the answer.
// The Agent only proposes: the card starts the Watch through the create
// dialog's own POST /api/watch, in one click with the dialog's defaults
// (watch.js watchDefaults), or "Adjust" opens that dialog prefilled. The card
// belongs to a completed answer, which points to it; agent-chat.js passes the
// saved turn's proposal only then. Whether the question is already watched or
// no slot is free comes from the account's watch list (watch.js
// receiveWatchList: every load of /api/my/watches in this page, the
// dashboard's too), never from the saved turn.
(function () {
  'use strict';
  const App = window.App = window.App || {};
  const MIN_QUESTION = 8;
  const MAX_GOALS = 3;
  const INTERVALS = ['daily', 'weekly', 'monthly'];
  const views = new WeakMap();
  const shown = new Set();
  let serial = 0;

  function line(value) {
    return typeof value === 'string' ? value.replace(/\s+/g, ' ').trim() : '';
  }

  function normalize(proposal) {
    const question = line(proposal?.question);
    if (question.length < MIN_QUESTION) return null;
    const goals = (Array.isArray(proposal.goals) ? proposal.goals : []).map(line).filter(Boolean).slice(0, MAX_GOALS);
    return { question, goals, interval: INTERVALS.includes(proposal.interval) ? proposal.interval : 'weekly' };
  }

  function icon() {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('aria-hidden', 'true');
    // The eye of the Watch button in the Consensus footer.
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

  function create(key) {
    const card = node('section', 'agent-watch-card');
    const title = node('span', 'agent-watch-title');
    const head = node('div', 'agent-watch-head');
    head.append(icon(), title);
    title.id = `agentWatchTitle${serial += 1}`;
    card.setAttribute('aria-labelledby', title.id);
    const question = node('p', 'agent-watch-question');
    const goal = node('p', 'agent-watch-goal');
    const settings = node('p', 'agent-watch-settings');
    const status = node('p', 'agent-watch-status');
    status.setAttribute('role', 'status');
    const view = { key, card, title, question, goal, settings, status, proposal: null, created: null, busy: false, message: '' };
    view.start = button('btn agent-watch-start', 'Start watching', () => start(view));
    view.adjust = button('agent-watch-link', 'Adjust', () => adjust(view));
    view.manage = button('agent-watch-link', 'Open Watches', () => App.watchUi?.openWatchDialog?.('list'));
    const actions = node('div', 'agent-watch-actions');
    actions.append(view.start, view.adjust, view.manage);
    card.append(head, question, goal, settings, status, actions);
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

  function sync(view) {
    const ui = App.watchUi;
    const { proposal } = view;
    const watch = view.created || App.watch?.watchedFor?.(proposal.question) || null;
    const limits = App.watchState?.limits;
    const full = !watch && Boolean(limits?.atLimit);
    const state = watch ? 'watching' : full ? 'full' : 'proposal';
    // Paused by the user or after failed checks ("paused_error") alike.
    const paused = Boolean(watch) && !['active', 'resolved'].includes(watch.status);
    view.card.dataset.state = state;
    view.title.textContent = !watch ? 'Watch this question'
      : paused ? 'Watch paused' : watch.status === 'resolved' ? 'Watch resolved' : 'Watching';
    view.question.textContent = watch?.question || proposal.question;
    const goal = watch ? line(watch.condition) : proposal.goals[0] || '';
    view.goal.textContent = !goal ? 'Any change to the answer'
      : `${watch?.status === 'resolved' ? 'Waited for' : 'Waiting for'}: ${goal}`;
    view.settings.hidden = Boolean(watch);
    if (!watch && ui) view.settings.textContent = ui.settingsSummary(ui.watchDefaults(proposal.interval));
    // A failed start speaks only while starting is still the next step: an
    // existing Watch or a full account says what holds now.
    view.status.textContent = state === 'proposal' ? view.message
      : paused ? 'You already watch this question. The Watch is paused.'
        : watch?.status === 'resolved' ? 'This Watch found what it waited for.'
          : watch && ui ? `Checks ${ui.formatWatchSchedule(watch)}.`
            : full && ui ? ui.limitMessage(limits) : '';
    view.status.hidden = !view.status.textContent;
    view.start.hidden = view.adjust.hidden = Boolean(watch);
    view.start.disabled = view.busy || full;
    view.start.textContent = view.busy ? 'Starting…' : 'Start watching';
    view.adjust.disabled = view.busy;
    view.manage.hidden = !(watch || full);
  }

  // One click: the question, the most likely goal and the dialog's defaults.
  async function start(view) {
    const ui = App.watchUi;
    if (!ui || view.busy) return;
    const proposal = view.proposal;
    const payload = { ...ui.watchDefaults(proposal.interval), question: proposal.question, condition: proposal.goals[0] || '' };
    view.busy = true;
    view.message = '';
    sync(view);
    try {
      const data = await ui.api('POST', '/api/watch', payload);
      view.created = data.watch;
      App.trackAppEvent?.('app_watch_created', { interval: data.watch.interval, source: 'agent',
        has_goal: Boolean(payload.condition), goal_source: payload.condition ? 'suggested' : 'none' });
    } catch (error) {
      // Already watched (409) or no free slot (429) is then said by the
      // refreshed list below; any other refusal, the request rate limit
      // included, keeps its reason while Start is still offered.
      view.message = `Watch could not be started: ${error.message}`;
    } finally {
      view.busy = false;
      sync(view);
      // From then on the account's list decides, also about a Watch that is
      // deleted later on /app/watches.
      App.watch?.refreshQuota?.().then(() => { view.created = null; sync(view); }, () => {});
    }
  }

  function adjust(view) {
    const { question, goals, interval } = view.proposal;
    App.watchUi?.openWatchDialog?.('create', { question, goals, goal: goals[0] || '', interval, source: 'agent' });
  }

  function render(body, { key = '', proposal = null } = {}) {
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
    }
    view.proposal = value;
    place(body, view.card);
    sync(view);
    // Slots and watched questions load once per session; the event below
    // brings them in.
    App.watch?.loadState?.().catch(() => {});
  }

  window.addEventListener('consensio:watches-changed', () => shown.forEach(sync));

  App.agentWatch = { render };
})();
