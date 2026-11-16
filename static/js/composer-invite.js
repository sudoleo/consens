// Inviting the first question. Three jobs around the composer:
//
// 1. Guests type. Their Send keeps the question (draft, app-init.js) and
//    opens the sign-in; once the new session can run it, the question goes
//    out by itself (afterAccessUpdate, called by updateQuestionInputAccess),
//    in Agent as the guest saw it, or in the mode the guest chose.
//    Most visitors used to leave in front of a locked field.
// 2. Example questions under an empty new chat (#composerStarters), curated
//    or predicted from the newest chats (composer-starters.js). A click
//    fills the field and never sends: the reader adapts it or sends it.
// 3. Where a sent question came from (typed, example, pasted, link), for the
//    "ask" event (app-core.js trackAsk). Never the text itself.
// 4. A question brought by /app#q= (app-bootstrap.js reads it on load) also
//    while the app is open: the browser then changes only the fragment.
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
    // never one typed (or cut short) after this Send. A mode the guest chose
    // in the (+) menu goes with it: the sign-in may bring an
    // account's settings that say otherwise. Unchosen, the account's own
    // mode applies (Agent by default, as the guest saw it). A temporary chat
    // is not a guest's to choose (temporary-chat.js): the switch comes with
    // the account.
    const mode = App.userSettings?.get?.("run_mode");
    writePending({ at: Date.now(), source, text, ...(mode ? { mode } : {}) });
    track("app_guest_send", { source });
    App.openAuthModal?.("register", document.getElementById("sendButton"), "composer", { lead: GUEST_SEND_LEAD });
    return true;
  }

  // What the guest sent is in the field (a record without its text only
  // needs one).
  function holdsSentText(pending) {
    const text = field()?.value.trim() || "";
    return Boolean(text) && (typeof pending.text !== "string" || text === pending.text.trim());
  }

  // The waiting question may still go out: fresh, into a new chat (a chat on
  // screen keeps the question in the field), and the field holds it.
  function sendable(pending) {
    if (Date.now() - pending.at > PENDING_MAX_AGE_MS) return false;
    const registry = App.runRegistry;
    if (registry?.visible?.() || registry?.getSelectedConversationBasis?.()) return false;
    return holdsSentText(pending);
  }

  function afterAccessUpdate(canStartRun) {
    if (autoSendScheduled || App.reloadingAfterSignIn) return;
    // A tab in the background only shares the sign-in (an email link opens a
    // new tab that signs in and reloads): the tab in front sends it, once.
    if (document.visibilityState === "hidden") return;
    const pending = readPending();
    if (!pending) return;
    // The mode the guest chose holds once an account can run the question,
    // before the send waits for that mode to be ready (Agent's model list,
    // two models). set() renders the composer, which asks here again.
    if (pending.mode && window.userCanAskQuestions?.() && App.runMode?.preference?.() !== pending.mode
        && sendable(pending) && App.runMode.set(pending.mode, { source: "guest" })) return;
    if (!canStartRun) return;
    // One try, whatever happens next.
    writePending(null);
    if (!sendable(pending)) return;
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
    if (App.questionLink?.filled) source = "link";
    if (App.questionLink?.opened) {
      // Umami's script loads after this bundle, app-init.js (isGuestComposer) too.
      const count = () => track("app_question_link", { filled: App.questionLink.filled, guest: Boolean(App.isGuestComposer?.()) });
      if (document.readyState === "complete") count();
      else window.addEventListener("load", count, { once: true });
    }
    window.addEventListener("hashchange", questionFromLink);
  }

  // The same link while the app is open: the address bar's keyword typed in
  // this tab, later the iOS app loading it again. Nothing reloads, so the
  // question is taken here. Like a fresh start it fills only an empty field,
  // in a new chat.
  function questionFromLink() {
    const text = App.questionLink?.parse?.(window.location.hash);
    if (typeof text !== "string" || window.location.pathname !== "/app") return;
    try {
      window.history.replaceState(window.history.state, "", window.location.pathname + window.location.search);
    } catch (_) { /* the fragment stays; the question still lands */ }
    const input = field();
    const filled = Boolean(text && input && !input.disabled && !input.value.trim());
    if (filled) {
      if (!document.body.classList.contains("is-hero")) document.getElementById("newRunButton")?.click();
      input.value = text;
      source = "link";
      // Autosize, the demo chip, collapse and Send follow the field's input.
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.focus({ preventScroll: true });
      input.setSelectionRange(input.value.length, input.value.length);
    }
    track("app_question_link", { filled, guest: Boolean(App.isGuestComposer?.()) });
  }

  // The waiting question stays in the field but no longer goes out by itself
  // (firebase.js: a login link from another browser's request).
  function forgetPending() { writePending(null); }

  App.composerInvite = { sendAsGuest, afterAccessUpdate, takeAskContext, forgetPending };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
  else init();
})();
