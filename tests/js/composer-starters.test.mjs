import { afterEach, describe, expect, it, vi } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

// static/js/composer-starters.js: example questions predicted from the
// newest chats, kept per account and painted from the first frame.
const ROW = '<div id="composerStarters">'
  + '<button type="button" class="composer-starter" data-starter="glp1" data-question="GLP-1?">GLP-1?</button>'
  + '</div><footer class="app-footer"></footer>';
const KEY = "consensio.starterQuestions.v1";
const PREDICTED = [
  { label: "Heat pump costs?", question: "What will a heat pump cost to run per year?" },
  { label: "AI Act deadlines?", question: "Which EU AI Act deadlines apply to us?" },
];
const contexts = [];

// A Firebase ID token's shape; only its payload is read.
function token(uid) {
  const payload = Buffer.from(JSON.stringify({ user_id: uid, sub: uid })).toString("base64url");
  return `header.${payload}.signature`;
}

function chats(count) {
  return Array.from({ length: count }, (_, index) => ({ id: `chat_${index}`, title: `Chat ${index}` }));
}

function boot({ storage = {}, uid = "uid-1", bookmarks = chats(3), answer = { status: "success", questions: PREDICTED },
  files = ["static/js/composer-starters.js"] } = {}) {
  const calls = { fetches: [] };
  const ctx = loadScripts(files, {
    body: ROW,
    before(window) {
      Object.entries(storage).forEach(([key, value]) => window.localStorage.setItem(key, value));
      // The test's timers, so vi.useFakeTimers() reaches the module's delay.
      window.setTimeout = (fn, ms) => setTimeout(fn, ms);
      window.clearTimeout = id => clearTimeout(id);
      window.matchMedia = () => ({ matches: true });
      window.auth = { currentUser: uid ? { uid, getIdToken: async () => "fresh-token" } : null };
      window.bookmarksData = bookmarks;
      window.fetch = async (url, options) => {
        calls.fetches.push([url, options]);
        return { ok: true, json: async () => answer };
      };
    },
  });
  contexts.push(ctx);
  const { window, document } = ctx;
  const labels = () => [...document.querySelectorAll(".composer-starter:not([hidden])")].map(button => button.textContent);
  const stored = () => JSON.parse(window.localStorage.getItem(KEY) || "null");
  return { ...ctx, App: window.App, calls, labels, stored, row: document.getElementById("composerStarters") };
}

// Past the refresh delay, then through the request's awaits.
async function settle() {
  await vi.advanceTimersByTimeAsync(2000);
  for (let index = 0; index < 30; index++) await Promise.resolve();
}

afterEach(() => {
  vi.useRealTimers();
  contexts.splice(0).forEach(ctx => ctx.window.close());
});

describe("the first frame", () => {
  const record = (uid, at = Date.now()) => JSON.stringify({ uid, basis: "chat_0", at, questions: PREDICTED });

  it("paints the account's stored prediction before the session is restored", () => {
    const { document, labels } = boot({
      storage: { id_token: token("uid-1"), [KEY]: record("uid-1") },
      files: ["static/js/composer-starters.js", "static/js/app-bootstrap.js"],
    });
    expect(labels()).toEqual(["Heat pump costs?", "AI Act deadlines?"]);
    const predicted = document.querySelector('[data-starter="predicted"]');
    expect(predicted.dataset.question).toBe(PREDICTED[0].question);
    // The curated question waits, hidden, for a sign-out.
    expect(document.querySelector('[data-starter="glp1"]').hidden).toBe(true);
  });

  it.each([
    ["another account's", { id_token: token("uid-2"), [KEY]: record("uid-1") }],
    ["a guest's browser", { [KEY]: record("uid-1") }],
    ["a week-old", { id_token: token("uid-1"), [KEY]: record("uid-1", Date.now() - 8 * 24 * 3600 * 1000) }],
  ])("keeps the curated questions for %s prediction", (_label, storage) => {
    const { labels } = boot({ storage, files: ["static/js/composer-starters.js", "static/js/app-bootstrap.js"] });
    expect(labels()).toEqual(["GLP-1?"]);
  });
});

describe("asking for a prediction", () => {
  it("asks once the account holds three chats, then keeps it per account", async () => {
    vi.useFakeTimers();
    const ctx = boot();
    ctx.App.composerStarters.refresh();
    ctx.App.composerStarters.refresh();
    await settle(ctx);

    expect(ctx.calls.fetches).toHaveLength(1);
    const [url, options] = ctx.calls.fetches[0];
    expect(url).toBe("/api/my/starter-questions");
    expect(options.method).toBe("POST");
    expect(options.headers.Authorization).toBe("Bearer fresh-token");
    expect(ctx.labels()).toEqual(["Heat pump costs?", "AI Act deadlines?"]);
    expect(ctx.stored()).toMatchObject({ uid: "uid-1", basis: "chat_0,chat_1,chat_2", questions: PREDICTED });

    // Same newest chats: nothing to ask.
    ctx.App.composerStarters.refresh();
    await settle(ctx);
    expect(ctx.calls.fetches).toHaveLength(1);

    // A new chat on top asks again.
    ctx.window.bookmarksData = [{ id: "chat_new" }, ...ctx.window.bookmarksData];
    ctx.App.composerStarters.refresh();
    await settle(ctx);
    expect(ctx.calls.fetches).toHaveLength(2);
  });

  it("reads the newest chats by time, with a pinned chat at its own place", async () => {
    // Bug hunt 2026-10-23: pinned chats come first in bookmarksData, so the
    // basis changed with the order the pins arrived in and twelve pins hid
    // every new chat.
    vi.useFakeTimers();
    const at = day => `2026-10-${String(day).padStart(2, "0")}T08:00:00Z`;
    const bookmarks = [
      { id: "pin_old", pinned: true, timestamp: at(1) },
      { id: "pin_mid", pinned: true, timestamp: at(20) },
      ...[30, 29, 25, 10].map(day => ({ id: `chat_${day}`, timestamp: at(day) })),
    ];
    const ctx = boot({ bookmarks });
    ctx.App.composerStarters.refresh();
    await settle(ctx);
    expect(ctx.stored().basis).toBe("chat_30,chat_29,chat_25,pin_mid,chat_10,pin_old");

    // The same chats after a reload that brought the pins in another order:
    // nothing to ask.
    ctx.window.bookmarksData = [bookmarks[1], bookmarks[0], ...bookmarks.slice(2)];
    ctx.App.composerStarters.refresh();
    await settle(ctx);
    expect(ctx.calls.fetches).toHaveLength(1);
  });

  it("never asks with fewer than three chats and forgets a prediction once they are deleted", async () => {
    vi.useFakeTimers();
    const record = JSON.stringify({ uid: "uid-1", basis: "chat_0,chat_1,chat_2", at: Date.now(), questions: PREDICTED });
    const ctx = boot({ storage: { [KEY]: record }, bookmarks: chats(2) });
    ctx.App.composerStarters.refresh();
    await settle(ctx);
    expect(ctx.calls.fetches).toHaveLength(0);
    expect(ctx.stored()).toBeNull();
    expect(ctx.labels()).toEqual(["GLP-1?"]);
  });

  it("keeps what the row shows when the server skips", async () => {
    vi.useFakeTimers();
    const ctx = boot({ answer: { status: "skipped", questions: [] } });
    ctx.App.composerStarters.refresh();
    await settle(ctx);
    expect(ctx.calls.fetches).toHaveLength(1);
    expect(ctx.stored()).toBeNull();
    expect(ctx.labels()).toEqual(["GLP-1?"]);
  });

  it("does not swap the buttons under the pointer", async () => {
    vi.useFakeTimers();
    const ctx = boot();
    ctx.row.matches = selector => selector === ":hover";
    ctx.App.composerStarters.refresh();
    await settle(ctx);
    expect(ctx.labels()).toEqual(["GLP-1?"]);

    ctx.row.matches = () => false;
    ctx.row.dispatchEvent(new ctx.window.Event("pointerleave"));
    expect(ctx.labels()).toEqual(["Heat pump costs?", "AI Act deadlines?"]);
  });
});

describe("leaving the account", () => {
  const record = JSON.stringify({ uid: "uid-1", basis: "chat_0", at: Date.now(), questions: PREDICTED });

  it("takes the prediction off the row and out of the browser on sign-out", () => {
    const ctx = boot({ storage: { id_token: token("uid-1"), [KEY]: record },
      files: ["static/js/composer-starters.js", "static/js/app-bootstrap.js"] });
    expect(ctx.labels()).toHaveLength(2);
    ctx.App.composerStarters.clear();
    expect(ctx.labels()).toEqual(["GLP-1?"]);
    expect(ctx.document.querySelector('[data-starter="predicted"]')).toBeNull();
    expect(ctx.stored()).toBeNull();
  });

  it("forgets another account's prediction once the session is known", () => {
    const ctx = boot({ storage: { [KEY]: record } });
    ctx.window.dispatchEvent(new ctx.window.CustomEvent("consensio:auth-state", { detail: { known: true, uid: "uid-2" } }));
    expect(ctx.stored()).toBeNull();

    const guest = boot({ storage: { [KEY]: record } });
    guest.window.dispatchEvent(new guest.window.CustomEvent("consensio:auth-state", { detail: { known: true, uid: null } }));
    expect(guest.stored()).toBeNull();
  });
});
