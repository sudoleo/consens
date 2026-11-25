import { describe, expect, it, vi } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

// An app the agent serves in the workspace (vm_show_app,
// agent_vm_processes.py): a card that opens it in the user's own browser, at
// the app's own address (agent_apps.py), while its process runs. After that
// the card asks the agent for a new start.
function setup() {
  const app = loadScripts(["static/js/agent-activity.js"], { body: '<div id="host"></div>' });
  app.window.App.userSettings = { get: name => (name === "detailed_progress" ? true : undefined) };
  app.window.auth = { currentUser: { getIdToken: async () => "id-token" } };
  return { app, host: app.document.getElementById("host"), activity: app.window.App.agentActivity };
}

const shown = fields => ({ version: 1, kind: "tool", id: "completion:1:call_9/tool", name: "vm_show_app",
  status: "succeeded", app_shown: true, process: "abcd1234", app_port: 3000, app_path: "/app", ...fields });

// The tab the click opens, as the card steers it.
function tabs(window) {
  const opened = [];
  window.open = vi.fn((address, target) => {
    const tab = { address, target, opener: window, closed: false, replaced: null,
      close() { this.closed = true; }, location: { replace(url) { tab.replaced = url; } } };
    opened.push(tab);
    return tab;
  });
  return opened;
}

function answers(window, body, status = 200) {
  window.fetch = vi.fn(async () => ({ ok: status < 400, status, json: async () => body }));
  return window.fetch;
}

const settle = () => new Promise(resolve => setTimeout(resolve, 0));

describe("An app the agent serves, on a card", () => {
  it("stands under the run's line with its name, how long it runs and Open", () => {
    const { host, activity } = setup();
    const ends = Date.now() + 30 * 60 * 1000;
    const events = [];
    activity.receive(events, shown({ app_title: "Todo app", ends_at: ends }));
    activity.render(host, { running: false, status: "succeeded", events });
    const pin = host.querySelector(".agent-page-pin");
    const card = pin.querySelector(".agent-app-card");
    expect(pin.hidden).toBe(false);
    expect(card.dataset.state).toBe("running");
    // The agent's own name for it: data, never translated.
    expect(card.querySelector(".agent-page-title").textContent).toBe("Todo app");
    expect(card.querySelector(".agent-page-title").translate).toBe(false);
    expect(card.querySelector(".agent-page-meta").textContent).toMatch(/^Runs in your workspace until \S+/);
    expect(card.querySelector(".agent-page-open").textContent).toBe("Open");
    // No picture's place: the app shows in the user's own tab.
    expect(card.querySelector(".agent-page-shot")).toBeNull();
    // Its step stays among the lines as words.
    expect(host.querySelector(".agent-activity-content .agent-vm .agent-vm-target").textContent).toBe("3000");
  });

  it("is called by its port without a name, and shows nothing for a call that failed", () => {
    const { host, activity } = setup();
    const events = [];
    activity.receive(events, shown({ status: "failed", app_shown: undefined }));
    activity.render(host, { running: false, status: "succeeded", events });
    expect(host.querySelector(".agent-page-pin").hidden).toBe(true);
    activity.receive(events, shown({ id: "completion:2:call_1/tool" }));
    activity.render(host, { running: false, status: "succeeded", events });
    const card = host.querySelector(".agent-page-pin .agent-app-card");
    expect(card.querySelector(".agent-page-title").textContent).toBe("App on port 3000");
    expect(card.querySelector(".agent-page-meta").textContent).toBe("Runs in your workspace");
  });

  it("opens the app's address in a tab opened within the click, cut off from this page", async () => {
    const { app, host, activity } = setup();
    const opened = tabs(app.window);
    const fetch = answers(app.window, { running: true, url: "https://apps.example.com/__consens/open?t=TOKEN" });
    const events = [];
    activity.receive(events, shown({}));
    activity.render(host, { running: false, status: "succeeded", events });
    const card = host.querySelector(".agent-app-card");
    const open = card.querySelector(".agent-page-open");
    open.click();
    // Before the server answered: the tab is there (no pop-up to block), the button waits.
    expect(opened).toHaveLength(1);
    expect(opened[0].address).toBe("about:blank");
    expect(open.disabled).toBe(true);
    expect(open.textContent).toBe("Opening…");
    await settle();
    const [path, request] = fetch.mock.calls[0];
    expect(path).toBe("/agent/workspace/app");
    expect(request.method).toBe("POST");
    expect(request.headers.Authorization).toBe("Bearer id-token");
    expect(JSON.parse(request.body)).toEqual({ process: "abcd1234", port: 3000, path: "/app" });
    expect(opened[0].opener).toBeNull();
    expect(opened[0].replaced).toBe("https://apps.example.com/__consens/open?t=TOKEN");
    expect(opened[0].closed).toBe(false);
    expect(open.disabled).toBe(false);
    expect(open.textContent).toBe("Open");
  });

  it("says that the app has ended and lets the user ask the agent to start it again", async () => {
    const { app, host, activity } = setup();
    const opened = tabs(app.window);
    const fetch = answers(app.window, { running: false });
    const asked = vi.fn();
    app.window.addEventListener("consensio:app-restart", asked);
    const events = [];
    activity.receive(events, shown({}));
    activity.render(host, { running: false, status: "succeeded", events });
    const card = host.querySelector(".agent-app-card");
    const open = card.querySelector(".agent-page-open");
    open.click();
    await settle();
    // The server found its process ended: no tab stays, the card says so.
    expect(opened[0].closed).toBe(true);
    expect(card.dataset.state).toBe("ended");
    expect(card.querySelector(".agent-page-meta").textContent).toBe("Ended in the workspace");
    expect(open.textContent).toBe("Start again");
    // The next click asks the agent (agent-chat.js restartApp), not the server.
    open.click();
    await settle();
    expect(asked).toHaveBeenCalledTimes(1);
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(opened).toHaveLength(1);
  });

  it("knows the process's own limit without asking", () => {
    const { app, host, activity } = setup();
    const opened = tabs(app.window);
    const asked = vi.fn();
    app.window.addEventListener("consensio:app-restart", asked);
    const events = [];
    activity.receive(events, shown({ ends_at: Date.now() - 1000 }));
    activity.render(host, { running: false, status: "succeeded", events });
    const card = host.querySelector(".agent-app-card");
    expect(card.dataset.state).toBe("ended");
    expect(card.querySelector(".agent-page-open").textContent).toBe("Start again");
    card.querySelector(".agent-page-open").click();
    expect(asked).toHaveBeenCalledTimes(1);
    expect(opened).toHaveLength(0);
  });

  it("says why it could not open: a blocked tab, or the server's words", async () => {
    const { app, host, activity } = setup();
    app.window.open = vi.fn(() => null);
    const fetch = answers(app.window, {});
    const events = [];
    activity.receive(events, shown({}));
    activity.render(host, { running: false, status: "succeeded", events });
    const card = host.querySelector(".agent-app-card");
    card.querySelector(".agent-page-open").click();
    await settle();
    expect(fetch).not.toHaveBeenCalled();
    expect(card.dataset.outcome).toBe("failed");
    expect(card.querySelector(".agent-page-meta").textContent).toContain("blocked the new tab");
    // The server's refusal, with the tab closed again.
    const opened = tabs(app.window);
    answers(app.window, { error: "The workspace is not reachable right now. Try again." }, 503);
    card.querySelector(".agent-page-open").click();
    await settle();
    expect(opened[0].closed).toBe(true);
    expect(card.querySelector(".agent-page-meta").textContent).toBe("The workspace is not reachable right now. Try again.");
    expect(card.querySelector(".agent-page-open").textContent).toBe("Open");
  });

  it("stays while the agent opens the app for its own look at it (AGENT_SERVER_AS_APP)", () => {
    const { host, activity } = setup();
    const events = [];
    activity.receive(events, shown({ app_title: "Todo app" }));
    activity.receive(events, { version: 1, kind: "tool", id: "completion:2:call_1/tool", name: "browser",
      status: "succeeded", action: "open", url: "http://localhost:3000/app", title: "Todo app" });
    activity.render(host, { running: false, status: "succeeded", events });
    const pin = host.querySelector(".agent-page-pin");
    expect(pin.hidden).toBe(false);
    expect(pin.querySelector(".agent-app-card .agent-page-title").textContent).toBe("Todo app");
  });

  it("gives its place to a page the agent opens for the user after it, and takes it back", () => {
    const { host, activity } = setup();
    const events = [];
    activity.receive(events, shown({}));
    activity.render(host, { running: true, status: "running", events });
    expect(host.querySelector(".agent-page-pin .agent-app-card")).not.toBeNull();
    activity.receive(events, { version: 1, kind: "tool", id: "completion:2:call_1/tool", name: "browser",
      status: "succeeded", action: "open", for_user: true, url: "https://example.org/", title: "Example" });
    activity.render(host, { running: true, status: "running", events });
    expect(host.querySelector(".agent-page-pin .agent-app-card")).toBeNull();
    expect(host.querySelector(".agent-page-pin .agent-page-title").textContent).toBe("Example");
    activity.receive(events, shown({ id: "completion:3:call_1/tool", process: "0000ffff", app_port: 5173 }));
    activity.render(host, { running: true, status: "running", events });
    expect(host.querySelector(".agent-page-pin .agent-app-card .agent-page-title").textContent).toBe("App on port 5173");
    expect(host.querySelectorAll(".agent-page-pin .agent-page-card")).toHaveLength(1);
  });
});
