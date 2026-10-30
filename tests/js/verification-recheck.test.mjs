import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import { ROOT } from "./helpers/appWindow.mjs";

/**
 * A signed-in account whose e-mail is not confirmed yet (firebase.js,
 * onIdTokenChanged): the handler rechecks once with User.reload(), then
 * shows the verification strip. Firebase's reload() fires onIdTokenChanged
 * again (User.reload -> _notifyListenersIfCurrent, the observer a microtask
 * later, before reload resolves); until 2026-10-30 that run reloaded once
 * more, without end: the composer was cleared and refilled, the strip drawn
 * anew and DELETE /auth/session sent several times a second. The handler and
 * the recheck are cut out of firebase.js (an ES module with Firebase
 * imports) and run against stand-ins, like the logout harness.
 */
function verificationHarness() {
  const source = readFileSync(path.join(ROOT, "static/firebase.js"), "utf8");
  const recheckStart = source.indexOf("async function refreshVerificationState()");
  const recheckEnd = source.indexOf("// Logging out asks first", recheckStart);
  const handlerStart = source.indexOf("onIdTokenChanged(auth, async (user) => {");
  const handlerEnd = source.indexOf("async function fetchUsageData(", handlerStart);
  const counts = { reloads: 0, deletes: 0, gates: 0, cleared: 0 };
  let handler = null;
  let gate = null;
  const user = {
    uid: "u1", email: "u1@example.invalid", emailVerified: false,
    async reload() {
      counts.reloads += 1;
      await new Promise(resolve => setTimeout(resolve, 2));
      // As Firebase: the listeners hear of it before reload() resolves.
      Promise.resolve().then(() => handler(auth.currentUser));
    },
    getIdToken: async () => "token",
  };
  const auth = { currentUser: user };
  const authState = {
    uid: null, generation: 0,
    setIdentity(uid) { if (uid !== this.uid) { this.uid = uid; this.generation += 1; } return this.generation; },
  };
  const window = { App: { userSettings: { stop() {} }, restoreQuestionDraft() {} } };
  const document = { getElementById: () => null };
  Function(
    "onIdTokenChanged", "auth", "authState", "window", "document", "fetch", "setActiveAuthIdentity",
    "resetLoadedRunAfterLogout", "clearAuthenticatedUiState", "clearLocalProviderKeys", "showEmailVerificationGate",
    "trackAppEvent", "setBookmarksAccess", "publishAuthState", "sendVerificationMail", "signOut",
    `${source.slice(recheckStart, recheckEnd)}\n${source.slice(handlerStart, handlerEnd)}`
  )(
    (_auth, callback) => { handler = callback; },
    auth, authState, window, document,
    async (url, options) => { if (url === "/auth/session" && options?.method === "DELETE") counts.deletes += 1; return { ok: true }; },
    uid => authState.setIdentity(uid),
    () => { counts.cleared += 1; },
    () => {},
    () => {},
    handlers => { counts.gates += 1; gate = handlers; },
    () => {},
    () => {},
    () => {},
    async () => {},
    async () => {}
  );
  return { counts, user, start: () => handler(user), gate: () => gate };
}

const settle = () => new Promise(resolve => setTimeout(resolve, 150));

describe("an account whose e-mail is not confirmed yet", () => {
  it("rechecks once and sets the strip up once, though reload() fires the handler again", async () => {
    const { counts, start } = verificationHarness();
    await start();
    await settle();
    expect(counts.reloads).toBe(1);
    expect(counts.deletes).toBe(1);
    expect(counts.gates).toBe(1);
    expect(counts.cleared).toBe(1);
  });

  it("rechecks once more for I've confirmed it, without clearing the page again", async () => {
    const { counts, start, gate } = verificationHarness();
    await start();
    await settle();
    expect(await gate().onRecheck()).toBe(false);
    await settle();
    expect(counts.reloads).toBe(2);
    expect(counts.deletes).toBe(1);
    expect(counts.gates).toBe(1);
  });
});
