// Auth bootstrap watchdog. firebase.js is an ES module with CDN imports; if
// those imports fail, none of that module executes. This small same-origin
// classic script keeps the signed-out UI usable instead of trusting a stale
// localStorage token forever.
(function () {
  const timeout = Number(window.AUTH_BOOTSTRAP_TIMEOUT_MS) || 8000;
  let fallbackActive = false;

  function modalEls() {
    return {
      modal: document.getElementById("loginModal"),
      close: document.getElementById("closeLoginModal"),
      error: document.getElementById("loginError")
    };
  }

  // #loginModal is a native <dialog> (App.modalDialog, overlays group, loaded
  // before this file): it brings focus back to the trigger and closes on
  // Escape and its backdrop by itself.
  function closeUnavailableDialog() {
    const { modal } = modalEls();
    if (!modal?.open) return;
    if (window.App?.modalDialog) window.App.modalDialog.close(modal);
    else modal.removeAttribute("open");
  }

  function openUnavailableDialog(trigger) {
    const { modal, close, error } = modalEls();
    if (!modal) return;
    if (error) {
      error.textContent = "Login is temporarily unavailable. Check your connection and try again.";
    }
    if (modal.open) return;
    if (window.App?.modalDialog) window.App.modalDialog.open(modal, { opener: trigger || null, focus: close });
    else {
      modal.setAttribute("open", "");
      close?.focus({ preventScroll: true });
    }
  }

  function activateFallback() {
    if (window.auth || fallbackActive) return;
    fallbackActive = true;
    document.documentElement.dataset.authUnavailable = "true";

    const actions = document.getElementById("authTopActions");
    if (actions) actions.hidden = false;
    const loginContainer = document.getElementById("loginContainer");
    if (loginContainer) {
      loginContainer.innerHTML = "";
      loginContainer.hidden = true;
    }
    const watchUsage = document.getElementById("watchUsageDisplay");
    if (watchUsage) watchUsage.textContent = "";
    const bookmarks = document.getElementById("bookmarksContainer");
    if (bookmarks?.querySelector(".skeleton")) bookmarks.innerHTML = "";

    actions?.addEventListener("click", event => {
      const trigger = event.target.closest("button");
      if (!trigger || window.auth) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      openUnavailableDialog(trigger);
    }, true);
    modalEls().close?.addEventListener("click", closeUnavailableDialog);
    window.dispatchEvent(new CustomEvent("consensio:auth-unavailable"));
  }

  const timer = window.setTimeout(activateFallback, timeout);
  window.addEventListener("consensio:auth-state", () => {
    window.clearTimeout(timer);
    delete document.documentElement.dataset.authUnavailable;
  }, { once: true });
})();
