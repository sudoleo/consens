// =====================================================================
// feedback-dialog.js
// The "Send feedback" dialog in the sidebar footer (#feedbackModal).
//
// Sending needs an account (POST /feedback verifies the ID token), so a
// guest gets the login hint and the contact address instead of a form that
// can only fail. The answer lands in the dialog's own status line instead of
// an alert(), and the submit button stays locked while a send is in flight,
// so a double click is one message (audit F7).
//
// Call-time dependencies: App.modalDialog (modal-dialog.js), window.auth
// (firebase.js), App.openAuthModal (firebase.js), App.trackAppEvent
// (app-core.js).
// =====================================================================

(function () {
  window.App = window.App || {};

  const $ = id => document.getElementById(id);

  function track(name, data) {
    window.App.trackAppEvent?.(name, data);
  }

  // The reason a failed send gives the person, in the dialog's own words.
  // FastAPI sends a string detail for 401/429/500 and a list for validation.
  function errorMessage(status, data) {
    if (status === 401) return "Log in again to send feedback.";
    const detail = Array.isArray(data?.detail) ? data.detail[0]?.msg : data?.detail;
    if (typeof detail === "string" && detail.trim()) return detail.replace(/^Value error,\s*/, "");
    if (status === 429) return "Too many messages in a row. Wait a minute and try again.";
    return "Your feedback couldn’t be sent. Try again.";
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
      throw new Error(window.App.userError(error, { fallback: "Your feedback couldn’t be sent. Try again." }));
    }
    const data = await window.App.readJson(response).catch(() => null);
    if (!response.ok || data?.status !== "success") {
      throw new Error(errorMessage(response.status, data));
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
