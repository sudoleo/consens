// "Memory updated" while an Agent run is working: what Agent saved, changed or
// forgot during that message, with Undo and a way into Settings > Memory. It
// disappears once the answer is final (render without `running`); from then on
// Settings > Memory is the place to review and undo. The server is the only
// state, and the saved turn keeps no memory texts (only which entry changed),
// so the live list comes from the SSE ``memory`` events.
(function () {
  'use strict';
  const App = window.App = window.App || {};
  const views = new WeakMap();
  // Undos confirmed in this page, so a re-render before the saved turn is
  // reloaded never offers Undo again for the same change.
  const undone = new Set();
  const VERBS = { add: 'Saved', update: 'Updated', delete: 'Forgot' };

  function icon() {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('aria-hidden', 'true');
    const path = document.createElementNS(svg.namespaceURI, 'path');
    // A bookmark with a small spark: something kept for later.
    path.setAttribute('d', 'M7 3h10v18l-5-3.5L7 21zM12 7v4M10 9h4');
    svg.append(path);
    return svg;
  }

  function normalize(changes) {
    return (Array.isArray(changes) ? changes : [])
      .filter(change => change && VERBS[change.op] && typeof change.text === 'string' && /^[0-9a-f]{16}$/.test(change.change_id || ''))
      .map(change => ({ ...change, undone: change.undone === true || undone.has(change.change_id) }));
  }

  // One request per change: Agent's changes of one tool call share an id.
  async function undo(view, changeId) {
    const user = window.auth?.currentUser;
    if (!user || view.busy) return;
    const uid = user.uid;
    view.busy = true;
    view.status.textContent = 'Undoing…';
    sync(view);
    try {
      const token = await user.getIdToken();
      if (window.auth?.currentUser?.uid !== uid) return;
      const response = await fetch(`/api/my/memory/changes/${changeId}/undo`, {
        method: 'POST', headers: { Authorization: `Bearer ${token}` },
      });
      let data = {};
      try { data = await response.json(); } catch (_) { /* empty body */ }
      if (window.auth?.currentUser?.uid !== uid) return;
      if (!response.ok) {
        const detail = data.detail || data.error;
        throw new Error((detail && (detail.message || (typeof detail === 'string' ? detail : ''))) || 'Undo failed.');
      }
      undone.add(changeId);
      view.changes = view.changes.map(change => change.change_id === changeId ? { ...change, undone: true } : change);
      view.status.textContent = 'Undone.';
      window.dispatchEvent(new CustomEvent('consensio:memory-changed'));
    } catch (error) {
      view.status.textContent = error.message || 'Undo failed.';
    } finally {
      view.busy = false;
      sync(view);
    }
  }

  function openSettings() {
    document.getElementById('editSystemPromptBtn')?.click();
    // Memory is the first Settings tab; bring the saved list into view.
    requestAnimationFrame(() => document.getElementById('memoryItemsSection')?.scrollIntoView({ block: 'nearest' }));
  }

  function sync(view) {
    const changes = view.changes;
    const active = changes.filter(change => !change.undone);
    view.title.textContent = active.length ? 'Memory updated' : 'Memory change undone';
    view.list.replaceChildren(...changes.map(change => {
      const item = document.createElement('li');
      item.classList.toggle('is-undone', change.undone);
      const verb = document.createElement('span');
      verb.className = 'agent-memory-verb';
      verb.textContent = `${VERBS[change.op]}:`;
      const text = document.createElement(change.op === 'delete' || change.undone ? 's' : 'span');
      text.textContent = change.text;
      item.append(verb, ' ', text);
      return item;
    }));
    const pending = [...new Set(active.map(change => change.change_id))];
    view.undo.hidden = !pending.length;
    view.undo.disabled = view.busy;
    view.undo.dataset.changes = pending.join(',');
    view.note.hidden = !changes.length;
  }

  function render(body, { key = '', changes = [], running = false } = {}) {
    if (!body) return;
    // The note belongs to the working phase. The finished answer stays clean;
    // the activity row ("Updated memory") and Settings > Memory keep the record.
    if (!running) {
      views.get(body)?.note.remove();
      return;
    }
    let view = views.get(body);
    if (!view) {
      const note = document.createElement('div');
      note.className = 'agent-memory-note';
      const head = document.createElement('div');
      head.className = 'agent-memory-head';
      const title = document.createElement('span');
      title.className = 'agent-memory-title';
      const undoButton = document.createElement('button');
      undoButton.type = 'button';
      undoButton.textContent = 'Undo';
      const manage = document.createElement('button');
      manage.type = 'button';
      manage.textContent = 'Manage memory';
      const status = document.createElement('span');
      status.className = 'agent-memory-status';
      status.setAttribute('role', 'status');
      head.append(icon(), title, undoButton, manage, status);
      const list = document.createElement('ul');
      list.className = 'agent-memory-list';
      note.append(head, list);
      view = { note, title, list, undo: undoButton, status, changes: [], busy: false, key: null };
      views.set(body, view);
      undoButton.addEventListener('click', async () => {
        for (const changeId of (undoButton.dataset.changes || '').split(',').filter(Boolean).reverse()) {
          await undo(view, changeId);
        }
      });
      manage.addEventListener('click', openSettings);
    }
    if (view.key !== key) view.status.textContent = '';
    view.key = key;
    view.changes = normalize(changes);
    sync(view);
    // Live answers show the note as soon as Agent saved something, which is
    // usually before the answer is written; it stays below the answer.
    view.note.dataset.running = running ? 'true' : '';
    const review = body._agentReview?.parentNode && body._agentReview.parentNode === body.parentNode ? body._agentReview : null;
    const anchor = review || body;
    if (anchor.nextElementSibling !== view.note) anchor.after(view.note);
  }

  // Live SSE ``memory`` event: append to the run's list, newest last.
  function receive(list, event) {
    let added = false;
    for (const change of normalize(event?.changes)) {
      if (!list.some(item => item.change_id === change.change_id && item.item_id === change.item_id && item.op === change.op)) {
        list.push(change);
        added = true;
      }
    }
    // A Settings list loaded earlier in this page follows along.
    if (added) window.dispatchEvent(new CustomEvent('consensio:memory-changed'));
    return list;
  }

  // A quiet hint for accounts that have not let Agent update memory yet: from
  // the second finished answer in this browser, under at most three answers,
  // until switched on or dismissed. One click turns on "Let Agent update
  // memory"; it stays opt-in. Whether the hint fits comes from the turn's own
  // settings, so no extra read: only an explicit `memory.hint === true` (memory
  // readable, in use, opt-in off). `auto === false` alone is no reason: it is
  // also false for a deliberately paused memory and for a turn whose memory
  // read failed. Older turns without the marker show nothing.
  const HINT_KEY = 'consensio.memoryHint.v1';
  const HINT_FROM_ANSWER = 2;
  const HINT_MAX_SHOWN = 3;
  const hints = new WeakMap();
  const counted = new Set();
  function hintState() {
    try { return { answers: 0, shown: 0, off: false, ...JSON.parse(localStorage.getItem(HINT_KEY) || '{}') }; }
    catch (_) { return { answers: 0, shown: 0, off: true }; }
  }
  function saveHintState(value) {
    try { localStorage.setItem(HINT_KEY, JSON.stringify(value)); } catch (_) { /* hint just reappears */ }
  }
  function dismissNudge() {
    saveHintState({ ...hintState(), off: true });
  }

  function nudge(body, { key = '', finished = false, memory = null } = {}) {
    if (!body) return;
    let view = hints.get(body);
    if (view && view.key !== key) { view.note.remove(); hints.delete(body); view = null; }
    if (view) { place(body, view.note); return; }
    if (!finished || !memory || memory.hint !== true || !key) return;
    let state = hintState();
    if (!counted.has(key)) {
      counted.add(key);
      state = { ...state, answers: state.answers + 1 };
      saveHintState(state);
    }
    if (state.off || state.answers < HINT_FROM_ANSWER || state.shown >= HINT_MAX_SHOWN) return;
    saveHintState({ ...state, shown: state.shown + 1 });
    window.App?.trackAppEvent?.('app_memory_hint', { action: 'shown' });

    const note = document.createElement('div');
    note.className = 'agent-memory-note agent-memory-hint';
    const head = document.createElement('div');
    head.className = 'agent-memory-head';
    const text = document.createElement('span');
    text.textContent = 'Agent can remember details you share, like your diet or your job, and use them in later chats.';
    const on = document.createElement('button');
    on.type = 'button';
    on.textContent = 'Turn on';
    const later = document.createElement('button');
    later.type = 'button';
    later.textContent = 'Not now';
    const status = document.createElement('span');
    status.className = 'agent-memory-status';
    status.setAttribute('role', 'status');
    head.append(icon(), text, on, later, status);
    note.append(head);
    view = { note, key };
    hints.set(body, view);
    later.addEventListener('click', () => {
      dismissNudge();
      window.App?.trackAppEvent?.('app_memory_hint', { action: 'dismissed' });
      note.remove(); hints.delete(body);
    });
    on.addEventListener('click', async () => {
      on.disabled = later.disabled = true;
      status.textContent = 'Turning on…';
      const ok = await window.App?.userMemory?.enableAgentMemory?.();
      if (!ok) {
        on.disabled = later.disabled = false;
        status.textContent = 'Could not turn it on. You can do it in Settings › Memory.';
        return;
      }
      dismissNudge();
      text.textContent = 'Memory is on. Agent saves what you share; review or undo any change in Settings › Memory.';
      const manage = document.createElement('button');
      manage.type = 'button';
      manage.textContent = 'Manage memory';
      manage.addEventListener('click', openSettings);
      status.textContent = '';
      on.replaceWith(manage); later.remove();
    });
    place(body, note);
  }
  function place(body, note) {
    const review = body._agentReview?.parentNode && body._agentReview.parentNode === body.parentNode ? body._agentReview : null;
    const anchor = review || body;
    if (anchor.nextElementSibling !== note) anchor.after(note);
  }

  App.agentMemory = { render, receive, nudge, dismissNudge };
})();
