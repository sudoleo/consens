// Follow the visible conversation only while the reader stays at its end.
(function () {
  "use strict";
  const App = window.App = window.App || {};
  const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const NEAR_END = 80;
  let context = null, following = false, frame = 0, observer = null, button = null;
  let lastY = window.scrollY, started = null, from = 0;
  let resumeUntil = 0, touchY = null;

  function maxTop() {
    const root = document.scrollingElement || document.documentElement;
    return Math.max(0, root.scrollHeight - window.innerHeight);
  }
  function valid() {
    return context && App.runRegistry?.visible()?.runId === context.runId
      && App.runRegistry.isAuthCurrent(context) && !document.body.classList.contains("is-hero")
      && document.getElementById("watchDashboard")?.hidden !== false;
  }
  function occupied() {
    return document.hidden || !window.getSelection()?.isCollapsed
      || !!document.querySelector('dialog[open]:not(.is-docked)')
      || window.getComputedStyle(document.body).overflowY === "hidden";
  }
  function cancelFrame() {
    if (frame) window.cancelAnimationFrame(frame);
    frame = 0; started = null;
  }
  function syncButton() {
    if (button) button.hidden = !valid() || following || occupied() || maxTop() - window.scrollY <= NEAR_END;
    document.body.classList.toggle("chat-scroll-following", !!valid() && following);
  }
  function pause() {
    following = false;
    resumeUntil = 0;
    cancelFrame();
    syncButton();
  }
  function write(top) {
    // Each frame is immediate; a native smooth scroll must not outlive our cancellation.
    lastY = top;
    window.scrollTo({ top, left: window.scrollX, behavior: "instant" });
  }
  function step(now) {
    frame = 0;
    if (!valid() || !following || occupied()) { pause(); return; }
    const target = maxTop();
    const y = window.scrollY;
    if (target - y <= 1) {
      if (target > y) write(target);
      started = null; syncButton(); return;
    }
    if (motion.matches) { write(target); started = null; syncButton(); return; }
    if (started === null) { started = now; from = y; }
    const progress = Math.min(1, (now - started) / 420);
    const eased = 1 - Math.pow(1 - progress, 3);
    // Re-measure as Markdown, images, the composer or the mobile viewport resize.
    // Never pull upwards when content gets shorter.
    write(Math.max(y, Math.min(target, Math.round(from + (target - from) * eased))));
    if (progress < 1) frame = window.requestAnimationFrame(step);
    else { started = null; syncButton(); }
  }
  function changed() {
    if (!valid()) { pause(); return; }
    syncButton();
    if (following && !frame) frame = window.requestAnimationFrame(step);
  }
  function ensure() {
    const container = document.querySelector(".container");
    const composer = container?.querySelector(".input-section");
    if (!button && composer) {
      button = document.createElement("button");
      button.type = "button"; button.className = "chat-scroll-latest";
      button.textContent = "Latest message ↓";
      button.setAttribute("aria-label", "Scroll to the latest message");
      button.hidden = true;
      button.addEventListener("click", event => {
        sent();
        // Keep keyboard focus usable without opening the mobile keyboard on a tap.
        if (event.detail === 0) document.getElementById("questionInput")?.focus({ preventScroll: true });
        else button.blur();
      });
      composer.append(button);
    }
    if (!observer && container && typeof ResizeObserver === "function") {
      observer = new ResizeObserver(changed);
      observer.observe(container);
    }
  }
  function project(next) {
    const eligible = next && (next.config?.executionMode === "agent" || next.config?.agentMode !== false);
    if (context?.runId !== next?.runId || !eligible) {
      pause();
      context = eligible ? next : null;
      lastY = window.scrollY;
    }
    ensure();
    syncButton();
  }
  function sent() {
    if (!valid()) return;
    cancelFrame();
    following = true;
    syncButton();
    // Let the question clamp, history append and collapsed composer settle first.
    frame = window.requestAnimationFrame(() => {
      frame = window.requestAnimationFrame(step);
    });
  }
  function interrupt(event) {
    if (event.target?.closest?.(".chat-scroll-latest")) return;
    if (event.type === "keydown" && !["ArrowUp", "ArrowDown", "PageUp", "PageDown", "Home", "End", " ", "Tab", "Escape"].includes(event.key)) return;
    if (valid()) {
      pause();
      if (event.type === "touchstart") touchY = event.touches?.[0]?.clientY;
      const towardEnd = (event.type === "wheel" && event.deltaY > 0)
        || (event.type === "keydown" && ["ArrowDown", "PageDown", "End", " "].includes(event.key) && !event.shiftKey)
        || (event.type === "pointerdown" && event.target === document.documentElement);
      if (towardEnd) resumeUntil = performance.now() + 1500;
    }
  }
  ["wheel", "touchstart", "pointerdown", "keydown"].forEach(name => {
    window.addEventListener(name, interrupt, { passive: true, capture: true });
  });
  window.addEventListener("touchmove", event => {
    const y = event.touches?.[0]?.clientY;
    if (valid() && y < touchY) resumeUntil = performance.now() + 1500;
    touchY = y;
  }, { passive: true });
  window.addEventListener("scroll", () => {
    const y = window.scrollY;
    // Only a real downward move back to the end resumes following. Layout
    // shrinkage, an interrupted animation and nested scroll areas cannot do so.
    if (valid() && !frame && performance.now() < resumeUntil && y > lastY
        && maxTop() - y <= NEAR_END && !occupied()) following = true;
    lastY = y;
    syncButton();
  }, { passive: true });
  window.addEventListener("resize", changed, { passive: true });
  window.visualViewport?.addEventListener("resize", changed, { passive: true });
  document.addEventListener("selectionchange", () => { if (!window.getSelection()?.isCollapsed) pause(); });
  document.addEventListener("visibilitychange", () => { if (document.hidden) pause(); });
  window.addEventListener("consensio:run-registry-change", () => { if (!valid()) project(null); });
  App.chatScroll = { project, changed, sent };
})();
