import { readFileSync } from "node:fs";
import vm from "node:vm";

import { describe, expect, it } from "vitest";

import { loadScripts, ROOT } from "./helpers/appWindow.mjs";

function readDemoData() {
  const source = readFileSync(`${ROOT}/static/demo.js`, "utf8");
  const dataOnly = source.split("/* === DEMO: Timing & Typing Configuration", 1)[0];
  const sandbox = {
    window: {
      App: { state: { set() {} } },
      currentEvidenceSources: []
    }
  };
  vm.runInNewContext(`${dataOnly}\nwindow.__testDemoData = DEMO_DATA; window.__testBuildDemo = buildDemoDataForModels;`, sandbox);
  return { ...sandbox.window.__testDemoData, buildForModels: sandbox.window.__testBuildDemo };
}

// The review's audit part as agent_audit.place_marks writes it and demo.js
// (demoAgentReview) builds it: one claim per noted sentence.
function auditOf(notes) {
  return {
    claims: notes.map((note, index) => ({ anchor: note.anchor, audit: true, kind: note.kind, agree: [],
      dissent: [{ model: note.model, kind: note.kind, note: note.note, target: note.target, mark: index + 1 }] })),
    unplaced: [], process: []
  };
}

describe("the demo's one-mode turn (2026-10-31)", () => {
  it("keeps six complete viewpoints and each reviewer's note with its viewpoint for updated preset families", () => {
    const data = readDemoData();
    const models = ['OpenAI', 'Gemini', 'DeepSeek', 'Kimi', 'GLM', 'Meta'];
    const demo = data.buildForModels(models);
    expect(Object.keys(demo.responses).sort()).toEqual([...models].sort());
    expect(Object.values(demo.responses).every(text => text.length > 500)).toBe(true);
    expect(demo.notes.every(note => models.includes(note.model))).toBe(true);
    expect(JSON.stringify(demo)).not.toMatch(/Mistral|Anthropic|Grok/);
    // No score and no judges' differences: the reviewers' notes are the review.
    expect(demo).not.toHaveProperty("differencesData");
    expect(demo).not.toHaveProperty("consensus");
  });

  it("has one note of each kind for the Daily lineup", () => {
    const data = readDemoData();
    const daily = data.buildForModels(["OpenAI", "Anthropic", "DeepSeek"]);
    expect(daily.notes.map(note => [note.model, note.kind])).toEqual([
      ["OpenAI", "wrong"], ["DeepSeek", "doubtful"], ["Anthropic", "incomplete"],
    ]);
  });

  it("marks every reviewer's note on its sentence and its words in the agent's answer", () => {
    const data = readDemoData();
    const { window, document } = loadScripts([
      "static/js/user-settings.js", "static/js/consensus-anchor.js",
      "static/js/consensus-insights.js"
    ], {
      body: `
        <article class="thread-history-turn">
          <div class="consensus-answer-body">${data.answer}</div>
          <div class="consensus-claims-fallback" hidden></div>
        </article>
        <div id="claimPopover" hidden></div>
        <div id="claimSheetBackdrop" hidden></div>
      `,
      before(browserWindow) {
        browserWindow.matchMedia = query => ({
          matches: false, media: query, addEventListener() {}, removeEventListener() {}
        });
      }
    });
    window.Element.prototype.scrollIntoView = function () {};

    const body = document.querySelector(".consensus-answer-body");
    const fallback = document.querySelector(".consensus-claims-fallback");
    expect(window.renderStoredAuditMarks(body, auditOf(data.notes), fallback, [])).toBe(true);
    // Every note found its sentence: none falls back to "Other notes".
    expect(fallback.hidden).toBe(true);
    const marks = [...body.querySelectorAll(".cx-claim.is-audit")];
    expect(marks.map(mark => mark.textContent.trim())).toEqual(data.notes.map(note => note.anchor));
    // Wrong red, doubtful amber, incomplete grey (consensus-insights.js AUDIT_CLASSES).
    expect(marks.map(mark => ["is-major", "is-split", "is-minor"].find(cls => mark.classList.contains(cls))))
      .toEqual(["is-major", "is-split", "is-minor"]);
    const spots = [...body.querySelectorAll(".cx-spot")].map(spot => spot.textContent);
    expect(data.notes.map(note => note.target).filter(target => !spots.some(spot => spot.includes(target)))).toEqual([]);
    // Unmarked text stays plain: no green, no counts.
    expect(body.querySelectorAll(".cx-claim.is-unanimous, .claim-badge")).toHaveLength(0);
  });
});
