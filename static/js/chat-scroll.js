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
  // A place to return to instead of the newest question (app-update.js,
  // after loading a new build): read again in each frame of the settle.
  let pendingPlace = null, place = null;
  function placeTop() {
    const top = place?.();
    return Number.isFinite(top) ? Math.max(0, Math.round(top)) : null;
  }

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
  //
  // The layout keeps that space, not a measurement after the fact (since
  // 2026-10-30): the column holds a minimum height that ends the page one
  // viewport below the scroll offset that puts the question at the top, and
  // the reserve (flex-grow, chat-scroll.css) takes whatever the turn leaves
  // of it, in the same layout. Until then the reserve's own height followed
  // the turn from a ResizeObserver: a turn that got shorter at the end of the
  // page, where Send leaves every later question, first shortened the page
  // for one layout, the browser clamped the scroll offset, and the whole chat
  // jumped by that much and back (Max, 2026-10-30: a live line going from two
  // lines to one, 21px; the phone's composer folding after Send, 151px).
  // A turn taller than the window still never gets shorter while its run
  // works: the reviewers finish while the reader types the next question,
  // and their row (or the live lines leaving) took a line from the end of the
  // page, which pulled the chat down under the reader's eyes. The tallest
  // column of the run holds until the next run, chat or window size.
  let floor = "", peak = 0;
  // The turn's own height: the column without the room the reserve fills.
  // The column alone holds its floor, and a floor measured into the next
  // floor would never let go.
  function contentHeight(bounds) {
    const room = reserve?.isConnected ? reserve.getBoundingClientRect() : null;
    return bounds.bottom - bounds.top - (room ? room.bottom - room.top : 0);
  }
  function updateReserve() {
    const column = container();
    if (!column) return;
    if (!reserve) {
      reserve = document.createElement("div");
      reserve.className = "chat-scroll-reserve";
      reserve.setAttribute("aria-hidden", "true");
      // A turn above that changes moves the question without changing the
      // column's height (the reserve gives way): the reserve's own size says so.
      observer?.observe(reserve);
    }
    if (reserve.parentNode !== column) column.append(reserve);
    const question = head();
    let next = "";
    if (question && !document.body.classList.contains("is-hero") && column.getClientRects().length) {
      // What follows the column in the body, measured in layout pixels. Not
      // via scrollHeight: that is rounded, so a fractional layout (a question
      // at 292.625px) swapped the page height by 1px every frame.
      const bounds = column.getBoundingClientRect();
      const after = Math.max(0, document.body.getBoundingClientRect().bottom - bounds.bottom)
        + (parseFloat(window.getComputedStyle(document.body).marginBottom) || 0);
      const head = question.getBoundingClientRect().top + window.scrollY - landing(question);
      // The page ends one viewport below headTop (a whole pixel), whatever the
      // turn's height and fraction (20.8px lines), down to the layout's own
      // unit (1/64px): a floor a fraction too tall would scroll by that fraction.
      const height = Math.floor((Math.round(head) + window.innerHeight - after - (bounds.top + window.scrollY)) * 64) / 64;
      if (context?.runId && App.runRegistry?.isExecuting?.(context.runId)) peak = Math.max(peak, contentHeight(bounds));
      // The column's own floor (shell.css) still holds on a short page.
      next = `max(calc(100dvh - 10px), ${Math.max(0, height, peak)}px)`;
    }
    if (next !== floor) {
      floor = next;
      column.style.minHeight = next;
    }
  }
  function contentEnd() {
    return reserve?.isConnected ? reserve.getBoundingClientRect().bottom + window.scrollY : null;
  }
  function cancelFrame() {
    if (frame) window.cancelAnimationFrame(frame);
    frame = 0; started = null;
  }
  // "Latest message" comes once the end stays out of reach a moment and by
  // more than the near-end band; it goes at once. Live lines that grow and
  // fold during a run made it flash on and off (2026-10-28). Just out of
  // reach (up to SHOW_FAR) the wait ends; the next scroll or layout change
  // starts it again, instead of a check in every frame while idle.
  const SHOW_FAR = 160, SHOW_AFTER_MS = 500;
  let farSince = null, showFrame = 0;
  function away() { return !valid() || !!jump || occupied() || maxTop() - window.scrollY <= NEAR_END; }
  function syncButton() {
    if (button) {
      if (away()) { button.hidden = true; farSince = null; }
      else if (button.hidden && !showFrame) showFrame = window.requestAnimationFrame(showWhenFar);
    }
    document.body.classList.toggle("chat-scroll-following", !!valid() && !!jump);
  }
  function showWhenFar(now) {
    showFrame = 0;
    if (!button || !button.hidden) return;
    if (away() || maxTop() - window.scrollY <= SHOW_FAR) { farSince = null; return; }
    if (farSince === null) farSince = now;
    if (now - farSince >= SHOW_AFTER_MS) { button.hidden = false; farSince = null; return; }
    showFrame = window.requestAnimationFrame(showWhenFar);
  }
  function pause() {
    jump = null;
    place = null;
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
      // Growth above the reader that the run's floor took into the reserve
      // below: the floor grows with it, or the page could not follow and the
      // text in view would move down by that much.
      const missing = y + shift - maxTop();
      if (peak && missing > 0) {
        peak = Math.max(peak, contentHeight(container().getBoundingClientRect())) + missing;
        updateReserve();
      }
      const target = Math.max(0, Math.min(maxTop(), y + shift));
      if (Math.abs(target - window.scrollY) > .5) write(target);
      syncButton();
    };
  }
  function finish() {
    jump = null; started = null; place = null; syncButton();
  }
  // How long an opened conversation keeps its newest question in place while
  // late layout settles (fonts, marks, the activity line, file rows).
  const OPEN_SETTLE_MS = 600;
  function step(now) {
    frame = 0;
    if (!valid() || !jump || occupied()) { pause(); return; }
    updateReserve();
    if (jump === "open") {
      // No ride: the position is written as it is, in every frame of the
      // short settle, and only when the question actually moved.
      const target = Math.min(placeTop() ?? headTop() ?? maxTop(), maxTop());
      if (Math.abs(target - window.scrollY) > .5) write(target);
      if (started === null) started = now;
      if (now - started < OPEN_SETTLE_MS) frame = window.requestAnimationFrame(step);
      else finish();
      return;
    }
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
      if (reserve) observer.observe(reserve);
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
      peak = 0;
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
  // The phone menu goes with the tap that chose a chat, not once it loaded.
  function closeMenu() {
    if (window.innerWidth < 1100 && document.querySelector('.sidebar.active')) {
      document.getElementById('sidebarToggleInner')?.click();
    }
  }
  // An opened conversation stands at its newest question before its first
  // frame (Apple audit A2/A3): no ride from the top through every answer,
  // and on a phone the question is never left under the floating header,
  // as it was at the absolute end. Only "Latest message" and Send move.
  function opened() {
    // A second call while a returned-to place still settles keeps it.
    const held = jump === "open" ? place : null;
    closeMenu();
    project(App.runRegistry?.visible());
    if (!valid() || occupied()) return;
    cancelFrame();
    jump = "open";
    destination = null;
    place = pendingPlace || held;
    pendingPlace = null;
    updateReserve();
    const target = Math.min(placeTop() ?? headTop() ?? maxTop(), maxTop());
    if (Math.abs(target - window.scrollY) > .5) write(target);
    started = window.performance.now();
    syncButton();
    frame = window.requestAnimationFrame(step);
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
  let width = window.innerWidth;
  window.addEventListener("resize", () => {
    // Another width sets the turn anew; the phone's keyboard does not.
    if (window.innerWidth !== width) { width = window.innerWidth; peak = 0; }
    changed();
  }, { passive: true });
  window.visualViewport?.addEventListener("resize", changed, { passive: true });
  document.addEventListener("selectionchange", () => { if (!window.getSelection()?.isCollapsed) pause(); });
  document.addEventListener("visibilitychange", () => { if (document.hidden) pause(); });
  window.addEventListener("consensio:run-registry-change", () => { if (!valid()) project(null); else changed(); });
  // The next opened() returns to this place (a function giving the scroll
  // offset) instead of the newest question; once, then as usual.
  function returnTo(where) { pendingPlace = typeof where === "function" ? where : null; }
  App.chatScroll = { project, changed, sent, opened, closeMenu, latest: () => start("latest"), preserveAbove, returnTo };
})();
