// =====================================================================
// landing-scenes.js
// Scroll-scrubbed product scenes on the landing page.
//
// The premise: a marketing mockup that loops on a timer is decoration.
// A mockup whose playhead IS the scroll position is a demonstration —
// the reader sets the pace, can hold a phase still, and can scrub back
// to re-read it. So scenes 01 and 02 pin their stage while the section
// scrolls past, and every frame is derived from one number: how far
// through the section you are.
//
// Both scenes render the real /app surfaces: the composer, and an Agent
// turn as agent-activity.js and agent-review.js draw it. The status words,
// the steps and the evidence row are the same ones the product uses, so
// the page cannot quietly drift away from it.
//
// Reduced motion (or no IntersectionObserver): every scene is rendered
// at its end state once and never touched again.
// =====================================================================

(function () {
  "use strict";

  const reducedMotion = window.matchMedia
    && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

  // Progress of `value` through the window [from, to], clamped to 0..1.
  const span = (value, from, to) => clamp((value - from) / (to - from), 0, 1);

  // ---- Scene 01: Ask --------------------------------------------------

  // Dieselbe Frage, die /app?demo=1 tippt (static/demo.js): Wer aus dem Hero
  // in die Demo springt, sieht dort weiter, was hier anfaengt. Nur die erste
  // Zeile — der Nachrichtenentwurf wird auch in der App eingefuegt, nicht
  // getippt.
  const ASK_QUESTION = "Can a heat pump heat our 1978 house with the original radiators?";

  function buildAskScene(scene) {
    const text = scene.querySelector("[data-ask-text]");
    const composer = scene.querySelector("[data-ask-composer]");
    const chip = scene.querySelector("[data-ask-chip]");
    const send = scene.querySelector("[data-ask-send]");
    const tools = scene.querySelector(".lp-composer-tools");
    const notes = Array.from(scene.querySelectorAll("[data-ask-note]"));
    if (!text || !composer) return null;

    let lastChars = -1;
    let lastStep = -1;

    // The question wraps to more lines as it is typed, and on a narrow screen
    // that grows the field — which grows the scene, which is what the scroll
    // progress is measured against. So the field is given the height of the
    // FINISHED question up front and never changes size while typing.
    function remeasureAsk() {
      text.style.minHeight = "";
      const previous = text.textContent;
      text.textContent = ASK_QUESTION;
      const full = text.offsetHeight;
      text.textContent = previous;
      if (full) text.style.minHeight = full + "px";
    }

    remeasureAsk();
    renderAsk.remeasure = remeasureAsk;

    function renderAsk(p) {
      // 0.08 → 0.58 types the question. Because the character count is a
      // pure function of scroll, scrubbing back un-types it rather than
      // restarting a timer somewhere else.
      const typed = span(p, 0.08, 0.58);
      const chars = Math.round(typed * ASK_QUESTION.length);
      if (chars !== lastChars) {
        text.textContent = ASK_QUESTION.slice(0, chars);
        lastChars = chars;
      }
      // The caret shows while there is still something to type.
      text.classList.toggle("is-typing", p > 0.04 && typed < 1);

      // Once there is a question, the composer is live: field focused,
      // then the run switch, then send.
      composer.classList.toggle("is-active", typed > 0.02);
      if (chip) chip.classList.toggle("is-lit", p >= 0.62 && p < 0.78);
      if (send) {
        send.classList.toggle("is-ready", typed >= 1);
        send.classList.toggle("is-pressed", p >= 0.9);
      }
      // Agent Mode hides the starting toolbar after send, as in /app. Keep
      // its layout slot so scrolling backwards has a stable progress range.
      if (tools) {
        tools.classList.toggle("is-sent", p >= 0.9);
        tools.setAttribute("aria-hidden", String(p >= 0.9));
      }

      // The three notes step through in time with the controls above them.
      const step = p < 0.62 ? 0 : (p < 0.78 ? 1 : 2);
      if (step !== lastStep) {
        notes.forEach((note, i) => {
          note.classList.toggle("is-active", i === step);
          note.classList.toggle("is-done", i < step);
        });
        lastStep = step;
      }
    }

    return renderAsk;
  }

  // ---- Scene 02: Run --------------------------------------------------

  // One Agent turn, on the same surfaces agent-activity.js and
  // agent-review.js draw in /app: a note on the plan, the comparison with
  // the six models landing one by one, the answer written in its own step,
  // the check on that exact text, then the marks and the evidence row. The
  // comparison owns the longest stretch, as it does in a real run.
  const PLAN_AT = 0.05;
  const COMPARE_AT = 0.13;
  const COMPARE_END = 0.54;
  const COMPARED_AT = 0.57;
  const WRITE_AT = 0.61;
  const CHECK_AT = 0.80;
  const DONE_AT = 0.91;
  const RUN_SECONDS = 24;

  // Where each model lands inside the comparison. A run is only as fast as
  // its slowest model, so the spread is deliberate.
  const MODEL_FINISH = [0.30, 0.42, 0.55, 0.66, 0.82, 1.0];

  function buildRunScene(scene) {
    const run = scene.querySelector("[data-run]");
    if (!run) return null;

    const body = scene.querySelector("[data-run-body]");
    const clock = scene.querySelector("[data-run-clock]");
    const log = scene.querySelector("[data-run-log]");
    const items = Object.fromEntries(Array.from(scene.querySelectorAll("[data-run-item]"))
      .map(el => [el.dataset.runItem, el]));
    const compareLabel = scene.querySelector("[data-run-compare]");
    const count = scene.querySelector("[data-run-count]");
    const status = scene.querySelector("[data-run-status]");
    const models = Array.from(scene.querySelectorAll("[data-model]"));
    const answer = scene.querySelector("[data-run-answer]");
    const evidence = scene.querySelector("[data-run-evidence]");
    // The answer streams in as one text across its blocks, in reading order.
    const streams = Array.from(scene.querySelectorAll("[data-stream]")).map(el => ({ el, text: el.textContent }));
    const total = streams.reduce((sum, item) => sum + item.text.length, 0);
    const marks = Array.from(scene.querySelectorAll("[data-mark]"));

    let lastChars = -1;

    function show(el, visible) {
      if (el && el.hidden === visible) el.hidden = !visible;
    }

    // The panel must not change size while the run plays: the log grows and
    // folds away, the answer grows, but inside a body locked to its tallest
    // state, so nothing below the mock moves and the scroll progress keeps a
    // fixed reference. Measured, because that state depends on the width.
    function remeasureRun() {
      if (!body) return;
      body.style.minHeight = "";
      let tallest = 0;
      for (const p of [CHECK_AT + 0.01, 1]) {
        renderRun(p);
        tallest = Math.max(tallest, body.offsetHeight);
      }
      if (tallest) body.style.minHeight = tallest + "px";
      lastChars = -1;
    }

    function renderRun(p) {
      const done = p >= DONE_AT;
      const seconds = done ? RUN_SECONDS : Math.floor(span(p, 0, DONE_AT) * RUN_SECONDS);
      if (clock) {
        const text = done ? `Thought for ${RUN_SECONDS}s` : `Working for ${seconds}s`;
        if (clock.textContent !== text) clock.textContent = text;
      }
      run.classList.toggle("is-running", !done);

      // The log: notes and steps appear as they happen and fold away into
      // the clock line once the run is over, as in /app.
      show(log, !done);
      show(items.plan, p >= PLAN_AT);
      show(items.compare, p >= COMPARE_AT);
      show(items.compared, p >= COMPARED_AT);

      const share = span(p, COMPARE_AT, COMPARE_END);
      let answered = 0;
      models.forEach((model, i) => {
        const landed = share >= MODEL_FINISH[i];
        if (landed) answered += 1;
        model.classList.toggle("is-done", landed);
      });
      const compared = answered === models.length;
      if (items.compare) items.compare.classList.toggle("is-current", !compared);
      if (compareLabel) {
        const text = compared ? "Compared perspectives" : "Comparing perspectives…";
        if (compareLabel.textContent !== text) compareLabel.textContent = text;
      }
      if (count) {
        const text = compared ? `${models.length} answers` : `${answered} of ${models.length}`;
        if (count.textContent !== text) count.textContent = text;
      }

      // One live status row: writing, then checking the fixed text.
      show(items.status, p >= WRITE_AT && !done);
      if (status) {
        const text = p >= CHECK_AT ? "Checking the answer…" : "Writing answer…";
        if (status.textContent !== text) status.textContent = text;
      }

      // The answer streams in while it is written; the sheen runs while it
      // is checked; the marks stroke on once the check is back.
      const chars = Math.round(span(p, WRITE_AT, CHECK_AT - 0.03) * total);
      if (chars !== lastChars) {
        let left = chars;
        streams.forEach(item => {
          const take = Math.max(0, Math.min(item.text.length, left));
          left -= take;
          const text = item.text.slice(0, take);
          if (item.el.textContent !== text) item.el.textContent = text;
        });
        lastChars = chars;
      }
      if (answer) {
        answer.classList.toggle("is-streaming", p >= WRITE_AT && chars < total);
        answer.classList.toggle("is-checking", p >= CHECK_AT && !done);
        answer.classList.toggle("is-marked", done);
      }
      marks.forEach(mark => mark.classList.toggle(mark.dataset.mark, done));
      if (evidence) evidence.classList.toggle("is-visible", done);
    }

    remeasureRun();
    renderRun.remeasure = remeasureRun;
    // The still frame for reduced motion is the finished turn.
    renderRun.still = 1;
    return renderRun;
  }

  // ---- Driver ---------------------------------------------------------

  const BUILDERS = { ask: buildAskScene, run: buildRunScene };

  function init() {
    const scenes = Array.from(document.querySelectorAll(".lp-scroll-scene"));
    if (!scenes.length) return;

    const tracked = [];

    scenes.forEach(scene => {
      const build = BUILDERS[scene.dataset.scene];
      const render = build && build(scene);
      if (!render) return;

      const stage = scene.querySelector(".lp-scene-stage");
      const rail = scene.querySelector(".lp-scene-rail i");
      tracked.push({ scene, stage, rail, render, inView: !reducedMotion, last: -1 });

      if (reducedMotion) {
        // A still frame, chosen so each scene shows what it is about: the
        // finished question with its toolbar, ready to send, for 01; the
        // finished turn with its marks and evidence for 02 (render.still).
        render(typeof render.still === "number" ? render.still : 0.86);
        scene.classList.add("is-static");
      }
    });

    if (reducedMotion || !tracked.length) return;

    // Only scenes on screen are measured; everything else costs nothing.
    if ("IntersectionObserver" in window) {
      const io = new IntersectionObserver(entries => {
        entries.forEach(entry => {
          const item = tracked.find(t => t.scene === entry.target);
          if (item) item.inView = entry.isIntersecting;
        });
        schedule();
      }, { rootMargin: "20% 0px 20% 0px" });
      tracked.forEach(item => io.observe(item.scene));
    }

    let frame = 0;
    let running = false;

    // Geometry is cached, NOT read per frame. Reading the scene's live height
    // every frame made the animation chase itself: a phase change resizes
    // something inside the mock, the changed height feeds straight back into
    // the progress that decides the phase, and the scene jumps between two
    // states. Cached geometry breaks that loop, and it also keeps the frame
    // loop free of forced layout. It is refreshed when the page really does
    // relayout — resize, rotate, late fonts — never mid-run.
    function remeasure() {
      const viewport = window.innerHeight || document.documentElement.clientHeight;
      const scrollY = window.scrollY || window.pageYOffset || 0;

      tracked.forEach(item => {
        if (typeof item.render.remeasure === "function") item.render.remeasure();
      });

      tracked.forEach(item => {
        const rect = item.scene.getBoundingClientRect();
        item.geo = {
          top: rect.top + scrollY,
          height: rect.height,
          stageHeight: item.stage ? item.stage.offsetHeight : 0,
          viewport
        };
      });
    }

    function measure(item) {
      const geo = item.geo;
      if (!geo) return 0;
      const scrollY = window.scrollY || window.pageYOffset || 0;
      // Travel is the distance the pinned stage stays put for. When the scene
      // is not tall enough to pin (short viewports, phones), the scene's own
      // pass through the viewport is the playhead instead.
      const travel = geo.height - geo.stageHeight;

      if (travel > 40) return clamp((scrollY - geo.top) / travel, 0, 1);
      return clamp(
        (scrollY + geo.viewport * 0.82 - geo.top) / (geo.height + geo.viewport * 0.5),
        0, 1
      );
    }

    function paintOnce() {
      let active = false;
      tracked.forEach(item => {
        if (!item.inView) return;
        active = true;
        const p = measure(item);
        // Repaint only on real movement. Scrubbing wants sub-pixel fidelity,
        // idling wants to cost nothing.
        if (Math.abs(p - item.last) < 0.0004) return;
        item.last = p;
        item.scene.style.setProperty("--sp", p.toFixed(4));
        if (item.rail) item.rail.style.setProperty("--p", (p * 100).toFixed(2) + "%");
        item.render(p);
      });
      return active;
    }

    // A frame loop rather than a scroll listener. Scroll events are throttled
    // during momentum scrolling on iOS and skipped entirely for some
    // programmatic scrolls, which shows up as a scene that jumps or freezes.
    // The loop only runs while a scene is actually on screen, so an idle page
    // schedules nothing at all.
    function loop() {
      frame = 0;
      const active = paintOnce();
      if (active) {
        frame = requestAnimationFrame(loop);
      } else {
        // Nothing on screen: drop to a quarter-second heartbeat instead of
        // stopping dead, so the scenes come back even where the scroll event
        // never arrives.
        running = false;
        window.setTimeout(schedule, 250);
      }
    }

    function schedule() {
      if (running || frame) return;
      running = true;
      frame = requestAnimationFrame(loop);
    }

    // A genuine relayout invalidates the cache; a phase change never does.
    let resizeTimer = 0;
    function refresh() {
      window.clearTimeout(resizeTimer);
      resizeTimer = window.setTimeout(() => {
        remeasure();
        tracked.forEach(item => { item.last = -1; });
        schedule();
      }, 120);
    }

    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", refresh, { passive: true });
    window.addEventListener("orientationchange", refresh, { passive: true });
    window.addEventListener("load", refresh);
    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(refresh).catch(() => {});
    }
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden) schedule();
    });

    remeasure();
    paintOnce();
    schedule();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
