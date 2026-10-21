import { describe, expect, it, vi } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

/**
 * The Watches page and the "New watch" dialog as Apple-Audit package J asks
 * for them: one layer closes per Esc, the dialog keeps its top edge and says
 * the truth before any typing, a card changes in place, settings save one
 * way, and every time on the page stays honest.
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
        <button type="button" id="watchDashCreate" class="wd-button is-primary"><span class="wd-button-label">New watch</span></button>
      </header>
      <div id="watchDashBody"></div>
    </div>
  </div>`;

const FUTURE = new Date(Date.now() + 26 * 3600 * 1000).toISOString();

function watch(extra = {}) {
  return {
    id: "w1", status: "active", question: "When does GPT-6 ship?", condition: "GPT-6 is released",
    goal_state: "not_met", interval: "daily", run_weekday: "", run_time: "08:00", timezone: "",
    next_run_at: FUTURE, share_path: "/s/a", share_id: "sh1", visibility: "private",
    email_enabled: true, telegram_enabled: false, email_mode: "changes_only",
    history: [{ ts: "2026-10-01T08:00:00+00:00", signal: "stable", trigger: "stable" }],
    ...extra
  };
}

// jsdom has no showModal()/close(); a browser's dialog fires "close" a task
// after close(), and Escape closes it through its own cancel step.
function nativeDialogs(window) {
  const proto = window.HTMLDialogElement.prototype;
  proto.showModal = function () {
    this.setAttribute("open", "");
    if (this.__escape) return;
    this.__escape = event => { if (event.key === "Escape" && !event.defaultPrevented) this.close(); };
    this.addEventListener("keydown", this.__escape);
  };
  proto.close = function () {
    if (!this.hasAttribute("open")) return;
    this.removeAttribute("open");
    window.setTimeout(() => this.dispatchEvent(new window.Event("close")), 0);
  };
}

function boot({ watches = [], limits = null, user = true, path = "/app/watches", patch = null, captureIntervals = false, dialogs = false } = {}) {
  const server = { watches, limits, calls: [] };
  const harness = loadScripts(
    ["static/js/motion.js", "static/js/modal-dialog.js", "static/js/popover.js", "static/js/notices.js",
      "static/js/watch-state.js", "static/js/share-dialog.js", "static/js/watch-fields.js", "static/js/watch.js", "static/js/watch-dashboard.js"],
    {
      body: SHELL,
      before(window) {
        if (dialogs) nativeDialogs(window);
        window.history.replaceState(null, "", path);
        // jsdom has no scrolling; the page restores the chat's position.
        window.scrollTo = () => {};
        if (captureIntervals) {
          window.__intervals = [];
          window.setInterval = fn => { window.__intervals.push(fn); return window.__intervals.length; };
        }
        window.App = { watch: {}, showPopup: vi.fn(), trackAppEvent: vi.fn(), openAuthModal: vi.fn() };
        window.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} });
        window.auth = user ? { currentUser: { uid: "watch-user", getIdToken: async () => "token" } } : { currentUser: null };
        window.__consensioAuthState = { known: true, uid: user ? "watch-user" : null };
        window.fetch = vi.fn(async (input, options = {}) => {
          const url = String(input);
          const method = options.method || "GET";
          const body = options.body ? JSON.parse(options.body) : null;
          server.calls.push([method, url, body]);
          let data = {};
          let status = 200;
          if (url === "/api/my/watches") {
            data = { watches: server.watches, limits: server.limits || { plan: "pro", active_count: server.watches.filter(w => w.status === "active").length, active_limit: 10, daily_available: true } };
          } else if (url === "/api/watch/goal-suggestions") {
            data = { goals: server.goals || [] };
          } else if (method === "PATCH" && url.startsWith("/api/watch/")) {
            if (patch) ({ status, data } = patch(body) || { status: 200, data: {} });
            else {
              const id = url.split("/").pop();
              const target = server.watches.find(item => item.id === id);
              Object.assign(target, body);
              const { history, ...rest } = target;
              data = { watch: rest };
            }
          } else if (url === "/api/my/telegram") {
            data = { telegram: { configured: false, connected: false } };
          } else if (method === "POST" && url === "/api/watch") {
            const created = watch({ id: "created", question: body.question, condition: body.condition,
              interval: body.interval, run_weekday: body.run_weekday, run_time: body.run_time,
              visibility: body.visibility, history: [], awaiting_first_run: true });
            server.watches.unshift(created);
            data = { watch: created };
          }
          return { ok: status < 400, status, json: async () => data, headers: { get: () => null } };
        });
      }
    }
  );
  return { ...harness, server };
}

const settle = () => new Promise(resolve => setTimeout(resolve, 0));

describe("Watch times (watch-fields.js)", () => {
  it("writes one schedule, names a foreign time zone as a place and the own one never", () => {
    const { window } = boot({ user: false, path: "/app" });
    const F = window.App.watchFields;
    const own = F.browserTimezone();
    expect(F.scheduleLabel({ interval: "weekly", run_weekday: "tuesday", run_time: "09:00", timezone: own }))
      .toBe("Weekly on Tuesday at 09:00");
    expect(F.scheduleText({ interval: "monthly", run_time: "07:00", timezone: "America/New_York" }, { own: "Europe/Berlin" }))
      .toBe("monthly at 07:00 (New York time)");
  });

  it("says a passed time is due, a running check is running, and the clock for later", () => {
    const { window } = boot({ user: false, path: "/app" });
    const F = window.App.watchFields;
    const now = new Date(2026, 9, 20, 14, 0).getTime();
    expect(F.nextCheck({ next_run_at: new Date(now - 12 * 60000).toISOString() }, now).text).toBe("Check due now");
    expect(F.nextCheck({ checking: true, next_run_at: new Date(now - 60000).toISOString() }, now).text).toBe("Checking now…");
    expect(F.nextCheck({ next_run_at: new Date(now + 12 * 60000).toISOString() }, now).text).toBe("Next check in 12m");
    expect(F.nextCheck({ next_run_at: new Date(2026, 9, 21, 9, 0).toISOString() }, now).text).toBe("Next check tomorrow, 09:00");
    expect(F.relativePast(new Date(now - 3 * 3600000).toISOString(), now)).toBe("3h ago");
  });
});

describe("Esc closes one layer (J1)", () => {
  it("closes the dialog and leaves the Watches page with what is typed in it", async () => {
    const { window, document } = boot({ watches: [watch()] });
    await window.App.watchDashboard.render();
    const card = document.querySelector(".wd-item");
    card.querySelector(".wd-action-toggle").click();
    const details = card.querySelector(".wd-goal-input.is-details");
    details.value = "Only from a shop";
    details.focus();
    document.dispatchEvent(new window.KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    expect(document.getElementById("watchDashboard").hidden).toBe(false);
    window.openWatchDialog("create");
    expect(document.getElementById("shareModal").open).toBe(true);
    // The key goes to what has focus, inside the dialog; the dialog keeps it.
    const pageEscape = vi.fn();
    document.addEventListener("keydown", pageEscape);
    document.activeElement.dispatchEvent(new window.KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true }));
    expect(document.getElementById("shareModal").open).toBe(false);
    expect(pageEscape).not.toHaveBeenCalled();
    expect(document.getElementById("watchDashboard").hidden).toBe(false);
    expect(window.location.pathname).toBe("/app/watches");
    expect(details.value).toBe("Only from a shop");
  });
});

describe("New watch dialog", () => {
  it("holds the places of three suggestions with 'Any change' picked, then takes the first suggestion (J2, J16, J27)", async () => {
    const { window, document, server } = boot({ watches: [] });
    let release;
    server.goals = ["The model is released", "A date is announced"];
    const original = window.fetch;
    window.fetch = vi.fn((input, options) => String(input) === "/api/watch/goal-suggestions"
      ? new Promise(resolve => { release = () => resolve(original(input, options)); })
      : original(input, options));
    window.openWatchDialog("create", { question: "When will OpenAI release GPT-6?" });
    expect(document.querySelectorAll("#watchGoalSuggestions .watch-goal-option.is-loading").length).toBe(3);
    expect(document.getElementById("watchGoalNone").checked).toBe(true);
    expect(document.getElementById("watchGoalHint").textContent).toContain("whenever a source changes");
    expect(document.getElementById("watchConfirmBtn").disabled).toBe(false);
    expect(document.activeElement).toBe(document.getElementById("watchGoalNone"));
    await vi.waitFor(() => expect(typeof release).toBe("function"));
    release();
    await vi.waitFor(() => expect(document.querySelectorAll("#watchGoalSuggestions label").length).toBe(2));
    const first = document.querySelector("#watchGoalSuggestions input");
    expect(first.checked).toBe(true);
    expect(document.activeElement).toBe(first);
  });

  it("opens a watched question as the watch it is, not as a form (J17)", async () => {
    const { window, document } = boot({ watches: [watch({ question: "When does GPT-6 ship?" })] });
    await window.App.watchDashboard.render();
    window.openWatchDialog("create", { question: "when does gpt-6 ship" });
    expect(document.getElementById("shareModalTitle").textContent).toBe("Watching");
    expect(document.getElementById("watchConfirmBtn")).toBeNull();
    expect(document.getElementById("watchOpenExisting").textContent).toBe("Open watch");
  });

  it("says all slots are in use before any typing (J25)", async () => {
    const { window, document } = boot({ watches: [watch()], limits: { plan: "free", active_count: 1, active_limit: 1 } });
    await window.App.watchDashboard.render();
    expect(document.getElementById("watchDashCreate").classList.contains("is-primary")).toBe(false);
    window.openWatchDialog("create");
    expect(document.getElementById("watchQuestion")).toBeNull();
    expect(document.getElementById("shareModalBody").textContent).toContain("Your watch slot is in use");
    expect(document.activeElement.id).toBe("watchShowList");
  });

  // Review 2: the step stood on "all in use" after the watch was deleted.
  it("brings the form back once a deletion frees the slot", async () => {
    const { window, document, server } = boot({ watches: [watch()], limits: { plan: "free", active_count: 1, active_limit: 1 } });
    await window.App.watchDashboard.render();
    const lists = () => server.calls.filter(call => call[1] === "/api/my/watches").length;
    const before = lists();
    window.openWatchDialog("create", { question: "Will the EU pass the AI liability rules?" });
    expect(document.getElementById("watchShowList")).not.toBeNull();
    // On opening it asks the server once more: still full.
    await vi.waitFor(() => expect(lists()).toBeGreaterThan(before));
    await settle();
    expect(document.getElementById("watchShowList")).not.toBeNull();
    // The one watch behind the dialog is deleted; while its Undo stands the
    // slot is not free yet.
    const card = document.querySelector('.wd-item[data-watch-id="w1"]');
    card.querySelector(".wd-action-toggle").click();
    card.querySelector('.wd-settings-footer [data-action="delete"]').click();
    await settle();
    expect(document.getElementById("watchShowList")).not.toBeNull();
    server.watches.splice(0);
    server.limits = { plan: "free", active_count: 0, active_limit: 1 };
    window.App.watchDashboard.commitPending();
    await vi.waitFor(() => expect(document.getElementById("watchConfirmBtn")).not.toBeNull());
    expect(document.getElementById("watchShowList")).toBeNull();
    expect(document.querySelector(".watch-question-preview strong").textContent).toBe("Will the EU pass the AI liability rules?");
    expect(document.getElementById("watchConfirmBtn").disabled).toBe(false);
  });

  // Review 2: a dialog closed while its watch started lost the details and
  // the new card; the watch was there all the same.
  it("keeps the details and the new card when the dialog closes while the watch starts", async () => {
    const { window, document, server } = boot({ watches: [watch({ id: "old" })], dialogs: true });
    await window.App.watchDashboard.render();
    const serve = window.fetch;
    let release = null;
    window.fetch = vi.fn((input, options = {}) => {
      if ((options.method || "GET") === "POST" && String(input) === "/api/watch") {
        return new Promise(resolve => { release = () => resolve(serve(input, options)); });
      }
      return serve(input, options);
    });
    window.openWatchDialog("create", { question: "Will the EU pass the AI liability rules?" });
    await settle();
    document.getElementById("watchDetails").value = "Only the final vote counts.";
    document.getElementById("watchConfirmBtn").click();
    await vi.waitFor(() => expect(typeof release).toBe("function"));
    document.getElementById("closeShareModal").click();
    expect(document.getElementById("shareModal").open).toBe(false);
    release();
    await vi.waitFor(() => expect(server.calls.some(([method, url, body]) => method === "PATCH"
      && url === "/api/watch/created" && body?.requirements === "Only the final vote counts.")).toBe(true));
    await vi.waitFor(() => expect(document.querySelector('.wd-item[data-watch-id="created"]')).not.toBeNull());
    expect(document.querySelector('.wd-section[data-section="active"] .wd-item').dataset.watchId).toBe("created");
    expect(document.querySelector("#appToasts .toast.is-shown").textContent).toContain("Watch started");
    expect(document.getElementById("shareModal").open).toBe(false);
  });

  it("sends a guest into the sign-in and back to the dialog with the question (J3)", async () => {
    const { window, document } = boot({ user: false, path: "/app" });
    window.openWatchDialog("create", { question: "Is the new iPhone out in Germany?" });
    expect(window.App.openAuthModal).toHaveBeenCalledWith("login", expect.anything(), "watch", expect.anything());
    expect(document.getElementById("shareModal").open).toBe(false);
    expect(JSON.parse(window.localStorage.getItem("consensio.watchAfterLogin.v1")).question)
      .toBe("Is the new iPhone out in Germany?");
    window.auth.currentUser = { uid: "new-user", getIdToken: async () => "token" };
    window.dispatchEvent(new window.CustomEvent("consensio:auth-state", { detail: { uid: "new-user" } }));
    expect(document.getElementById("shareModal").open).toBe(true);
    expect(document.querySelector(".watch-question-preview strong").textContent).toBe("Is the new iPhone out in Germany?");
    expect(window.localStorage.getItem("consensio.watchAfterLogin.v1")).toBeNull();
  });

  it("gives a guest who opens /app/watches directly the example, not an endless skeleton", async () => {
    const { document } = boot({ user: false, path: "/app/watches" });
    await vi.waitFor(() => expect(document.querySelector(".wd-item.is-example")).not.toBeNull());
    expect(document.getElementById("watchDashCreate").textContent).toBe("Log in to start watching");
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

  it("shows a guest the page with an example instead of a toast", async () => {
    const { window, document } = boot({ user: false, path: "/app" });
    document.getElementById("viewSwitchWatches").click();
    // The page fades through from the chat; it is there after the fade-out.
    await vi.waitFor(() => expect(document.getElementById("watchDashboard").hidden).toBe(false));
    expect(document.querySelector(".wd-item.is-example")).not.toBeNull();
    expect(document.getElementById("watchDashCreate").textContent).toBe("Log in to start watching");
    expect(window.App.showPopup).not.toHaveBeenCalled();
  });
});

describe("Cards change in place (D6, J8, J13, J14)", () => {
  it("rebuilds the schedule line from the answer and keeps the panel open", async () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    try {
      const { window, document, server } = boot({ watches: [watch()] });
      await window.App.watchDashboard.render();
      const card = document.querySelector(".wd-item");
      card.querySelector(".wd-action-toggle").click();
      expect(card.classList.contains("is-open")).toBe(true);
      expect(card.querySelector(".wd-item-side").textContent).toContain("Daily at 08:00");
      const interval = card.querySelector(".wd-settings select");
      interval.value = "weekly";
      interval.dispatchEvent(new window.Event("change", { bubbles: true }));
      await vi.advanceTimersByTimeAsync(400);
      const patch = server.calls.find(call => call[0] === "PATCH");
      expect(patch[2]).toMatchObject({ interval: "weekly" });
      expect(document.querySelector(".wd-item")).toBe(card);
      expect(card.classList.contains("is-open")).toBe(true);
      expect(card.querySelector(".wd-item-side").textContent).toContain("Weekly on");
    } finally {
      vi.useRealTimers();
    }
  });

  it("saves a time once it is finished, not after the first digits (J11)", async () => {
    const { window, document, server } = boot({ watches: [watch()] });
    await window.App.watchDashboard.render();
    const card = document.querySelector(".wd-item");
    card.querySelector(".wd-action-toggle").click();
    const time = card.querySelector('input[type="time"]');
    time.focus();
    time.value = "10:00";
    time.dispatchEvent(new window.Event("input", { bubbles: true }));
    time.dispatchEvent(new window.Event("change", { bubbles: true }));
    await settle();
    expect(server.calls.some(call => call[0] === "PATCH")).toBe(false);
    expect(time.disabled).toBe(false);
    time.dispatchEvent(new window.Event("blur"));
    await vi.waitFor(() => expect(server.calls.some(call => call[0] === "PATCH")).toBe(true));
    expect(server.calls.find(call => call[0] === "PATCH")[2]).toMatchObject({ run_time: "10:00" });
  });

  it("groups the channels without a label around them (J10)", async () => {
    const { window, document } = boot({ watches: [watch()] });
    await window.App.watchDashboard.render();
    const group = document.querySelector(".wd-item .watch-channel-options").closest(".watch-field");
    expect(group.tagName).toBe("DIV");
    expect(group.getAttribute("role")).toBe("group");
    expect(group.querySelector(".watch-field-label").tagName).toBe("SPAN");
  });

  it("pauses in place with Undo and deletes only once Undo has passed (J14, J22)", async () => {
    const { window, document, server } = boot({ watches: [watch(), watch({ id: "w2", question: "Second?" })] });
    await window.App.watchDashboard.render();
    const card = document.querySelector('.wd-item[data-watch-id="w1"]');
    card.querySelector(".wd-action-toggle").click();
    card.querySelector('.wd-settings-footer [data-action="pause"]').click();
    await vi.waitFor(() => expect(card.dataset.state).toBe("paused"));
    expect(card.closest(".wd-section").dataset.section).toBe("active");
    expect(card.classList.contains("is-open")).toBe(true);
    expect(card.querySelector('[data-action="resume"]')).not.toBeNull();
    // The app's one notice line (App.toast): a new line for every step.
    const toast = () => document.querySelector("#appToasts .toast.is-shown");
    expect(toast().textContent).toContain("Watch paused");
    toast().querySelector(".toast-action").click();
    await vi.waitFor(() => expect(card.dataset.state).not.toBe("paused"));

    card.querySelector('.wd-settings-footer [data-action="delete"]').click();
    expect(toast().textContent).toContain("Watch deleted");
    expect(server.calls.some(call => call[0] === "DELETE")).toBe(false);
    toast().querySelector(".toast-action").click();
    expect(server.calls.some(call => call[0] === "DELETE")).toBe(false);
    card.querySelector('.wd-settings-footer [data-action="delete"]').click();
    window.App.watchDashboard.commitPending();
    await vi.waitFor(() => expect(server.calls.some(call => call[0] === "DELETE" && call[1] === "/api/watch/w1")).toBe(true));
  });

  it("lists paused before reached and lets a reached watch be deleted (J21, J22)", async () => {
    const { window, document } = boot({ watches: [
      watch({ id: "r1", status: "resolved", resolution: { at: "2026-10-01T08:00:00+00:00", reason: "Out." } }),
      watch({ id: "p1", status: "paused_error" }),
      watch({ id: "a1" })
    ] });
    await window.App.watchDashboard.render();
    const order = [...document.querySelectorAll(".wd-section:not([hidden])")].map(section => section.dataset.section || "delivery");
    expect(order.slice(0, 3)).toEqual(["active", "paused", "resolved"]);
    const reached = document.querySelector('.wd-item[data-watch-id="r1"]');
    expect(reached.querySelector('.wd-settings-footer [data-action="delete"]')).not.toBeNull();
  });

  it("keeps the list when a refresh fails and offers another try (J6)", async () => {
    const { window, document } = boot({ watches: [watch()] });
    await window.App.watchDashboard.render();
    window.fetch = vi.fn(async () => { throw new Error("Failed to fetch"); });
    await window.App.watchDashboard.render();
    expect(document.querySelector(".wd-item")).not.toBeNull();
    expect(document.querySelector(".wd-alert").textContent).toContain("Try again");
  });

  it("leaves zero counts out of the summary and puts a new watch on top, marked (J15, J29)", async () => {
    const { window, document, server } = boot({ watches: [watch({ id: "old" })] });
    await window.App.watchDashboard.render();
    const summary = document.querySelector(".wd-summary").textContent;
    expect(summary).toContain("watching");
    expect(summary).not.toContain("moved this week");
    expect(summary).not.toMatch(/\b0\b/);
    const created = watch({ id: "new", question: "Brand new?", history: [], awaiting_first_run: true });
    server.watches.unshift(created);
    window.App.watchDashboard.addCreated(created);
    const first = document.querySelector('.wd-section[data-section="active"] .wd-item');
    expect(first.dataset.watchId).toBe("new");
    expect(first.classList.contains("is-highlight")).toBe(true);
  });

  it("re-reads its times every half minute (J5)", async () => {
    {
      const { window, document } = boot({ captureIntervals: true, watches: [watch({ next_run_at: new Date(2026, 9, 20, 9, 2).toISOString() })] });
      let now = new Date(2026, 9, 20, 9, 0).getTime();
      window.Date.now = () => now;
      await window.App.watchDashboard.render();
      const next = document.querySelector(".wd-side-next");
      expect(next.textContent).toBe("Next check in 2m");
      now = new Date(2026, 9, 20, 9, 3).getTime();
      window.__intervals.forEach(fn => fn());
      expect(next.textContent).toBe("Check due now");
    }
  });
});

describe("Watch pill under an Agent answer (J20)", () => {
  it("sits after the answer's evidence row and reads Watching for a watched question", async () => {
    const { window, document } = boot({ watches: [], path: "/app" });
    const answer = document.createElement("div");
    const review = document.createElement("section");
    review.innerHTML = '<nav class="agent-evidence-links"><button>Sources</button></nav>';
    document.body.append(answer, review);
    answer._agentReview = review;
    window.App.watch.answerButton(answer, { question: "When does GPT-6 ship?", eligible: true });
    const pill = review.querySelector("#agentAnswerWatchButton");
    expect(pill).not.toBeNull();
    // Beside the evidence links, never inside their equal-width grid.
    expect(pill.previousElementSibling.classList.contains("agent-evidence-links")).toBe(true);
    expect(pill.textContent).toBe("Watch");
    window.App.watchUi.receiveWatchList({ watches: [watch()], limits: { plan: "pro", active_count: 1, active_limit: 10 } });
    expect(pill.textContent).toBe("Watching");
    window.App.watch.answerButton(answer, { question: "When does GPT-6 ship?", eligible: false });
    expect(review.querySelector("#agentAnswerWatchButton")).toBeNull();
  });
});

describe("First frame of /app/watches (J6)", () => {
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
    expect(document.getElementById("viewSwitchWatches").getAttribute("aria-pressed")).toBe("true");
  });
});

/**
 * After the second review of the Apple audit (finding 8): an Undo that is
 * offered stays true until it passes, a logout does what the Undo let happen
 * before the token goes, the new watch shows however its dialog is closed,
 * "Edit" changes only the question, and a failed save keeps what was typed.
 */
describe("Undo, logout and failed saves (Apple-Audit second review 8)", () => {
  const toast = document => document.querySelector("#appToasts .toast.is-shown");
  const wait = ms => new Promise(resolve => setTimeout(resolve, ms));

  it("lets the logout wait until a watch deleted a moment ago is deleted", async () => {
    const { window, document, server } = boot({ watches: [watch()] });
    await window.App.watchDashboard.render();
    const card = document.querySelector(".wd-item");
    card.querySelector(".wd-action-toggle").click();
    card.querySelector('.wd-settings-footer [data-action="delete"]').click();
    expect(toast(document).textContent).toContain("Watch deleted");
    // The DELETE answers late: the logout must not drop the token before.
    const original = window.fetch;
    let answer;
    window.fetch = vi.fn((input, options = {}) => (options.method === "DELETE"
      ? new Promise(resolve => { answer = () => resolve(original(input, options)); })
      : original(input, options)));
    let sent = false;
    const pending = window.App.watchDashboard.commitPending();
    expect(typeof pending?.then).toBe("function");
    pending.then(() => { sent = true; });
    await vi.waitFor(() => expect(typeof answer).toBe("function"));
    expect(window.fetch.mock.calls.find(call => call[1]?.method === "DELETE")[1].keepalive).toBe(true);
    await wait(5);
    expect(sent).toBe(false);
    answer();
    await vi.waitFor(() => expect(sent).toBe(true));
    expect(server.calls.some(call => call[0] === "DELETE" && call[1] === "/api/watch/w1")).toBe(true);
  });

  it("keeps the deletion's Undo when a pause lands after it", async () => {
    const { window, document, server } = boot({ watches: [watch(), watch({ id: "w2", question: "Second?" })] });
    await window.App.watchDashboard.render();
    const card = document.querySelector('.wd-item[data-watch-id="w1"]');
    card.querySelector(".wd-action-toggle").click();
    const original = window.fetch;
    let land;
    window.fetch = vi.fn((input, options = {}) => (options.method === "PATCH"
      ? new Promise(resolve => { land = () => resolve(original(input, options)); })
      : original(input, options)));
    card.querySelector('.wd-settings-footer [data-action="pause"]').click();
    await vi.waitFor(() => expect(typeof land).toBe("function"));
    card.querySelector('.wd-settings-footer [data-action="delete"]').click();
    expect(toast(document).textContent).toContain("Watch deleted");
    land();
    await vi.waitFor(() => expect(server.calls.some(call => call[0] === "PATCH")).toBe(true));
    await wait(5);
    // Still the deletion's line with its Undo, and nothing deleted yet.
    expect(toast(document).textContent).toContain("Watch deleted");
    expect(server.calls.some(call => call[0] === "DELETE")).toBe(false);
    toast(document).querySelector(".toast-action").click();
    await vi.waitFor(() => expect(card.hidden).toBe(false));
    expect(server.calls.some(call => call[0] === "DELETE")).toBe(false);
  });

  it("brings a card and its section back for good with a quick Undo", async () => {
    const { window, document } = boot({ watches: [watch()] });
    await window.App.watchDashboard.render();
    const card = document.querySelector(".wd-item");
    const section = card.closest(".wd-section");
    card.querySelector(".wd-action-toggle").click();
    // Undo while the card still folds away.
    card.querySelector('.wd-settings-footer [data-action="delete"]').click();
    toast(document).querySelector(".toast-action").click();
    await wait(700);
    expect(card.hidden).toBe(false);
    expect(card.style.height).toBe("");
    // Undo while its section (the card was the last one) folds away.
    card.querySelector('.wd-settings-footer [data-action="delete"]').click();
    await vi.waitFor(() => expect(card.hidden).toBe(true), { timeout: 1500 });
    toast(document).querySelector(".toast-action").click();
    await wait(700);
    expect(card.hidden).toBe(false);
    expect(section.hidden).toBe(false);
  });

  it("shows the new watch on the page when the success step is closed with Esc or the cross", async () => {
    for (const way of ["escape", "cross"]) {
      const { window, document } = boot({ watches: [watch({ id: "old" })], dialogs: true });
      await window.App.watchDashboard.render();
      window.openWatchDialog("create", { question: "Will the EU pass the AI liability rules?" });
      await settle();
      document.getElementById("watchConfirmBtn").click();
      await vi.waitFor(() => expect(document.getElementById("watchDoneBtn")).not.toBeNull());
      if (way === "escape") {
        document.activeElement.dispatchEvent(new window.KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true }));
      } else {
        document.getElementById("closeShareModal").click();
      }
      expect(document.getElementById("shareModal").open).toBe(false);
      await vi.waitFor(() => expect(document.querySelector('.wd-item[data-watch-id="created"]')).not.toBeNull());
      const first = document.querySelector('.wd-section[data-section="active"] .wd-item');
      expect(first.dataset.watchId).toBe("created");
    }
  });

  it("keeps time, alerts, page, details and the open settings when the question is edited", async () => {
    const { window, document } = boot({ watches: [] });
    window.openWatchDialog("create", { question: "Will the EU pass the AI liability rules?" });
    await settle();
    document.querySelector("#watchAdvancedSettings summary").click();
    const set = (id, value) => {
      const node = document.getElementById(id);
      node.value = value;
      node.dispatchEvent(new window.Event(node.tagName === "SELECT" ? "change" : "input", { bubbles: true }));
    };
    set("watchInterval", "monthly");
    set("watchRunTime", "07:30");
    set("watchEmailMode", "every_run");
    set("watchVisibility", "public");
    set("watchDetails", "Only the official journal counts.");
    document.getElementById("watchQuestionEdit").click();
    const input = document.getElementById("watchQuestion");
    expect(input.value).toBe("Will the EU pass the AI liability rules?");
    input.value = "Will the EU pass the AI liability rules in 2027?";
    document.getElementById("watchQuestionNext").click();
    await settle();
    expect(document.querySelector(".watch-question-preview strong").textContent).toBe("Will the EU pass the AI liability rules in 2027?");
    expect(document.getElementById("watchInterval").value).toBe("monthly");
    expect(document.getElementById("watchRunTime").value).toBe("07:30");
    expect(document.getElementById("watchEmailMode").value).toBe("every_run");
    expect(document.getElementById("watchVisibility").value).toBe("public");
    expect(document.getElementById("watchDetails").value).toBe("Only the official journal counts.");
    expect(document.getElementById("watchAdvancedSettings").open).toBe(true);
    expect(document.getElementById("watchSettingsSummary").textContent).toContain("07:30");
  });

  it("keeps a typed goal and a typed time in their fields when saving them fails", async () => {
    const { window, document } = boot({ watches: [watch({ condition: "" })],
      patch: () => ({ status: 500, data: { error: "Something went wrong on our side. Try again." } }) });
    await window.App.watchDashboard.render();
    const card = document.querySelector(".wd-item");
    card.querySelector(".wd-action-toggle").click();
    const goal = card.querySelector(".wd-goal-input.is-goal");
    goal.focus();
    goal.value = "The rules are published in the official journal";
    goal.dispatchEvent(new window.Event("input", { bubbles: true }));
    goal.dispatchEvent(new window.Event("change", { bubbles: true }));
    goal.blur();
    const goalField = goal.closest(".watch-goal");
    await vi.waitFor(() => expect(goalField.querySelector(".watch-field-error").hidden).toBe(false));
    expect(goal.value).toBe("The rules are published in the official journal");
    expect(goalField.querySelector('input[value="custom"]').checked).toBe(true);

    const time = card.querySelector('input[type="time"]');
    time.focus();
    time.value = "10:15";
    time.dispatchEvent(new window.Event("input", { bubbles: true }));
    time.blur();
    const timeField = time.closest(".watch-field");
    await vi.waitFor(() => expect(timeField.querySelector(".watch-field-error").hidden).toBe(false));
    expect(time.value).toBe("10:15");
  });

  it("says a question waits only when there is one", () => {
    const { window } = boot({ user: false, path: "/app" });
    window.openWatchDialog("create");
    expect(window.App.openAuthModal.mock.calls.at(-1)[3].lead).toBe("Log in to start watching.");
    window.openWatchDialog("create", { question: "Is the new iPhone out in Germany?" });
    expect(window.App.openAuthModal.mock.calls.at(-1)[3].lead).toBe("Log in to start watching. Your question waits for you.");
  });
});
