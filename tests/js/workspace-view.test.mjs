import { describe, expect, it, vi } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

// The account's workspace live (workspace-view.js): the panel signs in over
// its WebSocket's first message, hands the socket to noVNC on "ready", and a
// click on the screen takes the browser over until "Hand back" in the bar
// above the picture.
class FakeSocket {
  static last = null;
  constructor(url) {
    this.url = url;
    this.sent = [];
    this.closed = false;
    this.closeListeners = [];
    // Open (WebSocket.OPEN) from the start: the tests call onopen themselves.
    this.readyState = 1;
    FakeSocket.last = this;
  }
  send(data) { this.sent.push(data); }
  addEventListener(name, handler) { if (name === "close") this.closeListeners.push(handler); }
  close() { this.closed = true; this.onclose?.({ code: 1000 }); }
  // The server closes it: the handler first (noVNC's once it has the socket), then the listeners.
  closedBy(code) { this.onclose?.({ code }); for (const handler of this.closeListeners) handler({ code }); }
  // A message from the server.
  deliver(data) { this.onmessage?.({ data }); }
}

class FakeRFB {
  static made = [];
  constructor(target, channel, options) {
    Object.assign(this, { target, channel, options, viewOnly: false, focused: 0, disconnected: false });
    this.listeners = {};
    this.keys = [];
    // noVNC's canvas, where its keyboard listens.
    this.canvas = target.ownerDocument.createElement("canvas");
    this.canvas.tabIndex = -1;
    this.noVNCKeys = [];
    this.canvas.addEventListener("keydown", (event) => this.noVNCKeys.push(event.key));
    target.append(this.canvas);
    // noVNC takes over the socket's handlers at once (rfb.js _connect).
    channel.onmessage = (event) => { this.received = event.data; };
    FakeRFB.made.push(this);
  }
  addEventListener(name, handler) { this.listeners[name] = handler; }
  // As noVNC: nothing goes to the VM while only watching.
  sendKey(keysym, code, down) { if (!this.viewOnly) this.keys.push([keysym, down]); }
  focus() { this.focused += 1; this.canvas.focus(); }
  disconnect() { this.disconnected = true; }
}

// xterm.js as the panel uses it: a terminal of cols x rows, its keys through onData.
class FakeTerminal {
  static made = [];
  constructor(options) {
    Object.assign(this, { options, cols: 80, rows: 24, written: [], resets: 0, focused: 0 });
    FakeTerminal.made.push(this);
  }
  loadAddon(addon) { addon.term = this; this.addon = addon; }
  open(host) { this.host = host; }
  onData(handler) { this.type = handler; }
  write(bytes) { this.written.push(new TextDecoder().decode(bytes)); }
  focus() { this.focused += 1; }
  reset() { this.resets += 1; }
  dispose() { this.disposed = true; }
}
class FakeFit {
  fit() { if (this.size) Object.assign(this.term, this.size); }
}

function setup({ clipboard, prepare } = {}) {
  FakeSocket.last = null;
  FakeRFB.made = [];
  FakeTerminal.made = [];
  const app = loadScripts(["static/js/workspace-view.js"], {
    body: '<button id="composerWorkspaceButton"></button><button id="attachWorkspaceOption"></button>'
      + '<div id="agentWorkspaceSettings"></div>',
    before(window) {
      window.WebSocket = FakeSocket;
      // As every browser has them (jsdom does not): the terminal's keys go as bytes.
      window.TextEncoder = TextEncoder;
      window.auth = { currentUser: { uid: "u1", getIdToken: async () => "token" } };
      window.App = { t: (text, values) => text.replace(/\{(\w+)\}/g, (_, key) => values?.[key] ?? "") };
      window.fetch = vi.fn(async () => ({ ok: true, json: async () => ({}) }));
      if (clipboard) Object.defineProperty(window.navigator, "clipboard", { value: clipboard, configurable: true });
      prepare?.(window);
    },
  });
  const { window } = app;
  window.App.workspaceView._setLoader(async () => FakeRFB);
  window.App.workspaceView._setTerminalLoader(async () => ({ Terminal: FakeTerminal, FitAddon: FakeFit }));
  // As at DOMContentLoaded (jsdom may still be loading here); a second call changes nothing.
  window.App.workspaceView.init();
  window.App.workspaceView.init();
  return { window, document: app.document, workspace: window.App.workspaceView };
}

async function opened(env) {
  env.document.getElementById("composerWorkspaceButton").click();
  await vi.waitFor(() => expect(FakeSocket.last).not.toBeNull());
  const socket = FakeSocket.last;
  await socket.onopen();
  return socket;
}

function controls(window) {
  return window.fetch.mock.calls.filter(([path]) => path === "/agent/workspace/control")
    .map(([, options]) => JSON.parse(options.body).holder);
}

describe("the workspace's loading and terminal (2026-10-28)", () => {
  it("draws a skeleton of the browser while it loads and says so calmly when the first start takes long", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      const env = setup();
      const socket = await opened(env);
      const screen = env.document.querySelector("#workspacePane-browser");
      expect(screen.classList.contains("is-loading")).toBe(true);
      expect(screen.querySelector(".workspace-view-skeleton.is-browser").getAttribute("aria-hidden")).toBe("true");
      socket.deliver(JSON.stringify({ state: "connecting" }));
      await vi.advanceTimersByTimeAsync(6_500);
      const status = env.document.querySelector(".workspace-view-status");
      expect(status.textContent).toBe("Starting your workspace. The first start can take a minute.");
      socket.deliver(JSON.stringify({ state: "ready" }));
      expect(screen.classList.contains("is-loading")).toBe(false);
    } finally {
      vi.useRealTimers();
    }
  });

  it("opens the user's own terminal on its tab: size in the first message, keys and output as bytes", async () => {
    const env = setup();
    const view = await opened(env);
    view.deliver(JSON.stringify({ state: "ready" }));
    env.document.querySelector("#workspaceTab-terminal").click();
    await vi.waitFor(() => expect(FakeSocket.last).not.toBe(view));
    const socket = FakeSocket.last;
    expect(socket.url).toBe("wss://consens.io/agent/workspace/terminal");
    await socket.onopen();
    expect(JSON.parse(socket.sent[0])).toEqual({ id_token: "token", cols: 80, rows: 24 });
    const pane = env.document.querySelector("#workspacePane-terminal");
    const [term] = FakeTerminal.made;
    // The shell's output is never translated, and the browser's controls are not this tab's.
    expect(term.host.hasAttribute("data-i18n-skip")).toBe(true);
    expect(pane.hidden).toBe(false);
    expect(env.document.querySelector("#workspacePane-browser").hidden).toBe(true);
    expect(env.document.querySelector(".workspace-view-toggle").hidden).toBe(true);
    expect(pane.classList.contains("is-loading")).toBe(true);
    socket.deliver(JSON.stringify({ state: "ready" }));
    expect(pane.classList.contains("is-loading")).toBe(false);
    expect(env.document.querySelector(".workspace-view-status").textContent)
      .toBe("Your terminal in the workspace, with the agent’s rights.");
    socket.deliver(new TextEncoder().encode("agent@workbench:~$ ").buffer);
    expect(term.written).toEqual(["agent@workbench:~$ "]);
    term.type("ls\r");
    expect(new TextDecoder().decode(socket.sent[1])).toBe("ls\r");
    // Back on the browser tab, its own line and controls return.
    env.document.querySelector("#workspaceTab-browser").click();
    expect(env.document.querySelector(".workspace-view-status").textContent).toBe("Watching. Click the screen to take over.");
    expect(env.document.querySelector(".workspace-view-toggle").hidden).toBe(false);
  });

  it("starts a new terminal after the shell ended, and closes it with the panel", async () => {
    const env = setup();
    await opened(env);
    env.workspace.showTab("terminal");
    await vi.waitFor(() => expect(FakeTerminal.made.length).toBe(1));
    const first = FakeSocket.last;
    await first.onopen();
    first.deliver(JSON.stringify({ state: "ready" }));
    first.closedBy(1000);
    const restart = env.document.querySelector(".workspace-view-restart");
    expect(restart.hidden).toBe(false);
    expect(env.document.querySelector(".workspace-view-status").textContent)
      .toBe("The terminal ended. Start a new one to go on.");
    restart.click();
    await vi.waitFor(() => expect(FakeSocket.last).not.toBe(first));
    const [term] = FakeTerminal.made;
    expect(FakeTerminal.made.length).toBe(1);
    expect(term.resets).toBe(1);
    env.workspace.close();
    expect(FakeSocket.last.closed).toBe(true);
    expect(term.disposed).toBe(true);
  });
});

describe("the workspace view", () => {
  it("signs in with its first message, never in the URL, and shows the setup while it lasts", async () => {
    const env = setup();
    const socket = await opened(env);
    expect(socket.url).toBe("wss://consens.io/agent/workspace/view");
    expect(socket.sent).toEqual([JSON.stringify({ id_token: "token" })]);
    socket.deliver(JSON.stringify({ state: "setup" }));
    const status = env.document.querySelector(".workspace-view-status");
    expect(status.textContent).toBe("Setting up the browser (once, about a minute)…");
    expect(env.document.body.classList.contains("workspace-view-open")).toBe(true);
    expect(env.workspace.isOpen()).toBe(true);
  });

  it("hands the socket to noVNC on ready, so the VNC bytes after it all reach noVNC, watching first", async () => {
    const env = setup();
    const socket = await opened(env);
    socket.deliver(JSON.stringify({ state: "ready" }));
    socket.deliver(new ArrayBuffer(12));
    const [rfb] = FakeRFB.made;
    expect(rfb.channel).toBe(socket);
    expect(rfb.received).toBeInstanceOf(ArrayBuffer);
    expect(rfb.viewOnly).toBe(true);
    expect(rfb.scaleViewport).toBe(true);
    const cover = env.document.querySelector(".workspace-view-cover");
    expect(cover.hidden).toBe(false);
    expect(env.document.querySelector(".workspace-view-status").textContent).toBe("Watching. Click the screen to take over.");
  });

  it("takes the browser over with a click on the screen, refreshes the takeover and hands it back", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      const env = setup();
      const handbacks = [];
      env.window.addEventListener("consensio:workspace-handback", () => handbacks.push("button"));
      const socket = await opened(env);
      socket.deliver(JSON.stringify({ state: "ready" }));
      const [rfb] = FakeRFB.made;
      env.document.querySelector(".workspace-view-cover").click();
      await vi.waitFor(() => expect(rfb.viewOnly).toBe(false));
      expect(handbacks).toEqual([]);
      // The way back is the bar's one button right above the picture, not the head's toggle.
      const toggle = env.document.querySelector(".workspace-view-toggle");
      const back = env.document.querySelector(".workspace-view-turn-button");
      expect(toggle.hidden).toBe(true);
      expect(back.textContent).toBe("Hand back");
      expect(rfb.focused).toBe(1);
      expect(env.document.querySelector(".workspace-view-cover").hidden).toBe(true);
      await vi.advanceTimersByTimeAsync(30_000);
      expect(controls(env.window)).toEqual(["user", "user"]);
      back.click();
      await vi.waitFor(() => expect(rfb.viewOnly).toBe(true));
      // The button's hand-back tells the chat, which lets the agent go on (agent-chat.js).
      expect(handbacks).toEqual(["button"]);
      expect(toggle.hidden).toBe(false);
      expect(toggle.textContent).toBe("Take over");
      expect(env.document.querySelector(".workspace-view-turn").hidden).toBe(true);
      await vi.advanceTimersByTimeAsync(60_000);
      expect(controls(env.window)).toEqual(["user", "user", "agent"]);
    } finally {
      vi.useRealTimers();
    }
  });

  it("says above the picture that the agent waits while the user has the browser, and reminds them after a minute", async () => {
    // Max, 2026-10-29: he waited for the agent while it waited for him; only
    // a small toggle in the head said he still had the browser.
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      const env = setup();
      const socket = await opened(env);
      socket.deliver(JSON.stringify({ state: "ready" }));
      const turn = env.document.querySelector(".workspace-view-turn");
      expect(turn.hidden).toBe(true);
      env.document.querySelector(".workspace-view-cover").click();
      await vi.waitFor(() => expect(FakeRFB.made[0].viewOnly).toBe(false));
      // The bar says it, the head stays quiet; the picture wears the green edge (is-user).
      expect(env.document.querySelector(".workspace-view-status").textContent).toBe("");
      expect(env.document.querySelector(".workspace-view").classList.contains("is-user")).toBe(true);
      expect(turn.hidden).toBe(false);
      expect(turn.classList.contains("is-user")).toBe(true);
      expect(turn.querySelector(".workspace-view-turn-says").textContent).toBe("You have the browser");
      expect(turn.querySelector(".workspace-view-turn-note").textContent).toBe("The agent waits.");
      // Working there keeps it calm; a minute without a key or click reminds.
      await vi.advanceTimersByTimeAsync(40_000);
      env.document.querySelector("#workspacePane-browser").dispatchEvent(new env.window.Event("pointerdown"));
      await vi.advanceTimersByTimeAsync(40_000);
      expect(turn.classList.contains("is-idle")).toBe(false);
      await vi.advanceTimersByTimeAsync(25_000);
      expect(turn.classList.contains("is-idle")).toBe(true);
      expect(turn.querySelector(".workspace-view-turn-says").textContent).toBe("Done?");
      expect(turn.querySelector(".workspace-view-turn-note").textContent)
        .toBe("Hand the browser back so the agent can go on.");
    } finally {
      vi.useRealTimers();
    }
  });

  it("says what the agent waits for, takes over from the agent's card and tells the chat who has the browser", async () => {
    const env = setup();
    const holders = [];
    env.window.addEventListener("consensio:workspace-holder", (event) => holders.push(event.detail.holder));
    // The card asks before the view is open: it opens to take over as soon as there is a picture.
    env.workspace.agentWaits("Bitte melde dich bei der Post an.");
    env.workspace.open({ takeOver: true });
    await vi.waitFor(() => expect(FakeSocket.last).not.toBeNull());
    const socket = FakeSocket.last;
    await socket.onopen();
    socket.deliver(JSON.stringify({ state: "ready" }));
    await vi.waitFor(() => expect(controls(env.window)).toEqual(["user"]));
    expect(env.workspace.holder()).toBe("user");
    // Opening says so too: the chat's card steps aside while the view is open.
    expect(holders).toEqual(["agent", "user"]);
    // The user has the browser, and what the agent asked for stays in view
    // (UX audit 2026-10-29 G2); the hint gives way to the bar (G5).
    const bar = env.document.querySelector(".workspace-view-turn");
    expect(bar.querySelector(".workspace-view-turn-says").textContent).toBe("You have the browser");
    expect(bar.querySelector(".workspace-view-turn-request").textContent).toBe("Bitte melde dich bei der Post an.");
    expect(bar.querySelector(".workspace-view-turn-note:not(.workspace-view-turn-request)").hidden).toBe(true);
    expect(env.document.querySelector(".workspace-view-hint").hidden).toBe(true);
    // In the terminal the bar stays while the user has the browser (G4).
    env.workspace.showTab("terminal");
    expect(bar.hidden).toBe(false);
    env.workspace.showTab("browser");
    env.document.querySelector(".workspace-view-turn-button").click();
    await vi.waitFor(() => expect(env.workspace.holder()).toBe("agent"));
    expect(holders).toEqual(["agent", "user", "agent"]);
    // Watching again while the agent still waits: the bar says what for, the request as data.
    const turn = env.document.querySelector(".workspace-view-turn");
    expect(turn.hidden).toBe(false);
    expect(turn.querySelector(".workspace-view-turn-says").textContent).toBe("The agent is waiting for you");
    expect(turn.querySelector(".workspace-view-turn-note:not(.workspace-view-turn-request)").hidden).toBe(true);
    // One way to take over at a time: the bar's, not also the head's.
    expect(env.document.querySelector(".workspace-view-toggle").hidden).toBe(true);
    const request = turn.querySelector(".workspace-view-turn-request");
    expect(request.textContent).toBe("Bitte melde dich bei der Post an.");
    expect(request.hasAttribute("data-i18n-skip")).toBe(true);
    expect(turn.querySelector(".workspace-view-turn-button").textContent).toBe("Take over");
    env.workspace.agentWaits(null);
    expect(turn.hidden).toBe(true);
  });

  it("hands back from the chat's card without an open view", async () => {
    const env = setup();
    const holders = [];
    let handbacks = 0;
    env.window.addEventListener("consensio:workspace-holder", (event) => holders.push(event.detail.holder));
    env.window.addEventListener("consensio:workspace-handback", () => { handbacks += 1; });
    expect(env.workspace.holder()).toBeNull();
    await env.workspace.handBack();
    expect(controls(env.window)).toEqual(["agent"]);
    expect(holders).toEqual(["agent"]);
    expect(handbacks).toBe(1);
  });

  // A-S6 (docs/agent-audit-readiness-2026-10-29.md): a phone in the 2FA app
  // ran no interval, the takeover lapsed after 90 s and the agent went on
  // mid-login. Back in front, the page refreshes it at once.
  it("refreshes the takeover the moment the page is in front again", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      const env = setup();
      const socket = await opened(env);
      socket.deliver(JSON.stringify({ state: "ready" }));
      env.document.querySelector(".workspace-view-cover").click();
      await vi.waitFor(() => expect(controls(env.window)).toEqual(["user"]));
      await vi.advanceTimersByTimeAsync(20_000);
      env.document.dispatchEvent(new env.window.Event("visibilitychange"));
      await vi.waitFor(() => expect(controls(env.window)).toEqual(["user", "user"]));
      // The interval starts over from there: the next refresh 30 s later, not 10 s.
      await vi.advanceTimersByTimeAsync(15_000);
      expect(controls(env.window)).toEqual(["user", "user"]);
      await vi.advanceTimersByTimeAsync(15_000);
      await vi.waitFor(() => expect(controls(env.window)).toEqual(["user", "user", "user"]));
      // Watching only: nothing to refresh.
      env.document.querySelector(".workspace-view-turn-button").click();
      await vi.waitFor(() => expect(controls(env.window).at(-1)).toBe("agent"));
      const count = controls(env.window).length;
      env.document.dispatchEvent(new env.window.Event("visibilitychange"));
      await vi.advanceTimersByTimeAsync(0);
      expect(controls(env.window)).toHaveLength(count);
    } finally {
      vi.useRealTimers();
    }
  });

  it("opens the view again in the user's hands after a reload, never for an old or foreign takeover", async () => {
    const env = setup({ prepare: window => window.sessionStorage.setItem("workspace_view_holder",
      JSON.stringify({ uid: "u1", at: Date.now() - 60_000 })) });
    // Nothing before the account is known (auth-session-state.js says so).
    await new Promise(resolve => setTimeout(resolve, 20));
    expect(FakeSocket.last).toBeNull();
    env.window.dispatchEvent(new env.window.CustomEvent("consensio:auth-state", { detail: { known: true, uid: "u1" } }));
    await vi.waitFor(() => expect(FakeSocket.last).not.toBeNull());
    const socket = FakeSocket.last;
    await socket.onopen();
    socket.deliver(JSON.stringify({ state: "ready" }));
    await vi.waitFor(() => expect(controls(env.window)).toEqual(["user"]));
    expect(env.workspace.holder()).toBe("user");
    // Closed: the next reload leaves it closed.
    env.document.querySelector(".workspace-view-close").click();
    expect(env.window.sessionStorage.getItem("workspace_view_holder")).toBe(null);
    for (const saved of [{ uid: "u1", at: Date.now() - 31 * 60_000 }, { uid: "someone-else", at: Date.now() }]) {
      FakeSocket.last = null;
      const other = setup({ prepare: window => window.sessionStorage.setItem("workspace_view_holder", JSON.stringify(saved)) });
      other.window.dispatchEvent(new other.window.CustomEvent("consensio:auth-state", { detail: { known: true, uid: "u1" } }));
      await new Promise(resolve => setTimeout(resolve, 20));
      expect(FakeSocket.last).toBeNull();
      expect(other.workspace.isOpen()).toBe(false);
      expect(other.window.sessionStorage.getItem("workspace_view_holder")).toBe(null);
    }
  });

  // A logout does not reload the page: until 2026-10-30 the view of the
  // account that left stayed open, its Chrome in the next person's hands,
  // and its refresh claimed the browser of whoever signed in next.
  it("closes when its account logs out or another signs in, not when the same one refreshes", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      const env = setup();
      const socket = await opened(env);
      socket.deliver(JSON.stringify({ state: "ready" }));
      env.document.querySelector(".workspace-view-cover").click();
      await vi.waitFor(() => expect(controls(env.window)).toEqual(["user"]));
      // The same account again (a token refresh): the view stays.
      env.window.dispatchEvent(new env.window.CustomEvent("consensio:auth-state", { detail: { known: true, uid: "u1" } }));
      expect(env.workspace.isOpen()).toBe(true);
      env.window.auth.currentUser = null;
      env.window.dispatchEvent(new env.window.CustomEvent("consensio:auth-state", { detail: { known: true, uid: null } }));
      expect(env.workspace.isOpen()).toBe(false);
      expect(FakeRFB.made[0].disconnected).toBe(true);
      expect(socket.closed).toBe(true);
      expect(env.window.sessionStorage.getItem("workspace_view_holder")).toBe(null);
      // Someone else signs in on this page: nothing claims their browser.
      env.window.auth.currentUser = { uid: "u2", getIdToken: async () => "token-u2" };
      env.window.dispatchEvent(new env.window.CustomEvent("consensio:auth-state", { detail: { known: true, uid: "u2" } }));
      await vi.advanceTimersByTimeAsync(65_000);
      expect(controls(env.window)).toEqual(["user"]);
      expect(env.workspace.isOpen()).toBe(false);

      const other = setup();
      const second = await opened(other);
      second.deliver(JSON.stringify({ state: "ready" }));
      other.window.auth.currentUser = { uid: "u2", getIdToken: async () => "token-u2" };
      other.window.dispatchEvent(new other.window.CustomEvent("consensio:auth-state", { detail: { known: true, uid: "u2" } }));
      expect(other.workspace.isOpen()).toBe(false);
      expect(second.closed).toBe(true);
    } finally {
      vi.useRealTimers();
    }
  });

  it("gives the browser back when it closes while the user has it", async () => {
    const env = setup();
    let handbacks = 0;
    env.window.addEventListener("consensio:workspace-handback", () => { handbacks += 1; });
    const socket = await opened(env);
    socket.deliver(JSON.stringify({ state: "ready" }));
    env.document.querySelector(".workspace-view-cover").click();
    await vi.waitFor(() => expect(FakeRFB.made[0].viewOnly).toBe(false));
    env.document.querySelector(".workspace-view-close").click();
    await vi.waitFor(() => expect(controls(env.window)).toEqual(["user", "agent"]));
    // Closing hands back without a word to the chat: no "Done in the browser.".
    expect(handbacks).toBe(0);
    expect(FakeRFB.made[0].disconnected).toBe(true);
    expect(socket.closed).toBe(true);
    expect(env.workspace.isOpen()).toBe(false);
    // It leaves the way it came (Apple audit C5), inert, then it is gone.
    const leaving = env.document.querySelector(".workspace-view");
    expect(leaving.classList.contains("is-leaving")).toBe(true);
    expect(leaving.inert).toBe(true);
    await vi.waitFor(() => expect(env.document.querySelector(".workspace-view")).toBeNull());
  });

  it("opens from the (+) menu in a chat and closes the menu", async () => {
    const env = setup();
    env.window.App.closeAttachMenu = vi.fn();
    env.document.getElementById("attachWorkspaceOption").click();
    expect(env.window.App.closeAttachMenu).toHaveBeenCalled();
    await vi.waitFor(() => expect(FakeSocket.last).not.toBeNull());
    expect(env.workspace.isOpen()).toBe(true);
  });

  it("says when the account has no workspace or the server cannot reach it", async () => {
    const env = setup();
    const socket = await opened(env);
    socket.deliver(JSON.stringify({ state: "error" }));
    const status = env.document.querySelector(".workspace-view-status");
    expect(status.textContent).toBe("The workspace is not reachable right now. Try again in a moment.");
    socket.onclose({ code: 4403 });
    expect(status.textContent).toBe("The workspace is not available on your account.");
    expect(FakeRFB.made).toEqual([]);
  });

  it("says why the server closed a view, also over the picture", async () => {
    // One view per account, its time counts as VM time (security audit 2026-10-27).
    const env = setup();
    const socket = await opened(env);
    socket.deliver(JSON.stringify({ state: "ready" }));
    expect(FakeRFB.made.length).toBe(1);
    socket.closedBy(4409);
    const status = env.document.querySelector(".workspace-view-status");
    expect(status.textContent).toBe("The workspace opened in another window, so this view closed.");
    const again = setup();
    const refused = await opened(again);
    refused.closedBy(4402);
    expect(again.document.querySelector(".workspace-view-status").textContent)
      .toBe("The workspace’s time for today is used up. It is back tomorrow.");
  });

  it("logs the browser out everywhere only after asking", async () => {
    const env = setup();
    env.window.App.confirm = vi.fn(async () => false);
    const [, signOut] = env.document.querySelectorAll("#agentWorkspaceSettings button");
    expect(signOut.textContent).toBe("Log out everywhere");
    signOut.click();
    await vi.waitFor(() => expect(env.window.App.confirm).toHaveBeenCalled());
    expect(env.window.fetch).not.toHaveBeenCalled();
    env.window.App.confirm = vi.fn(async () => true);
    signOut.click();
    await vi.waitFor(() => expect(env.window.fetch).toHaveBeenCalled());
    expect(env.window.fetch.mock.calls[0][0]).toBe("/agent/workspace/reset-browser");
    await vi.waitFor(() => expect(env.document.querySelector(".agent-workspace-status").textContent)
      .toBe("The workspace browser is logged out everywhere."));
  });
});

describe("pasting into the workspace", () => {
  // Shift, Control, Meta, Alt and Super, released in the VM before the text.
  const RELEASED = [0xffe1, 0xffe2, 0xffe3, 0xffe4, 0xffe7, 0xffe8, 0xffe9, 0xffea, 0xffeb, 0xffec]
    .map((keysym) => [keysym, false]);
  const pressed = (text) => [...text].map((char) => [char === "\n" ? 0xff0d : char.codePointAt(0) <= 0xff
    ? char.codePointAt(0) : 0x01000000 | char.codePointAt(0), undefined]);

  async function holding(env) {
    const socket = await opened(env);
    socket.deliver(JSON.stringify({ state: "ready" }));
    const [rfb] = FakeRFB.made;
    env.document.querySelector(".workspace-view-cover").click();
    await vi.waitFor(() => expect(rfb.viewOnly).toBe(false));
    return rfb;
  }
  function shortcut(env, rfb, init = { key: "v", ctrlKey: true }) {
    const event = new env.window.KeyboardEvent("keydown", { bubbles: true, cancelable: true, ...init });
    rfb.canvas.dispatchEvent(event);
    return event;
  }
  function paste(env, target, text) {
    const event = new env.window.Event("paste", { bubbles: true, cancelable: true });
    Object.defineProperty(event, "clipboardData", { value: { getData: (type) => (type === "text/plain" ? text : "") } });
    target.dispatchEvent(event);
    return event;
  }

  it("types the pasted text in as keys, never through the VM's clipboard, without the line break at its end", async () => {
    const env = setup();
    const rfb = await holding(env);
    const pressedShortcut = shortcut(env, rfb);
    // The shortcut never reaches noVNC, which would press it in the VM; the browser pastes into the hidden field.
    expect(rfb.noVNCKeys).toEqual([]);
    expect(pressedShortcut.defaultPrevented).toBe(false);
    const target = env.document.querySelector(".workspace-view-paste-target");
    expect(env.document.activeElement).toBe(target);
    const focused = rfb.focused;
    const event = paste(env, target, "Pa$$wörd€\r\n");
    expect(event.defaultPrevented).toBe(true);
    expect(rfb.keys).toEqual([...RELEASED, ...pressed("Pa$$wörd€")]);
    // Back on the screen, so the next keys reach the VM again.
    expect(rfb.focused).toBe(focused + 1);
    expect(env.document.activeElement).toBe(rfb.canvas);
    rfb.keys = [];
    shortcut(env, rfb, { key: "Insert", shiftKey: true });
    paste(env, target, "line one\nline two\n\n");
    expect(rfb.keys).toEqual([...RELEASED, ...pressed("line one\nline two")]);
  });

  it("leaves the keys to noVNC and pastes nothing while the user only watches", async () => {
    const env = setup();
    const socket = await opened(env);
    socket.deliver(JSON.stringify({ state: "ready" }));
    const [rfb] = FakeRFB.made;
    shortcut(env, rfb);
    expect(rfb.noVNCKeys).toEqual(["v"]);
    const event = paste(env, rfb.canvas, "secret");
    expect(event.defaultPrevented).toBe(false);
    expect(rfb.keys).toEqual([]);
    expect(env.document.querySelector(".workspace-view-paste").hidden).toBe(true);
  });

  it("refuses a paste too long to type in, and says so", async () => {
    const env = setup();
    const rfb = await holding(env);
    shortcut(env, rfb);
    paste(env, env.document.querySelector(".workspace-view-paste-target"), "x".repeat(2001));
    expect(rfb.keys).toEqual([]);
    expect(env.document.querySelector(".workspace-view-status").textContent)
      .toBe("That is too long to type in. Paste at most 2,000 characters at a time.");
  });

  it("pastes with the Paste button too, which shows only while the user has the browser", async () => {
    const readText = vi.fn(async () => "hunter2");
    const env = setup({ clipboard: { readText } });
    const socket = await opened(env);
    socket.deliver(JSON.stringify({ state: "ready" }));
    const button = env.document.querySelector(".workspace-view-paste");
    expect(button.hidden).toBe(true);
    env.document.querySelector(".workspace-view-cover").click();
    const [rfb] = FakeRFB.made;
    await vi.waitFor(() => expect(button.hidden).toBe(false));
    button.click();
    await vi.waitFor(() => expect(rfb.keys).toEqual([...RELEASED, ...pressed("hunter2")]));
    readText.mockRejectedValueOnce(new Error("denied"));
    rfb.keys = [];
    button.click();
    await vi.waitFor(() => expect(env.document.querySelector(".workspace-view-status").textContent)
      .toBe("Your browser did not share the clipboard. Press Ctrl+V (Cmd+V on a Mac) on the screen instead."));
    expect(rfb.keys).toEqual([]);
    env.document.querySelector(".workspace-view-turn-button").click();
    await vi.waitFor(() => expect(button.hidden).toBe(true));
  });
});

describe("the workspace beside the chat", () => {
  function wide(env, width = 1600) {
    Object.defineProperty(env.window, "innerWidth", { value: width, configurable: true });
    // jsdom lays nothing out: the window without a scrollbar is as wide.
    Object.defineProperty(env.document.documentElement, "clientWidth", { value: width, configurable: true });
    env.window.matchMedia = (query) => ({ matches: /min-width: (\d+)px/.test(query) && width >= Number(query.match(/(\d+)px/)[1]) });
  }

  it("docks at half of the room beside the chat and leaves the chat its lane", async () => {
    const env = setup();
    wide(env);
    await env.workspace.open();
    const body = env.document.body;
    expect(body.classList.contains("workspace-view-docked")).toBe(true);
    expect(env.workspace.width()).toBe(800);
    expect(body.style.getPropertyValue("--workspace-width")).toBe("800px");
    const resizer = env.document.querySelector(".workspace-view-resizer");
    expect(resizer.hidden).toBe(false);
    expect(resizer.getAttribute("role")).toBe("separator");
    expect(resizer.getAttribute("aria-valuenow")).toBe("800");
    env.workspace.close();
    expect(body.classList.contains("workspace-view-docked")).toBe(false);
    expect(body.style.getPropertyValue("--workspace-width")).toBe("");
  });

  it("resizes with the arrow keys within bounds that keep the chat readable, and remembers the width", async () => {
    const env = setup();
    wide(env);
    await env.workspace.open();
    const resizer = env.document.querySelector(".workspace-view-resizer");
    const key = (name) => resizer.dispatchEvent(new env.window.KeyboardEvent("keydown", { key: name, bubbles: true }));
    key("ArrowLeft");
    expect(env.workspace.width()).toBe(840);
    key("Home");
    // The chat keeps at least 520px beside it.
    expect(env.workspace.width()).toBe(1600 - 520);
    key("End");
    expect(env.workspace.width()).toBe(380);
    expect(env.window.localStorage.getItem("consens.workspaceWidth")).toBe("380");
    env.workspace.close();
    await env.workspace.open();
    expect(env.workspace.width()).toBe(380);
    // A double click goes back to half and half and forgets the choice.
    resizer.ownerDocument.querySelector(".workspace-view-resizer")
      .dispatchEvent(new env.window.MouseEvent("dblclick", { bubbles: true }));
    expect(env.workspace.width()).toBe(800);
    expect(env.window.localStorage.getItem("consens.workspaceWidth")).toBeNull();
  });

  it("moves aside when the Agent activity panel opens next to it", async () => {
    const env = setup();
    wide(env);
    await env.workspace.open();
    const panel = env.document.querySelector(".workspace-view");
    expect(panel.style.getPropertyValue("--workspace-right")).toBe("0px");
    env.document.body.classList.add("agent-sidebar-open");
    await vi.waitFor(() => expect(panel.style.getPropertyValue("--workspace-right")).toBe("346px"));
    // Both panels and the chat's 520px do not fit at 800: the workspace gives way.
    expect(env.workspace.width()).toBe(1600 - 346 - 520);
    // A narrower window takes it from the workspace, never from the chat.
    wide(env, 1400);
    env.window.dispatchEvent(new env.window.Event("resize"));
    expect(env.workspace.width()).toBe(1400 - 346 - 520);
  });

  it("lies over the Agent activity panel where beside it would leave it too narrow", async () => {
    // UX audit 2026-10-29 G1: at 1280px beside the activity it was 155px wide.
    const env = setup();
    wide(env, 1200);
    env.document.body.classList.add("agent-sidebar-open");
    await env.workspace.open();
    const panel = env.document.querySelector(".workspace-view");
    expect(env.document.body.classList.contains("workspace-view-covers")).toBe(true);
    expect(panel.style.getPropertyValue("--workspace-right")).toBe("0px");
    expect(env.workspace.width()).toBe(600);
    // The activity closes: still docked at the edge, no longer over anything.
    env.document.body.classList.remove("agent-sidebar-open");
    await vi.waitFor(() => expect(env.document.body.classList.contains("workspace-view-covers")).toBe(false));
    env.workspace.close();
    expect(env.document.body.classList.contains("workspace-view-covers")).toBe(false);
  });

  it("covers the screen on narrow windows, without an edge to drag", async () => {
    const env = setup();
    wide(env, 900);
    await env.workspace.open();
    expect(env.document.body.classList.contains("workspace-view-docked")).toBe(false);
    expect(env.document.querySelector(".workspace-view-resizer").hidden).toBe(true);
    expect(env.document.body.style.getPropertyValue("--workspace-width")).toBe("0px");
  });
});

// Runtime audit 2026-10-30 (docs/agent-workspace-runtime-audit-2026-10-30.md).
describe("the workspace view after the runtime audit", () => {
  async function watching(env) {
    const socket = await opened(env);
    socket.deliver(JSON.stringify({ state: "ready" }));
    return socket;
  }
  async function holding(env) {
    const socket = await watching(env);
    env.document.querySelector(".workspace-view-cover").click();
    await vi.waitFor(() => expect(FakeRFB.made.at(-1).viewOnly).toBe(false));
    return socket;
  }
  const status = env => env.document.querySelector(".workspace-view-status");
  const screen = env => env.document.querySelector("#workspacePane-browser");

  // V2: the phone went to its 2FA app and iOS closed the socket; the view
  // stayed empty, without "Hand back", and closing it handed back mid-login.
  it("comes back by itself after a dropped connection, with the takeover and its bar", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      const env = setup();
      const handbacks = [];
      env.window.addEventListener("consensio:workspace-handback", () => handbacks.push("button"));
      const first = await holding(env);
      expect(controls(env.window)).toEqual(["user"]);
      first.closedBy(1006);
      expect(status(env).textContent).toBe("Reconnecting…");
      expect(screen(env).classList.contains("is-loading")).toBe(true);
      // The bar and its "Hand back" stay; nothing handed back, nothing closed.
      const bar = env.document.querySelector(".workspace-view-turn");
      expect(bar.hidden).toBe(false);
      expect(bar.querySelector(".workspace-view-turn-button").textContent).toBe("Hand back");
      expect(env.workspace.isOpen()).toBe(true);
      expect(env.workspace.holder()).toBe("user");
      expect(FakeSocket.last).toBe(first);
      await vi.advanceTimersByTimeAsync(1_000);
      const second = FakeSocket.last;
      expect(second).not.toBe(first);
      await second.onopen();
      second.deliver(JSON.stringify({ state: "connecting" }));
      expect(status(env).textContent).toBe("Reconnecting…");
      second.deliver(JSON.stringify({ state: "ready" }));
      // Still the user's: the new picture takes their keys at once.
      expect(FakeRFB.made.at(-1).viewOnly).toBe(false);
      expect(screen(env).classList.contains("is-loading")).toBe(false);
      expect(controls(env.window)).toEqual(["user"]);
      // Handing back while it comes back again is the button's hand-back.
      second.closedBy(1006);
      bar.querySelector(".workspace-view-turn-button").click();
      await vi.waitFor(() => expect(controls(env.window)).toEqual(["user", "agent"]));
      expect(handbacks).toEqual(["button"]);
    } finally {
      vi.useRealTimers();
    }
  });

  it("tries after 1, 2, 5 and 10 seconds, then says so in two lines with Reconnect", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      const env = setup();
      let socket = await watching(env);
      for (const wait of [1_000, 2_000, 5_000, 10_000]) {
        socket.closedBy(1006);
        await vi.advanceTimersByTimeAsync(wait - 50);
        expect(FakeSocket.last).toBe(socket);
        await vi.advanceTimersByTimeAsync(50);
        expect(FakeSocket.last).not.toBe(socket);
        socket = FakeSocket.last;
      }
      socket.closedBy(1006);
      await vi.advanceTimersByTimeAsync(30_000);
      expect(FakeSocket.last).toBe(socket);
      expect(status(env).textContent).toBe("The connection to the workspace ended. Reconnect to go on.");
      expect(status(env).classList.contains("is-wrapping")).toBe(true);
      const again = env.document.querySelector(".workspace-view-reconnect");
      expect(again.hidden).toBe(false);
      expect(again.textContent).toBe("Reconnect");
      again.click();
      expect(FakeSocket.last).not.toBe(socket);
      expect(again.hidden).toBe(true);
      expect(status(env).textContent).toBe("Reconnecting…");
    } finally {
      vi.useRealTimers();
    }
  });

  it("comes back at once when the page is in front again or online, never after a server's reason", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      const env = setup();
      const socket = await watching(env);
      socket.closedBy(1006);
      env.window.dispatchEvent(new env.window.Event("online"));
      expect(FakeSocket.last).not.toBe(socket);
      const replaced = FakeSocket.last;
      await replaced.onopen();
      replaced.deliver(JSON.stringify({ state: "ready" }));
      replaced.closedBy(4409);
      env.document.dispatchEvent(new env.window.Event("visibilitychange"));
      await vi.advanceTimersByTimeAsync(20_000);
      expect(FakeSocket.last).toBe(replaced);
      expect(status(env).textContent).toBe("The workspace opened in another window, so this view closed.");
      expect(env.document.querySelector(".workspace-view-reconnect").hidden).toBe(false);
      // Nothing to try with the day's time used up.
      const other = setup();
      const refused = await opened(other);
      refused.closedBy(4402);
      expect(other.document.querySelector(".workspace-view-reconnect").hidden).toBe(true);
    } finally {
      vi.useRealTimers();
    }
  });

  // V4: a forgotten view counted its hour as VM time.
  it("lets go of the view after a minute in a hidden tab while the agent has the browser, and comes back", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let env;
    const visibility = state => Object.defineProperty(env.document, "visibilityState", { value: state, configurable: true });
    try {
      env = setup();
      const socket = await watching(env);
      visibility("hidden");
      env.document.dispatchEvent(new env.window.Event("visibilitychange"));
      await vi.advanceTimersByTimeAsync(59_000);
      expect(socket.closed).toBe(false);
      await vi.advanceTimersByTimeAsync(1_500);
      expect(socket.closed).toBe(true);
      expect(FakeRFB.made[0].disconnected).toBe(true);
      expect(status(env).textContent).toBe("Paused while this tab was in the background, to save your workspace time.");
      await vi.advanceTimersByTimeAsync(60_000);
      expect(FakeSocket.last).toBe(socket);
      visibility("visible");
      env.document.dispatchEvent(new env.window.Event("visibilitychange"));
      expect(FakeSocket.last).not.toBe(socket);
      expect(status(env).textContent).toBe("Reconnecting…");
      // While the user has the browser, a hidden tab keeps it (the 2FA app).
      const next = FakeSocket.last;
      await next.onopen();
      next.deliver(JSON.stringify({ state: "ready" }));
      env.document.querySelector(".workspace-view-cover").click();
      await vi.waitFor(() => expect(FakeRFB.made.at(-1).viewOnly).toBe(false));
      visibility("hidden");
      env.document.dispatchEvent(new env.window.Event("visibilitychange"));
      await vi.advanceTimersByTimeAsync(120_000);
      expect(next.closed).toBe(false);
    } finally {
      vi.useRealTimers();
    }
  });

  it("says what is left of today's VM time while the agent has the browser", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      // The window's clock is jsdom's own: it follows the test's.
      const env = setup({ prepare: window => { window.Date.now = () => Date.now(); } });
      const socket = await opened(env);
      socket.deliver(JSON.stringify({ state: "connecting", left_seconds: 4_320 }));
      socket.deliver(JSON.stringify({ state: "ready" }));
      const time = env.document.querySelector(".workspace-view-time");
      expect(time.hidden).toBe(false);
      expect(time.textContent).toBe("1h 12m left today");
      // Already in the page's language.
      expect(time.hasAttribute("data-i18n-skip")).toBe(true);
      // The open view counts as VM time: it counts down.
      await vi.advanceTimersByTimeAsync(150_500);
      expect(time.textContent).toBe("1h 10m left today");
      env.document.querySelector(".workspace-view-cover").click();
      await vi.waitFor(() => expect(time.hidden).toBe(true));
    } finally {
      vi.useRealTimers();
    }
  });

  // V1: iOS and Android open no keyboard for noVNC's canvas.
  it("opens the phone's keyboard on a field whose keys go to the browser, only while the user has it", async () => {
    const env = setup({ prepare: window => {
      window.matchMedia = query => ({ matches: query === "(pointer: coarse)" });
    } });
    await watching(env);
    const keyboard = env.document.querySelector(".workspace-view-keyboard");
    expect(keyboard.hidden).toBe(true);
    env.document.querySelector(".workspace-view-cover").click();
    const rfb = FakeRFB.made[0];
    await vi.waitFor(() => expect(keyboard.hidden).toBe(false));
    keyboard.click();
    const field = env.document.querySelector(".workspace-view-keys");
    expect(env.document.activeElement).toBe(field);
    expect(keyboard.getAttribute("aria-pressed")).toBe("true");
    // 16px, no capitals or corrections: iOS neither zooms nor changes the words.
    for (const [name, value] of [["autocapitalize", "off"], ["autocorrect", "off"], ["spellcheck", "false"]]) {
      expect(field.getAttribute(name)).toBe(value);
    }
    // A tap on the screen clicks there and leaves the keyboard open.
    expect(rfb.focusOnClick).toBe(false);
    rfb.keys = [];
    const typed = new env.window.InputEvent("beforeinput", { inputType: "insertText", data: "Hü", cancelable: true });
    field.dispatchEvent(typed);
    expect(typed.defaultPrevented).toBe(true);
    for (const key of ["Backspace", "Enter", "Tab"]) {
      field.dispatchEvent(new env.window.KeyboardEvent("keydown", { key, bubbles: true, cancelable: true }));
    }
    expect(rfb.keys).toEqual([[0x48, undefined], [0xfc, undefined], [0xff08, undefined], [0xff0d, undefined],
      [0xff09, undefined]]);
    // What a keyboard composes changes the field: the difference goes as keys.
    rfb.keys = [];
    field.value = `${field.value}ok`;
    field.dispatchEvent(new env.window.Event("input", { bubbles: true }));
    field.value = field.value.slice(0, -3);
    field.dispatchEvent(new env.window.Event("input", { bubbles: true }));
    expect(rfb.keys).toEqual([[0x6f, undefined], [0x6b, undefined], [0xff08, undefined], [0xff08, undefined],
      [0xff08, undefined]]);
    keyboard.click();
    expect(env.document.activeElement).not.toBe(field);
    expect(rfb.focusOnClick).toBe(true);
    // Watching only: the field sends nothing and the button is gone.
    field.focus();
    env.document.querySelector(".workspace-view-turn-button").click();
    await vi.waitFor(() => expect(keyboard.hidden).toBe(true));
    expect(env.document.activeElement).not.toBe(field);
    rfb.keys = [];
    field.dispatchEvent(new env.window.InputEvent("beforeinput", { inputType: "insertText", data: "x", cancelable: true }));
    expect(rfb.keys).toEqual([]);
  });

  // V5: on a phone the picture was a quarter of its size.
  it("shows the page at its real size while the user has it, and fits it again on hand-back", async () => {
    const env = setup();
    await holding(env);
    const rfb = FakeRFB.made[0];
    const zoom = env.document.querySelector(".workspace-view-zoom");
    expect(zoom.hidden).toBe(false);
    expect(zoom.textContent).toBe("100%");
    zoom.click();
    expect([rfb.scaleViewport, rfb.clipViewport, rfb.dragViewport]).toEqual([false, true, true]);
    expect(zoom.getAttribute("aria-pressed")).toBe("true");
    env.document.querySelector(".workspace-view-turn-button").click();
    await vi.waitFor(() => expect(rfb.viewOnly).toBe(true));
    expect([rfb.scaleViewport, rfb.clipViewport, rfb.dragViewport]).toEqual([true, false, false]);
    expect(zoom.hidden).toBe(true);
  });

  // V6: on a phone the panel covers the chat, and its line said the same all the time.
  it("names the agent's step in its line while the agent has the browser", async () => {
    const env = setup();
    await watching(env);
    env.workspace.agentStep("Clicking e12");
    expect(status(env).textContent).toBe("Clicking e12");
    // The step's target is data, its verb already in the page's language.
    expect(status(env).hasAttribute("data-i18n-skip")).toBe(true);
    env.workspace.agentStep(null);
    expect(status(env).textContent).toBe("Watching. Click the screen to take over.");
    expect(status(env).hasAttribute("data-i18n-skip")).toBe(false);
    env.workspace.agentStep("Opening example.com");
    env.document.querySelector(".workspace-view-cover").click();
    await vi.waitFor(() => expect(FakeRFB.made[0].viewOnly).toBe(false));
    expect(status(env).textContent).toBe("");
    env.workspace.agentStep(null);
  });

  // V7: at 390px the close cross stood alone in the head's second row.
  it("keeps title, tabs and the close cross apart from the line and its tools", async () => {
    const env = setup();
    await opened(env);
    const head = env.document.querySelector(".workspace-view-head");
    expect([...head.children].map(child => child.className.split(" ").at(-1)))
      .toEqual(["workspace-view-title", "workspace-view-tabs", "workspace-view-tools", "workspace-view-close"]);
    const tools = head.querySelector(".workspace-view-tools");
    for (const name of ["status", "time", "paste", "keyboard", "zoom", "toggle"]) {
      expect(tools.querySelector(`.workspace-view-${name}`)).not.toBeNull();
    }
  });
});
