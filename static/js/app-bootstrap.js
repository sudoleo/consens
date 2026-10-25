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
  // Gmail & Calendar and Drive as every account has them (pages.py): only
  // then does a guest's (+) menu show them (agent-google.js, agent-drive.js).
  window.GOOGLE_FOR_EVERYONE = parse("googleForEveryone", {});

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

  // The words of an empty new chat, for every account and for guests: they
  // name the one thing nobody would guess, that a pasted AI answer gets
  // checked. One length per width (agent-chat.js follows a rotated phone).
  window.App = window.App || {};
  window.App.askPlaceholder = function (width = window.innerWidth || 1024) {
    return width <= 360 ? "Ask or check an AI answer"
      : width <= 640 ? "Ask, or paste an AI answer to check" : "Ask anything, or paste an AI answer to check it";
  };

  function read(key, store = "localStorage") {
    try { return window[store].getItem(key); } catch (_) { return null; }
  }
  function readJSON(key) {
    try { return JSON.parse(read(key) || "null"); } catch (_) { return null; }
  }
  // The account a stored ID token names (its payload, unverified: only to
  // match remembered first-frame values to their account).
  function tokenUid(value) {
    try {
      const part = String(value || "").split(".")[1] || "";
      const payload = JSON.parse(window.atob(part.replace(/-/g, "+").replace(/_/g, "/")));
      const uid = payload.user_id || payload.sub;
      return typeof uid === "string" && uid ? uid : null;
    } catch (_) { return null; }
  }

  // ---- The session this page expects (Apple-Audit B4) ----------------------
  // Firebase answers only once its CDN modules ran, long after the first
  // paint. Until then this is the page's best knowledge, taken once from what
  // this browser stored: our ID token, the user Firebase keeps in
  // localStorage (firebase.js sets browserLocalPersistence) or a Google
  // sign-in on its way back from the redirect. Painting a guest first and
  // the account a second later showed two apps in one second. Once Firebase
  // has answered, the answer counts.
  const expected = (() => {
    const apiKey = config?.dataset.firebaseApiKey || "";
    const stored = readJSON(`firebase:authUser:${apiKey}:[DEFAULT]`);
    const user = stored && typeof stored.uid === "string" && stored.uid ? stored : null;
    const idToken = read("id_token");
    const redirect = read("consensio.googleRedirectPending", "sessionStorage") === "1";
    const verified = Boolean(idToken || redirect || (user && user.emailVerified !== false));
    return Object.freeze({
      account: Boolean(idToken || redirect || user),
      verified,
      uid: (user && user.uid) || tokenUid(idToken),
    });
  })();
  window.App.expectedSession = function () {
    const state = window.__consensioAuthState;
    if (state?.known) return { known: true, account: Boolean(state.uid), verified: Boolean(state.uid), uid: state.uid || null };
    if (document.documentElement.dataset.authUnavailable === "true") return { known: false, account: false, verified: false, uid: null };
    return { known: false, account: expected.account, verified: expected.verified, uid: expected.uid };
  };
  const guestExpected = () => !window.App.expectedSession().account;
  // A guest: nobody signed in or expected, and a login that can load (a page
  // whose login cannot load has nobody who could send, auth-bootstrap.js).
  // An unconfirmed sign-in is an account. The one rule for the first frame
  // and the app (app-init.js isGuestComposer, agent-chat.js, model-picker.js).
  window.App.isGuest = function () {
    if (window.auth?.currentUser) return false;
    if (document.documentElement.dataset.authUnavailable === "true") return false;
    return !window.App.expectedSession().account;
  };

  // Agent is open to every signed-in account (agent.py require_agent_access)
  // and the default mode, so a verified session expects Agent unless its
  // account chose another mode or this browser saw it without Agent access
  // ("agentShellExpected" is "0", written by agent-chat.js once access is
  // known). html.agent-shell-expected holds Agent's look until then
  // (agent-chat.js drops it); a failed status check keeps it while it asks
  // again (firebase.js, Apple-Audit B8). A guest sees Agent's composer of a
  // new chat as an account does by default (Max, Apple-Audit H3) and logs in
  // on Send (composer-invite.js); a guest's own choice of mode holds.
  window.App.expectsAgent = function () {
    const session = window.App.expectedSession();
    if ((window.App.runMode?.preference?.() || "agent") !== "agent") return false;
    if (window.App.isGuest()) return true;
    if (!session.verified) return false;
    return read("agentShellExpected") !== "0";
  };
  if (window.App.expectsAgent()) document.documentElement.classList.add("agent-shell-expected");
  // No session is coming (auth-bootstrap.js): the signed-out page it shows
  // has no Agent.
  window.addEventListener("consensio:auth-unavailable", () => {
    document.documentElement.classList.remove("agent-shell-expected");
  });

  // ---- What the composer said when the page was left (Apple-Audit B1) -----
  // The composer's chips are drawn by the deferred app bundle once the model
  // list has loaded; until then the template's placeholders stood there and
  // the field changed its face five times in a second. The words on screen
  // when the page was left (pagehide) are kept per account, and the first
  // frame paints them; the modules then draw the same.
  const LOOK_KEY = "consensio.firstFrame.v1";
  function rememberedLook() {
    const look = readJSON(LOOK_KEY);
    if (!look || typeof look !== "object") return null;
    const session = window.App.expectedSession();
    const owner = session.account ? session.uid : "";
    // A record of another account (or of a guest after a sign-in) stays unused.
    if (typeof look.uid !== "string" || (owner !== null && look.uid !== owner)) return null;
    return look;
  }
  function text(node) {
    return String(node?.textContent || "").replace(/\s+/g, " ").trim().slice(0, 80);
  }
  function rememberLook() {
    const state = window.__consensioAuthState;
    if (!state?.known) return;
    const agent = document.getElementById("agentModelDropdown");
    const look = { uid: state.uid || "", at: Date.now() };
    // Only words drawn from the loaded model list, never its placeholder.
    // The chip itself says what the comparison models do, so the chat
    // model's name comes from its select.
    if (agent?.dataset.catalog === "ready") {
      look.agentModel = text(agent.selectedOptions?.[0]);
      look.agentEffort = text(document.getElementById("agentReasoningEffort")?.selectedOptions?.[0]);
    }
    try { window.localStorage.setItem(LOOK_KEY, JSON.stringify(look)); } catch (_) { /* private mode */ }
  }
  window.App.firstFrame = Object.freeze({
    look: rememberedLook,
    remember: rememberLook,
    // The chat model's name while the model list loads (agent-chat.js).
    agentModel: () => rememberedLook()?.agentModel || config?.dataset.agentDefaultLabel || "Loading models…",
    agentEffort: () => rememberedLook()?.agentEffort || "",
    forget() { try { window.localStorage.removeItem(LOOK_KEY); } catch (_) { /* private mode */ } },
  });
  window.addEventListener("pagehide", rememberLook);
  document.addEventListener("visibilitychange", () => { if (document.hidden) rememberLook(); });

  // ---- The question waiting in the field (Apple-Audit B6) ------------------
  // Same record as app-init.js (QUESTION_DRAFT_KEY): a guest's question that
  // waits for the sign-in stands in the field from the first frame instead of
  // arriving with the app bundle.
  function waitingDraft() {
    const stored = read("consensio.questionDraft.v1") || "";
    let draft = null;
    try { draft = JSON.parse(stored); } catch (_) { /* a plain string from before 2026-10-16 */ }
    if (!draft || typeof draft.text !== "string") return typeof draft === "string" ? draft : stored;
    return Date.now() - Number(draft.at) <= 24 * 60 * 60 * 1000 ? draft.text : "";
  }

  // First-paint state. DOMContentLoaded waits for the deferred bundles (and
  // the Firebase CDN modules before them), so the browser usually paints the
  // bare template first; everything set only then slid or swapped into place
  // in front of the reader: the stored collapsed sidebar animated shut, the
  // auth buttons blinked for signed-in users. A MutationObserver runs
  // between parsing and painting, so each element gets its state as soon as
  // it exists. CSP forbids an inline script in the body for the same job.
  // Same rule as app-init.js (applyTheme), which keeps it later: the stored
  // theme, else the system's. Set only there, every dark reload painted a
  // light page first, and iPhone Safari kept that light colour in the strip
  // behind the status bar.
  let theme = read("theme");
  if (theme !== "dark" && theme !== "light") {
    theme = window.matchMedia?.("(prefers-color-scheme: dark)")?.matches ? "dark" : "light";
  }
  // /app/watches opens as the Watches page from its first frame (Apple-Audit
  // J6): the chat column is never painted, the page and its card skeleton
  // are, and watch.js takes over once the session is known.
  const watchPage = window.location.pathname === "/app/watches";
  window.App.watchSkeleton = function () {
    const card = '<div class="wd-skeleton-card" aria-hidden="true">'
      + '<span class="skeleton is-status"></span><span class="skeleton is-title"></span>'
      + '<span class="skeleton is-line"></span><span class="skeleton is-line is-short"></span>'
      + '<span class="skeleton is-foot"></span></div>';
    return '<div class="wd-skeleton skeleton-group" role="status" aria-label="Loading your watches">'
      + '<div class="wd-skeleton-summary" aria-hidden="true"><span class="skeleton"></span></div>'
      + '<div class="wd-skeleton-list">' + card.repeat(3) + '</div></div>';
  };
  function bookmarksSkeleton() {
    return '<div class="skeleton-group bookmarks-skeleton" role="status" aria-label="Loading chats">'
      + '<div class="skeleton-bookmark" aria-hidden="true"><span class="skeleton"></span></div>'.repeat(4)
      + '</div>';
  }
  function loginSkeleton() {
    return '<span class="skeleton-group" role="status" aria-label="Loading account"><span class="skeleton login-skeleton" aria-hidden="true"></span></span>';
  }
  // A session being restored (not yet known, auth reachable): the account's
  // placeholders belong in the first frame, not after the bundles (B11).
  function restoringAccount() {
    if (document.documentElement.dataset.authUnavailable === "true") return false;
    return !window.__consensioAuthState?.known && window.App.expectedSession().account;
  }

  // The chip a custom picker (model-picker.js) will draw, drawn now: the same
  // button in the same place, which initCustomModelPicker adopts. The native
  // select behind it is hidden the way the enhanced picker hides it.
  function seedPickerChip(wrapper, label, ariaLabel) {
    const select = wrapper?.querySelector("select");
    if (!select || !label || select._customModelPicker || wrapper.querySelector(":scope > .model-picker-display")) return;
    wrapper.classList.add("custom-model-picker", "is-enhanced");
    select.classList.add("native-model-picker");
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "model-picker-display";
    chip.dataset.seeded = "true";
    chip.setAttribute("aria-haspopup", "listbox");
    chip.setAttribute("aria-expanded", "false");
    // Translated part by part: "{picker}: {label}" has no entry of its own.
    chip.setAttribute("aria-label", ariaLabel || `${window.App.t(select.getAttribute("aria-label") || "Models")}: ${window.App.t(label)}`);
    const name = document.createElement("span");
    name.className = "model-picker-display-text";
    name.textContent = label;
    chip.append(name);
    wrapper.append(chip);
  }

  // The families that answer next: the account's stored choice
  // (compare_models, model-picker.js restoreModelSelections), else the
  // template's defaults. Drawn into the checkboxes before anything counts them.
  function seedFamilies() {
    const stored = window.App.userSettings?.get?.("compare_models") || {};
    (window.MODEL_FAMILIES || []).forEach(family => {
      const box = document.getElementById(family.checkboxId);
      const enabled = stored[family.label]?.enabled;
      if (box && typeof enabled === "boolean") box.checked = enabled;
    });
  }
  function checkedFamilies() {
    return (window.MODEL_FAMILIES || []).filter(family => document.getElementById(family.checkboxId)?.checked);
  }
  // The provider marks of the start bar (agent-mode.js renderComposerMode
  // draws the same nodes and keeps them while the families stay).
  function seedModelIcons(icons) {
    if (icons.childElementCount) return;
    const families = checkedFamilies();
    icons.replaceChildren(...families.map(family => {
      const mark = document.createElement("span");
      mark.className = "composer-model-icon";
      mark.dataset.provider = family.provider;
      mark.title = family.title;
      mark.setAttribute("role", "img");
      mark.setAttribute("aria-label", family.title);
      if (family.icon) {
        const image = document.createElement("img");
        image.src = family.icon;
        image.alt = "";
        ["chatgpt-logo", "grok-logo", "mono-logo"].forEach(name => {
          if (String(family.iconClass || "").split(/\s+/).includes(name)) image.classList.add(name);
        });
        mark.append(image);
      } else mark.textContent = String(family.title || "").slice(0, 1);
      return mark;
    }));
    icons.dataset.providers = families.map(family => family.provider).join(",");
  }
  // "6 models": Compare's chip names how many answer
  // (model-picker.js syncCustomModelPicker).
  function consensusChipLabel() {
    const count = checkedFamilies().length;
    return count === 1 ? "1 model" : `${count} models`;
  }

  let draftSeeded = false;
  const seeded = new Set();
  const SEED_KEYS = ["body", "sidebar", "auth", "input", "starters", "switch", "watches",
    "families", "agentChip", "consensusChip", "demo", "send", "reasoning", "icons", "bookmarks", "login", "watchHint"];
  function once(key, node) {
    if (seeded.has(key) || !node) return null;
    seeded.add(key);
    return node;
  }
  function seed() {
    const agentLook = document.documentElement.classList.contains("agent-shell-expected");
    if (once("body", document.body)) {
      if (watchPage) document.body.classList.add("is-watch-view");
      if (theme === "dark") document.body.classList.add("dark-mode");
      // Agent's start screen (not Compare's) is painted before auth
      // resolves; run-mode.js (earlier in this bundle) owns the stored choice.
      if (window.App?.runMode?.preference() !== "compare") {
        document.body.classList.add("agent-mode-enabled");
      }
      // A guest's composer (greeting on phones, no Compare chip, the demo
      // beside Agent's) from the first paint; app-init.js keeps the class in
      // step with the session.
      if (guestExpected()) document.body.classList.add("is-guest");
      // Agent's composer and sidebar (agent-chat.js keeps the class).
      if (agentLook) document.body.classList.add("single-agent-active");
    }
    const sidebar = once("sidebar", document.getElementById("appSidebar"));
    if (sidebar) {
      // Same rule as prefersCollapsedSidebar() in app-init.js, which keeps it
      // later: the reader's own choice, else shut for a guest and open for an
      // account.
      const overlay = window.matchMedia("(max-width: 1099px)").matches;
      const stored = read("sidebar_collapsed");
      sidebar.classList.toggle("collapsed", overlay || (stored === null ? guestExpected() : stored === "true"));
    }
    // Guests only. A stored session is being restored: firebase.js shows the
    // buttons if it turns out to be a guest after all.
    const authTopActions = once("auth", document.getElementById("authTopActions"));
    if (authTopActions && guestExpected()) authTopActions.hidden = false;
    // One greeting for every mode and for guests (Max, 2026-10-22): it
    // stands in the template and never changes while the page loads.
    // The composer starts with the words it will keep: Agent's new-chat line
    // (same words as agent-chat.js syncComposer), which a guest gets too
    // (app-init.js: guests type, and sign in when they send). A restored
    // session showed the template's, then "Sign in", then Consensus's, then
    // Agent's. A question that waits for the sign-in stands in it already.
    const input = once("input", document.getElementById("questionInput"));
    if (input) {
      if (agentLook || guestExpected()) input.placeholder = window.App.askPlaceholder();
      const draft = !input.value && waitingDraft();
      if (draft) {
        input.value = draft;
        draftSeeded = true;
        // The autosizer measures before the first paint, with the stylesheet
        // in place (composer-autosize.js, head bundle).
        requestAnimationFrame(() => {
          window.App.sizeQuestionInput?.(input);
          // The note under the examples stands in their room while the field
          // holds text (composer.css); its distance is theirs, measured as
          // composer-invite.js measures it, so it does not glide up later.
          const row = document.getElementById("composerStarters");
          const style = row && getComputedStyle(row);
          const room = row?.offsetHeight ? row.offsetHeight + (parseFloat(style.marginTop) || 0) + (parseFloat(style.marginBottom) || 0) : 0;
          row?.closest(".input-section")?.style.setProperty("--starters-room", room + "px");
        });
      }
    }
    // An account's predicted example questions from the first frame
    // (composer-starters.js): the curated ones swapped out in front of the
    // reader otherwise. Once the row's last button is parsed.
    const check = once("starters", document.querySelector('#composerStarters [data-starter="check"]'));
    if (check) window.App.composerStarters?.seed(check.parentElement);
    // The switch says "Watches" before it is ever painted as "Chat".
    if (!watchPage) {
      seeded.add("switch");
      seeded.add("watches");
    }
    const watches = once("switch", document.getElementById("viewSwitchWatches"));
    if (watches) {
      const chat = document.getElementById("viewSwitchConsensus");
      chat?.classList.remove("is-active");
      chat?.setAttribute("aria-pressed", "false");
      watches.classList.add("is-active");
      watches.setAttribute("aria-pressed", "true");
      watches.closest(".view-switch")?.setAttribute("data-active", "watches");
    }
    const dashBody = once("watches", document.getElementById("watchDashBody"));
    if (dashBody) {
      document.getElementById("watchDashboard").hidden = false;
      if (!dashBody.childElementCount) {
        dashBody.innerHTML = window.App.watchSkeleton();
        dashBody.setAttribute("aria-busy", "true");
      }
    }
    // The composer as the app will draw it (Apple-Audit B1, B2, B13): the
    // chips, Reasoning, the provider marks, the demo button and Send. Every
    // node below is parsed before the composer's end, so the first frame
    // has all of them.
    const families = window.MODEL_FAMILIES || [];
    const lastFamily = families.length ? document.getElementById(families[families.length - 1].checkboxId) : document.body;
    const area = once("families", lastFamily && document.getElementById("modelSelectionArea"));
    if (area) seedFamilies();
    const agentControls = once("agentChip", document.getElementById("agentModelsRetry") && document.getElementById("agentModelControls"));
    if (agentControls && agentLook) {
      agentControls.hidden = false;
      // agent-chat.js keeps the reasoning select hidden: it lives in the chip's menu.
      const effortWrapper = document.getElementById("agentReasoningEffort")?.parentElement;
      if (effortWrapper) effortWrapper.hidden = true;
      const crossCheck = window.App.words.crossCheck(checkedFamilies().length);
      seedPickerChip(agentControls.querySelector(".agent-model-picker"), crossCheck, crossCheck);
    }
    const consensusChip = once("consensusChip", document.querySelector(".consensus-model .select-wrapper select") && document.querySelector(".consensus-model"));
    if (consensusChip) {
      if (agentLook) consensusChip.hidden = true;
      else if (!guestExpected()) seedPickerChip(consensusChip.querySelector(".select-wrapper"), consensusChipLabel());
    }
    // "Try the demo" is a one-time offer (demo.js): gone for good once used
    // or typed past, so a reload never shows it for a moment.
    const demo = once("demo", document.querySelector(".chat-input-container .demo-chip"));
    if (demo && read("demoChipDismissed")) demo.remove();
    else if (demo) demo.hidden = false;
    // An empty field sends nothing (disabled in the template); a guest's
    // waiting question can go, and asks for the sign-in (composer-invite.js).
    const send = once("send", document.getElementById("sendButton"));
    if (send && draftSeeded && guestExpected()) {
      send.disabled = false;
      send.setAttribute("aria-disabled", "false");
    }
    const reasoning = once("reasoning", document.getElementById("composerReasoningState"));
    if (reasoning && agentLook) {
      reasoning.textContent = window.App.firstFrame.agentEffort() || "Auto";
      reasoning.dataset.seeded = "true";
    }
    const icons = once("icons", document.getElementById("composerModelIcons"));
    if (icons) seedModelIcons(icons);
    // On a phone the Watches hint is a still dot on the menu island until
    // Watches is opened once (watch.js): there from the first frame, not
    // added a second later (Apple-Audit B2). Above the overlay width it is a
    // pulse that watch.js starts on purpose after a moment. Only for an
    // account: a guest could only be asked to log in behind it (H2, review 3).
    const watchHint = once("watchHint", document.getElementById("viewSwitchWatches"));
    if (watchHint && !watchPage && !guestExpected() && window.matchMedia("(max-width: 1099px)").matches
      && read("consensio.watchViewSwitchHint.seen.v1") !== "true") {
      watchHint.classList.add("has-watch-pulse");
    }
    // The chat list and the account footer of a session being restored.
    const bookmarks = once("bookmarks", document.getElementById("bookmarksContainer"));
    if (bookmarks && restoringAccount() && !bookmarks.childElementCount) bookmarks.innerHTML = bookmarksSkeleton();
    const login = once("login", document.getElementById("loginContainer"));
    if (login && restoringAccount() && !login.childElementCount) {
      login.hidden = false;
      login.innerHTML = loginSkeleton();
    }
    return seeded.size === SEED_KEYS.length;
  }
  if (!seed() && typeof MutationObserver === "function") {
    const observer = new MutationObserver(() => { if (seed()) observer.disconnect(); });
    observer.observe(document.documentElement, { childList: true, subtree: true });
    document.addEventListener("DOMContentLoaded", () => observer.disconnect(), { once: true });
  }

  document.addEventListener("DOMContentLoaded", () => {
    seed();
    // A session that resolved before this point owns the UI already: the
    // restoring placeholders above never apply to it (restoringAccount).
  });
  // The account this browser remembered is not coming (its session ended):
  // the Watches dot drawn for it goes, as nobody signed in has one (H2).
  window.addEventListener("consensio:auth-state", event => {
    if (!event.detail?.uid) document.getElementById("viewSwitchWatches")?.classList.remove("has-watch-pulse");
  });
})();
