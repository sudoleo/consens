import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it, vi } from "vitest";

import { loadScripts, ROOT } from "./helpers/appWindow.mjs";

// What the sidebar and an opened chat do when the server answers with an
// error on the way (firebase.js loadBookmarks, loadBookmarkConversation).
const FIREBASE = readFileSync(path.join(ROOT, "static/firebase.js"), "utf8");

function slice(start, end) {
  const from = FIREBASE.indexOf(start);
  return FIREBASE.slice(from, FIREBASE.indexOf(end, from));
}

const json = (status, body) => ({ ok: status < 400, status, json: async () => body,
  text: async () => JSON.stringify(body) });
// A proxy's error page in front of a restarting server.
const page = status => ({ ok: false, status, json: async () => { throw new SyntaxError("Unexpected token <"); },
  text: async () => "<html><body>Bad Gateway</body></html>" });

describe("the chat list", () => {
  function list(responses) {
    const { window, document } = loadScripts([], { body: '<div id="bookmarksContainer"></div>' });
    window.App.chatList = { sync() {} };
    const calls = { error: 0, more: 0, popups: [] };
    window.App.showPopup = text => calls.popups.push(text);
    const fetch = vi.fn(async () => {
      const next = responses.shift();
      if (next instanceof Error) throw next;
      return next;
    });
    const load = Function("window", "document", "fetch", "calls", "console", `
      const auth = {currentUser: {uid: 'user', getIdToken: async () => 'token'}};
      const authState = {generation: 1};
      let bookmarksLoading = false, bookmarksLoadRequestId = 0, bookmarksNextCursor = null;
      const isCurrentAuthenticatedUser = () => true;
      const ensurePendingBookmarkDOM = () => {};
      const restoreRegistryRunRows = () => {};
      const renderBookmarksLoadMore = () => { calls.more += 1; calls.cursor = bookmarksNextCursor; };
      const syncActiveBookmark = () => {};
      const upsertBookmarkMeta = item => { const row = document.createElement('div'); row.className = 'bookmark'; row.textContent = item.id; document.getElementById('bookmarksContainer').append(row); };
      const renderBookmarksLoadError = container => { calls.error += 1; container.replaceChildren(); };
      ${slice("const BOOKMARK_MIN_NEW_ROWS", "async function loadBookmarkDetail(")}
      return loadBookmarks;
    `)(window, document, fetch, calls, { error() {} });
    return { load, calls, document, fetch };
  }

  it("keeps the first page when a page loaded after it for chats in closed projects fails", async () => {
    // Two rows only: the next page comes at once (sparse), and fails.
    const { load, calls, document, fetch } = list([
      json(200, { bookmarks: [{ id: "a" }, { id: "b" }], next_cursor: "page-2" }),
      json(503, { detail: "Service unavailable" }),
    ]);
    expect(await load()).toBe(true);
    expect(fetch).toHaveBeenCalledTimes(2);
    expect([...document.querySelectorAll(".bookmark")].map(row => row.textContent)).toEqual(["a", "b"]);
    expect(calls.error).toBe(0);
    expect(calls.popups).toEqual([]);
    // "Load more" asks for the page that failed.
    expect(calls.more).toBe(1);
    expect(calls.cursor).toBe("page-2");
  });

  it("still says so when the first page fails", async () => {
    const { load, calls, document } = list([new TypeError("Failed to fetch")]);
    expect(await load()).toBe(false);
    expect(calls.error).toBe(1);
    expect(document.querySelectorAll(".bookmark")).toHaveLength(0);
  });
});

describe("an opened chat's messages", () => {
  function conversation(responses) {
    const { window } = loadScripts([]);
    const fetch = vi.fn(async () => responses.shift());
    const load = Function("window", "fetch", `
      const auth = {currentUser: {uid: 'user', getIdToken: async () => 'token'}};
      const authState = {generation: 1};
      const isCurrentAuthenticatedUser = () => true;
      ${slice("async function loadBookmarkConversationOnce", "// Chat and turn IDs the server issues")}
      return loadBookmarkConversation;
    `)(window, fetch);
    return { load, fetch };
  }

  it("are asked for again after a proxy's error page, which is no JSON", async () => {
    const { load, fetch } = conversation([page(502), json(200, { chat_id: "c1", turns: [{ id: "t1" }] })]);
    const loaded = await load("b1");
    expect(fetch).toHaveBeenCalledTimes(2);
    expect(loaded.chatId).toBe("c1");
    expect(loaded.turns.map(turn => turn.id)).toEqual(["t1"]);
  });

  it("are not asked for again when the server refuses them", async () => {
    const { load, fetch } = conversation([json(404, { detail: "Not found" })]);
    await expect(load("b1")).rejects.toThrow("Not found");
    expect(fetch).toHaveBeenCalledTimes(1);
  });
});
