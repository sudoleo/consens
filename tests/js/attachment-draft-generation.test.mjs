/**
 * R21: a file that is still being read belongs to the draft it was added to.
 *
 * Resetting the draft (opening a saved chat, sending, Agent upload) or an
 * account change must discard the late FileReader result instead of letting
 * it reappear as an attachment of the next question. The full module runs;
 * only FileReader is paused.
 */

import { afterEach, describe, expect, it } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

const BODY = `<div class="chat-input-container"><button id="attachTrigger"></button>
  <div id="attachMenu"></div><button id="attachUploadOption"></button>
  <input id="attachFileInput" type="file"><div id="attachmentBar"></div>
  <textarea id="questionInput"></textarea></div>`;

const contexts = [];
afterEach(() => contexts.splice(0).forEach(ctx => ctx.window.close()));

function boot() {
  const readers = [];
  const ctx = loadScripts(["static/js/attachments.js"], {
    body: BODY,
    before(window) {
      window.App = {};
      window.isUserPlus = true;
      window.alert = () => {};
      window.auth = { currentUser: { uid: "uid-a" } };
      window.FileReader = class {
        readAsDataURL() { readers.push(this); }
      };
    },
  });
  contexts.push(ctx);
  return { ...ctx, readers };
}

const settle = () => new Promise(resolve => setTimeout(resolve, 0));

async function pick(ctx, ...names) {
  const picker = ctx.document.getElementById("attachFileInput");
  const files = names.map(name => new ctx.window.File([name], name, { type: "text/plain" }));
  Object.defineProperty(picker, "files", { value: files, configurable: true });
  picker.dispatchEvent(new ctx.window.Event("change"));
  await settle();
}

async function finish(ctx, reader) {
  reader.result = "data:text/plain;base64,b2xk";
  reader.onload();
  await settle();
}

const names = ctx => ctx.window.pendingAttachments.map(item => item.name);

describe("attachment import generation", () => {
  it("drops a late import after the saved-chat reset", async () => {
    const ctx = boot();
    await pick(ctx, "draft-a.txt");
    expect(ctx.window.App.attachments.isImporting()).toBe(true);

    ctx.window.showBookmarkAttachments([]);
    expect(ctx.window.App.attachments.isImporting()).toBe(false);
    await finish(ctx, ctx.readers[0]);

    expect(names(ctx)).toEqual([]);
  });

  it("drops a late import after the draft was handed to a sent message", async () => {
    const ctx = boot();
    await pick(ctx, "draft-a.txt");
    ctx.window.App.attachments.detachForMessage();
    await finish(ctx, ctx.readers[0]);
    expect(names(ctx)).toEqual([]);
  });

  it("drops a late import after an account change", async () => {
    const ctx = boot();
    await pick(ctx, "draft-a.txt");
    ctx.window.dispatchEvent(new ctx.window.CustomEvent("consensio:auth-state", { detail: { uid: "uid-b" } }));
    await finish(ctx, ctx.readers[0]);
    expect(names(ctx)).toEqual([]);
  });

  it("a stale import neither blocks nor leaks into the next draft's limit", async () => {
    const ctx = boot();
    // Two files is the per-question limit. The old draft's pending reads must
    // not count against the new draft once it was cleared.
    await pick(ctx, "a1.txt", "a2.txt");
    ctx.window.clearPendingAttachments();
    await pick(ctx, "b1.txt", "b2.txt");
    expect(ctx.readers).toHaveLength(4);

    // Old reads finish in between the new ones.
    await finish(ctx, ctx.readers[0]);
    await finish(ctx, ctx.readers[2]);
    await finish(ctx, ctx.readers[1]);
    await finish(ctx, ctx.readers[3]);

    expect(names(ctx)).toEqual(["b1.txt", "b2.txt"]);
    expect(ctx.window.App.attachments.isImporting()).toBe(false);
  });

  it("keeps order and completes a normal multi-file import", async () => {
    const ctx = boot();
    await pick(ctx, "one.txt", "two.txt");
    for (const reader of ctx.readers) await finish(ctx, reader);
    expect(names(ctx)).toEqual(["one.txt", "two.txt"]);
  });
});
