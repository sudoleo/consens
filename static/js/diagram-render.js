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
  const DRAWINGS_KEPT = 40;
  const SIZES_KEY = "consens.diagramSizes";
  const SIZES_KEPT = 200;
  // A drawing is laid out for the width of its place, in steps of WIDTH_STEP
  // so that a scrollbar coming or going draws nothing anew.
  const WIDTH_STEP = 20;
  const WIDTH_LEAST = 240;
  const WIDTH_MOST = 1600;
  // diagram.css shows a drawing no smaller than --diagram-min-scale of its
  // size (labels of 14 px at 10.5 px or more). A flowchart or timeline that
  // would come out smaller than TURN_BELOW in its place is laid out the
  // other way round as well (turned()).
  const TURN_BELOW = 0.85;
  // A Gantt chart is at least this wide: narrower, the names of its tasks
  // stand over each other and over its sections. On a phone it pans.
  const GANTT_LEAST = 760;
  // The diagram is an image (below), and an image loads nothing, not even
  // the page's web font: the app's Inter travels inside each drawing as
  // data (fontRule). Mermaid measures its labels in the page, where the
  // same bytes are a FontFace under the same name, so a label is measured
  // and drawn in one font and never runs over its box. Without the font
  // file both fall back to the system's sans serif.
  const FAMILY = "consens-diagram";
  const FONT = `"${FAMILY}", system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif`; // i18n-ignore
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
  // The data in "@{ … }" is YAML, so the key may come quoted, as an alias or
  // spelled in escapes: any "img" in it, or any backslash, refuses the
  // block. Mermaid's lexer ends the data at the first "}" outside double
  // quotes, and so does this.
  function loadsImage(source) {
    const text = String(source || "");
    for (let start = text.indexOf("@{"); start !== -1; start = text.indexOf("@{", start + 2)) {
      let end = start + 2;
      let quoted = false;
      for (; end < text.length; end += 1) {
        if (text[end] === '"') quoted = !quoted;
        else if (text[end] === "}" && !quoted) break;
      }
      const data = text.slice(start + 2, end);
      if (/img/i.test(data) || data.includes("\\")) return true;
    }
    return false;
  }

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
  // the tokens (variables.css, public-tokens.css) when a diagram is asked for.
  function themeName() {
    return document.documentElement.classList.contains("dark-mode")
      || Boolean(document.body && document.body.classList.contains("dark-mode")) ? "dark" : "light";
  }

  const FALLBACK = {
    light: { ground: [255, 255, 255], ink: [10, 10, 10], muted: [94, 94, 94], accent: [33, 120, 99] },
    dark: { ground: [5, 5, 5], ink: [245, 245, 245], muted: [161, 161, 161], accent: [109, 192, 164] }
  };

  // "rgb(10, 10, 10)", "rgba(…)" or "color(srgb 0.04 0.04 0.04)" as [r, g, b].
  function parseColor(value) {
    const numbers = (String(value || "").match(/-?\d*\.?\d+(?:e-?\d+)?%?/g) || []).slice(0, 3);
    if (numbers.length < 3) return null;
    const unit = /^color\(/.test(value) ? 255 : 1;
    const channels = numbers.map(part => part.endsWith("%") ? parseFloat(part) * 2.55 : parseFloat(part) * unit);
    return channels.every(Number.isFinite) ? channels.map(channel => Math.max(0, Math.min(255, Math.round(channel)))) : null;
  }

  // A page in the other theme has the other theme's variables.
  function tokens(theme) {
    const fallback = FALLBACK[theme];
    if (!document.body || themeName() !== theme) return fallback;
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
      ground: read("--ground", fallback.ground), ink: read("--ink", fallback.ink),
      muted: read("--ink-3", fallback.muted), accent: read("--agree", fallback.accent)
    };
    probe.remove();
    return palette;
  }

  const hex = color => `#${color.map(channel => channel.toString(16).padStart(2, "0")).join("")}`;
  // `share` of `to` in `from`.
  const mix = (from, to, share) => hex(from.map((channel, index) => Math.round(channel + (to[index] - channel) * share)));

  // Monochrome like the app: shapes are a tone of the ground without a
  // frame, a group is a fainter tone behind them, lines and words are ink,
  // and the house green is the one accent (a chart's first series, the task
  // that runs, today's line). Mermaid derives what is not named here from
  // these, so a grey stays grey.
  function palette(theme) {
    const { ground, ink, muted, accent } = tokens(theme);
    return {
      dark: theme === "dark", ground, ink, paper: hex(ground), text: hex(ink), quiet: hex(muted), green: hex(accent),
      shape: mix(ground, ink, 0.075), group: mix(ground, ink, 0.035), hair: mix(ground, ink, 0.16),
      soft: mix(ground, ink, 0.1), bar: mix(ground, ink, 0.15), strong: mix(ground, ink, 0.72)
    };
  }

  function themeVariables(colors) {
    const { ground, ink, paper, text, quiet, green, shape, group, hair, soft, bar, strong } = colors;
    // Tones a label in ink stays readable on, neighbors apart: a pie's
    // slices, and lighter ones for the sections of a timeline or mind map.
    const ramp = [0.3, 0.14, 0.4, 0.2, 0.08, 0.34, 0.17, 0.26, 0.11, 0.37, 0.23, 0.05].map(share => mix(ground, ink, share));
    const sections = [0.1, 0.06, 0.14, 0.08, 0.12, 0.05, 0.11, 0.07, 0.13, 0.09, 0.15, 0.04].map(share => mix(ground, ink, share));
    const variables = {
      darkMode: colors.dark, background: paper, fontFamily: FONT, fontSize: "14px",
      // Flat: no shadow under a shape and no gradient in it.
      dropShadow: "none", useGradient: false,
      primaryColor: shape, primaryTextColor: text, primaryBorderColor: shape,
      secondaryColor: shape, secondaryTextColor: text, secondaryBorderColor: shape,
      tertiaryColor: group, tertiaryTextColor: text, tertiaryBorderColor: group,
      lineColor: quiet, textColor: text, titleColor: text, mainBkg: shape, nodeBorder: shape, nodeTextColor: text,
      clusterBkg: group, clusterBorder: group, edgeLabelBackground: group, arrowheadColor: quiet, defaultLinkColor: quiet,
      noteBkgColor: group, noteTextColor: text, noteBorderColor: group,
      actorBkg: shape, actorBorder: shape, actorTextColor: text, actorLineColor: hair, signalColor: quiet,
      signalTextColor: text, labelBoxBkgColor: shape, labelBoxBorderColor: shape, labelTextColor: text, loopTextColor: quiet,
      activationBkgColor: soft, activationBorderColor: soft, sequenceNumberColor: paper,
      sectionBkgColor: group, altSectionBkgColor: paper, sectionBkgColor2: group, gridColor: hair,
      taskBkgColor: bar, taskBorderColor: bar, taskTextColor: text,
      taskTextLightColor: text, taskTextDarkColor: text, taskTextOutsideColor: text, taskTextClickableColor: text,
      activeTaskBkgColor: green, activeTaskBorderColor: green, doneTaskBkgColor: shape, doneTaskBorderColor: shape,
      critBkgColor: strong, critBorderColor: strong, todayLineColor: green, vertLineColor: quiet,
      labelColor: text, errorBkgColor: shape, errorTextColor: text,
      classText: text, attributeBackgroundColorOdd: paper, attributeBackgroundColorEven: group,
      relationColor: quiet, relationLabelBackground: paper, relationLabelColor: text,
      transitionColor: quiet, transitionLabelColor: text, stateLabelColor: text, stateBkg: shape, labelBackgroundColor: paper,
      compositeBackground: group, compositeTitleBackground: shape, compositeBorder: group, innerEndBackground: quiet,
      specialStateColor: quiet, altBackground: group,
      pieStrokeColor: paper, pieStrokeWidth: "2px", pieOuterStrokeColor: paper, pieOuterStrokeWidth: "0px", pieOpacity: "1",
      pieTitleTextColor: text, pieSectionTextColor: text, pieLegendTextColor: text,
      pieTitleTextSize: "15px", pieSectionTextSize: "13px", pieLegendTextSize: "14px",
      quadrant1Fill: group, quadrant2Fill: paper, quadrant3Fill: group, quadrant4Fill: paper,
      quadrant1TextFill: quiet, quadrant2TextFill: quiet, quadrant3TextFill: quiet, quadrant4TextFill: quiet,
      quadrantPointFill: green, quadrantPointTextFill: text, quadrantXAxisTextFill: text, quadrantYAxisTextFill: text,
      quadrantInternalBorderStrokeFill: hair, quadrantExternalBorderStrokeFill: hair, quadrantTitleFill: text,
      xyChart: {
        backgroundColor: "transparent", titleColor: text, xAxisLabelColor: quiet, xAxisTitleColor: quiet,
        xAxisTickColor: hair, xAxisLineColor: hair, yAxisLabelColor: quiet, yAxisTitleColor: quiet, yAxisTickColor: hair,
        yAxisLineColor: hair, plotColorPalette: [green, quiet, ...ramp.slice(0, 6)].join(",")
      },
      gitInv0: paper, gitBranchLabel0: paper, commitLabelColor: text, commitLabelBackground: shape, tagLabelColor: text,
      tagLabelBackground: shape, tagLabelBorder: shape
    };
    ramp.forEach((color, index) => {
      variables[`pie${index + 1}`] = color;
      // A timeline underlines each box in cScaleInv: in its own tone, unseen.
      variables[`cScale${index}`] = sections[index];
      variables[`cScaleLabel${index}`] = text;
      variables[`cScaleInv${index}`] = sections[index];
      if (index < 8) {
        variables[`git${index}`] = index ? mix(ground, ink, 0.35 + index * 0.06) : green;
        variables[`gitBranchLabel${index}`] = paper;
      }
    });
    return variables;
  }

  // The app's own look on top of Mermaid's rules: shapes without a frame and
  // with round corners (tidy()), quiet lines, small grey axis words, titles
  // in the weight of a heading, a bar's words readable on its tone. A model's
  // own style rules stay out (LOCKED); these are the app's.
  function themeCSS(colors) {
    const { paper, text, quiet, hair } = colors;
    const range = names => [0, 1, 2, 3].map(index => names.map(name => `.${name}${index}`).join(",")).join(",");
    const inside = selector => selector.split(",").map(name => `${name}:not(.taskTextOutsideLeft):not(.taskTextOutsideRight)`).join(",");
    return [
      ".node rect,.node polygon,.node circle,.node ellipse,.node path,.node .outer-path,.cluster rect"
        + ",[data-look=neo].node rect,[data-look=neo].node polygon,[data-look=neo].node path,[data-look=neo].node circle"
        + ",[data-look=neo].cluster rect{stroke:none}",
      `.cluster-label text,.cluster text{fill:${quiet};font-weight:500}`,
      ".flowchart-link,.edgePaths .path,.transition,.relation{stroke-width:1.25px}",
      ".edgeLabel rect{opacity:1}",
      `.titleText,.flowchartTitleText,.sequenceTitleText,.pieTitleText{font-size:15px;font-weight:600;fill:${text}}`,
      // Gantt: tone bands, hairline grid, flat bars.
      ".section,.section1,.section3{opacity:1}",
      `.grid .tick line{stroke:${hair};opacity:1}`,
      `.grid .tick text{fill:${quiet};font-size:12px;stroke:none}`,
      "rect.task{stroke-width:0}",
      `.sectionTitle{fill:${quiet};font-weight:500}`,
      `${inside(range(["activeText", "critText", "activeCritText"]))}{fill:${paper}!important}`,
      ".today{stroke-width:1.5px}",
      // Sequence: tone boxes, hairline lifelines.
      `.actor{stroke:none}.actor-line{stroke:${hair}}.note{stroke:none}.labelBox{stroke:none}`,
      `.loopLine{stroke:${hair};stroke-width:1px}.messageLine0,.messageLine1{stroke-width:1.25px}`,
      `.labelText,.labelText>tspan,.loopText,.loopText>tspan{fill:${quiet}}`,
      // Charts and state diagrams.
      `.pieOuterCircle{stroke:none}.legend text{fill:${text}}`,
      `.lineWrapper line{stroke:${hair};stroke-width:1.5px}`,
      ".statediagram-state rect,.statediagram-cluster rect{stroke:none}"
    ].join("");
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

  // The app's Inter (see FONT): the Latin file every page preloads
  // (partials/font_preload.html), as a FontFace for measuring and as an
  // @font-face rule for the drawing. "" when there is none: system fonts.
  let font = null;
  function loadFont() {
    if (!font) {
      font = (async () => {
        const links = [...document.querySelectorAll('link[rel~="preload"][as="font"]')];
        const link = links.find(item => !/italic/i.test(item.href)) || links[0];
        if (!link || typeof FontFace !== "function" || !document.fonts || typeof fetch !== "function") return "";
        const response = await fetch(link.href, { credentials: "same-origin" });
        if (!response.ok) return "";
        const bytes = new Uint8Array(await response.arrayBuffer());
        const face = new FontFace(FAMILY, bytes, { weight: "100 900" });
        await face.load();
        document.fonts.add(face);
        return `@font-face{font-family:"${FAMILY}";src:url(data:font/woff2;base64,${base64(bytes)}) format("woff2");font-weight:100 900}`;
      })().catch(() => "");
    }
    return font;
  }

  // The width a drawing is laid out for: its place's, in steps.
  let lastWidth = 720;
  function span(width) {
    const value = Number(width) > 0 ? Number(width) : lastWidth;
    return Math.max(WIDTH_LEAST, Math.min(WIDTH_MOST, Math.floor(value / WIDTH_STEP) * WIDTH_STEP));
  }

  // Everything that depends on the width of the place: a Gantt chart and a
  // bar chart span it, where Mermaid would take the width of the whole
  // window, and a sequence on a phone has narrower participants.
  function settings(colors, width) {
    const narrow = width < 520;
    return {
      startOnLoad: false, securityLevel: "strict", suppressErrorRendering: true, secure: LOCKED,
      // Labels as SVG text: HTML labels sit in <foreignObject>, which Safari
      // misplaces inside an image.
      htmlLabels: false, theme: "base", themeVariables: themeVariables(colors), themeCSS: themeCSS(colors),
      fontFamily: FONT, fontSize: 14,
      // Mermaid 12 lays out with ELK unless told otherwise: 1.6 MB more to
      // load, with regex lookbehinds Safari before 16.4 cannot parse. Dagre
      // is in the core's reach and draws the same diagrams.
      layout: "dagre",
      // A label wraps at 200 px, where Mermaid 12 wraps at 120 and cut
      // "Mehrheitsbeschluss" in two; a word wider than this is still cut.
      flowchart: { useMaxWidth: false, wrappingWidth: 200, padding: 14, nodeSpacing: narrow ? 28 : 36,
        rankSpacing: narrow ? 36 : 44, diagramPadding: 8, subGraphTitleMargin: { top: 4, bottom: 6 } },
      gantt: { useMaxWidth: false, useWidth: Math.max(width, GANTT_LEAST), fontSize: 13, sectionFontSize: 13, barHeight: 26, barGap: 6,
        topPadding: 44, leftPadding: narrow ? 64 : 84, rightPadding: 12, gridLineStartPadding: 32, titleTopMargin: 22 },
      sequence: { useMaxWidth: false, mirrorActors: false, width: narrow ? 100 : 132, height: 40,
        actorMargin: narrow ? 20 : 40, boxMargin: 8, boxTextMargin: 4, noteMargin: 8, messageMargin: 32,
        actorFontSize: 14, messageFontSize: 14, noteFontSize: 13, diagramMarginX: 8, diagramMarginY: 8 },
      pie: { useMaxWidth: false, textPosition: 0.7 },
      xyChart: { useMaxWidth: false, width: Math.min(width, 720), height: Math.round(Math.max(240, Math.min(400, width * 0.56))),
        titleFontSize: 15, titlePadding: 12,
        xAxis: { labelFontSize: 13, titleFontSize: 13 }, yAxis: { labelFontSize: 13, titleFontSize: 13 } },
      timeline: { useMaxWidth: false }, mindmap: { useMaxWidth: false }, journey: { useMaxWidth: false },
      class: { useMaxWidth: false }, state: { useMaxWidth: false }, er: { useMaxWidth: false, fontSize: 13 },
      quadrantChart: { useMaxWidth: false, chartWidth: Math.min(width, 520), chartHeight: Math.min(width, 520) }
    };
  }

  let configured = "";
  function configure(mermaid, config) {
    const name = JSON.stringify(config);
    if (configured === name) return;
    mermaid.initialize(config);
    configured = name;
  }

  function base64(content) {
    const bytes = typeof content === "string" ? new TextEncoder().encode(content) : content;
    let binary = "";
    for (let index = 0; index < bytes.length; index += 0x8000) {
      binary += String.fromCharCode.apply(null, bytes.subarray(index, index + 0x8000));
    }
    return btoa(binary);
  }

  const SVG = "http://www.w3.org/2000/svg";

  // What Mermaid drew, tidied for the app: no frame or shadow of its own,
  // round corners on its boxes, and an axis that names each day once.
  // ``bottom`` is the lower edge of Mermaid's frame.
  function tidy(svg, bottom) {
    // Some kinds of diagram shade their shapes with a filter of their own,
    // whatever the theme says.
    svg.querySelectorAll("filter").forEach(node => node.remove());
    svg.querySelectorAll("[filter]").forEach(node => node.removeAttribute("filter"));
    svg.querySelectorAll("[style*='filter']").forEach(node => {
      node.setAttribute("style", node.getAttribute("style").replace(/(^|;)\s*filter\s*:[^;]*/gi, "$1"));
    });
    const round = (selector, radius) => svg.querySelectorAll(selector).forEach(node => {
      if (!(Number(node.getAttribute("rx")) > 0)) {
        node.setAttribute("rx", String(radius));
        node.setAttribute("ry", String(radius));
      }
    });
    round(".node rect.label-container, .node rect.basic, rect.actor, rect.note, rect.labelBox, .statediagram-state rect", 6);
    round(".cluster > rect, .statediagram-cluster rect", 10);
    round("rect.task, .edgeLabel rect.background", 4);
    // A timeline's title is set at 4ex in bold, larger than the answer's
    // headings.
    svg.querySelectorAll(":scope > text[font-size='4ex']").forEach(title => {
      title.setAttribute("font-size", "15");
      title.setAttribute("font-weight", "600");
    });
    // A sequence without its participants repeated below draws their
    // lifelines 2000 units long, far past its frame.
    svg.querySelectorAll("line.actor-line, line[data-et='life-line']").forEach(line => {
      if (Number(line.getAttribute("y2")) > bottom) line.setAttribute("y2", String(bottom - 4));
    });
    // A Gantt chart marks today with a line wherever today falls, also
    // months beside its bars, and the drawing grows to reach whatever has ink
    // (picture()): a chart of last spring came out too wide to draw at all.
    // The line stays only from its first bar's start to its last bar's end.
    let from = Infinity, to = -Infinity;
    svg.querySelectorAll("rect.task").forEach(bar => {
      const x = Number(bar.getAttribute("x")), width = Number(bar.getAttribute("width"));
      if (Number.isFinite(x) && Number.isFinite(width)) {
        from = Math.min(from, x);
        to = Math.max(to, x + width);
      }
    });
    svg.querySelectorAll("g.today").forEach(today => {
      const line = today.querySelector("line");
      const at = line ? Number(line.getAttribute("x1")) : NaN;
      if (!(at >= from - 1 && at <= to + 1)) today.remove();
    });
    // A Gantt chart's ticks every twelve hours under a format of days say
    // every day twice, and on a phone its dates run into each other: a tick
    // that repeats the one before or stands too close to it goes.
    let last = null;
    svg.querySelectorAll(".grid .tick").forEach(tick => {
      const label = tick.textContent.trim();
      const at = Number((/translate\(\s*(-?[\d.]+)/.exec(tick.getAttribute("transform") || "") || [])[1]);
      const room = last ? (last.label.length + label.length) * 3.6 + 10 : 0;
      if (label && last && (label === last.label || (Number.isFinite(at) && at - last.at < room))) tick.remove();
      else if (label) last = { label, at };
    });
  }

  // Where the drawing has ink, in its own units: measured in the page,
  // since a Gantt chart's words beside a bar and a long title can stand
  // outside the frame Mermaid gives it. The drawing is laid out in a hidden
  // place of the document for the moment it takes, as Mermaid laid it out to
  // draw it; what could load or run is gone before (picture()).
  function inked(svg) {
    const holder = document.createElement("div");
    holder.setAttribute("aria-hidden", "true");
    holder.style.cssText = "position:absolute;left:-100000px;top:0;width:0;height:0;overflow:hidden;visibility:hidden";
    holder.append(svg);
    document.body.append(holder);
    try {
      const box = svg.getBBox();
      return box && box.width > 0 && box.height > 0 ? box : null;
    } catch (_) {
      return null;
    } finally {
      holder.remove();
    }
  }

  // Mermaid's markup as an image of its own size, the app's font inside.
  // The template is an inert document, so nothing in the markup loads or
  // runs while it is read, and XMLSerializer writes what an image needs:
  // well-formed XML (Mermaid's string is HTML, with "&nbsp;" and unclosed
  // <br>).
  function picture(markup, fontRule) {
    const template = document.createElement("template");
    template.innerHTML = markup;
    const svg = template.content.querySelector("svg");
    if (!svg) throw new Error("diagram without a size");
    svg.querySelectorAll("script, foreignObject, image, iframe, object, embed").forEach(node => node.remove());
    svg.querySelectorAll("[href], [*|href]").forEach(node => {
      for (const name of ["href", "xlink:href"]) {
        if (node.hasAttribute(name) && !node.getAttribute(name).startsWith("#")) node.removeAttribute(name);
      }
    });
    const view = (svg.getAttribute("viewBox") || "").trim().split(/[\s,]+/).map(Number);
    if (view.length !== 4 || !view.every(Number.isFinite)) throw new Error("diagram without a size");
    tidy(svg, view[1] + view[3]);
    let [left, top, right, bottom] = [view[0], view[1], view[0] + view[2], view[1] + view[3]];
    const ink = inked(svg);
    if (ink) {
      // Grown to what stands out, never cut to less than Mermaid's frame.
      left = Math.min(left, ink.x - 4);
      top = Math.min(top, ink.y - 4);
      right = Math.max(right, ink.x + ink.width + 4);
      bottom = Math.max(bottom, ink.y + ink.height + 4);
    }
    const width = Math.ceil(right - left), height = Math.ceil(bottom - top);
    if (!(width > 0) || !(height > 0) || width > 20000 || height > 20000) throw new Error("diagram without a size");
    svg.setAttribute("viewBox", `${left} ${top} ${width} ${height}`);
    svg.setAttribute("width", String(width));
    svg.setAttribute("height", String(height));
    svg.removeAttribute("style");
    if (fontRule) {
      const style = document.createElementNS(SVG, "style");
      style.textContent = fontRule;
      svg.prepend(style);
    }
    const title = svg.querySelector(":scope > title");
    return {
      data: base64(new XMLSerializer().serializeToString(svg)), width, height,
      title: title ? title.textContent.trim().slice(0, 200) : ""
    };
  }

  // How large a drawing shows in a place of this width (diagram.css).
  function scaleIn(result, width) {
    return Math.min(1, width / result.width);
  }

  // A flowchart or timeline the other way round: left to right becomes top
  // to bottom and back. A long chain the model laid out sideways is too
  // wide for a phone; standing, it fits. "" for any other diagram.
  const FLOW_HEAD = /^(\s*)(flowchart|graph|timeline)(?:\s+(LR|RL|TD|TB|BT))?(\s*;?\s*)$/i;
  const TURN = { LR: "TD", RL: "BT", TD: "LR", TB: "LR", BT: "RL" };
  function turned(source) {
    const lines = String(source || "").split("\n");
    let index = 0;
    if (lines[0].trim() === "---") index = lines.findIndex((line, at) => at > 0 && line.trim() === "---") + 1 || lines.length;
    for (; index < lines.length; index += 1) {
      const line = lines[index].trim();
      if (!line || line.startsWith("%%")) continue;
      const head = lines[index].match(FLOW_HEAD);
      if (!head) return "";
      const timeline = head[2].toLowerCase() === "timeline";
      // A timeline knows LR and TD only, and runs sideways unless told.
      const way = (head[3] || (timeline ? "LR" : "TD")).toUpperCase();
      if (timeline && !["LR", "TD"].includes(way)) return "";
      lines[index] = `${head[1]}${head[2]} ${TURN[way]}${head[4]}`;
      return lines.join("\n");
    }
    return "";
  }

  // One drawing at a time: Mermaid's settings are global, and a theme or
  // width change between two drawings sets them anew. The colors are the
  // theme's when it was asked for: by the drawing's turn in the queue the
  // page may show the other one, and the drawing is kept under the theme it
  // was asked for.
  let queue = Promise.resolve();
  let serial = 0;
  function draw(source, theme, width) {
    const config = settings(palette(theme), width);
    const job = queue.then(async () => {
      const mermaid = await load().catch(() => { throw Object.assign(new Error("Mermaid did not load"), { again: true }); });
      const fontRule = await loadFont();
      configure(mermaid, config);
      const once = async text => {
        serial += 1;
        const result = await mermaid.render(`consens-diagram-${serial}`, text);
        return Object.assign(picture(result.svg, fontRule), { kind: kindOf(result.diagramType) });
      };
      const drawn = await once(source);
      const other = ["flowchart", "timeline"].includes(drawn.kind) && scaleIn(drawn, width) < TURN_BELOW ? turned(source) : "";
      if (other) {
        const standing = await once(other).catch(() => null);
        // The viewer (figureOf) shows whichever of the two fits its window.
        if (standing && scaleIn(standing, width) > scaleIn(drawn, width) + 0.1) return Object.assign(standing, { other: drawn });
      }
      return drawn;
    });
    queue = job.catch(() => {});
    return job;
  }

  // ---- Drawings by source ----------------------------------------------------
  // theme + width + source -> { state: "pending" | "drawn" | "failed", since, done, picture, kind, outcome, live }.
  const drawings = new Map();

  function request(source, theme, width) {
    theme = theme || themeName();
    const wide = span(width);
    const id = `${theme}\n${wide}\n${source}`;
    let entry = drawings.get(id);
    // A diagram Mermaid cannot read stays code; one whose Mermaid did not
    // arrive (the network) is tried again by a later look, not at once.
    if (entry && !(entry.again && Date.now() - entry.since > RETRY_MS)) return entry;
    entry = { state: "pending", since: Date.now(), picture: null, done: null, again: false, live: false,
      kind: sourceKind(source), outcome: "" };
    drawings.set(id, entry);
    for (const old of drawings.keys()) {
      if (drawings.size <= DRAWINGS_KEPT) break;
      if (drawings.get(old).state !== "pending") drawings.delete(old);
    }
    const work = source.trim() && source.length <= MAX_SOURCE_CHARS && !loadsImage(source) ? draw(source, theme, wide)
      : Promise.reject(Object.assign(new Error("no diagram"), { refused: true }));
    entry.done = work.then(result => {
      entry.state = "drawn";
      entry.picture = result;
      entry.kind = result.kind;
      entry.outcome = "drawn";
      rememberSize(source, wide, result);
    }, error => {
      entry.state = "failed";
      entry.again = Boolean(error && error.again);
      entry.outcome = entry.again ? "load" : error && error.refused ? "refused" : "syntax";
      entry.since = Date.now();
    }).then(() => { if (entry.live) report(source, entry); });
    return entry;
  }

  // The stream's question (markdown-stream.js streamHold): whether the text
  // after this diagram may show, which is once it is drawn, failed or late.
  // Only an answer that is being written asks, so this is also where a
  // diagram counts as one a model just wrote. The block's place is already
  // on the page: the drawing asked for is the one for its width.
  function settled(source) {
    const text = String(source || "");
    const place = document.querySelector(`.md-diagram[data-diagram="${key(text)}"]`);
    const entry = request(text, "", place ? widthOf(place) : 0);
    entry.live = true;
    report(text, entry);
    return entry.state !== "pending" || Date.now() - entry.since > HOLD_MS;
  }

  // ---- Counting ---------------------------------------------------------------
  // How often a model's diagram is drawn and how often Mermaid cannot read
  // it (docs/analytics.md, app_diagram): once per diagram of an answer being
  // written, never for a chat opened later. Its kind is one of Mermaid's
  // names, never a word of the model's.
  const KINDS = ["flowchart", "sequence", "class", "state", "er", "gantt", "pie", "xychart", "mindmap", "timeline",
    "quadrant", "sankey", "git", "journey", "c4", "requirement", "block", "kanban", "architecture", "packet", "radar",
    "treemap"];
  function kindOf(name) {
    const word = String(name || "").toLowerCase().replace(/[^a-z0-9]/g, "");
    if (word.startsWith("graph")) return "flowchart";
    return KINDS.find(kind => word.startsWith(kind)) || "other";
  }
  // The kind a source names in its first line, after its front matter and
  // its "%%" lines: what a block that could not be drawn was meant to be.
  function sourceKind(source) {
    const lines = String(source || "").split("\n");
    let index = 0;
    if (lines[0].trim() === "---") index = lines.findIndex((line, at) => at > 0 && line.trim() === "---") + 1 || lines.length;
    for (; index < lines.length; index += 1) {
      const line = lines[index].trim();
      if (line && !line.startsWith("%%")) return kindOf(line.split(/[^A-Za-z0-9-]/)[0]);
    }
    return "other";
  }

  const reported = new Set();
  function report(source, entry) {
    const name = key(source);
    if (entry.state === "pending" || reported.has(name) || typeof window.trackUmamiEvent !== "function") return;
    reported.add(name);
    window.trackUmamiEvent("app_diagram", { kind: entry.kind, outcome: entry.outcome });
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
  // its size from the first frame and nothing below it moves. Kept by the
  // width it was laid out for, which may change its shape.
  function sizes() {
    try {
      const stored = JSON.parse(localStorage.getItem(SIZES_KEY) || "{}");
      return stored && typeof stored === "object" && !Array.isArray(stored) ? stored : {};
    } catch (_) { return {}; }
  }
  function rememberSize(source, wide, result) {
    try {
      const stored = sizes();
      const name = `${key(source)}@${wide}`;
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
  // The answer around a diagram is the model's and never translated, its
  // attributes included (data-i18n-skip, i18n.js): the app's own words in
  // it go through App.t here.
  function say(text) {
    return window.App && window.App.t ? window.App.t(text) : text;
  }

  function sourceOf(place) {
    const code = place.querySelector(":scope > pre > code");
    return code ? code.textContent.replace(/\n$/, "") : "";
  }

  // The width a place offers its drawing; one not laid out yet (a hidden
  // panel) is taken to be as wide as the last place that was.
  function widthOf(place) {
    const width = place.clientWidth;
    if (width > 0) lastWidth = width;
    return width > 0 ? width : lastWidth;
  }

  // The viewer gets whichever of the two layouts of a turned flowchart
  // (draw()) is larger in a window of this size: the model's own sideways
  // one has room there.
  function forViewer(shown) {
    if (!shown.other) return shown;
    const room = [Math.max(200, window.innerWidth - 64), Math.max(200, window.innerHeight - 120)];
    const fit = result => Math.min(room[0] / result.width, room[1] / result.height);
    return fit(shown.other) > fit(shown) ? shown.other : shown;
  }

  // ---- Enlarged ---------------------------------------------------------------
  // A public page (Share, Watch) has no viewer of the app's: a dialog of its
  // own shows the drawing as large as the window allows, up to twice its
  // size. One that would be too small to read there (diagram.css,
  // --diagram-min-scale) stands at the readable size and scrolls in the
  // dialog, by touch, wheel or the arrow keys. Escape, the cross and a
  // click beside it close it; the focus goes back to the diagram.
  const GROWS = 2;
  const READABLE = 0.75;
  let ownViewer = null;
  function viewerOfPage() {
    if (ownViewer) return ownViewer;
    const dialog = document.createElement("dialog");
    dialog.className = "md-diagram-viewer";
    const close = document.createElement("button");
    close.type = "button";
    close.className = "md-diagram-viewer-close";
    close.setAttribute("aria-label", say("Close preview"));
    close.innerHTML = '<svg viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M4 4l8 8M12 4l-8 8"/></svg>';
    const stage = document.createElement("div");
    stage.className = "md-diagram-viewer-stage";
    stage.tabIndex = 0;
    const image = document.createElement("img");
    image.alt = "";
    stage.append(image);
    dialog.append(close, stage);
    close.addEventListener("click", () => dialog.close());
    dialog.addEventListener("click", event => { if (event.target === dialog) dialog.close(); });
    dialog.addEventListener("close", () => {
      const back = ownViewer.opener;
      ownViewer.opener = null;
      if (back && back.isConnected) back.focus({ preventScroll: true });
    });
    document.body.append(dialog);
    ownViewer = { dialog, stage, image, opener: null };
    return ownViewer;
  }
  function enlarge(shown, opener) {
    const viewer = viewerOfPage();
    const { dialog, stage, image } = viewer;
    viewer.opener = opener;
    dialog.setAttribute("aria-label", shown.title || say("Diagram"));
    image.alt = shown.title || say("Diagram");
    image.src = `data:image/svg+xml;base64,${shown.data}`;
    if (!dialog.open) dialog.showModal();
    const room = [Math.max(120, stage.clientWidth - 32), Math.max(120, stage.clientHeight - 32)];
    const fit = Math.min(room[0] / shown.width, room[1] / shown.height, GROWS);
    const scale = Math.max(fit, READABLE);
    image.style.width = `${Math.round(shown.width * scale)}px`;
    image.style.height = `${Math.round(shown.height * scale)}px`;
    stage.scrollTo(0, 0);
    stage.focus({ preventScroll: true });
  }

  // The field the diagram is drawn into (diagram.css): there from the first
  // frame, so the drawing takes the place of its field, not room below it.
  // A click enlarges it: in /app in the picture viewer (attachments.js),
  // elsewhere in a dialog of its own (enlarge()).
  function figureOf(place) {
    let figure = place.querySelector(":scope > .md-diagram-figure");
    if (figure) return figure;
    figure = document.createElement("div");
    figure.className = "md-diagram-figure";
    const image = document.createElement("img");
    image.alt = "";
    const open = document.createElement("button");
    open.type = "button";
    open.className = "md-diagram-open";
    open.setAttribute("aria-label", say("Open diagram"));
    open.disabled = true;
    open.append(image);
    open.addEventListener("click", () => {
      const shown = place._diagram && forViewer(place._diagram);
      if (!shown) return;
      const viewer = window.App && window.App.attachments && window.App.attachments.openStored;
      if (viewer) {
        viewer({ name: "diagram.svg", title: shown.title || say("Diagram"), mime: "image/svg+xml", data: shown.data,
          drawing: true, trigger: open });
      } else if (typeof HTMLDialogElement === "function") {
        enlarge(shown, open);
      }
    });
    figure.append(open);
    place.prepend(figure);
    return figure;
  }

  // A drawing wider than its place pans sideways in it (diagram.css). A side
  // that hides more of it fades out instead of ending in a cut, so the reader
  // sees that it goes on; the classes follow the place's size and scroll.
  // A place that grows or shrinks by a step (a turned phone, a panel
  // opened beside the chat) gets the drawing for its new width once it has
  // settled.
  function watchPan(place) {
    if (place._diagramPan) return;
    let later = 0;
    place._diagramPan = () => {
      const hidden = place.scrollWidth - place.clientWidth;
      place.classList.toggle("is-cut-start", hidden > 1 && place.scrollLeft > 1);
      place.classList.toggle("is-cut-end", hidden > 1 && place.scrollLeft < hidden - 1);
    };
    place.addEventListener("scroll", place._diagramPan, { passive: true });
    if (typeof ResizeObserver === "function") {
      new ResizeObserver(() => {
        place._diagramPan();
        clearTimeout(later);
        if (place.clientWidth > 0 && place.isConnected && span(place.clientWidth) !== place._diagramSpan) {
          later = setTimeout(() => { if (place.isConnected) fill(place); }, 200);
        }
      }).observe(place);
    }
    place._diagramPan();
  }

  function show(place, result, theme, wide) {
    const figure = figureOf(place);
    const image = figure.querySelector("img");
    const open = figure.querySelector(".md-diagram-open");
    if (open) open.disabled = false;
    place._diagram = result;
    image.alt = result.title || say("Diagram");
    image.src = `data:image/svg+xml;base64,${result.data}`;
    setSize(place, result.width, result.height);
    place.dataset.drawn = theme;
    place._diagramSpan = wide;
    place.classList.remove("is-code");
    place.classList.add("is-drawn");
    watchPan(place);
  }

  function fill(place) {
    const theme = themeName();
    const wide = span(widthOf(place));
    if (place.dataset.drawn === theme && place._diagramSpan === wide) return;
    const entry = request(sourceOf(place), theme, wide);
    if (entry.state === "drawn") {
      show(place, entry.picture, theme, wide);
    } else if (entry.state === "failed") {
      // What Mermaid cannot read stays what the model wrote: a code block.
      if (!place.dataset.drawn) place.classList.add("is-code");
    } else if (!place._diagramWaits) {
      if (!place.dataset.drawn) {
        const known = sizes()[`${place.dataset.diagram}@${wide}`];
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
