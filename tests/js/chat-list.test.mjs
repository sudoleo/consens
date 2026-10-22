/**
 * The chat list in groups (static/js/chat-list.js, 2026-10-22).
 *
 * Pinned chats lead; the others stand under Today, Yesterday, Previous 7
 * days, Previous 30 days, the month, the year. Rows arrive from several
 * modules (firebase.js, run-view.js) that know nothing of headings, so the
 * module has to group whatever lands in the list, write nothing when all is
 * in place, and keep a follow-up's chat where the person found it.
 */

import { describe, expect, it } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

const NOW = new Date(2026, 9, 22, 15, 0).getTime();
const DAY = 864e5;

// The module starts on DOMContentLoaded when the page is still parsing (in
// the app it is deferred and starts at once); boot waits for that.
async function boot(bookmarks, rows = bookmarks.map((meta) => meta.id)) {
  const { window, document } = loadScripts(["static/js/chat-list.js"], {
    body: `<div id="bookmarksContainer">${rows
      .map((id) => `<div class="bookmark" data-id="${id}"><p>${id}</p></div>`)
      .join("")}<button id="bookmarksLoadMore"></button></div>`,
    before(win) {
      win.bookmarksData = bookmarks;
      win.Date.now = () => NOW;
    },
  });
  if (document.readyState === "loading") {
    await new Promise((resolve) => document.addEventListener("DOMContentLoaded", resolve, { once: true }));
  }
  return { window, document, chatList: window.App.chatList };
}

function layout(document) {
  return Array.from(document.getElementById("bookmarksContainer").children)
    .filter((node) => !node.hidden && node.style.display !== "none")
    .map((node) => node.dataset.id || node.id || node.textContent);
}

const ago = (days) => new Date(NOW - days * DAY).toISOString();

describe("chat list groups", () => {
  it("names the groups by calendar day, then month, then year", async () => {
    const { chatList } = await boot([]);
    const label = (value) => chatList.groupOf(value, NOW)?.label;
    expect(label(new Date(2026, 9, 22, 0, 1).toISOString())).toBe("Today");
    expect(label(new Date(2026, 9, 21, 23, 59).toISOString())).toBe("Yesterday");
    expect(label(ago(7))).toBe("Previous 7 days");
    expect(label(ago(8))).toBe("Previous 30 days");
    expect(label(ago(31))).toBe("September");
    expect(label(new Date(2025, 11, 30).toISOString())).toBe("2025");
    // Seconds, a Firestore timestamp's parts, and nothing at all.
    expect(label(Math.floor(NOW / 1000))).toBe("Today");
    expect(label({ seconds: Math.floor((NOW - 2 * DAY) / 1000) })).toBe("Previous 7 days");
    expect(chatList.groupOf(null, NOW)).toBeNull();
  });

  it("puts the pinned chats first, the latest pin on top, and every group under its heading", async () => {
    const { document } = await boot([
      { id: "a", timestamp: ago(0) },
      { id: "b", timestamp: ago(1), pinned: true, pinned_at: ago(3) },
      { id: "c", timestamp: ago(3) },
      { id: "d", timestamp: ago(400), pinned: true, pinned_at: ago(0) },
      { id: "e", timestamp: ago(40) },
    ]);
    expect(layout(document)).toEqual([
      "Pinned", "d", "b", "Today", "a", "Previous 7 days", "c", "September", "e", "bookmarksLoadMore",
    ]);
    expect(document.querySelector(".chat-list-heading").tagName).toBe("H3");
  });

  it("groups a row that arrives later and writes nothing when all is in place", async () => {
    const { window, document } = await boot([{ id: "a", timestamp: ago(2) }]);
    const container = document.getElementById("bookmarksContainer");
    // A new run: no saved chat yet, so it is new and goes on top.
    const row = document.createElement("div");
    row.className = "bookmark run-entry";
    row.dataset.id = "run";
    container.append(row);
    await Promise.resolve();
    expect(layout(document)).toEqual(["Today", "run", "Previous 7 days", "a", "bookmarksLoadMore"]);

    const writes = [];
    new window.MutationObserver((records) => writes.push(...records))
      .observe(container, { childList: true, subtree: true, attributes: true });
    window.App.chatList.sync();
    await Promise.resolve();
    expect(writes).toEqual([]);
  });

  it("keeps a chat where it was when a follow-up saves it with a new time", async () => {
    const data = [{ id: "a", timestamp: ago(0) }, { id: "b", timestamp: ago(5) }];
    const { window, document } = await boot(data);
    data[1] = { id: "b", timestamp: new Date(NOW).toISOString() };
    window.App.chatList.sync();
    expect(layout(document)).toEqual(["Today", "a", "Previous 7 days", "b", "bookmarksLoadMore"]);
  });

  it("hides the heading of a group whose chats a search hides", async () => {
    const { document } = await boot([{ id: "a", timestamp: ago(0) }, { id: "b", timestamp: ago(1) }]);
    document.querySelector('[data-id="a"]').style.display = "none";
    await Promise.resolve();
    expect(layout(document)).toEqual(["Yesterday", "b", "bookmarksLoadMore"]);
    document.querySelector('[data-id="a"]').style.display = "";
    await Promise.resolve();
    expect(layout(document)).toEqual(["Today", "a", "Yesterday", "b", "bookmarksLoadMore"]);
  });

  it("returns an unpinned chat to its own date", async () => {
    const data = [
      { id: "a", timestamp: ago(0) },
      { id: "old", timestamp: ago(400), pinned: true, pinned_at: ago(0) },
    ];
    const { window, document } = await boot(data, ["old", "a"]);
    expect(layout(document)).toEqual(["Pinned", "old", "Today", "a", "bookmarksLoadMore"]);
    Object.assign(data[1], { pinned: false, pinned_at: null });
    window.App.chatList.sync();
    expect(layout(document)).toEqual(["Today", "a", "2025", "old", "bookmarksLoadMore"]);
  });
});
