// Predicted example questions under an empty new chat (2026-10-16).
//
// The app shell renders three curated questions (a new pick per page load,
// app/services/starter_questions.py) and "Check an AI answer". Once an
// account has a few saved chats, three questions predicted from them take
// the curated ones' place: POST /api/my/starter-questions reads the newest
// chats and suggests what this person may ask next. The prediction is not
// announced; the reader recognises their own topics.
//
// This browser keeps the last prediction per account, so a reload paints it
// from the first frame (app-bootstrap.js calls seed()), and asks again only
// once the newest chats changed: firebase.js calls refresh() after the list
// loaded and after each save. Clicks stay composer-invite.js's
// (data-starter="predicted").
//
// Head bundle, before app-bootstrap.js; requests only at runtime
// (window.auth from firebase.js).
// Exports: window.App.composerStarters
(function () {
  "use strict";
  const App = window.App = window.App || {};

  const CACHE_KEY = "consensio.starterQuestions.v1";
  const ENDPOINT = "/api/my/starter-questions";
  // Same as the server (starter_questions.MIN_HISTORY).
  const MIN_CHATS = 3;
  // The newest chats a prediction was made from, as many as the server reads
  // (starter_questions.HISTORY_SIZE): a new chat, an older one continued to
  // the top or a deleted one asks again.
  const BASIS_SIZE = 12;
  const MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000;
  // A run saves several times in a row; one request after the last.
  const REFRESH_DELAY_MS = 1500;
  const REQUEST_TIMEOUT_MS = 20000;
  const MAX_LABEL = 48;
  const MAX_QUESTION = 400;

  function row() { return document.getElementById("composerStarters"); }

  function questionsOf(value) {
    if (!Array.isArray(value)) return [];
    return value.filter(item => item && typeof item.label === "string" && typeof item.question === "string"
      && item.label.trim() && item.question.trim()
      && item.label.length <= MAX_LABEL && item.question.length <= MAX_QUESTION).slice(0, 3);
  }

  function read() {
    try {
      const record = JSON.parse(window.localStorage.getItem(CACHE_KEY) || "null");
      if (!record || typeof record.uid !== "string" || typeof record.basis !== "string"
        || !Number.isFinite(record.at)) return null;
      const questions = questionsOf(record.questions);
      return questions.length ? Object.assign(record, { questions }) : null;
    } catch (_) { return null; }
  }

  function write(record) {
    try {
      if (record) window.localStorage.setItem(CACHE_KEY, JSON.stringify(record));
      else window.localStorage.removeItem(CACHE_KEY);
    } catch (_) { /* private mode: this page still shows it */ }
  }

  function fresh(record) {
    return Boolean(record) && Date.now() - record.at < MAX_AGE_MS;
  }

  // The account a stored ID token names, before Firebase restored the
  // session. Only to match the stored prediction to its account.
  function tokenUid(token) {
    try {
      const part = String(token || "").split(".")[1] || "";
      const payload = JSON.parse(window.atob(part.replace(/-/g, "+").replace(/_/g, "/")));
      const uid = payload.user_id || payload.sub;
      return typeof uid === "string" && uid ? uid : null;
    } catch (_) { return null; }
  }

  // ---- The row ---------------------------------------------------------------
  // Predicted buttons go before "Check an AI answer"; the curated ones stay
  // in the document, hidden, and come back when the prediction goes.
  function render(target, questions, { animate = false } = {}) {
    if (!target) return;
    const items = questionsOf(questions);
    const shown = [...target.querySelectorAll('[data-starter="predicted"]')];
    const same = shown.length === items.length
      && shown.every((button, index) => button.dataset.question === items[index].question
        && button.textContent === items[index].label);
    if (same) return;
    shown.forEach(button => button.remove());
    target.querySelectorAll(".composer-starter").forEach(button => {
      if (button.dataset.starter !== "check") button.hidden = items.length > 0;
    });
    const check = target.querySelector('[data-starter="check"]');
    const quiet = !animate || window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
    items.forEach(item => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "composer-starter";
      button.dataset.starter = "predicted";
      button.dataset.question = item.question;
      button.textContent = item.label;
      target.insertBefore(button, check);
      if (!quiet && button.animate) button.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 260, easing: "ease-out" });
    });
  }

  // Never swap the buttons under the pointer or the keyboard: the new set
  // waits until the reader leaves the row.
  let waiting = null;
  function show(questions) {
    const target = row();
    if (!target) return;
    const busy = target.matches?.(":hover") || target.contains(document.activeElement);
    if (!busy) { waiting = null; render(target, questions, { animate: true }); return; }
    const first = waiting === null;
    waiting = { questions };
    if (!first) return;
    const settle = event => {
      if (event.type === "focusout" && target.contains(event.relatedTarget)) return;
      target.removeEventListener("pointerleave", settle);
      target.removeEventListener("focusout", settle);
      const next = waiting;
      waiting = null;
      if (next) show(next.questions);
    };
    target.addEventListener("pointerleave", settle);
    target.addEventListener("focusout", settle);
  }

  // First paint (app-bootstrap.js): this account's stored prediction.
  function seed(target) {
    let token = null;
    try { token = window.localStorage.getItem("id_token"); } catch (_) { /* storage unavailable */ }
    const authState = window.__consensioAuthState;
    const uid = authState?.known ? authState.uid : tokenUid(token);
    const record = read();
    if (uid && record?.uid === uid && fresh(record)) render(target, record.questions);
  }

  // ---- Asking ----------------------------------------------------------------
  let timer = null;
  let asking = null; // {uid, basis} while a request runs

  function refresh() {
    clearTimeout(timer);
    timer = setTimeout(run, REFRESH_DELAY_MS);
  }

  async function run() {
    timer = null;
    const user = window.auth?.currentUser;
    if (!user) return;
    const chats = (window.bookmarksData || []).filter(item => item && item.id);
    const record = read();
    const own = record?.uid === user.uid ? record : null;
    if (chats.length < MIN_CHATS) {
      // Too few chats to read anything from, or the reader deleted them.
      if (own) write(null);
      show(null);
      return;
    }
    const basis = chats.slice(0, BASIS_SIZE).map(item => item.id).join(",");
    if (own && fresh(own)) show(own.questions);
    if (own && own.basis === basis && fresh(own)) return;
    if (asking && asking.uid === user.uid && asking.basis === basis) return;
    const mine = asking = { uid: user.uid, basis };
    const controller = typeof AbortController === "function" ? new AbortController() : null;
    const deadline = controller ? setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS) : null;
    try {
      const token = await user.getIdToken();
      const response = await fetch(ENDPOINT, {
        method: "POST",
        headers: { "Authorization": "Bearer " + token },
        cache: "no-store",
        signal: controller ? controller.signal : undefined,
      });
      const data = await response.json().catch(() => null);
      if (window.auth?.currentUser?.uid !== mine.uid) return;
      const questions = response.ok ? questionsOf(data?.questions) : [];
      // Nothing new (a limit, a failed call): the last prediction stays.
      if (!questions.length) return;
      write({ uid: mine.uid, basis, at: Date.now(), questions });
      show(questions);
    } catch (_) {
      /* offline or slow: the row keeps what it shows */
    } finally {
      clearTimeout(deadline);
      if (asking === mine) asking = null;
    }
  }

  // Signed out, or another account: its topics leave the row and the browser.
  function clear() {
    clearTimeout(timer);
    timer = null;
    asking = null;
    write(null);
    show(null);
  }

  window.addEventListener("consensio:auth-state", event => {
    const uid = event.detail?.uid || null;
    const record = read();
    if (!uid) { if (record) clear(); else show(null); return; }
    if (record && record.uid !== uid) clear();
  });

  App.composerStarters = Object.freeze({ seed, refresh, clear });
})();
