/**
 * user-settings.js -- account settings: the local copy, its migrations and
 * the sync with GET/PATCH /api/my/settings.
 *
 * The server half is tested in tests/test_user_settings.py.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

const UID = "uid-a";
const OTHER = "uid-b";
const SYNC_KEY = "consensio.settingsSync.v1";

// A stand-in for /api/my/settings: answers like the real route (settings,
// revision, the revision each setting last changed at, refused names) and
// records every call. hold() keeps the next answer back until release();
// `refuse` names settings the server does not take; `answer` replaces the
// next answer's body.
function fakeServer({ settings = {}, revision = 0, fieldRevisions = {} } = {}) {
  const server = { settings: { ...settings }, revision, fieldRevisions: { ...fieldRevisions },
    calls: [], failures: [], held: null, refuse: [], answers: [] };
  server.fetch = async (url, options = {}) => {
    const body = options.body ? JSON.parse(options.body) : null;
    server.calls.push({ url, method: options.method, body, keepalive: options.keepalive,
      auth: options.headers?.Authorization, signal: options.signal });
    if (server.held) await server.held.promise;
    if (options.signal?.aborted) throw new Error("aborted");
    const status = server.failures.shift();
    if (status) return { ok: false, status, json: async () => ({}) };
    const rejected = [];
    if (options.method === "PATCH") {
      const changes = Object.entries(body.settings).filter(([name]) => {
        if (!server.refuse.includes(name)) return true;
        rejected.push(name);
        return false;
      });
      if (changes.length) server.revision += 1;
      changes.forEach(([name, value]) => {
        if (value === null) delete server.settings[name];
        else server.settings[name] = value;
        server.fieldRevisions[name] = server.revision;
      });
    }
    const answer = server.answers.length ? server.answers.shift()
      : { settings: { ...server.settings }, revision: server.revision, field_revisions: { ...server.fieldRevisions },
        ...(options.method === "PATCH" ? { rejected } : {}) };
    return { ok: true, status: 200, json: async () => answer };
  };
  server.hold = () => {
    let release;
    server.held = { promise: new Promise(resolve => { release = resolve; }) };
    server.release = () => { server.held = null; release(); };
  };
  server.patches = () => server.calls.filter(call => call.method === "PATCH").map(call => call.body.settings);
  return server;
}

// A browser that already went through the one-time reset of 2026-10-12,
// unless a test asks for one from before it.
const RESET_KEY = "consensio.settingsReset";

function boot({ storage = {}, server = null, beforeReset = false } = {}) {
  const { window, dom } = loadScripts(["static/js/user-settings.js"], {
    before(win) {
      if (!beforeReset) win.localStorage.setItem(RESET_KEY, "2026-10-12");
      Object.entries(storage).forEach(([key, value]) => win.localStorage.setItem(key, value));
      if (server) win.fetch = server.fetch;
    },
  });
  const events = [];
  window.addEventListener("consensio:settings-change", event => events.push(event.detail));
  const settings = window.App.userSettings;
  const start = (uid = UID) => settings.start({ uid, getToken: async () => "token-" + uid });
  return { window, dom, settings, events, start, local: window.localStorage };
}

function record(local) {
  return JSON.parse(local.getItem(SYNC_KEY) || "null");
}

let opened = [];
beforeEach(() => {
  vi.useFakeTimers();
  opened = [];
});
afterEach(() => {
  opened.forEach(dom => dom.window.close());
  vi.useRealTimers();
  vi.restoreAllMocks();
});

function open(options) {
  const booted = boot(options);
  opened.push(booted.dom);
  return booted;
}

describe("the local copy", () => {
  it("keeps every setting under the storage keys the app used before", () => {
    const { settings, local } = open();
    settings.set("run_mode", "compare");
    settings.set("agent_preferences", { quorum: "fast" });
    settings.set("agent_model", { model_id: "openai/gpt-6-luna", reasoning_effort: "low" });
    settings.set("compare_models", { OpenAI: { enabled: false }, Gemini: { model: "gemini-3.6-flash" } });
    settings.set("consensus_model", "Gemini");
    settings.set("consensus_preset", "custom");
    settings.set("system_prompt", "  Answer in German.  ");
    settings.set("agreement_display", "summary");
    settings.set("consensus_highlights", "critical");
    settings.set("claim_counts", true);
    expect(Object.fromEntries(Object.keys(local).filter(key => key !== SYNC_KEY).map(key => [key, local.getItem(key)]))).toEqual({
      [RESET_KEY]: "2026-10-12",
      runMode: "compare",
      "consensio.agentPreferences.v2": JSON.stringify({ quorum: "fast" }),
      "consensio.agentModel.v1": JSON.stringify({ model_id: "openai/gpt-6-luna", reasoning_effort: "low" }),
      pref_check_OpenAI: "false",
      pref_select_Gemini: "gemini-3.6-flash",
      pref_select_consensus: "Gemini",
      pref_consensus_preset: "custom",
      systemPrompt: "Answer in German.",
      "consensio.agreementDisplay.v1": "summary",
      "consensio.showConsensusMarkers.v1": "true",
      "consensio.consensusHighlightMode.v1": "critical",
      "consensio.showClaimCounts.v1": "true",
    });
    // A guest's choice stays local: no account, no pending list.
    expect(record(local)).toBeNull();
  });

  it("resets a setting to its default with null", () => {
    const { settings, local } = open({ storage: {
      "consensio.showConsensusMarkers.v1": "false", "consensio.consensusHighlightMode.v1": "all",
      pref_check_OpenAI: "true", pref_select_OpenAI: "gpt-5.6-luna", pref_select_consensus: "Gemini",
    } });
    expect(settings.get("consensus_highlights")).toBe("none");
    expect(settings.set("consensus_highlights", null)).toBe(true);
    expect(settings.get("consensus_highlights")).toBeUndefined();
    expect(local.getItem("consensio.showConsensusMarkers.v1")).toBeNull();
    expect(local.getItem("consensio.consensusHighlightMode.v1")).toBeNull();
    settings.set("compare_models", { OpenAI: { enabled: false } });
    expect(local.getItem("pref_select_OpenAI")).toBeNull();
    expect(local.getItem("pref_check_OpenAI")).toBe("false");
    // The Consensus engine is a setting of its own.
    expect(local.getItem("pref_select_consensus")).toBe("Gemini");
    settings.set("compare_models", undefined);
    expect(local.getItem("pref_check_OpenAI")).toBeNull();
    expect(settings.get("compare_models")).toBeUndefined();
  });

  it.each([
    ["run_mode", "fast"],
    ["claim_counts", "true"],
    ["letter_animations", "off"],
    ["agent_model", { model_id: "openai gpt", reasoning_effort: "low" }],
    ["agent_preferences", { depth: "deep" }],
    ["compare_models", { "Open<AI>": { enabled: true } }],
    ["compare_models", { OpenAI: { enabled: "yes" } }],
    ["consensus_model", "gpt 5"],
    ["consensus_preset", "High Quality"],
    ["system_prompt", "x".repeat(12001)],
    ["system_prompt", "ä".repeat(16001)],
    ["agreement_display", "loud"],
    ["consensus_highlights", "some"],
  ])("refuses %s = %j and keeps the stored value", (name, value) => {
    const { settings } = open();
    vi.spyOn(console, "warn").mockImplementation(() => {});
    const before = settings.get(name);
    expect(settings.set(name, value)).toBe(false);
    expect(settings.get(name)).toEqual(before);
  });

  it("tells beforehand whether it takes a value", () => {
    const { settings } = open();
    expect(settings.accepts("system_prompt", "Answer in German.")).toBe(true);
    expect(settings.accepts("system_prompt", null)).toBe(true);
    expect(settings.accepts("system_prompt", "ä".repeat(16001))).toBe(false);
    expect(settings.accepts("run_mode", "fast")).toBe(false);
  });

  it("throws for a setting it does not know", () => {
    const { settings } = open();
    expect(() => settings.set("theme", "dark")).toThrow(/Unknown account setting/);
    expect(() => settings.onChange("theme", () => {})).toThrow(/Unknown account setting/);
  });
});

describe("the one-time reset to Agent and the default preset", () => {
  const BEFORE = {
    runMode: "compare", runModeDefault: "agent-2026-10-02", agentMode: "false", autoConsensus: "false",
    pref_check_Grok: "false", pref_select_OpenAI: "gpt-4o", pref_select_consensus: "OpenAI-Pro",
    pref_consensus_preset: "custom",
    // Not part of the reset: the user's own choices without model IDs.
    systemPrompt: "Answer in German.", "consensio.showClaimCounts.v1": "true",
    "consensio.agentPreferences.v2": JSON.stringify({ depth: "quick" }),
    "consensio.agentModel.v1": JSON.stringify({ model_id: "gpt-6-luna", reasoning_effort: "low" }),
    theme: "dark",
  };

  it("drops the mode and the model choice of an older version once", () => {
    const { settings, local } = open({ storage: BEFORE, beforeReset: true });
    for (const key of ["runMode", "agentMode", "autoConsensus", "pref_check_Grok",
      "pref_select_OpenAI", "pref_select_consensus", "pref_consensus_preset"]) {
      expect(local.getItem(key)).toBeNull();
    }
    // A tab of the previous version still open reads this mark; without it,
    // it would turn a new "consensus" choice into Agent.
    expect(local.getItem("runModeDefault")).toBe("agent-2026-10-02");
    expect(settings.get("run_mode")).toBeUndefined();
    expect(settings.get("compare_models")).toBeUndefined();
    expect(settings.get("system_prompt")).toBe("Answer in German.");
    expect(settings.get("claim_counts")).toBe(true);
    expect(settings.get("agent_preferences")).toEqual({ depth: "quick" });
    expect(settings.get("agent_model")).toEqual({ model_id: "gpt-6-luna", reasoning_effort: "low" });
    expect(local.getItem("theme")).toBe("dark");
    expect(local.getItem(RESET_KEY)).toBe("2026-10-12");
  });

  it("keeps what was chosen after the reset", () => {
    const { settings } = open({ storage: { runMode: "compare", pref_check_Grok: "false" } });
    expect(settings.get("run_mode")).toBe("compare");
    expect(settings.get("compare_models")).toEqual({ Grok: { enabled: false } });
  });

  it("reads a stored mode it does not know as the default", () => {
    const { settings } = open({ storage: { runMode: "bogus" } });
    expect(settings.get("run_mode")).toBeUndefined();
  });

  it("keeps only the Agent choices v1 stored beyond its defaults", () => {
    const { settings, local } = open({ storage: {
      "consensio.agentPreferences.v1": JSON.stringify({ depth: "auto", quorum: "fast", autonomy: "guided" }),
    } });
    expect(settings.get("agent_preferences")).toEqual({ quorum: "fast" });
    expect(local.getItem("consensio.agentPreferences.v1")).toBeNull();
    expect(local.getItem("consensio.agentPreferences.v2")).toBe(JSON.stringify({ quorum: "fast" }));
  });

  it.each([
    ["false", "summary"],
    ["true", undefined],
  ])("reads the old agreement switch %s as %s", (legacy, expected) => {
    const { settings, local } = open({ storage: { "consensio.showAgreementScore.v1": legacy } });
    expect(settings.get("agreement_display")).toBe(expected);
    expect(local.getItem("consensio.showAgreementScore.v1")).toBeNull();
  });

  it.each([
    "Please respond briefly and precisely, focusing only on the essentials.",
    "Please answer thoroughly and precisely, explaining your reasoning and covering the relevant details. Do not oversimplify. Do not ask any follow-up or clarifying questions; answer directly with the information available.",
    "   ",
    "x".repeat(12001),
  ])("drops once what the app itself stored as the system prompt (%s)", prompt => {
    const { settings, local } = open({ storage: { systemPrompt: prompt }, beforeReset: true });
    expect(settings.get("system_prompt")).toBeUndefined();
    expect(local.getItem("systemPrompt")).toBeNull();
  });

  it("keeps a prompt typed after the reset, even one that reads like an old default", () => {
    const { settings } = open();
    const prompt = "Please respond briefly and precisely, focusing only on the essentials.";
    expect(settings.set("system_prompt", prompt)).toBe(true);
    expect(settings.get("system_prompt")).toBe(prompt);
  });
});

describe("change events", () => {
  it("announce a change on this page once, with the previous value", () => {
    const { settings, events } = open({ storage: { "consensio.showClaimCounts.v1": "false" } });
    expect(settings.set("claim_counts", false)).toBe(false);
    settings.set("claim_counts", true);
    expect(events).toEqual([{ names: ["claim_counts"], source: "local", previous: { claim_counts: false } }]);
  });

  it("announce what the Agent's settings card applied as \"agent\" and save it like a change made here", async () => {
    const server = fakeServer({ settings: { claim_counts: false }, revision: 1 });
    const { settings, events, start } = open({ server });
    await start();
    events.length = 0;
    expect(settings.set("claim_counts", true, { source: "agent" })).toBe(true);
    // Any other source name is this page's own change.
    settings.set("agreement_display", "off", { source: "server" });
    await settings.flush();
    expect(events.map(event => [event.names, event.source])).toEqual([[["claim_counts"], "agent"], [["agreement_display"], "local"]]);
    expect(server.patches()).toEqual([{ claim_counts: true, agreement_display: "off" }]);
  });

  it("follow another tab, but not a write that changes no value", () => {
    const { window, settings, events, local } = open({ storage: { runMode: "compare" } });
    const heard = vi.fn();
    settings.onChange("run_mode", heard);
    const tab = (key, value) => {
      local.setItem(key, value);
      window.dispatchEvent(new window.StorageEvent("storage", { key, newValue: value, storageArea: local }));
    };
    tab("runMode", "compare");
    tab("pref_check_Gemini", "false");
    tab("runMode", "consensus");
    expect(events.map(event => [event.names, event.source])).toEqual([[["compare_models"], "tab"], [["run_mode"], "tab"]]);
    expect(heard).toHaveBeenCalledOnce();
    expect(heard.mock.calls[0][0].previous).toEqual({ run_mode: "compare" });
  });
});

describe("sync with the account", () => {
  it("gives an account without settings this browser's choices once", async () => {
    const server = fakeServer();
    const { settings, start, local } = open({ server, storage: {
      runMode: "compare", pref_check_Grok: "false", systemPrompt: "Be brief.",
    } });
    expect(await start()).toBe(true);
    await settings.flush();
    expect(server.calls[0]).toMatchObject({ url: "/api/my/settings", method: "GET", auth: "Bearer token-uid-a" });
    expect(server.patches()).toEqual([{
      run_mode: "compare", compare_models: { Grok: { enabled: false } }, system_prompt: "Be brief.",
    }]);
    expect(record(local)).toEqual({ owner: UID, pending: [], base: 1 });
    expect(settings.status()).toEqual({ uid: UID, loaded: true, pending: [] });

    // The next page of this account finds them on the server: nothing to send.
    const again = open({ server, storage: Object.fromEntries(Object.keys(local).map(key => [key, local.getItem(key)])) });
    await again.start();
    await again.settings.flush();
    expect(server.patches()).toHaveLength(1);
  });

  it("applies the account's settings over this browser's and announces them", async () => {
    const server = fakeServer({ settings: { run_mode: "consensus", claim_counts: true }, revision: 3 });
    const { settings, start, events, local } = open({ server, storage: {
      runMode: "compare", "consensio.agreementDisplay.v1": "summary",
      [SYNC_KEY]: JSON.stringify({ owner: UID, pending: [] }),
    } });
    await start();
    expect(settings.get("run_mode")).toBe("consensus");
    expect(settings.get("claim_counts")).toBe(true);
    // Not on the server: back to the default.
    expect(settings.get("agreement_display")).toBeUndefined();
    expect(local.getItem("consensio.agreementDisplay.v1")).toBeNull();
    expect(events).toEqual([{
      names: ["run_mode", "agreement_display", "claim_counts"], source: "server",
      previous: { run_mode: "compare", agreement_display: "summary", claim_counts: undefined },
    }]);
    expect(server.patches()).toEqual([]);
  });

  it("keeps the Agent choices it knows when the account holds a newer one", async () => {
    // A page of this version and an account saved by a newer one: only the
    // unknown field is left out (the server merges agent_preferences field by field).
    const server = fakeServer({ settings: { agent_preferences: { autonomy: "free", judges: "off", future: "x" } },
      revision: 3 });
    const { settings, start } = open({ server, storage: { [SYNC_KEY]: JSON.stringify({ owner: UID, pending: [] }) } });
    await start();
    expect(settings.get("agent_preferences")).toEqual({ autonomy: "free", judges: "off" });
    expect(server.patches()).toEqual([]);
    // A value it cannot read for a field it knows still refuses the change.
    vi.spyOn(console, "warn").mockImplementation(() => {});
    expect(settings.set("agent_preferences", { autonomy: "free", judges: "maybe" })).toBe(false);
  });

  it("keeps a change made before the account answered and sends it", async () => {
    const server = fakeServer({ settings: { run_mode: "agent", claim_counts: false }, revision: 2 });
    const { settings, start } = open({ server });
    server.hold();
    const loading = start();
    settings.set("run_mode", "compare");
    server.release();
    await loading;
    await settings.flush();
    expect(settings.get("run_mode")).toBe("compare");
    expect(settings.get("claim_counts")).toBe(false);
    expect(server.patches()).toEqual([{ run_mode: "compare" }]);
    expect(server.settings).toEqual({ run_mode: "compare", claim_counts: false });
  });

  it("sends what an earlier page of this account could not deliver", async () => {
    const server = fakeServer({ settings: { run_mode: "agent" }, revision: 5, fieldRevisions: { run_mode: 4 } });
    const { settings, start } = open({ server, storage: {
      runMode: "compare",
      [SYNC_KEY]: JSON.stringify({ owner: UID, pending: ["run_mode", "unknown"], base: 4 }),
    } });
    await start();
    await settings.flush();
    expect(settings.get("run_mode")).toBe("compare");
    expect(server.patches()).toEqual([{ run_mode: "compare" }]);
    expect(settings.status().pending).toEqual([]);
  });

  it("lets a newer value of the account win over a change kept from an earlier page", async () => {
    // The earlier page's request reached the account (its answer was lost
    // with the page), then another device chose consensus.
    const server = fakeServer({ settings: { run_mode: "consensus" }, revision: 7, fieldRevisions: { run_mode: 7 } });
    const { settings, start } = open({ server, storage: {
      runMode: "compare",
      [SYNC_KEY]: JSON.stringify({ owner: UID, pending: ["run_mode"], base: 5 }),
    } });
    await start();
    await settings.flush();
    expect(settings.get("run_mode")).toBe("consensus");
    expect(server.patches()).toEqual([]);
    expect(settings.status().pending).toEqual([]);
  });

  it("never gives one account another account's settings", async () => {
    const server = fakeServer();
    const { settings, start, local } = open({ server, storage: {
      runMode: "compare", systemPrompt: "Private to B.",
      [SYNC_KEY]: JSON.stringify({ owner: OTHER, pending: ["run_mode"] }),
      // This account's own Agent pick from before the sync existed.
      [`agent_settings_${UID}`]: JSON.stringify({ model_id: "anthropic/claude-sonnet-5.5", reasoning_effort: "medium" }),
    } });
    await start();
    await settings.flush();
    expect(settings.get("run_mode")).toBeUndefined();
    expect(settings.get("system_prompt")).toBeUndefined();
    expect(server.patches()).toEqual([{
      agent_model: { model_id: "anthropic/claude-sonnet-5.5", reasoning_effort: "medium" },
    }]);
    expect(local.getItem(`agent_settings_${UID}`)).toBeNull();
    expect(record(local)).toEqual({ owner: UID, pending: [], base: 1 });
  });

  it("collects quick changes into one request", async () => {
    const server = fakeServer({ revision: 1 });
    const { settings, start } = open({ server });
    await start();
    settings.set("run_mode", "compare");
    settings.set("claim_counts", false);
    settings.set("run_mode", "consensus");
    expect(server.patches()).toEqual([]);
    await vi.advanceTimersByTimeAsync(400);
    await settings.flush();
    expect(server.patches()).toEqual([{ run_mode: "consensus", claim_counts: false }]);
  });

  it("keeps a change pending through a failure and sends it again", async () => {
    const server = fakeServer({ revision: 1 });
    const { settings, start } = open({ server });
    await start();
    server.failures.push(503);
    settings.set("claim_counts", true);
    await settings.flush();
    expect(settings.status().pending).toEqual(["claim_counts"]);
    await vi.advanceTimersByTimeAsync(2000);
    await settings.flush();
    expect(server.patches()).toEqual([{ claim_counts: true }, { claim_counts: true }]);
    expect(settings.status().pending).toEqual([]);
    expect(server.settings).toEqual({ claim_counts: true });
  });

  it("saves the settings the account takes when it refuses one of them", async () => {
    const server = fakeServer({ revision: 1 });
    const { settings, start } = open({ server });
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    await start();
    server.refuse = ["claim_counts"];
    settings.set("claim_counts", true);
    settings.set("run_mode", "compare");
    await settings.flush();
    expect(server.settings).toEqual({ run_mode: "compare" });
    expect(settings.status().pending).toEqual([]);
    expect(warn).toHaveBeenCalledWith("Settings the account did not take:", "claim_counts");
    // The refused choice still holds on this page.
    expect(settings.get("claim_counts")).toBe(true);
  });

  it("drops a change the account refuses instead of retrying it forever", async () => {
    const server = fakeServer({ revision: 1 });
    const { settings, start } = open({ server });
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    await start();
    server.failures.push(422);
    settings.set("claim_counts", true);
    await settings.flush();
    await vi.advanceTimersByTimeAsync(300000);
    expect(server.patches()).toHaveLength(1);
    expect(settings.status().pending).toEqual([]);
    expect(warn).toHaveBeenCalled();
    // The choice still holds on this page.
    expect(settings.get("claim_counts")).toBe(true);
  });

  it("retries loading when the account cannot be reached", async () => {
    const server = fakeServer({ settings: { run_mode: "compare" }, revision: 1 });
    server.failures.push(503);
    const { settings, start } = open({ server });
    expect(await start()).toBe(false);
    expect(settings.get("run_mode")).toBeUndefined();
    await vi.advanceTimersByTimeAsync(2000);
    expect(settings.status().loaded).toBe(true);
    expect(settings.get("run_mode")).toBe("compare");
  });

  it("follows the account that takes over the page", async () => {
    const server = fakeServer({ settings: { run_mode: "compare" }, revision: 1 });
    const { settings, start } = open({ server });
    await start(UID);
    expect(settings.get("run_mode")).toBe("compare");
    server.settings = { run_mode: "consensus" };
    await start(OTHER);
    expect(settings.get("run_mode")).toBe("consensus");
    expect(settings.status().uid).toBe(OTHER);
    expect(server.calls.at(-1).auth).toBe("Bearer token-uid-b");
  });

  it("removes the account's settings from this browser on sign-out", async () => {
    const server = fakeServer({ settings: { run_mode: "compare", system_prompt: "Mine." }, revision: 1 });
    const { settings, start, events, local } = open({ server });
    await start();
    settings.stop();
    expect(settings.get("run_mode")).toBeUndefined();
    expect(settings.get("system_prompt")).toBeUndefined();
    expect(local.getItem(SYNC_KEY)).toBeNull();
    expect(events.at(-1)).toMatchObject({ names: ["run_mode", "system_prompt"], source: "signout" });
    expect(settings.status()).toEqual({ uid: null, loaded: false, pending: [] });
  });

  it("leaves a guest's own choices alone on sign-out", () => {
    const { settings } = open({ storage: { runMode: "compare" } });
    settings.stop();
    expect(settings.get("run_mode")).toBe("compare");
  });

  it("lets the logout wait for a pending change only so long", async () => {
    const server = fakeServer({ revision: 1 });
    const { settings, start } = open({ server });
    await start();
    settings.set("run_mode", "compare");
    server.hold();
    let done = false;
    settings.flush({ timeoutMs: 3000 }).then(() => { done = true; });
    await vi.advanceTimersByTimeAsync(2999);
    expect(done).toBe(false);
    await vi.advanceTimersByTimeAsync(1);
    expect(done).toBe(true);
    // The request itself still goes out.
    expect(server.patches()).toEqual([{ run_mode: "compare" }]);
    server.release();
  });

  it("sends what is pending with keepalive when the page goes away", async () => {
    const server = fakeServer({ revision: 1 });
    const { window, settings, start } = open({ server });
    await start();
    settings.set("claim_counts", false);
    window.dispatchEvent(new window.Event("pagehide"));
    await settings.flush();
    expect(server.calls.at(-1)).toMatchObject({ method: "PATCH", keepalive: true, body: { settings: { claim_counts: false } } });
  });

  it("lets a repair the app makes itself never win over the account's value", async () => {
    const server = fakeServer({ settings: { agent_model: { model_id: "gpt-6-sol", reasoning_effort: "high" } }, revision: 2 });
    const { settings, start } = open({ server, storage: {
      "consensio.agentModel.v1": JSON.stringify({ model_id: "retired-model", reasoning_effort: "default" }),
      [SYNC_KEY]: JSON.stringify({ owner: UID, pending: [], base: 2 }),
    } });
    server.hold();
    const loading = start();
    settings.set("agent_model", { model_id: "catalog-default" }, { derived: true });
    server.release();
    await loading;
    await settings.flush();
    expect(settings.get("agent_model")).toEqual({ model_id: "gpt-6-sol", reasoning_effort: "high" });
    expect(server.patches()).toEqual([]);
  });

  it("does not carry one account's changes into the next", async () => {
    const server = fakeServer({ revision: 1 });
    const { settings, start } = open({ server });
    await start(UID);
    settings.set("system_prompt", "A's private instructions");
    await settings.flush();
    server.settings = { run_mode: "consensus" };
    await start(OTHER);
    await settings.flush();
    expect(server.patches()).toEqual([{ system_prompt: "A's private instructions" }]);
    expect(settings.get("system_prompt")).toBeUndefined();
    expect(settings.get("run_mode")).toBe("consensus");
  });

  it("fills the settings the account lacks on the first sync of a browser", async () => {
    // Another device synced first and stored only an Agent pick.
    const server = fakeServer({ settings: { agent_model: { model_id: "gpt-6-luna", reasoning_effort: "default" } },
      revision: 1, fieldRevisions: { agent_model: 1 } });
    const { settings, start } = open({ server, storage: {
      systemPrompt: "Always answer in German.", "consensio.showClaimCounts.v1": "false",
      "consensio.agentModel.v1": JSON.stringify({ model_id: "claude-opus-5-5", reasoning_effort: "default" }),
    } });
    await start();
    await settings.flush();
    expect(settings.get("system_prompt")).toBe("Always answer in German.");
    expect(settings.get("claim_counts")).toBe(false);
    // What the account has applies.
    expect(settings.get("agent_model")).toEqual({ model_id: "gpt-6-luna", reasoning_effort: "default" });
    expect(server.patches()).toEqual([{ system_prompt: "Always answer in German.", claim_counts: false }]);
  });

  it("takes the account's values as they are once this browser synced before", async () => {
    const server = fakeServer({ settings: { claim_counts: true }, revision: 3 });
    const { settings, start } = open({ server, storage: {
      "consensio.agreementDisplay.v1": "summary", "consensio.settingsSeeded": "1",
    } });
    await start();
    await settings.flush();
    expect(settings.get("agreement_display")).toBeUndefined();
    expect(settings.get("claim_counts")).toBe(true);
    expect(server.patches()).toEqual([]);
  });

  it("keeps a change made without a session for the account this browser belongs to", async () => {
    const { settings, local } = open({ storage: { [SYNC_KEY]: JSON.stringify({ owner: UID, pending: [], base: 3 }) } });
    settings.set("run_mode", "compare");
    expect(record(local)).toEqual({ owner: UID, pending: ["run_mode"], base: 3 });
  });

  it("sends a setting again when another tab's newer request was overtaken by this one", async () => {
    const server = fakeServer({ revision: 1 });
    const { settings, start, local } = open({ server });
    await start();
    settings.set("run_mode", "compare");
    server.hold();
    const sending = settings.flush();
    // Meanwhile another tab chose consensus, sent it, saw it confirmed and
    // cleared the shared pending list -- then this older request lands last.
    local.setItem("runMode", "consensus");
    local.setItem(SYNC_KEY, JSON.stringify({ owner: UID, pending: [], base: 2 }));
    server.release();
    await sending;
    expect(server.settings).toEqual({ run_mode: "compare" });
    await settings.flush();
    expect(server.patches()).toEqual([{ run_mode: "compare" }, { run_mode: "consensus" }]);
    expect(server.settings).toEqual({ run_mode: "consensus" });
    expect(settings.status().pending).toEqual([]);
  });

  it.each([
    [{}],
    [null],
    [{ settings: null, revision: "abc" }],
    [{ settings: [], revision: 3 }],
  ])("treats an unreadable answer %j as a failure, not as an empty account", async answer => {
    const server = fakeServer({ settings: { run_mode: "consensus" }, revision: 2 });
    server.answers.push(answer);
    const { settings, start } = open({ server, storage: { runMode: "compare", systemPrompt: "Mine." } });
    expect(await start()).toBe(false);
    expect(settings.get("system_prompt")).toBe("Mine.");
    await vi.advanceTimersByTimeAsync(2000);
    expect(settings.status().loaded).toBe(true);
    expect(settings.get("run_mode")).toBe("consensus");
  });

  it("gives up on a request that hangs and tries again", async () => {
    const server = fakeServer({ settings: { run_mode: "compare" }, revision: 1 });
    server.hold();
    const { settings, start } = open({ server });
    const loading = start();
    await vi.advanceTimersByTimeAsync(15000);
    expect(server.calls[0].signal.aborted).toBe(true);
    server.release();
    expect(await loading).toBe(false);
    await vi.advanceTimersByTimeAsync(2000);
    expect(settings.get("run_mode")).toBe("compare");
  });

  it("loads once even when the browser comes back online meanwhile", async () => {
    const server = fakeServer({ revision: 1 });
    const { window, start } = open({ server });
    server.hold();
    const loading = start();
    window.dispatchEvent(new window.Event("online"));
    server.release();
    await loading;
    expect(server.calls.filter(call => call.method === "GET")).toHaveLength(1);
  });

  it("asks once more when an answer is older than what another tab confirmed", async () => {
    const server = fakeServer({ settings: { run_mode: "compare" }, revision: 6 });
    server.answers.push({ settings: { run_mode: "agent" }, revision: 4, field_revisions: {} });
    const { settings, start } = open({ server, storage: {
      [SYNC_KEY]: JSON.stringify({ owner: UID, pending: [], base: 6 }),
    } });
    await start();
    expect(server.calls.filter(call => call.method === "GET")).toHaveLength(2);
    expect(settings.get("run_mode")).toBe("compare");
  });
});

describe("robustness", () => {
  it("installs even when storage lists a key that is not a string", () => {
    const { window, dom } = loadScripts(["static/js/user-settings.js"], {
      before(win) {
        win.localStorage.setItem("pref_check_Grok", "false");
        win.Storage.prototype.key = () => null;
      },
    });
    opened.push(dom);
    expect(window.App.userSettings.get("run_mode")).toBeUndefined();
  });

  it("keeps family labels that name Object members as ordinary entries", () => {
    const { settings } = open({ storage: { pref_check_constructor: "true", pref_select_constructor: "model-x" } });
    expect(settings.get("compare_models")).toEqual({ constructor: { enabled: true, model: "model-x" } });
    expect(Object.prototype.enabled).toBeUndefined();
    expect(settings.set("compare_models", { ...settings.get("compare_models"), OpenAI: { enabled: false } })).toBe(true);
  });

  it("refuses a system prompt with a broken character", () => {
    const { settings } = open();
    vi.spyOn(console, "warn").mockImplementation(() => {});
    expect(settings.accepts("system_prompt", "Answer briefly \uD83D")).toBe(false);
    expect(settings.accepts("system_prompt", "Answer briefly \uD83D\uDE00")).toBe(true);
  });

  it("catches up on a page restored from the back/forward cache", () => {
    const { window, events, local } = open();
    local.setItem("runMode", "compare");
    window.dispatchEvent(new window.PageTransitionEvent("pageshow", { persisted: true }));
    expect(events).toEqual([{ names: ["run_mode"], source: "tab", previous: { run_mode: undefined } }]);
  });
});
