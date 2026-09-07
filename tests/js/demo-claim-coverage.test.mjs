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

describe("interactive demo claim coverage", () => {
  it("provides six complete viewpoints and consistent claims for updated Balanced families", () => {
    const data = readDemoData();
    const models = ['OpenAI', 'Gemini', 'DeepSeek', 'Kimi', 'GLM', 'Meta'];
    const demo = data.buildForModels(models);
    expect(Object.keys(demo.responses).sort()).toEqual([...models].sort());
    expect(Object.values(demo.responses).every(text => text.length > 500)).toBe(true);
    expect(demo.differencesData.models_compared.sort()).toEqual([...models].sort());
    expect(JSON.stringify(demo.differencesData)).not.toMatch(/Mistral|Anthropic|Grok/);
    expect(demo.differencesData.differences).toHaveLength(3);
  });

  it("marks every checkable consensus passage with the current coverage contract", () => {
    const data = readDemoData();
    const { window, document } = loadScripts([
      "static/js/consensus-anchor.js",
      "static/js/consensus-insights.js"
    ], {
      body: `
        <article class="thread-history-turn">
          <div class="consensus-answer-body">${data.consensus}</div>
          <div class="consensus-claims-fallback" hidden></div>
        </article>
        <div id="differencesCards"></div>
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
    window.renderStoredConsensusClaims(body, data.differencesData, fallback, []);

    expect(body.querySelectorAll(".cx-claim").length).toBe(19);
    expect(fallback.hidden).toBe(true);

    const passages = body.querySelectorAll(
      ".ai-consensus > p, .ai-consensus > ul > li, .ai-consensus > blockquote"
    );
    passages.forEach(passage => {
      const copy = passage.cloneNode(true);
      copy.querySelectorAll(".claim-badge").forEach(badge => badge.remove());
      copy.querySelectorAll(".cx-claim").forEach(mark => mark.remove());
      const unmarkedWords = copy.textContent.replace(/[^A-Za-z0-9]+/g, "");
      expect(unmarkedWords, passage.textContent).toBe("");
    });
  });
});
