// =====================================================================
// disclosure.js
// Every <details> in /app opens and closes with the same soft height
// change (Apple audit C11): the sources list, the check details, earlier
// answer versions, the Google cards, the panel rows, the Settings notes.
// "Thought for …" (agent-activity.js) and the Watch settings (watch.js)
// already move their own way; they stop the click (preventDefault) and are
// left alone, as is anything marked data-disclosure="static".
//
// The <details> keeps its native semantics: the toggle event, the open
// attribute and find-in-page work as before; only a pointer or keyboard
// activation of its summary is animated. With "reduce motion" it opens at
// once. App.disclosure.toggle(details, open?) animates from script.
// =====================================================================
(function () {
  "use strict";
  const App = window.App = window.App || {};
  const running = new WeakMap(); // details -> { motion, open } while it moves

  function closedHeight(details, summary) {
    const box = details.getBoundingClientRect();
    const head = summary.getBoundingClientRect();
    const style = getComputedStyle(details);
    return Math.max(0, head.bottom - box.top
      + (parseFloat(style.paddingBottom) || 0) + (parseFloat(style.borderBottomWidth) || 0));
  }

  function stop(details) {
    const current = running.get(details);
    if (!current) return;
    running.delete(details);
    details.classList.remove("is-disclosing");
    current.motion.onfinish = null;
    current.motion.cancel();
  }

  // `open` defaults to the other state than the one it is in or heading for:
  // a second click while it moves turns it round from where it is.
  function toggle(details, open) {
    if (typeof open !== "boolean") open = running.has(details) ? !running.get(details).open : !details.open;
    const summary = details.querySelector(":scope > summary");
    if (!summary || (App.motion?.reduced?.() ?? false) || typeof details.animate !== "function") {
      stop(details);
      details.open = open;
      return;
    }
    const from = details.getBoundingClientRect().height;
    stop(details);
    let to;
    if (open) {
      details.open = true;
      to = details.getBoundingClientRect().height;
    } else {
      to = closedHeight(details, summary);
    }
    if (Math.abs(to - from) < 1) {
      details.open = open;
      return;
    }
    details.classList.add("is-disclosing");
    const motion = details.animate(
      [{ height: `${from}px` }, { height: `${to}px` }],
      {
        duration: App.motion?.ms?.("state") ?? 200,
        easing: App.motion?.ease?.(open ? "out" : "standard") ?? "ease",
      }
    );
    running.set(details, { motion, open });
    motion.onfinish = () => {
      running.delete(details);
      details.classList.remove("is-disclosing");
      if (!open) details.open = false;
    };
  }

  document.addEventListener("click", event => {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const summary = event.target.closest?.("summary");
    const details = summary?.parentElement;
    if (!details || details.tagName !== "DETAILS" || details.querySelector(":scope > summary") !== summary) return;
    if (details.closest("[data-disclosure='static']")) return;
    // A link or a control inside the summary does its own thing.
    const control = event.target.closest("a, button, input, select, textarea, label");
    if (control && summary.contains(control) && control !== summary) return;
    event.preventDefault();
    toggle(details);
  });

  App.disclosure = { toggle };
})();
