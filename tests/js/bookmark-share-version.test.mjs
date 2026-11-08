import { webcrypto } from "node:crypto";
import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it, vi } from "vitest";

import { loadScripts, ROOT } from "./helpers/appWindow.mjs";

/**
 * Share and Watch of a reopened Consensus chat send the version the server
 * computes for the stored bookmark (`_bookmark_share_version`). The view is
 * drawn from the chat's transcript, whose texts the server serves
 * NFKC-folded and whose differences lack a Resolve result: hashed from the
 * view, every chat with "…", "CO₂" or a Resolve result ended at 409. The
 * fixture is shared with tests/test_bookmarks.py, which pins `version` to the
 * server's hash of `bookmark`.
 */
const FIREBASE = readFileSync(path.join(ROOT, "static/firebase.js"), "utf8");
const FIXTURE = JSON.parse(readFileSync(path.join(ROOT, "tests/fixtures/bookmark_share_version.json"), "utf8"));
const CHANGED = "Bookmark changed. Reopen it before sharing.";

function slice(start, end) {
  const from = FIREBASE.indexOf(start);
  return FIREBASE.slice(from, FIREBASE.indexOf(end, from));
}

// The server of this test: it knows only the version of the stored bookmark.
function server() {
  return vi.fn(async (_url, init) => {
    const { expectedVersion } = JSON.parse(init.body);
    const body = expectedVersion === FIXTURE.version
      ? { status: "success", result_id: "R".repeat(16), created: true }
      : { detail: CHANGED };
    return { ok: expectedVersion === FIXTURE.version, status: expectedVersion === FIXTURE.version ? 200 : 409,
             headers: { get: () => null }, text: async () => JSON.stringify(body) };
  });
}

function harness() {
  const { window: app } = loadScripts([]);
  const win = { App: { state: { set: (key, value) => { win[key] = value; } },
                       readJson: app.App.readJson, httpError: app.App.httpError, userError: app.App.userError } };
  const fetch = server();
  const api = Function("window", "auth", "authState", "enqueueBookmarkWrite", "bookmarkWriteAllowed",
    "isCurrentAuthenticatedUser", "patchCachedBookmark", "bookmarkDisplayQuestion", "bookmarkModelPresentation",
    "fetch", "console", "globalThis",
    `${slice("let bookmarkShareResultVersion = 0;", "function bookmarkModelPresentation(")}
    ${slice("function normalizeConversationTurn(turn) {", "async function loadBookmarkConversationOnce")}
    return { prepareBookmarkShareResult, materializeConversationBookmark };`)(
    win, { currentUser: { uid: "owner", getIdToken: async () => "token" } }, { generation: 1 },
    (_uid, _generation, _id, job) => job(), () => true, () => true, vi.fn(),
    bookmark => String(bookmark?.query || "").trim(), () => [], fetch, { error() {} },
    // The page has WebCrypto; a forked test process on Node 18 has it only here.
    { crypto: webcrypto });
  return { win, api, fetch };
}

// What loadSingleBookmarkUI does with a loaded bookmark and its transcript.
function open(api, turns) {
  const stored = structuredClone(FIXTURE.bookmark);
  const view = api.materializeConversationBookmark(stored, structuredClone(turns));
  api.prepareBookmarkShareResult(view.bookmark, stored);
  return view;
}

describe("sharing a reopened Consensus chat", () => {
  it("opens the view from the stored bookmark and its transcript", () => {
    const load = slice("function loadSingleBookmarkUI(", "// --- Quellen wiederherstellen ---");
    expect(load).toContain("materializeConversationBookmark(sourceBookmark, conversationTurns)");
    expect(load).toContain("prepareBookmarkShareResult(bookmark, sourceBookmark);");
  });

  it("sends the server's version of the stored bookmark, whatever NFKC does to its turn", async () => {
    const { win, api, fetch } = harness();
    // The transcript serves the texts folded: the view shows "CO2" and "...".
    expect(FIXTURE.turn.question).not.toBe(FIXTURE.bookmark.query);
    open(api, [FIXTURE.turn]);

    expect(await win.resolveCurrentShareResultId()).toBe("R".repeat(16));
    expect(JSON.parse(fetch.mock.calls[0][1].body).expectedVersion).toBe(FIXTURE.version);
    expect(win.currentBookmarkShareResultError).toBe("");
  });

  it("shows the Resolve result the stored bookmark keeps for its turn", () => {
    const { api } = harness();
    const view = open(api, [FIXTURE.turn]);

    const [difference] = view.bookmark.responses.differences_data.differences;
    expect(difference.resolution).toEqual(FIXTURE.bookmark.responses.differences_data.differences[0].resolution);
  });

  it("refuses a view of a newer turn than the bookmark names, and shows that turn's differences", async () => {
    const { win, api } = harness();
    const newer = {
      ...FIXTURE.turn, id: "c".repeat(32), position: 2, question: "And aluminium?",
      consensus: "About 16 t per tonne.", differences_data: { claims: [], differences: [] }
    };
    const view = open(api, [FIXTURE.turn, newer]);

    expect(view.bookmark.responses.differences_data).toEqual(newer.differences_data);
    expect(await win.resolveCurrentShareResultId()).toBeNull();
    expect(win.currentBookmarkShareResultError).toBe(CHANGED);
  });
});
