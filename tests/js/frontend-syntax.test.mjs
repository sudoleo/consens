/**
 * Syntax, die aeltere Browser nicht parsen koennen, im ausgelieferten Frontend.
 *
 * Regex-Lookbehind ("(?<=" / "(?<!") kennt Safari/iOS erst ab 16.4. Davor ist
 * es ein SyntaxError beim PARSEN - und weil /app seine Klassik-Skripte zu
 * einem Bundle verkettet (static/js/bundles.json), verwarf ein einziges
 * Lookbehind in math-render.js das ganze App-Bundle: die App startete dort
 * gar nicht. Geprueft werden die Quellen unter static/, die Templates (Inline-
 * Skripte) und die aktuell ausgelieferten Bundles laut static/dist/manifest.json.
 * Aeltere Bundles unter previous_assets bleiben aussen vor: sie werden nur fuer
 * schon offene Seiten vorgehalten und altern mit dem naechsten Build heraus.
 */

import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import { ROOT } from "./helpers/appWindow.mjs";

const LOOKBEHIND = /\(\?<[=!]/g;

function walk(relative, extensions, skip = []) {
  const found = [];
  for (const entry of readdirSync(path.join(ROOT, relative), { withFileTypes: true })) {
    const child = `${relative}/${entry.name}`;
    if (skip.includes(child)) continue;
    if (entry.isDirectory()) found.push(...walk(child, extensions, skip));
    else if (extensions.some((extension) => entry.name.endsWith(extension))) found.push(child);
  }
  return found;
}

function lookbehindHits(relative, text = readFileSync(path.join(ROOT, relative), "utf8")) {
  const hits = [];
  text.split("\n").forEach((line, index) => {
    for (const match of line.matchAll(LOOKBEHIND)) {
      hits.push(`${relative}:${index + 1}:${match.index + 1}`);
    }
  });
  return hits;
}

const manifest = JSON.parse(readFileSync(path.join(ROOT, "static/dist/manifest.json"), "utf8"));
const builtScripts = manifest.scripts.map((script) => script.src.replace(/^\//, ""));
const sourceFiles = walk("static", [".js", ".mjs"], ["static/dist"]);
const templateFiles = walk("templates", [".html"]);

describe("frontend syntax for older browsers", () => {
  it("erkennt Lookbehind ueberhaupt", () => {
    expect(lookbehindHits("probe.js", "const a = /(?<![\\s\\\\])\\$/;\nconst b = new RegExp(\"(?<=x)y\");"))
      .toEqual(["probe.js:1:12", "probe.js:2:23"]);
    // Benannte Gruppen kann Safari seit 11.1 - die sind erlaubt.
    expect(lookbehindHits("probe.js", "const c = /(?<year>\\d{4})/;")).toEqual([]);
  });

  it("prueft wirklich die Quellen, die Templates und die ausgelieferten Bundles", () => {
    expect(sourceFiles).toContain("static/js/math-render.js");
    expect(sourceFiles).toContain("static/js/app-init.js");
    expect(templateFiles).toContain("templates/index.html");
    expect(builtScripts.some((file) => /^static\/dist\/app\.[0-9a-f]+\.js$/.test(file))).toBe(true);
  });

  it("enthaelt kein Regex-Lookbehind (Safari/iOS unter 16.4)", () => {
    const hits = [...sourceFiles, ...templateFiles, ...builtScripts].flatMap((file) => lookbehindHits(file));
    expect(hits).toEqual([]);
  });
});
