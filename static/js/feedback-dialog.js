// =====================================================================
// feedback-dialog.js
// The "Send feedback" dialog in the sidebar footer (#feedbackModal).
//
// Sending needs an account (POST /feedback verifies the ID token), so a
// guest gets the login hint and the contact address instead of a form that
// can only fail. The answer lands in the dialog's own status line instead of
// an alert(), and the submit button stays locked while a send is in flight,
// so a double click is one message.
//
// Call-time dependencies: App.modalDialog (modal-dialog.js), window.auth
// (firebase.js), App.openAuthModal (firebase.js), App.trackAppEvent
// (app-core.js), App.readJson, App.httpError and App.userError
// (app-text.js).
// =====================================================================

(function () {
  window.App = window.App || {};

  const $ = id => document.getElementById(id);

  function track(name, data) {
    window.App.trackAppEvent?.(name, data);
  }

  const NOT_SENT = "Your feedback couldn’t be sent. Try again.";

  // The limits of persistence_guard.create_feedback. Their server sentences
  // have no German entry, and the daily one gives no way forward.
  const LIMIT_MESSAGES = {
    feedback_cooldown: "You just sent feedback. Try again in a moment.",
    feedback_daily_limit: "You’ve reached today’s feedback limit. You can also write to contact@consens.io."
  };

  // A refusal arrives as {error, code, retry_after} (main.error_body) or, for
  // a field the server rejects, as {error: "Validation failed", details:
  // [{msg}]}. Only FeedbackRequest's own validators write sentences for a
  // reader (Pydantic prefixes them with "Value error, "); Pydantic's own
  // words ("String should have at most …") are not.
  function errorMessage(response, data) {
    if (response.status === 401) return "Log in again to send feedback.";
    const error = window.App.httpError(response, data);
    if (LIMIT_MESSAGES[error.code]) return LIMIT_MESSAGES[error.code];
    if (response.status === 422) {
      const own = (Array.isArray(data?.details) ? data.details : [])
        .map(detail => String(detail?.msg || ""))
        .find(msg => /^Value error,\s*\S/.test(msg));
      return own ? own.replace(/^Value error,\s*/, "") : NOT_SENT;
    }
    return window.App.userError(error, { fallback: NOT_SENT });
  }

  // Resolves with the server's answer; rejects with an Error whose message
  // can be shown as is.
  async function send(message, email) {
    const user = window.auth?.currentUser;
    if (!user) throw new Error("Log in to send feedback.");
    let response;
    try {
      const idToken = await user.getIdToken();
      response = await fetch("/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, email: email || null, id_token: idToken })
      });
    } catch (error) {
      console.error("Feedback request failed:", error);
      throw new Error(window.App.userError(error, { fallback: NOT_SENT }));
    }
    const data = await window.App.readJson(response).catch(() => null);
    if (!response.ok || data?.status !== "success") {
      throw new Error(errorMessage(response, data));
    }
    return data;
  }

  function setStatus(text, tone = "") {
    const status = $("feedbackStatus");
    if (!status) return;
    status.textContent = text;
    status.hidden = !text;
    if (tone) status.dataset.tone = tone;
    else delete status.dataset.tone;
  }

  function open(event) {
    const dialog = $("feedbackModal");
    const form = $("feedbackForm");
    const guest = !window.auth?.currentUser;
    const note = $("feedbackGuestNote");
    if (note) note.hidden = !guest;
    if (form) form.hidden = guest;
    setStatus("");
    window.App.modalDialog?.open(dialog, {
      opener: event?.currentTarget || $("feedbackButton"),
      focus: guest ? $("feedbackLoginButton") : null
    });
    track("app_feedback_open", { logged_in: !guest });
  }

  async function submit(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const button = form.querySelector('button[type="submit"]');
    if (button?.disabled) return;
    const message = form.elements.message.value.trim();
    const email = form.elements.email.value.trim();
    if (!message) {
      setStatus("Please write a message first.", "error");
      form.elements.message.focus();
      return;
    }
    track("app_feedback_submit", { logged_in: Boolean(window.auth?.currentUser) });
    if (button) button.disabled = true;
    form.setAttribute("aria-busy", "true");
    setStatus("Sending…");
    try {
      await send(message, email);
      form.reset();
      track("app_feedback_result", { status: "success" });
      setStatus("Thanks, your feedback was sent.");
    } catch (error) {
      track("app_feedback_result", { status: "error" });
      setStatus(error.message, "error");
    } finally {
      if (button) button.disabled = false;
      form.removeAttribute("aria-busy");
    }
  }

  function bind() {
    const dialog = $("feedbackModal");
    const form = $("feedbackForm");
    if (!dialog || dialog.dataset.feedbackBound === "true") return;
    dialog.dataset.feedbackBound = "true";
    // A typed message keeps the dialog open on a backdrop click; Escape and
    // the close button still close it.
    window.App.modalDialog?.bind(dialog, {
      keepOpen: () => Boolean(form?.elements.message?.value.trim())
    });
    $("feedbackButton")?.addEventListener("click", open);
    $("closeFeedbackModal")?.addEventListener("click", () => window.App.modalDialog?.close(dialog));
    // One dialog at a time: close this one first, then open the login with
    // the feedback button as its opener.
    $("feedbackLoginButton")?.addEventListener("click", () => {
      window.App.modalDialog?.close(dialog);
      window.App.openAuthModal?.("login", $("feedbackButton"), "feedback");
    });
    form?.addEventListener("submit", submit);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bind);
  else bind();

  window.App.feedback = { send, open };
})();
