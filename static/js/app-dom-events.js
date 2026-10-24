(function () {
  document.addEventListener("click", (event) => {
    // The skip link (index.html) lands in the question of a chat, or on the
    // heading of the watches; without JS its #appMain still moves the start
    // of the Tab order there.
    if (event.target.closest(".skip-link")) {
      event.preventDefault();
      const watches = document.body.classList.contains("is-watch-view");
      const field = document.getElementById("questionInput");
      const target = !watches && field && !field.disabled
        ? field
        : document.getElementById(watches ? "watchDashTitle" : "appHeading");
      if (target && target !== field) target.tabIndex = -1;
      target?.focus();
      return;
    }
    const exclude = event.target.closest("[data-exclude-target]");
    if (exclude) return window.toggleExclude?.(exclude.dataset.excludeTarget);
    if (event.target.closest("#bookmarksToggle")) return window.toggleBookmarks?.();
    if (event.target.closest("#sendButton")) return window.sendQuestion?.();
    if (event.target.closest("#apiSettingsToggle")) {
      return window.toggleSettingsCollapse?.("apiSettingsArea", "apiArrow");
    }
    if (event.target.closest("#testAllKeysButton")) return window.testAllKeys?.();
  });
  document.addEventListener("keydown", (event) => {
    if (!event.target.closest("#apiSettingsToggle")) return;
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    window.toggleSettingsCollapse?.("apiSettingsArea", "apiArrow");
  });
})();
