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

  it("answers with the chosen view and memory after Continue and Agree", async () => {
    const { App, dialog, pick } = boot();
    const answer = App.firstRun.ask({ providers: PROVIDERS });
    pick("all");
    expect(dialog().dataset.view).toBe("all");
    expect(dialog().querySelector(".first-run-caption").textContent).toBe("Plus every thought and step, live.");
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
  it("writes only what differs from the app's default, and the correction pass for every view", () => {
    const { App, calls } = boot();
    App.firstRun.apply({ view: "doubts", memory: false });
    expect(calls.settings).toEqual([["findings_to_agent", true]]);
    expect(calls.memory).toEqual([]);
    calls.settings.length = 0;
    App.firstRun.apply({ view: "answer", memory: true });
    expect(calls.settings).toEqual([["consensus_highlights", "critical"], ["findings_to_agent", true]]);
    expect(calls.memory).toEqual(["first_run"]);
    calls.settings.length = 0;
    App.firstRun.apply({ view: "all", memory: false });
    expect(calls.settings)
      .toEqual([["consensus_highlights", "all"], ["detailed_progress", true], ["findings_to_agent", true]]);
    expect(calls.events.at(-1)).toEqual(["app_first_run", { view: "all", memory: false }]);
  });

  it("ignores a view it does not know", () => {
    const { App, calls } = boot();
    App.firstRun.apply({ view: "everything" });
    App.firstRun.apply(null);
    expect(calls.settings).toEqual([]);
  });
});
