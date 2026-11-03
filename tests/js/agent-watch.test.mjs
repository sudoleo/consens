/**
 * The Watch card under an Agent answer (agent-watch.js): since 2026-11-03 a
 * Watch runs the Agent again in its chat. The card shows the task the Agent
 * prepared, starts it through POST /agent/watches with only the chat, the
 * turn and the schedule, and reads what runs from the chat's Watches.
 */
import { describe, expect, it, vi } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

const CHAT = "c".repeat(32);
const TASK = "Check on ironman.com whether registration for IRONMAN Hamburg 2027 is open.";
const PROPOSAL = { task: TASK, goal: "Registration is open", interval: "daily", run_time: "", run_weekday: "" };

async function settle() {
  for (let i = 0; i < 40; i += 1) await Promise.resolve();
}

function boot({ watches = [], intervals = ["daily", "weekly"], active_count = 0, active_limit = 2, create = null } = {}) {
  const server = { watches, calls: [] };
  const harness = loadScripts(["static/js/watch-fields.js", "static/js/agent-watch.js"], {
    body: '<div id="agentAnswer"><div id="agentAnswerBody">The answer.</div></div>',
    before(window) {
      window.auth = { currentUser: { uid: "watch-user", getIdToken: async () => "token" } };
      window.App = { trackAppEvent: vi.fn() };
      window.fetch = async (url, options = {}) => {
        const body = options.body ? JSON.parse(options.body) : null;
        server.calls.push({ url, method: options.method || "GET", body });
        const reply = (status, data) => ({ ok: status < 400, status, json: async () => data });
        if (url === "/agent/watches" && options.method === "POST") {
          if (create) return reply(create.status, create.data);
          const watch = { id: "w1", chat_id: CHAT, turn_id: body.turn_id, task: TASK, goal: "Registration is open",
            status: "active", interval: body.interval, run_time: body.run_time, run_weekday: body.run_weekday,
            timezone: body.timezone, next_run_at: "2026-11-04T07:00:00+00:00", last_run: null };
          server.watches = [watch, ...server.watches];
          return reply(201, { watch });
        }
        if (url === "/agent/watches/w1/stop") {
          server.watches = server.watches.map(watch => ({ ...watch, status: "done", ended: "user", next_run_at: null }));
          return reply(200, { watch: server.watches[0] });
        }
        if (url.startsWith("/agent/watches?chat_id=")) {
          return reply(200, { watches: server.watches, intervals, active_count, active_limit });
        }
        return reply(404, {});
      };
    },
  });
  const body = harness.document.getElementById("agentAnswerBody");
  const render = options => harness.window.App.agentWatch.render(body, { key: "run-1", chatId: CHAT, turnId: "t1", ...options });
  const card = () => harness.document.querySelector(".agent-watch-card");
  const text = selector => card().querySelector(selector).textContent;
  return { ...harness, server, render, card, text };
}

describe("Agent Watch card", () => {
  it("shows the task, when it is done and when it runs", async () => {
    const { render, card, text } = boot();
    render({ proposal: null });
    expect(card()).toBeNull();
    render({ proposal: PROPOSAL });
    await settle();
    expect(card().previousElementSibling.id).toBe("agentAnswerBody");
    expect(card().dataset.state).toBe("proposal");
    expect(text(".agent-watch-question")).toBe(TASK);
    expect(text(".agent-watch-goal")).toBe("Done when: Registration is open");
    expect(text(".agent-watch-settings")).toBe("Daily at 08:00");
    expect(card().querySelector(".agent-watch-start").disabled).toBe(false);
    expect(card().querySelector(".agent-watch-end").hidden).toBe(true);
  });

  it("starts with only the chat, the turn and the schedule", async () => {
    const { window, server, render, card, text } = boot();
    render({ proposal: PROPOSAL });
    await settle();
    card().querySelector(".agent-watch-start").click();
    await settle();
    const post = server.calls.find(call => call.method === "POST");
    expect(post.url).toBe("/agent/watches");
    expect(post.body).toEqual({ chat_id: CHAT, turn_id: "t1", interval: "daily", run_time: "08:00", run_weekday: "",
      timezone: window.Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC" });
    expect(card().dataset.state).toBe("watching");
    expect(text(".agent-watch-title")).toBe("Watch running");
    expect(text(".agent-watch-settings")).toMatch(/^Daily at 08:00 · next run /);
    expect(card().querySelector(".agent-watch-start").hidden).toBe(true);
    expect(window.App.trackAppEvent).toHaveBeenCalledWith("app_watch_created",
      expect.objectContaining({ source: "agent", has_goal: true, interval: "daily" }));
  });

  it("offers only the intervals the account has, and a time for daily and weekly", async () => {
    const { window, server, render, card } = boot({ intervals: ["every_6_hours", "daily", "weekly"] });
    render({ proposal: { ...PROPOSAL, interval: "hourly" } });
    await settle();
    // Hourly is not on this account: the shortest it has.
    expect(card().querySelector(".agent-watch-settings").textContent).toBe("Every 6 hours");
    card().querySelector(".agent-watch-link").click();
    const select = card().querySelector(".agent-watch-interval");
    const time = card().querySelector(".agent-watch-time");
    expect([...select.options].map(option => option.value)).toEqual(["every_6_hours", "daily", "weekly"]);
    expect(time.hidden).toBe(true);
    select.value = "weekly";
    select.dispatchEvent(new window.Event("change"));
    expect(time.hidden).toBe(false);
    time.value = "07:30";
    time.dispatchEvent(new window.Event("change"));
    card().querySelector(".agent-watch-start").click();
    await settle();
    const post = server.calls.find(call => call.method === "POST");
    expect([post.body.interval, post.body.run_time]).toEqual(["weekly", "07:30"]);
  });

  it("says what the last run found and ends a running Watch", async () => {
    const watch = { id: "w1", chat_id: CHAT, turn_id: "t1", task: TASK, goal: "", status: "active", interval: "hourly",
      next_run_at: "2026-11-04T07:00:00+00:00",
      last_run: { at: new Date().toISOString(), outcome: "finding", summary: "Registration is open." } };
    const { server, render, card, text } = boot({ watches: [watch], active_count: 1 });
    render({ proposal: PROPOSAL });
    await settle();
    expect(card().dataset.state).toBe("watching");
    expect(text(".agent-watch-goal")).toBe("Runs until you end it");
    expect(text(".agent-watch-status")).toMatch(/: Registration is open\.$/);
    card().querySelector(".agent-watch-end").click();
    await settle();
    expect(server.calls.some(call => call.url === "/agent/watches/w1/stop" && call.method === "POST")).toBe(true);
    expect(card().dataset.state).toBe("ended");
    expect(text(".agent-watch-title")).toBe("Watch ended");
    expect(card().querySelector(".agent-watch-end").hidden).toBe(true);
  });

  it("does not offer a second Watch in a chat that has one, or past the account's limit", async () => {
    const other = { id: "w7", chat_id: CHAT, turn_id: "t0", task: "Another task of this chat.", status: "active", interval: "daily" };
    const taken = boot({ watches: [other], active_count: 1 });
    taken.render({ proposal: PROPOSAL });
    await settle();
    expect(taken.card().dataset.state).toBe("taken");
    expect(taken.card().querySelector(".agent-watch-start").disabled).toBe(true);
    expect(taken.text(".agent-watch-status")).toBe("This chat already has a Watch. End it first to start this one.");
    const full = boot({ active_count: 2, active_limit: 2 });
    full.render({ proposal: PROPOSAL });
    await settle();
    expect(full.card().dataset.state).toBe("full");
    expect(full.text(".agent-watch-status")).toBe("All your Watches are in use. End one in its chat first.");
  });

  it("keeps the reason of a refused start", async () => {
    const { render, card, text } = boot({ create: { status: 403, data: { error: "Runs this often need a higher plan.",
      code: "interval_not_allowed" } } });
    render({ proposal: PROPOSAL });
    await settle();
    card().querySelector(".agent-watch-start").click();
    await settle();
    expect(card().dataset.state).toBe("proposal");
    expect(text(".agent-watch-status")).toBe("Watch not started. Runs this often need a higher plan.");
  });

  it("shows no card for a proposal from before Watches ran the Agent, and leaves with its answer", async () => {
    const { render, card } = boot();
    render({ proposal: { question: "When will GPT-6 come out?", goals: [], interval: "weekly" } });
    expect(card()).toBeNull();
    render({ proposal: PROPOSAL });
    await settle();
    render({ key: "run-2", proposal: null });
    expect(card()).toBeNull();
  });
});
