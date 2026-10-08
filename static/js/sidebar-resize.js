// Drag the app sidebar's right edge to make it wider or narrower.
//
// One CSS custom property, --sidebar-width on <html>, carries the width; the
// sidebar, its fixed footer, the floating toggle, the centred reading column
// (--app-sidebar-offset) and the docked answer reader all derive from it
// (layout.css, model-answer-reader.css). The stored width is applied while
// this head script runs, before the first paint, so a reload does not jump.
//
// The handle (.sidebar-resizer, role="separator") exists only for the
// push-mode sidebar on wide screens (≥1100px) while it is open; the overlay
// sidebar on narrow screens keeps its own width. Pointer drag, double-click
// to reset, and the keyboard (arrows, Shift for larger steps, Home/End) all
// end in the same `set` and persist under localStorage "sidebar_width".
//
// Contract (App.sidebarResize): { get(), set(px, {persist}), reset(), bounds() }
(function () {
  'use strict';
  const App = window.App = window.App || {};
  const STORAGE_KEY = 'sidebar_width';
  const DEFAULT_WIDTH = 260;
  const MIN_WIDTH = 200;
  const MAX_WIDTH = 480;
  // The reading column keeps at least 60 % of the window.
  const MAX_SHARE = 0.4;
  const STEP = 10;
  const BIG_STEP = 40;
  const root = document.documentElement;

  function bounds() {
    const max = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, Math.floor((window.innerWidth || 0) * MAX_SHARE)));
    return { min: MIN_WIDTH, max };
  }
  function stored() {
    try {
      const value = Number(localStorage.getItem(STORAGE_KEY));
      return Number.isFinite(value) && value > 0 ? value : null;
    } catch (_) { return null; }
  }
  let preferred = stored() ?? DEFAULT_WIDTH;
  function clamp(px) {
    const { min, max } = bounds();
    return Math.round(Math.min(max, Math.max(min, Number(px) || DEFAULT_WIDTH)));
  }
  function apply() {
    const width = clamp(preferred);
    if (width === DEFAULT_WIDTH) root.style.removeProperty('--sidebar-width');
    else root.style.setProperty('--sidebar-width', `${width}px`);
    const handle = document.getElementById('sidebarResizer');
    if (handle) {
      const { min, max } = bounds();
      handle.setAttribute('aria-valuemin', String(min));
      handle.setAttribute('aria-valuemax', String(max));
      handle.setAttribute('aria-valuenow', String(width));
      handle.setAttribute('aria-valuetext', `${width} pixels`);
    }
    return width;
  }
  function get() { return clamp(preferred); }
  function set(px, { persist = true } = {}) {
    // What the person chose is kept as chosen; a narrow window only caps
    // what is shown, and a wider window brings the chosen width back.
    preferred = clamp(px);
    const width = apply();
    if (persist) {
      try {
        if (width === DEFAULT_WIDTH) localStorage.removeItem(STORAGE_KEY);
        else localStorage.setItem(STORAGE_KEY, String(width));
      } catch (_) { /* private mode: the width lasts for this page */ }
    }
    return width;
  }
  function reset() { return set(DEFAULT_WIDTH); }

  // Before the first paint (this file is in the render-blocking head group).
  apply();

  function mount() {
    const sidebar = document.getElementById('appSidebar');
    if (!sidebar || document.getElementById('sidebarResizer')) return;
    const handle = document.createElement('div');
    handle.id = 'sidebarResizer';
    handle.className = 'sidebar-resizer';
    handle.tabIndex = 0;
    handle.setAttribute('role', 'separator');
    handle.setAttribute('aria-orientation', 'vertical');
    handle.setAttribute('aria-controls', 'appSidebar');
    handle.setAttribute('aria-label', 'Resize sidebar');
    handle.title = 'Drag to resize · double-click to reset';
    sidebar.after(handle);
    apply();

    let drag = null;
    function finish(event) {
      if (!drag || (event && event.pointerId !== drag.pointerId)) return;
      try { handle.releasePointerCapture(drag.pointerId); } catch (_) { /* already released */ }
      drag = null;
      document.body.classList.remove('is-resizing-sidebar');
      set(get());
    }
    handle.addEventListener('pointerdown', event => {
      if (event.button !== 0 || drag) return;
      event.preventDefault();
      drag = { pointerId: event.pointerId, startX: event.clientX, startWidth: get() };
      try { handle.setPointerCapture(event.pointerId); } catch (_) { /* synthetic events */ }
      document.body.classList.add('is-resizing-sidebar');
      handle.focus({ preventScroll: true });
    });
    handle.addEventListener('pointermove', event => {
      if (!drag || event.pointerId !== drag.pointerId) return;
      set(drag.startWidth + event.clientX - drag.startX, { persist: false });
    });
    handle.addEventListener('pointerup', finish);
    handle.addEventListener('pointercancel', finish);
    handle.addEventListener('lostpointercapture', finish);
    handle.addEventListener('dblclick', () => reset());
    handle.addEventListener('keydown', event => {
      const step = event.shiftKey ? BIG_STEP : STEP;
      const keys = {
        ArrowLeft: () => set(get() - step),
        ArrowRight: () => set(get() + step),
        Home: () => set(bounds().min),
        End: () => set(bounds().max),
      };
      if (!keys[event.key]) return;
      event.preventDefault();
      keys[event.key]();
    });
    window.addEventListener('resize', apply);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount, { once: true });
  else mount();

  App.sidebarResize = { get, set, reset, bounds, DEFAULT_WIDTH, MIN_WIDTH, MAX_WIDTH };
})();
