// Private chat files and document versions. Everything belongs to the current
// authenticated chat and lives in memory only, never in localStorage.
//
// Every file belongs to the message or answer it came with; there is no
// chat-wide list under each answer:
// - Uploads sit as chips on the user message they were sent with
//   (attachments.js). A chip opens the stored file through openFile(), with
//   download and removal in the preview.
// - #agentAnswerResources (after the live answer) and one resources row per
//   archived Agent turn (renderTurnResources) show the documents created or
//   revised in that turn (one card per document_id), the files the agent
//   shared from its VM, mail attachments the agent fetched in it, per-file
//   upload progress, and a note when a file of the turn was only partly
//   readable.
// - The pictures the agent shared from its VM stand right under the answer
//   text, above its evidence row (Notes, Watch, Share): .agent-answer-pictures,
//   directly after the answer body. App.answerTail(body) is where that row
//   and the answer check line go (agent-review.js, watch.js, share-dialog.js).
//   Each loads when its place comes near the screen, as the server's preview
//   (?preview=1, at most 1600 px on a side, routers/agent_files.py); the
//   viewer and the download get the original (runtime audit 2026-10-30 P2:
//   an opened chat fetched every picture of every turn at once, up to 5 MB
//   each, as data: URLs).
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
  // Pictures the agent shared from its VM, loaded once per file as a data:
  // URL (the CSP's img-src allows data:, not blob:). fileId -> { url, load }
  const pictures = new Map();
  // How far below the screen a picture starts to load, so it is there when it scrolls in.
  const NEAR = '600px 0px';
  let watcher = null;
  // Shown as pictures; any other file is a row with its download.
  const PICTURE_MIMES = new Set(['image/png', 'image/jpeg', 'image/webp', 'image/gif']);
  const openState = { versions: new Set() };
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
  // Resource rows of archived turns in the thread history, keyed by turn.
  function historyRows() {
    return [...document.querySelectorAll('#threadHistory [data-agent-turn-resources]')];
  }

  async function request(path, options = {}) {
    const user = window.auth?.currentUser;
    if (!user) throw new Error('Log in to open files.');
    const token = await user.getIdToken();
    if (window.auth?.currentUser?.uid !== user.uid) throw new Error('Account changed.');
    const response = await fetch(path, { ...options, headers: { Authorization: `Bearer ${token}`, ...options.headers } });
    if (window.auth?.currentUser?.uid !== user.uid) throw new Error('Account changed.');
    if (!response.ok) throw App.httpError(response, await App.readJson(response).catch(() => ({})));
    return response;
  }
  // A file step failed: the server's sentence or ours, never the engine's.
  const fileError = (failure, context) => App.userError(failure, { context, fallback: context ? undefined : 'The file request failed. Try again.' });
  // Shared with agent-google.js: a plain inline button that reports failures.
  function button(label, action) {
    const control = node('button', 'settings-inline-btn', label); control.type = 'button';
    control.addEventListener('click', async () => {
      control.disabled = true;
      try { await action(); } catch (failure) { App.showPopup?.(fileError(failure)); }
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
    return `Expires ${App.format.date(time)}`;
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
      const menu = open.nextElementSibling;
      if (menu) App.popover?.closed(menu);
      menu?.setAttribute('hidden', '');
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
    // One of the app's popovers (App.popover): any other menu closes, and it
    // comes out of "…" and goes back (overlays.css).
    App.popover?.register(menu, { close: () => toggle(false) });
    const toggle = open => {
      closeMenus(trigger);
      if (open) App.popover?.opened(menu, { trigger });
      else App.popover?.closed(menu);
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
        App.showPopup?.(fileError(failure, 'delete'));
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
    box?.scrollIntoView?.({ block: 'center', behavior: App.scrollBehavior?.() || 'auto' });
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
      try { await download(chatId, file); } catch (failure) { App.showPopup?.(fileError(failure)); }
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
  function fileRow(chatId, file, scope) {
    const key = `${scope}:file:${file.id}`;
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
  function answerTail(body) {
    const slot = body?._pictures;
    return slot?.isConnected && slot.parentNode === body.parentNode && !slot.hidden ? slot : body;
  }
  // The answer's own place for its pictures, kept right after its text.
  function picturesSlot(body) {
    if (!body) return null;
    if (!body._pictures) { body._pictures = node('div', 'agent-answer-pictures'); body._pictures.hidden = true; }
    const slot = body._pictures;
    if (body.parentNode && body.nextElementSibling !== slot) body.after(slot);
    return slot;
  }
  // Drawn again only when its pictures (or a removal question) change, so a
  // picture never blinks while the answer around it updates.
  function fillPictures(body, chatId, shown, scope) {
    const slot = shown.length ? picturesSlot(body) : body?._pictures;
    if (!slot) return;
    const signature = JSON.stringify([chatId, scope, shown.map(file => [file.id, file.name, file.status]),
      shown.some(file => confirmKey === `${scope}:file:${file.id}`) ? confirmKey : '']);
    if (slot.dataset.signature === signature) return;
    slot.dataset.signature = signature;
    for (const old of slot.children) watcher?.unobserve(old);
    slot.replaceChildren(...shown.map(file => pictureCard(chatId, file, scope)));
    slot.hidden = !shown.length;
  }
  function readDataUrl(blob) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result || ''));
      reader.onerror = () => reject(new Error('Preview is not available in this browser.'));
      reader.readAsDataURL(blob);
    });
  }
  // Runs `load` once `element` comes near the screen; at once without an
  // IntersectionObserver.
  function whenNear(element, load) {
    if (typeof IntersectionObserver !== 'function') { load(); return; }
    watcher ||= new IntersectionObserver(entries => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        watcher.unobserve(entry.target);
        const run = entry.target._whenNear;
        delete entry.target._whenNear;
        run?.();
      }
    }, { rootMargin: NEAR });
    element._whenNear = load;
    watcher.observe(element);
  }
  function picture(chatId, file) {
    let entry = pictures.get(file.id);
    if (!entry) {
      entry = { url: '' };
      entry.load = request(`/agent/chats/${chatId}/files/${file.id}?preview=1`).then(response => response.blob()).then(readDataUrl)
        .then(url => { entry.url = url; return url; });
      // A failed load (chat changed, file removed) may be tried again later.
      entry.load.catch(() => { if (pictures.get(file.id) === entry) pictures.delete(file.id); });
      pictures.set(file.id, entry);
    }
    return entry;
  }
  // A picture the agent shared from its VM, under the answer at its width;
  // a click opens it in the file viewer (attachments.js) with download and
  // removal. Its name, download and removal sit in the caption.
  // A picture from the web (show_image, agent_web_images.py): what it shows,
  // as the agent said, and the page it came from, only an http(s) address.
  function webSource(file) {
    if (file.kind !== 'web_image') return null;
    const origin = file.origin || {};
    let page = '', host = '';
    try {
      const url = new URL(origin.page || origin.url);
      if (['http:', 'https:'].includes(url.protocol) && !url.username && !url.password) {
        page = url.href; host = url.hostname.replace(/^www\./, '');
      }
    } catch (_) { /* No source to link. */ }
    return { page, host, caption: typeof origin.caption === 'string' ? origin.caption.trim() : '' };
  }
  function pictureCard(chatId, file, scope) {
    const key = `${scope}:file:${file.id}`;
    const web = webSource(file);
    const name = web ? web.caption || web.host || file.name : file.name;
    const figure = node('figure', 'agent-vm-picture'); figure.dataset.filesKey = key;
    const open = node('button', 'agent-vm-picture-open'); open.type = 'button';
    open.setAttribute('aria-label', `Open ${name}`);
    const img = node('img'); img.alt = name; img.decoding = 'async';
    open.append(img);
    const loaded = pictures.get(file.id);
    if (loaded?.url) img.src = loaded.url;
    else {
      // Until it is drawn, the skeleton's field with its light passing, then
      // the picture fades in (an old chat opening; before, a blank white or
      // grey field stood there). One that cannot come says so in the field.
      // It loads once its place comes near the screen.
      figure.classList.add('is-loading');
      whenNear(figure, () => picture(chatId, file).load.then(url => {
        img.addEventListener('load', () => {
          figure.classList.remove('is-loading');
          if (img.animate && !window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) {
            img.animate([{ opacity: 0 }, { opacity: 1 }], { duration: App.motion?.ms?.('state') ?? 200,
              easing: App.motion?.ease?.('out') ?? 'ease-out' });
          }
        }, { once: true });
        img.src = url;
      }, () => {
        figure.classList.remove('is-loading'); figure.classList.add('is-failed');
        open.append(node('span', 'agent-vm-picture-failed', 'Picture couldn’t load'));
      }));
    }
    open.addEventListener('click', () => App.attachments?.openStored?.({ fileId: file.id, name: file.name, mime: file.mime, size: file.size }));
    const caption = node('figcaption', 'agent-vm-picture-caption');
    if (web) {
      // The agent's words and a site's name are content, not app text.
      if (web.caption) {
        const text = node('span', 'agent-file-name', web.caption);
        text.setAttribute('data-i18n-skip', '');
        caption.append(text);
      }
      if (web.page) {
        const source = node('a', 'agent-vm-picture-source', web.host);
        source.href = web.page; source.target = '_blank'; source.rel = 'noopener noreferrer nofollow';
        source.setAttribute('data-i18n-skip', '');
        caption.append(source);
      }
    } else caption.append(node('span', 'agent-file-name', file.name));
    caption.append(downloadChip(chatId, file, '', false),
      overflow(key, `More actions for ${name}`, [{ label: 'Remove…', danger: true, run: () => askToRemove(key) }]));
    figure.append(open, caption);
    if (confirmKey === key) {
      figure.append(confirmation(key, `Remove ${file.name}? The agent can no longer use it in this chat.`, 'Remove file', [file]));
    }
    return figure;
  }
  function partialNotice(files) {
    const box = node('div', 'agent-resource-notice');
    box.append(icon('warning'));
    const text = node('div', 'agent-resource-notice-text');
    text.append(node('strong', '', files.length === 1 ? `Parts of ${files[0].name} couldn’t be read`
      : `Parts of ${files.length} files couldn’t be read`));
    for (const file of files) text.append(node('span', '', files.length === 1 ? file.warnings.join(' ') : `${file.name}: ${file.warnings.join(' ')}`));
    box.append(text);
    return box;
  }

  function signature(turnInfo) {
    const origins = (data?.files || []).filter(file => file.origin?.message_id).map(mailOrigin);
    return JSON.stringify([chat, revision, turnInfo.id, turnInfo.fileIds, error, confirmKey, origins,
      historyRows().map(row => row.dataset.agentTurnResources)]);
  }
  function hideAll() {
    const resources = document.getElementById('agentAnswerResources');
    if (resources) { resources.replaceChildren(); resources.hidden = true; }
    fillPictures(document.getElementById('agentAnswerBody'), '', [], 'answer');
    for (const row of historyRows()) { row.replaceChildren(); row.hidden = true; fillPictures(row._answerBody, '', [], 'turn'); }
    rendered = '';
  }
  // What one turn produced: its documents (versions up to this turn), the
  // files the agent shared from its VM, the pictures it showed from the web
  // and the mail attachments it fetched.
  // Uploads are on the message.
  function turnResources(box, chatId, files, turnId, scope, live, body) {
    if (!turnId) { fillPictures(body, chatId, [], scope); return; }
    for (const group of groupDocuments(files)) {
      const mine = group.list.filter(version => version.turn === turnId);
      if (!mine.length) continue;
      const card = documentCard(chatId, group, { upTo: mine[0].number, turnId: live ? turnId : '', compact: !live, scope });
      if (card) box.append(card);
    }
    const shared = files.filter(file => ['vm_file', 'web_image'].includes(file.kind) && file.turn_id === turnId);
    const shown = shared.filter(file => PICTURE_MIMES.has(file.mime) && ['ready', 'partial'].includes(file.status));
    // Under the answer text when there is one, else with the other files.
    if (body) fillPictures(body, chatId, shown, scope);
    else if (shown.length) {
      const gallery = node('div', 'agent-answer-pictures');
      for (const file of shown) gallery.append(pictureCard(chatId, file, scope));
      box.append(gallery);
    }
    const rows = [...shared.filter(file => !shown.includes(file)),
      ...files.filter(file => file.kind === 'mail_attachment' && file.turn_id === turnId)];
    if (rows.length) {
      const list = node('div', 'agent-files-list');
      for (const file of rows) list.append(fileRow(chatId, file, scope));
      box.append(list);
    }
  }
  function fillHistoryRow(row) {
    row.replaceChildren();
    const turnId = row.dataset.agentTurnResources;
    if (chat && data) turnResources(row, chat, data.files || [], turnId, `turn:${turnId}`, false, row._answerBody);
    else fillPictures(row._answerBody, chat, [], `turn:${turnId}`);
    row.hidden = !row.childElementCount;
  }
  function project() {
    if (!chat) { hideAll(); return; }
    const resources = answerResources();
    const turnInfo = currentTurn();
    const key = signature(turnInfo);
    if (key === rendered && (!resources || resources.isConnected)) return;
    rendered = key; turn = turnInfo.id;
    const files = data?.files || [];
    const chatId = chat;
    if (resources) {
      resources.replaceChildren();
      const selected = new Set(turnInfo.fileIds || []);
      const readable = files.filter(file => selected.has(file.id) && partial(file));
      if (readable.length) resources.append(partialNotice(readable));
      if (error && selected.size) {
        // Only worth a line when this answer's own files are missing: one
        // quiet line, no surface and no technical reason, Retry as the text
        // link (UX audit B13; before, a grey box under every answer).
        const notice = node('p', 'agent-files-error');
        notice.append(node('span', '', 'Files couldn’t load'), ' · ');
        const retry = node('button', 'text-link', 'Retry'); retry.type = 'button';
        retry.addEventListener('click', () => refresh(chatId, true));
        notice.append(retry);
        resources.append(notice);
      }
      turnResources(resources, chatId, files, turnInfo.id, 'answer', true, document.getElementById('agentAnswerBody'));
      resources.hidden = !resources.childElementCount;
    }
    for (const row of historyRows()) fillHistoryRow(row);
  }

  // ---- loading --------------------------------------------------------------------
  async function load() {
    const chatId = chat, uid = owner, seq = ++generation;
    controller?.abort(); controller = new AbortController();
    try {
      const response = await request(`/agent/chats/${chatId}/files`, { signal: controller.signal });
      const body = await App.readJson(response);
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
      error = App.userError(failure, { fallback: 'Try again.' }); revision++;
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
    pictures.clear();
    watcher?.disconnect(); watcher = null;
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
    const files = context.attachments || [];
    // Their places over the message wait in the skeleton's light until each
    // file is stored (attachments.js markUploading, set when the message was
    // sent); since 2026-10-29 instead of a row per file under the message.
    const waiting = index => App.attachments?.markUploading?.(context.runId, files.slice(index));
    const stopped = () => App.attachments?.markUploading?.(context.runId, []);
    const result = [];
    if (files.length) {
      for (const file of files) App.attachments?.markError?.(file, '');
      if (chat !== chatId) refresh(chatId);
    }
    for (const [index, file] of files.entries()) {
      if (!App.runRegistry.isAuthCurrent(context) || signal.aborted) { stopped(); throw new DOMException('Stopped', 'AbortError'); }
      context.consensus.error = null;
      waiting(index);
      let data;
      try {
        const response = await request(`/agent/chats/${chatId}/files`, {
          method: 'POST', signal, headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: file.name, data: file.data,
            ...(file.origin?.source === 'google_drive' && file.origin.file_id ? { drive_file_id: file.origin.file_id } : {}) }) });
        data = await App.readJson(response);
      } catch (failure) {
        stopped();
        if (failure.name === 'AbortError' || signal.aborted) throw failure;
        context.metadata.uploadFailed = true;
        // The file stays in the composer with the reason on its chip, so it can
        // be removed or replaced and the message sent again.
        App.attachments?.markError?.(file, fileError(failure, 'upload'));
        if (result.length) refresh(chatId, true);
        // Offline or unreachable is the message's problem, not the file's:
        // the run says so and puts the message back (agent-chat.js failRun).
        if (['offline', 'unreachable', 'timeout'].includes(App.userError.kind(failure))) throw failure;
        throw new Error(`Couldn’t upload ${file.name}. ${fileError(failure, 'upload')}`);
      }
      if (!App.runRegistry.isAuthCurrent(context) || signal.aborted) { stopped(); throw new DOMException('Stopped', 'AbortError'); }
      result.push(data.file); waiting(index + 1);
    }
    context.metadata.fileIds = result.map(file => file.id);
    context.attachmentMeta = result;
    context.attachments = []; // Bytes never belong in saved turns or bookmarks.
    if (result.length) {
      window.clearPendingAttachments?.();
      await refresh(chatId, true);
    }
    return result;
  }

  // ---- files attached to a message --------------------------------------------------
  // The chip on a sent message knows only its file ID; the chat is the one
  // on screen. The server rechecks owner and chat on every request.
  function chatOnScreen() {
    if (chat) return chat;
    // A brand-new chat skips the list GET until its run reports files.
    const context = App.runRegistry?.visible?.();
    return context?.config?.executionMode === 'agent' ? context.metadata?.chatId || '' : '';
  }
  async function openFile(fileId) {
    const chatId = chatOnScreen();
    if (!chatId) throw new Error('Open this chat to preview the file.');
    const response = await request(`/agent/chats/${chatId}/files/${fileId}`);
    const blob = await response.blob();
    if (chatOnScreen() !== chatId) throw new Error('The chat changed. Open the file again.');
    return { blob, mime: blob.type || '' };
  }
  async function removeFile(fileId) {
    const chatId = chatOnScreen();
    if (!chatId) throw new Error('Open this chat to remove the file.');
    await request(`/agent/chats/${chatId}/files/${fileId}`, { method: 'DELETE' });
    if (chat === chatId) await refresh(chatId, true);
  }
  // Archived turns ask for their resources row while the thread renders; it
  // fills from the cached list now and again whenever the list changes.
  function renderTurnResources(row, turnId) {
    if (!row || !/^[a-f0-9]{32}$/.test(String(turnId || ''))) return;
    row.classList.add('agent-resources', 'agent-turn-resources');
    row.dataset.agentTurnResources = turnId;
    row.hidden = true;
    if (row.isConnected) fillHistoryRow(row);
    rendered = '';
  }

  window.addEventListener('consensio:auth-state', () => {
    reset(); chat = ''; owner = ''; openState.versions.clear(); hideAll();
  });
  App.agentWorkspace = { refresh, upload, request, button, download, openFile, removeFile, renderTurnResources };
  App.answerTail = answerTail;
})();
