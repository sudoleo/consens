// The Watches page (/app/watches). Since 2026-11-03 a Watch runs the Agent
// on a schedule in its chat (agent_watches.py); since 2026-11-04 (the
// redesign Max signed off) the page reads like this:
//
// * One way in: a field that takes a sentence (watch-composer.js). With no
//   Watch yet it is the page (large, with four ways to begin); with Watches
//   it is a slim field above them that opens as it is focused.
// * What wants the reader comes first ("Since you last looked"): a Watch
//   that needs them as a wide card with Decide, new findings and reached
//   goals as cards. A card opens its chat and counts as seen.
// * "Watching": the running and paused ones, each with its pulse, the last
//   14 looks as dots (grey nothing new, green found, rose needs you, a ring
//   that did not finish) and a ring for the next one. A row opens its
//   panel (a side sheet): the last 30 looks, what they found, the goal, how
//   often (both can change, PATCH), where it writes, Open chat, Pause and
//   End. It replaces the "…" menu.
// * A quiet foot: where findings go (Change opens Notifications: mail and
//   Telegram), the ended Watches and the Consensus Watches from before.
//
// Contract (watch.js calls these at view time): window.App.watchDashboard.
// {render, refresh, renderGuest, renderSkeleton, focusWatch, addCreated,
// compose, commitPending, reset}. Data: GET /agent/watches, GET
// /api/my/watches (the archive), GET /api/my/telegram.
(function () {
  'use strict';
  const App = window.App = window.App || {};
  const ui = () => App.watchUi;
  const PULSE = 14;
  const SVG = {
    eye: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 12s3.5-6 9-6 9 6 9 6-3.5 6-9 6-9-6-9-6Z"/><circle cx="12" cy="12" r="2.5"/></svg>',
    chevron: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 6 6 6-6 6"/></svg>',
    bell: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 16v-5a6 6 0 0 1 12 0v5l1.5 2h-15Z"/><path d="M10 20.5a2 2 0 0 0 4 0"/></svg>',
    check: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m5 12.5 4.5 4.5L19 7.5"/></svg>',
  };
  // Ways to begin on the empty page: the first words and how often.
  const STARTERS = [
    ['A price drops', 'Tell me when the price drops for', 'daily'],
    ['Registration opens', 'Tell me when registration opens for', 'daily'],
    ['A new release', 'Tell me about every new release of', 'weekly'],
    ['News on a topic', 'Every week, tell me what changed around', 'weekly'],
  ];

  // focus: { id, open } of a Watch to show once it is drawn.
  const page = { token: 0, data: null, archive: [], telegram: null, focus: null, showEnded: false,
    showArchive: false, follow: null, followTries: 0, composer: null, pending: null, detail: null,
    notify: null, refocus: null };
  // A Watch the page started runs at once; the page looks again until its
  // first run is there (seconds), then stops (FOLLOW_MAX looks).
  const FOLLOW_DELAYS = [15000, 30000, 60000, 120000];
  const FOLLOW_MAX = 12;

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

  function glyph(name, className) {
    const span = el('span', className);
    span.setAttribute('aria-hidden', 'true');
    span.innerHTML = SVG[name];
    return span;
  }

  function button(className, text, handler) {
    const control = el('button', className, text);
    control.type = 'button';
    if (handler) control.addEventListener('click', handler);
    return control;
  }

  // A Watch id in a selector (hex from the server; CSS.escape where there is one).
  function cssId(value) {
    return window.CSS?.escape ? window.CSS.escape(String(value)) : String(value).replace(/["\\]/g, '\\$&');
  }

  function capitalize(text) {
    const value = String(text || '');
    return value.charAt(0).toUpperCase() + value.slice(1);
  }

  function body() {
    return document.getElementById('watchDashBody');
  }

  // --- what a Watch is right now ------------------------------------------

  // The run a Watch is shown by: its last one, but for an unread Watch the
  // newest that told something (a finding, a question, the goal). A quiet run
  // after it moves last_run on and leaves `unread` set (agent_watches.turn_ended);
  // the card read "Found something · Nothing new." and a question lost its
  // Decide (bug hunt 2026-11-05).
  const TELLS = ['finding', 'needs_you', 'done'];
  function shownRun(watch) {
    const last = watch.last_run;
    if (!watch.unread || TELLS.includes(last?.outcome)) return last;
    const told = (Array.isArray(watch.looks) ? watch.looks : []).filter(look => look?.at && TELLS.includes(look.outcome));
    return told[told.length - 1] || last;
  }

  function stateOf(watch) {
    if (watch.unread && shownRun(watch)?.outcome === 'needs_you' && watch.status !== 'done') return 'needs';
    if (watch.unread) return 'fresh';
    if (watch.status === 'active' || watch.status === 'paused') return 'watching';
    return 'ended';
  }

  function scheduleOf(watch) {
    return App.watchComposer?.scheduleText ? App.watchComposer.scheduleText(watch)
      : App.watchFields?.scheduleLabel ? App.watchFields.scheduleLabel(watch) : watch.interval;
  }

  // Its first run has not ended: due now, or going. Its start moves
  // next_run_at on to the following time at once (agent_watches.claim), so a
  // first run under way says so by `looking` alone (bug hunt 2026-11-04).
  function firstRunPending(watch) {
    return watch.status === 'active' && !watch.last_run
      && (watch.looking === true || Date.parse(watch.next_run_at || '') <= Date.now() + 60000);
  }

  // A chat the page opened for its Watch (agent_watches.create names its
  // sidebar entry "agent_watch_…") is in the sidebar once a run of it
  // answered, a failed one too (routers/agent.py _save_interrupted); a run
  // that did not start (a busy chat's retry, a refusal) wrote none. A Watch
  // started in a chat (the agent's proposal, the pill's sheet) has its chat
  // already. Until 2026-11-06 "no turn_id" stood for the page's own chat,
  // and the sheet's Watch, which has none either, opened no chat during its
  // first look (bug hunt 2026-11-05).
  const ANSWERED = ['finding', 'needs_you', 'done', 'quiet', 'failed'];
  function chatPending(watch) {
    if (!watch.bookmark_id) return true;
    if (!String(watch.bookmark_id).startsWith('agent_watch_')) return false;
    const runs = [...(Array.isArray(watch.looks) ? watch.looks : []), watch.last_run];
    return !runs.some(run => ANSWERED.includes(run?.outcome));
  }

  function looking(watch) {
    return watch.status === 'active' && (watch.looking === true || firstRunPending(watch));
  }

  // The one line under the task: what its last run found, or where it stands.
  function lineOf(watch) {
    const last = shownRun(watch);
    const summary = last?.summary || '';
    if (watch.status === 'done') {
      if (watch.ended === 'goal') return summary || App.t('It reached its goal.');
      if (watch.ended === 'chat_gone') return App.t('Its chat was deleted.');
      if (watch.ended === 'google_data') return App.t('Its chat now holds Google information, so it no longer runs on a schedule.');
      if (watch.ended === 'cannot_run') return App.t('It could not start in its chat any more and has ended.');
      return summary || App.t('Ended.');
    }
    if (last?.outcome === 'needs_you') return summary || App.t('A reviewer stopped it. Open the chat to decide.');
    if (['finding', 'done'].includes(last?.outcome) && summary) return summary;
    if (watch.status === 'paused') return App.t('Paused. It looks again once you resume it.');
    if (firstRunPending(watch)) return App.t('Its first look is under way.');
    if (!last) return App.t('Nothing yet. It looks for the first time {when}.', { when: App.format.upcoming(watch.next_run_at) });
    if (last.outcome === 'quiet') return App.t('Nothing new.');
    return App.t('The last look did not finish. It tries again on schedule.');
  }

  // A line that is the model's finding stays as written; ours is translated already.
  function isFinding(watch) {
    const shown = shownRun(watch);
    return Boolean(shown?.summary) && (TELLS.includes(shown?.outcome)
      || (watch.status === 'done' && watch.ended === 'goal'));
  }

  function nextOf(watch) {
    if (watch.status === 'paused') return App.t('Paused');
    if (watch.status === 'done') return App.t(watch.ended === 'goal' ? 'Reached its goal' : 'Ended');
    if (looking(watch)) return App.t('Looking now');
    return watch.next_run_at ? capitalize(App.format.upcoming(watch.next_run_at)) : '';
  }

  function whenOf(watch) {
    const at = shownRun(watch)?.at;
    return at ? App.format.relative(at) : '';
  }

  function kindOf(outcome) {
    if (outcome === 'finding' || outcome === 'done') return 'found';
    if (outcome === 'needs_you') return 'needs';
    if (outcome === 'quiet') return 'quiet';
    return 'missed';
  }

  function looksOf(watch) {
    const looks = Array.isArray(watch.looks) ? watch.looks.filter(look => look && look.at) : [];
    const last = watch.last_run;
    // A run that had run already is no look of its own (agent_watches.py _legacy_look).
    if (looks.length || !last?.at || !last.outcome || last.outcome === 'already_ran') return looks;
    return [{ at: last.at, outcome: last.outcome, summary: last.summary || '' }];
  }

  // One look and no run before it: its first. A Watch from before the looks
  // (2026-11-04) shows only its last run, and `runs` says there were more.
  function onlyFirst(watch, looks) {
    return looks.length === 1 && !(Number(watch.runs) > 1);
  }

  // What the dots say, for a screen reader.
  function pulseSaid(looks, { first = true } = {}) {
    if (!looks.length) return App.t('No looks yet.');
    const found = looks.filter(look => kindOf(look.outcome) === 'found').length;
    const needs = looks.filter(look => kindOf(look.outcome) === 'needs').length;
    const missed = looks.filter(look => kindOf(look.outcome) === 'missed').length;
    const n = looks.length;
    const parts = [];
    if (n === 1 && first) parts.push(App.t(found ? 'Its first look found something.' : 'Its first look found nothing new.'));
    else if (n === 1) parts.push(App.t(found ? 'Its last look found something.' : 'Its last look found nothing new.'));
    else if (!found) parts.push(App.t('Nothing found in the last {n} looks.', { n }));
    else parts.push(App.t(found === 1 ? 'Found something once in the last {n} looks.'
      : 'Found something {found} times in the last {n} looks.', { n, found }));
    if (needs) parts.push(App.t(needs === 1 ? 'Once it needed you.' : '{needs} times it needed you.', { needs }));
    if (missed) parts.push(App.t(missed === 1 ? 'One look did not finish.' : '{missed} looks did not finish.', { missed }));
    return parts.join(' ');
  }

  function dots(looks, { next = false, now = false } = {}) {
    const row = el('span', 'aw-dots');
    row.setAttribute('aria-hidden', 'true');
    for (const look of looks) row.append(el('span', 'aw-dot is-' + kindOf(look.outcome)));
    if (next) row.append(el('span', 'aw-dot is-next' + (now ? ' is-now' : '')));
    return row;
  }

  // --- pictures ---------------------------------------------------------------

  function picture(watch, size = '') {
    const frame = el('span', 'aw-picture' + (size ? ' is-' + size : ''));
    frame.setAttribute('aria-hidden', 'true');
    const image = watch.image;
    if (image?.url) {
      frame.classList.add('is-' + (['item', 'article', 'logo'].includes(image.kind) ? image.kind : 'item'));
      const img = el('img');
      img.src = image.url;
      img.alt = '';
      img.loading = 'lazy';
      img.decoding = 'async';
      img.addEventListener('error', () => {
        frame.className = 'aw-picture is-symbol' + (size ? ' is-' + size : '');
        frame.innerHTML = SVG.eye;
      }, { once: true });
      frame.append(img);
    } else {
      frame.classList.add('is-symbol');
      frame.innerHTML = SVG.eye;
    }
    return frame;
  }

  // --- since you last looked: cards ---------------------------------------------

  function badge(watch, state) {
    if (state === 'needs') {
      const span = el('span', 'aw-badge is-needs');
      span.append(el('span', 'aw-badge-dot'), el('span', '', App.t('Needs you')));
      return span;
    }
    if (watch.status === 'done' && watch.ended === 'goal') {
      const span = el('span', 'aw-badge is-goal');
      span.append(glyph('check', 'aw-badge-check'), el('span', '', App.t('Goal reached')));
      return span;
    }
    if (watch.status === 'done') return el('span', 'aw-badge is-ended', App.t('Ended'));
    const span = el('span', 'aw-badge is-found');
    span.append(el('span', 'aw-badge-dot'), el('span', '', App.t('Found something')));
    return span;
  }

  function card(watch, state) {
    const item = el('li', 'aw-card-item is-' + state);
    const open = el('button', 'aw-card is-' + state);
    open.type = 'button';
    open.dataset.watchId = watch.id;
    const text = (isFinding(watch) ? data : el)('span', 'aw-card-text', lineOf(watch));
    const when = el('span', 'aw-card-when', whenOf(watch));
    when.setAttribute('data-i18n-skip', '');
    const task = data('span', 'aw-card-task', watch.task);
    if (state === 'needs') {
      const kicker = el('span', 'aw-card-kicker');
      kicker.append(badge(watch, state), task, when);
      const copy = el('span', 'aw-card-copy');
      copy.append(kicker, text);
      open.append(picture(watch, 'card'), copy, el('span', 'aw-card-action', App.t('Decide')));
    } else {
      const head = el('span', 'aw-card-head');
      head.append(picture(watch, 'small'), task, when);
      const foot = el('span', 'aw-card-foot');
      const go = el('span', 'aw-card-go', App.t('Open chat'));
      go.append(glyph('chevron', 'aw-card-chevron'));
      foot.append(badge(watch, state), go);
      open.append(head, text, foot);
    }
    const status = state === 'needs' ? App.t('Needs you') : watch.ended === 'goal' ? App.t('Goal reached')
      : watch.status === 'done' ? App.t('Ended') : App.t('Found something');
    open.setAttribute('aria-label', [status, watch.task, lineOf(watch)].filter(Boolean).join('. '));
    open.addEventListener('click', () => openChat(watch));
    item.append(open);
    return item;
  }

  function sinceSection(needs, fresh) {
    const box = el('section', 'aw-section is-since');
    const head = el('h2', 'aw-section-title', App.t('Since you last looked'));
    head.id = 'awSinceTitle';
    box.setAttribute('aria-labelledby', head.id);
    box.append(head);
    if (needs.length) {
      const list = el('ul', 'aw-cards is-wide');
      needs.forEach(watch => list.append(card(watch, 'needs')));
      box.append(list);
    }
    if (fresh.length) {
      const list = el('ul', 'aw-cards');
      fresh.forEach(watch => list.append(card(watch, 'fresh')));
      box.append(list);
    }
    return box;
  }

  // --- watching: rows with their pulse -----------------------------------------

  function row(watch) {
    const state = watch.status === 'active' ? 'running' : watch.status === 'paused' ? 'paused' : 'ended';
    const item = el('li', 'aw-row is-' + state);
    item.dataset.watchId = watch.id;
    const open = el('button', 'aw-open');
    open.type = 'button';
    open.setAttribute('aria-haspopup', 'dialog');
    const text = el('span', 'aw-text');
    const line = (isFinding(watch) ? data : el)('span', 'aw-line', lineOf(watch));
    const meta = el('span', 'aw-meta', state === 'ended' ? '' : scheduleOf(watch));
    meta.setAttribute('data-i18n-skip', '');
    meta.hidden = !meta.textContent;
    text.append(data('span', 'aw-title', watch.task), line, meta);
    const pulse = el('span', 'aw-pulse');
    const all = looksOf(watch);
    const looks = all.slice(-PULSE);
    const said = el('span', 'visually-hidden', pulseSaid(looks, { first: onlyFirst(watch, all) }));
    said.setAttribute('data-i18n-skip', '');
    const next = el('span', 'aw-next' + (looking(watch) ? ' is-now' : ''), nextOf(watch));
    next.setAttribute('data-i18n-skip', '');
    pulse.append(said, dots(looks, { next: state === 'running', now: looking(watch) }), next);
    open.append(picture(watch), text, pulse, glyph('chevron', 'aw-chevron'));
    open.addEventListener('click', () => openDetail(watch.id, open));
    item.append(open);
    return item;
  }

  function watchingSection(watches) {
    const box = el('section', 'aw-section is-watching');
    const top = el('div', 'aw-section-head');
    const head = el('h2', 'aw-section-title', App.t('Watching'));
    head.id = 'awWatchingTitle';
    box.setAttribute('aria-labelledby', head.id);
    const caption = el('span', 'aw-section-caption', App.t('Last {n} looks', { n: PULSE }));
    caption.setAttribute('aria-hidden', 'true');
    top.append(head, caption);
    const list = el('ul', 'aw-list');
    watches.forEach(watch => list.append(row(watch)));
    box.append(top, list);
    return box;
  }

  // --- the empty page and the guest's ---------------------------------------------

  function hero({ guest = false, message = '' } = {}) {
    const box = el('section', 'aw-hero');
    const title = el('h2', 'aw-hero-title', App.t('What should the Agent keep an eye on?'));
    title.id = 'awHeroTitle';
    box.setAttribute('aria-labelledby', title.id);
    const mark = glyph('eye', 'aw-hero-glyph');
    box.append(mark, title, el('p', 'aw-hero-text',
      message || App.t('It looks on a schedule and writes to you only when something changes.')));
    if (message) return box;
    const slot = el('div', 'aw-hero-compose');
    box.append(slot);
    const starters = el('div', 'aw-starters');
    starters.setAttribute('role', 'group');
    starters.setAttribute('aria-label', App.t('Ways to begin'));
    for (const [label, words, interval] of STARTERS) {
      starters.append(button('aw-starter', App.t(label), () => {
        composer()?.setTask(App.t(words) + ' ', { interval });
        composer()?.focus();
      }));
    }
    box.append(starters);
    if (guest) {
      const note = el('p', 'aw-hero-note');
      note.append(el('span', '', App.t('Already have Watches?')), document.createTextNode(' '),
        button('text-link aw-hero-login', App.t('Log in'), event => ui()?.requireAccount?.({}, event.currentTarget)));
      box.append(note);
    } else {
      box.append(el('p', 'aw-hero-note', App.t('You can also start one from the eye under any answer in a chat.')));
    }
    return box;
  }

  // --- the one field ------------------------------------------------------------

  function composer() {
    if (!page.composer && App.watchComposer) {
      page.composer = App.watchComposer.create({ mode: 'inline', source: 'watch_page', onStarted(watch) {
        focusWatch(watch.id, { open: false });
      }, onSettle() {
        // A field emptied and left closes again: the page under it moves once.
        if (page.composer?.isEmpty()) page.composer.refresh();
      } });
    }
    return page.composer;
  }

  // Where the reader is typing, taken before a redraw moves the field.
  function typing() {
    const active = document.activeElement;
    if (!page.composer || !page.composer.element.contains(active)) return null;
    return { node: active, selection: 'selectionStart' in active ? [active.selectionStart, active.selectionEnd] : null };
  }

  // Into the hero on the empty page, above the list otherwise; the same field,
  // so what is typed survives a redraw.
  function placeComposer(host, mode, typed = null) {
    const field = composer();
    if (!field || !host) return;
    field.setMode(mode);
    if (field.element.parentElement !== host) host.append(field.element);
    if (typed?.node.isConnected && document.activeElement !== typed.node) {
      typed.node.focus({ preventScroll: true });
      if (typed.selection) typed.node.setSelectionRange(...typed.selection);
    }
  }

  function composeHost() {
    return document.getElementById('watchDashCompose');
  }

  function clearComposeHost() {
    const host = composeHost();
    if (host) {
      host.hidden = true;
      if (page.composer && page.composer.element.parentElement === host) page.composer.element.remove();
    }
  }

  function syncComposerOptions() {
    const info = page.data;
    if (!info || !page.composer) return;
    page.composer.setOptions({ intervals: Array.isArray(info.intervals) ? info.intervals : undefined,
      limitReached: Number(info.active_count) >= Number(info.active_limit) });
  }

  // --- the foot: where findings go, the ended ones, the archive -----------------------

  function footer(ended, { empty = false } = {}) {
    const foot = el('footer', 'aw-foot');
    // Where findings go matters once something runs; the empty page keeps to its question.
    if (!empty) {
      const note = el('p', 'aw-foot-note');
      const telegram = page.telegram?.connected === true;
      note.append(glyph('bell', 'aw-foot-bell'),
        el('span', '', App.t(telegram ? 'Findings also reach you by email and on Telegram.' : 'Findings also reach you by email.')),
        document.createTextNode(' '),
        button('text-link aw-foot-change', App.t('Change'), event => openNotifications(event.currentTarget)));
      foot.append(note);
    }
    const links = el('div', 'aw-foot-links');
    const drawers = [];
    const drawer = (key, label, count, open, fill) => {
      const id = 'awDrawer-' + key;
      const toggle = button('aw-foot-link', '', () => {
        page[open] = !page[open];
        page.refocus = { selector: '.aw-foot-link[data-key="' + key + '"]' };
        draw();
      });
      toggle.dataset.key = key;
      toggle.setAttribute('aria-expanded', String(page[open]));
      toggle.setAttribute('aria-controls', id);
      toggle.append(el('span', '', App.t(label)), el('span', 'aw-count', String(count)), glyph('chevron', 'aw-foot-chevron'));
      links.append(toggle);
      const box = el('section', 'aw-drawer is-' + key);
      box.id = id;
      box.hidden = !page[open];
      box.setAttribute('aria-label', App.t(label));
      if (page[open]) fill(box);
      drawers.push(box);
    };
    if (ended.length) {
      drawer('ended', 'Ended', ended.length, 'showEnded', box => {
        const list = el('ul', 'aw-list');
        ended.forEach(watch => list.append(row(watch)));
        box.append(list);
      });
    }
    if (page.archive.length) drawer('archive', 'Earlier Watches', page.archive.length, 'showArchive', archive);
    if (links.childElementCount) foot.append(links);
    const fragment = document.createDocumentFragment();
    if (foot.childElementCount) fragment.append(foot, ...drawers);
    return fragment;
  }

  function archive(box) {
    box.append(el('p', 'aw-archive-note',
      App.t('Before Watches ran the Agent, they asked a question again on a schedule. They are archived: nothing checks them any more, and their pages stay as they last were.')));
    const list = el('ul', 'aw-archive-list');
    for (const watch of page.archive) {
      const item = el('li', 'aw-archive-row');
      const link = data('a', 'aw-archive-link', watch.question || '');
      link.href = watch.share_path || '/app/watches';
      const when = watch.last_run_at || watch.updated_at || watch.created_at;
      item.append(link);
      if (when) item.append(el('span', 'aw-archive-when', App.t('Last checked {date}', { date: App.format.date(when) })));
      list.append(item);
    }
    box.append(list);
  }

  // --- Notifications: mail and Telegram ----------------------------------------------

  function telegramRow() {
    const state = page.telegram || {};
    const item = el('div', 'aw-channel');
    const copy = el('div', 'aw-channel-copy');
    copy.append(el('span', 'aw-channel-title', 'Telegram'));
    const note = el('p', 'aw-channel-note');
    copy.append(note);
    const actions = el('div', 'aw-channel-actions');
    item.append(copy, actions);
    const add = (label, handler, className = 'wd-button') => {
      const control = button(className, label, handler);
      actions.append(control);
      return control;
    };
    if (!state.configured) {
      note.textContent = App.t('Telegram is not available right now.');
      return item;
    }
    if (state.connected) {
      const name = state.telegram_username ? '@' + state.telegram_username : (state.telegram_first_name || '');
      note.textContent = name ? App.t('Connected to {name}. Each Watch writes there too, unless you turn it off in its panel.', { name })
        : App.t('Connected. Each Watch writes there too, unless you turn it off in its panel.');
      add(App.t('Send test'), async function () {
        this.disabled = true;
        try {
          await ui().api('POST', '/api/my/telegram/test', {});
          App.toast?.({ message: App.t('A test message is on its way.') });
        } catch (error) {
          App.toast?.({ message: App.userError(error, { fallback: 'Try again.' }) });
        } finally { this.disabled = false; }
      });
      add(App.t('Disconnect'), async function () {
        const confirmed = await App.confirm({ title: App.t('Disconnect Telegram?'),
          body: App.t('Your Watches then write only by email.'), confirmLabel: App.t('Disconnect'), danger: true });
        if (!confirmed) return;
        this.disabled = true;
        try {
          const result = await ui().api('DELETE', '/api/my/telegram', {});
          page.telegram = result.telegram || { configured: true, connected: false };
          App.watchState?.setTelegram?.(page.telegram);
          telegramChanged();
        } catch (error) {
          this.disabled = false;
          App.toast?.({ message: App.userError(error, { fallback: 'Try again.' }) });
        }
      }, 'text-link');
      return item;
    }
    const idle = App.t('Get what your Watches find as a chat message too.');
    note.textContent = idle;
    const connect = add(App.t('Connect Telegram'), () => {
      ui().connectTelegram(next => {
        page.telegram = next;
        App.watchState?.setTelegram?.(next);
        telegramChanged();
      });
    });
    const cancel = add(App.t('Cancel'), () => ui().cancelTelegramPairing(), 'text-link');
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

  function channels() {
    const box = el('div', 'aw-channels');
    const mail = el('div', 'aw-channel');
    const copy = el('div', 'aw-channel-copy');
    copy.append(el('span', 'aw-channel-title', App.t('Email')));
    const address = window.auth?.currentUser?.email || '';
    copy.append(el('p', 'aw-channel-note', address
      ? App.t('A Watch writes to {address} when a look finds something, needs you, or reaches its goal.', { address })
      : App.t('A Watch writes when a look finds something, needs you, or reaches its goal.')));
    mail.append(copy);
    box.append(mail, telegramRow());
    return box;
  }

  function sheet(className, titleText) {
    const dialog = el('dialog', 'modal wd-sheet ' + className);
    const content = el('div', 'modal-content wd-sheet-content');
    const close = button('close close-button wd-sheet-close', '', () => App.modalDialog?.close(dialog));
    close.setAttribute('aria-label', App.t('Close'));
    close.innerHTML = App.closeIcon ? App.closeIcon() : '';
    const head = el('div', 'wd-sheet-head');
    const title = el('h2', 'wd-sheet-title', titleText);
    title.id = className + '-title';
    dialog.setAttribute('aria-labelledby', title.id);
    const main = el('div', 'wd-sheet-main');
    content.append(close, head, title, main);
    dialog.append(content);
    document.body.append(dialog);
    return { dialog, head, title, main, close };
  }

  function openNotifications(opener) {
    if (!page.notify?.dialog.isConnected) {
      page.notify = sheet('wd-notify', App.t('Notifications'));
      App.modalDialog?.bind(page.notify.dialog, { onClose: () => {
        const active = document.activeElement;
        if (active && active !== document.body && !page.notify.dialog.contains(active)) return;
        // Its opener may have been drawn again (Telegram connected): the same control.
        const panel = page.detail?.sheet.dialog.open ? page.detail.sheet.main.querySelector('[data-focus-key="telegram"]') : null;
        (panel || body()?.querySelector('.aw-foot-change'))?.focus({ preventScroll: true });
      } });
    }
    fillNotifications();
    App.modalDialog?.open(page.notify.dialog, { opener, focus: page.notify.close });
  }

  function fillNotifications() {
    if (!page.notify) return;
    page.notify.main.replaceChildren(
      el('p', 'wd-sheet-lead', App.t('Where your Watches tell you when they find something.')), channels());
  }

  function telegramChanged() {
    if (page.notify?.dialog.open) fillNotifications();
    renderDetail();
    draw();
  }

  // --- one Watch: its panel ------------------------------------------------------

  function watchById(id) {
    return (page.data?.watches || []).find(watch => watch.id === id) || null;
  }

  function openDetail(id, opener) {
    if (!watchById(id)) return;
    if (!page.detail?.sheet.dialog.isConnected) {
      const parts = sheet('wd-detail', '');
      App.modalDialog?.bind(parts.dialog, { onClose: () => {
        const closed = page.detail?.id || '';
        if (page.detail) Object.assign(page.detail, { id: '', editing: '', draft: null });
        // The row it came from was drawn again meanwhile (a switch, a poll):
        // focus goes to the same Watch's row or card, never to the page.
        const active = document.activeElement;
        if (closed && (!active || active === document.body || parts.dialog.contains(active))) restoreFocus({ id: closed });
      } });
      page.detail = { sheet: parts, id: '', editing: '', draft: null };
    }
    page.detail.id = id;
    page.detail.editing = '';
    page.detail.draft = null;
    renderDetail();
    App.modalDialog?.open(page.detail.sheet.dialog, { opener, focus: page.detail.sheet.close });
  }

  function closeDetail() {
    if (page.detail?.sheet.dialog.open) App.modalDialog?.close(page.detail.sheet.dialog);
  }

  function statusLine(watch) {
    const p = el('p', 'wd-detail-status');
    const tone = watch.status === 'active' ? (looking(watch) ? 'is-now' : 'is-on')
      : watch.status === 'paused' ? 'is-off' : watch.ended === 'goal' ? 'is-on' : 'is-off';
    let text;
    if (watch.status === 'active') {
      text = looking(watch) ? App.t('Running · looking now') : watch.next_run_at
        ? App.t('Running · next look {when}', { when: App.format.upcoming(watch.next_run_at) }) : App.t('Running');
    } else if (watch.status === 'paused') {
      text = App.t('Paused');
    } else {
      text = watch.ended === 'goal' ? App.t('Reached its goal') : App.t('Ended');
    }
    const words = el('span', '', text);
    words.setAttribute('data-i18n-skip', '');
    p.append(el('span', 'wd-status-dot ' + tone), words);
    return p;
  }

  function activity(watch) {
    const looks = looksOf(watch);
    const box = el('section', 'wd-activity');
    const head = el('div', 'wd-activity-head');
    const first = onlyFirst(watch, looks);
    const title = el('h3', 'wd-activity-title', looks.length
      ? App.t(looks.length > 1 ? 'Last {n} looks' : first ? 'Its first look' : 'Its last look', { n: looks.length })
      : App.t('No looks yet'));
    head.append(title);
    const found = looks.filter(look => kindOf(look.outcome) === 'found').length;
    if (looks.length) {
      head.append(el('span', 'wd-activity-count', found === 0 ? App.t('Nothing found')
        : App.t(found === 1 ? '1 finding' : '{n} findings', { n: found })));
    }
    box.append(head);
    if (!looks.length) {
      // One that ran before its looks were kept is not waiting for its first.
      const ran = Number(watch.runs) > 0;
      const when = watch.status === 'active' && watch.next_run_at ? App.format.upcoming(watch.next_run_at) : '';
      const text = when ? App.t(ran ? 'Next look {when}' : 'Its first look is {when}.', { when })
        : ran ? '' : App.t('Nothing has run yet.');
      if (text) box.append(el('p', 'wd-activity-empty', text));
      return box;
    }
    const said = el('span', 'visually-hidden', pulseSaid(looks, { first }));
    said.setAttribute('data-i18n-skip', '');
    const strip = dots(looks, { next: watch.status === 'active', now: looking(watch) });
    strip.classList.add('is-large');
    if (looks.length >= 12) strip.classList.add('is-spread');
    const axis = el('div', 'wd-activity-axis');
    axis.setAttribute('aria-hidden', 'true');
    axis.setAttribute('data-i18n-skip', '');
    axis.append(el('span', '', App.format.date(looks[0].at)),
      el('span', '', watch.status === 'active' ? App.t('Next look') : App.format.date(looks[looks.length - 1].at)));
    box.append(said, strip, axis);
    return box;
  }

  function finds(watch) {
    const entries = looksOf(watch).filter(look => look.summary || kindOf(look.outcome) === 'missed').slice(-6).reverse();
    if (!entries.length) return null;
    const box = el('section', 'wd-finds');
    box.append(el('h3', 'wd-finds-title', App.t('What it found')));
    const list = el('ul', 'wd-finds-list');
    for (const look of entries) {
      const item = el('li', 'wd-find is-' + kindOf(look.outcome));
      item.append(el('span', 'aw-dot is-' + kindOf(look.outcome)));
      const text = look.summary ? data('span', 'wd-find-text', look.summary)
        : el('span', 'wd-find-text', App.t('A look did not finish. It tried again on schedule.'));
      const when = el('span', 'wd-find-when', App.format.relative(look.at));
      when.setAttribute('data-i18n-skip', '');
      item.append(text, when);
      list.append(item);
    }
    box.append(list);
    return box;
  }

  function setting(key, label, value, { action, valueData = false } = {}) {
    const rowBox = el('div', 'wd-setting');
    rowBox.dataset.key = key;
    const copy = el('div', 'wd-setting-copy');
    copy.append(el('span', 'wd-setting-label', label), (valueData ? data : el)('span', 'wd-setting-value', value));
    rowBox.append(copy);
    if (action) rowBox.append(action);
    return rowBox;
  }

  function toggle(key, label, note, checked, onFlip) {
    const id = 'wdSwitch-' + key;
    const rowBox = el('div', 'wd-setting');
    rowBox.dataset.key = key;
    const copy = el('div', 'wd-setting-copy');
    const name = el('span', 'wd-setting-label', label);
    name.id = id + '-label';
    copy.append(name, el('span', 'wd-setting-value', note));
    const control = button('wd-switch');
    control.dataset.focusKey = key;
    control.setAttribute('role', 'switch');
    control.setAttribute('aria-checked', String(Boolean(checked)));
    control.setAttribute('aria-labelledby', name.id);
    control.append(el('span', 'wd-switch-knob'));
    control.addEventListener('click', async () => {
      // One change at a time: a second click waits for the first.
      if (control.getAttribute('aria-busy') === 'true') return;
      control.setAttribute('aria-busy', 'true');
      try { await onFlip(control.getAttribute('aria-checked') !== 'true'); } finally { control.removeAttribute('aria-busy'); }
    });
    rowBox.append(copy, control);
    return rowBox;
  }

  function goalEditor(watch) {
    const rowBox = el('div', 'wd-setting is-editing');
    rowBox.dataset.key = 'goal';
    const form = el('form', 'wd-edit');
    form.noValidate = true;
    const label = el('label', 'wd-setting-label', App.t('Done when'));
    label.htmlFor = 'wdGoalInput';
    const input = el('input', 'wd-edit-input');
    input.id = 'wdGoalInput';
    input.type = 'text';
    input.maxLength = 200;
    // What is typed survives a redraw of the panel (a poll, back on the tab).
    input.value = page.detail.draft?.goal ?? (watch.goal || '');
    input.placeholder = App.t('registration is open');
    input.setAttribute('data-i18n-skip', '');
    input.setAttribute('autocomplete', 'off');
    input.addEventListener('input', () => { page.detail.draft = { ...page.detail.draft, goal: input.value }; });
    const actions = el('div', 'wd-edit-actions');
    const cancel = button('text-link', App.t('Cancel'), () => {
      page.detail.editing = '';
      page.detail.draft = null;
      renderDetail({ focus: 'goal' });
    });
    const save = el('button', 'wd-button is-primary', App.t('Save'));
    save.type = 'submit';
    actions.append(cancel, save);
    form.append(label, input, el('p', 'wd-edit-hint', App.t('Leave it empty and it runs until you end it.')), actions);
    form.addEventListener('submit', async event => {
      event.preventDefault();
      save.disabled = true;
      const changed = await act(watch, '', { method: 'PATCH', body: { goal: input.value.replace(/\s+/g, ' ').trim() } });
      save.disabled = false;
      if (changed) {
        page.detail.editing = '';
        page.detail.draft = null;
        renderDetail({ focus: 'goal' });
      }
    });
    input.addEventListener('keydown', event => {
      if (event.key === 'Escape') {
        event.preventDefault();
        event.stopPropagation();
        cancel.click();
      }
    });
    rowBox.append(form);
    setTimeout(() => {
      input.focus({ preventScroll: true });
      rowBox.scrollIntoView({ block: 'nearest', behavior: App.motion?.reduced?.() ? 'auto' : 'smooth' });
    }, 0);
    return rowBox;
  }

  // The schedule as it runs: a weekly Watch without its own day (one the
  // Agent prepared) runs on the weekday of its next run, in its time zone.
  function scheduleNow(watch) {
    if (watch.interval !== 'weekly' || watch.run_weekday || !watch.next_run_at) return watch;
    try {
      const day = new Date(watch.next_run_at).toLocaleDateString('en-US', { weekday: 'long', timeZone: watch.timezone || 'UTC' });
      return { ...watch, run_weekday: day.toLowerCase() };
    } catch (_) {
      return watch;
    }
  }

  function scheduleEditor(watch) {
    const rowBox = el('div', 'wd-setting is-editing');
    rowBox.dataset.key = 'schedule';
    const picker = App.watchComposer.schedulePicker({ schedule: page.detail.draft?.schedule || scheduleNow(watch),
      allowed: page.data?.intervals || ['daily', 'weekly'],
      onChange(value) { page.detail.draft = { ...page.detail.draft, schedule: value }; } });
    const actions = el('div', 'wd-edit-actions');
    const cancel = button('text-link', App.t('Cancel'), () => {
      page.detail.editing = '';
      page.detail.draft = null;
      renderDetail({ focus: 'schedule' });
    });
    const save = button('wd-button is-primary', App.t('Save'), async () => {
      const value = picker.value();
      save.disabled = true;
      // Its time stays in its own time zone ("Daily at 08:00 (Berlin time)"),
      // edited from anywhere; the reader's only for a Watch that has none.
      const changed = await act(watch, '', { method: 'PATCH', body: { interval: value.interval, run_time: value.run_time,
        run_weekday: value.run_weekday, timezone: watch.timezone || (() => {
          try { return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'; } catch (_) { return 'UTC'; }
        })() } });
      save.disabled = false;
      if (changed) {
        page.detail.editing = '';
        page.detail.draft = null;
        renderDetail({ focus: 'schedule' });
      }
    });
    actions.append(cancel, save);
    rowBox.append(picker.element, actions);
    rowBox.addEventListener('keydown', event => {
      if (event.key === 'Escape') {
        event.preventDefault();
        event.stopPropagation();
        cancel.click();
      }
    });
    setTimeout(() => {
      picker.focus();
      rowBox.scrollIntoView({ block: 'nearest', behavior: App.motion?.reduced?.() ? 'auto' : 'smooth' });
    }, 0);
    return rowBox;
  }

  function settings(watch) {
    const box = el('section', 'wd-settings');
    box.setAttribute('aria-label', App.t('Settings'));
    const change = (key, text) => {
      const control = button('wd-pill', text, () => { page.detail.editing = key; renderDetail(); });
      control.dataset.focusKey = key;
      return control;
    };
    box.append(page.detail.editing === 'goal' ? goalEditor(watch)
      : setting('goal', App.t('Done when'), watch.goal || App.t('Runs until you end it'),
        { valueData: Boolean(watch.goal), action: change('goal', App.t(watch.goal ? 'Change' : 'Add')) }));
    const schedule = scheduleOf(watch);
    const scheduleRow = page.detail.editing === 'schedule' ? scheduleEditor(watch)
      : setting('schedule', App.t('How often'), schedule, { action: change('schedule', App.t('Change')) });
    scheduleRow.querySelector('.wd-setting-value')?.setAttribute('data-i18n-skip', '');
    box.append(scheduleRow);
    box.append(toggle('email', App.t('Email'), App.t('When a look finds something'), watch.email_enabled,
      value => act(watch, '', { method: 'PATCH', body: { email_enabled: value } }).then(() => renderDetail({ focus: 'email' }))));
    if (page.telegram?.connected) {
      box.append(toggle('telegram', 'Telegram', App.t('Connected'), watch.telegram_enabled,
        value => act(watch, '', { method: 'PATCH', body: { telegram_enabled: value } }).then(() => renderDetail({ focus: 'telegram' }))));
    } else if (page.telegram?.configured) {
      const setUp = button('wd-pill', App.t('Set up'), event => openNotifications(event.currentTarget));
      setUp.dataset.focusKey = 'telegram';
      box.append(setting('telegram', 'Telegram', App.t('Not connected'), { action: setUp }));
    }
    return box;
  }

  function renderDetail({ focus = '' } = {}) {
    const detail = page.detail;
    if (!detail?.id) return;
    const watch = watchById(detail.id);
    if (!watch) { closeDetail(); return; }
    const { sheet: parts } = detail;
    const active = document.activeElement;
    const keep = focus || (parts.dialog.contains(active) ? active.dataset.focusKey || '' : '');
    parts.title.textContent = watch.task;
    parts.title.setAttribute('data-i18n-skip', '');
    parts.head.replaceChildren(picture(watch, 'large'));
    const sections = [statusLine(watch), activity(watch), finds(watch)].filter(Boolean);
    if (watch.status === 'active' || watch.status === 'paused') sections.push(settings(watch));
    const actions = el('div', 'wd-detail-actions');
    const chat = button('wd-button is-primary is-wide', App.t('Open chat'), () => openChat(watch));
    chat.dataset.focusKey = 'chat';
    actions.append(chat);
    if (watch.status === 'active' || watch.status === 'paused') {
      const more = el('div', 'wd-detail-more');
      const pause = button('wd-button', App.t(watch.status === 'active' ? 'Pause' : 'Resume'),
        () => act(watch, watch.status === 'active' ? '/pause' : '/resume').then(() => renderDetail({ focus: 'pause' })));
      pause.dataset.focusKey = 'pause';
      const stop = button('wd-button is-danger', App.t('End Watch'), () => end(watch));
      stop.dataset.focusKey = 'end';
      more.append(pause, stop);
      actions.append(more);
    }
    parts.main.replaceChildren(...sections, actions);
    if (keep) parts.main.querySelector(`[data-focus-key="${keep}"]`)?.focus({ preventScroll: true });
  }

  // --- the page ---------------------------------------------------------------

  function syncHead() {
    const pageBox = document.getElementById('watchDashboard');
    const status = document.getElementById('watchDashStatus');
    const limit = document.getElementById('watchDashLimit');
    const info = page.data;
    const watches = Array.isArray(info?.watches) ? info.watches : [];
    const active = watches.filter(watch => watch.status === 'active');
    if (status) {
      status.classList.remove('is-now', 'is-off');
      let text = '';
      if (info && active.some(looking)) {
        text = App.t('Looking now');
        status.classList.add('is-now');
      } else if (info && active.length) {
        const soonest = active.map(watch => watch.next_run_at).filter(Boolean).sort()[0];
        text = soonest ? App.t('Next look {when}', { when: App.format.upcoming(soonest) }) : '';
      } else if (info && watches.some(watch => watch.status === 'paused')) {
        text = App.t('All your Watches are paused.');
        status.classList.add('is-off');
      }
      const words = status.querySelector('.wd-status-text') || el('span', 'wd-status-text');
      words.setAttribute('data-i18n-skip', '');
      if (words.textContent !== text) words.textContent = text;
      if (!words.isConnected) status.replaceChildren(el('span', 'wd-status-dot'), words);
      status.classList.toggle('is-empty', !text);
    }
    if (limit) {
      if (!info) {
        limit.hidden = true;
      } else {
        limit.hidden = false;
        const count = Number(info.active_count) || 0;
        const max = Number(info.active_limit) || 0;
        const text = App.t('{count} of {limit} running', { count, limit: max });
        // aria-live: said again only when it changed.
        if (limit.dataset.said !== text) {
          limit.dataset.said = text;
          const meter = el('span', 'wd-meter');
          meter.setAttribute('aria-hidden', 'true');
          if (max > 0 && max <= 10) {
            for (let index = 0; index < max; index += 1) meter.append(el('span', 'wd-meter-step' + (index < count ? ' is-on' : '')));
          }
          const words = el('span', 'wd-meter-text', text);
          words.setAttribute('data-i18n-skip', '');
          limit.replaceChildren(meter, words);
        }
      }
      App.agentWatch?.showQuota?.(info);
    }
    pageBox?.classList.toggle('is-empty', Boolean(info) && !watches.some(watch => stateOf(watch) !== 'ended'));
  }

  // Where focus was before a redraw: the same control of the same Watch after it.
  function focusedPlace() {
    const active = document.activeElement;
    const host = body();
    if (!active || !host?.contains(active)) return null;
    const item = active.closest('[data-watch-id]');
    if (item) return { id: item.dataset.watchId };
    if (active.classList.contains('aw-foot-link')) return { selector: `.aw-foot-link[data-key="${active.dataset.key}"]` };
    if (active.classList.contains('aw-foot-change')) return { selector: '.aw-foot-change' };
    return null;
  }

  function restoreFocus(place) {
    if (!place) return;
    const host = body();
    const target = place.id
      ? host?.querySelector(`.aw-row[data-watch-id="${cssId(place.id)}"] .aw-open, .aw-card[data-watch-id="${cssId(place.id)}"]`)
        || nearest(place.id)
      : host?.querySelector(place.selector);
    target?.focus({ preventScroll: true });
  }

  // The Watch's own row is gone (ended into the closed "Ended" drawer, or
  // deleted with its chat): the nearest place that is there, never the page
  // itself (review 2026-11-04). The drawer's toggle for an ended one, else
  // the first Watch, else the field that starts one.
  function nearest(id) {
    const host = body();
    if (!host) return null;
    const watch = watchById(id);
    const ended = watch && stateOf(watch) === 'ended' ? host.querySelector('.aw-foot-link[data-key="ended"]') : null;
    return ended || host.querySelector('.aw-row .aw-open, .aw-card')
      || (page.composer?.element.isConnected ? page.composer.element.querySelector('.wc-task') : null);
  }

  function draw() {
    const host = body();
    if (!host || !page.data) return;
    const typed = typing();
    const place = focusedPlace() || page.refocus;
    page.refocus = null;
    const watches = Array.isArray(page.data.watches) ? page.data.watches : [];
    const groups = { needs: [], fresh: [], watching: [], ended: [] };
    watches.forEach(watch => groups[stateOf(watch)].push(watch));
    // Newest finding first; a running Watch by its next run, the paused ones last.
    const latest = (a, b) => String(shownRun(b)?.at || b.created_at || '').localeCompare(String(shownRun(a)?.at || a.created_at || ''));
    groups.needs.sort(latest);
    groups.fresh.sort(latest);
    groups.ended.sort(latest);
    groups.watching.sort((a, b) => (a.status === 'paused') - (b.status === 'paused')
      || String(a.next_run_at || '').localeCompare(String(b.next_run_at || '')));
    const empty = !groups.needs.length && !groups.fresh.length && !groups.watching.length;
    const fragment = document.createDocumentFragment();
    let heroBox = null;
    if (empty) {
      heroBox = hero();
      fragment.append(heroBox);
    } else {
      if (groups.needs.length || groups.fresh.length) fragment.append(sinceSection(groups.needs, groups.fresh));
      if (groups.watching.length) fragment.append(watchingSection(groups.watching));
    }
    fragment.append(footer(groups.ended, { empty }));
    if (empty) {
      clearComposeHost();
      host.replaceChildren(fragment);
      placeComposer(heroBox.querySelector('.aw-hero-compose'), 'hero', typed);
    } else {
      const compose = composeHost();
      if (compose) compose.hidden = false;
      placeComposer(compose, 'inline', typed);
      host.replaceChildren(fragment);
    }
    syncComposerOptions();
    host.removeAttribute('aria-busy');
    syncHead();
    if (page.pending) {
      const pending = page.pending;
      page.pending = null;
      compose(pending);
    }
    if (page.focus) focusWatch(page.focus.id, { open: page.focus.open });
    else if (!typed) restoreFocus(place);
    // An editor in the panel keeps what is typed: the panel follows once it is closed.
    if (page.detail?.id && page.detail.sheet.dialog.open && !page.detail.editing) renderDetail();
    followFirstRuns();
  }

  function followFirstRuns() {
    clearTimeout(page.follow);
    page.follow = null;
    const pending = (page.data?.watches || []).some(watch => looking(watch));
    if (!pending) {
      page.followTries = 0;
      return;
    }
    if (page.followTries >= FOLLOW_MAX) return;
    page.follow = setTimeout(() => {
      page.follow = null;
      page.followTries += 1;
      if (!page.data || document.visibilityState !== 'visible'
        || document.getElementById('watchDashboard')?.hidden !== false) return;
      load().then(fresh => { if (fresh) draw(); }).catch(() => {});
    }, FOLLOW_DELAYS[Math.min(page.followTries, FOLLOW_DELAYS.length - 1)]);
  }

  async function load() {
    const token = ++page.token;
    const [agent, archived, telegram] = await Promise.all([
      ui().api('GET', '/agent/watches'),
      // Shared with watch.js's own load of the list (one GET, review 2).
      ui().requestWatchList().catch(() => ({ watches: [] })),
      ui().api('GET', '/api/my/telegram').catch(() => ({ telegram: page.telegram || {} })),
    ]);
    if (token !== page.token) return false;
    page.data = agent;
    page.archive = (Array.isArray(archived.watches) ? archived.watches : []).filter(watch => watch.question);
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
      clearComposeHost();
      host.replaceChildren(failureNote(App.userError(error, { fallback: 'Watches could not be loaded. Try again.' })));
      host.removeAttribute('aria-busy');
    }
  }

  function failureNote(message) {
    const box = el('div', 'aw-alert');
    box.setAttribute('role', 'alert');
    box.append(el('p', '', message), button('wd-button', App.t('Try again'), () => render()));
    return box;
  }

  function renderGuest(message) {
    page.token += 1;
    page.data = null;
    closeDetail();
    const host = body();
    if (!host) return;
    syncHead();
    document.getElementById('watchDashboard')?.classList.add('is-empty');
    const typed = typing();
    const box = hero({ guest: true, message });
    clearComposeHost();
    host.replaceChildren(box);
    if (!message) placeComposer(box.querySelector('.aw-hero-compose'), 'hero', typed);
    host.removeAttribute('aria-busy');
    if (page.pending) {
      const pending = page.pending;
      page.pending = null;
      compose(pending);
    }
  }

  function renderSkeleton() {
    const host = body();
    if (!host) return;
    clearComposeHost();
    host.innerHTML = App.watchSkeleton?.() || '<div class="wd-skeleton skeleton-group" role="status" aria-label="Loading your watches"></div>';
    host.setAttribute('aria-busy', 'true');
  }

  // A Watch to show: its card stands out, its row opens its panel (the pill
  // under an answer says "Watching" and comes here).
  // The wish waits only for the list's first drawing: once it is drawn, a
  // Watch ended elsewhere (the pill still says "Watching") shows in the
  // opened "Ended" drawer, and one that is gone is forgotten. Until
  // 2026-11-06 it stayed, and opening the drawer later opened its panel by
  // itself (bug hunt 2026-11-05).
  function focusWatch(id, { open = true } = {}) {
    const wanted = String(id || '');
    page.focus = wanted ? { id: wanted, open } : null;
    const host = body();
    const target = wanted && (host?.querySelector(`.aw-card[data-watch-id="${cssId(wanted)}"]`)
      || host?.querySelector(`.aw-row[data-watch-id="${cssId(wanted)}"] .aw-open`));
    const watch = watchById(wanted);
    if (!target) {
      if (!page.data || !host) return;
      if (watch && stateOf(watch) === 'ended' && !page.showEnded) {
        page.showEnded = true;
        draw();
        return;
      }
      page.focus = null;
      return;
    }
    page.focus = null;
    target.scrollIntoView({ block: 'center', behavior: App.motion?.reduced?.() ? 'auto' : 'smooth' });
    target.focus({ preventScroll: true });
    const item = target.closest('.aw-row, .aw-card');
    item?.classList.add('is-focused');
    setTimeout(() => item?.classList.remove('is-focused'), 1600);
    if (open && watch && target.classList.contains('aw-open')) openDetail(watch.id, target);
  }

  // Every start on this page comes here (watch.js startWatch): the field
  // takes the words and the focus.
  function compose({ task = '' } = {}) {
    const field = composer();
    if (!field) return false;
    if (!field.element.isConnected) {
      page.pending = { task };
      return true;
    }
    if (task) field.setTask(task);
    field.element.scrollIntoView?.({ block: 'center', behavior: App.motion?.reduced?.() ? 'auto' : 'smooth' });
    field.focus();
    return true;
  }

  // --- acting on one --------------------------------------------------------

  function replace(watch) {
    if (!page.data || !watch) return;
    // A read already on its way knows less than this answer: it is dropped.
    page.token += 1;
    const list = page.data.watches || (page.data.watches = []);
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
      // The page drew it already; cards and pills follow the event.
      window.dispatchEvent(new CustomEvent('consensio:agent-watches-changed', { detail: { watch: result.watch, page: true } }));
      return result.watch;
    } catch (error) {
      App.toast?.({ message: App.userError(error, { fallback: 'Try again.' }) });
      return null;
    }
  }

  function openChat(watch) {
    if (watch.unread) {
      // Seen at once here; the chat marks it on the server too (agentWatch.opened).
      watch.unread = false;
      ui().api('POST', `/agent/watches/${encodeURIComponent(watch.id)}/seen`, {}).catch(() => {});
      draw();
    }
    if (chatPending(watch)) {
      App.toast?.({ message: App.t(firstRunPending(watch) ? 'Its first look is under way. Its chat appears in a moment.'
        : watch.status === 'done' ? 'It ended before its first look, so it has no chat.'
          : 'Its chat appears once it has looked for the first time.') });
      return;
    }
    closeDetail();
    window.openBookmark?.(watch.bookmark_id);
  }

  async function end(watch) {
    const confirmed = await App.confirm({ title: App.t('End this Watch?'),
      body: App.t('It stops looking. Its chat and what it found stay.'), confirmLabel: App.t('End Watch'), danger: true });
    if (!confirmed) return;
    const ended = await act(watch, '/stop');
    if (ended) renderDetail({ focus: 'chat' });
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
    page.showArchive = false;
    page.pending = null;
    clearTimeout(page.follow);
    page.follow = null;
    page.followTries = 0;
    closeDetail();
    if (page.notify?.dialog.open) App.modalDialog?.close(page.notify.dialog);
    page.composer?.reset({ reload: true });
  }

  // A Watch started here or on a sheet, changed on a card or in another tab:
  // the open page shows it at once; back on the tab, it reads again.
  window.addEventListener('consensio:agent-watches-changed', event => {
    if (!page.data || event.detail?.loaded || event.detail?.page) return;
    if (event.detail?.watch) replace(event.detail.watch);
  });
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible' && page.data && document.getElementById('watchDashboard')?.hidden === false) {
      load().then(fresh => { if (fresh) draw(); }).catch(() => {});
    }
  });
  App.watchDashboard = {
    render, refresh: render, renderGuest, renderSkeleton, focusWatch, addCreated, compose,
    // The page keeps nothing pending (deleting is "End", taken back by no Undo).
    commitPending() {}, reset,
  };
})();
