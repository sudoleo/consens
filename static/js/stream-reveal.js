// =====================================================================
// stream-reveal.js
// How a streamed Agent answer comes into view ("Licht").
// The provider sends text in uneven bundles: ten words at once, then
// nothing for a third of a second. Painted as it lands, the answer jumped on
// by the bundle. stream(body, text, paint) keeps its own pace instead: it
// paints a growing prefix of `text`, whole words only, a fifth of a second
// behind the text that has arrived; a big bundle is caught up faster, never
// in one jump. A painted word stands in the layout at once, so it never
// wraps half-way, but its letters come into view one after another at the
// pace of the text: each fades in, in the green of the Send button's light
// (--stream-light), and cools to ink within about six words. The glyphs
// stay sharp: the light is a tint, not a glow.
// The look is drawn with the CSS Custom Highlight API over the text the
// Markdown renderer made: no node is added and nothing moves, so a link or a
// selection in the growing paragraph stays what it is (Apple audit D4).
// Without that API, with reduced motion or with Letter animations switched
// off in Settings, active() is false and the caller paints the answer as it
// arrives.
// Exports: App.streamReveal { active, stream, settle }.
// =====================================================================
(() => {
  const App = window.App = window.App || {};

  // The shown text trails the arrived text by most of the usual gap between
  // two bundles, so the words of one bundle last until the next arrives:
  // 0.15 s for a token stream, up to 0.8 s when a proxy buffers the stream
  // into a bundle a second. The pace follows the backlog within EASE_MS.
  const LAG_MIN_S = 0.15;
  const LAG_MAX_S = 0.8;
  const GAP_CAP_MS = 1200;
  const EASE_MS = 160;
  const MIN_CPS = 40;
  const MAX_CPS = 3000;
  // A word the stream cut in two waits for its rest this long, then stands.
  const IDLE_MS = 250;
  // Further behind than this (a reload picks up a running answer): no pace.
  const JUMP_CHARS = 1200;
  // A paint that took longer (a long table or list still growing) spaces
  // out the next ones by twice its time.
  const SLOW_PAINT_MS = 8;
  // A letter runs through STEPS highlight rules after its first, unseen one.
  // They lie closer together at its start, where the eye sees each change.
  const STEPS = 20;
  const STEP_CURVE = 1.7;
  // Letters come into view at the pace of the text, never more than LEAD_MS
  // after their word was painted.
  const LEAD_MS = 100;
  // The light reaches back about six words however fast the answer streams,
  // within these bounds of time. A letter fades in over the first
  // LIGHT_APPEAR of it.
  const LIGHT_TRAIL_CHARS = 45;
  const LIGHT_MIN_MS = 380;
  const LIGHT_MAX_MS = 750;
  const LIGHT_APPEAR = 0.32;
  // What is not text (a list's bullet, a source pill) cannot be reached by a
  // highlight: while the look runs, the answer carries this class and
  // agent-chat.css brings each one into view with its first letters.
  const REVEALING = "is-stream-revealing";

  const ease = x => 1 - (1 - x) ** 3;
  const clamp01 = x => Math.max(0, Math.min(1, x));
  const pct = x => `${(clamp01(x) * 100).toFixed(1)}%`;
  const fade = (color, share) => `color-mix(in srgb, ${color} ${pct(share)}, transparent)`;
  // A letter `t` (0 to 1) into its light, in the text color it ends in.
  function lightRule(t, color) {
    const lit = `color-mix(in oklab, var(--stream-light, var(--agree)) ${pct(1 - ease(t))}, ${color})`;
    return `color: ${fade(lit, ease(clamp01(t / LIGHT_APPEAR)))};`;
  }
  const lightMs = speed => Math.min(LIGHT_MAX_MS, Math.max(LIGHT_MIN_MS, (LIGHT_TRAIL_CHARS / Math.max(1, speed)) * 1000));

  const canDraw = Boolean(window.CSS?.highlights) && typeof window.Highlight === "function"
    && typeof window.CSSStyleSheet === "function" && "adoptedStyleSheets" in document;
  const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)");
  const tracked = new Set();
  const colorIndex = new Map();
  const highlights = new Map();
  let sheet = null;
  let frame = 0;

  // Settings > Display > Letter animations off (account setting) paints the
  // answer as it arrives, like reduced motion.
  function active() {
    return canDraw && !reducedMotion?.matches && App.userSettings?.get("letter_animations") !== false;
  }

  function sharedLength(a, b) {
    const max = Math.min(a.length, b.length);
    let index = 0;
    while (index < max && a.charCodeAt(index) === b.charCodeAt(index)) index += 1;
    return index;
  }

  function lastBreak(text, at) {
    for (let index = Math.min(at, text.length) - 1; index >= 0; index -= 1) {
      if (/\s/.test(text[index])) return index;
    }
    return 0;
  }

  // Markdown that opens a line ("###", "-", "1.", ">") stands only with the
  // word after it: alone it drew an empty heading or bullet for a frame.
  const LINE_MARK = /^(?:#{1,6}|[-*+>]|\d{1,9}[.)])$/;

  // `cut` moved back before a line mark it would end on.
  function beforeMark(text, cut) {
    for (;;) {
      let end = cut;
      while (end > 0 && /\s/.test(text[end - 1])) end -= 1;
      const start = lastBreak(text, end);
      const lineStart = start === 0 || text[start] === "\n";
      if (!end || !lineStart || !LINE_MARK.test(text.slice(start ? start + 1 : 0, end))) return cut;
      cut = start;
    }
  }

  // Shown text ends at the end of a word. A word the stream has not finished
  // waits for its rest, unless the stream has paused (`idle`).
  function wordEnd(text, at, idle) {
    let end = at;
    for (;;) {
      if (end >= text.length) {
        return beforeMark(text, idle || /\s$/.test(text) ? text.length : lastBreak(text, text.length));
      }
      const next = text.slice(end).search(/\s/);
      if (next === -1) return beforeMark(text, idle ? text.length : lastBreak(text, end));
      const start = lastBreak(text, end + next) || 0;
      const word = text.slice(start ? start + 1 : 0, end + next);
      const lineStart = start === 0 || text[start] === "\n";
      if (!(lineStart && LINE_MARK.test(word))) return end + next;
      end = end + next + 1;
    }
  }

  // --- The look: highlight ranges over the newest letters -----------------
  function sheetFor() {
    if (!sheet) {
      sheet = new CSSStyleSheet();
      document.adoptedStyleSheets = [...document.adoptedStyleSheets, sheet];
    }
    return sheet;
  }

  // Every text color in the answer gets its own rules, so a link or a muted
  // word comes into its own color, not into the body's ink. Step 0 is a
  // letter not yet in view.
  function highlightFor(color, step) {
    let index = colorIndex.get(color);
    if (index === undefined) {
      index = colorIndex.size;
      colorIndex.set(color, index);
      sheetFor().insertRule(`::highlight(stream-light-${index}-0) { color: transparent; }`);
      for (let at = 1; at <= STEPS; at += 1) {
        const t = ((at - 0.5) / STEPS) ** STEP_CURVE;
        sheetFor().insertRule(`::highlight(stream-light-${index}-${at}) { ${lightRule(t, color)} }`);
      }
    }
    const key = `stream-light-${index}-${step}`;
    let highlight = highlights.get(key);
    if (!highlight) {
      highlight = new Highlight();
      CSS.highlights.set(key, highlight);
      highlights.set(key, highlight);
    }
    return highlight;
  }

  // The answer's text as the renderer left it. What is new since the last
  // look comes into view letter by letter from now on, at the pace of the
  // text and within LEAD_MS; `age` false shows it at once.
  function measure(state, now, age) {
    const nodes = [];
    const starts = [];
    let text = "";
    const walker = document.createTreeWalker(state.body, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      nodes.push(node);
      starts.push(text.length);
      text += node.data;
    }
    const kept = text.startsWith(state.text) ? state.text.length : sharedLength(state.text, text);
    state.spans = state.spans.filter(span => span.from < kept).map(span => ({ ...span, to: Math.min(span.to, kept) }));
    if (age && text.length > kept) {
      const length = text.length - kept;
      const start = Math.max(now, state.nextLetterAt);
      const letter = Math.min(1000 / Math.max(MIN_CPS, state.speed), Math.max(0, now + LEAD_MS - start) / length);
      state.spans.push({ from: kept, to: text.length, start, letter, ms: lightMs(state.speed) });
      state.nextLetterAt = start + length * letter;
    }
    state.text = text;
    state.nodes = nodes;
    state.starts = starts;
    state.writes = state.body._markdownWrites;
  }

  // The letters from `from` to `to` in `step`, across text nodes.
  function paintStep(state, from, to, step, colorOf) {
    // The last node that starts at or before `from`.
    let low = 0;
    let high = state.starts.length - 1;
    while (low < high) {
      const mid = (low + high + 1) >> 1;
      if (state.starts[mid] <= from) low = mid;
      else high = mid - 1;
    }
    for (let index = low; index < state.nodes.length && state.starts[index] < to; index += 1) {
      const node = state.nodes[index];
      const parent = node.parentElement;
      if (!parent || !node.isConnected) continue;
      const start = Math.max(0, from - state.starts[index]);
      const end = Math.min(node.length, to - state.starts[index]);
      if (end <= start) continue;
      const range = new Range();
      range.setStart(node, start);
      range.setEnd(node, end);
      highlightFor(colorOf(parent), step).add(range);
    }
  }

  function draw(now) {
    if (!canDraw) return;
    for (const highlight of highlights.values()) highlight.clear();
    const colors = new Map();
    const colorOf = element => {
      if (!colors.has(element)) colors.set(element, getComputedStyle(element).color);
      return colors.get(element);
    };
    for (const state of tracked) {
      state.spans = state.spans.filter(span => now - span.start - (span.to - span.from - 1) * span.letter < span.ms);
      for (const span of state.spans) {
        // Each letter has its own moment; before it, it is not in view (0).
        const stepAt = index => {
          const age = now - span.start - (index - span.from) * span.letter;
          if (age < 0) return 0;
          return age >= span.ms ? -1 : 1 + Math.min(STEPS - 1, Math.floor((age / span.ms) ** (1 / STEP_CURVE) * STEPS));
        };
        let runFrom = span.from;
        let runStep = stepAt(span.from);
        for (let index = span.from + 1; index <= span.to; index += 1) {
          const step = index < span.to ? stepAt(index) : NaN;
          if (step === runStep) continue;
          if (runStep >= 0) paintStep(state, runFrom, index, runStep, colorOf);
          runFrom = index;
          runStep = step;
        }
      }
    }
  }

  // --- The pace -------------------------------------------------------------
  // Someone else wrote into the answer since this look last did (another
  // chat, the review's marks): it is theirs now.
  function foreign(state) {
    return !state.body.isConnected || state.body._markdownWrites !== state.writes;
  }

  function show(state, cut, now, age) {
    state.cut = cut;
    state.shown = Math.max(state.shown, cut);
    state.paint(state.target.slice(0, cut));
    measure(state, now, age);
  }

  function advance(state, now) {
    const elapsed = state.last ? Math.min(50, now - state.last) : 16;
    state.last = now;
    const backlog = state.target.length - state.shown;
    if (backlog > 0) {
      const lag = Math.min(LAG_MAX_S, Math.max(LAG_MIN_S, (0.8 * state.gap) / 1000));
      const wanted = Math.min(MAX_CPS, Math.max(MIN_CPS, backlog / lag));
      state.speed += (wanted - state.speed) * (1 - Math.exp(-elapsed / EASE_MS));
      state.shown = Math.min(state.target.length, state.shown + (state.speed * elapsed) / 1000);
    }
    if (now < state.paintAfter) return;
    // A fixed answer paced to its end ends there, even on what looks like a
    // line mark ("42."): no word follows it that the mark could wait for.
    const cut = state.finish && state.shown >= state.target.length ? state.target.length
      : wordEnd(state.target, Math.floor(state.shown), Boolean(state.finish) || now - state.grewAt > IDLE_MS);
    if (cut > state.cut) {
      const started = performance.now();
      show(state, cut, now, true);
      const cost = performance.now() - started;
      state.paintAfter = cost > SLOW_PAINT_MS ? now + cost * 2 : 0;
    }
    // Caught up with an answer that is fixed: its full render takes over.
    if (state.finish && state.cut >= state.target.length) {
      const render = state.finish;
      state.finish = null;
      state.settled = true;
      render();
      measure(state, now, true);
    }
  }

  function drop(state) {
    tracked.delete(state);
    if (state.body._streamReveal === state) {
      delete state.body._streamReveal;
      state.body.classList.remove(REVEALING);
    }
    // The next frame draws the highlights without this answer's letters.
    schedule();
  }

  function tick(now) {
    frame = 0;
    for (const state of tracked) {
      if (foreign(state)) drop(state);
      else if (!state.settled) advance(state, now);
    }
    draw(now);
    for (const state of tracked) {
      const pacing = !state.settled && (state.cut < state.target.length || Boolean(state.finish));
      if (pacing || state.spans.length) continue;
      if (state.settled) drop(state);
      else tracked.delete(state);
    }
    if (tracked.size) schedule();
  }

  function schedule() {
    if (!frame) frame = requestAnimationFrame(tick);
  }

  // `text` is everything that has arrived; `paint(prefix)` renders a prefix
  // of it (renderMarkdownStream). Called again whenever more arrived.
  function stream(body, text, paint) {
    const now = performance.now();
    let state = body._streamReveal;
    const shown = state ? state.target.slice(0, state.cut) : "";
    if (!state || state.settled || foreign(state) || !text.startsWith(shown)) {
      // A new answer, or one that went on or took words back: the words it
      // shares with what stands stay, the rest comes in.
      let keep = state && !foreign(state) ? sharedLength(shown, text) : 0;
      if (keep < text.length && !/\s/.test(text[keep])) keep = lastBreak(text, keep);
      keep = beforeMark(text, keep);
      if (state) drop(state);
      state = body._streamReveal = {
        body, target: text, paint, cut: 0, shown: 0, speed: 0, last: 0, grewAt: now, gap: 0,
        paintAfter: 0, nextLetterAt: 0, text: "", nodes: [], starts: [], spans: [],
        writes: body._markdownWrites, settled: false, finish: null,
      };
      body.classList.add(REVEALING);
      show(state, keep, now, false);
    }
    if (text !== state.target) {
      const gap = Math.min(GAP_CAP_MS, now - state.grewAt);
      state.gap = state.gap ? state.gap * 0.7 + gap * 0.3 : gap;
      state.target = text;
      state.grewAt = now;
    }
    state.paint = paint;
    if (state.target.length - state.cut > JUMP_CHARS) show(state, state.target.length, now, false);
    if (state.cut < state.target.length) {
      tracked.add(state);
      schedule();
    }
  }

  // The answer is fixed as `text`; `render()` renders it in full. Words the
  // pace has not shown yet keep coming in at its pace and the full render
  // follows the last of them; without a backlog it renders at once. What it
  // shows beyond the paced text still comes into view letter by letter. A
  // text that does not go on from the paced one (another chat) renders at
  // once and ends the look.
  function settle(body, text, render) {
    const state = body._streamReveal;
    const goesOn = Boolean(state) && !state.settled && !foreign(state)
      && text.startsWith(state.target.slice(0, state.cut));
    if (goesOn && state.cut < text.length && text.length - state.cut <= JUMP_CHARS) {
      state.target = text;
      state.finish = render;
      tracked.add(state);
      schedule();
      return;
    }
    render();
    if (!state) return;
    if (!goesOn) {
      drop(state);
      return;
    }
    state.settled = true;
    state.finish = null;
    state.target = text;
    state.cut = text.length;
    measure(state, performance.now(), true);
    tracked.add(state);
    schedule();
  }

  App.streamReveal = { active, stream, settle };
})();
