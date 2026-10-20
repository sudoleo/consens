// =====================================================================
// modal-dialog.js
// App.modalDialog: one way to open and close the app's native <dialog>
// windows: Settings, Help, Feedback, Login, Share/Watch, the early-access
// note, the attachment preview and App.confirm (confirm-dialog.js).
//
// showModal() does the hard part: the page behind becomes inert for focus,
// pointer and screen readers, and a later dialog stacks over an earlier one
// (Help over Settings) without a z-index. This helper adds what every
// dialog here needs on top of that:
//   - focus goes to a sensible control on open and back to the control that
//     opened it on close;
//   - the backdrop closes only a deliberate click on it. A press that starts
//     inside (selecting text in a field) and is released over the backdrop
//     reaches the dialog as a click on itself; that one must not close it
//     and drop what was typed (audit F5, same guard as the login dialog);
//   - Escape belongs to the open dialog, so a document-level Escape handler
//     behind it (the answer reader, a popover) does not act at the same time;
//   - an open menu or card (App.popover) closes when a dialog opens.
//
// The way in and the way out are drawn by CSS (overlays.css): the dialog
// fades and its surface rises 8px from 98 % in, and the same way back out.
// close() stays synchronous -- the page behind is usable and focus is back
// on the opener at once -- while `display`/`overlay` transition with
// allow-discrete keep the closing dialog painted until it has faded.
// =====================================================================

(function () {
  window.App = window.App || {};

  const openers = new WeakMap();
  const options = new WeakMap();
  const openDialogs = new Set();

  const FOCUSABLE = 'button:not([disabled]), [href], input:not([disabled]):not([type="hidden"]), '
    + 'select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

  function native(dialog) {
    return typeof dialog.showModal === "function";
  }

  function focusable(element) {
    return Boolean(element?.isConnected && !element.disabled && !element.closest("[hidden], [inert]"));
  }

  function focusInside(dialog, target) {
    const chosen = (typeof target === "function" ? target() : target)
      || dialog.querySelector("[autofocus]");
    // Plain focus(): the dialog is fixed, so this only scrolls its own
    // containers (a tab strip, a long body) to the control, never the page.
    if (chosen && dialog.contains(chosen)) {
      chosen.focus();
      return;
    }
    // showModal() already ran the dialog focusing steps; only the fallback
    // (engines without it) still needs a first control.
    if (!native(dialog)) dialog.querySelector(FOCUSABLE)?.focus();
  }

  // Tab wraps inside the dialog: from the last control to the first and back
  // with Shift. Without it the browser lets focus leave a modal dialog for
  // its own toolbar, and the next Tab lands at the top of the dialog only
  // after a detour through the address bar.
  function trapTab(dialog, event) {
    const controls = Array.from(dialog.querySelectorAll(FOCUSABLE))
      .filter(element => focusable(element) && element.getClientRects().length > 0);
    if (!controls.length) return;
    const first = controls[0];
    const last = controls[controls.length - 1];
    const active = document.activeElement;
    const outside = !dialog.contains(active) || active === dialog;
    if (event.shiftKey && (active === first || outside)) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && (active === last || outside)) {
      event.preventDefault();
      first.focus();
    }
  }

  function restoreFocus(dialog) {
    const opener = openers.get(dialog);
    openers.delete(dialog);
    const active = document.activeElement;
    const focusLeftWithDialog = !active || active === document.body || dialog.contains(active);
    if (focusLeftWithDialog && focusable(opener)) opener.focus({ preventScroll: true });
  }

  function settle(dialog) {
    if (!openDialogs.delete(dialog)) return;
    restoreFocus(dialog);
    options.get(dialog)?.onClose?.();
  }

  function bind(dialog, config = {}) {
    if (!dialog || options.has(dialog)) return;
    options.set(dialog, config);

    let pressedOnBackdrop = false;
    dialog.addEventListener("pointerdown", event => {
      pressedOnBackdrop = event.target === dialog;
    });
    dialog.addEventListener("click", event => {
      const deliberate = pressedOnBackdrop && event.target === dialog;
      pressedOnBackdrop = false;
      if (!deliberate) return;
      if (config.keepOpen?.()) return;
      close(dialog);
    });
    // Bubbling on the dialog: a control inside that uses Escape itself
    // (and calls preventDefault) still gets it first. What is left belongs
    // to the dialog, not to the document-level Escape handlers behind it.
    // The browser's own cancel step still closes a native modal dialog;
    // stopPropagation does not cancel it.
    dialog.addEventListener("keydown", event => {
      if (event.key === "Tab" && !event.defaultPrevented) {
        trapTab(dialog, event);
        return;
      }
      if (event.key !== "Escape" || event.isComposing) return;
      event.stopPropagation();
      if (event.defaultPrevented || native(dialog)) return;
      event.preventDefault();
      close(dialog);
    });
    // Escape, form method="dialog" and dialog.close() all end here.
    dialog.addEventListener("close", () => settle(dialog));
  }

  function open(dialog, { opener, focus } = {}) {
    if (!dialog || dialog.open) return false;
    bind(dialog);
    const active = document.activeElement;
    // Safari does not focus a clicked button, so the active element can be
    // <body>; the caller's opener is the fallback.
    const from = active && active !== document.body && !dialog.contains(active) ? active : opener;
    openers.set(dialog, from || null);
    // One layer at a time: a menu left open would sit under the dialog.
    window.App.popover?.closeAll?.({ reason: "dialog" });
    if (native(dialog)) dialog.showModal();
    else dialog.setAttribute("open", "");
    openDialogs.add(dialog);
    focusInside(dialog, focus);
    return true;
  }

  function close(dialog) {
    if (!dialog?.open) return false;
    if (typeof dialog.close === "function") dialog.close();
    else dialog.removeAttribute("open");
    // The close event is queued as a task; settle now, so focus is back on
    // the opener before the caller's next line runs. The event then finds
    // nothing left to do.
    settle(dialog);
    return true;
  }

  function isOpen(dialog) {
    return Boolean(dialog?.open);
  }

  window.App.modalDialog = { bind, open, close, isOpen };

  // The one close cross (foundation.css .close-button/.close-icon, Apple
  // audit G3): a drawn X, never the "×"/"✕" glyphs of two different fonts.
  const CLOSE_ICON = '<svg class="close-icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false">'
    + '<path d="M4 4l8 8M12 4l-8 8"/></svg>';
  window.App.closeIcon = () => CLOSE_ICON;
})();
