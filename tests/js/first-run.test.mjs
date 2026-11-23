import { afterEach, describe, expect, it } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

// static/js/first-run.js: the two-step dialog before an account's first
// question (ai-consent.js asks through it).
const contexts = [];
const PROVIDERS = [
  { text: "OpenAI", icon: "/static/chatgpt.png", iconClass: "chatgpt-logo" },
  { text: "Anthropic Claude", icon: "/static/claude.png" },
];

function boot() {
  const calls = { settings: [], memory: [], events: [] };
  const ctx = loadScripts(["static/js/motion.js", "static/js/modal-dialog.js", "static/js/first-run.js"], {
    before(window) {
      window.App = {
        userSettings: { set: (name, value) => calls.settings.push([name, value]) },
        userMemory: { enableAgentMemory: source => calls.memory.push(source) },
        trackAppEvent: (name, fields) => calls.events.push([name, fields]),
      };
    },
  });
  contexts.push(ctx);
  const dialog = () => ctx.document.getElementById("firstRunDialog");
  const pick = view => {
    const input = dialog().querySelector(`input[name="firstRunView"][value="${view}"]`);
    input.checked = true;
    input.dispatchEvent(new ctx.window.Event("change", { bubbles: true }));
  };
  return { ...ctx, App: ctx.window.App, calls, dialog, pick };
}
afterEach(() => contexts.splice(0).forEach(ctx => ctx.window.close()));

describe("the dialog", () => {
  it("opens on the choices with the app's default view and memory off, without a button that says no", () => {
    const { App, dialog } = boot();
    App.firstRun.ask({ providers: PROVIDERS });
    expect(dialog().dataset.step).toBe("setup");
    expect(dialog().dataset.view).toBe("doubts");
    expect(dialog().querySelector("#firstRunMemory").checked).toBe(false);
    expect(dialog().querySelector(".first-run-caption").textContent)
      .toBe("You see what was fixed and what is still open.");
    expect(dialog().querySelector(".confirm-cancel")).toBeNull();
    expect(dialog().querySelector(".close-button").dataset.answer).toBe("false");
  });

  it("plays one answer as a scene: its words in stream order, the wrong claim with its corrected year, the reviewers' logos", () => {
    const { App, dialog } = boot();
    App.firstRun.ask({ providers: [...PROVIDERS, { text: "Gemini", icon: "/g.png" }, { text: "Grok", icon: "/x.png" }] });
    const stage = dialog().querySelector(".first-run-stage");
    expect(stage.getAttribute("aria-hidden")).toBe("true");
    expect(stage.querySelector(".first-run-answer").textContent)
      .toBe("The Eiffel Tower opened in 18871889 and is the most visited monument in the world.");
    const places = [...stage.querySelectorAll(".first-run-word")].map(word => Number(word.style.getPropertyValue("--i")));
    expect(places).toEqual(places.map((_, index) => index));
    expect(stage.querySelector(".first-run-claim").textContent).toBe("opened in 18871889");
    expect([...stage.querySelectorAll(".first-run-claim > .first-run-year > span")].map(year => [year.className, year.textContent]))
      .toEqual([["is-old", "1887"], ["is-new", "1889"]]);
    expect(stage.querySelector(".first-run-mark").textContent).toBe("the most visited monument in the world");
    // Its dots fade in apart from its words (first-run.css): each word
    // carries its text for them, each space is a span of its own.
    expect([...stage.querySelectorAll(".first-run-mark > *")].map(part => part.dataset.dots ?? part.className))
      .toEqual(["the", "first-run-gap", "most", "first-run-gap", "visited", "first-run-gap", "monument",
        "first-run-gap", "in", "first-run-gap", "the", "first-run-gap", "world"]);
    expect(stage.querySelectorAll(".first-run-answer > .first-run-gap, .first-run-claim [data-dots]")).toHaveLength(0);
    expect(stage.querySelectorAll(".first-run-reviewers img")).toHaveLength(3);
  });

  it("runs the reviewers' progress in one line above the answer, their steps in it", () => {
    const { App, dialog } = boot();
    App.firstRun.ask({ providers: PROVIDERS });
    const scene = dialog().querySelector(".first-run-scene");
    expect([...scene.children].map(child => child.className)).toEqual(["first-run-status", "first-run-answer"]);
    expect([...scene.querySelectorAll(".first-run-phases > span")].map(phase => phase.className))
      .toEqual(["is-checking", "is-step", "is-step", "is-step", "is-found", "is-done"]);
  });

  it("keeps the claim around the year where a translation puts it", () => {
    const { App, dialog } = boot();
    App.t = text => text.startsWith("The Eiffel Tower <3>")
      ? "Der Eiffelturm <3>wurde <0>1887</0><1>1889</1> eröffnet</3> und ist <2>das meistbesuchte Bauwerk der Welt</2>."
      : text;
    App.firstRun.ask({ providers: PROVIDERS });
    const stage = dialog().querySelector(".first-run-stage");
    expect(stage.querySelector(".first-run-answer").textContent)
      .toBe("Der Eiffelturm wurde 18871889 eröffnet und ist das meistbesuchte Bauwerk der Welt.");
    expect(stage.querySelector(".first-run-claim").textContent).toBe("wurde 18871889 eröffnet");
    expect([...stage.querySelectorAll(".first-run-claim .first-run-word")].map(word => word.textContent))
      .toEqual(["wurde", "18871889", "eröffnet"]);
  });

  it("answers with the chosen view and memory after Continue and Agree", async () => {
    const { App, dialog, pick } = boot();
    const answer = App.firstRun.ask({ providers: PROVIDERS });
    pick("all");
    expect(dialog().dataset.view).toBe("all");
    expect(dialog().querySelector(".first-run-caption").textContent).toBe("Plus what they confirm and every step, live.");
    dialog().querySelector("#firstRunMemory").checked = true;
    dialog().querySelector(".first-run-next").click();
    expect(dialog().dataset.step).toBe("consent");
    expect(dialog().getAttribute("aria-labelledby")).toBe("firstRunConsentTitle");
    dialog().querySelector(".confirm-accept").click();
    expect(await answer).toEqual({ view: "all", memory: true });
  });

  it("shows the providers as logos first and keeps their names one click away", () => {
    const { App, dialog } = boot();
    App.firstRun.ask({ providers: [...PROVIDERS, { text: "" }] });
    const providers = dialog().querySelector(".first-run-providers");
    expect(providers.open).toBe(false);
    expect(providers.querySelectorAll(".first-run-logos img")).toHaveLength(2);
    expect([...providers.querySelectorAll("li")].map(row => row.textContent)).toEqual(["OpenAI", "Anthropic Claude"]);
    // A provider without a logo has nothing to stand for its name.
    App.firstRun.ask({ providers: [...PROVIDERS, { text: "Qwen" }] });
    expect(dialog().querySelector(".first-run-providers").open).toBe(true);
  });

  it("switches to Raw HTML at once with I like it raw, and back with a second press", () => {
    const { App, dialog, calls } = boot();
    let raw = false;
    App.userSettings.get = name => (name === "raw_display" ? raw : undefined);
    App.userSettings.set = (name, value) => {
      calls.settings.push([name, value]);
      if (name === "raw_display") raw = value;
    };
    App.firstRun.ask({ providers: PROVIDERS });
    const button = dialog().querySelector(".first-run-raw");
    expect(button.textContent).toBe("I like it raw");
    expect(button.getAttribute("aria-pressed")).toBe("false");
    button.click();
    expect(calls.settings).toEqual([["raw_display", true]]);
    expect(button.getAttribute("aria-pressed")).toBe("true");
    // A look, not an answer: the dialog stays on its choices.
    expect(dialog().dataset.step).toBe("setup");
    button.click();
    expect(raw).toBe(false);
    expect(button.getAttribute("aria-pressed")).toBe("false");
  });

  it("answers null for the X and starts over next time", async () => {
    const { App, dialog, pick } = boot();
    const first = App.firstRun.ask({ providers: PROVIDERS });
    pick("answer");
    dialog().querySelector(".first-run-next").click();
    dialog().querySelector(".close-button").click();
    expect(await first).toBeNull();
    App.firstRun.ask({ providers: PROVIDERS });
    expect(dialog().dataset.step).toBe("setup");
    expect(dialog().dataset.view).toBe("doubts");
  });

  it("can ask for the agreement alone or the choices alone", async () => {
    const { App, dialog } = boot();
    const consent = App.firstRun.ask({ providers: PROVIDERS, steps: ["consent"] });
    expect(dialog().dataset.step).toBe("consent");
    dialog().querySelector(".confirm-accept").click();
    expect(await consent).toEqual({ view: "doubts", memory: false });
    const setup = App.firstRun.ask({ steps: ["setup"] });
    expect(dialog().querySelector(".first-run-next").textContent).toBe("Done");
    dialog().querySelector(".first-run-next").click();
    expect(await setup).toEqual({ view: "doubts", memory: false });
  });
});

describe("apply", () => {
  it("writes only what differs from the app's default; the correction pass is the default in every view", () => {
    const { App, calls } = boot();
    App.firstRun.apply({ view: "doubts", memory: false });
    expect(calls.settings).toEqual([]);
    expect(calls.memory).toEqual([]);
    calls.settings.length = 0;
    App.firstRun.apply({ view: "answer", memory: true });
    expect(calls.settings).toEqual([["consensus_highlights", "critical"]]);
    expect(calls.memory).toEqual(["first_run"]);
    calls.settings.length = 0;
    App.firstRun.apply({ view: "all", memory: false });
    expect(calls.settings)
      .toEqual([["consensus_highlights", "all"], ["detailed_progress", true]]);
    expect(calls.events.at(-1)).toEqual(["app_first_run", { view: "all", memory: false }]);
  });

  it("hands the view to the modules that own it, as a change they did not make themselves", () => {
    // consensus-insights.js ignores a "local" change of consensus_highlights
    // (its own select already applied it): the answer kept the old marks
    // until a reload.
    const ctx = loadScripts(["static/js/user-settings.js", "static/js/first-run.js"], {
      before(window) {
        window.localStorage.setItem("consensio.settingsReset", "2026-10-12");
        window.App = { userMemory: {}, trackAppEvent: () => {} };
      },
    });
    contexts.push(ctx);
    const changes = [];
    ctx.window.addEventListener("consensio:settings-change", event => changes.push(event.detail));
    ctx.window.App.firstRun.apply({ view: "all", memory: false });
    expect(ctx.window.App.userSettings.get("consensus_highlights")).toBe("all");
    expect(changes.map(detail => [detail.names, detail.source])).toEqual([
      [["consensus_highlights"], "first_run"], [["detailed_progress"], "first_run"],
    ]);
  });

  it("ignores a view it does not know", () => {
    const { App, calls } = boot();
    App.firstRun.apply({ view: "everything" });
    App.firstRun.apply(null);
    expect(calls.settings).toEqual([]);
  });
});
