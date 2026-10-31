// =====================================================================
// math-render.js
// Gemeinsame LaTeX-Darstellung fuer App- und Share-Seiten.
// KaTeX + auto-render werden davor aus static/vendor geladen; auf
// oeffentlichen Seiten nur bei einer Formel, sonst bei Bedarf von hier.
// Export: window.ConsensusMath.{prepareMarkdown,render}.
// =====================================================================

(function initConsensusMath() {
  "use strict";

  const delimiters = [
    { left: "$$", right: "$$", display: true },
    { left: "\\(", right: "\\)", display: false },
    { left: "\\begin{equation}", right: "\\end{equation}", display: true },
    { left: "\\begin{align}", right: "\\end{align}", display: true },
    { left: "\\begin{alignat}", right: "\\end{alignat}", display: true },
    { left: "\\begin{gather}", right: "\\end{gather}", display: true },
    { left: "\\begin{CD}", right: "\\end{CD}", display: true },
    { left: "\\[", right: "\\]", display: true }
  ];

  // Zusammenhaengende Formelabschnitte in den von KaTeX erkannten Formen.
  const MATH_SPAN_RE = new RegExp(
    "\\$\\$[\\s\\S]*?\\$\\$"
    + "|\\\\\\[[\\s\\S]*?\\\\\\]"
    + "|\\\\\\([\\s\\S]*?\\\\\\)"
    + "|\\\\begin\\{(equation|align|alignat|gather|CD)\\*?\\}"
    + "[\\s\\S]*?\\\\end\\{\\1\\*?\\}",
    "g"
  );

  // Inline-Math als "$...$" ist die Schreibweise, die die Modelle am
  // haeufigsten liefern - KaTeX kennt sie ab Werk NICHT, und genau dasselbe
  // Zeichen steht in denselben Antworten als Waehrung ("6,7 Mrd. $ in Q1
  // gegenueber 6,7 Mrd. $ in Q2"). Wer "$" einfach als Trennzeichen
  // registriert, macht aus dem Text zwischen zwei Betraegen eine Formel.
  // Erkannt wird deshalb nur ein Paar, das eindeutig Formel ist: der Inhalt
  // liegt ohne Leerzeichen an beiden Dollarzeichen an, bleibt in einer Zeile,
  // ist kurz und enthaelt mindestens ein LaTeX-Signal (\befehl, ^, _, {}).
  // Das letzte Zeichen vor dem schliessenden "$" ist weder Leerraum noch
  // Backslash: dafuer steht ein eigenes Schlusselement, kein Lookbehind -
  // Safari/iOS unter 16.4 kann Lookbehind nicht parsen und verwirft dann das
  // ganze App-Bundle (tests/js/frontend-syntax.test.mjs haelt das fest).
  const DOLLAR_INLINE_RE =
    /(^|[^\\$\w])\$(?!\s)((?:[^$\n\\]|\\[^\n])*?(?:[^$\s\\]|\\[^\s\\]))\$(?![\w$])/g;
  const LATEX_SIGNAL_RE = /\\[A-Za-z]|[\^_{}]/;
  const MAX_INLINE_MATH_CHARS = 200;

  function dollarInlineToParens(text) {
    return String(text).replace(
      DOLLAR_INLINE_RE,
      function (match, before, body) {
        if (body.length > MAX_INLINE_MATH_CHARS) return match;
        if (!LATEX_SIGNAL_RE.test(body)) return match;
        return before + "\\(" + body + "\\)";
      }
    );
  }

  // Manche Modelle lassen die Backslashes von "\[ ... \]" weg und schreiben
  // "[ P(\text{a}\mid b) = \frac12. ]" - im Text stand dann die Formel als
  // Quelltext in eckigen Klammern. Als abgesetzte Formel gilt nur ein Paar,
  // das innen an beiden Klammern Leerraum hat, einen \befehl enthaelt, keine
  // Leerzeile ueberspannt und kein Link/Quellenverweis ist ("[S1]", "[x](url)").
  const BARE_DISPLAY_RE =
    /(^|[^\\\]\w])\[(\s+)((?:[^[\]\n]|\n(?![ \t]*\n))+?)(\s+)\](?![(\[:])/g;
  const MAX_DISPLAY_MATH_CHARS = 2000;

  function bareBracketsToDisplay(text) {
    return String(text).replace(
      BARE_DISPLAY_RE,
      function (match, before, open, body, close) {
        if (body.length > MAX_DISPLAY_MATH_CHARS) return match;
        if (!/\\[A-Za-z]/.test(body)) return match;
        return before + "\\[" + open + body + close + "\\]";
      }
    );
  }

  // Manche Modelle schreiben Formeln ganz ohne Trennzeichen: "O(2^{εn})",
  // "2^{n^{o(1)}}", "s_{k}" (DeepSeek V4.1 Flash, 2026-10-31) - im Text
  // standen dann Klammern und Dach als Quelltext. Ein Exponent oder Index in
  // TeX-Klammern kommt in normalem Text nicht vor; als Formel gilt deshalb
  // nur eine Kette aus Basis und Hoch-/Tiefstellungen, in der mindestens ein
  // "^{...}" oder "_{...}" steckt. Blankes "n^2" oder "s_k" bleibt Text: es
  // liest sich auch so, und "_" steht in Bezeichnern ("max_tokens"). Woerter
  // mit Adresse ("://", "](", "@") bleiben unangetastet.
  const BARE_SCRIPT_RE = /[\^_]\{/g;
  const ADDRESS_WORD_RE = /\S*(?::\/\/|\]\(|@)\S*/g;
  const BASE_CHAR_RE = /[\p{L}\p{N}]/u;
  const SCRIPT_TOKEN_RE = /^(?:-?\d+|[\p{L}\p{N}])/u;

  // Ende der geschweiften Klammer, die bei "open" beginnt, in derselben Zeile.
  function closingBrace(text, open) {
    let depth = 0;
    for (let i = open; i < text.length && text[i] !== "\n"; i++) {
      if (text[i] === "{") depth++;
      else if (text[i] === "}" && --depth === 0) return i + 1;
    }
    return -1;
  }

  function openingParen(text, close, floor) {
    let depth = 0;
    for (let i = close; i >= floor && text[i] !== "\n"; i--) {
      if (text[i] === ")") depth++;
      else if (text[i] === "(" && --depth === 0) return i;
    }
    return -1;
  }

  // Basis vor dem ersten Hoch-/Tiefzeichen: ein Wort ("2", "log", "\sum"),
  // eine Klammer ("(n+1)", "f(x)") und davor stehende blanke Indizes
  // ("x_i^{2}"). -1, wenn keine Basis davorsteht.
  function scriptBase(text, at, floor) {
    let base = -1;
    let start = at;
    for (;;) {
      let i = start;
      if (text[i - 1] === ")") {
        i = openingParen(text, i - 1, floor);
        if (i < 0) return base;
      }
      const wordEnd = i;
      while (i > floor && BASE_CHAR_RE.test(text[i - 1])) i--;
      if (i < wordEnd && i > floor && text[i - 1] === "\\") i--;
      if (i === start) return base;
      base = i;
      if ((text[i - 1] !== "^" && text[i - 1] !== "_") || i - 1 <= floor) return base;
      start = i - 1;
    }
  }

  // Ende der Kette ab "at": "^{...}", "_{...}", "^2", "^-3", "_i" in Folge.
  function scriptChainEnd(text, at) {
    let end = at;
    while (text[end] === "^" || text[end] === "_") {
      let next;
      if (text[end + 1] === "{") {
        next = closingBrace(text, end + 1);
      } else {
        const token = SCRIPT_TOKEN_RE.exec(text.slice(end + 1, end + 12));
        next = token ? end + 1 + token[0].length : -1;
      }
      if (next < 0) break;
      end = next;
    }
    return end;
  }

  function wrapScriptChains(text) {
    let out = "";
    let cursor = 0;
    let match;
    BARE_SCRIPT_RE.lastIndex = 0;
    while ((match = BARE_SCRIPT_RE.exec(text)) !== null) {
      const start = scriptBase(text, match.index, cursor);
      if (start < 0) continue;
      const end = scriptChainEnd(text, match.index);
      if (end === match.index || end - start > MAX_INLINE_MATH_CHARS) continue;
      out += text.slice(cursor, start) + "\\(" + text.slice(start, end) + "\\)";
      cursor = end;
      BARE_SCRIPT_RE.lastIndex = end;
    }
    return out + text.slice(cursor);
  }

  function bareScriptsToInline(text) {
    const source = String(text);
    if (!/[\^_]\{/.test(source)) return source;
    let out = "";
    let cursor = 0;
    let match;
    ADDRESS_WORD_RE.lastIndex = 0;
    while ((match = ADDRESS_WORD_RE.exec(source)) !== null) {
      out += wrapScriptChains(source.slice(cursor, match.index)) + match[0];
      cursor = match.index + match[0].length;
    }
    return out + wrapScriptChains(source.slice(cursor));
  }

  function keepMath(math) { return math; }

  function toKatexDelimiters(text) {
    return withMathSegments(
      bareBracketsToDisplay(dollarInlineToParens(text)),
      keepMath,
      bareScriptsToInline
    );
  }

  // Innerhalb einer Formel ist Markdown kein Markup, sondern Notation.
  // Markdown frisst aber jeden Backslash vor einem Satzzeichen: aus
  // "17{,}5\%" wird "17{,}5%" - und das Prozentzeichen leitet in TeX einen
  // Kommentar ein. Die Formel verlor also stillschweigend ihr Ergebnis.
  // Ein verdoppelter Backslash ueberlebt den Markdown-Pass als einer;
  // Alle ASCII-Satzzeichen schuetzen: ein alleinstehendes "=" macht sonst
  // die vorige Formelzeile zur Setext-Ueberschrift. Auch Listen, Tabellen,
  // Links und HTML duerfen einen Formelabschnitt nicht in DOM-Knoten teilen.
  function escapeMathSegment(segment) {
    return segment.replace(/[!-/:-@\x5b-\x60{-~]/g, "\\$&");
  }

  function prepareMarkdown(markdown) {
    // Code bleibt unangetastet: dort ist "$" ein Zeichen und kein Trenner.
    const codeSegments = /(```[\s\S]*?(?:```|$)|`[^`\n]*`)/g;
    return String(markdown || "")
      .split(codeSegments)
      .map(function (part, index) {
        if (index % 2) return part;
        // Erst die Dollar-Schreibweise auf die KaTeX-Form bringen, dann alle
        // Formelabschnitte gegen den Markdown-Pass schuetzen. Was ausserhalb
        // einer Formel steht, behaelt die alte, konservative Behandlung:
        // ein einzelnes "\(" bleibt sichtbar, statt zu "(" zu verkuemmern.
        return withMathSegments(
          toKatexDelimiters(part),
          escapeMathSegment,
          function (plain) { return plain.replace(/\\([\[\]()])/g, "\\\\$1"); }
        );
      })
      .join("");
  }

  function withMathSegments(text, onMath, onPlain) {
    let out = "";
    let cursor = 0;
    let match;
    MATH_SPAN_RE.lastIndex = 0;
    while ((match = MATH_SPAN_RE.exec(text)) !== null) {
      out += onPlain(text.slice(cursor, match.index)) + onMath(match[0]);
      cursor = match.index + match[0].length;
    }
    return out + onPlain(text.slice(cursor));
  }

  // Eine gerenderte Formel ist im DOM ein .katex-Block und damit fuer jede
  // Textsuche unsichtbar. Der gespeicherte Anker traegt dagegen den
  // LaTeX-QUELLTEXT - ein Satz mit Formel fand seine Stelle im Konsens
  // deshalb nie und landete samt Rohtext in der Key-claims-Liste. Diese
  // Fassung laesst die Formel weg und passt damit wieder auf den sichtbaren
  // Text. "" heisst: keine Formel enthalten, es gibt nichts zu ergaenzen.
  function stripMath(value) {
    const source = String(value || "");
    const stripped = withMathSegments(
      toKatexDelimiters(source),
      function () { return " "; },
      function (plain) { return plain; }
    );
    return stripped === source ? "" : stripped;
  }

  // Ein blanker LaTeX-Ausdruck OHNE Trennzeichen. So stehen abgesetzte
  // Formeln in Ankern aus alten Laeufen: gespeichert wurde die Zeile
  // zwischen den "$$", nicht der Block - "6{,}7 / 5{,}7 - 1 \approx 17{,}5\%"
  // steht seitdem als Quelltext in der Key-claims-Liste. Nachtraeglich als
  // Formel gelesen wird das nur, wenn NICHTS ausser LaTeX darin steht: ein
  // einziges Wort gewoehnlichen Textes laesst den Anker Text bleiben.
  const LATEX_LEFTOVER_RE = /\\[A-Za-z]+|[\s\d{}[\]()^_+\-*/=<>.,:;|&~!%'"\\]/g;

  function wrapBareLatex(value) {
    const source = String(value || "").trim();
    if (!source || source.length > MAX_INLINE_MATH_CHARS) return "";
    if (source.indexOf("$") !== -1 || /\\[([]/.test(source)) return "";
    if (!LATEX_SIGNAL_RE.test(source)) return "";
    if (source.replace(LATEX_LEFTOVER_RE, "")) return "";
    return "\\(" + source + "\\)";
  }

  // Nicht jeder Weg fuehrt ueber prepareMarkdown: Share- und Topic-Seiten
  // liefern fertiges HTML vom Server, und ohne marked/DOMPurify zeigt die App
  // den Rohtext. Damit "$...$" und blanke "^{...}" auch dort eine Formel
  // werden, laeuft dieselbe konservative Erkennung noch einmal ueber die
  // fertigen Textknoten. Eine Fehlermarke von KaTeX traegt den Quelltext und
  // wuerde sonst bei jedem Durchgang erneut eingewickelt.
  const MATH_SKIP_SELECTOR = "script, style, code, pre, textarea, .katex, .katex-error";

  function normalizeDollarMath(root) {
    const doc = root.ownerDocument || document;
    const walker = doc.createTreeWalker(root, 4 /* SHOW_TEXT */);
    const pending = [];
    let node;
    while ((node = walker.nextNode())) {
      const value = node.nodeValue;
      if (!value || (value.indexOf("$") === -1 && !/[\^_]\{/.test(value))) continue;
      if (node.parentElement && node.parentElement.closest(MATH_SKIP_SELECTOR)) continue;
      const converted = withMathSegments(dollarInlineToParens(value), keepMath, bareScriptsToInline);
      if (converted !== value) pending.push([node, converted]);
    }
    pending.forEach(function (entry) { entry[0].nodeValue = entry[1]; });
  }

  function typeset(root) {
    window.renderMathInElement(root, {
      delimiters: delimiters,
      throwOnError: false,
      trust: false
    });
  }

  // Oeffentliche Seiten binden KaTeX nur ein, wenn der Server eine Formel
  // gefunden hat (partials/katex.html). Hat er eine uebersehen, nennt das
  // Meta-Tag die Dateien, und KaTeX wird hier einmal nachgeladen. Ohne
  // Meta-Tag (z. B. /app, wo KaTeX immer geladen wird) bleibt alles wie zuvor.
  const MATH_TEXT_RE = /\$\$|\\\(|\\\[|\\begin\{/;
  let katexLoad = null;
  const waitingRoots = new Set();

  function loadKatex() {
    if (katexLoad) return katexLoad;
    const meta = document.querySelector('meta[name="katex-assets"]');
    if (!meta) return null;
    function add(tag, attrs) {
      return new Promise(function (resolve, reject) {
        const el = document.createElement(tag);
        Object.keys(attrs).forEach(function (key) { el[key] = attrs[key]; });
        el.onload = resolve;
        el.onerror = reject;
        document.head.appendChild(el);
      });
    }
    add("link", { rel: "stylesheet", href: meta.dataset.css }).catch(function () {});
    // async=false: dynamisch eingefuegte Skripte laufen sonst in
    // Ankunftsreihenfolge, auto-render braucht aber katex vorher.
    katexLoad = Promise.all([
      add("script", { src: meta.dataset.js, async: false }),
      add("script", { src: meta.dataset.autoRender, async: false })
    ]).then(function () {
      waitingRoots.forEach(function (root) {
        if (root.isConnected) typeset(root);
      });
      waitingRoots.clear();
    }, function () { waitingRoots.clear(); });
    return katexLoad;
  }

  function render(root) {
    if (!root) return;
    normalizeDollarMath(root);
    if (typeof window.renderMathInElement === "function") {
      typeset(root);
      return;
    }
    if (!MATH_TEXT_RE.test(root.textContent || "")) return;
    if (loadKatex()) waitingRoots.add(root);
  }

  window.ConsensusMath = {
    prepareMarkdown: prepareMarkdown,
    stripMath: stripMath,
    wrapBareLatex: wrapBareLatex,
    render: render
  };

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-math-render]").forEach(render);
  });
})();
