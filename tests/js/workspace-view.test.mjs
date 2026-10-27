import { describe, expect, it, vi } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

// The account's workspace live (workspace-view.js): the panel signs in over
// its WebSocket's first message, hands the socket to noVNC on "ready", and a
// click on the screen takes the browser over until "Hand back".
class FakeSocket {
  static last = null;
  constructor(url) {
    this.url = url;
    this.sent = [];
    this.closed = false;
    FakeSocket.last = this;
  }
  send(data) { this.sent.push(data); }
  close() { this.closed = true; this.onclose?.({ code: 1000 }); }
  // A message from the server.
  deliver(data) { this.onmessage?.({ data }); }
}

class FakeRFB {
  static made = [];
  constructor(target, channel, options) {
    Object.assign(this, { target, channel, options, viewOnly: false, focused: 0, disconnected: false });
    this.listeners = {};
    // noVNC takes over the socket's handlers at once (rfb.js _connect).
    channel.onmessage = (event) => { this.received = event.data; };
    FakeRFB.made.push(this);
  }
  addEventListener(name, handler) { this.listeners[name] = handler; }
  focus() { this.focused += 1; }
  disconnect() { this.disconnected = true; }
}

function setup() {
  FakeSocket.last = null;
  FakeRFB.made = [];
  const app = loadScripts(["static/js/workspace-view.js"], {
    body: '<button id="composerWorkspaceButton"></button><div id="agentWorkspaceSettings"></div>',
    before(window) {
      window.WebSocket = FakeSocket;
      window.auth = { currentUser: { uid: "u1", getIdToken: async () => "token" } };
      window.App = { t: (text, values) => text.replace(/\{(\w+)\}/g, (_, key) => values?.[key] ?? "") };
      window.fetch = vi.fn(async () => ({ ok: true, json: async () => ({}) }));
    },
  });
  const { window } = app;
  window.App.workspaceView._setLoader(async () => FakeRFB);
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
      const socket = await opened(env);
      socket.deliver(JSON.stringify({ state: "ready" }));
      const [rfb] = FakeRFB.made;
      env.document.querySelector(".workspace-view-cover").click();
      await vi.waitFor(() => expect(rfb.viewOnly).toBe(false));
      const toggle = env.document.querySelector(".workspace-view-toggle");
      expect(toggle.textContent).toBe("Hand back");
      expect(rfb.focused).toBe(1);
      expect(env.document.querySelector(".workspace-view-cover").hidden).toBe(true);
      await vi.advanceTimersByTimeAsync(30_000);
      expect(controls(env.window)).toEqual(["user", "user"]);
      toggle.click();
      await vi.waitFor(() => expect(rfb.viewOnly).toBe(true));
      expect(toggle.textContent).toBe("Take over");
      await vi.advanceTimersByTimeAsync(60_000);
      expect(controls(env.window)).toEqual(["user", "user", "agent"]);
    } finally {
      vi.useRealTimers();
    }
  });

  it("gives the browser back when it closes while the user has it", async () => {
    const env = setup();
    const socket = await opened(env);
    socket.deliver(JSON.stringify({ state: "ready" }));
    env.document.querySelector(".workspace-view-cover").click();
    await vi.waitFor(() => expect(FakeRFB.made[0].viewOnly).toBe(false));
    env.document.querySelector(".workspace-view-close").click();
    await vi.waitFor(() => expect(controls(env.window)).toEqual(["user", "agent"]));
    expect(FakeRFB.made[0].disconnected).toBe(true);
    expect(socket.closed).toBe(true);
    expect(env.document.querySelector(".workspace-view")).toBeNull();
    expect(env.workspace.isOpen()).toBe(false);
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

  it("signs the browser out everywhere only after asking", async () => {
    const env = setup();
    env.window.App.confirm = vi.fn(async () => false);
    const [, signOut] = env.document.querySelectorAll("#agentWorkspaceSettings button");
    expect(signOut.textContent).toBe("Sign out everywhere");
    signOut.click();
    await vi.waitFor(() => expect(env.window.App.confirm).toHaveBeenCalled());
    expect(env.window.fetch).not.toHaveBeenCalled();
    env.window.App.confirm = vi.fn(async () => true);
    signOut.click();
    await vi.waitFor(() => expect(env.window.fetch).toHaveBeenCalled());
    expect(env.window.fetch.mock.calls[0][0]).toBe("/agent/workspace/reset-browser");
    await vi.waitFor(() => expect(env.document.querySelector(".agent-workspace-status").textContent)
      .toBe("The workspace browser is signed out everywhere."));
  });
});
