// =====================================================================
// motion.js
// App.motion: the motion tokens of foundation.css for script, and the one
// way a layer leaves the page.
//
// Durations and curves live in CSS (--dur-press/state/layer/light,
// --ease-standard/out/in). A script that animates (a FLIP glide, a layer
// that waits for its way out) reads the same values here instead of
// writing its own 300 or 420 ms (Apple audit C14):
//
//   App.motion.ms("layer")          -> 320 (from --dur-layer)
//   App.motion.ease("out")          -> "cubic-bezier(0.22, 1, 0.36, 1)"
//   App.motion.reduced()            -> prefers-reduced-motion: reduce
//   App.motion.leave(el, done, {token, className})
//       adds `className` (default "is-leaving", which the overlay CSS turns
//       into the closed look), waits for that transition, then calls
//       done(); at once with reduced motion or without a transition.
//   App.motion.switchTheme(apply)
//       runs apply() (the class change of light/dark) with every transition
//       off for that frame, inside one cross-fade of the page where the
//       browser has view transitions (Apple audit C8, motion.css).
//
// Loaded first in the "auth" group (the overlay modules), before firebase.js.
// =====================================================================
(function () {
  "use strict";
  const App = window.App = window.App || {};

  // The values in foundation.css, for engines that cannot read them (jsdom)
  // or a page without the stylesheet. Kept equal by tests/js/motion-tokens.test.mjs.
  const FALLBACK = {
    press: 120, state: 200, layer: 320, light: 560,
    standard: "cubic-bezier(0.2, 0, 0, 1)",
    out: "cubic-bezier(0.22, 1, 0.36, 1)",
    in: "cubic-bezier(0.4, 0, 1, 1)",
  };

  const reduceQuery = typeof window.matchMedia === "function"
    ? window.matchMedia("(prefers-reduced-motion: reduce)")
    : null;

  function token(name) {
    try {
      return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    } catch (_) {
      return "";
    }
  }

  function ms(name = "state") {
    const raw = token(`--dur-${name}`);
    const match = /^(-?[\d.]+)(ms|s)$/.exec(raw);
    if (match) return Number(match[1]) * (match[2] === "s" ? 1000 : 1);
    return FALLBACK[name] ?? FALLBACK.state;
  }

  function ease(name = "standard") {
    return token(`--ease-${name}`) || FALLBACK[name] || FALLBACK.standard;
  }

  function reduced() {
    return Boolean(reduceQuery?.matches);
  }

  // One pending way out per element: a second leave() (or show()) while
  // the first is still running replaces it instead of firing twice.
  const leaving = new WeakMap();

  function cancelLeave(element) {
    const pending = leaving.get(element);
    if (!pending) return false;
    leaving.delete(element);
    pending.cleanup();
    element.classList.remove(pending.className);
    return true;
  }

  function leave(element, done, { token: durationToken = "state", className = "is-leaving" } = {}) {
    if (!element) { done?.(); return; }
    cancelLeave(element);
    const finish = () => {
      if (leaving.get(element) !== record) return;
      leaving.delete(element);
      record.cleanup();
      element.classList.remove(className);
      done?.();
    };
    const record = { className, cleanup: () => {} };
    leaving.set(element, record);
    element.classList.add(className);
    const style = typeof getComputedStyle === "function" ? getComputedStyle(element) : null;
    const animated = !reduced() && element.isConnected
      && style && /[1-9]/.test(style.transitionDuration || "");
    if (!animated) { finish(); return; }
    // transitionend is the signal; the timer covers a transition that never
    // starts (the element was already in its closed look, or is not drawn).
    const onEnd = event => { if (event.target === element) finish(); };
    const timer = window.setTimeout(finish, ms(durationToken) + 80);
    element.addEventListener("transitionend", onEnd);
    element.addEventListener("transitioncancel", onEnd);
    record.cleanup = () => {
      window.clearTimeout(timer);
      element.removeEventListener("transitionend", onEnd);
      element.removeEventListener("transitioncancel", onEnd);
    };
  }

  // Light and dark change in one step: without it the page flipped at once
  // while sidebar, composer and fields followed over 120-320 ms each.
  function switchTheme(apply) {
    const root = document.documentElement;
    const change = () => {
      root.classList.add("is-theme-switching");
      apply();
      // The new colours are computed while transitions are off.
      void root.offsetWidth;
    };
    const settle = () => {
      requestAnimationFrame(() => requestAnimationFrame(() => root.classList.remove("is-theme-switching")));
    };
    if (!reduced() && typeof document.startViewTransition === "function") {
      try {
        const transition = document.startViewTransition(change);
        transition.finished.then(settle, settle);
        return transition;
      } catch (_) { /* fall through: change in one frame */ }
    }
    change();
    settle();
    return null;
  }

  App.motion = { ms, ease, reduced, leave, cancelLeave, switchTheme, isLeaving: element => leaving.has(element) };
})();
