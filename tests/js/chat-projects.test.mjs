/**
 * Projects in the chat list (static/js/chat-projects.js with chat-list.js).
 *
 * A project chat stands under its project and nowhere else; a closed
 * project is one row; a chat naming a project the account does not have is
 * an ordinary chat; a search opens every project and shows a project by
 * its name; a move is optimistic and goes back when the server refuses it.
 */

import { describe, expect, it, vi } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

const NOW = new Date(2026, 10, 19, 15, 0).getTime();
const DAY = 864e5;
const ago = (days) => new Date(NOW - days * DAY).toISOString();

async function boot(bookmarks, { projects = [], open = [] } = {}) {
  const { window, document } = loadScripts(["static/js/chat-list.js", "static/js/chat-projects.js"], {
    body: `<input id="chatSearch" value=""><div id="bookmarksContainer">${bookmarks
      .map((meta) => `<div class="bookmark" data-id="${meta.id}"><p>${meta.id}</p><button class="bookmark-menu-button"></button></div>`)
      .join("")}<button id="bookmarksLoadMore"></button></div>`,
    before(win) {
      win.bookmarksData = bookmarks;
      win.Date.now = () => NOW;
      win.localStorage.setItem("projects_open", JSON.stringify(open));
    },
  });
  if (document.readyState === "loading") {
    await new Promise((resolve) => document.addEventListener("DOMContentLoaded", resolve, { once: true }));
  }
  const chatProjects = window.App.chatProjects;
  // The first page's projects; no fetch for an open one in these tests.
  window.fetch = vi.fn(async () => ({ ok: true, json: async () => ({ bookmarks: [] }) }));
  await chatProjects.adopt(projects);
  window.App.chatList.sync();
  return { window, document, chatProjects };
}

// What a reader sees, top to bottom: rows by id, project rows by name,
// headings and buttons by their words.
function layout(document) {
  return Array.from(document.getElementById("bookmarksContainer").children)
    .filter((node) => !node.hidden && node.style.display !== "none" && !node.classList.contains("is-folded"))
    .map((node) => {
      if (node.classList.contains("chat-project")) return `[${node.querySelector(".chat-project-name").textContent}]`;
      if (node.classList.contains("chat-project-empty")) return "+chat";
      if (node.classList.contains("chat-projects-heading")) return "Projects";
      return node.dataset.id || node.id || node.textContent;
    });
}

const PROJECTS = [
  { id: "p_aaaaaaaaaaaa", name: "Thesis" },
  { id: "p_bbbbbbbbbbbb", name: "Move" },
];

describe("projects in the chat list", () => {
  it("puts the projects first, newest first, each chat only under its open project", async () => {
    const { document } = await boot([
      { id: "a", timestamp: ago(0) },
      { id: "t1", timestamp: ago(3), project_id: "p_aaaaaaaaaaaa" },
      { id: "t2", timestamp: ago(1), project_id: "p_aaaaaaaaaaaa" },
      { id: "m1", timestamp: ago(0), project_id: "p_bbbbbbbbbbbb", pinned: true, pinned_at: ago(0) },
      { id: "p", timestamp: ago(40), pinned: true, pinned_at: ago(1) },
    ], { projects: PROJECTS, open: ["p_aaaaaaaaaaaa"] });

    expect(layout(document)).toEqual([
      "Projects", "[Move]", "[Thesis]", "t2", "t1", "Pinned", "p", "Today", "a", "bookmarksLoadMore",
    ]);
    // A pinned chat in a project stands in its project (folded here), not under Pinned.
    const folded = document.querySelector('[data-id="m1"]');
    expect(folded.classList.contains("is-folded")).toBe(true);
    expect(folded.classList.contains("in-project")).toBe(true);
    expect(document.querySelector('[data-id="t2"]').classList.contains("is-folded")).toBe(false);
  });

  it("shows an open empty project's New chat row and nothing for an account without projects", async () => {
    const empty = await boot([{ id: "a", timestamp: ago(0) }], { projects: [PROJECTS[0]], open: ["p_aaaaaaaaaaaa"] });
    expect(layout(empty.document)).toEqual(["Projects", "[Thesis]", "+chat", "Today", "a", "bookmarksLoadMore"]);

    const none = await boot([{ id: "a", timestamp: ago(0), project_id: "p_gone00000000" }]);
    expect(layout(none.document)).toEqual(["Today", "a", "bookmarksLoadMore"]);
    expect(none.document.querySelector(".chat-projects-heading")).toBeNull();
  });

  it("treats a chat naming a project the account lost as an ordinary chat", async () => {
    const { document } = await boot([
      { id: "a", timestamp: ago(0), project_id: "p_cccccccccccc" },
    ], { projects: PROJECTS });
    expect(layout(document)).toEqual(["Projects", "[Move]", "[Thesis]", "Today", "a", "bookmarksLoadMore"]);
    expect(document.querySelector('[data-id="a"]').classList.contains("in-project")).toBe(false);
  });

  it("opens every project while the search has words and shows a project by its name", async () => {
    const data = [
      { id: "t1", timestamp: ago(1), project_id: "p_aaaaaaaaaaaa" },
      { id: "m1", timestamp: ago(2), project_id: "p_bbbbbbbbbbbb" },
    ];
    const { window, document } = await boot(data, { projects: PROJECTS });
    expect(layout(document)).toEqual(["Projects", "[Move]", "[Thesis]", "bookmarksLoadMore"]);

    document.getElementById("chatSearch").value = "thesis";
    document.querySelector('[data-id="m1"]').style.display = "none";
    window.App.chatList.sync();
    expect(layout(document)).toEqual(["Projects", "[Thesis]", "t1", "bookmarksLoadMore"]);
    expect(document.querySelector('[data-project-id="p_aaaaaaaaaaaa"] .chat-project-toggle')
      .getAttribute("aria-disabled")).toBe("true");

    document.getElementById("chatSearch").value = "";
    document.querySelector('[data-id="m1"]').style.display = "";
    window.App.chatList.sync();
    expect(layout(document)).toEqual(["Projects", "[Move]", "[Thesis]", "bookmarksLoadMore"]);
  });

  it("opens and closes a project from its row and keeps the choice", async () => {
    const { window, document } = await boot([
      { id: "t1", timestamp: ago(1), project_id: "p_aaaaaaaaaaaa" },
    ], { projects: [PROJECTS[0]] });
    const toggle = document.querySelector(".chat-project-toggle");

    toggle.click();
    expect(layout(document)).toEqual(["Projects", "[Thesis]", "t1", "bookmarksLoadMore"]);
    expect(toggle.getAttribute("aria-expanded")).toBe("true");
    expect(JSON.parse(window.localStorage.getItem("projects_open"))).toEqual(["p_aaaaaaaaaaaa"]);

    toggle.click();
    await new Promise((resolve) => window.setTimeout(resolve, 0));
    expect(layout(document)).toEqual(["Projects", "[Thesis]", "bookmarksLoadMore"]);
    expect(JSON.parse(window.localStorage.getItem("projects_open"))).toEqual([]);
  });

  it("moves a chat at once and puts it back when the server refuses", async () => {
    const data = [{ id: "a", timestamp: ago(0) }];
    const { window, document, chatProjects } = await boot(data, { projects: [PROJECTS[0]], open: ["p_aaaaaaaaaaaa"] });
    const user = { uid: "u1", getIdToken: async () => "token" };
    window.auth = { currentUser: user };
    window.App.showPopup = vi.fn();
    let answer;
    window.fetch = vi.fn(() => new Promise((resolve) => { answer = resolve; }));

    const moving = chatProjects.move("a", "p_aaaaaaaaaaaa");
    expect(layout(document)).toEqual(["Projects", "[Thesis]", "a", "bookmarksLoadMore"]);
    await vi.waitFor(() => expect(answer).toBeTypeOf("function"));
    answer({ ok: false, status: 500, json: async () => ({ detail: "The chat could not be moved." }) });
    await moving;

    expect(layout(document)).toEqual(["Projects", "[Thesis]", "+chat", "Today", "a", "bookmarksLoadMore"]);
    expect(data[0].project_id).toBeNull();
    expect(window.App.showPopup).toHaveBeenCalledWith("This chat couldn’t be moved. Try again.");
    const [path, request] = window.fetch.mock.calls[0];
    expect(path).toBe("/bookmarks/a/project");
    expect(JSON.parse(request.body)).toEqual({ project_id: "p_aaaaaaaaaaaa" });
  });
});
