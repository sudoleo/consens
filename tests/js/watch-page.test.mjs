import { describe, expect, it, vi } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";
import { ENGLISH_QUESTION, GERMAN_SCRIPTS, settleGerman, useGerman } from "./helpers/german.mjs";

/**
 * The Watches page since the redesign of 2026-11-04 (watch-dashboard.js,
 * watch-composer.js): one field that takes a sentence and starts a Watch
 * (the page itself while there is none, a slim field above the list once
 * there are some); what wants the reader first ("Since you last looked":
 * a wide card for one that needs them, cards for findings and goals); the
 * running and paused ones with their pulse ("Watching"); a panel per Watch
 * instead of the "…" menu (its looks, what they found, goal, how often,
 * channels, Open chat, Pause, End); a quiet foot (Notifications, the ended
 * ones, the archive). The pill under an answer opens the same field in a
 * sheet (watch-sheet.js). The page's routing stays as Apple-Audit package J
 * asked for it.
 */
const SHELL = `
  <nav id="viewSwitch" class="view-switch" data-active="chat">
    <button id="viewSwitchConsensus" class="view-switch-btn is-active"><span>Chat</span></button>
    <button id="viewSwitchWatches" class="view-switch-btn"><span>Watches</span></button>
  </nav>
  <div class="container"><div id="bookmarksContainer"></div></div>
  <dialog id="shareModal" class="modal">
    <div class="modal-content share-modal-content">
      <button type="button" class="close close-button" id="closeShareModal" aria-label="Close dialog"></button>
      <h2 id="shareModalTitle"></h2>
      <div id="shareModalBody"></div>
    </div>
  </dialog>
  <main id="watchDashboard" class="watch-page" hidden>
    <div class="watch-page-inner">
      <header class="wd-head">
        <div class="wd-head-copy">
          <h1 id="watchDashTitle">Watches</h1>
          <p id="watchDashStatus" class="wd-status is-empty"></p>
        </div>
        <div id="watchDashLimit" class="wd-capacity" hidden></div>
      </header>
      <div id="watchDashCompose" class="wd-compose" hidden></div>
      <div id="watchDashBody"></div>
    </div>
  </main>`;

const LATER = new Date(Date.now() + 20 * 3600 * 1000).toISOString();
const EARLIER = new Date(Date.now() - 2 * 3600 * 1000).toISOString();
const DAY = 24 * 3600 * 1000;

function watch(extra = {}) {
  return {
    id: "w1", chat_id: "c".repeat(32), turn_id: "", bookmark_id: "agent_b1", task: "Check whether IRONMAN Hamburg 2027 registration is open.",
    goal: "Registration is open", status: "active", interval: "daily", run_time: "08:00", run_weekday: "", timezone: "",
    next_run_at: LATER, created_at: EARLIER, runs: 3, last_run: { at: EARLIER, outcome: "quiet", summary: "" },
    ended: "", unread: false, email_enabled: true, telegram_enabled: true, image: null, looks: [], looking: false, ...extra,
  };
}

function looks(pattern, summaries = {}) {
  const kinds = { q: "quiet", f: "finding", n: "needs_you", x: "failed" };
  return [...pattern].map((char, index) => ({ at: new Date(Date.now() - (pattern.length - index) * DAY).toISOString(),
    outcome: kinds[char], summary: summaries[index] || "" }));
}

function boot({ watches = [], archive = [], user = true, path = "/app/watches", telegram = null, failList = false,
  german = false, limit = 5, intervals = ["daily", "weekly"] } = {}) {
  const server = { watches, archive, telegram: telegram || { configured: true, connected: false }, calls: [] };
  const harness = loadScripts(
    [...(german ? GERMAN_SCRIPTS : []), "static/js/motion.js", "static/js/modal-dialog.js", "static/js/popover.js",
      "static/js/notices.js", "static/js/watch-state.js", "static/js/share-dialog.js", "static/js/watch-fields.js",
      "static/js/watch-composer.js", "static/js/watch-sheet.js", "static/js/watch.js", "static/js/agent-watch.js",
      "static/js/watch-dashboard.js"],
    {
      body: SHELL,
      before(window) {
        if (german) useGerman(window);
        window.history.replaceState(null, "", path);
        window.scrollTo = () => {};
        window.Element.prototype.scrollIntoView = function () {};
        window.App = { watch: {}, showPopup: vi.fn(), trackAppEvent: vi.fn(), openAuthModal: vi.fn() };
        window.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} });
        window.auth = user ? { currentUser: { uid: "watch-user", email: "max@example.com", getIdToken: async () => "token" } }
          : { currentUser: null };
        window.__consensioAuthState = { known: true, uid: user ? "watch-user" : null };
        window.openBookmark = vi.fn();
        window.fetch = vi.fn(async (input, options = {}) => {
          const url = String(input);
          const method = options.method || "GET";
          const body = options.body ? JSON.parse(options.body) : null;
          server.calls.push([method, url, body]);
          let data = {};
          let status = 200;
          const action = url.match(/^\/agent\/watches\/(\w+)\/(\w+)$/);
          const one = url.match(/^\/agent\/watches\/(\w+)$/);
          if (url.startsWith("/agent/watches?") || (url === "/agent/watches" && method === "GET")) {
            if (failList) { status = 503; data = { detail: "Watches are unavailable right now. Try again." }; }
            else data = { watches: server.watches, intervals, active_limit: limit,
              active_count: server.watches.filter(item => item.status === "active").length };
          } else if (url === "/agent/watches" && method === "POST") {
            const created = watch({ id: "new1", task: body.task, goal: body.goal, interval: body.interval,
              run_time: body.run_time, run_weekday: body.run_weekday, chat_id: body.chat_id || "n".repeat(32),
              next_run_at: new Date().toISOString(), runs: 0, last_run: null });
            server.watches.unshift(created);
            status = 201;
            data = { watch: created };
          } else if (action) {
            const target = server.watches.find(item => item.id === action[1]);
            if (action[2] === "pause") Object.assign(target, { status: "paused", next_run_at: null });
            if (action[2] === "resume") Object.assign(target, { status: "active", next_run_at: LATER });
            if (action[2] === "stop") Object.assign(target, { status: "done", ended: "user", next_run_at: null });
            if (action[2] === "seen") Object.assign(target, { unread: false });
            data = { watch: { ...target } };
          } else if (one && method === "PATCH") {
            const target = server.watches.find(item => item.id === one[1]);
            Object.assign(target, body);
            data = { watch: { ...target } };
          } else if (url === "/api/my/watches") {
            data = { watches: server.archive, limits: { plan: "free", active_count: 0, active_limit: 1 }, archived: true };
          } else if (url === "/api/my/telegram") {
            data = { telegram: server.telegram };
          } else if (url === "/api/my/shares") {
            data = { shares: [], site_url: "https://www.consens.io" };
          } else if (method === "POST" && url === "/api/my/telegram/link") {
            data = { url: "https://t.me/consens_bot?start=pair" };
          }
          return { ok: status < 400, status, json: async () => data, headers: { get: () => null } };
        });
      }
    }
  );
  harness.window.App.confirm = vi.fn(async () => true);
  return { ...harness, server };
}

const settle = () => new Promise(resolve => setTimeout(resolve, 0));
const rows = document => [...document.querySelectorAll("#watchDashBody .is-watching .aw-row")].map(row => row.dataset.watchId);
const cards = document => [...document.querySelectorAll(".aw-card")].map(card => card.dataset.watchId);
const titles = document => [...document.querySelectorAll(".aw-section-title")].map(node => node.textContent);
const detail = document => document.querySelector("dialog.wd-detail");
const field = document => document.querySelector("#watchDashBody .wc, #watchDashCompose .wc");
const posted = server => server.calls.find(([method, url]) => method === "POST" && url === "/agent/watches")?.[2];

function type(window, input, text) {
  input.value = text;
  input.dispatchEvent(new window.Event("input", { bubbles: true }));
}

describe("Watch times (watch-fields.js)", () => {
  it("writes one schedule, names a foreign time zone as a place and the own one never", () => {
    const { window } = boot({ user: false, path: "/app" });
    const F = window.App.watchFields;
    const own = { own: "Europe/Berlin" };
    expect(F.scheduleLabel({ interval: "weekly", run_weekday: "tuesday", run_time: "09:00", timezone: "Europe/Berlin" }, own))
      .toBe("Weekly on Tuesday at 09:00");
    expect(F.scheduleLabel({ interval: "monthly", run_time: "07:00", timezone: "America/New_York" }, own))
      .toBe("Monthly at 07:00 (New York time)");
  });
});

describe("The page: what wants the reader first, then what runs", () => {
  it("puts a Watch that needs you and new findings first, the running ones and the paused ones under them", async () => {
    const { window, document, server } = boot({ watches: [
      watch({ id: "run", task: "Running task one.", next_run_at: new Date(Date.now() + 3 * 3600 * 1000).toISOString() }),
      watch({ id: "later", task: "Running task two." }),
      watch({ id: "found", task: "A task that found something.", unread: true,
        last_run: { at: EARLIER, outcome: "finding", summary: "The registration is open." } }),
      watch({ id: "goal", task: "A task that reached its goal.", unread: true, status: "done", ended: "goal", next_run_at: null,
        last_run: { at: EARLIER, outcome: "done", summary: "It is open now." } }),
      watch({ id: "ask", task: "A task that needs the user.", unread: true,
        last_run: { at: EARLIER, outcome: "needs_you", summary: "I need you to log in to the portal." } }),
      watch({ id: "rest", task: "A paused task.", status: "paused", next_run_at: null }),
      watch({ id: "old", task: "An ended task.", status: "done", ended: "user", next_run_at: null }),
    ] });
    await window.App.watchDashboard.render();
    expect(titles(document)).toEqual(["Since you last looked", "Watching"]);
    expect(cards(document)).toEqual(["ask", "found", "goal"]);
    const needs = document.querySelector('.aw-card[data-watch-id="ask"]');
    expect(needs.classList.contains("is-needs")).toBe(true);
    expect(needs.querySelector(".aw-card-text").textContent).toBe("I need you to log in to the portal.");
    expect(needs.querySelector(".aw-card-action").textContent).toBe("Decide");
    expect(needs.getAttribute("aria-label")).toMatch(/^Needs you\. A task that needs the user\./);
    expect(document.querySelector('.aw-card[data-watch-id="goal"] .aw-badge').textContent).toBe("Goal reached");
    expect(document.querySelector('.aw-card[data-watch-id="found"] .aw-badge').textContent).toBe("Found something");
    // Running by their next look, the paused ones last; the ended one waits in the foot.
    expect(rows(document)).toEqual(["run", "later", "rest"]);
    const running = document.querySelector('.aw-row[data-watch-id="run"]');
    expect(running.querySelector(".aw-line").textContent).toBe("Nothing new.");
    expect(running.querySelector(".aw-meta").textContent).toBe("Daily at 08:00");
    const upcoming = window.App.format.upcoming(server.watches[0].next_run_at);
    expect(running.querySelector(".aw-next").textContent).toBe(upcoming.charAt(0).toUpperCase() + upcoming.slice(1));
    expect(document.querySelector('.aw-row[data-watch-id="rest"] .aw-next').textContent).toBe("Paused");
    expect(document.getElementById("watchDashLimit").textContent).toBe("4 of 5 running");
    expect(document.querySelectorAll("#watchDashLimit .wd-meter-step.is-on")).toHaveLength(4);
    expect(document.getElementById("watchDashStatus").textContent).toBe(`Next look ${upcoming}`);
    // One way in: the field above the list, no button of its own.
    expect(document.querySelector("#watchDashCompose .wc.is-inline.is-collapsed")).not.toBeNull();
    expect(document.querySelectorAll("#watchDashboard .wd-button.is-primary")).toHaveLength(0);
    const ended = document.querySelector('.aw-foot-link[data-key="ended"]');
    expect(ended.textContent).toBe("Ended1");
    expect(ended.getAttribute("aria-expanded")).toBe("false");
    ended.click();
    expect(document.querySelector('.aw-drawer.is-ended .aw-row[data-watch-id="old"] .aw-line').textContent).toBe("Ended.");
    expect(document.querySelector('.aw-foot-link[data-key="ended"]').getAttribute("aria-expanded")).toBe("true");
  });

  it("opens a card's chat and counts its finding as seen", async () => {
    const { window, document, server } = boot({ watches: [watch({ unread: true,
      last_run: { at: EARLIER, outcome: "finding", summary: "Open." } })] });
    await window.App.watchDashboard.render();
    document.querySelector(".aw-card").click();
    await settle();
    expect(window.openBookmark).toHaveBeenCalledWith("agent_b1");
    expect(server.calls).toContainEqual(["POST", "/agent/watches/w1/seen", {}]);
    // Seen, it joins the running ones.
    expect(rows(document)).toEqual(["w1"]);
  });

  it("draws the last looks as a pulse with a ring for the next and says it in words", async () => {
    const { window, document } = boot({ watches: [watch({ looks: looks("qqfxqqnqqqqqqqqfqq") }),
      watch({ id: "now", looking: true, looks: looks("qq") })] });
    await window.App.watchDashboard.render();
    const pulse = document.querySelector('.aw-row[data-watch-id="w1"] .aw-pulse');
    const dots = [...pulse.querySelectorAll(".aw-dot")].map(dot => dot.className.replace("aw-dot ", ""));
    // The newest 14, oldest first, then the next one.
    expect(dots).toEqual(["is-quiet", "is-quiet", "is-needs", ...Array(8).fill("is-quiet"), "is-found", "is-quiet", "is-quiet", "is-next"]);
    expect(pulse.querySelector(".aw-dots").getAttribute("aria-hidden")).toBe("true");
    expect(pulse.querySelector(".visually-hidden").textContent).toBe("Found something once in the last 14 looks. Once it needed you.");
    const now = document.querySelector('.aw-row[data-watch-id="now"]');
    expect(now.querySelector(".aw-dot.is-next.is-now")).not.toBeNull();
    expect(now.querySelector(".aw-next").textContent).toBe("Looking now");
    expect(document.getElementById("watchDashStatus").textContent).toBe("Looking now");
  });

  it("says a first look is under way and opens no chat that is not there yet", async () => {
    const { window, document } = boot({ watches: [watch({ last_run: null, runs: 0, next_run_at: new Date().toISOString() })] });
    await window.App.watchDashboard.render();
    expect(document.querySelector(".aw-line").textContent).toBe("Its first look is under way.");
    document.querySelector(".aw-open").click();
    expect(detail(document).open).toBe(true);
    [...detail(document).querySelectorAll(".wd-detail-actions button")].find(button => button.textContent === "Open chat").click();
    expect(window.openBookmark).not.toHaveBeenCalled();
    expect(document.querySelector("#appToasts .toast.is-shown").textContent).toContain("Its chat appears in a moment");
  });

  it("knows a first look under way after its start moved the next run on", async () => {
    vi.useFakeTimers();
    try {
      // claim() sets next_run_at to tomorrow at the start; last_run comes at the end.
      const tomorrow = new Date(Date.now() + 86400000).toISOString();
      const { window, document, server } = boot({ watches: [watch({ last_run: null, runs: 1, looking: true, next_run_at: tomorrow })] });
      await window.App.watchDashboard.render();
      document.getElementById("watchDashboard").hidden = false;
      expect(document.querySelector(".aw-line").textContent).toBe("Its first look is under way.");
      // The page's own start (watch.js) draws it once more at once.
      await vi.advanceTimersByTimeAsync(1000);
      const reads = () => server.calls.filter(([method, url]) => method === "GET" && url === "/agent/watches").length;
      const before = reads();
      await vi.advanceTimersByTimeAsync(15000);
      expect(reads()).toBe(before + 1);
      // Its chat is not in the sidebar before the run has ended.
      document.querySelector(".aw-open").click();
      [...detail(document).querySelectorAll(".wd-detail-actions button")].find(button => button.textContent === "Open chat").click();
      expect(window.openBookmark).not.toHaveBeenCalled();
      expect(document.querySelector("#appToasts .toast.is-shown").textContent).toContain("Its chat appears in a moment");
      server.watches[0] = { ...server.watches[0], looking: false, last_run: { at: new Date().toISOString(), outcome: "quiet", summary: "" } };
      await vi.advanceTimersByTimeAsync(60000);
      await vi.waitFor(() => expect(document.querySelector(".aw-line").textContent).toBe("Nothing new."));
      // Its first look is there: no more looks.
      const after = reads();
      await vi.advanceTimersByTimeAsync(300000);
      expect(reads()).toBe(after);
    } finally {
      vi.useRealTimers();
    }
  });

  it("opens a chat's own Watch during its first look: that chat is there already", async () => {
    const tomorrow = new Date(Date.now() + 86400000).toISOString();
    const { window, document } = boot({ watches: [watch({ turn_id: "t1", last_run: null, runs: 1, looking: true, next_run_at: tomorrow })] });
    await window.App.watchDashboard.render();
    document.querySelector(".aw-open").click();
    [...detail(document).querySelectorAll(".wd-detail-actions button")].find(button => button.textContent === "Open chat").click();
    expect(window.openBookmark).toHaveBeenCalledWith("agent_b1");
  });

  it("looks again until a new Watch's first look is there", async () => {
    vi.useFakeTimers();
    try {
      const { window, document, server } = boot({ watches: [watch({ last_run: null, runs: 0, next_run_at: new Date().toISOString() })] });
      await window.App.watchDashboard.render();
      document.getElementById("watchDashboard").hidden = false;
      const reads = () => server.calls.filter(([method, url]) => method === "GET" && url === "/agent/watches").length;
      const before = reads();
      server.watches[0].last_run = { at: new Date().toISOString(), outcome: "quiet", summary: "" };
      await vi.advanceTimersByTimeAsync(15000);
      expect(reads()).toBe(before + 1);
      await vi.waitFor(() => expect(document.querySelector(".aw-line").textContent).toBe("Nothing new."));
      // Its first look is there: no more looks.
      await vi.advanceTimersByTimeAsync(300000);
      expect(reads()).toBe(before + 1);
    } finally {
      vi.useRealTimers();
    }
  });

  it("says why a Watch that could not run any more has ended", async () => {
    const { window, document } = boot({ watches: [watch({ id: "g", status: "done", ended: "google_data", unread: true,
      last_run: { at: EARLIER, outcome: "google_data", summary: "" } })] });
    await window.App.watchDashboard.render();
    const card = document.querySelector('.aw-card[data-watch-id="g"]');
    expect(card.querySelector(".aw-card-text").textContent)
      .toBe("Its chat now holds Google information, so it no longer runs on a schedule.");
    expect(card.querySelector(".aw-badge").textContent).toBe("Ended");
  });

  it("counts the Agent's Watches in the plan line, not the archived ones", async () => {
    const { window, document } = boot({ watches: [watch(), watch({ id: "w2" })], limit: 2 });
    document.body.insertAdjacentHTML("beforeend", '<span id="watchUsageDisplay">Watches: <strong>…</strong></span>');
    await window.App.watchDashboard.render();
    expect(document.querySelector("#watchUsageDisplay strong").textContent).toBe("2 / 2");
  });

  it("keeps the Consensus Watches from before in the foot, with their pages", async () => {
    const { window, document } = boot({ watches: [watch()], archive: [
      { id: "old1", question: "When does GPT-6 ship?", share_path: "/s/gpt-6", last_run_at: "2026-10-30T08:00:00+00:00" }] });
    await window.App.watchDashboard.render();
    const toggle = document.querySelector('.aw-foot-link[data-key="archive"]');
    expect(toggle.querySelector(".aw-count").textContent).toBe("1");
    toggle.click();
    const link = document.querySelector(".aw-drawer.is-archive .aw-archive-link");
    expect(link.textContent).toBe("When does GPT-6 ship?");
    expect(link.getAttribute("href")).toBe("/s/gpt-6");
    expect(document.querySelector(".aw-archive-when").textContent).toMatch(/^Last checked /);
    // Open stays open across a redraw, and the focus with its toggle.
    await window.App.watchDashboard.render();
    expect(document.querySelector(".aw-drawer.is-archive").hidden).toBe(false);
  });

  it("says where findings go and pairs Telegram from Notifications", async () => {
    const { window, document, server } = boot({ watches: [watch()] });
    await window.App.watchDashboard.render();
    expect(document.querySelector(".aw-foot-note").textContent).toContain("Findings also reach you by email.");
    document.querySelector(".aw-foot-change").click();
    const sheet = document.querySelector("dialog.wd-notify");
    expect(sheet.open).toBe(true);
    const notes = [...sheet.querySelectorAll(".aw-channel-note")].map(node => node.textContent);
    expect(notes[0]).toBe("A Watch writes to max@example.com when a look finds something, needs you, or reaches its goal.");
    expect(notes[1]).toBe("Get what your Watches find as a chat message too.");
    window.open = vi.fn(() => ({ closed: false, location: { href: "" }, close() {} }));
    [...sheet.querySelectorAll(".aw-channel button")].find(button => button.textContent === "Connect Telegram").click();
    await vi.waitFor(() => expect(server.calls.some(([method, url]) => method === "POST" && url === "/api/my/telegram/link")).toBe(true));
  });

  it("keeps the reason and offers another try when the list cannot load", async () => {
    const { window, document } = boot({ failList: true });
    await window.App.watchDashboard.render();
    expect(document.querySelector(".aw-alert p").textContent).toBe("Watches are unavailable right now. Try again.");
    expect(document.querySelector(".aw-alert button").textContent).toBe("Try again");
    expect(document.getElementById("watchDashCompose").hidden).toBe(true);
  });

  it("leaves the task as written on a German page, its own words German", async () => {
    const { window, document } = boot({ german: true, watches: [watch({ task: ENGLISH_QUESTION })] });
    await window.App.watchDashboard.render();
    await settleGerman(window);
    expect(document.querySelector(".aw-title").textContent).toBe(ENGLISH_QUESTION);
    expect(document.querySelector(".aw-line").textContent).toBe("Nichts Neues.");
    expect(titles(document)).toEqual(["Wird beobachtet"]);
    expect(document.querySelector("#watchDashCompose .wc-task").placeholder).toBe("Etwas im Blick behalten…");
  });
});

describe("One Watch's panel (instead of the … menu)", () => {
  it("shows its looks and what they found, pauses, picks the channels and ends it", async () => {
    const { window, document, server } = boot({ telegram: { configured: true, connected: true, telegram_username: "maxl" },
      watches: [watch({ looks: looks("qfqx", { 1: "Two new listings, both over budget." }) })] });
    await window.App.watchDashboard.render();
    document.querySelector('.aw-row[data-watch-id="w1"] .aw-open').click();
    const panel = detail(document);
    expect(panel.open).toBe(true);
    expect(panel.querySelector(".wd-sheet-title").textContent).toBe("Check whether IRONMAN Hamburg 2027 registration is open.");
    expect(panel.querySelector(".wd-detail-status").textContent).toMatch(/^Running · next look (today|tomorrow), /);
    expect(panel.querySelector(".wd-activity-title").textContent).toBe("Last 4 looks");
    expect(panel.querySelector(".wd-activity-count").textContent).toBe("1 finding");
    expect([...panel.querySelectorAll(".wd-find-text")].map(node => node.textContent))
      .toEqual(["A look did not finish. It tried again on schedule.", "Two new listings, both over budget."]);
    expect([...panel.querySelectorAll(".wd-setting-label")].map(node => node.textContent))
      .toEqual(["Done when", "How often", "Email", "Telegram"]);
    const pause = () => [...panel.querySelectorAll(".wd-detail-more button")].find(button => /^(Pause|Resume)$/.test(button.textContent));
    pause().click();
    await vi.waitFor(() => expect(server.calls).toContainEqual(["POST", "/agent/watches/w1/pause", {}]));
    await vi.waitFor(() => expect(pause().textContent).toBe("Resume"));
    expect(document.querySelector('.aw-row[data-watch-id="w1"]').classList.contains("is-paused")).toBe(true);
    const telegram = panel.querySelector('.wd-setting[data-key="telegram"] .wd-switch');
    expect(telegram.getAttribute("aria-checked")).toBe("true");
    telegram.click();
    await vi.waitFor(() => expect(server.calls).toContainEqual(["PATCH", "/agent/watches/w1", { telegram_enabled: false }]));
    await vi.waitFor(() => expect(panel.querySelector('.wd-setting[data-key="telegram"] .wd-switch').getAttribute("aria-checked")).toBe("false"));
    // The switch keeps the focus across the redraw.
    expect(window.document.activeElement).toBe(panel.querySelector('.wd-setting[data-key="telegram"] .wd-switch'));
    [...panel.querySelectorAll(".wd-detail-more button")].find(button => button.textContent === "End Watch").click();
    await vi.waitFor(() => expect(server.calls).toContainEqual(["POST", "/agent/watches/w1/stop", {}]));
    expect(window.App.confirm).toHaveBeenCalledWith(expect.objectContaining({ title: "End this Watch?", danger: true }));
    // Ended, it keeps only Open chat and leaves the list for the foot.
    await vi.waitFor(() => expect(panel.querySelector(".wd-settings")).toBeNull());
    expect(rows(document)).toEqual([]);
  });

  it("changes its goal and how often it runs in place", async () => {
    const { window, document, server } = boot({ watches: [watch({ goal: "" })], intervals: ["every_6_hours", "daily", "weekly"] });
    await window.App.watchDashboard.render();
    document.querySelector(".aw-open").click();
    const panel = detail(document);
    expect(panel.querySelector('.wd-setting[data-key="goal"] .wd-setting-value').textContent).toBe("Runs until you end it");
    panel.querySelector('.wd-setting[data-key="goal"] .wd-pill').click();
    const input = panel.querySelector("#wdGoalInput");
    input.value = "  It is open ";
    panel.querySelector(".wd-edit").dispatchEvent(new window.Event("submit", { cancelable: true }));
    await vi.waitFor(() => expect(server.calls).toContainEqual(["PATCH", "/agent/watches/w1", { goal: "It is open" }]));
    await vi.waitFor(() => expect(panel.querySelector('.wd-setting[data-key="goal"] .wd-setting-value').textContent).toBe("It is open"));
    panel.querySelector('.wd-setting[data-key="schedule"] .wd-pill').click();
    const segments = [...panel.querySelectorAll(".wc-segment")];
    expect(segments.map(segment => segment.getAttribute("aria-disabled"))).toEqual(["true", null, null, null]);
    panel.querySelector('.wc-segment[data-interval="weekly"]').click();
    panel.querySelector('.wc-day[data-weekday="friday"]').click();
    const time = panel.querySelector(".wc-time");
    time.value = "09:30";
    time.dispatchEvent(new window.Event("change"));
    [...panel.querySelectorAll('.wd-setting[data-key="schedule"] button')].find(button => button.textContent === "Save").click();
    await vi.waitFor(() => expect(server.calls.some(([method, url, body]) => method === "PATCH" && url === "/agent/watches/w1"
      && body.interval === "weekly")).toBe(true));
    const [, , body] = server.calls.filter(([method]) => method === "PATCH").at(-1);
    expect(body).toMatchObject({ interval: "weekly", run_time: "09:30", run_weekday: "friday" });
    await vi.waitFor(() => expect(panel.querySelector('.wd-setting[data-key="schedule"] .wd-setting-value').textContent)
      .toBe("Weekly on Friday at 09:30"));
  });

  it("keeps what is typed in its editors when the page draws again, and gives focus back to its row (review 2026-11-04)", async () => {
    const { window, document } = boot({ watches: [watch({ goal: "" })] });
    await window.App.watchDashboard.render();
    document.querySelector(".aw-open").click();
    const panel = detail(document);
    panel.querySelector('.wd-setting[data-key="goal"] .wd-pill').click();
    type(window, panel.querySelector("#wdGoalInput"), "It is open");
    // Back on the tab: the page reads again and draws.
    document.dispatchEvent(new window.Event("visibilitychange"));
    await window.App.watchDashboard.render();
    expect(panel.querySelector("#wdGoalInput").value).toBe("It is open");
    // A switch draws the rows again; closing the panel still lands on the Watch's row.
    panel.querySelector('.wd-setting[data-key="email"] .wd-switch').click();
    await vi.waitFor(() => expect(panel.querySelector('.wd-setting[data-key="email"] .wd-switch').getAttribute("aria-checked")).toBe("false"));
    expect(panel.querySelector("#wdGoalInput").value).toBe("It is open");
    window.App.modalDialog.close(panel);
    expect(document.activeElement).toBe(document.querySelector('.aw-row[data-watch-id="w1"] .aw-open'));
  });

  it("sends one change per switch at a time and edits a weekly Watch on the day it runs", async () => {
    const monday = new Date();
    monday.setDate(monday.getDate() + ((8 - monday.getDay()) % 7 || 7));
    monday.setHours(9, 0, 0, 0);
    const { window, document, server } = boot({ watches: [watch({ interval: "weekly", run_weekday: "", run_time: "09:00",
      next_run_at: monday.toISOString(), timezone: Intl.DateTimeFormat().resolvedOptions().timeZone })] });
    await window.App.watchDashboard.render();
    document.querySelector(".aw-open").click();
    const panel = detail(document);
    const email = panel.querySelector('.wd-setting[data-key="email"] .wd-switch');
    email.click();
    email.click();
    await vi.waitFor(() => expect(server.calls.filter(([method]) => method === "PATCH")).toHaveLength(1));
    panel.querySelector('.wd-setting[data-key="schedule"] .wd-pill').click();
    expect(panel.querySelector('.wc-day[aria-checked="true"]').dataset.weekday).toBe("monday");
  });

  it("keeps a Watch's own time zone when its schedule is saved from elsewhere (review 2026-11-04)", async () => {
    const { window, document, server } = boot({ watches: [watch({ timezone: "Asia/Tokyo" }),
      watch({ id: "w2", timezone: "" })] });
    await window.App.watchDashboard.render();
    const save = async id => {
      document.querySelector(`.aw-row[data-watch-id="${id}"] .aw-open`).click();
      const panel = detail(document);
      panel.querySelector('.wd-setting[data-key="schedule"] .wd-pill').click();
      [...panel.querySelectorAll('.wd-setting[data-key="schedule"] button')].find(button => button.textContent === "Save").click();
      await vi.waitFor(() => expect(server.calls.some(([method, url]) => method === "PATCH" && url === `/agent/watches/${id}`)).toBe(true));
      window.App.modalDialog.close(panel);
      return server.calls.filter(([method, url]) => method === "PATCH" && url === `/agent/watches/${id}`).at(-1)[2];
    };
    expect(await save("w1")).toMatchObject({ interval: "daily", run_time: "08:00", timezone: "Asia/Tokyo" });
    // One without a zone of its own takes the reader's.
    expect((await save("w2")).timezone).toBe(Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC");
  });

  it("gives the focus to the Ended drawer, not the page, once an ended Watch's panel closes (review 2026-11-04)", async () => {
    const { window, document, server } = boot({ watches: [watch(), watch({ id: "w2", task: "Another running task." })] });
    await window.App.watchDashboard.render();
    document.querySelector('.aw-row[data-watch-id="w1"] .aw-open').click();
    const panel = detail(document);
    [...panel.querySelectorAll(".wd-detail-more button")].find(button => button.textContent === "End Watch").click();
    await vi.waitFor(() => expect(server.calls).toContainEqual(["POST", "/agent/watches/w1/stop", {}]));
    await vi.waitFor(() => expect(panel.querySelector(".wd-settings")).toBeNull());
    window.App.modalDialog.close(panel);
    expect(document.activeElement).toBe(document.querySelector('.aw-foot-link[data-key="ended"]'));
    // A Watch gone with its chat while its panel is open: the page's field
    // (no Watch runs any more), never the page itself.
    document.querySelector('.aw-row[data-watch-id="w2"] .aw-open').click();
    server.watches.splice(server.watches.findIndex(item => item.id === "w2"), 1);
    await window.App.watchDashboard.render();
    expect(detail(document).open).toBe(false);
    expect(document.activeElement).toBe(document.querySelector("#watchDashBody .wc-task"));
  });

  it("calls the one look of a Watch from before the looks its last, not its first (review 2026-11-04)", async () => {
    const { window, document } = boot({ watches: [
      watch({ id: "old", runs: 9, looks: [], last_run: { at: EARLIER, outcome: "quiet", summary: "" } }),
      watch({ id: "new", runs: 1, looks: looks("q") }),
      watch({ id: "dup", runs: 4, looks: [], last_run: { at: EARLIER, outcome: "already_ran", summary: "" } }),
    ] });
    await window.App.watchDashboard.render();
    const said = id => document.querySelector(`.aw-row[data-watch-id="${id}"] .aw-pulse .visually-hidden`).textContent;
    expect(said("old")).toBe("Its last look found nothing new.");
    expect(said("new")).toBe("Its first look found nothing new.");
    // A run that had run already is no look, and never a ring that did not finish.
    expect(said("dup")).toBe("No looks yet.");
    expect(document.querySelectorAll('.aw-row[data-watch-id="dup"] .aw-dot:not(.is-next)')).toHaveLength(0);
    document.querySelector('.aw-row[data-watch-id="old"] .aw-open').click();
    expect(detail(document).querySelector(".wd-activity-title").textContent).toBe("Its last look");
    window.App.modalDialog.close(detail(document));
    document.querySelector('.aw-row[data-watch-id="new"] .aw-open').click();
    expect(detail(document).querySelector(".wd-activity-title").textContent).toBe("Its first look");
    window.App.modalDialog.close(detail(document));
    document.querySelector('.aw-row[data-watch-id="dup"] .aw-open').click();
    expect(detail(document).querySelector(".wd-finds")).toBeNull();
    expect(detail(document).querySelector(".wd-activity-empty").textContent).toMatch(/^Next look /);
  });

  it("opens from the pill's Watching for the chat's Watch", async () => {
    const { window, document } = boot({ watches: [watch()] });
    await window.App.watchDashboard.render();
    window.App.watchDashboard.focusWatch("w1");
    expect(detail(document).open).toBe(true);
  });
});

describe("The field that starts a Watch (watch-composer.js)", () => {
  it("is the page while there is no Watch: a question, the field and four ways to begin, no second button", async () => {
    const { window, document } = boot();
    await window.App.watchDashboard.render();
    expect(document.getElementById("watchDashboard").classList.contains("is-empty")).toBe(true);
    expect(document.querySelector(".aw-hero-title").textContent).toBe("What should the Agent keep an eye on?");
    expect(document.querySelectorAll(".wc")).toHaveLength(1);
    expect(document.querySelector(".aw-hero .wc.is-hero")).not.toBeNull();
    expect(document.querySelectorAll("#watchDashboard .wd-button")).toHaveLength(0);
    expect(document.querySelector(".aw-foot-note")).toBeNull();
    const starters = [...document.querySelectorAll(".aw-starter")];
    expect(starters.map(button => button.textContent)).toEqual(["A price drops", "Registration opens", "A new release", "News on a topic"]);
    starters[3].click();
    expect(document.querySelector(".wc-task").value).toBe("Every week, tell me what changed around ");
    expect(document.querySelector(".wc-when").textContent).toMatch(/^Weekly on \w+day at 08:00$/);
    expect(document.activeElement).toBe(document.querySelector(".wc-task"));
  });

  it("starts one in a chat of its own from a sentence, a goal and a weekday", async () => {
    const { window, document, server } = boot({ watches: [watch()] });
    await window.App.watchDashboard.render();
    const form = field(document);
    const task = form.querySelector(".wc-task");
    task.focus();
    expect(form.classList.contains("is-collapsed")).toBe(false);
    type(window, task, "Tell me when the new Garmin 975 is announced.");
    form.querySelector(".wc-goal-add").click();
    type(window, form.querySelector(".wc-goal-input"), "it is announced");
    expect(form.querySelector(".wc-preview").textContent)
      .toBe("Its first look starts right away, in a chat of its own. It ends by itself once its goal is reached.");
    form.querySelector(".wc-when").click();
    expect(form.querySelector(".wc-popover").hidden).toBe(false);
    form.querySelector('.wc-segment[data-interval="weekly"]').click();
    form.querySelector('.wc-day[data-weekday="tuesday"]').click();
    expect(form.querySelector(".wc-when").textContent).toBe("Weekly on Tuesday at 08:00");
    task.dispatchEvent(new window.KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
    await vi.waitFor(() => expect(posted(server)).toBeTruthy());
    expect(posted(server)).toMatchObject({ task: "Tell me when the new Garmin 975 is announced.", goal: "it is announced",
      interval: "weekly", run_time: "08:00", run_weekday: "tuesday" });
    expect(posted(server).chat_id).toBeUndefined();
    await vi.waitFor(() => expect(document.querySelector('.aw-row[data-watch-id="new1"]')).not.toBeNull());
    // The field is empty again; the new Watch has the focus.
    expect(task.value).toBe("");
    expect(document.activeElement).toBe(document.querySelector('.aw-row[data-watch-id="new1"] .aw-open'));
    expect(detail(document)?.open).toBeFalsy();
  });

  it("offers the plan's intervals and says what the others need", async () => {
    const { window, document } = boot({ watches: [watch()] });
    await window.App.watchDashboard.render();
    const form = field(document);
    form.querySelector(".wc-task").focus();
    form.querySelector(".wc-when").click();
    const locked = [...form.querySelectorAll(".wc-segment.is-locked")].map(segment => segment.dataset.interval);
    expect(locked).toEqual(["hourly", "every_6_hours"]);
    expect(form.querySelector(".wc-picker-note").textContent).toBe("Shorter intervals come with Plus and Pro.");
    form.querySelector('.wc-segment[data-interval="hourly"]').click();
    expect(form.querySelector('.wc-segment[aria-checked="true"]').dataset.interval).toBe("daily");
    // The 24-hour clock of the app, never the browser's.
    expect(form.querySelector(".wc-time").value).toBe("08:00");
    expect([...form.querySelector(".wc-time").options].map(option => option.value)).toContain("23:30");
    form.querySelector(".wc-popover").dispatchEvent(new window.KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    expect(form.querySelector(".wc-popover").hidden).toBe(true);
    expect(document.activeElement).toBe(form.querySelector(".wc-when"));
  });

  it("closes How often when the focus leaves it", async () => {
    const { window, document } = boot({ watches: [watch()] });
    await window.App.watchDashboard.render();
    const form = field(document);
    form.querySelector(".wc-task").focus();
    form.querySelector(".wc-when").click();
    expect(form.querySelector(".wc-popover").hidden).toBe(false);
    document.querySelector(".aw-open").focus();
    await settle();
    expect(form.querySelector(".wc-popover").hidden).toBe(true);
  });

  it("asks for a sentence before it sends anything, and says a full plan at once", async () => {
    const { window, document, server } = boot({ watches: [watch(), watch({ id: "w2" })], limit: 2 });
    await window.App.watchDashboard.render();
    const form = field(document);
    form.querySelector(".wc-task").focus();
    await settle();
    expect(form.querySelector(".wc-error").textContent).toBe("All your Watches are in use. End one first.");
    type(window, form.querySelector(".wc-task"), "Short");
    form.dispatchEvent(new window.Event("submit", { cancelable: true }));
    expect(form.querySelector(".wc-error").textContent).toBe("Say in a sentence what the Agent should do.");
    expect(posted(server)).toBeUndefined();
  });

  it("drops the full plan's refusal once a Watch ends and a slot is free (review 2026-11-04)", async () => {
    const { window, document, server } = boot({ watches: [watch(), watch({ id: "w2" }), watch({ id: "w3" })], limit: 3 });
    await window.App.watchDashboard.render();
    const form = field(document);
    const task = form.querySelector(".wc-task");
    const error = form.querySelector(".wc-error");
    // Ended in another tab while the field holds the refusal: it goes at once.
    task.focus();
    await settle();
    expect(error.hidden).toBe(false);
    window.dispatchEvent(new window.CustomEvent("consensio:agent-watches-changed",
      { detail: { watch: { ...server.watches[2], status: "done", ended: "user", next_run_at: null } } }));
    expect(error.hidden).toBe(true);
    // Empty and left, the slim field closes again.
    document.querySelector('.aw-row[data-watch-id="w1"] .aw-open').focus();
    await settle();
    expect(form.classList.contains("is-collapsed")).toBe(true);
    // Full again, with a few words typed (they keep the refusal when the field is left):
    // ending one in its panel takes the refusal away too.
    window.App.watchDashboard.addCreated(watch({ id: "w4" }));
    task.focus();
    await settle();
    type(window, task, "Short");
    expect(error.hidden).toBe(false);
    const open = document.querySelector('.aw-row[data-watch-id="w2"] .aw-open');
    open.focus();
    open.click();
    await settle();
    expect(error.hidden).toBe(false);
    const panel = detail(document);
    [...panel.querySelectorAll(".wd-detail-more button")].find(button => button.textContent === "End Watch").click();
    await vi.waitFor(() => expect(server.calls).toContainEqual(["POST", "/agent/watches/w2/stop", {}]));
    await vi.waitFor(() => expect(error.hidden).toBe(true));
  });

  it("speaks German on a German page and leaves what is typed as it is", async () => {
    const { window, document } = boot({ german: true });
    await window.App.watchDashboard.render();
    await settleGerman(window);
    const form = field(document);
    expect(form.querySelector(".wc-task").placeholder).toBe("Sag mir, sobald die Anmeldung für den IRONMAN Hamburg 2027 öffnet");
    expect(document.querySelector(".aw-hero-title").textContent).toBe("Worauf soll der Agent für dich achten?");
    expect(form.querySelector(".wc-when").textContent).toBe("Täglich um 08:00");
    document.querySelector(".aw-starter").click();
    expect(form.querySelector(".wc-task").value).toBe("Sag mir, wenn der Preis fällt für ");
  });

  it("goes into the sign-in from the empty page of a guest, and back into the field after it (J3)", async () => {
    const { window, document } = boot({ user: false });
    await vi.waitFor(() => expect(document.querySelector(".aw-hero .wc")).not.toBeNull());
    const form = field(document);
    type(window, form.querySelector(".wc-task"), "Is the new iPhone out in Germany?");
    form.dispatchEvent(new window.Event("submit", { cancelable: true }));
    expect(window.App.openAuthModal).toHaveBeenCalledWith("login", expect.anything(), "watch", expect.anything());
    expect(JSON.parse(window.localStorage.getItem("consensio.watchAfterLogin.v1")).question).toBe("Is the new iPhone out in Germany?");
    form.querySelector(".wc-task").value = "";
    window.auth.currentUser = { uid: "new-user", getIdToken: async () => "token" };
    window.dispatchEvent(new window.CustomEvent("consensio:auth-state", { detail: { uid: "new-user" } }));
    await vi.waitFor(() => expect(field(document)?.querySelector(".wc-task").value).toBe("Is the new iPhone out in Germany?"));
    expect(document.querySelector(".watch-sheet")).toBeNull();
    expect(window.localStorage.getItem("consensio.watchAfterLogin.v1")).toBeNull();
  });
});

describe("The pill's sheet (watch-sheet.js)", () => {
  it("starts one in that chat with the same field and stays open while it starts", async () => {
    const { window, document, server } = boot({ path: "/app" });
    window.App.watchSheet.open({ chatId: "a".repeat(32), task: "And what about the price of it?" });
    await settle();
    const sheet = document.querySelector(".watch-sheet");
    expect(sheet.hasAttribute("open")).toBe(true);
    expect(sheet.querySelector(".wc.is-sheet .wc-task").value).toBe("And what about the price of it?");
    expect(sheet.querySelector(".wc-preview").textContent).toBe("It looks again in this chat on this schedule. It runs until you end it.");
    let release;
    const fetch = window.fetch;
    window.fetch = vi.fn((url, options) => (options?.method === "POST"
      ? new Promise(resolve => { release = () => resolve(fetch(url, options)); }) : fetch(url, options)));
    sheet.querySelector(".wc-send").click();
    await settle();
    const cancel = new window.Event("cancel", { cancelable: true });
    sheet.dispatchEvent(cancel);
    expect(cancel.defaultPrevented).toBe(true);
    release();
    await vi.waitFor(() => expect(sheet.hasAttribute("open")).toBe(false));
    expect(posted(server)).toMatchObject({ chat_id: "a".repeat(32), task: "And what about the price of it?" });
  });

  it("reads the account's slots again each time it opens (review 2026-11-04)", async () => {
    const { window, document, server } = boot({ path: "/app", watches: [watch()], limit: 1 });
    const chat = "a".repeat(32);
    window.App.watchSheet.open({ chatId: chat, task: "And what about the price of it?" });
    await vi.waitFor(() => expect(document.querySelector(".watch-sheet .wc-error").textContent)
      .toBe("All your Watches are in use. End one first."));
    window.App.watchSheet.close();
    server.watches[0].status = "done";
    window.App.watchSheet.open({ chatId: chat, task: "And what about the price of it?" });
    await vi.waitFor(() => expect(server.calls.filter(([method, url]) => method === "GET" && url.startsWith("/agent/watches?")).length).toBe(2));
    await settle();
    expect(document.querySelector(".watch-sheet .wc-error").hidden).toBe(true);
  });

  it("never says a full plan from its last opening before the slots are read again (review 2026-11-04)", async () => {
    const { window, document, server } = boot({ path: "/app", watches: [watch()], limit: 1 });
    const chat = "a".repeat(32);
    const outside = document.createElement("button");
    document.body.append(outside);
    window.App.watchSheet.open({ chatId: chat, task: "And what about the price of it?" });
    const error = () => document.querySelector(".watch-sheet .wc-error");
    await vi.waitFor(() => expect(error().hidden).toBe(false));
    window.App.watchSheet.close();
    // In a browser the focus leaves the closed sheet: the next opening focuses the field anew.
    outside.focus();
    server.watches[0].status = "done";
    let release;
    const fetch = window.fetch;
    window.fetch = vi.fn((url, options) => (String(url).startsWith("/agent/watches?")
      ? new Promise(resolve => { release = () => resolve(fetch(url, options)); }) : fetch(url, options)));
    window.App.watchSheet.open({ chatId: chat, task: "And what about the price of it?" });
    await settle();
    expect(document.activeElement).toBe(document.querySelector(".watch-sheet .wc-task"));
    expect(error().hidden).toBe(true);
    release();
    await settle();
    await settle();
    expect(error().hidden).toBe(true);
  });

  it("sends a guest into the sign-in and back to the sheet with the question (J3)", async () => {
    const { window, document } = boot({ user: false, path: "/app" });
    window.App.watchSheet.open({ task: "Is the new iPhone out in Germany?" });
    expect(window.App.openAuthModal).toHaveBeenCalledWith("login", expect.anything(), "watch", expect.anything());
    expect(JSON.parse(window.localStorage.getItem("consensio.watchAfterLogin.v1")).question)
      .toBe("Is the new iPhone out in Germany?");
    window.auth.currentUser = { uid: "new-user", getIdToken: async () => "token" };
    window.dispatchEvent(new window.CustomEvent("consensio:auth-state", { detail: { uid: "new-user" } }));
    await settle();
    expect(document.querySelector(".watch-sheet .wc-task").value).toBe("Is the new iPhone out in Germany?");
    expect(window.localStorage.getItem("consensio.watchAfterLogin.v1")).toBeNull();
  });

  it("says a question waits only when there is one", () => {
    const { window } = boot({ user: false, path: "/app" });
    window.App.watchSheet.open();
    expect(window.App.openAuthModal.mock.calls.at(-1)[3].lead).toBe("Log in to start watching.");
    window.App.watchSheet.open({ task: "Is the new iPhone out in Germany?" });
    expect(window.App.openAuthModal.mock.calls.at(-1)[3].lead).toBe("Log in to start watching. Your question waits for you.");
  });
});

describe("The page beside the chat (J1, J6)", () => {
  it("gives a guest the field and a way to log in instead of an endless skeleton", async () => {
    const { document } = boot({ user: false, path: "/app/watches" });
    await vi.waitFor(() => expect(document.querySelector(".aw-hero-title")).not.toBeNull());
    expect(document.querySelector(".aw-hero .wc")).not.toBeNull();
    expect(document.querySelector(".aw-hero-login").textContent).toBe("Log in");
  });

  it("leaves Watches at once for New chat, so the composer can take the focus", () => {
    const { document } = boot({ watches: [] });
    const button = document.createElement("button");
    button.id = "newRunButton";
    document.querySelector(".container").appendChild(button);
    expect(document.getElementById("watchDashboard").hidden).toBe(false);
    button.click();
    expect(document.getElementById("watchDashboard").hidden).toBe(true);
    expect(document.body.classList.contains("is-watch-view")).toBe(false);
  });

  it("stays on Watches for a chat row's menu and rename field, leaves for the row itself", () => {
    const { document } = boot({ watches: [] });
    document.getElementById("bookmarksContainer").innerHTML =
      '<div class="bookmark" data-id="b1"><p role="button">A chat</p><input class="bookmark-rename-input">'
      + '<button type="button" class="bookmark-menu-button"><svg><path></path></svg></button></div>';
    const page = document.getElementById("watchDashboard");
    document.querySelector(".bookmark-menu-button path").dispatchEvent(new document.defaultView.MouseEvent("click", { bubbles: true }));
    document.querySelector(".bookmark-rename-input").click();
    expect(page.hidden).toBe(false);
    document.querySelector(".bookmark > p").click();
    expect(page.hidden).toBe(true);
  });

  // openBookmark calls it: Enter on a row and a Watch's card open the chat
  // without a click, and it loaded unseen behind Watches (2026-10-23).
  it("leaves Watches for a chat opened without a click", () => {
    const { window, document } = boot({ watches: [] });
    const page = document.getElementById("watchDashboard");
    expect(page.hidden).toBe(false);
    window.App.watch.leave();
    expect(page.hidden).toBe(true);
    expect(document.body.classList.contains("is-watch-view")).toBe(false);
  });

  it("paints the Watches page with its skeleton before anything else loads", () => {
    const { document } = loadScripts(["static/js/app-bootstrap.js"], {
      body: SHELL,
      before(window) {
        window.history.replaceState(null, "", "/app/watches");
        window.App = {};
      }
    });
    expect(document.body.classList.contains("is-watch-view")).toBe(true);
    expect(document.getElementById("watchDashboard").hidden).toBe(false);
    expect(document.querySelector("#watchDashBody .wd-skeleton-field")).not.toBeNull();
    expect(document.querySelectorAll("#watchDashBody .wd-skeleton-card").length).toBe(3);
    expect(document.querySelectorAll("#watchDashBody .wd-skeleton-row").length).toBe(3);
    expect(document.getElementById("viewSwitch").dataset.active).toBe("watches");
  });
});
