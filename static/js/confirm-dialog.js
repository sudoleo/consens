// =====================================================================
// confirm-dialog.js
// App.confirm: the app's own question before something that cannot be
// taken back, instead of the browser's grey "consens.io says" window
// (Apple audit E1). One dialog, built once, the same surface and motion as
// every other (App.modalDialog, overlays.css).
//
//   const ok = await App.confirm({
//     title: "Delete your account?",
//     body: "This removes …",           // a string; line breaks are kept
//     confirmLabel: "Delete account",   // default "OK"
//     cancelLabel: "Cancel",            // default "Cancel"
//     danger: true,                     // the confirm button says it destroys
//   });
//
// Resolves true for the confirm button, false for Cancel, Escape, the
// backdrop or a newer App.confirm. With danger, focus starts on Cancel:
// Enter alone never destroys anything.
// Loaded in the "auth" group (the overlay modules) after modal-dialog.js.
// =====================================================================
(function () {
  "use strict";
  const App = window.App = window.App || {};

  let dialog = null;
  let pending = null;

  function build() {
    if (dialog?.isConnected) return dialog;
    dialog = document.createElement("dialog");
    dialog.id = "appConfirmDialog";
    dialog.className = "modal confirm-dialog";
    dialog.setAttribute("aria-labelledby", "appConfirmTitle");
    dialog.setAttribute("aria-describedby", "appConfirmBody");
    dialog.innerHTML = `
      <div class="modal-content confirm-modal-content">
        <h2 id="appConfirmTitle"></h2>
        <p id="appConfirmBody"></p>
        <div class="confirm-modal-actions">
          <button type="button" class="btn-free confirm-cancel" data-answer="false"></button>
          <button type="button" class="btn-pro confirm-accept" data-answer="true"></button>
        </div>
      </div>`;
    document.body.append(dialog);
    App.modalDialog?.bind(dialog, { onClose: () => answer(false) });
    dialog.addEventListener("click", event => {
      const button = event.target.closest?.("[data-answer]");
      if (!button) return;
      const accepted = button.dataset.answer === "true";
      // The answer before the close: closing settles the rest as "no".
      answer(accepted);
      App.modalDialog?.close(dialog);
      if (!App.modalDialog) dialog.removeAttribute("open");
    });
    return dialog;
  }

  function answer(value) {
    if (!pending) return;
    const { resolve } = pending;
    pending = null;
    resolve(Boolean(value));
  }

  function confirm({ title = "", body = "", confirmLabel = "OK", cancelLabel = "Cancel", danger = false } = {}) {
    const element = build();
    // A newer question replaces an unanswered one: that one is a "no".
    answer(false);
    element.querySelector("#appConfirmTitle").textContent = String(title);
    const text = element.querySelector("#appConfirmBody");
    text.textContent = String(body);
    text.hidden = !body;
    const cancel = element.querySelector(".confirm-cancel");
    const accept = element.querySelector(".confirm-accept");
    cancel.textContent = cancelLabel;
    accept.textContent = confirmLabel;
    accept.classList.toggle("is-danger", Boolean(danger));
    element.classList.toggle("is-danger", Boolean(danger));
    return new Promise(resolve => {
      pending = { resolve };
      const focus = danger ? cancel : accept;
      if (App.modalDialog) {
        if (App.modalDialog.isOpen(element)) focus.focus({ preventScroll: true });
        else App.modalDialog.open(element, { focus });
      } else {
        element.setAttribute("open", "");
        focus.focus();
      }
    });
  }

  App.confirm = confirm;
})();
