/**
 * math-render.js -- der gemeinsame LaTeX-Pfad von Konsens, Key claims und
 * Share-Seiten.
 *
 * Zwei Dinge stehen hier auf dem Spiel, und beide sind still: Markdown frisst
 * die Escapes INNERHALB einer Formel ("17{,}5\%" -> "17{,}5%", und "%" ist in
 * TeX ein Kommentar, der den Rest der Zeile verschluckt), und dasselbe
 * Dollarzeichen traegt in denselben Antworten Betraege ("6,7 Mrd. $ in Q1").
 * Beides faellt visuell kaum auf und veraendert trotzdem, was dasteht.
 */

import { beforeEach, describe, expect, it } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

function bootRenderPipeline() {
  // Pinned test dependencies mirror the CDN versions in templates/index.html.
  return loadScripts([
    "node_modules/marked/marked.min.js",
    "node_modules/dompurify/dist/purify.min.js",
    "node_modules/katex/dist/katex.min.js",
    "node_modules/katex/dist/contrib/auto-render.min.js",
    "static/js/math-render.js",
    "static/js/markdown-stream.js",
  ], { body: '<div id="answer"></div>' });
}

const screenshotFormulas = [
  String.raw`\[
(y^2+py+q)(y^2-py+r)
=
y^4+(q+r-p^2)y^2+p(r-q)y+qr.
\]`,
  String.raw`\[
v^3-48v+64
=
128\cos(3\theta)+64.
\]`,
  ...["1,2", "3,4"].flatMap((indices, index) => {
    const sign = index ? "+" : "-";
    const radicandSign = index ? "-" : "+";
    return [
      `\\[\nt_{${indices}}\n=\n${sign}\\frac p2 \\pm \\frac{i}{2} \\sqrt{u+12${radicandSign}\\frac{16}{p}}.\n\\]`,
      `\\[\n\\boxed{ x_{${indices}}\n=\n1${sign}\\frac p2 \\pm \\frac{i}{2} \\sqrt{u+12${radicandSign}\\frac{16}{p}} }\n\\]`,
    ];
  }),
];

describe("Markdown and KaTeX integration", () => {
  it.each(screenshotFormulas)("typesets the complete screenshot formula: %s", (formula) => {
    const { window, document } = bootRenderPipeline();
    const answer = document.getElementById("answer");
    window.injectMarkdown(answer, `## Ergebnis\n\n${formula}\n\nWeiter **im Text**.`);
    expect(answer.querySelectorAll("h1, h2")).toHaveLength(1);
    expect(answer.querySelectorAll(".katex-display")).toHaveLength(1);
    expect(answer.querySelector(".katex-error")).toBeNull();
    expect(answer.querySelector("annotation").textContent).toBe(formula.slice(2, -2));
    expect(answer.querySelector("strong").textContent).toBe("im Text");
    window.close();
  });

  it("recovers a formula once its streaming delimiter is complete", async () => {
    const { window, document } = bootRenderPipeline();
    const answer = document.getElementById("answer");
    const stream = window.createStreamRenderer(answer, () => true);
    const formula = screenshotFormulas[0];
    stream.append(formula.slice(0, -2));
    stream.append(formula.slice(-2));
    await new Promise(resolve => window.setTimeout(resolve, 150));
    stream.stop();
    expect(answer.querySelectorAll(".katex-display")).toHaveLength(1);
    expect(answer.querySelector("h1, h2, .katex-error")).toBeNull();
    window.close();
  });

  it.each([
    "$$\nx_1+x_2\n=\ny^2\n$$",
    String.raw`\begin{align}
x_1+x_2
=
y^2
\end{align}`,
    "\\[\nx_1+x_2\n- y\n= 17{,}5\\%\n\\]",
  ])("preserves other display delimiters and formula punctuation: %s", (formula) => {
    const { window, document } = bootRenderPipeline();
    const answer = document.getElementById("answer");
    window.injectMarkdown(answer, formula);
    expect(answer.querySelectorAll(".katex-display")).toHaveLength(1);
    expect(answer.querySelector("h1, h2, li, em, .katex-error")).toBeNull();
    expect(answer.querySelector("annotation").textContent).toContain("=");
    window.close();
  });

  it("keeps code literal and renders ordinary Markdown and currency as before", () => {
    const { window, document } = bootRenderPipeline();
    const answer = document.getElementById("answer");
    const formula = screenshotFormulas[0];
    window.injectMarkdown(answer, `Titel\n=====\n\n\`\\(x_1\\)\`\n\n\`\`\`tex\n${formula}\n\`\`\`\n\n**Preis:** $100 auf $80.`);
    expect(answer.querySelectorAll(".katex")).toHaveLength(0);
    expect(answer.querySelector("h1").textContent).toBe("Titel");
    expect(answer.querySelector("pre code").textContent.trim()).toBe(formula);
    expect(answer.textContent).toContain("Preis: $100 auf $80.");
    window.close();
  });
});

// Das macht marked mit dem vorbereiteten Text: ein Backslash vor einem
// ASCII-Satzzeichen ist ein Escape und verschwindet (CommonMark).
const MARKDOWN_ESCAPE_RE = /\\([!-/:-@[-`{-~])/g;
const throughMarkdown = (value) => value.replace(MARKDOWN_ESCAPE_RE, "$1");

function boot() {
  const { window, document } = loadScripts(["static/js/math-render.js"]);
  return { window, document, math: window.ConsensusMath };
}

describe("ConsensusMath.prepareMarkdown", () => {
  let math;
  beforeEach(() => {
    math = boot().math;
  });

  it("laesst die Escapes einer Formel den Markdown-Pass ueberleben", () => {
    const source = String.raw`Also \(6{,}7 / 5{,}7 - 1 \approx 17{,}5\%\).`;
    expect(throughMarkdown(math.prepareMarkdown(source))).toBe(source);
  });

  it("macht aus $...$ die von KaTeX erkannte Form", () => {
    const source = String.raw`Also $6{,}7 / 5{,}7 - 1 \approx 17{,}5\%$.`;
    expect(throughMarkdown(math.prepareMarkdown(source))).toBe(
      String.raw`Also \(6{,}7 / 5{,}7 - 1 \approx 17{,}5\%\).`
    );
  });

  it("laesst Betraege in Ruhe, auch wenn zwei davon nebeneinander stehen", () => {
    const source = "Anthropic erzielte 5,7 Mrd. $ in Q1 gegenueber 6,7 Mrd. $ in Q2.";
    expect(math.prepareMarkdown(source)).toBe(source);
  });

  it("haelt einen Preisvergleich fuer Text, keine Formel", () => {
    const source = "Der Preis fiel von $100 auf $80.";
    expect(math.prepareMarkdown(source)).toBe(source);
  });

  it("schuetzt Indizes vor der Kursivschrift", () => {
    const source = String.raw`Es gilt $x_1 + x_2 = y^2$.`;
    // Vor dem Markdown-Pass sind die Unterstriche escapt, danach stehen sie
    // wieder als Notation da - kursiv wird nichts.
    expect(math.prepareMarkdown(source)).toContain("x\\_1");
    expect(throughMarkdown(math.prepareMarkdown(source))).toBe(
      String.raw`Es gilt \(x_1 + x_2 = y^2\).`
    );
  });

  it("fasst Code nicht an", () => {
    const source = "Nutze `const cost = $total * 2` im Skript.";
    expect(math.prepareMarkdown(source)).toBe(source);
  });

  it("laesst $$-Bloecke unveraendert durch", () => {
    const source = "$$\\frac{a}{b}$$";
    expect(throughMarkdown(math.prepareMarkdown(source))).toBe(source);
  });

  it("behaelt ein einzelnes \\( ausserhalb einer Formel sichtbar", () => {
    expect(throughMarkdown(math.prepareMarkdown(String.raw`Rest \( ohne Ende`))).toBe(
      String.raw`Rest \( ohne Ende`
    );
  });
});

describe("ConsensusMath.stripMath", () => {
  let math;
  beforeEach(() => {
    math = boot().math;
  });

  it("liefert den Satz ohne Formel - so, wie ihn das DOM zeigt", () => {
    expect(
      math.stripMath(String.raw`Der Zuwachs betraegt \(17{,}5\%\) gegenueber Q1.`)
    ).toBe("Der Zuwachs betraegt   gegenueber Q1.");
  });

  it("erkennt auch die Dollar-Schreibweise", () => {
    expect(math.stripMath(String.raw`Der Zuwachs betraegt $17{,}5\%$.`)).toBe(
      "Der Zuwachs betraegt  ."
    );
  });

  it("meldet mit \"\", dass gar keine Formel drin war", () => {
    expect(math.stripMath("6,7 Mrd. $ in Q1 gegenueber 6,7 Mrd. $ in Q2.")).toBe("");
  });
});

describe("ConsensusMath.wrapBareLatex", () => {
  let math;
  beforeEach(() => {
    math = boot().math;
  });

  it("erkennt den Anker einer abgesetzten Formel aus einem alten Lauf", () => {
    expect(math.wrapBareLatex(String.raw`6{,}7 / 5{,}7 - 1 \approx 17{,}5\%`)).toBe(
      String.raw`\(6{,}7 / 5{,}7 - 1 \approx 17{,}5\%\)`
    );
  });

  it("laesst jeden Anker mit gewoehnlichem Text in Ruhe", () => {
    const claims = [
      "$ ARR = annualisiertes aktuelles Umsatztempo im spaeteren Zeitraum",
      "Die haeufig genannten mehr als 40 Mrd.",
      "Der Zuwachs betraegt 17,5 % gegenueber Q1.",
      String.raw`Also \(17{,}5\%\) mehr.`,
      "2026-08-20"
    ];
    claims.forEach((claim) => expect(math.wrapBareLatex(claim)).toBe(""));
  });
});

describe("ConsensusMath.render", () => {
  it("uebergibt auch $...$ als echten KaTeX-Ausdruck", () => {
    const { window, document, math } = boot();
    const seen = [];
    window.renderMathInElement = (root) => seen.push(root.textContent);
    const box = document.createElement("div");
    box.textContent = String.raw`Also $6{,}7 / 5{,}7 - 1 \approx 17{,}5\%$.`;
    document.body.appendChild(box);

    math.render(box);

    expect(seen).toEqual([
      String.raw`Also \(6{,}7 / 5{,}7 - 1 \approx 17{,}5\%\).`
    ]);
  });

  it("fasst Betraege im fertigen DOM nicht an", () => {
    const { window, document, math } = boot();
    window.renderMathInElement = () => {};
    const box = document.createElement("div");
    const text = "6,7 Mrd. $ in Q1 gegenueber 6,7 Mrd. $ in Q2.";
    box.textContent = text;
    document.body.appendChild(box);

    math.render(box);

    expect(box.textContent).toBe(text);
  });
});
