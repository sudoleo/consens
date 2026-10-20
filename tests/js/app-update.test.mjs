import { describe, expect, it, vi } from "vitest";
import { VirtualConsole } from "jsdom";
import { loadScripts } from "./helpers/appWindow.mjs";

const OWN = "aaaaaaa";
const NEW = "bbbbbbb";
const RESTORE_KEY = "consens.appUpdate.restore";
const ATTEMPT_KEY = "consens.appUpdate.attempt";

function boot({ own = OWN, live = NEW, hidden = false, session = {}, deferFetch = false, before } = {}) {
  const state = {
    hidden, live, active: 0, run: null, identity: null, uid: "u1",
    reloads: 0, fetches: 0, opened: [], tracked: [], release: null,
  };
  const virtualConsole = new VirtualConsole();
  virtualConsole.on("jsdomError", error => {
    if (/navigation/i.test(error.message)) state.reloads += 1;
  });
  const { window } = loadScripts(["static/js/app-update.js"], {
    virtualConsole,
    body: `<style>.modal{display:none}</style>
      <meta id="appBootstrapConfig" data-app-build="${own}">
      <textarea id="questionInput"></textarea>
      <dialog id="loginModal" class="modal"></dialog>
      <div id="watchDashboard" hidden></div>`,
    before(window) {
      window.document.body.classList.add("is-hero");
      Object.defineProperty(window.document, "hidden", { configurable: true, get: () => state.hidden });
      Object.entries(session).forEach(([key, value]) => window.sessionStorage.setItem(key, JSON.stringify(value)));
      window.fetch = () => {
        state.fetches += 1;
        const answer = () => ({ ok: true, json: async () => ({ build: state.live }) });
        if (!deferFetch) return Promise.resolve(answer());
        return new Promise(resolve => { state.release = () => resolve(answer()); });
      };
      window.openBookmark = id => { state.opened.push(id); };
      window.App = {
        runRegistry: {
          activeCount: () => state.active,
          visible: () => state.run,
          getSelectedConversationIdentity: () => state.identity,
        },
        authState: { get uid() { return state.uid; } },
        trackAppEvent: (name, data) => state.tracked.push([name, data]),
      };
      before?.(window);
    },
  });
  const flip = next => {
    state.hidden = next;
    window.document.dispatchEvent(new window.Event("visibilitychange"));
  };
  return {
    window,
    state,
    leave: () => flip(true),
    come: () => flip(false),
    check: options => window.App.appUpdate.check(options),
    stored: key => JSON.parse(window.sessionStorage.getItem(key) || "null"),
  };
}

const settle = () => new Promise(resolve => setTimeout(resolve, 0));

describe("app update", () => {
  it("loads a newer build in the background once the page is left", async () => {
    const app = boot();
    app.leave();
    await settle();
    expect(app.state.reloads).toBe(1);
    expect(app.stored(RESTORE_KEY)).toMatchObject({ from: OWN, uid: "u1", bookmarkId: "" });
    expect(app.stored(ATTEMPT_KEY)).toMatchObject({ build: NEW });
  });

  it("leaves a page alone that already runs the live build", async () => {
    const app = boot({ live: OWN });
    app.leave();
    await settle();
    expect(app.state.fetches).toBe(1);
    expect(app.state.reloads).toBe(0);
  });

  it("never reloads under someone using the page; it waits until they leave", async () => {
    const app = boot();
    await app.check({ force: true });
    expect(app.state.reloads).toBe(0);
    app.leave();
    await settle();
    expect(app.state.reloads).toBe(1);
  });

  it("reloads as the page comes back, but not once the first click landed", async () => {
    const quick = boot({ hidden: true });
    quick.come();
    await settle();
    expect(quick.state.reloads).toBe(1);

    const busy = boot({ hidden: true, deferFetch: true });
    busy.come();
    busy.window.dispatchEvent(new busy.window.Event("pointerdown"));
    busy.state.release();
    await settle();
    expect(busy.state.reloads).toBe(0);
  });

  it.each([
    ["a run is still going", app => { app.state.active = 1; }],
    ["the composer holds a draft", app => { app.window.document.getElementById("questionInput").value = "half a question"; }],
    ["a file waits in the composer", app => { app.window.pendingAttachments = [{ name: "a.pdf" }]; }],
    ["a dialog is open", app => { app.window.document.getElementById("loginModal").setAttribute("open", ""); }],
    ["a result is on screen that is not saved", app => {
      app.window.document.body.classList.remove("is-hero");
      app.state.run = { status: "succeeded" };
    }],
    ["a failed run is on screen", app => {
      app.window.document.body.classList.remove("is-hero");
      app.state.run = { status: "failed" };
      app.state.identity = { bookmarkId: "b1" };
    }],
  ])("keeps the old build while %s", async (_, arrange) => {
    const app = boot();
    arrange(app);
    app.leave();
    await settle();
    expect(app.state.reloads).toBe(0);
  });

  it("remembers the open saved chat for after the reload", async () => {
    const app = boot();
    app.window.document.body.classList.remove("is-hero");
    app.state.run = { status: "succeeded" };
    app.state.identity = { bookmarkId: "b1" };
    app.leave();
    await settle();
    expect(app.state.reloads).toBe(1);
    expect(app.stored(RESTORE_KEY)).toMatchObject({ uid: "u1", bookmarkId: "b1" });
  });

  it("does not try the same build again right away when the reload brought the old one", async () => {
    const app = boot({ session: { [ATTEMPT_KEY]: { build: NEW, at: Date.now() } } });
    app.leave();
    await settle();
    expect(app.state.reloads).toBe(0);
  });

  it("asks nothing without a build of its own", async () => {
    const app = boot({ own: "" });
    app.leave();
    app.come();
    await settle();
    expect(app.state.fetches).toBe(0);
    expect(app.state.reloads).toBe(0);
  });

  it("reopens the saved chat once the same account is signed in again", async () => {
    const record = { from: "0000000", at: Date.now(), uid: "u1", bookmarkId: "b1" };
    const app = boot({ session: { [RESTORE_KEY]: record } });
    expect(app.stored(RESTORE_KEY)).toBeNull();
    app.window.dispatchEvent(new app.window.CustomEvent("consensio:auth-state", { detail: { known: true, uid: "u1" } }));
    expect(app.state.opened).toEqual(["b1"]);
    await vi.waitFor(() => expect(app.state.tracked).toEqual([["app_updated", { reopened: true }]]));
  });

  it("reopens the chat when the sign-in was published before this module ran", async () => {
    // firebase.js (a module) can finish restoring the session while the app
    // bundle is still loading: its consensio:auth-state event has gone by.
    const record = { from: "0000000", at: Date.now(), uid: "u1", bookmarkId: "b1" };
    const app = boot({
      session: { [RESTORE_KEY]: record },
      before(window) { window.__consensioAuthState = Object.freeze({ known: true, uid: "u1", generation: 1 }); },
    });
    expect(app.state.opened).toEqual([]);
    await vi.waitFor(() => expect(app.state.opened).toEqual(["b1"]));
    // A late event for the same sign-in does not open it twice.
    app.window.dispatchEvent(new app.window.CustomEvent("consensio:auth-state", { detail: { known: true, uid: "u1" } }));
    await settle();
    expect(app.state.opened).toEqual(["b1"]);
  });

  it("does not reopen a chat for another account or after the user moved on", () => {
    const record = { from: "0000000", at: Date.now(), uid: "u1", bookmarkId: "b1" };
    const other = boot({ session: { [RESTORE_KEY]: record } });
    other.window.dispatchEvent(new other.window.CustomEvent("consensio:auth-state", { detail: { known: true, uid: "u2" } }));
    expect(other.state.opened).toEqual([]);

    const typed = boot({ session: { [RESTORE_KEY]: record } });
    typed.window.document.getElementById("questionInput").value = "new question";
    typed.window.dispatchEvent(new typed.window.CustomEvent("consensio:auth-state", { detail: { known: true, uid: "u1" } }));
    expect(typed.state.opened).toEqual([]);

    const stale = boot({ session: { [RESTORE_KEY]: { ...record, at: Date.now() - 10 * 60 * 1000 } } });
    stale.window.dispatchEvent(new stale.window.CustomEvent("consensio:auth-state", { detail: { known: true, uid: "u1" } }));
    expect(stale.state.opened).toEqual([]);
  });
});
