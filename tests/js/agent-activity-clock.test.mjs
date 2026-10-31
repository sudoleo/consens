import { describe, expect, it, vi } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

// "Working for 9s" ticks in a field of fixed width: the chevron and the
// model icons after it stay put while it counts and when it ends (Apple
// audit A7). The words themselves do not change.
describe("activity clock", () => {
  it("keeps its words and sizes its time slot by unit, with the other verb reserved", () => {
    vi.useFakeTimers();
    const app = loadScripts(["static/js/agent-activity.js"], { body: '<div id="host"></div>' });
    const host = app.document.getElementById("host");
    const activity = app.window.App.agentActivity;
    activity.render(host, { running: true, elapsedMs: 9000, status: "running", events: [] });
    const title = host.querySelector(".agent-activity-title");
    const time = title.querySelector(".agent-activity-time");
    const verb = title.querySelector(".agent-activity-verb");
    expect(title.textContent).toBe("Working for 9s");
    // The first minute holds only the seconds slot: the minutes slot left a
    // wide gap before the chevron.
    expect(time.dataset.unit).toBe("seconds");
    expect(verb.dataset.ghost).toBe("Thought for");
    activity.render(host, { running: true, elapsedMs: 10000, status: "running", events: [] });
    expect(title.textContent).toBe("Working for 10s");
    expect(time.dataset.unit).toBe("seconds");
    expect(title.querySelector(".agent-activity-time")).toBe(time);
    activity.render(host, { running: true, elapsedMs: 72000, status: "running", events: [] });
    expect(title.textContent).toBe("Working for 1m 12s");
    expect(time.dataset.unit).toBe("minutes");
    activity.render(host, { running: false, elapsedMs: 72000, status: "succeeded", events: [] });
    expect(title.textContent).toBe("Thought for 1m 12s");
    expect(time.dataset.unit).toBe("minutes");
    // Its clock is still: the field takes its own words, no double gap (B14).
    expect(verb.dataset.ghost).toBeUndefined();
    activity.render(host, { running: false, elapsedMs: 72000, status: "failed", events: [] });
    expect(title.textContent).toBe("Failed after 1m 12s");
    expect(verb.dataset.ghost).toBeUndefined();
    activity.dispose(host);
    // A saved turn that never ticked here sizes the slot by its own value.
    const saved = app.document.createElement("div");
    activity.render(saved, { running: false, elapsedMs: 18000, status: "succeeded", events: [] });
    expect(saved.querySelector(".agent-activity-time").dataset.unit).toBe("seconds");
    vi.useRealTimers();
    app.dom.window.close();
  });

  it("ends a short run in the seconds slot and lets a later end widen it once", () => {
    vi.useFakeTimers();
    const app = loadScripts(["static/js/agent-activity.js"], { body: '<div id="short"></div><div id="edge"></div>' });
    const activity = app.window.App.agentActivity;
    const short = app.document.getElementById("short");
    activity.render(short, { running: true, elapsedMs: 40000, status: "running", events: [] });
    activity.render(short, { running: false, elapsedMs: 41000, status: "succeeded", events: [] });
    expect(short.querySelector(".agent-activity-title").textContent).toBe("Thought for 41s");
    expect(short.querySelector(".agent-activity-time").dataset.unit).toBe("seconds");
    // The server's end can land past the minute the browser last showed.
    const edge = app.document.getElementById("edge");
    activity.render(edge, { running: true, elapsedMs: 59000, status: "running", events: [] });
    expect(edge.querySelector(".agent-activity-time").dataset.unit).toBe("seconds");
    activity.render(edge, { running: false, elapsedMs: 60400, status: "succeeded", events: [] });
    expect(edge.querySelector(".agent-activity-title").textContent).toBe("Thought for 1m 0s");
    expect(edge.querySelector(".agent-activity-time").dataset.unit).toBe("minutes");
    activity.dispose(short);
    activity.dispose(edge);
    vi.useRealTimers();
    app.dom.window.close();
  });
});

// One state everywhere (UX audit E1): while the reviewers check the answer
// the head said "Working for", and while the run waited for the user its
// clock ran on.
describe("activity head while the run reviews or waits", () => {
  it("says Reviewing while the reviewers check, and stands still while it waits for the user", () => {
    vi.useFakeTimers();
    const app = loadScripts(["static/js/agent-activity.js"], { body: '<div id="host"></div>' });
    const host = app.document.getElementById("host");
    const activity = app.window.App.agentActivity;
    // The page's wall clock, as the caller's elapsed time counts it.
    let wall = Date.parse("2026-10-29T10:00:00Z");
    app.window.Date.now = () => wall;
    const advance = ms => { wall += ms; vi.advanceTimersByTime(ms); };
    const title = () => host.querySelector(".agent-activity-title").textContent;
    activity.render(host, { running: true, elapsedMs: 139000, status: "running", events: [],
      review: { mode: "audit", status: "running" }, answerText: "The answer." });
    expect(title()).toBe("Reviewing · 2m 19s");
    expect(host.querySelector(".agent-activity-verb").dataset.ghost).toBeUndefined();
    // The comparison mode's answer check is gone (2026-10-31): a review
    // without the reviewers' mode is no phase of its own.
    activity.render(host, { running: true, elapsedMs: 139000, status: "running", events: [],
      review: { status: "running" }, answerText: "The answer." });
    expect(title()).toBe("Working for 2m 19s");
    expect(activity.PHASE_WORDS.checking).toBeUndefined();
    // A pause: the head says so, and its clock does not move while it lasts.
    const hold = { version: 1, kind: "hold", id: "hold-a1", step_id: "hold", reviewer: "Claude", halt: "harm",
      reason: "Deletes files.", state: "waiting" };
    activity.render(host, { running: true, elapsedMs: 150000, status: "running", events: [hold] });
    expect(title()).toBe("Paused · 2m 30s");
    advance(4000);
    activity.render(host, { running: true, elapsedMs: 154000, status: "running", events: [hold] });
    expect(title()).toBe("Paused · 2m 30s");
    // The agent's own question waits for the user too.
    const ask = { ...hold, id: "hold-a2", ask: "browser", request: "Log in.", reviewer: "", halt: "" };
    activity.render(host, { running: true, elapsedMs: 154000, status: "running", events: [ask] });
    expect(title()).toBe("Waiting for you · 2m 30s");
    // Decided: it works on from where it stood, without the time it waited.
    advance(6000);
    activity.render(host, { running: true, elapsedMs: 160000, status: "running", events: [{ ...ask, state: "handed_back" }] });
    expect(title()).toBe("Working for 2m 30s");
    activity.dispose(host);
    vi.useRealTimers();
    app.dom.window.close();
  });

  it("leaves the time a saved turn waited for the user out of its duration", () => {
    const app = loadScripts(["static/js/agent-activity.js"], { body: "" });
    const { savedDuration } = app.window.App.agentActivity;
    const turn = { created_at: "2026-10-29T10:00:00Z", completed_at: "2026-10-29T10:32:10Z" };
    expect(savedDuration(turn)).toBe(1930000);
    expect(savedDuration({ ...turn, agent_wait_seconds: 1810.5 })).toBe(119500);
    expect(savedDuration({ ...turn, agent_wait_seconds: "1810" })).toBe(1930000);
    app.dom.window.close();
  });
});

// On the German page "{0} reasoning" took the whole line, model name
// included, and the line was written anew on every render (2026-10-23).
describe("run details on a German page", () => {
  it("translates the reasoning on its own, keeps the model's name and the line", async () => {
    const app = loadScripts(["static/js/i18n.js", "static/js/app-text.js", "static/js/agent-activity.js"], {
      body: '<div id="host"></div>', base: false,
      before(window) {
        window.__consensI18n = { lang: "de", entries: {
          "{0} reasoning": "Nachdenken: {0}", "High": "Hoch", "Reasoning off": "Nachdenken aus" } };
      },
    });
    const host = app.document.getElementById("host");
    const activity = app.window.App.agentActivity;
    const settled = async () => { await Promise.resolve(); app.window.App.i18n.flush(); };
    const settings = { label: "Claude Sonnet 5.5", reasoning_effort: "high" };
    activity.render(host, { running: false, elapsedMs: 9000, status: "succeeded", events: [], settings });
    await settled();
    const details = host.querySelector(".agent-activity-run-details");
    expect(details.textContent).toBe("Claude Sonnet 5.5 · Nachdenken: Hoch");
    const name = details.firstElementChild;
    activity.render(host, { running: false, elapsedMs: 9000, status: "succeeded", events: [], settings });
    await settled();
    expect(details.firstElementChild).toBe(name);
    expect(details.textContent).toBe("Claude Sonnet 5.5 · Nachdenken: Hoch");
    activity.render(host, { running: false, elapsedMs: 9000, status: "succeeded", events: [],
      settings: { label: "Claude Sonnet 5.5", reasoning_effort: "none" } });
    await settled();
    expect(details.textContent).toBe("Claude Sonnet 5.5 · Nachdenken aus");
    app.dom.window.close();
  });
});
