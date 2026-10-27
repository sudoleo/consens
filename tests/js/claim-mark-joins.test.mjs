/**
 * Ein Satz mit Fett-/Kursivteilen wird in mehrere Spans zerlegt. Nur die
 * aeusseren Enden duerfen Innenabstand tragen; sonst stand an jeder
 * Elementgrenze ein sichtbarer Zusatzabstand ("( Årsrapport )").
 */
import { expect, it } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

const SENTENCE = "Hoch: Jahresabschluss (Årsrapport) nach dem Gesetz, das gilt.";

it("keeps inner joins of a split sentence flush and pads only its outer ends", () => {
  const { window, document } = loadScripts(["static/js/user-settings.js", "static/js/consensus-anchor.js", "static/js/consensus-insights.js"], {
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

function markClaims(html, claims) {
  const { window, document } = loadScripts(["static/js/user-settings.js", "static/js/consensus-anchor.js", "static/js/consensus-insights.js"], {
    body: `<article class="thread-history-turn"><div class="consensus-answer-body thread-history-answer-body">${html}</div>
      <div class="consensus-claims-fallback" hidden></div></article>`
  });
  window.Element.prototype.scrollIntoView = function () {};
  const body = document.querySelector(".thread-history-answer-body");
  const fallback = document.querySelector(".consensus-claims-fallback");
  window.renderStoredConsensusClaims(body, {
    models_compared: ["OpenAI", "Gemini"], differences: [],
    claims: claims.map((anchor, index) => ({ anchor, sentence_id: index + 1, anchor_occurrence: 0,
      agree: ["OpenAI"], dissent: [{ model: "Gemini", quote: "no" }], coverage: "split" }))
  }, fallback, []);
  const groups = [...new Set([...body.querySelectorAll(".cx-claim")].map(span => span.cxGroup))];
  return { body, fallback, sentences: groups.map(group => group.spans.map(span => span.textContent).join("|")) };
}

it("marks a sentence that starts with inline code on its own, from its first word", () => {
  const { body, sentences } = markClaims(
    "<p>The CLI is fast. <code>npm</code> installs packages quickly.</p>",
    ["The CLI is fast.", "`npm` installs packages quickly."]
  );
  // Before, the second sentence was never found and the first one's mark ran
  // on over it: two claims, one mark.
  expect(sentences).toEqual(["The CLI is fast.", "installs packages quickly."]);
  expect(body.querySelector("code .cx-claim, .cx-claim code")).toBeNull();
  expect(body.querySelector("code").outerHTML).toBe("<code>npm</code>");
});

it("leaves a sentence of nothing but code to the list instead of marking its full stop", () => {
  const { body, fallback, sentences } = markClaims(
    "<p>Install it first. <code>npm ci</code>.</p>",
    ["Install it first.", "`npm ci`."]
  );
  expect(sentences).toEqual(["Install it first."]);
  expect(body.querySelector("code").outerHTML).toBe("<code>npm ci</code>");
  expect(fallback.textContent).toContain("npm ci");
});
