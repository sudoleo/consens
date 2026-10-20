// Feature gates keep their existing window.App.showProFeatureModal contract:
// true means a notice was shown, false lets the caller provide a fallback.
// The notice is the app's one notice line (App.toast, notices.js) with the
// way to the early-access note as its action; the note itself is a native
// <dialog> (App.modalDialog) that opens only on an explicit click.
(function () {
  const app = window.App;
  const modal = document.getElementById("proFeatureModal");
  const closeButton = document.getElementById("closeProModal");
  const sidebarLink = document.getElementById("upgradeLink");
  const plusFeatures = new Set(["Resolve"]);
  const messages = {
    "High Quality mode": "High Quality mode is not available on your account yet. Your current models are still selected.",
    "Resolve": "Resolve is not available on your account yet. You can still review the differences and model answers.",
    "More frequent Consensus Watch checks": "More frequent Watch checks are not available on your account yet.",
    "More Consensus Watches": "Your active Watch limit has been reached. Pause a Watch to make room for another.",
  };
  let notice = null;

  function dismissNotice() {
    notice?.cancel();
    notice = null;
  }

  app.showProFeatureModal = function (featureName) {
    if (window.isUserPro) return false;
    if (window.isUserPlus && plusFeatures.has(featureName)) return false;
    if (typeof app.toast !== "function") return false;
    const message = messages[featureName]
      || `${featureName || "This feature"} is not available on your account yet.`;
    notice = app.toast({
      message,
      key: "feature-access",
      action: { label: "About early access", onAction: () => { app.showAccessInfo({ fromNotice: true }); } },
    });
    app.trackAppEvent?.("app_feature_access_notice", { feature: featureName || "general" });
    return true;
  };

  app.showAccessInfo = function ({ fromNotice = false } = {}) {
    if (!modal) return false;
    dismissNotice();
    // From the notice, which is gone once the note opens, focus comes back
    // to the sidebar's own link to the same note.
    let opener = null;
    if (fromNotice) {
      opener = sidebarLink?.getClientRects().length ? sidebarLink : document.getElementById("questionInput");
      document.activeElement?.blur?.();
    }
    if (app.modalDialog) {
      if (!app.modalDialog.isOpen(modal)) app.modalDialog.open(modal, { opener, focus: closeButton });
    } else {
      modal.setAttribute("open", "");
      closeButton?.focus();
    }
    app.trackAppEvent?.("app_pro_beta_opened", { feature: "general" });
    return true;
  };

  function closeInfo() {
    if (!modal?.open && !modal?.hasAttribute("open")) return;
    if (app.modalDialog) app.modalDialog.close(modal);
    else modal.removeAttribute("open");
  }

  app.dismissFeatureAccessNotice = dismissNotice;
  closeButton?.addEventListener("click", closeInfo);
  document.getElementById("keepFreeBtn")?.addEventListener("click", closeInfo);
  sidebarLink?.addEventListener("click", (event) => {
    event.preventDefault();
    app.showAccessInfo();
  });
})();
