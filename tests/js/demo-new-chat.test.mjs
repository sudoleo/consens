// New chat ends the demo whichever one plays, also while it still types
// the question (static/demo.js): the field and the answer boxes are the
// reader's again, and a Compare run started next is not written over.
import { describe, expect, it } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

const BODY = `
  <textarea id="questionInput"></textarea>
  <button id="sendButton"></button>
  <button id="newRunButton"></button>
  <div class="response-box" id="openaiResponse"><div class="collapsible-content"></div></div>
  <div class="response-box" id="geminiResponse"><div class="collapsible-content"></div></div>`;

function page(mode) {
  const ctx = loadScripts(["static/demo.js"], {
    body: BODY,
    before(window) {
      // Every pause of the demo passes at once: what matters is the order.
      const later = window.setTimeout.bind(window);
      window.setTimeout = (callback, _ms, ...args) => later(callback, 0, ...args);
      window.App = {
        state: { set() {} },
        modelPrefs: [{ key: "OpenAI", provider: "openai", responseId: "openaiResponse" },
          { key: "Gemini", provider: "gemini", responseId: "geminiResponse" }],
        runMode: { preference: () => mode },
        agentChat: { demoView: () => null },
      };
      window.CONSENSUS_PRESETS = [{ id: "fast", models: { openai: true, gemini: true } }];
      window.matchMedia = query => ({ matches: false, media: query, addEventListener() {}, removeEventListener() {} });
    },
  });
  return ctx;
}

const turn = window => new Promise(resolve => window.setTimeout(resolve, 0));

async function until(window, condition) {
  for (let step = 0; step < 2000 && !condition(); step += 1) await turn(window);
  expect(condition()).toBe(true);
}

describe("New chat during the Compare demo", () => {
  it("stops its typing and leaves the field and the answer boxes alone", async () => {
    const { window, document } = page("compare");
    const field = document.getElementById("questionInput");
    const send = document.getElementById("sendButton");
    const played = window.runDemoFlow();
    await until(window, () => field.value.length >= 3);
    expect(send.disabled).toBe(true);

    document.getElementById("newRunButton").click();
    // What the app's own New chat does to the field (app-init.js), then
    // the reader types and a real run's answer arrives.
    field.value = "My own question";
    const box = document.querySelector("#openaiResponse .collapsible-content");
    box.textContent = "A real answer";
    await played;
    for (let step = 0; step < 50; step += 1) await turn(window);

    expect(field.value).toBe("My own question");
    expect(box.textContent).toBe("A real answer");
    expect(document.querySelector("#geminiResponse .collapsible-content").textContent).toBe("");
    expect(send.disabled).toBe(false);
  });
});

describe("New chat while the Agent demo types its question", () => {
  it("leaves the field to the reader", async () => {
    const { window, document } = page("agent");
    const field = document.getElementById("questionInput");
    const played = window.runDemoFlow();
    await until(window, () => field.value.length >= 3);
    document.getElementById("newRunButton").click();
    field.value = "My own question";
    await played;
    for (let step = 0; step < 50; step += 1) await turn(window);
    expect(field.value).toBe("My own question");
    expect(document.getElementById("sendButton").disabled).toBe(false);
  });
});
