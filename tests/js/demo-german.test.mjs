// static/demo.js on a German page: the scenario's text arrives in German
// (demoInPageLanguage), the values the app reads stay as they are, and every
// anchor and contested word still finds its place in the German answer.
import { readdirSync, readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import { loadScripts, ROOT } from "./helpers/appWindow.mjs";

// The fields a reader reads as words. Everything else in differencesData is
// a value: a type, a severity, a coverage, a model name, a count.
const TEXT_FIELDS = new Set(["anchor", "quote", "target", "claim", "consensus_anchor", "stance", "verify"]);

// What the browser gets (app/core/i18n.py, client_bundle): every file but the
// server-only ones, keys with collapsed whitespace.
function browserDictionary() {
  const folder = `${ROOT}/app/i18n/de`;
  const entries = {};
  for (const name of readdirSync(folder)) {
    if (!name.endsWith(".json") || name.startsWith("page-") || name === "mail.json") continue;
    for (const [key, value] of Object.entries(JSON.parse(readFileSync(`${folder}/${name}`, "utf8")))) {
      if (!key.startsWith("_")) entries[key.replace(/\s+/g, " ").trim()] = value;
    }
  }
  return entries;
}

const DEMO_SOURCE = readFileSync(`${ROOT}/static/demo.js`, "utf8")
  .split("/* === DEMO: Timing & Typing Configuration", 1)[0];

// The demo's data block on a page in `lang`, behind i18n.js as on /app.
function demoOnPage(lang, entries, { scripts = [], body = "", after } = {}) {
  const page = loadScripts(["static/js/i18n.js", "static/js/app-text.js", ...scripts], {
    body,
    base: false,
    before(window) {
      window.__consensI18n = { lang, entries };
      window.App = { state: { set() {} } };
      window.matchMedia = query => ({
        matches: false, media: query, addEventListener() {}, removeEventListener() {}
      });
    },
  });
  after?.(page.window);
  const script = page.document.createElement("script");
  script.textContent = `${DEMO_SOURCE}\nwindow.__testDemoData = DEMO_DATA;`;
  page.document.head.appendChild(script);
  return { ...page, data: page.window.__testDemoData };
}

function withoutText(value) {
  if (Array.isArray(value)) return value.map(withoutText);
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.entries(value)
      .filter(([key]) => !TEXT_FIELDS.has(key))
      .map(([key, entry]) => [key, withoutText(entry)]));
  }
  return value;
}

function textFields(value, out = []) {
  if (Array.isArray(value)) value.forEach(entry => textFields(entry, out));
  else if (value && typeof value === "object") {
    for (const [key, entry] of Object.entries(value)) {
      if (TEXT_FIELDS.has(key) && typeof entry === "string") out.push([key, entry]);
      else textFields(entry, out);
    }
  }
  return out;
}

const english = demoOnPage("en", {}).data;

describe("the demo on a German page", () => {
  it("translates the text and never a value the app reads", () => {
    // A dictionary with German for every string: whatever is a value must
    // still arrive as it was ("contradiction" -> "Widerspruch" took the
    // demo's red mark, its "vs" and "Critical").
    const german = demoOnPage("de", { Copy: "Kopieren" }, {
      after(window) { window.App.t = text => `DE ${text}`; },
    }).data;
    expect(withoutText(german.differencesData)).toEqual(withoutText(english.differencesData));
    for (const [key, text] of textFields(german.differencesData)) expect(text, key).toMatch(/^DE /);
  });

  it("keeps every type and severity with the real dictionary", () => {
    const german = demoOnPage("de", browserDictionary()).data;
    expect(withoutText(german.differencesData)).toEqual(withoutText(english.differencesData));
    expect(german.differencesData.differences.map(diff => [diff.type, diff.severity])).toEqual([
      ["contradiction", "major"], ["contradiction", "minor"], ["emphasis", "minor"],
    ]);
  });

  it("has German for every anchor, quote and contested word", () => {
    const german = demoOnPage("de", browserDictionary()).data;
    const before = textFields(english.differencesData);
    const untranslated = textFields(german.differencesData)
      .filter(([, text], index) => text === before[index][1])
      .map(([key, text]) => `${key}: ${text}`);
    expect(untranslated).toEqual([]);
  });

  it("marks the critical contradiction and every contested word in the German answer", () => {
    const { window, document, data } = demoOnPage("de", browserDictionary(), {
      scripts: ["static/js/user-settings.js", "static/js/consensus-anchor.js", "static/js/consensus-insights.js"],
      body: `
        <article class="thread-history-turn">
          <div class="consensus-answer-body"></div>
          <div class="consensus-claims-fallback" hidden></div>
        </article>
        <div id="differencesCards"></div>
        <div id="claimPopover" hidden></div>
        <div id="claimSheetBackdrop" hidden></div>
      `,
    });
    window.Element.prototype.scrollIntoView = function () {};
    const body = document.querySelector(".consensus-answer-body");
    body.innerHTML = data.consensus;
    window.renderStoredConsensusClaims(body, data.differencesData,
      document.querySelector(".consensus-claims-fallback"), []);

    const critical = data.differencesData.differences[0];
    expect([...body.querySelectorAll(".cx-claim.is-major")].map(mark => mark.textContent).join(""))
      .toContain(critical.consensus_anchor);
    const spots = [...body.querySelectorAll(".cx-spot")].map(spot => spot.textContent);
    const targets = [...new Set(data.differencesData.claims.flatMap(claim => claim.dissent.map(item => item.target)))];
    expect(targets.filter(target => !spots.some(spot => spot.includes(target)))).toEqual([]);
  });
});
