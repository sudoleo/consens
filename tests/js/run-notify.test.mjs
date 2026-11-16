import { afterEach, describe, expect, it } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

// static/js/run-notify.js: a system notification when a run ends or waits
// for the reader while the page is hidden; the offer in the live line and
// the switch in Settings. The run states are tab-status.js's.
const SETTINGS = `
  <div class="settings-group">
    <div class="settings-section" id="runNotifySetting" hidden>
      <label for="runNotifySwitch"><span><strong>Notify me when it’s done</strong></span>
        <input type="checkbox" id="runNotifySwitch" aria-describedby="runNotifyPermission"></label>
      <p id="runNotifyPermission"></p>
    </div>
  </div>`;
const PREF = "consensio.runNotify.v1";
const OFFERS = "consensio.runNotify.offers.v1";
const contexts = [];
afterEach(() => contexts.splice(0).forEach(ctx => ctx.window.close()));

function boot({ permission = "default", answer = "granted", notification = true, agent = null, storage = {},
  touch = 0, secure = true, refuse = false } = {}) {
  const runs = new Map();
  let visibleId = null;
  let hidden = false;
  const calls = { notes: [], opened: [], shown: [], updates: [], events: [], focus: 0 };
  const ctx = loadScripts(["static/js/tab-status.js", "static/js/run-notify.js"], {
    body: SETTINGS,
    before(window) {
      Object.entries(storage).forEach(([key, value]) => window.localStorage.setItem(key, value));
      Object.defineProperty(window, "isSecureContext", { configurable: true, value: secure });
      Object.defineProperty(window.document, "hidden", { configurable: true, get: () => hidden });
      if (agent) Object.defineProperty(window.navigator, "userAgent", { configurable: true, value: agent });
      Object.defineProperty(window.navigator, "maxTouchPoints", { configurable: true, value: touch });
      if (notification) {
        window.Notification = class {
          constructor(title, options) {
            if (refuse) throw new TypeError("Illegal constructor");
            Object.assign(this, { title, ...options, closed: false });
            calls.notes.push(this);
          }
          close() { this.closed = true; this.onclose?.(); }
          static requestPermission() { window.Notification.permission = answer; return Promise.resolve(answer); }
        };
        window.Notification.permission = permission;
      }
      window.focus = () => { calls.focus += 1; };
      window.openBookmark = id => calls.opened.push(id);
      window.App = {
        t: text => text,
        lang: "en",
        trackAppEvent: (name, data) => calls.events.push([name, data]),
        runRegistry: {
          list: () => [...runs.values()],
          get: id => runs.get(id) || null,
          visible: () => runs.get(visibleId) || null,
          isVisible: id => id === visibleId,
          isExecuting: id => ["starting", "running"].includes(runs.get(id)?.status),
          update: id => calls.updates.push(id),
          show: id => { visibleId = id; calls.shown.push(id); },
        },
      };
    },
  });
  contexts.push(ctx);
  ctx.document.dispatchEvent(new ctx.window.Event("DOMContentLoaded"));
  const { window } = ctx;
  const emit = () => window.dispatchEvent(new window.CustomEvent("consensio:run-registry-change"));
  return {
    ...ctx,
    calls,
    notify: window.App.runNotify,
    run(id, status, { metadata = {}, title = "Price of gold", temporary = false, visible = true } = {}) {
      const run = runs.get(id) || { runId: id, startedAt: Date.now(), config: { executionMode: "agent" }, bookmark: {} };
      Object.assign(run, { status, metadata, question: title });
      run.bookmark = { id: `b_${id}`, title };
      run.config = { ...run.config, temporary };
      runs.set(id, run);
      if (visible) visibleId = id;
      emit();
      return run;
    },
    hide() { hidden = true; window.document.dispatchEvent(new window.Event("visibilitychange")); },
    show() { hidden = false; window.document.dispatchEvent(new window.Event("visibilitychange")); },
  };
}
const flush = () => new Promise(resolve => setTimeout(resolve, 0));

describe("where a page may notify", () => {
  it.each([
    ["no Notification at all", { notification: false }],
    ["Chrome on Android, which wants a service worker", { agent: "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Mobile Safari/537.36" }],
    ["an iPhone", { agent: "Mozilla/5.0 (iPhone; CPU iPhone OS 19_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.0 Mobile/15E148 Safari/604.1" }],
    ["an iPad that names itself a Mac", { agent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.0 Safari/605.1.15", touch: 5 }],
    ["a page that is not secure", { secure: false }],
  ])("offers nothing and shows no switch with %s", (_, options) => {
    const app = boot(options);
    expect(app.notify.permission()).toBe("unsupported");
    expect(app.notify.offer("r1", 60000)).toBeNull();
    expect(app.document.getElementById("runNotifySetting").hidden).toBe(true);
  });

  it("has them on a desktop browser, a Mac's Safari included", () => {
    const mac = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.0 Safari/605.1.15";
    expect(boot({ agent: mac }).notify.permission()).toBe("default");
    expect(boot().document.getElementById("runNotifySetting").hidden).toBe(false);
  });
});

describe("the offer in the live line", () => {
  it("comes after 20 s while the browser has not decided, never before and never after a decision", () => {
    expect(boot().notify.offer("r1", 19999)).toBeNull();
    expect(boot().notify.offer("r1", 20000)).toBe("ask");
    expect(boot({ permission: "denied" }).notify.offer("r1", 60000)).toBeNull();
    expect(boot({ permission: "granted" }).notify.offer("r1", 60000)).toBeNull();
    expect(boot({ storage: { [PREF]: "off" } }).notify.offer("r1", 60000)).toBeNull();
  });

  it("stops offering after three runs nobody took it on", () => {
    const app = boot();
    expect(["r1", "r1", "r2", "r3"].map(id => app.notify.offer(id, 30000))).toEqual(["ask", "ask", "ask", "ask"]);
    expect(app.notify.offer("r4", 30000)).toBeNull();
    expect(app.window.localStorage.getItem(OFFERS)).toBe("3");
  });

  it("asks the browser only on its click, then says what it set up", async () => {
    const app = boot();
    app.run("r1", "running");
    expect(app.notify.offer("r1", 25000)).toBe("ask");
    expect(await app.notify.ask("offer", "r1")).toBe("granted");
    expect(app.notify.offer("r1", 26000)).toBe("set");
    expect(app.window.localStorage.getItem(PREF)).toBe("on");
    expect(app.calls.events).toEqual([["app_run_notify", { source: "offer", result: "granted" }]]);
    // The live line draws the new state at once.
    expect(app.calls.updates).toContain("r1");
  });

  it("goes for this run when the browser's question is closed or refused", async () => {
    const app = boot({ answer: "default" });
    expect(app.notify.offer("r1", 25000)).toBe("ask");
    expect(await app.notify.ask("offer", "r1")).toBe("default");
    expect(app.notify.offer("r1", 26000)).toBeNull();
  });
});

describe("the notification", () => {
  it("says once that the answer is ready, with the chat's title, when the run ends while the page is hidden", () => {
    const app = boot({ permission: "granted" });
    app.run("r1", "running");
    app.hide();
    app.run("r1", "running", { metadata: { agentReview: { status: "running" } } });
    expect(app.calls.notes).toHaveLength(0);
    app.run("r1", "succeeded");
    // The reviewers' marks after the answer are no news.
    app.run("r1", "succeeded", { metadata: { agentReview: { status: "succeeded" } } });
    expect(app.calls.notes).toHaveLength(1);
    expect(app.calls.notes[0]).toMatchObject({ title: "Price of gold", body: "Your answer is ready.", tag: "consens-run-r1" });
  });

  it("says that a run waits for the reader, and how it ended, in one place per run", () => {
    const app = boot({ permission: "granted" });
    app.run("r1", "running");
    app.hide();
    app.run("r1", "running", { metadata: { hold: { id: "h1", ask: "browser" } } });
    app.run("r1", "running", { metadata: { hold: { id: "h1", ask: "browser" } } });
    app.run("r2", "running", { visible: false });
    app.run("r2", "running", { metadata: { hold: { id: "h2" } }, visible: false });
    app.run("r2", "failed", { metadata: { hold: { id: "h2" } }, visible: false });
    expect(app.calls.notes.map(note => [note.tag, note.body])).toEqual([
      ["consens-run-r1", "The Agent is waiting for you."],
      ["consens-run-r2", "Waiting for your decision."],
      ["consens-run-r2", "The answer couldn’t be completed."],
    ]);
  });

  it("names no temporary chat, whose title is its question", () => {
    const app = boot({ permission: "granted" });
    app.run("r1", "running", { temporary: true, title: "My rash" });
    app.hide();
    app.run("r1", "succeeded", { temporary: true, title: "My rash" });
    expect(app.calls.notes[0]).toMatchObject({ title: "Temporary chat", body: "Your answer is ready." });
  });

  it("says nothing while the page is in front, for a run done before it was left, or once switched off", () => {
    const front = boot({ permission: "granted" });
    front.run("r1", "running");
    front.run("r1", "succeeded");
    front.hide();
    expect(front.calls.notes).toHaveLength(0);
    const off = boot({ permission: "granted", storage: { [PREF]: "off" } });
    off.run("r1", "running");
    off.hide();
    off.run("r1", "succeeded");
    expect(off.calls.notes).toHaveLength(0);
    const unasked = boot();
    unasked.run("r1", "running");
    unasked.hide();
    unasked.run("r1", "succeeded");
    expect(unasked.calls.notes).toHaveLength(0);
  });

  it("brings the tab to the front with that chat, and goes once the page is back", () => {
    const app = boot({ permission: "granted" });
    app.run("r1", "running", { visible: false });
    app.hide();
    app.run("r1", "succeeded", { visible: false });
    app.calls.notes[0].onclick();
    expect(app.calls.focus).toBe(1);
    expect(app.calls.opened).toEqual(["b_r1"]);
    expect(app.calls.notes[0].closed).toBe(true);
    const visible = boot({ permission: "granted" });
    visible.run("r1", "running");
    visible.hide();
    visible.run("r1", "succeeded");
    visible.show();
    expect(visible.calls.notes[0].closed).toBe(true);
    visible.calls.notes[0].onclick();
    expect(visible.calls.opened).toEqual([]);
  });

  it("gives up for good where the browser names the constructor but refuses it", () => {
    const app = boot({ permission: "granted", refuse: true });
    app.run("r1", "running");
    app.hide();
    app.run("r1", "succeeded");
    expect(app.notify.supported()).toBe(false);
    expect(app.document.getElementById("runNotifySetting").hidden).toBe(true);
  });
});

describe("the switch in Settings", () => {
  const parts = app => ({
    input: app.document.getElementById("runNotifySwitch"),
    note: app.document.getElementById("runNotifyPermission").textContent,
  });

  it("shows what the browser allows", () => {
    expect(parts(boot({ permission: "granted" }))).toMatchObject({ note: "Allowed in this browser." });
    expect(parts(boot({ permission: "granted" })).input.checked).toBe(true);
    expect(parts(boot()).input.checked).toBe(false);
    expect(parts(boot()).note).toBe("Your browser asks once when you switch it on.");
    const blocked = parts(boot({ permission: "denied" }));
    expect([blocked.input.checked, blocked.input.disabled, blocked.note])
      .toEqual([false, true, "Blocked in this browser’s site settings."]);
  });

  it("asks the browser when switched on, and holds an off on this device", async () => {
    const app = boot();
    const { input } = parts(app);
    input.checked = true;
    input.dispatchEvent(new app.window.Event("change"));
    await flush();
    expect(app.notify.enabled()).toBe(true);
    expect(parts(app)).toMatchObject({ note: "Allowed in this browser." });
    input.checked = false;
    input.dispatchEvent(new app.window.Event("change"));
    expect(app.notify.enabled()).toBe(false);
    expect(app.window.localStorage.getItem(PREF)).toBe("off");
    expect(app.calls.events.map(([, data]) => data)).toEqual([
      { source: "settings", result: "granted" }, { source: "settings", result: "off" }]);
  });
});
