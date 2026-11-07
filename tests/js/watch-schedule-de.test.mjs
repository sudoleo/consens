/**
 * A watch's schedule on a German page (watch-fields.js): whole sentences
 * through App.t with the dictionary the browser really gets, never glued
 * from English pieces ("Weekly on Tuesday at 09:00" stayed English, the
 * interval "Daily" read as the preset "Alltag").
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

async function settle(window) {
  for (let i = 0; i < 30; i += 1) await Promise.resolve();
  window.App.i18n.flush();
}

function boot() {
  const harness = loadScripts(
    ["static/js/i18n.js", "static/js/app-text.js", "static/js/watch-fields.js", "static/js/agent-watch.js"],
    {
      body: '<main><div id="agentAnswer"><div id="agentAnswerBody">Die Antwort.</div></div></main>',
      before(window) {
        window.__consensI18n = { lang: "de", entries: DICTIONARY };
        window.auth = { currentUser: { uid: "watch-user", getIdToken: async () => "token" } };
        window.App = { trackAppEvent: vi.fn() };
        window.fetch = async () => ({ ok: false, status: 404, json: async () => ({}) });
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
    expect(F.scheduleLabel({ interval: "monthly", run_time: "07:00", timezone: "America/New_York" }, own))
      .toBe("Monatlich um 07:00 (Ortszeit New York)");
    expect(F.scheduleLabel({ interval: "weekly", run_weekday: "friday", run_time: "08:30", timezone: "Etc/UTC" }, own))
      .toBe("Jeden Freitag um 08:30 (UTC)");
  });

  // The Agent card starts a Watch that runs the Agent
  // (agent-watch.js): its schedule, the line around the goal and its state
  // are German, the task and the goal stay as the model wrote them.
  it("writes the Agent card's schedule and state as German lines", async () => {
    const { window, document } = boot();
    const proposal = { task: "Check whether registration for IRONMAN Hamburg 2027 is open.", goal: "Registration is open",
      interval: "weekly", run_time: "09:00", run_weekday: "tuesday" };
    window.App.agentWatch.render(document.getElementById("agentAnswerBody"), { key: "run-1", proposal, chatId: "c", turnId: "t" });
    await settle(window);
    const card = document.querySelector(".agent-watch-card");
    expect(card.querySelector(".agent-watch-settings").textContent).toMatch(/^Jeden Dienstag um 09:00/);
    expect(card.querySelector(".agent-watch-question").textContent).toBe(proposal.task);
    expect(card.querySelector(".agent-watch-goal").textContent).toBe("Fertig, wenn: Registration is open");
    expect(card.querySelector(".agent-watch-start").textContent).toBe("Watch starten");
    window.App.agentWatch.render(document.getElementById("agentAnswerBody"), { key: "run-2", chatId: "c", turnId: "t",
      proposal: { ...proposal, goal: "", interval: "every_6_hours" } });
    await settle(window);
    expect(document.querySelector(".agent-watch-goal").textContent).toBe("Läuft, bis du sie beendest");
    expect(document.querySelector(".agent-watch-settings").textContent).toBe("Alle 6 Stunden");
  });
});
