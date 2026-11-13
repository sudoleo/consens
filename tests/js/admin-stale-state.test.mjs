/**
 * What the admin page shows after an action is what is true after it.
 *
 * The count of reported pages was only recounted under the filter Reported:
 * reviewed under All, the Overview kept asking for a review that was done.
 * And a preset pick redrew the whole Models tab, because the guard looked for
 * a select the preset's own redraw had already taken off the page.
 *
 * admin.js imports the Firebase SDK from a CDN and cannot be imported here;
 * the sections run as classic scripts against constructed API answers.
 */

import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";
import { JSDOM } from "jsdom";

import { ROOT } from "./helpers/appWindow.mjs";

const SOURCE = readFileSync(path.join(ROOT, "static/js/admin.js"), "utf8");

function section(from, to) {
    const start = SOURCE.indexOf(from);
    const end = SOURCE.indexOf(to, start);
    if (start < 0 || end <= start) throw new Error(`${from} not found in static/js/admin.js`);
    return SOURCE.slice(start, end);
}

function boot(body, lines) {
    const dom = new JSDOM(`<!doctype html><html><body>${body}</body></html>`,
        { runScripts: "dangerously", url: "https://consens.io/admin" });
    const script = dom.window.document.createElement("script");
    script.textContent = lines.join("\n");
    dom.window.document.body.appendChild(script);
    return dom.window;
}

const REPORTED = { share_id: "A", needs_review: true, status: "live" };

describe("reported pages on the Overview", () => {
    function bootShares() {
        return boot('<button id="loadReportedSharesBtn"></button><button id="loadAllSharesBtn"></button><p id="sharesStatus"></p>', [
            "window.requests = []; window.counts = []; window.reported = [];",
            "var overviewErrors = new Map();",
            "function overviewFailed() {}",
            "function renderOverview() { window.counts.push(unreviewedShares); }",
            "function renderShares() {}",
            "async function loadAdminWatches() {}",
            "window.confirm = () => true;",
            "async function shareAdminRequest(method, url) {",
            "    window.requests.push(`${method} ${url}`);",
            "    if (method !== 'GET') { window.reported = []; return {}; }",
            "    return { shares: url.includes('filter=reported') ? window.reported : window.reported.concat([{ share_id: 'B' }]) };",
            "}",
            section("// === Shared pages ===", "function formatAdminDay"),
            "window.loadShares = loadShares; window.moderateShare = moderateShare; window.deleteShare = deleteShare;",
        ]);
    }

    it.each([
        ["reviewed", window => window.moderateShare("A", { indexed: false })],
        ["deleted", window => window.deleteShare("A", "A question")],
    ])("are counted anew when one is %s under All", async (_what, act) => {
        const window = bootShares();
        window.reported = [REPORTED];
        await window.loadShares("reported");
        expect(window.counts.at(-1)).toBe(1);
        await window.loadShares("all");

        await act(window);
        expect(window.requests.at(-1)).toBe("GET /api/admin/shares?filter=reported");
        expect(window.counts.at(-1)).toBe(0);
    });

    it("need no second request under Reported", async () => {
        const window = bootShares();
        window.reported = [REPORTED];
        await window.loadShares("reported");
        await window.moderateShare("A", { indexed: false });
        expect(window.requests).toEqual([
            "GET /api/admin/shares?filter=reported",
            "POST /api/admin/shares/A/moderate",
            "GET /api/admin/shares?filter=reported",
        ]);
        expect(window.counts.at(-1)).toBe(0);
    });
});

describe("a preset pick", () => {
    it("redraws the preset only, once", () => {
        const window = boot('<section id="tab-models"><div id="presetModelsContainer"></div><select id="other"></select></section>', [
            "window.drawn = [];",
            "function renderJudgeSelects() { window.drawn.push('judges'); }",
            "function renderConsensusAddSelect() { window.drawn.push('add'); }",
            "function renderWatchModelConfig() { window.drawn.push('watch'); }",
            // As in admin.js: every draw replaces the selects, the pick's own listener draws first.
            "function renderPresetModels() {",
            "    window.drawn.push('presets');",
            "    const box = document.getElementById('presetModelsContainer');",
            "    box.innerHTML = '';",
            "    const select = document.createElement('select');",
            "    select.id = 'preset-daily-0'; select.dataset.presetId = 'daily';",
            "    select.addEventListener('change', () => { renderPresetModels(); document.getElementById(select.id)?.focus(); });",
            "    box.appendChild(select);",
            "}",
            section("document.getElementById('tab-models').addEventListener('change'", "// ===="),
            "renderPresetModels(); window.drawn.length = 0;",
        ]);
        const doc = window.document;
        doc.getElementById("preset-daily-0").dispatchEvent(new window.Event("change", { bubbles: true }));
        expect(window.drawn).toEqual(["presets"]);
        expect(doc.activeElement).toBe(doc.getElementById("preset-daily-0"));

        // A provider list that changed still reaches everything that lists its models.
        doc.getElementById("other").dispatchEvent(new window.Event("change", { bubbles: true }));
        expect(window.drawn).toEqual(["presets", "judges", "add", "presets", "watch"]);
    });
});
