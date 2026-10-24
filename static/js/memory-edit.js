/** Explicit ask/add/correct actions for selected question and answer text. */
(function () {
  "use strict";

  const state = {
    selection: null,
    intent: "correct",
    busy: false,
    toast: null,
    requestId: null,
    requestFeedback: null,
    returnFocus: null,
    // Account the selection/dialog belongs to ({uid, generation}); the Undo
    // toast keeps its own binding because it outlives the dialog.
    binding: null,
    undoBinding: null,
    // Bumped on every account change; a response from an older epoch is
    // dropped instead of reloading or toasting in the next account's UI.
    epoch: 0,
    controller: null
  };
  const user = () => window.auth?.currentUser?.uid ? window.auth.currentUser : null;

  function authGeneration() {
    const generation = window.App?.authState?.generation;
    return Number.isInteger(generation) ? generation : null;
  }

  function currentBinding() {
    const current = user();
    return current ? { uid: current.uid, generation: authGeneration() } : null;
  }

  // Same rule as auth-session-state.js: the uid must match AND no identity
  // change may have happened in between. A token refresh of the same account
  // changes neither, so it keeps working.
  function bindingIsCurrent(binding) {
    if (!binding) return false;
    if (user()?.uid !== binding.uid) return false;
    const generation = authGeneration();
    return binding.generation === null || generation === null || generation === binding.generation;
  }

  function staleError() {
    const error = new Error("Authentication changed.");
    error.stale = true;
    return error;
  }
  const icons = {
    ask: '<svg aria-hidden="true" viewBox="0 0 24 24"><path d="M9.25 7.5h9M9.25 12h9M9.25 16.5h5.5"/><path d="M5.25 6.5v11"/></svg>',
    remember: '<svg aria-hidden="true" viewBox="0 0 24 24"><path d="M12 3.75a6.25 6.25 0 0 0-3.87 11.16L7.5 19.75l4.5-2.5 4.5 2.5-.63-4.84A6.25 6.25 0 0 0 12 3.75Z"/><path d="M9.5 10.5h5M12 8v5"/></svg>',
    correct: '<svg aria-hidden="true" viewBox="0 0 24 24"><path d="m14.75 5.25 4 4L9.5 18.5l-4.75.75.75-4.75 9.25-9.25Z"/><path d="m12.75 7.25 4 4"/></svg>',
    close: '<svg aria-hidden="true" viewBox="0 0 24 24"><path d="m7 7 10 10M17 7 7 17"/></svg>',
    check: '<svg aria-hidden="true" viewBox="0 0 24 24"><path d="m5.5 12.5 4 4 9-9"/></svg>'
  };

  function sourceForNode(node) {
    const el = node?.nodeType === Node.ELEMENT_NODE ? node : node?.parentElement;
    if (el?.closest("#consensusAnswerBody, #agentAnswerBody, .thread-history-answer")) return "consensus";
    if (el?.closest(".response-box .collapsible-content, .answer-reader-body")) return "model_answer";
    if (el?.closest(".thread-ask-text, .thread-history-question")) return "question";
    return null;
  }

  function sourceLabel(selection) {
    if (selection?.kind === "consensus") return "Answer";
    if (selection?.kind === "model_answer") return "Model answer";
    return "Your question";
  }

  // Zitieren geht nur, was eine Antwort GESAGT hat. Die eigene Frage noch
  // einmal zu zitieren, um sie zu fragen, waere ein Kreis.
  function canAskAbout(selection) {
    if (!window.App?.quote || !document.getElementById("questionInput")) return false;
    return selection?.kind === "consensus" || selection?.kind === "model_answer";
  }

  function askAboutSelection() {
    if (!state.selection || !canAskAbout(state.selection)) return;
    hideMenu();
    window.getSelection?.()?.removeAllRanges?.();
    if (state.selection.reader) window.App?.answerReader?.close({ focus: false });
    window.App.quote.set(state.selection.text);
    window.App.quote.focusComposer();
    window.App?.trackAppEvent?.("app_quote_asked", { source: state.selection.kind });
  }

  function ensureUi() {
    if (document.getElementById("memorySelectionMenu")) return;
    const menu = document.createElement("div");
    menu.id = "memorySelectionMenu";
    menu.className = "memory-selection-menu";
    menu.hidden = true;
    menu.setAttribute("role", "toolbar");
    menu.setAttribute("aria-label", "Actions for selected text");
    // Zuerst die Frage, dann das Gedaechtnis: nach einer Antwort ist
    // "nachfragen" der haeufigere Griff, und er braucht kein Konto.
    menu.innerHTML = `
      <button type="button" class="memory-selection-action" data-selection-group="ask" data-selection-action="ask">
        ${icons.ask}<span>Ask about this</span>
      </button>
      <span class="memory-selection-divider" data-selection-group="between" aria-hidden="true"></span>
      <button type="button" class="memory-selection-action" data-selection-group="memory" data-memory-intent="add">
        ${icons.remember}<span>Remember</span>
      </button>
      <span class="memory-selection-divider" data-selection-group="memory" aria-hidden="true"></span>
      <button type="button" class="memory-selection-action" data-selection-group="memory" data-memory-intent="correct">
        ${icons.correct}<span>Correct memory</span>
      </button>`;

    const backdrop = document.createElement("div");
    backdrop.id = "memoryEditBackdrop";
    backdrop.className = "memory-edit-backdrop";
    backdrop.hidden = true;
    backdrop.innerHTML = `
      <section class="memory-edit-dialog" role="dialog" aria-modal="true" aria-labelledby="memoryEditTitle" aria-describedby="memoryEditDescription">
        <header class="memory-edit-dialog-head">
          <span class="memory-edit-title-icon" id="memoryEditTitleIcon" aria-hidden="true"></span>
          <div>
            <h2 id="memoryEditTitle"></h2>
            <p id="memoryEditDescription"></p>
          </div>
          <button type="button" class="memory-edit-close close-button" aria-label="Close">${window.App?.closeIcon?.() || icons.close}</button>
        </header>
        <div class="memory-edit-dialog-body">
          <div class="memory-edit-context">
            <span class="memory-edit-source" id="memoryEditSource"></span>
            <blockquote id="memoryEditSelection"></blockquote>
          </div>
          <div class="memory-edit-field-head">
            <label for="memoryEditCorrection" id="memoryEditLabel"></label>
            <span id="memoryEditCount" aria-hidden="true">0 / 500</span>
          </div>
          <textarea id="memoryEditCorrection" rows="4" maxlength="500" aria-describedby="memoryEditHelper memoryEditStatus"></textarea>
          <p class="memory-edit-helper" id="memoryEditHelper"></p>
          <p class="memory-edit-status" id="memoryEditStatus" role="status" aria-live="polite"></p>
        </div>
        <footer class="memory-edit-dialog-actions">
          <button type="button" class="memory-edit-cancel">Cancel</button>
          <button type="button" class="memory-edit-submit"><span class="memory-edit-submit-label"></span></button>
        </footer>
      </section>`;

    // The confirmation with its Undo is the app's one notice line
    // (App.toast, notices.js), not a toast of its own.
    document.body.append(menu, backdrop);
    document.addEventListener("close", event => {
      if (event.target.contains?.(menu)) hideMenu();
    }, true);
    menu.querySelector("[data-selection-action='ask']")
      ?.addEventListener("click", askAboutSelection);
    menu.querySelectorAll("[data-memory-intent]").forEach(button => {
      button.addEventListener("click", () => openDialog(button.dataset.memoryIntent, button));
    });
    backdrop.querySelector(".memory-edit-close").addEventListener("click", closeDialog);
    backdrop.querySelector(".memory-edit-cancel").addEventListener("click", closeDialog);
    backdrop.querySelector(".memory-edit-submit").addEventListener("click", submitEdit);
    backdrop.addEventListener("click", event => {
      if (event.target === backdrop) closeDialog();
    });
    const textarea = backdrop.querySelector("textarea");
    textarea.addEventListener("input", updateCounter);
    textarea.addEventListener("keydown", event => {
      if ((event.ctrlKey || event.metaKey) && event.key === "Enter" && !window.App?.isComposingKey?.(event)) submitEdit();
    });
    backdrop.addEventListener("keydown", handleDialogKeys);
  }

  function makeRequestId() {
    return window.crypto?.randomUUID?.()
      || `edit-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  function hideMenu() {
    const menu = document.getElementById("memorySelectionMenu");
    if (menu) menu.hidden = true;
  }

  // Where a finger selected, the system's own menu (Copy, Look Up …) sits
  // over the selection and its handles hang below the last line. Ours goes
  // under the handle there, never under the system menu; with a mouse it
  // stays right below the selection.
  const TOUCH_HANDLE_PX = 28;
  const SYSTEM_MENU_PX = 56;

  function showSelection(text, kind, rect, sourceNode = null, { touch = lastPointer === "touch" || lastPointer === "pen" } = {}) {
    if (!text || text.length > 2000 || !rect) return hideMenu();
    const sourceElement = sourceNode?.nodeType === Node.ELEMENT_NODE ? sourceNode : sourceNode?.parentElement;
    const readerDialog = sourceElement?.closest('.answer-reader-dialog[open]');
    const selection = { text, kind, reader: !!readerDialog };
    // Zitieren braucht kein Konto, Memory schon. Bleibt nichts uebrig, bleibt
    // auch das Menue weg — ein Balken mit einem ausgegrauten Rest ist keine
    // Auswahl, sondern eine Werbeflaeche.
    const askable = canAskAbout(selection);
    const rememberable = !!user();
    if (!askable && !rememberable) return hideMenu();
    state.selection = selection;
    state.binding = currentBinding();
    const menu = document.getElementById("memorySelectionMenu");
    // A modal native reader makes body siblings inert. Keep the toolbar in
    // its dialog until an action returns to the composer or the Memory dialog.
    const menuHost = readerDialog || document.body;
    if (menu.parentElement !== menuHost) menuHost.appendChild(menu);
    menu.querySelectorAll("[data-selection-group]").forEach(node => {
      const group = node.dataset.selectionGroup;
      node.hidden = group === "ask" ? !askable
        : group === "memory" ? !rememberable
        : !(askable && rememberable);
    });
    menu.hidden = false;
    menu.style.visibility = "hidden";
    requestAnimationFrame(() => {
      const menuWidth = menu.offsetWidth;
      const menuHeight = menu.offsetHeight;
      const center = rect.left + (rect.width / 2);
      const left = Math.max(10, Math.min(window.innerWidth - menuWidth - 10, center - (menuWidth / 2)));
      const below = rect.bottom + (touch ? TOUCH_HANDLE_PX : 10);
      const top = below + menuHeight <= window.innerHeight - 10
        ? below
        : Math.max(10, rect.top - menuHeight - (touch ? SYSTEM_MENU_PX : 10));
      menu.style.left = `${left}px`;
      menu.style.top = `${top}px`;
      menu.style.visibility = "visible";
    });
  }

  function captureSelection(event, { touch = lastPointer === "touch" || lastPointer === "pen" } = {}) {
    if (state.busy || !document.getElementById("memoryEditBackdrop")?.hidden) return;
    if (event?.target?.closest?.(".memory-selection-menu, .toast-region")) return;
    const input = event?.target?.closest?.("#questionInput");
    if (input && input.selectionStart !== input.selectionEnd) {
      return showSelection(
        input.value.slice(input.selectionStart, input.selectionEnd).trim(),
        "question",
        input.getBoundingClientRect()
      );
    }
    const selection = window.getSelection();
    const text = selection?.toString().trim() || "";
    if (!text || selection.rangeCount !== 1) return hideMenu();
    const range = selection.getRangeAt(0);
    const kind = sourceForNode(range.commonAncestorContainer);
    if (!kind) return hideMenu();
    showSelection(text, kind, range.getBoundingClientRect(), range.commonAncestorContainer, { touch });
  }

  // A finger selects without a mouseup (Apple audit F7): on a phone "Ask
  // about this", "Remember" and "Correct memory" never appeared. After a
  // touch the selection itself is watched: while the handles move the menu
  // waits, once the selection has stood still for a moment it shows; a
  // selection that is gone takes the menu with it (unless the finger is on
  // the menu, whose tap ends the selection).
  const SELECTION_SETTLE_MS = 350;
  let lastPointer = "";
  let selectionTimer = 0;

  function onSelectionChange() {
    if (lastPointer !== "touch" && lastPointer !== "pen") return;
    clearTimeout(selectionTimer);
    const menu = document.getElementById("memorySelectionMenu");
    if (menu && !menu.hidden && window.getSelection()?.toString().trim()) menu.style.visibility = "hidden";
    selectionTimer = setTimeout(() => {
      if (document.activeElement?.closest?.(".memory-selection-menu")) return;
      const text = window.getSelection()?.toString().trim();
      if (!text) { hideMenu(); return; }
      captureSelection(null, { touch: true });
    }, SELECTION_SETTLE_MS);
  }

  function dialogCopy(intent) {
    if (intent === "add") {
      return {
        title: "Remember this",
        description: "Save a lasting fact or preference and keep related Memory consistent.",
        label: "What should consens.io remember?",
        helper: "consens.io adds it, or updates the one saved passage it clearly matches. Nothing else changes.",
        placeholder: "For example: I live in Hanover.",
        submit: "Save to Memory",
        busy: "Saving…",
        progress: "Looking for a related saved passage…"
      };
    }
    return {
      title: "Correct memory",
      description: "Update one outdated or incorrect passage in your Memory.",
      label: "What should consens.io remember instead?",
      helper: "consens.io changes the one passage it matches. If none does, your correction is added as a new one.",
      placeholder: "For example: I now work in Hanover.",
      submit: "Update Memory",
      busy: "Updating…",
      progress: "Looking for the matching passage…"
    };
  }

  function openDialog(intent, trigger) {
    hideMenu();
    if (!state.selection || !user()) return;
    if (!bindingIsCurrent(state.binding)) return resetForAuthChange();
    state.intent = intent === "add" ? "add" : "correct";
    state.returnFocus = trigger || null;
    if (state.selection.reader) {
      window.App?.answerReader?.close();
      state.returnFocus = document.activeElement;
    }
    const copy = dialogCopy(state.intent);
    const backdrop = document.getElementById("memoryEditBackdrop");
    const textarea = document.getElementById("memoryEditCorrection");
    document.getElementById("memoryEditTitle").textContent = copy.title;
    document.getElementById("memoryEditDescription").textContent = copy.description;
    document.getElementById("memoryEditTitleIcon").innerHTML = state.intent === "add" ? icons.remember : icons.correct;
    document.getElementById("memoryEditLabel").textContent = copy.label;
    document.getElementById("memoryEditHelper").textContent = copy.helper;
    document.getElementById("memoryEditSource").textContent = sourceLabel(state.selection);
    document.getElementById("memoryEditSelection").textContent = state.selection.text.slice(0, 360) + (state.selection.text.length > 360 ? "…" : "");
    document.querySelector(".memory-edit-submit-label").textContent = copy.submit;
    textarea.placeholder = copy.placeholder;
    textarea.value = state.intent === "add" ? state.selection.text.slice(0, 500) : "";
    textarea.removeAttribute("aria-invalid");
    document.getElementById("memoryEditStatus").textContent = "";
    state.requestId = makeRequestId();
    state.requestFeedback = textarea.value.trim();
    backdrop.hidden = false;
    updateCounter();
    requestAnimationFrame(() => {
      textarea.focus();
      textarea.setSelectionRange(textarea.value.length, textarea.value.length);
    });
  }

  function closeDialog() {
    if (state.busy) return;
    document.getElementById("memoryEditBackdrop").hidden = true;
    state.returnFocus?.focus?.();
  }

  function handleDialogKeys(event) {
    if (event.key === "Escape") {
      event.preventDefault();
      closeDialog();
      return;
    }
    if (event.key !== "Tab") return;
    const controls = [...event.currentTarget.querySelectorAll("button:not(:disabled), textarea:not(:disabled)")];
    if (!controls.length) return;
    const first = controls[0];
    const last = controls[controls.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  function updateCounter() {
    const textarea = document.getElementById("memoryEditCorrection");
    const count = textarea?.value?.length || 0;
    const counter = document.getElementById("memoryEditCount");
    if (counter) {
      counter.textContent = `${count} / 500`;
      counter.dataset.near = count >= 400 ? "true" : "false";
    }
    textarea?.removeAttribute("aria-invalid");
    const status = document.getElementById("memoryEditStatus");
    if (status?.dataset.kind === "error") {
      status.textContent = "";
      delete status.dataset.kind;
    }
  }

  function setBusy(busy, message) {
    state.busy = busy;
    const backdrop = document.getElementById("memoryEditBackdrop");
    backdrop.querySelectorAll("button, textarea").forEach(control => { control.disabled = busy; });
    const submit = backdrop.querySelector(".memory-edit-submit");
    submit.classList.toggle("is-busy", busy);
    submit.querySelector("span").textContent = busy ? dialogCopy(state.intent).busy : dialogCopy(state.intent).submit;
    if (message !== undefined) {
      const status = document.getElementById("memoryEditStatus");
      status.textContent = message;
      status.dataset.kind = busy ? "progress" : "";
    }
  }

  function showFieldError(message) {
    const status = document.getElementById("memoryEditStatus");
    const textarea = document.getElementById("memoryEditCorrection");
    status.textContent = message;
    status.dataset.kind = "error";
    textarea.setAttribute("aria-invalid", "true");
    textarea.focus();
  }

  // Every request is bound to the account that made the selection. The token
  // must belong to that account, and the answer is used only while it is
  // still the signed-in account (checked after token, fetch and JSON).
  async function post(path, body, binding) {
    if (!bindingIsCurrent(binding)) throw staleError();
    const authUser = user();
    const token = await authUser.getIdToken();
    if (!bindingIsCurrent(binding)) throw staleError();
    const controller = typeof AbortController === "function" ? new AbortController() : null;
    state.controller = controller;
    let response;
    try {
      response = await fetch(path, {
        method: "POST",
        headers: { "Authorization": `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: controller?.signal
      });
    } catch (error) {
      if (!bindingIsCurrent(binding) || controller?.signal.aborted) throw staleError();
      throw error;
    } finally {
      if (state.controller === controller) state.controller = null;
    }
    const data = await window.App.readJson(response).catch(() => ({}));
    if (!bindingIsCurrent(binding)) throw staleError();
    if (!response.ok) throw window.App.httpError(response, data);
    return data;
  }

  // Logout, login or an account switch (e.g. in another tab) closes the
  // dialog, forgets the selection and its request id, hides the old Undo and
  // abandons any in-flight request. Nothing from account A may reach B.
  function resetForAuthChange() {
    state.epoch += 1;
    state.controller?.abort?.();
    state.controller = null;
    state.selection = null;
    state.binding = null;
    state.undoBinding = null;
    state.requestId = null;
    state.requestFeedback = null;
    hideMenu();
    const backdrop = document.getElementById("memoryEditBackdrop");
    if (backdrop) {
      if (state.busy) setBusy(false, "");
      backdrop.hidden = true;
      const textarea = document.getElementById("memoryEditCorrection");
      if (textarea) textarea.value = "";
      const selection = document.getElementById("memoryEditSelection");
      if (selection) selection.textContent = "";
    }
    state.toast?.cancel();
    state.toast = null;
  }

  function handleAuthState(event) {
    hideMenu();
    const bound = state.binding || state.undoBinding;
    if (!bound) return;
    const uid = event?.detail?.uid || null;
    const generation = Number.isInteger(event?.detail?.generation) ? event.detail.generation : null;
    const same = uid === bound.uid
      && (generation === null || bound.generation === null || generation === bound.generation);
    if (!same) resetForAuthChange();
  }

  // Another worker still holds this request; its result answers a repeat.
  const RETRY_SAME_REQUEST = new Set(["edit_in_progress", "lease_lost"]);

  async function submitEdit() {
    if (state.busy || !state.selection) return;
    const binding = state.binding;
    // Ownership check BEFORE anything leaves the browser: a selection made
    // under account A must never be submitted with account B's token.
    if (!bindingIsCurrent(binding)) return resetForAuthChange();
    const correction = document.getElementById("memoryEditCorrection").value.trim();
    if (!correction) return showFieldError("Enter what consens.io should remember.");
    if (state.requestFeedback !== correction) {
      state.requestId = makeRequestId();
      state.requestFeedback = correction;
    }
    const epoch = state.epoch;
    const intent = state.intent;
    setBusy(true, dialogCopy(intent).progress);
    try {
      const result = await post("/api/my/memory/edit", {
        client_request_id: state.requestId,
        source_kind: state.selection.kind,
        selected_text: state.selection.text,
        correction,
        intent
      }, binding);
      if (epoch !== state.epoch) return;
      if (result.status === "processing") throw new Error("This Memory action is already processing.");
      document.getElementById("memoryEditBackdrop").hidden = true;
      await window.App?.userMemory?.load?.(true, { keepDraft: true });
      if (epoch !== state.epoch || !bindingIsCurrent(binding)) return;
      showUndo(result, intent, binding);
      window.App?.trackAppEvent?.("app_memory_ai_edit", { intent, status: "updated" });
    } catch (error) {
      if (error?.stale || epoch !== state.epoch) {
        if (epoch === state.epoch) resetForAuthChange();
        return;
      }
      // The server's own refusal (it names a code) is final for this id: a
      // repeat would only hear "already failed". Without an answer (network,
      // gateway) the edit may have been applied, so the same id stays.
      if (error?.code && !RETRY_SAME_REQUEST.has(error.code)) {
        state.requestId = null;
        state.requestFeedback = null;
      }
      showFieldError(window.App.userError(error, { fallback: "Memory couldn’t be updated. Try again." }));
    } finally {
      if (epoch === state.epoch) setBusy(false);
    }
  }

  // The way back stays offered while the server keeps the revision, at
  // most ten seconds on screen (hover and focus hold it longer).
  const UNDO_VISIBLE_MS = 10000;
  function showUndo(result, intent, binding) {
    state.undoBinding = binding;
    state.toast?.cancel();
    const expires = Date.parse(result.undo_expires_at || "");
    const left = Number.isFinite(expires) ? Math.max(0, expires - Date.now()) : UNDO_VISIBLE_MS;
    state.toast = window.App?.toast?.({
      message: intent === "add"
        ? (result.operation === "append" ? "Added to Memory" : result.operation === "replace" ? "Memory updated" : "Saved to Memory")
        : "Memory updated",
      tone: "success",
      duration: Math.max(3000, Math.min(left, UNDO_VISIBLE_MS)),
      action: { label: "Undo", onAction: handle => undoEdit(result.revision_id, handle, binding, intent) },
    }) || null;
  }

  async function undoEdit(revisionId, handle, binding, intent) {
    const epoch = state.epoch;
    try {
      await post("/api/my/memory/undo", { revision_id: revisionId }, binding);
      if (epoch !== state.epoch) return;
      await window.App?.userMemory?.load?.(true, { keepDraft: true });
      if (epoch !== state.epoch || !bindingIsCurrent(binding)) return;
      handle.update({ message: "Previous Memory restored", action: null, duration: 2500 });
      window.App?.trackAppEvent?.("app_memory_ai_edit", { intent, status: "undone" });
    } catch (error) {
      if (error?.stale || epoch !== state.epoch) {
        if (epoch === state.epoch) resetForAuthChange();
        return;
      }
      handle.update({ message: window.App.userError(error, { fallback: "Memory couldn’t be restored. Try again." }), tone: "error", action: null, duration: 4000 });
    }
  }

  function bind() {
    ensureUi();
    document.addEventListener("pointerdown", event => {
      if (event.target?.closest?.(".memory-selection-menu")) return;
      lastPointer = event.pointerType || "";
    }, true);
    document.addEventListener("selectionchange", onSelectionChange);
    document.addEventListener("mouseup", event => setTimeout(() => captureSelection(event), 0));
    document.addEventListener("keyup", event => {
      if (event.key === "Shift" || event.shiftKey) captureSelection(event);
    });
    document.addEventListener("scroll", hideMenu, true);
    window.addEventListener("resize", hideMenu);
    window.addEventListener("consensio:auth-state", handleAuthState);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bind);
  else bind();
})();
