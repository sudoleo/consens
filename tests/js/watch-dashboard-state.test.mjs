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
    const figures = body.querySelectorAll(".wd-image");
    expect(figures.length).toBe(1);
    const figure = figures[0];
    expect(figure.closest(".wd-subject").querySelector(".wd-question a").textContent)
      .toBe("Adios Pro 4 in 44.5 under 140 euros?");
    const img = figure.querySelector("img");
    expect(img.getAttribute("src")).toBe(imageUrl);
    expect(img.alt).toBe("");
    const frame = figure.querySelector("a.wd-image-frame");
    expect(frame.href).toBe("https://shop.test/p/1");
    expect(frame.rel).toContain("noreferrer");
    expect(frame.getAttribute("aria-label")).toBe("Image from shop.test");

    figure.querySelector(".wd-image-remove").click();
    await vi.waitFor(() => expect(body.querySelector(".wd-image")).toBeNull());
    expect(calls).toContainEqual(["DELETE", "/api/watch/WatchImage0001/image"]);
  });
});
