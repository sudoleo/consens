// static/demo.js on a German page: the scenario's text arrives in German
// (demoInPageLanguage), the values the app reads stay as they are, and every
// reviewer's note still finds its sentence and words in the German answer.
import { readdirSync, readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import { loadScripts, ROOT } from "./helpers/appWindow.mjs";

// The fields of a reviewer's note a reader reads as words. Its kind and its
// reviewer are values.
const TEXT_FIELDS = new Set(["anchor", "target", "note"]);

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

function values(notes) {
  return notes.map(note => Object.fromEntries(Object.entries(note).filter(([key]) => !TEXT_FIELDS.has(key))));
}

function texts(notes) {
  return notes.flatMap(note => [...TEXT_FIELDS].map(key => [key, note[key]]));
}

const english = demoOnPage("en", {}).data;

describe("the demo on a German page", () => {
  it("translates the notes and never a value the app reads", () => {
    // A dictionary with German for every string: whatever is a value must
    // still arrive as it was (a note of kind "falsch" has no colour).
    const german = demoOnPage("de", { Copy: "Kopieren" }, {
      after(window) { window.App.t = text => `DE ${text}`; },
    }).data;
    expect(values(german.notes)).toEqual(values(english.notes));
    for (const [key, text] of texts(german.notes)) expect(text, key).toMatch(/^DE /);
  });

  it("has German for every sentence, quoted word and note of the reviewers", () => {
    const german = demoOnPage("de", browserDictionary()).data;
    expect(values(german.notes)).toEqual(values(english.notes));
    const before = texts(english.notes);
    const untranslated = texts(german.notes)
      .filter(([, text], index) => text === before[index][1])
      .map(([key, text]) => `${key}: ${text}`);
    expect(untranslated).toEqual([]);
  });

  it("marks every note's sentence and words in the German answer", () => {
    const { window, document, data } = demoOnPage("de", browserDictionary(), {
      scripts: ["static/js/user-settings.js", "static/js/consensus-anchor.js", "static/js/consensus-insights.js"],
      body: `
        <article class="thread-history-turn">
          <div class="consensus-answer-body"></div>
          <div class="consensus-claims-fallback" hidden></div>
        </article>
        <div id="claimPopover" hidden></div>
        <div id="claimSheetBackdrop" hidden></div>
      `,
    });
    window.Element.prototype.scrollIntoView = function () {};
    const body = document.querySelector(".consensus-answer-body");
    const fallback = document.querySelector(".consensus-claims-fallback");
    body.innerHTML = data.answer;
    // The answer itself arrived in German.
    expect(body.textContent).toContain("Als Erstes");
    const audit = { claims: data.notes.map(note => ({ anchor: note.anchor, audit: true, kind: note.kind, agree: [],
      dissent: [{ model: note.model, kind: note.kind, note: note.note, target: note.target }] })), unplaced: [], process: [] };
    expect(window.renderStoredAuditMarks(body, audit, fallback, [])).toBe(true);
    expect(fallback.hidden).toBe(true);
    expect([...body.querySelectorAll(".cx-claim.is-audit")].map(mark => mark.textContent.trim()))
      .toEqual(data.notes.map(note => note.anchor));
    const spots = [...body.querySelectorAll(".cx-spot")].map(spot => spot.textContent);
    expect(data.notes.map(note => note.target).filter(target => !spots.some(spot => spot.includes(target)))).toEqual([]);
  });

  it("has German for the agent's notes while it works", () => {
    const source = readFileSync(`${ROOT}/static/demo.js`, "utf8");
    const block = source.split("const DEMO_AGENT_NOTES = demoInPageLanguage({", 2)[1].split("});", 1)[0];
    const notes = [...block.matchAll(/^\s+\w+: "(.+)",?$/gm)].map(match => match[1]);
    expect(notes).toHaveLength(2);
    const dictionary = browserDictionary();
    expect(notes.filter(note => !dictionary[note])).toEqual([]);
  });
});
