// =====================================================================
// popover.js
// App.popover: the menus and cards that open at a control — the (+) menu,
// the model menu, the account menu, the "…" menus, the token card, the
// card of a marked sentence. Each module keeps its own markup and its own
// open/close; this module makes them one family (Apple audit C4, E6, E10):
//
//   - exactly one is open: opening one closes every other (and a dialog
//     opening closes them all), even when the opener stopped its click;
//   - each comes from its control and goes back to it (overlays.css draws
//     the motion; this sets the direction from where the control sits);
//   - the keyboard works the same in every menu: focus goes in, arrows
//     and Home/End move, Escape closes and gives focus back, Tab leaves.
//
//   const pop = App.popover.register(panel, { close: opts => myClose(opts) });
//   // in myOpen():   App.popover.opened(panel, { trigger });   (before showing)
//   // in myClose():  App.popover.closed(panel);
//   App.popover.menuKeys(panel, { items: () => [...], close, opener });
//   App.popover.focusItem(panel, items, 0 | -1);
//   App.popover.closeAll({ except });
//   App.popover.leave(panel, () => panel.remove());   // a menu that is removed
//   App.popover.triggerOf(el)      the control the popover around `el` came from
//   App.popover.recentTrigger()    that control for a popover closed in the last second
//
// Loaded in the "auth" group (the overlay modules), before firebase.js (the account menu).
// =====================================================================
(function () {
  "use strict";
  const App = window.App = window.App || {};

  const registry = new Map(); // element -> { close }
  const openSet = new Set();
  // The control each popover came from, and the one that closed last: a
  // dialog chosen in a menu gives focus back to the menu's control when it
  // closes, as the menu item is gone by then (modal-dialog.js).
  const triggers = new WeakMap();
  let lastClosed = null;

  function register(element, { close } = {}) {
    if (!element) return null;
    registry.set(element, { close: typeof close === "function" ? close : null });
    element.setAttribute("data-popover", "");
    return {
      opened: options => opened(element, options),
      closed: () => closed(element),
    };
  }

  function unregister(element) {
    registry.delete(element);
    closed(element);
  }

  // A popover sits above its control when the control is in the lower half
  // of the window (the composer in a thread, the sidebar footer), below it
  // otherwise; it comes out of the control and goes back into it.
  function aim(element, trigger) {
    const rect = trigger?.getBoundingClientRect?.();
    if (!rect || !(rect.width || rect.height)) {
      element.style.removeProperty("--popover-shift");
      element.style.removeProperty("--popover-origin-y");
      return;
    }
    const viewport = window.visualViewport;
    const height = viewport?.height || window.innerHeight || 0;
    const above = rect.top + rect.height / 2 > (viewport?.offsetTop || 0) + height / 2;
    element.style.setProperty("--popover-shift", above ? "4px" : "-4px");
    element.style.setProperty("--popover-origin-y", above ? "100%" : "0%");
  }

  function closeAll({ except = null, reason = "other" } = {}) {
    for (const element of Array.from(openSet)) {
      if (element === except) continue;
      if (!element.isConnected) { openSet.delete(element); continue; }
      closed(element);
      try {
        registry.get(element)?.close?.({ reason, focus: false });
      } catch (error) {
        console.error("Closing a popover failed:", error);
      }
    }
  }

  function opened(element, { trigger = null } = {}) {
    if (!element) return;
    if (!registry.has(element)) register(element);
    closeAll({ except: element });
    App.motion?.cancelLeave?.(element);
    aim(element, trigger);
    if (trigger) triggers.set(element, trigger);
    else triggers.delete(element);
    openSet.add(element);
  }

  function closed(element) {
    if (openSet.delete(element)) lastClosed = { trigger: triggers.get(element) || null, at: Date.now() };
  }

  // The control `element` (a popover, or anything inside one) came from.
  function triggerOf(element) {
    const popover = element?.closest?.("[data-popover]");
    return (popover && triggers.get(popover)) || null;
  }

  // The control of the popover that closed in the last moment (a menu item
  // that closes its menu before it opens a dialog), or null.
  function recentTrigger(within = 1000) {
    if (!lastClosed || Date.now() - lastClosed.at > within) return null;
    return lastClosed.trigger?.isConnected ? lastClosed.trigger : null;
  }

  function isOpen(element) {
    return openSet.has(element);
  }

  function anyOpen() {
    for (const element of openSet) if (element.isConnected) return true;
    return false;
  }

  function visibleItems(container, selector) {
    return Array.from(container.querySelectorAll(selector)).filter(item =>
      !item.disabled && !item.closest("[hidden]") && item.getClientRects().length > 0);
  }

  const ITEM_SELECTOR = '[role="menuitem"], [role="menuitemradio"], [role="menuitemcheckbox"], [role="option"], '
    + 'button, input:not([type="hidden"]), a[href]';

  function itemsOf(container, items) {
    const list = typeof items === "function" ? items() : items;
    return Array.isArray(list) ? list.filter(Boolean) : visibleItems(container, ITEM_SELECTOR);
  }

  function focusItem(container, items, index) {
    const list = itemsOf(container, items);
    if (!list.length) return false;
    const target = list[((index % list.length) + list.length) % list.length];
    target.focus({ preventScroll: true });
    return true;
  }

  // The account menu's keyboard, for every menu: the arrows wrap, Home/End
  // jump, Escape closes and hands focus back to the opener, Tab leaves the
  // menu (and closes it) in the page's own order.
  function menuKeys(container, { items = null, close, opener = null } = {}) {
    if (!container || container.__popoverKeys) return;
    container.__popoverKeys = true;
    container.addEventListener("keydown", event => {
      if (event.defaultPrevented || event.isComposing) return;
      const list = itemsOf(container, items);
      const index = list.indexOf(document.activeElement);
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        // A focused field (a search box in a menu) keeps its own arrows.
        if (document.activeElement?.matches?.("textarea, input[type='text'], input[type='search']")) return;
        event.preventDefault();
        const step = event.key === "ArrowDown" ? 1 : -1;
        focusItem(container, list, index < 0 ? (step > 0 ? 0 : -1) : index + step);
      } else if (event.key === "Home" || event.key === "End") {
        if (document.activeElement?.matches?.("textarea, input[type='text'], input[type='search']")) return;
        event.preventDefault();
        focusItem(container, list, event.key === "Home" ? 0 : -1);
      } else if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        close?.({ reason: "escape", focus: true });
        const back = typeof opener === "function" ? opener() : opener;
        if (back?.isConnected && !container.contains(back)) back.focus({ preventScroll: true });
      } else if (event.key === "Tab") {
        close?.({ reason: "tab", focus: false });
      }
    });
  }

  // A menu that is built on open and removed on close leaves the same way
  // the others do (overlays.css: [data-popover].is-leaving).
  function leave(element, done) {
    closed(element);
    if (App.motion?.leave) App.motion.leave(element, done);
    else done?.();
  }

  App.popover = { register, unregister, opened, closed, isOpen, anyOpen, closeAll, menuKeys, focusItem, leave, aim,
    triggerOf, recentTrigger };
})();
