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
    ["static/js/watch-state.js", "static/js/watch.js", "static/js/watch-dashboard.js"],
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
    expect(state.headline).toContain("Astra announced.");
  });
});

describe("dashboard render", () => {
  it("groups watches and shows the goal with its status", async () => {
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
      }
    ];
    window.fetch = vi.fn(async (path) => ({
      ok: true,
      json: async () => String(path).includes("/api/my/watches")
        ? { watches: watches, limits: { plan: "free", active_count: 1, active_limit: 3 } }
        : {}
    }));

    await window.App.watchDashboard.render();

    const body = window.document.getElementById("watchDashBody");
    const sections = [...body.querySelectorAll(".wd-section-head h2")].map(node => node.textContent);
    expect(sections).toEqual(["Watching", "Resolved", "Delivery"]);
    expect(body.querySelector(".wd-item.is-moved .wd-goal-text").textContent).toBe("GPT-6 is released");
    expect(body.querySelector(".wd-item.is-resolved .wd-goal-status").textContent).toBe("Reached");
    expect(body.textContent).toContain("Why a Watch, not a scheduled prompt");
    expect(body.textContent).not.toMatch(/\/100/);
  });

  it("shows the source's picture beside the question and removes it for good", async () => {
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
    // Setup details moved from the status line into the schedule footer.
    expect(card.querySelector(".wd-status").textContent).not.toContain("Public");
    expect(card.querySelector(".wd-side-meta").textContent).toBe("Public page");
    const img = figure.querySelector("img");
    expect(img.getAttribute("src")).toBe(imageUrl);
    expect(img.alt).toBe("");
    const frame = figure.querySelector("a.wd-image-frame");
    expect(frame.href).toBe("https://shop.test/p/1");
    expect(frame.rel).toContain("noreferrer");
    expect(frame.getAttribute("aria-label")).toBe("Image from shop.test");

    figure.querySelector(".wd-image-remove").click();
    await vi.waitFor(() => expect(card.querySelector(".wd-image.is-item")).toBeNull());
    expect(calls).toContainEqual(["DELETE", "/api/watch/WatchImage0001/image"]);
    // The removed picture gives way to the watch's symbol.
    expect(card.querySelector(".wd-image.is-symbol svg")).not.toBeNull();
    expect(card.classList.contains("has-image")).toBe(true);
  });

  it("says where the goal stands, keeps one label voice and shows the record from three checks", async () => {
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
        visibility: "public", telegram_enabled: true
      }),
      active({ signal: "stable", trigger: "stable" }, {
        id: "w2", question: "Cursor or Claude Code?", share_path: "/s/b",
        condition: "Cursor drops its price", goal_state: "pending",
        history: [...two, { ts: "2026-10-12T07:00:00+00:00", signal: "stable", trigger: "stable" }]
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
    // Checked, but no answer: never "Not checked yet".
    expect(job.querySelector(".wd-goal-status").textContent).toBe("No clear answer yet");
    expect(card("Cursor").querySelector(".wd-goal-status").textContent).toBe("Not checked yet");
    expect(job.querySelector(".wd-status-time").textContent).toMatch(/^checked /);
    expect(job.querySelector(".wd-headline").textContent).toBe("The answer has held through 2 checks.");
    // Two checks are no shape yet; three are.
    expect(job.querySelector(".wd-record")).toBeNull();
    expect(card("Cursor").querySelectorAll(".wd-record .wd-tick").length).toBe(3);
    // The footer is one line of parts; each dot is tied to the part before it.
    const side = job.querySelector(".wd-item-side");
    expect(side.textContent.replace(/ /g, " ")).toMatch(/^Next check \S.* · Weekly · Public page · Telegram$/);
    expect([...side.querySelectorAll(".wd-sep")].every(dot => dot.previousSibling.textContent === " ")).toBe(true);
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
          { url: "javascript:alert(1)", title: "bad", domain: "x.de" }
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
    const links = card("Adios").querySelectorAll(".wd-sources a");
    expect(links.length).toBe(1);
    expect(links[0].href).toBe("https://www.idealo.de/preisvergleich/OffersOfProduct/1");
    expect(links[0].rel).toContain("noreferrer");
    expect(links[0].querySelector(".wd-source-icon").getAttribute("src")).toBe("/api/topics/favicon?d=idealo.de");
    expect(links[0].querySelector(".wd-source-title").textContent).toBe("Adios Pro 4");
    // A move shows what moved it, not the standing direct links.
    const moved = card("GPU").querySelectorAll(".wd-sources a");
    expect([...moved].map(link => link.href)).toEqual(["https://geizhals.de/p"]);
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
    expect(logo.querySelector(".wd-image-remove").title).toBe("Remove logo");
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
    expect(card.querySelector(".wd-side-meta").textContent).toBe("Telegram");
  });
});
