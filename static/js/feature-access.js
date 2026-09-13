// Feature gates keep their existing window.App.showProFeatureModal contract:
// true means a notice was shown, false lets the caller provide a fallback.
// The full early-access explanation opens only on an explicit information click.
(function () {
  const app = window.App;
  const notice = document.getElementById("featureAccessNotice");
  const message = document.getElementById("featureAccessMessage");
  const modal = document.getElementById("proFeatureModal");
  const closeButton = document.getElementById("closeProModal");
  const details = document.getElementById("featureAccessDetails");
  const sidebarLink = document.getElementById("upgradeLink");
  const plusFeatures = new Set(["Resolve", "File uploads"]);
  const messages = {
    "Deep Think": "Deep Think is not available on your account yet. You can continue with a standard run.",
    "High Quality mode": "High Quality mode is not available on your account yet. Your current models are still selected.",
    "Resolve": "Resolve is not available on your account yet. You can still review the differences and model answers.",
    "File uploads": "File uploads are not available on your account yet. You can enter your question as text.",
    "More frequent Consensus Watch checks": "More frequent Watch checks are not available on your account yet.",
    "More Consensus Watches": "Your active Watch limit has been reached. Pause a Watch to make room for another.",
  };
  let returnFocus = null;
  let dismissTimer = null;

  function dismissNotice() {
    window.clearTimeout(dismissTimer);
    dismissTimer = null;
    if (notice) notice.hidden = true;
  }

  app.showProFeatureModal = function (featureName) {
    if (window.isUserPro) return false;
    if (window.isUserPlus && plusFeatures.has(featureName)) return false;
    if (!notice || !message) return false;
    message.textContent = messages[featureName]
      || `${featureName || "This feature"} is not available on your account yet.`;
    notice.hidden = false;
    window.clearTimeout(dismissTimer);
    dismissTimer = window.setTimeout(dismissNotice, 5000);
    app.trackAppEvent?.("app_feature_access_notice", { feature: featureName || "general" });
    return true;
  };

  app.showAccessInfo = function () {
    if (!modal) return false;
    returnFocus = notice?.contains(document.activeElement)
      ? sidebarLink : document.activeElement;
    dismissNotice();
    modal.style.display = "block";
    closeButton?.focus();
    app.trackAppEvent?.("app_pro_beta_opened", { feature: "general" });
    return true;
  };

  function closeInfo() {
    if (!modal || modal.style.display !== "block") return;
    modal.style.display = "none";
    if (returnFocus?.isConnected && returnFocus.getClientRects().length) {
      returnFocus.focus();
    } else {
      document.getElementById("questionInput")?.focus();
    }
    returnFocus = null;
  }

  app.dismissFeatureAccessNotice = dismissNotice;
  document.getElementById("closeFeatureAccessNotice")?.addEventListener("click", dismissNotice);
  closeButton?.addEventListener("click", closeInfo);
  document.getElementById("keepFreeBtn")?.addEventListener("click", closeInfo);
  for (const link of [details, sidebarLink]) {
    link?.addEventListener("click", (event) => {
      event.preventDefault();
      app.showAccessInfo();
    });
  }
  modal?.addEventListener("click", (event) => {
    if (event.target === modal) closeInfo();
  });
  modal?.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      closeInfo();
    } else if (event.key === "Tab") {
      const controls = Array.from(modal.querySelectorAll("button, a[href]"));
      const first = controls[0];
      const last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    }
  });
})();
