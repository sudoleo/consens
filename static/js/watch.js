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
  // Dialog ohnehin vorschlaegt — der Dialog bleibt fuer alles andere da
  // ("Pick a different schedule").
  function nudgeWatchDefaults() {
    return {
      interval: "weekly",
      run_weekday: browserTomorrowWeekday(),
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
      const payload = Object.assign(nudgeWatchDefaults(), origin);
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

  async function loadWatchLimits(force) {
    if (watchState.limits && !force) return watchState.limits;
    if (watchState.limitRequest && !force) return watchState.limitRequest;
    const request = api("GET", "/api/my/watches")
      .then(data => {
        watchState.setLimits(normalizeWatchLimits(data.limits, data.watches));
        renderSidebarWatchQuota(watchState.limits);
        return watchState.limits;
      })
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

  function applyDialogWatchLimit(limits) {
    const target = document.getElementById("watchDialogLimit");
    if (!target || !limits) return;
    renderWatchLimit(target, limits);
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
    if (view === "create") renderQuestionStep(options?.question, modalIntent, options?.goal);
    else renderConfirm(undefined, modalIntent);
  }

  function normalizeWatchQuestion(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
  }

  function renderQuestionStep(initialQuestion, modalIntent, pendingGoal) {
    const { title, body } = els();
    if (!body) return;
    title.textContent = "Create a Consensus Watch";
    body.innerHTML = `
      <div class="watch-step-label">Step 1 of 2 · Question</div>
      <p class="watch-config-intro">Ask about something that will change: a release, a decision, a price, a rule. Next you tell us what you are waiting for.</p>
      <div id="watchDialogLimit" class="watch-limit-summary is-dialog" aria-live="polite"><span>Checking Watch availability…</span></div>
      <div class="watch-config-field watch-question-field">
        <label class="watch-interval-label" for="watchQuestion">What do you want to monitor?</label>
        <textarea id="watchQuestion" class="watch-condition-input watch-question-input" maxlength="2000" rows="5" placeholder="Example: Has the EU guidance for general-purpose AI models changed?" aria-describedby="watchQuestionNote watchQuestionError">${escapeHtml(initialQuestion || "")}</textarea>
        <p id="watchQuestionNote" class="watch-data-note">Phrase it as a complete, neutral question. You can be specific about a market, policy, product, or time horizon.</p>
        <p id="watchQuestionError" class="watch-field-error" role="alert" hidden></p>
      </div>
      <details class="watch-question-guidance">
        <summary>What makes a useful watch question?</summary>
        <ul>
          <li>Focus on one decision, claim, or development.</li>
          <li>Add relevant scope, such as a country, audience, or timeframe.</li>
          <li>Avoid asking several unrelated questions at once.</li>
        </ul>
      </details>
      <p class="watch-config-assurance"><span aria-hidden="true">✓</span> No model run starts until the Watch reaches its scheduled check.</p>
      <div class="share-modal-actions">
        <button type="button" id="watchQuestionNext" class="share-primary-btn">Continue</button>
        <button type="button" id="watchCancelBtn" class="share-secondary-btn">Cancel</button>
        <button type="button" id="watchListLink" class="share-link-btn">Open dashboard</button>
      </div>`;
    const input = document.getElementById("watchQuestion");
    bindWatchFieldErrorReset(input, "input");
    document.getElementById("watchCancelBtn").addEventListener("click", closeDialog);
    document.getElementById("watchListLink").addEventListener("click", () => {
      closeDialog();
      openWatchDashboard();
    });
    document.getElementById("watchQuestionNext").addEventListener("click", () => {
      clearWatchFieldError(input);
      const question = normalizeWatchQuestion(input.value);
      if (question.length < 8) {
        setWatchFieldError(input, "Enter a complete question so the models know what to evaluate.");
        focusWatchField(input);
        return;
      }
      renderConfirm({ question: question, goal: pendingGoal || "" }, modalIntent);
    });
    refreshDialogWatchLimit();
    requestAnimationFrame(() => input.focus());
  }

  function renderConfirm(options, modalIntent) {
    const directQuestion = normalizeWatchQuestion(options?.question);
    const presetGoal = normalizeWatchQuestion(options?.goal);
    const suggestionQuestion = directQuestion || normalizeWatchQuestion(window.lastQuestion);
    const { title, body } = els();
    if (!body) return;
    title.textContent = directQuestion ? "Set up your Watch" : "Watch this answer";
    body.innerHTML = `
      ${directQuestion ? '<div class="watch-step-label">Step 2 of 2 · Goal and delivery</div>' : ""}
      <div id="watchDialogLimit" class="watch-limit-summary is-dialog" aria-live="polite"><span>Checking Watch availability…</span></div>
      ${directQuestion ? `<div class="watch-question-preview"><span>Question</span><strong>${escapeHtml(directQuestion)}</strong></div>` : ""}
      <section class="watch-goal" aria-labelledby="watchGoalLabel">
        <label id="watchGoalLabel" class="watch-goal-label" for="watchGoal">What are you waiting for?</label>
        <p class="watch-goal-hint">Name the event you want to hear about. When a source confirms it, the watch closes and shows you the proof. Optional: without a goal you hear about every change on evidence.</p>
        <div id="watchGoalSuggestions" class="watch-goal-suggestions" aria-live="polite" hidden></div>
        <textarea id="watchGoal" class="watch-condition-input watch-goal-input" maxlength="500" rows="2" placeholder="Example: An official release date is announced" aria-describedby="watchGoalError">${escapeHtml(presetGoal)}</textarea>
        <p id="watchGoalError" class="watch-field-error" role="alert" hidden></p>
      </section>
      <div class="watch-setup-summary" aria-label="Watch defaults">
        <div class="watch-setup-summary-head">
          <span class="watch-setup-summary-label">Schedule and alerts</span>
          <button type="button" id="watchEditDefaults" class="watch-setup-edit"
            aria-controls="watchAdvancedSettings" aria-expanded="false">Edit</button>
        </div>
        <div class="watch-setup-summary-chips">
          <button type="button" class="watch-setup-chip" id="watchScheduleSummary" data-edit-field="watchInterval" title="Change interval, run day and run time"></button>
          <button type="button" class="watch-setup-chip" id="watchAlertSummary" data-edit-field="watchEmailMode" title="Change when you get alerted"></button>
          <button type="button" class="watch-setup-chip" id="watchVisibilitySummary" data-edit-field="watchVisibility" title="Change page visibility"></button>
        </div>
        <p class="watch-setup-summary-hint">A daily scan between checks pulls the next check forward when a new source appears.</p>
      </div>
      <details id="watchAdvancedSettings" class="watch-advanced-settings">
        <summary><span>Customize schedule and alerts</span><small>Optional</small></summary>
        <div class="watch-advanced-settings-body">
          <div class="watch-config-field">
            <label class="watch-interval-label" for="watchVisibility">Page visibility</label>
            <select id="watchVisibility" class="watch-interval-select" required aria-describedby="watchVisibilityNote watchVisibilityError">
              <option value="private" selected>Private, only my account</option>
              <option value="public">Public, anyone with the link</option>
            </select>
            <p id="watchVisibilityNote" class="watch-data-note">Public pages are read-only, show the goal, and stay off Google unless you nominate them.</p>
            <p id="watchVisibilityError" class="watch-field-error" role="alert" hidden></p>
          </div>
          <div class="watch-config-grid">
            <div class="watch-config-field">
              <label class="watch-interval-label" for="watchInterval">Interval ${dailyIntervalAllowed() ? "" : '<span class="pro-badge is-subtle">Pro: daily</span>'}</label>
              <select id="watchInterval" class="watch-interval-select">${intervalOptions("weekly")}</select>
              <div id="watchWeekdayWrap" class="watch-weekday-wrap">
                <label class="watch-interval-label" for="watchWeekday">Run day</label>
                <select id="watchWeekday" class="watch-interval-select">${weekdayOptions(browserTomorrowWeekday())}</select>
              </div>
            </div>
            <div class="watch-config-field">
              <label class="watch-interval-label" for="watchRunTime">Run time</label>
              <input id="watchRunTime" class="watch-time-input" type="time" value="09:00" required aria-describedby="watchRunTimeNote watchRunTimeError">
              <p id="watchRunTimeNote" class="watch-data-note"><span id="watchTimezoneLabel"></span> · checks may begin up to 30 minutes later</p>
              <p id="watchRunTimeError" class="watch-field-error" role="alert" hidden></p>
            </div>
          </div>
          <div class="watch-config-field">
            <label class="watch-interval-label" for="watchEmailMode">Alerts</label>
            <select id="watchEmailMode" class="watch-interval-select watch-email-select">${emailModeOptions("changes_only", Boolean(presetGoal))}</select>
            <p class="watch-data-note">“After every check” includes the full answer; “resolves” means a source confirmed your goal.</p>
          </div>
        </div>
      </details>
      <div class="watch-config-field watch-delivery-field">
        <span class="watch-interval-label">Delivery channels</span>
        <div class="watch-channel-options">
          <label class="watch-channel-option"><input type="checkbox" id="watchEmailEnabled" checked> E-mail</label>
          <label class="watch-channel-option"><input type="checkbox" id="watchTelegramEnabled" disabled> Telegram</label>
          <button type="button" id="watchTelegramConnect" class="share-link-btn">Connect Telegram</button>
        </div>
        <p id="watchTelegramNote" class="watch-data-note">Checking Telegram connection…</p>
        <p id="watchChannelsError" class="watch-field-error" role="alert" hidden></p>
      </div>
      <div class="share-modal-actions">
        <button type="button" id="watchConfirmBtn" class="share-primary-btn">Start watching</button>
        <button type="button" id="watchCancelBtn" class="share-secondary-btn">${directQuestion ? "Back" : "Cancel"}</button>
        <button type="button" id="watchListLink" class="share-link-btn">Open dashboard</button>
      </div>`;
    document.getElementById("watchCancelBtn").addEventListener("click", () => {
      if (directQuestion) renderQuestionStep(directQuestion, modalIntent, goalInput.value);
      else closeDialog();
    });
    document.getElementById("watchListLink").addEventListener("click", () => {
      closeDialog();
      openWatchDashboard();
    });
    const visibilitySelect = document.getElementById("watchVisibility");
    const intervalSelect = document.getElementById("watchInterval");
    const weekdaySelect = document.getElementById("watchWeekday");
    const runTimeInput = document.getElementById("watchRunTime");
    const emailModeSelect = document.getElementById("watchEmailMode");
    const goalInput = document.getElementById("watchGoal");
    const emailEnabledInput = document.getElementById("watchEmailEnabled");
    const telegramEnabledInput = document.getElementById("watchTelegramEnabled");
    const telegramConnect = document.getElementById("watchTelegramConnect");
    const telegramNote = document.getElementById("watchTelegramNote");
    const channelsError = document.getElementById("watchChannelsError");
    document.getElementById("watchTimezoneLabel").textContent = browserTimezone();
    bindWeekdayVisibility(intervalSelect, document.getElementById("watchWeekdayWrap"));

    function updateSetupSummary() {
      const intervalLabel = intervalSelect.options[intervalSelect.selectedIndex]?.textContent.trim() || "Weekly";
      const weekdayLabel = weekdaySelect.options[weekdaySelect.selectedIndex]?.textContent.trim() || "";
      const scheduleParts = [intervalLabel];
      if (intervalSelect.value === "weekly" && weekdayLabel) scheduleParts.push(weekdayLabel);
      if (runTimeInput.value) scheduleParts.push(runTimeInput.value);
      document.getElementById("watchScheduleSummary").textContent = scheduleParts.join(" · ");
      document.getElementById("watchAlertSummary").textContent =
        emailModeSelect.options[emailModeSelect.selectedIndex]?.textContent.trim() || "When it moves on evidence";
      document.getElementById("watchVisibilitySummary").textContent =
        visibilitySelect.value === "public" ? "Public page" : "Private page";
    }
    function syncAlertLabels() {
      const selected = emailModeSelect.value;
      emailModeSelect.innerHTML = emailModeOptions(selected, Boolean(goalInput.value.trim()));
      updateSetupSummary();
    }
    [visibilitySelect, intervalSelect, weekdaySelect, emailModeSelect].forEach(input => {
      input.addEventListener("change", updateSetupSummary);
    });
    runTimeInput.addEventListener("input", updateSetupSummary);
    goalInput.addEventListener("input", () => {
      clearWatchFieldError(goalInput);
      syncGoalChips();
      syncAlertLabels();
    });
    updateSetupSummary();

    // Suggested goals turn "What are you waiting for?" into one tap. They
    // are a convenience: without them (or on failure) the field just works.
    const suggestions = document.getElementById("watchGoalSuggestions");
    function syncGoalChips() {
      const current = goalInput.value.trim();
      suggestions.querySelectorAll(".watch-goal-chip").forEach(chip => {
        chip.setAttribute("aria-pressed", String(chip.dataset.goal === current));
      });
    }
    function renderGoalChips(goals) {
      suggestions.innerHTML = "";
      if (!goals.length) {
        suggestions.hidden = true;
        return;
      }
      goals.forEach(goal => {
        const chip = makeButton(goal, "watch-goal-chip", () => {
          goalInput.value = goalInput.value.trim() === goal ? "" : goal;
          goalInput.dispatchEvent(new Event("input"));
        });
        chip.dataset.goal = goal;
        suggestions.appendChild(chip);
      });
      suggestions.hidden = false;
      syncGoalChips();
    }
    if (suggestionQuestion.length >= 8) {
      suggestions.hidden = false;
      suggestions.innerHTML = '<span class="watch-goal-chip is-loading" aria-hidden="true"></span>'.repeat(3)
        + '<span class="watch-sr-only">Loading suggested goals…</span>';
      api("POST", "/api/watch/goal-suggestions", { question: suggestionQuestion },
        () => watchModalIntentIsCurrent(modalIntent))
        .then(data => {
          if (suggestions.isConnected) renderGoalChips(Array.isArray(data.goals) ? data.goals : []);
        })
        .catch(() => {
          if (suggestions.isConnected) renderGoalChips([]);
        });
    }

    // Die Voreinstellungen sahen aus wie feste Fakten: das Aufklapp-Feld stand
    // ganz unten und wurde schlicht uebersehen ("man kann nichts verstellen").
    // Deshalb steht der Schalter jetzt IN der Zusammenfassung, und jeder Chip
    // ist selbst der Weg zu seinem Feld.
    const advanced = document.getElementById("watchAdvancedSettings");
    const editToggle = document.getElementById("watchEditDefaults");
    function syncEditToggle() {
      editToggle.textContent = advanced.open ? "Done" : "Edit";
      editToggle.setAttribute("aria-expanded", String(advanced.open));
    }
    function openAdvanced(focusId) {
      advanced.open = true;
      syncEditToggle();
      const target = focusId ? document.getElementById(focusId) : null;
      (target || advanced).scrollIntoView({ block: "nearest" });
      if (target) requestAnimationFrame(() => target.focus());
    }
    advanced.addEventListener("toggle", syncEditToggle);
    editToggle.addEventListener("click", () => {
      if (advanced.open) {
        advanced.open = false;
        syncEditToggle();
        return;
      }
      openAdvanced("watchInterval");
    });
    body.querySelectorAll(".watch-setup-chip").forEach(chip => {
      chip.addEventListener("click", () => openAdvanced(chip.dataset.editField));
    });
    syncEditToggle();

    function syncTelegram(state) {
      telegramEnabledInput.disabled = !state.connected;
      telegramConnect.hidden = !!state.connected || !state.configured;
      telegramNote.textContent = !state.configured
        ? "Telegram notifications are not available yet."
        : state.connected
          ? `Connected${state.telegram_username ? " as @" + state.telegram_username : ""}.`
          : "Connect Telegram to enable this channel.";
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
      const goal = normalizeWatchQuestion(goalInput.value);
      const runTime = runTimeInput.value;
      [visibilitySelect, runTimeInput, goalInput].forEach(clearWatchFieldError);
      const invalidFields = [];
      if (!visibility) {
        setWatchFieldError(visibilitySelect, "Choose whether this page should be private or public.");
        invalidFields.push(visibilitySelect);
      }
      if (!runTime) {
        setWatchFieldError(runTimeInput, "Choose a run time for the automatic check.");
        invalidFields.push(runTimeInput);
      }
      if (emailMode === "condition" && !goal) {
        setWatchFieldError(goalInput, "Name the goal, or choose a different alert rule.");
        invalidFields.push(goalInput);
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
        const payload = {
          interval: intervalSelect.value,
          run_weekday: intervalSelect.value === "weekly" ? weekdaySelect.value : "",
          email_mode: emailMode,
          email_enabled: emailEnabledInput.checked,
          telegram_enabled: telegramEnabledInput.checked,
          condition: goal,
          visibility: visibility,
          run_time: runTime,
          timezone: browserTimezone()
        };
        if (directQuestion) payload.question = directQuestion;
        else payload.result_id = resultId;
        const data = await api(
          "POST",
          "/api/watch",
          payload,
          () => watchModalIntentIsCurrent(modalIntent)
        );
        if (!watchModalIntentIsCurrent(modalIntent)) return;
        watchState.setLimits(null);
        window.App?.trackAppEvent?.("app_watch_created", {
          interval: data.watch.interval,
          source: directQuestion ? "query_first" : "consensus",
          has_goal: Boolean(goal)
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
    const url = window.location.origin + (watch.share_path || "");
    body.innerHTML = `
      <div class="watch-success-card">
        <span class="watch-success-icon" aria-hidden="true">✓</span>
        <div>
          <strong id="watchStartSummary"></strong>
          <p id="watchMailSummary"></p>
          <div id="watchSuccessChips" class="watch-setup-summary-chips"></div>
        </div>
      </div>
      <div class="share-modal-actions">
        <a id="watchOpenLink" class="share-secondary-btn" target="_blank" rel="noopener">Open history page</a>
        <button type="button" id="watchListLink" class="share-link-btn">Open dashboard</button>
      </div>`;
    document.getElementById("watchStartSummary").textContent = watch.query_first
      ? `First check: ${formatWatchSchedule(watch)}`
      : `Next check: ${formatWatchSchedule(watch)}`;
    const goal = String(watch.condition || "").trim();
    document.getElementById("watchMailSummary").textContent = watch.email_mode === "every_run"
      ? "You will get every check, including the answer."
      : goal
        ? `Waiting for: ${goal}. ${watch.email_mode === "condition" ? "You hear from us when a source confirms it." : "You also hear about every change on evidence."}`
        : "You hear from us only when a source moves the answer.";
    const successChips = document.getElementById("watchSuccessChips");
    [
      watch.visibility === "private" ? "Private page" : "Public page",
      watch.email_enabled ? "E-mail" : "",
      watch.telegram_enabled ? "Telegram" : ""
    ].filter(Boolean).forEach(label => {
      const chip = document.createElement("span");
      chip.textContent = label;
      successChips.appendChild(chip);
    });
    document.getElementById("watchOpenLink").href = url;
    document.getElementById("watchListLink").addEventListener("click", () => {
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
    resetAfterLogout: resetAfterLogout
  });
  // Shared with watch-dashboard.js, which renders /app/watches.
  window.App.watchUi = {
    api: api,
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
