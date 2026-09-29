/**
 * R23: the Remember/Correct dialog belongs to the account that selected the
 * text. The full memory-edit.js module runs with the real auth generation
 * owner (auth-session-state.js); Firebase identity and fetch are stubs.
 */

import { afterEach, describe, expect, it, vi } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

const contexts = [];
afterEach(() => contexts.splice(0).forEach(ctx => ctx.window.close()));

function account(uid) {
  return { uid, getIdToken: vi.fn(async () => `token-${uid}`) };
}

function boot() {
  const requests = [];
  const ctx = loadScripts(["static/js/auth-session-state.js", "static/js/memory-edit.js"], {
    body: '<textarea id="questionInput">Account A preference</textarea>',
    before(window) {
      window.auth = { currentUser: account("A") };
      window.fetch = (url, options) => new Promise(resolve => {
        requests.push({ url, options, resolve });
      });
    },
  });
  const { window } = ctx;
  window.App.userMemory = { load: vi.fn(async () => {}) };
  window.App.authState.setIdentity("A");
  window.App.authState.publish("A");
  window.document.dispatchEvent(new window.Event("DOMContentLoaded"));
  contexts.push(ctx);
  return { ...ctx, requests };
}

const settle = async () => {
  for (let i = 0; i < 10; i += 1) await new Promise(resolve => setTimeout(resolve, 0));
};

function selectAndOpen(ctx) {
  const question = ctx.document.getElementById("questionInput");
  question.setSelectionRange(0, question.value.length);
  question.dispatchEvent(new ctx.window.KeyboardEvent("keyup", { key: "Shift", bubbles: true }));
  ctx.document.querySelector('[data-memory-intent="add"]').click();
  expect(ctx.document.getElementById("memoryEditBackdrop").hidden).toBe(false);
}

function switchAccount(ctx, uid) {
  ctx.window.auth.currentUser = uid ? account(uid) : null;
  ctx.window.App.authState.setIdentity(uid);
  ctx.window.App.authState.publish(uid);
}

const submit = ctx => ctx.document.querySelector(".memory-edit-submit").click();

describe("memory edit dialog ownership", () => {
  it("closes and forgets A's selection when the account changes to B", async () => {
    const ctx = boot();
    selectAndOpen(ctx);

    switchAccount(ctx, "B");

    expect(ctx.document.getElementById("memoryEditBackdrop").hidden).toBe(true);
    expect(ctx.document.getElementById("memoryEditSelection").textContent).toBe("");
    submit(ctx);
    await settle();
    expect(ctx.requests).toEqual([]);
  });

  it("refuses to submit A's selection even if no auth event was seen", async () => {
    const ctx = boot();
    selectAndOpen(ctx);
    // A second tab switched the Firebase user; this tab has not been told yet.
    ctx.window.auth.currentUser = account("B");

    submit(ctx);
    await settle();

    expect(ctx.requests).toEqual([]);
    expect(ctx.document.getElementById("memoryEditBackdrop").hidden).toBe(true);
  });

  it("a late answer for A neither reloads nor shows Undo in B's session", async () => {
    const ctx = boot();
    selectAndOpen(ctx);
    submit(ctx);
    await settle();
    expect(ctx.requests).toHaveLength(1);
    expect(ctx.requests[0].options.headers.Authorization).toBe("Bearer token-A");

    switchAccount(ctx, "B");
    ctx.requests[0].resolve({
      ok: true,
      json: async () => ({ status: "applied", revision_id: "a".repeat(32), operation: "append" }),
    });
    await settle();

    expect(ctx.window.App.userMemory.load).not.toHaveBeenCalled();
    expect(ctx.document.getElementById("memoryEditToast").hidden).toBe(true);
  });

  it("hides A's Undo toast when the account changes", async () => {
    const ctx = boot();
    selectAndOpen(ctx);
    submit(ctx);
    await settle();
    ctx.requests[0].resolve({
      ok: true,
      json: async () => ({ status: "applied", revision_id: "b".repeat(32), operation: "append" }),
    });
    await settle();
    const toast = ctx.document.getElementById("memoryEditToast");
    expect(toast.hidden).toBe(false);

    switchAccount(ctx, "B");

    expect(toast.hidden).toBe(true);
    expect(toast.querySelector(".memory-edit-undo")).toBeNull();
  });

  it("keeps working through a token refresh of the same account", async () => {
    const ctx = boot();
    selectAndOpen(ctx);
    // Same uid republished (e.g. token refresh / tab focus): no identity change.
    ctx.window.App.authState.publish("A");
    expect(ctx.document.getElementById("memoryEditBackdrop").hidden).toBe(false);

    submit(ctx);
    await settle();
    ctx.requests[0].resolve({
      ok: true,
      json: async () => ({ status: "applied", revision_id: "c".repeat(32), operation: "append" }),
    });
    await settle();

    expect(JSON.parse(ctx.requests[0].options.body).selected_text).toBe("Account A preference");
    expect(ctx.window.App.userMemory.load).toHaveBeenCalledWith(true, { keepDraft: true });
    expect(ctx.document.getElementById("memoryEditToast").hidden).toBe(false);
  });
});
