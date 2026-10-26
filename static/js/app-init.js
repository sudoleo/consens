// =====================================================================
// app-init.js
// App initialisation / orchestration. This is the remaining initApp()
// bootstrap after the feature clusters were extracted into their own
// modules: theme, usage/limits + user status, response-box UI toggles,
// sidebar/layout, modals, tooltips, evidence rendering, API-key test and
// all the DOM event wiring that glues the window.* contracts together.
//
// MUST load last (after all other static/js modules, firebase.js and
// demo.js): it aliases window.App.* and many window.* helpers at
// initApp() time and wires the document's event listeners. Loaded via a
// deferred <script> at the end of <body> in templates/index.html, so it
// runs after every earlier module in document order.
//
// The daily allowance is a token account shared by every mode; it lives in
// window.App.tokenBudget (token-budget.js), not in a Jinja value.
// =====================================================================

      (function () {
        // localStorage wirft bei gesperrtem Speicher (blockierte Cookies,
        // manche privaten Modi) schon beim Zugriff. Ein Wurf in initApp braeche
        // den Start ab und liesse die App halb verdrahtet stehen. Deshalb geht
        // jeder Zugriff hier ueber diese Helfer - wie in user-settings.js mit
        // einer Seiten-Ablage fuer verweigerte Werte: die Wahl gilt dann
        // wenigstens bis zum naechsten Laden.
        const storageOverlay = new Map();

        function readStored(key) {
          if (storageOverlay.has(key)) return storageOverlay.get(key);
          try { return window.localStorage.getItem(key); } catch (_) { return null; }
        }

        function writeStored(key, value) {
          try {
            if (value === null) window.localStorage.removeItem(key);
            else window.localStorage.setItem(key, value);
            storageOverlay.delete(key);
          } catch (_) {
            storageOverlay.set(key, value);
          }
        }

        function initApp() {
        // --------------------------
        // Dark/Light Mode Initialisierung
        // --------------------------
        // Zugriff auf die Checkboxen:

        // Global verfügbar für alle Funktionen
        window.App.state.set("spinnerHTML", `
          <span class="thinking-wrap" role="status" aria-live="polite" aria-busy="true">
            <span class="thinking typing-indicator" data-text="Typing" aria-label="Typing">Typing<span class="typing-dots" aria-hidden="true"><span>.</span><span>.</span><span>.</span></span></span>
          </span>
        `, "runUi");
        window.consensusSpinnerHTML = `
          <span class="thinking-wrap consensus-thinking-wrap" role="status" aria-live="polite" aria-busy="true">
            <span class="consensus-loader" aria-hidden="true"><span></span><span></span><span></span><span></span></span>
            <span class="thinking consensus-thinking">Synthesizing consensus</span>
          </span>
        `;
        // Der Differences-Judge liefert JSON, das erst am Ende sichtbar wird.
        // Frueher stand hier erst eine eigene Fortschrittsleiste, dann noch das
        // Wort "Comparing responses". Beides sagte, was der gefuehrte Lauf
        // ueber dem Thread ohnehin schon ansagt ("Checking for contradictions").
        // Es gibt genau EINE Fortschrittsanzeige, also bleibt hier nichts.
        window.consensusDifferencesSpinnerHTML = "";

        // Geteilte Config + Helfer kommen aus static/js/app-core.js (window.App).
        // Lokale Aliase, damit die bestehenden Aufrufstellen in initApp
        // unverändert bleiben (Übergangsbus, siehe app-core.js).
        const {
          modelPrefs,
          getModelOptionLabel,
          getSelectedModelCount,
          trackAppEvent,
          showPopup
        } = window.App;

        // View classes and answer previews live in static/js/agent-mode.js;
        // the mode choice (Agent / Compare) in static/js/run-mode.js.
        const setAgentModeStatus = window.setAgentModeStatus;
        const updateAgentModeUI = window.updateAgentModeUI;

        // Model-Picker + Modell-Auswahl sind nach static/js/model-picker.js
        // ausgelagert; lokale Aliase für das in initApp verbliebene Wiring
        // (Event-Listener + Init-Aufrufe). restoreModelSelections und
        // syncCustomModelPickers liegen direkt auf window.
        const setModelSelectionState = window.App.setModelSelectionState;
        const openModelPicker = window.App.openModelPicker;
        const collapseExpandedModelPicker = window.App.collapseExpandedModelPicker;
        const initCustomModelPicker = window.App.initCustomModelPicker;

        // Tier-/Pro-UI ist nach static/js/user-tier.js ausgelagert; lokale Aliase
        // für die Aufrufstellen in initApp.
        const updateUserTierUI = window.updateUserTierUI;
        const updatePremiumModelsState = window.updatePremiumModelsState;
        // Brücke: user-tier.js nutzt updateReasoningUI (gehoistete Fn-Decl in initApp).
        window.App.updateReasoningUI = updateReasoningUI;

        const modeToggles = Array.from(document.querySelectorAll(".theme-toggle"));

        function applyTheme(theme) {
          const isDark = theme === "dark";
          if (theme === "dark") {
            document.body.classList.add("dark-mode");
          } else {
            document.body.classList.remove("dark-mode");
          }

          modeToggles.forEach(toggle => {
            toggle.classList.toggle("is-dark", isDark);
            toggle.setAttribute("aria-pressed", String(isDark));
            toggle.setAttribute("aria-label", isDark ? "Switch to light mode" : "Switch to dark mode");
            toggle.title = isDark ? "Switch to light mode" : "Switch to dark mode";
          });
        }

        // Markdown-Rendering + SSE-Streaming-Helfer sind nach
        // static/js/markdown-stream.js ausgelagert (window.injectMarkdown,
        // window.createStreamRenderer, window.streamSSERequest). Lokale Aliase,
        // damit die bestehenden Aufrufstellen in initApp unverändert bleiben.
        const injectMarkdown = window.injectMarkdown;
        const createStreamRenderer = window.createStreamRenderer;
        const streamSSERequest = window.streamSSERequest;

        // Quellen-/Evidence-Handling ist nach static/js/sources.js ausgelagert
        // (window.linkifySourceTags, window.mergeEvidenceSources, window.rewriteSourceTags,
        // window.registerResponseSources, window.prepareResponseSources,
        // window.renderModelResponseWithSources). Alle Aufrufer nutzen bereits window.*,
        // daher keine lokalen Aliase noetig.

        // Lese gespeicherten Wert aus; wenn keiner vorhanden, verwende die Systempräferenz:
        let storedTheme = readStored("theme");
        if (!storedTheme) {
          storedTheme = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
          writeStored("theme", storedTheme);
        }
        applyTheme(storedTheme);

        // Schalte den Dark Mode um und speichere die Auswahl:
        modeToggles.forEach(toggle => {
          toggle.addEventListener("click", function () {
            const newTheme = document.body.classList.contains("dark-mode") ? "light" : "dark";
            writeStored("theme", newTheme);
            // One step, not a smear of different speeds (Apple audit C8).
            if (window.App.motion?.switchTheme) window.App.motion.switchTheme(() => applyTheme(newTheme));
            else applyTheme(newTheme);
          });
        });

        // Agreement bleibt standardmaessig sichtbar. Wer weniger davon lesen
        // will, waehlt eine von drei Stufen, die fuer Live- und archivierte
        // Consensus-Antworten gemeinsam gilt:
        //   full    — Zahl, Balken und Einordnung
        //   summary — nur die Worte, keine Zahl (die alte Aus-Stellung)
        //   off     — gar kein Urteilsbereich, unter der Antwort bleiben nur
        //             die Schubladen (Differences / Answers / Sources)
        // Kontoeinstellung "agreement_display" (user-settings.js, dort auch
        // die Migration des Vorgaenger-Schalters).
        const AGREEMENT_DISPLAY_MODES = ["full", "summary", "off"];
        const agreementDisplaySelect = document.getElementById("agreementDisplaySelect");

        function applyAgreementDisplayPreference(mode) {
          document.body.classList.toggle("agreement-score-hidden", mode === "summary");
          document.body.classList.toggle("agreement-verdict-hidden", mode === "off");
          if (agreementDisplaySelect) agreementDisplaySelect.value = mode;
        }

        function restoreAgreementDisplayPreference() {
          applyAgreementDisplayPreference(window.App.userSettings.get("agreement_display") || "full");
        }

        restoreAgreementDisplayPreference();
        window.App.userSettings.onChange("agreement_display", detail => {
          if (detail.source !== "local") restoreAgreementDisplayPreference();
        });
        agreementDisplaySelect?.addEventListener("change", function () {
          const mode = AGREEMENT_DISPLAY_MODES.includes(this.value) ? this.value : "full";
          window.App.userSettings.set("agreement_display", mode);
          applyAgreementDisplayPreference(mode);
          trackAppEvent("app_agreement_score_visibility_changed", {
            mode: mode,
            visible: mode === "full"
          });
        });

        window.addEventListener("pageshow", restoreAgreementDisplayPreference);


        const questionInput = document.getElementById("questionInput");
        const defaultQuestionPlaceholder = "Enter your question";
        const lockedQuestionPlaceholder = "Log in to start asking questions for free.";

        const resizeQuestionInput = window.App.initComposerAutosize(questionInput);
        window.App.resizeQuestionInput = resizeQuestionInput;

        function hasVerifiedSession() {
          return Boolean(window.auth?.currentUser?.emailVerified);
        }

        // Angemeldet, aber die E-Mail ist noch nicht bestaetigt. Frueher wurde
        // dieser Zustand sofort ausgeloggt; jetzt bleibt der Nutzer in der App
        // und sieht den Bestaetigungs-Streifen (#verifyBanner). Tippen darf er
        // dabei — nur der Lauf selbst wartet auf die Bestaetigung, damit die
        // getippte Frage den Klick auf den Verify-Link ueberlebt.
        function hasUnverifiedSession() {
          const user = window.auth?.currentUser;
          return Boolean(user && !user.emailVerified);
        }
        window.hasUnverifiedSession = hasUnverifiedSession;

        // Gaeste tippen auch (seit 2026-10-15): erst die Frage, die Anmeldung
        // kommt beim Absenden (composer-invite.js). Nur ein unerreichbarer
        // Login sperrt das Feld, dann koennte kein Konto sie abschicken. Eine
        // gespeicherte Sitzung, die noch wiederhergestellt wird, ist kein Gast.
        // Dieselbe Regel wie das erste Bild (app-bootstrap.js App.isGuest).
        function isGuestComposer() {
          if (window.App.isGuest) return window.App.isGuest();
          if (window.auth?.currentUser) return false;
          if (document.documentElement.dataset.authUnavailable === "true") return false;
          const authState = window.__consensioAuthState;
          if (authState?.known) return !authState.uid;
          // The session app-bootstrap.js expects before Firebase answers.
          return !(window.App.expectedSession ? window.App.expectedSession().account : readStored("id_token"));
        }
        window.App.isGuestComposer = isGuestComposer;

        window.userCanAskQuestions = function () {
          return hasVerifiedSession();
        };

        // Wer tippen darf, ist nicht dasselbe wie wer starten darf.
        window.userCanTypeQuestions = function () {
          return hasVerifiedSession() || hasUnverifiedSession() || isGuestComposer();
        };

        const unverifiedQuestionPlaceholder =
          "Type your question — confirm your email to run it";

        // Landing field -> /app?focus=1: arrive with the caret in the composer.
        // The parameter goes again at once, so a reload or bookmark is plain.
        // The field only takes the caret once the account may type into it
        // (updateQuestionInputAccess below); a guest may, and signs in when
        // the question is sent.
        let pendingComposerFocus = false;
        try {
          const url = new URL(window.location.href);
          if (url.searchParams.get('focus') === '1') {
            pendingComposerFocus = true;
            url.searchParams.delete('focus');
            window.history.replaceState(window.history.state, '', url.pathname + url.search + url.hash);
          }
        } catch (e) { /* a missing History API only costs the caret */ }

        window.updateQuestionInputAccess = function () {
          const canAsk = window.userCanAskQuestions();
          const canType = window.userCanTypeQuestions();
          const guest = isGuestComposer();
          const unverified = hasUnverifiedSession();
          document.body.classList.toggle("is-guest", guest);
          const selectedModelCount = window.App.getSelectedModelCount?.() || 0;
          const agent = window.App.agentChat?.isSelected?.();
          const agentBlocker = agent ? window.App.agentChat.sendBlocker() : null;
          const hasMinimumModels = agent
            ? !agentBlocker
            : selectedModelCount >= 2;
          // Files alone are a message too: they go out under their names.
          const hasMessage = !agent || Boolean(String(window.App.quote?.compose?.(questionInput?.value || '') ?? questionInput?.value ?? '').trim())
            || Boolean(window.App.attachments?.messageText?.());
          // A stored Agent choice waits for the account's Agent access instead
          // of sending as Compare in the moment before it arrives.
          const mode = window.App.agentChat?.modeState?.();
          const modePending = window.App.runMode?.preference?.() === "agent" && !mode?.family && mode?.pending === true;
          const canStartRun = canAsk && hasMinimumModels && hasMessage && !modePending;
          const sendButton = document.getElementById("sendButton");
          const postDemoLoginPrompt = document.getElementById("postDemoLoginPrompt");

          // A stored session still being restored keeps the words the field
          // was painted with (app-bootstrap.js); "Sign in" in between only
          // flickered past before the account arrived.
          const restoring = !canType && !window.__consensioAuthState?.known
            && document.documentElement.dataset.authUnavailable !== "true"
            && Boolean(window.App.expectedSession ? window.App.expectedSession().account : readStored("id_token"));
          if (questionInput) {
            questionInput.disabled = !canType;
            if (!restoring) {
              questionInput.placeholder = canAsk
                ? defaultQuestionPlaceholder
                : unverified
                  ? unverifiedQuestionPlaceholder
                  : guest
                    ? window.App.askPlaceholder()
                    : lockedQuestionPlaceholder;
            }
            questionInput.setAttribute("aria-disabled", String(!canType));
            if (pendingComposerFocus && canType) {
              pendingComposerFocus = false;
              questionInput.focus({ preventScroll: true });
            } else if (pendingComposerFocus && window.__consensioAuthState?.known) {
              pendingComposerFocus = false;
            }
          }

          // A guest's Send asks for the sign-in (composer-invite.js), so it
          // works as soon as there is something to send.
          const guestCanSend = guest && Boolean(questionInput?.value.trim());
          if (sendButton && !sendButton.classList.contains("is-cancel-action")) {
            sendButton.disabled = !canStartRun && !guestCanSend;
            sendButton.title = !canAsk
              ? unverified
                ? "Confirm your email address to start this run"
                : guest
                  ? "Log in to send your question. It’s free."
                  : "Log in to ask questions or use your own API keys"
              : agent
                ? agentBlocker?.message || (hasMessage ? "Send message" : "Write a message to send")
              : hasMinimumModels
                ? "Send question"
                : "Select at least two models to compare";
            sendButton.setAttribute("aria-label", sendButton.title);
            sendButton.setAttribute("aria-disabled", String(sendButton.disabled));
          }

          if (canAsk && postDemoLoginPrompt) {
            postDemoLoginPrompt.hidden = true;
            postDemoLoginPrompt.classList.remove("is-visible");
          }

          // Nach einer Antwort traegt das Feld den Follow-up-Platzhalter.
          // Diese Funktion laeuft nach jedem Auth-Update und wuerde ihn sonst
          // wieder mit dem Standardtext ueberschreiben.
          window.App?.followup?.syncInputLock?.();
          window.App.agentChat?.syncComposer?.();
          // A question sent as a guest goes out once the new session can run it.
          window.App.composerInvite?.afterAccessUpdate?.(canStartRun);

          return canStartRun;
        };

        // The first call follows the draft's restore below.
        // Login unreachable (auth-bootstrap.js): no session is coming, so the
        // field stops waiting for one and says why it is locked.
        window.addEventListener("consensio:auth-unavailable", () => window.updateQuestionInputAccess());

        // --- Frage-Entwurf ueber den Bestaetigungs-Umweg retten ------------
        // Wer auf den Link im Postfach klickt, verlaesst diese Seite. Kaeme er
        // mit leerem Feld zurueck, waere die Bestaetigung eine Strafe fuer den
        // Versuch, etwas zu fragen. Gespeichert wird nur, solange der Lauf
        // nicht starten kann — ein verifizierter Nutzer braucht keinen
        // Zwischenspeicher, und alte Fragen sollen nicht wieder auftauchen.
        const QUESTION_DRAFT_KEY = "consensio.questionDraft.v1";
        // Whole, never cut: a pasted answer to check runs to the Agent limit
        // (8,000 characters), and a guest's question goes out by itself after
        // the sign-in only when the field holds exactly what was sent.
        const QUESTION_DRAFT_MAX_CHARS = 20000;
        // A detour through the mailbox takes minutes, not days; on a shared
        // device the next visitor should not find someone's unsent question.
        const QUESTION_DRAFT_MAX_AGE_MS = 24 * 60 * 60 * 1000;

        function storeQuestionDraft(value) {
          // Private/gehaertete Browser: dann haelt nur die Seiten-Ablage.
          const text = String(value || "").trim().slice(0, QUESTION_DRAFT_MAX_CHARS);
          writeStored(QUESTION_DRAFT_KEY, text ? JSON.stringify({ text, at: Date.now() }) : null);
        }

        function readQuestionDraft() {
          const stored = readStored(QUESTION_DRAFT_KEY) || "";
          let draft = null;
          try { draft = JSON.parse(stored); } catch (_) { /* a plain string from before 2026-10-16 */ }
          if (!draft || typeof draft.text !== "string") return stored;
          if (!(Date.now() - Number(draft.at) <= QUESTION_DRAFT_MAX_AGE_MS)) {
            storeQuestionDraft("");
            return "";
          }
          return draft.text;
        }

        window.App.clearQuestionDraft = function () {
          storeQuestionDraft("");
        };
        // A guest's Send keeps the question for the way through the sign-in,
        // also one an example filled in (no keystroke, so no input below).
        window.App.saveQuestionDraft = function (value) {
          storeQuestionDraft(value);
        };

        // Nur ECHTE Tastenanschlaege sind ein Entwurf. Programmatische
        // input-Events (clearResponseBoxes beim Auth-Wechsel, Demo-Tippen)
        // haetten den Entwurf sonst geloescht, bevor er gebraucht wurde.
        questionInput?.addEventListener("input", event => {
          if (!event.isTrusted) return;
          // Signed in, the field needs no stand-in: a draft left from before
          // the sign-in goes with the first keystroke instead of coming back
          // on every start after it was deleted by hand.
          if (window.userCanAskQuestions()) {
            if (readStored(QUESTION_DRAFT_KEY)) storeQuestionDraft("");
            return;
          }
          storeQuestionDraft(questionInput.value);
        });

        // Idempotent: fuellt nur ein leeres Feld. Wird beim Start UND nach
        // jedem Auth-Wechsel aufgerufen (firebase.js), weil der Auth-Callback
        // den Composer ueber resetLoadedRunAfterLogout() leert — und genau
        // dieser Callback laeuft, wenn der Nutzer nach der Bestaetigung
        // zurueckkommt.
        window.App.restoreQuestionDraft = function () {
          if (!questionInput || questionInput.value.trim()) return;
          const draft = readQuestionDraft();
          if (!draft) return;
          questionInput.value = draft;
          requestAnimationFrame(resizeQuestionInput);
          window.syncDemoChipState?.();
          // A guest's Send follows the text it now has.
          window.updateQuestionInputAccess?.();
        };

        window.App.restoreQuestionDraft();
        // Only now, with the draft back in the field: after the sign-in's
        // reload the account's status can be in before this start, and a
        // question sent as a guest goes out only when the field holds it
        // again (composer-invite.js). Before, the empty field used up its
        // one try.
        window.updateQuestionInputAccess();

        function isCompactControlLayout() {
          return window.matchMedia("(max-width: 900px)").matches;
        }

        // A thin forward to the one notice line (App.toast, notices.js).
        function showMobileInfoPopup(message) {
          if (!message || !isCompactControlLayout()) return;
          window.App.toast?.({ message });
        }
        window.showMobileInfoPopup = showMobileInfoPopup;

        // Der Modus-Erklaerer ist mit seinem (i)-Trigger entfallen: die
        // Modi werden jetzt dort erklaert, wo man sie schaltet (Settings,
        // (+)-Menue) und waehrend sie laufen (gefuehrter Lauf).

        // Der Reasoning-Schalter (#reasoningToggle) tauscht seit 2026-10-02
        // weder Antwortmodelle noch die Consensus-Engine: dieselben gewaehlten
        // Modelle denken nur laenger. Diese Funktion haelt deshalb nur die
        // Modell-Ueberschriften und den Composer synchron.
        function updateReasoningUI() {
          document.querySelectorAll(".model-picker-wrapper").forEach(el => {
            el.style.display = "inline-flex";
          });

          const selectedModelLabel = (selectId) => {
            const select = document.getElementById(selectId);
            return getModelOptionLabel(select?.options[select.selectedIndex]) || select?.value || "";
          };
          // Picker and Reasoning controls configure the next run. Headings in
          // the selected result keep the model labels frozen at that run's
          // start, even when those controls change while it is in background.
          const visibleRun = window.App.runRegistry?.visible?.();
          const runLabels = visibleRun
            ? Object.fromEntries(
              (visibleRun.config?.providers || []).map(provider => [
                provider.provider,
                provider.modelLabel || provider.modelId || provider.provider
              ])
            )
            : {};

          const setModelText = (id, txt) => {
            const el = document.getElementById(id);
            if (el) {
              el.textContent = txt;
              el.title = `Choose model: ${txt}`;
            }
          };
          (window.App.modelPrefs || []).forEach(pref => {
            const text = runLabels[pref.key] || selectedModelLabel(pref.selectId);
            setModelText(pref.textId, text);
          });

          if (typeof window.updateAgentModeUI === "function") {
            window.updateAgentModeUI();
          }
        }

        // Reasoning-Schalter: fuer alle Stufen frei, kein Pro-Gate.
        document.getElementById("reasoningToggle").addEventListener("change", function () {
          updateReasoningUI();
          trackAppEvent("app_reasoning_changed", { enabled: this.checked });
        });

        updateReasoningUI();

        // Datei-Anhaenge (Pro) sind nach static/js/attachments.js ausgelagert
        // (window.pendingAttachments, window.renderAttachmentChips,
        // window.clearPendingAttachments, window.getAttachmentsPayload,
        // window.showBookmarkAttachments). Alle Aufrufer nutzen window.*.

        // Diese Funktion prüft den Status sofort beim Laden
        async function checkUserStatusOnLoad(user) {
          if (!user) return;

          try {
            const token = await user.getIdToken();

            // Aufruf an den neuen Backend-Endpoint
            const response = await fetch("/user_status", {
              method: "GET",
              headers: {
                "Authorization": "Bearer " + token,
                "Content-Type": "application/json"
              }
            });

            if (response.ok) {
              const data = await response.json();

              // 1. UI sofort umschalten (Badge an, Modelle frei)
              updateUserTierUI(data.tier ?? data.is_pro, true);

              // 2. Das Tokenkonto des Tages steht schon in /user_status.
              window.App.tokenBudget?.apply?.(data.token_budget, {
                uid: user.uid, authoritative: true
              });
            }
          } catch (error) {
            console.error("Fehler beim Laden des User-Status:", error);
          }
        }

        // Muss zum Push/Overlay-Umschaltpunkt in layout.css (1099px) passen.
        const SIDEBAR_OVERLAY_BREAKPOINT = 1099;
        const SIDEBAR_COLLAPSED_STORAGE_KEY = "sidebar_collapsed";

        function usesOverlaySidebar() {
          return window.matchMedia(`(max-width: ${SIDEBAR_OVERLAY_BREAKPOINT}px)`).matches;
        }

        // Neben dem Inhalt (ab 1100px): die eigene Wahl, sonst seit
        // 2026-10-18 fuer Gaeste eingeklappt (der erste Besuch beginnt bei der
        // Frage, nicht bei einer leeren Chatliste) und fuer Konten offen.
        // Dieselbe Regel malt app-bootstrap.js in den ersten Frame.
        function prefersCollapsedSidebar() {
          const stored = readStored(SIDEBAR_COLLAPSED_STORAGE_KEY);
          if (stored !== null) return stored === "true";
          if (window.auth?.currentUser) return false;
          const authState = window.__consensioAuthState;
          if (authState?.known) return !authState.uid;
          return !(window.App.expectedSession ? window.App.expectedSession().account : readStored("id_token"));
        }

        // Ohne Gleiten: Start und Anmeldung sind keine Geste des Lesers, die
        // Spalte soll nicht vor ihm zur Seite rutschen.
        function setSidebarCollapsedInstantly(sidebar, collapsed) {
          if (sidebar.classList.contains("collapsed") === collapsed) return;
          document.body.classList.add("is-sidebar-settling");
          sidebar.classList.toggle("collapsed", collapsed);
          void sidebar.offsetWidth;
          document.body.classList.remove("is-sidebar-settling");
        }

        // The fixed phone composer's height, as room at the column's end
        // (shell.css --thread-composer-height). Written on the column, which
        // alone reads it: on <html> every change restyled the whole page.
        // While the composer opens, closes or glides, its height changes each
        // frame; the room follows once, with the height it ends at
        // (Apple-Audit D9).
        const threadComposer = document.querySelector(".input-section");
        const threadColumn = threadComposer?.closest(".container") || null;
        const MOVING_COMPOSER = ["composer-animating", "composer-gliding"];
        // The same height as the page's scroll-padding, at every width: a
        // link or mark reached with Tab scrolls into view above the composer
        // (sticky on a desktop, fixed on a phone) instead of behind it (WCAG
        // 2.4.11, a11y audit K3). A plain property of <html>, not a custom
        // one, so its change restyles nothing below.
        function syncFocusReserve(height) {
          const root = document.documentElement;
          const value = height > 0 && !document.body.classList.contains("is-hero") ? `${height}px` : "";
          if (root.style.scrollPaddingBottom !== value) root.style.scrollPaddingBottom = value;
        }
        function syncThreadComposerReserve() {
          if (!threadComposer) return;
          const moving = MOVING_COMPOSER.some(name => document.body.classList.contains(name));
          const composerHeight = moving ? 0 : Math.ceil(threadComposer.getBoundingClientRect().height);
          if (!moving) syncFocusReserve(composerHeight);
          if (!threadColumn || !usesOverlaySidebar()) {
            threadColumn?.style.removeProperty("--thread-composer-height");
            return;
          }
          if (moving) return;

          const value = `${composerHeight}px`;
          if (composerHeight > 0 && threadColumn.style.getPropertyValue("--thread-composer-height") !== value) {
            threadColumn.style.setProperty("--thread-composer-height", value);
          }
        }

        if (threadComposer && typeof ResizeObserver === "function") {
          const threadComposerObserver = new ResizeObserver(syncThreadComposerReserve);
          threadComposerObserver.observe(threadComposer);
        }
        // The end of a move: its final height (the observer kept quiet).
        // The start page has no composer over the text: no reserve there.
        let composerWasMoving = false;
        let wasHero = document.body.classList.contains("is-hero");
        new MutationObserver(() => {
          const moving = MOVING_COMPOSER.some(name => document.body.classList.contains(name));
          const hero = document.body.classList.contains("is-hero");
          if ((composerWasMoving && !moving) || hero !== wasHero) requestAnimationFrame(syncThreadComposerReserve);
          composerWasMoving = moving;
          wasHero = hero;
        }).observe(document.body, { attributes: true, attributeFilter: ["class"] });
        requestAnimationFrame(syncThreadComposerReserve);

        // On a phone or tablet the open sidebar is a drawer over the page
        // (Apple audit E6): the page behind is inert while it is open, focus
        // goes into it and comes back to the menu button when it closes, and
        // Escape closes it. What lives on <body> for the drawer (a chat's row
        // menu, the notice line, dialogs) stays usable.
        const DRAWER_BACKDROP = [".container", ".app-mobile-header", ".app-nav-float", "#authTopActions",
          "#viewSwitch", "#mobileConversationActions", ".app-bottom-edge"];
        let drawerOpen = false;
        function syncDrawerFocus(sidebar, open) {
          if (open === drawerOpen) return;
          drawerOpen = open;
          DRAWER_BACKDROP.forEach(function (selector) {
            document.querySelectorAll(selector).forEach(function (element) {
              // What the phone layout moved into the drawer (the Chat |
              // Watches switch) belongs to it, not to the page behind.
              if (element.contains(sidebar) || sidebar.contains(element)) return;
              element.inert = open;
            });
          });
          const active = document.activeElement;
          if (open) {
            const target = sidebar.querySelector("#sidebarToggleInner") || sidebar.querySelector("button:not([disabled])");
            if (target && !sidebar.contains(active)) target.focus({ preventScroll: true });
          } else if (!active || active === document.body || sidebar.contains(active)) {
            // The menu button was inert a moment ago; now it takes focus back.
            document.getElementById("toggleSidebarButton")?.focus({ preventScroll: true });
          }
        }
        // Capture: a menu or dialog open above the drawer takes its Escape
        // first (they stop it); only a plain Escape closes the drawer.
        window.addEventListener("keydown", function (event) {
          if (event.key !== "Escape" || event.isComposing || !drawerOpen) return;
          if (document.querySelector("dialog[open]")) return;
          if (window.App?.popover?.anyOpen?.()) return;
          const sidebar = document.querySelector(".sidebar");
          if (!sidebar?.classList.contains("active")) return;
          if (event.target?.closest?.(".bookmark-rename-input")) return;
          const hadFocus = sidebar.contains(document.activeElement);
          closeOverlaySidebar();
          if (hadFocus || document.activeElement === document.body) {
            document.getElementById("toggleSidebarButton")?.focus({ preventScroll: true });
          }
        }, true);

        function closeOverlaySidebar() {
          const sidebar = document.querySelector(".sidebar");
          if (!sidebar || !usesOverlaySidebar()) return;
          sidebar.classList.remove("active");
          sidebar.classList.add("collapsed");
          updateToggleButton();
        }

        document.addEventListener("click", function (event) {
          const sidebar = document.querySelector(".sidebar");
          if (!sidebar || !usesOverlaySidebar() || !sidebar.classList.contains("active")) return;
          // A click in a dialog (Settings opened from the sidebar, its
          // backdrop) belongs to the dialog, not to the page behind it. The
          // sidebar stays, so closing the dialog can hand focus back to the
          // gear inside it. A chat's row menu and its "Undo" line belong to
          // the list too.
          if (event.target.closest("dialog, .bookmark-menu, .toast-region")) return;

          if (!sidebar.contains(event.target) && !event.target.closest(".sidebar-toggle")) {
            closeOverlaySidebar();
          }
        });

        // The phone menu follows the finger (Apple audit F11): a swipe to the
        // left takes it along, the dim fades with it, and it closes once it
        // is a third of the way out or was flicked; let go earlier and it
        // settles back. Up and down stay the list's own scroll (shell.css
        // gives the open menu touch-action: pan-y). From the menu or the
        // dimmed page; focus goes back to the menu button as on every close.
        (function bindDrawerSwipe() {
          const sidebar = document.querySelector(".sidebar");
          if (!sidebar || typeof window.PointerEvent !== "function") return;
          const SLOP = 10;
          let drag = null;

          // The dim goes on from where the finger left it, to the state the
          // class change gives it, in the menu's own time; the page's CSS
          // takes over when it ends (a cancelled script animation does not
          // hand its value to a CSS transition).
          function settleDim(dim, to) {
            if (!dim) return;
            const from = Number(getComputedStyle(document.body, "::after").opacity);
            dim.cancel();
            if (window.App.motion?.reduced?.() || !Number.isFinite(from)) return;
            try {
              document.body.animate([{ opacity: from, visibility: "visible" }, { opacity: to, visibility: "visible" }],
                { pseudoElement: "::after", duration: window.App.motion?.ms?.("layer") || 320,
                  easing: window.App.motion?.ease?.("standard") || "ease" });
            } catch (_) { /* the dim simply takes its state */ }
          }
          // A finger that moved makes no tap; should a browser still send the
          // click of this gesture, it lands nowhere. The next real tap counts.
          function swallowNextClick() {
            const swallow = event => { event.preventDefault(); event.stopPropagation(); };
            window.addEventListener("click", swallow, { capture: true, once: true });
            setTimeout(() => window.removeEventListener("click", swallow, true), 80);
          }
          document.addEventListener("pointerdown", function (event) {
            // A second finger leaves the first one's swipe alone: dropping it
            // here left the menu stuck half way, with no finger to end it
            // (review 13). A new first finger ends a swipe whose end was lost.
            if (!event.isPrimary) return;
            if (drag?.moving) {
              sidebar.classList.remove("is-dragging");
              sidebar.style.removeProperty("transform");
              settleDim(drag.dim, 1);
            }
            drag = null;
            if (event.pointerType !== "touch") return;
            if (!usesOverlaySidebar() || !sidebar.classList.contains("active")) return;
            const onDim = event.target === document.body;
            if (!onDim && !sidebar.contains(event.target)) return;
            // A field keeps its own drag (selecting text), a chat being renamed too.
            if (event.target.closest?.("input, textarea, select, [contenteditable='true'], .bookmark.is-renaming")) return;
            drag = { id: event.pointerId, x: event.clientX, y: event.clientY, width: sidebar.getBoundingClientRect().width || 1,
              moving: false, offset: 0, lastX: event.clientX, lastT: event.timeStamp, velocity: 0, dim: null };
          }, true);
          document.addEventListener("pointermove", function (event) {
            if (!drag || event.pointerId !== drag.id) return;
            const dx = event.clientX - drag.x;
            const dy = event.clientY - drag.y;
            if (!drag.moving) {
              if (Math.abs(dx) < SLOP && Math.abs(dy) < SLOP) return;
              // Up, down or to the right: not a close.
              if (dx > -SLOP || Math.abs(dy) > Math.abs(dx)) { drag = null; return; }
              drag.moving = true;
              try { sidebar.setPointerCapture(drag.id); } catch (_) { /* captured by the browser */ }
              // "Reduce motion": the menu does not travel (it fades, motion.css);
              // the swipe still closes it.
              drag.follow = !window.App.motion?.reduced?.();
              if (!drag.follow) return;
              sidebar.classList.add("is-dragging");
              try {
                drag.dim = document.body.animate([{ opacity: 1 }, { opacity: 0 }],
                  { pseudoElement: "::after", duration: 1000, fill: "both", easing: "linear" });
                drag.dim.pause();
              } catch (_) { drag.dim = null; }
            }
            drag.offset = Math.min(0, dx + SLOP);
            if (event.timeStamp > drag.lastT) {
              drag.velocity = (event.clientX - drag.lastX) / (event.timeStamp - drag.lastT);
              drag.lastX = event.clientX;
              drag.lastT = event.timeStamp;
            }
            if (!drag.follow) return;
            sidebar.style.transform = `translateX(${drag.offset}px)`;
            if (drag.dim) drag.dim.currentTime = Math.min(1, -drag.offset / drag.width) * 1000;
          }, true);
          function release(event) {
            if (!drag || event.pointerId !== drag.id) return;
            const ended = drag;
            drag = null;
            if (!ended.moving) return;
            const travelled = -ended.offset / ended.width;
            const close = event.type === "pointerup"
              && (travelled > 1 / 3 || (ended.velocity < -0.5 && travelled > 0.05));
            sidebar.classList.remove("is-dragging");
            sidebar.style.removeProperty("transform");
            settleDim(ended.dim, close ? 0 : 1);
            swallowNextClick();
            if (close) closeOverlaySidebar();
          }
          document.addEventListener("pointerup", release, true);
          document.addEventListener("pointercancel", release, true);
        })();

        const consensusDropdown = document.getElementById("consensusModelDropdown");

        // Mapping: Response-Box → zugehörige Sidebar-Checkbox
        function getCheckboxForResponse(responseId) {
          const pref = (window.App.modelPrefs || [])
            .find(item => item.responseId === responseId);
          return pref ? document.getElementById(pref.checkId) : null;
        }

        // Settings- und Help-Controls werden ausschliesslich von app-ui.js
        // gebunden, Feedback von feedback-dialog.js. Zwei Binder fuehrten
        // jeden Klick und globale Backdrop-Listener doppelt aus.

        // Toggle FAQ items with icons. The question becomes a real button
        // inside its heading (APG accordion), so the keyboard reaches it.
        // Most answers are a single paragraph; richer answers (such as model
        // insights) use the same direct-child contract via .faq-answer.
        document.querySelectorAll('.faq-item h3').forEach((heading, index) => {
          const answer = heading.nextElementSibling;
          const question = document.createElement('button');
          question.type = 'button';
          question.className = 'faq-question';
          question.setAttribute('aria-expanded', 'false');
          if (answer) {
            if (!answer.id) answer.id = `faqAnswer${index + 1}`;
            question.setAttribute('aria-controls', answer.id);
          }
          question.append(...heading.childNodes);
          heading.append(question);
          question.querySelector('.faq-toggle-icon')?.setAttribute('aria-hidden', 'true');
          question.addEventListener('click', () => {
            const icon = question.querySelector('.faq-toggle-icon');
            if (!answer || !icon) return;
            const shouldOpen = !answer.style.display || answer.style.display === 'none';
            answer.style.display = shouldOpen ? 'block' : 'none';
            icon.textContent = shouldOpen ? '−' : '+';
            question.setAttribute('aria-expanded', String(shouldOpen));
          });
        });

        document.querySelectorAll('.faq-item > p, .faq-item > .faq-answer').forEach((answer) => {
          answer.style.display = 'none';
        });

        const APP_LIMITS = window.APP_LIMITS || {};
        function validateInputText() {
          const text = document.getElementById("questionInput").value.trim();
          // Agent counts characters, as its server does: a pasted answer to
          // check easily passes the word limit, and the token account (not
          // the word count) meters what a message costs.
          if (window.App?.runMode?.effective?.() === "agent") {
            const maxChars = Number(APP_LIMITS.consensus_max_question_chars || 8000);
            const message = window.App.quote?.compose?.(text) ?? text;
            // Counted like the server: code points after NFKC (an emoji is one
            // character, "…" becomes three).
            const length = [...String(message).normalize("NFKC").trim()].length;
            // Said under the field it is about, not in a browser window
            // (Apple audit E1); typing again takes it away.
            if (length > maxChars) {
              window.App.composerNotice.show(`Your message is longer than ${window.App.format.number(maxChars)} characters `
                + `(it has ${window.App.format.number(length)}). `
                + "Shorten it, or paste only the part you want checked.");
              return false;
            }
            return true;
          }
          const wordCount = text.split(/\s+/).filter(word => word.length > 0).length;
          // Das Wortlimit hat pro Stufe einen eigenen Admin-Wert und haengt
          // nicht vom Reasoning-Schalter ab (wie serverseitig get_word_limit).
          const tier = window.userTier || "free";
          const maxWordsRaw = APP_LIMITS[`${tier}_max_words`];
          const maxWords = Number(maxWordsRaw || 0);

          if (wordCount > maxWords) {
            window.App.composerNotice.show(`The query is above the limit of ${maxWords} words (you entered ${wordCount}).`);
            return false;
          }
          return true;
        }
        // Von query-send.js (window.sendQuestion) genutzt: der Senden-Klick
        // (app-dom-events.js) und Enter pruefen dort genau einmal. Ein
        // eigener Klick-Listener hier zeigte jede Absage doppelt.
        window.validateInputText = validateInputText;

        // Event-Listener für Eingabefelder und Buttons
        // Mit Tastatur sendet Enter, Shift+Enter macht einen Absatz; auf einem
        // Touch-Geraet bleibt Enter die Absatz-Taste, und ein Enter, das ein
        // Wort einer Eingabemethode bestaetigt, gehoert dem Wort
        // (App.enterSends, app-core.js; Apple-Audit E7, E8).
        document.getElementById("questionInput").addEventListener("keydown", function (event) {
          if (event.key === "Enter" && !event.shiftKey) {
            if (!window.App.enterSends(event)) {
              return;
            }
            if (window.isRunActive && window.isRunActive()) {
              event.preventDefault();
              return;
            }
            if (window.isQueryRequestRunning && window.isQueryRequestRunning()) {
              event.preventDefault();
              return;
            }
            // Wenn der Button deaktiviert ist, breche die Ausführung ab
            if (document.getElementById("sendButton").disabled) {
              event.preventDefault();
              return;
            }
            event.preventDefault();
            window.sendQuestion();
          }
        });

        // Es gibt genau EINEN sichtbaren Sidebar-Toggle: der schwebende
        // (.app-nav-float) bei geschlossener Sidebar, der im Sidebar-Kopf bei
        // offener. Beide teilen sich diesen Handler.
        document.querySelectorAll(".sidebar-toggle").forEach(function (button) {
          button.addEventListener("click", handleSidebarToggle);
        });

        function handleSidebarToggle() {
          const sidebar = document.querySelector(".sidebar");
          if (!sidebar) return;

          if (usesOverlaySidebar()) {
            const shouldOpen = !sidebar.classList.contains("active");
            sidebar.classList.toggle("active", shouldOpen);
            sidebar.classList.toggle("collapsed", !shouldOpen);
          } else {
            sidebar.classList.toggle("collapsed");
            sidebar.classList.remove("active");
            writeStored(
              SIDEBAR_COLLAPSED_STORAGE_KEY,
              String(sidebar.classList.contains("collapsed"))
            );
          }
          updateToggleButton();
        }

        // "New comparison" detaches the main view from the selected run. Any
        // background run keeps its private context and remains reachable from
        // the sidebar; only logout tears down the complete registry.
        document.getElementById("newRunButton")?.addEventListener("click", function () {
          if (document.getElementById("watchDashboard")?.hidden === false) {
            document.getElementById("viewSwitchConsensus")?.click();
          }
          window.clearResponseBoxes?.({ silent: true });
          window.clearPreparedBookmarkShareResult?.();
          window.App.state.set("currentEvidenceSources", [], "evidence");
          window.App.state.set("consensusCitationMeta", null, "consensus");

          const input = document.getElementById("questionInput");
          if (input) {
            input.value = "";
            input.disabled = false;
            input.dispatchEvent(new Event("input", { bubbles: true }));
          }
          const enterHero = () => {
            document.body.classList.add("is-hero");
            window.syncHeroResponseAccess?.();
          };
          if (window.App?.glideComposer) window.App.glideComposer(enterHero);
          else enterHero();
          window.App?.setAppTitle?.();
          window.App?.setThreadQuestion?.("");

          if (usesOverlaySidebar()) closeOverlaySidebar();
          input?.focus();
          trackAppEvent("app_new_comparison");
        });

        // Fenstergröße prüfen – im Overlay-Modus (<=1099px) Sidebar einklappen.
        // Nur ein Wechsel zwischen Overlay und Push setzt die Sidebar zurück:
        // Resizes innerhalb eines Modus (Handy-Tastatur mit
        // interactive-widget=resizes-content, einklappende Browserleiste)
        // schlossen sonst die offene Sidebar, während man in ihrer Suche tippt.
        let sidebarOverlayMode = null;
        function checkWindowSize() {
          const sidebar = document.querySelector(".sidebar");
          syncThreadComposerReserve();
          if (!sidebar) return;
          const overlay = usesOverlaySidebar();
          if (overlay === sidebarOverlayMode) return;
          sidebarOverlayMode = overlay;

          if (overlay) {
            sidebar.classList.add("collapsed");
            sidebar.classList.remove("active");
          } else {
            setSidebarCollapsedInstantly(sidebar, prefersCollapsedSidebar());
            sidebar.classList.remove("active");
          }
          updateToggleButton();
        }
        window.addEventListener("resize", checkWindowSize);
        checkWindowSize(); // Initial

        // Anmelden oeffnet, Abmelden schliesst die Sidebar - nur ohne eigene
        // Wahl und nur neben dem Inhalt; das Overlay bleibt zu.
        window.addEventListener("consensio:auth-state", function () {
          const sidebar = document.querySelector(".sidebar");
          if (!sidebar || usesOverlaySidebar()) return;
          setSidebarCollapsedInstantly(sidebar, prefersCollapsedSidebar());
          updateToggleButton();
        });

        // Fixed navigation should make room while a result is being read. The
        // main app scrolls the window, whereas the Watch dashboard owns an
        // independent scroll container, so both sources feed the same small
        // direction-aware controller. A little accumulated travel prevents
        // touchpad jitter from flickering the controls on and off.
        function initReadingChrome() {
          const body = document.body;
          const consensusOutput = document.getElementById("consensusOutput");
          const watchPage = document.getElementById("watchDashboard");
          const topRevealDistance = 64;
          const directionTravel = 14;
          const mainState = { lastY: window.scrollY, direction: 0, travel: 0, frame: 0 };
          const watchState = { lastY: watchPage?.scrollTop || 0, direction: 0, travel: 0, frame: 0 };

          function watchIsOpen() {
            return Boolean(watchPage && !watchPage.hidden);
          }

          function consensusIsReadable() {
            return Boolean(
              !watchIsOpen()
              && consensusOutput
              && !consensusOutput.classList.contains("is-hidden")
              // Agent chats hide the Consensus output with CSS while an older
              // answer may still sit in it; hidden text is not being read.
              && !document.body.classList.contains("single-agent-active")
              && consensusOutput.getClientRects().length > 0
              && document.getElementById("consensusAnswerBody")?.textContent?.trim()
            );
          }

          // The Watch page scrolls the window as well (components-watch.css).
          function canAutoHide(source) {
            return source === watchPage ? watchIsOpen() : watchIsOpen() || consensusIsReadable();
          }

          function setChromeHidden(hidden) {
            body.classList.toggle("is-reading-chrome-hidden", Boolean(hidden));
          }

          function resetState(state, y) {
            state.lastY = y;
            state.direction = 0;
            state.travel = 0;
          }

          function readScrollY(source) {
            return source === watchPage ? source.scrollTop : window.scrollY;
          }

          function handleScroll(source, state) {
            if (state.frame) return;
            state.frame = requestAnimationFrame(() => {
              state.frame = 0;
              const y = readScrollY(source);
              const delta = y - state.lastY;
              state.lastY = y;

              if (!canAutoHide(source) || y <= topRevealDistance) {
                state.direction = 0;
                state.travel = 0;
                setChromeHidden(false);
                return;
              }
              if (Math.abs(delta) < 0.5) return;

              const nextDirection = delta > 0 ? 1 : -1;
              if (nextDirection !== state.direction) {
                state.direction = nextDirection;
                state.travel = 0;
              }
              state.travel += Math.abs(delta);
              if (state.travel < directionTravel) return;

              setChromeHidden(nextDirection > 0);
              state.travel = 0;
            });
          }

          function revealAndResync() {
            setChromeHidden(false);
            resetState(mainState, window.scrollY);
            resetState(watchState, watchPage?.scrollTop || 0);
          }

          window.addEventListener("scroll", () => handleScroll(window, mainState), { passive: true });
          watchPage?.addEventListener("scroll", () => handleScroll(watchPage, watchState), { passive: true });

          // Hidden controls never trap keyboard users: starting keyboard
          // navigation reveals them before focus advances.
          document.addEventListener("keydown", event => {
            if (!body.classList.contains("is-reading-chrome-hidden")) return;
            if (["Tab", "Home", "PageUp", "ArrowUp"].includes(event.key)) {
              revealAndResync();
            }
          }, true);
          document.querySelector(".app-nav-float")?.addEventListener("focusin", revealAndResync);
          document.querySelector(".app-mobile-header")?.addEventListener("focusin", revealAndResync);
          document.getElementById("viewSwitch")?.addEventListener("focusin", revealAndResync);

          // Opening/closing Watches, clearing a result, or returning to the
          // hero can happen without a scroll event. Keep the chrome state in
          // sync with those view transitions as well.
          const syncEligibility = () => {
            if (!watchIsOpen() && !consensusIsReadable()) revealAndResync();
            else {
              resetState(mainState, window.scrollY);
              resetState(watchState, watchPage?.scrollTop || 0);
            }
          };
          const observer = new MutationObserver(syncEligibility);
          observer.observe(body, { attributes: true, attributeFilter: ["class"] });
          if (consensusOutput) {
            observer.observe(consensusOutput, { attributes: true, attributeFilter: ["class"] });
          }
          if (watchPage) {
            observer.observe(watchPage, { attributes: true, attributeFilter: ["hidden"] });
          }
        }

        initReadingChrome();

        // Aktualisiert den Pfeil des Sidebar-Toggle-Buttons
        function updateToggleButton() {
          const sidebar = document.querySelector(".sidebar");
          if (!sidebar) return;
          const isOpen = usesOverlaySidebar()
            ? sidebar.classList.contains("active")
            : !sidebar.classList.contains("collapsed");
          if (!isOpen && sidebar.contains(document.activeElement)) {
            document.getElementById("toggleSidebarButton")?.focus();
          }
          sidebar.inert = !isOpen;
          if (isOpen) {
            sidebar.removeAttribute("aria-hidden");
          } else {
            sidebar.setAttribute("aria-hidden", "true");
          }
          syncDrawerFocus(sidebar, isOpen && usesOverlaySidebar());
          document.querySelectorAll(".sidebar-toggle").forEach(function (toggleButton) {
            toggleButton.setAttribute("aria-expanded", String(isOpen));
            toggleButton.setAttribute("aria-label", isOpen ? "Collapse sidebar" : "Open sidebar");
            toggleButton.title = isOpen ? "Collapse sidebar" : "Open sidebar";
          });
          const newText = sidebar.classList.contains("collapsed") ? "►" : "◄";
          const arrow = document.querySelector(".sidebar-toggle .arrow");
          if (arrow) {
            arrow.textContent = newText;
          }
        }

        // Funktion, um das Popup anzuzeigen
        // showPopup stammt aus app-core.js (window.App), siehe Alias oben.

        // Quellenverzeichnis unter der Antwort. Die hochgestellten Zahlen im
        // Konsenstext zeigen hierher, deshalb ist die Reihenfolge dieser Liste
        // der Vertrag: Die explizite Quellen-ID bleibt auch bei Lücken erhalten.
        // Das Panel selbst bleibt zu, bis der
        // Quellen-Chip in der Fusszeile es oeffnet.
        function renderEvidenceSources(sources) {
          const panel = document.getElementById("consensusSourcesPanel");
          const listEl = document.getElementById("consensusSourcesList");
          if (!panel || !listEl) return;

          listEl.innerHTML = "";

          if (!sources || !sources.length) {
            panel.hidden = true;
            window.App?.consensusFooter?.render?.();
            return;
          }

          const hasExplicitIds = sources.some(src => /^S[1-9]\d*$/i.test(String(src.id || '')));
          sources.forEach((src, idx) => {
            const explicitId = String(src.id || '').match(/^S([1-9]\d*)$/i);
            const number = explicitId ? Number(explicitId[1]) : hasExplicitIds ? null : idx + 1;
            const li = document.createElement("li");
            li.className = "consensus-source-item";
            if (number !== null) { li.dataset.sourceId = 'S' + number; li.value = number; }

            const index = document.createElement("span");
            index.className = "consensus-source-index";
            index.textContent = number === null ? '—' : String(number);
            li.appendChild(index);

            const body = document.createElement("div");
            body.className = "consensus-source-body";

            const url = String(src.url || "");
            let safeHref = "";
            let host = "";
            try {
              const parsed = new URL(url);
              if (["http:", "https:"].includes(parsed.protocol)) {
                safeHref = parsed.href;
                host = parsed.hostname.replace(/^www\./, "");
              }
            } catch (e) {
              // Ohne gueltige URL bleibt der Titel als reiner Text stehen.
            }

            const title = safeHref ? document.createElement("a") : document.createElement("span");
            title.className = "consensus-source-title";
            title.textContent = src.title || url || "Source " + number;
            if (safeHref) {
              title.href = safeHref;
              title.target = "_blank";
              title.rel = "noopener noreferrer";
            }
            body.appendChild(title);

            if (host) {
              const meta = document.createElement("span");
              meta.className = "consensus-source-host";
              meta.textContent = host;
              body.appendChild(meta);
            }

            if (src.snippet || src.text) {
              const snippet = document.createElement("div");
              snippet.className = "consensus-source-snippet";
              snippet.textContent = src.snippet || src.text;
              body.appendChild(snippet);
            }

            li.appendChild(body);
            listEl.appendChild(li);
          });

          // Sichtbar wird das Panel erst ueber den Chip; hier zaehlt nur, dass
          // es Inhalt hat, damit der Chip erscheinen kann.
          window.App?.consensusFooter?.render?.();
        }

        // global machen, falls du es anderswo brauchst
        window.renderEvidenceSources = renderEvidenceSources;


        // Models remains one compact sidebar row. Its detailed controls open
        // on the composer's existing run picker instead of expanding the
        // navigation into a six-row settings panel.
        document.querySelectorAll("#sidebarModelPicker, #composerModelPicker").forEach(trigger => {
          trigger.addEventListener("click", function (event) {
            event.preventDefault();
            event.stopPropagation();
            if (!window.auth?.currentUser) {
              window.App.askToLogIn("Log in to choose your models.", { trigger, source: "models" });
              return;
            }
            // Kein Choice-State mehr, den die Modellwahl stoeren koennte: eine
            // Folgefrage ist der Default, und die Modelle duerfen dabei jederzeit
            // gewechselt werden (der naechste Lauf nutzt die neue Auswahl).
            const consensusSelect = document.getElementById("consensusModelDropdown");
            if (!consensusSelect) return;

            const openPicker = () => {
              window.App.openModelPicker(consensusSelect);
              consensusSelect._customModelPicker?.displayButton?.focus({ preventScroll: true });
            };

            const source = trigger.id === "sidebarModelPicker" ? "sidebar" : "composer_toolbar";
            if (source === "sidebar" && usesOverlaySidebar()) {
              closeOverlaySidebar();
              window.setTimeout(openPicker, 180);
            } else {
              openPicker();
            }
            trackAppEvent("app_model_picker_opened", { source });
          });
        });

        // Exclude/Include einer Antwort-Box
        // ➜ steuert jetzt auch die Sidebar-Checkboxen / modelSelectionArea mit
        window.toggleExclude = function (responseId) {
          const box = document.getElementById(responseId);
          if (!box) return;

          const checkbox = getCheckboxForResponse(responseId);

          // Fallback: falls aus irgendeinem Grund keine Checkbox gefunden wird,
          // verhalte dich wie früher (nur .excluded toggeln).
          if (!checkbox) {
            if (!box.classList.contains("excluded")) {
              showPopup("You have excluded this answer. It is minimized, and its model is left out of your next run.");
            }
            box.classList.toggle("excluded");
            return;
          }

          const currentlyChecked = checkbox.checked;
          const willBeChecked = !currentlyChecked;

          if (currentlyChecked && !box.classList.contains("excluded")) {
            showPopup("You have excluded this answer. It is minimized, and its model is left out of your next run.");
          }

          checkbox.checked = willBeChecked;

          window.toggleModel(responseId, willBeChecked);
        };

        // --- MODEL PREFERENCES WIEDERHERSTELLUNG ---
        // setPickerToValue, applyTierDefaultModels, getModelPrefByResponseId,
        // animateResponseReorder, setModelSelectionState und restoreModelSelections
        // sind nach static/js/model-picker.js ausgelagert. Aliase siehe oben.

        // View classes: static/js/agent-mode.js (window.setAgentModeStatus,
        // window.updateAgentModeUI). Mode choice: App.runMode
        // (static/js/run-mode.js).

        // 1. Initialer Aufruf beim Laden der Seite
        window.restoreModelSelections();
        updateAgentModeUI();

        window.addEventListener("pageshow", function () {
          window.restoreModelSelections();
          updateAgentModeUI();
        });

        // 2. Event Listener zum Speichern hinzufügen (bleibt gleich)
        modelPrefs.forEach(pref => {
          const checkbox = document.getElementById(pref.checkId);
          const select = document.getElementById(pref.selectId);
          const labelText = document.getElementById(pref.textId);

          if (checkbox) {
            checkbox.addEventListener("change", function () {
              setModelSelectionState(pref, this.checked, { persist: true, syncCheckbox: false });
            });
          }

          if (select) {
            select.addEventListener("change", function () {
              // Speichert die Wahl dieser Familie (beim Verlassen eines
              // Presets die ganze Aufstellung).
              window.App.markConsensusPresetCustom({ family: pref });
              const selectedLabel = getModelOptionLabel(this.options[this.selectedIndex]) || this.value;
              if (labelText) {
                labelText.textContent = selectedLabel;
                labelText.title = `Choose model: ${selectedLabel}`;
              }
              trackAppEvent("app_model_picker_changed", {
                provider: pref.key,
                model: selectedLabel
              });
              updateAgentModeUI();
              if (window.App.runRegistry?.visible?.()) {
                window.App.runRegistry.renderVisible();
              }
              window.App.attachments?.refreshCompatibility?.();
            });
          }
        });



        // A search without a match says so in one quiet line (Apple audit
        // H11); an empty list of a new account stays empty on purpose.
        window.filterBookmarks = function (query) {
          const shown = String(query || "").trim();
          const q = shown.toLowerCase();
          const container = document.getElementById("bookmarksContainer");
          let matches = 0;
          // The name and the question it was asked as: a generated name
          // rarely has the words a person remembers.
          const questions = new Map((window.bookmarksData || []).map(meta => [meta?.id, meta?.query || ""]));
          document.querySelectorAll("#bookmarksContainer .bookmark").forEach(el => {
            const text = `${el.querySelector("p")?.textContent || ""}\n${questions.get(el.dataset.id) || ""}`.toLowerCase();
            const match = !q || text.includes(q);
            el.style.display = match ? "" : "none";
            if (match && !el.classList.contains("is-undo-pending")) matches += 1;
          });
          let empty = document.getElementById("bookmarksSearchEmpty");
          if (q && !matches && container) {
            if (!empty) {
              empty = document.createElement("p");
              empty.id = "bookmarksSearchEmpty";
              empty.className = "bookmarks-search-empty";
              empty.setAttribute("role", "status");
            }
            empty.textContent = `No chats match “${shown}”`;
            if (empty.parentElement !== container) container.prepend(empty);
            empty.hidden = false;
          } else if (empty) {
            empty.hidden = true;
          }
        };

        const bookmarkSearchHead = document.querySelector(".sidebar-bookmarks-head");
        const bookmarkSearchTrigger = document.getElementById("bookmarkSearchTrigger");
        const bookmarkSearchInput = document.getElementById("chatSearch");

        function setBookmarkSearchOpen(isOpen, { focus = false, clear = false } = {}) {
          if (!bookmarkSearchHead || !bookmarkSearchTrigger || !bookmarkSearchInput) return;
          if (clear) {
            bookmarkSearchInput.value = "";
            window.filterBookmarks("");
          }
          bookmarkSearchHead.classList.toggle("is-searching", isOpen);
          bookmarkSearchTrigger.setAttribute("aria-expanded", String(isOpen));
          if (isOpen && focus) requestAnimationFrame(() => bookmarkSearchInput.focus());
        }

        bookmarkSearchTrigger?.addEventListener("click", function (event) {
          event.stopPropagation();
          setBookmarkSearchOpen(true, { focus: true });
        });

        // Ctrl+K (Cmd+K on a Mac) finds a chat from anywhere, as in other chat
        // apps: a closed sidebar opens, a folded list unfolds, and the
        // search field takes the keys.
        const searchShortcut = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent || "") ? "Cmd+K" : "Ctrl+K";
        bookmarkSearchTrigger?.setAttribute("data-tooltip", `Search chats (${searchShortcut})`);
        bookmarkSearchTrigger?.setAttribute("aria-keyshortcuts", "Control+K Meta+K");
        document.addEventListener("keydown", function (event) {
          if (String(event.key).toLowerCase() !== "k" || !(event.ctrlKey || event.metaKey)) return;
          if (event.altKey || event.shiftKey || event.isComposing || event.defaultPrevented) return;
          if (!bookmarkSearchInput || bookmarkSearchInput.disabled || document.querySelector("dialog[open]")) return;
          event.preventDefault();
          const sidebar = document.querySelector(".sidebar");
          const sidebarOpen = usesOverlaySidebar()
            ? sidebar?.classList.contains("active")
            : !sidebar?.classList.contains("collapsed");
          if (sidebar && !sidebarOpen) handleSidebarToggle();
          if (document.querySelector(".bookmarks-section")?.classList.contains("is-collapsed")) window.toggleBookmarks?.();
          setBookmarkSearchOpen(true, { focus: true });
        });

        // Search operates on compact metadata only. When needed, remaining
        // metadata pages are fetched without loading full bookmark answers.
        // The filter reads the field after the await: typing on while the
        // pages load must not leave the list filtered by an older term.
        bookmarkSearchInput?.addEventListener("input", async function () {
          if (this.value.trim()) await window.loadAllBookmarkMetadata?.();
          window.filterBookmarks(this.value);
        });

        bookmarkSearchInput?.addEventListener("keydown", function (event) {
          if (event.key !== "Escape") return;
          event.preventDefault();
          setBookmarkSearchOpen(false, { clear: true });
          document.getElementById("bookmarksToggle")?.focus();
        });

        bookmarkSearchHead?.addEventListener("focusout", function () {
          setTimeout(() => {
            if (!bookmarkSearchHead.contains(document.activeElement) && !bookmarkSearchInput?.value.trim()) {
              setBookmarkSearchOpen(false);
            }
          }, 0);
        });

        window.toggleBookmarks = function () {
          const section = document.querySelector(".bookmarks-section");
          const container = document.getElementById("bookmarksContainer");
          const toggle = document.getElementById("bookmarksToggle");
          if (!section || !container || !toggle) return;

          const isCollapsed = section.classList.toggle("is-collapsed");
          container.classList.toggle("hidden", isCollapsed);
          toggle.setAttribute("aria-expanded", String(!isCollapsed));
          if (isCollapsed) setBookmarkSearchOpen(false, { clear: true });
          writeStored("bookmarks_collapsed", String(isCollapsed));
        };

        function restoreBookmarksState() {
          const section = document.querySelector(".bookmarks-section");
          const container = document.getElementById("bookmarksContainer");
          const toggle = document.getElementById("bookmarksToggle");
          if (!section || !container || !toggle) return;

          const isCollapsed = readStored("bookmarks_collapsed") === "true";
          section.classList.toggle("is-collapsed", isCollapsed);
          container.classList.toggle("hidden", isCollapsed);
          toggle.setAttribute("aria-expanded", String(!isCollapsed));
        }

        restoreBookmarksState();

        // Custom-Model-Picker (eigene Listbox ueber den nativen <select>) ist
        // nach static/js/model-picker.js ausgelagert: getModelPickerState,
        // syncCustomModelPicker, renderCustomModelPicker, openModelPicker,
        // collapseExpandedModelPicker, initCustomModelPicker (+ modul-privater
        // expandedModelPicker-State). Aliase siehe oben.

        modelPrefs.forEach(pref => {
          const labelText = document.getElementById(pref.textId);
          const select = document.getElementById(pref.selectId);
          if (!labelText || !select) return;

          labelText.classList.add("model-name-trigger");
          labelText.setAttribute("role", "button");
          labelText.setAttribute("tabindex", "0");
          labelText.setAttribute("aria-haspopup", "listbox");
          labelText.setAttribute("aria-controls", pref.selectId);
          labelText.title = `Choose model: ${labelText.textContent}`;

          labelText.addEventListener("click", function (event) {
            event.stopPropagation();
            openModelPicker(select);
          });

          labelText.addEventListener("keydown", function (event) {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              openModelPicker(select);
            }
          });

          select.addEventListener("change", function () {
            collapseExpandedModelPicker(select);
          });

          select.addEventListener("keydown", function (event) {
            if (event.key === "Escape") {
              collapseExpandedModelPicker(select);
              labelText.focus({ preventScroll: true });
            }
          });

          initCustomModelPicker(select, { externalTrigger: labelText });
        });

        initCustomModelPicker(document.getElementById("consensusModelDropdown"), { presets: true });



        // Query-Send (window.sendQuestion, Cancel, Query-Run-State und die
        // Query-Helfer isDemoQuery/predictSearchIntent/getActiveMode) ist nach
        // static/js/query-send.js ausgelagert. Die Send-Listener unten fragen
        // window.isQueryRequestRunning() statt das private Flag zu lesen.

        // Modelle (Checkboxen) ein-/ausschalten
        window.toggleModel = function (responseId, isChecked) {
          setModelSelectionState(responseId, isChecked, { persist: true, syncCheckbox: true });
        };
        (window.App.modelPrefs || []).forEach(pref => {
          document.getElementById(pref.checkId)?.addEventListener("change", function () {
            toggleModel(pref.responseId, this.checked);
          });
        });

        // Modell-Dropdowns aktualisieren die angezeigten Namen und Tooltips
        function syncVisibleModelName(select, textId) {
          const el = document.getElementById(textId);
          if (!el || !select) return;
          const label = getModelOptionLabel(select.options[select.selectedIndex]) || select.value;
          el.textContent = label;
          el.title = `Choose model: ${label}`;
        }

        (window.App.modelPrefs || []).forEach(pref => {
          document.getElementById(pref.selectId)?.addEventListener("change", function () {
            syncVisibleModelName(this, pref.textId);
          });
        });

        // collapse model dropdown after selection to avoid lingering focus
        document.querySelectorAll('.model-picker').forEach(function (sel) {
          sel.addEventListener('change', function () {
            this.blur();
          });
        });

        // Erneut API Keys in Felder schreiben (falls benötigt)
        ["openrouterKey"].forEach(function (key) {
          const stored = readStored(key);
          if (stored) {
            document.getElementById(key).value = stored;
          }
        });

        // Globale Variable, um die letzte verarbeitete Frage zu speichern;
        // query-send.js (window.sendQuestion) und run-view.js schreiben sie.
        window.App.state.set("lastQuestion", "", "run");

        // Inline-Status statt Browser-alert() fuer den API-Key-Test.
        function setApiKeysStatus(message, tone) {
          const el = document.getElementById("apiKeysStatus");
          if (!el) return;
          if (!message) {
            el.hidden = true;
            el.textContent = "";
            el.classList.remove("is-error", "is-success");
            return;
          }
          el.hidden = false;
          el.textContent = message;
          el.classList.toggle("is-error", tone === "error");
          el.classList.toggle("is-success", tone === "success");
        }

        // The verdict beside the key's label (Apple-Audit H12): a check in the
        // agreement colour for a valid key, a cross in the dispute colour for
        // one OpenRouter refused, nothing while unknown. Never a star.
        function showKeyVerdict(valid) {
          const feedback = document.getElementById("openrouterFeedback");
          if (!feedback) return;
          feedback.classList.toggle("is-valid", valid === true);
          feedback.classList.toggle("is-invalid", valid === false);
          if (valid === null || valid === undefined) {
            feedback.replaceChildren();
            feedback.removeAttribute("role");
            feedback.removeAttribute("aria-label");
            return;
          }
          const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
          svg.setAttribute("viewBox", "0 0 16 16");
          svg.setAttribute("aria-hidden", "true");
          const path = document.createElementNS(svg.namespaceURI, "path");
          path.setAttribute("d", valid ? "M3.5 8.5l3 3 6-7" : "M4.5 4.5l7 7M11.5 4.5l-7 7");
          svg.append(path);
          feedback.replaceChildren(svg);
          feedback.setAttribute("role", "img");
          feedback.setAttribute("aria-label", valid ? "Key verified" : "Key not accepted");
        }

        // Testet die API Keys und aktualisiert das Feedback
        window.testAllKeys = async function () {
          trackAppEvent("app_api_keys_test_started");
          setApiKeysStatus("");
          const currentUser = window.auth?.currentUser;
          if (!currentUser || !currentUser.emailVerified) {
            setApiKeysStatus("Log in with a confirmed account to save or test your own API key.", "error");
            trackAppEvent("app_api_keys_test_result", { status: "auth_required" });
            return;
          }

          const openrouterKey = document.getElementById("openrouterKey").value;
          if (!openrouterKey.trim()) {
            setApiKeysStatus("Enter an OpenRouter API key to test it.", "error");
            trackAppEvent("app_api_keys_test_result", { status: "no_keys" });
            return;
          }

          let idToken = "";
          try {
            idToken = await currentUser.getIdToken();
          } catch (error) {
            setApiKeysStatus("Your session couldn’t be verified. Log in again.", "error");
            trackAppEvent("app_api_keys_test_result", { status: "auth_error" });
            return;
          }

          writeStored("openrouterKey", openrouterKey);
          if (typeof window.updateQuestionInputAccess === "function") {
            window.updateQuestionInputAccess();
          }
          const spinner = document.getElementById("apiSpinner");
          spinner.style.display = "inline-block";
          try {
            const response = await fetch("/check_keys", {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
                "Authorization": "Bearer " + idToken
              },
              body: JSON.stringify({
                id_token: idToken,
                openrouter_key: openrouterKey
              })
            });
            const data = await window.App.readJson(response);
            if (!response.ok) throw window.App.httpError(response, data);
            if (!data || !data.results) throw Object.assign(new Error(""), { unreadable: true });
            const valid = data.results["OpenRouter"] === "valid";
            showKeyVerdict(valid);
            trackAppEvent("app_api_keys_test_result", { status: "success", valid_count: valid ? 1 : 0 });
            setApiKeysStatus(
              valid ? "Key saved and verified." : "Key saved, but OpenRouter didn’t accept it. Check the key and try again.",
              valid ? "success" : "error"
            );
          } catch (error) {
            console.error("Error while testing API keys:", error);
            trackAppEvent("app_api_keys_test_result", { status: "error" });
            showKeyVerdict(null);
            setApiKeysStatus("The key couldn’t be tested. " + window.App.userError(error, { fallback: "Try again." }), "error");
          } finally {
            spinner.style.display = "none";
          }
        };

        window.clearResponseBoxes = function (options = {}) {
          window.App.answerReader?.reset?.();
          if (!options.silent) trackAppEvent("app_responses_cleared");
          if (options.keepRunSelection !== true) {
            window.App.runRegistry?.clearVisible?.();
          }
          document.body.classList.remove("direct-comparison-active");
          const boxIds = (window.App.modelPrefs || []).map(pref => pref.responseId);

          // Eine gespeicherte Consensus-Antwort samt Verlauf verlaesst den Schirm.
          window.hideConsensusOutput?.();
          window.App.consensusFooter?.clear?.();
          window.App.followup?.reset?.();
          window.App.followup?.clearHistory?.();
          window.App.bookmarkSession?.reset?.();

          // Lösche den Inhalt aller Modell-Antwortboxen.
          boxIds.forEach(id => {
            const box = document.getElementById(id);
            if (box) {
              delete box.dataset.consensusAnswer;
              delete box.dataset.consensusSources;
              const contentEl = box.querySelector(".collapsible-content");
              if (contentEl) {
                contentEl.innerHTML = "";
              }
            }
          });

          // Leere den Inhalt der Consensus-Antwortbox.
          const consensusBox = document.getElementById("consensusResponse");
          if (consensusBox) {
            const mainElement = window.App.consensusBodyEl(consensusBox);
            if (mainElement) {
              mainElement.innerHTML = "";
            }

            const diffElement = consensusBox.querySelector(".consensus-differences p");
            if (diffElement) {
              diffElement.innerHTML = "";
            }
            if (window.resetCredibilityFrame) {
              window.resetCredibilityFrame(consensusBox.querySelector(".consensus-differences"));
            }
          }

          // Leere den Inhalt der Input-Box mit der ID "questionInput".
          const inputBox = document.getElementById("questionInput");
          if (inputBox) {
            inputBox.value = "";
            inputBox.dispatchEvent(new Event("input", { bubbles: true }));
            window.syncDemoChipState?.();
          }
          // Das Zitat gehoert zu der Antwort, die hier gerade geloescht wird.
          window.App.quote?.clear?.();
          window.App.setAppTitle();
          window.App.setThreadQuestion?.("");
          window.App.state.set("lastQuestion", "", "run");
          window.App.state.set("currentEvidenceSources", [], "evidence");
          window.App.state.set("consensusCitationMeta", null, "consensus");
          window.clearPreparedBookmarkShareResult?.();

          setAgentModeStatus("idle");
          window.App.syncSendButtonRunning?.();
        }

        // getActiveMode lebt jetzt in static/js/query-send.js (einziger Aufrufer war sendQuestion).

        let countdownUtcDay = null;
        let usageRefreshUtcDay = null;
        let usageRefreshTargetUtcDay = null;
        let usageRefreshInFlight = null;
        let usageRefreshRetryAt = 0;
        const usageRefreshRetryMs = Math.max(
          25,
          Number(window.USAGE_REFRESH_RETRY_MS) || 5000
        );

        function utcDayKey(date) {
          return `${date.getUTCFullYear()}-${date.getUTCMonth()}-${date.getUTCDate()}`;
        }

        function maybeRefreshUsageForUtcDay(currentUtcDay, nowMs) {
          if (usageRefreshTargetUtcDay !== currentUtcDay
              || usageRefreshUtcDay === currentUtcDay
              || usageRefreshInFlight
              || nowMs < usageRefreshRetryAt) return;
          usageRefreshRetryAt = nowMs + usageRefreshRetryMs;
          const attempt = Promise.resolve().then(() => window.refreshUsageData?.());
          usageRefreshInFlight = attempt;
          attempt.then(refreshed => {
            if (refreshed === true && usageRefreshTargetUtcDay === currentUtcDay) {
              usageRefreshUtcDay = currentUtcDay;
            }
          }).catch(() => {
            // Keep the target pending; the countdown tick retries with backoff.
          }).finally(() => {
            if (usageRefreshInFlight === attempt) usageRefreshInFlight = null;
          });
        }

        function updateCountdown() {
          const now = new Date();
          const currentUtcDay = utcDayKey(now);
          if (countdownUtcDay === null) {
            countdownUtcDay = currentUtcDay;
          } else if (currentUtcDay !== countdownUtcDay) {
            countdownUtcDay = currentUtcDay;
            usageRefreshTargetUtcDay = currentUtcDay;
            usageRefreshRetryAt = 0;
          }
          // Mark the day complete only after the authoritative request
          // succeeds. A transient false/rejection remains retryable, so a stale
          // zero cannot block this tab for the rest of the UTC day.
          maybeRefreshUsageForUtcDay(currentUtcDay, now.getTime());

          const resetTime = new Date(Date.UTC(
            now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + 1
          ));
          const diff = Math.max(0, resetTime - now);

          // Stunden und Minuten bis zum Reset. Der Zaehler ist unsichtbar
          // (#usageOptions) und weckt ueber den MutationObserver in
          // sidebar-quota.js das Kontingent-Panel, dessen "in 3 h 12 min"
          // er damit frisch haelt. Jede Sekunde neu geschrieben, zog er das
          // Panel auch beim Scrollen und Streamen jede Sekunde nach (Apple-
          // Audit D10); einmal pro Minute reicht dem Panel.
          const totalMinutes = Math.floor(diff / (1000 * 60));
          const formattedHours = Math.floor(totalMinutes / 60).toString().padStart(2, "0");
          const formattedMinutes = (totalMinutes % 60).toString().padStart(2, "0");
          const text = "Resets in: " + formattedHours + ":" + formattedMinutes;

          const countdown = document.getElementById('countdownDisplay');
          if (countdown && countdown.textContent !== window.App.t(text)) countdown.textContent = text;
        }

        // Countdown sofort starten und jede Sekunde aktualisieren - nur bei
        // sichtbarem Tab. Ein versteckter Tab tickt nicht; beim Zurueckkehren
        // rechnet der erste Tick sofort nach (auch einen UTC-Tageswechsel).
        let countdownTimer = null;
        function syncCountdownTimer() {
          if (document.hidden) {
            clearInterval(countdownTimer);
            countdownTimer = null;
            return;
          }
          updateCountdown();
          if (countdownTimer === null) countdownTimer = setInterval(updateCountdown, 1000);
        }
        document.addEventListener("visibilitychange", syncCountdownTimer);
        syncCountdownTimer();

        document.getElementById("logoLink").addEventListener("click", () => {
          trackAppEvent("app_logo_home_click");
          // wenn ich wirklich zurück will, entferne den visitedLanding-Flag
          writeStored("visitedLanding", null);
          // und damit gilt beim nächsten Laden der Landing-Seite wieder first-view
        });

        // Demo-Chip automatisch beim ersten echten Besuch (wenn noch nie benutzt)
        if (!readStored("marketingPopupShown") || !readStored("demoChipDismissed")) {
          createStartDemoChip();
        }

        // Consensus-Actions (Copy/Citation/Share controls) sind nach
        // static/js/consensus-actions.js ausgelagert.

        // === Share-Dialog (öffentliche Links) ===
        // Views: "confirm" (Opt-in vor dem Teilen), "success" (Link erstellt),
        // "list" (eigene Links verwalten/widerrufen).

        // Share-Dialog (oeffentliche Links) ist nach static/js/share-dialog.js
        // ausgelagert. Export: window.openShareDialog.

        // Initialer Aufruf: Alles sperren (Standard)
        updatePremiumModelsState(false);

        window.App.state.set("userTier", "free", "userTier");
        window.App.state.set("isUserPro", false, "userTier");
        window.App.state.set("isUserPlus", false, "userTier");

        // Tier-/Pro-UI (updateUserTierUI, updatePremiumModelsState) ist nach
        // static/js/user-tier.js ausgelagert. Exporte gleichen Namens auf window.

        // The one tooltip of the app (tooltip.js): title and data-tooltip, for
        // the pointer, the keyboard and a tap on a mark (Apple audit E12).
        window.App.tooltip?.init?.();

        }

        if (document.readyState === "loading") {
          document.addEventListener("DOMContentLoaded", initApp);
        } else {
          initApp();
        }
      })();
