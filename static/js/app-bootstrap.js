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

  // First-paint state. DOMContentLoaded waits for the deferred bundles (and
  // the Firebase CDN modules before them), so the browser usually paints the
  // bare template first; everything set only then slid or swapped into place
  // in front of the reader: the stored collapsed sidebar animated shut, the
  // auth buttons blinked for signed-in users. A MutationObserver runs
  // between parsing and painting, so each element gets its state as soon as
  // it exists. CSP forbids an inline script in the body for the same job.
  let token = null;
  try { token = localStorage.getItem("id_token"); } catch (_) { /* storage unavailable */ }
  const seeded = new Set();
  function seed() {
    if (!seeded.has("body") && document.body) {
      seeded.add("body");
      // The consensus view is painted before auth resolves; run-mode.js
      // (earlier in this bundle) owns the stored choice.
      if (window.App?.runMode?.preference() !== "compare") {
        document.body.classList.add("agent-mode-enabled");
      }
    }
    const sidebar = !seeded.has("sidebar") && document.getElementById("appSidebar");
    if (sidebar) {
      seeded.add("sidebar");
      // Same rule as checkWindowSize() in app-init.js, which keeps it later.
      const overlay = window.matchMedia("(max-width: 1099px)").matches;
      let collapsed = overlay;
      try { collapsed = overlay || localStorage.getItem("sidebar_collapsed") === "true"; } catch (_) { /* storage unavailable */ }
      sidebar.classList.toggle("collapsed", collapsed);
    }
    const authTopActions = !seeded.has("auth") && document.getElementById("authTopActions");
    if (authTopActions) {
      seeded.add("auth");
      // Guests only. A stored token means a session is being restored:
      // firebase.js shows the buttons if it turns out to be a guest after all.
      const authState = window.__consensioAuthState;
      if (authState?.known ? !authState.uid : !token) authTopActions.hidden = false;
    }
    // A reload that ended in Agent starts with Agent's words (agent-chat.js
    // keeps them until access is known): the consensus wording swapped in
    // front of the reader once /user_status answered, and the greeting
    // changed size with it.
    if (document.documentElement.classList.contains("agent-shell-expected")) {
      const greeting = !seeded.has("greeting") && document.querySelector(".hero-greeting");
      if (greeting) {
        seeded.add("greeting");
        greeting.dataset.consensusGreeting = greeting.textContent;
        greeting.textContent = "What can I help you with?";
      }
      const newChat = !seeded.has("newChat") && document.getElementById("newRunButton");
      const newChatText = newChat?.querySelector("span");
      if (newChatText) {
        seeded.add("newChat");
        newChatText.textContent = "New chat";
        newChat.title = "Start a new chat";
      }
    } else {
      seeded.add("greeting");
      seeded.add("newChat");
    }
    return seeded.size === 5;
  }
  if (!seed() && typeof MutationObserver === "function") {
    const observer = new MutationObserver(() => { if (seed()) observer.disconnect(); });
    observer.observe(document.documentElement, { childList: true, subtree: true });
    document.addEventListener("DOMContentLoaded", () => observer.disconnect(), { once: true });
  }

  document.addEventListener("DOMContentLoaded", () => {
    seed();
    const authState = window.__consensioAuthState;
    try {
      if (document.documentElement.dataset.authUnavailable === "true") return;
      // A resolved session owns the UI; a cached token must not overwrite it.
      if (authState?.known) return;
      if (!token) return;
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
