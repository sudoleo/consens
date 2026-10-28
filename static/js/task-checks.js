// =====================================================================
// task-checks.js
// Ticks in the checklists of an answer ("- [ ] item"; markdown-stream.js
// draws the boxes). A box can be ticked in the answer of a saved turn: the
// element that answer is written into names its turn (App.taskChecks.scope)
// and the ticks are kept on that turn (PUT /chats/{chat}/turns/{turn}/
// task-checks), so a chat shows the same ticks on every device. Every other
// box (one model's answer, an answer that is still being written) stands as
// the text wrote it and cannot be ticked.
//
// A turn the reader never ticked shows the boxes as written ("[x]" ticked);
// once ticked, the turn's list of ticked boxes (their order in the answer)
// decides. Ticks made on this page win over turn data loaded before them:
// a re-render from the saved chat never takes a tick back.
// Exporte: App.taskChecks.scope, .apply, .flush.
// Call-time-Abhaengigkeiten: window.auth, App.runRegistry.
// =====================================================================
(function () {
  "use strict";
  const App = window.App = window.App || {};
  const MAX_ITEMS = 200;
  const SAVE_DELAY_MS = 600;
  const RETRY_DELAYS_MS = [2000, 8000];
  // turnId -> { chatId, checked: Set | null, touched, dirty, timer, inflight, attempt }
  const turns = new Map();

  function cleanList(value) {
    return [...new Set(value.filter(index => Number.isInteger(index) && index >= 0 && index < MAX_ITEMS))];
  }

  // The boxes of the answer written into `el`, in order; boxes of another
  // answer nested in it (an earlier version) are not its own.
  function boxesOf(el) {
    return Array.from(el.querySelectorAll(".md-task-box"))
      .filter(box => box.parentElement.closest("[data-task-turn], .consensus-answer-body") === el);
  }

  function apply(el) {
    const state = turns.get(el?.dataset?.taskTurn || "");
    if (!state) return;
    boxesOf(el).forEach((box, index) => {
      box.disabled = false;
      if (!state.checked) return;
      const wanted = state.checked.has(index) ? "true" : "false";
      if (box.getAttribute("aria-checked") !== wanted) box.setAttribute("aria-checked", wanted);
    });
  }

  // `el` shows the answer of `turnId` (none: its boxes cannot be ticked).
  // `checked` is the turn's saved list; it replaces what this page knows
  // until the reader ticks here.
  function scope(el, { chatId = "", turnId = "", checked } = {}) {
    if (!el) return;
    const turn = String(turnId || "").trim();
    if (!turn) {
      if (!el.dataset.taskTurn) return;
      delete el.dataset.taskTurn;
      delete el.dataset.taskChat;
      el.querySelectorAll(".md-task-box").forEach(box => { box.disabled = true; });
      return;
    }
    el.dataset.taskTurn = turn;
    if (chatId) el.dataset.taskChat = String(chatId);
    else delete el.dataset.taskChat;
    let state = turns.get(turn);
    if (!state) turns.set(turn, state = { chatId: "", checked: null, touched: false, attempt: 0 });
    if (chatId) state.chatId = String(chatId);
    if (!state.touched && Array.isArray(checked)) state.checked = new Set(cleanList(checked));
    if (el.querySelector(".md-task-box")) apply(el);
  }

  // The chat on screen: the run shown, else the saved chat opened.
  function visibleChatId() {
    const registry = App.runRegistry;
    const context = registry?.visible?.();
    return context?.metadata?.chatId || context?.basis?.chatId
      || registry?.getSelectedConversationBasis?.({ includeHistory: false })?.chatId || "";
  }

  function schedule(turnId, delay) {
    const state = turns.get(turnId);
    clearTimeout(state.timer);
    state.timer = setTimeout(() => { state.timer = null; save(turnId); }, delay);
  }

  function save(turnId, keepalive = false) {
    const state = turns.get(turnId);
    const user = window.auth?.currentUser;
    // One request at a time per turn; what changed meanwhile goes next.
    if (!state?.dirty || state.inflight || !user || !state.chatId) return;
    clearTimeout(state.timer);
    state.timer = null;
    state.dirty = false;
    const checked = [...state.checked].sort((a, b) => a - b);
    const url = `/chats/${encodeURIComponent(state.chatId)}/turns/${encodeURIComponent(turnId)}/task-checks`;
    state.inflight = Promise.resolve(user.getIdToken()).then(token => fetch(url, {
      method: "PUT",
      headers: { "Authorization": "Bearer " + token, "Content-Type": "application/json" },
      body: JSON.stringify({ checked }),
      cache: "no-store",
      keepalive,
    })).then(response => {
      // A chat deleted meanwhile, a turn of another chat: nothing to keep.
      if (!response.ok && (response.status === 401 || response.status === 408
          || response.status === 429 || response.status >= 500)) throw new Error("retry");
      state.attempt = 0;
    }).catch(() => {
      if (state.attempt >= RETRY_DELAYS_MS.length) return;
      state.dirty = true;
      schedule(turnId, RETRY_DELAYS_MS[state.attempt++]);
    }).finally(() => {
      state.inflight = null;
      if (state.dirty && !state.timer) schedule(turnId, SAVE_DELAY_MS);
    });
  }

  function flush() {
    turns.forEach((state, turnId) => { if (state.dirty) save(turnId, true); });
  }

  document.addEventListener("click", event => {
    const box = event.target?.closest?.(".md-task-box");
    if (!box || box.disabled) return;
    const el = box.closest("[data-task-turn]");
    const turnId = el?.dataset.taskTurn || "";
    const state = turns.get(turnId);
    const boxes = el ? boxesOf(el) : [];
    const index = boxes.indexOf(box);
    if (!state || index < 0 || index >= MAX_ITEMS) return;
    if (!state.checked) {
      state.checked = new Set(boxes.flatMap((item, at) => item.getAttribute("aria-checked") === "true" ? [at] : []));
    }
    if (state.checked.has(index)) state.checked.delete(index);
    else state.checked.add(index);
    box.setAttribute("aria-checked", state.checked.has(index) ? "true" : "false");
    state.touched = true;
    state.dirty = true;
    // A new tick gets its own retries: after a longer outage had used them
    // up, every later tick of the turn failed once and was dropped unsaved,
    // its box still ticked (2026-10-24).
    state.attempt = 0;
    state.chatId = state.chatId || el.dataset.taskChat || visibleChatId();
    schedule(turnId, SAVE_DELAY_MS);
  });

  // A tick right before the tab goes away still reaches the server.
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") flush();
  });

  App.taskChecks = { scope, apply, flush };
})();
