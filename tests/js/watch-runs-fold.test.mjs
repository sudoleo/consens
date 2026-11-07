/**
 * A Watch's runs in its chat (thread-history.js): a run's
 * message says the Watch sent it and when, runs that found nothing, one
 * after another on the same day, fold into one line, and what a run found
 * stays a turn of its own. The chat reads as one running
 * conversation ("wie bei WhatsApp mit Datum getrennt"): each day starts
 * with its name, and a run that sends the task the chat already shows is
 * only its line.
 */
import { describe, expect, it } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

const RUN = { watch_id: "w".repeat(32), scheduled_at: "2026-11-03T07:00:00+00:00", request_id: "watch.w.1", goal: "" };
const TASK = "Check whether registration is open.";

// A local time `daysBack` calendar days ago, as the server sends it.
function at(daysBack, hour, minute = 0) {
  const day = new Date();
  day.setDate(day.getDate() - daysBack);
  day.setHours(hour, minute, 0, 0);
  return day.toISOString();
}

function turn(id, extra = {}) {
  return { id: id.repeat(32), turn_id: id.repeat(32), question: TASK,
    consensus: "Still closed.", status: "completed", mode: "Agent", execution_mode: "agent",
    created_at: at(0, 9), ...extra };
}

const quiet = (id, when) => turn(id, { agent_settings: { watch_run: RUN }, created_at: when });
const found = (id, when) => turn(id, { agent_settings: { watch_run: RUN }, consensus: "It is open.", created_at: when,
  agent_watch_run: { finding: { summary: "Open.", evidence_url: "https://www.ironman.com" } } });

function boot() {
  return loadScripts(["static/js/thread-history.js"], {
    body: '<div id="threadHistory" hidden></div>'
      + '<div id="threadAsk" class="thread-ask"><h2 class="visually-hidden">Your message</h2>'
      + '<div class="thread-ask-bubble"><div class="thread-ask-text" id="threadAskText"></div></div></div>',
  });
}

const days = root => [...root.querySelectorAll(".thread-day")].map(node => node.textContent);
const weekday = value => new Date(value).toLocaleDateString("en-US", { weekday: "long" });

describe("A Watch's runs in its chat", () => {
  it("folds quiet runs by day, keeps a finding and shows the task once", () => {
    const { window, document } = boot();
    const chat = [
      turn("a", { question: "Tell me when registration opens.", created_at: at(2, 9) }),
      quiet("b", at(2, 10)), quiet("c", at(1, 10)), quiet("d", at(1, 16)),
      found("e", at(0, 10)), quiet("f", at(0, 16)),
    ];
    window.App.followup.renderStoredTurns(chat);
    const history = document.getElementById("threadHistory");
    const folds = [...history.querySelectorAll(".thread-watch-fold-button")];
    // A new day starts a new line: the runs of yesterday never fold with
    // today's. The run that first brought the task stays open (b).
    expect(folds.map(button => button.textContent)).toEqual([
      "Checked 2 times · nothing new · last 16:00",
      "Checked once · nothing new · 16:00"]);
    const turns = [...history.querySelectorAll(".thread-history-turn")];
    expect(turns.map(node => node.classList.contains("is-watch-folded"))).toEqual([false, false, true, true, false, true]);
    // The user's own message stays; a run says the Watch sent it, and when.
    const heads = turns.map(node => node.querySelector(".thread-history-question"));
    expect(heads[0].querySelector(".thread-watch-run")).toBeNull();
    expect(heads[1].querySelector(".thread-watch-run").textContent).toBe("Scheduled Watch run · 10:00");
    expect(heads[4].querySelector(".thread-watch-run").textContent).toBe("Scheduled Watch run · 10:00");
    // A screen reader hears it by the message's heading, the label once.
    expect(heads[4].querySelector("h2.visually-hidden").textContent).toBe("Scheduled Watch run · 10:00");
    expect(heads[4].querySelector(".thread-watch-run").getAttribute("aria-hidden")).toBe("true");
    expect(heads[0].querySelector("h2.visually-hidden").textContent).toBe("Your message");
    // The task stands once, where it first came; later runs are their line.
    expect(heads.map(head => head.classList.contains("is-watch-repeat"))).toEqual([false, false, true, true, true, true]);
    // Each day starts with its name: the first message, or the line that
    // folds its first runs.
    expect(days(history)).toEqual([weekday(at(2, 9)), "Yesterday", "Today"]);
    expect(heads[0].firstElementChild.className).toBe("thread-day");
    expect(heads[0].querySelector(".thread-day time").dateTime).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(folds[0].parentElement.firstElementChild.textContent).toBe("Yesterday");
    expect(heads[4].querySelector(".thread-day").textContent).toBe("Today");

    folds[0].click();
    expect(folds[0].getAttribute("aria-expanded")).toBe("true");
    expect(turns[2].classList.contains("is-watch-folded")).toBe(false);
    // A later render keeps what the reader opened, and the days.
    window.App.followup.renderStoredTurns([...chat, quiet("g", at(0, 17))]);
    const again = [...history.querySelectorAll(".thread-watch-fold-button")];
    expect(again[0].getAttribute("aria-expanded")).toBe("true");
    expect(again[1].textContent).toBe("Checked 2 times · nothing new · last 17:00");
    expect(days(history)).toEqual([weekday(at(2, 9)), "Yesterday", "Today"]);
  });

  it("names an older day by its date and leaves a chat without a Watch undated", () => {
    const { window, document } = boot();
    const history = document.getElementById("threadHistory");
    window.App.followup.renderStoredTurns([
      turn("a", { question: "Plan my week.", created_at: at(3, 9) }),
      turn("b", { question: "And the weekend?", created_at: at(0, 9) }),
    ]);
    expect(history.querySelector(".thread-day")).toBeNull();
    const old = at(40, 9);
    window.App.followup.renderStoredTurns([quiet("c", old), found("d", at(0, 8))]);
    expect(days(history)).toEqual([window.App.format.date(old), "Today"]);
  });

  it("puts the live message under its day and keeps its line in step", () => {
    const { window, document } = boot();
    const ask = document.getElementById("threadAsk");
    const text = document.getElementById("threadAskText");
    window.App.followup.renderStoredTurns([quiet("a", at(1, 10))]);
    // The run on screen sends the same task today.
    text.dataset.question = TASK;
    window.App.followup.markWatchRun(ask, quiet("b", at(0, 8, 5)));
    expect(ask.querySelector(".thread-watch-run").textContent).toBe("Scheduled Watch run · 08:05");
    expect(ask.firstElementChild.className).toBe("thread-day");
    expect(ask.querySelector(".thread-day").textContent).toBe("Today");
    expect(ask.classList.contains("is-watch-repeat")).toBe(true);
    // The user's own message today: their words, under the same day.
    text.dataset.question = "Thanks, and the price?";
    window.App.followup.markWatchRun(ask, null);
    expect(ask.querySelector(".thread-watch-run")).toBeNull();
    expect(ask.classList.contains("is-watch-repeat")).toBe(false);
    expect(ask.querySelector(".thread-day").textContent).toBe("Today");
    // Another chat without a Watch: no day left on the message.
    window.App.followup.clearHistory();
    expect(ask.querySelector(".thread-day")).toBeNull();
  });

  // Opening a saved Watch chat (firebase.js loadSingleBookmarkUI) projects
  // its run first (showSavedView -> agent-chat.js markWatchRun) and sets the
  // chat's question after; ordered with the question of the chat shown
  // before, or none, the newest run stood under Yesterday, or its task as a
  // bubble again.
  it("orders the days again once the opened chat's question is set", () => {
    const { window, document } = loadScripts(["static/js/app-core.js", "static/js/thread-history.js"], {
      body: '<div id="threadHistory" hidden></div>'
        + '<div id="threadAsk" class="thread-ask" hidden><h2 class="visually-hidden">Your message</h2>'
        + '<div class="thread-ask-bubble"><div class="thread-ask-text" id="threadAskText"></div></div></div>',
    });
    const ask = document.getElementById("threadAsk");
    // From a new chat: the live message is still hidden.
    window.App.followup.renderStoredTurns([quiet("a", at(1, 10))]);
    window.App.followup.markWatchRun(ask, quiet("b", at(0, 8)));
    window.App.setThreadQuestion(TASK);
    expect(ask.querySelector(".thread-day")?.textContent).toBe("Today");
    expect(ask.classList.contains("is-watch-repeat")).toBe(true);
    // From another chat: its question was still on the live message.
    window.App.setThreadQuestion("Plan my week.");
    window.App.followup.renderStoredTurns([quiet("c", at(1, 10))]);
    window.App.followup.markWatchRun(ask, quiet("d", at(0, 9)));
    window.App.setThreadQuestion(TASK);
    expect(ask.classList.contains("is-watch-repeat")).toBe(true);
    expect(days(document)).toEqual(["Yesterday", "Today"]);
  });

  it("reads the server's times with microseconds and Firestore's parts", () => {
    const { window, document } = boot();
    const ask = document.getElementById("threadAsk");
    document.getElementById("threadAskText").dataset.question = TASK;
    window.App.followup.markWatchRun(ask, quiet("a", "2026-11-05T08:03:00.123456+00:00"));
    const clock = window.App.format.time(new Date("2026-11-05T08:03:00.123Z"));
    expect(ask.querySelector(".thread-watch-run").textContent).toBe(`Scheduled Watch run · ${clock}`);
    window.App.followup.markWatchRun(ask, quiet("b", { seconds: Date.parse("2026-11-04T09:30:00Z") / 1000 }));
    const later = window.App.format.time(new Date("2026-11-04T09:30:00Z"));
    expect(ask.querySelector(".thread-watch-run").textContent).toBe(`Scheduled Watch run · ${later}`);
  });
});
