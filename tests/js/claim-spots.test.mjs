/**
 * Only the point of dispute carries the colour (2026-10-19): in a disputed
 * sentence the words a model contradicts (claims[].dissent[].target, named by
 * the Coverage judge and checked by the server) are wrapped in .cx-spot; the
 * sentence span stays the control and loses its own surface (.has-spot).
 */
import { afterEach, expect, it } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

let opened = [];
afterEach(() => {
  opened.forEach(dom => dom.window.close());
  opened = [];
});

// `markdown` loads the vendored Markdown library as the app does: with it,
// stripMarkdown keeps an unpaired "**" (the bundle-free fallback drops it).
const MARKDOWN = ["static/vendor/marked/12.0.2/marked.min.js", "static/vendor/dompurify/3.4.17/dist/purify.min.js"];

function boot(html, mode = null, { markdown = false } = {}) {
  const env = loadScripts([...(markdown ? MARKDOWN : []),
    "static/js/user-settings.js", "static/js/consensus-anchor.js", "static/js/consensus-insights.js"], {
    body: `<select id="consensusHighlightsSelect">
        <option value="all">All checks</option><option value="contradictions">Contradictions only</option>
        <option value="concerns">Disagreements</option><option value="critical">Critical</option><option value="none">None</option>
      </select>
      <div id="consensusAnswerBody" class="consensus-answer-body">${html}</div>
      <div id="consensusClaimsFallback" class="consensus-claims-fallback" hidden></div>
      <div id="differencesCards"></div><div id="claimPopover" hidden></div><div id="claimSheetBackdrop" hidden></div>`,
    before(window) {
      if (mode) window.localStorage.setItem("consensio.consensusHighlightMode.v1", mode);
      window.App = window.App || {};
      window.App.consensusBodyEl = () => window.document.getElementById("consensusAnswerBody");
      window.matchMedia = query => ({ matches: false, media: query, addEventListener() {}, removeEventListener() {} });
    }
  });
  opened.push(env.dom);
  env.window.Element.prototype.scrollIntoView = function () {};
  return env;
}

const split = (anchor, dissent) => ({ anchor, agree: ["OpenAI", "Gemini"], dissent, coverage: "split" });
const spots = document => [...document.querySelectorAll(".cx-spot")].map(spot => spot.textContent);
// The answer's own text, without the support counts placed after a sentence.
function text(element) {
  const copy = element.cloneNode(true);
  copy.querySelectorAll(".claim-badge").forEach(badge => badge.remove());
  return copy.textContent;
}

it("colours only the disputed words and keeps the sentence as the control", () => {
  const sentence = "Rooms that stay warm keep their radiators; the rest need larger ones.";
  const { window, document } = boot(`<p>${sentence}</p>`);
  window.renderConsensusInsights({ models_compared: ["OpenAI", "Gemini", "Mistral"], differences: [],
    claims: [split(sentence, [{ model: "Mistral", quote: "Replace them all", target: "keep their radiators" }])] }, 3);
  expect(spots(document)).toEqual(["keep their radiators"]);
  const mark = document.querySelector(".cx-claim");
  expect(mark.classList.contains("has-spot")).toBe(true);
  expect(mark.classList.contains("is-split")).toBe(true);
  expect(mark.getAttribute("role")).toBe("button");
  expect(text(document.querySelector("p"))).toBe(sentence);
});

it("finds words across bold text and keeps the visible text unchanged", () => {
  const sentence = "In Kona Vincent Luis won the men's race.";
  const { window, document } = boot("<p>In Kona <strong>Vincent Luis</strong> won the men's race.</p>");
  window.renderConsensusInsights({ models_compared: ["OpenAI", "Gemini", "GLM"], differences: [],
    claims: [split("In Kona **Vincent Luis** won the men's race.",
      [{ model: "GLM", quote: "not in Kona", target: "Vincent Luis** won" }])] }, 3);
  expect(spots(document).join("")).toBe("Vincent Luis won");
  const parts = [...document.querySelectorAll(".cx-spot")];
  expect(parts.length).toBe(2);
  expect(parts[0].classList.contains("cx-join-end")).toBe(true);
  expect(parts[1].classList.contains("cx-join-start")).toBe(true);
  expect(text(document.querySelector("p"))).toBe(sentence);
});

it("marks the whole sentence when no named words are found", () => {
  const sentence = "Its current thresholds are 25,000 and 100,000 euros.";
  const { window, document } = boot(`<p>${sentence}</p>`);
  window.renderConsensusInsights({ models_compared: ["OpenAI", "Gemini", "Grok"], differences: [],
    claims: [split(sentence, [{ model: "Grok", quote: "22,000 and 50,000", target: "German VAT may be due" }]),
    ] }, 3);
  expect(spots(document)).toEqual([]);
  expect(document.querySelector(".cx-claim").classList.contains("has-spot")).toBe(false);
});

it("joins overlapping words and keeps separate spots apart", () => {
  const sentence = "Prices start at 300 dollars and euro prices are missing.";
  const { window, document } = boot(`<p>${sentence}</p>`);
  window.renderConsensusInsights({ models_compared: ["OpenAI", "Gemini", "Grok", "GLM"], differences: [],
    claims: [split(sentence, [
      { model: "Grok", quote: "about 250", target: "300 dollars" },
      { model: "GLM", quote: "150 euros", target: "euro prices are missing" },
      { model: "Gemini", quote: "around 250 dollars", target: "at 300" },
    ])] }, 4);
  expect(spots(document)).toEqual(["at 300 dollars", "euro prices are missing"]);
});

it("puts the words of a contradiction's sentence in its red mark", () => {
  const sentence = "The models split on the target flow temperature: 55 or 45 degrees.";
  const { window, document } = boot(`<p>${sentence}</p>`);
  window.renderConsensusInsights({ models_compared: ["OpenAI", "Gemini", "Claude"],
    claims: [split(sentence, [{ model: "Claude", quote: "45 degrees", target: "target flow temperature" }])],
    differences: [{ claim: "Flow temperature", consensus_anchor: sentence, type: "contradiction", severity: "major",
      positions: [{ models: ["OpenAI"], stance: "55", quote: "55" }, { models: ["Claude"], stance: "45", quote: "45" }] }] }, 3);
  const mark = document.querySelector(".cx-claim");
  expect(mark.classList.contains("is-major")).toBe(true);
  expect(mark.classList.contains("has-spot")).toBe(true);
  expect(spots(document)).toEqual(["target flow temperature"]);
});

it("follows the highlight filter and leaves nothing behind on reset", () => {
  const sentence = "Test it this winter: turn the boiler down for a week.";
  const { window, document } = boot(`<p>${sentence}</p>`, "critical");
  window.renderConsensusInsights({ models_compared: ["OpenAI", "Gemini", "DeepSeek"], differences: [],
    claims: [split(sentence, [{ model: "DeepSeek", quote: "Do not rely on it", target: "Test it this winter" }])] }, 3);
  // "Critical contradictions" hides amber: the spot stays inside a filtered sentence.
  expect(document.querySelector(".cx-claim").classList.contains("is-marker-filtered")).toBe(true);
  expect(spots(document)).toEqual(["Test it this winter"]);
  window.resetConsensusInsights();
  expect(document.querySelector(".cx-spot, .cx-claim")).toBe(null);
  expect(document.querySelector("p").textContent).toBe(sentence);
  expect(document.querySelector("p").childNodes.length).toBe(1);
});

it.each([
  // The server returns the span of the Markdown source: it may start or end
  // inside emphasis, or carry a source tag the page shows as a chip.
  ["<p>In Kona <strong>Vincent Luis</strong> won the men's race.</p>", "In Kona **Vincent Luis** won the men's race.",
    "Vincent Luis** won", "Vincent Luis won"],
  ["<p>In Kona <strong>Vincent Luis</strong> won the men's race.</p>", "In Kona **Vincent Luis** won the men's race.",
    "In Kona **Vincent", "In Kona Vincent"],
  ['<p>It is 330 m tall.<a class="src-ref" href="https://example.org">example.org</a> Later.</p>', "It is 330 m tall.[S1]",
    "330 m tall.[S1]", "330 m tall."],
  ['<p>See <a href="https://x.y">the guide</a> for details.</p>', "See [the guide](https://x.y) for details.",
    "[the guide](https://x.y)", "the guide"],
])("finds the visible words of a Markdown span with the real Markdown library (%#)", (html, anchor, target, visible) => {
  const { window, document } = boot(html, null, { markdown: true });
  expect(typeof window.marked?.parseInline).toBe("function");
  window.renderConsensusInsights({ models_compared: ["OpenAI", "Gemini", "GLM"], differences: [],
    claims: [split(anchor, [{ model: "GLM", quote: "otherwise", target }])] }, 3);
  expect(spots(document).join("")).toBe(visible);
  expect(document.querySelector(".cx-claim").classList.contains("has-spot")).toBe(true);
});
