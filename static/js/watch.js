// Consensus Watch UI. Classic script/module contract: exports window.openWatchDialog
// (create dialog + dashboard) and window.openWatchDashboard (dashboard only).
// The fields and the time wording come from watch-fields.js (App.watchFields).
(function () {
  const FEATURE_NUDGE_STORAGE_KEY = "consensio.watchFeatureNudge.dismissed.v1";
  const FEATURE_NUDGE_RUNS_STORAGE_KEY = "consensio.watchFeatureNudge.runs.v1";
  // Der Hinweis bittet um eine WIEDERKEHRENDE Verpflichtung (woechentlicher
  // Lauf, E-Mail). Nach der ersten Antwort weiss der Nutzer noch nicht, ob er
  // das Produkt ueberhaupt will -- der Hinweis war dort reine Werbung. Ab der
  // dritten Frage ist die Nutzung belegt, und "aktuell halten" beschreibt ein
  // Beduerfnis, das er selbst schon hat.
  const FEATURE_NUDGE_MIN_RUNS = 3;
  const VIEW_SWITCH_HINT_STORAGE_KEY = "consensio.watchViewSwitchHint.seen.v1";
  // What a guest asked for before signing in (the sign-in reloads the page):
  // the dialog opens again with it afterwards (Apple-Audit J3).
  const PENDING_STORAGE_KEY = "consensio.watchAfterLogin.v1";
  const PENDING_MAX_AGE_MS = 60 * 60 * 1000;
  const WATCH_WEEKDAYS = [
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"
  ];
  let featureNudgeTimer = null;
  let featureNudgeAnchor = null;
  let featureNudgeQuestion = "";
  let featureNudgePositionHandler = null;
  const watchState = window.App.watchState;
  const fields = () => window.App.watchFields;

  function reducedMotion() {
    try {
      return Boolean(window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches);
    } catch (_) {
      return false;
    }
  }

  function featureNudgeWasDismissed() {
    try {
      return localStorage.getItem(FEATURE_NUDGE_STORAGE_KEY) === "true";
    } catch (_) {
      return false;
    }
  }

  // Zaehlt die abgeschlossenen Laeufe ueber Sitzungen hinweg und gibt den
  // neuen Stand zurueck. Ist der Speicher gesperrt (privater Modus), faellt
  // der Zaehler auf einen Sitzungswert zurueck -- lieber ein Hinweis pro
  // Sitzung zu spaet als gar keiner.
  let featureNudgeRunsFallback = 0;
  function countFeatureNudgeRun() {
    featureNudgeRunsFallback += 1;
    try {
      const next = (parseInt(localStorage.getItem(FEATURE_NUDGE_RUNS_STORAGE_KEY), 10) || 0) + 1;
      localStorage.setItem(FEATURE_NUDGE_RUNS_STORAGE_KEY, String(next));
      return next;
    } catch (_) {
      return featureNudgeRunsFallback;
    }
  }

  // Der Hinweis lebt direkt unter <body>, nicht im Consensus-Fuss. Nur so kann
  // er ueber dem fixierten Composer liegen, ohne dafuer die gesamte Antwort
  // anzuheben: Letzteres liess Antworttext und Footer ueber das Eingabefeld
  // malen. Die Position folgt trotzdem dem Watch-Knopf: absolut in
  // Seitenkoordinaten, so scrollt der Browser die Karte selbst mit. Fixiert
  // und bei jedem Scroll-Event nachgesetzt, lief sie ihrem Platz ein Bild
  // hinterher und zitterte (Apple-Audit D8). Geschrieben wird nur noch, wo
  // sie im Bild gehalten werden muss: unter der Oberkante, ueber dem Composer.
  function placeWatchFeatureNudge(nudge, anchor) {
    if (!nudge || !anchor?.isConnected) return;
    const edge = 8;
    const gap = 10;
    const anchorRect = anchor.getBoundingClientRect();
    const composerRect = document.querySelector(".input-section")?.getBoundingClientRect();
    const composerIsVisible = composerRect && composerRect.height > 0
      && composerRect.bottom > 0 && composerRect.top < window.innerHeight;
    const limit = composerIsVisible
      ? composerRect.top
      : window.innerHeight;

    const maxHeight = `${Math.max(80, Math.floor(limit - edge * 2))}px`;
    if (nudge.style.maxHeight !== maxHeight) nudge.style.maxHeight = maxHeight;
    const nudgeRect = nudge.getBoundingClientRect();
    const width = nudgeRect.width;
    const height = nudgeRect.height;
    const fitsBelow = anchorRect.bottom + gap + height <= limit - edge;
    const spaceBelow = limit - anchorRect.bottom;
    const spaceAbove = anchorRect.top;
    const placeAbove = !fitsBelow && spaceAbove >= spaceBelow;
    const desiredTop = placeAbove
      ? anchorRect.top - gap - height
      : anchorRect.bottom + gap;
    const maxTop = Math.max(edge, limit - edge - height);
    const top = Math.min(Math.max(edge, desiredTop), maxTop);
    const maxLeft = Math.max(edge, window.innerWidth - edge - width);
    const left = Math.min(Math.max(edge, anchorRect.right - width), maxLeft);

    if (nudge.classList.contains("is-above") !== placeAbove) nudge.classList.toggle("is-above", placeAbove);
    const page = (nudge.offsetParent || document.body).getBoundingClientRect();
    const pageLeft = `${Math.round(left - page.left)}px`;
    const pageTop = `${Math.round(top - page.top)}px`;
    if (nudge.style.left !== pageLeft) nudge.style.left = pageLeft;
    if (nudge.style.top !== pageTop) nudge.style.top = pageTop;
    // An anchor in a hidden view (another mode took over) has no box.
    const visibility = anchor.getClientRects().length ? "visible" : "hidden";
    if (nudge.style.visibility !== visibility) nudge.style.visibility = visibility;
  }

  function stopWatchFeatureNudgePositioning() {
    if (!featureNudgePositionHandler) return;
    window.removeEventListener("resize", featureNudgePositionHandler);
    document.removeEventListener("scroll", featureNudgePositionHandler, true);
    featureNudgePositionHandler = null;
  }

  function startWatchFeatureNudgePositioning(nudge, anchor) {
    stopWatchFeatureNudgePositioning();
    featureNudgeAnchor = anchor;
    featureNudgePositionHandler = () => placeWatchFeatureNudge(nudge, anchor);
    window.addEventListener("resize", featureNudgePositionHandler);
    document.addEventListener("scroll", featureNudgePositionHandler, true);
    featureNudgePositionHandler();
  }

  function dismissWatchFeatureNudge(reason) {
    const nudge = document.getElementById("watchFeatureNudge");
    const wasActive = Boolean(featureNudgeTimer || nudge);
    if (featureNudgeTimer) {
      clearTimeout(featureNudgeTimer);
      featureNudgeTimer = null;
    }
    const anchor = featureNudgeAnchor || document.querySelector(".watch-feature-anchor");
    stopWatchFeatureNudgePositioning();
    if (nudge) nudge.remove();
    if (anchor) {
      anchor.classList.remove("has-feature-nudge");
    }
    featureNudgeAnchor = null;
    featureNudgeQuestion = "";
    try {
      localStorage.setItem(FEATURE_NUDGE_STORAGE_KEY, "true");
    } catch (_) {
      // Storage can be unavailable in hardened/private browser contexts.
    }
    if (wasActive) {
      window.App?.trackAppEvent?.("app_watch_feature_nudge_dismissed", {
        reason: reason || "dismissed"
      });
    }
  }

  // Consensus haengt den Hinweis an den Watch-Knopf der Antwort und startet
  // die Watch aus dem gespeicherten Ergebnis. Der Agent hat weder Knopf noch
  // Ergebnis-Snapshot: er uebergibt `source` = { eligible, question, anchor },
  // und die Watch entsteht aus der Frage selbst ("question first"; der Server
  // fuehrt die erste Pruefung zum Termin aus). Zaehler und "nicht mehr zeigen"
  // sind fuer beide Modi dieselben.
  function showWatchFeatureNudge(source) {
    // Every finished consensus also brings its question to the Watch button.
    syncConsensusWatchButton();
    if (featureNudgeWasDismissed() || featureNudgeTimer
        || document.getElementById("watchFeatureNudge")) return;
    // Jeder abgeschlossene Lauf zaehlt -- auch der eines Gastes, damit der
    // Hinweis nach einer spaeteren Anmeldung nicht wieder bei null anfaengt.
    if (countFeatureNudgeRun() < FEATURE_NUDGE_MIN_RUNS) return;
    // Only promote an immediately usable action. Guests and failed snapshot
    // persistence keep the normal Watch button without a marketing nudge.
    const questionSource = source && source.eligible && source.question && source.anchor
      ? { question: String(source.question), anchor: source.anchor } : null;
    if (source && !questionSource) return;
    // A question that is already watched needs no invitation (J17).
    if (questionSource && watchedFor(questionSource.question)) return;
    const usable = () => Boolean(window.auth?.currentUser)
      && (questionSource ? questionSource.anchor.isConnected : Boolean(window.lastShareResultId));
    if (!usable()) return;

    featureNudgeTimer = setTimeout(() => {
      featureNudgeTimer = null;
      if (featureNudgeWasDismissed() || !usable()) return;
      const anchor = questionSource ? questionSource.anchor : document.querySelector(".watch-feature-anchor");
      if (!anchor || document.getElementById("watchFeatureNudge")) return;
      featureNudgeQuestion = questionSource ? questionSource.question : "";

      const nudge = document.createElement("span");
      nudge.id = "watchFeatureNudge";
      nudge.className = "watch-feature-nudge";
      nudge.setAttribute("role", "status");
      nudge.setAttribute("aria-label", "New: watches");
      // Der Hinweis war frueher nur ein Hinweis: er erklaerte die Funktion und
      // liess den Nutzer dann den Watch-Knopf suchen. Jetzt steht die Aktion
      // selbst darin — ein Klick, fertige Voreinstellungen. Der Preis dafuer
      // ist Ehrlichkeit ueber die Benachrichtigung: nur bei einer echten
      // Aenderung, sonst nie. Genau das steht neben dem Knopf.
      nudge.innerHTML = `
        <button type="button" class="watch-feature-nudge-close close-button" aria-label="Dismiss new feature tip"><svg class="close-icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M4 4l8 8M12 4l-8 8"/></svg></button>
        <span class="watch-feature-nudge-label">New</span>
        <strong>Keep this answer current</strong>
        <span class="watch-feature-nudge-copy">We re-check it across model families and write only when a source moves the answer.</span>
        <button type="button" class="watch-nudge-btn" id="watchNudgeStart">Start watching</button>
        <span class="watch-nudge-meta">Weekly &middot; email only on evidence &middot; stop any time</span>
        <button type="button" class="watch-nudge-skip" id="watchNudgeCustomize">Add a goal or change the schedule</button>
      `;
      nudge.querySelector(".watch-feature-nudge-close").addEventListener("click", event => {
        event.stopPropagation();
        dismissWatchFeatureNudge("dismissed");
      });
      nudge.querySelector("#watchNudgeStart").addEventListener("click", event => {
        event.stopPropagation();
        startWatchFromNudge(event.currentTarget);
      });
      nudge.querySelector("#watchNudgeCustomize").addEventListener("click", event => {
        event.stopPropagation();
        const question = featureNudgeQuestion;
        dismissWatchFeatureNudge("customize");
        if (question) openWatchDialog("create", { question });
        else openWatchDialog("confirm");
      });
      anchor.classList.add("has-feature-nudge");
      document.body.appendChild(nudge);
      startWatchFeatureNudgePositioning(nudge, anchor);
      window.App?.trackAppEvent?.("app_watch_feature_nudge_shown");
    }, 650);
  }

  // Ein Klick, fertige Voreinstellungen: woechentlich, morgen, 09:00 lokal,
  // privat, E-Mail nur bei materieller Aenderung. Genau die Werte, die der
  // Dialog ohnehin vorschlaegt — der Dialog bleibt fuer alles andere da.
  // Der Hinweis und die Agent-Karte (agent-watch.js) starten damit; Daily
  // faellt ohne Berechtigung auf Weekly zurueck, ein Wochentag nur bei Weekly.
  function watchDefaults(interval = "weekly") {
    const chosen = interval === "monthly" || (interval === "daily" && dailyIntervalAllowed()) ? interval : "weekly";
    return {
      interval: chosen,
      run_weekday: chosen === "weekly" ? browserTomorrowWeekday() : "",
      email_mode: "changes_only",
      email_enabled: true,
      telegram_enabled: false,
      condition: "",
      visibility: "private",
      run_time: "09:00",
      timezone: browserTimezone()
    };
  }

  async function startWatchFromNudge(button) {
    if (!button || button.disabled) return;
    if (!requireAccount({ question: featureNudgeQuestion || normalizeWatchQuestion(window.lastQuestion) }, button)) return;
    button.disabled = true;
    button.textContent = "Starting…";
    window.App?.trackAppEvent?.("app_watch_nudge_start_click");
    try {
      let origin;
      if (featureNudgeQuestion) {
        origin = { question: featureNudgeQuestion };
      } else {
        const resultId = await (window.resolveCurrentShareResultId?.()
          || Promise.resolve(window.lastShareResultId));
        if (!resultId) throw new Error("This consensus is not saved yet.");
        origin = { result_id: resultId };
      }
      const payload = Object.assign(watchDefaults(), origin);
      const data = await api("POST", "/api/watch", payload);
      watchState.setLimits(null);
      window.App?.trackAppEvent?.("app_watch_created", {
        interval: data.watch.interval,
        source: "nudge"
      });
      renderNudgeSuccess(data.watch);
    } catch (error) {
      button.disabled = false;
      button.textContent = "Start watching";
      // Kontingent voll, schon beobachtet oder Server-Fehler: der Dialog kann
      // mehr erklaeren (Limits, Upgrade, Telegram) als dieser Streifen. Ein
      // Request-Limit ist kein Kontingent (H6): es sagt nur, wann es weitergeht.
      if (error.code === "rate_limited") {
        popup(window.App.userError(error));
        return;
      }
      if (error.status === 429 || isAlreadyWatched(error)) {
        watchState.setLimits(null);
        const question = featureNudgeQuestion || normalizeWatchQuestion(window.lastQuestion);
        dismissWatchFeatureNudge(error.status === 429 ? "limit" : "watched");
        await loadWatchLimits(true).catch(() => {});
        if (question) openWatchDialog("create", { question });
        else openWatchDialog("confirm");
        return;
      }
      popup("Watch not started. " + window.App.userError(error, { fallback: "Try again." }));
    }
  }

  // Der Hinweis bleibt stehen und wird zur Bestaetigung: der Nutzer soll
  // sehen, was er gerade ausgeloest hat — vor allem, dass er nur bei einer
  // Aenderung etwas hoert. Der Zeitplan steht schon in der Sprache des Lesers
  // (watch-fields.js) und ist im Satz nur ein Platzhalter (data-i18n-skip).
  function renderNudgeSuccess(watch) {
    const nudge = document.getElementById("watchFeatureNudge");
    if (!nudge) return;
    nudge.innerHTML = `
      <button type="button" class="watch-feature-nudge-close close-button" aria-label="Dismiss"><svg class="close-icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M4 4l8 8M12 4l-8 8"/></svg></button>
      <span class="watch-feature-nudge-label is-active">Watching</span>
      <strong>You are set</strong>
      <span class="watch-feature-nudge-copy">First check: <span data-i18n-skip>${escapeHtml(formatWatchSchedule(watch))}</span>. We only write when a source moves the answer.</span>
      <button type="button" class="watch-nudge-skip" id="watchNudgeOpenDash">Open Watches</button>
    `;
    nudge.querySelector(".watch-feature-nudge-close").addEventListener("click", event => {
      event.stopPropagation();
      dismissWatchFeatureNudge("created");
    });
    nudge.querySelector("#watchNudgeOpenDash").addEventListener("click", event => {
      event.stopPropagation();
      dismissWatchFeatureNudge("created");
      openWatchDashboard({ focus: watch.id });
    });
    placeWatchFeatureNudge(nudge, featureNudgeAnchor);
    loadWatchLimits(true).catch(() => {});
  }

  function els() {
    return {
      modal: document.getElementById("shareModal"),
      title: document.getElementById("shareModalTitle"),
      body: document.getElementById("shareModalBody")
    };
  }

  function closeDialog() {
    if (window.App?.sharedModal?.close) {
      window.App.sharedModal.close();
      return;
    }
    const { modal } = els();
    if (modal?.open) modal.close();
  }

  function popup(message) {
    window.App?.showPopup?.(message);
  }

  function watchModalIntentIsCurrent(intent) {
    if (window.App?.sharedModal?.isCurrent) {
      return window.App.sharedModal.isCurrent(intent);
    }
    const { modal } = els();
    return Boolean(modal?.open)
      && modal.classList.contains("is-watch-dialog");
  }

  async function api(method, path, body, intentIsCurrent) {
    const user = window.auth?.currentUser;
    if (!user) throw new Error("Log in first.");
    const userUid = user.uid;
    const requestEpoch = watchState.sessionEpoch;
    const token = await user.getIdToken();
    if (requestEpoch !== watchState.sessionEpoch || window.auth?.currentUser?.uid !== userUid) {
      throw new Error("Authentication changed.");
    }
    if (intentIsCurrent && !intentIsCurrent()) {
      const stale = new Error("This view is no longer active.");
      stale.stale = true;
      throw stale;
    }
    const response = await fetch(path, {
      method,
      headers: { "Content-Type": "application/json", "Authorization": "Bearer " + token },
      body: body ? JSON.stringify(body) : undefined,
      // A change outlives the page: a deletion whose Undo the closing tab
      // let happen (pagehide, commitPending) or a setting typed last still
      // arrives. The bodies are small (keepalive allows 64 kB).
      keepalive: method !== "GET"
    });
    const data = await window.App.readJson(response);
    if (requestEpoch !== watchState.sessionEpoch || window.auth?.currentUser?.uid !== userUid) {
      throw new Error("Authentication changed.");
    }
    if (!response.ok) {
      // The reason may come flat ({error, code}) or as FastAPI's detail,
      // a string or an object of the same fields (App.httpError reads all).
      const error = window.App.httpError(response, data);
      const detail = data.detail && typeof data.detail === "object" ? data.detail : {};
      error.watchId = String(data.watch_id || detail.watch_id || "");
      throw error;
    }
    return data;
  }

  // "This question is already watched": the server's code (J17), or its
  // older wording.
  function isAlreadyWatched(error) {
    return error?.code === "already_watched"
      || (error?.status === 409 && /already watched/i.test(error.message || ""));
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
  // dashboard): limits, the list Agent Watch cards compare their question to,
  // the sidebar count, and the event those cards follow.
  function receiveWatchList(data) {
    const watches = Array.isArray(data?.watches) ? data.watches : [];
    watchState.setLimits(normalizeWatchLimits(data?.limits, watches));
    watchState.setWatches(watches);
    renderSidebarWatchQuota(watchState.limits);
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

  async function loadWatchLimits(force) {
    if (watchState.limits && watchState.watches && !force) return watchState.limits;
    await requestWatchList({ fresh: Boolean(force) });
    return watchState.limits;
  }

  function showWatchCostInfo() {
    window.App?.showAccessInfo?.();
  }

  function renderSidebarWatchQuota(limits) {
    const target = document.getElementById("watchUsageDisplay");
    if (!target || !limits) return;
    target.innerHTML = `Watches: <strong>${limits.activeCount} / ${limits.activeLimit}</strong>`;
  }

  // The plan line in the page head: one quiet line with real separators
  // ("Pro access · 6 of 10 active · 4 slots free"), the detail below it.
  function renderWatchLimit(target, limits) {
    if (!target || !limits) return;
    const tier = window.App.normalizeTier?.(limits.plan) || "free";
    // Nur Free bekommt den Early-Access-Hinweis: Plus und Pro
    // haben ihr groesseres Kontingent schon.
    const isFree = tier === "free";
    const planLabel = tier === "pro"
      ? "Pro access" : (tier === "plus" ? "Plus access" : "Standard access");
    const activeLabel = `${limits.activeCount} of ${limits.activeLimit} active`;
    const availabilityLabel = limits.atLimit
      ? "All slots in use"
      : limits.remaining === 1 ? "1 slot free" : `${limits.remaining} slots free`;
    const meterWidth = limits.activeLimit > 0
      ? Math.min(100, Math.round((limits.activeCount / limits.activeLimit) * 100)) : 100;
    target.hidden = false;
    target.classList.toggle("is-full", limits.atLimit);
    target.innerHTML = `
      <div class="watch-limit-main">
        <span class="watch-limit-plan">${planLabel}</span>
        <strong>${activeLabel}</strong>
        <span class="watch-limit-sep" aria-hidden="true">·</span>
        <span class="watch-limit-availability">${availabilityLabel}</span>
        <span class="watch-limit-meter" aria-hidden="true"><i style="width:${meterWidth}%"></i></span>
      </div>
      <div class="watch-limit-detail">
        <span>Paused watches don’t count.</span>
        ${isFree ? `<span>Slots and check intervals are limited during early access.</span><button type="button" class="watch-limit-upgrade">About early access</button>` : ""}
      </div>`;
    target.querySelector(".watch-limit-upgrade")?.addEventListener("click", showWatchCostInfo);
  }

  // Why no new watch can start: the dialog, the page and the Agent card say
  // the same sentence.
  function limitMessage(limits) {
    return limits.activeLimit > 1
      ? `All ${limits.activeLimit} watch slots are in use. Pause one to start another.`
      : limits.activeLimit === 1
        ? "Your watch slot is in use. Pause that watch to start another."
        : "Watches are not available for your account yet.";
  }

  function renderDialogWatchLimit(target, limits) {
    if (!limits.atLimit) {
      target.hidden = true;
      target.textContent = "";
      return;
    }
    const isFree = (window.App.normalizeTier?.(limits.plan) || "free") === "free";
    const message = limitMessage(limits);
    target.hidden = false;
    target.classList.add("is-full");
    target.innerHTML = `<span>${escapeHtml(message)}</span>${isFree
      ? ' <button type="button" class="watch-limit-upgrade">About early access</button>' : ""}`;
    target.querySelector(".watch-limit-upgrade")?.addEventListener("click", showWatchCostInfo);
  }

  // A dialog opened before the limits were known learns them late: it then
  // says so where the form is and holds the start (J25 covers the usual
  // case, a limit known before the dialog opens).
  function applyDialogWatchLimit(limits) {
    const target = document.getElementById("watchDialogLimit");
    if (!target || !limits) return;
    renderDialogWatchLimit(target, limits);
    const action = document.getElementById("watchQuestionNext")
      || document.getElementById("watchConfirmBtn");
    if (!action || !limits.atLimit) return;
    action.disabled = true;
    action.textContent = "All slots in use";
  }

  function refreshDialogWatchLimit() {
    const target = document.getElementById("watchDialogLimit");
    if (!target) return;
    if (watchState.limits) applyDialogWatchLimit(watchState.limits);
    loadWatchLimits().then(applyDialogWatchLimit).catch(() => {
      if (!target.isConnected) return;
      target.hidden = true;
    });
  }

  // ------------------------------------------------------------------
  // Telegram pairing (J19): one pairing at a time for the whole page. It
  // waits as long as the link is valid (10 min), checks at once when the
  // reader comes back from Telegram and never asks for a reload. Every
  // surface that offers it (dialog, card settings, Delivery) listens.
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

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function dailyIntervalAllowed() {
    if (window.isUserPro === true) return true;
    if (watchState.limits) return watchState.limits.dailyAvailable === true;
    if (Number((window.APP_LIMITS || {}).watch_daily_interval_requires_pro) === 0) return true;
    // Plus darf das taegliche Intervall, solange der Admin-Schalter es erlaubt.
    return window.isUserPlus === true
      && Number((window.APP_LIMITS || {}).watch_plus_daily_interval_allowed) !== 0;
  }

  function browserWeekday() {
    const sundayFirstIndex = new Date().getDay();
    return WATCH_WEEKDAYS[(sundayFirstIndex + 6) % 7];
  }

  function browserTomorrowWeekday() {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    return WATCH_WEEKDAYS[(tomorrow.getDay() + 6) % 7];
  }

  // "Weekly on Sunday at 09:00 · E-mail · Private": schedule, channels,
  // alert rule (only when not the default) and page of a Watch's settings,
  // in the create dialog and on the Agent card. One line of parts, so each
  // part goes through App.t before they are joined (the schedule already
  // did, watch-fields.js).
  function settingsSummary(settings) {
    const say = text => window.App.t(text);
    const schedule = fields().scheduleLabel({ ...settings, timezone: settings.timezone || browserTimezone() });
    const channels = [
      settings.email_enabled ? say("Email") : "",
      settings.telegram_enabled ? say("Telegram") : ""
    ].filter(Boolean).join(" + ") || say("No channel");
    const parts = [schedule, channels];
    if (settings.email_mode === "every_run") parts.push(say("Every check"));
    if (settings.email_mode === "condition") parts.push(say("Only when it is reached"));
    parts.push(say(settings.visibility === "public" ? "Public" : "Private"));
    return parts.join(" · ");
  }

  // share_snapshots.question_hash in words: case, spacing and a final "?",
  // "!" or "." do not make another question.
  function questionKey(value) {
    return String(value || "").trim().toLowerCase().replace(/\s+/g, " ").replace(/[?!. ]+$/, "");
  }

  // The account's Watch of this question, if any (status included): the rule
  // of watch_service.creation_outlook, from the list loadWatchLimits keeps.
  function watchedFor(question) {
    const key = questionKey(question);
    if (!key) return null;
    return (watchState.watches || []).find(watch => questionKey(watch.question) === key) || null;
  }

  // "weekly on Tuesday at 09:00", the time zone only when it is not the
  // reader's own, in the reader's language (watch-fields.js scheduleText:
  // one wording everywhere).
  function formatWatchSchedule(watch) {
    return fields().scheduleText(watch);
  }

  function browserTimezone() {
    return fields().browserTimezone();
  }

  function setWatchFieldError(field, message) {
    if (!field) return;
    field.setAttribute("aria-invalid", "true");
    const error = document.getElementById(field.id + "Error");
    if (error) {
      error.textContent = message;
      error.hidden = false;
    }
  }

  function clearWatchFieldError(field) {
    if (!field) return;
    field.removeAttribute("aria-invalid");
    const error = document.getElementById(field.id + "Error");
    if (error) {
      error.textContent = "";
      error.hidden = true;
    }
  }

  function focusWatchField(field) {
    if (!field) return;
    const collapsedSection = field.closest("details:not([open])");
    if (collapsedSection) collapsedSection.open = true;
    field.scrollIntoView({ behavior: window.App.scrollBehavior?.() || "auto", block: "center" });
    try {
      field.focus({ preventScroll: true });
    } catch (_) {
      field.focus();
    }
  }

  function bindWatchFieldErrorReset(field, eventName) {
    if (!field) return;
    field.addEventListener(eventName, () => clearWatchFieldError(field));
  }

  function focusQuietly(node) {
    if (!node) return;
    try { node.focus({ preventScroll: true }); } catch (_) { node.focus(); }
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

  // ------------------------------------------------------------------
  // Guests (J3): every invitation leads into the sign-in and, after the
  // reload it ends in, straight back to the dialog with the same question.
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
    writePending({
      at: Date.now(),
      question,
      goal: normalizeWatchQuestion(intent?.goal).slice(0, 500)
    });
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

  function resumePendingWatch() {
    if (!window.auth?.currentUser) return;
    const pending = readPending();
    if (!pending) return;
    writePending(null);
    if (Date.now() - Number(pending.at || 0) > PENDING_MAX_AGE_MS) return;
    openWatchDialog("create", { question: pending.question || "", goal: pending.goal || "", source: "after_login" });
  }

  function openWatchDialog(view, options) {
    const setup = options || {};
    if (view === "list") {
      closeDialog();
      openWatchDashboard();
      return;
    }
    const knownQuestion = normalizeWatchQuestion(
      view === "create" ? setup.question : (setup.question || window.lastQuestion));
    if (!requireAccount({ question: knownQuestion, goal: setup.goal }, setup.trigger)) return;
    const { modal } = els();
    if (!modal) return;
    let modalIntent = null;
    if (window.App?.sharedModal?.open) {
      modalIntent = window.App.sharedModal.open("watch");
    } else {
      modal.classList.add("is-watch-dialog");
      if (!modal.open) modal.showModal?.();
    }
    // The state belongs to the button, not to an error after the form (J17):
    // a question that is already watched opens as the watch it is.
    const existing = knownQuestion && watchedFor(knownQuestion);
    if (existing) {
      renderAlreadyWatching(existing, modalIntent);
      return;
    }
    const showForm = () => {
      if (view !== "create") {
        renderConfirm(undefined, modalIntent);
        return;
      }
      // A question that is already known (an example, the chat's last
      // question, an Agent proposal) goes straight to the goal; "Edit" leads
      // back to the field. Options: question, goal (the preset choice), goals
      // (suggestions the caller already has, so none are fetched), interval,
      // editQuestion (a follow-up: start at the field, prefilled) and source
      // (analytics).
      if (knownQuestion.length >= WATCH_QUESTION_MIN_CHARS && !setup.editQuestion) {
        renderConfirm({ ...setup, question: knownQuestion }, modalIntent);
      } else {
        renderQuestionStep(setup.question, modalIntent, setup);
      }
    };
    // Before any typing: no free slot, no form (J25); the form comes as
    // soon as a slot is free.
    if (watchState.limits?.atLimit) {
      renderLimitStep(modalIntent, { resume: showForm, reload: true });
      return;
    }
    showForm();
  }

  function normalizeWatchQuestion(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
  }

  function dialogButton(id, label, kind = "secondary") {
    const button = document.createElement("button");
    button.type = "button";
    button.id = id;
    button.className = kind === "primary" ? "wd-button is-primary"
      : kind === "link" ? "wd-link" : "wd-button";
    button.textContent = label;
    return button;
  }

  // The action bar of every step: one primary, a quiet second, an error line
  // above them that says what went wrong without a toast.
  function dialogActions(...buttons) {
    const bar = document.createElement("div");
    bar.className = "share-modal-actions watch-dialog-actions";
    const error = document.createElement("p");
    error.id = "watchDialogError";
    error.className = "watch-field-error watch-dialog-error";
    error.setAttribute("role", "alert");
    error.hidden = true;
    bar.append(error, ...buttons);
    return bar;
  }

  function showDialogError(message) {
    const error = document.getElementById("watchDialogError");
    if (!error) {
      popup(message);
      return;
    }
    error.textContent = message;
    error.hidden = !message;
  }

  function questionPreview(question, editable) {
    const preview = document.createElement("div");
    preview.className = "watch-question-preview";
    const text = document.createElement("strong");
    text.textContent = question;
    preview.appendChild(text);
    if (editable) {
      const edit = dialogButton("watchQuestionEdit", "Edit", "link");
      edit.className = "watch-question-edit";
      preview.appendChild(edit);
    }
    return preview;
  }

  function renderQuestionStep(initialQuestion, modalIntent, setup = {}) {
    const { title, body } = els();
    if (!body) return;
    title.textContent = "New watch";
    body.innerHTML = `
      <div id="watchDialogLimit" class="watch-limit-summary is-dialog" aria-live="polite" hidden></div>
      <div class="watch-question-field">
        <label class="watch-goal-label" for="watchQuestion">What should we keep checking?</label>
        <p id="watchQuestionNote" class="watch-goal-hint">One question about something that will change: a release, a decision, a price.</p>
        <textarea id="watchQuestion" class="watch-condition-input watch-question-input" maxlength="2000" rows="3" placeholder="Example: When will OpenAI release GPT-6?" aria-describedby="watchQuestionNote watchQuestionError">${escapeHtml(initialQuestion || "")}</textarea>
        <p id="watchQuestionError" class="watch-field-error" role="alert" hidden></p>
      </div>`;
    const next = dialogButton("watchQuestionNext", "Continue", "primary");
    const cancel = dialogButton("watchCancelBtn", "Cancel");
    body.appendChild(dialogActions(next, cancel));
    const input = document.getElementById("watchQuestion");
    bindWatchFieldErrorReset(input, "input");
    cancel.addEventListener("click", closeDialog);
    next.addEventListener("click", () => {
      clearWatchFieldError(input);
      const question = normalizeWatchQuestion(input.value);
      if (question.length < WATCH_QUESTION_MIN_CHARS) {
        setWatchFieldError(input, "Enter a complete question so the models know what to evaluate.");
        focusWatchField(input);
        return;
      }
      // The same question as one already watched: say so now, not after the form.
      const existing = watchedFor(question);
      if (existing) {
        renderAlreadyWatching(existing, modalIntent);
        return;
      }
      // Goals belong to the question they were written for; schedule,
      // alerts, channels, page, details and origin carry over. "Only when
      // it is reached" needs a goal, so without one it is the first rule.
      const sameQuestion = question === normalizeWatchQuestion(initialQuestion);
      const settings = setup.settings && !sameQuestion && setup.settings.email_mode === "condition"
        ? { ...setup.settings, email_mode: "changes_only" } : setup.settings;
      renderConfirm({ interval: setup.interval, source: setup.source, settings,
        ...(sameQuestion ? { goal: setup.goal, goals: setup.goals } : {}), question }, modalIntent);
    });
    // A question is one line; Enter moves on, Shift+Enter still breaks.
    input.addEventListener("keydown", event => {
      if (event.key !== "Enter" || event.shiftKey || window.App.isComposingKey?.(event) || event.isComposing) return;
      event.preventDefault();
      if (!next.disabled) next.click();
    });
    refreshDialogWatchLimit();
    requestAnimationFrame(() => {
      focusQuietly(input);
      const end = input.value.length;
      try { input.setSelectionRange(end, end); } catch (_) { /* not a text field */ }
    });
  }

  // Suggestions cost a Judge call; going back to edit the question and
  // returning must not ask again for the same text.
  const goalSuggestionCache = new Map();

  function loadGoalSuggestions(question, intentIsCurrent) {
    if (goalSuggestionCache.has(question)) {
      return Promise.resolve(goalSuggestionCache.get(question));
    }
    return api("POST", "/api/watch/goal-suggestions", { question: question }, intentIsCurrent)
      .then(data => {
        const goals = Array.isArray(data.goals)
          ? data.goals.map(normalizeWatchQuestion).filter(Boolean) : [];
        if (goalSuggestionCache.size >= 20) goalSuggestionCache.clear();
        goalSuggestionCache.set(question, goals);
        return goals;
      });
  }

  // The goal suggestions are three rows at most; their places are held from
  // the first frame, so the list below never jumps when they arrive (J2).
  const GOAL_SUGGESTION_ROWS = 3;

  function renderConfirm(options, modalIntent) {
    const F = fields();
    const directQuestion = normalizeWatchQuestion(options?.question);
    const presetGoal = normalizeWatchQuestion(options?.goal);
    const suppliedGoals = Array.isArray(options?.goals)
      ? options.goals.map(normalizeWatchQuestion).filter(Boolean) : null;
    // What was set before "Edit" led back to the question (schedule, alerts,
    // channels, page, details, the open settings) comes back with it.
    const kept = options?.settings && typeof options.settings === "object" ? options.settings : null;
    const presetInterval = watchDefaults(kept?.interval || options?.interval).interval;
    const watchedQuestion = directQuestion || normalizeWatchQuestion(window.lastQuestion);
    const { title, body } = els();
    if (!body) return;
    title.textContent = "New watch";
    body.replaceChildren();
    const limitNote = document.createElement("div");
    limitNote.id = "watchDialogLimit";
    limitNote.className = "watch-limit-summary is-dialog";
    limitNote.setAttribute("aria-live", "polite");
    limitNote.hidden = true;
    body.appendChild(limitNote);
    if (watchedQuestion) body.appendChild(questionPreview(watchedQuestion, Boolean(directQuestion)));

    // --- What are you waiting for? -------------------------------------
    // One visible choice instead of chips above an empty field. "Any change
    // to the answer" is picked from the first frame, so what a quick Start
    // sends is what the reader sees (J16); arriving suggestions take the
    // pick over only while the reader has not chosen.
    const goals = F.goalList({ prefix: "watchGoal", name: "watchGoalChoice" });
    body.appendChild(goals.root);
    const goalInput = goals.input;
    const customChoice = goals.customChoice;
    const noneChoice = goals.anyChoice;
    const goalHint = goals.hint;
    const suggestions = goals.offered;
    let goalTouched = false;

    function selectedGoal() {
      const value = goals.value();
      return value.kind === "none" || !value.kind ? "" : value.goal;
    }
    function syncGoalHint() {
      const checked = goals.checked();
      goalHint.textContent = !checked || checked.value === "none"
        ? "You hear from us whenever a source changes the answer."
        : "When a source confirms it, you get the proof and the watch ends.";
    }
    function onGoalChange(keepError) {
      if (!keepError) clearWatchFieldError(goalInput);
      syncGoalHint();
      syncAlertLabels();
    }
    function offeredGoals(goalsList) {
      const offered = presetGoal ? [presetGoal] : [];
      goalsList.forEach(goal => {
        if (goal && !offered.includes(goal)) offered.push(goal);
      });
      return offered.slice(0, GOAL_SUGGESTION_ROWS + (presetGoal ? 1 : 0));
    }
    // Settled suggestions replace the held rows. The first offered row is
    // picked for the reader as long as they have not chosen anything; a
    // focus on the old pick follows it.
    function renderGoalOptions(goalsList) {
      const before = goals.checked();
      const hadFocus = before && document.activeElement === before;
      smoothHeight(suggestions, () => {
        goals.setOffered(offeredGoals(goalsList));
        suggestions.classList.toggle("is-empty", !suggestions.children.length);
        const radios = goals.offeredRadios();
        if (!goalTouched && radios[0]) radios[0].checked = true;
        else if (!goals.checked()) noneChoice.checked = true;
      }, { hold: goals.input.closest(".watch-goal-option") });
      const after = goals.checked();
      if (hadFocus && after && after !== before) focusQuietly(after);
      onGoalChange();
    }
    function renderGoalPlaceholders() {
      const known = offeredGoals([]);
      goals.setOffered(known);
      const loading = document.createElement("div");
      loading.className = "watch-goal-loading";
      loading.setAttribute("aria-hidden", "true");
      loading.innerHTML = '<span class="watch-goal-option is-loading"></span>'.repeat(GOAL_SUGGESTION_ROWS);
      suggestions.appendChild(loading);
      const status = document.createElement("span");
      status.className = "watch-sr-only";
      status.textContent = "Finding events you may be waiting for…";
      suggestions.appendChild(status);
      if (known.length) goals.select(known[0]);
      else noneChoice.checked = true;
    }

    goals.root.addEventListener("change", event => {
      if (event.target.name !== "watchGoalChoice") return;
      goalTouched = true;
      if (event.target === customChoice) goalInput.focus();
      onGoalChange();
    });
    // Focus alone selects the row but keeps a validation message: the
    // dialog itself focuses this field to show "Name the goal".
    goalInput.addEventListener("focus", () => {
      if (customChoice.checked) return;
      customChoice.checked = true;
      goalTouched = true;
      onGoalChange(true);
    });
    goalInput.addEventListener("input", () => {
      goalTouched = true;
      customChoice.checked = true;
      onGoalChange();
    });

    // --- Schedule, alerts, channels, page: one line until "Change" -------
    const advanced = document.createElement("details");
    advanced.id = "watchAdvancedSettings";
    advanced.className = "watch-settings";
    const summary = document.createElement("summary");
    summary.innerHTML = '<span id="watchSettingsSummary" class="watch-settings-summary"></span>'
      + '<span id="watchSettingsToggle" class="watch-settings-toggle">Change</span>';
    advanced.appendChild(summary);
    const settingsBody = document.createElement("div");
    settingsBody.className = "watch-settings-body";
    advanced.appendChild(settingsBody);
    body.appendChild(advanced);

    const detailsInput = F.detailsInput("watchDetails", kept?.details || "");
    settingsBody.appendChild(F.field({ label: "Details that matter", control: detailsInput, id: "watchDetails",
      hint: "Every check searches with these. The goal only counts when they fit." }));
    const intervalSelect = F.intervalSelect("watchInterval", presetInterval, dailyIntervalAllowed());
    const weekdaySelect = F.weekdaySelect("watchWeekday", kept?.run_weekday || browserTomorrowWeekday());
    const runTimeInput = F.timeInput("watchRunTime", kept?.run_time || "09:00");
    const grid = document.createElement("div");
    grid.className = "watch-config-grid";
    const weekdayField = F.field({ label: "Day", control: weekdaySelect, id: "watchWeekdayWrap" });
    weekdayField.id = "watchWeekdayWrap";
    grid.append(
      F.field({ label: "How often", control: intervalSelect }),
      weekdayField,
      F.field({ label: "Time", control: runTimeInput, id: "watchRunTime" })
    );
    settingsBody.appendChild(grid);
    const emailModeSelect = F.alertSelect("watchEmailMode", kept?.email_mode || "changes_only", Boolean(presetGoal));
    settingsBody.appendChild(F.field({ label: "Notify me", control: emailModeSelect, wide: true }));
    const channels = buildChannels({ idPrefix: "watch", email: kept ? kept.email_enabled !== false : true,
      telegram: kept?.telegram_enabled === true });
    settingsBody.appendChild(channels.field);
    const visibilitySelect = F.visibilitySelect("watchVisibility", kept?.visibility || "private");
    visibilitySelect.required = true;
    settingsBody.appendChild(F.field({ label: "Watch page", control: visibilitySelect, id: "watchVisibility" }));

    const confirm = dialogButton("watchConfirmBtn", "Start watching", "primary");
    const cancel = dialogButton("watchCancelBtn", "Cancel");
    body.appendChild(dialogActions(confirm, cancel));
    cancel.addEventListener("click", closeDialog);

    const emailEnabledInput = channels.email;
    const telegramEnabledInput = channels.telegram;
    const channelsError = channels.error;
    const settingsToggle = document.getElementById("watchSettingsToggle");
    const syncWeekday = () => {
      const hide = intervalSelect.value !== "weekly";
      if (weekdayField.hidden !== hide) smoothHeight(grid, () => { weekdayField.hidden = hide; });
    };
    intervalSelect.addEventListener("change", syncWeekday);
    syncWeekday();

    // The fields as POST /api/watch takes them; the summary line reads the same.
    function currentSettings() {
      return {
        interval: intervalSelect.value,
        run_weekday: intervalSelect.value === "weekly" ? weekdaySelect.value : "",
        email_mode: emailModeSelect.value,
        email_enabled: emailEnabledInput.checked,
        telegram_enabled: telegramEnabledInput.checked,
        visibility: visibilitySelect.value,
        run_time: runTimeInput.value
      };
    }
    function updateSetupSummary() {
      document.getElementById("watchSettingsSummary").textContent = settingsSummary(currentSettings());
    }
    function syncAlertLabels() {
      F.relabelAlerts(emailModeSelect, Boolean(selectedGoal()));
      updateSetupSummary();
    }
    [visibilitySelect, intervalSelect, weekdaySelect, emailModeSelect,
      emailEnabledInput, telegramEnabledInput].forEach(input => {
      input.addEventListener("change", updateSetupSummary);
    });
    runTimeInput.addEventListener("input", updateSetupSummary);
    // "Change" opens the settings below the line; the dialog grows down from
    // its fixed top edge, softly.
    summary.addEventListener("click", event => {
      event.preventDefault();
      smoothHeight(settingsBody.parentElement, () => { advanced.open = !advanced.open; });
    });
    advanced.addEventListener("toggle", () => {
      settingsToggle.textContent = advanced.open ? "Done" : "Change";
    });
    if (kept?.open) {
      advanced.open = true;
      settingsToggle.textContent = "Done";
    }

    renderGoalPlaceholders();
    syncGoalHint();
    updateSetupSummary();
    if (suppliedGoals) {
      renderGoalOptions(suppliedGoals);
    } else if (watchedQuestion.length >= WATCH_QUESTION_MIN_CHARS) {
      loadGoalSuggestions(watchedQuestion, () => watchModalIntentIsCurrent(modalIntent))
        .then(goalsList => {
          if (suggestions.isConnected) renderGoalOptions(goalsList);
        })
        .catch(() => {
          if (suggestions.isConnected) renderGoalOptions([]);
        });
    } else {
      renderGoalOptions([]);
    }

    // "Edit" changes only the question: everything set here comes back.
    document.getElementById("watchQuestionEdit")?.addEventListener("click", () => {
      renderQuestionStep(directQuestion, modalIntent,
        { ...options, goal: selectedGoal() || presetGoal, interval: intervalSelect.value,
          settings: { ...currentSettings(), details: detailsInput.value, open: advanced.open } });
    });

    bindWatchFieldErrorReset(visibilitySelect, "change");
    bindWatchFieldErrorReset(runTimeInput, "input");
    emailModeSelect.addEventListener("change", () => clearWatchFieldError(goalInput));
    if (!directQuestion && !window.lastShareResultId && window.currentBookmarkShareResultContext) {
      confirm.disabled = true;
      confirm.textContent = "Preparing saved consensus…";
      window.resolveCurrentShareResultId?.().then(resultId => {
        if (!confirm.isConnected) return;
        confirm.disabled = false;
        confirm.textContent = "Start watching";
        // A saved chat that could not be prepared says why (the server's
        // reason); the button stays to try again.
        if (!resultId) showDialogError(window.currentBookmarkShareResultError || "");
      });
    } else if (!directQuestion && !window.lastShareResultId) {
      confirm.disabled = true;
      confirm.textContent = "Nothing to watch yet";
    }
    refreshDialogWatchLimit();
    // The focus lands on the step's first choice, never on the page (J27).
    requestAnimationFrame(() => {
      if (!body.contains(document.activeElement)) focusQuietly(goals.checked() || confirm);
    });
    confirm.addEventListener("click", async function () {
      // A second try after a failed preparation asks the server again.
      if (!directQuestion) this.disabled = true;
      const resultId = directQuestion ? "" : await (window.resolveCurrentShareResultId?.()
        || Promise.resolve(window.lastShareResultId));
      if (!watchModalIntentIsCurrent(modalIntent)) return;
      this.disabled = false;
      if (!directQuestion && !resultId) {
        showDialogError(window.currentBookmarkShareResultError || "");
        return;
      }
      const visibility = visibilitySelect.value;
      const emailMode = emailModeSelect.value;
      const goal = selectedGoal();
      const runTime = runTimeInput.value;
      [visibilitySelect, runTimeInput, goalInput].forEach(clearWatchFieldError);
      showDialogError("");
      const invalidFields = [];
      if (customChoice.checked && !goal) {
        setWatchFieldError(goalInput, "Describe the event, or pick one of the options.");
        invalidFields.push(goalInput);
      } else if (emailMode === "condition" && !goal) {
        setWatchFieldError(goalInput, "Name the goal, or choose a different alert rule.");
        invalidFields.push(goalInput);
      }
      if (!visibility) {
        setWatchFieldError(visibilitySelect, "Choose whether this page should be private or public.");
        invalidFields.push(visibilitySelect);
      }
      if (!runTime) {
        setWatchFieldError(runTimeInput, "Choose a run time for the automatic check.");
        invalidFields.push(runTimeInput);
      }
      if (!emailEnabledInput.checked && !telegramEnabledInput.checked) {
        channelsError.textContent = "Keep at least one way to reach you.";
        channelsError.hidden = false;
        invalidFields.push(emailEnabledInput);
      }
      if (invalidFields.length) {
        focusWatchField(invalidFields[0]);
        return;
      }
      this.disabled = true;
      this.textContent = "Starting…";
      const question = directQuestion || watchedQuestion;
      const epoch = watchState.sessionEpoch;
      const onWatchPage = onWatchPagePath();
      // A dialog closed while the watch starts: the request went out, so
      // the watch is there all the same. It keeps its details, the page
      // behind shows it, and a line says what became of it. Closing it
      // dropped both before (review 2).
      const sameSession = () => Boolean(window.auth?.currentUser) && epoch === watchState.sessionEpoch;
      try {
        const payload = { ...currentSettings(), condition: goal, timezone: browserTimezone() };
        if (directQuestion) payload.question = directQuestion;
        else payload.result_id = resultId;
        const data = await api(
          "POST",
          "/api/watch",
          payload,
          () => watchModalIntentIsCurrent(modalIntent)
        );
        let watch = data.watch;
        // "Details that matter" ride along in the same step; the create
        // endpoint takes them through the watch's own update.
        const details = normalizeWatchQuestion(detailsInput.value);
        let detailsFailed = false;
        if (details && sameSession()) {
          try {
            const updated = await api("PATCH", "/api/watch/" + encodeURIComponent(watch.id), { requirements: details });
            watch = Object.assign({}, watch, updated.watch);
          } catch (_) {
            detailsFailed = true;
          }
        }
        if (!sameSession()) return;
        // Sidebar count, Watch buttons and Agent cards follow the new watch.
        loadWatchLimits(true).catch(() => {});
        const checked = goals.checked();
        window.App?.trackAppEvent?.("app_watch_created", {
          interval: watch.interval,
          source: options?.source || (directQuestion ? "query_first" : "consensus"),
          has_goal: Boolean(goal),
          goal_source: checked ? checked.value : "none"
        });
        if (!watchModalIntentIsCurrent(modalIntent)) {
          if (onWatchPage && onWatchPagePath()) window.App.watchDashboard?.addCreated?.(watch);
          window.App?.toast?.({
            message: detailsFailed ? "Watch started, but its details couldn’t be saved" : "Watch started",
            action: onWatchPagePath() ? null : { label: "Open", onAction: () => openWatchDashboard({ focus: watch.id }) },
          });
          return;
        }
        renderSuccess(watch, modalIntent, { detailsFailed });
      } catch (error) {
        if (error?.stale) return;
        if (!watchModalIntentIsCurrent(modalIntent)) {
          if (sameSession()) {
            window.App?.toast?.(isAlreadyWatched(error) ? { message: "You already watch this question" }
              : { tone: "error", message: "Watch not started. " + window.App.userError(error, { fallback: "Try again." }) });
          }
          return;
        }
        this.disabled = false;
        this.textContent = "Start watching";
        if (isAlreadyWatched(error)) {
          await loadWatchLimits(true).catch(() => {});
          if (!watchModalIntentIsCurrent(modalIntent)) return;
          renderAlreadyWatching(watchedFor(question) || { id: error.watchId, question }, modalIntent);
          return;
        }
        if (error.status === 429 && error.code !== "rate_limited") {
          watchState.setLimits(null);
          await loadWatchLimits(true).catch(() => {});
          if (!watchModalIntentIsCurrent(modalIntent)) return;
          // A slot that frees up brings this form back as it was.
          const kept = { ...options, goal: selectedGoal() || presetGoal, interval: intervalSelect.value,
            settings: { ...currentSettings(), details: detailsInput.value, open: advanced.open } };
          renderLimitStep(modalIntent, { resume: () => renderConfirm(kept, modalIntent) });
          return;
        }
        showDialogError(error.code === "rate_limited"
          ? window.App.userError(error) : "Watch not started. " + window.App.userError(error, { fallback: "Try again." }));
      }
    });
  }

  // E-mail and Telegram as one group of boxes (never a label around both,
  // J10). Without a configured bot Telegram is noise; unconnected, it says
  // why it is off and offers the connection beside it (J19).
  function buildChannels({ idPrefix = "", email = true, telegram = false, onChange } = {}) {
    const F = fields();
    const group = document.createElement("div");
    group.className = "watch-channel-options";
    const make = (id, label) => {
      const wrap = document.createElement("label");
      wrap.className = "watch-channel-option";
      const box = document.createElement("input");
      box.type = "checkbox";
      if (id) box.id = id;
      wrap.append(box, document.createTextNode(" " + label));
      group.appendChild(wrap);
      return { wrap, box };
    };
    const mail = make(idPrefix ? idPrefix + "EmailEnabled" : "", "Email");
    mail.box.checked = email;
    const tg = make(idPrefix ? idPrefix + "TelegramEnabled" : "", "Telegram");
    if (idPrefix) tg.wrap.id = idPrefix + "TelegramOption";
    tg.box.checked = telegram;
    tg.box.disabled = true;
    const connect = document.createElement("button");
    connect.type = "button";
    connect.className = "wd-link watch-telegram-connect";
    if (idPrefix) connect.id = idPrefix + "TelegramConnect";
    connect.textContent = "Connect Telegram";
    connect.hidden = true;
    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.className = "wd-link watch-telegram-cancel";
    cancel.textContent = "Cancel";
    cancel.hidden = true;
    group.append(connect, cancel);
    const field = F.field({ label: "Send to", control: group, group: true, id: idPrefix ? idPrefix + "Channels" : "" });
    const note = document.createElement("p");
    note.className = "watch-field-hint watch-telegram-note";
    note.hidden = true;
    field.insertBefore(note, field.querySelector(".watch-field-error"));
    const error = field.querySelector(".watch-field-error");
    let telegramState = { configured: false, connected: false };
    // Only the place the reader connected from ticks its box afterwards;
    // other open settings just learn that Telegram is there now.
    let initiated = false;

    function sync(state = telegramState) {
      telegramState = state || { configured: false, connected: false };
      const status = telegramStatus();
      tg.wrap.hidden = !telegramState.configured;
      tg.box.disabled = !telegramState.connected;
      if (!telegramState.connected) tg.box.checked = false;
      tg.wrap.title = telegramState.connected && telegramState.telegram_username
        ? "Connected as @" + telegramState.telegram_username : "";
      const offer = telegramState.configured && !telegramState.connected;
      connect.hidden = !offer;
      connect.disabled = status === "waiting";
      connect.textContent = status === "waiting" ? "Waiting for Telegram…" : "Connect Telegram";
      cancel.hidden = !(offer && status === "waiting");
      note.hidden = !offer;
      note.textContent = status === "waiting"
        ? "Press Start in Telegram. This updates by itself."
        : "Connect Telegram once to get messages there too.";
    }
    const unsubscribe = onTelegramStatus((state, detail) => {
      if (!group.isConnected) { unsubscribe(); return; }
      if (state === "connected") {
        sync(detail);
        if (!initiated) return;
        initiated = false;
        // Connected for this watch: the box is ticked, not left for later.
        tg.box.checked = true;
        tg.box.dispatchEvent(new Event("change", { bubbles: true }));
        F.markSaved(field, "Connected");
        return;
      }
      if (state !== "waiting") initiated = false;
      sync();
      if (state === "expired") F.setError(field, "The link expired. Connect again when you are ready.");
      if (state === "failed") F.setError(field, "Telegram couldn’t be connected. " + window.App.userError(detail, { fallback: "Try again." }));
    });
    connect.addEventListener("click", () => {
      F.setError(field, "");
      initiated = true;
      connectTelegram(state => {
        watchState.setTelegram(state);
      });
    });
    cancel.addEventListener("click", cancelTelegramPairing);
    [mail.box, tg.box].forEach(box => box.addEventListener("change", () => {
      F.setError(field, "");
      onChange?.(box === mail.box ? "email_enabled" : "telegram_enabled", box);
    }));
    if (watchState.telegram) sync(watchState.telegram);
    else {
      sync();
      if (window.auth?.currentUser) loadTelegramState().then(sync).catch(() => sync());
    }
    return { field, email: mail.box, telegram: tg.box, error, sync, connect };
  }

  // A question this account already watches (J17): what holds now and the
  // way to it, instead of a form that ends in "already watched".
  function renderAlreadyWatching(watch, modalIntent) {
    if (!watchModalIntentIsCurrent(modalIntent)) return;
    const { title, body } = els();
    if (!body) return;
    const paused = watch.status && !["active", "resolved"].includes(watch.status);
    title.textContent = "Watching";
    body.replaceChildren();
    if (watch.question) body.appendChild(questionPreview(watch.question, false));
    const card = document.createElement("div");
    card.className = "watch-success-card";
    card.innerHTML = '<span class="watch-success-icon" aria-hidden="true">✓</span><div><strong></strong><p></p></div>';
    card.querySelector("strong").textContent = watch.status === "resolved"
      ? "You watched this question until its goal was reached."
      : paused ? "You already watch this question. The watch is paused."
        : "You already watch this question.";
    card.querySelector("p").textContent = watch.interval ? fields().checksSentence(watch) : "";
    body.appendChild(card);
    const open = dialogButton("watchOpenExisting", "Open watch", "primary");
    const close = dialogButton("watchCancelBtn", "Close");
    body.appendChild(dialogActions(open, close));
    open.addEventListener("click", () => openWatchDashboard({ focus: watch.id }));
    close.addEventListener("click", closeDialog);
    requestAnimationFrame(() => focusQuietly(open));
  }

  // All slots in use (J25): said before any typing, with the way out.
  // `resume` renders the form this step stands in for: a slot that frees up
  // while the step is open (a deletion whose Undo passed, a watch paused or
  // deleted elsewhere) brings it back, instead of the step standing on "all
  // in use" (review 2). `reload` asks the server once, as the cached list
  // may be older than this account's other tabs.
  function renderLimitStep(modalIntent, { resume = null, reload = false } = {}) {
    if (!watchModalIntentIsCurrent(modalIntent)) return;
    const { title, body } = els();
    if (!body) return;
    const limits = watchState.limits;
    title.textContent = "New watch";
    body.replaceChildren();
    const card = document.createElement("div");
    card.id = "watchDialogLimit";
    card.className = "watch-limit-step";
    const text = document.createElement("p");
    text.textContent = limits ? limitMessage(limits) : "All watch slots are in use. Pause one to start another.";
    card.appendChild(text);
    const detail = document.createElement("p");
    detail.className = "watch-field-hint";
    detail.textContent = "Paused watches don’t count, and you can resume them any time.";
    card.appendChild(detail);
    if ((window.App.normalizeTier?.(limits?.plan) || "free") === "free") {
      const about = document.createElement("button");
      about.type = "button";
      about.className = "watch-limit-upgrade";
      about.textContent = "About early access";
      about.addEventListener("click", showWatchCostInfo);
      card.appendChild(about);
    }
    body.appendChild(card);
    const show = dialogButton("watchShowList", "Show my watches", "primary");
    const close = dialogButton("watchCancelBtn", "Close");
    body.appendChild(dialogActions(show, close));
    show.addEventListener("click", () => {
      closeDialog();
      openWatchDashboard({ focusList: true });
    });
    close.addEventListener("click", closeDialog);
    requestAnimationFrame(() => focusQuietly(show));
    if (typeof resume !== "function") return;
    const follow = () => {
      if (!card.isConnected || !watchModalIntentIsCurrent(modalIntent)) {
        window.removeEventListener("consensio:watches-changed", follow);
        return;
      }
      const now = watchState.limits;
      if (!now) return;
      if (now.atLimit) {
        text.textContent = limitMessage(now);
        return;
      }
      window.removeEventListener("consensio:watches-changed", follow);
      resume();
    };
    window.addEventListener("consensio:watches-changed", follow);
    if (reload) loadWatchLimits(true).catch(() => {});
  }

  function renderSuccess(watch, modalIntent, { detailsFailed = false } = {}) {
    if (!watchModalIntentIsCurrent(modalIntent)) return;
    const { title, body } = els();
    title.textContent = "Watching";
    const onWatchPage = onWatchPagePath();
    body.innerHTML = `
      <div class="watch-success-card">
        <span class="watch-success-icon" aria-hidden="true">✓</span>
        <div>
          <strong id="watchStartSummary"></strong>
          <p id="watchMailSummary"></p>
          <p id="watchDetailsNote" class="watch-field-error" hidden></p>
        </div>
      </div>`;
    const done = dialogButton("watchDoneBtn", "Done", "primary");
    const buttons = [done];
    if (!onWatchPage) buttons.push(dialogButton("watchListLink", "Open Watches", "link"));
    body.appendChild(dialogActions(...buttons));
    document.getElementById("watchStartSummary").textContent = fields().checksSentence(watch, { period: false });
    const goal = String(watch.condition || "").trim();
    document.getElementById("watchMailSummary").textContent = watch.email_mode === "every_run"
      ? "You get every check, including the answer."
      : goal
        ? (watch.email_mode === "condition"
          ? `We write when a source confirms “${goal}”.`
          : `We write when a source confirms “${goal}”, and whenever the answer changes before that.`)
        : "We write only when a source changes the answer.";
    if (detailsFailed) {
      const note = document.getElementById("watchDetailsNote");
      note.textContent = "Your details could not be saved. Add them under Settings on the card.";
      note.hidden = false;
    }
    // On the Watch page the new watch appears at the top of the list behind
    // the dialog, at once and marked, not after a reload far below (J15) --
    // however the dialog is closed: Done, the cross, Esc or a step away.
    const card = body.querySelector(".watch-success-card");
    const epoch = watchState.sessionEpoch;
    let revealed = false;
    const reveal = () => {
      if (revealed) return;
      revealed = true;
      els().modal?.removeEventListener("close", onClose);
      // Only the list this dialog stood over ("Open Watches" opens the page
      // with the watch in focus by itself), and never after a logout closed it.
      if (!onWatchPage || !onWatchPagePath() || !window.auth?.currentUser || epoch !== watchState.sessionEpoch) return;
      window.App.watchDashboard?.addCreated?.(watch);
    };
    // A later step in the same dialog (another watch) is not this one's close.
    const onClose = () => { if (card.isConnected) reveal(); else els().modal?.removeEventListener("close", onClose); };
    els().modal?.addEventListener("close", onClose);
    done.addEventListener("click", () => {
      closeDialog();
      reveal();
    });
    document.getElementById("watchListLink")?.addEventListener("click", () => {
      closeDialog();
      openWatchDashboard({ focus: watch.id });
    });
    requestAnimationFrame(() => focusQuietly(done));
  }

  function makeButton(label, className, handler) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = className;
    button.textContent = label;
    button.addEventListener("click", handler);
    return button;
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
        if (!window.auth?.currentUser || onWatchPagePath() || document.getElementById("watchFeatureNudge")) return;
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
    if (options.focus || options.focusList) {
      Promise.resolve(rendering).then(() => {
        if (options.focus) window.App.watchDashboard?.focusWatch?.(options.focus);
      });
    }
  }

  // Guests see the page too: what a watch is, by example, and the way in
  // (J3) -- no toast that says "log in" and leaves them where they were.
  function openWatchDashboard(options = {}) {
    // Share and Watch share one modal node. A navigation to the full Watch
    // view must never leave the previous Share surface floating above it.
    closeDialog();
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
    // /app/watches?create=1 (the public watch page's invitation): the dialog
    // opens once the session is known; a guest is asked to sign in first.
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
        if (wantsCreate) openWatchDialog("create", { source: "watch_page" });
        return;
      }
      if (window.__consensioAuthState?.known === true || Date.now() - startedAt >= 8000) {
        window.App.watchDashboard?.renderGuest?.();
        if (wantsCreate) requireAccount({}, document.getElementById("watchDashCreate"));
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
  // Watch buttons under an answer (Consensus footer, Agent answer): the
  // same pill in both modes (J20); a watched question reads "Watching" and
  // opens its watch (J17).
  // ------------------------------------------------------------------
  const EYE_ICON = '<svg class="share-pill-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M3 12s3.5-6 9-6 9 6 9 6-3.5 6-9 6-9-6-9-6Z"></path><circle cx="12" cy="12" r="2.5"></circle></svg>';
  const answerButtons = new Set();

  // Also off the page: a history turn is built before it is inserted.
  function syncWatchPill(button) {
    if (!button) return;
    const watch = watchedFor(button._watchQuestion?.());
    const watching = Boolean(watch);
    const label = button.querySelector("span");
    const text = watching ? "Watching" : "Watch";
    if (label && label.textContent !== window.App.t(text)) label.textContent = text;
    button.classList.toggle("is-watching", watching);
    const description = watching ? "You watch this question. Open it on Watches." : "Watch this question for changes";
    button.title = description;
    button.setAttribute("aria-label", description);
  }

  function watchPill(id, question, onStart) {
    const button = document.createElement("button");
    button.type = "button";
    if (id) button.id = id;
    button.className = "consensus-share-pill watch-consensus-pill";
    button.innerHTML = EYE_ICON + "<span>Watch</span>";
    button._watchQuestion = question;
    button.addEventListener("click", () => {
      dismissWatchFeatureNudge("opened");
      const watch = watchedFor(question());
      if (watch) openWatchDashboard({ focus: watch.id });
      else onStart(button);
    });
    answerButtons.add(button);
    return button;
  }

  function syncConsensusWatchButton() {
    const button = document.getElementById("consensusWatchButton");
    if (button) syncWatchPill(button);
  }

  function initWatchButton() {
    const bar = document.querySelector("#consensusResponse .consensus-copy-inline");
    if (!bar || document.getElementById("consensusWatchButton")) return;
    const button = watchPill("consensusWatchButton",
      () => normalizeWatchQuestion(window.lastQuestion),
      trigger => openWatchDialog("confirm", { trigger }));
    const anchor = document.createElement("span");
    anchor.className = "watch-feature-anchor";
    anchor.appendChild(button);
    const actions = bar.querySelector(".consensus-actions-wrapper");
    bar.insertBefore(anchor, actions || null);
    syncWatchPill(button);
    // A bookmark or a new run changes the question under the same button.
    const answer = document.getElementById("consensusAnswerBody");
    if (answer && typeof MutationObserver === "function") {
      new MutationObserver(syncConsensusWatchButton).observe(answer, { childList: true });
    }
  }

  // The Agent answer's pill, right after its evidence row (Sources ·
  // Answers · Differences) in the same line, on phones on the next one;
  // without an evidence row, on a line of its own under the answer.
  // Every finished Agent answer has one (Max, Apple-Audit J20): the live
  // answer (agent-chat.js, on every projection), a reopened chat's answer
  // and each Agent turn of the history (thread-history.js, built off the
  // page, `history: true`). The pill carries the question of its own turn,
  // set on every call; a follow-up opens at the question so it can stand
  // alone. Only the live answer's pill is #agentAnswerWatchButton.
  const LIVE_PILL_ID = "agentAnswerWatchButton";

  function syncAnswerWatchButton(answerBody, { question = "", eligible = false, followUp = false, history = false } = {}) {
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
      button = watchPill(history ? "" : LIVE_PILL_ID, () => answerBody._watchPill?._question || text,
        trigger => openWatchDialog("create", { question: button._question, editQuestion: button._followUp, source: "agent_answer", trigger }));
      button.classList.add("agent-watch-pill");
      answerBody._watchPill = button;
    }
    button._question = text;
    button._followUp = followUp;
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

  function initDashboardCreateButton() {
    document.getElementById("watchDashCreate")?.addEventListener("click", event => {
      openWatchDialog("create", { trigger: event.currentTarget, source: "dashboard" });
    });
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

  window.openWatchDialog = openWatchDialog;
  window.openWatchDashboard = openWatchDashboard;
  window.App.watch = Object.assign(window.App.watch || {}, {
    showFeatureNudge: showWatchFeatureNudge,
    refreshQuota: () => loadWatchLimits(true),
    // Slots and watched questions, loaded once per session (Agent cards).
    loadState: () => loadWatchLimits(false),
    watchedFor: watchedFor,
    answerButton: syncAnswerWatchButton,
    resetAfterLogout: resetAfterLogout
  });
  // Shared with watch-dashboard.js, which renders /app/watches, and with
  // agent-watch.js, the Watch card under an Agent answer.
  window.App.watchUi = {
    api: api,
    isAlreadyWatched: isAlreadyWatched,
    watchDefaults: watchDefaults,
    settingsSummary: settingsSummary,
    limitMessage: limitMessage,
    receiveWatchList: receiveWatchList,
    requestWatchList: requestWatchList,
    loadTelegramState: loadTelegramState,
    popup: popup,
    escapeHtml: escapeHtml,
    makeButton: makeButton,
    browserWeekday: browserWeekday,
    browserTimezone: browserTimezone,
    dailyIntervalAllowed: dailyIntervalAllowed,
    buildChannels: buildChannels,
    connectTelegram: connectTelegram,
    cancelTelegramPairing: cancelTelegramPairing,
    onTelegramStatus: onTelegramStatus,
    telegramStatus: telegramStatus,
    normalizeWatchLimits: normalizeWatchLimits,
    renderWatchLimit: renderWatchLimit,
    openWatchDialog: openWatchDialog,
    requireAccount: requireAccount,
    onWatchPagePath: onWatchPagePath,
    smoothHeight: smoothHeight,
    reducedMotion: reducedMotion
  };
  initWatchButton();
  initViewSwitch();
  initDashboardCreateButton();
  initWatchPageRoute();
  window.addEventListener("consensio:auth-state", event => {
    const uid = event.detail?.uid || null;
    const changed = watchState.updateAuthUid(uid);
    // A logout anywhere (also in the chat) lets the next login look again.
    if (!uid) firstLookFor = "";
    if (uid && window.auth?.currentUser?.uid === uid) {
      // Watch buttons know their state from the first answer on.
      loadWatchLimits(false).catch(() => {});
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
