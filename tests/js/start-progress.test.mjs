import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

// A start the user waits for, counted down the Apple way (start-progress.js,
// since 2026-11-02): a thin bar toward the server's estimate and the time
// left under it; the chat's step and the live view show it.
const NOW = Date.parse("2026-11-02T15:37:02Z");

function setup(files = ["static/js/start-progress.js"]) {
  const app = loadScripts(files, { body: '<div id="host"></div>' });
  const { window } = app;
  // The window's own clock and timers: a test moves time on by hand.
  const clock = { now: NOW, intervals: [], timeouts: [] };
  window.Date.now = () => clock.now;
  window.setInterval = (fn, ms) => clock.intervals.push({ fn, ms, next: clock.now + ms, live: true });
  window.clearInterval = id => { if (clock.intervals[id - 1]) clock.intervals[id - 1].live = false; };
  window.setTimeout = (fn, ms = 0) => clock.timeouts.push({ fn, at: clock.now + ms, live: true });
  window.clearTimeout = id => { if (clock.timeouts[id - 1]) clock.timeouts[id - 1].live = false; };
  const advance = ms => {
    const end = clock.now + ms;
    for (;;) {
      const due = clock.intervals.filter(timer => timer.live && timer.next <= end).sort((a, b) => a.next - b.next)[0];
      if (!due) break;
      clock.now = due.next;
      due.next += due.ms;
      due.fn();
    }
    clock.now = end;
    for (const timer of clock.timeouts) if (timer.live && timer.at <= end) { timer.live = false; timer.fn(); }
  };
  return { ...app, App: window.App, host: app.document.getElementById("host"), advance };
}
const left = bar => bar.node.querySelector(".start-progress-left").textContent;

describe("the start's bar", () => {
  it("shows only once a start takes a while, then counts the estimate down to 'Almost done…'", () => {
    const { App, host, advance } = setup();
    const bar = App.startProgress.create();
    host.append(bar.node);
    bar.set(new Date(NOW + 65_000).toISOString());
    // A quick start never flashes a bar.
    expect(bar.node.hidden).toBe(true);
    advance(1_500);
    expect(bar.node.hidden).toBe(false);
    expect(bar.node.getAttribute("role")).toBe("progressbar");
    expect(left(bar)).toBe("About a minute left");
    advance(30_000);
    expect(left(bar)).toBe("About 35 seconds left");
    expect(bar.value).toBeGreaterThan(.4);
    expect(bar.value).toBeLessThan(.5);
    advance(40_000);
    // Past the estimate: never full before it is done, and still moving.
    expect(left(bar)).toBe("Almost done…");
    const late = bar.value;
    expect(late).toBeGreaterThanOrEqual(.9);
    expect(late).toBeLessThan(.98);
    advance(20_000);
    expect(bar.value).toBeGreaterThan(late);
    expect(bar.value).toBeLessThan(.98);
    bar.done();
    expect(bar.value).toBe(1);
    expect(bar.node.getAttribute("aria-valuenow")).toBe("100");
    // Full for a moment, then gone.
    advance(500);
    expect(bar.node.hidden).toBe(true);
  });

  it("never runs backwards: a longer estimate goes on from where the bar stands", () => {
    const { App, host, advance } = setup();
    const bar = App.startProgress.create();
    host.append(bar.node);
    bar.set(NOW + 15_000);
    advance(10_000);
    const before = bar.value;
    expect(before).toBeGreaterThan(.5);
    // The VM was new after all: its setup takes a minute more.
    bar.set(NOW + 75_000);
    advance(250);
    expect(bar.value).toBeGreaterThanOrEqual(before);
    expect(left(bar)).toBe("About a minute left");
    advance(30_000);
    expect(bar.value).toBeGreaterThan(before);
    expect(left(bar)).toBe("About 35 seconds left");
  });

  it("names minutes as whole sentences, and a bar off the page stops counting", () => {
    const { App, host, advance } = setup();
    expect(App.startProgress.leftText(150_000)).toBe("About 3 minutes left");
    expect(App.startProgress.leftText(9_000)).toBe("Almost done…");
    const bar = App.startProgress.create();
    host.append(bar.node);
    bar.set(NOW + 60_000);
    advance(2_000);
    bar.node.remove();
    advance(1_000);
    const value = bar.value;
    advance(10_000);
    expect(bar.value).toBe(value);
  });
});

describe("the bar where the user waits", () => {
  it("stands under the calm line of a step that waits for the workspace's start, and goes with it", () => {
    const { App, host, advance } = setup(["static/js/user-settings.js", "static/js/start-progress.js",
      "static/js/agent-activity.js"]);
    const activity = App.agentActivity;
    const events = [];
    const step = fields => ({ version: 1, kind: "tool", id: "completion:1:call_1/tool", name: "browser",
      action: "open", url: "https://web.whatsapp.com/", status: "running", ...fields });
    const render = () => activity.render(host, { running: true, status: "running", events });
    activity.receive(events, step({ starting_until: new Date(NOW + 15_000).toISOString() }));
    render();
    const preview = host.querySelector(".agent-progress");
    expect(preview.querySelector(".agent-current-status").textContent).toBe("Starting the browser…");
    const bar = preview.querySelector(".agent-start-progress");
    expect(bar.previousElementSibling.classList.contains("agent-current-status")).toBe(true);
    advance(2_000);
    expect(bar.hidden).toBe(false);
    expect(bar.querySelector(".start-progress-left").textContent).toBe("About 15 seconds left");
    // The browser runs: the step is itself again, the bar gone.
    activity.receive(events, step({ starting_until: null, started_at: new Date(NOW + 9_000).toISOString() }));
    render();
    expect(preview.querySelector(".agent-start-progress")).toBeNull();
    activity.dispose(host);
  });

  it("stands flush under a tool's line in the detailed lines, after the mark only under the calm one (2026-11-03)", () => {
    // Max's screenshot: under "Listing the tabs" the bar stood a mark's
    // width in, though a tool's line has no mark.
    const { App, host } = setup(["static/js/user-settings.js", "static/js/start-progress.js",
      "static/js/agent-activity.js"]);
    App.userSettings.set("detailed_progress", true);
    const activity = App.agentActivity;
    const events = [];
    activity.receive(events, { version: 1, kind: "tool", id: "completion:1:call_1/tool", name: "browser",
      action: "tabs", status: "running", starting_until: new Date(NOW + 15_000).toISOString() });
    activity.render(host, { running: true, status: "running", events });
    const bar = host.querySelector(".agent-progress .agent-start-progress");
    expect(bar.previousElementSibling.classList.contains("agent-vm")).toBe(true);
    expect(bar.previousElementSibling.classList.contains("agent-current-status")).toBe(false);
    activity.dispose(host);
    // The indent belongs to the line with the mark alone.
    const css = readFileSync(new URL("../../static/css/agent-chat.css", import.meta.url), "utf8")
      .replace(/\/\*[\s\S]*?\*\//g, "");
    const rules = css.split("}").filter(rule => /\.agent-start-progress\s*\{/.test(rule));
    expect(rules.map(rule => rule.trim().split("{")[0].trim())).toEqual([
      ".agent-progress .agent-start-progress",
      ".agent-progress .agent-current-status + .agent-start-progress",
    ]);
    expect(rules[0]).not.toMatch(/padding-left/);
    expect(rules[1]).toMatch(/padding-left: calc\(\.86em \* 1\.395 \+ \.55em\)/);
  });
});
