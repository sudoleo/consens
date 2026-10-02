// Owns textarea height, multiline layout and responsive width changes.
// app-init installs it once; App.resizeQuestionInput remains the public trigger.
(function () {
  window.App = window.App || {};
  window.App.initComposerAutosize = function (questionInput) {
    if (!questionInput) return () => {};
    const COMPOSER_MULTILINE_CLASS = "is-multiline";

    function measureQuestionInput() {
      questionInput.style.height = "0px";
      questionInput.style.overflowY = "hidden";
      const styles = window.getComputedStyle(questionInput);
      const minHeight = Number.parseFloat(styles.minHeight) || 52;
      const maxHeight = Number.parseFloat(styles.maxHeight) || 220;
      const contentHeight = questionInput.scrollHeight;
      const nextHeight = Math.max(minHeight, Math.min(contentHeight, maxHeight));

      questionInput.style.height = `${Math.ceil(nextHeight)}px`;
      questionInput.style.overflowY = contentHeight > maxHeight + 1 ? "auto" : "hidden";
      return { minHeight, nextHeight };
    }

    function resizeQuestionInput() {
      if (!questionInput) return;

      const measured = measureQuestionInput();
      const container = questionInput.closest(".chat-input-container");
      if (!container) return;

      // Ab der zweiten Zeile bekommt der Text die ganze Breite und die
      // Knopfzeile rutscht darunter (Optik in shell.css, nur Desktop —
      // Mobile ist aufgeklappt ohnehin schon so gebaut).
      //
      // Zurueck geht es NUR beim leeren Feld, und das ist Absicht: das
      // Umschalten aendert die Breite des Feldes, und derselbe Text
      // braucht breit oft eine Zeile weniger als schmal. Eine Bedingung,
      // die selbst von dieser Breite abhaengt, wuerde in diesem
      // Zwischenbereich bei jedem Tastendruck zwischen beiden Formen
      // hin- und herspringen. Leer/nicht leer ist in beiden Breiten
      // dasselbe und damit der einzige stabile Ausstieg.
      const isMultiline = container.classList.contains(COMPOSER_MULTILINE_CLASS);
      const wantsMultiline = questionInput.value.length > 0 &&
        (isMultiline || measured.nextHeight > measured.minHeight + 1);

      if (wantsMultiline !== isMultiline) {
        container.classList.toggle(COMPOSER_MULTILINE_CLASS, wantsMultiline);
        // Die neue Breite ergibt eine andere Zeilenzahl — ohne zweite
        // Messung bliebe die Hoehe der alten Form bis zum naechsten
        // Tastendruck stehen.
        measureQuestionInput();
      }
    }

    questionInput.addEventListener("input", resizeQuestionInput);
    window.addEventListener("resize", resizeQuestionInput, { passive: true });
    // Empty textarea scrollHeight includes its placeholder.
    new MutationObserver(resizeQuestionInput).observe(questionInput,
      { attributes: true, attributeFilter: ["placeholder"] });

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
