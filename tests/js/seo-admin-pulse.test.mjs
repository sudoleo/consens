/**
 * The SEO tab shows one weekly pulse: the week's numbers, what moved and the
 * pages the pulse set to noindex (each with an undo). A failed run must say so
 * at the top instead of leaving last week's numbers looking current.
 *
 * Drives the real markup from templates/admin.html and the SEO section of
 * static/js/admin.js against constructed API responses.
 */

import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";
import { JSDOM } from "jsdom";

import { ROOT } from "./helpers/appWindow.mjs";

function seoTabMarkup() {
    const html = readFileSync(path.join(ROOT, "templates/admin.html"), "utf8");
    const start = html.indexOf('<section id="tab-seo"');
    const end = html.indexOf("</section>", start) + "</section>".length;
    if (start < 0 || end <= start) throw new Error("#tab-seo not found in templates/admin.html");
    return html.slice(start, end).replace(" hidden>", ">");
}

/**
 * admin.js is an ES module that imports the Firebase SDK from a CDN, so it
 * cannot be imported here. The SEO section is plain global-scope code, so it
 * runs as a classic script once the module boilerplate around it is dropped.
 */
function seoModuleSource() {
    const js = readFileSync(path.join(ROOT, "static/js/admin.js"), "utf8");
    const start = js.indexOf("// === SEO pulse ===");
    const end = js.indexOf("onAuthStateChanged(auth");
    if (start < 0 || end <= start) throw new Error("SEO section not found in static/js/admin.js");
    return js.slice(start, end);
}

function bootSeoTab() {
    const dom = new JSDOM(
        `<!doctype html><html><head></head><body>${seoTabMarkup()}</body></html>`,
        { runScripts: "dangerously", url: "https://consens.io/admin" }
    );
    const { window } = dom;
    window.requests = [];
    const script = window.document.createElement("script");
    script.textContent = [
        "window.shareAdminRequest = async function (method, url, body) { window.requests.push([method, url, body]); return window.nextResponse; };",
        "window.formatAdminTime = function (value) { return value ? 'T' : 'never'; };",
        "window.actionBtn = function (label, onClick) { const b = document.createElement('button'); b.textContent = label; b.onclick = onClick; return b; };",
        seoModuleSource(),
    ].join("\n");
    window.document.body.appendChild(script);
    return window;
}

const REPORT = {
    window: { start: "2026-09-27", end: "2026-10-03" },
    week: { impressions: 506, clicks: 3, position: 8.8 },
    prev_week: { impressions: 172, clicks: 4 },
    movers: {
        up: [{ path: "/", impressions: 243, prev_impressions: 35, delta: 208, clicks: 1, top_query: "consens" }],
        down: [{ path: "/topics/gpt-6", impressions: 2, prev_impressions: 30, delta: -28, clicks: 0, top_query: "" }],
    },
    noindexed: [],
};

describe("SEO pulse tab", () => {
    it("shows the week, its change and the query behind each move", () => {
        const window = bootSeoTab();
        const doc = window.document;
        window.renderSeoPulse({
            enabled: true,
            next_run_at: "2026-10-12T07:00:00+00:00",
            report: REPORT,
            history: [{ end: "2026-09-26", impressions: 172, clicks: 4 }, { end: "2026-10-03", impressions: 506, clicks: 3 }],
            noindexed: [],
        });

        expect(doc.getElementById("seoPulseWeek").textContent).toMatch(/^Week 27 \S+ – 3 Oct$/);
        expect(doc.getElementById("seoPulseImpressions").textContent).toBe("506");
        expect(doc.getElementById("seoPulseImpressionsPrev").textContent).toBe("prev 172, +194%");
        expect(doc.getElementById("seoPulseError").hidden).toBe(true);
        expect(doc.getElementById("seoPulseTrend").children).toHaveLength(2);
        const moves = [...doc.querySelectorAll("#seoPulseMovers li")].map(li => li.textContent);
        expect(moves[0]).toContain("↑ +208");
        expect(moves[0]).toContain("“consens”");
        expect(moves[1]).toContain("↓ -28");
        expect(doc.getElementById("seoPulseNoindexed").textContent).toBe("None so far.");
    });

    it("puts a failed run at the top instead of showing stale numbers", () => {
        const window = bootSeoTab();
        const doc = window.document;
        window.renderSeoPulse({ enabled: true, report: { error: "Not configured: GSC_SITE_URL." }, history: [], noindexed: [] });

        const error = doc.getElementById("seoPulseError");
        expect(error.hidden).toBe(false);
        expect(error.textContent).toBe("Last run failed: Not configured: GSC_SITE_URL.");
        expect(doc.getElementById("seoPulseImpressions").textContent).toBe("–");
        expect(doc.getElementById("seoPulseWeek").textContent).toBe("No report yet");
    });

    it("offers an undo for every page the pulse set to noindex", async () => {
        const window = bootSeoTab();
        const doc = window.document;
        const entry = { share_id: "ZZZZZZZZZZZZZZZZ", path: "/s/x-ZZZZZZZZZZZZZZZZ", impressions_90d: 2, at: "2026-10-05T07:00:00+00:00" };
        window.renderSeoPulse({ enabled: false, report: REPORT, history: [], noindexed: [entry] });

        expect(doc.getElementById("seoPulseSchedule").textContent).toContain("Paused");
        expect(doc.getElementById("seoPulseEnabled").checked).toBe(false);
        const keep = doc.querySelector("#seoPulseNoindexed button");
        expect(keep.textContent).toBe("Keep indexed");

        window.nextResponse = { enabled: false, report: REPORT, history: [], noindexed: [] };
        await keep.onclick();
        expect(window.requests).toEqual([["POST", "/api/admin/seo/shares/ZZZZZZZZZZZZZZZZ/keep", {}]]);
        expect(doc.getElementById("seoPulseNoindexed").textContent).toBe("None so far.");
    });
});
