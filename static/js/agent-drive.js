// Google Drive as a file source for Agent chats ((+) menu, "Add from Google
// Drive"). Google's own picker shows the user's Drive; the browser fetches each
// picked file with a short-lived token that only reaches files picked here
// (drive.file) and hands it to the composer as an ordinary attachment
// (attachments.js addRemote). Nothing about Drive is stored: no grant on the
// server, no token beyond this page's memory.
//
// A Drive file is Google data: the attachment carries its origin, the upload
// names it, and the chat then follows the Google rules (agent-google.js asks
// for consent once per chat; the server routes every model call with zero
// data retention and turns web search off).
(() => {
  const App = window.App = window.App || {};
  const GIS_SRC = 'https://accounts.google.com/gsi/client';
  const GAPI_SRC = 'https://apis.google.com/js/api.js';
  const SCOPE = 'https://www.googleapis.com/auth/drive.file';
  const DOCX = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
  const MAX_BYTES = 5 * 1024 * 1024, IMAGE_MAX_BYTES = 15 * 1024 * 1024;
  // Google's own formats leave Drive in the closest format Consens reads:
  // Docs keep headings and tables as Word, Sheets give their first sheet as
  // CSV, Slides become a PDF.
  const EXPORTS = {
    'application/vnd.google-apps.document': {mime: DOCX, ext: 'docx'},
    'application/vnd.google-apps.spreadsheet': {mime: 'text/csv', ext: 'csv'},
    'application/vnd.google-apps.presentation': {mime: 'application/pdf', ext: 'pdf'},
  };
  const FILES = ['application/pdf', DOCX, 'text/plain', 'text/markdown', 'text/csv', 'image/png', 'image/jpeg', 'image/webp'];

  let settings = null, scripts = null, token = null, tokenClient = null, tokenClientId = '';

  function option() { return document.getElementById('attachDriveOption'); }
  function uid() { return window.auth?.currentUser?.uid || ''; }
  function popup(message) { App.showPopup?.(message); }
  function slots() {
    const max = Number(App.attachments?.maxFiles) || 2;
    return max - (window.pendingAttachments || []).length;
  }

  // ---- Visibility: Agent chats on installations with a picker -----------
  function sync() {
    const el = option();
    if (!el) return;
    const show = Boolean(App.agentGoogle?.agentActive?.() && App.agentGoogle?.knownDrive?.());
    if (el.hidden === show) el.hidden = !show;
  }
  async function refresh() {
    sync();
    if (!App.agentGoogle?.agentActive?.()) return;
    try {
      const current = await App.agentGoogle.config();
      settings = current?.drive || null;
    } catch (_) { settings = null; }
    sync();
    if (settings) prepare().catch(() => {});
  }

  // ---- Google's scripts, loaded on first need ----------------------------
  function script(src) {
    return new Promise((resolve, reject) => {
      const existing = document.querySelector(`script[src="${src}"]`);
      if (existing?.dataset.loaded === 'true') { resolve(); return; }
      const el = existing || document.createElement('script');
      el.addEventListener('load', () => { el.dataset.loaded = 'true'; resolve(); }, {once: true});
      el.addEventListener('error', () => reject(new Error('Google Drive could not be loaded. Check your connection and try again.')), {once: true});
      if (!existing) { el.src = src; el.async = true; document.head.append(el); }
    });
  }
  function prepare() {
    if (!scripts) {
      scripts = Promise.all([
        script(GIS_SRC),
        script(GAPI_SRC).then(() => new Promise((resolve, reject) => {
          window.gapi.load('picker', {callback: resolve, onerror: () => reject(new Error('Google Drive could not be loaded. Please try again.'))});
        })),
      ]).catch(error => { scripts = null; throw error; });
    }
    return scripts;
  }
  function ready() { return Boolean(window.google?.accounts?.oauth2 && window.google?.picker?.PickerBuilder); }

  // ---- Short-lived access, only for files picked here --------------------
  function validToken() {
    return token && token.uid === uid() && token.until > Date.now() + 60000 ? token.value : '';
  }
  // Must run inside the click: Google opens its consent window from here.
  function requestToken(config, after) {
    if (!tokenClient || tokenClientId !== config.client_id) {
      tokenClientId = config.client_id;
      tokenClient = window.google.accounts.oauth2.initTokenClient({
        client_id: config.client_id, scope: SCOPE, callback: () => {},
        error_callback: error => {
          if (error?.type === 'popup_failed_to_open') popup('Allow the Google window to open, then try again.');
        },
      });
    }
    const owner = uid();
    tokenClient.callback = response => {
      if (owner !== uid()) return;
      if (response?.error || !response?.access_token
          || !window.google.accounts.oauth2.hasGrantedAllScopes(response, SCOPE)) {
        popup('Google Drive access was not granted. No files were added.');
        return;
      }
      token = {value: response.access_token, uid: owner, until: Date.now() + Math.min(Number(response.expires_in) || 3600, 3600) * 1000};
      after(token.value);
    };
    tokenClient.requestAccessToken({prompt: ''});
  }

  // ---- Picker and download ---------------------------------------------
  function openPicker(config, accessToken) {
    const picker = window.google.picker;
    const free = slots();
    if (free <= 0) { popup(`You can attach up to ${Number(App.attachments?.maxFiles) || 2} files per question.`); return; }
    const view = new picker.DocsView(picker.ViewId.DOCS)
      .setMimeTypes([...FILES, ...Object.keys(EXPORTS)].join(','))
      .setIncludeFolders(true).setSelectFolderEnabled(false)
      .setMode(picker.DocsViewMode.LIST);
    let builder = new picker.PickerBuilder()
      .addView(view)
      .setOAuthToken(accessToken)
      .setDeveloperKey(config.api_key)
      .setAppId(config.app_id)
      .setOrigin(location.origin)
      .setTitle('Choose files from Google Drive')
      .setCallback(data => picked(data, accessToken));
    if (free > 1) builder = builder.enableFeature(picker.Feature.MULTISELECT_ENABLED).setMaxItems(free);
    builder.build().setVisible(true);
  }
  function picked(data, accessToken) {
    const picker = window.google.picker;
    if (data?.[picker.Response.ACTION] !== picker.Action.PICKED) return;
    for (const doc of data[picker.Response.DOCUMENTS] || []) {
      const id = String(doc[picker.Document.ID] || ''), mime = String(doc[picker.Document.MIME_TYPE] || '');
      const exported = EXPORTS[mime] || null;
      const title = String(doc[picker.Document.NAME] || 'Drive file').slice(0, 180);
      // Google's own formats have titles, not file names.
      const name = exported ? `${title}.${exported.ext}` : title;
      if (!/^[A-Za-z0-9_-]{10,200}$/.test(id)) continue;
      const item = {id, name, mime: exported ? exported.mime : mime, size: exported ? 0 : Number(doc.sizeBytes) || 0, exported};
      App.attachments?.addRemote?.({name, mime: item.mime, size: item.size, source: 'drive',
        origin: {source: 'google_drive', file_id: id}}, () => download(item, accessToken));
    }
  }
  async function download(item, accessToken) {
    const limit = item.mime.startsWith('image/') ? IMAGE_MAX_BYTES : MAX_BYTES;
    const megabytes = Math.round(limit / (1024 * 1024));
    if (item.size > limit) throw new Error(`'${item.name}' is larger than ${megabytes} MB, the limit per file.`);
    const base = `https://www.googleapis.com/drive/v3/files/${encodeURIComponent(item.id)}`;
    const url = item.exported ? `${base}/export?mimeType=${encodeURIComponent(item.exported.mime)}` : `${base}?alt=media&supportsAllDrives=true`;
    const response = await fetch(url, {headers: {Authorization: `Bearer ${accessToken}`}, credentials: 'omit', referrerPolicy: 'no-referrer'});
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      const reason = body?.error?.errors?.[0]?.reason || '';
      if (response.status === 401) { token = null; throw new Error('Google Drive access expired. Add the file again.'); }
      if (reason === 'exportSizeLimitExceeded') throw new Error(`'${item.name}' is too large to export from Google Drive. Split it or save a smaller copy.`);
      if (response.status === 403 || response.status === 404) throw new Error(`Google Drive did not allow reading '${item.name}'.`);
      throw new Error(`'${item.name}' could not be loaded from Google Drive. Please try again.`);
    }
    const blob = await response.blob();
    if (blob.size > limit) throw new Error(`'${item.name}' is larger than ${megabytes} MB, the limit per file.`);
    return new File([blob], item.name, {type: item.mime || blob.type});
  }

  function choose(event) {
    event.stopPropagation();
    App.closeAttachMenu?.();
    if (!uid()) { popup('Sign in to add files.'); return; }
    if (slots() <= 0) { popup(`You can attach up to ${Number(App.attachments?.maxFiles) || 2} files per question.`); return; }
    const config = settings;
    if (!config || !ready()) {
      popup('Google Drive is still loading. Try again in a moment.');
      refresh();
      return;
    }
    const current = validToken();
    if (current) openPicker(config, current);
    else requestToken(config, value => openPicker(config, value));
  }

  function init() {
    option()?.addEventListener('click', choose);
    // The (+) menu is where Drive shows up: learn on its first opening
    // whether this installation offers it.
    // Only a click that leaves the menu open counts (the same button closes it).
    document.addEventListener('click', event => {
      if (!event.target.closest?.('#attachTrigger')) return;
      setTimeout(() => { if (document.getElementById('attachMenu')?.hidden === false) refresh(); }, 0);
    }, true);
    sync();
  }
  window.addEventListener('consensio:auth-state', () => { token = null; settings = null; sync(); });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();

  App.agentDrive = {refresh, sync, exports: EXPORTS};
})();
