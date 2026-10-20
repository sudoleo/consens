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
// Solange eine Tastatur offen ist, setzt dieses Modul body.keyboard-open
// und schreibt, wie weit die Unterkante des sichtbaren Viewports ueber der
// des Layout-Viewports liegt, als --keyboard-lift an den Composer selbst
// (nicht an <html>: eine Variable am Wurzelelement liess bei jedem Scroll
// die Styles der ganzen Seite neu rechnen, Apple-Audit D9). shell.css hebt
// den unten fixierten Composer per transform um diesen Betrag an, ohne
// Layout. Jede offene Ebene mit Feldern (jeder modale Dialog, das Memory-
// und das Gmail-&-Calendar-Sheet) bekommt den sichtbaren Bereich als
// --keyboard-top/--keyboard-height und endet damit an der Tastatur
// (overlays.css, Apple-Audit F8): was man tippt und die Knoepfe darunter
// bleiben erreichbar. Ohne Tastatur bleibt es bei bottom: 0, das der Browser
// beim Scrollen ohne Verzug nachfuehrt.
//
// iOS meldet die neue Groesse erst, wenn die Tastatur schon steht; der
// Composer sprang ihr hinterher und liess beim Schliessen kurz eine Luecke
// (Apple-Audit F9). Hat dieses Geraet die Tastatur schon einmal gemeldet,
// faehrt der Composer beim Fokus deshalb sofort mit ihr hoch (gemerkte Hoehe,
// iOS-Kurve, body.keyboard-moving) und beim Verlassen des Feldes mit ihr
// herunter; die gemeldete Groesse korrigiert danach nur noch. Android meldet
// nie eine verdeckende Tastatur (resizes-content) und bleibt unberuehrt.
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
  const MOVING_CLASS = "keyboard-moving";
  // Weniger Verdeckung ist Browser-Chrome (Werkzeugleiste, Formularleiste),
  // keine Tastatur.
  const KEYBOARD_MIN_PX = 120;
  // So lange faehrt die Tastatur auf iOS (shell.css: .keyboard-moving).
  const MOVE_MS = 300;
  const LIFT_KEY = "consensio.keyboardLift.v1";
  const NOT_TYPED = /^(button|checkbox|color|file|hidden|image|radio|range|reset|submit)$/i;
  // Until then a rise made ahead of the keyboard stands, even though the
  // viewport has not reported it yet; without a keyboard it ends then.
  const PREDICTION_MS = 1000;
  let frame = 0;
  let moveTimer = 0;
  let predictedUntil = 0;

  function composer() { return document.querySelector(".input-section"); }
  // The layers that cover the page and hold fields; the open ones follow the
  // keyboard. Variables on the layer itself, never on <html> (D9).
  const LAYERS = "dialog[open], .memory-edit-backdrop:not([hidden]), .agent-google-overlay:not([hidden])";
  let layers = [];

  function typing() {
    const el = document.activeElement;
    if (!el || el === document.body) return false;
    if (el.isContentEditable) return true;
    if (el.tagName === "TEXTAREA") return !el.readOnly && !el.disabled;
    if (el.tagName !== "INPUT" || el.readOnly || el.disabled) return false;
    return !NOT_TYPED.test(el.type || "");
  }

  function orientation() {
    return window.innerWidth > window.innerHeight ? "landscape" : "portrait";
  }
  function rememberedLift() {
    try {
      const value = Number(JSON.parse(window.localStorage.getItem(LIFT_KEY) || "{}")[orientation()]);
      return Number.isFinite(value) && value >= KEYBOARD_MIN_PX ? value : 0;
    } catch (_) { return 0; }
  }
  function rememberLift(lift) {
    try {
      const stored = JSON.parse(window.localStorage.getItem(LIFT_KEY) || "{}");
      if (Math.abs((stored[orientation()] || 0) - lift) < 1) return;
      stored[orientation()] = Math.round(lift);
      window.localStorage.setItem(LIFT_KEY, JSON.stringify(stored));
    } catch (_) { /* private mode: the next opening is measured again */ }
  }

  function write(open, lift, edge, top = 0) {
    document.body.classList.toggle(OPEN_CLASS, open);
    const section = composer();
    for (const layer of layers) {
      layer.style.removeProperty("--keyboard-top");
      layer.style.removeProperty("--keyboard-height");
    }
    layers = open ? Array.from(document.querySelectorAll(LAYERS)) : [];
    if (open) {
      section?.style.setProperty("--keyboard-lift", `${Math.round(lift)}px`);
      for (const layer of layers) {
        layer.style.setProperty("--keyboard-top", `${Math.round(top)}px`);
        layer.style.setProperty("--keyboard-height", `${Math.round(edge - top)}px`);
      }
    } else {
      section?.style.removeProperty("--keyboard-lift");
    }
  }

  // The keyboard's own move, ahead of its report: Safari reports the size
  // once the keyboard stands. Only for a size this device reported before.
  function glide() {
    document.body.classList.add(MOVING_CLASS);
    clearTimeout(moveTimer);
    moveTimer = setTimeout(() => document.body.classList.remove(MOVING_CLASS), MOVE_MS);
  }

  function sync() {
    frame = 0;
    // Hineingezoomt schrumpft das sichtbare Viewport auch ohne Tastatur.
    const unzoomed = Math.abs((viewport.scale || 1) - 1) < 0.01;
    const layoutHeight = root.clientHeight;
    const covered = layoutHeight - viewport.height;
    const open = media.matches && unzoomed && covered > KEYBOARD_MIN_PX && typing();
    // The keyboard is still on its way up: the rise made ahead of it stays.
    if (!open && typing() && media.matches && performance.now() < predictedUntil) return;
    predictedUntil = 0;
    const edge = viewport.offsetTop + viewport.height;
    if (open) rememberLift(layoutHeight - viewport.height);
    write(open, Math.max(0, layoutHeight - edge), edge, viewport.offsetTop);
  }

  function schedule() {
    if (!frame) frame = window.requestAnimationFrame(sync);
  }

  // A tap into a field: if this device's keyboard is known, the composer
  // rises with it now instead of after it.
  function onFocusIn() {
    if (!media.matches || !typing() || !composer()?.contains(document.activeElement)) { schedule(); return; }
    const lift = rememberedLift();
    if (lift && !document.body.classList.contains(OPEN_CLASS)
      && root.clientHeight - viewport.height <= KEYBOARD_MIN_PX) {
      glide();
      predictedUntil = performance.now() + PREDICTION_MS;
      write(true, lift, root.clientHeight - lift);
      // No keyboard came (a hardware keyboard): the composer goes back down.
      window.setTimeout(schedule, PREDICTION_MS + 20);
    }
    schedule();
  }
  // Leaving the field closes the keyboard: the composer goes down with it.
  // Another field taking the focus keeps it (checked once focus has moved).
  function onFocusOut() {
    window.setTimeout(() => {
      if (document.body.classList.contains(OPEN_CLASS) && !typing()) {
        glide();
        write(false, 0, 0);
      }
      schedule();
    }, 0);
  }

  // Die Tastatur meldet sich ueber resize, Safaris Verschieben des sichtbaren
  // Viewports ueber scroll; der Fokuswechsel entscheidet, ob getippt wird.
  viewport.addEventListener("resize", schedule);
  viewport.addEventListener("scroll", schedule);
  document.addEventListener("focusin", onFocusIn);
  document.addEventListener("focusout", onFocusOut);
  media.addEventListener?.("change", schedule);
  sync();

  window.App.composerKeyboard = { sync: sync };
})();
