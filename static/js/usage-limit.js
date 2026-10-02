/* ==========================================================================
   usage-limit.js — "dieser Lauf hat nicht stattgefunden"

   Ein aufgebrauchtes Kontingent war bis 2026-07-31 der einzige Fehlerfall,
   den die App gar nicht erzaehlt hat. Der Grund war kein fehlender Text,
   sondern ein fehlender ORT: der gefuehrte Lauf (consensus-progress.js)
   startet schon bei /prepare, und der Limit-Pfad meldete danach
   setAgentModeStatus("error") — was den Block per dismiss() wieder
   wegnimmt. Die eigentliche Meldung landete in den Antwortboxen, die im
   Agent Mode (Default) hinter "Compare answers" liegen. Ergebnis: eine
   Sekunde Fortschritt, dann eine leere Seite.

   Dieses Modul ist die eine Stelle, die diesen Zustand besitzt:

     - erkennt Limit-Antworten (ein Detektor, nicht drei),
     - prueft VOR dem Absenden gegen dasselbe Tokenkonto wie der Ring
       (App.tokenBudget), damit der Lauf gar nicht erst scheinbar losgeht,
     - rendert eine bleibende Karte im Thread (#runBlocked), genau dort, wo
       sonst die Antwort stuende.

   Seit 2026-10-01 gibt es keine Run-Zaehler mehr: Compare, Consensus, Deep
   Think und Agent teilen ein Tokenkonto pro Tag. Ein Lauf startet, wenn das
   freie Budget die erwarteten Tokens eines typischen Laufs dieses Modus
   deckt — dieselbe Regel wie die Admission auf dem Server.

   Die Karte verkauft nichts. consens.io ist waehrend des Tests gratis, es
   gibt also keinen Kauf-Ausweg — sie sagt, wann das Kontingent
   zurueckkommt, und bietet an, was jetzt geht.
   ========================================================================== */
(function () {
  "use strict";

  window.App = window.App || {};

  function el(id) {
    return document.getElementById(id);
  }

  // --- Erkennung -------------------------------------------------------
  // FastAPI verpackt HTTPException-Details in {detail: {...}}; die Streams
  // reichen das Objekt teils schon ausgepackt weiter. Beides muss hier
  // ankommen duerfen.
  function unwrap(data) {
    var detail = data && data.detail;
    if (detail && typeof detail === "object") {
      var merged = {};
      Object.keys(detail).forEach(function (key) { merged[key] = detail[key]; });
      merged.error = detail.error || detail.message || "";
      return merged;
    }
    return data || {};
  }

  // Der Server sendet "token_budget_exhausted" (chat.py, _token_limit_detail);
  // Agent meldet "agent_tokens_exhausted". Aeltere Codes enthalten "limit".
  function isLimitError(data, message) {
    var normalized = unwrap(data);
    var code = String(normalized.error_code || normalized.code || "").toLowerCase();
    var text = String(message || normalized.error || normalized.detail || "").toLowerCase();
    return code === "token_budget_exhausted"
      || code.indexOf("limit") !== -1
      || text.indexOf("usage limit") !== -1
      || text.indexOf("allowance") !== -1
      || text.indexOf("quota") !== -1
      || text.indexOf("used up") !== -1
      || text.indexOf("exhausted") !== -1;
  }

  // Ein Topf fuer alles; der Name bleibt fuer Telemetrie und data-bucket.
  function bucketOf() {
    return "tokens";
  }

  function budget() {
    return window.App.tokenBudget || null;
  }

  var MODE_NAMES = { compare: "Compare run", consensus: "Consensus run", deep_think: "Deep Think run" };

  /* "4% left today · a Consensus run needs about 8% · resets at 02:00 (in 1 h 58 min)".
     Zahlen aus der Server-Absage (frischeste Quelle, schon im Store), sonst
     aus demselben Konto wie der Ring. Ohne Zahl bleibt die Reset-Zeit. */
  function metaLine(mode) {
    var api = budget();
    var view = api ? api.view() : null;
    var reset = api ? api.resetInfo() : null;
    var parts = [];
    if (view) parts.push(view.percent + " left today");
    var share = api ? api.runShare(mode) : null;
    if (share) parts.push("a " + MODE_NAMES[mode] + " needs about " + share);
    if (reset) parts.push("resets at " + reset.clock + " (in " + reset.relative + ")");
    return parts.join(" · ");
  }

  // --- Rendering -------------------------------------------------------

  function clearActions() {
    var actions = el("runBlockedActions");
    if (actions) actions.innerHTML = "";
    return actions;
  }

  function addAction(actions, label, title, handler, variant) {
    if (!actions) return null;
    var button = document.createElement("button");
    button.type = "button";
    button.className = "run-blocked-btn" + (variant ? " is-" + variant : "");
    button.textContent = label;
    if (title) button.title = title;
    button.addEventListener("click", handler);
    actions.appendChild(button);
    return button;
  }

  function hide() {
    var card = el("runBlocked");
    if (!card) return;
    card.hidden = true;
    card.classList.remove("is-visible");
    clearActions();
  }

  function render(view) {
    var card = el("runBlocked");
    if (!card) {
      // Ohne die Karte darf der Zustand trotzdem nicht verschwinden.
      window.App.showPopup && window.App.showPopup(view.title + " " + view.body);
      return;
    }

    card.dataset.bucket = view.bucket || "tokens";

    var title = el("runBlockedTitle");
    if (title) title.textContent = view.title;

    var body = el("runBlockedBody");
    if (body) body.textContent = view.body;

    var meta = el("runBlockedMeta");
    if (meta) {
      meta.textContent = view.meta || "";
      meta.hidden = !view.meta;
    }

    var actions = clearActions();
    (view.actions || []).forEach(function (action) {
      addAction(actions, action.label, action.title, action.onClick, action.variant);
    });

    card.hidden = false;
    // Zwei Frames, damit der Einblend-Uebergang auch beim ersten Zeigen
    // greift (dieselbe Mechanik wie beim gefuehrten Lauf).
    requestAnimationFrame(function () {
      requestAnimationFrame(function () { card.classList.add("is-visible"); });
    });
    card.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }

  // --- Die eigentliche Absage ------------------------------------------

  function deepThinkIsOn() {
    var toggle = el("deepSearchToggle");
    return !!(toggle && toggle.checked);
  }

  function currentMode(opts) {
    if (opts && opts.mode) return opts.mode;
    if ((opts && opts.deepThink) || deepThinkIsOn()) return "deep_think";
    try {
      if (window.App.runMode && window.App.runMode.pipeline && window.App.runMode.pipeline() === false) return "compare";
    } catch (_) { /* default */ }
    return "consensus";
  }

  // Das Kontingent-Panel haengt im Sidebar-Fuss. Bei zugeklappter Sidebar
  // wuerde setOpen(true) etwas Unsichtbares oeffnen — also erst die Sidebar
  // ueber ihren eigenen Toggle aufmachen (eine Mechanik, nicht zwei) und
  // danach das Panel.
  function openQuotaPanel() {
    var sidebar = document.querySelector(".sidebar");
    var collapsed = sidebar
      && sidebar.classList.contains("collapsed")
      && !sidebar.classList.contains("active");
    if (collapsed) {
      var toggle = document.querySelector(".sidebar-toggle");
      if (toggle) toggle.click();
    }
    requestAnimationFrame(function () {
      if (window.App.sidebarQuota) window.App.sidebarQuota.setOpen(true);
      var trigger = el("quotaTrigger");
      if (trigger && !trigger.hidden) trigger.focus();
    });
  }

  function buildView(info) {
    var opts = info || {};
    var data = unwrap(opts.data);
    // A refusal carries the account; it becomes the ring's value too.
    if (budget()) budget().fromResponse(data);
    var mode = currentMode(opts);
    var phase = opts.phase;
    var view = { bucket: "tokens", actions: [] };
    var api = budget();

    view.title = "Not enough of today’s allowance left";
    if (phase === "consensus") {
      view.body = "The models answered, but the consensus could not be written: today’s allowance ran out during this run. The individual answers are still there under “Compare answers”.";
    } else {
      view.body = "Compare, Consensus and Agent share one daily allowance, and what is left does not cover a typical "
        + (MODE_NAMES[mode] || "run") + ". Nothing was sent, and your question is still in the box.";
    }
    view.meta = metaLine(mode);

    // Deep Think is the largest run. If a normal one still fits, offer it.
    if (mode === "deep_think" && api && api.canStart("consensus") === true) {
      // Warning tone, not refusal: there is another way (shell.css).
      view.bucket = "deep_think";
      view.body = "A Deep Think run needs more of today’s allowance than is left. A normal run still fits, and your question is still in the box.";
      view.actions.push({
        label: "Send without Deep Think",
        title: "Switch Deep Think off and send this question as a normal run.",
        variant: "primary",
        onClick: function () {
          var toggle = el("deepSearchToggle");
          if (toggle && toggle.checked) {
            toggle.checked = false;
            toggle.dispatchEvent(new Event("change", { bubbles: true }));
          }
          hide();
          track("deep_think_downgrade");
          if (typeof window.sendQuestion === "function") window.sendQuestion();
        }
      });
    }

    // Immer erreichbar: die Zahlen selbst. Der Ring im Sidebar-Fuss ist der
    // Ort, an dem das Kontingent lebt — die Karte schickt dorthin, statt
    // eine zweite Rechnung danebenzustellen.
    view.actions.push({
      label: "See your allowance",
      title: "Open the allowance panel in the sidebar.",
      onClick: function () {
        track("open_quota");
        openQuotaPanel();
      }
    });

    return view;
  }

  function track(action) {
    try {
      window.App.trackAppEvent && window.App.trackAppEvent("app_usage_limit_blocked", {
        action: action
      });
    } catch (err) { /* Telemetrie darf die Meldung nie verhindern */ }
  }

  /* Zeigt die Absage. info: {data, mode, phase, source}
     Gibt die verwendete Auspraegung zurueck, damit Aufrufer sie loggen
     koennen. */
  function show(info) {
    var view = buildView(info || {});
    render(view);
    try {
      window.App.trackAppEvent && window.App.trackAppEvent("app_usage_limit_shown", {
        bucket: view.bucket,
        source: (info && info.source) || "unknown",
        phase: (info && info.phase) || "prepare"
      });
    } catch (err) { /* s. o. */ }
    return view;
  }

  // Firestore can abort a hot transaction even after its own retry budget.
  // This is deliberately separate from quota exhaustion: nothing has been
  // denied permanently and the user should be able to retry the same question.
  function showTemporaryStorageBusy() {
    render({
      bucket: "temporary",
      title: "Temporarily unable to start this run",
      body: "The usage service is busy right now. No model was asked; please try this question again in a moment.",
      actions: [{
        label: "Try again",
        variant: "primary",
        title: "Retry this question.",
        onClick: function () {
          hide();
          if (typeof window.sendQuestion === "function") window.sendQuestion();
        }
      }]
    });
    try {
      window.App.trackAppEvent && window.App.trackAppEvent("app_usage_storage_busy");
    } catch (err) { /* Telemetrie darf die Meldung nie verhindern */ }
  }

  /* Vor dem Absenden: gibt "tokens" zurueck, wenn der Lauf sicher nicht
     durchgeht, sonst null. Bewusst konservativ — bei unbekanntem Stand
     (Gast, noch nicht geladen, eigene Keys) entscheidet weiterhin der
     Server. Lieber ein Server-Nein als ein falsches Client-Nein. */
  function preflight(options) {
    var opts = options || {};
    if (opts.useOwnKeys) return null;
    var api = budget();
    if (!api) return null;
    return api.canStart(currentMode(opts)) === false ? "tokens" : null;
  }

  /* Blockiert den Versuch, falls das Konto den Lauf nicht deckt. true = der
     Aufrufer soll abbrechen. */
  function blockIfExhausted(options) {
    var bucket = preflight(options);
    if (!bucket) return false;
    show({
      mode: currentMode(options),
      deepThink: options && options.deepThink,
      source: (options && options.source) || "preflight",
      phase: "preflight"
    });
    return true;
  }

  var closeButton = el("runBlockedClose");
  if (closeButton) {
    closeButton.addEventListener("click", function () {
      hide();
      track("dismiss");
      var input = el("questionInput");
      if (input && !input.disabled) input.focus();
    });
  }

  // "New comparison" raeumt den Thread — die Absage gehoert zum geraeumten
  // Lauf und darf nicht ueber ihn hinaus stehenbleiben. Delegiert, weil der
  // Knopf auch aus dem Composer-Gate heraus geklickt wird.
  document.addEventListener("click", function (event) {
    if (event.target.closest && event.target.closest("#newRunButton")) hide();
  });

  window.App.usageLimit = {
    isLimitError: isLimitError,
    bucketOf: bucketOf,
    show: show,
    showTemporaryStorageBusy: showTemporaryStorageBusy,
    hide: hide,
    preflight: preflight,
    blockIfExhausted: blockIfExhausted
  };
})();
