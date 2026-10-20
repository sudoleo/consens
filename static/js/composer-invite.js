// Inviting the first question (2026-10-15). Three jobs around the composer:
//
// 1. Guests type. Their Send keeps the question (draft, app-init.js) and
//    opens the sign-in; once the new session can run it, the question goes
//    out by itself (afterAccessUpdate, called by updateQuestionInputAccess).
//    Most visitors used to leave in front of a locked field.
// 2. Example questions under an empty new chat (#composerStarters), curated
//    or predicted from the newest chats (composer-starters.js). A click
//    fills the field and never sends: the reader adapts it or sends it.
// 3. Where a sent question came from (typed, example, pasted), for the "ask"
//    event (app-core.js trackAsk). Never the text itself.
(function () {
  "use strict";
  const App = window.App = window.App || {};

  // One sign-in may take a detour through the mailbox; an hour later the
  // question is still in the field, but nothing sends it unasked.
  const PENDING_KEY = "consensio.sendAfterLogin.v1";
  const PENDING_MAX_AGE_MS = 60 * 60 * 1000;
  // A pasted AI answer is long; a pasted question of one line is "typed".
  const PASTE_MIN_CHARS = 200;
  const GUEST_SEND_LEAD = "Your question stays here and runs as soon as you’re logged in.";

  let source = "typed";
  let afterLogin = false;
  let autoSendScheduled = false;

  function field() { return document.getElementById("questionInput"); }
  function track(name, data) { App.trackAppEvent?.(name, data); }
  function readPending() {
    try {
      const pending = JSON.parse(localStorage.getItem(PENDING_KEY) || "null");
      return pending && Number.isFinite(pending.at) ? pending : null;
    } catch (_) { return null; }
  }
  function writePending(value) {
    try {
      if (value) localStorage.setItem(PENDING_KEY, JSON.stringify(value));
      else localStorage.removeItem(PENDING_KEY);
    } catch (_) { /* private mode: the question still waits in the field */ }
  }

  // query-send.js asks first: true means "handled, send nothing".
  function sendAsGuest() {
    if (!App.isGuestComposer?.()) return false;
    const input = field();
    const text = input?.value.trim() || "";
    if (!text) { input?.focus(); return true; }
    App.saveQuestionDraft?.(text);
    // The text itself: only exactly this question goes out by itself later,
    // never one typed (or cut short) after this Send.
    writePending({ at: Date.now(), source, text });
    track("app_guest_send", { source });
    App.openAuthModal?.("register", document.getElementById("sendButton"), "composer", { lead: GUEST_SEND_LEAD });
    return true;
  }

  // What the guest sent is in the field (records from before 2026-10-16 carry
  // no text and only need one).
  function holdsSentText(pending) {
    const text = field()?.value.trim() || "";
    return Boolean(text) && (typeof pending.text !== "string" || text === pending.text.trim());
  }

  function afterAccessUpdate(canStartRun) {
    if (!canStartRun || autoSendScheduled || App.reloadingAfterSignIn) return;
    // A tab in the background only shares the sign-in (an email link opens a
    // new tab that signs in and reloads): the tab in front sends it, once.
    if (document.visibilityState === "hidden") return;
    const pending = readPending();
    if (!pending) return;
    // One try, whatever happens next.
    writePending(null);
    if (Date.now() - pending.at > PENDING_MAX_AGE_MS) return;
    // Only into a new chat: a chat on screen keeps the question in the field.
    const registry = App.runRegistry;
    if (registry?.visible?.() || registry?.getSelectedConversationBasis?.()) return;
    if (!holdsSentText(pending)) return;
    autoSendScheduled = true;
    // Not from inside updateQuestionInputAccess, which sending calls again.
    setTimeout(() => {
      autoSendScheduled = false;
      if (App.reloadingAfterSignIn || !holdsSentText(pending) || !window.userCanAskQuestions?.()) return;
      source = pending.source || "typed";
      afterLogin = true;
      // A send that stopped before its "ask" (a limit, a refusal) must not
      // pass its marks on to the next question.
      Promise.resolve(window.sendQuestion?.()).finally(() => {
        if (!afterLogin) return;
        afterLogin = false;
        source = "typed";
      });
    }, 0);
  }

  // Read once per sent question; the next one starts from "typed" again.
  function takeAskContext() {
    const context = { source };
    if (afterLogin) context.after_login = true;
    source = "typed";
    afterLogin = false;
    return context;
  }

  // The examples step back as soon as the field holds anything, however it
  // got there (draft, quote, Run again): composer.css reads
  // #questionInput:placeholder-shown, so no setter has to tell this module.
  function useStarter(button) {
    const input = field();
    if (!input || input.disabled || !button.dataset.question) return;
    input.value = button.dataset.question;
    source = "example";
    // Autosize, the demo chip, collapse and Send follow the field's input.
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.focus({ preventScroll: true });
    input.setSelectionRange(input.value.length, input.value.length);
    track("app_starter_used", { starter: button.dataset.starter || "", guest: Boolean(App.isGuestComposer?.()) });
  }

  // While the field holds text the note below the examples glides up into
  // their room (composer.css moves .app-footer by --starters-room). The row
  // wraps differently per width and per set (predicted labels are longer),
  // so its height is measured, not assumed; display: none outside the hero
  // measures 0. The room is the row's margin box: on touch the scrolling row
  // pads itself for the 44px hit areas and gives that back with its margins.
  function trackStartersRoom() {
    const row = document.getElementById("composerStarters");
    const section = row?.closest(".input-section");
    if (!row || !section) return;
    const measure = () => {
      const style = getComputedStyle(row);
      const room = row.offsetHeight ? row.offsetHeight + (parseFloat(style.marginTop) || 0) + (parseFloat(style.marginBottom) || 0) : 0;
      section.style.setProperty("--starters-room", room + "px");
    };
    if (typeof ResizeObserver === "function") new ResizeObserver(measure).observe(row);
    else window.addEventListener("resize", measure, { passive: true });
    measure();
  }

  function init() {
    const input = field();
    input?.addEventListener("paste", event => {
      const pasted = event.clipboardData?.getData("text") || "";
      if (pasted.trim().length >= PASTE_MIN_CHARS) source = "pasted";
    });
    input?.addEventListener("input", event => {
      // Emptied by hand: what comes next is typed. Emptied by a send or a new
      // chat (no keystroke): trackAsk still has to read the source.
      if (event.isTrusted && !input.value.trim()) source = "typed";
      // A guest's Send depends on the text; signed in, Agent's own listener
      // (agent-chat.js) and the run gate keep it.
      if (App.isGuestComposer?.()) window.updateQuestionInputAccess?.();
    });
    document.getElementById("composerStarters")?.addEventListener("click", event => {
      const button = event.target.closest?.(".composer-starter");
      if (button) useStarter(button);
    });
    trackStartersRoom();
    // The placeholder has a length per width (App.askPlaceholder); a rotated
    // phone gets the right one. Accounts: agent-chat.js syncComposer.
    for (const query of ["(max-width: 360px)", "(max-width: 640px)"]) {
      window.matchMedia?.(query)?.addEventListener?.("change", () => {
        if (App.isGuestComposer?.()) window.updateQuestionInputAccess?.();
      });
    }
  }

  App.composerInvite = { sendAsGuest, afterAccessUpdate, takeAskContext };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
  else init();
})();
