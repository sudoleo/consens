import { readFileSync } from "node:fs";
import path from "node:path";

import { JSDOM } from "jsdom";
import { describe, expect, it, vi } from "vitest";

import { ROOT } from "./helpers/appWindow.mjs";

/**
 * A chat seen a moment ago is back at once and checked in the background
 * (firebase.js openBookmark, bookmarkViewCache). A check whose transcript
 * request fails says nothing new about the chat: the full view on screen
 * stays (bug hunt 2026-11-04: the fallback without the transcript was drawn
 * over it, the earlier messages vanished and a popup said they could not be
 * displayed).
 */
const FIREBASE = readFileSync(path.join(ROOT, "static/firebase.js"), "utf8");

function slice(start, end) {
  const from = FIREBASE.indexOf(start);
  return FIREBASE.slice(from, FIREBASE.indexOf(end, from));
}

function harness(views, { fetch = null } = {}) {
  const win = { App: { chatScroll: {}, watch: {}, runRegistry: { findByBookmarkId: () => null } } };
  const document = { body: { classList: { contains: () => false } }, querySelector: () => null };
  const drawn = vi.fn();
  const cache = new Map();
  const details = new Map();
  let active = null;
  const loadBookmarkView = vi.fn(async id => views[id].shift());
  // Rename (renameBookmark) beside the opening, in the same scope.
  Function("window", "document", "auth", "authState", "bookmarkWriteAllowed", "syncActiveBookmark",
    "isCurrentAuthenticatedUser", "hideChatOpening", "showChatOpening", "loadSingleBookmarkUI",
    "bookmarkViewCache", "BOOKMARK_VIEW_CACHE_SIZE", "bookmarkDetailCache", "activeBookmarkId",
    "trackAppEvent", "loadBookmarkView", "openedBookmarkId", "bookmarkViewEpoch", "console", "fetch",
    `${slice("function rememberBookmarkView(", "window.loadAllBookmarkMetadata")}
    ${slice("async function renameBookmark(", "// Pin moves the chat")}
    window.renameBookmark = renameBookmark;`)(
    win, document, { currentUser: { uid: "owner", getIdToken: async () => "token" } }, { generation: 1 }, () => true,
    id => { active = id ?? active; }, () => true, () => {}, () => ({}), drawn, cache, 10, details, () => active,
    () => {}, loadBookmarkView, null, 0, { warn() {}, error() {} }, fetch);
  return { open: win.openBookmark, rename: win.renameBookmark, drawn, cache, details, loadBookmarkView };
}

const turns = [
  { id: "t1", question: "First?", status: "completed", consensus: "Answer one" },
  { id: "t2", question: "Second?", status: "completed", consensus: "Answer two" },
];
const full = { bookmark: { id: "a", chat_id: "c".repeat(32), title: "A", responses: { consensus: "Answer two" } },
               turns, conversationLoadFailed: false, running: null };
const other = { bookmark: { id: "b", chat_id: "d".repeat(32), title: "B" }, turns: [], conversationLoadFailed: false, running: null };
const failed = { ...full, turns: [], conversationLoadFailed: true };

describe("a chat back from the view cache", () => {
  it("keeps its full view when the background check's transcript fails", async () => {
    const { open, drawn, cache } = harness({ a: [full, failed], b: [other] });
    await open("a");
    await open("b");
    await open("a");

    // Drawn from the cache, never again from the failed check.
    expect(drawn).toHaveBeenCalledTimes(3);
    expect(drawn.mock.calls[2][1]).toBe(turns);
    expect(drawn.mock.calls[2][2].conversationLoadFailed).toBe(false);
    // The next return is still at once.
    expect(cache.get("a")).toBe(full);
  });

  it("is still drawn anew when the check finds a real change", async () => {
    const longer = { ...full, turns: [...turns, { id: "t3", question: "Third?", status: "completed", consensus: "Three" }] };
    const { open, drawn, cache } = harness({ a: [full, longer], b: [other] });
    await open("a");
    await open("b");
    await open("a");

    expect(drawn).toHaveBeenCalledTimes(4);
    expect(drawn.mock.calls[3][1]).toBe(longer.turns);
    expect(drawn.mock.calls[3][2].keepComposer).toBe(true);
    expect(cache.get("a")).toBe(longer);
  });

  it("is drawn anew when the chat got its share result elsewhere", async () => {
    // Shared in another tab: the server noted a share result on the chat.
    const shared = { ...full, bookmark: { ...full.bookmark, share_result_id: "r1" } };
    const { open, drawn, cache } = harness({ a: [full, shared], b: [other] });
    await open("a");
    await open("b");
    await open("a");

    expect(drawn).toHaveBeenCalledTimes(4);
    expect(drawn.mock.calls[3][0].share_result_id).toBe("r1");
    expect(cache.get("a")).toBe(shared);
  });
});

describe("a renamed chat (bug hunt 2026-11-04)", () => {
  it("keeps its view and takes the new name, instead of loading again over a typed follow-up", async () => {
    const renamed = { ...full, bookmark: { ...full.bookmark, title: "Renamed", title_source: "user" } };
    const fetch = vi.fn(async () => ({ ok: true, json: async () => ({ bookmark: { id: "a", title: "Renamed" } }) }));
    const { open, rename, drawn, cache, details } = harness({ a: [full, renamed] }, { fetch });
    await open("a");
    details.set("a", { ...full.bookmark });
    await rename("a", "Renamed");

    expect(fetch).toHaveBeenCalledWith("/bookmarks/a/title", expect.objectContaining({ method: "PATCH" }));
    expect(cache.get("a").bookmark.title).toBe("Renamed");
    expect(details.get("a").title).toBe("Renamed");
    // Its row clicked again: the chat on screen stays as it is (keepComposer).
    await open("a");
    expect(drawn).toHaveBeenCalledTimes(1);
  });
});

describe("a chat deleted while it still loads (bug hunt 2026-11-04)", () => {
  it("does not open under Chat deleted, and Undo opens it again", async () => {
    const dom = new JSDOM(`<div id="bookmarksContainer"><div class="bookmark" data-id="y"></div></div><div class="container"></div>`);
    const { document } = dom.window;
    const notices = [];
    const clearVisible = vi.fn();
    const win = { App: { chatScroll: {}, watch: {}, runRegistry: { findByBookmarkId: () => null, clearVisible, visible: () => null },
      undoNotice: { show: notice => { notices.push(notice); return notice; } } } };
    const drawn = vi.fn();
    const pending = [];
    const loadBookmarkView = vi.fn(() => new Promise(resolve => pending.push(resolve)));
    const deleteBookmark = vi.fn();
    Function("window", "document", "auth", "authState", "bookmarkWriteAllowed", "syncActiveBookmark",
      "isCurrentAuthenticatedUser", "hideChatOpening", "showChatOpening", "loadSingleBookmarkUI",
      "bookmarkViewCache", "BOOKMARK_VIEW_CACHE_SIZE", "bookmarkDetailCache", "activeBookmarkId",
      "trackAppEvent", "loadBookmarkView", "openedBookmarkId", "bookmarkViewEpoch", "console",
      "undoableBookmarkDeletes", "collapseBookmarkRow", "expandBookmarkRow", "BOOKMARK_UNDO_MS", "deleteBookmark",
      `${slice("function rememberBookmarkView(", "window.loadAllBookmarkMetadata")}
      ${slice("function leaveDeletedChat(", "// Settles every deletion")}
      window.deleteBookmarkWithUndo = deleteBookmarkWithUndo;`)(
      win, document, { currentUser: { uid: "owner" } }, { generation: 1 }, () => true, () => {},
      // The chat on screen before stays the selected one until the new one is drawn.
      () => true, () => {}, () => ({}), drawn, new Map(), 10, new Map(), () => "x",
      () => {}, loadBookmarkView, null, 0, { warn() {}, error() {} },
      new Map(), () => {}, () => {}, 5000, deleteBookmark);
    const row = document.querySelector(".bookmark");

    const opening = win.openBookmark("y");
    expect(row.classList.contains("is-loading")).toBe(true);
    win.deleteBookmarkWithUndo("y");
    // Left like an open chat: the view goes back to the start.
    expect(clearVisible).toHaveBeenCalledTimes(1);
    expect(document.body.classList.contains("is-hero")).toBe(true);
    pending[0](full);
    await opening;
    expect(drawn).not.toHaveBeenCalled();

    notices[0].onAction();
    expect(loadBookmarkView).toHaveBeenCalledTimes(2);
    pending[1](full);
    await vi.waitFor(() => expect(drawn).toHaveBeenCalledTimes(1));
    expect(deleteBookmark).not.toHaveBeenCalled();
  });
});
