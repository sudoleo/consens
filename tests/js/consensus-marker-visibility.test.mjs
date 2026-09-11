import { describe, expect, it } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

const STORAGE_KEY = "consensio.showConsensusMarkers.v1";
const CLAIM = "The launch date is September 3.";

function boot(stored = null, mode = null, denyStorage = false) {
  return loadScripts([
    "static/js/consensus-anchor.js",
    "static/js/consensus-insights.js"
  ], {
    body: `
      <select id="consensusHighlightsSelect">
        <option value="all">All checks</option><option value="contradictions">Contradictions only</option>
        <option value="concerns">Red & amber</option><option value="critical">Red only</option>
        <option value="none">No highlights</option>
      </select>
      <small id="consensusHighlightsHelp"></small>
      <input type="checkbox" id="claimCountsSwitch">
      <div id="consensusAnswerBody" class="consensus-answer-body"><p>${CLAIM}</p></div>
      <div id="consensusClaimsFallback" class="consensus-claims-fallback" hidden></div>
      <div id="differencesCards"></div>
      <div id="claimPopover" hidden></div>
      <div id="claimSheetBackdrop" hidden></div>
    `,
    before(window) {
      if (stored !== null) window.localStorage.setItem(STORAGE_KEY, stored);
      if (mode !== null) window.localStorage.setItem("consensio.consensusHighlightMode.v1", mode);
      if (denyStorage) window.Storage.prototype.setItem = () => { throw new Error("denied"); };
      window.App = window.App || {};
      window.App.consensusBodyEl = () => window.document.getElementById("consensusAnswerBody");
      window.matchMedia = query => ({
        matches: false, media: query, addEventListener() {}, removeEventListener() {}
      });
    }
  });
}

function renderContradiction(window) {
  window.renderConsensusInsights({
    models_compared: ["OpenAI", "Gemini"],
    claims: [],
    differences: [{
      claim: "the launch date",
      consensus_anchor: CLAIM,
      type: "contradiction",
      severity: "major",
      positions: [
        { models: ["OpenAI"], stance: "September 3", quote: "September 3" },
        { models: ["Gemini"], stance: "September 5", quote: "September 5" }
      ]
    }]
  }, 2);
}

describe("consensus sentence-check visibility", () => {
  it("uses the persistent settings selection without removing the analysis", () => {
    const { window, document } = boot();
    renderContradiction(window);

    const ctx = { window, document };
    const mark = document.querySelector("#consensusAnswerBody .cx-claim");
    expect(mark.getAttribute("role")).toBe("button");
    expect(document.body.dataset.consensusHighlightMode).toBe("concerns");

    choose(ctx, document.body.classList.contains("consensus-markers-hidden") ? "concerns" : "none");
    expect(document.body.classList.contains("consensus-markers-hidden")).toBe(true);
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe("false");
    expect(document.getElementById("consensusHighlightsSelect").value).toBe("none");
    expect(mark.hasAttribute("role")).toBe(false);
    expect(document.querySelectorAll("#differencesCards .diff-card").length).toBe(1);

    choose(ctx, document.body.classList.contains("consensus-markers-hidden") ? "concerns" : "none");
    expect(document.body.classList.contains("consensus-markers-hidden")).toBe(false);
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe("true");
    expect(mark.getAttribute("role")).toBe("button");
  });

  it("restores the hidden preference before a new answer is rendered", () => {
    const { window, document } = boot("false");
    expect(document.body.classList.contains("consensus-markers-hidden")).toBe(true);

    renderContradiction(window);
    const mark = document.querySelector("#consensusAnswerBody .cx-claim");
    expect(mark).not.toBe(null);
    expect(mark.hasAttribute("role")).toBe(false);
    expect(document.getElementById("consensusHighlightsSelect").value).toBe("none");
  });
});

const SENTENCES = ["The tower is tall.", "Tickets cost twenty euros.", "The queue is short.", "Launch is on Monday.", "Doors open at eight.", "The view is scenic."];
function renderMixed(ctx, stored = false) {
  const body = ctx.document.getElementById("consensusAnswerBody");
  body.innerHTML = SENTENCES.map(text => `<p>${text}</p>`).join("");
  const payload = {
    models_compared: ["OpenAI", "Gemini", "Anthropic"],
    claims: [
      { anchor: SENTENCES[0], agree: ["OpenAI", "Gemini"], dissent: [], coverage: "supported" },
      { anchor: SENTENCES[1], agree: ["OpenAI"], dissent: [{model:"Gemini",quote:"Thirty euros"}], coverage: "split" },
      { anchor: SENTENCES[2], agree: ["OpenAI"], dissent: [], coverage: "thin" },
      { anchor: "An unmatched supported claim.", agree: ["OpenAI", "Gemini"], dissent: [], coverage: "supported" },
      { anchor: "An unmatched split claim.", agree: ["OpenAI"], dissent: [{model:"Gemini",quote:"Another view"}], coverage: "split" },
    ],
    differences: [
      { claim: "Launch day", consensus_anchor: SENTENCES[3], type: "contradiction", severity: "major" },
      { claim: "Opening time", consensus_anchor: SENTENCES[4], type: "contradiction", severity: "minor" },
      { claim: "The view", consensus_anchor: SENTENCES[5], type: "emphasis", severity: "minor" },
    ].map(diff => ({...diff, positions: [
      {models:["OpenAI"],stance:"First view",quote:"First view"},
      {models:["Gemini"],stance:"Second view",quote:"Second view"},
    ]})),
  };
  if (stored) ctx.window.renderStoredConsensusClaims(body, payload, ctx.document.getElementById("consensusClaimsFallback"), []);
  else ctx.window.renderConsensusInsights(payload, 3);
}

function choose(ctx, value) {
  const select = ctx.document.getElementById("consensusHighlightsSelect");
  select.value = value;
  select.dispatchEvent(new ctx.window.Event("change"));
}

describe("sentence highlight filters", () => {
  it("distinguishes minor contradictions from grey emphasis and restores keyboard access", () => {
    const ctx = boot();
    renderMixed(ctx);
    const marks = () => Array.from(ctx.document.querySelectorAll(".cx-claim:not(.is-marker-filtered)"), el => el.textContent);
    choose(ctx, "contradictions");
    expect(marks()).toEqual([SENTENCES[3], SENTENCES[4]]);
    choose(ctx, "concerns");
    expect(marks()).toEqual([SENTENCES[1], SENTENCES[3]]);
    const hidden = ctx.document.querySelector(".cx-claim.is-unanimous");
    expect(hidden.hasAttribute("tabindex")).toBe(false);
    hidden.click();
    expect(ctx.document.getElementById("claimPopover").hidden).toBe(true);
    choose(ctx, "critical");
    expect(marks()).toEqual([SENTENCES[3]]);
    expect(ctx.document.querySelectorAll("#differencesCards .diff-card")).toHaveLength(3);
    choose(ctx, "all");
    expect(marks()).toEqual(SENTENCES);
    expect(hidden.tabIndex).toBe(0);
    hidden.click();
    expect(ctx.document.getElementById("claimPopover").hidden).toBe(false);
  });

  it("keeps filters across settings changes, counts changes and later stored answers", () => {
    const ctx = boot();
    renderMixed(ctx);
    choose(ctx, "concerns");
    choose(ctx, "none");
    expect(ctx.document.body.classList.contains("consensus-markers-hidden")).toBe(true);
    choose(ctx, "concerns");
    expect(ctx.document.getElementById("consensusHighlightsSelect").value).toBe("concerns");
    ctx.document.getElementById("claimCountsSwitch").click();
    renderMixed(ctx, true);
    expect(ctx.document.querySelectorAll(".cx-claim:not(.is-marker-filtered)")).toHaveLength(2);
    expect(ctx.document.querySelectorAll(".claims-fallback-row:not(.is-marker-filtered)")).toHaveLength(1);
    expect(ctx.document.querySelector(".cx-claim.is-unanimous").nextElementSibling.classList.contains("is-marker-filtered")).toBe(true);
    expect(ctx.window.localStorage.getItem("consensio.consensusHighlightMode.v1")).toBe("concerns");
  });

  it("restores saved filters and the existing hidden preference", () => {
    const ctx = boot("false", "critical");
    expect(ctx.document.getElementById("consensusHighlightsSelect").value).toBe("none");
    choose(ctx, "critical");
    renderMixed(ctx, true);
    expect(ctx.document.getElementById("consensusHighlightsSelect").value).toBe("critical");
    expect(ctx.document.querySelectorAll(".cx-claim:not(.is-marker-filtered)")).toHaveLength(1);
    expect(ctx.document.body.dataset.consensusHighlightMode).toBe("critical");
  });

  it("falls back for invalid values and retains the session choice when writes fail", () => {
    const ctx = boot(null, "invalid", true);
    expect(ctx.document.getElementById("consensusHighlightsSelect").value).toBe("concerns");
    choose(ctx, "critical");
    renderMixed(ctx, true);
    expect(ctx.document.querySelectorAll(".cx-claim:not(.is-marker-filtered)")).toHaveLength(1);
    choose(ctx, "none");
    ctx.document.getElementById("claimCountsSwitch").click();
    renderMixed(ctx, true);
    expect(ctx.document.body.classList.contains("consensus-markers-hidden")).toBe(true);
  });
});


describe("highlight defaults", () => {
  it("defaults new browsers to disagreements and concerns while preserving explicit all", () => {
    const fresh=boot(); renderMixed(fresh);
    expect(fresh.document.body.dataset.consensusHighlightMode).toBe("concerns");
    expect(fresh.document.querySelectorAll(".cx-claim:not(.is-marker-filtered)")).toHaveLength(2);
    const explicit=boot("true","all"); renderMixed(explicit);
    expect(explicit.document.querySelectorAll(".cx-claim:not(.is-marker-filtered)")).toHaveLength(6);
    expect(explicit.document.body.dataset.consensusHighlightMode).toBe("all");
  });
});
