// =====================================================================
// app-core.js
// Geteilte Basis (Uebergangsbus window.App) fuer die ausgelagerten
// Feature-Module und die verbleibende initApp-Closure.
// Haelt zentrale Config (modelPrefs) und
// cross-cutting Helfer (getModelOptionLabel, getSelectedModelCount,
// trackAppEvent). MUSS vor den Feature-Modulen geladen werden.
//
// Hinweis: window.App ist bewusst ein TEMPORAERER Bus, um die Cluster
// schrittweise aus index.html zu loesen. Der echte State-Refactor folgt
// spaeter (DOM-als-State aufloesen).
// =====================================================================

(function () {
  window.App = window.App || {};

  // Smooth scrolling is decoration. Whoever asked the system for less
  // motion gets the jump instead (audit F15); every scrollTo/scrollIntoView
  // in /app takes its `behavior` from here. Read per call, so a changed
  // system setting applies without a reload.
  const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)");
  function scrollBehavior() {
    return reducedMotion?.matches ? "auto" : "smooth";
  }

  // Telemetrie-Wrapper (Guard um window.trackUmamiEvent).
  function trackAppEvent(eventName, eventData = {}) {
    if (typeof window.trackUmamiEvent === "function") {
      window.trackUmamiEvent(eventName, eventData);
    }
  }

  // Core events (docs/analytics.md): one "ask" per sent question and one
  // "answer" per run, with the same shape in every mode. The older
  // app_query_*/app_consensus_* events keep firing as the detailed record.
  function analyticsMode(context) {
    const config = context?.config || {};
    if (config.executionMode === "agent") return "agent";
    return config.autoConsensus ? "consensus" : "compare";
  }

  function trackAsk(context) {
    if (!context) return;
    const config = context.config || {};
    trackAppEvent("ask", {
      mode: analyticsMode(context),
      follow_up: Boolean(context.conversationLockKey),
      files: (context.attachments?.length || context.attachmentMeta?.length || 0) > 0,
      reasoning: config.executionMode === "agent"
        ? (config.agentSettings?.reasoning_effort || "default") !== "default"
        : config.deepSearch === true,
      // typed, example or pasted; after_login for a guest's question
      // (composer-invite.js).
      ...(window.App.composerInvite?.takeAskContext?.() || { source: "typed" })
    });
  }

  // status: "ok" | "partial" | "failed". The first terminal state of a run
  // counts; a manual Consensus on an already answered run adds nothing.
  function trackAnswer(context, status) {
    if (!context?.metadata || context.metadata.answerTracked) return;
    context.metadata.answerTracked = true;
    trackAppEvent("answer", { mode: analyticsMode(context), status });
  }

  function getSelectedModelCount() {
    return modelPrefs.filter(pref => document.getElementById(pref.checkId)?.checked).length;
  }

  // Same as <title> in templates/index.html.
  const DEFAULT_APP_TITLE = "consens.io";

  function setAppTitle(question = "") {
    const normalized = String(question || "").replace(/\s+/g, " ").trim();
    if (!normalized) {
      document.title = DEFAULT_APP_TITLE;
      return;
    }

    const maxQuestionLength = 64;
    const shortened = normalized.length > maxQuestionLength
      ? `${normalized.slice(0, maxQuestionLength - 1).trimEnd()}…`
      : normalized;
    document.title = `${shortened} | consens.io`;
  }

  // Anhaenge der sichtbaren Frage. Sie gehoeren zu der Nachricht, mit der sie
  // rausgegangen sind — eine neue Frage erbt sie nicht. Gerendert werden sie
  // von attachments.js, das die Chip-Optik besitzt.
  let threadAttachments = [];

  function getThreadAttachments() {
    return threadAttachments.slice();
  }

  function setThreadQuestionAttachments(attachmentsMeta) {
    threadAttachments = (Array.isArray(attachmentsMeta) ? attachmentsMeta : [])
      .filter(item => item && item.name)
      .map(item => ({
        name: String(item.name),
        mime: String(item.mime || ""),
        size: Number(item.size) || 0,
        // Agent files are stored per chat; their ID opens the preview.
        ...(/^[a-f0-9]{32}$/.test(String(item.id || "")) ? { id: String(item.id) } : {}),
        // Agent files carry extraction warnings (for a "Partly read" badge).
        ...(Array.isArray(item.warnings) && item.warnings.length
          ? { warnings: item.warnings.map(String).slice(0, 5) } : {}),
        // A file from Google Drive keeps saying so on its message.
        ...(item.source === "google_drive" || item.kind === "drive_file" || item.origin?.source === "google_drive"
          ? { source: "google_drive" } : {})
      }));
    const row = document.getElementById("threadAskAttachments");
    if (!row) return;
    if (typeof window.App.attachments?.renderMessageAttachments === "function") {
      window.App.attachments.renderMessageAttachments(row, threadAttachments);
      return;
    }
    row.innerHTML = "";
    row.hidden = true;
  }

  // Absaetze der Nachricht bleiben stehen (die Blase setzt pre-wrap); nur
  // Leerzeichenfolgen und mehr als eine Leerzeile werden eingeebnet.
  function normalizeQuestionText(question) {
    return String(question || "")
      .replace(/\r\n?/g, "\n")
      .replace(/[^\S\n]+/g, " ")
      .replace(/ ?\n ?/g, "\n")
      .replace(/\n{3,}/g, "\n\n")
      .trim();
  }

  // Ein "Ask about this"-Zitat ist Teil der gesendeten Frage (composer-quote.js),
  // in der Blase aber Kontext: es steht als abgesetzter Block unter der
  // getippten Frage statt als "Quoted from the previous answer: ..."-Satz.
  // Absaetze werden eigene Bloecke mit Abstand statt einer Leerzeile: die
  // eingeklappte Blase zeigt nur acht Zeilen, und eine Leerzeile waere eine davon.
  function fillQuestionText(element, normalized) {
    const parts = window.App.quote?.split?.(normalized) || { typed: normalized, quote: "" };
    const paragraphs = parts.typed.split(/\n\n+/).filter(Boolean);
    if (!parts.quote && paragraphs.length <= 1) {
      element.textContent = normalized;
      return;
    }
    element.replaceChildren();
    for (const paragraph of paragraphs) {
      const block = document.createElement("span");
      block.className = "thread-ask-paragraph";
      block.textContent = paragraph;
      element.append(block);
    }
    if (!parts.quote) return;
    const quote = document.createElement("span");
    quote.className = "thread-ask-quote";
    quote.textContent = parts.quote;
    element.append(quote);
  }

  // Beide Fragen-Koepfe im Thread teilen sich Optik und Aufklapp-Logik: der
  // aktive (#threadAsk) und der der gerade abgeschickten, noch nicht
  // uebernommenen Nachricht (#threadPendingAsk). Leerer Text versteckt den
  // Block wieder. Lange Nachrichten klappen per CSS ein, sobald
  // syncQuestionFold is-long setzt; is-open hebt den Clamp auf.
  function renderThreadQuestion(wrap, text, question) {
    if (!wrap || !text) return "";

    const normalized = normalizeQuestionText(question);
    const unchanged = (text.dataset.question ?? text.textContent) === normalized;
    // Die Multi-Run-Projektion schreibt den sichtbaren Context waehrend des
    // Streamings regelmaessig neu ins DOM. Eine identische Frage ist dabei
    // kein neuer Turn: ihren lokalen Disclosure-State zurueckzusetzen liess
    // "Show more" unter dem Mauszeiger flackern und klappte einen
    // erfolgreichen Klick beim naechsten Stream-Update sofort wieder zu.
    // Nur neuer Inhalt initialisiert Clamp und Link deshalb von vorn.
    if (unchanged) {
      wrap.hidden = !normalized;
      if (normalized) observeQuestionFold(wrap, text);
      return normalized;
    }

    fillQuestionText(text, normalized);
    text.dataset.question = normalized;
    wrap.hidden = !normalized;
    wrap.classList.remove("is-open", "is-long");
    const more = wrap.querySelector(".thread-ask-more");
    if (more) {
      more.textContent = "Show more";
      more.setAttribute("aria-expanded", "false");
    }
    if (!normalized) return "";

    observeQuestionFold(wrap, text);
    return normalized;
  }

  // Kopf des Threads (#threadAsk): zeigt die gestellte Frage über dem Lauf.
  // Leerer Text versteckt den Block wieder (New comparison, Clear).
  function setThreadQuestion(question = "") {
    // Wer den Kopf setzt, hat die schwebende Nachricht uebernommen (oder den
    // Thread ganz geraeumt) — in beiden Faellen ist die Blase erledigt. Das
    // gilt auch fuer Aufrufer ausserhalb des Sendepfads (Bookmark-Restore,
    // "New comparison", Direktvergleich), damit sie nie stehen bleibt.
    clearPendingThreadQuestion();
    const wrap = document.getElementById("threadAsk");
    const text = document.getElementById("threadAskText");
    if (!wrap || !text) return;
    // Eine neue Frage beginnt ohne Anhaenge; wer welche mitschickt, meldet sie
    // direkt nach dem Senden ueber setThreadQuestionAttachments an.
    setThreadQuestionAttachments([]);
    renderThreadQuestion(wrap, text, question);
  }

  // ---- Die gerade abgeschickte Nachricht -----------------------------------
  // Sie steht sofort im Thread, nicht erst wenn der Lauf sie zum Kopf des
  // neuen Turns macht: dazwischen liegen /prepare und, im laufenden Gespraech,
  // das Binden des Chat-Kontexts. Das sind Sekunden, in denen frueher nichts
  // passierte — die Frage stand unveraendert im Feld, der Thread zeigte
  // weiter die vorige. Der Vorgaenger bleibt dabei unangetastet: erst wenn der
  // Lauf wirklich stattfindet, wandert er in den Verlauf.
  const PENDING_MESSAGE_CLASS = "thread-message-pending";

  function setPendingThreadQuestion(question = "", attachmentsMeta = []) {
    const wrap = document.getElementById("threadPendingAsk");
    const text = document.getElementById("threadPendingAskText");
    const normalized = renderThreadQuestion(wrap, text, question);
    const row = document.getElementById("threadPendingAskAttachments");
    if (row) {
      const renderer = window.App.attachments?.renderMessageAttachments;
      if (normalized && typeof renderer === "function") {
        renderer(row, attachmentsMeta);
      } else {
        row.replaceChildren();
        row.hidden = true;
      }
    }
    document.body.classList.toggle(PENDING_MESSAGE_CLASS, !!normalized);
    return !!normalized;
  }

  function clearPendingThreadQuestion() {
    document.body.classList.remove(PENDING_MESSAGE_CLASS);
    const wrap = document.getElementById("threadPendingAsk");
    const text = document.getElementById("threadPendingAskText");
    const row = document.getElementById("threadPendingAskAttachments");
    if (text) {
      text.textContent = "";
      delete text.dataset.question;
    }
    if (wrap) {
      wrap.hidden = true;
      wrap.classList.remove("is-open", "is-long");
    }
    if (row) {
      row.replaceChildren();
      row.hidden = true;
    }
  }

  // Shared by the Agent and Consensus send paths; ordinary projections never
  // force a reader back to the latest message.
  function revealSentMessage() {
    window.App.chatScroll?.sent();
  }

  // Eingeklappt wird grosszuegig: erst wenn mindestens drei Zeilen ueber acht
  // hinaus verschwinden wuerden. Eine Frage mit ein paar Absaetzen bleibt
  // ganz stehen, und "Show more" verbirgt nie nur eine einzelne Zeile.
  const FOLD_LINES = 8;
  const FOLD_MIN_HIDDEN_LINES = 3;

  // Ob eine Nachricht so lang ist, haengt an der Breite der Blase - und die
  // steht im ersten Frame noch nicht fest: Der Ausstieg aus dem Hero animiert
  // den Container, und die Sidebar aendert ihn spaeter noch einmal. Wurde nur
  // einmal gemessen, blieb der Link bei einer langen Frage aus und das Ende
  // verschwand lautlos. Deshalb misst ein ResizeObserver nach jeder
  // Groessenaenderung nach — einer je Fragen-Text (aktiver Kopf, schwebende
  // Nachricht, jede archivierte Frage).
  const threadAskResizeObservers = new WeakMap();

  function syncQuestionFold(wrap, text) {
    // Aufgeklappt gibt es nichts zu messen: die Marke bleibt, der Link auch.
    if (wrap.hidden || wrap.classList.contains("is-open")) return;
    // Der Clamp wird fuer die Messung kurz aufgehoben (innerhalb eines
    // Frames, es wird also nichts davon gezeichnet): an einem geklammerten
    // Block meldet scrollHeight je nach Zeitpunkt die geklammerte Hoehe.
    // Only a folded question is clamped (shell.css .is-long); an unfolded
    // one is measured as it stands, without the write that forced a second
    // style pass inside every send (Apple-Audit D3).
    let full;
    if (wrap.classList.contains("is-long")) {
      const previous = text.style.webkitLineClamp;
      text.style.webkitLineClamp = "unset";
      full = text.scrollHeight;
      text.style.webkitLineClamp = previous;
    } else full = text.scrollHeight;
    const line = parseFloat(getComputedStyle(text).lineHeight) || 24;
    wrap.classList.toggle("is-long", full > line * (FOLD_LINES + FOLD_MIN_HIDDEN_LINES) + 2);
  }

  // The observer measures after layout, before the frame is painted (its
  // first call comes with the first layout of the text); measuring here as
  // well read the half-built thread in the middle of every send and of every
  // streamed projection (Apple-Audit D3). Without an observer it measures now.
  function observeQuestionFold(wrap, text) {
    if (!wrap || !text) return;
    if (typeof ResizeObserver !== "function") { syncQuestionFold(wrap, text); return; }
    if (threadAskResizeObservers.has(text)) return;
    const observer = new ResizeObserver(() => syncQuestionFold(wrap, text));
    observer.observe(text);
    threadAskResizeObservers.set(text, observer);
  }

  // Dieselbe Geste fuer die aktive Frage (#threadAskMore) und fuer jede
  // archivierte im Verlauf: der Link gehoert immer zu der Blase, in der er
  // steht, deshalb wird der Umschalter aus dem geklickten Knopf abgeleitet.
  document.addEventListener("click", (event) => {
    const more = event.target.closest(".thread-ask-more");
    if (!more) return;
    const wrap = more.closest(".thread-ask, .thread-history-question");
    if (!wrap) return;
    const open = wrap.classList.toggle("is-open");
    more.textContent = open ? "Show less" : "Show more";
    more.setAttribute("aria-expanded", String(open));
    // A folded box starts at its first line, even after focus scrolled it.
    const text = wrap.querySelector(".thread-ask-text, .thread-history-question-text");
    if (text && !open) text.scrollTop = 0;
  });

  // Definition der Modelle und IDs (zentral, von mehreren Clustern genutzt).
  // EINE Quelle: der Server liefert die Familien aus cfg.PROVIDERS in
  // window.MODEL_FAMILIES; hier werden sie nur auf die im Frontend
  // etablierten Feldnamen gebracht. Eine neue Familie erscheint damit
  // ueberall, ohne dass eine dieser Listen nachgezogen werden muss.
  const modelFamilies = Array.isArray(window.MODEL_FAMILIES) ? window.MODEL_FAMILIES : [];
  // All model surfaces use the server registry, including newer Agent models.
  function createModelMark(model = {}) {
    const name = typeof model === "string" ? model : model.provider || "";
    const family = modelFamilies.find(f => [f.provider, f.label, f.title].some(v => v?.toLowerCase() === name.toLowerCase())
      || (f.apiPrefix && model.model?.startsWith(f.apiPrefix)));
    const mark = document.createElement(family?.icon ? "img" : "span");
    if (family?.icon) { mark.src = family.icon; mark.alt = ""; mark.className = family.iconClass || ""; }
    else { mark.textContent = (model.label || name || "M").slice(0, 1).toUpperCase(); mark.className = "model-mark-fallback"; }
    mark.setAttribute("aria-hidden", "true");
    return mark;
  }
  window.App.createModelMark = createModelMark;
  const modelPrefs = modelFamilies.map(family => ({
    key: family.label,
    provider: family.provider,
    label: family.title,
    shortLabel: family.shortLabel,
    citationLabel: family.citationLabel || family.label,
    checkId: family.checkboxId,
    selectId: family.selectId,
    responseId: family.responseId,
    textId: family.textId,
    endpoint: family.endpoint,
    attachmentModels: Array.isArray(family.attachmentModels)
      ? family.attachmentModels.slice()
      : (family.attachmentModels === null ? null : undefined),
    // Models of a family that reads files and still read none (gpt-oss-120b in
    // Open Models): without this list the panel ran into the server's 400.
    textOnlyModels: Array.isArray(family.textOnlyModels) ? family.textOnlyModels.slice() : [],
    handlesAttachments: family.handlesAttachments !== false
  }));

  // Der Reasoning-Schalter tauscht kein Modell: es zaehlt immer das gewaehlte.
  function modelAcceptsAttachments(pref, modelId) {
    if (!pref) return false;
    if (pref.textOnlyModels?.includes(String(modelId || ""))) return false;
    const allowed = pref.attachmentModels;
    if (Array.isArray(allowed)) {
      return allowed.includes(String(modelId || ""));
    }
    if (allowed === null) return true;
    return pref.handlesAttachments !== false;
  }

  // Hoechstzahl gleichzeitig laufender Familien (Serverregel, siehe
  // cfg.MAX_RUN_FAMILIES): mehr Familien duerfen konfiguriert sein, ein Lauf
  // bleibt trotzdem ein Sechs-Modell-Vergleich.
  const maxRunFamilies = Number(window.MAX_RUN_FAMILIES) > 0
    ? Number(window.MAX_RUN_FAMILIES)
    : 6;

  function getModelOptionLabel(option) {
    const explicitLabel = option?.dataset?.modelLabel;
    if (explicitLabel) return explicitLabel;
    return (option?.textContent || "").replace(/(?:\s*(?:Â·|·)\s*Pro)+$/i, "").trim();
  }

  // Einziges Renderziel des Konsenstextes. Frueher war das ein einzelnes <p>
  // unter .consensus-main, adressiert per ".consensus-main p" an einem guten
  // Dutzend Stellen. Das Inline-Marker-Rendering braucht einen stabilen
  // Blockcontainer, deshalb laeuft jeder Zugriff jetzt ueber diesen Helfer.
  // Der scope-Parameter erlaubt es, gezielt in einer bestimmten Konsens-Box zu
  // suchen (z. B. der von getConsensus gehaltenen Referenz).
  function consensusBodyEl(scope) {
    const root = scope || document;
    return (
      root.querySelector?.("#consensusAnswerBody")
      || root.querySelector?.(".consensus-main .consensus-answer-body")
      || null
    );
  }

  // An Enter that confirms a word an input method (Japanese, Chinese,
  // Korean) is still composing belongs to that word, never to a send or
  // save. Safari reports the confirming Enter with isComposing false but
  // keyCode 229 (Apple-Audit E8). Every Enter handler of a text field asks
  // this first.
  function isComposingKey(event) {
    return Boolean(event?.isComposing || event?.keyCode === 229);
  }

  // Enter in the composer: on a device whose keyboard is the touch screen it
  // is a new paragraph (there is a Send button under the thumb); with a
  // physical keyboard it sends, Shift+Enter breaks the line. Decided by the
  // device, not the window's width: a narrow desktop window sends, an iPad's
  // touch keyboard does not (Apple-Audit E7).
  const touchKeyboard = window.matchMedia?.("(hover: none) and (pointer: coarse)");
  function enterSends(event) {
    if (event?.key !== "Enter" || event.shiftKey || isComposingKey(event)) return false;
    return !touchKeyboard?.matches;
  }

  // The short notice of ~100 callers: a thin forward to the one notice line
  // (App.toast, notices.js), which queues, reads out and stays as long as it
  // takes to read. `options` passes on tone, action, duration.
  function showPopup(message, options = {}) {
    if (typeof window.App.toast === "function") return window.App.toast({ ...options, message });
    return null;
  }

  // The centered hero hides answer targets. The direct-comparison preview
  // uses the accessible thread shell even before a question has started.
  function syncHeroResponseAccess() {
    const responses = document.querySelector(".response-section");
    if (!responses) return;
    const hiddenInHero = document.body.classList.contains("is-hero");
    responses.inert = hiddenInHero;
    if (hiddenInHero) responses.setAttribute("aria-hidden", "true");
    else responses.removeAttribute("aria-hidden");
  }
  syncHeroResponseAccess();

  // Der Thread ist das Gegenteil der Vergleichsflaeche: wer den Hero verlaesst,
  // verlaesst auch den Direktvergleich. Die Marke haengen zu lassen waere eine
  // Mine — sie steuert Sichtbarkeit und inert der .response-section.
  function exitHeroMode() {
    glideComposer(() => {
      document.body.classList.remove("is-hero", "direct-comparison-active", "direct-comparison-preview");
      syncHeroResponseAccess();
    });
  }

  // Direct answers share the normal thread shell: question bubble, dimensions,
  // compact composer and upward-opening menus. Only the result differs.
  function enterDirectComparisonView() {
    glideComposer(() => {
      document.body.classList.remove("is-hero", "direct-comparison-preview");
      document.body.classList.add("direct-comparison-active");
      syncHeroResponseAccess();
    });
  }

  // Hero <-> thread moves the composer from the middle of the screen to its
  // place at the bottom (or back). The layouts share no transform a CSS
  // transition could run between, so the field glides from where it was
  // last drawn to where it now stands (FLIP). The new place is read just
  // before the next paint, after the rest of the task has built the thread
  // around it, so no frame shows the field at its end before it moves.
  //
  // It is one movement, also for the box's shape (Apple-Audit C2): the start
  // box and the thread's pill differ in height, and the pill used to stand
  // there at once, then glide. Now the box's height runs with the glide.
  // Leaving the start screen the bottom edge travels (the thread composer
  // stands on the bottom, the box shrinks onto its row of controls); coming
  // back the top edge travels (the start field hangs from its top). The
  // empty field's hint changes its place inside the box and shows again
  // where it ends; the tool bar under the field fades in the first part of
  // the way, out of the block's flow (.is-leaving, shell.css), and the
  // greeting fades with it (components-input.css). Nothing in between is
  // measured again: composer-collapse.js does not animate its own height
  // while body.composer-gliding is set.
  // The glide is a layer move (--dur-layer, --ease-out); the bar leaves at
  // the press tempo (shell.css .is-leaving) and settles just after it.
  const glideMs = () => window.App.motion?.ms("layer") ?? 320;
  const glideEasing = () => window.App.motion?.ease("out") ?? "cubic-bezier(0.22, 1, 0.36, 1)";
  const barFadeMs = () => (window.App.motion?.ms("press") ?? 120) + 20;
  let composerGlide = null;
  let barSettle = null;
  function settleLeavingBar(bar) {
    clearTimeout(barSettle);
    barSettle = null;
    if (!bar?.classList.contains("is-leaving")) return;
    bar.classList.remove("is-leaving");
    window.App.renderComposerMode?.();
  }
  function endGlide(composer, box) {
    composerGlide = null;
    document.body.classList.remove("composer-gliding");
    box?.classList.remove("is-morphing");
  }
  // The start place of the box, read where a gesture begins (query-send.js),
  // before the gesture writes anything: read later in the same task, it
  // forced the half-built thread's layout (Apple-Audit D3). Valid for the
  // task that read it.
  let anchoredBox = null;
  function barShown(bar) {
    return Boolean(bar && !bar.hidden && bar.getClientRects().length > 0);
  }
  function anchorGlide() {
    const box = document.querySelector(".input-section .chat-input-container");
    if (!box || anchoredBox) return;
    anchoredBox = { rect: box.getBoundingClientRect(), bar: barShown(document.getElementById("composerModeBar")) };
    setTimeout(() => { anchoredBox = null; }, 0);
  }
  function glideComposer(change) {
    const body = document.body;
    const composer = document.querySelector(".input-section");
    const box = composer?.querySelector(".chat-input-container");
    const wasHero = body.classList.contains("is-hero");
    const animate = Boolean(composer?.animate && box && !reducedMotion?.matches);
    const before = animate ? anchoredBox?.rect || box.getBoundingClientRect() : null;
    const bar = document.getElementById("composerModeBar");
    const fadeBar = animate && wasHero && (anchoredBox ? anchoredBox.bar : barShown(bar));
    if (fadeBar) bar.classList.add("is-leaving");
    change();
    // A call that does not cross the start screen's edge (the run projecting
    // its thread once more) leaves a running glide alone.
    if (!animate || wasHero === body.classList.contains("is-hero")) {
      if (fadeBar) settleLeavingBar(bar);
      return;
    }
    // Crossing it again mid-way starts from where the box is drawn now.
    if (composerGlide) composerGlide.forEach(animation => animation.cancel());
    body.classList.add("composer-gliding");
    if (fadeBar) barSettle = setTimeout(() => settleLeavingBar(bar), barFadeMs());
    requestAnimationFrame(() => {
      if (!composer.isConnected) { endGlide(composer, box); return; }
      // The field's height for its new state, written before the box is read.
      window.App.resizeQuestionInput?.();
      const leaving = wasHero && !body.classList.contains("is-hero");
      const after = box.getBoundingClientRect();
      const dx = before.left - after.left;
      const dy = leaving ? before.bottom - after.bottom : before.top - after.top;
      const morph = Math.abs(before.height - after.height) >= 1;
      if (Math.abs(dx) < 1 && Math.abs(dy) < 1 && !morph) { endGlide(composer, box); return; }
      const timing = { duration: glideMs(), easing: glideEasing() };
      const animations = [composer.animate([{ translate: `${dx}px ${dy}px` }, { translate: "0px 0px" }], timing)];
      if (morph) {
        // The row of controls stays on the box's bottom edge while it grows
        // or shrinks (composer.css .is-morphing).
        box.classList.add("is-morphing");
        animations.push(box.animate([{ height: `${before.height}px` }, { height: `${after.height}px` }], timing));
        const field = box.querySelector(".input-field");
        if (field) animations.push(field.animate([{ opacity: 0 }, { opacity: 0, offset: 0.55 }, { opacity: 1 }],
          { duration: glideMs(), easing: window.App.motion?.ease("linear") ?? "linear" }));
      }
      // The note under the pill comes in once the bar above it has gone.
      const note = leaving ? composer.querySelector(":scope > .app-footer") : null;
      if (note?.getClientRects().length) animations.push(note.animate([{ opacity: 0 }, { opacity: 0, offset: 0.4 }, { opacity: 1 }],
        { duration: glideMs(), easing: window.App.motion?.ease("linear") ?? "linear" }));
      composerGlide = animations;
      Promise.all(animations.map(animation => animation.finished)).then(() => {
        if (composerGlide === animations) endGlide(composer, box);
      }, () => {});
    });
  }

  window.exitHeroMode = exitHeroMode;
  window.enterDirectComparisonView = enterDirectComparisonView;
  window.syncHeroResponseAccess = syncHeroResponseAccess;

  // Einziger Eingang fuer Kontostaende aus API-Antworten: jede Antwort, die
  // das gemeinsame Tokenkonto kennt, traegt `token_budget` (auch in
  // Fehler-Details). Antworten ohne das Feld (eigene Keys) aendern nichts.
  // `owner` ist der RunContext/Auth-Stand des Aufrufers: eine spaete Antwort
  // eines frueheren Logins malt nie das naechste Konto an.
  function renderUsageDisplay(data, owner) {
    const auth = owner?.auth || owner;
    return window.App.tokenBudget?.fromResponse?.(data, { uid: auth?.uid || undefined }) || false;
  }

  // Ein logischer UI-Lauf teilt genau einen serverseitigen Idempotency-Key
  // zwischen /prepare, allen parallelen /ask_* und /consensus. Kosten oder
  // Modellanzahl kommen bewusst nicht aus dem Client.
  const usageRun = {
    current: null,
    start(deepThink, useOwnKeys) {
      let key = null;
      if (!useOwnKeys) {
        key = globalThis.crypto?.randomUUID?.();
        if (!key) {
          key = `${Date.now()}-${Math.random().toString(16).slice(2)}-${Math.random().toString(16).slice(2)}`;
        }
      }
      this.current = {
        key,
        deepThink: deepThink === true,
        useOwnKeys: useOwnKeys === true,
        status: useOwnKeys ? "own_keys" : "new"
      };
      return this.current;
    },
    ensure(deepThink, useOwnKeys) {
      if (
        !this.current
        || this.current.deepThink !== (deepThink === true)
        || this.current.useOwnKeys !== (useOwnKeys === true)
      ) {
        return this.start(deepThink, useOwnKeys);
      }
      return this.current;
    },
    mark(status) {
      if (this.current && status) this.current.status = status;
    },
    clear() {
      this.current = null;
    }
  };

  Object.assign(window.App, {
    modelPrefs,
    maxRunFamilies,
    modelAcceptsAttachments,
    getModelOptionLabel,
    getSelectedModelCount,
    setAppTitle,
    setThreadQuestion,
    normalizeQuestionText,
    fillQuestionText,
    observeQuestionFold,
    setThreadQuestionAttachments,
    setPendingThreadQuestion,
    clearPendingThreadQuestion,
    revealSentMessage,
    getThreadAttachments,
    consensusBodyEl,
    scrollBehavior,
    trackAppEvent,
    trackAsk,
    trackAnswer,
    showPopup,
    isComposingKey,
    enterSends,
    exitHeroMode,
    enterDirectComparisonView,
    glideComposer,
    anchorGlide,
    syncHeroResponseAccess,
    renderUsageDisplay,
    usageRun
  });
})();
