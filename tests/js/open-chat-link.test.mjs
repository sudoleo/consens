import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import { ROOT } from "./helpers/appWindow.mjs";

/**
 * A Watch's mail links its chat as /app?chat=<bookmark> (firebase.js,
 * openChatFromLink). Signed out, the login comes first; a password or Google
 * popup login then reloads the page without ?chat (continueSignedIn), and
 * Firebase tells the listeners of the sign-in before that reload. The block
 * is cut out of firebase.js (an ES module with Firebase imports) and run
 * against stand-ins, one run per page load, sharing the tab's sessionStorage.
 */
function storage() {
  const items = new Map();
  return {
    getItem: key => (items.has(key) ? items.get(key) : null),
    setItem: (key, value) => { items.set(key, String(value)); },
    removeItem: key => { items.delete(key); },
  };
}

function pageLoad(href, sessionStorage) {
  const source = readFileSync(path.join(ROOT, "static/firebase.js"), "utf8");
  const start = source.indexOf("(function openChatFromLink() {");
  const end = source.indexOf("// Back from the password-setup e-mail", start);
  expect(start).toBeGreaterThan(-1);
  expect(end).toBeGreaterThan(start);
  const opened = [];
  const dialogs = [];
  let listener = () => {};
  const window = {
    location: { href },
    history: { state: null, replaceState(_state, _title, next) { window.location.href = new URL(next, href).href; } },
    openBookmark: id => { opened.push(id); },
  };
  Function("window", "sessionStorage", "onAuthStateChanged", "auth", "showAuthModal", "loginNoticeEl",
    source.slice(start, end))(
    window, sessionStorage, (_auth, callback) => { listener = callback; }, {},
    mode => { dialogs.push(mode); }, { textContent: "" });
  return { opened, dialogs, window, auth: user => listener(user) };
}

const KEY = "consensio:open-chat";
const user = { uid: "u1" };

describe("a chat link from a Watch's mail", () => {
  it("opens the chat on the fresh page a login on this page reloads to", () => {
    const tab = storage();
    const linked = pageLoad("https://www.consens.io/app?chat=abc_123", tab);
    expect(linked.window.location.href).toBe("https://www.consens.io/app");
    linked.auth(null);
    expect(linked.dialogs).toEqual(["login"]);
    linked.auth(user);
    // continueSignedIn() reloads to /app: the fresh page finds the chat kept.
    const fresh = pageLoad("https://www.consens.io/app", tab);
    fresh.auth(user);
    expect(fresh.opened).toEqual(["abc_123"]);
    expect(tab.getItem(KEY)).toBeNull();
  });

  it("opens at once and keeps nothing when the browser is signed in already", () => {
    const tab = storage();
    const linked = pageLoad("https://www.consens.io/app?chat=abc_123", tab);
    linked.auth(user);
    expect(linked.opened).toEqual(["abc_123"]);
    expect(linked.dialogs).toEqual([]);
    expect(tab.getItem(KEY)).toBeNull();
  });
});
