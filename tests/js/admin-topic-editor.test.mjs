/**
 * R20: the Topic editor must never save A's form as B.
 *
 * selectAdminTopic used to switch the global id before the GET; a failed or
 * overtaken load left A's form under B's id, and Save then PUT A's content to
 * B. The real Topic section of static/js/admin.js runs here against the real
 * form markup from templates/admin.html; only the admin HTTP client is faked.
 */

import { readFileSync } from "node:fs";
import path from "node:path";

import { afterEach, describe, expect, it } from "vitest";
import { JSDOM } from "jsdom";

import { ROOT } from "./helpers/appWindow.mjs";

function topicSection() {
    const js = readFileSync(path.join(ROOT, "static/js/admin.js"), "utf8");
    const start = js.indexOf("// === Public Topic tickers ===");
    const end = js.indexOf("// === Read-only SEO data foundation ===");
    if (start < 0 || end <= start) throw new Error("Topic section not found in static/js/admin.js");
    return js.slice(start, end);
}

function topicMarkup() {
    const html = readFileSync(path.join(ROOT, "templates/admin.html"), "utf8");
    const start = html.indexOf('<div class="topic-admin-actions u-mb-14">');
    const end = html.indexOf('<section id="tab-seo"');
    if (start < 0 || end <= start) throw new Error("Topic markup not found in templates/admin.html");
    return html.slice(start, end);
}

const TOPICS = {
    A: { id: "A", title: "Topic A", slug: "topic-a", status: "active", lead_question: "A?", category: "c" },
    B: { id: "B", title: "Topic B", slug: "topic-b", status: "active", lead_question: "B?", category: "c" },
};

const doms = [];
afterEach(() => doms.splice(0).forEach(dom => dom.window.close()));

function boot() {
    const dom = new JSDOM(`<!doctype html><html><body>${topicMarkup()}</body></html>`, {
        runScripts: "dangerously",
        url: "https://consens.io/admin",
    });
    doms.push(dom);
    const { window } = dom;
    const calls = [];
    const pending = [];
    window.__request = (method, url, payload) => {
        calls.push({ method, url, payload });
        return new Promise((resolve, reject) => pending.push({ method, url, resolve, reject }));
    };
    const script = window.document.createElement("script");
    script.textContent = [
        "const providers = [];",
        "let globalModelsData = {};",
        "function meta() { return {}; }",
        "function providerLabel(p) { return p; }",
        "function formatAdminTime(v) { return String(v || ''); }",
        "const shareAdminRequest = (...args) => window.__request(...args);",
        topicSection(),
        "window.__topic = { selectAdminTopic, saveAdminTopic, loadAdminTopics, newAdminTopic, resetAdminTopicEditor };",
    ].join("\n");
    window.document.body.appendChild(script);
    return { window, document: window.document, calls, pending, api: window.__topic };
}

const tick = () => new Promise(resolve => setTimeout(resolve, 0));

async function answer(ctx, url, body) {
    await tick();
    const request = ctx.pending.find(item => item.url === url);
    ctx.pending.splice(ctx.pending.indexOf(request), 1);
    request.resolve(body);
    await tick();
}

async function fail(ctx, url) {
    await tick();
    const request = ctx.pending.find(item => item.url === url);
    ctx.pending.splice(ctx.pending.indexOf(request), 1);
    request.reject(new Error("Loading failed."));
    await tick();
}

async function openA(ctx) {
    const loaded = ctx.api.selectAdminTopic("A");
    await answer(ctx, "/api/admin/topics/A", { topic: TOPICS.A, runs: [] });
    await loaded;
    expect(ctx.document.getElementById("adminTopicTitle").value).toBe("Topic A");
}

const puts = ctx => ctx.calls.filter(call => call.method === "PUT" || call.method === "POST");

describe("admin Topic editor", () => {
    it("never saves the A form under B after B failed to load", async () => {
        const ctx = boot();
        await openA(ctx);

        const switching = ctx.api.selectAdminTopic("B");
        expect(ctx.document.getElementById("saveAdminTopicBtn").disabled).toBe(true);
        await fail(ctx, "/api/admin/topics/B");
        await switching;
        expect(ctx.document.getElementById("saveAdminTopicBtn").disabled).toBe(true);
        expect(ctx.document.getElementById("topicAdminStatus").textContent).toMatch(/Saving stays disabled/);

        // Even a forced call (keyboard, stale handler) writes nothing.
        await ctx.api.saveAdminTopic();
        expect(puts(ctx)).toEqual([]);
    });

    it("drops a slow A answer that arrives after B was selected", async () => {
        const ctx = boot();
        const slowA = ctx.api.selectAdminTopic("A");
        const fastB = ctx.api.selectAdminTopic("B");
        await answer(ctx, "/api/admin/topics/B", { topic: TOPICS.B, runs: [] });
        await fastB;
        await answer(ctx, "/api/admin/topics/A", { topic: TOPICS.A, runs: [] });
        await slowA;

        expect(ctx.document.getElementById("adminTopicTitle").value).toBe("Topic B");
        const saving = ctx.api.saveAdminTopic();
        await tick();
        expect(puts(ctx)).toHaveLength(1);
        expect(puts(ctx)[0].url).toBe("/api/admin/topics/B");
        expect(puts(ctx)[0].payload.title).toBe("Topic B");
        ctx.pending.splice(0).forEach(item => item.reject(new Error("done")));
        await saving;
    });

    it("an account change invalidates the editor and any open request", async () => {
        const ctx = boot();
        await openA(ctx);
        const late = ctx.api.selectAdminTopic("B");
        ctx.api.resetAdminTopicEditor();
        await answer(ctx, "/api/admin/topics/B", { topic: TOPICS.B, runs: [] });
        await late;

        expect(ctx.document.getElementById("topicAdminForm").hidden).toBe(true);
        await ctx.api.saveAdminTopic();
        expect(puts(ctx)).toEqual([]);
    });

    it("keeps saving a new Topic and a loaded Topic working", async () => {
        const ctx = boot();
        ctx.api.newAdminTopic();
        expect(ctx.document.getElementById("saveAdminTopicBtn").disabled).toBe(false);
        ctx.document.getElementById("adminTopicTitle").value = "Fresh";
        const creating = ctx.api.saveAdminTopic();
        await tick();
        expect(puts(ctx)[0]).toMatchObject({ method: "POST", url: "/api/admin/topics" });
        ctx.pending.splice(0).forEach(item => item.reject(new Error("stop")));
        await creating;

        await openA(ctx);
        const updating = ctx.api.saveAdminTopic();
        await tick();
        expect(puts(ctx)[1]).toMatchObject({ method: "PUT", url: "/api/admin/topics/A" });
        expect(puts(ctx)[1].payload.title).toBe("Topic A");
        ctx.pending.splice(0).forEach(item => item.reject(new Error("stop")));
        await updating;
    });
});
