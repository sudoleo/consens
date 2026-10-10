// Consensus Watch UI. Classic script/module contract: exports window.openWatchDialog
// (create dialog + dashboard) and window.openWatchDashboard (dashboard only).
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
  const WATCH_WEEKDAYS = [
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"
  ];
  let featureNudgeTimer = null;
  let featureNudgeAnchor = null;
  let featureNudgeQuestion = "";
  let featureNudgePositionHandler = null;
  const watchState = window.App.watchState;

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
  // malen. Die Position folgt trotzdem dem Watch-Knopf.
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

    nudge.style.maxHeight = `${Math.max(80, Math.floor(limit - edge * 2))}px`;
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

    nudge.classList.toggle("is-above", placeAbove);
    nudge.style.left = `${Math.round(left)}px`;
    nudge.style.top = `${Math.round(top)}px`;
    // An anchor in a hidden view (another mode took over) has no box.
    nudge.style.visibility = anchor.getClientRects().length ? "visible" : "hidden";
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
      nudge.setAttribute("aria-label", "New Consensus Watch feature");
      // Der Hinweis war frueher nur ein Hinweis: er erklaerte die Funktion und
      // liess den Nutzer dann den Watch-Knopf suchen. Jetzt steht die Aktion
      // selbst darin — ein Klick, fertige Voreinstellungen. Der Preis dafuer
      // ist Ehrlichkeit ueber die Benachrichtigung: nur bei einer echten
      // Aenderung, sonst nie. Genau das steht neben dem Knopf.
      nudge.innerHTML = `
        <button type="button" class="watch-feature-nudge-close" aria-label="Dismiss new feature tip">&#10005;</button>
        <span class="watch-feature-nudge-label">New</span>
        <strong>Keep this answer current</strong>
        <span class="watch-feature-nudge-copy">We re-check it across model families and write only when a source moves the answer.</span>
        <button type="button" class="watch-nudge-btn" id="watchNudgeStart">Watch this question</button>
        <span class="watch-nudge-meta">Weekly &middot; e-mail only on evidence &middot; stop anytime</span>
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
    if (!window.auth?.currentUser) {
      popup("Please log in to use Consensus Watch.");
      return;
    }
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
      button.textContent = "Watch this question";
      // Kontingent voll oder Server-Fehler: der Dialog kann mehr erklaeren
      // (Limits, Upgrade, Telegram) als dieser Streifen.
      if (error.status === 429) {
        watchState.setLimits(null);
        const question = featureNudgeQuestion;
        dismissWatchFeatureNudge("limit");
        if (question) openWatchDialog("create", { question });
        else openWatchDialog("confirm");
        return;
      }
      popup("Watch could not be started: " + error.message);
    }
  }

  // Der Hinweis bleibt stehen und wird zur Bestaetigung: der Nutzer soll
  // sehen, was er gerade ausgeloest hat — vor allem, dass er nur bei einer
  // Aenderung etwas hoert.
  function renderNudgeSuccess(watch) {
    const nudge = document.getElementById("watchFeatureNudge");
    if (!nudge) return;
    nudge.innerHTML = `
      <button type="button" class="watch-feature-nudge-close" aria-label="Dismiss">&#10005;</button>
      <span class="watch-feature-nudge-label is-active">Watching</span>
      <strong>You are set</strong>
      <span class="watch-feature-nudge-copy">First check: ${escapeHtml(formatWatchSchedule(watch))}. We only write when a source moves the answer.</span>
      <button type="button" class="watch-nudge-skip" id="watchNudgeOpenDash">Manage your watches</button>
    `;
    nudge.querySelector(".watch-feature-nudge-close").addEventListener("click", event => {
      event.stopPropagation();
      dismissWatchFeatureNudge("created");
    });
    nudge.querySelector("#watchNudgeOpenDash").addEventListener("click", event => {
      event.stopPropagation();
      dismissWatchFeatureNudge("created");
      openWatchDashboard();
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
    if (modal) modal.style.display = "none";
  }

  function popup(message) {
    window.App?.showPopup?.(message);
  }

  function watchModalIntentIsCurrent(intent) {
    if (window.App?.sharedModal?.isCurrent) {
      return window.App.sharedModal.isCurrent(intent);
    }
    const { modal } = els();
    return modal?.style.display === "flex"
      && modal.classList.contains("is-watch-dialog");
  }

  async function api(method, path, body, intentIsCurrent) {
    const user = window.auth?.currentUser;
    if (!user) throw new Error("Please log in first.");
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
      body: body ? JSON.stringify(body) : undefined
    });
    let data = {};
    try { data = await response.json(); } catch (_) { /* empty body */ }
    if (requestEpoch !== watchState.sessionEpoch || window.auth?.currentUser?.uid !== userUid) {
      throw new Error("Authentication changed.");
    }
    if (!response.ok) {
      const error = new Error(data.error || data.detail || ("HTTP " + response.status));
      error.status = response.status;
      throw error;
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

  async function loadWatchLimits(force) {
    if (watchState.limits && watchState.watches && !force) return watchState.limits;
    if (watchState.limitRequest && !force) return watchState.limitRequest;
    const request = api("GET", "/api/my/watches")
      .then(receiveWatchList)
      .finally(() => {
        if (watchState.limitRequest === request) watchState.setLimitRequest(null);
      });
    watchState.setLimitRequest(request);
    return watchState.limitRequest;
  }

  function showWatchCostInfo() {
    window.App?.showAccessInfo?.();
  }

  function renderSidebarWatchQuota(limits) {
    const target = document.getElementById("watchUsageDisplay");
    if (!target || !limits) return;
    target.innerHTML = `Watches: <strong>${limits.activeCount} / ${limits.activeLimit}</strong>`;
  }

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
      ? "Limit reached"
      : `${limits.remaining} slot${limits.remaining === 1 ? "" : "s"} available`;
    const meterWidth = limits.activeLimit > 0
      ? Math.min(100, Math.round((limits.activeCount / limits.activeLimit) * 100)) : 100;
    target.hidden = false;
    target.classList.toggle("is-full", limits.atLimit);
    target.innerHTML = `
      <div class="watch-limit-main">
        <span class="watch-limit-plan">${planLabel}</span>
        <strong>${activeLabel}</strong>
        <span>${availabilityLabel}</span>
        <span class="watch-limit-meter" aria-hidden="true"><i style="width:${meterWidth}%"></i></span>
      </div>
      <div class="watch-limit-detail">
        <span>Paused Watches do not count.</span>
        ${isFree ? `<span>Watch slots and check intervals are limited during early access.</span><button type="button" class="watch-limit-upgrade">About early access</button>` : ""}
      </div>`;
    target.querySelector(".watch-limit-upgrade")?.addEventListener("click", showWatchCostInfo);
  }

  // Why no new Watch can start: the create dialog and the Agent card say the
  // same sentence.
  function limitMessage(limits) {
    return limits.activeLimit > 1
      ? `All ${limits.activeLimit} Watch slots are in use. Pause one to start a new Watch.`
      : limits.activeLimit === 1
        ? "Your Watch slot is in use. Pause that Watch to start a new one."
        : "Watches are not available for your account yet.";
  }

  // The dialog only mentions the limit when it blocks: the sidebar and the
  // dashboard already carry the count, the dialog is about the question.
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

  function applyDialogWatchLimit(limits) {
    const target = document.getElementById("watchDialogLimit");
    if (!target || !limits) return;
    renderDialogWatchLimit(target, limits);
    const action = document.getElementById("watchQuestionNext")
      || document.getElementById("watchConfirmBtn");
    if (!action || !limits.atLimit) return;
    action.disabled = true;
    action.textContent = "Watch limit reached";
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

  async function connectTelegram(onConnected) {
    let pendingWindow = null;
    try {
      pendingWindow = window.open("about:blank", "_blank");
      if (pendingWindow) pendingWindow.opener = null;
      const data = await api("POST", "/api/my/telegram/link", {});
      if (pendingWindow) pendingWindow.location = data.url;
      else window.location.href = data.url;
      popup("Start the bot in Telegram. This page will detect the connection automatically.");
      for (let attempt = 0; attempt < 20; attempt += 1) {
        await new Promise(resolve => setTimeout(resolve, 2000));
        const state = await loadTelegramState(true);
        if (state.connected) {
          popup("Telegram connected.");
          onConnected?.(state);
          return state;
        }
      }
      popup("Connection not detected yet. Finish /start in Telegram, then refresh this page.");
    } catch (error) {
      try { pendingWindow?.close(); } catch (_) { /* ignored */ }
      popup("Telegram connection failed: " + error.message);
    }
    return null;
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

  function intervalOptions(selected) {
    const dailyDisabled = !dailyIntervalAllowed();
    return `
      <option value="weekly"${selected === "weekly" ? " selected" : ""}>Weekly</option>
      <option value="monthly"${selected === "monthly" ? " selected" : ""}>Monthly</option>
      <option value="daily"${selected === "daily" ? " selected" : ""}${dailyDisabled ? " disabled" : ""}>Daily${dailyDisabled ? " (Pro)" : ""}</option>
    `;
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

  function weekdayOptions(selected) {
    const current = WATCH_WEEKDAYS.includes(selected) ? selected : browserWeekday();
    return WATCH_WEEKDAYS.map(day =>
      `<option value="${day}"${day === current ? " selected" : ""}>${day[0].toUpperCase() + day.slice(1)}</option>`
    ).join("");
  }

  // "Weekly on Sunday at 09:00 · E-mail · Private": schedule, channels,
  // alert rule (only when not the default) and page of a Watch's settings,
  // in the create dialog and on the Agent card.
  function settingsSummary(settings) {
    const interval = settings.interval;
    let schedule = interval === "daily" ? "Daily" : interval === "monthly" ? "Monthly" : "Weekly";
    if (interval === "weekly" && WATCH_WEEKDAYS.includes(settings.run_weekday)) {
      schedule += " on " + settings.run_weekday[0].toUpperCase() + settings.run_weekday.slice(1);
    }
    if (settings.run_time) schedule += " at " + settings.run_time;
    const channels = [
      settings.email_enabled ? "E-mail" : "",
      settings.telegram_enabled ? "Telegram" : ""
    ].filter(Boolean).join(" + ") || "No channel";
    const parts = [schedule, channels];
    if (settings.email_mode === "every_run") parts.push("Every check");
    if (settings.email_mode === "condition") parts.push("Only when it resolves");
    parts.push(settings.visibility === "public" ? "Public" : "Private");
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
    return (watchState.watches || []).find(watch => questionKey(watch.question) === key) || null;
  }

  function formatWatchSchedule(watch) {
    let label = String(watch.interval || "weekly");
    if (watch.interval === "weekly" && WATCH_WEEKDAYS.includes(watch.run_weekday)) {
      label += " on " + watch.run_weekday[0].toUpperCase() + watch.run_weekday.slice(1);
    }
    if (watch.run_time) {
      label += " at " + watch.run_time + (watch.timezone ? " (" + watch.timezone + ")" : "");
    }
    return label;
  }

  function browserTimezone() {
    try {
      return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
    } catch (_) {
      return "UTC";
    }
  }

  // Alert rules in the words of the evidence model: a watch writes when a
  // source moves the answer, when its goal is reached, or after every check.
  function emailModeOptions(selected, hasGoal) {
    return `
      <option value="changes_only"${selected === "changes_only" || !selected ? " selected" : ""}>${hasGoal ? "When it moves or resolves" : "When it moves on evidence"}</option>
      <option value="condition"${selected === "condition" ? " selected" : ""}>Only when it resolves</option>
      <option value="every_run"${selected === "every_run" ? " selected" : ""}>After every check</option>
    `;
  }

  function bindWeekdayVisibility(intervalSelect, wrapper) {
    if (!intervalSelect || !wrapper) return;
    const sync = () => { wrapper.hidden = intervalSelect.value !== "weekly"; };
    intervalSelect.addEventListener("change", sync);
    sync();
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

  function setWatchFieldError(field, message) {
    if (!field) return;
    field.setAttribute("aria-invalid", "true");
    const error = document.getElementById(field.id + "Error");
    if (error) {
      error.textContent = message;
      error.hidden = false;
    }
  }

  function focusWatchField(field) {
    if (!field) return;
    const collapsedSection = field.closest("details:not([open])");
    if (collapsedSection) collapsedSection.open = true;
    field.scrollIntoView({ behavior: "smooth", block: "center" });
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

  const WATCH_QUESTION_MIN_CHARS = 8;

  function openWatchDialog(view, options) {
    if (!window.auth?.currentUser) {
      popup("Please log in to use Consensus Watch.");
      return;
    }
    if (view === "list") {
      closeDialog();
      openWatchDashboard();
      return;
    }
    const { modal } = els();
    if (!modal) return;
    let modalIntent = null;
    if (window.App?.sharedModal?.open) {
      modalIntent = window.App.sharedModal.open("watch");
    } else {
      modal.classList.add("is-watch-dialog");
      modal.style.display = "flex";
    }
    if (view !== "create") {
      renderConfirm(undefined, modalIntent);
      return;
    }
    // A question that is already known (an example, the chat's last
    // question, an Agent proposal) goes straight to the goal; "Edit" leads
    // back to the field. Options: question, goal (the preset choice), goals
    // (suggestions the caller already has, so none are fetched), interval and
    // source (analytics).
    const setup = options || {};
    const knownQuestion = normalizeWatchQuestion(setup.question);
    if (knownQuestion.length >= WATCH_QUESTION_MIN_CHARS) {
      renderConfirm({ ...setup, question: knownQuestion }, modalIntent);
    } else {
      renderQuestionStep(setup.question, modalIntent, setup);
    }
  }

  function normalizeWatchQuestion(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
  }

  function renderQuestionStep(initialQuestion, modalIntent, setup = {}) {
    const { title, body } = els();
    if (!body) return;
    title.textContent = "New Watch";
    body.innerHTML = `
      <div id="watchDialogLimit" class="watch-limit-summary is-dialog" aria-live="polite" hidden></div>
      <div class="watch-question-field">
        <label class="watch-goal-label" for="watchQuestion">What should we keep checking?</label>
        <p id="watchQuestionNote" class="watch-goal-hint">One question about something that will change: a release, a decision, a price.</p>
        <textarea id="watchQuestion" class="watch-condition-input watch-question-input" maxlength="2000" rows="3" placeholder="Example: When will OpenAI release GPT-6?" aria-describedby="watchQuestionNote watchQuestionError">${escapeHtml(initialQuestion || "")}</textarea>
        <p id="watchQuestionError" class="watch-field-error" role="alert" hidden></p>
      </div>
      <div class="share-modal-actions">
        <button type="button" id="watchQuestionNext" class="share-primary-btn">Continue</button>
        <button type="button" id="watchCancelBtn" class="share-secondary-btn">Cancel</button>
      </div>`;
    const input = document.getElementById("watchQuestion");
    const next = document.getElementById("watchQuestionNext");
    bindWatchFieldErrorReset(input, "input");
    document.getElementById("watchCancelBtn").addEventListener("click", closeDialog);
    next.addEventListener("click", () => {
      clearWatchFieldError(input);
      const question = normalizeWatchQuestion(input.value);
      if (question.length < WATCH_QUESTION_MIN_CHARS) {
        setWatchFieldError(input, "Enter a complete question so the models know what to evaluate.");
        focusWatchField(input);
        return;
      }
      // Goals belong to the question they were written for; schedule and
      // origin carry over.
      const sameQuestion = question === normalizeWatchQuestion(initialQuestion);
      renderConfirm({ interval: setup.interval, source: setup.source,
        ...(sameQuestion ? { goal: setup.goal, goals: setup.goals } : {}), question }, modalIntent);
    });
    // A question is one line; Enter moves on, Shift+Enter still breaks.
    input.addEventListener("keydown", event => {
      if (event.key !== "Enter" || event.shiftKey || event.isComposing) return;
      event.preventDefault();
      if (!next.disabled) next.click();
    });
    refreshDialogWatchLimit();
    requestAnimationFrame(() => input.focus());
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

  function renderConfirm(options, modalIntent) {
    const directQuestion = normalizeWatchQuestion(options?.question);
    const presetGoal = normalizeWatchQuestion(options?.goal);
    const suppliedGoals = Array.isArray(options?.goals)
      ? options.goals.map(normalizeWatchQuestion).filter(Boolean) : null;
    const presetInterval = watchDefaults(options?.interval).interval;
    const watchedQuestion = directQuestion || normalizeWatchQuestion(window.lastQuestion);
    const { title, body } = els();
    if (!body) return;
    title.textContent = directQuestion ? "New Watch" : "Watch this answer";
    body.innerHTML = `
      <div id="watchDialogLimit" class="watch-limit-summary is-dialog" aria-live="polite" hidden></div>
      ${watchedQuestion ? `<div class="watch-question-preview">
        <strong>${escapeHtml(watchedQuestion)}</strong>
        ${directQuestion ? '<button type="button" id="watchQuestionEdit" class="watch-question-edit">Edit</button>' : ""}
      </div>` : ""}
      <fieldset class="watch-goal" aria-describedby="watchGoalHint">
        <legend id="watchGoalLabel" class="watch-goal-label">What are you waiting for?</legend>
        <div class="watch-goal-options">
          <div id="watchGoalSuggestions" class="watch-goal-suggestions" aria-live="polite"></div>
          <div class="watch-goal-option is-custom">
            <input type="radio" name="watchGoalChoice" id="watchGoalCustomChoice" value="custom" aria-label="Something else">
            <input type="text" id="watchGoal" class="watch-goal-input" maxlength="500" placeholder="Something else…" aria-label="Something else: the event you are waiting for" aria-describedby="watchGoalError" autocomplete="off">
          </div>
          <label class="watch-goal-option">
            <input type="radio" name="watchGoalChoice" id="watchGoalNone" value="none">
            <span>Any change to the answer</span>
          </label>
        </div>
        <p id="watchGoalHint" class="watch-goal-hint"></p>
        <p id="watchGoalError" class="watch-field-error" role="alert" hidden></p>
      </fieldset>
      <details id="watchAdvancedSettings" class="watch-settings">
        <summary>
          <span id="watchSettingsSummary" class="watch-settings-summary"></span>
          <span id="watchSettingsToggle" class="watch-settings-toggle">Change</span>
        </summary>
        <div class="watch-settings-body">
          <div class="watch-config-grid">
            <div class="watch-config-field">
              <label class="watch-interval-label" for="watchInterval">How often</label>
              <select id="watchInterval" class="watch-interval-select">${intervalOptions(presetInterval)}</select>
            </div>
            <div id="watchWeekdayWrap" class="watch-config-field">
              <label class="watch-interval-label" for="watchWeekday">Day</label>
              <select id="watchWeekday" class="watch-interval-select">${weekdayOptions(browserTomorrowWeekday())}</select>
            </div>
            <div class="watch-config-field">
              <label class="watch-interval-label" for="watchRunTime">Time</label>
              <input id="watchRunTime" class="watch-time-input" type="time" value="09:00" required aria-describedby="watchRunTimeNote watchRunTimeError">
              <p id="watchRunTimeNote" class="watch-data-note"><span id="watchTimezoneLabel"></span></p>
              <p id="watchRunTimeError" class="watch-field-error" role="alert" hidden></p>
            </div>
          </div>
          <div class="watch-config-field">
            <label class="watch-interval-label" for="watchEmailMode">Notify me</label>
            <select id="watchEmailMode" class="watch-interval-select watch-email-select">${emailModeOptions("changes_only", Boolean(presetGoal))}</select>
          </div>
          <div class="watch-config-field">
            <span class="watch-interval-label">Send to</span>
            <div class="watch-channel-options">
              <label class="watch-channel-option"><input type="checkbox" id="watchEmailEnabled" checked> E-mail</label>
              <label id="watchTelegramOption" class="watch-channel-option"><input type="checkbox" id="watchTelegramEnabled" disabled> Telegram</label>
              <button type="button" id="watchTelegramConnect" class="share-link-btn" hidden>Connect Telegram</button>
            </div>
            <p id="watchChannelsError" class="watch-field-error" role="alert" hidden></p>
          </div>
          <div class="watch-config-field">
            <label class="watch-interval-label" for="watchVisibility">Watch page</label>
            <select id="watchVisibility" class="watch-interval-select" required aria-describedby="watchVisibilityError">
              <option value="private" selected>Private, only you</option>
              <option value="public">Public, anyone with the link</option>
            </select>
            <p id="watchVisibilityError" class="watch-field-error" role="alert" hidden></p>
          </div>
        </div>
      </details>
      <div class="share-modal-actions">
        <button type="button" id="watchConfirmBtn" class="share-primary-btn">Start watching</button>
        <button type="button" id="watchCancelBtn" class="share-secondary-btn">Cancel</button>
      </div>`;
    document.getElementById("watchCancelBtn").addEventListener("click", closeDialog);
    const visibilitySelect = document.getElementById("watchVisibility");
    const intervalSelect = document.getElementById("watchInterval");
    const weekdaySelect = document.getElementById("watchWeekday");
    const runTimeInput = document.getElementById("watchRunTime");
    const emailModeSelect = document.getElementById("watchEmailMode");
    const goalInput = document.getElementById("watchGoal");
    const customChoice = document.getElementById("watchGoalCustomChoice");
    const noneChoice = document.getElementById("watchGoalNone");
    const goalHint = document.getElementById("watchGoalHint");
    const suggestions = document.getElementById("watchGoalSuggestions");
    const emailEnabledInput = document.getElementById("watchEmailEnabled");
    const telegramOption = document.getElementById("watchTelegramOption");
    const telegramEnabledInput = document.getElementById("watchTelegramEnabled");
    const telegramConnect = document.getElementById("watchTelegramConnect");
    const channelsError = document.getElementById("watchChannelsError");
    const advanced = document.getElementById("watchAdvancedSettings");
    const settingsToggle = document.getElementById("watchSettingsToggle");
    document.getElementById("watchTimezoneLabel").textContent = browserTimezone();
    bindWeekdayVisibility(intervalSelect, document.getElementById("watchWeekdayWrap"));

    // --- What are you waiting for? -------------------------------------
    // One visible choice instead of chips above an empty field: suggestions
    // looked like decoration, and nothing showed that one still had to be
    // clicked. The first row (a preset goal, else the first suggestion) is
    // picked for the reader as long as they have not chosen anything.
    let goalTouched = false;

    function checkedGoalChoice() {
      return body.querySelector('input[name="watchGoalChoice"]:checked');
    }
    function selectedGoal() {
      const checked = checkedGoalChoice();
      if (!checked || checked.value === "none") return "";
      if (checked.value === "custom") return normalizeWatchQuestion(goalInput.value);
      return checked.dataset.goal || "";
    }
    function syncGoalHint() {
      const checked = checkedGoalChoice();
      goalHint.textContent = !checked
        ? ""
        : checked.value === "none"
          ? "You hear from us whenever a source changes the answer."
          : "When a source confirms it, you get the proof and the Watch ends.";
    }
    function onGoalChange(keepError) {
      if (!keepError) clearWatchFieldError(goalInput);
      syncGoalHint();
      syncAlertLabels();
    }
    function goalOption(goal) {
      const option = document.createElement("label");
      option.className = "watch-goal-option";
      const radio = document.createElement("input");
      radio.type = "radio";
      radio.name = "watchGoalChoice";
      radio.value = "suggested";
      radio.dataset.goal = goal;
      const text = document.createElement("span");
      text.textContent = goal;
      option.append(radio, text);
      return option;
    }
    function renderGoalOptions(goals, settled) {
      const current = selectedGoal();
      const offered = presetGoal ? [presetGoal] : [];
      goals.forEach(goal => {
        if (goal && !offered.includes(goal)) offered.push(goal);
      });
      suggestions.innerHTML = "";
      offered.forEach(goal => suggestions.appendChild(goalOption(goal)));
      const radios = Array.from(suggestions.querySelectorAll('input[name="watchGoalChoice"]'));
      const keep = radios.find(radio => radio.dataset.goal === current);
      if (keep) keep.checked = true;
      else if (!goalTouched && !checkedGoalChoice()) {
        if (radios[0]) radios[0].checked = true;
        else if (settled) noneChoice.checked = true;
      }
      onGoalChange();
    }

    body.querySelector(".watch-goal").addEventListener("change", event => {
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
    // The custom row is a div (two controls), so its padding answers clicks
    // like the label rows around it.
    goalInput.closest(".watch-goal-option").addEventListener("click", event => {
      if (event.target === event.currentTarget) goalInput.focus();
    });

    renderGoalOptions([]);
    if (suppliedGoals) {
      renderGoalOptions(suppliedGoals, true);
    } else if (watchedQuestion.length >= WATCH_QUESTION_MIN_CHARS) {
      const loading = document.createElement("div");
      loading.className = "watch-goal-loading";
      loading.innerHTML = '<span class="watch-goal-option is-loading" aria-hidden="true"></span>'.repeat(2)
        + '<span class="watch-sr-only">Finding events you may be waiting for…</span>';
      suggestions.appendChild(loading);
      loadGoalSuggestions(watchedQuestion, () => watchModalIntentIsCurrent(modalIntent))
        .then(goals => {
          if (suggestions.isConnected) renderGoalOptions(goals, true);
        })
        .catch(() => {
          if (suggestions.isConnected) renderGoalOptions([], true);
        });
    } else {
      renderGoalOptions([], true);
    }

    document.getElementById("watchQuestionEdit")?.addEventListener("click", () => {
      renderQuestionStep(directQuestion, modalIntent,
        { ...options, goal: selectedGoal() || presetGoal, interval: intervalSelect.value });
    });

    // --- Schedule, alerts, channels, page: one line until "Change" -------
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
      const selected = emailModeSelect.value;
      emailModeSelect.innerHTML = emailModeOptions(selected, Boolean(selectedGoal()));
      updateSetupSummary();
    }
    [visibilitySelect, intervalSelect, weekdaySelect, emailModeSelect,
      emailEnabledInput, telegramEnabledInput].forEach(input => {
      input.addEventListener("change", updateSetupSummary);
    });
    runTimeInput.addEventListener("input", updateSetupSummary);
    advanced.addEventListener("toggle", () => {
      settingsToggle.textContent = advanced.open ? "Done" : "Change";
    });
    updateSetupSummary();

    function syncTelegram(state) {
      // Without a configured bot the option is noise; unconnected, it offers
      // the connection next to it.
      telegramOption.hidden = !state.configured;
      telegramEnabledInput.disabled = !state.connected;
      telegramConnect.hidden = !!state.connected || !state.configured;
      telegramOption.title = state.connected && state.telegram_username
        ? "Connected as @" + state.telegram_username : "";
    }
    loadTelegramState().then(syncTelegram).catch(() => {
      syncTelegram({ configured: false, connected: false });
    });
    telegramConnect.addEventListener("click", () => connectTelegram(syncTelegram));
    [emailEnabledInput, telegramEnabledInput].forEach(input => input.addEventListener("change", () => {
      channelsError.hidden = true;
      channelsError.textContent = "";
    }));
    bindWatchFieldErrorReset(visibilitySelect, "change");
    bindWatchFieldErrorReset(runTimeInput, "input");
    emailModeSelect.addEventListener("change", () => clearWatchFieldError(goalInput));
    const confirm = document.getElementById("watchConfirmBtn");
    if (!directQuestion && !window.lastShareResultId && window.currentBookmarkShareResultContext) {
      confirm.disabled = true;
      confirm.textContent = "Preparing saved consensus…";
      window.resolveCurrentShareResultId?.().then(resultId => {
        if (!confirm.isConnected) return;
        confirm.disabled = !resultId;
        confirm.textContent = resultId ? "Start watching" : "Saved consensus unavailable";
      });
    } else if (!directQuestion && !window.lastShareResultId) {
      confirm.disabled = true;
      confirm.textContent = "Run a consensus first";
    }
    refreshDialogWatchLimit();
    confirm.addEventListener("click", async function () {
      const resultId = directQuestion ? "" : await (window.resolveCurrentShareResultId?.()
        || Promise.resolve(window.lastShareResultId));
      if (!watchModalIntentIsCurrent(modalIntent)) return;
      if (!directQuestion && !resultId) return;
      const visibility = visibilitySelect.value;
      const emailMode = emailModeSelect.value;
      const goal = selectedGoal();
      const runTime = runTimeInput.value;
      [visibilitySelect, runTimeInput, goalInput].forEach(clearWatchFieldError);
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
        channelsError.textContent = "Keep at least one delivery channel enabled.";
        channelsError.hidden = false;
        invalidFields.push(emailEnabledInput);
      }
      if (invalidFields.length) {
        focusWatchField(invalidFields[0]);
        return;
      }
      this.disabled = true;
      this.textContent = "Starting…";
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
        if (!watchModalIntentIsCurrent(modalIntent)) return;
        // Sidebar count and Agent cards follow the new Watch.
        loadWatchLimits(true).catch(() => {});
        const checked = checkedGoalChoice();
        window.App?.trackAppEvent?.("app_watch_created", {
          interval: data.watch.interval,
          source: options?.source || (directQuestion ? "query_first" : "consensus"),
          has_goal: Boolean(goal),
          goal_source: checked ? checked.value : "none"
        });
        renderSuccess(data.watch, modalIntent);
      } catch (error) {
        if (!watchModalIntentIsCurrent(modalIntent)) return;
        this.disabled = false;
        this.textContent = "Start watching";
        if (error.status === 429) {
          watchState.setLimits(null);
          loadWatchLimits(true).then(applyDialogWatchLimit).catch(() => {});
        }
        popup("Watch could not be started: " + error.message);
      }
    });
  }

  function renderSuccess(watch, modalIntent) {
    if (!watchModalIntentIsCurrent(modalIntent)) return;
    const { title, body } = els();
    title.textContent = "Your Watch is active";
    const onWatchPage = onWatchPagePath();
    body.innerHTML = `
      <div class="watch-success-card">
        <span class="watch-success-icon" aria-hidden="true">✓</span>
        <div>
          <strong id="watchStartSummary"></strong>
          <p id="watchMailSummary"></p>
        </div>
      </div>
      <div class="share-modal-actions">
        <button type="button" id="watchDoneBtn" class="share-primary-btn">Done</button>
        ${onWatchPage ? "" : '<button type="button" id="watchListLink" class="share-link-btn">Open dashboard</button>'}
      </div>`;
    document.getElementById("watchStartSummary").textContent = "Checks " + formatWatchSchedule(watch);
    const goal = String(watch.condition || "").trim();
    document.getElementById("watchMailSummary").textContent = watch.email_mode === "every_run"
      ? "You get every check, including the answer."
      : goal
        ? (watch.email_mode === "condition"
          ? `We write when a source confirms “${goal}”.`
          : `We write when a source confirms “${goal}”, and whenever the answer changes before that.`)
        : "We write only when a source changes the answer.";
    // On the Watch page the list behind the dialog must show the new Watch.
    document.getElementById("watchDoneBtn").addEventListener("click", () => {
      if (onWatchPagePath()) openWatchDashboard();
      else closeDialog();
    });
    document.getElementById("watchListLink")?.addEventListener("click", () => {
      closeDialog();
      openWatchDashboard();
    });
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
  // ------------------------------------------------------------------

  const WATCH_PAGE_PATH = "/app/watches";
  const APP_PATH = "/app";

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
    setTimeout(() => {
      if (!onWatchPagePath() && !document.getElementById("watchFeatureNudge")) {
        watchesButton.addEventListener("animationend", () => {
          watchesButton.classList.remove("has-watch-pulse");
        }, { once: true });
        watchesButton.classList.add("has-watch-pulse");
      }
    }, 1400);
  }

  function wireWatchPage() {
    const { page } = dashEls();
    if (!page || page.dataset.wired) return;
    page.dataset.wired = "1";
    document.addEventListener("keydown", event => {
      if (event.key === "Escape" && !page.hidden) closeWatchDashboard();
    });
    // Browser-Navigation (Back/Forward) hält Seite und URL synchron.
    window.addEventListener("popstate", () => {
      if (onWatchPagePath()) showWatchPage();
      else {
        page.hidden = true;
        setViewSwitchState(false);
      }
    });
  }

  function closeWatchDashboard() {
    const { page } = dashEls();
    if (!page) return;
    page.hidden = true;
    setViewSwitchState(false);
    if (!onWatchPagePath()) return;
    // Innerhalb der App geöffnet: echter History-Schritt zurück. Direkt auf
    // /app/watches geladen: URL ohne neuen History-Eintrag auf /app setzen.
    if (window.history.state && window.history.state.watchPage) {
      window.history.back();
    } else {
      window.history.replaceState(null, "", APP_PATH);
    }
  }

  function showWatchPage() {
    const { page } = dashEls();
    if (!page) return;
    wireWatchPage();
    page.hidden = false;
    setViewSwitchState(true);
    window.App.watchDashboard?.render();
  }

  function openWatchDashboard() {
    if (!window.auth?.currentUser) {
      popup("Please log in to use Consensus Watch.");
      return;
    }
    // Share and Watch share one modal node. A navigation to the full Watch
    // view must never leave the previous Share surface floating above it.
    closeDialog();
    acknowledgeViewSwitchHint();
    if (!onWatchPagePath()) {
      window.history.pushState({ watchPage: true }, "", WATCH_PAGE_PATH);
    }
    showWatchPage();
  }

  function initWatchPageRoute() {
    // Deep-Link /app/watches: Seite sofort zeigen, auf den asynchronen
    // Firebase-Auth-Status warten und erst dann laden.
    if (!onWatchPagePath()) return;
    acknowledgeViewSwitchHint();
    const { page, body } = dashEls();
    if (!page || !body) return;
    wireWatchPage();
    page.hidden = false;
    setViewSwitchState(true);
    body.innerHTML = '<p class="watch-dash-loading">Checking your session…</p>';
    const startedAt = Date.now();
    (function waitForAuth() {
      if (window.auth?.currentUser) {
        window.App.watchDashboard?.render();
        return;
      }
      if (window.__consensioAuthState?.known === true) {
        renderWatchLoginHint();
        return;
      }
      if (Date.now() - startedAt < 8000) {
        setTimeout(waitForAuth, 250);
        return;
      }
      renderWatchLoginHint();
    })();
  }

  function renderWatchLoginHint(message) {
    const { page, body } = dashEls();
    if (!page || !body || !onWatchPagePath()) return;
    wireWatchPage();
    page.hidden = false;
    setViewSwitchState(true);
    body.innerHTML = "";
    const hint = document.createElement("div");
    hint.className = "wd-loading";
    hint.textContent = message || "Please log in to see your Consensus Watch dashboard.";
    body.appendChild(hint);
  }

  function initWatchButton() {
    const bar = document.querySelector("#consensusResponse .consensus-copy-inline");
    if (!bar || document.getElementById("consensusWatchButton")) return;
    const button = document.createElement("button");
    button.type = "button";
    button.id = "consensusWatchButton";
    button.className = "consensus-share-pill watch-consensus-pill";
    button.title = "Watch this consensus for material changes";
    button.setAttribute("aria-label", "Watch this consensus for changes");
    button.innerHTML = '<svg class="share-pill-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M3 12s3.5-6 9-6 9 6 9 6-3.5 6-9 6-9-6-9-6Z"></path><circle cx="12" cy="12" r="2.5"></circle></svg><span>Watch</span>';
    button.addEventListener("click", () => {
      dismissWatchFeatureNudge("opened");
      openWatchDialog("confirm");
    });
    const anchor = document.createElement("span");
    anchor.className = "watch-feature-anchor";
    anchor.appendChild(button);
    const actions = bar.querySelector(".consensus-actions-wrapper");
    bar.insertBefore(anchor, actions || null);
  }

  function initViewSwitch() {
    const consensusButton = document.getElementById("viewSwitchConsensus");
    const watchesButton = document.getElementById("viewSwitchWatches");
    if (!consensusButton || !watchesButton) return;

    consensusButton.addEventListener("click", closeWatchDashboard);
    watchesButton.addEventListener("click", () => {
      acknowledgeViewSwitchHint();
      openWatchDashboard();
    });
    setViewSwitchState(onWatchPagePath());
    initViewSwitchHint();
  }

  function initDashboardCreateButton() {
    document.getElementById("watchDashCreate")?.addEventListener("click", () => {
      openWatchDialog("create");
    });
  }

  function resetAfterLogout() {
    const { page, body } = dashEls();
    watchState.resetSession();
    if (body) body.innerHTML = "";
    const quota = document.getElementById("watchUsageDisplay");
    if (quota) quota.textContent = "";
    if (onWatchPagePath()) {
      renderWatchLoginHint();
    } else {
      if (page) page.hidden = true;
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
    resetAfterLogout: resetAfterLogout
  });
  // Shared with watch-dashboard.js, which renders /app/watches, and with
  // agent-watch.js, the Watch card under an Agent answer.
  window.App.watchUi = {
    api: api,
    watchDefaults: watchDefaults,
    settingsSummary: settingsSummary,
    limitMessage: limitMessage,
    receiveWatchList: receiveWatchList,
    popup: popup,
    escapeHtml: escapeHtml,
    makeButton: makeButton,
    formatWatchSchedule: formatWatchSchedule,
    intervalOptions: intervalOptions,
    weekdayOptions: weekdayOptions,
    emailModeOptions: emailModeOptions,
    browserWeekday: browserWeekday,
    browserTimezone: browserTimezone,
    connectTelegram: connectTelegram,
    normalizeWatchLimits: normalizeWatchLimits,
    renderWatchLimit: renderWatchLimit,
    openWatchDialog: openWatchDialog,
    onWatchPagePath: onWatchPagePath
  };
  initWatchButton();
  initViewSwitch();
  initDashboardCreateButton();
  initWatchPageRoute();
  window.addEventListener("consensio:auth-state", event => {
    const uid = event.detail?.uid || null;
    const changed = watchState.updateAuthUid(uid);
    if (!onWatchPagePath() || !changed) return;
    if (uid && window.auth?.currentUser?.uid === uid) showWatchPage();
    else renderWatchLoginHint();
  });
  window.addEventListener("consensio:auth-unavailable", () => {
    if (onWatchPagePath()) {
      renderWatchLoginHint("Login is temporarily unavailable. Check your connection and reload to try again.");
    }
  });
})();
