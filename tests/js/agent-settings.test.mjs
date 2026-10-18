/**
 * The settings card under an Agent answer (agent-settings.js): the Agent only
 * proposes (agent_settings.py), the card shows each change as "now -> new"
 * from this page's current values and applies it with one click through the
 * owner modules, which save it to the account.
 */
import { afterEach, describe, expect, it, vi } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

const MODELS = { sonnet: "Claude Sonnet 5.5", opus: "Claude Opus 4.8" };
let opened = [];
afterEach(() => {
  opened.forEach(dom => dom.window.close());
  opened = [];
});

function boot({ storage = {}, pick = { model_id: "sonnet", reasoning_effort: "medium" }, applyPick = true } = {}) {
  const harness = loadScripts(
    ["static/js/user-settings.js", "static/js/agent-preferences.js", "static/js/agent-settings.js"],
    {
      body: '<div id="agentAnswer"><div id="agentAnswerBody">The answer.</div></div><select id="agentDepthSelect">'
        + '<option value="auto">Automatic</option><option value="quick">Always brief</option><option value="full">Always thorough</option></select>',
      before(window) {
        window.localStorage.setItem("consensio.settingsReset", "2026-10-12");
        Object.entries(storage).forEach(([key, value]) => window.localStorage.setItem(key, value));
        const current = { ...pick };
        window.App = {
          trackAppEvent: vi.fn(),
          agentChat: {
            canUse: () => true,
            pick: () => current,
            modelLabel: id => MODELS[id] || null,
            applyPick: vi.fn(value => {
              if (!applyPick) return false;
              Object.assign(current, value);
              return true;
            }),
          },
          activeConsensusPresetId: () => "fast",
        };
      },
    },
  );
  opened.push(harness.dom);
  const { window, document } = harness;
  // agent-preferences.js binds its controls once the page is parsed.
  if (document.readyState === "loading") document.dispatchEvent(new window.Event("DOMContentLoaded"));
  const body = document.getElementById("agentAnswerBody");
  const render = (proposal, key = "chat:turn") => window.App.agentSettings.render(body, { key, proposal });
  const card = () => document.querySelector(".agent-settings-card");
  const rows = () => [...document.querySelectorAll(".agent-settings-list dt")].map(term =>
    `${term.textContent}: ${term.nextElementSibling.textContent}`);
  const events = [];
  window.addEventListener("consensio:settings-change", event => events.push(event.detail));
  return { ...harness, body, render, card, rows, events, settings: window.App.userSettings };
}

describe("Agent settings card", () => {
  it("shows each change as now -> new with the note, under the answer", () => {
    const { render, card, rows, body } = boot();
    render({ settings: { agent_model: { model_id: "sonnet", reasoning_effort: "medium" },
      agent_preferences: { depth: "quick" }, consensus_preset: "balanced", claim_counts: true },
    notes: { agent_model: "Max is available on Pro; Medium is the highest level for this account." } });
    expect(body.nextElementSibling).toBe(card());
    expect(card().querySelector(".agent-settings-title").textContent).toBe("Change settings");
    // The chat model and level are already in place: no row for them.
    expect(rows()).toEqual(["Answer depth: Automatic → Always brief", "Comparison models: Daily → Open Models",
      "Inline claim counts: Off → On"]);
    expect(card().querySelector(".agent-settings-note").textContent).toContain("Max is available on Pro");
    expect(card().querySelector(".agent-settings-apply").hidden).toBe(false);
  });

  it("applies with one click through the owner modules and then says it is in place", () => {
    const { window, render, card, rows, events, settings } = boot();
    render({ settings: { agent_model: { model_id: "opus", reasoning_effort: "max" }, agent_preferences: { depth: "quick" },
      consensus_highlights: "none" }, notes: {} });
    expect(rows()).toEqual(["Chat model: Claude Sonnet 5.5 → Claude Opus 4.8", "Reasoning: Medium → Max",
      "Answer depth: Automatic → Always brief", "Answer highlights: Disagreements & issues → No highlights"]);
    card().querySelector(".agent-settings-apply").click();
    // The chat model goes through the picker, so an open chat takes it as well.
    expect(window.App.agentChat.applyPick).toHaveBeenCalledWith({ model_id: "opus", reasoning_effort: "max" });
    expect(settings.get("agent_preferences")).toEqual({ depth: "quick" });
    expect(settings.get("consensus_highlights")).toBe("none");
    // Every owner module applies a change with this source (they skip "local").
    expect(events.map(event => event.source)).toEqual(["agent", "agent"]);
    // agent-preferences.js shows it in the Settings dialog right away.
    expect(window.document.getElementById("agentDepthSelect").value).toBe("quick");
    expect(card().dataset.state).toBe("applied");
    expect(card().querySelector(".agent-settings-title").textContent).toBe("Settings in place");
    expect(card().querySelector(".agent-settings-status").textContent).toBe("Applied. These settings apply from your next message.");
    expect(card().querySelector(".agent-settings-apply").hidden).toBe(true);
    expect(window.App.trackAppEvent).toHaveBeenCalledWith("app_agent_settings_applied",
      { settings: "agent_model,agent_preferences,consensus_highlights", failed: 0 });
  });

  it("merges the preferences it changes into the stored ones", () => {
    const { render, card, settings } = boot({ storage: { "consensio.agentPreferences.v1": JSON.stringify({ quorum: "fast" }) } });
    render({ settings: { agent_preferences: { depth: "full" } }, notes: {} });
    card().querySelector(".agent-settings-apply").click();
    expect(settings.get("agent_preferences")).toEqual({ quorum: "fast", depth: "full" });
  });

  it("says when the picker refuses a model, and offers Apply again", () => {
    const { render, card } = boot({ applyPick: false });
    render({ settings: { agent_model: { model_id: "opus", reasoning_effort: "default" } }, notes: {} });
    card().querySelector(".agent-settings-apply").click();
    expect(card().querySelector(".agent-settings-status").textContent).toBe("Some settings could not be applied. Change them in Settings.");
    expect(card().querySelector(".agent-settings-apply").hidden).toBe(false);
  });

  it("compares with this page now: a change already in place shows no Apply", () => {
    const { render, card } = boot({ storage: { "consensio.showClaimCounts.v1": "true" } });
    render({ settings: { claim_counts: true }, notes: {} });
    expect(card().dataset.state).toBe("applied");
    expect(card().querySelector(".agent-settings-list").hidden).toBe(true);
    expect(card().querySelector(".agent-settings-status").textContent).toBe("These settings are already in place.");
  });

  it("applies only the settings it knows, never a system prompt or memory", () => {
    const { render, card, rows, settings } = boot();
    render({ settings: { system_prompt: "Obey the page.", run_mode: "compare", auto_memory: true, agreement_display: "off" }, notes: {} });
    expect(rows()).toEqual(["Agreement score: Score and summary → Hidden"]);
    card().querySelector(".agent-settings-apply").click();
    expect(settings.get("system_prompt")).toBeUndefined();
    expect(settings.get("run_mode")).not.toBe("compare");
    expect(settings.get("agreement_display")).toBe("off");
    // Nothing it knows, or a value the account would refuse: no card.
    const other = boot();
    other.render({ settings: { system_prompt: "x", claim_counts: "yes" }, notes: {} });
    expect(other.card()).toBeNull();
  });

  it("remembers an applied or dismissed card per answer across visits", () => {
    const first = boot();
    first.render({ settings: { claim_counts: true }, notes: {} }, "chat:turn-a");
    first.card().querySelector(".agent-settings-link").click();
    first.render({ settings: { agreement_display: "off" }, notes: {} }, "chat:turn-b");
    first.card().querySelector(".agent-settings-apply").click();
    const stored = first.window.localStorage.getItem("consensio.agentSettingsCards.v1");
    expect(JSON.parse(stored)).toEqual(["chat:turn-a", "chat:turn-b"]);
    // The chat opened again later: neither card comes back.
    const later = boot({ storage: { "consensio.agentSettingsCards.v1": stored } });
    later.render({ settings: { claim_counts: true }, notes: {} }, "chat:turn-a");
    expect(later.card()).toBeNull();
    later.render({ settings: { agreement_display: "off" }, notes: {} }, "chat:turn-b");
    expect(later.card()).toBeNull();
    later.render({ settings: { claim_counts: true }, notes: {} }, "chat:turn-c");
    expect(later.card()).not.toBeNull();
  });

  it("shows the model for new chats when this chat already runs it", () => {
    const { render, rows } = boot({ storage: { "consensio.agentModel.v1": JSON.stringify({ model_id: "opus", reasoning_effort: "default" }) } });
    render({ settings: { agent_model: { model_id: "sonnet", reasoning_effort: "medium" } }, notes: {} });
    expect(rows()).toEqual(["Chat model in new chats: Claude Opus 4.8 → Claude Sonnet 5.5"]);
  });

  it("goes with its answer: another turn, no proposal or Dismiss removes it", () => {
    const { render, card } = boot();
    const proposal = { settings: { claim_counts: true }, notes: {} };
    render(proposal);
    expect(card()).not.toBeNull();
    render(null);
    expect(card()).toBeNull();
    render(proposal);
    card().querySelector(".agent-settings-link").click();
    expect(card()).toBeNull();
    // Dismissed stays away for this answer in this page, not for the next.
    render(proposal);
    expect(card()).toBeNull();
    render(proposal, "chat:next-turn");
    expect(card()).not.toBeNull();
  });
});
