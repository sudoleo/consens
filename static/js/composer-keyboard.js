// =====================================================================
// composer-keyboard.js
// Haelt den Thread-Composer auf dem Handy an der Tastaturkante.
//
// Chrome auf Android verkleinert fuer die Tastatur das Layout-Viewport
// (interactive-widget=resizes-content in index.html), der unten fixierte
// Composer (shell.css) faehrt dann von selbst mit. Safari auf iOS ignoriert
// diesen Hinweis: dort behaelt das Layout-Viewport seine Hoehe, nur das
// sichtbare (visual) Viewport schrumpft und verschiebt sich. Ein am
// Layout-Rand fixierter Composer stand so hinter der Tastatur oder, nach
// Safaris eigenem Scroll zum Feld, mitten im Bild — mit dem Thread, der
// zwischen ihm und der Tastatur durchschien.
//
// Solange eine Tastatur offen ist, schreibt dieses Modul die Unterkante des
// sichtbaren Viewports (in Koordinaten des Layout-Viewports, also denen von
// position: fixed) nach --keyboard-edge und setzt body.keyboard-open;
// shell.css haengt den Composer dann an diese Kante. Ohne Tastatur bleibt
// es bei bottom: 0, das der Browser beim Scrollen ohne Verzug nachfuehrt.
// Exporte: window.App.composerKeyboard.sync
// =====================================================================

(function () {
  "use strict";

  window.App = window.App || {};

  const viewport = window.visualViewport;
  if (!viewport) return;

  // Muss zur Breite passen, ab der shell.css den Composer fixiert.
  const media = window.matchMedia("(max-width: 1099px)");
  const root = document.documentElement;
  const OPEN_CLASS = "keyboard-open";
  // Weniger Verdeckung ist Browser-Chrome (Werkzeugleiste, Formularleiste),
  // keine Tastatur.
  const KEYBOARD_MIN_PX = 120;
  const NOT_TYPED = /^(button|checkbox|color|file|hidden|image|radio|range|reset|submit)$/i;
  let frame = 0;

  function typing() {
    const el = document.activeElement;
    if (!el || el === document.body) return false;
    if (el.isContentEditable) return true;
    if (el.tagName === "TEXTAREA") return !el.readOnly && !el.disabled;
    if (el.tagName !== "INPUT" || el.readOnly || el.disabled) return false;
    return !NOT_TYPED.test(el.type || "");
  }

  function sync() {
    frame = 0;
    // Hineingezoomt schrumpft das sichtbare Viewport auch ohne Tastatur.
    const unzoomed = Math.abs((viewport.scale || 1) - 1) < 0.01;
    const covered = root.clientHeight - viewport.height;
    const open = media.matches && unzoomed && covered > KEYBOARD_MIN_PX && typing();
    document.body.classList.toggle(OPEN_CLASS, open);
    if (open) {
      root.style.setProperty("--keyboard-edge", `${Math.round(viewport.offsetTop + viewport.height)}px`);
    } else {
      root.style.removeProperty("--keyboard-edge");
    }
  }

  function schedule() {
    if (!frame) frame = window.requestAnimationFrame(sync);
  }

  // Die Tastatur meldet sich ueber resize, Safaris Verschieben des sichtbaren
  // Viewports ueber scroll; der Fokuswechsel entscheidet, ob getippt wird.
  viewport.addEventListener("resize", schedule);
  viewport.addEventListener("scroll", schedule);
  document.addEventListener("focusin", schedule);
  document.addEventListener("focusout", schedule);
  media.addEventListener?.("change", schedule);
  sync();

  window.App.composerKeyboard = { sync: sync };
})();
