/* Public pages: apply the saved or preferred color scheme before first paint.
 *
 * Loaded render-blocking in <head> so the page never flashes the wrong theme.
 * It is an external file (not an inline <script>) so pages that load it can
 * run under a script CSP without 'unsafe-inline'.
 */
(function () {
  "use strict";
  try {
    var savedTheme = window.localStorage.getItem("theme");
    var prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
    if (savedTheme === "dark" || (!savedTheme && prefersDark)) {
      document.documentElement.classList.add("dark-mode");
    }
  } catch (error) {
    /* Blocked storage: keep the default light theme. */
  }
})();
