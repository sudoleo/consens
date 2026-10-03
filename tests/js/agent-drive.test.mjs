/**
 * Google Drive as a file source: Google's picker, a short-lived drive.file
 * token in page memory, and the picked file as an ordinary composer
 * attachment that names its Google origin. attachments.js runs for real;
 * Google's scripts and the Drive API are stubs.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

const BODY = `<div class="chat-input-container"><button id="attachTrigger"></button>
  <div id="attachMenu" hidden><button id="attachUploadOption"></button><button id="attachDriveOption" hidden></button></div>
  <input id="attachFileInput" type="file"><div id="attachmentBar"></div>
  <textarea id="questionInput"></textarea></div><div id="composerModeBar" hidden></div>`;
const DRIVE = { client_id: "client.apps.googleusercontent.com", api_key: "AIzaSyExampleExampleExample0123", app_id: "123456789012" };
const DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document";

const contexts = [];
afterEach(() => contexts.splice(0).forEach(ctx => ctx.window.close()));
const settle = () => new Promise(resolve => setTimeout(resolve, 0));

function stubGoogle(window, calls) {
  const builder = {};
  for (const name of ["addView", "setOAuthToken", "setDeveloperKey", "setAppId", "setOrigin", "setTitle", "enableFeature", "setMaxItems"]) {
    builder[name] = (...args) => { calls.picker.push([name, ...args]); return builder; };
  }
  builder.setCallback = fn => { calls.pick = fn; return builder; };
  builder.build = () => ({ setVisible: visible => calls.picker.push(["visible", visible]) });
  class DocsView {
    constructor(id) { calls.view = { id }; }
    setMimeTypes(types) { calls.view.types = types; return this; }
    setIncludeFolders() { return this; }
    setSelectFolderEnabled() { return this; }
    setMode() { return this; }
  }
  window.google = {
    accounts: { oauth2: {
      initTokenClient: config => { calls.tokenConfig = config; calls.client = { callback: config.callback, requestAccessToken: options => calls.tokenRequests.push(options) }; return calls.client; },
      hasGrantedAllScopes: (response, scope) => response.scope === scope,
    } },
    picker: {
      PickerBuilder: function PickerBuilder() { return builder; }, DocsView,
      ViewId: { DOCS: "all" }, DocsViewMode: { LIST: "list" }, Feature: { MULTISELECT_ENABLED: "multi" },
      Response: { ACTION: "action", DOCUMENTS: "docs" }, Action: { PICKED: "picked", CANCEL: "cancel" },
      Document: { ID: "id", NAME: "name", MIME_TYPE: "mimeType" },
    },
  };
}

function boot({ drive = DRIVE, agent = true } = {}) {
  const calls = { picker: [], tokenRequests: [], fetches: [], view: null, pick: null, tokenConfig: null };
  const ctx = loadScripts(["static/js/attachments.js", "static/js/agent-drive.js"], {
    body: BODY,
    before(window) {
      window.App = { showPopup: vi.fn(), agentGoogle: {
        agentActive: () => agent, knownDrive: () => Boolean(drive),
        config: async () => ({ configured: true, writes: false, drive }),
      } };
      window.alert = vi.fn();
      window.auth = { currentUser: { uid: "uid-a" } };
      stubGoogle(window, calls);
      // Already loaded: the module must not inject Google's scripts again.
      for (const src of ["https://accounts.google.com/gsi/client", "https://apis.google.com/js/api.js"]) {
        const el = window.document.createElement("script"); el.src = src; el.dataset.loaded = "true"; window.document.head.append(el);
      }
      window.gapi = { load: (_, options) => options.callback() };
      window.fetch = vi.fn(async (url, options) => {
        calls.fetches.push([url, options]);
        if (url.includes("/denied")) return { ok: false, status: 403, json: async () => ({}) };
        return { ok: true, blob: async () => new window.Blob(["Offer: 42 EUR"], { type: "text/plain" }) };
      });
    },
  });
  contexts.push(ctx);
  return { ...ctx, calls };
}

async function openMenu(ctx) {
  await settle(); // the page has finished loading before anyone opens (+)
  ctx.document.getElementById("attachTrigger").click();
  await settle(); await settle(); await settle();
}
function grant(ctx, scope = "https://www.googleapis.com/auth/drive.file") {
  ctx.calls.client.callback({ access_token: "drive-token", expires_in: 3599, scope });
}
function pick(ctx, docs) {
  const p = ctx.window.google.picker;
  ctx.calls.pick({ [p.Response.ACTION]: p.Action.PICKED, [p.Response.DOCUMENTS]: docs });
}
async function untilIdle(ctx) {
  await vi.waitFor(() => expect(ctx.window.App.attachments.isImporting()).toBe(false));
}

describe("Google Drive file source", () => {
  it("shows the entry only in Agent chats on installations with a picker", async () => {
    const off = boot({ drive: null });
    await openMenu(off);
    expect(off.document.getElementById("attachDriveOption").hidden).toBe(true);
    const compare = boot({ agent: false });
    await openMenu(compare);
    expect(compare.document.getElementById("attachDriveOption").hidden).toBe(true);
    const on = boot();
    await openMenu(on);
    expect(on.document.getElementById("attachDriveOption").hidden).toBe(false);
  });

  it("asks Google for drive.file access inside the click, then opens the picker scoped to this app", async () => {
    const ctx = boot();
    await openMenu(ctx);
    ctx.document.getElementById("attachDriveOption").click();
    expect(ctx.window.App.showPopup.mock.calls).toEqual([]);
    expect(ctx.calls.tokenConfig).toMatchObject({ client_id: DRIVE.client_id, scope: "https://www.googleapis.com/auth/drive.file" });
    expect(ctx.calls.tokenRequests).toEqual([{ prompt: "" }]);
    grant(ctx);
    const steps = Object.fromEntries(ctx.calls.picker.map(([name, ...args]) => [name, args]));
    expect(steps.setOAuthToken).toEqual(["drive-token"]);
    expect(steps.setDeveloperKey).toEqual([DRIVE.api_key]);
    // The app ID makes picked files readable to this app (drive.file) only.
    expect(steps.setAppId).toEqual([DRIVE.app_id]);
    expect(steps.setMaxItems).toEqual([2]);
    expect(steps.visible).toEqual([true]);
    expect(ctx.calls.view.types).toContain("application/vnd.google-apps.document");
    // A second pick reuses the token instead of asking Google again.
    ctx.document.getElementById("attachDriveOption").click();
    expect(ctx.calls.tokenRequests).toHaveLength(1);
  });

  it("turns a picked Google Doc into a Word attachment that names its Drive origin", async () => {
    const ctx = boot();
    await openMenu(ctx);
    ctx.document.getElementById("attachDriveOption").click(); grant(ctx);
    pick(ctx, [{ id: "1AbCdEfGhIjKlMnOp", name: "Offer comparison", mimeType: "application/vnd.google-apps.document" }]);
    // While it loads, the chip holds its slot and Send waits.
    expect(ctx.window.App.attachments.isImporting()).toBe(true);
    expect(ctx.document.getElementById("attachmentBar").textContent).toContain("Loading from Google Drive");
    await untilIdle(ctx);
    const [url, options] = ctx.calls.fetches[0];
    expect(url).toBe(`https://www.googleapis.com/drive/v3/files/1AbCdEfGhIjKlMnOp/export?mimeType=${encodeURIComponent(DOCX)}`);
    expect(options.headers.Authorization).toBe("Bearer drive-token");
    await vi.waitFor(() => expect(ctx.window.pendingAttachments).toHaveLength(1));
    const [file] = ctx.window.pendingAttachments;
    expect(file).toMatchObject({ name: "Offer comparison.docx", mime: DOCX, origin: { source: "google_drive", file_id: "1AbCdEfGhIjKlMnOp" } });
    expect(ctx.window.App.attachments.hasDriveFiles()).toBe(true);
    expect(ctx.document.getElementById("attachmentBar").textContent).toContain("Google Drive");
    // The upload payload carries the origin; the token never does.
    const [payload] = ctx.window.getAttachmentsPayload();
    expect(payload.origin).toEqual({ source: "google_drive", file_id: "1AbCdEfGhIjKlMnOp" });
    expect(JSON.stringify(payload)).not.toContain("drive-token");
  });

  it("downloads ordinary files as they are and refuses oversized or unreadable ones", async () => {
    const ctx = boot();
    await openMenu(ctx);
    ctx.document.getElementById("attachDriveOption").click(); grant(ctx);
    pick(ctx, [{ id: "2AbCdEfGhIjKlMnOp", name: "huge.pdf", mimeType: "application/pdf", sizeBytes: String(6 * 1024 * 1024) }]);
    await untilIdle(ctx);
    expect(ctx.calls.fetches).toHaveLength(0);
    expect(ctx.window.App.showPopup).toHaveBeenCalledWith(expect.stringContaining("larger than 5 MB"));
    pick(ctx, [{ id: "3AbCdEfGhIjKlMnOp", name: "notes.txt", mimeType: "text/plain", sizeBytes: "13" }]);
    await untilIdle(ctx);
    expect(ctx.calls.fetches[0][0]).toBe("https://www.googleapis.com/drive/v3/files/3AbCdEfGhIjKlMnOp?alt=media&supportsAllDrives=true");
    await vi.waitFor(() => expect(ctx.window.pendingAttachments.map(item => item.name)).toEqual(["notes.txt"]));
  });

  it("drops a file whose chip was removed while it loaded, and adds nothing without access", async () => {
    const ctx = boot();
    await openMenu(ctx);
    ctx.document.getElementById("attachDriveOption").click();
    grant(ctx, "https://www.googleapis.com/auth/drive.readonly");
    expect(ctx.calls.picker).toHaveLength(0);
    expect(ctx.window.App.showPopup).toHaveBeenCalledWith(expect.stringContaining("not granted"));
    ctx.document.getElementById("attachDriveOption").click(); grant(ctx);
    pick(ctx, [{ id: "4AbCdEfGhIjKlMnOp", name: "draft.txt", mimeType: "text/plain", sizeBytes: "13" }]);
    ctx.document.querySelector("#attachmentBar .attachment-chip-remove").click();
    await settle(); await settle();
    expect(ctx.window.pendingAttachments).toHaveLength(0);
  });

  it("forgets the token when the account changes", async () => {
    const ctx = boot();
    await openMenu(ctx);
    ctx.document.getElementById("attachDriveOption").click(); grant(ctx);
    ctx.window.auth.currentUser = { uid: "uid-b" };
    ctx.window.dispatchEvent(new ctx.window.Event("consensio:auth-state"));
    await openMenu(ctx);
    ctx.document.getElementById("attachDriveOption").click();
    expect(ctx.calls.tokenRequests).toHaveLength(2);
  });
});
