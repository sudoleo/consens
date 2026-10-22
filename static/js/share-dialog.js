// =====================================================================
// share-dialog.js
// Oeffentliche Share-Links: Bestaetigen, Erfolg, Liste/Revoke. In eigene
// IIFE gekapselt. Extrahiert aus templates/index.html (initApp-Closure).
// Export: window.openShareDialog (firebase.js User-Menue ruft es auf).
// Abhaengigkeiten: window.auth (firebase), window.lastShareResultId,
// window.App.showPopup, window.App.trackAppEvent.
// =====================================================================

(function () {
  let sharedModalEpoch = 0;
  let sharedModalMode = null;
  const activeShareControllers = new Set();

  function invalidateSharedModalRequests() {
    sharedModalEpoch += 1;
    activeShareControllers.forEach(controller => controller.abort());
    activeShareControllers.clear();
    return sharedModalEpoch;
  }

  function beginShareView() {
    sharedModalMode = "share";
    return invalidateSharedModalRequests();
  }

  function shareViewIsCurrent(epoch) {
    const { modal } = shareDialogEls();
    return epoch === sharedModalEpoch
      && sharedModalMode === "share"
      && dialogIsOpen(modal);
  }

  // #shareModal is a native <dialog> opened through App.modalDialog: focus
  // goes in and back, Tab stays inside, Escape closes this layer only (the
  // Watches page beneath keeps what is typed there, Apple-Audit J1), and it
  // fades in and out like every dialog (overlays.css).
  function dialogIsOpen(modal) {
    return Boolean(modal?.open || modal?.hasAttribute?.("open"));
  }

  function settleSharedModalClose() {
    invalidateSharedModalRequests();
    sharedModalMode = null;
  }

  function bindSharedModal(modal) {
    if (!modal || modal.dataset.sharedModalBound === "true") return;
    modal.dataset.sharedModalBound = "true";
    window.App?.modalDialog?.bind(modal, {
      // A watch being set up is not dropped by a click beside it.
      keepOpen: () => modal.classList.contains("is-watch-dialog"),
      onClose: settleSharedModalClose,
    });
  }

  function staleShareRequest() {
    const error = new Error("This view is no longer active.");
    error.stale = true;
    return error;
  }

  function currentAuthSnapshot() {
    const user = window.auth?.currentUser;
    if (!user) throw new Error("Not logged in");
    return {
      user,
      uid: user.uid,
      generation: window.__consensioAuthState?.generation
    };
  }

  function authSnapshotIsCurrent(snapshot) {
    const current = window.auth?.currentUser;
    const currentGeneration = window.__consensioAuthState?.generation;
    return current === snapshot.user
      && current?.uid === snapshot.uid
      && (snapshot.generation == null || currentGeneration === snapshot.generation);
  }

  function shareDialogEls() {
    return {
      modal: document.getElementById("shareModal"),
      body: document.getElementById("shareModalBody"),
      title: document.getElementById("shareModalTitle")
    };
  }

  function sharedModalSnapshot() {
    return Object.freeze({ epoch: sharedModalEpoch, mode: sharedModalMode });
  }

  function sharedModalSnapshotIsCurrent(snapshot) {
    const { modal } = shareDialogEls();
    return !!snapshot
      && snapshot.epoch === sharedModalEpoch
      && snapshot.mode === sharedModalMode
      && dialogIsOpen(modal);
  }

  function setSharedModalOpen(isOpen, mode) {
    const { modal, body } = shareDialogEls();
    if (!modal) return null;
    bindSharedModal(modal);
    if (isOpen) {
      // Every explicit open is a new user intent, including a second Watch or
      // Share open while the same modal mode is already visible.
      invalidateSharedModalRequests();
      sharedModalMode = mode || null;
      // The mode classes stay on after closing: the dialog keeps its shape
      // while it fades out, and the next open sets them again.
      modal.classList.toggle("is-watch-dialog", mode === "watch");
      modal.classList.toggle("is-share-dialog", mode !== "watch");
      if (!dialogIsOpen(modal)) {
        if (window.App?.modalDialog) window.App.modalDialog.open(modal);
        else modal.setAttribute("open", "");
      }
      requestAnimationFrame(() => {
        if (body) body.scrollTop = 0;
      });
      return sharedModalSnapshot();
    }
    if (dialogIsOpen(modal)) {
      if (window.App?.modalDialog) window.App.modalDialog.close(modal);
      else modal.removeAttribute("open");
    }
    // close() settled it already (onClose); a dialog that was not open, or
    // an engine without the helper, still ends every request of the view.
    settleSharedModalClose();
    return sharedModalSnapshot();
  }

  function closeShareDialog() {
    setSharedModalOpen(false);
  }

  // `options.prepare(viewEpoch)` names the answer to share when it is not the
  // one Share/Watch target by default (lastShareResultId or the opened chat
  // entry): a Promise of its pending result ID that rejects with the reason
  // it can't be shared.
  function openShareDialog(view, options = {}) {
    const { modal } = shareDialogEls();
    if (!modal) return;
    if (!window.auth?.currentUser) {
      window.App.askToLogIn("Log in to share this answer.", { source: "share", trigger: options.trigger });
      return;
    }
    setSharedModalOpen(true, "share");
    if (view === "list") {
      renderShareListView();
    } else {
      renderShareConfirmView(options.prepare);
    }
  }

  async function shareApiRequest(method, path, body, viewEpoch) {
    const authSnapshot = currentAuthSnapshot();
    const controller = new AbortController();
    activeShareControllers.add(controller);
    try {
      const idToken = await authSnapshot.user.getIdToken();
      if (!authSnapshotIsCurrent(authSnapshot) || !shareViewIsCurrent(viewEpoch)) {
        throw staleShareRequest();
      }
      const response = await fetch(path, {
        method,
        headers: {
          "Content-Type": "application/json",
          "Authorization": "Bearer " + idToken
        },
        body: body ? JSON.stringify(body) : undefined,
        signal: controller.signal
      });
      if (!authSnapshotIsCurrent(authSnapshot) || !shareViewIsCurrent(viewEpoch)) {
        throw staleShareRequest();
      }
      const data = await window.App.readJson(response).catch(() => ({}));
      if (!authSnapshotIsCurrent(authSnapshot) || !shareViewIsCurrent(viewEpoch)) {
        throw staleShareRequest();
      }
      if (!response.ok) throw window.App.httpError(response, data);
      return data;
    } catch (error) {
      if (error?.name === "AbortError") throw staleShareRequest();
      throw error;
    } finally {
      activeShareControllers.delete(controller);
    }
  }

  function copyShareUrl(url) {
    if (!navigator.clipboard) {
      const ta = document.createElement("textarea");
      ta.value = url;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      window.App.showPopup("Link copied to clipboard.");
      return;
    }
    navigator.clipboard.writeText(url).then(() => {
      window.App.showPopup("Link copied to clipboard.");
    }).catch(() => {
      window.App.toast?.({ message: "Copy to clipboard failed.", tone: "error" });
    });
  }

  // A refusal that another try can change: the network, a busy or failing
  // server. A 4xx names a reason that stays (an unfinished answer, a chat
  // with Google data), so the dialog offers no button that cannot work.
  function retryable(error) {
    const status = Number(error?.status) || 0;
    return !status || status === 408 || status === 429 || status >= 500;
  }

  function renderShareConfirmView(prepare) {
    const viewEpoch = beginShareView();
    const { body, title } = shareDialogEls();
    if (!body) return;
    title.textContent = "Share this answer publicly";
    body.innerHTML = `
      <p>This creates a <strong>public, read-only page</strong> with the question,
      the answer, its differences and its sources.</p>
      <ul class="share-modal-notes">
        <li>Anyone with the link can view it, without an account.</li>
        <li>The page contains no account data and is not linked to you publicly.</li>
        <li>It is a snapshot: later runs will not change it.</li>
        <li>You can revoke the link at any time under "My shared links".</li>
      </ul>
      <div class="share-modal-actions">
        <p id="shareDialogError" class="share-modal-error" role="alert" hidden></p>
        <button type="button" id="shareConfirmBtn" class="share-primary-btn">Create public link</button>
        <button type="button" id="shareCancelBtn" class="share-secondary-btn">Cancel</button>
        <button type="button" id="shareListLink" class="share-link-btn">My shared links</button>
        <button type="button" id="watchListLink" class="share-link-btn">Watches</button>
      </div>
    `;
    document.getElementById("shareCancelBtn").addEventListener("click", closeShareDialog);
    document.getElementById("shareListLink").addEventListener("click", renderShareListView);
    document.getElementById("watchListLink").addEventListener("click", () => window.openWatchDialog?.("list"));
    const confirmBtn = document.getElementById("shareConfirmBtn");
    const errorLine = document.getElementById("shareDialogError");
    // The server's own sentence, in the dialog it belongs to (never a toast
    // that is gone before it is read, never "unavailable" on a dead button).
    function showError(error, fallback) {
      const message = error ? window.App.userError(error, { fallback }) : "";
      errorLine.textContent = message;
      errorLine.hidden = !message;
      confirmBtn.hidden = Boolean(message) && !retryable(error);
      confirmBtn.disabled = false;
      confirmBtn.textContent = message ? "Try again" : "Create public link";
    }
    // The pending result this dialog publishes: the named answer, the run on
    // screen, or the opened chat entry (prepared on the server, firebase.js).
    let pendingId = prepare ? "" : window.lastShareResultId || "";
    async function resolveResultId() {
      if (pendingId) return pendingId;
      if (prepare) {
        pendingId = await prepare(viewEpoch);
        return pendingId;
      }
      const resultId = await window.resolveCurrentShareResultId?.();
      if (resultId) return (pendingId = resultId);
      // The refusal itself (its status says whether a retry can help), else
      // its sentence (firebase.js requestBookmarkShareResult).
      const error = window.currentBookmarkShareResultContext?.error;
      throw error || new Error(window.currentBookmarkShareResultError
        || "This chat couldn’t be prepared for sharing. Try again.");
    }
    async function prepareLink() {
      confirmBtn.disabled = true;
      confirmBtn.textContent = "Preparing link…";
      try {
        await resolveResultId();
        if (!confirmBtn.isConnected || !shareViewIsCurrent(viewEpoch)) return;
        showError(null);
      } catch (error) {
        if (error?.stale || !confirmBtn.isConnected || !shareViewIsCurrent(viewEpoch)) return;
        showError(error, "This answer couldn’t be prepared for sharing. Try again.");
      }
    }
    if (prepare || (!pendingId && window.currentBookmarkShareResultContext)) {
      prepareLink();
    } else if (!pendingId) {
      confirmBtn.disabled = true;
      confirmBtn.textContent = "Run a consensus first";
    }
    confirmBtn.addEventListener("click", async function () {
      if (!pendingId) {
        prepareLink();
        return;
      }
      this.disabled = true;
      this.textContent = "Creating link…";
      errorLine.hidden = true;
      try {
        const data = await shareApiRequest("POST", "/api/share", { result_id: pendingId }, viewEpoch);
        if (!shareViewIsCurrent(viewEpoch)) return;
        window.App.trackAppEvent("app_share_created", { reused: data.created === false });
        renderShareSuccessView(data.url);
      } catch (err) {
        if (err?.stale) return;
        showError(err, "The link couldn’t be created. Try again.");
      }
    });
  }

  function renderShareSuccessView(url) {
    beginShareView();
    const { body, title } = shareDialogEls();
    if (!body) return;
    title.textContent = "Public link created";
    body.innerHTML = `
      <p>Your answer is now public at:</p>
      <div class="share-url-row">
        <input type="text" id="shareUrlInput" readonly>
        <button type="button" id="shareCopyUrlBtn" class="share-primary-btn">Copy</button>
      </div>
      <div class="share-modal-actions">
        <a id="shareOpenLink" target="_blank" rel="noopener" class="share-secondary-btn">Open page</a>
        <button type="button" id="shareListLink" class="share-link-btn">My shared links</button>
        <button type="button" id="watchListLink" class="share-link-btn">Watches</button>
      </div>
    `;
    const input = document.getElementById("shareUrlInput");
    input.value = url;
    input.addEventListener("focus", () => input.select());
    document.getElementById("shareOpenLink").href = url;
    document.getElementById("shareCopyUrlBtn").addEventListener("click", () => copyShareUrl(url));
    document.getElementById("shareListLink").addEventListener("click", renderShareListView);
    document.getElementById("watchListLink").addEventListener("click", () => window.openWatchDialog?.("list"));
  }

  async function renderShareListView() {
    const viewEpoch = beginShareView();
    const { body, title } = shareDialogEls();
    if (!body) return;
    title.textContent = "My shared links";
    body.innerHTML = `<p class="share-list-loading">Loading…</p>`;
    let data;
    try {
      data = await shareApiRequest("GET", "/api/my/shares", undefined, viewEpoch);
    } catch (err) {
      if (err?.stale || !shareViewIsCurrent(viewEpoch)) return;
      body.innerHTML = "";
      const p = document.createElement("p");
      p.textContent = "Your shared links couldn’t be loaded. " + window.App.userError(err, { fallback: "Try again." });
      body.appendChild(p);
      return;
    }

    if (!shareViewIsCurrent(viewEpoch)) return;
    body.innerHTML = "";
    const shares = (data.shares || []).filter(s => s.status === "active");
    if (!shares.length) {
      const p = document.createElement("p");
      p.textContent = "You have no active shared links.";
      body.appendChild(p);
      return;
    }

    const list = document.createElement("ul");
    list.className = "share-list";
    shares.forEach(share => {
      const item = document.createElement("li");
      const url = (data.site_url || "") + share.path;

      const question = document.createElement("a");
      question.className = "share-list-question";
      question.textContent = (share.visibility === "private" ? "Private · " : "") + (share.question || "(untitled)");
      question.href = url;
      question.target = "_blank";
      question.rel = "noopener";

      const actions = document.createElement("div");
      actions.className = "share-list-actions";

      const copyBtn = document.createElement("button");
      copyBtn.type = "button";
      copyBtn.className = "share-secondary-btn";
      copyBtn.textContent = share.visibility === "private" ? "Copy private link" : "Copy link";
      copyBtn.addEventListener("click", () => copyShareUrl(url));

      const revokeBtn = document.createElement("button");
      revokeBtn.type = "button";
      revokeBtn.className = "share-danger-btn";
      revokeBtn.textContent = "Revoke";
      revokeBtn.addEventListener("click", async () => {
        const confirmed = await window.App.confirm({
          title: share.visibility === "private" ? "Revoke this private page?" : "Revoke this public link?",
          body: share.visibility === "private"
            ? "It will no longer be available to you."
            : "Visitors will no longer be able to open it.",
          confirmLabel: "Revoke",
          danger: true,
        });
        if (!confirmed || !shareViewIsCurrent(viewEpoch)) return;
        revokeBtn.disabled = true;
        try {
          await shareApiRequest("DELETE", "/api/share/" + encodeURIComponent(share.share_id), undefined, viewEpoch);
          if (!shareViewIsCurrent(viewEpoch)) return;
          window.App.trackAppEvent("app_share_revoked", {});
          window.App.showPopup("Share link revoked.");
          item.remove();
          if (!list.children.length) renderShareListView();
        } catch (err) {
          if (err?.stale) return;
          revokeBtn.disabled = false;
          window.App.toast?.({ message: window.App.userError(err, { fallback: "The link couldn’t be revoked. Try again." }), tone: "error" });
        }
      });

      actions.appendChild(copyBtn);
      actions.appendChild(revokeBtn);
      item.appendChild(question);
      item.appendChild(actions);
      list.appendChild(item);
    });
    body.appendChild(list);
    if (data.has_more) {
      // The list is bounded; say so instead of implying it is complete.
      const more = document.createElement("p");
      more.className = "share-list-truncated";
      more.textContent = "Showing your most recent shared links. Older links are not listed here.";
      body.appendChild(more);
    }
  }

  // ------------------------------------------------------------------
  // Sharing an Agent answer (since 2026-10-21). The server builds the
  // snapshot from the saved turn (POST /agent/chats/{chat}/turns/{turn}/
  // share-result) under an ID that stays the same for that answer, so a
  // second Share finds the first link. Every finished answer of a chat has
  // its pill, also one higher up in the history.
  // ------------------------------------------------------------------
  const TURN_ID = /^[0-9a-f]{32}$/;
  const preparedAnswers = new Map();

  function prepareAgentAnswer(chatId, turnId) {
    return async viewEpoch => {
      if (!TURN_ID.test(chatId || "") || !TURN_ID.test(turnId || "")) {
        throw new Error("This answer isn’t finished yet. Share it once it is.");
      }
      const key = `${window.auth?.currentUser?.uid || ""}:${chatId}:${turnId}`;
      if (preparedAnswers.has(key)) return preparedAnswers.get(key);
      const path = `/agent/chats/${encodeURIComponent(chatId)}/turns/${encodeURIComponent(turnId)}/share-result`;
      const data = await shareApiRequest("POST", path, undefined, viewEpoch);
      if (!data?.result_id) throw new Error("This answer couldn’t be prepared for sharing. Try again.");
      preparedAnswers.set(key, data.result_id);
      return data.result_id;
    };
  }

  function shareAgentAnswer({ chatId, turnId, trigger } = {}) {
    openShareDialog("confirm", { trigger, prepare: prepareAgentAnswer(chatId, turnId) });
  }

  // The chat of the answers on screen: a history turn knows only its own ID.
  function visibleChatId() {
    const run = window.App.runRegistry?.visible?.();
    return run?.metadata?.chatId
      || window.App.runRegistry?.getSelectedConversationBasis?.({ includeHistory: false })?.chatId || "";
  }

  const SHARE_PILL_ICON = '<svg class="share-pill-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 15V4"></path><path d="M8.5 7.5 12 4l3.5 3.5"></path><path d="M5 12v7a1.5 1.5 0 0 0 1.5 1.5h11A1.5 1.5 0 0 0 19 19v-7"></path></svg>';

  // The pill sits right after the answer's Watch pill (watch.js), in the
  // evidence row (Sources · Answers · Differences) or, without one, in the
  // row of its own under the answer. Call it after App.watch.answerButton.
  function syncAnswerShareButton(answerBody, { chatId = "", turnId = "", eligible = false } = {}) {
    if (!answerBody) return;
    let button = answerBody._sharePill;
    if (!eligible || !turnId) {
      const row = button?.closest(".agent-watch-pill-row");
      button?.remove();
      if (row && !row.children.length) row.remove();
      answerBody._sharePill = null;
      return;
    }
    if (!button) {
      button = document.createElement("button");
      button.type = "button";
      button.className = "consensus-share-pill agent-share-pill";
      button.innerHTML = SHARE_PILL_ICON + "<span>Share</span>";
      button.title = "Share this answer as a public page";
      button.setAttribute("aria-label", "Share this answer publicly");
      button.addEventListener("click", () => shareAgentAnswer({
        chatId: button._chatId || visibleChatId(), turnId: button._turnId, trigger: button
      }));
      answerBody._sharePill = button;
    }
    button._chatId = chatId;
    button._turnId = turnId;
    const review = answerBody._agentReview?.parentNode && answerBody._agentReview.parentNode === answerBody.parentNode
      ? answerBody._agentReview : null;
    const nav = review ? review.querySelector(".agent-evidence-links") : null;
    const watch = answerBody._watchPill;
    const ownRow = button.closest(".agent-watch-pill-row");
    if (nav) {
      const after = watch?.parentNode === nav.parentNode ? watch : nav;
      if (after.nextElementSibling !== button) after.after(button);
      if (ownRow && !ownRow.children.length) ownRow.remove();
      return;
    }
    const watchRow = watch?.closest(".agent-watch-pill-row") || null;
    let row = watchRow || ownRow;
    if (!row) {
      row = document.createElement("div");
      row.className = "agent-watch-pill-row";
    }
    if (row.lastElementChild !== button) row.appendChild(button);
    if (ownRow && ownRow !== row && !ownRow.children.length) ownRow.remove();
    // Also off the page: a history turn is built before it is inserted.
    const after = review || answerBody;
    if (!row.parentNode || (!watchRow && after.nextElementSibling !== row)) after.after(row);
  }

  window.App.answerShare = { open: shareAgentAnswer, button: syncAnswerShareButton };

  // Global verfügbar machen, damit z.B. das User-Icon-Menü (firebase.js)
  // die Übersicht der geteilten Links direkt öffnen kann.
  window.openShareDialog = openShareDialog;
  window.App.sharedModal = {
    open: (mode) => setSharedModalOpen(true, mode),
    close: closeShareDialog,
    snapshot: sharedModalSnapshot,
    isCurrent: sharedModalSnapshotIsCurrent
  };

  (function initShareModal() {
    const modal = document.getElementById("shareModal");
    if (!modal) return;
    bindSharedModal(modal);
    const closeBtn = document.getElementById("closeShareModal");
    if (closeBtn) closeBtn.addEventListener("click", closeShareDialog);
  })();
})();
