// =====================================================================
// diagram-render.js
// Diagrams in an answer: a ```mermaid block shows as its diagram, in the
// app (markdown-stream.js leaves each block in a .md-diagram place) and on
// public pages (the server's code block, adopted here).
// Mermaid comes from static/vendor, imported when an answer first holds a
// diagram: its core and one kind of diagram are about 230 KB compressed.
// Export: window.ConsensusDiagram.{key, request, settled, warm, render}.
// =====================================================================

(function initConsensusDiagram() {
  "use strict";

  const ENTRY = "/static/vendor/mermaid/12.3.0/dist/mermaid.esm.min.mjs";
  // A drawing that takes longer no longer holds back the text after it
  // (markdown-stream.js streamHold): a slow network must not stop an answer.
  const HOLD_MS = 2500;
  const RETRY_MS = 15000;
  // Longer sources stay code: layout time grows faster than the text.
  const MAX_SOURCE_CHARS = 20000;
  const DRAWINGS_KEPT = 60;
  const SIZES_KEY = "consens.diagramSizes";
  const SIZES_KEPT = 200;
  // The diagram is an image (below), and an image cannot use the page's web
  // font. Mermaid measures its labels in the page, so both name the same
  // system fonts: a label measured in one font and drawn in another runs
  // over its box.
  const FONT = 'system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif'; // i18n-ignore
  // Settings a diagram's own "%%{init}%%" line or front matter may not
  // change: Mermaid's defaults, the look (the app's theme decides),
  // everything that would bring markup or style rules of the model's into
  // the drawing, and the layout (configure(); the ELK engine is not
  // shipped, scripts/vendor_frontend.mjs).
  const LOCKED = ["secure", "securityLevel", "startOnLoad", "maxTextSize", "suppressErrorRendering", "maxEdges",
    "theme", "themeVariables", "themeCSS", "darkMode", "fontFamily", "altFontFamily", "htmlLabels", "look",
    "handDrawnSeed", "layout"];

  // An image shape ("@{ img: … }") makes Mermaid fetch its address while it
  // draws, in the page. Nothing in an answer loads on its own
  // (markdown-stream.js), so such a block stays code; the CSP's img-src
  // would refuse a foreign host as well.
  const LOADS_IMAGE = /@\{[^}]*\bimg\s*:/i;

  // FNV-1a over the source: the name of a diagram's place. Two renders of
  // the same source are the same place (markdown-stream.js keeps its node).
  function key(source) {
    const text = String(source || "");
    let hash = 0x811c9dc5;
    for (let index = 0; index < text.length; index += 1) {
      hash ^= text.charCodeAt(index);
      hash = Math.imul(hash, 0x01000193);
    }
    return `${(hash >>> 0).toString(36)}-${text.length.toString(36)}`;
  }

  // ---- The app's colors ------------------------------------------------------
  // An image sees no CSS variable of the page, so the palette is read from
  // the tokens (variables.css, public-tokens.css) when a diagram is drawn.
  function themeName() {
    return document.documentElement.classList.contains("dark-mode")
      || Boolean(document.body && document.body.classList.contains("dark-mode")) ? "dark" : "light";
  }

  const FALLBACK = {
    light: { ground: [255, 255, 255], raise: [243, 243, 243], ink: [10, 10, 10], muted: [94, 94, 94], accent: [33, 120, 99] },
    dark: { ground: [5, 5, 5], raise: [21, 21, 21], ink: [245, 245, 245], muted: [161, 161, 161], accent: [109, 192, 164] }
  };

  // "rgb(10, 10, 10)", "rgba(…)" or "color(srgb 0.04 0.04 0.04)" as [r, g, b].
  function parseColor(value) {
    const numbers = (String(value || "").match(/-?\d*\.?\d+(?:e-?\d+)?%?/g) || []).slice(0, 3);
    if (numbers.length < 3) return null;
    const unit = /^color\(/.test(value) ? 255 : 1;
    const channels = numbers.map(part => part.endsWith("%") ? parseFloat(part) * 2.55 : parseFloat(part) * unit);
    return channels.every(Number.isFinite) ? channels.map(channel => Math.max(0, Math.min(255, Math.round(channel)))) : null;
  }

  function tokens(theme) {
    const fallback = FALLBACK[theme];
    if (!document.body) return fallback;
    const probe = document.createElement("span");
    probe.style.position = "absolute";
    probe.style.visibility = "hidden";
    document.body.append(probe);
    const read = (name, spare) => {
      probe.style.color = "";
      probe.style.color = `var(${name})`;
      return (probe.style.color && parseColor(getComputedStyle(probe).color)) || spare;
    };
    const palette = {
      ground: read("--ground", fallback.ground), raise: read("--raise", fallback.raise), ink: read("--ink", fallback.ink),
      muted: read("--ink-3", fallback.muted), accent: read("--agree", fallback.accent)
    };
    probe.remove();
    return palette;
  }

  const hex = color => `#${color.map(channel => channel.toString(16).padStart(2, "0")).join("")}`;
  // `share` of `to` in `from`.
  const mix = (from, to, share) => hex(from.map((channel, index) => Math.round(channel + (to[index] - channel) * share)));

  // Monochrome like the app: shapes are a tone of the ground, lines and
  // words are ink, and the house green is the one accent (a chart's first
  // series, today's line). Mermaid derives what is not named here from
  // these, so a grey stays grey.
  function themeVariables(theme) {
    const { ground, raise, ink, muted, accent } = tokens(theme);
    const paper = hex(ground), tone = hex(raise), text = hex(ink), quiet = hex(muted), green = hex(accent);
    const hair = mix(ground, ink, 0.2);
    const soft = mix(ground, ink, 0.1);
    // Tones a label in ink stays readable on, neighbors apart.
    const ramp = [0.3, 0.14, 0.4, 0.2, 0.08, 0.34, 0.17, 0.26, 0.11, 0.37, 0.23, 0.05].map(share => mix(ground, ink, share));
    const variables = {
      darkMode: theme === "dark", background: paper, fontFamily: FONT, fontSize: "15px",
      // Flat: no shadow under a shape and no gradient in it.
      dropShadow: "none", useGradient: false,
      primaryColor: tone, primaryTextColor: text, primaryBorderColor: hair,
      secondaryColor: tone, secondaryTextColor: text, secondaryBorderColor: hair,
      tertiaryColor: paper, tertiaryTextColor: text, tertiaryBorderColor: hair,
      lineColor: quiet, textColor: text, titleColor: text, mainBkg: tone, nodeBorder: hair, nodeTextColor: text,
      clusterBkg: paper, clusterBorder: hair, edgeLabelBackground: paper, arrowheadColor: quiet, defaultLinkColor: quiet,
      noteBkgColor: tone, noteTextColor: text, noteBorderColor: hair,
      actorBkg: tone, actorBorder: hair, actorTextColor: text, actorLineColor: hair, signalColor: quiet,
      signalTextColor: text, labelBoxBkgColor: tone, labelBoxBorderColor: hair, labelTextColor: text, loopTextColor: text,
      activationBkgColor: soft, activationBorderColor: hair, sequenceNumberColor: paper,
      sectionBkgColor: tone, altSectionBkgColor: paper, sectionBkgColor2: tone, gridColor: soft,
      taskBkgColor: mix(ground, ink, 0.3), taskBorderColor: mix(ground, ink, 0.3), taskTextColor: text,
      taskTextLightColor: text, taskTextDarkColor: text, taskTextOutsideColor: text, taskTextClickableColor: text,
      activeTaskBkgColor: green, activeTaskBorderColor: green, doneTaskBkgColor: soft, doneTaskBorderColor: hair,
      critBkgColor: quiet, critBorderColor: quiet, todayLineColor: green,
      labelColor: text, errorBkgColor: tone, errorTextColor: text,
      classText: text, attributeBackgroundColorOdd: paper, attributeBackgroundColorEven: tone,
      relationColor: quiet, relationLabelBackground: paper, relationLabelColor: text,
      transitionColor: quiet, transitionLabelColor: text, stateLabelColor: text, stateBkg: tone, labelBackgroundColor: paper,
      compositeBackground: paper, compositeTitleBackground: tone, compositeBorder: hair, innerEndBackground: quiet,
      specialStateColor: quiet, altBackground: tone,
      pieStrokeColor: paper, pieStrokeWidth: "2px", pieOuterStrokeColor: paper, pieOuterStrokeWidth: "0px", pieOpacity: "1",
      pieTitleTextColor: text, pieSectionTextColor: text, pieLegendTextColor: text,
      quadrant1Fill: tone, quadrant2Fill: paper, quadrant3Fill: tone, quadrant4Fill: paper,
      quadrant1TextFill: quiet, quadrant2TextFill: quiet, quadrant3TextFill: quiet, quadrant4TextFill: quiet,
      quadrantPointFill: green, quadrantPointTextFill: text, quadrantXAxisTextFill: text, quadrantYAxisTextFill: text,
      quadrantInternalBorderStrokeFill: hair, quadrantExternalBorderStrokeFill: hair, quadrantTitleFill: text,
      xyChart: {
        backgroundColor: "transparent", titleColor: text, xAxisLabelColor: quiet, xAxisTitleColor: text,
        xAxisTickColor: hair, xAxisLineColor: hair, yAxisLabelColor: quiet, yAxisTitleColor: text, yAxisTickColor: hair,
        yAxisLineColor: hair, plotColorPalette: [green, quiet, ...ramp.slice(0, 6)].join(",")
      },
      gitInv0: paper, gitBranchLabel0: paper, commitLabelColor: text, commitLabelBackground: tone, tagLabelColor: text,
      tagLabelBackground: tone, tagLabelBorder: hair
    };
    ramp.forEach((color, index) => {
      variables[`pie${index + 1}`] = color;
      variables[`cScale${index}`] = color;
      variables[`cScaleLabel${index}`] = text;
      variables[`cScaleInv${index}`] = text;
      if (index < 8) {
        variables[`git${index}`] = index ? mix(ground, ink, 0.35 + index * 0.06) : green;
        variables[`gitBranchLabel${index}`] = paper;
      }
    });
    return variables;
  }

  // ---- Mermaid ---------------------------------------------------------------
  let library = null;
  function load() {
    if (!library) {
      library = import(ENTRY).then(module => module.default);
      // A failed download may be tried again by the next diagram.
      library.catch(() => { library = null; });
    }
    return library;
  }

  let configured = "";
  function configure(mermaid, theme) {
    if (configured === theme) return;
    mermaid.initialize({
      startOnLoad: false, securityLevel: "strict", suppressErrorRendering: true, secure: LOCKED,
      // Labels as SVG text: HTML labels sit in <foreignObject>, which Safari
      // misplaces inside an image.
      htmlLabels: false, theme: "base", themeVariables: themeVariables(theme), fontFamily: FONT,
      // Mermaid 12 lays out with ELK unless told otherwise: 1.6 MB more to
      // load, with regex lookbehinds Safari before 16.4 cannot parse. Dagre
      // is in the core's reach and draws the same diagrams.
      layout: "dagre"
    });
    configured = theme;
  }

  function base64(text) {
    const bytes = new TextEncoder().encode(text);
    let binary = "";
    for (let index = 0; index < bytes.length; index += 0x8000) {
      binary += String.fromCharCode.apply(null, bytes.subarray(index, index + 0x8000));
    }
    return btoa(binary);
  }

  // Mermaid's markup as an image of its own size. The template is an inert
  // document, so nothing in the markup loads or runs while it is read, and
  // XMLSerializer writes what an image needs: well-formed XML (Mermaid's
  // string is HTML, with "&nbsp;" and unclosed <br>).
  function picture(markup) {
    const template = document.createElement("template");
    template.innerHTML = markup;
    const svg = template.content.querySelector("svg");
    const box = (svg && svg.getAttribute("viewBox") || "").trim().split(/[\s,]+/).map(Number);
    const width = Math.ceil(box[2]), height = Math.ceil(box[3]);
    if (!svg || box.length !== 4 || !(width > 0) || !(height > 0) || width > 20000 || height > 20000) {
      throw new Error("diagram without a size");
    }
    svg.setAttribute("width", String(width));
    svg.setAttribute("height", String(height));
    svg.removeAttribute("style");
    // Some kinds of diagram shade their shapes with a filter of their own,
    // whatever the theme says.
    svg.querySelectorAll("filter").forEach(node => node.remove());
    svg.querySelectorAll("[filter]").forEach(node => node.removeAttribute("filter"));
    svg.querySelectorAll("[style*='filter']").forEach(node => {
      node.setAttribute("style", node.getAttribute("style").replace(/(^|;)\s*filter\s*:[^;]*/gi, "$1"));
    });
    const title = svg.querySelector(":scope > title");
    return {
      data: base64(new XMLSerializer().serializeToString(svg)), width, height,
      title: title ? title.textContent.trim().slice(0, 200) : ""
    };
  }

  // One drawing at a time: Mermaid's settings are global, and a theme
  // change between two drawings sets them anew.
  let queue = Promise.resolve();
  let serial = 0;
  function draw(source, theme) {
    const job = queue.then(async () => {
      const mermaid = await load().catch(() => { throw Object.assign(new Error("Mermaid did not load"), { again: true }); });
      configure(mermaid, theme);
      serial += 1;
      const result = await mermaid.render(`consens-diagram-${serial}`, source);
      return picture(result.svg);
    });
    queue = job.catch(() => {});
    return job;
  }

  // ---- Drawings by source ----------------------------------------------------
  // theme + source -> { state: "pending" | "drawn" | "failed", since, done, picture }.
  const drawings = new Map();

  function request(source, theme) {
    theme = theme || themeName();
    const id = `${theme}\n${source}`;
    let entry = drawings.get(id);
    // A diagram Mermaid cannot read stays code; one whose Mermaid did not
    // arrive (the network) is tried again by a later look, not at once.
    if (entry && !(entry.again && Date.now() - entry.since > RETRY_MS)) return entry;
    entry = { state: "pending", since: Date.now(), picture: null, done: null, again: false };
    drawings.set(id, entry);
    for (const old of drawings.keys()) {
      if (drawings.size <= DRAWINGS_KEPT) break;
      if (drawings.get(old).state !== "pending") drawings.delete(old);
    }
    const work = source.trim() && source.length <= MAX_SOURCE_CHARS && !LOADS_IMAGE.test(source) ? draw(source, theme)
      : Promise.reject(new Error("no diagram"));
    entry.done = work.then(result => {
      entry.state = "drawn";
      entry.picture = result;
      rememberSize(source, result);
    }, error => {
      entry.state = "failed";
      entry.again = Boolean(error && error.again);
      entry.since = Date.now();
    });
    return entry;
  }

  // Whether the text after this diagram may show: drawn, failed or late.
  function settled(source) {
    const entry = request(String(source || ""));
    return entry.state !== "pending" || Date.now() - entry.since > HOLD_MS;
  }

  // The block is still being written: Mermaid and the diagram's kind (named
  // in its first line) load meanwhile, so the finished block draws at once.
  const warmed = new Set();
  function warm(partial) {
    const first = String(partial || "").trim().split("\n")[0].trim();
    if (warmed.has(first)) return;
    warmed.add(first);
    load().then(mermaid => first && mermaid.parse(String(partial), { suppressErrors: true })).catch(() => {});
  }

  // ---- The size a diagram had ------------------------------------------------
  // Known before it is drawn again (a chat opened later), so its place has
  // its size from the first frame and nothing below it moves.
  function sizes() {
    try {
      const stored = JSON.parse(localStorage.getItem(SIZES_KEY) || "{}");
      return stored && typeof stored === "object" && !Array.isArray(stored) ? stored : {};
    } catch (_) { return {}; }
  }
  function rememberSize(source, result) {
    try {
      const stored = sizes();
      const name = key(source);
      delete stored[name];
      stored[name] = [result.width, result.height];
      const names = Object.keys(stored);
      for (const old of names.slice(0, Math.max(0, names.length - SIZES_KEPT))) delete stored[old];
      localStorage.setItem(SIZES_KEY, JSON.stringify(stored));
    } catch (_) { /* Private mode or a full store: the place keeps its default field. */ }
  }
  function setSize(place, width, height) {
    place.style.setProperty("--diagram-width", String(width));
    place.style.setProperty("--diagram-height", String(height));
    place.classList.add("has-size");
  }

  // ---- A diagram's place -----------------------------------------------------
  function sourceOf(place) {
    const code = place.querySelector(":scope > pre > code");
    return code ? code.textContent.replace(/\n$/, "") : "";
  }

  // The field the diagram is drawn into (diagram.css): there from the first
  // frame, so the drawing takes the place of its field, not room below it.
  function figureOf(place) {
    let figure = place.querySelector(":scope > .md-diagram-figure");
    if (figure) return figure;
    figure = document.createElement("div");
    figure.className = "md-diagram-figure";
    // The answer's words are the model's (data-i18n-skip); these are ours.
    figure.setAttribute("data-i18n-ui", "");
    const image = document.createElement("img");
    image.alt = "";
    // The picture viewer of /app (attachments.js) enlarges it; a public
    // page shows it as it is.
    const viewer = window.App && window.App.attachments && window.App.attachments.openStored;
    if (viewer) {
      const open = document.createElement("button");
      open.type = "button";
      open.className = "md-diagram-open";
      open.setAttribute("aria-label", "Open diagram");
      open.disabled = true;
      open.append(image);
      open.addEventListener("click", () => {
        const shown = place._diagram;
        // The viewer's title is a file's name, which nothing translates.
        const title = shown && (shown.title || (window.App.t ? window.App.t("Diagram") : "Diagram"));
        if (shown) viewer({ name: "diagram.svg", title, mime: "image/svg+xml", data: shown.data, trigger: open });
      });
      figure.append(open);
    } else {
      figure.append(image);
    }
    place.prepend(figure);
    return figure;
  }

  function show(place, result, theme) {
    const figure = figureOf(place);
    const image = figure.querySelector("img");
    const open = figure.querySelector(".md-diagram-open");
    if (open) open.disabled = false;
    place._diagram = result;
    image.alt = result.title || "Diagram";
    image.src = `data:image/svg+xml;base64,${result.data}`;
    setSize(place, result.width, result.height);
    place.dataset.drawn = theme;
    place.classList.remove("is-code");
    place.classList.add("is-drawn");
  }

  function fill(place) {
    const theme = themeName();
    if (place.dataset.drawn === theme) return;
    const entry = request(sourceOf(place), theme);
    if (entry.state === "drawn") {
      show(place, entry.picture, theme);
    } else if (entry.state === "failed") {
      // What Mermaid cannot read stays what the model wrote: a code block.
      if (!place.dataset.drawn) place.classList.add("is-code");
    } else if (!place._diagramWaits) {
      if (!place.dataset.drawn) {
        const known = sizes()[place.dataset.diagram];
        if (Array.isArray(known) && known[0] > 0 && known[1] > 0) setSize(place, known[0], known[1]);
        figureOf(place);
      }
      place._diagramWaits = true;
      entry.done.then(() => {
        place._diagramWaits = false;
        // Only a drawing the reader waited for comes into view; one that is
        // there at once (drawn before) stands.
        if (!place.dataset.drawn) place.classList.add("is-arriving");
        fill(place);
      });
    }
  }

  // A code block the server rendered (public pages) becomes a place.
  function adopt(root) {
    root.querySelectorAll("pre > code.language-mermaid").forEach(code => {
      const pre = code.parentElement;
      if (pre.parentElement && pre.parentElement.classList.contains("md-diagram")) return;
      const place = document.createElement("div");
      place.className = "md-diagram";
      place.dataset.diagram = key(code.textContent.replace(/\n$/, ""));
      pre.replaceWith(place);
      place.append(pre);
    });
  }

  function render(root) {
    if (!root || !root.querySelectorAll) return;
    adopt(root);
    root.querySelectorAll(".md-diagram[data-diagram]").forEach(fill);
  }

  function start() {
    render(document);
    // The app and the public pages mark dark mode on <body> or <html>.
    const repaint = () => {
      const theme = themeName();
      document.querySelectorAll(".md-diagram.is-drawn").forEach(place => {
        if (place.dataset.drawn !== theme) fill(place);
      });
    };
    const watcher = new MutationObserver(repaint);
    watcher.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
    if (document.body) watcher.observe(document.body, { attributes: true, attributeFilter: ["class"] });
  }

  window.ConsensusDiagram = { key, request, settled, warm, render };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
