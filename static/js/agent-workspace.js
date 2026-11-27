// Private chat files and document versions. Everything belongs to the current
// authenticated chat and lives in memory only, never in localStorage.
//
// Every file belongs to the message or answer it came with; there is no
// chat-wide list under each answer:
// - Uploads sit as chips on the user message they were sent with
//   (attachments.js). A chip opens the stored file through openFile(), with
//   download and removal in the preview.
// - The documents created or revised in a turn (one row per document_id),
//   the other files the agent shared from its VM and the mail attachments
//   it fetched belong to its answer: right under its text and pictures,
//   above the evidence row (.agent-answer-documents, documentsSlot). A
//   document's click opens its PDF in the preview beside the chat
//   (file-viewer.js), as a shared presentation, PDF, code or text file does:
//   each shows its first page as a thumbnail, its type and its
//   number of pages, and the word Preview, so it is plain that it opens.
// - #agentAnswerResources (after the live answer) shows a note when a file of
//   the turn was only partly readable or could not load; it and one resources
//   row per archived Agent turn (renderTurnResources) also hold the files of
//   a turn without an answer body.
// - The pictures the agent showed (vm_share_file, show_image) stand in the
//   answer text where it placed them (.md-picture, fillPictures), the others
//   right under the text, above its evidence row (Notes, Watch, Share):
//   .agent-answer-pictures, directly after the answer body.
//   App.answerTail(body) is where that row and the answer check line go
//   (agent-review.js, watch.js, share-dialog.js, agent-chat.js).
//   Each loads when its place comes near the screen, as the server's preview
//   (?preview=1, at most 1600 px on a side, routers/agent_files.py); the
//   viewer and the download get the original (otherwise an opened chat
//   fetches every picture of every turn at once, up to 5 MB each, as data:
//   URLs).
// - A page the agent shared (an HTML file that needs nothing from outside
//   itself, app/core/html_page.py) runs under the text, between the
//   pictures and the documents (.agent-answer-pages, pageCard): in a
//   sandboxed frame the server confines, in a place of fixed size.
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
    expand: 'M9 4H4v5M15 4h5v5M9 20H4v-5M15 20h5v-5',
  };
  let chat = '', owner = '', turn = '', data = null, error = '', generation = 0, controller = null;
  let lastStart = -Infinity, timer = null, retryTimer = null, inflight = null, waiting = null, rendered = '';
  let revision = 0, retried = false;
  // The demo's files (static/demo.js, demo()): fileId -> file with its
  // static addresses; the answer body that shows them.
  const demoFiles = new Map();
  let demoBody = null;
  // Pictures the agent shared from its VM, loaded once per file as a data:
  // URL (the CSP's img-src allows data:, not blob:), an SVG as its source.
  // fileId -> { url | svg, ready, load }
  const pictures = new Map();
  // How far below the screen a picture starts to load, so it is there when it scrolls in.
  const NEAR = '600px 0px';
  let watcher = null;
  // Shown as pictures; any other file is a row with its download. An SVG
  // keeps the type of a download (agent_vm_tools.share: served as an image,
  // a page that opened it would run it) and is drawn from its bytes.
  const PICTURE_MIMES = new Set(['image/png', 'image/jpeg', 'image/webp', 'image/gif']);
  const isPicture = file => PICTURE_MIMES.has(file.mime) || file.picture === 'svg';
  // An HTML file of the agent's that needs nothing from outside itself runs
  // under the answer as a page (agent_vm_tools.share, app/core/html_page.py).
  const isPage = file => file.page === 'html' && file.kind === 'vm_file';
  // A page's place follows the height the page says its content has
  // (pageCard). While it settles, after it loaded or its width changed, it
  // may say so a few times (a font, a chart drawn late). A page laid out
  // against its frame's height answers every height with another: past
  // PAGE_SETTLE_MOVES it keeps the place every page starts in. Each height
  // it takes keeps it settling for PAGE_ANSWER_MS more, so such a page is
  // found out on a slow device too, where its answers take their time.
  const PAGE_SETTLE_MS = 2000, PAGE_SETTLE_MOVES = 5, PAGE_ANSWER_MS = 1000;
  // The heights pages arrived at in this browser, { fileId: [width, height] },
  // 0 for one that keeps the starting place: a chat opened again gives a
  // page its place before it loads, so nothing under it moves when it does.
  // Only the height a page arrives at is kept, not one the user gave it by
  // using it: it loads as it was shared. pageHeightsNow: the same for this
  // visit, where a temporary chat's stay (it leaves nothing in the browser).
  const PAGE_HEIGHTS_KEY = 'agentPageHeights', PAGE_HEIGHTS_KEPT = 60, PAGE_WIDTH_SLACK = 24;
  const pageHeightsNow = new Map();
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
      // A page without the template's hook gets one where the template puts
      // it (before the error line), so the answer's evidence and copy rows
      // keep their own stable anchors on body.
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
    const blob = demoFiles.has(file.id) ? await demoFetch(file.demo.file)
      : await (await request(`/agent/chats/${chatId}/files/${file.id}`)).blob();
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
  function available(file) { return ['ready', 'partial'].includes(file.status) && expiry(file) !== 'Expired'; }

  // ---- previews (file-viewer.js) ----------------------------------------------
  // The number of pages a card learned from its thumbnail, so a card drawn
  // again says it at once.
  const pageCounts = new Map();
  function previewItem(chatId, file, extra = {}) {
    return { key: file.id, name: file.name, title: extra.title, mime: file.mime, preview: file.preview, kind: file.kind,
      family: extra.family, load: () => openPreview(file.id),
      downloads: extra.downloads || [{ label: extension(file), run: () => download(chatId, file) }],
      remove: extra.remove === false || demoFiles.has(file.id) ? null : () => removeFile(file.id) };
  }
  // A card's mark becomes its first page; under its name its type and pages.
  function previewMark(mark, meta, item, extra = []) {
    const viewer = App.fileViewer;
    if (!viewer) return;
    const type = viewer.describe(item);
    const say = () => {
      const pages = pageCounts.get(item.key);
      const unit = type.family === 'presentation' || type.family === 'spreadsheet' ? type.family : 'page';
      // Each part in the page's language (countText translates with the number).
      meta.textContent = [App.t(type.label), pages ? viewer.countText(unit, pages) : '', ...extra.map(part => App.t(part))]
        .filter(Boolean).join(' · ');
      meta.hidden = false;
    };
    say();
    viewer.thumbnail(mark, item, info => {
      // A landscape PDF is a deck: its pages are slides.
      if (type.family === 'pdf' && info.landscape) type.family = 'presentation';
      pageCounts.set(item.key, info.pages);
      say();
    });
  }
  function previewHint() {
    const hint = node('span', 'agent-file-preview-hint', 'Preview');
    hint.setAttribute('aria-hidden', 'true');
    return hint;
  }
  async function openPreview(fileId) {
    const shown = demoFiles.get(fileId);
    if (shown) {
      const blob = await demoFetch(shown.demo.preview || shown.demo.file);
      return { blob, mime: blob.type || '' };
    }
    const chatId = chatOnScreen();
    if (!chatId) throw new Error('Open this chat to preview the file.');
    const response = await request(`/agent/chats/${chatId}/files/${fileId}?preview=1`);
    const blob = await response.blob();
    if (chatOnScreen() !== chatId) throw new Error('The chat changed. Open the file again.');
    return { blob, mime: response.headers.get('Content-Type') || blob.type || '' };
  }

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
    // Size and expiry are details for the pointer, not for the row. Part by
    // part (docs/i18n.md).
    control.title = [App.t(`Download ${file.name}`), size(file.size), App.t(expiry(file))].filter(Boolean).join(' · ');
    control.append(icon('download'));
    if (withLabel) control.append(node('span', 'agent-files-chip-type', extension(file)));
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
  // A document is one quiet row in the flow of its answer (no box, no green
  // badge, no hint): its mark, its title and, on the right, the formats to
  // download. Under the title only what changes a decision: a later
  // version's number, or that it expired; with a PDF to preview, its type
  // and pages before them (previewMark).
  function documentCard(chatId, group, { upTo = Infinity, scope }) {
    const versions = group.list.filter(version => version.number <= upTo);
    const current = versions[0];
    if (!current) return null;
    const key = `${scope}:doc:${group.id}:${current.number}`;
    const card = node('article', 'agent-doc-card');
    card.dataset.filesKey = key; card.dataset.documentId = group.id;
    card.setAttribute('aria-label', `${group.title}, version ${current.number}`);
    const head = node('div', 'agent-doc-head');
    // Its PDF opens in the file viewer (file-viewer.js), as an upload does;
    // without one ready, the row only downloads.
    const pdf = current.files.find(file => (file.mime === 'application/pdf' || /\.pdf$/i.test(file.name || ''))
      && available(file));
    const main = node(pdf ? 'button' : 'div', 'agent-doc-main');
    const mark = node('span', 'agent-doc-mark agent-file-thumb'); mark.append(icon('document'));
    const titles = node('span', 'agent-doc-titles');
    const title = node('span', 'agent-doc-title');
    title.append(node('span', '', group.title));
    title.title = group.title;
    titles.append(title);
    const expired = expiry(current.files[0] || {}) === 'Expired';
    const note = [current.number > 1 ? `Version ${current.number}` : '', expired ? 'Expired' : ''].filter(Boolean);
    const meta = node('span', 'agent-doc-meta', note.map(part => App.t(part)).join(' · '));
    meta.hidden = !note.length;
    titles.append(meta);
    main.append(mark, titles);
    if (pdf) {
      main.type = 'button';
      main.title = App.t('Preview {title}', { title: group.title });
      // In the preview: the title, every format to download, no removal (a
      // version goes from this row's ⋯).
      const downloads = current.files.filter(available).map(file => ({ label: extension(file), run: () => download(chatId, file) }));
      const item = previewItem(chatId, pdf, { title: group.title, family: 'document', downloads, remove: false });
      previewMark(mark, meta, item, note);
      main.append(previewHint());
      main.addEventListener('click', () => App.fileViewer?.open({ ...item, trigger: main }));
    }
    const chips = node('div', 'agent-doc-downloads');
    for (const file of current.files) chips.append(downloadChip(chatId, file, `, version ${current.number}`, true));
    head.append(main, chips);
    const removeLabel = `Remove version ${current.number}…`;
    head.append(overflow(key, `More actions for ${group.title}, version ${current.number}`, [{ label: removeLabel, danger: true,
      run: () => askToRemove(key) }]));
    card.append(head);
    if (confirmKey === key) {
      card.append(confirmation(key, `Remove ${group.title} version ${current.number} (${current.files.map(extension).join(' and ')})? The agent can no longer use or revise it.`,
        'Remove version', current.files));
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
    // A file the preview can show (file-viewer.js): mark, name and the
    // word Preview are one button, as a document's row.
    const item = available(file) && App.fileViewer?.previews(file) ? previewItem(chatId, file) : null;
    const typeMeta = item ? node('span', 'agent-file-kind') : null;
    if (typeMeta) { main.append(typeMeta); type.classList.add('agent-file-thumb'); previewMark(type, typeMeta, item); }
    const origin = mailOrigin(file);
    // As the document row: the name says the type; size and expiry are the
    // download's tooltip. Under the name only a state worth reading.
    const status = file.status === 'processing' ? 'Processing…' : file.status === 'deleting' ? 'Removing…'
      : expiry(file) === 'Expired' ? 'Expired' : '';
    const meta = node('span', 'agent-file-meta', status);
    if (partial(file)) {
      const badge = node('span', 'agent-files-badge is-warning');
      badge.append(icon('warning'), node('span', '', 'Partly read'));
      meta.prepend(badge);
    }
    if (meta.childNodes.length) main.append(meta);
    if (origin) main.append(node('span', 'agent-file-origin', origin));
    for (const warning of file.warnings || []) main.append(node('span', 'agent-file-warning', warning));
    const actions = node('div', 'agent-file-actions');
    actions.append(downloadChip(chatId, file, '', false));
    if (!demoFiles.has(file.id)) {
      actions.append(overflow(key, `More actions for ${file.name}`, [{ label: 'Remove…', danger: true,
        run: () => askToRemove(key) }]));
    }
    if (item) {
      const open = node('button', 'agent-file-open');
      open.type = 'button';
      open.title = App.t('Preview {name}', { name: file.name });
      open.append(type, main, previewHint());
      open.addEventListener('click', () => App.fileViewer?.open({ ...item, trigger: open }));
      row.classList.add('can-preview');
      row.append(open, actions);
    } else row.append(type, main, actions);
    const wrap = node('div', 'agent-file-item'); wrap.append(row);
    if (confirmKey === key) {
      wrap.append(confirmation(key, `Remove ${file.name}? The agent can no longer use it in this chat.`, 'Remove file', [file]));
    }
    return wrap;
  }
  function answerTail(body) {
    for (const slot of [body?._documents, body?._pages, body?._pictures]) {
      if (slot?.isConnected && slot.parentNode === body.parentNode && !slot.hidden) return slot;
    }
    return body;
  }
  // The answer's documents, right after its pictures' and its pages' places
  // (which stand right after the text), so the evidence row follows them.
  function documentsSlot(body) {
    const pictures = picturesSlot(body);
    if (!pictures) return null;
    if (!body._documents) {
      body._documents = node('div', 'agent-resources agent-answer-documents'); body._documents.hidden = true;
    }
    const slot = body._documents;
    const before = body._pages?.parentNode && body._pages.parentNode === pictures.parentNode ? body._pages : pictures;
    if (before.parentNode && before.nextElementSibling !== slot) before.after(slot);
    return slot;
  }
  // The answer's pages, between its pictures and its documents. Put there
  // once: a frame taken out of the page and put back loads again.
  function pagesSlot(body) {
    const pictures = picturesSlot(body);
    if (!pictures) return null;
    if (!body._pages) { body._pages = node('div', 'agent-answer-pages'); body._pages.hidden = true; }
    if (pictures.parentNode && body._pages.parentNode !== pictures.parentNode) pictures.after(body._pages);
    return body._pages;
  }
  // Each page keeps its figure for as long as the answer shows it: only one
  // that is new is put in, only one that is gone is taken out, and a
  // removal question opens inside the figure (pageCard sync).
  function fillPages(body, chatId, pages, scope) {
    if (!body || (!pages.length && !body._pageCards)) return;
    const cards = body._pageCards ||= new Map();
    for (const [id, card] of cards) {
      if (pages.some(file => file.id === id && file.name === card.name) && card.chatId === chatId && card.scope === scope) continue;
      watcher?.unobserve(card.figure); card.figure.remove(); cards.delete(id);
    }
    const slot = pages.length ? pagesSlot(body) : body._pages;
    if (!slot) return;
    pages.forEach((file, index) => {
      let card = cards.get(file.id);
      if (!card) { card = pageCard(chatId, file, scope); cards.set(file.id, card); }
      card.sync();
      if (card.figure.parentNode !== slot) slot.insertBefore(card.figure, slot.children[index] || null);
    });
    slot.hidden = !pages.length;
  }
  function fillDocuments(body, cards) {
    if (!body) return;
    if (!cards.length && !body._documents) return;
    const slot = documentsSlot(body);
    if (!slot) return;
    slot.replaceChildren(...cards);
    slot.hidden = !cards.length;
  }
  // The answer's own place for the pictures it does not place, kept right after its text.
  function picturesSlot(body) {
    if (!body) return null;
    if (!body._pictures) { body._pictures = node('div', 'agent-answer-pictures'); body._pictures.hidden = true; }
    const slot = body._pictures;
    if (body.parentNode && body.nextElementSibling !== slot) body.after(slot);
    return slot;
  }
  // Pictures in the text: the agent writes ![what it shows](picture:p2)
  // where one belongs, a place in the rendered answer (markdown-stream.js .md-picture)
  // that takes the turn's picture with that origin.ref. The others stand
  // under the text, once the answer is written: while it streams, a picture
  // waits for its place instead of jumping from under the text into it.
  // Every write of the answer (stream, full render, review marks) may bring
  // new places; the body's observer fills them before the frame is drawn,
  // always with the same figure, so a picture never loads or blinks again.
  function fillPictures(body, chatId, shown, scope, hold = false) {
    if (!body || (!shown.length && !body._pictureState)) return;
    body._pictureState = { chatId, shown, scope, hold };
    if (!body._pictureWatch && typeof MutationObserver === 'function') {
      body._pictureWatch = new MutationObserver(() => placePictures(body));
      body._pictureWatch.observe(body, { childList: true, subtree: true });
    }
    placePictures(body);
  }
  function placePictures(body) {
    const { chatId, shown, scope, hold } = body._pictureState;
    const figures = body._figures ||= new Map();
    // Each figure is drawn again only when its picture or a removal question about it changes.
    for (const file of shown) {
      const key = `${scope}:file:${file.id}`;
      const signature = JSON.stringify([chatId, scope, file.name, file.status, file.origin?.caption || '', confirmKey === key]);
      const old = figures.get(file.id);
      if (old?.signature === signature) continue;
      const figure = pictureCard(chatId, file, scope);
      if (old) { watcher?.unobserve(old.figure); if (old.figure.parentNode) old.figure.replaceWith(figure); }
      figures.set(file.id, { signature, figure });
    }
    const ids = new Set(shown.map(file => file.id));
    for (const [id, old] of figures) {
      if (!ids.has(id)) { watcher?.unobserve(old.figure); old.figure.remove(); figures.delete(id); }
    }
    // A picture takes the first place that names it; a place that names none stays empty.
    const byRef = new Map(shown.filter(file => file.origin?.ref).map(file => [file.origin.ref, file]));
    const placed = new Set();
    for (const place of body.querySelectorAll('.md-picture')) {
      const file = byRef.get(place.dataset.picture);
      const figure = file && !placed.has(file.id) ? figures.get(file.id).figure : null;
      if (figure) placed.add(file.id);
      if (figure ? place.firstChild !== figure || place.childNodes.length !== 1 : place.firstChild) {
        // One the text reaches while it is written fades in like the words
        // around it, instead of standing there whole from one frame to the next.
        const arriving = hold && figure && !figure.isConnected;
        place.replaceChildren(...(figure ? [figure] : []));
        if (arriving) fadeIn(figure);
      }
    }
    markGalleries(body);
    const rest = hold ? [] : shown.filter(file => !placed.has(file.id)).map(file => figures.get(file.id).figure);
    for (const figure of rest) markTile(figure, 0, 0);
    const slot = rest.length ? picturesSlot(body) : body._pictures;
    if (!slot) return;
    if (rest.length !== slot.children.length || rest.some((figure, index) => slot.children[index] !== figure)) {
      slot.replaceChildren(...rest);
    }
    slot.hidden = !rest.length;
  }
  // Pictures the agent wrote on one line are a collage to click through: one
  // large, the next two beside it (two alone side by side), "+N" on the third
  // for the rest, which the viewer pages through. The marks
  // sit on the figures, which are ours: a morph of the streamed text keeps
  // them (agent-workspace.css lays the line out by them with :has).
  const GALLERY_TILES = 3;
  function markGalleries(body) {
    const marked = new Set();
    for (const line of body.querySelectorAll('.md-picture-line')) {
      const tiles = [...line.querySelectorAll(':scope > .md-picture > .agent-vm-picture')];
      if (tiles.length < 2) continue;
      tiles.forEach((figure, index) => { markTile(figure, tiles.length, index); marked.add(figure); });
    }
    // A picture that left its collage (the line became a paragraph, lost a
    // picture) is a picture of its own again.
    for (const figure of body.querySelectorAll('.md-picture > .agent-vm-picture')) {
      if (!marked.has(figure)) markTile(figure, 0, 0);
    }
  }
  function fadeIn(element) {
    if (!element.animate || window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return;
    element.animate([{ opacity: 0 }, { opacity: 1 }], { duration: App.motion?.ms?.('state') ?? 200,
      easing: App.motion?.ease?.('out') ?? 'ease-out' });
  }
  function markTile(figure, count, index) {
    const marks = {
      gallerySize: count ? String(Math.min(count, GALLERY_TILES)) : '',
      galleryLead: count > 2 && index === 0 ? '' : null,
      galleryMore: count > GALLERY_TILES && index === GALLERY_TILES - 1 ? `+${count - GALLERY_TILES}` : null,
      galleryHidden: count && index >= GALLERY_TILES ? '' : null,
    };
    for (const [name, value] of Object.entries(marks)) {
      if (value === null || (name === 'gallerySize' && !value)) delete figure.dataset[name];
      else if (figure.dataset[name] !== value) figure.dataset[name] = value;
    }
  }
  function readBlob(blob, how) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result || ''));
      reader.onerror = () => reject(new Error('Preview is not available in this browser.'));
      reader[how](blob);
    });
  }
  const readDataUrl = blob => readBlob(blob, 'readAsDataURL');
  // A picture's bytes in its <img>: a photo as it came, an SVG drawn as an
  // image for the theme on screen (diagram-render.js paint, which draws it
  // again when the theme changes). Rejects when there is nothing to show.
  function showPicture(img, entry) {
    if (entry.svg === undefined) { img.src = entry.url; return Promise.resolve(); }
    const drawings = window.ConsensusDiagram;
    return drawings?.paint ? drawings.paint(img, entry.svg) : Promise.reject(new Error('No drawing'));
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
      entry = { url: '', ready: false };
      const blob = demoFiles.has(file.id) ? demoFetch(file.demo.preview || file.demo.file)
        : request(`/agent/chats/${chatId}/files/${file.id}?preview=1`).then(response => response.blob());
      entry.load = (file.picture === 'svg'
        ? blob.then(bytes => readBlob(bytes, 'readAsText')).then(svg => { entry.svg = svg; })
        : blob.then(readDataUrl).then(url => { entry.url = url; })).then(() => { entry.ready = true; return entry; });
      // A failed load (chat changed, file removed) may be tried again later.
      entry.load.catch(() => { if (pictures.get(file.id) === entry) pictures.delete(file.id); });
      pictures.set(file.id, entry);
    }
    return entry;
  }
  // A picture the agent shared from its VM, in or under the answer at its width;
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
    // In the answer's text the page's words are its own (data-i18n-skip); this bar is ours (i18n.js).
    figure.setAttribute('data-i18n-ui', '');
    // Its own shape when the store knows it (agent_files.picture_size, for an
    // SVG app/core/svg.py): the
    // field it shows until it arrives is the picture's, so nothing moves
    // when it comes. Files without a size keep the 16:10 field.
    const width = Number(file.width), height = Number(file.height);
    if (Number.isInteger(width) && Number.isInteger(height) && width > 0 && height > 0) {
      figure.classList.add('has-size');
      figure.style.setProperty('--picture-width', String(width));
      figure.style.setProperty('--picture-height', String(height));
    }
    const open = node('button', 'agent-vm-picture-open'); open.type = 'button';
    open.setAttribute('aria-label', `Open ${name}`);
    const img = node('img'); img.alt = name; img.decoding = 'async';
    open.append(img);
    const failed = () => {
      figure.classList.remove('is-loading'); figure.classList.add('is-failed');
      open.append(node('span', 'agent-vm-picture-failed', 'Picture couldn’t load'));
    };
    const loaded = pictures.get(file.id);
    if (loaded?.ready) showPicture(img, loaded).catch(failed);
    else {
      // Until it is drawn, the skeleton's field with its light passing, then
      // the picture fades in. One that cannot come says so in the field.
      // It loads once its place comes near the screen.
      figure.classList.add('is-loading');
      whenNear(figure, () => picture(chatId, file).load.then(entry => {
        img.addEventListener('load', () => {
          figure.classList.remove('is-loading');
          fadeIn(img);
        }, { once: true });
        return showPicture(img, entry);
      }).catch(failed));
    }
    // The viewer pages through the pictures of the same line or of the
    // pictures under the answer, as through a gallery (attachments.js).
    const own = !demoFiles.has(file.id);
    figure._picture = { fileId: file.id, name: file.name, mime: file.mime, size: file.size, title: name,
      page: web?.page || '', host: web?.host || '', ...(file.picture === 'svg' ? { picture: 'svg' } : {}),
      ...(own ? {} : { removable: false }) };
    open.addEventListener('click', () => {
      const set = figure.closest('.md-picture-line, .agent-answer-pictures');
      const figures = set ? [...set.querySelectorAll('.agent-vm-picture')].filter(item => item._picture) : [figure];
      App.attachments?.openStored?.({ ...figure._picture, gallery: figures.map(item => item._picture),
        index: Math.max(0, figures.indexOf(figure)) });
    });
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
    caption.append(downloadChip(chatId, file, '', false));
    if (own) caption.append(overflow(key, `More actions for ${name}`, [{ label: 'Remove…', danger: true, run: () => askToRemove(key) }]));
    figure.append(open, caption);
    if (confirmKey === key) {
      figure.append(confirmation(key, `Remove ${file.name}? The agent can no longer use it in this chat.`, 'Remove file', [file]));
    }
    return figure;
  }
  // The address a frame loads a shared page from, and how long a load under
  // it finds the page (routers/agent_files.py open_page). A frame cannot
  // send the sign-in, so the address is asked for, signed in, each time a
  // page is to load; only this app's own page route ever goes into a frame.
  async function pageAddress(fileId, chatId = chatOnScreen()) {
    if (!chatId) throw new Error('Open this chat to see the page.');
    const response = await request(`/agent/chats/${chatId}/files/${fileId}/page`, { method: 'POST' });
    const body = await App.readJson(response);
    const url = String(body?.url || '');
    if (!/^\/agent\/pages\/[A-Za-z0-9_=-]+$/.test(url)) throw new Error('The page couldn’t load.');
    return { url, until: Date.now() + Math.max(0, (Number(body.expires_in) || 0) - 10) * 1000 };
  }
  // A frame for a page of the agent's: its script runs, in an origin of its
  // own that reaches nothing of the app; the page's answer sets the same and
  // more (app/core/html_page.py).
  function pageFrame(name, className) {
    const frame = node('iframe', className);
    frame.setAttribute('sandbox', 'allow-scripts');
    frame.setAttribute('referrerpolicy', 'no-referrer');
    // Its name for a screen reader: the file's, the user's word and not the
    // app's (i18n.js). As a label, not a title: a title is drawn as a
    // tooltip (tooltip.js), which would lie over the page while it is used.
    frame.setAttribute('data-i18n-skip', '');
    frame.setAttribute('aria-label', name);
    return frame;
  }
  function pageHeights() {
    try {
      const kept = JSON.parse(localStorage.getItem(PAGE_HEIGHTS_KEY) || '{}');
      return kept && typeof kept === 'object' && !Array.isArray(kept) ? kept : {};
    } catch { return {}; }
  }
  function keepPageHeight(chatId, id, width, height) {
    const entry = [Math.round(width), Math.round(height)];
    pageHeightsNow.set(id, entry);
    if (App.temporaryChat?.token?.(chatId)) return;
    try {
      const kept = pageHeights();
      delete kept[id];
      kept[id] = entry;
      const ids = Object.keys(kept);
      for (const old of ids.slice(0, Math.max(0, ids.length - PAGE_HEIGHTS_KEPT))) delete kept[old];
      localStorage.setItem(PAGE_HEIGHTS_KEY, JSON.stringify(kept));
    } catch { /* No storage: the page finds its height again on every visit. */ }
  }
  // A page says how tall its content is (app/core/html_page.py _FIT). The
  // word of a page is not trusted: only the document inside one of this
  // module's page frames is heard, only for a number, and what the number
  // may do is the card's to decide (pageCard fit).
  window.addEventListener('message', event => {
    const height = event.data?.consensPage?.height;
    if (typeof height !== 'number' || !Number.isFinite(height) || !(height > 0)) return;
    let around = null;
    try { around = event.source?.parent; } catch { return; }
    if (!around || around === window) return;
    for (const frame of document.querySelectorAll('iframe.agent-page-frame')) {
      if (frame.contentWindow === around) { frame._fitPage?.(height); return; }
    }
  });
  // The focus going into a page: the window loses it to the page's frame.
  window.addEventListener('blur', () => setTimeout(() => {
    const frame = document.activeElement;
    if (frame?.classList?.contains('agent-page-frame')) frame._pageArrived?.();
  }, 0));
  // A page the agent shared, running under the answer. Its place has a size
  // before anything loads (agent-workspace.css) and then the height the page
  // says its content has, within the stylesheet's bounds: the page stands in
  // the answer whole, and only one longer than the bound scrolls inside. It
  // loads once it comes near the screen; its name, a larger view (the
  // viewer's stage, attachments.js), its download and its removal sit in the
  // line under it. { figure, sync }: sync opens or closes the removal
  // question without touching the frame.
  function pageCard(chatId, file, scope) {
    const key = `${scope}:file:${file.id}`;
    const figure = node('figure', 'agent-page'); figure.dataset.filesKey = key;
    figure.setAttribute('data-i18n-ui', '');
    const stage = node('div', 'agent-page-stage is-loading');
    const frame = pageFrame(file.name, 'agent-page-frame');
    stage.append(frame);
    let until = 0, loads = 0;
    // fitted: the height the place has from the page, 0 for the starting
    // place. bound: the page keeps the starting place. later: a height the
    // page said while it was not its turn to move anything.
    let fitted = 0, bound = false, moves = 0, settled = Infinity, later = 0, width = 0;
    const place = height => {
      fitted = height;
      stage.classList.toggle('is-fitted', height > 0);
      if (height) stage.style.setProperty('--agent-page-height', `${height}px`);
      else stage.style.removeProperty('--agent-page-height');
    };
    // What is under the page moves with its height. That is the page
    // arriving while it settles, and the user's own doing while they are in
    // it (the pointer over it, or the focus inside): a tab that shows more, a
    // slider that adds rows. A page that changes by itself later waits until
    // the user comes to it, so a chat being read does not move.
    const withUser = () => frame.matches(':hover') || document.activeElement === frame;
    const fit = (height, here = withUser()) => {
      if (bound) return;
      const next = Math.round(height);
      later = 0;
      if (Math.abs(next - fitted) < 2) return;
      if (Date.now() < settled) {
        if (++moves > PAGE_SETTLE_MOVES) {
          bound = true; place(0); keepPageHeight(chatId, file.id, stage.clientWidth, 0);
          return;
        }
        keepPageHeight(chatId, file.id, stage.clientWidth, next);
        if (settled !== Infinity) settled = Math.max(settled, Date.now() + PAGE_ANSWER_MS);
      } else if (!here) { later = next; return; }
      place(next);
    };
    frame._fitPage = height => fit(height);
    frame._pageArrived = () => { if (later) fit(later, true); };
    frame.addEventListener('pointerenter', frame._pageArrived);
    // Its place gets a width when it enters the chat: there the page stands
    // at the height this browser last gave it at that width, before the
    // first frame is drawn. A width that changes later (the window, the
    // sidebar, a phone turned) lets the page settle anew.
    if (typeof ResizeObserver === 'function') {
      new ResizeObserver(() => {
        const now = stage.clientWidth;
        if (!now || Math.abs(now - width) < 2) return;
        const first = !width;
        width = now;
        if (!first) { if (settled !== Infinity) { settled = Date.now() + PAGE_SETTLE_MS; moves = 0; } return; }
        const known = pageHeightsNow.get(file.id) || pageHeights()[file.id];
        if (fitted || !Array.isArray(known) || !(Math.abs(known[0] - now) <= PAGE_WIDTH_SLACK)) return;
        if (known[1] > 0) place(Math.round(known[1])); else if (known[1] === 0) bound = true;
      }).observe(stage);
    }
    // One that cannot come says so in its place, with the way to try again.
    const failed = () => {
      stage.classList.remove('is-loading');
      if (stage.classList.contains('is-failed')) return;
      stage.classList.add('is-failed');
      const note = node('p', 'agent-page-failed');
      const retry = node('button', 'text-link', 'Retry'); retry.type = 'button';
      retry.addEventListener('click', () => reload());
      note.append(node('span', '', 'Page couldn’t load'), ' · ', retry);
      stage.append(note);
    };
    const load = () => pageAddress(file.id, chatId).then(address => {
      until = address.until;
      frame.src = address.url;
    }).catch(failed);
    // The page anew, as it was shared: after a failure, after the user
    // changed what it shows, or when it got stuck ("Reload page" in its menu).
    const reload = () => {
      stage.querySelector('.agent-page-failed')?.remove();
      stage.classList.remove('is-failed'); stage.classList.add('is-loading');
      loads = 0; bound = false; moves = 0; settled = Infinity;
      load();
    };
    frame.addEventListener('load', () => {
      // An empty frame reports a load of its own when it enters the page.
      if (!frame.getAttribute('src')) return;
      stage.classList.remove('is-loading');
      if (settled === Infinity) settled = Date.now() + PAGE_SETTLE_MS;
      // The frame loads again when its answer moves in the page (the live
      // answer joining the history). Past its address's time that load
      // found nothing: it gets a new address.
      if (loads++ && Date.now() > until) load();
    });
    whenNear(figure, load);
    const caption = node('figcaption', 'agent-vm-picture-caption');
    const name = node('span', 'agent-file-name', file.name);
    name.setAttribute('data-i18n-skip', '');
    caption.append(name);
    const open = node('button', 'agent-files-icon-btn agent-page-open'); open.type = 'button';
    open.setAttribute('aria-label', `Open ${file.name} larger`); open.title = 'Open larger';
    open.append(icon('expand'));
    open.addEventListener('click', () => App.attachments?.openStored?.({ fileId: file.id, name: file.name,
      mime: file.mime, size: file.size, title: file.name, htmlPage: true }));
    caption.append(open, downloadChip(chatId, file, '', false),
      overflow(key, `More actions for ${file.name}`, [{ label: 'Reload page', run: reload },
        { label: 'Remove…', danger: true, run: () => askToRemove(key) }]));
    figure.append(stage, caption);
    const sync = () => {
      const box = [...figure.children].find(child => child.classList.contains('agent-files-confirm'));
      if (confirmKey !== key) box?.remove();
      else if (!box) {
        figure.append(confirmation(key, `Remove ${file.name}? The agent can no longer use it in this chat.`, 'Remove file', [file]));
      }
    };
    return { figure, sync, chatId, scope, name: file.name };
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
    return JSON.stringify([chat, revision, turnInfo.id, turnInfo.fileIds, error, confirmKey, origins, answerWriting(),
      historyRows().map(row => row.dataset.agentTurnResources)]);
  }
  // The live answer is still being written: its Agent run executes.
  function answerWriting() {
    const context = App.runRegistry?.visible?.();
    return Boolean(context?.config?.executionMode === 'agent' && App.runRegistry?.isExecuting?.(context.runId));
  }
  function hideAll() {
    const resources = document.getElementById('agentAnswerResources');
    if (resources) { resources.replaceChildren(); resources.hidden = true; }
    // The demo's files stay with its answer until the demo lets them go.
    const body = document.getElementById('agentAnswerBody');
    if (body !== demoBody) { fillPictures(body, '', [], 'answer'); fillPages(body, '', [], 'answer'); fillDocuments(body, []); }
    for (const row of historyRows()) {
      row.replaceChildren(); row.hidden = true; fillPictures(row._answerBody, '', [], 'turn');
      fillPages(row._answerBody, '', [], 'turn'); fillDocuments(row._answerBody, []);
    }
    rendered = '';
  }
  // What one turn produced: its documents (versions up to this turn), the
  // files the agent shared from its VM, the pictures it showed from the web
  // and the mail attachments it fetched. All of it belongs to the answer:
  // under its text, above its evidence row. Uploads are on the message.
  function turnResources(box, chatId, files, turnId, scope, live, body) {
    if (!turnId) { fillPictures(body, chatId, [], scope); fillPages(body, chatId, [], scope); fillDocuments(body, []); return; }
    const own = [];
    for (const group of groupDocuments(files)) {
      const mine = group.list.filter(version => version.turn === turnId);
      if (!mine.length) continue;
      const card = documentCard(chatId, group, { upTo: mine[0].number, scope });
      if (card) own.push(card);
    }
    const shared = files.filter(file => ['vm_file', 'web_image'].includes(file.kind) && file.turn_id === turnId);
    const shown = shared.filter(file => isPicture(file) && ['ready', 'partial'].includes(file.status));
    // In and under the answer text when there is one, else with the other files.
    if (body) fillPictures(body, chatId, shown, scope, live && answerWriting());
    else if (shown.length) {
      const gallery = node('div', 'agent-answer-pictures');
      for (const file of shown) gallery.append(pictureCard(chatId, file, scope));
      own.push(gallery);
    }
    // A page runs under the text, each in the figure it keeps; a turn
    // without an answer text shows it with its other files.
    const pages = shared.filter(file => isPage(file) && available(file));
    if (body) fillPages(body, chatId, pages, scope);
    else for (const file of pages) { const card = pageCard(chatId, file, scope); card.sync(); own.push(card.figure); }
    const rows = [...shared.filter(file => !shown.includes(file) && !pages.includes(file)),
      ...files.filter(file => file.kind === 'mail_attachment' && file.turn_id === turnId)];
    if (rows.length) {
      const list = node('div', 'agent-files-list');
      for (const file of rows) list.append(fileRow(chatId, file, scope));
      own.push(list);
    }
    if (body) fillDocuments(body, own); else box.append(...own);
  }
  function fillHistoryRow(row) {
    row.replaceChildren();
    const turnId = row.dataset.agentTurnResources;
    if (chat && data) turnResources(row, chat, data.files || [], turnId, `turn:${turnId}`, false, row._answerBody);
    else {
      fillPictures(row._answerBody, chat, [], `turn:${turnId}`); fillPages(row._answerBody, chat, [], `turn:${turnId}`);
      fillDocuments(row._answerBody, []);
    }
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
        // quiet line, no surface and no technical reason, Retry as the text link.
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
    // A file of the chat left behind stays in it.
    if (App.fileViewer?.isOpen?.()) App.fileViewer.close({ focus: false });
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
    // sent), with no row per file under the message.
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
      App.attachments?.releaseStored?.(files);
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
    const shown = demoFiles.get(fileId);
    if (shown) {
      const blob = await demoFetch(shown.demo.file);
      return { blob, mime: blob.type || shown.mime || '' };
    }
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

  // ---- the demo (static/demo.js) ----------------------------------------------------
  // The demo's turn shares a chart and a spreadsheet as a real turn does: the
  // picture in its place in the answer, the spreadsheet as a row with its
  // first page under it, each opening in the same viewer. Its files are the
  // static ones under static/demo (scripts/demo_assets.py), each
  // { id, name, mime, kind, preview?, origin?, demo: { file, preview? } }:
  // loaded without a chat or an account, never removable. demo(body, files)
  // shows them with that answer (called again as the turn shares more),
  // demo(null) lets go. With { writing: true } the answer is still being
  // written: as in a live run, a picture waits for its place in the text
  // instead of standing under it first; it loads already.
  async function demoFetch(url) {
    const response = await fetch(url);
    if (!response.ok) throw new Error('The file couldn’t load.');
    return response.blob();
  }
  function demo(body, files = [], { writing = false } = {}) {
    if (demoBody && demoBody !== body) { fillPictures(demoBody, '', [], 'demo'); fillDocuments(demoBody, []); }
    if (!body) {
      for (const id of demoFiles.keys()) pictures.delete(id);
      demoFiles.clear(); demoBody = null;
      return;
    }
    demoBody = body;
    for (const file of files) demoFiles.set(file.id, file);
    const shown = files.filter(isPicture);
    for (const file of shown) picture('', file);
    fillPictures(body, '', shown, 'demo', writing);
    const rows = files.filter(file => !shown.includes(file));
    const list = node('div', 'agent-files-list');
    for (const file of rows) list.append(fileRow('', file, 'demo'));
    fillDocuments(body, rows.length ? [list] : []);
  }

  window.addEventListener('consensio:auth-state', () => {
    reset(); chat = ''; owner = ''; openState.versions.clear(); hideAll();
  });
  App.agentWorkspace = { refresh, upload, request, button, download, openFile, openPreview, pageAddress, pageFrame,
    removeFile, renderTurnResources, demo };
  App.answerTail = answerTail;
})();
