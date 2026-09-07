import { describe, expect, it } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

function render(agreement) {
  const app = loadScripts(["static/js/consensus-anchor.js", "static/js/consensus-insights.js"], {
    body: '<div id="consensusAnswerBody"><p>A concrete statement with evidence.</p></div><div id="consensusVerdict"></div><div id="differencesCards"></div>',
    before(window) {
      window.App = { consensusBodyEl: () => window.document.getElementById("consensusAnswerBody") };
      window.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} });
    }
  });
  app.window.renderConsensusInsights({ models_compared: ["OpenAI", "Gemini"], claims: [], differences: [], agreement }, 2);
  return app.document.getElementById("consensusVerdict");
}

describe("agreement coverage", () => {
  it("shows an explicit unavailable verdict instead of a reassuring score", () => {
    const verdict = render({ score: null, coverage_status: "insufficient", coverage_percent: 5, scored_claims: 1, total_claims: 20 });
    expect(verdict.textContent).toContain("Insufficient evidence to assess agreement");
    expect(verdict.textContent).toContain("Coverage: 1/20 claims (5%)");
    expect(verdict.querySelector(".verdict-gauge")).toBeNull();
    expect(verdict.classList.contains("is-calm")).toBe(false);
  });
  it("keeps measured agreement and coverage separate", () => {
    const verdict = render({ score: 64, coverage_status: "limited", coverage_percent: 50, scored_claims: 2, total_claims: 4, evidence_incomplete: true });
    expect(verdict.querySelector(".verdict-score-num").textContent).toContain("64");
    expect(verdict.textContent).toContain("Coverage: 2/4 claims (50%)");
    expect(verdict.textContent).toContain("evidence incomplete");
  });
  it("retains the legacy verdict for snapshots without coverage metadata", () => {
    expect(render({ score: 90 }).textContent).toContain("High agreement");
  });
});
