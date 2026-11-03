import { describe, expect, it, vi } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";
import { ENGLISH_QUESTION, GERMAN_SCRIPTS, settleGerman, useGerman } from "./helpers/german.mjs";

/**
 * The Watches page since 2026-11-03 (watch-dashboard.js): the Agent's
 * Watches by what they want from the reader (Needs you, New, Running,
 * Paused, Ended folded away), each a row that opens its chat; "…" pauses,
 * resumes, picks the channels and ends it; the messages (mail, Telegram)
 * and the archived Consensus Watches below. "New Watch" and every other way
 * to start one open the sheet (watch-sheet.js). The page's routing (one
 * page, the chat steps aside, the first frame) stays as Apple-Audit
 * package J asked for it.
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
  <div id="watchDashboard" class="watch-page" hidden>
    <div class="watch-page-inner">
      <header class="wd-head">
        <div id="watchDashLimit" class="watch-limit-summary is-compact" hidden></div>
        <button type="button" id="watchDashCreate" class="wd-button is-primary"><span class="wd-button-label">New Watch</span></button>
      </header>
      <div id="watchDashBody"></div>
    </div>
  </div>`;

const LATER = new Date(Date.now() + 20 * 3600 * 1000).toISOString();
const EARLIER = new Date(Date.now() - 2 * 3600 * 1000).toISOString();

function watch(extra = {}) {
  return {
    id: "w1", chat_id: "c".repeat(32), turn_id: "", bookmark_id: "agent_b1", task: "Check whether IRONMAN Hamburg 2027 registration is open.",
    goal: "Registration is open", status: "active", interval: "daily", run_time: "08:00", run_weekday: "", timezone: "",
    next_run_at: LATER, created_at: EARLIER, runs: 3, last_run: { at: EARLIER, outcome: "quiet", summary: "" },
    ended: "", unread: false, email_enabled: true, telegram_enabled: true, image: null, ...extra,
  };
}

function boot({ watches = [], archive = [], user = true, path = "/app/watches", telegram = null, failList = false,
  german = false, limit = 5 } = {}) {
  const server = { watches, archive, telegram: telegram || { configured: true, connected: false }, calls: [] };
  const harness = loadScripts(
    [...(german ? GERMAN_SCRIPTS : []), "static/js/motion.js", "static/js/modal-dialog.js", "static/js/popover.js",
      "static/js/notices.js", "static/js/watch-state.js", "static/js/share-dialog.js", "static/js/watch-fields.js",
      "static/js/watch.js", "static/js/watch-sheet.js", "static/js/watch-dashboard.js"],
    {
      body: SHELL,
      before(window) {
        if (german) useGerman(window);
        window.history.replaceState(null, "", path);
        window.scrollTo = () => {};
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
            else data = { watches: server.watches, intervals: ["daily", "weekly"], active_limit: limit,
              active_count: server.watches.filter(item => item.status === "active").length };
          } else if (url === "/agent/watches" && method === "POST") {
            const created = watch({ id: "new1", task: body.task, goal: body.goal, interval: body.interval,
              chat_id: body.chat_id || "n".repeat(32), next_run_at: new Date().toISOString(), runs: 0, last_run: null });
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
const rows = document => [...document.querySelectorAll(".aw-row")];
const titles = document => [...document.querySelectorAll(".aw-section-title")].map(node => node.textContent);

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

describe("The Agent's Watches by what they want from the reader", () => {
  it("lists Needs you, New, Running and Paused in that order, the ended ones folded away", async () => {
    const { window, document } = boot({ watches: [
      watch({ id: "run", task: "Running task one." }),
      watch({ id: "found", task: "A task that found something.", unread: true,
        last_run: { at: EARLIER, outcome: "finding", summary: "The registration is open." } }),
      watch({ id: "ask", task: "A task that needs the user.", unread: true,
        last_run: { at: EARLIER, outcome: "needs_you", summary: "I need you to log in to the portal." } }),
      watch({ id: "rest", task: "A paused task.", status: "paused", next_run_at: null }),
      watch({ id: "old", task: "An ended task.", status: "done", ended: "user", next_run_at: null }),
    ] });
    await window.App.watchDashboard.render();
    expect(titles(document)).toEqual(["Needs you", "New", "Running", "Paused", "Messages"]);
    expect(rows(document).map(row => row.dataset.watchId)).toEqual(["ask", "found", "run", "rest"]);
    const needs = document.querySelector('.aw-row[data-watch-id="ask"]');
    expect(needs.querySelector(".aw-line").textContent).toBe("I need you to log in to the portal.");
    expect(needs.querySelector(".aw-dot")).not.toBeNull();
    expect(needs.querySelector(".aw-open").getAttribute("aria-label")).toMatch(/^Needs you\. A task that needs the user\./);
    const running = document.querySelector('.aw-row[data-watch-id="run"]');
    expect(running.querySelector(".aw-line").textContent).toBe("Nothing new.");
    expect(running.querySelector(".aw-meta").textContent).toMatch(/^Daily at 08:00 · next run /);
    expect(document.querySelector('.aw-row[data-watch-id="rest"] .aw-meta').textContent).toBe("Daily at 08:00 · paused");
    expect(document.getElementById("watchDashLimit").textContent).toBe("3 of 5 Watches running");
    const disclosure = document.querySelector(".aw-disclosure");
    expect(disclosure.textContent).toBe("Show ended Watches (1)");
    disclosure.click();
    expect(document.querySelector('.aw-row[data-watch-id="old"] .aw-line').textContent).toBe("Ended.");
  });

  it("opens a row's chat and counts its finding as seen", async () => {
    const { window, document, server } = boot({ watches: [watch({ unread: true,
      last_run: { at: EARLIER, outcome: "finding", summary: "Open." } })] });
    await window.App.watchDashboard.render();
    document.querySelector(".aw-open").click();
    await settle();
    expect(window.openBookmark).toHaveBeenCalledWith("agent_b1");
    expect(server.calls).toContainEqual(["POST", "/agent/watches/w1/seen", {}]);
  });

  it("says a first run is under way instead of opening a chat that is not there yet", async () => {
    const { window, document } = boot({ watches: [watch({ last_run: null, runs: 0, next_run_at: new Date().toISOString() })] });
    await window.App.watchDashboard.render();
    expect(document.querySelector(".aw-line").textContent).toBe("Its first run is under way.");
    document.querySelector(".aw-open").click();
    expect(window.openBookmark).not.toHaveBeenCalled();
    expect(document.querySelector("#appToasts .toast.is-shown").textContent).toContain("Its chat appears in a moment");
  });

  it("pauses, picks the channels and ends a Watch from its menu", async () => {
    const { window, document, server } = boot({ watches: [watch()], telegram: { configured: true, connected: true,
      telegram_username: "maxl" } });
    await window.App.watchDashboard.render();
    const open = () => { document.querySelector(".aw-more").click(); return [...document.querySelectorAll(".aw-menu .bookmark-menu-item")]; };
    expect(open().map(item => item.textContent.replace("✓", ""))).toEqual(["Open chat", "Pause", "Email", "Telegram", "End Watch"]);
    document.querySelector('.aw-menu [data-action="pause"]').click();
    await vi.waitFor(() => expect(titles(document)).toContain("Paused"));
    expect(server.calls).toContainEqual(["POST", "/agent/watches/w1/pause", {}]);
    const items = open();
    expect(items.map(item => item.dataset.action)).toContain("resume");
    const telegram = items.find(item => item.dataset.action === "telegram");
    expect(telegram.getAttribute("aria-checked")).toBe("true");
    telegram.click();
    await vi.waitFor(() => expect(server.calls).toContainEqual(["PATCH", "/agent/watches/w1", { telegram_enabled: false }]));
    open();
    document.querySelector('.aw-menu [data-action="end"]').click();
    await vi.waitFor(() => expect(server.calls).toContainEqual(["POST", "/agent/watches/w1/stop", {}]));
    expect(window.App.confirm).toHaveBeenCalledWith(expect.objectContaining({ title: "End this Watch?", danger: true }));
  });

  it("shows where the messages go and pairs Telegram from the page", async () => {
    const { window, document, server } = boot({ watches: [watch()] });
    await window.App.watchDashboard.render();
    const notes = [...document.querySelectorAll(".aw-channel-note")].map(node => node.textContent);
    expect(notes[0]).toBe("A Watch writes to max@example.com when a run finds something, needs you, or reaches its goal.");
    expect(notes[1]).toBe("Get what your Watches find as a chat message too.");
    window.open = vi.fn(() => ({ closed: false, location: { href: "" }, close() {} }));
    [...document.querySelectorAll(".aw-channel button")].find(button => button.textContent === "Connect Telegram").click();
    await vi.waitFor(() => expect(server.calls.some(([method, url]) => method === "POST" && url === "/api/my/telegram/link")).toBe(true));
  });

  it("keeps the Consensus Watches from before as an archive with their pages", async () => {
    const { window, document } = boot({ watches: [watch()], archive: [
      { id: "old1", question: "When does GPT-6 ship?", share_path: "/s/gpt-6", last_run_at: "2026-10-30T08:00:00+00:00" }] });
    await window.App.watchDashboard.render();
    const archive = document.querySelector(".aw-archive");
    expect(archive.querySelector(".aw-archive-count").textContent).toBe("1");
    const link = archive.querySelector(".aw-archive-link");
    expect(link.textContent).toBe("When does GPT-6 ship?");
    expect(link.getAttribute("href")).toBe("/s/gpt-6");
    expect(archive.querySelector(".aw-archive-when").textContent).toMatch(/^Last checked /);
  });

  it("starts with an empty state whose button opens the sheet", async () => {
    const { window, document } = boot();
    await window.App.watchDashboard.render();
    expect(document.querySelector(".aw-empty-title").textContent).toBe("Nothing watched yet");
    document.querySelector(".aw-empty .wd-button").click();
    await settle();
    expect(document.querySelector(".watch-sheet").hasAttribute("open")).toBe(true);
  });

  it("keeps the reason and offers another try when the list cannot load", async () => {
    const { window, document } = boot({ failList: true });
    await window.App.watchDashboard.render();
    expect(document.querySelector(".aw-alert p").textContent).toBe("Watches are unavailable right now. Try again.");
    expect(document.querySelector(".aw-alert button").textContent).toBe("Try again");
  });

  it("leaves the task as written on a German page, its own words German", async () => {
    const { window, document } = boot({ german: true, watches: [watch({ task: ENGLISH_QUESTION })] });
    await window.App.watchDashboard.render();
    await settleGerman(window);
    expect(document.querySelector(".aw-title").textContent).toBe(ENGLISH_QUESTION);
    expect(document.querySelector(".aw-line").textContent).toBe("Nichts Neues.");
    expect(titles(document)[0]).toBe("Läuft");
  });
});

describe("The sheet that starts a Watch", () => {
  it("opens from New Watch and starts one in a chat of its own", async () => {
    const { window, document, server } = boot({ watches: [watch()] });
    await window.App.watchDashboard.render();
    document.getElementById("watchDashCreate").click();
    await settle();
    const sheet = document.querySelector(".watch-sheet");
    expect(sheet.hasAttribute("open")).toBe(true);
    expect([...sheet.querySelectorAll(".watch-sheet-interval option")].map(option => option.value)).toEqual(["daily", "weekly"]);
    sheet.querySelector(".watch-sheet-task").value = "Tell me when the new Garmin 975 is announced.";
    sheet.querySelector(".watch-sheet-goal").value = "It is announced";
    sheet.querySelector(".watch-sheet-start").click();
    await vi.waitFor(() => expect(server.calls.some(([method, url]) => method === "POST" && url === "/agent/watches")).toBe(true));
    const [, , body] = server.calls.find(([method, url]) => method === "POST" && url === "/agent/watches");
    expect(body).toMatchObject({ task: "Tell me when the new Garmin 975 is announced.", goal: "It is announced",
      interval: "daily", run_time: "08:00" });
    expect(body.chat_id).toBeUndefined();
    await vi.waitFor(() => expect(document.querySelector('.aw-row[data-watch-id="new1"]')).not.toBeNull());
    expect(sheet.hasAttribute("open")).toBe(false);
  });

  it("asks for a sentence before it sends anything", async () => {
    const { window, document, server } = boot();
    await window.App.watchDashboard.render();
    window.App.watchSheet.open();
    await settle();
    document.querySelector(".watch-sheet-start").click();
    expect(document.querySelector(".watch-sheet-error").textContent).toBe("Say in a sentence what the Agent should do.");
    expect(server.calls.some(([method, url]) => method === "POST" && url === "/agent/watches")).toBe(false);
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
    expect(document.querySelector(".watch-sheet .watch-sheet-task").value).toBe("Is the new iPhone out in Germany?");
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
  it("gives a guest a sign-in instead of an endless skeleton", async () => {
    const { document } = boot({ user: false, path: "/app/watches" });
    await vi.waitFor(() => expect(document.querySelector(".aw-empty-title")).not.toBeNull());
    expect(document.querySelector(".aw-empty-title").textContent).toBe("Let the Agent keep an eye on things");
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

  // openBookmark calls it: Enter on a row and a Watch's row open the chat
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
    expect(document.querySelectorAll("#watchDashBody .wd-skeleton-card").length).toBe(3);
    expect(document.getElementById("viewSwitch").dataset.active).toBe("watches");
  });
});
