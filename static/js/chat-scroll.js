// Conversation scrolling like ChatGPT/Claude: Send moves the new question to
// the top once, the answer grows into reserved space below it, and nothing
// scrolls on its own while text streams, checks arrive or a run ends.
(function () {
  "use strict";
  const App = window.App = window.App || {};
  const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const NEAR_END = 80;
  let context = null, frame = 0, observer = null, button = null, reserve = null;
  let started = null, from = 0;
  // "head": the current question to the top; "end": the end of the thread;
  // "latest": the end of the content as it was when "Latest message" was pressed.
  let jump = null, destination = null;

  function container() { return document.querySelector(".container"); }
  function maxTop() {
    const root = document.scrollingElement || document.documentElement;
    return Math.max(0, root.scrollHeight - window.innerHeight);
  }
  function valid() {
    const selected = context?.bookmarkId
      ? !App.runRegistry?.visible() && App.runRegistry?.getSelectedConversationIdentity?.()?.bookmarkId === context.bookmarkId
      : context && App.runRegistry?.visible()?.runId === context.runId;
    return selected
      && App.runRegistry.isAuthCurrent(context) && !document.body.classList.contains("is-hero")
      && document.getElementById("watchDashboard")?.hidden !== false;
  }
  function occupied() {
    return document.hidden || !window.getSelection()?.isCollapsed
      || !!document.querySelector('dialog[open]:not(.is-docked)')
      || window.getComputedStyle(document.body).overflowY === "hidden";
  }
  // The question that heads the newest turn (the pending bubble while a
  // follow-up has not been promoted yet).
  function head() {
    for (const id of ["threadPendingAsk", "threadAsk"]) {
      const element = document.getElementById(id);
      if (element && !element.hidden && element.getClientRects().length) return element;
    }
    return null;
  }
  // The question lands where a first question sits on an unscrolled page:
  // below the column's top padding and its own top margin.
  function landing(question) {
    const column = container();
    if (!column) return 0;
    return column.getBoundingClientRect().top + window.scrollY
      + (parseFloat(window.getComputedStyle(column).paddingTop) || 0)
      + (parseFloat(window.getComputedStyle(question).marginTop) || 0);
  }
  function headTop() {
    const element = head();
    return element ? Math.max(0, Math.round(element.getBoundingClientRect().top + window.scrollY - landing(element))) : null;
  }
  // Space below the newest turn, so its question can reach the top while the
  // answer is still short. The answer, its evidence row and late files fill
  // this space instead of lengthening the page: nothing above or on screen
  // moves, and the page only grows once the turn is taller than the viewport.
  function updateReserve() {
    const column = container();
    if (!column) return;
    if (!reserve) {
      reserve = document.createElement("div");
      reserve.className = "chat-scroll-reserve";
      reserve.setAttribute("aria-hidden", "true");
    }
    if (reserve.parentNode !== column) column.append(reserve);
    const question = head();
    let height = 0;
    if (question && !document.body.classList.contains("is-hero") && column.getClientRects().length) {
      const style = window.getComputedStyle(column);
      const composer = column.querySelector(".input-section");
      const inFlow = composer && window.getComputedStyle(composer).position !== "fixed";
      // What follows the column in the body, measured in layout pixels. Not
      // via scrollHeight: that is rounded and includes the reserve itself, so
      // a fractional layout (a question at 292.625px) made the reserve and the
      // page height swap 1px every frame, and the scrollbar flickered.
      const after = Math.max(0, document.body.getBoundingClientRect().bottom - column.getBoundingClientRect().bottom)
        + (parseFloat(window.getComputedStyle(document.body).marginBottom) || 0);
      const below = (parseFloat(style.paddingBottom) || 0) + (inFlow ? composer.offsetHeight : 0) + after;
      const turn = reserve.getBoundingClientRect().top - question.getBoundingClientRect().top;
      // Rounded down: a reserve a fraction too tall makes the page scroll by
      // that fraction. A fraction short is filled by the column's minimum
      // height on a one-viewport page; on later turns the question lands
      // under a pixel lower, unseen.
      height = Math.max(0, Math.floor(window.innerHeight - landing(question) - turn - below));
    }
    const current = parseFloat(reserve.style.height) || 0;
    if (Math.abs(current - height) >= 1) reserve.style.height = `${height}px`;
  }
  function contentEnd() {
    return reserve?.isConnected ? reserve.getBoundingClientRect().bottom + window.scrollY : null;
  }
  function cancelFrame() {
    if (frame) window.cancelAnimationFrame(frame);
    frame = 0; started = null;
  }
  function syncButton() {
    if (button) button.hidden = !valid() || !!jump || occupied() || maxTop() - window.scrollY <= NEAR_END;
    document.body.classList.toggle("chat-scroll-following", !!valid() && !!jump);
  }
  function pause() {
    jump = null;
    cancelFrame();
    syncButton();
  }
  function write(top) {
    // Each frame is immediate; a native smooth scroll must not outlive our cancellation.
    window.scrollTo({ top, left: window.scrollX, behavior: "instant" });
  }
  function preserveAbove(element, anchor = null) {
    if (!element?.isConnected || !valid() || occupied() || window.scrollY <= 0) return null;
    const bounds = element.getBoundingClientRect();
    if (bounds.bottom > 0) return null;
    // The next content edge includes collapsing margins outside the activity.
    const position = () => (anchor?.isConnected ? anchor.getBoundingClientRect().top : element.getBoundingClientRect().bottom) + window.scrollY;
    const y = window.scrollY, before = position(), owner = context;
    cancelFrame();
    return () => {
      if (!element.isConnected || context !== owner || !valid()) return;
      // Use document coordinates so native scroll anchoring, if it already ran,
      // cannot double the correction. Preserve the same text in the viewport.
      const shift = position() - before;
      const target = Math.max(0, Math.min(maxTop(), y + shift));
      if (Math.abs(target - window.scrollY) > .5) write(target);
      syncButton();
    };
  }
  function finish() {
    jump = null; started = null; syncButton();
  }
  function step(now) {
    frame = 0;
    if (!valid() || !jump || occupied()) { pause(); return; }
    updateReserve();
    // Re-measured every frame: the question settles, history is appended and
    // the composer collapses while the jump runs.
    // "Latest message" keeps the content end it was pressed for in view: text
    // streaming in meanwhile must not stretch the jump into following, while
    // a composer that grows (focus on narrow screens) still moves the end.
    let goal = jump === "head" ? headTop() ?? maxTop() : maxTop();
    if (jump === "latest") {
      const end = contentEnd();
      if (destination === null) destination = end;
      if (end !== null && destination !== null) goal = maxTop() - (end - destination);
    }
    const target = Math.min(goal, maxTop());
    const y = window.scrollY;
    if (Math.abs(target - y) <= 1 || motion.matches) {
      if (Math.abs(target - y) > .5) write(target);
      finish(); return;
    }
    if (started === null) { started = now; from = y; }
    const progress = Math.min(1, (now - started) / 420);
    const eased = 1 - Math.pow(1 - progress, 3);
    write(Math.round(from + (target - from) * eased));
    if (progress < 1) frame = window.requestAnimationFrame(step);
    else finish();
  }
  function changed() {
    updateReserve();
    if (!valid()) { pause(); return; }
    syncButton();
  }
  function ensure() {
    const column = container();
    const composer = column?.querySelector(".input-section");
    if (!button && composer) {
      button = document.createElement("button");
      button.type = "button"; button.className = "chat-scroll-latest";
      button.innerHTML = '<svg class="chat-scroll-latest-icon" viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="M10 4v12m-4.5-4.5L10 16l4.5-4.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg><span>Latest message</span>';
      button.setAttribute("aria-label", "Scroll to the latest message");
      button.hidden = true;
      button.addEventListener("click", event => {
        start("latest");
        // Keep keyboard focus usable without opening the mobile keyboard on a tap.
        if (event.detail === 0) document.getElementById("questionInput")?.focus({ preventScroll: true });
        else button.blur();
      });
      composer.append(button);
    }
    if (!observer && column && typeof ResizeObserver === "function") {
      observer = new ResizeObserver(changed);
      observer.observe(column);
    }
    updateReserve();
  }
  function project(next) {
    if (!next && !App.runRegistry?.visible()) {
      const basis = App.runRegistry?.getSelectedConversationIdentity?.();
      if (basis?.bookmarkId) next = {
        bookmarkId: basis.bookmarkId,
        auth: { user: window.auth?.currentUser, uid: window.auth?.currentUser?.uid, generation: App.authState?.generation },
        config: { executionMode: basis.executionMode, agentMode: !document.body.classList.contains('direct-comparison-active') }
      };
    }
    const eligible = next && (next.config?.executionMode === "agent" || next.config?.agentMode !== false);
    if (context?.runId !== next?.runId || context?.bookmarkId !== next?.bookmarkId
        || context?.auth?.generation !== next?.auth?.generation || !eligible) {
      pause();
      context = eligible ? next : null;
    }
    ensure();
    syncButton();
  }
  // One explicit, cancellable jump. Streaming, review and completion never
  // start one; only Send, "Latest message" and opening a conversation do.
  function start(kind) {
    if (!valid()) return;
    cancelFrame();
    jump = kind;
    destination = null;
    syncButton();
    // Let the question, history append and collapsed composer settle first.
    frame = window.requestAnimationFrame(() => {
      frame = window.requestAnimationFrame(step);
    });
  }
  function sent() { start("head"); }
  function opened() {
    if (window.innerWidth < 1100 && document.querySelector('.sidebar.active')) {
      document.getElementById('sidebarToggleInner')?.click();
    }
    project(App.runRegistry?.visible());
    start("end");
  }
  function interrupt(event) {
    if (event.target?.closest?.(".chat-scroll-latest")) return;
    if (event.type === "keydown" && !["ArrowUp", "ArrowDown", "PageUp", "PageDown", "Home", "End", " ", "Tab", "Escape"].includes(event.key)) return;
    if (jump) pause();
  }
  ["wheel", "touchstart", "pointerdown", "keydown"].forEach(name => {
    window.addEventListener(name, interrupt, { passive: true, capture: true });
  });
  window.addEventListener("scroll", syncButton, { passive: true });
  window.addEventListener("resize", changed, { passive: true });
  window.visualViewport?.addEventListener("resize", changed, { passive: true });
  document.addEventListener("selectionchange", () => { if (!window.getSelection()?.isCollapsed) pause(); });
  document.addEventListener("visibilitychange", () => { if (document.hidden) pause(); });
  window.addEventListener("consensio:run-registry-change", () => { if (!valid()) project(null); else changed(); });
  App.chatScroll = { project, changed, sent, opened, latest: () => start("latest"), preserveAbove };
})();
