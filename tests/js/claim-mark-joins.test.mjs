/**
 * Ein Satz mit Fett-/Kursivteilen wird in mehrere Spans zerlegt. Nur die
 * aeusseren Enden duerfen Innenabstand tragen; sonst stand an jeder
 * Elementgrenze ein sichtbarer Zusatzabstand ("( Årsrapport )").
 */
import { expect, it } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

const SENTENCE = "Hoch: Jahresabschluss (Årsrapport) nach dem Gesetz, das gilt.";

it("keeps inner joins of a split sentence flush and pads only its outer ends", () => {
  const { window, document } = loadScripts(["static/js/consensus-anchor.js", "static/js/consensus-insights.js"], {
    body: `<article class="thread-history-turn"><div class="consensus-answer-body thread-history-answer-body">
      <p><strong>Hoch:</strong> Jahresabschluss (<em>Årsrapport</em>) nach dem <em>Gesetz</em>, das gilt.</p></div>
      <div class="consensus-claims-fallback" hidden></div></article>`
  });
  window.Element.prototype.scrollIntoView = function () {};
  const body = document.querySelector(".thread-history-answer-body");
  const fallback = document.querySelector(".consensus-claims-fallback");
  window.renderStoredConsensusClaims(body, {
    models_compared: ["OpenAI", "Gemini"],
    claims: [],
    differences: [{ claim: "the report", type: "contradiction", severity: "major", consensus_anchor: SENTENCE,
      positions: [{ models: ["OpenAI"], stance: "a", quote: "a" }, { models: ["Gemini"], stance: "b", quote: "b" }] }]
  }, fallback, []);
  const spans = [...body.querySelectorAll(".cx-claim")];
  expect(spans.length).toBeGreaterThan(2);
  expect(spans.map(s => s.textContent).join("")).toBe(SENTENCE);
  expect(spans[0].classList.contains("cx-join-start")).toBe(false);
  expect(spans[0].classList.contains("cx-join-end")).toBe(true);
  expect(spans.at(-1).classList.contains("cx-join-start")).toBe(true);
  expect(spans.at(-1).classList.contains("cx-join-end")).toBe(false);
  for (const inner of spans.slice(1, -1)) {
    expect(inner.classList.contains("cx-join-start") && inner.classList.contains("cx-join-end")).toBe(true);
  }
  // The visible text is unchanged: no characters were added around the marks.
  expect(body.querySelector("p").textContent).toBe(SENTENCE);
});
