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
//
// Screen readers never see a frame: both mockups are aria-hidden, and the
// finished scene stands beside each in words (.lp-sr in landing.html).
// =====================================================================

(function () {
  "use strict";

  const reducedMotion = window.matchMedia
    && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
  // A label as the page shows it: German on a German page (i18n.js
  // translates what is written), so "already shown" compares with that.
  const say = text => (window.App && window.App.t ? window.App.t(text) : text);

  // Progress of `value` through the window [from, to], clamped to 0..1.
  const span = (value, from, to) => clamp((value - from) / (to - from), 0, 1);

  // ---- Scene 01: Ask --------------------------------------------------

  // Dieselbe Frage, die /app?demo=1 tippt (static/demo.js): Wer aus dem Hero
  // in die Demo springt, sieht dort weiter, was hier anfaengt. Nur die erste
  // Zeile — die Eckdaten werden auch in der App eingefuegt, nicht getippt.
  // In the page's language: typed letter by letter, a half question is never
  // looked up (the field is data-i18n-skip below).
  const ASK_QUESTION = say("Should we buy the flat we rent, or keep renting and invest the difference?");

  function buildAskScene(scene) {
    const text = scene.querySelector("[data-ask-text]");
    const composer = scene.querySelector("[data-ask-composer]");
    const send = scene.querySelector("[data-ask-send]");
    if (!text || !composer) return null;
    text.setAttribute("data-i18n-skip", "");

    let lastChars = -1;

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
      // then send. The reviewers' words beside it are a label, not a switch:
      // lighting up on the way (a run switch's step) read as a flicker while
      // scrolling.
      composer.classList.toggle("is-active", typed > 0.02);
      if (send) {
        send.classList.toggle("is-ready", typed >= 1);
        send.classList.toggle("is-pressed", p >= 0.9);
      }
    }

    return renderAsk;
  }

  // ---- Scene 02: Run --------------------------------------------------

  // One Agent turn in the one mode, on the surfaces agent-activity.js,
  // agent-delegation.js and agent-review.js draw in /app: the reviewers
  // join beside the clock with the first step, a note on the plan, its
  // search, its workspace (the script it writes, the command it runs and
  // what the command prints), the agent asking the AIs once (their answers
  // land one by one). Once it writes, its steps fold into the clock line and
  // one live row stays: the answer with its chart, whose lines grow as the
  // page scrolls, and its spreadsheet, the reviewers' review of that exact
  // text, then their marks and the evidence row. No score.
  const PLAN_AT = 0.03;
  const SEARCH_AT = 0.05;
  const SEARCHED_AT = 0.10;
  const WORKSPACE_AT = 0.11;
  const WORKSPACE_DONE = 0.15;
  const SCRIPT_AT = 0.16;
  const SCRIPT_DONE = 0.19;
  const COMMAND_AT = 0.20;
  const PRINTED_AT = 0.30;
  const COMMAND_DONE = 0.33;
  const COMPARE_AT = 0.35;
  const COMPARE_END = 0.50;
  const COMPARED_AT = 0.52;
  const WRITE_AT = 0.56;
  const CHART_AT = 0.61;
  const CHART_END = 0.71;
  const TEXT_END = 0.77;
  const REVIEW_AT = 0.80;
  const DONE_AT = 0.91;
  const RUN_SECONDS = 17;

  // Where each AI's answer lands inside the comparison, by how many AIs the
  // scene asks (Daily's two). A comparison is only as fast
  // as its slowest AI, so the spread is deliberate, and the last one always
  // lands at the end of the stretch. Any other count spreads evenly.
  const MODEL_FINISH = { 2: [0.55, 1.0], 3: [0.42, 0.7, 1.0] };
  const finishOf = (i, count) => (MODEL_FINISH[count] || [])[i] ?? (i + 1) / count;

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
    const writing = scene.querySelector("[data-run-writing]");
    const status = scene.querySelector("[data-run-status]");
    const models = Array.from(scene.querySelectorAll("[data-model]"));
    const reviewers = Array.from(scene.querySelectorAll("[data-reviewer]"));
    const answer = scene.querySelector("[data-run-answer]");
    const evidence = scene.querySelector("[data-run-evidence]");
    const files = scene.querySelector("[data-run-files]");
    // What the command prints, a line at a time, and the time it took.
    const output = scene.querySelector("[data-run-output]");
    const lines = Array.from(scene.querySelectorAll("[data-run-line]"));
    const ran = scene.querySelector("[data-run-ran]");
    // The chart and where on its way from left to right its marks stand
    // (the partial scripts/demo_assets.py writes).
    const chart = scene.querySelector("[data-run-chart]");
    const crossing = chart ? Number(chart.dataset.crossing) || 0 : 0;
    const stay = chart ? Number(chart.dataset.stay) || 0 : 0;
    // A step's words while it runs and once it is done (landing.html).
    const steps = [[items.search, SEARCHED_AT], [items.workspace, WORKSPACE_DONE], [items.write, SCRIPT_DONE]]
      .filter(([el]) => el).map(([el, end]) => ({ el, end, label: el.querySelector("[data-run-live]") }));
    // The answer streams in as one text across its blocks, in reading order.
    const streams = Array.from(scene.querySelectorAll("[data-stream]")).map(el => {
      // The words arrive already in the page's language; a half-written
      // word is never looked up in the dictionary.
      el.setAttribute("data-i18n-skip", "");
      return { el, text: el.textContent };
    });
    const total = streams.reduce((sum, item) => sum + item.text.length, 0);
    // The verdict stands before the chart, the rest of the text after it.
    const verdict = streams.length ? streams[0].text.length : 0;
    const marks = Array.from(scene.querySelectorAll("[data-mark]"));

    let lastChars = -1;
    let lastP = 0;
    let labelWidths = null;
    const slot = run.parentElement;

    function show(el, visible) {
      if (el && el.hidden === visible) el.hidden = !visible;
    }

    // Nothing around the mock may move while the run plays, and nothing in
    // it may jump. The SLOT the card sits in is locked to
    // the card's tallest state, so the heading beside it and the page below
    // keep their place and the scroll progress keeps a fixed reference. The
    // card itself follows its content: the log grows, and once the agent
    // writes it FOLDS into the clock line with a height transition
    // (.lp-agent-log.is-folded) instead of vanishing in one frame, which
    // dropped the answer 204 px (277 on a phone) and left a blank card. The
    // model icons stand after the comparison label, and the label is shorter
    // once it is done (no mark, lighter weight, fewer letters): kept at the
    // wider width it left a hole before the icons for the rest of the run,
    // let go the icons jumped. So the label carries its measured width for
    // each wording as a min-width, and the stylesheet glides from the running
    // one to the finished one. Measured with transitions off and in the
    // page's language, because both depend on the width.
    function remeasureRun() {
      if (!body) return;
      // renderRun moves lastP, so the reader's frame is kept before measuring.
      const frame = lastP;
      run.classList.add("is-measuring");
      if (slot) slot.style.minHeight = "";
      labelWidths = null;
      if (compareLabel) compareLabel.style.minWidth = "";
      let tallest = 0;
      const widths = {};
      // The tallest frames: the command with all it printed, the comparison
      // with its note, the whole answer under its live row, the finished turn.
      for (const [p, wording] of [[COMMAND_DONE - 0.01], [COMPARE_AT + 0.01, "live"], [COMPARED_AT, "done"], [REVIEW_AT + 0.01], [1]]) {
        renderRun(p);
        if (window.App && window.App.i18n) window.App.i18n.flush();
        tallest = Math.max(tallest, run.offsetHeight);
        if (wording && compareLabel) widths[wording] = Math.ceil(compareLabel.getBoundingClientRect().width);
      }
      if (slot && tallest) slot.style.minHeight = tallest + "px";
      if (widths.live && widths.done) labelWidths = widths;
      lastChars = -1;
      // Back to the frame the reader is on before transitions return, or the
      // log would fold open from the last measured state.
      renderRun(frame);
      void run.offsetHeight;
      run.classList.remove("is-measuring");
    }

    function renderRun(p) {
      lastP = p;
      const done = p >= DONE_AT;
      const wrote = p >= WRITE_AT;
      const reviewing = p >= REVIEW_AT && !done;
      const seconds = done ? RUN_SECONDS : Math.floor(span(p, 0, DONE_AT) * RUN_SECONDS);
      if (clock) {
        // The head's words in /app (agent-activity.js HEAD_VERBS): working,
        // the reviewers reviewing the written answer, done.
        const text = done ? `Thought for ${RUN_SECONDS}s` : reviewing ? `Reviewing · ${seconds}s` : `Working for ${seconds}s`;
        if (clock.textContent !== say(text)) clock.textContent = text;
      }
      run.classList.toggle("is-running", !done);

      // The reviewers follow from the first step on, beside the clock.
      reviewers.forEach(reviewer => reviewer.classList.toggle("is-done", p >= PLAN_AT));

      // The log: notes and steps appear as they happen and fold into the
      // clock line once the agent writes its answer, as the steps of a turn
      // in /app give way to one live line -- a fold, not a cut.
      if (log) log.classList.toggle("is-folded", wrote);
      show(items.plan, p >= PLAN_AT);
      show(items.search, p >= SEARCH_AT);
      show(items.workspace, p >= WORKSPACE_AT);
      show(items.write, p >= SCRIPT_AT);
      show(items.command, p >= COMMAND_AT);
      steps.forEach(({ el, end, label }) => {
        el.classList.toggle("is-current", p < end);
        if (!label) return;
        const text = p < end ? label.dataset.runLive : label.dataset.runDone;
        if (label.textContent !== say(text)) label.textContent = text;
      });

      // The command prints line by line while it runs. Done, its output
      // folds and the line says how long it took, as in /app.
      const finished = p >= COMMAND_DONE;
      const printed = Math.ceil(span(p, COMMAND_AT, PRINTED_AT) * lines.length);
      lines.forEach((line, i) => show(line, i < printed));
      if (items.command) items.command.classList.toggle("is-current", !finished);
      if (output) output.classList.toggle("is-folded", finished || printed === 0);
      show(ran, finished);

      show(items.compare, p >= COMPARE_AT);
      show(items.compared, p >= COMPARED_AT);

      const share = span(p, COMPARE_AT, COMPARE_END);
      let answered = 0;
      models.forEach((model, i) => {
        const landed = share >= finishOf(i, models.length);
        if (landed) answered += 1;
        model.classList.toggle("is-done", landed);
      });
      const compared = answered === models.length;
      if (items.compare) items.compare.classList.toggle("is-current", !compared);
      if (compareLabel) {
        const text = compared ? "Compared perspectives" : "Comparing perspectives…";
        if (compareLabel.textContent !== say(text)) compareLabel.textContent = text;
        if (labelWidths) compareLabel.style.minWidth = (compared ? labelWidths.done : labelWidths.live) + "px";
      }
      if (count) {
        const text = compared ? `${models.length} answers` : `${answered} of ${models.length}`;
        if (count.textContent !== say(text)) count.textContent = text;
      }

      // One live row under the clock: writing, then the reviewers reviewing
      // the fixed text. It folds away with the end of the run.
      if (writing) writing.classList.toggle("is-open", wrote && !done);
      if (status) {
        const text = p >= REVIEW_AT ? "Reviewing the answer…" : "Writing answer…";
        if (status.textContent !== say(text)) status.textContent = text;
      }

      // The answer streams in while it is written: the verdict, then the
      // chart, then the sentences under it. The sheen runs while the
      // reviewers review it; their marks stroke on once they are back.
      const chars = p < CHART_END
        ? Math.round(span(p, WRITE_AT + 0.01, CHART_AT) * verdict)
        : verdict + Math.round(span(p, CHART_END, TEXT_END) * (total - verdict));
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
      // The chart draws itself from the first year to the last: how far is
      // the scroll, so scrubbing back takes the lines back. Its marks stand
      // once the lines have reached them.
      show(chart, p >= CHART_AT);
      if (chart) {
        const drawn = span(p, CHART_AT, CHART_END);
        chart.style.setProperty("--draw", drawn.toFixed(3));
        chart.classList.toggle("is-crossed", drawn >= crossing);
        chart.classList.toggle("is-staying", drawn >= stay);
        chart.classList.toggle("is-drawn", drawn >= 1);
      }
      // The spreadsheet joins the answer under its chart.
      show(files, p >= CHART_END);
      if (answer) {
        answer.classList.toggle("is-streaming", wrote && p < TEXT_END);
        answer.classList.toggle("is-reviewing", reviewing);
        answer.classList.toggle("is-marked", done);
      }
      marks.forEach(mark => mark.classList.toggle(mark.dataset.mark, done));
      if (evidence) evidence.classList.toggle("is-visible", done);
    }

    remeasureRun();
    renderRun.remeasure = remeasureRun;
    // The still frame for reduced motion is the finished turn.
    renderRun.still = 1;
    // Where the stage is not pinned, the card itself is the clock (measure).
    renderRun.anchor = slot;
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
        const anchor = item.render.anchor ? item.render.anchor.getBoundingClientRect() : null;
        item.geo = {
          top: rect.top + scrollY,
          height: rect.height,
          stageHeight: item.stage ? item.stage.offsetHeight : 0,
          anchorTop: anchor ? anchor.top + scrollY : 0,
          anchorHeight: anchor ? anchor.height : 0,
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
      // A scene with a card taller than a phone's screen is never pinned, and
      // its heading alone fills the first screen: there the card is the
      // clock. The run starts as the card comes up from the lower edge and is
      // over when its last line has arrived, so each part is written while
      // it is on screen and the finished card scrolls on like any other.
      if (geo.anchorHeight) {
        const distance = Math.max(240, geo.anchorHeight - geo.viewport * 0.2);
        return clamp((scrollY + geo.viewport * 0.72 - geo.anchorTop) / distance, 0, 1);
      }
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
