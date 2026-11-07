// The preview of a file beside the chat (Max: "einen Viewer für
// Office-Dokumente … wie bei ChatGPT", then "natürlich auch für PDFs … für
// Code natürlich auch"). Presentations, Word files, spreadsheets and PDFs
// show page by page with a rail of thumbnails ("5 slides"), code and text
// with line numbers, Markdown as read, CSV as a table.
//
// Every document is shown as a PDF, drawn here by pdf.js
// (static/vendor/pdfjs, imported when a preview first needs it; no eval, no
// links, no scripts of the file: only the canvas of each page). An Office
// file the agent shared from its workspace brings its PDF from the converter
// all accounts share (agent_office.py), a created document has its own, a
// Word file the user
// sent previews as its text; the server answers all of them on
// GET …/files/{id}?preview=1 (routers/agent_files.py). Pictures keep the
// picture viewer (attachments.js), which pages through a gallery.
//
// Wide screens (DOCK_QUERY) dock the preview at the right edge in its own
// lane, as the workspace does (workspace-view.js): the chat narrows and
// re-centres left of it (body.file-viewer-docked, --file-viewer-width;
// file-viewer.css), the activity panel and the workspace wait beneath it.
// The edge drags and remembers its width per browser; "Full screen" takes
// the whole window. Narrower screens show it over everything. It opens only
// when the user opens a file, never by itself (Max: panels open on a click
// alone).
//
// App.fileViewer: open(item), close(), isOpen(), describe(file) (how a file
// is shown and called), previews(file), thumbnail(host, item, onInfo) (the
// first page of a card, loaded when it comes near the screen). An item:
// { key, name, title?, mime, family?, load() -> Promise<{ blob, mime }>,
//   downloads: [{ label, run }], remove?, removeLabel? }.
(() => {
  'use strict';
  const App = window.App = window.App || {};
  const PDFJS_DIR = '/static/vendor/pdfjs/6.4.299/';
  const DOCK_QUERY = '(min-width: 1100px)';
  // The rail of thumbnails needs a preview this wide, and narrows below RAIL_FULL.
  const RAIL_MIN = 520;
  const RAIL_FULL = 720;
  const MIN_WIDTH = 420;
  // The chat keeps this much beside the preview: room to read and write, and
  // the composer on one line (field, reviewers in short, model, Send). Where
  // the window leaves less beside MIN_WIDTH, the preview covers the chat.
  const MIN_CHAT = 600;
  const KEY_STEP = 40;
  const WIDTH_KEY = 'consens.fileViewerWidth';
  const RAIL_KEY = 'consens.fileViewerRail';
  const TEXT_BYTES = 2 * 1024 * 1024;
  const MAX_LINES = 20000;
  const MAX_ROWS = 1000;
  const ZOOMS = [0.5, 0.75, 1, 1.25, 1.5, 2];
  // 100 % is a page at its printed size: 72 points an inch, 96 CSS pixels.
  const CSS_PER_POINT = 96 / 72;
  // A page wider than this does not fit a document's page to the width.
  const FIT_PORTRAIT_MAX = 880;
  const MAX_CANVAS_PIXELS = 16 * 1024 * 1024;
  const THUMB_WIDTH = 132;
  const THUMB_NARROW = 96;
  const PAD = 24;
  const DOCUMENTS_KEPT = 4;
  const SVG = 'http://www.w3.org/2000/svg';
  const ICONS = {
    file: 'M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8zM14 3v5h5',
    slides: 'M4 5h16v11H4zM12 16v4M8 20h8',
    sheet: 'M4 4h16v16H4zM4 10h16M4 15h16M10 4v16',
    code: 'M9 8l-4 4 4 4M15 8l4 4-4 4',
    download: 'M12 4v11M7 10l5 5 5-5M5 20h14',
    expand: 'M14 4h6v6M10 20H4v-6M20 4l-7 7M4 20l7-7',
    collapse: 'M20 10h-6V4M4 14h6v6M14 10l7-7M10 14l-7 7',
    play: 'M8 5.5v13l11-6.5z',
    rail: 'M4 4h16v16H4zM9 4v16',
    more: 'M5 12h.01M12 12h.01M19 12h.01',
    chevron: 'M7 10l5 5 5-5',
  };
  const OFFICE = {
    pptx: ['presentation', 'PowerPoint'], ppt: ['presentation', 'PowerPoint'], ppsx: ['presentation', 'PowerPoint'],
    pps: ['presentation', 'PowerPoint'], odp: ['presentation', 'Presentation'],
    docx: ['document', 'Word'], doc: ['document', 'Word'], odt: ['document', 'Document'], rtf: ['document', 'Document'],
    xlsx: ['spreadsheet', 'Excel'], xls: ['spreadsheet', 'Excel'], ods: ['spreadsheet', 'Spreadsheet'],
  };
  const CODE = {
    py: 'Python', js: 'JavaScript', mjs: 'JavaScript', cjs: 'JavaScript', jsx: 'JavaScript', ts: 'TypeScript',
    tsx: 'TypeScript', json: 'JSON', ipynb: 'Notebook', html: 'HTML', htm: 'HTML', css: 'CSS', scss: 'CSS',
    sh: 'Shell', bash: 'Shell', zsh: 'Shell', ps1: 'PowerShell', sql: 'SQL', yml: 'YAML', yaml: 'YAML',
    toml: 'TOML', ini: 'INI', cfg: 'INI', xml: 'XML', svg: 'SVG', java: 'Java', kt: 'Kotlin', go: 'Go',
    rs: 'Rust', c: 'C', h: 'C', cpp: 'C++', cc: 'C++', hpp: 'C++', cs: 'C#', rb: 'Ruby', php: 'PHP',
    swift: 'Swift', r: 'R', lua: 'Lua', pl: 'Perl', dart: 'Dart', scala: 'Scala', vue: 'Vue', svelte: 'Svelte',
    tex: 'LaTeX', dockerfile: 'Dockerfile', makefile: 'Makefile',
  };
  const PLAIN = { txt: 'Text', log: 'Log', text: 'Text' };
  // What a page is called: a slide in a presentation, a sheet in a spreadsheet.
  const UNITS = {
    presentation: ['1 slide', '{n} slides', 'Slide {n}'],
    spreadsheet: ['1 sheet', '{n} sheets', 'Sheet {n}'],
    page: ['1 page', '{n} pages', 'Page {n}'],
  };

  let view = null;
  let pdfjs = null;
  let worker = null;
  // Bodies and parsed documents per item key, shared by cards and the viewer.
  const bodies = new Map();
  const documents = new Map();
  let thumbWatcher = null;
  const thumbQueue = [];
  let thumbsRunning = 0;

  function node(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined && text !== null) element.textContent = text;
    return element;
  }
  function icon(name) {
    const svg = document.createElementNS(SVG, 'svg');
    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('aria-hidden', 'true');
    svg.setAttribute('class', `file-viewer-icon file-viewer-icon-${name}`);
    const path = document.createElementNS(SVG, 'path');
    path.setAttribute('d', ICONS[name]);
    svg.append(path);
    return svg;
  }
  function toolButton(name, label, handler) {
    const control = node('button', `file-viewer-tool file-viewer-tool-${name}`);
    control.type = 'button';
    control.setAttribute('aria-label', label);
    control.title = label;
    control.append(icon(name));
    control.addEventListener('click', handler);
    return control;
  }
  function track(name, data) {
    if (typeof window.trackUmamiEvent === 'function') window.trackUmamiEvent(name, data);
  }
  const matches = query => Boolean(window.matchMedia?.(query)?.matches);
  const viewportWidth = () => document.documentElement.clientWidth || window.innerWidth;
  const reduced = () => matches('(prefers-reduced-motion: reduce)');
  function stored(key) {
    try { return localStorage.getItem(key); } catch (error) { return null; }
  }
  function store(key, value) {
    try { localStorage.setItem(key, value); } catch (error) { /* per browser only */ }
  }

  // ---- What a file is -----------------------------------------------------
  function extensionOf(name) {
    const base = String(name || '').toLowerCase().split('/').pop();
    if (base === 'dockerfile' || base === 'makefile') return base;
    const match = /\.([a-z0-9]{1,10})$/.exec(base);
    return match ? match[1] : '';
  }
  // How a file is shown (view), what kind of pages it has (family) and its
  // type's name for a card ("PowerPoint", "PDF", "Python").
  function describe(file) {
    const ext = extensionOf(file?.name);
    const mime = String(file?.mime || '').toLowerCase().split(';')[0];
    if (file?.family === 'document') return { view: 'pdf', family: 'document', label: 'Document' };
    if (OFFICE[ext]) return { view: 'pdf', family: OFFICE[ext][0], label: OFFICE[ext][1] };
    if (mime === 'application/pdf' || ext === 'pdf') return { view: 'pdf', family: 'pdf', label: 'PDF' };
    if (ext === 'md' || ext === 'markdown' || mime === 'text/markdown') return { view: 'markdown', family: 'text', label: 'Markdown' };
    if (ext === 'csv' || ext === 'tsv' || mime === 'text/csv' || mime === 'text/tab-separated-values') {
      return { view: 'table', family: 'text', label: ext === 'tsv' ? 'TSV' : 'CSV' };
    }
    if (CODE[ext]) return { view: 'code', family: 'code', label: CODE[ext] };
    if (PLAIN[ext] || mime.startsWith('text/')) return { view: 'text', family: 'text', label: PLAIN[ext] || 'Text' };
    if (mime.startsWith('image/')) return { view: 'image', family: 'image', label: 'Image' };
    return { view: 'none', family: 'other', label: ext ? ext.toUpperCase() : 'File' };
  }
  // Whether the viewer can show it: an Office file only with the PDF made of
  // it, or as the text of a Word file the user sent.
  function previews(file) {
    const described = describe(file);
    if (described.view === 'none' || described.view === 'image') return false;
    if (OFFICE[extensionOf(file?.name)] && file?.family !== 'document') {
      return Boolean(file?.preview) || extensionOf(file?.name) === 'docx' && file?.kind !== 'vm_file';
    }
    return true;
  }
  function units(family) {
    return UNITS[family === 'presentation' || family === 'spreadsheet' ? family : 'page'];
  }
  // In the page's language: the number goes in after the words are translated.
  function countText(family, count) {
    const [one, many] = units(family);
    const text = count === 1 ? one : many;
    return App.t ? App.t(text, { n: count }) : text.replace('{n}', String(count));
  }
  function pageName(family, number) {
    return units(family)[2].replace('{n}', String(number));
  }

  // ---- Loading --------------------------------------------------------------
  function body(item) {
    let entry = bodies.get(item.key);
    if (!entry) {
      entry = Promise.resolve().then(() => item.load()).then(result => ({
        blob: result.blob, mime: String(result.mime || result.blob?.type || '').toLowerCase().split(';')[0],
      }));
      entry.catch(() => { if (bodies.get(item.key) === entry) bodies.delete(item.key); });
      bodies.set(item.key, entry);
      while (bodies.size > DOCUMENTS_KEPT * 2) bodies.delete(bodies.keys().next().value);
    }
    return entry;
  }
  function loadPdfjs() {
    if (!pdfjs) {
      pdfjs = import(`${PDFJS_DIR}build/pdf.min.mjs`).then(lib => {
        lib.GlobalWorkerOptions.workerSrc = `${PDFJS_DIR}build/pdf.worker.min.mjs`;
        return lib;
      });
      pdfjs.catch(() => { pdfjs = null; });
    }
    return pdfjs;
  }
  // The parsed PDF of an item, kept for a few items: a card's thumbnail and
  // the viewer share it. One worker for all of them.
  function pdfDocument(item) {
    let entry = documents.get(item.key);
    if (!entry) {
      entry = Promise.all([loadPdfjs(), body(item)]).then(async ([lib, loaded]) => {
        if (loaded.mime !== 'application/pdf') {
          const error = new Error('Not a PDF');
          error.loaded = loaded;
          throw error;
        }
        worker = worker || new lib.PDFWorker({ name: 'file-preview' });
        const data = new Uint8Array(await bytesOf(loaded.blob));
        return lib.getDocument({ data, worker, isEvalSupported: false, enableXfa: false,
          standardFontDataUrl: `${PDFJS_DIR}standard_fonts/`, wasmUrl: `${PDFJS_DIR}wasm/`,
          cMapUrl: `${PDFJS_DIR}cmaps/`, cMapPacked: true }).promise;
      });
      entry.catch(() => { if (documents.get(item.key) === entry) documents.delete(item.key); });
      documents.set(item.key, entry);
      for (const [key, kept] of documents) {
        if (documents.size <= DOCUMENTS_KEPT) break;
        if (view?.item.key === key) continue;
        documents.delete(key);
        kept.then(doc => doc.destroy()).catch(() => {});
      }
    }
    return entry;
  }
  function bytesOf(blob) {
    if (typeof blob.arrayBuffer === 'function') return blob.arrayBuffer();
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = () => reject(reader.error);
      reader.readAsArrayBuffer(blob);
    });
  }
  // Text as its file wrote it: a byte order mark says UTF-8 or UTF-16;
  // without one UTF-8, and what is no UTF-8 reads as Windows-1252 (a CSV
  // from a German Excel). A file with NUL characters is no text (notText).
  async function textOf(blob) {
    const bytes = new Uint8Array(await bytesOf(blob));
    let text;
    if (bytes[0] === 0xff && bytes[1] === 0xfe) text = new TextDecoder('utf-16le').decode(bytes.subarray(2));
    else if (bytes[0] === 0xfe && bytes[1] === 0xff) text = new TextDecoder('utf-16be').decode(bytes.subarray(2));
    else {
      const body = bytes.subarray(bytes[0] === 0xef && bytes[1] === 0xbb && bytes[2] === 0xbf ? 3 : 0);
      try {
        text = new TextDecoder('utf-8', { fatal: true }).decode(body);
      } catch (error) {
        text = new TextDecoder('windows-1252').decode(body);
      }
    }
    if (text.includes('\u0000')) {
      const error = new Error('Not text');
      error.notText = true;
      throw error;
    }
    return text;
  }

  // ---- Drawing a page -------------------------------------------------------
  // ``page`` drawn ``width`` CSS pixels wide into a new canvas, sharp on the
  // screen's pixels but never larger than MAX_CANVAS_PIXELS.
  function drawPage(page, width, register) {
    const base = page.getViewport({ scale: 1 });
    let scale = (width / base.width) * Math.min(window.devicePixelRatio || 1, 3);
    const area = base.width * base.height * scale * scale;
    if (area > MAX_CANVAS_PIXELS) scale *= Math.sqrt(MAX_CANVAS_PIXELS / area);
    const viewport = page.getViewport({ scale });
    const canvas = node('canvas', 'file-viewer-canvas');
    canvas.width = Math.max(1, Math.floor(viewport.width));
    canvas.height = Math.max(1, Math.floor(viewport.height));
    canvas.setAttribute('aria-hidden', 'true');
    const task = page.render({ canvas, viewport });
    register?.(task);
    return task.promise.then(() => canvas);
  }
  function cancelled(error) {
    return error?.name === 'RenderingCancelledException' || /cancel/i.test(String(error?.message || ''));
  }

  // ---- Cards: the first page as a thumbnail ---------------------------------
  const thumbs = new Map();
  // The mark of a card (agent-workspace.css .agent-file-thumb).
  const THUMB_BOX = { width: 64, height: 48 };
  // The marks waiting to come near the screen; one rebuilt with its answer
  // leaves the watcher (an IntersectionObserver keeps what it observes).
  const watched = new Set();
  function copyCanvas(source) {
    const canvas = node('canvas', source.className);
    canvas.width = source.width;
    canvas.height = source.height;
    canvas.style.cssText = source.style.cssText;
    canvas.setAttribute('aria-hidden', 'true');
    canvas.getContext('2d')?.drawImage(source, 0, 0);
    return canvas;
  }
  function pumpThumbs() {
    while (thumbsRunning < 2 && thumbQueue.length) {
      const job = thumbQueue.shift();
      thumbsRunning++;
      job().finally(() => { thumbsRunning--; pumpThumbs(); });
    }
  }
  // The first page of ``item`` in ``host`` once it comes near the screen;
  // ``onInfo({ pages, landscape })`` when it is known. Nothing happens for a
  // file that is no PDF to the viewer: the card keeps its glyph.
  function thumbnail(host, item, onInfo) {
    if (!host || describe(item).view !== 'pdf') return;
    // An Office file without its PDF has no page to show (a Word file the user sent previews as text).
    if (OFFICE[extensionOf(item.name)] && !item.preview && item.family !== 'document') return;
    const place = (canvas, info) => {
      host.classList.toggle('is-portrait', !info.landscape);
      host.replaceChildren(canvas);
      host.classList.add('has-thumb');
      onInfo?.(info);
    };
    // A card drawn again (a new projection of the answer) shows it at once.
    const known = thumbs.get(item.key);
    if (known) { place(copyCanvas(known.canvas), known.info); return; }
    const start = () => { thumbQueue.push(draw); pumpThumbs(); };
    const draw = async () => {
      try {
        const doc = await pdfDocument(item);
        const page = await doc.getPage(1);
        const base = page.getViewport({ scale: 1 });
        const landscape = base.width >= base.height;
        // A card not laid out yet (its answer still hidden) has no size: the
        // thumbnail is cached, so it takes the size of a card's mark.
        const box = host.getBoundingClientRect();
        const boxWidth = box.width || THUMB_BOX.width, boxHeight = box.height || THUMB_BOX.height;
        const width = Math.max(24, Math.round(Math.min(boxWidth, boxHeight * base.width / base.height)));
        const canvas = await drawPage(page, width);
        canvas.style.width = `${width}px`;
        canvas.style.height = `${Math.round(width * base.height / base.width)}px`;
        const info = { pages: doc.numPages, landscape };
        thumbs.set(item.key, { canvas, info });
        while (thumbs.size > 40) thumbs.delete(thumbs.keys().next().value);
        if (host.isConnected) place(copyCanvas(canvas), info);
      } catch (error) { /* The card keeps its glyph. */ }
    };
    if (typeof IntersectionObserver !== 'function') { start(); return; }
    if (!thumbWatcher) {
      thumbWatcher = new IntersectionObserver(entries => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          thumbWatcher.unobserve(entry.target);
          watched.delete(entry.target);
          entry.target._thumbStart?.();
        }
      }, { rootMargin: '400px 0px' });
    }
    // A card is built before it is placed: only a mark that has been
    // detached for a while is gone for good.
    const now = Date.now();
    for (const old of watched) {
      if (!old.isConnected && now - old._watchedAt > 2000) { thumbWatcher.unobserve(old); watched.delete(old); }
    }
    host._thumbStart = start;
    host._watchedAt = now;
    watched.add(host);
    thumbWatcher.observe(host);
  }

  // ---- The panel --------------------------------------------------------------
  function build() {
    const panel = node('aside', 'file-viewer');
    panel.id = 'fileViewer';
    panel.setAttribute('role', 'dialog');
    panel.hidden = true;
    const resizer = node('div', 'file-viewer-resizer');
    resizer.setAttribute('role', 'separator');
    resizer.setAttribute('aria-orientation', 'vertical');
    resizer.setAttribute('aria-label', 'Resize the preview');
    resizer.title = 'Drag to resize';
    resizer.tabIndex = 0;
    resizer.addEventListener('pointerdown', startDrag);
    resizer.addEventListener('keydown', keyResize);
    resizer.addEventListener('dblclick', () => {
      try { localStorage.removeItem(WIDTH_KEY); } catch (error) { /* per browser only */ }
      layout(preferredWidth());
    });

    const head = node('header', 'file-viewer-head');
    const file = node('div', 'file-viewer-file');
    const glyph = node('span', 'file-viewer-file-glyph');
    const name = node('span', 'file-viewer-name');
    name.dataset.i18nSkip = '';
    file.append(glyph, name);
    const count = node('span', 'file-viewer-count');
    count.setAttribute('aria-live', 'polite');
    count.dataset.i18nSkip = '';
    const tools = node('div', 'file-viewer-tools');
    const zoomWrap = node('div', 'file-viewer-menu-wrap');
    const zoom = node('button', 'file-viewer-tool file-viewer-zoom');
    zoom.type = 'button';
    zoom.setAttribute('aria-haspopup', 'menu');
    zoom.setAttribute('aria-expanded', 'false');
    zoom.title = 'Zoom';
    const zoomLabel = node('span', 'file-viewer-zoom-label', 'Fit');
    zoom.append(zoomLabel, icon('chevron'));
    const zoomMenu = node('div', 'file-viewer-menu');
    zoomMenu.setAttribute('role', 'menu');
    zoomMenu.setAttribute('aria-label', 'Zoom');
    zoomMenu.hidden = true;
    for (const level of ['fit', ...ZOOMS]) {
      const entry = node('button', 'file-viewer-menu-item', level === 'fit' ? 'Fit' : `${Math.round(level * 100)}%`);
      entry.type = 'button';
      entry.setAttribute('role', 'menuitemradio');
      entry.dataset.zoom = String(level);
      entry.addEventListener('click', () => { closeMenu(zoomMenu); setZoom(level); ui.stage.focus({ preventScroll: true }); });
      zoomMenu.append(entry);
    }
    zoom.addEventListener('click', () => toggleMenu(zoomMenu, zoom));
    zoomWrap.append(zoom, zoomMenu);
    const present = toolButton('play', 'Present', startPresenting);
    const downloadWrap = node('div', 'file-viewer-menu-wrap');
    const download = toolButton('download', 'Download', () => {
      const list = view?.item.downloads || [];
      if (list.length > 1) toggleMenu(downloadMenu, download);
      else runDownload(list[0], download);
    });
    const downloadMenu = node('div', 'file-viewer-menu');
    downloadMenu.setAttribute('role', 'menu');
    downloadMenu.setAttribute('aria-label', 'Download');
    downloadMenu.hidden = true;
    downloadWrap.append(download, downloadMenu);
    const moreWrap = node('div', 'file-viewer-menu-wrap');
    const more = toolButton('more', 'More actions', () => toggleMenu(moreMenu, more));
    more.setAttribute('aria-haspopup', 'menu');
    const moreMenu = node('div', 'file-viewer-menu');
    moreMenu.setAttribute('role', 'menu');
    moreMenu.hidden = true;
    moreWrap.append(more, moreMenu);
    const expand = toolButton('expand', 'Full screen', () => setExpanded(!view?.expanded));
    expand.setAttribute('aria-pressed', 'false');
    const closer = node('button', 'close-button file-viewer-close');
    closer.type = 'button';
    closer.setAttribute('aria-label', 'Close preview');
    closer.title = 'Close preview';
    closer.innerHTML = App.closeIcon?.() || '<svg class="close-icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M4 4l8 8M12 4l-8 8"/></svg>';
    closer.addEventListener('click', () => close());
    tools.append(zoomWrap, present, downloadWrap, moreWrap, expand, closer);
    head.append(file, count, tools);

    const main = node('div', 'file-viewer-main');
    const rail = node('nav', 'file-viewer-rail');
    const railHead = node('div', 'file-viewer-rail-head');
    const railCount = node('span', 'file-viewer-rail-count');
    const railToggle = toolButton('rail', 'Hide thumbnails', () => setRail(false));
    railHead.append(railCount, railToggle);
    const thumbs = node('ol', 'file-viewer-thumbs');
    rail.append(railHead, thumbs);
    const showRail = toolButton('rail', 'Show thumbnails', () => setRail(true));
    showRail.classList.add('file-viewer-show-rail');
    const stage = node('div', 'file-viewer-stage');
    stage.tabIndex = 0;
    stage.addEventListener('keydown', onStageKey);
    const pages = node('div', 'file-viewer-pages');
    stage.append(pages);
    main.append(rail, showRail, stage);
    panel.append(resizer, head, main);
    panel.addEventListener('keydown', onPanelKey);
    panel.addEventListener('animationend', () => panel.classList.remove('is-entering'));
    for (const menu of [zoomMenu, downloadMenu, moreMenu]) {
      App.popover?.register(menu, { close: () => closeMenu(menu) });
      App.popover?.menuKeys?.(menu, { close: () => closeMenu(menu), opener: () => menu.previousElementSibling });
    }
    document.body.append(panel);
    return { panel, resizer, name, glyph, count, zoom, zoomLabel, zoomMenu, present, download, downloadMenu, more,
      moreMenu, expand, closer, main, rail, railCount, thumbs, showRail, stage, pages };
  }

  function toggleMenu(menu, trigger) {
    if (!menu.hidden) { closeMenu(menu); return; }
    for (const other of [ui.zoomMenu, ui.downloadMenu, ui.moreMenu]) if (other !== menu) closeMenu(other);
    if (menu === ui.downloadMenu) fillDownloads();
    if (menu === ui.moreMenu) fillMore();
    if (menu === ui.zoomMenu) {
      for (const entry of menu.children) entry.setAttribute('aria-checked', String(entry.dataset.zoom === String(view?.zoom)));
    }
    menu.hidden = false;
    trigger.setAttribute('aria-expanded', 'true');
    App.popover?.opened(menu, { trigger });
    (menu.querySelector('[aria-checked="true"]') || menu.querySelector('button'))?.focus({ preventScroll: true });
  }
  function closeMenu(menu) {
    if (!menu || menu.hidden) return;
    menu.hidden = true;
    menu.previousElementSibling?.setAttribute('aria-expanded', 'false');
    App.popover?.closed(menu);
  }
  function closeMenus() {
    if (ui) for (const menu of [ui.zoomMenu, ui.downloadMenu, ui.moreMenu]) closeMenu(menu);
  }
  document.addEventListener('click', event => {
    if (ui && !event.target.closest?.('.file-viewer-menu-wrap')) closeMenus();
  });
  async function runDownload(entry, control) {
    if (!entry) return;
    if (control) control.disabled = true;
    try { await entry.run(); } catch (failure) {
      App.showPopup?.(App.userError?.(failure, { fallback: 'The download failed. Try again.' }) || 'The download failed. Try again.');
    } finally { if (control) control.disabled = false; }
  }
  function fillDownloads() {
    ui.downloadMenu.replaceChildren(...(view?.item.downloads || []).map(entry => {
      const item = node('button', 'file-viewer-menu-item', `Download ${entry.label}`);
      item.type = 'button';
      item.setAttribute('role', 'menuitem');
      item.addEventListener('click', () => { closeMenu(ui.downloadMenu); runDownload(entry, ui.download); });
      return item;
    }));
  }
  function fillMore() {
    const item = node('button', 'file-viewer-menu-item is-danger', view?.item.removeLabel || 'Remove from chat…');
    item.type = 'button';
    item.setAttribute('role', 'menuitem');
    item.addEventListener('click', async () => {
      closeMenu(ui.moreMenu);
      const current = view;
      if (!current?.item.remove) return;
      const name = current.item.title || current.item.name;
      const yes = App.confirm ? await App.confirm({ title: App.t ? App.t('Remove {name}?', { name }) : `Remove ${name}?`,
        body: 'The agent can no longer use it in this chat.', confirmLabel: 'Remove', danger: true }) : true;
      if (!yes || view !== current) return;
      try {
        await current.item.remove();
        close({ focus: false });
      } catch (failure) {
        App.showPopup?.(App.userError?.(failure, { context: 'delete' }) || 'The file could not be removed.');
      }
    });
    ui.moreMenu.replaceChildren(item);
  }

  // ---- Lane beside the chat ---------------------------------------------------
  let ui = null;
  function docked() {
    return matches(DOCK_QUERY) && viewportWidth() - sidebarOffset() - MIN_WIDTH >= MIN_CHAT;
  }
  function sidebarOffset() {
    return Number.parseFloat(getComputedStyle(document.body).getPropertyValue('--app-sidebar-offset')) || 0;
  }
  function bounds() {
    const room = viewportWidth() - sidebarOffset() - MIN_CHAT;
    return { min: MIN_WIDTH, max: Math.max(MIN_WIDTH, room) };
  }
  // A little more than half of what is left beside the app's sidebar: a page
  // is worth more room than the chat while it is open, and the composer
  // still fits its tools.
  function preferredWidth() {
    return Number(stored(WIDTH_KEY)) || Math.round((viewportWidth() - sidebarOffset()) * 0.52);
  }
  function layout(width) {
    if (!view) return;
    const isDocked = docked() && !view.expanded;
    const { min, max } = bounds();
    view.width = Math.round(Math.min(max, Math.max(min, width || view.width || preferredWidth())));
    document.body.classList.toggle('file-viewer-docked', isDocked);
    document.body.classList.toggle('file-viewer-covers', !isDocked);
    document.body.style.setProperty('--file-viewer-width', `${isDocked ? view.width : 0}px`);
    ui.panel.classList.toggle('is-expanded', Boolean(view.expanded));
    ui.panel.toggleAttribute('aria-modal', !isDocked);
    setCovering(!isDocked);
    if (isDocked && document.body.classList.contains('answer-reader-docked')) App.answerReader?.close?.({ focus: false });
    ui.resizer.hidden = !isDocked;
    ui.expand.hidden = !docked();
    ui.resizer.setAttribute('aria-valuemin', String(Math.round(min)));
    ui.resizer.setAttribute('aria-valuemax', String(Math.round(max)));
    ui.resizer.setAttribute('aria-valuenow', String(view.width));
    syncRail();
    relayout();
  }
  // Over everything (aria-modal), what lies beneath is inert: Tab and a
  // screen reader stay in the preview. Dialogs keep their own layer.
  let inerted = [];
  function setCovering(on) {
    if (!on) {
      for (const element of inerted) element.inert = false;
      inerted = [];
      return;
    }
    for (const element of document.body.children) {
      if (element === ui.panel || element.inert || ['DIALOG', 'SCRIPT', 'TEMPLATE'].includes(element.tagName)) continue;
      element.inert = true;
      inerted.push(element);
    }
  }
  function startDrag(event) {
    if (!view || event.button !== 0) return;
    event.preventDefault();
    const resizer = ui.resizer;
    resizer.setPointerCapture?.(event.pointerId);
    document.body.classList.add('file-viewer-resizing');
    const edge = viewportWidth();
    const move = moved => layout(edge - moved.clientX);
    const end = () => {
      resizer.removeEventListener('pointermove', move);
      resizer.removeEventListener('pointerup', end);
      resizer.removeEventListener('pointercancel', end);
      document.body.classList.remove('file-viewer-resizing');
      if (view) { store(WIDTH_KEY, String(view.width)); relayout(); }
    };
    resizer.addEventListener('pointermove', move);
    resizer.addEventListener('pointerup', end);
    resizer.addEventListener('pointercancel', end);
  }
  function keyResize(event) {
    if (!view) return;
    const { min, max } = bounds();
    const next = { ArrowLeft: view.width + KEY_STEP, ArrowRight: view.width - KEY_STEP, Home: max, End: min }[event.key];
    if (next === undefined) return;
    event.preventDefault();
    layout(next);
    store(WIDTH_KEY, String(view.width));
  }
  function setExpanded(on) {
    if (!view) return;
    view.expanded = Boolean(on);
    ui.expand.replaceChildren(icon(view.expanded ? 'collapse' : 'expand'));
    const label = view.expanded ? 'Exit full screen' : 'Full screen';
    ui.expand.setAttribute('aria-label', label);
    ui.expand.title = label;
    ui.expand.setAttribute('aria-pressed', String(view.expanded));
    layout();
  }
  function panelWidth() {
    return document.body.classList.contains('file-viewer-docked') ? view.width : viewportWidth();
  }
  function thumbWidthNow() {
    return view && panelWidth() < RAIL_FULL ? THUMB_NARROW : THUMB_WIDTH;
  }
  function railWanted() {
    return stored(RAIL_KEY) !== 'hidden';
  }
  function syncRail() {
    if (!view) return;
    const has = view.kind === 'pdf' && view.count > 1 && panelWidth() >= RAIL_MIN;
    ui.panel.classList.toggle('has-narrow-rail', panelWidth() < RAIL_FULL);
    const shown = has && railWanted();
    ui.rail.hidden = !shown;
    ui.showRail.hidden = !has || shown;
  }
  function setRail(on) {
    store(RAIL_KEY, on ? 'shown' : 'hidden');
    syncRail();
    relayout();
    (on ? ui.rail.querySelector('[aria-current="true"]') || ui.rail : ui.showRail)?.focus?.({ preventScroll: true });
  }

  // ---- Opening and closing ------------------------------------------------------
  function open(item) {
    if (!item || typeof item.load !== 'function') return;
    ui = ui || build();
    const trigger = item.trigger || document.activeElement;
    const wasOpen = Boolean(view);
    teardown();
    const described = describe(item);
    view = { item, described, trigger, kind: '', count: 0, active: 1, zoom: 'fit', entries: [], width: view?.width || 0,
      expanded: wasOpen ? Boolean(ui.panel.classList.contains('is-expanded')) : false, token: Symbol('view') };
    const shown = item.title || item.name;
    ui.panel.setAttribute('aria-label', App.t ? App.t('Preview of {shown}', { shown }) : `Preview of ${shown}`);
    ui.name.textContent = item.title || item.name;
    ui.name.title = item.name;
    ui.glyph.replaceChildren(icon(glyphFor(described)));
    ui.count.textContent = '';
    ui.count.dataset.i18nSkip = '';
    ui.zoomLabel.textContent = 'Fit';
    ui.download.hidden = !(item.downloads || []).length;
    ui.download.setAttribute('aria-haspopup', (item.downloads || []).length > 1 ? 'menu' : 'false');
    ui.more.parentElement.hidden = typeof item.remove !== 'function';
    ui.present.hidden = true;
    ui.zoom.parentElement.hidden = true;
    ui.pages.replaceChildren(loadingSheet(described));
    ui.thumbs.replaceChildren();
    ui.stage.scrollTop = 0;
    ui.stage.classList.remove('is-text');
    ui.panel.hidden = false;
    if (!wasOpen && !reduced()) ui.panel.classList.add('is-entering');
    document.body.classList.add('file-viewer-open');
    setExpanded(view.expanded);
    if (!wasOpen) window.addEventListener('resize', onWindowResize);
    // Into the preview, also when another file replaces the one shown: its
    // keys (pages, zoom, Escape) work at once.
    ui.stage.focus({ preventScroll: true });
    track('app_file_preview_opened', { view: described.view, family: described.family });
    show(view);
  }
  function glyphFor(described) {
    if (described.family === 'presentation') return 'slides';
    if (described.family === 'spreadsheet' || described.view === 'table') return 'sheet';
    if (described.view === 'code') return 'code';
    return 'file';
  }
  function teardown() {
    if (!view) return;
    closeMenus();
    stopPresenting();
    view.observer?.disconnect();
    view.thumbObserver?.disconnect();
    for (const entry of view.entries) {
      entry.task?.cancel();
      entry.thumbTask?.cancel();
      freeCanvases(entry.el);
      freeCanvases(entry.thumbFrame);
    }
    clearTimeout(drawTimer);
    view.token = null;
  }
  function close({ focus = true } = {}) {
    if (!view) return;
    const trigger = view.trigger;
    teardown();
    view = null;
    window.removeEventListener('resize', onWindowResize);
    setCovering(false);
    ui.panel.hidden = true;
    ui.panel.classList.remove('is-entering', 'is-expanded');
    ui.pages.replaceChildren();
    ui.thumbs.replaceChildren();
    document.body.classList.remove('file-viewer-open', 'file-viewer-docked', 'file-viewer-covers');
    document.body.style.removeProperty('--file-viewer-width');
    if (focus && trigger?.isConnected) trigger.focus({ preventScroll: true });
  }
  let resizeFrame = 0;
  function onWindowResize() {
    cancelAnimationFrame(resizeFrame);
    resizeFrame = requestAnimationFrame(() => layout());
  }
  function onPanelKey(event) {
    if (event.key !== 'Escape' || event.defaultPrevented) return;
    if (presenting) return;
    event.preventDefault();
    close();
  }
  // Over everything (a phone, Full screen), Escape closes from anywhere.
  document.addEventListener('keydown', event => {
    if (!view || event.key !== 'Escape' || event.defaultPrevented || presenting) return;
    if (!document.body.classList.contains('file-viewer-covers') || ui.panel.contains(event.target)) return;
    if (document.querySelector('dialog[open]')) return;
    close();
  });
  window.addEventListener('consensio:auth-state', () => close({ focus: false }));
  // The activity panel or the workspace opened in the preview's lane would
  // open beneath it, unseen: the preview gives them the place.
  if (typeof MutationObserver === 'function') {
    const lanesNow = () => ['agent-sidebar-open', 'workspace-view-docked', 'answer-reader-docked']
      .filter(name => document.body.classList.contains(name));
    let lanes = lanesNow();
    new MutationObserver(() => {
      if (!document?.body) return;
      const now = lanesNow();
      const opened = now.some(name => !lanes.includes(name));
      lanes = now;
      if (opened && view && document.body.classList.contains('file-viewer-docked')) close({ focus: false });
    }).observe(document.body, { attributes: true, attributeFilter: ['class'] });
    // The app's sidebar opening or folding changes the room beside the
    // preview (--app-sidebar-offset), not the window.
    const sidebar = document.querySelector('.sidebar');
    if (sidebar) {
      new MutationObserver(() => { if (view) onWindowResize(); })
        .observe(sidebar, { attributes: true, attributeFilter: ['class'] });
    }
  }

  function loadingSheet(described) {
    const sheet = node('div', `file-viewer-skeleton${described.view === 'pdf' ? '' : ' is-text'}`);
    sheet.setAttribute('role', 'status');
    sheet.append(node('span', 'file-viewer-skeleton-label', 'Loading preview…'));
    return sheet;
  }
  function notice(message, { retry = false } = {}) {
    const box = node('div', 'file-viewer-notice');
    box.setAttribute('role', 'status');
    const mark = node('span', 'file-viewer-notice-glyph');
    mark.append(icon(glyphFor(view?.described || { family: 'other' })));
    box.append(mark, node('p', '', message));
    const actions = node('div', 'file-viewer-notice-actions');
    if (retry) {
      const again = node('button', 'btn file-viewer-notice-button', 'Try again');
      again.type = 'button';
      again.addEventListener('click', () => { if (view) { bodies.delete(view.item.key); documents.delete(view.item.key); open({ ...view.item, trigger: view.trigger }); } });
      actions.append(again);
    }
    const first = view?.item.downloads?.[0];
    if (first) {
      const get = node('button', 'btn file-viewer-notice-button', 'Download');
      get.type = 'button';
      get.addEventListener('click', () => runDownload(first, get));
      actions.append(get);
    }
    if (actions.childElementCount) box.append(actions);
    return box;
  }

  async function show(current) {
    const { item, described } = current;
    try {
      if (described.view === 'pdf') {
        try {
          await showPdf(current, await pdfDocument(item));
          return;
        } catch (error) {
          if (!error?.loaded) throw error;
          // A Word file the user sent comes as its text (routers/agent_files.py).
          if (current !== view) return;
          if (error.loaded.mime === 'text/plain') return showText(current, await textOf(error.loaded.blob), 'document');
          ui.pages.replaceChildren(notice('There is no preview of this file. Download it to open it.'));
          return;
        }
      }
      const loaded = await body(item);
      if (current !== view) return;
      if (loaded.mime === 'application/pdf') return showPdf(current, await pdfDocument(item));
      if (loaded.blob.size > TEXT_BYTES) {
        ui.pages.replaceChildren(notice('This file is too large to preview. Download it to open it.'));
        return;
      }
      const text = await textOf(loaded.blob);
      if (current !== view) return;
      showText(current, text, described.view);
    } catch (failure) {
      if (current !== view) return;
      const unreadable = failure?.notText === true;
      ui.pages.replaceChildren(unreadable
        ? notice('There is no preview of this file. Download it to open it.')
        : notice(App.userError?.(failure, { fallback: 'The preview could not be loaded.' }) || 'The preview could not be loaded.',
          { retry: true }));
    }
  }

  // ---- PDF: pages and thumbnails -------------------------------------------------
  async function showPdf(current, doc) {
    if (current !== view) return;
    const first = await doc.getPage(1);
    if (current !== view) return;
    const base = first.getViewport({ scale: 1 });
    current.kind = 'pdf';
    current.doc = doc;
    current.count = doc.numPages;
    const family = current.described.family;
    // A landscape PDF is a deck (an exported presentation): it can be presented.
    current.slides = family === 'presentation' || (family === 'pdf' && base.width > base.height);
    current.unit = family === 'spreadsheet' ? 'spreadsheet' : current.slides ? 'presentation' : 'page';
    ui.present.hidden = !current.slides;
    ui.zoom.parentElement.hidden = false;
    ui.railCount.textContent = countText(current.unit, current.count);
    const pages = [];
    const thumbs = [];
    for (let number = 1; number <= current.count; number++) {
      const entry = { number, width: base.width, height: base.height, page: number === 1 ? first : null, drawn: 0 };
      entry.el = node('div', 'file-viewer-page');
      entry.el.dataset.page = String(number);
      entry.el.setAttribute('role', 'img');
      entry.el.setAttribute('aria-label', `${pageName(current.unit, number)} of ${current.count}`);
      pages.push(entry.el);
      const li = node('li', 'file-viewer-thumb-item');
      entry.thumb = node('button', 'file-viewer-thumb');
      entry.thumb.type = 'button';
      entry.thumb.setAttribute('aria-label', pageName(current.unit, number));
      entry.thumb.dataset.page = String(number);
      entry.thumbFrame = node('span', 'file-viewer-thumb-frame');
      entry.thumb.append(node('span', 'file-viewer-thumb-number', String(number)), entry.thumbFrame);
      entry.thumb.addEventListener('click', () => goTo(number, { focus: false }));
      li.append(entry.thumb);
      thumbs.push(li);
      current.entries.push(entry);
    }
    ui.pages.replaceChildren(...pages);
    ui.thumbs.replaceChildren(...thumbs);
    syncRail();
    sizePages();
    watchPages(current);
    setActive(1);
  }
  function stagePad() {
    return Number.parseFloat(getComputedStyle(ui.stage).paddingTop) || PAD;
  }
  function stageRoom() {
    const pad = stagePad();
    return { width: ui.stage.clientWidth - 2 * pad, height: ui.stage.clientHeight - 2 * pad };
  }
  function cssWidth(entry) {
    if (view.zoom !== 'fit') return Math.round(entry.width * CSS_PER_POINT * view.zoom);
    const room = stageRoom();
    const aspect = entry.width / entry.height;
    // A slide shows whole; a document's page fills the width up to a readable size.
    const width = aspect >= 1 ? Math.min(room.width, room.height * aspect) : Math.min(room.width, FIT_PORTRAIT_MAX);
    return Math.max(120, Math.floor(width));
  }
  function sizePages() {
    if (!view || view.kind !== 'pdf') return;
    for (const entry of view.entries) {
      entry.css = cssWidth(entry);
      entry.el.style.width = `${entry.css}px`;
      entry.el.style.height = `${Math.round(entry.css * entry.height / entry.width)}px`;
      const thumbWidth = thumbWidthNow();
      entry.thumbFrame.style.width = `${thumbWidth}px`;
      entry.thumbFrame.style.height = `${Math.round(thumbWidth * Math.min(1.42, entry.height / entry.width))}px`;
    }
  }
  // Resize, zoom, a rail shown or hidden: the pages take their new size and
  // the ones on the screen are drawn again, sharp; the page in view stays.
  // Drawing waits until the size rests (a drag, a window being resized): in
  // between the drawn pages only scale.
  let drawTimer = 0;
  function relayout() {
    if (!view || view.kind !== 'pdf') return;
    const keep = view.active;
    sizePages();
    goTo(keep, { behavior: 'auto', focus: false, quiet: true });
    clearTimeout(drawTimer);
    if (document.body.classList.contains('file-viewer-resizing')) return;
    const current = view;
    drawTimer = setTimeout(() => {
      if (current !== view) return;
      for (const entry of current.entries) if (entry.near) drawEntry(current, entry);
    }, 120);
  }
  function watchPages(current) {
    current.observer = new IntersectionObserver(items => {
      if (current !== view) return;
      for (const item of items) {
        const entry = current.entries[Number(item.target.dataset.page) - 1];
        if (!entry) continue;
        entry.near = item.isIntersecting;
        if (entry.near) drawEntry(current, entry);
        else releaseEntry(entry);
      }
    }, { root: ui.stage, rootMargin: '100% 0px' });
    current.thumbObserver = new IntersectionObserver(items => {
      if (current !== view) return;
      for (const item of items) {
        if (!item.isIntersecting) continue;
        const entry = current.entries[Number(item.target.dataset.page) - 1];
        if (entry && !entry.thumbDrawn) drawThumb(current, entry);
      }
    }, { root: ui.thumbs, rootMargin: '200px 0px' });
    for (const entry of current.entries) {
      current.observer.observe(entry.el);
      current.thumbObserver.observe(entry.thumb);
    }
    ui.stage.onscroll = () => {
      if (current !== view || current.scrolling) return;
      cancelAnimationFrame(current.scrollFrame);
      current.scrollFrame = requestAnimationFrame(() => setActive(pageAtTop()));
    };
  }
  // The page that holds the middle of the stage, or the last one at the end.
  function pageAtTop() {
    const stage = ui.stage;
    if (stage.scrollTop + stage.clientHeight >= stage.scrollHeight - 2) return view.count;
    const middle = stage.scrollTop + stage.clientHeight / 2;
    let best = 1;
    for (const entry of view.entries) {
      if (entry.el.offsetTop <= middle) best = entry.number; else break;
    }
    return best;
  }
  async function pageOf(current, entry) {
    if (!entry.page) {
      entry.page = await current.doc.getPage(entry.number);
      const base = entry.page.getViewport({ scale: 1 });
      if (Math.abs(base.width - entry.width) > .5 || Math.abs(base.height - entry.height) > .5) {
        entry.width = base.width;
        entry.height = base.height;
        if (current === view) sizePages();
      }
    }
    return entry.page;
  }
  async function drawEntry(current, entry) {
    let width = entry.css;
    if (!width || entry.drawn === width || entry.drawing === width) return;
    entry.drawing = width;
    entry.task?.cancel();
    try {
      const page = await pageOf(current, entry);
      if (current !== view || entry.drawing !== width) return;
      // Its own size, known only now, may have changed the width.
      width = entry.drawing = entry.css;
      const canvas = await drawPage(page, width, task => { entry.task = task; });
      if (current !== view || entry.drawing !== width) return;
      entry.el.replaceChildren(canvas);
      entry.el.classList.add('is-drawn');
      entry.drawn = width;
    } catch (error) {
      if (!cancelled(error) && current === view) entry.el.classList.add('is-failed');
    } finally {
      if (entry.drawing === width) entry.drawing = 0;
    }
  }
  // Out of reach of the screen a page gives its pixels back (a 50-page
  // document at full width kept almost a gigabyte, and an iPhone drew later
  // pages blank): an empty canvas first, which frees its memory at once.
  function freeCanvases(element) {
    for (const canvas of element.querySelectorAll('canvas')) { canvas.width = 0; canvas.height = 0; }
  }
  function releaseEntry(entry) {
    entry.task?.cancel();
    entry.drawing = 0;
    if (entry.drawn || entry.el.classList.contains('is-drawn')) {
      freeCanvases(entry.el);
      entry.el.replaceChildren();
      entry.el.classList.remove('is-drawn');
      entry.drawn = 0;
    }
    entry.page?.cleanup?.();
  }
  async function drawThumb(current, entry) {
    entry.thumbDrawn = true;
    try {
      const page = await pageOf(current, entry);
      if (current !== view) return;
      const canvas = await drawPage(page, thumbWidthNow(), task => { entry.thumbTask = task; });
      if (current !== view) return;
      entry.thumbFrame.replaceChildren(canvas);
      entry.thumbFrame.classList.add('is-drawn');
    } catch (error) {
      if (!cancelled(error)) entry.thumbDrawn = false;
    }
  }
  function setActive(number) {
    if (!view || view.kind !== 'pdf') return;
    view.active = Math.min(view.count, Math.max(1, number));
    ui.count.textContent = view.count > 1 ? `${view.active} / ${view.count}` : '';
    for (const entry of view.entries) {
      if (entry.number === view.active) entry.thumb.setAttribute('aria-current', 'true');
      else entry.thumb.removeAttribute('aria-current');
    }
    // The rail follows on its own, never the page.
    const thumb = view.entries[view.active - 1]?.thumb;
    const list = ui.thumbs;
    if (thumb && !ui.rail.hidden) {
      const top = thumb.offsetTop - list.offsetTop;
      if (top < list.scrollTop + 8) list.scrollTop = Math.max(0, top - 8);
      else if (top + thumb.offsetHeight > list.scrollTop + list.clientHeight - 8) {
        list.scrollTop = top + thumb.offsetHeight - list.clientHeight + 8;
      }
    }
  }
  function goTo(number, { behavior, focus = true, quiet = false } = {}) {
    if (!view || view.kind !== 'pdf') return;
    const target = view.entries[Math.min(view.count, Math.max(1, number)) - 1];
    if (!target) return;
    const current = view;
    current.scrolling = true;
    ui.stage.scrollTo({ top: Math.max(0, target.el.offsetTop - stagePad()),
      behavior: behavior || (reduced() ? 'auto' : 'smooth') });
    clearTimeout(current.scrollTimer);
    current.scrollTimer = setTimeout(() => { current.scrolling = false; }, behavior === 'auto' ? 0 : 400);
    setActive(target.number);
    if (!quiet && focus) ui.stage.focus({ preventScroll: true });
  }
  function setZoom(level) {
    if (!view || view.kind !== 'pdf') return;
    view.zoom = level === 'fit' ? 'fit' : Number(level);
    ui.zoomLabel.textContent = view.zoom === 'fit' ? 'Fit' : `${Math.round(view.zoom * 100)}%`;
    relayout();
  }
  function stepZoom(step) {
    if (!view || view.kind !== 'pdf') return;
    const now = view.zoom === 'fit' ? (view.entries[0].css / (view.entries[0].width * CSS_PER_POINT)) : view.zoom;
    const next = step > 0 ? ZOOMS.find(level => level > now + .01) : [...ZOOMS].reverse().find(level => level < now - .01);
    if (next) setZoom(next);
  }
  function onStageKey(event) {
    if (!view || view.kind !== 'pdf' || event.altKey || event.ctrlKey || event.metaKey) return;
    const steps = { ArrowRight: 1, PageDown: 1, ArrowLeft: -1, PageUp: -1 };
    if (view.slides) { steps.ArrowDown = 1; steps.ArrowUp = -1; steps[' '] = event.shiftKey ? -1 : 1; }
    if (event.key in steps) { event.preventDefault(); goTo(view.active + steps[event.key]); }
    else if (event.key === 'Home') { event.preventDefault(); goTo(1); }
    else if (event.key === 'End') { event.preventDefault(); goTo(view.count); }
    else if (event.key === '+' || event.key === '=') { event.preventDefault(); stepZoom(1); }
    else if (event.key === '-') { event.preventDefault(); stepZoom(-1); }
    else if (event.key === '0') { event.preventDefault(); setZoom('fit'); }
  }

  // ---- Presenting a deck -----------------------------------------------------------
  let presenting = null;
  function startPresenting() {
    if (!view || view.kind !== 'pdf' || presenting) return;
    const current = view;
    const stage = node('div', 'file-viewer-present');
    stage.setAttribute('role', 'dialog');
    stage.setAttribute('aria-label', 'Presentation');
    stage.tabIndex = -1;
    const slide = node('div', 'file-viewer-present-slide');
    const counter = node('span', 'file-viewer-present-count');
    counter.setAttribute('aria-live', 'polite');
    counter.dataset.i18nSkip = '';
    const end = node('button', 'file-viewer-present-end', 'End presentation');
    end.type = 'button';
    end.addEventListener('click', event => { event.stopPropagation(); stopPresenting(); });
    stage.append(slide, counter, end);
    presenting = { stage, slide, counter, index: current.active, current, drawToken: 0 };
    const draw = async () => {
      const state = presenting;
      if (!state) return;
      const token = ++state.drawToken;
      counter.textContent = `${state.index} / ${current.count}`;
      const entry = current.entries[state.index - 1];
      try {
        const page = await pageOf(current, entry);
        const room = { width: stage.clientWidth, height: stage.clientHeight };
        const aspect = entry.width / entry.height;
        const width = Math.floor(Math.min(room.width, room.height * aspect));
        const canvas = await drawPage(page, width);
        if (presenting !== state || token !== state.drawToken) return;
        canvas.style.width = `${width}px`;
        canvas.style.height = `${Math.floor(width / aspect)}px`;
        slide.replaceChildren(canvas);
      } catch (error) { /* The slide stays as it was. */ }
    };
    const step = by => {
      const next = Math.min(current.count, Math.max(1, presenting.index + by));
      if (next === presenting.index) return;
      presenting.index = next;
      draw();
    };
    presenting.step = step;
    presenting.draw = draw;
    stage.addEventListener('keydown', event => {
      if ((event.key === 'Enter' || event.key === ' ') && event.target.closest?.('button')) return;
      const forward = ['ArrowRight', 'ArrowDown', 'PageDown', ' ', 'Enter'];
      const back = ['ArrowLeft', 'ArrowUp', 'PageUp', 'Backspace'];
      if (forward.includes(event.key)) { event.preventDefault(); step(1); }
      else if (back.includes(event.key)) { event.preventDefault(); step(-1); }
      else if (event.key === 'Home') { event.preventDefault(); presenting.index = 1; draw(); }
      else if (event.key === 'End') { event.preventDefault(); presenting.index = current.count; draw(); }
      else if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); stopPresenting(); }
    });
    // A click goes on, on the left third back.
    stage.addEventListener('click', event => step(event.clientX < stage.clientWidth / 3 ? -1 : 1));
    ui.panel.append(stage);
    stage.focus({ preventScroll: true });
    const full = stage.requestFullscreen?.({ navigationUI: 'hide' });
    if (full?.catch) full.catch(() => {});
    presenting.onResize = () => draw();
    window.addEventListener('resize', presenting.onResize);
    draw();
    track('app_file_preview_presented', { pages: current.count });
  }
  function stopPresenting() {
    if (!presenting) return;
    const state = presenting;
    presenting = null;
    window.removeEventListener('resize', state.onResize);
    if (document.fullscreenElement === state.stage) document.exitFullscreen?.().catch?.(() => {});
    state.stage.remove();
    if (state.current === view) {
      goTo(state.index, { behavior: 'auto', focus: false });
      ui.present.focus({ preventScroll: true });
    }
  }
  document.addEventListener('fullscreenchange', () => {
    if (presenting && document.fullscreenElement !== presenting.stage) stopPresenting();
  });

  // ---- Code, text, Markdown, tables ------------------------------------------------
  function showText(current, text, how) {
    if (current !== view) return;
    current.kind = 'text';
    ui.stage.classList.add('is-text');
    syncRail();
    let content;
    if (how === 'markdown' && typeof window.renderMarkdownFragment === 'function') {
      // The answer's own renderer (markdown-stream.js): its sanitizer, and
      // nothing of the file loads by itself (a remote picture is a note).
      content = node('article', 'file-viewer-sheet file-viewer-markdown');
      content.append(window.renderMarkdownFragment(text));
      window.addNewTabToLinks?.(content);
    } else if (how === 'table') {
      content = table(text, /\.tsv$/i.test(current.item.name) ? '\t' : null);
    } else if (how === 'document') {
      content = node('article', 'file-viewer-sheet file-viewer-document');
      for (const paragraph of text.split(/\n{2,}/)) content.append(node('p', '', paragraph));
    } else if (how === 'code') {
      content = code(text);
    } else {
      content = node('pre', 'file-viewer-plain');
      content.textContent = text;
    }
    // The file's words are its own; the notes around them are the app's.
    content.dataset.i18nSkip = '';
    const notes = [];
    if (how === 'document') notes.push(node('p', 'file-viewer-sheet-note', 'Text only. Download the file for its layout.'));
    if (content._cut) notes.push(node('p', 'file-viewer-sheet-note', `Showing the first ${MAX_LINES} lines. Download the file for the rest.`));
    if (content._rowsCut) notes.push(node('p', 'file-viewer-sheet-note', `Showing the first ${MAX_ROWS} rows. Download the file for the rest.`));
    ui.pages.replaceChildren(...notes, content);
    const lines = content._lines ?? (text ? text.split('\n').length : 0);
    const counted = how === 'code' || how === 'text';
    ui.count.textContent = counted ? (lines === 1 ? '1 line' : `${lines} lines`) : '';
    ui.count.toggleAttribute('data-i18n-skip', !counted);
  }
  function code(text) {
    let lines = text.replace(/\r\n?/g, '\n').split('\n');
    if (lines.length > 1 && lines[lines.length - 1] === '') lines.pop();
    const total = lines.length;
    const cut = total > MAX_LINES;
    if (cut) lines = lines.slice(0, MAX_LINES);
    const wrap = node('div', 'file-viewer-code');
    const gutter = node('pre', 'file-viewer-gutter');
    gutter.setAttribute('aria-hidden', 'true');
    gutter.textContent = lines.map((_, index) => index + 1).join('\n');
    const source = node('pre', 'file-viewer-source');
    source.tabIndex = 0;
    source.textContent = lines.join('\n');
    wrap.append(gutter, source);
    wrap._cut = cut;
    wrap._lines = total;
    return wrap;
  }
  // A small CSV reader: quoted fields, doubled quotes, commas or semicolons.
  function rows(text, separator) {
    const sep = separator || ((text.split('\n')[0].match(/;/g) || []).length > (text.split('\n')[0].match(/,/g) || []).length ? ';' : ',');
    const out = [];
    let row = [], field = '', quoted = false;
    for (let i = 0; i < text.length; i++) {
      const char = text[i];
      if (quoted) {
        if (char === '"' && text[i + 1] === '"') { field += '"'; i++; }
        else if (char === '"') quoted = false;
        else field += char;
      } else if (char === '"' && field === '') quoted = true;
      else if (char === sep) { row.push(field); field = ''; }
      else if (char === '\n' || char === '\r') {
        if (char === '\r' && text[i + 1] === '\n') i++;
        row.push(field); out.push(row); row = []; field = '';
        if (out.length > MAX_ROWS) {
          out.cut = /\S/.test(text.slice(i + 1));
          break;
        }
      } else field += char;
    }
    if (field || row.length) { row.push(field); out.push(row); }
    return out;
  }
  function table(text, separator) {
    const read = rows(text, separator);
    const all = read.filter(row => row.some(cell => cell.trim()));
    const wrap = node('div', 'file-viewer-table-wrap');
    wrap.tabIndex = 0;
    const grid = node('table', 'file-viewer-table');
    const [head, ...rest] = all;
    if (head) {
      const thead = node('thead');
      const tr = node('tr');
      tr.append(node('th', 'file-viewer-row-number', ''));
      for (const cell of head) tr.append(node('th', '', cell));
      thead.append(tr);
      grid.append(thead);
    }
    const tbody = node('tbody');
    rest.slice(0, MAX_ROWS).forEach((row, index) => {
      const tr = node('tr');
      tr.append(node('td', 'file-viewer-row-number', String(index + 2)));
      for (const cell of row) tr.append(node('td', '', cell));
      tbody.append(tr);
    });
    grid.append(tbody);
    wrap.append(grid);
    wrap._rowsCut = Boolean(read.cut) || rest.length > MAX_ROWS;
    return wrap;
  }

  App.fileViewer = {
    open, close, describe, previews, thumbnail, countText,
    isOpen: () => Boolean(view),
  };
})();
