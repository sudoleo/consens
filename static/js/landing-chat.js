// The landing page as one chat (templates/landing.html, landing-chat.css).
// The scroll position is the playhead: a piece appears once it has cleared
// the docked field, the review plays when the place of its note has come
// into view, and the Watch card starts as it comes up the page.
//
// The page is whole without this script: landing-chat.css draws every piece
// in its last frame and takes the states before it only under .lc-js, which
// this script sets. Under reduced motion it sets nothing.
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
  if (reduced || !("IntersectionObserver" in window)) return;

  const root = document.documentElement;
  const dock = document.querySelector(".lc-dock");
  const reveals = Array.from(document.querySelectorAll("[data-reveal]"));
  const clamp = value => Math.min(1, Math.max(0, value));
  // Where the docked field begins: what stands above it is in view.
  const line = () => window.innerHeight - (dock ? dock.offsetHeight : 0) - 24;

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
      }, SETTLE_MS);
    }, READING_MS);
  }
  // What the agent does about a finding waits for the finding.
  const held = review => reveals.filter(el => el.hasAttribute("data-after-review") && review.contains(el));

  const watches = Array.from(document.querySelectorAll("[data-watch]"));

  root.classList.add("lc-js");
  reviews.forEach(view => { view.el.dataset.phase = "plain"; measure(view); });
  watches.forEach(card => { card.dataset.state = "proposal"; });

  // ---- pieces that appear ------------------------------------------------------
  // An observer, not a scroll listener: a phone delivers scroll events late
  // while the page glides, and the pieces would come in behind the finger.
  let revealer = null;
  function onReveal(entries) {
    const edge = line();
    entries.forEach(entry => {
      const box = entry.boundingClientRect;
      // Above the window (a visit that starts further down): it is there.
      const passed = !entry.isIntersecting && entry.rootBounds && box.bottom <= entry.rootBounds.top;
      if (passed || (entry.isIntersecting && standsClear(box.top, box.height, edge))) {
        entry.target.classList.add("is-in");
        revealer.unobserve(entry.target);
      }
    });
  }
  function watchReveals() {
    if (revealer) revealer.disconnect();
    const under = Math.round(window.innerHeight - line());
    revealer = new IntersectionObserver(onReveal, {
      rootMargin: `0px 0px -${under}px 0px`,
      threshold: [0, 0.25, 0.5, 0.75, 1],
    });
    reveals.forEach(el => {
      if (el.classList.contains("is-in")) return;
      const review = el.hasAttribute("data-after-review") && el.closest("[data-review]");
      if (review && review.dataset.settled !== "true") return;
      revealer.observe(el);
    });
  }

  // ---- pieces the scroll moves ----------------------------------------------
  // Read every frame, but only while one of them is near the window.
  const near = new Set();
  let running = false;
  function drive() {
    const edge = line();
    const height = window.innerHeight;
    reviews.forEach(view => {
      // Not before the place of the note stands in view: the finding is
      // what the reader is to see arrive.
      if (!view.played && view.note.getBoundingClientRect().bottom < edge + 12) play(view);
    });
    watches.forEach(card => {
      // It starts once the whole card has stood in view for a moment of
      // scrolling, and goes back with the scroll.
      const state = watchState(clamp((edge - card.getBoundingClientRect().bottom) / (height * 0.2)));
      if (card.dataset.state !== state) card.dataset.state = state;
    });
  }
  function frame() {
    if (!near.size) { running = false; return; }
    drive();
    window.requestAnimationFrame(frame);
  }
  const driver = new IntersectionObserver(entries => {
    entries.forEach(entry => { if (entry.isIntersecting) near.add(entry.target); else near.delete(entry.target); });
    // Once more as a piece leaves, so it rests where the scroll left it.
    drive();
    if (near.size && !running) { running = true; window.requestAnimationFrame(frame); }
  }, { rootMargin: "20% 0px 20% 0px" });
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
