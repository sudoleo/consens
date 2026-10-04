// "Memory updated" under an Agent answer: what Agent saved, changed or
// forgot during that message, with Undo and a way into Settings > Memory.
// Shared by live, reopened and history answers; the server is the only state.
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

  App.agentMemory = { render, receive };
})();
