import { describe, it, expect, vi } from 'vitest';
import { loadScripts } from './helpers/appWindow.mjs';

const CHAT = 'b'.repeat(32);
const DOC = 'd'.repeat(32);
const TURN_ONE = '1'.repeat(32), TURN_TWO = '2'.repeat(32);
const ANSWER = '<section id="agentAnswer"><div id="agentAnswerActivity"></div><div id="agentAnswerBody"></div><p id="agentAnswerError" hidden></p></section>';

function reply(files) { return { ok: true, json: async () => ({ files }) }; }
function boot({ files = [], turn = TURN_TWO, body = ANSWER } = {}) {
  const loaded = loadScripts(['static/js/agent-workspace.js'], { body, before(window) {
    window.auth = { currentUser: { uid: 'owner', getIdToken: async () => 'token' } };
    window.App = {
      agentChat: { isSelected: () => true }, showPopup: vi.fn(),
      runRegistry: { isAuthCurrent: () => true, visible: () => null, isExecuting: () => false,
        getSelectedConversationBasis: () => ({ chatId: CHAT, turnId: turn, currentTurn: { id: turn } }) },
      agentGoogle: { refreshActions: vi.fn() },
    };
    window.fetch = vi.fn(async () => reply(files));
  } });
  return loaded;
}
const version = (id, number, turn, ext, extra = {}) => ({ id: id.repeat(32), name: `Decision brief-v${number}.${ext}`, title: 'Decision brief',
  kind: 'document', document_id: DOC, version: number, parent_version: number - 1, turn_id: turn, status: 'ready',
  mime: ext === 'pdf' ? 'application/pdf' : 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  size: 41000, created_at: `2026-09-2${number}T10:00:00Z`, expires_at: '2099-10-29T10:00:00Z', ...extra });
const DOCS = [version('3', 1, TURN_ONE, 'docx'), version('4', 1, TURN_ONE, 'pdf'), version('5', 2, TURN_TWO, 'docx'), version('6', 2, TURN_TWO, 'pdf')];
const MAIL = { id: 'c'.repeat(32), name: 'invoice.pdf', mime: 'application/pdf', size: 51000, status: 'ready', kind: 'mail_attachment',
  turn_id: TURN_TWO, expires_at: '2099-10-29T10:00:00Z',
  origin: { message_id: '18c2f0a1b2c3d4e5', part_id: '1.2' }, origin_subject: 'Offer 2026', origin_from: 'Jens <jens@vendor.example>' };
const UPLOAD = { id: 'a'.repeat(32), name: 'offer.pdf', mime: 'application/pdf', size: 182000, status: 'partial', created_at: '2026-09-20T09:00:00Z',
  expires_at: '2099-10-29T10:00:00Z', warnings: ['No extractable text on pages 4. Scans require visual reading; OCR is not available.'] };

describe('private Agent workspace', () => {
  it('renders one document card per document after the answer, grouped by version and without raw IDs', async () => {
    const { window, document, dom } = boot({ files: [UPLOAD, ...DOCS] });
    await window.App.agentWorkspace.refresh(CHAT);
    const resources = document.getElementById('agentAnswerResources');
    expect(resources.previousElementSibling.id).toBe('agentAnswerBody');
    const cards = resources.querySelectorAll('.agent-doc-card');
    expect(cards).toHaveLength(1);
    const card = cards[0];
    expect(card.querySelector('.agent-doc-title > span').textContent).toBe('Decision brief');
    expect(card.textContent).toContain('Version 2 · revised from version 1');
    expect(card.querySelector('.agent-files-badge.is-new').textContent).toBe('Updated in this answer');
    expect(card.textContent).toContain('Ask for changes in the chat to create version 3.');
    expect(card.textContent).not.toContain(DOC);
    expect(card.querySelector('.agent-doc-earlier summary').textContent).toBe('Earlier versions (1)');
    expect(card.querySelector('.agent-doc-earlier').open).toBe(false);
    const labels = [...card.querySelectorAll('.agent-doc-downloads > .agent-files-chip')].map(b => b.getAttribute('aria-label'));
    expect(labels.slice(0, 2)).toEqual(['Download Decision brief-v2.docx, version 2', 'Download Decision brief-v2.pdf, version 2']);
    // Remove never sits next to Download: it lives behind the overflow menu.
    expect([...card.querySelectorAll('button')].some(b => /^Remove/.test(b.textContent) && !b.closest('[role=menu]'))).toBe(false);
    // No chat-wide list under the answer: uploads live on their message.
    expect(document.getElementById('agentWorkspace')).toBeNull();
    expect(document.body.textContent).not.toContain('Files in this chat');
    expect(resources.textContent).not.toContain('offer.pdf');
    dom.window.close();
  });

  it('shows only the documents of the displayed turn under the answer', async () => {
    const { window, document, dom } = boot({ files: DOCS, turn: TURN_ONE });
    await window.App.agentWorkspace.refresh(CHAT);
    const card = document.querySelector('#agentAnswerResources .agent-doc-card');
    expect(card.textContent).toContain('Version 1');
    expect(card.textContent).not.toContain('Version 2');
    expect(card.querySelector('.agent-doc-earlier')).toBeNull();
    const other = boot({ files: DOCS, turn: 'f'.repeat(32) });
    await other.window.App.agentWorkspace.refresh(CHAT);
    expect(other.document.getElementById('agentAnswerResources').hidden).toBe(true);
    expect(other.document.getElementById('agentWorkspace')).toBeNull();
    other.dom.window.close();
    dom.window.close();
  });

  it('removes only after an explicit confirmation from the overflow menu', async () => {
    const { window, document, dom } = boot({ files: [MAIL] });
    await window.App.agentWorkspace.refresh(CHAT);
    const more = document.querySelector('#agentAnswerResources .agent-files-more');
    expect(more.getAttribute('aria-label')).toBe('More actions for invoice.pdf');
    expect(document.querySelector('#agentAnswerResources .agent-files-icon-btn').getAttribute('aria-label')).toBe('Download invoice.pdf');
    more.click();
    expect(more.getAttribute('aria-expanded')).toBe('true');
    document.querySelector('#agentAnswerResources [role=menuitem]').click();
    expect(window.fetch).toHaveBeenCalledTimes(1);
    const confirm = document.querySelector('.agent-files-confirm');
    expect(confirm.textContent).toContain('Remove invoice.pdf? The agent can no longer use it in this chat.');
    expect(document.activeElement.textContent).toBe('Cancel');
    confirm.querySelector('.agent-files-ghost').click();
    expect(document.querySelector('.agent-files-confirm')).toBeNull();
    expect(window.fetch).toHaveBeenCalledTimes(1);
    document.querySelector('#agentAnswerResources .agent-files-more').click();
    document.querySelector('#agentAnswerResources [role=menuitem]').click();
    document.querySelector('.agent-files-danger').click();
    await vi.waitFor(() => expect(window.fetch.mock.calls.some(([, o]) => o?.method === 'DELETE')).toBe(true));
    const call = window.fetch.mock.calls.find(([, o]) => o?.method === 'DELETE');
    expect(call[0]).toBe(`/agent/chats/${CHAT}/files/${MAIL.id}`);
    dom.window.close();
  });

  it('marks partly readable files and never renders file names as markup', async () => {
    const hostile = { ...UPLOAD, name: '<img src=x onerror=alert(1)>.txt' };
    const { window, document, dom } = boot({ files: [hostile] });
    window.App.runRegistry.getSelectedConversationBasis = () => ({ chatId: CHAT, turnId: TURN_TWO,
      currentTurn: { id: TURN_TWO, agent_settings: { file_ids: [UPLOAD.id] } } });
    await window.App.agentWorkspace.refresh(CHAT);
    expect(document.querySelector('img')).toBeNull();
    const notice = document.querySelector('#agentAnswerResources .agent-resource-notice');
    expect(notice.textContent).toContain("couldn't be read");
    expect(notice.textContent).toContain('OCR is not available');
    expect(notice.textContent).toContain('<img src=x onerror=alert(1)>.txt');
    dom.window.close();
  });

  it('describes Gmail imports of the turn by subject and sender instead of message IDs', async () => {
    const { window, document, dom } = boot({ files: [MAIL, { ...MAIL, id: 'e'.repeat(32), origin_subject: undefined, origin_from: undefined,
      origin: { message_id: 'ff', part_id: '1' } }, { ...MAIL, id: '9'.repeat(32), name: 'older.pdf', turn_id: TURN_ONE }] });
    window.App.agentGoogle.evidenceFor = id => id === 'ff' ? { subject: 'Contract', from: 'Legal <legal@example.org>' } : null;
    await window.App.agentWorkspace.refresh(CHAT);
    const text = document.getElementById('agentAnswerResources').textContent;
    expect(text).not.toContain('older.pdf');
    expect(text).toContain('From email: Offer 2026 (Jens)');
    expect(text).toContain('From email: Contract (Legal)');
    expect(text).not.toContain('18c2f0a1b2c3d4e5');
    dom.window.close();
  });

  it('coalesces refreshes to one request per 300 ms and never refreshes Google actions', async () => {
    // jsdom keeps its own clock, so this runs on real (short) timers.
    const { window, dom } = boot({ files: [] });
    const workspace = window.App.agentWorkspace;
    const started = Date.now();
    const first = workspace.refresh(CHAT, true);
    const burst = [];
    for (let i = 0; i < 5; i++) burst.push(workspace.refresh(CHAT, true));
    await first;
    expect(window.fetch).toHaveBeenCalledTimes(1);
    await Promise.all(burst);
    expect(window.fetch).toHaveBeenCalledTimes(2);
    expect(Date.now() - started).toBeGreaterThanOrEqual(290);
    await new Promise(resolve => setTimeout(resolve, 400));
    expect(window.fetch).toHaveBeenCalledTimes(2);
    // A plain refresh of the same chat only re-projects the cached list.
    await workspace.refresh(CHAT);
    await new Promise(resolve => setTimeout(resolve, 350));
    expect(window.fetch).toHaveBeenCalledTimes(2);
    expect(window.App.agentGoogle.refreshActions).not.toHaveBeenCalled();
    dom.window.close();
  });

  it('keeps the list while uploading and shows a progress row per file', async () => {
    const { window, document, dom } = boot({ files: [UPLOAD] });
    await window.App.agentWorkspace.refresh(CHAT);
    let release;
    window.fetch = vi.fn((path, options) => options?.method === 'POST'
      ? new Promise(resolve => { release = () => resolve({ ok: true, json: async () => ({ file: { ...UPLOAD, id: 'f'.repeat(32), name: 'new.pdf', warnings: [] } }) }); })
      : Promise.resolve(reply([UPLOAD])));
    const context = { metadata: { chatId: CHAT }, consensus: {}, attachments: [{ name: 'new.pdf', mime: 'application/pdf', size: 10, data: 'eA==' }] };
    const pending = window.App.agentWorkspace.upload(context, {}, new AbortController().signal);
    await vi.waitFor(() => expect(typeof release).toBe('function'));
    expect(document.querySelector('#agentAnswerResources .agent-upload-row').textContent).toContain('new.pdf');
    expect(document.querySelector('#agentAnswerResources .agent-upload-row').textContent).toContain('Uploading');
    release();
    await pending;
    expect(context.metadata.fileIds).toEqual(['f'.repeat(32)]);
    expect(context.attachments).toEqual([]);
    expect(document.querySelector('.agent-upload-row')).toBeNull();
    dom.window.close();
  });

  it('keeps a failed upload in the composer with its reason', async () => {
    const { window, dom } = boot({ files: [] });
    window.App.attachments = { markError: vi.fn() };
    window.fetch = vi.fn(async (path, options) => options?.method === 'POST'
      ? { ok: false, json: async () => ({ detail: 'Page limit: 80 pages.' }) } : reply([]));
    const file = { name: 'big.pdf', mime: 'application/pdf', size: 10, data: 'eA==' };
    const context = { metadata: { chatId: CHAT }, consensus: {}, attachments: [file] };
    await expect(window.App.agentWorkspace.upload(context, {}, new AbortController().signal)).rejects.toThrow("Couldn't upload big.pdf. Page limit: 80 pages.");
    expect(window.App.attachments.markError).toHaveBeenLastCalledWith(file, 'Page limit: 80 pages.');
    expect(context.attachments).toEqual([file]);
    expect(context.metadata.uploadFailed).toBe(true);
    dom.window.close();
  });

  it('creates the answer resources hook when the template lacks it and discards an old account response', async () => {
    const { window, document, dom } = boot();
    let release; window.fetch = vi.fn(() => new Promise(resolve => { release = resolve; }));
    const loading = window.App.agentWorkspace.refresh(CHAT);
    await vi.waitFor(() => expect(typeof release).toBe('function'));
    expect(document.getElementById('agentAnswerResources')).not.toBeNull();
    window.auth.currentUser = { uid: 'other', getIdToken: async () => 'new' };
    window.dispatchEvent(new window.Event('consensio:auth-state'));
    release(reply([{ ...UPLOAD, name: 'private owner file' }]));
    await loading;
    expect(document.body.textContent).not.toContain('private owner file');
    dom.window.close();
  });

  it('keeps each archived turn\'s documents with its own answer', async () => {
    const history = '<div id="threadHistory"><article><div id="old"></div></article></div>';
    const { window, document, dom } = boot({ files: DOCS, body: history + ANSWER });
    const row = document.getElementById('old');
    window.App.agentWorkspace.renderTurnResources(row, TURN_ONE);
    await window.App.agentWorkspace.refresh(CHAT);
    expect(row.hidden).toBe(false);
    expect(row.querySelector('.agent-doc-card').textContent).toContain('Version 1');
    expect(row.textContent).not.toContain('Version 2');
    expect(row.querySelector('.agent-files-badge')).toBeNull();
    const live = document.querySelector('#agentAnswerResources .agent-doc-card');
    expect(live.textContent).toContain('Version 2');
    // A turn without files keeps an empty, hidden row.
    const empty = document.createElement('div'); document.getElementById('threadHistory').append(empty);
    window.App.agentWorkspace.renderTurnResources(empty, 'f'.repeat(32));
    expect(empty.hidden).toBe(true);
    dom.window.close();
  });

  it('opens and removes a message attachment in the chat on screen', async () => {
    const { window, dom } = boot({ files: [UPLOAD] });
    await expect(window.App.agentWorkspace.openFile(UPLOAD.id)).rejects.toThrow('Open this chat to preview the file.');
    await window.App.agentWorkspace.refresh(CHAT);
    const blob = new window.Blob(['%PDF'], { type: 'application/pdf' });
    window.fetch = vi.fn(async (path, options) => options?.method === 'DELETE' ? { ok: true, json: async () => ({}) }
      : path.endsWith(UPLOAD.id) ? { ok: true, blob: async () => blob } : reply([]));
    const file = await window.App.agentWorkspace.openFile(UPLOAD.id);
    expect(file.mime).toBe('application/pdf');
    expect(window.fetch.mock.calls[0][0]).toBe(`/agent/chats/${CHAT}/files/${UPLOAD.id}`);
    expect(window.fetch.mock.calls[0][1].headers.Authorization).toBe('Bearer token');
    await window.App.agentWorkspace.removeFile(UPLOAD.id);
    expect(window.fetch.mock.calls.some(([path, o]) => o?.method === 'DELETE' && path === `/agent/chats/${CHAT}/files/${UPLOAD.id}`)).toBe(true);
    // The list refreshes afterwards.
    expect(window.fetch.mock.calls.at(-1)[0]).toBe(`/agent/chats/${CHAT}/files`);
    dom.window.close();
  });
});
