// Private chat files and document versions. Everything belongs to the current
// authenticated chat and lives in memory only, never in localStorage.
//
// Two places show it:
// - #agentAnswerResources (after the answer text): the documents created or
//   revised in the displayed turn (one card per document_id), per-file upload
//   progress and a note when a file of this turn was only partly readable.
// - #agentWorkspace (below the answer): the collapsed chat-level disclosure
//   "Files in this chat (n)" with every upload, mail attachment and document.
//
// refresh(chatId, force) is cheap to call on every render: without force it
// only re-projects the cached list (for example when the turn changes). A
// fetch happens on a chat change or with force, at most once per 300 ms per
// chat (leading call, one trailing call). It never refreshes Google actions.
(() => {
  const App = window.App = window.App || {};
  const WINDOW_MS = 300;
  const RETRY_MS = 1500;
  const SVG = 'http://www.w3.org/2000/svg';
  const ICONS = {
    document: 'M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8zM14 3v5h5M9 13h6M9 17h6',
    download: 'M12 4v11M7 10l5 5 5-5M5 20h14',
    more: 'M5 12h.01M12 12h.01M19 12h.01',
    warning: 'M12 4 2.5 20h19zM12 10v4M12 17h.01',
    mail: 'M4 6h16v12H4zM4 7l8 6 8-6',
  };
  let chat = '', owner = '', turn = '', data = null, error = '', generation = 0, controller = null;
  let lastStart = -Infinity, timer = null, retryTimer = null, inflight = null, waiting = null, rendered = '';
  let revision = 0, retried = false;
  const uploads = new Map(); // chatId -> [{name, mime, size, state, message}]
  const openState = { files: new Set(), versions: new Set() };
  let confirmKey = '';

  function node(tag, className, text) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (text !== undefined && text !== null) el.textContent = text;
    return el;
  }
  function icon(name) {
    const svg = document.createElementNS(SVG, 'svg');
    svg.setAttribute('viewBox', '0 0 24 24'); svg.setAttribute('aria-hidden', 'true');
    svg.setAttribute('class', `agent-files-icon agent-files-icon-${name}`);
    const path = document.createElementNS(SVG, 'path'); path.setAttribute('d', ICONS[name]);
    svg.append(path);
    return svg;
  }
  function answerResources() {
    let resources = document.getElementById('agentAnswerResources');
    if (!resources) {
      // Package C adds this hook to the template; create it until that lands.
      // Placed where the template will put it (before the error line), so the
      // answer's evidence and copy rows keep their own stable anchors on body.
      const body = document.getElementById('agentAnswerBody');
      if (!body) return null;
      resources = node('div'); resources.id = 'agentAnswerResources';
      const error = document.getElementById('agentAnswerError');
      if (error && error.parentElement === body.parentElement) error.before(resources); else body.parentElement.append(resources);
    }
    resources.classList.add('agent-resources');
    return resources;
  }
  function filesPanel() {
    let panel = document.getElementById('agentWorkspace');
    const answer = document.getElementById('agentAnswer');
    if (!panel) {
      if (!answer) return null;
      panel = node('section', 'agent-workspace agent-files'); panel.id = 'agentWorkspace';
      panel.setAttribute('aria-label', 'Files in this chat');
      panel.hidden = true;
    }
    // Below the answer and any Google action cards, which need attention first.
    const anchor = document.getElementById('agentGoogleActions') || answer;
    if (anchor && anchor.parentElement && anchor.nextElementSibling !== panel) anchor.after(panel);
    return panel;
  }

  async function request(path, options = {}) {
    const user = window.auth?.currentUser;
    if (!user) throw new Error('Sign in to access files.');
    const token = await user.getIdToken();
    if (window.auth?.currentUser?.uid !== user.uid) throw new Error('Account changed.');
    const response = await fetch(path, { ...options, headers: { Authorization: `Bearer ${token}`, ...options.headers } });
    if (window.auth?.currentUser?.uid !== user.uid) throw new Error('Account changed.');
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(typeof body.detail === 'string' ? body.detail : body.error || 'The file request failed. Please retry.');
    }
    return response;
  }
  // Shared with agent-google.js: a plain inline button that reports failures.
  function button(label, action) {
    const control = node('button', 'settings-inline-btn', label); control.type = 'button';
    control.addEventListener('click', async () => {
      control.disabled = true;
      try { await action(); } catch (failure) { App.showPopup?.(failure.message); }
      finally { control.disabled = false; }
    });
    return control;
  }
  async function download(chatId, file) {
    const response = await request(`/agent/chats/${chatId}/files/${file.id}`);
    const blob = await response.blob();
    const url = URL.createObjectURL(blob), link = document.createElement('a');
    link.href = url; link.download = file.name; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
  }

  // ---- formatting -----------------------------------------------------------
  function extension(file) {
    const match = /\.([a-z0-9]{1,5})$/i.exec(file.name || '');
    if (match) return match[1].toUpperCase();
    const mime = file.mime || '';
    if (mime.startsWith('image/')) return 'IMG';
    if (mime === 'application/pdf') return 'PDF';
    if (mime.includes('wordprocessingml')) return 'DOCX';
    if (mime.startsWith('text/')) return 'TXT';
    return 'FILE';
  }
  function size(bytes) {
    const value = Number(bytes) || 0;
    if (!value) return '';
    if (value >= 1024 * 1024) return `${(value / (1024 * 1024)).toFixed(1)} MB`;
    return `${Math.max(1, Math.round(value / 1024))} KB`;
  }
  function expiry(file) {
    const time = Date.parse(file.expires_at || '');
    if (!Number.isFinite(time)) return '';
    if (time <= Date.now()) return 'Expired';
    return `Expires ${new Date(time).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}`;
  }
  function sender(value) {
    const text = String(value || '').trim();
    const named = /^"?([^"<]+?)"?\s*<[^>]+>$/.exec(text);
    return (named ? named[1] : text).trim();
  }
  function mailOrigin(file) {
    if (!file.origin?.message_id) return '';
    const evidence = App.agentGoogle?.evidenceFor?.(file.origin.message_id) || null;
    const subject = file.origin_subject || evidence?.subject || '';
    const from = sender(file.origin_from || evidence?.from || '');
    if (!subject && !from) return 'From an email attachment';
    return `From email: ${subject || '(no subject)'}${from ? ` (${from})` : ''}`;
  }
  function documentTitle(file) {
    return file.title || String(file.name || 'Document').replace(/-v\d+\.[a-z0-9]+$/i, '').replace(/\.[a-z0-9]+$/i, '');
  }
  function partial(file) { return Array.isArray(file.warnings) && file.warnings.length > 0; }

  // ---- data shaping -----------------------------------------------------------
  function groupDocuments(files) {
    const groups = new Map();
    for (const file of files) {
      if (file.kind !== 'document' || !file.document_id) continue;
      let group = groups.get(file.document_id);
      if (!group) { group = { id: file.document_id, title: documentTitle(file), versions: new Map() }; groups.set(file.document_id, group); }
      if (file.title) group.title = file.title;
      const number = Number(file.version) || 1;
      let version = group.versions.get(number);
      if (!version) {
        version = { number, parent: Number(file.parent_version) || 0, turn: file.turn_id || '', files: [] };
        group.versions.set(number, version);
      }
      version.files.push(file);
    }
    for (const group of groups.values()) {
      group.list = [...group.versions.values()].sort((a, b) => b.number - a.number);
      for (const version of group.list) version.files.sort((a, b) => extension(a).localeCompare(extension(b)));
    }
    return [...groups.values()];
  }
  function currentTurn() {
    const registry = App.runRegistry;
    const context = registry?.visible?.();
    if (context && context.config?.executionMode === 'agent') {
      return { id: context.consensus?.completedTurn?.id || context.metadata?.agentTurnId || '',
        fileIds: context.metadata?.fileIds || context.consensus?.completedTurn?.agent_settings?.file_ids || [] };
    }
    const basis = registry?.getSelectedConversationBasis?.({ includeHistory: false });
    return { id: basis?.turnId || basis?.currentTurn?.id || '', fileIds: basis?.currentTurn?.agent_settings?.file_ids || [] };
  }

  // ---- menus and confirmation -------------------------------------------------
  function closeMenus(except) {
    for (const open of document.querySelectorAll('.agent-files-more[aria-expanded="true"]')) {
      if (open === except) continue;
      open.setAttribute('aria-expanded', 'false');
      open.nextElementSibling?.setAttribute('hidden', '');
    }
  }
  document.addEventListener('click', event => {
    if (!event.target.closest?.('.agent-files-menu-wrap')) closeMenus();
  });
  document.addEventListener('keydown', event => {
    if (event.key !== 'Escape') return;
    const open = document.querySelector('.agent-files-more[aria-expanded="true"]');
    if (open) { closeMenus(); open.focus(); }
  });
  function overflow(key, label, items) {
    const wrap = node('div', 'agent-files-menu-wrap');
    const trigger = node('button', 'agent-files-more'); trigger.type = 'button';
    trigger.setAttribute('aria-label', label); trigger.title = 'More actions';
    trigger.setAttribute('aria-haspopup', 'menu'); trigger.setAttribute('aria-expanded', 'false');
    trigger.append(icon('more'));
    const menu = node('div', 'agent-files-menu'); menu.setAttribute('role', 'menu'); menu.hidden = true;
    for (const item of items) {
      const entry = node('button', `agent-files-menu-item${item.danger ? ' is-danger' : ''}`, item.label);
      entry.type = 'button'; entry.setAttribute('role', 'menuitem');
      entry.addEventListener('click', () => { closeMenus(); item.run(); });
      menu.append(entry);
    }
    const toggle = open => {
      closeMenus(trigger);
      trigger.setAttribute('aria-expanded', String(open)); menu.hidden = !open;
      if (open) menu.querySelector('button')?.focus();
    };
    trigger.addEventListener('click', () => toggle(trigger.getAttribute('aria-expanded') !== 'true'));
    menu.addEventListener('keydown', event => {
      const entries = [...menu.querySelectorAll('button')];
      const index = entries.indexOf(document.activeElement);
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        entries[(index + (event.key === 'ArrowDown' ? 1 : entries.length - 1)) % entries.length]?.focus();
      } else if (event.key === 'Tab') closeMenus();
    });
    wrap.append(trigger, menu);
    return wrap;
  }
  function confirmation(key, message, label, removeFiles) {
    const box = node('div', 'agent-files-confirm');
    box.dataset.confirmKey = key;
    box.setAttribute('role', 'group'); box.setAttribute('aria-label', 'Confirm removal');
    const text = node('p', '', message);
    const actions = node('div', 'agent-files-confirm-actions');
    const remove = node('button', 'agent-files-danger', label); remove.type = 'button';
    const cancel = node('button', 'agent-files-ghost', 'Cancel'); cancel.type = 'button';
    cancel.addEventListener('click', () => { confirmKey = ''; rendered = ''; project(); focusKey(key); });
    remove.addEventListener('click', async () => {
      const chatId = chat;
      remove.disabled = cancel.disabled = true; remove.textContent = 'Removing…';
      try {
        for (const file of removeFiles) await request(`/agent/chats/${chatId}/files/${file.id}`, { method: 'DELETE' });
        confirmKey = '';
      } catch (failure) {
        App.showPopup?.(failure.message);
        remove.disabled = cancel.disabled = false; remove.textContent = label;
        return;
      }
      if (chat === chatId) await refresh(chatId, true);
    });
    actions.append(remove, cancel);
    box.append(text, actions);
    return box;
  }
  function askToRemove(key) {
    confirmKey = key; rendered = ''; project();
    // Start on the safe choice; Remove is one Tab away.
    const box = [...document.querySelectorAll('.agent-files-confirm')].find(item => item.dataset.confirmKey === key);
    box?.querySelector('.agent-files-ghost')?.focus({ preventScroll: true });
    // The sticky composer can cover the bottom of the page; keep the choice visible.
    box?.scrollIntoView?.({ block: 'center', behavior: 'smooth' });
  }
  function focusKey(key) {
    const owner = [...document.querySelectorAll('[data-files-key]')].find(item => item.dataset.filesKey === key);
    owner?.querySelector('.agent-files-more')?.focus({ preventScroll: true });
  }

  // ---- rendering ----------------------------------------------------------------
  function downloadChip(chatId, file, context, withLabel) {
    const control = node('button', withLabel ? 'agent-files-chip' : 'agent-files-icon-btn'); control.type = 'button';
    control.setAttribute('aria-label', `Download ${file.name}${context}`);
    control.title = `Download ${file.name}`;
    control.append(icon('download'));
    if (withLabel) {
      control.append(node('span', 'agent-files-chip-type', extension(file)));
      if (file.size) control.append(node('span', 'agent-files-chip-size', size(file.size)));
    }
    const available = ['ready', 'partial'].includes(file.status) && expiry(file) !== 'Expired';
    control.disabled = !available;
    if (!available) control.title = file.status === 'processing' ? 'Still processing' : 'No longer available';
    control.addEventListener('click', async () => {
      control.disabled = true;
      try { await download(chatId, file); } catch (failure) { App.showPopup?.(failure.message); }
      finally { control.disabled = false; }
    });
    return control;
  }
  function versionMeta(version) {
    return version.parent ? `Version ${version.number} · revised from version ${version.parent}` : `Version ${version.number}`;
  }
  function documentCard(chatId, group, { upTo = Infinity, turnId = '', compact = false, scope }) {
    const versions = group.list.filter(version => version.number <= upTo);
    const current = versions[0];
    if (!current) return null;
    const key = `${scope}:doc:${group.id}:${current.number}`;
    const card = node('article', `agent-doc-card${compact ? ' is-compact' : ''}`);
    card.dataset.filesKey = key; card.dataset.documentId = group.id;
    card.setAttribute('aria-label', `${group.title}, version ${current.number}`);
    const head = node('div', 'agent-doc-head');
    const mark = node('span', 'agent-doc-mark'); mark.append(icon('document'));
    const titles = node('div', 'agent-doc-titles');
    const title = node('h3', 'agent-doc-title');
    title.append(node('span', '', group.title));
    if (!compact && turnId && current.turn === turnId) {
      title.append(node('span', 'agent-files-badge is-new', current.number > 1 ? 'Updated in this answer' : 'New in this answer'));
    }
    const meta = node('p', 'agent-doc-meta', [versionMeta(current), expiry(current.files[0] || {})].filter(Boolean).join(' · '));
    titles.append(title, meta);
    head.append(mark, titles);
    const removeLabel = `Remove version ${current.number}…`;
    head.append(overflow(key, `More actions for ${group.title}, version ${current.number}`, [{ label: removeLabel, danger: true,
      run: () => askToRemove(key) }]));
    card.append(head);
    const chips = node('div', 'agent-doc-downloads');
    for (const file of current.files) chips.append(downloadChip(chatId, file, `, version ${current.number}`, true));
    card.append(chips);
    if (confirmKey === key) {
      card.append(confirmation(key, `Remove ${group.title} version ${current.number} (${current.files.map(extension).join(' and ')})? The agent can no longer use or revise it.`,
        'Remove version', current.files));
    }
    if (!compact && current.number === group.list[0].number) {
      card.append(node('p', 'agent-doc-hint', `Ask for changes in the chat to create version ${current.number + 1}.`));
    }
    const earlier = versions.slice(1);
    if (earlier.length) {
      const details = node('details', 'agent-doc-earlier');
      const openKey = `${scope}:${group.id}`;
      details.open = openState.versions.has(openKey);
      details.addEventListener('toggle', () => { if (details.open) openState.versions.add(openKey); else openState.versions.delete(openKey); });
      details.append(node('summary', '', `Earlier versions (${earlier.length})`));
      for (const version of earlier) {
        const rowKey = `${scope}:doc:${group.id}:${version.number}`;
        const row = node('div', 'agent-doc-version'); row.dataset.filesKey = rowKey;
        row.append(node('span', 'agent-doc-version-label', versionMeta(version)));
        const actions = node('div', 'agent-doc-downloads');
        for (const file of version.files) actions.append(downloadChip(chatId, file, `, version ${version.number}`, true));
        actions.append(overflow(rowKey, `More actions for ${group.title}, version ${version.number}`, [{ label: `Remove version ${version.number}…`, danger: true,
          run: () => askToRemove(rowKey) }]));
        row.append(actions);
        details.append(row);
        if (confirmKey === rowKey) {
          details.append(confirmation(rowKey, `Remove ${group.title} version ${version.number} (${version.files.map(extension).join(' and ')})? The agent can no longer use or revise it.`,
            'Remove version', version.files));
        }
      }
      card.append(details);
    }
    return card;
  }
  function fileRow(chatId, file) {
    const key = `files:file:${file.id}`;
    const row = node('div', `agent-file-row${partial(file) ? ' has-warning' : ''}`);
    row.dataset.filesKey = key;
    const type = node('span', 'agent-file-type', file.origin?.message_id ? '' : extension(file));
    if (file.origin?.message_id) { type.append(icon('mail')); type.setAttribute('aria-hidden', 'true'); }
    else type.setAttribute('aria-hidden', 'true');
    const main = node('div', 'agent-file-main');
    const name = node('span', 'agent-file-name', file.name);
    main.append(name);
    const origin = mailOrigin(file);
    const status = file.status === 'processing' ? 'Processing…' : file.status === 'deleting' ? 'Removing…' : '';
    const meta = node('span', 'agent-file-meta', [status, extension(file), size(file.size), expiry(file)].filter(Boolean).join(' · '));
    if (partial(file)) {
      const badge = node('span', 'agent-files-badge is-warning');
      badge.append(icon('warning'), node('span', '', 'Partly read'));
      meta.prepend(badge);
    }
    main.append(meta);
    if (origin) main.append(node('span', 'agent-file-origin', origin));
    for (const warning of file.warnings || []) main.append(node('span', 'agent-file-warning', warning));
    const actions = node('div', 'agent-file-actions');
    actions.append(downloadChip(chatId, file, '', false));
    actions.append(overflow(key, `More actions for ${file.name}`, [{ label: 'Remove…', danger: true,
      run: () => askToRemove(key) }]));
    row.append(type, main, actions);
    const wrap = node('div', 'agent-file-item'); wrap.append(row);
    if (confirmKey === key) {
      wrap.append(confirmation(key, `Remove ${file.name}? The agent can no longer use it in this chat.`, 'Remove file', [file]));
    }
    return wrap;
  }
  function uploadRows(list) {
    const box = node('div', 'agent-uploads');
    box.setAttribute('aria-live', 'polite');
    for (const item of list) {
      const row = node('div', `agent-upload-row is-${item.state}`);
      const type = node('span', 'agent-file-type', extension(item)); type.setAttribute('aria-hidden', 'true');
      const main = node('div', 'agent-file-main');
      main.append(node('span', 'agent-file-name', item.name));
      const status = node('span', 'agent-file-meta');
      if (item.state === 'uploading') {
        status.append(node('span', 'agent-upload-spinner'), node('span', '', extension(item) === 'PDF' ? 'Uploading and reading PDF…' : 'Uploading and reading…'));
      } else if (item.state === 'waiting') status.textContent = 'Waiting…';
      else status.textContent = item.warnings?.length ? 'Uploaded · partly read' : 'Uploaded';
      main.append(status);
      row.append(type, main);
      box.append(row);
    }
    return box;
  }
  function partialNotice(files) {
    const box = node('div', 'agent-resource-notice');
    box.append(icon('warning'));
    const text = node('div', 'agent-resource-notice-text');
    text.append(node('strong', '', files.length === 1 ? '1 file was only partly readable' : `${files.length} files were only partly readable`));
    for (const file of files) text.append(node('span', '', `${file.name}: ${file.warnings.join(' ')}`));
    box.append(text);
    return box;
  }

  function signature(turnInfo) {
    const origins = (data?.files || []).filter(file => file.origin?.message_id).map(mailOrigin);
    return JSON.stringify([chat, revision, turnInfo.id, turnInfo.fileIds, error, confirmKey, origins,
      (uploads.get(chat) || []).map(item => [item.name, item.state])]);
  }
  function hideAll() {
    const resources = document.getElementById('agentAnswerResources');
    if (resources) { resources.replaceChildren(); resources.hidden = true; }
    const panel = document.getElementById('agentWorkspace');
    if (panel) { panel.replaceChildren(); panel.hidden = true; }
    rendered = '';
  }
  function project() {
    if (!chat) { hideAll(); return; }
    const resources = answerResources(), panel = filesPanel();
    const turnInfo = currentTurn();
    const key = signature(turnInfo);
    if (key === rendered && (!resources || resources.isConnected)) return;
    rendered = key; turn = turnInfo.id;
    const files = data?.files || [];
    const chatId = chat;
    if (resources) {
      resources.replaceChildren();
      const pending = uploads.get(chatId) || [];
      if (pending.length) resources.append(uploadRows(pending));
      const selected = new Set(turnInfo.fileIds || []);
      const readable = files.filter(file => selected.has(file.id) && partial(file));
      if (readable.length) resources.append(partialNotice(readable));
      if (turnInfo.id) {
        for (const group of groupDocuments(files)) {
          const mine = group.list.filter(version => version.turn === turnInfo.id);
          if (!mine.length) continue;
          const card = documentCard(chatId, group, { upTo: mine[0].number, turnId: turnInfo.id, scope: 'answer' });
          if (card) resources.append(card);
        }
      }
      resources.hidden = !resources.childElementCount;
    }
    if (!panel) return;
    panel.replaceChildren();
    if (error) {
      const notice = node('div', 'agent-files-error');
      notice.append(icon('warning'), node('span', '', `Couldn't load chat files. ${error}`));
      const retry = node('button', 'agent-files-ghost', 'Retry'); retry.type = 'button';
      retry.addEventListener('click', () => refresh(chatId, true));
      notice.append(retry);
      panel.append(notice); panel.hidden = false; return;
    }
    const groups = groupDocuments(files);
    const plain = files.filter(file => !(file.kind === 'document' && file.document_id));
    const count = groups.length + plain.length;
    panel.hidden = !count;
    if (!count) return;
    const details = node('details', 'agent-files-disclosure');
    details.open = openState.files.has(chatId);
    details.addEventListener('toggle', () => { if (details.open) openState.files.add(chatId); else openState.files.delete(chatId); });
    const summary = node('summary', '', `Files in this chat (${count})`);
    details.append(summary);
    details.append(node('p', 'agent-files-note', 'Files stay available to this chat for 30 days. Relevant excerpts may be sent to your selected models.'));
    const list = node('div', 'agent-files-list');
    for (const group of groups) list.append(documentCard(chatId, group, { compact: true, scope: 'files' }));
    for (const file of plain) list.append(fileRow(chatId, file));
    details.append(list);
    panel.append(details);
  }

  // ---- loading --------------------------------------------------------------------
  async function load() {
    const chatId = chat, uid = owner, seq = ++generation;
    controller?.abort(); controller = new AbortController();
    try {
      const response = await request(`/agent/chats/${chatId}/files`, { signal: controller.signal });
      const body = await response.json();
      if (seq !== generation || chatId !== chat || uid !== window.auth?.currentUser?.uid) return;
      data = { files: Array.isArray(body.files) ? body.files : [] }; error = ''; revision++;
      clearTimeout(retryTimer); retryTimer = null;
    } catch (failure) {
      if (seq !== generation || failure.name === 'AbortError' || chatId !== chat) return;
      if (!data && !retried) {
        // One silent retry: a chat that never used files should not flash an error.
        retried = true;
        retryTimer = setTimeout(() => { retryTimer = null; if (chat === chatId) refresh(chatId, true); }, RETRY_MS);
        return;
      }
      error = failure.message || 'Please retry.'; revision++;
    }
    project();
  }
  function pump() {
    if (timer || inflight || !waiting) return;
    const wait = lastStart + WINDOW_MS - Date.now();
    if (wait > 0) { timer = setTimeout(() => { timer = null; pump(); }, wait); return; }
    const done = waiting.resolve; waiting = null;
    lastStart = Date.now();
    inflight = load().finally(() => { inflight = null; done(); pump(); });
  }
  function schedule() {
    if (!waiting) { let resolve; const promise = new Promise(r => { resolve = r; }); waiting = { promise, resolve }; }
    const promise = waiting.promise;
    pump();
    return promise;
  }
  function reset() {
    generation++; controller?.abort(); controller = null;
    clearTimeout(timer); timer = null; clearTimeout(retryTimer); retryTimer = null;
    waiting?.resolve(); waiting = null;
    lastStart = -Infinity; data = null; error = ''; revision++; confirmKey = ''; retried = false;
  }
  function knownEmpty(chatId) {
    // A chat created for the run in progress has no files yet; skip that GET.
    const context = App.runRegistry?.visible?.();
    // Nothing can exist before the server accepted the turn (resources only
    // follow `accepted`); its own uploads and documents arrive through forced
    // refreshes. Returning to the chat later in the run fetches normally.
    return Boolean(context && context.metadata?.chatId === chatId && !context.basis
      && App.runRegistry?.isExecuting?.(context.runId) && !context.metadata?.agentTurnId
      && !context.metadata?.fileIds?.length);
  }
  function refresh(chatId, force = false) {
    const uid = window.auth?.currentUser?.uid || '';
    if (!chatId || !uid || !App.agentChat?.isSelected?.()) {
      if (chat) reset();
      chat = ''; owner = ''; hideAll();
      return Promise.resolve();
    }
    if (chatId !== chat || uid !== owner) {
      reset(); chat = chatId; owner = uid;
      if (!force && knownEmpty(chatId)) { data = { files: [] }; project(); return Promise.resolve(); }
      project();
      return schedule();
    }
    if (force || (!data && !error && !inflight && !waiting && !retryTimer)) {
      project();
      return schedule();
    }
    project();
    return inflight || Promise.resolve();
  }

  // ---- upload -----------------------------------------------------------------------
  async function upload(context, headers, signal) {
    const chatId = context.metadata.chatId;
    const list = (context.attachments || []).map(file => ({ name: file.name, mime: file.mime || '', size: file.size || 0, state: 'waiting' }));
    const result = [];
    const update = () => { rendered = ''; if (chat === chatId) project(); };
    if (list.length) {
      uploads.set(chatId, list);
      for (const file of context.attachments) App.attachments?.markError?.(file, '');
      if (chat !== chatId) refresh(chatId); else update();
    }
    for (const [index, file] of (context.attachments || []).entries()) {
      if (!App.runRegistry.isAuthCurrent(context) || signal.aborted) { uploads.delete(chatId); update(); throw new DOMException('Stopped', 'AbortError'); }
      context.consensus.error = null;
      list[index].state = 'uploading'; update();
      let data;
      try {
        const response = await request(`/agent/chats/${chatId}/files`, {
          method: 'POST', signal, headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: file.name, data: file.data }) });
        data = await response.json();
      } catch (failure) {
        if (failure.name === 'AbortError' || signal.aborted) { uploads.delete(chatId); update(); throw failure; }
        uploads.delete(chatId);
        context.metadata.uploadFailed = true;
        // The file stays in the composer with the reason on its chip, so it can
        // be removed or replaced and the message sent again.
        App.attachments?.markError?.(file, failure.message);
        if (result.length) refresh(chatId, true); else update();
        throw new Error(`Couldn't upload ${file.name}. ${failure.message}`);
      }
      if (!App.runRegistry.isAuthCurrent(context) || signal.aborted) { uploads.delete(chatId); update(); throw new DOMException('Stopped', 'AbortError'); }
      list[index].state = 'done'; list[index].warnings = data.file?.warnings || [];
      result.push(data.file); update();
    }
    context.metadata.fileIds = result.map(file => file.id);
    context.attachmentMeta = result;
    context.attachments = []; // Bytes never belong in saved turns or bookmarks.
    if (result.length) {
      uploads.delete(chatId);
      window.clearPendingAttachments?.();
      await refresh(chatId, true);
    }
    return result;
  }

  window.addEventListener('consensio:auth-state', () => {
    reset(); chat = ''; owner = ''; uploads.clear(); openState.files.clear(); openState.versions.clear(); hideAll();
  });
  App.agentWorkspace = { refresh, upload, request, button, download };
})();
