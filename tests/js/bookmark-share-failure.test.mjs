import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it, vi } from "vitest";

import { loadScripts, ROOT } from "./helpers/appWindow.mjs";

/**
 * Share and Watch of a saved chat never end at a dead "Saved consensus
 * unavailable" button (Apple-Audit follow-up): the sidebar menu offers Share
 * only for a chat with a saved answer (a Consensus or, since 2026-10-21, an
 * Agent answer), and a preparation the server refuses is shown with the
 * server's reason.
 */
const FIREBASE = readFileSync(path.join(ROOT, "static/firebase.js"), "utf8");

function slice(start, end) {
  const from = FIREBASE.indexOf(start);
  return FIREBASE.slice(from, FIREBASE.indexOf(end, from));
}

describe("Share in the chat menu", () => {
  const shareable = Function(`${slice("function bookmarkShareable(", "function labelBookmarkMenu(")}
    return bookmarkShareable;`)();

  it("is offered for a saved answer only", () => {
    expect(shareable({ id: "c", mode: "Standard", has_consensus: true })).toBe(true);
    // An Agent answer is shared by its turn (share-dialog.js, agent.py).
    expect(shareable({ id: "a", mode: "Agent", has_consensus: true })).toBe(true);
    // A direct comparison has no answer to share.
    expect(shareable({ id: "d", mode: "Standard", has_consensus: false })).toBe(false);
    expect(shareable(undefined)).toBe(false);
  });
});

describe("preparing a saved chat for Share or Watch", () => {
  function harness(response) {
    const { window: app } = loadScripts([]);
    const win = { App: { state: { set: (key, value) => { win[key] = value; } },
                         readJson: app.App.readJson, httpError: app.App.httpError, userError: app.App.userError } };
    const fetch = vi.fn(async () => response);
    const api = Function("window", "auth", "authState", "enqueueBookmarkWrite", "bookmarkWriteAllowed",
      "isCurrentAuthenticatedUser", "fetch", "console",
      `${slice("let bookmarkShareResultVersion = 0;", "function bookmarkModelPresentation(")}
      return { prepareBookmarkShareResult };`)(
      win, { currentUser: { uid: "owner", getIdToken: async () => "token" } }, { generation: 1 },
      (_uid, _generation, _id, job) => job(), () => true, () => true, fetch, { error() {} });
    return { win, api, fetch };
  }
  const refused = (status, body) => ({ ok: false, status, headers: { get: () => null },
                                       text: async () => JSON.stringify(body) });

  it("keeps the server's reason for the dialogs, and forgets it with the chat", async () => {
    const { win, api } = harness(refused(409, { detail: "Bookmark changed. Reopen it before sharing." }));
    api.prepareBookmarkShareResult({ id: "saved", query: "Q", responses: { consensus: "Answer" } });

    expect(await win.resolveCurrentShareResultId()).toBeNull();
    expect(win.currentBookmarkShareResultError).toBe("Bookmark changed. Reopen it before sharing.");
    win.clearPreparedBookmarkShareResult();
    expect(win.currentBookmarkShareResultError).toBe("");
  });

  it("words a refusal without a sentence of its own", async () => {
    const { win, api } = harness({ ok: false, status: 409, headers: { get: () => null }, text: async () => "" });
    api.prepareBookmarkShareResult({ id: "saved", query: "Q", responses: { consensus: "Answer" } });

    expect(await win.resolveCurrentShareResultId()).toBeNull();
    expect(win.currentBookmarkShareResultError).toBe("This chat couldn’t be prepared. Try again.");
  });
});

const SHELL = `
  <dialog id="shareModal" class="modal">
    <div class="modal-content share-modal-content">
      <button type="button" class="close close-button" id="closeShareModal" aria-label="Close dialog"></button>
      <h2 id="shareModalTitle"></h2>
      <div id="shareModalBody"></div>
    </div>
  </dialog>`;
const REASON = "This saved consensus can no longer be shared. Ask the question again to share it.";

function dialogs() {
  const resolve = vi.fn(async () => null);
  const harness = loadScripts(
    ["static/js/motion.js", "static/js/modal-dialog.js", "static/js/popover.js", "static/js/notices.js",
      "static/js/watch-state.js", "static/js/share-dialog.js", "static/js/watch-fields.js", "static/js/watch.js"],
    {
      body: SHELL,
      before(window) {
        window.App = { watch: {}, showPopup: vi.fn(), trackAppEvent: vi.fn(), openAuthModal: vi.fn() };
        window.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} });
        window.auth = { currentUser: { uid: "owner", getIdToken: async () => "token" } };
        window.__consensioAuthState = { known: true, uid: "owner" };
        window.lastQuestion = "Is the heat pump worth it in an old house?";
        // A reopened saved chat whose preparation the server refuses.
        window.currentBookmarkShareResultContext = { bookmarkId: "saved", versionParts: [] };
        window.resolveCurrentShareResultId = async () => {
          window.currentBookmarkShareResultError = REASON;
          return resolve();
        };
        window.fetch = vi.fn(async input => ({
          ok: true, status: 200, headers: { get: () => null },
          json: async () => String(input) === "/api/my/watches"
            ? { watches: [], limits: { plan: "pro", active_count: 0, active_limit: 10 } }
            : String(input) === "/api/watch/goal-suggestions" ? { goals: [] } : {}
        }));
      }
    }
  );
  return { ...harness, resolve };
}

const settle = () => new Promise(resolve => setTimeout(resolve, 0));

describe("a refused preparation in the dialogs", () => {
  it("Share says why and lets the reader try again", async () => {
    const { window, document, resolve } = dialogs();
    window.openShareDialog();
    await vi.waitFor(() => expect(document.getElementById("shareDialogError").hidden).toBe(false));

    const button = document.getElementById("shareConfirmBtn");
    expect(document.getElementById("shareDialogError").textContent).toBe(REASON);
    expect(button.textContent).toBe("Try again");
    expect(button.disabled).toBe(false);
    expect(document.getElementById("shareModalBody").textContent).not.toContain("unavailable");

    button.click();
    await settle();
    expect(resolve).toHaveBeenCalledTimes(2);
    expect(button.disabled).toBe(false);
    expect(window.App.showPopup).not.toHaveBeenCalled();
  });

  it("Share offers no button a refusal that stays cannot pass", async () => {
    const { window, document } = dialogs();
    window.currentBookmarkShareResultContext.error = Object.assign(new Error(REASON),
      { name: "HttpError", status: 409, serverMessage: REASON });
    window.openShareDialog();
    await vi.waitFor(() => expect(document.getElementById("shareDialogError").hidden).toBe(false));

    expect(document.getElementById("shareDialogError").textContent).toBe(REASON);
    expect(document.getElementById("shareConfirmBtn").hidden).toBe(true);
  });

  it("Watch says why and lets the reader try again", async () => {
    const { window, document, resolve } = dialogs();
    window.openWatchDialog("confirm");
    await vi.waitFor(() => expect(document.getElementById("watchDialogError").hidden).toBe(false));

    const button = document.getElementById("watchConfirmBtn");
    expect(document.getElementById("watchDialogError").textContent).toBe(REASON);
    expect(button.textContent).toBe("Start watching");
    expect(button.disabled).toBe(false);

    button.click();
    await settle();
    expect(resolve).toHaveBeenCalledTimes(2);
    expect(document.getElementById("watchDialogError").textContent).toBe(REASON);
    expect(window.fetch.mock.calls.some(([url, options]) => url === "/api/watch" && options?.method === "POST")).toBe(false);
  });
});
