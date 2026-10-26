import { describe, expect, it, vi } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

/**
 * The dashboard presents the server's verdict (drift_signal, see
 * docs/watch-evidence-model.md) and never re-derives it: a card says "Moved"
 * only for a check the server graded as moved, and a check whose sources
 * merely did not come up again reads "Answer stands", never as a change.
 */
function boot(body = "") {
  const harness = loadScripts(
    ["static/js/motion.js", "static/js/notices.js", "static/js/watch-state.js", "static/js/watch-fields.js", "static/js/watch.js", "static/js/watch-dashboard.js"],
    {
      body,
      before(window) {
        window.fetch = vi.fn(async () => ({ ok: true, json: async () => ({}) }));
        window.auth = { currentUser: { uid: "dashboard-user" } };
        window.App = { watch: {} };
      }
    }
  );
  return harness;
}

function active(point, extra = {}) {
  return {
    status: "active",
    next_run_at: "2026-10-08T07:00:00+00:00",
    history: [{ ts: "2026-09-30T08:00:00+00:00", ...point }],
    ...extra
  };
}

describe("cardState", () => {
  it("reads moved only from the server verdict, with the sources that carry it", () => {
    const { cardState } = boot().window.App.watchDashboard;

    const moved = cardState(active({
      signal: "moved", trigger: "changed",
      change_summary: "GPT-6 was officially released.",
      evidence_sources: [{ title: "Launch", url: "https://openai.com/gpt-6" }]
    }));

    expect(moved.key).toBe("moved");
    expect(moved.headline).toBe("GPT-6 was officially released.");
    // The Judge's sentence is shown as written, never translated.
    expect(moved.quoted).toBe(true);
    expect(moved.sources[0].url).toBe("https://openai.com/gpt-6");
  });

  it("never presents a held answer as a change", () => {
    const { cardState } = boot().window.App.watchDashboard;

    const held = cardState(active({
      signal: "held", trigger: "stable", changed: true, severity: "major",
      change_summary: "The release can no longer be confirmed."
    }));

    expect(held.key).toBe("held");
    expect(held.label).toBe("Answer stands");
    expect(held.headline).not.toContain("no longer be confirmed");
  });

  it("names a pending re-check and a resolved goal", () => {
    const { cardState } = boot().window.App.watchDashboard;

    expect(cardState(active({ signal: "confirming", trigger: "stable" })).key).toBe("rechecking");
    const resolved = cardState({
      status: "resolved",
      resolution: { at: "2026-09-24T08:00:00+00:00", reason: "OpenAI announced it.", sources: [] },
      history: []
    });
    expect(resolved.key).toBe("resolved");
    expect(resolved.headline).toBe("OpenAI announced it.");
  });

  it("falls back to the last move while the answer is steady", () => {
    const { cardState } = boot().window.App.watchDashboard;
    const watch = {
      status: "active",
      history: [
        { ts: "2026-09-09T08:00:00+00:00", signal: "moved", trigger: "changed", change_summary: "Astra announced." },
        { ts: "2026-09-16T08:00:00+00:00", signal: "stable", trigger: "stable" },
        { ts: "2026-09-23T08:00:00+00:00", signal: "restated", trigger: "stable" }
      ]
    };

    const state = cardState(watch);

    expect(state.key).toBe("watching");
    expect(state.lead).toMatch(/^Last moved .+:$/);
    expect(state.headline).toBe("Astra announced.");
  });
});

describe("dashboard render", () => {
  it("groups watches; the goal is news on the card only once it is reported", async () => {
    const harness = boot('<div id="watchDashboard"><div id="watchDashLimit" hidden></div><div id="watchDashBody"></div></div>');
    const { window } = harness;
    window.history.replaceState(null, "", "/app/watches");
    window.auth.currentUser.getIdToken = async () => "token";
    const watches = [
      active({ signal: "moved", trigger: "changed", change_summary: "Released." }, {
        id: "w1", question: "When does GPT-6 ship?", condition: "GPT-6 is released",
        last_condition_status: "not_met", share_path: "/s/a"
      }),
      {
        id: "w2", status: "resolved", question: "Will the EU publish guidance?",
        condition: "Guidance is published",
        resolution: { at: "2026-09-20T08:00:00+00:00", reason: "Published.", sources: [] },
        history: [], share_path: "/s/b"
      },
      active({ signal: "stable", trigger: "stable" }, {
        id: "w3", question: "Adios Pro 4 under 140 euros?", condition: "A shop offers it under 140 EUR",
        goal_state: "confirming", share_path: "/s/c"
      })
    ];
    window.fetch = vi.fn(async (path) => ({
      ok: true,
      json: async () => String(path).includes("/api/my/watches")
        ? { watches: watches, limits: { plan: "free", active_count: 1, active_limit: 3 } }
        : {}
    }));

    await window.App.watchDashboard.render();

    const body = window.document.getElementById("watchDashBody");
    const sections = [...body.querySelectorAll(".wd-section:not([hidden]) .wd-section-head h2")].map(node => node.textContent);
    // A goal that happened is "Reached", one word for it everywhere (J18).
    expect(sections).toEqual(["Watching", "Reached", "Delivery"]);
    // The goal and "not yet" are on the watch's page and in Settings; the
    // card says what happened (Moved, Reached) and a reported goal.
    expect(body.querySelector(".wd-goal")).toBeNull();
    expect(body.querySelector(".wd-item.is-moved .wd-status-goal")).toBeNull();
    expect(body.querySelector(".wd-item.is-resolved .wd-status-label").textContent).toBe("Reached");
    expect(body.querySelector('[data-watch-id="w3"] .wd-status-goal').textContent).toBe("Goal reported, confirming");
    expect(body.textContent).toContain("Why a watch, not a scheduled prompt");
    expect(body.textContent).not.toMatch(/\/100/);
  });

  it("shows the source's picture beside the question, leads to the watch and removes it from the settings", async () => {
    const harness = boot('<div id="watchDashboard"><div id="watchDashLimit" hidden></div><div id="watchDashBody"></div></div>');
    const { window } = harness;
    window.history.replaceState(null, "", "/app/watches");
    window.auth.currentUser.getIdToken = async () => "token";
    const imageUrl = "/api/watch/WatchImage0001/image/" + "a".repeat(20);
    const watches = [
      active({ signal: "stable", trigger: "stable" }, {
        id: "WatchImage0001", question: "Adios Pro 4 in 44.5 under 140 euros?", share_path: "/s/a",
        visibility: "public",
        image: {
          url: imageUrl, width: 320, height: 240,
          source_url: "https://shop.test/p/1", source_host: "shop.test"
        }
      }),
      // Only our own image route is ever rendered.
      active({ signal: "stable", trigger: "stable" }, {
        id: "w2", question: "Is GPT-6 Sol better value?", share_path: "/s/b",
        image: { url: "https://tracker.test/pixel.png", source_url: "https://tracker.test" }
      })
    ];
    const calls = [];
    window.fetch = vi.fn(async (path, options = {}) => {
      calls.push([options.method || "GET", String(path)]);
      return {
        ok: true,
        json: async () => String(path).includes("/api/my/watches")
          ? { watches: watches, limits: { plan: "free", active_count: 2, active_limit: 3 } }
          : {}
      };
    });

    await window.App.watchDashboard.render();

    const body = window.document.getElementById("watchDashBody");
    const figures = body.querySelectorAll(".wd-image:not(.is-symbol)");
    expect(figures.length).toBe(1);
    // The foreign URL is never loaded; that card shows its symbol instead.
    expect(body.querySelectorAll(".wd-image.is-symbol").length).toBe(1);
    expect(body.querySelector('img[src^="https://tracker.test"]')).toBeNull();
    const figure = figures[0];
    const card = figure.closest(".wd-item");
    expect(card.classList.contains("has-image")).toBe(true);
    expect(figure.classList.contains("is-item")).toBe(true);
    expect(card.querySelector(".wd-question a").textContent).toBe("Adios Pro 4 in 44.5 under 140 euros?");
    // How the watch is set up is in Settings, not on the card.
    expect(card.querySelector(".wd-status").textContent).not.toContain("Public");
    expect(card.querySelector(".wd-item-side").textContent).not.toContain("Public");
    const img = figure.querySelector("img");
    expect(img.getAttribute("src")).toBe(imageUrl);
    expect(img.alt).toBe("");
    // The picture leads to the watch's own page, like its question (J23).
    const frame = figure.querySelector("a.wd-image-frame");
    expect(frame.getAttribute("href")).toBe("/s/a");
    expect(frame.getAttribute("aria-hidden")).toBe("true");
    // No standing × on the tile; removing it is a setting with Undo.
    expect(figure.querySelector(".wd-image-remove")).toBeNull();
    card.querySelector('[data-action="remove-picture"]').click();
    expect(card.querySelector(".wd-image.is-item")).toBeNull();
    expect(calls.some(call => call[0] === "DELETE")).toBe(false);
    expect(window.document.querySelector("#appToasts .toast").textContent).toContain("Picture removed");
    window.App.watchDashboard.commitPending();
    await vi.waitFor(() => expect(calls).toContainEqual(["DELETE", "/api/watch/WatchImage0001/image"]));
    // The removed picture gives way to the watch's symbol.
    expect(card.querySelector(".wd-image.is-symbol svg")).not.toBeNull();
    expect(card.classList.contains("has-image")).toBe(true);
  });

  it("keeps a card to status, question, one sentence and the next check", async () => {
    const harness = boot('<div id="watchDashboard"><div id="watchDashLimit" hidden></div><div id="watchDashBody"></div></div>');
    const { window } = harness;
    window.history.replaceState(null, "", "/app/watches");
    window.auth.currentUser.getIdToken = async () => "token";
    const two = [
      { ts: "2026-10-10T07:00:00+00:00", signal: "stable", trigger: "stable" },
      { ts: "2026-10-11T07:00:00+00:00", signal: "stable", trigger: "stable" }
    ];
    const watches = [
      active({ signal: "stable", trigger: "stable" }, {
        id: "w1", question: "Promotionsstelle an der Hochschule Hannover?", share_path: "/s/a",
        condition: "Eine Stelle wird ausgeschrieben", goal_state: "unclear", history: two,
        visibility: "public", telegram_enabled: true,
        last_probe: { at: "2026-10-11T09:00:00+00:00", outcome: "nothing_new" }
      }),
      active({ signal: "stable", trigger: "stable" }, {
        id: "w2", question: "Cursor or Claude Code?", share_path: "/s/b",
        condition: "Cursor drops its price", goal_state: "pending",
        history: [...two, { ts: "2026-10-12T07:00:00+00:00", signal: "stable", trigger: "stable" }],
        last_probe: { at: "2026-10-12T09:00:00+00:00", outcome: "new_evidence" }
      })
    ];
    window.fetch = vi.fn(async (path) => ({
      ok: true,
      json: async () => String(path).includes("/api/my/watches")
        ? { watches: watches, limits: { plan: "free", active_count: 2, active_limit: 3 } }
        : {}
    }));

    await window.App.watchDashboard.render();

    const card = text => [...window.document.querySelectorAll(".wd-item")]
      .find(node => node.querySelector(".wd-question a").textContent.startsWith(text));
    const job = card("Promotionsstelle");
    expect(job.querySelector(".wd-status-time").textContent).toMatch(/^checked /);
    expect(job.querySelector(".wd-headline").textContent).toBe("The answer has held through 2 checks.");
    // "Not yet", the record and "Open page" are on the watch's page; the
    // question is the card's one link to it.
    expect(job.querySelector(".wd-goal, .wd-record, [data-action='open']")).toBeNull();
    expect(job.querySelector(".wd-question a").getAttribute("href")).toBe("/s/a");
    expect(card("Cursor").querySelector(".wd-record")).toBeNull();
    // The footer: when it looks next (a time in the past is due, never
    // "12 min ago", J5) and news from the daily scan; no setup, no "nothing new".
    const side = job.querySelector(".wd-item-side");
    expect(side.textContent).toBe("Check due now");
    const cursor = card("Cursor").querySelector(".wd-item-side");
    expect(cursor.textContent).toMatch(/^Check due now · Daily scan found news /);
    // A no-break space ties each dot to the part before it.
    expect([...cursor.querySelectorAll(".wd-sep")].every(dot => dot.previousSibling.textContent === " ")).toBe(true);
  });

  it("leads straight to the pages: direct links, or the evidence of a move", async () => {
    const harness = boot('<div id="watchDashboard"><div id="watchDashLimit" hidden></div><div id="watchDashBody"></div></div>');
    const { window } = harness;
    window.history.replaceState(null, "", "/app/watches");
    window.auth.currentUser.getIdToken = async () => "token";
    const watches = [
      active({ signal: "stable", trigger: "stable" }, {
        id: "w1", question: "Adios Pro 4 unter 140 €?", share_path: "/s/a",
        key_links: [
          { url: "https://www.idealo.de/preisvergleich/OffersOfProduct/1", title: "Adios Pro 4", domain: "idealo.de" },
          { url: "https://www.idealo.de/preisvergleich/OffersOfProduct/2", title: "Adios Pro 4 (Herren)", domain: "idealo.de" },
          { url: "javascript:alert(1)", title: "bad", domain: "x.de" },
          { url: "https://geizhals.de/a", title: "adidas Adizero", domain: "geizhals.de" }
        ]
      }),
      active({
        signal: "moved", trigger: "changed", change_summary: "Price dropped.",
        evidence_sources: [{ title: "Price history", url: "https://geizhals.de/p" }]
      }, {
        id: "w2", question: "GPU prices?", share_path: "/s/b",
        key_links: [{ url: "https://www.idealo.de/x", title: "Other", domain: "idealo.de" }]
      })
    ];
    window.fetch = vi.fn(async (path) => ({
      ok: true,
      json: async () => String(path).includes("/api/my/watches")
        ? { watches: watches, limits: { plan: "free", active_count: 2, active_limit: 3 } }
        : {}
    }));

    await window.App.watchDashboard.render();

    const card = text => [...window.document.querySelectorAll(".wd-item")]
      .find(node => node.querySelector(".wd-question a").textContent.startsWith(text));
    // One chip per site, favicon and site; the page's title is the tooltip.
    const links = card("Adios").querySelectorAll(".wd-sources a");
    expect([...links].map(link => link.textContent)).toEqual(["idealo.de", "geizhals.de"]);
    expect(links[0].href).toBe("https://www.idealo.de/preisvergleich/OffersOfProduct/1");
    expect(links[0].rel).toContain("noreferrer");
    expect(links[0].title).toBe("Adios Pro 4 · idealo.de");
    expect(links[0].querySelector(".wd-source-icon").getAttribute("src")).toBe("/api/topics/favicon?d=idealo.de");
    // A move shows what moved it, not the standing direct links.
    const moved = card("GPU");
    expect([...moved.querySelectorAll(".wd-sources a")].map(link => link.href)).toEqual(["https://geizhals.de/p"]);
    // The Judge's sentence stays in the language it was written in.
    expect(moved.querySelector(".wd-headline [data-i18n-skip]").textContent).toBe("Price dropped.");
  });

  it("shows logos without a frame and otherwise the watch's symbol", async () => {
    const harness = boot('<div id="watchDashboard"><div id="watchDashLimit" hidden></div><div id="watchDashBody"></div></div>');
    const { window } = harness;
    window.history.replaceState(null, "", "/app/watches");
    window.auth.currentUser.getIdToken = async () => "token";
    const watches = [
      active({ signal: "stable", trigger: "stable" }, {
        id: "WatchLogo0003", question: "Is Cursor or Claude Code better value?", share_path: "/s/d",
        symbol: "code",
        image: { url: "/api/watch/WatchLogo0003/image/" + "d".repeat(20), kind: "logo",
                 width: 304, height: 144, source_url: "https://cursor.com/", source_host: "cursor.com, claude.com" }
      }),
      active({ signal: "stable", trigger: "stable" }, {
        id: "w4", question: "Stelle an der Hochschule Hannover?", share_path: "/s/e", symbol: "briefcase"
      }),
      active({ signal: "stable", trigger: "stable" }, {
        id: "w5", question: "How to make money?", share_path: "/s/f", symbol: "<img src=x onerror=alert(1)>"
      })
    ];
    window.fetch = vi.fn(async (path) => ({
      ok: true,
      json: async () => String(path).includes("/api/my/watches")
        ? { watches: watches, limits: { plan: "free", active_count: 3, active_limit: 3 } }
        : {}
    }));

    await window.App.watchDashboard.render();

    const byQuestion = text => [...window.document.querySelectorAll(".wd-item")]
      .find(card => card.querySelector(".wd-question a").textContent.startsWith(text));
    const cards = [byQuestion("Is Cursor"), byQuestion("Stelle"), byQuestion("How to")];
    const logo = cards[0].querySelector(".wd-image");
    expect(logo.classList.contains("is-logo")).toBe(true);
    expect(logo.querySelector(".wd-image-frame").title).toBe("Logo: cursor.com, claude.com");
    expect(cards[0].querySelector('[data-action="remove-picture"]').textContent).toBe("Remove logo");
    const job = cards[1].querySelector(".wd-image.is-symbol");
    expect(job.getAttribute("aria-hidden")).toBe("true");
    expect(job.querySelector("svg rect")).not.toBeNull();
    // An unknown name falls back to the default drawing, never to markup.
    const other = cards[2].querySelector(".wd-image.is-symbol");
    expect(other.querySelector("img")).toBeNull();
    expect(other.querySelector("svg circle")).not.toBeNull();
  });

  it("lets an article photo fill its tile and keeps a pending card's time in the footer only", async () => {
    const harness = boot('<div id="watchDashboard"><div id="watchDashLimit" hidden></div><div id="watchDashBody"></div></div>');
    const { window } = harness;
    window.history.replaceState(null, "", "/app/watches");
    window.auth.currentUser.getIdToken = async () => "token";
    const watches = [{
      id: "WatchTopic0002", status: "active", awaiting_first_run: true, history: [],
      next_run_at: "2026-10-12T07:00:00+00:00", question: "Has the EU AI Act guidance changed?",
      share_path: "/s/c", visibility: "private", telegram_enabled: true,
      image: { url: "/api/watch/WatchTopic0002/image/" + "c".repeat(20), kind: "article",
               width: 320, height: 206, source_url: "https://news.test/eu", source_host: "news.test" }
    }];
    window.fetch = vi.fn(async (path) => ({
      ok: true,
      json: async () => String(path).includes("/api/my/watches")
        ? { watches: watches, limits: { plan: "free", active_count: 1, active_limit: 3 } }
        : {}
    }));

    await window.App.watchDashboard.render();

    const card = window.document.querySelector(".wd-item");
    expect(card.querySelector(".wd-image").classList.contains("is-article")).toBe(true);
    expect(card.querySelector(".wd-status time")).toBeNull();
    expect(card.querySelector(".wd-item-side .wd-side-value")).not.toBeNull();
    expect(card.querySelector(".wd-item-side").textContent).not.toContain("Telegram");
  });
});

describe("the explainer at the end of the page", () => {
  const KEY = "consensio.watchExplainer.open.v2";

  async function rendered(window) {
    window.history.replaceState(null, "", "/app/watches");
    window.auth.currentUser.getIdToken = async () => "token";
    window.fetch = vi.fn(async (path) => ({
      ok: true,
      json: async () => String(path).includes("/api/my/watches")
        ? { watches: [], limits: { plan: "free", active_count: 0, active_limit: 1 } }
        : {}
    }));
    await window.App.watchDashboard.render();
    return window.document.querySelector(".wd-explainer");
  }
  // A details element announces every change of `open` a task later.
  const toggled = () => new Promise(resolve => setTimeout(resolve, 0));
  const page = '<div id="watchDashboard"><div id="watchDashLimit" hidden></div><div id="watchDashBody"></div></div>';

  it("starts closed, also for readers whose old key stored the page's own default", async () => {
    const { window } = boot(page);
    window.localStorage.setItem("consensio.watchExplainer.open.v1", "true");

    const box = await rendered(window);
    await toggled();

    expect(box.open).toBe(false);
    expect(window.localStorage.getItem(KEY)).toBeNull();
  });

  it("keeps only what the reader chose, never what the page set", async () => {
    const { window } = boot(page);
    window.localStorage.setItem(KEY, "true");
    const box = await rendered(window);
    expect(box.open).toBe(true);
    // The page's own `open = true` fires a toggle too: it is not a choice.
    window.localStorage.removeItem(KEY);
    await toggled();
    expect(window.localStorage.getItem(KEY)).toBeNull();

    box.querySelector("summary").click();
    await toggled();
    expect(box.open).toBe(false);
    expect(window.localStorage.getItem(KEY)).toBe("false");
    box.querySelector("summary").click();
    await toggled();
    expect(window.localStorage.getItem(KEY)).toBe("true");
  });
});

describe("details and wrong matches", () => {
  function dashboard(watches) {
    const harness = boot('<div id="watchDashboard"><div id="watchDashLimit" hidden></div><div id="watchDashBody"></div></div>');
    const { window } = harness;
    window.history.replaceState(null, "", "/app/watches");
    window.auth.currentUser.getIdToken = async () => "token";
    const calls = [];
    window.fetch = vi.fn(async (path, options = {}) => {
      calls.push([options.method || "GET", String(path), options.body ? JSON.parse(options.body) : null]);
      return {
        ok: true,
        json: async () => String(path).includes("/api/my/watches")
          ? { watches: watches, limits: { plan: "pro", active_count: 0, active_limit: 10 } }
          : { watch: watches[0] }
      };
    });
    return { window, calls };
  }

  it("keeps the details in the settings and saves them from there", async () => {
    const { window, calls } = dashboard([active({ signal: "stable", trigger: "stable" }, {
      id: "w1", question: "Adios Pro 4 in 44.5 under 140 euros?", share_path: "/s/a",
      condition: "A new pair is offered for under 140 EUR", goal_state: "pending",
      requirements: "Only new, from a shop.",
      rejected_sources: [{ url: "https://www.kleinanzeigen.de/s-adios/k0", title: "" }]
    })]);
    await window.App.watchDashboard.render();
    const card = window.document.querySelector(".wd-item");

    expect(card.querySelector(".wd-item-main").textContent).not.toContain("Only new");
    const input = card.querySelector(".wd-goal-input.is-details");
    expect(input.value).toBe("Only new, from a shop.");
    expect(card.querySelector(".wd-settings").textContent).toContain("Ruled out: kleinanzeigen.de.");
    // Saved when the field is left, like every text in the settings (J9).
    input.value = "Only new, from a shop. No private sellers.";
    input.dispatchEvent(new window.Event("input", { bubbles: true }));
    input.dispatchEvent(new window.Event("change", { bubbles: true }));

    await vi.waitFor(() => expect(calls.some(call => call[0] === "PATCH")).toBe(true));
    const patch = calls.find(call => call[0] === "PATCH");
    expect(patch[1]).toBe("/api/watch/w1");
    expect(patch[2]).toMatchObject({ requirements: "Only new, from a shop. No private sellers." });
  });

  it("reopens a wrong match with the same goal and what was wrong", async () => {
    const { window, calls } = dashboard([{
      id: "w1", status: "resolved", question: "Adios Pro 4 in 44.5 under 140 euros?", share_path: "/s/a",
      condition: "A new pair is offered for under 140 EUR", goal_state: "reached",
      resolution: {
        at: "2026-10-13T07:30:00+00:00", reason: "A new pair is listed on Kleinanzeigen.",
        sources: [{ url: "https://www.kleinanzeigen.de/s-adios/k0", title: "Kleinanzeigen" }]
      },
      history: []
    }]);
    await window.App.watchDashboard.render();
    const card = window.document.querySelector(".wd-item");

    const reject = card.querySelector(".wd-reject");
    const goalBox = card.querySelector(".wd-goal-input.is-goal").closest(".wd-goal-editor");
    // Settings on a resolved card lead to the next goal, as before.
    card.querySelector(".wd-action-toggle").click();
    expect(reject.hidden).toBe(true);
    expect(goalBox.hidden).toBe(false);
    card.querySelector(".wd-action-toggle").click();

    const wrong = [...card.querySelectorAll(".wd-action")].find(button => button.textContent === "Not what I wanted");
    wrong.click();
    const input = card.querySelector(".wd-goal-input.is-reject");
    expect(card.classList.contains("is-open")).toBe(true);
    expect(card.querySelector(".wd-settings").hasAttribute("inert")).toBe(false);
    // One way on at a time: no second "Keep watching" for a new goal.
    expect(reject.hidden).toBe(false);
    expect(goalBox.hidden).toBe(true);
    expect(window.document.activeElement).toBe(input);
    // The goal itself is not up for editing here; only what was wrong.
    expect(input.value).toBe("");
    input.value = "No private sellers, only shops.";
    [...card.querySelectorAll(".wd-button")].find(button => button.textContent === "Keep watching").click();

    await vi.waitFor(() => expect(calls.some(call => call[0] === "PATCH")).toBe(true));
    const patch = calls.find(call => call[0] === "PATCH");
    expect(patch[2]).toMatchObject({
      status: "active", reject_match: true, requirements: "No private sellers, only shops."
    });
    expect(patch[2]).not.toHaveProperty("condition");
  });

  it("keeps the details already set when a wrong match is ruled out", async () => {
    const reached = extra => ({
      id: "w1", status: "resolved", question: "Adios Pro 4 in 44.5 under 140 euros?", share_path: "/s/a",
      condition: "A new pair is offered for under 140 EUR", goal_state: "reached",
      requirements: "Size 44.5, only new",
      resolution: {
        at: "2026-10-13T07:30:00+00:00", reason: "A new pair is listed on Kleinanzeigen.",
        sources: [{ url: "https://www.kleinanzeigen.de/s-adios/k0", title: "Kleinanzeigen" }]
      },
      history: [],
      ...extra
    });
    async function rejectWith(text) {
      const { window, calls } = dashboard([reached()]);
      await window.App.watchDashboard.render();
      const card = window.document.querySelector(".wd-item");
      [...card.querySelectorAll(".wd-action")].find(button => button.textContent === "Not what I wanted").click();
      card.querySelector(".wd-goal-input.is-reject").value = text;
      [...card.querySelectorAll(".wd-button")].find(button => button.textContent === "Keep watching").click();
      await vi.waitFor(() => expect(calls.some(call => call[0] === "PATCH")).toBe(true));
      return calls.find(call => call[0] === "PATCH")[2];
    }

    // Nothing typed: the details stay as they are (2026-10-26 they were wiped).
    const silent = await rejectWith("  ");
    expect(silent).toMatchObject({ status: "active", reject_match: true });
    expect(silent).not.toHaveProperty("requirements");
    // What was wrong adds to the details instead of replacing them.
    const said = await rejectWith("No private sellers.");
    expect(said.requirements).toBe("Size 44.5, only new. No private sellers.");
  });
});
