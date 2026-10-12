// =====================================================================
// user-settings.js
// Account settings: the choices that follow an account to every device --
// run mode, Agent model and preferences, Check sources, the Compare and
// Consensus models, the system prompt and three display options.
//
// The server keeps them per account (GET/PATCH /api/my/settings,
// app/services/user_settings.py). This browser keeps a copy under the
// localStorage keys listed below, so the first paint already matches and a
// guest keeps a choice as well. Modules read and write these settings ONLY
// through App.userSettings; the storage keys are this module's business.
// Theme, sidebar, drafts, the own OpenRouter key and seen hints stay in the
// browser on purpose and are not handled here.
//
// Sync rules (docs/codebase-map.md, "Kontoeinstellungen"):
//   * Once an account has saved settings, the server's values apply. A
//     change that has not reached the server yet -- made on this page before
//     the server answered, or kept from a page that went offline -- is sent
//     instead ("pending", stored per account across reloads).
//   * An account that never saved settings receives this browser's values
//     once, unless they belong to another account.
//   * Signing out removes the account's values from this browser.
//
// Loaded first in the render-blocking head bundle: run-mode.js reads it
// before the first paint. Legacy storage formats are migrated on read, here
// and nowhere else. No DOM access.
// Exports: window.App.userSettings
// Event:   "consensio:settings-change" on window,
//          detail {names, source, previous}; source is "local" (this page
//          changed it), "server", "tab" (another tab) or "signout".
// =====================================================================

(function () {
  "use strict";

  const EVENT = "consensio:settings-change";
  const ENDPOINT = "/api/my/settings";
  const SYNC_KEY = "consensio.settingsSync.v1";
  const FLUSH_DELAY_MS = 400;
  const RETRY_DELAYS_MS = [2000, 10000, 60000, 300000];

  // The same rules as app/services/user_settings.py (a test compares them):
  // a value the browser accepts is one the server stores.
  const MODEL_ID = /^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,159}$/;
  const FAMILY_LABEL = /^[A-Za-z0-9][A-Za-z0-9 ._-]{0,31}$/;
  const PRESET_ID = /^[a-z0-9][a-z0-9_-]{0,31}$/;
  const REASONING_EFFORT = /^(default|none|minimal|low|medium|high|xhigh|max)$/;
  const MAX_COMPARE_FAMILIES = 16;
  const MAX_SYSTEM_PROMPT_CHARS = 12000;
  const MAX_SYSTEM_PROMPT_BYTES = 32000;

  // ---- Storage --------------------------------------------------------------
  // localStorage, with an in-page overlay for values it refused (private
  // mode, blocked storage, a full quota): the choice then holds for this page.
  const overlay = new Map();

  function readKey(key) {
    if (overlay.has(key)) return overlay.get(key);
    try { return window.localStorage.getItem(key); } catch (_) { return null; }
  }

  function writeKey(key, value) {
    try {
      if (value === null) window.localStorage.removeItem(key);
      else window.localStorage.setItem(key, value);
      overlay.delete(key);
    } catch (_) {
      overlay.set(key, value);
    }
  }

  function storedKeys() {
    const keys = new Set();
    try {
      for (let index = 0; index < window.localStorage.length; index++) keys.add(window.localStorage.key(index));
    } catch (_) { /* only the overlay */ }
    overlay.forEach((value, key) => { if (value === null) keys.delete(key); else keys.add(key); });
    return Array.from(keys);
  }

  function parseJson(raw) {
    if (raw === null) return null;
    try { return JSON.parse(raw); } catch (_) { return null; }
  }

  function isPlainObject(value) {
    return Boolean(value) && typeof value === "object" && !Array.isArray(value);
  }

  // Order-independent comparison of stored values.
  function canonical(value) {
    if (Array.isArray(value)) return value.map(canonical);
    if (!isPlainObject(value)) return value === undefined ? null : value;
    const sorted = {};
    Object.keys(value).sort().forEach(key => { sorted[key] = canonical(value[key]); });
    return sorted;
  }

  function same(left, right) {
    return JSON.stringify(canonical(left)) === JSON.stringify(canonical(right));
  }

  // ---- Settings -------------------------------------------------------------
  // Each setting: read() -> value or undefined (not chosen), write(value or
  // null), normalize(input) -> value, null (back to the default) or
  // undefined (not a valid value), owns(key) -> whether a storage key is its.

  function keyed(keys, setting) {
    return Object.assign({ owns: key => keys.includes(key) }, setting);
  }

  function booleanSetting(key) {
    return keyed([key], {
      read() {
        const stored = readKey(key);
        return stored === "true" ? true : (stored === "false" ? false : undefined);
      },
      write(value) { writeKey(key, value === null ? null : String(value)); },
      normalize: value => (typeof value === "boolean" ? value : undefined),
    });
  }

  function patternSetting(key, pattern) {
    return keyed([key], {
      read() {
        const stored = readKey(key);
        return stored !== null && pattern.test(stored) ? stored : undefined;
      },
      write(value) { writeKey(key, value); },
      normalize: value => (typeof value === "string" && pattern.test(value) ? value : undefined),
    });
  }

  // run_mode ---------------------------------------------------------------
  const RUN_MODE_KEY = "runMode";
  const RUN_MODES = ["compare", "consensus", "agent"];

  const runMode = keyed([RUN_MODE_KEY], {
    read() {
      const stored = readKey(RUN_MODE_KEY);
      return RUN_MODES.includes(stored) ? stored : undefined;
    },
    write(value) { writeKey(RUN_MODE_KEY, value); },
    normalize: value => (RUN_MODES.includes(value) ? value : undefined),
  });

  // agent_preferences ------------------------------------------------------
  // Only the fields the user chose, so a later change of a default reaches
  // everyone who never touched that field.
  const AGENT_PREFERENCES_KEY = "consensio.agentPreferences.v2";
  // v1 stored every field whenever one changed; values equal to its
  // defaults were never chosen.
  const AGENT_PREFERENCES_LEGACY_KEY = "consensio.agentPreferences.v1";
  const AGENT_PREFERENCES_LEGACY_DEFAULTS = { depth: "auto", quorum: "balanced", autonomy: "guided" };
  const AGENT_CHOICES = {
    depth: ["auto", "quick", "full"],
    quorum: ["balanced", "fast", "all"],
    autonomy: ["guided", "free"],
  };

  function chosenAgentPreferences(value, unchosen) {
    if (!isPlainObject(value)) return null;
    const chosen = {};
    Object.keys(AGENT_CHOICES).forEach(field => {
      if (AGENT_CHOICES[field].includes(value[field]) && value[field] !== unchosen?.[field]) chosen[field] = value[field];
    });
    return Object.keys(chosen).length ? chosen : null;
  }

  const agentPreferences = keyed([AGENT_PREFERENCES_KEY, AGENT_PREFERENCES_LEGACY_KEY], {
    read() {
      const current = readKey(AGENT_PREFERENCES_KEY);
      if (current !== null) return chosenAgentPreferences(parseJson(current)) || undefined;
      const legacy = readKey(AGENT_PREFERENCES_LEGACY_KEY);
      if (legacy === null) return undefined;
      const chosen = chosenAgentPreferences(parseJson(legacy), AGENT_PREFERENCES_LEGACY_DEFAULTS);
      if (chosen) writeKey(AGENT_PREFERENCES_KEY, JSON.stringify(chosen));
      writeKey(AGENT_PREFERENCES_LEGACY_KEY, null);
      return chosen || undefined;
    },
    write(value) { writeKey(AGENT_PREFERENCES_KEY, value === null ? null : JSON.stringify(value)); },
    normalize(value) {
      if (!isPlainObject(value)) return undefined;
      const unknown = Object.keys(value).some(field => !Object.prototype.hasOwnProperty.call(AGENT_CHOICES, field)
        || (value[field] !== null && value[field] !== undefined && !AGENT_CHOICES[field].includes(value[field])));
      return unknown ? undefined : chosenAgentPreferences(value);
    },
  });

  // agent_model ------------------------------------------------------------
  const AGENT_MODEL_KEY = "consensio.agentModel.v1";
  // Until 2026-10-12 the pick was kept per account: agent_settings_<uid>.
  const AGENT_MODEL_LEGACY_PREFIX = "agent_settings_";

  // The model is the pick; a level the app no longer knows falls back to
  // the model's own default instead of dropping the pick.
  function agentModelValue(value) {
    if (!isPlainObject(value) || typeof value.model_id !== "string" || !MODEL_ID.test(value.model_id)) return undefined;
    const effort = typeof value.reasoning_effort === "string" && REASONING_EFFORT.test(value.reasoning_effort)
      ? value.reasoning_effort : "default";
    return { model_id: value.model_id, reasoning_effort: effort };
  }

  const agentModel = keyed([AGENT_MODEL_KEY], {
    read: () => agentModelValue(parseJson(readKey(AGENT_MODEL_KEY))),
    write(value) { writeKey(AGENT_MODEL_KEY, value === null ? null : JSON.stringify(value)); },
    normalize: agentModelValue,
  });

  // compare_models ---------------------------------------------------------
  // Per family label (OpenAI, Gemini, ...): included or not, and the model.
  const FAMILY_CHECK_PREFIX = "pref_check_";
  const FAMILY_SELECT_PREFIX = "pref_select_";
  const CONSENSUS_MODEL_KEY = "pref_select_consensus";
  const CONSENSUS_PRESET_KEY = "pref_consensus_preset";

  function familyKey(key) {
    if (key === CONSENSUS_MODEL_KEY) return null;
    if (key.startsWith(FAMILY_CHECK_PREFIX)) return { field: "enabled", label: key.slice(FAMILY_CHECK_PREFIX.length) };
    if (key.startsWith(FAMILY_SELECT_PREFIX)) return { field: "model", label: key.slice(FAMILY_SELECT_PREFIX.length) };
    return null;
  }

  function compareFamilies(value) {
    if (!isPlainObject(value)) return undefined;
    const labels = Object.keys(value);
    if (labels.length > MAX_COMPARE_FAMILIES) return undefined;
    const families = {};
    for (const label of labels) {
      const family = value[label];
      if (!FAMILY_LABEL.test(label) || !isPlainObject(family)) return undefined;
      if (Object.keys(family).some(field => field !== "enabled" && field !== "model")) return undefined;
      const clean = {};
      if (family.enabled !== undefined && family.enabled !== null) {
        if (typeof family.enabled !== "boolean") return undefined;
        clean.enabled = family.enabled;
      }
      if (family.model !== undefined && family.model !== null) {
        if (typeof family.model !== "string" || !MODEL_ID.test(family.model)) return undefined;
        clean.model = family.model;
      }
      if (Object.keys(clean).length) families[label] = clean;
    }
    return Object.keys(families).length ? families : null;
  }

  const compareModels = {
    owns: key => familyKey(key) !== null,
    read() {
      const families = {};
      storedKeys().forEach(key => {
        const parsed = familyKey(key);
        if (!parsed || !FAMILY_LABEL.test(parsed.label)) return;
        const stored = readKey(key);
        let value;
        if (parsed.field === "enabled" && (stored === "true" || stored === "false")) value = stored === "true";
        else if (parsed.field === "model" && stored !== null && MODEL_ID.test(stored)) value = stored;
        else return;
        families[parsed.label] = Object.assign(families[parsed.label] || {}, { [parsed.field]: value });
      });
      return Object.keys(families).length ? families : undefined;
    },
    write(value) {
      const wanted = new Map();
      Object.entries(value || {}).forEach(([label, family]) => {
        if (typeof family.enabled === "boolean") wanted.set(FAMILY_CHECK_PREFIX + label, String(family.enabled));
        if (family.model) wanted.set(FAMILY_SELECT_PREFIX + label, family.model);
      });
      storedKeys().forEach(key => { if (familyKey(key) && !wanted.has(key)) writeKey(key, null); });
      wanted.forEach((stored, key) => { if (readKey(key) !== stored) writeKey(key, stored); });
    },
    normalize: compareFamilies,
  };

  // system_prompt ----------------------------------------------------------
  const SYSTEM_PROMPT_KEY = "systemPrompt";
  // Built-in defaults the app once wrote itself. They are not a choice: the
  // server's configured prompt applies instead.
  const SYSTEM_PROMPT_LEGACY_DEFAULTS = [
    "Please answer thoroughly and precisely, explaining your reasoning and covering the relevant details. Do not oversimplify. Do not ask any follow-up or clarifying questions; answer directly with the information available.",
    "Please respond briefly and precisely, focusing only on the essentials.",
    "Please respond briefly and precisely, focusing only on the essentials. No follow-up questions.",
    "Please answer thoroughly and precisely, explaining your reasoning and covering the relevant details. Do not oversimplify.",
  ];

  function utf8Length(text) {
    let bytes = 0;
    for (const char of text) {
      const code = char.codePointAt(0);
      bytes += code < 0x80 ? 1 : (code < 0x800 ? 2 : (code < 0x10000 ? 3 : 4));
    }
    return bytes;
  }

  function systemPromptValue(value) {
    if (typeof value !== "string") return undefined;
    const text = value.trim();
    if (!text) return null;
    if (text.length > MAX_SYSTEM_PROMPT_CHARS || utf8Length(text) > MAX_SYSTEM_PROMPT_BYTES) return undefined;
    return text;
  }

  const systemPrompt = keyed([SYSTEM_PROMPT_KEY], {
    read() {
      const stored = readKey(SYSTEM_PROMPT_KEY);
      if (stored === null) return undefined;
      const text = systemPromptValue(stored);
      if (typeof text === "string" && !SYSTEM_PROMPT_LEGACY_DEFAULTS.includes(text)) return text;
      writeKey(SYSTEM_PROMPT_KEY, null);
      return undefined;
    },
    write(value) { writeKey(SYSTEM_PROMPT_KEY, value); },
    normalize: systemPromptValue,
  });

  // agreement_display ------------------------------------------------------
  const AGREEMENT_DISPLAY_KEY = "consensio.agreementDisplay.v1";
  // Its predecessor, a switch: "false" is the "summary" level.
  const AGREEMENT_SCORE_LEGACY_KEY = "consensio.showAgreementScore.v1";
  const AGREEMENT_DISPLAY_MODES = ["full", "summary", "off"];

  const agreementDisplay = keyed([AGREEMENT_DISPLAY_KEY, AGREEMENT_SCORE_LEGACY_KEY], {
    read() {
      const stored = readKey(AGREEMENT_DISPLAY_KEY);
      const legacy = readKey(AGREEMENT_SCORE_LEGACY_KEY);
      if (legacy !== null) {
        writeKey(AGREEMENT_SCORE_LEGACY_KEY, null);
        if (!AGREEMENT_DISPLAY_MODES.includes(stored) && legacy === "false") {
          writeKey(AGREEMENT_DISPLAY_KEY, "summary");
          return "summary";
        }
      }
      return AGREEMENT_DISPLAY_MODES.includes(stored) ? stored : undefined;
    },
    write(value) { writeKey(AGREEMENT_DISPLAY_KEY, value); },
    normalize: value => (AGREEMENT_DISPLAY_MODES.includes(value) ? value : undefined),
  });

  // consensus_highlights ---------------------------------------------------
  // One choice in the UI, two keys in storage: hidden, or which checks.
  const MARKERS_VISIBLE_KEY = "consensio.showConsensusMarkers.v1";
  const HIGHLIGHT_MODE_KEY = "consensio.consensusHighlightMode.v1";
  const HIGHLIGHT_FILTERS = ["all", "contradictions", "concerns", "critical"];

  const consensusHighlights = keyed([MARKERS_VISIBLE_KEY, HIGHLIGHT_MODE_KEY], {
    read() {
      if (readKey(MARKERS_VISIBLE_KEY) === "false") return "none";
      const mode = readKey(HIGHLIGHT_MODE_KEY);
      return HIGHLIGHT_FILTERS.includes(mode) ? mode : undefined;
    },
    write(value) {
      writeKey(MARKERS_VISIBLE_KEY, value === null ? null : String(value !== "none"));
      writeKey(HIGHLIGHT_MODE_KEY, value === null || value === "none" ? null : value);
    },
    normalize: value => (value === "none" || HIGHLIGHT_FILTERS.includes(value) ? value : undefined),
  });

  const DEFINITIONS = Object.freeze({
    run_mode: runMode,
    agent_model: agentModel,
    agent_preferences: agentPreferences,
    check_sources: booleanSetting("checkSources"),
    compare_models: compareModels,
    consensus_model: patternSetting(CONSENSUS_MODEL_KEY, MODEL_ID),
    consensus_preset: patternSetting(CONSENSUS_PRESET_KEY, PRESET_ID),
    system_prompt: systemPrompt,
    agreement_display: agreementDisplay,
    consensus_highlights: consensusHighlights,
    claim_counts: booleanSetting("consensio.showClaimCounts.v1"),
  });
  const NAMES = Object.freeze(Object.keys(DEFINITIONS));

  function definition(name) {
    const found = Object.prototype.hasOwnProperty.call(DEFINITIONS, name) ? DEFINITIONS[name] : null;
    if (!found) throw new Error("Unknown account setting: " + name);
    return found;
  }

  // ---- Sync state ----------------------------------------------------------
  let session = null;       // {uid, getToken, loaded, foreign, ready}
  const touched = new Set(); // changed on this page before its account answered
  let flushTimer = null;
  let retryTimer = null;
  let retryAttempt = 0;
  let inflight = null;

  // ---- One-time reset (2026-10-12) ------------------------------------------
  // With the move to account settings every browser starts once from the
  // defaults for the mode (Agent) and the models (the app's default preset,
  // Daily): stored Compare choices and lineups from earlier versions held
  // retired model IDs and would otherwise be uploaded to the account. Choices
  // made after the reset stay. The keys listed here are the run mode, its
  // earlier forms and marks, and the Compare/Consensus model choice.
  const RESET_KEY = "consensio.settingsReset";
  const RESET_MARK = "2026-10-12";
  const RESET_KEYS = [RUN_MODE_KEY, "runModeDefault", "agentMode", "autoConsensus",
    CONSENSUS_MODEL_KEY, CONSENSUS_PRESET_KEY];

  function resetOnce() {
    if (readKey(RESET_KEY) === RESET_MARK) return;
    storedKeys().forEach(key => {
      if (RESET_KEYS.includes(key) || familyKey(key)) writeKey(key, null);
    });
    writeKey(RESET_KEY, RESET_MARK);
  }
  resetOnce();

  // ---- What this page last saw, and change events --------------------------
  // Reading every setting once here also runs the legacy migrations before
  // any module asks.
  const known = new Map(NAMES.map(name => [name, canonical(DEFINITIONS[name].read())]));

  function refresh(names, source) {
    const changed = [];
    const previous = {};
    names.forEach(name => {
      const value = canonical(DEFINITIONS[name].read());
      if (same(value, known.get(name))) return;
      previous[name] = known.get(name) === null ? undefined : known.get(name);
      known.set(name, value);
      changed.push(name);
    });
    if (changed.length) {
      window.dispatchEvent(new CustomEvent(EVENT, { detail: { names: changed, source, previous } }));
    }
    return changed;
  }

  function get(name) {
    return definition(name).read();
  }

  // Whether set() would take this value (null or undefined: the default).
  function accepts(name, value) {
    return value === null || value === undefined || definition(name).normalize(value) !== undefined;
  }

  // A change the user made on this page. null or undefined: back to the default.
  function set(name, value) {
    const setting = definition(name);
    const next = value === null || value === undefined ? null : setting.normalize(value);
    if (next === undefined) {
      console.warn(`Ignored an invalid value for the setting "${name}".`);
      return false;
    }
    if (same(setting.read(), next)) return false;
    setting.write(next);
    touched.add(name);
    if (session) addPending([name]);
    refresh([name], "local");
    scheduleFlush();
    return true;
  }

  function onChange(names, handler) {
    const wanted = Array.isArray(names) ? names : [names];
    wanted.forEach(definition);
    const listener = event => {
      if (event.detail.names.some(name => wanted.includes(name))) handler(event.detail);
    };
    window.addEventListener(EVENT, listener);
    return () => window.removeEventListener(EVENT, listener);
  }

  // Another tab wrote one of the keys: storage is shared, the event is not.
  window.addEventListener("storage", event => {
    let shared = false;
    try { shared = event.storageArea === window.localStorage; } catch (_) { /* storage blocked */ }
    if (!shared || event.key === SYNC_KEY) return;
    const names = event.key === null ? NAMES : NAMES.filter(name => DEFINITIONS[name].owns(event.key));
    if (names.length) refresh(names, "tab");
  });

  // ---- Sync with the account -------------------------------------------------
  function syncRecord() {
    const raw = parseJson(readKey(SYNC_KEY));
    return {
      owner: isPlainObject(raw) && typeof raw.owner === "string" && raw.owner ? raw.owner : null,
      pending: isPlainObject(raw) && Array.isArray(raw.pending) ? raw.pending.filter(name => NAMES.includes(name)) : [],
    };
  }

  function saveSyncRecord(owner, pending) {
    writeKey(SYNC_KEY, JSON.stringify({ owner, pending: Array.from(new Set(pending)) }));
  }

  function addPending(names) {
    const record = syncRecord();
    const pending = record.owner === session.uid ? record.pending : [];
    saveSyncRecord(session.uid, pending.concat(names));
  }

  function isCurrent(candidate) {
    return session !== null && session === candidate;
  }

  async function request(candidate, method, body, keepalive) {
    const token = await candidate.getToken();
    if (!isCurrent(candidate)) throw Object.assign(new Error("The account changed."), { stale: true });
    const headers = { "Authorization": "Bearer " + token };
    if (body) headers["Content-Type"] = "application/json";
    const response = await fetch(ENDPOINT, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
      cache: "no-store",
      keepalive: keepalive === true,
    });
    if (response.ok) return response.json();
    // A token that expired, a rate limit and a server fault pass; anything
    // else (a refused value, an account being deleted) will not on retry.
    const status = response.status;
    throw Object.assign(new Error(`Settings request failed (${status})`), {
      permanent: status !== 401 && status !== 408 && status !== 429 && status < 500,
    });
  }

  function scheduleRetry(candidate, action) {
    clearTimeout(retryTimer);
    const delay = RETRY_DELAYS_MS[Math.min(retryAttempt, RETRY_DELAYS_MS.length - 1)];
    retryAttempt += 1;
    retryTimer = setTimeout(() => {
      retryTimer = null;
      if (isCurrent(candidate)) action(candidate);
    }, delay);
  }

  function apply(name, value) {
    const setting = DEFINITIONS[name];
    const next = value === null || value === undefined ? null : setting.normalize(value);
    if (!same(setting.read(), next === undefined ? null : next)) setting.write(next === undefined ? null : next);
  }

  async function load(candidate) {
    let data;
    try {
      data = await request(candidate, "GET");
    } catch (error) {
      if (isCurrent(candidate) && !error.stale && !error.permanent) scheduleRetry(candidate, load);
      return false;
    }
    if (!isCurrent(candidate)) return false;
    retryAttempt = 0;
    const revision = Number(data?.revision) || 0;
    const server = isPlainObject(data?.settings) ? data.settings : {};
    const record = syncRecord();
    const pending = new Set(record.owner === candidate.uid ? record.pending : []);
    touched.forEach(name => pending.add(name));
    const legacyAgentModelKey = AGENT_MODEL_LEGACY_PREFIX + candidate.uid;
    const legacyAgentModel = agentModelValue(parseJson(readKey(legacyAgentModelKey)));
    writeKey(legacyAgentModelKey, null);

    if (revision > 0) {
      NAMES.forEach(name => { if (!pending.has(name)) apply(name, server[name]); });
    } else {
      // This account never saved settings: what this browser chose so far
      // becomes the account's -- unless it was another account's choice.
      if (candidate.foreign) NAMES.forEach(name => { if (!pending.has(name)) apply(name, null); });
      if (legacyAgentModel && agentModel.read() === undefined) agentModel.write(legacyAgentModel);
      NAMES.forEach(name => { if (DEFINITIONS[name].read() !== undefined) pending.add(name); });
    }
    saveSyncRecord(candidate.uid, Array.from(pending));
    touched.clear();
    candidate.loaded = true;
    refresh(NAMES, "server");
    flush();
    return true;
  }

  function scheduleFlush() {
    if (!session?.loaded) return;
    clearTimeout(flushTimer);
    flushTimer = setTimeout(() => { flushTimer = null; flush(); }, FLUSH_DELAY_MS);
  }

  // Send pending changes now. keepalive lets the request outlive the page;
  // timeoutMs stops the wait (not the request) for a caller that cannot wait
  // longer, such as the logout.
  function flush(options = {}) {
    const sending = send(options);
    if (!options.timeoutMs) return sending;
    return Promise.race([sending, new Promise(resolve => setTimeout(() => resolve(false), options.timeoutMs))]);
  }

  function send(options) {
    clearTimeout(flushTimer);
    flushTimer = null;
    const candidate = session;
    if (!candidate?.loaded) return Promise.resolve(false);
    // One request at a time; what changed meanwhile goes in the next one.
    if (inflight) return inflight.then(() => send(options));
    const record = syncRecord();
    if (record.owner !== candidate.uid || !record.pending.length) return Promise.resolve(true);
    const names = record.pending;
    const sent = {};
    names.forEach(name => {
      const value = DEFINITIONS[name].read();
      sent[name] = value === undefined ? null : value;
    });
    // Sent values leave the pending list unless they changed in between.
    const settle = () => {
      const latest = syncRecord();
      if (latest.owner !== candidate.uid) return;
      saveSyncRecord(candidate.uid, latest.pending.filter(name => !(name in sent)
        || !same(DEFINITIONS[name].read(), sent[name])));
    };
    inflight = request(candidate, "PATCH", { settings: sent }, options.keepalive)
      .then(() => {
        if (!isCurrent(candidate)) return false;
        retryAttempt = 0;
        settle();
        return true;
      }, error => {
        if (!isCurrent(candidate) || error.stale) return false;
        if (error.permanent) {
          console.warn("Settings were not saved to the account:", error.message);
          settle();
        } else {
          scheduleRetry(candidate, () => flush());
        }
        return false;
      })
      .finally(() => {
        inflight = null;
        // Changes made meanwhile, or by the account that took over this page.
        if (session?.loaded && !retryTimer && syncRecord().pending.length) scheduleFlush();
      });
    return inflight;
  }

  // The signed-in, verified account of this page (firebase.js). getToken
  // returns a fresh ID token.
  function start(options) {
    const uid = options?.uid;
    const getToken = options?.getToken;
    if (typeof uid !== "string" || !uid || typeof getToken !== "function") return Promise.resolve(false);
    if (session?.uid === uid) {
      session.getToken = getToken;
      return session.ready;
    }
    clearTimers();
    const record = syncRecord();
    session = { uid, getToken, loaded: false, foreign: record.owner !== null && record.owner !== uid };
    session.ready = load(session);
    return session.ready;
  }

  // Signed out: the account's values leave this browser. A guest's own
  // values (never synced) stay.
  function stop() {
    clearTimers();
    session = null;
    touched.clear();
    if (syncRecord().owner === null) return;
    NAMES.forEach(name => DEFINITIONS[name].write(null));
    writeKey(SYNC_KEY, null);
    refresh(NAMES, "signout");
  }

  function clearTimers() {
    clearTimeout(flushTimer);
    clearTimeout(retryTimer);
    flushTimer = null;
    retryTimer = null;
    retryAttempt = 0;
  }

  // Best effort when the page goes away; whatever does not arrive stays
  // pending and is sent on the next visit.
  window.addEventListener("pagehide", () => { flush({ keepalive: true }); });
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") flush({ keepalive: true });
  });
  window.addEventListener("online", () => {
    if (!session) return;
    clearTimeout(retryTimer);
    retryTimer = null;
    if (session.loaded) flush();
    else load(session);
  });

  window.App = window.App || {};
  window.App.userSettings = Object.freeze({
    EVENT,
    NAMES,
    get,
    set,
    accepts,
    onChange,
    start,
    stop,
    flush,
    status: () => ({
      uid: session?.uid || null,
      loaded: session?.loaded === true,
      pending: session ? syncRecord().pending : [],
    }),
  });
})();
