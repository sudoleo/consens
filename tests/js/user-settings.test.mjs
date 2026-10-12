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

// A stand-in for /api/my/settings: answers like the real route and records
// every call. hold() keeps the next answer back until release().
function fakeServer({ settings = {}, revision = 0 } = {}) {
  const server = { settings: { ...settings }, revision, calls: [], failures: [], held: null };
  server.fetch = async (url, options = {}) => {
    const body = options.body ? JSON.parse(options.body) : null;
    server.calls.push({ url, method: options.method, body, keepalive: options.keepalive,
      auth: options.headers?.Authorization });
    if (server.held) await server.held.promise;
    const status = server.failures.shift();
    if (status) return { ok: false, status, json: async () => ({}) };
    if (options.method === "PATCH") {
      Object.entries(body.settings).forEach(([name, value]) => {
        if (value === null) delete server.settings[name];
        else server.settings[name] = value;
      });
      server.revision += 1;
    }
    return { ok: true, status: 200, json: async () => ({ settings: { ...server.settings }, revision: server.revision }) };
  };
  server.hold = () => {
    let release;
    server.held = { promise: new Promise(resolve => { release = resolve; }) };
    server.release = () => { server.held = null; release(); };
  };
  server.patches = () => server.calls.filter(call => call.method === "PATCH").map(call => call.body.settings);
  return server;
}

function boot({ storage = {}, server = null } = {}) {
  const { window, dom } = loadScripts(["static/js/user-settings.js"], {
    before(win) {
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
    settings.set("check_sources", false);
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
      runMode: "compare",
      runModeDefault: "agent-2026-10-02",
      checkSources: "false",
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
    ["check_sources", "false"],
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

describe("migrations of older stored values", () => {
  it.each([
    [{ agentMode: "false", autoConsensus: "false" }, "compare"],
    [{ agentMode: "true" }, undefined],
    // Before 2026-10-02 every first visit stored "consensus" unasked.
    [{ runMode: "consensus" }, undefined],
    [{ runMode: "consensus", runModeDefault: "agent-2026-10-02" }, "consensus"],
    [{ runMode: "compare" }, "compare"],
    [{ runMode: "bogus" }, undefined],
  ])("reads the run mode of %o as %s", (storage, expected) => {
    const { settings, local } = open({ storage });
    expect(settings.get("run_mode")).toBe(expected);
    expect(local.getItem("runMode")).toBe(expected || null);
    expect(local.getItem("agentMode")).toBeNull();
    expect(local.getItem("autoConsensus")).toBeNull();
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
  ])("drops a built-in default the app once stored as the system prompt (%s)", prompt => {
    const { settings, local } = open({ storage: { systemPrompt: prompt } });
    expect(settings.get("system_prompt")).toBeUndefined();
    expect(local.getItem("systemPrompt")).toBeNull();
  });
});

describe("change events", () => {
  it("announce a change on this page once, with the previous value", () => {
    const { settings, events } = open({ storage: { checkSources: "false" } });
    expect(settings.set("check_sources", false)).toBe(false);
    settings.set("check_sources", true);
    expect(events).toEqual([{ names: ["check_sources"], source: "local", previous: { check_sources: false } }]);
  });

  it("follow another tab, but not a write that changes no value", () => {
    const { window, settings, events, local } = open({ storage: { runMode: "compare", runModeDefault: "agent-2026-10-02" } });
    const heard = vi.fn();
    settings.onChange("run_mode", heard);
    const tab = (key, value) => {
      local.setItem(key, value);
      window.dispatchEvent(new window.StorageEvent("storage", { key, newValue: value, storageArea: local }));
    };
    tab("runModeDefault", "agent-2026-10-02");
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
      runMode: "compare", runModeDefault: "agent-2026-10-02", pref_check_Grok: "false", systemPrompt: "Be brief.",
    } });
    expect(await start()).toBe(true);
    await settings.flush();
    expect(server.calls[0]).toMatchObject({ url: "/api/my/settings", method: "GET", auth: "Bearer token-uid-a" });
    expect(server.patches()).toEqual([{
      run_mode: "compare", compare_models: { Grok: { enabled: false } }, system_prompt: "Be brief.",
    }]);
    expect(record(local)).toEqual({ owner: UID, pending: [] });
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
      runMode: "compare", runModeDefault: "agent-2026-10-02", checkSources: "false",
      [SYNC_KEY]: JSON.stringify({ owner: UID, pending: [] }),
    } });
    await start();
    expect(settings.get("run_mode")).toBe("consensus");
    expect(settings.get("claim_counts")).toBe(true);
    // Not on the server: back to the default.
    expect(settings.get("check_sources")).toBeUndefined();
    expect(local.getItem("checkSources")).toBeNull();
    expect(events).toEqual([{
      names: ["run_mode", "check_sources", "claim_counts"], source: "server",
      previous: { run_mode: "compare", check_sources: false, claim_counts: undefined },
    }]);
    expect(server.patches()).toEqual([]);
  });

  it("keeps a change made before the account answered and sends it", async () => {
    const server = fakeServer({ settings: { run_mode: "agent", check_sources: false }, revision: 2 });
    const { settings, start } = open({ server });
    server.hold();
    const loading = start();
    settings.set("run_mode", "compare");
    server.release();
    await loading;
    await settings.flush();
    expect(settings.get("run_mode")).toBe("compare");
    expect(settings.get("check_sources")).toBe(false);
    expect(server.patches()).toEqual([{ run_mode: "compare" }]);
    expect(server.settings).toEqual({ run_mode: "compare", check_sources: false });
  });

  it("sends what an earlier page of this account could not deliver", async () => {
    const server = fakeServer({ settings: { run_mode: "agent" }, revision: 5 });
    const { settings, start } = open({ server, storage: {
      runMode: "compare", runModeDefault: "agent-2026-10-02",
      [SYNC_KEY]: JSON.stringify({ owner: UID, pending: ["run_mode", "unknown"] }),
    } });
    await start();
    await settings.flush();
    expect(settings.get("run_mode")).toBe("compare");
    expect(server.patches()).toEqual([{ run_mode: "compare" }]);
    expect(settings.status().pending).toEqual([]);
  });

  it("never gives one account another account's settings", async () => {
    const server = fakeServer();
    const { settings, start, local } = open({ server, storage: {
      runMode: "compare", runModeDefault: "agent-2026-10-02", systemPrompt: "Private to B.",
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
    expect(record(local)).toEqual({ owner: UID, pending: [] });
  });

  it("collects quick changes into one request", async () => {
    const server = fakeServer({ revision: 1 });
    const { settings, start } = open({ server });
    await start();
    settings.set("run_mode", "compare");
    settings.set("check_sources", false);
    settings.set("run_mode", "consensus");
    expect(server.patches()).toEqual([]);
    await vi.advanceTimersByTimeAsync(400);
    await settings.flush();
    expect(server.patches()).toEqual([{ run_mode: "consensus", check_sources: false }]);
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
    const { settings } = open({ storage: { runMode: "compare", runModeDefault: "agent-2026-10-02" } });
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
    settings.set("check_sources", false);
    window.dispatchEvent(new window.Event("pagehide"));
    await settings.flush();
    expect(server.calls.at(-1)).toMatchObject({ method: "PATCH", keepalive: true, body: { settings: { check_sources: false } } });
  });
});
