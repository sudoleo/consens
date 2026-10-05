(function () {
  const config = document.getElementById("appBootstrapConfig");
  const parse = (name, fallback) => {
    try { return JSON.parse(config?.dataset?.[name] || ""); }
    catch (_) { return fallback; }
  };
  window.FIREBASE_CONFIG = {
    apiKey: config?.dataset.firebaseApiKey || "",
    authDomain: config?.dataset.firebaseAuthDomain || "",
    projectId: config?.dataset.firebaseProjectId || "",
    storageBucket: config?.dataset.firebaseStorageBucket || "",
    messagingSenderId: config?.dataset.firebaseMessagingSenderId || "",
    appId: config?.dataset.firebaseAppId || ""
  };
  window.APP_LIMITS = parse("limits", {});
  window.FREE_DEFAULT_MODELS = parse("freeModels", {});
  window.PRO_DEFAULT_MODELS = parse("proModels", {});
  window.CONSENSUS_PRESETS = parse("consensusPresets", []);
  window.DEFAULT_CONSENSUS_PRESET = parse("defaultConsensusPreset", "");
  // Die eine Familienliste der App: Antwortboxen, Picker, Sendepfad und
  // Fortschritt lesen ausschliesslich hieraus (Server = cfg.PROVIDERS).
  window.MODEL_FAMILIES = parse("modelFamilies", []);
  window.MAX_RUN_FAMILIES = Number(config?.dataset.maxRunFamilies || 6);

  window.trackUmamiEvent = function (eventName, eventData = {}) {
    if (!eventName || !window.umami || typeof window.umami.track !== "function") return;
    const blocked = /(email|mail|token|key|prompt|question|message|response|answer|password)/i;
    const safeData = {};
    Object.entries(eventData || {}).forEach(([key, value]) => {
      if (!key || blocked.test(key) || value == null) return;
      if (typeof value === "boolean" || (typeof value === "number" && Number.isFinite(value))) {
        safeData[key] = value;
      } else if (typeof value === "string") {
        const trimmed = value.trim();
        if (trimmed && trimmed.length <= 120 && !trimmed.includes("@")) safeData[key] = trimmed;
      }
    });
    window.umami.track(eventName, safeData);
  };

  // Agent hides the sidebar's Models row, but only knows it may after
  // /user_status. A signed-in reload that ended in Agent hides it from the
  // first paint (agent-chat.js keeps the hint and drops the class), so the
  // bookmark list below does not jump up once auth resolves.
  try {
    if (localStorage.getItem("id_token") && localStorage.getItem("agentShellExpected") === "1") {
      document.documentElement.classList.add("agent-shell-expected");
      setTimeout(() => document.documentElement.classList.remove("agent-shell-expected"), 10000);
    }
  } catch (_) { /* storage unavailable */ }

  document.addEventListener("DOMContentLoaded", () => {
    // The consensus view is painted before auth resolves; run-mode.js
    // (earlier in this bundle) owns the stored choice.
    if (window.App?.runMode?.preference() !== "compare") {
      document.body.classList.add("agent-mode-enabled");
    }
    const authTopActions = document.getElementById("authTopActions");
    const authState = window.__consensioAuthState;
    if (authTopActions && !(authState?.known && authState.uid)) {
      authTopActions.hidden = false;
    }
    try {
      if (document.documentElement.dataset.authUnavailable === "true") return;
      // A resolved session owns the UI; a cached token must not overwrite it.
      if (authState?.known) return;
      if (!localStorage.getItem("id_token")) return;
      const bookmarks = document.getElementById("bookmarksContainer");
      if (bookmarks) {
        bookmarks.innerHTML = '<div class="skeleton-group bookmarks-skeleton" role="status" aria-label="Loading chats">'
          + '<div class="skeleton-bookmark" aria-hidden="true"><span class="skeleton"></span></div>'.repeat(4)
          + '</div>';
      }
      const login = document.getElementById("loginContainer");
      if (login) {
        login.hidden = false;
        login.innerHTML = '<span class="skeleton-group" role="status" aria-label="Loading account"><span class="skeleton login-skeleton" aria-hidden="true"></span></span>';
      }
    } catch (_) { /* best-effort first paint */ }
  });
})();
