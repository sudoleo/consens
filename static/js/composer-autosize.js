// Owns the question field's height, its multiline layout and width changes.
//
// Head bundle (render-blocking, no DOM work at load): app-bootstrap.js sizes
// a question that waits in the field before the first paint
// (App.sizeQuestionInput). app-init installs the listeners once
// (App.initComposerAutosize); App.resizeQuestionInput remains the public
// trigger.
//
// The text is measured in a hidden twin with the field's sizing styles, not
// in the field itself. Measuring the field at height 0 made it, and the page
// with it, a moment shorter on every key press (a reader at the end of a long
// chat was pulled up by the scroll clamp, Apple audit A12), and it gave the
// height no start value to glide from: the start field now grows downward in
// one soft step per line (composer.css, Apple audit B5).
(function () {
  window.App = window.App || {};
  const MULTILINE = "is-multiline";
  // Everything that decides how tall the same text sets.
  const SIZING = ["box-sizing", "padding-top", "padding-right", "padding-bottom", "padding-left",
    "border-top-width", "border-right-width", "border-bottom-width", "border-left-width", "border-top-style",
    "border-right-style", "border-bottom-style", "border-left-style", "font-family", "font-size", "font-weight",
    "font-style", "font-stretch", "font-variant", "font-feature-settings", "font-kerning", "letter-spacing",
    "word-spacing", "line-height", "text-indent", "text-transform", "text-rendering", "white-space",
    "word-break", "overflow-wrap", "tab-size", "direction"];
  let twin = null;

  function twinFor(input) {
    if (twin?.isConnected) return twin;
    twin = document.createElement("textarea");
    twin.className = "input-field-twin";
    twin.setAttribute("aria-hidden", "true");
    twin.tabIndex = -1;
    twin.readOnly = true;
    twin.rows = 1;
    Object.assign(twin.style, {
      position: "absolute", top: "0", left: "-10000px", height: "0", minHeight: "0", maxHeight: "none",
      overflow: "hidden", visibility: "hidden", pointerEvents: "none", resize: "none",
      // Its own layout stays apart from the page's (size containment would
      // hide the very height it measures).
      contain: "layout style",
    });
    (input.ownerDocument.body || input.ownerDocument.documentElement).append(twin);
    return twin;
  }

  function measure(input) {
    const styles = window.getComputedStyle(input);
    const mirror = twinFor(input);
    for (const name of SIZING) mirror.style.setProperty(name, styles.getPropertyValue(name));
    mirror.style.width = `${input.getBoundingClientRect().width}px`;
    // An empty field is as tall as its hint (scrollHeight includes it).
    mirror.placeholder = input.value ? "" : input.placeholder;
    mirror.value = input.value;
    const minHeight = Number.parseFloat(styles.minHeight) || 52;
    const maxHeight = Number.parseFloat(styles.maxHeight) || 220;
    const contentHeight = mirror.scrollHeight;
    return { minHeight, maxHeight, contentHeight, nextHeight: Math.max(minHeight, Math.min(contentHeight, maxHeight)) };
  }

  // instant: no glide (first paint, a width or state change); only typing
  // lets the field grow softly.
  function apply(input, instant) {
    const measured = measure(input);
    const height = `${Math.ceil(measured.nextHeight)}px`;
    const overflow = measured.contentHeight > measured.maxHeight + 1 ? "auto" : "hidden";
    if (input.style.overflowY !== overflow) input.style.overflowY = overflow;
    if (input.style.height !== height) {
      if (instant) {
        input.style.transition = "none";
        input.style.height = height;
        // The new height is the style the next transition starts from.
        void window.getComputedStyle(input).transitionDuration;
        input.style.transition = "";
      } else input.style.height = height;
    }
    return measured;
  }

  function sizeQuestionInput(input, options = {}) {
    if (!input || !input.isConnected) return null;
    const instant = options.instant !== false;
    const measured = apply(input, instant);
    const container = input.closest(".chat-input-container");
    if (!container) return measured;

    // Ab der zweiten Zeile bekommt der Text die ganze Breite und die
    // Knopfzeile rutscht darunter (Optik in composer.css, nur Desktop —
    // Mobile ist aufgeklappt ohnehin schon so gebaut).
    //
    // Zurueck geht es NUR beim leeren Feld, und das ist Absicht: das
    // Umschalten aendert die Breite des Feldes, und derselbe Text
    // braucht breit oft eine Zeile weniger als schmal. Eine Bedingung,
    // die selbst von dieser Breite abhaengt, wuerde in diesem
    // Zwischenbereich bei jedem Tastendruck zwischen beiden Formen
    // hin- und herspringen. Leer/nicht leer ist in beiden Breiten
    // dasselbe und damit der einzige stabile Ausstieg.
    const isMultiline = container.classList.contains(MULTILINE);
    const wantsMultiline = input.value.length > 0 &&
      (isMultiline || measured.nextHeight > measured.minHeight + 1);
    if (wantsMultiline !== isMultiline) {
      container.classList.toggle(MULTILINE, wantsMultiline);
      // Die neue Breite ergibt eine andere Zeilenzahl — ohne zweite
      // Messung bliebe die Hoehe der alten Form bis zum naechsten
      // Tastendruck stehen.
      return apply(input, true);
    }
    return measured;
  }
  window.App.sizeQuestionInput = sizeQuestionInput;

  window.App.initComposerAutosize = function (questionInput) {
    if (!questionInput) return () => {};
    const resizeQuestionInput = () => sizeQuestionInput(questionInput);

    // Typing measures once per frame, before it is painted and after every
    // other write of the task: sending clears the field in the same click
    // that builds the thread, and a measurement in between forced the whole
    // new layout once more (Apple-Audit D3).
    let inputFrame = null;
    questionInput.addEventListener("input", () => {
      if (inputFrame !== null) return;
      inputFrame = requestAnimationFrame(() => {
        inputFrame = null;
        sizeQuestionInput(questionInput, { instant: false });
      });
    });
    window.addEventListener("resize", resizeQuestionInput, { passive: true });
    // Empty textarea scrollHeight includes its placeholder. Only a new hint
    // counts: the same words written again (the Agent's composer does it on
    // every key press) re-measured at once and cut the soft growth short.
    let placeholder = questionInput.placeholder;
    new MutationObserver(() => {
      if (questionInput.placeholder === window.App.t(placeholder)) return;
      placeholder = questionInput.placeholder;
      resizeQuestionInput();
    }).observe(questionInput, { attributes: true, attributeFilter: ["placeholder"] });

    // A viewport or sidebar change can animate the available width after the
    // window resize event. Re-measure each actual width, including its final
    // value. Ignore height-only notifications from our own writes.
    let previousWidth = questionInput.getBoundingClientRect().width;
    let widthFrame = null;
    if (typeof ResizeObserver === "function") {
      new ResizeObserver(() => {
        const width = questionInput.getBoundingClientRect().width;
        if (width === previousWidth) return;
        previousWidth = width;
        if (widthFrame !== null) return;
        widthFrame = requestAnimationFrame(() => {
          widthFrame = null;
          resizeQuestionInput();
        });
      }).observe(questionInput);
    }
    requestAnimationFrame(resizeQuestionInput);
    return resizeQuestionInput;
  };
})();
