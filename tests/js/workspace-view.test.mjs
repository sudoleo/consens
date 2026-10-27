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
    body: '<button id="composerWorkspaceButton"></button><button id="attachWorkspaceOption"></button>'
      + '<div id="agentWorkspaceSettings"></div>',
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

  it("covers the screen on narrow windows, without an edge to drag", async () => {
    const env = setup();
    wide(env, 900);
    await env.workspace.open();
    expect(env.document.body.classList.contains("workspace-view-docked")).toBe(false);
    expect(env.document.querySelector(".workspace-view-resizer").hidden).toBe(true);
    expect(env.document.body.style.getPropertyValue("--workspace-width")).toBe("0px");
  });
});
