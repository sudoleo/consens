/**
 * A German page for a test: the dictionary the browser really gets and the
 * scripts that come first on such a page (i18n.js before app-text.js).
 */
import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";

import { ROOT } from "./appWindow.mjs";

// What /i18n/de.<hash>.js carries: every file but page-* and mail.json
// (app/core/i18n.py, server_only).
export function browserDictionary() {
  const folder = path.join(ROOT, "app/i18n/de");
  return Object.assign({}, ...readdirSync(folder)
    .filter(name => name.endsWith(".json") && !name.startsWith("page-") && name !== "mail.json")
    .map(name => JSON.parse(readFileSync(path.join(folder, name), "utf8"))));
}

export const GERMAN_SCRIPTS = ["static/js/i18n.js", "static/js/app-text.js"];

export function useGerman(window) {
  window.__consensI18n = { lang: "de", entries: browserDictionary() };
}

// A question the dictionary's open patterns rewrote: "Remove {name}" made it
// "Entfernen: background noise" (bug hunt 2026-10-23).
export const ENGLISH_QUESTION = "Remove background noise";

export async function settleGerman(window) {
  for (let i = 0; i < 30; i += 1) await Promise.resolve();
  window.App.i18n.flush();
}
