/**
 * Boot the real /app classic scripts (groups head + app from bundles.json,
 * in their load order) against markup cut from templates/index.html.
 *
 * Tests that exercise a whole flow (a dialog, the sidebar search, a timer
 * in app-init.js) need the real script order and the real markup, not one
 * module and a mock of the rest. The template is Jinja; the cut-out parts
 * only carry `{% if %}` guards and `{{ value }}` output, which are dropped.
 */

import { readFileSync } from "node:fs";
import path from "node:path";

import { loadScripts, ROOT } from "./appWindow.mjs";

const bundles = JSON.parse(readFileSync(path.join(ROOT, "static/js/bundles.json"), "utf8"));

export const APP_SCRIPTS = bundles.groups
  .filter((group) => group.kind === "classic" && ["head", "app"].includes(group.name))
  .flatMap((group) => group.files.map((entry) => (typeof entry === "string" ? entry : entry.file)));

// Normalized: a Windows checkout has CRLF, the markers below use LF.
const TEMPLATE = readFileSync(path.join(ROOT, "templates/index.html"), "utf8").replace(/\r\n/g, "\n");

function stripJinja(markup) {
  return markup
    .replace(/\{#[\s\S]*?#\}/g, "")
    .replace(/\{%[\s\S]*?%\}/g, "")
    .replace(/\{\{[\s\S]*?\}\}/g, "");
}

/** The element whose opening tag contains `marker`, through `endMarker`. */
export function templateSlice(marker, endMarker) {
  const start = TEMPLATE.indexOf(marker);
  if (start < 0) throw new Error(`Marker not in templates/index.html: ${marker}`);
  const tagStart = TEMPLATE.lastIndexOf("<", start);
  const end = TEMPLATE.indexOf(endMarker, start);
  if (end < 0) throw new Error(`End marker not found after ${marker}: ${endMarker}`);
  return stripJinja(TEMPLATE.slice(tagStart, end + endMarker.length));
}

export function templateText() {
  return TEMPLATE;
}

/**
 * @param {object} options
 * @param {string} options.body           markup for <body>
 * @param {Function} [options.before]     runs against window before the scripts
 * @param {object} [options.media]        matchMedia answers by query substring
 */
export async function bootApp({ body, before, media = {} } = {}) {
  const errors = [];
  const loaded = loadScripts(APP_SCRIPTS, {
    body,
    before(window) {
      window.addEventListener("error", (event) => errors.push(event.error || event.message));
      window.matchMedia = (query) => ({
        media: query,
        matches: Object.entries(media).some(([part, value]) => query.includes(part) && value),
        addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {},
      });
      window.fetch = () => new Promise(() => {});
      // jsdom does not draw; without a context letter-clouds.js stays quiet
      // instead of writing "Not implemented" to stderr on every call.
      window.HTMLCanvasElement.prototype.getContext = () => null;
      // Defined by static/demo.js (an ES module, not loaded here).
      window.createStartDemoChip = () => {};
      before?.(window);
    },
  });
  if (loaded.document.readyState === "loading") {
    await new Promise((resolve) => loaded.document.addEventListener("DOMContentLoaded", resolve));
  }
  return { ...loaded, errors };
}

/** Let queued tasks (MutationObserver, timers at 0 ms, promise chains) run. */
export function settle(window, ms = 0) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}
