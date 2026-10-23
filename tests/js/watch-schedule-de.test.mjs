/**
 * A watch's schedule on a German page (watch-fields.js): whole sentences
 * through App.t with the dictionary the browser really gets, never glued
 * from English pieces ("Weekly on Tuesday at 09:00 · Email · Private"
 * stayed English, the interval "Daily" read as the preset "Alltag").
 */
import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it, vi } from "vitest";

import { loadScripts, ROOT } from "./helpers/appWindow.mjs";

// What /i18n/de.<hash>.js carries: every file but page-* and mail.json
// (app/core/i18n.py, server_only).
function browserDictionary() {
  const folder = path.join(ROOT, "app/i18n/de");
  return Object.assign({}, ...readdirSync(folder)
    .filter(name => name.endsWith(".json") && !name.startsWith("page-") && name !== "mail.json")
    .map(name => JSON.parse(readFileSync(path.join(folder, name), "utf8"))));
}

const DICTIONARY = browserDictionary();
const QUESTION = "When will OpenAI release GPT-6 to the public?";
const PROPOSAL = { question: QUESTION, goals: ["GPT-6 is officially released"], interval: "weekly" };
const WEEKDAYS_DE = ["Sonntag", "Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag"];

async function settle(window) {
  for (let i = 0; i < 30; i += 1) await Promise.resolve();
  window.App.i18n.flush();
}

function boot({ watches = [] } = {}) {
  const harness = loadScripts(
    ["static/js/i18n.js", "static/js/app-text.js", "static/js/watch-state.js", "static/js/watch-fields.js",
      "static/js/watch.js", "static/js/agent-watch.js"],
    {
      body: '<main><div id="agentAnswer"><div id="agentAnswerBody">Die Antwort.</div></div></main>',
      before(window) {
        window.__consensI18n = { lang: "de", entries: DICTIONARY };
        window.auth = { currentUser: { uid: "watch-user", getIdToken: async () => "token" } };
        window.App = { trackAppEvent: vi.fn() };
        window.fetch = async url => ({
          ok: url === "/api/my/watches",
          status: url === "/api/my/watches" ? 200 : 404,
          json: async () => (url === "/api/my/watches"
            ? { watches, limits: { plan: "free", active_count: watches.length, active_limit: 3 } } : {}),
        });
      },
    },
  );
  return { ...harness, F: harness.window.App.watchFields };
}

describe("Watch schedules in German", () => {
  it("writes each shape as one German sentence, the time zone as a place", () => {
    const { F } = boot();
    const own = { own: "Europe/Berlin" };
    expect(F.scheduleLabel({ interval: "weekly", run_weekday: "tuesday", run_time: "09:00", timezone: "Europe/Berlin" }, own))
      .toBe("Jeden Dienstag um 09:00");
    expect(F.scheduleLabel({ interval: "daily", run_time: "08:00" }, own)).toBe("Täglich um 08:00");
    expect(F.scheduleLabel({ interval: "daily" }, own)).toBe("Täglich");
    expect(F.scheduleText({ interval: "monthly", run_time: "07:00", timezone: "America/New_York" }, own))
      .toBe("monatlich um 07:00 (Ortszeit New York)");
    expect(F.scheduleText({ interval: "weekly", run_weekday: "sunday" }, own)).toBe("jeden Sonntag");
    expect(F.checksSentence({ interval: "weekly", run_weekday: "friday", run_time: "08:30", timezone: "Etc/UTC" }, own))
      .toBe("Prüft jeden Freitag um 08:30 (UTC).");
    expect(F.checksSentence({ interval: "weekly", run_time: "08:30" }, { period: false, own: "Europe/Berlin" }))
      .toBe("Prüft wöchentlich um 08:30");
    expect(F.timezoneNote("America/Port_of_Spain", "Europe/Berlin")).toBe("Ortszeit Port of Spain");
    expect(F.timezoneNote("UTC", "Europe/Berlin")).toBe("Zeitzone UTC");
    expect(F.timezoneNote("Europe/Berlin", "Europe/Berlin")).toBe("");
  });

  it("names the interval and the weekdays in the controls, the values stay English", async () => {
    const { window, document, F } = boot();
    const interval = F.intervalSelect("interval", "daily", true);
    const weekday = F.weekdaySelect("weekday", "monday");
    document.querySelector("main").append(interval, weekday);
    await settle(window);
    expect(Array.from(interval.options, item => item.textContent)).toEqual(["Wöchentlich", "Monatlich", "Täglich"]);
    expect(interval.value).toBe("daily");
    expect(Array.from(weekday.options, item => item.textContent).slice(0, 2)).toEqual(["Montag", "Dienstag"]);
    expect(weekday.value).toBe("monday");
  });

  it("writes the Agent card's summary and status as German lines", async () => {
    const { window, document } = boot();
    window.App.agentWatch.render(document.getElementById("agentAnswerBody"), { key: "run-1", proposal: PROPOSAL });
    await settle(window);
    const card = document.querySelector(".agent-watch-card");
    const tomorrow = new window.Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    expect(card.querySelector(".agent-watch-settings").textContent)
      .toBe(`Jeden ${WEEKDAYS_DE[tomorrow.getDay()]} um 09:00 · E-Mail · Privat`);
    window.App.watchUi.receiveWatchList({ watches: [{ id: "w4", status: "active", question: QUESTION,
      interval: "monthly", run_time: "08:00" }], limits: { plan: "free", active_count: 1, active_limit: 3 } });
    await settle(window);
    expect(card.querySelector(".agent-watch-status").textContent).toBe("Prüft monatlich um 08:00.");
  });

  it("keeps the German schedule whole inside the success tip (watch.js renderNudgeSuccess)", async () => {
    const { window, document, F } = boot();
    const schedule = F.scheduleText({ interval: "weekly", run_weekday: "tuesday", run_time: "09:00",
      timezone: "America/Port_of_Spain" }, { own: "Europe/Berlin" });
    const nudge = document.createElement("div");
    nudge.innerHTML = `
      <span class="watch-feature-nudge-label is-active">Watching</span>
      <strong>You are set</strong>
      <span class="watch-feature-nudge-copy">First check: <span data-i18n-skip>${schedule}</span>. We only write when a source moves the answer.</span>`;
    document.querySelector("main").append(nudge);
    await settle(window);
    expect(nudge.textContent.replace(/\s+/g, " ").trim()).toBe("Aktiv Alles bereit Erste Prüfung: "
      + "jeden Dienstag um 09:00 (Ortszeit Port of Spain). Wir melden uns nur, wenn eine Quelle die Antwort ändert.");
  });
});
