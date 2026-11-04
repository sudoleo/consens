// The Watches page (/app/watches) and what every Watch surface shares. Since
// 2026-11-03 a Watch runs the Agent on a schedule (agent_watches.py):
// watch-sheet.js starts one, watch-dashboard.js renders the page, agent-watch.js
// is the card under an answer. This file keeps the page's route and view
// switch, the Watch pill under an Agent answer, the sign-in hand-off and the
// Telegram pairing. Classic script: exports window.openWatchDashboard,
// window.App.watch and window.App.watchUi.
(function () {
  const VIEW_SWITCH_HINT_STORAGE_KEY = "consensio.watchViewSwitchHint.seen.v1";
  // What a guest asked for before signing in (the sign-in reloads the page):
  // the sheet opens again with it afterwards (Apple-Audit J3).
  const PENDING_STORAGE_KEY = "consensio.watchAfterLogin.v1";
  const PENDING_MAX_AGE_MS = 60 * 60 * 1000;
  const watchState = window.App.watchState;

  function reducedMotion() {
    try {
      return Boolean(window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches);
    } catch (_) {
      return false;
    }
  }

  // The Share dialog links to Watches (share-dialog.js): the page never
  // opens under it.
  function closeShareDialog() {
    if (window.App?.sharedModal?.close) {
      window.App.sharedModal.close();
      return;
    }
    const modal = document.getElementById("shareModal");
    if (modal?.open) modal.close();
  }

  function popup(message) {
    window.App?.showPopup?.(message);
  }

  async function api(method, path, body) {
    const user = window.auth?.currentUser;
    if (!user) throw new Error("Log in first.");
    const userUid = user.uid;
    const requestEpoch = watchState.sessionEpoch;
    const token = await user.getIdToken();
    if (requestEpoch !== watchState.sessionEpoch || window.auth?.currentUser?.uid !== userUid) {
      throw new Error("Authentication changed.");
    }
    const response = await fetch(path, {
      method,
      headers: { "Content-Type": "application/json", "Authorization": "Bearer " + token },
      body: body ? JSON.stringify(body) : undefined,
      // A change outlives the page: a setting typed last still arrives when
      // the tab closes. The bodies are small (keepalive allows 64 kB).
      keepalive: method !== "GET"
    });
    const data = await window.App.readJson(response);
    if (requestEpoch !== watchState.sessionEpoch || window.auth?.currentUser?.uid !== userUid) {
      throw new Error("Authentication changed.");
    }
    if (!response.ok) {
      // The reason may come flat ({error, code}) or as FastAPI's detail,
      // a string or an object of the same fields (App.httpError reads all).
      throw window.App.httpError(response, data);
    }
    return data;
  }

  async function loadTelegramState(force) {
    if (watchState.telegram && !force) return watchState.telegram;
    const data = await api("GET", "/api/my/telegram");
    watchState.setTelegram(data.telegram || { configured: false, connected: false });
    return watchState.telegram;
  }

  function normalizeWatchLimits(rawLimits, watches) {
    const list = Array.isArray(watches) ? watches : [];
    const activeFromList = list.filter(watch => watch.status === "active").length;
    // "plan" traegt jetzt free/plus/pro. Der Fallback greift nur, solange der
    // Server noch nicht geantwortet hat; die Zahl selbst kommt sonst immer aus
    // der Antwort.
    const tier = window.App.normalizeTier?.(rawLimits?.plan ?? window.userTier) || "free";
    const configuredLimit = Number(rawLimits?.active_limit);
    const configFallback = Number((window.APP_LIMITS || {})[
      `watch_${tier}_active_limit`
    ]);
    const activeLimit = Number.isFinite(configuredLimit) && configuredLimit >= 0
      ? configuredLimit : (Number.isFinite(configFallback) ? configFallback : 0);
    const configuredActive = Number(rawLimits?.active_count);
    const activeCount = Number.isFinite(configuredActive) && configuredActive >= 0
      ? configuredActive : activeFromList;
    const configuredPaused = Number(rawLimits?.paused_count);
    const pausedCount = Number.isFinite(configuredPaused) && configuredPaused >= 0
      ? configuredPaused : Math.max(0, list.length - activeFromList);
    return {
      plan: tier,
      activeCount: activeCount,
      activeLimit: activeLimit,
      remaining: Math.max(0, activeLimit - activeCount),
      pausedCount: pausedCount,
      dailyAvailable: rawLimits?.daily_available === true,
      atLimit: activeCount >= activeLimit
    };
  }

  // The one place that takes an answer of /api/my/watches (this file and the
  // dashboard's archive): the limits, the sidebar count, and the event the
  // Watch pills follow.
  function receiveWatchList(data) {
    const watches = Array.isArray(data?.watches) ? data.watches : [];
    watchState.setLimits(normalizeWatchLimits(data?.limits, watches));
    // Archived, they count for nothing: the Agent's Watches write the line.
    // On the Watches page, the page writes it from its own read.
    if (!data?.archived) renderSidebarWatchQuota(watchState.limits);
    else if (!onWatchPagePath()) window.App.agentWatch?.refreshQuota?.();
    window.dispatchEvent(new CustomEvent("consensio:watches-changed"));
    return watchState.limits;
  }

  // One GET of the list at a time: a caller that comes while one is on its
  // way shares it (the Watches page opened directly loaded the list three
  // times, review 2), unless it needs a list newer than a change it just
  // made (`fresh`). Resolves to the server's answer, already taken in.
  function requestWatchList({ fresh = false } = {}) {
    if (watchState.limitRequest && !fresh) return watchState.limitRequest;
    const request = api("GET", "/api/my/watches")
      .then(data => {
        receiveWatchList(data);
        return data;
      })
      .finally(() => {
        if (watchState.limitRequest === request) watchState.setLimitRequest(null);
      });
    watchState.setLimitRequest(request);
    return request;
  }

  async function loadWatchLimits() {
    if (watchState.limits) return watchState.limits;
    await requestWatchList();
    return watchState.limits;
  }

  function renderSidebarWatchQuota(limits) {
    const target = document.getElementById("watchUsageDisplay");
    if (!target || !limits) return;
    target.innerHTML = `Watches: <strong>${limits.activeCount} / ${limits.activeLimit}</strong>`;
  }

  // ------------------------------------------------------------------
  // Telegram pairing (J19): one pairing at a time for the whole page. It
  // waits as long as the link is valid (10 min), checks at once when the
  // reader comes back from Telegram and never asks for a reload. Every
  // surface that offers it (the page's Delivery) listens.
  // ------------------------------------------------------------------
  const TELEGRAM_LINK_MS = 10 * 60 * 1000;
  const telegramListeners = new Set();
  let telegramPairing = null;

  function telegramStatus() {
    return telegramPairing ? telegramPairing.state : "idle";
  }

  function onTelegramStatus(listener) {
    telegramListeners.add(listener);
    return () => telegramListeners.delete(listener);
  }

  function emitTelegram(state, detail) {
    telegramListeners.forEach(listener => {
      try { listener(state, detail); } catch (_) { /* a closed surface */ }
    });
  }

  function cancelTelegramPairing() {
    if (!telegramPairing) return;
    telegramPairing.stop();
    telegramPairing = null;
    emitTelegram("idle");
  }

  async function connectTelegram(onConnected) {
    if (telegramPairing) return null;
    let pendingWindow = null;
    let stopped = false;
    let timer = null;
    const startedAt = Date.now();
    const pairing = {
      state: "waiting",
      stop() {
        stopped = true;
        clearTimeout(timer);
        window.removeEventListener("focus", checkSoon);
        document.removeEventListener("visibilitychange", onVisible);
      }
    };
    telegramPairing = pairing;
    emitTelegram("waiting");
    function finish(state, detail) {
      if (telegramPairing !== pairing) return;
      pairing.stop();
      telegramPairing = null;
      emitTelegram(state, detail);
    }
    async function check() {
      if (stopped) return;
      try {
        const state = await loadTelegramState(true);
        if (stopped) return;
        if (state.connected) {
          finish("connected", state);
          onConnected?.(state);
          return;
        }
      } catch (_) { /* the next try decides */ }
      if (stopped) return;
      const waited = Date.now() - startedAt;
      if (waited >= TELEGRAM_LINK_MS) {
        finish("expired");
        return;
      }
      // Quick at first (the reader is in Telegram right now), then calmer.
      timer = setTimeout(check, waited < 40000 ? 2000 : waited < 120000 ? 5000 : 15000);
    }
    function checkSoon() {
      if (stopped) return;
      clearTimeout(timer);
      timer = setTimeout(check, 250);
    }
    function onVisible() {
      if (document.visibilityState === "visible") checkSoon();
    }
    try {
      pendingWindow = window.open("about:blank", "_blank");
      if (pendingWindow) pendingWindow.opener = null;
      const data = await api("POST", "/api/my/telegram/link", {});
      if (stopped) {
        try { pendingWindow?.close(); } catch (_) { /* ignored */ }
        return null;
      }
      if (pendingWindow) pendingWindow.location = data.url;
      else window.location.href = data.url;
      window.addEventListener("focus", checkSoon);
      document.addEventListener("visibilitychange", onVisible);
      timer = setTimeout(check, 2000);
    } catch (error) {
      try { pendingWindow?.close(); } catch (_) { /* ignored */ }
      finish("failed", error);
    }
    return pairing;
  }

  // A block that changes its height grows or shrinks over --dur-state from
  // where it was instead of in one frame (J2). `hold` keeps the old height
  // while the reader types in a field below it; the block settles once the
  // field is left, so nothing slides away under the cursor.
  function smoothHeight(node, mutate, { hold = null } = {}) {
    if (!node) { mutate(); return; }
    const before = node.getBoundingClientRect().height;
    mutate();
    if (hold && hold.contains(document.activeElement)) {
      node.style.minHeight = before + "px";
      const release = event => {
        if (hold.contains(event.relatedTarget)) return;
        hold.removeEventListener("focusout", release);
        smoothHeight(node, () => { node.style.minHeight = ""; });
      };
      hold.addEventListener("focusout", release);
      return;
    }
    if (reducedMotion() || !node.isConnected) return;
    // style.height means the border box or the content box, depending on the
    // node; both ends of the movement are measured in that same box, so a
    // bordered dialog does not pop 2 px at the start or the end.
    const cs = getComputedStyle(node);
    const px = name => parseFloat(cs[name]) || 0;
    const borders = px("borderTopWidth") + px("borderBottomWidth");
    const paddings = px("paddingTop") + px("paddingBottom");
    const borderBox = cs.boxSizing === "border-box";
    const from = borderBox ? before : before - borders - paddings;
    const after = borderBox ? node.scrollHeight + borders : node.scrollHeight - paddings;
    if (Math.abs(after - from) < 1) return;
    node.style.overflow = "hidden";
    node.style.height = from + "px";
    void node.offsetHeight;
    node.style.transition = "height var(--dur-state) var(--ease-standard)";
    node.style.height = after + "px";
    let done = false;
    const settle = () => {
      if (done) return;
      done = true;
      node.style.height = "";
      node.style.overflow = "";
      node.style.transition = "";
    };
    node.addEventListener("transitionend", event => { if (event.target === node) settle(); }, { once: true });
    setTimeout(settle, 400);
  }

  const WATCH_QUESTION_MIN_CHARS = 8;

  function normalizeWatchQuestion(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
  }

  // ------------------------------------------------------------------
  // Guests (J3): every invitation leads into the sign-in and, after the
  // reload it ends in, straight back to the sheet with the same question.
  // ------------------------------------------------------------------
  function readPending() {
    try {
      const pending = JSON.parse(localStorage.getItem(PENDING_STORAGE_KEY) || "null");
      return pending && typeof pending === "object" ? pending : null;
    } catch (_) {
      return null;
    }
  }

  function writePending(value) {
    try {
      if (value) localStorage.setItem(PENDING_STORAGE_KEY, JSON.stringify(value));
      else localStorage.removeItem(PENDING_STORAGE_KEY);
    } catch (_) { /* private mode: the reader starts over after signing in */ }
  }

  function requireAccount(intent, trigger) {
    if (window.auth?.currentUser) return true;
    const question = normalizeWatchQuestion(intent?.question).slice(0, 2000);
    writePending({ at: Date.now(), question });
    if (window.App?.openAuthModal) {
      // "Your question waits" only when there is one (not from "Log in to
      // start watching" on an empty Watches page).
      window.App.openAuthModal("login", trigger || document.activeElement, "watch",
        { lead: question ? "Log in to start watching. Your question waits for you." : "Log in to start watching." });
    } else {
      popup("Log in to start watching.");
    }
    return false;
  }

  // Every way to start a Watch (the pill, the public page's invitation, a
  // sign-in that came between): on the Watches page its own field takes it
  // (watch-dashboard.js compose), anywhere else, and from the pill in a
  // chat, the sheet (watch-sheet.js), which sends a guest into the sign-in
  // first.
  function startWatch(options = {}) {
    if (!options.chatId && onWatchPagePath() && watchViewIsOpen()
      && window.App.watchDashboard?.compose?.(options)) return;
    window.App.watchSheet?.open(options);
  }

  function resumePendingWatch() {
    if (!window.auth?.currentUser) return;
    const pending = readPending();
    if (!pending) return;
    writePending(null);
    if (Date.now() - Number(pending.at || 0) > PENDING_MAX_AGE_MS) return;
    startWatch({ task: pending.question || "", source: "after_login" });
  }

  // ------------------------------------------------------------------
  // Watch page (/app/watches): full view with URL + segmented-switch sync.
  // The page scrolls the document like every page (F14): the chat column
  // steps aside while it is open (body.is-watch-view) and gets its scroll
  // position back when it returns. Changing views fades through: the old
  // view fades out, the new one fades in with a small rise; the switch
  // itself never moves (C6, J4).
  // ------------------------------------------------------------------

  const WATCH_PAGE_PATH = "/app/watches";
  const APP_PATH = "/app";
  const VIEW_OUT_MS = 120;
  const VIEW_IN_MS = 200;
  let viewToken = 0;
  let chatScrollY = 0;
  let viewTimer = null;
  // The state a running fade is heading for: asking again for it (the
  // popstate that follows our own history.back()) must not restart it.
  let viewHeading = null;

  function dashEls() {
    return {
      page: document.getElementById("watchDashboard"),
      body: document.getElementById("watchDashBody")
    };
  }

  function onWatchPagePath() {
    return window.location.pathname === WATCH_PAGE_PATH;
  }

  function setViewSwitchState(isWatchView) {
    const consensusButton = document.getElementById("viewSwitchConsensus");
    const watchesButton = document.getElementById("viewSwitchWatches");
    if (!consensusButton || !watchesButton) return;

    consensusButton.classList.toggle("is-active", !isWatchView);
    consensusButton.setAttribute("aria-pressed", String(!isWatchView));
    watchesButton.classList.toggle("is-active", isWatchView);
    watchesButton.setAttribute("aria-pressed", String(isWatchView));
    consensusButton.closest(".view-switch")?.setAttribute("data-active", isWatchView ? "watches" : "chat");
  }

  function watchViewIsOpen() {
    const { page } = dashEls();
    return Boolean(page && !page.hidden);
  }

  const VIEW_CLASSES = ["is-view-out", "is-view-in", "is-view-settle", "is-switch-out", "is-switch-in"];

  // Opens or closes the page. `restoreScroll: false` leaves the window where
  // a caller is about to put it (a chat opened from the sidebar).
  function setWatchView(open, { animate = true, restoreScroll = true } = {}) {
    const { page } = dashEls();
    if (!page) return;
    if (viewHeading === open) return;
    const token = ++viewToken;
    clearTimeout(viewTimer);
    viewHeading = null;
    const body = document.body;
    setViewSwitchState(open);
    const isOpen = !page.hidden;
    // The switch lives on the start screen and on Watches; into or out of a
    // chat it fades with the page instead of popping.
    const switchMoves = !body.classList.contains("is-hero");
    const swap = () => {
      if (open && !isOpen) {
        chatScrollY = window.scrollY || 0;
        page.hidden = false;
        body.classList.add("is-watch-view");
        window.scrollTo(0, 0);
      } else if (!open && isOpen) {
        page.hidden = true;
        body.classList.remove("is-watch-view");
        if (restoreScroll) window.scrollTo(0, chatScrollY);
      }
    };
    body.classList.remove(...VIEW_CLASSES);
    if (open === isOpen || !animate || reducedMotion()) {
      swap();
      return;
    }
    body.classList.add("is-view-out");
    if (switchMoves && !open) body.classList.add("is-switch-out");
    viewHeading = open;
    viewTimer = setTimeout(() => {
      if (token !== viewToken) return;
      viewHeading = null;
      swap();
      body.classList.remove("is-view-out", "is-switch-out");
      body.classList.add("is-view-in");
      if (switchMoves && open) body.classList.add("is-switch-in");
      void body.offsetHeight;
      requestAnimationFrame(() => {
        if (token !== viewToken) return;
        body.classList.add("is-view-settle");
        body.classList.remove("is-view-in", "is-switch-in");
        viewTimer = setTimeout(() => {
          if (token === viewToken) body.classList.remove("is-view-settle");
        }, VIEW_IN_MS + 40);
      });
    }, VIEW_OUT_MS);
  }

  function acknowledgeViewSwitchHint() {
    document.getElementById("viewSwitchWatches")?.classList.remove("has-watch-pulse");
    try { localStorage.setItem(VIEW_SWITCH_HINT_STORAGE_KEY, "true"); } catch (_) {}
  }

  function initViewSwitchHint() {
    const watchesButton = document.getElementById("viewSwitchWatches");
    if (!watchesButton || onWatchPagePath()) return;
    try {
      if (localStorage.getItem(VIEW_SWITCH_HINT_STORAGE_KEY) === "true") return;
    } catch (_) {}
    // A dot stands only where something waits that can be opened: a guest
    // could only be asked for an account behind it, so the hint waits for
    // a signed-in account (Apple-Audit H2), also on the phone's menu button.
    let scheduled = false;
    const schedule = () => {
      if (scheduled || !window.auth?.currentUser) return;
      scheduled = true;
      window.removeEventListener("consensio:auth-state", schedule);
      setTimeout(() => {
        if (!window.auth?.currentUser || onWatchPagePath()) return;
        watchesButton.addEventListener("animationend", () => {
          watchesButton.classList.remove("has-watch-pulse");
        }, { once: true });
        watchesButton.classList.add("has-watch-pulse");
      }, 1400);
    };
    schedule();
    if (!scheduled) window.addEventListener("consensio:auth-state", schedule);
  }

  function wireWatchPage() {
    const { page } = dashEls();
    if (!page || page.dataset.wired) return;
    page.dataset.wired = "1";
    // Esc closes the topmost layer only (a dialog, a menu): the page is a
    // page, not a layer, and never closes on Esc with work in it (J1).
    // Browser-Navigation (Back/Forward) hält Seite und URL synchron.
    window.addEventListener("popstate", () => {
      if (onWatchPagePath()) showWatchPage();
      else {
        window.App.watchDashboard?.commitPending?.();
        setWatchView(false);
      }
    });
    // New chat leaves Watches at once: its handler (app-init.js) puts the
    // focus into the composer, which the fade would still keep hidden.
    document.addEventListener("click", event => {
      if (!watchViewIsOpen() || !event.target?.closest?.("#newRunButton")) return;
      closeWatchDashboard({ animate: false });
    }, true);
    // A chat opened from the sidebar leaves Watches for that chat; its "…"
    // menu and rename field act on the row and keep the page.
    document.getElementById("bookmarksContainer")?.addEventListener("click", event => {
      if (!watchViewIsOpen() || event.target.closest(".bookmark-menu-button, .bookmark-rename-input")) return;
      if (!event.target.closest(".bookmark")) return;
      closeWatchDashboard({ animate: false, restoreScroll: false });
    }, true);
  }

  function closeWatchDashboard(options = {}) {
    const { page } = dashEls();
    if (!page) return;
    window.App.watchDashboard?.commitPending?.();
    setWatchView(false, options);
    if (!onWatchPagePath()) return;
    // Innerhalb der App geöffnet: echter History-Schritt zurück. Direkt auf
    // /app/watches geladen: URL ohne neuen History-Eintrag auf /app setzen.
    if (window.history.state && window.history.state.watchPage) {
      window.history.back();
    } else {
      window.history.replaceState(null, "", APP_PATH);
    }
  }

  function showWatchPage(options = {}) {
    const { page } = dashEls();
    if (!page) return;
    wireWatchPage();
    setWatchView(true, { animate: options.animate !== false });
    if (!window.auth?.currentUser) {
      window.App.watchDashboard?.renderGuest?.();
      return;
    }
    const rendering = window.App.watchDashboard?.render({ visit: true });
    if (options.focus) {
      Promise.resolve(rendering).then(() => window.App.watchDashboard?.focusWatch?.(options.focus));
    }
  }

  // Guests see the page too: what a watch is, by example, and the way in
  // (J3) -- no toast that says "log in" and leaves them where they were.
  function openWatchDashboard(options = {}) {
    closeShareDialog();
    acknowledgeViewSwitchHint();
    if (!onWatchPagePath()) {
      window.history.pushState({ watchPage: true }, "", WATCH_PAGE_PATH);
    }
    showWatchPage(options);
  }

  // The page's first look for an account comes once, from whichever way
  // learns of the account first: the route's wait below or the auth state.
  // Both rendered it, and each render loaded the page (review 2).
  let firstLookFor = "";
  function firstLook(uid) {
    if (!uid || firstLookFor === uid) return false;
    firstLookFor = uid;
    return true;
  }

  function initWatchPageRoute() {
    // Deep-Link /app/watches: app-bootstrap.js has already painted the page
    // with its card skeleton (J6); here it waits for the asynchronous
    // Firebase auth state and only then loads -- without a line of
    // "Checking your session…" in between.
    if (!onWatchPagePath()) return;
    acknowledgeViewSwitchHint();
    const { page, body } = dashEls();
    if (!page || !body) return;
    wireWatchPage();
    page.hidden = false;
    document.body.classList.add("is-watch-view");
    setViewSwitchState(true);
    if (!body.childElementCount) window.App.watchDashboard?.renderSkeleton?.();
    // /app/watches?create=1 (the public watch page's invitation): once the
    // session is known the page's field takes the focus; a guest signs in
    // when they start the Watch.
    const url = new URL(window.location.href);
    const wantsCreate = url.searchParams.get("create") === "1";
    if (wantsCreate) {
      url.searchParams.delete("create");
      window.history.replaceState(window.history.state, "", url.pathname + url.search + url.hash);
    }
    const startedAt = Date.now();
    // watch-dashboard.js comes right after this file in the same bundle: the
    // first look waits until it is there (a guest whose state is already
    // known would otherwise keep the skeleton).
    const waitForAuth = function () {
      if (window.auth?.currentUser) {
        if (firstLook(window.auth.currentUser.uid)) window.App.watchDashboard?.render();
        if (wantsCreate) startWatch({ source: "watch_page" });
        return;
      }
      if (window.__consensioAuthState?.known === true || Date.now() - startedAt >= 8000) {
        window.App.watchDashboard?.renderGuest?.();
        if (wantsCreate) startWatch({ source: "watch_page" });
        return;
      }
      setTimeout(waitForAuth, 250);
    };
    setTimeout(waitForAuth, 0);
  }

  function renderWatchLoginHint(message) {
    const { page } = dashEls();
    if (!page || !onWatchPagePath()) return;
    wireWatchPage();
    page.hidden = false;
    document.body.classList.add("is-watch-view");
    setViewSwitchState(true);
    window.App.watchDashboard?.renderGuest?.(message);
  }

  // ------------------------------------------------------------------
  // The Watch pill under an Agent answer (J20): a chat with a Watch reads
  // "Watching" and opens it on Watches (J17), any other starts one there.
  // ------------------------------------------------------------------
  const EYE_ICON = '<svg class="share-pill-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M3 12s3.5-6 9-6 9 6 9 6-3.5 6-9 6-9-6-9-6Z"></path><circle cx="12" cy="12" r="2.5"></circle></svg>';
  const answerButtons = new Set();

  // Also off the page: a history turn is built before it is inserted.
  function pillWatch(button) {
    return button?._chatId ? window.App.agentWatch?.activeFor?.(button._chatId) || null : null;
  }

  function syncWatchPill(button) {
    if (!button) return;
    const watch = pillWatch(button);
    const watching = Boolean(watch);
    const label = button.querySelector("span");
    const text = watching ? "Watching" : "Watch";
    if (label && label.textContent !== window.App.t(text)) label.textContent = text;
    button.classList.toggle("is-watching", watching);
    const description = watching ? "This chat has a Watch. Open it on Watches." : "Start a Watch in this chat";
    button.title = description;
    button.setAttribute("aria-label", description);
  }

  function watchPill(id, onStart) {
    const button = document.createElement("button");
    button.type = "button";
    if (id) button.id = id;
    button.className = "consensus-share-pill watch-consensus-pill";
    button.innerHTML = EYE_ICON + "<span>Watch</span>";
    button.addEventListener("click", () => {
      const watch = pillWatch(button);
      if (watch) openWatchDashboard({ focus: watch.id });
      else onStart(button);
    });
    answerButtons.add(button);
    return button;
  }

  // The Agent answer's pill, right after its evidence row (Sources ·
  // Answers · Differences) in the same line, on phones on the next one;
  // without an evidence row, on a line of its own under the answer.
  // Every finished Agent answer has one (Max, Apple-Audit J20): the live
  // answer (agent-chat.js, on every projection), a reopened chat's answer
  // and each Agent turn of the history (thread-history.js, built off the
  // page, `history: true`). The pill carries the question of its own turn,
  // set on every call, and starts the Watch in its chat. Only the live
  // answer's pill is #agentAnswerWatchButton.
  const LIVE_PILL_ID = "agentAnswerWatchButton";

  function syncAnswerWatchButton(answerBody, { question = "", eligible = false, history = false, chatId = "" } = {}) {
    if (!answerBody) return;
    let button = answerBody._watchPill;
    const text = normalizeWatchQuestion(question);
    // A turn that moved up into the history keeps its pill, but not the
    // live answer's ID.
    if (!history) {
      document.querySelectorAll("#" + LIVE_PILL_ID).forEach(node => { if (node !== button) node.removeAttribute("id"); });
    }
    // The row under an answer without an evidence row also holds its Share
    // pill (share-dialog.js): it goes only once it is empty.
    const ownRow = button?.closest(".agent-watch-pill-row");
    if (!eligible || text.length < WATCH_QUESTION_MIN_CHARS) {
      button?.remove();
      if (ownRow && !ownRow.children.length) ownRow.remove();
      answerButtons.delete(button);
      answerBody._watchPill = null;
      return;
    }
    if (!button) {
      button = watchPill(history ? "" : LIVE_PILL_ID,
        trigger => startWatch({ task: button._question, chatId: button._chatId, source: "agent_answer", trigger }));
      button.classList.add("agent-watch-pill");
      answerBody._watchPill = button;
    }
    button._question = text;
    button._chatId = String(chatId || "");
    // The chat's Watches load once per chat; the pill follows them.
    if (button._chatId) window.App.agentWatch?.load?.(button._chatId);
    // The evidence row beside the answer, also while a history turn is still
    // built off the page.
    const review = answerBody._agentReview?.parentNode && answerBody._agentReview.parentNode === answerBody.parentNode
      ? answerBody._agentReview : null;
    const nav = review ? review.querySelector(".agent-evidence-links") : null;
    if (nav) {
      if (nav.nextElementSibling !== button) nav.after(button);
      if (ownRow && !ownRow.children.length) ownRow.remove();
    } else {
      let row = button.closest(".agent-watch-pill-row");
      if (!row) {
        row = document.createElement("div");
        row.className = "agent-watch-pill-row";
        row.appendChild(button);
      }
      const after = review || window.App.answerTail?.(answerBody) || answerBody;
      if (after.nextElementSibling !== row) after.after(row);
    }
    syncWatchPill(button);
  }

  window.addEventListener("consensio:agent-watches-changed", () => answerButtons.forEach(button => {
    if (button.isConnected) syncWatchPill(button);
    else answerButtons.delete(button);
  }));

  window.addEventListener("consensio:watches-changed", () => answerButtons.forEach(button => {
    // A history replaced by another chat's takes its pills with it.
    if (button.isConnected) syncWatchPill(button);
    else answerButtons.delete(button);
  }));

  function initViewSwitch() {
    const consensusButton = document.getElementById("viewSwitchConsensus");
    const watchesButton = document.getElementById("viewSwitchWatches");
    if (!consensusButton || !watchesButton) return;

    consensusButton.addEventListener("click", () => closeWatchDashboard());
    watchesButton.addEventListener("click", () => {
      acknowledgeViewSwitchHint();
      if (watchViewIsOpen() && onWatchPagePath()) return;
      openWatchDashboard();
    });
    setViewSwitchState(onWatchPagePath());
    initViewSwitchHint();
  }

  function resetAfterLogout() {
    const { page } = dashEls();
    watchState.resetSession();
    cancelTelegramPairing();
    const quota = document.getElementById("watchUsageDisplay");
    if (quota) quota.textContent = "";
    answerButtons.forEach(syncWatchPill);
    // Nothing of the old session stays: an Undo still open is taken back.
    window.App.watchDashboard?.reset?.();
    if (onWatchPagePath()) {
      renderWatchLoginHint();
    } else {
      if (page) {
        page.hidden = true;
        document.body.classList.remove("is-watch-view");
      }
      setViewSwitchState(false);
    }
  }

  window.openWatchDashboard = openWatchDashboard;
  window.App.watch = Object.assign(window.App.watch || {}, {
    // The sidebar's Watch count, loaded once per session.
    loadState: loadWatchLimits,
    answerButton: syncAnswerWatchButton,
    resetAfterLogout: resetAfterLogout,
    // A chat that opens leaves Watches (openBookmark): by keyboard or from
    // Share in its "…" menu it opened unseen behind the page (2026-10-23).
    leave: () => { if (watchViewIsOpen()) closeWatchDashboard({ animate: false, restoreScroll: false }); }
  });
  // Shared with watch-dashboard.js (the API, the archive's list, Telegram),
  // watch-sheet.js (the sign-in hand-off) and firebase.js (smoothHeight).
  window.App.watchUi = {
    api: api,
    receiveWatchList: receiveWatchList,
    requestWatchList: requestWatchList,
    connectTelegram: connectTelegram,
    cancelTelegramPairing: cancelTelegramPairing,
    onTelegramStatus: onTelegramStatus,
    telegramStatus: telegramStatus,
    requireAccount: requireAccount,
    onWatchPagePath: onWatchPagePath,
    smoothHeight: smoothHeight
  };
  initViewSwitch();
  initWatchPageRoute();
  window.addEventListener("consensio:auth-state", event => {
    const uid = event.detail?.uid || null;
    const changed = watchState.updateAuthUid(uid);
    // A logout anywhere (also in the chat) lets the next login look again.
    if (!uid) firstLookFor = "";
    if (uid && window.auth?.currentUser?.uid === uid) {
      loadWatchLimits().catch(() => {});
      resumePendingWatch();
    }
    if (!onWatchPagePath() || !changed) return;
    if (uid && window.auth?.currentUser?.uid === uid) {
      if (firstLook(uid)) showWatchPage({ animate: false });
    } else {
      firstLookFor = "";
      renderWatchLoginHint();
    }
  });
  window.addEventListener("consensio:auth-unavailable", () => {
    if (onWatchPagePath()) {
      renderWatchLoginHint("Logging in isn’t possible right now. Check your connection and reload to try again.");
    }
  });
})();
