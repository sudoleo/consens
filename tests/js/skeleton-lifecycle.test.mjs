import { afterEach, describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import path from "node:path";
import { loadScripts, ROOT } from "./helpers/appWindow.mjs";

const contexts = [];
const body = '<div id="authTopActions" hidden></div><div id="loginContainer"></div>'
  + '<div id="freeUsageDisplay"></div><div id="deepUsageDisplay"></div><div id="bookmarksContainer"></div>';
function boot(state) {
  const ctx = loadScripts(["static/js/app-bootstrap.js"], { body, before(window) {
    window.localStorage.setItem("id_token", "cached-token");
    window.__consensioAuthState = state;
  } });
  contexts.push(ctx);
  ctx.document.dispatchEvent(new ctx.window.Event("DOMContentLoaded"));
  return ctx;
}
afterEach(() => contexts.splice(0).forEach(ctx => ctx.window.close()));

// The first paint already has what the app settles on: no light flash on a
// dark reload, no composer wording swapped in front of the reader.
function paint({ storage = {}, systemDark = false } = {}) {
  const ctx = loadScripts(["static/js/app-bootstrap.js"], {
    body: '<h1 class="hero-greeting">Compare</h1><textarea id="questionInput" placeholder="Enter your question"></textarea>',
    before(window) {
      Object.entries(storage).forEach(([key, value]) => window.localStorage.setItem(key, value));
      window.matchMedia = query => ({ matches: systemDark && query.includes("dark") });
    },
  });
  contexts.push(ctx);
  return ctx;
}

describe("first paint", () => {
  it.each([
    [{ theme: "dark" }, false, true],
    [{ theme: "light" }, true, false],
    [{}, true, true],
    [{}, false, false],
  ])("paints the stored theme, else the system's: %o system dark %s", (storage, systemDark, dark) => {
    const { document } = paint({ storage, systemDark });
    expect(document.body.classList.contains("dark-mode")).toBe(dark);
  });

  it("starts a reload that ended in Agent with Agent's composer words", () => {
    const { document } = paint({ storage: { id_token: "cached-token", agentShellExpected: "1" } });
    expect(document.getElementById("questionInput").placeholder).toBe("Ask anything, or paste an AI answer to check it");
  });

  it("starts a guest with the sign-in words and a restoring Consensus session with the template's", () => {
    expect(paint().document.getElementById("questionInput").placeholder).toBe("Sign in to start asking questions for free.");
    expect(paint({ storage: { id_token: "cached-token" } }).document.getElementById("questionInput").placeholder)
      .toBe("Enter your question");
  });
});

describe("loading lifecycle", () => {
  it.each([{ known: true, uid: "user" }, { known: true, uid: null }])(
    "does not overwrite an already resolved session with cached-token placeholders: %o", state => {
      const { document } = boot(state);
      expect(document.querySelector(".skeleton")).toBeNull();
    });

  it("exposes one named chat loading status and hides its decorative lines", () => {
    const { document } = boot({ known: false });
    expect(document.querySelector('.bookmarks-skeleton[role="status"]').getAttribute("aria-label")).toBe("Loading chats");
    expect(document.querySelectorAll('.skeleton-bookmark[aria-hidden="true"]')).toHaveLength(4);
    expect(document.querySelector('#loginContainer [role="status"]').closest('[aria-hidden="true"]')).toBeNull();
  });

  it.each([{ bookmarks: [] }, { bookmarks: [{ id: "saved" }] }])("keeps chat placeholders through the request and removes them on success: %o", async ({ bookmarks }) => {
    const { window, document } = boot({ known: false });
    const source = readFileSync(path.join(ROOT, "static/firebase.js"), "utf8");
    const load = source.slice(source.indexOf("async function loadBookmarks("), source.indexOf("async function loadBookmarkDetail("));
    let respond;
    const response = new Promise(resolve => { respond = resolve; });
    const create = Function("window", "document", "fetch", `
      const auth = {currentUser: {uid: 'user', getIdToken: async () => 'token'}};
      const authState = {generation: 1};
      let bookmarksLoading = false, bookmarksLoadRequestId = 0, bookmarksNextCursor = null;
      const isCurrentAuthenticatedUser = () => true;
      const ensurePendingBookmarkDOM = () => {};
      const restoreRegistryRunRows = () => {};
      const renderBookmarksLoadMore = () => {};
      const upsertBookmarkMeta = item => { const row = document.createElement('div'); row.className = 'bookmark'; row.textContent = item.id; document.getElementById('bookmarksContainer').append(row); };
      const renderBookmarksLoadError = () => { throw new Error('Unexpected load failure'); };
      ${load}
      return loadBookmarks;
    `);
    window.App = {};
    const request = create(window, document, () => response)();
    await Promise.resolve();
    expect(document.querySelector(".bookmarks-skeleton")).not.toBeNull();
    respond({ ok: true, json: async () => ({ bookmarks }) });
    expect(await request).toBe(true);
    expect(document.querySelector(".bookmarks-skeleton")).toBeNull();
    expect(document.querySelectorAll(".bookmark")).toHaveLength(bookmarks.length);
  });
});
