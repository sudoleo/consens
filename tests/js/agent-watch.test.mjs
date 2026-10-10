/**
 * The Watch card under an Agent answer (agent-watch.js): the Agent only
 * proposes, the card starts the Watch through POST /api/watch and reads
 * "already watched" and "no free slot" from the account's watch list.
 */
import { describe, expect, it, vi } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

const QUESTION = "When will OpenAI release GPT-6 to the public?";
const PROPOSAL = { question: QUESTION, goals: ["GPT-6 is officially released", "A date is announced"], interval: "weekly" };

async function settle() {
  for (let i = 0; i < 30; i += 1) await Promise.resolve();
}

function boot({ watches = [], limits = { plan: "free", active_count: 0, active_limit: 3 }, create = null } = {}) {
  const server = { watches, limits, calls: [] };
  const harness = loadScripts(
    ["static/js/watch-state.js", "static/js/watch.js", "static/js/agent-watch.js"],
    {
      body: '<div id="agentAnswer"><div id="agentAnswerBody">The answer.</div></div>',
      before(window) {
        window.auth = { currentUser: { uid: "watch-user", getIdToken: async () => "token" } };
        window.App = { trackAppEvent: vi.fn() };
        window.fetch = async (url, options = {}) => {
          const body = options.body ? JSON.parse(options.body) : null;
          server.calls.push({ url, method: options.method || "GET", body });
          const reply = (status, data) => ({ ok: status < 400, status, json: async () => data });
          if (url === "/api/watch" && options.method === "POST") {
            if (create) return reply(create.status, create.data);
            const watch = { id: "w1", status: "active", question: body.question, condition: body.condition,
              interval: body.interval, run_weekday: body.run_weekday, run_time: body.run_time, timezone: body.timezone };
            server.watches = [...server.watches, watch];
            server.limits = { ...server.limits, active_count: server.limits.active_count + 1 };
            return reply(200, { status: "success", watch });
          }
          if (url === "/api/my/watches") return reply(200, { watches: server.watches, limits: server.limits });
          return reply(404, {});
        };
      },
    },
  );
  const body = harness.document.getElementById("agentAnswerBody");
  const render = options => harness.window.App.agentWatch.render(body, { key: "run-1", ...options });
  const card = () => harness.document.querySelector(".agent-watch-card");
  return { ...harness, server, render, card };
}

function tomorrow(window) {
  const days = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"];
  const date = new window.Date();
  date.setDate(date.getDate() + 1);
  return days[date.getDay()];
}

describe("Agent Watch card", () => {
  it("waits for the final answer, then shows the question, the goal and the defaults", async () => {
    const { window, render, card } = boot();
    render({ proposal: PROPOSAL, running: true });
    expect(card()).toBeNull();

    render({ proposal: PROPOSAL });
    await settle();
    const day = tomorrow(window);
    expect(card().previousElementSibling.id).toBe("agentAnswerBody");
    expect(card().dataset.state).toBe("proposal");
    expect(card().querySelector(".agent-watch-question").textContent).toBe(QUESTION);
    expect(card().querySelector(".agent-watch-goal").textContent).toBe("Waiting for: GPT-6 is officially released");
    expect(card().querySelector(".agent-watch-settings").textContent)
      .toBe(`Weekly on ${day[0].toUpperCase()}${day.slice(1)} at 09:00 · E-mail · Private`);
    expect(card().querySelector(".agent-watch-start").disabled).toBe(false);
  });

  it("starts the Watch in one click with the most likely goal and the dialog's defaults", async () => {
    const { window, server, render, card } = boot();
    render({ proposal: PROPOSAL });
    await settle();
    card().querySelector(".agent-watch-start").click();
    await settle();
    const post = server.calls.find(call => call.method === "POST");
    expect(post.body).toEqual({
      interval: "weekly", run_weekday: tomorrow(window), email_mode: "changes_only", email_enabled: true,
      telegram_enabled: false, condition: "GPT-6 is officially released", visibility: "private", run_time: "09:00",
      timezone: window.Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC", question: QUESTION,
    });
    expect(card().dataset.state).toBe("watching");
    expect(card().querySelector(".agent-watch-title").textContent).toBe("Watching");
    expect(card().querySelector(".agent-watch-status").textContent).toMatch(/^Checks weekly on /);
    expect(card().querySelector(".agent-watch-start").hidden).toBe(true);
    expect(window.App.trackAppEvent).toHaveBeenCalledWith("app_watch_created",
      expect.objectContaining({ source: "agent", has_goal: true }));
  });

  it("says when the question is already watched, whatever its spelling", async () => {
    const { render, card } = boot({ watches: [{ id: "w9", status: "paused", question: "when will openai release GPT-6 to the public",
      condition: "", interval: "monthly" }] });
    render({ proposal: PROPOSAL });
    await settle();
    expect(card().dataset.state).toBe("watching");
    expect(card().querySelector(".agent-watch-title").textContent).toBe("Watch paused");
    expect(card().querySelector(".agent-watch-status").textContent).toBe("You already watch this question. The Watch is paused.");
    expect(card().querySelector(".agent-watch-start").hidden).toBe(true);
  });

  it("explains a full account instead of offering a button that fails", async () => {
    const { render, card } = boot({ limits: { plan: "free", active_count: 1, active_limit: 1 },
      watches: [{ id: "w2", status: "active", question: "Another question?" }] });
    render({ proposal: PROPOSAL });
    await settle();
    expect(card().dataset.state).toBe("full");
    expect(card().querySelector(".agent-watch-start").disabled).toBe(true);
    expect(card().querySelector(".agent-watch-status").textContent).toBe(
      "Your Watch slot is in use. Pause that Watch to start a new one.");
    expect(card().querySelector(".agent-watch-link:not([hidden])")).not.toBeNull();
  });

  it("turns a refused start into the state the account really has", async () => {
    const { server, render, card } = boot({ create: { status: 409, data: { error: "This question is already watched." } } });
    render({ proposal: PROPOSAL });
    await settle();
    server.watches = [{ id: "w3", status: "active", question: QUESTION, interval: "weekly", run_time: "09:00" }];
    card().querySelector(".agent-watch-start").click();
    await settle();
    expect(card().dataset.state).toBe("watching");
    expect(card().querySelector(".agent-watch-status").textContent).not.toContain("could not be started");
  });

  it("opens the create dialog prefilled for anything else", async () => {
    const { window, render, card } = boot();
    render({ proposal: { ...PROPOSAL, interval: "monthly" } });
    await settle();
    window.App.watchUi.openWatchDialog = vi.fn();
    card().querySelectorAll(".agent-watch-link")[0].click();
    expect(window.App.watchUi.openWatchDialog).toHaveBeenCalledWith("create", {
      question: QUESTION, goals: PROPOSAL.goals, goal: "GPT-6 is officially released", interval: "monthly", source: "agent",
    });
  });

  it("proposes weekly when the account cannot check daily, and leaves with its answer", async () => {
    const { render, card } = boot();
    render({ proposal: { question: QUESTION, goals: [], interval: "daily" } });
    await settle();
    expect(card().querySelector(".agent-watch-settings").textContent).toMatch(/^Weekly on /);
    expect(card().querySelector(".agent-watch-goal").textContent).toBe("Any change to the answer");
    render({ key: "run-2", proposal: null });
    expect(card()).toBeNull();
  });
});
