import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it, vi } from "vitest";

import { ROOT } from "./helpers/appWindow.mjs";

/**
 * A deletion still offering its Undo when the reader logs out happens before
 * the account's token goes: chats, a watch and a project alike; without the
 * token the request never leaves and the thing comes back at the next login.
 * performLogout is cut out of firebase.js (an ES module with
 * Firebase imports) and run against stand-ins, like the bookmark write queue.
 */
function logoutHarness({ watchCommit, projectSettle = () => Promise.resolve() }) {
  const source = readFileSync(path.join(ROOT, "static/firebase.js"), "utf8");
  const start = source.indexOf("async function performLogout()");
  const end = source.indexOf("async function openLogoutConfirm()", start);
  const events = [];
  const window = {
    App: {
      userSettings: { flush: () => Promise.resolve(true) },
      runRegistry: { cancelAll: () => events.push("cancel-runs") },
      watchDashboard: { commitPending: () => { events.push("watch-commit"); return watchCommit(); } },
      chatProjects: { settle: () => { events.push("project-settle"); return projectSettle(); } },
      toast: vi.fn(),
    },
  };
  const performLogout = Function(
    "window", "trackAppEvent", "settleUndoableBookmarkDeletes", "fetch", "signOut", "auth",
    "setActiveAuthIdentity", "resetLoadedRunAfterLogout", "clearAuthenticatedUiState", "clearLocalProviderKeys",
    `${source.slice(start, end)}\nreturn performLogout;`
  )(
    window,
    () => {},
    () => { events.push("chat-deletes"); return Promise.resolve(); },
    async () => ({ ok: true }),
    async () => { events.push("sign-out"); },
    {},
    () => {},
    () => events.push("reset-ui"),
    () => {},
    () => {}
  );
  return { performLogout, events, window };
}

describe("logout with a deletion still pending", () => {
  it("sends the watch's DELETE and waits for it before signing out", async () => {
    let answer;
    const { performLogout, events } = logoutHarness({
      watchCommit: () => new Promise(resolve => { answer = () => { events.push("watch-deleted"); resolve(); }; }),
    });
    const loggingOut = performLogout();
    await vi.waitFor(() => expect(typeof answer).toBe("function"));
    await new Promise(resolve => setTimeout(resolve, 5));
    expect(events).not.toContain("sign-out");
    answer();
    await loggingOut;
    expect(events.indexOf("watch-commit")).toBeGreaterThanOrEqual(0);
    expect(events.indexOf("watch-deleted")).toBeLessThan(events.indexOf("sign-out"));
    expect(events.indexOf("chat-deletes")).toBeLessThan(events.indexOf("sign-out"));
  });

  it("sends a deleted project's DELETE and waits for it before signing out", async () => {
    let answer;
    const { performLogout, events } = logoutHarness({
      watchCommit: () => Promise.resolve(),
      projectSettle: () => new Promise(resolve => { answer = () => { events.push("project-deleted"); resolve(); }; }),
    });
    const loggingOut = performLogout();
    await vi.waitFor(() => expect(typeof answer).toBe("function"));
    await new Promise(resolve => setTimeout(resolve, 5));
    expect(events).not.toContain("sign-out");
    answer();
    await loggingOut;
    expect(events.indexOf("project-deleted")).toBeLessThan(events.indexOf("sign-out"));
  });

  it("signs out after at most three seconds when the DELETE hangs", async () => {
    vi.useFakeTimers();
    try {
      const { performLogout, events } = logoutHarness({ watchCommit: () => new Promise(() => {}) });
      const loggingOut = performLogout();
      await vi.advanceTimersByTimeAsync(3100);
      await loggingOut;
      expect(events).toContain("sign-out");
    } finally {
      vi.useRealTimers();
    }
  });
});
