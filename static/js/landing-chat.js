// The landing page as one chat (templates/landing.html, landing-chat.css).
// The scroll position is the playhead: a piece appears once it has cleared
// the docked field, the review plays when the place of its note has come
// into view, and the Watch card starts as it comes up the page.
//
// The page is whole without this script: landing-chat.css draws every piece
// in its last frame and takes the states before it only under .lc-js, which
// this script sets. Under reduced motion it does not set it; only the docked
// field still takes its two forms, without the glide between them.
(function () {
  "use strict";

  // A short piece (a heading, a bubble) shows once all of it stands above
  // the docked field; a tall one once its first lines do.
  const FIRST_LINES = 110;
  function standsClear(top, height, line) {
    return top + Math.min(height, FIRST_LINES) <= line;
  }

  // The Watch card along the scroll: its proposal, the Start button pressed,
  // then the running Watch.
  function watchState(progress) {
    return progress < 0.4 ? "proposal" : progress < 0.62 ? "pressing" : "watching";
  }

  window.LandingChat = { standsClear, watchState };

  // The two ways into the app from this page: with the mark set, the app
  // skips its redirect back to the landing page.
  ["landingField", "navCtaButton"].forEach(id => {
    const link = document.getElementById(id);
    if (!link) return;
    link.addEventListener("click", () => {
      sessionStorage.setItem("skipLandingRedirect", "1");
      if (id === "navCtaButton") window.umami?.track?.("landing_nav_open_app");
    });
  });

  const reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (!("IntersectionObserver" in window)) return;

  // ---- the docked field ------------------------------------------------------
  // One row high while it rides along, as the composer of /app, and two rows
  // under the last line of the page (.is-end; landing-chat.css draws both).
  // A reader who asked for less motion gets the two forms without the glide.
  const dock = document.querySelector(".lc-dock");
  const field = document.getElementById("landingField");
  const rest = document.querySelector(".lc-dock-rest");
  const PARTS = ".lp-composer-text, .lp-icon-btn, .lp-composer-models, .lp-run-chip, .lp-send";
  // What the one-row field takes at the foot of the window.
  let under = dock ? dock.offsetHeight : 0;
  // The room the two rows take beyond the one: the dock keeps it above the
  // one-row field (--lc-rise), so the change of form moves nothing else.
  function measureDock() {
    const end = dock.classList.contains("is-end");
    dock.classList.remove("is-end");
    dock.style.setProperty("--lc-rise", "0px");
    const low = field.getBoundingClientRect().height;
    under = dock.offsetHeight;
    dock.classList.add("is-end");
    const rise = Math.max(0, field.getBoundingClientRect().height - low);
    dock.classList.toggle("is-end", end);
    dock.style.setProperty("--lc-rise", `${rise.toFixed(2)}px`);
  }
  function setForm(end, glide) {
    if (dock.classList.contains("is-end") === end) return;
    const parts = glide ? [field, ...field.querySelectorAll(PARTS)] : [];
    const first = parts.map(el => el.getBoundingClientRect());
    dock.classList.toggle("is-end", end);
    if (!parts.length) return;
    // Every part is in its new place at once. It is put back where it
    // stood, without a transition, and let go in the next frame.
    field.classList.add("is-placing");
    parts.forEach((el, n) => {
      const last = el.getBoundingClientRect();
      if (el === field) field.style.setProperty("--lc-from", `${(first[n].top - last.top).toFixed(1)}px`);
      // A part one of the forms does not draw has no place to come from.
      else if (first[n].width && last.width) {
        el.style.translate = `${(first[n].left - last.left).toFixed(1)}px ${(first[n].top - last.top).toFixed(1)}px`;
      }
    });
    void field.offsetHeight;
    window.requestAnimationFrame(() => {
      field.classList.remove("is-placing");
      field.style.removeProperty("--lc-from");
      parts.forEach(el => { if (el !== field) el.style.translate = ""; });
    });
  }
  if (dock && field && rest) {
    measureDock();
    let placed = false;
    new IntersectionObserver(entries => {
      const entry = entries[entries.length - 1];
      // At rest also when the reader has gone on into the footer. The first
      // word says where the visit starts: there is no change to watch.
      setForm(entry.isIntersecting || entry.boundingClientRect.top < 0, placed && !reduced);
      placed = true;
    }).observe(rest);
    window.addEventListener("resize", measureDock);
    window.addEventListener("load", measureDock);
  }

  if (reduced) return;

  const root = document.documentElement;
  const reveals = Array.from(document.querySelectorAll("[data-reveal]"));
  const clamp = value => Math.min(1, Math.max(0, value));
  // Where the docked field begins: what stands above it is in view.
  const line = () => window.innerHeight - under - 24;

  // ---- the review ----------------------------------------------------------
  // Played once, on a clock, because it is a thing that happens: the
  // reviewers read (a sheen over the plan), then their finding is there.
  // landing-chat.css draws each phase and the order in which the pieces of
  // "found" arrive (the days step back, the mark, the note).
  const READING_MS = 1150;
  // The correction comes after the finding has landed.
  const SETTLE_MS = 1500;
  const reviews = Array.from(document.querySelectorAll("[data-review]")).map(el => ({
    el, plan: el.querySelector(".lc-claims"), note: el.querySelector(".lc-note"),
    room: el.querySelector(".lc-note-row"), played: false,
  }));
  // The room the note takes in the plan: until it shows, the days after it
  // are moved up by this much.
  function measure(view) {
    view.plan.style.setProperty("--note-room", `${view.room.getBoundingClientRect().height.toFixed(1)}px`);
  }
  function play(view) {
    view.played = true;
    view.el.dataset.phase = "reviewing";
    view.plan.classList.add("is-reviewing");
    window.setTimeout(() => {
      view.plan.classList.remove("is-reviewing");
      view.el.dataset.phase = "found";
      window.setTimeout(() => {
        view.el.dataset.settled = "true";
        held(view.el).forEach(el => revealer.observe(el));
        wake();
      }, SETTLE_MS);
    }, READING_MS);
  }
  // Left behind unseen (a jump down the page, a visit that starts below
  // it): nobody watches the clock, so it stands in its last frame at once
  // and is whole when the reader scrolls back up to it.
  function finish(view) {
    view.played = true;
    view.el.dataset.phase = "found";
    view.el.dataset.settled = "true";
    held(view.el).forEach(el => revealer.observe(el));
  }
  // What the agent does about a finding waits for the finding.
  const held = review => reveals.filter(el => el.hasAttribute("data-after-review") && review.contains(el));

  const watches = Array.from(document.querySelectorAll("[data-watch]"));

  root.classList.add("lc-js");
  reviews.forEach(view => { view.el.dataset.phase = "plain"; measure(view); });
  watches.forEach(card => { card.dataset.state = "proposal"; });

  // ---- pieces that appear ------------------------------------------------------
  // An observer says which pieces have come into the window, and while one
  // of them has not cleared the field its box is read every frame. Neither
  // alone would do: a phone delivers scroll events late while the page
  // glides, so the pieces would come in behind the finger, and an observer
  // never reports its last threshold for a piece a fraction of a pixel
  // short of it, which then stays unseen.
  let revealer = null;
  const arriving = new Set();
  function show(el) {
    el.classList.add("is-in");
    arriving.delete(el);
    revealer.unobserve(el);
  }
  function settle() {
    if (!arriving.size) return;
    const edge = line();
    arriving.forEach(el => {
      const box = el.getBoundingClientRect();
      if (standsClear(box.top, box.height, edge)) show(el);
    });
  }
  function onReveal(entries) {
    entries.forEach(entry => {
      // Above the window (a visit that starts further down): it is there.
      const passed = !entry.isIntersecting && entry.rootBounds
        && entry.boundingClientRect.bottom <= entry.rootBounds.top;
      if (passed) show(entry.target);
      else if (entry.isIntersecting) arriving.add(entry.target);
      else arriving.delete(entry.target);
    });
    settle();
    wake();
  }
  function watchReveals() {
    if (revealer) revealer.disconnect();
    arriving.clear();
    const under = Math.round(window.innerHeight - line());
    revealer = new IntersectionObserver(onReveal, { rootMargin: `0px 0px -${under}px 0px` });
    reveals.forEach(el => {
      if (el.classList.contains("is-in")) return;
      const review = el.hasAttribute("data-after-review") && el.closest("[data-review]");
      if (review && review.dataset.settled !== "true") return;
      revealer.observe(el);
    });
  }

  // ---- pieces the scroll moves ----------------------------------------------
  const near = new Set();
  function drive() {
    const edge = line();
    const height = window.innerHeight;
    reviews.forEach(view => {
      if (view.played) return;
      if (view.el.getBoundingClientRect().bottom <= 0) finish(view);
      // Not before the place of the note stands in view: the finding is
      // what the reader is to see arrive.
      else if (near.has(view.el) && view.note.getBoundingClientRect().bottom < edge + 12) play(view);
    });
    if (!near.size) return;
    watches.forEach(card => {
      // It starts once the whole card has stood in view for a moment of
      // scrolling, and goes back with the scroll.
      const state = watchState(clamp((edge - card.getBoundingClientRect().bottom) / (height * 0.2)));
      if (card.dataset.state !== state) card.dataset.state = state;
    });
  }
  const driver = new IntersectionObserver(entries => {
    entries.forEach(entry => { if (entry.isIntersecting) near.add(entry.target); else near.delete(entry.target); });
    // Once more as a piece leaves, so it rests where the scroll left it.
    if (!near.size) { near.add(entries[0].target); drive(); near.clear(); } else drive();
    wake();
  }, { rootMargin: "20% 0px 20% 0px" });

  // ---- the frames --------------------------------------------------------------
  // Boxes are read every frame only while a piece is arriving or the scroll
  // moves one, and only while the page moves: a page at rest costs nothing.
  const REST_FRAMES = 12;
  let running = false;
  let rested = 0;
  let lastY = -1;
  function frame() {
    rested = window.scrollY === lastY ? rested + 1 : 0;
    lastY = window.scrollY;
    settle();
    drive();
    if ((arriving.size || near.size) && rested < REST_FRAMES) window.requestAnimationFrame(frame);
    else running = false;
  }
  function wake() {
    rested = 0;
    if (running) return;
    running = true;
    window.requestAnimationFrame(frame);
  }
  window.addEventListener("scroll", wake, { passive: true });

  reviews.forEach(view => driver.observe(view.el));
  watches.forEach(card => driver.observe(card));

  watchReveals();
  // The field's height and the note's room change with the window's width.
  function relayout() {
    reviews.forEach(measure);
    watchReveals();
  }
  window.addEventListener("resize", relayout);
  window.addEventListener("load", relayout);
})();
