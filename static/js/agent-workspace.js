// Private resources belong to the current authenticated chat, never localStorage.
(() => {
  const App = window.App = window.App || {};
  let owner = '', chat = '', generation = 0, loaded = '', controller = null;
  function host() {
    let panel = document.getElementById('agentWorkspace');
    if (!panel) {
      const answer = document.getElementById('agentAnswer');
      if (!answer) return null;
      panel = document.createElement('section'); panel.id = 'agentWorkspace';
      panel.className = 'agent-workspace'; panel.setAttribute('aria-label', 'Chat files and results');
      answer.before(panel);
    }
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
      const error = await response.json().catch(() => ({}));
      throw new Error(typeof error.detail === 'string' ? error.detail : error.error || 'The file request failed. Please retry.');
    }
    return response;
  }
  function button(label, action) {
    const node = document.createElement('button'); node.type = 'button'; node.textContent = label;
    node.className = 'settings-inline-btn';
    node.addEventListener('click', async () => {
      node.disabled = true;
      try { await action(); } catch (error) { App.showPopup?.(error.message); }
      finally { node.disabled = false; }
    });
    return node;
  }
  async function download(chatId, file) {
    const response = await request(`/agent/chats/${chatId}/files/${file.id}`);
    const blob = await response.blob();
    const url = URL.createObjectURL(blob), link = document.createElement('a');
    link.href = url; link.download = file.name; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
  }
  async function refresh(chatId, force = false) {
    const panel = host(), uid = window.auth?.currentUser?.uid || '';
    if (!panel) return;
    if (!chatId || !uid || !App.agentChat?.isSelected()) {
      generation++; controller?.abort(); loaded = ''; chat = ''; panel.replaceChildren(); panel.hidden = true; return;
    }
    const key = `${uid}:${chatId}`;
    panel.hidden = false;
    if (loaded === key && !force) return;
    owner = uid; chat = chatId; loaded = key;
    controller?.abort(); controller = new AbortController(); const seq = ++generation;
    panel.textContent = 'Loading chat files…';
    try {
      const response = await request(`/agent/chats/${chatId}/files`, { signal: controller.signal });
      const data = await response.json();
      if (seq !== generation || owner !== window.auth?.currentUser?.uid) return;
      panel.replaceChildren(); panel.hidden = !data.files?.length;
      if (!data.files?.length) return;
      const details = document.createElement('details'), summary = document.createElement('summary');
      summary.textContent = `Files in this chat (${data.files.length})`;
      details.append(summary);
      const notice = document.createElement('p');
      notice.textContent = 'Files remain available for follow-up questions for 30 days. Relevant excerpts may be sent to your selected models.';
      details.append(notice);
      for (const file of data.files) {
        const row = document.createElement('div'); row.className = 'agent-file-card';
        const title = document.createElement('strong'); title.textContent = file.name;
        const status = document.createElement('span'); status.textContent = ` · ${file.status}${file.version ? ` · version ${file.version}` : ''}`;
        row.append(title, status);
        for (const warning of file.warnings || []) { const text = document.createElement('p'); text.textContent = warning; row.append(text); }
        row.append(button('Download', () => download(chatId, file)));
        row.append(button('Remove', async () => {
          await request(`/agent/chats/${chatId}/files/${file.id}`, { method: 'DELETE' });
          if (chat === chatId) await refresh(chatId, true);
        }));
        details.append(row);
      }
      panel.append(details);
    } catch (error) {
      if (seq !== generation || error.name === 'AbortError') return;
      loaded = ''; panel.textContent = error.message;
      panel.append(button('Retry', () => refresh(chatId, true)));
    }
  }
  async function upload(context, headers, signal) {
    const result = [];
    for (const file of context.attachments || []) {
      if (!App.runRegistry.isAuthCurrent(context) || signal.aborted) throw new DOMException('Stopped', 'AbortError');
      context.consensus.error = null;
      const panel = host(); if (panel) { panel.hidden = false; panel.textContent = `Processing ${file.name}…`; }
      const response = await request(`/agent/chats/${context.metadata.chatId}/files`, {
        method: 'POST', signal, headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: file.name, data: file.data }) });
      const data = await response.json();
      if (!App.runRegistry.isAuthCurrent(context) || signal.aborted) throw new DOMException('Stopped', 'AbortError');
      result.push(data.file);
    }
    context.metadata.fileIds = result.map(file => file.id);
    context.attachmentMeta = result;
    context.attachments = []; // Bytes never belong in saved turns or bookmarks.
    if (result.length) { window.clearPendingAttachments?.(); await refresh(context.metadata.chatId, true); }
    return result;
  }
  window.addEventListener('consensio:auth-state', () => { generation++; controller?.abort(); loaded = ''; host()?.replaceChildren(); });
  App.agentWorkspace = { refresh, upload, request, button, download };
})();
